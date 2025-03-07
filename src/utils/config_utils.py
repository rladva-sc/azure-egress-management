"""
Configuration utilities for Azure Egress Management.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from file.
    
    Args:
        config_path (str, optional): Path to config file. If None, uses default.
        
    Returns:
        dict: Configuration dictionary
    """
    if not config_path:
        # Use default config path
        config_path = str(Path(__file__).parent.parent.parent / "config" / "config.json")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config
    except Exception as ex:
        print(f"Error loading config from {config_path}: {ex}")
        # Fall back to default config
        from ...config.settings import DEFAULT_CONFIG
        return DEFAULT_CONFIG.copy()


def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two configuration dictionaries.
    
    Args:
        base_config (dict): Base configuration
        override_config (dict): Configuration to override base
        
    Returns:
        dict: Merged configuration
    """
    result = base_config.copy()
    
    for key, value in override_config.items():
        if (
            key in result and 
            isinstance(result[key], dict) and 
            isinstance(value, dict)
        ):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result


def get_config_with_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Override configuration with environment variables.
    
    Args:
        config (dict): Base configuration
        
    Returns:
        dict: Configuration with environment variable overrides
    """
    result = config.copy()
    
    # Azure auth settings
    if os.environ.get("AZURE_AUTH_METHOD"):
        if "azure" not in result:
            result["azure"] = {}
        result["azure"]["auth_method"] = os.environ.get("AZURE_AUTH_METHOD")
    
    if os.environ.get("AZURE_USE_CLI"):
        if "azure" not in result:
            result["azure"] = {}
        result["azure"]["use_cli"] = os.environ.get("AZURE_USE_CLI").lower() == "true"
    
    # Logging settings
    if os.environ.get("LOG_LEVEL"):
        if "logging" not in result:
            result["logging"] = {}
        result["logging"]["level"] = os.environ.get("LOG_LEVEL")
    
    return result
