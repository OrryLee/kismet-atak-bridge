# Kismet API Implementation Assessment Report

**Date:** October 29, 2025  
**Repository:** https://github.com/OrryLee/kismet-atak-bridge  
**Assessment Type:** Code vs. Official Kismet API Documentation

---

## Executive Summary

After analyzing the official Kismet API documentation and comparing it against our implementation, I have identified **several critical issues** that need to be addressed. While the overall architecture is sound, there are bugs and incorrect API usage patterns that will prevent the system from working correctly with a live Kismet server.

**Overall Status:** ⚠️ **NEEDS IMPROVEMENT**

---

## Critical Issues Found

### 🔴 **CRITICAL ISSUE #1: Incorrect API Endpoint**

**Location:** `backend/src/kismet_client.py`, line 227

**Current Code:**
```python
endpoint = f"/devices/last-time/{last_time}/devices.json"
```

**Problem:**  
According to the official Kismet API documentation, the correct endpoint is:
```
/devices/last-time/{TIMESTAMP}/devices.json
```

However, our implementation is **missing the proper HTTP method handling**. The documentation states:

> "This endpoint takes additional parameters by using a `POST` request and supplying a JSON document or `json` form variable."

**Impact:** The current implementation will work for basic GET requests, but when we try to use field filtering (which we do), we need to send a POST request with the JSON data in the correct format.

**What's Wrong:**
- We're sending `json_data` directly as JSON content type
- Kismet expects either:
  1. A form-encoded POST with `json=<json_string>` parameter, OR
  2. A JSON content type with the JSON directly

Our current implementation does #2, which should work, but we need to verify the `Content-Type` header is set correctly.

---

### 🔴 **CRITICAL ISSUE #2: Missing Content-Type Headers**

**Location:** `backend/src/kismet_client.py`, `_make_request()` method

**Current Code:**
```python
response = self.session.request(
    method=method,
    url=url,
    params=params,
    json=json_data,  # This sets Content-Type automatically
    timeout=self.timeout,
    verify=self.verify_ssl
)
```

**Problem:**  
According to the Kismet API documentation:

> "Parameters sent as JSON content should be sent as type `application/json`:  
> `Content-Type: application/json; charset=UTF-8`"

**Status:** ✅ **Actually OK** - The `requests` library automatically sets `Content-Type: application/json` when using the `json=` parameter. However, we should explicitly verify this for clarity.

---

### 🟡 **ISSUE #3: Incorrect Response Handling**

**Location:** `backend/src/kismet_client.py`, line 240

**Current Code:**
```python
response = self._make_request(
    endpoint,
    method="POST" if json_data else "GET",
    json_data=json_data if json_data else None
)

return response  # Returns the full JSON response
```

**Problem:**  
The Kismet API documentation doesn't clearly specify the response structure, but based on standard Kismet behavior, the `/devices/last-time/{TIMESTAMP}/devices.json` endpoint likely returns an **array of devices directly**, not a wrapper object.

**Impact:** Our `data_formatter.py` expects to receive a list of devices, so this should work. However, we need to verify the actual response structure.

**Recommendation:** Add response structure validation and logging.

---

### 🟡 **ISSUE #4: Field Name Assumptions**

**Location:** `backend/src/data_formatter.py`, lines 140-180

**Current Code:**
```python
mac_fields = [
    "kismet.device.base.macaddr",
    "dot11.device.last_bssid",
    "bluetooth.device.bd_addr"
]
```

**Problem:**  
These field names are **assumptions** based on common Kismet field naming conventions, but we haven't verified them against the actual API documentation. The Kismet documentation shows that field names can vary by PHY type.

**Impact:** If the field names are incorrect, we won't be able to extract MAC addresses, GPS coordinates, or other critical data.

**Recommendation:** We need to verify these field names against actual Kismet responses or use the Kismet field exploration API.

---

### 🟢 **ISSUE #5: Missing Field Simplification**

**Location:** `backend/src/kismet_client.py`, `get_recent_devices()` method

**Current Status:** ✅ **Implemented Correctly**

The implementation correctly supports field simplification:
```python
if fields:
    json_data['fields'] = fields
```

According to the documentation:
> "Field simplification objects take the format of a vector/array containing multiple field definitions"

Our implementation is correct, but we're **not using it** in the bridge service. We should define a minimal field list to reduce bandwidth and processing.

---

### 🟡 **ISSUE #6: Timestamp Handling**

**Location:** `backend/src/kismet_client.py`, lines 220-225

**Current Code:**
```python
if isinstance(last_time, int):
    if last_time > 0 and last_time > time.time():
        raise ValueError("Timestamp cannot be in the future")
```

**Problem:**  
According to the Kismet API documentation:

> "Timestamps can be absolute (UNIX epochal) timestamps, or they can be relative negative numbers, indicating 'number of seconds before now'."

Our validation logic is correct for absolute timestamps, but we're not validating negative (relative) timestamps properly. We should ensure negative values are reasonable (e.g., not less than -86400 for 24 hours).

**Impact:** Minor - the API will accept any negative value, but we should add reasonable bounds checking.

---

### 🟢 **ISSUE #7: Authentication**

**Location:** `backend/src/kismet_client.py`, lines 85-87

**Current Code:**
```python
if username and password:
    self.session.auth = (username, password)
```

**Status:** ✅ **Correct**

The Kismet API uses HTTP Basic Authentication, and our implementation is correct.

---

### 🔴 **CRITICAL ISSUE #8: Device Data Structure**

**Location:** `backend/src/data_formatter.py`, `_safe_get()` method

**Current Code:**
```python
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
```

**Problem:**  
Kismet device records are **deeply nested JSON objects**. The field names use dot notation (e.g., `kismet.device.base.macaddr`), but the actual JSON structure uses nested dictionaries:

```json
{
  "kismet.device.base.macaddr": "AA:BB:CC:DD:EE:FF",
  "kismet.device.base.signal": {
    "kismet.common.signal.last_signal": -65
  }
}
```

Our `_safe_get()` method assumes the keys are **actual dictionary keys**, not paths. This is **incorrect**.

**Correct Approach:**  
Kismet uses **flat keys with dots in them**, not nested paths. So `kismet.device.base.macaddr` is a single key, not a path.

**Impact:** 🔴 **CRITICAL** - Our field extraction will fail completely.

**Fix Required:**
```python
@staticmethod
def _safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from Kismet device record"""
    try:
        # Try direct key access first (Kismet uses flat keys with dots)
        if key in data:
            return data[key]
        
        # If not found, try nested path (for sub-objects)
        keys = key.split('/')
        value = data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value
    except (KeyError, TypeError, AttributeError):
        return default
```

---

### 🟡 **ISSUE #9: Signal Strength Field**

**Location:** `backend/src/data_formatter.py`, lines 215-228

**Current Code:**
```python
signal_fields = [
    "kismet.device.base.signal.last_signal",
    "dot11.device.last_signal",
    "bluetooth.device.rssi"
]
```

**Problem:**  
According to Kismet's data structure, signal information is nested. The correct field path should be:
```
kismet.device.base.signal/kismet.common.signal.last_signal
```

Note the `/` separator for nested objects.

---

### 🟢 **ISSUE #10: ATAK Plugin JSON Parsing**

**Location:** `atak-plugin/src/KismetBridgePlugin.java`, lines 200-230

**Status:** ✅ **Correct**

The ATAK plugin correctly validates the JSON schema and handles the expected data structure.

---

## Summary of Required Changes

### **Must Fix (Critical):**

1. ✅ **Fix `_safe_get()` method** - Change from path-based to direct key access with nested fallback
2. ✅ **Verify field names** - Test against live Kismet server or use field exploration API
3. ✅ **Add field simplification** - Define minimal field list in bridge service
4. ✅ **Fix signal strength field path** - Use correct nested path with `/` separator

### **Should Fix (Important):**

5. ✅ **Add response structure validation** - Verify API response format
6. ✅ **Add timestamp bounds checking** - Validate relative timestamps
7. ✅ **Add explicit Content-Type headers** - For clarity and debugging

### **Nice to Have (Minor):**

8. ✅ **Add field exploration capability** - Allow dynamic field discovery
9. ✅ **Add better error messages** - Include field names in errors
10. ✅ **Add integration tests** - Test against mock Kismet server

---

## Testing Recommendations

### **Before Deployment:**

1. **Test against live Kismet server** - Verify all field names and API endpoints
2. **Test field simplification** - Ensure bandwidth optimization works
3. **Test with various device types** - Wi-Fi, Bluetooth, BLE
4. **Test GPS coordinate extraction** - Verify location data is correct
5. **Test error handling** - Ensure graceful degradation

### **Integration Testing:**

1. Set up a test Kismet server
2. Capture sample device data
3. Verify data flows through the entire pipeline
4. Check ATAK map markers are created correctly

---

## Conclusion

**Overall Assessment:** ⚠️ **NEEDS FIXES BEFORE PRODUCTION USE**

The architecture and security design are excellent, but there are **critical bugs** in the data extraction logic that will prevent the system from working with a live Kismet server.

**Priority Actions:**

1. Fix the `_safe_get()` method (CRITICAL)
2. Verify field names against live Kismet (CRITICAL)
3. Add field simplification to bridge service (HIGH)
4. Test against live Kismet server (HIGH)

**Estimated Time to Fix:** 2-4 hours

**Risk Level:** Medium - The fixes are straightforward, but require testing against a live Kismet server to verify.

---

## Recommended Next Steps

1. **Do NOT deploy to production yet**
2. Fix the critical issues identified above
3. Test against a live Kismet server
4. Update the repository with fixes
5. Re-run security tests
6. Deploy to production

Would you like me to proceed with implementing these fixes?
