from llm.router import ModelRouter
import asyncio


async def test_stream():
    """测试流式输出"""
    print("=" * 50)
    print("测试流式输出")
    print("=" * 50)
    
    router = ModelRouter(config_path="llm/config.yaml")
    stream_result = await router.chat(
        model="fgo-chat-model",
        messages=[{"role": "user", "content": "你好，请用一句话介绍一下自己"}],
        stream=True,
    )
    
    # stream_result 现在是 StreamWithMetadata 对象
    print("流式输出：", end="")
    async for chunk in stream_result:
        content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
        if content:
            print(content, end="", flush=True)
    
    print("\n")
    # 流式传输完成后，可以获取元数据（通过闭包变量）
    if hasattr(stream_result, '_metadata_dict'):
        instance_name = stream_result._metadata_dict.get('instance_name')
        physical_model_name = stream_result._metadata_dict.get('physical_model_name')
        print(f"使用的实例: {instance_name}")
        print(f"物理模型: {physical_model_name}")


async def test_non_stream():
    """测试非流式输出"""
    print("\n" + "=" * 50)
    print("测试非流式输出")
    print("=" * 50)
    
    router = ModelRouter(config_path="llm/config.yaml")
    result, instance_name, physical_model_name, failover_events = await router.chat(
        model="fgo-chat-model",
        messages=[{"role": "user", "content": "你好"}],
        stream=False,
    )
    
    # 打印结果
    content = result.get("choices", [{}])[0].get("message", {}).get("content")
    print(f"回复: {content}")
    print(f"使用的实例: {instance_name}")
    print(f"物理模型: {physical_model_name}")
    print(f"Token 使用: {result.get('usage', {})}")
    print(f"容灾事件: {failover_events}")


async def main():
    """主测试函数"""
    # 测试流式
    await test_stream()
    
    # 测试非流式
    await test_non_stream()


if __name__ == "__main__":
    asyncio.run(main())
