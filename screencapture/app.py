"""Tray application: capture, editor windows, library, single-instance control."""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import about, diagnostics, icons, prefs, theme
from .capture import CaptureSession, grab_current_screen, grab_screens
from .editor import EditorWindow
from .hotkey import HotkeyManager
from .settings_dialog import SettingsDialog
from .library import Library, LibraryWindow
from .windows import window_rects

SERVER_NAME = f"ScreenCapture-{getpass.getuser()}"
COMMANDS = {"capture", "fullscreen", "library", "quit"}


make_icon = icons.app_icon


class ScreenCapture(QObject):
    def __init__(self, library: Library | None = None):
        super().__init__()
        self.library = library or Library()
        self.library_window = LibraryWindow(self.library)
        self.library_window.openRequested.connect(self.open_editor)
        self.library_window.captureRequested.connect(self.capture_region)
        self.library_window.fullscreenRequested.connect(lambda: self.capture_fullscreen(0))
        self.library_window.settingsRequested.connect(self.open_settings)
        self.editors: list[EditorWindow] = []
        self._hidden: list = []
        self._overlay: CaptureSession | None = None
        self.tray = self._make_tray()
        self.server = self._make_server()
        self.hotkeys = HotkeyManager()
        self.hotkeys.triggered.connect(self.capture_region)
        err = self.hotkeys.apply(self.hotkeys.saved(), persist=False)
        self.library_window.set_hotkey(self.hotkeys.current)
        if err:
            self._warn(f"Capture hotkey '{self.hotkeys.saved()}' is not active. {err}")

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

    def _warn(self, text: str):
        if self.tray is not None:
            self.tray.showMessage("ScreenCapture", text, QSystemTrayIcon.Warning, 10000)
        self.library_window.statusBar().showMessage(text, 15000)

    def open_settings(self):
        dlg = SettingsDialog(self.hotkeys, self.library_window)
        dlg.exec()
        self.library_window.set_hotkey(self.hotkeys.current)

    # tray -----------------------------------------------------------------------------------

    def _make_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        t = QSystemTrayIcon(make_icon(), self)
        t.setToolTip("ScreenCapture")
        m = QMenu()
        icons.tag(m.addAction("Capture region / window", self.capture_region), "capture")
        icons.tag(m.addAction("Capture full screen", lambda: self.capture_fullscreen(0)), "screen")
        icons.tag(m.addAction("Capture full screen in 3 s", lambda: self.capture_fullscreen(3000)), "screen")
        m.addSeparator()
        icons.tag(m.addAction("Library", self.show_library), "folder")
        icons.tag(m.addAction("Settings…", self.open_settings), "settings")
        icons.tag(m.addAction("About", lambda: about.show_about(self.library_window)), "info")
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
        """Get our own windows out of the way of a capture. Not while one of our dialogs (Settings, About, Resize…) is
        open: then the user is capturing our own UI, so everything stays visible. (Hiding the library window would
        also hide the dialog that belongs to it, on Windows.)"""
        if QApplication.activeModalWidget() is not None:
            self._hidden = []
            return
        self._hidden = [w for w in [self.library_window, *self.editors] if w.isVisible()]
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
        session = CaptureSession(grab_screens(), window_rects())
        session.captured.connect(self._on_captured)
        session.cancelled.connect(self._on_cancelled)
        self._overlay = session
        session.start()

    def capture_fullscreen(self, delay_ms: int = 0):
        self._hide_own_windows()
        QTimer.singleShot(max(delay_ms, 250), lambda: self._on_captured(grab_current_screen()))

    def _on_cancelled(self):
        self._overlay = None
        self._restore_own_windows()

    def _on_captured(self, image: QImage):
        self._overlay = None
        self._restore_own_windows()
        if prefs.get(prefs.AUTO_CLIPBOARD):
            QGuiApplication.clipboard().setImage(image)  # ready to paste straight away
        if prefs.get(prefs.AUTO_SAVE):
            self.open_editor(self.library.add(image))
        else:  # not in the library until the user saves it from the editor
            self._show_editor(EditorWindow(image, self.library, None))

    # editor ---------------------------------------------------------------------------------

    def open_editor(self, path: Path):
        path = Path(path)
        w = next((e for e in self.editors if e.path == path), None)
        if w is None:
            w = EditorWindow(QImage(str(path)), self.library, path)
        self._show_editor(w)

    def _show_editor(self, w: EditorWindow):
        if w not in self.editors:
            self.editors.append(w)
            w.closed.connect(lambda _w: self.editors.remove(_w) if _w in self.editors else None)
            w.libraryRequested.connect(self.show_library)
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
    diagnostics.install()
    problem = diagnostics.check_runtime()
    if problem:
        print(problem, file=sys.stderr)
        QMessageBox.critical(None, "ScreenCapture", problem)
        return 1
    app.setApplicationName("ScreenCapture")
    app.setOrganizationName("ScreenCapture")
    app.setWindowIcon(make_icon())
    theme.init(app)
    theme.apply(app, theme.saved())
    cmd = next((c for c in COMMANDS if getattr(args, c)), None)

    if _send_to_running(cmd or "library"):
        return 0
    if args.quit:
        return 0

    sc = ScreenCapture()
    app.setQuitOnLastWindowClosed(sc.tray is None)
    app.aboutToQuit.connect(sc.hotkeys.stop)
    if cmd in ("capture", "fullscreen"):
        sc.dispatch(cmd)
    elif not (args.tray and sc.tray is not None):
        sc.show_library()
    return app.exec()
