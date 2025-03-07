"""
Metrics collection functionality for Azure egress monitoring.
"""
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
import threading
import queue

from azure.mgmt.monitor import MonitorManagementClient
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError

from ..auth.azure_auth import AzureAuthenticator
from .metrics import EgressMetricsDefinition, get_metrics_for_resource_type
from .storage import MetricsStorage
from ..utils.azure_utils import (
    get_resource_name, 
    get_resource_group,
    get_resource_type,
    format_resource_id_for_metrics_query,
    safe_execute_azure_operation,
    get_time_range_for_metrics
)


class MetricsCollectorError(Exception):
    """Exception raised for errors in the MetricsCollector class."""
    pass


class MetricsCollector:
    """
    Collects metrics from Azure resources for egress monitoring.
    """
    def __init__(
        self, 
        subscription_id: str,
        authenticator: AzureAuthenticator,
        config: Dict[str, Any] = None,
        storage: Optional[MetricsStorage] = None
    ):
        """
        Initialize the collector.
        
        Args:
            subscription_id: Azure subscription ID to monitor
            authenticator: Authentication provider for Azure API access
            config: Configuration settings
            storage: Optional storage for persisting metrics
        """
        self.logger = logging.getLogger(__name__)
        self.subscription_id = subscription_id
        self.authenticator = authenticator
        self.config = config or {}
        self.storage = storage
        
        # Rate limiting configuration
        self.rate_limit = self.config.get("metrics", {}).get("rate_limit", 12)  # requests per second
        self.rate_limit_sleep = 1.0 / self.rate_limit if self.rate_limit > 0 else 0
        
        # Thread safety for concurrent collection
        self._lock = threading.RLock()
        self._collection_queue = queue.Queue()
        self._results = {}
        self._errors = []
        
    def _get_monitor_client(self) -> MonitorManagementClient:
        """Get or create a Monitor Management client."""
        return self.authenticator.get_client('monitor', self.subscription_id)
    
    def collect_metrics(
        self, 
        resources: Optional[Dict[str, List]] = None,
        days: int = 7,
        granularity: str = "PT1H",  # ISO8601 duration format: PT1H = 1 hour
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """
        Collect metrics for the specified resources.
        
        Args:
            resources: Dictionary of resources by type. If None, resources will be discovered.
            days: Number of days of data to collect
            granularity: Time granularity for metrics
            progress_callback: Optional callback to report progress percentage
            
        Returns:
            Dictionary of collected metrics
        """
        self.logger.info(f"Starting metrics collection for subscription {self.subscription_id}")
        
        # Get monitor client
        try:
            monitor_client = self._get_monitor_client()
        except Exception as ex:
            error_msg = f"Failed to initialize monitor client: {str(ex)}"
            self.logger.error(error_msg)
            raise MetricsCollectorError(error_msg) from ex
            
        # If resources not provided, we need a resource client to discover them
        if resources is None:
            try:
                resources = self._discover_resources()
            except Exception as ex:
                error_msg = f"Failed to discover resources: {str(ex)}"
                self.logger.error(error_msg)
                raise MetricsCollectorError(error_msg) from ex
        
        # Get time range
        start_time, end_time = get_time_range_for_metrics(days)
        
        # Prepare results container
        collection_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        metrics_data = {
            "collection_id": collection_id,
            "subscription_id": self.subscription_id,
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "granularity": granularity
            },
            "resources": {},
            "errors": []
        }
        
        # Count total resources to process for progress tracking
        total_resources = sum(len(res_list) for res_list in resources.values())
        processed_resources = 0
        
        self.logger.info(f"Collecting metrics for {total_resources} resources")
        
        # Process each resource type
        for resource_type, resource_list in resources.items():
            self.logger.info(f"Processing {len(resource_list)} resources of type {resource_type}")
            
            # Get metrics definitions for this resource type
            metrics_definitions = get_metrics_for_resource_type(resource_type)
            if not metrics_definitions:
                self.logger.info(f"No metrics defined for resource type {resource_type}, skipping")
                processed_resources += len(resource_list)
                if progress_callback:
                    progress_callback(processed_resources / total_resources * 100)
                continue
                
            # Process each resource
            for resource in resource_list:
                try:
                    resource_id = resource.id
                    resource_name = get_resource_name(resource_id)
                    resource_group = get_resource_group(resource_id)
                    
                    self.logger.debug(f"Collecting metrics for {resource_name} ({resource_id})")
                    
                    # Apply rate limiting
                    if self.rate_limit_sleep > 0:
                        time.sleep(self.rate_limit_sleep)
                    
                    resource_metrics = {}
                    
                    # Collect each metric
                    for metric_key, metric_def in metrics_definitions.items():
                        metric_data, error = self._collect_single_metric(
                            monitor_client, 
                            resource_id,
                            metric_def,
                            start_time,
                            end_time,
                            granularity
                        )
                        
                        if error:
                            metrics_data["errors"].append({
                                "resource_id": resource_id,
                                "metric": metric_key,
                                "error": error
                            })
                        
                        if metric_data:
                            resource_metrics[metric_key] = metric_data
                    
                    # Store resource metrics in results
                    if resource_metrics:
                        if resource_type not in metrics_data["resources"]:
                            metrics_data["resources"][resource_type] = {}
                            
                        metrics_data["resources"][resource_type][resource_id] = {
                            "name": resource_name,
                            "resource_group": resource_group,
                            "metrics": resource_metrics
                        }
                
                except Exception as ex:
                    self.logger.error(f"Error processing resource {getattr(resource, 'name', 'unknown')}: {str(ex)}")
                    metrics_data["errors"].append({
                        "resource_id": getattr(resource, 'id', 'unknown'),
                        "error": str(ex)
                    })
                
                # Update progress
                processed_resources += 1
                if progress_callback:
                    progress_callback(processed_resources / total_resources * 100)
        
        # Store metrics if storage is available
        if self.storage:
            try:
                self.storage.store_metrics(metrics_data, collection_id)
                self.logger.info(f"Metrics stored with collection ID: {collection_id}")
            except Exception as ex:
                self.logger.error(f"Failed to store metrics: {str(ex)}")
                metrics_data["errors"].append({
                    "type": "storage",
                    "error": str(ex)
                })
        
        self.logger.info("Metrics collection completed")
        return metrics_data
    
    def _collect_single_metric(
        self,
        monitor_client: MonitorManagementClient,
        resource_id: str,
        metric_def: EgressMetricsDefinition,
        start_time: datetime,
        end_time: datetime,
        granularity: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Collect a single metric for a resource.
        
        Args:
            monitor_client: Azure Monitor client
            resource_id: Resource ID to collect metrics for
            metric_def: Metric definition
            start_time: Start time for metrics collection
            end_time: End time for metrics collection
            granularity: Time granularity
            
        Returns:
            Tuple of (metric_data, error_message)
        """
        try:
            # Format resource ID for metrics API
            formatted_resource_id = format_resource_id_for_metrics_query(resource_id)
            
            # Call metrics API
            metric_data = monitor_client.metrics.list(
                resource_uri=formatted_resource_id,
                timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                interval=granularity,
                metricnames=metric_def.name,
                aggregation=metric_def.aggregation
            )
            
            # Process the response
            if not metric_data.value:
                return None, f"No metric data returned for {metric_def.name}"
                
            # Format the metric data
            result = {
                "name": metric_def.name,
                "display_name": metric_def.display_name,
                "unit": metric_def.unit,
                "times": [],
                "values": []
            }
            
            # Extract time series data
            for metric in metric_data.value:
                if not metric.timeseries:
                    continue
                    
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        # Get the value for the configured aggregation
                        value = getattr(data_point, metric_def.aggregation.lower(), None)
                        if value is not None:
                            result["times"].append(data_point.time_stamp.isoformat())
                            result["values"].append(value)
            
            return result, None
            
        except HttpResponseError as ex:
            error_msg = f"HTTP error collecting metric {metric_def.name}: {ex.message}"
            self.logger.error(error_msg)
            return None, error_msg
        except Exception as ex:
            error_msg = f"Error collecting metric {metric_def.name}: {str(ex)}"
            self.logger.error(error_msg)
            return None, error_msg
    
    def _discover_resources(self) -> Dict[str, List]:
        """
        Discover resources in the subscription.
        
        Returns:
            Dictionary of resources by type
        """
        self.logger.info(f"Discovering resources in subscription {self.subscription_id}")
        
        network_client = self.authenticator.get_client('network', self.subscription_id)
        compute_client = self.authenticator.get_client('compute', self.subscription_id)
        web_client = None  # Initialize on demand
        
        # Get configuration for which resource types to discover
        resources_config = self.config.get("monitoring", {}).get("resources", {})
        collect_vms = resources_config.get("virtual_machines", True)
        collect_app_services = resources_config.get("app_services", True)
        collect_vnets = resources_config.get("vnets", True)
        collect_lbs = resources_config.get("load_balancers", True)
        collect_nics = resources_config.get("network_interfaces", True)
        collect_pips = resources_config.get("public_ips", True)
        
        resources = {}
        
        # Get virtual networks
        if collect_vnets:
            self.logger.info("Discovering virtual networks")
            vnets = list(network_client.virtual_networks.list_all())
            resources["Microsoft.Network/virtualNetworks"] = vnets
            self.logger.info(f"Found {len(vnets)} virtual networks")
        
        # Get public IPs
        if collect_pips:
            self.logger.info("Discovering public IP addresses")
            public_ips = list(network_client.public_ip_addresses.list_all())
            resources["Microsoft.Network/publicIPAddresses"] = public_ips
            self.logger.info(f"Found {len(public_ips)} public IP addresses")
            
        # Get network interfaces
        if collect_nics:
            self.logger.info("Discovering network interfaces")
            nics = list(network_client.network_interfaces.list_all())
            resources["Microsoft.Network/networkInterfaces"] = nics
            self.logger.info(f"Found {len(nics)} network interfaces")
            
        # Get load balancers
        if collect_lbs:
            self.logger.info("Discovering load balancers")
            load_balancers = list(network_client.load_balancers.list_all())
            resources["Microsoft.Network/loadBalancers"] = load_balancers
            self.logger.info(f"Found {len(load_balancers)} load balancers")
            
        # Get virtual machines
        if collect_vms:
            self.logger.info("Discovering virtual machines")
            vms = list(compute_client.virtual_machines.list_all())
            resources["Microsoft.Compute/virtualMachines"] = vms
            self.logger.info(f"Found {len(vms)} virtual machines")
            
        # Get app services
        if collect_app_services:
            try:
                from azure.mgmt.web import WebSiteManagementClient
                
                self.logger.info("Discovering app services")
                web_client = self.authenticator.get_client('web', self.subscription_id)
                apps = list(web_client.web_apps.list())
                resources["Microsoft.Web/sites"] = apps
                self.logger.info(f"Found {len(apps)} app services")
            except Exception as ex:
                self.logger.warning(f"Failed to discover app services: {str(ex)}")
        
        return resources
