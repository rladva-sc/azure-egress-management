"""
Tests for the metrics module.
"""
import pytest
from src.egress.metrics import (
    EgressMetricsDefinition, 
    EgressMetricRegistry,
    get_metrics_for_resource_type
)

def test_metrics_definition_initialization():
    """Test the initialization of EgressMetricsDefinition."""
    metric = EgressMetricsDefinition(
        name="TestMetric",
        display_name="Test Metric",
        category="Test",
        unit="Count"
    )
    
    assert metric.name == "TestMetric"
    assert metric.display_name == "Test Metric"
    assert metric.category == "Test"
    assert metric.unit == "Count"
    assert metric.aggregation == "Total"  # default
    assert metric.resource_type == "Microsoft.Network/networkInterfaces"  # default
    assert metric.dimensions == []  # default
    assert metric.description == "Test Metric (Count)"  # auto-generated

def test_metrics_definition_custom_values():
    """Test EgressMetricsDefinition with custom values."""
    metric = EgressMetricsDefinition(
        name="CustomMetric",
        display_name="Custom Metric",
        category="Custom",
        unit="Bytes",
        aggregation="Average",
        resource_type="Microsoft.Compute/virtualMachines",
        dimensions=["Direction"],
        description="Custom description"
    )
    
    assert metric.name == "CustomMetric"
    assert metric.display_name == "Custom Metric"
    assert metric.aggregation == "Average"
    assert metric.resource_type == "Microsoft.Compute/virtualMachines"
    assert metric.dimensions == ["Direction"]
    assert metric.description == "Custom description"

def test_metrics_definition_to_dict():
    """Test the to_dict method."""
    metric = EgressMetricsDefinition(
        name="TestMetric",
        display_name="Test Metric",
        category="Test",
        unit="Count",
        aggregation="Maximum"
    )
    
    result = metric.to_dict()
    
    assert result["name"] == "TestMetric"
    assert result["aggregation"] == "Maximum"
    assert result["resourceType"] == "Microsoft.Network/networkInterfaces"
    assert result["unit"] == "Count"
    
def test_network_interface_metrics():
    """Test retrieving network interface metrics."""
    metrics = EgressMetricRegistry.get_network_interface_metrics()
    
    assert len(metrics) == 4
    assert "bytes_out" in metrics
    assert "bytes_in" in metrics
    assert "packets_out" in metrics
    assert "packets_in" in metrics
    
    # Check specific metric
    assert metrics["bytes_out"].name == "BytesOutPerSecond"
    assert metrics["bytes_out"].unit == "BytesPerSecond"

def test_virtual_machine_metrics():
    """Test retrieving VM metrics."""
    metrics = EgressMetricRegistry.get_virtual_machine_metrics()
    
    assert len(metrics) == 4
    assert "network_out" in metrics
    assert "network_in" in metrics
    
    # Check specific metric
    assert metrics["network_out"].resource_type == "Microsoft.Compute/virtualMachines"

def test_load_balancer_metrics():
    """Test retrieving load balancer metrics."""
    metrics = EgressMetricRegistry.get_load_balancer_metrics()
    
    assert len(metrics) == 3
    assert "bytes_out" in metrics
    assert "packet_count" in metrics
    assert "snat_connection_count" in metrics
    
    # Check dimensions
    assert "Direction" in metrics["bytes_out"].dimensions

def test_get_metrics_for_resource_type():
    """Test getting metrics by resource type."""
    # Network interface
    nic_metrics = get_metrics_for_resource_type("Microsoft.Network/networkInterfaces")
    assert len(nic_metrics) == 4
    
    # VM
    vm_metrics = get_metrics_for_resource_type("Microsoft.Compute/virtualMachines")
    assert len(vm_metrics) == 4
    
    # Virtual network - no direct metrics
    vnet_metrics = get_metrics_for_resource_type("Microsoft.Network/virtualNetworks")
    assert len(vnet_metrics) == 0
    
    # Case insensitivity
    lb_metrics = get_metrics_for_resource_type("microsoft.network/loadbalancers")
    assert len(lb_metrics) == 3
    
    # Unknown type
    unknown_metrics = get_metrics_for_resource_type("Unknown/ResourceType")
    assert len(unknown_metrics) == 0
