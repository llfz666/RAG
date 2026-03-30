"""安全模块 - 企业级安全防护

本模块提供完整的企业级安全防护功能：

模块结构:
├── secret_manager.py    - 密钥管理（环境变量/加密配置/密钥管理服务）
├── input_validator.py   - 输入验证（Prompt 注入/SQL 注入/路径遍历/XSS 等）
├── output_filter.py     - 输出过滤（PII 脱敏/密钥过滤/数据分级）
├── audit_logger.py      - 安全审计日志
├── rate_limiter.py      - 速率限制
├── anomaly_detector.py  - 异常检测（待实现）
├── auth.py              - 认证授权（待实现）
└── rbac.py              - 基于角色的访问控制（待实现）

使用示例:
    from src.security import (
        SecretManager,      # 密钥管理
        InputValidator,     # 输入验证
        OutputFilter,       # 输出过滤
        validate_query,     # 便捷函数：验证查询
        filter_sensitive,   # 便捷函数：过滤敏感信息
        get_secret,         # 便捷函数：获取密钥
    )
    
    # 获取 API 密钥
    api_key = get_secret("LLM_API_KEY", required=True)
    
    # 验证用户输入
    result = validate_query(user_query)
    if not result.is_valid:
        raise ValueError(result.error_message)
    
    # 过滤输出
    safe_output = filter_sensitive(llm_response)
"""

from __future__ import annotations

import logging

# 导入密钥管理
from src.security.secret_manager import (
    SecretManager,
    SecretSource,
    SecretValue,
    get_secret,
    get_api_key,
    get_secret_manager,
)

# 导入输入验证
from src.security.input_validator import (
    InputValidator,
    ValidationResult,
    AttackType,
    validate_input,
    validate_query,
    validate_collection_name,
    get_validator,
    detect_prompt_injection,
)

# 导入输出过滤
from src.security.output_filter import (
    OutputFilter,
    DataClassification,
    PIICategory,
    PIIPattern,
    FilterResult,
    filter_sensitive,
    filter_results,
    contains_sensitive,
    get_filter,
    redact_range,
)

# 导入审计日志
from src.security.audit_logger import (
    AuditLogger,
    AuditEvent,
    SecurityEvent,
    EventSeverity,
    get_audit_logger,
    log_event,
    log_auth_event,
    log_security_event,
)

# 导入速率限制
from src.security.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    RateLimitConfig,
    RateLimitResult,
    RateLimitStrategy,
    get_rate_limiter,
    is_allowed,
    check_rate_limit,
    limit_requests,
)

# 模块版本
__version__ = "1.0.0"

# 模块作者
__author__ = "Modular RAG Security Team"

# 所有导出
__all__ = [
    # 版本信息
    "__version__",
    
    # 密钥管理
    "SecretManager",
    "SecretSource",
    "SecretValue",
    "get_secret",
    "get_api_key",
    "get_secret_manager",
    
    # 输入验证
    "InputValidator",
    "ValidationResult",
    "AttackType",
    "validate_input",
    "validate_query",
    "validate_collection_name",
    "get_validator",
    "detect_prompt_injection",
    
    # 输出过滤
    "OutputFilter",
    "DataClassification",
    "PIICategory",
    "PIIPattern",
    "FilterResult",
    "filter_sensitive",
    "filter_results",
    "contains_sensitive",
    "get_filter",
    "redact_range",
    
    # 审计日志
    "AuditLogger",
    "AuditEvent",
    "SecurityEvent",
    "EventSeverity",
    "get_audit_logger",
    "log_event",
    "log_auth_event",
    "log_security_event",
    
    # 速率限制
    "RateLimiter",
    "RateLimitExceeded",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitStrategy",
    "get_rate_limiter",
    "is_allowed",
    "check_rate_limit",
    "limit_requests",
]

# 配置日志
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def get_security_status() -> dict:
    """获取安全模块状态
    
    Returns:
        包含安全模块状态的字典
    """
    return {
        "version": __version__,
        "modules": {
            "secret_manager": "available",
            "input_validator": "available",
            "output_filter": "available",
            "audit_logger": "available",
            "rate_limiter": "available",
        },
        "features": {
            "key_management": True,
            "input_validation": True,
            "output_filtering": True,
            "prompt_injection_detection": True,
            "pii_redaction": True,
            "data_classification": True,
            "audit_logging": True,
            "rate_limiting": True,
        },
    }
