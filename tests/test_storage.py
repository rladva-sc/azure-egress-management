"""
Tests for the metrics storage module.
"""
import os
import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open

from src.egress.storage import MetricsStorage, StorageError

@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for data storage tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

def test_storage_init():
    """Test storage initialization with default config."""
    storage = MetricsStorage()
    assert storage is not None
    assert hasattr(storage, 'data_dir')
    assert hasattr(storage, 'raw_dir')
    assert hasattr(storage, 'processed_dir')

def test_storage_init_with_config():
    """Test storage initialization with custom config."""
    config = {
        "storage": {
            "data_dir": "/tmp/test_data",
            "raw_subdir": "raw_metrics",
            "processed_subdir": "processed_metrics"
        }
    }
    storage = MetricsStorage(config)
    assert storage.data_dir == "/tmp/test_data"
    assert storage.raw_dir == "/tmp/test_data/raw_metrics"
    assert storage.processed_dir == "/tmp/test_data/processed_metrics"

def test_storage_initialize(temp_data_dir):
    """Test storage directory initialization."""
    config = {
        "storage": {
            "data_dir": temp_data_dir,
            "raw_subdir": "raw",
            "processed_subdir": "processed"
        }
    }
    storage = MetricsStorage(config)
    storage.initialize()
    
    # Verify directories were created
    assert os.path.exists(temp_data_dir)
    assert os.path.exists(os.path.join(temp_data_dir, "raw"))
    assert os.path.exists(os.path.join(temp_data_dir, "processed"))

def test_store_metrics(temp_data_dir, sample_metrics_data):
    """Test storing metrics data."""
    config = {
        "storage": {
            "data_dir": temp_data_dir
        }
    }
    storage = MetricsStorage(config)
    storage.initialize()
    
    # Store metrics with auto-generated collection ID
    collection_id = storage.store_metrics(sample_metrics_data)
    
    # Verify collection ID is returned
    assert collection_id is not None
    assert isinstance(collection_id, str)
    
    # Verify file was created
    expected_file = os.path.join(temp_data_dir, "processed", f"metrics_{collection_id}.json")
    assert os.path.exists(expected_file)
    
    # Verify file contents
    with open(expected_file, 'r') as f:
        stored_data = json.load(f)
    
    assert "metadata" in stored_data
    assert stored_data["metadata"]["collection_id"] == collection_id

def test_store_metrics_with_custom_id(temp_data_dir, sample_metrics_data):
    """Test storing metrics data with custom collection ID."""
    config = {
        "storage": {
            "data_dir": temp_data_dir
        }
    }
    storage = MetricsStorage(config)
    storage.initialize()
    
    # Store metrics with custom collection ID
    custom_id = "test_123456"
    returned_id = storage.store_metrics(sample_metrics_data, collection_id=custom_id)
    
    # Verify collection ID is returned
    assert returned_id == custom_id
    
    # Verify file was created
    expected_file = os.path.join(temp_data_dir, "processed", f"metrics_{custom_id}.json")
    assert os.path.exists(expected_file)

def test_retrieve_metrics(temp_data_dir, sample_metrics_data):
    """Test retrieving metrics data."""
    config = {
        "storage": {
            "data_dir": temp_data_dir
        }
    }
    storage = MetricsStorage(config)
    storage.initialize()
    
    # Store metrics
    collection_id = storage.store_metrics(sample_metrics_data)
    
    # Retrieve metrics
    retrieved_data = storage.retrieve_metrics(collection_id)
    
    # Verify data
    assert retrieved_data is not None
    assert "metadata" in retrieved_data
    assert retrieved_data["metadata"]["collection_id"] == collection_id
    assert "resources" in retrieved_data
    
    # Check specific contents
    assert "Microsoft.Compute/virtualMachines" in retrieved_data["resources"]

def test_retrieve_metrics_nonexistent():
    """Test retrieving nonexistent metrics collection."""
    storage = MetricsStorage()
    
    # Try to retrieve nonexistent collection
    with pytest.raises(StorageError):
        storage.retrieve_metrics("nonexistent_id")

def test_list_available_collections(temp_data_dir, sample_metrics_data):
    """Test listing available collections."""
    config = {
        "storage": {
            "data_dir": temp_data_dir
        }
    }
    storage = MetricsStorage(config)
    storage.initialize()
    
    # Store multiple metrics collections
    collection_id1 = storage.store_metrics(sample_metrics_data)
    collection_id2 = storage.store_metrics(sample_metrics_data)
    collection_id3 = storage.store_metrics(sample_metrics_data)
    
    # List collections
    collections = storage.list_available_collections()
    
    # Verify
    assert len(collections) == 3
    collection_ids = [c["id"] for c in collections]
    assert collection_id1 in collection_ids
    assert collection_id2 in collection_ids
    assert collection_id3 in collection_ids
    
    # Check sorting (newest first)
    assert collections[0]["id"] == collection_id3
    assert collections[1]["id"] == collection_id2
    assert collections[2]["id"] == collection_id1

def test_list_available_collections_with_limit(temp_data_dir, sample_metrics_data):
    """Test listing available collections with max_results limit."""
    config = {
        "storage": {
            "data_dir": temp_data_dir
        }
    }
    storage = MetricsStorage(config)
    storage.initialize()
    
    # Store multiple metrics collections
    for _ in range(5):
        storage.store_metrics(sample_metrics_data)
    
    # List collections with limit
    collections = storage.list_available_collections(max_results=3)
    
    # Verify
    assert len(collections) == 3
