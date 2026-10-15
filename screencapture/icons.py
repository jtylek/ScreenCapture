"""Toolbar icons drawn in code (24x24 design grid), so they stay crisp on any DPI and follow the theme."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPalette, QPen, QPixmap, QPolygonF

ACCENT = QColor("#2f81f7")
GREEN = QColor("#2e9e4f")


def _poly(*xy: float) -> QPolygonF:
    return QPolygonF([QPointF(xy[i], xy[i + 1]) for i in range(0, len(xy), 2)])


def _line(p, x1, y1, x2, y2):
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _select(p, fg, bg):
    p.setBrush(fg)
    p.drawPolygon(_poly(5, 3, 5, 19, 9.5, 14.5, 12.5, 21, 15, 19.8, 12, 13.5, 18, 13.5))


def _rect(p, fg, bg):
    p.drawRoundedRect(QRectF(4, 6, 16, 12), 1.5, 1.5)


def _ellipse(p, fg, bg):
    p.drawEllipse(QRectF(4, 6, 16, 12))


def _arrow(p, fg, bg):
    _line(p, 5, 19, 16, 8)
    p.setBrush(fg)
    p.drawPolygon(_poly(19.5, 4.5, 12.5, 6.5, 17.5, 11.5))


def _linetool(p, fg, bg):
    _line(p, 5, 19, 19, 5)


def _text(p, fg, bg):
    _line(p, 6, 6, 18, 6)
    _line(p, 12, 6, 12, 19)
    _line(p, 9.5, 19, 14.5, 19)


def _highlight(p, fg, bg):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 210, 0, 210))
    p.drawRoundedRect(QRectF(3, 8, 18, 9), 1.5, 1.5)
    p.setPen(QPen(fg, 1.6, Qt.SolidLine, Qt.RoundCap))
    _line(p, 6.5, 12.5, 17.5, 12.5)


def _pixelate(p, fg, bg):
    p.setPen(Qt.NoPen)
    for i in range(3):
        for j in range(3):
            c = QColor(fg)
            c.setAlpha(255 if (i + j) % 2 == 0 else 90)
            p.setBrush(c)
            p.drawRect(QRectF(4 + i * 5.4, 4 + j * 5.4, 4.8, 4.8))


def _step(p, fg, bg):
    p.setBrush(fg)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(3.5, 3.5, 17, 17))
    f = QFont()
    f.setBold(True)
    f.setPixelSize(11)
    p.setFont(f)
    p.setPen(bg)
    p.drawText(QRectF(3.5, 3.5, 17, 17), Qt.AlignCenter, "1")


def _crop(p, fg, bg):
    p.drawPolyline(_poly(7, 3, 7, 17, 21, 17))
    p.drawPolyline(_poly(3, 7, 17, 7, 17, 21))


def _blocks(p, fg, rects):
    p.save()
    p.setPen(Qt.NoPen)
    c = QColor(fg)
    c.setAlpha(90)
    p.setBrush(c)
    for r in rects:
        p.drawRoundedRect(QRectF(*r), 1, 1)
    p.restore()


def _cutv(p, fg, bg):  # two panels with the strip between them removed
    _blocks(p, fg, [(2.5, 6, 7, 12), (14.5, 6, 7, 12)])
    _line(p, 11, 3.5, 11, 20.5)
    _line(p, 13, 3.5, 13, 20.5)


def _cuth(p, fg, bg):
    _blocks(p, fg, [(6, 2.5, 12, 7), (6, 14.5, 12, 7)])
    _line(p, 3.5, 11, 20.5, 11)
    _line(p, 3.5, 13, 20.5, 13)


def _apply(p, fg, bg):
    p.setPen(QPen(GREEN, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline(_poly(5, 12.5, 10, 17.5, 19, 7))


def _undo(p, fg, bg):
    p.drawPolyline(_poly(9, 4.5, 5, 8.5, 9, 12.5))
    from PySide6.QtGui import QPainterPath

    path = QPainterPath(QPointF(5, 8.5))
    path.lineTo(13, 8.5)
    path.cubicTo(18.5, 8.5, 18.5, 18, 13, 18)
    path.lineTo(8, 18)
    p.drawPath(path)


def _redo(p, fg, bg):
    p.translate(24, 0)
    p.scale(-1, 1)
    _undo(p, fg, bg)


def _copy(p, fg, bg):
    p.drawRoundedRect(QRectF(8, 3.5, 12, 13), 1.5, 1.5)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(4, 7.5, 12, 13), 1.5, 1.5)


def _save(p, fg, bg):
    p.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2)
    p.drawRect(QRectF(8, 4, 8, 6))
    p.drawRect(QRectF(7.5, 14, 9, 6))


def _saveas(p, fg, bg):
    p.drawRoundedRect(QRectF(3, 3, 15, 15), 2, 2)
    p.drawRect(QRectF(6.5, 3, 7.5, 5))
    p.drawRect(QRectF(6, 12, 8.5, 6))
    p.setPen(QPen(ACCENT, 2, Qt.SolidLine, Qt.RoundCap))
    _line(p, 15.5, 19, 21.5, 19)
    _line(p, 18.5, 16, 18.5, 22)


def _capture(p, fg, bg):  # viewfinder
    for pts in ((3, 8, 3, 3, 8, 3), (16, 3, 21, 3, 21, 8), (3, 16, 3, 21, 8, 21), (21, 16, 21, 21, 16, 21)):
        p.drawPolyline(_poly(*pts))
    p.setBrush(fg)
    p.drawEllipse(QPointF(12, 12), 2.2, 2.2)


def _screen(p, fg, bg):
    p.drawRoundedRect(QRectF(3, 4, 18, 12), 1.5, 1.5)
    _line(p, 12, 16, 12, 20)
    _line(p, 8, 20, 16, 20)


def _edit(p, fg, bg):  # pencil
    p.drawPolygon(_poly(4.5, 19.5, 5.5, 15, 15.5, 5, 19, 8.5, 9, 18.5))
    _line(p, 13.5, 7, 17, 10.5)


def _folder(p, fg, bg):
    p.drawPolygon(_poly(3, 6.5, 9, 6.5, 11, 9, 21, 9, 21, 19, 3, 19))


def _trash(p, fg, bg):
    _line(p, 4, 7, 20, 7)
    p.drawPolyline(_poly(9, 7, 9, 4.5, 15, 4.5, 15, 7))
    p.drawPolyline(_poly(6, 7, 7, 20, 17, 20, 18, 7))
    _line(p, 10, 10.5, 10, 16.5)
    _line(p, 14, 10.5, 14, 16.5)


def _settings(p, fg, bg):  # gear
    import math

    p.drawEllipse(QPointF(12, 12), 6.2, 6.2)
    p.drawEllipse(QPointF(12, 12), 2.4, 2.4)
    p.setPen(QPen(fg, 2.6, Qt.SolidLine, Qt.RoundCap))
    for i in range(8):
        a = i * math.pi / 4
        _line(p, 12 + 7.6 * math.cos(a), 12 + 7.6 * math.sin(a), 12 + 9.6 * math.cos(a), 12 + 9.6 * math.sin(a))


def _glyph(p, fg, text, bold=False, italic=False, serif=False):
    f = QFont("serif" if serif else "sans-serif")
    f.setPixelSize(19)
    f.setBold(bold)
    f.setItalic(italic)
    p.setFont(f)
    p.setPen(fg)
    p.drawText(QRectF(2, 1, 20, 22), Qt.AlignCenter, text)


def _bold(p, fg, bg):
    _glyph(p, fg, "B", bold=True)


def _italic(p, fg, bg):
    _glyph(p, fg, "I", italic=True, serif=True)


def _magnifier(p, plus: bool):
    p.drawEllipse(QPointF(10.5, 10.5), 6.5, 6.5)
    p.setPen(QPen(p.pen().color(), 2.4, Qt.SolidLine, Qt.RoundCap))
    _line(p, 15.4, 15.4, 20.5, 20.5)
    p.setPen(QPen(p.pen().color(), 1.8, Qt.SolidLine, Qt.RoundCap))
    _line(p, 7.5, 10.5, 13.5, 10.5)
    if plus:
        _line(p, 10.5, 7.5, 10.5, 13.5)


def _zoomin(p, fg, bg):
    _magnifier(p, True)


def _zoomout(p, fg, bg):
    _magnifier(p, False)


def _fit(p, fg, bg):  # corner brackets around a smaller picture: "fit the image in the window"
    for pts in ((3, 8, 3, 3, 8, 3), (16, 3, 21, 3, 21, 8), (3, 16, 3, 21, 8, 21), (21, 16, 21, 21, 16, 21)):
        p.drawPolyline(_poly(*pts))
    p.setBrush(fg)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(8, 8.5, 8, 7), 1, 1)


def _actual(p, fg, bg):  # "1:1"
    f = QFont("sans-serif")
    f.setPixelSize(11)
    f.setBold(True)
    p.setFont(f)
    p.setPen(fg)
    p.drawText(QRectF(0, 5, 24, 14), Qt.AlignCenter, "1:1")


def _sun(p, fg, bg):
    import math

    p.drawEllipse(QPointF(12, 12), 4.2, 4.2)
    for i in range(8):
        a = i * math.pi / 4
        _line(p, 12 + 7 * math.cos(a), 12 + 7 * math.sin(a), 12 + 9.6 * math.cos(a), 12 + 9.6 * math.sin(a))


def _moon(p, fg, bg):
    from PySide6.QtGui import QPainterPath

    outer = QPainterPath()
    outer.addEllipse(QRectF(4, 4, 16, 16))
    bite = QPainterPath()
    bite.addEllipse(QRectF(9.5, 1.5, 14, 14))
    p.setBrush(fg)
    p.drawPath(outer.subtracted(bite))


_DRAW = {
    "select": _select, "rect": _rect, "ellipse": _ellipse, "arrow": _arrow, "line": _linetool,
    "text": _text, "highlight": _highlight, "pixelate": _pixelate, "step": _step,
    "crop": _crop, "cutv": _cutv, "cuth": _cuth, "apply": _apply, "undo": _undo, "redo": _redo,
    "copy": _copy, "save": _save, "saveas": _saveas, "capture": _capture, "screen": _screen,
    "edit": _edit, "settings": _settings, "zoomin": _zoomin, "zoomout": _zoomout, "fit": _fit, "actual": _actual, "bold": _bold, "italic": _italic, "sun": _sun, "moon": _moon, "folder": _folder, "trash": _trash,
}
NAMES = tuple(_DRAW)
_SIZE = 96  # drawn large, scaled down smoothly by Qt for any toolbar size / DPI


def icon(name: str) -> QIcon:
    pal = QGuiApplication.palette()
    fg, bg = pal.color(QPalette.WindowText), pal.color(QPalette.Window)
    pm = QPixmap(_SIZE, _SIZE)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(_SIZE / 24, _SIZE / 24)
    p.setPen(QPen(fg, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    _DRAW[name](p, fg, bg)
    p.end()
    return QIcon(pm)  # Qt derives the greyed disabled look from this


def app_icon() -> QIcon:
    """The application icon (blue rounded square with white capture corners)."""
    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(4, 4)
    p.setBrush(QColor("#2f81f7"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 60, 60, 12, 12)
    p.setPen(QPen(Qt.white, 5, Qt.SolidLine, Qt.SquareCap))
    for x, y, dx, dy in ((16, 16, 1, 1), (48, 16, -1, 1), (16, 48, 1, -1), (48, 48, -1, -1)):
        p.drawLine(x, y, x + 12 * dx, y)
        p.drawLine(x, y, x, y + 12 * dy)
    p.end()
    return QIcon(pm)


def tag(action, name: str):
    """Give a QAction its icon and remember the name, so refresh() can redraw it after a theme change."""
    action.setProperty("icon_name", name)
    action.setIcon(icon(name))
    return action


def refresh():
    """Redraw every tagged action's icon with the current palette."""
    from PySide6.QtWidgets import QApplication

    seen = set()
    for w in QApplication.allWidgets():
        for a in w.actions():
            if id(a) in seen:
                continue
            seen.add(id(a))
            name = a.property("icon_name")
            if name:
                a.setIcon(icon(str(name)))


# -- toolbar icon size (Settings → Icon size) ------------------------------------------------

SIZES = {"small": 22, "medium": 28, "large": 36}
DEFAULT_SIZE = "medium"
SIZE_KEY = "appearance/icon_size"


def size_name() -> str:
    from PySide6.QtCore import QSettings

    v = str(QSettings("ScreenCapture", "ScreenCapture").value(SIZE_KEY, DEFAULT_SIZE))
    return v if v in SIZES else DEFAULT_SIZE


def save_size(name: str):
    from PySide6.QtCore import QSettings

    s = QSettings("ScreenCapture", "ScreenCapture")
    s.setValue(SIZE_KEY, name)
    s.sync()


def toolbar_pixels(name: str | None = None) -> int:
    return SIZES.get(name or size_name(), SIZES[DEFAULT_SIZE])


def apply_size(name: str | None = None):
    """Resize the icons of every open toolbar."""
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QApplication, QToolBar

    n = toolbar_pixels(name)
    for w in QApplication.allWidgets():
        if isinstance(w, QToolBar):
            w.setIconSize(QSize(n, n))
