"""MCP Tool: compare_documents

对比多个文档或 Chunk 的异同，支持并排展示和差异分析。

使用场景：
- 对比不同版本文档的差异
- 比较多个相关文档的侧重点
- 分析不同来源的信息一致性

使用方法:
    Tool name: compare_documents
    Input: {
        "chunk_ids": ["chunk_123", "chunk_456"],
        "comparison_type": "content"
    }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from mcp import types

if TYPE_CHECKING:
    from src.core.settings import Settings

logger = logging.getLogger(__name__)


# Tool metadata
TOOL_NAME = "compare_documents"
TOOL_DESCRIPTION = """对比多个文档或 Chunk 的异同。

支持功能：
- 并排展示多个文档内容
- 分析内容相似度和差异点
- 提取各自的关键信息

参数:
- chunk_ids: 要对比的 Chunk ID 列表
- comparison_type: 对比类型（content/similarity/keypoints）
- max_length: 每个文档的最大展示长度
"""

TOOL_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "chunk_ids": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": "要对比的 Chunk ID 列表。",
            "minItems": 2,
            "maxItems": 5,
        },
        "comparison_type": {
            "type": "string",
            "description": "对比类型。",
            "enum": ["content", "similarity", "keypoints", "all"],
            "default": "all",
        },
        "max_length": {
            "type": "integer",
            "description": "每个文档的最大展示长度（字符数）。",
            "default": 500,
            "minimum": 100,
            "maximum": 2000,
        },
    },
    "required": ["chunk_ids"],
}


class ComparisonType(str, Enum):
    """对比类型"""
    CONTENT = "content"  # 内容并排展示
    SIMILARITY = "similarity"  # 相似度分析
    KEYPOINTS = "keypoints"  # 关键点提取
    ALL = "all"  # 全部


@dataclass
class DocumentInfo:
    """文档信息"""
    chunk_id: str
    content: str
    source: str
    title: str
    score: Optional[float] = None


@dataclass
class ComparisonResult:
    """对比结果"""
    documents: List[DocumentInfo]
    similarity_matrix: List[List[float]]
    common_themes: List[str]
    unique_points: Dict[str, List[str]]
    summary: str


class CompareDocumentsTool:
    """文档对比工具"""
    
    def __init__(
        self,
        settings: Optional["Settings"] = None,
    ) -> None:
        self.settings = settings
    
    def compare(
        self,
        chunk_ids: List[str],
        comparison_type: str = "all",
        max_length: int = 500,
    ) -> ComparisonResult:
        """对比文档
        
        Args:
            chunk_ids: 要对比的 Chunk ID 列表
            comparison_type: 对比类型
            max_length: 最大展示长度
            
        Returns:
            ComparisonResult 对比结果
        """
        # 注意：实际实现需要从存储中加载文档
        # 这里提供框架实现
        documents = self._load_documents(chunk_ids)
        
        # 计算相似度矩阵
        similarity_matrix = self._calculate_similarity(documents)
        
        # 提取共同主题
        common_themes = self._extract_common_themes(documents)
        
        # 提取独特点
        unique_points = self._extract_unique_points(documents)
        
        # 生成总结
        summary = self._generate_summary(documents, common_themes, unique_points)
        
        return ComparisonResult(
            documents=documents,
            similarity_matrix=similarity_matrix,
            common_themes=common_themes,
            unique_points=unique_points,
            summary=summary,
        )
    
    def _load_documents(self, chunk_ids: List[str]) -> List[DocumentInfo]:
        """加载文档信息
        
        实际实现需要从 DocumentManager 或存储中加载
        """
        # 模拟实现 - 实际使用需要集成 DocumentManager
        documents = []
        for chunk_id in chunk_ids:
            documents.append(DocumentInfo(
                chunk_id=chunk_id,
                content=f"[文档内容：{chunk_id}]",
                source=f"source_{chunk_id}",
                title=f"文档 {chunk_id[-6:]}",
            ))
        return documents
    
    def _calculate_similarity(self, documents: List[DocumentInfo]) -> List[List[float]]:
        """计算相似度矩阵"""
        n = len(documents)
        matrix = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        
        # 简单实现：基于文本重叠计算相似度
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._text_similarity(
                    documents[i].content,
                    documents[j].content,
                )
                matrix[i][j] = sim
                matrix[j][i] = sim
        
        return matrix
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的相似度"""
        # 简单实现：Jaccard 相似度
        set1 = set(text1.lower().split())
        set2 = set(text2.lower().split())
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def _extract_common_themes(self, documents: List[DocumentInfo]) -> List[str]:
        """提取共同主题"""
        # 简单实现：返回占位符
        return ["共同主题分析需要 LLM 支持"]
    
    def _extract_unique_points(
        self,
        documents: List[DocumentInfo],
    ) -> Dict[str, List[str]]:
        """提取各文档的独特点"""
        unique = {}
        for doc in documents:
            unique[doc.chunk_id] = [f"{doc.title} 的独特内容需要 LLM 分析"]
        return unique
    
    def _generate_summary(
        self,
        documents: List[DocumentInfo],
        common_themes: List[str],
        unique_points: Dict[str, List[str]],
    ) -> str:
        """生成对比总结"""
        return f"已对比 {len(documents)} 个文档，发现 {len(common_themes)} 个共同主题。"


# 模块级工具实例
_tool_instance: Optional[CompareDocumentsTool] = None


def get_tool_instance() -> CompareDocumentsTool:
    """获取或创建工具实例"""
    global _tool_instance
    if _tool_instance is None:
        _tool_instance = CompareDocumentsTool()
    return _tool_instance


async def compare_documents_handler(
    chunk_ids: List[str],
    comparison_type: str = "all",
    max_length: int = 500,
) -> types.CallToolResult:
    """MCP 工具处理函数"""
    tool = get_tool_instance()
    
    try:
        # 验证输入
        if len(chunk_ids) < 2:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text="❌ 错误：至少需要提供 2 个 Chunk ID 进行对比",
                    )
                ],
                isError=True,
            )
        
        if len(chunk_ids) > 5:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text="❌ 错误：最多支持 5 个 Chunk ID 对比",
                    )
                ],
                isError=True,
            )
        
        result = tool.compare(
            chunk_ids=chunk_ids,
            comparison_type=comparison_type,
            max_length=max_length,
        )
        
        # 构建响应内容
        content = f"## 文档对比分析\n\n"
        content += f"**对比文档数:** {len(result.documents)}\n\n"
        
        # 内容并排展示
        if comparison_type in ["content", "all"]:
            content += f"### 📄 文档内容\n\n"
            for i, doc in enumerate(result.documents, 1):
                content_preview = doc.content[:max_length]
                if len(doc.content) > max_length:
                    content_preview += "..."
                content += f"**{i}. {doc.title}** (`{doc.chunk_id[:12]}...`)\n"
                content += f"> {content_preview}\n\n"
        
        # 相似度矩阵
        if comparison_type in ["similarity", "all"]:
            content += f"### 📊 相似度矩阵\n\n"
            content += "| | " + " | ".join(f"D{i+1}" for i in range(len(result.documents))) + " |\n"
            content += "|" + "|".join(["---"] * (len(result.documents) + 1)) + "|\n"
            for i, row in enumerate(result.similarity_matrix):
                content += f"| D{i+1} | " + " | ".join(f"{s:.2f}" for s in row) + " |\n"
            content += "\n"
        
        # 共同主题
        if comparison_type in ["keypoints", "all"]:
            content += f"### 🔍 共同主题\n\n"
            for theme in result.common_themes:
                content += f"- {theme}\n"
            content += "\n"
        
        # 总结
        content += f"### 📝 分析总结\n\n{result.summary}\n"
        
        return types.CallToolResult(
            content=[
                types.TextContent(type="text", text=content)
            ],
            isError=False,
        )
        
    except Exception as e:
        logger.exception(f"compare_documents handler error: {e}")
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"对比失败：{e}",
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
        handler=compare_documents_handler,
    )
    logger.info(f"Registered MCP tool: {TOOL_NAME}")