"""
Azure metrics definitions for egress monitoring.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta

@dataclass
class EgressMetricsDefinition:
    """Definition of a metric to be collected for egress monitoring."""
    name: str
    display_name: str
    category: str
    unit: str
    aggregation: str = "Total"
    resource_type: str = "Microsoft.Network/networkInterfaces"
    dimensions: Optional[List[str]] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        """Set defaults for optional fields."""
        if self.dimensions is None:
            self.dimensions = []
        if not self.description:
            self.description = f"{self.display_name} ({self.unit})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API calls."""
        return {
            "name": self.name,
            "aggregation": self.aggregation,
            "resourceType": self.resource_type,
            "unit": self.unit
        }

class EgressMetricRegistry:
    """Registry of available metrics for different Azure resource types."""
    
    @staticmethod
    def get_network_interface_metrics() -> Dict[str, EgressMetricsDefinition]:
        """Get metrics for network interfaces."""
        return {
            "bytes_out": EgressMetricsDefinition(
                name="BytesOutPerSecond",
                display_name="Outbound Traffic",
                category="Traffic",
                unit="BytesPerSecond",
                aggregation="Average",
                resource_type="Microsoft.Network/networkInterfaces",
                description="Rate of bytes transmitted by the network interface"
            ),
            "bytes_in": EgressMetricsDefinition(
                name="BytesInPerSecond",
                display_name="Inbound Traffic",
                category="Traffic",
                unit="BytesPerSecond",
                aggregation="Average",
                resource_type="Microsoft.Network/networkInterfaces",
                description="Rate of bytes received by the network interface"
            ),
            "packets_out": EgressMetricsDefinition(
                name="PacketsOutPerSecond",
                display_name="Outbound Packets",
                category="Traffic",
                unit="CountPerSecond",
                aggregation="Average",
                resource_type="Microsoft.Network/networkInterfaces",
                description="Rate of packets transmitted by the network interface"
            ),
            "packets_in": EgressMetricsDefinition(
                name="PacketsInPerSecond",
                display_name="Inbound Packets",
                category="Traffic",
                unit="CountPerSecond",
                aggregation="Average",
                resource_type="Microsoft.Network/networkInterfaces",
                description="Rate of packets received by the network interface"
            )
        }
    
    @staticmethod
    def get_virtual_machine_metrics() -> Dict[str, EgressMetricsDefinition]:
        """Get metrics for virtual machines."""
        return {
            "network_out": EgressMetricsDefinition(
                name="Network Out Total",
                display_name="Network Out Total",
                category="Network",
                unit="Bytes",
                aggregation="Total",
                resource_type="Microsoft.Compute/virtualMachines",
                description="Total bytes sent over all network interfaces by the VM"
            ),
            "network_in": EgressMetricsDefinition(
                name="Network In Total",
                display_name="Network In Total",
                category="Network",
                unit="Bytes",
                aggregation="Total",
                resource_type="Microsoft.Compute/virtualMachines",
                description="Total bytes received over all network interfaces by the VM"
            ),
            "network_out_rate": EgressMetricsDefinition(
                name="Network Out",
                display_name="Network Out Rate",
                category="Network",
                unit="BytesPerSecond",
                aggregation="Average",
                resource_type="Microsoft.Compute/virtualMachines",
                description="Average rate of bytes sent over all network interfaces by the VM"
            ),
            "network_in_rate": EgressMetricsDefinition(
                name="Network In",
                display_name="Network In Rate",
                category="Network",
                unit="BytesPerSecond",
                aggregation="Average",
                resource_type="Microsoft.Compute/virtualMachines",
                description="Average rate of bytes received over all network interfaces by the VM"
            )
        }
    
    @staticmethod
    def get_load_balancer_metrics() -> Dict[str, EgressMetricsDefinition]:
        """Get metrics for load balancers."""
        return {
            "bytes_out": EgressMetricsDefinition(
                name="ByteCount",
                display_name="Byte Count",
                category="Traffic",
                unit="Bytes",
                aggregation="Total",
                resource_type="Microsoft.Network/loadBalancers",
                description="Total bytes transmitted via the load balancer",
                dimensions=["Direction"]
            ),
            "packet_count": EgressMetricsDefinition(
                name="PacketCount",
                display_name="Packet Count",
                category="Traffic",
                unit="Count",
                aggregation="Total",
                resource_type="Microsoft.Network/loadBalancers",
                description="Total packets transmitted via the load balancer",
                dimensions=["Direction"]
            ),
            "snat_connection_count": EgressMetricsDefinition(
                name="SnatConnectionCount",
                display_name="SNAT Connection Count",
                category="Connections",
                unit="Count",
                aggregation="Average",
                resource_type="Microsoft.Network/loadBalancers",
                description="Total SNAT connections"
            )
        }
    
    @staticmethod
    def get_app_service_metrics() -> Dict[str, EgressMetricsDefinition]:
        """Get metrics for App Services."""
        return {
            "data_out": EgressMetricsDefinition(
                name="BytesSent",
                display_name="Data Out",
                category="Network",
                unit="Bytes",
                aggregation="Total",
                resource_type="Microsoft.Web/sites",
                description="Total bytes sent from App Service"
            ),
            "data_in": EgressMetricsDefinition(
                name="BytesReceived",
                display_name="Data In",
                category="Network",
                unit="Bytes",
                aggregation="Total",
                resource_type="Microsoft.Web/sites",
                description="Total bytes received by App Service"
            )
        }

    @staticmethod
    def get_metrics_for_resource_type(resource_type: str) -> Dict[str, EgressMetricsDefinition]:
        """
        Get metrics definitions for a specific resource type.
        
        Args:
            resource_type: The Azure resource type
            
        Returns:
            Dictionary of metric definitions
        """
        resource_type = resource_type.lower()
        
        if "virtualnetwork" in resource_type:
            # Virtual networks don't have direct metrics, return empty
            return {}
        elif "networkinterface" in resource_type:
            return EgressMetricRegistry.get_network_interface_metrics()
        elif "virtualmachine" in resource_type:
            return EgressMetricRegistry.get_virtual_machine_metrics()
        elif "loadbalancer" in resource_type:
            return EgressMetricRegistry.get_load_balancer_metrics()
        elif "sites" in resource_type or "webapp" in resource_type:
            return EgressMetricRegistry.get_app_service_metrics()
        else:
            # Unknown resource type
            return {}

def get_metrics_for_resource_type(resource_type: str) -> Dict[str, EgressMetricsDefinition]:
    """
    Get metrics definitions for a specific resource type.
    
    Args:
        resource_type: The Azure resource type
        
    Returns:
        Dictionary of metric definitions
    """
    return EgressMetricRegistry.get_metrics_for_resource_type(resource_type)
