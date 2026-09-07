"""LLM provider factory.

Creates the correct LLMProvider based on LLM_PROVIDER in settings.
Add new providers here — do not change the agent or graph code.
"""

from app.config.settings import settings
from app.infrastructure.llm.base import LLMProvider


def create_llm_provider(provider_name: str | None = None, model: str | None = None, api_key: str | None = None, base_url: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> LLMProvider:
    """Instantiate a provider from explicit values or environment settings."""
    provider = (provider_name or settings.LLM_PROVIDER).lower()
    model = model or settings.LLM_MODEL
    api_key = api_key or settings.LLM_API_KEY
    base_url = base_url or settings.LLM_BASE_URL
    temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
    max_tokens = settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens

    if provider in ("ollama", "lmstudio", "openai", "gemini", "openai_compatible"):
        from app.infrastructure.llm.providers.openai_compatible import OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            model=model, api_key=api_key, base_url=base_url, temperature=temperature, max_tokens=max_tokens,
        )

    if provider == "anthropic":
        from app.infrastructure.llm.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            model=model, api_key=api_key, temperature=temperature, max_tokens=max_tokens,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {provider!r}. "
        "Supported: ollama, lmstudio, openai, anthropic, gemini"
    )


# Module-level singleton — import this everywhere.
llm_provider: LLMProvider = create_llm_provider()

def set_llm_provider(provider: LLMProvider) -> None:
    global llm_provider
    llm_provider = provider

def get_llm_provider() -> LLMProvider:
    return llm_provider
