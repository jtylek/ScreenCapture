"""Yes/no preferences kept in QSettings (what happens to a new capture)."""
from __future__ import annotations

from PySide6.QtCore import QSettings

AUTO_CLIPBOARD = "autoClipboard"  # default on
AUTO_SAVE = "autoSaveToLibrary"  # default off
DEFAULTS = {AUTO_CLIPBOARD: True, AUTO_SAVE: False}


def get(key: str) -> bool:
    v = QSettings("ScreenCapture", "ScreenCapture").value(key, DEFAULTS[key])
    return v if isinstance(v, bool) else str(v).lower() in ("true", "1")


def set_(key: str, on: bool):
    s = QSettings("ScreenCapture", "ScreenCapture")
    s.setValue(key, bool(on))
    s.sync()
