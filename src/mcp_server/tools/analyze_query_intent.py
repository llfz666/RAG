"""MCP Tool: analyze_query_intent

分析用户查询的意图类型，帮助后续检索策略的选择。

支持的意图类型：
- FACTUAL: 事实性查询（寻求具体信息）
- COMPARATIVE: 比较类查询（对比多个事物）
- PROCEDURAL: 流程类查询（如何做某事）
- EXPLANATORY: 解释类查询（为什么/原理）
- TROUBLESHOOTING: 故障排除类查询
- DEFINITION: 定义类查询（是什么）

使用方法:
    Tool name: analyze_query_intent
    Input: {"query": "如何配置 Azure 连接？"}
    Output: {"intent": "PROCEDURAL", "confidence": 0.9, ...}
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, TYPE_CHECKING

from mcp import types

if TYPE_CHECKING:
    from src.core.settings import Settings

logger = logging.getLogger(__name__)


# Tool metadata
TOOL_NAME = "analyze_query_intent"
TOOL_DESCRIPTION = """分析用户查询的意图类型。

支持的意图类型：
- FACTUAL: 事实性查询（寻求具体信息、数据、配置等）
- COMPARATIVE: 比较类查询（对比多个事物、方案选型等）
- PROCEDURAL: 流程类查询（如何做某事、步骤、指南等）
- EXPLANATORY: 解释类查询（为什么、原理、原因等）
- TROUBLESHOOTING: 故障排除类查询（错误、失败、问题解决等）
- DEFINITION: 定义类查询（是什么、概念解释等）

返回结果包含意图类型、置信度和检索策略建议。
"""

TOOL_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "要分析的用户查询语句。",
        },
        "language": {
            "type": "string",
            "description": "查询语言，用于更精确的意图识别。",
            "enum": ["zh", "en", "auto"],
            "default": "auto",
        },
    },
    "required": ["query"],
}


class QueryIntent(str, Enum):
    """查询意图类型"""
    FACTUAL = "FACTUAL"  # 事实性查询
    COMPARATIVE = "COMPARATIVE"  # 比较类查询
    PROCEDURAL = "PROCEDURAL"  # 流程类查询
    EXPLANATORY = "EXPLANATORY"  # 解释类查询
    TROUBLESHOOTING = "TROUBLESHOOTING"  # 故障排除
    DEFINITION = "DEFINITION"  # 定义类查询
    UNKNOWN = "UNKNOWN"  # 未知


@dataclass
class IntentAnalysisResult:
    """意图分析结果"""
    intent: QueryIntent
    confidence: float
    keywords: list[str]
    suggested_top_k: int
    suggested_rerank: bool
    reasoning: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "keywords": self.keywords,
            "suggested_top_k": self.suggested_top_k,
            "suggested_rerank": self.suggested_rerank,
            "reasoning": self.reasoning,
        }


# 意图识别关键词模式（中英文）
INTENT_PATTERNS = {
    QueryIntent.FACTUAL: {
        "zh": [
            r"什么 (是 | 叫 | 做)", r"哪些", r"多少", r"怎么查", r"在哪里",
            r"配置", r"设置", r"参数", r"地址", r"密钥", r"API",
        ],
        "en": [
            r"what (is|are|was|were)", r"which", r"how many", r"how much",
            r"config", r"setting", r"parameter", r"address", r"key", r"API",
        ],
    },
    QueryIntent.COMPARATIVE: {
        "zh": [
            r"哪个 (更 | 好)", r"对比", r"比较", r"区别", r"差异",
            r"vs", r" versus", r"和.*有什么 (不同 | 区别)", r"选.*还是",
        ],
        "en": [
            r"which (is )?(better|more|faster)", r"compare", r"comparison",
            r"difference", r"vs", r"versus", r"between.*and",
        ],
    },
    QueryIntent.PROCEDURAL: {
        "zh": [
            r"怎么 (做 | 弄 | 搞 | 配置 | 设置)", r"如何", r"步骤", r"流程",
            r"教程", r"指南", r"手册", r"安装", r"部署", r"搭建",
        ],
        "en": [
            r"how to", r"how do i", r"steps", r"process", r"guide",
            r"tutorial", r"install", r"deploy", r"setup", r"configure",
        ],
    },
    QueryIntent.EXPLANATORY: {
        "zh": [
            r"为什么", r"为啥", r"原因", r"原理", r"机制", r"原则",
            r"解释", r"说明.*是.*原因", r"基于什么",
        ],
        "en": [
            r"why", r"reason", r"principle", r"mechanism", r"explain",
            r"based on", r"how.*work",
        ],
    },
    QueryIntent.TROUBLESHOOTING: {
        "zh": [
            r"错误", r"失败", r"问题", r"报错", r"异常", r"解决",
            r"fix", r"debug", r"不能", r"无法", r"不行",
        ],
        "en": [
            r"error", r"failed", r"fail", r"issue", r"problem",
            r"exception", r"fix", r"debug", r"cannot", r"unable to",
        ],
    },
    QueryIntent.DEFINITION: {
        "zh": [
            r"什么是", r".*是什么", r"定义", r"概念", r"含义", r"意思",
        ],
        "en": [
            r"what is", r"what are", r"define", r"definition", r"meaning",
        ],
    },
}


@dataclass
class QueryIntentConfig:
    """配置"""
    default_top_k_map: Dict[QueryIntent, int] = None
    default_rerank_map: Dict[QueryIntent, bool] = None
    
    def __post_init__(self):
        if self.default_top_k_map is None:
            self.default_top_k_map = {
                QueryIntent.FACTUAL: 5,
                QueryIntent.COMPARATIVE: 10,  # 比较类需要更多结果
                QueryIntent.PROCEDURAL: 5,
                QueryIntent.EXPLANATORY: 7,
                QueryIntent.TROUBLESHOOTING: 5,
                QueryIntent.DEFINITION: 3,
                QueryIntent.UNKNOWN: 5,
            }
        if self.default_rerank_map is None:
            self.default_rerank_map = {
                QueryIntent.FACTUAL: True,
                QueryIntent.COMPARATIVE: True,  # 比较类需要精排
                QueryIntent.PROCEDURAL: False,
                QueryIntent.EXPLANATORY: True,
                QueryIntent.TROUBLESHOOTING: True,
                QueryIntent.DEFINITION: False,
                QueryIntent.UNKNOWN: True,
            }


class AnalyzeQueryIntentTool:
    """查询意图分析工具"""
    
    def __init__(
        self,
        settings: Optional["Settings"] = None,
        config: Optional[QueryIntentConfig] = None,
    ) -> None:
        self.settings = settings
        self.config = config or QueryIntentConfig()
    
    def analyze(self, query: str, language: str = "auto") -> IntentAnalysisResult:
        """分析查询意图
        
        Args:
            query: 用户查询语句
            language: 语言标识，"auto" 为自动检测
            
        Returns:
            IntentAnalysisResult 意图分析结果
        """
        # 自动检测语言
        if language == "auto":
            language = self._detect_language(query)
        
        # 计算各意图类型的得分
        intent_scores: Dict[QueryIntent, float] = {}
        intent_keywords: Dict[QueryIntent, list[str]] = {}
        
        for intent, patterns_by_lang in INTENT_PATTERNS.items():
            patterns = patterns_by_lang.get(language, patterns_by_lang.get("en", []))
            score = 0.0
            matched_keywords = []
            
            for pattern in patterns:
                matches = re.findall(pattern, query, re.IGNORECASE)
                if matches:
                    score += len(matches) * 0.3
                    matched_keywords.extend(
                        m if isinstance(m, str) else str(m)
                        for m in matches
                    )
            
            intent_scores[intent] = min(score, 1.0)  # 上限 1.0
            intent_keywords[intent] = matched_keywords
        
        # 选择得分最高的意图
        best_intent = max(intent_scores.keys(), key=lambda x: intent_scores[x])
        confidence = intent_scores[best_intent]
        
        # 如果所有得分都很低，标记为未知
        if confidence < 0.3:
            best_intent = QueryIntent.UNKNOWN
            confidence = 0.5  # 默认置信度
        
        # 生成分析结果
        result = IntentAnalysisResult(
            intent=best_intent,
            confidence=confidence,
            keywords=intent_keywords.get(best_intent, []),
            suggested_top_k=self.config.default_top_k_map.get(best_intent, 5),
            suggested_rerank=self.config.default_rerank_map.get(best_intent, True),
            reasoning=self._generate_reasoning(best_intent, confidence, query),
        )
        
        logger.info(
            f"Intent analysis: query='{query[:50]}...', "
            f"intent={result.intent}, confidence={result.confidence:.2f}"
        )
        
        return result
    
    def _detect_language(self, query: str) -> str:
        """简单检测查询语言"""
        # 检测中文字符比例
        chinese_chars = sum(1 for c in query if '\u4e00' <= c <= '\u9fff')
        chinese_ratio = chinese_chars / max(len(query), 1)
        
        return "zh" if chinese_ratio > 0.3 else "en"
    
    def _generate_reasoning(
        self,
        intent: QueryIntent,
        confidence: float,
        query: str,
    ) -> str:
        """生成推理说明"""
        intent_descriptions = {
            QueryIntent.FACTUAL: "事实性查询，寻求具体信息、数据或配置详情",
            QueryIntent.COMPARATIVE: "比较类查询，需要对比多个事物或方案",
            QueryIntent.PROCEDURAL: "流程类查询，需要了解步骤、方法或指南",
            QueryIntent.EXPLANATORY: "解释类查询，需要理解原理或原因",
            QueryIntent.TROUBLESHOOTING: "故障排除类查询，需要解决错误或问题",
            QueryIntent.DEFINITION: "定义类查询，需要概念解释或术语说明",
            QueryIntent.UNKNOWN: "未知类型，使用默认检索策略",
        }
        
        reasoning = f"识别为{intent_descriptions.get(intent, '未知类型')}。"
        
        if confidence >= 0.8:
            reasoning += f"置信度高 ({confidence:.0%})。"
        elif confidence >= 0.5:
            reasoning += f"置信度中等 ({confidence:.0%})。"
        else:
            reasoning += f"置信度较低 ({confidence:.0%})，建议结合用户反馈优化。"
        
        return reasoning


# 模块级工具实例
_tool_instance: Optional[AnalyzeQueryIntentTool] = None


def get_tool_instance() -> AnalyzeQueryIntentTool:
    """获取或创建工具实例"""
    global _tool_instance
    if _tool_instance is None:
        _tool_instance = AnalyzeQueryIntentTool()
    return _tool_instance


async def analyze_query_intent_handler(
    query: str,
    language: str = "auto",
) -> types.CallToolResult:
    """MCP 工具处理函数"""
    tool = get_tool_instance()
    
    try:
        result = tool.analyze(query=query, language=language)
        
        content = f"## 查询意图分析\n\n"
        content += f"**查询:** `{query}`\n\n"
        content += f"| 属性 | 值 |\n"
        content += f"|------|-----|\n"
        content += f"| 意图类型 | **{result.intent.value}** |\n"
        content += f"| 置信度 | {result.confidence:.0%} |\n"
        content += f"| 建议 Top-K | {result.suggested_top_k} |\n"
        content += f"| 建议重排 | {'是' if result.suggested_rerank else '否'} |\n"
        content += f"| 关键词 | {', '.join(result.keywords) or '无'} |\n\n"
        content += f"**分析说明:** {result.reasoning}\n"
        
        return types.CallToolResult(
            content=[
                types.TextContent(type="text", text=content)
            ],
            isError=False,
        )
        
    except Exception as e:
        logger.exception(f"analyze_query_intent handler error: {e}")
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"分析失败：{e}",
                )
            ],
            isError=True,
        )


def register_tool(protocol_handler) -> None:
    """注册工具"""
    protocol_handler.register_tool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        input_schema=TOOL_INPUT_SCHEMA,
        handler=analyze_query_intent_handler,
    )
    logger.info(f"Registered MCP tool: {TOOL_NAME}")