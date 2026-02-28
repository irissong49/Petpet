import threading
import wave
import struct
import tempfile
import os
import time
import random
import pyaudio
import pygame

# ── 参数配置 ──────────────────────────────────────────────
CHUNK = 1024          # 每次读取的帧数
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000          # 采样率

TRIGGER_DB = 70       # 超过这个 dB 才开始录音
SILENCE_DB = 35       # 低于这个 dB 视为静音
SILENCE_TIMEOUT = 1 # 静音持续多少秒后停止录音
# ─────────────────────────────────────────────────────────


def rms_to_db(rms: float) -> float:
    """RMS 转 dB，避免 log(0)"""
    if rms < 1:
        return 0.0
    import math
    return 20 * math.log10(rms)


def calc_rms(data: bytes) -> float:
    """计算一帧音频的 RMS"""
    count = len(data) // 2
    shorts = struct.unpack(f"{count}h", data)
    if count == 0:
        return 0.0
    return (sum(s ** 2 for s in shorts) / count) ** 0.5


def dummy_tts(audio_path: str) -> str:
    """
    占位 TTS 函数。
    实际使用时替换为真实模型调用，返回回复音频的路径（wav）。
    
    参数:
        audio_path: 用户说话录音的临时 wav 文件路径
    返回:
        回复音频的 wav 文件路径
    """
    print(f"[TTS] 收到录音: {audio_path}，生成回复中...")
    time.sleep(0.5)  # 模拟处理延迟

    # 生成一段简单的静音 wav 作为占位回复
    reply_path = tempfile.mktemp(suffix="_reply.wav")
    with wave.open(reply_path, "w") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        # 写入 1 秒静音
        wf.writeframes(b"\x00\x00" * RATE)

    print(f"[TTS] 回复音频已生成: {reply_path}")
    #return reply_path
    return random.choice(["./shigure_idle1.mp3","./shigure_idle2.mp3"])


# def play_wav(path: str):
#     """用 pyaudio 播放 wav 文件"""
#     pa = pyaudio.PyAudio()
#     with wave.open(path, "rb") as wf:
#         stream = pa.open(
#             format=pa.get_format_from_width(wf.getsampwidth()),
#             channels=wf.getnchannels(),
#             rate=wf.getframerate(),
#             output=True,
#         )
#         data = wf.readframes(CHUNK)
#         while data:
#             stream.write(data)
#             data = wf.readframes(CHUNK)
#         stream.stop_stream()
#         stream.close()
#     pa.terminate()

def play_wav(path: str):
    """用 pygame 播放音频，支持 mp3 和 wav"""
    import pygame
    pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    pygame.mixer.quit()



class VoiceListener(threading.Thread):
    """
    后台线程：持续监听麦克风，触发录音 → TTS → 播放。
    在播放回复期间不会监听新的输入。

    用法:
        listener = VoiceListener()
        listener.start()
        ...
        listener.stop()
    """

    def __init__(self):
        super().__init__(daemon=True)
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

        print("[监听] 开始监听麦克风...")

        try:
            while not self._stop_event.is_set():
                # ── 阶段 1：等待触发 ──────────────────────
                data = stream.read(CHUNK, exception_on_overflow=False)
                db = rms_to_db(calc_rms(data))

                if db < TRIGGER_DB:
                    continue

                # ── 阶段 2：录音 ──────────────────────────
                print(f"[录音] 检测到声音 {db:.1f} dB，开始录音...")
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
                            print("[录音] 静音超时，停止录音")
                            break
                    else:
                        silence_start = None  # 有声音，重置静音计时

                if self._stop_event.is_set():
                    break

                # ── 阶段 3：保存录音并送 TTS ─────────────
                tmp_in = tempfile.mktemp(suffix="_input.wav")
                with wave.open(tmp_in, "w") as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(pa.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(b"".join(frames))

                reply_path = dummy_tts(tmp_in)

                # ── 阶段 4：播放回复（此期间不监听）──────
                print("[播放] 正在播放回复...")
                stream.stop_stream()   # 暂停麦克风
                play_wav(reply_path)
                stream.start_stream()  # 恢复监听
                print("[监听] 播放完毕，继续监听...")

                # 清理临时文件
                for f in (tmp_in, reply_path):
                    try:
                        pass
                        #os.remove(f)
                    except OSError:
                        pass

        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            print("[监听] 已停止")


if __name__ == "__main__":
    # 单独测试用
    listener = VoiceListener()
    listener.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在退出...")
        listener.stop()
        listener.join()