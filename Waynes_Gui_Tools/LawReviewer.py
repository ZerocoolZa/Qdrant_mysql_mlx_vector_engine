#[@GHOST]
#[@VBSTYLE]
#[@FILEID] LawReviewer.py
#[@SUMMARY] PyQt6 datagrid for reviewing extracted laws. Shows Law, Reason, Do, Dont, Decision, Comment.
#[@DATE] 2026-07-03
#[@AUTHOR] Cascade

import sys
import sqlite3
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QHeaderView
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QPalette


CHAT_DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Report/saved_sessions/Devin_Moseimport.db"


class LawReviewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.laws = self.LoadLawsFromDB()
        self.BuildUI()

    def LoadLawsFromDB(self):
        conn = sqlite3.connect(CHAT_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, law, reason, do_instead, dont_do, decision, comment
            FROM extracted_laws
            ORDER BY id
        """)
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def BuildUI(self):
        self.setWindowTitle("Law Reviewer")
        self.setMinimumSize(QSize(1200, 600))
        self.setStyleSheet("background-color: #1e1e1e;")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel(f"{len(self.laws)} Laws — Review Each One")
        title.setStyleSheet("color: #569cd6; font-size: 16px; font-weight: bold;")
        main_layout.addWidget(title)

        self.table = QTableWidget(len(self.laws), 6)
        self.table.setHorizontalHeaderLabels(["Law", "Reason", "Do", "Don't", "Decision", "Comment"])
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e; color: #d4d4d4;
                gridline-color: #3c3c3c; border: 1px solid #3c3c3c;
            }
            QHeaderView::section {
                background-color: #2d2d2d; color: #569cd6;
                padding: 6px; border: 1px solid #3c3c3c; font-weight: bold; font-size: 13px;
            }
            QTableWidget::item { padding: 6px; }
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(4, 130)

        for i, law in enumerate(self.laws):
            self.table.setItem(i, 0, QTableWidgetItem(law["law"]))
            self.table.setItem(i, 1, QTableWidgetItem(law.get("reason") or ""))
            self.table.setItem(i, 2, QTableWidgetItem(law.get("do_instead") or ""))
            self.table.setItem(i, 3, QTableWidgetItem(law.get("dont_do") or ""))

            for col in range(4):
                item = self.table.item(i, col)
                if item:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            combo = QComboBox()
            combo.addItem("  Pending  ")
            combo.addItem("  Yes  ")
            combo.addItem("  No  ")
            existing = law.get("decision")
            if existing == "yes":
                combo.setCurrentIndex(1)
            elif existing == "no":
                combo.setCurrentIndex(2)
            combo.setStyleSheet("""
                QComboBox {
                    background-color: #3c3c3c; color: #d4d4d4;
                    padding: 8px 10px; border: 2px solid #569cd6;
                    border-radius: 4px; font-weight: bold; font-size: 14px;
                }
                QComboBox::drop-down { border: none; width: 30px; }
                QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #569cd6; }
                QComboBox QAbstractItemView {
                    background-color: #2d2d2d; color: #d4d4d4;
                    selection-background-color: #264f78; padding: 4px;
                }
            """)
            combo.setMinimumHeight(36)
            self.table.setCellWidget(i, 4, combo)

            comment_item = QTableWidgetItem(law.get("comment") or "")
            self.table.setItem(i, 5, comment_item)

        self.table.verticalHeader().setDefaultSectionSize(70)
        self.table.setShowGrid(True)
        main_layout.addWidget(self.table)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        btn_save = QPushButton("Save to DB")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #264f78; color: white; border: none;
                padding: 8px 24px; border-radius: 3px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #3674b8; }
        """)
        btn_save.clicked.connect(self.SaveResults)
        bottom_layout.addWidget(btn_save)

        btn_sql = QPushButton("Save + Generate SQL")
        btn_sql.setStyleSheet("""
            QPushButton {
                background-color: #264f78; color: white; border: none;
                padding: 8px 24px; border-radius: 3px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #3674b8; }
        """)
        btn_sql.clicked.connect(self.SaveAndGenerateSQL)
        bottom_layout.addWidget(btn_sql)

        bottom_layout.addStretch()

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #888; font-size: 12px;")
        bottom_layout.addWidget(self.progress_label)

        main_layout.addLayout(bottom_layout)

        self.statusBar().showMessage("Read each law. Pick Yes or No. Add a comment if you want.")
        self.statusBar().setStyleSheet("color: #888; font-size: 11px;")

    def SaveResults(self):
        conn = sqlite3.connect(CHAT_DB)
        cur = conn.cursor()
        reviewed = 0
        approved = 0
        rejected = 0
        for i, law in enumerate(self.laws):
            combo = self.table.cellWidget(i, 4)
            comment_item = self.table.item(i, 5)
            if not combo:
                continue
            decision = combo.currentText().strip()
            comment = comment_item.text().strip() if comment_item else ""
            if "Pending" in decision:
                decision_db = None
            elif "Yes" in decision:
                decision_db = "yes"
            else:
                decision_db = "no"
            cur.execute(
                "UPDATE extracted_laws SET decision = ?, comment = ? WHERE id = ?",
                (decision_db, comment, law["id"])
            )
            if decision_db:
                reviewed += 1
                if decision_db == "yes":
                    approved += 1
                else:
                    rejected += 1
        conn.commit()
        conn.close()
        self.progress_label.setText(f"{reviewed} reviewed ({approved} approved, {rejected} rejected)")
        self.statusBar().showMessage(f"Saved {reviewed} reviews to database")

    def SaveAndGenerateSQL(self):
        self.SaveResults()

        conn = sqlite3.connect(CHAT_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM extracted_laws WHERE decision = 'yes' ORDER BY id")
        approved = cur.fetchall()
        conn.close()

        if not approved:
            self.statusBar().showMessage("No approved laws to generate SQL for.")
            return

        sql_path = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Report/approved_laws.sql"
        with open(sql_path, "w") as f:
            f.write("-- Approved laws for diagnostic_kb.law table\n")
            f.write(f"-- Date: {datetime.now().isoformat()}\n")
            f.write(f"-- Approved: {len(approved)} of {len(self.laws)} laws\n\n")

            for row in approved:
                escaped_law = row["law"].replace("'", "\\'")
                escaped_reason = (row["reason"] or "").replace("'", "\\'")
                escaped_do = (row["do_instead"] or "").replace("'", "\\'")
                escaped_dont = (row["dont_do"] or "").replace("'", "\\'")

                f.write(f"-- Law: {row['law']}\n")
                f.write(f"INSERT INTO law (law_text, reason, do_instead, dont_do, source)\n")
                f.write(f"VALUES ('{escaped_law}', '{escaped_reason}', '{escaped_do}', '{escaped_dont}', 'user_review');\n\n")

        self.statusBar().showMessage(f"Saved {len(approved)} approved laws to {sql_path}")


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

    reviewer = LawReviewer()
    reviewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
