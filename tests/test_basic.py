import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from screencapture.editor import AddCommand, CropCommand, EditorWindow
from screencapture.items import ArrowItem, BoxItem, PixelateItem
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
