# Smart Agent Hub

基于 ReAct 模式的智能 Agent 框架，支持 MCP (Model Context Protocol) 工具调用。

## ✨ 新功能：Chat Dashboard

现在您可以通过可视化聊天界面与 Agent 交互了！

```bash
# 启动 Chat Dashboard
python main.py

# 或使用 Streamlit 直接启动
streamlit run dashboard/app.py --server.port 8502
```

访问 http://localhost:8502 开始对话！

**功能特点**：
- 💬 实时聊天界面
- 🤔 可视化思考过程
- 🔧 工具调用展示
- 📜 会话历史管理
- ⚙️ 配置管理

详细使用指南请参考 [Chat Dashboard 使用指南](docs/CHAT_DASHBOARD_USAGE_GUIDE.md)。

## 参考项目

本项目参考了 [ragent](https://github.com/nageoffer/ragent) 的设计和实现。

## 架构

```
smart-agent-hub/
├── agent/
│   ├── core/           # 核心 Agent 逻辑
│   │   ├── agent.py    # 主 Agent 类
│   │   ├── planner.py  # ReAct 规划器
│   │   ├── executor.py # 工具执行器
│   │   ├── memory.py   # 记忆管理
│   │   ├── models.py   # 数据模型
│   │   ├── settings.py # 配置管理
│   │   └── state_manager.py  # 状态管理
│   ├── llm/            # LLM 客户端
│   │   ├── client.py   # LLM 客户端
│   │   └── prompts.py  # 提示词模板
│   ├── mcp/            # MCP 客户端
│   │   ├── client.py   # MCP 客户端（参考 ragent 实现）
│   │   └── tool_registry.py  # 工具注册表
│   └── storage/        # 存储层
│       └── jsonl_logger.py  # JSONL 日志
├── dashboard/          # Streamlit 仪表板
├── config/             # 配置文件
├── data/               # 数据目录
├── tests/              # 单元测试
└── cli.py              # 命令行入口
```

## 快速开始

### 1. 安装依赖

```bash
cd smart-agent-hub
pip install -e .
```

### 2. 配置

编辑 `config/settings.yaml` 配置 LLM 和 MCP 服务器：

```yaml
settings:
  llm:
    provider: "qwen"
    model: "qwen3.5-plus"
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: "your-api-key"
  
  mcp_servers:
    rag_server:
      enabled: true
      command: "python"
      args: ["-m", "src.mcp_server.server"]
      cwd: "E:/code/MODULAR-RAG-MCP-SERVER"
      timeout: 120
```

### 3. 运行

```bash
# 使用 CLI
python cli.py "帮我查找关于 RAG 的资料"

# 带详细输出
python cli.py "你的问题" --verbose
```

## 核心功能

### ReAct 模式

Agent 使用 ReAct (Reasoning + Acting) 模式进行规划和执行：

1. **Thought**: 分析当前状态和下一步行动
2. **Action**: 选择并执行工具
3. **Observation**: 获取工具执行结果
4. **Repeat**: 循环直到得出最终答案

### MCP 工具调用

通过 MCP 协议连接到外部服务（如 RAG 知识库）：

- `query_knowledge_hub`: 搜索知识库文档
- `list_collections`: 列出文档集合
- `get_document_summary`: 获取文档摘要

### 会话管理

- 自动保存会话历史到 `data/logs/agent_traces.jsonl`
- 状态持久化到 `data/db/agent_sessions.db`
- 支持会话恢复和查询

## 与 ragent 的对比

| 特性 | ragent | smart-agent-hub |
|------|--------|-----------------|
| MCP 客户端 | 使用官方 SDK | 自定义实现（更可靠） |
| 规划模式 | ReAct | ReAct |
| 记忆系统 | 简单历史 | 完整状态管理 |
| 仪表板 | 无 | Streamlit |
| 配置 | 环境变量 | YAML 文件 |

## 修复内容

参考 ragent 项目，对原有代码进行了以下修复：

1. **MCP 客户端重写**: 使用底层 JSON-RPC 通信，避免 anyio TaskGroup 问题
2. **编码问题**: 添加 UTF-8 编码支持，处理中文字符
3. **超时管理**: 正确的超时参数传递和初始化握手
4. **资源清理**: 完善的 subprocess 清理逻辑

## 开发

### 运行测试

```bash
pytest tests/unit/ -v
```

### 查看日志

```bash
# Agent 执行日志
cat data/logs/agent_traces.jsonl

# 会话数据库
sqlite3 data/db/agent_sessions.db "SELECT * FROM sessions;"
```

## License

MIT