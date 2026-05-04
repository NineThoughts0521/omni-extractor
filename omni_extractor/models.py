"""Data models for omni-extractor."""

from datetime import datetime

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """Result of a successful content extraction."""

    url: str = Field(description="The URL that was extracted")
    title: str = Field(description="The title of the content")
    summary: str = Field(description="A brief summary of the main content")
    main_content: str = Field(description="The main extracted content body")
    publish_time: str | None = Field(
        None, description="Publication time if available"
    )
    author: str | None = Field(None, description="Author name if available")
    keywords: list[str] = Field(
        default_factory=list, description="List of extracted keywords"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score of the extraction (0.0-1.0)"
    )
    raw_excerpt: str = Field(description="Raw excerpt used for extraction")

    model_config = {"extra": "forbid"}


class ExtractionError(BaseModel):
    """Result of a failed content extraction."""

    url: str = Field(description="The URL that failed to extract")
    error_type: str = Field(description="Type of error that occurred")
    error_message: str = Field(description="Detailed error message")
    timestamp: datetime = Field(description="When the error occurred")

    model_config = {"extra": "forbid"}


class BatchResult(BaseModel):
    """Result of a batch extraction operation."""

    successes: list[ExtractionResult] = Field(
        description="List of successful extractions"
    )
    failures: list[ExtractionError] = Field(description="List of failed extractions")
    total_processed: int = Field(description="Total number of URLs processed")
    total_failed: int = Field(description="Total number of failed extractions")
    started_at: datetime = Field(description="When the batch operation started")
    completed_at: datetime = Field(description="When the batch operation completed")

    model_config = {"extra": "forbid"}


class FetchResult(BaseModel):
    """Result of fetching raw content from a URL."""

    url: str = Field(description="The URL that was fetched")
    html: str = Field(description="The raw HTML content fetched")
    status_code: int = Field(description="HTTP status code of the response")
    content_type: str = Field(description="Content type of the response")
    fetch_time: float = Field(description="Time taken to fetch in seconds")

    model_config = {"extra": "forbid"}


__all__ = [
    "ExtractionResult",
    "ExtractionError",
    "BatchResult",
    "FetchResult",
]
