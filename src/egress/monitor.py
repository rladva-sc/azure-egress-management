"""
Core egress monitoring functionality.
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable

from azure.core.exceptions import AzureError

from ..auth.azure_auth import AzureAuthenticator
from .metrics import EgressMetricsDefinition, get_metrics_for_resource_type
from .collector import MetricsCollector
from .storage import MetricsStorage
from ..utils.azure_utils import (
    get_resource_name, 
    get_resource_group, 
    get_resource_type,
    safe_execute_azure_operation,
    get_time_range_for_metrics
)

class EgressMonitorError(Exception):
    """Exception raised for errors in the EgressMonitor class."""
    pass

class EgressMonitor:
    """
    Monitors and analyzes Azure egress traffic.
    """
    def __init__(self, subscription_id, authenticator=None, config=None):
        """
        Initialize the egress monitor.
        
        Args:
            subscription_id (str): Azure subscription ID
            authenticator (AzureAuthenticator, optional): Authentication provider
            config (dict, optional): Configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self.subscription_id = subscription_id
        self.authenticator = authenticator or AzureAuthenticator()
        self.config = config or {}
        
        # Initialize metrics collector and storage if monitoring is enabled
        self.collector = None
        self.storage = None
        
        if self.config.get("monitoring", {}).get("enabled", True):
            # Set up storage if configured
            storage_enabled = self.config.get("storage", {}).get("enabled", True)
            if storage_enabled:
                try:
                    self.storage = MetricsStorage(self.config)
                    self.storage.initialize()
                except Exception as ex:
                    self.logger.warning(f"Failed to initialize metrics storage: {str(ex)}")
                    self.storage = None
            
            # Set up collector with storage
            self.collector = MetricsCollector(
                subscription_id=self.subscription_id,
                authenticator=self.authenticator,
                config=self.config,
                storage=self.storage
            )
        
    def get_network_resources(self, resource_type: Optional[str] = None) -> Dict[str, List]:
        """
        Get network resources in the subscription.
        
        Args:
            resource_type (str, optional): Filter by resource type (vnets, public_ips, etc.)
            
        Returns:
            dict: Collection of network resources by type
        """
        self.logger.info(f"Retrieving network resources for subscription {self.subscription_id}")
        
        # If collector is available, use it for discovery
        if self.collector:
            try:
                resources = self.collector._discover_resources()
                
                # Filter by resource type if specified
                if resource_type:
                    filtered_resources = {}
                    for rt, items in resources.items():
                        if resource_type.lower() in rt.lower():
                            filtered_resources[rt] = items
                    return filtered_resources
                else:
                    return resources
            except Exception as ex:
                self.logger.error(f"Error using collector for resource discovery: {str(ex)}")
                # Fall back to basic implementation
        
        # Basic implementation if collector not available or errored
        try:
            # Determine which resources to collect
            resources_config = self.config.get("monitoring", {}).get("resources", {})
            collect_vnets = resources_config.get("vnets", True)
            collect_pips = resources_config.get("public_ips", True)
            
            # Get network client
            network_client = self.authenticator.get_client('network', self.subscription_id)
            
            # Initialize result dictionary
            resources = {}
            
            # Get virtual networks
            if (not resource_type or "vnet" in resource_type.lower()) and collect_vnets:
                vnets = list(network_client.virtual_networks.list_all())
                self.logger.info(f"Found {len(vnets)} virtual networks")
                resources['vnets'] = vnets
            
            # Get public IPs
            if (not resource_type or "ip" in resource_type.lower()) and collect_pips:
                public_ips = list(network_client.public_ip_addresses.list_all())
                self.logger.info(f"Found {len(public_ips)} public IP addresses")
                resources['public_ips'] = public_ips
            
            return resources
            
        except Exception as ex:
            self.logger.error(f"Error retrieving network resources: {str(ex)}")
            raise EgressMonitorError(f"Failed to get network resources: {str(ex)}") from ex
    
    def get_egress_data(self, days=7, progress_callback: Optional[Callable[[float], None]] = None):
        """
        Collect egress data for the specified time period.
        
        Args:
            days (int): Number of days of data to retrieve
            progress_callback (callable, optional): Callback for progress updates
            
        Returns:
            dict: Collected egress data
        """
        self.logger.info(f"Collecting {days} days of egress data")
        
        # Use collector if available
        if self.collector:
            try:
                return self.collector.collect_metrics(days=days, progress_callback=progress_callback)
            except Exception as ex:
                self.logger.error(f"Error using collector for metrics collection: {str(ex)}")
                # Fall back to simplified implementation
        
        # Simplified implementation if collector not available or errored
        monitor_client = self.authenticator.get_client('monitor', self.subscription_id)
        network_client = self.authenticator.get_client('network', self.subscription_id)

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Basic implementation - to be expanded
        return {
            'collection_id': datetime.utcnow().strftime("%Y%m%d%H%M%S"),
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'resources': {},
            'errors': []
        }

    def analyze_egress(self, data=None):
        """
        Analyze egress patterns from collected data.
        
        Args:
            data (dict, optional): Egress data to analyze, or None to collect new data
            
        Returns:
            dict: Analysis results
        """
        if data is None:
            data = self.get_egress_data()
            
        # Basic analysis - gather statistics on collected data
        analysis = {
            'timestamp': datetime.utcnow().isoformat(),
            'subscription_id': self.subscription_id,
            'period': data.get('period', {}),
            'resource_stats': self._calculate_resource_statistics(data),
            'results': {
                'message': 'Detailed analysis to be implemented in future phase'
            }
        }
        
        return analysis
    
    def _calculate_resource_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate basic statistics for the resources in the collected data.
        
        Args:
            data: Collected metrics data
            
        Returns:
            Dictionary with resource statistics
        """
        stats = {
            'resource_count': 0,
            'resource_types': [],
            'metrics_count': 0,
            'errors_count': len(data.get('errors', [])),
            'resources_with_data': 0,
            'resources_by_type': {}
        }
        
        resources = data.get('resources', {})
        
        # Calculate statistics for each resource type
        for resource_type, resources_of_type in resources.items():
            resource_count = len(resources_of_type)
            stats['resource_count'] += resource_count
            stats['resource_types'].append(resource_type)
            
            resources_with_metrics = 0
            metrics_count_for_type = 0
            
            for resource_id, resource_data in resources_of_type.items():
                metrics = resource_data.get('metrics', {})
                metrics_count = len(metrics)
                
                if metrics_count > 0:
                    resources_with_metrics += 1
                    metrics_count_for_type += metrics_count
            
            stats['resources_by_type'][resource_type] = {
                'count': resource_count,
                'with_metrics': resources_with_metrics,
                'metrics_count': metrics_count_for_type
            }
            
            stats['resources_with_data'] += resources_with_metrics
            stats['metrics_count'] += metrics_count_for_type
        
        return stats
