# ==============================================================================
# OmniCam - Autonomous Multi-Camera Studio Director & NLE Engine
# Copyright (C) 2026 librarianistxyz <https://github.com/librarianistxyz/OmniCam>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
# ==============================================================================

import os
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class OverlayPreset:
    id: str
    title: str
    category: str
    filename: str
    description: str
    recommended_blend: str = "screen"
    default_opacity: float = 0.85
    lavfi_filter: Optional[str] = None
    duration: float = 3.0


# ------------------------------------------------------------------------------
# VIRAL CAPCUT / VN OVERLAY PRESET DEFINITIONS
# ------------------------------------------------------------------------------
OVERLAY_PRESETS: List[OverlayPreset] = [
    OverlayPreset(
        id="light_leak_01",
        title="Golden Flare Leak",
        category="Light Leaks",
        filename="light_leak_01.mp4",
        description="Warm golden flares & amber ambient edge leaks (CapCut golden hour look).",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='190*sin(X/35+T*2.2)*sin(Y/22+T*1.6)+65':"
            "g='110*sin(X/38+T*2.0)*sin(Y/25+T*1.3)+35':"
            "b='15*sin(X/50+T)*sin(Y/30+T)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=28:2"
        ),
    ),
    OverlayPreset(
        id="light_leak_02",
        title="Sunset Crimson Burst",
        category="Light Leaks",
        filename="light_leak_02.mp4",
        description="Vivid sunset magenta and neon crimson pulses for dramatic emotional cuts.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='200*sin(X/30+T*2.5)*sin(Y/25+T*1.8)+55':"
            "g='45*sin(X/45+T*1.5)*sin(Y/30+T*1.1)+15':"
            "b='120*sin(X/35+T*2.1)*sin(Y/28+T*1.4)+30':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=28:2"
        ),
    ),
    OverlayPreset(
        id="film_dust_scratches",
        title="16mm / 35mm Vintage Dust",
        category="Film Textures",
        filename="film_dust_scratches.mp4",
        description="Organic 16mm/35mm film grain, micro-hair scratches & dust specks.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=1280x720:d=2.5:r=24,noise=alls=30:allf=t+u,"
            "curves=all='0/0 0.88/0 0.98/0.85 1/1',"
            "drawbox=x='mod(t*973,1240)':y=0:w=2:h=720:color=white@0.6:t=fill:enable='eq(mod(n,14),0)',"
            "drawbox=x='mod(t*641,1200)':y=0:w=1:h=720:color=white@0.5:t=fill:enable='eq(mod(n,22),0)'"
        ),
    ),
    OverlayPreset(
        id="vhs_static_overlay",
        title="90s Retro VHS Static",
        category="Retro & Cyber",
        filename="vhs_static_overlay.mp4",
        description="Magnetic tape noise, horizontal tracking jitter & nostalgic CRT static.",
        recommended_blend="screen",
        default_opacity=0.70,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=640x360:d=2.5:r=24,noise=alls=15:allf=t+u,"
            "drawgrid=w=640:h=4:color=white@0.08:t=1,"
            "drawbox=x=0:y='mod(t*180,360)':w=640:h=18:color=white@0.22:t=fill,"
            "curves=all='0/0 0.7/0 0.95/0.8 1/1',scale=1280:720:flags=neighbor"
        ),
    ),
    OverlayPreset(
        id="prism_bokeh",
        title="Dreamy Prism Bokeh",
        category="Optical & Lens",
        filename="prism_bokeh.mp4",
        description="Floating hexagonal light discs, optical refraction & dreamy bokeh flare.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=320x180:d=3:r=24,"
            "geq=r='140*pow(cos(X/25+T*1.4)*sin(Y/20-T),4)':"
            "g='120*pow(cos(X/28+T*1.6+1)*sin(Y/22-T*1.2),4)':"
            "b='160*pow(cos(X/22+T*1.2+2)*sin(Y/18-T*0.8),4)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=15:2"
        ),
    ),
    OverlayPreset(
        id="film_burn_01",
        title="Fiery Film Burn",
        category="Film Textures",
        filename="film_burn_01.mp4",
        description="High-intensity amber & orange film burn edge burst with halation.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=160x90:d=2.5:r=24,"
            "geq=r='230*pow(sin(X/40+T*3),2)':g='90*pow(sin(X/40+T*3),3)':b='10*pow(sin(X/40+T*3),4)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=30:2"
        ),
    ),
    OverlayPreset(
        id="film_burn_02",
        title="Edge Halation Burn",
        category="Film Textures",
        filename="film_burn_02.mp4",
        description="Deep crimson gate halation burn with organic edge flicker.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=160x90:d=2.5:r=24,"
            "geq=r='240*pow(cos(Y/30+T*2.8),2)':g='160*pow(cos(Y/30+T*2.8),2)':b='30*pow(cos(Y/30+T*2.8),4)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=26:2"
        ),
    ),
    OverlayPreset(
        id="retro_crt_scanlines",
        title="Cyber CRT Scanlines",
        category="Retro & Cyber",
        filename="retro_crt_scanlines.mp4",
        description="Analog broadcast television CRT lines and horizontal beam sweeps.",
        recommended_blend="screen",
        default_opacity=0.65,
        duration=2.0,
        lavfi_filter=(
            "color=c=black:s=1280x720:d=2:r=24,"
            "drawgrid=w=1280:h=3:color=white@0.18:t=1,"
            "drawbox=x=0:y='mod(t*220,720)':w=1280:h=32:color=white@0.12:t=fill"
        ),
    ),
    OverlayPreset(
        id="lens_flare_anamorphic",
        title="Anamorphic Flare Streak",
        category="Optical & Lens",
        filename="lens_flare_anamorphic.mp4",
        description="Cinematic cyan & electric blue horizontal anamorphic lens flare.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=320x180:d=3:r=24,"
            "drawbox=x=0:y='88+sin(t*3)*15':w=320:h=4:color=0x00E5FF@0.85:t=fill,"
            "drawbox=x='150+cos(t*2)*80':y='85+sin(t*3)*15':w=20:h=10:color=white@0.9:t=fill,"
            "scale=1280:720:flags=bicubic,boxblur=22:2"
        ),
    ),
    OverlayPreset(
        id="golden_particles",
        title="Floating Golden Particles",
        category="Optical & Lens",
        filename="golden_particles.mp4",
        description="Warm floating dust motes and soft bokeh embers for luxury/podcast aesthetic.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=10:allf=t+u,"
            "curves=all='0/0 0.94/0 0.99/0.9 1/1',"
            "colorbalance=rs=0.4:gs=0.2:bs=-0.3,boxblur=2:1,scale=1280:720:flags=bicubic"
        ),
    ),
    OverlayPreset(
        id="glitch_digital",
        title="Cyber Digital Glitch",
        category="Retro & Cyber",
        filename="glitch_digital.mp4",
        description="Chromatic RGB displacement blocks and futuristic electronic glitch slices.",
        recommended_blend="screen",
        default_opacity=0.70,
        duration=2.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=2:r=24,"
            "drawbox=x='mod(t*750,480)':y='mod(t*530,300)':w='160':h='20':color=cyan@0.65:t=fill:enable='eq(mod(n,9),0)',"
            "drawbox=x='mod(t*620,440)':y='mod(t*410,320)':w='200':h='14':color=red@0.65:t=fill:enable='eq(mod(n,9),0)',"
            "scale=1280:720:flags=neighbor"
        ),
    ),
    OverlayPreset(
        id="vintage_super8",
        title="Super 8 Projector",
        category="Film Textures",
        filename="vintage_super8.mp4",
        description="Super 8mm vintage projector gate flicker, corner vignetting & organic jitter.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=1280x720:d=2.5:r=24,noise=alls=18:allf=t+u,"
            "curves=all='0/0 0.85/0 0.97/0.7 1/1',"
            "vignette='PI/4 + 0.05*sin(t*18)',scale=1280:720:flags=lanczos"
        ),
    ),
]


class OverlayEngine:
    """
    Manages discovering, generating, and blending video loop overlay textures.
    Supports standard blend modes: 'screen', 'addition', 'overlay', 'lighten', 'softlight'.
    """

    SUPPORTED_BLEND_MODES = [
        "screen",
        "addition",
        "overlay",
        "lighten",
        "softlight",
        "dodge",
        "multiply",
    ]

    def __init__(self, assets_dir: str = "assets/overlays"):
        self.assets_dir = os.path.abspath(assets_dir)
        os.makedirs(self.assets_dir, exist_ok=True)

    @classmethod
    def get_presets(cls) -> List[OverlayPreset]:
        return OVERLAY_PRESETS

    @classmethod
    def get_preset_by_id(cls, preset_id: str) -> Optional[OverlayPreset]:
        for p in OVERLAY_PRESETS:
            if p.id == preset_id or p.filename == preset_id:
                return p
        return None

    def get_overlay_path(self, identifier: str) -> Optional[str]:
        """Resolves preset id, filename, or direct file path to an existing overlay video."""
        if not identifier:
            return None

        # Check if it's already an existing file path
        if os.path.isfile(identifier):
            return os.path.abspath(identifier)

        # Check in assets/overlays
        candidate = os.path.join(self.assets_dir, identifier)
        if os.path.isfile(candidate):
            return candidate

        # Check with .mp4 suffix
        if not identifier.endswith(".mp4"):
            candidate_mp4 = os.path.join(self.assets_dir, f"{identifier}.mp4")
            if os.path.isfile(candidate_mp4):
                return candidate_mp4

        # Check preset filename
        preset = self.get_preset_by_id(identifier)
        if preset:
            p_path = os.path.join(self.assets_dir, preset.filename)
            if os.path.isfile(p_path):
                return p_path

            # Auto-synthesize on demand if it's a known preset
            self.generate_preset(preset, p_path)
            if os.path.isfile(p_path):
                return p_path

        return None

    def list_available_overlays(self) -> List[Dict]:
        """Lists all built-in and user-provided overlay video loops."""
        overlays = []

        # Built-in presets
        for preset in OVERLAY_PRESETS:
            file_path = os.path.join(self.assets_dir, preset.filename)
            exists = os.path.isfile(file_path)
            overlays.append({
                "id": preset.id,
                "title": preset.title,
                "category": preset.category,
                "filename": preset.filename,
                "description": preset.description,
                "recommended_blend": preset.recommended_blend,
                "default_opacity": preset.default_opacity,
                "duration": preset.duration,
                "available": exists,
                "path": file_path if exists else None,
                "is_custom": False,
            })

        # Discover any custom MP4 / MOV videos dropped into assets/overlays
        if os.path.isdir(self.assets_dir):
            known_filenames = {p.filename for p in OVERLAY_PRESETS}
            for entry in sorted(os.listdir(self.assets_dir)):
                if entry in known_filenames:
                    continue
                ext = os.path.splitext(entry)[1].lower()
                if ext in (".mp4", ".mov", ".mkv", ".webm"):
                    full_p = os.path.join(self.assets_dir, entry)
                    title_name = os.path.splitext(entry)[0].replace("_", " ").title()
                    overlays.append({
                        "id": entry,
                        "title": f"Custom: {title_name}",
                        "category": "User Uploads",
                        "filename": entry,
                        "description": f"Custom overlay texture ({entry})",
                        "recommended_blend": "screen",
                        "default_opacity": 0.85,
                        "duration": 0.0,
                        "available": True,
                        "path": full_p,
                        "is_custom": True,
                    })

        return overlays

    def generate_preset(self, preset: OverlayPreset, output_path: str) -> bool:
        """Synthesizes a lightweight looping overlay video texture using FFmpeg lavfi."""
        if not preset.lavfi_filter:
            return False

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "lavfi",
            "-i", preset.lavfi_filter,
            "-t", f"{preset.duration:.2f}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return res.returncode == 0
        except Exception as ex:
            print(f"  [!] Failed to synthesize overlay {preset.filename}: {ex}")
            return False

    def ensure_all_presets(self, progress_callback=None) -> int:
        """Ensures all standard overlay textures exist in assets/overlays."""
        count = 0
        total = len(OVERLAY_PRESETS)
        for i, p in enumerate(OVERLAY_PRESETS):
            out_file = os.path.join(self.assets_dir, p.filename)
            if not os.path.isfile(out_file):
                if progress_callback:
                    progress_callback(i / total, f"Generating overlay texture '{p.title}'...")
                ok = self.generate_preset(p, out_file)
                if ok:
                    count += 1
            else:
                count += 1
        return count

    @classmethod
    def build_blend_filtergraph(
        cls,
        base_video_label: str,
        overlay_input_idx: int,
        blend_mode: str = "screen",
        opacity: float = 0.85,
        target_width: int = 1920,
        target_height: int = 1080,
        output_label: str = "v_blended",
    ) -> Tuple[List[str], str]:
        """
        Builds FFmpeg filter complex fragment to scale/crop the looping overlay video
        and blend it over the main video with the specified blend mode and opacity.
        """
        mode = blend_mode.lower()
        if mode not in cls.SUPPORTED_BLEND_MODES:
            mode = "screen"

        opacity = max(0.0, min(1.0, float(opacity)))

        filter_lines = [
            # Scale and crop looping overlay to perfectly cover target aspect ratio
            f"[{overlay_input_idx}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
            f"crop={target_width}:{target_height},setsar=1[v_ov_scaled]",
            # Blend onto base video
            f"{base_video_label}[v_ov_scaled]blend=all_mode='{mode}':all_opacity={opacity:.2f}[{output_label}]",
        ]
        return filter_lines, f"[{output_label}]"
