import asyncio
import os

# 确保你的适配器文件在正确的路径下，或者你的项目已经设置了正确的 PYTHONPATH
from base import BaseAdapter
from qwen import QwenAdapter
from ollama import OllamaAdapter


# qwen
DASHSCOPE_API_KEY = "sk-e75caf43cd184188bcc1503407e0184a"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
CHAT_MODEL = "qwen-plus"
EMBED_MODEL = "text-embedding-v1"

# ollama
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_MODEL = "deepseek-r1:1.5b"
OLLAMA_EMBED_MODEL = "deepseek-r1:1.5b"




async def test_adapter(adapter: BaseAdapter, chat_model: str, embed_model: str, adapter_name: str):
    """
    一个通用的测试函数，用于验证任何继承自 BaseAdapter 的适配器。
    """
    print(f"\n{'='*20} 🧪 开始测试: {adapter_name} {'='*20}")
    
    # --- 1. 测试 Chat (非流式) ---
    print("\n--- 1. 测试 Chat (非流式) ---")
    try:
        messages = [
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': f'你好，请介绍一下你自己。'}
        ]
        
        response = await adapter.chat(messages, model=chat_model, stream=False)
        
        print("✅ 非流式 Chat 调用成功!")
        print("    - 模型 (Model):", response.get('model'))
        print("    - 回复内容 (Content):", response['choices'][0]['message']['content'][:80] + "...") # 打印前80个字符
        print("    - 用量 (Usage):", response.get('usage'))
        
        # 检查返回格式是否符合预期
        assert 'id' in response
        assert 'choices' in response and len(response['choices']) > 0
        assert 'message' in response['choices'][0]
        assert 'usage' in response

    except Exception as e:
        print(f"❌ 非流式 Chat 调用失败: {e}")

    # --- 2. 测试 Chat (流式) ---
    print("\n--- 2. 测试 Chat (流式) ---")
    try:
        messages = [
            {'role': 'user', 'content': f'请用一句话描述一下 "{adapter_name}" 的作用。'}
        ]
        
        stream_generator = await adapter.chat(messages, model=chat_model, stream=True)
        
        print("✅ 流式 Chat 调用成功，开始接收数据流:")
        full_response = ""
        async for chunk in stream_generator:
            content_delta = chunk['choices'][0]['delta'].get('content', '')
            if content_delta:
                print(content_delta, end='', flush=True)
                full_response += content_delta
        print("\n--- 流式传输结束 ---")
        assert len(full_response) > 0

    except Exception as e:
        print(f"❌ 流式 Chat 调用失败: {e}")
        
    # --- 3. 测试 Embedding ---
    # print("\n--- 3. 测试 Embedding ---")
    # try:
    #     texts_to_embed = ["你好，世界！", "这是一个测试。"]
        
    #     response = await adapter.embed(texts_to_embed, model=embed_model)

    #     print("✅ Embedding 调用成功!")
    #     print("    - 模型 (Model):", response.get('model'))
    #     print("    - 嵌入向量数量 (Embeddings count):", len(response.get('data', [])))
        
    #     if response.get('data'):
    #         first_embedding = response['data'][0]['embedding']
    #         print("    - 第一个向量维度 (First embedding dimension):", len(first_embedding))
    #         print("    - 第一个向量预览 (First embedding preview):", f"[{first_embedding[0]:.4f}, {first_embedding[1]:.4f}, ...]")
        
    #     print("    - 用量 (Usage):", response.get('usage'))
        
    #     assert 'data' in response and len(response['data']) == len(texts_to_embed)
    #     assert 'embedding' in response['data'][0]
        
    # except Exception as e:
    #     print(f"❌ Embedding 调用失败: {e}")
        
    # print(f"\n{'='*20} ✅ 测试结束: {adapter_name} {'='*20}\n")


async def main():
    """主函数，实例化并测试所有适配器"""
    
    # # --- 测试 QwenAdapter ---
    # if DASHSCOPE_API_KEY:
    #     qwen_adapter = QwenAdapter(
    #         api_key=DASHSCOPE_API_KEY,
    #         base_url=BASE_URL
    #     )
    #     await test_adapter(qwen_adapter, CHAT_MODEL, EMBED_MODEL, "QwenAdapter")
    # else:
    #     print("⚠️ 跳过 QwenAdapter 测试，因为未设置 DASHSCOPE_API_KEY 环境变量。")


    try:
        import httpx
        await httpx.AsyncClient().get(OLLAMA_BASE_URL)
        print("Ollama 服务连接正常，开始测试 OllamaAdapter...")
        ollama_adapter = OllamaAdapter(base_url=OLLAMA_BASE_URL)
        await test_adapter(ollama_adapter, OLLAMA_CHAT_MODEL, OLLAMA_EMBED_MODEL, "OllamaAdapter")
    except (httpx.ConnectError, ConnectionRefusedError):
        print(f"⚠️ 跳过 OllamaAdapter 测试，因为无法连接到 {OLLAMA_BASE_URL}。请确保 Ollama 服务正在运行。")
    except Exception as e:
        print(f"OllamaAdapter 测试期间发生意外错误: {e}")


    


if __name__ == "__main__":
    
    asyncio.run(main())