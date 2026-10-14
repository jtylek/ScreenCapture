#!/usr/bin/env bash
# ScreenCapture installer for Linux (tested target: Linux Mint / Ubuntu, X11).
# Per-user install, no root needed for the app itself:
#   ./install.sh            install or upgrade
#   ./install.sh --autostart   also start it (tray icon) at login
# Remove with ./uninstall.sh
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/screencapture"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
BIN="$BIN_DIR/screencapture"
ICON="$APP_DIR/screencapture.png"

command -v python3 >/dev/null || { echo "python3 is required: sudo apt install python3"; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || { echo "Python 3.9 or newer is required."; exit 1; }
if ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
    echo "Python's venv module is missing. Run:  sudo apt install python3-venv  and re-run this script."
    exit 1
fi

echo "==> Creating virtual environment in $APP_DIR"
mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet --upgrade "$SRC"

cp "$SRC/packaging/screencapture.png" "$ICON"
ln -sf "$APP_DIR/venv/bin/screencapture" "$BIN"

sed -e "s|@BIN@|$BIN|g" -e "s|@ICON@|$ICON|g" "$SRC/packaging/screencapture.desktop" > "$DESKTOP_DIR/screencapture.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

if [[ "${1:-}" == "--autostart" ]]; then
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_DIR/screencapture.desktop" <<EOT
[Desktop Entry]
Type=Application
Name=ScreenCapture
Exec=$BIN --tray
Icon=$ICON
X-GNOME-Autostart-enabled=true
EOT
    echo "==> Will start at login"
fi

# Qt 6's X11 plugin needs libxcb-cursor0, which Mint/Ubuntu don't install by default.
LIBS="$(ldconfig -p 2>/dev/null || true)"
if [[ "$LIBS" != *libxcb-cursor.so.0* ]]; then
    echo
    echo "NOTE: one system library is missing. Install it with:"
    echo "        sudo apt install libxcb-cursor0"
fi

case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "NOTE: add $BIN_DIR to your PATH (log out and in again on Mint)." ;; esac

cat <<EOT

Installed. Start it from the menu ("ScreenCapture") or run:  screencapture

Set your capture hotkey in the app: Library window > Settings (gear icon).
To use PrintScreen, first clear the system's own screenshot shortcut
(Menu > Keyboard > Shortcuts), because the system holds that key.
Alternative: add a custom system shortcut with the command  $BIN --capture
EOT
