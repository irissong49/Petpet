import threading
import wave
import struct
import tempfile
import os
import io
import time
import random
import math
import pyaudio
import pygame
from http import HTTPStatus

from PyQt5.QtCore import QObject, pyqtSignal

# ── 参数配置 ──────────────────────────────────────────────
CHUNK           = 1024
FORMAT          = pyaudio.paInt16
CHANNELS        = 1
RATE            = 16000

TRIGGER_DB      = 70    # 超过这个 dB 才开始录音
SILENCE_DB      = 50   # 低于这个 dB 视为静音
SILENCE_TIMEOUT = 1     # 静音持续多少秒后停止录音

# ── 回复模式开关 ───────────────────────────────────────────
# "random" : 随机播放本地音频（无文字对话框）
# "ai"     : 调用 ASR → DeepSeek → CosyVoice TTS，并弹出对话框
REPLY_MODE = "ai"

# ── 随机回复音频列表（REPLY_MODE = "random" 时使用）─────────
RANDOM_REPLIES = [
    "./shigure_idle1.mp3",
    "./shigure_idle2.mp3",
]

# ── AI 模式配置 ────────────────────────────────────────────
DASHSCOPE_API_KEY = "sk-2ad0d19e2f704757b481f8447d34658f"  # ← 填入
DEEPSEEK_API_KEY  = "sk-7c69d9db9b0b44e2bec34c57ff23b105"

ASR_MODEL     = "paraformer-realtime-v2"
LLM_MODEL     = "deepseek-chat"
TTS_MODEL     = "cosyvoice-v3-plus"
VOICE_ID      = "cosyvoice-v3-plus-myvoice-fa6128de021f436b97886a495a3e853e"
TRIM_START_MS = 2000

# SYSTEM_PROMPT = """
# 你是一个可爱的无口日系水色萌妹，你叫急诊酱，你要以呆萌和帮助你的主人为主。
# 你的回复应该尽量口语化和简短，像是真人的对话场景而非ai助手。
# 因为之后会被用于生成语音进行回复，所以**不需要**任何括号里的动作描述。
# """


SYSTEM_PROMPT = """
你是一个有用的车载智能助手，你需要根据用户的语音输入，确定用户需要的操作。

你应当仅输出原子级操作或者原子级操作的组合，或者在意图过于不明确的时候提出可能的选项向用户提问。

输出原子级操作或者原子级操作的时序组合时，你的输出格式应该为[操作A，操作B……]
在意图过于不明确的时候提出可能的选项向用户提问时，你的输出格式应该为 “请问您是不是需要 操作A 或者 操作B？”

合法操作包括：
调高温度
调低温度
音量变大
音量变小
打开车窗
关闭车窗
调亮灯光
调暗灯光

"""


# ──────────────────────────────────────────────────────────


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def rms_to_db(rms: float) -> float:
    if rms < 1:
        return 0.0
    return 20 * math.log10(rms)


def calc_rms(data: bytes) -> float:
    count = len(data) // 2
    shorts = struct.unpack(f"{count}h", data)
    if count == 0:
        return 0.0
    return (sum(s ** 2 for s in shorts) / count) ** 0.5


# ── AI 回复流程 ────────────────────────────────────────────

def asr(audio_file: str) -> str:
    import dashscope
    from dashscope.audio.asr import Recognition

    dashscope.api_key = DASHSCOPE_API_KEY
    log(f"正在识别音频：{audio_file}")

    fmt = audio_file.rsplit(".", 1)[-1].lower()
    try:
        from pydub import AudioSegment
        real_sr = AudioSegment.from_file(audio_file).frame_rate
    except Exception:
        real_sr = RATE

    log(f"检测到采样率：{real_sr} Hz")
    recognition = Recognition(
        model=ASR_MODEL,
        format=fmt,
        sample_rate=real_sr,
        language_hints=["zh", "en"],
        callback=None,
    )
    result = recognition.call(audio_file)

    if result.status_code == HTTPStatus.OK:
        sentences = result.get_sentence()
        text = "".join(s["text"] for s in sentences) if sentences else ""
        log(f"✅ 识别结果：{text}")
        return text
    else:
        raise RuntimeError(f"ASR 失败：{result.message}")


def chat(user_input: str) -> str:
    from openai import OpenAI
    log("正在生成回复...")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_input},
        ],
        stream=False,
    )
    reply = response.choices[0].message.content
    log(f"✅ 急诊酱：{reply}")
    return reply


def synthesize(text: str) -> str:
    """合成语音，返回临时 mp3 文件路径"""
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer

    dashscope.api_key = DASHSCOPE_API_KEY
    log("正在合成语音...")

    synthesizer = SpeechSynthesizer(model=TTS_MODEL, voice=VOICE_ID)
    audio_data = synthesizer.call(text)
    log(f"✅ 合成成功！Request ID：{synthesizer.get_last_request_id()}")

    output_path = tempfile.mktemp(suffix="_reply.mp3")
    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_mp3(io.BytesIO(audio_data))
        trimmed = seg[TRIM_START_MS:]
        trimmed.export(output_path, format="mp3")
        log(f"✅ 已裁掉开头 {TRIM_START_MS // 1000}s（{len(trimmed) / 1000:.1f}s）")
    except ImportError:
        with open(output_path, "wb") as f:
            f.write(audio_data)

    return output_path


def play_audio(path: str):
    pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    pygame.mixer.quit()


# ── VoiceListener（QObject + Thread 双继承，支持 Qt 信号）──

class VoiceListener(QObject, threading.Thread):
    """
    后台线程：持续监听麦克风，触发录音 → 回复 → 播放。
    AI 模式下，LLM 生成的文字通过 reply_text 信号发送给 UI。
    """

    # 信号：携带 LLM 回复文字
    reply_text = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)
        threading.Thread.__init__(self, daemon=True)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )

        log(f"开始监听麦克风... 回复模式：{REPLY_MODE}")

        try:
            while not self._stop_event.is_set():
                # ── 阶段 1：等待触发 ──────────────────────
                data = stream.read(CHUNK, exception_on_overflow=False)
                db = rms_to_db(calc_rms(data))
                if db < TRIGGER_DB:
                    continue

                # ── 阶段 2：录音 ──────────────────────────
                log(f"检测到声音 {db:.1f} dB，开始录音...")
                frames = [data]
                silence_start = None

                while not self._stop_event.is_set():
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    db = rms_to_db(calc_rms(data))
                    frames.append(data)

                    if db < SILENCE_DB:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= SILENCE_TIMEOUT:
                            log("静音超时，停止录音")
                            break
                    else:
                        silence_start = None

                if self._stop_event.is_set():
                    break

                # ── 阶段 3：保存录音 ──────────────────────
                tmp_in = tempfile.mktemp(suffix="_input.wav")
                with wave.open(tmp_in, "w") as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(pa.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(b"".join(frames))

                # ── 阶段 4：获取回复 ──────────────────────
                reply_path = None
                if REPLY_MODE == "random":
                    reply_path = random.choice(RANDOM_REPLIES)

                elif REPLY_MODE == "ai":
                    try:
                        user_text = asr(tmp_in)
                        if user_text.strip():
                            reply_txt = chat(user_text)
                            # 发送文字信号给 UI（跨线程安全）
                            self.reply_text.emit(reply_txt)
                            reply_path = synthesize(reply_txt)
                        else:
                            log("⚠️  未识别到有效内容，跳过回复")
                    except Exception as e:
                        log(f"❌ AI 回复失败：{e}")

                # ── 阶段 5：播放（此期间暂停麦克风）───────
                if reply_path and os.path.exists(reply_path):
                    log("正在播放回复...")
                    stream.stop_stream()
                    play_audio(reply_path)
                    stream.start_stream()
                    log("播放完毕，继续监听...")
                else:
                    log("无回复音频，继续监听...")

                # 清理临时文件
                try:
                    os.remove(tmp_in)
                except OSError:
                    pass
                if REPLY_MODE == "ai" and reply_path:
                    try:
                        os.remove(reply_path)
                    except OSError:
                        pass

        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            log("已停止")


if __name__ == "__main__":
    # 单独测试（无 Qt 环境，信号不会被接收，仅测试音频流程）
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    listener = VoiceListener()
    listener.reply_text.connect(lambda t: print(f"[信号] {t}"))
    listener.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在退出...")
        listener.stop()
        listener.join()