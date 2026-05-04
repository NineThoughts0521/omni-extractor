"""Tests for the omni-extractor CLI."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni_extractor.cli import _create_parser, _validate_url, main
from omni_extractor.models import ExtractionError, ExtractionResult


class TestCliArgumentParsing:
    """Argument parsing behaviour."""

    def test_help_top_level(self) -> None:
        """``--help`` at the top level should print usage and exit."""
        parser = _create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_help_extract_command(self) -> None:
        """``extract --help`` should print command-specific help."""
        parser = _create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["extract", "--help"])
        assert exc_info.value.code == 0

    def test_help_extract_batch_command(self) -> None:
        """``extract-batch --help`` should print command-specific help."""
        parser = _create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["extract-batch", "--help"])
        assert exc_info.value.code == 0

    def test_extract_url_required(self) -> None:
        """``extract`` without ``--url`` should fail."""
        parser = _create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["extract"])
        assert exc_info.value.code == 2

    def test_extract_batch_input_required(self) -> None:
        """``extract-batch`` without ``--input`` should fail."""
        parser = _create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["extract-batch"])
        assert exc_info.value.code == 2

    def test_extract_url_parsing(self) -> None:
        """``extract --url`` should capture the URL."""
        parser = _create_parser()
        args = parser.parse_args(["extract", "--url", "https://example.com"])
        assert args.command == "extract"
        assert args.url == "https://example.com"
        assert args.output is None
        assert args.config is None

    def test_extract_with_output(self) -> None:
        """``extract --url --output`` should capture both arguments."""
        parser = _create_parser()
        args = parser.parse_args(
            [
                "extract",
                "--url",
                "https://example.com",
                "--output",
                "result.json",
            ]
        )
        assert args.output == "result.json"

    def test_extract_with_config(self) -> None:
        """Top-level ``--config`` should be recognised."""
        parser = _create_parser()
        args = parser.parse_args(
            [
                "--config",
                "/path/to/.env",
                "extract",
                "--url",
                "https://example.com",
            ]
        )
        assert args.config == "/path/to/.env"

    def test_extract_batch_input_parsing(self) -> None:
        """``extract-batch --input`` should capture the input file."""
        parser = _create_parser()
        args = parser.parse_args(["extract-batch", "--input", "urls.txt"])
        assert args.command == "extract-batch"
        assert args.input == "urls.txt"
        assert args.output_dir == "outputs"
        assert args.config is None

    def test_extract_batch_with_output_dir(self) -> None:
        """``extract-batch --output-dir`` should override the default."""
        parser = _create_parser()
        args = parser.parse_args(
            [
                "extract-batch",
                "--input",
                "urls.txt",
                "--output-dir",
                "custom_outputs",
            ]
        )
        assert args.output_dir == "custom_outputs"


class TestCliUrlValidation:
    """URL validation logic."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com",
            "http://localhost:8080",
            "https://user:pass@host/path?query=1",
        ],
    )
    def test_valid_urls(self, url: str) -> None:
        assert _validate_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com",
            "example.com",
            "not-a-url",
            "",
            "javascript:void(0)",
        ],
    )
    def test_invalid_urls(self, url: str) -> None:
        assert _validate_url(url) is False


class TestCliExtractCommand:
    """End-to-end ``extract`` command scenarios."""

    def test_extract_invalid_url(self) -> None:
        """An invalid URL should return exit code 1 with a friendly error."""
        exit_code = main(["extract", "--url", "not-a-url"])
        assert exit_code == 1

    @patch("omni_extractor.cli.ExtractionPipeline")
    @patch("omni_extractor.cli._load_settings")
    def test_extract_success_stdout(
        self,
        mock_load_settings: MagicMock,
        mock_pipeline_cls: MagicMock,
    ) -> None:
        """A successful extraction should print JSON to stdout."""
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings

        mock_pipeline = AsyncMock()
        mock_pipeline_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipeline
        )
        mock_pipeline_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = ExtractionResult(
            url="https://example.com",
            title="Test",
            summary="Summary",
            main_content="Content",
            publish_time=None,
            author=None,
            keywords=["test"],
            confidence=0.95,
            raw_excerpt="Content",
        )
        mock_pipeline.extract_single = AsyncMock(return_value=result)

        with patch("omni_extractor.cli.Console.print") as mock_print:
            exit_code = main(["extract", "--url", "https://example.com"])

        assert exit_code == 0
        mock_pipeline.extract_single.assert_awaited_once_with(
            "https://example.com", print_result=False
        )
        # Ensure something JSON-like was printed
        printed = [call.args[0] for call in mock_print.call_args_list]
        json_strs = [s for s in printed if isinstance(s, str) and "Test" in s]
        assert len(json_strs) == 1
        parsed = json.loads(json_strs[0])
        assert parsed["url"] == "https://example.com"
        assert parsed["title"] == "Test"

    @patch("omni_extractor.cli.ExtractionPipeline")
    @patch("omni_extractor.cli._load_settings")
    def test_extract_success_file_output(
        self,
        mock_load_settings: MagicMock,
        mock_pipeline_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A successful extraction with ``--output`` should write to a file."""
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings

        mock_pipeline = AsyncMock()
        mock_pipeline_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipeline
        )
        mock_pipeline_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = ExtractionResult(
            url="https://example.com",
            title="Test",
            summary="Summary",
            main_content="Content",
            publish_time=None,
            author=None,
            keywords=["test"],
            confidence=0.95,
            raw_excerpt="Content",
        )
        mock_pipeline.extract_single = AsyncMock(return_value=result)

        output_file = tmp_path / "result.json"
        exit_code = main(
            [
                "extract",
                "--url",
                "https://example.com",
                "--output",
                str(output_file),
            ]
        )

        assert exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert data["url"] == "https://example.com"
        assert data["title"] == "Test"

    @patch("omni_extractor.cli.ExtractionPipeline")
    @patch("omni_extractor.cli._load_settings")
    def test_extract_failure(
        self,
        mock_load_settings: MagicMock,
        mock_pipeline_cls: MagicMock,
    ) -> None:
        """An extraction failure should return exit code 1."""
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings

        mock_pipeline = AsyncMock()
        mock_pipeline_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipeline
        )
        mock_pipeline_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        error = ExtractionError(
            url="https://example.com",
            error_type="FetchError",
            error_message="Network unreachable",
            timestamp="2024-01-01T00:00:00",
        )
        mock_pipeline.extract_single = AsyncMock(return_value=error)

        exit_code = main(["extract", "--url", "https://example.com"])
        assert exit_code == 1


class TestCliExtractBatchCommand:
    """End-to-end ``extract-batch`` command scenarios."""

    def test_extract_batch_missing_input_file(self) -> None:
        """A missing input file should return exit code 1."""
        exit_code = main(
            [
                "extract-batch",
                "--input",
                "/nonexistent/urls.txt",
            ]
        )
        assert exit_code == 1

    def test_extract_batch_empty_input_file(self, tmp_path: Path) -> None:
        """An empty input file should return exit code 1."""
        input_file = tmp_path / "empty.txt"
        input_file.write_text("\n\n", encoding="utf-8")
        exit_code = main(
            [
                "extract-batch",
                "--input",
                str(input_file),
            ]
        )
        assert exit_code == 1

    def test_extract_batch_invalid_urls(self, tmp_path: Path) -> None:
        """Invalid URLs in the input file should return exit code 1."""
        input_file = tmp_path / "urls.txt"
        input_file.write_text("not-a-url\nanother-bad-url\n", encoding="utf-8")
        exit_code = main(
            [
                "extract-batch",
                "--input",
                str(input_file),
            ]
        )
        assert exit_code == 1

    @patch("omni_extractor.cli.ExtractionPipeline")
    @patch("omni_extractor.cli._load_settings")
    def test_extract_batch_success(
        self,
        mock_load_settings: MagicMock,
        mock_pipeline_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A successful batch run should return exit code 0."""
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings

        mock_pipeline = AsyncMock()
        mock_pipeline_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipeline
        )
        mock_pipeline_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        success = ExtractionResult(
            url="https://example.com",
            title="Test",
            summary="Summary",
            main_content="Content",
            publish_time=None,
            author=None,
            keywords=["test"],
            confidence=0.95,
            raw_excerpt="Content",
        )
        batch_result = MagicMock()
        batch_result.successes = [success]
        batch_result.total_failed = 0
        batch_result.total_processed = 1
        mock_pipeline.extract_batch = AsyncMock(return_value=batch_result)

        input_file = tmp_path / "urls.txt"
        input_file.write_text("https://example.com\n", encoding="utf-8")

        exit_code = main(
            [
                "extract-batch",
                "--input",
                str(input_file),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )

        assert exit_code == 0
        mock_pipeline.extract_batch.assert_awaited_once()
        call_urls = mock_pipeline.extract_batch.await_args[0][0]
        assert call_urls == ["https://example.com"]

    @patch("omni_extractor.cli.ExtractionPipeline")
    @patch("omni_extractor.cli._load_settings")
    def test_extract_batch_mixed_results(
        self,
        mock_load_settings: MagicMock,
        mock_pipeline_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A batch with failures should still complete and return 0."""
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings

        mock_pipeline = AsyncMock()
        mock_pipeline_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipeline
        )
        mock_pipeline_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        batch_result = MagicMock()
        batch_result.successes = []
        batch_result.total_failed = 1
        batch_result.total_processed = 1
        mock_pipeline.extract_batch = AsyncMock(return_value=batch_result)

        input_file = tmp_path / "urls.txt"
        input_file.write_text("https://example.com\n", encoding="utf-8")

        exit_code = main(
            [
                "extract-batch",
                "--input",
                str(input_file),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )

        assert exit_code == 0


class TestCliConfigHandling:
    """Configuration loading behaviour."""

    @patch("omni_extractor.cli._load_settings")
    def test_config_flag_passed_to_settings(
        self,
        mock_load_settings: MagicMock,
    ) -> None:
        """``--config`` should be forwarded to the settings loader."""
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings

        parser = _create_parser()
        args = parser.parse_args(
            [
                "--config",
                "/custom/.env",
                "extract",
                "--url",
                "https://example.com",
            ]
        )
        assert args.config == "/custom/.env"

    @patch("omni_extractor.cli._load_settings")
    def test_config_load_failure(
        self,
        mock_load_settings: MagicMock,
    ) -> None:
        """A settings load failure should return exit code 1."""
        mock_load_settings.side_effect = ValueError("Bad config")

        exit_code = main(
            [
                "--config",
                "/bad/.env",
                "extract",
                "--url",
                "https://example.com",
            ]
        )
        assert exit_code == 1


class TestCliKeyboardInterrupt:
    """Graceful interruption handling."""

    @patch("omni_extractor.cli._load_settings")
    def test_keyboard_interrupt(
        self,
        mock_load_settings: MagicMock,
    ) -> None:
        """A KeyboardInterrupt should return exit code 130."""
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings

        with patch("omni_extractor.cli.asyncio.run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            exit_code = main(
                [
                    "extract",
                    "--url",
                    "https://example.com",
                ]
            )

        assert exit_code == 130
