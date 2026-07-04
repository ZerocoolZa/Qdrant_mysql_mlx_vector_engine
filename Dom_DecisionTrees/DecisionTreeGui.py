#!/usr/bin/env python3
#[@GHOST]{("file_path=Dom_DecisionTrees/DecisionTreeGui.py";"identity=DecisionTreeGui.py";"purpose=Config-driven GUI using core.Dom_Gui engine";"date=2026-06-28";"version=2.0";"author=Cascade";"chat_link=")}
#[@VBSTYLE]{[@pass]{"return=Tuple3";"dispatch=Run";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete"}[@fail]{"decorators_found";"print_found";"hardcoded_values";"self._used"}}
#[@FILEID]{("session_id=auto";"context=Auto-stamped by header watcher";"purpose=")}
#[@SUMMARY]{("Created on 2026-06-28";"auto_stamped=true";"version=2.0 — uses core.Dom_Gui parser/builder/router engine")}

#!/usr/bin/env python3
"""
DecisionTreeGui v2.0 — Config-driven GUI using core.Dom_Gui engine.

Shell (main window, panels, splitter, tabs, combos, buttons, search) is built
from WCL declarations in Config.py via GUIParser + GUIBuilder + EventRouter.

Canvas (DecisionTreeCanvas with draggable nodes, edges, BCL mode) remains
domain-specific and is inserted post-build.

Left: JSON editor (live config that drives the tree).
Right: Canvas with boxes + arrows rendering a real decision tree.
Reads Config.py for DB path, settings, WCL declarations, color schemes.
"""

import sys
import json
import sqlite3
import math
from pathlib import Path

# ─── core.Dom_Gui engine imports ────────────────────────────────────────────
CORE_DIR = str(Path(__file__).resolve().parent.parent / "core")
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from Dom_Gui import GUIParser, GUIBuilder
from Dom_Gui.bus import GuiBus

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QTreeWidget,
    QTreeWidgetItem, QPlainTextEdit, QLabel, QVBoxLayout, QHBoxLayout,
    QStatusBar, QMenuBar, QMenu, QFileDialog, QMessageBox, QTabWidget,
    QHeaderView, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsEllipseItem,
    QGraphicsPolygonItem, QGraphicsPathItem,
    QStyle, QPushButton, QComboBox, QSpinBox, QLineEdit, QInputDialog,
    QDialog, QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, QSize, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QFont, QColor, QAction, QSyntaxHighlighter, QTextCharFormat,
    QPen, QBrush, QPainter, QPolygonF, QPixmap, QImage, QPainterPath
)

from Config import (
    DB_PATH, SOURCES, DESCRIPTIONS, PURPOSES, LOCAL_MODULES,
    TREE_CONFIG_DEFAULT, COLOR_SCHEMES, BCL_NODE_COLORS, NODE_RADIUS,
    WCL_CONFIG
)


class JsonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []
        fmt_key = QTextCharFormat()
        fmt_key.setForeground(QColor("#89b4fa"))
        fmt_key.setFontWeight(QFont.Weight.Bold)
        self.rules.append((r'"[^"]*"\s*:', fmt_key))
        fmt_str = QTextCharFormat()
        fmt_str.setForeground(QColor("#a6e3a1"))
        self.rules.append((r'"[^"]*"', fmt_str))
        fmt_num = QTextCharFormat()
        fmt_num.setForeground(QColor("#f9e2af"))
        self.rules.append((r'\b\d+\b', fmt_num))
        fmt_bool = QTextCharFormat()
        fmt_bool.setForeground(QColor("#f5c2e7"))
        self.rules.append((r'\b(true|false|null)\b', fmt_bool))

    def highlightBlock(self, text):
        import re
        for pattern, fmt in self.rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class TreeNode:
    """Logical tree node for layout calculation."""
    def __init__(self, label, node_type, detail="", data=None):
        self.label = label
        self.node_type = node_type
        self.detail = detail
        self.data = data or {}
        self.children = []
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.depth = 0
        self.bcl_node = None
        self.rect_item = None

    def add_child(self, child):
        child.depth = self.depth + 1
        self.children.append(child)


class MovableNodeItem(QGraphicsRectItem):
    """A canvas node you can drag. Notifies attached edges when it moves so they redraw.

    Stores a back-ref to its TreeNode (so positions persist + the GUI can inspect it) and
    to the canvas (so context menus / connect-mode can reach back). Rounded corners are
    drawn by overriding paint(); shape() returns a rounded-rect path so hit-testing matches
    the visual (not the sharp bounding rect).
    """

    def __init__(self, rect, tree_node, canvas, parent=None):
        super().__init__(rect, parent)
        self.tree_node = tree_node
        self.canvas = canvas
        self.edges = []
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.base_pen = self.pen()

    def add_edge(self, edge):
        if edge not in self.edges:
            self.edges.append(edge)

    def remove_edge(self, edge):
        if edge in self.edges:
            self.edges.remove(edge)

    def set_selected_visual(self, selected):
        if selected:
            pen = QPen(QColor("#ffffff"), 2)
            pen.setStyle(Qt.PenStyle.DashLine)
        else:
            pen = self.base_pen
        self.setPen(pen)

    def set_search_highlight(self, on):
        if on:
            self.setPen(QPen(QColor("#facc15"), 3))
        else:
            self.setPen(self.base_pen)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            self.tree_node.x = self.scenePos().x()
            self.tree_node.y = self.scenePos().y()
            for edge in self.edges:
                edge.update_path()
        if change == QGraphicsRectItem.GraphicsItemChange.ItemSelectedHasChanged:
            pass
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), NODE_RADIUS, NODE_RADIUS)

    def shape(self):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), NODE_RADIUS, NODE_RADIUS)
        return path

    def boundingRect(self):
        return self.rect().adjusted(-2, -2, 2, 2)


class EdgeItem(QGraphicsPathItem):
    """A directed edge between two MovableNodeItems. Recomputes its curve + arrowhead
    whenever either endpoint moves. The arrow attaches to the node's border (not its
    center) by intersecting the center-line with the source/dest rect.
    """

    def __init__(self, source, dest, color, parent=None):
        super().__init__(parent)
        self.source = source
        self.dest = dest
        self.color = color
        self.setPen(QPen(QColor(color), 2))
        self.setZValue(-1)
        source.add_edge(self)
        dest.add_edge(self)
        self.update_path()

    def update_path(self):
        src_pos = self.source.scenePos()
        dst_pos = self.dest.scenePos()
        src_center = QPointF(src_pos.x() + self.source.rect().width() / 2,
                             src_pos.y() + self.source.rect().height() / 2)
        dst_center = QPointF(dst_pos.x() + self.dest.rect().width() / 2,
                             dst_pos.y() + self.dest.rect().height() / 2)
        start = self.border_point_from_center(src_center, self.source.rect(), dst_center)
        end = self.border_point_from_center(dst_center, self.dest.rect(), src_center)
        path = QPainterPath()
        path.moveTo(start)
        ctrl = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
        path.quadTo(ctrl, end)
        self.setPath(path)

    def border_point_from_center(self, center, rect, toward):
        dx = toward.x() - center.x()
        dy = toward.y() - center.y()
        if dx == 0 and dy == 0:
            return QPointF(center.x(), center.y())
        rx = rect.width() / 2.0
        ry = rect.height() / 2.0
        sx = rx / dx if dx != 0 else float("inf")
        sy = ry / dy if dy != 0 else float("inf")
        s = min(abs(sx), abs(sy))
        return QPointF(center.x() + dx * s, center.y() + dy * s)


class DecisionTreeCanvas(QGraphicsView):
    """Canvas that renders the decision tree with boxes and arrows.

    Modes:
      - "code":    tree from decision_trees.db (files/methods/classes)
      - "bcl":     tree from a parsed .bcl file (Pass/Fail/Unsure colored)
      - "deps":    directed graph of cross-file imports
    Emits nodeSelected(TreeNode) when a node is clicked.
    """

    nodeSelected = pyqtSignal(object)
    nodeCreated = pyqtSignal(object)
    nodeDeleted = pyqtSignal(object)
    nodeRenamed = pyqtSignal(object, str)
    edgeCreated = pyqtSignal(object, object)
    statusHint = pyqtSignal(str)
    labelEditRequested = pyqtSignal(object)

    def __init__(self, colors):
        super().__init__()
        self.colors = colors
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.node_items = {}
        self.rect_to_node = {}
        self.edges = []
        self.edge_by_endpoints = {}
        self.root_node = None
        self.config = {}
        self.mode = "code"
        self.zoom = 1.0
        self.selected_rect = None
        self.search_highlight = set()
        self.connect_source = None
        self.last_pan_pos = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def set_colors(self, colors):
        self.colors = colors
        self.scene.setBackgroundBrush(QBrush(QColor(colors["canvas_bg"])))

    def set_config(self, config):
        self.config = config

    def set_mode(self, mode):
        self.mode = mode

    def build_tree(self, root_node):
        self.root_node = root_node
        self.scene.clear()
        self.scene.setBackgroundBrush(QBrush(QColor(self.colors["canvas_bg"])))
        self.node_items = {}
        self.rect_to_node = {}
        self.edges = []
        self.edge_by_endpoints = {}
        self.selected_rect = None
        self.search_highlight = set()
        self.connect_source = None
        if root_node is None:
            return
        self.layout_tree(root_node)
        if self.mode == "deps":
            self.draw_graph(root_node)
        else:
            self.draw_tree(root_node)
        self.fit_view()

    def layout_tree(self, root):
        cfg = self.config
        spacing_x = cfg.get("node_spacing_x", 200)
        spacing_y = cfg.get("node_spacing_y", 80)
        node_w = cfg.get("node_width", 160)
        node_h = cfg.get("node_height", 40)
        orientation = cfg.get("orientation", "vertical")

        def assign_positions(node, x_offset, depth):
            node.depth = depth
            if orientation == "vertical":
                node.y = depth * spacing_y
                if not node.children:
                    node.x = x_offset
                    node.width = node_w
                    node.height = node_h
                    return node_w + spacing_x
                total_w = 0
                for child in node.children:
                    child_w = assign_positions(child, x_offset + total_w, depth + 1)
                    total_w += child_w
                node.x = x_offset + total_w / 2 - node_w / 2
                node.width = node_w
                node.height = node_h
                return total_w
            else:
                node.x = depth * spacing_x
                if not node.children:
                    node.y = x_offset
                    node.width = node_w
                    node.height = node_h
                    return node_h + spacing_y
                total_h = 0
                for child in node.children:
                    child_h = assign_positions(child, x_offset + total_h, depth + 1)
                    total_h += child_h
                node.y = x_offset + total_h / 2 - node_h / 2
                node.width = node_w
                node.height = node_h
                return total_h

        assign_positions(root, 0, 0)
        saved = cfg.get("saved_layout", {})
        if saved:
            def apply_saved(n):
                pos = saved.get(n.label)
                if pos:
                    n.x = pos.get("x", n.x)
                    n.y = pos.get("y", n.y)
                for c in n.children:
                    apply_saved(c)
            apply_saved(root)

    def node_fill_border(self, node):
        c = self.colors
        if self.mode == "bcl":
            nt = node.node_type
            if nt in BCL_NODE_COLORS:
                return BCL_NODE_COLORS[nt]
            return (c["text"], c["bg"])
        type_colors = {
            "ROOT": (c["root"], c["root_bg"]),
            "Category": (c["category"], c["category_bg"]),
            "File": (c["file"], c["file_bg"]),
            "Class": (c["class"], c["category_bg"]),
            "Method": (c["method"], c["method_bg"]),
            "DepFile": (c["file"], c["file_bg"]),
            "DepFileLocal": (c["class"], c["root_bg"]),
        }
        return type_colors.get(node.node_type, (c["text"], c["bg"]))

    def draw_tree(self, node):
        border_color, bg_color = self.node_fill_border(node)

        rect_item = MovableNodeItem(QRectF(0, 0, node.width, node.height), node, self)
        base_pen = QPen(QColor(border_color), 2)
        rect_item.setPen(base_pen)
        rect_item.base_pen = base_pen
        rect_item.setBrush(QBrush(QColor(bg_color)))
        rect_item.setPos(node.x, node.y)

        label = node.label
        if self.mode == "bcl" and node.data.get("weight") is not None:
            label = f"{node.label}  [{node.data['weight']}]"
        text_item = QGraphicsTextItem(label)
        font = QFont("SF Pro", 10)
        if node.node_type in ("ROOT", "Rule"):
            font.setBold(True)
            font.setPointSize(12)
        elif node.node_type in ("Category", "Pass", "Fail", "Unsure", "Check"):
            font.setBold(True)
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor(border_color))
        text_w = text_item.boundingRect().width()
        text_h = text_item.boundingRect().height()
        text_item.setPos((node.width - text_w) / 2, (node.height - text_h) / 2)
        text_item.setParentItem(rect_item)

        rect_item.setData(0, node.data)
        node.rect_item = rect_item
        self.node_items[id(node)] = rect_item
        self.rect_to_node[id(rect_item)] = node
        self.scene.addItem(rect_item)

        if id(node) in self.search_highlight:
            rect_item.set_search_highlight(True)

        for child in node.children:
            self.draw_tree(child)
            edge = EdgeItem(rect_item, child.rect_item, self.colors["arrow"])
            self.edges.append(edge)
            self.edge_by_endpoints[(id(node), id(child))] = edge

    def draw_graph(self, root):
        self.draw_tree(root)

    def select_node(self, node, rect_item):
        if self.selected_rect is not None and self.selected_rect is not rect_item:
            prev_node = self.rect_to_node.get(id(self.selected_rect))
            if prev_node is not None and id(prev_node) not in self.search_highlight:
                self.selected_rect.set_selected_visual(False)
        if id(node) in self.search_highlight:
            rect_item.set_search_highlight(True)
        else:
            rect_item.set_selected_visual(True)
        self.selected_rect = rect_item

    def highlight_search(self, query):
        self.search_highlight = set()
        if self.root_node is None:
            return 0
        q = query.strip().lower()
        for rect_item in self.node_items.values():
            rect_item.set_search_highlight(False)
            rect_item.set_selected_visual(rect_item.isSelected())
        if not q:
            return 0
        count = 0
        def walk(n):
            nonlocal count
            if q in n.label.lower():
                self.search_highlight.add(id(n))
                count += 1
            for ch in n.children:
                walk(ch)
        walk(self.root_node)
        for node_id, rect_item in self.node_items.items():
            if node_id in self.search_highlight:
                rect_item.set_search_highlight(True)
        return count

    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        item = self.node_at(scene_pos)
        if event.button() == Qt.MouseButton.LeftButton:
            if item is not None:
                node = self.rect_to_node.get(id(item))
                if node is not None:
                    if self.connect_source is not None:
                        self.try_connect(self.connect_source, item)
                        self.connect_source = None
                        event.accept()
                        return
                    self.select_node(node, item)
                    self.nodeSelected.emit(node)
            else:
                if self.connect_source is not None:
                    self.connect_source = None
                    self.statusHint.emit("Connect cancelled")
                if self.selected_rect is not None:
                    prev = self.rect_to_node.get(id(self.selected_rect))
                    if prev is not None and id(prev) not in self.search_highlight:
                        self.selected_rect.set_selected_visual(False)
                    self.selected_rect = None
        super().mousePressEvent(event)

    def node_at(self, scene_pos):
        item = self.scene.itemAt(scene_pos, self.viewportTransform())
        while item is not None and not isinstance(item, MovableNodeItem):
            item = item.parentItem()
        return item if isinstance(item, MovableNodeItem) else None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            item = self.node_at(scene_pos)
            if item is not None:
                node = self.rect_to_node.get(id(item))
                if node is not None:
                    self.select_node(node, item)
                    self.nodeSelected.emit(node)
                    self.labelEditRequested.emit(node)
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and \
           event.modifiers() & Qt.KeyboardModifier.ControlModifier and \
           self.last_pan_pos is not None:
            delta = event.pos() - self.last_pan_pos
            self.last_pan_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    def delete_selected(self):
        if self.selected_rect is None:
            return
        node = self.rect_to_node.get(id(self.selected_rect))
        if node is None:
            return
        for edge in list(self.selected_rect.edges):
            self.remove_edge(edge)
        def detach(tree, target):
            tree.children = [c for c in tree.children if c is not target]
            for c in tree.children:
                detach(c, target)
        if self.root_node is not None:
            detach(self.root_node, node)
        self.node_items.pop(id(node), None)
        self.rect_to_node.pop(id(self.selected_rect), None)
        self.scene.removeItem(self.selected_rect)
        self.selected_rect = None
        self.nodeDeleted.emit(node)

    def remove_edge(self, edge):
        edge.source.remove_edge(edge)
        edge.dest.remove_edge(edge)
        for key, val in list(self.edge_by_endpoints.items()):
            if val is edge:
                del self.edge_by_endpoints[key]
                break
        if edge in self.edges:
            self.edges.remove(edge)
        self.scene.removeItem(edge)

    def try_connect(self, source_item, dest_item):
        src_node = self.rect_to_node.get(id(source_item))
        dst_node = self.rect_to_node.get(id(dest_item))
        if src_node is None or dst_node is None or src_node is dst_node:
            return
        if (id(src_node), id(dst_node)) in self.edge_by_endpoints:
            return
        edge = EdgeItem(source_item, dest_item, self.colors["arrow"])
        self.edges.append(edge)
        self.edge_by_endpoints[(id(src_node), id(dst_node))] = edge
        if dst_node not in src_node.children:
            src_node.children.append(dst_node)
            dst_node.depth = src_node.depth + 1
        self.edgeCreated.emit(src_node, dst_node)

    def begin_connect(self, source_item):
        self.connect_source = source_item
        self.statusHint.emit("Connect: click a target node (or empty space to cancel)")

    def add_node_at(self, scene_pos, label, node_type):
        cfg = self.config
        w = cfg.get("node_width", 160)
        h = cfg.get("node_height", 40)
        parent_node = self.root_node
        if self.selected_rect is not None:
            sel = self.rect_to_node.get(id(self.selected_rect))
            if sel is not None:
                parent_node = sel
        new_node = TreeNode(label, node_type, "", {"type": "canvas_added"})
        new_node.x = scene_pos.x() - w / 2
        new_node.y = scene_pos.y() - h / 2
        new_node.width = w
        new_node.height = h
        if parent_node is not None:
            parent_node.add_child(new_node)
        border_color, bg_color = self.node_fill_border(new_node)
        rect_item = MovableNodeItem(QRectF(0, 0, w, h), new_node, self)
        base_pen = QPen(QColor(border_color), 2)
        rect_item.setPen(base_pen)
        rect_item.base_pen = base_pen
        rect_item.setBrush(QBrush(QColor(bg_color)))
        rect_item.setPos(new_node.x, new_node.y)
        text_item = QGraphicsTextItem(label)
        text_item.setFont(QFont("SF Pro", 10))
        text_item.setDefaultTextColor(QColor(border_color))
        tw = text_item.boundingRect().width()
        th = text_item.boundingRect().height()
        text_item.setPos((w - tw) / 2, (h - th) / 2)
        text_item.setParentItem(rect_item)
        self.node_items[id(new_node)] = rect_item
        self.rect_to_node[id(rect_item)] = new_node
        self.scene.addItem(rect_item)
        if parent_node is not None and parent_node.rect_item is not None:
            edge = EdgeItem(parent_node.rect_item, rect_item, self.colors["arrow"])
            self.edges.append(edge)
            self.edge_by_endpoints[(id(parent_node), id(new_node))] = edge
        self.nodeCreated.emit(new_node)
        return new_node

    def rename_selected(self, new_label):
        if self.selected_rect is None:
            return
        node = self.rect_to_node.get(id(self.selected_rect))
        if node is None:
            return
        node.label = new_label
        for child in list(self.selected_rect.childItems()):
            child.setParentItem(None)
            if child.scene() is self.scene:
                self.scene.removeItem(child)
        label = new_label
        if self.mode == "bcl" and node.data.get("weight") is not None:
            label = f"{new_label}  [{node.data['weight']}]"
        text_item = QGraphicsTextItem(label)
        text_item.setFont(QFont("SF Pro", 10))
        border, _ = self.node_fill_border(node)
        text_item.setDefaultTextColor(QColor(border))
        tw = text_item.boundingRect().width()
        th = text_item.boundingRect().height()
        text_item.setPos((node.width - tw) / 2, (node.height - th) / 2)
        text_item.setParentItem(self.selected_rect)
        self.nodeRenamed.emit(node, new_label)

    def selected_node(self):
        if self.selected_rect is None:
            return None
        return self.rect_to_node.get(id(self.selected_rect))

    def scene_position_of(self, item):
        return item.scenePos()

    def start_pan(self, pos):
        self.last_pan_pos = pos

    def stop_pan(self):
        self.last_pan_pos = None

    def export_png(self, path):
        if not self.scene.items():
            return False
        rect = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
        img = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(painter, QRectF(img.rect()), rect)
        painter.end()
        return img.save(path, "PNG")

    def fit_view(self):
        if self.scene.items():
            self.fitInView(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self.resetTransform()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom *= 1.15
            else:
                self.zoom /= 1.15
            self.zoom = max(0.1, min(5.0, self.zoom))
            self.resetTransform()
            self.scale(self.zoom, self.zoom)
        else:
            super().wheelEvent(event)

    def reset_zoom(self):
        self.zoom = 1.0
        self.resetTransform()
        self.fit_view()


# ─── HOST APPLICATION (uses core.Dom_Gui engine for shell) ──────────────────

class DecisionTreeGui(QMainWindow):
    """Decision Tree GUI v2.0 — config-driven shell via core.Dom_Gui engine.

    The GUI shell (window, panels, splitter, tabs, combos, buttons, search bar)
    is built from WCL declarations in Config.py using GUIParser + GUIBuilder +
    EventRouter. The canvas (custom QGraphicsView with draggable nodes) and all
    domain logic (tree building, DB queries, BCL mode, dependency mode) remain
    in this class as handler methods the router connects to.
    """

    def __init__(self):
        super().__init__()
        self.state = {}
        self.db_path = str(DB_PATH)
        self.conn = None
        self.tree_config = dict(TREE_CONFIG_DEFAULT)
        self.colors = COLOR_SCHEMES.get(self.tree_config.get("color_scheme", "dark"), COLOR_SCHEMES["dark"])
        self.mode = "code"
        self.bcl_path = None
        self.bcl_root = None
        self.bcl_parser = None
        self.bcl_lexer = None
        self.bus = GuiBus()
        self.load_bcl_engine()
        self.load_config_file()
        self.build_shell()
        self.post_build()
        self.connect_db()
        self.rebuild_tree()
        self.statusBar().showMessage(f"DB: {self.db_path}  |  Mode: code  |  Ctrl+scroll to zoom  |  Click a node")

    # ─── Engine: parse WCL + build shell ────────────────────────────────────

    def build_shell(self):
        """Parse WCL declarations from Config.py and build the GUI shell via core.Dom_Gui engine."""
        parser = GUIParser()
        parser.parse_string(WCL_CONFIG)
        tree = parser.nodes
        signals = parser.get_signals()
        gui_meta = parser.get_gui_meta()

        if "title" in gui_meta:
            self.setWindowTitle(gui_meta["title"])
        if "size" in gui_meta:
            parts = gui_meta["size"].split("x")
            if len(parts) == 2:
                self.resize(int(parts[0]), int(parts[1]))
        self.setMinimumSize(QSize(900, 600))

        builder = GUIBuilder(host=self)
        self.widgets = builder.build(tree, signals)
        self.builder = builder
        self.parser = parser

        # Set central widget (engine builds it as a root node, not auto-set)
        if "central" in self.widgets:
            self.setCentralWidget(self.widgets["central"])

        self.apply_style()

    def post_build(self):
        """After engine builds the shell, populate combos, create canvas, setup menus."""
        w = self.widgets

        # Promote widgets to attributes for backward-compat with domain logic
        self.json_editor = w["json_editor"]
        self.mode_combo = w["mode_combo"]
        self.group_combo = w["group_combo"]
        self.orient_combo = w["orient_combo"]
        self.max_spin = w["max_spin"]
        self.rebuild_btn = w["rebuild_btn"]
        self.reset_zoom_btn = w["reset_zoom_btn"]
        self.search_box = w["search_box"]
        self.search_clear_btn = w["search_clear_btn"]
        self.tabs = w["tabs"]
        self.code_preview = w["code_preview"]
        self.bcl_preview = w["bcl_preview"]
        self.dep_preview = w["dep_preview"]
        self.bcl_editor = w["bcl_editor"]
        self.splitter = w["splitter"]

        # Populate combos (engine doesn't handle items)
        # Block signals — setCurrentText fires on_mode_changed -> rebuild_tree
        # which needs self.canvas, not yet created at this point.
        self.mode_combo.blockSignals(True)
        self.mode_combo.addItems(["code", "bcl", "deps"])
        self.mode_combo.setCurrentText("code")
        self.mode_combo.blockSignals(False)
        self.group_combo.blockSignals(True)
        self.group_combo.addItems(["category", "file", "class"])
        self.group_combo.setCurrentText(self.tree_config.get("group_by", "category"))
        self.group_combo.blockSignals(False)
        self.orient_combo.blockSignals(True)
        self.orient_combo.addItems(["vertical", "horizontal"])
        self.orient_combo.setCurrentText(self.tree_config.get("orientation", "vertical"))
        self.orient_combo.blockSignals(False)

        # Spinbox range (engine doesn't handle min/max)
        self.max_spin.blockSignals(True)
        self.max_spin.setRange(5, 200)
        self.max_spin.setValue(self.tree_config.get("max_methods_per_node", 30))
        self.max_spin.blockSignals(False)

        # Timer for live JSON updates (debounced) — must exist before json_editor fires
        self.json_timer = QTimer()
        self.json_timer.setSingleShot(True)
        self.json_timer.timeout.connect(self.on_json_changed)

        # JSON editor setup — block signals to prevent textChanged firing before ready
        self.json_editor.blockSignals(True)
        self.json_editor.setPlainText(json.dumps(self.tree_config, indent=2))
        self.json_editor.blockSignals(False)
        self.highlighter = JsonHighlighter(self.json_editor.document())
        self.json_editor.setFont(QFont("Menlo", 12))

        # Preview tab fonts
        for name in ("code_preview", "bcl_preview", "dep_preview", "bcl_editor"):
            self.widgets[name].setFont(QFont("Menlo", 11))

        # Create canvas (custom widget — engine can't build it)
        self.canvas = DecisionTreeCanvas(self.colors)
        self.canvas.set_config(self.tree_config)
        self.canvas.set_mode("code")
        self.canvas.nodeSelected.connect(self.on_node_selected)
        self.canvas.nodeCreated.connect(self.on_node_created)
        self.canvas.nodeDeleted.connect(self.on_node_deleted)
        self.canvas.nodeRenamed.connect(self.on_node_renamed)
        self.canvas.edgeCreated.connect(self.on_edge_created)
        self.canvas.statusHint.connect(lambda m: self.statusBar().showMessage(m) if self.statusBar() else None)
        self.canvas.customContextMenuRequested.connect(self.on_canvas_context_menu)
        self.canvas.labelEditRequested.connect(self.on_label_edit_requested)

        # Insert canvas as first tab (before the engine-built tabs)
        self.tabs.insertTab(0, self.canvas, "Decision Tree Canvas")
        self.tabs.setCurrentIndex(0)

        # Splitter sizes
        self.splitter.setSizes([380, 1020])

        # Menus (built manually — engine menu support is limited)
        self.setup_menu()
        self.setStatusBar(QStatusBar())

        # (json_timer created earlier, before json_editor setup)

    # ─── BCL engine loader ──────────────────────────────────────────────────

    def load_bcl_engine(self):
        """Add core/Dom_Bcl to sys.path and import the BCL lexer/parser for BCL mode."""
        bcl_dir = str(Path(__file__).resolve().parent.parent / "core" / "Dom_Bcl")
        if bcl_dir not in sys.path:
            sys.path.insert(0, bcl_dir)
        try:
            from bcl_lexer import BCLTokenizer
            from bcl_parser import BCLParser
            self.bcl_lexer = BCLTokenizer()
            self.bcl_parser = BCLParser()
        except Exception as e:
            self.bcl_lexer = None
            self.bcl_parser = None
            self.bcl_import_error = str(e)

    # ─── Config file load/save ──────────────────────────────────────────────

    def load_config_file(self):
        cfg_path = Path(__file__).parent / "tree_config.json"
        if cfg_path.exists():
            try:
                loaded = json.loads(cfg_path.read_text())
                self.tree_config.update(loaded)
            except Exception:
                pass
        self.colors = COLOR_SCHEMES.get(self.tree_config.get("color_scheme", "dark"), COLOR_SCHEMES["dark"])

    def save_config_file(self):
        cfg_path = Path(__file__).parent / "tree_config.json"
        cfg_path.write_text(json.dumps(self.tree_config, indent=2))

    # ─── DB connection ──────────────────────────────────────────────────────

    def connect_db(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Cannot open DB:\n{self.db_path}\n\n{e}")

    # ─── Style ──────────────────────────────────────────────────────────────

    def apply_style(self):
        c = self.colors
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background-color: {c['bg']}; color: {c['text']}; }}
            QPlainTextEdit {{
                background-color: {c['bg']};
                color: {c['text']};
                border: 1px solid {c['border']};
                font-size: 12px;
            }}
            QLineEdit {{
                background-color: {c['bg']};
                color: {c['text']};
                border: 1px solid {c['border']};
                padding: 2px 4px;
            }}
            QTabWidget::pane {{ border: 1px solid {c['border']}; }}
            QTabBar::tab {{
                background-color: {c['bg']};
                color: {c['text']};
                padding: 6px 16px;
                border: 1px solid {c['border']};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{ background-color: {c['selection']}; }}
            QLabel {{ color: {c['text']}; }}
            QStatusBar {{ background-color: {c['bg']}; color: {c['text']}; border-top: 1px solid {c['border']}; }}
            QMenuBar {{ background-color: {c['bg']}; color: {c['text']}; }}
            QMenuBar::item:selected {{ background-color: {c['selection']}; }}
            QMenu {{ background-color: {c['bg']}; color: {c['text']}; }}
            QMenu::item:selected {{ background-color: {c['selection']}; }}
            QPushButton {{
                background-color: {c['selection']};
                color: {c['text']};
                border: 1px solid {c['border']};
                padding: 4px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {c['border']}; }}
            QComboBox {{
                background-color: {c['selection']};
                color: {c['text']};
                border: 1px solid {c['border']};
                padding: 2px 6px;
            }}
            QSpinBox {{
                background-color: {c['selection']};
                color: {c['text']};
                border: 1px solid {c['border']};
            }}
        """)

    # ─── Menu setup (manual — engine menu support is limited) ────────────────

    def setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        act_rebuild = QAction("Rebuild Tree", self)
        act_rebuild.triggered.connect(self.rebuild_tree)
        file_menu.addAction(act_rebuild)
        act_save = QAction("Save Config", self)
        act_save.triggered.connect(self.save_config)
        file_menu.addAction(act_save)
        file_menu.addSeparator()
        act_open_bcl = QAction("Open BCL File...", self)
        act_open_bcl.triggered.connect(self.open_bcl_file)
        file_menu.addAction(act_open_bcl)
        act_save_bcl = QAction("Save BCL File", self)
        act_save_bcl.triggered.connect(self.save_bcl_file)
        file_menu.addAction(act_save_bcl)
        file_menu.addSeparator()
        act_export_png = QAction("Export Canvas as PNG...", self)
        act_export_png.triggered.connect(self.export_png)
        file_menu.addAction(act_export_png)
        file_menu.addSeparator()
        act_save_layout = QAction("Save Layout to Config", self)
        act_save_layout.triggered.connect(self.save_layout)
        file_menu.addAction(act_save_layout)
        file_menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        db_menu = menubar.addMenu("Database")
        act_stats = QAction("DB Stats", self)
        act_stats.triggered.connect(self.show_stats)
        db_menu.addAction(act_stats)
        act_refresh = QAction("Reconnect DB", self)
        act_refresh.triggered.connect(self.reconnect_db)
        db_menu.addAction(act_refresh)

        view_menu = menubar.addMenu("View")
        act_mode_code = QAction("Code Graph Mode", self)
        act_mode_code.triggered.connect(lambda: self.set_mode("code"))
        view_menu.addAction(act_mode_code)
        act_mode_bcl = QAction("BCL Tree Mode", self)
        act_mode_bcl.triggered.connect(lambda: self.set_mode("bcl"))
        view_menu.addAction(act_mode_bcl)
        act_mode_deps = QAction("Dependency Graph Mode", self)
        act_mode_deps.triggered.connect(lambda: self.set_mode("deps"))
        view_menu.addAction(act_mode_deps)
        view_menu.addSeparator()
        act_dark = QAction("Dark Theme", self)
        act_dark.triggered.connect(lambda: self.switch_theme("dark"))
        view_menu.addAction(act_dark)
        act_light = QAction("Light Theme", self)
        act_light.triggered.connect(lambda: self.switch_theme("light"))
        view_menu.addAction(act_light)
        act_fit = QAction("Fit to View", self)
        act_fit.triggered.connect(lambda: self.canvas.reset_zoom())
        view_menu.addAction(act_fit)

    # ─── Signal handlers (connected by EventRouter from WCL) ────────────────

    def schedule_json_update(self):
        self.json_timer.start(800)

    def on_combo_changed(self, *args):
        self.tree_config["group_by"] = self.group_combo.currentText()
        self.tree_config["orientation"] = self.orient_combo.currentText()
        self.tree_config["max_methods_per_node"] = self.max_spin.value()
        self.json_editor.setPlainText(json.dumps(self.tree_config, indent=2))
        self.rebuild_tree()

    def on_mode_changed(self, *args):
        self.set_mode(self.mode_combo.currentText())

    def on_json_changed(self):
        try:
            new_config = json.loads(self.json_editor.toPlainText())
            self.tree_config = new_config
            self.colors = COLOR_SCHEMES.get(new_config.get("color_scheme", "dark"), COLOR_SCHEMES["dark"])
            self.apply_style()
            self.canvas.set_colors(self.colors)
            self.canvas.set_config(new_config)
            self.rebuild_tree()
            self.statusBar().showMessage("Config applied — canvas rebuilt")
        except json.JSONDecodeError as e:
            self.statusBar().showMessage(f"JSON error: {e}")

    def on_fit_view(self, *args):
        self.canvas.reset_zoom()

    def on_search_changed(self, text):
        count = self.canvas.highlight_search(text)
        if text.strip():
            self.statusBar().showMessage(f"Search: {count} node(s) matched")
        else:
            self.statusBar().showMessage("Search cleared")

    def on_search_clear(self, *args):
        self.search_box.setText("")

    # ─── Config save / DB reconnect / theme ─────────────────────────────────

    def save_config(self):
        try:
            self.tree_config = json.loads(self.json_editor.toPlainText())
            self.save_config_file()
            self.statusBar().showMessage("Config saved to tree_config.json")
        except Exception as e:
            self.statusBar().showMessage(f"Save error: {e}")

    def reconnect_db(self):
        if self.conn:
            self.conn.close()
        self.connect_db()
        self.rebuild_tree()
        self.statusBar().showMessage("DB reconnected")

    def switch_theme(self, scheme):
        self.tree_config["color_scheme"] = scheme
        self.colors = COLOR_SCHEMES[scheme]
        self.json_editor.setPlainText(json.dumps(self.tree_config, indent=2))
        self.apply_style()
        self.canvas.set_colors(self.colors)
        self.rebuild_tree()

    def show_stats(self):
        if not self.conn:
            return
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files")
        files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM dependencies")
        deps = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT category) FROM methods")
        cats = cur.fetchone()[0]
        QMessageBox.information(self, "DB Stats",
            f"Files: {files}\nMethods: {methods}\nDependencies: {deps}\nCategories: {cats}")

    # ─── Tree building (domain logic — unchanged) ───────────────────────────

    def build_tree_data(self):
        if not self.conn:
            return None
        cfg = self.tree_config
        root_label = cfg.get("root_label", "Code Decision Tree")
        group_by = cfg.get("group_by", "category")
        filter_cat = cfg.get("filter_category", "")
        filter_file = cfg.get("filter_file", "")
        max_methods = cfg.get("max_methods_per_node", 30)
        show_methods = cfg.get("show_methods", True)

        root = TreeNode(root_label, "ROOT", "Root node")
        cur = self.conn.cursor()

        if group_by == "category":
            self.build_by_category(root, cur, filter_cat, filter_file, max_methods, show_methods)
        elif group_by == "file":
            self.build_by_file(root, cur, filter_cat, filter_file, max_methods, show_methods)
        elif group_by == "class":
            self.build_by_class(root, cur, filter_cat, filter_file, max_methods, show_methods)
        else:
            self.build_by_category(root, cur, filter_cat, filter_file, max_methods, show_methods)

        return root

    def build_by_category(self, root, cur, filter_cat, filter_file, max_methods, show_methods):
        query = "SELECT category, COUNT(*) FROM methods"
        conditions = []
        params = []
        if filter_cat:
            conditions.append("category = ?")
            params.append(filter_cat)
        if filter_file:
            conditions.append("file_name = ?")
            params.append(filter_file)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " GROUP BY category ORDER BY COUNT(*) DESC"
        cur.execute(query, params)
        for row in cur.fetchall():
            cat_name = row[0]
            count = row[1]
            cat_node = TreeNode(cat_name, "Category", f"{count} methods")
            root.add_child(cat_node)
            if show_methods:
                sub_q = "SELECT file_name, class_name, method_name, description, id FROM methods WHERE category=? ORDER BY file_name, class_name LIMIT ?"
                cur.execute(sub_q, (cat_name, max_methods))
                current_file = None
                file_node = None
                for m_row in cur.fetchall():
                    fname, cls, mname, desc, mid = m_row
                    if fname != current_file:
                        current_file = fname
                        file_node = TreeNode(fname, "File", DESCRIPTIONS.get(fname, ""))
                        cat_node.add_child(file_node)
                    label = f"{cls}.{mname}" if cls else mname
                    m_node = TreeNode(label, "Method", desc or "", {"type": "method", "id": mid})
                    file_node.add_child(m_node)

    def build_by_file(self, root, cur, filter_cat, filter_file, max_methods, show_methods):
        query = "SELECT file_name, COUNT(*) FROM methods"
        conditions = []
        params = []
        if filter_cat:
            conditions.append("category = ?")
            params.append(filter_cat)
        if filter_file:
            conditions.append("file_name = ?")
            params.append(filter_file)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " GROUP BY file_name ORDER BY file_name"
        cur.execute(query, params)
        for row in cur.fetchall():
            fname = row[0]
            count = row[1]
            desc = DESCRIPTIONS.get(fname, "")
            file_node = TreeNode(fname, "File", f"{count} methods — {desc}")
            root.add_child(file_node)
            if show_methods:
                sub_q = "SELECT class_name, method_name, category, description, id FROM methods WHERE file_name=? ORDER BY class_name, method_name LIMIT ?"
                cur.execute(sub_q, (fname, max_methods))
                current_class = None
                class_node = None
                for m_row in cur.fetchall():
                    cls, mname, cat, desc, mid = m_row
                    if cls != current_class:
                        current_class = cls
                        if cls:
                            class_node = TreeNode(cls, "Class", fname)
                            file_node.add_child(class_node)
                        else:
                            class_node = file_node
                    m_node = TreeNode(mname, "Method", f"{cat} — {desc or ''}", {"type": "method", "id": mid})
                    class_node.add_child(m_node)

    def build_by_class(self, root, cur, filter_cat, filter_file, max_methods, show_methods):
        query = "SELECT class_name, file_name, COUNT(*) FROM methods"
        conditions = []
        params = []
        if filter_cat:
            conditions.append("category = ?")
            params.append(filter_cat)
        if filter_file:
            conditions.append("file_name = ?")
            params.append(filter_file)
        if conditions:
            query += " WHERE " + " AND ".join(conditions) + " AND class_name IS NOT NULL"
        else:
            query += " WHERE class_name IS NOT NULL"
        query += " GROUP BY class_name, file_name ORDER BY class_name"
        cur.execute(query, params)
        for row in cur.fetchall():
            cls, fname, count = row
            class_node = TreeNode(cls or "(no class)", "Class", f"{fname} — {count} methods")
            root.add_child(class_node)
            if show_methods:
                sub_q = "SELECT method_name, category, description, id FROM methods WHERE class_name=? AND file_name=? ORDER BY method_name LIMIT ?"
                cur.execute(sub_q, (cls, fname, max_methods))
                for m_row in cur.fetchall():
                    mname, cat, desc, mid = m_row
                    m_node = TreeNode(mname, "Method", f"{cat} — {desc or ''}", {"type": "method", "id": mid})
                    class_node.add_child(m_node)

    def rebuild_tree(self, *args):
        self.canvas.set_config(self.tree_config)
        self.canvas.set_mode(self.mode)
        if self.mode == "code":
            root = self.build_tree_data()
            self.canvas.build_tree(root)
            if self.conn:
                cur = self.conn.cursor()
                cur.execute("SELECT COUNT(*) FROM files")
                f = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM methods")
                m = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM dependencies")
                d = cur.fetchone()[0]
                self.statusBar().showMessage(
                    f"Code graph — {f} files, {m} methods, {d} deps  |  Ctrl+scroll zoom  |  Click a node")
        elif self.mode == "bcl":
            root = self.build_bcl_tree()
            self.canvas.build_tree(root)
            if self.bcl_path:
                self.statusBar().showMessage(f"BCL tree — {self.bcl_path}  |  Click a node  |  Double-click tuple to edit")
            else:
                self.statusBar().showMessage("BCL mode — no file loaded. Use File→Open BCL File...")
        elif self.mode == "deps":
            root = self.build_dep_graph()
            self.canvas.build_tree(root)
            self.statusBar().showMessage("Dependency graph — click a file node to see its imports")

    # ─── Mode switching ─────────────────────────────────────────────────────

    def set_mode(self, mode):
        if mode not in ("code", "bcl", "deps"):
            return
        self.mode = mode
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentText(mode)
        self.mode_combo.blockSignals(False)
        self.rebuild_tree()

    # ─── Node selection → populate the right-side tabs ──────────────────────

    def on_node_selected(self, node):
        if node is None:
            return
        if self.mode == "bcl":
            self.populate_bcl_tabs(node)
        elif self.mode == "deps":
            self.populate_dep_tabs(node)
        else:
            self.populate_code_tabs(node)

    # ─── Canvas editor signal handlers ──────────────────────────────────────

    def on_node_created(self, node):
        self.statusBar().showMessage("Node added: %s" % node.label, 3000)

    def on_node_deleted(self, node):
        self.statusBar().showMessage("Node deleted: %s" % node.label, 3000)

    def on_node_renamed(self, node, new_label):
        self.statusBar().showMessage("Renamed to: %s" % new_label, 3000)

    def on_edge_created(self, src, dst):
        self.statusBar().showMessage("Edge: %s → %s" % (src.label, dst.label), 3000)

    def on_label_edit_requested(self, node):
        self.canvas_edit_label()

    def on_canvas_context_menu(self, pos):
        scene_pos = self.canvas.mapToScene(pos)
        item = self.canvas.node_at(scene_pos)
        menu = QMenu(self.canvas)
        if item is not None:
            node = self.canvas.rect_to_node.get(id(item))
            if node is None:
                return
            act_edit = menu.addAction("Edit label…")
            act_delete = menu.addAction("Delete node")
            menu.addSeparator()
            act_connect = menu.addAction("Connect to…")
            act_child = menu.addAction("Add child node…")
            action = menu.exec(self.canvas.mapToGlobal(pos))
            if action == act_edit:
                self.canvas_edit_label()
            elif action == act_delete:
                self.canvas.delete_selected()
            elif action == act_connect:
                self.canvas.begin_connect(item)
            elif action == act_child:
                self.canvas_add_child(node)
        else:
            act_add = menu.addAction("Add node here…")
            act_save = menu.addAction("Save layout")
            menu.addSeparator()
            act_fit = menu.addAction("Fit view")
            action = menu.exec(self.canvas.mapToGlobal(pos))
            if action == act_add:
                self.canvas_add_node_at(scene_pos)
            elif action == act_save:
                self.save_layout()
            elif action == act_fit:
                self.canvas.reset_zoom()

    def canvas_edit_label(self):
        node = self.canvas.selected_node()
        if node is None:
            return
        new_label, ok = QInputDialog.getText(self, "Edit label", "New label:", text=node.label)
        if ok and new_label.strip():
            self.canvas.rename_selected(new_label.strip())

    def canvas_add_node_at(self, scene_pos):
        label, ok = QInputDialog.getText(self, "Add node", "Node label:")
        if not ok or not label.strip():
            return
        node_type, ok2 = QInputDialog.getItem(self, "Node type", "Type:", ["check", "container", "leaf", "branch"], 0, False)
        if not ok2:
            return
        self.canvas.add_node_at(scene_pos, label.strip(), node_type)

    def canvas_add_child(self, parent_node):
        label, ok = QInputDialog.getText(self, "Add child", "Child label:")
        if not ok or not label.strip():
            return
        scene_pos = QPointF(parent_node.x + parent_node.width / 2, parent_node.y + parent_node.height + 80)
        self.canvas.add_node_at(scene_pos, label.strip(), "check")

    def save_layout(self):
        if self.canvas.root_node is None:
            return
        positions = {}
        def walk(n):
            positions[n.label] = {"x": int(n.x), "y": int(n.y)}
            for c in n.children:
                walk(c)
        walk(self.canvas.root_node)
        self.tree_config["saved_layout"] = positions
        self.json_editor.setPlainText(json.dumps(self.tree_config, indent=2))
        self.statusBar().showMessage("Layout saved (%d nodes) — use Save Config to write to disk" % len(positions), 4000)

    # ─── Code tab population ────────────────────────────────────────────────

    def populate_code_tabs(self, node):
        nt = node.node_type
        data = node.data or {}
        if not self.conn:
            self.code_preview.setPlainText("(no DB connection)")
            self.bcl_preview.setPlainText("")
            self.dep_preview.setPlainText("")
            return
        cur = self.conn.cursor()
        if nt == "Method" and data.get("id") is not None:
            cur.execute("SELECT code, bcl, bcl_ir, file_name, class_name, method_name, description FROM methods WHERE id=?", (data["id"],))
            row = cur.fetchone()
            if row:
                code, bcl, bcl_ir, fname, cls, mname, desc = row
                header = f"# {fname} :: {cls}.{mname}\n# category: {node.label}\n# desc: {desc or ''}\n"
                self.code_preview.setPlainText(header + "\n" + (code or "(no code stored)"))
                self.bcl_preview.setPlainText(f"--- BCL ---\n{bcl or '(none)'}\n\n--- BCL IR ---\n{bcl_ir or '(none)'}")
                cur.execute("SELECT import_type, module, alias, line, is_local FROM dependencies WHERE file_name=? ORDER BY line", (fname,))
                dep_rows = cur.fetchall()
                lines = [f"# {len(dep_rows)} imports in {fname}"]
                for dr in dep_rows:
                    itype, mod, alias, line, is_local = dr
                    tag = "LOCAL " if is_local else "EXT   "
                    lines.append(f"  L{line:>4} {tag} {itype} {mod}" + (f" as {alias}" if alias else ""))
                self.dep_preview.setPlainText("\n".join(lines))
        elif nt in ("File", "Category", "Class"):
            if nt == "File":
                fname = node.label
                cur.execute("SELECT COUNT(*) FROM methods WHERE file_name=?", (fname,))
                mc = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM dependencies WHERE file_name=?", (fname,))
                dc = cur.fetchone()[0]
                self.code_preview.setPlainText(f"# File: {fname}\n# methods: {mc}\n# imports: {dc}\n# {node.detail}")
                cur.execute("SELECT class_name, method_name, category FROM methods WHERE file_name=? ORDER BY class_name, method_name LIMIT 50", (fname,))
                self.bcl_preview.setPlainText("\n".join(f"{r[0] or '(none)'}.{r[1]}  [{r[2]}]" for r in cur.fetchall()))
                cur.execute("SELECT import_type, module, alias, line, is_local FROM dependencies WHERE file_name=? ORDER BY line", (fname,))
                self.dep_preview.setPlainText("\n".join(f"L{r[3]:>4} {'LOCAL' if r[4] else 'EXT'} {r[0]} {r[1]}" for r in cur.fetchall()))
            elif nt == "Category":
                cat = node.label
                cur.execute("SELECT file_name, class_name, method_name FROM methods WHERE category=? ORDER BY file_name LIMIT 50", (cat,))
                self.code_preview.setPlainText(f"# Category: {cat}\n{node.detail}\n\n" + "\n".join(f"{r[0]}::{r[1]}.{r[2]}" for r in cur.fetchall()))
                self.bcl_preview.setPlainText(f"# {node.detail}")
                self.dep_preview.setPlainText(f"# Category-level view. Click a File or Method node for imports.")
            else:
                cls = node.label
                cur.execute("SELECT file_name, method_name, category, description FROM methods WHERE class_name=? ORDER BY method_name", (cls,))
                rows = cur.fetchall()
                self.code_preview.setPlainText(f"# Class: {cls}\n{node.detail}\n\n" + "\n".join(f"{r[0]}::{r[1]}  [{r[2]}] — {r[3] or ''}" for r in rows))
                self.bcl_preview.setPlainText(f"# {len(rows)} methods in {cls}")
                self.dep_preview.setPlainText("# Click a File or Method node for imports.")
        else:
            self.code_preview.setPlainText(f"# Root: {node.label}\n# {node.detail}")
            self.bcl_preview.setPlainText("")
            self.dep_preview.setPlainText("")

    def populate_dep_tabs(self, node):
        nt = node.node_type
        self.bcl_preview.setPlainText("")
        self.dep_preview.setPlainText("")
        if nt in ("DepFile", "DepFileLocal"):
            fname = node.label
            self.code_preview.setPlainText(f"# File: {fname}\n# {node.detail}")
            if self.conn:
                cur = self.conn.cursor()
                cur.execute("SELECT import_type, module, alias, line, is_local FROM dependencies WHERE file_name=? ORDER BY line", (fname,))
                rows = cur.fetchall()
                lines = [f"# {len(rows)} imports in {fname}"]
                for r in rows:
                    tag = "LOCAL " if r[4] else "EXT   "
                    lines.append(f"  L{r[3]:>4} {tag} {r[0]} {r[1]}" + (f" as {r[2]}" if r[2] else ""))
                self.dep_preview.setPlainText("\n".join(lines))
        else:
            self.code_preview.setPlainText(f"# {node.label}\n# {node.detail}")

    def populate_bcl_tabs(self, node):
        bcl_node = node.bcl_node
        if bcl_node is None:
            self.code_preview.setPlainText(f"# {node.label} (no BCL node attached)")
            self.bcl_preview.setPlainText("")
            self.dep_preview.setPlainText("")
            self.bcl_editor.setPlainText("")
            return
        path_result = bcl_node.Run("path", {})
        path_str = path_result[1] if path_result[0] == 1 else ""
        to_bcl = bcl_node.Run("to_bcl", {})
        bcl_text = to_bcl[1] if to_bcl[0] == 1 else ""
        self.code_preview.setPlainText(f"# Path: {path_str}\n# Type: {node.node_type}\n# Detail: {node.detail}\n\n{bcl_text}")
        tup_lines = [f"# {len(bcl_node.state['tuples'])} tuple(s) in [@{bcl_node.state['name']}]"]
        for i, t in enumerate(bcl_node.state["tuples"]):
            weight = t[-1] if t and isinstance(t[-1], (int, float)) else None
            values = t[:-1] if weight is not None else t
            tup_lines.append(f"  tuple[{i}] weight={weight} values={values}")
        self.bcl_preview.setPlainText("\n".join(tup_lines))
        child_lines = [f"# {len(bcl_node.state['children'])} child container(s)"]
        for ch in bcl_node.state["children"]:
            child_lines.append(f"  [@{ch.state['name']}]")
        self.dep_preview.setPlainText("\n".join(child_lines))
        edit_lines = [f"# Edit tuples for [@{bcl_node.state['name']}] (path: {path_str})",
                      "# Format: each line = one tuple, values separated by ; , weight last (int 0-100)",
                      "# Save via File -> Save BCL File. Empty lines are kept as empty tuples.",
                      ""]
        for t in bcl_node.state["tuples"]:
            parts = []
            for v in t:
                if isinstance(v, (int, float)):
                    parts.append(str(v))
                else:
                    parts.append(str(v))
            edit_lines.append(";".join(parts))
        self.bcl_editor.setReadOnly(False)
        self.bcl_editor.setPlainText("\n".join(edit_lines))
        self.bcl_editing_node = bcl_node

    # ─── BCL mode: load / build / save ──────────────────────────────────────

    def open_bcl_file(self):
        if self.bcl_parser is None or self.bcl_lexer is None:
            QMessageBox.warning(self, "BCL unavailable",
                f"BCL engine could not be imported:\n{getattr(self, 'bcl_import_error', 'unknown')}\n"
                "Check core/Dom_Bcl/ exists and bcl_lexer.py / bcl_parser.py are present.")
            return
        start_dir = str(Path(__file__).resolve().parent.parent / "Sql_Schema_Config")
        path, _ = QFileDialog.getOpenFileName(self, "Open BCL file", start_dir, "BCL files (*.bcl);;All files (*)")
        if not path:
            return
        try:
            text = Path(path).read_text()
        except Exception as e:
            QMessageBox.critical(self, "Open error", f"Cannot read {path}:\n{e}")
            return
        lex_result = self.bcl_lexer.Run("tokenize", {"text": text})
        if lex_result[0] == 0:
            QMessageBox.critical(self, "Lex error", f"Lexer failed:\n{lex_result[2]}")
            return
        parse_result = self.bcl_parser.Run("parse", {"tokens": lex_result[1]["tokens"]})
        if parse_result[0] == 0:
            QMessageBox.critical(self, "Parse error", f"Parser failed:\n{parse_result[2]}")
            return
        self.bcl_root = parse_result[1]["root"]
        self.bcl_path = path
        self.set_mode("bcl")
        self.statusBar().showMessage(f"Loaded BCL: {path}")

    def build_bcl_tree(self):
        if self.bcl_root is None:
            return TreeNode("(no BCL file loaded)", "ROOT", "Use File -> Open BCL File...")
        root_tn = TreeNode("BCL Root", "ROOT", "Parsed BCL container tree")
        for child in self.bcl_root.state["children"]:
            self.bcl_to_treenode(child, root_tn)
        return root_tn

    def bcl_to_treenode(self, bcl_node, parent_tn):
        name = bcl_node.state["name"]
        if name in ("Pass", "Fail", "Unsure", "Wait"):
            nt = name
        elif parent_tn.node_type in ("Pass", "Fail", "Unsure", "Wait"):
            nt = "Check"
        elif parent_tn.node_type == "ROOT":
            nt = "Rule"
        else:
            nt = "Check"
        weight = None
        detail = ""
        if bcl_node.state["tuples"]:
            first = bcl_node.state["tuples"][0]
            if first and isinstance(first[-1], (int, float)):
                weight = first[-1]
                detail = "; ".join(str(v) for v in first[:-1])
            elif first:
                detail = "; ".join(str(v) for v in first)
        label = f"@{name}" if nt in ("Pass", "Fail", "Unsure", "Wait") else name
        data = {"weight": weight, "fix_sql": detail, "type": "bcl"}
        tn = TreeNode(label, nt, detail, data)
        tn.bcl_node = bcl_node
        parent_tn.add_child(tn)
        for child in bcl_node.state["children"]:
            self.bcl_to_treenode(child, tn)

    def save_bcl_file(self):
        if self.bcl_root is None or self.bcl_path is None:
            QMessageBox.information(self, "Save BCL", "No BCL file is loaded.")
            return
        editing = getattr(self, "bcl_editing_node", None)
        if editing is not None and not self.bcl_editor.isReadOnly():
            self.apply_bcl_tuple_edit(editing)
        lines = []
        for child in self.bcl_root.state["children"]:
            r = child.Run("to_bcl", {})
            if r[0] == 1:
                lines.append(r[1])
        text = "\n\n".join(lines) + "\n"
        try:
            Path(self.bcl_path).write_text(text)
            self.statusBar().showMessage(f"Saved BCL: {self.bcl_path}")
            QMessageBox.information(self, "Saved", f"Wrote {self.bcl_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save error", f"Cannot write {self.bcl_path}:\n{e}")

    def apply_bcl_tuple_edit(self, bcl_node):
        raw = self.bcl_editor.toPlainText()
        lines = raw.split("\n")
        new_tuples = []
        for line in lines:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split(";")
            parsed = []
            for p in parts:
                p = p.strip()
                if not p:
                    parsed.append("")
                    continue
                try:
                    if "." not in p:
                        parsed.append(int(p))
                    else:
                        parsed.append(float(p))
                except ValueError:
                    parsed.append(p)
            new_tuples.append(parsed)
        bcl_node.state["tuples"] = new_tuples

    # ─── Dependency graph mode ──────────────────────────────────────────────

    def build_dep_graph(self):
        root = TreeNode("Dependency Graph", "ROOT", "Cross-file imports")
        if not self.conn:
            return root
        cur = self.conn.cursor()
        cur.execute("SELECT file_name, COUNT(*) FROM dependencies GROUP BY file_name ORDER BY COUNT(*) DESC")
        for row in cur.fetchall():
            fname, count = row
            nt = "DepFileLocal" if fname in LOCAL_MODULES else "DepFile"
            file_tn = TreeNode(fname, nt, f"{count} imports", {"type": "file", "name": fname})
            root.add_child(file_tn)
            cur.execute("SELECT import_type, module, alias, line, is_local FROM dependencies WHERE file_name=? ORDER BY line LIMIT ?", (fname, 30))
            for d in cur.fetchall():
                itype, mod, alias, line, is_local = d
                label = f"{mod}" + (f" as {alias}" if alias else "")
                detail = f"L{line} {itype} {'local' if is_local else 'ext'}"
                mod_tn = TreeNode(label, "Method", detail, {"type": "dep", "module": mod, "line": line})
                file_tn.add_child(mod_tn)
        return root

    # ─── Export ─────────────────────────────────────────────────────────────

    def export_png(self):
        if not self.canvas.scene.items():
            QMessageBox.information(self, "Export PNG", "Canvas is empty.")
            return
        default = str(Path(__file__).parent / "decision_tree_export.png")
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", default, "PNG images (*.png)")
        if not path:
            return
        ok = self.canvas.export_png(path)
        if ok:
            self.statusBar().showMessage(f"Exported PNG: {path}")
            QMessageBox.information(self, "Exported", f"Wrote {path}")
        else:
            QMessageBox.critical(self, "Export failed", f"Could not write {path}")

    # ─── Close ──────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self.conn:
            self.conn.close()
        try:
            self.tree_config = json.loads(self.json_editor.toPlainText())
        except Exception:
            pass
        self.save_config_file()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = DecisionTreeGui()
    gui.show()
    sys.exit(app.exec())
