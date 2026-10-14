"""Screen grabbing and the region/window selection overlay."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget


def grab_desktop() -> tuple[QImage, QRect, float]:
    """All screens composed into one image. Returns (image, logical geometry, device pixel ratio)."""
    screens = QGuiApplication.screens()
    geo = screens[0].geometry()
    for s in screens[1:]:
        geo = geo.united(s.geometry())
    dpr = max(s.devicePixelRatio() for s in screens)
    img = QImage(int(geo.width() * dpr), int(geo.height() * dpr), QImage.Format_RGB32)
    img.fill(Qt.black)
    p = QPainter(img)
    for s in screens:
        g = s.geometry()
        target = QRect(
            int((g.x() - geo.x()) * dpr), int((g.y() - geo.y()) * dpr), int(g.width() * dpr), int(g.height() * dpr)
        )
        p.drawPixmap(target, s.grabWindow(0))
    p.end()
    return img, geo, dpr


def grab_current_screen() -> QImage:
    screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    return screen.grabWindow(0).toImage().convertToFormat(QImage.Format_RGB32)


class CaptureOverlay(QWidget):
    """Frozen, dimmed desktop. Drag = region, click = window under the cursor, Esc/right click = cancel."""

    captured = Signal(QImage)
    cancelled = Signal()

    def __init__(self, desktop: QImage, geometry: QRect, dpr: float, windows: list[QRect]):
        super().__init__()
        self._img, self._geo, self._dpr = desktop, geometry, dpr
        # window rects arrive in physical desktop pixels -> logical widget coordinates
        self._windows = [
            QRect(int(r.x() / dpr) - geometry.x(), int(r.y() / dpr) - geometry.y(), int(r.width() / dpr), int(r.height() / dpr))
            for r in windows
        ]
        self._press: QPoint | None = None
        self._cur = QPoint()
        self._sel: QRect | None = None
        self._hover: QRect | None = None
        self._done = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(geometry)

    def start(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabKeyboard()

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
        self.releaseKeyboard()
        self.hide()
        if rect is None:
            self.cancelled.emit()
        else:
            d = self._dpr
            src = QRect(int(rect.x() * d), int(rect.y() * d), int(rect.width() * d), int(rect.height() * d))
            out = self._img.copy(src)
            out.setDevicePixelRatio(1.0)
            self.captured.emit(out)
        self.deleteLater()

    # -- painting ----------------------------------------------------------------------------

    def paintEvent(self, _e):
        p = QPainter(self)
        p.drawImage(self.rect(), self._img)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))
        box = self._sel if self._sel is not None else (self._hover if self._press is None else None)
        if box is not None:
            d = self._dpr
            src = QRectF(box.x() * d, box.y() * d, box.width() * d, box.height() * d)
            p.drawImage(QRectF(box), self._img, src)
            p.setPen(QPen(QColor("#2f81f7"), 2))
            p.drawRect(box)
            label = f"{int(box.width() * d)} × {int(box.height() * d)}"
            p.setFont(QFont(self.font().family(), 10))
            w = p.fontMetrics().horizontalAdvance(label) + 12
            ty = box.top() - 24 if box.top() > 28 else box.top() + 4
            tag = QRect(box.left(), ty, w, 20)
            p.fillRect(tag, QColor(0, 0, 0, 200))
            p.setPen(Qt.white)
            p.drawText(tag, Qt.AlignCenter, label)
