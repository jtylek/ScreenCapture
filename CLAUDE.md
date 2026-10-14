# CLAUDE.md

Simple screen capture tool for Windows and Linux (X11) built with Python + PySide6 (Qt 6): capture a region or
window, annotate, crop / cut out, keep a library of screenshots. Output is flattened PNG. README.md is the user
documentation; keep it accurate when behaviour changes, and don't mention other products in it.

## Layout

`screencapture/`: `app.py` (tray app, single-instance control via `--capture` etc.), `capture.py` (overlay),
`windows.py` (window rectangles: X11 / Win32), `editor.py` + `items.py` (annotation editor, undo commands),
`library.py` (library storage + window), `hotkey.py` (global hotkey: XGrabKey / RegisterHotKey),
`autostart.py`, `theme.py`, `icons.py`, `settings_dialog.py`. `packaging/` (Windows installer, launcher, icons),
`install.sh` / `uninstall.sh` (Linux), `.github/workflows/release.yml`.

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
- A busy X server can drop a brand-new connection: X11 code retries.
- UI strings are plain English; there is no translation system.
- Keep dependencies minimal (`PySide6-Essentials`, `python-xlib` on Linux only).
