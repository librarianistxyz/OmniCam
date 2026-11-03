"""
OmniCam - AI Virtual Multi-Camera Director
Transform a single handheld smartphone video into an automated multi-camera studio cut.
"""

__version__ = "1.0.0"
__author__ = "OmniCam Engine"

from .audio_analyzer import AudioAnalyzer, SpeechSegment
from .vision_tracker import VisionTracker, FaceRegion
from .director import CameraDirector, ShotPlan, CameraAngle
from .render_engine import RenderEngine

__all__ = [
    "AudioAnalyzer",
    "SpeechSegment",
    "VisionTracker",
    "FaceRegion",
    "CameraDirector",
    "ShotPlan",
    "CameraAngle",
    "RenderEngine",
]

