"""
Audio Analyzer for OmniCam
Detects speech, pauses, and dead-air to drive the intelligent camera director.
"""

from dataclasses import dataclass
import json
import re
import subprocess
from typing import List, Optional, Tuple


@dataclass
class SpeechSegment:
    index: int
    start: float
    end: float
    duration: float
    silence_before: float = 0.0

    def __repr__(self) -> str:
        return (
            f"<SpeechSegment #{self.index} [{self.start:.2f}s -> {self.end:.2f}s "
            f"({self.duration:.2f}s, pause_before={self.silence_before:.2f}s)>"
        )


class AudioAnalyzer:
    """
    Analyzes video audio track using deterministic acoustic silence detection
    to isolate spoken segments and remove dead air.
    """

    def __init__(
        self,
        noise_threshold_db: float = -32.0,
        min_silence_duration: float = 0.35,
        padding_start: float = 0.06,
        padding_end: float = 0.06,
    ):
        self.noise_threshold_db = noise_threshold_db
        self.min_silence_duration = min_silence_duration
        self.padding_start = padding_start
        self.padding_end = padding_end

    @staticmethod
    def get_media_duration(file_path: str) -> float:
        """Retrieves exact video duration in seconds using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            file_path,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            return float(data["format"]["duration"])
        except Exception as e:
            # Fallback probe
            cmd_alt = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=duration",
                "-of", "csv=p=0",
                file_path,
            ]
            res_alt = subprocess.run(cmd_alt, capture_output=True, text=True)
            val = res_alt.stdout.strip()
            if val and val != "N/A":
                return float(val)
            raise RuntimeError(f"Failed to probe duration of {file_path}: {e}")

    def detect_silence_intervals(self, video_path: str) -> List[Tuple[float, float]]:
        """
        Executes FFmpeg silencedetect to identify intervals of silence.
        Returns a list of (start_time, end_time) tuples.
        """
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i", video_path,
            "-af", f"silencedetect=n={self.noise_threshold_db}dB:d={self.min_silence_duration}",
            "-f", "null",
            "-",
        ]

        process = subprocess.run(cmd, capture_output=True, text=True)
        stderr = process.stderr

        silence_starts: List[float] = []
        silences: List[Tuple[float, float]] = []

        start_pattern = re.compile(r"silence_start:\s*([0-9.]+)")
        end_pattern = re.compile(r"silence_end:\s*([0-9.]+)")

        for line in stderr.splitlines():
            start_match = start_pattern.search(line)
            if start_match:
                silence_starts.append(float(start_match.group(1)))
                continue

            end_match = end_pattern.search(line)
            if end_match:
                end_time = float(end_match.group(1))
                if silence_starts:
                    start_time = silence_starts.pop(0)
                    silences.append((start_time, end_time))

        return silences

    def extract_speech_segments(
        self, video_path: str, min_segment_duration: float = 0.2
    ) -> List[SpeechSegment]:
        """
        Inverts silence intervals into active speech segments, applying acoustic
        safety padding and merging sub-threshold gaps.
        """
        total_duration = self.get_media_duration(video_path)
        silences = self.detect_silence_intervals(video_path)

        if not silences:
            # No silence detected: speech is continuous across whole video
            return [
                SpeechSegment(
                    index=0,
                    start=0.0,
                    end=total_duration,
                    duration=total_duration,
                    silence_before=0.0,
                )
            ]

        # Invert silences to get speech ranges
        raw_speech_spans: List[Tuple[float, float, float]] = []
        cur_pos = 0.0

        for s_start, s_end in silences:
            silence_len = s_end - s_start
            if s_start > cur_pos:
                raw_speech_spans.append((cur_pos, s_start, silence_len))
            cur_pos = s_end

        if cur_pos < total_duration:
            raw_speech_spans.append((cur_pos, total_duration, 0.0))

        # Apply padding and clamp
        padded_spans: List[Tuple[float, float, float]] = []
        for start, end, s_len in raw_speech_spans:
            p_start = max(0.0, start - self.padding_start)
            p_end = min(total_duration, end + self.padding_end)
            if p_end > p_start:
                padded_spans.append((p_start, p_end, s_len))

        if not padded_spans:
            return []

        # Merge overlapping segments after padding
        merged_spans: List[Tuple[float, float, float]] = []
        curr_start, curr_end, curr_s_len = padded_spans[0]

        for next_start, next_end, next_s_len in padded_spans[1:]:
            if next_start <= curr_end:
                # Overlap or touch: merge
                curr_end = max(curr_end, next_end)
            else:
                merged_spans.append((curr_start, curr_end, curr_s_len))
                curr_start, curr_end, curr_s_len = next_start, next_end, next_s_len
        merged_spans.append((curr_start, curr_end, curr_s_len))

        # Filter out negligible noise blips and build SpeechSegment list
        result: List[SpeechSegment] = []
        idx = 0
        for start, end, s_len in merged_spans:
            dur = end - start
            if dur >= min_segment_duration:
                result.append(
                    SpeechSegment(
                        index=idx,
                        start=round(start, 3),
                        end=round(end, 3),
                        duration=round(dur, 3),
                        silence_before=round(s_len, 3),
                    )
                )
                idx += 1

        return result

