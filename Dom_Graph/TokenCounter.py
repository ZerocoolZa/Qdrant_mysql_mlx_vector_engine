#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/TokenCounter.py"
# date="2026-08-18" author="Devin" session_id="token-counter"
# context="PyQt6 GUI token counter for files and folders"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3"}
# [@FILEID]{id="TokenCounter.py" domain="tools" authority="TokenCounter"}
# [@SUMMARY]{summary="PyQt6 GUI that counts tokens in files and folders. Supports drag-drop, file picker, folder picker. Uses tiktoken for accurate OpenAI-style token counts. Shows per-file breakdown and totals."}
# [@CLASS]{class="TokenCounter" domain="tools" authority="single"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<PyQt6 GUI token counter for files and folders. Uses tiktoken. VBStyle violations: multiple classes (CountWorker QThread + TokenCounter), hardcoded DEFAULT_EXTS and ENCODING constants, missing @METHOD header, missing Run() dispatch in header. Uses pyqtSignal.>][@todos<Add @METHOD header. Split CountWorker into separate file. Make ENCODING/DEFAULT_EXTS configurable. Add Run() dispatch.>]}
"""
TokenCounter -- PyQt6 GUI for counting tokens in files and folders.

Features:
  - Add files via button or drag-drop
  - Add folders (recursive scan)
  - Counts tokens using tiktoken (cl100k_base / GPT-4 tokenizer)
  - Also shows char count, word count, line count
  - Per-file breakdown in table
  - Totals at bottom
  - Export results to CSV
  - Filter by file extension

Usage:
  python3 TokenCounter.py
"""
import sys
import os
import csv
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QProgressBar, QComboBox, QCheckBox, QHeaderView, QMessageBox,
    QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QDragEnterEvent, QDropEvent

import tiktoken

ENCODING = tiktoken.get_encoding("cl100k_base")
DEFAULT_EXTS = ".py,.js,.ts,.tsx,.jsx,.java,.c,.cpp,.h,.hpp,.rs,.go,.rb,.php,.swift,.kt,.scala,.sh,.bash,.sql,.md,.txt,.json,.yaml,.yml,.xml,.html,.css,.scss,.toml,.cfg,.ini,.csv,.tsv"


class CountWorker(QThread):
    progress = pyqtSignal(int, int)
    file_done = pyqtSignal(str, int, int, int, int)
    finished_signal = pyqtSignal(int, int, int, int, float)

    def __init__(self, files):
        super().__init__()
        self.files = files
        self.cancelled = False

    def run(self):
        total_tokens = 0
        total_chars = 0
        total_words = 0
        total_lines = 0
        n = len(self.files)
        t0 = time.time()
        for i, fpath in enumerate(self.files):
            if self.cancelled:
                break
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                tokens = len(ENCODING.encode(content))
                chars = len(content)
                words = len(content.split())
                lines = content.count("\n") + 1
            except Exception:
                tokens = 0
                chars = 0
                words = 0
                lines = 0
            total_tokens += tokens
            total_chars += chars
            total_words += words
            total_lines += lines
            self.file_done.emit(fpath, tokens, chars, words, lines)
            self.progress.emit(i + 1, n)
        elapsed = time.time() - t0
        self.finished_signal.emit(total_tokens, total_chars, total_words, total_lines, elapsed)

    def cancel(self):
        self.cancelled = True


class TokenCounter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.files = []
        self.worker = None
        self.setWindowTitle("Token Counter")
        self.resize(1000, 700)
        self.setMinimumSize(QSize(700, 500))
        self.setAcceptDrops(True)
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        input_group = QGroupBox("Input")
        input_layout = QGridLayout(input_group)

        btn_add_files = QPushButton("Add Files")
        btn_add_files.clicked.connect(self._add_files)
        input_layout.addWidget(btn_add_files, 0, 0)

        btn_add_folder = QPushButton("Add Folder")
        btn_add_folder.clicked.connect(self._add_folder)
        input_layout.addWidget(btn_add_folder, 0, 1)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear_all)
        input_layout.addWidget(btn_clear, 0, 2)

        input_layout.addWidget(QLabel("Extensions:"), 1, 0)
        self.ext_input = QComboBox()
        self.ext_input.setEditable(True)
        self.ext_input.addItems([DEFAULT_EXTS, ".py", ".py,.md,.txt", ".js,.ts,.tsx", ".java,.c,.cpp", "*"])
        self.ext_input.setCurrentIndex(0)
        self.ext_input.setMinimumWidth(400)
        input_layout.addWidget(self.ext_input, 1, 1, 1, 2)

        self.cb_recursive = QCheckBox("Recursive")
        self.cb_recursive.setChecked(True)
        input_layout.addWidget(self.cb_recursive, 2, 0)

        self.cb_show_content = QCheckBox("Show file content preview")
        input_layout.addWidget(self.cb_show_content, 2, 1)

        layout.addWidget(input_group)

        btn_count = QPushButton("Count Tokens")
        btn_count.setStyleSheet("QPushButton { font-size: 14px; font-weight: bold; padding: 8px; }")
        btn_count.clicked.connect(self._count_tokens)
        layout.addWidget(btn_count)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["File", "Tokens", "Chars", "Words", "Lines", "Preview"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 80)
        self.table.setAlternatingRowColors(True)
        self.table.itemClicked.connect(self._on_row_click)
        layout.addWidget(self.table)

        results_group = QGroupBox("Totals")
        results_layout = QGridLayout(results_group)
        self.lbl_files = QLabel("Files: 0")
        self.lbl_tokens = QLabel("Tokens: 0")
        self.lbl_chars = QLabel("Chars: 0")
        self.lbl_words = QLabel("Words: 0")
        self.lbl_lines = QLabel("Lines: 0")
        self.lbl_time = QLabel("Time: 0.00s")
        self.lbl_cost = QLabel("Est. cost (GPT-4): $0.00")
        results_layout.addWidget(self.lbl_files, 0, 0)
        results_layout.addWidget(self.lbl_tokens, 0, 1)
        results_layout.addWidget(self.lbl_chars, 0, 2)
        results_layout.addWidget(self.lbl_words, 1, 0)
        results_layout.addWidget(self.lbl_lines, 1, 1)
        results_layout.addWidget(self.lbl_time, 1, 2)
        results_layout.addWidget(self.lbl_cost, 2, 0, 1, 3)
        layout.addWidget(results_group)

        bottom_bar = QHBoxLayout()
        btn_export = QPushButton("Export CSV")
        btn_export.clicked.connect(self._export_csv)
        bottom_bar.addWidget(btn_export)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self._cancel_count)
        bottom_bar.addWidget(btn_cancel)
        bottom_bar.addStretch()
        self.lbl_status = QLabel("Ready. Drag files/folders here or use buttons above.")
        bottom_bar.addWidget(self.lbl_status)
        layout.addLayout(bottom_bar)

    def _get_extensions(self):
        ext_text = self.ext_input.currentText().strip()
        if ext_text == "*":
            return None
        exts = [e.strip().lower() for e in ext_text.split(",") if e.strip()]
        if not all(e.startswith(".") for e in exts):
            exts = ["." + e if not e.startswith(".") else e for e in exts]
        return set(exts)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", "")
        if not paths:
            return
        exts = self._get_extensions()
        for p in paths:
            if exts:
                ext = os.path.splitext(p)[1].lower()
                if ext not in exts:
                    continue
            if p not in self.files:
                self.files.append(p)
        self.lbl_status.setText("Added " + str(len(self.files)) + " files")
        self.lbl_files.setText("Files: " + str(len(self.files)))

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return
        exts = self._get_extensions()
        recursive = self.cb_recursive.isChecked()
        count_before = len(self.files)
        if recursive:
            for dirpath, dirnames, filenames in os.walk(folder):
                dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git", "node_modules", ".venv", "venv")]
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    if exts:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in exts:
                            continue
                    if fpath not in self.files:
                        self.files.append(fpath)
        else:
            for fname in os.listdir(folder):
                fpath = os.path.join(folder, fname)
                if not os.path.isfile(fpath):
                    continue
                if exts:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in exts:
                        continue
                if fpath not in self.files:
                    self.files.append(fpath)
        added = len(self.files) - count_before
        self.lbl_status.setText("Added " + str(added) + " files from folder (total: " + str(len(self.files)) + ")")
        self.lbl_files.setText("Files: " + str(len(self.files)))

    def _clear_all(self):
        self.files = []
        self.table.setRowCount(0)
        self.lbl_files.setText("Files: 0")
        self.lbl_tokens.setText("Tokens: 0")
        self.lbl_chars.setText("Chars: 0")
        self.lbl_words.setText("Words: 0")
        self.lbl_lines.setText("Lines: 0")
        self.lbl_time.setText("Time: 0.00s")
        self.lbl_cost.setText("Est. cost (GPT-4): $0.00")
        self.lbl_status.setText("Cleared")

    def _count_tokens(self):
        if not self.files:
            QMessageBox.information(self, "No Files", "Add files or a folder first.")
            return
        self.table.setRowCount(0)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.progress.setMaximum(len(self.files))
        self.lbl_status.setText("Counting tokens in " + str(len(self.files)) + " files...")
        self.worker = CountWorker(self.files)
        self.worker.file_done.connect(self._on_file_done)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_file_done(self, fpath, tokens, chars, words, lines):
        row = self.table.rowCount()
        self.table.insertRow(row)
        fname = os.path.basename(fpath)
        fitem = QTableWidgetItem(fname)
        fitem.setToolTip(fpath)
        fitem.setData(Qt.ItemDataRole.UserRole, fpath)
        self.table.setItem(row, 0, fitem)
        self.table.setItem(row, 1, QTableWidgetItem(str(tokens)))
        self.table.setItem(row, 2, QTableWidgetItem(str(chars)))
        self.table.setItem(row, 3, QTableWidgetItem(str(words)))
        self.table.setItem(row, 4, QTableWidgetItem(str(lines)))
        if tokens > 10000:
            self.table.item(row, 1).setForeground(QColor("#cc0000"))
        elif tokens > 1000:
            self.table.item(row, 1).setForeground(QColor("#cc8800"))
        else:
            self.table.item(row, 1).setForeground(QColor("#006600"))
        preview_item = QTableWidgetItem("")
        self.table.setItem(row, 5, preview_item)

    def _on_progress(self, done, total):
        self.progress.setValue(done)
        self.lbl_status.setText("Processing " + str(done) + "/" + str(total))

    def _on_finished(self, total_tokens, total_chars, total_words, total_lines, elapsed):
        self.progress.setVisible(False)
        self.lbl_files.setText("Files: " + str(len(self.files)))
        self.lbl_tokens.setText("Tokens: " + str(total_tokens))
        self.lbl_chars.setText("Chars: " + str(total_chars))
        self.lbl_words.setText("Words: " + str(total_words))
        self.lbl_lines.setText("Lines: " + str(total_lines))
        self.lbl_time.setText("Time: " + str(round(elapsed, 2)) + "s")
        cost = (total_tokens / 1000.0) * 0.03
        self.lbl_cost.setText("Est. cost (GPT-4 input): $" + str(round(cost, 2)))
        self.lbl_status.setText("Done. " + str(total_tokens) + " tokens in " + str(round(elapsed, 2)) + "s")

    def _on_row_click(self, item):
        if item.column() != 5:
            return
        row = item.row()
        fpath_item = self.table.item(row, 0)
        if not fpath_item:
            return
        fpath = fpath_item.data(Qt.ItemDataRole.UserRole)
        if not fpath or not os.path.isfile(fpath):
            return
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read(5000)
        except Exception:
            content = "[read error]"
        self.table.setItem(row, 5, QTableWidgetItem(content[:200] + "..." if len(content) > 200 else content))

    def _cancel_count(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.lbl_status.setText("Cancelled")
            self.progress.setVisible(False)

    def _export_csv(self):
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Count tokens first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "token_counts.csv", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["File", "Path", "Tokens", "Chars", "Words", "Lines"])
            for row in range(self.table.rowCount()):
                fitem = self.table.item(row, 0)
                fpath = fitem.data(Qt.ItemDataRole.UserRole) if fitem else ""
                fname = fitem.text() if fitem else ""
                tokens = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
                chars = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
                words = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
                lines = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
                writer.writerow([fname, fpath, tokens, chars, words, lines])
        self.lbl_status.setText("Exported to " + path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        exts = self._get_extensions()
        recursive = self.cb_recursive.isChecked()
        count_before = len(self.files)
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            if os.path.isfile(path):
                if exts:
                    ext = os.path.splitext(path)[1].lower()
                    if ext not in exts:
                        continue
                if path not in self.files:
                    self.files.append(path)
            elif os.path.isdir(path):
                if recursive:
                    for dirpath, dirnames, filenames in os.walk(path):
                        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git", "node_modules", ".venv", "venv")]
                        for fname in filenames:
                            fpath = os.path.join(dirpath, fname)
                            if exts:
                                ext = os.path.splitext(fname)[1].lower()
                                if ext not in exts:
                                    continue
                            if fpath not in self.files:
                                self.files.append(fpath)
                else:
                    for fname in os.listdir(path):
                        fpath = os.path.join(path, fname)
                        if not os.path.isfile(fpath):
                            continue
                        if exts:
                            ext = os.path.splitext(fname)[1].lower()
                            if ext not in exts:
                                continue
                        if fpath not in self.files:
                            self.files.append(fpath)
        added = len(self.files) - count_before
        self.lbl_status.setText("Dropped " + str(added) + " files (total: " + str(len(self.files)) + ")")
        self.lbl_files.setText("Files: " + str(len(self.files)))


def main():
    app = QApplication(sys.argv)
    window = TokenCounter()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
