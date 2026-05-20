"""LLM provider interface — agnostic to OpenAI/Gemini/local."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Iterator

from django.conf import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str: ...

    @abstractmethod
    def stream(self, prompt: str, system: str = "") -> Iterator[str]: ...


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        import httpx
        self._client = httpx.Client(
            base_url=settings.LLM_BASE_URL,
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            timeout=60,
        )
        self._model = settings.LLM_MODEL

    def complete(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.post("/chat/completions", json={"model": self._model, "messages": messages})
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def stream(self, prompt: str, system: str = "") -> Iterator[str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        with self._client.stream("POST", "/chat/completions", json={"model": self._model, "messages": messages, "stream": True}) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    import json
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        pass


def get_llm() -> LLMProvider:
    return OpenAIProvider()
