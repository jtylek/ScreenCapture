# ScreenCapture

A simple screen capture tool for Windows and Linux. Capture a region or a window, add annotations, crop,
and keep your screenshots in a library. Output is flattened PNG.

- **Capture** – drag a region, or click a window (it is highlighted as you hover); full-screen capture
  with optional 3 s delay from the tray menu. `Esc` / right click cancels.
- **Annotate** – rectangle, ellipse, arrow, line, text, highlight, blur (pixelate), numbered steps.
  Move items, `Delete` removes, full undo/redo. Color and line width in the toolbar.
- **Crop** – drag the crop rectangle (edges resize, inside moves), `Enter` / *Apply*.
- **Cut out** – remove a vertical or horizontal strip from the middle of the image; the two sides are joined.
- **Library** – every capture is saved automatically (newest first, last 500 kept). Open one to edit
  it again; *Save* writes your edits back, *Save as…* exports elsewhere, *Copy* puts it on the clipboard.

## Install

### Linux (Mint / Ubuntu)

```bash
sudo apt install python3-venv libxcb-cursor0
wget -qO- https://github.com/jtylek/ScreenCapture/releases/latest/download/screencapture-linux.tar.gz | tar xz
cd screencapture && ./install.sh --autostart
```

That's it: start **ScreenCapture** from the menu (or run `screencapture`). To update, run the same commands again.

- The installer works for your user only, no `sudo`. It sets up a private Python environment in
  `~/.local/share/screencapture` (needs internet), a `screencapture` command in `~/.local/bin` and a menu entry.
- `--autostart` is optional: it starts the app quietly in the tray at login, which the capture hotkey needs.
- If the `screencapture` command is not found right after installing, log out and back in.
- Set your capture hotkey in **Library → Settings** (gear icon); see [Settings](#settings) for using PrintScreen.
  Alternative that always works: add a custom system shortcut with the command `~/.local/bin/screencapture --capture`.
- **Uninstall:** `cd screencapture && ./uninstall.sh` (`--purge` also deletes your saved screenshots).

### Windows

**[Download ScreenCapture-Setup.exe](https://github.com/jtylek/ScreenCapture/releases/latest/download/ScreenCapture-Setup.exe)**
(always the latest release; older versions are on the [Releases](https://github.com/jtylek/ScreenCapture/releases) page) and run it. It installs per user
(no admin needed) and optionally adds a desktop shortcut and start-at-login. Set the capture hotkey in
**Library → Settings** (gear icon). If you want PrintScreen and Windows already uses it for the Snipping Tool, turn
that off in *Settings → Accessibility → Keyboard → Use the Print screen button to open screen capture*.

Build the installer yourself on Windows (needs Python 3.9+ and [Inno Setup](https://jrsoftware.org/isinfo.php)):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Pushing a `v*` tag builds the installer and Linux bundle in GitHub Actions and attaches them to a release.

## Settings

**Startup** (Library → Settings): start ScreenCapture quietly in the tray when you sign in to Windows / Linux, so
the capture hotkey is always ready.

**Theme**: follow the system, light or dark (Library → Settings). The sun/moon button in the Library toolbar
switches between light and dark in one click.

**Capture hotkey** (Library → Settings): a global shortcut that starts a region / window capture from any
application. Default `Ctrl+Shift+Print`. Works on Windows and Linux/X11 (not Wayland). `Ctrl+Alt+letter` is
refused because it is AltGr on many keyboards. Clear the box to turn the hotkey off.

Using **PrintScreen** as the hotkey:

- **Linux Mint:** the system holds that key for its own screenshot tool. Clear the system screenshot
  shortcut under *Keyboard → Shortcuts* first. ScreenCapture tells you when a key is taken.
- **Windows:** Windows may be holding PrintScreen for the Snipping Tool. Turn that off under
  *Settings → Accessibility → Keyboard → Use the Print screen button to open screen capture*.

## Command line

`screencapture` (library) · `--capture` · `--fullscreen` · `--library` · `--tray` (start quietly) · `--quit`.
These talk to the already running instance, so they are what keyboard shortcuts should call.

## Development

```bash
pip install -e ".[dev]" && QT_QPA_PLATFORM=offscreen pytest
```

Not implemented yet: Wayland (needs the xdg-desktop-portal screenshot API), resizing handles on
existing annotations, scrolling capture.
