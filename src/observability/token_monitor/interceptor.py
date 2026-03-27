"""
LLM Interceptor - LLM 调用拦截器模块

负责：
1. 拦截 LLM 调用，自动记录 token 使用
2. 支持多种 LLM 客户端（OpenAI、Qwen、DeepSeek 等）
3. 预算检查和告警

使用示例：
    # 方式 1：装饰器
    @token_interceptor.track(user_id="user_123", task_type="chat")
    def chat_with_llm(messages):
        return client.chat.completions.create(messages=messages)
    
    # 方式 2：包装器
    tracked_client = OpenAIInterceptor(original_client, tracker, budget_manager)
    response = tracked_client.chat.completions.create(messages=messages)
"""

import time
import functools
from typing import Optional, Dict, Any, Callable, Type, Any
from .tracker import TokenTracker
from .budget import BudgetManager
from .models import TokenStatus, TaskType


class TokenInterceptor:
    """
    Token 拦截器 - 用于自动记录 LLM 调用的 token 使用
    
    使用示例：
        interceptor = TokenInterceptor(tracker, budget_manager)
        
        # 包装 OpenAI 客户端
        from openai import OpenAI
        client = OpenAI(api_key="...")
        tracked_client = interceptor.wrap_openai(client)
        
        # 现在调用会自动记录 token
        response = tracked_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}]
        )
    """
    
    def __init__(
        self, 
        tracker: TokenTracker, 
        budget_manager: Optional[BudgetManager] = None
    ):
        """
        初始化拦截器
        
        Args:
            tracker: TokenTracker 实例
            budget_manager: BudgetManager 实例（可选）
        """
        self.tracker = tracker
        self.budget_manager = budget_manager
    
    def track(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_type: str = "chat",
        model_override: Optional[str] = None,
    ):
        """
        装饰器：跟踪 LLM 调用
        
        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            task_type: 任务类型
            model_override: 覆盖模型名称
        
        Returns:
            装饰器函数
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return self._track_call(
                    func=func,
                    args=args,
                    kwargs=kwargs,
                    user_id=user_id,
                    session_id=session_id,
                    task_type=task_type,
                    model_override=model_override,
                )
            return wrapper
        return decorator
    
    def _track_call(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        user_id: Optional[str],
        session_id: Optional[str],
        task_type: str,
        model_override: Optional[str],
    ) -> Any:
        """跟踪单次调用"""
        start_time = time.time()
        
        # 尝试从参数中获取模型名
        model = model_override or self._extract_model(kwargs)
        
        # 预算检查（如果有预算管理器）
        if self.budget_manager:
            can_proceed, message = self.budget_manager.can_proceed(user_id, estimated_cost=0.1)
            if not can_proceed:
                raise BudgetExceededError(f"预算检查失败：{message}")
        
        # 计算输入 token 数（估算）
        prompt_tokens = self._estimate_input_tokens(kwargs)
        
        try:
            # 执行实际调用
            result = func(*args, **kwargs)
            
            # 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 解析响应中的 token 数
            completion_tokens = self._extract_output_tokens(result)
            
            # 记录使用
            self.tracker.record(
                model=model or "unknown",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                user_id=user_id,
                session_id=session_id,
                task_type=task_type,
                status=TokenStatus.SUCCESS,
                duration_ms=duration_ms,
            )
            
            return result
            
        except Exception as e:
            # 记录错误
            duration_ms = int((time.time() - start_time) * 1000)
            self.tracker.record(
                model=model or "unknown",
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                user_id=user_id,
                session_id=session_id,
                task_type=task_type,
                status=TokenStatus.ERROR,
                error_message=str(e),
                duration_ms=duration_ms,
            )
            raise
    
    def _extract_model(self, kwargs: dict) -> Optional[str]:
        """从 kwargs 中提取模型名"""
        return kwargs.get('model')
    
    def _estimate_input_tokens(self, kwargs: dict) -> int:
        """
        估算输入 token 数
        
        这里使用简单估算，实际可以使用 tiktoken 精确计算
        """
        messages = kwargs.get('messages', [])
        prompt = kwargs.get('prompt', '')
        
        # 计算消息 token 数
        token_count = 0
        
        if messages:
            for msg in messages:
                content = msg.get('content', '')
                if isinstance(content, str):
                    # 简单估算：中文约 2 字符/token，英文约 4 字符/token
                    token_count += len(content) // 3
                elif isinstance(content, list):
                    # 多模态内容
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            token_count += len(item.get('text', '')) // 3
        elif prompt:
            token_count += len(prompt) // 3
        
        # 加上系统开销
        token_count += 10
        
        return max(1, token_count)
    
    def _extract_output_tokens(self, result: Any) -> int:
        """从响应中提取输出 token 数"""
        # 尝试访问 usage 属性
        if hasattr(result, 'usage'):
            usage = result.usage
            if hasattr(usage, 'completion_tokens'):
                return usage.completion_tokens
            elif hasattr(usage, 'get'):
                return usage.get('completion_tokens', 0)
        
        # 尝试直接访问
        if hasattr(result, 'get'):
            usage = result.get('usage', {})
            if isinstance(usage, dict):
                return usage.get('completion_tokens', 0)
        
        # 默认返回估算值
        return 100
    
    def wrap_openai(self, client: Any) -> Any:
        """
        包装 OpenAI 客户端
        
        Args:
            client: OpenAI 客户端实例
        
        Returns:
            包装后的客户端
        """
        return OpenAIInterceptor(client, self)
    
    def wrap_qwen(self, client: Any) -> Any:
        """
        包装 Qwen 客户端
        
        Args:
            client: Qwen 客户端实例
        
        Returns:
            包装后的客户端
        """
        return QwenInterceptor(client, self)


class OpenAIInterceptor:
    """OpenAI 客户端包装器"""
    
    def __init__(self, client: Any, interceptor: TokenInterceptor):
        self._client = client
        self._interceptor = interceptor
        
        # 代理所有属性
        self.__dict__['_client'] = client
        self.__dict__['_interceptor'] = interceptor
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name in ('_client', '_interceptor'):
            self.__dict__[name] = value
        else:
            setattr(self._client, name, value)
    
    @property
    def chat(self) -> Any:
        """代理 chat 属性"""
        return ChatCompletionsInterceptor(self._client.chat, self._interceptor)
    
    @property
    def completions(self) -> Any:
        """代理 completions 属性"""
        return CompletionsInterceptor(self._client.completions, self._interceptor)


class ChatCompletionsInterceptor:
    """Chat Completions 包装器"""
    
    def __init__(self, chat: Any, interceptor: TokenInterceptor):
        self._chat = chat
        self._interceptor = interceptor
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)
    
    @property
    def completions(self) -> Any:
        return ChatCompletionCreateInterceptor(self._chat.completions, self._interceptor)


class ChatCompletionCreateInterceptor:
    """Chat Completion create 方法包装器"""
    
    def __init__(self, completions: Any, interceptor: TokenInterceptor):
        self._completions = completions
        self._interceptor = interceptor
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)
    
    def create(self, *args, **kwargs) -> Any:
        """拦截 create 调用"""
        return self._interceptor._track_call(
            func=self._completions.create,
            args=args,
            kwargs=kwargs,
            user_id=kwargs.pop('_user_id', None),
            session_id=kwargs.pop('_session_id', None),
            task_type=kwargs.pop('_task_type', 'chat'),
            model_override=kwargs.pop('_model', None),
        )


class CompletionsInterceptor:
    """Completions 包装器"""
    
    def __init__(self, completions: Any, interceptor: TokenInterceptor):
        self._completions = completions
        self._interceptor = interceptor
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)
    
    def create(self, *args, **kwargs) -> Any:
        """拦截 create 调用"""
        return self._interceptor._track_call(
            func=self._completions.create,
            args=args,
            kwargs=kwargs,
            user_id=kwargs.pop('_user_id', None),
            session_id=kwargs.pop('_session_id', None),
            task_type=kwargs.pop('_task_type', 'completion'),
            model_override=kwargs.pop('_model', None),
        )


class QwenInterceptor:
    """Qwen 客户端包装器（类似结构）"""
    
    def __init__(self, client: Any, interceptor: TokenInterceptor):
        self._client = client
        self._interceptor = interceptor
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)
    
    def call(self, *args, **kwargs) -> Any:
        """拦截 call 调用"""
        return self._interceptor._track_call(
            func=self._client.call,
            args=args,
            kwargs=kwargs,
            user_id=kwargs.pop('_user_id', None),
            session_id=kwargs.pop('_session_id', None),
            task_type=kwargs.pop('_task_type', 'chat'),
            model_override=kwargs.pop('_model', None),
        )


class BudgetExceededError(Exception):
    """预算超出异常"""
    pass


# 便捷函数
def create_intercepted_openai_client(
    api_key: str,
    tracker: TokenTracker,
    budget_manager: Optional[BudgetManager] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    **kwargs
) -> Any:
    """
    创建带拦截的 OpenAI 客户端
    
    Args:
        api_key: API 密钥
        tracker: TokenTracker 实例
        budget_manager: BudgetManager 实例
        user_id: 默认用户 ID
        session_id: 默认会话 ID
        **kwargs: 其他 OpenAI 客户端参数
    
    Returns:
        包装后的 OpenAI 客户端
    """
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key, **kwargs)
    interceptor = TokenInterceptor(tracker, budget_manager)
    
    # 返回包装后的客户端，并设置默认参数
    wrapped = interceptor.wrap_openai(client)
    
    # 添加便捷方法
    def tracked_chat(messages, **chat_kwargs):
        chat_kwargs.setdefault('_user_id', user_id)
        chat_kwargs.setdefault('_session_id', session_id)
        return wrapped.chat.completions.create(messages=messages, **chat_kwargs)
    
    wrapped.tracked_chat = tracked_chat
    
    return wrapped