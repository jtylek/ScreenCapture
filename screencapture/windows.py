"""Top-level window rectangles (physical pixels, desktop coordinates), topmost first."""
from __future__ import annotations

import sys

from PySide6.QtCore import QRect


def window_rects() -> list[QRect]:
    try:
        if sys.platform == "win32":
            return _windows()
        if sys.platform.startswith("linux"):
            return _x11()
    except Exception:
        pass
    return []


def _x11() -> list[QRect]:
    from Xlib import X, display

    d = display.Display()
    try:
        root = d.screen().root
        prop = root.get_full_property(d.intern_atom("_NET_CLIENT_LIST_STACKING"), X.AnyPropertyType)
        if prop is not None:
            ids = list(prop.value)[::-1]
        else:  # no EWMH window manager: fall back to the root's children
            ids = [c.id for c in reversed(root.query_tree().children)]
        extents_atom = d.intern_atom("_NET_FRAME_EXTENTS")
        rects = []
        for wid in ids:
            w = d.create_resource_object("window", wid)
            try:
                if w.get_attributes().map_state != X.IsViewable:
                    continue
                g = w.get_geometry()
                c = w.translate_coords(root, 0, 0)
                x, y = -c.x, -c.y
                left = right = top = bottom = 0
                ext = w.get_full_property(extents_atom, X.AnyPropertyType)
                if ext is not None and len(ext.value) == 4:
                    left, right, top, bottom = ext.value
            except Exception:
                continue
            if g.width < 20 or g.height < 20:
                continue
            rects.append(QRect(x - left, y - top, g.width + left + right, g.height + top + bottom))
        return rects
    finally:
        d.close()


def _windows() -> list[QRect]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    dwm = ctypes.windll.dwmapi
    rects: list[QRect] = []
    DWMWA_EXTENDED_FRAME_BOUNDS, DWMWA_CLOAKED = 9, 14

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        cloaked = ctypes.c_int(0)
        dwm.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), 4)
        if cloaked.value:
            return True
        r = wintypes.RECT()
        if dwm.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) != 0:
            user32.GetWindowRect(hwnd, ctypes.byref(r))
        if r.right - r.left >= 20 and r.bottom - r.top >= 20:
            rects.append(QRect(r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumWindows(cb, 0)  # enumerates in Z order, topmost first
    return rects
