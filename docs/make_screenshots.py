"""Regenerates docs/screenshots/*.png from the real app windows with made-up sample captures.

    xvfb-run -a -s "-screen 0 1700x1100x24" env PYTHONPATH=. python docs/make_screenshots.py

Nothing here is a real screenshot of anyone's screen: the sample captures are drawn below.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFocusEvent, QFont, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

OUT = Path(__file__).resolve().parent / "screenshots"


def sample(kind: int, w: int = 1280, h: int = 720) -> QImage:
    """A made-up application window, drawn from scratch (kind picks the palette and content)."""
    palettes = [
        ("#2f81f7", "#f4f7fb", "Sales dashboard"),
        ("#2e9e4f", "#f3faf5", "Server status"),
        ("#a855f7", "#f8f4fd", "Project timeline"),
        ("#e8590c", "#fdf6f1", "Support queue"),
        ("#0ea5a4", "#f0fafa", "Release notes"),
        ("#64748b", "#f5f6f8", "Settings"),
    ]
    accent, bg, title = palettes[kind % len(palettes)]
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(bg))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    font = QFont()
    font.setPixelSize(15)
    p.setFont(font)
    # window title bar + sidebar
    p.fillRect(0, 0, w, 44, QColor("#ffffff"))
    p.setPen(QColor("#d9dee6"))
    p.drawLine(0, 44, w, 44)
    p.setPen(QColor("#1f2933"))
    f = QFont(font)
    f.setPixelSize(18)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(24, 0, 400, 44), Qt.AlignVCenter, title)
    p.setFont(font)
    p.fillRect(0, 45, 190, h - 45, QColor("#ffffff"))
    for i, name in enumerate(["Overview", "Customers", "Reports", "Invoices", "Settings"]):
        y = 70 + i * 46
        if i == 0:
            p.fillRect(10, y - 8, 170, 36, QColor(accent).lighter(185))
            p.setPen(QColor(accent).darker(130))
        else:
            p.setPen(QColor("#52606d"))
        p.drawText(QRectF(28, y - 8, 150, 36), Qt.AlignVCenter, name)
    # KPI cards
    for i, (label, value) in enumerate([("Revenue", "$48,210"), ("Orders", "1,284"), ("Customers", "367"), ("Refunds", "1.8%")]):
        x = 220 + i * 255
        p.setPen(QPen(QColor("#d9dee6"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(x, 70, 235, 96), 10, 10)
        p.setPen(QColor("#7b8794"))
        p.drawText(QRectF(x + 18, 80, 200, 30), Qt.AlignVCenter, label)
        big = QFont(font)
        big.setPixelSize(30)
        big.setBold(True)
        p.setFont(big)
        p.setPen(QColor("#1f2933"))
        p.drawText(QRectF(x + 18, 108, 210, 46), Qt.AlignVCenter, value)
        p.setFont(font)
    # bar chart card
    p.setPen(QPen(QColor("#d9dee6"), 1))
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(220, 190, 620, 330), 10, 10)
    p.setPen(QColor("#52606d"))
    p.drawText(QRectF(240, 198, 300, 30), Qt.AlignVCenter, "Monthly revenue")
    heights = [90, 120, 105, 150, 140, 185, 170, 215, 205, 250]
    for i, hh in enumerate(heights):
        g = QLinearGradient(0, 500 - hh, 0, 500)
        g.setColorAt(0, QColor(accent))
        g.setColorAt(1, QColor(accent).lighter(160))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(QRectF(250 + i * 58, 500 - hh, 38, hh), 5, 5)
    # table card
    p.setPen(QPen(QColor("#d9dee6"), 1))
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(865, 190, 375, 330), 10, 10)
    p.setPen(QColor("#52606d"))
    p.drawText(QRectF(885, 198, 300, 30), Qt.AlignVCenter, "Latest customers")
    names = ["Jane Smith", "Marco Rossi", "Aiko Tanaka", "Lena Müller", "Omar Haddad", "Sofia Silva"]
    for i, n in enumerate(names):
        y = 236 + i * 46
        p.setPen(QColor("#e4e7eb"))
        p.drawLine(885, y - 4, 1220, y - 4)
        p.setPen(QColor("#1f2933"))
        p.drawText(QRectF(885, y, 200, 36), Qt.AlignVCenter, n)
        p.setPen(QColor("#7b8794"))
        p.drawText(QRectF(1090, y, 130, 36), Qt.AlignVCenter | Qt.AlignRight, f"${(i + 3) * 187}")
    # footer text lines
    p.setPen(QColor("#9aa5b1"))
    p.drawText(QRectF(220, 545, 800, 28), Qt.AlignVCenter, "Updated a few seconds ago · All times in UTC")
    p.end()
    return img


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ScreenCapture")
    app.setOrganizationName("ScreenCapture")
    from screencapture import theme
    from screencapture.editor import AddCommand, EditorWindow
    from screencapture.items import ArrowItem, BoxItem, HighlightItem, MOVABLE, PixelateItem, StepItem, TextItem
    from screencapture.library import Library, LibraryWindow

    theme.init(app)
    theme.apply(app, "light")
    root = Path(tempfile.mkdtemp())
    lib = Library(root / "library")

    # ---- library: six sample captures with believable timestamps ------------------------------------------------
    stamps = ["2026-10-14_09-15-02", "2026-10-14_10-42-37", "2026-10-14_14-03-11", "2026-10-15_08-31-55", "2026-10-15_11-20-09", "2026-10-15_16-48-26"]
    for i, stamp in enumerate(stamps):
        sample(i).save(str(lib.root / f"{stamp}.png"))
    lw = LibraryWindow(lib)
    lw.set_hotkey("Ctrl+Shift+Print")
    lw.resize(1000, 500)
    lw.show()
    QTest.qWait(700)
    lw.grab().save(str(OUT / "library.png"))
    lw.close()

    # ---- editor: the first sample with every kind of annotation ------------------------------------------------
    path = lib.root / f"{stamps[0]}.png"
    ed = EditorWindow(QImage(str(path)), lib, path)
    ed.resize(1240, 850)
    ed.show()
    QTest.qWait(900)
    c = ed.canvas
    red = QColor("#e53935")
    pen = QPen(red, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def add(item):
        ed.stack.push(AddCommand(ed.scene, item))
        return item

    box = BoxItem(QRectF(230, 200, 604, 318))
    box.setPen(pen)
    box.setFlags(box.flags() | MOVABLE)
    add(box)
    hl = HighlightItem(QRectF(878, 232, 348, 44))
    hl.setBrush(QColor(255, 235, 0, 110))
    hl.setFlags(hl.flags() | MOVABLE)
    add(hl)
    blur = PixelateItem(QRectF(884, 280, 120, 34))
    blur.setFlags(blur.flags() | MOVABLE)
    add(blur)
    from PySide6.QtCore import QLineF

    arrow = ArrowItem(QLineF(930, 600, 760, 440), pen, head=True)
    arrow.setFlags(arrow.flags() | MOVABLE)
    add(arrow)
    f = QFont(c.font_family)
    f.setPixelSize(34)
    f.setBold(True)
    text = TextItem(red, f, lambda i: None)
    text.setPlainText("Revenue is up 12%")
    text.setPos(850, 590)
    ed.scene.addItem(text)
    text._committed = True
    ed.stack.push(AddCommand(ed.scene, text))
    for n, (x, y) in enumerate([(205, 118), (205, 345), (1252, 255)], start=1):
        s = StepItem(n, QColor("#2f81f7"))
        s.setPos(x, y)
        add(s)
    ed.scene.clearSelection()
    ed.statusBar().showMessage("Click an item to select it (Ctrl+click adds), drag on empty space to select several. Delete removes, right-click for more.")
    c.zoom_fit()
    QTest.qWait(600)
    ed.grab().save(str(OUT / "editor.png"))
    ed.stack.setClean()
    ed.close()
    print("written:", *(f"{p.name} {p.stat().st_size // 1024} KB" for p in sorted(OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
