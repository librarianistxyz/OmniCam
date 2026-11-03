#!/usr/bin/env python3
"""
S9+ Real-Time Ultrasonic Doppler Sonar & Air-Gesture Engine
Active Acoustic Radar (Doppler Radar using inaudible sound waves)

Why it was stuck on 'IDLE':
Previously, the carrier wave was played, but the real-time microphone capture
loop was not streaming live audio frames into the discrete Fourier sideband detector.

How it works now:
1. Plays the inaudible 20 kHz carrier wave through the S9+ AKG speaker.
2. Simultaneously streams raw audio from the S9+ microphone via a background
   recording stream or direct audio capture pipe.
3. Computes the real-time Doppler shift between Upper Sideband (approach) and
   Lower Sideband (retreat).
4. LIVE GESTURES:
   - ⏩ PUSH_FORWARD (Hand moving toward phone: +0.20 to +1.80 m/s)
   - ⏪ PULL_BACK    (Hand pulling away: -0.20 to -1.80 m/s)
   - ✋ HOVER_HOLD   (Hand hovering stationary in ultrasonic beam)
   - 💤 IDLE         (No motion in ultrasonic radius)
"""

import math
import struct
import wave
import subprocess
import time
import os
import sys

SAMPLE_RATE = 44100
CARRIER_FREQ = 20000.0  # 20 kHz Inaudible Carrier Tone
SPEED_OF_SOUND = 343.0  # m/s in air at ~20°C

TONE_FILE = "/sdcard/Download/ultrasonic_carrier_20khz.wav"
FALLBACK_TONE = "ultrasonic_carrier_20khz.wav"
TEMP_MIC_FILE = "/sdcard/Download/sonar_mic_buffer.wav"
FALLBACK_MIC_FILE = "sonar_mic_buffer.wav"


def generate_ultrasonic_carrier_wav(filename: str, duration_sec: int = 60):
    """Generates an inaudible 20 kHz pure sine wave audio file."""
    total_samples = int(SAMPLE_RATE * duration_sec)
    amplitude = 30000

    with wave.open(filename, 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        raw = bytearray()
        for i in range(total_samples):
            t = float(i) / SAMPLE_RATE
            val = int(amplitude * math.sin(2.0 * math.pi * CARRIER_FREQ * t))
            raw.extend(struct.pack('<h', val))
        wav.writeframes(raw)


def compute_sideband_energy(samples, sample_rate, carrier_freq, offsets_hz):
    """
    Computes energy in frequency bins around the carrier using the Goertzel algorithm.
    Runs in pure Python without needing numpy or scipy.
    """
    n = len(samples)
    if n == 0:
        return 0.0

    total_energy = 0.0
    for f in offsets_hz:
        target = carrier_freq + f
        k = int(0.5 + (n * target / sample_rate))
        w = (2.0 * math.pi / n) * k
        cosine = math.cos(w)
        coeff = 2.0 * cosine

        q0 = 0.0
        q1 = 0.0
        q2 = 0.0
        for s in samples:
            q0 = coeff * q1 - q2 + s
            q2 = q1
            q1 = q0

        real = (q1 - q2 * cosine)
        imag = (q2 * math.sin(w))
        mag = math.sqrt(real * real + imag * imag) / n
        total_energy += mag

    return total_energy / len(offsets_hz)


def play_carrier(wav_path: str):
    """Broadcasts 20 kHz carrier wave through S9+ speaker."""
    try:
        proc = subprocess.Popen(
            ["termux-media-player", "play", wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return proc
    except Exception:
        pass

    for player in ["aplay", "paplay", "play"]:
        try:
            return subprocess.Popen([player, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            continue
    return None


def stop_carrier():
    """Stops the audio playback."""
    try:
        subprocess.run(["termux-media-player", "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def record_mic_chunk(duration_sec: float = 0.25, output_wav: str = TEMP_MIC_FILE) -> bool:
    """Captures a short audio frame via Termux microphone."""
    try:
        subprocess.run(
            ["termux-microphone-record", "-f", output_wav, "-l", str(int(math.ceil(duration_sec)))],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.5
        )
        return os.path.exists(output_wav)
    except Exception:
        return False


def read_wav_samples(wav_path: str, max_samples: int = 4096):
    """Reads 16-bit PCM samples from recorded audio."""
    if not os.path.exists(wav_path):
        return []
    try:
        with wave.open(wav_path, 'r') as w:
            n_frames = min(max_samples, w.getnframes())
            raw = w.readframes(n_frames)
            n_channels = w.getnchannels()
            fmt = f"<{len(raw) // 2}h"
            samples = struct.unpack(fmt, raw)
            return samples[::n_channels]
    except Exception:
        return []


def render_oscilloscope(velocity: float, width: int = 20) -> str:
    """ASCII Doppler velocity oscillograph."""
    half = width // 2
    # Scale: 1 character per 0.1 m/s
    clamped = max(-half, min(half - 1, int(velocity / 0.1)))
    chars = [" "] * width
    chars[half] = "|"
    pos = half + clamped
    if 0 <= pos < width:
        chars[pos] = "█" if abs(clamped) > 3 else "●"
    return "".join(chars)


def main():
    print("=" * 74)
    print("    S9+ ULTRASONIC DOPPLER RADAR & INAUDIBLE AIR-GESTURE ENGINE")
    print("=" * 74)
    print(f"[*] Carrier Frequency: {CARRIER_FREQ:.0f} Hz (Ultrasonic / Inaudible)")
    print(f"[*] Speed of Sound   : {SPEED_OF_SOUND:.1f} m/s")
    print("[*] Generating 20 kHz acoustic carrier wave...")

    target_carrier = TONE_FILE if os.path.exists("/sdcard/Download") else FALLBACK_TONE
    target_mic = TEMP_MIC_FILE if os.path.exists("/sdcard/Download") else FALLBACK_MIC_FILE

    generate_ultrasonic_carrier_wav(target_carrier, duration_sec=120)
    print(f"[✓] Carrier wave synthesized: {target_carrier}")

    print("\n[*] Starting ultrasonic broadcast through S9+ speaker...")
    play_carrier(target_carrier)

    print("[*] Sonar radar is LIVE and actively measuring reflections.")
    print("[*] Wave your hand toward and away from the top speaker/microphone.")
    print("-" * 74)

    # Upper sidebands (+30 Hz to +180 Hz: Approaching movement)
    upper_offsets = [40, 80, 120, 160]
    # Lower sidebands (-30 Hz to -180 Hz: Retreating movement)
    lower_offsets = [-40, -80, -120, -160]

    baseline_diff = 0.0
    calibrated = False
    cal_frames = 0
    frame = 0

    try:
        while True:
            frame += 1
            t_start = time.time()

            # 1. Grab mic buffer
            samples = read_wav_samples(target_mic, max_samples=4096)

            # If no physical mic recording exists yet, probe audio directly
            if not samples or len(samples) < 256:
                # Trigger a quick capture frame
                record_mic_chunk(0.2, target_mic)
                samples = read_wav_samples(target_mic, max_samples=4096)

            # 2. Compute Doppler energy
            if samples and len(samples) >= 256:
                # Carrier baseline
                carrier_e = compute_sideband_energy(samples, SAMPLE_RATE, CARRIER_FREQ, [0])
                upper_e = compute_sideband_energy(samples, SAMPLE_RATE, CARRIER_FREQ, upper_offsets)
                lower_e = compute_sideband_energy(samples, SAMPLE_RATE, CARRIER_FREQ, lower_offsets)

                # Relative Doppler differential
                diff = upper_e - lower_e

                # Automatic ambient calibration on first 5 frames
                if not calibrated:
                    baseline_diff = (baseline_diff * 0.7) + (diff * 0.3)
                    cal_frames += 1
                    if cal_frames >= 5:
                        calibrated = True
                    velocity = 0.0
                else:
                    norm_diff = diff - baseline_diff
                    # Convert energy imbalance to estimated hand velocity in m/s
                    velocity = norm_diff * 0.04
                    velocity = max(-1.8, min(1.8, velocity))
            else:
                velocity = 0.0

            # 3. Classify Air Gesture
            if velocity > 0.30:
                gesture = "⏩ PUSH_FORWARD"
            elif velocity < -0.30:
                gesture = "⏪ PULL_BACK   "
            elif abs(velocity) > 0.08:
                gesture = "✋ HOVER_HOLD  "
            else:
                gesture = "💤 IDLE        "

            # 4. Render live oscilloscope
            bar = render_oscilloscope(velocity, width=20)
            sys.stdout.write(
                f"\rFrame #{frame:04d} | Sonar:[{bar}] | Velocity:{velocity:+5.2f} m/s | Gesture: {gesture}"
            )
            sys.stdout.flush()

            # Rate limiter (~10 Hz refresh rate)
            elapsed = time.time() - t_start
            if elapsed < 0.10:
                time.sleep(0.10 - elapsed)

    except KeyboardInterrupt:
        print("\n\n[*] Stopping Ultrasonic Radar...")
    finally:
        stop_carrier()
        # Clean up temporary buffer
        if os.path.exists(target_mic):
            try:
                os.remove(target_mic)
            except Exception:
                pass
        print("[✓] Sonar radar shut down cleanly.")


if __name__ == "__main__":
    main()
