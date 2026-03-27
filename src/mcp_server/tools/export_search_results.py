"""MCP Tool: export_search_results

导出检索结果为多种格式（Markdown、JSON、CSV），支持离线保存和分享。

使用场景：
- 将检索结果保存为文档
- 导出用于后续分析
- 分享给团队成员

使用方法:
    Tool name: export_search_results
    Input: {
        "query": "Azure 配置",
        "format": "markdown",
        "top_k": 5
    }
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from mcp import types

if TYPE_CHECKING:
    from src.core.settings import Settings
    from src.core.types import RetrievalResult

logger = logging.getLogger(__name__)


# Tool metadata
TOOL_NAME = "export_search_results"
TOOL_DESCRIPTION = """导出检索结果为多种格式。

支持的格式：
- markdown: 格式化的 Markdown 文档
- json: 结构化 JSON 数据
- csv: 表格格式 CSV 文件

参数:
- query: 检索查询
- format: 导出格式（markdown/json/csv）
- top_k: 导出结果数量
- collection: 可选的集合名称
"""

TOOL_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "检索查询语句。",
        },
        "format": {
            "type": "string",
            "description": "导出格式。",
            "enum": ["markdown", "json", "csv"],
            "default": "markdown",
        },
        "top_k": {
            "type": "integer",
            "description": "导出结果数量。",
            "default": 5,
            "minimum": 1,
            "maximum": 50,
        },
        "collection": {
            "type": "string",
            "description": "可选的集合名称。",
        },
        "include_metadata": {
            "type": "boolean",
            "description": "是否包含元数据信息。",
            "default": True,
        },
    },
    "required": ["query", "format"],
}


class ExportFormat(str, Enum):
    """导出格式"""
    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"


@dataclass
class ExportResult:
    """导出结果"""
    content: str
    format: ExportFormat
    item_count: int
    file_name: str


class ExportSearchResultsTool:
    """检索结果导出工具"""
    
    def __init__(
        self,
        settings: Optional["Settings"] = None,
    ) -> None:
        self.settings = settings
    
    def export(
        self,
        query: str,
        format: str,
        results: List["RetrievalResult"],
        include_metadata: bool = True,
    ) -> ExportResult:
        """导出检索结果
        
        Args:
            query: 原始查询
            format: 导出格式
            results: 检索结果列表
            include_metadata: 是否包含元数据
            
        Returns:
            ExportResult 导出结果
        """
        export_format = ExportFormat(format.lower())
        
        if export_format == ExportFormat.MARKDOWN:
            content = self._export_markdown(query, results, include_metadata)
            file_name = f"search_results_{query[:20].replace(' ', '_')}.md"
        elif export_format == ExportFormat.JSON:
            content = self._export_json(query, results, include_metadata)
            file_name = f"search_results_{query[:20].replace(' ', '_')}.json"
        elif export_format == ExportFormat.CSV:
            content = self._export_csv(query, results, include_metadata)
            file_name = f"search_results_{query[:20].replace(' ', '_')}.csv"
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return ExportResult(
            content=content,
            format=export_format,
            item_count=len(results),
            file_name=file_name,
        )
    
    def _export_markdown(
        self,
        query: str,
        results: List["RetrievalResult"],
        include_metadata: bool,
    ) -> str:
        """导出为 Markdown 格式"""
        md = f"# 检索结果导出\n\n"
        md += f"**查询:** {query}\n"
        md += f"**结果数量:** {len(results)}\n\n"
        md += f"---\n\n"
        
        for i, result in enumerate(results, 1):
            score = getattr(result, 'score', 'N/A')
            md += f"## {i}. 结果 #{i}\n\n"
            md += f"**相关性分数:** {score}\n\n"
            
            if include_metadata and hasattr(result, 'metadata') and result.metadata:
                md += "**元数据:**\n"
                for key, value in result.metadata.items():
                    md += f"- {key}: {value}\n"
                md += "\n"
            
            md += f"**内容:**\n\n"
            md += f"> {result.text or '无内容'}\n\n"
            md += f"---\n\n"
        
        md += f"\n*导出时间：{self._get_timestamp()}*\n"
        return md
    
    def _export_json(
        self,
        query: str,
        results: List["RetrievalResult"],
        include_metadata: bool,
    ) -> str:
        """导出为 JSON 格式"""
        data = {
            "query": query,
            "export_time": self._get_timestamp(),
            "result_count": len(results),
            "results": [],
        }
        
        for result in results:
            item = {
                "text": result.text,
                "score": getattr(result, 'score', None),
            }
            
            if include_metadata and hasattr(result, 'metadata'):
                item["metadata"] = result.metadata or {}
            
            data["results"].append(item)
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def _export_csv(
        self,
        query: str,
        results: List["RetrievalResult"],
        include_metadata: bool,
    ) -> str:
        """导出为 CSV 格式"""
        output = io.StringIO()
        
        # 定义列
        fieldnames = ["rank", "score", "text", "source", "title"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for i, result in enumerate(results, 1):
            row = {
                "rank": i,
                "score": getattr(result, 'score', ''),
                "text": (result.text or '').replace('\n', ' ')[:500],  # 限制长度
                "source": result.metadata.get('source_path', '') if hasattr(result, 'metadata') and result.metadata else '',
                "title": result.metadata.get('title', '') if hasattr(result, 'metadata') and result.metadata else '',
            }
            writer.writerow(row)
        
        return output.getvalue()
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 模块级工具实例
_tool_instance: Optional[ExportSearchResultsTool] = None


def get_tool_instance() -> ExportSearchResultsTool:
    """获取或创建工具实例"""
    global _tool_instance
    if _tool_instance is None:
        _tool_instance = ExportSearchResultsTool()
    return _tool_instance


async def export_search_results_handler(
    query: str,
    format: str,
    top_k: int = 5,
    collection: Optional[str] = None,
    include_metadata: bool = True,
) -> types.CallToolResult:
    """MCP 工具处理函数
    
    注意：此工具需要与 query_knowledge_hub 配合使用。
    实际使用时，应该先执行检索，然后导出结果。
    这里提供一个示例实现。
    """
    # 由于此工具需要访问检索结果，我们提供一个模拟实现
    # 实际使用时应该与 query_knowledge_hub 集成
    
    content = f"## 检索结果导出\n\n"
    content += f"**查询:** `{query}`\n"
    content += f"**格式:** `{format}`\n"
    content += f"**数量:** `{top_k}`\n"
    content += f"**集合:** `{collection or 'default'}`\n\n"
    
    content += f"### 使用说明\n\n"
    content += f"此工具用于导出检索结果。\n\n"
    content += f"**导出格式说明:**\n"
    content += f"- **Markdown**: 格式化的文档，适合阅读和分享\n"
    content += f"- **JSON**: 结构化数据，适合程序处理\n"
    content += f"- **CSV**: 表格格式，适合导入 Excel 等工具\n\n"
    
    content += f"### 示例\n\n"
    content += f"```python\n"
    content += f"# 使用示例\n"
    content += f"from src.mcp_server.tools.export_search_results import get_tool_instance\n"
    content += f"\n"
    content += f"tool = get_tool_instance()\n"
    content += f"# 需要先获取检索结果\n"
    content += f"# result = tool.export(query='...', format='markdown', results=search_results)\n"
    content += f"```\n"
    
    return types.CallToolResult(
        content=[
            types.TextContent(type="text", text=content)
        ],
        isError=False,
    )


def register_tool(protocol_handler) -> None:
    """注册工具"""
    protocol_handler.register_tool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        input_schema=TOOL_INPUT_SCHEMA,
        handler=export_search_results_handler,
    )
    logger.info(f"Registered MCP tool: {TOOL_NAME}")