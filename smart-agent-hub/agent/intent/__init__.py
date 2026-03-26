"""意图识别模块。

针对广告公司客服场景的意图分类、实体识别和槽位填充。
"""

from agent.intent.models import (
    IntentType,
    EntityType,
    Entity,
    IntentResult,
    INTENT_SLOTS,
    INTENT_DESCRIPTIONS,
)
from agent.intent.classifier import IntentClassifier

__all__ = [
    "IntentType",
    "EntityType",
    "Entity",
    "IntentResult",
    "INTENT_SLOTS",
    "INTENT_DESCRIPTIONS",
    "IntentClassifier",
]