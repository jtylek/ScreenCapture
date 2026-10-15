"""The About box."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from . import __author__, __license__, __url__, __version__, icons


def build_about(parent=None) -> QMessageBox:
    """The About message box (built separately from exec() so it can be tested)."""
    box = QMessageBox(parent)
    box.setWindowTitle("About ScreenCapture")
    box.setIconPixmap(icons.app_icon().pixmap(72, 72))
    box.setTextFormat(Qt.RichText)
    box.setText(
        f"<h3>ScreenCapture {__version__}</h3>"
        "<p>A simple screen capture tool: capture a region or a window, annotate, crop, resize, "
        "and keep your screenshots in a library.</p>"
        f"<p><b>Free software</b>, released under the <b>{__license__} license</b>.<br>"
        f"Copyright © 2026 {__author__}.</p>"
        f'<p>Updates and help: <a href="{__url__}">{__url__}</a></p>'
    )
    box.setTextInteractionFlags(Qt.TextBrowserInteraction)  # the link is clickable
    web = box.addButton("Open GitHub page", QMessageBox.ActionRole)
    web.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(__url__)))
    box.addButton(QMessageBox.Close)
    return box


def show_about(parent=None):
    build_about(parent).exec()
