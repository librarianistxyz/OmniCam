#!/usr/bin/env bash
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

