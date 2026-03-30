"""输入验证服务 - 企业级注入攻击防护

本模块提供全面的输入验证功能，防御：
1. Prompt 注入攻击（LLM 指令劫持）
2. SQL/NoSQL 注入攻击
3. 路径遍历攻击
4. XSS 跨站脚本攻击
5. 命令注入攻击

使用示例:
    from src.security.input_validator import validate_input, InputValidator
    
    # 验证用户查询
    result = validate_input(user_query, field_name="query")
    if not result.is_valid:
        raise ValueError(result.error_message)
    
    # 使用验证器类
    validator = InputValidator()
    validator.validate_query(user_query)
    validator.validate_collection_name(collection)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


class AttackType(str, Enum):
    """攻击类型枚举"""
    PROMPT_INJECTION = "prompt_injection"
    SQL_INJECTION = "sql_injection"
    NOSQL_INJECTION = "nosql_injection"
    PATH_TRAVERSAL = "path_traversal"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    SSRF = "ssrf"
    NONE = "none"


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    value: str
    field_name: str
    error_message: Optional[str] = None
    detected_attacks: List[AttackType] = field(default_factory=list)
    sanitized_value: Optional[str] = None


class InputValidator:
    """企业级输入验证器
    
    防御策略：
    1. 白名单验证（优先）
    2. 黑名单过滤（补充）
    3. 模式匹配检测
    4. 长度限制
    5. 字符集限制
    """
    
    # ==================== 危险模式定义 ====================
    
    # Prompt 注入攻击模式（检测 LLM 指令劫持尝试）
    PROMPT_INJECTION_PATTERNS = [
        # 忽略指令类
        (r"ignore\s+(previous|all|above|below|prior)", "忽略之前的指令"),
        (r"forget\s+(all|everything|previous)", "忘记所有指令"),
        (r"disregard\s+(previous|all|above)", " disregarding 之前的指令"),
        (r"cancel\s+previous", "取消之前的指令"),
        
        # 系统提示词类
        (r"system\s*(prompt|instruction|message)", "系统提示词"),
        (r"you\s+are\s+now\s+(instructed|acting|as)", "角色劫持"),
        (r"from\s+now\s+on\s+,?\s*(you|act)", "指令覆盖"),
        (r"new\s+(instruction|rule|command)", "新指令覆盖"),
        
        # 越狱类
        (r"(jailbreak|break\s+free|escape)\s*(mode|rules)", "越狱模式"),
        (r"do\s+not\s+follow\s+(your|the)\s+(rules|guidelines)", "绕过规则"),
        (r"bypass\s+(safety|content|filter)", "绕过安全"),
        (r"override\s+(restrictions|limits)", "覆盖限制"),
        
        # 数据泄露类
        (r"(reveal|show|print|output)\s+(your|the)\s+(prompt|instruction|system)", "泄露提示词"),
        (r"what\s+(is|are)\s+(your|the)\s+(system\s+)?(prompt|instruction)", "探测提示词"),
        (r"repeat\s+(above|previous|first)", "重复上文"),
        
        # 编码绕过类
        (r"(base64|hex|url|unicode)\s*(decode|encode|convert)", "编码绕过"),
        (r"convert\s+to\s+(base64|hex|binary)", "编码转换"),
        
        # 多语言注入
        (r"忽略之前的指令", "中文指令覆盖"),
        (r"忘记所有规则", "中文规则覆盖"),
        (r"你现在必须", "强制指令"),
        (r"系统提示：", "伪造系统提示"),
    ]
    
    # SQL 注入模式
    SQL_INJECTION_PATTERNS = [
        # 经典 SQL 注入
        (r"'\s*(OR|AND)\s*'?'\s*=\s*'?", "OR 注入"),
        (r"'\s*(OR|AND)\s+\d+\s*=\s*\d+", "数字比较注入"),
        (r"--\s*$", "SQL 注释"),
        (r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)", "危险 SQL 语句"),
        (r"UNION\s+(ALL\s+)?SELECT", "UNION 注入"),
        
        # NoSQL 注入
        (r"\{\s*'\s*\$", "MongoDB 操作符"),
        (r"\[\s*'\s*\$", "MongoDB 数组操作符"),
        (r"\$\s*(where|expr|function)\s*:", "MongoDB 查询注入"),
    ]
    
    # 路径遍历模式
    PATH_TRAVERSAL_PATTERNS = [
        (r"\.\./", "目录穿越"),
        (r"\.\.\\", "Windows 目录穿越"),
        (r"%2e%2e%2f", "URL 编码穿越"),
        (r"%2e%2e/", "部分编码穿越"),
        (r"\.\.%2f", "部分编码穿越"),
        (r"%2e%2e\\", "Windows 编码穿越"),
        (r"/etc/passwd", "Linux 敏感文件"),
        (r"/etc/shadow", "Linux 密码文件"),
        (r"\\windows\\system32", "Windows 系统目录"),
        (r"C:\\", "Windows 根目录"),
        (r"file://", "文件协议"),
    ]
    
    # XSS 攻击模式
    XSS_PATTERNS = [
        (r"<script[^>]*>", "脚本标签"),
        (r"</script>", "脚本闭合"),
        (r"javascript:", "JavaScript 协议"),
        (r"on(load|error|click|mouse|focus|blur|change|submit)\s*=", "事件处理器"),
        (r"<iframe[^>]*>", "内嵌框架"),
        (r"<object[^>]*>", "对象标签"),
        (r"<embed[^>]*>", "嵌入标签"),
        (r"<svg[^>]*onload", "SVG 注入"),
        (r"expression\s*\(", "CSS 表达式"),
        (r"url\s*\(\s*['\"]?javascript:", "CSS JS 注入"),
    ]
    
    # 命令注入模式
    COMMAND_INJECTION_PATTERNS = [
        (r"[;&|]\s*(cat|ls|dir|whoami|id|uname|pwd)", "命令连接"),
        (r"`[^`]+`", "反引号命令"),
        (r"\$\([^)]+\)", "命令替换"),
        (r"\|\s*(bash|sh|cmd|powershell)", "管道注入"),
        (r">\s*/dev/", "重定向注入"),
        (r"&&\s*(rm|del|rmdir)", "危险命令"),
    ]
    
    # SSRF 模式
    SSRF_PATTERNS = [
        (r"http://(localhost|127\.0\.0\.1|0\.0\.0\.0)", "本地回环"),
        (r"http://169\.254\.", "云元数据"),
        (r"http://10\.\d+\.\d+\.\d+", "内网地址"),
        (r"http://172\.(1[6-9]|2[0-9]|3[01])\.", "内网地址"),
        (r"http://192\.168\.", "内网地址"),
        (r"file://", "文件协议"),
        (r"gopher://", "Gopher 协议"),
        (r"dict://", "Dict 协议"),
    ]
    
    # ==================== 白名单模式定义 ====================
    
    # 安全的集合名称模式
    SAFE_COLLECTION_PATTERN = r'^[a-zA-Z0-9_-]{1,64}$'
    
    # 安全的文件名模式
    SAFE_FILENAME_PATTERN = r'^[a-zA-Z0-9._-]{1,255}$'
    
    # 安全的查询长度限制
    MAX_QUERY_LENGTH = 2000
    
    # ==================== 配置 ====================
    
    def __init__(
        self,
        strict_mode: bool = True,
        log_violations: bool = True,
        sanitize_input: bool = True,
    ) -> None:
        """初始化验证器
        
        Args:
            strict_mode: 严格模式（发现任何可疑输入都拒绝）
            log_violations: 记录违规日志
            sanitize_input: 自动清理输入
        """
        self.strict_mode = strict_mode
        self.log_violations = log_violations
        self.sanitize_input = sanitize_input
        
        # 预编译正则表达式
        self._prompt_injection_regex: List[tuple] = [
            (re.compile(pattern, re.IGNORECASE), desc)
            for pattern, desc in self.PROMPT_INJECTION_PATTERNS
        ]
        self._sql_injection_regex: List[tuple] = [
            (re.compile(pattern, re.IGNORECASE), desc)
            for pattern, desc in self.SQL_INJECTION_PATTERNS
        ]
        self._path_traversal_regex: List[tuple] = [
            (re.compile(pattern, re.IGNORECASE), desc)
            for pattern, desc in self.PATH_TRAVERSAL_PATTERNS
        ]
        self._xss_regex: List[tuple] = [
            (re.compile(pattern, re.IGNORECASE), desc)
            for pattern, desc in self.XSS_PATTERNS
        ]
        self._command_injection_regex: List[tuple] = [
            (re.compile(pattern, re.IGNORECASE), desc)
            for pattern, desc in self.COMMAND_INJECTION_PATTERNS
        ]
        self._ssrf_regex: List[tuple] = [
            (re.compile(pattern, re.IGNORECASE), desc)
            for pattern, desc in self.SSRF_PATTERNS
        ]
        
        # 审计日志
        self._audit_log: List[Dict[str, Any]] = []
    
    # ==================== 主要验证方法 ====================
    
    def validate_query(
        self,
        query: str,
        field_name: str = "query",
        max_length: Optional[int] = None,
    ) -> ValidationResult:
        """验证查询输入
        
        Args:
            query: 用户查询
            field_name: 字段名称
            max_length: 最大长度
            
        Returns:
            验证结果
        """
        if not query:
            return ValidationResult(
                is_valid=False,
                value=query or "",
                field_name=field_name,
                error_message="查询不能为空",
            )
        
        # 长度检查
        length_limit = max_length or self.MAX_QUERY_LENGTH
        if len(query) > length_limit:
            return ValidationResult(
                is_valid=False,
                value=query,
                field_name=field_name,
                error_message=f"查询过长（最大{length_limit}字符）",
            )
        
        # 攻击检测
        detected_attacks = []
        
        # 检测 Prompt 注入
        for regex, desc in self._prompt_injection_regex:
            if regex.search(query):
                detected_attacks.append(AttackType.PROMPT_INJECTION)
                if self.strict_mode:
                    return self._log_and_return(
                        field_name, query, detected_attacks,
                        f"检测到 Prompt 注入攻击：{desc}"
                    )
        
        # 检测 SQL 注入
        for regex, desc in self._sql_injection_regex:
            if regex.search(query):
                detected_attacks.append(AttackType.SQL_INJECTION)
                if self.strict_mode:
                    return self._log_and_return(
                        field_name, query, detected_attacks,
                        f"检测到 SQL 注入攻击：{desc}"
                    )
        
        # 检测路径遍历
        for regex, desc in self._path_traversal_regex:
            if regex.search(query):
                detected_attacks.append(AttackType.PATH_TRAVERSAL)
                if self.strict_mode:
                    return self._log_and_return(
                        field_name, query, detected_attacks,
                        f"检测到路径遍历攻击：{desc}"
                    )
        
        # 检测 XSS
        for regex, desc in self._xss_regex:
            if regex.search(query):
                detected_attacks.append(AttackType.XSS)
                if self.strict_mode:
                    return self._log_and_return(
                        field_name, query, detected_attacks,
                        f"检测到 XSS 攻击：{desc}"
                    )
        
        # 检测命令注入
        for regex, desc in self._command_injection_regex:
            if regex.search(query):
                detected_attacks.append(AttackType.COMMAND_INJECTION)
                if self.strict_mode:
                    return self._log_and_return(
                        field_name, query, detected_attacks,
                        f"检测到命令注入攻击：{desc}"
                    )
        
        # 检测 SSRF
        for regex, desc in self._ssrf_regex:
            if regex.search(query):
                detected_attacks.append(AttackType.SSRF)
                if self.strict_mode:
                    return self._log_and_return(
                        field_name, query, detected_attacks,
                        f"检测到 SSRF 攻击：{desc}"
                    )
        
        # 通过验证
        sanitized = self._sanitize(query) if self.sanitize_input else query
        
        return ValidationResult(
            is_valid=True,
            value=query,
            field_name=field_name,
            sanitized_value=sanitized,
            detected_attacks=detected_attacks if not self.strict_mode else [],
        )
    
    def validate_collection_name(
        self,
        collection: str,
        field_name: str = "collection",
    ) -> ValidationResult:
        """验证集合名称
        
        Args:
            collection: 集合名称
            field_name: 字段名称
            
        Returns:
            验证结果
        """
        if not collection:
            return ValidationResult(
                is_valid=False,
                value=collection or "",
                field_name=field_name,
                error_message="集合名称不能为空",
            )
        
        # 白名单验证
        if not re.match(self.SAFE_COLLECTION_PATTERN, collection):
            return ValidationResult(
                is_valid=False,
                value=collection,
                field_name=field_name,
                error_message="集合名称只能包含字母、数字、下划线和连字符",
            )
        
        # 额外检查路径遍历
        if ".." in collection or collection.startswith("/"):
            return ValidationResult(
                is_valid=False,
                value=collection,
                field_name=field_name,
                error_message="检测到路径遍历攻击",
                detected_attacks=[AttackType.PATH_TRAVERSAL],
            )
        
        return ValidationResult(
            is_valid=True,
            value=collection,
            field_name=field_name,
            sanitized_value=collection,
        )
    
    def validate_file_path(
        self,
        file_path: str,
        field_name: str = "file_path",
        allowed_base_dirs: Optional[List[str]] = None,
    ) -> ValidationResult:
        """验证文件路径
        
        Args:
            file_path: 文件路径
            field_name: 字段名称
            allowed_base_dirs: 允许的基目录列表
            
        Returns:
            验证结果
        """
        if not file_path:
            return ValidationResult(
                is_valid=False,
                value=file_path or "",
                field_name=field_name,
                error_message="文件路径不能为空",
            )
        
        # 检测路径遍历
        for regex, desc in self._path_traversal_regex:
            if regex.search(file_path):
                return ValidationResult(
                    is_valid=False,
                    value=file_path,
                    field_name=field_name,
                    error_message=f"检测到路径遍历攻击：{desc}",
                    detected_attacks=[AttackType.PATH_TRAVERSAL],
                )
        
        # 如果指定了允许的基目录，检查路径是否在其中
        if allowed_base_dirs:
            import os
            abs_path = os.path.abspath(file_path)
            allowed = False
            for base_dir in allowed_base_dirs:
                abs_base = os.path.abspath(base_dir)
                if abs_path.startswith(abs_base):
                    allowed = True
                    break
            if not allowed:
                return ValidationResult(
                    is_valid=False,
                    value=file_path,
                    field_name=field_name,
                    error_message="文件路径不在允许的目录中",
                )
        
        return ValidationResult(
            is_valid=True,
            value=file_path,
            field_name=field_name,
            sanitized_value=file_path,
        )
    
    def validate_url(
        self,
        url: str,
        field_name: str = "url",
        allowed_schemes: Optional[List[str]] = None,
        allowed_hosts: Optional[List[str]] = None,
    ) -> ValidationResult:
        """验证 URL
        
        Args:
            url: URL 地址
            field_name: 字段名称
            allowed_schemes: 允许的协议列表
            allowed_hosts: 允许的主机列表
            
        Returns:
            验证结果
        """
        if not url:
            return ValidationResult(
                is_valid=False,
                value=url or "",
                field_name=field_name,
                error_message="URL 不能为空",
            )
        
        # 检测 SSRF
        for regex, desc in self._ssrf_regex:
            if regex.search(url, re.IGNORECASE):
                return ValidationResult(
                    is_valid=False,
                    value=url,
                    field_name=field_name,
                    error_message=f"检测到 SSRF 攻击：{desc}",
                    detected_attacks=[AttackType.SSRF],
                )
        
        # 解析 URL 进行更详细的验证
        try:
            from urllib.parse import urlparse
            
            parsed = urlparse(url)
            
            # 检查协议
            if allowed_schemes and parsed.scheme not in allowed_schemes:
                return ValidationResult(
                    is_valid=False,
                    value=url,
                    field_name=field_name,
                    error_message=f"不允许的协议：{parsed.scheme}",
                )
            
            # 检查主机
            if allowed_hosts and parsed.hostname not in allowed_hosts:
                return ValidationResult(
                    is_valid=False,
                    value=url,
                    field_name=field_name,
                    error_message=f"不允许的主机：{parsed.hostname}",
                )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                value=url,
                field_name=field_name,
                error_message=f"URL 解析失败：{e}",
            )
        
        return ValidationResult(
            is_valid=True,
            value=url,
            field_name=field_name,
            sanitized_value=url,
        )
    
    def validate_json_input(
        self,
        json_str: str,
        field_name: str = "json_input",
        max_depth: int = 10,
        max_size: int = 1024 * 1024,  # 1MB
    ) -> ValidationResult:
        """验证 JSON 输入
        
        Args:
            json_str: JSON 字符串
            field_name: 字段名称
            max_depth: 最大嵌套深度
            max_size: 最大字节数
            
        Returns:
            验证结果
        """
        import json
        
        if not json_str:
            return ValidationResult(
                is_valid=False,
                value=json_str or "",
                field_name=field_name,
                error_message="JSON 不能为空",
            )
        
        # 大小检查
        if len(json_str.encode('utf-8')) > max_size:
            return ValidationResult(
                is_valid=False,
                value=json_str,
                field_name=field_name,
                error_message=f"JSON 过大（最大{max_size}字节）",
            )
        
        # 尝试解析
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                value=json_str,
                field_name=field_name,
                error_message=f"JSON 解析失败：{e}",
            )
        
        # 深度检查
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                raise ValueError(f"嵌套过深（最大{max_depth}层）")
            if isinstance(obj, dict):
                for value in obj.values():
                    check_depth(value, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)
        
        try:
            check_depth(data)
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                value=json_str,
                field_name=field_name,
                error_message=str(e),
            )
        
        return ValidationResult(
            is_valid=True,
            value=json_str,
            field_name=field_name,
            sanitized_value=json_str,
        )
    
    # ==================== 内部方法 ====================
    
    def _sanitize(self, value: str) -> str:
        """清理输入
        
        Args:
            value: 原始输入
            
        Returns:
            清理后的输入
        """
        if not value:
            return value
        
        # 去除首尾空白
        sanitized = value.strip()
        
        # 移除控制字符（保留换行和制表符）
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)
        
        # 标准化空白字符
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        return sanitized
    
    def _log_and_return(
        self,
        field_name: str,
        value: str,
        detected_attacks: List[AttackType],
        error_message: str,
    ) -> ValidationResult:
        """记录日志并返回验证失败结果"""
        import time
        from datetime import datetime
        
        # 记录审计日志
        if self.log_violations:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "timestamp_unix": time.time(),
                "field_name": field_name,
                "value_preview": value[:100] if len(value) > 100 else value,
                "detected_attacks": [a.value for a in detected_attacks],
                "error_message": error_message,
            }
            self._audit_log.append(log_entry)
            
            # 保持日志大小合理
            if len(self._audit_log) > 10000:
                self._audit_log = self._audit_log[-1000:]
            
            # 记录到日志
            logger.warning(
                f"Input validation failed: {field_name} - {error_message} "
                f"(attacks: {[a.value for a in detected_attacks]})"
            )
        
        return ValidationResult(
            is_valid=False,
            value=value,
            field_name=field_name,
            error_message=error_message,
            detected_attacks=detected_attacks,
        )
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取审计日志"""
        return self._audit_log[-limit:]


# ==================== 便捷函数 ====================

# 全局验证器实例
_default_validator: Optional[InputValidator] = None


def get_validator() -> InputValidator:
    """获取默认验证器实例"""
    global _default_validator
    if _default_validator is None:
        _default_validator = InputValidator()
    return _default_validator


def validate_input(
    value: str,
    field_name: str = "input",
    value_type: str = "query",
    **kwargs,
) -> ValidationResult:
    """验证输入（便捷函数）
    
    Args:
        value: 输入值
        field_name: 字段名称
        value_type: 值类型（query/collection/file_path/url/json）
        **kwargs: 传递给具体验证方法的参数
        
    Returns:
        验证结果
    """
    validator = get_validator()
    
    if value_type == "query":
        return validator.validate_query(value, field_name, **kwargs)
    elif value_type == "collection":
        return validator.validate_collection_name(value, field_name)
    elif value_type == "file_path":
        return validator.validate_file_path(value, field_name, **kwargs)
    elif value_type == "url":
        return validator.validate_url(value, field_name, **kwargs)
    elif value_type == "json":
        return validator.validate_json_input(value, field_name, **kwargs)
    else:
        # 默认使用查询验证
        return validator.validate_query(value, field_name, **kwargs)


def validate_query(query: str, **kwargs) -> ValidationResult:
    """验证查询（便捷函数）"""
    return get_validator().validate_query(query, **kwargs)


def validate_collection_name(collection: str, **kwargs) -> ValidationResult:
    """验证集合名称（便捷函数）"""
    return get_validator().validate_collection_name(collection, **kwargs)


def detect_prompt_injection(text: str) -> List[tuple]:
    """检测 Prompt 注入攻击
    
    Args:
        text: 待检测文本
        
    Returns:
        检测到的攻击列表（描述元组）
    """
    validator = get_validator()
    detected = []
    
    for regex, desc in validator._prompt_injection_regex:
        if regex.search(text):
            detected.append((desc, regex.pattern))
    
    return detected