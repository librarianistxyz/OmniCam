#!/usr/bin/env python3
"""
S9+ IoT Discovery Radar & Universal Controller (with Industrial Digital Signage & Commercial Billboard Support)

Supported Hardware:
- Commercial / Industrial LED Billboards:
    * Novastar Taurus Multimedia Players (TB1, TB2, TB30, TB50 via TCP 5200 / HTTP 80 VIPlex API)
    * Colorlight LED Cloud Media Players (C-Series C3/C4/C6 via TCP 5005 / LEDVISION)
    * Huidu Technology Controllers (HD-A30, HD-C16, HD-C36 via TCP 6101 / HDPlayer)
    * Xibo Digital Signage Displays (TCP 9505 / HTTP API)
    * Screenly OSE / Pi Signage (HTTP 80 / 8080 REST API)
- Smart Clocks & Pixel Matrix Boards (Awtrix / Ulanzi TC001 / PixelIt / LaMetric Time)
- Smart Home Lighting & Relays (Tasmota, WLED, Shelly, ESPHome)
- Media Receivers (Chromecast / Google Cast)

Features:
- Silent scan with physical haptic vibration when complete (no speech)
- Auto-detects industrial billboard controllers and smart signs
- Dedicated Commercial Billboard Controller Menu:
    1. Push Live Text / Banner to Billboard
    2. Switch Billboard Display Program / Playlist
    3. Blank / Blackout Billboard Screen (Mute Display)
    4. Wake / Restore Live Broadcast Schedule
    5. Query Billboard Telemetry & Status
"""

import socket
import struct
import subprocess
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
import sys
import time

# Standard Chromium on Raspberry Pi OS (Debian arm64) to disguise traffic as a local Raspberry Pi workstation
STEALTH_CHROME_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Common Signage & IoT Ports to Probe
SIGNAGE_PORTS = [80, 8080, 5005, 5200, 6101, 9505, 8008, 8123, 1883, 554]

def trigger_vibrate(duration_ms=300):
    """Triggers S9+ physical haptic motor via Termux:API (No Speech)."""
    try:
        subprocess.run(
            ["termux-vibrate", "-d", str(duration_ms)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def get_local_subnet():
    """Detects phone's current Wi-Fi IP and subnet."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    
    if ip == '127.0.0.1':
        return None, None
    
    parts = ip.split('.')
    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}"
    return ip, subnet

def probe_port(ip, port, timeout=1.0):
    """
    Checks if a TCP port is open.
    Enforces strict timeout and guarantees immediate socket teardown (SO_LINGER 0)
    to prevent lingering in CLOSE_WAIT, TIME_WAIT, or ESTABLISHED states.
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        # Force immediate hard close without lingering in kernel table
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        result = sock.connect_ex((ip, port))
        return result == 0
    except Exception:
        return False
    finally:
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

def audit_http_fingerprint(ip, port=80):
    """Inspects HTTP web server banners to fingerprint signage controllers."""
    url = f"http://{ip}:{port}"
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': STEALTH_CHROME_USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=1.8) as resp:
            headers = str(resp.headers).lower()
            body = resp.read(4096).decode('utf-8', errors='ignore').lower()
            
            # Industrial Billboards & Commercial Signage
            if "novastar" in body or "taurus" in body or "viplex" in body:
                return "OPEN_ZERO_ADMIN", "NOVASTAR", "Novastar Taurus LED Billboard Controller (VIPlex)"
            elif "colorlight" in body or "ledvision" in body:
                return "OPEN_ZERO_ADMIN", "COLORLIGHT", "Colorlight LED Cloud Controller (C-Series)"
            elif "huidu" in body or "hdplayer" in body:
                return "OPEN_ZERO_ADMIN", "HUIDU", "Huidu Commercial LED Controller"
            elif "screenly" in body:
                return "OPEN_ZERO_ADMIN", "SCREENLY", "Screenly OSE Digital Signage Display"
            elif "xibo" in body:
                return "CHECK_AUTH", "XIBO", "Xibo Digital Signage Player"
            
            # Pixel Matrix Clocks & Smart Devices
            elif "awtrix" in body or "ulanzi" in body or "tc001" in body:
                return "OPEN_ZERO_ADMIN", "AWTRIX", "Awtrix / Ulanzi TC001 LED Matrix Display"
            elif "pixelit" in body:
                return "OPEN_ZERO_ADMIN", "PIXELIT", "PixelIt Matrix Display"
            elif "lametric" in body:
                return "PAIRING_REQUIRED", "LAMETRIC", "LaMetric Time Smart Clock"
            elif "wled" in body:
                return "OPEN_ZERO_ADMIN", "WLED", "WLED Smart LED Light Strip / Matrix"
            elif "tasmota" in body:
                return "OPEN_ZERO_ADMIN", "TASMOTA", "Tasmota Smart Relay / Bulb"
            elif "shelly" in body:
                return "OPEN_ZERO_ADMIN", "SHELLY", "Shelly Smart Relay / Switch"
            elif "esphome" in body:
                return "OPEN_ZERO_ADMIN", "ESPHOME", "ESPHome Sensor Node"
            elif resp.status == 200:
                if any(x in body for x in ["password", "login", "sign in", "auth"]):
                    return "PROTECTED_AUTH", "GENERIC_WEB_AUTH", "Web UI (Login Form Required)"
                return "OPEN_POTENTIAL", "GENERIC_HTTP", "Open HTTP Endpoint (No Auth Prompt)"
            
    except urllib.error.HTTPError as e:
        if e.code in [401, 403]:
            return "PROTECTED_AUTH", "AUTH_GATED", f"Auth-Gated (HTTP {e.code})"
        return "UNKNOWN_HTTP", "HTTP_ERR", f"HTTP Error {e.code}"
    except Exception:
        pass
    
    return "UNKNOWN", "UNKNOWN", "Silent Web Server"

def scan_host(ip):
    """Probes a single IP for industrial billboard & smart ports."""
    open_ports = []
    for port in SIGNAGE_PORTS:
        if probe_port(ip, port):
            open_ports.append(port)
            
    if not open_ports:
        return None

    device = {
        "ip": ip,
        "ports": open_ports,
        "auth_category": "UNKNOWN",
        "device_type": "UNKNOWN",
        "description": "General Network Host"
    }

    # 1. Check Specific Industrial Billboard Ports First
    if 5200 in open_ports:
        device["auth_category"] = "OPEN_ZERO_ADMIN"
        device["device_type"] = "NOVASTAR"
        device["description"] = "Novastar Taurus LED Billboard Controller (VIPlex TCP 5200)"
        return device
    elif 5005 in open_ports:
        device["auth_category"] = "OPEN_ZERO_ADMIN"
        device["device_type"] = "COLORLIGHT"
        device["description"] = "Colorlight LED Billboard Controller (LEDVISION TCP 5005)"
        return device
    elif 6101 in open_ports:
        device["auth_category"] = "OPEN_ZERO_ADMIN"
        device["device_type"] = "HUIDU"
        device["description"] = "Huidu Commercial LED Display Controller (HDPlayer TCP 6101)"
        return device
    elif 9505 in open_ports:
        device["auth_category"] = "CHECK_AUTH"
        device["device_type"] = "XIBO"
        device["description"] = "Xibo Signage Player (TCP 9505)"
        return device

    # 2. Check HTTP/Web ports
    if 80 in open_ports or 8080 in open_ports:
        p = 80 if 80 in open_ports else 8080
        category, dtype, desc = audit_http_fingerprint(ip, p)
        device["auth_category"] = category
        device["device_type"] = dtype
        device["description"] = desc
    elif 8008 in open_ports:
        device["auth_category"] = "OPEN_ZERO_ADMIN"
        device["device_type"] = "CAST"
        device["description"] = "Google Cast / Smart Display"
    elif 1883 in open_ports:
        device["auth_category"] = "PROTECTED_AUTH"
        device["device_type"] = "MQTT"
        device["description"] = "MQTT IoT Broker"
    elif 554 in open_ports:
        device["auth_category"] = "CHECK_AUTH"
        device["device_type"] = "RTSP"
        device["description"] = "RTSP Video Stream / IP Camera"

    return device

# ==============================================================================
# DISPATCH COMMANDS FOR INDUSTRIAL BILLBOARDS & SIGNAGE
# ==============================================================================

def execute_http_request(url, method="GET", payload=None, timeout=1.5):
    """Helper to dispatch HTTP REST payloads disguised as Google Chrome with strict 1.5s timeout."""
    try:
        data = json.dumps(payload).encode('utf-8') if payload else None
        headers = {
            "User-Agent": STEALTH_CHROME_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "close"
        }
        if payload:
            headers["Content-Type"] = "application/json"
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            return True, content
    except Exception as e:
        return False, str(e)

def send_raw_tcp_socket(ip, port, payload_bytes, timeout=1.5):
    """
    Sends raw TCP commands to industrial controllers.
    Enforces strict 1.5s timeout, SO_LINGER 0, and explicit teardown in finally block.
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        # Disallow socket linger; force immediate RST/teardown on close
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        sock.connect((ip, port))
        sock.sendall(payload_bytes)
        try:
            response = sock.recv(1024)
        except Exception:
            response = b""
        return True, response.hex()
    except Exception as e:
        return False, str(e)
    finally:
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

def control_industrial_billboard(device):
    """Control interface for commercial Novastar, Colorlight, Huidu, and Screenly signs."""
    ip = device["ip"]
    dtype = device["device_type"]

    while True:
        print(f"\n=================================================================")
        print(f" 🏢 COMMERCIAL LED BILLBOARD CONTROLLER: [{ip}] ({dtype})")
        print(f"=================================================================")
        print("1. 📢 Push Live Banner / Emergency Text to Billboard")
        print("2. 🔀 Switch Display Program / Playlist Source")
        print("3. ⬛ Screen Blackout / Blank Display (Mute LEDs)")
        print("4. 💡 Screen Wake / Unblank (Restore LED Output)")
        print("5. 🔄 Restore Default Broadcast Schedule")
        print("6. 📊 Query Controller Telemetry & Health")
        print("-----------------------------------------------------------------")
        print("7. ⬅️ Back to Discovered Devices List")
        print("=================================================================")

        cmd = input("Select Billboard Action [1-7]: ").strip()

        if cmd == "1":
            text = input("Enter banner text to display: ").strip()
            if text:
                print(f"[*] Dispatching live banner '{text}' to {ip}...")
                trigger_vibrate(80)
                if dtype == "NOVASTAR":
                    # Novastar Taurus VIPlex API endpoint for emergency subtitle/text overlay
                    payload = {"message": text, "speed": 5, "color": "0xFF0000", "stayTime": 15}
                    ok, res = execute_http_request(f"http://{ip}/api/v1/screen/notice", method="POST", payload=payload)
                elif dtype == "SCREENLY":
                    # Screenly OSE inject live text asset
                    payload = {"name": "S9 Alert", "asset_url": f"data:text/html,<h1>{text}</h1>", "mimetype": "web"}
                    ok, res = execute_http_request(f"http://{ip}/api/v1/assets", method="POST", payload=payload)
                elif dtype == "COLORLIGHT":
                    # Colorlight JSON command packet over TCP 5005
                    raw_cmd = json.dumps({"cmd": "show_text", "text": text, "color": "red"}).encode('utf-8')
                    ok, res = send_raw_tcp_socket(ip, 5005, raw_cmd)
                elif dtype == "HUIDU":
                    # Huidu HDPlayer protocol notice packet over TCP 6101
                    raw_cmd = f"HDACTION:NOTIFY:{text}\r\n".encode('utf-8')
                    ok, res = send_raw_tcp_socket(ip, 6101, raw_cmd)
                else:
                    ok, res = execute_http_request(f"http://{ip}/api/message", method="POST", payload={"text": text})
                
                print("[✓] Live text pushed to billboard!" if ok else f"[!] Error dispatching text: {res}")
                trigger_vibrate(150)

        elif cmd == "2":
            prog = input("Enter Program / Page index number [e.g. 1, 2, 3]: ").strip()
            if prog.isdigit():
                print(f"[*] Switching {ip} to Program {prog}...")
                trigger_vibrate(80)
                if dtype == "NOVASTAR":
                    ok, res = execute_http_request(f"http://{ip}/api/v1/screen/program?index={prog}", method="POST")
                elif dtype == "COLORLIGHT":
                    raw_cmd = json.dumps({"cmd": "switch_program", "program_index": int(prog)}).encode('utf-8')
                    ok, res = send_raw_tcp_socket(ip, 5005, raw_cmd)
                elif dtype == "SCREENLY":
                    ok, res = execute_http_request(f"http://{ip}/api/v1/assets/switch?index={prog}", method="POST")
                else:
                    ok, res = execute_http_request(f"http://{ip}/switch?page={prog}")
                
                print(f"[✓] Switched to Program {prog}!" if ok else f"[!] Notice: {res}")
                trigger_vibrate(120)

        elif cmd == "3":
            print(f"[*] Sending Screen Blackout / Blank command to {ip}...")
            trigger_vibrate(100)
            if dtype == "NOVASTAR":
                # Novastar Taurus API screen power off / black
                ok, res = execute_http_request(f"http://{ip}/api/v1/screen/power", method="POST", payload={"powerState": "black"})
            elif dtype == "COLORLIGHT":
                raw_cmd = json.dumps({"cmd": "set_screen_state", "state": "black"}).encode('utf-8')
                ok, res = send_raw_tcp_socket(ip, 5005, raw_cmd)
            elif dtype == "HUIDU":
                raw_cmd = b"HDACTION:SCREEN:OFF\r\n"
                ok, res = send_raw_tcp_socket(ip, 6101, raw_cmd)
            elif dtype == "SCREENLY":
                ok, res = execute_http_request(f"http://{ip}/api/v1/display/standby", method="POST")
            else:
                ok, res = execute_http_request(f"http://{ip}/power?state=off")
            
            print("[✓] Billboard Blackout active (LEDs muted)!" if ok else f"[!] Notice: {res}")
            trigger_vibrate(200)

        elif cmd == "4":
            print(f"[*] Sending Screen Wake / Unblank command to {ip}...")
            trigger_vibrate(80)
            if dtype == "NOVASTAR":
                ok, res = execute_http_request(f"http://{ip}/api/v1/screen/power", method="POST", payload={"powerState": "on"})
            elif dtype == "COLORLIGHT":
                raw_cmd = json.dumps({"cmd": "set_screen_state", "state": "on"}).encode('utf-8')
                ok, res = send_raw_tcp_socket(ip, 5005, raw_cmd)
            elif dtype == "HUIDU":
                raw_cmd = b"HDACTION:SCREEN:ON\r\n"
                ok, res = send_raw_tcp_socket(ip, 6101, raw_cmd)
            elif dtype == "SCREENLY":
                ok, res = execute_http_request(f"http://{ip}/api/v1/display/on", method="POST")
            else:
                ok, res = execute_http_request(f"http://{ip}/power?state=on")
            
            print("[✓] Billboard screen unblanked and active!" if ok else f"[!] Notice: {res}")
            trigger_vibrate(150)

        elif cmd == "5":
            print(f"[*] Restoring default broadcast playlist on {ip}...")
            trigger_vibrate(80)
            if dtype == "NOVASTAR":
                # Clear active alerts and resume regular program schedule
                execute_http_request(f"http://{ip}/api/v1/screen/notice/clear", method="POST")
                ok, res = execute_http_request(f"http://{ip}/api/v1/screen/program/resume", method="POST")
            elif dtype == "SCREENLY":
                ok, res = execute_http_request(f"http://{ip}/api/v1/playlist/resume", method="POST")
            elif dtype == "COLORLIGHT":
                raw_cmd = json.dumps({"cmd": "resume_schedule"}).encode('utf-8')
                ok, res = send_raw_tcp_socket(ip, 5005, raw_cmd)
            else:
                ok, res = execute_http_request(f"http://{ip}/reset")
            
            print("[✓] Default broadcast schedule restored!" if ok else f"[!] Notice: {res}")
            trigger_vibrate(150)

        elif cmd == "6":
            print(f"[*] Querying status and telemetry from {ip}...")
            if dtype == "NOVASTAR":
                ok, res = execute_http_request(f"http://{ip}/api/v1/screen/status")
            elif dtype == "SCREENLY":
                ok, res = execute_http_request(f"http://{ip}/api/v1/system_info")
            else:
                ok, res = execute_http_request(f"http://{ip}/")
            
            if ok:
                try:
                    parsed = json.loads(res)
                    print(json.dumps(parsed, indent=2))
                except Exception:
                    print(res[:600])
            else:
                print(f"[!] Controller response: {res}")

        elif cmd == "7":
            break

def control_matrix_smart_clock(device):
    """Control interface for hobbyist pixel matrix clocks (Awtrix, Ulanzi, PixelIt)."""
    ip = device["ip"]
    dtype = device["device_type"]

    while True:
        print(f"\n=======================================================")
        print(f" 📟 PIXEL CLOCK / MATRIX DISPLAY: [{ip}] ({dtype})")
        print(f"=======================================================")
        print("1. Push Scrolling Text / Notification")
        print("2. Flash Alert Message (Red Warning)")
        print("3. Set Display Brightness")
        print("4. Toggle Display Power (ON / OFF)")
        print("5. 🔄 RESTORE BACK TO ORIGINAL (Resume Clock Loop)")
        print("6. ⬅️ Back to Device List")
        print("=======================================================")

        choice = input("Select Action [1-6]: ").strip()

        if choice == "1":
            text = input("Enter text to display: ").strip()
            if text:
                trigger_vibrate(80)
                if dtype == "AWTRIX":
                    ok, res = execute_http_request(f"http://{ip}/api/notify", method="POST", payload={"text": text, "repeat": 2, "color": [0, 255, 200]})
                elif dtype == "PIXELIT":
                    ok, res = execute_http_request(f"http://{ip}/api/screen", method="POST", payload={"text": {"textString": text, "hexColor": "#00FFC8"}})
                else:
                    ok, res = execute_http_request(f"http://{ip}/api/custom?name=s9", method="POST", payload={"text": text})
                print("[✓] Text pushed!" if ok else f"[!] Failed: {res}")
                trigger_vibrate(150)

        elif choice == "2":
            alert_text = input("Enter alert headline [default: 'SECURITY ALERT']: ").strip()
            if not alert_text:
                alert_text = "SECURITY ALERT"
            trigger_vibrate(120)
            if dtype == "AWTRIX":
                ok, res = execute_http_request(f"http://{ip}/api/notify", method="POST", payload={"text": alert_text, "color": [255, 0, 0], "repeat": 3, "blinkText": 2})
            else:
                ok, res = execute_http_request(f"http://{ip}/api/screen", method="POST", payload={"text": {"textString": alert_text, "hexColor": "#FF0000"}})
            print("[✓] Alert sent!" if ok else f"[!] Failed: {res}")
            trigger_vibrate(150)

        elif choice == "3":
            bri = input("Enter brightness [0-100%]: ").strip()
            if bri.isdigit():
                val = int(bri)
                if dtype == "AWTRIX":
                    ok, res = execute_http_request(f"http://{ip}/api/settings", method="POST", payload={"BRI": int(val * 2.55)})
                else:
                    ok, res = execute_http_request(f"http://{ip}/api/brightness", method="POST", payload={"brightness": val})
                print("[✓] Brightness updated!" if ok else f"[!] Failed: {res}")
                trigger_vibrate(100)

        elif choice == "4":
            trigger_vibrate(80)
            if dtype == "AWTRIX":
                ok, res = execute_http_request(f"http://{ip}/api/power", method="POST", payload={"power": "toggle"})
            else:
                ok, res = execute_http_request(f"http://{ip}/toggle")
            print("[✓] Power toggle sent!" if ok else f"[!] Failed: {res}")
            trigger_vibrate(120)

        elif choice == "5":
            trigger_vibrate(80)
            if dtype == "AWTRIX":
                execute_http_request(f"http://{ip}/api/notify/dismiss", method="POST", payload={})
                execute_http_request(f"http://{ip}/api/custom?name=s9", method="POST", payload={})
                ok, res = execute_http_request(f"http://{ip}/api/loop", method="POST", payload={})
            else:
                ok, res = execute_http_request(f"http://{ip}/api/screen", method="POST", payload={"clock": True})
            print("[✓] Restored back to default clock loop!" if ok else f"[!] Notice: {res}")
            trigger_vibrate(150)

        elif choice == "6":
            break

def control_generic_iot(device):
    """Control interface for smart plugs, bulbs, and relays."""
    ip = device["ip"]
    dtype = device["device_type"]

    while True:
        print(f"\n=======================================================")
        print(f" 💡 SMART DEVICE CONTROLLER: [{ip}] ({dtype})")
        print(f"=======================================================")
        print("1. Toggle Power / Light")
        print("2. Turn ON")
        print("3. Turn OFF")
        print("4. Query Status / Telemetry")
        print("5. Back to Device List")
        print("=======================================================")

        cmd = input("Select Action [1-5]: ").strip()

        if cmd == "1":
            trigger_vibrate(80)
            if dtype == "TASMOTA":
                ok, res = execute_http_request(f"http://{ip}/cm?cmnd=Power%20TOGGLE")
            elif dtype == "WLED":
                ok, res = execute_http_request(f"http://{ip}/win&T=2")
            elif dtype == "SHELLY":
                ok, res = execute_http_request(f"http://{ip}/relay/0?turn=toggle")
            else:
                ok, res = execute_http_request(f"http://{ip}/toggle")
            print("[✓] Toggle sent!" if ok else f"[!] Failed: {res}")
            trigger_vibrate(120)

        elif cmd == "2":
            trigger_vibrate(80)
            if dtype == "TASMOTA":
                ok, res = execute_http_request(f"http://{ip}/cm?cmnd=Power%20ON")
            elif dtype == "WLED":
                ok, res = execute_http_request(f"http://{ip}/win&T=1")
            elif dtype == "SHELLY":
                ok, res = execute_http_request(f"http://{ip}/relay/0?turn=on")
            else:
                ok, res = execute_http_request(f"http://{ip}/on")
            print("[✓] Power ON sent!" if ok else f"[!] Failed: {res}")
            trigger_vibrate(120)

        elif cmd == "3":
            trigger_vibrate(80)
            if dtype == "TASMOTA":
                ok, res = execute_http_request(f"http://{ip}/cm?cmnd=Power%20OFF")
            elif dtype == "WLED":
                ok, res = execute_http_request(f"http://{ip}/win&T=0")
            elif dtype == "SHELLY":
                ok, res = execute_http_request(f"http://{ip}/relay/0?turn=off")
            else:
                ok, res = execute_http_request(f"http://{ip}/off")
            print("[✓] Power OFF sent!" if ok else f"[!] Failed: {res}")
            trigger_vibrate(120)

        elif cmd == "4":
            print(f"[*] Querying status from {ip}...")
            if dtype == "TASMOTA":
                ok, res = execute_http_request(f"http://{ip}/cm?cmnd=Status%200")
            elif dtype == "WLED":
                ok, res = execute_http_request(f"http://{ip}/json/state")
            elif dtype == "SHELLY":
                ok, res = execute_http_request(f"http://{ip}/status")
            else:
                ok, res = execute_http_request(f"http://{ip}/")
            
            if ok:
                try:
                    parsed = json.loads(res)
                    print(json.dumps(parsed, indent=2))
                except Exception:
                    print(res[:500])
            else:
                print(f"[!] Error: {res}")

        elif cmd == "5":
            break

def main():
    print("""
======================================================================
 S9+ UNIVERSAL IoT & COMMERCIAL BILLBOARD DISCOVERY RADAR
======================================================================
 Scanning Subnet for:
 • Industrial Signs (Novastar Taurus, Colorlight, Huidu, Screenly, Xibo)
 • Pixel Matrix Clocks (Awtrix, Ulanzi TC001, PixelIt, LaMetric)
 • Smart Bulbs & Relays (Tasmota, WLED, Shelly, ESPHome)
======================================================================
""")
    local_ip, subnet = get_local_subnet()
    if not subnet:
        print("[!] No Wi-Fi connected. Connect to your workshop Wi-Fi and re-run.")
        sys.exit(1)

    print(f"[*] Phone Local IP : {local_ip}")
    print(f"[*] Subnet Scanning: {subnet}.1 - {subnet}.254...")
    print("[*] Probing Industrial Billboard Ports (5200, 5005, 6101, 9505, 80/8080)...\n")

    targets = [f"{subnet}.{i}" for i in range(1, 255) if f"{subnet}.{i}" != local_ip]

    discovered = []
    with ThreadPoolExecutor(max_workers=60) as executor:
        results = executor.map(scan_host, targets)
        for r in results:
            if r:
                discovered.append(r)

    # Silent Haptic Alert on scan completion
    print("\n[✓] Scan Complete!")
    trigger_vibrate(350)

    open_devices = [d for d in discovered if "OPEN" in d["auth_category"]]
    protected_devices = [d for d in discovered if "OPEN" not in d["auth_category"]]

    while True:
        print("\n======================================================================")
        print("🟢 CONTROLLABLE COMMERCIAL SIGNS & SMART DEVICES (Direct Access):")
        print("======================================================================")
        if not open_devices:
            print("  (No direct-access signs or devices found on this subnet)")
        else:
            for idx, d in enumerate(open_devices, start=1):
                dtype = d["device_type"]
                if dtype in ["NOVASTAR", "COLORLIGHT", "HUIDU", "SCREENLY", "XIBO"]:
                    tag = "🏢 LIVE BILLBOARD"
                elif dtype in ["AWTRIX", "PIXELIT", "LAMETRIC"]:
                    tag = "📟 PIXEL CLOCK"
                else:
                    tag = "💡 SMART BULB/RELAY"
                print(f"  [{idx}] {tag:<20} IP: {d['ip']:<15} Ports: {str(d['ports']):<12} -> {d['description']}")

        print("\n----------------------------------------------------------------------")
        print("🔒 PROTECTED / CREDENTIALS REQUIRED (Auth-gated / Login / Token):")
        print("----------------------------------------------------------------------")
        if not protected_devices:
            print("  (No auth-gated devices detected)")
        else:
            for d in protected_devices:
                print(f"  • IP: {d['ip']:<15} Ports: {str(d['ports']):<12} -> {d['description']}")

        print("----------------------------------------------------------------------")
        print("[R] Rescan Workshop Network | [Q] Quit")
        
        choice = input("\nEnter device number to control (or R/Q): ").strip().upper()

        if choice == "Q":
            print("Exiting...")
            sys.exit(0)
        elif choice == "R":
            return main()
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(open_devices):
                selected = open_devices[idx - 1]
                dtype = selected["device_type"]
                if dtype in ["NOVASTAR", "COLORLIGHT", "HUIDU", "SCREENLY", "XIBO"]:
                    control_industrial_billboard(selected)
                elif dtype in ["AWTRIX", "PIXELIT", "LAMETRIC"]:
                    control_matrix_smart_clock(selected)
                else:
                    control_generic_iot(selected)
            else:
                print("[!] Number out of range.")
        else:
            print("[!] Invalid option.")

if __name__ == "__main__":
    main()
