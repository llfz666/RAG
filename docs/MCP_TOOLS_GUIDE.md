# MCP 扩展工具使用指南

本文档介绍为 Modular RAG MCP Server 新增的扩展工具及其使用方法。

## 新增工具概览

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| `analyze_query_intent` | 查询意图分析 | 识别用户查询类型，优化检索策略 |
| `suggest_related_questions` | 相关问题推荐 | 引导用户深入探索主题 |
| `export_search_results` | 检索结果导出 | 导出结果为 Markdown/JSON/CSV |
| `compare_documents` | 文档对比分析 | 对比多个文档的异同 |

## 工具详细说明

### 1. analyze_query_intent - 查询意图分析

**功能**: 分析用户查询的意图类型，帮助选择最优检索策略。

**支持的意图类型**:
- `FACTUAL` - 事实性查询（寻求具体信息）
- `COMPARATIVE` - 比较类查询（对比多个事物）
- `PROCEDURAL` - 流程类查询（如何做某事）
- `EXPLANATORY` - 解释类查询（为什么/原理）
- `TROUBLESHOOTING` - 故障排除类查询
- `DEFINITION` - 定义类查询（是什么）

**输入参数**:
```json
{
  "query": "如何配置 Azure 连接？",
  "language": "auto"  // 可选：zh, en, auto
}
```

**输出示例**:
```markdown
## 查询意图分析

**查询:** `如何配置 Azure 连接？`

| 属性 | 值 |
|------|-----|
| 意图类型 | **PROCEDURAL** |
| 置信度 | 90% |
| 建议 Top-K | 5 |
| 建议重排 | 是 |
| 关键词 | 如何，配置 |

**分析说明:** 识别为流程类查询，需要了解步骤、方法或指南。置信度高 (90%)。
```

**使用建议**:
- 在检索前调用，根据意图调整 `top_k` 和是否启用 rerank
- PROCEDURAL 类查询：top_k=5, 启用 rerank
- COMPARATIVE 类查询：top_k=10, 启用 rerank

---

### 2. suggest_related_questions - 相关问题推荐

**功能**: 基于用户当前查询，生成相关的后续问题建议。

**输入参数**:
```json
{
  "query": "如何配置 Azure 连接？",
  "num_suggestions": 5,
  "category": "all"  // 可选：basic, advanced, troubleshooting, comparison, all
}
```

**输出示例**:
```markdown
## 相关问题推荐

**原始查询:** `如何配置 Azure 连接？`

以下是您可能感兴趣的相关问题：

1. 📘 基础 **什么是 Azure 连接？**
   _帮助您理解基础概念和用法_

2. 📚 进阶 **如何优化 Azure 连接的性能？**
   _深入探索高级功能和最佳实践_

3. 🔧 排障 **如何解决 Azure 连接失败的问题？**
   _解决可能遇到的常见问题_

4. ⚖️ 对比 **Azure 连接与其他方案有什么区别？**
   _帮助您做出更好的技术选型_
```

**使用场景**:
- 检索完成后，帮助用户深入探索
- 在对话界面中提供后续问题建议

---

### 3. export_search_results - 检索结果导出

**功能**: 将检索结果导出为多种格式。

**输入参数**:
```json
{
  "query": "Azure 配置",
  "format": "markdown",  // 可选：markdown, json, csv
  "top_k": 5,
  "collection": "default",
  "include_metadata": true
}
```

**输出格式**:

**Markdown**:
```markdown
# 检索结果导出

**查询:** Azure 配置
**结果数量:** 3

---

## 1. 结果 #1
**相关性分数:** 0.92
**内容:**
> 配置 Azure OpenAI 需要以下步骤...
```

**JSON**:
```json
{
  "query": "Azure 配置",
  "export_time": "2024-01-01 12:00:00",
  "result_count": 3,
  "results": [
    {
      "text": "内容...",
      "score": 0.92,
      "metadata": {...}
    }
  ]
}
```

**CSV**:
```csv
rank,score,text,source,title
1,0.92,"配置 Azure OpenAI 需要...","source.pdf","配置指南"
```

---

### 4. compare_documents - 文档对比分析

**功能**: 对比多个文档或 Chunk 的异同。

**输入参数**:
```json
{
  "chunk_ids": ["chunk_abc123", "chunk_def456"],
  "comparison_type": "all",  // 可选：content, similarity, keypoints, all
  "max_length": 500
}
```

**输出示例**:
```markdown
## 文档对比分析

**对比文档数:** 2

### 📄 文档内容

**1. Azure OpenAI 配置指南** (`chunk_abc123...`)
> 配置 Azure OpenAI 需要：Endpoint, API Key, API Version...

**2. OpenAI 原生 API 配置** (`chunk_def456...`)
> 使用 OpenAI API 需要：API Key, Organization ID, Base URL...

### 📊 相似度矩阵

|   | D1 | D2 |
|---|----|----|
| D1 | 1.00 | 0.65 |
| D2 | 0.65 | 1.00 |

### 🔍 共同主题
- 都需要 API Key 进行认证

### 📝 分析总结
已对比 2 个文档，发现 1 个共同主题。
```

**使用场景**:
- 对比不同版本文档的差异
- 比较多个相关文档的侧重点
- 分析不同来源的信息一致性

---

## 完整工作流示例

```
┌─────────────────────────────────────────────────────────────┐
│                    用户提出问题                              │
│              "如何配置 Azure OpenAI 连接？"                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  1. analyze_query_intent                                    │
│     识别意图：PROCEDURAL (流程类)                            │
│     建议：top_k=5, 启用 rerank                              │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. query_knowledge_hub                                     │
│     执行检索，返回 5 条相关结果                               │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. suggest_related_questions                               │
│     生成相关问题建议                                         │
│     - Azure OpenAI 支持哪些模型？                            │
│     - 如何优化响应速度？                                     │
│     - 连接超时时如何解决？                                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  4. (可选) export_search_results                            │
│     用户选择导出结果为 Markdown/JSON/CSV                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Python 代码调用示例

```python
# 查询意图分析
from src.mcp_server.tools.analyze_query_intent import get_tool_instance

intent_tool = get_tool_instance()
result = intent_tool.analyze(query="如何配置 Azure？")
print(f"意图：{result.intent}, 置信度：{result.confidence}")

# 相关问题推荐
from src.mcp_server.tools.suggest_related_questions import get_tool_instance

suggest_tool = get_tool_instance()
result = suggest_tool.suggest(
    query="如何配置 Azure？",
    num_suggestions=5,
    category="all"
)
for suggestion in result.suggestions:
    print(f"- {suggestion.question}")

# 结果导出
from src.mcp_server.tools.export_search_results import get_tool_instance

export_tool = get_tool_instance()
# 需要先获取检索结果
# result = export_tool.export(
#     query="Azure 配置",
#     format="markdown",
#     results=search_results
# )

# 文档对比
from src.mcp_server.tools.compare_documents import get_tool_instance

compare_tool = get_tool_instance()
# result = compare_tool.compare(
#     chunk_ids=["chunk_1", "chunk_2"],
#     comparison_type="all"
# )
```

---

## 本地化部署

使用本地开源模型运行 RAG 系统：

```bash
# 1. 安装 Ollama
# 访问 https://ollama.ai 下载安装

# 2. 下载模型
ollama pull qwen2.5-coder:7b   # LLM
ollama pull bge-m3:latest       # Embedding

# 3. 运行部署脚本
python scripts/local_deploy.py

# 4. 启动服务
python scripts/start_local.py
```

---

## Demo 场景演示

运行 Demo 脚本查看所有功能演示：

```bash
python scripts/demo_scenarios.py
```

查看使用指南：

```bash
python scripts/demo_scenarios.py --guide
```

---

## 工具注册

所有新工具已自动注册到 MCP 服务器，在 `src/mcp_server/protocol_handler.py` 中的 `_register_default_tools()` 函数中可以看到注册逻辑。

启动 MCP 服务器后，任何 MCP Client（如 Claude Desktop、GitHub Copilot）都可以发现和调用这些工具。

```bash
# 启动 MCP 服务器
python main.py
```

---

## 总结

这些扩展工具增强了 RAG 系统的交互能力：

1. **更智能的检索** - 通过意图分析优化检索策略
2. **更好的引导** - 通过相关问题推荐帮助用户深入探索
3. **更方便的使用** - 支持结果导出和文档对比
4. **更灵活的部署** - 支持完全本地化运行

这些工具可以单独使用，也可以组合成完整的工作流，为用户提供更好的知识检索体验。