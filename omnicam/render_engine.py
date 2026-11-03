"""
Render Engine for OmniCam
Compiles shot plans and audio cuts into optimized FFmpeg rendering pipelines.
Supports studio audio normalization, multi-angle cropping, and cinematic color grades.
"""

from dataclasses import dataclass
import os
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Dict, List, Optional

from .director import CameraAngle, ShotPlan


@dataclass
class RenderConfig:
    target_width: int = 1280
    target_height: int = 720
    color_grade: str = "cinematic"  # "cinematic", "podcast", "vintage", "none"
    normalize_audio: bool = True
    highpass_audio: bool = True
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 21
    preset: str = "fast"
    force_chunk_mode: bool = False


def detect_safe_video_codec() -> str:
    """Detects available H.264 video encoder supported by the local FFmpeg build."""
    try:
        res = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
        out = res.stdout
        if "libx264" in out:
            return "libx264"
        elif "h264_mediacodec" in out:
            return "h264_mediacodec"
        elif "h264" in out:
            return "h264"
        elif "mpeg4" in out:
            return "mpeg4"
    except Exception:
        pass
    return "libx264"


class RenderEngine:
    """
    Renders the director's multi-angle shot plan into a final polished studio video.
    """

    def __init__(self, input_video: str, config: Optional[RenderConfig] = None):
        self.input_video = os.path.abspath(input_video)
        self.config = config or RenderConfig()
        if not self.config.video_codec or self.config.video_codec == "libx264":
            self.config.video_codec = detect_safe_video_codec()

    def render(
        self,
        shot_plans: List[ShotPlan],
        output_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """
        Executes video generation. Chooses single-pass filtergraph for optimal speed,
        or chunked demuxer for massive segment counts.
        """
        if not shot_plans:
            raise ValueError("No shot plans provided for rendering.")

        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if progress_callback:
            progress_callback(0.05, "Initializing FFmpeg rendering pipeline...")

        # Decide rendering mode
        if len(shot_plans) > 40 or self.config.force_chunk_mode:
            return self._render_chunked(shot_plans, output_path, progress_callback)
        else:
            return self._render_single_pass(shot_plans, output_path, progress_callback)

    def _get_color_filter(self) -> str:
        grade = self.config.color_grade.lower()
        if grade == "cinematic":
            # Rich contrast, subtle teal/warm separation
            return "eq=contrast=1.08:brightness=0.01:saturation=1.12,colorbalance=rs=0.02:bs=-0.02:rm=-0.01:bm=0.02"
        elif grade == "podcast":
            # Vibrant tech YouTube look
            return "eq=contrast=1.05:saturation=1.10"
        elif grade == "vintage":
            # Muted retro documentary
            return "eq=contrast=1.02:saturation=0.88,colorbalance=gs=0.02:bs=-0.04"
        return ""

    def _render_single_pass(
        self,
        shot_plans: List[ShotPlan],
        output_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """
        Builds a single elegant FFmpeg filter_complex graph.
        Zero intermediate disk writes; maximum rendering speed.
        """
        filter_parts: List[str] = []
        v_concat_inputs: List[str] = []
        a_concat_inputs: List[str] = []

        tw = self.config.target_width
        th = self.config.target_height
        color_filter = self._get_color_filter()

        for idx, shot in enumerate(shot_plans):
            seg = shot.segment
            s_start = seg.start
            s_end = seg.end
            dur = max(0.1, seg.duration)

            crop = shot.crop_coords
            cx, cy, cw, ch = crop["x"], crop["y"], crop["w"], crop["h"]

            # Video branch
            v_in = f"[0:v]trim=start={s_start}:end={s_end},setpts=PTS-STARTPTS"

            if shot.angle == CameraAngle.SLOW_PUSH:
                # Dynamic push-in zoom: crops dynamically over time from 1.0x to 1.18x
                # clamp zoom smoothly with t/dur
                zoom_expr = f"(1.0 + 0.18*(t/{dur:.3f}))"
                w_expr = f"(iw/{zoom_expr})"
                h_expr = f"(ih/{zoom_expr})"
                x_expr = f"({cx + cw/2.0} - (w/2))"
                y_expr = f"({cy + ch/2.0} - (h/2))"
                crop_filter = f"crop=w='{w_expr}':h='{h_expr}':x='{x_expr}':y='{y_expr}'"
            else:
                crop_filter = f"crop=w={cw}:h={ch}:x={cx}:y={cy}"

            scale_filter = f"scale={tw}:{th}:flags=lanczos,setsar=1"
            v_chain = f"{v_in},{crop_filter},{scale_filter}"

            # Subtle clip edge fade to prevent visual flicker
            if dur > 0.4:
                v_chain += f",fade=t=in:st=0:d=0.03"

            if color_filter:
                v_chain += f",{color_filter}"

            v_out_label = f"[v{idx}]"
            filter_parts.append(f"{v_chain}{v_out_label}")
            v_concat_inputs.append(v_out_label)

            # Audio branch
            a_in = f"[0:a]atrim=start={s_start}:end={s_end},asetpts=PTS-STARTPTS"
            # Micro-fades on audio boundaries to prevent clicks
            fade_in_d = min(0.015, dur / 4.0)
            fade_out_d = min(0.015, dur / 4.0)
            fade_out_st = max(0.0, dur - fade_out_d)
            a_chain = f"{a_in},afade=t=in:ss=0:d={fade_in_d:.3f},afade=t=out:st={fade_out_st:.3f}:d={fade_out_d:.3f}"

            a_out_label = f"[a{idx}]"
            filter_parts.append(f"{a_chain}{a_out_label}")
            a_concat_inputs.append(a_out_label)

        # Concat stage - FFmpeg concat=v=1:a=1 requires interleaved stream pairs: [v0][a0][v1][a1]...
        num_shots = len(shot_plans)
        interleaved_concat_inputs: List[str] = []
        for idx in range(num_shots):
            interleaved_concat_inputs.append(f"[v{idx}][a{idx}]")

        concat_in_str = "".join(interleaved_concat_inputs)
        filter_parts.append(
            f"{concat_in_str}concat=n={num_shots}:v=1:a=1[v_stitched][a_stitched]"
        )

        # Audio Mastering filters on the final stitched stream
        final_a_chain = "[a_stitched]"
        audio_filters: List[str] = []
        if self.config.highpass_audio:
            audio_filters.append("highpass=f=80")
        if self.config.normalize_audio:
            # EBU R128 loudness normalization
            audio_filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")

        if audio_filters:
            filter_parts.append(f"{final_a_chain}{','.join(audio_filters)}[a_final]")
            final_a_label = "[a_final]"
        else:
            final_a_label = "[a_stitched]"

        full_filtergraph = ";\n".join(filter_parts)

        # Prepare FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-i", self.input_video,
            "-filter_complex", full_filtergraph,
            "-map", "[v_stitched]",
            "-map", final_a_label,
            "-c:v", self.config.video_codec,
            "-pix_fmt", "yuv420p",
            "-profile:v", "main",
            "-level:v", "3.1",
            "-crf", str(self.config.crf),
            "-preset", self.config.preset,
            "-c:a", self.config.audio_codec,
            "-ar", "44100",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]

        if progress_callback:
            progress_callback(0.20, f"Rendering {num_shots} studio angles with FFmpeg...")

        t_start = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode != 0:
            # If complex filtergraph failed, raise with diagnostics
            err_msg = res.stderr[-2000:] if res.stderr else "Unknown FFmpeg failure"
            raise RuntimeError(f"FFmpeg rendering failed (code {res.returncode}):\n{err_msg}")

        elapsed = time.time() - t_start
        if progress_callback:
            progress_callback(1.0, f"Rendering complete in {elapsed:.1f}s -> {output_path}")

        return output_path

    def _render_chunked(
        self,
        shot_plans: List[ShotPlan],
        output_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """
        Chunk-based rendering for very large videos with dozens/hundreds of cuts.
        Renders individual segment files to temp directory and joins with concat demuxer.
        """
        temp_dir = tempfile.mkdtemp(prefix="omnicam_chunks_")
        chunk_files: List[str] = []

        tw = self.config.target_width
        th = self.config.target_height
        color_filter = self._get_color_filter()
        total_shots = len(shot_plans)

        try:
            for idx, shot in enumerate(shot_plans):
                seg = shot.segment
                dur = max(0.1, seg.duration)
                crop = shot.crop_coords
                cx, cy, cw, ch = crop["x"], crop["y"], crop["w"], crop["h"]

                chunk_file = os.path.join(temp_dir, f"chunk_{idx:04d}.mp4")

                # Video filter
                if shot.angle == CameraAngle.SLOW_PUSH:
                    zoom_expr = f"(1.0 + 0.18*(t/{dur:.3f}))"
                    crop_f = f"crop=w='(iw/{zoom_expr})':h='(ih/{zoom_expr})':x='{cx + cw/2.0}-(w/2)':y='{cy + ch/2.0}-(h/2)'"
                else:
                    crop_f = f"crop=w={cw}:h={ch}:x={cx}:y={cy}"

                v_chain = f"{crop_f},scale={tw}:{th}:flags=lanczos,setsar=1"
                if color_filter:
                    v_chain += f",{color_filter}"

                # Audio filter
                fade_in_d = min(0.015, dur / 4.0)
                fade_out_d = min(0.015, dur / 4.0)
                fade_out_st = max(0.0, dur - fade_out_d)
                a_chain = f"afade=t=in:ss=0:d={fade_in_d:.3f},afade=t=out:st={fade_out_st:.3f}:d={fade_out_d:.3f}"

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss", str(seg.start),
                    "-to", str(seg.end),
                    "-i", self.input_video,
                    "-vf", v_chain,
                    "-af", a_chain,
                    "-c:v", self.config.video_codec,
                    "-pix_fmt", "yuv420p",
                    "-profile:v", "main",
                    "-level:v", "3.1",
                    "-crf", str(self.config.crf),
                    "-preset", self.config.preset,
                    "-c:a", self.config.audio_codec,
                    "-ar", "44100",
                    "-b:a", "192k",
                    chunk_file,
                ]

                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode != 0:
                    raise RuntimeError(f"Chunk render failed for shot #{idx}: {res.stderr[-500:]}")

                chunk_files.append(chunk_file)
                if progress_callback:
                    pct = 0.10 + (0.75 * (idx + 1) / total_shots)
                    progress_callback(pct, f"Rendered angle {idx+1}/{total_shots} ({shot.angle.value})")

            # Write concat demuxer file
            concat_list = os.path.join(temp_dir, "concat.txt")
            with open(concat_list, "w") as f:
                for cf in chunk_files:
                    f.write(f"file '{cf}'\n")

            # Final concat and audio master
            audio_master = []
            if self.config.highpass_audio:
                audio_master.append("highpass=f=80")
            if self.config.normalize_audio:
                audio_master.append("loudnorm=I=-16:TP=-1.5:LRA=11")

            concat_cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list,
            ]
            if audio_master:
                concat_cmd += ["-af", ",".join(audio_master)]

            concat_cmd += [
                "-c:v", self.config.video_codec,
                "-pix_fmt", "yuv420p",
                "-profile:v", "main",
                "-level:v", "3.1",
                "-c:a", self.config.audio_codec,
                "-ar", "44100",
                "-movflags", "+faststart",
                output_path,
            ]

            if progress_callback:
                progress_callback(0.90, "Concatenating multi-camera master cut...")

            res_concat = subprocess.run(concat_cmd, capture_output=True, text=True)
            if res_concat.returncode != 0:
                raise RuntimeError(f"Concat failed: {res_concat.stderr[-1000:]}")

            return output_path
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
