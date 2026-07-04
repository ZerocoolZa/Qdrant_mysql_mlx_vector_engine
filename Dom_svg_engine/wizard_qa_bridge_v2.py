#!/usr/bin/env python3
"""
SVG Engine ↔ QA Engine Bridge
VS Code-style layout: activity bar (icons) + expandable side panel + bottom chat bar.
All GUI settings driven by Config_svg_engine.py — no hardcoded values.
"""

import sys
import os
import time

# Add paths
QA_ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qa_engine")
sys.path.insert(0, QA_ENGINE_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTextEdit, QGroupBox, QComboBox, QFrame, QCheckBox,
    QFormLayout, QSplitter, QScrollArea, QSpinBox, QDoubleSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QByteArray, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QFont, QAction

from Config_svg_engine import cfg
from wizard_scene_editor import WizardEngine


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
                "config_path": cfg.paths["qa_config"],
            })
            if ok:
                self._available = True
                self._error = None
                self._init_data = data
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
                "answer": cfg.ERROR_QA_OFFLINE.format(error=self._error),
                "confidence": 0.0, "mode": "UNAVAILABLE", "found": False,
            }
        params = {"question": question}
        if context and len(context.strip()) > 10:
            params["pipeline_mode"] = "E"
            params["context"] = context
        ok, data, err = self._engine.Run("ask", params)
        if ok:
            return data
        err_str = str(err)
        if "QA model not available" in err_str:
            return {"answer": cfg.ERROR_MODEL_LOAD, "confidence": 0.0, "mode": "MODEL_ERROR", "found": False, "error": err_str}
        if "Tokenizer not loaded" in err_str:
            return {"answer": cfg.ERROR_TOKENIZER, "confidence": 0.0, "mode": "TOKENIZER_ERROR", "found": False, "error": err_str}
        return {"answer": f"Error: {err_str}", "confidence": 0.0, "mode": "ERROR", "found": False, "error": err_str}

    def status(self):
        if self._available is None:
            self._try_init()
        if self._available:
            models = getattr(self, '_loaded_models', [])
            if models:
                return f"{cfg.STATUS_CONNECTED} ({len(models)} models)", cfg.COLOR_SUCCESS
            return f"{cfg.STATUS_CONNECTED} (no models)", cfg.COLOR_WARNING
        return cfg.STATUS_OFFLINE, cfg.COLOR_ERROR


class QASpeechBubble:
    """Generates SVG speech bubble markup — values from config."""

    @staticmethod
    def render_bubble(x, y, text):
        w = cfg.bubble["width"]
        h = cfg.bubble["height"]
        bg = cfg.bubble["bg"]
        border = cfg.bubble["border"]
        tc = cfg.bubble["text_color"]
        ff = cfg.BUBBLE_FONT_FAMILY
        fs = cfg.BUBBLE_FONT_SIZE
        r = cfg.BUBBLE_RADIUS
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        lines = []
        current = ""
        for word in safe.split():
            if len(current) + len(word) + 1 > 45:
                lines.append(current)
                current = word
            else:
                current = (current + " " + word).strip()
        if current:
            lines.append(current)
        lines = lines[:4]
        text_elements = ""
        for i, line in enumerate(lines):
            ly = y + 20 + i * 16
            text_elements += f'<text x="{x + 15}" y="{ly}" fill="{tc}" font-family="{ff}" font-size="{fs}">{line}</text>'
        return f"""
<g class="speech-bubble">
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{bg}" stroke="{border}" stroke-width="1" opacity="0.95"/>
  <path d="M{x + 30} {y + h} L{x + 50} {y + h + 15} L{x + 60} {y + h} Z" fill="{bg}" stroke="{border}" stroke-width="1"/>
  {text_elements}
</g>"""

    @staticmethod
    def render_thinking(x, y):
        bg = cfg.bubble["bg"]
        border = cfg.bubble["border"]
        dc = cfg.THINKING_DOT_COLOR
        dr = cfg.THINKING_DOT_RADIUS
        dur = cfg.THINKING_DURATION
        dots = ""
        for i in range(3):
            delay = i * 0.3
            dy = y + 25
            dx = x + 20 + i * 20
            dots += f"""
<circle cx="{dx}" cy="{dy}" r="{dr}" fill="{dc}" opacity="0.6">
  <animate attributeName="cy" values="{dy};{dy-10};{dy}" dur="{dur}" repeatCount="indefinite" begin="{delay}s"/>
  <animate attributeName="opacity" values="0.3;1;0.3" dur="{dur}" repeatCount="indefinite" begin="{delay}s"/>
</circle>"""
        return f"""
<g class="thinking">
  <rect x="{x}" y="{y}" width="100" height="50" rx="12" fill="{bg}" stroke="{border}" stroke-width="1" opacity="0.95"/>
  <path d="M{x + 30} {y + 50} L{x + 45} {y + 65} L{x + 55} {y + 50} Z" fill="{bg}" stroke="{border}" stroke-width="1"/>
  {dots}
</g>"""


class QAQueryThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, bridge, question, context=""):
        super().__init__()
        self.bridge = bridge
        self.question = question
        self.context = context

    def run(self):
        result = self.bridge.ask(self.question, self.context)
        self.finished.emit(result)


class ActivityBar(QFrame):
    """VS Code-style vertical icon bar. Click icon to toggle panel."""
    icon_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(cfg.ACTIVITY_BAR_WIDTH)
        self.setStyleSheet(f"QFrame {{ background: {cfg.ACTIVITY_BAR_BG}; border-left: 1px solid {cfg.COLOR_BORDER}; }}")
        self._buttons = {}
        self._active = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 8, 4, 8)

        for key, icon in cfg.ICONS.items():
            btn = QPushButton(icon)
            btn.setFixedSize(cfg.ACTIVITY_BAR_ICON_SIZE + 8, cfg.ACTIVITY_BAR_ICON_SIZE + 8)
            btn.setFont(QFont("Arial", 14))
            btn.setToolTip(cfg.TOOLTIPS.get(key, key))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: {cfg.ACTIVITY_BAR_ICON_COLOR};
                    font-size: 16px;
                }}
                QPushButton:hover {{
                    color: {cfg.ACTIVITY_BAR_ICON_COLOR_HOVER};
                }}
                QPushButton:checked {{
                    color: {cfg.ACTIVITY_BAR_ICON_COLOR_ACTIVE};
                    border-left: 3px solid {cfg.ACTIVITY_BAR_INDICATOR_COLOR};
                }}
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._on_click(k))
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()

    def _on_click(self, key):
        if self._active == key:
            self._buttons[key].setChecked(False)
            self._active = None
            self.icon_clicked.emit("")
        else:
            for k, b in self._buttons.items():
                b.setChecked(k == key)
            self._active = key
            self.icon_clicked.emit(key)

    def set_active(self, key):
        if key and key in self._buttons:
            for k, b in self._buttons.items():
                b.setChecked(k == key)
            self._active = key
        elif not key:
            for b in self._buttons.values():
                b.setChecked(False)
            self._active = None


class SettingsPanel(QWidget):
    """QA Engine settings panel — all values from config."""

    def __init__(self, qa_bridge, chat_display):
        super().__init__()
        self.qa_bridge = qa_bridge
        self.chat_display = chat_display
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("QA Engine Settings")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {cfg.COLOR_GOLD};")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(6)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(cfg.pipeline_mode_list())
        self.mode_combo.setCurrentIndex(list(cfg.PIPELINE_MODES.keys()).index(cfg.PIPELINE_DEFAULT_MODE))
        form.addRow("Pipeline:", self.mode_combo)

        self.emb_combo = QComboBox()
        self.emb_combo.addItems(cfg.models["embedding"])
        form.addRow("Embedding:", self.emb_combo)

        self.qa_combo = QComboBox()
        self.qa_combo.addItems(cfg.models["qa"])
        form.addRow("QA Model:", self.qa_combo)

        self.llm_check = QCheckBox("Enable LLM")
        self.llm_check.setChecked(True)
        form.addRow("LLM:", self.llm_check)

        self.backend_combo = QComboBox()
        self.backend_combo.addItems(cfg.backends)
        form.addRow("Vector Backend:", self.backend_combo)

        self.exec_combo = QComboBox()
        self.exec_combo.addItems(cfg.execution)
        form.addRow("Execution:", self.exec_combo)

        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(cfg.RETRIEVAL_TOP_K_MIN, cfg.RETRIEVAL_TOP_K_MAX)
        self.topk_spin.setValue(cfg.retrieval["top_k"])
        form.addRow("Top-K:", self.topk_spin)

        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0, 100)
        self.conf_spin.setSingleStep(0.5)
        self.conf_spin.setValue(cfg.classification["true_threshold"])
        form.addRow("Confidence Threshold:", self.conf_spin)

        layout.addLayout(form)

        apply_btn = QPushButton("Apply Settings")
        apply_btn.setStyleSheet(cfg.btn("warning"))
        apply_btn.clicked.connect(self._apply_settings)
        layout.addWidget(apply_btn)

        layout.addStretch()

    def _apply_settings(self):
        if not self.qa_bridge.available:
            self.chat_display.append(f'<i style="color:{cfg.COLOR_ERROR}">{cfg.ERROR_QA_UNAVAILABLE}</i>')
            return

        mode_map = {i: k for i, k in enumerate(cfg.PIPELINE_MODES.keys())}
        mode = mode_map.get(self.mode_combo.currentIndex(), cfg.PIPELINE_DEFAULT_MODE)
        emb = self.emb_combo.currentText()
        qa_model = self.qa_combo.currentText()
        llm_on = self.llm_check.isChecked()
        backend = self.backend_combo.currentText()
        exec_mode = self.exec_combo.currentText()
        topk = self.topk_spin.value()
        conf_thresh = self.conf_spin.value()

        engine = self.qa_bridge._engine
        c = engine.state.get("config", {})
        if not c:
            self.chat_display.append(f'<i style="color:{cfg.COLOR_ERROR}">{cfg.ERROR_NO_CONFIG}</i>')
            return

        c.setdefault("pipeline", {})["mode"] = mode
        c.setdefault("models", {}).setdefault("embedding", {})["active"] = emb
        c.setdefault("models", {}).setdefault("qa", {})["active"] = qa_model
        c.setdefault("models", {}).setdefault("llm", {})["enabled"] = llm_on
        c.setdefault("storage", {})["vector_backend"] = backend
        c.setdefault("hardware", {})["execution_mode"] = exec_mode
        c.setdefault("retrieval", {})["top_k"] = topk
        c.setdefault("classification", {})["true_threshold"] = conf_thresh
        engine.state["config"] = c

        mode_names = cfg.pipeline_mode_names()
        self.chat_display.append(
            f'<i style="color:{cfg.COLOR_SUCCESS}">Settings applied: Mode {mode} ({mode_names.get(mode,"?")}) | '
            f'Emb: {emb} | QA: {qa_model} | LLM: {"on" if llm_on else "off"} | '
            f'Backend: {backend} | Exec: {exec_mode} | Top-K: {topk}</i>'
        )
        if mode == "E":
            self.chat_display.append(
                f'<i style="color:{cfg.COLOR_WARNING}">Mode E requires context text — paste it in the context box.</i>'
            )


class ChatPanel(QWidget):
    """Chat panel — conversation log + context input."""

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("Conversation")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {cfg.COLOR_GOLD};")
        layout.addWidget(title)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        ctx_label = QLabel("Context (for Mode E — direct QA):")
        ctx_label.setStyleSheet(f"color: {cfg.COLOR_TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(ctx_label)

        self.context_input = QTextEdit()
        self.context_input.setMaximumHeight(60)
        self.context_input.setPlaceholderText("Paste context text for direct QA...")
        layout.addWidget(self.context_input)


class ExportPanel(QWidget):
    """Export panel — SVG, PNG, JSON, frames."""

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("Export")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {cfg.COLOR_GOLD};")
        layout.addWidget(title)

        for label, style, fn in [
            ("Export SVG (static)", "primary", self._export_svg),
            ("Export PNG (512x512)", "success", self._export_png),
            ("Export JSON (scene)", "warning", self._export_json),
            ("Export 60 Frames", "muted", self._export_frames),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(cfg.btn(style))
            btn.clicked.connect(fn)
            layout.addWidget(btn)

        layout.addStretch()

    def _export_svg(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "wizard.svg", "SVG Files (*.svg)")
        if path:
            svg = self.engine.render_static_svg()
            if svg:
                with open(path, "wb") as f:
                    f.write(svg)

    def _export_png(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "wizard.png", "PNG Files (*.png)")
        if path:
            png = self.engine.render_png()
            if png:
                with open(path, "wb") as f:
                    f.write(png)

    def _export_json(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "scene.json", "JSON Files (*.json)")
        if path:
            j = self.engine.export_scene_json()
            if j:
                with open(path, "wb") as f:
                    f.write(j)

    def _export_frames(self):
        from PyQt6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d:
            for i in range(cfg.scene["frames"]):
                t = i / cfg.scene["frames"]
                svg = self.engine.render(t)
                if svg:
                    with open(os.path.join(d, f"frame_{i:02d}.svg"), "wb") as f:
                        f.write(svg)


class InfoPanel(QWidget):
    """About / info panel."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("About")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {cfg.COLOR_GOLD};")
        layout.addWidget(title)

        info = QLabel(cfg.INFO_TEXT)
        info.setStyleSheet(f"color: {cfg.COLOR_TEXT_DIM}; font-size: 11px; padding: 8px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Engine details
        details = QLabel(
            f"SVG Engine v{cfg.SVG_ENGINE_VERSION}\n"
            f"Scene: {cfg.scene['width']}x{cfg.scene['height']}\n"
            f"Animation: {cfg.scene['frames']} frames @ {cfg.scene['fps']}fps\n"
            f"Max Objects: {cfg.scene['max_objects']}\n"
            f"Max Keyframes: {cfg.scene['max_keyframes']}\n"
            f"Max Particles: {cfg.scene['max_particles']}\n"
            f"\nPipeline Modes: {', '.join(cfg.PIPELINE_MODES.keys())}\n"
            f"Embedding Models: {len(cfg.models['embedding'])}\n"
            f"QA Models: {len(cfg.models['qa'])}\n"
            f"LLM Models: {len(cfg.models['llm'])}\n"
            f"Vector Backends: {', '.join(cfg.backends)}\n"
        )
        details.setStyleSheet(f"color: {cfg.COLOR_TEXT_MUTED}; font-size: 11px; padding: 8px;")
        layout.addWidget(details)

        layout.addStretch()


class WizardQAUI(QMainWindow):
    """VS Code-style layout: activity bar + expandable panel + SVG center + bottom chat bar."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(cfg.window["title"])
        self.setMinimumSize(cfg.window["min_width"], cfg.window["min_height"])
        self.resize(cfg.window["width"], cfg.window["height"])
        self.setStyleSheet(cfg.theme())

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
        self.active_panel = None

        self._build_ui()
        self._start_timer()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setSpacing(0)
        main.setContentsMargins(0, 0, 0, 0)

        # ─── Center: SVG Preview + Bottom Chat Bar (added first = leftmost) ───
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setSpacing(0)
        center_layout.setContentsMargins(10, 10, 10, 10)

        # SVG preview area
        svg_area = QVBoxLayout()
        svg_area.setSpacing(6)

        title = QLabel(f"{cfg.SVG_ENGINE_NAME} — Live Preview")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {cfg.COLOR_GOLD};")
        svg_area.addWidget(title)

        self.svg_widget = QSvgWidget()
        self.svg_widget.setFixedSize(cfg.scene["width"], cfg.scene["height"])
        self.svg_widget.setStyleSheet(
            f"border: {cfg.SVG_PREVIEW_BORDER}; border-radius: {cfg.SVG_PREVIEW_RADIUS}; background: {cfg.SVG_PREVIEW_BG};"
        )
        svg_area.addWidget(self.svg_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Theme + playback row
        ctrl_row = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet(f"color: {cfg.COLOR_TEXT_MUTED};")
        ctrl_row.addWidget(theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(cfg.themes.keys())
        self.theme_combo.currentTextChanged.connect(self._load_preset)
        ctrl_row.addWidget(self.theme_combo)

        self.play_btn = QPushButton("Pause")
        self.play_btn.setStyleSheet(cfg.btn("primary"))
        self.play_btn.clicked.connect(self._toggle_play)
        ctrl_row.addWidget(self.play_btn)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setStyleSheet(cfg.btn("warning"))
        self.reset_btn.clicked.connect(lambda: setattr(self, 'time', 0.0))
        ctrl_row.addWidget(self.reset_btn)
        ctrl_row.addStretch()
        svg_area.addLayout(ctrl_row)

        center_layout.addLayout(svg_area, stretch=1)

        # ─── Bottom Chat Bar ───
        chat_bar = QFrame()
        chat_bar.setStyleSheet(f"QFrame {{ background: {cfg.CHAT_BAR_BG}; border-top: 1px solid {cfg.COLOR_BORDER}; }}")
        chat_layout = QHBoxLayout(chat_bar)
        chat_layout.setSpacing(8)
        chat_layout.setContentsMargins(10, 8, 10, 8)

        chat_input_col = QVBoxLayout()
        chat_input_col.setSpacing(4)

        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Ask the wizard...")
        self.question_input.returnPressed.connect(self._ask_question)
        self.question_input.setStyleSheet(
            f"QLineEdit {{ background: {cfg.CHAT_BAR_INPUT_BG}; color: {cfg.COLOR_TEXT}; "
            f"border: 2px solid {cfg.CHAT_BAR_INPUT_BORDER}; padding: {cfg.CHAT_BAR_INPUT_PADDING}px; "
            f"border-radius: {cfg.CHAT_BAR_INPUT_RADIUS}px; font-size: {cfg.CHAT_BAR_INPUT_FONT_SIZE}px; }}"
        )
        chat_input_col.addWidget(self.question_input)
        chat_layout.addLayout(chat_input_col)

        self.ask_btn = QPushButton(cfg.STATUS_ASK)
        self.ask_btn.setStyleSheet(cfg.btn("success"))
        self.ask_btn.clicked.connect(self._ask_question)
        chat_layout.addWidget(self.ask_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(cfg.btn("muted"))
        self.clear_btn.clicked.connect(self._clear_chat)
        chat_layout.addWidget(self.clear_btn)

        center_layout.addWidget(chat_bar)

        main.addWidget(center, stretch=1)

        # ─── Side Panel (expandable, right of center, left of activity bar) ───
        self.side_panel = QFrame()
        self.side_panel.setFixedWidth(cfg.SIDE_PANEL_WIDTH)
        self.side_panel.setStyleSheet(f"QFrame {{ background: {cfg.SIDE_PANEL_BG}; border-left: 1px solid {cfg.COLOR_BORDER}; }}")
        self.side_panel.setVisible(False)
        self.side_layout = QVBoxLayout(self.side_panel)
        self.side_layout.setSpacing(0)
        self.side_layout.setContentsMargins(0, 0, 0, 0)
        main.addWidget(self.side_panel)

        # ─── Activity Bar (far right, vertical icons) ───
        self.activity_bar = ActivityBar()
        self.activity_bar.icon_clicked.connect(self._on_activity_clicked)
        main.addWidget(self.activity_bar)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet(f"QStatusBar {{ background: {cfg.CHAT_BAR_BG}; color: {cfg.COLOR_TEXT_MUTED}; }}")

        # Build panels (lazy)
        self._panels = {}
        QTimer.singleShot(1000, self._check_qa_status)

    def _on_activity_clicked(self, key):
        # Clear current panel
        if self.active_panel == key:
            self.side_panel.setVisible(False)
            self.active_panel = None
            self.activity_bar.set_active("")
            return

        # Clear side panel layout
        while self.side_layout.count():
            item = self.side_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Build and show the requested panel
        if key == "settings":
            panel = SettingsPanel(self.qa_bridge, self._get_chat_display())
        elif key == "chat":
            panel = ChatPanel()
            self._chat_panel = panel
        elif key == "export":
            panel = ExportPanel(self.engine)
        elif key == "info":
            panel = InfoPanel()
        else:
            self.side_panel.setVisible(False)
            self.active_panel = None
            return

        self._panels[key] = panel
        self.side_layout.addWidget(panel)
        self.side_panel.setVisible(True)
        self.active_panel = key

    def _get_chat_display(self):
        if hasattr(self, '_chat_panel') and self._chat_panel:
            return self._chat_panel.chat_display
        # If chat panel hasn't been opened yet, create a temp one
        if not hasattr(self, '_temp_chat'):
            self._temp_chat = QTextEdit()
            self._temp_chat.setReadOnly(True)
        return self._temp_chat

    def _check_qa_status(self):
        status_text, color = self.qa_bridge.status()
        chat = self._get_chat_display()
        if hasattr(self.qa_bridge, '_loaded_models') and self.qa_bridge._loaded_models:
            models = ", ".join(self.qa_bridge._loaded_models)
            chat.append(f'<i style="color:{cfg.COLOR_TEXT_DIM}">Loaded models: {models}</i>')
        if hasattr(self.qa_bridge, '_init_errors') and self.qa_bridge._init_errors:
            for e in self.qa_bridge._init_errors[-3:]:
                chat.append(f'<i style="color:{cfg.COLOR_ERROR}">Init error: {e}</i>')
        if hasattr(self.qa_bridge, '_init_data') and self.qa_bridge._init_data:
            d = self.qa_bridge._init_data
            chat.append(
                f'<i style="color:{cfg.COLOR_TEXT_DIM}">Backend: {d.get("backend","?")} | '
                f'Embedding: {d.get("embedding_model","?")} | '
                f'QA: {d.get("qa_model","?")} | '
                f'LLM: {d.get("llm_model","?")}</i>'
            )

    def _ask_question(self):
        question = self.question_input.text().strip()
        if not question:
            return
        context = ""
        if hasattr(self, '_chat_panel') and self._chat_panel:
            context = self._chat_panel.context_input.toPlainText().strip()

        self.thinking = True
        self.bubble_text = ""
        self.ask_btn.setEnabled(False)
        self.ask_btn.setText(cfg.STATUS_THINKING)

        chat = self._get_chat_display()
        chat.append(f'<b style="color:{cfg.COLOR_CHAT_USER}">You:</b> {question}')

        self.qa_thread = QAQueryThread(self.qa_bridge, question, context)
        self.qa_thread.finished.connect(self._on_qa_result)
        self.qa_thread.start()

    def _on_qa_result(self, result):
        self.thinking = False
        self.ask_btn.setEnabled(True)
        self.ask_btn.setText(cfg.STATUS_ASK)

        answer = result.get("answer", "No answer")
        confidence = result.get("confidence", 0.0)
        mode = result.get("mode", "UNKNOWN")
        found = result.get("found", False)

        self.bubble_text = answer
        self.bubble_timer = time.time() + cfg.bubble["display_seconds"]

        chat = self._get_chat_display()
        color = cfg.COLOR_CHAT_WIZARD if found else cfg.COLOR_CHAT_WIZARD_NOT_FOUND
        chat.append(
            f'<b style="color:{color}">Wizard:</b> {answer}\n'
            f'<span style="color:{cfg.COLOR_TEXT_DIM}">  [confidence: {confidence:.2f} | mode: {mode}]</span>'
        )

        self.status_bar.showMessage(
            f"Answer: confidence={confidence:.2f} mode={mode}  |  QA: {self.qa_bridge.status()[0]}", 5000
        )

    def _clear_chat(self):
        chat = self._get_chat_display()
        chat.clear()
        self.bubble_text = ""
        self.bubble_timer = 0

    def _load_preset(self, name):
        self.engine.load_preset(name)

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

        svg_bytes = self.engine.render(self.time)
        if not svg_bytes:
            return

        svg_str = svg_bytes.decode("utf-8", errors="replace")

        bubble_svg = ""
        if self.thinking:
            bubble_svg = QASpeechBubble.render_thinking(340, 100)
        elif self.bubble_text and now < self.bubble_timer:
            bubble_svg = QASpeechBubble.render_bubble(280, 80, self.bubble_text)
        elif self.bubble_text and now >= self.bubble_timer:
            self.bubble_text = ""

        if bubble_svg:
            svg_str = svg_str.replace("</svg>", bubble_svg + "</svg>")

        self.svg_widget.load(QByteArray(svg_str.encode("utf-8")))

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
    app.setApplicationName(cfg.window["title"])
    w = WizardQAUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
