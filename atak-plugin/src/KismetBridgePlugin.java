package com.kismet.atak.bridge;

import android.content.Context;
import android.content.Intent;
import android.util.Log;

import com.atakmap.android.maps.MapView;
import com.atakmap.android.dropdown.DropDownMapComponent;
import com.atakmap.coremap.cot.event.CotEvent;
import com.atakmap.coremap.cot.event.CotDetail;
import com.atakmap.coremap.coremap.cot.event.CotPoint;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.ServerSocket;
import java.net.Socket;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;
import java.util.UUID;

import javax.net.ssl.SSLServerSocket;
import javax.net.ssl.SSLServerSocketFactory;

/**
 * Kismet-ATAK Bridge Plugin
 * 
 * Receives wireless device data from the Kismet bridge service and displays
 * it on the ATAK map as Cursor-on-Target (CoT) markers.
 * 
 * Security Features:
 * - JSON schema validation
 * - Input sanitization
 * - TLS encryption support
 * - Rate limiting
 * - Malformed data handling
 */
public class KismetBridgePlugin extends DropDownMapComponent {
    
    private static final String TAG = "KismetBridgePlugin";
    
    // Configuration
    private static final int DEFAULT_PORT = 8087;
    private static final boolean USE_TLS = true;
    private static final int MAX_DEVICES_PER_MESSAGE = 1000;
    private static final int MAX_SSID_LENGTH = 32;
    
    // Server components
    private ServerSocket serverSocket;
    private Thread listenerThread;
    private boolean isRunning = false;
    
    // ATAK components
    private Context pluginContext;
    private MapView mapView;
    
    /**
     * Initialize the plugin
     */
    @Override
    public void onCreate(Context context, Intent intent, MapView view) {
        super.onCreate(context, intent, view);
        
        this.pluginContext = context;
        this.mapView = view;
        
        Log.d(TAG, "Kismet Bridge Plugin initialized");
        
        // Start listener service
        startListenerService();
    }
    
    /**
     * Start the listener service for incoming device data
     */
    private void startListenerService() {
        listenerThread = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    // Create server socket (with or without TLS)
                    if (USE_TLS) {
                        SSLServerSocketFactory sslFactory = 
                            (SSLServerSocketFactory) SSLServerSocketFactory.getDefault();
                        serverSocket = sslFactory.createServerSocket(DEFAULT_PORT);
                        Log.i(TAG, "TLS server socket created on port " + DEFAULT_PORT);
                    } else {
                        serverSocket = new ServerSocket(DEFAULT_PORT);
                        Log.i(TAG, "Server socket created on port " + DEFAULT_PORT);
                    }
                    
                    isRunning = true;
                    
                    // Accept connections
                    while (isRunning) {
                        try {
                            Socket clientSocket = serverSocket.accept();
                            Log.d(TAG, "Client connected: " + clientSocket.getInetAddress());
                            
                            // Handle client in separate thread
                            handleClient(clientSocket);
                            
                        } catch (IOException e) {
                            if (isRunning) {
                                Log.e(TAG, "Error accepting client", e);
                            }
                        }
                    }
                    
                } catch (IOException e) {
                    Log.e(TAG, "Error creating server socket", e);
                }
            }
        });
        
        listenerThread.start();
    }
    
    /**
     * Handle incoming client connection
     */
    private void handleClient(Socket clientSocket) {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    BufferedReader reader = new BufferedReader(
                        new InputStreamReader(clientSocket.getInputStream())
                    );
                    
                    StringBuilder jsonBuilder = new StringBuilder();
                    String line;
                    
                    while ((line = reader.readLine()) != null) {
                        jsonBuilder.append(line);
                    }
                    
                    String jsonData = jsonBuilder.toString();
                    Log.d(TAG, "Received data: " + jsonData.length() + " bytes");
                    
                    // Process the JSON data
                    processDeviceData(jsonData);
                    
                    clientSocket.close();
                    
                } catch (IOException e) {
                    Log.e(TAG, "Error reading from client", e);
                }
            }
        }).start();
    }
    
    /**
     * Process device data and create CoT markers
     * 
     * @param jsonData JSON string containing device data
     */
    private void processDeviceData(String jsonData) {
        try {
            JSONObject root = new JSONObject(jsonData);
            
            // Validate schema
            if (!root.has("devices")) {
                Log.e(TAG, "Invalid JSON: missing 'devices' field");
                return;
            }
            
            JSONArray devices = root.getJSONArray("devices");
            
            // Rate limiting check
            if (devices.length() > MAX_DEVICES_PER_MESSAGE) {
                Log.w(TAG, "Too many devices in message: " + devices.length());
                return;
            }
            
            Log.i(TAG, "Processing " + devices.length() + " devices");
            
            // Process each device
            for (int i = 0; i < devices.length(); i++) {
                try {
                    JSONObject device = devices.getJSONObject(i);
                    
                    // Validate and create CoT event
                    if (validateDevice(device)) {
                        CotEvent cotEvent = createCotEvent(device);
                        if (cotEvent != null) {
                            sendCotEvent(cotEvent);
                        }
                    }
                    
                } catch (JSONException e) {
                    Log.e(TAG, "Error processing device " + i, e);
                }
            }
            
        } catch (JSONException e) {
            Log.e(TAG, "Error parsing JSON", e);
        }
    }
    
    /**
     * Validate device data
     * 
     * @param device Device JSON object
     * @return true if valid, false otherwise
     */
    private boolean validateDevice(JSONObject device) {
        try {
            // Required fields
            if (!device.has("type") || !device.has("netid") || 
                !device.has("trilat") || !device.has("trilong")) {
                Log.w(TAG, "Device missing required fields");
                return false;
            }
            
            // Validate type
            String type = device.getString("type");
            if (!type.equals("wifi") && !type.equals("bt") && !type.equals("ble")) {
                Log.w(TAG, "Invalid device type: " + type);
                return false;
            }
            
            // Validate MAC address format
            String netid = device.getString("netid");
            if (!isValidMacAddress(netid)) {
                Log.w(TAG, "Invalid MAC address: " + netid);
                return false;
            }
            
            // Validate GPS coordinates
            double lat = device.getDouble("trilat");
            double lon = device.getDouble("trilong");
            
            if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
                Log.w(TAG, "Invalid GPS coordinates: " + lat + ", " + lon);
                return false;
            }
            
            // Validate SSID length if present
            if (device.has("ssid")) {
                String ssid = device.getString("ssid");
                if (ssid.length() > MAX_SSID_LENGTH) {
                    Log.w(TAG, "SSID too long: " + ssid.length());
                    return false;
                }
            }
            
            return true;
            
        } catch (JSONException e) {
            Log.e(TAG, "Error validating device", e);
            return false;
        }
    }
    
    /**
     * Validate MAC address format
     * 
     * @param mac MAC address string
     * @return true if valid, false otherwise
     */
    private boolean isValidMacAddress(String mac) {
        if (mac == null || mac.isEmpty()) {
            return false;
        }
        
        // Standard MAC address pattern
        String pattern = "^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$";
        return mac.matches(pattern);
    }
    
    /**
     * Create CoT event from device data
     * 
     * @param device Device JSON object
     * @return CotEvent or null if creation failed
     */
    private CotEvent createCotEvent(JSONObject device) {
        try {
            // Extract required fields
            String type = device.getString("type");
            String netid = sanitizeString(device.getString("netid"));
            double lat = device.getDouble("trilat");
            double lon = device.getDouble("trilong");
            
            // Create unique ID
            String uid = "KISMET-" + type.toUpperCase() + "-" + netid.replace(":", "");
            
            // Determine CoT type based on device type
            String cotType = getCotType(type);
            
            // Create CoT event
            CotEvent cotEvent = new CotEvent();
            cotEvent.setUID(uid);
            cotEvent.setType(cotType);
            cotEvent.setHow("h-g-i-g-o"); // GPS-derived
            
            // Set timestamps
            long now = System.currentTimeMillis();
            cotEvent.setTime(new Date(now));
            cotEvent.setStart(new Date(now));
            cotEvent.setStale(new Date(now + 300000)); // 5 minutes
            
            // Set location
            CotPoint point = new CotPoint(lat, lon, 0, 0, 0);
            cotEvent.setPoint(point);
            
            // Add details
            CotDetail detail = new CotDetail();
            
            // Add contact info
            CotDetail contact = new CotDetail("contact");
            String callsign = getCallsign(device, type);
            contact.setAttribute("callsign", sanitizeString(callsign));
            detail.addChild(contact);
            
            // Add remarks with device info
            CotDetail remarks = new CotDetail("remarks");
            String remarksText = buildRemarksText(device, type, netid);
            remarks.setInnerText(sanitizeString(remarksText));
            detail.addChild(remarks);
            
            cotEvent.setDetail(detail);
            
            return cotEvent;
            
        } catch (JSONException e) {
            Log.e(TAG, "Error creating CoT event", e);
            return null;
        }
    }
    
    /**
     * Get CoT type string based on device type
     */
    private String getCotType(String deviceType) {
        switch (deviceType) {
            case "wifi":
                return "a-n-A-W"; // Neutral, WiFi AP
            case "bt":
                return "a-n-A-B"; // Neutral, Bluetooth
            case "ble":
                return "a-n-A-L"; // Neutral, BLE
            default:
                return "a-n-G"; // Neutral, Generic
        }
    }
    
    /**
     * Get callsign for the device
     */
    private String getCallsign(JSONObject device, String type) throws JSONException {
        if (device.has("ssid") && !device.getString("ssid").isEmpty()) {
            return device.getString("ssid");
        } else if (device.has("name") && !device.getString("name").isEmpty()) {
            return device.getString("name");
        } else {
            return type.toUpperCase() + "-" + device.getString("netid").substring(0, 8);
        }
    }
    
    /**
     * Build remarks text with device information
     */
    private String buildRemarksText(JSONObject device, String type, String netid) 
            throws JSONException {
        StringBuilder remarks = new StringBuilder();
        
        remarks.append("Type: ").append(type.toUpperCase()).append("\n");
        remarks.append("MAC: ").append(netid).append("\n");
        
        if (device.has("signal")) {
            remarks.append("Signal: ").append(device.getInt("signal")).append(" dBm\n");
        }
        
        if (device.has("channel")) {
            remarks.append("Channel: ").append(device.getInt("channel")).append("\n");
        }
        
        if (device.has("encryption")) {
            remarks.append("Encryption: ").append(device.getString("encryption")).append("\n");
        }
        
        if (device.has("firstseen")) {
            remarks.append("First Seen: ").append(device.getString("firstseen")).append("\n");
        }
        
        remarks.append("Source: Kismet");
        
        return remarks.toString();
    }
    
    /**
     * Sanitize string to prevent injection attacks
     * 
     * @param input Input string
     * @return Sanitized string
     */
    private String sanitizeString(String input) {
        if (input == null) {
            return "";
        }
        
        // Remove control characters
        input = input.replaceAll("[\u0000-\u001F]", "");
        
        // HTML escape
        input = input.replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;")
                     .replace("\"", "&quot;")
                     .replace("'", "&#x27;");
        
        // Limit length
        if (input.length() > 256) {
            input = input.substring(0, 256);
        }
        
        return input;
    }
    
    /**
     * Send CoT event to ATAK
     * 
     * @param cotEvent CoT event to send
     */
    private void sendCotEvent(CotEvent cotEvent) {
        try {
            // Send to ATAK's CoT dispatcher
            Intent intent = new Intent();
            intent.setAction("com.atakmap.android.maps.COT_PLACED");
            intent.putExtra("cot", cotEvent.toString());
            pluginContext.sendBroadcast(intent);
            
            Log.d(TAG, "CoT event sent: " + cotEvent.getUID());
            
        } catch (Exception e) {
            Log.e(TAG, "Error sending CoT event", e);
        }
    }
    
    /**
     * Cleanup on plugin destruction
     */
    @Override
    protected void onDestroyImpl(Context context, MapView view) {
        isRunning = false;
        
        try {
            if (serverSocket != null && !serverSocket.isClosed()) {
                serverSocket.close();
            }
        } catch (IOException e) {
            Log.e(TAG, "Error closing server socket", e);
        }
        
        super.onDestroyImpl(context, view);
    }
}
