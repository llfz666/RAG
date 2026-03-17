"""Chat Page - 聊天页面组件（Streamlit 原生版）.

This module provides the Streamlit chat page for interacting with the Smart Agent.
使用 Streamlit 原生方式处理异步代码。
"""

from __future__ import annotations

import logging
from typing import Optional

import streamlit as st
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径，确保可以导入模块
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dashboard.chat_models import (
    ChatMessage,
    ChatSession,
    MessageType,
)
from dashboard.chat_service import get_chat_service, initialize_chat_service

logger = logging.getLogger(__name__)

# 页面配置
st.set_page_config(
    page_title="Agent Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义 CSS
st.markdown("""
<style>
.chat-message {
    padding: 1rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
    border: 1px solid #e0e0e0;
}
.chat-message.user {
    background-color: #f0f2f6;
}
.chat-message.assistant {
    background-color: #e8f5e9;
}
.chat-message.thought {
    background-color: #fff3e0;
    font-style: italic;
}
.chat-message.action {
    background-color: #e3f2fd;
}
.chat-message.observation {
    background-color: #f3e5f5;
}
.chat-message.final_answer {
    background-color: #c8e6c9;
    border-color: #4caf50;
}
.chat-message.error {
    background-color: #ffebee;
    border-color: #f44336;
}
.chat-message.system {
    background-color: #eceff1;
}
</style>
""", unsafe_allow_html=True)


def render_message(message: ChatMessage) -> None:
    """渲染单条消息."""
    css_class = f"chat-message {message.role.value}"
    time_str = message.timestamp.strftime("%H:%M:%S")
    
    with st.container():
        if message.role == MessageType.USER:
            st.markdown(f"""
            <div class="{css_class}" style="text-align: right;">
                <span style="color: #666; font-size: 0.8em;">{time_str}</span>
                <p style="margin: 0.5rem 0;">{message.content}</p>
                <strong>👤 您</strong>
            </div>
            """, unsafe_allow_html=True)
        
        elif message.role == MessageType.FINAL_ANSWER:
            st.success(f"**✅ {message.content}**")
        
        elif message.role == MessageType.ERROR:
            st.error(f"**❌ {message.content}**")
        
        elif message.role == MessageType.THOUGHT:
            content = message.content
            if len(content) > 100:
                with st.expander(f"🤔 {content[:50]}..."):
                    st.markdown(f"*{content}*")
            else:
                st.info(f"🤔 {content}")
        
        elif message.role == MessageType.ACTION:
            tool_name = message.metadata.get("tool", "unknown")
            tool_input = message.metadata.get("input", {})
            with st.expander(f"🔧 {message.content}"):
                st.markdown(f"**工具**: `{tool_name}`")
                if tool_input:
                    st.json(tool_input)
        
        elif message.role == MessageType.OBSERVATION:
            result = message.metadata.get("result")
            content = message.content
            with st.expander(f"📦 {content[:50]}..." if len(content) > 50 else f"📦 {content}"):
                if result:
                    if isinstance(result, (dict, list)):
                        st.json(result)
                    else:
                        st.text(str(result)[:1000])
        
        elif message.role == MessageType.SYSTEM:
            st.info(f"⚙️ **系统**: {message.content}")
        
        else:
            st.markdown(f"""
            <div class="{css_class}">
                <small style="color: #666;">{time_str}</small>
                <p>{message.content}</p>
            </div>
            """, unsafe_allow_html=True)


def chat_page() -> None:
    """聊天页面主逻辑 - Streamlit 原生版."""
    st.title("💬 Agent Chat")
    st.markdown("与智能助手对话，获取知识库支持的答案")
    
    # 获取服务实例
    service = get_chat_service()
    
    # 初始化服务（只在第一次加载时）
    if "chat_service_initialized" not in st.session_state:
        st.session_state.chat_service_initialized = False
    
    if not st.session_state.chat_service_initialized:
        # 使用 progress 显示初始化进度
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 步骤 1: 加载配置
            status_text.text("正在加载配置...")
            progress_bar.progress(25)
            
            # 步骤 2: 初始化 LLM
            status_text.text("正在初始化 LLM...")
            progress_bar.progress(50)
            
            # 步骤 3: 初始化 RAG（可选）
            status_text.text("正在准备知识库...")
            progress_bar.progress(75)
            
            # 使用 Streamlit 的异步支持
            import asyncio
            asyncio.run(initialize_chat_service())
            
            progress_bar.progress(100)
            status_text.text("✅ Agent 已就绪！")
            
            st.session_state.chat_service_initialized = True
            
            # 等待 0.5 秒让用户看到成功消息
            import time
            time.sleep(0.5)
            
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"初始化失败：{e}")
            st.info("请检查配置文件 settings.yaml 是否正确设置")
            return
        
        progress_bar.empty()
        status_text.empty()
    
    # 初始化会话历史
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "session_id" not in st.session_state:
        import uuid
        st.session_state.session_id = str(uuid.uuid4())[:8]
    
    # 侧边栏
    with st.sidebar:
        st.title("💬 Chat Dashboard")
        
        # 连接状态
        st.subheader("连接状态")
        if service.is_initialized:
            st.success("🟢 已连接")
        elif service.is_initializing:
            st.info("🔄 连接中...")
        else:
            st.warning("🔴 未连接")
        
        st.divider()
        
        # 会话信息
        st.subheader("会话信息")
        st.metric("消息数", len(st.session_state.messages))
        st.metric("会话 ID", st.session_state.session_id)
        
        st.divider()
        
        # 操作按钮
        st.subheader("操作")
        
        if st.button("🗑️ 清除当前会话", key="clear_btn"):
            st.session_state.messages = []
            import uuid
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.rerun()
        
        if st.button("🔄 重新连接", key="reconnect_btn"):
            st.session_state.chat_service_initialized = False
            try:
                import asyncio
                asyncio.run(service.shutdown())
            except:
                pass
            st.rerun()
    
    # 主聊天区域
    chat_container = st.container()
    
    with chat_container:
        # 显示历史消息
        if st.session_state.messages:
            for msg in st.session_state.messages:
                render_message(msg)
        else:
            st.info("👋 您好！我是您的智能助手，请输入问题开始对话。")
    
    # 聊天输入框
    st.divider()
    
    prompt = st.chat_input("输入您的问题...", key="chat_input")
    
    if prompt:
        # 添加用户消息
        user_msg = ChatMessage(
            role=MessageType.USER,
            content=prompt,
        )
        st.session_state.messages.append(user_msg)
        
        # 显示用户消息
        with chat_container:
            render_message(user_msg)
        
        # 处理查询并流式显示
        with st.spinner("Agent 正在思考..."):
            status_placeholder = st.empty()
            
            try:
                # 使用 Streamlit 的异步支持
                import asyncio
                
                # 异步处理查询
                async def process_query_async():
                    messages = []
                    async for msg in service.process_query(
                        query=prompt,
                        session_id=st.session_state.session_id,
                    ):
                        messages.append(msg)
                    return messages
                
                # 运行异步代码
                messages = asyncio.run(process_query_async())
                
                # 处理返回的消息
                for msg in messages:
                    # 实时显示消息
                    if msg.role == MessageType.THOUGHT:
                        status_placeholder.info(f"🤔 {msg.content}")
                    elif msg.role == MessageType.ACTION:
                        status_placeholder.warning(f"🔧 {msg.content}")
                    elif msg.role == MessageType.OBSERVATION:
                        status_placeholder.success(f"📦 {msg.content}")
                    elif msg.role == MessageType.FINAL_ANSWER:
                        status_placeholder.empty()
                        with chat_container:
                            render_message(msg)
                    elif msg.role == MessageType.ERROR:
                        status_placeholder.empty()
                        st.error(f"❌ {msg.content}")
                    
                    # 添加到历史消息（除了临时状态消息）
                    if msg.role not in [MessageType.THOUGHT, MessageType.ACTION, MessageType.OBSERVATION]:
                        st.session_state.messages.append(msg)
                
                status_placeholder.empty()
                
            except Exception as e:
                status_placeholder.empty()
                st.error(f"处理失败：{e}")
                logger.exception("Chat query failed")
        
        # 重新加载页面以显示新消息
        st.rerun()


if __name__ == "__main__":
    chat_page()