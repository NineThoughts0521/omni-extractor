# omni-extractor

## TL;DR
> **Summary**: Build a greenfield Python CLI engine that asynchronously fetches webpages at bounded high concurrency and uses the OpenAI official SDK to extract a fixed, validated JSON payload from HTML.
> **Deliverables**:
> - uv-managed Python project with modular `network`, `llm`, `pipeline`, `cli`, and `config` packages
> - Shared `httpx.AsyncClient` fetch layer with retries, random User-Agent rotation, and concurrency controls
> - `.env`-driven OpenAI integration with forced JSON output and schema validation
> - `rich` progress UI, `loguru` logging, pytest async test suite, git/GitHub-ready repository scaffolding
> **Effort**: Medium
> **Parallel**: YES - 3 waves
> **Critical Path**: 1 → 2 → 5 → 7 → 8 → 9 → 10 → 11

## Context
### Original Request
Create a Python project named `omni-extractor` using `uv`, with `git` project management and future GitHub upload, to serve as a high-concurrency LLM-powered webpage information extraction engine. The stack must use `httpx` + `asyncio` for concurrent fetching with retry and random User-Agent support; the OpenAI official SDK must read API key and base URL from `.env` and force JSON output; terminal UX must use `loguru` and `rich`; architecture must cleanly separate network, LLM parsing, and orchestration.

### Interview Summary
- Delivery shape: CLI engine
- Primary use case: general single-page extraction
- Quality bar: test-first baseline (`pytest` + async tests + core unit/integration coverage)
- V1 output schema: fixed general schema
- CLI input modes: single URL and batch file
- V1 scope excludes advanced compliance/governance systems
- Showcase goal: polished GitHub-uploadable project suitable for Xiaomi Mimo application/demo usage

### Metis Review (gaps addressed)
- Fixed the V1 extraction schema to avoid execution-time ambiguity
- Fixed concrete defaults for concurrency, timeouts, retry policy, content filtering, and output persistence
- Added explicit handling for oversized HTML, invalid content type, model refusal, and partial batch failure
- Added measurable verification targets and agent-executable QA scenarios per task

## Work Objectives
### Core Objective
Deliver a production-style V1 CLI that accepts one URL or a batch file of URLs, fetches HTML concurrently with bounded resource usage, sends processed page content to an OpenAI-compatible endpoint configured via `.env`, and returns validated JSON in a stable schema.

### Deliverables
- Python 3.11+ project initialized with `uv`
- Source package `omni_extractor/` with submodules for configuration, schemas, networking, LLM integration, orchestration, and CLI
- Fixed output schema with validation:
  - `url: str`
  - `title: str`
  - `summary: str`
  - `main_content: str`
  - `publish_time: str | null`
  - `author: str | null`
  - `keywords: list[str]`
  - `confidence: float`
  - `raw_excerpt: str`
- Batch execution with progress bar and per-URL success/failure accounting
- `.env.example`, `.gitignore`, `README.md`, and GitHub-ready project hygiene
- Test suite covering config, retry behavior, schema validation, fetch pipeline, and CLI happy/failure flows

### Definition of Done (verifiable conditions with commands)
- `uv sync` succeeds from repo root
- `uv run pytest` passes
- `uv run python -m omni_extractor --help` exits 0 and renders CLI help
- `uv run python -m omni_extractor extract --url https://example.com --output stdout` exits 0 with valid JSON when provided a working `.env`
- `uv run python -m omni_extractor extract-batch --input sample-urls.txt --output-dir outputs` exits 0, writes machine-readable results, and reports failures without aborting the entire batch
- `git init` has been run and `.gitignore` excludes virtualenvs, secrets, caches, logs, and outputs

### Must Have
- `uv`-based dependency and script management
- Clear separation between network fetching, HTML preprocessing, LLM extraction, orchestration, and CLI concerns
- Shared `httpx.AsyncClient` lifecycle
- Explicit concurrency limits:
  - HTTP fetch semaphore default: `20`
  - OpenAI extraction semaphore default: `5`
  - HTTP client limits: `max_connections=40`, `max_keepalive_connections=20`, `keepalive_expiry=30.0`
- Explicit timeout defaults:
  - HTTP connect/read/write/pool: `10s / 30s / 5s / 10s`
  - OpenAI request timeout: `60s`
- Retry policy:
  - HTTP attempts: `3` total
  - Exponential backoff base: `0.5s`, multiplier `2`, jitter enabled
  - Retryable conditions: `httpx.TimeoutException`, `httpx.NetworkError`, HTTP `429/500/502/503/504`
- Random User-Agent rotation from a curated built-in list of modern desktop browser UAs
- HTML-only processing: non-HTML responses rejected with structured error results
- HTML preprocessing before LLM call:
  - remove `script/style/noscript`
  - extract visible text and document title
  - cap model input to a configurable character budget defaulting to `20_000` characters
- OpenAI SDK configured solely from environment-backed settings for `api_key`, `base_url`, and `model`
- Forced JSON output with schema validation and explicit model-refusal handling
- Single URL output default: pretty JSON to stdout unless file path is provided
- Batch output default: JSONL file under `outputs/results-<timestamp>.jsonl` plus companion failures file under the same directory

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No web UI, FastAPI service, or browser automation in V1
- No distributed queue system, Redis, Celery, or database persistence
- No multi-provider abstraction beyond the OpenAI-compatible SDK/base URL configuration already requested
- No advanced compliance subsystem (robots enforcement, allowlist/blocklist, governance dashboard)
- No silent fallback to unstructured text output if JSON validation fails
- No per-request creation of `httpx.AsyncClient` or OpenAI client objects
- No unbounded `asyncio.gather` over arbitrary URL lists
- No hidden defaults stored directly in code when they must be user-configurable via settings/env/CLI flags

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after with `pytest` + `pytest-asyncio`
- QA policy: Every task includes agent-executed happy-path and failure/edge-case scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: repository bootstrap, settings/schema design, HTTP policy foundation, logging/progress foundation, test harness

Wave 2: fetcher implementation, HTML preprocessing, OpenAI extractor, single-URL pipeline, batch pipeline

Wave 3: CLI surface, repository polish/docs/GitHub readiness

### Dependency Matrix (full, all tasks)
- 1 blocks 2, 3, 4, 5, 11, 12
- 2 blocks 6, 7, 8, 9, 10
- 3 blocks 6, 9
- 4 blocks 10
- 5 blocks 6, 7, 8, 9, 10, 11
- 6 blocks 8, 9
- 7 blocks 8, 9
- 8 blocks 10
- 9 blocks 10, 11
- 10 blocks 11, 12
- 11 blocks 12
- 12 blocks Final Verification Wave

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 5 tasks → `quick`, `unspecified-low`
- Wave 2 → 5 tasks → `quick`, `unspecified-high`
- Wave 3 → 2 tasks → `writing`, `quick`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit 1: `chore(init): bootstrap uv project and repository scaffolding`
- Commit 2: `feat(core): add async fetching and llm extraction pipeline`
- Commit 3: `feat(cli): add batch CLI workflow and project documentation`
- Commit 4: `test(core): add async pipeline and cli verification coverage`

## Success Criteria
- The repository can be cloned, configured with `.env`, and run locally via `uv` without manual patching
- The system returns validated fixed-schema JSON for supported HTML pages
- Batch processing is bounded, observable, and resilient to partial failures
- Tests prove config loading, retry semantics, schema validation, and CLI behavior
- The repository is polished enough for public GitHub publication and demo use
