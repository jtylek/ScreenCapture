from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QGuiApplication, QImage, QKeyEvent
from PySide6.QtWidgets import QApplication
import pytest

from screencapture.capture import CaptureSession, ScreenShot


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _session(qapp):
    img = QImage(100, 100, QImage.Format_RGB32)
    img.fill(0)
    s = CaptureSession([ScreenShot(img, QRect(0, 0, 100, 100), 1.0, None)], [])
    out = []
    s.cancelled.connect(lambda: out.append("cancel"))
    s.start()
    return s, out


def test_escape_cancels_via_app_filter(qapp):
    s, out = _session(qapp)
    s.eventFilter(None, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    assert out == ["cancel"]
    assert not s._idle.isActive() and not s._heartbeat.isActive()


def test_idle_timeout_cancels(qapp):
    s, out = _session(qapp)
    s._idle.timeout.emit()
    assert out == ["cancel"]


def test_sleep_gap_cancels(qapp):
    s, out = _session(qapp)
    s._last_tick -= 60
    s._tick()
    assert out == ["cancel"]


def test_screen_change_cancels(qapp):
    s, out = _session(qapp)
    QGuiApplication.instance().primaryScreenChanged.emit(QGuiApplication.primaryScreen())
    assert out == ["cancel"]


def test_right_click_cancels_via_app_filter(qapp):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent

    s, out = _session(qapp)
    e = QMouseEvent(QEvent.MouseButtonPress, QPointF(5, 5), Qt.RightButton, Qt.RightButton, Qt.NoModifier)
    s.eventFilter(None, e)
    assert out == ["cancel"]
