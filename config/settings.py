"""
Default configuration settings for Azure Egress Management.
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
for dir_path in [DATA_DIR, LOGS_DIR]:
    dir_path.mkdir(exist_ok=True)

# Default settings
DEFAULT_CONFIG = {
    "logging": {
        "level": "INFO",
        "file": str(LOGS_DIR / "egress_management.log")
    },
    "azure": {
        "auth_method": "default",  # 'default', 'browser', 'service_principal'
        "use_cli": True
    },
    "monitoring": {
        "default_days": 7,
        "resources": {
            "virtual_machines": True,
            "app_services": True,
            "vnets": True,
            "load_balancers": True,
            "public_ips": True
        },
        "metrics": {
            "egress_bytes": True, 
            "egress_packets": True,
            "active_connections": True
        }
    },
    "reporting": {
        "output_format": "json",  # 'json', 'csv', 'table'
        "default_path": str(DATA_DIR / "reports")
    }
}

def get_config():
    """Get configuration with environment variable overrides."""
    config = DEFAULT_CONFIG.copy()
    
    # Override with environment variables if present
    if os.environ.get("AZURE_AUTH_METHOD"):
        config["azure"]["auth_method"] = os.environ.get("AZURE_AUTH_METHOD")
    
    if os.environ.get("AZURE_USE_CLI"):
        config["azure"]["use_cli"] = os.environ.get("AZURE_USE_CLI").lower() == "true"
    
    return config
