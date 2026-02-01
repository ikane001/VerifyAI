"""Base LLM client interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str
    model: str
    usage: dict[str, int] | None = None
    raw_response: Any = None

    @property
    def input_tokens(self) -> int:
        """Get input token count."""
        if self.usage:
            return self.usage.get("input_tokens", 0) or self.usage.get("prompt_tokens", 0)
        return 0

    @property
    def output_tokens(self) -> int:
        """Get output token count."""
        if self.usage:
            return self.usage.get("output_tokens", 0) or self.usage.get("completion_tokens", 0)
        return 0


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, model: str, temperature: float = 0.3, max_tokens: int = 4096):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt

        Returns:
            LLMResponse with the generated content
        """
        pass

    @abstractmethod
    async def generate_code(
        self, prompt: str, language: str, system_prompt: str | None = None
    ) -> str:
        """Generate code from the LLM.

        Args:
            prompt: The code generation prompt
            language: Target programming language
            system_prompt: Optional system prompt

        Returns:
            Generated code as string
        """
        pass

    def _extract_code_block(self, content: str, language: str) -> str:
        """Extract code block from markdown-formatted response."""
        import re

        # Try to find code block with language tag
        pattern = rf"```{language}\n(.*?)```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find any code block
        pattern = r"```(?:\w+)?\n(.*?)```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Return content as-is if no code block found
        return content.strip()
