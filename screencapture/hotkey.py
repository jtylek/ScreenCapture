"""Global capture hotkey: X11 (XGrabKey) and Windows (RegisterHotKey), no extra dependencies."""
from __future__ import annotations

import os
import select
import sys
import threading
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QKeySequence

DEFAULT = "Ctrl+Shift+Print"
SETTINGS_KEY = "hotkey/capture"


def _int(x) -> int:
    return int(getattr(x, "value", x))


def _build_keys() -> dict[int, tuple[str, int]]:
    """Qt key -> (X11 keysym name, Windows virtual-key code)."""
    t: dict[int, tuple[str, int]] = {}
    for c in range(ord("A"), ord("Z") + 1):
        t[c] = (chr(c).lower(), c)
    for d in range(10):
        t[0x30 + d] = (str(d), 0x30 + d)
    f1 = _int(Qt.Key.Key_F1)
    for n in range(1, 25):
        t[f1 + n - 1] = (f"F{n}", 0x70 + n - 1)
    for qt_name, x_name, vk in (
        ("Key_Print", "Print", 0x2C), ("Key_Pause", "Pause", 0x13), ("Key_Insert", "Insert", 0x2D),
        ("Key_Delete", "Delete", 0x2E), ("Key_Home", "Home", 0x24), ("Key_End", "End", 0x23),
        ("Key_PageUp", "Prior", 0x21), ("Key_PageDown", "Next", 0x22), ("Key_Left", "Left", 0x25),
        ("Key_Up", "Up", 0x26), ("Key_Right", "Right", 0x27), ("Key_Down", "Down", 0x28),
        ("Key_Space", "space", 0x20),
    ):
        t[_int(getattr(Qt.Key, qt_name))] = (x_name, vk)
    return t


_KEYS = _build_keys()


@dataclass
class Parsed:
    text: str
    key_name: str  # X11 keysym name
    vk: int  # Windows virtual key
    ctrl: bool
    shift: bool
    alt: bool
    meta: bool


def parse(text: str) -> tuple[Parsed | None, str | None]:
    """Validate a portable key sequence such as 'Ctrl+Shift+Print'. Returns (parsed, error)."""
    ks = QKeySequence.fromString(text, QKeySequence.PortableText)
    if ks.count() != 1:
        return None, "Press a single key combination."
    combo = ks[0]
    key = _int(combo.key())
    mods = combo.keyboardModifiers()
    if key not in _KEYS:
        return None, "That key can't be used as a global hotkey."
    name, vk = _KEYS[key]
    ctrl, shift = bool(mods & Qt.ControlModifier), bool(mods & Qt.ShiftModifier)
    alt, meta = bool(mods & Qt.AltModifier), bool(mods & Qt.MetaModifier)
    standalone = (name[0] == "F" and name[1:].isdigit()) or name in ("Print", "Pause")
    if not (ctrl or shift or alt or meta) and not standalone:
        return None, "Add Ctrl, Alt, Shift or Win/Meta, otherwise the key could not be typed anywhere."
    if ctrl and alt and len(name) == 1:
        return None, "Ctrl+Alt+letter is AltGr on many keyboards (it types accented letters). Choose another combination."
    return Parsed(ks.toString(QKeySequence.PortableText), name, vk, ctrl, shift, alt, meta), None


# -- backends --------------------------------------------------------------------------------


class _X11Hotkey:
    def __init__(self, callback):
        self._callback = callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, p: Parsed) -> str | None:
        try:
            from Xlib import X, XK, display
        except ImportError:
            return "python-xlib is not installed."
        try:
            d = display.Display()
        except Exception:
            return "Could not connect to the X11 display."
        keysym = XK.string_to_keysym(p.key_name)
        code = d.keysym_to_keycode(keysym) if keysym else 0
        if not code:
            d.close()
            return "This keyboard has no such key."
        mods = (
            (X.ControlMask if p.ctrl else 0) | (X.ShiftMask if p.shift else 0)
            | (X.Mod1Mask if p.alt else 0) | (X.Mod4Mask if p.meta else 0)
        )
        root = d.screen().root
        errors: list = []
        combos = [mods | lock for lock in (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask)]  # Caps / Num Lock
        for m in combos:
            root.grab_key(code, m, True, X.GrabModeAsync, X.GrabModeAsync, onerror=lambda e, r: errors.append(e))
        d.sync()
        if errors:
            for m in combos:
                root.ungrab_key(code, m)
            d.sync()
            d.close()
            return (
                "That key combination is already used by the system or another program. "
                "(On Linux Mint, PrintScreen belongs to the system screenshot tool: change it under Keyboard → Shortcuts.)"
            )
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(d, root, code, combos), daemon=True)
        self._thread.start()
        return None

    def _run(self, d, root, code, combos):
        from Xlib import X

        while not self._stop.is_set():
            select.select([d], [], [], 0.25)
            while d.pending_events():
                ev = d.next_event()
                if ev.type == X.KeyPress:
                    self._callback()
        try:
            for m in combos:
                root.ungrab_key(code, m)
            d.sync()
            d.close()
        except Exception:
            pass

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(2)
            self._thread = None


class _WindowsHotkey:
    WM_HOTKEY, WM_QUIT, MOD_NOREPEAT = 0x0312, 0x0012, 0x4000

    def __init__(self, callback):
        self._callback = callback
        self._thread: threading.Thread | None = None
        self._tid = 0

    def start(self, p: Parsed) -> str | None:
        mods = (0x1 if p.alt else 0) | (0x2 if p.ctrl else 0) | (0x4 if p.shift else 0) | (0x8 if p.meta else 0)
        ready, result = threading.Event(), [None]

        def run():
            import ctypes
            from ctypes import wintypes

            user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
            self._tid = kernel32.GetCurrentThreadId()
            msg = wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # creates this thread's message queue
            if not user32.RegisterHotKey(None, 1, mods | self.MOD_NOREPEAT, p.vk):
                result[0] = "That key combination is already used by Windows or another program."
                ready.set()
                return
            ready.set()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == self.WM_HOTKEY:
                    self._callback()
            user32.UnregisterHotKey(None, 1)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        ready.wait(3)
        if result[0]:
            self._thread = None
        return result[0]

    def stop(self):
        if self._thread:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._tid, self.WM_QUIT, 0, 0)
            self._thread.join(2)
            self._thread = None


def _make_backend(callback):
    if sys.platform == "win32":
        return _WindowsHotkey(callback), None
    if sys.platform.startswith("linux"):
        if os.environ.get("XDG_SESSION_TYPE") == "wayland":
            return None, (
                "Global hotkeys are not available on Wayland. Bind a system shortcut to "
                "'screencapture --capture' in your desktop's keyboard settings instead."
            )
        return _X11Hotkey(callback), None
    return None, "Global hotkeys are not supported on this system."


class HotkeyManager(QObject):
    triggered = Signal()
    _fire = Signal()  # hop from the listener thread to the GUI thread

    def __init__(self):
        super().__init__()
        self._settings = QSettings("ScreenCapture", "ScreenCapture")
        self._backend = None
        self.current = ""  # the combination that is actually registered
        self._last = 0.0
        self._fire.connect(self._on_fire)

    def saved(self) -> str:
        return str(self._settings.value(SETTINGS_KEY, DEFAULT))

    def apply(self, text: str, persist: bool = True) -> str | None:
        """Register `text` ('' turns the hotkey off). Returns an error message, or None on success."""
        text = text.strip()
        old = self.current
        err = self._start(text)
        if err:
            if old:
                self._start(old)  # put the previous hotkey back
            self.current = old if self._backend else ""
            return err
        self.current = text
        if persist:
            self._settings.setValue(SETTINGS_KEY, text)
            self._settings.sync()
        return None

    def _start(self, text: str) -> str | None:
        self.stop()
        if not text:
            return None
        parsed, err = parse(text)
        if err:
            return err
        backend, err = _make_backend(self._fire.emit)
        if backend is None:
            return err
        err = backend.start(parsed)
        if err:
            return err
        self._backend = backend
        return None

    def _on_fire(self):
        now = time.monotonic()
        if now - self._last > 0.6:  # key auto-repeat / double presses
            self._last = now
            self.triggered.emit()

    def stop(self):
        if self._backend:
            self._backend.stop()
            self._backend = None
