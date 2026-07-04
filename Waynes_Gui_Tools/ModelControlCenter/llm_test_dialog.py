#!/usr/bin/env python3
# [@GHOST]{[@file<llm_test_dialog.py>][@domain<ModelControlCenter>][@role<llm_test_dialog>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<LLM model test dialog — chat with GGUF/MLX/ONNX models, optionally speak response via TTS>]}
# [@VBSTYLE]{[@auth<devin>][@role<llm_test_dialog>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{LLMTestDialog — PyQt6 dialog for testing LLM models (GGUF, MLX, ONNX). Chat-style interface. Type a prompt, get a response. Optionally speak the response via Kokoro TTS. Supports mlx_lm (Apple Silicon native) and is extensible to llama.cpp/ollama.}
# [@FILEID]{llm_test_dialog.py}
# [@CLASS]{LLMTestDialog, LLMGenerateThread}
# [@METHOD]{Run, Generate, PopulateModels, OnGenDone, Speak, Clear, SendQuick}

import os
import sys
import time

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTextEdit, QGroupBox,
    QProgressBar, QCheckBox, QSlider, QSpinBox, QMessageBox,
    QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from hardware_detector import HardwareDetector

MLX_MODELS = [
    "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "HuggingFaceTB/SmolLM-135M-Instruct",
    "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "mlx-community/Llama-3.2-3B-Instruct-4bit",
    "mlx-community/Phi-3.5-mini-instruct-4bit",
]

QUICK_PROMPTS = [
    "(pick a prompt)",
    "Say hello in one sentence.",
    "Write a Python function that reverses a string.",
    "Explain what a neural network is in simple terms.",
    "What is 2 + 2?",
    "Write a haiku about coding.",
    "List 3 benefits of using local AI models.",
    "Write a VBStyle class header for a file called test.py.",
]


class LLMGenerateThread(QThread):
    """Background thread — generates text from an LLM model."""
    finished_gen = pyqtSignal(bool, str, str)  # success, response, message
    progress = pyqtSignal(int)

    def __init__(self, model_name, prompt, max_tokens, temperature, backend="mlx"):
        super().__init__()
        self.model_name = model_name
        self.prompt = prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.backend = backend
        self.cancelled = False

    def run(self):
        try:
            self.progress.emit(10)
            if self.backend == "mlx":
                response = self._gen_mlx()
            elif self.backend == "ollama":
                response = self._gen_ollama()
            elif self.backend == "llama_cpp":
                response = self._gen_llama_cpp()
            else:
                self.finished_gen.emit(False, "", "Unknown backend: " + str(self.backend))
                return
            self.progress.emit(90)
            if response:
                self.finished_gen.emit(True, response, "OK")
            else:
                self.finished_gen.emit(False, "", "Empty response")
        except Exception as e:
            self.finished_gen.emit(False, "", str(e))

    def _gen_mlx(self):
        from mlx_lm import load, generate
        self.progress.emit(30)
        model, tokenizer = load(self.model_name)
        self.progress.emit(60)
        messages = [{"role": "user", "content": self.prompt}]
        try:
            prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            prompt_text = self.prompt

        response = generate(
            model, tokenizer,
            prompt=prompt_text,
            max_tokens=self.max_tokens,
            verbose=False
        )
        return response

    def _gen_ollama(self):
        import urllib.request
        import json
        url = "http://localhost:11434/api/generate"
        payload = json.dumps({
            "model": self.model_name,
            "prompt": self.prompt,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens}
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")

    def _gen_llama_cpp(self):
        from llama_cpp import Llama
        llm = Llama(model_path=self.model_name, n_ctx=2048, verbose=False)
        output = llm(
            self.prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            echo=False
        )
        return output["choices"][0]["text"]


class LLMTestDialog(QDialog):
    """Test LLM models — chat-style. Type prompt, get response, optionally speak it."""

    def __init__(self, parent=None, model_id=None, model_info=None):
        super().__init__(parent)
        self.setWindowTitle("Test LLM Model — Chat")
        self.resize(750, 650)
        self.model_id = model_id
        self.model_info = model_info or {}
        self.gen_thread = None
        self.history = []
        self.conversation = []
        self.sysinfo = HardwareDetector()
        self.build_ui()
        self.populate_models()
        self.refresh_system_panel()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Test LLM: " + self.model_info.get("name", "MLX Model"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        if self.model_info.get("description"):
            desc = QLabel(self.model_info["description"])
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #a6adc8; font-size: 12px;")
            layout.addWidget(desc)

        sys_group = QGroupBox("System Resources")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.setContentsMargins(8, 16, 8, 8)
        self.sys_label = QLabel("Detecting...")
        self.sys_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #cdd6f4;")
        sys_layout.addWidget(self.sys_label)

        self.preflight_label = QLabel("")
        self.preflight_label.setWordWrap(True)
        self.preflight_label.setStyleSheet("font-family: monospace; font-size: 11px;")
        sys_layout.addWidget(self.preflight_label)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh_system_panel)
        sys_layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(sys_group)

        config_group = QGroupBox("Model Settings")
        config_layout = QHBoxLayout(config_group)
        config_layout.setContentsMargins(8, 16, 8, 8)

        config_layout.addWidget(QLabel("Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["mlx", "ollama", "llama_cpp"])
        self.backend_combo.currentTextChanged.connect(self.on_backend_changed)
        config_layout.addWidget(self.backend_combo)

        config_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        config_layout.addWidget(self.model_combo, 1)

        config_layout.addWidget(QLabel("Max tokens:"))
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(16, 4096)
        self.tokens_spin.setValue(256)
        config_layout.addWidget(self.tokens_spin)

        layout.addWidget(config_group)

        temp_row = QHBoxLayout()
        temp_row.addWidget(QLabel("Temperature:"))
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 100)
        self.temp_slider.setValue(70)
        self.temp_label = QLabel("0.7")
        self.temp_slider.valueChanged.connect(self.on_temp_changed)
        temp_row.addWidget(self.temp_slider)
        temp_row.addWidget(self.temp_label)
        layout.addLayout(temp_row)

        prompt_group = QGroupBox("Prompt")
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_layout.setContentsMargins(8, 16, 8, 8)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Type a prompt for the model...")
        self.prompt_input.returnPressed.connect(self.on_generate)
        prompt_layout.addWidget(self.prompt_input)

        quick_row = QHBoxLayout()
        quick_lbl = QLabel("Quick test:")
        self.quick_combo = QComboBox()
        self.quick_combo.addItems(QUICK_PROMPTS)
        self.quick_combo.currentTextChanged.connect(self.on_quick_pick)
        quick_row.addWidget(quick_lbl)
        quick_row.addWidget(self.quick_combo, 1)
        prompt_layout.addLayout(quick_row)

        layout.addWidget(prompt_group)

        btn_row = QHBoxLayout()
        self.btn_preflight = QPushButton("Pre-Flight Check")
        self.btn_preflight.setStyleSheet("background-color: #f9e2af; font-weight: bold; padding: 8px 16px;")
        self.btn_preflight.setToolTip("Check backend, model, RAM, and disk before loading")
        self.btn_preflight.clicked.connect(self.on_preflight_check)

        self.btn_generate = QPushButton("Generate")
        self.btn_generate.setStyleSheet("background-color: #89b4fa; font-weight: bold; padding: 8px 20px;")
        self.btn_generate.clicked.connect(self.on_generate)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.on_stop)

        self.btn_speak = QPushButton("Speak Response")
        self.btn_speak.setEnabled(False)
        self.btn_speak.clicked.connect(self.on_speak)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.on_clear)

        btn_row.addWidget(self.btn_preflight)
        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.btn_speak)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_clear)
        layout.addLayout(btn_row)

        self.speak_check = QCheckBox("Auto-speak responses (TTS)")
        self.speak_check.setChecked(False)
        layout.addWidget(self.speak_check)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(14)
        layout.addWidget(self.progress_bar)

        chat_group = QGroupBox("Chat History")
        chat_layout = QVBoxLayout(chat_group)
        chat_layout.setContentsMargins(8, 16, 8, 8)
        self.chat_text = QTextEdit()
        self.chat_text.setReadOnly(True)
        self.chat_text.setStyleSheet("font-family: monospace; font-size: 12px;")
        chat_layout.addWidget(self.chat_text)
        layout.addWidget(chat_group, 1)

        self.info_label = QLabel("Ready")
        self.info_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(self.info_label)

    def populate_models(self):
        self.model_combo.clear()
        backend = self.backend_combo.currentText()
        if backend == "mlx":
            self.model_combo.addItems(MLX_MODELS)
            self.model_combo.setCurrentText(MLX_MODELS[0])
        elif backend == "ollama":
            self.model_combo.addItems(["llama3.2", "qwen2.5-coder", "phi3", "mistral", "gemma2"])
            self.model_combo.setCurrentText("llama3.2")
        elif backend == "llama_cpp":
            self.model_combo.addItems(["(select .gguf file path)"])
            self.model_combo.setCurrentText("")

    def on_backend_changed(self):
        self.populate_models()

    def on_temp_changed(self, value):
        self.temp_label.setText("%.1f" % (value / 100.0))

    def on_quick_pick(self, text):
        if text and text != "(pick a prompt)":
            self.prompt_input.setText(text)

    def on_preflight_check(self):
        """Run pre-flight checks before model load. Shows results in chat area."""
        model_name = self.model_combo.currentText()
        if not model_name or model_name.startswith("("):
            self.info_label.setText("Select or type a model name first")
            return

        backend = self.backend_combo.currentText()
        model_size_mb = self._guess_model_size_mb(backend, model_name)
        self.info_label.setText("Pre-flight checks for %s (%s)..." % (model_name, backend))
        self.add_chat("CHECK", "Pre-flight for %s [%s] — est. %d MB" % (model_name, backend, model_size_mb))

        run_check = self.sysinfo.can_run(model_size_mb)
        dl_check = self.sysinfo.can_download(model_size_mb)

        checks = [
            {"name": "RAM", "pass": run_check["can_run"], "detail": "%d MB available / %d MB needed" % (run_check["available_ram_mb"], run_check["needed_ram_mb"])},
            {"name": "Disk", "pass": dl_check["can_download"], "detail": "%d MB free / %d MB needed" % (dl_check["free_mb"], dl_check["needed_mb"])},
        ]
        summary = self.sysinfo.get_summary()
        checks.append({"name": "CPU", "pass": True, "detail": "%s (%d cores)" % (summary["cpu"], summary["cores"])})
        checks.append({"name": "GPU", "pass": True, "detail": summary["gpu"] + (" (Metal)" if summary["metal"] else "")})
        if summary["neural_engine"]:
            checks.append({"name": "Neural Engine", "pass": True, "detail": "Available"})

        all_pass = True
        for c in checks:
            status = "PASS" if c["pass"] else "FAIL"
            if not c["pass"]:
                all_pass = False
            self.add_chat("CHECK", "  [%s] %s: %s" % (status, c["name"], c["detail"]))

        if all_pass:
            self.add_chat("CHECK", "=== ALL CHECKS PASSED — ready to generate ===")
            self.info_label.setText("Pre-flight: ALL PASS")
        else:
            self.add_chat("ERROR", "=== PRE-FLIGHT FAILED — see failures above ===")
            self.info_label.setText("Pre-flight: ISSUES FOUND")

        self.refresh_system_panel()

    def on_generate(self):
        prompt = self.prompt_input.text().strip()
        if not prompt:
            self.info_label.setText("Type a prompt first")
            return
        model_name = self.model_combo.currentText()
        if not model_name or model_name.startswith("("):
            self.info_label.setText("Select or type a model name")
            return

        backend = self.backend_combo.currentText()

        # AUTO PRE-FLIGHT: check RAM/disk before loading
        model_size_mb = self._guess_model_size_mb(backend, model_name)
        run_check = self.sysinfo.can_run(model_size_mb)
        dl_check = self.sysinfo.can_download(model_size_mb)

        if not run_check["can_run"] or not dl_check["can_download"]:
            fails = []
            if not run_check["can_run"]:
                fails.append("RAM: %d MB available, need %d MB (short %d MB)" % (
                    run_check["available_ram_mb"], run_check["needed_ram_mb"], run_check["shortfall_mb"]))
            if not dl_check["can_download"]:
                fails.append("Disk: %d MB free, need %d MB (short %d MB)" % (
                    dl_check["free_mb"], dl_check["needed_mb"], dl_check["shortfall_mb"]))
            fail_msgs = "\n".join("  [FAIL] " + f for f in fails)
            self.add_chat("ERROR", "Pre-flight FAILED:\n%s" % fail_msgs)
            self.info_label.setText("Pre-flight FAILED — click Pre-Flight Check for details")
            reply = QMessageBox.warning(
                self, "Pre-Flight Check Failed",
                "The following checks failed:\n\n%s\n\nContinue anyway?" % fail_msgs,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.add_chat("CHECK", "User chose to continue despite pre-flight warnings")
        else:
            self.add_chat("CHECK", "Pre-flight OK — loading model...")

        max_tokens = self.tokens_spin.value()
        temperature = self.temp_slider.value() / 100.0

        self.btn_generate.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_speak.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.info_label.setText("Generating with %s (%s)..." % (model_name, backend))

        self.add_chat("YOU", prompt)
        self.conversation.append({"role": "user", "content": prompt})

        self.gen_thread = LLMGenerateThread(model_name, prompt, max_tokens, temperature, backend)
        self.gen_thread.finished_gen.connect(self.on_gen_done)
        self.gen_thread.progress.connect(self.progress_bar.setValue)
        self.gen_thread.start()

    def on_gen_done(self, success, response, message):
        self.progress_bar.setVisible(False)
        self.btn_generate.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if not success:
            self.info_label.setText("Error: " + message[:100])
            self.add_chat("ERROR", message)
            return

        self.add_chat("AI", response)
        self.conversation.append({"role": "assistant", "content": response})
        self.last_response = response
        self.btn_speak.setEnabled(True)
        elapsed = "done"
        self.info_label.setText("Response: %d chars  |  %s" % (len(response), elapsed))

        if self.speak_check.isChecked():
            self.on_speak()

    def on_speak(self):
        response = getattr(self, "last_response", "")
        if not response:
            return
        self.info_label.setText("Speaking response via Kokoro TTS...")
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voice_pipeline"))
            from ToneSynthesizer import ToneSynthesizer
            synth = ToneSynthesizer()
            ok, result, err = synth.Run("speak", {"text": response[:500], "voice": "af_bella", "play": True})
            if ok:
                self.info_label.setText("Spoke response (%d chars)" % min(len(response), 500))
            else:
                self.info_label.setText("TTS error: " + str(err))
        except Exception as e:
            self.info_label.setText("TTS unavailable: " + str(e)[:80])

    def on_stop(self):
        if self.gen_thread and self.gen_thread.isRunning():
            self.gen_thread.cancelled = True
        self.progress_bar.setVisible(False)
        self.btn_generate.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.info_label.setText("Stopped")

    def on_clear(self):
        self.history = []
        self.conversation = []
        self.chat_text.clear()

    def add_chat(self, role, text):
        ts = time.strftime("%H:%M:%S")
        if role == "YOU":
            prefix = ">>> "
            color = "#89b4fa"
        elif role == "AI":
            prefix = "<<< "
            color = "#a6e3a1"
        elif role == "CHECK":
            prefix = "[CHK] "
            color = "#f9e2af"
        else:
            prefix = "!!! "
            color = "#f38ba8"
        line = '<span style="color: %s;">[%s] %s%s</span>' % (color, ts, prefix, text.replace("<", "&lt;").replace("\n", "<br>"))
        self.chat_text.append(line)

    def _guess_model_size_mb(self, backend, model_name):
        """Estimate model size in MB from name for RAM/disk checks."""
        name_lower = model_name.lower()
        if "135m" in name_lower:
            return 300
        if "1.5b" in name_lower or "1b" in name_lower:
            return 1500
        if "3b" in name_lower:
            return 3000
        if "7b" in name_lower:
            return 4000
        if "8b" in name_lower:
            return 4500
        if "13b" in name_lower:
            return 7000
        if "70b" in name_lower:
            return 35000
        if "kokoro" in name_lower or "82m" in name_lower:
            return 200
        return 2000

    def refresh_system_panel(self):
        """Refresh the system resources display using HardwareDetector."""
        summary = self.sysinfo.get_summary()
        ramAvail = summary.get("ram_available_mb", 0)
        ramTotal = summary.get("ram_total_mb", 0)
        diskFree = summary.get("disk_free_mb", 0)
        lines = []
        lines.append("Chip:  %s (%d cores)" % (summary.get("cpu", "?"), summary.get("cores", 0)))
        lines.append("RAM:   %.1f GB free / %.1f GB total" % (ramAvail / 1024.0, ramTotal / 1024.0))
        lines.append("Disk:  %.1f GB free" % (diskFree / 1024.0))
        gpu = summary.get("gpu", "None")
        if summary.get("metal"):
            gpu = gpu + " (Metal)"
        if summary.get("neural_engine"):
            gpu = gpu + " + ANE"
        lines.append("GPU:   %s" % gpu)
        self.sys_label.setText("<br>".join(lines))

        model_name = self.model_combo.currentText()
        backend = self.backend_combo.currentText()
        if model_name and not model_name.startswith("("):
            model_size_mb = self._guess_model_size_mb(backend, model_name)
            run_check = self.sysinfo.can_run(model_size_mb)
            dl_check = self.sysinfo.can_download(model_size_mb)
            if run_check["can_run"] and dl_check["can_download"]:
                self.preflight_label.setText("<span style='color: #a6e3a1;'>CAN LOAD — %.1f GB RAM free, %.1f GB disk free (need %d MB RAM, %d MB disk)</span>" % (
                    ramAvail / 1024.0, diskFree / 1024.0, run_check["needed_ram_mb"], dl_check["needed_mb"]))
            else:
                fails = []
                if not run_check["can_run"]:
                    fails.append("RAM short %d MB" % run_check["shortfall_mb"])
                if not dl_check["can_download"]:
                    fails.append("Disk short %d MB" % dl_check["shortfall_mb"])
                self.preflight_label.setText("<span style='color: #f38ba8;'>CANNOT LOAD — %s</span>" % " | ".join(fails))

    def closeEvent(self, event):
        if self.gen_thread and self.gen_thread.isRunning():
            self.gen_thread.cancelled = True
        super().closeEvent(event)
