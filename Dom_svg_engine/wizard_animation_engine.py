#!/usr/bin/env python3
"""
Wizard SVG Animation Engine — Live Preview
C engine (libwizard.dylib) + PyQt6 real-time animation renderer.
"""

import sys
import os
import ctypes
import time
import math
from ctypes import c_float, c_int, c_char, c_char_p, POINTER, Structure, byref

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QSlider, QCheckBox, QGroupBox, QFormLayout, QFileDialog
)
from PyQt6.QtCore import Qt, QByteArray, QTimer, QPointF
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QFont, QPainter, QImage
from PyQt6.QtSvg import QSvgRenderer


# ─── C Engine FFI ───

LIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libwizard.dylib")

class Vec2(ctypes.Structure):
    _fields_ = [("x", c_float), ("y", c_float)]

class Keyframe(ctypes.Structure):
    _fields_ = [
        ("t", c_float),
        ("pos", Vec2),
        ("rot", c_float),
        ("scale", c_float),
        ("opacity", c_float),
    ]

class Object(ctypes.Structure):
    _fields_ = [
        ("id", c_char * 32),
        ("type", c_char * 32),
        ("pos", Vec2),
        ("rot", c_float),
        ("scale", c_float),
        ("opacity", c_float),
        ("color", c_char * 16),
        ("keys", Keyframe * 16),
        ("key_count", c_int),
    ]

class Particle(ctypes.Structure):
    _fields_ = [
        ("pos", Vec2),
        ("vel", Vec2),
        ("life", c_float),
        ("max_life", c_float),
        ("color", c_char * 16),
    ]

class Scene(ctypes.Structure):
    _fields_ = [
        ("w", c_int),
        ("h", c_int),
        ("objects", Object * 128),
        ("obj_count", c_int),
        ("particles", Particle * 256),
        ("particle_count", c_int),
        ("seed", ctypes.c_uint),
        ("bg_color", c_char * 16),
    ]


SCENE_PRESETS = {
    "Classic Blue": "build_demo",
    "Fire Mage": "build_fire_mage",
    "Arcane Cyan": "build_arcane",
    "Storm Caller": "build_storm",
}


class WizardEngine:
    """C engine bridge via ctypes."""

    def __init__(self):
        self.lib = ctypes.CDLL(LIB_PATH)

        # render_svg(Scene* s, float t, char* buffer, int bufsize) -> int
        self.lib.render_svg.argtypes = [POINTER(Scene), c_float, c_char_p, c_int]
        self.lib.render_svg.restype = c_int

        # scene_init(Scene*, int w, int h)
        self.lib.scene_init.argtypes = [POINTER(Scene), c_int, c_int]
        self.lib.scene_init.restype = None

        # build functions
        for fname in SCENE_PRESETS.values():
            func = getattr(self.lib, fname)
            func.argtypes = [POINTER(Scene)]
            func.restype = None

        # spawn_particle(Scene*, Vec2 p, const char* color)
        self.lib.spawn_particle.argtypes = [POINTER(Scene), Vec2, c_char_p]
        self.lib.spawn_particle.restype = None

        # update_particles(Scene*, float dt)
        self.lib.update_particles.argtypes = [POINTER(Scene), c_float]
        self.lib.update_particles.restype = None

        self.scene = Scene()
        self.buffer = ctypes.create_string_buffer(65536)
        self.set_preset("Classic Blue")

    def set_preset(self, preset_name):
        func_name = SCENE_PRESETS.get(preset_name, "build_demo")
        func = getattr(self.lib, func_name)
        func(byref(self.scene))

    def render(self, t):
        """Render scene at time t (0.0-1.0) and return SVG bytes."""
        # Spawn particles each frame
        for _ in range(6):
            self.lib.spawn_particle(byref(self.scene), Vec2(390, 240), b"#7ec8ff")
        self.lib.update_particles(byref(self.scene), c_float(0.05))

        length = self.lib.render_svg(byref(self.scene), c_float(t), self.buffer, 65536)
        if length > 0:
            return self.buffer.raw[:length]
        return b""


class AnimationPreviewUI(QWidget):
    """Live animation preview with playback controls."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("\U0001f9d9 Wizard Animation Engine — Live Preview")
        self.setMinimumSize(700, 700)
        self.setStyleSheet("""
            QWidget { background: #0d1117; color: #fff; }
            QGroupBox { border: 1px solid #333; border-radius: 6px; margin-top: 12px; padding-top: 18px; color: #aaa; font-weight: bold; }
            QComboBox { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 5px; border-radius: 4px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1a1a2e; color: #fff; selection-background-color: #2196F3; }
            QSlider::groove:horizontal { background: #333; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #2196F3; width: 16px; margin: -5px 0; border-radius: 8px; }
            QSlider::sub-page:horizontal { background: #2196F3; border-radius: 3px; }
            QCheckBox { color: #ccc; }
        """)

        self.engine = WizardEngine()
        self.playing = True
        self.time = 0.0
        self.speed = 1.0
        self.loop = True
        self.last_frame_time = time.time()
        self.frame_count = 0
        self.fps = 0.0
        self.fps_timer = time.time()

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(15, 15, 15, 15)

        # Title
        title = QLabel("\U0001f9d9 Wizard Animation Engine — C Core + Live Preview")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFD700;")
        layout.addWidget(title)

        # SVG Preview
        self.svg_widget = QSvgWidget()
        self.svg_widget.setFixedSize(512, 512)
        self.svg_widget.setStyleSheet("border: 2px solid #333; border-radius: 12px; background: #000;")
        layout.addWidget(self.svg_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Status
        self.status = QLabel("Playing")
        self.status.setStyleSheet("color: #4CAF50; font-size: 12px; font-family: 'Menlo', monospace;")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        # Controls
        controls = QGroupBox("Playback Controls")
        ctrl_layout = QFormLayout(controls)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(SCENE_PRESETS.keys())
        self.preset_combo.currentTextChanged.connect(self.change_preset)
        ctrl_layout.addRow("Scene:", self.preset_combo)

        speed_row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(10, 300)
        self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(self.change_speed)
        self.speed_label = QLabel("1.0x")
        self.speed_label.setFixedWidth(40)
        speed_row.addWidget(self.speed_slider)
        speed_row.addWidget(self.speed_label)
        ctrl_layout.addRow("Speed:", speed_row)

        self.loop_check = QCheckBox("Loop")
        self.loop_check.setChecked(True)
        self.loop_check.stateChanged.connect(self.toggle_loop)
        ctrl_layout.addRow("", self.loop_check)

        layout.addWidget(controls)

        # Buttons
        btn_row = QHBoxLayout()
        btn_blue = "QPushButton { background: #2196F3; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #1976D2; }"
        btn_green = "QPushButton { background: #4CAF50; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #388E3C; }"
        btn_orange = "QPushButton { background: #FF9800; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #F57C00; }"

        self.play_btn = QPushButton("\u23f8  Pause")
        self.play_btn.setStyleSheet(btn_blue)
        self.play_btn.clicked.connect(self.toggle_play)
        btn_row.addWidget(self.play_btn)

        self.reset_btn = QPushButton("\u21ba  Reset")
        self.reset_btn.setStyleSheet(btn_orange)
        self.reset_btn.clicked.connect(self.reset_time)
        btn_row.addWidget(self.reset_btn)

        self.save_btn = QPushButton("\U0001f4be  Save Frame SVG")
        self.save_btn.setStyleSheet(btn_green)
        self.save_btn.clicked.connect(self.save_frame)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)  # ~60fps

    def tick(self):
        now = time.time()
        dt = now - self.last_frame_time
        self.last_frame_time = now

        if self.playing:
            self.time += dt * self.speed * 0.5  # 0.5 = one full loop in 2 seconds
            if self.time >= 1.0:
                if self.loop:
                    self.time = self.time % 1.0
                else:
                    self.time = 1.0
                    self.playing = False
                    self.play_btn.setText("\u25b6  Play")

        # Render via C engine
        svg_bytes = self.engine.render(self.time)
        if svg_bytes:
            self.svg_widget.load(QByteArray(svg_bytes))

        # FPS counter
        self.frame_count += 1
        if now - self.fps_timer >= 1.0:
            self.fps = self.frame_count / (now - self.fps_timer)
            self.frame_count = 0
            self.fps_timer = now

        self.status.setText(
            f"t={self.time:.3f}  |  FPS: {self.fps:.0f}  |  Particles: {self.engine.scene.particle_count}  |  Objects: {self.engine.scene.obj_count}  |  {'Playing' if self.playing else 'Paused'}"
        )

    def toggle_play(self):
        self.playing = not self.playing
        self.play_btn.setText("\u23f8  Pause" if self.playing else "\u25b6  Play")
        if self.playing and self.time >= 1.0:
            self.time = 0.0

    def reset_time(self):
        self.time = 0.0

    def change_speed(self, val):
        self.speed = val / 100.0
        self.speed_label.setText(f"{self.speed:.1f}x")

    def toggle_loop(self):
        self.loop = self.loop_check.isChecked()

    def change_preset(self, name):
        self.engine.set_preset(name)
        self.time = 0.0

    def save_frame(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save SVG Frame", "wizard_frame.svg", "SVG files (*.svg)")
        if path:
            svg_bytes = self.engine.render(self.time)
            with open(path, "wb") as f:
                f.write(svg_bytes)
            self.status.setText(f"Saved: {path}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wizard Animation Engine")
    w = AnimationPreviewUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
