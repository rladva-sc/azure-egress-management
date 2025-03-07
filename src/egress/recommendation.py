"""
Recommendation engine for Azure egress optimization.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime

from .trend_analysis import TrendAnalyzer
from .cost_analysis import CostAnalyzer
from .anomaly_detection import AnomalyDetector
from ..utils.azure_utils import get_resource_name


@dataclass
class Recommendation:
    """
    Represents a single recommendation.
    """
    id: str  # Unique identifier
    type: str  # Type of recommendation (cost, security, performance, etc.)
    title: str  # Short title
    description: str  # Longer description
    severity: str  # high, medium, low
    actions: List[str] = field(default_factory=list)  # List of suggested actions
    resource_id: Optional[str] = None  # Associated resource
    resource_name: Optional[str] = None  # For display purposes
    potential_savings: Optional[float] = None  # Estimated cost savings
    confidence: float = 1.0  # Confidence score (0-1)
    related_metrics: List[str] = field(default_factory=list)  # Related metrics
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata


class RecommendationEngine:
    """
    Generates recommendations based on trend analysis, cost analysis, and anomaly detection.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the recommendation engine.
        
        Args:
            config: Configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Initialize analyzers
        self.trend_analyzer = TrendAnalyzer(config)
        self.cost_analyzer = CostAnalyzer(config)
        self.anomaly_detector = AnomalyDetector(config)
        
        # Get recommendation configuration
        rec_config = self.config.get("recommendations", {})
        
        # Confidence thresholds
        self.high_confidence_threshold = rec_config.get("high_confidence", 0.8)
        self.low_confidence_threshold = rec_config.get("low_confidence", 0.4)
        
        # Maximum recommendations to return
        self.max_recommendations = rec_config.get("max_recommendations", 15)
        self.max_per_category = rec_config.get("max_per_category", 5)

        # Severity weights for sorting
        self.severity_weights = {
            "high": 3,
            "medium": 2,
            "low": 1
        }
    
    def generate_recommendations(self, metrics_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate comprehensive recommendations based on metrics data.
        
        Args:
            metrics_df: DataFrame with metrics data
            
        Returns:
            Dictionary with recommendations
        """
        if metrics_df.empty:
            return {"status": "no_data", "recommendations": []}
        
        # Generate recommendation sources
        self.logger.info("Generating recommendations from all analysis modules")
        
        # Run all analyses
        trend_results = self.trend_analyzer.analyze_overall_trend(metrics_df)
        cost_results = self.cost_analyzer.analyze_costs(metrics_df)
        anomaly_results = self.anomaly_detector.detect_anomalies(metrics_df)
        
        # Check status of each analysis
        trend_valid = trend_results.get("status") == "success"
        cost_valid = cost_results.get("status") == "success"
        anomaly_valid = anomaly_results.get("status") == "success"
        
        # Collect recommendations from each source
        all_recommendations = []
        
        # Cost recommendations
        if cost_valid:
            cost_recs = self.cost_analyzer.generate_cost_recommendations(cost_results)
            all_recommendations.extend(
                self._transform_cost_recommendations(cost_recs)
            )
        
        # Trend-based recommendations
        if trend_valid:
            trend_recs = self._generate_trend_recommendations(trend_results)
            all_recommendations.extend(trend_recs)
        
        # Anomaly-based recommendations
        if anomaly_valid:
            anomaly_recs = self.anomaly_detector.generate_anomaly_recommendations(anomaly_results)
            all_recommendations.extend(
                self._transform_anomaly_recommendations(anomaly_recs)
            )
        
        # Additional recommendations based on combined insights
        if trend_valid and cost_valid:
            combined_recs = self._generate_combined_recommendations(
                trend_results, cost_results, anomaly_results if anomaly_valid else None
            )
            all_recommendations.extend(combined_recs)
        
        # Remove duplicate recommendations
        unique_recommendations = self._deduplicate_recommendations(all_recommendations)
        
        # Sort and limit recommendations
        final_recommendations = self._prioritize_recommendations(unique_recommendations)
        
        # Create the result
        result = {
            "status": "success" if final_recommendations else "no_recommendations",
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(final_recommendations),
            "sources": {
                "trends": trend_valid,
                "costs": cost_valid,
                "anomalies": anomaly_valid
            },
            "recommendations": final_recommendations
        }
        
        # Add category counts
        category_counts = {}
        for rec in final_recommendations:
            rec_type = rec.get("type", "other")
            if rec_type not in category_counts:
                category_counts[rec_type] = 0
            category_counts[rec_type] += 1
        
        result["categories"] = category_counts
        
        return result
    
    def _transform_cost_recommendations(self, cost_recs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform cost recommendations to standard format.
        
        Args:
            cost_recs: Recommendations from cost analyzer
            
        Returns:
            Standardized list of recommendations
        """
        results = []
        
        for i, rec in enumerate(cost_recs):
            # Generate a unique ID
            rec_id = f"cost_{i}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
            # Create standardized recommendation
            standardized_rec = {
                "id": rec_id,
                "type": rec.get("type", "cost"),
                "title": rec.get("title", "Cost Optimization"),
                "description": rec.get("description", ""),
                "severity": rec.get("severity", "medium"),
                "actions": rec.get("actions", []),
                "potential_savings": rec.get("potential_savings"),
                "confidence": 0.9,  # Cost recommendations are generally high confidence
                "source": "cost_analyzer"
            }
            
            # Add resource info if available
            if "resource_id" in rec:
                standardized_rec["resource_id"] = rec["resource_id"]
                standardized_rec["resource_name"] = get_resource_name(rec["resource_id"])
            
            results.append(standardized_rec)
            
        return results
        
    def _transform_anomaly_recommendations(self, anomaly_recs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform anomaly recommendations to standard format.
        
        Args:
            anomaly_recs: Recommendations from anomaly detector
            
        Returns:
            Standardized list of recommendations
        """
        results = []
        
        for i, rec in enumerate(anomaly_recs):
            # Generate a unique ID
            rec_id = f"anomaly_{i}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
            # Create standardized recommendation
            standardized_rec = {
                "id": rec_id,
                "type": rec.get("type", "anomaly"),
                "title": rec.get("title", "Anomaly Detection"),
                "description": rec.get("description", ""),
                "severity": rec.get("severity", "medium"),
                "actions": rec.get("actions", []),
                "confidence": 0.85 if rec.get("severity") == "high" else 0.7,
                "source": "anomaly_detector"
            }
            
            # Add resource info if available
            if "resource_id" in rec:
                standardized_rec["resource_id"] = rec["resource_id"]
                standardized_rec["resource_name"] = get_resource_name(rec["resource_id"])
            
            results.append(standardized_rec)
            
        return results
    
    def _generate_trend_recommendations(self, trend_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on trend analysis.
        
        Args:
            trend_results: Results from trend analyzer
            
        Returns:
            List of trend-based recommendations
        """
        recommendations = []
        
        if trend_results.get("status") != "success":
            return recommendations
            
        # Get trend parameters
        direction = trend_results.get("direction", "stable")
        strength = trend_results.get("strength", "none")
        normalized_slope = trend_results.get("normalized_slope_percent", 0)
        day_over_day = trend_results.get("day_over_day_percent")
        week_over_week = trend_results.get("week_over_week_percent")
        
        # Recommendation for strong increasing trend
        if direction == "increasing" and strength in ("moderate", "strong"):
            confidence = 0.7
            severity = "medium"
            
            # Adjust severity and confidence based on steepness
            if abs(normalized_slope) > 20:
                severity = "high"
                confidence = 0.85
            
            recommendations.append({
                "id": f"trend_inc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "type": "trend",
                "title": "Rising Egress Traffic Trend Detected",
                "description": (
                    f"Egress traffic is showing a {strength} increasing trend "
                    f"({normalized_slope:.1f}% per data point). This may lead to increased costs."
                ),
                "severity": severity,
                "actions": [
                    "Review recent application or infrastructure changes",
                    "Set up budget alerts for unexpected traffic increases",
                    "Analyze top traffic generating resources",
                    "Consider implementing caching or CDN for frequently accessed content"
                ],
                "confidence": confidence,
                "source": "trend_analyzer",
                "metadata": {
                    "normalized_slope": normalized_slope,
                    "day_over_day": day_over_day,
                    "week_over_week": week_over_week
                }
            })
        
        # Recommendation for weekly patterns if observed
        weekly_patterns = self.trend_analyzer.detect_weekly_patterns(metrics_df)
        if weekly_patterns.get("status") == "success" and weekly_patterns.get("has_pattern", False):
            peak_days = weekly_patterns.get("peak_days", [])
            low_days = weekly_patterns.get("low_days", [])
            
            if peak_days:
                peak_str = ", ".join(peak_days)
                recommendations.append({
                    "id": f"trend_weekly_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    "type": "pattern",
                    "title": "Weekly Egress Pattern Detected",
                    "description": (
                        f"Egress traffic peaks on {peak_str}. Consider scheduling large "
                        f"data transfers during off-peak days."
                    ),
                    "severity": "medium",
                    "actions": [
                        "Schedule batch processing during low traffic days",
                        "Implement auto-scaling based on weekly patterns",
                        "Consider reserved capacity planning based on these patterns"
                    ],
                    "confidence": 0.75,
                    "source": "trend_analyzer",
                    "metadata": {
                        "peak_days": peak_days,
                        "low_days": low_days,
                        "weekend_weekday_percent_diff": weekly_patterns.get("weekend_weekday_percent_diff")
                    }
                })
        
        # Recommendation for hourly patterns if observed
        hourly_patterns = self.trend_analyzer.detect_hourly_patterns(metrics_df)
        if hourly_patterns.get("status") == "success" and hourly_patterns.get("has_pattern", False):
            peak_hours = hourly_patterns.get("peak_hours", [])
            
            if peak_hours:
                peak_hours_formatted = [f"{h}:00" for h in peak_hours]
                peak_str = ", ".join(peak_hours_formatted)
                recommendations.append({
                    "id": f"trend_hourly_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    "type": "pattern",
                    "title": "Daily Egress Pattern Detected",
                    "description": (
                        f"Egress traffic peaks at {peak_str}. Optimize scheduling of "
                        f"data transfers to reduce congestion."
                    ),
                    "severity": "low",
                    "actions": [
                        "Schedule non-critical transfers during off-peak hours",
                        "Consider traffic shaping for better load distribution",
                        "Review applications causing peak hour traffic"
                    ],
                    "confidence": 0.7,
                    "source": "trend_analyzer",
                    "metadata": {
                        "peak_hours": peak_hours,
                        "business_hours_percent_diff": hourly_patterns.get("business_hours_percent_diff")
                    }
                })
                
        return recommendations

    def _generate_combined_recommendations(
        self, trend_results: Dict[str, Any], 
        cost_results: Dict[str, Any],
        anomaly_results: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on combined insights.
        
        Args:
            trend_results: Results from trend analyzer
            cost_results: Results from cost analyzer
            anomaly_results: Results from anomaly detector (optional)
            
        Returns:
            List of recommendations based on combined insights
        """
        recommendations = []
        
        # Check if we have both increasing trend and high costs
        trend_direction = trend_results.get("direction", "stable")
        cost_status = cost_results.get("cost_status", "normal")
        
        if trend_direction == "increasing" and cost_status in ("warning", "critical"):
            recommendations.append({
                "id": f"combined_rising_costs_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "type": "strategic",
                "title": "Strategic Review of Rising Egress Costs",
                "description": (
                    "Both egress traffic and costs are increasing significantly. "
                    "A strategic review of your network architecture is recommended."
                ),
                "severity": "high",
                "actions": [
                    "Conduct comprehensive network architecture review",
                    "Implement cross-region traffic optimization",
                    "Consider dedicated ExpressRoute for consistent high-volume traffic",
                    "Evaluate global content delivery networks",
                    "Implement strict egress monitoring and budget controls"
                ],
                "confidence": 0.9,
                "source": "recommendation_engine",
                "metadata": {
                    "trend_direction": trend_direction,
                    "cost_status": cost_status
                }
            })
        
        # Check if we have anomalies and high costs
        if (anomaly_results and 
            anomaly_results.get("status") == "success" and 
            anomaly_results.get("summary", {}).get("total_anomalies", 0) > 3 and
            cost_status in ("warning", "critical")):
            
            # Get anomaly summary
            anomaly_count = anomaly_results.get("summary", {}).get("total_anomalies", 0)
            high_severity_count = anomaly_results.get("summary", {}).get("severity_counts", {}).get("high", 0)
            
            recommendations.append({
                "id": f"combined_anomaly_costs_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "type": "security_cost",
                "title": "Security and Cost Alert: Unusual Egress Patterns",
                "description": (
                    f"Detected {anomaly_count} anomalies ({high_severity_count} high severity) "
                    f"along with elevated costs. This might indicate security issues with cost implications."
                ),
                "severity": "high" if high_severity_count > 0 else "medium",
                "actions": [
                    "Implement egress security monitoring and filtering",
                    "Review resource access controls",
                    "Conduct security audit of high-egress resources",
                    "Set up alerts for sudden egress spikes",
                    "Consider network security groups with egress rules"
                ],
                "confidence": 0.85 if high_severity_count > 0 else 0.7,
                "source": "recommendation_engine",
                "metadata": {
                    "anomaly_count": anomaly_count,
                    "high_severity_anomalies": high_severity_count,
                    "cost_status": cost_status
                }
            })
            
        # Check for opportunities to implement CDN or caching based on patterns and costs
        if (trend_results.get("status") == "success" and 
            cost_results.get("status") == "success" and
            cost_results.get("total_cost", 0) > self.cost_analyzer.cost_threshold_warning * 0.5):
            
            # See if we have weekly or hourly patterns
            weekly_patterns = self.trend_analyzer.detect_weekly_patterns(metrics_df)
            hourly_patterns = self.trend_analyzer.detect_hourly_patterns(metrics_df)
            
            has_patterns = (weekly_patterns.get("status") == "success" and 
                           weekly_patterns.get("has_pattern", False)) or (
                           hourly_patterns.get("status") == "success" and 
                           hourly_patterns.get("has_pattern", False))
            
            if has_patterns:
                recommendations.append({
                    "id": f"combined_cdn_cache_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    "type": "architecture",
                    "title": "Implement CDN and Caching for Pattern Optimization",
                    "description": (
                        "Your egress shows distinct usage patterns and significant costs. "
                        "Implementing CDN and caching can optimize these patterns and reduce costs."
                    ),
                    "severity": "medium",
                    "actions": [
                        "Implement Azure CDN for static content delivery",
                        "Configure caching with appropriate time-to-live based on patterns",
                        "Set up Front Door for global load balancing",
                        "Apply compression for all compressible responses",
                        "Consider read-replicas for database access optimization"
                    ],
                    "confidence": 0.8,
                    "potential_savings": cost_results.get("total_cost", 0) * 0.3,  # Estimate 30% savings
                    "source": "recommendation_engine"
                })
        
        return recommendations
    
    def _deduplicate_recommendations(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate recommendations.
        
        Args:
            recommendations: List of all recommendations
            
        Returns:
            Deduplicated list of recommendations
        """
        # Use title as the key for deduplication
        unique_recs = {}
        
        for rec in recommendations:
            title = rec.get("title", "")
            
            # If we haven't seen this title before, add it
            if title not in unique_recs:
                unique_recs[title] = rec
            else:
                # If we have seen it, keep the one with higher severity or confidence
                existing_rec = unique_recs[title]
                existing_severity = self.severity_weights.get(existing_rec.get("severity", "low"), 0)
                new_severity = self.severity_weights.get(rec.get("severity", "low"), 0)
                
                # Replace if the new one has higher severity
                if new_severity > existing_severity:
                    unique_recs[title] = rec
                # If same severity, keep the one with higher confidence
                elif new_severity == existing_severity:
                    if rec.get("confidence", 0) > existing_rec.get("confidence", 0):
                        unique_recs[title] = rec
        
        return list(unique_recs.values())
    
    def _prioritize_recommendations(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort and limit recommendations by priority.
        
        Args:
            recommendations: List of unique recommendations
            
        Returns:
            Prioritized and limited list of recommendations
        """
        # If no recommendations, return empty list
        if not recommendations:
            return []
            
        # Sort by severity (high to low) then by confidence (high to low)
        sorted_recs = sorted(
            recommendations,
            key=lambda r: (
                -self.severity_weights.get(r.get("severity", "low"), 0),
                -r.get("confidence", 0)
            )
        )
        
        # Split into categories
        categorized_recs = {}
        for rec in sorted_recs:
            rec_type = rec.get("type", "other")
            if rec_type not in categorized_recs:
                categorized_recs[rec_type] = []
            categorized_recs[rec_type].append(rec)
        
        # Select top N from each category, limited by max_per_category
        selected_recs = []
        for category, recs in categorized_recs.items():
            selected_recs.extend(recs[:self.max_per_category])
        
        # Re-sort the selected recommendations
        selected_recs = sorted(
            selected_recs,
            key=lambda r: (
                -self.severity_weights.get(r.get("severity", "low"), 0),
                -r.get("confidence", 0)
            )
        )
        
        # Apply overall limit
        return selected_recs[:self.max_recommendations]
