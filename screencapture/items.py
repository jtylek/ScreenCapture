"""Annotation graphics items."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)

MOVABLE = QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable


def _stroke(path: QPainterPath, width: float) -> QPainterPath:
    s = QPainterPathStroker()
    s.setWidth(max(width, 1.0) + 8)  # a little slack so thin lines are easy to grab
    return s.createStroke(path)


def _selection_outline(painter: QPainter, rect: QRectF):
    painter.setPen(QPen(QColor("#2f81f7"), 1, Qt.DashLine))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(rect)


class BoxItem(QGraphicsRectItem):
    """Rectangle outline; only the outline is clickable so boxes don't block items beneath."""

    def shape(self):
        p = QPainterPath()
        p.addRect(self.rect())
        return _stroke(p, self.pen().widthF())

    def paint(self, painter, option, widget=None):
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect())
        if self.isSelected():
            _selection_outline(painter, self.rect().adjusted(-4, -4, 4, 4))


class OvalItem(QGraphicsEllipseItem):
    def shape(self):
        p = QPainterPath()
        p.addEllipse(self.rect())
        return _stroke(p, self.pen().widthF())

    def paint(self, painter, option, widget=None):
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawEllipse(self.rect())
        if self.isSelected():
            _selection_outline(painter, self.rect().adjusted(-4, -4, 4, 4))


class HighlightItem(QGraphicsRectItem):
    def paint(self, painter, option, widget=None):
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())
        if self.isSelected():
            _selection_outline(painter, self.rect())


class ArrowItem(QGraphicsLineItem):
    def __init__(self, line, pen: QPen, head: bool = True):
        super().__init__(line)
        pen = QPen(pen)
        pen.setCapStyle(Qt.RoundCap)
        self.setPen(pen)
        self.head = head

    def _size(self) -> float:
        return max(12.0, self.pen().widthF() * 4)

    def _head_polygon(self) -> QPolygonF:
        line = self.line()
        if not self.head or line.length() < 1:
            return QPolygonF()
        size = min(self._size(), line.length())
        ang = math.atan2(line.dy(), line.dx())
        tip = line.p2()
        a = QPointF(math.cos(ang - math.pi / 7), math.sin(ang - math.pi / 7)) * size
        b = QPointF(math.cos(ang + math.pi / 7), math.sin(ang + math.pi / 7)) * size
        return QPolygonF([tip, tip - a, tip - b])

    def _body(self):
        line = self.line()
        if self.head and line.length() > 1:
            line.setLength(max(line.length() - self._size() * 0.8, 0.1))
        return line

    def shape(self):
        p = QPainterPath()
        p.moveTo(self.line().p1())
        p.lineTo(self.line().p2())
        s = _stroke(p, self.pen().widthF())
        head = QPainterPath()
        head.addPolygon(self._head_polygon())
        return s.united(head)

    def boundingRect(self):
        return self.shape().boundingRect().adjusted(-2, -2, 2, 2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.pen())
        painter.drawLine(self._body())
        if self.head:
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.pen().color())
            painter.drawPolygon(self._head_polygon())
        if self.isSelected():
            _selection_outline(painter, self.boundingRect())


class StepItem(QGraphicsItem):
    """Numbered circle for step-by-step instructions."""

    D = 30.0

    def __init__(self, number: int, color: QColor):
        super().__init__()
        self.number, self.color = number, QColor(color)
        self.setFlags(MOVABLE)

    def boundingRect(self):
        r = self.D / 2 + 3
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.D / 2
        painter.setPen(QPen(Qt.white, 2))
        painter.setBrush(self.color)
        painter.drawEllipse(QRectF(-r, -r, self.D, self.D))
        f = QFont()
        f.setBold(True)
        f.setPixelSize(int(self.D * 0.55))
        painter.setFont(f)
        painter.setPen(Qt.white)
        painter.drawText(QRectF(-r, -r, self.D, self.D), Qt.AlignCenter, str(self.number))
        if self.isSelected():
            _selection_outline(painter, self.boundingRect())


class PixelateItem(QGraphicsRectItem):
    """Hides what is underneath by pixelating the *base screenshot* in its rectangle."""

    BLOCK = 10

    def paint(self, painter, option, widget=None):
        scene = self.scene()
        rect = self.rect()
        base = getattr(scene, "base_image", None)
        if base is not None:
            src = self.mapRectToScene(rect).toRect().intersected(base.rect())
            if src.width() > 0 and src.height() > 0:
                small = base.copy(src).scaled(
                    max(1, src.width() // self.BLOCK), max(1, src.height() // self.BLOCK), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                )
                big = small.scaled(src.width(), src.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
                painter.drawImage(self.mapRectFromScene(QRectF(src)), big)
        if self.isSelected():
            _selection_outline(painter, rect)


class TextItem(QGraphicsTextItem):
    def __init__(self, color: QColor, font: QFont, commit_cb):
        super().__init__()
        self.setFont(font)
        self.setDefaultTextColor(color)
        self.setFlags(MOVABLE | QGraphicsItem.ItemIsFocusable)
        self._commit_cb = commit_cb
        self._committed = False

    def start_edit(self):
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus(Qt.MouseFocusReason)

    def mouseDoubleClickEvent(self, e):
        self.start_edit()
        super().mouseDoubleClickEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        c = self.textCursor()
        c.clearSelection()
        self.setTextCursor(c)
        if self.toPlainText().strip() == "":
            if self.scene() is not None:
                self.scene().removeItem(self)
        else:
            self.setSelected(True)  # so the font controls act on the text that was just typed
            if not self._committed:
                self._committed = True
                self._commit_cb(self)

    def paint(self, painter, option, widget=None):
        # draw only a custom outline when selected (Qt's default is a heavy dotted box)
        option.state &= ~option.state.State_Selected
        super().paint(painter, option, widget)
        if self.isSelected():
            _selection_outline(painter, self.boundingRect())


class CropItem(QGraphicsItem):
    """Crop rubber band: dims everything outside the chosen rectangle."""

    def __init__(self, rect: QRectF, mode: str = "crop"):
        super().__init__()
        self._rect = QRectF(rect)
        self.mode = mode  # "crop", or "cutv" / "cuth": a strip to cut out
        self.setZValue(10_000)

    def rect(self) -> QRectF:
        return QRectF(self._rect)

    def set_rect(self, r: QRectF):
        self.prepareGeometryChange()
        self._rect = r.normalized()
        self.update()

    def boundingRect(self):
        return self.scene().sceneRect() if self.scene() else self._rect

    def _paint_cut(self, painter):
        red = QColor(225, 45, 45)
        r = self._rect
        painter.fillRect(r, QColor(225, 45, 45, 60))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(225, 45, 45, 140), Qt.BDiagPattern))
        painter.drawRect(r)
        painter.setPen(QPen(red, 1.5, Qt.DashLine))
        if self.mode == "cutv":
            painter.drawLine(r.topLeft(), r.bottomLeft())
            painter.drawLine(r.topRight(), r.bottomRight())
        else:
            painter.drawLine(r.topLeft(), r.topRight())
            painter.drawLine(r.bottomLeft(), r.bottomRight())

    def paint(self, painter, option, widget=None):
        if self.mode != "crop":
            return self._paint_cut(painter)
        outside = QPainterPath()
        outside.addRect(self.boundingRect())
        inside = QPainterPath()
        inside.addRect(self._rect)
        painter.fillPath(outside.subtracted(inside), QColor(0, 0, 0, 140))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(Qt.white, 1))
        painter.drawRect(self._rect)
        painter.setPen(QPen(Qt.black, 1, Qt.DashLine))
        painter.drawRect(self._rect)
