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
from .captions import Transcriber, WordTiming, remap_words_to_edited_timeline, generate_hormozi_ass

__all__ = [
    "AudioAnalyzer",
    "SpeechSegment",
    "VisionTracker",
    "FaceRegion",
    "CameraDirector",
    "ShotPlan",
    "CameraAngle",
    "RenderEngine",
    "Transcriber",
    "WordTiming",
    "remap_words_to_edited_timeline",
    "generate_hormozi_ass",
]

