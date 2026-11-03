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
  <title>OmniCam Studio | Autonomous Multi-Camera Video Production Engine</title>
  <meta name="description" content="OmniCam transforms single-camera handheld footage into an automated multi-camera studio production with AI angle cuts, 3D LUTs, auto-ducking BGM, and Hormozi captions.">

  <!-- Google Fonts: Plus Jakarta Sans & Outfit (Mustuds Typography) -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <!-- FontAwesome 6 Icons -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" integrity="sha512-DTOQO9RWCH3ppGqcWaEA1BIZOC6xxalwEsw9c2QQeAIftl+Vegovlnee1c9QX4TctnWMn13TZye+giMm8e2LwA==" crossorigin="anonymous" referrerpolicy="no-referrer" />

  <style>
    /* ==========================================================================
       OmniCam Studio - Executive Light Theme (Inspired by Mustuds.com)
       ========================================================================== */
    :root {
      /* Brand Palette (Executive Corporate Blue & Pure Contrast) */
      --primary: #0052CC;
      --primary-hover: #0747A6;
      --primary-deep: #091E42;
      --primary-light: #EBF3FF;
      --primary-subtle: #DEEBFF;
      --accent-cyan: #00A3BF;
      --accent-sky: #0284C7;

      /* Status Palette */
      --success: #059669;
      --success-hover: #047857;
      --success-bg: #ECFDF5;
      --warning: #D97706;
      --danger: #DC2626;

      /* Light Executive Canvas (Pure Crisp White & Soft Slate) */
      --bg-body: #F8FAFC;
      --bg-navbar: rgba(255, 255, 255, 0.95);
      --bg-card: #FFFFFF;
      --bg-card-hover: #F8FAFC;
      --bg-input: #FFFFFF;
      --bg-subtle: #F1F5F9;
      --border-card: #E2E8F0;
      --border-strong: #CBD5E1;

      /* Typography Colors (ZERO GRADIENTS, CRISP HIGH-CONTRAST) */
      --text-heading: #091E42;
      --text-main: #0F172A;
      --text-secondary: #475569;
      --text-muted: #64748B;
      --text-white: #FFFFFF;

      /* Elevation & Shadows */
      --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
      --shadow-md: 0 4px 16px rgba(9, 30, 66, 0.08);
      --shadow-lg: 0 12px 32px rgba(9, 30, 66, 0.12);
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 16px;
      --radius-full: 9999px;

      /* Fonts */
      --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-heading: 'Outfit', 'Plus Jakarta Sans', sans-serif;
    }

    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    html {
      scroll-behavior: smooth;
      font-size: 16px;
    }

    body {
      background-color: var(--bg-body);
      color: var(--text-main);
      font-family: var(--font-sans);
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      overflow-x: hidden;
      padding-top: 72px; /* Space for fixed navbar */
    }

    .container {
      width: 100%;
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 1.25rem;
    }

    /* ==========================================================================
       TOP FIXED EXECUTIVE NAVBAR
       ========================================================================== */
    .navbar {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 72px;
      background: var(--bg-navbar);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--border-card);
      z-index: 1000;
      display: flex;
      align-items: center;
      box-shadow: 0 1px 4px rgba(9, 30, 66, 0.04);
    }

    .nav-container {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
    }

    .brand-logo {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      text-decoration: none;
      color: var(--text-heading);
    }

    .brand-icon-box {
      width: 40px;
      height: 40px;
      background: var(--primary);
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #FFFFFF;
      font-size: 1.2rem;
      box-shadow: 0 3px 10px rgba(0, 82, 204, 0.3);
    }

    .brand-text {
      display: flex;
      flex-direction: column;
    }

    .brand-name {
      font-family: var(--font-heading);
      font-size: 1.35rem;
      font-weight: 800;
      letter-spacing: -0.3px;
      color: var(--text-heading);
      line-height: 1.1;
    }

    .brand-tagline {
      font-size: 0.7rem;
      color: var(--primary);
      font-weight: 700;
      letter-spacing: 0.4px;
      text-transform: uppercase;
    }

    .nav-links {
      display: flex;
      align-items: center;
      gap: 1.5rem;
      list-style: none;
    }

    .nav-link {
      text-decoration: none;
      color: var(--text-secondary);
      font-size: 0.9rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 0.45rem;
      transition: all 0.2s ease;
      padding: 0.45rem 0.75rem;
      border-radius: var(--radius-sm);
    }

    .nav-link:hover {
      color: var(--primary);
      background: var(--bg-subtle);
    }

    .nav-actions {
      display: flex;
      align-items: center;
      gap: 1rem;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.35rem 0.85rem;
      border-radius: var(--radius-full);
      background: var(--success-bg);
      border: 1px solid #A7F3D0;
      font-size: 0.78rem;
      font-weight: 700;
      color: var(--success);
    }

    .status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #10B981;
      box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
    }

    .btn-nav-cta {
      text-decoration: none;
      background: var(--primary);
      color: #FFFFFF;
      font-size: 0.88rem;
      font-weight: 700;
      padding: 0.55rem 1.15rem;
      border-radius: var(--radius-md);
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      transition: background 0.2s ease, transform 0.1s ease;
      box-shadow: 0 3px 10px rgba(0, 82, 204, 0.25);
      border: none;
      cursor: pointer;
    }

    .btn-nav-cta:hover {
      background: var(--primary-hover);
      transform: translateY(-1px);
    }

    /* ==========================================================================
       HERO BANNER SECTION (MUSTUDS CRISP WHITE ARCHITECTURE)
       ========================================================================== */
    .hero-section {
      position: relative;
      padding: 4rem 0 3rem;
      border-bottom: 1px solid var(--border-card);
      background: linear-gradient(180deg, #EBF3FF 0%, #F8FAFC 100%);
      text-align: center;
    }

    .hero-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.45rem 1.1rem;
      border-radius: var(--radius-full);
      background: #FFFFFF;
      border: 1px solid #BFDBFE;
      color: var(--primary);
      font-size: 0.76rem;
      font-weight: 700;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      margin-bottom: 1.35rem;
      box-shadow: 0 2px 8px rgba(0, 82, 204, 0.08);
    }

    .hero-title {
      font-family: var(--font-heading);
      font-size: clamp(2.1rem, 4.2vw, 3.4rem);
      font-weight: 800;
      line-height: 1.18;
      letter-spacing: -0.8px;
      color: var(--text-heading);
      max-width: 920px;
      margin: 0 auto 1.35rem;
    }

    .hero-subtitle {
      font-size: clamp(1.02rem, 1.8vw, 1.18rem);
      color: var(--text-secondary);
      max-width: 820px;
      margin: 0 auto 2.25rem;
      line-height: 1.65;
    }

    .hero-cta-group {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: center;
      gap: 1rem;
      margin-bottom: 2.75rem;
    }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.55rem;
      font-family: var(--font-sans);
      font-weight: 700;
      border-radius: var(--radius-md);
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s ease;
      border: 1px solid transparent;
      padding: 0.75rem 1.45rem;
      font-size: 0.95rem;
    }

    .btn-lg {
      padding: 0.85rem 1.85rem;
      font-size: 1rem;
    }

    .btn-primary {
      background: var(--primary);
      color: #FFFFFF;
      box-shadow: 0 4px 14px rgba(0, 82, 204, 0.25);
    }
    .btn-primary:hover {
      background: var(--primary-hover);
      transform: translateY(-1px);
      box-shadow: 0 6px 18px rgba(0, 82, 204, 0.35);
    }

    .btn-secondary {
      background: #FFFFFF;
      color: var(--text-heading);
      border-color: var(--border-strong);
      box-shadow: var(--shadow-sm);
    }
    .btn-secondary:hover {
      background: var(--bg-subtle);
      border-color: #94A3B8;
      transform: translateY(-1px);
    }

    .btn-outline {
      background: transparent;
      color: var(--text-secondary);
      border-color: var(--border-strong);
    }
    .btn-outline:hover {
      background: #FFFFFF;
      color: var(--text-heading);
      border-color: var(--text-heading);
      transform: translateY(-1px);
      box-shadow: var(--shadow-sm);
    }

    .btn-success {
      background: var(--success);
      color: #FFFFFF;
      box-shadow: 0 4px 14px rgba(5, 150, 105, 0.25);
    }
    .btn-success:hover {
      background: var(--success-hover);
      transform: translateY(-1px);
      box-shadow: 0 6px 18px rgba(5, 150, 105, 0.35);
    }

    /* Trust / Spec Bar */
    .security-trust-bar {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 1rem;
    }

    .security-trust-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.65rem;
      padding: 0.7rem 1.25rem;
      border-radius: var(--radius-md);
      background: #FFFFFF;
      border: 1px solid var(--border-card);
      color: var(--text-secondary);
      font-size: 0.85rem;
      text-decoration: none;
      box-shadow: var(--shadow-sm);
    }

    .security-trust-badge strong {
      color: var(--text-heading);
    }

    /* ==========================================================================
       SECTION CONTAINERS & CARDS
       ========================================================================== */
    .main-content {
      padding: 3rem 0 5rem;
    }

    .studio-section {
      margin-bottom: 2.75rem;
    }

    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1.15rem;
    }

    .section-title {
      font-family: var(--font-heading);
      font-size: 1.35rem;
      font-weight: 700;
      color: var(--text-heading);
      display: flex;
      align-items: center;
      gap: 0.65rem;
    }

    .section-tag {
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--primary);
      background: var(--primary-light);
      padding: 0.3rem 0.75rem;
      border-radius: var(--radius-sm);
      border: 1px solid #BFDBFE;
    }

    .card {
      background: #FFFFFF;
      border: 1px solid var(--border-card);
      border-radius: var(--radius-lg);
      padding: 1.75rem;
      box-shadow: var(--shadow-md);
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }

    .card:hover {
      border-color: #CBD5E1;
      box-shadow: 0 6px 20px rgba(9, 30, 66, 0.1);
    }

    .card-title {
      font-family: var(--font-heading);
      font-size: 1.15rem;
      font-weight: 700;
      color: var(--text-heading);
      margin-bottom: 0.4rem;
      display: flex;
      align-items: center;
      gap: 0.55rem;
    }

    .card-desc {
      font-size: 0.88rem;
      color: var(--text-muted);
      margin-bottom: 1.35rem;
    }

    /* Form Fields */
    label {
      display: block;
      font-size: 0.85rem;
      font-weight: 600;
      color: #334155;
      margin-bottom: 0.45rem;
      margin-top: 1rem;
    }

    label:first-child { margin-top: 0; }

    input[type="text"], select {
      width: 100%;
      background: #FFFFFF;
      border: 1px solid var(--border-strong);
      color: var(--text-main);
      padding: 0.8rem 1rem;
      border-radius: var(--radius-md);
      font-size: 0.94rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }

    input[type="text"]:focus, select:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(0, 82, 204, 0.15);
    }

    /* Path Chips */
    .chip-container {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: 0.85rem;
    }

    .path-chip {
      background: var(--bg-subtle);
      border: 1px solid var(--border-card);
      color: var(--text-secondary);
      font-size: 0.78rem;
      font-weight: 600;
      padding: 0.4rem 0.85rem;
      border-radius: var(--radius-full);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.15s ease;
    }

    .path-chip:hover {
      background: var(--primary-light);
      border-color: var(--primary);
      color: var(--primary);
    }

    /* Grid Layouts */
    .grid-2 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1.75rem;
    }

    .grid-4 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.15rem;
    }

    /* KPI Stat Cards */
    .stat-card {
      background: var(--bg-body);
      border: 1px solid var(--border-card);
      border-radius: var(--radius-md);
      padding: 1.25rem 1.35rem;
      display: flex;
      align-items: center;
      gap: 1.15rem;
      box-shadow: var(--shadow-sm);
    }

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: var(--radius-md);
      background: var(--primary-light);
      color: var(--primary);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.3rem;
      flex-shrink: 0;
    }

    .stat-meta {
      display: flex;
      flex-direction: column;
    }

    .stat-label {
      font-size: 0.76rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .stat-val {
      font-family: var(--font-heading);
      font-size: 1.45rem;
      font-weight: 800;
      color: var(--text-heading);
      line-height: 1.2;
    }

    /* Timeline Visualizer */
    .timeline-wrapper {
      margin-top: 1.75rem;
    }

    .timeline-track {
      width: 100%;
      height: 52px;
      background: var(--bg-subtle);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-md);
      display: flex;
      overflow: hidden;
      margin-top: 0.6rem;
      position: relative;
    }

    .shot-block {
      height: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-size: 0.74rem;
      font-weight: 700;
      color: #FFFFFF;
      border-right: 1px solid rgba(0, 0, 0, 0.25);
      cursor: pointer;
      transition: filter 0.15s, transform 0.15s;
      overflow: hidden;
      white-space: nowrap;
      padding: 0 4px;
    }

    .shot-block:hover {
      filter: brightness(1.2);
    }

    /* Camera Angle Colors */
    .angle-wide { background: #0052CC; }
    .angle-closeup { background: #DC2626; }
    .angle-third_left { background: #0891B2; }
    .angle-third_right { background: #0D9488; }
    .angle-slow_push { background: #D97706; }
    .angle-broll { background: #059669; }

    .timeline-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 1.15rem;
      margin-top: 1rem;
      font-size: 0.78rem;
      color: var(--text-secondary);
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 0.45rem;
    }

    .legend-dot {
      width: 12px;
      height: 12px;
      border-radius: 3px;
    }

    /* Shot Inspector */
    .shot-inspector-card {
      margin-top: 1.15rem;
      background: var(--bg-body);
      border: 1px solid var(--border-card);
      border-radius: var(--radius-md);
      padding: 1rem 1.25rem;
      font-size: 0.88rem;
      color: var(--text-secondary);
      display: none;
    }

    .shot-inspector-card strong {
      color: var(--text-heading);
    }

    /* Toggles & Sliders */
    .toggle-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.95rem 0;
      border-bottom: 1px solid #F1F5F9;
    }

    .toggle-row:last-child {
      border-bottom: none;
    }

    .toggle-meta {
      display: flex;
      flex-direction: column;
    }

    .toggle-title {
      font-size: 0.92rem;
      font-weight: 700;
      color: var(--text-main);
    }

    .toggle-desc {
      font-size: 0.78rem;
      color: var(--text-muted);
      margin-top: 0.15rem;
    }

    input[type="checkbox"] {
      width: 1.3rem;
      height: 1.3rem;
      accent-color: var(--primary);
      cursor: pointer;
    }

    .slider-row {
      margin-top: 1.15rem;
    }

    .slider-header {
      display: flex;
      justify-content: space-between;
      font-size: 0.85rem;
      font-weight: 600;
      color: #334155;
      margin-bottom: 0.45rem;
    }

    .slider-val {
      color: var(--primary);
      font-weight: 800;
    }

    input[type="range"] {
      width: 100%;
      height: 7px;
      background: #E2E8F0;
      border-radius: 4px;
      accent-color: var(--primary);
      cursor: pointer;
    }

    /* Render Box & Progress */
    .progress-box {
      margin-top: 1.75rem;
      display: none;
    }

    .progress-header {
      display: flex;
      justify-content: space-between;
      font-size: 0.92rem;
      font-weight: 700;
      color: var(--text-heading);
      margin-bottom: 0.55rem;
    }

    .progress-bar-bg {
      width: 100%;
      height: 11px;
      background: #E2E8F0;
      border-radius: var(--radius-full);
      overflow: hidden;
      border: 1px solid #CBD5E1;
    }

    .progress-bar-fill {
      height: 100%;
      width: 0%;
      background: var(--primary);
      transition: width 0.3s ease;
    }

    video {
      width: 100%;
      border-radius: var(--radius-md);
      margin-top: 1.35rem;
      background: #000000;
      border: 1px solid var(--border-card);
      box-shadow: var(--shadow-lg);
    }

    /* ==========================================================================
       SITE FOOTER (MUSTUDS CORPORATE ARCHITECTURE)
       ========================================================================== */
    .site-footer {
      background: var(--primary-deep);
      border-top: 1px solid #1E2D4A;
      padding: 3.5rem 0 2.25rem;
      margin-top: 4.5rem;
      color: #F8FAFC;
    }

    .footer-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 2.25rem;
      margin-bottom: 2.75rem;
    }

    .footer-col h4 {
      font-family: var(--font-heading);
      font-size: 0.95rem;
      font-weight: 700;
      color: #FFFFFF;
      margin-bottom: 1.15rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .footer-links {
      list-style: none;
    }

    .footer-links li {
      margin-bottom: 0.65rem;
    }

    .footer-links a {
      color: #94A3B8;
      text-decoration: none;
      font-size: 0.88rem;
      transition: color 0.15s;
    }

    .footer-links a:hover {
      color: #FFFFFF;
    }

    .footer-bottom {
      border-top: 1px solid rgba(255, 255, 255, 0.1);
      padding-top: 1.75rem;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      font-size: 0.82rem;
      color: #94A3B8;
    }

    
    /* ==========================================================================
       DEVICE FILE NAVIGATOR MODAL STYLES
       ========================================================================== */
    .modal-backdrop {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(9, 30, 66, 0.65);
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
      z-index: 2000;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }

    .modal-window {
      background: #FFFFFF;
      border-radius: var(--radius-lg);
      border: 1px solid var(--border-card);
      box-shadow: var(--shadow-lg);
      width: 100%;
      max-width: 780px;
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
      padding: 1.15rem 1.35rem;
      border-bottom: 1px solid var(--border-card);
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #F8FAFC;
    }

    .modal-close-btn {
      background: transparent;
      border: none;
      font-size: 1.6rem;
      color: var(--text-muted);
      cursor: pointer;
      line-height: 1;
      padding: 0.2rem 0.55rem;
      border-radius: var(--radius-sm);
    }
    .modal-close-btn:hover {
      color: var(--text-heading);
      background: #E2E8F0;
    }

    .modal-roots-bar {
      display: flex;
      gap: 0.5rem;
      padding: 0.65rem 1.35rem;
      background: #F1F5F9;
      border-bottom: 1px solid var(--border-card);
      overflow-x: auto;
      white-space: nowrap;
    }

    .browser-root-chip {
      background: #FFFFFF;
      border: 1px solid var(--border-strong);
      color: var(--text-heading);
      font-size: 0.78rem;
      font-weight: 700;
      padding: 0.35rem 0.75rem;
      border-radius: var(--radius-full);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.15s ease;
    }
    .browser-root-chip:hover {
      background: var(--primary-light);
      border-color: var(--primary);
      color: var(--primary);
    }

    .browser-nav-bar {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.65rem 1.35rem;
      border-bottom: 1px solid var(--border-card);
      background: #FFFFFF;
    }

    .browser-breadcrumbs {
      display: flex;
      align-items: center;
      gap: 0.35rem;
      overflow-x: auto;
      white-space: nowrap;
      font-size: 0.82rem;
    }

    .crumb-btn {
      background: transparent;
      border: none;
      color: var(--primary);
      font-weight: 600;
      cursor: pointer;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      transition: background 0.15s;
    }
    .crumb-btn:hover {
      background: var(--primary-light);
      text-decoration: underline;
    }
    .crumb-sep {
      color: var(--text-muted);
      font-size: 0.75rem;
    }

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
      padding: 0.7rem 1.35rem;
      border-bottom: 1px solid #F1F5F9;
      cursor: pointer;
      transition: background 0.15s;
    }
    .browser-item:hover {
      background: #F8FAFC;
    }

    .browser-item-left {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex: 1;
      min-width: 0;
    }

    .browser-item-icon {
      width: 34px;
      height: 34px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      font-size: 1rem;
    }
    .icon-folder { background: #EBF3FF; color: var(--primary); }
    .icon-video { background: #ECFDF5; color: var(--success); }
    .icon-file { background: #F1F5F9; color: var(--text-muted); }

    .browser-item-name {
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--text-main);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .browser-item-meta {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .badge-video {
      background: #ECFDF5;
      color: var(--success);
      border: 1px solid #A7F3D0;
      font-size: 0.7rem;
      font-weight: 700;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
    }

    .modal-footer {
      padding: 0.85rem 1.35rem;
      border-top: 1px solid var(--border-card);
      background: #F8FAFC;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    /* Mobile Responsive */
    @media (max-width: 768px) {
      .nav-links { display: none; }
      .hero-title { font-size: 1.95rem; }
      .hero-subtitle { font-size: 0.98rem; }
      .security-trust-bar { flex-direction: column; align-items: stretch; }
      .card { padding: 1.25rem; }
    }
  </style>
</head>
<body>

  <!-- ========================================================================
       TOP EXECUTIVE NAVBAR
       ======================================================================== -->
  <nav class="navbar">
    <div class="container nav-container">
      <a href="#" class="brand-logo">
        <div class="brand-icon-box">
          <i class="fa-solid fa-film"></i>
        </div>
        <div class="brand-text">
          <span class="brand-name">OmniCam</span>
          <span class="brand-tagline">AI Multi-Camera Studio</span>
        </div>
      </a>

      <ul class="nav-links">
        <li><a href="#footage" class="nav-link"><i class="fa-solid fa-folder-open"></i> <span>Footage</span></a></li>
        <li><a href="#timeline" class="nav-link"><i class="fa-solid fa-timeline"></i> <span>Timeline</span></a></li>
        <li><a href="#settings" class="nav-link"><i class="fa-solid fa-sliders"></i> <span>Studio Suite</span></a></li>
        <li><a href="#export" class="nav-link"><i class="fa-solid fa-clapperboard"></i> <span>Export</span></a></li>
      </ul>

      <div class="nav-actions">
        <div class="status-pill">
          <span class="status-dot"></span>
          <span>Engine Online (Port 8080)</span>
        </div>
        <a href="#export" class="btn-nav-cta">
          <i class="fa-solid fa-bolt"></i>
          <span>Render Master</span>
        </a>
      </div>
    </div>
  </nav>

  <!-- ========================================================================
       HERO BANNER (MUSTUDS DESIGN LANGUAGE)
       ======================================================================== -->
  <header class="hero-section">
    <div class="container">
      <div class="hero-badge">
        <i class="fa-solid fa-wand-magic-sparkles"></i> AUTONOMOUS VIRTUAL MULTI-CAMERA PRODUCTION STUDIO
      </div>

      <h1 class="hero-title">
        Turn single-camera takes into studio multi-cam masterpieces.
      </h1>

      <p class="hero-subtitle">
        OmniCam automatically trims acoustic dead-air silences, cuts dynamic rule-of-thirds close-up angles, locks horizon stabilization, ducks background music under speech, and burns animated Hormozi word captions—running 100% offline on your device.
      </p>

      <div class="hero-cta-group">
        <a href="#footage" class="btn btn-primary btn-lg">
          <i class="fa-solid fa-folder-open"></i> Select Footage
        </a>
        <a href="#timeline" class="btn btn-secondary btn-lg">
          <i class="fa-solid fa-chart-line"></i> View Timeline Cuts
        </a>
        <a href="#settings" class="btn btn-outline btn-lg">
          <i class="fa-solid fa-sliders"></i> Studio Controls
        </a>
      </div>

      <!-- Trust Bar -->
      <div class="security-trust-bar">
        <div class="security-trust-badge">
          <i class="fa-solid fa-bolt" style="color: #38BDF8;"></i>
          <span><strong>Hardware Accelerated:</strong> Pure Local S9+ CPU / GPU</span>
        </div>
        <div class="security-trust-badge">
          <i class="fa-solid fa-shield-halved" style="color: #10B981;"></i>
          <span><strong>100% Offline &amp; Private:</strong> Zero Cloud Uploads</span>
        </div>
        <div class="security-trust-badge">
          <i class="fa-solid fa-circle-check" style="color: #F59E0B;"></i>
          <span><strong>Samsung Native:</strong> Standard H.264 Playback</span>
        </div>
      </div>
    </div>
  </header>

  <!-- ========================================================================
       MAIN APPLICATION WORKSPACE
       ======================================================================== -->
  <main class="main-content">
    <div class="container">

      <!-- STEP 1: SOURCE FOOTAGE -->
      <section class="studio-section" id="footage">
        <div class="section-header">
          <h2 class="section-title">
            <i class="fa-solid fa-folder-open" style="color: #0052CC;"></i> Step 1: Source Footage &amp; Media Hub
          </h2>
          <span class="section-tag">Storage Access</span>
        </div>

        <div class="card">
          <div class="card-title">
            <i class="fa-solid fa-video"></i> Handheld Video Source File
          </div>
          <p class="card-desc">
            Select any raw 4K/1080p single-camera recording from anywhere on your device or phone gallery to transform.
          </p>

          <label for="inputVideo">Selected Video Path</label>
          <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.75rem;">
            <input type="text" id="inputVideo" placeholder="/sdcard/DCIM/Camera/VID_20261103.mp4" spellcheck="false" style="flex: 1; min-width: 250px;" />
            <button class="btn btn-primary" onclick="openFileBrowser()" type="button" title="Navigate anywhere on device">
              <i class="fa-solid fa-folder-tree"></i> Browse Device
            </button>
            <button class="btn btn-secondary" onclick="document.getElementById('nativeFilePicker').click()" type="button" title="Pick from Phone Gallery or Files">
              <i class="fa-solid fa-mobile-screen"></i> Gallery
            </button>
            <input type="file" id="nativeFilePicker" accept="video/*" style="display: none;" onchange="handleNativeFileSelect(this)" />
          </div>

          <div id="uploadStatusBadge" style="display: none; margin-bottom: 0.75rem; padding: 0.55rem 0.95rem; border-radius: 6px; font-size: 0.85rem; background: #EBF3FF; color: #0052CC; border: 1px solid #BFDBFE;">
            <i class="fa-solid fa-spinner fa-spin"></i> <span id="uploadStatusMsg">Reading device video...</span>
          </div>

          <label style="margin-top: 0.5rem;">Quick Storage Shortcuts</label>
          <div class="chip-container">
            <span class="path-chip" onclick="openFileBrowser('/sdcard/DCIM/Camera')">
              <i class="fa-solid fa-camera"></i> Camera (DCIM)
            </span>
            <span class="path-chip" onclick="openFileBrowser('/sdcard/Movies')">
              <i class="fa-solid fa-film"></i> Movies
            </span>
            <span class="path-chip" onclick="openFileBrowser('/sdcard/Download')">
              <i class="fa-solid fa-download"></i> Downloads
            </span>
            <span class="path-chip" onclick="openFileBrowser('/sdcard')">
              <i class="fa-solid fa-hard-drive"></i> /sdcard (Internal)
            </span>
            <span class="path-chip" onclick="openFileBrowser('~')">
              <i class="fa-solid fa-house"></i> Termux Home
            </span>
            <span class="path-chip" onclick="openFileBrowser('.')">
              <i class="fa-solid fa-briefcase"></i> Workspace
            </span>
          </div>

          <div style="margin-top: 1.5rem; display: flex; justify-content: flex-end;">
            <button class="btn btn-primary" id="analyzeBtn" onclick="analyzeFootage()" type="button">
              <i class="fa-solid fa-bolt"></i> Analyze Footage &amp; Generate Multi-Cam Timeline
            </button>
          </div>
        </div>
      </section>

      <!-- STEP 2: TIMELINE & METRICS -->
      <section class="studio-section" id="timeline">
        <div class="section-header">
          <h2 class="section-title">
            <i class="fa-solid fa-timeline" style="color: #0052CC;"></i> Step 2: Multi-Camera Timeline &amp; Telemetry
          </h2>
          <span class="section-tag">Director Analysis</span>
        </div>

        <div class="card" id="timelineCard" style="display: none;">
          <!-- 4 KPI Stat Cards -->
          <div class="grid-4">
            <div class="stat-card">
              <div class="stat-icon"><i class="fa-solid fa-stopwatch"></i></div>
              <div class="stat-meta">
                <span class="stat-label">Edited Duration</span>
                <span class="stat-val" id="statEditedDur">00:00</span>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon" style="color: #34D399; background: rgba(5,150,105,0.15);"><i class="fa-solid fa-scissors"></i></div>
              <div class="stat-meta">
                <span class="stat-label">Dead Air Cut</span>
                <span class="stat-val" id="statDeadAir">0.0s</span>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon" style="color: #F59E0B; background: rgba(217,119,6,0.15);"><i class="fa-solid fa-camera-rotate"></i></div>
              <div class="stat-meta">
                <span class="stat-label">Camera Cuts</span>
                <span class="stat-val" id="statCuts">0</span>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon" style="color: #A78BFA; background: rgba(139,92,246,0.15);"><i class="fa-solid fa-arrow-trend-up"></i></div>
              <div class="stat-meta">
                <span class="stat-label">Retention Boost</span>
                <span class="stat-val" id="statSaved">+0%</span>
              </div>
            </div>
          </div>

          <!-- Interactive Multi-Camera Timeline Track -->
          <div class="timeline-wrapper">
            <label style="margin-top: 0;">Multi-Camera Cut Sequence Track</label>
            <div class="timeline-track" id="timelineTrack"></div>

            <div class="timeline-legend">
              <div class="legend-item"><div class="legend-dot" style="background: #0052CC;"></div> Wide Establishing</div>
              <div class="legend-item"><div class="legend-dot" style="background: #DC2626;"></div> Tight Close-Up</div>
              <div class="legend-item"><div class="legend-dot" style="background: #0891B2;"></div> Rule of Thirds (Left)</div>
              <div class="legend-item"><div class="legend-dot" style="background: #0D9488;"></div> Rule of Thirds (Right)</div>
              <div class="legend-item"><div class="legend-dot" style="background: #D97706;"></div> Cinematic Slow Push</div>
              <div class="legend-item"><div class="legend-dot" style="background: #059669;"></div> B-Roll Cutaway</div>
            </div>

            <!-- Shot Detail Inspector -->
            <div class="shot-inspector-card" id="shotInspector">
              Tap any shot block above to inspect angle and duration parameters.
            </div>
          </div>
        </div>
      </section>

      <!-- STEP 3: STUDIO SETTINGS (CATEGORIZED SAAS CARDS) -->
      <section class="studio-section" id="settings">
        <div class="section-header">
          <h2 class="section-title">
            <i class="fa-solid fa-sliders" style="color: #0052CC;"></i> Step 3: Studio Suite Controls &amp; Aesthetics
          </h2>
          <span class="section-tag">Production Engine</span>
        </div>

        <div class="grid-2">
          <!-- CARD 1: CAMERA & CADENCE -->
          <div class="card">
            <div class="card-title">
              <i class="fa-solid fa-camera"></i> Camera Cadence &amp; Framing
            </div>
            <p class="card-desc">Configure director pacing rhythm and close-up punch-in magnification.</p>

            <label for="pacingSelect">Director Cutting Pace</label>
            <select id="pacingSelect">
              <option value="dynamic" selected>Dynamic (Fast cuts, rapid zoom punch-ins for Reels/Shorts)</option>
              <option value="podcast">Podcast (Deliberate cuts on natural topic transitions)</option>
              <option value="documentary">Documentary (Cinematic wide pauses with slow push-ins)</option>
              <option value="dramatic">Dramatic (Emphasizes emotional close-ups)</option>
            </select>

            <div class="slider-row">
              <div class="slider-header">
                <span>Close-Up Zoom Punch-In</span>
                <span class="slider-val" id="zoomVal">1.75x</span>
              </div>
              <input type="range" id="zoomRange" min="120" max="220" value="175" oninput="document.getElementById('zoomVal').innerText = (this.value/100).toFixed(2) + 'x'" />
            </div>

            <label for="targetRes">Master Target Resolution</label>
            <select id="targetRes">
              <option value="720p" selected>720p HD (Ultra-Fast Mobile Render on S9+)</option>
              <option value="1080p">1080p Full HD (Balanced Master)</option>
              <option value="4k">4K UHD (Highest Fidelity Studio Master)</option>
            </select>
          </div>

          <!-- CARD 2: COLOR SCIENCE & LETTERBOX -->
          <div class="card">
            <div class="card-title">
              <i class="fa-solid fa-palette"></i> Color Science &amp; Cinema Framing
            </div>
            <p class="card-desc">Apply professional 3D LUT grading and anamorphic cinema bars.</p>

            <label for="colorSelect">3D LUT Color Profile</label>
            <select id="colorSelect">
              <option value="cinematic" selected>Cinematic (Teal &amp; Orange Hollywood Contrast)</option>
              <option value="podcast">Podcast Warm (Rich Skin Tones &amp; Subtle Shadows)</option>
              <option value="vintage">Vintage 35mm (Analog Film Saturation &amp; Grain)</option>
              <option value="none">Natural Flat (Preserve Original Camera Colors)</option>
            </select>

            <div class="toggle-row" style="margin-top: 1rem;">
              <div class="toggle-meta">
                <span class="toggle-title">Studio Loudness Normalization</span>
                <span class="toggle-desc">Highpass filter + EBU R128 voice clarity leveling</span>
              </div>
              <input type="checkbox" id="normalizeAudio" checked />
            </div>

            <div class="toggle-row">
              <div class="toggle-meta">
                <span class="toggle-title">2.35:1 Anamorphic Cinema Bars</span>
                <span class="toggle-desc">Ultra-widescreen letterboxing for cinematic scale</span>
              </div>
              <input type="checkbox" id="letterbox" />
            </div>

            <label for="titleText">Opening Lower-Third Title</label>
            <input type="text" id="titleText" value="OMNICAM AI • MULTI-CAM PRODUCTION" />
          </div>

                    <!-- CARD 3: CAPCUT PRO TRANSITIONS & FREEZE FRAMES -->
          <div class="card" style="border-left: 4px solid var(--primary);">
            <div class="card-title">
              <i class="fa-solid fa-wand-magic-sparkles" style="color: var(--primary);"></i> CapCut Style Transitions &amp; Freezes
            </div>
            <p class="card-desc">Professional viral editing tools: white flash strobe, dynamic crash zooms, freeze frame spotlights, and whoosh sound effects.</p>

            <label for="transitionSelect">Cut Transition Effect</label>
            <select id="transitionSelect">
              <option value="flash" selected>⚡ White Flash (CapCut Viral Strobe Impact)</option>
              <option value="zoom">🌀 Dynamic Crash Zoom (Energetic Punch-In)</option>
              <option value="glitch">✨ Glitch RGB Split (Modern Cyber / TikTok)</option>
              <option value="push">🎥 Smooth Ken Burns Glide (Continuous Push)</option>
              <option value="dissolve">🌊 Cinematic Cross Dissolve</option>
              <option value="none">✂️ Clean Jump Cut (No Transition)</option>
            </select>

            <div class="toggle-row" style="margin-top: 1rem;">
              <div class="toggle-meta">
                <span class="toggle-title">❄️ Dramatic Freeze Frames</span>
                <span class="toggle-desc">Freezes key emphatic pauses for 0.6s with spotlight &amp; camera snap</span>
              </div>
              <input type="checkbox" id="freezeFrame" checked />
            </div>

            <div class="toggle-row">
              <div class="toggle-meta">
                <span class="toggle-title">🔊 Transition Sound Effects (SFX)</span>
                <span class="toggle-desc">Synthesized cinematic whoosh &amp; impact sweeps on every cut</span>
              </div>
              <input type="checkbox" id="sfxEnabled" checked />
            </div>

            <div class="toggle-row">
              <div class="toggle-meta">
                <span class="toggle-title">💥 Crash Zoom Punch-In</span>
                <span class="toggle-desc">Dynamic 0.3s zoom punch on close-up angles for retention</span>
              </div>
              <input type="checkbox" id="crashZoom" checked />
            </div>
          </div>

          <!-- CARD 3: SMART ENHANCEMENTS -->
          <div class="card">
            <div class="card-title">
              <i class="fa-solid fa-brain"></i> AI Visual &amp; Audio Enhancements
            </div>
            <p class="card-desc">Autonomous algorithms to fix camera shake, hesitations, and subtitles.</p>

            <div class="toggle-row">
              <div class="toggle-meta">
                <span class="toggle-title">Digital Gimbal Stabilization</span>
                <span class="toggle-desc">Neutralizes walking bounce and handheld jitter</span>
              </div>
              <input type="checkbox" id="stabilize" checked />
            </div>

            <div class="toggle-row">
              <div class="toggle-meta">
                <span class="toggle-title">Hormozi / MrBeast Word Captions</span>
                <span class="toggle-desc">High-contrast animated subtitles with active-word highlight</span>
              </div>
              <input type="checkbox" id="captions" checked />
            </div>

            <div class="toggle-row">
              <div class="toggle-meta">
                <span class="toggle-title">Vocal Filler Word Removal</span>
                <span class="toggle-desc">Cuts "uhm", "ah", "like", and prolonged vocal drones</span>
              </div>
              <input type="checkbox" id="removeFillers" checked />
            </div>
          </div>

          <!-- CARD 4: SOUNDTRACK & B-ROLL -->
          <div class="card">
            <div class="card-title">
              <i class="fa-solid fa-music"></i> Soundtrack Bed &amp; B-Roll Engine
            </div>
            <p class="card-desc">Sidechain auto-ducking music bed and automated B-roll cutaway clips.</p>

            <label for="bgmSelect">Background Music Soundtrack</label>
            <select id="bgmSelect">
              <option value="ambient" selected>Built-in Royalty-Free Ambient Pad (Warm &amp; Subtle)</option>
              <option value="none">None (Dialogue Only)</option>
            </select>

            <div class="slider-row">
              <div class="slider-header">
                <span>Music Volume (Auto-Ducks to -22dB during speech)</span>
                <span class="slider-val" id="bgmVolVal">22%</span>
              </div>
              <input type="range" id="bgmVol" min="5" max="60" value="22" oninput="document.getElementById('bgmVolVal').innerText = this.value + '%'" />
            </div>

            <label for="brollFolder">Automated B-Roll Folder Path</label>
            <input type="text" id="brollFolder" placeholder="/sdcard/Movies/broll or empty" />
          </div>
        </div>
      </section>

      <!-- STEP 4: MASTER RENDER STUDIO -->
      <section class="studio-section" id="export">
        <div class="section-header">
          <h2 class="section-title">
            <i class="fa-solid fa-clapperboard" style="color: #0052CC;"></i> Step 4: Master Production Export Studio
          </h2>
          <span class="section-tag">Final Assembly</span>
        </div>

        <div class="card">
          <div class="card-title">
            <i class="fa-solid fa-bolt"></i> Render Studio Production Video
          </div>
          <p class="card-desc">
            Executes single-pass FFmpeg hardware encoding with camera switching, color LUT, sidechain ducking, and burn-in captions.
          </p>

          <button class="btn btn-success btn-lg" id="renderBtn" onclick="renderStudioVideo()" style="width: 100%;" type="button">
            <i class="fa-solid fa-film"></i> Render Studio Video
          </button>

          <!-- Real-Time Progress -->
          <div class="progress-box" id="progressBox">
            <div class="progress-header">
              <span id="progressMsg">Initializing render pipeline...</span>
              <span id="progressPct">0%</span>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" id="progressBar"></div>
            </div>
          </div>

          <!-- Video Player Output -->
          <div id="videoContainer" style="display: none; margin-top: 1.5rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
              <span style="font-weight: 700; color: #FFFFFF; font-size: 0.95rem;">
                <i class="fa-solid fa-circle-check" style="color: #10B981;"></i> Production Video Ready
              </span>
              <a href="#" id="downloadLink" class="btn btn-secondary" style="padding: 0.4rem 0.85rem; font-size: 0.82rem;">
                <i class="fa-solid fa-download"></i> Download Video
              </a>
            </div>
            <video id="outputVideoPlayer" controls playsinline></video>
          </div>
        </div>
      </section>

    </div>
  </main>

  <!-- ========================================================================
       CORPORATE SITE FOOTER (MUSTUDS ARCHITECTURE)
       ======================================================================== -->
  <footer class="site-footer">
    <div class="container">
      <div class="footer-grid">
        <div class="footer-col" style="grid-column: span 2;">
          <div class="brand-logo" style="margin-bottom: 0.75rem;">
            <div class="brand-icon-box" style="width: 32px; height: 32px; font-size: 0.95rem;">
              <i class="fa-solid fa-film"></i>
            </div>
            <span class="brand-name" style="font-size: 1.2rem;">OmniCam Studio</span>
          </div>
          <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6; max-width: 440px;">
            Autonomous AI virtual multi-camera director engine. Transforms raw single-camera footage into high-retention multi-camera studio videos completely offline on Android and Linux devices.
          </p>
        </div>

        <div class="footer-col">
          <h4>Studio Navigation</h4>
          <ul class="footer-links">
            <li><a href="#footage">Source Footage</a></li>
            <li><a href="#timeline">Timeline Visualizer</a></li>
            <li><a href="#settings">Color &amp; Audio Suite</a></li>
            <li><a href="#export">Master Render</a></li>
          </ul>
        </div>

        <div class="footer-col">
          <h4>Engine Architecture</h4>
          <ul class="footer-links">
            <li><span style="color: var(--text-secondary); font-size: 0.85rem;"><i class="fa-solid fa-microchip"></i> Hardware: S9+ / Exynos 9810</span></li>
            <li><span style="color: var(--text-secondary); font-size: 0.85rem;"><i class="fa-solid fa-video"></i> Core: FFmpeg 6+ Native Filtergraph</span></li>
            <li><span style="color: var(--text-secondary); font-size: 0.85rem;"><i class="fa-solid fa-comment-dots"></i> Subtitles: Whisper.cpp Offline</span></li>
            <li><span style="color: var(--text-secondary); font-size: 0.85rem;"><i class="fa-solid fa-terminal"></i> Platform: Termux Linux</span></li>
          </ul>
        </div>
      </div>

      <div class="footer-bottom">
        <div>
          &copy; 2026 OmniCam Studio Engine. 100% Offline &bull; Zero External Telemetry.
        </div>
        <div>
          <span style="color: #34D399; font-weight: 700;">
            <i class="fa-solid fa-circle" style="font-size: 0.6rem;"></i> Local Web Server Active (Port 8080)
          </span>
        </div>
      </div>
    </div>
  </footer>

  <!-- ========================================================================
       DEVICE FILE NAVIGATOR MODAL
       ======================================================================== -->
  <div id="deviceBrowserModal" class="modal-backdrop" style="display: none;">
    <div class="modal-window">
      <div class="modal-header">
        <div style="display: flex; align-items: center; gap: 0.65rem;">
          <div class="brand-icon-box" style="width: 36px; height: 36px; font-size: 1rem;">
            <i class="fa-solid fa-folder-tree"></i>
          </div>
          <div>
            <h3 style="font-family: var(--font-heading); font-size: 1.15rem; color: var(--text-heading); font-weight: 800; line-height: 1.2;">
              Device File Navigator
            </h3>
            <span style="font-size: 0.75rem; color: var(--text-muted);">Browse all folders and storage locations on your device</span>
          </div>
        </div>
        <button class="modal-close-btn" onclick="closeFileBrowser()" type="button">&times;</button>
      </div>

      <!-- Quick Roots Bar -->
      <div class="modal-roots-bar" id="browserRootsBar"></div>

      <!-- Breadcrumbs & Up Button -->
      <div class="browser-nav-bar">
        <button class="btn btn-secondary btn-sm" id="browserUpBtn" onclick="navigateBrowserUp()" type="button" title="Go to Parent Folder">
          <i class="fa-solid fa-arrow-up"></i> Up
        </button>
        <div class="browser-breadcrumbs" id="browserBreadcrumbs"></div>
      </div>

      <!-- Search / Filter in Directory -->
      <div style="padding: 0.65rem 1.35rem 0.35rem; background: #FFFFFF;">
        <input type="text" id="browserSearchInput" placeholder="Quick filter files in this folder..." oninput="filterBrowserList(this.value)" style="padding: 0.55rem 0.85rem; font-size: 0.85rem;" />
      </div>

      <!-- Directory Contents List -->
      <div class="browser-list-container" id="browserListContainer">
        <div style="padding: 2.5rem; text-align: center; color: var(--text-muted);">
          <i class="fa-solid fa-spinner fa-spin"></i> Loading device storage...
        </div>
      </div>

      <div class="modal-footer">
        <span style="font-size: 0.78rem; color: var(--text-muted);" id="browserStatusText">0 items found</span>
        <button class="btn btn-secondary btn-sm" onclick="closeFileBrowser()" type="button">Close</button>
      </div>
    </div>
  </div>


  <!-- ========================================================================
       CLIENT APPLICATION JAVASCRIPT
       ======================================================================== -->
  <script>
    let currentShots = [];

    // ========================================================================
    // HTML UTILITIES & GALLERY PICKER
    // ========================================================================
    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    async function handleNativeFileSelect(input) {
      const file = input.files && input.files[0];
      if (!file) return;

      const badge = document.getElementById('uploadStatusBadge');
      const msg = document.getElementById('uploadStatusMsg');
      badge.style.display = 'block';
      badge.style.background = '#EBF3FF';
      badge.style.color = '#0052CC';
      badge.style.borderColor = '#BFDBFE';
      msg.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Checking video: <strong>' + escapeHtml(file.name) + '</strong>...';

      // 1. Fast path: see if video already exists on device storage
      try {
        const findRes = await fetch('/api/find_local?name=' + encodeURIComponent(file.name) + '&size=' + file.size);
        const findData = await findRes.json();
        if (findData.found && findData.path) {
          document.getElementById('inputVideo').value = findData.path;
          badge.style.background = '#ECFDF5';
          badge.style.color = '#059669';
          badge.style.borderColor = '#A7F3D0';
          msg.innerHTML = '<i class="fa-solid fa-circle-check"></i> Gallery video linked: <strong>' + escapeHtml(file.name) + '</strong> (' + (file.size / (1024 * 1024)).toFixed(1) + ' MB)';
          input.value = '';
          return;
        }
      } catch (err) {
        // Fall back to upload
      }

      // 2. Stream into workspace uploads folder
      msg.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading from Gallery (0%)...';
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload', true);
      xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name));
      xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');

      xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          msg.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading from Gallery (' + pct + '%)...';
        }
      };

      xhr.onload = function() {
        if (xhr.status === 200) {
          try {
            const resp = JSON.parse(xhr.responseText);
            if (resp.path) {
              document.getElementById('inputVideo').value = resp.path;
              badge.style.background = '#ECFDF5';
              badge.style.color = '#059669';
              badge.style.borderColor = '#A7F3D0';
              msg.innerHTML = '<i class="fa-solid fa-circle-check"></i> Ready to edit: <strong>' + escapeHtml(file.name) + '</strong> (' + (file.size / (1024 * 1024)).toFixed(1) + ' MB)';
              input.value = '';
              return;
            }
          } catch (e) {}
        }
        badge.style.background = '#FEF2F2';
        badge.style.color = '#DC2626';
        badge.style.borderColor = '#FECACA';
        msg.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Upload failed. Try "Browse Device" or typing path directly.';
      };

      xhr.onerror = function() {
        badge.style.background = '#FEF2F2';
        badge.style.color = '#DC2626';
        badge.style.borderColor = '#FECACA';
        msg.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Connection failed while loading video.';
      };

      xhr.send(file);
    }

    // ========================================================================
    // DEVICE FILE NAVIGATOR MODAL HANDLERS
    // ========================================================================
    let browserCurrentDir = '';
    let browserParentDir = null;
    let browserAllEntries = [];

    function openFileBrowser(dir) {
      const modal = document.getElementById('deviceBrowserModal');
      modal.style.display = 'flex';
      loadBrowserDir(dir || 'default');
    }

    function closeFileBrowser() {
      const modal = document.getElementById('deviceBrowserModal');
      modal.style.display = 'none';
    }

    function navigateBrowserUp() {
      if (browserParentDir) {
        loadBrowserDir(browserParentDir);
      }
    }

    async function loadBrowserDir(dir) {
      const listContainer = document.getElementById('browserListContainer');
      const breadcrumbs = document.getElementById('browserBreadcrumbs');
      const rootsBar = document.getElementById('browserRootsBar');
      const statusText = document.getElementById('browserStatusText');
      const upBtn = document.getElementById('browserUpBtn');
      const searchInput = document.getElementById('browserSearchInput');
      if (searchInput) searchInput.value = '';

      listContainer.innerHTML = '<div style="padding: 2.5rem; text-align: center; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Reading device storage...</div>';

      try {
        const res = await fetch('/api/browse?dir=' + encodeURIComponent(dir || 'default'));
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        browserCurrentDir = data.current_dir;
        browserParentDir = data.parent_dir;
        browserAllEntries = data.entries || [];

        // Up button state
        upBtn.disabled = !browserParentDir;
        upBtn.style.opacity = browserParentDir ? '1' : '0.4';

        // Render Quick Roots
        rootsBar.innerHTML = '';
        (data.quick_roots || []).forEach(r => {
          const chip = document.createElement('span');
          chip.className = 'browser-root-chip';
          chip.innerHTML = '<i class="fa-solid ' + r.icon + '"></i> ' + escapeHtml(r.label);
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
        listContainer.innerHTML = '<div style="padding: 2.5rem; text-align: center; color: #DC2626;"><i class="fa-solid fa-triangle-exclamation"></i> ' + escapeHtml(err.message) + '</div>';
        statusText.innerText = 'Error reading storage folder';
      }
    }

    function renderBrowserList(entries) {
      const listContainer = document.getElementById('browserListContainer');
      const statusText = document.getElementById('browserStatusText');
      listContainer.innerHTML = '';

      if (!entries || entries.length === 0) {
        listContainer.innerHTML = '<div style="padding: 2.5rem; text-align: center; color: var(--text-muted);"><i class="fa-regular fa-folder-open"></i> This folder contains no files.</div>';
        statusText.innerText = '0 items found';
        return;
      }

      let videoCount = 0;
      let dirCount = 0;

      entries.forEach(item => {
        if (item.is_video) videoCount++;
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
        meta.className = 'browser-item-meta';

        if (item.is_video) {
          const badge = document.createElement('span');
          badge.className = 'badge-video';
          badge.innerText = item.size || 'VIDEO';
          meta.appendChild(badge);
        } else if (item.is_dir) {
          const badge = document.createElement('span');
          badge.style.fontSize = '0.75rem';
          badge.style.color = 'var(--text-muted)';
          badge.innerText = 'Folder';
          meta.appendChild(badge);
        }

        div.appendChild(left);
        div.appendChild(meta);

        if (item.is_dir) {
          div.onclick = () => loadBrowserDir(item.path);
        } else if (item.is_video) {
          div.onclick = () => selectBrowserFile(item.path);
        }

        listContainer.appendChild(div);
      });

      statusText.innerText = `${videoCount} video(s), ${dirCount} folder(s)`;
    }

    function filterBrowserList(query) {
      if (!query || !query.trim()) {
        renderBrowserList(browserAllEntries);
        return;
      }
      const q = query.toLowerCase().trim();
      const filtered = browserAllEntries.filter(e => e.name.toLowerCase().includes(q));
      renderBrowserList(filtered);
    }

    function selectBrowserFile(filePath) {
      document.getElementById('inputVideo').value = filePath;
      closeFileBrowser();
      const badge = document.getElementById('uploadStatusBadge');
      const msg = document.getElementById('uploadStatusMsg');
      badge.style.display = 'block';
      badge.style.background = '#ECFDF5';
      badge.style.color = '#059669';
      badge.style.borderColor = '#A7F3D0';
      msg.innerHTML = '<i class="fa-solid fa-circle-check"></i> Selected: <strong>' + escapeHtml(filePath.split('/').pop()) + '</strong>';
    }

    function setFolderPath(folder) {
      document.getElementById('inputVideo').value = folder + '/';
      document.getElementById('inputVideo').focus();
    }

    async function scanDevice() {
      const select = document.getElementById('scanSelect');
      select.innerHTML = '<option value="">Scanning device storage for videos...</option>';
      try {
        const res = await fetch('/api/scan');
        const files = await res.json();
        select.innerHTML = '<option value="">-- Pick a discovered video (' + files.length + ' found) --</option>';
        files.forEach(f => {
          const opt = document.createElement('option');
          opt.value = f.path;
          opt.innerText = f.name + ' (' + f.size + ')';
          select.appendChild(opt);
        });
      } catch (err) {
        select.innerHTML = '<option value="">Scan failed. Type path manually.</option>';
      }
    }

    function onScanSelectChange(selectElem) {
      if (selectElem.value) {
        document.getElementById('inputVideo').value = selectElem.value;
      }
    }

    async function analyzeFootage() {
      const inputPath = document.getElementById('inputVideo').value.trim();
      if (!inputPath) return alert('Please enter or select a video file path first.');

      const btn = document.getElementById('analyzeBtn');
      const originalText = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing Acoustics & Angles...';
      btn.disabled = true;

      try {
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            input_path: inputPath,
            pacing: document.getElementById('pacingSelect').value,
            remove_fillers: document.getElementById('removeFillers').checked,
            broll_dir: document.getElementById('brollFolder').value.trim() || null
          })
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        renderTimeline(data);
      } catch (err) {
        alert('Footage Analysis Failed: ' + err.message);
      } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
      }
    }

    function renderTimeline(data) {
      currentShots = data.shots || [];
      const track = document.getElementById('timelineTrack');
      track.innerHTML = '';

      const totalDur = data.edited_duration || 1.0;

      currentShots.forEach((shot, idx) => {
        const dur = shot.duration;
        const pct = Math.max((dur / totalDur) * 100, 0.7);
        const block = document.createElement('div');
        block.className = 'shot-block angle-' + (shot.angle || 'wide');
        block.style.width = pct + '%';
        block.title = 'Shot #' + (idx + 1) + ': ' + (shot.angle || 'wide').toUpperCase() + ' (' + dur.toFixed(1) + 's)';
        block.innerText = dur >= 2.0 ? (shot.angle || 'wide') : '';

        if (shot.is_freeze) {
          block.style.boxShadow = 'inset 0 0 0 2px #F59E0B';
          block.title += ' [❄️ FREEZE FRAME]';
        }

        block.onclick = () => {
          const inspector = document.getElementById('shotInspector');
          inspector.style.display = 'block';
          let freezeNote = shot.is_freeze ? ' &bull; <span style=\"color: #F59E0B; font-weight: 700;\">❄️ Dramatic Freeze Frame (' + (shot.freeze_duration || 0.6) + 's)</span>' : '';
          let transNote = ' &bull; Transition: <strong style=\"text-transform: uppercase;\">' + (shot.transition || 'flash') + '</strong>';
          inspector.innerHTML = '<strong>Shot #' + (idx + 1) + '</strong> &bull; Angle: <strong style=\"text-transform: uppercase;\">' + shot.angle + '</strong>' + transNote + freezeNote + ' &bull; Cut Range: <strong>' + shot.start.toFixed(2) + 's &rarr; ' + shot.end.toFixed(2) + 's</strong> (' + shot.duration.toFixed(2) + 's)';
        };

        track.appendChild(block);
      });

      document.getElementById('statEditedDur').innerText = formatTime(data.edited_duration);
      document.getElementById('statDeadAir').innerText = data.dead_air_cut.toFixed(1) + 's';
      document.getElementById('statCuts').innerText = currentShots.length;
      const boostPct = Math.round((data.dead_air_cut / (data.total_duration || 1.0)) * 100);
      document.getElementById('statSaved').innerText = '+' + boostPct + '%';

      document.getElementById('timelineCard').style.display = 'block';
      // Smooth scroll to timeline
      document.getElementById('timeline').scrollIntoView({ behavior: 'smooth' });
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
      container.scrollIntoView({ behavior: 'smooth' });
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
                                "size": size_str,
                            })
                        except (PermissionError, OSError):
                            continue

                entries.sort(key=lambda x: (not x["is_dir"], not x["is_video"], x["name"].lower()))

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
                        enable_freeze_frames=bool(params.get("freeze_frame", True)),
                        transition_style=params.get("transition", "flash"),
                    )
                    shot_plans = director.plan_production(segments)

                    stem, _ = os.path.splitext(input_path)
                    out_path = f"{stem}_capcut_master.mp4"

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
                        transition_style=params.get("transition", "flash"),
                        enable_freeze_frames=bool(params.get("freeze_frame", True)),
                        enable_sfx=bool(params.get("sfx", True)),
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
