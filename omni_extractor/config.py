"""Configuration management for omni-extractor."""

from typing import Optional

from pydantic import Field, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI configuration
    openai_api_key: str = Field(description="OpenAI API key for content extraction")
    openai_base_url: Optional[str] = Field(
        default=None, description="Custom OpenAI API base URL (optional)"
    )
    openai_model: str = Field(
        default="gpt-4o-mini", description="OpenAI model to use for extraction"
    )

    # HTTP configuration
    http_timeout: PositiveFloat = Field(
        default=30.0, description="HTTP request timeout in seconds"
    )

    # Concurrency configuration
    max_concurrent_fetch: PositiveInt = Field(
        default=20, description="Maximum concurrent HTTP fetch operations"
    )
    max_concurrent_extract: PositiveInt = Field(
        default=5, description="Maximum concurrent OpenAI extraction operations"
    )

    # Retry configuration
    max_retries: PositiveInt = Field(
        default=3, description="Maximum number of retry attempts for failed operations"
    )
    retry_base_delay: PositiveFloat = Field(
        default=0.5, description="Base delay in seconds for exponential backoff"
    )

    # Logging configuration
    log_level: str = Field(
        default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # Ignore extra environment variables
    }


__all__ = ["Settings"]
