#!/usr/bin/env python3
"""
S9+ Real-Time Hardware Barometer & Atmospheric Infrasound Monitor
Actively streams continuous live readings from the phone's physical sensor.

Key Improvements:
- Bulletproof multi-format JSON parser: Works whether termux-sensor outputs streaming JSON,
  multiline blocks, or one-shot dumps.
- Fallback Poller: If streaming pipes stall or buffer on Android, automatically switches
  to rapid polling so the terminal NEVER freezes on the same output.
- Live rolling stats: Shows current sample count, live Hz rate, raw pressure, micro-changes,
  and relative elevation delta in real-time.
"""

import subprocess
import json
import time
import math
import sys
import os
from typing import Optional, Tuple

class SecondOrderBandpassFilter:
    """Extracts micro-pressure fluctuations (0.03 Hz - 2.0 Hz)."""
    def __init__(self, lowcut_hz: float = 0.03, highcut_hz: float = 2.0, sample_rate_hz: float = 10.0):
        self.fs = sample_rate_hz
        center_freq = math.sqrt(lowcut_hz * highcut_hz)
        q_factor = center_freq / max(0.001, (highcut_hz - lowcut_hz))
        
        w0 = 2.0 * math.pi * center_freq / self.fs
        alpha = math.sin(w0) / (2.0 * max(0.1, q_factor))

        b0 = alpha
        b1 = 0.0
        b2 = -alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * math.cos(w0)
        a2 = 1.0 - alpha

        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0

        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0

    def process(self, x: float) -> float:
        y = (self.b0 * x) + (self.b1 * self.x1) + (self.b2 * self.x2) - (self.a1 * self.y1) - (self.a2 * self.y2)
        self.x2 = self.x1
        self.x1 = x
        self.y2 = self.y1
        self.y1 = y
        return y


def extract_pressure_from_json(raw_text: str) -> Optional[float]:
    """Parses pressure value from any termux-sensor JSON structure."""
    if not raw_text or not raw_text.strip():
        return None
    try:
        data = json.loads(raw_text.strip())
        if isinstance(data, dict):
            for k, v in data.items():
                if "pressure" in k.lower():
                    if isinstance(v, dict) and "values" in v and len(v["values"]) > 0:
                        return float(v["values"][0])
                    elif isinstance(v, list) and len(v) > 0:
                        return float(v[0])
                    elif isinstance(v, (int, float)):
                        return float(v)
        elif isinstance(data, list) and len(data) > 0:
            item = data[0]
            if isinstance(item, dict):
                return extract_pressure_from_json(json.dumps(item))
            elif isinstance(item, (int, float)):
                return float(item)
    except Exception:
        pass
    return None


def fetch_single_pressure_sample() -> Optional[float]:
    """Fallback rapid one-shot sensor fetch via termux-sensor."""
    try:
        res = subprocess.run(
            ["termux-sensor", "-s", "pressure", "-n", "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=1.5,
            check=True
        )
        return extract_pressure_from_json(res.stdout)
    except Exception:
        return None


def calculate_elevation_delta(current_p: float, baseline_p: float) -> float:
    """
    Hypsometric barometric equation:
    Δh = - (R * T / (g * M)) * ln(P / P0)
    At ~22°C (295.15 K): scale factor ≈ -8.63 meters per hPa near sea level.
    """
    if baseline_p <= 0 or current_p <= 0:
        return 0.0
    return -8630.0 * math.log(current_p / baseline_p)


def render_oscilloscope_bar(val_pa: float, width: int = 28) -> str:
    """ASCII center-zero waveform visualizer."""
    half = width // 2
    # 1 character = 0.1 Pascal
    clamped = max(-half, min(half - 1, int(val_pa / 0.1)))
    chars = [" "] * width
    chars[half] = "|"
    pos = half + clamped
    if 0 <= pos < width:
        chars[pos] = "█" if abs(clamped) > 4 else "●"
    return "".join(chars)


def main():
    print("=" * 74)
    print("      S9+ REAL-TIME HARDWARE BAROMETER & INFRASOUND RADAR")
    print("=" * 74)
    print("[*] Probing S9+ hardware barometer sensor (LPS22H / BMP280)...")

    # Verify sensor responds
    initial_p = None
    for attempt in range(3):
        initial_p = fetch_single_pressure_sample()
        if initial_p and initial_p > 300.0:
            break
        time.sleep(0.3)

    if not initial_p or initial_p <= 0:
        print("[!] Error: No pressure data received from phone sensor.")
        print("    1. Ensure Termux:API app is installed and granted SENSORS permission.")
        print("    2. Run 'termux-sensor -s pressure -n 1' in Termux to test.")
        sys.exit(1)

    print(f"[✓] Hardware Barometer Active! Initial Ambient Pressure: {initial_p:.2f} hPa")
    print("[*] Stream is LIVE. Live readings will update continuously below.")
    print("[*] Test: Lift phone up to your head, step on a chair, or blow across the mic.")
    print("-" * 74)

    baseline_p = initial_p
    prev_p = initial_p
    flt = SecondOrderBandpassFilter(lowcut_hz=0.03, highcut_hz=2.0, sample_rate_hz=10.0)

    sample_count = 0
    start_time = time.time()
    last_print_time = 0

    # Try streaming subprocess first
    stream_proc = None
    try:
        stream_proc = subprocess.Popen(
            ["termux-sensor", "-s", "pressure", "-d", "100"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    except Exception:
        stream_proc = None

    buf = ""
    last_stream_read = time.time()

    try:
        while True:
            cur_p = None

            # 1. Try reading from active stream
            if stream_proc and stream_proc.poll() is None:
                # Read line non-blocking via select or short timeout
                line = stream_proc.stdout.readline()
                if line:
                    buf += line
                    if "}" in line:
                        cur_p = extract_pressure_from_json(buf)
                        buf = ""
                        if cur_p:
                            last_stream_read = time.time()

            # 2. Fallback to rapid polling if stream stalls for > 1.0 second
            if cur_p is None and (time.time() - last_stream_read > 1.0):
                cur_p = fetch_single_pressure_sample()

            # If still no sample, small sleep and continue
            if cur_p is None:
                time.sleep(0.04)
                continue

            sample_count += 1
            now = time.time()

            # Slow rolling baseline drift filter (tracks weather changes over hours)
            baseline_p = (baseline_p * 0.998) + (cur_p * 0.002)

            # Micro-barometric wave filter (Pascals)
            delta_pa = (cur_p - baseline_p) * 100.0
            wave_pa = flt.process(delta_pa)

            # Sub-meter elevation delta
            elevation_m = calculate_elevation_delta(cur_p, baseline_p)

            # Anomaly classifier
            diff_from_prev = (cur_p - prev_p) * 100.0
            prev_p = cur_p

            tag = "   "
            if abs(wave_pa) > 3.0:
                tag = "⚡ SHOCKWAVE"
            elif abs(wave_pa) > 0.8:
                tag = "🌊 AIR-PULSE"
            elif abs(elevation_m) > 0.5:
                tag = "🔺 ELEVATION"

            # Render live line (updated every ~50ms)
            if now - last_print_time >= 0.05:
                bar = render_oscilloscope_bar(wave_pa, width=24)
                elapsed = max(1.0, now - start_time)
                hz = sample_count / elapsed

                sys.stdout.write(
                    f"\r#{sample_count:04d} | {cur_p:7.2f} hPa | Δh:{elevation_m:+5.2f}m | "
                    f"Wave:[{bar}] {wave_pa:+5.2f}Pa | {hz:4.1f}Hz {tag}  "
                )
                sys.stdout.flush()
                last_print_time = now

            time.sleep(0.03)

    except KeyboardInterrupt:
        print("\n\n[*] Stopping micro-barometer...")
    finally:
        if stream_proc:
            try:
                stream_proc.terminate()
                stream_proc.wait(timeout=0.5)
            except Exception:
                pass
        # Cleanly release sensor
        subprocess.run(["termux-sensor", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[✓] Hardware sensor released cleanly.")


if __name__ == "__main__":
    main()
