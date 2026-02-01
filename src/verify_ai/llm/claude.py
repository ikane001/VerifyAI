"""Claude LLM client implementation."""

import anthropic

from ..config import settings
from .base import LLMClient, LLMResponse


class ClaudeClient(LLMClient):
    """Claude API client."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", temperature: float = 0.3, max_tokens: int = 4096):
        super().__init__(model, temperature, max_tokens)
        api_key = settings.claude_api_key
        if not api_key:
            raise ValueError("CLAUDE_API_KEY not set. Please set VAI_CLAUDE_API_KEY environment variable or configure Claude Code.")

        # Support custom base URL (e.g., for Claude Code proxy)
        kwargs = {"api_key": api_key}
        if settings.claude_base_url:
            kwargs["base_url"] = settings.claude_base_url

        self.client = anthropic.AsyncAnthropic(**kwargs)

    async def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Generate a response using Claude."""
        messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": messages,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self.client.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            raw_response=response,
        )

    async def generate_code(
        self, prompt: str, language: str, system_prompt: str | None = None
    ) -> str:
        """Generate code using Claude."""
        code_system_prompt = f"""You are an expert {language} developer and test engineer.
Generate clean, well-documented, production-ready code.
Always wrap your code in ```{language} code blocks.
{system_prompt or ''}"""

        response = await self.generate(prompt, system_prompt=code_system_prompt)
        return self._extract_code_block(response.content, language)
