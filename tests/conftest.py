"""
Common test fixtures for all test modules.
"""
import os
import json
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.auth.azure_auth import AzureAuthenticator
from src.egress.storage import MetricsStorage
from src.egress.monitor import EgressMonitor
from src.egress.trend_analysis import TrendAnalyzer
from src.egress.cost_analysis import CostAnalyzer
from src.egress.anomaly_detection import AnomalyDetector

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "azure": {
            "auth_method": "environment",
            "tenant_id": "test-tenant-id",
            "subscription_id": "test-subscription-id"
        },
        "storage": {
            "data_dir": "./tests/data",
            "raw_subdir": "raw",
            "processed_subdir": "processed"
        },
        "monitoring": {
            "enabled": True,
            "interval_minutes": 60,
            "metrics": ["BytesOut", "BytesSent", "NetworkOut"]
        },
        "analysis": {
            "trends": {
                "significant_change_threshold": 10.0,
                "min_data_points": 3,
                "lookback_window": 7
            },
            "cost": {
                "threshold_warning": 100.0,
                "threshold_critical": 500.0,
                "currency": "USD"
            },
            "anomaly_detection": {
                "zscore_threshold": 3.0,
                "min_data_points": 5,
                "mad_threshold": 3.5
            }
        }
    }

@pytest.fixture
def mock_authenticator():
    """Mock Azure authenticator."""
    auth = MagicMock(spec=AzureAuthenticator)
    
    # Mock client returns
    mock_network_client = MagicMock()
    mock_resource_client = MagicMock()
    mock_monitor_client = MagicMock()
    
    # Configure the get_client method to return different mock clients
    def get_client_side_effect(client_type, *args, **kwargs):
        if client_type == 'network':
            return mock_network_client
        elif client_type == 'resource':
            return mock_resource_client
        elif client_type == 'monitor':
            return mock_monitor_client
        else:
            return MagicMock()
    
    auth.get_client.side_effect = get_client_side_effect
    
    return auth

@pytest.fixture
def sample_metrics_dataframe():
    """Create a sample metrics DataFrame for testing."""
    # Create timestamps - hourly for 3 days
    timestamps = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(72)]
    
    data = []
    resources = ['vm1', 'vm2', 'appservice1']
    resource_types = {
        'vm1': 'Microsoft.Compute/virtualMachines', 
        'vm2': 'Microsoft.Compute/virtualMachines',
        'appservice1': 'Microsoft.Web/sites'
    }
    
    for resource_name in resources:
        resource_id = f"/subscriptions/sub1/resourceGroups/rg1/providers/{resource_types[resource_name]}/{resource_name}"
        
        for ts in timestamps:
            # Add BytesOut metric (egress data)
            hour_factor = 1.0
            if 8 <= ts.hour <= 17:  # Business hours
                hour_factor = 2.0
                
            # Add day factor (weekends lower)
            day_factor = 0.7 if ts.weekday() >= 5 else 1.0
            
            # Base value with some randomness
            base_value = 100000000 * hour_factor * day_factor  # 100MB base
            value = base_value * (0.8 + (0.4 * (hash(f"{resource_name}{ts}") % 1000) / 1000))
            
            data.append({
                'timestamp': ts,
                'resource_id': resource_id,
                'resource_name': resource_name,
                'resource_type': resource_types[resource_name],
                'metric_name': 'BytesOut',
                'display_name': 'Bytes Out',
                'unit': 'Bytes',
                'value': value,
                'resource_group': 'rg1',
                'location': 'eastus'
            })
    
    return pd.DataFrame(data)

@pytest.fixture
def sample_metrics_data():
    """Sample metrics data for storage tests."""
    return {
        "metadata": {
            "collection_id": "20230101120000",
            "timestamp": "2023-01-01T12:00:00",
            "subscription_id": "test-subscription-id"
        },
        "resources": {
            "Microsoft.Compute/virtualMachines": {
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1": {
                    "name": "vm1",
                    "resource_group": "rg1",
                    "location": "eastus",
                    "metrics": {
                        "BytesOut": {
                            "name": "BytesOut",
                            "display_name": "Bytes Out",
                            "unit": "Bytes",
                            "times": ["2023-01-01T11:00:00", "2023-01-01T12:00:00"],
                            "values": [123456789, 234567890]
                        }
                    }
                }
            }
        },
        "errors": []
    }

@pytest.fixture
def mock_storage():
    """Mock storage class for testing."""
    storage = MagicMock(spec=MetricsStorage)
    storage.retrieve_metrics.return_value = {
        "metadata": {
            "collection_id": "20230101120000",
            "timestamp": "2023-01-01T12:00:00"
        },
        "resources": {}
    }
    return storage
