"""Screen grabbing and the selection overlay: one overlay window per monitor.

Every monitor gets its own window at its own scale. A single window spanning monitors with different display
scaling (e.g. 100% and 133%) is placed and scaled wrongly by Windows, which shifted captures."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget


@dataclass
class ScreenShot:
    image: QImage  # the monitor in native (physical) pixels
    geometry: QRect  # Qt's logical geometry; its top-left is the monitor's native top-left, its size is scaled
    dpr: float
    screen: object = None  # the QScreen (None in tests)

    @property
    def native_rect(self) -> QRect:
        return QRect(self.geometry.topLeft(), self.image.size())


def grab_screens() -> list[ScreenShot]:
    shots = []
    for s in QGuiApplication.screens():
        img = s.grabWindow(0).toImage().convertToFormat(QImage.Format_RGB32)
        img.setDevicePixelRatio(1.0)
        shots.append(ScreenShot(img, s.geometry(), s.devicePixelRatio(), s))
    return shots


def grab_current_screen() -> QImage:
    """The monitor under the mouse, at full native resolution."""
    shots = grab_screens()
    pos = QCursor.pos()
    return next((s.image for s in shots if s.geometry.contains(pos)), shots[0].image)


def windows_for_screen(shot: ScreenShot, native_windows: list[QRect]) -> list[QRect]:
    """Window rectangles (native desktop pixels, topmost first) -> this monitor's overlay widget coordinates."""
    native, d = shot.native_rect, shot.dpr
    out = []
    for r in native_windows:
        c = r.intersected(native)
        if c.width() < 8 or c.height() < 8:
            continue
        out.append(QRect(round((c.x() - native.x()) / d), round((c.y() - native.y()) / d), round(c.width() / d), round(c.height() / d)))
    return out


class CaptureOverlay(QWidget):
    """One monitor, frozen and dimmed. Drag = region, click = window under the cursor, Esc / right click = cancel."""

    captured = Signal(QImage)
    cancelled = Signal()

    def __init__(self, shot: ScreenShot, native_windows: list[QRect]):
        super().__init__()
        self._shot = shot
        self._windows = windows_for_screen(shot, native_windows)
        self._press: QPoint | None = None
        self._cur = QPoint()
        self._sel: QRect | None = None
        self._hover: QRect | None = None
        self._done = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        if shot.screen is not None:
            self.setScreen(shot.screen)
        self.setGeometry(shot.geometry)

    def dismiss(self):
        self.releaseKeyboard()
        self.hide()
        self.deleteLater()

    # -- events ------------------------------------------------------------------------------

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            return self._finish(None)
        if e.button() == Qt.LeftButton:
            self._press = e.position().toPoint()
            self._cur = self._press

    def mouseMoveEvent(self, e):
        self._cur = e.position().toPoint()
        if self._press is not None:
            if (self._cur - self._press).manhattanLength() > 4 or self._sel is not None:
                self._sel = QRect(self._press, self._cur).normalized()
        else:
            self._hover = next((r for r in self._windows if r.contains(self._cur)), None)
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._press is None:
            return
        rect = self._sel if self._sel is not None else self._hover
        self._press = None
        if rect is None or rect.width() < 3 or rect.height() < 3:
            self._sel = None
            return self.update()
        self._finish(rect.intersected(self.rect()))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._finish(None)

    def _finish(self, rect: QRect | None):
        if self._done:
            return
        self._done = True
        if rect is None:
            return self.cancelled.emit()
        d, img = self._shot.dpr, self._shot.image
        src = QRect(round(rect.x() * d), round(rect.y() * d), round(rect.width() * d), round(rect.height() * d)).intersected(img.rect())
        self.captured.emit(img.copy(src))

    # -- painting ----------------------------------------------------------------------------

    def paintEvent(self, _e):
        p = QPainter(self)
        img, d = self._shot.image, self._shot.dpr
        p.drawImage(self.rect(), img)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))
        box = self._sel if self._sel is not None else (self._hover if self._press is None else None)
        if box is not None:
            src = QRectF(box.x() * d, box.y() * d, box.width() * d, box.height() * d)
            p.drawImage(QRectF(box), img, src)
            p.setPen(QPen(QColor("#2f81f7"), 2))
            p.drawRect(box)
            label = f"{round(box.width() * d)} × {round(box.height() * d)}"
            p.setFont(QFont(self.font().family(), 10))
            w = p.fontMetrics().horizontalAdvance(label) + 12
            ty = box.top() - 24 if box.top() > 28 else box.top() + 4
            tag = QRect(box.left(), ty, w, 20)
            p.fillRect(tag, QColor(0, 0, 0, 200))
            p.setPen(Qt.white)
            p.drawText(tag, Qt.AlignCenter, label)


class CaptureSession(QObject):
    """Overlays on all monitors; the first selection (or a cancel on any of them) ends the session."""

    captured = Signal(QImage)
    cancelled = Signal()

    def __init__(self, shots: list[ScreenShot], native_windows: list[QRect]):
        super().__init__()
        self.overlays = [CaptureOverlay(s, native_windows) for s in shots]
        self._done = False
        for o in self.overlays:
            o.captured.connect(self._on_captured)
            o.cancelled.connect(self._on_cancelled)

    def start(self):
        for o in self.overlays:
            o.show()
            o.raise_()
        under_mouse = next((o for o in self.overlays if o.geometry().contains(QCursor.pos())), self.overlays[0])
        under_mouse.activateWindow()
        under_mouse.grabKeyboard()  # Esc cancels

    def _dismiss_all(self):
        for o in self.overlays:
            o.dismiss()

    def _on_captured(self, img: QImage):
        if not self._done:
            self._done = True
            self._dismiss_all()
            self.captured.emit(img)

    def _on_cancelled(self):
        if not self._done:
            self._done = True
            self._dismiss_all()
            self.cancelled.emit()
