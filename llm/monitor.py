# core/monitoring.py

import time
import uuid
import logging
import json
import traceback
from datetime import datetime
from functools import wraps
from typing import Callable, Any, Coroutine, AsyncGenerator, Dict, List

# 导入 DAL 和实体类
# 确保你的项目结构中这些路径是正确的
from database.db.repositories import LogDAL
from database.db.models import Models, Logs
# from llm.router import ModelRouter

# --- 初始化 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(call_id)s] - %(message)s')
logger = logging.getLogger("ModelCallMonitor")

# 创建一个全局的 DAL 实例，供所有装饰器调用使用
log_dal = LogDAL()

# --- 装饰器工厂 ---

def monitor_llm_call(method_name: str):
    """
    一个装饰器工厂，用于拦截、监控并记录 ModelRouter 的方法调用。
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        
        @wraps(func)
        async def wrapper(self: 'ModelRouter', *args, **kwargs):
            # --- 1. 前置拦截：调用开始 ---
            
            call_id = str(uuid.uuid4())
            start_time = time.monotonic()
            
            log_adapter = logging.LoggerAdapter(logger, {'call_id': call_id})
            
            logical_model = kwargs.get('model') or (args[1] if len(args) > 1 else 'unknown')
            is_stream = kwargs.get('stream', False)

            # 创建并立即插入初始日志记录
            initial_log = Logs(
                id=call_id,
                timestamp_start=datetime.utcnow(),
                type=method_name,
                logical_model=logical_model,
                status="in_progress",
                is_stream=is_stream,
            )
            # 初始时 model_id 可以为 None (如果数据库允许) 或一个虚拟ID
            # 我们假设数据库允许为 NULL
            await log_dal.save_log(initial_log)
            log_adapter.info(f"开始执行 '{method_name}' for model '{logical_model}'")
            
            # 准备“信使”对象和 failover 日志列表
            failover_events: List[Dict[str, Any]] = []
            call_context = {
                "successful_instance_name": None,
                "physical_model_name": None,
                "model_id": None,
                "final_usage": None
            }
            
            kwargs['__failover_log'] = failover_events
            kwargs['__call_context'] = call_context
            
            try:
                # --- 2. 执行原始方法 (Router 的 chat 或 embed) ---
                result = await func(self, *args, **kwargs)
                
                # ---- 3. 拦截响应，后置处理 ----
                if not is_stream:
                    # **非流式**: result 是一个 dict
                    instance_name = call_context["successful_instance_name"]
                    physical_name = call_context["physical_model_name"]
                    
                    instance_config = self.instances.get(instance_name)
                    model_obj = Models(
                        instance_name=instance_name, type=instance_config.get('type'),
                        physical_model_name=physical_name, base_url=instance_config.get('base_url')
                    )
                    model_id = await log_dal.get_or_create_model(model_obj)
                    
                    usage = result.get('usage', {})
                    final_log_obj = Logs(
                        id=call_id, model_id=model_id, status="success",
                        prompt_token=usage.get('prompt_tokens', 0),
                        completion_token=usage.get('completion_tokens', 0),
                        failover_events=json.dumps(failover_events, ensure_ascii=False) if failover_events else None,
                        timestamp_end=datetime.utcnow(),
                    )
                    await log_dal.save_log(final_log_obj)
                    latency = (datetime.utcnow() - initial_log.timestamp_start).total_seconds() * 1000
                    log_adapter.info(f"'{method_name}' 非流式成功。耗时: {latency:.2f}ms, 实例: {instance_name}")
                    
                    return result
                
                else:
                    # **流式**: result 是一个 async generator, 我们需要包装它
                    async def streaming_wrapper():
                        try:
                            async for chunk in result:
                                yield chunk
                                if chunk.get('usage'):
                                    call_context['final_usage'] = chunk['usage']
                        
                        except Exception as stream_exc:
                            # 如果流消费失败
                            instance_name = call_context.get("successful_instance_name")
                            model_id = call_context.get("model_id")
                            if instance_name and not model_id:
                                # 尝试在失败时也获取 model_id
                                instance_config = self.instances.get(instance_name)
                                model_obj = Models(...)
                                model_id = await log_dal.get_or_create_model(model_obj)
                            
                            failure_log = Logs(
                                id=call_id, model_id=model_id, status="failure",
                                error_message=f"流式传输错误: {stream_exc}\n{traceback.format_exc()}",
                                failover_events=json.dumps(failover_events, ensure_ascii=False) if failover_events else None,
                                timestamp_end=datetime.utcnow(),
                            )
                            await log_dal.save_log(failure_log)
                            log_adapter.error(f"'{method_name}' 流式传输失败。")
                            raise
                        
                        else:
                            # 如果流正常结束
                            instance_name = call_context["successful_instance_name"]
                            physical_name = call_context["physical_model_name"]

                            print('instance_name', instance_name)
                                
                            print('physical_name', physical_name)
                            
                            instance_config = self.instances.get(instance_name)
                            model_obj = Models(
                                instance_name=instance_name, type=instance_config.get('type'),
                                physical_model_name=physical_name, base_url=instance_config.get('base_url')
                            )
                            model_id = await log_dal.get_or_create_model(model_obj)
                            
                            usage = call_context.get('final_usage', {})
                            success_log = Logs(
                                id=call_id, model_id=model_id, status="success",
                                prompt_token=usage.get('prompt_tokens', 0),
                                completion_token=usage.get('completion_tokens', 0),
                                failover_events=json.dumps(failover_events, ensure_ascii=False) if failover_events else None,
                                timestamp_end=datetime.utcnow(),
                            )
                            await log_dal.save_log(success_log)
                            latency = (datetime.utcnow() - initial_log.timestamp_start).total_seconds() * 1000
                            log_adapter.info(f"'{method_name}' 流式成功。耗时: {latency:.2f}ms, 实例: {instance_name}")

                    return streaming_wrapper()

            except Exception as e:
                # 捕获 `func` 直接抛出的异常 (所有 failover 都失败)
                failure_log = Logs(
                    id=call_id,
                    status="failure",

                    logical_model=logical_model,
                    type=method_name,
                    is_stream=is_stream,  

                    error_message=f"所有实例均失败: {e}\n{traceback.format_exc()}",
                    failover_events=json.dumps(failover_events, ensure_ascii=False) if failover_events else None,
                    timestamp_end=datetime.utcnow(),
                )
                # 此时 model_id 为 None (或虚拟ID)，是合理的
                await log_dal.save_log(failure_log)
                log_adapter.error(f"'{method_name}' 执行失败，所有实例均不可用。")
                raise
        
        return wrapper
    return decorator