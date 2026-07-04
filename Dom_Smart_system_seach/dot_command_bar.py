"""
Dot-Notation Command Bar — Floating Toolbar
Introspects running PyQt6 windows, auto-suggests widget paths and properties.
Type .win to see running windows, .win.table to see widgets, .win.table.header.sort to see properties.

Run: python3 dot_command_bar.py
Launch alongside any other PyQt6 GUI (like rule_truth_gui.py or fact_store_mock.py).
"""

import sys
import re
import inspect
from collections import defaultdict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QCompleter, QListWidget, QListWidgetItem,
    QTabWidget, QTextEdit, QPushButton, QComboBox, QSplitter,
    QGroupBox, QToolBar, QStatusBar, QMenu, QCheckBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QSlider, QMenuBar, QListView, QTreeView, QDoubleSpinBox,
    QPlainTextEdit, QDialog
)
from PyQt6.QtCore import Qt, QTimer, QStringListModel, QSize
from PyQt6.QtGui import QColor, QFont, QAction, QKeySequence, QShortcut


PYQT_CLASSES = [
    QWidget, QMainWindow, QPushButton, QLabel, QLineEdit, QTableWidget,
    QComboBox, QTabWidget, QProgressBar, QTextEdit, QSpinBox, QCheckBox,
    QSlider, QToolBar, QStatusBar, QMenuBar, QListView, QTreeView,
    QDoubleSpinBox, QPlainTextEdit, QGroupBox, QDialog, QListWidget,
    QSplitter, QMenu, QAction, QShortcut,
]

SKIP_PREFIXES = ("_", "meta", "qt_", "static", "tr", "q")
COMMON_PROPS = [
    "title", "text", "color", "font", "size", "width", "height",
    "visible", "enabled", "hidden", "style", "stylesheet",
    "margin", "padding", "alignment", "tooltip", "minimum",
    "maximum", "resize", "move", "close", "show", "hide",
    "sort", "header", "selection", "model", "index", "count",
    "value", "maximum", "minimum", "singleStep", "readOnly",
    "placeholder", "currentText", "currentIndex", "itemText",
    "columnCount", "rowCount", "horizontalHeader", "verticalHeader",
    "setSortingEnabled", "setAlternatingRowColors", "setColumnCount",
    "setRowCount", "setHorizontalHeaderLabels", "setSelectionBehavior",
    "setContextMenuPolicy", "setSectionHidden", "setSectionResizeMode",
    "setStyleSheet", "setFont", "setWindowTitle", "resize",
    "setEnabled", "setVisible", "setHidden", "setToolTip",
    "setPlaceholderText", "setText", "setReadOnly", "setValue",
    "setMaximum", "setMinimum", "setCurrentText", "setCurrentIndex",
    "addItem", "removeItem", "clear", "addTab", "removeTab",
    "setTabText", "currentWidget", "indexOf", "widget",
    "setLayout", "addWidget", "removeWidget", "insertWidget",
    "setPlainText", "setHtml", "append", "toPlainText",
    "setCheckable", "setChecked", "isChecked", "click",
    "setRange", "setSingleStep", "setDecimals",
    "setFormat", "setAlignment", "setMaximum",
]

CATEGORY_MAP = {
    "set": "setter",
    "get": "getter",
    "is": "checker",
    "add": "action",
    "remove": "action",
    "insert": "action",
    "clear": "action",
    "show": "action",
    "hide": "action",
    "close": "action",
    "resize": "action",
    "move": "action",
    "click": "action",
    "sort": "action",
    "select": "action",
    "current": "state",
    "column": "table",
    "row": "table",
    "header": "table",
    "tab": "container",
    "item": "content",
    "text": "content",
    "font": "style",
    "color": "style",
    "style": "style",
    "size": "layout",
    "width": "layout",
    "height": "layout",
    "margin": "layout",
    "padding": "layout",
    "visible": "state",
    "enabled": "state",
    "hidden": "state",
    "value": "state",
    "count": "state",
    "title": "meta",
    "tooltip": "meta",
    "placeholder": "meta",
}


def build_property_db():
    db = {}
    for cls in PYQT_CLASSES:
        name = cls.__name__
        props = []
        seen = set()
        for m in dir(cls):
            if any(m.startswith(p) for p in SKIP_PREFIXES):
                continue
            if m in seen:
                continue
            seen.add(m)
            cat = "other"
            for prefix, category in CATEGORY_MAP.items():
                if m.lower().startswith(prefix) or m.lower().endswith(prefix):
                    cat = category
                    break
            props.append((m, cat))
        for cp in COMMON_PROPS:
            if cp not in seen and hasattr(cls, cp):
                props.append((cp, CATEGORY_MAP.get(cp.split("set")[-1].lower() if cp.startswith("set") else cp[:6].lower(), "other")))
        db[name] = sorted(set(props), key=lambda x: x[0])
    return db


def _human_name(widget):
    """Extract a human-readable name from a widget."""
    name = widget.objectName()
    if name and not name.startswith("qt_"):
        return name
    if isinstance(widget, QPushButton):
        return widget.text() or "button"
    if isinstance(widget, QLabel):
        txt = widget.text()
        return txt.lower().replace(" ", "_").replace(":", "").replace("-", "_") if txt else "label"
    if isinstance(widget, QLineEdit):
        ph = widget.placeholderText()
        if ph:
            return ph.lower().replace(" ", "_").replace(".", "").replace(".", "")
        return "text_input"
    if isinstance(widget, QComboBox):
        return "dropdown"
    if isinstance(widget, QTableWidget):
        return "table"
    if isinstance(widget, QTabWidget):
        return "tabs"
    if isinstance(widget, QTextEdit):
        return "text_area"
    if isinstance(widget, QPlainTextEdit):
        return "text_area"
    if isinstance(widget, QProgressBar):
        return "progress_bar"
    if isinstance(widget, QCheckBox):
        return widget.text().lower().replace(" ", "_") if widget.text() else "checkbox"
    if isinstance(widget, QSpinBox):
        return "number_input"
    if isinstance(widget, QDoubleSpinBox):
        return "number_input"
    if isinstance(widget, QSlider):
        return "slider"
    if isinstance(widget, QGroupBox):
        return widget.title().lower().replace(" ", "_") if widget.title() else "group"
    if isinstance(widget, QListWidget):
        return "list"
    if isinstance(widget, QToolBar):
        return "toolbar"
    if isinstance(widget, QStatusBar):
        return "status_bar"
    if isinstance(widget, QMenuBar):
        return "menu_bar"
    if isinstance(widget, QMenu):
        return widget.title().lower().replace(" ", "_") if widget.title() else "menu"
    if isinstance(widget, QSplitter):
        return "splitter"
    if isinstance(widget, QDialog):
        return widget.windowTitle().lower().replace(" ", "_") if widget.windowTitle() else "dialog"
    cls_name = widget.__class__.__name__
    if cls_name.startswith("Q"):
        cls_name = cls_name[1:]
    return cls_name.lower()


def _human_type(widget):
    """Return a human-readable type description."""
    if isinstance(widget, QPushButton):
        return "Button"
    if isinstance(widget, QLabel):
        return "Label"
    if isinstance(widget, QLineEdit):
        return "Text Input"
    if isinstance(widget, QComboBox):
        return "Dropdown"
    if isinstance(widget, QTableWidget):
        return "Table"
    if isinstance(widget, QTabWidget):
        return "Tabs"
    if isinstance(widget, QTextEdit):
        return "Text Area"
    if isinstance(widget, QPlainTextEdit):
        return "Text Area"
    if isinstance(widget, QProgressBar):
        return "Progress Bar"
    if isinstance(widget, QCheckBox):
        return "Checkbox"
    if isinstance(widget, QSpinBox):
        return "Number Input"
    if isinstance(widget, QDoubleSpinBox):
        return "Number Input"
    if isinstance(widget, QSlider):
        return "Slider"
    if isinstance(widget, QGroupBox):
        return "Group"
    if isinstance(widget, QListWidget):
        return "List"
    if isinstance(widget, QToolBar):
        return "Toolbar"
    if isinstance(widget, QStatusBar):
        return "Status Bar"
    if isinstance(widget, QMainWindow):
        return "Window"
    if isinstance(widget, QDialog):
        return "Dialog"
    if isinstance(widget, QMenu):
        return "Menu"
    if isinstance(widget, QWidget):
        return "Panel"
    return widget.__class__.__name__


HUMAN_PROPS = {
    "setWindowTitle": "title",
    "windowTitle": "title",
    "setText": "text",
    "text": "text",
    "setPlaceholderText": "placeholder",
    "placeholderText": "placeholder",
    "setFont": "font",
    "font": "font",
    "setStyleSheet": "style",
    "styleSheet": "style",
    "setVisible": "visible",
    "isVisible": "visible",
    "setVisible": "show",
    "setHidden": "hide",
    "setEnabled": "enabled",
    "isEnabled": "enabled",
    "setToolTip": "tooltip",
    "toolTip": "tooltip",
    "resize": "size",
    "setGeometry": "position",
    "geometry": "position",
    "setMinimumSize": "min_size",
    "setMaximumSize": "max_size",
    "setFixedSize": "fixed_size",
    "setAlignment": "alignment",
    "setReadOnly": "readonly",
    "isReadOnly": "readonly",
    "setValue": "value",
    "value": "value",
    "setMaximum": "max",
    "maximum": "max",
    "setMinimum": "min",
    "minimum": "min",
    "setSingleStep": "step",
    "setRange": "range",
    "setDecimals": "decimals",
    "setChecked": "checked",
    "isChecked": "checked",
    "setCheckable": "checkable",
    "click": "click",
    "close": "close",
    "show": "show",
    "hide": "hide",
    "setSortingEnabled": "sort",
    "isSortingEnabled": "sort",
    "setAlternatingRowColors": "zebra_stripes",
    "setColumnCount": "columns",
    "columnCount": "columns",
    "setRowCount": "rows",
    "rowCount": "rows",
    "setHorizontalHeaderLabels": "headers",
    "setSelectionBehavior": "selection",
    "setContextMenuPolicy": "right_click_menu",
    "setSectionHidden": "hide_column",
    "isSectionHidden": "column_hidden",
    "setSectionResizeMode": "column_resize",
    "setCurrentText": "current_text",
    "currentText": "current_text",
    "setCurrentIndex": "current_item",
    "currentIndex": "current_item",
    "addItem": "add_item",
    "removeItem": "remove_item",
    "clear": "clear",
    "addTab": "add_tab",
    "removeTab": "remove_tab",
    "setTabText": "tab_name",
    "setPlainText": "content",
    "toPlainText": "content",
    "setHtml": "content",
    "append": "add_text",
    "setFormat": "format",
    "count": "count",
    "setRowCount": "row_count",
    "setColumnCount": "col_count",
    "setMaximumHeight": "max_height",
    "setMaximumWidth": "max_width",
    "setMinimumHeight": "min_height",
    "setMinimumWidth": "min_width",
    "setContentsMargins": "margins",
    "setSpacing": "spacing",
    "move": "move",
    "setFocus": "focus",
    "update": "update",
    "repaint": "repaint",
    "activateWindow": "activate",
    "raise_": "raise",
    "setTabVisible": "tab_visible",
    "currentIndex": "current_tab",
    "setCurrentIndex": "switch_tab",
}


def _human_prop(prop):
    """Map a PyQt property name to a human-readable name."""
    if prop in HUMAN_PROPS:
        return HUMAN_PROPS[prop]
    if prop.startswith("set"):
        return prop[3:].lower()
    if prop.startswith("is"):
        return prop[2:].lower()
    return prop.lower()


def find_running_widgets():
    widgets = []
    for w in QApplication.topLevelWidgets():
        if w is None:
            continue
        if not w.isVisible():
            continue
        wname = w.windowTitle() or _human_name(w)
        wname = wname.replace(" ", "_").lower()
        widgets.append((wname, w, _human_type(w)))
        children = w.findChildren(QWidget)
        for child in children:
            cname = _human_name(child)
            if cname:
                widgets.append((f"{wname}.{cname}", child, _human_type(child)))
    return widgets


class DotCommandBar(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dot Command Bar")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.resize(600, 400)
        self.prop_db = build_property_db()
        self._build_ui()
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_windows)
        self._refresh_timer.start(2000)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title_bar = QHBoxLayout()
        title = QLabel("Dot Command Bar — type .win to start")
        title.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        title_bar.addWidget(title)
        title_bar.addStretch()
        btn_close = QPushButton("x")
        btn_close.setFixedSize(20, 20)
        btn_close.clicked.connect(self.close)
        title_bar.addWidget(btn_close)
        btn_drag = QPushButton("drag")
        btn_drag.setFixedSize(40, 20)
        btn_drag.mousePressEvent = self._start_drag
        btn_drag.mouseMoveEvent = self._do_drag
        title_bar.addWidget(btn_drag)
        layout.addLayout(title_bar)

        self.input = QLineEdit()
        self.input.setFont(QFont("Menlo", 14))
        self.input.setPlaceholderText(".win.table.header.sort...")
        self.input.textChanged.connect(self._on_input)
        layout.addWidget(self.input)

        self.suggest_list = QListWidget()
        self.suggest_list.setFont(QFont("Menlo", 11))
        self.suggest_list.setMaximumHeight(120)
        self.suggest_list.itemClicked.connect(self._on_suggestion_click)
        layout.addWidget(self.suggest_list)

        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Helvetica", 10))
        self.info_label.setStyleSheet("color: #666;")
        layout.addWidget(self.info_label)

        tabs = QTabWidget()
        tabs.setMaximumHeight(180)

        tab_props = QWidget()
        tab_props_layout = QVBoxLayout(tab_props)
        tab_props_layout.setContentsMargins(2, 2, 2, 2)
        self.props_table = QTableWidget()
        self.props_table.setColumnCount(3)
        self.props_table.setHorizontalHeaderLabels(["Property", "Category", "Class"])
        self.props_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.props_table.setAlternatingRowColors(True)
        self.props_table.setSortingEnabled(True)
        tab_props_layout.addWidget(self.props_table)
        tabs.addTab(tab_props, "Properties")

        tab_windows = QWidget()
        tab_windows_layout = QVBoxLayout(tab_windows)
        tab_windows_layout.setContentsMargins(2, 2, 2, 2)
        self.windows_list = QListWidget()
        self.windows_list.setFont(QFont("Menlo", 10))
        tab_windows_layout.addWidget(self.windows_list)
        tabs.addTab(tab_windows, "Running Windows")

        tab_chat = QWidget()
        tab_chat_layout = QVBoxLayout(tab_chat)
        tab_chat_layout.setContentsMargins(2, 2, 2, 2)
        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setFont(QFont("Menlo", 10))
        self.chat_log.setPlaceholderText("Command log...")
        tab_chat_layout.addWidget(self.chat_log)
        tabs.addTab(tab_chat, "Log")

        layout.addWidget(tabs)

        bottom = QHBoxLayout()
        self.btn_run = QPushButton("Run")
        self.btn_run.clicked.connect(self._run_command)
        bottom.addWidget(self.btn_run)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._refresh_windows)
        bottom.addWidget(self.btn_refresh)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(lambda: self.input.clear())
        bottom.addWidget(self.btn_clear)
        layout.addLayout(bottom)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._refresh_windows()
        self.input.setFocus()

        esc = QShortcut(QKeySequence("Escape"), self)
        esc.activated.connect(self.close)

    def _start_drag(self, event):
        self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def _do_drag(self, event):
        if hasattr(self, "_drag_pos"):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def _refresh_windows(self):
        self.running_widgets = find_running_widgets()
        self.windows_list.clear()
        for name, w, htype in self.running_widgets:
            item = QListWidgetItem(f".{name}  [{htype}]")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.windows_list.addItem(item)
        self.status.showMessage(f"{len(self.running_widgets)} widgets found")

    def _on_input(self, text):
        if not text:
            self.suggest_list.clear()
            self.info_label.setText("")
            return

        parts = text.lstrip(".").split(".")
        suggestions = []

        if len(parts) == 1 and not text.endswith("."):
            partial = parts[0].lower()
            for name, w, htype in self.running_widgets:
                if partial in name.lower():
                    suggestions.append((f".{name}", htype))
            if not suggestions:
                for cls in PYQT_CLASSES:
                    if partial in cls.__name__.lower():
                        suggestions.append((f".{cls.__name__}", "class"))
        elif len(parts) >= 2:
            widget_path = ".".join(parts[:-1])
            partial = parts[-1].lower() if parts[-1] else ""

            target_cls = None
            target_htype = None
            for name, w, htype in self.running_widgets:
                if name == widget_path:
                    target_cls = w.__class__
                    target_htype = htype
                    break

            if target_cls:
                cls_name = target_cls.__name__
                props = self.prop_db.get(cls_name, [])
                for prop, cat in props:
                    hp = _human_prop(prop)
                    if not partial or partial in hp or partial in prop.lower():
                        suggestions.append((f".{widget_path}.{hp}", f"{cat} ({target_htype})"))
            else:
                for cls in PYQT_CLASSES:
                    if cls.__name__ == parts[0]:
                        cls_name = cls.__name__
                        props = self.prop_db.get(cls_name, [])
                        for prop, cat in props:
                            hp = _human_prop(prop)
                            if not partial or partial in hp or partial in prop.lower():
                                suggestions.append((f".{cls_name}.{hp}", f"{cat}"))
                        break

            if not suggestions and not partial:
                for name, w, htype in self.running_widgets:
                    if name.startswith(widget_path + "."):
                        remaining = name[len(widget_path) + 1:]
                        if "." not in remaining:
                            suggestions.append((f".{name}", htype))

        self.suggest_list.clear()
        for path, info in suggestions[:50]:
            item = QListWidgetItem(f"{path}  —  {info}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            color = QColor(30, 100, 200)
            if "setter" in info:
                color = QColor(138, 43, 226)
            elif "action" in info:
                color = QColor(34, 139, 34)
            elif "style" in info:
                color = QColor(184, 134, 11)
            elif "table" in info:
                color = QColor(178, 34, 34)
            item.setForeground(color)
            self.suggest_list.addItem(item)

        self.info_label.setText(f"{len(suggestions)} suggestions")
        self._update_props_table(parts)

    def _update_props_table(self, parts):
        if not parts or not parts[0]:
            self.props_table.setRowCount(0)
            return

        target_cls = None
        target_htype = None
        for name, w, htype in self.running_widgets:
            if name == parts[0] or name == ".".join(parts[:-1]):
                target_cls = w.__class__
                target_htype = htype
                break

        if not target_cls:
            for cls in PYQT_CLASSES:
                if cls.__name__ == parts[0]:
                    target_cls = cls
                    target_htype = cls.__name__
                    break

        if not target_cls:
            self.props_table.setRowCount(0)
            return

        cls_name = target_cls.__name__
        props = self.prop_db.get(cls_name, [])
        self.props_table.setRowCount(len(props))
        for i, (prop, cat) in enumerate(props):
            hp = _human_prop(prop)
            self.props_table.setItem(i, 0, QTableWidgetItem(hp))
            self.props_table.setItem(i, 1, QTableWidgetItem(cat))
            self.props_table.setItem(i, 2, QTableWidgetItem(target_htype or cls_name))

    def _on_suggestion_click(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.input.setText(path + ".")
            self.input.setFocus()
            self.input.setCursorPosition(len(self.input.text()))

    def _run_command(self):
        text = self.input.text().strip()
        if not text:
            return

        parts = text.lstrip(".").split(".")
        self.chat_log.append(f"> {text}")

        if len(parts) < 2:
            self.chat_log.append("  Need at least .widget.property")
            return

        widget_path = parts[0]
        prop_human = ".".join(parts[1:])

        target = None
        target_htype = None
        for name, w, htype in self.running_widgets:
            if name == widget_path:
                target = w
                target_htype = htype
                break

        if not target:
            self.chat_log.append(f"  '{widget_path}' not found. Available:")
            for name, _, htype in self.running_widgets[:10]:
                self.chat_log.append(f"    .{name}  [{htype}]")
            return

        reverse_map = {v: k for k, v in HUMAN_PROPS.items()}
        prop = reverse_map.get(prop_human, prop_human)

        if hasattr(target, prop):
            try:
                val = getattr(target, prop)
                if callable(val):
                    self.chat_log.append(f"  {prop_human}() is a method on {target_htype}")
                else:
                    self.chat_log.append(f"  {prop_human} = {val}")
            except Exception as e:
                self.chat_log.append(f"  Error: {e}")
        else:
            matches = [m for m in dir(target) if prop_human.lower() in m.lower() and not m.startswith("_")]
            if matches:
                self.chat_log.append(f"  '{prop_human}' not found. Similar on {target_htype}:")
                for m in matches[:10]:
                    hp = _human_prop(m)
                    self.chat_log.append(f"    .{widget_path}.{hp}")
            else:
                self.chat_log.append(f"  '{prop_human}' not found on {target_htype}")

        self.chat_log.append("")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    bar = DotCommandBar()
    bar.show()
    sys.exit(app.exec())
