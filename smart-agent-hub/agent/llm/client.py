"""LLM Client for Smart Agent Hub."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from agent.core.settings import LLMSettings


@dataclass
class LLMMessage:
    """A message in the conversation."""
    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    usage: dict = field(default_factory=dict)
    raw_response: Optional[dict] = None

    def parse_json(self) -> dict:
        """Parse response as JSON."""
        return json.loads(self.content)


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat request to the LLM.

        Args:
            messages: List of messages in the conversation.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with the generated content.
        """
        pass


class QwenLLMClient(BaseLLMClient):
    """Qwen LLM Client using DashScope API."""

    def __init__(
        self,
        settings: Optional[LLMSettings] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize Qwen LLM Client.

        Args:
            settings: LLM settings configuration.
            api_key: API key (overrides settings if provided).
        """
        self.settings = settings or LLMSettings()
        self.api_key = api_key or self.settings.api_key
        self.base_url = self.settings.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.model = self.settings.model
        # 增加超时时间到 120 秒
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0, read=90.0))

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Send a chat request to Qwen.

        Args:
            messages: List of messages in the conversation.
            temperature: Sampling temperature (uses settings default if not provided).
            max_tokens: Maximum tokens to generate (uses settings default if not provided).

        Returns:
            LLMResponse with the generated content.
        """
        temperature = temperature if temperature is not None else self.settings.temperature
        max_tokens = max_tokens if max_tokens is not None else self.settings.max_tokens

        # Convert messages to API format
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": api_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            usage=usage,
            raw_response=data,
        )


class OpenAILLMClient(BaseLLMClient):
    """OpenAI LLM Client."""

    def __init__(
        self,
        settings: Optional[LLMSettings] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize OpenAI LLM Client.

        Args:
            settings: LLM settings configuration.
            api_key: API key (overrides settings if provided).
            base_url: Base URL (overrides settings if provided).
        """
        self.settings = settings or LLMSettings()
        self.api_key = api_key or self.settings.api_key
        self.base_url = base_url or self.settings.base_url or "https://api.openai.com/v1"
        self.model = self.settings.model or "gpt-4o-mini"
        self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Send a chat request to OpenAI.

        Args:
            messages: List of messages in the conversation.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with the generated content.
        """
        temperature = temperature if temperature is not None else self.settings.temperature
        max_tokens = max_tokens if max_tokens is not None else self.settings.max_tokens

        api_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": api_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            usage=usage,
            raw_response=data,
        )


class LLMClient:
    """Factory for creating LLM clients."""

    _clients: dict[str, type[BaseLLMClient]] = {
        "qwen": QwenLLMClient,
        "openai": OpenAILLMClient,
    }

    @classmethod
    def create(
        cls,
        provider: str = "qwen",
        settings: Optional[LLMSettings] = None,
        api_key: Optional[str] = None,
    ) -> BaseLLMClient:
        """Create an LLM client for the specified provider.

        Args:
            provider: LLM provider name (qwen, openai, etc.).
            settings: LLM settings configuration.
            api_key: Optional API key.

        Returns:
            Configured LLM client instance.

        Raises:
            ValueError: If provider is not supported.
        """
        if provider not in cls._clients:
            supported = list(cls._clients.keys())
            raise ValueError(
                f"Unsupported provider: {provider}. Supported: {supported}"
            )

        client_class = cls._clients[provider]
        return client_class(settings=settings, api_key=api_key)

    @classmethod
    def register_provider(
        cls,
        name: str,
        client_class: type[BaseLLMClient],
    ) -> None:
        """Register a new LLM provider.

        Args:
            name: Provider name.
            client_class: Client class implementing BaseLLMClient.
        """
        cls._clients[name] = client_class

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered providers.

        Returns:
            List of provider names.
        """
        return list(cls._clients.keys())