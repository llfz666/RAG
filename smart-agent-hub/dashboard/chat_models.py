"""Chat Dashboard Data Models.

This module defines the data models used in the chat dashboard,
including message types, chat messages, and session state.

Requirements:
    pip install pydantic
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """聊天消息类型枚举."""
    
    USER = "user"                    # 用户消息
    ASSISTANT = "assistant"          # 助手消息
    THOUGHT = "thought"              # 思考过程
    ACTION = "action"                # 工具调用
    OBSERVATION = "observation"      # 工具结果
    FINAL_ANSWER = "final_answer"    # 最终答案
    ERROR = "error"                  # 错误消息
    SYSTEM = "system"                # 系统消息


class ChatMessage(BaseModel):
    """聊天消息模型.
    
    Attributes:
        id: 消息唯一标识符
        role: 消息类型
        content: 消息内容
        timestamp: 消息创建时间
        metadata: 附加元数据
    
    Example:
        >>> msg = ChatMessage(
        ...     role=MessageType.USER,
        ...     content="帮我查找 RAG 资料"
        ... )
        >>> print(msg.icon)
        👤
    """
    
    id: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"),
        description="消息 ID"
    )
    role: MessageType = Field(..., description="消息类型")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="时间戳"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="元数据"
    )
    
    @property
    def icon(self) -> str:
        """获取消息类型对应的图标."""
        icons = {
            MessageType.USER: "👤",
            MessageType.ASSISTANT: "🤖",
            MessageType.THOUGHT: "🤔",
            MessageType.ACTION: "🔧",
            MessageType.OBSERVATION: "📦",
            MessageType.FINAL_ANSWER: "✅",
            MessageType.ERROR: "❌",
            MessageType.SYSTEM: "⚙️",
        }
        return icons.get(self.role, "💬")
    
    @property
    def display_title(self) -> str:
        """获取消息类型的显示标题."""
        titles = {
            MessageType.USER: "用户",
            MessageType.ASSISTANT: "助手",
            MessageType.THOUGHT: "思考",
            MessageType.ACTION: "调用工具",
            MessageType.OBSERVATION: "观察结果",
            MessageType.FINAL_ANSWER: "最终答案",
            MessageType.ERROR: "错误",
            MessageType.SYSTEM: "系统",
        }
        return titles.get(self.role, "消息")
    
    @property
    def background_color(self) -> str:
        """获取消息类型的背景颜色（用于 UI 渲染）."""
        colors = {
            MessageType.USER: "#f0f2f6",
            MessageType.ASSISTANT: "#e8f5e9",
            MessageType.THOUGHT: "#fff3e0",
            MessageType.ACTION: "#e3f2fd",
            MessageType.OBSERVATION: "#f3e5f5",
            MessageType.FINAL_ANSWER: "#c8e6c9",
            MessageType.ERROR: "#ffebee",
            MessageType.SYSTEM: "#eceff1",
        }
        return colors.get(self.role, "#ffffff")
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于 JSON 序列化）."""
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatMessage:
        """从字典创建消息实例."""
        return cls(
            id=data.get("id", datetime.now().strftime("%Y%m%d%H%M%S%f")),
            role=MessageType(data.get("role", "user")),
            content=data.get("content", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            metadata=data.get("metadata", {}),
        )


class ChatSession(BaseModel):
    """聊天会话模型.
    
    Attributes:
        session_id: 会话唯一标识符
        user_id: 用户标识符（可选，用于多用户场景）
        messages: 会话中的消息列表
        created_at: 会话创建时间
        updated_at: 会话更新时间
        metadata: 会话元数据
    """
    
    session_id: str = Field(..., description="会话 ID")
    user_id: Optional[str] = Field(None, description="用户 ID")
    messages: list[ChatMessage] = Field(
        default_factory=list,
        description="消息列表"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="更新时间"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="元数据"
    )
    
    def add_message(self, message: ChatMessage) -> None:
        """添加消息到会话."""
        self.messages.append(message)
        self.updated_at = datetime.now()
    
    def get_recent_messages(self, limit: int = 10) -> list[ChatMessage]:
        """获取最近的消息."""
        return self.messages[-limit:]
    
    def clear_messages(self) -> None:
        """清除所有消息."""
        self.messages = []
        self.updated_at = datetime.now()
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatSession:
        """从字典创建会话实例."""
        return cls(
            session_id=data.get("session_id", datetime.now().strftime("%Y%m%d%H%M%S%f")),
            user_id=data.get("user_id"),
            messages=[
                ChatMessage.from_dict(msg) 
                for msg in data.get("messages", [])
            ],
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
            metadata=data.get("metadata", {}),
        )


class ConnectionStatus(str, Enum):
    """连接状态枚举."""
    
    DISCONNECTED = "disconnected"      # 未连接
    CONNECTING = "connecting"          # 连接中
    CONNECTED = "connected"            # 已连接
    ERROR = "error"                    # 错误状态
    RECONNECTING = "reconnecting"      # 重连中


class SessionState(BaseModel):
    """会话状态模型（用于 Streamlit session_state）."""
    
    connection_status: ConnectionStatus = Field(
        ConnectionStatus.DISCONNECTED,
        description="连接状态"
    )
    current_session: Optional[ChatSession] = Field(
        None,
        description="当前会话"
    )
    is_processing: bool = Field(
        False,
        description="是否正在处理请求"
    )
    error_message: Optional[str] = Field(
        None,
        description="错误消息"
    )
    
    def set_connected(self) -> None:
        """设置连接状态为已连接."""
        self.connection_status = ConnectionStatus.CONNECTED
        self.error_message = None
    
    def set_connecting(self) -> None:
        """设置连接状态为连接中."""
        self.connection_status = ConnectionStatus.CONNECTING
        self.error_message = None
    
    def set_error(self, error: str) -> None:
        """设置错误状态."""
        self.connection_status = ConnectionStatus.ERROR
        self.error_message = error
    
    def set_processing(self, is_processing: bool = True) -> None:
        """设置处理状态."""
        self.is_processing = is_processing