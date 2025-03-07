
"""
Tests for Azure utility functions.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.utils.azure_utils import (
    get_resource_name,
    get_resource_group,
    get_resource_type,
    get_subscription_from_resource_id,
    format_resource_id_for_metrics_query,
    safe_execute_azure_operation,
    get_time_range_for_metrics,
    batch_list_generator
)
from azure.core.exceptions import HttpResponseError
from azure.mgmt.monitor.models import ErrorResponseException

def test_get_resource_name():
    """Test extracting resource name from ID."""
    resource_id = "/subscriptions/sub123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
    assert get_resource_name(resource_id) == "vnet1"
    
    # Empty ID
    assert get_resource_name("") == "unknown"
    
    # None ID
    assert get_resource_name(None) == "unknown"

def test_get_resource_group():
    """Test extracting resource group from ID."""
    resource_id = "/subscriptions/sub123/resourceGroups/my-rg/providers/Microsoft.Network/virtualNetworks/vnet1"
    assert get_resource_group(resource_id) == "my-rg"
    
    # No resource group
    assert get_resource_group("/subscriptions/sub123") == "unknown"
    
    # Empty ID
    assert get_resource_group("") == "unknown"

def test_get_resource_type():
    """Test extracting resource type from ID."""
    resource_id = "/subscriptions/sub123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
    assert get_resource_type(resource_id) == "Microsoft.Network/virtualNetworks"
    
    # No provider
    assert get_resource_type("/subscriptions/sub123") == "unknown"
    
    # Empty ID
    assert get_resource_type("") == "unknown"

def test_get_subscription_from_resource_id():
    """Test extracting subscription ID from resource ID."""
    resource_id = "/subscriptions/sub123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
    assert get_subscription_from_resource_id(resource_id) == "sub123"
    
    # No subscription
    assert get_subscription_from_resource_id("/providers/Microsoft.Network") == "unknown"
    
    # Empty ID
    assert get_subscription_from_resource_id("") == "unknown"

def test_format_resource_id_for_metrics_query():
    """Test formatting resource ID for metrics queries."""
    resource_id = "/subscriptions/sub123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
    assert format_resource_id_for_metrics_query(resource_id) == resource_id
    
    # With whitespace
    assert format_resource_id_for_metrics_query(" " + resource_id + " ") == resource_id

def test_safe_execute_azure_operation_success():
    """Test successful execution of an Azure operation."""
    mock_operation = MagicMock(return_value="success")
    
    result, error = safe_execute_azure_operation("test_op", mock_operation, "arg1", kwarg1="value1")
    
    assert result == "success"
    assert error is None
    mock_operation.assert_called_once_with("arg1", kwarg1="value1")

def test_safe_execute_azure_operation_http_error():
    """Test handling HTTP errors in Azure operations."""
    mock_error = HttpResponseError(message="Test HTTP error")
    mock_operation = MagicMock(side_effect=mock_error)
    
    result, error = safe_execute_azure_operation("test_op", mock_operation)
    
    assert result is None
    assert "HTTP error in test_op" in error
    assert "Test HTTP error" in error

def test_safe_execute_azure_operation_azure_error():
    """Test handling ErrorResponseException in Azure operations."""
    mock_error = ErrorResponseException(message="Test Azure error")
    mock_operation = MagicMock(side_effect=mock_error)
    
    result, error = safe_execute_azure_operation("test_op", mock_operation)
    
    assert result is None
    assert "Azure error in test_op" in error

def test_safe_execute_azure_operation_general_exception():
    """Test handling general exceptions in Azure operations."""
    mock_operation = MagicMock(side_effect=ValueError("Test value error"))
    
    result, error = safe_execute_azure_operation("test_op", mock_operation)
    
    assert result is None
    assert "Unexpected error in test_op" in error
    assert "Test value error" in error

def test_get_time_range_for_metrics():
    """Test getting time range for metrics."""
    start_time, end_time = get_time_range_for_metrics(7)
    
    assert isinstance(start_time, datetime)
    assert isinstance(end_time, datetime)
    # Should be 7 days apart (give or take a second for test execution time)
    delta = end_time - start_time
    assert delta.days == 7
    assert 0 <= delta.seconds < 5  # Allow a few seconds of test execution time

def test_batch_list_generator():
    """Test the batch list generator."""
    # Mock collection function that returns pages with continuation tokens
    class MockPage:
        def __init__(self, items, continuation=None):
            self._items = items
            self.continuation_token = continuation
            
        def __iter__(self):
            return iter(self._items)
    
    # Create a mock that returns different pages with continuation tokens
    mock_fn = MagicMock()
    mock_fn.side_effect = [
        MockPage(["item1", "item2"], "token1"),
        MockPage(["item3", "item4"], "token2"),
        MockPage(["item5", "item6"], None)  # No more pages
    ]
    
    # Use the generator
    results = list(batch_list_generator(mock_fn, max_batch_size=2, param="value"))
    
    # Check the results
    assert results == ["item1", "item2", "item3", "item4", "item5", "item6"]
    
    # Check the function calls
    assert mock_fn.call_count == 3
    mock_fn.assert_any_call(top=2, param="value")
    mock_fn.assert_any_call(top=2, param="value", skip_token="token1")
    mock_fn.assert_any_call(top=2, param="value", skip_token="token2")
