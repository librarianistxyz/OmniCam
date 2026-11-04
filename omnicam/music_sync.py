# Copyright (C) 2026 librarianistxyz <https://github.com/librarianistxyz/OmniCam>
#
# This file is part of OmniCam: AI Virtual Multi-Camera Director.
#
# OmniCam is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OmniCam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Multi-Take Waveform Auto-Sync Engine for OmniCam.
Synchronizes multiple video camera takes to a Studio Master audio file (song.wav / master.mp3)
to sub-millisecond precision using FFT Cross-Correlation (pure NumPy, zero heavyweight deps).
"""

from dataclasses import dataclass
import os
import subprocess
from typing import Dict, List, Optional, Tuple
import numpy as np


@dataclass
class TakeSyncInfo:
    take_index: int
    take_path: str
    offset_seconds: float  # Delta t: t_master = t_take + offset_seconds
    confidence: float  # 0.0 to 1.0 (peak-to-noise ratio in correlation)
    is_locked: bool
    take_duration: float
    master_duration: float
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            "take_index": self.take_index,
            "take_path": self.take_path,
            "take_filename": os.path.basename(self.take_path),
            "offset_seconds": round(self.offset_seconds, 4),
            "confidence": round(self.confidence, 3),
            "is_locked": self.is_locked,
            "take_duration": round(self.take_duration, 2),
            "master_duration": round(self.master_duration, 2),
            "description": self.description,
        }


class MultiTakeSyncEngine:
    """
    Sub-millisecond multi-camera acoustic sync engine.
    Extracts scratch audio from camera takes and computes fast FFT cross-correlation
    against clean studio audio.
    """

    def __init__(self, sample_rate: int = 8000, min_confidence: float = 0.35):
        self.sample_rate = sample_rate
        self.min_confidence = min_confidence

    def extract_pcm(
        self,
        media_path: str,
        max_duration: Optional[float] = None,
    ) -> Tuple[np.ndarray, float]:
        """
        Extracts 16-bit mono PCM audio from any video or audio file using FFmpeg pipe.
        Returns (audio_samples_float32, duration_seconds).
        """
        if not os.path.isfile(media_path):
            raise FileNotFoundError(f"Media file not found: {media_path}")

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
        ]
        if max_duration and max_duration > 0:
            cmd.extend(["-t", str(max_duration)])

        cmd.extend([
            "-i", media_path,
            "-vn",
            "-ac", "1",
            "-ar", str(self.sample_rate),
            "-f", "s16le",
            "-"
        ])

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            raw_bytes = proc.stdout
            if not raw_bytes:
                return np.zeros(0, dtype=np.float32), 0.0

            pcm_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
            pcm_float = pcm_int16.astype(np.float32) / 32768.0
            dur = len(pcm_float) / float(self.sample_rate)
            return pcm_float, dur
        except subprocess.CalledProcessError as exc:
            err = exc.stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(f"Failed to extract PCM audio from {media_path}: {err}") from exc

    def align_take_to_master(
        self,
        master_audio_path: str,
        take_video_path: str,
        take_index: int = 0,
        max_search_duration: Optional[float] = 300.0,
    ) -> TakeSyncInfo:
        """
        Aligns a single camera take to the master song.
        Detects exact offset (Delta t in seconds).
        t_master = t_take + offset_seconds
        t_take = t_master - offset_seconds
        """
        master_pcm, master_dur = self.extract_pcm(master_audio_path, max_duration=max_search_duration)
        take_pcm, take_dur = self.extract_pcm(take_video_path, max_duration=max_search_duration)

        if len(master_pcm) == 0 or len(take_pcm) == 0:
            return TakeSyncInfo(
                take_index=take_index,
                take_path=take_video_path,
                offset_seconds=0.0,
                confidence=0.0,
                is_locked=False,
                take_duration=take_dur,
                master_duration=master_dur,
                description="Failed to extract audio for synchronization",
            )

        # Standardize signals (remove DC bias, normalize energy)
        master_norm = master_pcm - np.mean(master_pcm)
        take_norm = take_pcm - np.mean(take_pcm)

        m_std = np.std(master_norm)
        t_std = np.std(take_norm)
        if m_std > 1e-6:
            master_norm /= m_std
        if t_std > 1e-6:
            take_norm /= t_std

        # Fast FFT Cross-Correlation
        nx = len(take_norm)
        ny = len(master_norm)
        n_corr = nx + ny - 1
        n_fft = 1 << (n_corr - 1).bit_length()

        x_fft = np.fft.rfft(take_norm, n_fft)
        y_fft = np.fft.rfft(master_norm, n_fft)
        corr = np.fft.irfft(x_fft.conj() * y_fft, n_fft)

        # Peak detection with circular lag unwrapping
        peak_idx = int(np.argmax(corr))
        peak_val = float(corr[peak_idx])

        if peak_idx > n_fft // 2:
            lag_samples = peak_idx - n_fft
        else:
            lag_samples = peak_idx

        offset_seconds = float(lag_samples) / float(self.sample_rate)

        # Confidence calculation: Peak-to-Noise Ratio (PNR)
        corr_abs = np.abs(corr[:nx + ny])
        median_noise = float(np.median(corr_abs))
        std_noise = float(np.std(corr_abs))

        if std_noise > 1e-6:
            pnr = (peak_val - median_noise) / std_noise
            # PNR > 10 is very clean; scale to [0, 1]
            confidence = float(np.clip(pnr / 14.0, 0.0, 1.0))
        else:
            confidence = 0.0

        is_locked = confidence >= self.min_confidence

        desc = (
            f"Offset {offset_seconds:+.3f}s (Conf: {confidence*100:.1f}%)"
            if is_locked
            else f"Low correlation ({confidence*100:.1f}%). Scratch audio might be quiet or silent."
        )

        return TakeSyncInfo(
            take_index=take_index,
            take_path=take_video_path,
            offset_seconds=offset_seconds,
            confidence=confidence,
            is_locked=is_locked,
            take_duration=take_dur,
            master_duration=master_dur,
            description=desc,
        )

    def align_multiple_takes(
        self,
        master_audio_path: str,
        take_paths: List[str],
    ) -> List[TakeSyncInfo]:
        """
        Synchronizes an entire multi-camera shoot (Takes 1..N) to the studio master audio.
        """
        results: List[TakeSyncInfo] = []
        for idx, path in enumerate(take_paths):
            info = self.align_take_to_master(master_audio_path, path, take_index=idx)
            results.append(info)
        return results
