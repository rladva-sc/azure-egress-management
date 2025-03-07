"""
Command-line interface for the Azure Egress Management tool.
"""
import typer
import logging
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn

from .auth.azure_auth import AzureAuthenticator
from .auth.credentials import CredentialOptions, load_credentials_from_file
from .egress.monitor import EgressMonitor
from .egress.collector import MetricsCollector
from .egress.storage import MetricsStorage
from .utils.config_utils import load_config, merge_configs, get_config_with_env_overrides
from .utils.logging_utils import setup_logging
from .utils.time_utils import TimeTracker  # Add this import

app = typer.Typer(help="Azure Egress Management Tool")
auth_app = typer.Typer(help="Authentication commands")
monitor_app = typer.Typer(help="Monitoring commands")
app.add_typer(auth_app, name="auth")
app.add_typer(monitor_app, name="monitor")

console = Console()
logger = None  # Will be initialized with setup

def initialize_logging(config=None):
    """Initialize logging with the specified config."""
    global logger
    logger = setup_logging(config)
    return logger

@app.callback()
def callback():
    """Azure Egress Management Tool."""
    # This will be called before any command
    config = load_config()
    initialize_logging(config)

def get_configured_authenticator(config_file=None, auth_method=None, credentials_file=None):
    """Get an authenticator configured from files and parameters."""
    config = load_config(config_file)
    
    # If auth_method is provided, override the config
    if auth_method:
        if "azure" not in config:
            config["azure"] = {}
        config["azure"]["auth_method"] = auth_method
    
    # Create credential options
    credential_options = None
    if credentials_file:
        credential_options = load_credentials_from_file(credentials_file)
    
    # Get the auth method from config
    auth_method = config.get("azure", {}).get("auth_method", "default")
    
    return AzureAuthenticator(
        auth_method=auth_method,
        credential_options=credential_options,
        config=config
    )

@auth_app.command("test")
def test_auth(
    subscription_id: str = typer.Option(..., "--subscription", "-s", help="Azure Subscription ID"),
    auth_method: str = typer.Option("default", "--auth-method", "-a", help="Authentication method"),
    credentials_file: Optional[str] = typer.Option(None, "--credentials", "-c", help="Path to credentials file"),
    config_file: Optional[str] = typer.Option(None, "--config", help="Path to config file"),
):
    """Test Azure authentication."""
    try:
        console.print(f"[bold blue]Testing Azure authentication using method: [/bold blue]{auth_method}")
        
        # Initialize authenticator
        auth = get_configured_authenticator(config_file, auth_method, credentials_file)
        
        # Test authentication
        if auth.validate_authentication(subscription_id):
            console.print("[bold green]Authentication successful![/bold green]")
        else:
            console.print("[bold red]Authentication failed![/bold red]")
            raise typer.Exit(code=1)
            
    except Exception as ex:
        if logger:
            logger.error(f"Authentication test error: {str(ex)}")
        console.print(f"[bold red]Error: [/bold red]{str(ex)}")
        raise typer.Exit(code=1)

@monitor_app.command("resources")
def list_resources(
    subscription_id: str = typer.Option(..., "--subscription", "-s", help="Azure Subscription ID"),
    resource_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for results"),
    auth_method: str = typer.Option("default", "--auth-method", "-a", help="Authentication method"),
    credentials_file: Optional[str] = typer.Option(None, "--credentials", "-c", help="Path to credentials file"),
    config_file: Optional[str] = typer.Option(None, "--config", help="Path to config file"),
):
    """List Azure resources with network egress capabilities."""
    try:
        console.print(f"[bold blue]Listing Azure network resources for subscription: [/bold blue]{subscription_id}")
        
        # Initialize authenticator and monitor
        auth = get_configured_authenticator(config_file, auth_method, credentials_file)
        config = load_config(config_file)
        monitor = EgressMonitor(subscription_id, auth, config)
        
        # Get network resources
        with console.status("[yellow]Collecting network resources...[/yellow]"):
            resources = monitor.get_network_resources(resource_type)
        
        # Create a table to display resources
        table = Table(title="Azure Network Resources")
        table.add_column("Resource Type", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Location", style="yellow")
        table.add_column("Resource Group", style="magenta")
        
        # Create flat list of resources for display and export
        flat_resources = []
        for res_type, items in resources.items():
            for item in items:
                name = getattr(item, 'name', 'Unknown')
                location = getattr(item, 'location', 'Unknown')
                resource_group = getattr(item, 'resource_group_name', 'Unknown')
                
                table.add_row(res_type, name, location, resource_group)
                
                flat_resources.append({
                    'type': res_type,
                    'name': name,
                    'location': location,
                    'resource_group': resource_group,
                    'id': getattr(item, 'id', 'Unknown')
                })
        
        console.print(table)
        console.print(f"Total resources: {len(flat_resources)}")
        
        # Output results to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(flat_resources, f, indent=2)
            console.print(f"[green]Results saved to: [/green]{output_file}")
        
    except Exception as ex:
        if logger:
            logger.error(f"Error listing resources: {str(ex)}")
        console.print(f"[bold red]Error: [/bold red]{str(ex)}")
        raise typer.Exit(code=1)

@app.command()
def monitor(
    subscription_id: str = typer.Option(..., "--subscription", "-s", help="Azure Subscription ID"),
    days: int = typer.Option(7, "--days", "-d", help="Number of days of data to analyze"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for results"),
    auth_method: str = typer.Option("default", "--auth-method", "-a", help="Authentication method"),
    credentials_file: Optional[str] = typer.Option(None, "--credentials", "-c", help="Path to credentials file"),
    config_file: Optional[str] = typer.Option(None, "--config", help="Path to config file"),
    store_data: bool = typer.Option(True, "--store/--no-store", help="Store collected data"),
):
    """Monitor Azure egress traffic."""
    try:
        config = load_config(config_file)
        initialize_logging(config)
        
        console.print(f"[bold blue]Monitoring Azure egress for subscription: [/bold blue]{subscription_id}")
        
        # Initialize authenticator and monitor
        auth = get_configured_authenticator(config_file, auth_method, credentials_file)
        monitor = EgressMonitor(subscription_id, auth, config)
        
        # Get network resources
        with console.status("[yellow]Collecting network resources...[/yellow]"):
            resources = monitor.get_network_resources()
        
        # Create a table to display resources
        table = Table(title="Azure Network Resources")
        table.add_column("Resource Type", style="cyan")
        table.add_column("Count", style="green")
        
        for resource_type, items in resources.items():
            table.add_row(resource_type, str(len(items)))
        
        console.print(table)
        
        # Set up metrics storage if needed
        storage = None
        if store_data:
            storage = MetricsStorage(config)
            
        # Set up metrics collector
        collector = MetricsCollector(subscription_id, auth, config, storage)
        
        # Get egress data with progress bar
        console.print(f"[yellow]Collecting {days} days of egress data...[/yellow]")
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("Collecting metrics", total=100)
            
            # Custom progress callback
            def progress_callback(percent):
                progress.update(task, completed=percent)
                
            egress_data = collector.collect_metrics(
                days=days,
                progress_callback=progress_callback
            )
        
        # Analyze data
        with console.status("[yellow]Analyzing egress patterns...[/yellow]"):
            results = monitor.analyze_egress(egress_data)
        
        # Output results
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            console.print(f"[green]Results saved to: [/green]{output_file}")
        else:
            console.print_json(json.dumps(results))
            
        console.print("[bold green]Monitoring completed successfully![/bold green]")
        
    except Exception as ex:
        if logger:
            logger.error(f"Error in monitoring: {str(ex)}")
        console.print(f"[bold red]Error: [/bold red]{str(ex)}")
        raise typer.Exit(code=1)

@app.command()
def setup():
    """Set up the Azure Egress Management environment."""
    console.print("[bold blue]Setting up Azure Egress Management...[/bold blue]")
    console.print("This will verify your Azure credentials and create necessary directories.")
    
    try:
        # Load config
        config = load_config()
        initialize_logging(config)
        
        # Check credentials
        auth = get_configured_authenticator()
        credential = auth.credential
        console.print("[green]✓ Azure credentials verified[/green]")
        
        # Create necessary directories
        paths = [
            Path(__file__).parent.parent / "logs",
            Path(__file__).parent.parent / "data",
            Path(__file__).parent.parent / "data" / "raw",
            Path(__file__).parent.parent / "data" / "processed",
            Path(__file__).parent.parent / "data" / "reports",
        ]
        
        for path in paths:
            path.mkdir(exist_ok=True)
            console.print(f"[green]✓ Created directory: {path}[/green]")
        
        # Verify storage is working if configured
        if config.get("storage", {}).get("enabled", False):
            storage = MetricsStorage(config)
            storage.initialize()
            console.print("[green]✓ Storage configuration verified[/green]")
            
        console.print("[bold green]Setup completed successfully![/bold green]")
        
    except Exception as ex:
        if logger:
            logger.error(f"Setup error: {str(ex)}")
        console.print(f"[bold red]Setup Error: [/bold red]{str(ex)}")
        raise typer.Exit(code=1)

@app.command("timing")
def timing_report(
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for timing report"),
):
    """Generate a report of timing data for project phases."""
    try:
        console.print("[bold blue]Generating timing report...[/bold blue]")
        
        # Load timing data
        tracker = TimeTracker()
        summary = tracker.get_phase_summary()
        
        # Create a table to display timing info
        table = Table(title="Project Phase Timing")
        table.add_column("Phase ID", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Duration", style="magenta")
        
        for phase_id, phase in summary["phases"].items():
            table.add_row(
                phase_id,
                phase.get("description", ""),
                phase.get("status", "unknown"),
                phase.get("duration_formatted", "In progress")
            )
        
        console.print(table)
        console.print(f"[bold green]Total Duration: [/bold green]{summary['total_duration_formatted']}")
        
        # Output results to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2)
            console.print(f"[green]Timing report saved to: [/green]{output_file}")
        
    except Exception as ex:
        if logger:
            logger.error(f"Error generating timing report: {str(ex)}")
        console.print(f"[bold red]Error: [/bold red]{str(ex)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
