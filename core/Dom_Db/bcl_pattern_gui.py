#!/usr/bin/env python3
#[@GHOST]{[@file<bcl_pattern_gui.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<bcl_pattern_gui>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
#[@SUMMARY]{PyQt6 GUI for BCL pattern detection, canonical selection, and repair preview}

import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QPlainTextEdit,
    QPushButton, QTabWidget, QStatusBar, QLabel, QHeaderView,
)
from PyQt6.QtCore import Qt

WINDOW_TITLE = "BCL Pattern Studio"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 750
COL_PATTERN = 0
COL_COUNT = 1
COL_FILES = 2

class BclPatternGui:
    """PyQt6 GUI for BCL pattern detection, canonical selection, and repair preview.

    Accepts a BclPatternCollector instance via param for repair callbacks.
    All access via Run() dispatch. The GUI runs in a blocking Qt event loop.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "results": {},
            "memunit": mem,
            "db_manager": db,
            "collector": None,
            "patterns": {},
            "canonical": "",
            "diffs": {},
            "app": None,
            "window": None,
        }
        if param:
            for key, value in param.items():
                if key == "collector":
                    self.state["collector"] = value
                else:
                    self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "show":
            return self.Show(params)
        elif command == "show_diffs":
            return self.ShowDiffs(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        elif command == "close":
            return self.Close()
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            if key == "collector":
                self.state["collector"] = value
            else:
                self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Close(self):
        """Close any open resources. Returns Tuple3."""
        return (1, {"closed": True}, None)

    def Show(self, params):
        """Launch the PyQt6 GUI with detected patterns."""
        patterns = self._p(params, "patterns", {})
        canonical = self._p(params, "canonical", "")
        if not patterns:
            return (0, None, ("NO_PATTERNS", "patterns param is required", 0))

        self.state["patterns"] = patterns
        self.state["canonical"] = canonical

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        self.state["app"] = app

        window = BclPatternWindow(self)
        window.LoadPatterns(patterns, canonical)
        window.show()
        app.exec()

        return (1, {
            "canonical": self.state["canonical"],
            "patterns": self.state["patterns"],
        }, None)

    def ShowDiffs(self, params):
        """Show repair diffs in the Repair Preview tab."""
        diffs = self._p(params, "diffs", {})
        if not diffs:
            return (0, None, ("NO_DIFFS", "diffs param is required", 0))

        self.state["diffs"] = diffs
        window = self.state["window"]
        if window is not None:
            window.LoadDiffs(diffs)
            return (1, {"diffs_loaded": True, "count": len(diffs)}, None)
        return (0, None, ("NO_WINDOW", "GUI window not active, call show first", 0))


class BclPatternWindow(QMainWindow):
    """Main PyQt6 window for BCL Pattern Studio."""

    def __init__(self, gui):
        super().__init__()
        self.gui = gui
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.tree_items = {}
        self.canonical = ""
        self.BuildUi()

    def BuildUi(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_label = QLabel("Detected Patterns")
        left_layout.addWidget(left_label)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Pattern", "Count", "Files"])
        header = self.tree.header()
        header.setSectionResizeMode(COL_PATTERN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_COUNT, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_FILES, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemSelectionChanged.connect(self.OnTreeSelect)
        left_layout.addWidget(self.tree)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_label = QLabel("Examples")
        right_layout.addWidget(right_label)

        self.examples_edit = QPlainTextEdit()
        self.examples_edit.setReadOnly(True)
        right_layout.addWidget(self.examples_edit)
        splitter.addWidget(right_panel)

        splitter.setSizes([500, 700])

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        detect_tab = QWidget()
        detect_layout = QVBoxLayout(detect_tab)
        detect_layout.addWidget(splitter)
        self.tabs.addTab(detect_tab, "Detect")

        self.diff_edit = QPlainTextEdit()
        self.diff_edit.setReadOnly(True)
        self.tabs.addTab(self.diff_edit, "Repair Preview")

        self.report_edit = QPlainTextEdit()
        self.report_edit.setReadOnly(True)
        self.tabs.addTab(self.report_edit, "Report")

        btn_row = QHBoxLayout()
        self.btn_canonical = QPushButton("Set Canonical")
        self.btn_canonical.clicked.connect(self.OnSetCanonical)
        btn_row.addWidget(self.btn_canonical)

        self.btn_repair = QPushButton("Repair All")
        self.btn_repair.clicked.connect(self.OnRepairAll)
        btn_row.addWidget(self.btn_repair)

        self.btn_dryrun = QPushButton("Dry Run")
        self.btn_dryrun.clicked.connect(self.OnDryRun)
        btn_row.addWidget(self.btn_dryrun)

        layout.addLayout(btn_row)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    def LoadPatterns(self, patterns, canonical):
        self.tree.clear()
        self.tree_items = {}
        self.canonical = canonical
        sorted_names = sorted(patterns.keys())
        for name in sorted_names:
            examples = patterns[name]
            count = len(examples) if isinstance(examples, list) else 0
            files = set()
            if isinstance(examples, list):
                for ex in examples:
                    if isinstance(ex, dict) and "file" in ex:
                        files.add(ex["file"])
            item = QTreeWidgetItem([name, str(count), str(len(files))])
            if name == canonical:
                font = item.font(COL_PATTERN)
                font.setBold(True)
                item.setFont(COL_PATTERN, font)
            self.tree.addTopLevelItem(item)
            self.tree_items[name] = item
            if isinstance(examples, list):
                for ex in examples:
                    if not isinstance(ex, dict):
                        continue
                    line_num = ex.get("line", "")
                    file_path = ex.get("file", "")
                    text = ex.get("text", "")[:80]
                    child = QTreeWidgetItem([
                        "L" + str(line_num) + " " + file_path, "", ""
                    ])
                    child.setData(COL_PATTERN, Qt.ItemDataRole.UserRole, text)
                    item.addChild(child)
        self.status.showMessage(str(len(sorted_names)) + " patterns loaded")

    def LoadDiffs(self, diffs):
        self.diff_edit.clear()
        for name, diff_text in diffs.items():
            self.diff_edit.appendPlainText("=== " + name + " ===")
            self.diff_edit.appendPlainText(str(diff_text))
            self.diff_edit.appendPlainText("")
        self.tabs.setCurrentIndex(1)
        self.status.showMessage(str(len(diffs)) + " diffs loaded")

    def OnTreeSelect(self):
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        parent = item.parent()
        if parent is not None:
            pattern_name = parent.text(COL_PATTERN)
            text = item.data(COL_PATTERN, Qt.ItemDataRole.UserRole)
            self.examples_edit.clear()
            self.examples_edit.appendPlainText("Pattern: " + pattern_name)
            self.examples_edit.appendPlainText("Example: " + str(text))
        else:
            pattern_name = item.text(COL_PATTERN)
            patterns = self.gui.state["patterns"]
            examples = patterns.get(pattern_name, [])
            self.examples_edit.clear()
            self.examples_edit.appendPlainText("Pattern: " + pattern_name)
            self.examples_edit.appendPlainText("Examples: " + str(len(examples)))
            self.examples_edit.appendPlainText("")
            if isinstance(examples, list):
                for ex in examples:
                    if not isinstance(ex, dict):
                        continue
                    line_num = ex.get("line", "")
                    file_path = ex.get("file", "")
                    text = ex.get("text", "")
                    self.examples_edit.appendPlainText(
                        "--- L" + str(line_num) + " in " + file_path + " ---"
                    )
                    self.examples_edit.appendPlainText(str(text))
                    self.examples_edit.appendPlainText("")
        self.status.showMessage("Selected: " + item.text(COL_PATTERN))

    def OnSetCanonical(self):
        items = self.tree.selectedItems()
        if not items:
            self.status.showMessage("Select a pattern first")
            return
        item = items[0]
        parent = item.parent()
        if parent is not None:
            item = parent
        pattern_name = item.text(COL_PATTERN)
        self.canonical = pattern_name
        self.gui.state["canonical"] = pattern_name
        for name, tree_item in self.tree_items.items():
            font = tree_item.font(COL_PATTERN)
            font.setBold(name == pattern_name)
            tree_item.setFont(COL_PATTERN, font)
        self.status.showMessage("Canonical set to: " + pattern_name)
        self.BuildReport()

    def OnRepairAll(self):
        collector = self.gui.state["collector"]
        if collector is None:
            self.status.showMessage("No collector instance available")
            return
        if not self.canonical:
            self.status.showMessage("Set canonical pattern first")
            return
        ok, data, err = collector.Run("repair", {"dry_run": False})
        if not ok:
            self.status.showMessage("Repair failed: " + str(err))
            return
        self.status.showMessage("Repair complete: " + str(data))
        self.BuildReport()

    def OnDryRun(self):
        collector = self.gui.state["collector"]
        if collector is None:
            self.status.showMessage("No collector instance available")
            return
        if not self.canonical:
            self.status.showMessage("Set canonical pattern first")
            return
        ok, data, err = collector.Run("repair", {"dry_run": True})
        if not ok:
            self.status.showMessage("Dry run failed: " + str(err))
            return
        diffs = {}
        if isinstance(data, dict):
            diffs = data.get("diffs", data)
        self.LoadDiffs(diffs)
        self.status.showMessage("Dry run complete")

    def BuildReport(self):
        patterns = self.gui.state["patterns"]
        self.report_edit.clear()
        self.report_edit.appendPlainText("BCL Pattern Report")
        self.report_edit.appendPlainText("=" * 40)
        self.report_edit.appendPlainText("Canonical: " + str(self.canonical))
        self.report_edit.appendPlainText("")
        for name in sorted(patterns.keys()):
            examples = patterns[name]
            count = len(examples) if isinstance(examples, list) else 0
            files = set()
            if isinstance(examples, list):
                for ex in examples:
                    if isinstance(ex, dict) and "file" in ex:
                        files.add(ex["file"])
            marker = " [CANONICAL]" if name == self.canonical else ""
            self.report_edit.appendPlainText(
                name + marker + " — " + str(count) + " examples, " + str(len(files)) + " files"
            )
