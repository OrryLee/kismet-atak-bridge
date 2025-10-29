#!/usr/bin/env python3
"""
Secure Data Formatter
Converts Kismet device data to WiGLE-compatible JSON format with security mitigations
"""

import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import html

logger = logging.getLogger(__name__)


class DataFormatterError(Exception):
    """Custom exception for data formatting errors"""
    pass


class SecureDataFormatter:
    """
    Secure formatter for converting Kismet data to standardized WiGLE-like JSON
    
    Security Features:
    - Input sanitization
    - XML/JSON escaping
    - Data validation
    - GPS coordinate obfuscation (optional)
    - SSID length limiting
    - MAC address validation
    """
    
    def __init__(self, 
                 gps_precision: int = 6,
                 max_ssid_length: int = 32,
                 obfuscate_gps: bool = False,
                 gps_obfuscation_precision: int = 3):
        """
        Initialize secure data formatter
        
        Args:
            gps_precision: Decimal places for GPS coordinates
            max_ssid_length: Maximum SSID length (security limit)
            obfuscate_gps: Enable GPS coordinate obfuscation for OPSEC
            gps_obfuscation_precision: Precision for obfuscated coordinates
        """
        self.gps_precision = gps_precision
        self.max_ssid_length = max_ssid_length
        self.obfuscate_gps = obfuscate_gps
        self.gps_obfuscation_precision = gps_obfuscation_precision
        
        logger.info(f"Data formatter initialized (GPS obfuscation: {obfuscate_gps})")
    
    def format_devices(self, kismet_devices: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Format multiple Kismet devices to WiGLE-compatible JSON
        
        Args:
            kismet_devices: List of device records from Kismet
            
        Returns:
            Dictionary with 'devices' key containing formatted device list
        """
        formatted_devices = []
        
        for device in kismet_devices:
            try:
                formatted = self._format_single_device(device)
                if formatted:
                    formatted_devices.append(formatted)
            except Exception as e:
                logger.warning(f"Failed to format device: {e}")
                continue
        
        return {"devices": formatted_devices}
    
    def _format_single_device(self, device: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Format a single Kismet device record
        
        Args:
            device: Kismet device record
            
        Returns:
            Formatted device dictionary or None if invalid
        """
        try:
            # Extract device type
            device_type = self._determine_device_type(device)
            if not device_type:
                return None
            
            # Extract and validate MAC address
            mac_address = self._extract_mac_address(device)
            if not mac_address:
                logger.warning("Device missing MAC address")
                return None
            
            # Extract GPS coordinates
            lat, lon, alt = self._extract_gps(device)
            if lat is None or lon is None:
                logger.debug("Device missing GPS coordinates")
                return None
            
            # Build base record
            formatted = {
                "type": device_type,
                "netid": mac_address,
                "trilat": lat,
                "trilong": lon,
                "signal": self._extract_signal_strength(device),
                "firstseen": self._extract_timestamp(device, "first"),
                "lastseen": self._extract_timestamp(device, "last"),
                "source": "kismet"
            }
            
            # Add altitude if available
            if alt is not None:
                formatted["altitude"] = alt
            
            # Add type-specific fields
            if device_type == "wifi":
                self._add_wifi_fields(formatted, device)
            elif device_type in ["bt", "ble"]:
                self._add_bluetooth_fields(formatted, device)
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error formatting device: {e}")
            return None
    
    def _determine_device_type(self, device: Dict[str, Any]) -> Optional[str]:
        """Determine device type from Kismet record"""
        # Check for Wi-Fi device
        if "dot11.device" in device or "kismet.device.base.phyname" in device:
            phy_name = device.get("kismet.device.base.phyname", "")
            if "IEEE802.11" in phy_name or "dot11" in str(device.keys()):
                return "wifi"
        
        # Check for Bluetooth
        if "bluetooth.device" in device:
            # Determine BT vs BLE
            if device.get("bluetooth.device", {}).get("bluetooth.device.le_limited", False):
                return "ble"
            return "bt"
        
        # Default to wifi if uncertain
        return "wifi"
    
    def _extract_mac_address(self, device: Dict[str, Any]) -> Optional[str]:
        """
        Extract and validate MAC address
        
        Args:
            device: Kismet device record
            
        Returns:
            Validated MAC address or None
        """
        # Try common MAC address fields
        mac_fields = [
            "kismet.device.base.macaddr",
            "dot11.device.last_bssid",
            "bluetooth.device.bd_addr"
        ]
        
        for field in mac_fields:
            mac = self._safe_get(device, field)
            if mac and self._validate_mac_address(mac):
                return self._sanitize_mac_address(mac)
        
        return None
    
    def _extract_gps(self, device: Dict[str, Any]) -> tuple:
        """
        Extract and optionally obfuscate GPS coordinates
        
        Args:
            device: Kismet device record
            
        Returns:
            Tuple of (latitude, longitude, altitude)
        """
        # Extract coordinates
        lat = self._safe_get(device, "kismet.device.base.location.avg_lat")
        lon = self._safe_get(device, "kismet.device.base.location.avg_lon")
        alt = self._safe_get(device, "kismet.device.base.location.avg_alt")
        
        # Validate coordinates
        if lat is not None and lon is not None:
            if not self._validate_coordinates(lat, lon):
                logger.warning(f"Invalid coordinates: {lat}, {lon}")
                return None, None, None
            
            # Apply obfuscation if enabled (OPSEC)
            if self.obfuscate_gps:
                lat = round(float(lat), self.gps_obfuscation_precision)
                lon = round(float(lon), self.gps_obfuscation_precision)
                logger.debug("GPS coordinates obfuscated for OPSEC")
            else:
                lat = round(float(lat), self.gps_precision)
                lon = round(float(lon), self.gps_precision)
            
            if alt is not None:
                alt = int(alt)
            
            return lat, lon, alt
        
        return None, None, None
    
    def _extract_signal_strength(self, device: Dict[str, Any]) -> Optional[int]:
        """Extract signal strength (RSSI)"""
        signal_fields = [
            "kismet.device.base.signal.last_signal",
            "dot11.device.last_signal",
            "bluetooth.device.rssi"
        ]
        
        for field in signal_fields:
            signal = self._safe_get(device, field)
            if signal is not None:
                # Validate signal strength range
                signal = int(signal)
                if -120 <= signal <= 0:
                    return signal
        
        return None
    
    def _extract_timestamp(self, device: Dict[str, Any], time_type: str) -> str:
        """
        Extract and format timestamp
        
        Args:
            device: Kismet device record
            time_type: 'first' or 'last'
            
        Returns:
            ISO 8601 formatted timestamp
        """
        field = f"kismet.device.base.{time_type}_time"
        timestamp = self._safe_get(device, field)
        
        if timestamp:
            try:
                # Convert Unix timestamp to ISO 8601
                dt = datetime.fromtimestamp(timestamp)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                pass
        
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _add_wifi_fields(self, formatted: Dict[str, Any], device: Dict[str, Any]) -> None:
        """Add Wi-Fi specific fields"""
        # Extract SSID
        ssid = self._safe_get(device, "dot11.device.last_beaconed_ssid")
        if not ssid:
            ssid = self._safe_get(device, "dot11.device.last_probed_ssid")
        
        if ssid:
            formatted["ssid"] = self._sanitize_ssid(ssid)
        
        # Extract encryption
        encryption = self._safe_get(device, "dot11.device.last_beaconed_ssid_crypt")
        if encryption:
            formatted["encryption"] = self._sanitize_string(str(encryption))
        
        # Extract channel
        channel = self._safe_get(device, "kismet.device.base.channel")
        if channel:
            formatted["channel"] = int(channel)
    
    def _add_bluetooth_fields(self, formatted: Dict[str, Any], device: Dict[str, Any]) -> None:
        """Add Bluetooth specific fields"""
        # Extract device name
        name = self._safe_get(device, "bluetooth.device.name")
        if name:
            formatted["name"] = self._sanitize_string(name)
        
        # Extract manufacturer
        mfgr = self._safe_get(device, "bluetooth.device.manufacturer")
        if mfgr:
            formatted["manufacturer"] = self._sanitize_string(str(mfgr))
    
    @staticmethod
    def _safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Safely get nested dictionary value"""
        try:
            keys = key.split('.')
            value = data
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    @staticmethod
    def _validate_mac_address(mac: str) -> bool:
        """Validate MAC address format"""
        pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(pattern, str(mac)))
    
    @staticmethod
    def _sanitize_mac_address(mac: str) -> str:
        """Sanitize MAC address to standard format"""
        # Remove any non-hex characters except colons and hyphens
        mac = re.sub(r'[^0-9A-Fa-f:-]', '', mac)
        # Convert to uppercase and use colons
        return mac.upper().replace('-', ':')
    
    def _sanitize_ssid(self, ssid: str) -> str:
        """
        Sanitize SSID to prevent injection attacks
        
        Args:
            ssid: Raw SSID string
            
        Returns:
            Sanitized SSID
        """
        # Limit length
        ssid = str(ssid)[:self.max_ssid_length]
        
        # HTML escape to prevent XSS
        ssid = html.escape(ssid)
        
        # Remove control characters
        ssid = ''.join(char for char in ssid if ord(char) >= 32)
        
        return ssid
    
    @staticmethod
    def _sanitize_string(value: str) -> str:
        """Generic string sanitization"""
        # HTML escape
        value = html.escape(str(value))
        
        # Remove control characters
        value = ''.join(char for char in value if ord(char) >= 32)
        
        return value[:256]  # Limit length
    
    @staticmethod
    def _validate_coordinates(lat: float, lon: float) -> bool:
        """Validate GPS coordinates"""
        try:
            lat = float(lat)
            lon = float(lon)
            return -90 <= lat <= 90 and -180 <= lon <= 180
        except (ValueError, TypeError):
            return False


if __name__ == "__main__":
    # Example usage
    formatter = SecureDataFormatter(obfuscate_gps=False)
    
    # Sample Kismet device
    sample_device = {
        "kismet.device.base.macaddr": "AA:BB:CC:DD:EE:FF",
        "kismet.device.base.phyname": "IEEE802.11",
        "kismet.device.base.location.avg_lat": 40.7128,
        "kismet.device.base.location.avg_lon": -74.0060,
        "kismet.device.base.signal.last_signal": -65,
        "kismet.device.base.first_time": 1698451200,
        "kismet.device.base.last_time": 1698451800,
        "dot11.device.last_beaconed_ssid": "TestNetwork",
        "dot11.device.last_beaconed_ssid_crypt": "WPA2"
    }
    
    result = formatter.format_devices([sample_device])
    import json
    print(json.dumps(result, indent=2))
