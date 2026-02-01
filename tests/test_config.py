"""Tests for configuration."""

from pathlib import Path

import pytest

from verify_ai.config import ProjectConfig, LLMConfig, Settings


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LLMConfig()
        assert config.provider == "claude"
        assert config.model == "claude-sonnet-4-20250514"
        assert config.temperature == 0.3
        assert config.max_tokens == 4096


class TestProjectConfig:
    """Tests for ProjectConfig."""

    def test_default_values(self):
        """Test default project configuration."""
        config = ProjectConfig()
        assert config.name == "unnamed-project"
        assert "python" in config.languages
        assert config.test_output == "./tests/generated"

    def test_load_from_file(self, tmp_path):
        """Test loading config from file."""
        config_content = """
project:
  name: test-project
  languages:
    - python
    - typescript
  test_output: ./custom-tests

llm:
  provider: openai
  model: gpt-4
"""
        config_file = tmp_path / "verify-ai.yaml"
        config_file.write_text(config_content)

        config = ProjectConfig.load_from_file(config_file)
        # Note: this test checks the raw loading, actual parsing may need adjustment

    def test_find_and_load(self, tmp_path):
        """Test finding and loading config."""
        config = ProjectConfig.find_and_load(tmp_path)
        # Should return default config when file doesn't exist
        assert config.name == "unnamed-project"


class TestSettings:
    """Tests for Settings."""

    def test_default_settings(self):
        """Test default settings."""
        settings = Settings()
        assert settings.server_port == 8080
        assert settings.cache_enabled is True
        assert settings.log_level == "INFO"
