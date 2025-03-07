"""
Pytest configuration for Azure Egress Management tests.
"""
import os
import sys
import pytest
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "logging": {
            "level": "DEBUG",
            "file": "test_log.log"
        },
        "azure": {
            "auth_method": "default",
            "use_cli": True
        },
        "monitoring": {
            "default_days": 7,
            "resources": {
                "virtual_machines": True,
                "app_services": True
            }
        }
    }

@pytest.fixture
def mock_credential():
    """Mock Azure credential for testing."""
    class MockCredential:
        def get_token(self, *args, **kwargs):
            return {"token": "fake-token", "expires_on": 9999999999}
    return MockCredential()
