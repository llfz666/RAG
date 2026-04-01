"""Configuration management for Smart Agent Hub."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class EmbeddingSettings(BaseModel):
    """Embedding configuration."""

    provider: str = Field(default="qwen", description="Embedding provider")
    model: str = Field(default="text-embedding-v3", description="Model name")
    base_url: Optional[str] = Field(None, description="API base URL")
    api_key: Optional[str] = Field(None, description="API key")
    dimensions: int = Field(default=1024, description="Embedding dimensions")


class VectorStoreSettings(BaseModel):
    """Vector store configuration."""

    provider: str = Field(default="chroma", description="Vector store provider")
    persist_directory: str = Field(default="data/db/chroma", description="Persistence directory")


class LLMSettings(BaseModel):
    """LLM configuration."""

    provider: str = Field(default="qwen", description="LLM provider")
    model: str = Field(default="qwen3.5-plus", description="Model name")
    base_url: Optional[str] = Field(None, description="API base URL")
    api_key: Optional[str] = Field(None, description="API key")
    temperature: float = Field(default=0.0, ge=0, le=2, description="Temperature")
    max_tokens: int = Field(default=4096, ge=1, description="Max tokens")


class AgentSettings(BaseModel):
    """Agent configuration."""

    max_iterations: int = Field(default=10, ge=1, description="Max ReAct iterations")
    enable_reflection: bool = Field(default=True, description="Enable reflection")
    enable_memory: bool = Field(default=True, description="Enable memory")


class StorageSettings(BaseModel):
    """Storage configuration."""

    db_path: str = Field(default="data/db/agent_sessions.db", description="SQLite DB path")
    log_path: str = Field(default="data/logs/agent_traces.jsonl", description="JSONL log path")


class DashboardSettings(BaseModel):
    """Dashboard configuration."""

    enabled: bool = Field(default=True, description="Enable dashboard")
    port: int = Field(default=8502, ge=1, le=65535, description="Dashboard port")


class ChatSettings(BaseModel):
    """Chat service configuration."""

    fallback_to_llm: bool = Field(
        default=True,
        description="Whether to fallback to LLM when knowledge base search returns empty results",
    )
    empty_search_message: str = Field(
        default="抱歉，知识库中未找到与您的问题相关的内容。请尝试使用不同的关键词或扩大搜索范围。",
        description="Message to show when knowledge base search returns no results",
    )
    enable_rag: bool = Field(default=True, description="Enable RAG-based knowledge retrieval")


class MCPServerSettings(BaseModel):
    """MCP Server configuration."""

    enabled: bool = Field(default=True, description="Enable server")
    command: str = Field(default="python", description="Command to run")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    cwd: str = Field(default=".", description="Working directory")
    timeout: int = Field(default=60, ge=1, description="Timeout in seconds")
    tools: list[str] = Field(default_factory=list, description="Available tools")


class MCPServersSettings(BaseModel):
    """MCP Servers configuration."""

    rag_server: MCPServerSettings = Field(default_factory=MCPServerSettings)


class Settings(BaseModel):
    """Main settings container."""

    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)
    chat: ChatSettings = Field(default_factory=ChatSettings)
    mcp_servers: MCPServersSettings = Field(default_factory=MCPServersSettings)

    @classmethod
    def expand_env_vars(cls, value: str) -> str:
        """Expand environment variables in string values."""
        if not isinstance(value, str):
            return value

        def replace_env(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(r"\$\{(\w+)\}", replace_env, value)

    @classmethod
    def process_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Process dictionary values to expand environment variables."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = cls.expand_env_vars(value)
            elif isinstance(value, dict):
                result[key] = cls.process_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    cls.expand_env_vars(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> Settings:
        """Load settings from YAML file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        if not raw_data:
            raise ValueError("Config file is empty")

        # Process data to expand environment variables
        processed_data = cls.process_dict(raw_data)

        # Handle nested settings structure
        settings_data = {}
        if "settings" in processed_data:
            settings_data = processed_data["settings"]
        else:
            settings_data = processed_data

        return cls.model_validate(settings_data)

    @classmethod
    def from_env(cls) -> Settings:
        """Create settings from environment variables."""
        return cls()


def load_settings(config_path: Optional[str | Path] = None) -> Settings:
    """Load settings from file or environment."""
    if config_path is None:
        # Try default paths
        default_paths = [
            Path("config/settings.yaml"),
            Path(__file__).parent.parent.parent / "config" / "settings.yaml",
        ]
        for path in default_paths:
            if path.exists():
                return Settings.from_yaml(path)
        return Settings.from_env()
    else:
        return Settings.from_yaml(config_path)


# Default instance for quick access
_default_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get default settings instance."""
    global _default_settings
    if _default_settings is None:
        _default_settings = load_settings()
    return _default_settings