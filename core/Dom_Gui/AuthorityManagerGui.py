#!/usr/bin/env python3
# [@GHOST]{file_path="core/Dom_Gui/AuthorityManagerGui.py" date="2026-07-04" author="Devin" context="PyQt6 GUI for authority table management"}
# [@VBSTYLE]{auth="system" role="authority_gui" return="Tuple3" orch="none" no="decorators|print|hardcoded|tabs|self_underscore"}
# [@FILEID]{id="AuthorityManagerGui.py" domain="gui" authority="authority_gui"}
# [@SUMMARY]{PyQt6 GUI for browsing, adding, editing, deleting authority table entries. Uses AuthorityManager class.}

"""
AuthorityManagerGui — PyQt6 GUI for managing authority tables.

Left panel: list of authority tables with entry counts.
Right panel: data table showing entries (id, name, description, active).
Bottom panel: add/edit/delete buttons + search field.

Run: python3 AuthorityManagerGui.py
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QMessageBox, QCheckBox, QGroupBox, QGridLayout,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

sys.path.insert(0, "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Db")
from AuthorityManager import AuthorityManager, AUTHORITY_TABLES


class AuthorityManagerGui(QMainWindow):
    """Main window for authority table management."""

    def __init__(self):
        super().__init__()
        self.state = {
            "manager": AuthorityManager(),
            "current_table": None,
            "entries": [],
            "selected_id": None,
        }
        self._p = self.PHelper
        self.setWindowTitle("Authority Manager — laws database")
        self.setMinimumSize(1000, 600)
        self.InitUi()
        self.ConnectDb()
        self.LoadTables()

    def PHelper(self, key, default=None):
        return self.state.get(key, default)

    def read_state(self):
        return dict(self.state)

    def set_config(self, config):
        if isinstance(config, dict):
            self.state.update(config)

    def InitUi(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left_panel = self.BuildLeftPanel()
        splitter.addWidget(left_panel)

        right_panel = self.BuildRightPanel()
        splitter.addWidget(right_panel)

        splitter.setSizes([250, 750])

        bottom_bar = self.BuildBottomBar()
        layout.addWidget(bottom_bar)

    def BuildLeftPanel(self):
        group = QGroupBox("Authority Tables")
        layout = QVBoxLayout(group)

        self.table_list = QTableWidget(0, 2)
        self.table_list.setHorizontalHeaderLabels(["Table", "Count"])
        self.table_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_list.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_list.itemSelectionChanged.connect(self.OnTableSelected)
        layout.addWidget(self.table_list)

        refresh_btn = QPushButton("Refresh Counts")
        refresh_btn.clicked.connect(self.LoadTables)
        layout.addWidget(refresh_btn)

        return group

    def BuildRightPanel(self):
        group = QGroupBox("Entries")
        layout = QVBoxLayout(group)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_field = QLineEdit()
        self.search_field.textChanged.connect(self.OnSearchChanged)
        search_layout.addWidget(self.search_field)
        layout.addLayout(search_layout)

        self.data_table = QTableWidget(0, 4)
        self.data_table.setHorizontalHeaderLabels(["ID", "Name", "Description", "Active"])
        self.data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.data_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.data_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.data_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.data_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.data_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.data_table.itemSelectionChanged.connect(self.OnEntrySelected)
        self.data_table.doubleClicked.connect(self.OnEditClicked)
        layout.addWidget(self.data_table)

        edit_group = QGroupBox("Edit Entry")
        edit_layout = QGridLayout(edit_group)

        edit_layout.addWidget(QLabel("Name:"), 0, 0)
        self.name_field = QLineEdit()
        edit_layout.addWidget(self.name_field, 0, 1)

        edit_layout.addWidget(QLabel("Description:"), 1, 0)
        self.desc_field = QLineEdit()
        edit_layout.addWidget(self.desc_field, 1, 1)

        self.active_check = QCheckBox("Active")
        edit_layout.addWidget(self.active_check, 2, 0, 1, 2)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add New")
        self.add_btn.clicked.connect(self.OnAddClicked)
        btn_layout.addWidget(self.add_btn)

        self.update_btn = QPushButton("Update Selected")
        self.update_btn.clicked.connect(self.OnUpdateClicked)
        btn_layout.addWidget(self.update_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.OnDeleteClicked)
        btn_layout.addWidget(self.delete_btn)

        self.clear_btn = QPushButton("Clear Fields")
        self.clear_btn.clicked.connect(self.ClearFields)
        btn_layout.addWidget(self.clear_btn)

        edit_layout.addLayout(btn_layout, 3, 0, 1, 2)
        layout.addWidget(edit_group)

        return group

    def BuildBottomBar(self):
        bar = QWidget()
        layout = QHBoxLayout(bar)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.ref_label = QLabel("")
        self.ref_label.setStyleSheet("color: orange;")
        layout.addWidget(self.ref_label)

        return bar

    def ConnectDb(self):
        ok, _, err = self.state["manager"].Run("connect")
        if not ok:
            QMessageBox.critical(self, "Connection Error", f"Cannot connect to MySQL:\n{err[1]}")
            sys.exit(1)
        self.SetStatus("Connected to laws database")

    def SetStatus(self, msg):
        self.status_label.setText(msg)

    def SetRefWarning(self, msg):
        self.ref_label.setText(msg)

    def LoadTables(self):
        ok, stats, err = self.state["manager"].Run("get_stats")
        if not ok:
            self.SetStatus(f"Error: {err[1]}")
            return
        self.table_list.setRowCount(0)
        for table in AUTHORITY_TABLES:
            row = self.table_list.rowCount()
            self.table_list.insertRow(row)
            self.table_list.setItem(row, 0, QTableWidgetItem(table))
            count = stats.get(table, 0)
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_list.setItem(row, 1, count_item)
        total = stats.get("total", 0)
        self.SetStatus(f"Loaded {len(AUTHORITY_TABLES)} tables, {total} total entries")

    def OnTableSelected(self):
        items = self.table_list.selectedItems()
        if not items:
            return
        table_name = items[0].text()
        self.state["current_table"] = table_name
        self.LoadEntries()

    def LoadEntries(self, search_query=None):
        table = self.state["current_table"]
        if not table:
            return
        if search_query:
            ok, rows, err = self.state["manager"].Run("search_entries", {"table": table, "query": search_query})
        else:
            ok, rows, err = self.state["manager"].Run("list_entries", {"table": table})
        if not ok:
            self.SetStatus(f"Error loading {table}: {err[1]}")
            return
        self.state["entries"] = rows
        self.data_table.setRowCount(0)
        for row_data in rows:
            row = self.data_table.rowCount()
            self.data_table.insertRow(row)
            rid = QTableWidgetItem(str(row_data.get("id", "")))
            rid.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.data_table.setItem(row, 0, rid)
            self.data_table.setItem(row, 1, QTableWidgetItem(str(row_data.get("name", ""))))
            self.data_table.setItem(row, 2, QTableWidgetItem(str(row_data.get("description", "") or "")))
            active = "Yes" if row_data.get("is_active", 1) else "No"
            act_item = QTableWidgetItem(active)
            act_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.data_table.setItem(row, 3, act_item)
        self.SetStatus(f"Loaded {len(rows)} entries from {table}")
        self.SetRefWarning("")

    def OnSearchChanged(self):
        text = self.search_field.text().strip()
        self.LoadEntries(text if text else None)

    def OnEditClicked(self):
        self.OnEntrySelected()
        self.name_field.setFocus()
        self.name_field.selectAll()

    def OnEntrySelected(self):
        items = self.data_table.selectedItems()
        if not items:
            return
        row = items[0].row()
        entry_id = int(self.data_table.item(row, 0).text())
        name = self.data_table.item(row, 1).text()
        desc = self.data_table.item(row, 2).text()
        active = self.data_table.item(row, 3).text() == "Yes"
        self.state["selected_id"] = entry_id
        self.name_field.setText(name)
        self.desc_field.setText(desc)
        self.active_check.setChecked(active)
        ok, refs, err = self.state["manager"].Run("check_references", {
            "table": self.state["current_table"],
            "id": entry_id,
        })
        if ok and refs:
            total = sum(refs.values())
            ref_str = ", ".join(f"{t}:{c}" for t, c in refs.items())
            self.SetRefWarning(f"Referenced by {total} rows: {ref_str}")
        else:
            self.SetRefWarning("")

    def OnAddClicked(self):
        table = self.state["current_table"]
        if not table:
            QMessageBox.warning(self, "No Table", "Select a table first.")
            return
        name = self.name_field.text().strip()
        desc = self.desc_field.text().strip()
        if not name:
            QMessageBox.warning(self, "Empty Name", "Name is required.")
            return
        ok, data, err = self.state["manager"].Run("add_entry", {
            "table": table, "name": name, "description": desc,
        })
        if not ok:
            QMessageBox.warning(self, "Add Failed", err[1])
            return
        self.SetStatus(f"Added '{name}' to {table} (id={data['id']})")
        self.ClearFields()
        self.LoadEntries()
        self.LoadTables()

    def OnUpdateClicked(self):
        table = self.state["current_table"]
        entry_id = self.state["selected_id"]
        if not table or entry_id is None:
            QMessageBox.warning(self, "No Selection", "Select an entry to update.")
            return
        name = self.name_field.text().strip()
        desc = self.desc_field.text().strip()
        active = self.active_check.isChecked()
        ok, data, err = self.state["manager"].Run("update_entry", {
            "table": table, "id": entry_id,
            "name": name, "description": desc, "is_active": active,
        })
        if not ok:
            QMessageBox.warning(self, "Update Failed", err[1])
            return
        self.SetStatus(f"Updated id={entry_id} in {table}")
        self.LoadEntries()

    def OnDeleteClicked(self):
        table = self.state["current_table"]
        entry_id = self.state["selected_id"]
        if not table or entry_id is None:
            QMessageBox.warning(self, "No Selection", "Select an entry to delete.")
            return
        ok, refs, err = self.state["manager"].Run("check_references", {
            "table": table, "id": entry_id,
        })
        total_refs = sum(refs.values()) if refs else 0
        ref_msg = f"\n\nThis entry has {total_refs} references in other tables." if total_refs else ""
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete entry id={entry_id} from {table}?{ref_msg}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        force = total_refs > 0
        ok, data, err = self.state["manager"].Run("delete_entry", {
            "table": table, "id": entry_id, "force": force,
        })
        if not ok:
            QMessageBox.warning(self, "Delete Failed", err[1])
            return
        nulled = data.get("refs_nulled", 0)
        self.SetStatus(f"Deleted id={entry_id} from {table} ({nulled} refs nulled)")
        self.ClearFields()
        self.LoadEntries()
        self.LoadTables()

    def ClearFields(self):
        self.name_field.clear()
        self.desc_field.clear()
        self.active_check.setChecked(True)
        self.state["selected_id"] = None
        self.SetRefWarning("")

    def closeEvent(self, event):
        self.state["manager"].Run("disconnect")
        event.accept()


def Main():
    app = QApplication(sys.argv)
    font = QFont("Menlo", 13)
    app.setFont(font)
    window = AuthorityManagerGui()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(Main())
