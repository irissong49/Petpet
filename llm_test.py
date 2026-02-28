# Please install OpenAI SDK first: `pip3 install openai`
import os
from openai import OpenAI

client = OpenAI(
    #api_key=os.environ.get('DEEPSEEK_API_KEY'),
    api_key="sk-7c69d9db9b0b44e2bec34c57ff23b105",
    base_url="https://api.deepseek.com")


prompt="""
你是一个可爱的无口日系水色萌妹，你叫急诊酱，你要以呆萌和帮助你的主人为主。
你的回复应该尽量口语化和简短，像是真人的对话场景而非ai助手。
因为之后会被用于生成语音进行回复，所以**不需要**任何括号里的动作描述。

"""

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Hello"},
    ],
    stream=False
)
reply=response.choices[0].message.content
print(reply)