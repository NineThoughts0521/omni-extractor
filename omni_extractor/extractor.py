"""LLM-based extraction functionality for omni-extractor."""

import asyncio
import json
from typing import Optional

import openai
from loguru import logger
from pydantic import ValidationError

from omni_extractor.config import Settings
from omni_extractor.models import ExtractionResult


class ExtractionException(Exception):
    """Exception raised when LLM extraction fails."""

    def __init__(self, message: str, url: Optional[str] = None) -> None:
        super().__init__(message)
        self.url = url


class LLMExtractor:
    """Extract structured content from web pages using an LLM."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize the extractor with application settings.

        Args:
            settings: Application settings. If None, loads from environment.
        """
        self.settings = settings or Settings()
        self.client = openai.AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            timeout=60.0,
        )
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_extract)

    async def extract(self, url: str, raw_content: str) -> ExtractionResult:
        """Extract structured data from raw web content.

        Args:
            url: The source URL for context.
            raw_content: The cleaned text or HTML content to analyse.

        Returns:
            Validated extraction result.

        Raises:
            ExtractionException: On model refusal, timeout, or validation failure.
        """
        async with self._semaphore:
            logger.debug("Starting extraction for {}", url)
            prompt = self._build_prompt(url, raw_content)

            try:
                response = await self.client.chat.completions.create(
                    model=self.settings.openai_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a precise web-content extraction assistant. "
                                "Analyse the provided webpage content and return a single JSON object "
                                "matching the requested schema exactly."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
            except openai.APITimeoutError as exc:
                logger.error("OpenAI call timed out for {}: {}", url, exc)
                raise ExtractionException(
                    f"OpenAI request timed out after 60s: {exc}", url=url
                ) from exc
            except Exception as exc:
                logger.error("OpenAI call failed for {}: {}", url, exc)
                raise ExtractionException(
                    f"OpenAI request failed: {exc}", url=url
                ) from exc

            choice = response.choices[0]
            message = choice.message

            if getattr(message, "refusal", None):
                logger.warning("Model refused extraction for {}", url)
                raise ExtractionException(
                    f"Model refused to extract content: {message.refusal}", url=url
                )

            raw_text = message.content or ""
            if not raw_text.strip():
                raise ExtractionException(
                    "OpenAI returned empty content", url=url
                )

            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                logger.error("Invalid JSON from LLM for {}: {}", url, exc)
                raise ExtractionException(
                    f"LLM returned invalid JSON: {exc}", url=url
                ) from exc

            # Ensure the URL from the prompt is present if the model omitted it
            if "url" not in parsed:
                parsed["url"] = url

            try:
                result = ExtractionResult.model_validate(parsed)
            except ValidationError as exc:
                logger.error("Pydantic validation failed for {}: {}", url, exc)
                raise ExtractionException(
                    f"LLM output failed validation: {exc}", url=url
                ) from exc

            logger.debug("Extraction successful for {}", url)
            return result

    def _build_prompt(self, url: str, raw_content: str) -> str:
        """Build the extraction prompt including URL context.

        Args:
            url: Source URL.
            raw_content: Cleaned content to analyse.

        Returns:
            Prompt string.
        """
        return (
            f"URL: {url}\n\n"
            "Extract the following fields from the webpage content below and "
            "return them as a JSON object with these exact keys:\n"
            "- url (string): the page URL\n"
            "- title (string): the page title\n"
            "- summary (string): a brief summary of the main content\n"
            "- main_content (string): the main body of the article or page\n"
            "- publish_time (string or null): publication date/time if available\n"
            "- author (string or null): author name if available\n"
            "- keywords (list of strings): relevant keywords\n"
            "- confidence (number 0.0-1.0): confidence in the extraction\n"
            "- raw_excerpt (string): a short raw excerpt from the content\n\n"
            f"Webpage content:\n{raw_content}"
        )


__all__ = ["LLMExtractor", "ExtractionException"]
