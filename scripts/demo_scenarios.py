#!/usr/bin/env python3
"""
Demo 场景脚本

展示 RAG 系统和 MCP 工具的各种使用场景，适合面试演示和测试。

使用方法:
    python scripts/demo_scenarios.py

场景列表:
    1. 基础检索演示
    2. 查询意图分析
    3. 相关问题推荐
    4. 文档对比分析
    5. 结果导出功能
    6. 完整工作流演示
"""

import asyncio
import json
import sys
from typing import List, Dict, Any


# 颜色输出
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(title: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}\n")


def print_step(step: str, content: str):
    print(f"{Colors.YELLOW}[{step}]{Colors.END} {content}")


def print_result(content: str):
    print(f"{Colors.GREEN}→ {content}{Colors.END}")


def print_error(content: str):
    print(f"{Colors.RED}✗ {content}{Colors.END}")


# ==================== 场景 1: 基础检索演示 ====================

def demo_basic_search():
    """演示基础检索功能"""
    print_header("场景 1: 基础检索演示")
    
    print_step("1", "用户查询：'如何配置 Azure OpenAI 连接？'")
    print_result("调用 query_knowledge_hub 工具...")
    
    # 模拟检索结果
    mock_results = {
        "query": "如何配置 Azure OpenAI 连接？",
        "results": [
            {
                "chunk_id": "chunk_abc123",
                "title": "Azure OpenAI 服务配置指南",
                "score": 0.92,
                "content": "配置 Azure OpenAI 需要以下步骤：1. 在 Azure 门户创建资源 2. 获取 API Key 和 Endpoint 3. 配置环境变量..."
            },
            {
                "chunk_id": "chunk_def456",
                "title": "API 密钥管理最佳实践",
                "score": 0.85,
                "content": "API 密钥应该安全存储，建议使用 Azure Key Vault 或环境变量，避免硬编码在代码中..."
            },
            {
                "chunk_id": "chunk_ghi789",
                "title": "连接问题排查",
                "score": 0.78,
                "content": "如果连接失败，请检查：网络配置、防火墙规则、API Key 是否有效、Endpoint 是否正确..."
            }
        ]
    }
    
    print(f"\n{Colors.BLUE}检索结果 (Top 3):{Colors.END}")
    for i, result in enumerate(mock_results["results"], 1):
        print(f"\n{i}. **{result['title']}** (分数：{result['score']})")
        print(f"   ID: {result['chunk_id']}")
        print(f"   内容：{result['content'][:80]}...")
    
    print(f"\n{Colors.GREEN}✓ 检索完成，返回 3 条相关结果{Colors.END}")


# ==================== 场景 2: 查询意图分析 ====================

def demo_intent_analysis():
    """演示查询意图分析功能"""
    print_header("场景 2: 查询意图分析")
    
    test_queries = [
        "如何配置 Azure OpenAI 连接？",
        "RAG 和传统搜索有什么区别？",
        "为什么检索结果不准确？",
        "什么是混合检索？",
    ]
    
    expected_intents = {
        "如何": "PROCEDURAL (流程类)",
        "区别": "COMPARATIVE (比较类)",
        "为什么": "EXPLANATORY (解释类)",
        "什么是": "DEFINITION (定义类)",
    }
    
    for query in test_queries:
        print_step("查询", f"'{query}'")
        
        # 简单意图识别
        intent = "UNKNOWN"
        if "如何" in query:
            intent = "PROCEDURAL (流程类)"
        elif "区别" in query or "对比" in query:
            intent = "COMPARATIVE (比较类)"
        elif "为什么" in query:
            intent = "EXPLANATORY (解释类)"
        elif "什么是" in query:
            intent = "DEFINITION (定义类)"
        
        print_result(f"识别意图：{intent}")
        
        if intent == "PROCEDURAL (流程类)":
            print(f"   → 建议检索策略：Top-K=5, 启用 Rerank")
        elif intent == "COMPARATIVE (比较类)":
            print(f"   → 建议检索策略：Top-K=10, 启用 Rerank")
    
    print(f"\n{Colors.GREEN}✓ 意图分析完成{Colors.END}")


# ==================== 场景 3: 相关问题推荐 ====================

def demo_related_questions():
    """演示相关问题推荐功能"""
    print_header("场景 3: 相关问题推荐")
    
    original_query = "如何配置 Azure OpenAI 连接？"
    print_step("原始查询", f"'{original_query}'")
    
    related = [
        ("📘 基础", "Azure OpenAI 支持哪些模型？"),
        ("📚 进阶", "如何优化 Azure OpenAI 的响应速度？"),
        ("🔧 排障", "Azure OpenAI 连接超时时如何解决？"),
        ("⚖️ 对比", "Azure OpenAI 和 OpenAI API 有什么区别？"),
        ("📌 扩展", "如何监控 Azure OpenAI 的使用量和成本？"),
    ]
    
    print(f"\n{Colors.BLUE}推荐的相关问题:{Colors.END}\n")
    for icon, question in related:
        print(f"  {icon} {question}")
    
    print(f"\n{Colors.GREEN}✓ 生成了 5 个相关问题建议{Colors.END}")


# ==================== 场景 4: 文档对比分析 ====================

def demo_document_comparison():
    """演示文档对比分析功能"""
    print_header("场景 4: 文档对比分析")
    
    print_step("输入", "对比 2 个 Chunk 的内容")
    
    mock_comparison = {
        "doc1": {
            "chunk_id": "chunk_abc123",
            "title": "Azure OpenAI 配置指南",
            "content": "配置 Azure OpenAI 需要：Endpoint, API Key, API Version..."
        },
        "doc2": {
            "chunk_id": "chunk_def456",
            "title": "OpenAI 原生 API 配置",
            "content": "使用 OpenAI API 需要：API Key, Organization ID, Base URL..."
        }
    }
    
    print(f"\n{Colors.BLUE}文档对比结果:{Colors.END}\n")
    print(f"文档 1: {mock_comparison['doc1']['title']}")
    print(f"  内容：{mock_comparison['doc1']['content']}")
    print(f"\n文档 2: {mock_comparison['doc2']['title']}")
    print(f"  内容：{mock_comparison['doc2']['content']}")
    
    print(f"\n{Colors.CYAN}相似度分析:{Colors.END}")
    print(f"  - 共同点：都需要 API Key 进行认证")
    print(f"  - 差异点：Azure 需要 Endpoint，原生 API 需要 Organization ID")
    print(f"  - 文本相似度：0.65")
    
    print(f"\n{Colors.GREEN}✓ 对比分析完成{Colors.END}")


# ==================== 场景 5: 结果导出功能 ====================

def demo_export_results():
    """演示结果导出功能"""
    print_header("场景 5: 检索结果导出")
    
    print_step("导出格式", "Markdown / JSON / CSV")
    
    print(f"\n{Colors.BLUE}导出示例 (Markdown):{Colors.END}\n")
    
    markdown_example = """# 检索结果导出

**查询:** 如何配置 Azure OpenAI 连接？
**结果数量:** 3

---

## 1. Azure OpenAI 服务配置指南
**相关性分数:** 0.92
**内容:**
> 配置 Azure OpenAI 需要以下步骤：
> 1. 在 Azure 门户创建资源
> 2. 获取 API Key 和 Endpoint
> 3. 配置环境变量
"""
    
    print(markdown_example)
    
    print(f"{Colors.GREEN}✓ 导出功能支持多种格式{Colors.END}")


# ==================== 场景 6: 完整工作流演示 ====================

def demo_complete_workflow():
    """演示完整的工作流"""
    print_header("场景 6: 完整工作流演示")
    
    workflow_steps = [
        ("1. 用户提问", "用户向 MCP Client 提出问题"),
        ("2. 意图分析", "调用 analyze_query_intent 分析查询意图"),
        ("3. 执行检索", "根据意图调用 query_knowledge_hub 检索"),
        ("4. 结果推荐", "调用 suggest_related_questions 生成相关问题"),
        ("5. 结果导出", "用户可选择 export_search_results 导出结果"),
        ("6. 文档对比", "需要时调用 compare_documents 对比多个文档"),
    ]
    
    print(f"{Colors.CYAN}完整工作流程:{Colors.END}\n")
    for step, description in workflow_steps:
        print(f"  {Colors.YELLOW}{step}{Colors.END} {description}")
    
    print(f"\n{Colors.BLUE}MCP 工具列表:{Colors.END}")
    tools = [
        ("query_knowledge_hub", "核心知识检索"),
        ("list_collections", "列出文档集合"),
        ("get_document_summary", "获取文档摘要"),
        ("analyze_query_intent", "查询意图分析"),
        ("suggest_related_questions", "相关问题推荐"),
        ("export_search_results", "结果导出"),
        ("compare_documents", "文档对比"),
    ]
    
    for tool_name, tool_desc in tools:
        print(f"  • {tool_name}: {tool_desc}")
    
    print(f"\n{Colors.GREEN}✓ 完整工作流演示完成{Colors.END}")


# ==================== 主函数 ====================

def run_all_demos():
    """运行所有演示场景"""
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{'RAG 系统 Demo 场景演示':^60}{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    
    demo_basic_search()
    demo_intent_analysis()
    demo_related_questions()
    demo_document_comparison()
    demo_export_results()
    demo_complete_workflow()
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}所有演示场景执行完成！{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'=' * 60}{Colors.END}\n")


def print_usage_guide():
    """打印使用指南"""
    print_header("MCP 工具使用指南")
    
    guide = """
这些 MCP 工具可以通过以下方式调用:

1. 通过 MCP Client (如 Claude Desktop, GitHub Copilot):
   - 连接到本地 MCP Server
   - 直接调用工具名称

2. 通过 Python 代码:
   ```python
   from src.mcp_server.tools.analyze_query_intent import get_tool_instance
   
   tool = get_tool_instance()
   result = tool.analyze(query="如何配置 Azure？")
   ```

3. 通过命令行测试:
   ```bash
   python main.py  # 启动 MCP Server
   ```

可用工具列表:
┌─────────────────────────────┬──────────────────────────────┐
│ 工具名称                    │ 功能描述                     │
├─────────────────────────────┼──────────────────────────────┤
│ query_knowledge_hub         │ 核心知识检索                 │
│ list_collections            │ 列出文档集合                 │
│ get_document_summary        │ 获取文档摘要                 │
│ analyze_query_intent        │ 查询意图分析 (新增)          │
│ suggest_related_questions   │ 相关问题推荐 (新增)          │
│ export_search_results       │ 结果导出 (新增)              │
│ compare_documents           │ 文档对比分析 (新增)          │
└─────────────────────────────┴──────────────────────────────┘
"""
    print(guide)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--guide":
            print_usage_guide()
        else:
            print_error(f"未知参数：{sys.argv[1]}")
            print("使用 --guide 查看使用指南")
    else:
        run_all_demos()