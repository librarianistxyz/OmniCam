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
Vision Tracker & Subject Framing for OmniCam
Tracks speaker presence, stabilizes headroom, and calculates crop coordinates.
Handles native portrait (9:16) and landscape (16:9) orientations and rotation tags.
"""

from dataclasses import dataclass
import json
import subprocess
from typing import Dict, List, Optional, Tuple

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


@dataclass
class FaceRegion:
    norm_x: float  # Center X normalized (0.0 -> 1.0)
    norm_y: float  # Center Y normalized (0.0 -> 1.0)
    norm_w: float  # Width normalized (0.0 -> 1.0)
    norm_h: float  # Height normalized (0.0 -> 1.0)
    confidence: float = 1.0


@dataclass
class VideoMetadata:
    width: int
    height: int
    display_width: int
    display_height: int
    fps: float
    duration: float
    is_portrait: bool


class VisionTracker:
    """
    Tracks talking-head positioning to compute cinematic multi-camera crop windows.
    Automatically adapts to horizontal (16:9) or vertical (9:16) smartphone recordings.
    """

    def __init__(self, video_path: str):
        self.video_path = video_path
        self.metadata = self._probe_video(video_path)
        self.face_cascade = None
        if OPENCV_AVAILABLE:
            try:
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception:
                self.face_cascade = None

    @staticmethod
    def _probe_video(video_path: str) -> VideoMetadata:
        """Extracts resolution, orientation, frame rate, and duration via ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration:stream_tags=rotate:stream_side_data=rotation",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)

        stream = data["streams"][0]
        raw_w = int(stream["width"])
        raw_h = int(stream["height"])

        # Detect orientation rotation metadata common on smartphones
        rotation = 0
        if "tags" in stream and "rotate" in stream["tags"]:
            try:
                rotation = int(float(stream["tags"]["rotate"]))
            except (ValueError, TypeError):
                pass
        if "side_data_list" in stream:
            for sd in stream["side_data_list"]:
                if "rotation" in sd:
                    try:
                        rotation = int(float(sd["rotation"]))
                    except (ValueError, TypeError):
                        pass

        if abs(rotation) in (90, 270):
            disp_w = raw_h
            disp_h = raw_w
        else:
            disp_w = raw_w
            disp_h = raw_h

        is_portrait = disp_h > disp_w

        # Parse frame rate
        fps_str = stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 30.0
        else:
            fps = float(fps_str)

        # Parse duration
        duration = 0.0
        if "duration" in stream and stream["duration"] != "N/A":
            duration = float(stream["duration"])
        elif "format" in data and "duration" in data["format"]:
            duration = float(data["format"]["duration"])

        return VideoMetadata(
            width=raw_w,
            height=raw_h,
            display_width=disp_w,
            display_height=disp_h,
            fps=fps,
            duration=duration,
            is_portrait=is_portrait,
        )

    def sample_face_region(self, timestamp: float) -> FaceRegion:
        """
        Samples a video frame at a given timestamp to detect the speaker's face.
        If OpenCV is missing or face is not detected, returns the golden-ratio default.
        """
        default_face = FaceRegion(norm_x=0.50, norm_y=0.38, norm_w=0.25, norm_h=0.30, confidence=0.5)

        if not OPENCV_AVAILABLE or self.face_cascade is None:
            return default_face

        try:
            cap = cv2.VideoCapture(self.video_path)
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
            success, frame = cap.read()
            cap.release()

            if not success or frame is None:
                return default_face

            h, w, _ = frame.shape
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=4,
                minSize=(int(w * 0.10), int(h * 0.10)),
            )

            if len(faces) == 0:
                return default_face

            best_face = max(faces, key=lambda f: f[2] * f[3])
            fx, fy, fw, fh = best_face

            cx = (fx + fw / 2.0) / w
            cy = (fy + fh / 2.0) / h
            nw = fw / w
            nh = fh / h

            return FaceRegion(norm_x=cx, norm_y=cy, norm_w=nw, norm_h=nh, confidence=0.95)
        except Exception:
            return default_face

    def compute_crop_coordinates(
        self,
        angle_name: str,
        face: FaceRegion,
        zoom_factor: float = 1.75,
    ) -> Dict[str, int]:
        """
        Computes the pixel crop bounding box (x, y, w, h) for a specified camera angle.
        Guarantees that the crop remains strictly inside the source canvas and preserves
        the video's native aspect ratio (landscape 16:9 or vertical 9:16).
        """
        src_w = self.metadata.width
        src_h = self.metadata.height

        # Determine target aspect ratio based on video orientation
        if self.metadata.is_portrait:
            out_aspect_ratio = src_w / src_h
        else:
            out_aspect_ratio = 16.0 / 9.0

        # Angle 1: Master Wide Shot (Uses full frame or matching aspect ratio)
        if angle_name == "WIDE":
            src_aspect = src_w / src_h
            if src_aspect >= out_aspect_ratio:
                crop_h = src_h
                crop_w = int(crop_h * out_aspect_ratio)
                crop_x = (src_w - crop_w) // 2
                crop_y = 0
            else:
                crop_w = src_w
                crop_h = int(crop_w / out_aspect_ratio)
                crop_x = 0
                crop_y = (src_h - crop_h) // 2
            return {
                "x": crop_x - (crop_x % 2),
                "y": crop_y - (crop_y % 2),
                "w": crop_w - (crop_w % 2),
                "h": crop_h - (crop_h % 2),
            }

        # Cropped Angles: Close-up and Rule-of-Thirds
        crop_w = int(src_w / zoom_factor)
        crop_h = int(crop_w / out_aspect_ratio)

        if crop_h > src_h:
            crop_h = int(src_h / zoom_factor)
            crop_w = int(crop_h * out_aspect_ratio)

        px_face_x = face.norm_x * src_w
        px_face_y = face.norm_y * src_h

        # Framing coordinates
        if angle_name == "CLOSEUP":
            # Center face horizontally, place eyes at ~35% headroom
            target_x = px_face_x - (crop_w / 2.0)
            target_y = px_face_y - (crop_h * 0.35)

        elif angle_name == "THIRD_LEFT":
            # Visibly offset subject to the left (25% line) with room on the right
            target_x = px_face_x - (crop_w * 0.25)
            target_y = px_face_y - (crop_h * 0.35)

        elif angle_name == "THIRD_RIGHT":
            # Visibly offset subject to the right (75% line) with room on the left
            target_x = px_face_x - (crop_w * 0.75)
            target_y = px_face_y - (crop_h * 0.35)

        elif angle_name in ("SLOW_PUSH", "SLOW_PULL"):
            target_x = px_face_x - (crop_w / 2.0)
            target_y = px_face_y - (crop_h * 0.38)

        else:
            target_x = (src_w - crop_w) / 2.0
            target_y = (src_h - crop_h) / 2.0

        # Boundary clamping to prevent clipping out of canvas
        clamped_x = max(0, min(src_w - crop_w, int(target_x)))
        clamped_y = max(0, min(src_h - crop_h, int(target_y)))

        # Ensure even dimensions (required by h264/yuv420p)
        clamped_w = crop_w - (crop_w % 2)
        clamped_h = crop_h - (crop_h % 2)
        clamped_x = clamped_x - (clamped_x % 2)
        clamped_y = clamped_y - (clamped_y % 2)

        return {"x": clamped_x, "y": clamped_y, "w": clamped_w, "h": clamped_h}
