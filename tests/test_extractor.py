"""Tests for the LLM extraction module."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from omni_extractor.config import Settings
from omni_extractor.extractor import ExtractionException, LLMExtractor
from omni_extractor.models import ExtractionResult


def _make_mock_response(content: str | None, refusal: str | None = None) -> MagicMock:
    """Helper to build a mocked OpenAI chat completion response."""
    message = MagicMock()
    message.content = content
    message.refusal = refusal

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def sample_settings() -> Settings:
    """Return a Settings instance suitable for unit tests."""
    return Settings(
        openai_api_key="test-api-key",
        openai_base_url="https://test.openai.example.com/v1",
        openai_model="gpt-4o-mini",
        max_concurrent_extract=5,
    )


class TestLLMExtractorSuccess:
    """Happy-path extraction scenarios."""

    @patch("omni_extractor.extractor.openai.AsyncOpenAI")
    async def test_extract_success(self, mock_async_openai: MagicMock, sample_settings: Settings) -> None:
        """A valid JSON response from the LLM should yield an ExtractionResult."""
        payload = {
            "url": "https://example.com/article",
            "title": "Test Article",
            "summary": "A short summary.",
            "main_content": "The main content body.",
            "publish_time": "2024-01-01T00:00:00Z",
            "author": "Jane Doe",
            "keywords": ["test", "article"],
            "confidence": 0.95,
            "raw_excerpt": "The main content body.",
        }
        mock_response = _make_mock_response(json.dumps(payload))

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_async_openai.return_value = mock_client

        extractor = LLMExtractor(settings=sample_settings)
        result = await extractor.extract(
            url="https://example.com/article",
            raw_content="The main content body.",
        )

        assert isinstance(result, ExtractionResult)
        assert result.url == "https://example.com/article"
        assert result.title == "Test Article"
        assert result.confidence == 0.95

        # Verify the call was made with forced JSON output
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.1
        assert call_args.kwargs["response_format"] == {"type": "json_object"}
        assert call_args.kwargs["model"] == "gpt-4o-mini"

    @patch("omni_extractor.extractor.openai.AsyncOpenAI")
    async def test_extract_injects_url_when_missing(
        self, mock_async_openai: MagicMock, sample_settings: Settings
    ) -> None:
        """If the LLM omits the 'url' key, the extractor should inject it."""
        payload = {
            "title": "No URL Provided",
            "summary": "Summary here.",
            "main_content": "Content here.",
            "confidence": 0.8,
            "raw_excerpt": "Content here.",
        }
        mock_response = _make_mock_response(json.dumps(payload))

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_async_openai.return_value = mock_client

        extractor = LLMExtractor(settings=sample_settings)
        result = await extractor.extract(
            url="https://example.com/auto-inject",
            raw_content="Content here.",
        )

        assert result.url == "https://example.com/auto-inject"


class TestLLMExtractorFailures:
    """Failure scenarios for LLM extraction."""

    @patch("omni_extractor.extractor.openai.AsyncOpenAI")
    async def test_extract_validation_failure(
        self, mock_async_openai: MagicMock, sample_settings: Settings
    ) -> None:
        """A JSON object that does not match ExtractionResult should raise ExtractionException."""
        # Missing required fields like 'title', 'main_content', etc.
        bad_payload = {"url": "https://example.com", "confidence": 2.0}
        mock_response = _make_mock_response(json.dumps(bad_payload))

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_async_openai.return_value = mock_client

        extractor = LLMExtractor(settings=sample_settings)
        with pytest.raises(ExtractionException) as exc_info:
            await extractor.extract(
                url="https://example.com",
                raw_content="some content",
            )

        assert "validation" in str(exc_info.value).lower() or "LLM output failed validation" in str(exc_info.value)

    @patch("omni_extractor.extractor.openai.AsyncOpenAI")
    async def test_extract_model_refusal(
        self, mock_async_openai: MagicMock, sample_settings: Settings
    ) -> None:
        """A model refusal should be raised as ExtractionException."""
        mock_response = _make_mock_response(content=None, refusal="Content policy violation")

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_async_openai.return_value = mock_client

        extractor = LLMExtractor(settings=sample_settings)
        with pytest.raises(ExtractionException) as exc_info:
            await extractor.extract(
                url="https://example.com",
                raw_content="forbidden content",
            )

        assert "refused" in str(exc_info.value).lower()
        assert exc_info.value.url == "https://example.com"

    @patch("omni_extractor.extractor.openai.AsyncOpenAI")
    async def test_extract_timeout(
        self, mock_async_openai: MagicMock, sample_settings: Settings
    ) -> None:
        """An OpenAI timeout should be raised as ExtractionException."""
        import openai

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=openai.APITimeoutError("Request timed out")
        )
        mock_async_openai.return_value = mock_client

        extractor = LLMExtractor(settings=sample_settings)
        with pytest.raises(ExtractionException) as exc_info:
            await extractor.extract(
                url="https://example.com",
                raw_content="some content",
            )

        assert "timed out" in str(exc_info.value).lower()
        assert exc_info.value.url == "https://example.com"
