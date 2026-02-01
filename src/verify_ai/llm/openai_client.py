"""OpenAI LLM client implementation."""

import openai

from ..config import settings
from .base import LLMClient, LLMResponse


class OpenAIClient(LLMClient):
    """OpenAI API client."""

    def __init__(self, model: str = "gpt-4-turbo-preview", temperature: float = 0.3, max_tokens: int = 4096):
        super().__init__(model, temperature, max_tokens)
        api_key = settings.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Please set VAI_OPENAI_API_KEY environment variable.")
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Generate a response using OpenAI."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        content = response.choices[0].message.content or ""

        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }

        return LLMResponse(
            content=content,
            model=response.model,
            usage=usage,
            raw_response=response,
        )

    async def generate_code(
        self, prompt: str, language: str, system_prompt: str | None = None
    ) -> str:
        """Generate code using OpenAI."""
        code_system_prompt = f"""You are an expert {language} developer and test engineer.
Generate clean, well-documented, production-ready code.
Always wrap your code in ```{language} code blocks.
{system_prompt or ''}"""

        response = await self.generate(prompt, system_prompt=code_system_prompt)
        return self._extract_code_block(response.content, language)
