# Deployment Guide

This guide provides step-by-step instructions for deploying the Kismet-to-ATAK Bridge in a production environment.

---

## Deployment Architecture

The recommended deployment architecture is:

```
┌─────────────────┐
│  Kismet Server  │
│  (Raspberry Pi) │
│                 │
│  - Kismet       │
│  - Bridge       │
└────────┬────────┘
         │
         │ Local Network
         │
┌────────┴────────┐
│   ATAK Device   │
│   (Android)     │
│                 │
│  - ATAK App     │
│  - Bridge Plugin│
└─────────────────┘
```

---

## Hardware Requirements

### Backend Server (Kismet + Bridge)

- **Recommended:** Raspberry Pi 4 (4GB RAM or higher)
- **Minimum:** Any Linux machine with Python 3.7+
- **Storage:** 16GB+ SD card or SSD
- **Network:** Wi-Fi adapter capable of monitor mode (e.g., Alfa AWUS036ACH)

### ATAK Device

- **Android device** running ATAK (version 4.0+)
- **Network:** Wi-Fi or cellular connection to the backend server

---

## Step-by-Step Deployment

### Phase 1: Backend Server Setup

#### 1.1 Install Kismet

On your Raspberry Pi or Linux server:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Kismet
wget -O - https://www.kismetwireless.net/repos/kismet-release.gpg.key | sudo apt-key add -
echo 'deb https://www.kismetwireless.net/repos/apt/release/bullseye bullseye main' | sudo tee /etc/apt/sources.list.d/kismet.list
sudo apt update
sudo apt install kismet

# Add your user to the kismet group
sudo usermod -aG kismet $USER

# Reboot to apply group changes
sudo reboot
```

#### 1.2 Configure Kismet

Edit `/etc/kismet/kismet.conf`:

```bash
sudo nano /etc/kismet/kismet.conf
```

Add or modify the following lines:

```
# Enable REST API
httpd_username=admin
httpd_password=your_secure_password_here

# Set your Wi-Fi adapter
source=wlan1:name=monitor

# Enable GPS if available
gps=gpsd:host=localhost,port=2947
```

Start Kismet:

```bash
sudo systemctl enable kismet
sudo systemctl start kismet
```

#### 1.3 Install Bridge Service

Clone the repository:

```bash
cd ~
git clone https://github.com/YourUsername/kismet-atak-bridge.git
cd kismet-atak-bridge/backend
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 1.4 Configure the Bridge

Edit the configuration file:

```bash
nano config/bridge_config.json
```

Key settings to review:

```json
{
  "kismet": {
    "host": "127.0.0.1",
    "port": 2501
  },
  "formatter": {
    "obfuscate_gps": false
  },
  "atak": {
    "host": "0.0.0.0",
    "port": 8087,
    "use_tls": true
  }
}
```

**Important:** Set `atak.host` to `0.0.0.0` to allow connections from other devices on the network.

#### 1.5 Store Credentials

Run the credential setup:

```bash
python3 src/bridge_service.py --setup-credentials
```

Enter your Kismet username and password when prompted.

#### 1.6 Create Systemd Service

Create a systemd service file for automatic startup:

```bash
sudo nano /etc/systemd/system/kismet-bridge.service
```

Add the following content:

```ini
[Unit]
Description=Kismet-ATAK Bridge Service
After=network.target kismet.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/kismet-atak-bridge/backend
ExecStart=/home/pi/kismet-atak-bridge/backend/venv/bin/python3 /home/pi/kismet-atak-bridge/backend/src/bridge_service.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable kismet-bridge
sudo systemctl start kismet-bridge
```

Check the status:

```bash
sudo systemctl status kismet-bridge
```

---

### Phase 2: ATAK Plugin Deployment

#### 2.1 Build the Plugin

On your development machine with Android Studio:

1. Open the `atak-plugin` directory in Android Studio
2. Build the APK: **Build → Build Bundle(s) / APK(s) → Build APK(s)**
3. Locate the generated APK in `atak-plugin/build/outputs/apk/`

#### 2.2 Install on ATAK Device

Transfer the APK to your ATAK device and install it:

```bash
adb install -r kismet-bridge-plugin.apk
```

Or manually copy the APK to the device and install via the file manager.

#### 2.3 Configure Network Connection

On the ATAK device, ensure it can reach the backend server:

- If using Wi-Fi, connect to the same network as the Raspberry Pi
- If using cellular, ensure the backend server has a public IP or VPN connection

Test connectivity:

```bash
# From ATAK device terminal
ping <backend_server_ip>
telnet <backend_server_ip> 8087
```

---

### Phase 3: Verification

#### 3.1 Check Backend Logs

On the backend server:

```bash
tail -f ~/kismet-atak-bridge/backend/bridge_service.log
```

You should see:

```
2025-10-29 12:00:00 - INFO - Bridge service initialized successfully
2025-10-29 12:00:01 - INFO - Connected to Kismet: 2024-10-R1
2025-10-29 12:00:05 - INFO - Found 5 devices
2025-10-29 12:00:05 - INFO - Formatted 5 devices
2025-10-29 12:00:05 - INFO - Sent 5 devices to ATAK
```

#### 3.2 Check ATAK Map

Open ATAK on your device. You should see:

- Wi-Fi access points appearing as markers on the map
- Bluetooth devices appearing as markers
- Markers updating in real-time as devices are detected

---

## Troubleshooting

### Backend Issues

**Problem:** Bridge cannot connect to Kismet

**Solution:**
- Check that Kismet is running: `sudo systemctl status kismet`
- Verify credentials are correct
- Check firewall: `sudo ufw allow 2501`

**Problem:** No devices being detected

**Solution:**
- Verify Kismet is capturing: `kismet_client`
- Check that your Wi-Fi adapter is in monitor mode
- Ensure GPS is working if you need location data

### ATAK Plugin Issues

**Problem:** No markers appearing on ATAK

**Solution:**
- Check network connectivity between ATAK device and backend
- Verify the plugin is installed and running
- Check ATAK logs for errors

**Problem:** TLS connection errors

**Solution:**
- If using self-signed certificates, you may need to disable TLS verification
- Set `use_tls: false` in the backend config for testing

---

## Security Hardening for Production

1. **Enable TLS:** Always use TLS in production environments
2. **Firewall Rules:** Restrict access to port 8087 to only trusted devices
3. **GPS Obfuscation:** Enable GPS obfuscation if operating in sensitive areas
4. **Credential Rotation:** Regularly rotate Kismet API credentials
5. **Log Monitoring:** Set up log monitoring and alerting for security events

---

## Performance Tuning

For high-density environments with many devices:

1. **Increase Poll Interval:** Reduce backend polling frequency to avoid overwhelming the system
2. **Reduce Lookback Window:** Process only the most recent devices
3. **Enable Rate Limiting:** Ensure rate limits are appropriate for your environment

Example optimized config:

```json
{
  "service": {
    "poll_interval": 10,
    "lookback_seconds": 30
  },
  "security": {
    "max_devices_per_minute": 500
  }
}
```

---

## Maintenance

### Regular Tasks

- **Weekly:** Check logs for errors or security events
- **Monthly:** Update Kismet and the bridge service
- **Quarterly:** Review and rotate credentials

### Backup

Back up the following:

- Configuration files: `backend/config/`
- Credentials (if using keyring, these are backed up with your OS)
- Custom ignore lists or filters

---

## Support

For issues, questions, or contributions, please open an issue on the GitHub repository.
