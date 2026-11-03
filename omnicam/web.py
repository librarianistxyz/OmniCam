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
  <title>OmniCam AI Studio</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #111827;
      --card-border: #1f293d;
      --primary: #00D2FF;
      --primary-glow: rgba(0, 210, 255, 0.35);
      --accent: #FF3366;
      --text: #F3F4F6;
      --text-muted: #9CA3AF;
      --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: var(--font-stack);
      line-height: 1.5;
      padding: 1rem;
      padding-bottom: 5rem;
      color-scheme: dark;
      accent-color: var(--primary);
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 1.5rem;
    }

    .brand-title {
      font-size: 1.25rem;
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #FFF;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .brand-title span { color: var(--primary); }

    .status-badge {
      font-size: 0.75rem;
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      background: rgba(0, 210, 255, 0.15);
      color: var(--primary);
      border: 1px solid rgba(0, 210, 255, 0.3);
      font-weight: 600;
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.25rem;
      margin-bottom: 1.25rem;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }

    .card-title {
      font-size: 0.95rem;
      font-weight: 700;
      color: #E5E7EB;
      margin-bottom: 0.75rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    label {
      display: block;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 0.4rem;
      margin-top: 0.8rem;
    }

    input[type="text"], select {
      width: 100%;
      background: #0B0F19;
      border: 1px solid var(--card-border);
      color: #FFF;
      padding: 0.65rem 0.85rem;
      border-radius: 8px;
      font-size: 0.9rem;
      outline: none;
      transition: border 0.2s;
    }

    input[type="text"]:focus, select:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 2px var(--primary-glow);
    }

    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      width: 100%;
      padding: 0.8rem 1.25rem;
      border-radius: 8px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
      margin-top: 0.8rem;
    }

    .btn-primary {
      background: linear-gradient(135deg, #00D2FF 0%, #0077FF 100%);
      color: #FFF;
      box-shadow: 0 4px 15px var(--primary-glow);
    }

    .btn-secondary {
      background: #1F293D;
      color: #E5E7EB;
    }

    .btn-secondary:hover { background: #2D3748; }

    .btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    /* Timeline visualizer */
    .timeline-container {
      margin-top: 1rem;
      overflow-x: auto;
    }

    .timeline-bar {
      display: flex;
      height: 48px;
      border-radius: 8px;
      overflow: hidden;
      background: #0B0F19;
      border: 1px solid var(--card-border);
      min-width: 100%;
    }

    .shot-block {
      height: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-size: 0.65rem;
      font-weight: 700;
      color: #FFF;
      text-shadow: 0 1px 2px rgba(0,0,0,0.8);
      border-right: 1px solid rgba(0,0,0,0.4);
      cursor: pointer;
      transition: opacity 0.2s;
      overflow: hidden;
      white-space: nowrap;
      padding: 0 4px;
    }

    .shot-block:hover { opacity: 0.85; }

    .angle-wide { background: #2563EB; }
    .angle-closeup { background: #DC2626; }
    .angle-third_left { background: #0D9488; }
    .angle-third_right { background: #0891B2; }
    .angle-slow_push { background: #D97706; }
    .angle-broll { background: #16A34A; }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 0.75rem;
      margin-top: 0.75rem;
    }

    .stat-box {
      background: #0B0F19;
      border: 1px solid var(--card-border);
      padding: 0.75rem;
      border-radius: 8px;
      text-align: center;
    }

    .stat-val {
      font-size: 1.2rem;
      font-weight: 800;
      color: var(--primary);
    }

    .stat-lbl {
      font-size: 0.7rem;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 600;
    }

    /* Toggles & Sliders */
    .toggle-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.65rem 0;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }

    .toggle-label {
      font-size: 0.85rem;
      font-weight: 600;
      color: #E5E7EB;
    }

    .slider-row {
      margin-top: 0.75rem;
    }

    .slider-header {
      display: flex;
      justify-content: space-between;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 0.25rem;
    }

    input[type="range"] {
      width: 100%;
      height: 6px;
      background: #1F293D;
      border-radius: 3px;
    }

    .progress-box {
      margin-top: 1rem;
      display: none;
    }

    .progress-bar-bg {
      width: 100%;
      height: 10px;
      background: #0B0F19;
      border-radius: 5px;
      overflow: hidden;
      margin-top: 0.5rem;
    }

    .progress-bar-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #00D2FF, #FF3366);
      transition: width 0.3s ease;
    }

    video {
      width: 100%;
      border-radius: 8px;
      margin-top: 1rem;
      background: #000;
      box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
  </style>
</head>
<body>

  <header>
    <div class="brand-title">🎬 <span>OMNICAM</span> STUDIO</div>
    <div class="status-badge" id="serverStatus">PORT 8080 ONLINE</div>
  </header>

  <!-- Video Source Section -->
  <div class="card">
    <div class="card-title">📹 Video Input Source</div>
    <label for="inputVideo">File Path or Storage Location</label>
    <input type="text" id="inputVideo" value="/sdcard/Movies/Vid.mp4" placeholder="/sdcard/Movies/my_clip.mp4">
    
    <button class="btn btn-secondary" onclick="scanStorage()">🔍 Scan Device For Videos</button>
    <div id="scanResults" style="display:none; margin-top:0.75rem;">
      <label for="scanSelect">Discovered Recordings</label>
      <select id="scanSelect" onchange="selectScannedFile(this.value)">
        <option value="">-- Choose a video --</option>
      </select>
    </div>

    <button class="btn btn-primary" id="analyzeBtn" onclick="analyzeVideo()">🧠 Analyze Acoustics & Cuts</button>
  </div>

  <!-- Interactive Timeline Section -->
  <div class="card" id="timelineCard" style="display:none;">
    <div class="card-title">🎞️ Virtual Multi-Camera Timeline</div>
    <div class="timeline-container">
      <div class="timeline-bar" id="timelineBar"></div>
    </div>

    <div class="stats-grid">
      <div class="stat-box">
        <div class="stat-val" id="statEditedDur">00:00</div>
        <div class="stat-lbl">Edited Duration</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" id="statDeadAir">0.0s</div>
        <div class="stat-lbl">Dead Air Cut</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" id="statCuts">0</div>
        <div class="stat-lbl">Camera Switches</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" id="statSaved">0%</div>
        <div class="stat-lbl">Retention Boost</div>
      </div>
    </div>
    <div id="shotDetail" style="margin-top: 0.75rem; font-size: 0.8rem; color: var(--text-muted); text-align: center;"></div>
  </div>

  <!-- Production Studio Settings -->
  <div class="card">
    <div class="card-title">🎛️ Director & Style Controls</div>

    <div class="toggle-row">
      <span class="toggle-label">🗣️ Filler Word Removal ("uh", "um", "like")</span>
      <input type="checkbox" id="removeFillers" checked>
    </div>

    <div class="toggle-row">
      <span class="toggle-label">🎥 Digital Gimbal Stabilization</span>
      <input type="checkbox" id="stabilize" checked>
    </div>

    <div class="toggle-row">
      <span class="toggle-label">🔤 Hormozi Active-Word Subtitles</span>
      <input type="checkbox" id="captions" checked>
    </div>

    <label for="pacingSelect">Director Pacing Cadence</label>
    <select id="pacingSelect">
      <option value="dynamic" selected>Dynamic Studio (Fast-Paced YouTube / Reels)</option>
      <option value="podcast">Podcast (Wide Context + Alternating Thirds)</option>
      <option value="documentary">Documentary (Wide Context + Push-Ins)</option>
      <option value="dramatic">Dramatic (Punch-In Intimacy)</option>
    </select>

    <label for="colorSelect">Color Grade Preset</label>
    <select id="colorSelect">
      <option value="cinematic" selected>Cinematic (Hollywood Teal & Orange)</option>
      <option value="podcast">Podcast (Vibrant Modern Tech)</option>
      <option value="vintage">Vintage (Warm Muted Documentary)</option>
      <option value="none">Raw Camera Pass-through</option>
    </select>

    <label for="bgmSelect">Auto-Ducking Background Music</label>
    <select id="bgmSelect">
      <option value="ambient" selected>Synthesized Ambient Bed (Built-in)</option>
      <option value="none">No Background Music (Voice Only)</option>
    </select>

    <div class="slider-row">
      <div class="slider-header">
        <span>BGM Ducking Level</span>
        <span id="bgmVolVal">22%</span>
      </div>
      <input type="range" id="bgmVol" min="5" max="50" value="22" oninput="document.getElementById('bgmVolVal').innerText = this.value + '%'">
    </div>

    <label for="brollFolder">Automatic B-Roll Clips Folder (Optional)</label>
    <input type="text" id="brollFolder" placeholder="/sdcard/Movies/Broll/">

    <label for="targetRes">Target Output Resolution</label>
    <select id="targetRes">
      <option value="720p" selected>720p (Recommended: 3x Faster, Mobile Safe)</option>
      <option value="1080p">1080p Full HD</option>
      <option value="4k">4K UHD Master</option>
    </select>

    <label for="titleText">Opening Title Card</label>
    <input type="text" id="titleText" value="OMNICAM AI • MULTI-CAM PRODUCTION">
  </div>

  <!-- Render Studio Action -->
  <div class="card">
    <button class="btn btn-primary" id="renderBtn" onclick="renderStudioVideo()">
      🎬 RENDER STUDIO VIDEO
    </button>

    <div class="progress-box" id="progressBox">
      <div style="display:flex; justify-content:space-between; font-size:0.8rem; font-weight:700;">
        <span id="progressMsg">Preparing cinematic pipeline...</span>
        <span id="progressPct">0%</span>
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" id="progressBar"></div>
      </div>
    </div>

    <div id="videoContainer" style="display:none; margin-top:1.5rem;">
      <div class="card-title" style="color:var(--primary);">✨ Master Render Complete!</div>
      <video id="outputVideoPlayer" controls></video>
      <a id="downloadLink" class="btn btn-secondary" style="margin-top:0.5rem; text-decoration:none;" download>
        ⬇️ Download Video
      </a>
    </div>
  </div>

  <script>
    let currentShots = [];

    async function scanStorage() {
      try {
        const res = await fetch('/api/scan');
        const data = await res.json();
        const select = document.getElementById('scanSelect');
        select.innerHTML = '<option value="">-- Choose a video --</option>';
        if (data.length > 0) {
          data.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.path;
            opt.innerText = `${item.name} (${item.size})`;
            select.appendChild(opt);
          });
          document.getElementById('scanResults').style.display = 'block';
        } else {
          alert('No video files found in common folders. Type path manually.');
        }
      } catch (err) {
        alert('Scan failed: ' + err);
      }
    }

    function selectScannedFile(val) {
      if (val) document.getElementById('inputVideo').value = val;
    }

    async function analyzeVideo() {
      const inputPath = document.getElementById('inputVideo').value.trim();
      if (!inputPath) return alert('Please enter video path');

      const btn = document.getElementById('analyzeBtn');
      btn.disabled = true;
      btn.innerText = '⏳ Analyzing Acoustics & Cuts...';

      try {
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            input_path: inputPath,
            pacing: document.getElementById('pacingSelect').value,
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
        btn.innerText = '🧠 Analyze Acoustics & Cuts';
      }
    }

    function renderTimeline(data) {
      currentShots = data.shots || [];
      const bar = document.getElementById('timelineBar');
      bar.innerHTML = '';

      const totalDur = data.edited_duration || 1.0;

      currentShots.forEach((shot, idx) => {
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
      document.getElementById('statSaved').innerText = '+' + Math.round((data.dead_air_cut / data.total_duration) * 100) + '%';

      document.getElementById('timelineCard').style.display = 'block';
    }

    function formatTime(sec) {
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    async function renderStudioVideo() {
      const inputPath = document.getElementById('inputVideo').value.trim();
      if (!inputPath) return alert('Please enter video path');

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
            color: document.getElementById('colorSelect').value,
            bgm: document.getElementById('bgmSelect').value === 'ambient' ? 'ambient' : null,
            bgm_volume: parseFloat(document.getElementById('bgmVol').value) / 100.0,
            captions: document.getElementById('captions').checked,
            stabilize: document.getElementById('stabilize').checked,
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
        alert('Render failed to start: ' + err.message);
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
              alert('Render encountered error: ' + data.error);
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


def launch_web_server(port: int = 8080):
    """Starts the zero-dependency OmniCam Localhost Mobile Web Studio."""
    server_address = ("", port)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(server_address, StudioHTTPHandler) as httpd:
        print("\n" + "=" * 65)
        print(" 🎬 OMNICAM LOCALHOST MOBILE WEB STUDIO")
        print("=" * 65)
        print(f" [*] Server Live: http://localhost:{port}")
        print(f" [*] Open your phone or desktop browser to: http://localhost:{port}")
        print(" [*] Zero dependencies required. Press Ctrl+C to terminate.")
        print("=" * 65 + "\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[-] Web studio server stopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    launch_web_server(port)
