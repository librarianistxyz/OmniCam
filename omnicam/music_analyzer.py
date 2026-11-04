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
Music Rhythm & Energy Grid Analyzer for OmniCam.
Detects BPM tempo, musical downbeats (bars), kick drum / 808 sub-bass drops,
snare hits, and song structural sections (Intro, Verse, Pre-Chorus, Drop/Chorus).
"""

from dataclasses import dataclass, field
import os
import subprocess
from typing import Dict, List, Optional, Tuple
import numpy as np


@dataclass
class SongSection:
    name: str  # "intro", "verse", "pre_chorus", "chorus", "drop", "outro"
    start: float
    end: float
    energy_level: float  # 0.0 to 1.0
    cadence_bars: int  # 8, 4, 2, or 1 bar per camera cut

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "energy_level": round(self.energy_level, 2),
            "cadence_bars": self.cadence_bars,
        }


@dataclass
class MusicAnalysisResult:
    bpm: float
    beat_duration: float
    downbeats: List[float]  # Measure/Bar start timestamps
    beats: List[float]  # Every beat timestamp
    half_beats: List[float]  # 1/2 beat subdivisions
    kick_onsets: List[float]  # Heavy kick / 808 transient timestamps
    snare_onsets: List[float]  # Snare / clap transient timestamps
    sections: List[SongSection]
    total_duration: float

    def to_dict(self) -> Dict:
        return {
            "bpm": round(self.bpm, 1),
            "beat_duration": round(self.beat_duration, 4),
            "bar_duration": round(self.beat_duration * 4.0, 4),
            "total_bars": len(self.downbeats),
            "total_beats": len(self.beats),
            "downbeats": [round(t, 3) for t in self.downbeats[:100]],  # cap for json brevity
            "beats": [round(t, 3) for t in self.beats[:200]],
            "kick_onsets": [round(t, 3) for t in self.kick_onsets[:100]],
            "snare_onsets": [round(t, 3) for t in self.snare_onsets[:100]],
            "sections": [s.to_dict() for s in self.sections],
            "total_duration": round(self.total_duration, 3),
        }


class MusicBeatAnalyzer:
    """
    Analyzes music rhythm, tempo, transients, and song sections using pure NumPy STFT.
    """

    def __init__(self, sample_rate: int = 22050, hop_size: int = 512, win_size: int = 1024):
        self.sample_rate = sample_rate
        self.hop_size = hop_size
        self.win_size = win_size

    def _extract_audio(self, audio_path: str, max_duration: Optional[float] = None) -> np.ndarray:
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
        ]
        if max_duration and max_duration > 0:
            cmd.extend(["-t", str(max_duration)])

        cmd.extend([
            "-i", audio_path,
            "-vn",
            "-ac", "1",
            "-ar", str(self.sample_rate),
            "-f", "s16le",
            "-"
        ])

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        raw_bytes = proc.stdout
        if not raw_bytes:
            return np.zeros(0, dtype=np.float32)

        pcm = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return pcm

    def analyze(
        self,
        audio_path: str,
        manual_bpm: Optional[float] = None,
        max_duration: Optional[float] = None,
    ) -> MusicAnalysisResult:
        """
        Extracts BPM, downbeat grid, kick/snare transients, and song structure.
        """
        audio = self._extract_audio(audio_path, max_duration=max_duration)
        total_duration = len(audio) / float(self.sample_rate)

        if len(audio) < self.win_size * 4:
            # Fallback for ultra-short clips
            fallback_bpm = manual_bpm or 120.0
            beat_dur = 60.0 / fallback_bpm
            beats = list(np.arange(0, total_duration, beat_dur))
            downbeats = beats[::4]
            sec = SongSection(name="verse", start=0.0, end=total_duration, energy_level=0.5, cadence_bars=4)
            return MusicAnalysisResult(
                bpm=fallback_bpm,
                beat_duration=beat_dur,
                downbeats=downbeats,
                beats=beats,
                half_beats=[],
                kick_onsets=[],
                snare_onsets=[],
                sections=[sec],
                total_duration=total_duration,
            )

        # 1. Compute STFT spectrogram
        num_frames = (len(audio) - self.win_size) // self.hop_size
        window = np.hanning(self.win_size)
        stft_mags = np.empty((num_frames, self.win_size // 2 + 1), dtype=np.float32)

        for i in range(num_frames):
            idx = i * self.hop_size
            frame = audio[idx : idx + self.win_size] * window
            stft_mags[i] = np.abs(np.fft.rfft(frame))

        freq_bin_hz = self.sample_rate / float(self.win_size)
        fps = float(self.sample_rate) / float(self.hop_size)

        # 2. Sub-band Frequency Isolation
        # Kick / 808 sub-bass: 20 Hz to 140 Hz
        kick_bin_start = max(1, int(20.0 / freq_bin_hz))
        kick_bin_end = max(kick_bin_start + 1, int(140.0 / freq_bin_hz))
        kick_band_mag = np.sum(stft_mags[:, kick_bin_start:kick_bin_end], axis=1)

        # Snare / Clap / Cymbal: 1500 Hz to 4500 Hz
        snare_bin_start = int(1500.0 / freq_bin_hz)
        snare_bin_end = min(stft_mags.shape[1], int(4500.0 / freq_bin_hz))
        snare_band_mag = np.sum(stft_mags[:, snare_bin_start:snare_bin_end], axis=1)

        # Full-band Onset Detection Function (ODF) via Spectral Flux
        spectral_flux = np.maximum(0.0, np.diff(stft_mags, axis=0))
        odf = np.sum(spectral_flux, axis=1)
        # Pad 1 frame to align length with num_frames
        odf = np.pad(odf, (0, 1), mode="edge")

        # 3. BPM Tempo Detection
        if manual_bpm and 50.0 <= manual_bpm <= 220.0:
            detected_bpm = float(manual_bpm)
        else:
            odf_centered = odf - np.mean(odf)
            ac = np.correlate(odf_centered, odf_centered, mode="full")[len(odf_centered) - 1 :]

            min_lag = max(1, int(60.0 / 200.0 * fps))
            max_lag = min(len(ac) - 2, int(60.0 / 65.0 * fps))

            if max_lag > min_lag:
                best_lag_rel = int(np.argmax(ac[min_lag:max_lag]))
                best_lag = min_lag + best_lag_rel

                # Parabolic peak refinement
                y0 = float(ac[best_lag - 1])
                y1 = float(ac[best_lag])
                y2 = float(ac[best_lag + 1])
                denom = y0 - 2.0 * y1 + y2
                delta = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-7 else 0.0
                refined_lag = best_lag + delta
                detected_bpm = float(60.0 * fps / refined_lag)
                # Standardize into typical 70-170 music range
                if detected_bpm < 70.0:
                    detected_bpm *= 2.0
                elif detected_bpm > 175.0:
                    detected_bpm /= 2.0
            else:
                detected_bpm = 120.0

        beat_dur = 60.0 / detected_bpm

        # 4. Beat Grid Phase Alignment (find initial downbeat t0)
        # Scan candidate phase offsets from 0 to beat_dur
        num_phase_steps = 32
        phase_scores = []
        for step in range(num_phase_steps):
            t_cand = (step / float(num_phase_steps)) * beat_dur
            frame_indices = np.arange(t_cand * fps, len(odf), beat_dur * fps).astype(int)
            valid_indices = frame_indices[frame_indices < len(odf)]
            score = np.sum(odf[valid_indices])
            phase_scores.append(score)

        best_phase_idx = int(np.argmax(phase_scores))
        t0 = (best_phase_idx / float(num_phase_steps)) * beat_dur

        # Generate regular beat grid
        beats = list(np.arange(t0, total_duration, beat_dur))
        half_beats = list(np.arange(t0, total_duration, beat_dur / 2.0))

        # 5. Bar Downbeats (4/4 musical measure)
        # Determine which of the 4 beats has strongest kick presence
        bar_scores = [0.0, 0.0, 0.0, 0.0]
        for b_idx, b_time in enumerate(beats):
            mod_b = b_idx % 4
            f_idx = min(int(b_time * fps), len(kick_band_mag) - 1)
            bar_scores[mod_b] += float(kick_band_mag[f_idx])

        best_bar_offset = int(np.argmax(bar_scores))
        downbeats = [beats[i] for i in range(best_bar_offset, len(beats), 4)]

        # 6. Kick & Snare Transients Detection
        kick_diff = np.maximum(0.0, np.diff(kick_band_mag))
        kick_thresh = np.mean(kick_diff) + 1.25 * np.std(kick_diff)
        kick_frame_indices = np.where(kick_diff > kick_thresh)[0]
        # Cluster onsets within 0.15s
        kick_onsets = []
        last_t = -1.0
        for fi in kick_frame_indices:
            t = fi / fps
            if t - last_t >= 0.15:
                kick_onsets.append(t)
                last_t = t

        snare_diff = np.maximum(0.0, np.diff(snare_band_mag))
        snare_thresh = np.mean(snare_diff) + 1.40 * np.std(snare_diff)
        snare_frame_indices = np.where(snare_diff > snare_thresh)[0]
        snare_onsets = []
        last_t = -1.0
        for fi in snare_frame_indices:
            t = fi / fps
            if t - last_t >= 0.15:
                snare_onsets.append(t)
                last_t = t

        # 7. Song Structure Segmentation
        # Calculate moving RMS energy across 4-bar chunks
        bar_dur = beat_dur * 4.0
        sections: List[SongSection] = []
        if not downbeats:
            downbeats = [0.0]

        # Break the timeline into 8-bar or 4-bar blocks
        block_bars = 4 if len(downbeats) < 32 else 8
        bar_chunk_starts = downbeats[::block_bars]

        block_energies = []
        for i, st in enumerate(bar_chunk_starts):
            ed = bar_chunk_starts[i + 1] if i + 1 < len(bar_chunk_starts) else total_duration
            f_st = max(0, int(st * fps))
            f_ed = min(len(odf), int(ed * fps))
            if f_ed > f_st:
                e = float(np.mean(odf[f_st:f_ed]))
            else:
                e = 0.0
            block_energies.append(e)

        max_e = max(block_energies) if block_energies else 1.0
        norm_energies = [(e / max_e if max_e > 0 else 0.5) for e in block_energies]

        for i, st in enumerate(bar_chunk_starts):
            ed = bar_chunk_starts[i + 1] if i + 1 < len(bar_chunk_starts) else total_duration
            energy = norm_energies[i]

            # Structural classification based on energy position and trend
            if i == 0 and energy < 0.45:
                sec_name = "intro"
                cadence = 8
            elif i == len(bar_chunk_starts) - 1 and energy < 0.40:
                sec_name = "outro"
                cadence = 8
            elif energy > 0.72:
                sec_name = "chorus"
                cadence = 1  # Rapid cuts on every bar or downbeat
            elif i > 0 and energy > norm_energies[i - 1] * 1.15 and energy > 0.50:
                sec_name = "pre_chorus"
                cadence = 2  # Build up tension every 2 bars
            else:
                sec_name = "verse"
                cadence = 4  # Standard cinematic verse rhythm

            sections.append(
                SongSection(
                    name=sec_name,
                    start=st,
                    end=ed,
                    energy_level=energy,
                    cadence_bars=cadence,
                )
            )

        return MusicAnalysisResult(
            bpm=detected_bpm,
            beat_duration=beat_dur,
            downbeats=downbeats,
            beats=beats,
            half_beats=half_beats,
            kick_onsets=kick_onsets,
            snare_onsets=snare_onsets,
            sections=sections,
            total_duration=total_duration,
        )
