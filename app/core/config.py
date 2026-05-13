"""Application configuration and settings management."""

from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = Field(..., description="PostgreSQL async connection string")

    # Server
    port_http: int = 8000
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )
    log_requests: bool = True

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dims: int = 1536

    # Pomelo (Card Provider)
    pomelo_api_key: str = Field(default="", description="Pomelo API key")
    pomelo_base_url: str = "https://api.pomelo.dev"

    # Tavily (Web Search)
    tavily_api_key: str = Field(default="", description="Tavily API key")

    # LangFuse (Tracing)
    langfuse_public_key: str = Field(default="", description="LangFuse public key")
    langfuse_secret_key: str = Field(default="", description="LangFuse secret key")

    # Authentication
    hmac_secret: str = Field(..., description="Shared HMAC secret")

    # Workers
    max_workers: int = 4

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("database_url must start with 'postgresql+asyncpg://'")
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        if v not in ("development", "staging", "production"):
            raise ValueError(
                f"environment must be one of: development, staging, production. Got: {v}"
            )
        return v


settings = Settings()
