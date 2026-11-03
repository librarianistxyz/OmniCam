#!/usr/bin/env bash
# ==============================================================================
# OmniCam - AI Virtual Multi-Camera Director Runner
# Supports Linux Host, macOS, and Android Termux
# ==============================================================================

set -e

# Detect Termux environment
IS_TERMUX=false
if [ -n "$TERMUX_VERSION" ] || [ -d "/data/data/com.termux" ]; then
    IS_TERMUX=true
fi

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "[-] Error: python3 is not installed."
    if [ "$IS_TERMUX" = true ]; then
        echo "    Install on Termux with: pkg update && pkg install -y python"
    else
        echo "    Install with: sudo apt install python3"
    fi
    exit 1
fi

# Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "[-] Error: ffmpeg is not installed."
    if [ "$IS_TERMUX" = true ]; then
        echo "    Install on Termux with: pkg install -y ffmpeg"
    else
        echo "    Install with: sudo apt install ffmpeg"
    fi
    exit 1
fi

# Run OmniCam CLI
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/omnicam.py" "$@"

