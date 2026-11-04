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

### 3. ✨ 54+ Studio Blend Mode Overlays (`--overlay` & `--overlay-target`)
- **⚛️ Oppenheimer & Atomic Suite (8 Presets)**:
  - `oppenheimer_trinity_fire`: Scorched fiery nuclear fission embers & atmospheric plasma flames (Trinity test).
  - `oppenheimer_imax_mono`: IMAX 70mm high-contrast black & white silver halide grain & negative gate breathing.
  - `oppenheimer_radiation_glow`: Luminous Cherenkov radiation ultraviolet-cyan reactor pulse bloom.
  - `oppenheimer_quantum_waves`: Subatomic wave-particle interference fringes & probability ripples.
  - `oppenheimer_atomic_sparks`: Swirling uranium core fission sparks, radiant embers & glowing isotopes.
  - `oppenheimer_los_alamos_dust`: Arid New Mexico desert windblown micro-grit & thermal sun haze.
  - `oppenheimer_fission_burst`: Strobe atomic chain-reaction flashes & expanding fireball luminance.
  - `oppenheimer_trinity_shockwave`: Supersonic atmospheric pressure wave refraction ring.
- **🕵️ Sherlock & Victorian Noir Suite (8 Presets)**:
  - `sherlock_baker_st_fog`: Dense London Thames river fog & 1890s coal-smoke mist rolling across streets.
  - `sherlock_gaslamp_glow`: Flickering Victorian street gaslamp amber flare, soot halo & warm cobblestone glow.
  - `sherlock_cobblestone_rain`: Moody vertical English drizzle, rain streaks & dark wet pavement reflections.
  - `sherlock_pipe_smoke`: Graceful tobacco smoke tendrils drifting lazily through the study.
  - `sherlock_victorian_dust`: Suspended vintage room dust motes illuminated by leaded window sunbeams.
  - `sherlock_candlelight_flicker`: Intimate 221B Baker Street oscillating candlelight glow & breathing shadows.
  - `sherlock_wet_carriage_glass`: Rain droplets trickling down the glass of a Victorian hansom cab window.
  - `sherlock_antique_parchment`: Aged yellowed manuscript texture, tea-stain border vignette & fiber grain.
- **🎞️ Vintages & Old Films Suite (12 Presets)**:
  - `vintage_super8`: Super 8mm mechanical projector gate jitter, corner vignette & optical jitter.
  - `vintage_16mm_grain`: French New Wave 16mm Kodak Tri-X silver halide organic grain.
  - `vintage_35mm_dust`: 35mm cinema reel scratches, black hair artifacts & organic dust specks.
  - `vintage_nitrate_burn`: 1920s flammable nitrate film edge melting & burning amber flare.
  - `vintage_silent_1920`: Silent cinema gate weave, frame stutter & optical vignetting.
  - `vintage_technicolor_leak`: 3-strip dye transfer magenta/cyan optical light bleed.
  - `vintage_kodachrome_64`: 1970s Kodachrome slide color bleeding & golden sunlight wash.
  - `vintage_film_leader`: Mechanical countdown leader frame flash, sprockets & crosshairs.
  - `vintage_damaged_tape`: VHS magnetic oxide tape loss, tracking jitter & line dropouts.
  - `vintage_polaroid_fade`: 1980s instant film chemical dispersion border & pastel wash.
  - `vintage_sepia_saloon`: 19th-century daguerreotype antique sepia toning & silver tarnish.
  - `vintage_drive_in_grain`: Outdoor drive-in projector light dust beam & reel flutter.
- **🔥 Light Leaks, Film Burns & Prisms (10 Presets)**:
  - `light_leak_01`, `light_leak_02`, `light_leak_warm_radial`, `light_leak_cyan_streak`
  - `film_burn_01`, `film_burn_02`, `film_burn_slow_amber`, `film_burn_solar_white`
  - `prism_bokeh`, `prism_refraction_halo`
- **⚡ Sci-Fi & Cyberpunk Telemetry (10 Presets)**:
  - `cyber_hud_matrix`, `holo_matrix_grid`, `neural_circuit_core`, `tactical_sonar_radar`, `quantum_particles_stream`
  - `glitch_digital`, `retro_crt_scanlines`, `cyber_matrix_rain`, `cyber_hex_shield`, `lens_flare_anamorphic`
- **✨ Atmosphere & Elements (6 Presets)**:
  - `golden_particles`, `cinema_smoke_fog`, `snow_frost_drift`, `ember_fire_sparks`, `lens_dirt_grime`, `stage_concert_lasers`
- **👤 Subject-Isolation Masking & Person Tracking (`--target-person`, `--selective-color`, `--overlay-target`)**:
  - **Track Specific Speaker**: Select between `primary` (main speaker), `left` / `person_1`, `right` / `person_2`, or `center`.
  - **Selective Color Isolation (Sin City / Oppenheimer Splash)**:
    - `person_color_bg_mono`: Tracked speaker stays in natural color while background & others turn into Oppenheimer 70mm B&W.
    - `person_color_bg_sherlock`: Tracked speaker stays in natural color while background turns into Victorian foggy sepia.
    - `person_color_bg_oppenheimer`: Tracked speaker stays in color while background turns into atomic fission amber.
    - `person_grade_only`: Apply color grade ONLY to the tracked person.
    - `bg_grade_only`: Apply color grade ONLY to the background behind the speaker.
  - **Behind-the-Speaker Overlay Placement** (`--overlay-target background_only`):
    - Places the high-tech matrix, film burn, or vintage dust behind the speaker, leaving their face and body untouched.

### 4. 🎛️ Visual Effects (FX) Suite
- **Pro-Mist Diffusion Bloom** (`--fx-glow promist`): Creamy highlights & smooth skin tones.
- **Chromatic RGB Aberration** (`--fx-rgb subtle`): Optical anamorphic lens edge fringing.
- **Organic Handheld Cam Drift** (`--fx-motion handheld`): Natural operator breathing on static tripod shots.
- **Action Impact Quake** (`--fx-motion quake`): Punchy cut & beat shudder.
- **90s Camcorder Viewfinder OSD** (`--fx-camcorder`): Retro HUD with blinking `REC ●`, battery, and timecode.
- **Portrait Depth Blur** (`--fx-tilt-shift`): Soft background bokeh keeping speaker face in focus.
- **Analog 35mm Film Grain** (`--film-grain`): Organic silver halide texture.
- **2.35:1 Anamorphic Cinema Bars** (`--letterbox`): Widescreen top/bottom letterbox.

### 5. 🎵 Music Video Studio Mode (`--music-mode` & `--song`)
Turn raw multi-take shoot footage into a MTV / Cole Bennett style music video locked to the song:
- **1. Multi-Take Waveform Auto-Sync (Lip-Sync Alignment)**:
  - Uses FFT cross-correlation (`np.fft.rfft` / `np.fft.irfft`) with zero external libraries.
  - Compares noisy camera scratch audio against the clean Studio Master audio file (`song.wav` or `master.mp3`).
  - Detects the exact millisecond offset ($\Delta t$) of each take to lock all camera angles in phase.
- **2. Beat & Energy Grid Detection (`MusicBeatAnalyzer`)**:
  - Detects BPM tempo, 4/4 measure bar downbeats, kick drum / 808 sub-bass drops (20–140 Hz), and snare transients (1.5–4.5 kHz).
  - Classifies song structure: Intro/Verse (slower 4–8 bar cadence), Pre-Chorus/Build-up (2-bar tension cadence), and Chorus/Drop (1-bar rapid cuts).
- **3. Musical Virtual Camera Directing (`MusicVideoDirector`)**:
  - **The 808 / Drop Punch-In**: Instant snap from Master Wide directly into an aggressive Extreme Close-Up centered on the singer's face.
  - **Dutch Tilt & Counter-Pans**: Alternating angles across measures (Bar 1: Thirds Left, Bar 2: Thirds Right, Bar 3: Zoom push).
  - **Multi-Take Rotation**: Seamlessly switches between takes (`Take 1 Wide`, `Take 2 Close-up`, `Take 3 Performance`) staying in phase ($T_{\text{take}} = T_{\text{song}} - \Delta t$).
- **4. Beat-Reactive Visual Effects (`--beat-fx`)**:
  - Downbeat lens flares, fiery film burns on chorus starts, and chromatic RGB glitch flashes on 808 drops.
- **5. Speed Ramping & Motion Pumping (`--speed-ramps` & `--bass-pump`)**:
  - **Speed Ramping**: Slow-motion 60% cruise during vocal sustained notes snapping into 250% acceleration into cuts.
  - **Bass Pump**: Sub-bass camera vibration synced to kick frequencies via mathematical exponential oscillation.

```bash
# Full Music Video Production with Multi-Take Auto-Sync
python3 -m omnicam.cli take1_wide.mp4 \
  --music-mode \
  --song studio_master.wav \
  --takes take2_closeup.mp4 take3_performance.mp4 \
  --bass-pump \
  --speed-ramps \
  --beat-fx \
  --color cinematic \
  -o finished_music_video.mp4
```

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
