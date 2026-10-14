"""Start ScreenCapture (quietly, in the tray) when the user signs in.

Windows: HKCU\\...\\Run registry value. Linux: an XDG autostart .desktop file.
The state is always read back from the system, so it reflects what the installer or the user set."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

NAME = "ScreenCapture"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _platform() -> str:
    return sys.platform


def supported() -> bool:
    return _platform() == "win32" or _platform().startswith("linux")


# -- Windows ---------------------------------------------------------------------------------


def _win_command() -> str:
    if getattr(sys, "frozen", False):  # the installed ScreenCapture.exe
        return f'"{sys.executable}" --tray'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pyw if pyw.exists() else sys.executable}" -m screencapture --tray'


def _win_enabled() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE) as k:
            winreg.QueryValueEx(k, NAME)
        return True
    except OSError:
        return False


def _win_set(on: bool):
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, _win_command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass


# -- Linux -----------------------------------------------------------------------------------


def _desktop_file() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "autostart" / "screencapture.desktop"


def _quote(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg


def _linux_exec() -> str:
    local = Path.home() / ".local" / "bin" / "screencapture"
    found = str(local) if local.exists() else shutil.which("screencapture")
    if found:
        return f"{_quote(found)} --tray"
    return f"{_quote(sys.executable)} -m screencapture --tray"


def _linux_enabled() -> bool:
    f = _desktop_file()
    if not f.exists():
        return False
    text = f.read_text(errors="ignore").lower()
    return "hidden=true" not in text and "x-gnome-autostart-enabled=false" not in text


def _linux_set(on: bool):
    f = _desktop_file()
    if not on:
        f.unlink(missing_ok=True)
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    icon = Path.home() / ".local" / "share" / "screencapture" / "screencapture.png"
    lines = [
        "[Desktop Entry]", "Type=Application", f"Name={NAME}", "Comment=Screen capture tray app",
        f"Exec={_linux_exec()}", "X-GNOME-Autostart-enabled=true",
    ]
    if icon.exists():
        lines.insert(4, f"Icon={icon}")
    f.write_text("\n".join(lines) + "\n")


# -- public ----------------------------------------------------------------------------------


def is_enabled() -> bool:
    try:
        if _platform() == "win32":
            return _win_enabled()
        if _platform().startswith("linux"):
            return _linux_enabled()
    except Exception:
        pass
    return False


def set_enabled(on: bool) -> str | None:
    """Returns an error message, or None on success."""
    if not supported():
        return "Starting at login is not supported on this system."
    try:
        _win_set(on) if _platform() == "win32" else _linux_set(on)
    except Exception as e:
        return f"Could not change the startup setting: {e}"
    return None
