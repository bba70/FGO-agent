import asyncio
import sys
print(sys.path)

from router import ModelRouter


async def test_router():
    router = ModelRouter(config_path="llm/config.yaml")
    response = await router.chat(
        model="fgo-chat-model",
        messages=[{"role": "user", "content": "你好"}],
        stream=True,
    )
    # print(response)
    async for chunk in response:
        content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
        if content:
            print(content, end="", flush=True)



async def main():


    await test_router()



if __name__ == "__main__":
    asyncio.run(main())