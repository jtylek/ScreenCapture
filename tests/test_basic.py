import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from screencapture.editor import AddCommand, CropCommand, EditorWindow
from screencapture.items import MOVABLE, ArrowItem, BoxItem, PixelateItem
from screencapture.library import Library


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _img(w=200, h=100, color="#3366cc"):
    i = QImage(w, h, QImage.Format_RGB32)
    i.fill(QColor(color))
    return i


def test_library_add_list_delete_prune(qapp, tmp_path):
    lib = Library(tmp_path, max_items=2)
    paths = [lib.add(_img()) for _ in range(3)]
    assert len(set(paths)) == 3
    assert len(lib.entries()) == 2  # pruned oldest
    assert not lib.thumbnail(lib.entries()[0]).isNull()
    lib.delete(lib.entries()[0])
    assert len(lib.entries()) == 1


def test_annotate_undo_and_flatten(qapp, tmp_path):
    lib = Library(tmp_path)
    ed = EditorWindow(_img(), lib, lib.add(_img()))
    box = BoxItem(QRectF(10, 10, 50, 40))
    box.setPen(ed.canvas.pen())
    ed.stack.push(AddCommand(ed.scene, box))
    out = ed.image()
    assert out.size() == _img().size()
    assert out.pixelColor(10, 30) != QColor("#3366cc")  # stroke drawn on the left edge
    ed.stack.undo()
    assert ed.image().pixelColor(10, 30) == QColor("#3366cc")


def test_crop_moves_annotations_and_undoes(qapp, tmp_path):
    lib = Library(tmp_path)
    ed = EditorWindow(_img(), lib)
    arrow = ArrowItem(__import__("PySide6.QtCore", fromlist=["QLineF"]).QLineF(60, 60, 100, 60), ed.canvas.pen())
    ed.stack.push(AddCommand(ed.scene, arrow))
    from PySide6.QtCore import QRect

    ed.stack.push(CropCommand(ed.scene, QRect(50, 50, 100, 40)))
    assert ed.image().size().toTuple() == (100, 40)
    assert arrow.pos() == QPointF(-50, -50)
    ed.stack.undo()
    assert ed.image().size().toTuple() == (200, 100)
    assert arrow.pos() == QPointF(0, 0)


def test_pixelate_renders(qapp, tmp_path):
    base = _img()
    for x in range(100):
        for y in range(100):
            base.setPixelColor(x, y, QColor("white") if (x // 3 + y // 3) % 2 else QColor("black"))
    ed = EditorWindow(base, Library(tmp_path))
    px = PixelateItem(QRectF(0, 0, 100, 100))
    ed.stack.push(AddCommand(ed.scene, px))
    out = ed.image()
    assert out.pixelColor(50, 50).lightness() not in (0, 255)  # averaged away from pure black/white


def test_all_icons_draw(qapp):
    from screencapture import icons

    for name in icons.NAMES:
        pm = icons.icon(name).pixmap(24, 24)
        assert not pm.isNull()
        img = pm.toImage()
        assert any(img.pixelColor(x, y).alpha() for x in range(img.width()) for y in range(img.height())), name


def _striped(w=100, h=60):
    """Left 40px red, middle 20px green, right 40px blue."""
    i = QImage(w, h, QImage.Format_RGB32)
    for x in range(w):
        c = QColor("red") if x < 40 else QColor("lime") if x < 60 else QColor("blue")
        for y in range(h):
            i.setPixelColor(x, y, c)
    return i


def test_cut_vertical_strip(qapp, tmp_path):
    from PySide6.QtCore import QLineF

    from screencapture.editor import CutCommand

    ed = EditorWindow(_striped(), Library(tmp_path))
    gone = BoxItem(QRectF(42, 5, 10, 10))  # inside the strip -> removed
    kept = BoxItem(QRectF(70, 5, 10, 10))  # right of it -> shifts left by 20
    for it in (gone, kept):
        ed.stack.push(AddCommand(ed.scene, it))
    ed.stack.push(CutCommand(ed.scene, True, 40, 60))
    out = ed.image()
    assert out.size().toTuple() == (80, 60)
    assert out.pixelColor(10, 30) == QColor("red") and out.pixelColor(70, 30) == QColor("blue")
    assert not any(out.pixelColor(x, 30) == QColor("lime") for x in range(80))
    assert gone.scene() is None and kept.pos() == QPointF(-20, 0)
    ed.stack.undo()
    assert ed.image().size().toTuple() == (100, 60)
    assert gone.scene() is ed.scene and kept.pos() == QPointF(0, 0)


def test_cut_horizontal_strip_via_canvas(qapp, tmp_path):
    ed = EditorWindow(_striped(60, 100), Library(tmp_path))
    ed.canvas.set_tool("cuth")
    from screencapture.items import CropItem

    ed.canvas._crop = CropItem(QRectF(0, 30, 60, 20), "cuth")
    ed.scene.addItem(ed.canvas._crop)
    ed.canvas.apply_crop()
    assert ed.image().size().toTuple() == (60, 80)
    # cutting the whole image is refused
    ed.canvas._crop = CropItem(QRectF(0, 0, 60, 80), "cuth")
    ed.scene.addItem(ed.canvas._crop)
    ed.canvas.apply_crop()
    assert ed.image().size().toTuple() == (60, 80)


def test_theme_switch_redraws_icons_and_persists(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QAction, QPalette

    from screencapture import icons, theme

    theme.init(qapp)
    a = icons.tag(QAction("x"), "rect")
    w = __import__("PySide6.QtWidgets", fromlist=["QWidget"]).QWidget()
    w.addAction(a)

    def ink():  # brightest opaque pixel of the icon
        img = a.icon().pixmap(48, 48).toImage()
        return max(img.pixelColor(x, y).lightness() for x in range(48) for y in range(48) if img.pixelColor(x, y).alpha() > 200)

    theme.apply(qapp, "dark")
    assert theme.is_dark(qapp) and ink() > 180
    theme.apply(qapp, "light")
    assert not theme.is_dark(qapp) and ink() < 80
    theme.save("dark")
    theme.apply(qapp, "dark")
    assert theme.saved() == "dark"
    theme.toggle(qapp)  # dark -> light, remembered
    assert theme.saved() == "light" and not theme.is_dark(qapp)
    theme.save("system")
    theme.apply(qapp, "system")


def test_autostart_linux_desktop_file(qapp, tmp_path, monkeypatch):
    from screencapture import autostart

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(autostart, "_platform", lambda: "linux")
    assert not autostart.is_enabled()
    assert autostart.set_enabled(True) is None and autostart.is_enabled()
    text = (tmp_path / "autostart" / "screencapture.desktop").read_text()
    assert "Exec=" in text and text.split("Exec=")[1].splitlines()[0].endswith("--tray")
    assert autostart.set_enabled(False) is None and not autostart.is_enabled()
    (tmp_path / "autostart").mkdir(exist_ok=True)
    (tmp_path / "autostart" / "screencapture.desktop").write_text("[Desktop Entry]\nHidden=true\n")
    assert not autostart.is_enabled()  # a disabled entry counts as off


def test_autostart_windows_registry(qapp, monkeypatch):
    import sys
    import types

    from screencapture import autostart

    store = {}

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fake = types.SimpleNamespace(
        HKEY_CURRENT_USER=1, KEY_QUERY_VALUE=1, KEY_SET_VALUE=2, REG_SZ=1,
        OpenKey=lambda root, sub, res, acc: Key(),
        SetValueEx=lambda k, n, r, t, v: store.__setitem__(n, v),
        QueryValueEx=lambda k, n: (store[n], 1) if n in store else (_ for _ in ()).throw(FileNotFoundError()),
        DeleteValue=lambda k, n: store.pop(n) if n in store else (_ for _ in ()).throw(FileNotFoundError()),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake)
    monkeypatch.setattr(autostart, "_platform", lambda: "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\ScreenCapture\ScreenCapture.exe")
    assert not autostart.is_enabled()
    assert autostart.set_enabled(True) is None
    assert store["ScreenCapture"] == r'"C:\Program Files\ScreenCapture\ScreenCapture.exe" --tray'
    assert autostart.is_enabled()
    assert autostart.set_enabled(False) is None and not autostart.is_enabled()
    assert autostart.set_enabled(False) is None  # already off: no error


def test_select_and_delete_objects(qapp, tmp_path):
    from PySide6.QtCore import QPoint

    ed = EditorWindow(_img(400, 300), Library(tmp_path))
    ed.show()
    items = [BoxItem(QRectF(10 + 60 * i, 10, 40, 40)) for i in range(3)]
    for it in items:
        it.setPen(ed.canvas.pen())
        it.setFlags(it.flags() | MOVABLE)
        ed.stack.push(AddCommand(ed.scene, it))
    assert not ed.delete_action.isEnabled()
    items[0].setSelected(True)
    items[2].setSelected(True)
    assert ed.delete_action.isEnabled()
    ed.delete_action.trigger()  # toolbar button
    assert [i.scene() is ed.scene for i in items] == [False, True, False]
    ed.stack.undo()
    assert all(i.scene() is ed.scene for i in items)
    ed.canvas.select_all()
    assert len(ed.canvas.selected_annotations()) == 3
    menu = ed.canvas.context_menu(QPoint(5, 5))
    assert [a.text() for a in menu.actions() if not a.isSeparator()] == ["Delete", "Select all", "Delete all annotations"]
    ed.canvas.delete_all()
    assert not ed.scene.annotations() and not ed.delete_action.isEnabled()
    ed.stack.undo()
    assert len(ed.scene.annotations()) == 3


def test_diagnostics_log(qapp, tmp_path):
    import sys
    import threading

    from screencapture import diagnostics

    path = diagnostics.install(tmp_path / "sc.log")
    try:
        t = threading.Thread(target=lambda: 1 / 0, name="boom")
        t.start()
        t.join()
        text = path.read_text()
        assert "PySide6" in text and "ZeroDivisionError" in text and "boom" in text
    finally:
        sys.excepthook, threading.excepthook = sys.__excepthook__, threading.__excepthook__


def test_closing_editor_with_selection_raises_nothing(qapp, tmp_path):
    """Qt emits selectionChanged / sceneRectChanged while the window is being destroyed; nothing may blow up."""
    import gc
    import sys

    errors = []
    old = sys.excepthook
    sys.excepthook = lambda k, v, tb: errors.append(repr(v))
    try:
        for _ in range(5):
            ed = EditorWindow(_img(300, 200), Library(tmp_path))
            ed.show()
            box = BoxItem(QRectF(10, 10, 40, 40))
            box.setPen(ed.canvas.pen())
            box.setFlags(box.flags() | MOVABLE)
            ed.stack.push(AddCommand(ed.scene, box))
            box.setSelected(True)
            ed.stack.clear()  # leave the item alive only inside the scene
            ed.close()
            ed.deleteLater()
            del ed, box
            gc.collect()
            QApplication.sendPostedEvents(None, 0)
            QApplication.processEvents()
        gc.collect()
        QApplication.processEvents()
    finally:
        sys.excepthook = old
    assert errors == []


def _typed_text(ed, text="hello"):
    """Create a text annotation the way the user does: text tool, click, type, finish (focus out)."""
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QFocusEvent

    from screencapture.items import TextItem

    before = {id(i) for i in ed.scene.items() if isinstance(i, TextItem)}
    ed.canvas.set_tool("text")
    ed.canvas._add_text(QPointF(20, 20))
    it = next(i for i in ed.scene.items() if isinstance(i, TextItem) and id(i) not in before)
    it.setPlainText(text)
    it.focusOutEvent(QFocusEvent(QEvent.FocusOut))
    return it


def test_text_font_controls(qapp, tmp_path):
    from screencapture.items import TextItem

    ed = EditorWindow(_img(400, 300), Library(tmp_path))
    ed.show()
    it = _typed_text(ed)
    assert it.isSelected() and ed.stack.count() == 1
    old = it.font()
    ed.font_size_box.setValue(48)  # toolbar spin box -> applies to the selected text
    ed.bold_action.setChecked(True)
    ed.italic_action.setChecked(True)
    assert it.font().pixelSize() == 48 and it.font().bold() and it.font().italic()
    ed.stack.undo()
    ed.stack.undo()
    ed.stack.undo()
    assert it.font().pixelSize() == old.pixelSize() and not it.font().bold()
    ed.stack.redo()
    ed.stack.redo()
    ed.stack.redo()
    assert it.font().pixelSize() == 48
    # new text picks up the chosen style
    ed.canvas.scene().clearSelection()
    ed.canvas.set_text_style(family=ed.canvas.font_family, size=33)
    new = _typed_text(ed, "second")
    assert new is not it and new.font().pixelSize() == 33 and it.font().pixelSize() == 48
    # selecting a text shows its font in the controls
    it.setSelected(True)
    ed.canvas.scene().clearSelection()
    it.setSelected(True)
    assert ed.font_size_box.value() == 48 and ed.bold_action.isChecked()


def test_icon_size_setting(qapp, tmp_path):
    from PySide6.QtWidgets import QToolBar

    from screencapture import icons
    from screencapture.hotkey import HotkeyManager
    from screencapture.settings_dialog import SettingsDialog

    assert icons.size_name() == "medium" and icons.toolbar_pixels() == 28
    ed = EditorWindow(_img(300, 200), Library(tmp_path))
    ed.show()
    bars = ed.findChildren(QToolBar)
    assert len(bars) == 2 and all(b.iconSize().width() == 28 for b in bars)
    dlg = SettingsDialog(HotkeyManager())
    dlg.size_box.setCurrentIndex(dlg.size_box.findData("large"))
    assert all(b.iconSize().width() == 36 for b in bars)  # live preview
    dlg.reject()
    assert all(b.iconSize().width() == 28 for b in bars) and icons.size_name() == "medium"  # reverted
    dlg2 = SettingsDialog(HotkeyManager())
    dlg2.size_box.setCurrentIndex(dlg2.size_box.findData("small"))
    dlg2.accept()
    assert icons.size_name() == "small" and all(b.iconSize().width() == 22 for b in bars)


def test_windows_are_mapped_per_monitor(qapp):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QImage

    from screencapture.capture import ScreenShot, windows_for_screen

    def shot(geometry, dpr):
        img = QImage(1920, 1080, QImage.Format_RGB32)  # every monitor is 1920x1080 native
        return ScreenShot(img, geometry, dpr)

    # the reported setup: primary on the right at 100% (native 0..1920), a 133% monitor on the LEFT (native -1920..0).
    # Qt keeps its top-left at native -1920 and scales its size to 1440x810, leaving a gap in logical space.
    left = shot(QRect(-1920, 0, 1440, 810), 1.3333333)
    right = shot(QRect(0, 0, 1920, 1080), 1.0)
    chrome = QRect(-1920, 0, 1920, 1040)  # maximised Chrome on the left monitor, native pixels
    assert windows_for_screen(left, [chrome]) == [QRect(0, 0, 1440, 780)]  # fills the left overlay exactly
    assert windows_for_screen(right, [chrome]) == []  # not on the right monitor
    # a window on the right monitor is unaffected by the left monitor's scaling
    assert windows_for_screen(right, [QRect(200, 100, 800, 600)]) == [QRect(200, 100, 800, 600)]
    # a window straddling two monitors is clipped to each
    both = QRect(-500, 100, 1000, 400)
    assert windows_for_screen(left, [both]) == [QRect(round(1420 / 1.3333333), round(100 / 1.3333333), round(500 / 1.3333333), round(400 / 1.3333333))]
    assert windows_for_screen(right, [both]) == [QRect(0, 100, 500, 400)]
    # tiny slivers are ignored
    assert windows_for_screen(right, [QRect(-1000, 0, 1004, 500)]) == []


def test_overlay_crops_native_pixels_on_a_scaled_monitor(qapp):
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtTest import QTest

    from screencapture.capture import CaptureOverlay, CaptureSession, ScreenShot

    img = QImage(1920, 1080, QImage.Format_RGB32)
    img.fill(QColor("blue"))
    for x in range(400, 800):
        for y in range(300, 600):
            img.setPixelColor(x, y, QColor("red"))
    shot = ScreenShot(img, QRect(-1920, 0, 1440, 810), 1.3333333)
    got = []
    session = CaptureSession([shot], [QRect(-1920 + 300, 225, 600, 450)])
    session.captured.connect(got.append)
    ov = session.overlays[0]
    ov.show()
    # drag the red block as the user sees it: widget 300..600 x 225..450 (= native 400..800 x 300..600)
    QTest.mousePress(ov, Qt.LeftButton, pos=QPoint(300, 225))
    QTest.mouseMove(ov, QPoint(600, 450))
    QTest.mouseRelease(ov, Qt.LeftButton, pos=QPoint(600, 450))
    assert len(got) == 1
    out = got[0]
    assert abs(out.width() - 400) <= 2 and abs(out.height() - 300) <= 2  # full native resolution, not logical
    assert out.pixelColor(out.width() // 2, out.height() // 2) == QColor("red")
    assert out.pixelColor(1, 1) == QColor("red") and out.pixelColor(out.width() - 2, out.height() - 2) == QColor("red")


def test_windows_stay_on_the_screen(qapp, tmp_path):
    """A huge capture must not produce a window larger than the screen (title bar / close button unreachable)."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication

    from screencapture import winutil
    from screencapture.library import LibraryWindow

    avail = QGuiApplication.primaryScreen().availableGeometry()  # 800x600 on the offscreen platform
    lib = Library(tmp_path)
    ed = EditorWindow(_img(5120, 2880), lib)  # a 5K capture
    ed.show()
    QApplication.processEvents()
    QApplication.processEvents()
    assert avail.contains(ed.frameGeometry()), (avail, ed.frameGeometry())
    assert ed.minimumSizeHint().width() <= avail.width() and ed.minimumSizeHint().height() <= avail.height()
    # dragged (or restored) off-screen: shown again, it comes back with its title bar reachable
    ed.move(QPoint(avail.right() - 40, avail.bottom() - 30))
    ed.hide()
    ed.show()
    QApplication.processEvents()
    QApplication.processEvents()
    assert avail.contains(ed.frameGeometry())
    lw = LibraryWindow(lib)
    lw.show()
    QApplication.processEvents()
    QApplication.processEvents()
    assert avail.contains(lw.frameGeometry())
    winutil.ensure_on_screen(lw)


def test_every_drawn_annotation_can_be_selected_moved_and_deleted(qapp, tmp_path):
    """Regression: arrows and lines were created without the selectable / movable flags."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest

    from PySide6.QtWidgets import QGraphicsItem

    ed = EditorWindow(_img(700, 450), Library(tmp_path))
    ed.show()
    QApplication.processEvents()
    c = ed.canvas
    vp = c.viewport()

    def at(x, y):
        return c.mapFromScene(x, y)

    def drag(a, b):
        QTest.mousePress(vp, Qt.LeftButton, pos=at(*a))
        QTest.mouseMove(vp, at(*b))
        QTest.mouseRelease(vp, Qt.LeftButton, pos=at(*b))

    def new_items(before):
        return [i for i in ed.scene.annotations() if id(i) not in before]

    row = 40
    for tool in ("rect", "ellipse", "arrow", "line", "highlight", "pixelate", "step"):
        before = {id(i) for i in ed.scene.annotations()}
        c.set_tool(tool)
        if tool == "step":
            QTest.mouseClick(vp, Qt.LeftButton, pos=at(100, row + 20))
        else:
            drag((60, row), (260, row + 60))
        (it,) = new_items(before)
        assert it.flags() & QGraphicsItem.ItemIsSelectable and it.flags() & QGraphicsItem.ItemIsMovable, tool
        # select tool: click it -> selected; Delete removes it; undo brings it back
        c.set_tool("select")
        if tool in ("arrow", "line"):
            target = it.mapToScene(it.line().pointAt(0.3))  # on the line itself
        elif tool in ("rect", "ellipse"):
            r = it.rect()
            target = it.mapToScene(QPointF(r.left(), r.center().y()))  # outline only: click the left edge
        else:
            target = it.sceneBoundingRect().center()
        QTest.mouseClick(vp, Qt.LeftButton, pos=at(target.x(), target.y()))
        assert it.isSelected(), f"{tool}: clicking it did not select it"
        # drag it 50 px right
        old = it.pos()
        drag((target.x(), target.y()), (target.x() + 50, target.y()))
        assert it.pos().x() - old.x() == pytest.approx(50, abs=2), f"{tool}: could not be moved"
        ed.canvas.delete_selected()
        assert it.scene() is None, f"{tool}: not deleted"
        ed.stack.undo()
        assert it.scene() is ed.scene
        ed.canvas.scene().clearSelection()
        row += 70
