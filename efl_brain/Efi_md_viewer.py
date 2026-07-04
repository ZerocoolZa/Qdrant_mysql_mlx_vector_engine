#!/usr/bin/env python3
"""PyQt6 Markdown Viewer with Search + Match Navigation."""

import os
import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QTextEdit,
)
from PyQt6.QtGui import (
    QTextCursor,
    QTextCharFormat,
    QColor,
    QFont,
)
from PyQt6.QtCore import QRegularExpression


import Config_efl_brain as Config

DEFAULT_MD = os.path.join(Config.BASE_DIR, "Efi_readme.md")


class MdViewer(QMainWindow):

    def __init__(self, filepath=None):
        super().__init__()

        self.filepath = filepath or DEFAULT_MD
        self.content = ""

        self.search_matches = []
        self.current_match = -1

        self.setWindowTitle("MD Viewer — Search & Highlight")
        self.resize(1000, 700)

        self._build_ui()
        self.load_file()

    def _build_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.returnPressed.connect(self.do_search)
        search_layout.addWidget(self.search_input)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.do_search)
        search_layout.addWidget(self.search_btn)

        self.prev_btn = QPushButton("Prev")
        self.prev_btn.clicked.connect(self.prev_match)
        search_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.next_match)
        search_layout.addWidget(self.next_btn)

        self.result_label = QLabel("")
        search_layout.addWidget(self.result_label)

        layout.addLayout(search_layout)

        self.path_label = QLabel(self.filepath)
        self.path_label.setStyleSheet(
            "color:#888888;font-size:11px;"
        )
        layout.addWidget(self.path_label)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)

        font = QFont()
        font.setFamilies([
            "Menlo",
            "Consolas",
            "Courier New",
            "Monaco"
        ])
        font.setPointSize(12)

        self.text_edit.setFont(font)

        layout.addWidget(self.text_edit)

    def load_file(self):

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.content = f.read()

            self.text_edit.setPlainText(self.content)

        except Exception as e:
            self.text_edit.setPlainText(
                f"Error loading file:\n\n{e}"
            )

    def clear_highlights(self):

        self.text_edit.setPlainText(self.content)

        self.search_matches = []
        self.current_match = -1

    def do_search(self):

        query = self.search_input.text().strip()

        if not query:
            return

        self.clear_highlights()

        doc = self.text_edit.document()

        regex = QRegularExpression(
            query,
            QRegularExpression.PatternOption.CaseInsensitiveOption
        )

        yellow = QTextCharFormat()
        yellow.setBackground(QColor(255, 255, 0))

        cursor = QTextCursor(doc)

        while True:

            cursor = doc.find(regex, cursor)

            if cursor.isNull():
                break

            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            cursor.mergeCharFormat(yellow)

            self.search_matches.append(
                (start, end)
            )

            cursor.setPosition(end)

        count = len(self.search_matches)

        if count == 0:
            self.result_label.setText("No matches")
            return

        self.current_match = 0

        self.highlight_current()

    def highlight_current(self):

        if not self.search_matches:
            return

        self.text_edit.setPlainText(self.content)

        doc = self.text_edit.document()

        yellow = QTextCharFormat()
        yellow.setBackground(QColor(255, 255, 0))

        orange = QTextCharFormat()
        orange.setBackground(QColor(255, 165, 0))

        for index, (start, end) in enumerate(self.search_matches):

            cursor = QTextCursor(doc)

            cursor.setPosition(start)
            cursor.setPosition(
                end,
                QTextCursor.MoveMode.KeepAnchor
            )

            if index == self.current_match:
                cursor.mergeCharFormat(orange)
            else:
                cursor.mergeCharFormat(yellow)

        start, end = self.search_matches[self.current_match]

        cursor = QTextCursor(doc)

        cursor.setPosition(start)
        cursor.setPosition(
            end,
            QTextCursor.MoveMode.KeepAnchor
        )

        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

        self.result_label.setText(
            f"Match {self.current_match + 1} of {len(self.search_matches)}"
        )

    def next_match(self):

        if not self.search_matches:
            return

        self.current_match += 1

        if self.current_match >= len(self.search_matches):
            self.current_match = 0

        self.highlight_current()

    def prev_match(self):

        if not self.search_matches:
            return

        self.current_match -= 1

        if self.current_match < 0:
            self.current_match = len(self.search_matches) - 1

        self.highlight_current()


def main():

    app = QApplication(sys.argv)

    filepath = None

    if len(sys.argv) > 1:
        filepath = sys.argv[1]

    viewer = MdViewer(filepath)
    viewer.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()