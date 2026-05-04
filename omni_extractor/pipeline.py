"""Pipeline orchestration for omni-extractor."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from loguru import logger
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from omni_extractor.config import Settings
from omni_extractor.extractor import ExtractionException, LLMExtractor
from omni_extractor.fetcher import FetchError, Fetcher
from omni_extractor.html_cleaner import HTMLCleaner
from omni_extractor.models import BatchResult, ExtractionError, ExtractionResult


class ExtractionPipeline:
    """Orchestrate fetch → clean → extract for one or many URLs.

    The pipeline owns a :class:`Fetcher`, :class:`HTMLCleaner`, and
    :class:`LLMExtractor`.  It should be used as an async context manager so
    that underlying HTTP and OpenAI clients are closed automatically.

    Example:
        >>> async with ExtractionPipeline() as pipeline:
        ...     result = await pipeline.extract_single("https://example.com")
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.output_dir = output_dir or Path("outputs")
        self.fetcher = Fetcher(settings=self.settings)
        self.cleaner = HTMLCleaner(char_budget=20000)
        self.extractor = LLMExtractor(settings=self.settings)
        self._stderr_console = Console(stderr=True)
        self._stdout_console = Console(file=sys.stdout)

    async def __aenter__(self) -> "ExtractionPipeline":
        await self.fetcher.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> bool:
        await self.fetcher.__aexit__(exc_type, exc_val, exc_tb)
        await self.extractor.client.close()
        return False

    async def _process_url(
        self, url: str
    ) -> Union[ExtractionResult, ExtractionError]:
        """Fetch, clean, and extract a single URL.

        Errors at any stage are caught and returned as :class:`ExtractionError`
        so that a single failing URL never aborts a batch.
        """
        # --- Fetch --------------------------------------------------------
        try:
            fetch_result = await self.fetcher.fetch(url)
        except FetchError as exc:
            logger.warning("Fetch failed for {}: {}", url, exc)
            return exc.extraction_error
        except Exception as exc:
            logger.warning("Unexpected fetch error for {}: {}", url, exc)
            return ExtractionError(
                url=url,
                error_type=type(exc).__name__,
                error_message=str(exc),
                timestamp=datetime.now(),
            )

        # --- Clean --------------------------------------------------------
        try:
            cleaned_text, _title = self.cleaner.clean_html(fetch_result.html)
        except Exception as exc:
            logger.warning("HTML cleaning failed for {}: {}", url, exc)
            return ExtractionError(
                url=url,
                error_type=type(exc).__name__,
                error_message=str(exc),
                timestamp=datetime.now(),
            )

        # --- Extract ------------------------------------------------------
        try:
            result = await self.extractor.extract(url, cleaned_text)
        except ExtractionException as exc:
            logger.warning("Extraction failed for {}: {}", url, exc)
            return ExtractionError(
                url=url,
                error_type="ExtractionException",
                error_message=str(exc),
                timestamp=datetime.now(),
            )
        except Exception as exc:
            logger.warning("Unexpected extraction error for {}: {}", url, exc)
            return ExtractionError(
                url=url,
                error_type=type(exc).__name__,
                error_message=str(exc),
                timestamp=datetime.now(),
            )

        return result

    async def extract_single(
        self,
        url: str,
        print_result: bool = True,
    ) -> Union[ExtractionResult, ExtractionError]:
        """Extract content from a single URL.

        On success (and when *print_result* is ``True``) the result is
        serialised as pretty JSON and printed to ``stdout``.

        Args:
            url: The target URL.
            print_result: Whether to print the JSON result to stdout.

        Returns:
            The extraction result, or an :class:`ExtractionError` on failure.
        """
        result = await self._process_url(url)

        if isinstance(result, ExtractionResult) and print_result:
            json_str = json.dumps(result.model_dump(), indent=2, default=str)
            self._stdout_console.print(json_str)

        return result

    async def extract_batch(self, urls: List[str]) -> BatchResult:
        """Extract content from multiple URLs with rich progress tracking.

        Results are written to timestamped JSONL files under *output_dir*:

        * ``outputs/results-<timestamp>.jsonl`` – successful extractions
        * ``outputs/failures-<timestamp>.jsonl`` – failed extractions

        Args:
            urls: List of target URLs.

        Returns:
            A :class:`BatchResult` summarising the run.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        successes_path = self.output_dir / f"results-{timestamp}.jsonl"
        failures_path = self.output_dir / f"failures-{timestamp}.jsonl"

        started_at = datetime.now()
        successes: List[ExtractionResult] = []
        failures: List[ExtractionError] = []

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self._stderr_console,
        )

        with progress:
            task = progress.add_task("Extracting URLs...", total=len(urls))

            # Avoid unbounded gather – cap concurrent URL processing.
            semaphore = asyncio.Semaphore(self.settings.max_concurrent_fetch)

            async def _process_with_progress(url: str) -> None:
                async with semaphore:
                    result = await self._process_url(url)
                    if isinstance(result, ExtractionResult):
                        successes.append(result)
                        self._append_jsonl(successes_path, result)
                    else:
                        failures.append(result)
                        self._append_jsonl(failures_path, result)
                    progress.advance(task)

            await asyncio.gather(*[_process_with_progress(url) for url in urls])

        completed_at = datetime.now()

        logger.info(
            "Batch complete: {} succeeded, {} failed out of {}",
            len(successes),
            len(failures),
            len(urls),
        )

        return BatchResult(
            successes=successes,
            failures=failures,
            total_processed=len(urls),
            total_failed=len(failures),
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _append_jsonl(
        path: Path, obj: Union[ExtractionResult, ExtractionError]
    ) -> None:
        """Append a single JSON object to a JSONL file."""
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj.model_dump(), default=str) + "\n")


__all__ = ["ExtractionPipeline"]
