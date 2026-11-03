# 🎬 OmniCam: AI Virtual Multi-Camera Director

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Android%20(Termux)-green.svg)](https://github.com/librarianistxyz/OmniCam)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Offline%20%7C%20Zero%20Cloud-orange.svg)](https://github.com/librarianistxyz/OmniCam)

> **Transform raw, handheld single-camera phone footage into a multi-camera studio production — fully automated, zero cloud, 100% offline.**

---

## 🌟 The Vision

When you record yourself speaking on a smartphone, you naturally pause, hesitate, take breaths, or lose your train of thought. Standard video editors either leave all that awkward dead air in, or make crude **jump cuts** that look amateurish and jarring because your face snaps abruptly in the exact same frame.

Professional studios (TED, Vox, Wired, Joe Rogan) hide cuts by **switching camera angles**:
- Sentence A ends on a **Master Wide** angle.
- The silence is eliminated.
- Sentence B starts on an intimate **Punch-In Close-Up** or **Rule-of-Thirds Offset**.

**OmniCam automates this entire production workflow instantly.**

```
+---------------------------------------------------------------------------------+
|                                RAW 4K FOOTAGE                                   |
|   "Hey everyone..." [pause 1.2s] "...today I'm revealing..." [pause 0.8s]       |
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
                     [ 🧠 OmniCam AI Director Engine ]
                     ├── Acoustic Silence Detection
                     ├── Face & Headroom Horizon Tracking
                     ├── Zero-Jump-Cut State Machine
                     └── EBU R128 Studio Audio Mastering
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
|                           MULTI-CAMERA 1080p MASTER                             |
|  [Cam 1: Wide]            ──>  [Cam 2: Tight Close-up]  ──>  [Cam 3: Ken Burns] |
|  "Hey everyone..."              "...today I'm revealing..."  "a brand new engine"|
|               (0s dead air, smooth studio cadence, pro color)                    |
+---------------------------------------------------------------------------------+
```

---

## 📐 The 4K Mathematics: Native Clarity

A 4K recording (**3840×2160**) possesses **4× the pixel density** of Full HD 1080p (**1920×1080**):

$$\text{Area}_{4K} = 3840 \times 2160 = 8,294,400\text{ pixels}$$
$$\text{Area}_{1080p} = 1920 \times 1080 = 2,073,600\text{ pixels}$$

By cropping into distinct regions of a 4K sensor (up to $1.8\times$ zoom) and rendering a 1080p master, **every virtual camera angle is 100% native resolution** with zero upscaling blur or pixelation.

---

## 🎥 The 5 Virtual Cameras

| Virtual Camera | Description | Purpose |
| :--- | :--- | :--- |
| **Cam 1: Master Wide** | Full frame scaled to 1080p | Context, establishing posture, relaxed delivery. |
| **Cam 2: Tight Close-Up** | $1.75\times$ crop centered on speaker's eyes/mouth | High-impact punchlines, emotional hooks, emphasis. |
| **Cam 3: Rule-of-Thirds Left** | Subject framed on left-third line looking right | Conversational interview depth and perspective. |
| **Cam 4: Rule-of-Thirds Right** | Subject framed on right-third line looking left | Dynamic perspective balance against Cam 3. |
| **Cam 5: Ken Burns Slow Push-In**| Continuous micro-zoom ($1.0\times \to 1.2\times$) | Keeps long explanations (>4s) visually engaging. |

---

## ✨ Features

- **🌐 Localhost Mobile Web Studio (`http://localhost:8080`)**: Zero-dependency browser interface running inside Termux on your phone. Visual interactive timeline of all cuts, color grading & ducking sliders, storage video scanner, and one-tap rendering with in-browser video player.
- **⚡ Invisible Cut Engine**: Silences and pauses are removed. Every single cut triggers an automatic angle switch so the edit feels natural and deliberate.
- **🗣️ Filler Word & Vocal Hesitation Removal (`--remove-fillers`)**: Dual-engine lexical (Whisper token matching) and acoustic spectral stationarity filter detects prolonged vocal hesitations ("uh", "um", "ah", "like", "you know") and cuts them out cleanly, turning awkward hesitations into dynamic angle switches.
- **🎞️ Automatic B-Roll Cutaways (`--broll ./clips/`)**: When explaining concepts for extended takes (>4s), OmniCam automatically cuts to relevant footage or still photos for 2–3s with smooth Ken Burns drift, keeping your voiceover seamless underneath.
- **🎥 Digital Gimbal Horizon Stabilization**: 2-pass optical motion analysis (`vidstabdetect` / `vidstabtransform`) stabilizes walking bounce, handheld camera shake, and horizon tilt—rendering butter-smooth gimbal motion without heavy hardware rigs.
- **🎙️ Studio Audio Mastering**:
  - High-pass filter at 80Hz (eliminates handling thumps and wind rumble).
  - Sidechain compressed auto-ducking background music (`--bgm`) that ducks ~22dB during speech and swells in pauses.
  - EBU R128 Loudness Normalization (`loudnorm`, -16 LUFS, ready for YouTube/Reels/TikTok).
  - Boundary micro-fades to prevent clicks and pops.
- **🔤 Hormozi / MrBeast Active-Word Animated Captions**: Offline Whisper transcription generates high-contrast neon subtitles that light up word-by-word synchronously with speech, remapped mathematically across edited takes.
- **🎨 Cinematic Color Grading**:
  - `cinematic`: Contrast S-curve, warm highlights, subtle cool shadow balance.
  - `podcast`: Vibrant modern YouTube tech aesthetic.
  - `vintage`: Muted documentary warmth.
  - `none`: Raw camera pass-through.
- **🛡️ Zero-Dependency Architecture**: Runs with pure Python standard library + FFmpeg. If OpenCV is present, it dynamically tracks the speaker's face; otherwise, it uses the Golden-Ratio Talking Head heuristic.
- **📱 Fully Mobile & Termux Compatible**: Pull this repo to Termux on your Samsung Galaxy S9+ (or any Android device) and edit 4K video right on your phone without sending a single byte to the cloud.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.8+
- FFmpeg & FFprobe installed and available in PATH.

### 2. Basic Usage

```bash
# Option A: Visual Web Studio on your phone (Open http://localhost:8080 in Chrome)
./omnicam.sh --web

# Option B: Automated CLI edit
./omnicam.sh my_4k_recording.mp4
```

### 3. Dry-Run (Preview Cut Sheet)

Before rendering, inspect the timestamps, removed pauses, and assigned camera angles without waiting for encoding:

```bash
python3 omnicam.py my_video.mp4 --preview
```

**Example Output:**
```
================================================================================
#   START     END       DUR     ANGLE         DIRECTOR NOTE
--------------------------------------------------------------------------------
1     0.00s    3.10s    3.10s  CLOSEUP       Tight Close-Up Punch-In (High Emotional Emphasis, 3.1s)
2     4.50s    7.60s    3.10s  WIDE          Master Wide Shot (Full Scene Context, 3.1s)
3     8.90s   14.20s    5.30s  SLOW_PUSH     Cinematic Slow Push-In (Continuous Focus, 5.3s)
================================================================================
Original Length: 00:15.50 (15.50s)
Edited Length:   00:11.50 (11.50s)
Dead Air Cut:    00:04.00 (4.00s, -25.8%)
Total Camera Switches: 3
================================================================================
```

---

## 🎛️ Advanced Options

```bash
python3 omnicam.py input.mp4 \
  --remove-fillers \          # Cut filler words ('uh', 'um', 'ah', 'like', 'you know') and vocal hesitations
  --fillers "uh,um,like" \    # Custom target filler words to excise (optional)
  --broll ./clips/ \          # Auto B-roll folder: cuts to secondary footage/photos during long takes (>4s)
  --broll-min-dur 4.0 \       # Minimum speech duration to trigger B-roll (default: 4.0s)
  --broll-length 2.5 \        # Cutaway duration in seconds (default: 2.5s)
  --stabilize \               # 2-pass Digital Gimbal Horizon Stabilization (walking & shake fix)
  --stabilize-smoothing 25 \  # Gimbal smoothing radius in frames (default: 25)
  --pacing dynamic \          # Director pacing: dynamic, podcast, documentary, dramatic
  --color cinematic \         # Color grade: cinematic, podcast, vintage, none
  --captions \                # Burn dynamic "Hormozi / MrBeast" active-word animated subtitles
  --caption-color yellow \    # Highlight color: yellow, green, cyan, red, white
  --bgm /path/to/lofi.mp3 \   # Auto-ducking BGM audio track (or 'ambient'/'lofi')
  --bgm-volume 0.22 \         # Music level before ducking (ducks to -22dB during speech)
  --title "MY PODCAST" \      # Opening lower-third title banner
  --subtitle "EPISODE 1" \    # Opening lower-third subtitle
  --silence-thresh -32.0 \    # Sensitivity in dB (lower = only quietest pauses cut)
  --min-silence 0.35 \        # Minimum pause in seconds to trigger cut
  --zoom 1.75 \               # Punch-in zoom factor
  --resolution 720p \         # Target output: 720p (default), 1080p, 4k
  -o finished_master.mp4
```

---

## 📱 Running in Termux on Samsung Galaxy S9+

1. **Install dependencies in Termux**:
   ```bash
   pkg update && pkg install -y git python ffmpeg
   ```

2. **Clone repository**:
   ```bash
   git clone https://github.com/librarianistxyz/OmniCam.git
   cd OmniCam
   ```

3. **Record in 4K on Phone Camera**:
   - Open Camera $\to$ Settings $\to$ Rear Video Size $\to$ **UHD / 4K (3840x2160)**.
   - Record your speech holding the phone naturally.

4. **Launch Web Studio or CLI**:
   ```bash
   # Termux storage access
   termux-setup-storage

   # Option A: Visual Web Studio (open http://localhost:8080 in Chrome)
   ./omnicam.sh --web

   # Option B: Automated CLI edit
   ./omnicam.sh ~/storage/dcim/Camera/20261103_120000.mp4 -o ~/storage/dcim/Camera/edited_studio.mp4
   ```

---

## 🧪 Verification & Tests

Run the built-in end-to-end synthetic verification test suite:

```bash
python3 test_omnicam.py
```

This generates a synthetic 4K video with spoken tones and silence gaps, executes the full silence detector, camera director, B-roll insertions, animated captions, and render engine, verifying zero-jump-cut compliance and audio normalization automatically.

---

## 📄 License & Attribution

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.  
See the [LICENSE](LICENSE) file for complete details.

**Copyright (C) 2026 librarianistxyz (<https://github.com/librarianistxyz/OmniCam>)**

*Under the AGPLv3, you are free to run, study, modify, and distribute this software, provided that any derivative works or network deployments (including web services or SaaS) remain 100% open-source under the exact same AGPLv3 terms with original author copyright notices preserved.*

