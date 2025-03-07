"""
Main dashboard application for Azure Egress Management.
"""
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

from ..auth.azure_auth import AzureAuthenticator
from ..egress.storage import MetricsStorage
from ..egress.monitor import EgressMonitor
from ..egress.cost_analysis import CostAnalyzer
from ..egress.trend_analysis import TrendAnalyzer
from ..egress.anomaly_detection import AnomalyDetector
from ..egress.recommendation import RecommendationEngine
from ..utils.config_utils import load_config
from ..utils.logging_utils import setup_logging

# Setup logging
logger = setup_logging()

# Load configuration
config = load_config()
dashboard_config = config.get("dashboard", {})

# Initialize the Dash app with Bootstrap CSS
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Azure Egress Dashboard",
    suppress_callback_exceptions=True
)
server = app.server

# Initialize storage for data access
storage = MetricsStorage(config)

# Initialize authenticator (will be used when needed)
auth_method = config.get("azure", {}).get("auth_method", "default")
authenticator = None

# Function to load the latest metrics data
def load_latest_metrics() -> Tuple[pd.DataFrame, str]:
    """
    Load the latest metrics data from storage.
    
    Returns:
        Tuple of (DataFrame, collection_id)
    """
    try:
        # Get list of available collections
        collections = storage.list_available_collections()
        
        if not collections:
            logger.warning("No data collections found")
            return pd.DataFrame(), ""
            
        # Sort by timestamp (newest first) and get the latest
        latest = collections[0]
        collection_id = latest.get("id", "")
        
        # Load the data
        metrics_data = storage.retrieve_metrics(collection_id)
        
        # Parse into DataFrame
        df = parse_metrics_to_dataframe(metrics_data)
        
        return df, collection_id
    except Exception as ex:
        logger.error(f"Error loading metrics data: {ex}")
        return pd.DataFrame(), ""

# Function to parse metrics into DataFrame
def parse_metrics_to_dataframe(metrics_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Parse metrics data into a DataFrame.
    
    Args:
        metrics_data: Raw metrics data
        
    Returns:
        DataFrame with parsed metrics
    """
    rows = []
    
    # Process each resource type
    resources = metrics_data.get("resources", {})
    for resource_type, resource_dict in resources.items():
        # Process each resource
        for resource_id, resource_data in resource_dict.items():
            resource_name = resource_data.get("name", "Unknown")
            resource_group = resource_data.get("resource_group", "Unknown")
            
            # Process each metric
            metrics = resource_data.get("metrics", {})
            for metric_name, metric_data in metrics.items():
                # Get values and timestamps
                values = metric_data.get("values", [])
                times = metric_data.get("times", [])
                
                if not values or not times or len(values) != len(times):
                    continue
                
                # Add rows for each data point
                for i in range(len(values)):
                    rows.append({
                        "timestamp": times[i],
                        "value": values[i],
                        "metric_name": metric_data.get("name", metric_name),
                        "display_name": metric_data.get("display_name", metric_name),
                        "unit": metric_data.get("unit", "Count"),
                        "resource_id": resource_id,
                        "resource_name": resource_name,
                        "resource_group": resource_group,
                        "resource_type": resource_type,
                        "location": resource_data.get("location", "unknown")
                    })
    
    # Create DataFrame
    if rows:
        df = pd.DataFrame(rows)
        
        # Convert timestamp to datetime if it's a string
        if "timestamp" in df.columns and isinstance(df["timestamp"].iloc[0], str):
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            
        return df
    
    return pd.DataFrame()

# Function to load available metrics collections
def load_available_collections() -> List[Dict[str, Any]]:
    """
    Load list of available metrics collections.
    
    Returns:
        List of collection info dictionaries
    """
    try:
        return storage.list_available_collections()
    except Exception as ex:
        logger.error(f"Error loading collections: {ex}")
        return []

# Function to load and analyze metrics
def analyze_metrics(metrics_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Perform analysis on metrics data.
    
    Args:
        metrics_df: DataFrame with metrics
        
    Returns:
        Dictionary with analysis results
    """
    results = {}
    
    try:
        # Initialize analyzers
        trend_analyzer = TrendAnalyzer(config)
        cost_analyzer = CostAnalyzer(config)
        anomaly_detector = AnomalyDetector(config)
        recommendation_engine = RecommendationEngine(config)
        
        # Perform analysis
        if not metrics_df.empty:
            results["trend"] = trend_analyzer.analyze_overall_trend(metrics_df)
            results["weekly_patterns"] = trend_analyzer.detect_weekly_patterns(metrics_df)
            results["hourly_patterns"] = trend_analyzer.detect_hourly_patterns(metrics_df)
            results["costs"] = cost_analyzer.analyze_costs(metrics_df)
            results["anomalies"] = anomaly_detector.detect_anomalies(metrics_df)
            results["recommendations"] = recommendation_engine.generate_recommendations(metrics_df)
    except Exception as ex:
        logger.error(f"Error analyzing metrics: {ex}")
        results["error"] = str(ex)
        
    return results

# Create the dashboard layout
app.layout = dbc.Container([
    # Top navigation bar
    dbc.Navbar(
        dbc.Container([
            html.A(
                dbc.Row([
                    dbc.Col(dbc.NavbarBrand("Azure Egress Management Dashboard", className="ms-2")),
                ], align="center"),
                href="/",
                style={"textDecoration": "none"},
            ),
            dbc.NavbarToggler(id="navbar-toggler"),
            dbc.Collapse(
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink("Overview", href="/")),
                    dbc.NavItem(dbc.NavLink("Resources", href="/resources")),
                    dbc.NavItem(dbc.NavLink("Trends", href="/trends")),
                    dbc.NavItem(dbc.NavLink("Costs", href="/costs")),
                    dbc.NavItem(dbc.NavLink("Anomalies", href="/anomalies")),
                    dbc.NavItem(dbc.NavLink("Recommendations", href="/recommendations")),
                    dbc.NavItem(dbc.NavLink("Settings", href="/settings")),
                ], navbar=True),
                id="navbar-collapse",
                navbar=True,
            ),
        ]),
        color="primary",
        dark=True,
    ),
    
    # Content area
    dbc.Container(id="page-content", className="mt-4"),
    
    # Data refresh indicator and controls
    dbc.Row([
        dbc.Col([
            html.Div(id="refresh-indicator", className="text-muted small"),
        ]),
        dbc.Col([
            dbc.Button("Refresh Data", id="refresh-button", color="secondary", size="sm", className="float-end"),
        ]),
    ], className="mt-4 border-top pt-2"),
    
    # Store components for data
    dcc.Store(id="metrics-data"),
    dcc.Store(id="analysis-results"),
    dcc.Store(id="current-collection-id"),
    dcc.Location(id="url")
], fluid=True)

# Load initial data
@app.callback(
    [Output("metrics-data", "data"),
     Output("current-collection-id", "data"),
     Output("refresh-indicator", "children")],
    [Input("refresh-button", "n_clicks")],
    prevent_initial_call=False
)
def load_data(n_clicks):
    """Load metrics data and update the refresh indicator."""
    # Load the latest metrics
    df, collection_id = load_latest_metrics()
    
    # Convert DataFrame to JSON for storage in dcc.Store
    if not df.empty:
        # Handle datetime columns by converting to ISO strings
        df_json = df.to_dict(orient="records")
        refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Data last refreshed: {refresh_time} | Collection: {collection_id}"
    else:
        df_json = []
        message = "No data available. Please check data storage configuration."
    
    return df_json, collection_id, message

# Process data and run analysis
@app.callback(
    Output("analysis-results", "data"),
    [Input("metrics-data", "data")],
    prevent_initial_call=True
)
def process_data(metrics_json):
    """Process the loaded metrics and run analysis."""
    if not metrics_json:
        return {"status": "no_data"}
    
    # Convert JSON back to DataFrame
    df = pd.DataFrame(metrics_json)
    
    # Convert timestamp strings back to datetime
    if "timestamp" in df.columns and df["timestamp"].dtype == "object":
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Run analysis
    analysis_results = analyze_metrics(df)
    
    return analysis_results

# URL routing
@app.callback(
    Output("page-content", "children"),
    [Input("url", "pathname")],
    [State("metrics-data", "data"),
     State("analysis-results", "data"),
     State("current-collection-id", "data")]
)
def render_page(pathname, metrics_json, analysis_results, collection_id):
    """Render the appropriate page based on URL."""
    # Default to overview page
    if pathname == "/" or pathname == "/overview":
        from .pages.overview import create_layout
        return create_layout(metrics_json, analysis_results, collection_id)
    elif pathname == "/resources":
        from .pages.resources import create_layout
        return create_layout(metrics_json, analysis_results, collection_id)
    elif pathname == "/trends":
        from .pages.trends import create_layout
        return create_layout(metrics_json, analysis_results, collection_id)
    elif pathname == "/costs":
        from .pages.costs import create_layout
        return create_layout(metrics_json, analysis_results, collection_id)
    elif pathname == "/anomalies":
        from .pages.anomalies import create_layout
        return create_layout(metrics_json, analysis_results, collection_id)
    elif pathname == "/recommendations":
        from .pages.recommendations import create_layout
        return create_layout(metrics_json, analysis_results, collection_id)
    elif pathname == "/settings":
        from .pages.settings import create_layout
        return create_layout(metrics_json, analysis_results, collection_id)
    else:
        # 404 page
        return html.Div([
            html.H1("404: Not Found", className="text-danger"),
            html.P(f"The page {pathname} was not found."),
            dbc.Button("Return to Home", color="primary", href="/"),
        ])

if __name__ == "__main__":
    app.run_server(debug=dashboard_config.get("debug", True),
                  host=dashboard_config.get("host", "127.0.0.1"),
                  port=dashboard_config.get("port", 8050))
