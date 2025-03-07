<#
.SYNOPSIS
    Setup script for Azure Egress Management environment
.DESCRIPTION
    This script checks prerequisites and sets up the environment for Azure Egress Management
.EXAMPLE
    .\setup.ps1
#>

# Ensure running as administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Warning "This script should be run as Administrator for best results"
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") {
        exit
    }
}

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Cyan
try {
    $pythonVersion = python --version
    Write-Host "Found $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Error "Python not found. Please install Python 3.8 or higher"
    exit 1
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
    if (-not $?) {
        Write-Error "Failed to create virtual environment"
        exit 1
    }
    Write-Host "Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
if ($PSVersionTable.PSVersion.Major -ge 5) {
    . .\.venv\Scripts\Activate.ps1
}
else {
    Write-Error "PowerShell 5.0 or higher is required to activate the virtual environment"
    exit 1
}

# Install requirements
Write-Host "Installing required packages..." -ForegroundColor Cyan
pip install -r requirements.txt
if (-not $?) {
    Write-Error "Failed to install required packages"
    exit 1
}
Write-Host "Packages installed successfully" -ForegroundColor Green

# Check Azure CLI installation
Write-Host "Checking Azure CLI installation..." -ForegroundColor Cyan
try {
    $azVersion = az --version
    Write-Host "Azure CLI is installed" -ForegroundColor Green
}
catch {
    Write-Warning "Azure CLI not found. Some features may not work correctly."
    $installAz = Read-Host "Would you like to install Azure CLI now? (y/n)"
    if ($installAz -eq "y") {
        Invoke-WebRequest -Uri https://aka.ms/installazurecliwindows -OutFile .\AzureCLI.msi
        Start-Process msiexec.exe -Wait -ArgumentList '/I AzureCLI.msi /quiet'
        Remove-Item .\AzureCLI.msi
        Write-Host "Azure CLI installed" -ForegroundColor Green
    }
}

# Check Azure login status
Write-Host "Checking Azure login status..." -ForegroundColor Cyan
$azAccount = az account show 2>$null | ConvertFrom-Json
if ($null -eq $azAccount) {
    Write-Host "You are not logged in to Azure." -ForegroundColor Yellow
    $login = Read-Host "Would you like to log in now? (y/n)"
    if ($login -eq "y") {
        az login
        if (-not $?) {
            Write-Error "Failed to log in to Azure"
            exit 1
        }
    }
}
else {
    Write-Host "Logged in to Azure as $($azAccount.user.name)" -ForegroundColor Green
    Write-Host "Current subscription: $($azAccount.name)" -ForegroundColor Green
}

# Create required directories
$directories = @(
    "logs",
    "data",
    "data\reports"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        Write-Host "Creating directory: $dir" -ForegroundColor Cyan
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

Write-Host "`nAzure Egress Management setup completed successfully!" -ForegroundColor Green
Write-Host "Run 'python -m src.main setup' to verify your environment." -ForegroundColor Cyan
Write-Host "`nTo get started, try: 'python -m src.main monitor --subscription <subscription-id>'" -ForegroundColor Cyan
