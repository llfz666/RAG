"""情感分析模块 - 数据模型定义。

用于广告公司客服场景的情感理解、情绪检测和共情回应。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SentimentType(str, Enum):
    """情感类型。"""
    
    POSITIVE = "positive"  # 积极
    NEUTRAL = "neutral"    # 中性
    NEGATIVE = "negative"  # 消极


class EmotionType(str, Enum):
    """情绪类型（基于 Ekman 六种基本情绪扩展）。"""
    
    JOY = "joy"        # 高兴
    TRUST = "trust"    # 信任
    FEAR = "fear"      # 恐惧/担忧
    SURPRISE = "surprise"  # 惊讶
    SADNESS = "sadness"    # 悲伤/失望
    DISGUST = "disgust"    # 厌恶
    ANGER = "anger"    # 愤怒
    ANTICIPATION = "anticipation"  # 期待
    CONFUSED = "confused"  # 困惑
    URGENT = "urgent"    # 急切
    FRUSTRATED = "frustrated"  # 沮丧


class UrgencyLevel(str, Enum):
    """紧急程度。"""
    
    LOW = "low"        # 低
    MEDIUM = "medium"  # 中
    HIGH = "high"      # 高
    CRITICAL = "critical"  # 紧急


@dataclass
class SentimentResult:
    """情感分析结果。"""
    
    # 总体情感
    sentiment: SentimentType = SentimentType.NEUTRAL
    
    # 情感强度 (0-1)
    sentiment_intensity: float = 0.0
    
    # 主要情绪
    primary_emotion: Optional[EmotionType] = None
    
    # 情绪强度 (0-1)
    emotion_intensity: float = 0.0
    
    # 次要情绪（可选）
    secondary_emotions: list[tuple[EmotionType, float]] = field(default_factory=list)
    
    # 紧急程度
    urgency_level: UrgencyLevel = UrgencyLevel.MEDIUM
    
    # 原始文本
    raw_text: str = ""
    
    # 置信度
    confidence: float = 0.0
    
    # 是否需要共情回应
    needs_empathy: bool = False
    
    # 建议的回应策略
    response_strategy: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "sentiment": self.sentiment.value,
            "sentiment_intensity": self.sentiment_intensity,
            "primary_emotion": self.primary_emotion.value if self.primary_emotion else None,
            "emotion_intensity": self.emotion_intensity,
            "secondary_emotions": [
                (e.value, i) for e, i in self.secondary_emotions
            ],
            "urgency_level": self.urgency_level.value,
            "raw_text": self.raw_text,
            "confidence": self.confidence,
            "needs_empathy": self.needs_empathy,
            "response_strategy": self.response_strategy,
        }


# 情绪到回应策略的映射
EMOTION_RESPONSE_STRATEGIES: dict[EmotionType, str] = {
    EmotionType.JOY: "友好回应，强化积极体验",
    EmotionType.TRUST: "保持专业，巩固信任关系",
    EmotionType.FEAR: "安抚情绪，提供保障信息",
    EmotionType.SURPRISE: "解释说明，消除疑虑",
    EmotionType.SADNESS: "表达理解，提供解决方案",
    EmotionType.DISGUST: "道歉并改进，展示专业态度",
    EmotionType.ANGER: "冷静处理，优先安抚情绪",
    EmotionType.ANTICIPATION: "积极回应，提供明确时间线",
    EmotionType.CONFUSED: "耐心解释，简化信息",
    EmotionType.URGENT: "快速响应，明确处理优先级",
    EmotionType.FRUSTRATED: "表达理解，提供具体解决方案",
}

# 情感到回应语气的映射
SENTIMENT_RESPONSE_TONES: dict[SentimentType, str] = {
    SentimentType.POSITIVE: "热情友好",
    SentimentType.NEUTRAL: "专业礼貌",
    SentimentType.NEGATIVE: "诚恳道歉 + 解决方案",
}

# 紧急程度响应时间建议
URGENCY_RESPONSE_TIMES: dict[UrgencyLevel, str] = {
    UrgencyLevel.LOW: "24 小时内回复",
    UrgencyLevel.MEDIUM: "2-4 小时内回复",
    UrgencyLevel.HIGH: "30 分钟内回复",
    UrgencyLevel.CRITICAL: "立即处理，优先响应",
}