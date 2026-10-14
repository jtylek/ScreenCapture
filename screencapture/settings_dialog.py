"""Settings dialog (currently: the global capture hotkey)."""
from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from . import icons
from .hotkey import DEFAULT, HotkeyManager, parse


class SettingsDialog(QDialog):
    def __init__(self, hotkeys: HotkeyManager, parent=None):
        super().__init__(parent)
        self.hotkeys = hotkeys
        self.setWindowTitle("Settings")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumWidth(460)

        self.edit = QKeySequenceEdit(QKeySequence(hotkeys.current))
        self.edit.setMaximumSequenceLength(1)
        clear = QPushButton("Clear")
        clear.setToolTip("No capture hotkey")
        clear.clicked.connect(self.edit.clear)
        default = QPushButton("Default")
        default.setToolTip(f"Reset to {DEFAULT}")
        default.clicked.connect(lambda: self.edit.setKeySequence(QKeySequence(DEFAULT)))
        row = QHBoxLayout()
        row.addWidget(self.edit, 1)
        row.addWidget(clear)
        row.addWidget(default)

        form = QFormLayout()
        form.addRow("Capture hotkey:", row)
        hint = QLabel(
            "Starts a region / window capture from anywhere. Click the box and press the keys you want; "
            "Clear turns the hotkey off."
        )
        hint.setWordWrap(True)
        self.message = QLabel()
        self.message.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addWidget(self.message)
        lay.addWidget(buttons)
        self.edit.keySequenceChanged.connect(self._validate)

    def _text(self) -> str:
        return self.edit.keySequence().toString(QKeySequence.PortableText)

    def _show(self, text: str, error: bool):
        self.message.setStyleSheet("color: #d33;" if error else "")
        self.message.setText(text)

    def _validate(self):
        text = self._text()
        if not text:
            return self._show("", False)
        _, err = parse(text)
        self._show(err or "", bool(err))

    def accept(self):
        err = self.hotkeys.apply(self._text())
        if err:
            return self._show(err, True)
        super().accept()
