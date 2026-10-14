#!/usr/bin/env bash
# Removes the per-user ScreenCapture install. Your captures are kept unless you pass --purge.
set -euo pipefail
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
"$HOME/.local/bin/screencapture" --quit 2>/dev/null || true
rm -rf "$DATA/screencapture/venv" "$DATA/screencapture/screencapture.png"
rmdir "$DATA/screencapture" 2>/dev/null || true
rm -f "$HOME/.local/bin/screencapture" "$DATA/applications/screencapture.desktop" \
      "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/screencapture.desktop"
if [[ "${1:-}" == "--purge" ]]; then
    rm -rf "$DATA/screencapture" "$DATA/ScreenCapture"
    echo "Removed, including the capture library."
else
    echo "Removed. Captures are still in $DATA/ScreenCapture (run with --purge to delete them)."
fi
