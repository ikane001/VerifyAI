"""Factory for creating LLM clients."""

from typing import Literal

from ..config import LLMConfig, settings
from .base import LLMClient
from .claude import ClaudeClient
from .ollama_client import OllamaClient
from .openai_client import OpenAIClient


def create_llm_client(
    provider: Literal["claude", "openai", "ollama"] | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    config: LLMConfig | None = None,
) -> LLMClient:
    """Create an LLM client based on provider.

    Args:
        provider: LLM provider name ("claude", "openai", "ollama")
        model: Model name to use
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        config: Optional LLMConfig to use instead of individual params

    Returns:
        LLMClient instance

    Raises:
        ValueError: If provider is not supported or API key is missing
    """
    if config:
        provider = config.provider
        model = config.model
        temperature = config.temperature
        max_tokens = config.max_tokens

    if provider is None:
        provider = "claude"

    if provider == "claude":
        model = model or "claude-sonnet-4-20250514"
        return ClaudeClient(model=model, temperature=temperature, max_tokens=max_tokens)

    elif provider == "openai":
        model = model or "gpt-4-turbo-preview"
        return OpenAIClient(model=model, temperature=temperature, max_tokens=max_tokens)

    elif provider == "ollama":
        # Handle model format like "ollama/codellama"
        if model and "/" in model:
            model = model.split("/")[-1]
        model = model or "codellama"
        return OllamaClient(model=model, temperature=temperature, max_tokens=max_tokens)

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


async def create_llm_client_with_fallback(
    primary_provider: Literal["claude", "openai", "ollama"],
    fallback_provider: str | None = None,
    **kwargs,
) -> LLMClient:
    """Create LLM client with fallback support.

    If primary provider fails, try fallback.
    """
    try:
        client = create_llm_client(provider=primary_provider, **kwargs)
        # Test if client works (for Ollama, check availability)
        if primary_provider == "ollama":
            if not await client.is_available():
                raise ConnectionError("Ollama server not available")
        return client
    except Exception as e:
        if fallback_provider:
            # Parse fallback like "ollama/codellama"
            if "/" in fallback_provider:
                parts = fallback_provider.split("/")
                fb_provider = parts[0]
                fb_model = parts[1] if len(parts) > 1 else None
            else:
                fb_provider = fallback_provider
                fb_model = None

            return create_llm_client(
                provider=fb_provider,  # type: ignore
                model=fb_model,
                **kwargs,
            )
        raise e
