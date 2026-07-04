#!/usr/bin/env python3
"""
SVG Engine ↔ QA Engine Bridge
Connects the animated wizard SVG frontend to the GhostQAEngine backend.
The wizard can ask questions, get answers, and display results as speech bubbles in the SVG scene.
"""

import sys
import os
import time
import json

# Add qa_engine to path
QA_ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qa_engine")
sys.path.insert(0, QA_ENGINE_DIR)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTextEdit, QGroupBox, QComboBox, QFrame, QCheckBox,
    QFormLayout, QTabWidget, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QByteArray, QTimer, pyqtSignal, QThread
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QFont

# Import the SVG engine (same folder)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wizard_scene_editor import WizardEngine, THEME_PRESETS, StyleHelper


class QABridge:
    """Bridge to GhostQAEngine — lazy-loaded, graceful degradation."""

    def __init__(self):
        self._engine = None
        self._available = None
        self._error = None

    @property
    def available(self):
        if self._available is None:
            self._try_init()
        return self._available

    def _try_init(self):
        try:
            from GhostQAEngine import GhostQAEngine
            self._engine = GhostQAEngine()
            ok, data, err = self._engine.Run("init", {
                "config_path": os.path.join(QA_ENGINE_DIR, "qa_engine_config.json"),
            })
            if ok:
                self._available = True
                self._error = None
                self._init_data = data
                # Check which models actually loaded
                ok2, models, _ = self._engine.Run("read_state")
                if ok2:
                    loaded = models.get("meta", {}).get("loaded_models", {})
                    self._loaded_models = list(loaded.keys())
                    self._init_errors = models.get("errors", [])
            else:
                self._available = False
                self._error = f"Init failed: {err}"
        except Exception as e:
            self._available = False
            self._error = str(e)

    def ask(self, question, context=""):
        if not self.available:
            return {
                "answer": f"QA engine offline: {self._error}",
                "confidence": 0.0,
                "mode": "UNAVAILABLE",
                "found": False,
            }
        # Mode E: direct QA with context (no retrieval needed)
        # Mode B: retrieval + QA (needs Qdrant + embedding model)
        # Mode is overridden by toolbar selection
        params = {"question": question}
        if context and len(context.strip()) > 10:
            # Use Mode E for direct context QA
            params["pipeline_mode"] = "E"
            params["context"] = context
        ok, data, err = self._engine.Run("ask", params)
        if ok:
            return data
        # Graceful error message
        err_str = str(err)
        if "QA model not available" in err_str:
            return {
                "answer": "My BERT QA model failed to load. Check the model path in qa_engine_config.json. The .mlmodel file must exist.",
                "confidence": 0.0,
                "mode": "MODEL_ERROR",
                "found": False,
                "error": err_str,
            }
        if "Tokenizer not loaded" in err_str:
            return {
                "answer": "My tokenizer failed to load. Need transformers BertTokenizer.",
                "confidence": 0.0,
                "mode": "TOKENIZER_ERROR",
                "found": False,
                "error": err_str,
            }
        return {
            "answer": f"Error: {err_str}",
            "confidence": 0.0,
            "mode": "ERROR",
            "found": False,
            "error": err_str,
        }

    def status(self):
        if self._available is None:
            self._try_init()
        if self._available:
            models = getattr(self, '_loaded_models', [])
            if models:
                return f"Connected ({len(models)} models)", "#4CAF50"
            return "Connected (no models)", "#FF9800"
        return "Offline", "#f44336"


class QASpeechBubble:
    """Generates SVG speech bubble markup to overlay on the wizard scene."""

    @staticmethod
    def render_bubble(x, y, text, w=300, h=80, color="#1a1a2e", text_color="#fff"):
        """Generate SVG for a speech bubble at (x,y)."""
        # Escape XML
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        # Wrap text at ~40 chars
        lines = []
        words = safe.split()
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > 45:
                lines.append(current)
                current = word
            else:
                current = (current + " " + word).strip()
        if current:
            lines.append(current)
        lines = lines[:4]  # max 4 lines

        text_elements = ""
        for i, line in enumerate(lines):
            ly = y + 20 + i * 16
            text_elements += f'<text x="{x + 15}" y="{ly}" fill="{text_color}" font-family="Arial" font-size="13" font-weight="normal">{line}</text>'

        return f"""
<g class="speech-bubble">
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{color}" stroke="#555" stroke-width="1" opacity="0.95"/>
  <path d="M{x + 30} {y + h} L{x + 50} {y + h + 15} L{x + 60} {y + h} Z" fill="{color}" stroke="#555" stroke-width="1"/>
  {text_elements}
</g>"""

    @staticmethod
    def render_thinking(x, y, color="#1a1a2e"):
        """Animated thinking dots."""
        dots = ""
        for i in range(3):
            delay = i * 0.3
            dy = y + 25
            dx = x + 20 + i * 20
            dots += f"""
<circle cx="{dx}" cy="{dy}" r="6" fill="#7ec8ff" opacity="0.6">
  <animate attributeName="cy" values="{dy};{dy-10};{dy}" dur="1s" repeatCount="indefinite" begin="{delay}s"/>
  <animate attributeName="opacity" values="0.3;1;0.3" dur="1s" repeatCount="indefinite" begin="{delay}s"/>
</circle>"""
        return f"""
<g class="thinking">
  <rect x="{x}" y="{y}" width="100" height="50" rx="12" fill="{color}" stroke="#555" stroke-width="1" opacity="0.95"/>
  <path d="M{x + 30} {y + 50} L{x + 45} {y + 65} L{x + 55} {y + 50} Z" fill="{color}" stroke="#555" stroke-width="1"/>
  {dots}
</g>"""


class QAQueryThread(QThread):
    """Runs QA query in background thread to keep UI responsive."""
    finished = pyqtSignal(dict)

    def __init__(self, bridge, question, context=""):
        super().__init__()
        self.bridge = bridge
        self.question = question
        self.context = context

    def run(self):
        result = self.bridge.ask(self.question, self.context)
        self.finished.emit(result)


class WizardQAUI(QMainWindow):
    """Wizard SVG + QA Engine — the wizard talks back."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("\U0001f9d9 Wizard SVG Engine + QA Bridge")
        self.setMinimumSize(1000, 750)
        self.setStyleSheet(StyleHelper.dark())

        self.engine = WizardEngine()
        self.qa_bridge = QABridge()
        self.playing = True
        self.time = 0.0
        self.speed = 1.0
        self.loop = True
        self.last_frame = time.time()
        self.frame_count = 0
        self.fps = 0.0
        self.fps_timer = time.time()
        self.qa_thread = None
        self.bubble_text = ""
        self.bubble_timer = 0
        self.thinking = False
        self._settings_dirty = False  # pending QA settings awaiting Apply

        self._build_ui()
        self._start_timer()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setSpacing(8)
        main.setContentsMargins(10, 10, 10, 10)

        # ─── Left: SVG Preview ───
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(6)

        title = QLabel("\U0001f9d9 Wizard SVG Engine — Live + QA")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFD700;")
        left_layout.addWidget(title)

        self.svg_widget = QSvgWidget()
        self.svg_widget.setFixedSize(512, 512)
        self.svg_widget.setStyleSheet("border: 2px solid #333; border-radius: 12px; background: #000;")
        left_layout.addWidget(self.svg_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Theme selector
        theme_row = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet("color: #888;")
        theme_row.addWidget(theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEME_PRESETS.keys())
        self.theme_combo.currentTextChanged.connect(self._load_preset)
        theme_row.addWidget(self.theme_combo)
        left_layout.addLayout(theme_row)

        # Playback
        pb_row = QHBoxLayout()
        self.play_btn = QPushButton("Pause")
        self.play_btn.setStyleSheet(StyleHelper.btn("#2196F3"))
        self.play_btn.clicked.connect(self._toggle_play)
        pb_row.addWidget(self.play_btn)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setStyleSheet(StyleHelper.btn("#FF9800"))
        self.reset_btn.clicked.connect(lambda: setattr(self, 'time', 0.0))
        pb_row.addWidget(self.reset_btn)
        left_layout.addLayout(pb_row)

        main.addWidget(left)

        # ─── Right: QA Panel ───
        right = QWidget()
        right.setFixedWidth(420)
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(8)

        # QA Status
        qa_title = QLabel("\U0001f4ac QA Engine Bridge")
        qa_title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        qa_title.setStyleSheet("color: #FFD700;")
        right_layout.addWidget(qa_title)

        status_row = QHBoxLayout()
        status_label = QLabel("Engine Status:")
        status_label.setStyleSheet("color: #888;")
        status_row.addWidget(status_label)
        self.qa_status = QLabel("Checking...")
        self.qa_status.setStyleSheet("color: #FF9800; font-weight: bold;")
        status_row.addWidget(self.qa_status)
        right_layout.addLayout(status_row)

        # ─── QA Settings Toolbar ───
        settings_group = QGroupBox("QA Engine Settings")
        settings_layout = QFormLayout(settings_group)
        settings_layout.setSpacing(4)

        # Pipeline mode
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "A — Retrieval Only",
            "B — Retrieval + QA",
            "C — Retrieval + QA + LLM",
            "D — Retrieval + LLM",
            "E — QA Only (needs context)",
            "R — Routed Auto",
        ])
        self.mode_combo.setCurrentIndex(1)  # Mode B default
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        settings_layout.addRow("Pipeline:", self.mode_combo)

        # Embedding model
        self.emb_combo = QComboBox()
        self.emb_combo.addItems([
            "bge_small", "bge_small_mlx", "minilm_l12",
            "token_embedder", "codebert", "bge_m3_mlx",
        ])
        self.emb_combo.currentTextChanged.connect(self._on_model_changed)
        settings_layout.addRow("Embedding:", self.emb_combo)

        # QA model
        self.qa_combo = QComboBox()
        self.qa_combo.addItems(["bert_squad_fp16", "bert_squad_int8"])
        self.qa_combo.currentTextChanged.connect(self._on_model_changed)
        settings_layout.addRow("QA Model:", self.qa_combo)

        # LLM enable
        self.llm_check = QCheckBox("Enable LLM (Qwen2.5-Coder)")
        self.llm_check.setChecked(True)
        self.llm_check.stateChanged.connect(self._on_model_changed)
        settings_layout.addRow("LLM:", self.llm_check)

        # Vector backend
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["qdrant", "faiss", "sqlite_vector", "ram"])
        self.backend_combo.currentTextChanged.connect(self._on_model_changed)
        settings_layout.addRow("Vector Backend:", self.backend_combo)

        # Execution mode
        self.exec_combo = QComboBox()
        self.exec_combo.addItems(["auto", "cpu", "gpu", "hybrid"])
        self.exec_combo.currentTextChanged.connect(self._on_model_changed)
        settings_layout.addRow("Execution:", self.exec_combo)

        # Top-K
        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 50); self.topk_spin.setValue(5)
        self.topk_spin.valueChanged.connect(self._on_model_changed)
        settings_layout.addRow("Top-K:", self.topk_spin)

        # Confidence threshold
        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0, 100); self.conf_spin.setSingleStep(0.5); self.conf_spin.setValue(0.0)
        self.conf_spin.valueChanged.connect(self._on_model_changed)
        settings_layout.addRow("Confidence Threshold:", self.conf_spin)

        # Apply button
        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.setStyleSheet(StyleHelper.btn("#FF9800"))
        self.apply_btn.clicked.connect(self._apply_settings)
        settings_layout.addRow("", self.apply_btn)

        right_layout.addWidget(settings_group)

        # Check QA engine availability after window loads
        QTimer.singleShot(1000, self._check_qa_status)

        # Question input
        q_group = QGroupBox("Ask the Wizard")
        q_layout = QVBoxLayout(q_group)

        q_label = QLabel("Your question:")
        q_label.setStyleSheet("color: #aaa;")
        q_layout.addWidget(q_label)

        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Ask a question...")
        self.question_input.returnPressed.connect(self._ask_question)
        self.question_input.setStyleSheet("QLineEdit { background: #1a1a2e; color: #fff; border: 2px solid #2196F3; padding: 8px; border-radius: 6px; font-size: 13px; }")
        q_layout.addWidget(self.question_input)

        ctx_label = QLabel("Context (optional, for Mode E):")
        ctx_label.setStyleSheet("color: #aaa; font-size: 11px;")
        q_layout.addWidget(ctx_label)

        self.context_input = QTextEdit()
        self.context_input.setMaximumHeight(80)
        self.context_input.setPlaceholderText("Paste context text for direct QA...")
        q_layout.addWidget(self.context_input)

        ask_row = QHBoxLayout()
        self.ask_btn = QPushButton("\U0001f9d9  Ask Wizard")
        self.ask_btn.setStyleSheet(StyleHelper.btn("#4CAF50"))
        self.ask_btn.clicked.connect(self._ask_question)
        ask_row.addWidget(self.ask_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(StyleHelper.btn("#9E9E9E"))
        self.clear_btn.clicked.connect(self._clear_chat)
        ask_row.addWidget(self.clear_btn)
        q_layout.addLayout(ask_row)

        right_layout.addWidget(q_group)

        # Chat history
        chat_group = QGroupBox("Conversation")
        chat_layout = QVBoxLayout(chat_group)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background: #0a0a14;
                color: #ccc;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Menlo', monospace;
                font-size: 12px;
            }
        """)
        chat_layout.addWidget(self.chat_display)
        right_layout.addWidget(chat_group)

        # Info
        info = QLabel(
            "The wizard SVG is rendered by the C engine (libwizard.dylib).\n"
            "Questions are routed through GhostQAEngine (BERT SQuAD CoreML).\n"
            "Answers appear as speech bubbles on the wizard + in the chat log."
        )
        info.setStyleSheet("color: #666; font-size: 11px; padding: 8px;")
        info.setWordWrap(True)
        right_layout.addWidget(info)

        main.addWidget(right)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("QStatusBar { background: #0a0a14; color: #888; }")

    def _check_qa_status(self):
        status_text, color = self.qa_bridge.status()
        self.qa_status.setText(status_text)
        self.qa_status.setStyleSheet(f"color: {color}; font-weight: bold;")
        # Show loaded models and any init errors
        if hasattr(self.qa_bridge, '_loaded_models') and self.qa_bridge._loaded_models:
            models = ", ".join(self.qa_bridge._loaded_models)
            self.chat_display.append(f'<i style="color:#666">Loaded models: {models}</i>')
        if hasattr(self.qa_bridge, '_init_errors') and self.qa_bridge._init_errors:
            for e in self.qa_bridge._init_errors[-3:]:
                self.chat_display.append(f'<i style="color:#f44336">Init error: {e}</i>')
        if hasattr(self.qa_bridge, '_init_data') and self.qa_bridge._init_data:
            d = self.qa_bridge._init_data
            self.chat_display.append(
                f'<i style="color:#666">Backend: {d.get("backend","?")} | '
                f'Embedding: {d.get("embedding_model","?")} | '
                f'QA: {d.get("qa_model","?")} | '
                f'LLM: {d.get("llm_model","?")}</i>'
            )

    def _ask_question(self):
        question = self.question_input.text().strip()
        if not question:
            return
        context = self.context_input.toPlainText().strip()

        # Show thinking bubble
        self.thinking = True
        self.bubble_text = ""
        self.ask_btn.setEnabled(False)
        self.ask_btn.setText("Thinking...")

        # Add to chat
        self.chat_display.append(f'<b style="color:#7ec8ff">You:</b> {question}')

        # Run QA in background
        self.qa_thread = QAQueryThread(self.qa_bridge, question, context)
        self.qa_thread.finished.connect(self._on_qa_result)
        self.qa_thread.start()

    def _on_qa_result(self, result):
        self.thinking = False
        self.ask_btn.setEnabled(True)
        self.ask_btn.setText("\U0001f9d9  Ask Wizard")

        answer = result.get("answer", "No answer")
        confidence = result.get("confidence", 0.0)
        mode = result.get("mode", "UNKNOWN")
        found = result.get("found", False)

        # Show speech bubble for 8 seconds
        self.bubble_text = answer
        self.bubble_timer = time.time() + 8.0

        # Add to chat log
        color = "#4CAF50" if found else "#FF9800"
        self.chat_display.append(
            f'<b style="color:{color}">Wizard:</b> {answer}\n'
            f'<span style="color:#666">  [confidence: {confidence:.2f} | mode: {mode}]</span>'
        )

        self.status_bar.showMessage(
            f"Answer: confidence={confidence:.2f} mode={mode}  |  "
            f"QA: {self.qa_bridge.status()[0]}", 5000
        )

    def _clear_chat(self):
        self.chat_display.clear()
        self.bubble_text = ""
        self.bubble_timer = 0

    def _load_preset(self, name):
        self.engine.load_preset(name)

    # ─── QA Settings ───

    def _on_mode_changed(self):
        """Pipeline mode changed in dropdown.

        The change is staged but not applied immediately — the user must
        click the Apply button (``_apply_settings``) to commit it to the
        engine config. We mark settings dirty and hint via the status bar.
        """
        self._settings_dirty = True
        mode_map = {0: "A", 1: "B", 2: "C", 3: "D", 4: "E", 5: "R"}
        mode = mode_map.get(self.mode_combo.currentIndex(), "B")
        self.status_bar.showMessage(
            f"Pipeline mode set to {mode} — click Apply to activate"
        )

    def _on_model_changed(self):
        """Model/backend setting changed.

        Like ``_on_mode_changed``, the change is staged until the Apply
        button is pressed. We mark settings dirty and hint via the status
        bar so the user knows a reload is pending.
        """
        self._settings_dirty = True
        self.status_bar.showMessage(
            "QA settings changed — click Apply to activate"
        )

    def _apply_settings(self):
        """Apply all QA settings to the engine config and reload."""
        if not self.qa_bridge.available:
            self.chat_display.append('<i style="color:#f44336">QA engine not available — cannot apply settings</i>')
            return

        mode_map = {0: "A", 1: "B", 2: "C", 3: "D", 4: "E", 5: "R"}
        mode = mode_map.get(self.mode_combo.currentIndex(), "B")
        emb = self.emb_combo.currentText()
        qa_model = self.qa_combo.currentText()
        llm_on = self.llm_check.isChecked()
        backend = self.backend_combo.currentText()
        exec_mode = self.exec_combo.currentText()
        topk = self.topk_spin.value()
        conf_thresh = self.conf_spin.value()

        # Update config in the engine's state
        cfg = self.qa_bridge._engine.state.get("config", {})
        if not cfg:
            self.chat_display.append('<i style="color:#f44336">No config loaded in engine</i>')
            return

        cfg.setdefault("pipeline", {})["mode"] = mode
        cfg.setdefault("models", {}).setdefault("embedding", {})["active"] = emb
        cfg.setdefault("models", {}).setdefault("qa", {})["active"] = qa_model
        cfg.setdefault("models", {}).setdefault("llm", {})["enabled"] = llm_on
        cfg.setdefault("storage", {})["vector_backend"] = backend
        cfg.setdefault("hardware", {})["execution_mode"] = exec_mode
        cfg.setdefault("retrieval", {})["top_k"] = topk
        cfg.setdefault("classification", {})["true_threshold"] = conf_thresh

        self.qa_bridge._engine.state["config"] = cfg

        mode_names = {
            "A": "Retrieval Only", "B": "Retrieval + QA",
            "C": "Retrieval + QA + LLM", "D": "Retrieval + LLM",
            "E": "QA Only", "R": "Routed Auto",
        }
        self.chat_display.append(
            f'<i style="color:#4CAF50">Settings applied: Mode {mode} ({mode_names.get(mode,"?")}) | '
            f'Emb: {emb} | QA: {qa_model} | LLM: {"on" if llm_on else "off"} | '
            f'Backend: {backend} | Exec: {exec_mode} | Top-K: {topk}</i>'
        )

        # If mode changed to E, remind about context
        if mode == "E":
            self.chat_display.append(
                '<i style="color:#FF9800">Mode E requires context text — paste it in the context box below.</i>'
            )

        # Settings are now committed — clear the pending flag
        self._settings_dirty = False
        self.status_bar.showMessage("QA settings applied", 5000)

    def _toggle_play(self):
        self.playing = not self.playing
        self.play_btn.setText("Pause" if self.playing else "Play")
        if self.playing and self.time >= 1.0:
            self.time = 0.0

    def _start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    def _tick(self):
        now = time.time()
        dt = now - self.last_frame
        self.last_frame = now

        if self.playing:
            self.time += dt * self.speed * 0.5
            if self.time >= 1.0:
                self.time = self.time % 1.0 if self.loop else 1.0

        # Render base SVG from C engine
        svg_bytes = self.engine.render(self.time)
        if not svg_bytes:
            return

        svg_str = svg_bytes.decode("utf-8", errors="replace")

        # Inject speech bubble or thinking animation before </svg>
        bubble_svg = ""
        if self.thinking:
            bubble_svg = QASpeechBubble.render_thinking(340, 100)
        elif self.bubble_text and now < self.bubble_timer:
            bubble_svg = QASpeechBubble.render_bubble(280, 80, self.bubble_text, w=300, h=90)
        elif self.bubble_text and now >= self.bubble_timer:
            self.bubble_text = ""

        if bubble_svg:
            svg_str = svg_str.replace("</svg>", bubble_svg + "</svg>")

        self.svg_widget.load(QByteArray(svg_str.encode("utf-8")))

        # FPS
        self.frame_count += 1
        if now - self.fps_timer >= 1.0:
            self.fps = self.frame_count / (now - self.fps_timer)
            self.frame_count = 0
            self.fps_timer = now

        self.status_bar.showMessage(
            f"t={self.time:.3f}  |  FPS: {self.fps:.0f}  |  "
            f"Objects: {self.engine.get_obj_count()}  |  "
            f"QA: {self.qa_bridge.status()[0]}"
        )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wizard SVG Engine + QA Bridge")
    w = WizardQAUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
