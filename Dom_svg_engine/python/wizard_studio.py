#!/usr/bin/env python3
"""
wizard_studio.py — Qt6-based GUI for the Wizard SVG Animation Engine.

Features:
  - Live SVG preview with auto-refresh
  - JSON scene editor with syntax highlighting
  - Object property panels (position, rotation, scale, color, motion)
  - Timeline scrubber with play/pause
  - Particle system controls
  - Export to SVG file
  - Built-in demo scenes

Architecture:
  Python/Qt UI → Scene JSON → C Engine (via ctypes) → SVG → Qt preview
"""

import sys
import os
import json
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QTextEdit, QPushButton, QLabel,
    QSlider, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QGroupBox, QFormLayout, QScrollArea, QFileDialog, QStatusBar,
    QToolBar, QProgressBar, QListWidget, QListWidgetItem,
    QColorDialog, QMessageBox, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QSize, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QAction, QIcon, QFont, QColor, QTextCharFormat, QSyntaxHighlighter
from PyQt6.QtWebEngineWidgets import QWebEngineView

from wizard_engine_bridge import WizardEngineBridge

# Paths
ENGINE_DIR = Path(__file__).parent.parent
EXAMPLES_DIR = ENGINE_DIR / "examples"
SCENES_DIR = ENGINE_DIR / "scenes"


class SVGHighlighter(QSyntaxHighlighter):
    """Simple syntax highlighter for SVG/JSON."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.json_format = QTextCharFormat()
        self.json_format.setForeground(QColor("#7ec8ff"))

        self.key_format = QTextCharFormat()
        self.key_format.setForeground(QColor("#ffd700"))

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#98c379"))

        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#d19a66"))

    def highlightBlock(self, text):
        # Highlight JSON keys
        import re
        for match in re.finditer(r'"(\w+)"\s*:', text):
            start = match.start(1)
            end = match.end(1)
            self.setFormat(start, end - start, self.key_format)

        # Highlight strings
        for match in re.finditer(r'"([^"]*)"', text):
            start = match.start(1)
            end = match.end(1)
            self.setFormat(start, end - start, self.string_format)

        # Highlight numbers
        for match in re.finditer(r'\b\d+\.?\d*\b', text):
            start = match.start()
            end = match.end()
            self.setFormat(start, end - start, self.number_format)


class RenderThread(QThread):
    """Background thread for rendering SVG via the C engine CLI."""
    rendered = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, engine: WizardEngineBridge):
        super().__init__()
        self.engine = engine
        self.json_text = ""
        self._tmp_counter = 0

    def set_json(self, json_text: str):
        self.json_text = json_text

    def run(self):
        try:
            # Write JSON to temp file, render via CLI, read SVG back
            import tempfile, subprocess, os
            tmp_json = tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False, prefix='wizard_scene_'
            )
            tmp_json.write(self.json_text)
            tmp_json.close()

            tmp_svg = tmp_json.name.replace('.json', '.svg')

            result = subprocess.run(
                [self.engine.cli_path, tmp_json.name, tmp_svg],
                capture_output=True, text=True, timeout=10
            )

            os.unlink(tmp_json.name)

            if result.returncode != 0:
                self.error.emit(f"Engine error: {result.stderr}")
                if os.path.exists(tmp_svg):
                    os.unlink(tmp_svg)
                return

            with open(tmp_svg, 'r') as f:
                svg = f.read()
            os.unlink(tmp_svg)

            self.rendered.emit(svg)
        except subprocess.TimeoutExpired:
            self.error.emit("Render timed out")
        except Exception as e:
            self.error.emit(str(e))


class WizardStudio(QMainWindow):
    """Main studio window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wizard SVG Animation Studio")
        self.resize(1200, 800)

        self.engine = WizardEngineBridge()
        self.render_thread = RenderThread(self.engine)
        self.render_thread.rendered.connect(self.on_svg_rendered)
        self.render_thread.error.connect(self.on_render_error)

        self.auto_refresh = True
        self.is_playing = False
        self.current_frame = 0
        self.total_frames = 60

        self._build_ui()
        self._load_default_scene()

        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_preview)
        self.refresh_timer.start(500)

        # Animation timer
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.on_anim_tick)

    def _build_ui(self):
        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: SVG preview
        self.preview_widget = self._build_preview_panel()
        splitter.addWidget(self.preview_widget)

        # Right: Editor tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_json_editor_tab(), "Scene JSON")
        self.tabs.addTab(self._build_objects_tab(), "Objects")
        self.tabs.addTab(self._build_timeline_tab(), "Timeline")
        splitter.addWidget(self.tabs)

        splitter.setSizes([600, 600])
        layout.addWidget(splitter)

        # Toolbar
        self._build_toolbar()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _build_toolbar(self):
        toolbar = self.addToolBar("Main")
        toolbar.setIconSize(QSize(16, 16))

        # New scene
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_scene)
        toolbar.addAction(new_action)

        # Open
        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_scene)
        toolbar.addAction(open_action)

        # Save
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_scene)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        # Export SVG
        export_action = QAction("Export SVG", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_svg)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        # Demo scenes
        demo_action = QAction("Wizard Demo", self)
        demo_action.triggered.connect(self.load_wizard_demo)
        toolbar.addAction(demo_action)

        mcp_demo_action = QAction("MCP Demo", self)
        mcp_demo_action.triggered.connect(self.load_mcp_demo)
        toolbar.addAction(mcp_demo_action)

        toolbar.addSeparator()

        # Auto-refresh toggle
        self.auto_refresh_action = QAction("Auto Refresh", self)
        self.auto_refresh_action.setCheckable(True)
        self.auto_refresh_action.setChecked(True)
        self.auto_refresh_action.triggered.connect(self.toggle_auto_refresh)
        toolbar.addAction(self.auto_refresh_action)

        # Manual refresh
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_preview)
        toolbar.addAction(refresh_action)

    def _build_preview_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # SVG preview using QWebEngineView (Chromium — supports SMIL animations)
        self.svg_preview = QWebEngineView()
        self.svg_preview.setMinimumHeight(400)
        layout.addWidget(self.svg_preview)

        # Preview controls
        controls = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self.toggle_playback)
        controls.addWidget(self.play_btn)

        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setRange(0, 59)
        self.frame_slider.setValue(0)
        self.frame_slider.valueChanged.connect(self.on_frame_change)
        controls.addWidget(self.frame_slider)

        self.frame_label = QLabel("Frame: 0/60")
        controls.addWidget(self.frame_label)

        layout.addLayout(controls)

        return widget

    def _build_json_editor_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.json_editor = QTextEdit()
        self.json_editor.setFont(QFont("Monaco", 12))
        self.highlighter = SVGHighlighter(self.json_editor.document())
        self.json_editor.textChanged.connect(self.on_json_changed)
        layout.addWidget(self.json_editor)

        # Validation status
        self.json_status = QLabel("✓ Valid JSON")
        self.json_status.setStyleSheet("color: green;")
        layout.addWidget(self.json_status)

        return widget

    def _build_objects_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Object list
        self.object_list = QListWidget()
        self.object_list.currentItemChanged.connect(self.on_object_selected)
        layout.addWidget(QLabel("Objects:"))
        layout.addWidget(self.object_list)

        # Property panel
        props_group = QGroupBox("Properties")
        props_layout = QFormLayout(props_group)

        self.prop_id = QLineEdit()
        self.prop_type = QComboBox()
        self.prop_type.addItems([
            "group", "hat", "wand", "star", "coat", "beard",
            "circle", "rect", "text", "emitter", "glow_orb",
            "rune_circle", "lightning", "mcp_node"
        ])
        self.prop_x = QDoubleSpinBox()
        self.prop_x.setRange(-1000, 2000)
        self.prop_y = QDoubleSpinBox()
        self.prop_y.setRange(-1000, 2000)
        self.prop_rotation = QDoubleSpinBox()
        self.prop_rotation.setRange(-360, 360)
        self.prop_scale = QDoubleSpinBox()
        self.prop_scale.setRange(0.01, 10.0)
        self.prop_scale.setSingleStep(0.1)
        self.prop_opacity = QDoubleSpinBox()
        self.prop_opacity.setRange(0.0, 1.0)
        self.prop_opacity.setSingleStep(0.1)
        self.prop_color_btn = QPushButton("Pick Color")
        self.prop_color_btn.clicked.connect(self.pick_color)

        props_layout.addRow("ID:", self.prop_id)
        props_layout.addRow("Type:", self.prop_type)
        props_layout.addRow("X:", self.prop_x)
        props_layout.addRow("Y:", self.prop_y)
        props_layout.addRow("Rotation:", self.prop_rotation)
        props_layout.addRow("Scale:", self.prop_scale)
        props_layout.addRow("Opacity:", self.prop_opacity)
        props_layout.addRow("Color:", self.prop_color_btn)

        # Motion controls
        motion_group = QGroupBox("Motion")
        motion_layout = QFormLayout(motion_group)

        self.motion_type = QComboBox()
        self.motion_type.addItems([
            "none", "rotate", "orbit", "pulse", "fade",
            "noise_drift", "float", "wand_wave", "particle_emit", "glow"
        ])
        self.motion_speed = QDoubleSpinBox()
        self.motion_speed.setRange(0, 10)
        self.motion_speed.setSingleStep(0.1)
        self.motion_amplitude = QDoubleSpinBox()
        self.motion_amplitude.setRange(0, 200)
        self.motion_radius = QDoubleSpinBox()
        self.motion_radius.setRange(0, 500)
        self.motion_phase = QDoubleSpinBox()
        self.motion_phase.setRange(0, 1)
        self.motion_phase.setSingleStep(0.1)

        motion_layout.addRow("Type:", self.motion_type)
        motion_layout.addRow("Speed:", self.motion_speed)
        motion_layout.addRow("Amplitude:", self.motion_amplitude)
        motion_layout.addRow("Radius:", self.motion_radius)
        motion_layout.addRow("Phase:", self.motion_phase)

        # Apply button
        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(self.apply_property_changes)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.addWidget(props_group)
        scroll_layout.addWidget(motion_group)
        scroll_layout.addWidget(apply_btn)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)

        layout.addWidget(scroll)

        return widget

    def _build_timeline_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Animation Timeline"))

        # Duration controls
        dur_layout = QHBoxLayout()
        dur_layout.addWidget(QLabel("Duration (s):"))
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 60.0)
        self.duration_spin.setValue(4.0)
        self.duration_spin.valueChanged.connect(self.on_duration_change)
        dur_layout.addWidget(self.duration_spin)
        dur_layout.addStretch()
        layout.addLayout(dur_layout)

        # FPS
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(60)
        self.fps_spin.valueChanged.connect(self.on_fps_change)
        fps_layout.addWidget(self.fps_spin)
        fps_layout.addStretch()
        layout.addLayout(fps_layout)

        # Timeline slider
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 100)
        self.timeline_slider.setValue(0)
        self.timeline_slider.valueChanged.connect(self._on_timeline_scrub)
        layout.addWidget(self.timeline_slider)

        # Keyframe list
        layout.addWidget(QLabel("Keyframes:"))
        self.keyframe_list = QListWidget()
        layout.addWidget(self.keyframe_list)

        # Add keyframe button
        add_kf_btn = QPushButton("Add Keyframe at Current Time")
        add_kf_btn.clicked.connect(self.add_keyframe)
        layout.addWidget(add_kf_btn)

        layout.addStretch()

        return widget

    # --- Event handlers ---

    def on_json_changed(self):
        """Called when the JSON editor text changes."""
        text = self.json_editor.toPlainText()
        try:
            json.loads(text)
            self.json_status.setText("✓ Valid JSON")
            self.json_status.setStyleSheet("color: green;")
            self.update_object_list()
            self._refresh_keyframe_list()
        except json.JSONDecodeError as e:
            self.json_status.setText(f"✗ Invalid JSON: {e}")
            self.json_status.setStyleSheet("color: red;")

    def on_svg_rendered(self, svg: str):
        """Called when the render thread produces SVG."""
        # Display SVG in WebEngineView (Chromium supports SMIL animations)
        html = f"<!DOCTYPE html><html><body style='margin:0;padding:0;background:#0d0a1a;display:flex;align-items:center;justify-content:center;min-height:100vh'>{svg}</body></html>"
        self.svg_preview.setHtml(html, QUrl("about:blank"))
        self.status_bar.showMessage(f"Rendered {len(svg)} bytes")

    def on_render_error(self, error: str):
        """Called when rendering fails."""
        self.status_bar.showMessage(f"Render error: {error}")

    def refresh_preview(self):
        """Refresh the SVG preview from current JSON."""
        if not self.auto_refresh:
            return
        if self.render_thread.isRunning():
            return  # Skip if still rendering

        text = self.json_editor.toPlainText()
        if not text.strip():
            return

        try:
            scene = json.loads(text)  # Validate
        except:
            return

        # Apply keyframe interpolation at the current timeline position
        if scene.get("keyframes"):
            t = self.timeline_slider.value() / 100.0
            scene = self._interpolate_keyframes(scene, t)
            text = json.dumps(scene)

        self.render_thread.set_json(text)
        self.render_thread.start()

    def toggle_auto_refresh(self):
        self.auto_refresh = self.auto_refresh_action.isChecked()

    def toggle_playback(self):
        if self.is_playing:
            self.anim_timer.stop()
            self.is_playing = False
            self.play_btn.setText("▶ Play")
        else:
            self.anim_timer.start(1000 // 60)
            self.is_playing = True
            self.play_btn.setText("⏸ Pause")

    def on_anim_tick(self):
        self.current_frame = (self.current_frame + 1) % 60
        self.frame_slider.setValue(self.current_frame)

    def on_frame_change(self, frame):
        self.frame_label.setText(f"Frame: {frame}/60")
        self.current_frame = frame

    def on_duration_change(self, val):
        self._update_json_field("duration", val)

    def on_fps_change(self, val):
        self._update_json_field("fps", val)

    def _on_timeline_scrub(self, value):
        """Timeline slider moved — refresh preview to show interpolated state."""
        self.status_bar.showMessage(f"Timeline: {value / 100.0:.2f}")
        self.refresh_preview()

    def on_object_selected(self, current, previous):
        if not current:
            return
        # Load object properties from JSON
        text = self.json_editor.toPlainText()
        try:
            scene = json.loads(text)
            obj_id = current.text().split(" — ")[0]
            for obj in scene.get("objects", []):
                if obj.get("id") == obj_id:
                    self.prop_id.setText(obj.get("id", ""))
                    self.prop_type.setCurrentText(obj.get("type", "group"))
                    pos = obj.get("position", [256, 256])
                    self.prop_x.setValue(pos[0])
                    self.prop_y.setValue(pos[1])
                    self.prop_rotation.setValue(obj.get("rotation", 0))
                    self.prop_scale.setValue(obj.get("scale", 1.0))
                    self.prop_opacity.setValue(obj.get("opacity", 1.0))

                    motion = obj.get("motion", {})
                    self.motion_type.setCurrentText(motion.get("type", "none"))
                    self.motion_speed.setValue(motion.get("speed", 1.0))
                    self.motion_amplitude.setValue(motion.get("amplitude", 10.0))
                    self.motion_radius.setValue(motion.get("radius", 40.0))
                    self.motion_phase.setValue(motion.get("phase", 0.0))
                    break
        except:
            pass

    def apply_property_changes(self):
        """Apply property panel changes back to JSON."""
        text = self.json_editor.toPlainText()
        try:
            scene = json.loads(text)
        except:
            return

        obj_id = self.prop_id.text()
        for obj in scene.get("objects", []):
            if obj.get("id") == obj_id:
                obj["type"] = self.prop_type.currentText()
                obj["position"] = [self.prop_x.value(), self.prop_y.value()]
                obj["rotation"] = self.prop_rotation.value()
                obj["scale"] = self.prop_scale.value()
                obj["opacity"] = self.prop_opacity.value()

                if self.motion_type.currentText() != "none":
                    obj["motion"] = {
                        "type": self.motion_type.currentText(),
                        "speed": self.motion_speed.value(),
                        "amplitude": self.motion_amplitude.value(),
                        "radius": self.motion_radius.value(),
                        "phase": self.motion_phase.value(),
                    }
                elif "motion" in obj:
                    del obj["motion"]
                break

        self.json_editor.setPlainText(json.dumps(scene, indent=2))

    def pick_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            # Apply to selected object
            text = self.json_editor.toPlainText()
            try:
                scene = json.loads(text)
                obj_id = self.prop_id.text()
                for obj in scene.get("objects", []):
                    if obj.get("id") == obj_id:
                        obj["color"] = color.name()
                        break
                self.json_editor.setPlainText(json.dumps(scene, indent=2))
            except:
                pass

    def add_keyframe(self):
        """Add a keyframe at the current timeline position.

        A keyframe captures the currently selected object's properties
        (position, rotation, scale, opacity, color) at a normalized time
        in [0.0, 1.0] derived from the timeline slider. Keyframes are
        stored per-object in the scene JSON under ``keyframes`` and kept
        sorted by time. If a keyframe already exists at the same time it
        is replaced.
        """
        obj_id = self.prop_id.text().strip()
        if not obj_id:
            self.status_bar.showMessage("Select an object before adding a keyframe")
            return

        text = self.json_editor.toPlainText()
        try:
            scene = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            self.status_bar.showMessage("Cannot add keyframe — invalid JSON")
            return

        # Locate the target object so we can capture its current color
        target = None
        for obj in scene.get("objects", []):
            if obj.get("id") == obj_id:
                target = obj
                break
        if target is None:
            self.status_bar.showMessage(f"Object '{obj_id}' not found in scene")
            return

        # Normalized time from the timeline slider (0..100 -> 0.0..1.0)
        t = self.timeline_slider.value() / 100.0

        # Capture animatable properties from the property panel
        properties = {
            "position": [self.prop_x.value(), self.prop_y.value()],
            "rotation": self.prop_rotation.value(),
            "scale": self.prop_scale.value(),
            "opacity": self.prop_opacity.value(),
        }
        if "color" in target:
            properties["color"] = target["color"]

        keyframes_map = scene.setdefault("keyframes", {})
        kf_list = keyframes_map.setdefault(obj_id, [])

        # Replace any existing keyframe at the same time, then insert
        kf_list = [kf for kf in kf_list if abs(kf.get("time", -1) - t) > 1e-6]
        kf_list.append({"time": t, "properties": properties})
        kf_list.sort(key=lambda kf: kf.get("time", 0.0))
        keyframes_map[obj_id] = kf_list

        self.json_editor.setPlainText(json.dumps(scene, indent=2))
        self._refresh_keyframe_list()

        self.status_bar.showMessage(
            f"Keyframe added for '{obj_id}' at t={t:.2f} ({len(kf_list)} total)"
        )

    def _refresh_keyframe_list(self):
        """Rebuild the keyframe list widget from the scene JSON."""
        self.keyframe_list.clear()
        text = self.json_editor.toPlainText()
        try:
            scene = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return
        keyframes_map = scene.get("keyframes", {})
        for obj_id in sorted(keyframes_map.keys()):
            for kf in keyframes_map[obj_id]:
                t = kf.get("time", 0.0)
                props = kf.get("properties", {})
                summary = ", ".join(
                    f"{k}={v}" for k, v in props.items()
                )
                item = QListWidgetItem(f"{obj_id} @ {t:.2f}  [{summary}]")
                self.keyframe_list.addItem(item)

    @staticmethod
    def _lerp(a, b, t):
        """Linear interpolation between two numbers."""
        return a + (b - a) * t

    @classmethod
    def _interpolate_keyframes(cls, scene, t):
        """Return a copy of *scene* with object properties interpolated
        between the keyframes surrounding normalized time *t*.

        Only objects that have at least two keyframes are affected. Numeric
        properties and 2-element positions are linearly interpolated; colors
        (hex strings) are interpolated in RGB space. Objects with zero or one
        keyframe keep their base values.
        """
        keyframes_map = scene.get("keyframes", {})
        if not keyframes_map:
            return scene

        import copy
        out = copy.deepcopy(scene)
        for obj in out.get("objects", []):
            obj_id = obj.get("id")
            kf_list = keyframes_map.get(obj_id)
            if not kf_list or len(kf_list) < 2:
                continue
            times = [kf.get("time", 0.0) for kf in kf_list]
            # Clamp t to the keyframe range
            if t <= times[0]:
                props = kf_list[0].get("properties", {})
            elif t >= times[-1]:
                props = kf_list[-1].get("properties", {})
            else:
                # Find the surrounding pair
                k0, k1 = kf_list[0], kf_list[-1]
                for i in range(len(kf_list) - 1):
                    if times[i] <= t <= times[i + 1]:
                        k0, k1 = kf_list[i], kf_list[i + 1]
                        break
                t0, t1 = k0.get("time", 0.0), k1.get("time", 0.0)
                span = (t1 - t0) or 1.0
                local_t = (t - t0) / span
                p0 = k0.get("properties", {})
                p1 = k1.get("properties", {})
                props = {}
                for key in set(p0.keys()) | set(p1.keys()):
                    v0 = p0.get(key)
                    v1 = p1.get(key)
                    if v0 is None:
                        props[key] = v1
                    elif v1 is None:
                        props[key] = v0
                    elif isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
                        props[key] = cls._lerp(v0, v1, local_t)
                    elif isinstance(v0, list) and isinstance(v1, list) and len(v0) == len(v1):
                        props[key] = [cls._lerp(a, b, local_t) for a, b in zip(v0, v1)]
                    elif isinstance(v0, str) and isinstance(v1, str) and v0.startswith("#") and v1.startswith("#"):
                        props[key] = cls._lerp_color(v0, v1, local_t)
                    else:
                        props[key] = v1 if local_t >= 0.5 else v0
            # Apply interpolated properties onto the object
            for key, val in props.items():
                obj[key] = val
        return out

    @classmethod
    def _lerp_color(cls, c0, c1, t):
        """Linearly interpolate between two hex colors (#rrggbb)."""
        try:
            r0, g0, b0 = int(c0[1:3], 16), int(c0[3:5], 16), int(c0[5:7], 16)
            r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
            r = round(cls._lerp(r0, r1, t))
            g = round(cls._lerp(g0, g1, t))
            b = round(cls._lerp(b0, b1, t))
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, IndexError):
            return c1 if t >= 0.5 else c0

    def update_object_list(self):
        """Update the object list from JSON."""
        text = self.json_editor.toPlainText()
        try:
            scene = json.loads(text)
            self.object_list.clear()
            for obj in scene.get("objects", []):
                item = QListWidgetItem(f"{obj.get('id', '?')} — {obj.get('type', '?')}")
                self.object_list.addItem(item)
        except:
            pass

    def _update_json_field(self, field, value):
        """Update a top-level field in the scene JSON."""
        text = self.json_editor.toPlainText()
        try:
            scene = json.loads(text)
            scene[field] = value
            self.json_editor.setPlainText(json.dumps(scene, indent=2))
        except:
            pass

    # --- File operations ---

    def new_scene(self):
        default = {
            "name": "New Scene",
            "width": 512,
            "height": 512,
            "background": [0.05, 0.03, 0.12],
            "duration": 4.0,
            "fps": 60,
            "objects": []
        }
        self.json_editor.setPlainText(json.dumps(default, indent=2))

    def open_scene(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Scene", str(SCENES_DIR), "JSON files (*.json)"
        )
        if filepath:
            with open(filepath) as f:
                self.json_editor.setPlainText(f.read())
            self.status_bar.showMessage(f"Loaded: {filepath}")

    def save_scene(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Scene", str(SCENES_DIR), "JSON files (*.json)"
        )
        if filepath:
            with open(filepath, "w") as f:
                f.write(self.json_editor.toPlainText())
            self.status_bar.showMessage(f"Saved: {filepath}")

    def export_svg(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export SVG", str(EXAMPLES_DIR), "SVG files (*.svg)"
        )
        if filepath:
            text = self.json_editor.toPlainText()
            try:
                # Write JSON to temp, render via CLI
                import tempfile, subprocess, os
                tmp_json = tempfile.NamedTemporaryFile(
                    mode='w', suffix='.json', delete=False, prefix='wizard_export_'
                )
                tmp_json.write(text)
                tmp_json.close()

                result = subprocess.run(
                    [self.engine.cli_path, tmp_json.name, filepath],
                    capture_output=True, text=True, timeout=10
                )
                os.unlink(tmp_json.name)

                if result.returncode != 0:
                    raise RuntimeError(result.stderr)

                self.status_bar.showMessage(f"Exported: {filepath}")
                QMessageBox.information(self, "Export", f"SVG exported to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def load_wizard_demo(self):
        """Load the wizard demo scene."""
        output = str(EXAMPLES_DIR / "wizard_idle.svg")
        try:
            self.engine.run_demo(output)
            # Also generate the JSON for the demo
            demo_json = self._generate_demo_json()
            self.json_editor.setPlainText(json.dumps(demo_json, indent=2))
            self.status_bar.showMessage("Wizard demo loaded")
        except Exception as e:
            QMessageBox.critical(self, "Demo Error", str(e))

    def load_mcp_demo(self):
        """Load the MCP node graph demo."""
        output = str(EXAMPLES_DIR / "mcp_nodes.svg")
        try:
            self.engine.run_mcp_demo(output)
            demo_json = self._generate_mcp_demo_json()
            self.json_editor.setPlainText(json.dumps(demo_json, indent=2))
            self.status_bar.showMessage("MCP demo loaded")
        except Exception as e:
            QMessageBox.critical(self, "Demo Error", str(e))

    def _generate_demo_json(self) -> dict:
        """Generate the wizard demo scene as JSON."""
        return {
            "name": "Wizard Idle",
            "width": 512,
            "height": 512,
            "background": [0.05, 0.03, 0.12],
            "duration": 4.0,
            "fps": 60,
            "objects": [
                {
                    "id": "rune_bg", "type": "rune_circle",
                    "position": [256, 280], "color": "#00ffff",
                    "motion": {"type": "rotate", "speed": 0.2, "amplitude": 0, "radius": 0, "phase": 0}
                },
                {
                    "id": "glow_bg", "type": "glow_orb",
                    "position": [256, 280], "scale": 3.0, "color": "#7b2ff7",
                    "motion": {"type": "glow", "speed": 0.5, "amplitude": 0, "radius": 0, "phase": 0}
                },
                {
                    "id": "hat", "type": "hat",
                    "position": [256, 180], "stroke_color": "#ffd700", "stroke_width": 2,
                    "motion": {"type": "float", "speed": 0.4, "amplitude": 6, "radius": 0, "phase": 0}
                },
                {
                    "id": "coat", "type": "coat",
                    "position": [256, 300], "stroke_color": "#ffd700", "stroke_width": 2,
                    "motion": {"type": "float", "speed": 0.4, "amplitude": 4, "radius": 0, "phase": 0.5}
                },
                {
                    "id": "beard", "type": "beard",
                    "position": [256, 240], "color": "#e0e0e0",
                    "motion": {"type": "float", "speed": 0.4, "amplitude": 3, "radius": 0, "phase": 0.3}
                },
                {
                    "id": "wand", "type": "wand",
                    "position": [330, 280], "rotation": -25,
                    "motion": {"type": "wand_wave", "speed": 1.0, "amplitude": 15, "radius": 0, "phase": 0}
                },
            ]
        }

    def _generate_mcp_demo_json(self) -> dict:
        """Generate the MCP node graph demo as JSON."""
        nodes = []
        labels = ["Gmail", "Yahoo", "Drive", "Chrome", "Vault", "OpenAI"]
        statuses = [1, 1, 1, 1, 1, 2]
        n = 6

        nodes.append({
            "id": "mcp_core", "type": "mcp_node",
            "position": [400, 300], "scale": 1.5,
            "node_label": "MCP", "node_status": 1,
            "motion": {"type": "glow", "speed": 0.3, "amplitude": 0, "radius": 0, "phase": 0}
        })

        for i, label in enumerate(labels):
            import math
            angle = (i / n) * 2 * math.pi
            radius = 180
            x = 400 + math.cos(angle) * radius
            y = 300 + math.sin(angle) * radius
            nodes.append({
                "id": f"node_{label}", "type": "mcp_node",
                "position": [x, y], "scale": 0.8,
                "node_label": label, "node_status": statuses[i],
                "motion": {"type": "pulse", "speed": 0.5 + i * 0.1, "amplitude": 5, "radius": 0, "phase": i * 0.15}
            })

        return {
            "name": "MCP Node Graph",
            "width": 800, "height": 600,
            "background": [0.02, 0.02, 0.06],
            "duration": 6.0, "fps": 60,
            "objects": nodes
        }

    def _load_default_scene(self):
        """Load the default wizard demo scene on startup."""
        self.json_editor.setPlainText(json.dumps(self._generate_demo_json(), indent=2))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wizard SVG Animation Studio")

    # Dark theme
    app.setStyle("Fusion")
    from PyQt6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    app.setPalette(palette)

    studio = WizardStudio()
    studio.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
