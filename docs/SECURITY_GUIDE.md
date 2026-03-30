# 企业级安全模块使用指南

## 📋 目录

- [概述](#概述)
- [安装与配置](#安装与配置)
- [密钥管理](#密钥管理)
- [输入验证](#输入验证)
- [输出过滤](#输出过滤)
- [安全审计日志](#安全审计日志)
- [速率限制](#速率限制)
- [集成示例](#集成示例)
- [最佳实践](#最佳实践)

---

## 概述

本安全模块为企业级 RAG 系统提供全面的安全防护功能：

| 模块 | 功能 | 状态 |
|------|------|------|
| `secret_manager.py` | 密钥管理（环境变量/加密配置/密钥管理服务） | ✅ 完成 |
| `input_validator.py` | 输入验证（Prompt 注入/SQL 注入/路径遍历/XSS 等） | ✅ 完成 |
| `output_filter.py` | 输出过滤（PII 脱敏/密钥过滤/数据分级） | ✅ 完成 |
| `audit_logger.py` | 安全审计日志 | ✅ 完成 |
| `rate_limiter.py` | 速率限制 | ✅ 完成 |
| `auth.py` | JWT 认证授权 | 🚧 待实现 |
| `rbac.py` | 基于角色的访问控制 | 🚧 待实现 |
| `anomaly_detector.py` | 异常检测 | 🚧 待实现 |

---

## 安装与配置

### 依赖安装

```bash
# 安装加密依赖
pip install cryptography

# 安装可选依赖（用于密钥管理服务）
pip install boto3 azure-keyvault-secrets google-cloud-secret-manager
```

### 环境变量配置

```bash
# 方式 1: 直接设置 API 密钥（推荐用于开发）
export OPENAI_API_KEY="sk-..."
export QWEN_API_KEY="..."

# 方式 2: 设置加密主密钥（用于解密配置）
export MASTER_KEY="your-master-key-at-least-32-chars"

# 方式 3: 设置加密的 API 密钥
export LLM_API_KEY_ENCRYPTED="AES256:base64encodedciphertext..."
```

---

## 密钥管理

### 基本使用

```python
from src.security import SecretManager, get_secret, get_api_key

# 方式 1: 使用便捷函数
api_key = get_secret("OPENAI_API_KEY", required=True)

# 方式 2: 使用类方法
api_key = SecretManager.get("OPENAI_API_KEY", default="fallback-key")

# 方式 3: 获取特定 Provider 的 API 密钥
api_key = get_api_key("qwen")  # 依次查找 QWEN_API_KEY -> LLM_API_KEY
```

### 从配置读取密钥

```python
from src.security import SecretManager

config = {
    "llm": {
        "api_key": "plain-key",  # 明文（不推荐）
        "api_key_encrypted": "AES256:..."  # 加密
    }
}

# 读取明文密钥
api_key = SecretManager.get_from_config(config, "llm.api_key")

# 读取加密密钥
api_key = SecretManager.get_from_config(config, "llm.api_key_encrypted", encrypted=True)
```

### 从密钥管理服务读取

```python
from src.security import SecretManager

# AWS Secrets Manager
api_key = SecretManager.get_from_secrets_manager("aws-secrets-manager:/prod/rag/llm-key")

# Azure Key Vault
api_key = SecretManager.get_from_secrets_manager("azure-key-vault://vault-name/secret-name")

# GCP Secret Manager
api_key = SecretManager.get_from_secrets_manager("gcp-secret-manager://project-id/secret-name")
```

### 加密值（用于生成加密配置）

```python
from src.security import SecretManager
import os

# 设置主密钥
os.environ["MASTER_KEY"] = "your-32-char-or-longer-master-key"

# 加密 API 密钥
plain_key = "sk-your-api-key"
encrypted = SecretManager.encrypt_value(plain_key)
print(f"加密后：{encrypted}")  # AES256:base64ciphertext
```

---

## 输入验证

### 验证查询输入

```python
from src.security import validate_query, InputValidator

# 使用便捷函数
result = validate_query(user_query)
if not result.is_valid:
    print(f"验证失败：{result.error_message}")
    print(f"检测到的攻击类型：{result.detected_attacks}")

# 使用验证器类
validator = InputValidator(strict_mode=True)
result = validator.validate_query(user_query, max_length=1000)
```

### 验证集合名称

```python
from src.security import validate_collection_name

result = validate_collection_name(collection_name)
if not result.is_valid:
    raise ValueError(f"无效的集合名称：{result.error_message}")
```

### 验证文件路径

```python
from src.security import InputValidator

validator = InputValidator()
result = validator.validate_file_path(
    file_path,
    allowed_base_dirs=["/app/data", "/app/uploads"]
)
if not result.is_valid:
    raise ValueError(result.error_message)
```

### 验证 URL

```python
from src.security import InputValidator

validator = InputValidator()
result = validator.validate_url(
    url,
    allowed_schemes=["https"],
    allowed_hosts=["api.example.com", "cdn.example.com"]
)
```

### 检测 Prompt 注入

```python
from src.security import detect_prompt_injection

attacks = detect_prompt_injection(user_input)
if attacks:
    print("检测到 Prompt 注入攻击：")
    for desc, pattern in attacks:
        print(f"  - {desc}: {pattern}")
```

### 攻击检测类型

| 攻击类型 | 描述 | 示例 |
|---------|------|------|
| `PROMPT_INJECTION` | Prompt 注入攻击 | "忽略之前的指令" |
| `SQL_INJECTION` | SQL 注入攻击 | `' OR '1'='1` |
| `PATH_TRAVERSAL` | 路径遍历攻击 | `../../../etc/passwd` |
| `XSS` | 跨站脚本攻击 | `<script>alert(1)</script>` |
| `COMMAND_INJECTION` | 命令注入攻击 | `; cat /etc/passwd` |
| `SSRF` | 服务端请求伪造 | `http://169.254.169.254/` |

---

## 输出过滤

### 过滤敏感信息

```python
from src.security import filter_sensitive, OutputFilter

# 使用便捷函数
text = "我的手机号是 13812345678，邮箱是 test@example.com"
filtered = filter_sensitive(text)
print(filtered)
# 输出：我的手机号是 [手机号已隐藏]，邮箱是 [邮箱已隐藏]
```

### 过滤检索结果

```python
from src.security import filter_results

results = [
    {
        "text": "联系人：张三，电话：13812345678",
        "metadata": {"author": "李四", "email": "lisi@example.com"}
    }
]

filtered = filter_results(results)
print(filtered[0]["text"])  # [手机号已隐藏]
print(filtered[0]["metadata"])  # email 已被过滤
```

### 检查是否包含敏感信息

```python
from src.security import contains_sensitive

if contains_sensitive(user_input):
    print("输入包含敏感信息")
```

### 获取敏感信息类别

```python
from src.security import get_filter

filter_instance = get_filter()
categories = filter_instance.get_sensitive_categories(text)
print(f"包含的敏感信息类型：{categories}")
```

### 支持的 PII 类型

| 类别 | 描述 | 脱敏后 |
|------|------|--------|
| `PHONE` | 手机号 | `[手机号已隐藏]` |
| `EMAIL` | 邮箱 | `[邮箱已隐藏]` |
| `ID_CARD` | 身份证号 | `[身份证号已隐藏]` |
| `BANK_CARD` | 银行卡号 | `[银行卡号已隐藏]` |
| `IP_ADDRESS` | IP 地址 | `[IP 地址已隐藏]` |
| `API_KEY` | API 密钥 | `[API 密钥已隐藏]` |
| `URL` | URL | `[URL 已隐藏]` |
| `CREDIT_CARD` | 信用卡号 | `[信用卡号已隐藏]` |
| `PASSPORT` | 护照号 | `[护照号已隐藏]` |
| `LICENSE_PLATE` | 车牌号 | `[车牌号已隐藏]` |

### 数据分级控制

```python
from src.security import OutputFilter, DataClassification

# 设置最小数据分级
filter_instance = OutputFilter(min_classification=DataClassification.INTERNAL)

# 过滤文档
content, metadata = filter_instance.filter_document(
    content="机密文档内容",
    metadata={"classification": "confidential"},
    classification=DataClassification.CONFIDENTIAL
)
```

---

## 安全审计日志

### 记录安全事件

```python
from src.security.audit_logger import AuditLogger, SecurityEvent, EventSeverity

audit = AuditLogger()

# 记录认证事件
audit.log_auth_event(
    event_type=SecurityEvent.LOGIN_SUCCESS,
    user_id="user123",
    ip_address="192.168.1.1",
    details={"method": "password"}
)

# 记录安全事件（攻击检测）
audit.log_security_event(
    event_type=SecurityEvent.PROMPT_INJECTION_DETECTED,
    ip_address="10.0.0.1",
    details={"attack_type": "instruction_override"},
    severity=EventSeverity.CRITICAL
)

# 记录通用事件
audit.log_event(
    event_type=SecurityEvent.DATA_EXPORT,
    user_id="user123",
    resource="knowledge_base",
    details={"format": "csv", "rows": 1000}
)
```

### 便捷函数

```python
from src.security.audit_logger import log_event, log_auth_event, log_security_event, SecurityEvent

# 快速记录
log_event(SecurityEvent.SYSTEM_STARTUP)

# 记录认证事件
log_auth_event(SecurityEvent.LOGIN_FAILURE, user_id="user123", ip="192.168.1.1")

# 记录安全事件
log_security_event(SecurityEvent.SQL_INJECTION_DETECTED, ip="10.0.0.1")
```

### 查询审计日志

```python
from src.security.audit_logger import AuditLogger

audit = AuditLogger()

# 查询特定类型的事件
logs = audit.query_logs(
    event_type="auth.login",
    start_time="2024-01-01T00:00:00",
    end_time="2024-12-31T23:59:59",
    limit=100
)

for log in logs:
    print(f"{log.timestamp}: {log.event_type.value} - {log.user_id}")
```

### 事件类型

| 类别 | 事件类型 | 描述 |
|------|---------|------|
| `auth.*` | `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT` | 认证事件 |
| `authz.*` | `PERMISSION_DENIED`, `ACCESS_DENIED` | 授权事件 |
| `access.*` | `DATA_EXPORT`, `DATA_DELETE` | 访问事件 |
| `security.*` | `INPUT_VALIDATION_FAILED`, `PROMPT_INJECTION_DETECTED` | 安全事件 |
| `secret.*` | `SECRET_ACCESS`, `SECRET_ROTATION` | 密钥管理事件 |
| `system.*` | `CONFIG_CHANGED`, `SYSTEM_STARTUP` | 系统事件 |

---

## 速率限制

### 基本使用

```python
from src.security.rate_limiter import RateLimiter, RateLimitExceeded

limiter = RateLimiter(default_limit="100/minute")

# 检查是否允许
if limiter.is_allowed(user_id, endpoint="query"):
    # 执行查询
    result = execute_query()
else:
    raise RateLimitExceeded("请求过于频繁，请稍后再试")
```

### 使用装饰器

```python
from src.security.rate_limiter import limit_requests

@limit_requests("10/minute", endpoint="query")
def query_knowledge(user_id: str, query: str):
    return execute_query(query)

# 异步函数也支持
@limit_requests("5/second", endpoint="chat")
async def chat(user_id: str, message: str):
    return await process_chat(message)
```

### 检查速率限制状态

```python
from src.security.rate_limiter import check_rate_limit

result = check_rate_limit(user_id, endpoint="query", limit="10/minute")

print(f"允许：{result.allowed}")
print(f"当前计数：{result.current_count}")
print(f"剩余配额：{result.remaining}")
print(f"重置时间：{result.reset_at}")
print(f"重试等待：{result.retry_after}秒")
```

### 自定义限流器

```python
from src.security.rate_limiter import RateLimiter, RateLimitStrategy

# 使用令牌桶算法
limiter = RateLimiter(
    default_limit="10/second",
    strategy=RateLimitStrategy.TOKEN_BUCKET,
    whitelist={"admin_user", "service_account"},
    blacklist={"malicious_user"},
)

# 重置特定用户的限制
limiter.reset(user_id)
```

### 限流策略

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| `SLIDING_WINDOW` | 滑动窗口 | 精确限流，推荐默认使用 |
| `FIXED_WINDOW` | 固定窗口 | 简单场景 |
| `TOKEN_BUCKET` | 令牌桶 | 允许突发流量 |
| `LEAKY_BUCKET` | 漏桶 | 平滑输出速率 |

---

## 集成示例

### 在 MCP Server 中集成安全模块

```python
# src/mcp_server/server.py
from src.security import (
    validate_query,
    filter_sensitive,
    filter_results,
    get_secret,
    is_allowed,
    check_rate_limit,
)
from src.security.audit_logger import AuditLogger, SecurityEvent, EventSeverity

audit = AuditLogger()

@app.tool
async def query_knowledge_hub(
    query: str,
    top_k: int = 5,
    collection: Optional[str] = None,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict:
    """查询知识库"""
    
    # 1. 速率限制检查
    if user_id and not is_allowed(user_id, endpoint="query_knowledge", limit="10/minute"):
        result = check_rate_limit(user_id, endpoint="query_knowledge")
        audit.log_event(
            SecurityEvent.RATE_LIMIT_EXCEEDED,
            user_id=user_id,
            ip_address=ip_address,
            details={"endpoint": "query_knowledge"}
        )
        raise RateLimitExceeded(
            f"请求过于频繁，请等待{result.retry_after:.0f}秒后重试"
        )
    
    # 2. 输入验证
    validation_result = validate_query(query)
    if not validation_result.is_valid:
        audit.log_event(
            SecurityEvent.INPUT_VALIDATION_FAILED,
            user_id=user_id,
            ip_address=ip_address,
            details={
                "query_preview": query[:100],
                "error": validation_result.error_message,
                "attacks": [a.value for a in validation_result.detected_attacks]
            },
            severity=EventSeverity.WARNING
        )
        raise ValueError(f"输入验证失败：{validation_result.error_message}")
    
    # 3. 记录查询开始
    audit.log_event(
        SecurityEvent.RESOURCE_ACCESS,
        user_id=user_id,
        ip_address=ip_address,
        details={"endpoint": "query_knowledge", "query_preview": query[:50]}
    )
    
    # 4. 执行查询
    results = await knowledge_base.search(query, top_k=top_k, collection=collection)
    
    # 5. 过滤敏感信息
    filtered_results = filter_results(results)
    
    # 6. 记录查询成功
    audit.log_event(
        SecurityEvent.ACCESS_GRANTED,
        user_id=user_id,
        ip_address=ip_address,
        details={"results_count": len(filtered_results)}
    )
    
    return {"results": filtered_results}
```

### 在配置加载时使用密钥管理

```python
# src/core/settings.py
from src.security import SecretManager, get_api_key

def load_llm_settings(data: dict) -> LLMSettings:
    # 优先从环境变量获取
    api_key = get_api_key(data.get("provider", ""))
    
    # 如果没有环境变量，尝试从配置获取
    if not api_key:
        api_key = SecretManager.get_from_config(
            data,
            "llm.api_key",
            encrypted=data.get("api_key_encrypted") is not None
        )
    
    return LLMSettings(
        provider=data["provider"],
        model=data["model"],
        api_key=api_key,
        # ... 其他设置
    )
```

### 在数据导入时使用输出过滤

```python
# src/ingestion/pipeline.py
from src.security import filter_sensitive, contains_sensitive

def process_document(content: str, metadata: dict) -> dict:
    # 检查是否包含敏感信息
    if contains_sensitive(content):
        logger.warning("文档包含敏感信息，进行脱敏处理")
        content = filter_sensitive(content)
    
    # 过滤元数据中的敏感信息
    if "author_email" in metadata:
        metadata["author_email"] = filter_sensitive(metadata["author_email"])
    
    return {"content": content, "metadata": metadata}
```

---

## 最佳实践

### 1. 密钥管理

- ✅ **永远不要**在代码中硬编码密钥
- ✅ **始终**使用环境变量或密钥管理服务
- ✅ 定期轮换密钥（建议 90 天）
- ✅ 使用不同的密钥用于开发/测试/生产环境
- ✅ 限制密钥的访问权限（最小权限原则）

### 2. 输入验证

- ✅ 对所有用户输入进行验证
- ✅ 使用白名单而非黑名单
- ✅ 设置合理的长度限制
- ✅ 记录所有验证失败事件
- ✅ 对检测到的攻击进行告警

### 3. 输出过滤

- ✅ 对所有输出进行敏感信息检查
- ✅ 根据数据分级设置过滤策略
- ✅ 在日志中也进行敏感信息脱敏
- ✅ 定期更新 PII 模式以覆盖新类型

### 4. 审计日志

- ✅ 记录所有安全相关事件
- ✅ 使用结构化日志（JSON 格式）
- ✅ 将日志发送到 SIEM 系统
- ✅ 定期审查审计日志
- ✅ 设置异常事件告警

### 5. 速率限制

- ✅ 对所有 API 端点设置速率限制
- ✅ 为不同用户角色设置不同限制
- ✅ 使用滑动窗口获得更精确的限流
- ✅ 对超出限制的行为进行记录和告警
- ✅ 为关键服务设置白名单

---

## 故障排除

### 常见问题

**Q: 密钥解密失败 "Master key not found"**

A: 确保设置了 `MASTER_KEY` 或 `ENCRYPTION_KEY` 环境变量：
```bash
export MASTER_KEY="your-32-char-or-longer-key"
```

**Q: 输入验证过于严格，误判正常输入**

A: 调整验证器配置：
```python
validator = InputValidator(strict_mode=False, log_violations=True)
```

**Q: 速率限制影响正常用户**

A: 为正常用户设置白名单或提高限制：
```python
limiter = RateLimiter(
    default_limit="100/minute",
    whitelist={"trusted_user_1", "trusted_user_2"}
)
```

---

## 待实现功能

以下功能正在开发中：

| 模块 | 功能描述 | 优先级 |
|------|---------|--------|
| `auth.py` | JWT 认证、Token 管理 | P1 |
| `rbac.py` | 基于角色的访问控制 | P2 |
| `anomaly_detector.py` | 异常行为检测 | P3 |
| `compliance.py` | 合规报告生成 | P3 |
| `data_retention.py` | 数据保留策略 | P3 |

---

## 相关文档

- [MCP 工具使用指南](./MCP_TOOLS_GUIDE.md)
- [Token 监控指南](./TOKEN_MONITOR_GUIDE.md)
- [快速开始指南](./QUICK_START_GUIDE.md)