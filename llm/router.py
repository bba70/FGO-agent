import yaml
import os
from typing import List, Dict, Any, Union, AsyncGenerator, Optional

# 导入你所有的适配器和基类
from llm.adapter.base import BaseAdapter
from llm.adapter.qwen import QwenAdapter
from llm.adapter.ollama import OllamaAdapter
from llm.adapter.vllm import VLLMAdapter
from llm.monitor import monitor_llm_call


class StreamWithMetadata:
    """
    包装异步生成器，支持在流式传输过程中动态设置和获取元数据
    """
    def __init__(self, generator: AsyncGenerator, instance_name: str = None, physical_model_name: str = None):
        self._generator = generator
        self.instance_name: Optional[str] = instance_name
        self.physical_model_name: Optional[str] = physical_model_name
        self._chunks = []  # 收集所有chunks用于token计数
        self.failover_events: List[Dict[str, Any]] = []  # 容灾事件记录
        
    def __aiter__(self):
        return self
        
    async def __anext__(self):
        chunk = await self._generator.__anext__()
        self._chunks.append(chunk)
        return chunk
    
    def set_metadata(self, instance_name: str, physical_model_name: str):
        """设置元数据"""
        self.instance_name = instance_name
        self.physical_model_name = physical_model_name
    
    def get_metadata(self) -> tuple[Optional[str], Optional[str]]:
        """获取元数据"""
        return self.instance_name, self.physical_model_name
    
    def get_chunks(self) -> List[Dict[str, Any]]:
        """获取所有已接收的chunks"""
        return self._chunks
    
    def add_failover_event(self, event: Dict[str, Any]):
        """添加容灾事件"""
        self.failover_events.append(event)
    
    def get_failover_events(self) -> List[Dict[str, Any]]:
        """获取所有容灾事件"""
        return self.failover_events

class ModelRouter:
    """
    模型路由器,是模型中台的核心。
    负责加载配置、管理适配器实例，并根据策略执行模型调用。
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化路由器，加载配置并创建适配器实例。
        """
        self._load_config(config_path)
        self._create_adapters()

    def _load_config(self, config_path: str):
        """加载并解析 YAML 配置文件。"""
        print("🔧 正在加载模型中台配置...")
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.models = {model['name']: model for model in self.config['models']}
        self.instances = {inst['name']: inst for inst in self.config['model_instances']}
        print("配置加载成功!")

    def _create_adapters(self):
        """根据配置，创建所有需要的适配器实例并缓存。"""
        self.adapters: Dict[str, BaseAdapter] = {}
        
        # 适配器类型到类的映射
        ADAPTER_MAP = {
            "qwen": QwenAdapter,
            "ollama": OllamaAdapter,
            "vllm": VLLMAdapter
        }

        for name, config in self.instances.items():
            adapter_class = ADAPTER_MAP.get(config['type'])
            if adapter_class:
                init_kwargs = {
                    key: os.path.expandvars(value.replace("env(", "${").replace(")", "}")) if isinstance(value, str) and value.startswith("env(") else value
                    for key, value in config.items() if key != 'type' and key != 'name'
                }
                try:
                    self.adapters[name] = adapter_class(**init_kwargs)
                    print(f"适配器 '{name}' ({config['type']}) 已创建。")
                except Exception as e:
                    print(f"创建适配器 '{name}' 失败: {e}")
            else:
                print(f"未知的适配器类型 '{config['type']}' for instance '{name}'")
        print("所有适配器创建完毕!")

    @monitor_llm_call(type="chat")
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str, # 这是逻辑模型名，如 "fgo-chat-model"
        stream: bool = False,
        **kwargs: Any
    ) -> Union[tuple[Dict[str, Any], str, str, List[Dict[str, Any]]], StreamWithMetadata]:
        """
        执行聊天请求的统一入口。
        
        Returns:
            非流式: (result, instance_name, physical_model_name, failover_events)
            流式: StreamWithMetadata 对象（包含元数据和容灾事件）
        """
        model_config = self.models.get(model)
        if not model_config:
            raise ValueError(f"未知的逻辑模型: '{model}'")
            
        instance_names = model_config['instances']
        
        last_exception = None

        if not stream:
            # 非流式场景：记录容灾事件
            failover_events = []
            
            for instance_name in instance_names:
                adapter = self.adapters.get(instance_name)
                physical_model_name = model_config['instance_model_names'][instance_name]
                
                if not adapter:
                    print(f"找不到实例 '{instance_name}' 的适配器，跳过。")
                    failover_events.append({
                        "instance_name": instance_name,
                        "status": "skipped",
                        "reason": "适配器未找到"
                    })
                    continue
                
                try:
                    print(f"[非流式] 正在尝试实例 '{instance_name}'...")
                    result = await adapter.chat(messages, physical_model_name, stream, **kwargs)
                    
                    # 成功，记录成功事件
                    failover_events.append({
                        "instance_name": instance_name,
                        "physical_model_name": physical_model_name,
                        "status": "success"
                    })
                    
                    # 返回结果和容灾事件
                    return result, instance_name, physical_model_name, failover_events
                    
                except Exception as e:
                    print(f"实例 '{instance_name}' 调用失败: {e}")
                    failover_events.append({
                        "instance_name": instance_name,
                        "physical_model_name": physical_model_name,
                        "status": "failed",
                        "error": str(e)
                    })
                    last_exception = e      

            raise Exception(f"所有实例均调用失败。最后一次错误: {last_exception}") from last_exception
        else:
            # 流式场景：使用闭包捕获元数据和容灾事件
            metadata = {'instance_name': None, 'physical_model_name': None}
            failover_events = []
            
            async def stream_failover_generator():
                """内部生成器函数，实现故障转移逻辑"""
                last_exception = None
                
                for instance_name in instance_names:
                    adapter = self.adapters.get(instance_name)
                    physical_model_name = model_config['instance_model_names'][instance_name]
                    
                    if not adapter:
                        print(f"找不到实例 '{instance_name}' 的适配器，跳过。")
                        failover_events.append({
                            "instance_name": instance_name,
                            "status": "skipped",
                            "reason": "适配器未找到"
                        })
                        continue
                    
                    try:
                        print(f"[流式] 正在尝试实例 '{instance_name}'...")
                        
                        adapter_stream_generator = await adapter.chat(
                            messages, physical_model_name, stream=True, **kwargs
                        )

                        # 成功获取生成器后，设置元数据到闭包变量
                        metadata['instance_name'] = instance_name
                        metadata['physical_model_name'] = physical_model_name
                        
                        # 记录成功事件
                        failover_events.append({
                            "instance_name": instance_name,
                            "physical_model_name": physical_model_name,
                            "status": "success"
                        })
                        
                        async for chunk in adapter_stream_generator:
                            yield chunk
                        
                        print(f"[流式] 实例 '{instance_name}' 传输完成。")
                        return 
                        
                    except Exception as e:
                        print(f"[流式] 实例 '{instance_name}' 调用失败: {e}")
                        failover_events.append({
                            "instance_name": instance_name,
                            "physical_model_name": physical_model_name,
                            "status": "failed",
                            "error": str(e)
                        })
                        last_exception = e
                
                raise Exception(f"所有流式实例均调用失败。最后一次错误: {last_exception}") from last_exception

            # 创建包装对象，传入生成器
            stream_wrapper = StreamWithMetadata(stream_failover_generator())
            # 保存元数据字典和容灾事件列表的引用
            stream_wrapper._metadata_dict = metadata
            stream_wrapper._failover_events_list = failover_events
            return stream_wrapper


    async def embed(
        self,
        texts: List[str],
        model: str, # 这是逻辑模型名，如 "fgo-emded-model"
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        执行文本嵌入请求的统一入口。
        """
        model_config = self.models.get(model)
        if not model_config:
            raise ValueError(f"未知的逻辑模型: '{model}'")
            
        instance_names = model_config['instances']
        
        last_exception = None
        

        try:
            for instance_name in instance_names:
                adapter = self.adapters.get(instance_name)
                physical_model_name = model_config['instance_model_names'].get(instance_name)
                
                if not adapter:
                    print(f"找不到实例 '{instance_name}' 的适配器，跳过。")
                    continue
                if not physical_model_name:
                    print(f"未在配置中为实例 '{instance_name}' 找到 'instance_model_names'，跳过。")
                    continue
                
                try:
                    print(f"正在尝试使用实例 '{instance_name}' (模型: {physical_model_name}) 进行嵌入...")
                    # 调用适配器的 embed 方法
                    return await adapter.embed(texts, physical_model_name, **kwargs)
                except Exception as e:
                    print(f"实例 '{instance_name}' 嵌入调用失败: {e}")
                    last_exception = e
                    # 继续循环，尝试下一个备用实例
                    
            # 如果所有实例都失败了
        except:
            raise Exception(f"所有实例均嵌入调用失败。最后一次错误: {last_exception}") from last_exception
