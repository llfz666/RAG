# 智能客服 Agent 使用指南

本文档介绍智能客服系统的架构、模块功能和使用方法。

---

## 📋 目录

1. [概述](#概述)
2. [系统架构](#系统架构)
3. [模块介绍](#模块介绍)
4. [快速开始](#快速开始)
5. [API 参考](#api 参考)
6. [使用示例](#使用示例)

---

## 概述

智能客服系统是专为广告公司设计的对话式 AI 助手，具备以下核心能力：

- **意图识别**: 理解用户咨询的意图（服务咨询、报价、周期等）
- **情感理解**: 识别用户情绪（高兴、愤怒、焦急等）并给出共情回应
- **多轮对话**: 支持槽位填充、上下文追踪的完整对话流程
- **智能回复**: 根据意图和情感生成合适的回复

### 支持的意图类型

| 意图 | 描述 | 示例 |
|------|------|------|
| `service_inquiry` | 服务咨询 | "你们提供哪些服务？" |
| `price_quote` | 报价咨询 | "Logo 设计多少钱？" |
| `case_portfolio` | 案例展示 | "能看看你们的作品吗？" |
| `timeline` | 周期咨询 | "多久能做完？" |
| `revision` | 修改请求 | "这个要改一下" |
| `urgent` | 紧急需求 | "很急，明天要" |
| `follow_up` | 进度跟进 | "项目进度怎么样了？" |
| `complaint` | 投诉 | "设计太差了" |
| `handoff` | 转人工 | "转人工客服" |
| `greeting` | 问候 | "你好" |
| `farewell` | 告别 | "再见" |

---

## 系统架构

```
smart-agent-hub/
├── agent/
│   ├── intent/           # 意图识别模块
│   │   ├── models.py     # 数据模型（IntentType, Entity, IntentResult）
│   │   ├── classifier.py # 意图分类器
│   │   └── __init__.py
│   ├── sentiment/        # 情感分析模块
│   │   ├── models.py     # 数据模型（SentimentType, EmotionType）
│   │   ├── analyzer.py   # 情感分析器
│   │   └── __init__.py
│   ├── dialogue/         # 对话管理模块
│   │   ├── models.py     # 对话上下文模型
│   │   ├── manager.py    # 对话管理器
│   │   └── __init__.py
│   └── core/
│       ├── agent.py      # 基础 Agent 类
│       └── planner.py    # ReAct 规划器
├── data/
│   └── customer_service/ # 客服数据
│       ├── faq.json
│       ├── intent_examples.json
│       └── dialogue_samples.json
└── scripts/
    └── generate_customer_service_data.py  # 数据生成脚本
```

---

## 模块介绍

### 1. 意图识别模块 (`agent.intent`)

**功能**: 识别用户输入的意图并提取实体

**核心类**:
- `IntentClassifier`: 意图分类器，支持基于规则和 LLM 两种模式
- `IntentType`: 意图类型枚举
- `IntentResult`: 意图识别结果

**使用示例**:
```python
from agent.intent import IntentClassifier, IntentType

# 创建分类器（基于规则模式）
classifier = IntentClassifier(use_rule_based=True)

# 分类用户输入
result = classifier.classify("Logo 设计多少钱？")
print(result.intent)  # IntentType.PRICE_QUOTE
print(result.entities)  # 提取的实体
```

### 2. 情感分析模块 (`agent.sentiment`)

**功能**: 分析用户输入的情感和情绪

**核心类**:
- `SentimentAnalyzer`: 情感分析器
- `SentimentType`: 情感类型（positive/neutral/negative）
- `EmotionType`: 情绪类型（joy/anger/sadness 等）
- `SentimentResult`: 情感分析结果

**使用示例**:
```python
from agent.sentiment import SentimentAnalyzer

# 创建分析器
analyzer = SentimentAnalyzer(use_rule_based=True)

# 分析情感
result = analyzer.analyze("你们的设计太差了，非常生气！")
print(result.sentiment)  # SentimentType.NEGATIVE
print(result.primary_emotion)  # EmotionType.ANGER
print(result.needs_empathy)  # True
```

### 3. 对话管理模块 (`agent.dialogue`)

**功能**: 管理对话状态、槽位填充和流程控制

**核心类**:
- `DialogueManager`: 对话管理器
- `DialogueContext`: 对话上下文
- `DialogueState`: 对话状态
- `FlowStage`: 流程阶段

**使用示例**:
```python
from agent.dialogue import DialogueManager, DialogueContext

# 创建对话管理器
manager = DialogueManager()

# 开始对话
greeting = manager.start_dialogue(user_id="user123")

# 处理用户输入
from agent.intent import IntentClassifier, IntentResult, IntentType
from agent.sentiment import SentimentAnalyzer

classifier = IntentClassifier(use_rule_based=True)
analyzer = SentimentAnalyzer(use_rule_based=True)

user_input = "你们提供哪些设计服务？"
intent_result = classifier.classify(user_input)
sentiment_result = analyzer.analyze(user_input)

response, state = manager.process_input(
    user_input=user_input,
    intent_result=intent_result,
    sentiment_result=sentiment_result,
)
print(response)  # 系统回复
```

---

## 快速开始

### 1. 生成客服数据

```bash
cd smart-agent-hub
python scripts/generate_customer_service_data.py
```

### 2. 测试意图识别

```python
from agent.intent import IntentClassifier

classifier = IntentClassifier(use_rule_based=True)

test_cases = [
    "你好",
    "Logo 设计多少钱？",
    "多久能做完？",
    "太丑了，要修改",
    "很急，明天要",
]

for text in test_cases:
    result = classifier.classify(text)
    print(f"输入：{text}")
    print(f"意图：{result.intent.value}")
    print(f"置信度：{result.confidence}")
    print()
```

### 3. 测试情感分析

```python
from agent.sentiment import SentimentAnalyzer

analyzer = SentimentAnalyzer(use_rule_based=True)

test_cases = [
    "非常满意，谢谢！",
    "设计太丑了，我要投诉",
    "很急，今天必须做好",
    "有点失望，不是想要的效果",
]

for text in test_cases:
    result = analyzer.analyze(text)
    print(f"输入：{text}")
    print(f"情感：{result.sentiment.value}")
    print(f"情绪：{result.primary_emotion.value if result.primary_emotion else '无'}")
    print(f"需要共情：{result.needs_empathy}")
    print()
```

### 4. 测试完整对话流程

```python
from agent.dialogue import DialogueManager
from agent.intent import IntentClassifier
from agent.sentiment import SentimentAnalyzer

# 初始化组件
manager = DialogueManager()
classifier = IntentClassifier(use_rule_based=True)
analyzer = SentimentAnalyzer(use_rule_based=True)

# 开始对话
print(manager.start_dialogue())

# 模拟对话
conversation = [
    "你们提供哪些服务？",
    "Logo 设计",
    "多少钱？",
    "简单一点的",
    "好的谢谢",
    "再见",
]

for user_input in conversation:
    intent_result = classifier.classify(user_input)
    sentiment_result = analyzer.analyze(user_input)
    
    response, state = manager.process_input(
        user_input=user_input,
        intent_result=intent_result,
        sentiment_result=sentiment_result,
    )
    
    print(f"用户：{user_input}")
    print(f"系统：{response}")
    print(f"状态：{state.value}")
    print()
```

---

## API 参考

### IntentClassifier

```python
class IntentClassifier:
    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        use_rule_based: bool = False,
    )
    
    async def classify(self, text: str) -> IntentResult:
        """对用户输入进行意图分类。"""
    
    def get_required_slots(self, intent: IntentType) -> list[str]:
        """获取指定意图所需的槽位。"""
```

### SentimentAnalyzer

```python
class SentimentAnalyzer:
    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        use_rule_based: bool = False,
    )
    
    async def analyze(self, text: str) -> SentimentResult:
        """分析文本的情感和情绪。"""
    
    def get_empathy_response(self, result: SentimentResult) -> str:
        """根据情感分析结果生成共情回应。"""
```

### DialogueManager

```python
class DialogueManager:
    def __init__(self, context: Optional[DialogueContext] = None)
    
    def start_dialogue(self, user_id: Optional[str] = None) -> str:
        """开始新的对话。"""
    
    def process_input(
        self,
        user_input: str,
        intent_result: IntentResult,
        sentiment_result: Optional[SentimentResult] = None,
    ) -> tuple[str, DialogueState]:
        """处理用户输入。"""
    
    def get_context(self) -> DialogueContext:
        """获取对话上下文。"""
    
    def reset(self) -> None:
        """重置对话。"""
```

---

## 使用示例

### 完整客服对话示例

```python
import asyncio
from agent.dialogue import DialogueManager
from agent.intent import IntentClassifier, IntentType
from agent.sentiment import SentimentAnalyzer

async def run_customer_service_demo():
    """运行客服对话演示。"""
    
    # 初始化组件
    manager = DialogueManager()
    classifier = IntentClassifier(use_rule_based=True)
    analyzer = SentimentAnalyzer(use_rule_based=True)
    
    # 开始对话
    print("=" * 50)
    print("智能客服演示")
    print("=" * 50)
    print()
    print(f"客服：{manager.start_dialogue()}")
    print()
    
    # 模拟用户输入序列
    user_inputs = [
        "你好",
        "我想做个 Logo 设计",
        "简单一点的",
        "多少钱？",
        "有点贵，能便宜吗",
        "好吧，多久能好？",
        "好的，谢谢",
        "再见",
    ]
    
    for user_input in user_inputs:
        # 意图识别
        intent_result = await classifier.classify(user_input)
        
        # 情感分析
        sentiment_result = await analyzer.analyze(user_input)
        
        # 处理输入
        response, state = manager.process_input(
            user_input=user_input,
            intent_result=intent_result,
            sentiment_result=sentiment_result,
        )
        
        print(f"用户：{user_input}")
        print(f"客服：{response}")
        print(f"意图：{intent_result.intent.value}")
        print(f"情感：{sentiment_result.sentiment.value}")
        print("-" * 50)
        print()

if __name__ == "__main__":
    asyncio.run(run_customer_service_demo())
```

---

## 数据格式

### FAQ 数据格式

```json
[
  {
    "category": "service_inquiry",
    "question": "你们公司提供哪些服务？",
    "answer": "我们提供品牌设计...",
    "keywords": ["服务", "业务"]
  }
]
```

### 意图示例数据格式

```json
[
  {
    "text": "Logo 设计多少钱？",
    "intent": "price_quote",
    "confidence": 1.0
  }
]
```

### 对话数据格式

```json
[
  {
    "scenario": "service_inquiry",
    "turns": [
      {"user": "你好", "system": "您好！..."},
      {"user": "你们提供哪些服务？", "system": "..."}
    ],
    "metadata": {
      "total_turns": 5,
      "created_at": "2026-03-26T19:00:00"
    }
  }
]
```

---

## 扩展与定制

### 添加新的意图类型

1. 在 `agent/intent/models.py` 中添加新的 `IntentType`
2. 在 `IntentClassifier._init_rule_patterns()` 中添加关键词映射
3. 在 `DialogueManager` 中添加对应的回复处理方法

### 添加新的情感类型

1. 在 `agent/sentiment/models.py` 中添加新的 `EmotionType`
2. 在 `SentimentAnalyzer._init_patterns()` 中添加关键词映射
3. 更新 `EMOTION_RESPONSE_STRATEGIES` 映射

### 定制回复模板

在 `DialogueManager.__init__()` 中修改模板：

```python
self.greeting_templates = [
    "您的自定义问候语",
]

self.request_templates = {
    "service_type": "您的自定义请求话术",
}
```

---

## 注意事项

1. **LLM Provider 费用**: 使用 LLM 模式会产生 API 调用费用，建议开发时使用规则模式
2. **数据隐私**: 对话数据可能包含用户敏感信息，注意数据保护
3. **并发处理**: 生产环境需考虑并发对话的上下文隔离

---

## 相关文档

- [Agent 使用指南](./AGENT_USAGE_GUIDE.md)
- [对话 dashboard 规格](./CHAT_DASHBOARD_SPEC.md)
- [对话 dashboard 使用指南](./CHAT_DASHBOARD_USAGE_GUIDE.md)