"""Tray application: capture, editor windows, library, single-instance control."""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import icons
from .capture import CaptureOverlay, grab_current_screen, grab_desktop
from .editor import EditorWindow
from .library import Library, LibraryWindow
from .windows import window_rects

SERVER_NAME = f"ScreenCapture-{getpass.getuser()}"
COMMANDS = {"capture", "fullscreen", "library", "quit"}


def make_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#2f81f7"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 60, 60, 12, 12)
    p.setPen(QPen(Qt.white, 5, Qt.SolidLine, Qt.SquareCap))
    for x, y, dx, dy in ((16, 16, 1, 1), (48, 16, -1, 1), (16, 48, 1, -1), (48, 48, -1, -1)):
        p.drawLine(x, y, x + 12 * dx, y)
        p.drawLine(x, y, x, y + 12 * dy)
    p.end()
    return QIcon(pm)


class ScreenCapture(QObject):
    def __init__(self, library: Library | None = None):
        super().__init__()
        self.library = library or Library()
        self.library_window = LibraryWindow(self.library)
        self.library_window.openRequested.connect(self.open_editor)
        self.library_window.captureRequested.connect(self.capture_region)
        self.library_window.fullscreenRequested.connect(lambda: self.capture_fullscreen(0))
        self.editors: dict[Path, EditorWindow] = {}
        self._hidden: list = []
        self._overlay: CaptureOverlay | None = None
        self.tray = self._make_tray()
        self.server = self._make_server()

    # control channel (second `screencapture --capture` invocation talks to the running one) ----

    def _make_server(self) -> QLocalServer:
        QLocalServer.removeServer(SERVER_NAME)  # stale socket from a crash
        s = QLocalServer(self)
        s.listen(SERVER_NAME)
        s.newConnection.connect(self._on_connection)
        return s

    def _on_connection(self):
        sock = self.server.nextPendingConnection()
        sock.waitForReadyRead(500)
        self.dispatch(bytes(sock.readAll()).decode(errors="ignore").strip())
        sock.disconnectFromServer()

    def dispatch(self, cmd: str):
        if cmd == "capture":
            QTimer.singleShot(0, self.capture_region)
        elif cmd == "fullscreen":
            QTimer.singleShot(0, lambda: self.capture_fullscreen(0))
        elif cmd == "library":
            self.show_library()
        elif cmd == "quit":
            QApplication.quit()

    # tray -----------------------------------------------------------------------------------

    def _make_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        t = QSystemTrayIcon(make_icon(), self)
        t.setToolTip("ScreenCapture")
        m = QMenu()
        m.addAction(icons.icon("capture"), "Capture region / window", self.capture_region)
        m.addAction(icons.icon("screen"), "Capture full screen", lambda: self.capture_fullscreen(0))
        m.addAction(icons.icon("screen"), "Capture full screen in 3 s", lambda: self.capture_fullscreen(3000))
        m.addSeparator()
        m.addAction(icons.icon("folder"), "Library", self.show_library)
        m.addSeparator()
        m.addAction("Quit", QApplication.quit)
        t.setContextMenu(m)
        t.activated.connect(lambda r: r == QSystemTrayIcon.Trigger and self.show_library())
        t.show()
        self._tray_menu = m
        return t

    def show_library(self):
        self.library_window.show()
        self.library_window.raise_()
        self.library_window.activateWindow()

    # capture --------------------------------------------------------------------------------

    def _hide_own_windows(self):
        self._hidden = [w for w in [self.library_window, *self.editors.values()] if w.isVisible()]
        for w in self._hidden:
            w.hide()
        QApplication.processEvents()

    def _restore_own_windows(self):
        for w in self._hidden:
            w.show()
        self._hidden = []

    def capture_region(self):
        if self._overlay is not None:
            return
        self._hide_own_windows()
        QTimer.singleShot(250, self._start_overlay)  # let the compositor repaint without our windows

    def _start_overlay(self):
        desktop, geo, dpr = grab_desktop()
        ov = CaptureOverlay(desktop, geo, dpr, window_rects())
        ov.captured.connect(self._on_captured)
        ov.cancelled.connect(self._on_cancelled)
        self._overlay = ov
        ov.start()

    def capture_fullscreen(self, delay_ms: int = 0):
        self._hide_own_windows()
        QTimer.singleShot(max(delay_ms, 250), lambda: self._on_captured(grab_current_screen()))

    def _on_cancelled(self):
        self._overlay = None
        self._restore_own_windows()

    def _on_captured(self, image: QImage):
        self._overlay = None
        self._restore_own_windows()
        self.open_editor(self.library.add(image))

    # editor ---------------------------------------------------------------------------------

    def open_editor(self, path: Path):
        path = Path(path)
        if path in self.editors:
            w = self.editors[path]
        else:
            w = EditorWindow(QImage(str(path)), self.library, path)
            w.closed.connect(lambda _w, p=path: self.editors.pop(p, None))
            self.editors[path] = w
        w.show()
        w.raise_()
        w.activateWindow()


def _send_to_running(cmd: str) -> bool:
    s = QLocalSocket()
    s.connectToServer(SERVER_NAME)
    if not s.waitForConnected(300):
        return False
    s.write(cmd.encode())
    s.waitForBytesWritten(500)
    s.disconnectFromServer()
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="screencapture", description="Capture, annotate, crop.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--capture", action="store_true", help="start a region/window capture (bind this to PrintScreen)")
    g.add_argument("--fullscreen", action="store_true", help="capture the screen under the mouse")
    g.add_argument("--library", action="store_true", help="show the library window")
    g.add_argument("--quit", action="store_true", help="stop the running instance")
    ap.add_argument("--tray", action="store_true", help="start quietly in the tray (used for autostart)")
    args = ap.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("ScreenCapture")
    app.setOrganizationName("ScreenCapture")
    app.setWindowIcon(make_icon())
    cmd = next((c for c in COMMANDS if getattr(args, c)), None)

    if _send_to_running(cmd or "library"):
        return 0
    if args.quit:
        return 0

    sc = ScreenCapture()
    app.setQuitOnLastWindowClosed(sc.tray is None)
    if cmd in ("capture", "fullscreen"):
        sc.dispatch(cmd)
    elif not (args.tray and sc.tray is not None):
        sc.show_library()
    return app.exec()
