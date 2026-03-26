"""对话管理模块。

用于对话状态追踪、上下文管理和多轮对话流程控制。
"""

from agent.dialogue.models import (
    DialogueState,
    FlowStage,
    DialogueTurn,
    DialogueContext,
    DialogueAct,
)
from agent.dialogue.manager import DialogueManager

__all__ = [
    "DialogueState",
    "FlowStage",
    "DialogueTurn",
    "DialogueContext",
    "DialogueAct",
    "DialogueManager",
]