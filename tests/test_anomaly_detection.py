"""
Tests for the anomaly detection module.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.egress.anomaly_detection import AnomalyDetector, AnomalyConfig, AnomalyResult

@pytest.fixture
def anomaly_detector():
    """Create an anomaly detector for testing."""
    return AnomalyDetector()

@pytest.fixture
def sample_data_with_anomalies():
    """Create sample data with known anomalies."""
    # Create timestamps - hourly for 3 days
    timestamps = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(72)]
    
    # Create base values with a daily pattern
    base_values = []
    for ts in timestamps:
        # Create a daily pattern with higher values during business hours
        hour = ts.hour
        if 8 <= hour <= 17:
            base_values.append(100 + 20 * np.sin(hour / 24 * 2 * np.pi))
        else:
            base_values.append(50 + 10 * np.sin(hour / 24 * 2 * np.pi))
    
    # Add random noise
    values = [base + np.random.normal(0, 5) for base in base_values]
    
    # Inject anomalies
    # Anomaly 1: Spike on day 2, hour 14 (index 38)
    values[38] = values[38] * 3  # 3x normal value
    
    # Anomaly 2: Dip on day 3, hour 10 (index 58)
    values[58] = values[58] * 0.2  # 80% reduction
    
    # Anomaly 3: Elevated period for a few hours on day 1 (indices 18-20)
    values[18] = values[18] * 2
    values[19] = values[19] * 2.2
    values[20] = values[20] * 1.9
    
    # Create a DataFrame
    df = pd.DataFrame({
        'timestamp': timestamps,
        'resource_id': 'test-resource-1',
        'resource_name': 'Test Resource 1',
        'resource_type': 'Microsoft.Test/testResources',
        'metric_name': 'BytesOut',
        'value': values
    })
    
    # Add a second metric for the same resource
    values2 = [v * 0.5 + np.random.normal(0, 2) for v in values]
    df2 = pd.DataFrame({
        'timestamp': timestamps,
        'resource_id': 'test-resource-1',
        'resource_name': 'Test Resource 1',
        'resource_type': 'Microsoft.Test/testResources',
        'metric_name': 'PacketsOut',
        'value': values2
    })
    
    # Add a second resource
    values3 = [100 + 30 * np.sin(i / 24 * 2 * np.pi) + np.random.normal(0, 8) for i in range(72)]
    # Add a single anomaly
    values3[45] = values3[45] * 4  # 4x normal value
    
    df3 = pd.DataFrame({
        'timestamp': timestamps,
        'resource_id': 'test-resource-2',
        'resource_name': 'Test Resource 2',
        'resource_type': 'Microsoft.Test/testResources',
        'metric_name': 'BytesOut',
        'value': values3
    })
    
    # Combine all data
    return pd.concat([df, df2, df3])

def test_anomaly_detector_initialization(anomaly_detector):
    """Test that AnomalyDetector initializes correctly."""
    assert anomaly_detector is not None
    assert hasattr(anomaly_detector, 'detection_config')
    assert isinstance(anomaly_detector.detection_config, AnomalyConfig)

def test_detect_anomalies(anomaly_detector, sample_data_with_anomalies):
    """Test detecting anomalies in sample data."""
    results = anomaly_detector.detect_anomalies(sample_data_with_anomalies)
    
    # Check overall structure
    assert results["status"] == "success"
    assert "summary" in results
    assert "anomalies" in results
    assert "by_resource" in results
    
    # Check anomalies were found
    assert results["summary"]["total_anomalies"] > 0
    assert len(results["anomalies"]) > 0
    
    # Check we detected anomalies for both resources
    assert "test-resource-1" in results["by_resource"]
    assert "test-resource-2" in results["by_resource"]
    
    # Check the anomalies match our injected ones (approximately)
    # For resource 1, we injected anomalies at indices 18, 19, 20, 38, 58
    resource1_anomalies = results["by_resource"]["test-resource-1"]
    resource1_timestamps = [a["timestamp"] for a in resource1_anomalies]
    
    # Convert sample data timestamps to ISO strings for comparison
    sample_timestamps = [
        sample_data_with_anomalies.iloc[i]["timestamp"].isoformat()
        for i in [18, 19, 20, 38, 58]
    ]
    
    # Check that at least some of our injected anomalies were detected
    # (We don't expect all to be detected, as it depends on the algorithm settings)
    assert any(ts in resource1_timestamps for ts in sample_timestamps)
    
    # For resource 2, we injected an anomaly at index 45
    resource2_anomalies = results["by_resource"]["test-resource-2"]
    resource2_timestamps = [a["timestamp"] for a in resource2_anomalies]
    
    sample_timestamp = sample_data_with_anomalies.iloc[45]["timestamp"].isoformat()
    
    # Check that our injected anomaly was detected
    assert any(ts == sample_timestamp for ts in resource2_timestamps)

def test_detect_anomalies_empty_data(anomaly_detector):
    """Test anomaly detection with empty data."""
    empty_df = pd.DataFrame()
    results = anomaly_detector.detect_anomalies(empty_df)
    
    assert results["status"] == "no_data"

def test_detect_anomalies_non_egress_data(anomaly_detector):
    """Test anomaly detection with non-egress metrics."""
    # Create data that doesn't match egress patterns
    timestamps = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(24)]
    data = []
    
    for ts in timestamps:
        data.append({
            'timestamp': ts,
            'resource_id': 'test-resource',
            'resource_name': 'Test Resource',
            'resource_type': 'Microsoft.Test/testResources',
            'metric_name': 'CPUUsage',  # Not egress related
            'value': 50 + np.random.normal(0, 5)
        })
    
    df = pd.DataFrame(data)
    results = anomaly_detector.detect_anomalies(df)
    
    assert results["status"] == "no_egress_data"

def test_detect_zscore_anomalies(anomaly_detector, sample_data_with_anomalies):
    """Test Z-score anomaly detection method."""
    anomalies = anomaly_detector._detect_zscore_anomalies(sample_data_with_anomalies)
    
    # Check we found some anomalies
    assert len(anomalies) > 0
    
    # Check the structure of the anomaly results
    for anomaly in anomalies:
        assert isinstance(anomaly, AnomalyResult)
        assert anomaly.algorithm == "zscore"
        assert hasattr(anomaly, 'resource_id')
        assert hasattr(anomaly, 'timestamp')
        assert hasattr(anomaly, 'value')
        assert hasattr(anomaly, 'expected_value')
        assert hasattr(anomaly, 'score')

def test_detect_mad_anomalies(anomaly_detector, sample_data_with_anomalies):
    """Test MAD anomaly detection method."""
    anomalies = anomaly_detector._detect_mad_anomalies(sample_data_with_anomalies)
    
    # Check we found some anomalies
    assert len(anomalies) > 0
    
    # Check the structure of the anomaly results
    for anomaly in anomalies:
        assert isinstance(anomaly, AnomalyResult)
        assert anomaly.algorithm == "mad"
        assert hasattr(anomaly, 'resource_id')
        assert hasattr(anomaly, 'timestamp')

def test_detect_moving_avg_anomalies(anomaly_detector, sample_data_with_anomalies):
    """Test moving average anomaly detection method."""
    anomalies = anomaly_detector._detect_moving_avg_anomalies(sample_data_with_anomalies)
    
    # Check we found some anomalies
    assert len(anomalies) > 0
    
    # Check the structure of the anomaly results
    for anomaly in anomalies:
        assert isinstance(anomaly, AnomalyResult)
        assert anomaly.algorithm == "moving_average"
        assert hasattr(anomaly, 'resource_id')
        assert hasattr(anomaly, 'timestamp')

def test_deduplicate_anomalies(anomaly_detector):
    """Test anomaly deduplication."""
    # Create some duplicate anomalies
    anomalies = [
        AnomalyResult(resource_id="res1", timestamp="2023-01-01T12:00:00", metric_name="m1", score=2.5),
        AnomalyResult(resource_id="res1", timestamp="2023-01-01T12:00:00", metric_name="m1", score=3.0),
        AnomalyResult(resource_id="res1", timestamp="2023-01-01T13:00:00", metric_name="m1", score=2.0),
        AnomalyResult(resource_id="res2", timestamp="2023-01-01T12:00:00", metric_name="m1", score=1.5)
    ]
    
    # Deduplicate
    deduplicated = anomaly_detector._deduplicate_anomalies(anomalies)
    
    # We should have 3 anomalies: the highest scoring one for res1/12:00, plus the other two
    assert len(deduplicated) == 3
    
    # Check that we kept the higher score for the duplicate
    for anomaly in deduplicated:
        if anomaly.resource_id == "res1" and anomaly.timestamp == "2023-01-01T12:00:00":
            assert anomaly.score == 3.0

def test_generate_anomaly_recommendations(anomaly_detector, sample_data_with_anomalies):
    """Test generating recommendations from anomalies."""
    # First detect anomalies
    results = anomaly_detector.detect_anomalies(sample_data_with_anomalies)
    
    # Generate recommendations
    recommendations = anomaly_detector.generate_anomaly_recommendations(results)
    
    # Check we got some recommendations
    assert len(recommendations) > 0
    
    # Check recommendation structure
    for rec in recommendations:
        assert "type" in rec
        assert "severity" in rec
        assert "title" in rec
        assert "description" in rec
        assert "actions" in rec
        assert isinstance(rec["actions"], list)
