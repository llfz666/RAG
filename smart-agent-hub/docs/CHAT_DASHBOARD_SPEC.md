# Agent Dashboard 聊天交互功能实现规范

## 📖 文档信息

| 项目 | 内容 |
|------|------|
| **文档名称** | Agent Dashboard 聊天交互功能实现规范 |
| **版本** | 0.1 (基础版本 MVP) |
| **目标** | 在现有 Dashboard 基础上添加实时聊天交互功能 |
| **优先级** | P0 - 核心功能 |

---

## 1. 需求概述

### 1.1 当前状态

目前 Smart Agent Hub 的使用方式：
- ✅ **命令行交互**：`python cli.py "问题"`
- ✅ **只读 Dashboard**：查看历史会话、执行轨迹

### 1.2 目标状态

添加 **Dashboard 聊天交互功能**：
- ✅ 保留现有命令行功能
- ✅ 保留现有 Dashboard 查看功能
- ✅ **新增**：Dashboard 聊天页面，实时与 Agent 对话

### 1.3 用户流程

```
┌─────────────────────────────────────────────────────────────┐
│  用户打开浏览器访问 http://localhost:8502                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  进入 Chat 页面                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🤖 Agent 助手                                         │   │
│  │                                                      │   │
│  │  [历史消息区域]                                      │   │
│  │  - 用户：帮我查找 RAG 资料                              │   │
│  │  - Agent: 好的，正在为您搜索...                       │   │
│  │                                                      │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ 输入您的问题...                       [发送] │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Agent 后台执行 ReAct 循环，实时流式返回：                    │
│  🤔 Thought → 🔧 Action → 📦 Observation → ✅ Answer        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit Dashboard                           │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │                    Chat Page (新增)                         │     │
│  │  • st.chat_input - 用户输入                                 │     │
│  │  • st.session_state - 对话历史                              │     │
│  │  • st.write_stream - 流式响应                               │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              │                                        │
│                              ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              Chat Service (新增)                            │     │
│  │  • 调用 Agent Planner                                       │     │
│  │  • 处理流式响应                                             │     │
│  │  • 保存到会话历史                                           │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Smart Agent Hub                                  │
│  (现有 Agent 逻辑，无需修改)                                          │
│  • Planner - ReAct 规划器                                            │
│  • Executor - 工具执行器                                            │
│  • MCP Client - 连接 RAG Server                                     │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     RAG-MCP-SERVER                                   │
│  (现有 RAG 服务，无需修改)                                            │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
用户输入
   ↓
st.session_state.messages.append()
   ↓
ChatService.process()
   ↓
Agent Planner.plan_and_execute()
   ↓
[ReAct 循环：Thought → Action → Observation]
   ↓
流式返回中间结果
   ↓
Dashboard 实时显示
   ↓
最终答案
   ↓
保存到 SQLite + JSONL
```

---

## 3. 核心数据模型

### 3.1 消息类型枚举

```python
class MessageType(str, Enum):
    USER = "user"           # 用户消息
    ASSISTANT = "assistant" # 助手消息
    THOUGHT = "thought"     # 思考过程
    ACTION = "action"       # 工具调用
    OBSERVATION = "observation"  # 工具结果
    FINAL_ANSWER = "final_answer"  # 最终答案
```

### 3.2 聊天消息模型

```python
class ChatMessage(BaseModel):
    """聊天消息"""
    id: str                    # 消息 ID
    role: MessageType          # 消息类型
    content: str               # 消息内容
    timestamp: datetime        # 时间戳
    metadata: dict[str, Any]   # 元数据
```

---

## 4. 核心模块实现

### 4.1 模块列表

| 文件 | 描述 | 状态 |
|------|------|------|
| `dashboard/chat_models.py` | 数据模型定义 | 待实现 |
| `dashboard/chat_service.py` | 聊天服务逻辑 | 待实现 |
| `dashboard/chat_page.py` | 聊天页面 UI | 待实现 |
| `dashboard/app.py` | 主应用（扩展） | 待修改 |

### 4.2 Chat Service 接口

```python
class ChatService:
    async def initialize(self, config_path: str = None) -> None:
        """初始化 Agent 组件"""
        
    async def shutdown(self) -> None:
        """关闭连接"""
        
    async def process_query(
        self, 
        query: str, 
        session_id: str
    ) -> AsyncGenerator[ChatMessage, None]:
        """处理用户查询，流式返回消息"""
```

### 4.3 Chat Page 接口

```python
async def chat_page() -> None:
    """聊天页面主逻辑"""
    # 1. 初始化服务
    # 2. 显示历史消息
    # 3. 处理用户输入
    # 4. 流式显示响应
```

---

## 5. 测试方案

### 5.1 单元测试

| 测试文件 | 测试内容 | 状态 |
|---------|---------|------|
| `tests/unit/test_chat_models.py` | 数据模型测试 | 待实现 |
| `tests/unit/test_chat_service.py` | 聊天服务测试 | 待实现 |

### 5.2 集成测试

| 测试文件 | 测试内容 | 状态 |
|---------|---------|------|
| `tests/integration/test_chat_page.py` | 聊天页面集成测试 | 待实现 |

### 5.3 手动测试清单

| 测试项 | 操作步骤 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 页面加载 | 访问 http://localhost:8502 | Chat 页面正常显示 | [ ] |
| 简单问答 | 输入"你好" | Agent 返回问候 | [ ] |
| RAG 查询 | 输入"帮我查找 RAG 资料" | Agent 调用工具并返回结果 | [ ] |
| 多轮对话 | 连续发送多条消息 | 上下文保持连贯 | [ ] |
| 清除会话 | 点击"清除当前会话" | 消息清空 | [ ] |

---

## 6. 实现排期

### 阶段总览

| 阶段 | 名称 | 预计时间 | 产出 |
|------|------|----------|------|
| **A** | 工程准备 | 2 小时 | 目录结构、依赖安装 |
| **B** | Chat Service | 4 小时 | 聊天服务核心逻辑 |
| **C** | Chat Page UI | 4 小时 | 聊天页面组件 |
| **D** | 集成测试 | 2 小时 | 测试用例 |
| **E** | 文档和验收 | 2 小时 | 使用指南 |

**总计：约 14 小时（2 个工作日）**

---

### 阶段 A：工程准备

#### A1. 目录结构
```
smart-agent-hub/
├── dashboard/
│   ├── app.py              # 主应用（扩展）
│   ├── chat_page.py        # 聊天页面（新增）
│   ├── chat_service.py     # 聊天服务（新增）
│   └── chat_models.py      # 数据模型（新增）
├── tests/
│   ├── unit/
│   │   └── test_chat_service.py  # 单元测试（新增）
│   └── integration/
│       └── test_chat_dashboard.py # 集成测试（新增）
└── docs/
    └── CHAT_DASHBOARD_GUIDE.md  # 使用指南（新增）
```

#### A2. 依赖安装
```bash
# 现有依赖（应已安装）
pip install streamlit pandas

# 新增依赖（如需）
pip install aiohttp  # 如果需要异步 HTTP
```

**验收标准**：
- [ ] 目录结构创建完成
- [ ] `streamlit --version` 可运行
- [ ] 现有 Dashboard 可正常启动

---

### 阶段 B：Chat Service

#### B1. 数据模型 (chat_models.py)
- [ ] ChatMessage 类
- [ ] MessageType 枚举
- [ ] 显示辅助方法

#### B2. 聊天服务 (chat_service.py)
- [ ] 初始化 Agent 组件
- [ ] process_query 流式处理
- [ ] 错误处理

**验收标准**：
- [ ] `pytest tests/unit/test_chat_service.py` 通过
- [ ] 服务可正常初始化和关闭
- [ ] 流式返回消息格式正确

---

### 阶段 C：Chat Page UI

#### C1. 页面布局
- [ ] st.chat_input 输入框
- [ ] 消息历史显示区域
- [ ] 自定义 CSS 样式

#### C2. 消息渲染
- [ ] render_message 函数
- [ ] 不同消息类型样式
- [ ] 元数据显示（可折叠）

#### C3. 侧边栏功能
- [ ] 清除会话按钮
- [ ] 会话统计

**验收标准**：
- [ ] 页面可正常加载
- [ ] 输入消息后正确显示
- [ ] 流式响应正常显示

---

### 阶段 D：集成测试

#### D1. 集成测试
- [ ] Dashboard 启动测试
- [ ] 页面加载测试
- [ ] 聊天功能测试

**验收标准**：
- [ ] `pytest tests/integration/test_chat_dashboard.py` 通过
- [ ] 手动测试清单全部通过

---

### 阶段 E：文档和验收

#### E1. 使用指南
```markdown
# Chat Dashboard 使用指南

## 快速开始
1. 启动 Agent：`cd smart-agent-hub && streamlit run dashboard/app.py --server.port 8502`
2. 访问：http://localhost:8502
3. 点击侧边栏 "💬 Chat"
4. 输入问题并发送

## 功能说明
- ...
```

**验收标准**：
- [ ] 文档完整
- [ ] 截图示例
- [ ] 常见问题解答

---

## 7. 技术风险与应对

### 7.1 一般风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| Streamlit 流式显示不稳定 | 中 | 低 | 使用 st.empty 占位符 |
| Agent 初始化时间长 | 中 | 中 | 后台异步初始化，显示 Loading |
| MCP 连接失败 | 高 | 低 | 添加重试机制和错误提示 |
| 长文本溢出 | 低 | 中 | 限制显示长度，提供展开查看 |

---

## 8. 环境冲突风险与应对

### 8.1 Python 环境冲突

#### 风险描述
| 风险项 | 描述 | 影响 | 概率 |
|--------|------|------|------|
| **依赖版本冲突** | RAG Server 和 Agent 可能依赖不同版本的库 | 高 | 中 |
| **虚拟环境隔离** | 两个项目可能使用不同的虚拟环境 | 中 | 高 |
| **Python 版本差异** | 不同 Python 版本导致的兼容性问题 | 中 | 低 |

#### 应对方案

**方案 A：统一虚拟环境（推荐）**
```bash
# 在 RAG 项目根目录创建统一虚拟环境
cd MODULAR-RAG-MCP-SERVER
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 安装 RAG 项目依赖
pip install -e .

# 安装 Agent 项目依赖（共享同一环境）
cd smart-agent-hub
pip install -e .
```

**方案 B：独立虚拟环境（隔离更好）**
```yaml
# config/settings.yaml 中明确指定 Python 路径
mcp_servers:
  rag_server:
    enabled: true
    command: ".venv/Scripts/python.exe"  # 明确指定 Python 路径
    args:
      - "main.py"
    cwd: "../MODULAR-RAG-MCP-SERVER"
```

**方案 C：Conda 环境（适合复杂依赖）**
```bash
# 创建统一 Conda 环境
conda create -n rag-agent python=3.11
conda activate rag-agent

# 安装所有依赖
pip install -e MODULAR-RAG-MCP-SERVER/
pip install -e smart-agent-hub/
```

---

### 8.2 端口冲突

#### 风险描述
| 服务 | 默认端口 | 冲突可能 |
|------|----------|----------|
| RAG Dashboard | 8501 | 高（Streamlit 默认端口） |
| Agent Dashboard | 8502 | 中 |

#### 应对方案

**方案 A：配置文件指定端口**
```yaml
# smart-agent-hub/config/settings.yaml
dashboard:
  port: 8502  # 明确指定端口
  host: "localhost"
```

**方案 B：命令行参数覆盖**
```bash
# 启动 RAG Dashboard
streamlit run src/observability/dashboard/app.py --server.port 8501

# 启动 Agent Dashboard（带聊天功能）
streamlit run smart-agent-hub/dashboard/app.py --server.port 8502
```

---

### 8.3 数据库文件锁冲突

#### 风险描述
- 多个进程同时访问 SQLite 数据库可能导致锁竞争
- ChromaDB 和 BM25 索引可能被多个进程同时写入

#### 应对方案

**方案 A：数据库连接池**
```python
# agent/core/state_manager.py
from contextlib import contextmanager

class StateManager:
    @contextmanager
    def get_connection(self):
        """上下文管理器获取连接"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            yield conn
        finally:
            conn.close()
```

---

### 8.4 环境变量冲突

#### 风险描述
- API_KEY 等环境变量可能在两个项目中重复定义
- 不同项目可能使用不同的配置文件路径

#### 应对方案

**统一环境变量管理**
```bash
# .env 文件（项目根目录）
QWEN_API_KEY=your_api_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
RAG_DATA_DIR=./data
AGENT_DATA_DIR=./smart-agent-hub/data
```

---

## 9. 网络连接问题与应对

### 9.1 LLM API 连接问题

#### 风险描述
| 风险项 | 描述 | 影响 | 概率 |
|--------|------|------|------|
| **API 超时** | LLM API 响应超时 | 高 | 中 |
| **API 限流** | 请求频率超过限制 | 高 | 中 |
| **网络中断** | 完全无法连接 | 高 | 低 |

#### 应对方案

**方案 A：重试机制**
```python
# agent/llm/client.py
from tenacity import retry, stop_after_attempt, wait_exponential

class LLMClient:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate(self, messages: list, **kwargs) -> str:
        """带重试的生成方法"""
        pass
```

**方案 B：超时设置**
```yaml
# config/settings.yaml
llm:
  timeout: 60  # 60 秒超时
  max_retries: 3
```

---

### 9.2 MCP 连接问题

#### 风险描述
| 风险项 | 描述 | 影响 | 概率 |
|--------|------|------|------|
| **子进程启动失败** | RAG Server 进程无法启动 | 高 | 中 |
| **stdin/stdout 死锁** | 标准输入输出死锁 | 高 | 低 |

#### 应对方案

**方案 A：进程健康检查**
```python
# agent/mcp/client.py
async def connect(self):
    """带健康检查的连接"""
    # 等待进程启动
    for _ in range(10):
        if self.process.poll() is not None:
            stderr = self.process.stderr.read().decode()
            raise RuntimeError(f"MCP Server failed to start: {stderr}")
        time.sleep(0.5)
```

**方案 B：连接超时**
```python
async def connect_with_timeout(self, timeout: float = 30.0):
    """带超时的连接"""
    await asyncio.wait_for(self.connect(), timeout=timeout)
```

---

### 9.3 Dashboard 网络问题

#### 风险描述
| 风险项 | 描述 | 影响 | 概率 |
|--------|------|------|------|
| **浏览器无法访问** | 防火墙或端口被阻止 | 中 | 中 |
| **WebSocket 断开** | 流式连接不稳定 | 中 | 中 |

#### 应对方案

**方案 A：端口检查脚本**
```python
# dashboard/health_check.py
import socket

def check_port_available(port: int) -> bool:
    """检查端口是否可用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False
```

---

## 10. 故障排查指南

### 10.1 快速诊断流程

```
问题：聊天功能无法使用
   ↓
Step 1: Dashboard 是否正常启动
   ↓
Step 2: Agent 初始化状态检查
   ↓
Step 3: MCP 连接状态检查
   ↓
Step 4: LLM API 连接检查
```

### 10.2 日志收集脚本

```bash
#!/bin/bash
# scripts/collect_logs.sh

echo "=== Dashboard 日志 ==="
tail -n 100 data/logs/chat_service.log

echo "=== MCP Client 日志 ==="
tail -n 100 data/logs/mcp_client.log

echo "=== Agent 轨迹日志 ==="
tail -n 50 data/logs/agent_traces.jsonl
```

---

## 11. 总结

本规范定义了 **Agent Dashboard 聊天交互功能**的基础版本实现：

1. **最小可行产品 (MVP)**：
   - 保留现有命令行功能
   - 在 Dashboard 中添加聊天页面
   - 流式显示 Agent 思考过程

2. **架构清晰**：
   - Chat Service 连接 Dashboard 和 Agent
   - 复用现有 Agent 逻辑，无需修改核心代码

3. **可测试**：
   - 单元测试验证服务逻辑
   - 集成测试验证端到端流程
   - 手动测试清单确保功能完整

4. **可扩展**：
   - 后续可添加多会话管理
   - 可添加消息历史记录
   - 可添加文件上传功能

---

## 附录 A：快速开始

```bash
# 1. 进入项目目录
cd smart-agent-hub

# 2. 安装依赖（如果需要）
pip install -e ".[dashboard]"

# 3. 启动 Dashboard
streamlit run dashboard/app.py --server.port 8502

# 4. 访问聊天页面
# 浏览器打开 http://localhost:8502
# 点击侧边栏 "💬 Chat"
```

## 附录 B：与现有功能的对比

| 功能 | 命令行 (CLI) | Dashboard (只读) | Dashboard (聊天) |
|------|-------------|-----------------|-----------------|
| 发送查询 | ✅ | ❌ | ✅ |
| 查看历史 | ❌ | ✅ | ✅ (侧边栏) |
| 流式显示 | ✅ (verbose) | ❌ | ✅ |
| 多轮对话 | ⚠️ (需 session) | ❌ | ✅ |
| 可视化执行 | ❌ | ✅ | ⚠️ (简化版) |

---

**文档版本**: 0.1  
**最后更新**: 2026-03-17  
**状态**: 实现中