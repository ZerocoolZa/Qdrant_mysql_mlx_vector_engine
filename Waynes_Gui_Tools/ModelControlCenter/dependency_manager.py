#!/usr/bin/env python3
# [@GHOST]{[@file<dependency_manager.py>][@domain<ModelControlCenter>][@role<deps>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<Centralized dependency installer for all AI backends: MLX, PyTorch, ONNX, llama.cpp/GGUF, Ollama, HuggingFace, embedders. One-click install with status detection.>]}
# [@VBSTYLE]{[@auth<devin>][@role<deps>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{DependencyManager — PyQt6 dialog for installing and managing all AI runtime dependencies. Detects installed packages, shows version, one-click pip install, Ollama service management, HuggingFace CLI, embedders. Status table with install/uninstall buttons.}
# [@FILEID]{dependency_manager.py}
# [@CLASS]{DependencyManagerDialog, InstallDepsThread, CheckDepsThread}
# [@METHOD]{Run, CheckAll, InstallPackage, UninstallPackage, StartOllama, StopOllama, RefreshStatus}

import os
import sys
import subprocess
import shutil
import urllib.request
import urllib.error
import json
import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTextEdit, QGroupBox,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QStatusBar, QCheckBox, QMessageBox, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont


# ═══════════════════════════════════════════════════════════
# DEPENDENCY CATALOG — everything that can be installed
# ═══════════════════════════════════════════════════════════

DEPS_CATALOG = [
    # --- MLX (Apple Silicon native) ---
    {"id": "mlx", "name": "MLX Core", "category": "MLX",
     "pip": "mlx", "import": "mlx", "desc": "Apple MLX array framework"},
    {"id": "mlx_lm", "name": "MLX-LM", "category": "MLX",
     "pip": "mlx-lm", "import": "mlx_lm", "desc": "LLM inference on Apple Silicon"},
    {"id": "mlx_vlm", "name": "MLX-VLM", "category": "MLX",
     "pip": "mlx-vlm", "import": "mlx_vlm", "desc": "Vision-language models on MLX"},

    # --- PyTorch ---
    {"id": "torch", "name": "PyTorch", "category": "PyTorch",
     "pip": "torch", "import": "torch", "desc": "Deep learning framework"},
    {"id": "torchvision", "name": "TorchVision", "category": "PyTorch",
     "pip": "torchvision", "import": "torchvision", "desc": "Vision models + datasets"},
    {"id": "transformers", "name": "Transformers (HuggingFace)", "category": "PyTorch",
     "pip": "transformers", "import": "transformers", "desc": "HuggingFace model hub"},

    # --- ONNX ---
    {"id": "onnxruntime", "name": "ONNX Runtime", "category": "ONNX",
     "pip": "onnxruntime", "import": "onnxruntime", "desc": "Cross-platform ML inference"},
    {"id": "onnx", "name": "ONNX", "category": "ONNX",
     "pip": "onnx", "import": "onnx", "desc": "ONNX model format tools"},

    # --- GGUF / llama.cpp ---
    {"id": "llama_cpp", "name": "llama-cpp-python", "category": "GGUF",
     "pip": "llama-cpp-python", "import": "llama_cpp", "desc": "GGUF model inference"},
    {"id": "gguf", "name": "gguf (reader)", "category": "GGUF",
     "pip": "gguf", "import": "gguf", "desc": "Read GGUF file metadata"},

    # --- Ollama ---
    {"id": "ollama", "name": "Ollama (service)", "category": "Ollama",
     "pip": None, "import": None, "desc": "Local LLM service (HTTP API on :11434)",
     "binary": "ollama"},

    # --- HuggingFace ---
    {"id": "huggingface_hub", "name": "HuggingFace Hub", "category": "HuggingFace",
     "pip": "huggingface-hub", "import": "huggingface_hub", "desc": "Download models from HF Hub"},
    {"id": "hf_cli", "name": "HuggingFace CLI", "category": "HuggingFace",
     "pip": "huggingface-hub[cli]", "import": "huggingface_hub", "desc": "HF command-line tools"},
    {"id": "datasets", "name": "Datasets", "category": "HuggingFace",
     "pip": "datasets", "import": "datasets", "desc": "HuggingFace datasets library"},
    {"id": "accelerate", "name": "Accelerate", "category": "HuggingFace",
     "pip": "accelerate", "import": "accelerate", "desc": "Distributed/optimized training"},

    # --- Embedders ---
    {"id": "sentence_transformers", "name": "Sentence Transformers", "category": "Embedders",
     "pip": "sentence-transformers", "import": "sentence_transformers", "desc": "Text embeddings"},
    {"id": "faiss_cpu", "name": "FAISS (CPU)", "category": "Embedders",
     "pip": "faiss-cpu", "import": "faiss", "desc": "Vector similarity search"},
    {"id": "chromadb", "name": "ChromaDB", "category": "Embedders",
     "pip": "chromadb", "import": "chromadb", "desc": "Vector database"},
    {"id": "qdrant_client", "name": "Qdrant Client", "category": "Embedders",
     "pip": "qdrant-client", "import": "qdrant_client", "desc": "Qdrant vector DB client"},

    # --- CoreML ---
    {"id": "coremltools", "name": "CoreML Tools", "category": "CoreML",
     "pip": "coremltools", "import": "coremltools", "desc": "Apple CoreML model tools"},

    # --- Audio / TTS ---
    {"id": "soundfile", "name": "SoundFile", "category": "Audio",
     "pip": "soundfile", "import": "soundfile", "desc": "Audio file I/O"},
    {"id": "edge_tts", "name": "Edge TTS", "category": "Audio",
     "pip": "edge-tts", "import": "edge_tts", "desc": "Microsoft Edge neural TTS"},
    {"id": "numpy", "name": "NumPy", "category": "Audio",
     "pip": "numpy", "import": "numpy", "desc": "Numerical computing"},
]


# ═══════════════════════════════════════════════════════════
# BACKGROUND THREADS
# ═══════════════════════════════════════════════════════════

class CheckDepsThread(QThread):
    """Check all dependencies in background."""
    result_ready = pyqtSignal(dict)  # dep_id -> {installed, version, message}
    finished_all = pyqtSignal()

    def __init__(self, catalog):
        super().__init__()
        self.catalog = catalog

    def run(self):
        for dep in self.catalog:
            result = self._check_one(dep)
            self.result_ready.emit({dep["id"]: result})
        self.finished_all.emit()

    def _check_one(self, dep):
        if dep.get("import"):
            try:
                mod = __import__(dep["import"])
                version = getattr(mod, "__version__", "installed")
                return {"installed": True, "version": str(version), "message": "OK"}
            except ImportError:
                return {"installed": False, "version": "", "message": "Not installed"}
            except Exception as e:
                return {"installed": False, "version": "", "message": "Error: %s" % str(e)[:80]}
        elif dep.get("binary"):
            path = shutil.which(dep["binary"])
            if path:
                version = ""
                try:
                    r = subprocess.run([dep["binary"], "--version"],
                                       capture_output=True, text=True, timeout=5)
                    version = r.stdout.strip()[:60]
                except Exception:
                    pass
                return {"installed": True, "version": version, "message": "Found at %s" % path}
            return {"installed": False, "version": "", "message": "Binary not in PATH"}
        return {"installed": False, "version": "", "message": "Unknown check method"}


class InstallDepsThread(QThread):
    """Install a pip package in background."""
    finished_install = pyqtSignal(bool, str, str)  # success, dep_id, message
    progress = pyqtSignal(str)

    def __init__(self, dep_id, pip_name):
        super().__init__()
        self.dep_id = dep_id
        self.pip_name = pip_name

    def run(self):
        self.progress.emit("Installing %s..." % self.pip_name)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", self.pip_name],
                capture_output=True, text=True, timeout=300
            )
            if proc.returncode == 0:
                self.finished_install.emit(True, self.dep_id, "Installed %s" % self.pip_name)
            else:
                err = proc.stderr.strip()[-200:] if proc.stderr else "Unknown error"
                self.finished_install.emit(False, self.dep_id, err)
        except subprocess.TimeoutExpired:
            self.finished_install.emit(False, self.dep_id, "Install timed out (5 min)")
        except Exception as e:
            self.finished_install.emit(False, self.dep_id, str(e))


class UninstallDepsThread(QThread):
    """Uninstall a pip package in background."""
    finished_uninstall = pyqtSignal(bool, str, str)

    def __init__(self, dep_id, pip_name):
        super().__init__()
        self.dep_id = dep_id
        self.pip_name = pip_name

    def run(self):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", self.pip_name],
                capture_output=True, text=True, timeout=120
            )
            if proc.returncode == 0:
                self.finished_uninstall.emit(True, self.dep_id, "Uninstalled %s" % self.pip_name)
            else:
                self.finished_uninstall.emit(False, self.dep_id, proc.stderr.strip()[-200:])
        except Exception as e:
            self.finished_uninstall.emit(False, self.dep_id, str(e))


# ═══════════════════════════════════════════════════════════
# MAIN DIALOG
# ═══════════════════════════════════════════════════════════

class DependencyManagerDialog(QDialog):
    """Install, uninstall, and manage all AI runtime dependencies."""

    def __init__(self, parent=None, theme=None):
        super().__init__(parent)
        self.theme = theme or {
            "bg": "#1e1e2e", "surface": "#313244", "primary": "#89b4fa",
            "text": "#cdd6f4", "text_dim": "#a6adc8", "success": "#a6e3a1",
            "danger": "#f38ba8", "warning": "#f9e2af", "border": "#45475a"
        }
        self.setWindowTitle("Environment Setup — AI Runtime Dependencies")
        self.resize(1000, 700)
        self.setStyleSheet(self._build_style(self.theme))
        self.dep_status = {}
        self.install_thread = None
        self.uninstall_thread = None
        self.check_thread = None
        self._build_ui()
        self._start_check_all()

    def _build_style(self, t):
        return """
        QDialog { background-color: %s; }
        QWidget { color: %s; font-size: 13px; }
        QGroupBox { border: 1px solid %s; border-radius: 6px; margin-top: 12px; padding-top: 12px; font-weight: bold; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QTableWidget { background-color: %s; border: 1px solid %s; border-radius: 4px; gridline-color: %s; selection-background-color: %s; }
        QHeaderView::section { background-color: %s; color: %s; padding: 6px; border: none; border-bottom: 1px solid %s; font-weight: bold; }
        QPushButton { background-color: %s; color: %s; border: 1px solid %s; border-radius: 4px; padding: 6px 16px; font-weight: bold; }
        QPushButton:hover { background-color: %s; }
        QPushButton:disabled { background-color: %s; color: %s; }
        QStatusBar { background-color: %s; color: %s; border-top: 1px solid %s; }
        QProgressBar { border: 1px solid %s; border-radius: 3px; text-align: center; background-color: %s; }
        QProgressBar::chunk { background-color: %s; border-radius: 2px; }
        QTextEdit { background-color: %s; color: %s; border: 1px solid %s; border-radius: 4px; font-family: monospace; }
        QTabWidget::pane { border: 1px solid %s; }
        QTabBar::tab { background-color: %s; color: %s; padding: 8px 16px; border: 1px solid %s; }
        QTabBar::tab:selected { background-color: %s; color: %s; }
        """ % (
            t["bg"], t["text"], t["border"],
            t["surface"], t["border"], t["border"], t["primary"],
            t["surface"], t["text"], t["border"],
            t["surface"], t["text"], t["border"],
            t["primary"],
            t["bg"], t["text_dim"],
            t["surface"], t["text_dim"], t["border"],
            t["border"], t["surface"],
            t["primary"],
            t["surface"], t["text"], t["border"],
            t["border"],
            t["surface"], t["text_dim"], t["border"],
            t["primary"], t["text"],
        )

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("AI Runtime Environment Setup")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: %s;" % self.theme["primary"])
        layout.addWidget(title)

        subtitle = QLabel("Install, manage, and verify all AI backends: MLX, PyTorch, ONNX, GGUF, Ollama, HuggingFace, Embedders")
        subtitle.setStyleSheet("color: %s;" % self.theme["text_dim"])
        layout.addWidget(subtitle)

        # Action bar
        action_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh Status")
        self.btn_refresh.clicked.connect(self._start_check_all)
        self.btn_install_all = QPushButton("Install All Missing")
        self.btn_install_all.setStyleSheet("background-color: %s; color: #000;" % self.theme["success"])
        self.btn_install_all.clicked.connect(self._install_all_missing)

        self.btn_start_ollama = QPushButton("Start Ollama")
        self.btn_start_ollama.clicked.connect(self._start_ollama)
        self.btn_stop_ollama = QPushButton("Stop Ollama")
        self.btn_stop_ollama.clicked.connect(self._stop_ollama)

        action_row.addWidget(self.btn_refresh)
        action_row.addWidget(self.btn_install_all)
        action_row.addStretch()
        action_row.addWidget(self.btn_start_ollama)
        action_row.addWidget(self.btn_stop_ollama)
        layout.addLayout(action_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        # Dependencies table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Category", "Name", "Description", "Status", "Version", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 160)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        # Log area
        log_group = QGroupBox("Install Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(8, 16, 8, 8)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Checking dependencies...")
        layout.addWidget(self.status_bar)

    def _log(self, msg):
        self.log_text.append(msg)

    def _start_check_all(self):
        self.dep_status = {}
        self.table.setRowCount(len(DEPS_CATALOG))
        for i, dep in enumerate(DEPS_CATALOG):
            self.table.setItem(i, 0, QTableWidgetItem(dep["category"]))
            self.table.setItem(i, 1, QTableWidgetItem(dep["name"]))
            self.table.setItem(i, 2, QTableWidgetItem(dep["desc"]))
            self.table.setItem(i, 3, QTableWidgetItem("Checking..."))
            self.table.setItem(i, 4, QTableWidgetItem(""))
            self.table.setItem(i, 5, QTableWidgetItem(""))

        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Checking %d dependencies..." % len(DEPS_CATALOG))
        self.check_thread = CheckDepsThread(DEPS_CATALOG)
        self.check_thread.result_ready.connect(self._on_dep_checked)
        self.check_thread.finished_all.connect(self._on_check_all_done)
        self.check_thread.start()

    def _on_dep_checked(self, result):
        dep_id = list(result.keys())[0]
        info = result[dep_id]
        self.dep_status[dep_id] = info

        for i, dep in enumerate(DEPS_CATALOG):
            if dep["id"] == dep_id:
                status_text = "Installed" if info["installed"] else "Missing"
                status_color = self.theme["success"] if info["installed"] else self.theme["danger"]
                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(QColor(status_color))
                font = QFont()
                font.setBold(True)
                status_item.setFont(font)
                self.table.setItem(i, 3, status_item)
                self.table.setItem(i, 4, QTableWidgetItem(info["version"]))

                # Action buttons
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(2, 2, 2, 2)
                btn_layout.setSpacing(4)

                if dep.get("pip"):
                    if info["installed"]:
                        btn_uninstall = QPushButton("Uninstall")
                        btn_uninstall.setFixedHeight(26)
                        btn_uninstall.clicked.connect(lambda checked, d=dep: self._uninstall_dep(d))
                        btn_layout.addWidget(btn_uninstall)
                    else:
                        btn_install = QPushButton("Install")
                        btn_install.setFixedHeight(26)
                        btn_install.setStyleSheet("background-color: %s; color: #000;" % self.theme["success"])
                        btn_install.clicked.connect(lambda checked, d=dep: self._install_dep(d))
                        btn_layout.addWidget(btn_install)
                elif dep.get("binary") and not info["installed"]:
                    btn_install = QPushButton("Install")
                    btn_install.setFixedHeight(26)
                    btn_install.clicked.connect(lambda checked, d=dep: self._install_binary(d))
                    btn_layout.addWidget(btn_install)

                btn_layout.addStretch()
                self.table.setCellWidget(i, 5, btn_widget)
                break

    def _on_check_all_done(self):
        self.progress_bar.setVisible(False)
        installed = sum(1 for v in self.dep_status.values() if v["installed"])
        total = len(self.dep_status)
        missing = total - installed
        self.status_bar.showMessage("Done: %d/%d installed, %d missing" % (installed, total, missing))
        self._log("=== Status: %d installed, %d missing ===" % (installed, missing))

    def _install_dep(self, dep):
        self._log("Installing %s (pip install %s)..." % (dep["name"], dep["pip"]))
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Installing %s..." % dep["name"])
        self.btn_refresh.setEnabled(False)
        self.install_thread = InstallDepsThread(dep["id"], dep["pip"])
        self.install_thread.progress.connect(self._log)
        self.install_thread.finished_install.connect(self._on_install_done)
        self.install_thread.start()

    def _on_install_done(self, success, dep_id, message):
        self.progress_bar.setVisible(False)
        self.btn_refresh.setEnabled(True)
        dep_name = next((d["name"] for d in DEPS_CATALOG if d["id"] == dep_id), dep_id)
        if success:
            self._log("[OK] %s: %s" % (dep_name, message))
            self.status_bar.showMessage("Installed %s — refreshing..." % dep_name)
        else:
            self._log("[FAIL] %s: %s" % (dep_name, message))
            self.status_bar.showMessage("Failed to install %s" % dep_name)
        # Re-check this one dep
        self._start_check_all()

    def _uninstall_dep(self, dep):
        reply = QMessageBox.question(
            self, "Confirm Uninstall",
            "Uninstall %s (%s)?" % (dep["name"], dep["pip"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._log("Uninstalling %s..." % dep["name"])
        self.progress_bar.setVisible(True)
        self.uninstall_thread = UninstallDepsThread(dep["id"], dep["pip"])
        self.uninstall_thread.finished_uninstall.connect(self._on_uninstall_done)
        self.uninstall_thread.start()

    def _on_uninstall_done(self, success, dep_id, message):
        self.progress_bar.setVisible(False)
        dep_name = next((d["name"] for d in DEPS_CATALOG if d["id"] == dep_id), dep_id)
        if success:
            self._log("[OK] %s uninstalled" % dep_name)
        else:
            self._log("[FAIL] %s: %s" % (dep_name, message))
        self._start_check_all()

    def _install_binary(self, dep):
        if dep["id"] == "ollama":
            reply = QMessageBox.information(
                self, "Install Ollama",
                "Ollama needs to be installed via Homebrew or from the website.\n\n"
                "Run: brew install ollama\n\n"
                "Or download from: https://ollama.com/download\n\n"
                "Click OK to install via Homebrew.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Ok:
                self._log("Installing Ollama via Homebrew...")
                self.progress_bar.setVisible(True)
                try:
                    proc = subprocess.run(
                        ["brew", "install", "ollama"],
                        capture_output=True, text=True, timeout=300
                    )
                    if proc.returncode == 0:
                        self._log("[OK] Ollama installed via Homebrew")
                    else:
                        self._log("[FAIL] %s" % proc.stderr.strip()[-200:])
                except Exception as e:
                    self._log("[FAIL] %s" % str(e))
                self.progress_bar.setVisible(False)
                self._start_check_all()

    def _install_all_missing(self):
        missing = [d for d in DEPS_CATALOG if d.get("pip") and not self.dep_status.get(d["id"], {}).get("installed")]
        if not missing:
            self.status_bar.showMessage("All dependencies already installed!")
            return
        reply = QMessageBox.question(
            self, "Install All Missing",
            "Install %d missing dependencies?\n%s" % (
                len(missing),
                "\n".join("  - %s (%s)" % (d["name"], d["pip"]) for d in missing[:10])
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._install_queue = missing
        self._install_next_in_queue()

    def _install_next_in_queue(self):
        if not self._install_queue:
            self.progress_bar.setVisible(False)
            self.status_bar.showMessage("All installations complete")
            self._start_check_all()
            return
        dep = self._install_queue.pop(0)
        self._log("Installing %s..." % dep["name"])
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Installing %s (%d left)..." % (dep["name"], len(self._install_queue)))
        self.install_thread = InstallDepsThread(dep["id"], dep["pip"])
        self.install_thread.progress.connect(self._log)
        self.install_thread.finished_install.connect(lambda s, did, msg: self._on_queue_install_done(s, did, msg))
        self.install_thread.start()

    def _on_queue_install_done(self, success, dep_id, message):
        dep_name = next((d["name"] for d in DEPS_CATALOG if d["id"] == dep_id), dep_id)
        if success:
            self._log("[OK] %s installed" % dep_name)
        else:
            self._log("[FAIL] %s: %s" % (dep_name, message))
        self._install_next_in_queue()

    def _start_ollama(self):
        self._log("Starting Ollama service...")
        try:
            subprocess.Popen(["ollama", "serve"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._log("[OK] Ollama service started")
            self.status_bar.showMessage("Ollama started — checking...")
            QTimer.singleShot(2000, self._check_ollama_status)
        except FileNotFoundError:
            self._log("[FAIL] Ollama binary not found. Install it first.")
            self.status_bar.showMessage("Ollama not installed")

    def _stop_ollama(self):
        self._log("Stopping Ollama service...")
        try:
            subprocess.run(["pkill", "-f", "ollama serve"],
                           capture_output=True, timeout=5)
            self._log("[OK] Ollama service stopped")
            self.status_bar.showMessage("Ollama stopped")
        except Exception as e:
            self._log("[FAIL] %s" % str(e))

    def _check_ollama_status(self):
        try:
            url = "http://localhost:11434/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                self._log("[OK] Ollama running — %d models available" % len(models))
                self.status_bar.showMessage("Ollama running — %d models" % len(models))
        except Exception:
            self._log("[FAIL] Ollama not responding on :11434")
            self.status_bar.showMessage("Ollama not responding")


from PyQt6.QtCore import QTimer
