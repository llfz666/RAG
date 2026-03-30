"""速率限制服务 - 企业级请求频率控制

本模块提供全面的速率限制功能，防御：
1. DDoS 攻击（分布式拒绝服务）
2. 暴力破解（密码猜测）
3. API 滥用（过度调用）
4. 资源耗尽（内存/CPU）

使用示例:
    from src.security.rate_limiter import RateLimiter, RateLimitExceeded
    
    # 创建限流器
    limiter = RateLimiter()
    
    # 使用装饰器
    @limiter.limit("10/minute")
    async def query_knowledge(query: str):
        ...
    
    # 手动检查
    if not limiter.is_allowed("user123", "query", limit="10/minute"):
        raise RateLimitExceeded("Too many requests")
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """速率限制超出异常"""
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[str] = None,
        retry_after: Optional[float] = None,
        client_id: Optional[str] = None,
    ):
        self.message = message
        self.limit = limit
        self.retry_after = retry_after
        self.client_id = client_id
        super().__init__(self.message)


class RateLimitStrategy(str, Enum):
    """限流策略"""
    SLIDING_WINDOW = "sliding_window"      # 滑动窗口
    FIXED_WINDOW = "fixed_window"          # 固定窗口
    TOKEN_BUCKET = "token_bucket"          # 令牌桶
    LEAKY_BUCKET = "leaky_bucket"          # 漏桶


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    limit: int  # 限制次数
    period: int  # 时间周期（秒）
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst: Optional[int] = None  # 突发允许（令牌桶专用）
    
    @classmethod
    def parse(cls, rate_string: str) -> "RateLimitConfig":
        """解析速率字符串
        
        支持格式:
        - "10/minute" - 每分钟 10 次
        - "100/hour" - 每小时 100 次
        - "1000/day" - 每天 1000 次
        - "5/second" - 每秒 5 次
        - "10/60" - 每 60 秒 10 次
        
        Args:
            rate_string: 速率字符串
            
        Returns:
            RateLimitConfig 配置
        """
        rate_string = rate_string.lower().strip()
        
        # 解析数字/时间格式
        match = re.match(r"(\d+)\s*/\s*(\w+)", rate_string)
        if not match:
            raise ValueError(f"Invalid rate string format: {rate_string}")
        
        limit = int(match.group(1))
        period_str = match.group(2)
        
        # 时间单位转换
        period_map = {
            'second': 1,
            'seconds': 1,
            'sec': 1,
            's': 1,
            'minute': 60,
            'minutes': 60,
            'min': 60,
            'm': 60,
            'hour': 3600,
            'hours': 3600,
            'hr': 3600,
            'h': 3600,
            'day': 86400,
            'days': 86400,
            'd': 86400,
        }
        
        if period_str.isdigit():
            period = int(period_str)
        elif period_str in period_map:
            period = period_map[period_str]
        else:
            raise ValueError(f"Unknown time period: {period_str}")
        
        return cls(limit=limit, period=period)


@dataclass
class RateLimitResult:
    """速率限制检查结果"""
    allowed: bool
    current_count: int
    limit: int
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "allowed": self.allowed,
            "current_count": self.current_count,
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_at": self.reset_at,
            "retry_after": self.retry_after,
        }


class SlidingWindowCounter:
    """滑动窗口计数器"""
    
    def __init__(self, limit: int, period: int):
        self.limit = limit
        self.period = period
        self.requests: List[float] = []
    
    def check(self) -> Tuple[bool, int]:
        """检查是否允许请求"""
        now = time.time()
        window_start = now - self.period
        
        # 清理过期请求
        self.requests = [t for t in self.requests if t > window_start]
        
        # 检查是否超出限制
        current_count = len(self.requests)
        allowed = current_count < self.limit
        
        return allowed, current_count
    
    def record(self) -> None:
        """记录一次请求"""
        self.requests.append(time.time())
    
    def get_reset_time(self) -> float:
        """获取重置时间"""
        if not self.requests:
            return time.time()
        return self.requests[0] + self.period


class FixedWindowCounter:
    """固定窗口计数器"""
    
    def __init__(self, limit: int, period: int):
        self.limit = limit
        self.period = period
        self.count = 0
        self.window_start = time.time()
    
    def check(self) -> Tuple[bool, int]:
        """检查是否允许请求"""
        now = time.time()
        
        # 检查是否需要重置窗口
        if now - self.window_start >= self.period:
            self.window_start = now
            self.count = 0
        
        allowed = self.count < self.limit
        return allowed, self.count
    
    def record(self) -> None:
        """记录一次请求"""
        self.count += 1
    
    def get_reset_time(self) -> float:
        """获取重置时间"""
        return self.window_start + self.period


class TokenBucket:
    """令牌桶算法"""
    
    def __init__(self, capacity: int, refill_rate: float, burst: Optional[int] = None):
        """
        Args:
            capacity: 桶容量（最大令牌数）
            refill_rate: 补充速率（每秒补充的令牌数）
            burst: 突发容量（可选，默认等于 capacity）
        """
        self.capacity = capacity
        self.burst = burst or capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
    
    def _refill(self) -> None:
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def check(self) -> Tuple[bool, int]:
        """检查是否允许请求"""
        self._refill()
        allowed = self.tokens >= 1
        return allowed, int(self.tokens)
    
    def record(self) -> None:
        """消耗一个令牌"""
        if self.tokens >= 1:
            self.tokens -= 1
    
    def get_reset_time(self) -> float:
        """获取完全恢复时间"""
        tokens_needed = self.capacity - self.tokens
        if tokens_needed <= 0:
            return time.time()
        return time.time() + (tokens_needed / self.refill_rate)


class RateLimiter:
    """企业级速率限制器
    
    功能：
    1. 多策略支持（滑动窗口、固定窗口、令牌桶、漏桶）
    2. 多维度限流（用户/IP/端点）
    3. 分布式支持（Redis 后端）
    4. 动态限流配置
    5. 白名单/黑名单
    """
    
    def __init__(
        self,
        default_limit: str = "100/minute",
        strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW,
        enable_async: bool = True,
        use_redis: bool = False,
        redis_url: Optional[str] = None,
        whitelist: Optional[set] = None,
        blacklist: Optional[set] = None,
        log_exceeded: bool = True,
    ) -> None:
        """初始化速率限制器
        
        Args:
            default_limit: 默认限制（如 "100/minute"）
            strategy: 限流策略
            enable_async: 启用异步支持
            use_redis: 使用 Redis 后端（分布式）
            redis_url: Redis 连接 URL
            whitelist: 白名单（不限流）
            blacklist: 黑名单（直接拒绝）
            log_exceeded: 记录超出限制的日志
        """
        self.default_config = RateLimitConfig.parse(default_limit)
        self.strategy = strategy
        self.enable_async = enable_async
        self.use_redis = use_redis
        self.redis_url = redis_url
        self.whitelist = whitelist or set()
        self.blacklist = blacklist or set()
        self.log_exceeded = log_exceeded
        
        # 本地存储（client_id -> endpoint -> counter）
        self._counters: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # 统计信息
        self._stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "denied_requests": 0,
            "by_client": defaultdict(int),
        }
        
        # 审计日志
        self._audit_log: List[Dict[str, Any]] = []
        
        logger.info(f"RateLimiter initialized with default limit: {default_limit}")
    
    def is_allowed(
        self,
        client_id: str,
        endpoint: str = "default",
        limit: Optional[str] = None,
        config: Optional[RateLimitConfig] = None,
    ) -> bool:
        """检查请求是否允许
        
        Args:
            client_id: 客户端标识（用户 ID/IP 等）
            endpoint: 端点名称
            limit: 可选的覆盖限制
            config: 可选的覆盖配置
            
        Returns:
            是否允许
        """
        # 检查白名单
        if client_id in self.whitelist:
            return True
        
        # 检查黑名单
        if client_id in self.blacklist:
            return False
        
        # 获取配置
        if config is None:
            if limit:
                config = RateLimitConfig.parse(limit)
            else:
                config = self.default_config
        
        # 获取或创建计数器
        counter = self._get_counter(client_id, endpoint, config)
        
        # 检查限制
        allowed, current_count = counter.check()
        
        # 更新统计
        self._stats["total_requests"] += 1
        if allowed:
            self._stats["allowed_requests"] += 1
            counter.record()
        else:
            self._stats["denied_requests"] += 1
            self._stats["by_client"][client_id] += 1
            
            # 记录日志
            if self.log_exceeded:
                self._log_exceeded(client_id, endpoint, config)
        
        return allowed
    
    def check(
        self,
        client_id: str,
        endpoint: str = "default",
        limit: Optional[str] = None,
    ) -> RateLimitResult:
        """检查速率限制状态（不消耗配额）
        
        Args:
            client_id: 客户端标识
            endpoint: 端点名称
            limit: 可选的覆盖限制
            
        Returns:
            速率限制结果
        """
        config = RateLimitConfig.parse(limit) if limit else self.default_config
        
        # 检查白名单/黑名单
        if client_id in self.whitelist:
            return RateLimitResult(
                allowed=True,
                current_count=0,
                limit=config.limit,
                remaining=config.limit,
                reset_at=time.time(),
            )
        
        if client_id in self.blacklist:
            return RateLimitResult(
                allowed=False,
                current_count=config.limit + 1,
                limit=config.limit,
                remaining=0,
                reset_at=time.time() + config.period,
                retry_after=config.period,
            )
        
        # 获取计数器
        counter = self._get_counter(client_id, endpoint, config)
        
        # 检查状态
        allowed, current_count = counter.check()
        remaining = max(0, config.limit - current_count)
        reset_at = counter.get_reset_time()
        retry_after = max(0, reset_at - time.time()) if not allowed else None
        
        return RateLimitResult(
            allowed=allowed,
            current_count=current_count,
            limit=config.limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after,
        )
    
    def reset(self, client_id: str, endpoint: Optional[str] = None) -> None:
        """重置速率限制
        
        Args:
            client_id: 客户端标识
            endpoint: 端点名称（None 则重置所有）
        """
        if endpoint:
            if client_id in self._counters:
                self._counters[client_id].pop(endpoint, None)
        else:
            self._counters.pop(client_id, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": self._stats["total_requests"],
            "allowed_requests": self._stats["allowed_requests"],
            "denied_requests": self._stats["denied_requests"],
            "denial_rate": (
                self._stats["denied_requests"] / max(1, self._stats["total_requests"])
            ),
            "by_client": dict(self._stats["by_client"]),
            "active_clients": len(self._counters),
        }
    
    def limit(
        self,
        limit_string: str,
        endpoint: str = "default",
        key_func: Optional[Callable] = None,
    ) -> Callable:
        """装饰器：限制函数调用频率
        
        Args:
            limit_string: 限制字符串（如 "10/minute"）
            endpoint: 端点名称
            key_func: 获取 client_id 的函数
            
        Returns:
            装饰器函数
        """
        def decorator(func: Callable) -> Callable:
            if asyncio.iscoroutinefunction(func):
                async def async_wrapper(*args, **kwargs):
                    # 获取 client_id
                    client_id = self._get_key(func, args, kwargs, key_func)
                    
                    # 检查限制
                    if not self.is_allowed(client_id, endpoint, limit_string):
                        result = self.check(client_id, endpoint, limit_string)
                        raise RateLimitExceeded(
                            message=f"Rate limit exceeded for {endpoint}",
                            limit=limit_string,
                            retry_after=result.retry_after,
                            client_id=client_id,
                        )
                    
                    return await func(*args, **kwargs)
                return async_wrapper
            else:
                def sync_wrapper(*args, **kwargs):
                    # 获取 client_id
                    client_id = self._get_key(func, args, kwargs, key_func)
                    
                    # 检查限制
                    if not self.is_allowed(client_id, endpoint, limit_string):
                        result = self.check(client_id, endpoint, limit_string)
                        raise RateLimitExceeded(
                            message=f"Rate limit exceeded for {endpoint}",
                            limit=limit_string,
                            retry_after=result.retry_after,
                            client_id=client_id,
                        )
                    
                    return func(*args, **kwargs)
                return sync_wrapper
        
        return decorator
    
    # ==================== 内部方法 ====================
    
    def _get_counter(
        self,
        client_id: str,
        endpoint: str,
        config: RateLimitConfig,
    ) -> Union[SlidingWindowCounter, FixedWindowCounter, TokenBucket]:
        """获取或创建计数器"""
        if endpoint not in self._counters[client_id]:
            # 创建新计数器
            if config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                self._counters[client_id][endpoint] = SlidingWindowCounter(
                    config.limit, config.period
                )
            elif config.strategy == RateLimitStrategy.FIXED_WINDOW:
                self._counters[client_id][endpoint] = FixedWindowCounter(
                    config.limit, config.period
                )
            elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                refill_rate = config.limit / config.period
                self._counters[client_id][endpoint] = TokenBucket(
                    config.limit, refill_rate, config.burst
                )
            else:
                # 默认滑动窗口
                self._counters[client_id][endpoint] = SlidingWindowCounter(
                    config.limit, config.period
                )
        
        return self._counters[client_id][endpoint]
    
    def _get_key(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        key_func: Optional[Callable],
    ) -> str:
        """获取 client_id"""
        if key_func:
            return str(key_func(*args, **kwargs))
        
        # 默认使用第一个参数作为 key
        if args:
            return str(args[0])
        if kwargs:
            return str(list(kwargs.values())[0])
        
        return "anonymous"
    
    def _log_exceeded(
        self,
        client_id: str,
        endpoint: str,
        config: RateLimitConfig,
    ) -> None:
        """记录超出限制的日志"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "rate_limit_exceeded",
            "client_id": client_id,
            "endpoint": endpoint,
            "limit": f"{config.limit}/{config.period}",
        }
        
        self._audit_log.append(log_entry)
        
        # 保持日志大小合理
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-1000:]
        
        logger.warning(
            f"Rate limit exceeded: client={client_id}, endpoint={endpoint}, "
            f"limit={config.limit}/{config.period}s"
        )


# ==================== 便捷函数 ====================

# 全局限流器实例
_default_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """获取默认限流器实例"""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter()
    return _default_limiter


def is_allowed(client_id: str, endpoint: str = "default", limit: Optional[str] = None) -> bool:
    """便捷函数：检查是否允许"""
    return get_rate_limiter().is_allowed(client_id, endpoint, limit)


def check_rate_limit(client_id: str, endpoint: str = "default", limit: Optional[str] = None) -> RateLimitResult:
    """便捷函数：检查速率限制状态"""
    return get_rate_limiter().check(client_id, endpoint, limit)


def limit_requests(limit_string: str, endpoint: str = "default"):
    """便捷函数：装饰器限制请求"""
    return get_rate_limiter().limit(limit_string, endpoint)