"""Command-line interface for omni-extractor."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from rich.console import Console

from omni_extractor.config import Settings
from omni_extractor.models import ExtractionError
from omni_extractor.pipeline import ExtractionPipeline


def _create_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="omni-extractor",
        description="A unified extraction tool for various content sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Path to a custom .env configuration file (optional).",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ------------------------------------------------------------------
    # extract
    # ------------------------------------------------------------------
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract content from a single URL.",
        description="Fetch, clean, and extract structured content from a single URL.",
    )
    extract_parser.add_argument(
        "--url",
        required=True,
        help="Target URL to extract content from.",
    )
    extract_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help=(
            "Path to write the JSON result. If omitted, results are printed to stdout."
        ),
    )

    # ------------------------------------------------------------------
    # extract-batch
    # ------------------------------------------------------------------
    batch_parser = subparsers.add_parser(
        "extract-batch",
        help="Extract content from multiple URLs.",
        description=(
            "Read a list of URLs from a file and process them in batch. "
            "Results are written to JSONL files under the output directory."
        ),
    )
    batch_parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to a text file containing one URL per line.",
    )
    batch_parser.add_argument(
        "--output-dir",
        "-d",
        default="outputs",
        help=("Directory to write results. Defaults to 'outputs/'."),
    )

    return parser


def _load_settings(config_path: Optional[str]) -> Settings:
    """Load settings, optionally from a custom .env file."""
    kwargs: dict = {}
    if config_path is not None:
        kwargs["_env_file"] = config_path
    return Settings(**kwargs)


def _read_url_file(path: str) -> List[str]:
    """Read a file and return a list of non-empty, stripped URLs."""
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _validate_url(url: str) -> bool:
    """Perform basic URL validation."""
    return url.startswith(("http://", "https://"))


def _write_json_output(path: str, data: dict) -> None:
    """Write serialised JSON to the given path."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


async def _run_extract(
    url: str,
    output_path: Optional[str],
    settings: Settings,
    console: Console,
) -> int:
    """Execute the ``extract`` command.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    if not _validate_url(url):
        console.print(f"[red]Error:[/red] Invalid URL: {url}")
        return 1

    async with ExtractionPipeline(settings=settings) as pipeline:
        result = await pipeline.extract_single(url, print_result=False)

    if isinstance(result, ExtractionError):
        console.print(f"[red]Extraction failed for {result.url}[/red]")
        console.print(f"  {result.error_type}: {result.error_message}")
        return 1

    json_data = result.model_dump()
    json_str = json.dumps(json_data, indent=2, default=str)

    if output_path is not None:
        _write_json_output(output_path, json_data)
        console.print(f"[green]Result written to[/green] {output_path}")
    else:
        console.print(json_str)

    return 0


async def _run_extract_batch(
    input_path: str,
    output_dir: str,
    settings: Settings,
    console: Console,
) -> int:
    """Execute the ``extract-batch`` command.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    if not os.path.isfile(input_path):
        console.print(f"[red]Error:[/red] Input file not found: {input_path}")
        return 1

    urls = _read_url_file(input_path)
    if not urls:
        console.print("[red]Error:[/red] No URLs found in input file.")
        return 1

    invalid_urls = [u for u in urls if not _validate_url(u)]
    if invalid_urls:
        console.print("[red]Error:[/red] The following URLs are invalid:")
        for u in invalid_urls:
            console.print(f"  - {u}")
        return 1

    output_path = Path(output_dir)
    async with ExtractionPipeline(
        settings=settings, output_dir=output_path
    ) as pipeline:
        batch_result = await pipeline.extract_batch(urls)

    console.print(
        f"[green]Batch complete:[/green] "
        f"{len(batch_result.successes)} succeeded, "
        f"{batch_result.total_failed} failed "
        f"out of {batch_result.total_processed}."
    )
    console.print(f"Results written to [cyan]{output_path.resolve()}[/cyan]")

    return 0 if batch_result.total_failed == 0 else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse arguments and dispatch to the appropriate command handler.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parser = _create_parser()
    args = parser.parse_args(argv)
    console = Console(stderr=True)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        settings = _load_settings(args.config)
    except Exception as exc:
        console.print(f"[red]Error loading configuration:[/red] {exc}")
        return 1

    try:
        if args.command == "extract":
            return asyncio.run(
                _run_extract(
                    url=args.url,
                    output_path=args.output,
                    settings=settings,
                    console=console,
                )
            )
        elif args.command == "extract-batch":
            return asyncio.run(
                _run_extract_batch(
                    input_path=args.input,
                    output_dir=args.output_dir,
                    settings=settings,
                    console=console,
                )
            )
        else:
            parser.print_help()
            return 0
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        return 130
    except Exception as exc:
        console.print(f"[red]Unexpected error:[/red] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
