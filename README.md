# Kismet-to-ATAK Bridge

**A secure, production-ready bridge for visualizing Kismet wireless intelligence in ATAK.**

---

## Overview

This project provides a complete, secure, and robust system for taking real-time wireless signal intelligence from **Kismet** and displaying it as tactical markers on the **Android Team Awareness Kit (ATAK)**. It is designed with operational security (OPSEC) as a primary focus, ensuring that all data remains local and secure.

This system replaces the need for complex, internet-dependent workflows and provides a direct, offline-capable link between your Kismet sensor and your ATAK device.

### Key Features

- **Real-time Visualization:** See Wi-Fi, Bluetooth, and BLE devices on your ATAK map as they are detected by Kismet.
- **Security First:** Implements a comprehensive suite of security mitigations, including TLS encryption, secure credential storage, input validation, and rate limiting.
- **OPSEC-Aware:** No data is ever transmitted to external services. All processing and transmission is local.
- **Configurable GPS Obfuscation:** Optionally reduce the precision of GPS coordinates to protect operator location.
- **Decoupled Architecture:** A Python backend service handles data processing, while the ATAK plugin focuses solely on visualization.
- **Easy Deployment:** Designed for straightforward setup on common hardware like a Raspberry Pi.

---

## Architecture

The system is composed of two main components:

1.  **Backend Bridge Service (Python):** A service that runs on the same machine as Kismet. It polls the Kismet REST API for new device data, formats it into a standardized JSON format, and sends it to the ATAK plugin over a secure local connection.

2.  **ATAK Plugin (Java):** A lightweight ATAK plugin that listens for incoming JSON data from the backend service, validates it, and generates the corresponding Cursor-on-Target (CoT) map markers.

### Data Flow

```
Kismet REST API --> [Backend Bridge] --> Standardized JSON --> [ATAK Plugin] --> CoT XML --> ATAK Map
```

This decoupled design ensures that the components are modular, easy to maintain, and secure.

---

## Security Mitigations

This project was built from the ground up with security in mind. The following mitigations have been implemented and tested:

| Vulnerability Category | Mitigation Strategy |
| :--- | :--- |
| **Data Transmission** | TLS encryption for all data sent to ATAK. |
| **Credential Exposure** | OS-level secure credential storage (via Python `keyring`). No plaintext credentials. |
| **SQL/Code Injection** | All inputs from Kismet are sanitized. XML and JSON special characters are escaped. |
| **Location Data Privacy** | Configurable GPS coordinate obfuscation. No data is ever sent to external services. |
| **Denial of Service (DoS)** | Rate limiting on both Kismet API requests and incoming data to the ATAK plugin. |
| **Database Access** | The backend service only makes read-only requests to the Kismet API. |
| **Data Validation** | Strict validation of all incoming data on both the backend and the ATAK plugin. |

For a full security audit and checklist, please see the `SECURITY.md` file.

---

## Getting Started

### Prerequisites

- **Kismet:** A running Kismet instance with the REST API enabled.
- **ATAK:** A device running ATAK.
- **Backend Host:** A Linux machine (e.g., Raspberry Pi, laptop) to run the backend bridge service.

### 1. Backend Service Setup

**a. Clone the repository:**

```bash
git clone <repository_url>
cd kismet-atak-bridge/backend
```

**b. Install dependencies:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**c. Configure the bridge:**

Edit the `config/bridge_config.json` file to match your setup. At a minimum, you may need to configure the Kismet API credentials if you have them set.

**d. Store Kismet credentials securely:**

Run the interactive setup to store your Kismet username and password in the OS keyring:

```bash
python3 src/bridge_service.py --setup-credentials
```

**e. Run the service:**

```bash
python3 src/bridge_service.py
```

The service will now be running and polling Kismet for new devices.

### 2. ATAK Plugin Setup

**a. Build the plugin:**

Open the `atak-plugin` directory in Android Studio and build the APK.

**b. Install the plugin:**

Sideload the generated APK onto your ATAK device.

**c. Configure ATAK:**

Ensure your ATAK device is on the same network as the backend service. The plugin will automatically start listening for data on port 8087.

---

## Usage

Once both the backend service and the ATAK plugin are running, you will see new wireless devices appear on your ATAK map as they are detected by Kismet. The markers will be typed (Wi-Fi, Bluetooth, BLE) and will contain detailed information in the CoT marker details.

### Marker Details

- **Callsign:** SSID (for Wi-Fi) or device name (for Bluetooth).
- **Type:** Wi-Fi, BT, or BLE.
- **MAC Address:** The unique hardware address of the device.
- **Signal Strength:** The last seen signal strength in dBm.
- **Encryption:** The encryption type for Wi-Fi networks.
- **Timestamps:** First and last time the device was seen.

---

## Development & Testing

### Security Testing

This repository includes a full security testing suite. To run the tests:

```bash
cd kismet-atak-bridge
python3 -m pip install -q pytest
python3 tests/test_security_standalone.py
```

This will run a series of tests to validate the security mitigations and ensure the code is robust against common attack vectors.

### Field Exploration

Before deploying, you can explore the available Kismet API fields using the field explorer tool:

```bash
cd backend/src
python3 field_explorer.py
```

This will:
- Connect to your Kismet server
- Fetch a sample device record
- List all available fields
- Validate the REQUIRED_FIELDS list
- Export a full field report to `kismet_fields_report.json`

This is useful for:
- Verifying field names before deployment
- Understanding the Kismet data structure
- Debugging field extraction issues

---

## License

This project is released under the MIT License. See the `LICENSE` file for details.
