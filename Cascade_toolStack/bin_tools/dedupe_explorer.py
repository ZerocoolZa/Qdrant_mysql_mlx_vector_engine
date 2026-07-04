#!/usr/bin/env python3
#[@GHOST]{("file_path=Cascade_toolStack/bin_tools/dedupe_explorer.py";"identity=dedupe_explorer.py";"purpose=PyQt6 GUI for exploring and safely deduplicating CODEBASE.python_files";"date=2026-06-28";"version=1.0";"author=Cascade";"chat_link=")}
#[@VBSTYLE]{[@Pass]{"PyQt6";"Tuple3";"report()";"Run()";"self.state";"PascalCase";"UPPERCASE";"spaces"}[@Fail]{"print";"decorators";"hardcoded";"self._";"tabs";"trailing_whitespace"}[@Unsure]{""}}
#[@FILEID]{("session_id=auto";"context=CODEBASE deduplication explorer";"purpose=GUI for safe dedupe of python_files")}
#[@SUMMARY]{("Created on 2026-06-28";"auto_stamped=true")}

import sys
import mysql.connector
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
    QProgressBar, QHeaderView, QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt, QTimer

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "CODEBASE",
}


class DedupeExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CODEBASE Dedupe Explorer — python_files")
        self.resize(1100, 700)
        self.conn = None
        self.selected_hash = None
        self.deletable_ids = []
        self._build_ui()
        self._connect()
        if self.conn:
            self._load_duplicates()

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        self.status_label = QLabel("Connecting to CODEBASE...")
        self.status_label.setStyleSheet("color: #888; padding: 4px;")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        splitter = QSplitter(Qt.Orientation.Vertical)

        top_panel = QWidget()
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)

        top_header = QHBoxLayout()
        top_header.addWidget(QLabel("<b>Duplicate Groups</b> (click a row to inspect)"))
        self.waste_label = QLabel("")
        self.waste_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        top_header.addStretch()
        top_header.addWidget(self.waste_label)
        top_layout.addLayout(top_header)

        self.dup_table = QTableWidget()
        self.dup_table.setColumnCount(4)
        self.dup_table.setHorizontalHeaderLabels(["Content Hash", "Copies", "Wasted MB", "First Filename"])
        self.dup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.dup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.dup_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.dup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.dup_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.dup_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.dup_table.cellClicked.connect(self._on_dup_click)
        top_layout.addWidget(self.dup_table)

        splitter.addWidget(top_panel)

        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        bottom_header = QHBoxLayout()
        bottom_header.addWidget(QLabel("<b>Rows in Selected Group</b> (green = canonical, red = deletable)"))
        bottom_header.addStretch()
        bottom_layout.addLayout(bottom_header)

        self.row_table = QTableWidget()
        self.row_table.setColumnCount(5)
        self.row_table.setHorizontalHeaderLabels(["ID", "Filename", "Full Path", "Size KB", "Status"])
        self.row_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.row_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.row_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.row_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.row_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.row_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        bottom_layout.addWidget(self.row_table)

        splitter.addWidget(bottom_panel)

        layout.addWidget(splitter)

        btn_row = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Reload duplicate groups from database")
        self.refresh_btn.clicked.connect(self._load_duplicates)
        btn_row.addWidget(self.refresh_btn)

        self.preview_btn = QPushButton("Preview Deletables")
        self.preview_btn.setToolTip("Show which rows would be deleted (keeps oldest ID per hash)")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._preview_deletables)
        btn_row.addWidget(self.preview_btn)

        self.delete_btn = QPushButton("Safe Delete (Transaction)")
        self.delete_btn.setToolTip("Delete duplicates in a transaction. Rolls back on error. Keeps MIN(id) per hash.")
        self.delete_btn.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._safe_delete)
        btn_row.addWidget(self.delete_btn)

        self.all_dupes_btn = QPushButton("Delete ALL Dupes (Transaction)")
        self.all_dupes_btn.setToolTip("Delete ALL 620K duplicates in one transaction. Keeps MIN(id) per hash. Rollback on error.")
        self.all_dupes_btn.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold;")
        self.all_dupes_btn.clicked.connect(self._delete_all_dupes)
        btn_row.addWidget(self.all_dupes_btn)

        btn_row.addStretch()

        self.summary_btn = QPushButton("Summary")
        self.summary_btn.setToolTip("Show overall dedup statistics")
        self.summary_btn.clicked.connect(self._show_summary)
        btn_row.addWidget(self.summary_btn)

        layout.addLayout(btn_row)

        self.setCentralWidget(central)

    def _connect(self):
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.status_label.setText("Connected to CODEBASE")
            self.status_label.setStyleSheet("color: #27ae60; padding: 4px;")
        except Exception as e:
            self.status_label.setText("Connection failed: %s" % str(e))
            self.status_label.setStyleSheet("color: #e74c3c; padding: 4px;")

    def _load_duplicates(self):
        if not self.conn:
            return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Loading duplicate groups...")
        QApplication.processEvents()

        try:
            cur = self.conn.cursor(dictionary=True)
            cur.execute("""
                SELECT content_hash, COUNT(*) AS cnt,
                       ROUND(SUM(file_size) / 1024 / 1024, 1) AS total_mb,
                       ROUND((SUM(file_size) - MIN(file_size)) / 1024 / 1024, 1) AS wasted_mb,
                       SUBSTRING_INDEX(GROUP_CONCAT(filename ORDER BY id SEPARATOR '||'), '||', 1) AS first_filename
                FROM python_files
                WHERE content_hash IS NOT NULL
                GROUP BY content_hash
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC
                LIMIT 500
            """)
            rows = cur.fetchall()
            cur.close()

            self.dup_table.setRowCount(len(rows))
            total_waste = 0.0
            for i, row in enumerate(rows):
                self.dup_table.setItem(i, 0, QTableWidgetItem(row["content_hash"][:16] + "..."))
                self.dup_table.setItem(i, 1, QTableWidgetItem(str(row["cnt"])))
                self.dup_table.setItem(i, 2, QTableWidgetItem(str(row["wasted_mb"])))
                self.dup_table.setItem(i, 3, QTableWidgetItem(row["first_filename"] or ""))
                self.dup_table.item(i, 0).setToolTip(row["content_hash"])
                total_waste += row["wasted_mb"]

            self.waste_label.setText("Total wasted (top 500): %.1f MB" % total_waste)
            self.status_label.setText("Loaded %d duplicate groups" % len(rows))
        except Exception as e:
            self.status_label.setText("Error: %s" % str(e))
            self.status_label.setStyleSheet("color: #e74c3c; padding: 4px;")
        finally:
            self.progress.setVisible(False)

    def _on_dup_click(self, row, col):
        hash_item = self.dup_table.item(row, 0)
        if not hash_item:
            return
        self.selected_hash = hash_item.toolTip()
        self.preview_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self._inspect_rows()

    def _inspect_rows(self):
        if not self.selected_hash or not self.conn:
            return
        try:
            cur = self.conn.cursor(dictionary=True)
            cur.execute("""
                SELECT id, filename, full_path, file_size, line_count, created_at
                FROM python_files
                WHERE content_hash = %s
                ORDER BY id ASC
            """, (self.selected_hash,))
            rows = cur.fetchall()
            cur.close()

            self.row_table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                status = "CANONICAL (keep)" if i == 0 else "DUPLICATE"
                self.row_table.setItem(i, 0, QTableWidgetItem(str(row["id"])))
                self.row_table.setItem(i, 1, QTableWidgetItem(row["filename"] or ""))
                self.row_table.setItem(i, 2, QTableWidgetItem(row["full_path"] or ""))
                self.row_table.setItem(i, 3, QTableWidgetItem("%.1f" % ((row["file_size"] or 0) / 1024)))
                self.row_table.setItem(i, 4, QTableWidgetItem(status))
                if i == 0:
                    self.row_table.item(i, 4).setForeground(Qt.GlobalColor.green)
                else:
                    self.row_table.item(i, 4).setForeground(Qt.GlobalColor.red)

            self.status_label.setText("Inspecting %d rows for hash %s..." % (len(rows), self.selected_hash[:16]))
        except Exception as e:
            self.status_label.setText("Error: %s" % str(e))

    def _preview_deletables(self):
        if not self.selected_hash or not self.conn:
            return
        try:
            cur = self.conn.cursor(dictionary=True)
            cur.execute("""
                SELECT id, filename, full_path, file_size
                FROM python_files
                WHERE content_hash = %s
                  AND id NOT IN (
                      SELECT MIN(id) FROM python_files WHERE content_hash = %s
                  )
                ORDER BY id
            """, (self.selected_hash, self.selected_hash))
            rows = cur.fetchall()
            cur.close()

            self.deletable_ids = [r["id"] for r in rows]
            self.row_table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                self.row_table.setItem(i, 0, QTableWidgetItem(str(row["id"])))
                self.row_table.setItem(i, 1, QTableWidgetItem(row["filename"] or ""))
                self.row_table.setItem(i, 2, QTableWidgetItem(row["full_path"] or ""))
                self.row_table.setItem(i, 3, QTableWidgetItem("%.1f" % ((row["file_size"] or 0) / 1024)))
                self.row_table.setItem(i, 4, QTableWidgetItem("DELETE"))
                self.row_table.item(i, 4).setForeground(Qt.GlobalColor.red)

            self.status_label.setText("%d rows safe to delete (canonical preserved)" % len(rows))
        except Exception as e:
            self.status_label.setText("Error: %s" % str(e))

    def _safe_delete(self):
        if not self.deletable_ids or not self.conn:
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete %d duplicate rows?\nCanonical (MIN id) will be kept.\nTransaction will rollback on error." % len(self.deletable_ids),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            cur = self.conn.cursor()
            self.conn.start_transaction()
            ids_str = ",".join(str(i) for i in self.deletable_ids)
            cur.execute("DELETE FROM python_files WHERE id IN (%s)" % ids_str)
            deleted = cur.rowcount
            self.conn.commit()
            cur.close()
            self.status_label.setText("Deleted %d rows. Transaction committed." % deleted)
            self.status_label.setStyleSheet("color: #27ae60; padding: 4px;")
            self.deletable_ids = []
            self.delete_btn.setEnabled(False)
            self._load_duplicates()
        except Exception as e:
            self.conn.rollback()
            self.status_label.setText("FAILED — rolled back: %s" % str(e))
            self.status_label.setStyleSheet("color: #e74c3c; padding: 4px;")

    def _delete_all_dupes(self):
        if not self.conn:
            return
        reply = QMessageBox.question(
            self, "DELETE ALL DUPLICATES",
            "This will delete ALL duplicate rows in python_files.\n"
            "Keeps MIN(id) per content_hash.\n"
            "Transaction with rollback on error.\n\n"
            "This may take several minutes. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Deleting all duplicates (transaction)...")
        QApplication.processEvents()

        try:
            cur = self.conn.cursor()
            self.conn.start_transaction()
            cur.execute("""
                DELETE p1 FROM python_files p1
                INNER JOIN (
                    SELECT MIN(id) AS min_id, content_hash
                    FROM python_files
                    WHERE content_hash IS NOT NULL
                    GROUP BY content_hash
                ) p2 ON p1.content_hash = p2.content_hash AND p1.id > p2.min_id
            """)
            deleted = cur.rowcount
            self.conn.commit()
            cur.close()
            self.status_label.setText("Deleted %d duplicate rows. Transaction committed." % deleted)
            self.status_label.setStyleSheet("color: #27ae60; padding: 4px;")
            self._load_duplicates()
        except Exception as e:
            self.conn.rollback()
            self.status_label.setText("FAILED — rolled back: %s" % str(e))
            self.status_label.setStyleSheet("color: #e74c3c; padding: 4px;")
        finally:
            self.progress.setVisible(False)

    def _show_summary(self):
        if not self.conn:
            return
        try:
            cur = self.conn.cursor(dictionary=True)
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(DISTINCT content_hash) AS unique_files,
                       COUNT(*) - COUNT(DISTINCT content_hash) AS dupes,
                       ROUND(SUM(file_size) / 1024 / 1024 / 1024, 2) AS total_gb,
                       ROUND((SUM(file_size) - SUM(CASE WHEN rn = 1 THEN file_size ELSE 0 END)) / 1024 / 1024 / 1024, 2) AS wasted_gb
                FROM (
                    SELECT file_size, content_hash,
                           ROW_NUMBER() OVER (PARTITION BY content_hash ORDER BY id) AS rn
                    FROM python_files
                    WHERE content_hash IS NOT NULL
                ) t
            """)
            row = cur.fetchone()
            cur.close()

            msg = (
                "CODEBASE python_files Summary\n\n"
                "Total rows:      %s\n"
                "Unique files:    %s\n"
                "Duplicates:      %s\n"
                "Total content:   %s GB\n"
                "Wasted on dupes: %s GB\n\n"
                "Dupe rate:       %.1f%%" % (
                    row["total"], row["unique_files"], row["dupes"],
                    row["total_gb"], row["wasted_gb"],
                    (row["dupes"] / row["total"] * 100) if row["total"] else 0
                )
            )
            QMessageBox.information(self, "Summary", msg)
        except Exception as e:
            self.status_label.setText("Error: %s" % str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DedupeExplorer()
    window.show()
    sys.exit(app.exec())
