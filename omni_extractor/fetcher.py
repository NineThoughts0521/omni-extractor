"""HTTP fetching layer for omni-extractor."""

import asyncio
import random
import time
from datetime import datetime
from typing import Optional

import httpx

from omni_extractor.config import Settings
from omni_extractor.models import ExtractionError, FetchResult


# Curated list of modern desktop browser User-Agent strings
USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4.1 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 "
        "Edg/124.0.2478.67"
    ),
]


class FetchError(Exception):
    """Exception raised when a fetch operation fails.

    Contains an :class:`ExtractionError` model for structured error reporting.
    """

    def __init__(self, url: str, error_type: str, error_message: str) -> None:
        self.extraction_error = ExtractionError(
            url=url,
            error_type=error_type,
            error_message=error_message,
            timestamp=datetime.now(),
        )
        super().__init__(f"{error_type}: {error_message}")


class Fetcher:
    """Async HTTP fetcher with retry logic, User-Agent rotation, and concurrency control.

    Uses a single shared :class:`httpx.AsyncClient` for all requests. Concurrency is
    limited via an :class:`asyncio.Semaphore`. Failed requests are retried with
    exponential backoff and jitter for retryable errors and status codes.
    """

    RETRYABLE_STATUS_CODES: set[int] = {429, 500, 502, 503, 504}

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_fetch)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "Fetcher":
        await self._init_client()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> bool:
        await self.close()
        return False

    async def _init_client(self) -> None:
        """Initialise the shared :class:`httpx.AsyncClient` with tuned limits."""
        if self._client is not None:
            return

        limits = httpx.Limits(
            max_connections=40,
            max_keepalive_connections=20,
            keepalive_expiry=30.0,
        )

        timeout = httpx.Timeout(
            connect=10.0,
            read=30.0,
            write=5.0,
            pool=10.0,
        )

        self._client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
        )

    async def close(self) -> None:
        """Close the shared :class:`httpx.AsyncClient`."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_random_user_agent(self) -> str:
        """Return a randomly chosen User-Agent string."""
        return random.choice(USER_AGENTS)

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate the delay for the given retry attempt.

        Uses exponential backoff with random jitter:
        ``base_delay * (2 ** attempt) + random.uniform(0, 1)``
        """
        return self.settings.retry_base_delay * (2**attempt) + random.uniform(0, 1)

    async def _fetch_with_retry(self, url: str) -> httpx.Response:
        """Perform a GET request with exponential-backoff retries.

        Retries on :class:`httpx.TimeoutException`, :class:`httpx.NetworkError`,
        and HTTP status codes 429 / 500 / 502 / 503 / 504.

        Args:
            url: The target URL.

        Returns:
            The HTTP response.

        Raises:
            The last encountered exception if all retries are exhausted.
        """
        max_retries = self.settings.max_retries
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                headers = {
                    "User-Agent": self._get_random_user_agent(),
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                }

                response = await self._client.get(url, headers=headers)

                # Retry on specific status codes before calling raise_for_status
                if response.status_code in self.RETRYABLE_STATUS_CODES:
                    if attempt < max_retries:
                        await asyncio.sleep(self._calculate_backoff(attempt))
                        continue
                    # On the final attempt let raise_for_status() fail properly

                response.raise_for_status()
                return response

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < max_retries:
                    await asyncio.sleep(self._calculate_backoff(attempt))
                else:
                    break

        if last_error is not None:
            raise last_error

        # Defensive fallback – should never be reached
        raise FetchError(
            url=url,
            error_type="FetchFailed",
            error_message="All retry attempts exhausted without a specific error",
        )

    async def fetch(self, url: str) -> FetchResult:
        """Fetch HTML content from *url* under concurrency control.

        Args:
            url: The URL to fetch.

        Returns:
            A :class:`FetchResult` containing the HTML and metadata.

        Raises:
            FetchError: If the request fails after all retries or the response is
                not valid HTML.
        """
        if self._client is None:
            await self._init_client()

        async with self._semaphore:
            start_time = time.monotonic()

            try:
                response = await self._fetch_with_retry(url)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise FetchError(
                    url=url,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                ) from exc
            except httpx.HTTPStatusError as exc:
                raise FetchError(
                    url=url,
                    error_type=f"HTTPStatusError_{exc.response.status_code}",
                    error_message=str(exc),
                ) from exc
            except FetchError:
                raise
            except Exception as exc:
                raise FetchError(
                    url=url,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                ) from exc

            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                raise FetchError(
                    url=url,
                    error_type="NonHTMLResponse",
                    error_message=f"Expected HTML response, got content-type: {content_type}",
                )

            fetch_time = time.monotonic() - start_time

            return FetchResult(
                url=str(response.url),
                html=response.text,
                status_code=response.status_code,
                content_type=content_type,
                fetch_time=fetch_time,
            )
