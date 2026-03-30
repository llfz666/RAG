"""安全审计日志服务 - 企业级安全事件记录

本模块提供全面的安全审计日志功能，记录：
1. 认证事件（登录成功/失败、Token 刷新）
2. 授权事件（权限变更、角色分配）
3. 访问事件（资源访问、数据导出）
4. 安全事件（攻击检测、异常行为）
5. 系统事件（配置变更、密钥轮换）

使用示例:
    from src.security.audit_logger import AuditLogger, SecurityEvent
    
    # 获取审计日志实例
    audit = AuditLogger()
    
    # 记录安全事件
    audit.log_event(SecurityEvent.LOGIN_SUCCESS, user_id="user123", ip="192.168.1.1")
    audit.log_event(SecurityEvent.INPUT_VALIDATION_FAILED, details={"attack_type": "sql_injection"})
    
    # 查询审计日志
    logs = audit.query_logs(event_type="auth.login", start_time="2024-01-01")
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SecurityEvent(str, Enum):
    """安全事件类型枚举"""
    
    # ==================== 认证事件 (auth.*) ====================
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_REFRESH = "auth.token.refresh"
    TOKEN_EXPIRED = "auth.token.expired"
    TOKEN_REVOKED = "auth.token.revoked"
    PASSWORD_CHANGED = "auth.password.changed"
    MFA_ENABLED = "auth.mfa.enabled"
    MFA_DISABLED = "auth.mfa.disabled"
    MFA_CHALLENGE = "auth.mfa.challenge"
    MFA_SUCCESS = "auth.mfa.success"
    MFA_FAILURE = "auth.mfa.failure"
    
    # ==================== 授权事件 (authz.*) ====================
    PERMISSION_DENIED = "authz.permission.denied"
    PERMISSION_GRANTED = "authz.permission.granted"
    ROLE_ASSIGNED = "authz.role.assigned"
    ROLE_REVOKED = "authz.role.revoked"
    ACCESS_GRANTED = "authz.access.granted"
    ACCESS_DENIED = "authz.access.denied"
    
    # ==================== 访问事件 (access.*) ====================
    RESOURCE_ACCESS = "access.resource"
    DATA_EXPORT = "access.data.export"
    DATA_IMPORT = "access.data.import"
    DATA_DELETE = "access.data.delete"
    DATA_MODIFY = "access.data.modify"
    API_ACCESS = "access.api"
    
    # ==================== 安全事件 (security.*) ====================
    INPUT_VALIDATION_FAILED = "security.input.validation.failed"
    PROMPT_INJECTION_DETECTED = "security.prompt.injection.detected"
    SQL_INJECTION_DETECTED = "security.sql.injection.detected"
    XSS_DETECTED = "security.xss.detected"
    PATH_TRAVERSAL_DETECTED = "security.path.traversal.detected"
    RATE_LIMIT_EXCEEDED = "security.rate.limit.exceeded"
    SUSPICIOUS_ACTIVITY = "security.suspicious.activity"
    BRUTE_FORCE_DETECTED = "security.brute.force.detected"
    ANOMALY_DETECTED = "security.anomaly.detected"
    
    # ==================== 密钥管理事件 (secret.*) ====================
    SECRET_ACCESS = "secret.access"
    SECRET_ROTATION = "secret.rotation"
    SECRET_CREATED = "secret.created"
    SECRET_DELETED = "secret.deleted"
    
    # ==================== 系统事件 (system.*) ====================
    CONFIG_CHANGED = "system.config.changed"
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    BACKUP_CREATED = "system.backup.created"
    MAINTENANCE_STARTED = "system.maintenance.started"
    MAINTENANCE_COMPLETED = "system.maintenance.completed"


class EventSeverity(str, Enum):
    """事件严重程度"""
    DEBUG = "debug"       # 调试信息
    INFO = "info"         # 一般信息
    NOTICE = "notice"     # 需要注意
    WARNING = "warning"   # 警告
    ERROR = "error"       # 错误
    CRITICAL = "critical" # 严重
    ALERT = "alert"       # 需要立即响应


@dataclass
class AuditEvent:
    """审计事件"""
    event_id: str
    event_type: SecurityEvent
    severity: EventSeverity
    timestamp: str
    timestamp_unix: float
    user_id: Optional[str] = None
    user_role: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    status: str = "success"  # success/failure
    details: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        """从字典创建"""
        return cls(**data)


class AuditLogger:
    """企业级安全审计日志器
    
    功能：
    1. 结构化日志（JSON 格式）
    2. 多目的地输出（文件/控制台/SIEM）
    3. 日志轮转
    4. 敏感信息脱敏
    5. 异步写入（高性能）
    """
    
    # 事件严重程度的默认映射
    DEFAULT_SEVERITY_MAP = {
        # 认证事件
        SecurityEvent.LOGIN_SUCCESS: EventSeverity.INFO,
        SecurityEvent.LOGIN_FAILURE: EventSeverity.WARNING,
        SecurityEvent.LOGOUT: EventSeverity.DEBUG,
        SecurityEvent.TOKEN_REFRESH: EventSeverity.DEBUG,
        SecurityEvent.TOKEN_EXPIRED: EventSeverity.NOTICE,
        SecurityEvent.TOKEN_REVOKED: EventSeverity.WARNING,
        SecurityEvent.PASSWORD_CHANGED: EventSeverity.INFO,
        SecurityEvent.MFA_ENABLED: EventSeverity.INFO,
        SecurityEvent.MFA_DISABLED: EventSeverity.WARNING,
        SecurityEvent.MFA_CHALLENGE: EventSeverity.DEBUG,
        SecurityEvent.MFA_SUCCESS: EventSeverity.INFO,
        SecurityEvent.MFA_FAILURE: EventSeverity.WARNING,
        
        # 授权事件
        SecurityEvent.PERMISSION_DENIED: EventSeverity.WARNING,
        SecurityEvent.PERMISSION_GRANTED: EventSeverity.INFO,
        SecurityEvent.ROLE_ASSIGNED: EventSeverity.INFO,
        SecurityEvent.ROLE_REVOKED: EventSeverity.INFO,
        SecurityEvent.ACCESS_GRANTED: EventSeverity.DEBUG,
        SecurityEvent.ACCESS_DENIED: EventSeverity.WARNING,
        
        # 访问事件
        SecurityEvent.RESOURCE_ACCESS: EventSeverity.DEBUG,
        SecurityEvent.DATA_EXPORT: EventSeverity.INFO,
        SecurityEvent.DATA_IMPORT: EventSeverity.INFO,
        SecurityEvent.DATA_DELETE: EventSeverity.WARNING,
        SecurityEvent.DATA_MODIFY: EventSeverity.INFO,
        SecurityEvent.API_ACCESS: EventSeverity.DEBUG,
        
        # 安全事件
        SecurityEvent.INPUT_VALIDATION_FAILED: EventSeverity.WARNING,
        SecurityEvent.PROMPT_INJECTION_DETECTED: EventSeverity.CRITICAL,
        SecurityEvent.SQL_INJECTION_DETECTED: EventSeverity.CRITICAL,
        SecurityEvent.XSS_DETECTED: EventSeverity.CRITICAL,
        SecurityEvent.PATH_TRAVERSAL_DETECTED: EventSeverity.CRITICAL,
        SecurityEvent.RATE_LIMIT_EXCEEDED: EventSeverity.WARNING,
        SecurityEvent.SUSPICIOUS_ACTIVITY: EventSeverity.ERROR,
        SecurityEvent.BRUTE_FORCE_DETECTED: EventSeverity.CRITICAL,
        SecurityEvent.ANOMALY_DETECTED: EventSeverity.ERROR,
        
        # 密钥管理事件
        SecurityEvent.SECRET_ACCESS: EventSeverity.INFO,
        SecurityEvent.SECRET_ROTATION: EventSeverity.INFO,
        SecurityEvent.SECRET_CREATED: EventSeverity.INFO,
        SecurityEvent.SECRET_DELETED: EventSeverity.WARNING,
        
        # 系统事件
        SecurityEvent.CONFIG_CHANGED: EventSeverity.WARNING,
        SecurityEvent.SYSTEM_STARTUP: EventSeverity.INFO,
        SecurityEvent.SYSTEM_SHUTDOWN: EventSeverity.INFO,
        SecurityEvent.BACKUP_CREATED: EventSeverity.INFO,
        SecurityEvent.MAINTENANCE_STARTED: EventSeverity.INFO,
        SecurityEvent.MAINTENANCE_COMPLETED: EventSeverity.INFO,
    }
    
    # 需要脱敏的字段
    SENSITIVE_FIELDS = {
        'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
        'private_key', 'access_key', 'credential', 'auth', 'authorization',
    }
    
    def __init__(
        self,
        log_file: Optional[str] = None,
        log_level: EventSeverity = EventSeverity.INFO,
        enable_console: bool = True,
        enable_file: bool = True,
        enable_async: bool = True,
        max_queue_size: int = 10000,
        flush_interval: int = 5,
        redact_sensitive: bool = True,
    ) -> None:
        """初始化审计日志器
        
        Args:
            log_file: 日志文件路径
            log_level: 最低日志级别
            enable_console: 是否输出到控制台
            enable_file: 是否输出到文件
            enable_async: 是否启用异步写入
            max_queue_size: 异步队列最大大小
            flush_interval: 异步刷新间隔（秒）
            redact_sensitive: 是否脱敏敏感字段
        """
        self.log_level = log_level
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.redact_sensitive = redact_sensitive
        
        # 确定日志文件路径
        if log_file is None:
            log_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "logs", "security_audit.jsonl"
            )
        self.log_file = log_file
        
        # 确保日志目录存在
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 异步写入相关
        self.enable_async = enable_async
        self._queue: List[AuditEvent] = []
        self._max_queue_size = max_queue_size
        self._flush_interval = flush_interval
        self._last_flush = time.time()
        
        # 事件计数器
        self._event_counts: Dict[str, int] = {}
        
        # 严重性映射
        self._severity_map = dict(self.DEFAULT_SEVERITY_MAP)
        
        # 事件 ID 计数器
        self._event_id_counter = 0
        
        logger.info(f"AuditLogger initialized, log file: {self.log_file}")
    
    def log_event(
        self,
        event_type: SecurityEvent,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        severity: Optional[EventSeverity] = None,
    ) -> AuditEvent:
        """记录安全事件
        
        Args:
            event_type: 事件类型
            user_id: 用户 ID
            user_role: 用户角色
            ip_address: IP 地址
            user_agent: 用户代理
            resource: 资源名称
            action: 操作名称
            status: 状态（success/failure）
            details: 详细信息
            session_id: 会话 ID
            request_id: 请求 ID
            severity: 事件严重程度（可选，自动推断）
            
        Returns:
            创建的审计事件
        """
        # 确定严重程度
        if severity is None:
            severity = self._severity_map.get(event_type, EventSeverity.INFO)
        
        # 检查是否应该记录
        if not self._should_log(severity):
            return None  # type: ignore
        
        # 生成事件 ID
        self._event_id_counter += 1
        event_id = f"audit_{int(time.time() * 1000)}_{self._event_id_counter}"
        
        # 脱敏敏感信息
        if details and self.redact_sensitive:
            details = self._redact_details(details)
        
        # 创建事件
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            timestamp=datetime.utcnow().isoformat(),
            timestamp_unix=time.time(),
            user_id=user_id,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            resource=resource,
            action=action,
            status=status,
            details=details or {},
            session_id=session_id,
            request_id=request_id,
        )
        
        # 更新计数
        type_key = event_type.value.split(".")[0]
        self._event_counts[type_key] = self._event_counts.get(type_key, 0) + 1
        
        # 写入日志
        self._write_event(event)
        
        return event
    
    def quick_log(
        self,
        event_type: SecurityEvent,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ) -> AuditEvent:
        """快速记录事件（简化版）
        
        Args:
            event_type: 事件类型
            details: 详细信息
            status: 状态
            
        Returns:
            创建的审计事件
        """
        return self.log_event(
            event_type=event_type,
            details=details,
            status=status,
        )
    
    def log_auth_event(
        self,
        event_type: SecurityEvent,
        user_id: str,
        ip_address: str,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ) -> AuditEvent:
        """记录认证相关事件"""
        return self.log_event(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            status=status,
        )
    
    def log_security_event(
        self,
        event_type: SecurityEvent,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: Optional[EventSeverity] = None,
    ) -> AuditEvent:
        """记录安全相关事件（攻击检测等）"""
        return self.log_event(
            event_type=event_type,
            ip_address=ip_address,
            details=details,
            status="failure",
            severity=severity,
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "event_counts": dict(self._event_counts),
            "total_events": sum(self._event_counts.values()),
            "queue_size": len(self._queue),
            "log_file": self.log_file,
        }
    
    def flush(self) -> None:
        """强制刷新队列"""
        if self._queue:
            self._flush_to_file()
    
    def close(self) -> None:
        """关闭日志器"""
        self.flush()
        logger.info("AuditLogger closed")
    
    # ==================== 内部方法 ====================
    
    def _should_log(self, severity: EventSeverity) -> bool:
        """检查是否应该记录该级别的事件"""
        severity_levels = {
            EventSeverity.DEBUG: 0,
            EventSeverity.INFO: 1,
            EventSeverity.NOTICE: 2,
            EventSeverity.WARNING: 3,
            EventSeverity.ERROR: 4,
            EventSeverity.CRITICAL: 5,
            EventSeverity.ALERT: 6,
        }
        return severity_levels.get(severity, 0) >= severity_levels.get(self.log_level, 1)
    
    def _write_event(self, event: AuditEvent) -> None:
        """写入事件"""
        if self.enable_async:
            self._queue.append(event)
            
            # 检查是否需要刷新
            if len(self._queue) >= self._max_queue_size:
                self._flush_to_file()
            elif time.time() - self._last_flush > self._flush_interval:
                self._flush_to_file()
        else:
            self._write_event_sync(event)
    
    def _write_event_sync(self, event: AuditEvent) -> None:
        """同步写入事件"""
        # 写入文件
        if self.enable_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(event.to_json() + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit log to file: {e}")
        
        # 输出到控制台
        if self.enable_console:
            log_level_map = {
                EventSeverity.DEBUG: logging.DEBUG,
                EventSeverity.INFO: logging.INFO,
                EventSeverity.NOTICE: logging.INFO,
                EventSeverity.WARNING: logging.WARNING,
                EventSeverity.ERROR: logging.ERROR,
                EventSeverity.CRITICAL: logging.CRITICAL,
                EventSeverity.ALERT: logging.CRITICAL,
            }
            level = log_level_map.get(event.severity, logging.INFO)
            logger.log(level, f"[{event.event_type.value}] {event.to_json()}")
    
    def _flush_to_file(self) -> None:
        """刷新队列到文件"""
        events_to_write = self._queue[:]
        self._queue.clear()
        self._last_flush = time.time()
        
        if events_to_write and self.enable_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    for event in events_to_write:
                        f.write(event.to_json() + "\n")
            except Exception as e:
                logger.error(f"Failed to flush audit logs: {e}")
    
    def _redact_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏详细信息中的敏感字段"""
        redacted = {}
        for key, value in details.items():
            key_lower = key.lower()
            if any(s in key_lower for s in self.SENSITIVE_FIELDS):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_details(value)
            elif isinstance(value, str) and len(value) > 10:
                # 长字符串可能是敏感信息，进行部分脱敏
                if any(s in key_lower for s in ['key', 'secret', 'token', 'password']):
                    redacted[key] = value[:3] + "*" * (len(value) - 6) + value[-3:] if len(value) > 6 else "*" * len(value)
                else:
                    redacted[key] = value
            else:
                redacted[key] = value
        return redacted
    
    def query_logs(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        severity: Optional[EventSeverity] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """查询审计日志
        
        Args:
            event_type: 事件类型前缀（如 "auth.login"）
            user_id: 用户 ID
            start_time: 开始时间（ISO 格式）
            end_time: 结束时间（ISO 格式）
            severity: 最低严重程度
            limit: 最大返回数量
            
        Returns:
            审计事件列表
        """
        results = []
        
        if not os.path.exists(self.log_file):
            return results
        
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        
                        # 过滤 - 在创建对象之前进行，避免类型转换问题
                        if event_type and not data.get("event_type", "").startswith(event_type):
                            continue
                        if user_id and data.get("user_id") != user_id:
                            continue
                        if start_time and data.get("timestamp", "") < start_time:
                            continue
                        if end_time and data.get("timestamp", "") > end_time:
                            continue
                        if severity and data.get("severity") != severity.value:
                            continue
                        
                        event = AuditEvent.from_dict(data)
                        results.append(event)
                        
                        if len(results) >= limit:
                            break
                            
                    except (json.JSONDecodeError, Exception) as e:
                        logger.debug(f"Failed to parse audit log line: {e}")
                        continue
        except Exception as e:
            logger.error(f"Failed to query audit logs: {e}")
        
        return results


# ==================== 全局实例 ====================

_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志器实例"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def log_event(event_type: SecurityEvent, **kwargs) -> AuditEvent:
    """便捷函数：记录事件"""
    return get_audit_logger().log_event(event_type, **kwargs)


def log_auth_event(event_type: SecurityEvent, user_id: str, ip_address: str, **kwargs) -> AuditEvent:
    """便捷函数：记录认证事件"""
    return get_audit_logger().log_auth_event(event_type, user_id, ip_address, **kwargs)


def log_security_event(event_type: SecurityEvent, ip_address: str, **kwargs) -> AuditEvent:
    """便捷函数：记录安全事件"""
    return get_audit_logger().log_security_event(event_type, ip_address, **kwargs)