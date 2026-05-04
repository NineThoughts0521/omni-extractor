"""HTML preprocessing utilities for omni-extractor."""

import re
from typing import Tuple, Optional
from bs4 import BeautifulSoup
from bs4.element import Comment
from loguru import logger


class HTMLCleaner:
    """HTML cleaning and text extraction utility."""

    def __init__(self, char_budget: int = 20000):
        """Initialize HTML cleaner with character budget.

        Args:
            char_budget: Maximum characters to extract (default: 20000)
        """
        self.char_budget = char_budget

    def clean_html(self, html_content: str) -> Tuple[str, Optional[str]]:
        """Clean HTML content and extract visible text and title.

        Args:
            html_content: Raw HTML content

        Returns:
            Tuple of (cleaned_text, title)

        Raises:
            ValueError: If HTML content is empty or malformed
        """
        if not html_content:
            raise ValueError("HTML content cannot be empty")

        try:
            # Parse HTML with BeautifulSoup using html.parser (standard library)
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            raise ValueError(f"Malformed HTML: {e}")

        # Extract title before removing elements
        title = self._extract_title(soup)

        # Remove unwanted elements
        self._remove_unwanted_elements(soup)

        # Extract visible text, excluding title if it was in title tag
        text = self._extract_visible_text(soup, title)

        # Apply character budget
        text = self._apply_char_budget(text)

        return text, title

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from HTML document.

        Tries in order: <title> tag, first <h1>, None if not found
        """
        # Try title tag first
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            return title_tag.get_text(strip=True)

        # Try first h1 as fallback
        h1_tag = soup.find("h1")
        if h1_tag and h1_tag.get_text(strip=True):
            return h1_tag.get_text(strip=True)

        return None

    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """Remove script, style, noscript, iframe, and svg elements."""
        unwanted_tags = ["script", "style", "noscript", "iframe", "svg"]

        for tag_name in unwanted_tags:
            for element in soup.find_all(tag_name):
                element.decompose()

    def _extract_visible_text(
        self, soup: BeautifulSoup, title: Optional[str] = None
    ) -> str:
        """Extract visible text from HTML, excluding comments and hidden elements."""

        def is_visible_element(element):
            """Check if element should be considered visible text."""
            if element.parent.name in [
                "style",
                "script",
                "noscript",
                "iframe",
                "svg",
                "title",
            ]:
                return False
            if isinstance(element, Comment):
                return False
            return True

        # Get all text elements
        texts = soup.find_all(string=True)
        visible_texts = [
            text.strip() for text in texts if is_visible_element(text) and text.strip()
        ]

        # Join with spaces and normalize whitespace
        text = " ".join(visible_texts)
        text = re.sub(r"\s+", " ", text)  # Collapse multiple whitespace
        text = text.strip()

        return text

    def _apply_char_budget(self, text: str) -> str:
        """Apply character budget while preserving sentence boundaries."""
        if len(text) <= self.char_budget:
            return text

        # Truncate to budget
        truncated = text[: self.char_budget]

        # Try to end at a sentence boundary
        last_sentence_end = max(
            truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?")
        )

        if (
            last_sentence_end > self.char_budget * 0.8
        ):  # Only if it's reasonably close to budget
            return truncated[: last_sentence_end + 1]

        # Otherwise, try to end at a word boundary
        last_space = truncated.rfind(" ")
        if last_space > self.char_budget * 0.9:  # Only if it's very close to budget
            return truncated[:last_space]

        return truncated


def clean_html_content(
    html_content: str, char_budget: int = 20000
) -> Tuple[str, Optional[str]]:
    """Convenience function to clean HTML content.

    Args:
        html_content: Raw HTML content
        char_budget: Maximum characters to extract (default: 20000)

    Returns:
        Tuple of (cleaned_text, title)
    """
    cleaner = HTMLCleaner(char_budget=char_budget)
    return cleaner.clean_html(html_content)
