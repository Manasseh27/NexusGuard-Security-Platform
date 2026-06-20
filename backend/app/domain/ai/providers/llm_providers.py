"""
LLM Provider abstractions and implementations.
Supports: OpenAI, Anthropic, Ollama, Azure OpenAI.
Decouples provider logic from orchestration.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

import structlog

from app.core.config import settings
from app.domain.ai.providers.models import LLMMessage, LLMResponse, AIProvider

log = structlog.get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    name: AIProvider

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Get a complete response from the LLM."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from the LLM."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        ...


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4 provider."""

    name = AIProvider.OPENAI

    def __init__(self) -> None:
        import openai

        self._client = openai.AsyncOpenAI(api_key=settings.ai.OPENAI_API_KEY)
        self._model = settings.ai.OPENAI_MODEL

    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        start = time.monotonic()
        oai_msgs = [{"role": m.role, "content": m.content} for m in messages]
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=oai_msgs,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            content=resp.choices[0].message.content or "",
            provider=self.name,
            model=self._model,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
            latency_ms=latency,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        oai_msgs = [{"role": m.role, "content": m.content} for m in messages]
        async with self._client.chat.completions.stream(
            model=self._model,
            messages=oai_msgs,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    name = AIProvider.ANTHROPIC

    def __init__(self) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=settings.ai.ANTHROPIC_API_KEY)
        self._model = settings.ai.ANTHROPIC_MODEL

    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        start = time.monotonic()
        system_msg = next((m.content for m in messages if m.role == "system"), None)
        user_msgs = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]

        kwargs: dict[str, Any] = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=user_msgs,
        )
        if system_msg:
            kwargs["system"] = system_msg

        resp = await self._client.messages.create(**kwargs)
        latency = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            content=resp.content[0].text if resp.content else "",
            provider=self.name,
            model=self._model,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
            total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
            latency_ms=latency,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        system_msg = next((m.content for m in messages if m.role == "system"), None)
        user_msgs = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        kwargs: dict[str, Any] = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=user_msgs,
        )
        if system_msg:
            kwargs["system"] = system_msg
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False


class OllamaProvider(LLMProvider):
    """Local LLM via Ollama — no API key required."""

    name = AIProvider.OLLAMA

    def __init__(self) -> None:
        import aiohttp

        self._base_url = settings.ai.OLLAMA_BASE_URL
        self._model = settings.ai.OLLAMA_MODEL
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self):
        import aiohttp

        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=self._base_url,
                timeout=aiohttp.ClientTimeout(total=120),
            )
        return self._session

    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        start = time.monotonic()
        session = await self._get_session()
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with session.post("/api/chat", json=payload) as resp:
            data = await resp.json()
        latency = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            provider=self.name,
            model=self._model,
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            latency_ms=latency,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        import json as _json

        session = await self._get_session()
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with session.post("/api/chat", json=payload) as resp:
            async for line in resp.content:
                if line.strip():
                    chunk = _json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get("/api/tags") as resp:
                return resp.status == 200
        except Exception:
            return False


class LLMProviderRegistry:
    """Registry of available LLM providers with lazy initialization."""

    def __init__(self) -> None:
        self._providers: dict[AIProvider, LLMProvider] = {}

    def _build_provider(self, provider: AIProvider) -> LLMProvider:
        match provider:
            case AIProvider.OPENAI:
                return OpenAIProvider()
            case AIProvider.ANTHROPIC:
                return AnthropicProvider()
            case AIProvider.OLLAMA:
                return OllamaProvider()
            case _:
                raise ValueError(f"Unknown provider: {provider}")

    def get(self, provider: AIProvider) -> LLMProvider:
        if provider not in self._providers:
            self._providers[provider] = self._build_provider(provider)
        return self._providers[provider]

    async def health_status(self) -> dict[str, bool]:
        """Check health of all configured providers."""
        results = {}
        for p in AIProvider:
            try:
                provider = self.get(p)
                results[p.value] = await provider.health_check()
            except Exception:
                results[p.value] = False
        return results
