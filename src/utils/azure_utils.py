"""
Utilities for working with Azure resources and services.
"""
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

from azure.core.exceptions import HttpResponseError
from azure.mgmt.monitor.models import ErrorResponseException

logger = logging.getLogger(__name__)

def get_resource_name(resource_id: str) -> str:
    """
    Extract resource name from Azure resource ID.
    
    Args:
        resource_id: Full Azure resource ID
        
    Returns:
        The resource name
    """
    if not resource_id:
        return "unknown"
    
    parts = resource_id.split('/')
    return parts[-1] if parts else "unknown"

def get_resource_group(resource_id: str) -> str:
    """
    Extract resource group name from Azure resource ID.
    
    Args:
        resource_id: Full Azure resource ID
        
    Returns:
        The resource group name
    """
    if not resource_id:
        return "unknown"
    
    match = re.search(r'/resourceGroups/([^/]+)/', resource_id)
    return match.group(1) if match else "unknown"

def get_resource_type(resource_id: str) -> str:
    """
    Extract resource type from Azure resource ID.
    
    Args:
        resource_id: Full Azure resource ID
        
    Returns:
        The resource type
    """
    if not resource_id:
        return "unknown"
    
    match = re.search(r'providers/([^/]+/[^/]+)', resource_id)
    return match.group(1) if match else "unknown"

def get_subscription_from_resource_id(resource_id: str) -> str:
    """
    Extract subscription ID from Azure resource ID.
    
    Args:
        resource_id: Full Azure resource ID
        
    Returns:
        The subscription ID
    """
    if not resource_id:
        return "unknown"
    
    match = re.search(r'/subscriptions/([^/]+)/', resource_id)
    return match.group(1) if match else "unknown"

def format_resource_id_for_metrics_query(resource_id: str) -> str:
    """
    Format resource ID for use in metrics queries.
    
    Args:
        resource_id: Full Azure resource ID
        
    Returns:
        Properly formatted resource ID for metrics API
    """
    # Metrics API requires the resource ID in a specific format
    # This function ensures the format is correct
    return resource_id.strip()

def safe_execute_azure_operation(operation_name: str, operation, *args, **kwargs) -> Tuple[Any, Optional[str]]:
    """
    Safely execute an Azure operation with error handling.
    
    Args:
        operation_name: Name of the operation for logging
        operation: Function to execute
        *args: Positional arguments for the operation
        **kwargs: Keyword arguments for the operation
        
    Returns:
        Tuple containing (result, error_message)
    """
    try:
        result = operation(*args, **kwargs)
        return result, None
    except HttpResponseError as ex:
        error_msg = f"HTTP error in {operation_name}: {ex.message}"
        logger.error(error_msg)
        return None, error_msg
    except ErrorResponseException as ex:
        error_code = ex.error.code if hasattr(ex, 'error') and hasattr(ex.error, 'code') else "unknown"
        error_msg = f"Azure error in {operation_name}: {error_code} - {ex}"
        logger.error(error_msg)
        return None, error_msg
    except Exception as ex:
        error_msg = f"Unexpected error in {operation_name}: {str(ex)}"
        logger.error(error_msg)
        return None, error_msg

def get_time_range_for_metrics(days: int = 7) -> Tuple[datetime, datetime]:
    """
    Get start and end time for metrics queries.
    
    Args:
        days: Number of days to look back
        
    Returns:
        Tuple of (start_time, end_time)
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    return start_time, end_time

def batch_list_generator(collection_function, max_batch_size=100, **kwargs):
    """
    Generator that handles batching for list operations with continuation tokens.
    
    Args:
        collection_function: Function that returns a collection with continuation token
        max_batch_size: Maximum batch size for each request
        **kwargs: Additional arguments for collection_function
        
    Yields:
        Individual items from the collection
    """
    kwargs['top'] = max_batch_size
    continuation_token = None
    
    while True:
        if continuation_token:
            kwargs['skip_token'] = continuation_token
            
        try:
            page = collection_function(**kwargs)
            for item in page:
                yield item
                
            continuation_token = page.continuation_token
            if not continuation_token:
                break
        except Exception as ex:
            logger.error(f"Error in batch collection: {ex}")
            break
