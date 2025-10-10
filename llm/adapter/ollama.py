# adapters/ollama_adapter.py

import httpx
import json
from typing import AsyncGenerator, List, Dict, Any, Union

from llm.adapter.base import BaseAdapter

class OllamaAdapter(BaseAdapter):
    """
    与本地运行的 Ollama 服务进行交互的【独立】适配器。
    它调用 Ollama 的原生 API。
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", **kwargs):
        """
        初始化 Ollama 适配器。
        
        Args:
            base_url (str): Ollama 服务的 API 端点 URL。
        """
        super().__init__(**kwargs)
        self.base_url = base_url
        
        # 创建一个可复用的异步 HTTP 客户端
        self.async_client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs: Any
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        调用 Ollama 的 /api/chat 端点。
        """
        # 准备请求体
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": kwargs
        }
        
        if stream:
            return self._chat_stream(payload)
        
        # --- 非流式实现 ---
        try:
            response = await self.async_client.post("/api/chat", json=payload)
            response.raise_for_status() 
            
            # Ollama 的非流式响应是一个单行的 JSON 对象
            raw_response = response.json()
            return self._format_chat_response(raw_response, model)
            
        except httpx.HTTPStatusError as e:
            error_details = e.response.text
            raise Exception(f"Ollama API Error: {e.response.status_code} - {error_details}")
        except Exception as e:
            raise Exception(f"Ollama connection failed: {e}")

    async def _chat_stream(
        self,
        payload: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理 Ollama 的流式聊天响应。
        Ollama 的流式响应是每行一个 JSON 对象。
        """
        try:
            async with self.async_client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                # 逐行读取流式响应
                async for line in response.aiter_lines():
                    if line:
                        chunk = json.loads(line)
                        yield self._format_chat_stream_chunk(chunk, payload['model'])
                        # 检查流是否结束
                        if chunk.get("done"):
                            break
        except httpx.HTTPStatusError as e:
            error_details = await e.response.aread()
            raise Exception(f"Ollama Stream API Error: {e.response.status_code} - {error_details}")
        except Exception as e:
            raise Exception(f"Ollama stream connection failed: {e}")
            
    async def embed(
        self,
        texts: List[str],
        model: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        调用 Ollama 的 /api/embeddings 端点。
        Ollama 一次只处理一个文本，所以我们需要循环。
        """
        embeddings = []
        total_prompt_tokens = 0
        
        for text in texts:
            payload = {
                "model": model,
                "prompt": text,
                **kwargs
            }
            try:
                response = await self.async_client.post("/api/embeddings", json=payload)
                response.raise_for_status()
                
                total_prompt_tokens += len(text) // 4
                embeddings.append(response.json()['embedding'])
                
            except Exception as e:
                raise Exception(f"Ollama Embedding API Error for text '{text[:20]}...': {e}")
        
        return self._format_embedding_response(model, embeddings, total_prompt_tokens)

    # --- Ollama 特有的格式化方法 ---
    
    def _format_chat_response(self, raw_response: Dict, model: str) -> Dict[str, Any]:
        """将 Ollama 的完整响应格式化为标准输出。"""
        return {
            "id": f"ollama-resp-{raw_response.get('created_at')}",
            "model": raw_response.get('model', model),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": raw_response.get('message', {}).get('content')
                    },
                    "finish_reason": "stop" if raw_response.get("done") else None
                }
            ],
            "usage": {
                "prompt_tokens": raw_response.get("prompt_eval_count"),
                "completion_tokens": raw_response.get("eval_count"),
                "total_tokens": raw_response.get("prompt_eval_count", 0) + raw_response.get("eval_count", 0)
            }
        }
        
    def _format_chat_stream_chunk(self, chunk: Dict, model: str) -> Dict[str, Any]:
        """将 Ollama 的流式块格式化为标准输出。"""
        formatted_chunk = {
            "id": f"ollama-chunk-{chunk.get('created_at')}",
            "model": chunk.get('model', model),
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": chunk.get('message', {}).get('content', '')
                    },
                    "finish_reason": "stop" if chunk.get("done") else None
                }
            ]
        }
        # Ollama 在最后一个流块中提供 usage
        if chunk.get("done"):
            formatted_chunk["usage"] = {
                "prompt_tokens": chunk.get("prompt_eval_count"),
                "completion_tokens": chunk.get("eval_count"),
                "total_tokens": chunk.get("prompt_eval_count", 0) + chunk.get("eval_count", 0)
            }
        return formatted_chunk

    def _format_embedding_response(self, model: str, embeddings: List[list], total_tokens: int) -> Dict[str, Any]:
        """格式化 Ollama 的嵌入响应。"""
        return {
            "model": model,
            "data": [
                {
                    "index": i,
                    "embedding": emb
                } for i, emb in enumerate(embeddings)
            ],
            "usage": {
                "prompt_tokens": total_tokens,
                "total_tokens": total_tokens
            }
        }