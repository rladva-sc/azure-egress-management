"""
Handles authentication with Azure services.
"""
import logging
import os
from typing import Optional, Dict, Any, Union

from azure.identity import (
    DefaultAzureCredential,
    InteractiveBrowserCredential,
    ClientSecretCredential,
    ManagedIdentityCredential,
    AzureCliCredential,
    ChainedTokenCredential,
    DeviceCodeCredential,
    CredentialUnavailableError
)
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.core.exceptions import ClientAuthenticationError

from .credentials import get_credential_by_type, CredentialOptions
from ..utils.logging_utils import setup_logging


class AzureAuthenticationError(Exception):
    """Exception raised for Azure authentication errors."""
    pass


class AzureAuthenticator:
    """
    Manages authentication to Azure services required for egress monitoring.
    """
    def __init__(self, 
                 auth_method: str = "default", 
                 credential_options: Optional[CredentialOptions] = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize the authenticator.
        
        Args:
            auth_method (str): Authentication method to use. Options:
                             'default', 'browser', 'service_principal', 'managed_identity',
                             'cli', 'device_code'
            credential_options (CredentialOptions, optional): Options for credential creation
            config (dict, optional): Configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self._credential = None
        self._auth_method = auth_method
        self._credential_options = credential_options or CredentialOptions()
        self._config = config or {}
        self.clients = {}
        
        # Set up detailed logging
        setup_logging(self._config)
        
    @property
    def auth_method(self) -> str:
        """Get the current authentication method."""
        return self._auth_method
    
    @auth_method.setter
    def auth_method(self, method: str) -> None:
        """
        Set a new authentication method.
        
        Args:
            method (str): New authentication method
            
        Note: This will reset any existing credential
        """
        if method != self._auth_method:
            self._auth_method = method
            self._credential = None
            self.clients = {}
            self.logger.info(f"Authentication method changed to {method}")
    
    @property
    def credential(self):
        """
        Get or create the Azure credential.
        
        Returns:
            An Azure credential object for authenticating requests
            
        Raises:
            AzureAuthenticationError: If credential creation fails
        """
        if not self._credential:
            try:
                self._credential = get_credential_by_type(
                    self._auth_method, 
                    self._credential_options
                )
                self.logger.info(f"Created credential using {self._auth_method} method")
            except CredentialUnavailableError as ex:
                self.logger.error(f"Credential unavailable: {str(ex)}")
                self.logger.info("Attempting to fall back to DefaultAzureCredential")
                try:
                    self._credential = DefaultAzureCredential()
                except Exception as fallback_ex:
                    self.logger.error(f"Fallback authentication failed: {str(fallback_ex)}")
                    raise AzureAuthenticationError(
                        f"Failed to create credential with {self._auth_method} method and fallback failed"
                    ) from fallback_ex
            except Exception as ex:
                self.logger.error(f"Authentication error: {str(ex)}")
                raise AzureAuthenticationError(
                    f"Failed to create credential with {self._auth_method} method: {str(ex)}"
                ) from ex
        
        return self._credential
    
    def get_client(self, client_type: str, subscription_id: str):
        """
        Get or create a client for the specified Azure service.
        
        Args:
            client_type (str): Type of client ('network', 'resource', 'compute', 
                               'monitor', 'storage')
            subscription_id (str): Azure subscription ID
            
        Returns:
            The requested Azure management client
            
        Raises:
            ValueError: If client_type is not supported
            AzureAuthenticationError: If client creation fails
        """
        client_key = f"{client_type}_{subscription_id}"
        
        if client_key not in self.clients:
            try:
                credential = self.credential
                
                if client_type == 'network':
                    self.clients[client_key] = NetworkManagementClient(
                        credential=credential, 
                        subscription_id=subscription_id
                    )
                elif client_type == 'resource':
                    self.clients[client_key] = ResourceManagementClient(
                        credential=credential, 
                        subscription_id=subscription_id
                    )
                elif client_type == 'compute':
                    self.clients[client_key] = ComputeManagementClient(
                        credential=credential, 
                        subscription_id=subscription_id
                    )
                elif client_type == 'monitor':
                    self.clients[client_key] = MonitorManagementClient(
                        credential=credential, 
                        subscription_id=subscription_id
                    )
                elif client_type == 'storage':
                    self.clients[client_key] = StorageManagementClient(
                        credential=credential, 
                        subscription_id=subscription_id
                    )
                else:
                    raise ValueError(f"Unsupported client type: {client_type}")
                
                self.logger.info(f"Created {client_type} client for subscription {subscription_id}")
            except ClientAuthenticationError as ex:
                self.logger.error(f"Authentication failed for {client_type} client: {ex}")
                raise AzureAuthenticationError(
                    f"Failed to authenticate {client_type} client: {str(ex)}"
                ) from ex
            except Exception as ex:
                self.logger.error(f"Failed to create {client_type} client: {str(ex)}")
                raise
                
        return self.clients[client_key]
    
    def validate_authentication(self, subscription_id: str) -> bool:
        """
        Validate that authentication is working correctly.
        
        Args:
            subscription_id (str): Azure subscription ID to validate against
            
        Returns:
            bool: True if authentication is valid, False otherwise
        """
        try:
            # Try to get a token
            token = self.credential.get_token("https://management.azure.com/.default")
            if not token:
                self.logger.warning("No token received from credential")
                return False
            
            # Try to list resource groups (minimal permission test)
            resource_client = self.get_client('resource', subscription_id)
            list(resource_client.resource_groups.list(top=1))
            
            self.logger.info(f"Successfully authenticated to subscription {subscription_id}")
            return True
        except Exception as ex:
            self.logger.error(f"Authentication validation failed: {str(ex)}")
            return False
