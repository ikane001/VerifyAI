"""Configuration management for VerifyAI."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: Literal["claude", "openai", "ollama"] = "claude"
    model: str = "claude-sonnet-4-20250514"
    fallback: str | None = "ollama/codellama"
    temperature: float = 0.3
    max_tokens: int = 4096


class TriggerConfig(BaseModel):
    """Trigger configuration for different events."""

    push: list[str] = Field(default_factory=lambda: ["lint", "affected_unit_tests"])
    pull_request: list[str] = Field(
        default_factory=lambda: ["unit_tests", "integration_tests", "ai_review"]
    )
    merge_to_main: list[str] = Field(default_factory=lambda: ["regression_tests", "e2e_tests"])
    scheduled_cron: str = "0 2 * * *"
    scheduled_jobs: list[str] = Field(
        default_factory=lambda: ["full_regression", "test_regeneration"]
    )


class FixConfig(BaseModel):
    """Auto-fix configuration."""

    auto_fix_tests: bool = True
    auto_fix_source: bool = False
    require_approval: bool = True


class CoverageConfig(BaseModel):
    """Coverage analysis configuration."""

    enabled: bool = True
    threshold: float = 80.0
    formats: list[str] = Field(default_factory=lambda: ["console"])
    exclude: list[str] = Field(default_factory=lambda: ["tests/", "*/test_*.py"])
    fail_under: float | None = None  # Fail if coverage below this threshold


class DashboardConfig(BaseModel):
    """Dashboard configuration."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8080
    auto_open_browser: bool = True
    data_retention_days: int = 90
    auto_refresh_seconds: int = 30


class ProjectConfig(BaseModel):
    """Project-level configuration loaded from verify-ai.yaml."""

    name: str = "unnamed-project"
    languages: list[str] = Field(default_factory=lambda: ["python"])
    test_output: str = "./tests/generated"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    triggers: TriggerConfig = Field(default_factory=TriggerConfig)
    fix: FixConfig = Field(default_factory=FixConfig)
    coverage: CoverageConfig = Field(default_factory=CoverageConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)

    @classmethod
    def load_from_file(cls, path: Path) -> "ProjectConfig":
        """Load configuration from a YAML file."""
        if not path.exists():
            return cls()
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    @classmethod
    def find_and_load(cls, project_path: Path) -> "ProjectConfig":
        """Find and load verify-ai.yaml from project path."""
        config_file = project_path / "verify-ai.yaml"
        if not config_file.exists():
            config_file = project_path / "verify-ai.yml"
        return cls.load_from_file(config_file)


class Settings(BaseSettings):
    """Global settings from environment variables."""

    model_config = SettingsConfigDict(env_prefix="VAI_", env_file=".env")

    # LLM API Keys
    claude_api_key: str | None = None
    claude_base_url: str | None = None  # Custom base URL for Claude API
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # GitHub Integration
    github_token: str | None = None
    github_webhook_secret: str | None = None

    # Server Settings
    server_host: str = "0.0.0.0"
    server_port: int = 8080

    # Cache Settings
    cache_enabled: bool = True
    cache_ttl: int = 3600

    # Logging
    log_level: str = "INFO"


def load_claude_code_settings() -> dict:
    """Load settings from Claude Code's settings.json if available."""
    import json
    from pathlib import Path

    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
            return data.get("env", {})
        except Exception:
            pass
    return {}


# Load Claude Code settings and merge
_claude_code_env = load_claude_code_settings()

# Global settings instance
settings = Settings(
    claude_api_key=_claude_code_env.get("ANTHROPIC_AUTH_TOKEN"),
    claude_base_url=_claude_code_env.get("ANTHROPIC_BASE_URL"),
)
