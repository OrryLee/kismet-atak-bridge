#!/usr/bin/env python3
"""
Kismet Field Explorer
Utility to explore and validate available fields in Kismet API
"""

import logging
import json
from typing import Dict, List, Optional, Any
from kismet_client import SecureKismetClient, KismetAPIError

logger = logging.getLogger(__name__)


class KismetFieldExplorer:
    """
    Utility class for exploring Kismet API fields
    
    This helps developers understand what fields are available
    and validate field names before using them in production.
    """
    
    def __init__(self, kismet_client: SecureKismetClient):
        """
        Initialize field explorer
        
        Args:
            kismet_client: Configured Kismet client
        """
        self.client = kismet_client
    
    def get_tracked_fields(self) -> Optional[Dict[str, Any]]:
        """
        Get all tracked fields from Kismet
        
        Returns:
            Dictionary of tracked fields with descriptions
        """
        try:
            logger.info("Fetching tracked fields from Kismet")
            response = self.client._make_request("/system/tracked_fields.json")
            return response
        except KismetAPIError as e:
            logger.error(f"Failed to fetch tracked fields: {e}")
            return None
    
    def explore_device_fields(self, device_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Explore fields in a sample device record
        
        Args:
            device_key: Specific device key to explore, or None for recent device
            
        Returns:
            Sample device record with all fields
        """
        try:
            if device_key:
                logger.info(f"Fetching device: {device_key}")
                device = self.client.get_device_by_key(device_key)
            else:
                logger.info("Fetching recent devices")
                devices = self.client.get_recent_devices(last_time=-300)  # Last 5 minutes
                if not devices:
                    logger.warning("No recent devices found")
                    return None
                device = devices[0]
            
            return device
            
        except KismetAPIError as e:
            logger.error(f"Failed to fetch device: {e}")
            return None
    
    def list_available_fields(self, device: Dict[str, Any], prefix: str = "") -> List[str]:
        """
        Recursively list all available fields in a device record
        
        Args:
            device: Device record dictionary
            prefix: Current field path prefix
            
        Returns:
            List of all field paths
        """
        fields = []
        
        for key, value in device.items():
            full_key = f"{prefix}/{key}" if prefix else key
            fields.append(full_key)
            
            # If value is a dict, recurse
            if isinstance(value, dict):
                nested_fields = self.list_available_fields(value, full_key)
                fields.extend(nested_fields)
        
        return fields
    
    def validate_fields(self, field_list: List[str], sample_device: Dict[str, Any]) -> Dict[str, bool]:
        """
        Validate that a list of fields exists in a sample device
        
        Args:
            field_list: List of field names to validate
            sample_device: Sample device record
            
        Returns:
            Dictionary mapping field names to existence (True/False)
        """
        results = {}
        
        for field in field_list:
            # Try direct access
            if field in sample_device:
                results[field] = True
                continue
            
            # Try nested path with /
            if '/' in field:
                parts = field.split('/')
                value = sample_device
                found = True
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        found = False
                        break
                results[field] = found
            else:
                results[field] = False
        
        return results
    
    def print_field_report(self, device: Dict[str, Any]) -> None:
        """
        Print a human-readable report of available fields
        
        Args:
            device: Device record to analyze
        """
        print("\n" + "="*80)
        print("KISMET DEVICE FIELD REPORT")
        print("="*80)
        
        fields = self.list_available_fields(device)
        
        print(f"\nTotal fields found: {len(fields)}")
        print("\nField List:")
        print("-" * 80)
        
        for field in sorted(fields):
            print(f"  {field}")
        
        print("\n" + "="*80)
    
    def export_fields_to_file(self, device: Dict[str, Any], filename: str) -> None:
        """
        Export field list to a file
        
        Args:
            device: Device record to analyze
            filename: Output filename
        """
        fields = self.list_available_fields(device)
        
        with open(filename, 'w') as f:
            json.dump({
                "total_fields": len(fields),
                "fields": sorted(fields),
                "sample_device": device
            }, f, indent=2)
        
        logger.info(f"Exported {len(fields)} fields to {filename}")


def main():
    """Main function for standalone field exploration"""
    import sys
    from credential_manager import CredentialManager
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Get credentials
    cred_manager = CredentialManager()
    username, password = cred_manager.get_kismet_credentials()
    
    # Create Kismet client
    client = SecureKismetClient(
        host='127.0.0.1',
        port=2501,
        username=username,
        password=password
    )
    
    # Create explorer
    explorer = KismetFieldExplorer(client)
    
    # Explore device fields
    print("Fetching sample device...")
    device = explorer.explore_device_fields()
    
    if device:
        explorer.print_field_report(device)
        
        # Export to file
        output_file = "kismet_fields_report.json"
        explorer.export_fields_to_file(device, output_file)
        print(f"\nFull report exported to: {output_file}")
        
        # Validate our required fields
        from bridge_service import REQUIRED_FIELDS
        print("\nValidating REQUIRED_FIELDS...")
        validation = explorer.validate_fields(REQUIRED_FIELDS, device)
        
        missing = [f for f, exists in validation.items() if not exists]
        if missing:
            print(f"\n⚠️  WARNING: {len(missing)} required fields not found:")
            for field in missing:
                print(f"  - {field}")
        else:
            print("✅ All required fields validated successfully!")
    else:
        print("❌ Failed to fetch device data")
        sys.exit(1)


if __name__ == "__main__":
    main()
