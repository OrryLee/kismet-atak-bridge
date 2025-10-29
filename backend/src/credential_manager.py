#!/usr/bin/env python3
"""
Secure Credential Manager
Handles secure storage and retrieval of API credentials using OS-level keyring
"""

import logging
import os
from typing import Optional
import base64

logger = logging.getLogger(__name__)

# Try to import keyring, fall back to environment variables
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("keyring library not available, using environment variables only")


class CredentialManager:
    """
    Secure credential management with OS-level keyring support
    
    Security Features:
    - OS-level credential storage (keyring)
    - Environment variable fallback
    - No plaintext storage
    - Credential validation
    """
    
    SERVICE_NAME = "kismet-atak-bridge"
    
    def __init__(self):
        """Initialize credential manager"""
        self.use_keyring = KEYRING_AVAILABLE
        logger.info(f"Credential manager initialized (keyring: {self.use_keyring})")
    
    def store_credential(self, key: str, value: str) -> bool:
        """
        Store a credential securely
        
        Args:
            key: Credential identifier
            value: Credential value
            
        Returns:
            True if successful, False otherwise
        """
        if not key or not value:
            logger.error("Cannot store empty credential")
            return False
        
        try:
            if self.use_keyring:
                keyring.set_password(self.SERVICE_NAME, key, value)
                logger.info(f"Credential stored in keyring: {key}")
            else:
                logger.warning(f"Keyring not available, credential not persisted: {key}")
                logger.info("Set environment variable instead: export KISMET_BRIDGE_{key}=value")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store credential: {e}")
            return False
    
    def get_credential(self, key: str) -> Optional[str]:
        """
        Retrieve a credential
        
        Args:
            key: Credential identifier
            
        Returns:
            Credential value or None if not found
        """
        try:
            # Try keyring first
            if self.use_keyring:
                value = keyring.get_password(self.SERVICE_NAME, key)
                if value:
                    logger.debug(f"Credential retrieved from keyring: {key}")
                    return value
            
            # Fall back to environment variables
            env_key = f"KISMET_BRIDGE_{key.upper()}"
            value = os.getenv(env_key)
            if value:
                logger.debug(f"Credential retrieved from environment: {key}")
                return value
            
            logger.warning(f"Credential not found: {key}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve credential: {e}")
            return None
    
    def delete_credential(self, key: str) -> bool:
        """
        Delete a credential
        
        Args:
            key: Credential identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.use_keyring:
                keyring.delete_password(self.SERVICE_NAME, key)
                logger.info(f"Credential deleted: {key}")
                return True
            else:
                logger.warning(f"Keyring not available, cannot delete: {key}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete credential: {e}")
            return False
    
    def get_kismet_credentials(self) -> tuple:
        """
        Get Kismet API credentials
        
        Returns:
            Tuple of (username, password) or (None, None)
        """
        username = self.get_credential("kismet_username")
        password = self.get_credential("kismet_password")
        return username, password
    
    def store_kismet_credentials(self, username: str, password: str) -> bool:
        """
        Store Kismet API credentials
        
        Args:
            username: Kismet username
            password: Kismet password
            
        Returns:
            True if successful
        """
        success_user = self.store_credential("kismet_username", username)
        success_pass = self.store_credential("kismet_password", password)
        return success_user and success_pass


class SecureConfigLoader:
    """
    Secure configuration loader that separates credentials from config
    """
    
    @staticmethod
    def load_config(config_path: str = "config.json") -> dict:
        """
        Load configuration file without credentials
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
        """
        import json
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Warn if credentials are in config file
            if 'credentials' in config or 'api_keys' in config:
                logger.warning("Credentials found in config file - migrate to keyring!")
                logger.warning("Use credential_manager.store_credential() instead")
            
            return config
            
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return {}


if __name__ == "__main__":
    # Example usage
    cm = CredentialManager()
    
    # Store credentials
    cm.store_kismet_credentials("admin", "secure_password_here")
    
    # Retrieve credentials
    username, password = cm.get_kismet_credentials()
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password) if password else None}")
