# omni-extractor

<!-- Badges -->
<!--
[![CI](https://github.com/YOUR_USERNAME/omni-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/omni-extractor/actions)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
-->

A high-performance, LLM-powered web content extraction engine built for batch processing. Fetch, clean, and extract structured data from any URL with configurable concurrency, retry logic, and smart HTML preprocessing.

This project is designed with clean architecture and production-grade patterns, making it an excellent showcase for developer portfolio applications such as the **Xiaomi Mimo token application**.

## Features

- **LLM-Powered Extraction**: Uses OpenAI models to extract structured metadata from raw web pages
- **Async Batch Processing**: Process dozens of URLs concurrently with semaphores and progress bars
- **Smart HTML Cleaning**: Strips scripts, styles, and noise while preserving article text with BeautifulSoup4
- **Robust Fetching**: Automatic retries with exponential backoff, jitter, and User-Agent rotation
- **Structured Output**: Pydantic-validated results with confidence scores
- **Rich CLI**: Beautiful progress bars and colored output via Rich
- **Configurable**: Environment-based configuration with sensible defaults
- **Fault Tolerant**: One failed URL never aborts an entire batch

## Installation

Requires Python 3.11 or later.

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/omni-extractor.git
cd omni-extractor

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e ".[dev]"
```

## Quick Start

### 1. Configure your environment

Copy the example environment file and add your OpenAI API key:

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-...
```

### 2. Extract a single URL

```bash
uv run omni-extractor extract --url "https://example.com/article"
```

Save to a file instead of stdout:

```bash
uv run omni-extractor extract --url "https://example.com/article" -o result.json
```

### 3. Batch extract from a URL list

Create a file with one URL per line:

```bash
cat urls.txt
https://example.com/article-1
https://example.com/article-2
https://example.com/article-3
```

Run batch extraction:

```bash
uv run omni-extractor extract-batch -i urls.txt -d outputs/
```

Results are written to timestamped JSONL files:

- `outputs/results-YYYYMMDD-HHMMSS.jsonl` (successful extractions)
- `outputs/failures-YYYYMMDD-HHMMSS.jsonl` (failed extractions)

## Configuration

All settings are loaded from environment variables via a `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | Your OpenAI API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Custom OpenAI-compatible API base URL |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model to use for extraction |
| `HTTP_TIMEOUT` | `30.0` | HTTP request timeout in seconds |
| `MAX_CONCURRENT_FETCH` | `20` | Maximum concurrent HTTP fetch operations |
| `MAX_CONCURRENT_EXTRACT` | `5` | Maximum concurrent OpenAI extraction calls |
| `MAX_RETRIES` | `3` | Retry attempts for failed network requests |
| `RETRY_BASE_DELAY` | `0.5` | Base delay in seconds for exponential backoff |
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |

Use a custom config file:

```bash
uv run omni-extractor --config /path/to/.env extract --url "https://example.com"
```

## Extraction Schema

Every successful extraction returns a structured result with the following fields:

```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "summary": "A brief summary of the article content.",
  "main_content": "The full main body text of the article...",
  "publish_time": "2024-01-15T10:30:00",
  "author": "Jane Doe",
  "keywords": ["technology", "ai", "tutorial"],
  "confidence": 0.92,
  "raw_excerpt": "First few sentences from the raw content..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | The extracted page URL |
| `title` | string | Page or article title |
| `summary` | string | Brief summary of the main content |
| `main_content` | string | Full extracted article body |
| `publish_time` | string \| null | Publication date/time if available |
| `author` | string \| null | Author name if available |
| `keywords` | list[string] | Relevant keywords or tags |
| `confidence` | number (0.0-1.0) | Confidence score of the extraction |
| `raw_excerpt` | string | Short raw excerpt from the content |

## Architecture

```
omni_extractor/
├── cli.py          # argparse CLI with extract and extract-batch commands
├── pipeline.py     # Orchestrates fetch -> clean -> extract with progress tracking
├── fetcher.py      # Async HTTP client with retry, UA rotation, and concurrency limits
├── html_cleaner.py # BeautifulSoup4-based HTML cleaning and text extraction
├── extractor.py    # OpenAI LLM integration with structured JSON extraction
├── models.py       # Pydantic models for ExtractionResult, ExtractionError, BatchResult
├── config.py       # Pydantic-settings based configuration from environment variables
└── utils.py        # Shared utility functions
```

### Pipeline Flow

1. **Fetch**: `httpx.AsyncClient` fetches the raw HTML with retries and UA rotation
2. **Clean**: `HTMLCleaner` strips scripts, styles, and invisible elements, then extracts visible text within a character budget
3. **Extract**: `LLMExtractor` sends cleaned text to OpenAI with a structured prompt and validates the JSON response against `ExtractionResult`
4. **Output**: Results are serialized as JSON (single) or JSONL (batch)

## Development

### Setup

```bash
uv sync
```

### Run Tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=omni_extractor --cov-report=term-missing
```

### Lint and Format

```bash
# Check code
uv run ruff check omni_extractor tests

# Auto-fix issues
uv run ruff check --fix omni_extractor tests

# Format code
uv run ruff format omni_extractor tests
```

### Type Check

```bash
uv run mypy omni_extractor
```

## Project Showcase

This project demonstrates production-ready Python engineering practices:

- Clean architecture with separation of concerns
- Async/await patterns for I/O-bound concurrency
- Pydantic models for runtime validation and type safety
- Environment-based configuration with sensible defaults
- Comprehensive test coverage with pytest and asyncio fixtures
- Modern tooling: `uv`, `ruff`, `mypy`, `pytest`

These qualities make it well-suited for portfolio submissions, including the **Xiaomi Mimo token application**.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome. Please open an issue or pull request on GitHub.
