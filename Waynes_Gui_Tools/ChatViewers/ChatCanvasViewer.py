#!/usr/bin/env python3
"""
ChatCanvasViewer — Conversation DAG on a visual canvas.

Messages flow downward as a tree from the first message.
When the topic branches, a new visual branch opens to the side.
Pan/zoom canvas, click nodes for full text.

Usage:
    python3 ChatCanvasViewer.py [path/to/chat.md]
"""

import sys
import re
import os
from dataclasses import dataclass, field
from typing import List, Optional, Set

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem,
    QGraphicsItem, QFileDialog, QSplitter, QTextEdit,
    QStatusBar, QToolBar
)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import (
    QAction, QColor, QPen, QBrush, QFont, QPainter, QPainterPath,
    QPalette, QFontMetrics
)
from PyQt6.QtWidgets import QStyleFactory


# ─── Data ──────────────────────────────────────────────────────────────────

@dataclass
class Msg:
    idx: int
    kind: str
    text: str
    raw: str
    line_num: int = 0
    children: List["Msg"] = field(default_factory=list)
    parent: Optional["Msg"] = None
    x: float = 0.0
    y: float = 0.0
    is_branch: bool = False
    branch_id: int = 0


def truncate(text: str, n: int) -> str:
    text = text.replace("\n", " ").strip()
    return text[:n] + "..." if len(text) > n else text


# ─── Parser ────────────────────────────────────────────────────────────────

def parse_chat(path: str) -> List[Msg]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    nodes: List[Msg] = []
    i, idx = 0, 0
    while i < len(lines) and not lines[i].strip().startswith("###"):
        i += 1
    while i < len(lines):
        line = lines[i].strip()
        if line == "### User Input":
            i += 1
            parts = []
            while i < len(lines) and not lines[i].strip().startswith("###"):
                parts.append(lines[i].rstrip()); i += 1
            txt = "\n".join(parts).strip()
            nodes.append(Msg(idx, "user", truncate(txt, 120), txt, i - len(parts)))
            idx += 1
            continue
        if line == "### Planner Response":
            i += 1
            parts = []
            while i < len(lines) and not lines[i].strip().startswith("###"):
                parts.append(lines[i].rstrip()); i += 1
            txt = "\n".join(parts).strip()
            nodes.append(Msg(idx, "planner", truncate(txt, 120), txt, i - len(parts)))
            idx += 1
            for sub in _extract_actions(txt, i - len(parts)):
                sub.idx = idx; idx += 1; nodes.append(sub)
            continue
        i += 1
    return nodes


def _extract_actions(text: str, base: int) -> List[Msg]:
    subs: List[Msg] = []
    for li, line in enumerate(text.split("\n")):
        s = line.strip()
        m = re.match(r"\*User accepted the command `(.+?)`\*", s)
        if m:
            subs.append(Msg(0, "command", truncate(m.group(1), 80), m.group(1), base + li))
        elif s == "*Checked command status*":
            subs.append(Msg(0, "status", "Checked", s, base + li))
        elif s == "*Asked user a question*":
            subs.append(Msg(0, "question", "Asked user", s, base + li))
        else:
            for pat, kind, prefix in [
                (r"\*Viewed \[(.+?)\]\(.*?\)\*", "file", "View: "),
                (r"\*Listed directory \[(.+?)\]\(.*?\)\*", "dir", "Dir: "),
                (r"\*Edited \[(.+?)\]\(.*?\)\*", "edit", "Edit: "),
            ]:
                m2 = re.match(pat, s)
                if m2:
                    subs.append(Msg(0, kind, prefix + truncate(m2.group(1), 60), s, base + li))
                    break
    return subs


# ─── Branch Detection ──────────────────────────────────────────────────────

STOP: Set[str] = {
    "the","a","an","is","are","was","were","be","been","being","have","has",
    "had","do","does","did","will","would","could","should","may","might",
    "must","can","to","of","in","for","on","at","by","with","from","as",
    "into","about","like","through","over","after","before","between","under",
    "above","this","that","these","those","i","you","he","she","it","we",
    "they","me","him","her","us","them","my","your","his","its","our","their",
    "and","or","but","not","no","yes","so","if","then","else","when","where",
    "why","how","all","each","every","both","few","more","most","other","some",
    "such","only","own","same","than","too","very","just","now","also","there",
    "here","what","which","who","ok","yeah","uh","um","hmm","well","right",
    "fix","issue","problem","try","let","get","got","see","cant","dont",
    "wont","isnt","wasnt","arent","dont","know","want","need","make",
}


def keywords(text: str) -> Set[str]:
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower())
    return {w for w in words if w not in STOP and len(w) >= 3}


def is_continuation(prev: str, new: str) -> bool:
    pk, nk = keywords(prev), keywords(new)
    if not pk or not nk:
        return False
    return len(pk & nk) > 0


# ─── Tree Builder ──────────────────────────────────────────────────────────

def build_tree(nodes: List[Msg]) -> Optional[Msg]:
    if not nodes:
        return None
    # Group: each user msg + following planner/actions
    groups: List[List[Msg]] = []
    cur: List[Msg] = []
    for n in nodes:
        if n.kind == "user" and cur:
            groups.append(cur); cur = [n]
        else:
            cur.append(n)
    if cur:
        groups.append(cur)

    root = groups[0][0]
    prev_node = root
    for n in groups[0][1:]:
        n.parent = prev_node; prev_node.children.append(n); prev_node = n

    branch_counter = 0
    last_user = root

    for gi in range(1, len(groups)):
        user = groups[gi][0]
        prev_group = groups[gi - 1]
        prev_last = prev_group[-1]
        prev_ctx = " ".join(n.raw[:200] for n in prev_group[-3:])

        if is_continuation(prev_ctx, user.raw):
            user.parent = prev_last
            prev_last.children.append(user)
        else:
            branch_counter += 1
            user.parent = last_user
            user.is_branch = True
            user.branch_id = branch_counter
            last_user.children.append(user)

        last_user = user
        prev_node = user
        for n in groups[gi][1:]:
            n.parent = prev_node; prev_node.children.append(n); prev_node = n

    return root


# ─── Layout ────────────────────────────────────────────────────────────────

NODE_W = 300.0
NODE_H = 100.0
TITLE_H = 22.0
V_GAP = 30.0
H_GAP = 50.0


def compute_width(node: Msg) -> float:
    """Recursively compute how much horizontal space a subtree needs."""
    if not node.children:
        return NODE_W
    total = 0.0
    for child in node.children:
        total += compute_width(child)
    total += H_GAP * (len(node.children) - 1)
    return max(NODE_W, total)


def layout_tree(root: Msg):
    """Proper tree layout: compute subtree widths, then position nodes."""
    def walk(node: Msg, x: float, y: float):
        node.x = x + compute_width(node) / 2
        node.y = y

        if not node.children:
            return

        total_child_w = sum(compute_width(c) for c in node.children) + H_GAP * (len(node.children) - 1)
        cx = node.x - total_child_w / 2
        for child in node.children:
            cw = compute_width(child)
            walk(child, cx, y + NODE_H + V_GAP)
            cx += cw + H_GAP

    walk(root, 0, 0)


# ─── Colors ────────────────────────────────────────────────────────────────

KIND_BG = {
    "user":     QColor("#2563EB"),
    "planner":  QColor("#059669"),
    "command":  QColor("#D97706"),
    "status":   QColor("#6B7280"),
    "question": QColor("#CA8A04"),
    "file":     QColor("#7C3AED"),
    "dir":      QColor("#7C3AED"),
    "edit":     QColor("#DC2626"),
}
KIND_BORDER = {
    "user":     QColor("#1E40AF"),
    "planner":  QColor("#047857"),
    "command":  QColor("#B45309"),
    "status":   QColor("#4B5563"),
    "question": QColor("#A16207"),
    "file":     QColor("#5B21B6"),
    "dir":      QColor("#5B21B6"),
    "edit":     QColor("#B91C1C"),
}
KIND_TAG = {
    "user": "USER", "planner": "AI", "command": "CMD",
    "status": "OK", "question": "?", "file": "FILE",
    "dir": "DIR", "edit": "EDIT",
}


# ─── Canvas Node ───────────────────────────────────────────────────────────

class CanvasNode(QGraphicsRectItem):
    def __init__(self, msg: Msg):
        self.msg = msg
        super().__init__(0, 0, NODE_W, NODE_H)
        bg = KIND_BG.get(msg.kind, QColor("#555"))
        border = KIND_BORDER.get(msg.kind, QColor("#333"))
        self.setBrush(QBrush(QColor("#1e1e2e")))
        self.setPen(QPen(border, 2))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Title bar — colored strip at top
        title_bar = QGraphicsRectItem(0, 0, NODE_W, TITLE_H, self)
        title_bar.setBrush(QBrush(bg))
        title_bar.setPen(QPen(Qt.PenStyle.NoPen))

        title_text = QGraphicsTextItem(title_bar)
        kind_label = KIND_TAG.get(msg.kind, "?")
        if msg.is_branch:
            kind_label = f"NEW BRANCH #{msg.branch_id}"
        title_text.setPlainText(f"  {kind_label}")
        title_text.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        title_text.setDefaultTextColor(QColor("#ffffff"))
        title_text.setPos(0, 3)

        # Body text — the message content below the title
        body = QGraphicsTextItem(self)
        display = msg.text
        font = QFont("Menlo", 9)
        if msg.kind == "user":
            font.setBold(True)
        body.setFont(font)
        body.setDefaultTextColor(QColor("#cdd6f4"))
        fm = QFontMetrics(font)
        max_chars = int((NODE_W - 12) / max(fm.horizontalAdvance("x"), 1))
        if len(display) > max_chars:
            display = display[:max_chars - 3] + "..."
        body.setPlainText(display)
        body.setPos(6, TITLE_H + 4)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if self.isSelected():
                self.setPen(QPen(QColor("#FFD700"), 3))
            else:
                border = KIND_BORDER.get(self.msg.kind, QColor("#333"))
                self.setPen(QPen(border, 2))
        return super().itemChange(change, value)


# ─── Canvas Edge ───────────────────────────────────────────────────────────

class CanvasEdge(QGraphicsPathItem):
    def __init__(self, src: Msg, tgt: Msg):
        super().__init__()
        x1, y1 = src.x, src.y + NODE_H
        x2, y2 = tgt.x, tgt.y

        path = QPainterPath()
        path.moveTo(x1, y1)
        mid_y = (y1 + y2) / 2
        path.cubicTo(x1, mid_y, x2, mid_y, x2, y2)
        self.setPath(path)

        color = QColor("#FFD700") if tgt.is_branch else QColor("#666")
        self.setPen(QPen(color, 2 if tgt.is_branch else 1.5))
        self.setZValue(-1)


# ─── Canvas View (pinch + wheel zoom) ──────────────────────────────────────

class CanvasView(QGraphicsView):
    """QGraphicsView with trackpad pinch-to-zoom and mouse wheel zoom."""

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 10.0

    def wheelEvent(self, event):
        """Handle mouse wheel / trackpad scroll for zoom."""
        mods = event.modifiers()
        angle = event.angleDelta().y()

        # Trackpad pinch gesture comes through as Ctrl+wheel on macOS
        # Regular wheel scrolls, Ctrl+wheel zooms
        if mods & Qt.KeyboardModifier.ControlModifier:
            if angle > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            # Regular scroll — pan
            super().wheelEvent(event)

    def zoom_in(self, factor=1.15):
        if self._zoom * factor <= self._max_zoom:
            self.scale(factor, factor)
            self._zoom *= factor

    def zoom_out(self, factor=1.15):
        if self._zoom / factor >= self._min_zoom:
            self.scale(1.0 / factor, 1.0 / factor)
            self._zoom /= factor

    def reset_zoom(self):
        self.resetTransform()
        self._zoom = 1.0

    def fit_to_rect(self, rect):
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        # Estimate zoom level from the fit
        if rect.width() > 0 and rect.height() > 0:
            vw = self.viewport().width()
            vh = self.viewport().height()
            sx = vw / rect.width()
            sy = vh / rect.height()
            self._zoom = min(sx, sy)


# ─── Main Window ───────────────────────────────────────────────────────────

class ChatCanvasViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat Canvas — Conversation DAG")
        self.resize(1400, 900)
        self.root_node: Optional[Msg] = None

        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # Canvas
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(QColor("#1a1a2e")))
        self.view = CanvasView(self.scene)
        splitter.addWidget(self.view)
        self.scene.selectionChanged.connect(self.on_selection)

        # Detail panel
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Click a node to see full text...")
        splitter.addWidget(self.detail)
        splitter.setSizes([1000, 400])

        # Toolbar
        tb = QToolBar("Toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        open_act = QAction("Open", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_file)
        tb.addAction(open_act)

        tb.addSeparator()

        zoom_in = QAction("Zoom +", self)
        zoom_in.setShortcut("Ctrl++")
        zoom_in.triggered.connect(lambda: self.view.zoom_in())
        tb.addAction(zoom_in)

        zoom_out = QAction("Zoom -", self)
        zoom_out.setShortcut("Ctrl+-")
        zoom_out.triggered.connect(lambda: self.view.zoom_out())
        tb.addAction(zoom_out)

        fit = QAction("Fit", self)
        fit.setShortcut("Ctrl+F")
        fit.triggered.connect(self.fit_view)
        tb.addAction(fit)

        tb.addSeparator()

        reset = QAction("Reset Zoom", self)
        reset.triggered.connect(lambda: self.view.reset_zoom())
        tb.addAction(reset)

        # Menu
        mb = self.menuBar()
        file_menu = mb.addMenu("File")
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        view_menu = mb.addMenu("View")
        view_menu.addAction(zoom_in)
        view_menu.addAction(zoom_out)
        view_menu.addAction(fit)
        view_menu.addAction(reset)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Open a .md chat file (Ctrl+O)")

    def _apply_theme(self):
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#1e1e2e"))
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#cdd6f4"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#11111b"))
        pal.setColor(QPalette.ColorRole.Text, QColor("#cdd6f4"))
        pal.setColor(QPalette.ColorRole.Button, QColor("#313244"))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor("#cdd6f4"))
        pal.setColor(QPalette.ColorRole.Highlight, QColor("#585b70"))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(pal)

        self.view.setStyleSheet("""
            QGraphicsView { border: none; background: #1a1a2e; }
        """)
        self.detail.setStyleSheet("""
            QTextEdit {
                background-color: #11111b; color: #cdd6f4;
                border: 1px solid #313244;
                font-family: 'Menlo', 'Monaco', monospace; font-size: 12px;
            }
        """)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Chat File", os.path.expanduser("~/Downloads"),
            "Markdown (*.md);;All Files (*)"
        )
        if path:
            self.load_chat(path)

    def load_chat(self, path: str):
        self.scene.clear()
        nodes = parse_chat(path)
        if not nodes:
            self.status_bar.showMessage("No messages found in file")
            return

        self.root_node = build_tree(nodes)
        if not self.root_node:
            self.status_bar.showMessage("Failed to build tree")
            return

        layout_tree(self.root_node)

        # Draw edges first (behind nodes)
        def draw_edges(node: Msg):
            for child in node.children:
                edge = CanvasEdge(node, child)
                self.scene.addItem(edge)
                draw_edges(child)

        draw_edges(self.root_node)

        # Draw nodes
        node_count = [0]
        def draw_nodes(node: Msg):
            cn = CanvasNode(node)
            cn.setPos(node.x - NODE_W / 2, node.y)
            cn.setData(0, node)
            self.scene.addItem(cn)
            node_count[0] += 1
            for child in node.children:
                draw_nodes(child)

        draw_nodes(self.root_node)

        # Root label
        root_hdr = QGraphicsTextItem("CONVERSATION TREE")
        root_hdr.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        root_hdr.setDefaultTextColor(QColor("#FFD700"))
        root_hdr.setPos(self.root_node.x - 80, -40)
        self.scene.addItem(root_hdr)

        fname = os.path.basename(path)
        branches = sum(1 for n in nodes if n.is_branch)
        self.status_bar.showMessage(
            f"{fname} — {node_count[0]} nodes, {branches} branches"
        )

        self.fit_view()

    def on_selection(self):
        try:
            items = self.scene.selectedItems()
        except RuntimeError:
            return
        if items:
            item = items[0]
            if isinstance(item, CanvasNode):
                msg = item.msg
                tag = KIND_TAG.get(msg.kind, "?")
                self.detail.setPlainText(
                    f"═══ [{tag}] Line {msg.line_num} ═══\n\n{msg.raw}"
                )

    def fit_view(self):
        if self.scene.items():
            rect = self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
            self.view.fit_to_rect(rect)


# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    viewer = ChatCanvasViewer()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        viewer.load_chat(sys.argv[1])
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
