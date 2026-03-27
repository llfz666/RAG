"""
Token Monitor 配置模块

安全设计原则：
1. 使用数据类避免字典访问错误
2. 配置优先级：环境变量 > YAML 配置 > 默认值
3. 支持命名空间隔离避免冲突
4. 完整的配置验证
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class TokenMonitorConfig:
    """
    Token 监控配置类
    
    所有字段都有默认值，确保配置不完整时不会崩溃
    
    属性:
        enabled: 是否启用监控
        database_path: SQLite 数据库路径
        log_file: JSONL 日志文件路径
        default_daily_budget: 默认每日预算（元）
        default_monthly_budget: 默认每月预算（元）
        alert_threshold: 告警阈值（0-1）
        alerts_enabled: 是否启用告警
        alert_email: 告警邮箱
        sampling_enabled: 是否启用采样
        sampling_rate: 采样率（0-1）
        namespace: 配置命名空间标识
    """
    
    # 基础配置
    enabled: bool = True
    database_path: str = "data/token_usage.db"
    log_file: str = "logs/token_usage.jsonl"
    
    # 预算配置
    default_daily_budget: float = 10.0
    default_monthly_budget: float = 300.0
    alert_threshold: float = 0.8
    
    # 告警配置
    alerts_enabled: bool = True
    alert_email: Optional[str] = None
    alert_wechat_webhook: Optional[str] = None
    
    # 采样配置
    sampling_enabled: bool = False
    sampling_rate: float = 1.0
    
    # 命名空间标识（用于区分不同应用）
    namespace: str = "default"
    
    # 模型定价配置（每 1K tokens 价格，单位：元）
    model_pricing: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        # OpenAI
        "gpt-4": {"input": 0.064, "output": 0.128},
        "gpt-4-turbo": {"input": 0.024, "output": 0.048},
        "gpt-4o": {"input": 0.028, "output": 0.084},
        "gpt-4o-mini": {"input": 0.0011, "output": 0.0033},
        "gpt-3.5-turbo": {"input": 0.0035, "output": 0.0052},
        # Azure OpenAI
        "azure/gpt-4": {"input": 0.064, "output": 0.128},
        "azure/gpt-35-turbo": {"input": 0.0035, "output": 0.0052},
        # 通义千问
        "qwen-plus": {"input": 0.004, "output": 0.012},
        "qwen-turbo": {"input": 0.002, "output": 0.006},
        "qwen-max": {"input": 0.02, "output": 0.06},
        # DeepSeek
        "deepseek-chat": {"input": 0.001, "output": 0.002},
        "deepseek-coder": {"input": 0.001, "output": 0.002},
        # 其他
        "default": {"input": 0.01, "output": 0.03},  # 默认定价
    })
    
    @classmethod
    def from_yaml(
        cls, 
        config_path: str, 
        namespace: str = "token_monitor",
        env_prefix: str = "TOKEN_MONITOR"
    ) -> "TokenMonitorConfig":
        """
        从 YAML 配置文件加载配置
        
        配置优先级：
        1. 环境变量（最高优先级）
        2. YAML 配置文件
        3. 默认值
        
        Args:
            config_path: YAML 配置文件路径
            namespace: 配置命名空间
            env_prefix: 环境变量前缀
        
        Returns:
            TokenMonitorConfig 实例
        """
        config_data: Dict[str, Any] = {}
        
        # 1. 首先尝试加载 YAML 配置
        yaml_config = cls._load_yaml_config(config_path, namespace)
        if yaml_config:
            config_data.update(yaml_config)
        
        # 2. 从环境变量覆盖
        env_config = cls._load_env_config(env_prefix)
        config_data.update(env_config)
        
        # 3. 创建配置实例
        return cls(
            enabled=config_data.get('enabled', True),
            database_path=config_data.get('database_path', "data/token_usage.db"),
            log_file=config_data.get('log_file', "logs/token_usage.jsonl"),
            default_daily_budget=config_data.get('default_daily_budget', 10.0),
            default_monthly_budget=config_data.get('default_monthly_budget', 300.0),
            alert_threshold=config_data.get('alert_threshold', 0.8),
            alerts_enabled=config_data.get('alerts_enabled', True),
            alert_email=config_data.get('alert_email'),
            alert_wechat_webhook=config_data.get('alert_wechat_webhook'),
            sampling_enabled=config_data.get('sampling_enabled', False),
            sampling_rate=config_data.get('sampling_rate', 1.0),
            namespace=namespace,
            model_pricing=config_data.get('model_pricing', cls.__dataclass_fields__['model_pricing'].default_factory()),
        )
    
    @staticmethod
    def _load_yaml_config(config_path: str, namespace: str) -> Optional[Dict[str, Any]]:
        """从 YAML 文件加载配置"""
        try:
            path = Path(config_path)
            if not path.exists():
                return None
            
            with open(path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
            
            if not raw_config:
                return None
            
            # 获取命名空间下的配置
            config_data = raw_config.get(namespace, {})
            
            # 合并 budgets 子配置
            if 'budgets' in config_data:
                budgets = config_data['budgets']
                config_data['default_daily_budget'] = budgets.get('default_daily', config_data.get('default_daily_budget'))
                config_data['default_monthly_budget'] = budgets.get('default_monthly', config_data.get('default_monthly_budget'))
                config_data['alert_threshold'] = budgets.get('alert_threshold', config_data.get('alert_threshold'))
            
            # 合并 alerts 子配置
            if 'alerts' in config_data:
                alerts = config_data['alerts']
                config_data['alerts_enabled'] = alerts.get('enabled', config_data.get('alerts_enabled'))
                config_data['alert_email'] = alerts.get('email', config_data.get('alert_email'))
                config_data['alert_wechat_webhook'] = alerts.get('wechat_webhook', config_data.get('alert_wechat_webhook'))
            
            # 合并 sampling 子配置
            if 'sampling' in config_data:
                sampling = config_data['sampling']
                config_data['sampling_enabled'] = sampling.get('enabled', config_data.get('sampling_enabled'))
                config_data['sampling_rate'] = sampling.get('rate', config_data.get('sampling_rate'))
            
            # 合并 model_pricing 配置
            if 'model_pricing' in config_data:
                existing_pricing = Config.model_pricing if hasattr(Config, 'model_pricing') else {}
                existing_pricing.update(config_data['model_pricing'])
                config_data['model_pricing'] = existing_pricing
            
            return config_data
            
        except Exception as e:
            # 配置文件加载失败时返回 None，使用默认值
            print(f"Warning: 加载配置文件失败：{e}")
            return None
    
    @staticmethod
    def _load_env_config(env_prefix: str) -> Dict[str, Any]:
        """从环境变量加载配置"""
        config: Dict[str, Any] = {}
        
        # 布尔值转换
        def parse_bool(value: Optional[str]) -> Optional[bool]:
            if value is None:
                return None
            return str(value).lower() in ('true', '1', 'yes', 'on')
        
        # 浮点数转换
        def parse_float(value: Optional[str]) -> Optional[float]:
            if value is None:
                return None
            try:
                return float(value)
            except ValueError:
                return None
        
        # 映射环境变量到配置字段
        env_mapping = {
            'ENABLED': 'enabled',
            'DB_PATH': 'database_path',
            'LOG_FILE': 'log_file',
            'DAILY_BUDGET': 'default_daily_budget',
            'MONTHLY_BUDGET': 'default_monthly_budget',
            'ALERT_THRESHOLD': 'alert_threshold',
            'ALERTS_ENABLED': 'alerts_enabled',
            'ALERT_EMAIL': 'alert_email',
            'ALERT_WECHAT_WEBHOOK': 'alert_wechat_webhook',
            'SAMPLING_ENABLED': 'sampling_enabled',
            'SAMPLING_RATE': 'sampling_rate',
        }
        
        for env_key, config_key in env_mapping.items():
            value = os.getenv(f"{env_prefix}_{env_key}")
            if value:
                if config_key.endswith('_enabled'):
                    config[config_key] = parse_bool(value)
                elif config_key in ('default_daily_budget', 'default_monthly_budget', 
                                   'alert_threshold', 'sampling_rate'):
                    config[config_key] = parse_float(value)
                else:
                    config[config_key] = value
        
        return config
    
    def validate(self) -> List[str]:
        """
        验证配置有效性
        
        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors: List[str] = []
        
        # 检查 alert_threshold 范围
        if not 0 <= self.alert_threshold <= 1:
            errors.append(f"alert_threshold 必须在 0-1 之间，当前：{self.alert_threshold}")
        
        # 检查 sampling_rate 范围
        if not 0 < self.sampling_rate <= 1:
            errors.append(f"sampling_rate 必须在 0-1 之间，当前：{self.sampling_rate}")
        
        # 检查预算值
        if self.default_daily_budget < 0:
            errors.append(f"default_daily_budget 不能为负数，当前：{self.default_daily_budget}")
        
        if self.default_monthly_budget < 0:
            errors.append(f"default_monthly_budget 不能为负数，当前：{self.default_monthly_budget}")
        
        # 检查数据库路径
        db_path = Path(self.database_path)
        db_dir = db_path.parent
        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建数据库目录 {db_dir}: {e}")
        
        # 检查日志路径
        log_path = Path(self.log_file)
        log_dir = log_path.parent
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建日志目录 {log_dir}: {e}")
        
        # 检查模型定价配置
        for model, pricing in self.model_pricing.items():
            if not isinstance(pricing, dict):
                errors.append(f"模型 {model} 的定价配置格式错误")
                continue
            if 'input' not in pricing or 'output' not in pricing:
                errors.append(f"模型 {model} 的定价缺少 input 或 output 字段")
        
        return errors
    
    def get_model_price(self, model: str) -> Dict[str, float]:
        """
        获取模型定价
        
        Args:
            model: 模型名称
        
        Returns:
            包含 input 和 output 价格的字典
        """
        # 直接匹配
        if model in self.model_pricing:
            return self.model_pricing[model]
        
        # 尝试去掉前缀匹配（如 azure/gpt-4 -> gpt-4）
        if '/' in model:
            simple_name = model.split('/')[-1]
            if simple_name in self.model_pricing:
                return self.model_pricing[simple_name]
        
        # 返回默认定价
        return self.model_pricing.get('default', {'input': 0.01, 'output': 0.03})
    
    def calculate_cost(
        self, 
        model: str, 
        prompt_tokens: int, 
        completion_tokens: int
    ) -> float:
        """
        计算 LLM 调用成本
        
        Args:
            model: 模型名称
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
        
        Returns:
            成本（元）
        """
        pricing = self.get_model_price(model)
        
        input_cost = (prompt_tokens / 1000) * pricing['input']
        output_cost = (completion_tokens / 1000) * pricing['output']
        
        return input_cost + output_cost


# 模块级 Config 类别名（保持向后兼容）
Config = TokenMonitorConfig