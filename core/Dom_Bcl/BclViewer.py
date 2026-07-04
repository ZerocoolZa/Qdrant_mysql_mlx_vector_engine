#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/BclViewer.py"
# date="2026-08-18" author="Devin" session_id="bcl-ir-build"
# context="BCL IR database viewer - PyQt6 GUI to visualize normalized FK tables"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="BclViewer.py" domain="bcl_ir" authority="BclViewer"}
# [@SUMMARY]{summary="PyQt6 GUI viewer for BCL IR database. Tree view shows codebase > classes > methods > edges hierarchy. Detail panel shows full row data plus FK-linked source code from vb_code_test."}
# [@CLASS]{class="BclViewer" domain="bcl_ir" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
"""
BclViewer -- PyQt6 GUI for browsing the BCL IR database.

Tree view hierarchy:
  codebase
    +-- class
        +-- method
            +-- edge
    +-- unit
        +-- method

Detail panel shows:
  - Full row data for selected node
  - FK-linked source code from vb_code_test (for methods)
  - Parent class info (for methods)
  - Edge target resolution

Usage:
  python3 BclViewer.py
  python3 BclViewer.py --db bcl_ir
  python3 BclViewer.py --codebase vb_code_test_full
"""
import sys
import json
import argparse
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QTreeWidget,
    QTreeWidgetItem, QTextEdit, QLabel, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPalette

import mysql.connector


DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = ""
DB_NAME = "vb_code_test"


class BclViewer(QMainWindow):
    def __init__(self, db_name=DB_NAME, codebase_filter=None):
        super().__init__()
        self.db_name = db_name
        self.codebase_filter = codebase_filter
        self.conn = None
        self.setWindowTitle("BCL IR Viewer")
        self.resize(1400, 900)
        self._init_ui()
        self._connect_db()
        self._load_tree()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Codebase:"))
        self.cb_codebase = QComboBox()
        self.cb_codebase.setMinimumWidth(300)
        top_bar.addWidget(self.cb_codebase)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._load_tree)
        top_bar.addWidget(btn_refresh)
        btn_reload = QPushButton("Reload DB")
        btn_reload.clicked.connect(self._reload_db)
        top_bar.addWidget(btn_reload)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Node", "Type", "ID"])
        self.tree.setColumnWidth(0, 400)
        self.tree.setColumnWidth(1, 100)
        self.tree.setColumnWidth(2, 80)
        self.tree.itemClicked.connect(self._on_tree_click)
        splitter.addWidget(self.tree)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setFont(QFont("Menlo", 11))
        splitter.addWidget(self.detail)
        splitter.setSizes([500, 900])
        layout.addWidget(splitter)

        self.status = QLabel("Ready")
        layout.addWidget(self.status)

    def _connect_db(self):
        try:
            self.conn = mysql.connector.connect(
                user=DB_USER, password=DB_PASSWORD,
                host=DB_HOST, database=self.db_name
            )
            self.status.setText("Connected to " + self.db_name)
        except Exception as exc:
            self.status.setText("DB error: " + str(exc))

    def _reload_db(self):
        if self.conn:
            self.conn.close()
        self._connect_db()
        self._load_tree()

    def _load_tree(self):
        self.tree.clear()
        if not self.conn:
            return
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM bcl_codebases ORDER BY name")
        codebases = cursor.fetchall()
        self.cb_codebase.clear()
        for cb in codebases:
            self.cb_codebase.addItem(cb["name"], cb["id"])
        if self.codebase_filter:
            idx = self.cb_codebase.findText(self.codebase_filter)
            if idx >= 0:
                self.cb_codebase.setCurrentIndex(idx)
        for cb in codebases:
            cb_id = cb["id"]
            cb_node = QTreeWidgetItem([
                cb["name"], "codebase", str(cb_id)
            ])
            cb_node.setForeground(0, QColor("#0066cc"))
            cb_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "codebase", "id": cb_id, "data": cb})
            self._load_classes(cursor, cb_id, cb_node)
            self._load_units(cursor, cb_id, cb_node)
            self.tree.addTopLevelItem(cb_node)
            cb_node.setExpanded(True if self.codebase_filter else False)
        cursor.close()
        self.status.setText("Loaded " + str(len(codebases)) + " codebases")

    def _load_classes(self, cursor, cb_id, parent_node):
        cursor.execute(
            "SELECT * FROM bcl_classes WHERE codebase_id = %s ORDER BY class_name",
            (cb_id,)
        )
        classes = cursor.fetchall()
        classes_node = QTreeWidgetItem(["Classes (" + str(len(classes)) + ")", "group", ""])
        for cls in classes:
            cls_node = QTreeWidgetItem([
                cls["class_name"], "class", str(cls["id"])
            ])
            cls_node.setForeground(0, QColor("#008800"))
            cls_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "class", "id": cls["id"], "data": cls})
            self._load_methods(cursor, cb_id, cls["id"], cls_node)
            classes_node.addChild(cls_node)
        parent_node.addChild(classes_node)

    def _load_methods(self, cursor, cb_id, bcl_class_id, parent_node):
        cursor.execute(
            "SELECT * FROM bcl_methods WHERE codebase_id = %s AND bcl_class_id = %s ORDER BY method_name",
            (cb_id, bcl_class_id)
        )
        methods = cursor.fetchall()
        methods_node = QTreeWidgetItem(["Methods (" + str(len(methods)) + ")", "group", ""])
        for m in methods:
            type_color = {
                "IO": "#cc0000",
                "CORE": "#006600",
                "LINK": "#0000cc",
                "INIT": "#888800",
                "CLEANUP": "#884400",
            }.get(m.get("method_type", ""), "#000000")
            label = m["method_name"] + " [" + str(m.get("method_type", "?")) + "]"
            m_node = QTreeWidgetItem([label, "method", str(m["id"])])
            m_node.setForeground(0, QColor(type_color))
            m_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "method", "id": m["id"], "data": m})
            self._load_edges(cursor, cb_id, m["id"], m_node)
            methods_node.addChild(m_node)
        parent_node.addChild(methods_node)

    def _load_edges(self, cursor, cb_id, bcl_method_id, parent_node):
        cursor.execute(
            "SELECT * FROM bcl_edges WHERE codebase_id = %s AND bcl_method_id = %s "
            "ORDER BY edge_type, certainty LIMIT 50",
            (cb_id, bcl_method_id)
        )
        edges = cursor.fetchall()
        if not edges:
            return
        edges_node = QTreeWidgetItem(["Edges (" + str(len(edges)) + ")", "group", ""])
        for e in edges:
            cert_color = {
                "CERTAIN": "#006600",
                "PROBABLE": "#cc8800",
                "UNKNOWN": "#cc0000",
            }.get(e.get("certainty", ""), "#000000")
            label = e["edge_type"] + " -> " + str(e.get("target", "?"))[:40]
            if e.get("target_method_row_id"):
                label += " [resolved]"
            e_node = QTreeWidgetItem([label, "edge", str(e["id"])])
            e_node.setForeground(0, QColor(cert_color))
            e_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "edge", "id": e["id"], "data": e})
            edges_node.addChild(e_node)
        parent_node.addChild(edges_node)

    def _load_units(self, cursor, cb_id, parent_node):
        cursor.execute(
            "SELECT * FROM bcl_units WHERE codebase_id = %s ORDER BY unit_id",
            (cb_id,)
        )
        units = cursor.fetchall()
        units_node = QTreeWidgetItem(["Units (" + str(len(units)) + ")", "group", ""])
        for u in units:
            closed_str = " [CLOSED]" if u.get("is_closed") else " [OPEN]"
            label = u["unit_id"] + closed_str + " (" + str(u.get("method_count", 0)) + " methods)"
            u_node = QTreeWidgetItem([label, "unit", str(u["id"])])
            u_color = QColor("#006600") if u.get("is_closed") else QColor("#cc0000")
            u_node.setForeground(0, u_color)
            u_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "unit", "id": u["id"], "data": u})
            self._load_unit_methods(cursor, cb_id, u["unit_id"], u_node)
            units_node.addChild(u_node)
        parent_node.addChild(units_node)

    def _load_unit_methods(self, cursor, cb_id, unit_id, parent_node):
        cursor.execute(
            "SELECT um.bcl_method_id, um.method_id, m.method_name, m.method_type "
            "FROM bcl_unit_methods um "
            "LEFT JOIN bcl_methods m ON um.bcl_method_id = m.id "
            "WHERE um.codebase_id = %s AND um.unit_id = %s",
            (cb_id, unit_id)
        )
        um_rows = cursor.fetchall()
        if not um_rows:
            return
        um_node = QTreeWidgetItem(["Unit Methods (" + str(len(um_rows)) + ")", "group", ""])
        for um in um_rows:
            label = str(um.get("method_name", "?")) + " [" + str(um.get("method_type", "?")) + "]"
            um_item = QTreeWidgetItem([label, "unit_method", str(um.get("bcl_method_id", ""))])
            um_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "unit_method", "id": um.get("bcl_method_id"), "data": um})
            um_node.addChild(um_item)
        parent_node.addChild(um_node)

    def _on_tree_click(self, item, column):
        info = item.data(0, Qt.ItemDataRole.UserRole)
        if not info:
            return
        node_type = info["type"]
        data = info["data"]
        if node_type == "codebase":
            self._show_codebase(data)
        elif node_type == "class":
            self._show_class(data)
        elif node_type == "method":
            self._show_method(data)
        elif node_type == "edge":
            self._show_edge(data)
        elif node_type == "unit":
            self._show_unit(data)
        elif node_type == "unit_method":
            self._show_unit_method(data)

    def _fmt_row(self, row):
        lines = []
        for key, val in row.items():
            if val is None:
                val_str = "NULL"
            elif isinstance(val, (dict, list)):
                val_str = json.dumps(val, indent=2)
            elif isinstance(val, str) and len(val) > 200:
                val_str = val[:200] + "..."
            else:
                val_str = str(val)
            lines.append("  " + str(key) + ": " + val_str)
        return "\n".join(lines)

    def _show_codebase(self, data):
        html = "<h2>Codebase: " + str(data.get("name", "")) + "</h2>"
        html += "<pre>" + self._fmt_row(data) + "</pre>"
        self.detail.setHtml(html)

    def _show_class(self, data):
        html = "<h2>Class: " + str(data.get("class_name", "")) + "</h2>"
        html += "<pre>" + self._fmt_row(data) + "</pre>"
        source_id = data.get("source_class_id")
        if source_id and self.conn:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT class_name, domain, role, description, class_code "
                "FROM " + self.db_name + ".vb_classes WHERE id = %s",
                (source_id,)
            )
            src = cursor.fetchone()
            cursor.close()
            if src:
                html += "<h3>Source (vb_classes.id=" + str(source_id) + ")</h3>"
                html += "<pre>" + self._fmt_row(src) + "</pre>"
        self.detail.setHtml(html)

    def _show_method(self, data):
        html = "<h2>Method: " + str(data.get("method_name", "")) + "</h2>"
        html += "<table border='1' cellpadding='4' style='border-collapse:collapse'>"
        fields = [
            ("bcl_methods.id (PK)", data.get("id")),
            ("bcl_class_id (FK)", data.get("bcl_class_id")),
            ("source_method_id (FK)", data.get("source_method_id")),
            ("method_type", data.get("method_type")),
            ("is_async", data.get("is_async")),
            ("is_deterministic_subset", data.get("is_deterministic_subset")),
            ("line_start", data.get("line_start")),
            ("line_end", data.get("line_end")),
            ("ast_hash", data.get("ast_hash")),
            ("certain_count", data.get("certain_count")),
            ("probable_count", data.get("probable_count")),
            ("unknown_count", data.get("unknown_count")),
            ("has_branching", data.get("has_branching")),
            ("has_loops", data.get("has_loops")),
            ("has_recursion", data.get("has_recursion")),
            ("throws_exceptions", data.get("throws_exceptions")),
            ("handles_exceptions", data.get("handles_exceptions")),
            ("mutates_global_state", data.get("mutates_global_state")),
            ("mutates_external", data.get("mutates_external")),
        ]
        for label, val in fields:
            html += "<tr><td><b>" + label + "</b></td><td>" + str(val) + "</td></tr>"
        html += "</table>"
        html += "<h3>Inputs</h3><pre>" + str(data.get("inputs", "")) + "</pre>"
        html += "<h3>Outputs</h3><pre>" + str(data.get("outputs", "")) + "</pre>"
        source_id = data.get("source_method_id")
        if source_id and self.conn:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT method_name, params, method_code, line_start, is_dunder "
                "FROM " + self.db_name + ".vb_methods WHERE id = %s",
                (source_id,)
            )
            src = cursor.fetchone()
            cursor.close()
            if src:
                html += "<h3>Source Code (vb_methods.id=" + str(source_id) + ")</h3>"
                html += "<pre style='background:#f0f0f0;padding:8px'>" + str(src.get("method_code", "")) + "</pre>"
        self.detail.setHtml(html)

    def _show_edge(self, data):
        html = "<h2>Edge #" + str(data.get("id", "")) + "</h2>"
        html += "<table border='1' cellpadding='4' style='border-collapse:collapse'>"
        fields = [
            ("bcl_edges.id (PK)", data.get("id")),
            ("bcl_method_id (FK->bcl_methods)", data.get("bcl_method_id")),
            ("source_method_id (string)", data.get("source_method_id")),
            ("source_method_row_id (FK->vb_methods)", data.get("source_method_row_id")),
            ("target (string)", data.get("target")),
            ("target_method_row_id (FK->bcl_methods)", data.get("target_method_row_id")),
            ("edge_type", data.get("edge_type")),
            ("certainty", data.get("certainty")),
            ("resolution", data.get("resolution")),
            ("resource_type", data.get("resource_type")),
            ("line_number", data.get("line_number")),
        ]
        for label, val in fields:
            html += "<tr><td><b>" + label + "</b></td><td>" + str(val) + "</td></tr>"
        html += "</table>"
        bcl_method_id = data.get("bcl_method_id")
        if bcl_method_id and self.conn:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT method_name, method_type, class_name, source_method_id "
                "FROM bcl_methods WHERE id = %s",
                (bcl_method_id,)
            )
            src_method = cursor.fetchone()
            if src_method:
                html += "<h3>Source Method (bcl_methods.id=" + str(bcl_method_id) + ")</h3>"
                html += "<pre>" + self._fmt_row(src_method) + "</pre>"
                source_id = src_method.get("source_method_id")
                if source_id:
                    cursor.execute(
                        "SELECT method_code FROM " + self.db_name + ".vb_methods WHERE id = %s",
                        (source_id,)
                    )
                    src_code = cursor.fetchone()
                    if src_code:
                        html += "<h3>Source Code</h3>"
                        html += "<pre style='background:#f0f0f0;padding:8px'>" + str(src_code.get("method_code", "")) + "</pre>"
            target_row_id = data.get("target_method_row_id")
            if target_row_id:
                cursor.execute(
                    "SELECT method_name, method_type, class_name "
                    "FROM bcl_methods WHERE id = %s",
                    (target_row_id,)
                )
                tgt_method = cursor.fetchone()
                if tgt_method:
                    html += "<h3>Target Method (bcl_methods.id=" + str(target_row_id) + ")</h3>"
                    html += "<pre>" + self._fmt_row(tgt_method) + "</pre>"
            cursor.close()
        self.detail.setHtml(html)

    def _show_unit(self, data):
        html = "<h2>Unit: " + str(data.get("unit_id", "")) + "</h2>"
        html += "<table border='1' cellpadding='4' style='border-collapse:collapse'>"
        fields = [
            ("id (PK)", data.get("id")),
            ("unit_id", data.get("unit_id")),
            ("method_count", data.get("method_count")),
            ("is_closed", data.get("is_closed")),
            ("internal_calls", data.get("internal_calls")),
            ("external_call_count", data.get("external_call_count")),
            ("class_names", data.get("class_names")),
            ("file_names", data.get("file_names")),
            ("resources", data.get("resources")),
            ("state_keys", data.get("state_keys")),
            ("method_types_json", data.get("method_types_json")),
        ]
        for label, val in fields:
            html += "<tr><td><b>" + label + "</b></td><td>" + str(val) + "</td></tr>"
        html += "</table>"
        self.detail.setHtml(html)

    def _show_unit_method(self, data):
        html = "<h2>Unit Method</h2>"
        html += "<pre>" + self._fmt_row(data) + "</pre>"
        self.detail.setHtml(html)

    def closeEvent(self, event):
        if self.conn:
            self.conn.close()
        super().closeEvent(event)


def main():
    parser = argparse.ArgumentParser(description="BCL IR Database Viewer")
    parser.add_argument("--db", default=DB_NAME, help="BCL IR database name")
    parser.add_argument("--codebase", default=None, help="Filter to specific codebase name")
    args = parser.parse_args()
    app = QApplication(sys.argv)
    viewer = BclViewer(db_name=args.db, codebase_filter=args.codebase)
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
