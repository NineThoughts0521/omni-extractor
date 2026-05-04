"""Configuration management for omni-extractor."""

from pydantic import Field, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI configuration
    openai_api_key: str = Field(description="OpenAI API key for content extraction")
    openai_base_url: str | None = Field(
        default=None, description="Custom OpenAI API base URL (optional)"
    )
    openai_model: str = Field(
        default="gpt-4o-mini", description="OpenAI model to use for extraction"
    )
    openai_timeout: PositiveFloat = Field(
        default=60.0, description="OpenAI API timeout in seconds"
    )

    # HTTP configuration
    http_timeout: PositiveFloat = Field(
        default=30.0, description="HTTP request timeout in seconds"
    )
    http_connect_timeout: PositiveFloat = Field(
        default=10.0, description="HTTP connection timeout in seconds"
    )
    http_read_timeout: PositiveFloat = Field(
        default=30.0, description="HTTP read timeout in seconds"
    )
    http_write_timeout: PositiveFloat = Field(
        default=5.0, description="HTTP write timeout in seconds"
    )
    http_pool_timeout: PositiveFloat = Field(
        default=10.0, description="HTTP pool timeout in seconds"
    )
    http_max_connections: PositiveInt = Field(
        default=40, description="Maximum HTTP connections"
    )
    http_max_keepalive_connections: PositiveInt = Field(
        default=20, description="Maximum HTTP keepalive connections"
    )
    http_keepalive_expiry: PositiveFloat = Field(
        default=30.0, description="HTTP keepalive expiry in seconds"
    )

    # Content configuration
    html_char_budget: PositiveInt = Field(
        default=20000, description="Maximum characters to extract from HTML"
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
