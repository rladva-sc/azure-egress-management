"""
Storage functionality for metrics data.
"""
import os
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

class StorageError(Exception):
    """Exception raised for errors in the MetricsStorage class."""
    pass

class MetricsStorage:
    """
    Handles storage and retrieval of metrics data.
    """
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the storage provider.
        
        Args:
            config: Configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Get storage configuration
        storage_config = self.config.get("storage", {})
        
        # Storage type: 'local' or 'azure'
        self.storage_type = storage_config.get("type", "local")
        
        # Local storage configuration
        if self.storage_type == "local":
            self.base_path = storage_config.get("local_path")
            if not self.base_path:
                # Use default paths
                project_root = Path(__file__).parent.parent.parent
                self.raw_path = project_root / "data" / "raw"
                self.processed_path = project_root / "data" / "processed"
            else:
                base = Path(self.base_path)
                self.raw_path = base / "raw"
                self.processed_path = base / "processed"
        
        # Azure storage configuration for future implementation
        elif self.storage_type == "azure":
            self.connection_string = storage_config.get("connection_string")
            self.container_name = storage_config.get("container", "egress-metrics")
            self.raw_prefix = storage_config.get("raw_prefix", "raw/")
            self.processed_prefix = storage_config.get("processed_prefix", "processed/")
            
            # Azure storage client will be initialized on demand
            self.blob_service_client = None
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    def initialize(self):
        """
        Initialize the storage backend.
        
        Raises:
            StorageError: If storage initialization fails
        """
        try:
            if self.storage_type == "local":
                self.raw_path.mkdir(parents=True, exist_ok=True)
                self.processed_path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Initialized local storage at {self.raw_path} and {self.processed_path}")
            elif self.storage_type == "azure":
                try:
                    from azure.storage.blob import BlobServiceClient
                    
                    # Initialize Azure Storage client
                    if not self.connection_string:
                        raise StorageError("Azure Blob Storage connection string not provided")
                    
                    self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
                    container_client = self.blob_service_client.get_container_client(self.container_name)
                    
                    # Create container if it doesn't exist
                    try:
                        container_client.create_container()
                        self.logger.info(f"Created container {self.container_name}")
                    except Exception:
                        # Container may already exist, which is fine
                        pass
                    
                    self.logger.info(f"Initialized Azure Blob Storage in container {self.container_name}")
                except ImportError:
                    raise StorageError("Azure Storage SDK not installed. Run 'pip install azure-storage-blob'")
            else:
                raise StorageError(f"Unsupported storage type: {self.storage_type}")
        except Exception as ex:
            raise StorageError(f"Failed to initialize storage: {str(ex)}")
    
    def store_metrics(self, metrics_data: Dict[str, Any], collection_id: str = None) -> str:
        """
        Store metrics data.
        
        Args:
            metrics_data: Metrics data to store
            collection_id: Optional ID for this collection
            
        Returns:
            The collection ID
            
        Raises:
            StorageError: If storage fails
        """
        if collection_id is None:
            collection_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        
        try:
            if self.storage_type == "local":
                # Ensure directories exist
                self.initialize()
                
                # Store raw data
                raw_file = self.raw_path / f"metrics_{collection_id}.json"
                with open(raw_file, 'w') as f:
                    json.dump(metrics_data, f, indent=2)
                
                self.logger.info(f"Stored raw metrics data in {raw_file}")
                return collection_id
            elif self.storage_type == "azure":
                from azure.storage.blob import BlobClient
                
                # Ensure client is initialized
                if self.blob_service_client is None:
                    self.initialize()
                
                # Format blob name
                blob_name = f"{self.raw_prefix}metrics_{collection_id}.json"
                
                # Get blob client
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.container_name,
                    blob=blob_name
                )
                
                # Upload data
                metrics_json = json.dumps(metrics_data, indent=2)
                blob_client.upload_blob(metrics_json, overwrite=True)
                
                self.logger.info(f"Stored metrics data in blob {blob_name}")
                return collection_id
            else:
                raise StorageError(f"Unsupported storage type: {self.storage_type}")
        except Exception as ex:
            raise StorageError(f"Failed to store metrics: {str(ex)}")
    
    def retrieve_metrics(self, collection_id: str) -> Dict[str, Any]:
        """
        Retrieve stored metrics data.
        
        Args:
            collection_id: ID of the collection to retrieve
            
        Returns:
            The metrics data
            
        Raises:
            StorageError: If retrieval fails
        """
        try:
            if self.storage_type == "local":
                # Check raw data first
                raw_file = self.raw_path / f"metrics_{collection_id}.json"
                if raw_file.exists():
                    with open(raw_file, 'r') as f:
                        return json.load(f)
                
                # Check processed data
                processed_file = self.processed_path / f"metrics_{collection_id}.json"
                if processed_file.exists():
                    with open(processed_file, 'r') as f:
                        return json.load(f)
                
                raise StorageError(f"No metrics found with collection ID {collection_id}")
            elif self.storage_type == "azure":
                from azure.storage.blob import BlobClient
                from azure.core.exceptions import ResourceNotFoundError
                
                # Ensure client is initialized
                if self.blob_service_client is None:
                    self.initialize()
                
                # Try raw data first
                blob_name = f"{self.raw_prefix}metrics_{collection_id}.json"
                
                # Get blob client
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.container_name,
                    blob=blob_name
                )
                
                try:
                    # Download data
                    download_stream = blob_client.download_blob()
                    metrics_json = download_stream.readall().decode('utf-8')
                    return json.loads(metrics_json)
                except ResourceNotFoundError:
                    # Try processed data next
                    blob_name = f"{self.processed_prefix}metrics_{collection_id}.json"
                    blob_client = self.blob_service_client.get_blob_client(
                        container=self.container_name,
                        blob=blob_name
                    )
                    
                    try:
                        # Download data
                        download_stream = blob_client.download_blob()
                        metrics_json = download_stream.readall().decode('utf-8')
                        return json.loads(metrics_json)
                    except ResourceNotFoundError:
                        raise StorageError(f"No metrics found with collection ID {collection_id}")
            else:
                raise StorageError(f"Unsupported storage type: {self.storage_type}")
        except Exception as ex:
            raise StorageError(f"Failed to retrieve metrics: {str(ex)}")
    
    def list_available_collections(self, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        List available metric collections.
        
        Args:
            max_results: Maximum number of results to return
            
        Returns:
            List of collection information
            
        Raises:
            StorageError: If listing fails
        """
        try:
            if self.storage_type == "local":
                # Get all metric files in raw and processed directories
                collections = []
                
                # Raw files
                if self.raw_path.exists():
                    for file_path in self.raw_path.glob("metrics_*.json"):
                        collection_id = file_path.stem.replace("metrics_", "")
                        collections.append({
                            "id": collection_id,
                            "path": str(file_path),
                            "type": "raw",
                            "timestamp": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                        })
                
                # Processed files
                if self.processed_path.exists():
                    for file_path in self.processed_path.glob("metrics_*.json"):
                        collection_id = file_path.stem.replace("metrics_", "")
                        collections.append({
                            "id": collection_id,
                            "path": str(file_path),
                            "type": "processed",
                            "timestamp": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                        })
                
                # Sort by timestamp (newest first)
                collections.sort(key=lambda x: x["timestamp"], reverse=True)
                
                return collections[:max_results]
            elif self.storage_type == "azure":
                from azure.storage.blob import BlobClient
                
                # Ensure client is initialized
                if self.blob_service_client is None:
                    self.initialize()
                
                collections = []
                container_client = self.blob_service_client.get_container_client(self.container_name)
                
                # Raw files
                raw_blobs = list(container_client.list_blobs(name_starts_with=self.raw_prefix))
                for blob in raw_blobs:
                    if blob.name.endswith(".json") and "metrics_" in blob.name:
                        collection_id = blob.name.split("metrics_")[1].replace(".json", "")
                        collections.append({
                            "id": collection_id,
                            "path": blob.name,
                            "type": "raw",
                            "timestamp": blob.last_modified.isoformat() if blob.last_modified else None
                        })
                
                # Processed files
                processed_blobs = list(container_client.list_blobs(name_starts_with=self.processed_prefix))
                for blob in processed_blobs:
                    if blob.name.endswith(".json") and "metrics_" in blob.name:
                        collection_id = blob.name.split("metrics_")[1].replace(".json", "")
                        collections.append({
                            "id": collection_id,
                            "path": blob.name,
                            "type": "processed",
                            "timestamp": blob.last_modified.isoformat() if blob.last_modified else None
                        })
                
                # Sort by timestamp (newest first)
                collections = [c for c in collections if c["timestamp"] is not None]
                collections.sort(key=lambda x: x["timestamp"], reverse=True)
                
                return collections[:max_results]
            else:
                raise StorageError(f"Unsupported storage type: {self.storage_type}")
        except Exception as ex:
            raise StorageError(f"Failed to list collections: {str(ex)}")
