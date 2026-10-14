"""Annotation editor: canvas, undo commands and the editor window."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLineF, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QUndoCommand,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QFontComboBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSpinBox,
    QToolBar,
)

from .items import (
    MOVABLE,
    ArrowItem,
    BoxItem,
    CropItem,
    HighlightItem,
    OvalItem,
    PixelateItem,
    StepItem,
    TextItem,
)
from . import icons, winutil
from .library import Library

# key, tooltip, status-bar hint
TOOLS = [
    ("select", "Select", "Click an item to select it (Ctrl+click adds), drag on empty space to select several. Delete removes, right-click for more."),
    ("rect", "Rectangle", "Drag to draw a rectangle."),
    ("ellipse", "Ellipse", "Drag to draw an ellipse."),
    ("arrow", "Arrow", "Drag from the tail to the point."),
    ("line", "Line", "Drag to draw a line."),
    ("text", "Text", "Click and type. Click elsewhere to finish."),
    ("highlight", "Highlight", "Drag to highlight an area."),
    ("pixelate", "Blur (pixelate)", "Drag over what you want to hide."),
    ("step", "Step number", "Click to place the next numbered step."),
    ("crop", "Crop", "Drag the area to keep; adjust its edges, then press Enter."),
    ("cutv", "Cut out a vertical strip", "Drag across the part to remove (joins the left and right sides), then press Enter."),
    ("cuth", "Cut out a horizontal strip", "Drag across the part to remove (joins the top and bottom), then press Enter."),
]
TOOL_GROUPS_END = {"select", "step"}  # toolbar separator after these


class CanvasScene(QGraphicsScene):
    def __init__(self, image: QImage):
        super().__init__()
        self.base_item = QGraphicsPixmapItem()
        self.base_item.setZValue(-1000)
        self.addItem(self.base_item)
        self.set_base(QPixmap.fromImage(image))

    def set_base(self, pm: QPixmap):
        self.base_image = pm.toImage()
        self.base_item.setPixmap(pm)
        self.setSceneRect(QRectF(pm.rect()))

    def annotations(self):
        return [i for i in self.items() if i is not self.base_item and i.parentItem() is None and not isinstance(i, CropItem)]


# -- undo commands ---------------------------------------------------------------------------


class AddCommand(QUndoCommand):
    def __init__(self, scene, item):
        super().__init__("Add")
        self.scene, self.item = scene, item

    def redo(self):
        if self.item.scene() is not self.scene:
            self.scene.addItem(self.item)

    def undo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)


class DeleteCommand(QUndoCommand):
    def __init__(self, scene, items):
        super().__init__("Delete")
        self.scene, self.items = scene, list(items)

    def redo(self):
        for i in self.items:
            if i.scene() is self.scene:
                self.scene.removeItem(i)

    def undo(self):
        for i in self.items:
            if i.scene() is not self.scene:
                self.scene.addItem(i)


class MoveCommand(QUndoCommand):
    def __init__(self, moves):  # [(item, old_pos, new_pos)]
        super().__init__("Move")
        self.moves = moves

    def redo(self):
        for item, _old, new in self.moves:
            item.setPos(new)

    def undo(self):
        for item, old, _new in self.moves:
            item.setPos(old)


class CropCommand(QUndoCommand):
    def __init__(self, scene: CanvasScene, rect):
        super().__init__("Crop")
        self.scene, self.rect = scene, rect
        self.old_pixmap = None

    def redo(self):
        self.old_pixmap = self.scene.base_item.pixmap()
        self.scene.set_base(self.old_pixmap.copy(self.rect))
        for i in self.scene.annotations():
            i.moveBy(-self.rect.x(), -self.rect.y())

    def undo(self):
        self.scene.set_base(self.old_pixmap)
        for i in self.scene.annotations():
            i.moveBy(self.rect.x(), self.rect.y())


class FontCommand(QUndoCommand):
    def __init__(self, changes):  # [(item, old_font, new_font)]
        super().__init__("Text style")
        self.changes = changes

    def redo(self):
        for item, _old, new in self.changes:
            item.setFont(new)

    def undo(self):
        for item, old, _new in self.changes:
            item.setFont(old)


class CutCommand(QUndoCommand):
    """Removes a vertical (x range) or horizontal (y range) strip and joins the two remaining parts.

    Annotations whose centre lies inside the strip are removed; those beyond it move up/left."""

    def __init__(self, scene: CanvasScene, vertical: bool, a: int, b: int):
        super().__init__("Cut out")
        self.scene, self.vertical, self.a, self.b = scene, vertical, a, b
        self.old_pixmap = None
        self.removed, self.shifted = [], []

    def redo(self):
        pm = self.scene.base_item.pixmap()
        self.old_pixmap = pm
        w, h, a, b = pm.width(), pm.height(), self.a, self.b
        d = b - a
        if self.vertical:
            new = QPixmap(w - d, h)
            parts = [(pm.copy(0, 0, a, h), 0, 0), (pm.copy(b, 0, w - b, h), a, 0)]
        else:
            new = QPixmap(w, h - d)
            parts = [(pm.copy(0, 0, w, a), 0, 0), (pm.copy(0, b, w, h - b), 0, a)]
        new.fill(Qt.white)
        p = QPainter(new)
        for part, x, y in parts:
            p.drawPixmap(x, y, part)
        p.end()
        self.removed, self.shifted = [], []
        for it in self.scene.annotations():
            c = it.sceneBoundingRect().center()
            v = c.x() if self.vertical else c.y()
            if a <= v < b:
                self.removed.append(it)
                self.scene.removeItem(it)
            elif v >= b:
                it.moveBy(-d if self.vertical else 0, 0 if self.vertical else -d)
                self.shifted.append(it)
        self.scene.set_base(new)

    def undo(self):
        d = self.b - self.a
        self.scene.set_base(self.old_pixmap)
        for it in self.shifted:
            it.moveBy(d if self.vertical else 0, 0 if self.vertical else d)
        for it in self.removed:
            self.scene.addItem(it)
        self.removed, self.shifted = [], []


# -- canvas ----------------------------------------------------------------------------------


class Canvas(QGraphicsView):
    cropActive = Signal(bool)

    def __init__(self, scene: CanvasScene, stack: QUndoStack):
        super().__init__(scene)
        self.stack = stack
        self.tool = "select"
        self.color = QColor("#e53935")
        self.width = 4
        self.font_family = QFont().family()
        self.font_size = 20  # pixels
        self.font_bold = False
        self.font_italic = False
        self._item = None
        self._start = QPointF()
        self._crop: CropItem | None = None
        self._crop_drag = None
        self._moving = None
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor(45, 45, 48))
        self.setAlignment(Qt.AlignCenter)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)  # select tool: drag on empty space selects several

    # state ---------------------------------------------------------------------------------

    def set_tool(self, tool: str):
        self.tool = tool
        self.discard_crop()
        self.viewport().setCursor(Qt.ArrowCursor if tool == "select" else Qt.CrossCursor)
        self.setDragMode(QGraphicsView.RubberBandDrag if tool == "select" else QGraphicsView.NoDrag)

    def editing_text(self) -> bool:
        f = self.scene().focusItem()
        return isinstance(f, TextItem) and f.textInteractionFlags() != Qt.NoTextInteraction

    def selected_annotations(self):
        sc = self.scene()
        base = getattr(sc, "base_item", None)  # a scene that is being destroyed has lost its Python attributes
        return [i for i in sc.selectedItems() if i is not base and not isinstance(i, CropItem)]

    def delete_selected(self):
        sel = self.selected_annotations()
        if sel:
            self.stack.push(DeleteCommand(self.scene(), sel))

    def select_all(self):
        for i in self.scene().annotations():
            i.setSelected(True)

    def delete_all(self):
        items = self.scene().annotations()
        if items:
            self.stack.push(DeleteCommand(self.scene(), items))

    def context_menu(self, view_pos) -> QMenu:
        """Right-click menu (built separately from exec() so it can be tested)."""
        item = self.itemAt(view_pos)
        if item is not None and item is not self.scene().base_item and not item.isSelected():
            self.scene().clearSelection()
            item.setSelected(True)
        has_sel = bool(self.selected_annotations())
        has_any = bool(self.scene().annotations())
        m = QMenu(self)
        a = icons.tag(m.addAction("Delete", self.delete_selected), "trash")
        a.setEnabled(has_sel)
        m.addAction("Select all", self.select_all).setEnabled(has_any)
        m.addSeparator()
        m.addAction("Delete all annotations", self.delete_all).setEnabled(has_any)
        return m

    def contextMenuEvent(self, e):
        if self._item is None and not self._crop_drag:
            self.context_menu(e.pos()).exec(e.globalPos())

    def pen(self) -> QPen:
        return QPen(self.color, self.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def render_image(self) -> QImage:
        sc = self.scene()
        sc.setFocusItem(None)
        sc.clearSelection()
        if self._crop:
            self._crop.hide()
        img = QImage(sc.sceneRect().size().toSize(), QImage.Format_RGB32)
        img.fill(Qt.white)
        p = QPainter(img)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        sc.render(p, QRectF(img.rect()), sc.sceneRect())
        p.end()
        if self._crop:
            self._crop.show()
        return img

    # crop ----------------------------------------------------------------------------------

    def discard_crop(self):
        if self._crop:
            self.scene().removeItem(self._crop)
            self._crop = None
            self.cropActive.emit(False)

    def apply_crop(self):
        if not self._crop:
            return
        mode = self._crop.mode
        r = self._crop.rect().intersected(self.scene().sceneRect()).toRect()
        self.discard_crop()
        if mode == "crop":
            if r.width() >= 2 and r.height() >= 2:
                self.stack.push(CropCommand(self.scene(), r))
            return
        vertical = mode == "cutv"
        size = int(self.scene().sceneRect().width() if vertical else self.scene().sceneRect().height())
        a, b = (r.left(), r.right() + 1) if vertical else (r.top(), r.bottom() + 1)
        a, b = max(a, 0), min(b, size)
        if b - a >= 1 and b - a < size:  # never cut away the whole image
            self.stack.push(CutCommand(self.scene(), vertical, a, b))

    def _crop_hit(self, p: QPointF):
        r = self._crop.rect()
        m = 8 / max(self.transform().m11(), 0.01)
        near = (abs(p.x() - r.left()) < m, abs(p.x() - r.right()) < m, abs(p.y() - r.top()) < m, abs(p.y() - r.bottom()) < m)
        if self._crop.mode == "cutv":
            near = (near[0], near[1], False, False)
        elif self._crop.mode == "cuth":
            near = (False, False, near[2], near[3])
        inside = r.adjusted(-m, -m, m, m).contains(p)
        if inside and any(near):
            return ("edge", *near)
        if r.contains(p):
            return ("move",)
        return None

    def _crop_update(self, p: QPointF):
        mode, start, orig = self._crop_drag
        bounds = self.scene().sceneRect()
        if mode[0] == "new":
            r = QRectF(start, p).normalized()
        elif mode[0] == "move":
            d = p - start
            r = orig.translated(d)
            r.moveLeft(min(max(r.left(), bounds.left()), bounds.right() - r.width()))
            r.moveTop(min(max(r.top(), bounds.top()), bounds.bottom() - r.height()))
        else:
            _, l, rt, t, b = mode
            r = QRectF(orig)
            if l:
                r.setLeft(p.x())
            if rt:
                r.setRight(p.x())
            if t:
                r.setTop(p.y())
            if b:
                r.setBottom(p.y())
        r = r.normalized().intersected(bounds)
        if self._crop.mode == "cutv":
            r = QRectF(r.left(), bounds.top(), r.width(), bounds.height())
        elif self._crop.mode == "cuth":
            r = QRectF(bounds.left(), r.top(), bounds.width(), r.height())
        self._crop.set_rect(r)

    # items ---------------------------------------------------------------------------------

    def _make(self, p: QPointF):
        t = self.tool
        if t == "rect":
            return self._styled(BoxItem(QRectF(p, p)))
        if t == "ellipse":
            return self._styled(OvalItem(QRectF(p, p)))
        if t in ("arrow", "line"):
            return ArrowItem(QLineF(p, p), self.pen(), head=(t == "arrow"))
        if t == "highlight":
            it = HighlightItem(QRectF(p, p))
            it.setBrush(QColor(255, 235, 0, 110))
            it.setFlags(it.flags() | MOVABLE)
            return it
        if t == "pixelate":
            it = PixelateItem(QRectF(p, p))
            it.setFlags(it.flags() | MOVABLE)
            return it
        return None

    def _styled(self, item):
        item.setPen(self.pen())
        item.setFlags(item.flags() | MOVABLE)
        return item

    def _update(self, p: QPointF):
        it, s = self._item, self._start
        if isinstance(it, ArrowItem):
            it.setLine(s.x(), s.y(), p.x(), p.y())
        else:
            it.setRect(QRectF(s, p).normalized())

    def _too_small(self, it) -> bool:
        if isinstance(it, ArrowItem):
            return it.line().length() < 4
        r = it.rect()
        return r.width() < 4 and r.height() < 4

    def text_font(self) -> QFont:
        f = QFont(self.font_family)
        f.setPixelSize(self.font_size)
        f.setBold(self.font_bold)
        f.setItalic(self.font_italic)
        return f

    def set_text_style(self, family=None, size=None, bold=None, italic=None):
        """Sets the font for new text and applies it to the selected / currently edited text items."""
        if family is not None:
            self.font_family = family
        if size is not None:
            self.font_size = size
        if bold is not None:
            self.font_bold = bold
        if italic is not None:
            self.font_italic = italic
        targets = [i for i in self.scene().selectedItems() if isinstance(i, TextItem)]
        focus = self.scene().focusItem()
        if isinstance(focus, TextItem) and focus not in targets and focus.textInteractionFlags() != Qt.NoTextInteraction:
            targets.append(focus)  # the text being typed right now
        changes = []
        for it in targets:
            f = QFont(it.font())
            if family is not None:
                f.setFamily(family)
            if size is not None:
                f.setPixelSize(size)
            if bold is not None:
                f.setBold(bold)
            if italic is not None:
                f.setItalic(italic)
            if f != it.font():
                if it._committed:
                    changes.append((it, QFont(it.font()), f))
                else:  # still being typed: not in the undo stack yet
                    it.setFont(f)
        if changes:
            self.stack.push(FontCommand(changes))

    def _add_text(self, p: QPointF):
        it = TextItem(self.color, self.text_font(), lambda i: self.stack.push(AddCommand(self.scene(), i)))
        it.setPos(p)
        self.scene().addItem(it)
        it.start_edit()

    def _add_step(self, p: QPointF):
        n = sum(isinstance(i, StepItem) for i in self.scene().items()) + 1
        it = StepItem(n, self.color)
        it.setPos(p)
        self.stack.push(AddCommand(self.scene(), it))

    # events --------------------------------------------------------------------------------

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        p = self.mapToScene(e.position().toPoint())
        if self.tool == "select":
            super().mousePressEvent(e)
            self._moving = {i: i.pos() for i in self.scene().selectedItems()}
            return
        self.scene().setFocusItem(None)
        if self.tool in ("crop", "cutv", "cuth"):
            hit = self._crop_hit(p) if self._crop else None
            if hit is None:
                self.discard_crop()
                self._crop = CropItem(QRectF(p, p), self.tool)
                self.scene().addItem(self._crop)
                hit = ("new",)
            self._crop_drag = (hit, p, self._crop.rect())
            return
        if self.tool == "text":
            self.scene().clearSelection()
            under = self.scene().itemAt(p, self.transform())
            if isinstance(under, TextItem):
                under.start_edit()
            else:
                self._add_text(p)
            return
        if self.tool == "step":
            return self._add_step(p)
        self._start = p
        self._item = self._make(p)
        if self._item is not None:
            self.scene().addItem(self._item)

    def mouseMoveEvent(self, e):
        p = self.mapToScene(e.position().toPoint())
        if self._crop_drag:
            return self._crop_update(p)
        if self._item is not None:
            return self._update(p)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._crop_drag:
            self._crop_drag = None
            r = self._crop.rect()
            if r.width() < 4 or r.height() < 4:
                self.discard_crop()
            else:
                self.cropActive.emit(True)
            return
        if self._item is not None:
            it, self._item = self._item, None
            if self._too_small(it):
                self.scene().removeItem(it)
            else:
                self.stack.push(AddCommand(self.scene(), it))
            return
        super().mouseReleaseEvent(e)
        if self._moving:
            moves = [(i, old, i.pos()) for i, old in self._moving.items() if i.pos() != old]
            self._moving = None
            if moves:
                self.stack.push(MoveCommand(moves))

    def keyPressEvent(self, e):
        if self.editing_text():
            if e.key() == Qt.Key_Escape:
                self.scene().setFocusItem(None)
            else:
                super().keyPressEvent(e)
            return
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            return self.delete_selected()
        if e.matches(QKeySequence.SelectAll):
            return self.select_all()
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self._crop:
            return self.apply_crop()
        if e.key() == Qt.Key_Escape:
            self.discard_crop()
            self.scene().clearSelection()
            return
        super().keyPressEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
            self.scale(f, f)
        else:
            super().wheelEvent(e)


# -- window ----------------------------------------------------------------------------------


def _swatch(color: QColor) -> QIcon:
    pm = QPixmap(48, 48)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(128, 128, 128), 2))
    p.setBrush(color)
    p.drawRoundedRect(5, 5, 38, 38, 8, 8)
    p.end()
    return QIcon(pm)


class EditorWindow(QMainWindow):
    closed = Signal(object)

    def __init__(self, image: QImage, library: Library, path: Path | None = None):
        super().__init__()
        self.library, self.path = library, path
        self.stack = QUndoStack(self)
        self.scene = CanvasScene(image)
        self.canvas = Canvas(self.scene, self.stack)
        self.setCentralWidget(self.canvas)
        self.setWindowTitle("ScreenCapture")
        self._build_toolbar()
        self.size_label = QLabel()
        self.statusBar().addPermanentWidget(self.size_label)
        self.scene.sceneRectChanged.connect(self._update_size)
        self.scene.sceneRectChanged.connect(lambda *_: QTimer.singleShot(0, self._fit))
        self.stack.cleanChanged.connect(lambda _: self._update_title())
        self._update_size()
        self._update_title()
        dpr = winutil.target_screen().devicePixelRatio()  # image pixels -> screen units
        winutil.size_and_place(self, max(int(image.width() / dpr) + 40, 900), max(int(image.height() / dpr) + 150, 560))
        QTimer.singleShot(0, self._fit)

    def _build_toolbar(self):
        n = icons.toolbar_pixels()
        tb = QToolBar("Tools", self)
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        tb.setIconSize(QSize(n, n))
        self.addToolBar(tb)
        group = QActionGroup(self)
        for key, label, hint in TOOLS:
            a = icons.tag(QAction(label, self, checkable=True), key)
            a.setToolTip(label)
            a.triggered.connect(lambda _=False, k=key, h=hint: self._choose_tool(k, h))
            group.addAction(a)
            tb.addAction(a)
            if key == "select":
                a.setChecked(True)
            if key in TOOL_GROUPS_END:
                tb.addSeparator()

        self.addToolBarBreak()  # second row: style, edit actions, output
        tb2 = QToolBar("Style", self)
        tb2.setMovable(False)
        tb2.setToolButtonStyle(Qt.ToolButtonIconOnly)
        tb2.setIconSize(QSize(n, n))
        self.addToolBar(tb2)
        self.color_action = QAction(_swatch(self.canvas.color), "Color", self)
        self.color_action.setToolTip("Annotation colour")
        self.color_action.triggered.connect(self._pick_color)
        tb2.addAction(self.color_action)
        self.width_box = QSpinBox()
        self.width_box.setRange(1, 40)
        self.width_box.setValue(self.canvas.width)
        self.width_box.setSuffix(" px")
        self.width_box.setToolTip("Line width")
        self.width_box.valueChanged.connect(lambda v: setattr(self.canvas, "width", v))
        tb2.addWidget(self.width_box)
        tb2.addSeparator()

        # text font: applies to new text and to the selected text
        self.font_box = QFontComboBox()
        self.font_box.setCurrentFont(QFont(self.canvas.font_family))
        self.font_box.setMaximumWidth(190)
        self.font_box.setToolTip("Text font")
        self.font_box.activated.connect(lambda _=0: self._style_changed(family=self.font_box.currentFont().family()))
        tb2.addWidget(self.font_box)
        self.font_size_box = QSpinBox()
        self.font_size_box.setRange(6, 300)
        self.font_size_box.setValue(self.canvas.font_size)
        self.font_size_box.setSuffix(" px")
        self.font_size_box.setToolTip("Text size")
        self.font_size_box.valueChanged.connect(lambda v: self._style_changed(size=v))
        tb2.addWidget(self.font_size_box)
        self.bold_action = icons.tag(QAction("Bold", self, checkable=True), "bold")
        self.bold_action.setToolTip("Bold text")
        self.bold_action.toggled.connect(lambda on: self._style_changed(bold=on))
        tb2.addAction(self.bold_action)
        self.italic_action = icons.tag(QAction("Italic", self, checkable=True), "italic")
        self.italic_action.setToolTip("Italic text")
        self.italic_action.toggled.connect(lambda on: self._style_changed(italic=on))
        tb2.addAction(self.italic_action)
        tb2.addSeparator()

        self.apply_crop_action = self._act(tb2, "apply", "Apply crop / cut (Enter)", None, self.canvas.apply_crop)
        self.apply_crop_action.setEnabled(False)
        self.canvas.cropActive.connect(self.apply_crop_action.setEnabled)
        undo = self.stack.createUndoAction(self, "Undo")
        undo.setShortcut(QKeySequence.Undo)
        icons.tag(undo, "undo")
        redo = self.stack.createRedoAction(self, "Redo")
        redo.setShortcut(QKeySequence.Redo)
        icons.tag(redo, "redo")
        tb2.addAction(undo)
        tb2.addAction(redo)
        self.delete_action = self._act(tb2, "trash", "Delete selected (Delete)", None, self.canvas.delete_selected)
        self.delete_action.setEnabled(False)
        self.scene.selectionChanged.connect(self._sync_delete_action)
        self.scene.selectionChanged.connect(self._sync_font_controls)
        tb2.addSeparator()
        self._act(tb2, "copy", "Copy image to clipboard (Ctrl+Shift+C)", "Ctrl+Shift+C", self.copy_to_clipboard)
        self._act(tb2, "save", "Save to library (Ctrl+S)", QKeySequence.Save, self.save)
        self._act(tb2, "saveas", "Save as… (Ctrl+Shift+S)", QKeySequence.SaveAs, self.save_as)

    def _style_changed(self, **kw):
        self.canvas.set_text_style(**kw)
        self.canvas.viewport().setFocus()  # so Delete / Enter reach the canvas again

    def _sync_font_controls(self):
        """Show the font of the selected text in the controls (without re-applying it)."""
        try:
            texts = [i for i in self.canvas.scene().selectedItems() if isinstance(i, TextItem)]
            if len(texts) != 1:
                return
            f = texts[0].font()
            widgets = (self.font_box, self.font_size_box, self.bold_action, self.italic_action)
            for w in widgets:
                w.blockSignals(True)
            self.font_box.setCurrentFont(f)
            self.font_size_box.setValue(f.pixelSize() if f.pixelSize() > 0 else self.canvas.font_size)
            self.bold_action.setChecked(f.bold())
            self.italic_action.setChecked(f.italic())
            for w in widgets:
                w.blockSignals(False)
            self.canvas.font_family, self.canvas.font_size = f.family(), self.font_size_box.value()
            self.canvas.font_bold, self.canvas.font_italic = f.bold(), f.italic()
        except (RuntimeError, AttributeError):  # window is being torn down
            pass

    def _sync_delete_action(self):
        try:
            self.delete_action.setEnabled(bool(self.canvas.selected_annotations()))
        except (RuntimeError, AttributeError):  # window is being torn down
            pass

    def _choose_tool(self, key: str, hint: str):
        self.canvas.set_tool(key)
        self.statusBar().showMessage(hint)

    def _act(self, tb, icon_name, tip, shortcut, slot):
        a = icons.tag(QAction(tip, self), icon_name)
        a.setToolTip(tip)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(lambda _=False: slot())
        tb.addAction(a)
        return a

    # actions -------------------------------------------------------------------------------

    def _pick_color(self):
        c = QColorDialog.getColor(self.canvas.color, self, "Annotation color")
        if c.isValid():
            self.canvas.color = c
            self.color_action.setIcon(_swatch(c))

    def image(self) -> QImage:
        return self.canvas.render_image()

    def copy_to_clipboard(self):
        QGuiApplication.clipboard().setImage(self.image())
        self.statusBar().showMessage("Copied to clipboard", 3000)

    def save(self) -> bool:
        img = self.image()
        if self.path is None:
            self.path = self.library.add(img)
        else:
            self.library.save(self.path, img)
        self.stack.setClean()
        self.statusBar().showMessage(f"Saved to library: {self.path.name}", 3000)
        return True

    def save_as(self):
        start = str(Path.home() / "Pictures" / (self.path.name if self.path else "capture.png"))
        fn, _ = QFileDialog.getSaveFileName(self, "Save image", start, "PNG image (*.png);;JPEG image (*.jpg)")
        if fn:
            self.image().save(fn)
            self.statusBar().showMessage(f"Saved {fn}", 3000)

    # window plumbing -----------------------------------------------------------------------

    def _fit(self):
        try:
            self._fit_now()
        except RuntimeError:  # queued call that ran after the window was deleted
            pass

    def _fit_now(self):
        r = self.scene.sceneRect()
        vp = self.canvas.viewport().size()
        if r.width() > vp.width() or r.height() > vp.height():
            self.canvas.fitInView(r, Qt.KeepAspectRatio)
        else:
            self.canvas.resetTransform()

    def _update_size(self, *_):
        try:
            r = self.scene.sceneRect()
            self.size_label.setText(f"{int(r.width())} × {int(r.height())}")
        except RuntimeError:
            pass

    def _update_title(self):
        try:
            clean = self.stack.isClean()
        except RuntimeError:  # stack already destroyed while the window is being torn down
            return
        name = self.path.name if self.path else "untitled"
        self.setWindowTitle(f"{name}{'' if clean else ' *'} — ScreenCapture")

    def showEvent(self, e):
        super().showEvent(e)
        winutil.schedule_ensure_on_screen(self)

    def closeEvent(self, e):
        if not self.stack.isClean():
            b = QMessageBox.question(
                self,
                "ScreenCapture",
                "Save changes to the library?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if b == QMessageBox.Cancel:
                return e.ignore()
            if b == QMessageBox.Save:
                self.save()
        for sig, slot in ((self.scene.selectionChanged, self._sync_delete_action), (self.scene.selectionChanged, self._sync_font_controls),):
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self.closed.emit(self)
        e.accept()
