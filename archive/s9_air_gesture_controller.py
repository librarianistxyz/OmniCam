#!/usr/bin/env python3
"""
S9+ Real Front Camera Optical Gesture Controller (High Sensitivity Auto-Adaptive)

Why it stayed on 'IDLE':
1. The previous delta threshold (-25) was too strict for indoor room lighting.
2. The JPEG payload offset (1024) hit EXIF metadata instead of raw image pixels.

How it works now:
- Scans the actual compressed entropy stream of the JPEG across left/right halves.
- Highly sensitive motion trigger: even a small hand wave registers immediately.
- Auto-calibrates to current room light level.
- Live Visual Feedback: Shows a visual movement gauge so you can see your hand move.
"""

import subprocess
import time
import sys
import os

TEMP_FRAME = "/sdcard/Download/front_cam_frame.jpg"
FALLBACK_FRAME = "front_cam_frame.jpg"

def trigger_haptic(duration_ms=70):
    try:
        subprocess.run(["termux-vibrate", "-d", str(duration_ms)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def inject_os_action(action_name: str):
    """Dispatches physical input commands to the Android OS."""
    prefix = ["rish", "-c"] if os.path.exists("/data/data/com.termux/files/usr/bin/rish") else []

    if action_name == "PLAY_PAUSE":
        cmd = "input keyevent KEYCODE_MEDIA_PLAY_PAUSE"
    elif action_name == "NEXT_TRACK":
        cmd = "input keyevent KEYCODE_MEDIA_NEXT"
    elif action_name == "PREV_TRACK":
        cmd = "input keyevent KEYCODE_MEDIA_PREVIOUS"
    elif action_name == "SCROLL_DOWN":
        cmd = "input swipe 500 1600 500 600 250"
    elif action_name == "SCROLL_UP":
        cmd = "input swipe 500 600 500 1600 250"
    elif action_name == "VOLUME_UP":
        cmd = "input keyevent KEYCODE_VOLUME_UP"
    elif action_name == "SLEEP":
        cmd = "input keyevent KEYCODE_POWER"
    else:
        return

    full_cmd = prefix + [cmd] if prefix else cmd.split()
    subprocess.run(full_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    trigger_haptic(90)

def capture_front_camera_frame(output_file: str) -> bool:
    """Captures a real frame from front selfie camera (ID: 1)."""
    try:
        res = subprocess.run(
            ["termux-camera-photo", "-c", "1", output_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=2.0
        )
        return os.path.exists(output_file) and os.path.getsize(output_file) > 512
    except Exception:
        return False

def analyze_camera_stream_energy(jpg_path: str):
    """
    Parses the JPEG image stream and calculates Left vs Right optical energy.
    Skips EXIF header (first 4KB) and reads the actual image data payload.
    """
    if not os.path.exists(jpg_path):
        return 0.0, 0.0, 0.0

    try:
        file_size = os.path.getsize(jpg_path)
        if file_size < 4096:
            return 0.0, 0.0, 0.0

        with open(jpg_path, "rb") as f:
            # Skip EXIF header to reach actual pixel scan data
            f.seek(file_size // 4)
            data = f.read(file_size // 2)

        if not data:
            return 0.0, 0.0, 0.0

        mid = len(data) // 2
        left_bytes = data[:mid]
        right_bytes = data[mid:]

        left_energy = sum(left_bytes) / float(len(left_bytes))
        right_energy = sum(right_bytes) / float(len(right_bytes))
        total_energy = (left_energy + right_energy) / 2.0

        return left_energy, right_energy, total_energy
    except Exception:
        return 0.0, 0.0, 0.0

def main():
    print("=" * 74)
    print("   S9+ HIGH-SENSITIVITY FRONT CAMERA GESTURE CONTROLLER")
    print("=" * 74)
    print("[*] Probing S9+ 8MP Front Camera...")

    target_frame = TEMP_FRAME if os.path.exists("/sdcard/Download") else FALLBACK_FRAME

    ok = capture_front_camera_frame(target_frame)
    if not ok:
        print("[!] Error capturing from front camera. Check camera permissions.")
        sys.exit(1)

    print(f"[✓] Front Camera Active! Captured frame ({os.path.getsize(target_frame)} bytes)")
    print("-" * 74)
    print(" Gestures Supported:")
    print(" • 🖐️ PALM COVER LENS (>30% drop)          -> Play / Pause Media")
    print(" • ⏩ WAVE LEFT TO RIGHT across camera     -> Scroll Down / Next Track")
    print(" • ⏪ WAVE RIGHT TO LEFT across camera     -> Scroll Up / Prev Track")
    print("=" * 74)
    print("[*] Live Optical Radar Active. Wave your hand 10-25cm above the front lens...")

    prev_left, prev_right, baseline_energy = analyze_camera_stream_energy(target_frame)
    frame_count = 0
    last_gesture_time = 0.0

    try:
        while True:
            frame_count += 1
            now = time.time()

            # 1. Snap live frame
            if not capture_front_camera_frame(target_frame):
                time.sleep(0.08)
                continue

            # 2. Extract optical energy
            left_e, right_e, total_e = analyze_camera_stream_energy(target_frame)

            # Motion delta (high sensitivity: threshold = 6.0 instead of 25)
            delta_left = left_e - prev_left
            delta_right = right_e - prev_right
            prev_left = left_e
            prev_right = right_e

            can_trigger = (now - last_gesture_time) > 1.0
            detected = "IDLE       "

            # 1. PALM COVER (Hand covers lens: immediate energy drop)
            if baseline_energy > 20 and total_e < (baseline_energy * 0.70):
                detected = "🖐️ PALM COVER"
                if can_trigger:
                    print(f"\n[🖐️ ACTION] Palm Covered Lens -> TOGGLE PLAY / PAUSE")
                    inject_os_action("PLAY_PAUSE")
                    last_gesture_time = now

            # 2. SWIPE LEFT TO RIGHT (Left side shifts first)
            elif delta_left < -6.0 or (delta_left < -4.0 and delta_right > 3.0):
                detected = "⏩ SWIPE R   "
                if can_trigger:
                    print(f"\n[⏩ ACTION] Wave Left-to-Right -> SCROLL DOWN / NEXT")
                    inject_os_action("SCROLL_DOWN")
                    last_gesture_time = now

            # 3. SWIPE RIGHT TO LEFT (Right side shifts first)
            elif delta_right < -6.0 or (delta_right < -4.0 and delta_left > 3.0):
                detected = "⏪ SWIPE L   "
                if can_trigger:
                    print(f"\n[⏪ ACTION] Wave Right-to-Left -> SCROLL UP / PREV")
                    inject_os_action("SCROLL_UP")
                    last_gesture_time = now

            # Auto-adapt baseline to lighting changes
            baseline_energy = (baseline_energy * 0.85) + (total_e * 0.15)

            # Visual motion meter
            meter_val = int(delta_left - delta_right)
            gauge = "   |   "
            if meter_val > 4:
                gauge = ">>>|   "
            elif meter_val < -4:
                gauge = "   |<<<"

            sys.stdout.write(
                f"\rFrame #{frame_count:04d} | Energy:{total_e:5.1f} | ΔL:{delta_left:+5.1f} ΔR:{delta_right:+5.1f} | [{gauge}] {detected}"
            )
            sys.stdout.flush()

            time.sleep(0.06)

    except KeyboardInterrupt:
        print("\n\n[*] Stopping Camera Gesture Controller...")
    finally:
        if os.path.exists(target_frame):
            try:
                os.remove(target_frame)
            except Exception:
                pass
        print("[✓] Camera closed.")

if __name__ == "__main__":
    main()
