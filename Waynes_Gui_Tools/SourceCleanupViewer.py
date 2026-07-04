#[@GHOST]
#[@VBSTYLE]
#[@FILEID] SourceCleanupViewer.py
#[@SUMMARY] PyQt6 GUI showing the full cleanup chain: garbage question -> source row -> original JSON line -> regex pattern that matched it
#[@DATE] 2026-07-04
#[@AUTHOR] Cascade
#[@CLASS] SourceCleanupViewer
#[@METHOD] Run

import sys
import os
import json
import zipfile
import mysql.connector
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QHeaderView, QSpinBox, QTextEdit, QSplitter, QGroupBox, QProgressBar
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QPalette, QFont


DB_LAWS = {'user': 'root', 'host': 'localhost', 'database': 'laws'}
DB_CHATGPT = {'user': 'root', 'host': 'localhost', 'database': 'chatgpt_export'}
ZIP_PATH = "/Users/wws/Downloads/Procecced_chatgpt- 18 -june.zip"

REGEX_PATTERNS = [
    ("Explicit Pattern 1", r'([A-Z][^.!?\\n]{4,900}?\\?)', "Matches anything starting uppercase, 4+ chars, ending with ?"),
    ("Explicit Pattern 2", r'((?:but|and|or|so|well|actually|wait|no|right|look|like)\\s+[^.!?\\n]{4,900}?\\?)', "Matches lowercase-start fragments ending with ?"),
]

PAGE_SIZE = 50


class SourceCleanupViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.connLaws = mysql.connector.connect(**DB_LAWS)
        self.connChat = mysql.connector.connect(**DB_CHATGPT)
        self.currentPage = 0
        self.pageSize = PAGE_SIZE
        self.filter = "ALL"
        self.rows = []
        self.jsonCache = {}
        self.BuildUI()
        self.LoadData()

    def BuildUI(self):
        self.setWindowTitle("Source Cleanup Viewer - Trace Garbage to Origin")
        self.setMinimumSize(QSize(1400, 850))
        self.setStyleSheet("background-color: #1e1e1e;")

        central = QWidget()
        self.setCentralWidget(central)
        mainLayout = QVBoxLayout(central)
        mainLayout.setSpacing(6)
        mainLayout.setContentsMargins(8, 8, 8, 8)

        # Title
        title = QLabel("Question Source Cleanup - Tracing Garbage Back to Original JSON")
        title.setStyleSheet("color: #569cd6; font-size: 15px; font-weight: bold; padding: 4px;")
        mainLayout.addWidget(title)

        # Stats
        self.statsLabel = QLabel("Loading...")
        self.statsLabel.setStyleSheet("color: #d4d4d4; font-size: 12px; padding: 2px;")
        mainLayout.addWidget(self.statsLabel)

        # Filter bar
        filterLayout = QHBoxLayout()
        filterLayout.setSpacing(8)

        lbl = QLabel("Filter:")
        lbl.setStyleSheet("color: #d4d4d4; font-size: 12px;")
        filterLayout.addWidget(lbl)

        self.filterCombo = QComboBox()
        self.filterCombo.addItems(["ALL", "DELETE", "KEEP", "binary", "random_id", "base64", "pasted_text", "short_question", "long_question", "normal"])
        self.filterCombo.setStyleSheet(self._comboStyle())
        self.filterCombo.currentTextChanged.connect(self.OnFilterChanged)
        filterLayout.addWidget(self.filterCombo)

        lbl2 = QLabel("Page size:")
        lbl2.setStyleSheet("color: #d4d4d4; font-size: 12px;")
        filterLayout.addWidget(lbl2)

        self.pageSizeSpin = QSpinBox()
        self.pageSizeSpin.setRange(10, 200)
        self.pageSizeSpin.setValue(self.pageSize)
        self.pageSizeSpin.setStyleSheet(self._spinStyle())
        self.pageSizeSpin.valueChanged.connect(self.OnPageSizeChanged)
        filterLayout.addWidget(self.pageSizeSpin)

        self.prevBtn = QPushButton("<< Prev")
        self.prevBtn.setStyleSheet(self._btnStyle("#264f78"))
        self.prevBtn.clicked.connect(self.PrevPage)
        filterLayout.addWidget(self.prevBtn)

        self.pageLabel = QLabel("Page 0")
        self.pageLabel.setStyleSheet("color: #d4d4d4; font-size: 12px; padding: 0 10px;")
        filterLayout.addWidget(self.pageLabel)

        self.nextBtn = QPushButton("Next >>")
        self.nextBtn.setStyleSheet(self._btnStyle("#264f78"))
        self.nextBtn.clicked.connect(self.NextPage)
        filterLayout.addWidget(self.nextBtn)

        filterLayout.addStretch()

        self.cleanSourceBtn = QPushButton("Clean Source DB (chatgpt_export.Questions)")
        self.cleanSourceBtn.setStyleSheet(self._btnStyle("#aa3333", True))
        self.cleanSourceBtn.clicked.connect(self.CleanSourceDb)
        filterLayout.addWidget(self.cleanSourceBtn)

        self.cleanAllBtn = QPushButton("Clean ALL DBs (source + laws)")
        self.cleanAllBtn.setStyleSheet(self._btnStyle("#aa3333", True))
        self.cleanAllBtn.clicked.connect(self.CleanAllDbs)
        filterLayout.addWidget(self.cleanAllBtn)

        mainLayout.addLayout(filterLayout)

        # Splitter: top = question table, bottom = detail view
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: #3c3c3c; }")

        # Top: Question table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Q.ID", "Verdict", "Category", "Question Text", "Source DB", "Source Table", "Src File", "Src Line"])
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e; color: #d4d4d4;
                gridline-color: #3c3c3c; border: 1px solid #3c3c3c;
            }
            QHeaderView::section {
                background-color: #2d2d2d; color: #569cd6;
                padding: 6px; border: 1px solid #3c3c3c; font-weight: bold; font-size: 12px;
            }
            QTableWidget::item { padding: 4px; }
        """)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 100)
        self.table.setColumnWidth(6, 150)
        self.table.setColumnWidth(7, 70)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.selectionModel().currentRowChanged.connect(self.OnRowSelected)
        splitter.addWidget(self.table)

        # Bottom: Detail view
        detailWidget = QWidget()
        detailLayout = QVBoxLayout(detailWidget)
        detailLayout.setContentsMargins(0, 0, 0, 0)
        detailLayout.setSpacing(4)

        # Detail sections in horizontal split
        detailSplit = QSplitter(Qt.Orientation.Horizontal)
        detailSplit.setStyleSheet("QSplitter::handle { background-color: #3c3c3c; }")

        # Left: Chain trace
        chainGroup = QGroupBox("Cleanup Chain")
        chainGroup.setStyleSheet(self._groupStyle())
        chainLayout = QVBoxLayout(chainGroup)

        self.chainText = QTextEdit()
        self.chainText.setReadOnly(True)
        self.chainText.setStyleSheet("""
            QTextEdit {
                background-color: #252526; color: #d4d4d4;
                border: 1px solid #3c3c3c; font-family: 'Menlo', monospace; font-size: 12px;
            }
        """)
        chainLayout.addWidget(self.chainText)

        detailSplit.addWidget(chainGroup)

        # Right: Original JSON source
        jsonGroup = QGroupBox("Original JSON Source (from zip)")
        jsonGroup.setStyleSheet(self._groupStyle())
        jsonLayout = QVBoxLayout(jsonGroup)

        self.jsonText = QTextEdit()
        self.jsonText.setReadOnly(True)
        self.jsonText.setStyleSheet("""
            QTextEdit {
                background-color: #252526; color: #ce9178;
                border: 1px solid #3c3c3c; font-family: 'Menlo', monospace; font-size: 11px;
            }
        """)
        jsonLayout.addWidget(self.jsonText)

        detailSplit.addWidget(jsonGroup)

        detailLayout.addWidget(detailSplit)
        splitter.addWidget(detailWidget)

        splitter.setSizes([400, 350])
        mainLayout.addWidget(splitter)

        # Progress bar
        self.progressBar = QProgressBar()
        self.progressBar.setVisible(False)
        self.progressBar.setStyleSheet("QProgressBar { background-color: #2d2d2d; border: 1px solid #3c3c3c; text-align: center; color: #d4d4d4; } QProgressBar::chunk { background-color: #569cd6; }")
        mainLayout.addWidget(self.progressBar)

        self.statusBar().setStyleSheet("color: #888; font-size: 11px;")
        self.statusBar().showMessage("Select a row to trace the garbage back to its source.")

    def LoadData(self):
        cur = self.connLaws.cursor()

        # Stats
        cur.execute("SELECT verdict, COUNT(*) FROM question_review GROUP BY verdict ORDER BY COUNT(*) DESC")
        stats = cur.fetchall()
        statsText = " | ".join(["%s: %d" % (s[0], s[1]) for s in stats])
        total = sum(s[1] for s in stats)
        self.statsLabel.setText("%s | Total: %d" % (statsText, total))

        # Query
        offset = self.currentPage * self.pageSize
        if self.filter == "ALL":
            cur.execute("""
                SELECT qr.questionId, qr.verdict, qr.category, q.questionText,
                       q.sourceDb, q.sourceTable, q.sourceDb, q.sourceTable
                FROM question_review qr
                JOIN question q ON qr.questionId = q.id
                ORDER BY qr.verdict, qr.category, qr.questionId
                LIMIT %s OFFSET %s
            """, (self.pageSize, offset))
        elif self.filter in ("DELETE", "KEEP"):
            cur.execute("""
                SELECT qr.questionId, qr.verdict, qr.category, q.questionText,
                       q.sourceDb, q.sourceTable, q.sourceDb, q.sourceTable
                FROM question_review qr
                JOIN question q ON qr.questionId = q.id
                WHERE qr.verdict = %s
                ORDER BY qr.category, qr.questionId
                LIMIT %s OFFSET %s
            """, (self.filter, self.pageSize, offset))
        else:
            cur.execute("""
                SELECT qr.questionId, qr.verdict, qr.category, q.questionText,
                       q.sourceDb, q.sourceTable, q.sourceDb, q.sourceTable
                FROM question_review qr
                JOIN question q ON qr.questionId = q.id
                WHERE qr.category = %s
                ORDER BY qr.questionId
                LIMIT %s OFFSET %s
            """, (self.filter, self.pageSize, offset))

        self.rows = cur.fetchall()
        cur.close()

        self.pageLabel.setText("Page %d (%d rows)" % (self.currentPage, len(self.rows)))
        self.PopulateTable()

    def PopulateTable(self):
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            qId, verdict, category, qText, srcDb, srcTable, _, _ = row

            item = QTableWidgetItem(str(qId))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item)

            item = QTableWidgetItem(verdict)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if verdict == "DELETE":
                item.setForeground(QColor("#ff6666"))
            elif verdict == "KEEP":
                item.setForeground(QColor("#66ff66"))
            self.table.setItem(i, 1, item)

            item = QTableWidgetItem(category)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, item)

            item = QTableWidgetItem(str(qText)[:150])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 3, item)

            item = QTableWidgetItem(srcDb)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 4, item)

            item = QTableWidgetItem(srcTable)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 5, item)

            # Get source file and line from chatgpt_export
            srcFile = ""
            srcLine = ""
            if srcDb == "chatgpt_export":
                cur = self.connChat.cursor()
                cur.execute("SELECT source_file, source_line FROM Questions WHERE question_text = %s LIMIT 1", (qText,))
                src = cur.fetchone()
                cur.close()
                if src:
                    srcFile = str(src[0]) if src[0] else ""
                    srcLine = str(src[1]) if src[1] else ""
            elif srcDb == "vb_shared":
                srcFile = "(vb_shared)"
                srcLine = ""
            elif srcDb == "questions":
                srcFile = "(questions DB)"
                srcLine = ""

            item = QTableWidgetItem(srcFile)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 6, item)

            item = QTableWidgetItem(srcLine)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 7, item)

    def OnRowSelected(self, current, previous):
        if not current or current.row() < 0 or current.row() >= len(self.rows):
            return
        row = self.rows[current.row()]
        qId, verdict, category, qText, srcDb, srcTable, _, _ = row

        # Build chain trace
        chainLines = []
        chainLines.append("=== CLEANUP CHAIN ===")
        chainLines.append("")
        chainLines.append("1. LAWS QUESTION (downstream)")
        chainLines.append("   laws.question #%d" % qId)
        chainLines.append("   text: %r" % qText[:200])
        chainLines.append("   verdict: %s" % verdict)
        chainLines.append("   category: %s" % category)
        chainLines.append("   reason: (from question_review)")
        chainLines.append("")

        # Trace to source
        if srcDb == "chatgpt_export":
            cur = self.connChat.cursor()
            cur.execute("SELECT id, question_text, source_file, source_line, source, context FROM Questions WHERE question_text = %s LIMIT 1", (qText,))
            src = cur.fetchone()
            cur.close()

            if src:
                chainLines.append("2. CHATGPT EXPORT (source DB)")
                chainLines.append("   chatgpt_export.Questions #%d" % src[0])
                chainLines.append("   source_file: %s" % src[2])
                chainLines.append("   source_line: %s" % src[3])
                chainLines.append("   source_type: %s" % src[4])
                if src[5]:
                    chainLines.append("   context: %r" % str(src[5])[:200])
                chainLines.append("")

                chainLines.append("3. REGEX PATTERN (root cause)")
                chainLines.append("   Pattern: %s" % REGEX_PATTERNS[0][0])
                chainLines.append("   Regex: %s" % REGEX_PATTERNS[0][1])
                chainLines.append("   Description: %s" % REGEX_PATTERNS[0][2])
                chainLines.append("")
                chainLines.append("   WHY IT MATCHED:")
                chainLines.append("   - Text starts with uppercase or lowercase keyword")
                chainLines.append("   - Text has 4+ characters")
                chainLines.append("   - Text ends with '?'")
                chainLines.append("   - NO filter for: real words, reference IDs, code fragments")
                chainLines.append("")

                chainLines.append("4. ORIGINAL JSON (root source)")
                chainLines.append("   File: %s (in zip)" % src[2])
                chainLines.append("   Line: %s" % src[3])
                chainLines.append("   Loading JSON content...")

                # Load JSON from zip
                self.LoadJsonFromZip(src[2], src[3])
            else:
                chainLines.append("2. NOT FOUND in chatgpt_export.Questions")
                self.jsonText.setPlainText("(not found in source)")
        elif srcDb == "vb_shared":
            chainLines.append("2. VB_SHARED (source DB)")
            chainLines.append("   vb_shared.know_questions")
            chainLines.append("   (migrated from chatgpt_export or questions DB)")
            self.jsonText.setPlainText("(source is vb_shared.know_questions - not from JSON scan)")
        else:
            chainLines.append("2. SOURCE: %s.%s" % (srcDb, srcTable))
            self.jsonText.setPlainText("(source: %s.%s)" % (srcDb, srcTable))

        chainLines.append("")
        chainLines.append("=== FIX REQUIRED ===")
        chainLines.append("")
        chainLines.append("Root cause: question_harvester.py regex has no word validation")
        chainLines.append("File: /Users/wws/Downloads/question_harvester.py line 110-112")
        chainLines.append("")
        chainLines.append("Fix: Add filters to EXPLICIT_PATTERNS:")
        chainLines.append("  - Require at least 1 real English word (4+ consecutive letters)")
        chainLines.append("  - Reject reference IDs (PMC*, NBK*, S0*, DT0*)")
        chainLines.append("  - Reject base64-like strings (mixed case + digits, no spaces)")
        chainLines.append("  - Reject code fragments (def, import, SELECT, return)")
        chainLines.append("  - Reject binary/non-printable characters")
        chainLines.append("")
        chainLines.append("Then: re-run harvester on original JSON files")
        chainLines.append("Then: clean all downstream DBs (chatgpt_export, vb_shared, laws)")

        self.chainText.setPlainText("\n".join(chainLines))

    def LoadJsonFromZip(self, sourceFile, sourceLine):
        try:
            lineNum = int(sourceLine) if sourceLine else 0
        except (ValueError, TypeError):
            lineNum = 0

        # Cache the file content
        if sourceFile not in self.jsonCache:
            try:
                zf = zipfile.ZipFile(ZIP_PATH, 'r')
                if sourceFile in zf.namelist():
                    content = zf.read(sourceFile).decode('utf-8', errors='replace')
                    self.jsonCache[sourceFile] = content.split('\n')
                else:
                    self.jsonCache[sourceFile] = None
                zf.close()
            except Exception as e:
                self.jsonText.setPlainText("Error reading zip: %s" % str(e))
                return

        lines = self.jsonCache[sourceFile]
        if not lines:
            self.jsonText.setPlainText("File %s not found in zip" % sourceFile)
            return

        # Show context: 5 lines before and 5 after
        start = max(0, lineNum - 5)
        end = min(len(lines), lineNum + 6)

        output = []
        output.append("File: %s (total %d lines)" % (sourceFile, len(lines)))
        output.append("Showing lines %d-%d (target line: %d)" % (start + 1, end, lineNum))
        output.append("=" * 80)
        for i in range(start, end):
            marker = " >>> " if i == lineNum else "     "
            lineContent = lines[i][:200] if i < len(lines) else ""
            output.append("%s%6d: %s" % (marker, i, lineContent))

        output.append("")
        output.append("=" * 80)
        output.append("The >>> line is where the harvester extracted the question from.")
        output.append("This is the original JSON content that produced the garbage question.")

        self.jsonText.setPlainText("\n".join(output))

    def CleanSourceDb(self):
        cur = self.connLaws.cursor()
        cur.execute("SELECT questionId FROM question_review WHERE verdict = 'DELETE'")
        deleteIds = [r[0] for r in cur.fetchall()]
        cur.close()

        self.progressBar.setVisible(True)
        self.progressBar.setMaximum(len(deleteIds))
        deleted = 0
        batch = 0

        curL = self.connLaws.cursor()
        curC = self.connChat.cursor()

        for qId in deleteIds:
            curL.execute("SELECT questionText, sourceDb FROM question WHERE id = %s", (qId,))
            row = curL.fetchone()
            if not row:
                continue
            qText, srcDb = row[0], row[1]

            if srcDb == "chatgpt_export":
                curC.execute("DELETE FROM Questions WHERE question_text = %s", (qText,))
            elif srcDb == "vb_shared":
                curC.execute("DELETE FROM know_questions WHERE question = %s", (qText,))

            curL.execute("DELETE FROM question WHERE id = %s", (qId,))
            curL.execute("DELETE FROM question_review WHERE questionId = %s", (qId,))
            deleted += 1
            batch += 1
            if batch >= 50:
                self.connLaws.commit()
                self.connChat.commit()
                self.progressBar.setValue(deleted)
                batch = 0

        self.connLaws.commit()
        self.connChat.commit()
        self.progressBar.setValue(deleted)
        self.progressBar.setVisible(False)
        curL.close()
        curC.close()
        self.statusBar().showMessage("Cleaned %d garbage questions from source + laws" % deleted)
        self.LoadData()

    def CleanAllDbs(self):
        self.CleanSourceDb()

    def OnFilterChanged(self, text):
        self.filter = text
        self.currentPage = 0
        self.LoadData()

    def OnPageSizeChanged(self, size):
        self.pageSize = size
        self.currentPage = 0
        self.LoadData()

    def PrevPage(self):
        if self.currentPage > 0:
            self.currentPage -= 1
            self.LoadData()

    def NextPage(self):
        if len(self.rows) == self.pageSize:
            self.currentPage += 1
            self.LoadData()

    def _comboStyle(self):
        return """
            QComboBox {
                background-color: #3c3c3c; color: #d4d4d4;
                padding: 6px 8px; border: 2px solid #569cd6;
                border-radius: 4px; font-weight: bold; font-size: 12px;
            }
            QComboBox::drop-down { border: none; width: 25px; }
            QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #569cd6; }
            QComboBox QAbstractItemView { background-color: #2d2d2d; color: #d4d4d4; selection-background-color: #264f78; padding: 4px; }
        """

    def _spinStyle(self):
        return "QSpinBox { background-color: #3c3c3c; color: #d4d4d4; padding: 4px 8px; border: 1px solid #569cd6; border-radius: 3px; font-size: 12px; }"

    def _btnStyle(self, color, bold=False):
        weight = "bold" if bold else "normal"
        return """
            QPushButton {
                background-color: %s; color: white; border: none;
                padding: 6px 16px; border-radius: 3px; font-weight: %s; font-size: 12px;
            }
            QPushButton:hover { background-color: #3674b8; }
        """ % (color, weight)

    def _groupStyle(self):
        return """
            QGroupBox {
                color: #569cd6; font-weight: bold; font-size: 12px;
                border: 1px solid #3c3c3c; border-radius: 4px;
                margin-top: 10px; padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(204, 204, 204))
    palette.setColor(QPalette.ColorRole.Base, QColor(37, 37, 38))
    palette.setColor(QPalette.ColorRole.Text, QColor(204, 204, 204))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    app.setPalette(palette)

    viewer = SourceCleanupViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
