# CLAUDE.md

Simple, free (MIT, by Janusz Tylek; see LICENSE and `__init__.py`) screen capture tool for Windows and Linux (X11) built with Python + PySide6 (Qt 6): capture a region or
window, annotate, crop / cut out, keep a library of screenshots. Output is flattened PNG. README.md is the user
documentation; keep it accurate when behaviour changes, and don't mention other products in it.

## Layout

`screencapture/`: `app.py` (tray app, single-instance control via `--capture` etc.), `capture.py` (per-monitor capture overlays),
`windows.py` (window rectangles: X11 / Win32), `editor.py` + `items.py` (annotation editor, undo commands),
`library.py` (library storage + window), `hotkey.py` (global hotkey: XGrabKey / RegisterHotKey),
`autostart.py`, `theme.py`, `icons.py`, `settings_dialog.py`, `winutil.py` (window placement), `resize_dialogs.py` (resize image / canvas size dialogs), `about.py`, `diagnostics.py` (log, runtime check). `packaging/` (Windows installer, launcher, icons),
`install.sh` / `uninstall.sh` (Linux), `.github/workflows/release.yml`.

Supported platforms: Windows 10/11 and Linux/X11. NOT supported: Wayland, macOS (no window enumeration, global hotkey,
autostart or packaging there; note macOS already ships a `screencapture` command).

## Commands

```bash
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest -q tests            # fast, headless (the X11 hotkey test is skipped)
xvfb-run -a pytest -q tests                           # full run incl. the real X11 hotkey grab test
xvfb-run -n 301 pytest -q tests                       # several runs in parallel: give each its own display
                                                      # number (-a races when started at the same moment)
```

Needs `libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1` (+ `libxcb-cursor0` for a real X11 session).
Tests are isolated by `tests/conftest.py` (own HOME / XDG dirs / QSettings): never write to real user state.
Don't claim a push is good unless the test run actually passed (a pipe into `tail` hides failures).

README screenshots (`docs/screenshots/*.png`) come from the real windows with made-up sample captures:
`xvfb-run -a -s "-screen 0 1700x1100x24" env PYTHONPATH=. python docs/make_screenshots.py`. Regenerate them (and keep
the README's feature descriptions in step) when the UI changes.

## Releasing

Version lives in `pyproject.toml` and `screencapture/__init__.py` (bump both). Then run **Actions → Build installers**
on `main` (or push a `v*` tag): it tests, builds `ScreenCapture-Setup.exe` (PyInstaller + Inno Setup on
windows-latest) and `screencapture-linux.tar.gz`, and publishes release `v<version>`, creating the tag through
the API. Git tag pushes can be blocked in sandboxed sessions, so prefer the manual workflow run.
The release asset names are fixed on purpose: the README links to `releases/latest/download/<name>`.

## Gotchas learned the hard way

- The PyInstaller entry point must be `packaging/launcher.py` (absolute import). Using
  `screencapture/__main__.py` crashed the installed exe with "relative import with no known parent package".
  Before releasing, build the frozen app locally and run it under `xvfb-run` (start, then `--quit`).
- Toolbar/menu icons are drawn in code and must be attached with `icons.tag(action, name)`, not
  `action.setIcon(icons.icon(...))`, otherwise they don't recolour when the theme changes.
- Windows-only code (RegisterHotKey, Run registry key, window enumeration, installer script) can't run in the Linux
  dev environment: CI only proves it builds. Say so, and ask the maintainer to test on Windows.
- Global hotkeys: X11 and Windows only (no Wayland). Reject `Ctrl+Alt+<letter>` (AltGr on Polish / German
  keyboards). On Linux Mint PrintScreen is owned by the system and must be freed first; on Windows by the
  Snipping Tool.
- PySide6 6.12.0 leaks references to `None` on Python < 3.12 (every void call, e.g. `QPainter.setPen`) and aborts with
  `Fatal Python error: none_dealloc` after some painting. Python 3.12+ has immortal `None`, so dev machines on 3.12/3.13 and
  the Windows build never show it, but Linux Mint 21 / Ubuntu 22.04 (Python 3.10) do. `pyproject.toml` pins
  `PySide6-Essentials<6.12` for Python < 3.12, `diagnostics.check_runtime()` detects it at startup, and CI tests on 3.10.
  Reproduce with `uv python install 3.10` + a 3.10 venv. Raising the pin needs `tests/test_runtime.py` green on 3.10.
- A crash log is written to `~/.local/share/ScreenCapture/ScreenCapture/screencapture.log` (faulthandler + Qt warnings).
- Window sizes: never size or place a window from the primary screen or from image pixels. Use `winutil.size_and_place` /
  `ensure_on_screen` (target screen = where the mouse is, 90% cap, always on screen). A 4K capture once made the editor
  larger than the screen, so its title bar and close button were unreachable.
- Multi-monitor / display scaling: capture uses ONE OVERLAY WINDOW PER MONITOR (`capture.CaptureSession`), each showing that
  monitor's native-resolution grab at its own scale. A single window across monitors with different scaling (100% + 133%)
  is mis-sized by Windows and shifted captures (content cut on the left, black strip on the right). Native window
  rectangles (Win32 / X11) are physical pixels; Qt keeps each monitor's top-left at its native position and only scales
  its size, so `windows_for_screen` maps them per monitor. Never use `x / dpr` from the desktop origin. Tests cover a
  133% monitor to the left of a 100% primary.
- Modal dialogs block the capture overlays: while one of our dialogs (Settings, About, Resize…) is open Qt drops ALL input to
  every other window of the app, so pressing the capture hotkey with Settings open froze the overlays (no click, Esc did
  nothing). `CaptureSession` makes the first overlay application-modal (newest modal window wins) and the other monitors'
  overlays its child windows (never blocked); `ScreenCapture._hide_own_windows` hides nothing while a modal dialog is open
  (hiding the library window also hides its dialogs on Windows), so our own dialogs can be captured. `QTest.mouseClick(widget)`
  bypasses the blocking: send test input to `widget.windowHandle()` (see `tests/test_capture_modal.py`).
- A busy X server can drop a brand-new connection: X11 code retries.
- UI strings are plain English; there is no translation system.
- Keep dependencies minimal (`PySide6-Essentials`, `python-xlib` on Linux only).
