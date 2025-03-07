"""
Credential management and configuration.
"""
import os
import logging
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union

from azure.identity import (
    DefaultAzureCredential,
    InteractiveBrowserCredential,
    ClientSecretCredential,
    ManagedIdentityCredential,
    AzureCliCredential,
    DeviceCodeCredential,
    ChainedTokenCredential,
)


@dataclass
class CredentialOptions:
    """Options for creating Azure credentials."""
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    authority: Optional[str] = None
    include_environment: bool = True
    include_managed_identity: bool = True
    include_cli: bool = True
    include_visual_studio: bool = True
    exclude_interactive: bool = False
    logging_enable: bool = True
    timeout: float = 120.0


def get_credential_by_type(auth_method: str, options: CredentialOptions = None):
    """
    Create an Azure credential based on the specified method.
    
    Args:
        auth_method (str): Authentication method to use
        options (CredentialOptions, optional): Options for credential creation
        
    Returns:
        An Azure credential object
        
    Raises:
        ValueError: If an unsupported auth_method is provided
    """
    options = options or CredentialOptions()
    logger = logging.getLogger(__name__)
    
    # If environment variables are set, use them to override options
    tenant_id = options.tenant_id or os.environ.get('AZURE_TENANT_ID')
    client_id = options.client_id or os.environ.get('AZURE_CLIENT_ID')
    client_secret = options.client_secret or os.environ.get('AZURE_CLIENT_SECRET')
    
    if auth_method == "default":
        logger.info("Creating DefaultAzureCredential")
        return DefaultAzureCredential(
            exclude_interactive_browser_credential=options.exclude_interactive,
            exclude_managed_identity_credential=not options.include_managed_identity,
            exclude_visual_studio_code_credential=not options.include_visual_studio,
            exclude_cli_credential=not options.include_cli,
            exclude_environment_credential=not options.include_environment,
            logging_enable=options.logging_enable,
        )
    
    elif auth_method == "browser":
        logger.info("Creating InteractiveBrowserCredential")
        return InteractiveBrowserCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            authority=options.authority,
            login_timeout=options.timeout,
        )
    
    elif auth_method == "service_principal":
        logger.info("Creating ClientSecretCredential")
        if not all([tenant_id, client_id, client_secret]):
            raise ValueError(
                "Service principal authentication requires tenant_id, client_id, and client_secret"
            )
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
    
    elif auth_method == "managed_identity":
        logger.info("Creating ManagedIdentityCredential")
        return ManagedIdentityCredential(
            client_id=client_id
        )
    
    elif auth_method == "cli":
        logger.info("Creating AzureCliCredential")
        return AzureCliCredential()
    
    elif auth_method == "device_code":
        logger.info("Creating DeviceCodeCredential")
        return DeviceCodeCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            timeout=options.timeout,
        )
    
    elif auth_method == "chained":
        logger.info("Creating ChainedTokenCredential")
        credentials = []
        
        # Add credentials to the chain based on options
        if options.include_environment:
            try:
                from azure.identity import EnvironmentCredential
                credentials.append(EnvironmentCredential())
            except Exception as ex:
                logger.warning(f"Could not add EnvironmentCredential to chain: {ex}")
        
        if options.include_managed_identity:
            try:
                credentials.append(ManagedIdentityCredential())
            except Exception as ex:
                logger.warning(f"Could not add ManagedIdentityCredential to chain: {ex}")
        
        if options.include_cli:
            try:
                credentials.append(AzureCliCredential())
            except Exception as ex:
                logger.warning(f"Could not add AzureCliCredential to chain: {ex}")
        
        if not options.exclude_interactive:
            try:
                credentials.append(InteractiveBrowserCredential())
            except Exception as ex:
                logger.warning(f"Could not add InteractiveBrowserCredential to chain: {ex}")
        
        if not credentials:
            raise ValueError("No credentials could be added to the chain")
        
        return ChainedTokenCredential(*credentials)
    
    else:
        raise ValueError(f"Unsupported authentication method: {auth_method}")


def load_credentials_from_file(cred_file_path: str) -> CredentialOptions:
    """
    Load credential options from a JSON file.
    
    Args:
        cred_file_path (str): Path to credentials file
        
    Returns:
        CredentialOptions: Loaded credential options
    """
    logger = logging.getLogger(__name__)
    
    try:
        with open(cred_file_path, 'r') as f:
            creds_dict = json.load(f)
        
        options = CredentialOptions(
            tenant_id=creds_dict.get('tenant_id'),
            client_id=creds_dict.get('client_id'),
            client_secret=creds_dict.get('client_secret'),
            authority=creds_dict.get('authority'),
            include_environment=creds_dict.get('include_environment', True),
            include_managed_identity=creds_dict.get('include_managed_identity', True),
            include_cli=creds_dict.get('include_cli', True),
            include_visual_studio=creds_dict.get('include_visual_studio', True),
            exclude_interactive=creds_dict.get('exclude_interactive', False),
            logging_enable=creds_dict.get('logging_enable', True),
            timeout=float(creds_dict.get('timeout', 120.0)),
        )
        
        logger.info(f"Loaded credentials from {cred_file_path}")
        return options
    
    except Exception as ex:
        logger.error(f"Failed to load credentials from {cred_file_path}: {str(ex)}")
        return CredentialOptions()
