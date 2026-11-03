"""
AI Camera Director for OmniCam
Analyzes rhythm, speech duration, and cadence to orchestrate cinematic shot selection.
"""

from dataclasses import dataclass
from enum import Enum
import random
from typing import Dict, List, Optional

from .audio_analyzer import SpeechSegment
from .vision_tracker import FaceRegion, VisionTracker


class CameraAngle(str, Enum):
    WIDE = "WIDE"
    CLOSEUP = "CLOSEUP"
    THIRD_LEFT = "THIRD_LEFT"
    THIRD_RIGHT = "THIRD_RIGHT"
    SLOW_PUSH = "SLOW_PUSH"


@dataclass
class ShotPlan:
    index: int
    segment: SpeechSegment
    angle: CameraAngle
    crop_coords: Dict[str, int]
    zoom_factor: float
    description: str


class CameraDirector:
    """
    Intelligent shot planner that converts a stream of speech segments into
    a multi-camera studio production without jump cuts.
    """

    def __init__(
        self,
        tracker: VisionTracker,
        pacing_style: str = "dynamic",
        zoom_factor: float = 1.75,
        target_resolution: str = "720p",
    ):
        self.tracker = tracker
        self.pacing_style = pacing_style.lower()
        self.zoom_factor = zoom_factor
        self.target_resolution = target_resolution

    def plan_production(self, segments: List[SpeechSegment]) -> List[ShotPlan]:
        """
        Plans shot choices for all speech segments following cinematic directing rules.
        """
        if not segments:
            return []

        plans: List[ShotPlan] = []
        last_angle: Optional[CameraAngle] = None

        for i, seg in enumerate(segments):
            # Sample speaker's position at the midpoint of this speech segment
            mid_time = (seg.start + seg.end) / 2.0
            face = self.tracker.sample_face_region(mid_time)

            # Choose angle based on pacing style, segment duration, and history
            angle = self._select_angle(
                seg_idx=i,
                duration=seg.duration,
                silence_before=seg.silence_before,
                last_angle=last_angle,
                total_segments=len(segments),
            )

            # Compute pixel crop coordinates
            crop = self.tracker.compute_crop_coordinates(
                angle_name=angle.value,
                face=face,
                zoom_factor=self.zoom_factor,
            )

            # Generate director note
            desc = self._generate_description(angle, seg.duration)

            plans.append(
                ShotPlan(
                    index=i,
                    segment=seg,
                    angle=angle,
                    crop_coords=crop,
                    zoom_factor=self.zoom_factor,
                    description=desc,
                )
            )
            last_angle = angle

        return plans

    def _select_angle(
        self,
        seg_idx: int,
        duration: float,
        silence_before: float,
        last_angle: Optional[CameraAngle],
        total_segments: int,
    ) -> CameraAngle:
        """
        Selects the next camera angle according to director heuristics:
        1. Inviolable Rule: Never repeat the immediate previous angle (no jump cuts).
        2. Hook Opening: First shot grabs attention.
        3. Cadence: Long takes get dynamic pushes or wide; short punchy takes get close-up.
        """
        # Hook Shot: Open strong
        if seg_idx == 0:
            if self.pacing_style in ("dramatic", "dynamic"):
                return CameraAngle.CLOSEUP
            return CameraAngle.WIDE

        # Concluding Shot: Return to Master Wide
        if seg_idx == total_segments - 1 and last_angle != CameraAngle.WIDE:
            return CameraAngle.WIDE

        # Eligible angles excluding the last angle
        available = [a for a in CameraAngle if a != last_angle]

        # Duration-dependent selection
        if duration > 4.5:
            # Extended thought: Slow push or wide to avoid claustrophobia
            preferred = [CameraAngle.SLOW_PUSH, CameraAngle.WIDE]
            valid = [a for a in preferred if a in available]
            if valid:
                return valid[0]

        elif duration < 1.8:
            # Short punchy reaction / one-liner: Close-up is high impact
            if CameraAngle.CLOSEUP in available:
                return CameraAngle.CLOSEUP

        # Medium duration (1.8s - 4.5s): Style-guided rotation
        if self.pacing_style == "podcast":
            # Podcast prefers Wide and alternating Thirds
            cycle = [CameraAngle.WIDE, CameraAngle.THIRD_RIGHT, CameraAngle.WIDE, CameraAngle.THIRD_LEFT]
            idx = seg_idx % len(cycle)
            candidate = cycle[idx]
            if candidate != last_angle:
                return candidate

        elif self.pacing_style == "documentary":
            # Documentary leans heavily on Wide and Slow Push
            if last_angle == CameraAngle.WIDE and CameraAngle.SLOW_PUSH in available:
                return CameraAngle.SLOW_PUSH
            if CameraAngle.WIDE in available:
                return CameraAngle.WIDE

        # Dynamic / Default Studio Style:
        # Balanced distribution: WIDE -> CLOSEUP -> THIRD_RIGHT -> WIDE -> THIRD_LEFT -> CLOSEUP
        studio_cycle = [
            CameraAngle.WIDE,
            CameraAngle.CLOSEUP,
            CameraAngle.THIRD_RIGHT,
            CameraAngle.WIDE,
            CameraAngle.THIRD_LEFT,
            CameraAngle.SLOW_PUSH,
        ]
        candidate = studio_cycle[seg_idx % len(studio_cycle)]
        if candidate in available:
            return candidate

        return available[0]

    @staticmethod
    def _generate_description(angle: CameraAngle, duration: float) -> str:
        if angle == CameraAngle.WIDE:
            return f"Master Wide Shot (Full Scene Context, {duration:.1f}s)"
        elif angle == CameraAngle.CLOSEUP:
            return f"Tight Close-Up Punch-In (High Emotional Emphasis, {duration:.1f}s)"
        elif angle == CameraAngle.THIRD_LEFT:
            return f"Rule-of-Thirds Left Framing (Conversational Depth, {duration:.1f}s)"
        elif angle == CameraAngle.THIRD_RIGHT:
            return f"Rule-of-Thirds Right Framing (Gaze Balance, {duration:.1f}s)"
        elif angle == CameraAngle.SLOW_PUSH:
            return f"Cinematic Slow Push-In (Continuous Focus, {duration:.1f}s)"
        return f"{angle.value} Shot ({duration:.1f}s)"

