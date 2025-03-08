<#
.SYNOPSIS
    Installation script for Azure Egress Management.
.DESCRIPTION
    Sets up the Azure Egress Management tool, including dependencies,
    environment configuration, and Azure permissions.
.PARAMETER ConfigPath
    Path to configuration file
.PARAMETER InstallPath
    Path to install the tool
.PARAMETER SkipDependencies
    Skip dependency installation
.EXAMPLE
    .\Install-EgressManagement.ps1 -ConfigPath "config.json"
.NOTES
    Requires PowerShell 5.1 or higher and Azure PowerShell module.
#>

[CmdletBinding()]
param(
    [Parameter()]
    [string]$ConfigPath = ".\config.json",
    
    [Parameter()]
    [string]$InstallPath = $null,
    
    [Parameter()]
    [switch]$SkipDependencies = $false
)

# Set strict mode and error action preference
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Script variables
$script:MinPowerShellVersion = "5.1"
$script:RequiredModules = @("Az", "Az.ResourceGraph", "Az.Monitor")
$script:RequiredPythonVersion = "3.8"
$script:PythonPackages = @(
    "azure-identity",
    "azure-mgmt-compute",
    "azure-mgmt-network",
    "azure-mgmt-resource",
    "azure-mgmt-monitor",
    "azure-mgmt-storage", 
    "pandas",
    "numpy",
    "typer",
    "dash",
    "plotly",
    "pytest"
)

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    
    switch ($Status) {
        "INFO" { Write-Host "[$Status] $Message" -ForegroundColor Cyan }
        "SUCCESS" { Write-Host "[$Status] $Message" -ForegroundColor Green }
        "WARNING" { Write-Host "[$Status] $Message" -ForegroundColor Yellow }
        "ERROR" { Write-Host "[$Status] $Message" -ForegroundColor Red }
    }
}

function Test-SystemRequirements {
    Write-Status "Checking system requirements..."
    
    # Check PowerShell version
    $currentVersion = $PSVersionTable.PSVersion
    if ($currentVersion -lt [Version]$script:MinPowerShellVersion) {
        Write-Status "PowerShell version $currentVersion is below the required version $script:MinPowerShellVersion" -Status "ERROR"
        return $false
    }
    
    # Check if running as administrator
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Status "This script requires administrator privileges" -Status "WARNING"
    }
    
    # Check Python installation
    try {
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match 'Python (\d+\.\d+)') {
            $version = [Version]$matches[1]
            if ($version -lt [Version]$script:RequiredPythonVersion) {
                Write-Status "Python version $version is below the required version $script:RequiredPythonVersion" -Status "ERROR"
                return $false
            }
            Write-Status "Found Python $version" -Status "SUCCESS"
        }
        else {
            Write-Status "Python not found or version could not be determined" -Status "ERROR"
            return $false
        }
    }
    catch {
        Write-Status "Python not found or error checking version" -Status "ERROR"
        return $false
    }
    
    return $true
}

function Install-Dependencies {
    if ($SkipDependencies) {
        Write-Status "Skipping dependency installation"
        return $true
    }
    
    Write-Status "Installing dependencies..."
    
    # Install PowerShell modules
    foreach ($module in $script:RequiredModules) {
        if (-not (Get-Module -ListAvailable -Name $module)) {
            Write-Status "Installing PowerShell module: $module"
            try {
                Install-Module -Name $module -Scope CurrentUser -Force
                Write-Status "Installed PowerShell module: $module" -Status "SUCCESS"
            }
            catch {
                Write-Status "Failed to install PowerShell module: $module - $_" -Status "ERROR"
                return $false
            }
        }
        else {
            Write-Status "PowerShell module already installed: $module" -Status "SUCCESS"
        }
    }
    
    # Install Python packages
    Write-Status "Installing Python packages..."
    try {
        foreach ($package in $script:PythonPackages) {
            Write-Status "Installing Python package: $package"
            python -m pip install $package
        }
        Write-Status "Python packages installed successfully" -Status "SUCCESS"
    }
    catch {
        Write-Status "Failed to install Python packages: $_" -Status "ERROR"
        return $false
    }
    
    return $true
}

function Initialize-InstallLocation {
    if (-not $InstallPath) {
        $InstallPath = Join-Path $env:USERPROFILE "AzureEgressManagement"
    }
    
    Write-Status "Setting up installation directory: $InstallPath"
    
    # Create directory if it doesn't exist
    if (-not (Test-Path $InstallPath)) {
        try {
            New-Item -Path $InstallPath -ItemType Directory -Force | Out-Null
            Write-Status "Created installation directory" -Status "SUCCESS"
        }
        catch {
            Write-Status "Failed to create installation directory: $_" -Status "ERROR"
            return $null
        }
    }
    
    return $InstallPath
}

function Copy-SourceFiles {
    param([string]$DestinationPath)
    
    Write-Status "Copying source files to $DestinationPath..."
    
    # Get the directory of the current script
    $scriptDir = Split-Path -Parent $PSCommandPath
    $projectRoot = Split-Path -Parent $scriptDir
    
    # Copy source files
    try {
        # Copy src folder
        $srcPath = Join-Path $projectRoot "src"
        if (Test-Path $srcPath) {
            Copy-Item -Path $srcPath -Destination $DestinationPath -Recurse -Force
        }
        
        # Copy config files
        $configPath = Join-Path $projectRoot "config.json"
        if (Test-Path $configPath) {
            Copy-Item -Path $configPath -Destination $DestinationPath -Force
        }
        
        # Copy readme and documentation
        $readmePath = Join-Path $projectRoot "README.md"
        if (Test-Path $readmePath) {
            Copy-Item -Path $readmePath -Destination $DestinationPath -Force
        }
        
        $docsPath = Join-Path $projectRoot "docs"
        if (Test-Path $docsPath) {
            Copy-Item -Path $docsPath -Destination $DestinationPath -Recurse -Force
        }
        
        # Create data directories
        $dataPath = Join-Path $DestinationPath "data"
        New-Item -Path $dataPath -ItemType Directory -Force | Out-Null
        
        $subDirs = @("raw", "processed", "reports")
        foreach ($dir in $subDirs) {
            New-Item -Path (Join-Path $dataPath $dir) -ItemType Directory -Force | Out-Null
        }
        
        # Create logs directory
        $logsPath = Join-Path $DestinationPath "logs"
        New-Item -Path $logsPath -ItemType Directory -Force | Out-Null
        
        Write-Status "Files copied successfully" -Status "SUCCESS"
    }
    catch {
        Write-Status "Failed to copy files: $_" -Status "ERROR"
        return $false
    }
    
    return $true
}

function Set-EnvironmentVariables {
    param([string]$InstallPath)
    
    Write-Status "Setting up environment variables..."
    
    try {
        # Add installation directory to PATH for current process
        $env:Path = "$InstallPath;$env:Path"
        
        # Create .env file
        $envFilePath = Join-Path $InstallPath ".env"
        @"
# Azure Egress Management Environment Variables
AZURE_EGRESS_MANAGEMENT_HOME=$InstallPath
PYTHONPATH=$InstallPath
"@ | Out-File -FilePath $envFilePath -Encoding utf8 -Force
        
        Write-Status "Environment variables set" -Status "SUCCESS"
    }
    catch {
        Write-Status "Failed to set environment variables: $_" -Status "ERROR"
        return $false
    }
    
    return $true
}

function Set-AzurePermissions {
    Write-Status "Checking Azure permissions..."
    
    # Check if user is logged in to Azure
    try {
        $context = Get-AzContext
        if (-not $context) {
            Write-Status "Not logged in to Azure. Please login:" -Status "WARNING"
            Connect-AzAccount
            $context = Get-AzContext
            if (-not $context) {
                Write-Status "Failed to login to Azure" -Status "ERROR"
                return $false
            }
        }
        
        Write-Status "Logged in as $($context.Account) to subscription $($context.Subscription.Name)" -Status "SUCCESS"
    }
    catch {
        Write-Status "Error checking Azure login: $_" -Status "ERROR"
        return $false
    }
    
    return $true
}

function Create-ShortcutsAndAliases {
    param([string]$InstallPath)
    
    Write-Status "Creating shortcuts and PowerShell profile entries..."
    
    # Create PowerShell profile if it doesn't exist
    if (-not (Test-Path $PROFILE)) {
        New-Item -Path $PROFILE -ItemType File -Force | Out-Null
    }
    
    # Add aliases to PowerShell profile
    $aliasScript = @"
    
# Azure Egress Management Aliases
function Start-EgressDashboard {
    python "$InstallPath\src\dashboard\app.py"
}
Set-Alias -Name egress-dashboard -Value Start-EgressDashboard

function Invoke-EgressMonitoring {
    python "$InstallPath\src\cli.py" monitor `$args
}
Set-Alias -Name egress-monitor -Value Invoke-EgressMonitoring

function Get-EgressRecommendations {
    python "$InstallPath\src\cli.py" recommendation `$args
}
Set-Alias -Name egress-recommendations -Value Get-EgressRecommendations

# Add to PATH
`$env:Path = "$InstallPath;`$env:Path"
"@
    
    # Add to profile if the entries don't already exist
    $profileContent = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
    if (-not $profileContent -or -not $profileContent.Contains("Azure Egress Management Aliases")) {
        Add-Content -Path $PROFILE -Value $aliasScript
        Write-Status "Added aliases to PowerShell profile" -Status "SUCCESS"
    }
    else {
        Write-Status "Aliases already exist in PowerShell profile" -Status "INFO"
    }
    
    # Create desktop shortcut for dashboard
    try {
        $desktopPath = [Environment]::GetFolderPath("Desktop")
        $shortcutPath = Join-Path $desktopPath "Azure Egress Dashboard.lnk"
        
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($shortcutPath)
        $Shortcut.TargetPath = "powershell.exe"
        $Shortcut.Arguments = "-NoExit -Command Start-EgressDashboard"
        $Shortcut.WorkingDirectory = $InstallPath
        $Shortcut.Save()
        
        Write-Status "Created desktop shortcut" -Status "SUCCESS"
    }
    catch {
        Write-Status "Failed to create desktop shortcut: $_" -Status "WARNING"
    }
    
    return $true
}

function Test-Installation {
    param([string]$InstallPath)
    
    Write-Status "Testing installation..."
    
    # Check if src directory exists
    $srcPath = Join-Path $InstallPath "src"
    if (-not (Test-Path $srcPath)) {
        Write-Status "Source directory not found" -Status "ERROR"
        return $false
    }
    
    # Try to import the main module
    try {
        Push-Location $InstallPath
        $result = python -c "from src.utils import config_utils; print('Import successful')" 2>&1
        Pop-Location
        
        if ($result -match "Import successful") {
            Write-Status "Python module imports working correctly" -Status "SUCCESS"
        }
        else {
            Write-Status "Python module import test failed" -Status "ERROR"
            return $false
        }
    }
    catch {
        Write-Status "Failed to test Python imports: $_" -Status "ERROR"
        return $false
    }
    
    return $true
}

# Main installation process
try {
    Write-Status "Starting Azure Egress Management installation..."
    
    # Check system requirements
    if (-not (Test-SystemRequirements)) {
        Write-Status "System requirements check failed. Please address the issues and try again." -Status "ERROR"
        exit 1
    }
    
    # Install dependencies
    if (-not (Install-Dependencies)) {
        Write-Status "Dependency installation failed. Please address the issues and try again." -Status "ERROR"
        exit 1
    }
    
    # Initialize installation location
    $installDir = Initialize-InstallLocation
    if (-not $installDir) {
        Write-Status "Failed to initialize installation directory" -Status "ERROR"
        exit 1
    }
    
    # Copy source files
    if (-not (Copy-SourceFiles -DestinationPath $installDir)) {
        Write-Status "Failed to copy source files" -Status "ERROR"
        exit 1
    }
    
    # Set environment variables
    if (-not (Set-EnvironmentVariables -InstallPath $installDir)) {
        Write-Status "Failed to set environment variables" -Status "ERROR"
        exit 1
    }
    
    # Check Azure permissions
    if (-not (Set-AzurePermissions)) {
        Write-Status "Failed to verify Azure permissions" -Status "ERROR"
        exit 1
    }
    
    # Create shortcuts and aliases
    Create-ShortcutsAndAliases -InstallPath $installDir
    
    # Test installation
    if (-not (Test-Installation -InstallPath $installDir)) {
        Write-Status "Installation verification failed" -Status "ERROR"
        exit 1
    }
    
    Write-Status "Azure Egress Management successfully installed to: $installDir" -Status "SUCCESS"
    Write-Status "To start the dashboard, run: egress-dashboard" -Status "INFO"
    Write-Status "To run monitoring, run: egress-monitor --subscription <subscription-id>" -Status "INFO"
    Write-Status "For more information, refer to the documentation in the 'docs' folder" -Status "INFO"
    
}
catch {
    Write-Status "Installation failed with an unexpected error: $_" -Status "ERROR"
    exit 1
}
