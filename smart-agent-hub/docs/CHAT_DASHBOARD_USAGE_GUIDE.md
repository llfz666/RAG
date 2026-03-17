# Chat Dashboard 使用指南

Smart Agent Hub Chat Dashboard - 与智能 Agent 进行实时对话的可视化界面。

## 目录

- [功能概述](#功能概述)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [功能模块说明](#功能模块说明)
- [常见问题](#常见问题)
- [故障排查](#故障排查)

---

## 功能概述

Chat Dashboard 提供了一个直观的聊天界面，让您能够：

- 💬 **实时对话** - 与 Smart Agent 进行自然语言对话
- 🔍 **知识库查询** - 通过 Agent 查询知识库中的文档
- 📊 **可视化流程** - 查看 Agent 的思考、行动和观察过程
- 📜 **会话历史** - 保存和查看对话历史
- ⚙️ **配置管理** - 管理连接和 Agent 配置

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Chat Dashboard                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  chat_page   │  │chat_service  │  │ chat_models  │       │
│  │   (UI 层)     │◄─┤  (服务层)    │◄─┤   (模型层)   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                  │                  │               │
│         ▼                  ▼                  ▼               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Smart Agent Hub Core                    │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │    │
│  │  │ Planner  │  │ MCP Client│ │  Tool Registry   │  │    │
│  │  └──────────┘  └──────────┘  └──────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                  │
│                            ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              MCP Server (RAG Server)                 │    │
│  │  - query_knowledge_hub                               │    │
│  │  - list_collections                                  │    │
│  │  - get_document_summary                              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 前置条件

1. **Python 环境** - Python 3.11+
2. **依赖安装** - 确保已安装所有依赖

```bash
cd smart-agent-hub
pip install -e .
```

### 配置

确保配置文件 `config/settings.yaml` 已正确设置：

```yaml
# LLM 配置
llm:
  provider: openai  # 或 azure, qwen, ollama 等
  api_key: your-api-key
  model: gpt-3.5-turbo

# MCP Server 配置
mcp_servers:
  rag_server:
    command: "python"
    args:
      - "-m"
      - "src.mcp_server"
```

### 启动 Dashboard

```bash
# 方法 1: 使用 main.py 启动（推荐）
cd smart-agent-hub
python main.py

# 方法 2: 直接使用 Streamlit
streamlit run dashboard/app.py --server.port 8502
```

> **注意**: Chat Dashboard 使用端口 8502，避免与 RAG Dashboard（端口 8501）冲突。

### 访问界面

打开浏览器访问：http://localhost:8502

---

## 使用指南

### 1. 连接 Agent

首次使用时，Dashboard 会自动尝试连接 Agent：

1. 等待初始化完成（显示 "✅ Agent 已就绪！"）
2. 如果连接失败，检查配置和 MCP Server 状态
3. 点击 "🔄 重新连接" 可以重试

### 2. 开始对话

在聊天输入框中输入您的问题：

```
什么是 RAG？
```

Agent 会：
1. 🤔 **思考** - 分析问题意图
2. 🔧 **行动** - 调用合适的工具（如 query_knowledge_hub）
3. 📦 **观察** - 获取工具返回结果
4. ✅ **回答** - 综合信息给出最终答案

### 3. 查看执行流程

点击消息旁边的展开按钮，可以查看：

- **思考过程** - Agent 的推理过程
- **工具调用** - 调用的工具名称和参数
- **观察结果** - 工具返回的原始数据

### 4. 管理会话

**清除当前会话**：
- 点击侧边栏的 "🗑️ 清除当前会话" 按钮
- 会创建新的会话 ID

**查看历史会话**：
- 切换到 "📜 Session History" 页面
- 浏览和搜索过去的对话

---

## 功能模块说明

### 页面结构

```
┌────────────────────────────────────────────────────┐
│  Smart Agent Hub Dashboard                          │
├─────────────┬──────────────────────────────────────┤
│             │                                      │
│  侧边栏      │           主内容区                     │
│  - 连接状态   │           - 聊天消息列表              │
│  - 会话信息   │           - 输入框                   │
│  - 操作按钮   │                                      │
│             │                                      │
└─────────────┴──────────────────────────────────────┘
```

### 消息类型

| 类型 | 图标 | 说明 | 显示方式 |
|------|------|------|----------|
| USER | 👤 | 用户消息 | 右侧气泡 |
| ASSISTANT | 🤖 | 助手回复 | 左侧气泡 |
| THOUGHT | 🤔 | 思考过程 | 可折叠区域 |
| ACTION | 🔧 | 工具调用 | 可折叠区域（带参数） |
| OBSERVATION | 📦 | 工具结果 | 可折叠区域 |
| FINAL_ANSWER | ✅ | 最终答案 | 高亮成功样式 |
| ERROR | ❌ | 错误消息 | 红色警告 |
| SYSTEM | ⚙️ | 系统消息 | 灰色信息 |

### 侧边栏功能

**连接状态**：
- 🟢 已连接 - Agent 就绪，可以对话
- 🔄 连接中 - 正在初始化
- 🔴 未连接 - 需要手动连接
- ❌ 错误 - 显示错误信息

**会话信息**：
- 消息数量统计
- 会话 ID 预览
- 消息类型分布

**操作按钮**：
- 🗑️ 清除当前会话 - 清空消息，创建新会话
- 🔄 重新连接 - 重启 Agent 连接

---

## 常见问题

### Q1: 如何查询知识库？

直接在聊天框中输入您的问题即可。Agent 会自动判断是否需要查询知识库。

**示例问题**：
- "RAG 技术是什么？"
- "帮我查找关于机器学习的文档"
- "总结一下最近的会议记录"

### Q2: 为什么显示 "未连接"？

可能原因：
1. 配置文件未正确设置
2. MCP Server 未启动
3. LLM API Key 无效

请参考 [故障排查](#故障排查) 部分。

### Q3: 如何查看完整的执行日志？

1. 点击消息的展开按钮查看单条消息详情
2. 切换到 "🔍 Execution Trace" 页面查看完整流程
3. 查看日志文件：`data/logs/agent_traces.jsonl`

### Q4: 对话历史保存在哪里？

- **数据库**: `data/db/agent_sessions.db`
- **JSONL 日志**: `data/logs/agent_traces.jsonl`
- **长期记忆**: `data/logs/long_term_memory.jsonl`

---

## 故障排查

### 问题 1: 初始化失败

**错误信息**: "初始化失败：xxx"

**解决方案**：

1. 检查配置文件：
```bash
cat config/settings.yaml
```

2. 验证 LLM 配置：
```python
# 测试 LLM 连接
from agent.llm.client import LLMClient
from agent.core.settings import load_settings

settings = load_settings()
client = LLMClient.from_settings(settings)
response = client.generate("Hello")
print(response)
```

3. 检查 MCP Server：
```bash
# 手动启动 MCP Server 测试
python -m src.mcp_server
```

### 问题 2: 端口冲突

**错误信息**: "Port 8502 is already in use"

**解决方案**：

```bash
# 使用其他端口
streamlit run dashboard/app.py --server.port 8503
```

### 问题 3: 依赖缺失

**错误信息**: "ModuleNotFoundError: No module named 'xxx'"

**解决方案**：

```bash
cd smart-agent-hub
pip install -e .
```

### 问题 4: 数据库不存在

**错误信息**: "unable to open database file"

**解决方案**：

```bash
# 创建数据目录
mkdir -p data/db
mkdir -p data/logs

# 或者运行一次 Agent 自动创建
python main.py
```

### 问题 5: 消息不显示

**可能原因**：Streamlit 缓存问题

**解决方案**：

```bash
# 清除 Streamlit 缓存
rm -rf ~/.streamlit
```

---

## API 参考

### ChatService

```python
from dashboard.chat_service import get_chat_service

# 获取服务实例
service = get_chat_service()

# 初始化
await service.initialize()

# 处理查询（流式）
async for msg in service.process_query("问题", "session_id"):
    print(f"{msg.role}: {msg.content}")

# 简单查询（只返回最终答案）
answer = await service.simple_query("问题")
```

### ChatMessage

```python
from dashboard.chat_models import ChatMessage, MessageType

# 创建消息
msg = ChatMessage(
    role=MessageType.USER,
    content="Hello",
)

# 获取属性
print(msg.icon)           # 👤
print(msg.display_title)  # 用户
print(msg.background_color)  # #f0f2f6

# 序列化
data = msg.to_dict()

# 反序列化
msg = ChatMessage.from_dict(data)
```

---

## 进阶用法

### 自定义消息样式

编辑 `dashboard/chat_page.py` 中的 CSS：

```css
.chat-message.user {
    background-color: #your-color;
}
```

### 添加自定义工具

1. 在 MCP Server 中注册新工具
2. 在 `agent/mcp/tool_registry.py` 中添加工具定义
3. 重启 Dashboard

### 集成到其他应用

```python
from dashboard.chat_service import ChatService

# 在自己的应用中使用
async def my_function():
    service = ChatService()
    await service.initialize()
    answer = await service.simple_query("问题")
    return answer
```

---

## 相关文档

- [Chat Dashboard 规范](CHAT_DASHBOARD_SPEC.md) - 详细技术规范
- [Agent 使用指南](AGENT_USAGE_GUIDE.md) - Agent 命令行使用
- [Dashboard 使用指南](DASHBOARD_USAGE_GUIDE.md) - 原 Dashboard 功能
- [记忆和会话管理](MEMORY_AND_DASHBOARD_COMPLETE.md) - 记忆系统说明

---

## 技术支持

如有问题，请：

1. 查看日志文件：`logs/` 目录
2. 检查 GitHub Issues
3. 联系开发团队