"""
急诊酱 - 语音识别 → LLM 对话 → 语音合成
用法：
  python chat_tts.py <输入音频文件> [输出mp3文件]
示例：
  python chat_tts.py input.wav
  python chat_tts.py input.wav output.mp3
"""

import io
import sys
import datetime
from http import HTTPStatus

import dashscope
from dashscope.audio.asr import Recognition
from dashscope.audio.tts_v2 import SpeechSynthesizer
from openai import OpenAI

# ──────────────────────────────────────────────
# 配置区（直接填写，不读环境变量）
# ──────────────────────────────────────────────
DASHSCOPE_API_KEY = "sk-2ad0d19e2f704757b481f8447d34658f"  # ← 填入 DashScope API Key
DEEPSEEK_API_KEY  = "sk-7c69d9db9b0b44e2bec34c57ff23b105"

ASR_MODEL     = "paraformer-realtime-v2"
LLM_MODEL     = "deepseek-chat"
TTS_MODEL     = "cosyvoice-v3-plus"
VOICE_ID      = "cosyvoice-v3-plus-myvoice-fa6128de021f436b97886a495a3e853e"
TRIM_START_MS = 2000
DEFAULT_OUTPUT = "output.mp3"

SYSTEM_PROMPT = """
你是一个可爱的无口日系水色萌妹，你叫急诊酱，你要以呆萌和帮助你的主人为主。
你的回复应该尽量口语化和简短，像是真人的对话场景而非ai助手。
因为之后会被用于生成语音进行回复，所以**不需要**任何括号里的动作描述。
"""

# ──────────────────────────────────────────────

def log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def asr(audio_file: str) -> str:
    """用 Paraformer 识别本地音频文件，返回识别文本"""
    dashscope.api_key = DASHSCOPE_API_KEY
    log(f"正在识别音频：{audio_file}")

    fmt = audio_file.rsplit(".", 1)[-1].lower()  # 从文件扩展名推断格式

    # 自动检测真实采样率
    try:
        import librosa
        _, real_sr = librosa.load(audio_file, sr=None)
    except Exception:
        try:
            from pydub import AudioSegment
            real_sr = AudioSegment.from_file(audio_file).frame_rate
        except Exception:
            real_sr = 16000  # fallback

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
    """调用 DeepSeek 生成回复"""
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


def synthesize(text: str, output_path: str = DEFAULT_OUTPUT):
    """用 CosyVoice 合成语音并保存"""
    dashscope.api_key = DASHSCOPE_API_KEY
    log("正在合成语音...")

    synthesizer = SpeechSynthesizer(model=TTS_MODEL, voice=VOICE_ID)
    audio_data = synthesizer.call(text)
    log(f"✅ 合成成功！Request ID：{synthesizer.get_last_request_id()}")

    try:
        from pydub import AudioSegment
        audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_data))
        trimmed = audio_segment[TRIM_START_MS:]
        trimmed.export(output_path, format="mp3")
        log(f"✅ 已裁掉开头 {TRIM_START_MS // 1000}s，保存至：{output_path}（{len(trimmed) / 1000:.1f}s）")
    except ImportError:
        print("⚠️  未安装 pydub，将直接保存原始音频（不裁剪）")
        with open(output_path, "wb") as f:
            f.write(audio_data)
        log(f"✅ 已保存至：{output_path}")


def main():
    if len(sys.argv) < 2:
        print("用法：python chat_tts.py <输入音频文件> [输出mp3文件]")
        print("示例：python chat_tts.py input.wav")
        sys.exit(1)

    input_audio = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_OUTPUT

    print("\n" + "=" * 50)
    print("  急诊酱 ASR → Chat → TTS")
    print("=" * 50)
    print(f"  输入音频：{input_audio}")
    print(f"  输出语音：{output_path}")
    print("=" * 50 + "\n")

    # 1. 语音识别
    user_text = asr(input_audio)
    if not user_text.strip():
        print("❌ 未识别到有效语音内容，退出。")
        sys.exit(1)

    # 2. LLM 生成回复
    reply = chat(user_text)

    # 3. TTS 合成
    synthesize(reply, output_path)


if __name__ == "__main__":
    main()