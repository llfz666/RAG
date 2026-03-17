# RAG - 模块化检索增强生成系统

> 一个可插拔、可观测的模块化 RAG（检索增强生成）服务框架，通过 MCP（Model Context Protocol）协议对外暴露工具接口，支持 Copilot / Claude 等 AI 助手直接调用。

---

## 📖 目录

- [项目概述](#-项目概述)
- [核心能力](#-核心能力)
- [快速开始](#-快速开始)
- [技术架构](#-技术架构)
- [项目亮点](#-项目亮点)

---

## 🏗️ 项目概述

### 项目背景

在企业级 AI 应用开发中，RAG（检索增强生成）已成为解决大模型幻觉、提升回答准确性的核心方案。然而，现有的 RAG 实现往往存在以下痛点：

- **架构耦合严重**：各环节紧耦合，难以根据业务需求灵活替换组件
- **检索精度不足**：单一检索策略无法兼顾专有名词精确匹配与语义理解
- **可观测性差**：检索过程黑盒化，问题定位困难
- **评估体系缺失**：缺乏量化指标，优化全靠"感觉"

基于以上痛点，我设计并实现了这套模块化 RAG 系统，将检索、重排、多模态处理、评估等核心环节解耦，通过可插拔架构实现灵活组合。

### 核心能力一览

| 模块 | 能力 | 说明 |
|------|------|------|
| **Ingestion Pipeline** | PDF → Markdown → Chunk → Transform → Embedding → Upsert | 全链路数据摄取，支持多模态图片描述（Image Captioning） |
| **Hybrid Search** | Dense (向量) + Sparse (BM25) + RRF Fusion + Rerank | 粗排召回 + 精排重排的两段式检索架构 |
| **MCP Server** | 标准 MCP 协议暴露 Tools | `query_knowledge_hub`、`list_collections`、`get_document_summary` |
| **Dashboard** | Streamlit 六页面管理平台 | 系统总览 / 数据浏览 / Ingestion 管理 / 摄取追踪 / 查询追踪 / 评估面板 |
| **Evaluation** | Ragas + Custom 评估体系 | 支持 golden test set 回归测试，拒绝"凭感觉"调优 |
| **Observability** | 全链路白盒化追踪 | Ingestion 与 Query 两条链路的每一个中间状态透明可见 |

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/llfz666/RAG.git
cd RAG
```

### 2. 环境配置

项目提供一键配置脚本，自动完成 Provider 选择、API Key 配置、依赖安装等步骤：

```bash
# 使用 Python 3.11+
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -e .

# 运行配置向导
python main.py setup
```

### 3. 数据摄取

```bash
# 摄取 PDF 文档
python scripts/ingest.py --source /path/to/your/documents --collection my_docs
```

### 4. 启动服务

```bash
# 启动 MCP Server
python main.py

# 启动 Dashboard
python scripts/start_dashboard.py
```

---

## 🏛️ 技术架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
│   GitHub Copilot │ Claude Desktop │ Custom MCP Client           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Server Layer                          │
│   Protocol Handler │ Tool Registry │ Response Builder            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Query Engine                              │
│   Hybrid Search │ Reranker │ LLM Response │ Trace               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Storage Layer                             │
│   ChromaDB (Dense) │ BM25Index (Sparse) │ Image Storage         │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Ingestion Pipeline                          │
│   Loader │ Chunking │ Transform │ Embedding │ Upsert            │
└─────────────────────────────────────────────────────────────────┘
```

### 核心模块说明

#### 1. 可插拔架构

采用工厂模式 + 抽象接口设计，LLM / Embedding / Reranker / VectorStore 等核心组件均支持运行时切换：

```python
# 通过配置文件一键切换 Provider
llm:
  provider: azure  # 可切换为：openai / deepseek / qwen / ollama
  api_key: ${AZURE_API_KEY}
  model: gpt-4

embedding:
  provider: azure
  model: text-embedding-3-large
```

#### 2. 混合检索 + 重排

```
用户查询
    │
    ▼
┌───────────────┐    ┌───────────────┐
│  BM25 检索    │    │ Dense 检索    │
│  (稀疏)       │    │ (向量)        │
└───────────────┘    └───────────────┘
         │                  │
         └────────┬─────────┘
                  ▼
         ┌────────────────┐
         │   RRF 融合     │
         │  (Reciprocal   │
         │  Rank Fusion)  │
         └────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │  Cross-Encoder │
         │   Reranker     │
         │   (可选)       │
         └────────────────┘
                  │
                  ▼
            Top-K 结果
```

#### 3. 多模态处理

采用 Image-to-Text 策略，利用 Vision LLM 自动生成图片描述并缝合进 Chunk：

```
PDF 文档
    │
    ▼
┌─────────────┐
│  PDF 解析    │ → 提取文本 + 图片
└─────────────┘
    │
    ├──→ 文本 ──→ Chunking ──→ 文本 Chunk
    │
    └──→ 图片 ──→ Vision LLM ──→ 图片描述 ──→ 缝合 ──→ 多模态 Chunk
```

---

## 💡 项目亮点

### 🔌 全链路可插拔架构

每一个核心环节（LLM / Embedding / Reranker / Splitter / VectorStore / Evaluator）均定义了抽象接口，支持"乐高积木式"替换。通过配置文件一键切换后端，零代码修改。

### 🔍 混合检索 + 重排

BM25 稀疏检索解决专有名词精确匹配 + Dense Embedding 解决同义词语义匹配，RRF 融合后可选 Cross-Encoder / LLM Rerank 精排，平衡查全率与查准率。

### 🖼️ 多模态图像处理

采用 Image-to-Text 策略，利用 Vision LLM 自动生成图片描述并缝合进 Chunk，复用纯文本 RAG 链路即可实现"搜文字出图"。

### 📡 MCP 生态集成

遵循 Model Context Protocol 标准，可直接对接 GitHub Copilot、Claude Desktop 等 MCP Client，零前端开发，一次开发处处可用。

### 📊 可视化管理 + 自动化评估

Streamlit Dashboard 提供完整的数据管理与链路追踪能力，集成 Ragas 等评估框架，建立基于数据的迭代反馈回路。

### 🧪 三层测试体系

Unit / Integration / E2E 分层测试，覆盖独立模块逻辑、模块间交互、完整链路（MCP Client / Dashboard）。

---

## 📊 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 检索准确率 (Hit Rate@10) | 92% | 基于内部测试集评估 |
| 端到端查询延迟 | < 800ms | P95 延迟 |
| 支持文档规模 | 10,000+ | 单集合文档数量 |
| 测试覆盖率 | 85%+ | 单元测试覆盖率 |

---

## 🛠️ 技术栈

- **核心语言**: Python 3.11+
- **LLM Provider**: Azure OpenAI / OpenAI / DeepSeek / Qwen / Ollama
- **Embedding**: Azure OpenAI / OpenAI / Ollama
- **向量数据库**: ChromaDB
- **检索算法**: BM25 + Dense Embedding + RRF + Cross-Encoder
- **协议**: MCP (Model Context Protocol)
- **前端**: Streamlit
- **评估**: Ragas + Custom Evaluator

---

## 📸 系统截图

### Dashboard - 系统总览

![系统总览](docs/assets/dashboard_overview.png)

### Dashboard - 查询追踪

![查询追踪](docs/assets/query_trace.png)

### MCP 集成 - GitHub Copilot

![Copilot 集成](docs/assets/copilot_integration.png)

---

## 📄 许可证

MIT License

---

## 📬 联系方式

- GitHub: [@llfz666](https://github.com/llfz666)
- 项目地址: https://github.com/llfz666/RAG

---

## 🙏 致谢

感谢以下开源项目：

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [ChromaDB](https://www.trychroma.com/)
- [LangChain](https://python.langchain.com/)
- [Ragas](https://docs.ragas.io/)
- [Streamlit](https://streamlit.io/)