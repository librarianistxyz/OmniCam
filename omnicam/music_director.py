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
Music Video Camera Director for OmniCam.
Translates musical beat grids, drop transients, and multi-take timecode sync
into a dynamic music video edit with 808 punch-ins, counter-pans, speed ramps,
and beat-reactive transitions.
"""

from dataclasses import dataclass
import os
import random
from typing import Dict, List, Optional, Tuple

from .audio_analyzer import SpeechSegment
from .director import CameraAngle, ShotPlan
from .music_analyzer import MusicAnalysisResult, SongSection
from .music_sync import TakeSyncInfo
from .vision_tracker import FaceRegion, VisionTracker


class MusicVideoDirector:
    """
    Directs music videos following industry music video grammar:
    - Downbeat-locked cutting cadence (Verses 4 bars, Pre-Chorus 2 bars, Chorus 1 bar)
    - 808 / Drop punch-ins directly into tight singer close-ups
    - Alternating counter-pans across bars (Thirds Left -> Thirds Right)
    - Multi-take rotation locked in phase to master audio
    - Speed ramps and beat-reactive FX triggers (flares, film burns, glitches)
    """

    def __init__(
        self,
        analysis: MusicAnalysisResult,
        takes: List[TakeSyncInfo],
        tracker: Optional[VisionTracker] = None,
        target_resolution: str = "720p",
        zoom_factor: float = 1.85,
        enable_drop_punchins: bool = True,
        enable_speed_ramps: bool = True,
        enable_beat_fx: bool = True,
    ):
        self.analysis = analysis
        self.takes = takes if takes else []
        self.tracker = tracker
        self.target_resolution = target_resolution
        self.zoom_factor = zoom_factor
        self.enable_drop_punchins = enable_drop_punchins
        self.enable_speed_ramps = enable_speed_ramps
        self.enable_beat_fx = enable_beat_fx

        # Screen dimensions
        if target_resolution == "1080p":
            self.src_w, self.src_h = 1920, 1080
        elif target_resolution == "4k":
            self.src_w, self.src_h = 3840, 2160
        else:
            self.src_w, self.src_h = 1280, 720

    def _get_active_take_at(self, t_master: float, preferred_take_idx: int = 0) -> Tuple[int, TakeSyncInfo, float]:
        """
        Returns (take_index, TakeSyncInfo, t_take) for a given master timeline second.
        Falls back to available takes if preferred take is out of bounds.
        """
        if not self.takes:
            # Single take default
            dummy_take = TakeSyncInfo(
                take_index=0,
                take_path="",
                offset_seconds=0.0,
                confidence=1.0,
                is_locked=True,
                take_duration=self.analysis.total_duration,
                master_duration=self.analysis.total_duration,
            )
            return 0, dummy_take, max(0.0, t_master)

        # Check preferred take
        candidates = list(range(len(self.takes)))
        if preferred_take_idx in candidates:
            candidates.remove(preferred_take_idx)
            candidates.insert(0, preferred_take_idx)

        for c_idx in candidates:
            take_info = self.takes[c_idx]
            t_take = t_master - take_info.offset_seconds
            if 0.0 <= t_take <= (take_info.take_duration + 0.5):
                return c_idx, take_info, max(0.0, t_take)

        # Fallback to take 0 clamped
        take0 = self.takes[0]
        t_take0 = max(0.0, min(take0.take_duration, t_master - take0.offset_seconds))
        return 0, take0, t_take0

    def _calculate_crop(self, angle: CameraAngle, zoom: float, face_box: Optional[FaceRegion] = None) -> Dict[str, int]:
        """
        Calculates framing bounding box for given musical angle.
        """
        w = int(self.src_w / zoom)
        h = int(self.src_h / zoom)

        # Ensure even dimensions
        w = w if w % 2 == 0 else w - 1
        h = h if h % 2 == 0 else h - 1

        if face_box and face_box.confidence > 0.4:
            fx, fy, fw, fh = face_box.x, face_box.y, face_box.w, face_box.h
            fc_x = fx + fw // 2
            fc_y = fy + fh // 2
        else:
            fc_x = self.src_w // 2
            fc_y = int(self.src_h * 0.45)

        if angle == CameraAngle.WIDE:
            return {"x": 0, "y": 0, "w": self.src_w, "h": self.src_h}
        elif angle == CameraAngle.CLOSEUP:
            x = max(0, min(self.src_w - w, fc_x - w // 2))
            y = max(0, min(self.src_h - h, fc_y - int(h * 0.40)))
            return {"x": x, "y": y, "w": w, "h": h}
        elif angle == CameraAngle.THIRD_LEFT:
            # Place artist on left third line (x = w*0.33)
            x = max(0, min(self.src_w - w, fc_x - int(w * 0.33)))
            y = max(0, min(self.src_h - h, fc_y - int(h * 0.42)))
            return {"x": x, "y": y, "w": w, "h": h}
        elif angle == CameraAngle.THIRD_RIGHT:
            # Place artist on right third line (x = w*0.66)
            x = max(0, min(self.src_w - w, fc_x - int(w * 0.67)))
            y = max(0, min(self.src_h - h, fc_y - int(h * 0.42)))
            return {"x": x, "y": y, "w": w, "h": h}
        elif angle == CameraAngle.SLOW_PUSH:
            x = max(0, min(self.src_w - w, fc_x - w // 2))
            y = max(0, min(self.src_h - h, fc_y - int(h * 0.45)))
            return {"x": x, "y": y, "w": w, "h": h}

        return {"x": 0, "y": 0, "w": self.src_w, "h": self.src_h}

    def plan_music_video(self) -> List[ShotPlan]:
        """
        Orchestrates musical shot cuts, angles, speed ramps, and beat effects.
        """
        downbeats = self.analysis.downbeats
        total_dur = self.analysis.total_duration
        if not downbeats:
            downbeats = [0.0]

        # 1. Build cutting points based on sections and cadences
        cut_points: List[float] = [0.0]
        sections = self.analysis.sections or [
            SongSection(name="verse", start=0.0, end=total_dur, energy_level=0.5, cadence_bars=4)
        ]

        for sec in sections:
            # Find downbeats inside this section
            sec_downbeats = [t for t in downbeats if sec.start <= t < sec.end]
            if not sec_downbeats:
                continue

            cadence = sec.cadence_bars
            for i, db in enumerate(sec_downbeats):
                if i % cadence == 0 and db > cut_points[-1] + 0.4:
                    cut_points.append(db)

        if cut_points[-1] < total_dur - 0.5:
            cut_points.append(total_dur)

        # 2. Plan each shot
        shot_plans: List[ShotPlan] = []
        angle_rotation = [
            CameraAngle.WIDE,
            CameraAngle.THIRD_LEFT,
            CameraAngle.CLOSEUP,
            CameraAngle.THIRD_RIGHT,
            CameraAngle.SLOW_PUSH,
        ]

        kick_set = set([round(t, 1) for t in self.analysis.kick_onsets])
        snare_set = set([round(t, 1) for t in self.analysis.snare_onsets])

        num_takes = len(self.takes) if self.takes else 1

        for idx in range(len(cut_points) - 1):
            m_start = cut_points[idx]
            m_end = cut_points[idx + 1]
            shot_dur = m_end - m_start
            if shot_dur < 0.2:
                continue

            # Determine section
            curr_sec = next((s for s in sections if s.start <= m_start < s.end), sections[0])

            # Select camera take (cycle through takes across shots)
            pref_take = idx % num_takes
            take_idx, take_info, t_take_start = self._get_active_take_at(m_start, preferred_take_idx=pref_take)
            t_take_end = t_take_start + shot_dur

            # Determine angle following music grammar
            # Drop / Chorus check: is this a high energy drop?
            is_chorus = curr_sec.name in ("chorus", "drop")
            is_kick_drop = any(abs(m_start - k) < 0.25 for k in kick_set)

            if is_chorus and is_kick_drop and self.enable_drop_punchins:
                # 808 Bass Drop Punch-in: Extreme close-up centered on singer
                angle = CameraAngle.CLOSEUP
                zoom = self.zoom_factor * 1.25
                trans = "glitch"
                desc = "808 Bass Drop Punch-In (Extreme Close-Up)"
            elif is_chorus:
                # Fast angle switches during chorus
                angle = CameraAngle.CLOSEUP if (idx % 2 == 0) else CameraAngle.SLOW_PUSH
                zoom = self.zoom_factor
                trans = "flash"
                desc = f"Chorus Peak Energy ({angle.value})"
            elif curr_sec.name == "pre_chorus":
                # Build-up: alternating Dutch counter-pans
                angle = CameraAngle.THIRD_LEFT if (idx % 2 == 0) else CameraAngle.THIRD_RIGHT
                zoom = self.zoom_factor * 0.90
                trans = "zoom"
                desc = f"Pre-Chorus Build Counter-Pan ({angle.value})"
            else:
                # Verse / Intro: Smooth rhythmic rotation
                angle = angle_rotation[idx % len(angle_rotation)]
                zoom = self.zoom_factor if angle != CameraAngle.WIDE else 1.0
                trans = "flash" if idx > 0 else "none"
                desc = f"{curr_sec.name.capitalize()} 4-Bar ({angle.value})"

            # Face tracking if tracker available
            face_box = None
            if self.tracker:
                face_box = self.tracker.get_active_speaker_box(t_take_start + shot_dur / 2.0)

            crop = self._calculate_crop(angle, zoom, face_box)

            # CapCut Freeze frame on climax hits (rare, high impact)
            freeze = False
            freeze_dur = 0.0
            if is_kick_drop and is_chorus and (idx % 8 == 0):
                freeze = True
                freeze_dur = 0.35

            # Speed ramping: during pre-chorus into chorus downbeat
            ramp = "none"
            if self.enable_speed_ramps and curr_sec.name == "pre_chorus" and (idx % 2 == 1):
                ramp = "slow_to_fast"

            # Beat-reactive FX
            beat_fx = None
            if self.enable_beat_fx:
                if is_chorus and is_kick_drop:
                    beat_fx = "glitch"
                elif is_chorus and (idx % 4 == 0):
                    beat_fx = "lens_flare"
                elif curr_sec.name == "intro" and idx == 0:
                    beat_fx = "film_burn"

            # Create SpeechSegment representing the musical interval
            seg = SpeechSegment(
                start=round(t_take_start, 3),
                end=round(t_take_end, 3),
                text=f"[{curr_sec.name.upper()} // BAR {idx + 1}]",
                speaker_id=f"take_{take_idx}",
            )

            shot = ShotPlan(
                index=idx,
                segment=seg,
                angle=angle,
                crop_coords=crop,
                zoom_factor=zoom,
                description=desc,
                clip_index=take_idx,
                clip_path=take_info.take_path if take_info.take_path else None,
                is_freeze_frame=freeze,
                freeze_duration=freeze_dur,
                transition=trans,
            )
            # Attach dynamic music metadata
            setattr(shot, "speed_ramp", ramp)
            setattr(shot, "beat_effect", beat_fx)
            setattr(shot, "master_start", m_start)
            setattr(shot, "master_end", m_end)

            shot_plans.append(shot)

        return shot_plans
