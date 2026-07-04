#!/usr/bin/env python3
# [@GHOST]{[@file<model_gui.py>][@domain<ModelControlCenter>][@role<gui>][@auth<cascade>][@date<2026-07-03>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<gui>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{ModelGUI — PyQt6 Model Control Center. Table-driven model registry with install/uninstall/delete/restore, search, category filter, stats bar, and dark theme.}

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QComboBox, QStatusBar, QHeaderView, QProgressBar, QGroupBox,
    QGridLayout, QMenu, QDialog, QTextEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QAction

from config import (
    THEME, THEMES, WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    TOOLTIPS, STATUS_MESSAGES, CATEGORIES, STATUSES
)
from model_manager import ModelManager
from model_test_dialog import ModelTestDialog
from llm_test_dialog import LLMTestDialog
from dependency_manager import DependencyManagerDialog
from hardware_detector import HardwareDetector


def build_stylesheet(theme):
    return """
QMainWindow {
    background-color: %s;
}
QWidget {
    color: %s;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid %s;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QTableWidget {
    background-color: %s;
    border: 1px solid %s;
    border-radius: 4px;
    gridline-color: %s;
    selection-background-color: %s;
    selection-color: %s;
    alternate-background-color: %s;
}
QHeaderView::section {
    background-color: %s;
    color: %s;
    padding: 6px;
    border: none;
    border-bottom: 1px solid %s;
    font-weight: bold;
}
QPushButton {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: %s;
    border: 1px solid %s;
}
QPushButton:pressed {
    background-color: %s;
}
QPushButton:disabled {
    background-color: %s;
    color: %s;
}
QLineEdit, QComboBox {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: 4px;
    padding: 5px;
}
QLineEdit:focus, QComboBox:focus {
    border: 2px solid %s;
}
QStatusBar {
    background-color: %s;
    color: %s;
    border-top: 1px solid %s;
}
QProgressBar {
    border: 1px solid %s;
    border-radius: 3px;
    text-align: center;
    background-color: %s;
    color: %s;
}
QProgressBar::chunk {
    background-color: %s;
    border-radius: 2px;
}
QMenu {
    background-color: %s;
    border: 1px solid %s;
    color: %s;
}
QMenu::item {
    padding: 4px 20px;
}
QMenu::item:selected {
    background-color: %s;
}
QTextEdit {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: 4px;
}
QDialog {
    background-color: %s;
}
QLabel {
    color: %s;
}
""" % (
    theme["bg"],
    theme["text"],
    theme["border"],
    theme["surface"],
    theme["border"],
    theme["border"],
    theme["primary"],
    theme["text"],
    theme["bg"],
    theme["surface"],
    theme["text"],
    theme["border"],
    theme["surface"],
    theme["text"],
    theme["border"],
    theme["primary"],
    theme["border"],
    theme["primary"],
    theme["bg"],
    theme["text_dim"],
    theme["surface"],
    theme["text"],
    theme["border"],
    theme["primary"],
    theme["surface"],
    theme["text"],
    theme["border"],
    theme["border"],
    theme["surface"],
    theme["text"],
    theme["primary"],
    theme["surface"],
    theme["border"],
    theme["text"],
    theme["primary"],
    theme["surface"],
    theme["text"],
    theme["border"],
    theme["bg"],
    theme["text"],
)


# Initial stylesheet using default theme
STYLESHEET = build_stylesheet(THEME)


class InstallThread(QThread):
    """Background thread for model installation."""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int)

    def __init__(self, manager, model_id):
        super().__init__()
        self.manager = manager
        self.model_id = model_id

    def run(self):
        self.progress.emit(10)
        success, msg = self.manager.install_model(self.model_id)
        self.progress.emit(100)
        self.finished.emit(success, msg)


class ScanThread(QThread):
    """Background thread for scanning local model files."""
    finished = pyqtSignal(list)
    progress = pyqtSignal(int)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def run(self):
        self.progress.emit(0)
        discovered = self.manager.scan_models()
        self.progress.emit(100)
        self.finished.emit(discovered)


class TestThread(QThread):
    """Background thread for running model validation tests."""
    finished = pyqtSignal(dict, str)
    progress = pyqtSignal(int)

    def __init__(self, manager, model_id, model_name):
        super().__init__()
        self.manager = manager
        self.model_id = model_id
        self.model_name = model_name

    def run(self):
        self.progress.emit(10)
        result = self.manager.test_model(self.model_id)
        self.progress.emit(100)
        self.finished.emit(result, self.model_name)


class ModelGUI(QMainWindow):
    """PyQt6 Model Control Center — registry table + actions + stats."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.manager = ModelManager()
        self.install_thread = None
        self.scan_thread = None
        self.test_thread = None
        self.current_theme = "Catppuccin Dark"
        self.build_ui()
        self.build_menu()
        self.load_models()

    def build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        refresh_action = QAction("Refresh Registry", self)
        refresh_action.setShortcut("Ctrl+R")
        refresh_action.triggered.connect(self.load_models)
        file_menu.addAction(refresh_action)

        scan_action = QAction("Scan for Models", self)
        scan_action.setShortcut("Ctrl+S")
        scan_action.triggered.connect(self.on_scan)
        file_menu.addAction(scan_action)

        test_action = QAction("Test Selected Model", self)
        test_action.setShortcut("Ctrl+T")
        test_action.triggered.connect(self.on_test)
        file_menu.addAction(test_action)

        say_action = QAction("Say Something (TTS Test)", self)
        say_action.setShortcut("Ctrl+Shift+T")
        say_action.triggered.connect(self.on_say_something)
        file_menu.addAction(say_action)

        chat_action = QAction("Chat with LLM Model", self)
        chat_action.setShortcut("Ctrl+Shift+C")
        chat_action.triggered.connect(self.on_chat_with_model)
        file_menu.addAction(chat_action)

        setup_action = QAction("Environment Setup", self)
        setup_action.setShortcut("Ctrl+Shift+E")
        setup_action.triggered.connect(self.on_env_setup)
        file_menu.addAction(setup_action)

        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = menubar.addMenu("View")
        theme_menu = view_menu.addMenu("Theme")
        for theme_name in THEMES.keys():
            theme_action = QAction(theme_name, self, checkable=True)
            theme_action.setChecked(theme_name == self.current_theme)
            theme_action.triggered.connect(lambda checked, name=theme_name: self.on_theme_changed(name))
            theme_menu.addAction(theme_action)

        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        filter_group = QGroupBox("Filter")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setContentsMargins(8, 16, 8, 8)

        lbl_search = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, description, or category...")
        self.search_input.textChanged.connect(self.on_filter_changed)
        self.search_input.setToolTip(TOOLTIPS["search"])

        lbl_cat = QLabel("Category:")
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        self.category_combo.currentTextChanged.connect(self.on_filter_changed)
        self.category_combo.setToolTip(TOOLTIPS["category"])

        filter_layout.addWidget(lbl_search)
        filter_layout.addWidget(self.search_input, 1)
        filter_layout.addWidget(lbl_cat)
        filter_layout.addWidget(self.category_combo)
        layout.addWidget(filter_group)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Name", "Size", "Status", "Category", "Platforms", "Description"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 120)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_context_menu)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.btn_install = QPushButton("Install")
        self.btn_uninstall = QPushButton("Uninstall")
        self.btn_delete = QPushButton("Delete")
        self.btn_restore = QPushButton("Restore")
        self.btn_test = QPushButton("Test Model")
        self.btn_say = QPushButton("Say Something")
        self.btn_chat = QPushButton("Chat with LLM")
        self.btn_setup = QPushButton("Env Setup")
        self.btn_scan = QPushButton("Scan PC")
        self.btn_refresh = QPushButton("Refresh")

        self.btn_install.setToolTip(TOOLTIPS["install"])
        self.btn_uninstall.setToolTip(TOOLTIPS["uninstall"])
        self.btn_delete.setToolTip(TOOLTIPS["delete"])
        self.btn_restore.setToolTip(TOOLTIPS["restore"])
        self.btn_test.setToolTip(TOOLTIPS["test"])
        self.btn_say.setToolTip("Open TTS test dialog — type text, pick voice, make the model speak")
        self.btn_chat.setToolTip("Open LLM chat dialog — chat with GGUF/MLX/ONNX models, optionally speak response")
        self.btn_setup.setToolTip("Install MLX, PyTorch, ONNX, GGUF, Ollama, HuggingFace, embedders — one-click setup")
        self.btn_scan.setToolTip(TOOLTIPS["scan"])
        self.btn_refresh.setToolTip(TOOLTIPS["refresh"])

        self.btn_install.clicked.connect(self.on_install)
        self.btn_uninstall.clicked.connect(self.on_uninstall)
        self.btn_delete.clicked.connect(self.on_delete)
        self.btn_restore.clicked.connect(self.on_restore)
        self.btn_test.clicked.connect(self.on_test)
        self.btn_say.clicked.connect(self.on_say_something)
        self.btn_chat.clicked.connect(self.on_chat_with_model)
        self.btn_setup.clicked.connect(self.on_env_setup)
        self.btn_scan.clicked.connect(self.on_scan)
        self.btn_refresh.clicked.connect(self.load_models)

        btn_row.addWidget(self.btn_install)
        btn_row.addWidget(self.btn_uninstall)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_restore)
        btn_row.addWidget(self.btn_test)
        btn_row.addWidget(self.btn_say)
        btn_row.addWidget(self.btn_chat)
        btn_row.addWidget(self.btn_setup)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_scan)
        btn_row.addWidget(self.btn_refresh)
        layout.addLayout(btn_row)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(16)
        progress_row.addWidget(self.progress_bar)
        layout.addLayout(progress_row)

        stats_group = QGroupBox("Statistics")
        stats_layout = QGridLayout(stats_group)
        stats_layout.setContentsMargins(8, 16, 8, 8)
        self.lbl_total = QLabel("Total: 0")
        self.lbl_installed = QLabel("Installed: 0")
        self.lbl_not_installed = QLabel("Not Installed: 0")
        self.lbl_deleted = QLabel("Deleted: 0")
        self.lbl_size = QLabel("Installed Size: 0 MB")
        stats_layout.addWidget(self.lbl_total, 0, 0)
        stats_layout.addWidget(self.lbl_installed, 0, 1)
        stats_layout.addWidget(self.lbl_not_installed, 0, 2)
        stats_layout.addWidget(self.lbl_deleted, 0, 3)
        stats_layout.addWidget(self.lbl_size, 0, 4)
        layout.addWidget(stats_group)

        sys_group = QGroupBox("System Resources")
        sys_layout = QHBoxLayout(sys_group)
        sys_layout.setContentsMargins(8, 16, 8, 8)
        self.lbl_sys_chip = QLabel("Chip: —")
        self.lbl_sys_ram = QLabel("RAM: —")
        self.lbl_sys_disk = QLabel("Disk: —")
        self.lbl_sys_gpu = QLabel("GPU: —")
        self.lbl_sys_ram.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.lbl_sys_chip.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.lbl_sys_disk.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.lbl_sys_gpu.setStyleSheet("font-family: monospace; font-size: 11px;")
        sys_layout.addWidget(self.lbl_sys_chip)
        sys_layout.addWidget(self.lbl_sys_ram)
        sys_layout.addWidget(self.lbl_sys_disk)
        sys_layout.addWidget(self.lbl_sys_gpu)
        btn_sys_refresh = QPushButton("Refresh")
        btn_sys_refresh.setFixedWidth(80)
        btn_sys_refresh.clicked.connect(self.refresh_system_info)
        sys_layout.addWidget(btn_sys_refresh)
        layout.addWidget(sys_group)

        self.sysinfo = HardwareDetector()
        self.refresh_system_info()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(STATUS_MESSAGES["ready"])

    def load_models(self):
        category = self.category_combo.currentText()
        search = self.search_input.text()
        models = self.manager.filter_models(category=category, search=search)
        self.table.setRowCount(len(models))
        for i, m in enumerate(models):
            name_item = QTableWidgetItem(m["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, m["id"])
            self.table.setItem(i, 0, name_item)

            size_text = "%d MB" % m["size_mb"] if m["size_mb"] > 0 else "—"
            self.table.setItem(i, 1, QTableWidgetItem(size_text))

            status_key = m["status"]
            status_label, status_color = STATUSES.get(status_key, (status_key, THEME["text"]))
            status_item = QTableWidgetItem(status_label)
            status_item.setForeground(QColor(status_color))
            font = QFont()
            font.setBold(True)
            status_item.setFont(font)
            self.table.setItem(i, 2, status_item)

            self.table.setItem(i, 3, QTableWidgetItem(m.get("category", "Other")))
            self.table.setItem(i, 4, QTableWidgetItem(", ".join(m.get("platforms", []))))
            self.table.setItem(i, 5, QTableWidgetItem(m["description"]))

        self.update_stats()
        self.status_bar.showMessage(STATUS_MESSAGES["ready"])

    def update_stats(self):
        stats = self.manager.get_stats()
        self.lbl_total.setText("Total: %d" % stats["total"])
        self.lbl_installed.setText("Installed: %d" % stats["installed"])
        self.lbl_not_installed.setText("Not Installed: %d" % stats["not_installed"])
        self.lbl_deleted.setText("Deleted: %d" % stats["deleted"])
        self.lbl_size.setText("Installed Size: %d MB" % stats["total_size_mb"])

    def refresh_system_info(self):
        info = self.sysinfo.get_summary()
        ramAvail = info.get("ram_available_mb", 0)
        ramTotal = info.get("ram_total_mb", 0)
        diskFree = info.get("disk_free_mb", 0)
        self.lbl_sys_chip.setText("Chip: %s" % info.get("cpu", "Unknown"))
        ramColor = "#a6e3a1" if ramAvail > 2048 else "#f9e2af" if ramAvail > 1024 else "#f38ba8"
        self.lbl_sys_ram.setText("RAM: %.1f GB free / %.1f GB total" % (ramAvail / 1024.0, ramTotal / 1024.0))
        diskColor = "#a6e3a1" if diskFree > 5120 else "#f9e2af" if diskFree > 2048 else "#f38ba8"
        self.lbl_sys_disk.setText("Disk: %.1f GB free" % (diskFree / 1024.0))
        gpuName = info.get("gpu", "None")
        if info.get("metal"):
            gpuName = gpuName + " (Metal)"
        if info.get("neural_engine"):
            gpuName = gpuName + " + ANE"
        self.lbl_sys_gpu.setText("GPU: %s" % gpuName)
        self.lbl_sys_ram.setStyleSheet("font-family: monospace; font-size: 11px; color: %s;" % ramColor)
        self.lbl_sys_disk.setStyleSheet("font-family: monospace; font-size: 11px; color: %s;" % diskColor)

    def on_filter_changed(self):
        self.load_models()

    def get_selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            self.status_bar.showMessage(STATUS_MESSAGES["no_selection"])
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def on_install(self):
        mid = self.get_selected_id()
        if not mid:
            return
        self.set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage(STATUS_MESSAGES["installing"])
        self.install_thread = InstallThread(self.manager, mid)
        self.install_thread.finished.connect(self.on_install_done)
        self.install_thread.progress.connect(self.progress_bar.setValue)
        self.install_thread.start()

    def on_install_done(self, success, message):
        self.progress_bar.setVisible(False)
        self.set_buttons_enabled(True)
        if success:
            self.status_bar.showMessage(STATUS_MESSAGES["installed"])
        else:
            self.status_bar.showMessage(STATUS_MESSAGES["error"] % message)
        self.load_models()

    def on_uninstall(self):
        mid = self.get_selected_id()
        if not mid:
            return
        self.status_bar.showMessage(STATUS_MESSAGES["uninstalling"])
        success, msg = self.manager.uninstall_model(mid)
        if success:
            self.status_bar.showMessage(STATUS_MESSAGES["uninstalled"])
        else:
            self.status_bar.showMessage(STATUS_MESSAGES["error"] % msg)
        self.load_models()

    def on_delete(self):
        mid = self.get_selected_id()
        if not mid:
            return
        self.status_bar.showMessage(STATUS_MESSAGES["deleting"])
        success, msg = self.manager.delete_model(mid)
        if success:
            self.status_bar.showMessage(STATUS_MESSAGES["deleted"])
        else:
            self.status_bar.showMessage(STATUS_MESSAGES["error"] % msg)
        self.load_models()

    def on_restore(self):
        mid = self.get_selected_id()
        if not mid:
            return
        self.status_bar.showMessage(STATUS_MESSAGES["restoring"])
        success, msg = self.manager.restore_model(mid)
        if success:
            self.status_bar.showMessage(STATUS_MESSAGES["restored"])
        else:
            self.status_bar.showMessage(STATUS_MESSAGES["error"] % msg)
        self.load_models()

    def on_context_menu(self, position):
        row = self.table.rowAt(position.y())
        if row < 0:
            return
        self.table.selectRow(row)
        mid = self.get_selected_id()
        if not mid:
            return
        model = self.manager.get_model(mid)
        if not model:
            return

        menu = QMenu(self)
        if model["status"] != "installed":
            act_install = menu.addAction("Install")
            act_install.triggered.connect(self.on_install)
        if model["status"] == "installed":
            act_uninstall = menu.addAction("Uninstall")
            act_uninstall.triggered.connect(self.on_uninstall)
        if model["status"] != "deleted":
            act_delete = menu.addAction("Delete")
            act_delete.triggered.connect(self.on_delete)
        if model["status"] == "deleted":
            act_restore = menu.addAction("Restore")
            act_restore.triggered.connect(self.on_restore)

        menu.addSeparator()
        act_test = menu.addAction("Test Model")
        act_test.triggered.connect(self.on_test)

        act_say = menu.addAction("Say Something (TTS Test)")
        act_say.triggered.connect(self.on_say_something)

        act_chat = menu.addAction("Chat with LLM")
        act_chat.triggered.connect(self.on_chat_with_model)

        menu.addSeparator()
        act_info = menu.addAction("Show Details")
        act_info.triggered.connect(self.show_details)

        menu.exec(self.table.viewport().mapToGlobal(position))

    def show_details(self):
        mid = self.get_selected_id()
        if not mid:
            return
        model = self.manager.get_model(mid)
        if not model:
            return
        lines = [
            "ID: %s" % model["id"],
            "Name: %s" % model["name"],
            "Version: %s" % model.get("version", "?"),
            "Category: %s" % model.get("category", "Other"),
            "Size: %d MB" % model["size_mb"] if model["size_mb"] > 0 else "Size: —",
            "Status: %s" % model["status"],
            "Platforms: %s" % ", ".join(model.get("platforms", [])),
            "Pip deps: %s" % ", ".join(model.get("pip", [])) if model.get("pip") else "None",
            "Source: %s" % model.get("source_url", "—"),
            "Local path: %s" % model.get("local_path", "—"),
            "Description: %s" % model["description"],
        ]
        self.status_bar.showMessage(" | ".join(lines[:3]))

    def set_buttons_enabled(self, enabled):
        self.btn_install.setEnabled(enabled)
        self.btn_uninstall.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)
        self.btn_restore.setEnabled(enabled)
        self.btn_test.setEnabled(enabled)
        self.btn_say.setEnabled(enabled)
        self.btn_chat.setEnabled(enabled)
        self.btn_setup.setEnabled(enabled)
        self.btn_scan.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)

    def on_test(self):
        mid = self.get_selected_id()
        if not mid:
            return
        model = self.manager.get_model(mid)
        if not model:
            return
        file_path = model.get("file_path") or model.get("local_path")
        if not file_path:
            self.status_bar.showMessage(STATUS_MESSAGES["test_no_file"])
            return
        self.set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage(STATUS_MESSAGES["testing"])
        self.test_thread = TestThread(self.manager, mid, model["name"])
        self.test_thread.finished.connect(self.on_test_done)
        self.test_thread.progress.connect(self.progress_bar.setValue)
        self.test_thread.start()

    def on_test_done(self, result, model_name):
        self.progress_bar.setVisible(False)
        self.set_buttons_enabled(True)
        if result.get("overall_pass"):
            self.status_bar.showMessage(STATUS_MESSAGES["test_pass"])
        else:
            self.status_bar.showMessage(STATUS_MESSAGES["test_fail"])
        self.show_test_results(result, model_name)

    def show_test_results(self, result, model_name):
        dialog = QDialog(self)
        dialog.setWindowTitle("Test Results — %s" % model_name)
        dialog.resize(700, 500)
        layout = QVBoxLayout(dialog)

        passed = result.get("overall_pass", False)
        status_text = "PASSED" if passed else "FAILED"
        status_color = THEME["success"] if passed else THEME["danger"]

        header = QLabel("<h2 style='color: %s;'>%s</h2>" % (status_color, status_text))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        info_label = QLabel("Model: %s" % model_name)
        layout.addWidget(info_label)

        if result.get("details", {}).get("size_mb"):
            info_label.setText(info_label.text() + "  |  Size: %d MB" % result["details"]["size_mb"])

        results_text = QTextEdit()
        results_text.setReadOnly(True)

        lines = []
        lines.append("=== TEST RESULTS ===")
        lines.append("Overall: %s\n" % status_text)

        if result.get("tests_passed"):
            lines.append("--- PASSED CHECKS ---")
            for t in result["tests_passed"]:
                lines.append("  [PASS] %s" % t)
            lines.append("")

        if result.get("tests_failed"):
            lines.append("--- FAILED CHECKS ---")
            for t in result["tests_failed"]:
                lines.append("  [FAIL] %s" % t)
            lines.append("")

        if result.get("warnings"):
            lines.append("--- WARNINGS ---")
            for w in result["warnings"]:
                lines.append("  [WARN] %s" % w)
            lines.append("")

        if result.get("details"):
            lines.append("--- DETAILS ---")
            for key, val in result["details"].items():
                lines.append("  %s: %s" % (key, val))
            lines.append("")

        results_text.setPlainText("\n".join(lines))
        layout.addWidget(results_text)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)
        dialog.exec()

    def on_say_something(self):
        mid = self.get_selected_id()
        model_info = None
        if mid:
            model_info = self.manager.get_model(mid)
        if not model_info:
            model_info = {"name": "Kokoro 82M FP16", "description": "Neural TTS — type text and click Speak"}
        self.status_bar.showMessage("Opening TTS test dialog...")
        dialog = ModelTestDialog(self, model_id=mid, model_info=model_info)
        dialog.exec()
        self.status_bar.showMessage(STATUS_MESSAGES["ready"])

    def on_chat_with_model(self):
        mid = self.get_selected_id()
        model_info = None
        if mid:
            model_info = self.manager.get_model(mid)
        if not model_info:
            model_info = {"name": "MLX LLM Model", "description": "Chat with local LLM models (mlx_lm, ollama, llama.cpp)"}
        self.status_bar.showMessage("Opening LLM chat dialog...")
        dialog = LLMTestDialog(self, model_id=mid, model_info=model_info)
        dialog.exec()
        self.status_bar.showMessage(STATUS_MESSAGES["ready"])

    def on_env_setup(self):
        self.status_bar.showMessage("Opening Environment Setup...")
        dialog = DependencyManagerDialog(self, theme=THEME)
        dialog.exec()
        self.status_bar.showMessage(STATUS_MESSAGES["ready"])

    def on_theme_changed(self, theme_name):
        global THEME
        THEME = THEMES[theme_name]
        self.current_theme = theme_name
        app = QApplication.instance()
        app.setStyleSheet(build_stylesheet(THEME))
        self.load_models()
        self.status_bar.showMessage(STATUS_MESSAGES["theme_changed"] % theme_name)
        menubar = self.menuBar()
        for menu in [menubar.actions()[i].menu() for i in range(menubar.actions().__len__())]:
            if menu and menu.title() == "Theme":
                for action in menu.actions():
                    action.setChecked(action.text() == theme_name)

    def on_scan(self):
        self.set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage(STATUS_MESSAGES["scanning"])
        self.scan_thread = ScanThread(self.manager)
        self.scan_thread.finished.connect(self.on_scan_done)
        self.scan_thread.progress.connect(self.progress_bar.setValue)
        self.scan_thread.start()

    def on_scan_done(self, discovered):
        self.progress_bar.setVisible(False)
        self.set_buttons_enabled(True)
        if not discovered:
            self.status_bar.showMessage(STATUS_MESSAGES["scan_empty"])
            return

        added = self.manager.add_discovered(discovered)
        self.status_bar.showMessage(STATUS_MESSAGES["scan_done"] % added)
        self.show_scan_results(discovered, added)
        self.load_models()

    def show_scan_results(self, discovered, added):
        dialog = QDialog(self)
        dialog.setWindowTitle("Scan Results — %d found, %d new" % (len(discovered), added))
        dialog.resize(700, 400)
        layout = QVBoxLayout(dialog)

        info_label = QLabel("Found %d model file(s) on your Mac. %d were new and added to the registry." % (len(discovered), added))
        layout.addWidget(info_label)

        results_text = QTextEdit()
        results_text.setReadOnly(True)
        lines = []
        for dm in discovered:
            status_tag = "NEW" if dm["id"] not in set(m["id"] for m in self.manager.models[:len(self.manager.models) - added]) else "existing"
            lines.append("[%s] %s (%d MB, %s)\n  Path: %s\n" % (
                status_tag, dm["name"], dm["size_mb"], dm.get("file_type", "?"), dm.get("file_path", dm.get("local_path", "?"))
            ))
        results_text.setPlainText("\n".join(lines))
        layout.addWidget(results_text)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)
        dialog.exec()

    def show_about(self):
        self.status_bar.showMessage(
            "Model Control Center v1.0 — PyQt6 model registry manager with local scanner"
        )


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setApplicationName("Model Control Center")
    window = ModelGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
