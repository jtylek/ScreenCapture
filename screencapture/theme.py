"""Light / dark / follow-the-system theme."""
from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from . import icons

MODES = ("system", "light", "dark")
KEY = "appearance/theme"
_orig: dict = {}


class _Notifier(QObject):
    changed = Signal()


notifier = _Notifier()


def _palette(dark: bool) -> QPalette:
    c = QColor
    if dark:
        window, text, base, button, dim = c("#2d2d30"), c("#e6e6e6"), c("#1e1e1e"), c("#3c3c40"), c("#7a7a7a")
        tip = c("#3c3c40")
    else:
        window, text, base, button, dim = c("#f0f0f0"), c("#202124"), c("#ffffff"), c("#e6e6e6"), c("#9a9a9a")
        tip = c("#ffffdc")
    p = QPalette()
    for role, col in (
        (QPalette.Window, window), (QPalette.WindowText, text), (QPalette.Base, base),
        (QPalette.AlternateBase, window), (QPalette.Text, text), (QPalette.Button, button),
        (QPalette.ButtonText, text), (QPalette.ToolTipBase, tip), (QPalette.ToolTipText, text if dark else c("#202124")),
        (QPalette.Highlight, c("#2f81f7")), (QPalette.HighlightedText, c("#ffffff")),
        (QPalette.Link, c("#58a6ff") if dark else c("#0b5fd6")), (QPalette.PlaceholderText, dim),
        (QPalette.BrightText, c("#ffffff")),
    ):
        p.setColor(role, col)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, dim)
    return p


def init(app: QApplication):
    """Remember the platform look so 'System' can restore it. Call once, before apply()."""
    _orig["style"] = app.style().objectName()
    _orig["palette"] = QPalette(app.palette())


def saved() -> str:
    v = str(QSettings("ScreenCapture", "ScreenCapture").value(KEY, "system"))
    return v if v in MODES else "system"


def save(mode: str):
    s = QSettings("ScreenCapture", "ScreenCapture")
    s.setValue(KEY, mode)
    s.sync()


def apply(app: QApplication, mode: str):
    hints = app.styleHints()
    try:  # Qt >= 6.8: also makes native title bars follow the choice (Windows)
        hints.setColorScheme({"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(mode, Qt.ColorScheme.Unknown))
    except AttributeError:
        pass
    if mode == "system":
        if _orig:
            app.setStyle(_orig["style"])
            app.setPalette(_orig["palette"])
    else:
        app.setStyle("Fusion")
        app.setPalette(_palette(mode == "dark"))
    icons.refresh()
    notifier.changed.emit()


def is_dark(app: QApplication | None = None) -> bool:
    app = app or QApplication.instance()
    return app.palette().color(QPalette.Window).lightness() < 128


def toggle(app: QApplication):
    """Quick switch: flip between light and dark, and remember it."""
    mode = "light" if is_dark(app) else "dark"
    save(mode)
    apply(app, mode)
