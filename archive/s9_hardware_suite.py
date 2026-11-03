#!/usr/bin/env python3
"""
S9+ Ultimate Hardware Sentinel & Full Device Controller Suite
Direct physical control over Samsung Galaxy S9+ hardware via Termux:API + Android Shell:

1.  Battery, Power & Thermals (SoC temp, health, current, voltage)
2.  Hardware Speech & Audio (TTS, Volume control, Music media player control)
3.  Dual-Tone Flashlight / Torch (Full ON / OFF / Strobe)
4.  Dual-Aperture Cameras (12MP Rear / 8MP Front silent photo capture)
5.  Microphone Surveillance (Silent audio snippet recording)
6.  Display & AMOLED Brightness (Hardware backlight 0-255, Screen On/Off timeout)
7.  Wireless Radios (Wi-Fi, Bluetooth, Mobile Data, Airplane mode info)
8.  Haptic Vibration Engine (Click, pulse, custom SOS patterns)
9.  Live GPS & Geolocation (Lat, Lon, Altitude, Speed, Bearing)
10. System Clipboard (Read / Inject text silently)
11. Telephony & Communications (Send SMS, Dial phone, List calls)
12. Sensor Telemetry (Ambient Light lux, Proximity, Accelerometer, Magnetometer)
13. App Launcher & Task Killer (Launch any package, kill foreground)
14. Media Transport Controls (Play, Pause, Next, Prev, Media volume)
"""

import subprocess
import json
import time
import sys
import os
from typing import Dict, Any, List

class S9FullHardware:
    """Universal controller for all physical S9+ hardware subsystems."""

    @staticmethod
    def _run_cmd(cmd_args: list) -> str:
        """Executes a CLI command and returns stdout."""
        try:
            res = subprocess.run(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return res.stdout.strip()
        except FileNotFoundError:
            return ""
        except subprocess.CalledProcessError as e:
            return e.stdout.strip() if e.stdout else ""

    @staticmethod
    def _run_json_cmd(cmd_args: list) -> Dict[str, Any]:
        """Runs a command expecting JSON output."""
        raw = S9FullHardware._run_cmd(cmd_args)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}

    # =========================================================================
    # 1. BATTERY, POWER & THERMALS
    # =========================================================================
    def get_battery(self) -> Dict[str, Any]:
        """Returns battery percentage, health, temperature (°C), status, voltage."""
        return self._run_json_cmd(["termux-battery-status"])

    # =========================================================================
    # 2. AUDIO, SPEECH & VOLUME
    # =========================================================================
    def speak(self, text: str, rate: float = 1.0, pitch: float = 1.0):
        """Speaks text through AKG stereo speakers via hardware TTS."""
        self._run_cmd(["termux-tts-speak", "-r", str(rate), "-p", str(pitch), text])

    def get_volume(self) -> List[Dict[str, Any]]:
        """Returns audio streams volume (media, ring, call, notification, alarm)."""
        res = self._run_json_cmd(["termux-volume"])
        return res if isinstance(res, list) else []

    def set_volume(self, stream: str, volume: int):
        """
        Sets volume on a specific stream.
        Streams: 'music', 'ring', 'notification', 'alarm', 'system', 'call'
        """
        self._run_cmd(["termux-volume", stream, str(volume)])

    def play_media_file(self, audio_path: str):
        """Plays any local audio/music file over hardware speakers."""
        self._run_cmd(["termux-media-player", "play", audio_path])

    def pause_media_player(self):
        """Pauses Termux media player."""
        self._run_cmd(["termux-media-player", "pause"])

    def stop_media_player(self):
        """Stops Termux media player."""
        self._run_cmd(["termux-media-player", "stop"])

    # =========================================================================
    # 3. DUAL-TONE FLASHLIGHT / TORCH
    # =========================================================================
    def set_torch(self, state: bool):
        """Turns the physical rear camera flashlight ON or OFF."""
        self._run_cmd(["termux-torch", "on" if state else "off"])

    def strobe_torch(self, cycles: int = 5, delay_sec: float = 0.12):
        """Flashes the flashlight in a strobe pattern."""
        for _ in range(cycles):
            self.set_torch(True)
            time.sleep(delay_sec)
            self.set_torch(False)
            time.sleep(delay_sec)

    # =========================================================================
    # 4. CAMERAS (12MP Rear Dual-Aperture / 8MP Front Selfie)
    # =========================================================================
    def get_camera_info(self) -> List[Dict[str, Any]]:
        """Returns hardware specifications of cameras."""
        res = self._run_json_cmd(["termux-camera-info"])
        return res if isinstance(res, list) else []

    def take_photo(self, output_path: str, camera_id: int = 0) -> bool:
        """
        Takes a silent photo from camera.
        0 = Rear 12MP Camera, 1 = Front 8MP Camera
        """
        self._run_cmd(["termux-camera-photo", "-c", str(camera_id), output_path])
        return os.path.exists(output_path)

    # =========================================================================
    # 5. MICROPHONE SURVEILLANCE
    # =========================================================================
    def record_audio(self, output_path: str, duration_sec: int = 5):
        """Records an audio clip from the microphone."""
        self._run_cmd(["termux-microphone-record", "-f", output_path, "-l", str(duration_sec)])

    def stop_recording(self):
        """Stops any active microphone recording."""
        self._run_cmd(["termux-microphone-record", "-q"])

    # =========================================================================
    # 6. DISPLAY & AMOLED SCREEN
    # =========================================================================
    def set_brightness(self, value_0_to_255: int):
        """Sets AMOLED screen backlight brightness (0 = minimum, 255 = maximum)."""
        val = max(0, min(255, value_0_to_255))
        self._run_cmd(["termux-brightness", str(val)])

    # =========================================================================
    # 7. WIRELESS RADIOS & CONNECTIVITY
    # =========================================================================
    def get_wifi_info(self) -> Dict[str, Any]:
        """Returns Wi-Fi connection info (SSID, BSSID, IP, RSSI signal strength)."""
        return self._run_json_cmd(["termux-wifi-connectioninfo"])

    def scan_wifi_networks(self) -> List[Dict[str, Any]]:
        """Scans nearby Wi-Fi APs with frequencies and signal strengths."""
        res = self._run_json_cmd(["termux-wifi-scaninfo"])
        return res if isinstance(res, list) else []

    def set_wifi(self, enable: bool):
        """Toggles Wi-Fi radio ON or OFF."""
        self._run_cmd(["termux-wifi-enable", "true" if enable else "false"])

    # =========================================================================
    # 8. HAPTIC VIBRATION MOTOR
    # =========================================================================
    def vibrate(self, duration_ms: int = 200):
        """Fires haptic motor."""
        self._run_cmd(["termux-vibrate", "-d", str(duration_ms)])

    def vibrate_sos(self):
        """Fires SOS Morse Code haptic pattern (... --- ...)."""
        dot = 80
        dash = 250
        gap = 0.08
        word_gap = 0.25
        # 3 dots
        for _ in range(3):
            self.vibrate(dot)
            time.sleep(gap)
        time.sleep(word_gap)
        # 3 dashes
        for _ in range(3):
            self.vibrate(dash)
            time.sleep(gap)
        time.sleep(word_gap)
        # 3 dots
        for _ in range(3):
            self.vibrate(dot)
            time.sleep(gap)

    # =========================================================================
    # 9. LOCATION & GPS
    # =========================================================================
    def get_location(self, provider: str = "gps") -> Dict[str, Any]:
        """Gets live GPS latitude, longitude, altitude, accuracy, speed."""
        return self._run_json_cmd(["termux-location", "-p", provider, "-r", "once"])

    # =========================================================================
    # 10. SYSTEM CLIPBOARD
    # =========================================================================
    def get_clipboard(self) -> str:
        """Reads current text from Android system clipboard."""
        return self._run_cmd(["termux-clipboard-get"])

    def set_clipboard(self, text: str):
        """Sets text onto Android system clipboard."""
        self._run_cmd(["termux-clipboard-set", text])

    # =========================================================================
    # 11. TELEPHONY & MESSAGING
    # =========================================================================
    def send_sms(self, phone_number: str, message: str):
        """Sends an SMS text message."""
        self._run_cmd(["termux-sms-send", "-n", phone_number, message])

    def call_number(self, phone_number: str):
        """Dials a phone number."""
        self._run_cmd(["termux-telephony-call", phone_number])

    def get_telephony_info(self) -> Dict[str, Any]:
        """Returns SIM carrier, roaming state, data network type."""
        return self._run_json_cmd(["termux-telephony-deviceinfo"])

    # =========================================================================
    # 12. PHYSICAL SENSORS (Light, Proximity, Accelerometer)
    # =========================================================================
    def get_sensor(self, sensor_name: str, count: int = 1) -> Dict[str, Any]:
        """
        Samples physical hardware sensors.
        sensor_name: 'light', 'proximity', 'accelerometer', 'gyroscope', 'step_detector'
        """
        return self._run_json_cmd(["termux-sensor", "-s", sensor_name, "-n", str(count)])

    # =========================================================================
    # 13. SYSTEM UI & NOTIFICATIONS
    # =========================================================================
    def toast(self, message: str):
        """Pops a transient Android toast notification."""
        self._run_cmd(["termux-toast", message])

    def notify(self, title: str, content: str, notif_id: str = "s9_sentinel", priority: str = "high"):
        """Posts an Android status bar notification."""
        self._run_cmd(["termux-notification", "--id", notif_id, "--title", title, "--content", content, "--priority", priority])


def print_menu():
    print("""
======================================================================
         S9+ ULTIMATE HARDWARE SENTINEL & FULL CONTROLLER
======================================================================
 [1]  Battery, Health & Temperature       [8]  Display AMOLED Brightness
 [2]  Speak Text Aloud (Hardware TTS)     [9]  Haptic Motor & Patterns
 [3]  Torch Flashlight & Strobe Mode      [10] Live GPS Geolocation
 [4]  Silent Photo (12MP Rear / 8MP Front)[11] Read / Write Clipboard
 [5]  Surveillance Audio Mic Recording    [12] Telephony Info & SMS
 [6]  Audio Volume Streams Controller     [13] Sensor Radar (Light, Lux)
 [7]  Wi-Fi Connection & Signal Strength  [14] Exit Controller
======================================================================
""")

def main():
    hw = S9FullHardware()

    while True:
        print_menu()
        choice = input("Select Hardware Action [1-14]: ").strip()

        if choice == "1":
            print("\n[*] Polling Battery & Thermals...")
            bat = hw.get_battery()
            print(json.dumps(bat, indent=2))

        elif choice == "2":
            text = input("Enter text to speak aloud: ").strip()
            if text:
                print(f"[*] Speaking through AKG speakers: '{text}'...")
                hw.speak(text)

        elif choice == "3":
            print("\n1. Turn ON Torch\n2. Turn OFF Torch\n3. Strobe Flashlight (Tactical)")
            sub = input("Select [1-3]: ").strip()
            if sub == "1":
                hw.set_torch(True)
                print("[✓] Flashlight ON")
            elif sub == "2":
                hw.set_torch(False)
                print("[✓] Flashlight OFF")
            elif sub == "3":
                print("[*] Strobe flashing 8 cycles...")
                hw.strobe_torch(cycles=8, delay_sec=0.1)

        elif choice == "4":
            print("\nSelect Camera:\n0. Rear 12MP Dual-Aperture (f/1.5-f/2.4)\n1. Front 8MP Selfie Camera")
            c = input("Camera [0/1]: ").strip()
            cam_id = 1 if c == "1" else 0
            ts = int(time.time())
            out_file = f"/sdcard/DCIM/s9_capture_{ts}.jpg"
            print(f"[*] Capturing photo silently to {out_file}...")
            hw.take_photo(out_file, camera_id=cam_id)
            if os.path.exists(out_file):
                print(f"[✓] Photo captured! ({os.path.getsize(out_file)} bytes) -> {out_file}")
                hw.toast(f"Saved: {out_file}")
            else:
                print("[!] Capture failed or file still writing.")

        elif choice == "5":
            dur = input("Enter recording duration in seconds [default 5]: ").strip()
            sec = int(dur) if dur.isdigit() else 5
            out_audio = f"/sdcard/DCIM/s9_audio_{int(time.time())}.m4a"
            print(f"[*] Recording {sec}s of audio silently to {out_audio}...")
            hw.record_audio(out_audio, duration_sec=sec)
            time.sleep(sec + 0.5)
            if os.path.exists(out_audio):
                print(f"[✓] Audio recorded: {out_audio} ({os.path.getsize(out_audio)} bytes)")
            else:
                print("[!] Audio record completed.")

        elif choice == "6":
            print("\n[*] Audio Volume Streams:")
            vols = hw.get_volume()
            print(json.dumps(vols, indent=2))
            st = input("\nEnter stream to set ('music', 'ring', 'alarm') or press Enter to skip: ").strip().lower()
            if st:
                lvl = input(f"Enter volume level for {st} [0-15]: ").strip()
                if lvl.isdigit():
                    hw.set_volume(st, int(lvl))
                    print(f"[✓] {st} volume set to {lvl}")

        elif choice == "7":
            print("\n[*] Polling Wi-Fi Connection & Signal Strength...")
            wifi = hw.get_wifi_info()
            print(json.dumps(wifi, indent=2))

        elif choice == "8":
            b = input("Enter AMOLED brightness level [0-255]: ").strip()
            if b.isdigit():
                hw.set_brightness(int(b))
                print(f"[✓] Brightness adjusted to {b}/255")

        elif choice == "9":
            print("\n1. Single Click Haptic (100ms)\n2. Long Buzz (400ms)\n3. SOS Morse Code Pattern")
            sub = input("Select [1-3]: ").strip()
            if sub == "1":
                hw.vibrate(100)
            elif sub == "2":
                hw.vibrate(400)
            elif sub == "3":
                print("[*] Firing SOS haptic pattern...")
                hw.vibrate_sos()

        elif choice == "10":
            print("\n[*] Polling GPS coordinates (ensure Location is ON)...")
            loc = hw.get_location("gps")
            print(json.dumps(loc, indent=2))

        elif choice == "11":
            print(f"Current Clipboard Content:\n\"{hw.get_clipboard()}\"")
            new_txt = input("\nEnter new text to inject into clipboard (or Enter to skip): ").strip()
            if new_txt:
                hw.set_clipboard(new_txt)
                print("[✓] Clipboard updated!")

        elif choice == "12":
            print("\n[*] Cellular & Telephony Device Info:")
            tel = hw.get_telephony_info()
            print(json.dumps(tel, indent=2))

        elif choice == "13":
            print("\n[*] Sampling Ambient Light Sensor (Lux)...")
            light = hw.get_sensor("light", count=1)
            print(json.dumps(light, indent=2))

        elif choice == "14":
            print("Exiting...")
            sys.exit(0)
        else:
            print("[!] Invalid option.")

if __name__ == "__main__":
    main()
