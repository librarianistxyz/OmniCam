"""
Vision Tracker & Subject Framing for OmniCam
Tracks speaker presence, stabilizes headroom, and calculates crop coordinates.
Operates with OpenCV face detection when available, or elegant golden-ratio heuristics.
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
    fps: float
    duration: float


class VisionTracker:
    """
    Tracks talking-head positioning to compute cinematic multi-camera crop windows.
    Zero-hard-dependency design: gracefully degrades to golden-ratio heuristics
    if OpenCV is not installed on Termux.
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
        """Extracts resolution, frame rate, and duration via ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)

        stream = data["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])

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

        return VideoMetadata(width=width, height=height, fps=fps, duration=duration)

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
            # Detect faces with sensible min/max sizes
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=4,
                minSize=(int(w * 0.10), int(h * 0.10)),
            )

            if len(faces) == 0:
                return default_face

            # Pick the largest face (the speaker in foreground)
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
        zoom_factor: float = 1.7,
        out_aspect_ratio: float = 16.0 / 9.0,
    ) -> Dict[str, int]:
        """
        Computes the pixel crop bounding box (x, y, w, h) for a specified camera angle.
        Guarantees that the crop remains fully inside the source canvas.
        """
        src_w = self.metadata.width
        src_h = self.metadata.height

        # Wide Shot: Uses entire source canvas
        if angle_name == "WIDE":
            # Match target aspect ratio within source canvas
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
            return {"x": crop_x, "y": crop_y, "w": crop_w, "h": crop_h}

        # For cropped angles (Close-up, Thirds):
        # Calculate zoomed crop dimensions preserving target aspect ratio
        crop_w = int(src_w / zoom_factor)
        crop_h = int(crop_w / out_aspect_ratio)

        # Ensure crop height doesn't exceed source height
        if crop_h > src_h:
            crop_h = src_h
            crop_w = int(crop_h * out_aspect_ratio)

        # Pixel face center
        px_face_x = face.norm_x * src_w
        px_face_y = face.norm_y * src_h

        # Framing offsets depending on camera angle
        if angle_name == "CLOSEUP":
            # Center face horizontally, place eyes at ~1/3 from top of cropped frame
            target_x = px_face_x - (crop_w / 2.0)
            target_y = px_face_y - (crop_h * 0.35)
        elif angle_name == "THIRD_LEFT":
            # Subject framed on left third (1/3), looking right
            target_x = px_face_x - (crop_w * 0.33)
            target_y = px_face_y - (crop_h * 0.35)
        elif angle_name == "THIRD_RIGHT":
            # Subject framed on right third (2/3), looking left
            target_x = px_face_x - (crop_w * 0.67)
            target_y = px_face_y - (crop_h * 0.35)
        elif angle_name in ("SLOW_PUSH", "SLOW_PULL"):
            # Centered for dynamic zoom
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

