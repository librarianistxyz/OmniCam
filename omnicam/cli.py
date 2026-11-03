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
        choices=["cinematic", "podcast", "vintage", "none"],
        default="cinematic",
        help="Color grading profile (default: cinematic)",
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

