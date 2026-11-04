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
Render Engine for OmniCam
Compiles shot plans, dynamic angle transitions, Hollywood color grading,
broadcast lower-third titles, and auto-ducking background music into an optimized FFmpeg pipeline.
"""

from dataclasses import dataclass
import os
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Dict, List, Optional

from .director import CameraAngle, ShotPlan
from .captions import (
    Transcriber,
    generate_hormozi_ass,
    remap_words_to_edited_timeline,
)
from .stabilizer import VideoStabilizer, is_vidstab_supported
from .broll import BRollManager, BRollAsset, SUPPORTED_VIDEO_EXTS
from .overlay_engine import OverlayEngine


@dataclass
class RenderConfig:
    target_width: int = 1280
    target_height: int = 720
    is_portrait: bool = False
    color_grade: str = "cinematic"  # "cinematic", "podcast", "vintage", "none"
    normalize_audio: bool = True
    highpass_audio: bool = True
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.22
    enable_captions: bool = False
    caption_color: str = "yellow"  # "yellow", "green", "cyan", "red", "white"
    whisper_model: str = "tiny.en"
    captions_file: Optional[str] = None
    stabilize: bool = False
    stabilize_smoothing: int = 25
    broll_dir: Optional[str] = None
    broll_min_dur: float = 4.0
    broll_length: float = 2.5
    show_hud: bool = True
    show_title: bool = True
    title_text: str = "OMNICAM AI • MULTI-CAM PRODUCTION"
    subtitle_text: str = "PRO VIRTUAL STUDIO // 4K CLARITY"
    transition_flash: bool = True
    transition_style: str = "flash"  # "flash", "zoom", "push", "glitch", "dissolve", "none"
    enable_freeze_frames: bool = True
    freeze_duration: float = 0.6
    enable_crash_zoom: bool = True
    enable_sfx: bool = True
    sfx_volume: float = 0.35
    input_videos: Optional[List[str]] = None
    letterbox: bool = False
    vignette: bool = True
    film_grain: bool = False
    custom_watermark: Optional[str] = None
    overlay_effect: Optional[str] = None
    overlay_blend_mode: str = "screen"
    overlay_opacity: float = 0.85
    overlay_path: Optional[str] = None
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 21
    preset: str = "fast"
    force_chunk_mode: bool = False


def generate_whoosh_sfx(output_wav: str, duration: float = 0.20):
    """Synthesizes a clean pink-noise cinematic whoosh sweep for CapCut cut transitions."""
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-i", f"anoisesrc=d={duration:.2f}:color=pink,volume=0.32,afade=t=in:d=0.04,afade=t=out:st=0.08:d=0.12",
        "-c:a", "pcm_s16le", output_wav
    ]
    subprocess.run(cmd, check=True, capture_output=True)


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


def find_system_font() -> Optional[str]:
    """Finds a robust, readable TTF font on Android (Termux) or Linux."""
    candidates = [
        # Android paths (Termux)
        "/system/fonts/Roboto-Medium.ttf",
        "/system/fonts/Roboto-Bold.ttf",
        "/system/fonts/Roboto-Regular.ttf",
        "/system/fonts/DroidSans.ttf",
        # Linux paths
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def generate_ambient_track(output_wav: str, duration: float = 60.0):
    """Generates a warm, royalty-free C-Major ambient harmonic bed for auto-ducking."""
    af = (
        f"aevalsrc='0.11*sin(2*PI*130.81*t) + 0.09*sin(2*PI*164.81*t) + "
        f"0.08*sin(2*PI*196.00*t) + 0.05*sin(2*PI*246.94*t) + 0.04*sin(2*PI*261.63*t)':s=44100"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", af,
        "-t", str(duration),
        "-c:a", "pcm_s16le",
        output_wav,
    ]
    subprocess.run(cmd, check=True)


class RenderEngine:
    """
    Renders multi-angle cuts with professional broadcast graphics,
    optical transitions, auto-ducking background music, and studio audio mastering.
    """

    def __init__(
        self,
        input_video: str,
        config: Optional[RenderConfig] = None,
        input_videos: Optional[List[str]] = None,
    ):
        self.input_video = os.path.abspath(input_video)
        self.config = config or RenderConfig()
        if input_videos:
            self.input_videos = [os.path.abspath(v) for v in input_videos if os.path.isfile(v)]
        elif self.config.input_videos:
            self.input_videos = [os.path.abspath(v) for v in self.config.input_videos if os.path.isfile(v)]
        else:
            self.input_videos = [self.input_video]
        if not self.config.video_codec or self.config.video_codec == "libx264":
            self.config.video_codec = detect_safe_video_codec()
        self.font_path = find_system_font()

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
            progress_callback(0.05, "Initializing FFmpeg cinematic pipeline...")

        # Handle built-in ambient synth bed if requested
        temp_ambient_file = None
        if self.config.bgm_path and self.config.bgm_path.lower() in ("ambient", "lofi", "chill", "generate"):
            temp_ambient = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_ambient.close()
            temp_ambient_file = temp_ambient.name
            if progress_callback:
                progress_callback(0.08, "Synthesizing warm royalty-free ambient audio bed...")
            generate_ambient_track(temp_ambient_file, duration=90.0)
            self.config.bgm_path = temp_ambient_file

        # Handle animated Hormozi / MrBeast subtitles
        temp_ass_file = None
        self.active_ass_path = None
        if self.config.enable_captions or self.config.captions_file:
            if self.config.captions_file and os.path.isfile(self.config.captions_file):
                self.active_ass_path = self.config.captions_file
            else:
                try:
                    if progress_callback:
                        progress_callback(0.12, f"Transcribing speech with Whisper ({self.config.whisper_model})...")
                    transcriber = Transcriber(model_size=self.config.whisper_model)
                    if transcriber.is_available():
                        raw_words = transcriber.transcribe(self.input_video)
                        speech_segs = [s.segment for s in shot_plans]
                        remapped = remap_words_to_edited_timeline(raw_words, speech_segs)
                        t_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False)
                        t_ass.close()
                        temp_ass_file = t_ass.name
                        generate_hormozi_ass(
                            words=remapped,
                            output_ass_path=temp_ass_file,
                            play_res_x=self.config.target_width,
                            play_res_y=self.config.target_height,
                            highlight_color=self.config.caption_color,
                            is_portrait=self.config.is_portrait,
                        )
                        self.active_ass_path = temp_ass_file
                        if progress_callback:
                            progress_callback(0.18, f"Generated {len(remapped)} animated karaoke captions...")
                    else:
                        print("  [!] Notice: Whisper engine not detected. Burned subtitles skipped.")
                except Exception as ex:
                    print(f"  [!] Warning: Subtitle generation failed: {ex}. Rendering video without burned subtitles.")

                # Synthesize CapCut transition whoosh SFX bed if enabled
        temp_whoosh_file = None
        if self.config.enable_sfx:
            try:
                t_whoosh = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                t_whoosh.close()
                temp_whoosh_file = t_whoosh.name
                generate_whoosh_sfx(temp_whoosh_file, duration=0.22)
            except Exception as ex:
                print(f"  [!] Notice: Could not synthesize whoosh SFX: {ex}")
                temp_whoosh_file = None

        # Handle Digital Gimbal 2-pass horizon stabilization
        temp_trf_file = None
        self.active_trf_path = None
        if self.config.stabilize:
            if is_vidstab_supported():
                t_trf = tempfile.NamedTemporaryFile(suffix=".trf", delete=False)
                t_trf.close()
                temp_trf_file = t_trf.name
                try:
                    stabilizer = VideoStabilizer(smoothing=self.config.stabilize_smoothing)
                    stabilizer.detect_transforms(self.input_video, temp_trf_file, progress_callback)
                    self.active_trf_path = temp_trf_file
                except Exception as ex:
                    print(f"  [!] Warning: Gimbal stabilization Pass 1 failed: {ex}. Proceeding with raw motion.")
                    self.active_trf_path = None
            else:
                print("  [!] Notice: libvidstab not detected in local FFmpeg. Proceeding without optical stabilization.")

        # Prepare normalized B-roll clips for any B-roll cutaway shots
        temp_broll_files: Dict[int, str] = {}
        for shot in shot_plans:
            if shot.angle == CameraAngle.BROLL and shot.broll_path and os.path.isfile(shot.broll_path):
                tmp_broll = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                tmp_broll.close()
                temp_broll_files[shot.index] = tmp_broll.name
                if progress_callback:
                    progress_callback(0.20, f"Normalizing B-roll cutaway '{shot.broll_name or 'clip'}'...")
                is_vid = any(shot.broll_path.lower().endswith(ext) for ext in SUPPORTED_VIDEO_EXTS)
                asset = BRollAsset(path=shot.broll_path, is_video=is_vid, name=shot.broll_name or os.path.basename(shot.broll_path))
                BRollManager.prepare_clip(
                    asset=asset,
                    duration=shot.segment.duration,
                    target_width=self.config.target_width,
                    target_height=self.config.target_height,
                    output_path=tmp_broll.name,
                )

        try:
            if len(shot_plans) > 40 or self.config.force_chunk_mode:
                return self._render_chunked(shot_plans, output_path, progress_callback, temp_broll_files, temp_whoosh_file)
            else:
                return self._render_single_pass(shot_plans, output_path, progress_callback, temp_broll_files, temp_whoosh_file)
        finally:
            if temp_ambient_file and os.path.isfile(temp_ambient_file):
                try:
                    os.remove(temp_ambient_file)
                except OSError:
                    pass
            if temp_ass_file and os.path.isfile(temp_ass_file):
                try:
                    os.remove(temp_ass_file)
                except OSError:
                    pass
            if temp_whoosh_file and os.path.isfile(temp_whoosh_file):
                try:
                    os.remove(temp_whoosh_file)
                except OSError:
                    pass
            if temp_trf_file and os.path.isfile(temp_trf_file):
                try:
                    os.remove(temp_trf_file)
                except OSError:
                    pass
            for b_file in temp_broll_files.values():
                if os.path.isfile(b_file):
                    try:
                        os.remove(b_file)
                    except OSError:
                        pass

    def _get_color_filter(self) -> str:
        filters = []
        grade = self.config.color_grade.lower()
        if grade == "cinematic":
            # Hollywood Teal & Orange: punchy contrast, warm skin tones, cool shadows
            filters.append("eq=contrast=1.12:brightness=0.01:saturation=1.20")
            filters.append("colorbalance=rs=0.04:gs=-0.01:bs=-0.03:rm=-0.02:bm=0.04:rh=0.03:bh=-0.02")
        elif grade == "podcast":
            filters.append("eq=contrast=1.08:brightness=0.02:saturation=1.14")
        elif grade == "vintage":
            filters.append("eq=contrast=1.02:saturation=0.88,colorbalance=gs=0.02:bs=-0.04")

        if self.config.vignette and grade != "none":
            filters.append("vignette=PI/4.5")

        filters.append("unsharp=3:3:0.6:3:3:0.0")
        return ",".join(filters)

    def _get_hud_filter(self, angle: CameraAngle, tw: int, th: int) -> str:
        """Generates dynamic on-screen camera badge (e.g. CAM 1 • MASTER WIDE)."""
        if not self.config.show_hud or not self.font_path:
            return ""

        badge_map = {
            CameraAngle.WIDE: "CAM 1 // MASTER WIDE",
            CameraAngle.CLOSEUP: "CAM 2 // CLOSE-UP",
            CameraAngle.THIRD_LEFT: "CAM 3 // ISO-LEFT",
            CameraAngle.THIRD_RIGHT: "CAM 4 // ISO-RIGHT",
            CameraAngle.SLOW_PUSH: "CAM 5 // DYNAMIC PUSH",
            CameraAngle.BROLL: "B-ROLL // CUTAWAY",
        }
        badge_text = badge_map.get(angle, f"CAM // {angle.value}")

        font_arg = f":fontfile='{self.font_path}'"
        bg_box = "drawbox=x=25:y=25:w=225:h=32:color=black@0.65:t=fill:enable='between(t,0,2.5)'"
        dot_color = "0x00D2FF@0.9" if angle == CameraAngle.BROLL else "red@0.9"
        rec_dot = f"drawbox=x=35:y=36:w=10:h=10:color={dot_color}:t=fill:enable='between(t,0,2.5)'"
        txt = (
            f"drawtext={font_arg}:text='{badge_text}':fontcolor=white:fontsize=14:x=54:y=33:enable='between(t,0,2.5)'"
        )
        return f"{bg_box},{rec_dot},{txt}"

    def _get_title_overlay(self, shot_idx: int, dur: float, tw: int, th: int) -> str:
        """Generates an aesthetic animated lower-third title card in the opening shot."""
        if not self.config.show_title or shot_idx != 0 or not self.font_path:
            return ""

        font_arg = f":fontfile='{self.font_path}'"
        end_t = min(4.5, dur)
        if end_t <= 1.0:
            return ""

        box_y = th - 95
        box_w = tw - 50
        bg_box = f"drawbox=x=25:y={box_y}:w={box_w}:h=65:color=black@0.75:t=fill:enable='between(t,0.3,{end_t:.2f})'"
        accent_bar = f"drawbox=x=25:y={box_y}:w=6:h=65:color=0x00D2FF@1.0:t=fill:enable='between(t,0.3,{end_t:.2f})'"
        t1 = (
            f"drawtext={font_arg}:text='{self.config.title_text}':fontcolor=white:fontsize=16:x=42:y={box_y+10}:enable='between(t,0.3,{end_t:.2f})'"
        )
        t2 = (
            f"drawtext={font_arg}:text='{self.config.subtitle_text}':fontcolor=0x00D2FF:fontsize=12:x=42:y={box_y+36}:enable='between(t,0.3,{end_t:.2f})'"
        )
        return f"{bg_box},{accent_bar},{t1},{t2}"

    def _render_single_pass(
        self,
        shot_plans: List[ShotPlan],
        output_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        temp_broll_files: Optional[Dict[int, str]] = None,
        temp_whoosh_file: Optional[str] = None,
    ) -> str:
        """
        Builds a single elegant FFmpeg filter_complex graph with CapCut transitions,
        freeze frame spotlight moments, whoosh SFX, and auto-ducking BGM.
        """
        temp_broll_files = temp_broll_files or {}
        filter_parts: List[str] = []
        tw = self.config.target_width
        th = self.config.target_height
        color_filter = self._get_color_filter()

        # Build list of inputs: input_videos (0..N-1)
        input_args: List[str] = []
        for vpath in self.input_videos:
            input_args.extend(["-i", vpath])

        # Map B-roll shots to their input indices
        shot_broll_in_idx: Dict[int, int] = {}
        for shot in shot_plans:
            if shot.angle == CameraAngle.BROLL and shot.index in temp_broll_files:
                in_idx = input_args.count("-i")
                shot_broll_in_idx[shot.index] = in_idx
                input_args.extend(["-i", temp_broll_files[shot.index]])

        # Whoosh SFX input index
        sfx_input_idx = None
        if temp_whoosh_file and os.path.isfile(temp_whoosh_file):
            sfx_input_idx = input_args.count("-i")
            input_args.extend(["-i", temp_whoosh_file])

        # CapCut Blend Mode Overlay input index (Light leaks, film burns, VHS dust, etc.)
        overlay_file = None
        overlay_input_idx = None
        if self.config.overlay_effect or self.config.overlay_path:
            ov_engine = OverlayEngine()
            target_ov = self.config.overlay_path or self.config.overlay_effect
            overlay_file = ov_engine.get_overlay_path(target_ov)
            if overlay_file and os.path.isfile(overlay_file):
                overlay_input_idx = input_args.count("-i")
                input_args.extend(["-stream_loop", "-1", "-i", overlay_file])

        # BGM input index
        has_bgm = self.config.bgm_path and os.path.isfile(self.config.bgm_path)
        bgm_input_idx = None
        total_speech_dur = sum(s.segment.duration for s in shot_plans)
        if has_bgm:
            bgm_input_idx = input_args.count("-i")
            input_args.extend(["-stream_loop", "-1", "-t", f"{total_speech_dur + 5.0:.3f}", "-i", self.config.bgm_path])

        # Digital Gimbal Master Stabilization for primary clip
        if self.active_trf_path and os.path.isfile(self.active_trf_path):
            escaped_trf = self.active_trf_path.replace("\\", "/").replace(":", "\\:")
            filter_parts.append(
                f"[0:v]vidstabtransform=input='{escaped_trf}':smoothing={self.config.stabilize_smoothing}:"
                f"optalgo=gauss:interpol=bicubic:zoom=2:crop=black[v_stabilized]"
            )

        for idx, shot in enumerate(shot_plans):
            seg = shot.segment
            s_start = seg.start
            s_end = seg.end
            dur = max(0.1, seg.duration)

            crop = shot.crop_coords
            cx, cy, cw, ch = crop["x"], crop["y"], crop["w"], crop["h"]
            clip_idx = min(getattr(shot, "clip_index", 0), len(self.input_videos) - 1)

            if clip_idx == 0 and self.active_trf_path and os.path.isfile(self.active_trf_path):
                v_master_src = "[v_stabilized]"
            else:
                v_master_src = f"[{clip_idx}:v]"
            a_master_src = f"[{clip_idx}:a]"

            # Video branch: choose B-roll source or camera source
            if shot.angle == CameraAngle.BROLL and shot.index in shot_broll_in_idx:
                broll_in_idx = shot_broll_in_idx[shot.index]
                v_in = f"[{broll_in_idx}:v]setpts=PTS-STARTPTS"
                v_chain_list = [v_in]
            else:
                v_in = f"{v_master_src}trim=start={s_start}:end={s_end},setpts=PTS-STARTPTS"

                # CapCut Freeze Frame Hook: freeze frame at start of shot with spotlight
                if getattr(shot, "is_freeze_frame", False) and getattr(shot, "freeze_duration", 0.0) > 0:
                    fdur = shot.freeze_duration
                    v_chain_list = [
                        v_in,
                        f"tpad=start_duration={fdur:.2f}:start_mode=clone",
                        f"eq=contrast=1.35:saturation=0.40:enable='between(t,0,{fdur:.2f})'",
                        f"drawbox=x=0:y=0:w={tw}:h=42:color=black@0.65:t=fill:enable='between(t,0,{fdur:.2f})'",
                        f"drawtext=text='FREEZE // IMPACT':fontcolor=0xFFCC00:fontsize=15:x=25:y=14:enable='between(t,0,{fdur:.2f})'",
                    ]
                else:
                    v_chain_list = [v_in]

                crop_filter = f"crop=w={cw}:h={ch}:x={cx}:y={cy}"
                scale_filter = f"scale={tw}:{th}:flags=lanczos,setsar=1"
                v_chain_list.extend([crop_filter, scale_filter])

            # Transitions (CapCut Style)
            tr = getattr(shot, "transition", None) or self.config.transition_style
            if idx > 0:
                freeze_offset = shot.freeze_duration if (getattr(shot, "is_freeze_frame", False) and shot.freeze_duration > 0) else 0.0
                if tr == "flash":
                    v_chain_list.append(f"fade=t=in:st={freeze_offset:.2f}:d=0.10:color=white@0.88")
                elif tr == "glitch":
                    v_chain_list.append(f"fade=t=in:st={freeze_offset:.2f}:d=0.06:color=cyan@0.75,fade=t=in:st={freeze_offset+0.06:.2f}:d=0.04:color=red@0.55")
                elif tr == "dissolve":
                    v_chain_list.append(f"fade=t=in:st={freeze_offset:.2f}:d=0.20")
                elif tr == "zoom":
                    v_chain_list.append(f"fade=t=in:st={freeze_offset:.2f}:d=0.08:color=white@0.65")
            elif dur > 0.4:
                v_chain_list.append("fade=t=in:st=0:d=0.04")

            if color_filter:
                v_chain_list.append(color_filter)

            hud_f = self._get_hud_filter(shot.angle, tw, th)
            if hud_f:
                v_chain_list.append(hud_f)

            title_f = self._get_title_overlay(idx, dur, tw, th)
            if title_f:
                v_chain_list.append(title_f)

            if self.config.letterbox and not self.config.is_portrait:
                bar_h = int(th * 0.08)
                v_chain_list.append(f"drawbox=x=0:y=0:w={tw}:h={bar_h}:color=black:t=fill")
                v_chain_list.append(f"drawbox=x=0:y={th-bar_h}:w={tw}:h={bar_h}:color=black:t=fill")

            if self.config.film_grain:
                v_chain_list.append("noise=alls=12:allf=t+u")

            if self.config.custom_watermark and self.font_path:
                wm = self.config.custom_watermark.replace("'", "\\'")
                v_chain_list.append(f"drawtext=fontfile='{self.font_path}':text='{wm}':fontcolor=white@0.65:fontsize=13:x={tw}-text_w-25:y=25")

            v_chain = ",".join(v_chain_list)
            v_out_label = f"[v{idx}]"
            filter_parts.append(f"{v_chain}{v_out_label}")

            # Audio branch
            a_in = f"{a_master_src}atrim=start={s_start}:end={s_end},asetpts=PTS-STARTPTS"
            fade_in_d = min(0.015, dur / 4.0)
            fade_out_d = min(0.015, dur / 4.0)
            fade_out_st = max(0.0, dur - fade_out_d)
            a_base = f"{a_in},afade=t=in:ss=0:d={fade_in_d:.3f},afade=t=out:st={fade_out_st:.3f}:d={fade_out_d:.3f}"

            if getattr(shot, "is_freeze_frame", False) and shot.freeze_duration > 0:
                delay_ms = int(shot.freeze_duration * 1000)
                a_base = f"{a_base},adelay={delay_ms}|{delay_ms}"

            # Layer transition Whoosh SFX if available
            if sfx_input_idx is not None and idx > 0:
                filter_parts.append(f"{a_base}[a_raw_{idx}]")
                filter_parts.append(f"[{sfx_input_idx}:a]atrim=duration={dur:.3f},volume={self.config.sfx_volume:.2f},asetpts=PTS-STARTPTS[sfx_{idx}]")
                filter_parts.append(f"[a_raw_{idx}][sfx_{idx}]amix=inputs=2:duration=first:dropout_transition=0[a{idx}]")
            else:
                filter_parts.append(f"{a_base}[a{idx}]")

        # Concat stage
        num_shots = len(shot_plans)
        interleaved_concat_inputs: List[str] = []
        for idx in range(num_shots):
            interleaved_concat_inputs.append(f"[v{idx}][a{idx}]")

        concat_in_str = "".join(interleaved_concat_inputs)
        filter_parts.append(
            f"{concat_in_str}concat=n={num_shots}:v=1:a=1[v_stitched][a_stitched]"
        )

        # Voice Clean-up
        if self.config.highpass_audio:
            filter_parts.append("[a_stitched]highpass=f=80[a_voice]")
        else:
            filter_parts.append("[a_stitched]anull[a_voice]")

        # Background Music & Auto-Ducking Pipeline
        if has_bgm and bgm_input_idx is not None:
            bgm_vol = self.config.bgm_volume
            # Trim BGM to exact speech duration and sidechain-compress against speech
            filter_parts.append(
                f"[{bgm_input_idx}:a]atrim=duration={total_speech_dur:.3f},volume={bgm_vol:.3f},asetpts=PTS-STARTPTS[bgm_raw]"
            )
            # Sidechain Ducking: ducks BGM by ~20-22dB when speech is present, swells smoothly during pauses
            filter_parts.append(
                "[bgm_raw][a_voice]sidechaincompress=threshold=0.035:ratio=9:attack=35:release=450[ducked_bgm]"
            )
            filter_parts.append(
                f"[a_voice][ducked_bgm]amix=inputs=2:duration=first:dropout_transition=0,atrim=duration={total_speech_dur:.3f}[a_mixed]"
            )
            final_audio_in = "[a_mixed]"
        else:
            final_audio_in = "[a_voice]"

        # Audio Mastering (EBU R128 Loudness Normalization)
        if self.config.normalize_audio:
            filter_parts.append(f"{final_audio_in}loudnorm=I=-16:TP=-1.5:LRA=11[a_final]")
            final_a_label = "[a_final]"
        else:
            final_a_label = final_audio_in

        current_v_label = "[v_stitched]"

        # CapCut Blend Mode Overlay Engine (blend=mode=screen / addition / overlay)
        if overlay_input_idx is not None and overlay_file:
            blend_mode = getattr(self.config, "overlay_blend_mode", "screen") or "screen"
            opacity = getattr(self.config, "overlay_opacity", 0.85)
            ov_filters, blended_label = OverlayEngine.build_blend_filtergraph(
                base_video_label=current_v_label,
                overlay_input_idx=overlay_input_idx,
                blend_mode=blend_mode,
                opacity=opacity,
                target_width=tw,
                target_height=th,
                output_label="v_blended",
            )
            filter_parts.extend(ov_filters)
            current_v_label = blended_label

        # Apply burned-in Hormozi / MrBeast subtitles on final video (stays crisp over overlays)
        if self.active_ass_path and os.path.isfile(self.active_ass_path):
            escaped_ass = self.active_ass_path.replace("\\", "/").replace(":", "\\:")
            filter_parts.append(f"{current_v_label}ass=filename='{escaped_ass}'[v_captioned]")
            final_v_label = "[v_captioned]"
        else:
            final_v_label = current_v_label

        full_filtergraph = ";\n".join(filter_parts)

        # Prepare FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            *input_args,
            "-filter_complex", full_filtergraph,
            "-map", final_v_label,
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
            "-t", f"{total_speech_dur:.3f}",
            "-metadata", "comment=Directed by OmniCam (https://github.com/librarianistxyz/OmniCam)",
            "-metadata", "author=librarianistxyz",
            "-metadata", "copyright=2026 librarianistxyz",
            "-movflags", "+faststart",
            output_path,
        ]

        if progress_callback:
            progress_callback(0.20, f"Rendering {num_shots} studio angles with auto-ducking BGM...")

        t_start = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode != 0:
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
        temp_broll_files: Optional[Dict[int, str]] = None,
    ) -> str:
        """
        Chunk-based rendering for very large videos with dozens/hundreds of cuts.
        """
        temp_broll_files = temp_broll_files or {}
        temp_dir = tempfile.mkdtemp(prefix="omnicam_chunks_")
        chunk_files: List[str] = []

        tw = self.config.target_width
        th = self.config.target_height
        color_filter = self._get_color_filter()
        total_shots = len(shot_plans)
        total_speech_dur = sum(s.segment.duration for s in shot_plans)

        try:
            for idx, shot in enumerate(shot_plans):
                seg = shot.segment
                dur = max(0.1, seg.duration)
                crop = shot.crop_coords
                cx, cy, cw, ch = crop["x"], crop["y"], crop["w"], crop["h"]

                chunk_file = os.path.join(temp_dir, f"chunk_{idx:04d}.mp4")

                fade_in_d = min(0.015, dur / 4.0)
                fade_out_d = min(0.015, dur / 4.0)
                fade_out_st = max(0.0, dur - fade_out_d)
                a_chain = f"afade=t=in:ss=0:d={fade_in_d:.3f},afade=t=out:st={fade_out_st:.3f}:d={fade_out_d:.3f}"

                if shot.angle == CameraAngle.BROLL and idx in temp_broll_files:
                    v_chain_list = ["setpts=PTS-STARTPTS"]
                    if self.config.transition_flash and idx > 0 and dur > 0.3:
                        v_chain_list.append("fade=t=in:st=0:d=0.06:color=white@0.25")
                    elif dur > 0.4:
                        v_chain_list.append("fade=t=in:st=0:d=0.03")

                    if color_filter:
                        v_chain_list.append(color_filter)

                    hud_f = self._get_hud_filter(shot.angle, tw, th)
                    if hud_f:
                        v_chain_list.append(hud_f)

                    if self.config.letterbox and not self.config.is_portrait:
                        bar_h = int(th * 0.08)
                        v_chain_list.append(f"drawbox=x=0:y=0:w={tw}:h={bar_h}:color=black:t=fill")
                        v_chain_list.append(f"drawbox=x=0:y={th-bar_h}:w={tw}:h={bar_h}:color=black:t=fill")

                    v_chain = ",".join(v_chain_list)
                    cmd = [
                        "ffmpeg",
                        "-y",
                        "-i", temp_broll_files[idx],
                        "-ss", str(seg.start),
                        "-to", str(seg.end),
                        "-i", self.input_video,
                        "-filter_complex", f"[0:v]{v_chain}[v_out];[1:a]{a_chain}[a_out]",
                        "-map", "[v_out]",
                        "-map", "[a_out]",
                        "-c:v", self.config.video_codec,
                        "-pix_fmt", "yuv420p",
                        "-profile:v", "main",
                        "-level:v", "3.1",
                        "-crf", str(self.config.crf),
                        "-preset", self.config.preset,
                        "-c:a", self.config.audio_codec,
                        "-ar", "44100",
                        "-b:a", "192k",
                        "-t", f"{dur:.3f}",
                        chunk_file,
                    ]

                else:
                    if shot.angle == CameraAngle.SLOW_PUSH:
                        zoom_expr = f"(1.0 + 0.20*(t/{dur:.3f}))"
                        crop_f = f"crop=w='(iw/{zoom_expr})':h='(ih/{zoom_expr})':x='{cx + cw/2.0}-(w/2)':y='{cy + ch/2.0}-(h/2)'"
                    else:
                        crop_f = f"crop=w={cw}:h={ch}:x={cx}:y={cy}"

                    scale_f = f"scale={tw}:{th}:flags=lanczos,setsar=1"
                    v_chain_list = [crop_f, scale_f]

                    if self.active_trf_path and os.path.isfile(self.active_trf_path):
                        escaped_trf = self.active_trf_path.replace("\\", "/").replace(":", "\\:")
                        v_chain_list.insert(0, f"vidstabtransform=input='{escaped_trf}':smoothing={self.config.stabilize_smoothing}:optalgo=gauss:interpol=bicubic:zoom=2:crop=black")

                    if self.config.transition_flash and idx > 0 and dur > 0.3:
                        v_chain_list.append("fade=t=in:st=0:d=0.06:color=white@0.25")
                    elif dur > 0.4:
                        v_chain_list.append("fade=t=in:st=0:d=0.03")

                    if color_filter:
                        v_chain_list.append(color_filter)

                    hud_f = self._get_hud_filter(shot.angle, tw, th)
                    if hud_f:
                        v_chain_list.append(hud_f)

                    title_f = self._get_title_overlay(idx, dur, tw, th)
                    if title_f:
                        v_chain_list.append(title_f)

                    if self.config.letterbox and not self.config.is_portrait:
                        bar_h = int(th * 0.08)
                        v_chain_list.append(f"drawbox=x=0:y=0:w={tw}:h={bar_h}:color=black:t=fill")
                        v_chain_list.append(f"drawbox=x=0:y={th-bar_h}:w={tw}:h={bar_h}:color=black:t=fill")

                    v_chain = ",".join(v_chain_list)

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
                        "-t", f"{dur:.3f}",
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

            has_bgm = self.config.bgm_path and os.path.isfile(self.config.bgm_path)

            concat_cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list,
            ]
            if has_bgm:
                concat_cmd += ["-stream_loop", "-1", "-t", f"{total_speech_dur + 1.0:.3f}", "-i", self.config.bgm_path]

            if has_bgm:
                bgm_vol = self.config.bgm_volume
                filtergraph = (
                    "[0:a]highpass=f=80[a_voice]; "
                    f"[1:a]atrim=duration={total_speech_dur:.3f},volume={bgm_vol:.3f},asetpts=PTS-STARTPTS[bgm_raw]; "
                    "[bgm_raw][a_voice]sidechaincompress=threshold=0.035:ratio=9:attack=35:release=450[ducked_bgm]; "
                    f"[a_voice][ducked_bgm]amix=inputs=2:duration=first:dropout_transition=0,atrim=duration={total_speech_dur:.3f},loudnorm=I=-16:TP=-1.5:LRA=11[a_final]"
                )
                concat_cmd += ["-filter_complex", filtergraph, "-map", "0:v", "-map", "[a_final]"]
            else:
                audio_master = []
                if self.config.highpass_audio:
                    audio_master.append("highpass=f=80")
                if self.config.normalize_audio:
                    audio_master.append("loudnorm=I=-16:TP=-1.5:LRA=11")
                if audio_master:
                    concat_cmd += ["-af", ",".join(audio_master)]

            if self.active_ass_path and os.path.isfile(self.active_ass_path):
                escaped_ass = self.active_ass_path.replace("\\", "/").replace(":", "\\:")
                concat_cmd += ["-vf", f"ass=filename='{escaped_ass}'"]

            concat_cmd += [
                "-c:v", self.config.video_codec,
                "-pix_fmt", "yuv420p",
                "-profile:v", "main",
                "-level:v", "3.1",
                "-c:a", self.config.audio_codec,
                "-ar", "44100",
                "-t", f"{total_speech_dur:.3f}",
                "-metadata", "comment=Directed by OmniCam (https://github.com/librarianistxyz/OmniCam)",
                "-metadata", "author=librarianistxyz",
                "-metadata", "copyright=2026 librarianistxyz",
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
