"""Anthropic provider using the native `anthropic` Python SDK."""

import json
import re

import anthropic

from app.infrastructure.llm.base import LLMMessage, LLMProvider


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        api_key: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    def _split_messages(self, messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        """Anthropic requires system prompt separate from conversation."""
        system = ""
        conv: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                conv.append({"role": m["role"], "content": m["content"]})
        return system, conv

    async def invoke(self, messages: list[LLMMessage], **kwargs) -> str:
        system, conv = self._split_messages(messages)
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
            system=system,
            messages=conv,
        )
        return response.content[0].text if response.content else ""

    async def invoke_json(self, messages: list[LLMMessage], **kwargs) -> dict:
        raw = await self.invoke(messages, **kwargs)
        cleaned = _strip_fences(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM did not return valid JSON.\nRaw: {raw!r}") from exc
