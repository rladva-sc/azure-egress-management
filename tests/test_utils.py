"""
Tests for utility modules.
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from src.utils.config_utils import load_config, merge_configs, get_config_with_env_overrides
from src.utils.logging_utils import setup_logging


def test_merge_configs():
    """Test merging configurations."""
    base_config = {
        "logging": {
            "level": "INFO",
            "file": "base.log"
        },
        "azure": {
            "auth_method": "default",
            "use_cli": True
        }
    }
    
    override_config = {
        "logging": {
            "level": "DEBUG"
        },
        "monitoring": {
            "default_days": 14
        }
    }
    
    expected = {
        "logging": {
            "level": "DEBUG",
            "file": "base.log"
        },
        "azure": {
            "auth_method": "default",
            "use_cli": True
        },
        "monitoring": {
            "default_days": 14
        }
    }
    
    result = merge_configs(base_config, override_config)
    assert result == expected


def test_get_config_with_env_overrides():
    """Test environment variable overrides."""
    config = {
        "logging": {
            "level": "INFO"
        },
        "azure": {
            "auth_method": "default"
        }
    }
    
    with patch.dict(os.environ, {
        "AZURE_AUTH_METHOD": "browser",
        "LOG_LEVEL": "DEBUG"
    }):
        result = get_config_with_env_overrides(config)
    
    assert result["azure"]["auth_method"] == "browser"
    assert result["logging"]["level"] == "DEBUG"


@patch("builtins.open", new_callable=mock_open, read_data='{"test": "config"}')
def test_load_config(mock_file):
    """Test loading configuration from file."""
    config = load_config("dummy_path.json")
    assert config == {"test": "config"}
    mock_file.assert_called_once_with("dummy_path.json", "r")
