"""Tests for the HTTP fetcher module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from omni_extractor.config import Settings
from omni_extractor.fetcher import FetchError, Fetcher, USER_AGENTS
from omni_extractor.models import FetchResult


@pytest.fixture
def test_settings() -> Settings:
    """Return a Settings instance suitable for unit tests."""
    return Settings(openai_api_key="test-key")


class TestFetcherBasics:
    """Basic sanity checks for the fetcher."""

    def test_user_agent_list_not_empty(self) -> None:
        """The User-Agent list must contain modern browser strings."""
        assert len(USER_AGENTS) > 0
        assert all("Mozilla" in ua for ua in USER_AGENTS)

    @pytest.mark.asyncio
    async def test_fetcher_context_manager(self, test_settings: Settings) -> None:
        """Fetcher should initialise and close its client via async context manager."""
        fetcher = Fetcher(settings=test_settings)
        assert fetcher._client is None

        async with fetcher as f:
            assert f._client is not None

        assert fetcher._client is None

    @pytest.mark.asyncio
    async def test_fetcher_explicit_close(self, test_settings: Settings) -> None:
        """Fetcher.close should clean up the shared client."""
        fetcher = Fetcher(settings=test_settings)
        await fetcher._init_client()
        assert fetcher._client is not None

        await fetcher.close()
        assert fetcher._client is None


class TestFetcherSuccess:
    """Happy-path fetch scenarios."""

    @pytest.fixture
    async def fetcher(self, test_settings: Settings) -> Fetcher:
        """Yield a fresh Fetcher and ensure cleanup after the test."""
        f = Fetcher(settings=test_settings)
        yield f
        await f.close()

    @pytest.fixture
    def mock_html_response(self) -> MagicMock:
        """A mock HTTP response that looks like a valid HTML page."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "text/html; charset=utf-8"}
        response.text = "<html><body>Hello World</body></html>"
        response.url = "https://example.com"
        return response

    @pytest.mark.asyncio
    async def test_successful_fetch(self, fetcher: Fetcher, mock_html_response: MagicMock) -> None:
        """A successful request should return a populated FetchResult."""
        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(return_value=mock_html_response)

        result = await fetcher.fetch("https://example.com")

        assert isinstance(result, FetchResult)
        assert result.url == "https://example.com"
        assert result.html == "<html><body>Hello World</body></html>"
        assert result.status_code == 200
        assert "text/html" in result.content_type
        assert result.fetch_time >= 0.0
        fetcher._client.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_user_agent_rotation(self, fetcher: Fetcher, mock_html_response: MagicMock) -> None:
        """Each request should use a User-Agent chosen from the curated list."""
        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(return_value=mock_html_response)

        await fetcher.fetch("https://example.com")

        call_args = fetcher._client.get.call_args
        sent_headers = call_args.kwargs.get("headers", call_args[1] if len(call_args) > 1 else {})
        assert sent_headers["User-Agent"] in USER_AGENTS


class TestFetcherRetry:
    """Retry behaviour for transient failures."""

    @pytest.fixture
    async def fetcher(self, test_settings: Settings) -> Fetcher:
        """Yield a fresh Fetcher and ensure cleanup after the test."""
        f = Fetcher(settings=test_settings)
        yield f
        await f.close()

    @pytest.fixture
    def ok_response(self) -> MagicMock:
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "text/html; charset=utf-8"}
        response.text = "<html><body>OK</body></html>"
        response.url = "https://example.com"
        return response

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, fetcher: Fetcher, ok_response: MagicMock) -> None:
        """A TimeoutException on the first attempt should be retried."""
        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(
            side_effect=[
                httpx.TimeoutException("Request timed out"),
                ok_response,
            ]
        )

        result = await fetcher.fetch("https://example.com")

        assert isinstance(result, FetchResult)
        assert result.status_code == 200
        assert fetcher._client.get.await_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self, fetcher: Fetcher, ok_response: MagicMock) -> None:
        """A NetworkError on the first attempt should be retried."""
        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(
            side_effect=[
                httpx.NetworkError("Connection reset"),
                ok_response,
            ]
        )

        result = await fetcher.fetch("https://example.com")

        assert isinstance(result, FetchResult)
        assert result.status_code == 200
        assert fetcher._client.get.await_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_5xx_status_code(self, fetcher: Fetcher, ok_response: MagicMock) -> None:
        """A 503 response on the first attempt should trigger a retry."""
        error_response = MagicMock()
        error_response.status_code = 503
        error_response.headers = {"content-type": "text/html"}

        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(
            side_effect=[
                error_response,
                ok_response,
            ]
        )

        result = await fetcher.fetch("https://example.com")

        assert isinstance(result, FetchResult)
        assert result.status_code == 200
        assert fetcher._client.get.await_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_429_status_code(self, fetcher: Fetcher, ok_response: MagicMock) -> None:
        """A 429 (Too Many Requests) response should be retried."""
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.headers = {"content-type": "text/html"}

        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(
            side_effect=[
                error_response,
                ok_response,
            ]
        )

        result = await fetcher.fetch("https://example.com")

        assert isinstance(result, FetchResult)
        assert result.status_code == 200
        assert fetcher._client.get.await_count == 2

    @pytest.mark.asyncio
    async def test_exhausted_retries_raise_fetch_error(self, fetcher: Fetcher) -> None:
        """After all retries are exhausted a FetchError should be raised."""
        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(
            side_effect=httpx.TimeoutException("Always times out")
        )

        with pytest.raises(FetchError) as exc_info:
            await fetcher.fetch("https://example.com")

        assert exc_info.value.extraction_error.error_type == "TimeoutException"
        assert fetcher._client.get.await_count == fetcher.settings.max_retries + 1


class TestFetcherValidation:
    """Response validation rules."""

    @pytest.fixture
    async def fetcher(self, test_settings: Settings) -> Fetcher:
        """Yield a fresh Fetcher and ensure cleanup after the test."""
        f = Fetcher(settings=test_settings)
        yield f
        await f.close()

    @pytest.mark.asyncio
    async def test_non_html_rejection(self, fetcher: Fetcher) -> None:
        """Responses with a non-HTML content-type should be rejected."""
        json_response = MagicMock()
        json_response.status_code = 200
        json_response.headers = {"content-type": "application/json"}
        json_response.url = "https://example.com/api"

        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(return_value=json_response)

        with pytest.raises(FetchError) as exc_info:
            await fetcher.fetch("https://example.com/api")

        assert exc_info.value.extraction_error.error_type == "NonHTMLResponse"
        assert "application/json" in exc_info.value.extraction_error.error_message

    @pytest.mark.asyncio
    async def test_client_error_not_retried(self, fetcher: Fetcher) -> None:
        """Non-retryable client errors should fail immediately."""
        not_found_response = MagicMock()
        not_found_response.status_code = 404
        not_found_response.url = "https://example.com/missing"
        not_found_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=not_found_response,
        )

        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(return_value=not_found_response)

        with pytest.raises(FetchError) as exc_info:
            await fetcher.fetch("https://example.com/missing")

        assert "HTTPStatusError_404" in exc_info.value.extraction_error.error_type
        assert fetcher._client.get.await_count == 1


class TestFetcherConcurrency:
    """Semaphore-based concurrency limits."""

    @pytest.fixture
    async def fetcher(self, test_settings: Settings) -> Fetcher:
        """Yield a fresh Fetcher and ensure cleanup after the test."""
        f = Fetcher(settings=test_settings)
        yield f
        await f.close()

    @pytest.mark.asyncio
    async def test_concurrent_fetch_limiting(self, fetcher: Fetcher) -> None:
        """With a semaphore of 2, three 0.1 s requests should take >= 0.2 s."""
        fetcher._semaphore = asyncio.Semaphore(2)
        call_count = 0

        async def slow_get(url: str, **kwargs) -> MagicMock:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            response = MagicMock()
            response.status_code = 200
            response.headers = {"content-type": "text/html; charset=utf-8"}
            response.text = f"<html>{url}</html>"
            response.url = url
            return response

        fetcher._client = AsyncMock()
        fetcher._client.get = AsyncMock(side_effect=slow_get)

        urls = [
            "https://site1.com",
            "https://site2.com",
            "https://site3.com",
        ]

        start = asyncio.get_event_loop().time()
        results = await asyncio.gather(*[fetcher.fetch(url) for url in urls])
        elapsed = asyncio.get_event_loop().time() - start

        assert len(results) == 3
        assert all(isinstance(r, FetchResult) for r in results)
        # Semaphore of 2 means at most 2 concurrent; 3 × 0.1 s work needs >= 0.2 s
        assert elapsed >= 0.18
