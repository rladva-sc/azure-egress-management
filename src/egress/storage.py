"""
Storage functionality for metrics data.
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

class StorageError(Exception):
    """Exception raised for errors in the MetricsStorage class."""
    pass

class MetricsStorage:
    """
    Handles storage and retrieval of metrics data.
    """
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Get storage config
        storage_config = self.config.get("storage", {})
        
        # Set data directory
        self.data_dir = storage_config.get("data_dir", os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data"
        ))
        
        # Set subdirectories
        self.raw_dir = os.path.join(self.data_dir, storage_config.get("raw_subdir", "raw"))
        self.processed_dir = os.path.join(self.data_dir, storage_config.get("processed_subdir", "processed"))
        
        # Initialize storage
        self.initialize()
    
    def initialize(self):
        """Initialize storage directories."""
        try:
            # Create directories if they don't exist
            for directory in [self.data_dir, self.raw_dir, self.processed_dir]:
                os.makedirs(directory, exist_ok=True)
                
            logger.info(f"Storage initialized with data directory: {self.data_dir}")
        except Exception as ex:
            error_msg = f"Failed to initialize storage: {str(ex)}"
            logger.error(error_msg)
            raise StorageError(error_msg) from ex
    
    def store_metrics(self, metrics_data: Dict[str, Any], collection_id: str = None) -> str:
        """
        Store metrics data to file.
        
        Args:
            metrics_data: Metrics data to store
            collection_id: Optional collection ID, auto-generated if not provided
            
        Returns:
            The collection ID used for storage
        """
        # Generate collection ID if not provided
        if not collection_id:
            collection_id = datetime.now().strftime("%Y%m%d%H%M%S")
            
        try:
            # Add metadata if not present
            if "metadata" not in metrics_data:
                metrics_data["metadata"] = {}
                
            # Update metadata
            metrics_data["metadata"]["collection_id"] = collection_id
            metrics_data["metadata"]["timestamp"] = datetime.now().isoformat()
            
            # Create the filename
            filename = f"metrics_{collection_id}.json"
            file_path = os.path.join(self.processed_dir, filename)
            
            # Save to file
            with open(file_path, 'w') as file:
                json.dump(metrics_data, file, indent=2)
                
            logger.info(f"Stored metrics data with collection ID: {collection_id}")
            return collection_id
            
        except Exception as ex:
            error_msg = f"Failed to store metrics: {str(ex)}"
            logger.error(error_msg)
            raise StorageError(error_msg) from ex
    
    def retrieve_metrics(self, collection_id: str) -> Dict[str, Any]:
        """
        Retrieve metrics data for the given collection ID.
        
        Args:
            collection_id: Collection ID to retrieve
            
        Returns:
            Dictionary with metrics data
        """
        try:
            # Build the filename
            filename = f"metrics_{collection_id}.json"
            file_path = os.path.join(self.processed_dir, filename)
            
            # Check if file exists
            if not os.path.exists(file_path):
                raise StorageError(f"Metrics collection not found: {collection_id}")
            
            # Load from file
            with open(file_path, 'r') as file:
                metrics_data = json.load(file)
                
            logger.info(f"Retrieved metrics data for collection ID: {collection_id}")
            return metrics_data
            
        except Exception as ex:
            error_msg = f"Failed to retrieve metrics: {str(ex)}"
            logger.error(error_msg)
            raise StorageError(error_msg) from ex
    
    def list_available_collections(self, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        List available metrics collections.
        
        Args:
            max_results: Maximum number of results to return
            
        Returns:
            List of collection metadata dictionaries
        """
        try:
            # Get all metrics files
            metrics_files = Path(self.processed_dir).glob("metrics_*.json")
            collections = []
            
            for file_path in metrics_files:
                try:
                    # Extract collection ID from filename
                    file_name = file_path.name
                    if file_name.startswith("metrics_") and file_name.endswith(".json"):
                        collection_id = file_name[8:-5]  # Remove "metrics_" and ".json"
                        
                        # Load file to get metadata
                        with open(file_path, 'r') as file:
                            metrics_data = json.load(file)
                            
                        # Extract metadata
                        metadata = metrics_data.get("metadata", {})
                        timestamp = metadata.get("timestamp", "")
                        
                        # Parse datetime for sorting
                        try:
                            dt = datetime.fromisoformat(timestamp)
                        except:
                            dt = datetime.min
                            
                        collections.append({
                            "id": collection_id,
                            "timestamp": timestamp,
                            "datetime": dt,
                            "file_path": str(file_path),
                            "metadata": metadata
                        })
                except Exception as ex:
                    logger.warning(f"Error processing file {file_path}: {str(ex)}")
            
            # Sort by timestamp (newest first)
            collections.sort(key=lambda x: x["datetime"], reverse=True)
            
            # Limit results
            limited_collections = collections[:max_results]
            
            logger.info(f"Found {len(limited_collections)} of {len(collections)} available collections")
            return limited_collections
            
        except Exception as ex:
            error_msg = f"Failed to list collections: {str(ex)}"
            logger.error(error_msg)
            raise StorageError(error_msg) from ex
