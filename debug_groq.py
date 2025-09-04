import asyncio, os
from dotenv import load_dotenv
from groq import AsyncGroq, APIStatusError, RateLimitError

async def main():
    load_dotenv()  # .env 파일 로드
    key = os.getenv("GROQ_API_KEY")
    print("GROQ_API_KEY set? ", bool(key))
    client = AsyncGroq(api_key=key, timeout=20)
    try:
        ms = await client.models.list()
        print("Models:", [m.id for m in ms.data][:5])
        
        # 원래 모델로 테스트 호출
        test_model = "llama-3.3-70b-versatile"
        print(f"\n테스트: {test_model}")
        
        response = await client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "테스트"}],
            max_tokens=50
        )
        print("SUCCESS: Groq call worked!")
        print("Response:", response.choices[0].message.content[:100])
        
    except (RateLimitError, APIStatusError) as e:
        print("❌ Groq API 에러:", e)

if __name__ == "__main__":
    asyncio.run(main())