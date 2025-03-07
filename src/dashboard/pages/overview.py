"""
Overview page for the dashboard.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Any, List, Optional

from dash import html, dcc
import dash_bootstrap_components as dbc

def create_layout(metrics_json, analysis_results, collection_id):
    """
    Create the layout for the overview page.
    
    Args:
        metrics_json: JSON representation of metrics data
        analysis_results: Results from analysis
        collection_id: Current collection ID
        
    Returns:
        Dashboard layout
    """
    if not metrics_json:
        return html.Div([
            html.H2("Azure Egress Dashboard", className="mb-4"),
            html.Div(
                dbc.Alert("No data available. Please check data storage configuration.", color="warning"),
                className="mb-4"
            )
        ])
    
    # Convert JSON back to DataFrame
    metrics_df = pd.DataFrame(metrics_json)
    
    # Convert timestamp strings back to datetime
    if "timestamp" in metrics_df.columns and isinstance(metrics_df["timestamp"].iloc[0], str):
        metrics_df["timestamp"] = pd.to_datetime(metrics_df["timestamp"])
    
    # Extract key metrics for summary cards
    trend_direction = analysis_results.get("trend", {}).get("direction", "unknown")
    trend_strength = analysis_results.get("trend", {}).get("strength", "unknown")
    total_cost = analysis_results.get("costs", {}).get("total_cost", 0)
    cost_currency = analysis_results.get("costs", {}).get("currency", "USD")
    cost_status = analysis_results.get("costs", {}).get("cost_status", "normal")
    anomaly_count = analysis_results.get("anomalies", {}).get("summary", {}).get("total_anomalies", 0)
    recommendation_count = analysis_results.get("recommendations", {}).get("count", 0)
    
    # Create summary cards
    summary_cards = [
        dbc.Card([
            dbc.CardBody([
                html.H5("Trend Direction", className="card-title"),
                html.P(f"{trend_direction.title()} ({trend_strength})", 
                       className=f"card-text {'text-danger' if trend_direction == 'increasing' else 'text-success' if trend_direction == 'decreasing' else ''}"),
            ])
        ], className="mb-4"),
        
        dbc.Card([
            dbc.CardBody([
                html.H5("Total Cost", className="card-title"),
                html.P(f"{total_cost:.2f} {cost_currency}", 
                       className=f"card-text {'text-danger' if cost_status == 'critical' else 'text-warning' if cost_status == 'warning' else ''}"),
            ])
        ], className="mb-4"),
        
        dbc.Card([
            dbc.CardBody([
                html.H5("Anomalies", className="card-title"),
                html.P(f"{anomaly_count}", 
                       className=f"card-text {'text-danger' if anomaly_count > 10 else 'text-warning' if anomaly_count > 0 else ''}"),
            ])
        ], className="mb-4"),
        
        dbc.Card([
            dbc.CardBody([
                html.H5("Recommendations", className="card-title"),
                html.P(f"{recommendation_count}", 
                       className="card-text"),
            ])
        ], className="mb-4"),
    ]
    
    # Create time series chart of total egress
    time_series_fig = create_time_series_chart(metrics_df)
    
    # Create resource distribution chart
    resource_fig = create_resource_distribution_chart(metrics_df)
    
    # Create top recommendations section
    recommendations_section = create_recommendations_section(analysis_results)
    
    # Layout with grid of cards and charts
    layout = html.Div([
        html.H2("Azure Egress Dashboard", className="mb-4"),
        
        # Summary cards row
        dbc.Row([
            dbc.Col(card, width=3) for card in summary_cards
        ]),
        
        # Charts row
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Egress Traffic Over Time"),
                    dbc.CardBody(dcc.Graph(figure=time_series_fig)),
                ]),
            ], width=8),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Resource Distribution"),
                    dbc.CardBody(dcc.Graph(figure=resource_fig)),
                ]),
            ], width=4),
        ], className="mb-4"),
        
        # Recommendations section
        dbc.Row([
            dbc.Col([
                html.H4("Top Recommendations", className="mb-3"),
                recommendations_section
            ])
        ]),
    ])
    
    return layout

def create_time_series_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create a time series chart of egress traffic.
    
    Args:
        df: DataFrame with metrics
        
    Returns:
        Plotly figure
    """
    # Filter to egress metrics only
    egress_df = df[
        (df['metric_name'].str.contains('out', case=False, na=False)) | 
        (df['metric_name'].str.contains('sent', case=False, na=False)) |
        (df['metric_name'].str.contains('egress', case=False, na=False))
    ].copy()
    
    if egress_df.empty:
        # Create empty chart with message
        fig = go.Figure()
        fig.add_annotation(
            text="No egress data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False
        )
        return fig
    
    # Group by timestamp for overall egress
    overall_ts = egress_df.groupby('timestamp')['value'].sum().reset_index()
    overall_ts = overall_ts.sort_values('timestamp')
    
    # Convert to GB for readability
    overall_ts['value_gb'] = overall_ts['value'] / (1024 * 1024 * 1024)
    
    # Create figure
    fig = px.line(
        overall_ts, 
        x='timestamp', 
        y='value_gb',
        labels={'value_gb': 'Egress (GB)', 'timestamp': 'Time'}
    )
    
    # Improve layout
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=350,
        hovermode="x unified"
    )
    
    return fig

def create_resource_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create a chart showing distribution of egress by resource.
    
    Args:
        df: DataFrame with metrics
        
    Returns:
        Plotly figure
    """
    # Filter to egress metrics only
    egress_df = df[
        (df['metric_name'].str.contains('out', case=False, na=False)) | 
        (df['metric_name'].str.contains('sent', case=False, na=False)) |
        (df['metric_name'].str.contains('egress', case=False, na=False))
    ].copy()
    
    if egress_df.empty:
        # Create empty chart with message
        fig = go.Figure()
        fig.add_annotation(
            text="No egress data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False
        )
        return fig
    
    # Group by resource
    resource_totals = egress_df.groupby('resource_name')['value'].sum().reset_index()
    resource_totals = resource_totals.sort_values('value', ascending=False)
    
    # Convert to GB for readability and take top 10
    resource_totals['value_gb'] = resource_totals['value'] / (1024 * 1024 * 1024)
    resource_totals = resource_totals.head(10)  # Top 10 resources
    
    # Create figure
    fig = px.pie(
        resource_totals, 
        values='value_gb', 
        names='resource_name',
        title=None,
        labels={'value_gb': 'Egress (GB)', 'resource_name': 'Resource'}
    )
    
    # Improve layout
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
    )
    
    return fig

def create_recommendations_section(analysis_results: Dict[str, Any]) -> html.Div:
    """
    Create a section showing top recommendations.
    
    Args:
        analysis_results: Results from analysis
        
    Returns:
        Dash component
    """
    recommendations = analysis_results.get("recommendations", {}).get("recommendations", [])
    
    if not recommendations:
        return html.Div([
            dbc.Alert("No recommendations available.", color="info")
        ])
    
    # Take top 3 recommendations
    top_recommendations = recommendations[:3]
    
    # Create cards for each recommendation
    recommendation_cards = []
    for rec in top_recommendations:
        # Determine color based on severity
        severity = rec.get("severity", "medium")
        color = "danger" if severity == "high" else "warning" if severity == "medium" else "info"
        
        # Create card
        card = dbc.Card([
            dbc.CardHeader(rec.get("title", "Recommendation"), className=f"bg-{color} text-white"),
            dbc.CardBody([
                html.P(rec.get("description", "")),
                html.H6("Suggested Actions:") if rec.get("actions") else None,
                html.Ul([
                    html.Li(action) for action in rec.get("actions", [])
                ]) if rec.get("actions") else None,
                html.Div([
                    html.Small(f"Type: {rec.get('type', 'general')} | Severity: {severity.title()}"),
                    html.Div([
                        html.Small(f"Potential savings: {rec.get('potential_savings', 0):.2f} USD") 
                        if rec.get('potential_savings') else None
                    ])
                ], className="text-muted mt-2")
            ])
        ], className="mb-3")
        
        recommendation_cards.append(card)
    
    # Add link to see all recommendations
    view_all_link = html.Div([
        dbc.Button("View All Recommendations", color="link", href="/recommendations")
    ], className="text-center mb-4")
    
    return html.Div(recommendation_cards + [view_all_link])
