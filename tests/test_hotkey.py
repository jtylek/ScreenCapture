import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from screencapture import hotkey


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    "text,ok",
    [
        ("Ctrl+Shift+Print", True),
        ("Print", True),
        ("F9", True),
        ("Ctrl+Shift+S", True),
        ("Meta+Shift+X", True),
        ("S", False),  # plain letter
        ("Ctrl+Alt+S", False),  # AltGr on Polish / German keyboards
        ("Ctrl+Alt+F5", True),
        ("Ctrl+Shift+Return", False),  # unsupported key
        ("Ctrl+A, Ctrl+B", False),  # chord
        ("", False),
    ],
)
def test_parse(qapp, text, ok):
    parsed, err = hotkey.parse(text)
    assert (err is None) == ok, err
    assert (parsed is not None) == ok


def test_empty_hotkey_turns_off(qapp, tmp_path):
    m = hotkey.HotkeyManager()
    assert m.apply("", persist=False) is None and m.current == ""


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="needs an X11 display (run under xvfb-run)")
def test_x11_grab_fires_and_conflicts(qapp):
    Xlib = pytest.importorskip("Xlib")
    from Xlib import X, XK, display
    from Xlib.ext import xtest

    a, b = hotkey.HotkeyManager(), hotkey.HotkeyManager()
    hits = []
    a.triggered.connect(lambda: hits.append(1))
    assert a.apply("Ctrl+Shift+F9", persist=False) is None
    assert "already used" in b.apply("Ctrl+Shift+F9", persist=False)  # same grab twice -> refused
    assert b.current == ""

    d = display.Display()
    code = lambda name: d.keysym_to_keycode(XK.string_to_keysym(name))
    for k in ("Control_L", "Shift_L", "F9"):
        xtest.fake_input(d, X.KeyPress, code(k))
    for k in ("F9", "Shift_L", "Control_L"):
        xtest.fake_input(d, X.KeyRelease, code(k))
    d.sync()
    deadline = time.time() + 3
    while not hits and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.05)
    a.stop()
    d.close()
    assert hits, "hotkey press was not delivered"

    # failed change keeps the previous hotkey registered
    assert a.apply("Ctrl+Shift+F8", persist=False) is None
    assert b.apply("Ctrl+Shift+F8", persist=False) is not None
    assert a.apply("Ctrl+Shift+F7", persist=False) is None and a.current == "Ctrl+Shift+F7"
    a.stop()
