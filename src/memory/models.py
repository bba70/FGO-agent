from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum

@dataclass
class User:
    '''用户实体'''
    user_id: str
    username: Optional[str] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        return cls(
            user_id=data.get('user_id'),
            username=data.get('username'),
            create_time=datetime.fromisoformat(data.get('create_time')) if data.get('create_time') else None,
            update_time=datetime.fromisoformat(data.get('update_time')) if data.get('update_time') else None    
        )

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
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
            last_active=datetime.fromisoformat(data['last_active']) if data.get('last_active') else None,
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
            turn_number=int(data.get('turn_number', 0))
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
            'turn_number': self.turn_number
        }
    
@dataclass
class SessionSummary:
    """会话摘要实体"""
    session_id: str
    summary_text: str
    turn_number: int
    last_summary_time: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SessionSummary':
        """从字典创建SessionSummary对象"""
        return cls(
            session_id=data.get('session_id'),
            summary_text=data.get('summary_text'),
            turned_number=int(data.get('turned_number', 0)),
            last_summary_time=datetime.fromisoformat(data['last_summary_time']) if data.get('last_summary_time') else None
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'summary_text': self.summary_text,
            'turned_number': self.turn_number,
            'last_summary_time': self.last_summary_time.isoformat() if self.last_summary_time else None
        }