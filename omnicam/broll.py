"""
Automatic B-Roll Cutaway Manager for OmniCam
Scans, prepares, and dynamically inserts secondary footage and photos during extended speech.
"""

import glob
import os
import random
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional


SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class BRollAsset:
    path: str
    is_video: bool
    name: str


class BRollManager:
    """
    Discovers, curates, and normalizes B-roll media (videos and still photos)
    for seamless cutaways during extended monologue.
    """

    def __init__(self, broll_dir: Optional[str] = None):
        self.broll_dir = os.path.abspath(broll_dir) if broll_dir else None
        self.assets: List[BRollAsset] = []
        self._current_index: int = 0
        if self.broll_dir:
            self.discover_assets()

    def discover_assets(self) -> List[BRollAsset]:
        """Scans the directory for valid video and image assets."""
        self.assets = []
        if not self.broll_dir or not os.path.isdir(self.broll_dir):
            return self.assets

        all_files = sorted(os.listdir(self.broll_dir))
        for filename in all_files:
            file_path = os.path.join(self.broll_dir, filename)
            if not os.path.isfile(file_path):
                continue

            _, ext = os.path.splitext(filename.lower())
            if ext in SUPPORTED_VIDEO_EXTS:
                self.assets.append(BRollAsset(path=file_path, is_video=True, name=filename))
            elif ext in SUPPORTED_IMAGE_EXTS:
                self.assets.append(BRollAsset(path=file_path, is_video=False, name=filename))

        # Shuffle once for diverse selection while retaining deterministic cycling
        random.seed(42)
        random.shuffle(self.assets)
        return self.assets

    def has_assets(self) -> bool:
        return len(self.assets) > 0

    def get_next_asset(self) -> Optional[BRollAsset]:
        """Returns the next B-roll asset in a round-robin rotation."""
        if not self.assets:
            return None
        asset = self.assets[self._current_index % len(self.assets)]
        self._current_index += 1
        return asset

    @staticmethod
    def prepare_clip(
        asset: BRollAsset,
        duration: float,
        target_width: int,
        target_height: int,
        output_path: str,
    ) -> str:
        """
        Normalizes a video clip or photo into an exact-duration video snippet
        matching target resolution, framerate, and aspect ratio without audio.
        """
        dur_str = f"{max(0.2, duration):.3f}"
        tw = target_width
        th = target_height

        if asset.is_video:
            # Video: scale to cover, center-crop, loop if shorter than duration
            filter_chain = (
                f"scale=w={tw}:h={th}:force_original_aspect_ratio=increase,"
                f"crop={tw}:{th},setsar=1"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-stream_loop", "-1",
                "-t", dur_str,
                "-i", asset.path,
                "-vf", filter_chain,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                "-an",
                output_path,
            ]
        else:
            # Still photo: scale 10% larger and apply gentle lateral Ken Burns drift
            filter_chain = (
                f"scale=w={int(tw * 1.10)}:h={int(th * 1.10)}:force_original_aspect_ratio=increase,"
                f"crop=w={tw}:h={th}:x='(iw-ow)*(t/{dur_str})':y='(ih-oh)/2',setsar=1"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-loop", "1",
                "-t", dur_str,
                "-i", asset.path,
                "-vf", filter_chain,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                "-an",
                output_path,
            ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to prepare B-roll clip '{asset.name}': {res.stderr[-400:]}")

        return output_path
