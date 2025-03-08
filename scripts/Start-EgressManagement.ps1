<#
.SYNOPSIS
    Starts the Azure Egress Management dashboard and services.
.DESCRIPTION
    Launches the Dash dashboard and background monitoring services.
.PARAMETER Mode
    Mode to start in: Dashboard, Monitor, or Both.
.PARAMETER ConfigPath
    Path to the configuration file.
.PARAMETER SubscriptionId
    Azure Subscription ID for monitoring.
.EXAMPLE
    .\Start-EgressManagement.ps1 -Mode Dashboard
.NOTES
    Requires PowerShell 5.1 or higher.
#>

[CmdletBinding()]
param(
    [Parameter()]
    [ValidateSet("Dashboard", "Monitor", "Both")]
    [string]$Mode = "Dashboard",
    
    [Parameter()]
    [string]$ConfigPath = ".\config.json",
    
    [Parameter()]
    [string]$SubscriptionId
)

# Set strict mode and error action preference
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    
    switch ($Status) {
        "INFO" { Write-Host "[$Status] $Message" -ForegroundColor Cyan }
        "SUCCESS" { Write-Host "[$Status] $Message" -ForegroundColor Green }
        "WARNING" { Write-Host "[$Status] $Message" -ForegroundColor Yellow }
        "ERROR" { Write-Host "[$Status] $Message" -ForegroundColor Red }
    }
}

function Start-EgressDashboard {
    Write-Status "Starting Azure Egress Management Dashboard..."
    
    try {
        # Get the directory of the current script
        $scriptDir = Split-Path -Parent $PSCommandPath
        $projectRoot = Split-Path -Parent $scriptDir
        
        # Start dashboard
        $dashboardPath = Join-Path $projectRoot "src" "dashboard" "app.py"
        if (Test-Path $dashboardPath) {
            Start-Process -FilePath "python" -ArgumentList $dashboardPath -NoNewWindow
            Write-Status "Dashboard started. Open http://localhost:8050 in your browser." -Status "SUCCESS"
        }
        else {
            Write-Status "Dashboard module not found at: $dashboardPath" -Status "ERROR"
            return $false
        }
    }
    catch {
        Write-Status "Failed to start dashboard: $_" -Status "ERROR"
        return $false
    }
    
    return $true
}

function Start-EgressMonitor {
    param([string]$SubscriptionId)
    
    if (-not $SubscriptionId) {
        Write-Status "SubscriptionId is required for monitoring" -Status "ERROR"
        return $false
    }
    
    Write-Status "Starting Azure Egress Monitor for subscription: $SubscriptionId"
    
    try {
        # Get the directory of the current script
        $scriptDir = Split-Path -Parent $PSCommandPath
        $projectRoot = Split-Path -Parent $scriptDir
        
        # Start monitor
        $cliPath = Join-Path $projectRoot "src" "cli.py"
        if (Test-Path $cliPath) {
            Start-Process -FilePath "python" -ArgumentList "$cliPath monitor --subscription $SubscriptionId" -NoNewWindow
            Write-Status "Monitoring started for subscription: $SubscriptionId" -Status "SUCCESS"
        }
        else {
            Write-Status "CLI module not found at: $cliPath" -Status "ERROR"
            return $false
        }
    }
    catch {
        Write-Status "Failed to start monitoring: $_" -Status "ERROR"
        return $false
    }
    
    return $true
}

function Test-AzureLogin {
    try {
        $context = Get-AzContext -ErrorAction SilentlyContinue
        if (-not $context) {
            Write-Status "Not logged in to Azure. Please login:" -Status "WARNING"
            Connect-AzAccount
            $context = Get-AzContext
            if (-not $context) {
                Write-Status "Failed to login to Azure" -Status "ERROR"
                return $false
            }
        }
        
        Write-Status "Logged in as $($context.Account) to subscription: $($context.Subscription.Name)" -Status "SUCCESS"
    }
    catch {
        Write-Status "Failed to check Azure login: $_" -Status "ERROR"
        Write-Status "You can still start the dashboard, but some Azure data may not be accessible." -Status "WARNING"
    }
    
    return $true
}

# Main execution
try {
    # Check Azure login if needed
    if ($Mode -eq "Monitor" -or $Mode -eq "Both") {
        if (-not (Test-AzureLogin)) {
            Write-Status "Azure login is required for monitoring" -Status "ERROR"
            exit 1
        }
    }
    
    # Start in requested mode
    switch ($Mode) {
        "Dashboard" {
            if (-not (Start-EgressDashboard)) {
                exit 1
            }
        }
        "Monitor" {
            if (-not (Start-EgressMonitor -SubscriptionId $SubscriptionId)) {
                exit 1
            }
        }
        "Both" {
            if (-not (Start-EgressDashboard)) {
                exit 1
            }
            if (-not (Start-EgressMonitor -SubscriptionId $SubscriptionId)) {
                exit 1
            }
        }
    }
    
    Write-Status "Azure Egress Management started successfully" -Status "SUCCESS"
    
}
catch {
    Write-Status "Failed to start Egress Management: $_" -Status "ERROR"
    exit 1
}
