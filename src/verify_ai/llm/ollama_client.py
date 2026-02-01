"""Ollama LLM client implementation for local models."""

import httpx

from ..config import settings
from .base import LLMClient, LLMResponse


class OllamaClient(LLMClient):
    """Ollama API client for local LLM models."""

    def __init__(self, model: str = "codellama", temperature: float = 0.3, max_tokens: int = 4096):
        super().__init__(model, temperature, max_tokens)
        self.base_url = settings.ollama_base_url.rstrip("/")

    async def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Generate a response using Ollama."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()

        return LLMResponse(
            content=data.get("response", ""),
            model=self.model,
            usage={
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
            raw_response=data,
        )

    async def generate_code(
        self, prompt: str, language: str, system_prompt: str | None = None
    ) -> str:
        """Generate code using Ollama."""
        code_system_prompt = f"""You are an expert {language} developer and test engineer.
Generate clean, well-documented, production-ready code.
Always wrap your code in ```{language} code blocks.
{system_prompt or ''}"""

        response = await self.generate(prompt, system_prompt=code_system_prompt)
        return self._extract_code_block(response.content, language)

    async def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
