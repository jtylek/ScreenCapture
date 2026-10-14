"""Crash / error log, so a crash leaves something to send: Python tracebacks (also for hard crashes via
faulthandler), uncaught exceptions in any thread, and Qt warnings."""
from __future__ import annotations

import faulthandler
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QtMsgType, QTimer, qInstallMessageHandler

MAX_BYTES = 1_000_000
_file = None
_shown = False
_path: Path | None = None


def log_path() -> Path:
    from .library import default_root

    return default_root().parent / "screencapture.log"


def _write(text: str):
    if _file is not None:
        _file.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {text}\n")
        _file.flush()


def _notify_once():
    global _shown
    if _shown:
        return
    _shown = True

    def show():
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance():
            QMessageBox.warning(
                None,
                "ScreenCapture",
                f"Something went wrong. The details were saved to:\n{_path}\n\nPlease send that file when you report it.",
            )

    QTimer.singleShot(0, show)


def _excepthook(kind, value, tb):
    _write("Uncaught exception:\n" + "".join(traceback.format_exception(kind, value, tb)))
    _notify_once()


def _thread_hook(args):
    _write(f"Uncaught exception in thread {args.thread.name if args.thread else '?'}:\n"
           + "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))


_LEVELS = {QtMsgType.QtWarningMsg: "Qt warning", QtMsgType.QtCriticalMsg: "Qt critical", QtMsgType.QtFatalMsg: "Qt FATAL"}


def _qt_handler(mode, context, message):
    if mode in _LEVELS:
        _write(f"{_LEVELS[mode]}: {message}")
    if mode == QtMsgType.QtFatalMsg:
        _file.flush()
    if sys.__stderr__ is not None:  # keep the normal console output when there is one
        print(message, file=sys.__stderr__)


def install(path: Path | None = None) -> Path | None:
    """Start logging. Returns the log path (None if the file can't be written)."""
    global _file, _path
    try:
        path = Path(path) if path else log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_BYTES:
            path.write_text("")
        _file = open(path, "a", encoding="utf-8")
    except OSError:
        return None
    _path = path
    _write(f"--- start, Python {sys.version.split()[0]}, platform {sys.platform} ---")
    try:
        import PySide6

        _write(f"PySide6 {PySide6.__version__}")
    except Exception:
        pass
    faulthandler.enable(file=_file, all_threads=True)  # Python traceback on segfault / abort
    sys.excepthook = _excepthook
    threading.excepthook = _thread_hook
    qInstallMessageHandler(_qt_handler)
    return path


def check_runtime() -> str | None:
    """Detects PySide6 builds that corrupt the reference count of None (PySide6 6.12.0 on Python < 3.12),
    which crashes the app with 'Fatal Python error: none_dealloc' after a few repaints.
    Returns an explanation, or None when everything is fine."""
    from PySide6.QtGui import QColor, QImage, QPainter, QPen

    img = QImage(4, 4, QImage.Format_RGB32)
    painter, pen = QPainter(img), QPen(QColor("red"))
    for _ in range(20):
        painter.setPen(pen)
    before = sys.getrefcount(None)
    for _ in range(100):
        painter.setPen(pen)
    leaked = before - sys.getrefcount(None)
    painter.end()
    if leaked <= 50:
        return None
    import PySide6

    return (
        f"This PySide6 ({PySide6.__version__}) is broken on Python {sys.version.split()[0]}: it corrupts Python's "
        "internal reference counts, and ScreenCapture would crash.\n\n"
        "Install a working version:\n"
        f'  {sys.executable} -m pip install "PySide6-Essentials<6.12"'
    )
