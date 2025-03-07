"""
Anomaly detection for Azure egress metrics.
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field

class AnomalyDetectionError(Exception):
    """Exception raised for errors in anomaly detection."""
    pass

@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection."""
    zscore_threshold: float = 3.0
    min_data_points: int = 5
    mad_threshold: float = 3.5
    moving_avg_window: int = 5
    seasonal_periods: int = 24  # For hourly data
    peak_detection_threshold: float = 3.0
    enable_seasonal_detection: bool = True

@dataclass
class AnomalyResult:
    """Result of an anomaly detection."""
    resource_id: str
    resource_name: str = "Unknown"
    timestamp: str = ""
    value: float = 0.0
    expected_value: float = 0.0
    score: float = 0.0
    algorithm: str = "zscore"
    metric_name: str = ""
    severity: str = "medium"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "timestamp": self.timestamp,
            "value": self.value,
            "expected_value": self.expected_value,
            "score": self.score,
            "algorithm": self.algorithm,
            "metric_name": self.metric_name,
            "severity": self.severity,
            "deviation_percent": self._calculate_deviation_percent()
        }
        
    def _calculate_deviation_percent(self) -> float:
        """Calculate percentage deviation from expected value."""
        if self.expected_value == 0:
            return float('inf') if self.value > 0 else 0.0
        return ((self.value - self.expected_value) / abs(self.expected_value)) * 100


class AnomalyDetector:
    """
    Detects anomalies in egress metrics using multiple algorithms.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the anomaly detector.
        
        Args:
            config: Configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Get anomaly detection configuration
        anomaly_config = self.config.get("analysis", {}).get("anomaly_detection", {})
        
        # Create anomaly configuration
        self.detection_config = AnomalyConfig(
            zscore_threshold=anomaly_config.get("zscore_threshold", 3.0),
            min_data_points=anomaly_config.get("min_data_points", 5),
            mad_threshold=anomaly_config.get("mad_threshold", 3.5),
            moving_avg_window=anomaly_config.get("moving_avg_window", 5),
            seasonal_periods=anomaly_config.get("seasonal_periods", 24),
            peak_detection_threshold=anomaly_config.get("peak_detection_threshold", 3.0),
            enable_seasonal_detection=anomaly_config.get("enable_seasonal_detection", True)
        )
    
    def detect_anomalies(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect anomalies in the provided metrics data.
        
        Args:
            df: DataFrame with egress metrics
            
        Returns:
            Dictionary with anomaly detection results
        """
        if df.empty:
            return {"status": "no_data"}
        
        # Filter to egress metrics only
        egress_df = df[
            (df['metric_name'].str.contains('out', case=False, na=False)) | 
            (df['metric_name'].str.contains('sent', case=False, na=False)) |
            (df['metric_name'].str.contains('egress', case=False, na=False))
        ].copy()
        
        if egress_df.empty:
            return {"status": "no_egress_data"}
        
        try:
            # Apply multiple anomaly detection algorithms
            zscore_anomalies = self._detect_zscore_anomalies(egress_df)
            mad_anomalies = self._detect_mad_anomalies(egress_df)
            moving_avg_anomalies = self._detect_moving_avg_anomalies(egress_df)
            
            # Combine all anomaly results
            all_anomalies = zscore_anomalies + mad_anomalies + moving_avg_anomalies
            
            # Deduplicate anomalies by resource and timestamp
            unique_anomalies = self._deduplicate_anomalies(all_anomalies)
            
            # Sort anomalies by score (highest first)
            unique_anomalies.sort(key=lambda x: abs(x.score), reverse=True)
            
            # Group anomalies by resource
            resource_anomalies = {}
            for anomaly in unique_anomalies:
                resource_id = anomaly.resource_id
                if resource_id not in resource_anomalies:
                    resource_anomalies[resource_id] = []
                resource_anomalies[resource_id].append(anomaly.to_dict())
            
            # Calculate summary metrics
            summary = {
                "total_anomalies": len(unique_anomalies),
                "total_resources_with_anomalies": len(resource_anomalies),
                "detection_methods": ["zscore", "mad", "moving_average"],
                "algorithm_counts": {
                    "zscore": len(zscore_anomalies),
                    "mad": len(mad_anomalies),
                    "moving_average": len(moving_avg_anomalies)
                },
                "severity_counts": {
                    "high": len([a for a in unique_anomalies if a.severity == "high"]),
                    "medium": len([a for a in unique_anomalies if a.severity == "medium"]),
                    "low": len([a for a in unique_anomalies if a.severity == "low"])
                }
            }
            
            return {
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "summary": summary,
                "anomalies": [a.to_dict() for a in unique_anomalies],
                "by_resource": resource_anomalies
            }
            
        except Exception as ex:
            self.logger.error(f"Error detecting anomalies: {str(ex)}")
            return {
                "status": "error",
                "error": str(ex)
            }

    def _detect_zscore_anomalies(self, df: pd.DataFrame) -> List[AnomalyResult]:
        """
        Detect anomalies using Z-score method.
        
        Args:
            df: DataFrame with metrics
            
        Returns:
            List of anomaly results
        """
        anomalies = []
        
        # Process each resource separately
        for (resource_id, resource_name), group_df in df.groupby(['resource_id', 'resource_name']):
            # Process each metric for this resource
            for metric_name, metric_df in group_df.groupby('metric_name'):
                # Skip if not enough data points
                if len(metric_df) < self.detection_config.min_data_points:
                    continue
                
                # Calculate mean and standard deviation
                mean_val = metric_df['value'].mean()
                std_val = metric_df['value'].std()
                
                # Skip if standard deviation is zero (all values are the same)
                if std_val == 0:
                    continue
                
                # Calculate z-scores
                metric_df['zscore'] = (metric_df['value'] - mean_val) / std_val
                
                # Identify anomalies
                threshold = self.detection_config.zscore_threshold
                anomalous_points = metric_df[abs(metric_df['zscore']) > threshold]
                
                # Create anomaly results
                for _, row in anomalous_points.iterrows():
                    # Determine severity based on z-score
                    severity = "medium"
                    if abs(row['zscore']) > threshold * 2:
                        severity = "high"
                    elif abs(row['zscore']) <= threshold * 1.2:
                        severity = "low"
                    
                    anomalies.append(AnomalyResult(
                        resource_id=resource_id,
                        resource_name=resource_name,
                        timestamp=row['timestamp'].isoformat() if isinstance(row['timestamp'], datetime) else str(row['timestamp']),
                        value=float(row['value']),
                        expected_value=float(mean_val),
                        score=float(row['zscore']),
                        algorithm="zscore",
                        metric_name=metric_name,
                        severity=severity
                    ))
        
        return anomalies
    
    def _detect_mad_anomalies(self, df: pd.DataFrame) -> List[AnomalyResult]:
        """
        Detect anomalies using Median Absolute Deviation method.
        
        Args:
            df: DataFrame with metrics
            
        Returns:
            List of anomaly results
        """
        anomalies = []
        
        # Process each resource separately
        for (resource_id, resource_name), group_df in df.groupby(['resource_id', 'resource_name']):
            # Process each metric for this resource
            for metric_name, metric_df in group_df.groupby('metric_name'):
                # Skip if not enough data points
                if len(metric_df) < self.detection_config.min_data_points:
                    continue
                
                # Calculate median and MAD
                median_val = metric_df['value'].median()
                mad = np.median(abs(metric_df['value'] - median_val))
                
                # Skip if MAD is zero
                if mad == 0:
                    continue
                
                # Calculate modified z-scores using MAD
                metric_df['mad_score'] = 0.6745 * (metric_df['value'] - median_val) / mad
                
                # Identify anomalies
                threshold = self.detection_config.mad_threshold
                anomalous_points = metric_df[abs(metric_df['mad_score']) > threshold]
                
                # Create anomaly results
                for _, row in anomalous_points.iterrows():
                    # Determine severity based on MAD score
                    severity = "medium"
                    if abs(row['mad_score']) > threshold * 2:
                        severity = "high"
                    elif abs(row['mad_score']) <= threshold * 1.2:
                        severity = "low"
                    
                    anomalies.append(AnomalyResult(
                        resource_id=resource_id,
                        resource_name=resource_name,
                        timestamp=row['timestamp'].isoformat() if isinstance(row['timestamp'], datetime) else str(row['timestamp']),
                        value=float(row['value']),
                        expected_value=float(median_val),
                        score=float(row['mad_score']),
                        algorithm="mad",
                        metric_name=metric_name,
                        severity=severity
                    ))
        
        return anomalies
    
    def _detect_moving_avg_anomalies(self, df: pd.DataFrame) -> List[AnomalyResult]:
        """
        Detect anomalies using moving average method.
        
        Args:
            df: DataFrame with metrics
            
        Returns:
            List of anomaly results
        """
        anomalies = []
        window = self.detection_config.moving_avg_window
        
        # Ensure timestamp is datetime
        if 'timestamp' in df.columns and df['timestamp'].dtype != 'datetime64[ns]':
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            except:
                pass
        
        # Process each resource separately
        for (resource_id, resource_name), group_df in df.groupby(['resource_id', 'resource_name']):
            # Process each metric for this resource
            for metric_name, metric_df in group_df.groupby('metric_name'):
                # Skip if not enough data points
                if len(metric_df) < window + 2:
                    continue
                
                # Sort by timestamp
                metric_df = metric_df.sort_values('timestamp')
                
                # Calculate moving average
                metric_df['moving_avg'] = metric_df['value'].rolling(window=window).mean()
                
                # Calculate standard deviation of the differences
                diffs = metric_df['value'] - metric_df['moving_avg']
                std_diff = diffs.std()
                
                if std_diff == 0:
                    continue
                
                # Calculate deviation scores
                metric_df['ma_score'] = diffs / std_diff
                
                # Identify anomalies
                threshold = self.detection_config.peak_detection_threshold
                anomalous_points = metric_df[
                    (abs(metric_df['ma_score']) > threshold) & 
                    (~metric_df['moving_avg'].isna())  # Exclude points without a moving avg
                ]
                
                # Create anomaly results
                for _, row in anomalous_points.iterrows():
                    # Determine severity based on deviation
                    severity = "medium"
                    if abs(row['ma_score']) > threshold * 2:
                        severity = "high"
                    elif abs(row['ma_score']) <= threshold * 1.2:
                        severity = "low"
                    
                    anomalies.append(AnomalyResult(
                        resource_id=resource_id,
                        resource_name=resource_name,
                        timestamp=row['timestamp'].isoformat() if isinstance(row['timestamp'], datetime) else str(row['timestamp']),
                        value=float(row['value']),
                        expected_value=float(row['moving_avg']),
                        score=float(row['ma_score']),
                        algorithm="moving_average",
                        metric_name=metric_name,
                        severity=severity
                    ))
        
        return anomalies
    
    def _deduplicate_anomalies(self, anomalies: List[AnomalyResult]) -> List[AnomalyResult]:
        """
        Deduplicate anomalies by resource ID and timestamp.
        Keep the anomaly with the highest score for each combination.
        
        Args:
            anomalies: List of anomaly results
            
        Returns:
            Deduplicated list of anomaly results
        """
        if not anomalies:
            return []
            
        # Create a dictionary to store the best anomaly for each key
        best_anomalies = {}
        
        for anomaly in anomalies:
            key = (anomaly.resource_id, anomaly.timestamp, anomaly.metric_name)
            
            # If this key doesn't exist yet or this anomaly has a higher score
            if key not in best_anomalies or abs(anomaly.score) > abs(best_anomalies[key].score):
                best_anomalies[key] = anomaly
        
        return list(best_anomalies.values())
    
    def generate_anomaly_recommendations(self, anomaly_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on detected anomalies.
        
        Args:
            anomaly_results: Results from detect_anomalies method
            
        Returns:
            List of recommendations
        """
        if anomaly_results.get("status") != "success":
            return []
        
        recommendations = []
        summary = anomaly_results.get("summary", {})
        
        # Skip if no anomalies
        if summary.get("total_anomalies", 0) == 0:
            return []
        
        # Get high severity anomalies
        high_severity = [a for a in anomaly_results.get("anomalies", []) 
                         if a.get("severity") == "high"]
        
        # General recommendation about anomalies
        if high_severity:
            recommendations.append({
                "type": "security",
                "severity": "high",
                "title": "Critical Egress Anomalies Detected",
                "description": f"Detected {len(high_severity)} high-severity anomalies in egress traffic patterns.",
                "actions": [
                    "Investigate resources with anomalous egress patterns immediately",
                    "Check for unauthorized access or data exfiltration",
                    "Review security logs for suspicious activities",
                    "Implement egress filtering if necessary"
                ]
            })
        elif summary.get("total_anomalies", 0) > 0:
            recommendations.append({
                "type": "security",
                "severity": "medium",
                "title": "Egress Anomalies Detected",
                "description": f"Detected {summary.get('total_anomalies')} anomalies in egress traffic patterns.",
                "actions": [
                    "Monitor resources with anomalous egress patterns",
                    "Review recent application changes that might affect network traffic",
                    "Set up alerts for significant traffic spikes"
                ]
            })
        
        # Resource-specific recommendations
        resource_anomalies = anomaly_results.get("by_resource", {})
        for resource_id, anomalies in resource_anomalies.items():
            if not anomalies:
                continue
                
            # Get resource name from first anomaly
            resource_name = anomalies[0].get("resource_name", "Unknown resource")
            
            # Check if this resource has high severity anomalies
            has_high = any(a.get("severity") == "high" for a in anomalies)
            
            if has_high:
                recommendations.append({
                    "type": "resource_specific",
                    "severity": "high",
                    "title": f"Investigate {resource_name} Egress Anomaly",
                    "description": f"Resource has exhibited highly anomalous egress patterns.",
                    "actions": [
                        "Verify all outbound connections from this resource",
                        "Check for unauthorized access",
                        "Review application logs for errors or unexpected behavior",
                        "Consider implementing network security groups for egress control"
                    ],
                    "resource_id": resource_id
                })
        
        # Recommendations for potential cost implications
        if summary.get("total_anomalies", 0) > 5:
            recommendations.append({
                "type": "cost",
                "severity": "medium",
                "title": "Cost Impact from Anomalous Egress",
                "description": "Multiple egress anomalies may lead to unexpected costs.",
                "actions": [
                    "Review egress patterns for cost efficiency",
                    "Set up budget alerts for unexpected traffic spikes",
                    "Consider implementing egress optimization techniques"
                ]
            })
        
        return recommendations
