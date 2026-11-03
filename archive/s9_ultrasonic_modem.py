#!/usr/bin/env python3
"""
S9+ Ultrasonic Air-Gap Acoustic Modem & Data Transmitter
Offline Inaudible Data Transfer via Frequency-Shift Keying (FSK)

Acoustic Physics & Protocol Design:
- Zero Radio: Works with Wi-Fi, Bluetooth, NFC, and Cellular COMPLETELY DISABLED.
- Ultrasonic Audio Band: 18,500 Hz to 20,500 Hz (Inaudible to human ear).
- Modulation: Dual-Tone FSK (Frequency-Shift Keying)
    * Preamble Sync Pulse: 18,500 Hz (marks start of transmission packet)
    * Bit '0': 19,200 Hz
    * Bit '1': 20,000 Hz
    * Postamble End Pulse: 20,500 Hz
- Packet Structure:
    [SYNC TONE (100ms)] -> [LENGTH BYTE] -> [PAYLOAD BYTES (ASCII)] -> [CHECKSUM] -> [END TONE]
- Bit Duration: 40ms per bit (~25 baud / ~3 characters per second for high-resilience through air).
- Pure Python: Zero external libraries needed (no numpy/scipy required, uses standard math & wave).
"""

import math
import struct
import wave
import subprocess
import time
import os
import sys

SAMPLE_RATE = 44100

# Ultrasonic Frequency Allocation (Hz)
FREQ_SYNC = 18500.0   # Packet Start Preamble
FREQ_BIT_0 = 19200.0  # Binary '0'
FREQ_BIT_1 = 20000.0  # Binary '1'
FREQ_END = 20500.0    # Packet End Postamble

BIT_DURATION_SEC = 0.040  # 40ms per bit (Reliable acoustic pulse length)
SYNC_DURATION_SEC = 0.120 # 120ms sync pulse

DEFAULT_TRANSMIT_WAV = "/sdcard/Download/ultrasonic_transmission.wav"
LOCAL_TRANSMIT_WAV = "ultrasonic_transmission.wav"


def generate_tone_pcm(freq_hz: float, duration_sec: float, amplitude: int = 28000) -> bytearray:
    """Generates pure sine wave PCM samples for a given frequency and duration."""
    total_samples = int(SAMPLE_RATE * duration_sec)
    raw = bytearray()
    
    # Smooth cosine window envelope on edges to prevent speaker click transients
    fade_samples = min(total_samples // 8, int(SAMPLE_RATE * 0.005))
    
    for i in range(total_samples):
        # Window envelope
        env = 1.0
        if i < fade_samples:
            env = 0.5 * (1.0 - math.cos(math.pi * i / fade_samples))
        elif i > total_samples - fade_samples:
            env = 0.5 * (1.0 - math.cos(math.pi * (total_samples - i) / fade_samples))
            
        t = float(i) / SAMPLE_RATE
        val = int(amplitude * env * math.sin(2.0 * math.pi * freq_hz * t))
        raw.extend(struct.pack('<h', val))
        
    return raw


def encode_string_to_ultrasonic_wav(message: str, output_wav: str) -> int:
    """
    Encodes an ASCII string / password / token into an inaudible ultrasonic WAV file.
    Returns total byte length of encoded audio.
    """
    raw_bytes = message.encode('utf-8')
    payload_len = len(raw_bytes)
    if payload_len > 120:
        raise ValueError("Payload too long (limit 120 characters for fast acoustic burst).")

    # Simple XOR checksum for data integrity
    checksum = 0
    for b in raw_bytes:
        checksum ^= b

    packet_bytes = bytearray([payload_len]) + raw_bytes + bytearray([checksum])
    
    # Assemble complete acoustic waveform
    audio_pcm = bytearray()

    # 1. Preamble Sync Pulse
    audio_pcm.extend(generate_tone_pcm(FREQ_SYNC, SYNC_DURATION_SEC))
    # Inter-frame silence gap (15ms)
    audio_pcm.extend(bytearray(int(SAMPLE_RATE * 0.015) * 2))

    # 2. Modulate each bit via FSK
    bit_count = 0
    for byte in packet_bytes:
        for bit_idx in range(7, -1, -1):
            bit = (byte >> bit_idx) & 1
            freq = FREQ_BIT_1 if bit == 1 else FREQ_BIT_0
            audio_pcm.extend(generate_tone_pcm(freq, BIT_DURATION_SEC))
            bit_count += 1

    # 3. Postamble End Tone
    audio_pcm.extend(generate_tone_pcm(FREQ_END, 0.080))

    # Save to standard 16-bit Mono WAV file
    with wave.open(output_wav, 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio_pcm)

    return len(audio_pcm)


def play_audio_file(wav_path: str):
    """Transmits the ultrasonic wave through S9+ hardware speakers."""
    # Try Termux media player first
    try:
        proc = subprocess.run(
            ["termux-media-player", "play", wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if proc.returncode == 0:
            return True
    except Exception:
        pass

    # Fallback to standard Linux players (aplay, paplay)
    for cmd in ["aplay", "paplay", "play"]:
        try:
            res = subprocess.run([cmd, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return True
        except Exception:
            continue
            
    return False


def compute_goertzel_magnitude(samples, target_freq: float, sample_rate: int = SAMPLE_RATE) -> float:
    """
    Calculates signal energy at target frequency in O(N) time with zero external libraries.
    Goertzel algorithm is optimized for single-tone frequency detection.
    """
    n = len(samples)
    if n == 0:
        return 0.0
    
    k = int(0.5 + (n * target_freq / sample_rate))
    w = (2.0 * math.pi / n) * k
    cosine = math.cos(w)
    sine = math.sin(w)
    coeff = 2.0 * cosine

    q0 = 0.0
    q1 = 0.0
    q2 = 0.0

    for s in samples:
        q0 = coeff * q1 - q2 + s
        q2 = q1
        q1 = q0

    real = (q1 - q2 * cosine)
    imag = (q2 * sine)
    magnitude = math.sqrt(real * real + imag * imag) / n
    return magnitude


def decode_ultrasonic_wav_file(wav_path: str) -> str:
    """
    Demodulates an ultrasonic FSK audio recording back into the original ASCII text.
    """
    if not os.path.exists(wav_path):
        return "[!] Error: Recording file not found."

    with wave.open(wav_path, 'r') as wav:
        n_channels = wav.getnchannels()
        sampwidth = wav.getsampwidth()
        framerate = wav.getframerate()
        n_frames = wav.getnframes()
        raw_bytes = wav.readframes(n_frames)

    # Convert 16-bit PCM bytes to integers
    fmt = f"<{n_frames * n_channels}h"
    all_samples = struct.unpack(fmt, raw_bytes)
    # Take first channel if stereo
    samples = all_samples[::n_channels]

    # Find the Sync Pulse (18.5 kHz)
    window_size = int(framerate * 0.030)  # 30ms scanning window
    sync_idx = -1
    max_sync = 0.0

    step = window_size // 2
    for i in range(0, len(samples) - window_size, step):
        chunk = samples[i:i + window_size]
        mag_sync = compute_goertzel_magnitude(chunk, FREQ_SYNC, framerate)
        if mag_sync > 120.0 and mag_sync > max_sync:
            max_sync = mag_sync
            sync_idx = i

    if sync_idx == -1:
        return "[!] Error: No ultrasonic synchronization preamble detected in audio."

    # Skip past sync pulse + silence gap
    start_offset = sync_idx + int(framerate * (SYNC_DURATION_SEC + 0.015))
    bit_samples = int(framerate * BIT_DURATION_SEC)

    # Demodulate bitstream
    bits = []
    idx = start_offset

    while idx + bit_samples <= len(samples):
        chunk = samples[idx:idx + bit_samples]
        mag_0 = compute_goertzel_magnitude(chunk, FREQ_BIT_0, framerate)
        mag_1 = compute_goertzel_magnitude(chunk, FREQ_BIT_1, framerate)
        mag_end = compute_goertzel_magnitude(chunk, FREQ_END, framerate)

        # End postamble check
        if mag_end > 140.0 and mag_end > mag_0 and mag_end > mag_1:
            break

        # Decode bit
        if mag_1 > mag_0:
            bits.append(1)
        else:
            bits.append(0)

        idx += bit_samples

    # Group bits into bytes
    byte_vals = []
    for i in range(0, len(bits) - 7, 8):
        byte_bits = bits[i:i + 8]
        val = 0
        for b in byte_bits:
            val = (val << 1) | b
        byte_vals.append(val)

    if not byte_vals:
        return "[!] Error: Failed to extract payload bits."

    payload_len = byte_vals[0]
    payload_bytes = byte_vals[1:1 + payload_len]

    try:
        decoded_text = bytes(payload_bytes).decode('utf-8', errors='ignore')
        return decoded_text
    except Exception as e:
        return f"[!] Decode error: {e}"


def main():
    print("""
======================================================================
    S9+ ULTRASONIC AIR-GAP ACOUSTIC MODEM (ZERO-RADIO COMM)
======================================================================
 Carrier Frequencies:
 • SYNC PREAMBLE : 18,500 Hz (Inaudible)
 • BIT '0'       : 19,200 Hz (Inaudible)
 • BIT '1'       : 20,000 Hz (Inaudible)
 • END POSTAMBLE : 20,500 Hz (Inaudible)

 Mode of Operation: Completely Air-Gapped (No Wi-Fi, No Bluetooth)
======================================================================
1. Transmit Data (Broadcast inaudible ultrasonic chirp through speaker)
2. Receive / Decode Data (Demodulate recorded audio file to ASCII)
3. Exit
======================================================================
""")

    choice = input("Select Option [1-3]: ").strip()

    target_wav = DEFAULT_TRANSMIT_WAV if os.path.exists("/sdcard/Download") else LOCAL_TRANSMIT_WAV

    if choice == "1":
        msg = input("\nEnter text/password/token to transmit: ").strip()
        if not msg:
            print("[!] Empty message.")
            return

        print(f"[*] Encoding '{msg}' into ultrasonic FSK packet...")
        encode_string_to_ultrasonic_wav(msg, target_wav)
        print(f"[✓] Generated inaudible ultrasonic wave: {target_wav}")

        print("\n[*] TRANSMITTING VIA ULTRASONIC SOUND WAVES...")
        print("[*] (The room should remain completely silent to human ears)")
        ok = play_audio_file(target_wav)
        if ok:
            print("[✓] Transmission complete! Sound wave propagated through air.")
        else:
            print(f"[!] WAV generated at {target_wav}. Play it using your media player.")

    elif choice == "2":
        path = input(f"Enter path to recorded WAV file [default: {target_wav}]: ").strip()
        if not path:
            path = target_wav

        print(f"[*] Demodulating ultrasonic frequencies from {path}...")
        text = decode_ultrasonic_wav_file(path)
        print("\n" + "=" * 50)
        print(f" [DECODED PAYLOAD]: {text}")
        print("=" * 50)

    elif choice == "3":
        sys.exit(0)


if __name__ == "__main__":
    main()

