"""输出过滤服务 - 企业级敏感信息脱敏

本模块提供全面的输出过滤功能，用于：
1. 敏感信息脱敏（PII 保护）
2. 密钥信息过滤
3. 内部信息隐藏
4. 数据分级控制

使用示例:
    from src.security.output_filter import OutputFilter, DataClassification
    
    # 过滤敏感信息
    filtered_text = OutputFilter.filter_sensitive(original_text)
    
    # 过滤检索结果
    filtered_results = OutputFilter.filter_results(search_results)
    
    # 根据数据分级过滤
    filter = OutputFilter(min_classification=DataClassification.INTERNAL)
    filtered = filter.apply_classification_filter(document)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class DataClassification(str, Enum):
    """数据分级枚举"""
    PUBLIC = "public"           # 公开数据 - 可对外发布
    INTERNAL = "internal"       # 内部数据 - 仅限内部员工
    CONFIDENTIAL = "confidential"  # 机密数据 - 需特殊权限
    RESTRICTED = "restricted"   # 受限数据 - 最高保密级别


class PIICategory(str, Enum):
    """个人敏感信息类别"""
    PHONE = "phone"             # 手机号
    EMAIL = "email"             # 邮箱地址
    ID_CARD = "id_card"         # 身份证号
    BANK_CARD = "bank_card"     # 银行卡号
    ADDRESS = "address"         # 地址
    NAME = "name"               # 姓名
    IP_ADDRESS = "ip_address"   # IP 地址
    URL = "url"                 # URL
    API_KEY = "api_key"         # API 密钥
    PASSWORD = "password"       # 密码
    CREDIT_CARD = "credit_card" # 信用卡号
    SOCIAL_SECURITY = "social_security"  # 社保卡号
    PASSPORT = "passport"       # 护照号
    LICENSE_PLATE = "license_plate"  # 车牌号
    CUSTOM = "custom"           # 自定义模式


@dataclass
class PIIPattern:
    """PII 匹配模式"""
    category: PIICategory
    pattern: re.Pattern
    replacement: str
    description: str


@dataclass
class FilterResult:
    """过滤结果"""
    original: str
    filtered: str
    redacted_count: int
    redacted_categories: Set[PIICategory]
    is_safe: bool
    warnings: List[str] = field(default_factory=list)


class OutputFilter:
    """企业级输出过滤器
    
    功能：
    1. 正则匹配脱敏
    2. 关键词过滤
    3. 数据分级控制
    4. 自定义规则扩展
    """
    
    # ==================== 默认 PII 模式定义 ====================
    
    DEFAULT_PII_PATTERNS = [
        # 手机号（中国）
        PIIPattern(
            category=PIICategory.PHONE,
            pattern=re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)'),
            replacement='[手机号已隐藏]',
            description="中国手机号",
        ),
        
        # 邮箱地址
        PIIPattern(
            category=PIICategory.EMAIL,
            pattern=re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}'),
            replacement='[邮箱已隐藏]',
            description="邮箱地址",
        ),
        
        # 身份证号（中国）
        PIIPattern(
            category=PIICategory.ID_CARD,
            pattern=re.compile(r'(?<!\d)\d{17}[\dXx](?!\d)'),
            replacement='[身份证号已隐藏]',
            description="中国身份证号",
        ),
        
        # 银行卡号（16-19 位）
        PIIPattern(
            category=PIICategory.BANK_CARD,
            pattern=re.compile(r'(?<!\d)\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4,7}(?!\d)'),
            replacement='[银行卡号已隐藏]',
            description="银行卡号",
        ),
        
        # IP 地址
        PIIPattern(
            category=PIICategory.IP_ADDRESS,
            pattern=re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
            replacement='[IP 地址已隐藏]',
            description="IP 地址",
        ),
        
        # API 密钥（常见格式）
        PIIPattern(
            category=PIICategory.API_KEY,
            pattern=re.compile(r'\b(sk-[a-zA-Z0-9]{20,})\b'),
            replacement='[API 密钥已隐藏]',
            description="OpenAI 格式 API 密钥",
        ),
        PIIPattern(
            category=PIICategory.API_KEY,
            pattern=re.compile(r'\b(AKIA[0-9A-Z]{16})\b'),
            replacement='[AWS 密钥已隐藏]',
            description="AWS Access Key",
        ),
        
        # URL（带协议的完整 URL）
        PIIPattern(
            category=PIICategory.URL,
            pattern=re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+'),
            replacement='[URL 已隐藏]',
            description="HTTP/HTTPS URL",
        ),
        
        # 信用卡号（带空格的 16 位）
        PIIPattern(
            category=PIICategory.CREDIT_CARD,
            pattern=re.compile(r'(?<!\d)\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}(?!\d)'),
            replacement='[信用卡号已隐藏]',
            description="信用卡号",
        ),
        
        # 护照号（国际格式，简化版）
        PIIPattern(
            category=PIICategory.PASSPORT,
            pattern=re.compile(r'(?<!\d)[A-Z]{1,2}\d{6,9}(?!\d)'),
            replacement='[护照号已隐藏]',
            description="护照号",
        ),
        
        # 车牌号（中国，简化版）
        PIIPattern(
            category=PIICategory.LICENSE_PLATE,
            pattern=re.compile(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5,6}'),
            replacement='[车牌号已隐藏]',
            description="中国车牌号",
        ),
    ]
    
    # ==================== 关键词过滤列表 ====================
    
    SENSITIVE_KEYWORDS = [
        # 认证相关
        "password", "passwd", "pwd", "secret", "token", "credential",
        "密码", "口令", "凭证",
        
        # 密钥相关
        "api_key", "apikey", "api-key", "private_key", "privatekey",
        "access_key", "accesskey", "secret_key", "secretkey",
        "密钥", "私钥", "访问密钥",
        
        # 数据库相关
        "connection_string", "connectionstring", "db_password", "db_passwd",
        "数据库密码", "连接字符串",
        
        # 内部系统
        "internal", "internal_only", "staff_only", "employee_only",
        "内部", "仅限员工", "机密",
    ]
    
    # ==================== 配置 ====================
    
    def __init__(
        self,
        custom_patterns: Optional[List[PIIPattern]] = None,
        disabled_categories: Optional[Set[PIICategory]] = None,
        min_classification: DataClassification = DataClassification.PUBLIC,
        log_redactions: bool = True,
        max_content_length: int = 100000,
    ) -> None:
        """初始化过滤器
        
        Args:
            custom_patterns: 自定义 PII 模式
            disabled_categories: 禁用的类别（不过滤）
            min_classification: 最小数据分级
            log_redactions: 记录脱敏日志
            max_content_length: 最大处理长度
        """
        self.custom_patterns = custom_patterns or []
        self.disabled_categories = disabled_categories or set()
        self.min_classification = min_classification
        self.log_redactions = log_redactions
        self.max_content_length = max_content_length
        
        # 合并默认和自定义模式
        self._patterns: List[PIIPattern] = []
        for pattern in self.DEFAULT_PII_PATTERNS:
            if pattern.category not in self.disabled_categories:
                self._patterns.append(pattern)
        self._patterns.extend(self.custom_patterns)
        
        # 审计日志
        self._audit_log: List[Dict[str, Any]] = []
        
        # 统计信息
        self._stats = {
            "total_filtered": 0,
            "total_redactions": 0,
            "redactions_by_category": {},
        }
    
    # ==================== 主要过滤方法 ====================
    
    def filter_sensitive(
        self,
        text: str,
        preserve_urls: bool = False,
        preserve_emails: bool = False,
    ) -> str:
        """过滤敏感信息
        
        Args:
            text: 原始文本
            preserve_urls: 是否保留 URL
            preserve_emails: 是否保留邮箱
            
        Returns:
            过滤后的文本
        """
        if not text:
            return text
        
        # 长度检查
        if len(text) > self.max_content_length:
            logger.warning(f"Text too long ({len(text)} chars), truncating")
            text = text[:self.max_content_length]
        
        result = text
        redacted_categories: Set[PIICategory] = set()
        redaction_count = 0
        
        for pattern in self._patterns:
            # 跳过被禁用的类别
            if pattern.category in self.disabled_categories:
                continue
            
            # 特殊处理：保留 URL 或邮箱
            if preserve_urls and pattern.category == PIICategory.URL:
                continue
            if preserve_emails and pattern.category == PIICategory.EMAIL:
                continue
            
            # 执行替换
            matches = pattern.pattern.findall(result)
            if matches:
                result = pattern.pattern.sub(pattern.replacement, result)
                redacted_categories.add(pattern.category)
                redaction_count += len(matches)
        
        # 记录统计
        if redaction_count > 0:
            self._stats["total_filtered"] += 1
            self._stats["total_redactions"] += redaction_count
            for cat in redacted_categories:
                self._stats["redactions_by_category"][cat.value] = \
                    self._stats["redactions_by_category"].get(cat.value, 0) + redaction_count
            
            # 记录审计日志
            if self.log_redactions:
                self._log_redaction(redaction_count, redacted_categories)
        
        return result
    
    def filter_results(
        self,
        results: List[Dict[str, Any]],
        filter_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """过滤检索结果中的敏感信息
        
        Args:
            results: 检索结果列表
            filter_metadata: 是否过滤元数据
            
        Returns:
            过滤后的结果
        """
        if not results:
            return results
        
        filtered_results = []
        
        for result in results:
            filtered = dict(result)  # 浅拷贝
            
            # 过滤文本内容
            if 'text' in filtered and isinstance(filtered['text'], str):
                filtered['text'] = self.filter_sensitive(filtered['text'])
            
            if 'content' in filtered and isinstance(filtered['content'], str):
                filtered['content'] = self.filter_sensitive(filtered['content'])
            
            # 过滤元数据
            if filter_metadata and 'metadata' in filtered:
                filtered['metadata'] = self._filter_metadata(filtered['metadata'])
            
            filtered_results.append(filtered)
        
        return filtered_results
    
    def filter_document(
        self,
        content: str,
        metadata: Dict[str, Any],
        classification: Optional[DataClassification] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """过滤文档内容和元数据
        
        Args:
            content: 文档内容
            metadata: 元数据
            classification: 数据分级
            
        Returns:
            (过滤后的内容，过滤后的元数据)
        """
        # 检查数据分级
        if classification and not self._check_classification(classification):
            logger.warning(f"Document classification {classification} below minimum {self.min_classification}")
            return "[内容因数据分级限制无法显示]", {}
        
        # 过滤内容
        filtered_content = self.filter_sensitive(content)
        
        # 过滤元数据
        filtered_metadata = self._filter_metadata(metadata)
        
        return filtered_content, filtered_metadata
    
    def filter_dict(
        self,
        data: Dict[str, Any],
        sensitive_keys: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """过滤字典中的敏感键值
        
        Args:
            data: 原始字典
            sensitive_keys: 敏感键名集合
            
        Returns:
            过滤后的字典
        """
        if not data:
            return data
        
        sensitive = sensitive_keys or self._get_sensitive_keys()
        filtered = {}
        
        for key, value in data.items():
            if key.lower() in sensitive:
                # 敏感键，进行脱敏
                if isinstance(value, str):
                    filtered[key] = self.filter_sensitive(value)
                elif isinstance(value, dict):
                    filtered[key] = self.filter_dict(value, sensitive_keys)
                elif isinstance(value, list):
                    filtered[key] = self._filter_list(value, sensitive_keys)
                else:
                    filtered[key] = f"[{key} 已隐藏]"
            else:
                # 非敏感键，递归处理
                if isinstance(value, str):
                    filtered[key] = self.filter_sensitive(value)
                elif isinstance(value, dict):
                    filtered[key] = self.filter_dict(value, sensitive_keys)
                elif isinstance(value, list):
                    filtered[key] = self._filter_list(value, sensitive_keys)
                else:
                    filtered[key] = value
        
        return filtered
    
    def redact_text(
        self,
        text: str,
        start: int,
        end: int,
        show_chars: int = 2,
    ) -> str:
        """脱敏指定范围的文本
        
        Args:
            text: 原始文本
            start: 起始位置
            end: 结束位置
            show_chars: 首尾显示的字符数
            
        Returns:
            脱敏后的文本
        """
        if not text or start >= end:
            return text
        
        before = text[:start]
        target = text[start:end]
        after = text[end:]
        
        # 部分显示
        if len(target) > show_chars * 2:
            redacted = target[:show_chars] + "*" * (len(target) - show_chars * 2) + target[-show_chars:]
        else:
            redacted = "*" * len(target)
        
        return before + redacted + after
    
    def contains_sensitive(self, text: str) -> bool:
        """检查文本是否包含敏感信息
        
        Args:
            text: 待检查文本
            
        Returns:
            是否包含敏感信息
        """
        if not text:
            return False
        
        for pattern in self._patterns:
            if pattern.category in self.disabled_categories:
                continue
            if pattern.pattern.search(text):
                return True
        
        # 检查关键词
        text_lower = text.lower()
        for keyword in self.SENSITIVE_KEYWORDS:
            if keyword.lower() in text_lower:
                return True
        
        return False
    
    def get_sensitive_categories(self, text: str) -> Set[PIICategory]:
        """获取文本中包含的敏感信息类别
        
        Args:
            text: 待检查文本
            
        Returns:
            敏感信息类别集合
        """
        categories: Set[PIICategory] = set()
        
        if not text:
            return categories
        
        for pattern in self._patterns:
            if pattern.category in self.disabled_categories:
                continue
            if pattern.pattern.search(text):
                categories.add(pattern.category)
        
        return categories
    
    # ==================== 数据分级控制 ====================
    
    def _check_classification(
        self,
        classification: DataClassification,
    ) -> bool:
        """检查数据分级是否满足要求"""
        hierarchy = {
            DataClassification.PUBLIC: 0,
            DataClassification.INTERNAL: 1,
            DataClassification.CONFIDENTIAL: 2,
            DataClassification.RESTRICTED: 3,
        }
        
        min_level = hierarchy.get(self.min_classification, 0)
        doc_level = hierarchy.get(classification, 0)
        
        return doc_level >= min_level
    
    def set_min_classification(self, classification: DataClassification) -> None:
        """设置最小数据分级"""
        self.min_classification = classification
    
    # ==================== 内部方法 ====================
    
    def _filter_metadata(
        self,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """过滤元数据"""
        if not metadata:
            return metadata
        
        filtered = {}
        sensitive_keys = self._get_sensitive_keys()
        
        for key, value in metadata.items():
            # 检查键名是否敏感
            if key.lower() in sensitive_keys:
                if isinstance(value, str):
                    filtered[key] = "[已隐藏]"
                else:
                    filtered[key] = f"[{key} 已隐藏]"
            elif isinstance(value, str):
                # 过滤字符串值中的敏感信息
                filtered[key] = self.filter_sensitive(value)
            elif isinstance(value, dict):
                filtered[key] = self._filter_metadata(value)
            elif isinstance(value, list):
                filtered[key] = self._filter_list(value)
            else:
                filtered[key] = value
        
        return filtered
    
    def _filter_list(
        self,
        items: List[Any],
        sensitive_keys: Optional[Set[str]] = None,
    ) -> List[Any]:
        """过滤列表"""
        if not items:
            return items
        
        filtered = []
        sensitive = sensitive_keys or self._get_sensitive_keys()
        
        for item in items:
            if isinstance(item, str):
                filtered.append(self.filter_sensitive(item))
            elif isinstance(item, dict):
                filtered.append(self.filter_dict(item, sensitive))
            elif isinstance(item, list):
                filtered.append(self._filter_list(item, sensitive))
            else:
                filtered.append(item)
        
        return filtered
    
    def _get_sensitive_keys(self) -> Set[str]:
        """获取敏感键名集合"""
        return {
            # 认证相关
            "password", "passwd", "pwd", "secret", "token", "credential", "auth",
            # 密钥相关
            "api_key", "apikey", "api-key", "private_key", "privatekey",
            "access_key", "accesskey", "secret_key", "secretkey",
            # 数据库相关
            "connection_string", "db_password", "db_passwd", "database_password",
            # 个人信息
            "ssn", "social_security", "id_card", "passport", "license_plate",
            # 其他
            "internal", "confidential", "restricted",
        }
    
    def _log_redaction(
        self,
        count: int,
        categories: Set[PIICategory],
    ) -> None:
        """记录脱敏日志"""
        import time
        from datetime import datetime
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "timestamp_unix": time.time(),
            "redaction_count": count,
            "categories": [c.value for c in categories],
        }
        
        self._audit_log.append(log_entry)
        
        # 保持日志大小合理
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-1000:]
        
        logger.debug(f"Redacted {count} sensitive items: {[c.value for c in categories]}")
    
    # ==================== 统计与审计 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return dict(self._stats)
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取审计日志"""
        return self._audit_log[-limit:]
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self._stats = {
            "total_filtered": 0,
            "total_redactions": 0,
            "redactions_by_category": {},
        }
    
    # ==================== 类方法（便捷使用） ====================
    
    @classmethod
    def _filter_sensitive_text(cls, text: str, **kwargs) -> str:
        """类方法：快速过滤敏感信息（内部使用）
        
        Args:
            text: 原始文本
            **kwargs: 传递给 OutputFilter 构造函数的参数
            
        Returns:
            过滤后的文本
        """
        filter_instance = cls(**kwargs)
        return filter_instance.filter_sensitive(text)
    
    @classmethod
    def _filter_results_list(cls, results: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """类方法：快速过滤检索结果（内部使用）
        
        Args:
            results: 检索结果列表
            **kwargs: 传递给 OutputFilter 构造函数的参数
            
        Returns:
            过滤后的结果
        """
        filter_instance = cls(**kwargs)
        return filter_instance.filter_results(results)
    
    @classmethod
    def _check_contains_sensitive(cls, text: str) -> bool:
        """类方法：快速检查是否包含敏感信息（内部使用）
        
        Args:
            text: 待检查文本
            
        Returns:
            是否包含敏感信息
        """
        filter_instance = cls()
        return filter_instance.contains_sensitive(text)


# ==================== 便捷函数 ====================

# 全局过滤器实例
_default_filter: Optional[OutputFilter] = None


def get_filter() -> OutputFilter:
    """获取默认过滤器实例"""
    global _default_filter
    if _default_filter is None:
        _default_filter = OutputFilter()
    return _default_filter


def filter_sensitive(text: str, **kwargs) -> str:
    """便捷函数：过滤敏感信息"""
    filter_instance = OutputFilter(**kwargs)
    return filter_instance.filter_sensitive(text)


def filter_results(results: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
    """便捷函数：过滤检索结果"""
    filter_instance = OutputFilter(**kwargs)
    return filter_instance.filter_results(results)


def contains_sensitive(text: str) -> bool:
    """便捷函数：检查是否包含敏感信息"""
    filter_instance = OutputFilter()
    return filter_instance.contains_sensitive(text)


def redact_range(text: str, start: int, end: int, show_chars: int = 2) -> str:
    """便捷函数：脱敏指定范围"""
    return get_filter().redact_text(text, start, end, show_chars)
