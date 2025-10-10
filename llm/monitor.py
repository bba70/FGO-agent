import time
import uuid
import logging
import json
import traceback
from datetime import datetime
from functools import wraps
from typing import Callable, Any, Coroutine, AsyncGenerator, Dict, List, TYPE_CHECKING


# 防止循环导入
if TYPE_CHECKING:
    from llm.router import ModelRouter
else:
    class ModelRouter: pass

from database.db.repositories import LogDAL
from database.db.models import Logs, Models

log_dal = LogDAL()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def monitor_llm_call(type: str):
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @wraps(func)
        async def wrapper(self: 'ModelRouter', *args, **kwargs):

            call_id = str(uuid.uuid4())
            start_time = datetime.now() 

            logical_model = kwargs.get('model')
            is_stream = kwargs.get('stream', False)
            
            try:
                result = await func(self, *args, **kwargs)

                # 导入 StreamWithMetadata（避免循环导入）
                from llm.router import StreamWithMetadata
                
                # 流式输出：返回 StreamWithMetadata 对象
                if isinstance(result, StreamWithMetadata):
                    # 创建包装生成器，在完成时记录日志
                    async def stream_with_logging():
                        """包装流式生成器，在完成后记录日志"""
                        try:
                            async for chunk in result:
                                yield chunk
                            
                            # 流式传输完成，记录日志
                            end_time = datetime.now()
                            
                            # 从闭包变量中获取元数据
                            metadata_dict = getattr(result, '_metadata_dict', None)
                            if metadata_dict:
                                instance_name = metadata_dict.get('instance_name')
                                physical_model_name = metadata_dict.get('physical_model_name')
                            else:
                                instance_name, physical_model_name = result.get_metadata()
                            
                            # 获取容灾事件
                            failover_events_list = getattr(result, '_failover_events_list', None)
                            failover_events_json = None
                            if failover_events_list:
                                failover_events_json = json.dumps(failover_events_list, ensure_ascii=False)
                            
                            if instance_name and physical_model_name:
                                instance_config = self.instances.get(instance_name)
                                model_id = str(uuid.uuid4())
                                model_obj = Models(
                                    id=model_id,
                                    instance_name=instance_name,
                                    physical_model_name=physical_model_name,
                                    type=instance_config['type'],
                                    base_url=instance_config.get('base_url', '')
                                )
                                model_id = await log_dal.get_or_create_model(model_obj)
                                
                                # 计算 token（从 chunks 中提取）
                                chunks = result.get_chunks()
                                prompt_tokens = 0
                                completion_tokens = 0
                                
                                # 尝试从最后一个 chunk 获取 usage 信息（更健壮的处理）
                                if chunks:
                                    # 从后往前找，找到第一个包含 usage 的 chunk
                                    for chunk in reversed(chunks):
                                        if chunk and isinstance(chunk, dict):
                                            usage = chunk.get('usage')
                                            if usage and isinstance(usage, dict):
                                                prompt_tokens = usage.get('prompt_tokens', 0)
                                                completion_tokens = usage.get('completion_tokens', 0)
                                                break
                                
                                log_obj = Logs(
                                    id=call_id,
                                    model_id=model_id,
                                    status="success",
                                    type=type,
                                    logical_model=logical_model,
                                    timestamp_start=start_time,
                                    timestamp_end=end_time,
                                    is_stream=True,
                                    prompt_token=prompt_tokens,
                                    completion_token=completion_tokens,
                                    failover_events=failover_events_json, 
                                )
                                await log_dal.save_log(log_obj)
                                logger.info(f"✅ 流式调用成功: {instance_name} - {physical_model_name} (tokens: {prompt_tokens}/{completion_tokens})")
                                if failover_events_list and len(failover_events_list) > 1:
                                    logger.info(f"容灾信息: 尝试了 {len(failover_events_list)} 个实例")
                            else:
                                logger.warning("流式传输完成，但未获取到元数据")
                                
                        except Exception as stream_error:
                            logger.error(f"流式传输失败: {stream_error}")
                            raise
                    
                    # 返回新的包装生成器，但保持 StreamWithMetadata 类型
                    wrapped_stream = StreamWithMetadata(stream_with_logging())
                    # 复制元数据和容灾事件引用
                    if hasattr(result, '_metadata_dict'):
                        wrapped_stream._metadata_dict = result._metadata_dict
                    if hasattr(result, '_failover_events_list'):
                        wrapped_stream._failover_events_list = result._failover_events_list
                    return wrapped_stream
                
                # 非流式输出：返回 (result, instance_name, physical_model_name, failover_events) 元组
                else:
                    response_data, instance_name, physical_model_name, failover_events = result
                    end_time = datetime.now()
                    
                    # 转换容灾事件为 JSON
                    failover_events_json = None
                    if failover_events:
                        failover_events_json = json.dumps(failover_events, ensure_ascii=False)
                    
                    instance_config = self.instances.get(instance_name)
                    model_id = str(uuid.uuid4())
                    model_obj = Models(
                        id=model_id,
                        instance_name=instance_name,
                        physical_model_name=physical_model_name,
                        type=instance_config['type'],
                        base_url=instance_config.get('base_url', '')
                    )
                    model_id = await log_dal.get_or_create_model(model_obj)
                    
                    # 安全地获取 token 信息
                    usage = response_data.get('usage', {}) if isinstance(response_data, dict) else {}
                    prompt_tokens = usage.get('prompt_tokens', 0) if isinstance(usage, dict) else 0
                    completion_tokens = usage.get('completion_tokens', 0) if isinstance(usage, dict) else 0
                    
                    log_obj = Logs(
                        id=call_id,
                        model_id=model_id,
                        status="success",
                        type=type,
                        logical_model=logical_model,
                        timestamp_start=start_time,
                        timestamp_end=end_time,
                        is_stream=False,
                        prompt_token=prompt_tokens,
                        completion_token=completion_tokens,
                        failover_events=failover_events_json,
                    )
                    await log_dal.save_log(log_obj)
                    logger.info(f"非流式调用成功: {instance_name} - {physical_model_name} (tokens: {prompt_tokens}/{completion_tokens})")
                    if failover_events and len(failover_events) > 1:
                        logger.info(f"容灾信息: 尝试了 {len(failover_events)} 个实例")
                    
                    return result  # 返回原始的 tuple

            except Exception as e:
                # 全部失败
                end_time = datetime.now()
                failure_log = Logs(
                    id=call_id,
                    model_id='failure',
                    status="failure",
                    logical_model=logical_model,
                    timestamp_start=start_time,
                    timestamp_end=end_time,
                    type=type,
                    is_stream=is_stream,
                    error_message=f"所有实例均失败: {e}\n{traceback.format_exc()}",
                )
                await log_dal.save_log(failure_log)
                logger.error(f"调用失败: {e}")
                raise

        return wrapper

    return decorator

