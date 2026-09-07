"""Abstract base for all LLM providers (Phase 4)."""

from abc import ABC, abstractmethod
from typing import TypedDict


class LLMMessage(TypedDict):
    role: str    # system | user | assistant
    content: str


class LLMProvider(ABC):
    """Provider-agnostic LLM interface.

    All LLM calls in the agent go through this interface so the graph
    stays decoupled from any specific SDK.
    """

    @abstractmethod
    async def invoke(self, messages: list[LLMMessage], **kwargs) -> str:
        """Send messages and return the assistant text response."""
        ...

    @abstractmethod
    async def invoke_json(self, messages: list[LLMMessage], **kwargs) -> dict:
        """Send messages and parse the response as JSON.

        The implementation must strip markdown code fences before parsing.
        """
        ...
