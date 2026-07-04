#!/usr/bin/env python3
# [@GHOST]{[@file<model_chat.py>][@domain<ModelControlCenter>][@role<chat>][@auth<devin>][@date<2026-07-04>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<chat>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{ModelChatDialog — PyQt6 chat window for testing LLM models. Supports MLX (local), Ollama (HTTP API), and OpenAI-compatible APIs. Streaming responses, message history, model status indicator.}

import json
import urllib.request
import urllib.error
import subprocess
import sys
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QComboBox, QStatusBar, QProgressBar,
    QFrame, QScrollArea, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QTextCursor


class ChatWorker(QThread):
    """Background thread for LLM inference — streaming chunks."""
    chunk_ready = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, provider, model_path, messages, temperature, max_tokens):
        super().__init__()
        self.provider = provider
        self.model_path = model_path
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens

    def run(self):
        if self.provider == "mlx":
            self.run_mlx()
        elif self.provider == "ollama":
            self.run_ollama()
        elif self.provider == "openai_api":
            self.run_openai_api()
        else:
            self.error_occurred.emit("Unknown provider: %s" % self.provider)

    def run_mlx(self):
        try:
            import mlx_lm
            self.chunk_ready.emit("[Loading model %s...]\n" % self.model_path)
            model, tokenizer = mlx_lm.load(self.model_path)
            self.chunk_ready.emit("[Model loaded. Generating...]\n")

            prompt = self.messages[-1]["content"] if self.messages else "Hello"
            response_text = ""
            for chunk in mlx_lm.generate(
                model, tokenizer, prompt=prompt,
                max_tokens=self.max_tokens, temp=self.temperature
            ):
                if chunk:
                    response_text += chunk
                    self.chunk_ready.emit(chunk)
            self.finished_ok.emit(response_text)
        except ImportError:
            self.error_occurred.emit("mlx_lm not installed. Run: pip3 install mlx-lm")
        except Exception as e:
            self.error_occurred.emit("MLX error: %s" % str(e))

    def run_ollama(self):
        try:
            url = "http://localhost:11434/api/chat"
            payload = json.dumps({
                "model": self.model_path,
                "messages": self.messages,
                "stream": True,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens
                }
            }).encode("utf-8")

            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"}
            )

            response_text = ""
            with urllib.request.urlopen(req, timeout=60) as resp:
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        chunk = data["message"]["content"]
                        response_text += chunk
                        self.chunk_ready.emit(chunk)
                    if data.get("done"):
                        break
            self.finished_ok.emit(response_text)
        except urllib.error.URLError:
            self.error_occurred.emit("Cannot connect to Ollama at localhost:11434. Is it running?")
        except Exception as e:
            self.error_occurred.emit("Ollama error: %s" % str(e))

    def run_openai_api(self):
        try:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                self.error_occurred.emit("OPENAI_API_KEY not set in environment")
                return

            url = "https://api.openai.com/v1/chat/completions"
            payload = json.dumps({
                "model": self.model_path,
                "messages": self.messages,
                "stream": True,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }).encode("utf-8")

            req = urllib.request.Request(
                url, data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer %s" % api_key
                }
            )

            response_text = ""
            with urllib.request.urlopen(req, timeout=60) as resp:
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    data = json.loads(data_str)
                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            chunk = delta["content"]
                            response_text += chunk
                            self.chunk_ready.emit(chunk)
            self.finished_ok.emit(response_text)
        except Exception as e:
            self.error_occurred.emit("API error: %s" % str(e))


class ModelChatDialog(QDialog):
    """Chat window for testing LLM models — streaming responses, message history."""

    def __init__(self, parent, model_name, model_path, provider, theme):
        super().__init__(parent)
        self.theme = theme
        self.model_name = model_name
        self.model_path = model_path
        self.provider = provider
        self.messages = []
        self.worker = None
        self.is_generating = False

        self.setWindowTitle("Chat — %s (%s)" % (model_name, provider.upper()))
        self.resize(800, 600)
        self.setStyleSheet(self.build_chat_style(theme))
        self.build_ui()

    def build_chat_style(self, t):
        return """
        QDialog { background-color: %s; }
        QTextEdit { background-color: %s; color: %s; border: 1px solid %s; border-radius: 6px; font-size: 14px; }
        QLineEdit { background-color: %s; color: %s; border: 1px solid %s; border-radius: 4px; padding: 8px; font-size: 14px; }
        QPushButton { background-color: %s; color: %s; border: 1px solid %s; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
        QPushButton:hover { background-color: %s; }
        QPushButton:disabled { background-color: %s; color: %s; }
        QLabel { color: %s; }
        QStatusBar { background-color: %s; color: %s; border-top: 1px solid %s; }
        QProgressBar { border: 1px solid %s; border-radius: 3px; text-align: center; background-color: %s; }
        QProgressBar::chunk { background-color: %s; border-radius: 2px; }
        QComboBox { background-color: %s; color: %s; border: 1px solid %s; border-radius: 4px; padding: 5px; }
        """ % (
            t["bg"], t["surface"], t["text"], t["border"],
            t["surface"], t["text"], t["border"],
            t["surface"], t["text"], t["border"],
            t["primary"],
            t["bg"], t["text_dim"],
            t["text"],
            t["surface"], t["text_dim"], t["border"],
            t["border"], t["surface"],
            t["primary"],
            t["surface"], t["text"], t["border"],
        )

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel("Model: %s  |  Provider: %s  |  Path: %s" % (
            self.model_name, self.provider.upper(), self.model_path or "N/A"
        ))
        header.setStyleSheet("color: %s; font-weight: bold;" % self.theme["primary"])
        layout.addWidget(header)

        provider_label = QLabel("Backend:")
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("MLX (Apple Silicon)", "mlx")
        self.provider_combo.addItem("Ollama (HTTP API)", "ollama")
        self.provider_combo.addItem("OpenAI-compatible API", "openai_api")
        if self.provider == "mlx":
            self.provider_combo.setCurrentIndex(0)
        elif self.provider == "ollama":
            self.provider_combo.setCurrentIndex(1)
        else:
            self.provider_combo.setCurrentIndex(2)
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)

        provider_row = QHBoxLayout()
        provider_row.addWidget(provider_label)
        provider_row.addWidget(self.provider_combo)
        provider_row.addStretch()
        layout.addLayout(provider_row)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Menlo", 13))
        welcome_msg = "=== Chat Test Window ===\n"
        welcome_msg += "Model: %s\n" % self.model_name
        welcome_msg += "Provider: %s\n" % self.provider.upper()
        welcome_msg += "Type a message below and press Enter or click Send.\n"
        welcome_msg += "The model will respond with streaming output.\n\n"
        self.chat_display.setPlainText(welcome_msg)
        layout.addWidget(self.chat_display, 1)

        input_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message here...")
        self.input_field.returnPressed.connect(self.on_send)
        self.btn_send = QPushButton("Send")
        self.btn_send.clicked.connect(self.on_send)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setEnabled(False)

        input_row.addWidget(self.input_field, 1)
        input_row.addWidget(self.btn_send)
        input_row.addWidget(self.btn_stop)
        input_row.addWidget(self.btn_clear)
        layout.addLayout(input_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready — type a message to test the model")
        layout.addWidget(self.status_bar)

    def on_provider_changed(self):
        idx = self.provider_combo.currentIndex()
        self.provider = self.provider_combo.itemData(idx)
        self.status_bar.showMessage("Provider switched to: %s" % self.provider.upper())

    def on_send(self):
        text = self.input_field.text().strip()
        if not text or self.is_generating:
            return

        self.messages.append({"role": "user", "content": text})

        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)
        self.chat_display.insertPlainText("\n[YOU]: %s\n" % text)
        self.chat_display.insertPlainText("\n[%s]: " % self.model_name.upper())
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)

        self.input_field.clear()
        self.is_generating = True
        self.btn_send.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Generating response...")

        self.worker = ChatWorker(
            self.provider, self.model_path,
            self.messages, temperature=0.7, max_tokens=512
        )
        self.worker.chunk_ready.connect(self.on_chunk)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def on_chunk(self, chunk):
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)
        self.chat_display.insertPlainText(chunk)
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def on_finished(self, full_response):
        self.is_generating = False
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.messages.append({"role": "assistant", "content": full_response})
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)
        self.chat_display.insertPlainText("\n")
        self.status_bar.showMessage("Response complete (%d chars)" % len(full_response))

    def on_error(self, error_msg):
        self.is_generating = False
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)
        self.chat_display.insertPlainText("\n[ERROR]: %s\n" % error_msg)
        self.status_bar.showMessage("Error: %s" % error_msg)

    def on_stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.is_generating = False
            self.btn_send.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.progress_bar.setVisible(False)
            self.chat_display.moveCursor(QTextCursor.MoveOperation.End)
            self.chat_display.insertPlainText("\n[STOPPED]\n")
            self.status_bar.showMessage("Generation stopped")

    def on_clear(self):
        self.messages = []
        self.chat_display.clear()
        self.chat_display.setPlainText("=== Chat cleared ===\n\n")
        self.status_bar.showMessage("Chat history cleared")
