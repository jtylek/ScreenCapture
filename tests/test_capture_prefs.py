"""What happens to a new capture: clipboard / library preferences."""
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtWidgets import QApplication

from screencapture import prefs
from screencapture.app import ScreenCapture
from screencapture.library import Library


def _image():
    img = QImage(20, 10, QImage.Format_ARGB32)
    img.fill(QColor("#336699"))
    return img


def _app(tmp_path):
    QApplication.instance() or QApplication([])
    return ScreenCapture(Library(tmp_path / "lib"))


def test_defaults():
    assert prefs.get(prefs.AUTO_CLIPBOARD) is True
    assert prefs.get(prefs.AUTO_SAVE) is False


def test_default_copies_but_does_not_save(tmp_path):
    app = _app(tmp_path)
    QGuiApplication.clipboard().clear()
    app._on_captured(_image())
    assert QGuiApplication.clipboard().image().width() == 20
    assert len(app.editors) == 1 and app.editors[0].path is None
    app.editors[0].close()
    assert app.editors == []


def test_auto_save_and_no_clipboard(tmp_path):
    prefs.set_(prefs.AUTO_SAVE, True)
    prefs.set_(prefs.AUTO_CLIPBOARD, False)
    app = _app(tmp_path)
    QGuiApplication.clipboard().clear()
    app._on_captured(_image())
    assert QGuiApplication.clipboard().image().isNull()
    assert app.editors[0].path is not None and app.editors[0].path.exists()
    app.editors[0].close()
