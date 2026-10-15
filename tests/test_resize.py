import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QLineF, QRectF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox, QToolBar

import screencapture
from screencapture import editor as editor_module
from screencapture.about import build_about
from screencapture.editor import AddCommand, CanvasSizeCommand, EditorWindow, ResizeImageCommand
from screencapture.items import MOVABLE, ArrowItem, BoxItem
from screencapture.library import Library, LibraryWindow
from screencapture.resize_dialogs import MAX_SIDE, CanvasSizeDialog, ResizeImageDialog

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _editor(tmp_path, w=400, h=200, color="#3366cc"):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(color))
    ed = EditorWindow(img, Library(tmp_path))
    ed.show()
    return ed


def _box(ed, rect=(100, 50, 100, 50)):
    b = BoxItem(QRectF(*rect))
    b.setPen(ed.canvas.pen())
    b.setFlags(b.flags() | MOVABLE)
    ed.stack.push(AddCommand(ed.scene, b))
    return b


def _ok(dlg):
    return dlg.buttons.button(QDialogButtonBox.Ok).isEnabled()


# -- resize image: dialog ---------------------------------------------------------------------------------------------


def test_resize_dialog_keeps_aspect_ratio_and_percent(qapp):
    d = ResizeImageDialog(700, 450)
    assert d.size() == (700, 450) and not _ok(d)  # unchanged: nothing to do
    d.w.setValue(350)
    assert d.size() == (350, 225) and d.h.value() == 225 and _ok(d)
    d.unit.setCurrentIndex(1)  # percent
    assert d.w.value() == 50 and d.h.value() == 50 and d.w.suffix().strip() == "%"
    d.w.setValue(200)
    assert d.size() == (1400, 900)
    d.keep.setChecked(False)
    d.h.setValue(100)  # independent height now
    assert d.size() == (1400, 450)
    d.unit.setCurrentIndex(0)
    assert d.w.value() == 1400 and d.h.value() == 450


def test_resize_dialog_refuses_huge_sizes(qapp):
    d = ResizeImageDialog(700, 450)
    d.w.setValue(MAX_SIDE)  # 20000 x 12857 px = 257 megapixels
    assert not _ok(d) and "too large" in d.info.text()
    d.w.setValue(3000)
    assert _ok(d)


# -- resize image: command --------------------------------------------------------------------------------------------


def test_resize_image_scales_picture_and_annotations_and_undoes(qapp, tmp_path):
    ed = _editor(tmp_path)
    box = _box(ed)
    arrow = ArrowItem(QLineF(20, 20, 120, 20), ed.canvas.pen())
    arrow.setFlags(arrow.flags() | MOVABLE)
    ed.stack.push(AddCommand(ed.scene, arrow))
    c0, a0 = box.sceneBoundingRect().center(), arrow.sceneBoundingRect().center()
    ed.stack.push(ResizeImageCommand(ed.scene, 200, 100))  # half size
    assert ed.image().size().toTuple() == (200, 100)
    assert box.scale() == pytest.approx(0.5)
    assert box.sceneBoundingRect().center().x() == pytest.approx(c0.x() / 2) and box.sceneBoundingRect().center().y() == pytest.approx(c0.y() / 2)
    assert arrow.sceneBoundingRect().center().x() == pytest.approx(a0.x() / 2)
    ed.stack.undo()
    assert ed.image().size().toTuple() == (400, 200)
    assert box.scale() == pytest.approx(1) and box.sceneBoundingRect().center() == c0
    ed.stack.redo()
    assert ed.image().size().toTuple() == (200, 100)


def test_resize_image_non_uniform_squashes_the_picture_not_the_shapes(qapp, tmp_path):
    ed = _editor(tmp_path)
    box = _box(ed)
    c0 = box.sceneBoundingRect().center()
    ed.stack.push(ResizeImageCommand(ed.scene, 800, 200))  # twice as wide, same height
    assert ed.image().size().toTuple() == (800, 200)
    assert box.sceneBoundingRect().center().x() == pytest.approx(c0.x() * 2)  # position follows the image...
    assert box.sceneBoundingRect().center().y() == pytest.approx(c0.y())
    assert box.scale() == pytest.approx(2 ** 0.5)  # ...the shape is scaled uniformly (average factor)
    ed.stack.undo()  # here positions really move, so undo has to put them back exactly
    assert box.sceneBoundingRect().center() == c0 and box.scale() == pytest.approx(1) and box.pos().x() == 0


# -- canvas size: dialog and command ----------------------------------------------------------------------------------


def test_canvas_dialog_anchor_and_values(qapp):
    d = CanvasSizeDialog(400, 200, QColor("#ff0000"))
    assert d.anchor() == (1, 1) and not _ok(d)  # center, unchanged
    d.w.setValue(600)
    d.h.setValue(300)
    assert _ok(d)
    d.group.button(0).setChecked(True)  # top-left
    assert d.anchor() == (0, 0)
    d.group.button(8).setChecked(True)  # bottom-right
    w, h, anchor, color = d.values()
    assert (w, h, anchor) == (600, 300, (2, 2)) and color == QColor("#ff0000")
    d.w.setValue(MAX_SIDE + 1 if MAX_SIDE < d.w.maximum() else d.w.maximum())
    d.h.setValue(d.h.maximum())
    assert not _ok(d)


@pytest.mark.parametrize(
    "anchor,offset",
    [((0, 0), (0, 0)), ((1, 1), (100, 50)), ((2, 2), (200, 100)), ((2, 0), (200, 0)), ((0, 2), (0, 100))],
)
def test_canvas_grow_places_image_by_anchor_and_fills_new_area(qapp, tmp_path, anchor, offset):
    ed = _editor(tmp_path)
    box = _box(ed, (10, 10, 40, 40))
    before = box.sceneBoundingRect().center()
    ed.stack.push(CanvasSizeCommand(ed.scene, 600, 300, anchor, QColor("#ff0000")))
    img = ed.image()
    assert img.size().toTuple() == (600, 300)
    ox, oy = offset
    assert img.pixelColor(ox + 200, oy + 100) == QColor("#3366cc")  # original picture, moved by the anchor
    corners = [(0, 0), (599, 0), (0, 299), (599, 299)]
    assert sum(img.pixelColor(x, y) == QColor("#ff0000") for x, y in corners) == (4 - sum(
        ox <= x < ox + 400 and oy <= y < oy + 200 for x, y in corners))  # new area is the fill color
    assert box.sceneBoundingRect().center().x() == pytest.approx(before.x() + ox)  # annotations moved along
    assert box.sceneBoundingRect().center().y() == pytest.approx(before.y() + oy)
    ed.stack.undo()
    assert ed.image().size().toTuple() == (400, 200) and box.sceneBoundingRect().center() == before


def test_canvas_shrink_cuts_off_by_anchor(qapp, tmp_path):
    ed = _editor(tmp_path)
    for x in range(200, 400):  # right half red
        for y in range(200):
            ed.scene.base_image.setPixelColor(x, y, QColor("#ff0000"))
    from PySide6.QtGui import QPixmap

    ed.scene.set_base(QPixmap.fromImage(ed.scene.base_image))
    ed.stack.push(CanvasSizeCommand(ed.scene, 200, 100, (2, 2), QColor("white")))  # keep the bottom-right part
    img = ed.image()
    assert img.size().toTuple() == (200, 100)
    assert img.pixelColor(10, 10) == QColor("#ff0000") and img.pixelColor(190, 90) == QColor("#ff0000")
    ed.stack.undo()
    assert ed.image().size().toTuple() == (400, 200)


# -- editor integration ------------------------------------------------------------------------------------------------


def test_toolbar_actions_open_the_dialogs_and_apply(qapp, tmp_path, monkeypatch):
    ed = _editor(tmp_path)
    actions = {a.toolTip(): a for tb in ed.findChildren(QToolBar) for a in tb.actions() if a.toolTip()}
    resize = next(a for t, a in actions.items() if t.startswith("Resize image"))
    canvas = next(a for t, a in actions.items() if t.startswith("Canvas size"))
    assert not resize.icon().isNull() and not canvas.icon().isNull()
    assert resize.shortcut().toString() == "Ctrl+R" and canvas.shortcut().toString() == "Ctrl+Shift+R"

    class FakeResize:
        def __init__(self, w, h, parent=None):
            pass

        def exec(self):
            return True

        def size(self):
            return 100, 50

    class FakeCanvas:
        def __init__(self, w, h, fill, parent=None):
            pass

        def exec(self):
            return True

        def values(self):
            return 500, 400, (1, 1), QColor("#00ff00")

    monkeypatch.setattr(editor_module, "ResizeImageDialog", FakeResize)
    monkeypatch.setattr(editor_module, "CanvasSizeDialog", FakeCanvas)
    resize.trigger()
    assert ed.image().size().toTuple() == (100, 50)
    canvas.trigger()
    assert ed.image().size().toTuple() == (500, 400)
    ed.stack.undo()
    ed.stack.undo()
    assert ed.image().size().toTuple() == (400, 200)


# -- about and licence -------------------------------------------------------------------------------------------------


def test_about_box_text(qapp):
    box = build_about()
    text = box.text()
    assert screencapture.__version__ in text
    assert "Free software" in text and "MIT" in text and "Janusz Tylek" in text
    assert "https://github.com/jtylek/ScreenCapture" in text
    assert any(b.text() == "Open GitHub page" for b in box.buttons())
    assert box.button(QMessageBox.Close) is not None  # there is a way to close it


def test_library_has_about_button_and_license_file_exists(qapp, tmp_path):
    lw = LibraryWindow(Library(tmp_path))
    about = next(a for tb in lw.findChildren(QToolBar) for a in tb.actions() if a.text() == "About")
    assert not about.icon().isNull()
    lic = (ROOT / "LICENSE").read_text()
    assert lic.startswith("MIT License") and "Janusz Tylek" in lic
