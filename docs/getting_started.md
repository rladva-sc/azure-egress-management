# Getting Started with Azure Egress Management

This guide will help you set up and start using the Azure Egress Management tool.

## Prerequisites

Before you begin, ensure you have the following:

- Python 3.8 or higher
- An Azure subscription
- Azure CLI installed and configured
- Proper Azure RBAC permissions (Network Contributor or Reader roles)

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd azure-egress-management
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   source .venv/bin/activate  # On Linux/Mac
   ```

3. Install required packages:
   ```
   pip install -r requirements.txt
   ```

4. Run the setup script to verify your environment:
   ```
   python -m src.main setup
   ```

## Authentication

The tool supports several authentication methods:

### Default Azure Credential

Uses the Azure SDK's DefaultAzureCredential, which attempts various authentication methods:

- Environment variables
- Managed Identity
- Visual Studio Code
- Azure CLI
- Interactive browser

This is the simplest method and works in most environments.

### Interactive Browser Authentication

For interactive sessions, you can use browser-based authentication:

```python
from src.auth.azure_auth import AzureAuthenticator

auth = AzureAuthenticator(use_browser_auth=True)
```

## Basic Usage

### Command Line Interface

Monitor egress for a subscription:

