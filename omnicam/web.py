"""
Localhost Mobile Web Studio for OmniCam
Lightweight zero-dependency web interface running inside Termux on port 8080.
"""

import http.server
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from dataclasses import asdict
from typing import Dict, List, Optional

from .audio_analyzer import AudioAnalyzer, SpeechSegment
from .broll import BRollManager
from .captions import WordTiming
from .director import CameraAngle, CameraDirector, ShotPlan
from .filler_remover import (
    DEFAULT_FILLER_WORDS,
    detect_acoustic_hesitations,
    detect_lexical_fillers,
    remove_filler_intervals,
)
from .render_engine import RenderConfig, RenderEngine
from .vision_tracker import VisionTracker


class StudioServerState:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_rendering: bool = False
        self.progress: float = 0.0
        self.status_message: str = "Ready"
        self.output_file: Optional[str] = None
        self.error: Optional[str] = None


STATE = StudioServerState()


def scan_media_files() -> List[Dict[str, str]]:
    """Scans common Android and workspace directories for video recordings."""
    candidate_dirs = [
        "/sdcard/Movies",
        "/sdcard/DCIM/Camera",
        "/sdcard/Download",
        os.path.expanduser("~/storage/movies"),
        os.path.expanduser("~/storage/dcim/Camera"),
        os.getcwd(),
    ]
    found = []
    seen = set()

    for d in candidate_dirs:
        if os.path.isdir(d):
            try:
                for entry in os.listdir(d):
                    lower = entry.lower()
                    if lower.endswith((".mp4", ".mov", ".mkv", ".webm")):
                        full = os.path.abspath(os.path.join(d, entry))
                        if full not in seen and os.path.isfile(full):
                            seen.add(full)
                            try:
                                sz = os.path.getsize(full)
                                sz_mb = f"{sz / (1024 * 1024):.1f} MB"
                            except OSError:
                                sz_mb = "N/A"
                            found.append({"path": full, "name": entry, "size": sz_mb, "dir": d})
            except Exception:
                continue

    return found


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>OmniCam Studio</title>
  <style>
    :root {
      --bg: #0F172A;
      --card-bg: #1E293B;
      --card-border: #334155;
      --input-bg: #0B1120;
      --primary: #2563EB;
      --primary-hover: #1D4ED8;
      --primary-focus: rgba(37, 99, 235, 0.35);
      --success: #10B981;
      --danger: #EF4444;
      --text-main: #F8FAFC;
      --text-secondary: #94A3B8;
      --text-muted: #64748B;
      --radius: 8px;
      --radius-lg: 12px;
      --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", Helvetica, Arial, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg);
      color: var(--text-main);
      font-family: var(--font-stack);
      line-height: 1.5;
      padding: 1.5rem 1rem 5rem;
      color-scheme: dark;
      accent-color: var(--primary);
      -webkit-font-smoothing: antialiased;
    }

    .container {
      max-width: 900px;
      margin: 0 auto;
    }

    /* Header */
    header {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-lg);
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.5rem;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }

    .brand-group h1 {
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: -0.3px;
      color: #FFFFFF;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .brand-group p {
      font-size: 0.85rem;
      color: var(--text-secondary);
      margin-top: 0.2rem;
    }

    .status-badge {
      font-size: 0.75rem;
      padding: 0.35rem 0.75rem;
      border-radius: 9999px;
      background: #0284C7;
      color: #FFFFFF;
      font-weight: 600;
      letter-spacing: 0.3px;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #38BDF8;
    }

    /* Section & Cards */
    .section-title {
      font-size: 0.85rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--text-secondary);
      margin-bottom: 0.75rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-lg);
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.5rem;
    }

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--card-border);
    }

    .card-heading {
      font-size: 1.05rem;
      font-weight: 700;
      color: #FFFFFF;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    /* Form Inputs */
    label {
      display: block;
      font-size: 0.82rem;
      font-weight: 600;
      color: var(--text-secondary);
      margin-bottom: 0.4rem;
      margin-top: 0.9rem;
    }

    label:first-child { margin-top: 0; }

    input[type="text"], select {
      width: 100%;
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      color: #FFFFFF;
      padding: 0.7rem 0.9rem;
      border-radius: var(--radius);
      font-size: 0.92rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }

    input[type="text"]:focus, select:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--primary-focus);
    }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      padding: 0.75rem 1.25rem;
      border-radius: var(--radius);
      font-size: 0.92rem;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      border: none;
      transition: background-color 0.15s, opacity 0.15s;
      text-decoration: none;
    }

    .btn-block { width: 100%; margin-top: 0.9rem; }

    .btn-primary {
      background: var(--primary);
      color: #FFFFFF;
    }

    .btn-primary:hover { background: var(--primary-hover); }

    .btn-secondary {
      background: #334155;
      color: #F8FAFC;
    }

    .btn-secondary:hover { background: #475569; }

    .btn-success {
      background: var(--success);
      color: #FFFFFF;
    }

    .btn-success:hover { background: #059669; }

    .btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    /* Grid Layouts */
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr;
      gap: 1rem;
    }

    @media (min-width: 640px) {
      .grid-2 { grid-template-columns: 1fr 1fr; }
    }

    .grid-stats {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 0.75rem;
      margin-top: 1rem;
    }

    @media (min-width: 640px) {
      .grid-stats { grid-template-columns: repeat(4, 1fr); }
    }

    .stat-card {
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      padding: 0.9rem;
      border-radius: var(--radius);
      text-align: center;
    }

    .stat-number {
      font-size: 1.35rem;
      font-weight: 700;
      color: #FFFFFF;
    }

    .stat-label {
      font-size: 0.72rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      font-weight: 600;
      margin-top: 0.2rem;
    }

    /* Timeline Visualizer */
    .timeline-container {
      margin-top: 1rem;
      overflow-x: auto;
    }

    .timeline-bar {
      display: flex;
      height: 44px;
      border-radius: var(--radius);
      overflow: hidden;
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      min-width: 100%;
    }

    .shot-block {
      height: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-size: 0.7rem;
      font-weight: 700;
      color: #FFFFFF;
      border-right: 1px solid rgba(0,0,0,0.3);
      cursor: pointer;
      transition: filter 0.15s;
      overflow: hidden;
      white-space: nowrap;
      padding: 0 4px;
    }

    .shot-block:hover { filter: brightness(1.2); }

    .angle-wide { background: #2563EB; }
    .angle-closeup { background: #DC2626; }
    .angle-third_left { background: #0891B2; }
    .angle-third_right { background: #0D9488; }
    .angle-slow_push { background: #D97706; }
    .angle-broll { background: #16A34A; }

    .timeline-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-top: 0.75rem;
      font-size: 0.75rem;
      color: var(--text-secondary);
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }

    .legend-dot {
      width: 10px;
      height: 10px;
      border-radius: 2px;
    }

    /* Toggles & Sliders */
    .toggle-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.75rem 0;
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }

    .toggle-row:last-child { border-bottom: none; }

    .toggle-info {
      display: flex;
      flex-direction: column;
    }

    .toggle-title {
      font-size: 0.9rem;
      font-weight: 600;
      color: #FFFFFF;
    }

    .toggle-desc {
      font-size: 0.75rem;
      color: var(--text-secondary);
      margin-top: 0.1rem;
    }

    input[type="checkbox"] {
      width: 1.25rem;
      height: 1.25rem;
      cursor: pointer;
    }

    .slider-row {
      margin-top: 0.9rem;
    }

    .slider-header {
      display: flex;
      justify-content: space-between;
      font-size: 0.82rem;
      font-weight: 600;
      color: var(--text-secondary);
      margin-bottom: 0.35rem;
    }

    .slider-val {
      color: #FFFFFF;
      font-weight: 700;
    }

    input[type="range"] {
      width: 100%;
      height: 6px;
      background: var(--input-bg);
      border-radius: 3px;
    }

    /* Progress & Video */
    .progress-box {
      margin-top: 1.25rem;
      display: none;
    }

    .progress-header {
      display: flex;
      justify-content: space-between;
      font-size: 0.85rem;
      font-weight: 600;
      color: #FFFFFF;
      margin-bottom: 0.4rem;
    }

    .progress-bar-bg {
      width: 100%;
      height: 8px;
      background: var(--input-bg);
      border-radius: 4px;
      overflow: hidden;
    }

    .progress-bar-fill {
      height: 100%;
      width: 0%;
      background: var(--primary);
      transition: width 0.3s ease;
    }

    video {
      width: 100%;
      border-radius: var(--radius);
      margin-top: 1rem;
      background: #000000;
      border: 1px solid var(--card-border);
    }
  </style>
</head>
<body>

<div class="container">

  <!-- Header -->
  <header>
    <div class="brand-group">
      <h1>🎬 OmniCam Studio</h1>
      <p>Automated Virtual Multi-Camera Video Production</p>
    </div>
    <div class="status-badge">
      <span class="status-dot"></span>
      Local Engine Online (Port 8080)
    </div>
  </header>

  <!-- Step 1: Source Footage -->
  <div class="card">
    <div class="card-header">
      <div class="card-heading">1. Source Footage</div>
    </div>
    <label for="inputVideo">Video File Path</label>
    <input type="text" id="inputVideo" value="/sdcard/Movies/Vid.mp4" placeholder="/sdcard/Movies/Vid.mp4">

    <div style="display:flex; gap:0.5rem; margin-top:0.75rem;">
      <button class="btn btn-secondary" style="flex:1;" onclick="scanStorage()">
        🔍 Scan Device for Videos
      </button>
    </div>

    <div id="scanResults" style="display:none; margin-top:0.75rem;">
      <label for="scanSelect">Discovered Recordings</label>
      <select id="scanSelect" onchange="selectScannedFile(this.value)">
        <option value="">-- Choose a recording --</option>
      </select>
    </div>

    <button class="btn btn-primary btn-block" id="analyzeBtn" onclick="analyzeVideo()">
      🧠 Analyze Audio & Plan Cuts
    </button>
  </div>

  <!-- Step 2: Virtual Multi-Camera Timeline -->
  <div class="card" id="timelineCard" style="display:none;">
    <div class="card-header">
      <div class="card-heading">2. Multi-Camera Cut Timeline</div>
      <span style="font-size:0.8rem; color:var(--text-secondary);" id="timelineOverview"></span>
    </div>

    <div class="timeline-container">
      <div class="timeline-bar" id="timelineBar"></div>
    </div>

    <div class="timeline-legend">
      <div class="legend-item"><span class="legend-dot" style="background:#2563EB;"></span> Wide Context</div>
      <div class="legend-item"><span class="legend-dot" style="background:#DC2626;"></span> Tight Close-Up</div>
      <div class="legend-item"><span class="legend-dot" style="background:#0891B2;"></span> Rule-of-Thirds L/R</div>
      <div class="legend-item"><span class="legend-dot" style="background:#D97706;"></span> Ken Burns Push</div>
      <div class="legend-item"><span class="legend-dot" style="background:#16A34A;"></span> B-Roll Cutaway</div>
    </div>

    <div class="grid-stats">
      <div class="stat-card">
        <div class="stat-number" id="statEditedDur">00:00</div>
        <div class="stat-label">Edited Duration</div>
      </div>
      <div class="stat-card">
        <div class="stat-number" id="statDeadAir">0.0s</div>
        <div class="stat-label">Dead Air Cut</div>
      </div>
      <div class="stat-card">
        <div class="stat-number" id="statCuts">0</div>
        <div class="stat-label">Camera Cuts</div>
      </div>
      <div class="stat-card">
        <div class="stat-number" id="statSaved">0%</div>
        <div class="stat-label">Retention Boost</div>
      </div>
    </div>

    <div id="shotDetail" style="margin-top:0.75rem; font-size:0.82rem; color:var(--text-secondary); padding:0.5rem; background:var(--input-bg); border-radius:var(--radius); border:1px solid var(--card-border); text-align:center;">
      Tap any timeline segment to inspect shot details.
    </div>
  </div>

  <!-- Step 3: Production Settings -->
  <div class="card">
    <div class="card-header">
      <div class="card-heading">3. Studio Production Settings</div>
    </div>

    <div class="grid-2">
      <!-- Group A: Camera & Cadence -->
      <div>
        <label for="pacingSelect">Director Pacing</label>
        <select id="pacingSelect">
          <option value="dynamic" selected>Dynamic (Fast-Paced YouTube / Reels)</option>
          <option value="podcast">Podcast (Wide Context + Alternating Thirds)</option>
          <option value="documentary">Documentary (Wide Context + Push-Ins)</option>
          <option value="dramatic">Dramatic (Punch-In Emotional Hook)</option>
        </select>

        <label for="targetRes">Output Resolution</label>
        <select id="targetRes">
          <option value="720p" selected>720p (Recommended: 3x Faster, Mobile Safe)</option>
          <option value="1080p">1080p Full HD</option>
          <option value="4k">4K UHD Master</option>
        </select>
      </div>

      <!-- Group B: Color & Audio -->
      <div>
        <label for="colorSelect">Color Grade Profile</label>
        <select id="colorSelect">
          <option value="cinematic" selected>Hollywood Cinematic (Teal & Orange)</option>
          <option value="podcast">Podcast Vibrant</option>
          <option value="vintage">Vintage Warm</option>
          <option value="none">Raw Camera Pass-through</option>
        </select>

        <label for="bgmSelect">Background Music Bed</label>
        <select id="bgmSelect">
          <option value="ambient" selected>Synthesized Ambient Bed (Built-in)</option>
          <option value="none">Voice Only (No Music)</option>
        </select>
      </div>
    </div>

    <!-- Sliders -->
    <div class="slider-row">
      <div class="slider-header">
        <span>BGM Ducking Level</span>
        <span class="slider-val" id="bgmVolVal">22%</span>
      </div>
      <input type="range" id="bgmVol" min="5" max="50" value="22" oninput="document.getElementById('bgmVolVal').innerText = this.value + '%'">
    </div>

    <div class="slider-row">
      <div class="slider-header">
        <span>Punch-In Zoom Factor</span>
        <span class="slider-val" id="zoomVal">1.75x</span>
      </div>
      <input type="range" id="zoomRange" min="120" max="220" value="175" oninput="document.getElementById('zoomVal').innerText = (this.value / 100).toFixed(2) + 'x'">
    </div>

    <!-- Smart Enhancements Toggles -->
    <div style="margin-top:1.25rem; border-top:1px solid var(--card-border); padding-top:0.75rem;">
      <div class="toggle-row">
        <div class="toggle-info">
          <span class="toggle-title">Filler Word Removal</span>
          <span class="toggle-desc">Automatically cuts hesitations ("uh", "um", "ah", "like", "you know")</span>
        </div>
        <input type="checkbox" id="removeFillers" checked>
      </div>

      <div class="toggle-row">
        <div class="toggle-info">
          <span class="toggle-title">Digital Gimbal Horizon Stabilization</span>
          <span class="toggle-desc">2-pass optical motion smoothing to eliminate walking bounce</span>
        </div>
        <input type="checkbox" id="stabilize" checked>
      </div>

      <div class="toggle-row">
        <div class="toggle-info">
          <span class="toggle-title">Hormozi Active-Word Subtitles</span>
          <span class="toggle-desc">High-contrast animated captions with neon word-tracking</span>
        </div>
        <input type="checkbox" id="captions" checked>
      </div>

      <div class="toggle-row">
        <div class="toggle-info">
          <span class="toggle-title">2.35:1 Anamorphic Cinema Letterbox</span>
          <span class="toggle-desc">Adds cinematic top and bottom matte bars for landscape video</span>
        </div>
        <input type="checkbox" id="letterbox">
      </div>
    </div>

    <div class="grid-2" style="margin-top:0.5rem;">
      <div>
        <label for="titleText">Opening Title</label>
        <input type="text" id="titleText" value="OMNICAM AI • MULTI-CAM PRODUCTION">
      </div>
      <div>
        <label for="brollFolder">B-Roll Footage Folder (Optional)</label>
        <input type="text" id="brollFolder" placeholder="/sdcard/Movies/Broll/">
      </div>
    </div>
  </div>

  <!-- Step 4: Render Studio Video -->
  <div class="card">
    <div class="card-header">
      <div class="card-heading">4. Export & Delivery</div>
    </div>

    <button class="btn btn-primary btn-block" id="renderBtn" onclick="renderStudioVideo()">
      🎬 Render Studio Video
    </button>

    <div class="progress-box" id="progressBox">
      <div class="progress-header">
        <span id="progressMsg">Initializing cinematic pipeline...</span>
        <span id="progressPct">0%</span>
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" id="progressBar"></div>
      </div>
    </div>

    <div id="videoContainer" style="display:none; margin-top:1.5rem;">
      <div class="card-heading" style="color:var(--success); margin-bottom:0.5rem;">
        ✓ Master Video Ready
      </div>
      <video id="outputVideoPlayer" controls></video>
      <a id="downloadLink" class="btn btn-secondary btn-block" download>
        ⬇️ Download Video File
      </a>
    </div>
  </div>

</div>

<script>
  let currentShots = [];

  async function scanStorage() {
    try {
      const res = await fetch('/api/scan');
      const data = await res.json();
      const select = document.getElementById('scanSelect');
      select.innerHTML = '<option value="">-- Choose a recording --</option>';
      if (data.length > 0) {
        data.forEach(item => {
          const opt = document.createElement('option');
          opt.value = item.path;
          opt.innerText = `${item.name} (${item.size})`;
          select.appendChild(opt);
        });
        document.getElementById('scanResults').style.display = 'block';
      } else {
        alert('No video files found in common storage directories.');
      }
    } catch (err) {
      alert('Storage scan failed: ' + err);
    }
  }

  function selectScannedFile(val) {
    if (val) document.getElementById('inputVideo').value = val;
  }

  async function analyzeVideo() {
    const inputPath = document.getElementById('inputVideo').value.trim();
    if (!inputPath) return alert('Please enter a video file path.');

    const btn = document.getElementById('analyzeBtn');
    btn.disabled = true;
    btn.innerText = '⏳ Analyzing Acoustics & Framing...';

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_path: inputPath,
          pacing: document.getElementById('pacingSelect').value,
          zoom: parseFloat(document.getElementById('zoomRange').value) / 100.0,
          remove_fillers: document.getElementById('removeFillers').checked,
          broll_dir: document.getElementById('brollFolder').value.trim() || null,
        })
      });

      const data = await res.json();
      if (data.error) throw new Error(data.error);

      renderTimeline(data);
    } catch (err) {
      alert('Analysis failed: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.innerText = '🧠 Analyze Audio & Plan Cuts';
    }
  }

  function renderTimeline(data) {
    currentShots = data.shots || [];
    const bar = document.getElementById('timelineBar');
    bar.innerHTML = '';

    const totalDur = data.edited_duration || 1.0;

    currentShots.forEach((shot) => {
      const pct = ((shot.duration / totalDur) * 100).toFixed(2);
      const div = document.createElement('div');
      div.className = `shot-block angle-${shot.angle.toLowerCase()}`;
      div.style.width = pct + '%';
      div.innerText = shot.angle;
      div.title = `#${shot.index + 1} ${shot.angle}: ${shot.duration}s`;
      div.onclick = () => {
        document.getElementById('shotDetail').innerText = 
          `Shot #${shot.index + 1}: ${shot.angle} (${shot.duration}s) - ${shot.description}`;
      };
      bar.appendChild(div);
    });

    document.getElementById('statEditedDur').innerText = formatTime(data.edited_duration);
    document.getElementById('statDeadAir').innerText = data.dead_air_cut.toFixed(1) + 's';
    document.getElementById('statCuts').innerText = currentShots.length;
    const boostPct = Math.round((data.dead_air_cut / (data.total_duration || 1.0)) * 100);
    document.getElementById('statSaved').innerText = '+' + boostPct + '%';

    document.getElementById('timelineCard').style.display = 'block';
  }

  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  async function renderStudioVideo() {
    const inputPath = document.getElementById('inputVideo').value.trim();
    if (!inputPath) return alert('Please enter a video file path.');

    const btn = document.getElementById('renderBtn');
    btn.disabled = true;
    document.getElementById('progressBox').style.display = 'block';
    document.getElementById('videoContainer').style.display = 'none';

    try {
      const res = await fetch('/api/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_path: inputPath,
          pacing: document.getElementById('pacingSelect').value,
          zoom: parseFloat(document.getElementById('zoomRange').value) / 100.0,
          color: document.getElementById('colorSelect').value,
          bgm: document.getElementById('bgmSelect').value === 'ambient' ? 'ambient' : null,
          bgm_volume: parseFloat(document.getElementById('bgmVol').value) / 100.0,
          captions: document.getElementById('captions').checked,
          stabilize: document.getElementById('stabilize').checked,
          letterbox: document.getElementById('letterbox').checked,
          remove_fillers: document.getElementById('removeFillers').checked,
          broll_dir: document.getElementById('brollFolder').value.trim() || null,
          resolution: document.getElementById('targetRes').value,
          title: document.getElementById('titleText').value,
        })
      });

      const data = await res.json();
      if (data.error) throw new Error(data.error);

      pollProgress();
    } catch (err) {
      alert('Render initialization failed: ' + err.message);
      btn.disabled = false;
      document.getElementById('progressBox').style.display = 'none';
    }
  }

  function pollProgress() {
    const timer = setInterval(async () => {
      try {
        const res = await fetch('/api/progress');
        const data = await res.json();

        const pct = Math.round(data.progress * 100);
        document.getElementById('progressBar').style.width = pct + '%';
        document.getElementById('progressPct').innerText = pct + '%';
        document.getElementById('progressMsg').innerText = data.status || 'Rendering...';

        if (!data.is_rendering) {
          clearInterval(timer);
          document.getElementById('renderBtn').disabled = false;

          if (data.error) {
            alert('Render encountered an error: ' + data.error);
          } else if (data.output_file) {
            showCompletedVideo(data.output_file);
          }
        }
      } catch (e) {
        // Retry next poll
      }
    }, 1000);
  }

  function showCompletedVideo(filePath) {
    const container = document.getElementById('videoContainer');
    const player = document.getElementById('outputVideoPlayer');
    const download = document.getElementById('downloadLink');

    const videoUrl = '/video?path=' + encodeURIComponent(filePath);
    player.src = videoUrl;
    download.href = videoUrl;
    download.download = filePath.split('/').pop();
    container.style.display = 'block';
    player.play().catch(() => {});
  }
</script>

</body>
</html>
"""


class StudioHTTPHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean terminal logging
        sys.stderr.write(f"[OmniCam Web] {args[0]}\n")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        if path == "/api/scan":
            files = scan_media_files()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(files).encode("utf-8"))
            return

        if path == "/api/progress":
            with STATE.lock:
                data = {
                    "is_rendering": STATE.is_rendering,
                    "progress": STATE.progress,
                    "status": STATE.status_message,
                    "output_file": STATE.output_file,
                    "error": STATE.error,
                }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        if path == "/video":
            qs = urllib.parse.parse_qs(parsed.query)
            file_path = qs.get("path", [None])[0]
            if not file_path or not os.path.isfile(file_path):
                self.send_error(404, "File Not Found")
                return

            try:
                file_size = os.path.getsize(file_path)
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                with open(file_path, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
            except Exception:
                pass
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            params = json.loads(body) if body else {}
        except Exception:
            params = {}

        if path == "/api/analyze":
            input_path = params.get("input_path")
            if not input_path or not os.path.isfile(input_path):
                self.send_json({"error": f"File not found: {input_path}"}, status=400)
                return

            try:
                analyzer = AudioAnalyzer(
                    noise_threshold_db=float(params.get("silence_thresh", -32.0)),
                    min_silence_duration=float(params.get("min_silence", 0.35)),
                )
                total_duration = analyzer.get_media_duration(input_path)
                segments = analyzer.extract_speech_segments(input_path)

                if params.get("remove_fillers"):
                    hesitations = detect_acoustic_hesitations(input_path)
                    segments = remove_filler_intervals(segments, hesitations)

                tracker = VisionTracker(input_path)
                broll_dir = params.get("broll_dir")
                broll_mgr = BRollManager(broll_dir) if (broll_dir and os.path.isdir(broll_dir)) else None

                director = CameraDirector(
                    tracker=tracker,
                    pacing_style=params.get("pacing", "dynamic"),
                    broll_manager=broll_mgr,
                )
                shot_plans = director.plan_production(segments)

                edited_dur = sum(s.segment.duration for s in shot_plans)
                dead_air_cut = max(0.0, total_duration - edited_dur)

                shots_data = [
                    {
                        "index": sp.index,
                        "angle": sp.angle.value,
                        "start": sp.segment.start,
                        "end": sp.segment.end,
                        "duration": sp.segment.duration,
                        "description": sp.description,
                        "broll_name": sp.broll_name,
                    }
                    for sp in shot_plans
                ]

                self.send_json({
                    "total_duration": total_duration,
                    "edited_duration": edited_dur,
                    "dead_air_cut": dead_air_cut,
                    "shots": shots_data,
                })
            except Exception as ex:
                self.send_json({"error": str(ex)}, status=500)
            return

        if path == "/api/render":
            input_path = params.get("input_path")
            if not input_path or not os.path.isfile(input_path):
                self.send_json({"error": f"File not found: {input_path}"}, status=400)
                return

            with STATE.lock:
                if STATE.is_rendering:
                    self.send_json({"error": "A render job is already running"}, status=409)
                    return
                STATE.is_rendering = True
                STATE.progress = 0.05
                STATE.status_message = "Initializing..."
                STATE.output_file = None
                STATE.error = None

            def run_render_job():
                try:
                    analyzer = AudioAnalyzer(
                        noise_threshold_db=-32.0,
                        min_silence_duration=0.35,
                    )
                    segments = analyzer.extract_speech_segments(input_path)

                    if params.get("remove_fillers"):
                        hesitations = detect_acoustic_hesitations(input_path)
                        segments = remove_filler_intervals(segments, hesitations)

                    tracker = VisionTracker(input_path)
                    broll_dir = params.get("broll_dir")
                    broll_mgr = BRollManager(broll_dir) if (broll_dir and os.path.isdir(broll_dir)) else None

                    director = CameraDirector(
                        tracker=tracker,
                        pacing_style=params.get("pacing", "dynamic"),
                        zoom_factor=float(params.get("zoom", 1.75)),
                        broll_manager=broll_mgr,
                    )
                    shot_plans = director.plan_production(segments)

                    stem, _ = os.path.splitext(input_path)
                    out_path = f"{stem}_studio_cut.mp4"

                    res_choice = params.get("resolution", "720p")
                    res_map = {"720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}
                    bw, bh = res_map.get(res_choice, (1280, 720))
                    if tracker.metadata.is_portrait:
                        tw, th = bh, bw
                    else:
                        tw, th = bw, bh

                    config = RenderConfig(
                        target_width=tw,
                        target_height=th,
                        is_portrait=tracker.metadata.is_portrait,
                        color_grade=params.get("color", "cinematic"),
                        bgm_path=params.get("bgm"),
                        bgm_volume=float(params.get("bgm_volume", 0.22)),
                        enable_captions=bool(params.get("captions")),
                        stabilize=bool(params.get("stabilize")),
                        letterbox=bool(params.get("letterbox", False)),
                        broll_dir=broll_dir,
                        title_text=params.get("title", "OMNICAM AI • MULTI-CAM PRODUCTION"),
                    )

                    engine = RenderEngine(input_path, config=config)

                    def update_prog(pct, msg):
                        with STATE.lock:
                            STATE.progress = pct
                            STATE.status_message = msg

                    engine.render(shot_plans, out_path, progress_callback=update_prog)

                    with STATE.lock:
                        STATE.progress = 1.0
                        STATE.status_message = "Complete"
                        STATE.output_file = out_path
                        STATE.is_rendering = False
                except Exception as ex:
                    with STATE.lock:
                        STATE.error = str(ex)
                        STATE.status_message = f"Failed: {ex}"
                        STATE.is_rendering = False

            threading.Thread(target=run_render_job, daemon=True).start()
            self.send_json({"status": "started"})
            return

        self.send_error(404, "Not Found")

    def send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def launch_web_server(port: int = 8080):
    """Starts the zero-dependency OmniCam Localhost Mobile Web Studio with automatic port fallback."""
    target_port = port
    httpd = None
    max_attempts = 10

    for offset in range(max_attempts):
        candidate_port = target_port + offset
        try:
            httpd = ReusableTCPServer(("", candidate_port), StudioHTTPHandler)
            target_port = candidate_port
            break
        except OSError as e:
            # 98 on Linux/Android Termux, 48 on macOS / BSD
            if getattr(e, "errno", None) in (98, 48) or "address already in use" in str(e).lower():
                if offset == 0:
                    print(f"⚠️  Notice: Port {target_port} is currently in use (another OmniCam or server process is active).")
                continue
            raise e

    if httpd is None:
        print(f"[-] Error: Could not bind to any port between {port} and {port + max_attempts - 1}.")
        print("    To terminate existing instances in Termux, run: pkill -f omnicam.py")
        sys.exit(1)

    with httpd:
        print("\n" + "=" * 65)
        print(" 🎬 OMNICAM LOCALHOST MOBILE WEB STUDIO")
        print("=" * 65)
        print(f" [*] Server Live: http://localhost:{target_port}")
        print(f" [*] Open your phone or desktop browser to: http://localhost:{target_port}")
        if target_port != port:
            print(f" [*] Note: Switched automatically from busy port {port} -> http://localhost:{target_port}")
        print(" [*] Zero dependencies required. Press Ctrl+C to terminate.")
        print("=" * 65 + "\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[-] Web studio server stopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    launch_web_server(port)
