# ScreenCapture

A small Snagit-style tool: capture a region or a window, annotate it, crop it, and keep a library of
recent captures. Runs on Linux (X11) and Windows. Output is flattened PNG.

- **Capture** – drag a region, or click a window (it is highlighted as you hover); full-screen capture
  with optional 3 s delay from the tray menu. `Esc` / right click cancels.
- **Annotate** – rectangle, ellipse, arrow, line, text, highlight, blur (pixelate), numbered steps.
  Move items, `Delete` removes, full undo/redo. Color and line width in the toolbar.
- **Crop** – drag the crop rectangle (edges resize, inside moves), `Enter` / *Apply crop*.
- **Library** – every capture is saved automatically (newest first, last 500 kept). Open one to edit
  it again; *Save* writes your edits back, *Save as…* exports elsewhere, *Copy* puts it on the clipboard.

## Install

### Linux (Mint / Ubuntu)

```bash
sudo apt install python3-venv libxcb-cursor0     # once
git clone https://github.com/jtylek/ScreenCapture && cd ScreenCapture
./install.sh --autostart                         # per-user, no root; --autostart = tray icon at login
```

Then make **PrintScreen** start a capture: *Menu → Keyboard → Shortcuts → Custom Shortcuts → Add*,
command `~/.local/bin/screencapture --capture` (clear the built-in screenshot shortcut first).
Remove with `./uninstall.sh` (`--purge` also deletes the library).

### Windows

Download `ScreenCapture-Setup-<version>.exe` from the
[Releases](https://github.com/jtylek/ScreenCapture/releases) page and run it. It installs per user
(no admin needed) and optionally adds a desktop shortcut and start-at-login. To bind a key: Start menu →
right-click *Capture region* → Properties → *Shortcut key*.

Build the installer yourself on Windows (needs Python 3.9+ and [Inno Setup](https://jrsoftware.org/isinfo.php)):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Pushing a `v*` tag builds the installer and Linux bundle in GitHub Actions and attaches them to a release.

## Command line

`screencapture` (library) · `--capture` · `--fullscreen` · `--library` · `--tray` (start quietly) · `--quit`.
These talk to the already running instance, so they are what keyboard shortcuts should call.

## Development

```bash
pip install -e ".[dev]" && QT_QPA_PLATFORM=offscreen pytest
```

Not implemented yet: Wayland (needs the xdg-desktop-portal screenshot API), resizing handles on
existing annotations, scrolling capture.
