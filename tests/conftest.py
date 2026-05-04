"""Pytest configuration and fixtures for omni-extractor tests."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from pydantic import BaseModel


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_http_response() -> AsyncGenerator[dict, None]:
    """Mock HTTP response fixture for testing."""
    yield {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "text": '{"message": "test response"}',
        "json": lambda: {"message": "test response"},
    }


@pytest.fixture
def mock_config_data() -> dict:
    """Mock configuration data for testing."""
    return {
        "openai": {
            "api_key": "test-api-key",
            "model": "gpt-4",
            "max_tokens": 1000,
        },
        "extraction": {
            "max_content_length": 10000,
            "timeout": 30,
        },
        "logging": {
            "level": "INFO",
            "format": "{time} {level} {message}",
        },
    }


@pytest.fixture
def sample_text_content() -> str:
    """Sample text content for testing."""
    return """
    This is a sample text content for testing extraction functionality.
    It contains multiple sentences and paragraphs to simulate real content.
    
    The content includes various elements like:
    - Bullet points
    - Multiple paragraphs
    - Different formatting
    
    This helps test the extraction capabilities of the omni-extractor.
    """


@pytest.fixture
def sample_html_content() -> str:
    """Sample HTML content for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
    </head>
    <body>
        <h1>Main Heading</h1>
        <p>This is a paragraph with <strong>bold text</strong> and <em>italic text</em>.</p>
        <ul>
            <li>First item</li>
            <li>Second item</li>
        </ul>
        <div class="content">
            <p>Nested content inside a div.</p>
        </div>
    </body>
    </html>
    """


class MockModel(BaseModel):
    """Mock Pydantic model for testing."""
    name: str
    value: int
    description: str = ""


@pytest.fixture
def mock_pydantic_model() -> type[MockModel]:
    """Mock Pydantic model class for testing."""
    return MockModel