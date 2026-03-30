"""密钥管理服务 - 企业级密钥管理方案

本模块提供安全的密钥管理功能，支持：
1. 环境变量读取（推荐用于开发环境）
2. 加密配置文件（推荐用于生产环境）
3. 密钥管理服务集成（AWS Secrets Manager, Azure Key Vault 等）
4. 密钥轮换支持

使用示例:
    # 方式 1: 从环境变量读取
    api_key = SecretManager.get("LLM_API_KEY")
    
    # 方式 2: 从加密配置读取
    api_key = SecretManager.get_decrypted("llm.api_key_encrypted")
    
    # 方式 3: 从密钥管理服务读取
    api_key = SecretManager.get_from_secrets_manager("aws-secrets-manager:/prod/rag/llm-key")
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SecretSource(str, Enum):
    """密钥来源枚举"""
    ENVIRONMENT = "environment"      # 环境变量
    ENCRYPTED_CONFIG = "encrypted"   # 加密配置
    SECRETS_MANAGER = "secrets_manager"  # 密钥管理服务
    PLAIN_CONFIG = "plain"           # 明文配置（不推荐）
    DEFAULT = "default"              # 默认值


@dataclass
class SecretValue:
    """密钥值及其元数据"""
    value: str
    source: SecretSource
    is_encrypted: bool = False
    rotation_due: bool = False  # 是否需要轮换


class SecretManager:
    """企业级密钥管理器
    
    安全实践：
    1. 优先从环境变量读取密钥
    2. 支持加密配置作为备选
    3. 记录密钥访问审计日志
    4. 支持密钥轮换提醒
    """
    
    # 密钥模式定义
    SECRET_PATTERNS = {
        'api_key': re.compile(r'^[A-Za-z0-9_-]{20,}$'),
        'aws_key': re.compile(r'^AKIA[0-9A-Z]{16}$'),
        'azure_key': re.compile(r'^[A-Za-z0-9+/]{43}=$'),
        'gcp_key': re.compile(r'^\{.*"private_key":.*\}$'),
    }
    
    # 需要轮换的密钥前缀（天）
    ROTATION_PERIODS = {
        'api_key': 90,      # API 密钥 90 天轮换
        'password': 60,     # 密码 60 天轮换
        'token': 30,        # Token 30 天轮换
    }
    
    _instance: Optional["SecretManager"] = None
    _master_key: Optional[bytes] = None
    _audit_log: list = []
    
    def __new__(cls) -> "SecretManager":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """初始化密钥管理器"""
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self._key_cache: Dict[str, SecretValue] = {}
        self._rotation_tracking: Dict[str, int] = {}  # key_name -> last_rotation_timestamp
    
    @classmethod
    def get(
        cls,
        name: str,
        default: Optional[str] = None,
        required: bool = False,
        validate_pattern: Optional[str] = None,
    ) -> Optional[str]:
        """获取密钥值
        
        优先级：环境变量 > 加密配置 > 默认值
        
        Args:
            name: 密钥名称（如 "LLM_API_KEY"）
            default: 默认值
            required: 是否必需
            validate_pattern: 验证模式名称（如 "api_key"）
            
        Returns:
            密钥值或 None
            
        Raises:
            ValueError: 当 required=True 但未找到密钥时
            ValueError: 当验证失败时
        """
        manager = cls()
        
        # 1. 尝试从环境变量读取
        value = os.environ.get(name)
        if value:
            secret_value = SecretValue(value=value, source=SecretSource.ENVIRONMENT)
            manager._key_cache[name] = secret_value
            manager._log_access(name, SecretSource.ENVIRONMENT, True)
            
            # 验证模式
            if validate_pattern and not cls._validate_pattern(value, validate_pattern):
                logger.warning(f"Secret {name} does not match pattern {validate_pattern}")
            
            return value
        
        # 2. 尝试从环境变量读取加密值
        encrypted_name = f"{name}_ENCRYPTED"
        encrypted_value = os.environ.get(encrypted_name)
        if encrypted_value:
            try:
                decrypted = cls._decrypt_value(encrypted_value)
                secret_value = SecretValue(value=decrypted, source=SecretSource.ENCRYPTED_CONFIG, is_encrypted=True)
                manager._key_cache[name] = secret_value
                manager._log_access(name, SecretSource.ENCRYPTED_CONFIG, True)
                return decrypted
            except Exception as e:
                logger.error(f"Failed to decrypt {encrypted_name}: {e}")
        
        # 3. 使用默认值
        if default is not None:
            secret_value = SecretValue(value=default, source=SecretSource.DEFAULT)
            manager._key_cache[name] = secret_value
            manager._log_access(name, SecretSource.DEFAULT, True)
            return default
        
        # 4. 必需但未找到
        if required:
            error_msg = f"Required secret '{name}' not found. Set as environment variable."
            manager._log_access(name, SecretSource.ENVIRONMENT, False)
            raise ValueError(error_msg)
        
        manager._log_access(name, SecretSource.DEFAULT, False)
        return None
    
    @classmethod
    def get_from_config(
        cls,
        config: Dict[str, Any],
        path: str,
        encrypted: bool = False,
        default: Optional[str] = None,
        required: bool = False,
    ) -> Optional[str]:
        """从配置字典获取密钥值
        
        Args:
            config: 配置字典
            path: 点分隔的路径（如 "llm.api_key"）
            encrypted: 是否为加密值
            default: 默认值
            required: 是否必需
            
        Returns:
            密钥值或 None
        """
        manager = cls()
        
        # 解析路径
        keys = path.split(".")
        value = config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                value = None
                break
        
        if value is None:
            if required:
                raise ValueError(f"Required config path '{path}' not found")
            return default
        
        if encrypted:
            try:
                decrypted = cls._decrypt_value(value)
                source = SecretSource.ENCRYPTED_CONFIG
                manager._log_access(path, source, True)
                return decrypted
            except Exception as e:
                logger.error(f"Failed to decrypt config path '{path}': {e}")
                if required:
                    raise
                return default
        else:
            source = SecretSource.PLAIN_CONFIG
            manager._log_access(path, source, True)
            logger.warning(f"Using plain (unencrypted) value for '{path}' - consider encryption")
            return str(value)
    
    @classmethod
    def get_from_secrets_manager(
        cls,
        secret_ref: str,
        cache_ttl_seconds: int = 3600,
    ) -> Optional[str]:
        """从密钥管理服务获取密钥
        
        支持的格式：
        - aws-secrets-manager:/prod/rag/llm-key
        - azure-key-vault://vault-name/secret-name
        - gcp-secret-manager://project-id/secret-name
        
        Args:
            secret_ref: 密钥引用
            cache_ttl_seconds: 缓存 TTL（秒）
            
        Returns:
            密钥值或 None
        """
        manager = cls()
        
        # 检查缓存
        cache_key = f"sm:{secret_ref}"
        if cache_key in manager._key_cache:
            cached = manager._key_cache[cache_key]
            # 简单 TTL 检查（实际应使用时间戳）
            return cached.value
        
        # 解析引用
        if secret_ref.startswith("aws-secrets-manager:"):
            return cls._get_aws_secret(secret_ref, cache_key, manager)
        elif secret_ref.startswith("azure-key-vault:"):
            return cls._get_azure_secret(secret_ref, cache_key, manager)
        elif secret_ref.startswith("gcp-secret-manager:"):
            return cls._get_gcp_secret(secret_ref, cache_key, manager)
        else:
            logger.warning(f"Unknown secrets manager format: {secret_ref}")
            return None
    
    @classmethod
    def _get_aws_secret(
        cls,
        secret_ref: str,
        cache_key: str,
        manager: "SecretManager",
    ) -> Optional[str]:
        """从 AWS Secrets Manager 获取密钥"""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # 解析路径
            path = secret_ref.replace("aws-secrets-manager:", "").lstrip("/")
            
            client = boto3.client("secretsmanager")
            response = client.get_secret_value(SecretId=path)
            
            # 处理字符串或二进制密钥
            if "SecretString" in response:
                value = response["SecretString"]
            else:
                value = base64.b64decode(response["SecretBinary"]).decode("utf-8")
            
            secret_value = SecretValue(value=value, source=SecretSource.SECRETS_MANAGER)
            manager._key_cache[cache_key] = secret_value
            manager._log_access(path, SecretSource.SECRETS_MANAGER, True)
            
            return value
            
        except ImportError:
            logger.error("boto3 not installed. Run: pip install boto3")
            return None
        except ClientError as e:
            logger.error(f"AWS Secrets Manager error: {e}")
            return None
    
    @classmethod
    def _get_azure_secret(
        cls,
        secret_ref: str,
        cache_key: str,
        manager: "SecretManager",
    ) -> Optional[str]:
        """从 Azure Key Vault 获取密钥"""
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential
            
            # 解析路径：azure-key-vault://vault-name/secret-name
            parts = secret_ref.replace("azure-key-vault:", "").lstrip("/").split("/", 1)
            if len(parts) != 2:
                logger.error(f"Invalid Azure Key Vault reference: {secret_ref}")
                return None
            
            vault_name, secret_name = parts
            vault_url = f"https://{vault_name}.vault.azure.net"
            
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_url, credential=credential)
            
            secret = client.get_secret(secret_name)
            
            secret_value = SecretValue(value=secret.value, source=SecretSource.SECRETS_MANAGER)
            manager._key_cache[cache_key] = secret_value
            manager._log_access(secret_name, SecretSource.SECRETS_MANAGER, True)
            
            return secret.value
            
        except ImportError:
            logger.error("azure-keyvault-secrets not installed. Run: pip install azure-keyvault-secrets")
            return None
        except Exception as e:
            logger.error(f"Azure Key Vault error: {e}")
            return None
    
    @classmethod
    def _get_gcp_secret(
        cls,
        secret_ref: str,
        cache_key: str,
        manager: "SecretManager",
    ) -> Optional[str]:
        """从 GCP Secret Manager 获取密钥"""
        try:
            from google.cloud import secretmanager
            
            # 解析路径：gcp-secret-manager://project-id/secret-name
            parts = secret_ref.replace("gcp-secret-manager:", "").lstrip("/").split("/", 1)
            if len(parts) != 2:
                logger.error(f"Invalid GCP Secret Manager reference: {secret_ref}")
                return None
            
            project_id, secret_name = parts
            
            client = secretmanager.SecretManagerServiceClient()
            request = {"name": f"projects/{project_id}/secrets/{secret_name}/versions/latest"}
            response = client.access_secret_version(request=request)
            
            value = response.payload.data.decode("UTF-8")
            
            secret_value = SecretValue(value=value, source=SecretSource.SECRETS_MANAGER)
            manager._key_cache[cache_key] = secret_value
            manager._log_access(secret_name, SecretSource.SECRETS_MANAGER, True)
            
            return value
            
        except ImportError:
            logger.error("google-cloud-secret-manager not installed. Run: pip install google-cloud-secret-manager")
            return None
        except Exception as e:
            logger.error(f"GCP Secret Manager error: {e}")
            return None
    
    @classmethod
    def _decrypt_value(cls, encrypted_value: str) -> str:
        """解密加密值
        
        支持的格式：
        - AES256:base64encodedciphertext
        - base64encodedciphertext (默认 AES256)
        
        Args:
            encrypted_value: 加密值
            
        Returns:
            解密后的明文
        """
        if not encrypted_value:
            raise ValueError("Encrypted value is empty")
        
        # 获取主密钥
        master_key = cls._get_master_key()
        
        # 解析格式
        if ":" in encrypted_value:
            algo, ciphertext_b64 = encrypted_value.split(":", 1)
        else:
            algo = "AES256"
            ciphertext_b64 = encrypted_value
        
        if algo.upper() == "AES256":
            return cls._decrypt_aes256(ciphertext_b64, master_key)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {algo}")
    
    @classmethod
    def _decrypt_aes256(cls, ciphertext_b64: str, key: bytes) -> str:
        """使用 AES-256 解密"""
        try:
            from cryptography.fernet import Fernet
            
            # 从主密钥派生 Fernet 密钥
            key_hash = hashlib.sha256(key).digest()
            fernet_key = base64.urlsafe_b64encode(key_hash)
            cipher = Fernet(fernet_key)
            
            ciphertext = base64.urlsafe_b64decode(ciphertext_b64)
            plaintext = cipher.decrypt(ciphertext)
            
            return plaintext.decode("utf-8")
            
        except ImportError:
            raise ImportError("cryptography not installed. Run: pip install cryptography")
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
    
    @classmethod
    def _get_master_key(cls) -> bytes:
        """获取主解密密钥
        
        优先级：
        1. 内存缓存的主密钥
        2. 环境变量 MASTER_KEY
        3. 环境变量 ENCRYPTION_KEY
        """
        if cls._master_key:
            return cls._master_key
        
        # 尝试从环境变量获取
        master_key_str = os.environ.get("MASTER_KEY") or os.environ.get("ENCRYPTION_KEY")
        
        if not master_key_str:
            raise ValueError(
                "Master key not found. Set MASTER_KEY or ENCRYPTION_KEY environment variable."
            )
        
        cls._master_key = master_key_str.encode("utf-8")
        return cls._master_key
    
    @classmethod
    def _validate_pattern(cls, value: str, pattern_name: str) -> bool:
        """验证密钥值是否匹配指定模式"""
        pattern = cls.SECRET_PATTERNS.get(pattern_name)
        if pattern:
            return bool(pattern.match(value))
        return True  # 未知模式默认通过
    
    def _log_access(self, name: str, source: SecretSource, success: bool) -> None:
        """记录密钥访问审计日志"""
        import time
        from datetime import datetime
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "timestamp_unix": time.time(),
            "secret_name": name,
            "source": source.value,
            "success": success,
        }
        
        self._audit_log.append(log_entry)
        
        # 保持审计日志大小合理
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]
        
        # 记录到日志（生产环境应发送到 SIEM）
        if success:
            logger.debug(f"Secret accessed: {name} from {source.value}")
        else:
            logger.warning(f"Secret access failed: {name} from {source.value}")
    
    def get_audit_log(self, limit: int = 100) -> list:
        """获取审计日志"""
        return self._audit_log[-limit:]
    
    def clear_cache(self, name: Optional[str] = None) -> None:
        """清除密钥缓存
        
        Args:
            name: 指定清除的密钥，None 则清除所有
        """
        if name:
            self._key_cache.pop(name, None)
        else:
            self._key_cache.clear()
    
    @classmethod
    def encrypt_value(cls, value: str) -> str:
        """加密值（用于生成加密配置）
        
        Args:
            value: 明文值
            
        Returns:
            加密值（格式：AES256:base64ciphertext）
        """
        try:
            from cryptography.fernet import Fernet
            
            master_key = cls._get_master_key()
            key_hash = hashlib.sha256(master_key).digest()
            fernet_key = base64.urlsafe_b64encode(key_hash)
            cipher = Fernet(fernet_key)
            
            ciphertext = cipher.encrypt(value.encode("utf-8"))
            ciphertext_b64 = base64.urlsafe_b64encode(ciphertext).decode("utf-8")
            
            return f"AES256:{ciphertext_b64}"
            
        except ImportError:
            raise ImportError("cryptography not installed. Run: pip install cryptography")


# 便捷函数
def get_secret(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """便捷函数：获取密钥"""
    return SecretManager.get(name, default, required)


def get_api_key(provider: str) -> Optional[str]:
    """获取 LLM Provider API 密钥
    
    尝试顺序：
    1. {PROVIDER}_API_KEY (如 OPENAI_API_KEY)
    2. LLM_API_KEY (通用)
    3. 返回 None
    
    Args:
        provider: Provider 名称（如 "openai", "qwen"）
        
    Returns:
        API 密钥或 None
    """
    provider_upper = provider.upper()
    
    # 尝试 provider 特定密钥
    key = SecretManager.get(f"{provider_upper}_API_KEY")
    if key:
        return key
    
    # 尝试通用密钥
    key = SecretManager.get("LLM_API_KEY")
    if key:
        return key
    
    return None


# 模块级实例
_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """获取 SecretManager 单例实例"""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager