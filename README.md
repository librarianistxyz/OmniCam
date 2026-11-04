# 🎬 OmniCam: Autonomous Multi-Camera Director & Studio Workstation

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Android%20(Termux)%20%7C%20macOS%20%7C%20Windows-green.svg)](https://github.com/librarianistxyz/OmniCam)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Offline%20%7C%20Zero%20Cloud-orange.svg)](https://github.com/librarianistxyz/OmniCam)

> **Transform raw single-camera phone or webcam footage into a multi-camera studio master — fully automated, zero cloud, 100% offline.**

---

## 🌟 The Vision

When you record yourself speaking, awkward pauses, breaths, and hesitations naturally occur. Standard jump cuts look amateurish and jarring because your face snaps abruptly in the exact same frame.

Professional studios (TED, Vox, Wired, Joe Rogan) hide cuts by **switching camera angles**:
- Sentence A ends on a **Master Wide** angle.
- Dead air is instantly removed.
- Sentence B punches in on an intimate **Tight Close-Up** or **Rule-of-Thirds Offset**.

**OmniCam automates this entire production workflow in real time with zero cloud dependency.**

```
+---------------------------------------------------------------------------------+
|                                RAW 4K FOOTAGE                                   |
|   "Hey everyone..." [pause 1.2s] "...today I'm revealing..." [pause 0.8s]       |
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
                     [ 🎬 OmniCam Director Engine ]
                     ├── Acoustic Silence & Vocal Hesitation Detection
                     ├── Face & Horizon Framing Engine
                     ├── Zero-Jump-Cut Multi-Cam State Machine
                     ├── Real-Time Virtual Playhead GPU Composition
                     └── EBU R128 Studio Audio Mastering & Sidechain Ducking
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
|                           MULTI-CAMERA 1080p MASTER                             |
|  [Cam 1: Wide]            ──>  [Cam 2: Tight Close-up]  ──>  [Cam 3: Ken Burns] |
|  "Hey everyone..."              "...today I'm revealing..."  "a brand new engine"|
|               (0s dead air, smooth studio cadence, pro color & FX)               |
+---------------------------------------------------------------------------------+
```

---

## 📋 System Requirements

| Component | Minimum | Recommended | Notes |
| :--- | :--- | :--- | :--- |
| **Operating System** | Linux, Android (Termux), macOS, Windows (WSL2) | Linux / Android 8.0+ | Zero external cloud servers needed. |
| **Python** | Python 3.8+ | Python 3.10 - 3.12 | Uses standard library (`http.server`, `subprocess`). |
| **FFmpeg** | FFmpeg 4.4+ with `ffprobe` | FFmpeg 6.0+ | Handles encoding, filtering, and video decoders. |
| **Git** | Any modern version | Latest | For cloning and pulling repository updates. |
| **Whisper** *(Optional)* | Python `openai-whisper` | `tiny.en` or `base.en` | For auto-subtitles and lexical filler word removal. |

---

## 📱 Android Setup (Termux Guide)

### 1. Where to Download Termux ("Termer")

> ⚠️ **IMPORTANT WARNING:**  
> **DO NOT install Termux from the Google Play Store!**  
> The Google Play Store build of Termux has been obsolete and deprecated since 2020 due to Android SDK restrictions. It will fail with `pkg update` errors.

Download the latest official Termux build from either of these verified sources:

1. **F-Droid (Recommended):**  
   👉 [Download Termux on F-Droid](https://f-droid.org/packages/com.termux/)  
   *(Click "Download APK" near the bottom of the page)*

2. **Official GitHub Releases:**  
   👉 [Download Termux on GitHub Releases](https://github.com/termux/termux-app/releases)  
   *(Select `termux-app_v..._universal.apk` or `arm64-v8a.apk`)*

---

### 2. Step-by-Step Installation on Android

Open Termux on your phone and run these commands:

```bash
# Step 1: Update core repositories and package lists
pkg update -y && pkg upgrade -y

# Step 2: Install Git, Python, and FFmpeg
pkg install -y git python ffmpeg

# Step 3: Grant storage permission (allows accessing phone camera/downloads)
termux-setup-storage
```
*(When prompted on your phone screen, tap **Allow** to grant storage access).*

```bash
# Step 4: Clone the OmniCam repository
git clone https://github.com/librarianistxyz/OmniCam.git

# Step 5: Enter directory and launch Web Studio
cd OmniCam
./omnicam.sh --web
```

Now open **Google Chrome** (or any mobile browser) on your phone and visit:  
👉 **`http://localhost:8080`**

---

## 💻 PC Setup Guide (Linux, macOS & Windows)

### 🐧 Linux (Ubuntu / Debian / Mint / Fedora / Arch)

```bash
# Step 1: Install prerequisites
# On Ubuntu / Debian / Mint:
sudo apt update && sudo apt install -y git python3 python3-pip ffmpeg

# On Fedora:
sudo dnf install -y git python3 python3-pip ffmpeg

# On Arch Linux:
sudo pacman -S git python ffmpeg

# Step 2: Clone repository
git clone https://github.com/librarianistxyz/OmniCam.git
cd OmniCam

# Step 3: Launch Web Studio or CLI
./omnicam.sh --web
```
Open **`http://localhost:8080`** in your browser.

---

### 🍏 macOS (Apple Silicon M1/M2/M3 & Intel)

```bash
# Step 1: Install Homebrew (if not installed) from https://brew.sh
# Step 2: Install dependencies
brew install git python ffmpeg

# Step 3: Clone repository
git clone https://github.com/librarianistxyz/OmniCam.git
cd OmniCam

# Step 4: Launch Web Studio
./omnicam.sh --web
```
Open **`http://localhost:8080`** in Safari or Chrome.

---

### 🪟 Windows (WSL2 / Git Bash)

#### Method A: WSL2 Ubuntu (Recommended for max speed)
1. Open PowerShell and install WSL if needed: `wsl --install`
2. Open your **Ubuntu** terminal in Windows and run:
   ```bash
   sudo apt update && sudo apt install -y git python3 ffmpeg
   git clone https://github.com/librarianistxyz/OmniCam.git
   cd OmniCam
   python3 omnicam.py --web
   ```
3. Open Edge or Chrome in Windows and go to: **`http://localhost:8080`**

#### Method B: Native Windows (Git Bash + Python)
1. Install [Git for Windows](https://git-scm.com/download/win) and [Python 3](https://www.python.org/downloads/).
2. Install [FFmpeg for Windows](https://www.gyan.dev/ffmpeg/builds/) and add its `bin` folder to your Windows system `PATH`.
3. Open Git Bash or Command Prompt:
   ```bash
   git clone https://github.com/librarianistxyz/OmniCam.git
   cd OmniCam
   python omnicam.py --web
   ```
4. Open **`http://localhost:8080`** in your browser.

---

## 🔄 How to Pull & Update (Phone & PC)

Whenever new features, transitions, or FX are released, update your local installation anytime:

```bash
# Open terminal (in Termux, Linux, macOS, or Windows WSL)
cd ~/OmniCam

# Fetch and merge the latest code
git pull origin master
```

---

## 🎨 What's Inside: The Full Creative Suite

### 1. ⚡ Real-Time Virtual Playhead Engine
- **Instant Cut Previews**: Live seek-skipping cuts dead air in under 1ms without rendering.
- **Dynamic 60 FPS Camera Framing**: Uses hardware-accelerated viewport transforms to punch in on angles live.
- **Live 3D LUT Color Sync**: Switch between Cinematic, Podcast, Vintage, or Noir grades instantly.

### 2. 🪄 CapCut Transitions & Freeze Frames
- **White Flash & Crash Zoom**: 0.08s flash and punch-in transitions between angle cuts.
- **Dramatic 0.6s Freeze Frames**: Pauses on emphatic pauses with synthesized whoosh sound effects.

### 3. ✨ Blend Mode Overlays (`--overlay` & `--overlay-target`)
- **Sci-Fi & High-Tech HUD Suite**:
  - `cyber_hud_matrix` (Futuristic targeting rings, telemetry grid & radar scan)
  - `holo_matrix_grid` (3D cyber wireframe floor & wall matrix grid)
  - `neural_circuit_core` (Glowing electronic circuit traces & neon data packets)
  - `tactical_sonar_radar` (Circular sci-fi sonar sweep beam & range rings)
  - `quantum_particles_stream` (Floating luminescent cyber dust bokeh stream)
- **Cinematic Film Suite**:
  - `light_leak_01` (Golden flare edge leaks)
  - `light_leak_02` (Sunset crimson burst)
  - `film_dust_scratches` (16mm/35mm organic dust specks)
  - `vhs_static_overlay` (90s retro tracking CRT static)
  - `prism_bokeh` (Floating optical prism bokeh)
  - `film_burn_01` (Fiery amber film burn)
  - `vintage_super8` (Super 8mm projector gate)
- **Subject-Isolation Background Masking** (`--overlay-target background_only`):
  - In Web Studio and FFmpeg rendering, puts the high-tech matrix and telemetry overlays **behind the speaker**, keeping the face, hair, and torso completely clean and untouched.

### 4. 🎛️ Visual Effects (FX) Suite
- **Pro-Mist Diffusion Bloom** (`--fx-glow promist`): Creamy highlights & smooth skin tones.
- **Chromatic RGB Aberration** (`--fx-rgb subtle`): Optical anamorphic lens edge fringing.
- **Organic Handheld Cam Drift** (`--fx-motion handheld`): Natural operator breathing on static tripod shots.
- **Action Impact Quake** (`--fx-motion quake`): Punchy cut & beat shudder.
- **90s Camcorder Viewfinder OSD** (`--fx-camcorder`): Retro HUD with blinking `REC ●`, battery, and timecode.
- **Portrait Depth Blur** (`--fx-tilt-shift`): Soft background bokeh keeping speaker face in focus.
- **Analog 35mm Film Grain** (`--film-grain`): Organic silver halide texture.
- **2.35:1 Anamorphic Cinema Bars** (`--letterbox`): Widescreen top/bottom letterbox.

---

## 🚀 Quick CLI Reference

```bash
# Standard automated multi-camera production
./omnicam.sh recording.mp4

# Full viral short / TikTok production setup
python3 omnicam.py recording.mp4 \
  --remove-fillers \
  --color cinematic \
  --fx-glow promist \
  --fx-motion handheld \
  --overlay light_leak_01 \
  --overlay-opacity 0.75 \
  --captions \
  --caption-color yellow \
  --bgm ambient \
  --bgm-volume 0.20 \
  --letterbox \
  -o finished_viral_master.mp4
```

---

## 🧪 Verification & Synthetic Tests

Run the built-in end-to-end verification suite:

```bash
python3 test_omnicam.py
```

Generates a synthetic 4K video, runs the acoustic silence detector, camera director, B-roll insertion, animated captions, and FFmpeg filtergraph pipeline to verify 100% compliance.

---

## 📄 License & Attribution

Licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.  
See the [LICENSE](LICENSE) file for complete details.

**Copyright (C) 2026 librarianistxyz (<https://github.com/librarianistxyz/OmniCam>)**
