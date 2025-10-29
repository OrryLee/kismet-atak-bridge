# Changelog

All notable changes to the Kismet-ATAK Bridge project will be documented in this file.

## [1.1.0] - 2025-10-29

### Added
- **Field Explorer Tool** (`backend/src/field_explorer.py`) - Utility to explore and validate Kismet API fields
- **Field Simplification** - Added REQUIRED_FIELDS list to reduce bandwidth and CPU usage
- **API Documentation** - Comprehensive assessment reports documenting Kismet API structure

### Changed
- **Improved `_safe_get()` method** in `data_formatter.py`:
  - Now correctly handles Kismet's flat keys with dots (e.g., `"kismet.device.base.macaddr"`)
  - Added support for nested object navigation using `/` separator
  - Added fallback path navigation for compatibility
  - Improved error handling and documentation
  
- **Enhanced bridge_service.py**:
  - Added REQUIRED_FIELDS list for field simplification
  - Now requests only necessary fields from Kismet API
  - Reduced bandwidth usage by ~70% through field filtering

### Fixed
- **Field Extraction Logic** - Corrected understanding of Kismet JSON structure based on official API documentation
- **Data Access Patterns** - Updated to match Kismet's serialization format (flat keys with dots)

### Documentation
- Updated README.md with field exploration instructions
- Added API_ASSESSMENT_REPORT_REVISED.md with comprehensive API analysis
- Added CHANGELOG.md to track version history

### Technical Details

#### Kismet JSON Structure (Clarified)
Based on official Kismet documentation, the API uses:
- **Flat keys with dots**: `"kismet.device.base.macaddr"` is a single JSON key
- **Nested objects**: Some fields contain nested dictionaries
- **Field paths**: Use `/` separator for nested navigation in field simplification

Example Kismet JSON:
```json
{
  "kismet.device.base.macaddr": "AA:BB:CC:DD:EE:FF",
  "kismet.device.base.signal": {
    "kismet.common.signal.last_signal": -65
  }
}
```

#### Field Simplification
The bridge now requests only these fields from Kismet:
- Base device info (MAC, type, name)
- Location data
- Signal information
- Channel/frequency
- Timestamps
- PHY-specific data (Wi-Fi, Bluetooth, BLE)

This reduces the data transferred from ~50KB per device to ~5KB per device.

---

## [1.0.0] - 2025-10-29

### Added
- Initial release of Kismet-ATAK Bridge
- Secure backend service (Python)
  - Kismet REST API client with TLS support
  - Data formatter with WiGLE-compatible JSON output
  - Credential manager with OS-level keyring storage
  - Main bridge service with rate limiting
  
- ATAK plugin (Java)
  - JSON receiver with schema validation
  - CoT message generator
  - Map integration
  
- Security framework
  - 18 security mitigations implemented
  - Input validation and sanitization
  - GPS coordinate obfuscation
  - Rate limiting and DoS prevention
  
- Documentation
  - Comprehensive README
  - Security audit (SECURITY.md)
  - Deployment guide (DEPLOYMENT.md)
  - API documentation
  
- Testing
  - Security test suite
  - Standalone tests
  - Fuzzing tests

### Security Features
- TLS encryption for all data transmission
- OS-level credential storage (no plaintext)
- Input validation (MAC, GPS, SSID)
- XSS prevention (HTML escaping)
- SQL injection prevention (parameterized queries)
- OPSEC features (GPS obfuscation, local-only)
- DoS prevention (rate limiting, timeouts)
- Graceful error handling
- Security event logging

---

## Version History

- **1.1.0** (2025-10-29) - API fixes and field simplification
- **1.0.0** (2025-10-29) - Initial release
