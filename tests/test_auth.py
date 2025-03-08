"""
Tests for the authentication module.
"""
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.auth.azure_auth import AzureAuthenticator, AzureAuthenticationError
from src.auth.credentials import CredentialManager, CredentialOptions


def test_credential_manager_init():
    """Test credential manager initialization."""
    credential_manager = CredentialManager()
    assert credential_manager is not None
    assert hasattr(credential_manager, 'get_credential')

@patch('src.auth.credentials.DefaultAzureCredential')
def test_default_credential(mock_default_credential):
    """Test getting default credential."""
    # Setup mock
    mock_credential = MagicMock()
    mock_default_credential.return_value = mock_credential
    
    # Create credential manager and get credential
    credential_manager = CredentialManager()
    credential = credential_manager.get_credential('default')
    
    # Verify
    assert credential == mock_credential
    mock_default_credential.assert_called_once()

@patch.dict(os.environ, {"AZURE_CLIENT_ID": "test-client-id", 
                         "AZURE_CLIENT_SECRET": "test-client-secret", 
                         "AZURE_TENANT_ID": "test-tenant-id"})
@patch('src.auth.credentials.ClientSecretCredential')
def test_service_principal_credential(mock_client_secret_credential):
    """Test getting service principal credential."""
    # Setup mock
    mock_credential = MagicMock()
    mock_client_secret_credential.return_value = mock_credential
    
    # Create credential manager and get credential
    credential_manager = CredentialManager()
    credential = credential_manager.get_credential('service_principal')
    
    # Verify
    assert credential == mock_credential
    mock_client_secret_credential.assert_called_once_with(
        client_id="test-client-id",
        client_secret="test-client-secret",
        tenant_id="test-tenant-id"
    )

def test_azure_authenticator_init():
    """Test authenticator initialization."""
    authenticator = AzureAuthenticator()
    assert authenticator is not None
    assert hasattr(authenticator, 'get_client')

@patch('src.auth.azure_auth.CredentialManager')
def test_authenticator_auth_method(mock_credential_manager):
    """Test authenticator with different authentication methods."""
    # Setup mock
    mock_manager = MagicMock()
    mock_credential = MagicMock()
    mock_manager.get_credential.return_value = mock_credential
    mock_credential_manager.return_value = mock_manager
    
    # Test default method
    authenticator = AzureAuthenticator()
    mock_manager.get_credential.assert_called_with('default')
    
    # Test specified method
    authenticator = AzureAuthenticator(auth_method='managed_identity')
    mock_manager.get_credential.assert_called_with('managed_identity')

@patch('src.auth.azure_auth.NetworkManagementClient')
@patch('src.auth.azure_auth.CredentialManager')
def test_get_network_client(mock_credential_manager, mock_network_client):
    """Test getting network client."""
    # Setup mocks
    mock_manager = MagicMock()
    mock_credential = MagicMock()
    mock_manager.get_credential.return_value = mock_credential
    mock_credential_manager.return_value = mock_manager
    
    mock_client = MagicMock()
    mock_network_client.return_value = mock_client
    
    # Get network client
    authenticator = AzureAuthenticator()
    subscription_id = "test-subscription-id"
    client = authenticator.get_client('network', subscription_id)
    
    # Verify
    assert client == mock_client
    mock_network_client.assert_called_once_with(mock_credential, subscription_id)

@patch('src.auth.azure_auth.MonitorManagementClient')
@patch('src.auth.azure_auth.CredentialManager')
def test_get_monitor_client(mock_credential_manager, mock_monitor_client):
    """Test getting monitor client."""
    # Setup mocks
    mock_manager = MagicMock()
    mock_credential = MagicMock()
    mock_manager.get_credential.return_value = mock_credential
    mock_credential_manager.return_value = mock_manager
    
    mock_client = MagicMock()
    mock_monitor_client.return_value = mock_client
    
    # Get monitor client
    authenticator = AzureAuthenticator()
    subscription_id = "test-subscription-id"
    client = authenticator.get_client('monitor', subscription_id)
    
    # Verify
    assert client == mock_client
    mock_monitor_client.assert_called_once_with(mock_credential, subscription_id)


def test_azure_authenticator_initialization():
    """Test that AzureAuthenticator initializes correctly."""
    auth = AzureAuthenticator()
    assert auth is not None
    assert auth.auth_method == "default"
    
    # Test with specific auth method
    auth = AzureAuthenticator(auth_method="browser")
    assert auth.auth_method == "browser"
    
    # Test with credential options
    options = CredentialOptions(tenant_id="test-tenant")
    auth = AzureAuthenticator(credential_options=options)
    assert auth._credential_options.tenant_id == "test-tenant"


@patch('src.auth.credentials.get_credential_by_type')
def test_credential_property(mock_get_credential):
    """Test that credential property works correctly."""
    mock_cred = MagicMock()
    mock_get_credential.return_value = mock_cred
    
    auth = AzureAuthenticator(auth_method="cli")
    credential = auth.credential
    
    assert credential == mock_cred
    mock_get_credential.assert_called_once_with("cli", auth._credential_options)
    

@patch('src.auth.credentials.get_credential_by_type')
def test_credential_error_handling(mock_get_credential):
    """Test credential error handling."""
    mock_get_credential.side_effect = ValueError("Test error")
    
    auth = AzureAuthenticator()
    with pytest.raises(AzureAuthenticationError):
        credential = auth.credential


@patch('src.auth.azure_auth.NetworkManagementClient')
def test_get_network_client(mock_network_client):
    """Test that network client is created correctly."""
    mock_instance = MagicMock()
    mock_network_client.return_value = mock_instance
    
    with patch.object(AzureAuthenticator, 'credential', PropertyMock()) as mock_credential:
        auth = AzureAuthenticator()
        client = auth.get_client('network', 'sub-123')
        
        assert client == mock_instance
        mock_network_client.assert_called_once_with(
            credential=mock_credential, 
            subscription_id='sub-123'
        )


@patch('src.auth.azure_auth.StorageManagementClient')
def test_get_storage_client(mock_storage_client):
    """Test that storage client is created correctly."""
    mock_instance = MagicMock()
    mock_storage_client.return_value = mock_instance
    
    with patch.object(AzureAuthenticator, 'credential', PropertyMock()) as mock_credential:
        auth = AzureAuthenticator()
        client = auth.get_client('storage', 'sub-123')
        
        assert client == mock_instance
        mock_storage_client.assert_called_once_with(
            credential=mock_credential, 
            subscription_id='sub-123'
        )


def test_get_unsupported_client():
    """Test that requesting an unsupported client type raises ValueError."""
    with patch.object(AzureAuthenticator, 'credential', PropertyMock()):
        auth = AzureAuthenticator()
        with pytest.raises(ValueError):
            auth.get_client('unsupported_type', 'sub-123')


@patch('src.auth.azure_auth.ResourceManagementClient')
def test_validate_authentication_success(mock_resource_client):
    """Test validate_authentication with successful authentication."""
    # Mock the credential
    mock_credential = MagicMock()
    mock_credential.get_token.return_value = {"token": "test-token"}
    
    # Mock the resource client
    mock_client_instance = MagicMock()
    mock_resource_groups = MagicMock()
    mock_resource_groups.list.return_value = ["group1"]
    mock_client_instance.resource_groups = mock_resource_groups
    mock_resource_client.return_value = mock_client_instance
    
    with patch.object(AzureAuthenticator, 'credential', mock_credential):
        auth = AzureAuthenticator()
        result = auth.validate_authentication('sub-123')
        
        assert result is True
        mock_credential.get_token.assert_called_once()
        mock_resource_client.assert_called_once()


@patch('src.auth.azure_auth.ResourceManagementClient')
def test_validate_authentication_failure(mock_resource_client):
    """Test validate_authentication with failed authentication."""
    # Mock the credential with failure
    mock_credential = MagicMock()
    mock_credential.get_token.side_effect = Exception("Authentication failed")
    
    with patch.object(AzureAuthenticator, 'credential', mock_credential):
        auth = AzureAuthenticator()
        result = auth.validate_authentication('sub-123')
        
        assert result is False
        mock_credential.get_token.assert_called_once()
        mock_resource_client.assert_not_called()


def test_auth_method_setter():
    """Test setting a new authentication method."""
    auth = AzureAuthenticator(auth_method="default")
    
    # Set up some initial state to verify it gets reset
    auth.clients = {"network_sub123": MagicMock()}
    with patch.object(AzureAuthenticator, '_credential', "initial-credential"):
        # Change the auth method
        auth.auth_method = "browser"
        
        # Verify the change
        assert auth.auth_method == "browser"
        assert auth.clients == {}
        assert auth._credential is None
