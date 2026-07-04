#!/usr/bin/env python3
"""
ChatTreeViewer — Visualize a conversation as a logic decision tree (DAG).

Parses Cascade .md chat exports and renders the logical structure as a
collapsible tree in PyQt6. Each User Input starts a new branch; Planner
Responses and command executions form the chain within each branch.

Usage:
    python3 ChatTreeViewer.py [path/to/chat.md]
"""

import sys
import re
import os
from dataclasses import dataclass, field
from typing import List, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QVBoxLayout, QWidget, QSplitter, QTextEdit,
    QMenuBar, QMenu, QStatusBar, QToolBar, QStyle,
    QLabel, QComboBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import (
    QAction, QIcon, QColor, QFont, QPalette, QTextCursor,
    QTextCharFormat, QSyntaxHighlighter, QTextDocument
)
from PyQt6.QtWidgets import QStyleFactory


# ─── Data Model ────────────────────────────────────────────────────────────

@dataclass
class ChatSegment:
    """One parsed unit of the conversation."""
    kind: str           # "user", "planner", "command", "status", "question", "file_view", "dir_list", "note"
    text: str           # main content
    raw: str = ""       # raw text for detail view
    line_num: int = 0   # line number in source file
    children: List["ChatSegment"] = field(default_factory=list)


@dataclass
class ChatBranch:
    """A top-level branch starting from a User Input."""
    root: ChatSegment
    segments: List[ChatSegment] = field(default_factory=list)


# ─── Parser ────────────────────────────────────────────────────────────────

def parse_chat(filepath: str) -> List[ChatBranch]:
    """Parse a Cascade .md chat export into branches."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    branches: List[ChatBranch] = []
    current_branch: Optional[ChatBranch] = None
    current_planner: Optional[ChatSegment] = None
    i = 0

    # Skip header lines (title + note)
    while i < len(lines) and not lines[i].strip().startswith("###"):
        i += 1

    while i < len(lines):
        line = lines[i].strip()

        # ── User Input ──
        if line == "### User Input":
            i += 1
            # Collect user text until next ### or end
            text_parts = []
            while i < len(lines) and not lines[i].strip().startswith("###"):
                text_parts.append(lines[i].rstrip())
                i += 1
            user_text = "\n".join(text_parts).strip()
            seg = ChatSegment(
                kind="user",
                text=user_text[:200] + ("..." if len(user_text) > 200 else ""),
                raw=user_text,
                line_num=i - len(text_parts),
            )
            branch = ChatBranch(root=seg)
            branches.append(branch)
            current_branch = branch
            current_planner = None
            continue

        # ── Planner Response ──
        if line == "### Planner Response":
            i += 1
            text_parts = []
            while i < len(lines) and not lines[i].strip().startswith("###"):
                text_parts.append(lines[i].rstrip())
                i += 1
            planner_text = "\n".join(text_parts).strip()
            seg = ChatSegment(
                kind="planner",
                text=planner_text[:200] + ("..." if len(planner_text) > 200 else ""),
                raw=planner_text,
                line_num=i - len(text_parts),
            )
            if current_branch:
                current_branch.segments.append(seg)
                current_planner = seg
            continue

        # ── Inline actions (inside planner blocks, but we already consumed them) ──
        # These appear within planner responses but we capture them from the raw text
        i += 1

    # Now re-parse to capture command/action sub-segments within planner blocks
    # We need a second pass to extract commands from the raw planner text
    for branch in branches:
        for seg in branch.segments:
            if seg.kind == "planner":
                sub_segments = extract_sub_segments(seg.raw, seg.line_num)
                seg.children = sub_segments

    return branches


def extract_sub_segments(planner_raw: str, base_line: int) -> List[ChatSegment]:
    """Extract command executions, questions, file views from planner text."""
    subs: List[ChatSegment] = []
    lines = planner_raw.split("\n")

    for idx, line in enumerate(lines):
        stripped = line.strip()

        # *User accepted the command `...`*
        m = re.match(r"\*User accepted the command `(.+?)`\*", stripped)
        if m:
            subs.append(ChatSegment(
                kind="command",
                text=m.group(1)[:150],
                raw=m.group(1),
                line_num=base_line + idx,
            ))
            continue

        # *Checked command status*
        if stripped == "*Checked command status*":
            subs.append(ChatSegment(
                kind="status",
                text="Checked command status",
                raw=stripped,
                line_num=base_line + idx,
            ))
            continue

        # *Asked user a question*
        if stripped == "*Asked user a question*":
            subs.append(ChatSegment(
                kind="question",
                text="Asked user a question",
                raw=stripped,
                line_num=base_line + idx,
            ))
            continue

        # *Viewed [file](...)*
        m = re.match(r"\*Viewed \[(.+?)\]\(.*?\)\*", stripped)
        if m:
            subs.append(ChatSegment(
                kind="file_view",
                text=f"Viewed: {m.group(1)}",
                raw=stripped,
                line_num=base_line + idx,
            ))
            continue

        # *Listed directory [name](...)*
        m = re.match(r"\*Listed directory \[(.+?)\]\(.*?\)\*", stripped)
        if m:
            subs.append(ChatSegment(
                kind="dir_list",
                text=f"Listed: {m.group(1)}",
                raw=stripped,
                line_num=base_line + idx,
            ))
            continue

        # *Edited [file](...)*
        m = re.match(r"\*Edited \[(.+?)\]\(.*?\)\*", stripped)
        if m:
            subs.append(ChatSegment(
                kind="edit",
                text=f"Edited: {m.group(1)}",
                raw=stripped,
                line_num=base_line + idx,
            ))
            continue

    return subs


# ─── Tree Builder ──────────────────────────────────────────────────────────

# Icons and colors for each segment kind
KIND_META = {
    "user":      ("USER",      QColor("#4A90D9"), "❓"),
    "planner":   ("PLANNER",   QColor("#50C878"), "💡"),
    "command":   ("COMMAND",   QColor("#FFB347"), "⚙"),
    "status":    ("STATUS",    QColor("#B0B0B0"), "✓"),
    "question":  ("QUESTION",  QColor("#FFD700"), "?"),
    "file_view": ("FILE",      QColor("#9B59B6"), "📄"),
    "dir_list":  ("DIR",       QColor("#9B59B6"), "📁"),
    "edit":      ("EDIT",      QColor("#E74C3C"), "✏"),
    "note":      ("NOTE",      QColor("#B0B0B0"), "ℹ"),
}


def build_tree_item(seg: ChatSegment) -> QTreeWidgetItem:
    """Build a QTreeWidgetItem from a ChatSegment."""
    label, color, icon = KIND_META.get(seg.kind, ("?", QColor("#000"), "?"))

    # Truncate for display
    display_text = seg.text.replace("\n", " ").strip()
    if len(display_text) > 120:
        display_text = display_text[:120] + "..."

    item = QTreeWidgetItem()
    item.setText(0, f"{icon} [{label}] {display_text}")
    item.setData(0, Qt.ItemDataRole.UserRole, seg)

    # Color the item
    font = item.font(0)
    if seg.kind == "user":
        font.setBold(True)
    elif seg.kind == "planner":
        font.setItalic(True)
    item.setFont(0, font)
    item.setForeground(0, color)

    # Recurse into children
    for child in seg.children:
        child_item = build_tree_item(child)
        item.addChild(child_item)

    return item


# ─── Main Window ───────────────────────────────────────────────────────────

class ChatTreeViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat Tree Viewer — Conversation DAG")
        self.resize(1200, 800)
        self.chat_path: Optional[str] = None
        self.branches: List[ChatBranch] = []

        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        # ── Central widget: splitter (tree | detail) ──
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Conversation Tree")
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(True)
        self.tree.itemClicked.connect(self.on_item_clicked)
        splitter.addWidget(self.tree)

        # Detail panel
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Click a node to see full text...")
        splitter.addWidget(self.detail)

        splitter.setSizes([700, 500])

        # ── Menu bar ──
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        open_action = QAction("Open Chat...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        export_action = QAction("Export Tree Text...", self)
        export_action.triggered.connect(self.export_tree)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = menubar.addMenu("View")
        expand_all = QAction("Expand All", self)
        expand_action = QAction("Expand All", self)
        expand_action.setShortcut("Ctrl+E")
        expand_action.triggered.connect(self.tree.expandAll)
        view_menu.addAction(expand_action)

        collapse_action = QAction("Collapse All", self)
        collapse_action.setShortcut("Ctrl+Shift+E")
        collapse_action.triggered.connect(self.tree.collapseAll)
        view_menu.addAction(collapse_action)

        # ── Toolbar ──
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        open_btn = QAction("Open", self)
        open_btn.triggered.connect(self.open_file)
        toolbar.addAction(open_btn)

        toolbar.addSeparator()

        expand_btn = QAction("Expand All", self)
        expand_btn.triggered.connect(self.tree.expandAll)
        toolbar.addAction(expand_btn)

        collapse_btn = QAction("Collapse All", self)
        collapse_btn.triggered.connect(self.tree.collapseAll)
        toolbar.addAction(collapse_btn)

        # ── Status bar ──
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready — open a .md chat file (Ctrl+O)")

    def _apply_theme(self):
        """Dark theme."""
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#d4d4d4"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#252526"))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#2d2d2d"))
        pal.setColor(QPalette.ColorRole.Text, QColor("#d4d4d4"))
        pal.setColor(QPalette.ColorRole.Button, QColor("#3c3c3c"))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor("#d4d4d4"))
        pal.setColor(QPalette.ColorRole.Highlight, QColor("#264f78"))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(pal)

        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #252526;
                color: #d4d4d4;
                border: none;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 4px 2px;
            }
            QTreeWidget::item:selected {
                background-color: #264f78;
                color: #ffffff;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none;
                image: none;
            }
        """)

        self.detail.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                font-family: 'Menlo', 'Monaco', monospace;
                font-size: 12px;
            }
        """)

    # ── Actions ──

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Chat File",
            os.path.expanduser("~/Downloads"),
            "Markdown (*.md);;All Files (*)"
        )
        if path:
            self.load_chat(path)

    def load_chat(self, path: str):
        self.chat_path = path
        self.tree.clear()
        self.branches = parse_chat(path)
        fname = os.path.basename(path)

        root_item = QTreeWidgetItem()
        root_item.setText(0, f"💬 {fname}  ({len(self.branches)} branches)")
        root_font = root_item.font(0)
        root_font.setBold(True)
        root_font.setPointSize(13)
        root_item.setFont(0, root_font)
        root_item.setForeground(0, QColor("#FFD700"))
        self.tree.addTopLevelItem(root_item)

        for idx, branch in enumerate(self.branches):
            branch_item = build_tree_item(branch.root)
            # Add planner segments as children
            for seg in branch.segments:
                seg_item = build_tree_item(seg)
                branch_item.addChild(seg_item)
            root_item.addChild(branch_item)

        root_item.setExpanded(True)
        for i in range(root_item.childCount()):
            root_item.child(i).setExpanded(True)

        self.status.showMessage(
            f"Loaded: {fname} — {len(self.branches)} branches, "
            f"{sum(len(b.segments) for b in self.branches)} planner responses"
        )

    def on_item_clicked(self, item: QTreeWidgetItem):
        seg = item.data(0, Qt.ItemDataRole.UserRole)
        if seg:
            kind_label = KIND_META.get(seg.kind, ("?",)) [0]
            header = f"═══ [{kind_label}] Line {seg.line_num} ═══\n\n"
            self.detail.setPlainText(header + seg.raw)
        else:
            self.detail.setPlainText("")

    def export_tree(self):
        if not self.branches:
            self.status.showMessage("Nothing to export — load a chat first")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Tree", "chat_tree.txt", "Text (*.txt)"
        )
        if not path:
            return

        lines = []
        def walk(item, depth):
            prefix = "  " * depth
            lines.append(f"{prefix}{item.text(0)}")
            for i in range(item.childCount()):
                walk(item.child(i), depth + 1)

        root = self.tree.topLevelItem(0)
        if root:
            walk(root, 0)

        with open(path, "w") as f:
            f.write("\n".join(lines))
        self.status.showMessage(f"Exported to {path}")


# ─── Entry Point ───────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))

    viewer = ChatTreeViewer()

    # If a file path was passed as argument, load it
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        viewer.load_chat(sys.argv[1])

    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
