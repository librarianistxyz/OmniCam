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
from .stabilizer import VideoStabilizer, is_vidstab_supported
from .broll import BRollManager, BRollAsset
from .filler_remover import (
    DEFAULT_FILLER_WORDS,
    detect_lexical_fillers,
    detect_acoustic_hesitations,
    remove_filler_intervals,
)
from .web import launch_web_server

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
    "VideoStabilizer",
    "is_vidstab_supported",
    "BRollManager",
    "BRollAsset",
    "DEFAULT_FILLER_WORDS",
    "detect_lexical_fillers",
    "detect_acoustic_hesitations",
    "remove_filler_intervals",
    "launch_web_server",
]

