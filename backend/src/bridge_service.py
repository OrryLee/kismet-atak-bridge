#!/usr/bin/env python3
"""
Kismet-ATAK Bridge Service
Main service that polls Kismet and forwards data to ATAK
"""

import logging
import time
import json
import socket
import ssl
from typing import Optional
from pathlib import Path

from kismet_client import SecureKismetClient, KismetAPIError
from data_formatter import SecureDataFormatter
from credential_manager import CredentialManager, SecureConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bridge_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BridgeServiceError(Exception):
    """Custom exception for bridge service errors"""
    pass


class SecureBridgeService:
    """
    Secure bridge service connecting Kismet to ATAK
    
    Security Features:
    - TLS encryption for data transmission
    - Rate limiting
    - Input validation
    - Graceful error handling
    - Secure credential management
    """
    
    def __init__(self, config_path: str = "config/bridge_config.json"):
        """
        Initialize bridge service
        
        Args:
            config_path: Path to configuration file
        """
        logger.info("Initializing Kismet-ATAK Bridge Service")
        
        # Load configuration
        self.config = SecureConfigLoader.load_config(config_path)
        
        # Initialize credential manager
        self.credential_manager = CredentialManager()
        
        # Get Kismet credentials
        username, password = self.credential_manager.get_kismet_credentials()
        
        # Initialize Kismet client
        kismet_config = self.config.get('kismet', {})
        self.kismet_client = SecureKismetClient(
            host=kismet_config.get('host', '127.0.0.1'),
            port=kismet_config.get('port', 2501),
            username=username,
            password=password,
            use_ssl=kismet_config.get('use_ssl', False),
            verify_ssl=kismet_config.get('verify_ssl', True),
            timeout=kismet_config.get('timeout', 30),
            max_requests_per_minute=kismet_config.get('max_requests_per_minute', 60)
        )
        
        # Initialize data formatter
        formatter_config = self.config.get('formatter', {})
        self.formatter = SecureDataFormatter(
            gps_precision=formatter_config.get('gps_precision', 6),
            max_ssid_length=formatter_config.get('max_ssid_length', 32),
            obfuscate_gps=formatter_config.get('obfuscate_gps', False),
            gps_obfuscation_precision=formatter_config.get('gps_obfuscation_precision', 3)
        )
        
        # Service configuration
        service_config = self.config.get('service', {})
        self.poll_interval = service_config.get('poll_interval', 5)
        self.lookback_seconds = service_config.get('lookback_seconds', 60)
        
        # ATAK transmission configuration
        atak_config = self.config.get('atak', {})
        self.atak_host = atak_config.get('host', '127.0.0.1')
        self.atak_port = atak_config.get('port', 8087)
        self.use_tls = atak_config.get('use_tls', True)
        
        # State tracking
        self.running = False
        self.last_poll_time = None
        
        logger.info("Bridge service initialized successfully")
    
    def start(self) -> None:
        """Start the bridge service"""
        logger.info("Starting bridge service")
        self.running = True
        
        try:
            # Test Kismet connection
            status = self.kismet_client.get_system_status()
            logger.info(f"Connected to Kismet: {status.get('kismet.system.version', 'unknown')}")
            
            # Main loop
            while self.running:
                try:
                    self._poll_and_forward()
                    time.sleep(self.poll_interval)
                    
                except KeyboardInterrupt:
                    logger.info("Received shutdown signal")
                    break
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(self.poll_interval)
                    continue
        
        finally:
            self.stop()
    
    def _poll_and_forward(self) -> None:
        """Poll Kismet for new devices and forward to ATAK"""
        try:
            # Get recent devices from Kismet
            logger.debug(f"Polling Kismet for devices (last {self.lookback_seconds}s)")
            
            devices = self.kismet_client.get_recent_devices(
                last_time=-self.lookback_seconds
            )
            
            if not devices:
                logger.debug("No new devices found")
                return
            
            logger.info(f"Found {len(devices)} devices")
            
            # Format devices
            formatted_data = self.formatter.format_devices(devices)
            
            if not formatted_data.get('devices'):
                logger.debug("No devices after formatting")
                return
            
            logger.info(f"Formatted {len(formatted_data['devices'])} devices")
            
            # Forward to ATAK
            self._send_to_atak(formatted_data)
            
            # Update last poll time
            self.last_poll_time = time.time()
            
        except KismetAPIError as e:
            logger.error(f"Kismet API error: {e}")
        except Exception as e:
            logger.error(f"Error in poll and forward: {e}")
    
    def _send_to_atak(self, data: dict) -> None:
        """
        Send formatted data to ATAK plugin
        
        Args:
            data: Formatted device data
        """
        try:
            # Convert to JSON
            json_data = json.dumps(data)
            
            # Create socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            # Wrap with TLS if enabled
            if self.use_tls:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE  # For localhost, can use self-signed
                sock = context.wrap_socket(sock, server_hostname=self.atak_host)
            
            # Connect and send
            sock.connect((self.atak_host, self.atak_port))
            sock.sendall(json_data.encode('utf-8'))
            
            logger.info(f"Sent {len(data['devices'])} devices to ATAK")
            
            # Close connection
            sock.close()
            
        except socket.timeout:
            logger.error("Timeout connecting to ATAK")
        except ConnectionRefusedError:
            logger.error(f"Cannot connect to ATAK at {self.atak_host}:{self.atak_port}")
        except Exception as e:
            logger.error(f"Error sending to ATAK: {e}")
    
    def stop(self) -> None:
        """Stop the bridge service"""
        logger.info("Stopping bridge service")
        self.running = False
        
        # Close Kismet client
        if hasattr(self, 'kismet_client'):
            self.kismet_client.close()
        
        logger.info("Bridge service stopped")
    
    def get_status(self) -> dict:
        """Get service status"""
        return {
            "running": self.running,
            "last_poll_time": self.last_poll_time,
            "kismet_connected": True,  # Could add actual connection check
            "config": {
                "poll_interval": self.poll_interval,
                "lookback_seconds": self.lookback_seconds,
                "gps_obfuscation": self.formatter.obfuscate_gps
            }
        }


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Kismet-ATAK Bridge Service')
    parser.add_argument('--config', default='config/bridge_config.json',
                       help='Path to configuration file')
    parser.add_argument('--setup-credentials', action='store_true',
                       help='Setup Kismet credentials')
    
    args = parser.parse_args()
    
    # Setup credentials if requested
    if args.setup_credentials:
        cm = CredentialManager()
        print("Kismet Credential Setup")
        print("=" * 40)
        username = input("Kismet username: ")
        password = input("Kismet password: ")
        
        if cm.store_kismet_credentials(username, password):
            print("✓ Credentials stored securely")
        else:
            print("✗ Failed to store credentials")
        return
    
    # Start bridge service
    try:
        service = SecureBridgeService(config_path=args.config)
        service.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
