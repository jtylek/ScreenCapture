import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QKeySequence, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolBar

from screencapture.editor import Canvas, EditorWindow
from screencapture.library import Library


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _editor(tmp_path, w=700, h=450):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("#9bb"))
    ed = EditorWindow(img, Library(tmp_path))
    ed.show()
    QApplication.processEvents()
    QApplication.processEvents()
    return ed


def test_zoom_buttons_label_and_limits(qapp, tmp_path):
    ed = _editor(tmp_path)
    c = ed.canvas
    c.set_zoom_percent(100)
    assert c.zoom_percent() == pytest.approx(100)
    assert ed.zoom_label.text() == "100%"
    c.zoom_by(1.25)
    assert c.zoom_percent() == pytest.approx(125) and ed.zoom_label.text() == "125%"
    c.zoom_by(1 / 1.25)
    c.zoom_by(1 / 1.25)
    assert c.zoom_percent() == pytest.approx(80)
    c.set_zoom_percent(1e9)
    assert c.zoom_percent() == pytest.approx(Canvas.MAX_ZOOM)
    c.set_zoom_percent(0.0001)
    assert c.zoom_percent() == pytest.approx(Canvas.MIN_ZOOM)
    c.zoom_actual()
    assert c.zoom_percent() == pytest.approx(100)


def test_toolbar_zoom_actions_have_icons_tooltips_shortcuts(qapp, tmp_path):
    ed = _editor(tmp_path)
    actions = {a.toolTip(): a for tb in ed.findChildren(QToolBar) for a in tb.actions() if a.toolTip()}
    names = [t for t in actions if t.startswith(("Zoom", "Fit", "Actual"))]
    assert len(names) == 4, names
    assert all(not actions[t].icon().isNull() for t in names)
    shortcuts = {s.toString() for a in actions.values() for s in a.shortcuts()}
    zoom_in_keys = {s.toString() for s in QKeySequence.keyBindings(QKeySequence.ZoomIn)}
    assert {"Ctrl+0", "Ctrl+1", "Ctrl+="} <= shortcuts and zoom_in_keys & shortcuts  # the platform's own Zoom In key too
    # the buttons really zoom
    c = ed.canvas
    c.set_zoom_percent(100)
    actions[next(t for t in names if t.startswith("Zoom in"))].trigger()
    assert c.zoom_percent() > 100
    actions[next(t for t in names if t.startswith("Actual"))].trigger()
    assert c.zoom_percent() == pytest.approx(100)


def test_fit_shows_whole_image_and_follows_window_size(qapp, tmp_path):
    ed = _editor(tmp_path, 3000, 2000)  # much larger than the window
    c = ed.canvas
    c.zoom_fit()
    assert c.fit_mode and c.zoom_percent() < 100
    vis = c.mapToScene(c.viewport().rect()).boundingRect()
    assert vis.contains(ed.scene.sceneRect().adjusted(1, 1, -1, -1))  # all of it is visible
    before = c.zoom_percent()
    ed.resize(ed.width() + 300, ed.height() + 200)
    QApplication.processEvents()
    QApplication.processEvents()
    assert c.fit_mode and c.zoom_percent() > before  # still "fit" after the window grew
    c.zoom_by(1.25)  # a manual zoom leaves fit mode
    assert not c.fit_mode


def test_hundred_percent_means_real_pixels_on_a_scaled_display(qapp, tmp_path, monkeypatch):
    ed = _editor(tmp_path)
    monkeypatch.setattr(Canvas, "_dpr", lambda self: 1.5)  # a 150% display
    ed.canvas.set_zoom_percent(100)
    assert ed.canvas.transform().m11() == pytest.approx(1 / 1.5)  # 1 image px = 1 physical px
    assert ed.canvas.zoom_percent() == pytest.approx(100)


def test_pan_with_middle_button_and_space(qapp, tmp_path):
    ed = _editor(tmp_path, 1600, 1000)
    c = ed.canvas
    c.set_zoom_percent(400)  # image is now far bigger than the window
    hb, vb = c.horizontalScrollBar(), c.verticalScrollBar()
    assert hb.maximum() > 0 and vb.maximum() > 0
    hb.setValue(hb.maximum() // 2)
    vb.setValue(vb.maximum() // 2)
    h0, v0 = hb.value(), vb.value()
    vp = c.viewport()
    # middle button drag: content follows the mouse (dragging left/up scrolls right/down)
    QTest.mousePress(vp, Qt.MiddleButton, pos=QPoint(200, 200))
    QTest.mouseMove(vp, QPoint(150, 170))
    QTest.mouseRelease(vp, Qt.MiddleButton, pos=QPoint(150, 170))
    assert hb.value() - h0 == 50 and vb.value() - v0 == 30
    # Space + left drag does the same, and doesn't draw or select anything
    h1, v1 = hb.value(), vb.value()
    c.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier))
    QTest.mousePress(vp, Qt.LeftButton, pos=QPoint(200, 200))
    QTest.mouseMove(vp, QPoint(230, 240))
    QTest.mouseRelease(vp, Qt.LeftButton, pos=QPoint(230, 240))
    c.keyReleaseEvent(QKeyEvent(QEvent.KeyRelease, Qt.Key_Space, Qt.NoModifier))
    assert hb.value() - h1 == -30 and vb.value() - v1 == -40
    assert not ed.scene.annotations()


def test_ctrl_wheel_zooms_plain_wheel_scrolls(qapp, tmp_path):
    ed = _editor(tmp_path, 1600, 1000)
    c = ed.canvas
    c.set_zoom_percent(200)
    p = QPointF(100, 100)

    def wheel(delta, mods):
        return QWheelEvent(p, c.viewport().mapToGlobal(p), QPoint(0, 0), QPoint(0, delta), Qt.NoButton, mods, Qt.NoScrollPhase, False)

    before = c.zoom_percent()
    c.wheelEvent(wheel(120, Qt.ControlModifier))
    assert c.zoom_percent() == pytest.approx(before * 1.15)
    c.wheelEvent(wheel(-120, Qt.ControlModifier))
    assert c.zoom_percent() == pytest.approx(before, rel=1e-6)
    v = c.verticalScrollBar().value()
    c.verticalScrollBar().setValue(50)
    c.wheelEvent(wheel(-120, Qt.NoModifier))  # plain wheel scrolls, zoom unchanged
    assert c.zoom_percent() == pytest.approx(before, rel=1e-6)
