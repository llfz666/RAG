"""情感分析模块。

用于广告公司客服场景的情感理解、情绪检测和共情回应。
"""

from agent.sentiment.models import (
    SentimentType,
    EmotionType,
    UrgencyLevel,
    SentimentResult,
    EMOTION_RESPONSE_STRATEGIES,
    SENTIMENT_RESPONSE_TONES,
    URGENCY_RESPONSE_TIMES,
)
from agent.sentiment.analyzer import SentimentAnalyzer

__all__ = [
    "SentimentType",
    "EmotionType",
    "UrgencyLevel",
    "SentimentResult",
    "EMOTION_RESPONSE_STRATEGIES",
    "SENTIMENT_RESPONSE_TONES",
    "URGENCY_RESPONSE_TIMES",
    "SentimentAnalyzer",
]