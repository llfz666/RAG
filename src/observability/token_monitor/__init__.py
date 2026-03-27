"""
Token 监控模块 - 用于追踪 LLM 调用的 token 使用和成本

安全导入设计：
- 使用延迟导入避免循环依赖
- 所有导出通过 __all__ 明确声明
- 单例注册表确保全局唯一实例
"""

from typing import Optional, TYPE_CHECKING

# 延迟导入避免循环依赖
if TYPE_CHECKING:
    from .tracker import TokenTracker
    from .budget import BudgetManager
    from .config import TokenMonitorConfig

__all__ = [
    'TokenMonitorRegistry',
    'global_registry',
    'get_tracker',
    'get_budget_manager',
    'get_config',
    'TokenTracker',
    'BudgetManager',
    'TokenMonitorConfig',
]


class TokenMonitorRegistry:
    """
    单例注册表 - 避免重复初始化和配置冲突
    
    使用方式：
        # 初始化（在应用启动时调用一次）
        global_registry.initialize("config/settings.yaml")
        
        # 获取组件
        tracker = global_registry.tracker
        budget_mgr = global_registry.budget_manager
    """
    
    _instance: Optional["TokenMonitorRegistry"] = None
    _tracker: Optional["TokenTracker"] = None
    _budget_manager: Optional["BudgetManager"] = None
    _config: Optional["TokenMonitorConfig"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "TokenMonitorRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 防止重复初始化
        if self._initialized:
            return
    
    def initialize(
        self, 
        config_path: str, 
        namespace: str = "token_monitor",
        namespace_prefix: Optional[str] = None
    ) -> None:
        """
        初始化所有组件
        
        Args:
            config_path: 配置文件路径
            namespace: 配置命名空间（默认：token_monitor）
            namespace_prefix: 环境变量前缀（默认：TOKEN_MONITOR）
        
        Raises:
            ValueError: 配置验证失败
            FileNotFoundError: 配置文件不存在
        """
        if self._initialized:
            return  # 已初始化，直接返回
        
        # 延迟导入，避免循环依赖
        from .config import TokenMonitorConfig
        from .tracker import TokenTracker
        from .budget import BudgetManager
        
        # 1. 加载配置
        self._config = TokenMonitorConfig.from_yaml(
            config_path=config_path,
            namespace=namespace,
            env_prefix=namespace_prefix or "TOKEN_MONITOR"
        )
        
        # 2. 验证配置
        errors = self._config.validate()
        if errors:
            raise ValueError(f"Token Monitor 配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors))
        
        # 3. 初始化组件
        self._tracker = TokenTracker(self._config)
        self._budget_manager = BudgetManager(self._tracker, self._config)
        
        self._initialized = True
    
    def ensure_initialized(self) -> None:
        """确保已初始化，否则抛出友好错误"""
        if not self._initialized:
            raise RuntimeError(
                "TokenMonitor 未初始化。请在应用启动时调用:\n"
                "  from src.observability.token_monitor import global_registry\n"
                "  global_registry.initialize('config/settings.yaml')"
            )
    
    @property
    def tracker(self) -> "TokenTracker":
        self.ensure_initialized()
        return self._tracker  # type: ignore
    
    @property
    def budget_manager(self) -> "BudgetManager":
        self.ensure_initialized()
        return self._budget_manager  # type: ignore
    
    @property
    def config(self) -> "TokenMonitorConfig":
        self.ensure_initialized()
        return self._config  # type: ignore
    
    def reset(self) -> None:
        """重置注册表（主要用于测试）"""
        self._initialized = False
        self._tracker = None
        self._budget_manager = None
        self._config = None


# 全局单例
global_registry = TokenMonitorRegistry()


def get_tracker() -> "TokenTracker":
    """获取全局 TokenTracker 实例"""
    return global_registry.tracker


def get_budget_manager() -> "BudgetManager":
    """获取全局 BudgetManager 实例"""
    return global_registry.budget_manager


def get_config() -> "TokenMonitorConfig":
    """获取全局配置实例"""
    return global_registry.config