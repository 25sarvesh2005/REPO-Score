"""
Unit tests for configuration validation.
"""

import pytest
from backend.core.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.APP_NAME == "RepoScore"
    assert settings.APP_ENV in ("development", "testing", "production")
    assert settings.PORT == 8000
    assert settings.AI_PROVIDER == "ollama"
    assert settings.SANDBOX_MAX_MEMORY_MB == 2048


def test_log_level_validation():
    settings = Settings(LOG_LEVEL="debug")
    assert settings.LOG_LEVEL == "DEBUG"

    with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
        Settings(LOG_LEVEL="INVALID_LEVEL")


def test_ai_provider_validation():
    settings = Settings(AI_PROVIDER="MOCK")
    assert settings.AI_PROVIDER == "mock"

    with pytest.raises(ValueError, match="Invalid AI_PROVIDER"):
        Settings(AI_PROVIDER="unsupported_ai")
