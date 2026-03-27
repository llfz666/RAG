"""MCP Tool: suggest_related_questions

基于用户当前查询，生成相关的后续问题建议。

使用场景：
- 帮助用户发现未考虑到的方面
- 引导用户深入探索主题
- 提高知识库利用率

使用方法:
    Tool name: suggest_related_questions
    Input: {"query": "如何配置 Azure 连接？", "num_suggestions": 5}
    Output: 返回 5 个相关问题建议
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from mcp import types

if TYPE_CHECKING:
    from src.core.settings import Settings

logger = logging.getLogger(__name__)


# Tool metadata
TOOL_NAME = "suggest_related_questions"
TOOL_DESCRIPTION = """基于用户当前查询，生成相关的后续问题建议。

这有助于：
- 帮助用户发现未考虑到的方面
- 引导用户深入探索主题
- 提高知识库利用率

参数:
- query: 用户当前的查询
- num_suggestions: 生成建议的数量（默认 5，最多 10）
- category: 可选，限制建议的问题类别
"""

TOOL_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "用户当前的查询语句。",
        },
        "num_suggestions": {
            "type": "integer",
            "description": "生成建议的数量。",
            "default": 5,
            "minimum": 1,
            "maximum": 10,
        },
        "category": {
            "type": "string",
            "description": "可选，限制建议的问题类别。",
            "enum": ["basic", "advanced", "troubleshooting", "comparison", "all"],
            "default": "all",
        },
    },
    "required": ["query"],
}


@dataclass
class RelatedQuestion:
    """相关问题"""
    question: str
    category: str
    relevance_score: float
    reasoning: str


@dataclass
class SuggestionResult:
    """推荐结果"""
    original_query: str
    suggestions: List[RelatedQuestion]
    

# 问题模板库
QUESTION_TEMPLATES = {
    # 基础类问题
    "basic": [
        "什么是{topic}？",
        "{topic}的主要作用是什么？",
        "如何使用{topic}？",
        "{topic}的基本配置步骤是什么？",
        "{topic}支持哪些功能？",
    ],
    # 进阶类问题
    "advanced": [
        "{topic}的最佳实践是什么？",
        "如何优化{topic}的性能？",
        "{topic}与其他方案相比有什么优势？",
        "{topic}的高级配置选项有哪些？",
        "如何监控{topic}的运行状态？",
    ],
    # 故障排除类
    "troubleshooting": [
        "{topic}常见错误有哪些？",
        "如何解决{topic}连接失败的问题？",
        "{topic}性能下降如何排查？",
        "{topic}报错时如何定位问题？",
        "{topic}的日志在哪里查看？",
    ],
    # 比较类问题
    "comparison": [
        "{topic}与其他方案有什么区别？",
        "{topic}和竞品相比有什么优劣？",
        "在什么场景下应该选择{topic}？",
        "{topic}的替代方案有哪些？",
        "如何选择{topic}的不同版本？",
    ],
}

# 关键词到主题的映射
KEYWORD_TOPIC_MAP = {
    # Azure 相关
    "azure": "Azure 服务",
    "连接": "连接配置",
    "配置": "配置方法",
    "api": "API 调用",
    "密钥": "认证密钥",
    # RAG 相关
    "检索": "检索策略",
    "embedding": "Embedding 模型",
    "rerank": "重排序",
    "chunk": "文本切分",
    # 通用
    "错误": "错误处理",
    "问题": "问题排查",
    "优化": "性能优化",
    "部署": "部署方案",
}


class SuggestRelatedQuestionsTool:
    """相关问题推荐工具"""
    
    def __init__(
        self,
        settings: Optional["Settings"] = None,
    ) -> None:
        self.settings = settings
    
    def suggest(
        self,
        query: str,
        num_suggestions: int = 5,
        category: str = "all",
    ) -> SuggestionResult:
        """生成相关问题建议
        
        Args:
            query: 用户当前查询
            num_suggestions: 建议数量
            category: 问题类别
            
        Returns:
            SuggestionResult 推荐结果
        """
        # 提取查询中的主题关键词
        topic = self._extract_topic(query)
        
        # 确定要使用的类别
        if category == "all":
            categories = list(QUESTION_TEMPLATES.keys())
        else:
            categories = [category]
        
        # 生成候选问题
        candidates: List[RelatedQuestion] = []
        
        for cat in categories:
            templates = QUESTION_TEMPLATES.get(cat, [])
            for template in templates:
                question = template.format(topic=topic)
                relevance = self._calculate_relevance(query, question)
                reasoning = self._generate_reasoning(cat, query, question)
                
                candidates.append(RelatedQuestion(
                    question=question,
                    category=cat,
                    relevance_score=relevance,
                    reasoning=reasoning,
                ))
        
        # 按相关性排序并去重
        seen_questions = set()
        unique_candidates = []
        for c in sorted(candidates, key=lambda x: x.relevance_score, reverse=True):
            if c.question not in seen_questions:
                seen_questions.add(c.question)
                unique_candidates.append(c)
        
        # 返回指定数量的建议
        suggestions = unique_candidates[:num_suggestions]
        
        logger.info(
            f"Generated {len(suggestions)} related questions for query: {query[:50]}..."
        )
        
        return SuggestionResult(
            original_query=query,
            suggestions=suggestions,
        )
    
    def _extract_topic(self, query: str) -> str:
        """从查询中提取主题"""
        # 简单实现：查找关键词
        for keyword, topic in KEYWORD_TOPIC_MAP.items():
            if keyword.lower() in query.lower():
                return topic
        
        # 如果没有匹配，返回查询的核心部分
        # 去除常见疑问词
        stop_words = [
            "如何", "怎么", "什么", "为什么", "哪些", "多少",
            "how", "what", "why", "which", "when", "where",
        ]
        result = query
        for word in stop_words:
            result = result.replace(word, "")
        
        return result.strip()[:20] or "相关内容"
    
    def _calculate_relevance(self, query: str, question: str) -> float:
        """计算问题与原始查询的相关性"""
        # 简单实现：基于词重叠
        query_words = set(query.lower())
        question_words = set(question.lower())
        
        intersection = query_words & question_words
        union = query_words | question_words
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _generate_reasoning(
        self,
        category: str,
        query: str,
        question: str,
    ) -> str:
        """生成推荐理由"""
        category_reasons = {
            "basic": "帮助您理解基础概念和用法",
            "advanced": "深入探索高级功能和最佳实践",
            "troubleshooting": "解决可能遇到的常见问题",
            "comparison": "帮助您做出更好的技术选型",
        }
        
        return category_reasons.get(category, "扩展您的知识探索")


# 模块级工具实例
_tool_instance: Optional[SuggestRelatedQuestionsTool] = None


def get_tool_instance() -> SuggestRelatedQuestionsTool:
    """获取或创建工具实例"""
    global _tool_instance
    if _tool_instance is None:
        _tool_instance = SuggestRelatedQuestionsTool()
    return _tool_instance


async def suggest_related_questions_handler(
    query: str,
    num_suggestions: int = 5,
    category: str = "all",
) -> types.CallToolResult:
    """MCP 工具处理函数"""
    tool = get_tool_instance()
    
    try:
        result = tool.suggest(
            query=query,
            num_suggestions=num_suggestions,
            category=category,
        )
        
        content = f"## 相关问题推荐\n\n"
        content += f"**原始查询:** `{result.original_query}`\n\n"
        content += f"以下是您可能感兴趣的相关问题：\n\n"
        
        for i, suggestion in enumerate(result.suggestions, 1):
            category_label = {
                "basic": "📘 基础",
                "advanced": "📚 进阶",
                "troubleshooting": "🔧 排障",
                "comparison": "⚖️ 对比",
            }.get(suggestion.category, "📌")
            
            content += f"{i}. {category_label} **{suggestion.question}**\n"
            content += f"   _{suggestion.reasoning}_\n\n"
        
        return types.CallToolResult(
            content=[
                types.TextContent(type="text", text=content)
            ],
            isError=False,
        )
        
    except Exception as e:
        logger.exception(f"suggest_related_questions handler error: {e}")
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"生成失败：{e}",
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
        handler=suggest_related_questions_handler,
    )
    logger.info(f"Registered MCP tool: {TOOL_NAME}")