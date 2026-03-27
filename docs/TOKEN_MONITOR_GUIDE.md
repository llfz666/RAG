# Token Monitor 使用指南

## 概述

Token Monitor 是一个完整的 LLM Token 使用监控和预算管理系统，提供：

- ✅ 实时 Token 使用追踪
- ✅ 成本计算和统计
- ✅ 预算管理和告警
- ✅ 用户级别用量分析
- ✅ Streamlit 可视化面板

## 快速开始

### 1. 配置

在 `config/settings.yaml` 中配置 Token Monitor：

```yaml
token_monitor:
  enabled: true
  
  # 存储配置
  database_path: "data/token_usage.db"
  log_file: "logs/token_usage.jsonl"
  
  # 预算配置
  budgets:
    default_daily: 10.0      # 默认每日预算（元）
    default_monthly: 300.0   # 默认每月预算（元）
    alert_threshold: 0.8     # 告警阈值（80%）
  
  # 告警配置
  alerts:
    enabled: true
  
  # 采样配置（高并发场景）
  sampling:
    enabled: false
    rate: 1.0  # 1.0 = 全量记录
```

### 2. 初始化

```python
from src.observability.token_monitor import global_registry

# 初始化 Token Monitor
global_registry.initialize("config/settings.yaml")

# 获取 tracker 和 budget manager
tracker = global_registry.tracker
budget_manager = global_registry.budget_manager
```

### 3. 记录 Token 使用

```python
# 手动记录
usage = tracker.record(
    model="gpt-4",
    prompt_tokens=1000,
    completion_tokens=500,
    user_id="user_123",
    session_id="session_abc",
    task_type="chat",
    sync=True  # 同步写入
)

print(f"本次调用成本：¥{usage.cost:.4f}")
```

### 4. 使用拦截器自动追踪

```python
from openai import OpenAI
from src.observability.token_monitor import global_registry

# 创建拦截客户端
client = OpenAI(api_key="your-key")
interceptor = global_registry.interceptor
tracked_client = interceptor.wrap_openai(client)

# 现在所有调用都会自动记录
response = tracked_client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}],
    _user_id="user_123",      # 可选：用户 ID
    _session_id="session_abc", # 可选：会话 ID
    _task_type="chat",         # 可选：任务类型
)
```

### 5. 查询统计

```python
# 获取总体统计
stats = tracker.get_stats(days=7)
print(f"总 Token: {stats.total_tokens}")
print(f"总成本：¥{stats.total_cost:.2f}")
print(f"总调用：{stats.total_requests}")

# 按模型分组
for model, data in stats.by_model.items():
    print(f"{model}: ¥{data['total_cost']:.2f}")

# 获取模型用量明细
breakdown = tracker.get_model_breakdown(days=7)
for item in breakdown:
    print(f"{item.model}: {item.total_tokens} tokens")

# 获取用户用量排名
user_breakdown = tracker.get_user_breakdown(days=7)
for item in user_breakdown:
    print(f"{item.user_id}: ¥{item.total_cost:.2f}")

# 获取最近使用记录
recent = tracker.get_recent_usage(limit=10)
for record in recent:
    print(f"{record.timestamp}: {record.model} - ¥{record.cost:.2f}")
```

### 6. 预算检查

```python
# 检查预算状态
status = budget_manager.check_budget()
print(f"今日已用：¥{status.today_cost:.2f}")
print(f"今日剩余：¥{status.remaining_daily:.2f}")
print(f"使用率：{status.daily_usage_ratio*100:.1f}%")

# 检查是否可以继续
can_proceed, message = budget_manager.can_proceed(estimated_cost=0.5)
if not can_proceed:
    print(f"预算不足：{message}")

# 设置用户自定义预算
budget_manager.set_budget("user_123", daily=20.0, monthly=600.0)
```

## Streamlit Dashboard

启动 Token 使用监控面板：

```bash
streamlit run src/observability/dashboard/pages/token_usage.py
```

面板功能：
- 📊 实时预算状态（今日/本月）
- 📈 总体用量统计
- 🤖 模型用量排名
- 👤 用户用量排名
- 📝 最近使用记录
- 🚨 告警历史

## API 参考

### TokenTracker

| 方法 | 描述 |
|------|------|
| `record(...)` | 记录一次 Token 使用 |
| `get_stats(days, user_id)` | 获取用量统计 |
| `get_today_usage(user_id)` | 获取今日用量 |
| `get_month_usage(user_id)` | 获取本月用量 |
| `get_model_breakdown(days)` | 获取模型用量明细 |
| `get_user_breakdown(days)` | 获取用户用量明细 |
| `get_recent_usage(limit)` | 获取最近使用记录 |
| `flush()` | 刷新缓冲区 |

### BudgetManager

| 方法 | 描述 |
|------|------|
| `check_budget(user_id)` | 检查预算状态 |
| `can_proceed(estimated_cost)` | 检查是否可以继续 |
| `set_budget(user_id, daily, monthly)` | 设置用户预算 |
| `get_user_budget(user_id)` | 获取用户预算配置 |
| `get_alerts(days, unresolved_only)` | 获取告警列表 |
| `resolve_alert(alert_id)` | 标记告警已解决 |
| `check_and_alert()` | 检查并触发告警 |

### TokenInterceptor

| 方法 | 描述 |
|------|------|
| `wrap_openai(client)` | 包装 OpenAI 客户端 |
| `wrap_qwen(client)` | 包装 Qwen 客户端 |
| `track(user_id, session_id, task_type)` | 装饰器追踪 |

## 环境变量

可以通过环境变量覆盖配置：

```bash
export TOKEN_MONITOR_ENABLED=true
export TOKEN_MONITOR_DAILY_BUDGET=20.0
export TOKEN_MONITOR_MONTHLY_BUDGET=600.0
export TOKEN_MONITOR_ALERT_THRESHOLD=0.9
```

## 模型定价

系统内置了常见模型的定价（每 1K tokens，单位：元）：

| 模型 | 输入 | 输出 |
|------|------|------|
| GPT-4 | ¥0.064 | ¥0.128 |
| GPT-4 Turbo | ¥0.024 | ¥0.048 |
| GPT-4o | ¥0.028 | ¥0.084 |
| GPT-4o Mini | ¥0.0011 | ¥0.0033 |
| GPT-3.5 Turbo | ¥0.0035 | ¥0.0052 |
| Qwen Plus | ¥0.004 | ¥0.012 |
| Qwen Turbo | ¥0.002 | ¥0.006 |
| Qwen Max | ¥0.02 | ¥0.06 |
| DeepSeek Chat | ¥0.001 | ¥0.002 |

在配置文件中添加自定义定价：

```yaml
token_monitor:
  model_pricing:
    my-custom-model:
      input: 0.01
      output: 0.03
```

## 最佳实践

### 1. 批量写入优化

默认使用异步批量写入，避免频繁数据库操作：

```python
# 异步记录（默认，性能更好）
tracker.record(model="gpt-4", prompt_tokens=100, completion_tokens=50)

# 同步记录（需要立即获取成本）
tracker.record(model="gpt-4", prompt_tokens=100, completion_tokens=50, sync=True)
```

### 2. 用户隔离

为不同用户/会话设置标识：

```python
# 在应用启动时初始化
global_registry.initialize("config/settings.yaml")

# 在每次请求时传入用户信息
tracker.record(
    model="gpt-4",
    prompt_tokens=100,
    completion_tokens=50,
    user_id=request.user.id,
    session_id=request.session.id,
)
```

### 3. 预算告警处理

```python
# 在关键操作前检查预算
can_proceed, message = budget_manager.can_proceed(estimated_cost=1.0)
if not can_proceed:
    # 降级处理或提示用户
    logger.warning(f"预算检查失败：{message}")
    # 使用更便宜的模型或拒绝请求
```

### 4. 定期清理数据

```python
import sqlite3
from datetime import datetime, timedelta

# 清理 90 天前的数据
cutoff = (datetime.now() - timedelta(days=90)).isoformat()
conn = sqlite3.connect("data/token_usage.db")
conn.execute("DELETE FROM token_usage WHERE timestamp < ?", (cutoff,))
conn.commit()
conn.close()
```

## 故障排除

### 问题：数据库锁定

**原因**: 并发写入导致 SQLite 锁定

**解决方案**:
1. 启用 WAL 模式（已默认启用）
2. 增加超时时间
3. 减少同步写入频率

### 问题：成本计算不准确

**原因**: 模型名称不匹配

**解决方案**:
1. 检查模型名称拼写
2. 在配置中添加自定义定价
3. 使用完整模型名称（如 `azure/gpt-4`）

### 问题：Dashboard 无法启动

**原因**: 缺少依赖或配置错误

**解决方案**:
```bash
# 安装依赖
pip install streamlit

# 检查配置
python -c "from src.observability.token_monitor import global_registry; global_registry.initialize('config/settings.yaml')"
```

## 相关文件

- `src/observability/token_monitor/__init__.py` - 模块入口和注册表
- `src/observability/token_monitor/config.py` - 配置管理
- `src/observability/token_monitor/models.py` - 数据模型
- `src/observability/token_monitor/tracker.py` - Token 追踪器
- `src/observability/token_monitor/budget.py` - 预算管理
- `src/observability/token_monitor/interceptor.py` - LLM 拦截器
- `src/observability/dashboard/pages/token_usage.py` - Dashboard 页面
- `tests/unit/test_token_monitor.py` - 单元测试