"""
Tests for the egress monitoring module.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.egress.monitor import EgressMonitor, EgressMonitorError

def test_monitor_init(mock_authenticator, sample_config):
    """Test monitor initialization."""
    subscription_id = "test-subscription-id"
    monitor = EgressMonitor(subscription_id, mock_authenticator, sample_config)
    
    assert monitor.subscription_id == subscription_id
    assert monitor.authenticator == mock_authenticator
    assert monitor.config == sample_config
    assert hasattr(monitor, 'collector')
    assert hasattr(monitor, 'storage')
    assert hasattr(monitor, 'logger')

@patch('src.egress.monitor.MetricsCollector')
@patch('src.egress.monitor.MetricsStorage')
def test_monitor_init_with_components(mock_storage_class, mock_collector_class, mock_authenticator):
    """Test monitor initialization with storage and collector components."""
    # Setup mocks
    mock_storage = MagicMock()
    mock_collector = MagicMock()
    mock_storage_class.return_value = mock_storage
    mock_collector_class.return_value = mock_collector
    
    # Create monitor
    subscription_id = "test-subscription-id"
    config = {"monitoring": {"enabled": True}}
    monitor = EgressMonitor(subscription_id, mock_authenticator, config)
    
    # Verify components were initialized
    assert monitor.storage == mock_storage
    assert monitor.collector == mock_collector
    mock_storage_class.assert_called_once()
    mock_collector_class.assert_called_once()

def test_get_network_resources_with_collector(mock_authenticator):
    """Test getting network resources using collector."""
    # Setup mock collector
    mock_collector = MagicMock()
    mock_resources = {
        'vnets': [MagicMock(), MagicMock()],
        'public_ips': [MagicMock()]
    }
    mock_collector.discover_resources.return_value = mock_resources
    
    # Create monitor with mock collector
    subscription_id = "test-subscription-id"
    monitor = EgressMonitor(subscription_id, mock_authenticator)
    monitor.collector = mock_collector
    
    # Get network resources
    resources = monitor.get_network_resources()
    
    # Verify
    assert resources == mock_resources
    mock_collector.discover_resources.assert_called_once_with(None)

def test_get_network_resources_without_collector(mock_authenticator):
    """Test getting network resources without collector (fallback)."""
    # Setup mock network client
    network_client = mock_authenticator.get_client('network')
    
    # Mock list methods
    network_client.virtual_networks.list_all.return_value = [MagicMock(), MagicMock()]
    network_client.public_ip_addresses.list_all.return_value = [MagicMock()]
    network_client.network_interfaces.list_all.return_value = [MagicMock(), MagicMock(), MagicMock()]
    network_client.application_gateways.list_all.return_value = [MagicMock()]
    
    # Create monitor without collector
    subscription_id = "test-subscription-id"
    monitor = EgressMonitor(subscription_id, mock_authenticator)
    monitor.collector = None
    
    # Get network resources
    resources = monitor.get_network_resources()
    
    # Verify
    assert 'vnets' in resources
    assert 'public_ips' in resources
    assert 'nics' in resources
    assert 'app_gateways' in resources
    assert len(resources['vnets']) == 2
    assert len(resources['public_ips']) == 1
    assert len(resources['nics']) == 3
    assert len(resources['app_gateways']) == 1

@patch('src.egress.monitor.MetricsCollector')
def test_get_egress_data_with_collector(mock_collector_class, mock_authenticator):
    """Test getting egress data using collector."""
    # Setup mock collector
    mock_collector = MagicMock()
    mock_data = {
        "resources": {
            "Microsoft.Compute/virtualMachines": {
                "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1": {
                    "metrics": {"BytesOut": {"values": [100, 200, 300]}}
                }
            }
        }
    }
    mock_collector.collect_metrics.return_value = mock_data
    mock_collector_class.return_value = mock_collector
    
    # Create monitor
    subscription_id = "test-subscription-id"
    config = {"monitoring": {"enabled": True}}
    monitor = EgressMonitor(subscription_id, mock_authenticator, config)
    
    # Get egress data
    data = monitor.get_egress_data(days=7)
    
    # Verify
    assert data == mock_data
    mock_collector.collect_metrics.assert_called_once()
    args = mock_collector.collect_metrics.call_args[0]
    assert len(args) >= 1
    assert args[0] == 7  # days parameter
