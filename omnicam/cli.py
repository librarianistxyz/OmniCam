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
Command Line Interface for OmniCam - AI Virtual Multi-Camera Director
"""

import argparse
import os
import sys
import time
from typing import Optional

from .audio_analyzer import AudioAnalyzer
from .director import CameraDirector
from .render_engine import RenderConfig, RenderEngine
from .vision_tracker import VisionTracker
from .broll import BRollManager
from .captions import Transcriber
from .music_sync import MultiTakeSyncEngine, TakeSyncInfo
from .music_analyzer import MusicBeatAnalyzer, MusicAnalysisResult
from .music_director import MusicVideoDirector
from .filler_remover import (
    DEFAULT_FILLER_WORDS,
    detect_lexical_fillers,
    detect_acoustic_hesitations,
    remove_filler_intervals,
)


def format_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:05.2f}"


def print_banner():
    banner = r"""
 ╔═══════════════════════════════════════════════════════════════╗
 ║      ____                  _  ____                            ║
 ║     / __ \____ ___  ____  (_)/ ____/___ _____ ___             ║
 ║    / / / / __ `__ \/ __ \/ // /   / __ `/ __ `__ \            ║
 ║   / /_/ / / / / / / / / / // /___/ /_/ / / / / / /            ║
 ║   \____/_/ /_/ /_/_/ /_/_(_)____/\__,_/_/ /_/ /_/             ║
 ║                                                               ║
 ║      AI VIRTUAL MULTI-CAMERA DIRECTOR (Studio 4K Edition)     ║
 ║      Zero-Cloud  •  Auto-Silence Cuts  •  Dynamic Framing     ║
 ╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def generate_cut_sheet(shot_plans, raw_duration: float) -> str:
    """Generates an ASCII director cut sheet summarizing shots, angles, and savings."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"{'#':<3} {'START':<9} {'END':<9} {'DUR':<7} {'ANGLE':<13} {'DIRECTOR NOTE'}")
    lines.append("-" * 80)

    total_cut_duration = 0.0
    for shot in shot_plans:
        s = shot.segment
        total_cut_duration += s.duration
        lines.append(
            f"{shot.index+1:<3} {s.start:>6.2f}s  {s.end:>6.2f}s  {s.duration:>5.2f}s  "
            f"{shot.angle.value:<13} {shot.description}"
        )

    saved_time = max(0.0, raw_duration - total_cut_duration)
    saved_pct = (saved_time / raw_duration * 100.0) if raw_duration > 0 else 0.0

    lines.append("=" * 80)
    lines.append(f"Original Length: {format_duration(raw_duration)} ({raw_duration:.2f}s)")
    lines.append(f"Edited Length:   {format_duration(total_cut_duration)} ({total_cut_duration:.2f}s)")
    lines.append(f"Dead Air Cut:    {format_duration(saved_time)} ({saved_time:.2f}s, -{saved_pct:.1f}%)")
    lines.append(f"Total Camera Switches: {len(shot_plans)}")
    lines.append("=" * 80)
    return "\n".join(lines)


def _run_music_video_pipeline(args, input_path: str, output_path: str):
    print("\n" + "=" * 65)
    print(" 🎵 OMNICAM AI // MUSIC VIDEO PRODUCTION STUDIO")
    print("=" * 65)

    song_path = os.path.abspath(args.song) if args.song else input_path
    if not os.path.isfile(song_path):
        print(f"[-] Error: Master song audio file not found: {song_path}")
        sys.exit(1)

    all_takes = [input_path]
    for tk in getattr(args, "takes", []):
        abs_tk = os.path.abspath(tk)
        if os.path.isfile(abs_tk) and abs_tk not in all_takes:
            all_takes.append(abs_tk)

    print(f"[*] Master Audio:        {song_path}")
    print(f"[*] Camera Takes:        {len(all_takes)} take(s) detected")
    for i, t in enumerate(all_takes):
        print(f"    - Take {i + 1}: {t}")

    # Phase 1: Multi-Take Waveform Auto-Sync
    print("\n[Phase 1/4] Multi-Take Waveform Auto-Sync (FFT Cross-Correlation)...")
    sync_engine = MultiTakeSyncEngine()
    takes_info = sync_engine.align_multiple_takes(song_path, all_takes)

    print("  +-----------------+---------------+------------+----------+")
    print("  | Camera Take     | Time Offset   | Confidence | Status   |")
    print("  +-----------------+---------------+------------+----------+")
    for ti in takes_info:
        fn = os.path.basename(ti.take_path)[:15]
        status = "LOCKED [✓]" if ti.is_locked else "UNLOCKED"
        print(f"  | {fn:<15} | {ti.offset_seconds:>+11.3f}s | {ti.confidence*100:>8.1f}% | {status:<8} |")
    print("  +-----------------+---------------+------------+----------+")

    # Phase 2: Beat & Energy Grid Detection
    print("\n[Phase 2/4] Beat & Energy Grid Detection (FFT Spectral Flux)...")
    music_analyzer = MusicBeatAnalyzer()
    analysis = music_analyzer.analyze(song_path, manual_bpm=args.bpm)
    print(f"  -> Detected Tempo:    {analysis.bpm:.1f} BPM (Beat: {analysis.beat_duration:.3f}s, Bar: {analysis.beat_duration*4:.2f}s)")
    print(f"  -> Total Measures:    {len(analysis.downbeats)} musical bars")
    print(f"  -> Kick Drops (808):  {len(analysis.kick_onsets)} sub-bass transients")
    print(f"  -> Snare Hits:        {len(analysis.snare_onsets)} transient cracks")
    sec_names = ", ".join(s.name.upper() for s in analysis.sections)
    print(f"  -> Song Structure:    {len(analysis.sections)} sections ({sec_names})")

    # Phase 3: Subject & Performer Tracking
    print("\n[Phase 3/4] Subject & Performer Face Tracking...")
    tracker = VisionTracker(input_path)
    tracker.analyze()

    # Phase 4: Musical Virtual Camera Directing
    print("\n[Phase 4/4] Orchestrating Musical Camera Cuts & 808 Drops...")
    director = MusicVideoDirector(
        analysis=analysis,
        takes=takes_info,
        tracker=tracker,
        target_resolution=args.resolution,
        zoom_factor=args.zoom,
        enable_drop_punchins=True,
        enable_speed_ramps=args.speed_ramps,
        enable_beat_fx=args.beat_fx,
    )
    shot_plans = director.plan_music_video()
    print(f"  -> Generated {len(shot_plans)} downbeat-locked camera cuts.")

    if args.dry_run:
        print("\n[*] Dry-run mode: Render skipped.")
        return

    base_w, base_h = 1280, 720
    if args.resolution == "1080p":
        base_w, base_h = 1920, 1080
    elif args.resolution == "4k":
        base_w, base_h = 3840, 2160

    target_w, target_h = (base_h, base_w) if tracker.metadata.is_portrait else (base_w, base_h)

    render_config = RenderConfig(
        target_width=target_w,
        target_height=target_h,
        is_portrait=tracker.metadata.is_portrait,
        color_grade=args.color,
        normalize_audio=not args.no_normalize_audio,
        input_videos=all_takes,
        transition_style=args.transition,
        show_hud=not args.no_hud,
        show_title=bool(args.title),
        title_text=args.title or "OMNICAM // MUSIC VIDEO MASTER",
        subtitle_text=args.subtitle or f"{analysis.bpm:.0f} BPM // 4K CINEMATIC",
        letterbox=args.letterbox,
        film_grain=args.film_grain,
        overlay_effect=args.overlay,
        overlay_blend_mode=args.overlay_blend,
        overlay_opacity=args.overlay_opacity,
        overlay_target=args.overlay_target,
        target_person=args.target_person,
        selective_color=args.selective_color,
        music_mode=True,
        song_audio_path=song_path,
        bpm=analysis.bpm,
        enable_bass_pump=args.bass_pump,
        enable_speed_ramps=args.speed_ramps,
        beat_reactive_fx=args.beat_fx,
    )

    print("\n[Mastering] Rendering Master 4K / 1080p Music Video...")
    engine = RenderEngine(input_path, config=render_config)

    def on_progress(pct: float, msg: str):
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {int(pct*100):>3}% - {msg}", end="", flush=True)

    t0 = time.time()
    try:
        engine.render(shot_plans, output_path, progress_callback=on_progress)
        print()
    except Exception as e:
        print(f"\n[-] Rendering Error: {e}")
        sys.exit(1)

    t_render = time.time() - t0
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)

    print("\n" + "=" * 65)
    print(" [✓] MUSIC VIDEO MASTER COMPLETE")
    print("=" * 65)
    print(f" Output Video:     {output_path}")
    print(f" File Size:        {file_size_mb:.2f} MB")
    print(f" Render Time:      {t_render:.1f} seconds")
    print(f" Locked Tempo:     {analysis.bpm:.1f} BPM")
    print(f" Motion Pumping:   {'ENABLED (Bass Pump)' if args.bass_pump else 'DISABLED'}")
    print(f" Speed Ramps:      {'ENABLED' if args.speed_ramps else 'DISABLED'}")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="OmniCam: Transform single-camera handheld footage into an automated multi-camera studio video."
    )
    parser.add_argument("input", nargs="?", default=None, help="Path to input video file (e.g., 4K MP4/MOV recorded on Samsung S9 or phone)")
    parser.add_argument("-o", "--output", help="Path to output edited video. Defaults to <input>_omnicam.mp4")
    parser.add_argument(
        "--web",
        "--studio",
        action="store_true",
        help="Launch the Localhost Mobile Web Studio (http://localhost:8080) for browser-based visual editing.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port number for the Localhost Mobile Web Studio (default: 8080).",
    )
    parser.add_argument(
        "--silence-thresh",
        type=float,
        default=-32.0,
        help="Silence detection threshold in dB (default: -32.0 dB). Lower numbers (-38) = only quietest pauses cut.",
    )
    parser.add_argument(
        "--min-silence",
        type=float,
        default=0.35,
        help="Minimum pause duration in seconds to trigger a camera cut (default: 0.35s).",
    )
    parser.add_argument(
        "--pacing",
        choices=["dynamic", "podcast", "documentary", "dramatic"],
        default="dynamic",
        help="Director pacing style (default: dynamic)",
    )
    parser.add_argument(
        "--zoom",
        type=float,
        default=1.75,
        help="Zoom punch-in factor for close-up and rule-of-thirds angles (default: 1.75)",
    )
    parser.add_argument(
        "--color",
        choices=[
            "cinematic",
            "podcast",
            "vintage",
            "oppenheimer_mono",
            "oppenheimer_fission",
            "sherlock_noir",
            "sherlock_gaslamp",
            "vintage_technicolor",
            "none",
        ],
        default="cinematic",
        help="Color grading profile (default: cinematic). Includes Oppenheimer B&W, Fission, Sherlock Noir, Gaslamp & Technicolor.",
    )
    parser.add_argument(
        "--target-person",
        choices=["primary", "left", "right", "person_1", "person_2", "center"],
        default="primary",
        help="Target speaker to frame and isolate in multi-person videos (default: primary).",
    )
    parser.add_argument(
        "--selective-color",
        choices=[
            "none",
            "person_color_bg_mono",
            "person_color_bg_sherlock",
            "person_color_bg_oppenheimer",
            "person_grade_only",
            "bg_grade_only",
        ],
        default="none",
        help="Selective color isolation mode: isolate tracked speaker in full color while grading background (Oppenheimer B&W, Sherlock fog, or Fission amber).",
    )
    parser.add_argument(
        "--resolution",
        choices=["720p", "1080p", "4k"],
        default="720p",
        help="Target output resolution (default: 720p for ultra-fast mobile rendering)",
    )
    parser.add_argument(
        "--no-normalize-audio",
        action="store_true",
        help="Disable studio loudness normalization and highpass filtering.",
    )
    parser.add_argument(
        "--title",
        default="OMNICAM AI • MULTI-CAM PRODUCTION",
        help="Main text for the opening lower-third title card (default: 'OMNICAM AI • MULTI-CAM PRODUCTION')",
    )
    parser.add_argument(
        "--subtitle",
        default="PRO VIRTUAL STUDIO // 4K CLARITY",
        help="Subtitle text for the opening lower-third title card",
    )
    parser.add_argument(
        "--no-hud",
        action="store_true",
        help="Disable on-screen camera angle watermark badge (CAM 1 • WIDE, CAM 2 • CLOSE-UP).",
    )
    parser.add_argument(
        "--letterbox",
        action="store_true",
        help="Add 2.35:1 Anamorphic cinema bars (letterbox) for high-end cinematic widescreen look.",
    )
    parser.add_argument(
        "--film-grain",
        action="store_true",
        help="Burn organic 35mm silver halide film grain noise.",
    )
    parser.add_argument(
        "--fx-glow",
        choices=["none", "promist", "dreamy"],
        default="none",
        help="Cinematic highlight bloom & diffusion glow (e.g., 1/4 Black Pro-Mist).",
    )
    parser.add_argument(
        "--fx-rgb",
        choices=["none", "subtle", "heavy"],
        default="none",
        help="Chromatic aberration RGB channel split (subtle lens fringe or heavy cyber glitch).",
    )
    parser.add_argument(
        "--fx-motion",
        choices=["none", "handheld", "quake"],
        default="none",
        help="Simulated camera motion (handheld camera operator drift or impact quake).",
    )
    parser.add_argument(
        "--fx-camcorder",
        action="store_true",
        help="Burn 90s retro VHS camcorder HUD overlay (REC ●, battery, timecode, safe brackets).",
    )
    parser.add_argument(
        "--fx-tilt-shift",
        action="store_true",
        help="Soft optical portrait depth blur on background keeping subject in sharp focus.",
    )
    parser.add_argument(
        "--fx-flicker",
        action="store_true",
        help="Vintage cinema film gate luminance breathing and subtle shutter flicker.",
    )
    parser.add_argument(
        "--overlay",
        help="Blend mode looping video overlay (e.g., light_leak_01, light_leak_02, film_dust_scratches, vhs_static_overlay, prism_bokeh, film_burn_01, or path to MP4).",
    )
    parser.add_argument(
        "--overlay-blend",
        choices=["screen", "addition", "overlay", "lighten", "softlight", "dodge", "multiply"],
        default="screen",
        help="Blend mode for looping overlay texture (default: screen).",
    )
    parser.add_argument(
        "--overlay-opacity",
        type=float,
        default=0.85,
        help="Opacity of blend mode overlay from 0.0 to 1.0 (default: 0.85).",
    )
    parser.add_argument(
        "--overlay-target",
        choices=["fullscreen", "background_only"],
        default="fullscreen",
        help="Target placement for overlay: 'fullscreen' (blends over whole screen) or 'background_only' (isolates subject and places overlay behind speaker).",
    )
    parser.add_argument(
        "--bgm",
        help="Path to background music audio file (e.g., /sdcard/Movies/lo-fi.mp3), or 'ambient'/'lofi' for built-in royalty-free ambient bed.",
    )
    parser.add_argument(
        "--bgm-volume",
        type=float,
        default=0.22,
        help="BGM volume level before ducking (default: 0.22). Automatically ducks to -22dB during speech.",
    )
    parser.add_argument(
        "--captions",
        "--hormozi",
        "--subtitles",
        action="store_true",
        help="Burn dynamic 'Hormozi / MrBeast' animated word captions with neon active-word tracking.",
    )
    parser.add_argument(
        "--caption-color",
        choices=["yellow", "green", "cyan", "red", "white"],
        default="yellow",
        help="Active word highlight color for animated subtitles (default: yellow)",
    )
    parser.add_argument(
        "--whisper-model",
        default="tiny.en",
        help="Whisper model size for transcription (default: tiny.en for fast mobile CPU transcription)",
    )
    parser.add_argument(
        "--captions-file",
        help="Optional path to existing .ass or .srt subtitle file to burn onto video.",
    )
    parser.add_argument(
        "--stabilize",
        "--gimbal",
        action="store_true",
        help="Enable 2-pass Digital Gimbal Horizon Stabilization (neutralizes walking bounce & handheld shake).",
    )
    parser.add_argument(
        "--stabilize-smoothing",
        type=int,
        default=25,
        help="Horizon stabilization smoothing radius in frames (default: 25). Higher numbers = smoother gimbal drift.",
    )
    parser.add_argument(
        "--broll",
        help="Directory of B-roll footage and photos to automatically insert during extended speech takes (>4s).",
    )
    parser.add_argument(
        "--broll-min-dur",
        type=float,
        default=4.0,
        help="Minimum speech take duration in seconds to trigger a B-roll cutaway (default: 4.0s).",
    )
    parser.add_argument(
        "--broll-length",
        type=float,
        default=2.5,
        help="Target duration in seconds for each B-roll cutaway (default: 2.5s).",
    )
    parser.add_argument(
        "--transition",
        choices=["flash", "zoom", "push", "glitch", "dissolve", "none"],
        default="flash",
        help="CapCut transition style between camera angle cuts (default: flash).",
    )
    parser.add_argument(
        "--freeze-frame",
        action="store_true",
        default=True,
        help="Enable dramatic CapCut freeze frames on speech pauses (holds keyframe for 0.6s with spotlight).",
    )
    parser.add_argument(
        "--no-freeze-frame",
        dest="freeze_frame",
        action="store_false",
        help="Disable dramatic freeze frames.",
    )
    parser.add_argument(
        "--freeze-dur",
        type=float,
        default=0.6,
        help="Duration of dramatic freeze frames in seconds (default: 0.6s).",
    )
    parser.add_argument(
        "--sfx",
        action="store_true",
        default=True,
        help="Enable cinematic whoosh and impact sound effects on cut transitions (default: enabled).",
    )
    parser.add_argument(
        "--no-sfx",
        dest="sfx",
        action="store_false",
        help="Disable transition whoosh sound effects.",
    )
    parser.add_argument(
        "--sfx-volume",
        type=float,
        default=0.35,
        help="Volume of transition whoosh sound effects (default: 0.35).",
    )
    parser.add_argument(
        "--join",
        help="Comma-separated list of multiple video files to cut, edit, and join into one master video.",
    )
    parser.add_argument(
        "--remove-fillers",
        "--filler-removal",
        action="store_true",
        help="Detect and cut vocal hesitations ('uh', 'um', 'ah', 'like', 'you know') and acoustic vowel drones.",
    )
    parser.add_argument(
        "--fillers",
        default="uh,um,uhm,ah,er,err,hmm,mm,like,you know",
        help="Comma-separated list of target filler words to remove (default: 'uh,um,uhm,ah,er,err,hmm,mm,like,you know').",
    )
    parser.add_argument(
        "--acoustic-fillers",
        action="store_true",
        help="Force spectral acoustic hesitation analysis to catch non-transcribed monotone vowel drones.",
    )
    parser.add_argument(
        "--dry-run",
        "--preview",
        action="store_true",
        help="Analyze pauses and display director cut sheet without rendering video.",
    )
    parser.add_argument(
        "--chunk-mode",
        action="store_true",
        help="Force multi-clip disk chunking instead of single-pass filtergraph.",
    )

    # ==========================================
    # MUSIC VIDEO STUDIO ARGUMENTS
    # ==========================================
    parser.add_argument(
        "--music-mode",
        action="store_true",
        help="Enable Music Video Production Mode (downbeat cutting, 808 drop punch-ins, beat-synced overlays).",
    )
    parser.add_argument(
        "--song",
        help="Path to clean Studio Master audio file (song.wav / song.mp3) to lock footage against.",
    )
    parser.add_argument(
        "--takes",
        nargs="+",
        default=[],
        help="Additional camera takes (e.g. Take 2 close-up, Take 3 dynamic performance) to auto-sync and rotate.",
    )
    parser.add_argument(
        "--bpm",
        type=float,
        default=None,
        help="Tempo of the song in BPM (automatically detected via FFT autocorrelation if omitted).",
    )
    parser.add_argument(
        "--bass-pump",
        action="store_true",
        help="Enable kick-drum sub-bass camera vibration / motion pumping.",
    )
    parser.add_argument(
        "--speed-ramps",
        action="store_true",
        help="Enable Cole Bennett / Lyrical Lemonade style slow-to-fast transition speed ramping.",
    )
    parser.add_argument(
        "--beat-fx",
        action="store_true",
        help="Trigger lens flares, film burns, and RGB chromatic glitches on downbeats and drops.",
    )

    args = parser.parse_args()

    if args.web:
        from .web import launch_web_server
        launch_web_server(port=args.port)
        return

    print_banner()

    if not args.input:
        parser.print_help()
        print("\n[-] Error: Please specify an input video file or run with --web to launch the Studio.")
        sys.exit(1)

    if not os.path.isfile(args.input):
        print(f"[-] Error: Input video file not found: {args.input}")
        sys.exit(1)

    input_path = os.path.abspath(args.input)
    if not args.output:
        stem, ext = os.path.splitext(input_path)
        output_path = f"{stem}_omnicam.mp4"
    else:
        output_path = os.path.abspath(args.output)

    if args.music_mode or args.song:
        _run_music_video_pipeline(args, input_path, output_path)
        return

    print(f"[*] Input Video:        {input_path}")
    print(f"[*] Director Pacing:    {args.pacing.upper()}")
    print(f"[*] Color Grading:      {args.color.upper()}")
    print(f"[*] Silence Threshold:  {args.silence_thresh} dB (min duration: {args.min_silence}s)")
    print(f"[*] Punch-in Zoom:      {args.zoom}x")
    print(f"[*] Output Target:      {args.resolution.upper()} -> {output_path}")
    print("-" * 65)

    # Step 1: Acoustic Silence Detection
    print("\n[Phase 1/3] Analyzing audio acoustics and speech pauses...")
    analyzer = AudioAnalyzer(
        noise_threshold_db=args.silence_thresh,
        min_silence_duration=args.min_silence,
        padding_start=0.06,
        padding_end=0.06,
    )
    raw_duration = analyzer.get_media_duration(input_path)
    print(f"  -> Total source duration: {raw_duration:.2f}s ({format_duration(raw_duration)})")

    segments = analyzer.extract_speech_segments(input_path)
    print(f"  -> Detected {len(segments)} spoken takes separated by pauses.")

    if args.remove_fillers or args.acoustic_fillers:
        print("  -> Scanning for vocal hesitations and filler words ('uh', 'um', 'like', 'you know')...")
        target_fillers = {f.strip().upper() for f in args.fillers.split(",") if f.strip()}
        filler_intervals = []

        # 1. Lexical detection via Whisper if available
        transcriber = Transcriber(model_size=args.whisper_model)
        if transcriber.is_available() and not args.acoustic_fillers:
            try:
                print(f"     Transcribing speech tokens with Whisper ({args.whisper_model})...")
                words = transcriber.transcribe(input_path)
                lexical_intervals = detect_lexical_fillers(words, target_fillers=target_fillers)
                filler_intervals.extend(lexical_intervals)
                print(f"     Identified {len(lexical_intervals)} spoken filler word tokens.")
            except Exception as ex:
                print(f"     Notice: Lexical transcription failed ({ex}). Falling back to acoustic hesitation detection.")
                acoustic_intervals = detect_acoustic_hesitations(input_path)
                filler_intervals.extend(acoustic_intervals)
        else:
            # 2. Acoustic spectral stationarity detection
            print("     Analyzing acoustic spectral flatness & stationary vowel drones...")
            acoustic_intervals = detect_acoustic_hesitations(input_path)
            filler_intervals.extend(acoustic_intervals)
            print(f"     Identified {len(acoustic_intervals)} acoustic vocal hesitations.")

        if filler_intervals:
            orig_count = len(segments)
            segments = remove_filler_intervals(segments, filler_intervals)
            print(f"  -> Excised {len(filler_intervals)} hesitations. Split into {len(segments)} clean takes.")

    if not segments:
        print("[-] No speech detected in video or audio track is silent.")
        sys.exit(1)

    # Step 2: Vision & Director Shot Planning
    print("\n[Phase 2/3] Summoning Virtual Camera Director & Framing...")
    tracker = VisionTracker(input_path)
    print(f"  -> Source Resolution: {tracker.metadata.width}x{tracker.metadata.height} @ {tracker.metadata.fps:.1f} fps")

    broll_mgr = None
    if args.broll:
        if os.path.isdir(args.broll):
            broll_mgr = BRollManager(args.broll)
            print(f"  -> B-Roll Media: Loaded {len(broll_mgr.assets)} assets from '{args.broll}'")
        else:
            print(f"  [!] Warning: B-Roll directory not found: '{args.broll}'. Proceeding without B-roll.")

    director = CameraDirector(
        tracker=tracker,
        pacing_style=args.pacing,
        zoom_factor=args.zoom,
        target_resolution=args.resolution,
        broll_manager=broll_mgr,
        min_broll_speech_dur=args.broll_min_dur,
        broll_cutaway_dur=args.broll_length,
        enable_freeze_frames=args.freeze_frame,
        freeze_duration=args.freeze_dur,
        transition_style=args.transition,
        target_person=args.target_person,
    )
    shot_plans = director.plan_production(segments)

    # Print cut sheet
    cut_sheet = generate_cut_sheet(shot_plans, raw_duration)
    print("\n" + cut_sheet)

    if args.dry_run:
        print("\n[+] Dry run complete. Reruns without --dry-run to produce finished video.")
        sys.exit(0)

    # Step 3: High-Performance Multi-Angle Rendering
    print("\n[Phase 3/3] Orchestrating FFmpeg Multi-Camera Render Engine...")

    res_map = {
        "1080p": (1920, 1080),
        "4k": (3840, 2160),
        "720p": (1280, 720),
    }
    base_w, base_h = res_map[args.resolution]
    if tracker.metadata.is_portrait:
        target_w, target_h = base_h, base_w
        print(f"  -> Detected Orientation: PORTRAIT (Vertical {target_w}x{target_h})")
    else:
        target_w, target_h = base_w, base_h
        print(f"  -> Detected Orientation: LANDSCAPE (Horizontal {target_w}x{target_h})")

    render_config = RenderConfig(
        target_width=target_w,
        target_height=target_h,
        is_portrait=tracker.metadata.is_portrait,
        color_grade=args.color,
        normalize_audio=not args.no_normalize_audio,
        highpass_audio=not args.no_normalize_audio,
        bgm_path=args.bgm,
        bgm_volume=args.bgm_volume,
        enable_captions=args.captions,
        caption_color=args.caption_color,
        whisper_model=args.whisper_model,
        captions_file=args.captions_file,
        stabilize=args.stabilize,
        stabilize_smoothing=args.stabilize_smoothing,
        broll_dir=args.broll,
        broll_min_dur=args.broll_min_dur,
        broll_length=args.broll_length,
        transition_style=args.transition,
        enable_freeze_frames=args.freeze_frame,
        freeze_duration=args.freeze_dur,
        enable_sfx=args.sfx,
        sfx_volume=args.sfx_volume,
        show_hud=not args.no_hud,
        show_title=bool(args.title),
        title_text=args.title,
        subtitle_text=args.subtitle,
        letterbox=args.letterbox,
        film_grain=args.film_grain,
        fx_glow=args.fx_glow,
        fx_rgb_split=args.fx_rgb,
        fx_camera_motion=args.fx_motion,
        fx_camcorder_osd=args.fx_camcorder,
        fx_tilt_shift=args.fx_tilt_shift,
        fx_flicker=args.fx_flicker,
        overlay_effect=args.overlay,
        overlay_blend_mode=args.overlay_blend,
        overlay_opacity=args.overlay_opacity,
        overlay_target=args.overlay_target,
        target_person=args.target_person,
        selective_color=args.selective_color,
        force_chunk_mode=args.chunk_mode,
    )

    engine = RenderEngine(input_path, config=render_config)

    def on_progress(pct: float, msg: str):
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {int(pct*100):>3}% - {msg}", end="", flush=True)

    t0 = time.time()
    try:
        engine.render(shot_plans, output_path, progress_callback=on_progress)
        print()
    except Exception as e:
        print(f"\n[-] Rendering Error: {e}")
        sys.exit(1)

    t_render = time.time() - t0
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)

    print("\n" + "=" * 65)
    print(" [✓] PRODUCTION COMPLETE - OMNICAM FINISHED MASTER")
    print("=" * 65)
    print(f" Output Video:     {output_path}")
    print(f" File Size:        {file_size_mb:.2f} MB")
    print(f" Render Time:      {t_render:.1f} seconds")
    print(f" Angles Used:      Wide, Close-Up, Rule-of-Thirds, Dynamic Push")
    print(f" Ready to upload:  YouTube, Shorts, Reels, TikTok, Podcasts")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()

