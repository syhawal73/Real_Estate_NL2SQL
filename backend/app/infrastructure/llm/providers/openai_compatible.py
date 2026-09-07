"""OpenAI-compatible provider — covers Ollama, LM Studio, OpenAI, and any
OpenAI-API-compatible endpoint. Uses the official `openai` Python SDK with
configurable base_url.
"""

import json
import re

from openai import AsyncOpenAI

from app.infrastructure.llm.base import LLMMessage, LLMProvider


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` fences."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


class OpenAICompatibleProvider(LLMProvider):
    """Works with any OpenAI-compatible /v1/chat/completions endpoint."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def invoke(self, messages: list[LLMMessage], **kwargs) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
        )
        return response.choices[0].message.content or ""

    async def invoke_json(self, messages: list[LLMMessage], **kwargs) -> dict:
        raw = await self.invoke(messages, **kwargs)
        cleaned = _strip_fences(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM did not return valid JSON.\nRaw output: {raw!r}") from exc
