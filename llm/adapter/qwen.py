from openai import AsyncOpenAI
from typing import AsyncGenerator, List, Dict, Any, Union

from llm.adapter.base import BaseAdapter

class QwenAdapter(BaseAdapter):
    
    def __init__(self, api_key: str, base_url: str, **kwargs):

        super().__init__(**kwargs)

        # print(api_key, base_url)
        # api_key = api_key + '666'
        
        # 在适配器内部创建并管理自己的 aiohttp 客户端
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs: Any
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        调用 Qwen 的聊天模型。
        """
        
        if stream:
            return self._chat_stream(messages, model, **kwargs)
        
        # --- 非流式实现 ---
        try:
            completion = await self.async_client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return completion.model_dump()
        except Exception as e:
            # 你可以在这里处理 DashScope 特有的 API 错误
            print(f"Qwen API Error: {e}")
            raise  # 重新抛出异常，让核心层去处理

    async def _chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理 Qwen 的流式聊天响应。
        """
        try:
            stream = await self.async_client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **kwargs
            )
            async for chunk in stream:
                yield chunk.model_dump()
        except Exception as e:
            print(f"Qwen API Stream Error: {e}")
            raise

    async def embed(
        self,
        texts: List[str],
        model: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        调用 Qwen 的嵌入模型。
        """
        try:
            embedding = await self.async_client.embeddings.create(
                model=model,
                input=texts,
                **kwargs
            )
            return embedding.model_dump()
        except Exception as e:
            print(f"Qwen Embedding API Error: {e}")
            raise