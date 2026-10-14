"""Keep windows on the screen they open on: sized to fit, centred, title bar always reachable."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor, QGuiApplication


def target_screen():
    """The screen the user is working on (where the mouse is), not just the primary one."""
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


def size_and_place(win, want_w: int, want_h: int, min_w: int = 480, min_h: int = 320):
    """Resize to the wanted size, but never beyond 90% of the target screen, and centre the window there."""
    avail = target_screen().availableGeometry()
    w, h = min(want_w, int(avail.width() * 0.9)), min(want_h, int(avail.height() * 0.9))
    win.setMinimumSize(min(min_w, w), min(min_h, h))
    win.resize(w, h)
    win.move(avail.x() + (avail.width() - w) // 2, avail.y() + (avail.height() - h) // 2)


def ensure_on_screen(win):
    """Shrink to fit and pull back inside the screen's usable area if any part (title bar, close button) is outside."""
    screen = win.screen() or target_screen()
    avail = screen.availableGeometry()
    g = win.frameGeometry()
    frame_w, frame_h = g.width() - win.width(), g.height() - win.height()
    w, h = min(win.width(), avail.width() - frame_w), min(win.height(), avail.height() - frame_h)
    if (w, h) != (win.width(), win.height()):
        win.resize(max(w, 1), max(h, 1))
        g = win.frameGeometry()
    x = min(max(g.x(), avail.left()), avail.right() - g.width() + 1)
    y = min(max(g.y(), avail.top()), avail.bottom() - g.height() + 1)
    if (x, y) != (g.x(), g.y()):
        win.move(max(x, avail.left()), max(y, avail.top()))


def schedule_ensure_on_screen(win):
    QTimer.singleShot(0, lambda: ensure_on_screen(win))
