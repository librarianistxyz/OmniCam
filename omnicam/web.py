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
from .overlay_engine import OverlayEngine
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
from .music_sync import MultiTakeSyncEngine, TakeSyncInfo
from .music_analyzer import MusicBeatAnalyzer, MusicAnalysisResult, SongSection
from .music_director import MusicVideoDirector


class StudioServerState:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_rendering: bool = False
        self.progress: float = 0.0
        self.status_message: str = "Ready"
        self.output_file: Optional[str] = None
        self.saved_device_path: Optional[str] = None
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
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <meta name="theme-color" content="#090D16">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="mobile-web-app-capable" content="yes">
  <title>OmniCam NLE | Autonomous Multi-Camera Director</title>
  <meta name="description" content="Professional NLE multi-camera studio workstation. 100% offline, zero cloud, autonomous AI angle switching, Hormozi captions, and sidechain audio ducking.">

  <!-- Google Fonts: Outfit & Inter for High-End NLE Typography -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">
  <!-- FontAwesome 6 Icons -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" crossorigin="anonymous" referrerpolicy="no-referrer" />

  <style>
    /* ==========================================================================
       OmniCam NLE - Modern Obsidian Studio UI (VN / CapCut Professional Aesthetic)
       ========================================================================== */
    :root {
      --bg-darkest: #07090E;
      --bg-main: #0B0E17;
      --bg-panel: #131826;
      --bg-panel-hover: #1A2234;
      --bg-surface: #1E273D;
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-focus: rgba(0, 240, 255, 0.5);

      --accent-neon: #00F0FF;
      --accent-blue: #2563EB;
      --accent-purple: #8B5CF6;
      --accent-pink: #EC4899;
      --accent-amber: #F59E0B;
      --accent-emerald: #10B981;
      --playhead-red: #FF2A55;

      --text-white: #FFFFFF;
      --text-main: #F1F5F9;
      --text-muted: #94A3B8;
      --text-dim: #64748B;

      --font-ui: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-display: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --radius-full: 9999px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      user-select: none;
      -webkit-user-select: none;
      -webkit-tap-highlight-color: transparent;
    }

    html, body {
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: var(--bg-darkest);
      color: var(--text-main);
      font-family: var(--font-ui);
      font-size: 14px;
    }

    /* Fullscreen Application Container */
    .nle-app {
      display: flex;
      flex-direction: column;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background: var(--bg-main);
      position: relative;
    }

    /* --------------------------------------------------------------------------
       TOP BAR (VN / CapCut Style)
       -------------------------------------------------------------------------- */
    .nle-topbar {
      height: 52px;
      background: var(--bg-darkest);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 1rem;
      z-index: 50;
      flex-shrink: 0;
      overflow-x: auto;
      overflow-y: hidden;
      white-space: nowrap;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
      gap: 0.75rem;
    }
    .nle-topbar::-webkit-scrollbar {
      display: none;
    }

    .topbar-left, .topbar-center, .topbar-right {
      flex-shrink: 0;
    }

    .topbar-left {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    /* --------------------------------------------------------------------------
       TOP TOOL NAV RIBBON (Scrollable Quick Tools Navigation)
       -------------------------------------------------------------------------- */
    .nle-top-tool-nav {
      height: 44px;
      background: #080A10;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      padding: 0 0.75rem;
      z-index: 45;
      flex-shrink: 0;
      overflow-x: auto;
      overflow-y: hidden;
      white-space: nowrap;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
    }
    .nle-top-tool-nav::-webkit-scrollbar {
      display: none;
    }

    .top-tool-nav-scroll {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      flex-wrap: nowrap;
    }

    .top-tool-chip {
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      border-radius: var(--radius-full);
      padding: 0.32rem 0.8rem;
      font-size: 0.76rem;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      flex-shrink: 0;
      outline: none;
      user-select: none;
      white-space: nowrap;
    }
    .top-tool-chip i {
      font-size: 0.85rem;
      transition: transform 0.15s ease;
    }
    .top-tool-chip:hover {
      background: rgba(255, 255, 255, 0.09);
      color: var(--text-white);
      border-color: rgba(255, 255, 255, 0.25);
    }
    .top-tool-chip:hover i {
      transform: scale(1.12);
    }
    .top-tool-chip.active {
      background: rgba(0, 240, 255, 0.14);
      border-color: var(--accent-neon);
      color: var(--accent-neon);
      box-shadow: 0 0 14px rgba(0, 240, 255, 0.35);
    }

    .app-brand-badge {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      color: var(--text-white);
      font-family: var(--font-display);
      font-weight: 800;
      font-size: 1.05rem;
      letter-spacing: -0.02em;
    }

    .brand-glow-dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--accent-neon);
      box-shadow: 0 0 10px var(--accent-neon);
    }

    .clip-name-pill {
      background: var(--bg-panel);
      border: 1px solid var(--border-subtle);
      padding: 0.28rem 0.7rem;
      border-radius: var(--radius-full);
      font-size: 0.78rem;
      color: var(--text-muted);
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.2s ease;
    }
    .clip-name-pill:hover {
      background: var(--bg-panel-hover);
      color: var(--text-white);
      border-color: rgba(255, 255, 255, 0.2);
    }

    .topbar-center {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }

    .telemetry-chip {
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-subtle);
      padding: 0.25rem 0.65rem;
      border-radius: var(--radius-sm);
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }
    .telemetry-chip strong {
      color: var(--accent-neon);
      font-weight: 700;
    }

    .topbar-right {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .res-select {
      background: var(--bg-panel);
      color: var(--text-white);
      border: 1px solid var(--border-subtle);
      padding: 0.35rem 0.7rem;
      border-radius: var(--radius-md);
      font-size: 0.78rem;
      font-weight: 600;
      outline: none;
      cursor: pointer;
    }

    .btn-export {
      background: linear-gradient(135deg, #00F0FF 0%, #0066FF 100%);
      color: #07090E;
      font-family: var(--font-display);
      font-weight: 800;
      font-size: 0.85rem;
      padding: 0.45rem 1.15rem;
      border-radius: var(--radius-md);
      border: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      box-shadow: 0 0 16px rgba(0, 240, 255, 0.35);
      transition: all 0.2s ease;
      letter-spacing: 0.02em;
    }
    .btn-export:hover {
      transform: translateY(-1px);
      box-shadow: 0 0 24px rgba(0, 240, 255, 0.55);
    }
    .btn-export:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      box-shadow: none;
    }

    /* --------------------------------------------------------------------------
       CENTER VIEWPORT / CINEMA MONITOR
       -------------------------------------------------------------------------- */
    .nle-monitor-area {
      flex: 1;
      min-height: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 0.75rem 1rem 0.25rem;
      position: relative;
      background: radial-gradient(circle at center, #111728 0%, #07090E 100%);
    }

    .monitor-canvas-box {
      width: 100%;
      max-width: 900px;
      height: 100%;
      max-height: calc(100% - 46px);
      background: #000000;
      border-radius: var(--radius-lg);
      border: 1px solid var(--border-subtle);
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.65);
      position: relative;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    /* Empty State Dropzone */
    .empty-state-card {
      text-align: center;
      padding: 2rem;
      max-width: 480px;
    }

    .empty-state-icon {
      width: 64px;
      height: 64px;
      margin: 0 auto 1.25rem;
      border-radius: var(--radius-lg);
      background: rgba(0, 240, 255, 0.08);
      border: 1px solid rgba(0, 240, 255, 0.25);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--accent-neon);
      font-size: 1.8rem;
    }

    .empty-state-title {
      font-family: var(--font-display);
      font-size: 1.35rem;
      font-weight: 800;
      color: var(--text-white);
      margin-bottom: 0.5rem;
    }

    .empty-state-subtitle {
      font-size: 0.85rem;
      color: var(--text-muted);
      line-height: 1.5;
      margin-bottom: 1.5rem;
    }

    .empty-actions-row {
      display: flex;
      gap: 0.75rem;
      justify-content: center;
      flex-wrap: wrap;
    }

    .btn-action-glow {
      background: var(--bg-panel);
      color: var(--text-white);
      border: 1px solid var(--border-subtle);
      font-family: var(--font-display);
      font-weight: 700;
      font-size: 0.88rem;
      padding: 0.65rem 1.25rem;
      border-radius: var(--radius-md);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      transition: all 0.2s ease;
    }
    .btn-action-glow:hover {
      background: var(--bg-panel-hover);
      border-color: var(--accent-neon);
      box-shadow: 0 0 16px rgba(0, 240, 255, 0.2);
    }
    .btn-action-primary {
      background: var(--accent-blue);
      border-color: rgba(255, 255, 255, 0.15);
    }
    .btn-action-primary:hover {
      background: #1D4ED8;
      border-color: var(--accent-neon);
    }

    /* Video Player Element */
    #studioVideoPlayer {
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #000000;
      display: none;
      transform-origin: 50% 45%;
      transition: transform 0.08s cubic-bezier(0.2, 0.8, 0.2, 1);
      will-change: transform, filter;
    }

    .flash-fx-overlay {
      position: absolute;
      inset: 0;
      background: #ffffff;
      opacity: 0;
      pointer-events: none;
      z-index: 12;
    }
    .flash-fx-overlay.flash-active {
      animation: flashCutAnim 0.08s ease-out forwards;
    }
    @keyframes flashCutAnim {
      0% { opacity: 0.85; }
      100% { opacity: 0; }
    }

    /* Dynamic FX Animations */
    @keyframes fxHandheld {
      0% { transform: scale(var(--cam-scale, 1.0)) translate(var(--cam-tx, 0px), var(--cam-ty, 0px)) rotate(0deg); }
      25% { transform: scale(var(--cam-scale, 1.0)) translate(calc(var(--cam-tx, 0px) - 3px), calc(var(--cam-ty, 0px) + 2px)) rotate(0.12deg); }
      50% { transform: scale(var(--cam-scale, 1.0)) translate(calc(var(--cam-tx, 0px) + 2px), calc(var(--cam-ty, 0px) - 2px)) rotate(-0.1deg); }
      75% { transform: scale(var(--cam-scale, 1.0)) translate(calc(var(--cam-tx, 0px) - 2px), calc(var(--cam-ty, 0px) - 1px)) rotate(0.08deg); }
      100% { transform: scale(var(--cam-scale, 1.0)) translate(var(--cam-tx, 0px), var(--cam-ty, 0px)) rotate(0deg); }
    }
    .fx-handheld-motion {
      animation: fxHandheld 3.8s ease-in-out infinite alternate !important;
    }

    @keyframes fxQuake {
      0%, 100% { transform: scale(var(--cam-scale, 1.0)) translate(var(--cam-tx, 0px), var(--cam-ty, 0px)); }
      10% { transform: scale(var(--cam-scale, 1.0)) translate(calc(var(--cam-tx, 0px) - 6px), calc(var(--cam-ty, 0px) + 5px)); }
      20% { transform: scale(var(--cam-scale, 1.0)) translate(calc(var(--cam-tx, 0px) + 6px), calc(var(--cam-ty, 0px) - 4px)); }
      30% { transform: scale(var(--cam-scale, 1.0)) translate(calc(var(--cam-tx, 0px) - 3px), calc(var(--cam-ty, 0px) + 2px)); }
      40% { transform: scale(var(--cam-scale, 1.0)) translate(calc(var(--cam-tx, 0px) + 2px), calc(var(--cam-ty, 0px) - 1px)); }
      50% { transform: scale(var(--cam-scale, 1.0)) translate(var(--cam-tx, 0px), var(--cam-ty, 0px)); }
    }
    .fx-quake-motion {
      animation: fxQuake 2.0s ease-in-out infinite !important;
    }

    @keyframes fxFlickerAnim {
      0% { opacity: 0; }
      20% { opacity: 0.05; }
      40% { opacity: 0.02; }
      60% { opacity: 0.07; }
      80% { opacity: 0.01; }
      100% { opacity: 0; }
    }
    .fx-flicker-layer {
      animation: fxFlickerAnim 0.14s steps(2, start) infinite;
    }

    @keyframes recPulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.2; }
    }
    .rec-indicator-dot {
      animation: recPulse 1s ease-in-out infinite;
    }

    .freeze-badge-overlay {
      position: absolute;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(220, 38, 38, 0.9);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border: 1px solid rgba(255, 255, 255, 0.3);
      color: #ffffff;
      font-family: var(--font-display);
      font-weight: 800;
      font-size: 0.75rem;
      letter-spacing: 0.08em;
      padding: 0.35rem 0.85rem;
      border-radius: var(--radius-full);
      display: none;
      align-items: center;
      gap: 0.45rem;
      z-index: 14;
      box-shadow: 0 4px 16px rgba(220, 38, 38, 0.5);
    }

    /* Monitor HUD Overlay */
    .monitor-hud-top {
      position: absolute;
      top: 12px;
      left: 14px;
      right: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      pointer-events: none;
      z-index: 10;
    }

    .hud-badge-angle {
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: var(--accent-neon);
      font-family: var(--font-display);
      font-weight: 800;
      font-size: 0.75rem;
      padding: 0.3rem 0.75rem;
      border-radius: var(--radius-full);
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      letter-spacing: 0.05em;
    }

    .hud-badge-timecode {
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: var(--text-white);
      font-family: monospace;
      font-size: 0.8rem;
      font-weight: 700;
      padding: 0.3rem 0.65rem;
      border-radius: var(--radius-sm);
    }

    /* Monitor Play Overlay */
    .monitor-play-center {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: rgba(0, 0, 0, 0.65);
      backdrop-filter: blur(6px);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: var(--text-white);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.35rem;
      cursor: pointer;
      opacity: 0;
      transition: all 0.2s ease;
      z-index: 15;
    }
    .monitor-canvas-box:hover .monitor-play-center,
    .monitor-play-center.visible {
      opacity: 1;
    }
    .monitor-play-center:hover {
      transform: translate(-50%, -50%) scale(1.1);
      background: var(--accent-blue);
      border-color: var(--accent-neon);
    }

    /* Transport Controls Row */
    .monitor-transport-bar {
      height: 42px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 1.25rem;
      margin-top: 0.35rem;
      width: 100%;
    }

    .transport-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 1.05rem;
      cursor: pointer;
      padding: 0.35rem 0.65rem;
      border-radius: var(--radius-sm);
      transition: all 0.15s ease;
    }
    .transport-btn:hover {
      color: var(--text-white);
      background: var(--bg-panel);
    }
    .transport-btn-primary {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--bg-panel);
      border: 1px solid var(--border-subtle);
      color: var(--text-white);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1rem;
    }
    .transport-btn-primary:hover {
      background: var(--accent-blue);
      color: var(--text-white);
      box-shadow: 0 0 14px rgba(37, 99, 235, 0.45);
    }

    /* --------------------------------------------------------------------------
       MULTI-TRACK TIMELINE (VN / CapCut Style)
       -------------------------------------------------------------------------- */
    .nle-timeline-area {
      height: 180px;
      background: var(--bg-darkest);
      border-top: 1px solid var(--border-subtle);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      position: relative;
      flex-shrink: 0;
      overflow: hidden;
    }

    /* Timeline Header & Zoom */
    .timeline-ruler-header {
      height: 26px;
      background: #090C12;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      position: relative;
      overflow-x: hidden;
      width: 100%;
    }

    .time-ticks-container {
      display: flex;
      width: 100%;
      height: 100%;
      position: absolute;
      top: 0;
      left: 0;
    }

    .time-tick {
      border-left: 1px solid rgba(255, 255, 255, 0.12);
      height: 100%;
      padding-left: 4px;
      font-size: 0.65rem;
      color: var(--text-dim);
      font-family: monospace;
      flex: 1;
      display: flex;
      align-items: center;
    }

    /* Multi-Track Canvas */
    .timeline-tracks-viewport {
      flex: 1;
      overflow-x: auto;
      overflow-y: hidden;
      position: relative;
      padding: 0.35rem 0;
      background: #080A10;
      cursor: crosshair;
    }

    /* Glowing Red Playhead */
    .timeline-playhead {
      position: absolute;
      top: 0;
      bottom: 0;
      left: 0;
      width: 2px;
      background: var(--playhead-red);
      box-shadow: 0 0 8px var(--playhead-red);
      z-index: 40;
      pointer-events: none;
      transform: translateX(0);
      transition: left 0.05s linear;
    }

    .playhead-head {
      width: 12px;
      height: 12px;
      background: var(--playhead-red);
      transform: translateX(-5px) rotate(45deg);
      border-radius: 2px;
      position: absolute;
      top: -2px;
      box-shadow: 0 0 8px var(--playhead-red);
    }

    /* Track 1: Angles & Cuts */
    .track-row {
      display: flex;
      align-items: center;
      height: 48px;
      margin-bottom: 0.35rem;
      position: relative;
      width: 100%;
      padding: 0 0.5rem;
    }

    .shot-block-nle {
      height: 100%;
      border-radius: var(--radius-sm);
      margin-right: 2px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 0.35rem 0.5rem;
      cursor: pointer;
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.12);
      transition: all 0.15s ease;
      font-size: 0.72rem;
      font-weight: 700;
    }
    .shot-block-nle:hover {
      filter: brightness(1.2);
      transform: scaleY(1.04);
      z-index: 5;
    }
    .shot-block-nle.active {
      border: 2px solid #FFFFFF !important;
      box-shadow: 0 0 12px rgba(255, 255, 255, 0.4);
    }

    /* Angle Color Palette */
    .angle-wide { background: linear-gradient(180deg, #1D4ED8 0%, #1E3A8A 100%); color: #BFDBFE; }
    .angle-closeup { background: linear-gradient(180deg, #7C3AED 0%, #5B21B6 100%); color: #E9D5FF; }
    .angle-third_left { background: linear-gradient(180deg, #059669 0%, #064E3B 100%); color: #A7F3D0; }
    .angle-third_right { background: linear-gradient(180deg, #0D9488 0%, #134E4A 100%); color: #99F6E4; }
    .angle-slow_push { background: linear-gradient(180deg, #D97706 0%, #78350F 100%); color: #FDE68A; }
    .angle-broll { background: linear-gradient(180deg, #E11D48 0%, #881337 100%); color: #FECDD3; }

    .shot-tag-name {
      display: flex;
      align-items: center;
      gap: 0.3rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .shot-tag-dur {
      font-size: 0.65rem;
      opacity: 0.8;
      font-family: monospace;
    }

    /* Track 2: Subtitle Track */
    .track-row-subtitles {
      height: 28px;
      background: rgba(255, 255, 255, 0.02);
      border-radius: var(--radius-sm);
      margin-bottom: 0.35rem;
      display: flex;
      align-items: center;
      padding: 0 0.5rem;
      overflow: hidden;
    }

    .sub-pill-nle {
      height: 20px;
      background: rgba(255, 230, 0, 0.15);
      border: 1px solid rgba(255, 230, 0, 0.4);
      color: #FFE600;
      border-radius: 4px;
      padding: 0 0.45rem;
      font-size: 0.68rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      white-space: nowrap;
      margin-right: 4px;
    }

    /* Track 3: Audio Ducking Track */
    .track-row-audio {
      height: 32px;
      background: rgba(0, 240, 255, 0.04);
      border: 1px dashed rgba(0, 240, 255, 0.2);
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      padding: 0 0.5rem;
      justify-content: space-between;
      font-size: 0.72rem;
      color: var(--accent-neon);
      font-weight: 600;
    }

    /* --------------------------------------------------------------------------
       BOTTOM TOOL DOCK & INSPECTOR DRAWER (VN / CapCut Layout)
       -------------------------------------------------------------------------- */
    .nle-bottom-section {
      background: var(--bg-darkest);
      position: relative;
      flex-shrink: 0;
      z-index: 45;
    }

    /* Professional Desktop Studio Layout & Responsive Panel System */
    .nle-desktop-workspace {
      display: flex;
      flex-direction: row;
      flex: 1;
      min-height: 0;
      width: 100vw;
      position: relative;
      overflow: hidden;
    }

    .nle-desktop-left-col {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-width: 0;
      min-height: 0;
      position: relative;
      overflow: hidden;
    }

    .nle-desktop-right-panel {
      width: 440px;
      max-width: 440px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      border-left: 1px solid var(--border-subtle);
      background: var(--bg-panel);
      z-index: 40;
      position: relative;
      overflow: hidden;
      transition: width 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
    }

    /* Dedicated Tool Inspector Container */
    .nle-inspector-drawer {
      background: var(--bg-panel);
      display: flex;
      flex-direction: column;
      flex: 1;
      height: 100%;
      min-height: 0;
      overflow-y: auto;
      padding: 1rem 1.25rem;
      scrollbar-width: thin;
    }
    .nle-inspector-drawer.open {
      display: flex;
    }

    .drawer-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.75rem;
      padding-bottom: 0.4rem;
      border-bottom: 1px solid var(--border-subtle);
    }

    .drawer-title {
      font-family: var(--font-display);
      font-size: 0.95rem;
      font-weight: 800;
      color: var(--text-white);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .drawer-close-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 1.1rem;
      padding: 0.2rem 0.5rem;
    }
    .drawer-close-btn:hover { color: var(--text-white); }

    .drawer-controls-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
    }

    .control-item {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
    }

    .control-label {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .nle-select, .nle-input {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      color: var(--text-white);
      padding: 0.5rem 0.75rem;
      border-radius: var(--radius-sm);
      font-size: 0.85rem;
      font-weight: 500;
      outline: none;
    }
    .nle-select:focus, .nle-input:focus {
      border-color: var(--accent-neon);
      box-shadow: 0 0 10px rgba(0, 240, 255, 0.25);
    }

    .nle-range-slider {
      width: 100%;
      accent-color: var(--accent-neon);
      cursor: pointer;
    }

    .toggle-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.5rem 0.75rem;
      background: var(--bg-surface);
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-subtle);
      cursor: pointer;
    }

    /* Bottom Tool Dock Buttons */
    .nle-dock-bar {
      height: 62px;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 0.4rem;
      padding: 0 0.75rem;
      border-top: 1px solid var(--border-subtle);
      background: #080A10;
      overflow-x: auto;
      overflow-y: hidden;
      white-space: nowrap;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
    }
    .nle-dock-bar::-webkit-scrollbar {
      display: none;
    }

    /* CapCut Blend Mode Overlay Cards */
    .overlay-cards-scroll {
      display: flex;
      gap: 0.5rem;
      overflow-x: auto;
      overflow-y: hidden;
      padding: 0.35rem 0.1rem 0.65rem;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: thin;
    }
    .overlay-thumb-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 0.5rem 0.65rem;
      min-width: 95px;
      max-width: 105px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.25rem;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      flex-shrink: 0;
      text-align: center;
      user-select: none;
    }
    .overlay-thumb-card:hover {
      border-color: rgba(255, 255, 255, 0.3);
      transform: translateY(-2px);
    }
    .overlay-thumb-card.active {
      border-color: var(--accent-neon);
      background: rgba(0, 240, 255, 0.12);
      box-shadow: 0 0 14px rgba(0, 240, 255, 0.35);
    }
    .ov-thumb-icon {
      font-size: 1.25rem;
      margin-bottom: 0.1rem;
    }
    .ov-thumb-name {
      font-size: 0.72rem;
      font-weight: 700;
      color: var(--text-white);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      width: 100%;
    }
    .ov-thumb-tag {
      font-size: 0.62rem;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .cat-pill {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      border-radius: 999px;
      padding: 0.24rem 0.65rem;
      font-size: 0.72rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s ease;
      flex-shrink: 0;
    }
    .cat-pill:hover, .cat-pill.active {
      background: rgba(0, 240, 255, 0.15);
      border-color: var(--accent-neon);
      color: #fff;
    }

    .dock-tool-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.25rem;
      padding: 0.4rem 0.65rem;
      border-radius: var(--radius-md);
      cursor: pointer;
      font-size: 0.7rem;
      font-weight: 600;
      transition: all 0.15s ease;
      min-width: 58px;
    }
    .dock-tool-btn i {
      font-size: 1.15rem;
      transition: transform 0.15s ease;
    }
    .dock-tool-btn:hover {
      color: var(--text-white);
      background: rgba(255, 255, 255, 0.05);
    }
    .dock-tool-btn:hover i {
      transform: translateY(-2px);
    }
    .dock-tool-btn.active {
      color: var(--accent-neon);
      background: rgba(0, 240, 255, 0.08);
      border: 1px solid rgba(0, 240, 255, 0.25);
    }

    /* --------------------------------------------------------------------------
       DEVICE FILE NAVIGATOR & EXPORT MODALS
       -------------------------------------------------------------------------- */
    .modal-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(4, 6, 10, 0.82);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      z-index: 1000;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }

    .modal-window {
      background: var(--bg-panel);
      border-radius: var(--radius-lg);
      border: 1px solid var(--border-subtle);
      box-shadow: 0 20px 48px rgba(0, 0, 0, 0.85);
      width: 100%;
      max-width: 740px;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      animation: modalFadeIn 0.2s ease-out;
    }

    @keyframes modalFadeIn {
      from { opacity: 0; transform: translateY(12px) scale(0.98); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }

    .modal-header {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: var(--bg-surface);
    }

    .modal-close-btn {
      background: transparent;
      border: none;
      font-size: 1.5rem;
      color: var(--text-muted);
      cursor: pointer;
      line-height: 1;
      padding: 0.2rem 0.5rem;
    }
    .modal-close-btn:hover { color: var(--text-white); }

    .modal-roots-bar {
      display: flex;
      gap: 0.5rem;
      padding: 0.65rem 1.25rem;
      background: var(--bg-main);
      border-bottom: 1px solid var(--border-subtle);
      overflow-x: auto;
      white-space: nowrap;
    }

    .browser-root-chip {
      background: var(--bg-panel);
      border: 1px solid var(--border-subtle);
      color: var(--text-main);
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.35rem 0.75rem;
      border-radius: var(--radius-full);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.15s ease;
    }
    .browser-root-chip:hover {
      background: var(--bg-surface);
      border-color: var(--accent-neon);
      color: var(--accent-neon);
    }

    .browser-nav-bar {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.65rem 1.25rem;
      border-bottom: 1px solid var(--border-subtle);
      background: var(--bg-surface);
    }

    .browser-breadcrumbs {
      display: flex;
      align-items: center;
      gap: 0.35rem;
      overflow-x: auto;
      white-space: nowrap;
      font-size: 0.8rem;
    }

    .crumb-btn {
      background: transparent;
      border: none;
      color: var(--accent-neon);
      font-weight: 600;
      cursor: pointer;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }
    .crumb-btn:hover { text-decoration: underline; }
    .crumb-sep { color: var(--text-dim); }

    .browser-list-container {
      flex: 1;
      overflow-y: auto;
      padding: 0.25rem 0;
      min-height: 280px;
    }

    .browser-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.65rem 1.25rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      cursor: pointer;
      transition: background 0.15s;
    }
    .browser-item:hover {
      background: var(--bg-panel-hover);
    }

    .browser-item-left {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex: 1;
      min-width: 0;
    }

    .browser-item-icon {
      width: 32px;
      height: 32px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      font-size: 0.95rem;
    }
    .icon-folder { background: rgba(37, 99, 235, 0.15); color: #60A5FA; }
    .icon-video { background: rgba(0, 240, 255, 0.15); color: var(--accent-neon); }
    .icon-file { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); }

    .browser-item-name {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-main);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .badge-video {
      background: rgba(0, 240, 255, 0.12);
      color: var(--accent-neon);
      border: 1px solid rgba(0, 240, 255, 0.3);
      font-size: 0.7rem;
      font-weight: 700;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
    }

    .modal-footer {
      padding: 0.85rem 1.25rem;
      border-top: 1px solid var(--border-subtle);
      background: var(--bg-surface);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    /* Responsive Adjustments: Desktop Side-by-Side vs Mobile Bottom Drawer */
    @media (min-width: 769px) {
      .nle-dock-bar {
        display: none !important;
      }
      .nle-bottom-section {
        display: none !important;
      }
      .nle-inspector-drawer {
        border-top: none;
        max-height: none !important;
      }
    }

    @media (max-width: 768px) {
      .nle-desktop-workspace {
        flex-direction: column;
      }
      .nle-desktop-right-panel {
        display: none !important;
      }
      .nle-dock-bar {
        display: none !important; /* Removed down below as requested */
      }
      .nle-topbar { padding: 0 0.65rem; gap: 0.5rem; }
      .clip-name-pill { max-width: 150px; }
      .timeline-ruler-header { height: 22px; }
      .nle-timeline-area { height: 160px; }
      .track-row { height: 42px; }
      .top-tool-chip { font-size: 0.72rem; padding: 0.28rem 0.65rem; }
      .nle-inspector-drawer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: var(--bg-panel);
        border-top: 1px solid var(--border-subtle);
        max-height: 0;
        overflow: hidden;
        transition: max-height 0.25s cubic-bezier(0.16, 1, 0.3, 1), padding 0.2s ease;
        z-index: 100;
        padding: 0;
        box-shadow: 0 -10px 30px rgba(0, 0, 0, 0.85);
      }
      .nle-inspector-drawer.open {
        max-height: 320px;
        padding: 0.85rem 1.25rem 1.5rem;
        overflow-y: auto;
      }
    }
  </style>
</head>
<body>

  <div class="nle-app">

    <!-- ======================================================================
         TOP BAR: PROJECT HEADER & EXPORT
         ====================================================================== -->
    <header class="nle-topbar">
      <div class="topbar-left">
        <div class="app-brand-badge">
          <span class="brand-glow-dot"></span>
          <span>OmniCam</span>
        </div>

        <div class="clip-name-pill" onclick="openFileBrowser()" title="Click to change source video">
          <i class="fa-solid fa-film"></i>
          <span id="topbarClipName">No Media Selected</span>
        </div>
      </div>

      <div class="topbar-center">
        <div class="telemetry-chip" id="statDurationChip" style="display: none;">
          <i class="fa-solid fa-clock"></i>
          <span>Cut: <strong id="statCutDuration">00:00</strong></span>
        </div>
        <div class="telemetry-chip" id="statDeadAirChip" style="display: none;">
          <i class="fa-solid fa-scissors"></i>
          <span>Dead Air: <strong id="statDeadAirPct">-0%</strong></span>
        </div>
        <div class="telemetry-chip" id="statCutsChip" style="display: none;">
          <i class="fa-solid fa-video"></i>
          <span>Angles: <strong id="statCutsCount">0</strong></span>
        </div>
      </div>

      <div class="topbar-right">
        <select class="res-select" id="aspectRatioSelect" onchange="setAspectRatio(this.value)" title="Canvas Aspect Ratio">
          <option value="16:9" selected>16:9 Landscape</option>
          <option value="9:16">9:16 Vertical</option>
          <option value="1:1">1:1 Square</option>
        </select>

        <select class="res-select" id="targetResolutionSelect">
          <option value="1080p" selected>1080p FHD</option>
          <option value="720p">720p Mobile</option>
          <option value="4k">4K Master</option>
        </select>

        <button class="btn-export" id="exportMasterBtn" onclick="openExportModal()" type="button">
          <i class="fa-solid fa-bolt"></i>
          <span>EXPORT</span>
        </button>
      </div>
    </header>

    <!-- ======================================================================
         TOP TOOLS NAV RIBBON (Scrollable VN / CapCut Style)
         ====================================================================== -->
    <nav class="nle-top-tool-nav" id="topToolNav" aria-label="Editor Tools Navigation">
      <div class="top-tool-nav-scroll">
        <button class="top-tool-chip" id="topBtnMedia" onclick="openToolPanel('Media', 'fa-folder-open')" type="button">
          <i class="fa-solid fa-folder-open"></i>
          <span>Media</span>
        </button>

        <button class="top-tool-chip" id="topBtnAngles" onclick="openToolPanel('Angles', 'fa-video')" type="button">
          <i class="fa-solid fa-video"></i>
          <span>Angles</span>
        </button>

        <button class="top-tool-chip" id="topBtnTransitions" onclick="openToolPanel('Transitions', 'fa-bolt')" type="button">
          <i class="fa-solid fa-bolt" style="color: var(--accent-neon);"></i>
          <span>Transitions</span>
        </button>

        <button class="top-tool-chip" id="topBtnEffects" onclick="openToolPanel('Effects', 'fa-wand-magic-sparkles')" type="button">
          <i class="fa-solid fa-wand-magic-sparkles" style="color: #A78BFA;"></i>
          <span>Effects</span>
        </button>

        <button class="top-tool-chip" id="topBtnOverlays" onclick="openToolPanel('Overlays', 'fa-sparkles')" type="button">
          <i class="fa-solid fa-sparkles" style="color: #F43F5E;"></i>
          <span>Overlays</span>
        </button>

        <button class="top-tool-chip" id="topBtnText" onclick="openToolPanel('Text', 'fa-font')" type="button">
          <i class="fa-solid fa-font" style="color: #FBBF24;"></i>
          <span>Text</span>
        </button>

        <button class="top-tool-chip" id="topBtnColor" onclick="openToolPanel('Color', 'fa-palette')" type="button">
          <i class="fa-solid fa-palette"></i>
          <span>3D LUT</span>
        </button>

        <button class="top-tool-chip" id="topBtnAudio" onclick="openToolPanel('Audio', 'fa-volume-high')" type="button">
          <i class="fa-solid fa-volume-high"></i>
          <span>Sound</span>
        </button>

        <button class="top-tool-chip" id="topBtnCaptions" onclick="openToolPanel('Captions', 'fa-closed-captioning')" type="button">
          <i class="fa-solid fa-closed-captioning"></i>
          <span>Captions</span>
        </button>

        <button class="top-tool-chip" id="topBtnFillers" onclick="openToolPanel('Fillers', 'fa-scissors')" type="button">
          <i class="fa-solid fa-scissors"></i>
          <span>Fillers</span>
        </button>

        <button class="top-tool-chip" id="topBtnGimbal" onclick="openToolPanel('Gimbal', 'fa-compass')" type="button">
          <i class="fa-solid fa-compass"></i>
          <span>Gimbal</span>
        </button>

        <button class="top-tool-chip" id="topBtnBRoll" onclick="openToolPanel('BRoll', 'fa-layer-group')" type="button">
          <i class="fa-solid fa-layer-group"></i>
          <span>B-Roll</span>
        </button>

        <button class="top-tool-chip" id="topBtnRatio" onclick="openToolPanel('Ratio', 'fa-crop-simple')" type="button">
          <i class="fa-solid fa-crop-simple"></i>
          <span>Canvas</span>
        </button>
      </div>
    </nav>

    <!-- Hidden native file input for gallery picker -->
    <input type="file" id="nativeFilePicker" accept="video/*" style="display: none;" onchange="handleNativeFileSelect(this)" />
    <input type="hidden" id="inputVideo" value="" />

    <!-- ======================================================================
         PROFESSIONAL DESKTOP WORKSPACE (Video Center-Left, Tools Fixed Right)
         ====================================================================== -->
    <div class="nle-desktop-workspace">
      <!-- Left Column: Center Video Monitor + Multi-Track Timeline -->
      <div class="nle-desktop-left-col">
    <!-- ======================================================================
         CENTER CINEMA MONITOR / CANVAS
         ====================================================================== -->
    <main class="nle-monitor-area">
      <div class="monitor-canvas-box" id="monitorCanvasBox">

        <!-- Empty State Hero (shown before selecting video) -->
        <div class="empty-state-card" id="emptyStateCard">
          <div class="empty-state-icon">
            <i class="fa-solid fa-clapperboard"></i>
          </div>
          <h2 class="empty-state-title">Autonomous Multi-Camera Studio</h2>
          <p class="empty-state-subtitle">
            Select any single-camera phone take. OmniCam will cut silences, track subject framing, and switch between 5 virtual camera angles with zero jump cuts.
          </p>

          <div class="empty-actions-row">
            <button class="btn-action-glow btn-action-primary" onclick="document.getElementById('nativeFilePicker').click()" type="button">
              <i class="fa-solid fa-mobile-screen"></i> Pick from Gallery
            </button>
            <button class="btn-action-glow" onclick="openFileBrowser()" type="button">
              <i class="fa-solid fa-folder-tree"></i> Browse Device Storage
            </button>
          </div>

          <div id="uploadStatusBadge" style="display: none; margin-top: 1.25rem; padding: 0.55rem 0.95rem; border-radius: 6px; font-size: 0.82rem; background: rgba(0, 240, 255, 0.1); color: var(--accent-neon); border: 1px solid rgba(0, 240, 255, 0.3);">
            <span id="uploadStatusMsg">Loading media...</span>
          </div>
        </div>

        <!-- Video Player Display -->
        <video id="studioVideoPlayer" loop playsinline></video>

        <!-- Real-time Selective Color Person Isolation Overlay -->
        <div id="liveSelectiveColorOverlay" style="position: absolute; inset: 0; pointer-events: none; z-index: 7; display: none;"></div>

        <!-- Real-time CapCut Blend Mode Overlay Player -->
        <video id="liveOverlayPlayer" loop playsinline muted style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; pointer-events: none; mix-blend-mode: screen; opacity: 0; transition: opacity 0.25s ease; z-index: 8;"></video>

        <!-- Real-time Lens Vignette Overlay -->
        <div id="liveVignetteOverlay" style="position: absolute; inset: 0; pointer-events: none; z-index: 9; background: radial-gradient(circle at center, transparent 55%, rgba(0, 0, 0, 0.72) 100%); display: none;"></div>

        <!-- Real-time 35mm Film Grain Overlay -->
        <div id="liveFilmGrainOverlay" style="position: absolute; inset: 0; pointer-events: none; z-index: 10; opacity: 0.16; display: none; background-image: url('data:image/svg+xml;utf8,<svg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'><filter id=\'noiseFilter\'><feTurbulence type=\'fractalNoise\' baseFrequency=\'0.85\' numOctaves=\'3\' stitchTiles=\'stitch\'/></filter><rect width=\'100%\' height=\'100%\' filter=\'url(%23noiseFilter)\'/></svg>');"></div>

        <!-- Real-time Portrait Depth Blur (Tilt-Shift) Overlay -->
        <div id="liveTiltShiftOverlay" style="position: absolute; inset: 0; pointer-events: none; z-index: 10; backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px); mask-image: radial-gradient(ellipse at 50% 45%, transparent 35%, black 75%); -webkit-mask-image: radial-gradient(ellipse at 50% 45%, transparent 35%, black 75%); display: none;"></div>

        <!-- Real-time 35mm Film Gate Flicker Overlay -->
        <div id="liveFilmFlickerOverlay" class="fx-flicker-layer" style="position: absolute; inset: 0; pointer-events: none; z-index: 11; background: #ffffff; display: none;"></div>

        <!-- Real-time 90s Retro Camcorder Viewfinder OSD -->
        <div id="liveCamcorderHud" style="position: absolute; inset: 16px; pointer-events: none; z-index: 16; display: none; font-family: monospace; color: #ffffff; text-shadow: 0 1px 4px rgba(0,0,0,0.95);">
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; font-weight: 800;">
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <span class="rec-indicator-dot" style="color: #ef4444; font-size: 1.1rem;">●</span> REC
            </div>
            <div>[ ■■■ ] SP</div>
          </div>
          <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 48px; height: 48px; border: 1px dashed rgba(255,255,255,0.45); display: flex; align-items: center; justify-content: center; font-size: 1.3rem; color: rgba(255,255,255,0.7);">+</div>
          <div style="position: absolute; bottom: 0; left: 0; right: 0; display: flex; justify-content: space-between; font-size: 0.8rem; font-weight: 700;">
            <div id="liveCamcorderTc">TC 00:00:00:00</div>
            <div>OCT. 24 1998</div>
          </div>
        </div>

        <!-- Real-time Anamorphic 2.35:1 Letterbox Bars -->
        <div id="liveLetterboxTop" style="position: absolute; top: 0; left: 0; right: 0; height: 9%; background: #000; pointer-events: none; z-index: 12; display: none; transition: height 0.2s ease;"></div>
        <div id="liveLetterboxBottom" style="position: absolute; bottom: 0; left: 0; right: 0; height: 9%; background: #000; pointer-events: none; z-index: 12; display: none; transition: height 0.2s ease;"></div>

        <!-- Real-time Lower-Third Title Overlay -->
        <div id="liveLowerThirdOverlay" style="position: absolute; bottom: 25px; left: 20px; right: 20px; z-index: 13; pointer-events: none; display: none;">
          <div style="display: flex; align-items: stretch; background: rgba(0, 0, 0, 0.82); border-radius: 4px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.6); max-width: 480px;">
            <div style="width: 5px; background: var(--accent-neon);"></div>
            <div style="padding: 0.45rem 0.85rem;">
              <div id="liveTitleText" style="font-size: 0.82rem; font-weight: 800; color: #fff; text-transform: uppercase; letter-spacing: 0.02em;">OMNICAM AI • MULTI-CAM PRODUCTION</div>
              <div id="liveSubtitleText" style="font-size: 0.68rem; font-weight: 600; color: var(--accent-neon);">PRO VIRTUAL STUDIO // 4K CLARITY</div>
            </div>
          </div>
        </div>

        <!-- Real-time Flash Transition FX Overlay -->
        <div id="playerFlashOverlay" class="flash-fx-overlay"></div>

        <!-- Dramatic Freeze Frame Badge Overlay -->
        <div id="freezeBadgeOverlay" class="freeze-badge-overlay">
          <i class="fa-solid fa-snowflake"></i> <span>DRAMATIC FREEZE</span>
        </div>

        <!-- Monitor HUD Overlay -->
        <div class="monitor-hud-top" id="monitorHudTop" style="display: none;">
          <div class="hud-badge-angle" id="hudAngleBadge">
            <i class="fa-solid fa-video"></i> <span id="hudAngleName">CAM 1 // MASTER WIDE</span>
          </div>
          <div class="hud-badge-timecode" id="hudTimecode">00:00.00 / 00:00.00</div>
        </div>

        <!-- Center Play Overlay Button -->
        <div class="monitor-play-center" id="monitorPlayOverlay" onclick="toggleVideoPlay()" style="display: none;">
          <i class="fa-solid fa-play" id="monitorPlayIcon"></i>
        </div>

      </div>

      <!-- Monitor Transport Bar -->
      <div class="monitor-transport-bar" id="monitorTransportBar" style="display: none;">
        <button class="transport-btn" onclick="stepVideo(-1.0)" type="button" title="Step Back 1s">
          <i class="fa-solid fa-backward-step"></i>
        </button>
        <button class="transport-btn transport-btn-primary" onclick="toggleVideoPlay()" type="button" title="Play / Pause (Space)">
          <i class="fa-solid fa-play" id="transportPlayIcon"></i>
        </button>
        <button class="transport-btn" onclick="stepVideo(1.0)" type="button" title="Step Forward 1s">
          <i class="fa-solid fa-forward-step"></i>
        </button>
        <button class="transport-btn" id="btnLiveDirectorToggle" onclick="toggleLiveDirector()" type="button" title="Toggle Real-Time Virtual Playhead (Instant edits & angles without exporting)" style="width: auto; padding: 0.35rem 0.75rem; font-size: 0.75rem; font-weight: 700; color: var(--accent-neon); border: 1px solid rgba(0, 240, 255, 0.4); border-radius: var(--radius-full); background: rgba(0, 240, 255, 0.08); display: inline-flex; align-items: center; gap: 0.4rem;">
          <i class="fa-solid fa-bolt"></i> <span id="liveDirectorText">Live Edit: ON</span>
        </button>
        <button class="transport-btn" onclick="reAnalyzeFootage()" type="button" title="Re-generate Cuts with Current Settings">
          <i class="fa-solid fa-wand-magic-sparkles"></i>
        </button>
      </div>
    </main>

    <!-- ======================================================================
         MULTI-TRACK TIMELINE (VN / CapCut Style)
         ====================================================================== -->
    <section class="nle-timeline-area">
      <!-- Timecode Ruler -->
      <div class="timeline-ruler-header">
        <div class="time-ticks-container" id="timeTicksContainer"></div>
      </div>

      <!-- Scrollable Multi-Track Container -->
      <div class="timeline-tracks-viewport" id="timelineViewport" onclick="handleTimelineClick(event)">
        <!-- Glowing Red Playhead -->
        <div class="timeline-playhead" id="timelinePlayhead">
          <div class="playhead-head"></div>
        </div>

        <!-- Track 1: Multi-Cam Angle Cuts -->
        <div class="track-row" id="cutsTrackRow">
          <div style="color: var(--text-dim); font-size: 0.75rem; padding-left: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
            <i class="fa-solid fa-film"></i> Select a video to generate virtual multi-camera cuts
          </div>
        </div>

        <!-- Track 2: Hormozi Subtitles -->
        <div class="track-row-subtitles" id="subtitlesTrackRow">
          <span style="font-size: 0.65rem; color: var(--text-dim); margin-right: 0.5rem;"><i class="fa-solid fa-closed-captioning"></i> CAPTIONS:</span>
          <span id="captionTrackStatus" style="font-size: 0.65rem; color: var(--text-muted);">Synced to speech</span>
        </div>

        <!-- Track 3: Voice + Ducking BGM -->
        <div class="track-row-audio" id="audioTrackRow">
          <span><i class="fa-solid fa-waveform-lines"></i> SOUNDTRACK &amp; VOICE</span>
          <span style="font-size: 0.68rem; color: var(--text-dim);" id="audioTrackMeta">Sidechain Auto-Ducking (-22dB) &bull; 80Hz Rumble Filter</span>
        </div>
      </div>
    </section>
      </div>

      <!-- Right Column: Dedicated Fixed Inspector & Tools Panel -->
      <aside class="nle-desktop-right-panel" id="desktopRightPanel">
      <!-- Sliding Inspector Drawer / Sheet -->
      <div class="nle-inspector-drawer" id="inspectorDrawer">
        <div class="drawer-header">
          <div class="drawer-title" id="drawerTitle">
            <i class="fa-solid fa-sliders"></i> Tool Inspector
          </div>
          <button class="drawer-close-btn" onclick="closeDrawer()" type="button">&times;</button>
        </div>

        <!-- Panel 1: Media -->
        <div class="drawer-panel" id="panelMedia" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Select Media Source</span>
              <div style="display: flex; gap: 0.5rem;">
                <button class="btn-action-glow" onclick="document.getElementById('nativeFilePicker').click()" type="button" style="flex: 1;">
                  <i class="fa-solid fa-mobile-screen"></i> Gallery
                </button>
                <button class="btn-action-glow" onclick="openFileBrowser()" type="button" style="flex: 1;">
                  <i class="fa-solid fa-folder-tree"></i> Storage
                </button>
              </div>
            </div>
            <div class="control-item">
              <span class="control-label">Quick Shortcuts</span>
              <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
                <span class="browser-root-chip" onclick="openFileBrowser('/sdcard/DCIM/Camera')"><i class="fa-solid fa-camera"></i> Camera</span>
                <span class="browser-root-chip" onclick="openFileBrowser('/sdcard/Movies')"><i class="fa-solid fa-film"></i> Movies</span>
                <span class="browser-root-chip" onclick="openFileBrowser('.')"><i class="fa-solid fa-briefcase"></i> Workspace</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Panel 2: Pacing & Angles -->
        <div class="drawer-panel" id="panelAngles" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Director Pacing Style</span>
              <select class="nle-select" id="pacingSelect" onchange="reAnalyzeFootage()">
                <option value="dynamic" selected>Dynamic Hollywood (Balanced 2.5s - 4.5s)</option>
                <option value="podcast">Podcast Studio (Longer takes 4s - 8s)</option>
                <option value="energetic">Energetic / TikTok (Rapid cuts 1.5s - 3s)</option>
              </select>
            </div>
            <div class="control-item">
              <span class="control-label">Close-Up Zoom Ratio</span>
              <select class="nle-select" id="zoomSelect">
                <option value="1.75" selected>1.75x Crop (Native 1080p from 4K)</option>
                <option value="1.5">1.50x Crop (Subtle Punch-in)</option>
                <option value="2.0">2.00x Crop (Intense Macro)</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Panel 3: Vocal Fillers -->
        <div class="drawer-panel" id="panelFillers" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Automatic Filler Excision</span>
              <label class="toggle-row">
                <span>Remove "uh", "um", "like", "you know"</span>
                <input type="checkbox" id="removeFillersToggle" checked onchange="reAnalyzeFootage()" />
              </label>
            </div>
            <div class="control-item">
              <span class="control-label">Hesitation Detection</span>
              <span style="font-size: 0.78rem; color: var(--text-muted); line-height: 1.4;">
                Dual lexical (Whisper token matching) and acoustic spectral drone filter cuts verbal stutters into dynamic angle switches.
              </span>
            </div>
          </div>
        </div>

        <!-- Panel 4: 3D Color LUT & Selective Isolation -->
        <div class="drawer-panel" id="panelColor" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Cinematic Color Palette &amp; Grading</span>
              <select class="nle-select" id="colorGradeSelect" onchange="applyLiveFilters()">
                <option value="cinematic" selected>🎬 Cinematic S-Curve (Warm skin, teal shadows)</option>
                <option value="oppenheimer_mono">⚛️ Oppenheimer 70mm Monochrome (IMAX Los Alamos B&amp;W)</option>
                <option value="oppenheimer_fission">🔥 Oppenheimer Trinity Fission (Scorched Amber &amp; Gold)</option>
                <option value="sherlock_noir">🕵️ Sherlock Holmes Victorian Noir (Baker St. Fog &amp; Cold Teal)</option>
                <option value="sherlock_gaslamp">🏮 Sherlock Gaslamp Sepia (1890s Warm Lantern Glow)</option>
                <option value="vintage_technicolor">🎨 1930s 3-Strip Technicolor (Vivid Dye-Transfer Pop)</option>
                <option value="podcast">🎙️ Modern Tech Podcast (High vibrance &amp; pop)</option>
                <option value="vintage">🎞️ Vintage 35mm (Muted organic tones)</option>
                <option value="noir">🌑 Classic Film Noir (High contrast monochrome)</option>
                <option value="none">Clean / Neutral (Raw sensor pass-through)</option>
              </select>
            </div>
            <div class="control-item">
              <span class="control-label">Target Speaker to Track</span>
              <select class="nle-select" id="targetPersonSelect" onchange="applyLiveFilters(); reAnalyzeFootage();">
                <option value="primary" selected>🎯 Primary Speaker (Main Talking Head)</option>
                <option value="left">👤 Speaker 1 (Left Side)</option>
                <option value="right">👤 Speaker 2 (Right Side)</option>
                <option value="center">👤 Center Speaker</option>
              </select>
            </div>
            <div class="control-item">
              <span class="control-label">Selective Color Isolation (Subject Splash)</span>
              <select class="nle-select" id="selectiveColorSelect" onchange="applyLiveFilters()">
                <option value="none" selected>Off (Grade Whole Frame)</option>
                <option value="person_color_bg_mono">👤 Tracked Person in Natural Color, Background in Oppenheimer B&amp;W</option>
                <option value="person_color_bg_sherlock">👤 Tracked Person in Color, Background in Sherlock Victorian Fog</option>
                <option value="person_color_bg_oppenheimer">👤 Tracked Person in Color, Background in Atomic Fission Amber</option>
                <option value="person_grade_only">🎨 Apply Color Grade ONLY to Tracked Person</option>
                <option value="bg_grade_only">🖼️ Apply Color Grade ONLY to Background (Behind Person)</option>
              </select>
            </div>
            <div class="control-item">
              <span class="control-label">Vignette &amp; Contrast</span>
              <label class="toggle-row">
                <span>Subtle Film Vignette &amp; S-Curve</span>
                <input type="checkbox" id="vignetteToggle" checked onchange="applyLiveFilters()" />
              </label>
            </div>
          </div>
        </div>

        <!-- Panel 5: Sound & Ducking -->
        <div class="drawer-panel" id="panelAudio" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Background Music Track</span>
              <select class="nle-select" id="bgmTrackSelect">
                <option value="ambient" selected>Warm Ambient Harmonics (Royalty-Free)</option>
                <option value="none">None (Speech Only)</option>
              </select>
            </div>
            <div class="control-item">
              <span class="control-label">Auto-Ducking Bed Volume (<span id="bgmVolLabel">20%</span>)</span>
              <input type="range" class="nle-range-slider" id="bgmVolSlider" min="5" max="50" value="20" oninput="document.getElementById('bgmVolLabel').innerText = this.value + '%'" />
            </div>
            <div class="control-item">
              <span class="control-label">Audio Mastering</span>
              <label class="toggle-row">
                <span>EBU R128 Broadcast Normalization (-16 LUFS)</span>
                <input type="checkbox" id="audioNormToggle" checked />
              </label>
            </div>
          </div>
        </div>

        <!-- Panel 6: Hormozi Captions -->
        <div class="drawer-panel" id="panelCaptions" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Animated Active-Word Subtitles</span>
              <label class="toggle-row">
                <span>Burn Hormozi Style Captions</span>
                <input type="checkbox" id="captionsToggle" />
              </label>
            </div>
            <div class="control-item">
              <span class="control-label">Word Highlight Color</span>
              <select class="nle-select" id="captionColorSelect">
                <option value="yellow" selected>Neon Yellow (#FFE600)</option>
                <option value="green">Electric Emerald (#00FF66)</option>
                <option value="cyan">Cyber Cyan (#00F0FF)</option>
                <option value="white">Pure Crisp White</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Panel 7: Digital Gimbal -->
        <div class="drawer-panel" id="panelGimbal" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">2-Pass Optical Horizon Stabilizer</span>
              <label class="toggle-row">
                <span>Enable vidstab Digital Gimbal</span>
                <input type="checkbox" id="stabilizeToggle" />
              </label>
            </div>
            <div class="control-item">
              <span class="control-label">Smoothing Radius (<span id="stabilizeSmoothingLabel">25</span> frames)</span>
              <input type="range" class="nle-range-slider" id="stabilizeSmoothingSlider" min="10" max="50" value="25" oninput="document.getElementById('stabilizeSmoothingLabel').innerText = this.value" />
            </div>
          </div>
        </div>

        <!-- Panel 8: B-Roll -->
        <div class="drawer-panel" id="panelBRoll" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">B-Roll Footage / Photos Folder</span>
              <input type="text" class="nle-input" id="brollFolderInput" placeholder="/sdcard/Movies/Clips or ./clips/" />
            </div>
            <div class="control-item">
              <span class="control-label">Cutaway Behavior</span>
              <span style="font-size: 0.78rem; color: var(--text-muted); line-height: 1.4;">
                Takes longer than 4.0s automatically cut away to secondary video or stills with smooth Ken Burns drift, keeping speech seamless.
              </span>
            </div>
          </div>
        </div>

        <!-- Panel 9: Transitions -->
        <div class="drawer-panel" id="panelTransitions" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Angle Cut Transition</span>
              <select class="nle-select" id="transitionSelect">
                <option value="flash" selected>⚡ White Flash (High Impact Cut)</option>
                <option value="zoom">🌀 Crash Zoom (Punch-in Sweep)</option>
                <option value="glitch">📺 RGB Glitch (Cyber Chromatic Aberration)</option>
                <option value="dissolve">🌫️ Cross Dissolve (Smooth Film Blend)</option>
                <option value="none">🎬 Hard Cut (Clean NLE Splicing)</option>
              </select>
            </div>
            <div class="control-item">
              <span class="control-label">Whoosh Transition SFX</span>
              <label class="toggle-row">
                <span>Play Sound Effect on Cuts</span>
                <input type="checkbox" id="transitionSfxToggle" checked />
              </label>
            </div>
            <div class="control-item">
              <span class="control-label">SFX Volume (<span id="sfxVolLabel">35%</span>)</span>
              <input type="range" class="nle-range-slider" id="sfxVolSlider" min="10" max="80" value="35" oninput="document.getElementById('sfxVolLabel').innerText = this.value + '%'" />
            </div>
            <div class="control-item">
              <span class="control-label">Punchline Freeze-Frame</span>
              <label class="toggle-row">
                <span>Dramatic Freeze Hold on Key Statements</span>
                <input type="checkbox" id="freezeFrameToggle" checked />
              </label>
            </div>
            <div class="control-item">
              <span class="control-label">Freeze Hold Duration (<span id="freezeDurLabel">0.6s</span>)</span>
              <input type="range" class="nle-range-slider" id="freezeDurSlider" min="0.3" max="1.5" step="0.1" value="0.6" oninput="document.getElementById('freezeDurLabel').innerText = this.value + 's'" />
            </div>
          </div>
        </div>

        <!-- Panel: Music Video Studio (Auto-Sync, Beat Grid, 808 Drops, Speed Ramps) -->
        <div class="drawer-panel" id="panelMusic" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item" style="grid-column: 1 / -1;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                <span class="control-label"><i class="fa-solid fa-music" style="color: #06B6D4;"></i> Music Video Studio Engine</span>
                <label class="toggle-row" style="margin: 0; padding: 0;">
                  <span style="font-size: 0.75rem; font-weight: 700; color: #06B6D4; margin-right: 0.5rem;">MV MODE</span>
                  <input type="checkbox" id="musicModeToggle" onchange="toggleMusicMode(this.checked)" />
                </label>
              </div>
              <p style="font-size: 0.76rem; color: var(--text-muted); margin: 0 0 0.5rem 0; line-height: 1.4;">
                Locks multiple camera takes to a clean master song (song.wav/mp3), aligns cuts to musical bars, 808 bass punch-ins, speed ramps, and kick-synced sub-bass vibration.
              </p>
            </div>

            <!-- Master Song Input -->
            <div class="control-item" style="grid-column: 1 / -1;">
              <span class="control-label">1. Clean Studio Master Song (WAV / MP3)</span>
              <div style="display: flex; gap: 0.4rem; margin-top: 0.3rem;">
                <input type="text" class="nle-input" id="masterSongInput" placeholder="/path/to/song.wav or .mp3" style="flex: 1;" />
                <button type="button" class="btn-action-glow" onclick="browseMasterSong()" style="padding: 0 0.8rem; font-size: 0.78rem;">
                  <i class="fa-solid fa-folder-open"></i> Pick
                </button>
              </div>
            </div>

            <!-- Auto-Sync Multi-Takes -->
            <div class="control-item" style="grid-column: 1 / -1;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                <span class="control-label">2. Multi-Take Waveform Auto-Sync (Lip-Sync)</span>
                <button type="button" class="btn-action-glow" id="btnSyncTakes" onclick="autoSyncTakes()" style="padding: 0.25rem 0.65rem; font-size: 0.72rem; background: rgba(6,182,212,0.18); border-color: #06B6D4; color: #06B6D4;">
                  <i class="fa-solid fa-bolt"></i> Auto-Sync Takes (FFT)
                </button>
              </div>
              <div id="takesSyncList" style="background: rgba(0,0,0,0.35); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 0.5rem; max-height: 140px; overflow-y: auto;">
                <div style="font-size: 0.75rem; color: var(--text-muted); text-align: center; padding: 0.5rem;">
                  Load video footage and a master song, then click Auto-Sync.
                </div>
              </div>
              <div style="display: flex; gap: 0.4rem; margin-top: 0.4rem;">
                <input type="text" class="nle-input" id="addTakeInput" placeholder="Add camera take path..." style="flex: 1; font-size: 0.75rem;" />
                <button type="button" class="cat-pill" onclick="addCameraTake()" style="font-size: 0.75rem; white-space: nowrap;">+ Add Take</button>
              </div>
            </div>

            <!-- Beat Grid & Tempo Card -->
            <div class="control-item" style="grid-column: 1 / -1;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                <span class="control-label">3. Rhythm &amp; Energy Grid (BPM)</span>
                <button type="button" class="cat-pill" onclick="analyzeMusicGrid()" style="font-size: 0.72rem;">
                  <i class="fa-solid fa-chart-simple"></i> Analyze Grid
                </button>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.5rem; margin-top: 0.3rem;">
                <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 0.4rem; text-align: center;">
                  <span style="font-size: 0.68rem; color: var(--text-muted); display: block;">TEMPO</span>
                  <input type="number" id="musicBpmInput" value="120" step="0.5" min="50" max="220" style="background: transparent; border: none; color: #06B6D4; font-size: 1.05rem; font-weight: 800; width: 60px; text-align: center;" />
                  <span style="font-size: 0.65rem; color: var(--text-muted);">BPM</span>
                </div>
                <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 0.4rem; text-align: center;">
                  <span style="font-size: 0.68rem; color: var(--text-muted); display: block;">MEASURES</span>
                  <span id="musicTotalBars" style="font-size: 1.05rem; font-weight: 800; color: #A78BFA;">--</span>
                  <span style="font-size: 0.65rem; color: var(--text-muted); display: block;">Bars (4/4)</span>
                </div>
                <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 0.4rem; text-align: center;">
                  <span style="font-size: 0.68rem; color: var(--text-muted); display: block;">808 / KICKS</span>
                  <span id="musicKickDrops" style="font-size: 1.05rem; font-weight: 800; color: #F43F5E;">--</span>
                  <span style="font-size: 0.65rem; color: var(--text-muted); display: block;">Transients</span>
                </div>
              </div>
              <div id="musicSectionsRow" style="display: flex; gap: 0.3rem; overflow-x: auto; margin-top: 0.4rem; padding-bottom: 0.2rem;">
                <span class="cat-pill" style="font-size: 0.68rem; opacity: 0.6;">Structure: Awaiting Analysis</span>
              </div>
            </div>

            <!-- Music Video Grammar & Motion Pumping Toggles -->
            <div class="control-item">
              <span class="control-label">Drop Punch-In</span>
              <label class="toggle-row">
                <span>808 Bass Extreme Close-Up Snap</span>
                <input type="checkbox" id="musicDropPunchToggle" checked />
              </label>
            </div>

            <div class="control-item">
              <span class="control-label">Motion Pumping</span>
              <label class="toggle-row">
                <span>Sub-Bass Camera Vibration (Bass Pump)</span>
                <input type="checkbox" id="musicBassPumpToggle" checked />
              </label>
            </div>

            <div class="control-item">
              <span class="control-label">Speed Ramping</span>
              <label class="toggle-row">
                <span>Cole Bennett Slow-to-Fast Transitions</span>
                <input type="checkbox" id="musicSpeedRampToggle" checked />
              </label>
            </div>

            <div class="control-item">
              <span class="control-label">Beat-Reactive Overlays</span>
              <label class="toggle-row">
                <span>Downbeat Flares &amp; Drop Glitches</span>
                <input type="checkbox" id="musicBeatFxToggle" checked />
              </label>
            </div>

          </div>
        </div>

        <!-- Panel: CapCut Blend Mode Overlay Engine (54+ Studio Textures) -->
        <div class="drawer-panel" id="panelOverlays" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item" style="grid-column: 1 / -1;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                <span class="control-label"><i class="fa-solid fa-wand-magic-sparkles"></i> 54+ Studio Overlays &amp; Textures</span>
                <span style="font-size: 0.72rem; color: var(--accent-neon); font-weight: 700;" id="activeOverlayBadge">No Overlay Active</span>
              </div>
              <p style="font-size: 0.76rem; color: var(--text-muted); margin: 0 0 0.5rem 0; line-height: 1.4;">
                Looping vintage films, Oppenheimer atomic fission, Sherlock Victorian mist, sci-fi telemetry HUDs, and light leaks.
              </p>
              
              <!-- Category Filter Tabs -->
              <div class="overlay-category-bar" style="display: flex; gap: 0.35rem; overflow-x: auto; padding-bottom: 0.4rem; margin-bottom: 0.5rem;">
                <button type="button" class="cat-pill active" onclick="filterOverlayCategory('All', this)">All (54)</button>
                <button type="button" class="cat-pill" onclick="filterOverlayCategory('Oppenheimer &amp; Atomic', this)">⚛️ Oppenheimer</button>
                <button type="button" class="cat-pill" onclick="filterOverlayCategory('Sherlock &amp; Victorian', this)">🕵️ Sherlock</button>
                <button type="button" class="cat-pill" onclick="filterOverlayCategory('Vintages &amp; Old Films', this)">🎞️ Vintages</button>
                <button type="button" class="cat-pill" onclick="filterOverlayCategory('Light Leaks &amp; Burns', this)">🔥 Leaks &amp; Burns</button>
                <button type="button" class="cat-pill" onclick="filterOverlayCategory('Sci-Fi &amp; Cyberpunk', this)">⚡ Sci-Fi &amp; HUD</button>
                <button type="button" class="cat-pill" onclick="filterOverlayCategory('Atmosphere &amp; Particles', this)">✨ Atmosphere</button>
              </div>

              <!-- Instant Search Filter -->
              <input type="text" class="nle-input" id="overlaySearchInput" placeholder="🔍 Search overlays (e.g. fire, fog, 16mm, laser, rain)..." oninput="searchOverlays(this.value)" style="margin-bottom: 0.6rem; font-size: 0.78rem; padding: 0.4rem 0.6rem; width: 100%; border: 1px solid var(--border-subtle); border-radius: 6px; background: var(--bg-surface); color: var(--text-main);" />

              <div class="overlay-cards-scroll" id="overlayCardsContainer">
                <div class="overlay-thumb-card active" id="ovCard_none" onclick="selectOverlay('none', 'No Overlay')">
                  <div class="ov-thumb-icon"><i class="fa-solid fa-ban"></i></div>
                  <div class="ov-thumb-name">None</div>
                  <div class="ov-thumb-tag">Clean</div>
                </div>
              </div>
            </div>

            <div class="control-item">
              <span class="control-label">Overlay Placement &amp; Subject Isolation</span>
              <select class="nle-select" id="overlayTargetSelect" onchange="applyLiveOverlaySettings()">
                <option value="fullscreen" selected>🌐 Fullscreen Blend (Entire Canvas)</option>
                <option value="background_only">👤 Behind Speaker (Background-Only Mask)</option>
              </select>
            </div>

            <div class="control-item">
              <span class="control-label">Blend Mode Algorithm</span>
              <select class="nle-select" id="overlayBlendModeSelect" onchange="applyLiveOverlaySettings()">
                <option value="screen" selected>⚡ Screen (Viral CapCut standard - keeps colors &amp; brights)</option>
                <option value="addition">💥 Addition / Linear Dodge (Super bright glow &amp; bloom)</option>
                <option value="overlay">🎞️ Overlay (Contrast enhancement &amp; rich shadows)</option>
                <option value="lighten">🌟 Lighten (Retains brightest pixels)</option>
                <option value="softlight">🌫️ Soft Light (Subtle analog film wash)</option>
              </select>
            </div>

            <div class="control-item">
              <span class="control-label">Blend Opacity (<span id="overlayOpacityVal">85%</span>)</span>
              <input type="range" class="nle-range-slider" id="overlayOpacitySlider" min="10" max="100" value="85" oninput="document.getElementById('overlayOpacityVal').innerText = this.value + '%'; applyLiveOverlaySettings();" />
            </div>
          </div>
        </div>

        <!-- Panel 10: CapCut / NLE FX Studio -->
        <div class="drawer-panel" id="panelEffects" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Pro-Mist Highlight Diffusion Bloom</span>
              <select class="nle-select" id="fxGlowSelect" onchange="applyLiveFilters()">
                <option value="none" selected>None (Standard Sharpness)</option>
                <option value="promist">1/4 Black Pro-Mist (Creamy highlights &amp; smooth skin)</option>
                <option value="dreamy">Dreamy Ethereal Bloom (Vivid soft glow)</option>
              </select>
            </div>

            <div class="control-item">
              <span class="control-label">Chromatic Aberration (RGB Split)</span>
              <select class="nle-select" id="fxRgbSelect" onchange="applyLiveFilters()">
                <option value="none" selected>None (Clean Edges)</option>
                <option value="subtle">Subtle Optical Lens Fringe (3px Red/Cyan offset)</option>
                <option value="heavy">Cyberpunk Glitch Displacement (6px RGB shift)</option>
              </select>
            </div>

            <div class="control-item">
              <span class="control-label">Simulated Camera Motion</span>
              <select class="nle-select" id="fxMotionSelect" onchange="applyLiveFilters()">
                <option value="none" selected>Static Locked Off (Tripod)</option>
                <option value="handheld">Handheld Operator Drift (Organic human breathing)</option>
                <option value="quake">Action Impact Quake (Cut &amp; beat shudder)</option>
              </select>
            </div>

            <div class="control-item">
              <span class="control-label">90s Retro Camcorder Viewfinder OSD</span>
              <label class="toggle-row">
                <span>Blinking REC ●, Battery, TC &amp; Framing HUD</span>
                <input type="checkbox" id="fxCamcorderToggle" onchange="applyLiveFilters()" />
              </label>
            </div>

            <div class="control-item">
              <span class="control-label">Portrait Depth Blur (Tilt-Shift)</span>
              <label class="toggle-row">
                <span>Soft background blur (keeps subject face in sharp focus)</span>
                <input type="checkbox" id="fxTiltShiftToggle" onchange="applyLiveFilters()" />
              </label>
            </div>

            <div class="control-item">
              <span class="control-label">Vintage Film Gate Flicker</span>
              <label class="toggle-row">
                <span>Analog 35mm projector gate luminance breathing</span>
                <input type="checkbox" id="fxFlickerToggle" onchange="applyLiveFilters()" />
              </label>
            </div>

            <div class="control-item">
              <span class="control-label">Analog 35mm Film Grain</span>
              <label class="toggle-row">
                <span>Organic silver halide film grain noise</span>
                <input type="checkbox" id="filmGrainToggle" onchange="applyLiveFilters()" />
              </label>
            </div>

            <div class="control-item">
              <span class="control-label">Cinema Letterbox</span>
              <label class="toggle-row">
                <span>2.35:1 Anamorphic Top/Bottom Bars</span>
                <input type="checkbox" id="letterboxToggle" onchange="applyLiveFilters()" />
              </label>
            </div>

            <div class="control-item">
              <span class="control-label">Organic Lens Vignette</span>
              <label class="toggle-row">
                <span>Subtle Corner Shadow Falloff</span>
                <input type="checkbox" id="vignetteToggle" checked onchange="applyLiveFilters()" />
              </label>
            </div>
          </div>
        </div>

        <!-- Panel 11: Text & Titles -->
        <div class="drawer-panel" id="panelText" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Broadcast Lower-Third Title</span>
              <label class="toggle-row">
                <span>Animated Title Card in Intro</span>
                <input type="checkbox" id="showTitleToggle" checked onchange="applyLiveFilters()" />
              </label>
            </div>
            <div class="control-item">
              <span class="control-label">Main Headline Title</span>
              <input type="text" class="nle-input" id="titleTextInput" value="OMNICAM AI • MULTI-CAM PRODUCTION" placeholder="Headline text..." oninput="applyLiveFilters()" />
            </div>
            <div class="control-item">
              <span class="control-label">Subtitle / Presenter Line</span>
              <input type="text" class="nle-input" id="subtitleTextInput" value="PRO VIRTUAL STUDIO // 4K CLARITY" placeholder="Presenter handle or subtitle..." oninput="applyLiveFilters()" />
            </div>
            <div class="control-item">
              <span class="control-label">Virtual Camera HUD Badge</span>
              <label class="toggle-row">
                <span>Show CAM 1 / CAM 2 + Red REC Dot</span>
                <input type="checkbox" id="hudToggle" checked />
              </label>
            </div>
            <div class="control-item">
              <span class="control-label">Custom Watermark Handle</span>
              <input type="text" class="nle-input" id="customWatermarkInput" placeholder="@channel_name or logo text" />
            </div>
          </div>
        </div>

        <!-- Panel 12: Canvas Ratio -->
        <div class="drawer-panel" id="panelRatio" style="display: none;">
          <div class="drawer-controls-grid">
            <div class="control-item">
              <span class="control-label">Video Canvas Aspect Ratio</span>
              <div style="display: flex; gap: 0.5rem; margin-top: 0.25rem;">
                <button class="btn-action-glow ratio-btn active" id="btnRatio169" onclick="setAspectRatio('16:9')" type="button" style="flex: 1; flex-direction: column; padding: 0.75rem 0.5rem; gap: 0.3rem;">
                  <i class="fa-solid fa-desktop" style="font-size: 1.25rem; color: var(--accent-neon);"></i>
                  <span style="font-weight: 700; font-size: 0.82rem;">16:9 Landscape</span>
                  <span style="font-size: 0.65rem; color: var(--text-dim);">YouTube / Desktop</span>
                </button>
                <button class="btn-action-glow ratio-btn" id="btnRatio916" onclick="setAspectRatio('9:16')" type="button" style="flex: 1; flex-direction: column; padding: 0.75rem 0.5rem; gap: 0.3rem;">
                  <i class="fa-solid fa-mobile-screen" style="font-size: 1.25rem; color: #EC4899;"></i>
                  <span style="font-weight: 700; font-size: 0.82rem;">9:16 Vertical</span>
                  <span style="font-size: 0.65rem; color: var(--text-dim);">TikTok / Reels / Shorts</span>
                </button>
                <button class="btn-action-glow ratio-btn" id="btnRatio11" onclick="setAspectRatio('1:1')" type="button" style="flex: 1; flex-direction: column; padding: 0.75rem 0.5rem; gap: 0.3rem;">
                  <i class="fa-solid fa-square" style="font-size: 1.25rem; color: #10B981;"></i>
                  <span style="font-weight: 700; font-size: 0.82rem;">1:1 Square</span>
                  <span style="font-size: 0.65rem; color: var(--text-dim);">Instagram Feed</span>
                </button>
              </div>
            </div>
            <div class="control-item">
              <span class="control-label">AI Center Framing</span>
              <span style="font-size: 0.78rem; color: var(--text-muted); line-height: 1.4;">
                OmniCam automatically crops around the subject's face to keep you perfectly framed across all aspect ratios without cutting off your headroom.
              </span>
            </div>
          </div>
        </div>
      </div>
      </aside>
    </div>

  </div>

  <!-- ========================================================================
       DEVICE FILE NAVIGATOR MODAL
       ======================================================================== -->
  <div id="deviceBrowserModal" class="modal-backdrop" style="display: none;">
    <div class="modal-window">
      <div class="modal-header">
        <div style="display: flex; align-items: center; gap: 0.65rem;">
          <div class="browser-item-icon icon-folder">
            <i class="fa-solid fa-folder-tree"></i>
          </div>
          <div>
            <h3 style="font-family: var(--font-display); font-size: 1.05rem; color: var(--text-white); font-weight: 800;">
              Device Storage Explorer
            </h3>
            <span style="font-size: 0.72rem; color: var(--text-muted);">Select video to direct</span>
          </div>
        </div>
        <button class="modal-close-btn" onclick="closeFileBrowser()" type="button">&times;</button>
      </div>

      <div class="modal-roots-bar" id="browserRootsBar"></div>

      <div class="browser-nav-bar">
        <button class="btn-action-glow" id="browserUpBtn" onclick="navigateBrowserUp()" type="button" style="padding: 0.3rem 0.65rem; font-size: 0.75rem;">
          <i class="fa-solid fa-arrow-up"></i> Up
        </button>
        <div class="browser-breadcrumbs" id="browserBreadcrumbs"></div>
      </div>

      <div style="padding: 0.5rem 1.25rem; background: var(--bg-main);">
        <input type="text" class="nle-input" id="browserSearchInput" placeholder="Search / filter files..." oninput="filterBrowserList(this.value)" style="width: 100%;" />
      </div>

      <div class="browser-list-container" id="browserListContainer">
        <div style="padding: 2.5rem; text-align: center; color: var(--text-muted);">
          <i class="fa-solid fa-spinner fa-spin"></i> Reading storage...
        </div>
      </div>

      <div class="modal-footer">
        <span style="font-size: 0.75rem; color: var(--text-muted);" id="browserStatusText">0 items found</span>
        <button class="btn-action-glow" onclick="closeFileBrowser()" type="button" style="padding: 0.35rem 0.85rem; font-size: 0.8rem;">Close</button>
      </div>
    </div>
  </div>

  <!-- ========================================================================
       RENDER & EXPORT MODAL
       ======================================================================== -->
  <div id="exportProgressModal" class="modal-backdrop" style="display: none;">
    <div class="modal-window" style="max-width: 580px;">
      <div class="modal-header">
        <div style="display: flex; align-items: center; gap: 0.65rem;">
          <div class="browser-item-icon icon-video">
            <i class="fa-solid fa-bolt"></i>
          </div>
          <div>
            <h3 style="font-family: var(--font-display); font-size: 1.05rem; color: var(--text-white); font-weight: 800;">
              OmniCam Studio Render
            </h3>
            <span style="font-size: 0.72rem; color: var(--text-muted);">Multi-Camera Studio Master</span>
          </div>
        </div>
        <button class="modal-close-btn" onclick="closeExportModal()" type="button">&times;</button>
      </div>

      <div style="padding: 1.5rem 1.25rem;">
        <!-- Render Progress -->
        <div id="exportActiveState">
          <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-size: 0.82rem;">
            <span style="color: var(--text-muted);" id="exportStatusMsg"><i class="fa-solid fa-spinner fa-spin"></i> Rendering multi-camera cuts...</span>
            <span style="font-weight: 800; color: var(--accent-neon);" id="exportProgressPct">0%</span>
          </div>
          <div style="height: 8px; background: var(--bg-surface); border-radius: var(--radius-full); overflow: hidden; margin-bottom: 1.25rem;">
            <div id="exportProgressBar" style="height: 100%; width: 0%; background: linear-gradient(90deg, #00F0FF, #2563EB); transition: width 0.3s ease;"></div>
          </div>
        </div>

        <!-- Render Complete -->
        <div id="exportCompleteState" style="display: none; text-align: center;">
          <div style="width: 52px; height: 52px; border-radius: 50%; background: rgba(16, 185, 129, 0.15); color: #10B981; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; margin: 0 auto 0.75rem;">
            <i class="fa-solid fa-check"></i>
          </div>
          <h4 style="font-family: var(--font-display); font-size: 1.15rem; color: var(--text-white); margin-bottom: 0.25rem;">
            Master Cut Complete!
          </h4>

          <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 0.45rem 0.85rem; font-size: 0.78rem; color: #34D399; font-weight: 700; margin: 0.65rem auto 1rem; display: flex; align-items: center; justify-content: center; gap: 0.5rem; max-width: 440px;">
            <i class="fa-solid fa-circle-check"></i> <span id="exportSavedPathBadge">Saved automatically to device storage &amp; Downloads!</span>
          </div>

          <video id="exportCompletePlayer" controls playsinline style="width: 100%; max-height: 220px; border-radius: var(--radius-md); background: #000; margin-bottom: 1rem; border: 1px solid var(--border-subtle);"></video>

          <div style="display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap;">
            <a id="downloadVideoLink" class="btn-action-glow btn-action-primary" href="#" download style="text-decoration: none;">
              <i class="fa-solid fa-download"></i> Save / Download Again
            </a>
            <button class="btn-action-glow" onclick="playRenderedInMonitor(); closeExportModal();" type="button">
              <i class="fa-solid fa-film"></i> Open in Editor Monitor
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ========================================================================
       NLE CLIENT JAVASCRIPT
       ======================================================================== -->
  <script>
    let currentShots = [];
    let currentTotalDur = 0;
    let activeDrawerPanel = null;
    let selectedOverlayEffect = 'none';
    let allOverlaysList = [];
    let activeOverlayCategory = 'All';

    async function loadOverlaysCatalog() {
      try {
        const res = await fetch('/api/overlays');
        const data = await res.json();
        allOverlaysList = data.overlays || [];
        renderOverlayCards();
      } catch (err) {
        console.warn('Could not fetch overlays catalog:', err);
      }
    }

    function renderOverlayCards(filteredList) {
      const container = document.getElementById('overlayCardsContainer');
      if (!container) return;

      const list = filteredList || (activeOverlayCategory === 'All' 
        ? allOverlaysList 
        : allOverlaysList.filter(o => o.category === activeOverlayCategory));

      let html = `
        <div class="overlay-thumb-card ${selectedOverlayEffect === 'none' ? 'active' : ''}" id="ovCard_none" onclick="selectOverlay('none', 'No Overlay')">
          <div class="ov-thumb-icon"><i class="fa-solid fa-ban"></i></div>
          <div class="ov-thumb-name">None</div>
          <div class="ov-thumb-tag">Clean</div>
        </div>
      `;

      list.forEach(o => {
        let iconHtml = '<i class="fa-solid fa-wand-magic-sparkles"></i>';
        let iconColor = '#00F0FF';
        const cat = o.category || '';
        if (cat.includes('Oppenheimer')) {
          iconHtml = '<i class="fa-solid fa-atom"></i>';
          iconColor = '#F59E0B';
        } else if (cat.includes('Sherlock')) {
          iconHtml = '<i class="fa-solid fa-magnifying-glass"></i>';
          iconColor = '#38BDF8';
        } else if (cat.includes('Vintage')) {
          iconHtml = '<i class="fa-solid fa-film"></i>';
          iconColor = '#A3E635';
        } else if (cat.includes('Leaks') || cat.includes('Burns')) {
          iconHtml = '<i class="fa-solid fa-fire"></i>';
          iconColor = '#FB923C';
        } else if (cat.includes('Sci-Fi')) {
          iconHtml = '<i class="fa-solid fa-crosshairs"></i>';
          iconColor = '#00F0FF';
        } else if (cat.includes('Atmosphere')) {
          iconHtml = '<i class="fa-solid fa-sparkles"></i>';
          iconColor = '#E879F9';
        }

        const isAct = (selectedOverlayEffect === o.id) ? 'active' : '';
        const shortName = o.title.replace('Oppenheimer ', '').replace('Sherlock ', '');
        const escTitle = o.title.replace(/'/g, "\\'");
        html += `
          <div class="overlay-thumb-card ${isAct}" id="ovCard_${o.id}" onclick="selectOverlay('${o.id}', '${escTitle}')" title="${o.description}">
            <div class="ov-thumb-icon" style="color: ${iconColor};">${iconHtml}</div>
            <div class="ov-thumb-name">${shortName}</div>
            <div class="ov-thumb-tag">${cat.split(' ')[0]}</div>
          </div>
        `;
      });

      container.innerHTML = html;
    }

    function filterOverlayCategory(cat, btn) {
      activeOverlayCategory = cat;
      document.querySelectorAll('.cat-pill').forEach(b => b.classList.remove('active'));
      if (btn) btn.classList.add('active');
      const searchVal = document.getElementById('overlaySearchInput')?.value.trim().toLowerCase() || '';
      if (searchVal) {
        searchOverlays(searchVal);
      } else {
        renderOverlayCards();
      }
    }

    function searchOverlays(query) {
      const q = (query || '').toLowerCase().trim();
      if (!q) {
        renderOverlayCards();
        return;
      }
      const filtered = allOverlaysList.filter(o => {
        const matchCat = (activeOverlayCategory === 'All' || o.category === activeOverlayCategory);
        const matchText = (o.title || '').toLowerCase().includes(q) || (o.description || '').toLowerCase().includes(q) || (o.id || '').toLowerCase().includes(q);
        return matchCat && matchText;
      });
      renderOverlayCards(filtered);
    }

    function selectOverlay(overlayId, title) {
      selectedOverlayEffect = overlayId;
      document.querySelectorAll('.overlay-thumb-card').forEach(c => c.classList.remove('active'));
      const activeCard = document.getElementById('ovCard_' + overlayId);
      if (activeCard) activeCard.classList.add('active');

      const badge = document.getElementById('activeOverlayBadge');
      if (badge) {
        if (overlayId === 'none') {
          badge.innerText = 'No Overlay Active';
          badge.style.color = 'var(--text-muted)';
        } else {
          badge.innerText = 'Active: ' + title;
          badge.style.color = 'var(--accent-neon)';
        }
      }

      updateLiveOverlay(overlayId);
    }

    function updateLiveOverlay(overlayId) {
      const overlayVideo = document.getElementById('liveOverlayPlayer');
      if (!overlayVideo) return;

      if (!overlayId || overlayId === 'none') {
        overlayVideo.style.opacity = '0';
        overlayVideo.pause();
        return;
      }

      const blendSelect = document.getElementById('overlayBlendModeSelect');
      const opacitySlider = document.getElementById('overlayOpacitySlider');
      let blendMode = blendSelect ? blendSelect.value : 'screen';
      if (blendMode === 'addition') blendMode = 'screen';
      const opacity = opacitySlider ? parseFloat(opacitySlider.value) / 100.0 : 0.85;

      overlayVideo.src = '/assets/overlays/' + overlayId + '.mp4';
      overlayVideo.style.mixBlendMode = blendMode;
      overlayVideo.style.opacity = opacity.toString();
      overlayVideo.currentTime = 0;

      const player = document.getElementById('studioVideoPlayer');
      if (player && !player.paused) {
        overlayVideo.play().catch(() => {});
      } else {
        overlayVideo.play().catch(() => {});
        setTimeout(() => {
          const p = document.getElementById('studioVideoPlayer');
          if (p && p.paused) overlayVideo.pause();
        }, 120);
      }
      applyLiveOverlaySettings();
    }

    function applyLiveOverlaySettings() {
      const overlayVideo = document.getElementById('liveOverlayPlayer');
      if (!overlayVideo || selectedOverlayEffect === 'none') return;

      const blendSelect = document.getElementById('overlayBlendModeSelect');
      const opacitySlider = document.getElementById('overlayOpacitySlider');
      const targetSelect = document.getElementById('overlayTargetSelect');

      if (blendSelect) {
        let bm = blendSelect.value;
        if (bm === 'addition') bm = 'screen';
        overlayVideo.style.mixBlendMode = bm;
      }
      if (opacitySlider) {
        overlayVideo.style.opacity = (parseFloat(opacitySlider.value) / 100.0).toString();
      }
      if (targetSelect && targetSelect.value === 'background_only') {
        const maskGrad = 'radial-gradient(ellipse 65% 85% at 50% 48%, transparent 40%, black 75%)';
        overlayVideo.style.webkitMaskImage = maskGrad;
        overlayVideo.style.maskImage = maskGrad;
      } else {
        overlayVideo.style.webkitMaskImage = 'none';
        overlayVideo.style.maskImage = 'none';
      }
    }

    function applyLiveFilters() {
      const player = document.getElementById('studioVideoPlayer');
      if (!player) return;

      const filterParts = [];

      // 1. Color Grading Filter
      const grade = (document.getElementById('colorGradeSelect')?.value || 'cinematic').toLowerCase();
      if (grade === 'cinematic') {
        filterParts.push('contrast(1.16) brightness(1.02) saturate(1.22) sepia(0.08) hue-rotate(-5deg)');
      } else if (grade === 'podcast') {
        filterParts.push('contrast(1.12) brightness(1.04) saturate(1.28)');
      } else if (grade === 'vintage') {
        filterParts.push('contrast(1.04) brightness(0.98) saturate(0.82) sepia(0.24) hue-rotate(-8deg)');
      } else if (grade === 'noir' || grade === 'oppenheimer_mono') {
        filterParts.push('contrast(1.35) brightness(0.96) grayscale(1.0)');
      } else if (grade === 'oppenheimer_fission') {
        filterParts.push('contrast(1.28) brightness(1.02) saturate(1.35) sepia(0.28) hue-rotate(-15deg)');
      } else if (grade === 'sherlock_noir') {
        filterParts.push('contrast(1.18) brightness(0.96) saturate(0.55) sepia(0.12) hue-rotate(160deg)');
      } else if (grade === 'sherlock_gaslamp') {
        filterParts.push('contrast(1.14) brightness(0.98) saturate(0.75) sepia(0.38) hue-rotate(-20deg)');
      } else if (grade === 'vintage_technicolor') {
        filterParts.push('contrast(1.16) brightness(1.02) saturate(1.50)');
      }

      // Selective Color Isolation Live GPU Preview
      const selColor = document.getElementById('selectiveColorSelect')?.value || 'none';
      const targetP = document.getElementById('targetPersonSelect')?.value || 'primary';
      const scOverlay = document.getElementById('liveSelectiveColorOverlay');
      if (scOverlay) {
        if (selColor === 'none') {
          scOverlay.style.display = 'none';
        } else {
          scOverlay.style.display = 'block';
          let px = 50;
          if (targetP === 'left') px = 35;
          else if (targetP === 'right') px = 65;

          if (selColor === 'person_color_bg_mono') {
            scOverlay.style.backdropFilter = 'grayscale(1) contrast(1.35) brightness(0.95)';
          } else if (selColor === 'person_color_bg_sherlock') {
            scOverlay.style.backdropFilter = 'contrast(1.15) saturate(0.50) sepia(0.35) hue-rotate(150deg)';
          } else if (selColor === 'person_color_bg_oppenheimer') {
            scOverlay.style.backdropFilter = 'contrast(1.28) saturate(1.35) sepia(0.40) hue-rotate(-15deg)';
          } else if (selColor === 'bg_grade_only') {
            scOverlay.style.backdropFilter = filterParts.join(' ') || 'none';
          } else {
            scOverlay.style.backdropFilter = 'grayscale(0.8) contrast(1.2)';
          }
          const maskStr = `radial-gradient(ellipse 30% 45% at ${px}% 48%, transparent 40%, black 80%)`;
          scOverlay.style.webkitMaskImage = maskStr;
          scOverlay.style.maskImage = maskStr;
        }
      }

      // 2. Pro-Mist Highlight Diffusion Bloom FX
      const glowFx = document.getElementById('fxGlowSelect')?.value || 'none';
      if (glowFx === 'promist') {
        filterParts.push('drop-shadow(0 0 10px rgba(255, 245, 220, 0.45)) brightness(1.04)');
      } else if (glowFx === 'dreamy') {
        filterParts.push('drop-shadow(0 0 18px rgba(255, 235, 210, 0.65)) brightness(1.08)');
      }

      // 3. Chromatic Aberration RGB Split FX
      const rgbFx = document.getElementById('fxRgbSelect')?.value || 'none';
      if (rgbFx === 'subtle') {
        filterParts.push('drop-shadow(-3px 0 0 rgba(255, 30, 80, 0.35)) drop-shadow(3px 0 0 rgba(0, 240, 255, 0.35))');
      } else if (rgbFx === 'heavy') {
        filterParts.push('drop-shadow(-6px 0 0 rgba(255, 30, 80, 0.6)) drop-shadow(6px 0 0 rgba(0, 240, 255, 0.6))');
      }

      player.style.filter = filterParts.length > 0 ? filterParts.join(' ') : 'none';

      // 4. Camera Motion FX (Handheld camera drift or Quake)
      const motionFx = document.getElementById('fxMotionSelect')?.value || 'none';
      player.classList.remove('fx-handheld-motion', 'fx-quake-motion');
      if (motionFx === 'handheld') {
        player.classList.add('fx-handheld-motion');
      } else if (motionFx === 'quake') {
        player.classList.add('fx-quake-motion');
      }

      // 5. 90s Camcorder Viewfinder OSD
      const isCamcorder = document.getElementById('fxCamcorderToggle')?.checked || false;
      const camHud = document.getElementById('liveCamcorderHud');
      if (camHud) camHud.style.display = isCamcorder ? 'block' : 'none';

      // 6. Portrait Depth Blur (Tilt-Shift)
      const isTiltShift = document.getElementById('fxTiltShiftToggle')?.checked || false;
      const tsElem = document.getElementById('liveTiltShiftOverlay');
      if (tsElem) tsElem.style.display = isTiltShift ? 'block' : 'none';

      // 7. Vintage Film Gate Flicker
      const isFlicker = document.getElementById('fxFlickerToggle')?.checked || false;
      const flkElem = document.getElementById('liveFilmFlickerOverlay');
      if (flkElem) flkElem.style.display = isFlicker ? 'block' : 'none';

      // 8. 35mm Film Grain
      const isGrain = document.getElementById('filmGrainToggle')?.checked || false;
      const grain = document.getElementById('liveFilmGrainOverlay');
      if (grain) grain.style.display = isGrain ? 'block' : 'none';

      // 9. Anamorphic 2.35:1 Letterbox Bars
      const isLetterbox = document.getElementById('letterboxToggle')?.checked || false;
      const lbTop = document.getElementById('liveLetterboxTop');
      const lbBottom = document.getElementById('liveLetterboxBottom');
      if (lbTop && lbBottom) {
        lbTop.style.display = isLetterbox ? 'block' : 'none';
        lbBottom.style.display = isLetterbox ? 'block' : 'none';
      }

      // 10. Lens Vignette
      const isVignette = document.getElementById('vignetteToggle')?.checked || false;
      const vig = document.getElementById('liveVignetteOverlay');
      if (vig) vig.style.display = isVignette ? 'block' : 'none';

      // 11. Lower-Third Title
      const isTitle = document.getElementById('showTitleToggle')?.checked || false;
      const titleBox = document.getElementById('liveLowerThirdOverlay');
      if (titleBox) {
        titleBox.style.display = isTitle ? 'block' : 'none';
        const tInput = document.getElementById('titleTextInput');
        const sInput = document.getElementById('subtitleTextInput');
        const tElem = document.getElementById('liveTitleText');
        const sElem = document.getElementById('liveSubtitleText');
        if (tInput && tElem) tElem.innerText = tInput.value.trim() || 'OMNICAM AI • MULTI-CAM PRODUCTION';
        if (sInput && sElem) sElem.innerText = sInput.value.trim() || 'PRO VIRTUAL STUDIO // 4K CLARITY';
      }
    }
    let renderedOutputPath = null;
    let currentAspectRatio = '16:9';

    function setAspectRatio(ratio) {
      currentAspectRatio = ratio;
      const box = document.getElementById('monitorCanvasBox');
      const select = document.getElementById('aspectRatioSelect');
      if (select) select.value = ratio;

      document.querySelectorAll('.ratio-btn').forEach(b => b.classList.remove('active'));
      if (ratio === '16:9') {
        box.style.aspectRatio = '16 / 9';
        box.style.maxWidth = '900px';
        const b = document.getElementById('btnRatio169');
        if (b) b.classList.add('active');
      } else if (ratio === '9:16') {
        box.style.aspectRatio = '9 / 16';
        box.style.maxWidth = '360px';
        const b = document.getElementById('btnRatio916');
        if (b) b.classList.add('active');
      } else if (ratio === '1:1') {
        box.style.aspectRatio = '1 / 1';
        box.style.maxWidth = '500px';
        const b = document.getElementById('btnRatio11');
        if (b) b.classList.add('active');
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    // ------------------------------------------------------------------------
    // TOOL DRAWER CONTROLLER
    // ------------------------------------------------------------------------
    function openToolPanel(panelId, iconClass) {
      const drawer = document.getElementById('inspectorDrawer');
      const title = document.getElementById('drawerTitle');
      const rightPanel = document.getElementById('desktopRightPanel');

      // Reset active states on both bottom dock and top nav ribbon
      document.querySelectorAll('.dock-tool-btn, .top-tool-chip').forEach(b => b.classList.remove('active'));

      if (activeDrawerPanel === panelId && drawer.classList.contains('open')) {
        closeDrawer();
        return;
      }

      // Hide all panels
      document.querySelectorAll('.drawer-panel').forEach(p => p.style.display = 'none');

      const targetPanel = document.getElementById('panel' + panelId);
      if (targetPanel) targetPanel.style.display = 'block';

      title.innerHTML = '<i class="fa-solid ' + iconClass + '"></i> ' + panelId + ' Settings';
      drawer.classList.add('open');
      if (rightPanel) rightPanel.style.display = 'flex';

      // Sync active state and auto-scroll top nav chip into view
      const topBtn = document.getElementById('topBtn' + panelId);
      if (topBtn) {
        topBtn.classList.add('active');
        topBtn.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
      }

      activeDrawerPanel = panelId;
    }

    function closeDrawer() {
      const drawer = document.getElementById('inspectorDrawer');
      const rightPanel = document.getElementById('desktopRightPanel');
      drawer.classList.remove('open');
      document.querySelectorAll('.dock-tool-btn, .top-tool-chip').forEach(b => b.classList.remove('active'));
      
      // On mobile hide the floating sheet; on desktop keep right panel ready
      if (window.innerWidth <= 768 && rightPanel) {
        rightPanel.style.display = 'none';
      }
      activeDrawerPanel = null;
    }

    // ------------------------------------------------------------------------
    // GALLERY & NATIVE FILE PICKER
    // ------------------------------------------------------------------------
    async function handleNativeFileSelect(input) {
      const file = input.files && input.files[0];
      if (!file) return;

      const badge = document.getElementById('uploadStatusBadge');
      const msg = document.getElementById('uploadStatusMsg');
      badge.style.display = 'block';
      msg.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Fast-linking: <strong>' + escapeHtml(file.name) + '</strong>...';

      // 1. Fast path match
      try {
        const findRes = await fetch('/api/find_local?name=' + encodeURIComponent(file.name) + '&size=' + file.size);
        const findData = await findRes.json();
        if (findData.found && findData.path) {
          selectVideoSource(findData.path, file.name);
          badge.style.display = 'none';
          input.value = '';
          return;
        }
      } catch (e) {}

      // 2. Fallback stream upload
      msg.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading from gallery (0%)...';
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload', true);
      xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name));
      xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');

      xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          msg.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading from gallery (' + pct + '%)...';
        }
      };

      xhr.onload = function() {
        if (xhr.status === 200) {
          try {
            const resp = JSON.parse(xhr.responseText);
            if (resp.path) {
              selectVideoSource(resp.path, file.name);
              badge.style.display = 'none';
              input.value = '';
              return;
            }
          } catch (err) {}
        }
        msg.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Failed to load video from gallery.';
      };

      xhr.onerror = function() {
        msg.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Connection error during upload.';
      };

      xhr.send(file);
    }

    // ------------------------------------------------------------------------
    // REAL-TIME VIRTUAL PLAYHEAD ENGINE (CapCut-Style Live Non-Destructive Editing)
    // ------------------------------------------------------------------------
    let liveDirectorEnabled = true;
    let activeShotIndex = -1;
    let isFreezeHolding = false;
    let playbackRaf = null;
    let audioCtx = null;

    function playWhooshSfx() {
      try {
        if (!audioCtx) {
          audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
          audioCtx.resume();
        }
        const bufferSize = Math.floor(audioCtx.sampleRate * 0.16);
        const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
          data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize);
        }
        const noise = audioCtx.createBufferSource();
        noise.buffer = buffer;
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.setValueAtTime(950, audioCtx.currentTime);
        filter.frequency.exponentialRampToValueAtTime(120, audioCtx.currentTime + 0.15);
        const gain = audioCtx.createGain();
        gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.15);
        noise.connect(filter);
        filter.connect(gain);
        gain.connect(audioCtx.destination);
        noise.start();
      } catch (e) {}
    }

    function applyShotFraming(shot) {
      const player = document.getElementById('studioVideoPlayer');
      if (!player) return;
      if (!liveDirectorEnabled) {
        player.style.setProperty('--cam-scale', '1.0');
        player.style.setProperty('--cam-tx', '0px');
        player.style.setProperty('--cam-ty', '0px');
        player.style.transform = 'scale(1.0) translate(0, 0)';
        return;
      }
      const angle = (shot.angle || 'WIDE').toUpperCase();
      let scale = 1.0;
      let tx = '0%';
      let ty = '0%';
      if (angle === 'CLOSEUP' || angle === 'CLOSE_UP') {
        scale = 1.36; tx = '0%'; ty = '-4%';
      } else if (angle === 'THIRD_LEFT' || angle === 'LEFT_THIRD') {
        scale = 1.28; tx = '-6%'; ty = '-3%';
      } else if (angle === 'THIRD_RIGHT' || angle === 'RIGHT_THIRD') {
        scale = 1.28; tx = '6%'; ty = '-3%';
      } else if (angle === 'SLOW_PUSH') {
        scale = 1.22; tx = '0%'; ty = '-2%';
      } else if (angle === 'BROLL') {
        scale = 1.06; tx = '0%'; ty = '0%';
      }
      player.style.setProperty('--cam-scale', scale);
      player.style.setProperty('--cam-tx', tx);
      player.style.setProperty('--cam-ty', ty);
      player.style.transform = `scale(${scale}) translate(${tx}, ${ty})`;
    }

    function applyLiveColorGrade() {
      const player = document.getElementById('studioVideoPlayer');
      if (!player) return;
      if (!liveDirectorEnabled) {
        player.style.filter = 'none';
        return;
      }
      const grade = (document.getElementById('colorGradeSelect')?.value || 'cinematic').toLowerCase();
      if (grade === 'cinematic') {
        player.style.filter = 'contrast(1.14) brightness(1.02) saturate(1.22) sepia(0.08) hue-rotate(-5deg)';
      } else if (grade === 'podcast') {
        player.style.filter = 'contrast(1.10) brightness(1.03) saturate(1.25)';
      } else if (grade === 'vintage') {
        player.style.filter = 'contrast(1.02) saturate(0.85) sepia(0.20) hue-rotate(-6deg)';
      } else {
        player.style.filter = 'none';
      }
    }

    function triggerCutTransition() {
      const overlay = document.getElementById('playerFlashOverlay');
      if (!overlay) return;
      overlay.classList.remove('flash-active');
      void overlay.offsetWidth;
      overlay.classList.add('flash-active');
    }

    function holdFreezeFrame(shot) {
      isFreezeHolding = true;
      const player = document.getElementById('studioVideoPlayer');
      const freezeBadge = document.getElementById('freezeBadgeOverlay');
      if (player) player.pause();
      if (freezeBadge) freezeBadge.style.display = 'inline-flex';
      playWhooshSfx();

      const durMs = Math.round((shot.freeze_duration || 0.6) * 1000);
      setTimeout(() => {
        if (freezeBadge) freezeBadge.style.display = 'none';
        isFreezeHolding = false;
        const nextShot = currentShots[activeShotIndex + 1];
        if (nextShot && player) {
          triggerCutTransition();
          player.currentTime = nextShot.start;
          player.play().catch(() => {});
        }
      }, durMs);
    }

    function toggleLiveDirector() {
      liveDirectorEnabled = !liveDirectorEnabled;
      const btn = document.getElementById('btnLiveDirectorToggle');
      const text = document.getElementById('liveDirectorText');
      const player = document.getElementById('studioVideoPlayer');
      if (liveDirectorEnabled) {
        if (btn) {
          btn.style.color = 'var(--accent-neon)';
          btn.style.borderColor = 'rgba(0, 240, 255, 0.4)';
          btn.style.background = 'rgba(0, 240, 255, 0.08)';
        }
        if (text) text.innerText = 'Live Edit: ON';
        applyLiveColorGrade();
        if (activeShotIndex >= 0 && activeShotIndex < currentShots.length) {
          applyShotFraming(currentShots[activeShotIndex]);
        }
      } else {
        if (btn) {
          btn.style.color = 'var(--text-dim)';
          btn.style.borderColor = 'var(--border-subtle)';
          btn.style.background = 'transparent';
        }
        if (text) text.innerText = 'Raw Footage';
        if (player) {
          player.style.transform = 'scale(1.0) translate(0, 0)';
          player.style.filter = 'none';
        }
      }
    }

    function startPlaybackLoop() {
      cancelAnimationFrame(playbackRaf);
      function loop() {
        const player = document.getElementById('studioVideoPlayer');
        if (player && !player.paused) {
          syncRealtimePlayback(player.currentTime);
          playbackRaf = requestAnimationFrame(loop);
        }
      }
      playbackRaf = requestAnimationFrame(loop);
    }

    function stopPlaybackLoop() {
      if (playbackRaf) {
        cancelAnimationFrame(playbackRaf);
        playbackRaf = null;
      }
    }

    // ------------------------------------------------------------------------
    // VIDEO SOURCE SELECTION & PLAYBACK
    // ------------------------------------------------------------------------
    function selectVideoSource(filePath, displayName) {
      document.getElementById('inputVideo').value = filePath;
      const fn = displayName || filePath.split('/').pop();
      document.getElementById('topbarClipName').innerText = fn;

      // Switch Viewport to Player
      document.getElementById('emptyStateCard').style.display = 'none';
      const player = document.getElementById('studioVideoPlayer');
      player.style.display = 'block';
      player.src = '/video?path=' + encodeURIComponent(filePath);

      document.getElementById('monitorHudTop').style.display = 'flex';
      document.getElementById('monitorPlayOverlay').style.display = 'flex';
      document.getElementById('monitorTransportBar').style.display = 'flex';

      // Setup Timecode & Playhead updates
      activeShotIndex = -1;
      isFreezeHolding = false;
      player.ontimeupdate = updatePlayerTimecode;
      player.onplay = () => {
        document.getElementById('transportPlayIcon').className = 'fa-solid fa-pause';
        document.getElementById('monitorPlayIcon').className = 'fa-solid fa-pause';
        applyLiveFilters();
        const ov = document.getElementById('liveOverlayPlayer');
        if (ov && selectedOverlayEffect !== 'none') {
          ov.play().catch(() => {});
        }
        startPlaybackLoop();
      };
      player.onpause = () => {
        document.getElementById('transportPlayIcon').className = 'fa-solid fa-play';
        document.getElementById('monitorPlayIcon').className = 'fa-solid fa-play';
        const ov = document.getElementById('liveOverlayPlayer');
        if (ov) ov.pause();
        stopPlaybackLoop();
      };
      player.onseeking = () => {
        const ov = document.getElementById('liveOverlayPlayer');
        if (ov && ov.duration) {
          ov.currentTime = player.currentTime % ov.duration;
        }
      };
      player.onended = () => {
        player.currentTime = 0;
        activeShotIndex = -1;
        isFreezeHolding = false;
        player.play().catch(() => {});
      };
      applyLiveFilters();

      // Automatically analyze & generate timeline cuts
      analyzeFootage(filePath);
    }

    function toggleVideoPlay() {
      const player = document.getElementById('studioVideoPlayer');
      if (player.paused) {
        player.play().catch(() => {});
      } else {
        player.pause();
      }
    }

    function stepVideo(deltaSec) {
      const player = document.getElementById('studioVideoPlayer');
      activeShotIndex = -1;
      isFreezeHolding = false;
      player.currentTime = Math.max(0, player.currentTime + deltaSec);
      syncRealtimePlayback(player.currentTime);
    }

    function syncRealtimePlayback(cur) {
      const player = document.getElementById('studioVideoPlayer');
      if (!player) return;
      const dur = player.duration || currentTotalDur || 1;

      document.getElementById('hudTimecode').innerText = `${formatTime(cur)} / ${formatTime(dur)}`;

      const camTc = document.getElementById('liveCamcorderTc');
      if (camTc) {
        const m = Math.floor(cur / 60);
        const s = Math.floor(cur % 60);
        const f = Math.floor((cur % 1) * 30);
        camTc.innerText = `TC 00:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}:${f.toString().padStart(2, '0')}`;
      }

      // Update Playhead position
      const pct = Math.min((cur / dur) * 100, 100);
      const playhead = document.getElementById('timelinePlayhead');
      if (playhead) {
        playhead.style.left = pct + '%';
      }

      if (!liveDirectorEnabled || !currentShots || currentShots.length === 0) {
        return;
      }
      if (isFreezeHolding) return;

      // Reset freeze trigger flags if restarted
      if (cur < 0.2) {
        currentShots.forEach(s => s._freezeTriggered = false);
      }

      // Check if active shot finished
      if (activeShotIndex >= 0 && activeShotIndex < currentShots.length) {
        const active = currentShots[activeShotIndex];
        if (cur >= active.end) {
          if (active.is_freeze && !active._freezeTriggered) {
            active._freezeTriggered = true;
            holdFreezeFrame(active);
            return;
          }
          if (activeShotIndex + 1 < currentShots.length) {
            const next = currentShots[activeShotIndex + 1];
            if (next.start > cur) {
              triggerCutTransition();
              player.currentTime = next.start;
              return;
            }
          }
        }
      }

      // Check matching shot
      let matchingIdx = -1;
      for (let i = 0; i < currentShots.length; i++) {
        const s = currentShots[i];
        if (cur >= s.start - 0.05 && cur <= s.end + 0.05) {
          matchingIdx = i;
          break;
        }
      }

      if (matchingIdx === -1 && !player.paused) {
        // In silence dead air: jump forward to next shot!
        const next = currentShots.find(s => s.start > cur);
        if (next) {
          triggerCutTransition();
          player.currentTime = next.start;
          return;
        }
      } else if (matchingIdx !== -1 && matchingIdx !== activeShotIndex) {
        activeShotIndex = matchingIdx;
        const shot = currentShots[matchingIdx];
        applyShotFraming(shot);
        triggerCutTransition();

        const hudAngle = document.getElementById('hudAngleName');
        if (hudAngle) {
          hudAngle.innerText = `CAM ${matchingIdx + 1} // ${(shot.angle || 'WIDE').replace('_', ' ')}`;
        }

        document.querySelectorAll('.shot-block-nle').forEach((el, idx) => {
          if (idx === matchingIdx) el.classList.add('active');
          else el.classList.remove('active');
        });
      }
    }

    function updatePlayerTimecode() {
      const player = document.getElementById('studioVideoPlayer');
      if (player) {
        syncRealtimePlayback(player.currentTime || 0);
      }
    }

    function handleTimelineClick(e) {
      const viewport = document.getElementById('timelineViewport');
      const rect = viewport.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const pct = Math.max(0, Math.min(clickX / rect.width, 1));

      const player = document.getElementById('studioVideoPlayer');
      const dur = player.duration || currentTotalDur;
      if (dur > 0) {
        activeShotIndex = -1;
        isFreezeHolding = false;
        player.currentTime = pct * dur;
        syncRealtimePlayback(player.currentTime);
      }
    }

    // ------------------------------------------------------------------------
    // ANALYSIS & TIMELINE GENERATION
    // ------------------------------------------------------------------------
    async function analyzeFootage(customPath) {
      const inputPath = customPath || document.getElementById('inputVideo').value.trim();
      if (!inputPath) return;

      const track = document.getElementById('cutsTrackRow');
      track.innerHTML = '<div style="color: var(--accent-neon); font-size: 0.75rem; padding-left: 0.5rem;"><i class="fa-solid fa-spinner fa-spin"></i> Analyzing acoustics &amp; framing virtual angles...</div>';

      try {
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            input_path: inputPath,
            pacing: document.getElementById('pacingSelect').value,
            remove_fillers: document.getElementById('removeFillersToggle').checked,
            target_person: document.getElementById('targetPersonSelect') ? document.getElementById('targetPersonSelect').value : 'primary',
            broll_dir: document.getElementById('brollFolderInput').value.trim() || null
          })
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        renderTimeline(data);
      } catch (err) {
        track.innerHTML = '<div style="color: #EF4444; font-size: 0.75rem; padding-left: 0.5rem;"><i class="fa-solid fa-triangle-exclamation"></i> ' + escapeHtml(err.message) + '</div>';
      }
    }

    function reAnalyzeFootage() {
      analyzeFootage();
    }

    function renderTimeline(data) {
      currentShots = data.shots || [];
      currentTotalDur = data.edited_duration || data.total_duration || 1.0;

      // Update Topbar Stats
      document.getElementById('statCutDuration').innerText = formatTime(currentTotalDur);
      document.getElementById('statDeadAirPct').innerText = '-' + (data.saved_pct || 0).toFixed(0) + '%';
      document.getElementById('statCutsCount').innerText = currentShots.length;
      document.getElementById('statDurationChip').style.display = 'flex';
      document.getElementById('statDeadAirChip').style.display = 'flex';
      document.getElementById('statCutsChip').style.display = 'flex';

      // Render Time Ticks
      const ticks = document.getElementById('timeTicksContainer');
      ticks.innerHTML = '';
      const totalSec = Math.ceil(currentTotalDur);
      const step = totalSec > 30 ? 5 : (totalSec > 15 ? 2 : 1);
      for (let s = 0; s <= totalSec; s += step) {
        const tick = document.createElement('div');
        tick.className = 'time-tick';
        tick.innerText = formatTime(s);
        ticks.appendChild(tick);
      }

      // Render Cut Blocks
      const track = document.getElementById('cutsTrackRow');
      track.innerHTML = '';

      currentShots.forEach((shot, idx) => {
        const dur = shot.duration;
        const pct = Math.max((dur / currentTotalDur) * 100, 1.2);

        const block = document.createElement('div');
        const angleClass = 'angle-' + (shot.angle || 'wide').toLowerCase();
        block.className = `shot-block-nle ${angleClass}`;
        block.style.width = pct + '%';
        block.title = `Shot #${idx+1}: ${(shot.angle||'wide').toUpperCase()} (${dur.toFixed(1)}s)`;

        const tag = document.createElement('div');
        tag.className = 'shot-tag-name';
        tag.innerHTML = `<i class="fa-solid fa-camera"></i> ${shot.angle || 'WIDE'}`;

        const durTag = document.createElement('div');
        durTag.className = 'shot-tag-dur';
        durTag.innerText = dur.toFixed(1) + 's';

        block.appendChild(tag);
        block.appendChild(durTag);

        block.onclick = (e) => {
          e.stopPropagation();
          const player = document.getElementById('studioVideoPlayer');
          activeShotIndex = -1;
          isFreezeHolding = false;
          player.currentTime = shot.start;
          syncRealtimePlayback(shot.start);
          player.play().catch(() => {});
        };

        track.appendChild(block);
      });
    }

    function formatTime(sec) {
      sec = Math.max(0, sec);
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    // ------------------------------------------------------------------------
    // DEVICE FILE NAVIGATOR MODAL
    // ------------------------------------------------------------------------
    let browserCurrentDir = '';
    let browserParentDir = null;
    let browserAllEntries = [];

    function openFileBrowser(dir) {
      document.getElementById('deviceBrowserModal').style.display = 'flex';
      loadBrowserDir(dir || 'default');
    }

    function closeFileBrowser() {
      document.getElementById('deviceBrowserModal').style.display = 'none';
    }

    function navigateBrowserUp() {
      if (browserParentDir) loadBrowserDir(browserParentDir);
    }

    async function loadBrowserDir(dir) {
      const listContainer = document.getElementById('browserListContainer');
      const breadcrumbs = document.getElementById('browserBreadcrumbs');
      const rootsBar = document.getElementById('browserRootsBar');
      const statusText = document.getElementById('browserStatusText');
      const upBtn = document.getElementById('browserUpBtn');
      const searchInput = document.getElementById('browserSearchInput');
      if (searchInput) searchInput.value = '';

      listContainer.innerHTML = '<div style="padding: 2.5rem; text-align: center; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Reading storage...</div>';

      try {
        const res = await fetch('/api/browse?dir=' + encodeURIComponent(dir || 'default'));
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        browserCurrentDir = data.current_dir;
        browserParentDir = data.parent_dir;
        browserAllEntries = data.entries || [];

        upBtn.disabled = !browserParentDir;
        upBtn.style.opacity = browserParentDir ? '1' : '0.4';

        // Render Quick Roots
        rootsBar.innerHTML = '';
        (data.quick_roots || []).forEach(r => {
          const chip = document.createElement('span');
          chip.className = 'browser-root-chip';
          chip.innerHTML = `<i class="fa-solid ${r.icon}"></i> ${escapeHtml(r.label)}`;
          chip.onclick = () => loadBrowserDir(r.path);
          rootsBar.appendChild(chip);
        });

        // Render Breadcrumbs
        breadcrumbs.innerHTML = '';
        (data.breadcrumbs || []).forEach((b, i) => {
          if (i > 0) {
            const sep = document.createElement('span');
            sep.className = 'crumb-sep';
            sep.innerText = '/';
            breadcrumbs.appendChild(sep);
          }
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'crumb-btn';
          btn.innerText = b.name;
          btn.onclick = () => loadBrowserDir(b.path);
          breadcrumbs.appendChild(btn);
        });

        renderBrowserList(browserAllEntries);
      } catch (err) {
        listContainer.innerHTML = '<div style="padding: 2.5rem; text-align: center; color: #EF4444;"><i class="fa-solid fa-triangle-exclamation"></i> ' + escapeHtml(err.message) + '</div>';
        statusText.innerText = 'Error reading directory';
      }
    }

    function renderBrowserList(entries) {
      const listContainer = document.getElementById('browserListContainer');
      const statusText = document.getElementById('browserStatusText');
      listContainer.innerHTML = '';

      if (!entries || entries.length === 0) {
        listContainer.innerHTML = '<div style="padding: 2.5rem; text-align: center; color: var(--text-muted);">No files in this folder.</div>';
        statusText.innerText = '0 items found';
        return;
      }

      let vidCount = 0;
      let dirCount = 0;

      entries.forEach(item => {
        if (item.is_video) vidCount++;
        if (item.is_dir) dirCount++;

        const div = document.createElement('div');
        div.className = 'browser-item';

        const left = document.createElement('div');
        left.className = 'browser-item-left';

        const iconBox = document.createElement('div');
        iconBox.className = 'browser-item-icon ' + (item.is_dir ? 'icon-folder' : (item.is_video ? 'icon-video' : 'icon-file'));
        iconBox.innerHTML = '<i class="fa-solid ' + (item.is_dir ? 'fa-folder' : (item.is_video ? 'fa-video' : 'fa-file')) + '"></i>';

        const nameSpan = document.createElement('div');
        nameSpan.className = 'browser-item-name';
        nameSpan.innerText = item.name;

        left.appendChild(iconBox);
        left.appendChild(nameSpan);

        const meta = document.createElement('div');
        if (item.is_video) {
          const badge = document.createElement('span');
          badge.className = 'badge-video';
          badge.innerText = item.size || 'VIDEO';
          meta.appendChild(badge);
        }

        div.appendChild(left);
        div.appendChild(meta);

        if (item.is_dir) div.onclick = () => loadBrowserDir(item.path);
        else if (item.is_video) div.onclick = () => selectBrowserFile(item.path);

        listContainer.appendChild(div);
      });

      statusText.innerText = `${vidCount} video(s), ${dirCount} folder(s)`;
    }

    function filterBrowserList(query) {
      if (!query || !query.trim()) {
        renderBrowserList(browserAllEntries);
        return;
      }
      const q = query.toLowerCase().trim();
      renderBrowserList(browserAllEntries.filter(e => e.name.toLowerCase().includes(q)));
    }

    function selectBrowserFile(filePath) {
      closeFileBrowser();
      if (window.browserPickerTarget === 'master_song') {
        const inp = document.getElementById('masterSongInput');
        if (inp) inp.value = filePath;
        window.browserPickerTarget = null;
        analyzeMusicGrid();
      } else if (window.browserPickerTarget === 'take_video') {
        addCameraTake(filePath);
        window.browserPickerTarget = null;
      } else {
        selectVideoSource(filePath);
      }
    }

    // ------------------------------------------------------------------------
    // MUSIC VIDEO STUDIO ENGINE
    // ------------------------------------------------------------------------
    window.musicTakesList = [];

    function toggleMusicMode(enabled) {
      const modeBadge = document.getElementById('statModeBadge');
      if (modeBadge) {
        modeBadge.innerText = enabled ? '🎵 MUSIC VIDEO' : '🎙️ SPEECH';
        modeBadge.style.color = enabled ? '#06B6D4' : '#10B981';
      }
      if (enabled && document.getElementById('masterSongInput').value.trim()) {
        analyzeMusicGrid();
      }
    }

    function browseMasterSong() {
      window.browserPickerTarget = 'master_song';
      openFileBrowser();
    }

    function addCameraTake(manualPath) {
      const pathVal = manualPath || (document.getElementById('addTakeInput') ? document.getElementById('addTakeInput').value.trim() : '');
      if (!pathVal) {
        window.browserPickerTarget = 'take_video';
        openFileBrowser();
        return;
      }
      if (!window.musicTakesList.includes(pathVal)) {
        window.musicTakesList.push(pathVal);
      }
      if (document.getElementById('addTakeInput')) {
        document.getElementById('addTakeInput').value = '';
      }
      renderTakesListUI();
      autoSyncTakes();
    }

    function removeCameraTake(idx) {
      window.musicTakesList.splice(idx, 1);
      renderTakesListUI();
    }

    function renderTakesListUI(syncResults) {
      const container = document.getElementById('takesSyncList');
      if (!container) return;
      const currentVid = document.getElementById('inputVideo').value.trim();
      const allTakes = [];
      if (currentVid) allTakes.push({ path: currentVid, is_primary: true });
      window.musicTakesList.forEach((p, i) => {
        if (p !== currentVid) allTakes.push({ path: p, is_primary: false, index: i });
      });

      if (allTakes.length === 0) {
        container.innerHTML = '<div style="font-size: 0.75rem; color: var(--text-muted); text-align: center; padding: 0.5rem;">Load video footage and a master song, then click Auto-Sync.</div>';
        return;
      }

      const syncMap = {};
      if (syncResults && Array.isArray(syncResults)) {
        syncResults.forEach(r => { syncMap[r.take_path] = r; });
      }

      container.innerHTML = allTakes.map((tk, idx) => {
        const fn = tk.path.split('/').pop();
        const sync = syncMap[tk.path];
        const offsetStr = sync ? (sync.offset_seconds >= 0 ? '+' : '') + sync.offset_seconds.toFixed(3) + 's' : 'Not Synced';
        const confStr = sync ? Math.round(sync.confidence * 100) + '%' : '--';
        const isLocked = sync ? sync.is_locked : false;
        const statusBadge = isLocked 
          ? '<span style="background: rgba(16,185,129,0.2); color: #10B981; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-size: 0.65rem;">LOCKED ✓</span>'
          : '<span style="background: rgba(244,63,94,0.2); color: #F43F5E; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-size: 0.65rem;">PENDING</span>';

        return `
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 0.75rem;">
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 48%;">
              <span style="color: ${tk.is_primary ? '#06B6D4' : '#E2E8F0'}; font-weight: 600;">Take ${idx + 1}:</span>
              <span title="${escapeHtml(tk.path)}">${escapeHtml(fn)}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <span style="font-family: monospace; color: #A78BFA; font-size: 0.7rem;">${offsetStr} (${confStr})</span>
              ${statusBadge}
              ${!tk.is_primary ? `<button type="button" onclick="removeCameraTake(${tk.index})" style="background: transparent; border: none; color: #EF4444; cursor: pointer; padding: 0 4px;"><i class="fa-solid fa-times"></i></button>` : ''}
            </div>
          </div>
        `;
      }).join('');
    }

    async function autoSyncTakes() {
      const songPath = document.getElementById('masterSongInput').value.trim();
      const currentVid = document.getElementById('inputVideo').value.trim();
      const allTakes = [];
      if (currentVid) allTakes.push(currentVid);
      window.musicTakesList.forEach(t => { if (!allTakes.includes(t)) allTakes.push(t); });

      if (!songPath) {
        alert('Please pick or enter a Master Song Audio file (song.wav / song.mp3) first.');
        return;
      }
      if (allTakes.length === 0) {
        alert('Please select at least one camera take video.');
        return;
      }

      const syncBtn = document.getElementById('btnSyncTakes');
      const origHtml = syncBtn ? syncBtn.innerHTML : '';
      if (syncBtn) {
        syncBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Syncing (FFT)...';
        syncBtn.disabled = true;
      }

      try {
        const res = await fetch('/api/music/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ song_path: songPath, take_paths: allTakes })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        renderTakesListUI(data.takes);
      } catch (err) {
        alert('Auto-Sync failed: ' + err.message);
      } finally {
        if (syncBtn) {
          syncBtn.innerHTML = origHtml;
          syncBtn.disabled = false;
        }
      }
    }

    async function analyzeMusicGrid() {
      const songPath = document.getElementById('masterSongInput').value.trim();
      if (!songPath) {
        alert('Please select or specify a master song audio file first.');
        return;
      }

      const currentVid = document.getElementById('inputVideo').value.trim();
      const allTakes = [];
      if (currentVid) allTakes.push(currentVid);
      window.musicTakesList.forEach(t => { if (!allTakes.includes(t)) allTakes.push(t); });

      const manualBpm = parseFloat(document.getElementById('musicBpmInput').value) || 0.0;

      try {
        const res = await fetch('/api/music/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            song_path: songPath,
            take_paths: allTakes,
            bpm: manualBpm,
            drop_punchins: document.getElementById('musicDropPunchToggle') ? document.getElementById('musicDropPunchToggle').checked : true,
            speed_ramps: document.getElementById('musicSpeedRampToggle') ? document.getElementById('musicSpeedRampToggle').checked : true,
            beat_fx: document.getElementById('musicBeatFxToggle') ? document.getElementById('musicBeatFxToggle').checked : true,
          })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        const a = data.analysis;
        document.getElementById('musicBpmInput').value = a.bpm.toFixed(1);
        document.getElementById('musicTotalBars').innerText = a.total_bars;
        document.getElementById('musicKickDrops').innerText = a.kick_onsets ? a.kick_onsets.length : '0';

        const secRow = document.getElementById('musicSectionsRow');
        if (secRow && a.sections) {
          secRow.innerHTML = a.sections.map(s => {
            const colors = {
              intro: '#6B7280',
              verse: '#3B82F6',
              pre_chorus: '#F59E0B',
              chorus: '#EF4444',
              drop: '#EC4899',
              outro: '#6B7280'
            };
            const col = colors[s.name] || '#06B6D4';
            return `<span class="cat-pill" style="border-color: ${col}; color: ${col}; font-size: 0.68rem; font-weight: 700;">${s.name.toUpperCase()} (${s.cadence_bars}b)</span>`;
          }).join('');
        }

        if (data.takes) {
          renderTakesListUI(data.takes);
        }

        if (data.shots && data.shots.length > 0) {
          renderTimeline({
            shots: data.shots,
            total_duration: a.total_duration,
            edited_duration: a.total_duration,
            saved_pct: 0
          });
        }
      } catch (err) {
        alert('Music Analysis Error: ' + err.message);
      }
    }

    // ------------------------------------------------------------------------
    // EXPORT & RENDER MODAL
    // ------------------------------------------------------------------------
    function openExportModal() {
      const inputPath = document.getElementById('inputVideo').value.trim();
      if (!inputPath) {
        alert('Please select or load a source video first.');
        return;
      }

      document.getElementById('exportProgressModal').style.display = 'flex';
      document.getElementById('exportActiveState').style.display = 'block';
      document.getElementById('exportCompleteState').style.display = 'none';

      startRenderExecution();
    }

    function closeExportModal() {
      document.getElementById('exportProgressModal').style.display = 'none';
    }

    async function startRenderExecution() {
      const inputPath = document.getElementById('inputVideo').value.trim();
      const resVal = document.getElementById('targetResolutionSelect').value;

      let targetW = 1920;
      let targetH = 1080;
      if (resVal === '720p') { targetW = 1280; targetH = 720; }
      else if (resVal === '4k') { targetW = 3840; targetH = 2160; }

      const payload = {
        input_path: inputPath,
        output_path: null,
        target_width: targetW,
        target_height: targetH,
        aspect_ratio: currentAspectRatio,
        resolution: resVal,
        color_grade: document.getElementById('colorGradeSelect').value,
        bgm_path: document.getElementById('bgmTrackSelect').value === 'ambient' ? 'ambient' : null,
        bgm_volume: parseFloat(document.getElementById('bgmVolSlider').value) / 100.0,
        enable_captions: document.getElementById('captionsToggle').checked,
        caption_color: document.getElementById('captionColorSelect').value,
        stabilize: document.getElementById('stabilizeToggle').checked,
        stabilize_smoothing: parseInt(document.getElementById('stabilizeSmoothingSlider').value),
        remove_fillers: document.getElementById('removeFillersToggle').checked,
        broll_dir: document.getElementById('brollFolderInput').value.trim() || null,
        transition_style: document.getElementById('transitionSelect') ? document.getElementById('transitionSelect').value : 'flash',
        enable_sfx: document.getElementById('transitionSfxToggle') ? document.getElementById('transitionSfxToggle').checked : true,
        sfx_volume: document.getElementById('sfxVolSlider') ? parseFloat(document.getElementById('sfxVolSlider').value) / 100.0 : 0.35,
        enable_freeze_frames: document.getElementById('freezeFrameToggle') ? document.getElementById('freezeFrameToggle').checked : true,
        freeze_duration: document.getElementById('freezeDurSlider') ? parseFloat(document.getElementById('freezeDurSlider').value) : 0.6,
        letterbox: document.getElementById('letterboxToggle') ? document.getElementById('letterboxToggle').checked : false,
        film_grain: document.getElementById('filmGrainToggle') ? document.getElementById('filmGrainToggle').checked : false,
        fx_glow: document.getElementById('fxGlowSelect') ? document.getElementById('fxGlowSelect').value : 'none',
        fx_rgb_split: document.getElementById('fxRgbSelect') ? document.getElementById('fxRgbSelect').value : 'none',
        fx_camera_motion: document.getElementById('fxMotionSelect') ? document.getElementById('fxMotionSelect').value : 'none',
        fx_camcorder_osd: document.getElementById('fxCamcorderToggle') ? document.getElementById('fxCamcorderToggle').checked : false,
        fx_tilt_shift: document.getElementById('fxTiltShiftToggle') ? document.getElementById('fxTiltShiftToggle').checked : false,
        fx_flicker: document.getElementById('fxFlickerToggle') ? document.getElementById('fxFlickerToggle').checked : false,
        overlay_effect: selectedOverlayEffect !== 'none' ? selectedOverlayEffect : null,
        overlay_blend_mode: document.getElementById('overlayBlendModeSelect') ? document.getElementById('overlayBlendModeSelect').value : 'screen',
        overlay_opacity: document.getElementById('overlayOpacitySlider') ? parseFloat(document.getElementById('overlayOpacitySlider').value) / 100.0 : 0.85,
        overlay_target: document.getElementById('overlayTargetSelect') ? document.getElementById('overlayTargetSelect').value : 'fullscreen',
        target_person: document.getElementById('targetPersonSelect') ? document.getElementById('targetPersonSelect').value : 'primary',
        selective_color: document.getElementById('selectiveColorSelect') ? document.getElementById('selectiveColorSelect').value : 'none',
        vignette: document.getElementById('vignetteToggle') ? document.getElementById('vignetteToggle').checked : true,
        show_hud: document.getElementById('hudToggle') ? document.getElementById('hudToggle').checked : true,
        show_title: document.getElementById('showTitleToggle') ? document.getElementById('showTitleToggle').checked : true,
        title_text: document.getElementById('titleTextInput') ? document.getElementById('titleTextInput').value.trim() : 'OMNICAM AI • MULTI-CAM PRODUCTION',
        subtitle_text: document.getElementById('subtitleTextInput') ? document.getElementById('subtitleTextInput').value.trim() : 'PRO VIRTUAL STUDIO // 4K CLARITY',
        custom_watermark: (document.getElementById('customWatermarkInput') && document.getElementById('customWatermarkInput').value.trim()) || null,
        music_mode: document.getElementById('musicModeToggle') ? document.getElementById('musicModeToggle').checked : false,
        song_path: document.getElementById('masterSongInput') ? document.getElementById('masterSongInput').value.trim() : null,
        take_paths: window.musicTakesList || [],
        bpm: parseFloat(document.getElementById('musicBpmInput') ? document.getElementById('musicBpmInput').value : '120') || 120,
        bass_pump: document.getElementById('musicBassPumpToggle') ? document.getElementById('musicBassPumpToggle').checked : false,
        speed_ramps: document.getElementById('musicSpeedRampToggle') ? document.getElementById('musicSpeedRampToggle').checked : false,
        beat_fx: document.getElementById('musicBeatFxToggle') ? document.getElementById('musicBeatFxToggle').checked : false,
        drop_punchins: document.getElementById('musicDropPunchToggle') ? document.getElementById('musicDropPunchToggle').checked : true
      };

      try {
        const res = await fetch('/api/render', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        pollRenderProgress();
      } catch (err) {
        alert('Render failed to start: ' + err.message);
        closeExportModal();
      }
    }

    function pollRenderProgress() {
      const timer = setInterval(async () => {
        try {
          const res = await fetch('/api/progress');
          const data = await res.json();

          const pct = Math.round(data.progress * 100);
          document.getElementById('exportProgressBar').style.width = pct + '%';
          document.getElementById('exportProgressPct').innerText = pct + '%';
          document.getElementById('exportStatusMsg').innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${data.status || 'Rendering multi-cam cuts...'}`;

          if (!data.is_rendering) {
            clearInterval(timer);
            if (data.error) {
              alert('Render encountered an error: ' + data.error);
              closeExportModal();
            } else if (data.output_file) {
              renderedOutputPath = data.output_file;
              document.getElementById('exportActiveState').style.display = 'none';
              document.getElementById('exportCompleteState').style.display = 'block';

              const fileName = data.output_file.split('/').pop();
              const vidUrl = '/video?path=' + encodeURIComponent(data.output_file);

              // 1. Programmatically trigger browser download to save directly to phone storage
              const autoDl = document.createElement('a');
              autoDl.href = vidUrl;
              autoDl.download = fileName;
              document.body.appendChild(autoDl);
              autoDl.click();
              document.body.removeChild(autoDl);

              // 2. Set up download button and embedded preview player in modal
              const dl = document.getElementById('downloadVideoLink');
              if (dl) {
                dl.href = vidUrl;
                dl.download = fileName;
              }
              const compPlayer = document.getElementById('exportCompletePlayer');
              if (compPlayer) {
                compPlayer.src = vidUrl;
                compPlayer.load();
                compPlayer.play().catch(() => {});
              }
              const badge = document.getElementById('exportSavedPathBadge');
              if (badge) {
                if (data.saved_device_path) {
                  badge.innerText = 'Saved to Gallery / Storage: ' + data.saved_device_path;
                } else {
                  badge.innerText = 'Saved automatically to Device Downloads (' + fileName + ')';
                }
              }
            }
          }
        } catch (e) {}
      }, 1000);
    }

    function playRenderedInMonitor() {
      if (!renderedOutputPath) return;
      closeExportModal();
      selectVideoSource(renderedOutputPath, 'Master_Cut.mp4');
    }

    // Auto-load 54+ studio overlay presets catalog
    window.addEventListener('DOMContentLoaded', loadOverlaysCatalog);
    setTimeout(loadOverlaysCatalog, 500);
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

        if path == "/api/browse":
            qs = urllib.parse.parse_qs(parsed.query)
            target_dir = qs.get("dir", [None])[0]
            if not target_dir or target_dir == "~":
                target_dir = os.path.expanduser("~")
            elif target_dir in ("default", ""):
                if os.path.isdir("/sdcard/DCIM/Camera"):
                    target_dir = "/sdcard/DCIM/Camera"
                elif os.path.isdir("/sdcard"):
                    target_dir = "/sdcard"
                else:
                    target_dir = os.getcwd()

            target_dir = os.path.abspath(os.path.expanduser(target_dir))
            if not os.path.isdir(target_dir):
                self.send_json({"error": f"Folder not found: {target_dir}"}, status=404)
                return

            try:
                parent_dir = os.path.dirname(target_dir) if target_dir != "/" else None

                # Compute breadcrumbs
                parts = []
                curr = target_dir
                while curr and curr != "/":
                    parts.append({"name": os.path.basename(curr) or curr, "path": curr})
                    curr = os.path.dirname(curr)
                parts.append({"name": "root (/)", "path": "/"})
                parts.reverse()

                entries = []
                with os.scandir(target_dir) as it:
                    for entry in it:
                        if entry.name.startswith("."):
                            continue
                        try:
                            is_dir = entry.is_dir(follow_symlinks=False)
                            is_file = entry.is_file(follow_symlinks=False)
                            lower = entry.name.lower()
                            is_video = is_file and lower.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".3gp", ".m4v"))
                            is_audio = is_file and lower.endswith((".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"))

                            size_str = ""
                            if is_file:
                                sz = entry.stat().st_size
                                if sz >= 1024 * 1024 * 1024:
                                    size_str = f"{sz / (1024**3):.2f} GB"
                                elif sz >= 1024 * 1024:
                                    size_str = f"{sz / (1024**2):.1f} MB"
                                elif sz >= 1024:
                                    size_str = f"{sz / 1024:.0f} KB"
                                else:
                                    size_str = f"{sz} B"

                            entries.append({
                                "name": entry.name,
                                "path": entry.path,
                                "is_dir": is_dir,
                                "is_video": is_video,
                                "is_audio": is_audio,
                                "size": size_str,
                            })
                        except (PermissionError, OSError):
                            continue

                entries.sort(key=lambda x: (not x["is_dir"], not (x["is_video"] or x["is_audio"]), x["name"].lower()))

                # Quick device root shortcuts
                roots = []
                for label, icon, rpath in [
                    ("Camera", "fa-camera", "/sdcard/DCIM/Camera"),
                    ("Movies", "fa-film", "/sdcard/Movies"),
                    ("Downloads", "fa-download", "/sdcard/Download"),
                    ("Storage", "fa-hard-drive", "/sdcard"),
                    ("Termux Home", "fa-house", os.path.expanduser("~")),
                    ("Workspace", "fa-briefcase", os.getcwd()),
                ]:
                    if os.path.isdir(rpath):
                        roots.append({"label": label, "icon": icon, "path": rpath})

                self.send_json({
                    "current_dir": target_dir,
                    "parent_dir": parent_dir,
                    "breadcrumbs": parts,
                    "quick_roots": roots,
                    "entries": entries,
                })
            except PermissionError:
                self.send_json({"error": f"Permission denied to access {target_dir}"}, status=403)
            except Exception as e:
                self.send_json({"error": str(e)}, status=500)
            return

        if path == "/api/find_local":
            qs = urllib.parse.parse_qs(parsed.query)
            filename = qs.get("name", [None])[0]
            size_str = qs.get("size", [None])[0]
            if not filename:
                self.send_json({"found": False})
                return

            clean_name = os.path.basename(urllib.parse.unquote(filename))
            target_size = int(size_str) if size_str and size_str.isdigit() else None

            candidate_dirs = [
                "/sdcard/DCIM/Camera",
                "/sdcard/Movies",
                "/sdcard/Download",
                os.path.expanduser("~/storage/dcim/Camera"),
                os.path.expanduser("~/storage/movies"),
                os.path.abspath("uploads"),
                os.getcwd(),
            ]
            for d in candidate_dirs:
                if os.path.isdir(d):
                    full = os.path.join(d, clean_name)
                    if os.path.isfile(full):
                        try:
                            if target_size is None or os.path.getsize(full) == target_size:
                                self.send_json({"found": True, "path": full})
                                return
                        except OSError:
                            pass

            self.send_json({"found": False})
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
                    "saved_device_path": STATE.saved_device_path,
                    "error": STATE.error,
                }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        if path == "/api/overlays":
            engine = OverlayEngine()
            overlays = engine.list_available_overlays()
            self.send_json({"overlays": overlays})
            return

        if path.startswith("/assets/overlays/"):
            fname = path[len("/assets/overlays/"):]
            safe_fname = os.path.basename(fname)
            full_p = os.path.join("assets", "overlays", safe_fname)
            if not os.path.isfile(full_p):
                # Auto-synthesize on-the-fly if it's a known preset
                engine = OverlayEngine()
                target_id = os.path.splitext(safe_fname)[0]
                preset = engine.get_preset_by_id(target_id)
                if preset:
                    engine.generate_preset(preset, full_p)

            if os.path.isfile(full_p):
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(os.path.getsize(full_p)))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    with open(full_p, "rb") as f:
                        while chunk := f.read(65536):
                            self.wfile.write(chunk)
                except Exception:
                    pass
                return
            else:
                self.send_error(404, "Overlay asset not found")
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

        if path == "/api/upload":
            raw_fn = self.headers.get("X-Filename", "device_video.mp4")
            filename = urllib.parse.unquote(raw_fn)
            filename = os.path.basename(filename)
            if not filename or filename in (".", ".."):
                filename = f"video_{int(time.time())}.mp4"
            upload_dir = os.path.abspath("uploads")
            os.makedirs(upload_dir, exist_ok=True)
            dest_path = os.path.join(upload_dir, filename)

            content_len = int(self.headers.get("Content-Length", 0))
            bytes_read = 0
            with open(dest_path, "wb") as f:
                while bytes_read < content_len:
                    chunk = self.rfile.read(min(65536, content_len - bytes_read))
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_read += len(chunk)

            self.send_json({"status": "uploaded", "path": dest_path})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
        try:
            params = json.loads(body) if body else {}
        except Exception:
            params = {}

        if path == "/api/music/sync":
            song_path = params.get("song_path")
            take_paths = params.get("take_paths", [])
            if not song_path or not os.path.isfile(song_path):
                self.send_json({"error": f"Master song not found: {song_path}"}, status=400)
                return
            valid_takes = [t for t in take_paths if t and os.path.isfile(t)]
            if not valid_takes:
                self.send_json({"error": "No valid take files provided."}, status=400)
                return
            try:
                sync_engine = MultiTakeSyncEngine()
                results = sync_engine.align_multiple_takes(song_path, valid_takes)
                self.send_json({"status": "ok", "takes": [t.to_dict() for t in results]})
            except Exception as ex:
                self.send_json({"error": str(ex)}, status=500)
            return

        if path == "/api/music/analyze":
            song_path = params.get("song_path")
            if not song_path or not os.path.isfile(song_path):
                self.send_json({"error": f"Master song not found: {song_path}"}, status=400)
                return
            manual_bpm = float(params.get("bpm", 0.0)) or None
            take_paths = params.get("take_paths", [])
            valid_takes = [t for t in take_paths if t and os.path.isfile(t)]
            try:
                music_analyzer = MusicBeatAnalyzer()
                analysis = music_analyzer.analyze(song_path, manual_bpm=manual_bpm)

                takes_info = []
                if valid_takes:
                    sync_engine = MultiTakeSyncEngine()
                    takes_info = sync_engine.align_multiple_takes(song_path, valid_takes)

                director = MusicVideoDirector(
                    analysis=analysis,
                    takes=takes_info,
                    tracker=None,
                    target_resolution=params.get("resolution", "720p"),
                    enable_drop_punchins=bool(params.get("drop_punchins", True)),
                    enable_speed_ramps=bool(params.get("speed_ramps", True)),
                    enable_beat_fx=bool(params.get("beat_fx", True)),
                )
                shot_plans = director.plan_music_video()
                shots_data = [
                    {
                        "index": sp.index,
                        "angle": sp.angle.value,
                        "start": sp.segment.start,
                        "end": sp.segment.end,
                        "duration": sp.segment.duration,
                        "description": sp.description,
                        "clip_index": sp.clip_index,
                        "transition": getattr(sp, "transition", "flash"),
                        "speed_ramp": getattr(sp, "speed_ramp", "none"),
                        "beat_effect": getattr(sp, "beat_effect", None),
                    }
                    for sp in shot_plans
                ]
                self.send_json({
                    "status": "ok",
                    "analysis": analysis.to_dict(),
                    "takes": [t.to_dict() for t in takes_info],
                    "shots": shots_data,
                })
            except Exception as ex:
                self.send_json({"error": str(ex)}, status=500)
            return

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
                    target_person=params.get("target_person", "primary"),
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
                        "is_freeze": getattr(sp, "is_freeze_frame", False),
                        "freeze_duration": getattr(sp, "freeze_duration", 0.0),
                        "transition": getattr(sp, "transition", "flash"),
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
                    is_music_mode = bool(params.get("music_mode", False))
                    song_path = params.get("song_path")

                    target_person = params.get("target_person", "primary")
                    selective_color = params.get("selective_color", "none")
                    broll_dir = params.get("broll_dir")

                    if is_music_mode and song_path and os.path.isfile(song_path):
                        take_paths = params.get("take_paths", [])
                        valid_takes = [t for t in take_paths if t and os.path.isfile(t)]
                        if input_path not in valid_takes:
                            valid_takes.insert(0, input_path)

                        sync_engine = MultiTakeSyncEngine()
                        takes_info = sync_engine.align_multiple_takes(song_path, valid_takes)

                        music_analyzer = MusicBeatAnalyzer()
                        analysis = music_analyzer.analyze(song_path, manual_bpm=float(params.get("bpm", 0.0)) or None)

                        tracker = VisionTracker(valid_takes[0])
                        director = MusicVideoDirector(
                            analysis=analysis,
                            takes=takes_info,
                            tracker=tracker,
                            target_resolution=params.get("resolution", "720p"),
                            zoom_factor=float(params.get("zoom", 1.85)),
                            enable_drop_punchins=bool(params.get("drop_punchins", True)),
                            enable_speed_ramps=bool(params.get("speed_ramps", True)),
                            enable_beat_fx=bool(params.get("beat_fx", True)),
                        )
                        shot_plans = director.plan_music_video()
                        all_inputs = valid_takes
                        active_bpm = analysis.bpm
                    else:
                        analyzer = AudioAnalyzer(
                            noise_threshold_db=-32.0,
                            min_silence_duration=0.35,
                        )
                        segments = analyzer.extract_speech_segments(input_path)

                        if params.get("remove_fillers"):
                            hesitations = detect_acoustic_hesitations(input_path)
                            segments = remove_filler_intervals(segments, hesitations)

                        tracker = VisionTracker(input_path)
                        broll_mgr = BRollManager(broll_dir) if (broll_dir and os.path.isdir(broll_dir)) else None

                        director = CameraDirector(
                            tracker=tracker,
                            pacing_style=params.get("pacing", "dynamic"),
                            zoom_factor=float(params.get("zoom", 1.75)),
                            broll_manager=broll_mgr,
                            enable_freeze_frames=bool(params.get("freeze_frame", True)),
                            transition_style=params.get("transition", "flash"),
                            target_person=target_person,
                        )
                        shot_plans = director.plan_production(segments)
                        all_inputs = [input_path]
                        active_bpm = None

                    stem, _ = os.path.splitext(input_path)
                    out_path = f"{stem}_capcut_master.mp4"

                    res_choice = params.get("resolution", "720p")
                    res_map = {"720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}
                    bw, bh = res_map.get(res_choice, (1280, 720))

                    aspect_ratio = params.get("aspect_ratio", "16:9")
                    if aspect_ratio == "9:16":
                        tw, th = bh, bw
                        is_portrait_target = True
                    elif aspect_ratio == "1:1":
                        dim = min(bw, bh)
                        tw, th = dim, dim
                        is_portrait_target = False
                    else:
                        if tracker.metadata.is_portrait:
                            tw, th = bh, bw
                            is_portrait_target = True
                        else:
                            tw, th = bw, bh
                            is_portrait_target = False

                    trans_choice = params.get("transition_style") or params.get("transition", "flash")

                    config = RenderConfig(
                        target_width=tw,
                        target_height=th,
                        is_portrait=is_portrait_target,
                        color_grade=params.get("color_grade") or params.get("color", "cinematic"),
                        bgm_path=params.get("bgm_path") or params.get("bgm"),
                        bgm_volume=float(params.get("bgm_volume", 0.22)),
                        enable_captions=bool(params.get("enable_captions", params.get("captions", False))),
                        caption_color=params.get("caption_color", "yellow"),
                        stabilize=bool(params.get("stabilize", False)),
                        stabilize_smoothing=int(params.get("stabilize_smoothing", 25)),
                        letterbox=bool(params.get("letterbox", False)),
                        film_grain=bool(params.get("film_grain", False)),
                        fx_glow=params.get("fx_glow", "none"),
                        fx_rgb_split=params.get("fx_rgb_split", "none"),
                        fx_camera_motion=params.get("fx_camera_motion", "none"),
                        fx_camcorder_osd=bool(params.get("fx_camcorder_osd", False)),
                        fx_tilt_shift=bool(params.get("fx_tilt_shift", False)),
                        fx_flicker=bool(params.get("fx_flicker", False)),
                        vignette=bool(params.get("vignette", True)),
                        overlay_effect=params.get("overlay_effect") or params.get("overlay"),
                        overlay_blend_mode=params.get("overlay_blend_mode") or params.get("overlay_blend", "screen"),
                        overlay_opacity=float(params.get("overlay_opacity", 0.85)),
                        overlay_target=params.get("overlay_target", "fullscreen"),
                        target_person=target_person,
                        selective_color=selective_color,
                        show_hud=bool(params.get("show_hud", True)),
                        show_title=bool(params.get("show_title", True)),
                        title_text=params.get("title_text") or params.get("title", "OMNICAM AI • MULTI-CAM PRODUCTION"),
                        subtitle_text=params.get("subtitle_text", "PRO VIRTUAL STUDIO // 4K CLARITY"),
                        custom_watermark=params.get("custom_watermark"),
                        input_videos=all_inputs,
                        music_mode=is_music_mode,
                        song_audio_path=song_path if is_music_mode else None,
                        bpm=active_bpm,
                        enable_bass_pump=bool(params.get("bass_pump", False)),
                        enable_speed_ramps=bool(params.get("speed_ramps", False)),
                        beat_reactive_fx=bool(params.get("beat_fx", False)),
                        broll_dir=broll_dir,
                        transition_style=trans_choice,
                        enable_freeze_frames=bool(params.get("enable_freeze_frames", params.get("freeze_frame", True))),
                        freeze_duration=float(params.get("freeze_duration", 0.6)),
                        enable_sfx=bool(params.get("enable_sfx", params.get("sfx", True))),
                        sfx_volume=float(params.get("sfx_volume", 0.35)),
                    )

                    engine = RenderEngine(input_path, config=config)

                    def update_prog(pct, msg):
                        with STATE.lock:
                            STATE.progress = pct
                            STATE.status_message = msg

                    engine.render(shot_plans, out_path, progress_callback=update_prog)

                    # Automatically mirror / save to device photo library / downloads folder if on mobile/Termux
                    saved_device_path = None
                    try:
                        candidate_dirs = [
                            "/sdcard/DCIM/Camera",
                            "/sdcard/Movies",
                            "/sdcard/Download",
                            os.path.expanduser("~/storage/shared/DCIM/Camera"),
                            os.path.expanduser("~/storage/downloads"),
                        ]
                        for cdir in candidate_dirs:
                            if os.path.isdir(cdir):
                                out_filename = os.path.basename(out_path)
                                target_dest = os.path.join(cdir, out_filename)
                                shutil.copy2(out_path, target_dest)
                                saved_device_path = target_dest
                                try:
                                    subprocess.run(["termux-media-scan", target_dest], capture_output=True, timeout=5)
                                except Exception:
                                    pass
                                break
                    except Exception as err:
                        print(f"  [!] Note: auto-copy to phone storage: {err}")

                    with STATE.lock:
                        STATE.progress = 1.0
                        STATE.status_message = "Complete - Saved to Device"
                        STATE.output_file = out_path
                        STATE.saved_device_path = saved_device_path
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
