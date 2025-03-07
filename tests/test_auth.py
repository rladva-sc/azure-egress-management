"""
Tests for the authentication module.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from src.auth.azure_auth import AzureAuthenticator, AzureAuthenticationError
from src.auth.credentials import CredentialOptions


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
