"""
Tests for the credentials module.
"""
import json
import os
import pytest
from unittest.mock import patch, mock_open, MagicMock
from src.auth.credentials import (
    CredentialOptions, 
    get_credential_by_type,
    load_credentials_from_file
)


def test_credential_options_defaults():
    """Test CredentialOptions default values."""
    options = CredentialOptions()
    
    assert options.tenant_id is None
    assert options.client_id is None
    assert options.client_secret is None
    assert options.include_environment is True
    assert options.include_managed_identity is True
    assert options.include_cli is True


def test_credential_options_custom():
    """Test CredentialOptions with custom values."""
    options = CredentialOptions(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        include_environment=False,
        exclude_interactive=True
    )
    
    assert options.tenant_id == "test-tenant"
    assert options.client_id == "test-client"
    assert options.client_secret == "test-secret"
    assert options.include_environment is False
    assert options.exclude_interactive is True


@patch('src.auth.credentials.DefaultAzureCredential')
def test_get_credential_default(mock_default_credential):
    """Test get_credential_by_type with 'default' method."""
    mock_instance = MagicMock()
    mock_default_credential.return_value = mock_instance
    
    credential = get_credential_by_type("default")
    
    assert credential == mock_instance
    mock_default_credential.assert_called_once()


@patch('src.auth.credentials.InteractiveBrowserCredential')
def test_get_credential_browser(mock_browser_credential):
    """Test get_credential_by_type with 'browser' method."""
    mock_instance = MagicMock()
    mock_browser_credential.return_value = mock_instance
    
    options = CredentialOptions(tenant_id="test-tenant")
    credential = get_credential_by_type("browser", options)
    
    assert credential == mock_instance
    mock_browser_credential.assert_called_once_with(
        tenant_id="test-tenant",
        client_id=None,
        authority=None,
        login_timeout=120.0
    )


@patch('src.auth.credentials.ClientSecretCredential')
def test_get_credential_service_principal(mock_sp_credential):
    """Test get_credential_by_type with 'service_principal' method."""
    mock_instance = MagicMock()
    mock_sp_credential.return_value = mock_instance
    
    options = CredentialOptions(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret"
    )
    
    with patch.dict(os.environ, {}, clear=True):
        credential = get_credential_by_type("service_principal", options)
        
        assert credential == mock_instance
        mock_sp_credential.assert_called_once_with(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret"
        )


def test_get_credential_service_principal_missing_values():
    """Test get_credential_by_type with 'service_principal' method and missing values."""
    options = CredentialOptions()  # Missing required values
    
    with pytest.raises(ValueError):
        get_credential_by_type("service_principal", options)


@patch('src.auth.credentials.AzureCliCredential')
def test_get_credential_cli(mock_cli_credential):
    """Test get_credential_by_type with 'cli' method."""
    mock_instance = MagicMock()
    mock_cli_credential.return_value = mock_instance
    
    credential = get_credential_by_type("cli")
    
    assert credential == mock_instance
    mock_cli_credential.assert_called_once()


def test_get_credential_unsupported():
    """Test get_credential_by_type with unsupported method."""
    with pytest.raises(ValueError):
        get_credential_by_type("unsupported_method")


@patch('builtins.open', new_callable=mock_open, read_data='{"tenant_id": "test-tenant", "client_id": "test-client"}')
def test_load_credentials_from_file(mock_file):
    """Test loading credentials from a file."""
    options = load_credentials_from_file("fake_path.json")
    
    assert options.tenant_id == "test-tenant"
    assert options.client_id == "test-client"
    mock_file.assert_called_once_with("fake_path.json", "r")


@patch('builtins.open', side_effect=IOError("File not found"))
def test_load_credentials_file_not_found(mock_file):
    """Test loading credentials with a missing file."""
    options = load_credentials_from_file("missing_file.json")
    
    # Should return default options
    assert options.tenant_id is None
    assert options.client_id is None
    assert isinstance(options, CredentialOptions)
