
"""
Cost analysis capabilities for Azure egress data.
"""
import logging
import pandas as pd
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ..utils.azure_utils import get_resource_name, get_resource_group, get_subscription_from_resource_id


@dataclass
class EgressCostEstimate:
    """Represents an egress cost estimate for a resource."""
    resource_id: str
    resource_name: str
    resource_type: str
    egress_gb: float
    cost: float
    currency: str = "USD"
    time_period_days: int = 0
    region: str = "unknown"
    additional_info: Dict[str, Any] = field(default_factory=dict)
    

class CostAnalysisError(Exception):
    """Exception raised for errors in cost analysis."""
    pass


class CostAnalyzer:
    """
    Provides cost analysis and estimation for Azure egress data.
    """
    
    # Azure egress pricing tiers (USD per GB)
    # As of 2023, typical prices. These can be overridden via config.
    DEFAULT_PRICING = {
        "zones": {
            "zone1": {
                "name": "North America & Europe",
                "tiers": [
                    {"limit_gb": 10 * 1024, "price": 0.087},  # First 10TB
                    {"limit_gb": 40 * 1024, "price": 0.083},  # Next 40TB
                    {"limit_gb": 100 * 1024, "price": 0.07},  # Next 100TB
                    {"limit_gb": float('inf'), "price": 0.05}  # Beyond 150TB
                ]
            },
            "zone2": {
                "name": "Asia Pacific",
                "tiers": [
                    {"limit_gb": 10 * 1024, "price": 0.12},
                    {"limit_gb": 40 * 1024, "price": 0.11},
                    {"limit_gb": 100 * 1024, "price": 0.08},
                    {"limit_gb": float('inf'), "price": 0.06}
                ]
            },
            "zone3": {
                "name": "Brazil, South America",
                "tiers": [
                    {"limit_gb": 10 * 1024, "price": 0.181},
                    {"limit_gb": 40 * 1024, "price": 0.175},
                    {"limit_gb": 100 * 1024, "price": 0.17},
                    {"limit_gb": float('inf'), "price": 0.16}
                ]
            },
            "default": {
                "name": "Default",
                "tiers": [
                    {"limit_gb": float('inf'), "price": 0.087}  # Default rate
                ]
            }
        },
        "inter_region_multiplier": 1.0,  # Multiplier for traffic between regions
        "intra_region_multiplier": 0.0,  # Often free within same region
        "global_vnet_pricing": 0.035,  # Global VNet peering
        "express_route_premium": 0.04,  # ExpressRoute premium pricing
    }

    # Region to pricing zone mapping
    DEFAULT_REGION_MAP = {
        # North America & Europe (Zone 1)
        "eastus": "zone1",
        "eastus2": "zone1",
        "westus": "zone1",
        "westus2": "zone1",
        "centralus": "zone1",
        "northcentralus": "zone1",
        "southcentralus": "zone1",
        "westcentralus": "zone1",
        "canadacentral": "zone1",
        "canadaeast": "zone1",
        "northeurope": "zone1",
        "westeurope": "zone1",
        "uksouth": "zone1",
        "ukwest": "zone1",
        "francecentral": "zone1",
        "francesouth": "zone1",
        "germanywestcentral": "zone1",
        "germanynorth": "zone1",
        
        # Asia Pacific (Zone 2)
        "eastasia": "zone2",
        "southeastasia": "zone2",
        "australiaeast": "zone2",
        "australiasoutheast": "zone2",
        "australiacentral": "zone2",
        "japaneast": "zone2",
        "japanwest": "zone2",
        "koreacentral": "zone2",
        "koreasouth": "zone2",
        "centralindia": "zone2",
        "southindia": "zone2",
        "westindia": "zone2",
        
        # Brazil & South America (Zone 3)
        "brazilsouth": "zone3",
        "brazilsoutheast": "zone3",
        
        # Default for unknown regions
        "unknown": "default"
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the cost analyzer.
        
        Args:
            config: Configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Load pricing configuration
        cost_config = self.config.get("analysis", {}).get("cost", {})
        
        # Override pricing if provided in config
        self.pricing = cost_config.get("pricing", self.DEFAULT_PRICING)
        self.region_map = cost_config.get("region_map", self.DEFAULT_REGION_MAP)
        
        # Thresholds for cost warnings
        self.cost_threshold_warning = cost_config.get("threshold_warning", 100.0)
        self.cost_threshold_critical = cost_config.get("threshold_critical", 500.0)
        
        # Currency settings
        self.currency = cost_config.get("currency", "USD")
    
    def analyze_costs(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Perform comprehensive cost analysis on collected metrics.
        
        Args:
            df: DataFrame with parsed metrics
            
        Returns:
            Dictionary with cost analysis results
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
            # Calculate total egress in GB
            total_bytes = egress_df['value'].sum()
            total_gb = total_bytes / (1024 * 1024 * 1024)  # Convert bytes to GB
            
            # Group by resource to calculate costs per resource
            resource_costs = []
            resource_totals = egress_df.groupby(['resource_id', 'resource_name', 'resource_type', 'location'])['value'].sum().reset_index()
            
            for _, row in resource_totals.iterrows():
                gb = row['value'] / (1024 * 1024 * 1024)
                cost = self.calculate_egress_cost(gb, row['location'])
                
                resource_costs.append(EgressCostEstimate(
                    resource_id=row['resource_id'],
                    resource_name=row['resource_name'],
                    resource_type=row['resource_type'],
                    egress_gb=gb,
                    cost=cost,
                    region=row['location']
                ))
            
            # Group by region to calculate costs per region
            region_costs = {}
            if 'location' in egress_df.columns:
                region_totals = egress_df.groupby('location')['value'].sum().reset_index()
                for _, row in region_totals.iterrows():
                    gb = row['value'] / (1024 * 1024 * 1024)
                    cost = self.calculate_egress_cost(gb, row['location'])
                    region_costs[row['location']] = {
                        "egress_gb": gb,
                        "cost": cost
                    }
            
            # Calculate total cost
            total_cost = sum(res.cost for res in resource_costs)
            
            # Calculate time period if timestamps are available
            time_period_days = 0
            if 'timestamp' in egress_df.columns and len(egress_df) > 1:
                try:
                    # Convert to datetime if it's a string
                    if isinstance(egress_df['timestamp'].iloc[0], str):
                        egress_df['timestamp'] = pd.to_datetime(egress_df['timestamp'])
                    
                    min_date = egress_df['timestamp'].min()
                    max_date = egress_df['timestamp'].max()
                    time_delta = max_date - min_date
                    time_period_days = time_delta.days + (time_delta.seconds / 86400)
                except Exception as ex:
                    self.logger.warning(f"Could not calculate time period: {ex}")
            
            # Calculate monthly projections if time period > 0
            monthly_projection = None
            if time_period_days > 0:
                # Project to 30 days
                monthly_factor = 30 / time_period_days
                monthly_projection = {
                    "egress_gb": total_gb * monthly_factor,
                    "cost": total_cost * monthly_factor
                }
            
            # Determine cost status based on thresholds
            cost_status = "normal"
            if total_cost > self.cost_threshold_critical:
                cost_status = "critical"
            elif total_cost > self.cost_threshold_warning:
                cost_status = "warning"
            
            # Format results
            cost_analysis = {
                "status": "success",
                "cost_status": cost_status,
                "egress_gb": total_gb,
                "total_cost": total_cost,
                "currency": self.currency,
                "time_period_days": time_period_days,
                "resources": [
                    {
                        "resource_id": res.resource_id,
                        "resource_name": res.resource_name,
                        "resource_type": res.resource_type,
                        "region": res.region,
                        "egress_gb": res.egress_gb,
                        "cost": res.cost,
                        "percentage_of_total": (res.cost / total_cost * 100) if total_cost > 0 else 0
                    } for res in resource_costs
                ],
                "by_region": {
                    region: {
                        "egress_gb": data["egress_gb"],
                        "cost": data["cost"],
                        "percentage_of_total": (data["cost"] / total_cost * 100) if total_cost > 0 else 0
                    } for region, data in region_costs.items()
                }
            }
            
            # Add monthly projection if available
            if monthly_projection:
                cost_analysis["monthly_projection"] = monthly_projection
                
                # Add warning if monthly projection exceeds thresholds
                monthly_cost = monthly_projection["cost"]
                if monthly_cost > self.cost_threshold_critical and cost_status != "critical":
                    cost_analysis["projection_warning"] = "critical"
                elif monthly_cost > self.cost_threshold_warning and cost_status == "normal":
                    cost_analysis["projection_warning"] = "warning"
            
            return cost_analysis
            
        except Exception as ex:
            self.logger.error(f"Error analyzing costs: {str(ex)}")
            return {
                "status": "error",
                "error": str(ex)
            }
    
    def calculate_egress_cost(self, gb: float, region: str = "unknown") -> float:
        """
        Calculate egress cost based on data transfer amount and region.
        
        Args:
            gb: Amount of data in gigabytes
            region: Azure region
            
        Returns:
            Calculated cost
        """
        # Normalize region name and map to pricing zone
        region = region.lower() if region else "unknown"
        zone = self.region_map.get(region, "default")
        
        # Get pricing tiers for the zone
        zone_pricing = self.pricing["zones"].get(zone, self.pricing["zones"]["default"])
        tiers = zone_pricing["tiers"]
        
        # Calculate cost based on tiered pricing
        remaining_gb = gb
        total_cost = 0.0
        
        for i, tier in enumerate(tiers):
            # For first tier, calculate from 0 to limit
            if i == 0:
                tier_gb = min(remaining_gb, tier["limit_gb"])
            # For subsequent tiers, calculate from previous tier limit to current limit
            else:
                previous_limit = tiers[i-1]["limit_gb"]
                tier_gb = min(remaining_gb, tier["limit_gb"] - previous_limit)
                
            # Add cost for this tier
            total_cost += tier_gb * tier["price"]
            remaining_gb -= tier_gb
            
            # If no more data to calculate, exit
            if remaining_gb <= 0:
                break
        
        return total_cost
    
    def generate_cost_recommendations(self, cost_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate cost saving recommendations based on cost analysis.
        
        Args:
            cost_analysis: Results from analyze_costs
            
        Returns:
            List of cost saving recommendations
        """
        if cost_analysis.get("status") != "success":
            return []
            
        recommendations = []
        
        # High-level cost status recommendations
        if cost_analysis.get("cost_status") == "critical":
            recommendations.append({
                "type": "cost",
                "severity": "high",
                "title": "Critical Egress Cost Alert",
                "description": "Your egress costs have exceeded the critical threshold. Review and optimize top consumers immediately.",
                "potential_savings": cost_analysis.get("total_cost", 0) * 0.3,  # Estimate 30% savings
                "actions": [
                    "Implement content delivery network (CDN) for static content",
                    "Review and adjust application egress patterns",
                    "Consider VNet peering for internal communication"
                ]
            })
        elif cost_analysis.get("cost_status") == "warning":
            recommendations.append({
                "type": "cost",
                "severity": "medium",
                "title": "High Egress Cost Warning",
                "description": "Your egress costs are approaching critical levels. Consider optimization measures.",
                "potential_savings": cost_analysis.get("total_cost", 0) * 0.2,  # Estimate 20% savings
                "actions": [
                    "Analyze top consumers and identify optimization opportunities",
                    "Implement caching where appropriate",
                    "Optimize data transfer patterns"
                ]
            })
        
        # Recommendations for high-cost resources
        resources = cost_analysis.get("resources", [])
        resources.sort(key=lambda x: x["cost"], reverse=True)
        
        # Focus on top 3 resources if they account for significant percentage
        for resource in resources[:3]:
            if resource["percentage_of_total"] >= 15:  # Resource uses 15% or more of total cost
                resource_type = resource["resource_type"].lower()
                
                # VM-specific recommendations
                if "virtualmachine" in resource_type:
                    recommendations.append({
                        "type": "resource_specific",
                        "severity": "medium",
                        "title": f"High VM Egress: {resource['resource_name']}",
                        "description": f"This virtual machine accounts for {resource['percentage_of_total']:.1f}% of your total egress costs.",
                        "potential_savings": resource["cost"] * 0.4,  # Estimate 40% savings possible
                        "actions": [
                            "Check for unnecessary file transfers or backups",
                            "Review application architecture for bandwidth efficiency",
                            "Consider compressed data formats",
                            "Implement regional replication to reduce cross-region traffic"
                        ],
                        "resource_id": resource["resource_id"]
                    })
                # App Service recommendations
                elif "site" in resource_type:
                    recommendations.append({
                        "type": "resource_specific",
                        "severity": "medium",
                        "title": f"High App Service Egress: {resource['resource_name']}",
                        "description": f"This App Service accounts for {resource['percentage_of_total']:.1f}% of your total egress costs.",
                        "potential_savings": resource["cost"] * 0.5,  # Estimate 50% savings possible
                        "actions": [
                            "Implement Azure Front Door or CDN for static content",
                            "Enable compression for HTTP responses",
                            "Review API responses for unnecessary data",
                            "Consider using Azure Cache for frequently accessed data"
                        ],
                        "resource_id": resource["resource_id"]
                    })
        
        # Region-specific recommendations
        regions = cost_analysis.get("by_region", {})
        multi_region = len(regions) > 1
        
        if multi_region:
            region_items = list(regions.items())
            region_items.sort(key=lambda x: x[1]["cost"], reverse=True)
            top_region = region_items[0][0] if region_items else "unknown"
            
            # Check if there's significant cross-region traffic
            if len(region_items) >= 2 and (region_items[1][1]["cost"] / cost_analysis.get("total_cost", 1)) > 0.2:
                recommendations.append({
                    "type": "region",
                    "severity": "medium",
                    "title": "Significant Cross-Region Traffic",
                    "description": "You have substantial egress traffic spanning multiple regions which incurs higher costs.",
                    "potential_savings": cost_analysis.get("total_cost", 0) * 0.15,  # Estimate 15% savings
                    "actions": [
                        "Consolidate workloads to fewer regions where possible",
                        "Implement region-paired storage accounts",
                        "Use Azure CDN for cross-region content delivery",
                        "Consider Global VNet peering or ExpressRoute for consistent high-volume traffic"
                    ]
                })
            
            # If data is primarily in one region, recommend consolidation
            if top_region != "unknown" and regions[top_region]["percentage_of_total"] > 70:
                recommendations.append({
                    "type": "region",
                    "severity": "low",
                    "title": f"Consider Consolidation to {top_region}",
                    "description": f"{top_region} accounts for {regions[top_region]['percentage_of_total']:.1f}% of egress. Consider consolidating more workloads here.",
                    "potential_savings": cost_analysis.get("total_cost", 0) * 0.08,  # Estimate 8% savings
                    "actions": [
                        f"Move compatible workloads to {top_region}",
                        "Implement regional data replication",
                        "Review application architecture for region-awareness"
                    ]
                })
        
        # Monthly projection recommendations
        if "monthly_projection" in cost_analysis:
            monthly_cost = cost_analysis["monthly_projection"]["cost"]
            if monthly_cost > cost_analysis.get("total_cost", 0) * 1.3:  # 30% higher than current
                recommendations.append({
                    "type": "projection",
                    "severity": "medium",
                    "title": "Increasing Cost Trend Detected",
                    "description": f"Monthly projected cost of {monthly_cost:.2f} {self.currency} is significantly higher than current spend.",
                    "potential_savings": monthly_cost * 0.25,  # Estimate 25% savings
                    "actions": [
                        "Set up Azure Budgets for proactive alerts",
                        "Implement auto-scaling for predictable traffic patterns",
                        "Analyze recent traffic growth patterns",
                        "Consider reserved bandwidth options for ExpressRoute"
                    ]
                })
        
        # Add general recommendation if no specific ones were generated
        if not recommendations:
            recommendations.append({
                "type": "general",
                "severity": "low",
                "title": "General Cost Optimization",
                "description": "Consider these general egress cost optimization strategies.",
                "potential_savings": cost_analysis.get("total_cost", 0) * 0.1,  # Estimate 10% savings
                "actions": [
                    "Use Azure CDN for static content delivery",
                    "Implement data compression for all transfers",
                    "Consider proximity placement groups for related resources",
                    "Review Azure Virtual Network design for traffic optimization"
                ]
            })
        
        return recommendations
    
    def project_costs(
        self, 
        cost_analysis: Dict[str, Any],
        projection_months: int = 12,
        trend_factor: float = 0
    ) -> Dict[str, Any]:
        """
        Project costs into the future based on current usage.
        
        Args:
            cost_analysis: Results from analyze_costs
            projection_months: Number of months to project
            trend_factor: Monthly percentage increase (positive) or decrease (negative)
            
        Returns:
            Dictionary with cost projections
        """
        if cost_analysis.get("status") != "success":
            return {"status": "error", "message": "Invalid cost analysis data"}
        
        # Get monthly values (either from projection or by normalizing current)
        if "monthly_projection" in cost_analysis:
            monthly_gb = cost_analysis["monthly_projection"]["egress_gb"]
            monthly_cost = cost_analysis["monthly_projection"]["cost"]
        else:
            # If we have time_period_days, normalize to a month (30 days)
            time_period = cost_analysis.get("time_period_days", 30)
            if time_period <= 0:
                time_period = 30  # Default to assuming data is for 30 days
                
            monthly_factor = 30 / time_period
            monthly_gb = cost_analysis.get("egress_gb", 0) * monthly_factor
            monthly_cost = cost_analysis.get("total_cost", 0) * monthly_factor
        
        # Generate projections for each future month
        projections = []
        cumulative_cost = 0
        
        for month in range(1, projection_months + 1):
            # Apply trend factor compounded monthly
            trend_multiplier = (1 + trend_factor/100) ** (month - 1)
            month_gb = monthly_gb * trend_multiplier
            month_cost = monthly_cost * trend_multiplier
            cumulative_cost += month_cost
            
            projections.append({
                "month": month,
                "egress_gb": month_gb,
                "cost": month_cost,
                "cumulative_cost": cumulative_cost
            })
        
        return {
            "status": "success",
            "base_monthly_cost": monthly_cost,
            "base_monthly_gb": monthly_gb,
            "trend_factor_percent": trend_factor,
            "currency": self.currency,
            "total_projected_cost": cumulative_cost,
            "monthly_projections": projections
        }
