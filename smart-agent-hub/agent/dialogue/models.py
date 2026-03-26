"""对话管理模块 - 数据模型定义。

用于对话状态追踪、上下文管理和多轮对话流程控制。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from agent.intent.models import IntentResult, IntentType
from agent.sentiment.models import SentimentResult


class DialogueState(str, Enum):
    """对话状态。"""
    
    NEW = "new"              # 新对话
    ACTIVE = "active"        # 进行中
    WAITING_USER = "waiting_user"  # 等待用户输入
    WAITING_INFO = "waiting_info"  # 等待补充信息
    HANDOFF = "handoff"      # 转人工
    COMPLETED = "completed"  # 已完成
    CLOSED = "closed"        # 已关闭


class FlowStage(str, Enum):
    """对话流程阶段。"""
    
    GREETING = "greeting"       # 问候
    INTENT_RECOGNITION = "intent_recognition"  # 意图识别
    SLOT_FILLING = "slot_filling"  # 槽位填充
    CONFIRMATION = "confirmation"  # 确认
    SOLUTION = "solution"       # 提供解决方案
    FOLLOW_UP = "follow_up"     # 跟进
    CLOSING = "closing"         # 结束


@dataclass
class DialogueTurn:
    """对话轮次记录。"""
    
    # 轮次 ID
    turn_id: str = field(default_factory=lambda: str(uuid4()))
    
    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 用户输入
    user_input: str = ""
    
    # 系统回复
    system_response: str = ""
    
    # 意图识别结果
    intent_result: Optional[IntentResult] = None
    
    # 情感分析结果
    sentiment_result: Optional[SentimentResult] = None
    
    # 槽位状态
    slots: dict[str, Any] = field(default_factory=dict)
    
    # 对话行为
    dialogue_act: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "turn_id": self.turn_id,
            "timestamp": self.timestamp.isoformat(),
            "user_input": self.user_input,
            "system_response": self.system_response,
            "intent_result": self.intent_result.to_dict() if self.intent_result else None,
            "sentiment_result": self.sentiment_result.to_dict() if self.sentiment_result else None,
            "slots": self.slots,
            "dialogue_act": self.dialogue_act,
        }


@dataclass
class DialogueContext:
    """对话上下文。"""
    
    # 对话 ID
    dialogue_id: str = field(default_factory=lambda: str(uuid4()))
    
    # 用户 ID（可选）
    user_id: Optional[str] = None
    
    # 对话状态
    state: DialogueState = DialogueState.NEW
    
    # 当前流程阶段
    flow_stage: FlowStage = FlowStage.GREETING
    
    # 当前意图
    current_intent: Optional[IntentType] = None
    
    # 已填充的槽位
    filled_slots: dict[str, Any] = field(default_factory=dict)
    
    # 待填充的槽位
    pending_slots: list[str] = field(default_factory=list)
    
    # 对话历史（最近 N 轮）
    history: list[DialogueTurn] = field(default_factory=list)
    
    # 上下文变量
    variables: dict[str, Any] = field(default_factory=dict)
    
    # 指代消解信息
    references: dict[str, str] = field(default_factory=dict)
    
    # 对话开始时间
    start_time: datetime = field(default_factory=datetime.now)
    
    # 最后活跃时间
    last_activity: datetime = field(default_factory=datetime.now)
    
    # 元数据
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # 最大历史长度
    max_history_length: int = 10
    
    def add_turn(
        self,
        user_input: str,
        system_response: str,
        intent_result: Optional[IntentResult] = None,
        sentiment_result: Optional[SentimentResult] = None,
    ) -> DialogueTurn:
        """添加新的对话轮次。
        
        Args:
            user_input: 用户输入。
            system_response: 系统回复。
            intent_result: 意图识别结果。
            sentiment_result: 情感分析结果。
            
        Returns:
            DialogueTurn: 新建的对话轮次。
        """
        turn = DialogueTurn(
            user_input=user_input,
            system_response=system_response,
            intent_result=intent_result,
            sentiment_result=sentiment_result,
            slots=self.filled_slots.copy(),
        )
        
        self.history.append(turn)
        
        # 限制历史长度
        if len(self.history) > self.max_history_length:
            self.history = self.history[-self.max_history_length:]
        
        self.last_activity = datetime.now()
        
        return turn
    
    def get_recent_turns(self, n: int = 3) -> list[DialogueTurn]:
        """获取最近 N 轮对话。
        
        Args:
            n: 轮次数量。
            
        Returns:
            list[DialogueTurn]: 最近 N 轮对话。
        """
        return self.history[-n:] if self.history else []
    
    def get_history_summary(self) -> str:
        """获取对话历史摘要。
        
        Returns:
            str: 对话历史摘要。
        """
        if not self.history:
            return ""
        
        summaries = []
        for turn in self.history[-5:]:  # 最近 5 轮
            if turn.user_input:
                summaries.append(f"用户：{turn.user_input[:50]}...")
            if turn.system_response:
                summaries.append(f"系统：{turn.system_response[:50]}...")
        
        return "\n".join(summaries)
    
    def update_slots(self, slots: dict[str, Any]) -> None:
        """更新槽位信息。
        
        Args:
            slots: 槽位数据。
        """
        self.filled_slots.update(slots)
        
        # 从待填充列表中移除已填充的槽位
        for key in slots.keys():
            if key in self.pending_slots:
                self.pending_slots.remove(key)
    
    def get_slot(self, key: str, default: Any = None) -> Any:
        """获取槽位值。
        
        Args:
            key: 槽位键。
            default: 默认值。
            
        Returns:
            Any: 槽位值。
        """
        return self.filled_slots.get(key, default)
    
    def set_variable(self, key: str, value: Any) -> None:
        """设置上下文变量。
        
        Args:
            key: 变量键。
            value: 变量值。
        """
        self.variables[key] = value
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取上下文变量。
        
        Args:
            key: 变量键。
            default: 默认值。
            
        Returns:
            Any: 变量值。
        """
        return self.variables.get(key, default)
    
    def resolve_reference(self, mention: str) -> str:
        """解析指代。
        
        Args:
            mention: 指代词（如"这个"、"那个"、"它"等）。
            
        Returns:
            str: 解析后的实际内容。
        """
        return self.references.get(mention, mention)
    
    def update_references(self, entities: list) -> None:
        """根据实体更新指代信息。
        
        Args:
            entities: 实体列表。
        """
        # 常见的指代词
        pronouns = ["这个", "那个", "它", "他们", "她们", "它们", "此", "该"]
        
        for entity in entities:
            entity_type = getattr(entity, 'entity_type', None)
            entity_value = getattr(entity, 'value', None)
            
            if entity_type and entity_value:
                # 为每个实体设置指代
                for pronoun in pronouns:
                    self.references[pronoun] = entity_value
                
                # 设置类型相关的指代
                type_key = f"this_{entity_type}"
                self.references[type_key] = entity_value
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "dialogue_id": self.dialogue_id,
            "user_id": self.user_id,
            "state": self.state.value,
            "flow_stage": self.flow_stage.value,
            "current_intent": self.current_intent.value if self.current_intent else None,
            "filled_slots": self.filled_slots,
            "pending_slots": self.pending_slots,
            "history": [t.to_dict() for t in self.history],
            "variables": self.variables,
            "references": self.references,
            "start_time": self.start_time.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DialogueContext:
        """从字典创建对话上下文。
        
        Args:
            data: 字典数据。
            
        Returns:
            DialogueContext: 对话上下文实例。
        """
        context = cls()
        context.dialogue_id = data.get("dialogue_id", str(uuid4()))
        context.user_id = data.get("user_id")
        context.state = DialogueState(data.get("state", "new"))
        context.flow_stage = FlowStage(data.get("flow_stage", "greeting"))
        
        intent_str = data.get("current_intent")
        if intent_str:
            try:
                context.current_intent = IntentType(intent_str)
            except ValueError:
                context.current_intent = None
        
        context.filled_slots = data.get("filled_slots", {})
        context.pending_slots = data.get("pending_slots", [])
        context.variables = data.get("variables", {})
        context.references = data.get("references", {})
        context.metadata = data.get("metadata", {})
        
        # 恢复历史对话
        history_data = data.get("history", [])
        for turn_data in history_data:
            turn = DialogueTurn()
            turn.turn_id = turn_data.get("turn_id", str(uuid4()))
            turn.timestamp = datetime.fromisoformat(turn_data.get("timestamp", datetime.now().isoformat()))
            turn.user_input = turn_data.get("user_input", "")
            turn.system_response = turn_data.get("system_response", "")
            turn.slots = turn_data.get("slots", {})
            turn.dialogue_act = turn_data.get("dialogue_act", "")
            context.history.append(turn)
        
        # 恢复时间
        start_time_str = data.get("start_time")
        if start_time_str:
            context.start_time = datetime.fromisoformat(start_time_str)
        
        last_activity_str = data.get("last_activity")
        if last_activity_str:
            context.last_activity = datetime.fromisoformat(last_activity_str)
        
        return context


# 对话行为类型
class DialogueAct(str, Enum):
    """对话行为类型。"""
    
    # 用户行为
    USER_GREET = "user_greet"           # 用户问候
    USER_INFORM = "user_inform"         # 用户提供信息
    USER_REQUEST = "user_request"       # 用户请求
    USER_CONFIRM = "user_confirm"       # 用户确认
    USER_DENY = "user_deny"             # 用户否认
    USER_QUESTION = "user_question"     # 用户提问
    USER_COMPLAINT = "user_complaint"   # 用户投诉
    USER_THANKS = "user_thanks"         # 用户感谢
    USER_BYE = "user_bye"               # 用户告别
    
    # 系统行为
    SYS_GREET = "sys_greet"             # 系统问候
    SYS_REQUEST = "sys_request"         # 系统请求信息
    SYS_CONFIRM = "sys_confirm"         # 系统确认
    SYS_DENY = "sys_deny"               # 系统否认
    SYS_INFORM = "sys_inform"           # 系统提供信息
    SYS_SUGGEST = "sys_suggest"         # 系统建议
    SYS_APOLOGY = "sys_apology"         # 系统道歉
    SYS_EMPATHY = "sys_empathy"         # 系统共情
    SYS_BYE = "sys_bye"                 # 系统告别