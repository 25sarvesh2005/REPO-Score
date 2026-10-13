"""
Application configuration management using Pydantic Settings.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """RepoScore core application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application & Environment
    APP_NAME: str = Field(default="RepoScore")
    APP_ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    DEBUG: bool = Field(default=False)

    # API Gateway
    API_V1_PREFIX: str = Field(default="/api/v1")
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000", "http://127.0.0.1:3000"])

    # PostgreSQL Relational Datastore
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://reposcore_user:reposcore_pass@localhost:5432/reposcore_db"
    )
    DB_POOL_SIZE: int = Field(default=20, ge=5, le=100)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=50)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=5, le=120)

    # Redis Distributed Job Queue & Pub/Sub
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, ge=5, le=200)

    # Evaluation Limits & Timeouts
    EVALUATION_DEFAULT_TIMEOUT_SECONDS: int = Field(default=600, ge=60, le=3600)
    EVALUATION_MAX_TIMEOUT_SECONDS: int = Field(default=1800, ge=300, le=7200)
    INGESTION_TIMEOUT_SECONDS: int = Field(default=120, ge=10, le=600)
    MAX_REPO_SIZE_BYTES: int = Field(default=250 * 1024 * 1024, ge=1024 * 1024)
    MAX_REPO_FILE_COUNT: int = Field(default=25000, ge=100)
    ALLOW_SUBMODULES: bool = Field(default=False)
    SNAPSHOT_STORAGE_PATH: str = Field(default="repo_snapshots")

    # Rate Limiting & Abuse Prevention
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_PER_MINUTE: int = Field(default=120, ge=10, le=10000)

    # Sandbox Security & Resource Quotas
    SANDBOX_PROVIDER: str = Field(default="docker")
    SANDBOX_DEFAULT_IMAGE_PYTHON: str = Field(default="reposcore/sandbox-python:3.11-slim")
    SANDBOX_DEFAULT_IMAGE_NODE: str = Field(default="reposcore/sandbox-node:20-slim")
    SANDBOX_MAX_MEMORY_MB: int = Field(default=2048, ge=512, le=8192)
    SANDBOX_MAX_CPUS: float = Field(default=2.0, ge=0.5, le=8.0)
    SANDBOX_MAX_PIDS: int = Field(default=128, ge=32, le=1024)

    # AI Auxiliary Provider (Local Ollama Default)
    AI_PROVIDER: str = Field(default="ollama")
    AI_BASE_URL: str = Field(default="http://localhost:11434")
    AI_MODEL_NAME: str = Field(default="llama3.2:3b")
    AI_TEMPERATURE: float = Field(default=0.1, ge=0.0, le=1.0)
    AI_TIMEOUT_SECONDS: int = Field(default=60, ge=5, le=300)

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL '{v}'. Must be one of {valid_levels}")
        return upper_v

    @field_validator("SANDBOX_PROVIDER")
    @classmethod
    def validate_sandbox_provider(cls, v: str) -> str:
        valid_providers = {"docker"}
        lower_v = v.lower()
        if lower_v not in valid_providers:
            raise ValueError(f"Invalid SANDBOX_PROVIDER '{v}'. Must be one of {valid_providers}")
        return lower_v

    @field_validator("AI_PROVIDER")
    @classmethod
    def validate_ai_provider(cls, v: str) -> str:
        valid_providers = {"ollama", "external"}
        lower_v = v.lower()
        if lower_v not in valid_providers:
            raise ValueError(f"Invalid AI_PROVIDER '{v}'. Must be one of {valid_providers}")
        return lower_v


# Global singleton instance
settings = Settings()
