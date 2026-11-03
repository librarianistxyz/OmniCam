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
Filler Word and Vocal Hesitation Remover for OmniCam
Detects and excises "uh", "um", "ah", "like", "you know" and prolonged acoustic vocal hesitations.
"""

import math
import os
import re
import struct
import subprocess
from typing import List, Optional, Set, Tuple

from .audio_analyzer import SpeechSegment
from .captions import WordTiming


DEFAULT_FILLER_WORDS = {
    "UH",
    "UM",
    "UHM",
    "AH",
    "ER",
    "ERR",
    "HMM",
    "MM",
    "LIKE",
    "YOU KNOW",
}


def normalize_token(text: str) -> str:
    """Strips punctuation and whitespace, converting to uppercase."""
    return re.sub(r"[^\w\s]", "", text).strip().upper()


def detect_lexical_fillers(
    words: List[WordTiming],
    target_fillers: Optional[Set[str]] = None,
    padding: float = 0.04,
) -> List[Tuple[float, float]]:
    """
    Identifies timestamp intervals corresponding to spoken filler words
    transcribed by Whisper (e.g. 'uh', 'um', 'like', 'you know').
    """
    if not words:
        return []

    targets = target_fillers or DEFAULT_FILLER_WORDS
    normalized_targets = {normalize_token(t) for t in targets}

    intervals: List[Tuple[float, float]] = []

    # 1. Check single-word fillers
    for i, w in enumerate(words):
        norm = normalize_token(w.word)
        if norm in normalized_targets:
            s = max(0.0, w.start - padding)
            e = w.end + padding
            intervals.append((s, e))

    # 2. Check multi-word phrase fillers (e.g. 'YOU KNOW')
    for i in range(len(words) - 1):
        phrase = f"{normalize_token(words[i].word)} {normalize_token(words[i+1].word)}"
        if phrase in normalized_targets:
            s = max(0.0, words[i].start - padding)
            e = words[i+1].end + padding
            intervals.append((s, e))

    return intervals


def extract_pcm_samples(media_path: str, sample_rate: int = 16000) -> List[int]:
    """Extracts raw 16-bit mono PCM audio samples via FFmpeg stdout pipe."""
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", media_path,
        "-ar", str(sample_rate),
        "-ac", "1",
        "-f", "s16le",
        "-",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, check=True)
        raw_bytes = res.stdout
        count = len(raw_bytes) // 2
        return list(struct.unpack(f"<{count}h", raw_bytes))
    except Exception as ex:
        # If extraction fails, return empty list
        return []


def detect_acoustic_hesitations(
    media_path: str,
    min_duration: float = 0.25,
    sample_rate: int = 16000,
    frame_ms: int = 40,
    hop_ms: int = 20,
) -> List[Tuple[float, float]]:
    """
    Acoustic spectral & stationarity detector for vocal hesitations.
    Identifies flat, non-consonant neutral vowel drones (120-600Hz) lasting >= min_duration.
    """
    pcm_samples = extract_pcm_samples(media_path, sample_rate=sample_rate)
    if not pcm_samples:
        return []

    frame_size = int(sample_rate * (frame_ms / 1000.0))
    hop_size = int(sample_rate * (hop_ms / 1000.0))
    min_frames = int(min_duration / (hop_ms / 1000.0))

    if len(pcm_samples) < frame_size:
        return []

    max_peak = max(abs(s) for s in pcm_samples) or 1
    min_energy = 0.025 * max_peak

    hesitation_spans: List[Tuple[float, float]] = []
    current_run = 0
    start_frame = 0
    prev_rms: Optional[float] = None
    prev_zcr: Optional[float] = None

    num_frames = (len(pcm_samples) - frame_size) // hop_size
    for i in range(num_frames):
        idx = i * hop_size
        frame = pcm_samples[idx : idx + frame_size]

        # Short-time RMS
        sum_sq = sum(s * s for s in frame)
        rms = math.sqrt(sum_sq / frame_size)

        # Zero-Crossing Rate
        zcr = 0
        for k in range(1, frame_size):
            if (frame[k] >= 0 and frame[k - 1] < 0) or (frame[k] < 0 and frame[k - 1] >= 0):
                zcr += 1
        norm_zcr = zcr / frame_size

        # Stationarity: stable volume (RMS) and stable pitch (ZCR)
        is_stationary = False
        if prev_rms is not None and prev_zcr is not None:
            rel_rms_diff = abs(rms - prev_rms) / (prev_rms + 1e-5)
            rel_zcr_diff = abs(norm_zcr - prev_zcr) / (prev_zcr + 1e-5)
            is_stationary = (rel_rms_diff < 0.25) and (rel_zcr_diff < 0.25)

        prev_rms = rms
        prev_zcr = norm_zcr

        # Prolonged neutral vowel hesitation criterion:
        # 1. Audible volume above noise floor
        # 2. Fundamental/first formant pitch range (120Hz - 640Hz)
        # 3. High frame-to-frame stationarity without consonant transition
        is_hesitation = (rms >= min_energy) and (0.010 <= norm_zcr <= 0.080) and is_stationary

        if is_hesitation:
            if current_run == 0:
                start_frame = i
            current_run += 1
        else:
            if current_run >= min_frames:
                t_start = (start_frame * hop_size) / sample_rate
                t_end = ((start_frame + current_run) * hop_size + frame_size) / sample_rate
                hesitation_spans.append((round(t_start, 2), round(t_end, 2)))
            current_run = 0

    if current_run >= min_frames:
        t_start = (start_frame * hop_size) / sample_rate
        t_end = len(pcm_samples) / sample_rate
        hesitation_spans.append((round(t_start, 2), round(t_end, 2)))

    return hesitation_spans


def remove_filler_intervals(
    segments: List[SpeechSegment],
    filler_intervals: List[Tuple[float, float]],
    min_segment_duration: float = 0.20,
) -> List[SpeechSegment]:
    """
    Carves out filler word and vocal hesitation intervals from speech segments,
    transforming hesitations into deliberate cuts that prompt camera angle switches.
    """
    if not filler_intervals or not segments:
        return segments

    # Merge overlapping or contiguous filler intervals
    sorted_fillers = sorted(filler_intervals, key=lambda x: x[0])
    merged_fillers: List[Tuple[float, float]] = []
    for f_start, f_end in sorted_fillers:
        if not merged_fillers:
            merged_fillers.append((f_start, f_end))
        else:
            prev_s, prev_e = merged_fillers[-1]
            if f_start <= prev_e:
                merged_fillers[-1] = (prev_s, max(prev_e, f_end))
            else:
                merged_fillers.append((f_start, f_end))

    new_segments: List[SpeechSegment] = []
    seg_idx = 0

    for seg in segments:
        cur_spans = [(seg.start, seg.end, seg.silence_before)]

        for f_start, f_end in merged_fillers:
            next_spans = []
            for s_start, s_end, s_before in cur_spans:
                # No overlap: retain span
                if f_end <= s_start or f_start >= s_end:
                    next_spans.append((s_start, s_end, s_before))
                    continue

                # Overlap: excise [f_start, f_end]
                # Left slice
                if f_start > s_start:
                    next_spans.append((s_start, f_start, s_before))

                # Right slice
                if f_end < s_end:
                    cut_dur = min(f_end, s_end) - max(f_start, s_start)
                    next_spans.append((f_end, s_end, cut_dur))

            cur_spans = next_spans

        for s_start, s_end, s_before in cur_spans:
            dur = s_end - s_start
            if dur >= min_segment_duration:
                new_segments.append(
                    SpeechSegment(
                        index=seg_idx,
                        start=round(s_start, 3),
                        end=round(s_end, 3),
                        duration=round(dur, 3),
                        silence_before=round(s_before, 3),
                    )
                )
                seg_idx += 1

    return new_segments
