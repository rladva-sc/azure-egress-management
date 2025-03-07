"""
Trend analysis functionality for Azure egress metrics.
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta

class TrendAnalyzer:
    """
    Analyzes egress metrics to detect trends and patterns.
    """
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the trend analyzer.
        
        Args:
            config: Configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Get trend analysis configuration
        trend_config = self.config.get("analysis", {}).get("trends", {})
        
        # Threshold for considering a trend significant (percent change)
        self.significant_change_threshold = trend_config.get("significant_change_threshold", 10.0)
        
        # Minimum number of data points needed for trend analysis
        self.min_data_points = trend_config.get("min_data_points", 3)
        
        # Lookback window for trend comparison (in days)
        self.lookback_window = trend_config.get("lookback_window", 7)
    
    def analyze_overall_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze the overall trend of egress traffic.
        
        Args:
            df: DataFrame with egress metrics
            
        Returns:
            Dictionary with trend analysis results
        """
        if df.empty:
            return {"status": "no_data"}
        
        # Filter to egress metrics only (outbound traffic)
        egress_df = df[
            (df['metric_name'].str.contains('out', case=False, na=False)) | 
            (df['metric_name'].str.contains('sent', case=False, na=False)) |
            (df['metric_name'].str.contains('egress', case=False, na=False))
        ].copy()
        
        if egress_df.empty:
            return {"status": "no_egress_data"}
        
        try:
            # Group by timestamp and calculate total
            overall_by_time = egress_df.groupby('timestamp')['value'].sum().reset_index()
            overall_by_time = overall_by_time.sort_values('timestamp')
            
            # If we don't have enough data points
            if len(overall_by_time) < self.min_data_points:
                return {
                    "status": "insufficient_data",
                    "message": f"Need at least {self.min_data_points} data points for trend analysis",
                    "data_points": len(overall_by_time)
                }
            
            # Calculate rate of change
            overall_by_time['prev_value'] = overall_by_time['value'].shift(1)
            overall_by_time['change'] = overall_by_time['value'] - overall_by_time['prev_value']
            overall_by_time['pct_change'] = (
                overall_by_time['change'] / overall_by_time['prev_value'] * 100
            ).replace([np.inf, -np.inf], np.nan)
            
            # Calculate trend metrics
            avg_pct_change = overall_by_time['pct_change'].mean()
            
            # Calculate linear regression trend
            if len(overall_by_time) >= 3:  # Need at least 3 points for meaningful regression
                x = np.arange(len(overall_by_time))
                y = overall_by_time['value'].values
                
                # Simple linear regression
                slope, intercept = np.polyfit(x, y, 1)
                
                # Calculate R-squared
                y_pred = slope * x + intercept
                ss_total = np.sum((y - np.mean(y)) ** 2)
                ss_residual = np.sum((y - y_pred) ** 2)
                r_squared = 1 - (ss_residual / ss_total) if ss_total != 0 else 0
                
                # Calculate trend strength and confidence
                trend_confidence = min(abs(r_squared * 100), 100)  # As percentage
                
                # Determine trend strength based on slope and average value
                avg_value = overall_by_time['value'].mean()
                normalized_slope = (slope / avg_value) * 100 if avg_value != 0 else 0
                
                # Get trend direction
                if abs(normalized_slope) < 1.0:  # Less than 1% change per data point
                    trend_direction = "stable"
                    trend_strength = "none"
                elif normalized_slope > 0:
                    trend_direction = "increasing"
                    if normalized_slope > 10.0:
                        trend_strength = "strong"
                    elif normalized_slope > 5.0:
                        trend_strength = "moderate"
                    else:
                        trend_strength = "weak"
                else:  # negative slope
                    trend_direction = "decreasing"
                    if normalized_slope < -10.0:
                        trend_strength = "strong"
                    elif normalized_slope < -5.0:
                        trend_strength = "moderate"
                    else:
                        trend_strength = "weak"
            else:
                # Not enough data points for regression
                slope = 0
                r_squared = 0
                trend_direction = "unknown"
                trend_strength = "unknown"
                trend_confidence = 0
                normalized_slope = 0
            
            # Get rate of change for recent data points
            if len(overall_by_time) > 1:
                latest_pct_change = overall_by_time['pct_change'].dropna().iloc[-1]
            else:
                latest_pct_change = 0
            
            # Get min/max/current values
            min_value = overall_by_time['value'].min()
            max_value = overall_by_time['value'].max()
            current_value = overall_by_time['value'].iloc[-1]
            
            # Calculate day-over-day and week-over-week changes if possible
            day_over_day = None
            week_over_week = None
            
            if len(overall_by_time) >= 2:
                day_over_day = (
                    (overall_by_time['value'].iloc[-1] - overall_by_time['value'].iloc[-2]) /
                    overall_by_time['value'].iloc[-2] * 100 if overall_by_time['value'].iloc[-2] != 0 else 0
                )
            
            # Check if we have data from at least a week ago (approximation)
            if len(overall_by_time) >= 7:
                week_over_week = (
                    (overall_by_time['value'].iloc[-1] - overall_by_time['value'].iloc[-7]) /
                    overall_by_time['value'].iloc[-7] * 100 if overall_by_time['value'].iloc[-7] != 0 else 0
                )
            
            return {
                "status": "success",
                "direction": trend_direction,
                "strength": trend_strength,
                "confidence": trend_confidence,
                "avg_change_percent": float(avg_pct_change),
                "latest_change_percent": float(latest_pct_change),
                "slope": float(slope),
                "normalized_slope_percent": float(normalized_slope),
                "r_squared": float(r_squared),
                "min_value": float(min_value),
                "max_value": float(max_value),
                "current_value": float(current_value),
                "day_over_day_percent": float(day_over_day) if day_over_day is not None else None,
                "week_over_week_percent": float(week_over_week) if week_over_week is not None else None,
                "timepoints": len(overall_by_time)
            }
            
        except Exception as ex:
            self.logger.error(f"Error analyzing overall trend: {ex}")
            return {
                "status": "error",
                "error": str(ex)
            }
    
    def analyze_trends_by_group(
        self, 
        df: pd.DataFrame, 
        group_column: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze egress trends for each value in the specified grouping column.
        
        Args:
            df: DataFrame with egress metrics
            group_column: Column to group by (e.g., 'resource_type', 'resource_name')
            
        Returns:
            Dictionary with trend analysis results keyed by group values
        """
        if df.empty:
            return {}
        
        # Filter to egress metrics only
        egress_df = df[
            (df['metric_name'].str.contains('out', case=False, na=False)) | 
            (df['metric_name'].str.contains('sent', case=False, na=False)) |
            (df['metric_name'].str.contains('egress', case=False, na=False))
        ].copy()
        
        if egress_df.empty:
            return {}
        
        # Check if the group column exists
        if group_column not in egress_df.columns:
            self.logger.error(f"Group column '{group_column}' not found in DataFrame")
            return {}
        
        results = {}
        
        # Analyze trends for each group
        for group_value, group_df in egress_df.groupby(group_column):
            # Skip empty or invalid group values
            if group_value is None or group_value == '':
                continue
                
            # Analyze trend for this group (resource type, name, etc.)
            trend_data = self._analyze_single_group_trend(group_df)
            
            if trend_data.get("status") == "success":
                results[str(group_value)] = trend_data
                
        return results
    
    def _analyze_single_group_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze trend for a single group of data.
        
        Args:
            df: DataFrame with egress metrics for a single group
            
        Returns:
            Dictionary with trend analysis results
        """
        try:
            # Group by timestamp and calculate total
            by_time = df.groupby('timestamp')['value'].sum().reset_index()
            by_time = by_time.sort_values('timestamp')
            
            # If we don't have enough data points
            if len(by_time) < self.min_data_points:
                return {
                    "status": "insufficient_data",
                    "message": f"Need at least {self.min_data_points} data points for trend analysis",
                    "data_points": len(by_time)
                }
            
            # Calculate rate of change
            by_time['prev_value'] = by_time['value'].shift(1)
            by_time['change'] = by_time['value'] - by_time['prev_value']
            by_time['pct_change'] = (
                by_time['change'] / by_time['prev_value'] * 100
            ).replace([np.inf, -np.inf], np.nan)
            
            # Calculate trend metrics
            avg_pct_change = by_time['pct_change'].mean()
            
            # Calculate linear regression trend
            if len(by_time) >= 3:  # Need at least 3 points for meaningful regression
                x = np.arange(len(by_time))
                y = by_time['value'].values
                
                # Simple linear regression
                slope, intercept = np.polyfit(x, y, 1)
                
                # Calculate R-squared
                y_pred = slope * x + intercept
                ss_total = np.sum((y - np.mean(y)) ** 2)
                ss_residual = np.sum((y - y_pred) ** 2)
                r_squared = 1 - (ss_residual / ss_total) if ss_total != 0 else 0
                
                # Calculate trend strength and confidence
                trend_confidence = min(abs(r_squared * 100), 100)  # As percentage
                
                # Determine trend strength based on slope and average value
                avg_value = by_time['value'].mean()
                normalized_slope = (slope / avg_value) * 100 if avg_value != 0 else 0
                
                # Get trend direction
                if abs(normalized_slope) < 1.0:  # Less than 1% change per data point
                    trend_direction = "stable"
                    trend_strength = "none"
                elif normalized_slope > 0:
                    trend_direction = "increasing"
                    if normalized_slope > 10.0:
                        trend_strength = "strong"
                    elif normalized_slope > 5.0:
                        trend_strength = "moderate"
                    else:
                        trend_strength = "weak"
                else:  # negative slope
                    trend_direction = "decreasing"
                    if normalized_slope < -10.0:
                        trend_strength = "strong"
                    elif normalized_slope < -5.0:
                        trend_strength = "moderate"
                    else:
                        trend_strength = "weak"
            else:
                # Not enough data points for regression
                slope = 0
                r_squared = 0
                trend_direction = "unknown"
                trend_strength = "unknown"
                trend_confidence = 0
                normalized_slope = 0
            
            # Get min/max/current values
            min_value = by_time['value'].min()
            max_value = by_time['value'].max()
            current_value = by_time['value'].iloc[-1]
            
            return {
                "status": "success",
                "direction": trend_direction,
                "strength": trend_strength,
                "confidence": trend_confidence,
                "avg_change_percent": float(avg_pct_change),
                "slope": float(slope),
                "normalized_slope_percent": float(normalized_slope),
                "r_squared": float(r_squared),
                "min_value": float(min_value),
                "max_value": float(max_value),
                "current_value": float(current_value),
                "timepoints": len(by_time)
            }
            
        except Exception as ex:
            self.logger.error(f"Error analyzing group trend: {ex}")
            return {
                "status": "error",
                "error": str(ex)
            }

    def detect_weekly_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect weekly patterns in egress data.
        
        Args:
            df: DataFrame with egress metrics
            
        Returns:
            Dictionary with weekly pattern analysis
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
            # Make sure we have datetime objects
            if isinstance(egress_df['timestamp'].iloc[0], str):
                egress_df['timestamp'] = pd.to_datetime(egress_df['timestamp'])
                
            # Extract day of week (0=Monday, 6=Sunday)
            egress_df['day_of_week'] = egress_df['timestamp'].dt.dayofweek
            
            # Group by day of week and calculate average
            day_of_week_avg = egress_df.groupby('day_of_week')['value'].mean().reset_index()
            
            # If not enough days, can't detect weekly patterns
            if len(day_of_week_avg) < 3:  # Need at least 3 days to detect patterns
                return {
                    "status": "insufficient_data",
                    "message": "Need data from at least 3 different days of the week",
                    "days_available": len(day_of_week_avg)
                }
            
            # Day names for output
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            # Calculate peak days (>20% above average)
            overall_avg = day_of_week_avg['value'].mean()
            peak_threshold = overall_avg * 1.2
            peak_days = day_of_week_avg[day_of_week_avg['value'] >= peak_threshold]
            
            # Calculate low days (<80% of average)
            low_threshold = overall_avg * 0.8
            low_days = day_of_week_avg[day_of_week_avg['value'] <= low_threshold]
            
            # Convert day numbers to day names
            peak_day_names = [day_names[day] for day in peak_days['day_of_week'].values]
            low_day_names = [day_names[day] for day in low_days['day_of_week'].values]
            
            # Calculate stats for each day
            daily_stats = {}
            for _, row in day_of_week_avg.iterrows():
                day_num = row['day_of_week']
                day_name = day_names[day_num]
                daily_stats[day_name] = {
                    "average_value": float(row['value']),
                    "percent_of_overall_avg": float(row['value'] / overall_avg * 100) if overall_avg != 0 else 0
                }
            
            # Calculate weekend vs weekday
            weekday_mask = egress_df['day_of_week'] < 5  # 0-4 are weekdays
            weekend_mask = egress_df['day_of_week'] >= 5  # 5-6 are weekend
            
            weekday_avg = egress_df[weekday_mask]['value'].mean()
            weekend_avg = egress_df[weekend_mask]['value'].mean()
            
            # Calculate weekend-weekday difference
            weekend_weekday_diff = 0
            if weekday_avg > 0:
                weekend_weekday_diff = (weekend_avg - weekday_avg) / weekday_avg * 100
            
            # Determine if there's a weekly pattern
            has_pattern = len(peak_day_names) > 0 or len(low_day_names) > 0 or abs(weekend_weekday_diff) > 15
            
            return {
                "status": "success",
                "has_pattern": has_pattern,
                "peak_days": peak_day_names,
                "low_days": low_day_names,
                "weekend_avg": float(weekend_avg),
                "weekday_avg": float(weekday_avg),
                "weekend_weekday_percent_diff": float(weekend_weekday_diff),
                "daily_stats": daily_stats
            }
            
        except Exception as ex:
            self.logger.error(f"Error detecting weekly patterns: {ex}")
            return {
                "status": "error",
                "error": str(ex)
            }

    def detect_hourly_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect hourly patterns in egress data.
        
        Args:
            df: DataFrame with egress metrics
            
        Returns:
            Dictionary with hourly pattern analysis
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
            # Make sure we have datetime objects
            if isinstance(egress_df['timestamp'].iloc[0], str):
                egress_df['timestamp'] = pd.to_datetime(egress_df['timestamp'])
                
            # Extract hour of day (0-23)
            egress_df['hour_of_day'] = egress_df['timestamp'].dt.hour
            
            # Group by hour of day and calculate average
            hour_of_day_avg = egress_df.groupby('hour_of_day')['value'].mean().reset_index()
            
            # If not enough hours, can't detect hourly patterns
            if len(hour_of_day_avg) < 6:  # Need at least 6 hours to detect patterns
                return {
                    "status": "insufficient_data",
                    "message": "Need data from at least 6 different hours of the day",
                    "hours_available": len(hour_of_day_avg)
                }
            
            # Calculate peak hours (>20% above average)
            overall_avg = hour_of_day_avg['value'].mean()
            peak_threshold = overall_avg * 1.2
            peak_hours = hour_of_day_avg[hour_of_day_avg['value'] >= peak_threshold]
            
            # Calculate low hours (<80% of average)
            low_threshold = overall_avg * 0.8
            low_hours = hour_of_day_avg[hour_of_day_avg['value'] <= low_threshold]
            
            # Calculate business hours vs non-business hours
            business_mask = (egress_df['hour_of_day'] >= 9) & (egress_df['hour_of_day'] < 17)  # 9am-5pm
            after_hours_mask = ~business_mask
            
            business_avg = egress_df[business_mask]['value'].mean()
            after_hours_avg = egress_df[after_hours_mask]['value'].mean()
            
            # Calculate business hours-after hours difference
            business_hours_diff = 0
            if after_hours_avg > 0:
                business_hours_diff = (business_avg - after_hours_avg) / after_hours_avg * 100
            
            # Calculate stats for each hour
            hourly_stats = {}
            for _, row in hour_of_day_avg.iterrows():
                hour = row['hour_of_day']
                hourly_stats[str(hour)] = {
                    "average_value": float(row['value']),
                    "percent_of_overall_avg": float(row['value'] / overall_avg * 100) if overall_avg != 0 else 0
                }
            
            # Determine if there's an hourly pattern
            has_pattern = len(peak_hours) > 0 or len(low_hours) > 0 or abs(business_hours_diff) > 20
            
            return {
                "status": "success",
                "has_pattern": has_pattern,
                "peak_hours": peak_hours['hour_of_day'].tolist(),
                "low_hours": low_hours['hour_of_day'].tolist(),
                "business_hours_avg": float(business_avg),
                "after_hours_avg": float(after_hours_avg),
                "business_hours_percent_diff": float(business_hours_diff),
                "hourly_stats": hourly_stats
            }
            
        except Exception as ex:
            self.logger.error(f"Error detecting hourly patterns: {ex}")
            return {
                "status": "error",
                "error": str(ex)
            }
