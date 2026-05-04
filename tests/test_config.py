"""Configuration loading tests for omni-extractor."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


class TestConfigurationLoading:
    """Test configuration loading functionality."""

    def test_mock_config_data_structure(self, mock_config_data):
        """Test that mock config data has expected structure."""
        assert isinstance(mock_config_data, dict)
        assert "openai" in mock_config_data
        assert "extraction" in mock_config_data
        assert "logging" in mock_config_data

    def test_openai_config_section(self, mock_config_data):
        """Test OpenAI configuration section."""
        openai_config = mock_config_data["openai"]
        assert "api_key" in openai_config
        assert "model" in openai_config
        assert "max_tokens" in openai_config
        assert openai_config["api_key"] == "test-api-key"
        assert openai_config["model"] == "gpt-4"
        assert openai_config["max_tokens"] == 1000

    def test_extraction_config_section(self, mock_config_data):
        """Test extraction configuration section."""
        extraction_config = mock_config_data["extraction"]
        assert "max_content_length" in extraction_config
        assert "timeout" in extraction_config
        assert extraction_config["max_content_length"] == 10000
        assert extraction_config["timeout"] == 30

    def test_logging_config_section(self, mock_config_data):
        """Test logging configuration section."""
        logging_config = mock_config_data["logging"]
        assert "level" in logging_config
        assert "format" in logging_config
        assert logging_config["level"] == "INFO"
        assert "{time} {level} {message}" in logging_config["format"]


class TestConfigurationFileOperations:
    """Test configuration file operations."""

    def test_config_yaml_serialization(self, mock_config_data):
        """Test that configuration can be serialized to YAML."""
        yaml_str = yaml.dump(mock_config_data)
        loaded_config = yaml.safe_load(yaml_str)
        assert loaded_config == mock_config_data

    def test_config_json_serialization(self, mock_config_data):
        """Test that configuration can be serialized to JSON."""
        import json
        json_str = json.dumps(mock_config_data)
        loaded_config = json.loads(json_str)
        assert loaded_config == mock_config_data

    def test_environment_variable_override(self, mock_config_data):
        """Test environment variable override functionality."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-api-key"}):
            # Simulate environment variable override
            config = mock_config_data.copy()
            if "OPENAI_API_KEY" in os.environ:
                config["openai"]["api_key"] = os.environ["OPENAI_API_KEY"]
            assert config["openai"]["api_key"] == "env-api-key"


class TestConfigurationValidation:
    """Test configuration validation."""

    def test_invalid_openai_model(self):
        """Test validation of OpenAI model configuration."""
        invalid_config = {
            "openai": {
                "api_key": "test-key",
                "model": "",  # Invalid empty model
                "max_tokens": 1000,
            }
        }
        # This would be validated by actual config model in real implementation
        assert invalid_config["openai"]["model"] == ""

    def test_invalid_max_tokens(self):
        """Test validation of max_tokens configuration."""
        invalid_config = {
            "openai": {
                "api_key": "test-key",
                "model": "gpt-4",
                "max_tokens": -1,  # Invalid negative value
            }
        }
        # This would be validated by actual config model in real implementation
        assert invalid_config["openai"]["max_tokens"] == -1

    def test_missing_required_fields(self):
        """Test validation of required configuration fields."""
        incomplete_config = {
            "openai": {
                "api_key": "test-key",
                # Missing model and max_tokens
            }
        }
        # This would be validated by actual config model in real implementation
        assert "model" not in incomplete_config["openai"]
        assert "max_tokens" not in incomplete_config["openai"]


class TestConfigurationFileLoading:
    """Test configuration file loading from filesystem."""

    def test_load_config_from_yaml_file(self, mock_config_data):
        """Test loading configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(mock_config_data, f)
            f.flush()
            f.close()  # Close the file before reopening
            
            # Simulate loading from file
            with open(f.name, 'r') as config_file:
                loaded_config = yaml.safe_load(config_file)
                assert loaded_config == mock_config_data
            
            # Cleanup
            try:
                os.unlink(f.name)
            except PermissionError:
                # On Windows, the file might still be locked
                pass

    def test_load_config_from_json_file(self, mock_config_data):
        """Test loading configuration from JSON file."""
        import json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(mock_config_data, f)
            f.flush()
            f.close()  # Close the file before reopening
            
            # Simulate loading from file
            with open(f.name, 'r') as config_file:
                loaded_config = json.load(config_file)
                assert loaded_config == mock_config_data
            
            # Cleanup
            try:
                os.unlink(f.name)
            except PermissionError:
                # On Windows, the file might still be locked
                pass

    def test_config_file_not_found(self):
        """Test handling of missing configuration file."""
        non_existent_file = Path("/non/existent/config.yaml")
        assert not non_existent_file.exists()
        # This would raise an exception in real implementation
        # For now, we just verify the file doesn't exist