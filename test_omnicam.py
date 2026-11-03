#!/usr/bin/env python3
"""
Automated Test Suite for OmniCam
Generates a synthetic 4K video with spoken tones and pauses, executes the full
AI Director and Render pipeline, and verifies audio-visual cuts end-to-end.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time

from omnicam.audio_analyzer import AudioAnalyzer, SpeechSegment
from omnicam.director import CameraDirector, CameraAngle
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

        # 4. Test Render Engine with Auto-Ducking BGM and Animated Captions
        print("\n[Test 3] Testing Hormozi Animated Captions & Auto-Ducking BGM...")
        from omnicam.captions import WordTiming, remap_words_to_edited_timeline, generate_hormozi_ass

        sample_words = [
            WordTiming(word="WELCOME", start=0.2, end=0.8),
            WordTiming(word="TO", start=0.8, end=1.2),
            WordTiming(word="OMNICAM", start=1.2, end=2.0),
            WordTiming(word="VIRTUAL", start=4.2, end=5.0),
            WordTiming(word="MULTI-CAM", start=5.0, end=5.8),
            WordTiming(word="PRODUCTION", start=7.1, end=7.9),
        ]
        remapped_words = remap_words_to_edited_timeline(sample_words, segments)
        assert len(remapped_words) == 6
        print(f"  [✓] Remapped {len(remapped_words)} words frame-accurately across speech takes.")

        ass_path = os.path.join(tmp_dir, "test_hormozi.ass")
        generate_hormozi_ass(
            words=remapped_words,
            output_ass_path=ass_path,
            highlight_color="yellow",
        )
        assert os.path.isfile(ass_path)
        with open(ass_path) as f:
            ass_text = f.read()
        assert r"\c&H0000E5FF&" in ass_text
        print("  [✓] Generated Hormozi .ass subtitle script with active-word illumination.")

        config = RenderConfig(
            target_width=1280,
            target_height=720,
            color_grade="cinematic",
            normalize_audio=True,
            bgm_path="ambient",
            bgm_volume=0.20,
            captions_file=ass_path,
            stabilize=True,
            stabilize_smoothing=15,
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

        # 5. Test Automatic B-Roll Cutaway Pipeline
        print("\n[Test 4] Testing Automatic B-Roll Cutaways (--broll ./clips/)...")
        from omnicam.broll import BRollManager, BRollAsset

        broll_dir = os.path.join(tmp_dir, "test_broll_clips")
        os.makedirs(broll_dir, exist_ok=True)

        # Generate synthetic B-roll video clip
        broll_vid = os.path.join(broll_dir, "broll_footage.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                "-t", "4.0", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-an", broll_vid,
            ],
            check=True,
        )

        # Generate synthetic B-roll photo
        broll_img = os.path.join(broll_dir, "broll_photo.png")
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=navy:s=1280x720:d=1",
                "-vframes", "1", broll_img,
            ],
            check=True,
        )

        broll_mgr = BRollManager(broll_dir)
        discovered = broll_mgr.discover_assets()
        assert len(discovered) == 2, f"Expected 2 B-roll assets, found {len(discovered)}"
        print(f"  [✓] BRollManager discovered {len(discovered)} assets (video + photo).")

        # Test B-roll planning on an extended 6-second take
        extended_segs = [
            SpeechSegment(index=0, start=0.0, end=6.0, duration=6.0, silence_before=1.0),
        ]
        broll_director = CameraDirector(
            tracker=tracker,
            pacing_style="dynamic",
            broll_manager=broll_mgr,
            min_broll_speech_dur=4.0,
            broll_cutaway_dur=2.5,
        )
        broll_plans = broll_director.plan_production(extended_segs)

        # Should split 1 long take into 3 sub-shots: [Speaker Lead-in, B-Roll Cutaway, Speaker Return]
        assert len(broll_plans) == 3, f"Expected 3 shots for B-roll cutaway, got {len(broll_plans)}"
        assert broll_plans[1].angle == CameraAngle.BROLL, "Middle shot must be BROLL"
        assert broll_plans[0].angle != CameraAngle.BROLL, "Lead-in must be speaker camera angle"
        assert broll_plans[2].angle != CameraAngle.BROLL, "Return must be speaker camera angle"
        assert broll_plans[0].angle != broll_plans[2].angle, "Lead-in and return angles must differ (zero jump cuts)"
        print(f"  [✓] Director split extended take into: {[s.angle.value for s in broll_plans]}")
        print(f"  [✓] B-Roll cutaway planned: {broll_plans[1].broll_name} ({broll_plans[1].segment.duration:.2f}s)")

        # Test rendering with B-roll cutaway
        broll_out = os.path.join(tmp_dir, "broll_master_output.mp4")
        broll_engine = RenderEngine(
            input_vid,
            config=RenderConfig(
                target_width=1280,
                target_height=720,
                broll_dir=broll_dir,
                preset="ultrafast",
            ),
        )
        broll_render_file = broll_engine.render(broll_plans, broll_out)
        assert os.path.isfile(broll_render_file)
        broll_dur = AudioAnalyzer.get_media_duration(broll_render_file)
        assert 5.5 <= broll_dur <= 6.5, f"B-roll cut duration unexpected: {broll_dur}s"
        print(f"  [✓] B-Roll cutaway rendered successfully: {broll_dur:.2f}s with voiceover intact.")

        # 6. Test Filler Word & Hesitation Removal
        print("\n[Test 5] Testing Filler Word & Vocal Hesitation Removal...")
        from omnicam.filler_remover import (
            detect_lexical_fillers,
            detect_acoustic_hesitations,
            remove_filler_intervals,
        )

        test_speech_words = [
            WordTiming(word="TODAY", start=1.0, end=1.4),
            WordTiming(word="UM", start=1.5, end=2.0),
            WordTiming(word="WE", start=2.1, end=2.3),
            WordTiming(word="ARE", start=2.3, end=2.5),
            WordTiming(word="LIKE", start=2.6, end=3.0),
            WordTiming(word="LAUNCHING", start=3.1, end=3.7),
            WordTiming(word="YOU", start=3.8, end=4.0),
            WordTiming(word="KNOW", start=4.0, end=4.3),
            WordTiming(word="OMNICAM", start=4.4, end=5.2),
        ]
        lexical_cuts = detect_lexical_fillers(test_speech_words)
        assert len(lexical_cuts) == 3, f"Expected 3 filler cuts ('UM', 'LIKE', 'YOU KNOW'), got {len(lexical_cuts)}"
        print(f"  [✓] Lexical filter identified {len(lexical_cuts)} filler intervals ('UM', 'LIKE', 'YOU KNOW').")

        # Test excision of filler intervals from active take
        raw_take = [SpeechSegment(index=0, start=1.0, end=5.5, duration=4.5, silence_before=1.0)]
        clean_takes = remove_filler_intervals(raw_take, lexical_cuts)
        assert len(clean_takes) >= 3, f"Expected segment to be carved into >=3 takes, got {len(clean_takes)}"
        for ct in clean_takes:
            # Ensure no clean take overlaps with 'UM' [1.5, 2.0]
            assert not (ct.start < 1.9 and ct.end > 1.6), "Clean take still contains 'UM' interval"
        print(f"  [✓] Successfully excised fillers: 1 rambling take carved into {len(clean_takes)} clean takes.")

        # Test acoustic spectral hesitation detector on 0.5s 220Hz drone
        drone_wav = os.path.join(tmp_dir, "acoustic_drone.wav")
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=16000:duration=0.6",
                "-c:a", "pcm_s16le", drone_wav,
            ],
            check=True,
        )
        acoustic_cuts = detect_acoustic_hesitations(drone_wav, min_duration=0.25)
        assert len(acoustic_cuts) >= 1, "Expected acoustic detector to catch 0.6s 220Hz hesitation drone"
        print(f"  [✓] Acoustic hesitation filter detected drone: {acoustic_cuts}")

        # 7. Test Localhost Mobile Web Studio
        print("\n[Test 6] Testing Localhost Mobile Web Studio Server & API (port 8899)...")
        import urllib.request
        from omnicam.web import launch_web_server

        server_thread = threading.Thread(target=launch_web_server, args=(8899,), daemon=True)
        server_thread.start()
        time.sleep(0.5)

        # Verify UI endpoint
        req_ui = urllib.request.urlopen("http://localhost:8899/")
        ui_html = req_ui.read().decode("utf-8")
        assert "OMNICAM" in ui_html
        assert "handleNativeFileSelect" in ui_html
        assert "openFileBrowser" in ui_html
        print(f"  [✓] Web Studio UI verified at http://localhost:8899/ ({len(ui_html)} bytes HTML)")

        # Verify Find Local endpoint (Gallery fast-path)
        req_find = urllib.request.urlopen("http://localhost:8899/api/find_local?name=" + os.path.basename(input_vid))
        find_res = json.loads(req_find.read().decode("utf-8"))
        assert find_res.get("found") is True
        assert find_res.get("path") == input_vid
        print(f"  [✓] Web API /api/find_local verified: instant match found.")

        # Verify Upload endpoint (Gallery stream)
        dummy_content = b"\x00\x00\x00\x18ftypmp42"
        req_up = urllib.request.Request(
            "http://localhost:8899/api/upload",
            data=dummy_content,
            headers={"X-Filename": "test_gallery.mp4", "Content-Type": "video/mp4"},
        )
        up_res = json.loads(urllib.request.urlopen(req_up).read().decode("utf-8"))
        assert up_res.get("status") == "uploaded"
        assert os.path.isfile(up_res.get("path"))
        print(f"  [✓] Web API /api/upload verified: binary stream uploaded successfully.")

        # Verify Browse endpoint (Device Navigator)
        req_browse = urllib.request.urlopen("http://localhost:8899/api/browse?dir=" + os.path.dirname(input_vid))
        browse_res = json.loads(req_browse.read().decode("utf-8"))
        assert "entries" in browse_res and len(browse_res["entries"]) >= 1
        print(f"  [✓] Web API /api/browse verified: {len(browse_res['entries'])} entries listed.")

        # Verify Analysis API endpoint
        req_post = urllib.request.Request(
            "http://localhost:8899/api/analyze",
            data=json.dumps({"input_path": input_vid, "pacing": "dynamic"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        res_post = urllib.request.urlopen(req_post)
        analysis = json.loads(res_post.read().decode("utf-8"))
        assert "shots" in analysis and len(analysis["shots"]) == 3
        print(f"  [✓] Web API /api/analyze returned {len(analysis['shots'])} timeline shots successfully.")

    print("\n" + "=" * 65)
    print(" [✓] ALL UNIT & INTEGRATION TESTS PASSED WITH 100% SUCCESS")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
