"""Tests for the extraction pipeline."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni_extractor.config import Settings
from omni_extractor.extractor import ExtractionException
from omni_extractor.fetcher import FetchError
from omni_extractor.models import BatchResult, ExtractionError, ExtractionResult
from omni_extractor.pipeline import ExtractionPipeline


@pytest.fixture
def test_settings() -> Settings:
    """Return a Settings instance suitable for unit tests."""
    return Settings(openai_api_key="test-key")


@pytest.fixture
def sample_extraction_result() -> ExtractionResult:
    """Return a sample successful extraction result."""
    return ExtractionResult(
        url="https://example.com",
        title="Test Title",
        summary="Test summary",
        main_content="Test content",
        publish_time=None,
        author=None,
        keywords=["test"],
        confidence=0.95,
        raw_excerpt="Test content",
    )


class TestExtractionPipelineSingle:
    """Single-URL extraction scenarios."""

    @pytest.mark.asyncio
    async def test_extract_single_success(
        self,
        test_settings: Settings,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        """A successful pipeline run should return an ExtractionResult."""
        pipeline = ExtractionPipeline(settings=test_settings)
        pipeline.fetcher = AsyncMock()
        pipeline.fetcher.fetch = AsyncMock(
            return_value=MagicMock(html="<html>test</html>")
        )
        pipeline.cleaner = MagicMock()
        pipeline.cleaner.clean_html = MagicMock(
            return_value=("cleaned text", "Test Title")
        )
        pipeline.extractor = AsyncMock()
        pipeline.extractor.extract = AsyncMock(return_value=sample_extraction_result)
        pipeline._stdout_console = MagicMock()

        result = await pipeline.extract_single("https://example.com")

        assert isinstance(result, ExtractionResult)
        assert result.url == "https://example.com"
        pipeline._stdout_console.print.assert_called_once()
        printed = pipeline._stdout_console.print.call_args[0][0]
        assert "Test Title" in printed
        assert "https://example.com" in printed

    @pytest.mark.asyncio
    async def test_extract_single_no_print(
        self,
        test_settings: Settings,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        """`print_result=False` should skip stdout output."""
        pipeline = ExtractionPipeline(settings=test_settings)
        pipeline.fetcher = AsyncMock()
        pipeline.fetcher.fetch = AsyncMock(
            return_value=MagicMock(html="<html>test</html>")
        )
        pipeline.cleaner = MagicMock()
        pipeline.cleaner.clean_html = MagicMock(
            return_value=("cleaned text", "Test Title")
        )
        pipeline.extractor = AsyncMock()
        pipeline.extractor.extract = AsyncMock(return_value=sample_extraction_result)
        pipeline._stdout_console = MagicMock()

        result = await pipeline.extract_single(
            "https://example.com", print_result=False
        )

        assert isinstance(result, ExtractionResult)
        pipeline._stdout_console.print.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_single_fetch_failure(self, test_settings: Settings) -> None:
        """A fetch failure should return an ExtractionError, not raise."""
        pipeline = ExtractionPipeline(settings=test_settings)
        error = FetchError(
            "https://example.com",
            "TimeoutException",
            "Request timed out",
        )
        pipeline.fetcher = AsyncMock()
        pipeline.fetcher.fetch = AsyncMock(side_effect=error)
        pipeline.cleaner = MagicMock()
        pipeline.extractor = AsyncMock()

        result = await pipeline.extract_single(
            "https://example.com", print_result=False
        )

        assert isinstance(result, ExtractionError)
        assert result.error_type == "TimeoutException"
        assert "timed out" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_single_clean_failure(self, test_settings: Settings) -> None:
        """An HTML cleaning failure should return an ExtractionError."""
        pipeline = ExtractionPipeline(settings=test_settings)
        pipeline.fetcher = AsyncMock()
        pipeline.fetcher.fetch = AsyncMock(
            return_value=MagicMock(html="<html>test</html>")
        )
        pipeline.cleaner = MagicMock()
        pipeline.cleaner.clean_html = MagicMock(
            side_effect=ValueError("Malformed HTML")
        )
        pipeline.extractor = AsyncMock()

        result = await pipeline.extract_single(
            "https://example.com", print_result=False
        )

        assert isinstance(result, ExtractionError)
        assert result.error_type == "ValueError"
        assert "Malformed HTML" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_single_extract_failure(
        self, test_settings: Settings
    ) -> None:
        """An LLM extraction failure should return an ExtractionError."""
        pipeline = ExtractionPipeline(settings=test_settings)
        pipeline.fetcher = AsyncMock()
        pipeline.fetcher.fetch = AsyncMock(
            return_value=MagicMock(html="<html>test</html>")
        )
        pipeline.cleaner = MagicMock()
        pipeline.cleaner.clean_html = MagicMock(
            return_value=("cleaned text", "Test Title")
        )
        pipeline.extractor = AsyncMock()
        pipeline.extractor.extract = AsyncMock(
            side_effect=ExtractionException("OpenAI failed", url="https://example.com")
        )

        result = await pipeline.extract_single(
            "https://example.com", print_result=False
        )

        assert isinstance(result, ExtractionError)
        assert result.error_type == "ExtractionException"
        assert "OpenAI failed" in result.error_message


class TestExtractionPipelineBatch:
    """Batch extraction scenarios."""

    @pytest.mark.asyncio
    async def test_extract_batch_partial_failures(
        self,
        test_settings: Settings,
        sample_extraction_result: ExtractionResult,
        tmp_path: Path,
    ) -> None:
        """A batch with mixed successes and failures should track both."""
        pipeline = ExtractionPipeline(settings=test_settings, output_dir=tmp_path)
        pipeline.fetcher = AsyncMock()
        pipeline.cleaner = MagicMock()
        pipeline.extractor = AsyncMock()

        def _mock_fetch(url: str) -> MagicMock:
            if "fail-fetch" in url:
                raise FetchError(url, "FetchError", "Network unreachable")
            resp = MagicMock()
            resp.html = f"<html>{url}</html>"
            return resp

        def _mock_clean(html: str) -> tuple[str, str]:
            if "fail-clean" in html:
                raise ValueError("Parser blew up")
            return ("cleaned text", "Title")

        def _mock_extract(url: str, content: str) -> ExtractionResult:
            if "fail-extract" in url:
                raise ExtractionException("Model error", url=url)
            return sample_extraction_result.model_copy(update={"url": url})

        pipeline.fetcher.fetch = AsyncMock(side_effect=_mock_fetch)
        pipeline.cleaner.clean_html = MagicMock(side_effect=_mock_clean)
        pipeline.extractor.extract = AsyncMock(side_effect=_mock_extract)

        urls = [
            "https://success1.com",
            "https://fail-fetch.com",
            "https://fail-clean.com",
            "https://fail-extract.com",
            "https://success2.com",
        ]

        result = await pipeline.extract_batch(urls)

        assert isinstance(result, BatchResult)
        assert result.total_processed == 5
        assert result.total_failed == 3
        assert len(result.successes) == 2
        assert len(result.failures) == 3

        # Verify JSONL output files were created
        results_files = list(tmp_path.glob("results-*.jsonl"))
        assert len(results_files) == 1
        with open(results_files[0], encoding="utf-8") as f:
            success_lines = f.readlines()
        assert len(success_lines) == 2
        for line in success_lines:
            parsed = json.loads(line)
            assert parsed["url"] in {"https://success1.com", "https://success2.com"}

        failures_files = list(tmp_path.glob("failures-*.jsonl"))
        assert len(failures_files) == 1
        with open(failures_files[0], encoding="utf-8") as f:
            failure_lines = f.readlines()
        assert len(failure_lines) == 3
        for line in failure_lines:
            parsed = json.loads(line)
            assert "fail" in parsed["url"]

    @pytest.mark.asyncio
    async def test_extract_batch_empty_list(
        self,
        test_settings: Settings,
        tmp_path: Path,
    ) -> None:
        """An empty URL list should yield an empty BatchResult."""
        pipeline = ExtractionPipeline(settings=test_settings, output_dir=tmp_path)
        pipeline.fetcher = AsyncMock()
        pipeline.cleaner = MagicMock()
        pipeline.extractor = AsyncMock()

        result = await pipeline.extract_batch([])

        assert isinstance(result, BatchResult)
        assert result.total_processed == 0
        assert result.total_failed == 0
        assert len(result.successes) == 0
        assert len(result.failures) == 0

        # No files should be written for an empty batch
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.asyncio
    async def test_extract_batch_creates_output_dir(
        self,
        test_settings: Settings,
        sample_extraction_result: ExtractionResult,
        tmp_path: Path,
    ) -> None:
        """The pipeline should create the output directory if it doesn't exist."""
        nested_dir = tmp_path / "nested" / "outputs"
        pipeline = ExtractionPipeline(settings=test_settings, output_dir=nested_dir)
        pipeline.fetcher = AsyncMock()
        pipeline.fetcher.fetch = AsyncMock(
            return_value=MagicMock(html="<html>test</html>")
        )
        pipeline.cleaner = MagicMock()
        pipeline.cleaner.clean_html = MagicMock(
            return_value=("cleaned text", "Title")
        )
        pipeline.extractor = AsyncMock()
        pipeline.extractor.extract = AsyncMock(return_value=sample_extraction_result)

        await pipeline.extract_batch(["https://example.com"])

        assert nested_dir.exists()
        assert len(list(nested_dir.glob("results-*.jsonl"))) == 1


class TestExtractionPipelineContextManager:
    """Async context manager lifecycle."""

    @pytest.mark.asyncio
    async def test_context_manager_encloses_resources(
        self, test_settings: Settings
    ) -> None:
        """Entering/exiting the pipeline should init and close resources."""
        pipeline = ExtractionPipeline(settings=test_settings)
        pipeline.fetcher = MagicMock()
        pipeline.fetcher.__aenter__ = AsyncMock(return_value=pipeline.fetcher)
        pipeline.fetcher.__aexit__ = AsyncMock(return_value=False)
        pipeline.extractor = MagicMock()
        pipeline.extractor.client = MagicMock()
        pipeline.extractor.client.close = AsyncMock()

        async with pipeline as p:
            assert p is pipeline

        pipeline.fetcher.__aenter__.assert_awaited_once()
        pipeline.fetcher.__aexit__.assert_awaited_once()
        pipeline.extractor.client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_manager_exception_cleanup(
        self, test_settings: Settings
    ) -> None:
        """Resources should still be closed when an exception is raised."""
        pipeline = ExtractionPipeline(settings=test_settings)
        pipeline.fetcher = MagicMock()
        pipeline.fetcher.__aenter__ = AsyncMock(return_value=pipeline.fetcher)
        pipeline.fetcher.__aexit__ = AsyncMock(return_value=False)
        pipeline.extractor = MagicMock()
        pipeline.extractor.client = MagicMock()
        pipeline.extractor.client.close = AsyncMock()

        with pytest.raises(RuntimeError, match="boom"):
            async with pipeline:
                raise RuntimeError("boom")

        pipeline.fetcher.__aexit__.assert_awaited_once()
        pipeline.extractor.client.close.assert_awaited_once()


class TestExtractionPipelineProgress:
    """Progress tracking behaviour."""

    @pytest.mark.asyncio
    async def test_batch_advances_progress(
        self,
        test_settings: Settings,
        sample_extraction_result: ExtractionResult,
        tmp_path: Path,
    ) -> None:
        """The rich progress bar should advance once per URL."""
        pipeline = ExtractionPipeline(settings=test_settings, output_dir=tmp_path)
        pipeline.fetcher = AsyncMock()
        pipeline.fetcher.fetch = AsyncMock(
            return_value=MagicMock(html="<html>test</html>")
        )
        pipeline.cleaner = MagicMock()
        pipeline.cleaner.clean_html = MagicMock(
            return_value=("cleaned text", "Title")
        )
        pipeline.extractor = AsyncMock()
        pipeline.extractor.extract = AsyncMock(return_value=sample_extraction_result)

        mock_progress = MagicMock()
        mock_task = MagicMock()
        mock_progress.add_task = MagicMock(return_value=mock_task)
        mock_progress.advance = MagicMock()

        with patch(
            "omni_extractor.pipeline.Progress", return_value=mock_progress
        ):
            # Make the context manager work
            mock_progress.__enter__ = MagicMock(return_value=mock_progress)
            mock_progress.__exit__ = MagicMock(return_value=False)

            await pipeline.extract_batch(["https://a.com", "https://b.com"])

        mock_progress.add_task.assert_called_once_with(
            "Extracting URLs...", total=2
        )
        assert mock_progress.advance.call_count == 2
