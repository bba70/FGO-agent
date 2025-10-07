from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Union

class BaseAdapter(ABC):

    def __init__(self, **kwargs):
        """
        初始化适配器。子类应该在这里接收并处理自己的配置。
        """
        pass
        
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs: Any
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        pass

    @abstractmethod
    async def embed(
        self,
        texts: List[str],
        model: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        pass