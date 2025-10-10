from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum

@dataclass
class User:
    '''用户实体'''
    user_id: str
    username: Optional[str] = None
    create_at: Optional[datetime] = None
    update_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        return cls(
            user_id=data.get('user_id'),
            username=data.get('username'),
            create_at=datetime.fromisoformat(data.get('create_at')) if data.get('create_at') else None,
            update_at=datetime.fromisoformat(data.get('update_at')) if data.get('update_at') else None    
        )

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "create_at": self.create_at.isoformat() if self.create_at else None,
            "update_at": self.update_at.isoformat() if self.update_at else None,
        }
    
@dataclass
class Session:
    """会话实体"""
    session_id: str
    user_id: str
    session_name: Optional[str] = None
    last_active: Optional[datetime] = None
    is_active: Optional[int] = 0
    message_count: int = 0
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        """从字典创建Session对象"""
        return cls(
            session_id=data.get('session_id'),
            user_id=data.get('user_id'),
            session_name=data.get('session_name'),
            last_active=data.get('last_active'), 
            is_active=int(data.get('is_active', 0)),
            message_count=int(data.get('message_count', 0))
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'session_name': self.session_name,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'is_active': self.is_active,
            'message_count': self.message_count
        }
    
@dataclass
class Conversation:
    """对话实体"""
    conversation_id: Optional[int] = None
    session_id: Optional[str] = None
    query: Optional[str] = None
    response: Optional[str] = None
    question_type: Optional[str] = None
    created_time: Optional[datetime] = None
    turn_number: int = 0
    token_count: int = 0
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Conversation':
        """从字典创建Conversation对象"""
        return cls(
            conversation_id=data.get('conversation_id'),
            session_id=data.get('session_id'),
            user_question=data.get('user_question'),
            ai_response=data.get('ai_response'),
            question_type=(data.get('question_type', 'general')),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            turn_number=int(data.get('turn_number', 0)),
            token_count=int(data.get('token_count', 0))
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'conversation_id': self.conversation_id,
            'session_id': self.session_id,
            'query': self.query,
            'response': self.response,
            'question_type': self.question_type.value if self.question_type else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'turn_number': self.turn_number,
            'token_count': self.token_count
        }
    
@dataclass
class SessionSummary:
    """会话摘要实体"""
    session_id: str
    summary_text: str
    turn_number: int
    last_summary_time: Optional[datetime] = None
    token_count: int = 0
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SessionSummary':
        """从字典创建SessionSummary对象"""
        return cls(
            session_id=data.get('session_id'),
            summary_text=data.get('summary_text'),
            turned_number=int(data.get('turned_number', 0)),
            last_summary_time=datetime.fromisoformat(data['last_summary_time']) if data.get('last_summary_time') else None,
            token_count=int(data.get('token_count', 0))
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'summary_text': self.summary_text,
            'turned_number': self.turn_number,
            'last_summary_time': self.last_summary_time.isoformat() if self.last_summary_time else None,
            'token_count': self.token_count
        }
    
@dataclass
class Models:
    id: str                                    
    instance_name: str 
    type: str      
    physical_model_name: str   
    
    base_url: Optional[str] = None  
    create_at: Optional[datetime] = None      
    

    @classmethod
    def from_dict(cls, data: dict) -> 'Models':
        return cls(
            id=data.get('id'),
            instance_name=data.get('instance_name'),
            type=data.get('type'),
            physical_model_name=data.get('physical_model_name'),
            base_url=data.get('base_url'),
            create_at=data.get('create_at') 
        )
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'instance_name': self.instance_name,
            'type': self.type,
            'physical_model_name': self.physical_model_name,
            'base_url': self.base_url,
            'create_at': self.create_at.isoformat() if self.create_at else None
        }
    
@dataclass
class Logs:
    id: str
    logical_model: str      
    type: str 
    status: str    
    prompt_token: int = 0                       
    completion_token: int = 0
    model_id: Optional[str] = None                     
    is_stream: bool = False                     
    timestamp_start: Optional[datetime] = None  
    timestamp_end: Optional[datetime] = None                       
    error_message: Optional[str] = None         
    failover_events: Optional[str] = None        
    

    @classmethod
    def from_dict(cls, data: dict) -> 'Logs':
        
        return cls(
            id=data.get('id'),
            model_id=data.get('model_id'),
            logical_model=data.get('logical_model'),
            type=data.get('type'),
            status=data.get('status'),
            timestamp_start=data.get('timestamp_start'),
            timestamp_end=data.get('timestamp_end'),
            is_stream=bool(data.get('is_stream', False)),
            prompt_token=int(data.get('prompt_token', 0)),
            completion_token=int(data.get('completion_token', 0)),
            error_message=data.get('error_message'),
            failover_events=data.get('failover_events'),
        )
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'model_id': self.model_id,
            'logical_model': self.logical_model,
            'type': self.type,
            'status': self.status,
            'is_stream': 1 if self.is_stream else 0, 
            'timestamp_start': self.timestamp_start.isoformat() if self.timestamp_start else None,
            'timestamp_end': self.timestamp_end.isoformat() if self.timestamp_end else None,
            
            'prompt_token': self.prompt_token,
            'completion_token': self.completion_token,
            'error_message': self.error_message,
            'failover_events': self.failover_events,
        }