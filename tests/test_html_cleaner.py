"""Tests for HTML cleaner functionality."""

import pytest
from omni_extractor.html_cleaner import HTMLCleaner, clean_html_content


class TestHTMLCleaner:
    """Test cases for HTMLCleaner class."""

    def test_basic_html_cleaning(self):
        """Test basic HTML cleaning and text extraction."""
        html = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Main Heading</h1>
            <p>This is a paragraph with some text.</p>
            <p>Another paragraph with more text.</p>
        </body>
        </html>
        """

        cleaner = HTMLCleaner()
        text, title = cleaner.clean_html(html)

        assert title == "Test Page"
        assert "Main Heading" in text
        assert "This is a paragraph with some text." in text
        assert "Another paragraph with more text." in text

    def test_script_style_removal(self):
        """Test removal of script and style tags."""
        html = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <script>alert('This should be removed');</script>
            <style>body { color: red; }</style>
            <noscript>No script content</noscript>
            <p>This is visible text.</p>
        </body>
        </html>
        """

        cleaner = HTMLCleaner()
        text, title = cleaner.clean_html(html)

        assert title == "Test Page"
        assert "This is visible text." in text
        assert "alert" not in text
        assert "color: red" not in text
        assert "No script content" not in text

    def test_title_extraction_priority(self):
        """Test title extraction priority: title tag first, then h1."""
        # Title tag present
        html1 = """
        <html><head><title>Page Title</title></head>
        <body><h1>Main Heading</h1><p>Content</p></body>
        </html>
        """

        # No title tag, h1 present
        html2 = """
        <html><head></head>
        <body><h1>Main Heading</h1><p>Content</p></body>
        </html>
        """

        # Neither title nor h1
        html3 = """
        <html><head></head>
        <body><p>Content</p></body>
        </html>
        """

        cleaner = HTMLCleaner()

        text1, title1 = cleaner.clean_html(html1)
        assert title1 == "Page Title"

        text2, title2 = cleaner.clean_html(html2)
        assert title2 == "Main Heading"

        text3, title3 = cleaner.clean_html(html3)
        assert title3 is None

    def test_character_budget_truncation(self):
        """Test character budget limiting."""
        # Create HTML with long text
        long_text = "This is a very long paragraph. " * 1000  # ~45k characters
        html = f"""
        <html><head><title>Long Page</title></head>
        <body><p>{long_text}</p></body>
        </html>
        """

        cleaner = HTMLCleaner(char_budget=1000)
        text, title = cleaner.clean_html(html)

        assert title == "Long Page"
        assert len(text) <= 1100  # Allow some margin for sentence boundary preservation
        assert len(text) >= 900  # Should be reasonably close to budget

    def test_whitespace_normalization(self):
        """Test whitespace normalization."""
        html = """
        <html>
        <body>
            <p>   Multiple   spaces   and   tabs   </p>
            <div>
                Multiple
                lines
                and
                newlines
            </div>
        </body>
        </html>
        """

        cleaner = HTMLCleaner()
        text, title = cleaner.clean_html(html)

        # Should not have multiple consecutive spaces
        assert "  " not in text
        # Should not have multiple newlines
        assert "\n\n" not in text
        # Should be properly trimmed
        assert not text.startswith(" ")
        assert not text.endswith(" ")

    def test_malformed_html_handling(self):
        """Test handling of malformed HTML."""
        malformed_html = """
        <html>
        <body>
            <p>Unclosed paragraph
            <div>Missing closing tag
            <script>alert('test');</script>
            <p>Proper paragraph</p>
        </body>
        """

        cleaner = HTMLCleaner()
        text, title = cleaner.clean_html(malformed_html)

        # Should still extract some text
        assert "Proper paragraph" in text
        assert "alert" not in text  # Script should be removed

    def test_empty_html_handling(self):
        """Test handling of empty HTML content."""
        cleaner = HTMLCleaner()

        with pytest.raises(ValueError, match="HTML content cannot be empty"):
            cleaner.clean_html("")

        with pytest.raises(ValueError, match="HTML content cannot be empty"):
            cleaner.clean_html(None)

    def test_iframe_svg_removal(self):
        """Test removal of iframe and svg elements."""
        html = """
        <html>
        <body>
            <p>Visible text</p>
            <iframe src="https://example.com"></iframe>
            <svg><circle cx="50" cy="50" r="40" /></svg>
            <p>More visible text</p>
        </body>
        </html>
        """

        cleaner = HTMLCleaner()
        text, title = cleaner.clean_html(html)

        assert "Visible text" in text
        assert "More visible text" in text
        assert "iframe" not in text.lower()
        assert "svg" not in text.lower()
        assert "circle" not in text.lower()

    def test_comment_removal(self):
        """Test removal of HTML comments."""
        html = """
        <html>
        <body>
            <!-- This is a comment that should be removed -->
            <p>Visible text</p>
            <!-- Another comment -->
        </body>
        </html>
        """

        cleaner = HTMLCleaner()
        text, title = cleaner.clean_html(html)

        assert "Visible text" in text
        assert "comment" not in text.lower()
        assert "<!--" not in text


class TestCleanHTMLContent:
    """Test cases for the convenience function."""

    def test_clean_html_content_convenience_function(self):
        """Test the convenience function wrapper."""
        html = """
        <html>
        <head><title>Convenience Test</title></head>
        <body><p>Test content</p></body>
        </html>
        """

        text, title = clean_html_content(html, char_budget=5000)

        assert title == "Convenience Test"
        assert "Test content" in text
        assert len(text) <= 5000

    def test_clean_html_content_default_budget(self):
        """Test convenience function with default character budget."""
        html = """
        <html>
        <head><title>Default Budget Test</title></head>
        <body><p>Short content</p></body>
        </html>
        """

        text, title = clean_html_content(html)

        assert title == "Default Budget Test"
        assert "Short content" in text
        # Default budget is 20000, so all content should be preserved
        assert text == "Short content"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_long_title(self):
        """Test handling of very long title."""
        long_title = "Very Long Title " * 100
        html = f"""
        <html>
        <head><title>{long_title}</title></head>
        <body><p>Content</p></body>
        </html>
        """

        cleaner = HTMLCleaner()
        text, title = cleaner.clean_html(html)

        # Title should be preserved as-is (not subject to character budget)
        assert title == long_title.strip()
        assert "Content" in text

    def test_nested_unwanted_elements(self):
        """Test removal of nested unwanted elements."""
        html = """
        <html>
        <body>
            <div>
                <script>alert('nested script');</script>
                <p>Visible text in div</p>
                <style>body { color: blue; }</style>
            </div>
            <p>Outside text</p>
        </body>
        </html>
        """

        cleaner = HTMLCleaner()
        text, title = cleaner.clean_html(html)

        assert "Visible text in div" in text
        assert "Outside text" in text
        assert "alert" not in text
        assert "color: blue" not in text

    def test_unicode_content(self):
        """Test handling of unicode content."""
        html = """
        <html>
        <head><title>Unicode Test 测试</title></head>
        <body>
            <p>Unicode content: 你好世界 🌍 ñoño</p>
            <p>More unicode: café naïve résumé</p>
        </body>
        </html>
        """

        cleaner = HTMLCleaner()
        text, title = cleaner.clean_html(html)

        assert "Unicode Test 测试" in title
        assert "你好世界" in text
        assert "🌍" in text
        assert "café naïve résumé" in text
