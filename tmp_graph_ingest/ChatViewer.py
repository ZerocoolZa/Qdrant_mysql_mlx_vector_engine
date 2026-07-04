#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     ChatViewer.py
# Domain:   chat_viewer
# Purpose:  PyQt6 GUI to view consolidated chat logs with User/AI distinction
# ============================================================================

import sys
import os
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextBrowser, QListWidget, QSplitter, QLabel, QLineEdit,
    QPushButton, QComboBox, QScrollBar
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor, QIcon


# ============================================================================
# CONSTANTS
# ============================================================================
DEFAULT_CHAT_FILE = "/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/Unifying Graph Codebases.md"

USER_BG = "#1a2a1a"
USER_LABEL = "USER SAID"
USER_COLOR = "#7ec7e2"

AI_BG = "#2a1a1a"
AI_LABEL = "AI SAID"
AI_COLOR = "#e27ec7"

WINDOW_TITLE = "Chat Log Viewer — Devin Session"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900


class ChatParser:
    """Parse consolidated chat markdown into structured messages."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.messages = []
        self.Parse()

    def Parse(self):
        if not os.path.exists(self.filepath):
            return
        with open(self.filepath, "r", errors="replace") as f:
            content = f.read()
        lines = content.split("\n")
        current_role = None
        current_lines = []
        msg_index = 0

        for line in lines:
            if line.strip() == "### User Input":
                if current_role and current_lines:
                    self.messages.append({
                        "index": msg_index,
                        "role": current_role,
                        "text": "\n".join(current_lines).strip(),
                    })
                    msg_index += 1
                current_role = "user"
                current_lines = []
            elif line.strip() == "### Planner Response":
                if current_role and current_lines:
                    self.messages.append({
                        "index": msg_index,
                        "role": current_role,
                        "text": "\n".join(current_lines).strip(),
                    })
                    msg_index += 1
                current_role = "ai"
                current_lines = []
            else:
                if current_role:
                    current_lines.append(line)

        if current_role and current_lines:
            self.messages.append({
                "index": msg_index,
                "role": current_role,
                "text": "\n".join(current_lines).strip(),
            })


class ChatViewer(QMainWindow):
    """Main window showing chat log with User/AI distinction."""

    def __init__(self, chat_file=DEFAULT_CHAT_FILE):
        super().__init__()
        self.chat_file = chat_file
        self.parser = ChatParser(chat_file)
        self.filtered_messages = self.parser.messages
        self.InitUi()

    def InitUi(self):
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Top bar ---
        top_bar = QHBoxLayout()
        lbl_file = QLabel("File: " + os.path.basename(self.chat_file))
        lbl_file.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        top_bar.addWidget(lbl_file)

        top_bar.addStretch()

        lbl_count = QLabel("Messages: {}".format(len(self.parser.messages)))
        lbl_count.setFont(QFont("Arial", 10))
        self.lbl_count = lbl_count
        top_bar.addWidget(lbl_count)

        top_bar.addStretch()

        # Filter dropdown
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItem("All")
        self.cmb_filter.addItem("User only")
        self.cmb_filter.addItem("AI only")
        self.cmb_filter.currentIndexChanged.connect(self.ApplyFilter)
        top_bar.addWidget(QLabel("Filter:"))
        top_bar.addWidget(self.cmb_filter)

        # Search
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search...")
        self.txt_search.setFixedWidth(200)
        self.txt_search.textChanged.connect(self.ApplyFilter)
        top_bar.addWidget(self.txt_search)

        layout.addLayout(top_bar)

        # --- Splitter: message list + content ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: message list
        self.lst_messages = QListWidget()
        self.lst_messages.setFont(QFont("Courier", 10))
        self.lst_messages.setMaximumWidth(350)
        self.lst_messages.currentRowChanged.connect(self.OnSelectMessage)
        splitter.addWidget(self.lst_messages)

        # Right: content viewer
        self.txt_content = QTextBrowser()
        self.txt_content.setFont(QFont("Courier", 11))
        self.txt_content.setOpenExternalLinks(True)
        splitter.addWidget(self.txt_content)

        splitter.setSizes([350, 1050])
        layout.addWidget(splitter)

        # --- Bottom bar ---
        bottom_bar = QHBoxLayout()
        lbl_info = QLabel("Total: {} messages | User: {} | AI: {}".format(
            len(self.parser.messages),
            sum(1 for m in self.parser.messages if m["role"] == "user"),
            sum(1 for m in self.parser.messages if m["role"] == "ai"),
        ))
        lbl_info.setFont(QFont("Arial", 9))
        self.lbl_info = lbl_info
        bottom_bar.addWidget(lbl_info)
        bottom_bar.addStretch()

        btn_top = QPushButton("Jump to Top")
        btn_top.clicked.connect(lambda: self.lst_messages.setCurrentRow(0))
        bottom_bar.addWidget(btn_top)

        btn_bottom = QPushButton("Jump to Bottom")
        btn_bottom.clicked.connect(lambda: self.lst_messages.setCurrentRow(len(self.filtered_messages) - 1))
        bottom_bar.addWidget(btn_bottom)

        layout.addLayout(bottom_bar)

        # Populate
        self.PopulateList()

    def PopulateList(self):
        self.lst_messages.clear()
        for msg in self.filtered_messages:
            role = msg["role"]
            prefix = "USER>" if role == "user" else "AI>  "
            text_preview = msg["text"][:80].replace("\n", " ").strip()
            if not text_preview:
                text_preview = "(empty)"
            display = "{} #{}: {}".format(prefix, msg["index"], text_preview)
            self.lst_messages.addItem(display)
        self.lbl_count.setText("Messages: {}".format(len(self.filtered_messages)))

    def ApplyFilter(self):
        filter_mode = self.cmb_filter.currentText()
        search_text = self.txt_search.text().lower().strip()

        self.filtered_messages = []
        for msg in self.parser.messages:
            if filter_mode == "User only" and msg["role"] != "user":
                continue
            if filter_mode == "AI only" and msg["role"] != "ai":
                continue
            if search_text and search_text not in msg["text"].lower():
                continue
            self.filtered_messages.append(msg)

        self.PopulateList()
        if self.filtered_messages:
            self.lst_messages.setCurrentRow(0)

    def OnSelectMessage(self, row):
        if row < 0 or row >= len(self.filtered_messages):
            return
        msg = self.filtered_messages[row]
        role = msg["role"]
        text = msg["text"]

        if role == "user":
            label = USER_LABEL
            color = USER_COLOR
            bg = USER_BG
        else:
            label = AI_LABEL
            color = AI_COLOR
            bg = AI_BG

        # Build HTML
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Preserve line breaks
        escaped = escaped.replace("\n", "<br>")
        # Highlight code blocks
        escaped = re.sub(r'```(.*?)```', lambda m: '<pre style="background:#1e1e2e;color:#cdd6f4;padding:8px;border-radius:4px;">' + m.group(0)[3:-3] + '</pre>', escaped, flags=re.DOTALL)

        html = """
        <div style="background:{bg};border-radius:8px;padding:12px;margin:4px;">
            <div style="color:{color};font-size:14px;font-weight:bold;margin-bottom:8px;
                 border-bottom:1px solid {color};padding-bottom:4px;">
                {label} &mdash; Message #{idx}
            </div>
            <div style="color:#cdd6f4;font-size:12px;line-height:1.5;">
                {content}
            </div>
        </div>
        """.format(
            bg=bg, color=color, label=label, idx=msg["index"], content=escaped
        )

        self.txt_content.setHtml(html)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    from PyQt6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#181825"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e2e"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#313244"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#45475a"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#cdd6f4"))
    app.setPalette(palette)

    chat_file = DEFAULT_CHAT_FILE
    if len(sys.argv) > 1:
        chat_file = sys.argv[1]

    viewer = ChatViewer(chat_file)
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
