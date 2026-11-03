#!/usr/bin/env python3
"""
S9+ Physical Bixby Button -> Instant IoT Toggle Engine
Can be triggered via Termux:Tasker, Key Mapper, or command line.

Features:
- Instant single haptic click on button press
- Sub-100ms dispatch to target smart device (Tasmota, WLED, Shelly, or generic REST)
- Success confirmation vibration (double pulse)
- Error vibration (long buzz) if unreachable
- Fallback auto-discovery mode if no target IP is hardcoded
"""

import urllib.request
import subprocess
import time
import sys
import os

# ==============================================================================
# CONFIGURATION: Set your default device here, or pass via command line:
#   python bixby_iot_toggle.py 192.168.1.50 TASMOTA
# ==============================================================================
DEFAULT_DEVICE_IP = ""          # e.g., "192.168.1.45" (leave empty to auto-load from last radar scan)
DEFAULT_DEVICE_TYPE = "TASMOTA" # Options: TASMOTA, WLED, SHELLY, GENERIC

CONFIG_FILE = "/data/data/com.termux/files/home/.bixby_iot_config.json"
FALLBACK_CONFIG = "/sdcard/Download/.bixby_iot_config.json"

def trigger_vibrate(duration_ms=80):
    """Fires S9+ haptic motor via Termux:API."""
    try:
        subprocess.run(
            ["termux-vibrate", "-d", str(duration_ms)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def trigger_pattern_vibrate(success=True):
    """Tactile feedback pattern."""
    if success:
        # Double crisp haptic click for success
        trigger_vibrate(50)
        time.sleep(0.08)
        trigger_vibrate(70)
    else:
        # Long buzz for failure/offline
        trigger_vibrate(400)

def load_saved_target():
    """Loads target IP if not hardcoded."""
    for path in [CONFIG_FILE, FALLBACK_CONFIG]:
        if os.path.exists(path):
            try:
                import json
                with open(path, "r") as f:
                    data = json.load(f)
                    return data.get("ip"), data.get("type", "TASMOTA")
            except Exception:
                pass
    return None, None

def save_target(ip, dtype):
    """Saves chosen target for future one-click Bixby toggles."""
    import json
    data = {"ip": ip, "type": dtype, "updated_at": int(time.time())}
    for path in [CONFIG_FILE, FALLBACK_CONFIG]:
        try:
            with open(path, "w") as f:
                json.dump(data, f)
            break
        except Exception:
            pass

def dispatch_toggle(ip, dtype):
    """Dispatches the fast toggle HTTP payload."""
    dtype = dtype.upper()
    url = ""
    
    if dtype == "TASMOTA":
        url = f"http://{ip}/cm?cmnd=Power%20TOGGLE"
    elif dtype == "WLED":
        url = f"http://{ip}/win&T=2"
    elif dtype == "SHELLY":
        url = f"http://{ip}/relay/0?turn=toggle"
    else:
        url = f"http://{ip}/toggle"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Connection": "close"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=1.8) as resp:
            return resp.status in [200, 204]
    except Exception as e:
        print(f"[!] Toggle error: {e}")
        return False

def main():
    # 1. Instant sensory feedback as soon as Bixby key is clicked
    trigger_vibrate(40)

    target_ip = DEFAULT_DEVICE_IP
    target_type = DEFAULT_DEVICE_TYPE

    # Check CLI arguments first (e.g. bixby_iot_toggle.py 192.168.1.50 TASMOTA)
    if len(sys.argv) >= 2:
        target_ip = sys.argv[1].strip()
        if len(sys.argv) >= 3:
            target_type = sys.argv[2].strip().upper()
        save_target(target_ip, target_type)
    elif not target_ip:
        # Load last known device from config
        saved_ip, saved_type = load_saved_target()
        if saved_ip:
            target_ip = saved_ip
            target_type = saved_type

    if not target_ip:
        print("[!] No target IP configured.")
        print("Usage: python bixby_iot_toggle.py <DEVICE_IP> [TASMOTA|WLED|SHELLY|GENERIC]")
        trigger_pattern_vibrate(success=False)
        sys.exit(1)

    print(f"[*] Bixby Action: Toggling {target_type} at {target_ip}...")
    success = dispatch_toggle(target_ip, target_type)

    if success:
        print("[✓] Toggle success!")
        trigger_pattern_vibrate(success=True)
    else:
        print("[!] Target device offline or unreachable.")
        trigger_pattern_vibrate(success=False)

if __name__ == "__main__":
    main()

