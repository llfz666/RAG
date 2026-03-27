"""
Token Monitor 数据模型模块

定义所有数据结构，使用 dataclass 确保类型安全和一致性
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class TokenStatus(str, Enum):
    """Token 使用记录状态"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


class TaskType(str, Enum):
    """任务类型"""
    CHAT = "chat"
    RAG = "rag"
    TOOL_CALL = "tool_call"
    AGENT_PLAN = "agent_plan"
    AGENT_EXECUTE = "agent_execute"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    OTHER = "other"


class AlertType(str, Enum):
    """告警类型"""
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXCEEDED = "budget_exceeded"
    ANOMALY_DETECTED = "anomaly_detected"
    RATE_LIMIT_WARNING = "rate_limit_warning"


@dataclass
class TokenUsage:
    """
    单次 Token 使用记录
    
    这是核心数据类，所有字段都应该是明确的
    """
    # 基本信息
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    
    # 可选信息
    id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    task_type: Optional[str] = None
    status: TokenStatus = TokenStatus.SUCCESS
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    namespace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return {
            'id': self.id,
            'model': self.model,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'cost': self.cost,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'task_type': self.task_type,
            'status': self.status.value if isinstance(self.status, TokenStatus) else self.status,
            'error_message': self.error_message,
            'duration_ms': self.duration_ms,
            'metadata': self.metadata,
            'namespace': self.namespace,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenUsage":
        """从字典创建实例"""
        # 处理 timestamp
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()
        
        # 处理 status
        status = data.get('status', 'success')
        if isinstance(status, str):
            status = TokenStatus(status)
        
        return cls(
            id=data.get('id'),
            model=data['model'],
            prompt_tokens=data['prompt_tokens'],
            completion_tokens=data['completion_tokens'],
            total_tokens=data['total_tokens'],
            cost=data['cost'],
            timestamp=timestamp,
            user_id=data.get('user_id'),
            session_id=data.get('session_id'),
            task_type=data.get('task_type'),
            status=status,
            error_message=data.get('error_message'),
            duration_ms=data.get('duration_ms'),
            metadata=data.get('metadata', {}),
            namespace=data.get('namespace'),
        )


@dataclass
class UsageStats:
    """
    用量统计信息
    """
    # 总量统计
    total_tokens: int = 0
    total_cost: float = 0.0
    total_requests: int = 0
    
    # 按模型分组
    by_model: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 按用户分组
    by_user: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 按任务类型分组
    by_task_type: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 时间范围
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost,
            'total_requests': self.total_requests,
            'by_model': self.by_model,
            'by_user': self.by_user,
            'by_task_type': self.by_task_type,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
        }


@dataclass
class BudgetStatus:
    """
    预算状态
    """
    today_cost: float = 0.0
    daily_budget: float = 10.0
    monthly_budget: float = 300.0
    month_cost: float = 0.0
    
    @property
    def remaining_daily(self) -> float:
        """剩余每日预算"""
        return max(0, self.daily_budget - self.today_cost)
    
    @property
    def remaining_monthly(self) -> float:
        """剩余每月预算"""
        return max(0, self.monthly_budget - self.month_cost)
    
    @property
    def daily_usage_ratio(self) -> float:
        """每日预算使用率"""
        if self.daily_budget <= 0:
            return 1.0
        return self.today_cost / self.daily_budget
    
    @property
    def monthly_usage_ratio(self) -> float:
        """每月预算使用率"""
        if self.monthly_budget <= 0:
            return 1.0
        return self.month_cost / self.monthly_budget
    
    @property
    def is_over_budget(self) -> bool:
        """是否超出预算"""
        return self.remaining_daily <= 0 or self.remaining_monthly <= 0
    
    @property
    def needs_warning(self) -> bool:
        """是否需要告警"""
        return self.daily_usage_ratio >= 0.8 or self.monthly_usage_ratio >= 0.8
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'today_cost': self.today_cost,
            'daily_budget': self.daily_budget,
            'monthly_budget': self.monthly_budget,
            'month_cost': self.month_cost,
            'remaining_daily': self.remaining_daily,
            'remaining_monthly': self.remaining_monthly,
            'daily_usage_ratio': self.daily_usage_ratio,
            'monthly_usage_ratio': self.monthly_usage_ratio,
            'is_over_budget': self.is_over_budget,
            'needs_warning': self.needs_warning,
        }


@dataclass
class Alert:
    """
    告警记录
    """
    alert_type: AlertType
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'alert_type': self.alert_type.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'is_resolved': self.is_resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'metadata': self.metadata,
        }


@dataclass
class ModelBreakdown:
    """
    模型用量明细
    """
    model: str
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0
    request_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'model': self.model,
            'total_tokens': self.total_tokens,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_cost': self.total_cost,
            'request_count': self.request_count,
        }


@dataclass
class UserBreakdown:
    """
    用户用量明细
    """
    user_id: str
    total_tokens: int = 0
    total_cost: float = 0.0
    request_count: int = 0
    last_activity: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'user_id': self.user_id,
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost,
            'request_count': self.request_count,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
        }