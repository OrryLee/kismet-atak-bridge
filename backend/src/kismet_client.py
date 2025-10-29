#!/usr/bin/env python3
"""
Secure Kismet REST API Client
Implements all security mitigations for safe Kismet database access
"""

import requests
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from urllib.parse import urljoin

# Configure secure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kismet_bridge_security.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class KismetAPIError(Exception):
    """Custom exception for Kismet API errors"""
    pass


class SecureKismetClient:
    """
    Secure client for Kismet REST API with comprehensive security mitigations
    
    Security Features:
    - TLS/SSL verification
    - Session token management
    - Rate limiting
    - Input validation
    - Connection timeout enforcement
    - Credential protection
    """
    
    def __init__(self, 
                 host: str = "127.0.0.1",
                 port: int = 2501,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 use_ssl: bool = False,
                 verify_ssl: bool = True,
                 timeout: int = 30,
                 max_requests_per_minute: int = 60):
        """
        Initialize secure Kismet client
        
        Args:
            host: Kismet server hostname (default: localhost only for security)
            port: Kismet server port
            username: API username (if required)
            password: API password (if required)
            use_ssl: Use HTTPS connection
            verify_ssl: Verify SSL certificates
            timeout: Request timeout in seconds
            max_requests_per_minute: Rate limit for API calls
        """
        # Validate inputs
        self._validate_host(host)
        self._validate_port(port)
        
        # Build base URL
        protocol = "https" if use_ssl else "http"
        self.base_url = f"{protocol}://{host}:{port}"
        
        # Security settings
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Rate limiting
        self.max_requests_per_minute = max_requests_per_minute
        self.request_timestamps: List[float] = []
        
        # Session management
        self.session = requests.Session()
        if username and password:
            self.session.auth = (username, password)
        
        # Connection test
        self._test_connection()
        
        logger.info(f"Secure Kismet client initialized: {self.base_url}")
    
    def _validate_host(self, host: str) -> None:
        """Validate host to prevent SSRF attacks"""
        # Only allow localhost connections for security
        allowed_hosts = ['127.0.0.1', 'localhost', '::1']
        if host not in allowed_hosts:
            logger.warning(f"Non-localhost host attempted: {host}")
            raise ValueError(f"Only localhost connections allowed. Got: {host}")
    
    def _validate_port(self, port: int) -> None:
        """Validate port number"""
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise ValueError(f"Invalid port number: {port}")
    
    def _check_rate_limit(self) -> bool:
        """
        Implement rate limiting to prevent DoS
        
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        now = time.time()
        
        # Remove timestamps older than 1 minute
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if now - ts < 60
        ]
        
        # Check if we've exceeded the limit
        if len(self.request_timestamps) >= self.max_requests_per_minute:
            logger.warning("Rate limit exceeded")
            return False
        
        # Add current timestamp
        self.request_timestamps.append(now)
        return True
    
    def _make_request(self, 
                      endpoint: str, 
                      method: str = "GET",
                      params: Optional[Dict] = None,
                      json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a secure API request with all mitigations
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            params: Query parameters
            json_data: JSON body data
            
        Returns:
            Parsed JSON response
            
        Raises:
            KismetAPIError: On API errors
        """
        # Rate limiting check
        if not self._check_rate_limit():
            raise KismetAPIError("Rate limit exceeded. Please slow down requests.")
        
        # Build full URL
        url = urljoin(self.base_url, endpoint)
        
        try:
            # Make request with timeout
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            # Check for errors
            response.raise_for_status()
            
            # Parse JSON safely
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {endpoint}")
            raise KismetAPIError(f"Request timeout after {self.timeout}s")
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise KismetAPIError(f"Cannot connect to Kismet server")
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise KismetAPIError(f"HTTP error: {e.response.status_code}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise KismetAPIError("Invalid JSON response from server")
    
    def _test_connection(self) -> None:
        """Test connection to Kismet server"""
        try:
            response = self._make_request("/system/status.json")
            logger.info("Kismet connection test successful")
        except KismetAPIError as e:
            logger.error(f"Kismet connection test failed: {e}")
            raise
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get Kismet system status"""
        return self._make_request("/system/status.json")
    
    def get_recent_devices(self, 
                          last_time: Optional[int] = None,
                          fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get devices seen since a specific timestamp
        
        Args:
            last_time: Unix timestamp or negative seconds from now
            fields: List of fields to return (for data minimization)
            
        Returns:
            List of device records
        """
        # Default to last 60 seconds if not specified
        if last_time is None:
            last_time = -60
        
        # Validate timestamp
        if isinstance(last_time, int):
            if last_time > 0 and last_time > time.time():
                raise ValueError("Timestamp cannot be in the future")
        else:
            raise ValueError("Timestamp must be an integer")
        
        endpoint = f"/devices/last-time/{last_time}/devices.json"
        
        # Build request with field filtering for data minimization
        json_data = {}
        if fields:
            json_data['fields'] = fields
        
        response = self._make_request(
            endpoint,
            method="POST" if json_data else "GET",
            json_data=json_data if json_data else None
        )
        
        return response
    
    def get_device_by_key(self, device_key: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific device
        
        Args:
            device_key: Kismet device key
            
        Returns:
            Device record
        """
        # Validate device key format (basic sanitization)
        if not isinstance(device_key, str) or len(device_key) == 0:
            raise ValueError("Invalid device key")
        
        # Sanitize to prevent path traversal
        safe_key = device_key.replace('/', '').replace('\\', '')
        
        endpoint = f"/devices/by-key/{safe_key}/device.json"
        return self._make_request(endpoint)
    
    def get_devices_by_mac(self, mac_address: str) -> List[Dict[str, Any]]:
        """
        Get devices matching a MAC address
        
        Args:
            mac_address: MAC address to search for
            
        Returns:
            List of matching devices
        """
        # Validate MAC address format
        if not self._validate_mac_address(mac_address):
            raise ValueError(f"Invalid MAC address format: {mac_address}")
        
        endpoint = f"/devices/by-mac/{mac_address}/devices.json"
        return self._make_request(endpoint)
    
    @staticmethod
    def _validate_mac_address(mac: str) -> bool:
        """
        Validate MAC address format
        
        Args:
            mac: MAC address string
            
        Returns:
            True if valid, False otherwise
        """
        import re
        # Standard MAC address pattern
        pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(pattern, mac))
    
    def close(self) -> None:
        """Close the session"""
        self.session.close()
        logger.info("Kismet client session closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


if __name__ == "__main__":
    # Example usage
    try:
        with SecureKismetClient(host="127.0.0.1", port=2501) as client:
            # Get system status
            status = client.get_system_status()
            print(f"Kismet Status: {status}")
            
            # Get recent devices
            devices = client.get_recent_devices(last_time=-300)
            print(f"Found {len(devices)} recent devices")
            
    except Exception as e:
        logger.error(f"Error: {e}")
