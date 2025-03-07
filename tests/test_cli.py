"""
Tests for the CLI module.
"""
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from src.cli import app

runner = CliRunner()


@pytest.fixture
def mock_authenticator():
    """Create a mock authenticator."""
    mock = MagicMock()
    mock.credential = MagicMock()
    return mock


@pytest.fixture
def mock_monitor():
    """Create a mock monitor."""
    mock = MagicMock()
    mock.get_network_resources.return_value = {
        "vnets": ["vnet1", "vnet2"],
        "public_ips": ["ip1"]
    }
    mock.get_egress_data.return_value = {"data": "test"}
    mock.analyze_egress.return_value = {"results": "analyzed"}
    return mock


@patch('src.cli.Path')
@patch('src.cli.AzureAuthenticator')
@patch('src.cli.EgressMonitor')
def test_monitor_command(mock_monitor_class, mock_auth_class, mock_path, 
                         mock_authenticator, mock_monitor):
    """Test the monitor command."""
    # Configure mocks
    mock_auth_class.return_value = mock_authenticator
    mock_monitor_class.return_value = mock_monitor
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance
    mock_path_instance.parent.parent.__truediv__.return_value = mock_path_instance
    
    # Call the CLI command
    with patch('src.cli.load_config', return_value={}):
        with patch('src.cli.open', MagicMock()):
            result = runner.invoke(app, ["monitor", "--subscription", "sub-123"])
    
    # Verify command executed without errors
    assert result.exit_code == 0
    
    # Verify the right methods were called
    mock_auth_class.assert_called_once()
    mock_monitor_class.assert_called_once_with("sub-123", mock_authenticator, {})
    mock_monitor.get_network_resources.assert_called_once()
    mock_monitor.get_egress_data.assert_called_once()
    mock_monitor.analyze_egress.assert_called_once()
