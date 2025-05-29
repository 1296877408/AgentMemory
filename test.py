from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "你是一个幽默的助手"},
        {"role": "user", "content": "帮我写一首诗"}
    ]
)

print(response.choices[0].message.content)