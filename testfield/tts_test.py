"""
CosyVoice 声音复刻完整流程 - 公网 URL 版
==========================================
前置准备：
  1. pip install dashscope
  2. 配置环境变量：
       export DASHSCOPE_API_KEY="sk-xxxxxxxxxxxx"
  3. 将 voice_to_copy.wav 上传到你的服务器，确保公网可直接访问

用法：
  python cosyvoice_clone.py <音频公网URL> [合成文本]

示例：
  python cosyvoice_clone.py https://your-server.com/voice_to_copy.wav
  python cosyvoice_clone.py https://your-server.com/voice_to_copy.wav "你好，这是测试文本"
"""

import os
import sys
import time
import datetime


# ──────────────────────────────────────────────
# ① 配置区（按需修改）
# ──────────────────────────────────────────────
TARGET_MODEL   = "cosyvoice-v3-plus"   # 复刻 & 合成模型必须一致
VOICE_PREFIX   = "myvoice"             # 音色前缀，仅限字母/数字/下划线，≤10 字符
LANGUAGE_HINTS = ["zh"]                # 音频语言："zh"/"en"/"ja"/"ko"/"fr"/"de"/"ru"

DEFAULT_TEXT   = "你好，这是用我的声音复刻合成的一段语音，感谢使用 CosyVoice！"
OUTPUT_PATH    = "output.mp3"          # 合成结果保存路径

# 轮询参数
POLL_INTERVAL_SEC = 10
MAX_POLL_ATTEMPTS = 36  # 最多等 6 分钟


# ──────────────────────────────────────────────
# ② 工具函数
# ──────────────────────────────────────────────
def log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def parse_args():
    if len(sys.argv) < 2:
        print("用法：python cosyvoice_clone.py <音频公网URL> [合成文本]")
        print("示例：python cosyvoice_clone.py https://your-server.com/voice_to_copy.wav")
        sys.exit(1)

    audio_url = sys.argv[1]
    text      = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_TEXT
    return audio_url, text


def check_env():
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("❌ 错误：请先配置环境变量 DASHSCOPE_API_KEY")
        print("   export DASHSCOPE_API_KEY='sk-xxxxxxxxxxxx'")
        sys.exit(1)
    return api_key


# ──────────────────────────────────────────────
# ③ 主流程
# ──────────────────────────────────────────────
def main():
    audio_url, text = parse_args()
    api_key         = check_env()

    try:
        import dashscope
        from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer
    except ImportError:
        print("❌ 缺少 dashscope 库，请执行：pip install dashscope")
        sys.exit(1)

    dashscope.api_key = "sk-2ad0d19e2f704757b481f8447d34658f"

    print("\n" + "=" * 55)
    print("  CosyVoice 声音复刻 - 完整流程")
    print("=" * 55)
    print(f"  音频 URL   : {audio_url}")
    print(f"  合成模型   : {TARGET_MODEL}")
    print(f"  合成文本   : {text}")
    print("=" * 55)

    service = VoiceEnrollmentService()

    # ── Step 1: 创建复刻音色 ────────────────────
    print("\n【Step 1】创建复刻音色")
    try:
        voice_id = service.create_voice(
            target_model=TARGET_MODEL,
            prefix=VOICE_PREFIX,
            url=audio_url,
            language_hints=LANGUAGE_HINTS,
        )
        log(f"✅ 提交成功！Request ID：{service.get_last_request_id()}")
        log(f"   Voice ID：{voice_id}")
    except Exception as e:
        print(f"❌ 创建音色失败：{e}")
        sys.exit(1)

    # ── Step 2: 轮询等待音色就绪 ────────────────
    print(f"\n【Step 2】等待音色审核（每 {POLL_INTERVAL_SEC}s 查询一次，最多 {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SEC // 60} 分钟）")
    voice_ready = False
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        try:
            info   = service.query_voice(voice_id=voice_id)
            status = info.get("status", "UNKNOWN")
            log(f"轮询 {attempt}/{MAX_POLL_ATTEMPTS}：状态 = {status}")

            if status == "OK":
                log("✅ 音色审核通过，可以使用！")
                voice_ready = True
                break
            elif status == "UNDEPLOYED":
                print("❌ 音色审核不通过（UNDEPLOYED）")
                print("   建议：检查音频质量（10~20秒、无噪音、无背景音乐、采样率 ≥ 16kHz）")
                sys.exit(1)
            else:
                time.sleep(POLL_INTERVAL_SEC)
        except Exception as e:
            log(f"查询出错（{e}），继续重试...")
            time.sleep(POLL_INTERVAL_SEC)

    if not voice_ready:
        print("❌ 超时：音色长时间未就绪，请稍后使用以下 Voice ID 手动重试合成：")
        print(f"   Voice ID：{voice_id}")
        sys.exit(1)

    # ── Step 3: 合成语音 ────────────────────────
    print(f"\n【Step 3】使用复刻音色合成语音")
    log(f"合成文本：{text}")
    try:
        synthesizer = SpeechSynthesizer(model=TARGET_MODEL, voice=voice_id)
        audio_data  = synthesizer.call(text)
        log(f"✅ 合成成功！Request ID：{synthesizer.get_last_request_id()}")
    except Exception as e:
        print(f"❌ 语音合成失败：{e}")
        sys.exit(1)

    # ── Step 4: 保存音频 ────────────────────────
    with open(OUTPUT_PATH, "wb") as f:
        f.write(audio_data)
    size_kb = len(audio_data) / 1024
    log(f"✅ 已保存至：{OUTPUT_PATH}（{size_kb:.1f} KB）")

    # ── 完成摘要 ────────────────────────────────
    print("\n" + "=" * 55)
    print("  🎉 全部流程完成！")
    print("=" * 55)
    print(f"  Voice ID : {voice_id}")
    print(f"  输出音频 : {OUTPUT_PATH}")
    print()
    print("  💡 Voice ID 已永久保存在账号中，下次可直接用于合成：")
    print(f"     SpeechSynthesizer(model='{TARGET_MODEL}', voice='{voice_id}')")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()