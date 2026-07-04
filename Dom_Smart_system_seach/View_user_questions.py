#!/usr/bin/env python3
"""Quick viewer for user_questions table in autocomplete.db."""

import os
import sys
import sqlite3
from collections import Counter

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QLineEdit, QFrame,
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'autocomplete.db')


class QuestionViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('User Questions Viewer')
        self.resize(900, 600)
        self.setStyleSheet(
            "QWidget { background: #0d1117; color: #c9d1d9; }"
            "QLineEdit { background: #161b22; border: 1px solid #30363d;"
            "           border-radius: 6px; padding: 6px; color: #c9d1d9; }"
            "QListWidget { background: #161b22; border: 1px solid #30363d;"
            "              border-radius: 6px; font-size: 13px; }"
            "QLabel { color: #8b949e; padding: 4px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Stats bar
        self.stats_label = QLabel('Loading…')
        layout.addWidget(self.stats_label)

        # Filter bar
        filter_frame = QFrame()
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText('Filter questions… (type to search)')
        self.filter_input.textChanged.connect(self._on_filter)
        filter_layout.addWidget(self.filter_input)
        layout.addWidget(filter_frame)

        # Results
        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        layout.addWidget(self.list_widget, 1)

        # Load
        self._all_rows = []
        self._load()

    def _load(self):
        if not os.path.exists(DB_PATH):
            self.stats_label.setText('No autocomplete.db found. Run Extract_user_questions.py first.')
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT question, style_mode, source FROM user_questions ORDER BY id DESC')
        self._all_rows = cur.fetchall()
        cur.execute('SELECT COUNT(*) FROM user_questions')
        total = cur.fetchone()[0]
        styles = Counter(r[1] for r in self._all_rows)
        sources = Counter(r[2] for r in self._all_rows)
        conn.close()

        style_str = ' | '.join(f'{k}: {v}' for k, v in styles.most_common())
        source_str = ' | '.join(f'{k}: {v}' for k, v in sources.most_common())
        self.stats_label.setText(
            f'{total} questions  |  Styles: {style_str}  |  Sources: {source_str}'
        )
        self._populate(self._all_rows)

    def _on_filter(self, text):
        text = text.strip().lower()
        if not text:
            self._populate(self._all_rows)
            return
        filtered = [r for r in self._all_rows if text in r[0].lower()]
        self._populate(filtered)

    def _populate(self, rows):
        self.list_widget.clear()
        for question, style, source in rows:
            # Color tag by style
            if style == 'frustrated':
                tag = '  [FRUSTRATED]'
                color = '#f85149'
            elif style == 'calm':
                tag = '  [CALM]'
                color = '#3fb950'
            else:
                tag = '  [NEUTRAL]'
                color = '#8b949e'
            display = f'{question[:200]}{tag}  ({source})'
            item = QListWidgetItem(display)
            item.setToolTip(question)
            item.setForeground(Qt.GlobalColor.white if style != 'neutral' else Qt.GlobalColor.lightGray)
            self.list_widget.addItem(item)
        self.stats_label.setText(
            self.stats_label.text().split('  |  Showing')[0] +
            f'  |  Showing {len(rows)}'
        )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('QuestionViewer')
    viewer = QuestionViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
