from openai import AsyncOpenAI
from typing import AsyncGenerator, List, Dict, Any, Union

from .base import BaseAdapter

class VLLMAdapter(BaseAdapter):
    """
    与 vLLM 的 OpenAI 兼容 API 端点进行交互的【独立】适配器。
    """
    
    def __init__(self, base_url: str = "http://localhost:8000/v1", api_key: str = "EMPTY", **kwargs):
        """
        初始化 vLLM 适配器。
        
        Args:
            base_url (str): vLLM OpenAI 兼容服务的 API 端点 URL。
            api_key (str): vLLM 服务通常不需要 API Key，可以留空或任意字符串。
        """
        super().__init__(**kwargs)
        self.base_url = base_url
        self.api_key = api_key
        
        self.async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str, 
        stream: bool = False,
        **kwargs: Any
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        调用 vLLM 的聊天模型。
        """
        
        if stream:
            return self._chat_stream(messages, model, **kwargs)
        
        try:
            completion = await self.async_client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return completion.model_dump()
        except Exception as e:
            raise Exception(f"vLLM API Error: {e}")

    async def _chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
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
            raise Exception(f"vLLM API Stream Error: {e}")

    async def embed(
        self,
        texts: List[str],
        model: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        调用 vLLM 的嵌入模型（如果 vLLM 加载了嵌入模型并提供了该端点）。
        """
        try:
            embedding = await self.async_client.embeddings.create(
                model=model,
                input=texts,
                **kwargs
            )
            return embedding.model_dump()
        except Exception as e:
            raise Exception(f"vLLM Embedding API Error: {e}")