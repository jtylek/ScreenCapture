"""Library of recent captures (flattened PNGs on disk) and its browser window."""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from . import icons
from PySide6.QtCore import QObject, QSize, Qt, QStandardPaths, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import QListView, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QToolBar

MAX_ITEMS = 500
THUMB = QSize(220, 150)


def default_root() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or str(Path.home() / ".screencapture")
    return Path(base) / "library"


class Library(QObject):
    changed = Signal()

    def __init__(self, root: Path | None = None, max_items: int = MAX_ITEMS):
        super().__init__()
        self.root = Path(root) if root else default_root()
        self.max_items = max_items
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / ".thumbs").mkdir(exist_ok=True)

    def entries(self) -> list[Path]:
        """Newest first."""
        return sorted(self.root.glob("*.png"), key=lambda p: p.name, reverse=True)

    def add(self, image: QImage) -> Path:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = self.root / f"{stamp}.png"
        n = 1
        while path.exists():
            n += 1
            path = self.root / f"{stamp}-{n}.png"
        image.save(str(path), "PNG")
        self._prune()
        self.changed.emit()
        return path

    def save(self, path: Path, image: QImage):
        image.save(str(path), "PNG")
        self.changed.emit()

    def delete(self, path: Path):
        path.unlink(missing_ok=True)
        (self.root / ".thumbs" / path.name).unlink(missing_ok=True)
        self.changed.emit()

    def _prune(self):
        for old in self.entries()[self.max_items :]:
            old.unlink(missing_ok=True)
            (self.root / ".thumbs" / old.name).unlink(missing_ok=True)

    def thumbnail(self, path: Path) -> QPixmap:
        cache = self.root / ".thumbs" / path.name
        if cache.exists() and cache.stat().st_mtime >= path.stat().st_mtime:
            pm = QPixmap(str(cache))
            if not pm.isNull():
                return pm
        img = QImage(str(path))
        if img.isNull():
            return QPixmap()
        pm = QPixmap.fromImage(img.scaled(THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        pm.save(str(cache), "PNG")
        return pm


def _label(path: Path) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})", path.stem)
    if m:
        d = datetime.strptime(f"{m[1]} {m[2]}:{m[3]}:{m[4]}", "%Y-%m-%d %H:%M:%S")
        return d.strftime("%b %d, %H:%M")
    return path.stem


class LibraryWindow(QMainWindow):
    openRequested = Signal(Path)
    captureRequested = Signal()
    fullscreenRequested = Signal()

    def __init__(self, library: Library):
        super().__init__()
        self.library = library
        self.setWindowTitle("ScreenCapture — Library")
        self.resize(900, 600)
        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setIconSize(THUMB)
        self.list.setGridSize(QSize(THUMB.width() + 24, THUMB.height() + 44))
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.itemActivated.connect(lambda it: self.openRequested.emit(Path(it.data(Qt.UserRole))))
        self.setCentralWidget(self.list)

        tb = QToolBar(self)
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.setIconSize(QSize(22, 22))
        tb.addAction(icons.icon("capture"), "Capture region", self.captureRequested.emit)
        tb.addAction(icons.icon("screen"), "Capture screen", self.fullscreenRequested.emit)
        tb.addSeparator()
        tb.addAction(icons.icon("edit"), "Edit", self._open_selected)
        tb.addAction(icons.icon("copy"), "Copy", self._copy_selected)
        tb.addAction(icons.icon("trash"), "Delete", self._delete_selected).setShortcut(QKeySequence.Delete)
        tb.addAction(
            icons.icon("folder"), "Open folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.library.root)))
        )

        self.library.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for p in self.library.entries():
            it = QListWidgetItem(QIcon(self.library.thumbnail(p)), _label(p))
            it.setData(Qt.UserRole, str(p))
            it.setTextAlignment(Qt.AlignHCenter)
            self.list.addItem(it)
        n = self.list.count()
        self.statusBar().showMessage(f"{n} capture{'' if n == 1 else 's'}")

    def _selected(self) -> list[Path]:
        return [Path(i.data(Qt.UserRole)) for i in self.list.selectedItems()]

    def _open_selected(self):
        for p in self._selected():
            self.openRequested.emit(p)

    def _copy_selected(self):
        sel = self._selected()
        if sel:
            QGuiApplication.clipboard().setImage(QImage(str(sel[0])))
            self.statusBar().showMessage("Copied to clipboard", 3000)

    def _delete_selected(self):
        sel = self._selected()
        if sel and QMessageBox.question(self, "Delete", f"Delete {len(sel)} capture(s) from the library?") == QMessageBox.Yes:
            for p in sel:
                self.library.delete(p)

    def _menu(self, pos):
        if not self.list.itemAt(pos):
            return
        m = QMenu(self)
        m.addAction(icons.icon("edit"), "Open in editor", self._open_selected)
        m.addAction(icons.icon("copy"), "Copy to clipboard", self._copy_selected)
        m.addAction(icons.icon("trash"), "Delete", self._delete_selected)
        m.exec(self.list.viewport().mapToGlobal(pos))
