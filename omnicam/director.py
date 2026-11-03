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
from .broll import BRollManager, BRollAsset


class CameraAngle(str, Enum):
    WIDE = "WIDE"
    CLOSEUP = "CLOSEUP"
    THIRD_LEFT = "THIRD_LEFT"
    THIRD_RIGHT = "THIRD_RIGHT"
    SLOW_PUSH = "SLOW_PUSH"
    BROLL = "BROLL"


@dataclass
class ShotPlan:
    index: int
    segment: SpeechSegment
    angle: CameraAngle
    crop_coords: Dict[str, int]
    zoom_factor: float
    description: str
    clip_index: int = 0
    clip_path: Optional[str] = None
    is_freeze_frame: bool = False
    freeze_duration: float = 0.0
    transition: str = "flash"
    broll_path: Optional[str] = None
    broll_name: Optional[str] = None


class CameraDirector:
    """
    Intelligent shot planner that converts a stream of speech segments into
    a multi-camera studio production without jump cuts, with automatic B-roll cutaways.
    """

    def __init__(
        self,
        tracker: VisionTracker,
        pacing_style: str = "dynamic",
        zoom_factor: float = 1.75,
        target_resolution: str = "720p",
        broll_manager: Optional[BRollManager] = None,
        min_broll_speech_dur: float = 4.0,
        broll_cutaway_dur: float = 2.5,
        enable_freeze_frames: bool = True,
        freeze_duration: float = 0.6,
        transition_style: str = "flash",
        clip_index: int = 0,
        clip_path: Optional[str] = None,
    ):
        self.tracker = tracker
        self.pacing_style = pacing_style.lower()
        self.zoom_factor = zoom_factor
        self.target_resolution = target_resolution
        self.broll_manager = broll_manager
        self.min_broll_speech_dur = min_broll_speech_dur
        self.broll_cutaway_dur = broll_cutaway_dur
        self.enable_freeze_frames = enable_freeze_frames
        self.freeze_duration = freeze_duration
        self.transition_style = transition_style
        self.clip_index = clip_index
        self.clip_path = clip_path

    def plan_production(self, segments: List[SpeechSegment]) -> List[ShotPlan]:
        """
        Plans shot choices for all speech segments following cinematic directing rules,
        inserting B-roll cutaways during long continuous takes.
        """
        if not segments:
            return []

        plans: List[ShotPlan] = []
        last_angle: Optional[CameraAngle] = None
        shot_counter = 0

        for i, seg in enumerate(segments):
            # Check if this segment qualifies for B-roll cutaway
            can_broll = (
                self.broll_manager is not None
                and self.broll_manager.has_assets()
                and seg.duration >= self.min_broll_speech_dur
            )

            if can_broll:
                asset = self.broll_manager.get_next_asset()
                lead_dur = min(1.5, max(1.0, seg.duration * 0.25))
                broll_dur = min(self.broll_cutaway_dur, seg.duration - lead_dur - 1.0)
                tail_dur = seg.duration - lead_dur - broll_dur

                # Part 1: Lead-in on speaker
                sub1 = SpeechSegment(
                    index=shot_counter,
                    start=seg.start,
                    end=seg.start + lead_dur,
                    duration=lead_dur,
                    silence_before=seg.silence_before,
                )
                face1 = self.tracker.sample_face_region((sub1.start + sub1.end) / 2.0)
                angle1 = self._select_angle(
                    seg_idx=shot_counter,
                    duration=lead_dur,
                    silence_before=sub1.silence_before,
                    last_angle=last_angle,
                    total_segments=len(segments),
                )
                crop1 = self.tracker.compute_crop_coordinates(angle1.value, face1, self.zoom_factor)
                desc1 = self._generate_description(angle1, lead_dur)
                plans.append(ShotPlan(shot_counter, sub1, angle1, crop1, self.zoom_factor, desc1))
                last_angle = angle1
                shot_counter += 1

                # Part 2: B-Roll Cutaway
                sub2 = SpeechSegment(
                    index=shot_counter,
                    start=seg.start + lead_dur,
                    end=seg.start + lead_dur + broll_dur,
                    duration=broll_dur,
                    silence_before=0.0,
                )
                crop2 = {"x": 0, "y": 0, "w": self.tracker.metadata.width, "h": self.tracker.metadata.height}
                desc2 = f"B-Roll Cutaway: {asset.name} ({broll_dur:.1f}s)"
                plans.append(
                    ShotPlan(
                        index=shot_counter,
                        segment=sub2,
                        angle=CameraAngle.BROLL,
                        crop_coords=crop2,
                        zoom_factor=1.0,
                        description=desc2,
                        broll_path=asset.path,
                        broll_name=asset.name,
                    )
                )
                last_angle = CameraAngle.BROLL
                shot_counter += 1

                # Part 3: Return to speaker on contrasting angle
                sub3 = SpeechSegment(
                    index=shot_counter,
                    start=seg.start + lead_dur + broll_dur,
                    end=seg.end,
                    duration=tail_dur,
                    silence_before=0.0,
                )
                face3 = self.tracker.sample_face_region((sub3.start + sub3.end) / 2.0)
                angle3 = self._select_angle(
                    seg_idx=shot_counter,
                    duration=tail_dur,
                    silence_before=0.0,
                    last_angle=angle1,
                    total_segments=len(segments),
                )
                crop3 = self.tracker.compute_crop_coordinates(angle3.value, face3, self.zoom_factor)
                desc3 = self._generate_description(angle3, tail_dur)
                plans.append(ShotPlan(shot_counter, sub3, angle3, crop3, self.zoom_factor, desc3))
                last_angle = angle3
                shot_counter += 1

            else:
                # Sample speaker's position at the midpoint of this speech segment
                mid_time = (seg.start + seg.end) / 2.0
                face = self.tracker.sample_face_region(mid_time)

                # Choose angle based on pacing style, segment duration, and history
                angle = self._select_angle(
                    seg_idx=shot_counter,
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

                # Determine CapCut dramatic freeze frame hook
                is_freeze = (
                    self.enable_freeze_frames
                    and seg.silence_before >= 0.70
                    and seg.duration >= 1.2
                    and (shot_counter > 0)
                )
                freeze_dur = self.freeze_duration if is_freeze else 0.0

                # Generate director note
                desc = self._generate_description(angle, seg.duration)
                if is_freeze:
                    desc += f" [FREEZE {freeze_dur:.1f}s]"

                plans.append(
                    ShotPlan(
                        index=shot_counter,
                        segment=seg,
                        angle=angle,
                        crop_coords=crop,
                        zoom_factor=self.zoom_factor,
                        description=desc,
                        clip_index=self.clip_index,
                        clip_path=self.clip_path,
                        is_freeze_frame=is_freeze,
                        freeze_duration=freeze_dur,
                        transition=self.transition_style,
                    )
                )
                last_angle = angle
                shot_counter += 1

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

        # Eligible angles excluding the last angle and B-Roll
        available = [a for a in CameraAngle if a != last_angle and a != CameraAngle.BROLL]
        if not available:
            available = [CameraAngle.WIDE, CameraAngle.CLOSEUP]

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
        elif angle == CameraAngle.BROLL:
            return f"B-Roll Cutaway Footage ({duration:.1f}s)"
        return f"{angle.value} Shot ({duration:.1f}s)"

