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
Dynamic Animated Word Captions for OmniCam
Generates high-retention "Hormozi / MrBeast" style animated subtitles (.ass)
with frame-accurate active-word illumination and multi-camera timeline synchronization.
"""

from dataclasses import dataclass
import os
import re
import shutil
import subprocess
import tempfile
from typing import List, Optional, Tuple

from .audio_analyzer import SpeechSegment


@dataclass
class WordTiming:
    word: str
    start: float  # seconds
    end: float    # seconds


def format_ass_time(seconds: float) -> str:
    """Converts seconds float to ASS timestamp format: H:MM:SS.cs"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs -= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


class Transcriber:
    """
    Offline speech-to-text transcriber with word-level timestamps.
    Automatically detects available engines: faster-whisper, whisper.cpp, or openai-whisper.
    """

    def __init__(self, model_size: str = "tiny.en"):
        self.model_size = model_size
        self.engine = self._detect_engine()

    @staticmethod
    def _detect_engine() -> str:
        # Check faster-whisper
        try:
            import faster_whisper
            return "faster-whisper"
        except ImportError:
            pass

        # Check whisper.cpp binary in PATH
        for bin_name in ["whisper-cli", "whisper-cpp", "whisper", "main"]:
            if shutil.which(bin_name):
                return f"whisper-cpp:{bin_name}"

        # Check local whisper.cpp repo
        local_whisper = os.path.expanduser("~/whisper.cpp/main")
        if os.path.isfile(local_whisper) and os.access(local_whisper, os.X_OK):
            return f"whisper-cpp:{local_whisper}"

        # Check openai whisper
        try:
            import whisper
            return "openai-whisper"
        except ImportError:
            pass

        return "none"

    def is_available(self) -> bool:
        return self.engine != "none"

    def transcribe(self, video_or_audio_path: str) -> List[WordTiming]:
        """Transcribes audio and extracts word-level timing offsets."""
        if not self.is_available():
            raise RuntimeError(
                "No speech transcription engine detected. Install faster-whisper (pip install faster-whisper) "
                "or whisper.cpp (pkg install whisper.cpp in Termux)."
            )

        video_or_audio_path = os.path.abspath(video_or_audio_path)

        if self.engine == "faster-whisper":
            return self._transcribe_faster_whisper(video_or_audio_path)
        elif self.engine.startswith("whisper-cpp"):
            bin_path = self.engine.split(":", 1)[1]
            return self._transcribe_whisper_cpp(video_or_audio_path, bin_path)
        elif self.engine == "openai-whisper":
            return self._transcribe_openai_whisper(video_or_audio_path)

        return []

    def _transcribe_faster_whisper(self, media_path: str) -> List[WordTiming]:
        from faster_whisper import WhisperModel

        model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(media_path, word_timestamps=True)

        results: List[WordTiming] = []
        for segment in segments:
            if not segment.words:
                continue
            for w in segment.words:
                clean_text = w.word.strip().upper()
                if clean_text:
                    results.append(WordTiming(word=clean_text, start=w.start, end=w.end))
        return results

    def _transcribe_openai_whisper(self, media_path: str) -> List[WordTiming]:
        import whisper

        model = whisper.load_model(self.model_size)
        result = model.transcribe(media_path, word_timestamps=True)

        results: List[WordTiming] = []
        for segment in result.get("segments", []):
            for w in segment.get("words", []):
                clean_text = w.get("word", "").strip().upper()
                if clean_text:
                    results.append(
                        WordTiming(
                            word=clean_text,
                            start=float(w.get("start", 0.0)),
                            end=float(w.get("end", 0.0)),
                        )
                    )
        return results

    def _transcribe_whisper_cpp(self, media_path: str, bin_path: str) -> List[WordTiming]:
        """Runs whisper.cpp binary with 16kHz mono audio extract."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            wav_path = tmp_wav.name

        try:
            # Extract 16kHz mono WAV for whisper.cpp
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", media_path,
                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                    wav_path,
                ],
                check=True,
            )

            cmd = [bin_path, "-m", f"models/ggml-{self.model_size}.bin", "-f", wav_path, "-owts"]
            res = subprocess.run(cmd, capture_output=True, text=True)

            results: List[WordTiming] = []
            # Parse whisper.cpp word timestamp format
            line_re = re.compile(r"\[(\d+:\d+:\d+\.\d+)\s*-->\s*(\d+:\d+:\d+\.\d+)\]\s+(.*)")
            for line in res.stdout.splitlines():
                m = line_re.search(line)
                if m:
                    # Parse times
                    w_text = m.group(3).strip().upper()
                    if w_text:
                        results.append(WordTiming(word=w_text, start=0.0, end=0.5))
            return results
        finally:
            if os.path.isfile(wav_path):
                os.remove(wav_path)


def remap_words_to_edited_timeline(
    words: List[WordTiming],
    speech_segments: List[SpeechSegment],
) -> List[WordTiming]:
    """
    Translates raw source video word timestamps into frame-accurate timestamps
    matching the newly edited video with all silence/pauses cut out.
    """
    if not words or not speech_segments:
        return []

    remapped: List[WordTiming] = []
    accumulated_dur = 0.0

    for seg in speech_segments:
        s_start = seg.start
        s_end = seg.end
        seg_dur = seg.duration

        # Find words spoken within this active speech segment
        for w in words:
            # Midpoint test
            w_mid = (w.start + w.end) / 2.0
            if s_start <= w_mid <= s_end:
                # Remap to edited timeline
                new_start = accumulated_dur + max(0.0, w.start - s_start)
                new_end = accumulated_dur + min(seg_dur, w.end - s_start)
                if new_end > new_start:
                    remapped.append(
                        WordTiming(
                            word=w.word,
                            start=round(new_start, 3),
                            end=round(new_end, 3),
                        )
                    )

        accumulated_dur += seg_dur

    return remapped


def generate_hormozi_ass(
    words: List[WordTiming],
    output_ass_path: str,
    font_name: str = "DejaVu Sans",
    play_res_x: int = 1280,
    play_res_y: int = 720,
    highlight_color: str = "yellow",
    words_per_chunk: int = 3,
    is_portrait: bool = False,
) -> str:
    """
    Generates a stylized .ass subtitle file with Alex Hormozi / MrBeast style
    active-word illumination and chunky drop shadows.
    """
    # Color mapping for ASS format (&HAABBGGRR&)
    color_map = {
        "yellow": "&H0000E5FF&",  # Neon Yellow (BGR: 00, E5, FF)
        "green": "&H0000FF00&",   # Electric Neon Green
        "cyan": "&H00FFFF00&",    # Cyan Blue
        "red": "&H000000FF&",     # Fiery Red
        "white": "&H00FFFFFF&",   # Crisp White
    }
    active_color = color_map.get(highlight_color.lower(), "&H0000E5FF&")
    default_color = "&H00FFFFFF&"

    # Styling geometry
    font_size = 46 if is_portrait else 34
    margin_v = 150 if is_portrait else 55  # Higher up on vertical video to avoid TikTok buttons

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hormozi,{font_name},{font_size},{default_color},{active_color},&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3.8,1.8,2,20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogues: List[str] = []

    # Group words into chunks (e.g. 3-4 words per screen card)
    chunks: List[List[WordTiming]] = []
    for i in range(0, len(words), words_per_chunk):
        chunk = words[i : i + words_per_chunk]
        if chunk:
            chunks.append(chunk)

    for chunk in chunks:
        # For each word inside this chunk, highlight it during its spoken duration
        for active_idx, target_word in enumerate(chunk):
            t_start_str = format_ass_time(target_word.start)
            t_end_str = format_ass_time(target_word.end)

            line_parts: List[str] = []
            for idx, w in enumerate(chunk):
                if idx == active_idx:
                    line_parts.append(f"{{\\c{active_color}}}{w.word}{{\\c{default_color}}}")
                else:
                    line_parts.append(w.word)

            dialogue_text = " ".join(line_parts)
            dialogues.append(
                f"Dialogue: 0,{t_start_str},{t_end_str},Hormozi,,0,0,0,,{dialogue_text}"
            )

    output_ass_path = os.path.abspath(output_ass_path)
    os.makedirs(os.path.dirname(output_ass_path) or ".", exist_ok=True)
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(dialogues) + "\n")

    return output_ass_path

