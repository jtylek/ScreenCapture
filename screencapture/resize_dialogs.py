"""Dialogs for Resize image and Canvas size."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

MAX_SIDE = 20000  # pixels
MAX_PIXELS = 120_000_000  # keeps memory use sane


def too_big(w: int, h: int) -> bool:
    return w > MAX_SIDE or h > MAX_SIDE or w * h > MAX_PIXELS


class ResizeImageDialog(QDialog):
    """New size of the whole image, in pixels or percent, optionally keeping the aspect ratio."""

    def __init__(self, width: int, height: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resize image")
        self._w0, self._h0 = width, height
        self._tw, self._th = width, height  # the target size in pixels is the source of truth

        self.unit = QComboBox()
        self.unit.addItems(["Pixels", "Percent"])
        self.w = QSpinBox()
        self.h = QSpinBox()
        self.keep = QCheckBox("Keep aspect ratio")
        self.keep.setChecked(True)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Current size:", QLabel(f"{width} × {height} px"))
        form.addRow("Unit:", self.unit)
        form.addRow("Width:", self.w)
        form.addRow("Height:", self.h)
        form.addRow("", self.keep)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.info)
        lay.addWidget(self.buttons)

        self._configure_spins()
        self._refresh()
        self.unit.currentIndexChanged.connect(lambda _: (self._configure_spins(), self._refresh()))
        self.w.valueChanged.connect(self._width_edited)
        self.h.valueChanged.connect(self._height_edited)
        self.keep.toggled.connect(lambda on: on and self._width_edited(self.w.value()))

    # -- units ---------------------------------------------------------------------------------

    def _percent(self) -> bool:
        return self.unit.currentIndex() == 1

    def _to_px(self, value: int, base: int) -> int:
        return max(1, round(value * base / 100)) if self._percent() else value

    def _configure_spins(self):
        for spin in (self.w, self.h):
            spin.blockSignals(True)
            spin.setRange(1, 2000 if self._percent() else MAX_SIDE)
            spin.setSuffix(" %" if self._percent() else " px")
            spin.blockSignals(False)

    def _refresh(self):
        for spin, px, base in ((self.w, self._tw, self._w0), (self.h, self._th, self._h0)):
            spin.blockSignals(True)
            spin.setValue(max(1, round(px * 100 / base)) if self._percent() else px)
            spin.blockSignals(False)
        ok = self.buttons.button(QDialogButtonBox.Ok)
        pct = f"{self._tw * 100 / self._w0:.0f}% × {self._th * 100 / self._h0:.0f}%"
        if too_big(self._tw, self._th):
            self.info.setText(f"New size: {self._tw} × {self._th} px — too large (limit {MAX_SIDE} px per side, "
                              f"{MAX_PIXELS // 1_000_000} megapixels).")
            ok.setEnabled(False)
        else:
            self.info.setText(f"New size: {self._tw} × {self._th} px ({pct})")
            ok.setEnabled((self._tw, self._th) != (self._w0, self._h0))

    def _width_edited(self, value: int):
        self._tw = self._to_px(value, self._w0)
        if self.keep.isChecked():
            self._th = max(1, round(self._tw * self._h0 / self._w0))
        self._refresh()

    def _height_edited(self, value: int):
        self._th = self._to_px(value, self._h0)
        if self.keep.isChecked():
            self._tw = max(1, round(self._th * self._w0 / self._h0))
        self._refresh()

    def size(self) -> tuple[int, int]:
        return self._tw, self._th


class CanvasSizeDialog(QDialog):
    """New canvas size, where the existing image sits in it (anchor), and the color of the new area."""

    ARROWS = ["↖", "↑", "↗", "←", "●", "→", "↙", "↓", "↘"]

    def __init__(self, width: int, height: int, fill: QColor | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Canvas size")
        self._w0, self._h0 = width, height
        self._fill = QColor(fill or "#ffffff")

        self.w = QSpinBox()
        self.h = QSpinBox()
        for spin, v in ((self.w, width), (self.h, height)):
            spin.setRange(1, MAX_SIDE)
            spin.setSuffix(" px")
            spin.setValue(v)
            spin.valueChanged.connect(self._refresh)

        grid_box = QWidget()
        grid = QGridLayout(grid_box)
        grid.setSpacing(2)
        grid.setContentsMargins(0, 0, 0, 0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, arrow in enumerate(self.ARROWS):
            b = QToolButton()
            b.setText(arrow)
            b.setCheckable(True)
            b.setFixedSize(34, 34)
            b.setToolTip("Where the current image stays in the new canvas")
            self.group.addButton(b, i)
            grid.addWidget(b, i // 3, i % 3)
        self.group.button(4).setChecked(True)

        self.color_button = QPushButton()
        self.color_button.setToolTip("Color of the added area")
        self.color_button.clicked.connect(self._pick_color)
        self._paint_color()
        self.info = QLabel()
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Current size:", QLabel(f"{width} × {height} px"))
        form.addRow("New width:", self.w)
        form.addRow("New height:", self.h)
        form.addRow("Image position:", grid_box)
        form.addRow("New area color:", self.color_button)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.info)
        lay.addWidget(self.buttons)
        self._refresh()

    def _paint_color(self):
        pm = QPixmap(48, 18)
        pm.fill(self._fill)
        self.color_button.setIcon(pm)
        self.color_button.setText(self._fill.name())

    def _pick_color(self):
        c = QColorDialog.getColor(self._fill, self, "Color of the added area")
        if c.isValid():
            self._fill = c
            self._paint_color()

    def _refresh(self, *_):
        nw, nh = self.w.value(), self.h.value()
        ok = self.buttons.button(QDialogButtonBox.Ok)
        if too_big(nw, nh):
            self.info.setText(f"Too large (limit {MAX_SIDE} px per side, {MAX_PIXELS // 1_000_000} megapixels).")
            ok.setEnabled(False)
            return
        grow = nw > self._w0 or nh > self._h0
        shrink = nw < self._w0 or nh < self._h0
        self.info.setText(
            "Added area is filled with the color." if grow and not shrink
            else "The image is cut off at the new edges." if shrink and not grow
            else "Added area is filled; parts outside the new canvas are cut off." if grow and shrink
            else "Same size."
        )
        ok.setEnabled((nw, nh) != (self._w0, self._h0))

    def anchor(self) -> tuple[int, int]:
        i = self.group.checkedId()
        return i % 3, i // 3  # (0 left / 1 center / 2 right, 0 top / 1 middle / 2 bottom)

    def values(self) -> tuple[int, int, tuple[int, int], QColor]:
        return self.w.value(), self.h.value(), self.anchor(), QColor(self._fill)
