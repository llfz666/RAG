"""意图识别模块 - 数据模型定义。

针对广告公司客服场景的意图分类和实体识别。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class IntentType(str, Enum):
    """广告公司客服意图类型。"""
    
    # 咨询类
    SERVICE_INQUIRY = "service_inquiry"  # 服务咨询
    PRICE_QUOTE = "price_quote"  # 报价咨询
    CASE_PORTFOLIO = "case_portfolio"  # 案例展示
    TIMELINE = "timeline"  # 周期咨询
    COMPANY_INFO = "company_info"  # 公司信息
    
    # 操作类
    REVISION = "revision"  # 修改请求
    URGENT = "urgent"  # 紧急需求
    FOLLOW_UP = "follow_up"  # 跟进进度
    
    # 情感类
    COMPLAINT = "complaint"  # 投诉
    PRAISE = "praise"  # 表扬
    
    # 流程类
    HANDOFF = "handoff"  # 转人工
    CONFIRM = "confirm"  # 确认
    CANCEL = "cancel"  # 取消
    
    # 基础类
    GREETING = "greeting"  # 问候
    FAREWELL = "farewell"  # 告别
    FAQ = "faq"  # 常见问题
    
    # 未知
    UNKNOWN = "unknown"  # 未知意图


class EntityType(str, Enum):
    """实体类型定义。"""
    
    # 服务类型
    SERVICE_TYPE = "service_type"  # 服务类型（Logo 设计、VI 设计、包装设计等）
    
    # 时间相关
    DEADLINE = "deadline"  # 截止时间
    DURATION = "duration"  # 周期时长
    
    # 价格相关
    BUDGET = "budget"  # 预算
    PRICE = "price"  # 价格
    
    # 项目相关
    PROJECT_NAME = "project_name"  # 项目名称
    INDUSTRY = "industry"  # 行业类型
    
    # 公司信息
    COMPANY_NAME = "company_name"  # 公司名称
    
    # 联系方式
    CONTACT = "contact"  # 联系方式
    
    # 数量
    QUANTITY = "quantity"  # 数量


@dataclass
class Entity:
    """识别出的实体。"""
    
    entity_type: EntityType
    value: str
    confidence: float = 1.0
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "type": self.entity_type.value,
            "value": self.value,
            "confidence": self.confidence,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
        }


@dataclass
class IntentResult:
    """意图识别结果。"""
    
    intent: IntentType
    confidence: float
    entities: list[Entity] = field(default_factory=list)
    raw_text: str = ""
    
    # 槽位信息（用于多轮对话）
    slots: dict[str, Any] = field(default_factory=dict)
    
    # 是否需要更多信息
    needs_more_info: bool = False
    
    # 缺失的槽位
    missing_slots: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "entities": [e.to_dict() for e in self.entities],
            "raw_text": self.raw_text,
            "slots": self.slots,
            "needs_more_info": self.needs_more_info,
            "missing_slots": self.missing_slots,
        }


# 各意图类型需要的槽位定义
INTENT_SLOTS: dict[IntentType, list[str]] = {
    IntentType.SERVICE_INQUIRY: ["service_type", "industry"],
    IntentType.PRICE_QUOTE: ["service_type", "quantity", "budget"],
    IntentType.CASE_PORTFOLIO: ["service_type", "industry"],
    IntentType.TIMELINE: ["service_type", "quantity"],
    IntentType.REVISION: ["project_name", "revision_reason"],
    IntentType.URGENT: ["deadline", "service_type"],
    IntentType.FOLLOW_UP: ["project_name"],
    IntentType.COMPLAINT: ["complaint_reason"],
}


# 意图类型描述（用于 Prompt）
INTENT_DESCRIPTIONS: dict[IntentType, str] = {
    IntentType.SERVICE_INQUIRY: "用户咨询公司提供哪些服务，如 Logo 设计、VI 设计、包装设计等",
    IntentType.PRICE_QUOTE: "用户询问某项服务的价格或要求报价",
    IntentType.CASE_PORTFOLIO: "用户要求查看公司的作品集、案例展示",
    IntentType.TIMELINE: "用户询问项目完成需要多长时间",
    IntentType.COMPANY_INFO: "用户询问公司相关信息，如地址、规模、成立时间等",
    IntentType.REVISION: "用户要求修改设计方案或提出修改意见",
    IntentType.URGENT: "用户表示需求很紧急，需要加急处理",
    IntentType.FOLLOW_UP: "用户询问项目进度或跟进情况",
    IntentType.COMPLAINT: "用户表达不满或投诉服务质量",
    IntentType.PRAISE: "用户表达满意或表扬",
    IntentType.HANDOFF: "用户要求转接人工客服",
    IntentType.CONFIRM: "用户确认某项信息或操作",
    IntentType.CANCEL: "用户取消某项操作或订单",
    IntentType.GREETING: "用户打招呼、问候",
    IntentType.FAREWELL: "用户告别、结束对话",
    IntentType.FAQ: "用户询问常见问题，如付款方式、发票等",
    IntentType.UNKNOWN: "无法识别的意图",
}