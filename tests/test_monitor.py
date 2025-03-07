"""
Tests for the monitoring module.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from src.egress.monitor import EgressMonitor


def test_egress_monitor_initialization():
    """Test that EgressMonitor initializes correctly."""
    mock_auth = MagicMock()
    monitor = EgressMonitor("sub-123", mock_auth)
    
    assert monitor.subscription_id == "sub-123"
    assert monitor.authenticator == mock_auth


def test_get_network_resources():
    """Test retrieving network resources."""
    # Create mock objects
    mock_auth = MagicMock()
    mock_network_client = MagicMock()
    mock_vnet_list = [MagicMock(), MagicMock()]
    mock_public_ip_list = [MagicMock()]
    
    # Configure mocks
    mock_auth.get_client.return_value = mock_network_client
    mock_network_client.virtual_networks.list_all.return_value = mock_vnet_list
    mock_network_client.public_ip_addresses.list_all.return_value = mock_public_ip_list
    
    # Create the monitor and call the method
    monitor = EgressMonitor("sub-123", mock_auth)
    resources = monitor.get_network_resources()
    
    # Verify results
    assert resources['vnets'] == mock_vnet_list
    assert len(resources['vnets']) == 2
    assert resources['public_ips'] == mock_public_ip_list
    assert len(resources['public_ips']) == 1
    
    # Verify the mock was called correctly
    mock_auth.get_client.assert_called_once_with('network', 'sub-123')


def test_analyze_egress():
    """Test analyze_egress with provided data."""
    mock_auth = MagicMock()
    monitor = EgressMonitor("sub-123", mock_auth)
    
    # Create test data
    test_data = {
        'period': {
            'start': '2023-01-01T00:00:00',
            'end': '2023-01-07T00:00:00'
        },
        'data': {
            'collected': True,
            'message': 'Test data'
        }
    }
    
    # Call the method
    result = monitor.analyze_egress(test_data)
    
    # Verify the result structure
    assert 'timestamp' in result
    assert 'subscription_id' in result
    assert result['subscription_id'] == 'sub-123'
    assert 'results' in result
