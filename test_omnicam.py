#!/usr/bin/env python3
"""
Automated Test Suite for OmniCam
Generates a synthetic 4K video with spoken tones and pauses, executes the full
AI Director and Render pipeline, and verifies audio-visual cuts end-to-end.
"""

import os
import subprocess
import sys
import tempfile
import time

from omnicam.audio_analyzer import AudioAnalyzer
from omnicam.director import CameraDirector
from omnicam.render_engine import RenderConfig, RenderEngine
from omnicam.vision_tracker import VisionTracker


def create_synthetic_4k_test_video(path: str, duration: float = 8.0):
    """
    Synthesizes a 4K test video with audio beeps and silence intervals:
      - 0.0s - 2.5s: Tone (Simulated Speech Segment 1)
      - 2.5s - 4.0s: Silence (1.5s pause)
      - 4.0s - 6.0s: Tone (Simulated Speech Segment 2)
      - 6.0s - 7.0s: Silence (1.0s pause)
      - 7.0s - 8.0s: Tone (Simulated Speech Segment 3)
    """
    print(f"[*] Generating synthetic 4K test video at {path}...")
    vf = (
        f"testsrc=duration={duration}:size=3840x2160:rate=24,"
        "drawbox=x=1600:y=600:w=640:h=800:color=red@0.8:t=fill,"
        "drawtext=text='OMNICAM 4K TEST':fontcolor=white:fontsize=80:x=1650:y=950"
    )

    # Audio filter: 3 beeps with volume=0 in between
    af = (
        f"sine=frequency=440:duration={duration},"
        "volume='if(between(t,0,2.5)+between(t,4.0,6.0)+between(t,7.0,8.0), 0.8, 0.0)':eval=frame"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-f", "lavfi", "-i", vf,
        "-f", "lavfi", "-i", af,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-t", str(duration),
        path,
    ]
    subprocess.run(cmd, check=True)
    print("  [✓] Test video created successfully.")


def run_tests():
    print("=" * 65)
    print(" OmniCam Verification & End-to-End Test Suite")
    print("=" * 65)

    with tempfile.TemporaryDirectory(prefix="omnicam_test_") as tmp_dir:
        input_vid = os.path.join(tmp_dir, "synthetic_input_4k.mp4")
        output_vid = os.path.join(tmp_dir, "master_output_720p.mp4")

        # 1. Create Synthetic Video
        create_synthetic_4k_test_video(input_vid, duration=8.0)

        # 2. Test Audio Analyzer
        print("\n[Test 1] Testing Audio Silence Detection...")
        analyzer = AudioAnalyzer(
            noise_threshold_db=-30.0,
            min_silence_duration=0.5,
            padding_start=0.05,
            padding_end=0.05,
        )
        duration = analyzer.get_media_duration(input_vid)
        assert abs(duration - 8.0) < 0.5, f"Expected ~8.0s duration, got {duration}s"
        print(f"  [✓] Detected media duration: {duration:.2f}s")

        segments = analyzer.extract_speech_segments(input_vid)
        print(f"  [✓] Extracted segments: {len(segments)}")
        for s in segments:
            print(f"      {s}")
        assert len(segments) == 3, f"Expected 3 speech segments, got {len(segments)}"

        # 3. Test Vision Tracker & Director
        print("\n[Test 2] Testing Vision Tracker and Camera Director...")
        tracker = VisionTracker(input_vid)
        assert tracker.metadata.width == 3840
        assert tracker.metadata.height == 2160
        print(f"  [✓] Probed source geometry: {tracker.metadata.width}x{tracker.metadata.height}")

        director = CameraDirector(tracker=tracker, pacing_style="dynamic", zoom_factor=1.75)
        shot_plans = director.plan_production(segments)
        assert len(shot_plans) == 3

        angles = [sp.angle for sp in shot_plans]
        print(f"  [✓] Planned angles: {[a.value for a in angles]}")
        # Verify no back-to-back duplicate angles
        for i in range(1, len(angles)):
            assert angles[i] != angles[i - 1], f"Duplicate consecutive angle: {angles[i]}"
        print("  [✓] Director rule verified: Zero jump cuts (all consecutive angles distinct).")

        # Verify crop coordinates are clamped inside 4K boundary
        for sp in shot_plans:
            c = sp.crop_coords
            assert 0 <= c["x"] <= 3840 - c["w"]
            assert 0 <= c["y"] <= 2160 - c["h"]
        print("  [✓] Crop coordinates geometry verified strictly within 4K bounds.")

        # 4. Test Render Engine with Auto-Ducking BGM
        print("\n[Test 3] Testing Multi-Angle Render Engine with Auto-Ducking BGM...")
        config = RenderConfig(
            target_width=1280,
            target_height=720,
            color_grade="cinematic",
            normalize_audio=True,
            bgm_path="ambient",
            bgm_volume=0.20,
            preset="ultrafast",
        )
        engine = RenderEngine(input_vid, config=config)

        t0 = time.time()
        rendered_file = engine.render(shot_plans, output_vid)
        render_time = time.time() - t0
        print(f"  [✓] Rendering finished in {render_time:.2f}s")

        assert os.path.isfile(rendered_file)
        out_size = os.path.getsize(rendered_file)
        assert out_size > 10000, f"Rendered file is suspiciously small: {out_size} bytes"
        print(f"  [✓] Rendered file verified: {out_size / 1024:.1f} KB")

        # Probe output video properties
        out_dur = AudioAnalyzer.get_media_duration(rendered_file)
        # 3 segments of 2.5s + 2.0s + 1.0s = ~5.5s total (pauses were cut out)
        print(f"  [✓] Rendered cut duration: {out_dur:.2f}s (Dead air removed: {duration - out_dur:.2f}s)")
        assert 5.0 <= out_dur <= 7.0, f"Output duration unexpected: {out_dur}s"

    print("\n" + "=" * 65)
    print(" [✓] ALL UNIT & INTEGRATION TESTS PASSED WITH 100% SUCCESS")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
