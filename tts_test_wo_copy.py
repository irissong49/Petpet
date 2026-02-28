"""
CosyVoice 语音合成 - 直接使用已有音色
======================================
用法：
  python tts_synthesize.py <voice_id> <合成文本> [输出文件名]

示例：
  python tts_synthesize.py cosyvoice-v3-plus-myvoice-xxxxxxxx "你好，世界"
  python tts_synthesize.py cosyvoice-v3-plus-myvoice-xxxxxxxx "你好，世界" my_output.mp3
"""

import os
import sys
import io
import datetime


# ──────────────────────────────────────────────
# 配置区
# ──────────────────────────────────────────────
TARGET_MODEL   = "cosyvoice-v3-plus"   # 必须与复刻时一致
DEFAULT_OUTPUT = "output.mp3"
TRIM_START_MS  = 2000                  # 裁掉开头的毫秒数（2000 = 2秒）


def log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def main():
    # 参数解析
    if len(sys.argv) < 2:
        print("用法：python tts_synthesize.py <voice_id> <合成文本> [输出文件名]")
        print("示例：python tts_synthesize.py cosyvoice-v3-plus-myvoice-xxxxxxxx \"你好，世界\"")
        sys.exit(1)

    voice_id    = 'cosyvoice-v3-plus-myvoice-fa6128de021f436b97886a495a3e853e'
    text        = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) >=3 else DEFAULT_OUTPUT

    # 检查 API Key
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("❌ 错误：请先配置环境变量 DASHSCOPE_API_KEY")
        print("   PowerShell : $env:DASHSCOPE_API_KEY = 'sk-xxxxxxxxxxxx'")
        print("   Linux/Mac  : export DASHSCOPE_API_KEY='sk-xxxxxxxxxxxx'")
        sys.exit(1)

    try:
        import dashscope
        from dashscope.audio.tts_v2 import SpeechSynthesizer
    except ImportError:
        print("❌ 缺少 dashscope 库，请执行：pip install dashscope")
        sys.exit(1)

    dashscope.api_key = api_key

    print("\n" + "=" * 50)
    print("  CosyVoice 语音合成")
    print("=" * 50)
    print(f"  Voice ID : {voice_id}")
    print(f"  模型     : {TARGET_MODEL}")
    print(f"  文本     : {text}")
    print(f"  输出     : {output_path}")
    print("=" * 50)

    # 合成
    log("正在合成...")
    try:
        synthesizer = SpeechSynthesizer(model=TARGET_MODEL, voice=voice_id)
        audio_data  = synthesizer.call(text)
        log(f"✅ 合成成功！Request ID：{synthesizer.get_last_request_id()}")
    except Exception as e:
        print(f"❌ 合成失败：{e}")
        sys.exit(1)

    # 裁掉开头 TRIM_START_MS 毫秒后保存
    try:
        from pydub import AudioSegment
        audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_data))
        trimmed       = audio_segment[TRIM_START_MS:]
        trimmed.export(output_path, format="mp3")
        log(f"✅ 已裁掉开头 {TRIM_START_MS // 1000}s，保存至：{output_path}（{len(trimmed) / 1000:.1f}s）")
    except ImportError:
        print("⚠️  未安装 pydub，将直接保存原始音频（不裁剪）")
        print("   安装方法：pip install pydub")
        with open(output_path, "wb") as f:
            f.write(audio_data)
        log(f"✅ 已保存至：{output_path}")
    print()


if __name__ == "__main__":
    main()