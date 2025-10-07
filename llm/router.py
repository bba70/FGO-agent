import yaml
import os
from typing import List, Dict, Any, Union, AsyncGenerator

# 导入你所有的适配器和基类
from adapter.base import BaseAdapter
from adapter.qwen import QwenAdapter
from adapter.ollama import OllamaAdapter
from adapter.vllm import VLLMAdapter

class ModelRouter:
    """
    模型路由器，是模型中台的核心。
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
        print("✅ 配置加载成功!")

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

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str, # 这是逻辑模型名，如 "fgo-chat-model"
        stream: bool = False,
        **kwargs: Any
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        执行聊天请求的统一入口。
        """
        model_config = self.models.get(model)
        if not model_config:
            raise ValueError(f"未知的逻辑模型: '{model}'")
            
        instance_names = model_config['instances']
        
        last_exception = None


        if not stream:
            for instance_name in instance_names:
                adapter = self.adapters.get(instance_name)
                physical_model_name = model_config['instance_model_names'][instance_name]
                
                if not adapter:
                    print(f"找不到实例 '{instance_name}' 的适配器，跳过。")
                    continue
                
                try:
                    return await adapter.chat(messages, physical_model_name, stream, **kwargs)
                except Exception as e:
                    print(f"实例 '{instance_name}' 调用失败: {e}")
                    last_exception = e      

            raise Exception(f"所有实例均调用失败。最后一次错误: {last_exception}") from last_exception
        else:
            async def stream_failover_generator():  # 使用内函数，因为一个函数不能既是普通函数又是生成函数
                last_exception = None
                
                for instance_name in instance_names:
                    try:
                        adapter = self.adapters.get(instance_name)
                        physical_model_name = model_config['instance_model_names'][instance_name]

                        print(f"[流式] 正在尝试实例 '{instance_name}'...")
                        
                        adapter_stream_generator = await adapter.chat(
                            messages, physical_model_name, stream=True, **kwargs
                        )

                        async for chunk in adapter_stream_generator:
                            # 每成功获取一个 chunk，就立即将其转发给上游
                            yield chunk
                        
                        print(f"[流式] 实例 '{instance_name}' 传输完成。")
                        return 
                        
                    except Exception as e:
                        print(f"[流式] 实例 '{instance_name}' 调用失败: {e}")
                        last_exception = e
                
                raise Exception(f"所有流式实例均调用失败。最后一次错误: {last_exception}") from last_exception

            return stream_failover_generator()
        


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