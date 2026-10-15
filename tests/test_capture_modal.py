"""A capture started while one of our own modal dialogs (Settings, About, Resize…) is open must still be usable.

Qt drops all input to every other window of the application while a modal dialog is open, which froze the capture
overlays: right-click did nothing. Input is sent here to the QWindow, i.e. through the window system layer where that
blocking happens (QTest.mouseClick(widget, ...) bypasses it and would not notice the bug)."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from screencapture.app import ScreenCapture
from screencapture.capture import CaptureSession, ScreenShot


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _shots(n=1):
    out = []
    for i in range(n):
        img = QImage(200, 120, QImage.Format_RGB32)
        img.fill(QColor("#3366cc"))
        out.append(ScreenShot(img, QRect(i * 200, 0, 200, 120), 1.0, None))
    return out


def _click(overlay, button, pos):
    QTest.mouseClick(overlay.windowHandle(), button, Qt.NoModifier, pos)


def _drag(overlay, a, b):
    w = overlay.windowHandle()
    QTest.mousePress(w, Qt.LeftButton, Qt.NoModifier, a)
    QTest.mouseMove(w, b)
    QTest.mouseRelease(w, Qt.LeftButton, Qt.NoModifier, b)


def _run_with_modal_dialog(scenario):
    """Runs `scenario(dialog)` inside the nested event loop of an open application-modal dialog."""
    dlg = QDialog()
    dlg.setWindowModality(Qt.ApplicationModal)
    QTimer.singleShot(150, lambda: scenario(dlg))
    QTimer.singleShot(8000, dlg.reject)  # never hang the test run
    dlg.exec()


def test_right_click_cancels_while_a_modal_dialog_is_open(qapp):
    events = []

    def scenario(dlg):
        s = CaptureSession(_shots(), [])
        s.cancelled.connect(lambda: events.append("cancelled"))
        s.captured.connect(lambda img: events.append("captured"))
        s.start()
        QTest.qWait(100)
        _click(s.overlays[0], Qt.RightButton, QPoint(20, 20))
        QTest.qWait(150)
        if not events:
            s._on_cancelled()  # clean up the stuck session so the test run goes on
        dlg.accept()

    _run_with_modal_dialog(scenario)
    assert events == ["cancelled"], "the overlay did not receive the click: it is blocked by the modal dialog"


def test_region_drag_works_while_a_modal_dialog_is_open(qapp):
    events = []

    def scenario(dlg):
        s = CaptureSession(_shots(), [])
        s.captured.connect(lambda img: events.append(img.size().toTuple()))
        s.start()
        QTest.qWait(100)
        _drag(s.overlays[0], QPoint(10, 10), QPoint(110, 70))
        QTest.qWait(150)
        if not events:
            s._on_cancelled()
        dlg.accept()

    _run_with_modal_dialog(scenario)
    assert events and abs(events[0][0] - 100) <= 2 and abs(events[0][1] - 60) <= 2


def test_every_monitor_overlay_receives_input_while_a_modal_dialog_is_open(qapp):
    """One overlay per monitor: all of them must stay usable, not just the newest one."""
    events = []

    def scenario(dlg):
        s = CaptureSession(_shots(3), [])
        s.captured.connect(lambda img: events.append(img.size().toTuple()))
        s.start()
        QTest.qWait(100)
        _drag(s.overlays[-1], QPoint(5, 5), QPoint(85, 45))  # the overlay of the third monitor
        QTest.qWait(150)
        if not events:
            s._on_cancelled()
        dlg.accept()

    _run_with_modal_dialog(scenario)
    assert events and abs(events[0][0] - 80) <= 2


def test_second_monitor_overlay_cancels_too(qapp):
    events = []

    def scenario(dlg):
        s = CaptureSession(_shots(2), [])
        s.cancelled.connect(lambda: events.append("cancelled"))
        s.start()
        QTest.qWait(100)
        _click(s.overlays[1], Qt.RightButton, QPoint(10, 10))
        QTest.qWait(150)
        if not events:
            s._on_cancelled()
        dlg.accept()

    _run_with_modal_dialog(scenario)
    assert events == ["cancelled"]


def test_session_still_works_without_any_dialog(qapp):
    """The usual case keeps working: no dialog, right-click cancels, a drag captures."""
    s = CaptureSession(_shots(2), [])
    out = []
    s.cancelled.connect(lambda: out.append("cancelled"))
    s.start()
    QTest.qWait(50)
    _click(s.overlays[1], Qt.RightButton, QPoint(10, 10))
    assert out == ["cancelled"]


# -- our own windows ----------------------------------------------------------------------------------------------------


def _fake_app(*windows):
    return SimpleNamespace(library_window=windows[0], editors=list(windows[1:]), _hidden=[])


def test_own_windows_are_hidden_for_a_capture_but_not_while_a_dialog_is_open(qapp):
    library, editor = QWidget(), QWidget()
    library.show()
    editor.show()
    app = _fake_app(library, editor)
    ScreenCapture._hide_own_windows(app)  # normal case: out of the way of the capture
    assert not library.isVisible() and not editor.isVisible() and app._hidden == [library, editor]
    library.show()
    editor.show()

    def scenario(dlg):
        ScreenCapture._hide_own_windows(app)
        assert library.isVisible() and editor.isVisible() and app._hidden == []  # user is capturing our own dialog
        dlg.accept()

    _run_with_modal_dialog(scenario)
    library.close()
    editor.close()
