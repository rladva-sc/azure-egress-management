# Authentication

This document describes the authentication options and configuration for Azure Egress Management.

## Authentication Methods

Azure Egress Management supports multiple authentication methods through Azure Identity:

### Default Azure Credential

```python
from src.auth.azure_auth import AzureAuthenticator

# Uses DefaultAzureCredential which tries multiple authentication methods
auth = AzureAuthenticator()
```

DefaultAzureCredential tries the following credential types in order:
- Environment credentials
- Managed Identity
- Visual Studio Code
- Azure CLI
- Azure PowerShell
- Interactive Browser

### Interactive Browser Authentication

```python
auth = AzureAuthenticator(auth_method="browser")
```

Opens a browser window to log in interactively. Good for development scenarios.

### Azure CLI Authentication

```python
auth = AzureAuthenticator(auth_method="cli")
```

Uses your existing Azure CLI login.

### Service Principal Authentication

```python
from src.auth.credentials import CredentialOptions

options = CredentialOptions(
    tenant_id="your-tenant-id",
    client_id="your-client-id",
    client_secret="your-client-secret"
)

auth = AzureAuthenticator(
    auth_method="service_principal", 
    credential_options=options
)
```

Or using environment variables:

```bash
export AZURE_TENANT_ID=your-tenant-id
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-client-secret
```

### Managed Identity Authentication

```python
auth = AzureAuthenticator(auth_method="managed_identity")
```

For use in Azure hosted environments like App Service, Functions, or VMs.

### Device Code Authentication

```python
auth = AzureAuthenticator(auth_method="device_code")
```

For environments without a browser.

## Loading Credentials from File

You can store credentials in a JSON file and load them:

```python
from src.auth.credentials import load_credentials_from_file

options = load_credentials_from_file("path/to/credentials.json")
auth = AzureAuthenticator(credential_options=options)
```

Example credentials.json:
```json
{
    "tenant_id": "your-tenant-id", 
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "include_cli": true,
    "exclude_interactive": false
}
```

## Using the CLI for Authentication Testing

The CLI provides commands to test authentication:

```bash
# Test authentication using default method
python -m src.main auth test --subscription YOUR_SUBSCRIPTION_ID

# Test with specific method
python -m src.main auth test --subscription YOUR_SUBSCRIPTION_ID --auth-method browser

# Test with credentials file
python -m src.main auth test --subscription YOUR_SUBSCRIPTION_ID --credentials path/to/creds.json
```
