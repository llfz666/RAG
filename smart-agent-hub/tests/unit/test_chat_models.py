"""Unit tests for Chat Dashboard models."""

import pytest
from datetime import datetime

from dashboard.chat_models import (
    ChatMessage,
    ChatSession,
    MessageType,
    ConnectionStatus,
    SessionState,
)


class TestMessageType:
    """测试 MessageType 枚举."""
    
    def test_message_type_values(self):
        """测试消息类型值."""
        assert MessageType.USER.value == "user"
        assert MessageType.ASSISTANT.value == "assistant"
        assert MessageType.THOUGHT.value == "thought"
        assert MessageType.ACTION.value == "action"
        assert MessageType.OBSERVATION.value == "observation"
        assert MessageType.FINAL_ANSWER.value == "final_answer"
        assert MessageType.ERROR.value == "error"
        assert MessageType.SYSTEM.value == "system"


class TestChatMessage:
    """测试 ChatMessage 模型."""
    
    def test_create_user_message(self):
        """测试创建用户消息."""
        msg = ChatMessage(
            role=MessageType.USER,
            content="Hello",
        )
        
        assert msg.role == MessageType.USER
        assert msg.content == "Hello"
        assert msg.icon == "👤"
        assert msg.display_title == "用户"
    
    def test_create_assistant_message(self):
        """测试创建助手消息."""
        msg = ChatMessage(
            role=MessageType.ASSISTANT,
            content="Hi there!",
        )
        
        assert msg.role == MessageType.ASSISTANT
        assert msg.content == "Hi there!"
        assert msg.icon == "🤖"
    
    def test_create_thought_message(self):
        """测试创建思考消息."""
        msg = ChatMessage(
            role=MessageType.THOUGHT,
            content="Let me think about this...",
        )
        
        assert msg.role == MessageType.THOUGHT
        assert msg.icon == "🤔"
        assert msg.display_title == "思考"
    
    def test_create_action_message(self):
        """测试创建行动消息."""
        msg = ChatMessage(
            role=MessageType.ACTION,
            content="调用工具：query_knowledge_hub",
            metadata={"tool": "query_knowledge_hub", "input": {"query": "RAG"}},
        )
        
        assert msg.role == MessageType.ACTION
        assert msg.icon == "🔧"
        assert msg.metadata["tool"] == "query_knowledge_hub"
    
    def test_create_final_answer_message(self):
        """测试创建最终答案消息."""
        msg = ChatMessage(
            role=MessageType.FINAL_ANSWER,
            content="RAG 是 Retrieval-Augmented Generation 的缩写...",
        )
        
        assert msg.role == MessageType.FINAL_ANSWER
        assert msg.icon == "✅"
        assert msg.background_color == "#c8e6c9"
    
    def test_create_error_message(self):
        """测试创建错误消息."""
        msg = ChatMessage(
            role=MessageType.ERROR,
            content="连接失败",
        )
        
        assert msg.role == MessageType.ERROR
        assert msg.icon == "❌"
        assert msg.background_color == "#ffebee"
    
    def test_message_to_dict(self):
        """测试消息转换为字典."""
        msg = ChatMessage(
            role=MessageType.USER,
            content="Test",
        )
        
        data = msg.to_dict()
        
        assert data["role"] == "user"
        assert data["content"] == "Test"
        assert "id" in data
        assert "timestamp" in data
    
    def test_message_from_dict(self):
        """测试从字典创建消息."""
        data = {
            "id": "test_123",
            "role": "user",
            "content": "Test content",
            "timestamp": "2024-01-01T12:00:00",
            "metadata": {"key": "value"},
        }
        
        msg = ChatMessage.from_dict(data)
        
        assert msg.id == "test_123"
        assert msg.role == MessageType.USER
        assert msg.content == "Test content"
        assert msg.metadata["key"] == "value"


class TestChatSession:
    """测试 ChatSession 模型."""
    
    def test_create_session(self):
        """测试创建会话."""
        session = ChatSession(session_id="test_session")
        
        assert session.session_id == "test_session"
        assert session.messages == []
        assert session.created_at is not None
    
    def test_add_message(self):
        """测试添加消息到会话."""
        session = ChatSession(session_id="test_session")
        
        msg = ChatMessage(
            role=MessageType.USER,
            content="Hello",
        )
        
        session.add_message(msg)
        
        assert len(session.messages) == 1
        assert session.messages[0].content == "Hello"
    
    def test_get_recent_messages(self):
        """测试获取最近消息."""
        session = ChatSession(session_id="test_session")
        
        for i in range(15):
            session.add_message(ChatMessage(
                role=MessageType.USER,
                content=f"Message {i}",
            ))
        
        recent = session.get_recent_messages(limit=5)
        
        assert len(recent) == 5
        assert recent[-1].content == "Message 14"
    
    def test_clear_messages(self):
        """测试清除消息."""
        session = ChatSession(session_id="test_session")
        session.add_message(ChatMessage(
            role=MessageType.USER,
            content="Hello",
        ))
        
        session.clear_messages()
        
        assert len(session.messages) == 0
    
    def test_session_to_dict(self):
        """测试会话转换为字典."""
        session = ChatSession(session_id="test_session")
        session.add_message(ChatMessage(
            role=MessageType.USER,
            content="Test",
        ))
        
        data = session.to_dict()
        
        assert data["session_id"] == "test_session"
        assert len(data["messages"]) == 1
        assert "created_at" in data
    
    def test_session_from_dict(self):
        """测试从字典创建会话."""
        data = {
            "session_id": "test_session",
            "user_id": "user_123",
            "messages": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "content": "Hello",
                    "timestamp": "2024-01-01T12:00:00",
                }
            ],
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:00:00",
        }
        
        session = ChatSession.from_dict(data)
        
        assert session.session_id == "test_session"
        assert session.user_id == "user_123"
        assert len(session.messages) == 1


class TestConnectionStatus:
    """测试 ConnectionStatus 枚举."""
    
    def test_connection_status_values(self):
        """测试连接状态值."""
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"
        assert ConnectionStatus.CONNECTING.value == "connecting"
        assert ConnectionStatus.CONNECTED.value == "connected"
        assert ConnectionStatus.ERROR.value == "error"
        assert ConnectionStatus.RECONNECTING.value == "reconnecting"


class TestSessionState:
    """测试 SessionState 模型."""
    
    def test_create_session_state(self):
        """测试创建会话状态."""
        state = SessionState()
        
        assert state.connection_status == ConnectionStatus.DISCONNECTED
        assert state.current_session is None
        assert state.is_processing is False
        assert state.error_message is None
    
    def test_set_connected(self):
        """测试设置连接状态."""
        state = SessionState()
        state.set_connected()
        
        assert state.connection_status == ConnectionStatus.CONNECTED
        assert state.error_message is None
    
    def test_set_connecting(self):
        """测试设置连接中状态."""
        state = SessionState()
        state.set_connecting()
        
        assert state.connection_status == ConnectionStatus.CONNECTING
    
    def test_set_error(self):
        """测试设置错误状态."""
        state = SessionState()
        state.set_error("Connection failed")
        
        assert state.connection_status == ConnectionStatus.ERROR
        assert state.error_message == "Connection failed"
    
    def test_set_processing(self):
        """测试设置处理状态."""
        state = SessionState()
        state.set_processing(True)
        
        assert state.is_processing is True
        
        state.set_processing(False)
        assert state.is_processing is False