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

    assert icons.size_name() == "medium" and icons.toolbar_pixels() == 32  # bigger than the old 24 by default
    ed = EditorWindow(_img(300, 200), Library(tmp_path))
    ed.show()
    bars = ed.findChildren(QToolBar)
    assert len(bars) == 2 and all(b.iconSize().width() == 32 for b in bars)
    dlg = SettingsDialog(HotkeyManager())
    dlg.size_box.setCurrentIndex(dlg.size_box.findData("large"))
    assert all(b.iconSize().width() == 40 for b in bars)  # live preview
    dlg.reject()
    assert all(b.iconSize().width() == 32 for b in bars) and icons.size_name() == "medium"  # reverted
    dlg2 = SettingsDialog(HotkeyManager())
    dlg2.size_box.setCurrentIndex(dlg2.size_box.findData("small"))
    dlg2.accept()
    assert icons.size_name() == "small" and all(b.iconSize().width() == 24 for b in bars)
