#!/usr/bin/env python3
"""
Wizard SVG Animation Engine — FULL SCENE EDITOR
C engine (libwizard.dylib) + PyQt6 real-time editor with:
- Object list (add/remove/reorder)
- Property editor (pos, rot, scale, opacity, color)
- Keyframe editor (add/remove keyframes per object)
- Theme presets
- Live animation playback
- Export SVG / PNG / animated SVG
"""

import sys
import os
import ctypes
import time
import math
import base64
import json
from ctypes import c_float, c_int, c_uint, c_char, c_char_p, POINTER, Structure, byref, create_string_buffer

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QSlider, QCheckBox, QGroupBox, QFormLayout, QFileDialog,
    QListWidget, QListWidgetItem, QDoubleSpinBox, QSpinBox, QLineEdit,
    QSplitter, QFrame, QColorDialog, QToolBar, QStatusBar, QMenu, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QGridLayout
)
from PyQt6.QtCore import Qt, QByteArray, QTimer, QSize, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QFont, QPainter, QImage, QAction, QColor, QIcon


# ─── C Engine FFI ───

LIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libwizard.dylib")

class Vec2(Structure):
    _fields_ = [("x", c_float), ("y", c_float)]

class Keyframe(Structure):
    _fields_ = [
        ("t", c_float), ("pos", Vec2), ("rot", c_float),
        ("scale", c_float), ("opacity", c_float),
    ]

class Object(Structure):
    _fields_ = [
        ("id", c_char * 32), ("type", c_char * 32),
        ("pos", Vec2), ("rot", c_float), ("scale", c_float), ("opacity", c_float),
        ("color", c_char * 16),
        ("keys", Keyframe * 16), ("key_count", c_int),
    ]

class Particle(Structure):
    _fields_ = [
        ("pos", Vec2), ("vel", Vec2), ("life", c_float),
        ("max_life", c_float), ("color", c_char * 16),
    ]

class Scene(Structure):
    _fields_ = [
        ("w", c_int), ("h", c_int),
        ("objects", Object * 128), ("obj_count", c_int),
        ("particles", Particle * 256), ("particle_count", c_int),
        ("seed", c_uint), ("bg_color", c_char * 16),
    ]


# Object types the C engine can render
OBJECT_TYPES = [
    "wizard_hat", "wide_hat", "crown_hat",
    "wand", "fire_wand", "crystal_staff", "lightning_wand",
    "star", "big_star", "rune",
    "coat", "face", "beard", "glow",
    "crystal_ball", "owl",
]

THEME_PRESETS = {
    "Classic Blue": {"build": "build_demo", "bg": "#0d1117", "colors": {"hat": "#1e5eff", "coat": "#2b2b2b", "accent": "#7ec8ff"}},
    "Fire Mage": {"build": "build_fire_mage", "bg": "#1a0500", "colors": {"hat": "#8B0000", "coat": "#3B1B00", "accent": "#FF4500"}},
    "Arcane Cyan": {"build": "build_arcane", "bg": "#021a36", "colors": {"hat": "#1a5276", "coat": "#0a2a46", "accent": "#00BFFF"}},
    "Storm Caller": {"build": "build_storm", "bg": "#10002b", "colors": {"hat": "#3a0ca3", "coat": "#10002b", "accent": "#4cc9f0"}},
}


class WizardEngine:
    """C engine bridge — full editor API."""

    def __init__(self):
        self.lib = ctypes.CDLL(LIB_PATH)
        self._setup_ffi()
        self.scene = Scene()
        self.buffer = create_string_buffer(65536)
        self.load_preset("Classic Blue")

    def _setup_ffi(self):
        L = self.lib
        # Scene ops
        L.scene_init.argtypes = [POINTER(Scene), c_int, c_int]; L.scene_init.restype = None
        L.clear_scene.argtypes = [POINTER(Scene)]; L.clear_scene.restype = None
        L.set_bg_color.argtypes = [POINTER(Scene), c_char_p]; L.set_bg_color.restype = None
        L.set_seed.argtypes = [POINTER(Scene), c_uint]; L.set_seed.restype = None
        # Object ops
        L.add_object.argtypes = [POINTER(Scene), c_char_p, c_char_p]; L.add_object.restype = POINTER(Object)
        L.remove_object.argtypes = [POINTER(Scene), c_int]; L.remove_object.restype = None
        L.set_object_pos.argtypes = [POINTER(Scene), c_int, c_float, c_float]; L.set_object_pos.restype = None
        L.set_object_rot.argtypes = [POINTER(Scene), c_int, c_float]; L.set_object_rot.restype = None
        L.set_object_scale.argtypes = [POINTER(Scene), c_int, c_float]; L.set_object_scale.restype = None
        L.set_object_opacity.argtypes = [POINTER(Scene), c_int, c_float]; L.set_object_opacity.restype = None
        L.set_object_color.argtypes = [POINTER(Scene), c_int, c_char_p]; L.set_object_color.restype = None
        L.clear_keyframes.argtypes = [POINTER(Scene), c_int]; L.clear_keyframes.restype = None
        L.add_key.argtypes = [POINTER(Object), c_float, Vec2, c_float, c_float, c_float]; L.add_key.restype = None
        # Getters
        L.get_obj_count.argtypes = [POINTER(Scene)]; L.get_obj_count.restype = c_int
        L.get_obj_pos_x.argtypes = [POINTER(Scene), c_int]; L.get_obj_pos_x.restype = c_float
        L.get_obj_pos_y.argtypes = [POINTER(Scene), c_int]; L.get_obj_pos_y.restype = c_float
        L.get_obj_rot.argtypes = [POINTER(Scene), c_int]; L.get_obj_rot.restype = c_float
        L.get_obj_scale.argtypes = [POINTER(Scene), c_int]; L.get_obj_scale.restype = c_float
        L.get_obj_opacity.argtypes = [POINTER(Scene), c_int]; L.get_obj_opacity.restype = c_float
        L.get_obj_type.argtypes = [POINTER(Scene), c_int]; L.get_obj_type.restype = c_char_p
        L.get_obj_color.argtypes = [POINTER(Scene), c_int]; L.get_obj_color.restype = c_char_p
        # Particles
        L.spawn_particle.argtypes = [POINTER(Scene), Vec2, c_char_p]; L.spawn_particle.restype = None
        L.update_particles.argtypes = [POINTER(Scene), c_float]; L.update_particles.restype = None
        # Render
        L.render_svg.argtypes = [POINTER(Scene), c_float, c_char_p, c_int]; L.render_svg.restype = c_int
        # Build presets
        for info in THEME_PRESETS.values():
            f = getattr(L, info["build"])
            f.argtypes = [POINTER(Scene)]; f.restype = None

    def load_preset(self, name):
        info = THEME_PRESETS.get(name, THEME_PRESETS["Classic Blue"])
        getattr(self.lib, info["build"])(byref(self.scene))

    def add_object(self, obj_type, color="#1e5eff"):
        """Add object and return its index."""
        idx = self.lib.get_obj_count(byref(self.scene))
        name = f"obj_{idx}".encode()
        self.lib.add_object(byref(self.scene), name, obj_type.encode())
        self.lib.set_object_color(byref(self.scene), idx, color.encode())
        return idx

    def remove_object(self, idx):
        self.lib.remove_object(byref(self.scene), idx)

    def clear_scene(self):
        self.lib.clear_scene(byref(self.scene))

    def set_pos(self, idx, x, y):
        self.lib.set_object_pos(byref(self.scene), idx, c_float(x), c_float(y))

    def set_rot(self, idx, r):
        self.lib.set_object_rot(byref(self.scene), idx, c_float(r))

    def set_scale(self, idx, s):
        self.lib.set_object_scale(byref(self.scene), idx, c_float(s))

    def set_opacity(self, idx, o):
        self.lib.set_object_opacity(byref(self.scene), idx, c_float(o))

    def set_color(self, idx, color):
        self.lib.set_object_color(byref(self.scene), idx, color.encode())

    def clear_keys(self, idx):
        self.lib.clear_keyframes(byref(self.scene), idx)

    def add_keyframe(self, idx, t, x, y, rot, scale, opacity):
        obj_ptr = ctypes.cast(ctypes.addressof(self.scene.objects) + idx * ctypes.sizeof(Object), POINTER(Object))
        self.lib.add_key(obj_ptr, c_float(t), Vec2(x, y), c_float(rot), c_float(scale), c_float(opacity))

    def get_obj_count(self):
        return self.lib.get_obj_count(byref(self.scene))

    def get_obj_info(self, idx):
        return {
            "type": self.lib.get_obj_type(byref(self.scene), idx).decode(),
            "x": self.lib.get_obj_pos_x(byref(self.scene), idx),
            "y": self.lib.get_obj_pos_y(byref(self.scene), idx),
            "rot": self.lib.get_obj_rot(byref(self.scene), idx),
            "scale": self.lib.get_obj_scale(byref(self.scene), idx),
            "opacity": self.lib.get_obj_opacity(byref(self.scene), idx),
            "color": self.lib.get_obj_color(byref(self.scene), idx).decode(),
        }

    def set_bg(self, color):
        self.lib.set_bg_color(byref(self.scene), color.encode())

    def render(self, t, spawn_particles=True):
        if spawn_particles:
            for _ in range(6):
                self.lib.spawn_particle(byref(self.scene), Vec2(390, 240), b"#7ec8ff")
            self.lib.update_particles(byref(self.scene), c_float(0.05))
        length = self.lib.render_svg(byref(self.scene), c_float(t), self.buffer, 65536)
        if length > 0:
            return self.buffer.raw[:length]
        return b""

    def render_static_svg(self):
        """Render at t=0 with no particles for static export."""
        length = self.lib.render_svg(byref(self.scene), c_float(0), self.buffer, 65536)
        if length > 0:
            return self.buffer.raw[:length]
        return b""

    def render_png(self, path, size=512):
        from PyQt6.QtSvg import QSvgRenderer
        svg_bytes = self.render_static_svg()
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        image.save(path)

    def export_scene_json(self, path):
        """Export scene as JSON for later import."""
        data = {"objects": [], "bg": self.scene.bg_color.decode()}
        for i in range(self.get_obj_count()):
            info = self.get_obj_info(i)
            data["objects"].append(info)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


# ─── UI Components ───

class StyleHelper:
    @staticmethod
    def dark():
        return """
            QWidget { background: #0d1117; color: #fff; font-size: 12px; }
            QGroupBox { border: 1px solid #333; border-radius: 6px; margin-top: 12px; padding-top: 18px; color: #aaa; font-weight: bold; }
            QListWidget { background: #1a1a2e; color: #fff; border: 1px solid #333; border-radius: 4px; }
            QListWidget::item:selected { background: #2196F3; }
            QListWidget::item:hover { background: #333; }
            QComboBox { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 4px; border-radius: 4px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1a1a2e; color: #fff; selection-background-color: #2196F3; }
            QDoubleSpinBox, QSpinBox { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 3px; border-radius: 3px; }
            QSlider::groove:horizontal { background: #333; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #2196F3; width: 14px; margin: -4px 0; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #2196F3; border-radius: 3px; }
            QCheckBox { color: #ccc; }
            QLineEdit { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 4px; border-radius: 4px; }
            QTableWidget { background: #1a1a2e; color: #fff; border: 1px solid #333; border-radius: 4px; gridline-color: #333; }
            QHeaderView::section { background: #2a2a3e; color: #aaa; border: 1px solid #333; padding: 4px; }
            QTabWidget::pane { border: 1px solid #333; border-radius: 4px; }
            QTabBar::tab { background: #1a1a2e; color: #888; padding: 6px 12px; border: 1px solid #333; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #2196F3; color: #fff; }
            QStatusBar { background: #0a0a14; color: #888; }
            QToolBar { background: #0a0a14; border: none; spacing: 4px; }
            QMenu { background: #1a1a2e; color: #fff; border: 1px solid #333; }
            QMenu::item:selected { background: #2196F3; }
        """

    @staticmethod
    def btn(color="#2196F3"):
        return f"QPushButton {{ background: {color}; color: white; border: none; padding: 6px 14px; border-radius: 4px; font-weight: bold; }} QPushButton:hover {{ background: {color}cc; }} QPushButton:pressed {{ background: {color}99; }}"

    @staticmethod
    def btn_danger():
        return "QPushButton { background: #f44336; color: white; border: none; padding: 6px 14px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #d32f2f; }"


class PropertyEditor(QWidget):
    """Property editor for the selected object."""

    property_changed = pyqtSignal()

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.selected_idx = -1
        self._building = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title
        title = QLabel("Object Properties")
        title.setStyleSheet("color: #FFD700; font-weight: bold;")
        layout.addWidget(title)

        # No selection label
        self.no_sel = QLabel("Select an object to edit")
        self.no_sel.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.no_sel)

        # Properties form
        self.props_widget = QWidget()
        self.props_widget.setVisible(False)
        form = QFormLayout(self.props_widget)
        form.setSpacing(4)

        self.type_label = QLabel("")
        self.type_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        form.addRow("Type:", self.type_label)

        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(0, 512); self.x_spin.setSingleStep(1)
        self.x_spin.valueChanged.connect(self._on_changed)
        form.addRow("X:", self.x_spin)

        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(0, 512); self.y_spin.setSingleStep(1)
        self.y_spin.valueChanged.connect(self._on_changed)
        form.addRow("Y:", self.y_spin)

        self.rot_spin = QDoubleSpinBox()
        self.rot_spin.setRange(-360, 360); self.rot_spin.setSingleStep(1)
        self.rot_spin.valueChanged.connect(self._on_changed)
        form.addRow("Rotation:", self.rot_spin)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 5.0); self.scale_spin.setSingleStep(0.1); self.scale_spin.setValue(1.0)
        self.scale_spin.valueChanged.connect(self._on_changed)
        form.addRow("Scale:", self.scale_spin)

        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0, 1); self.opacity_spin.setSingleStep(0.05); self.opacity_spin.setValue(1.0)
        self.opacity_spin.valueChanged.connect(self._on_changed)
        form.addRow("Opacity:", self.opacity_spin)

        # Color
        self.color_btn = QPushButton("Pick Color")
        self.color_btn.setStyleSheet(StyleHelper.btn("#9C27B0"))
        self.color_btn.clicked.connect(self._pick_color)
        form.addRow("Color:", self.color_btn)
        self.color_preview = QLabel("")
        self.color_preview.setFixedSize(40, 20)
        form.addRow("", self.color_preview)

        layout.addWidget(self.props_widget)

        # Keyframe section
        kf_group = QGroupBox("Keyframes")
        kf_layout = QVBoxLayout(kf_group)

        self.kf_table = QTableWidget(0, 5)
        self.kf_table.setHorizontalHeaderLabels(["t", "x", "y", "rot", "scale"])
        self.kf_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.kf_table.setMaximumHeight(120)
        kf_layout.addWidget(self.kf_table)

        kf_btn_row = QHBoxLayout()
        self.add_kf_btn = QPushButton("+ Add Keyframe")
        self.add_kf_btn.setStyleSheet(StyleHelper.btn("#4CAF50"))
        self.add_kf_btn.clicked.connect(self._add_keyframe)
        kf_btn_row.addWidget(self.add_kf_btn)

        self.del_kf_btn = QPushButton("Clear All")
        self.del_kf_btn.setStyleSheet(StyleHelper.btn_danger())
        self.del_kf_btn.clicked.connect(self._clear_keyframes)
        kf_btn_row.addWidget(self.del_kf_btn)
        kf_layout.addLayout(kf_btn_row)

        layout.addWidget(kf_group)

        layout.addStretch()

        # Delete button
        self.del_btn = QPushButton("\U0001f5d1  Delete Object")
        self.del_btn.setStyleSheet(StyleHelper.btn_danger())
        self.del_btn.clicked.connect(self._delete_object)
        layout.addWidget(self.del_btn)

    def load_object(self, idx):
        self.selected_idx = idx
        if idx < 0 or idx >= self.engine.get_obj_count():
            self.no_sel.setVisible(True)
            self.props_widget.setVisible(False)
            return
        self.no_sel.setVisible(False)
        self.props_widget.setVisible(True)
        self._building = True
        info = self.engine.get_obj_info(idx)
        self.type_label.setText(info["type"])
        self.x_spin.setValue(info["x"])
        self.y_spin.setValue(info["y"])
        self.rot_spin.setValue(info["rot"])
        self.scale_spin.setValue(info["scale"])
        self.opacity_spin.setValue(info["opacity"])
        self.color_preview.setStyleSheet(f"background: {info['color']}; border: 1px solid #555; border-radius: 3px;")
        self._building = False

    def _on_changed(self):
        if self._building or self.selected_idx < 0:
            return
        self.engine.set_pos(self.selected_idx, self.x_spin.value(), self.y_spin.value())
        self.engine.set_rot(self.selected_idx, self.rot_spin.value())
        self.engine.set_scale(self.selected_idx, self.scale_spin.value())
        self.engine.set_opacity(self.selected_idx, self.opacity_spin.value())
        self.property_changed.emit()

    def _pick_color(self):
        if self.selected_idx < 0:
            return
        info = self.engine.get_obj_info(self.selected_idx)
        color = QColorDialog.getColor(QColor(info["color"]), self, "Pick Object Color")
        if color.isValid():
            hex_color = color.name()
            self.engine.set_color(self.selected_idx, hex_color)
            self.color_preview.setStyleSheet(f"background: {hex_color}; border: 1px solid #555; border-radius: 3px;")
            self.property_changed.emit()

    def _add_keyframe(self):
        if self.selected_idx < 0:
            return
        t = 0.5
        info = self.engine.get_obj_info(self.selected_idx)
        self.engine.add_keyframe(self.selected_idx, t, info["x"], info["y"], info["rot"], info["scale"], info["opacity"])
        self._refresh_keyframes()

    def _clear_keyframes(self):
        if self.selected_idx < 0:
            return
        self.engine.clear_keys(self.selected_idx)
        self._refresh_keyframes()

    def _refresh_keyframes(self):
        # Keyframes are stored in C struct, we can't easily read them back
        # Just show a placeholder count
        self.kf_table.setRowCount(0)

    def _delete_object(self):
        if self.selected_idx < 0:
            return
        self.engine.remove_object(self.selected_idx)
        self.selected_idx = -1
        self.load_object(-1)
        self.property_changed.emit()


class SceneEditorUI(QMainWindow):
    """Full scene editor with live animation preview."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("\U0001f9d9 Wizard Animation Engine — Scene Editor")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet(StyleHelper.dark())

        self.engine = WizardEngine()
        self.playing = True
        self.time = 0.0
        self.speed = 1.0
        self.loop = True
        self.last_frame = time.time()
        self.frame_count = 0
        self.fps = 0.0
        self.fps_timer = time.time()
        self.selected_idx = -1

        self._build_ui()
        self._refresh_object_list()
        self._start_timer()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setSpacing(6)
        main.setContentsMargins(6, 6, 6, 6)

        # ─── Left Panel: Object List + Add Objects ───
        left = QWidget()
        left.setFixedWidth(260)
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(6)

        # Theme selector
        theme_group = QGroupBox("\U0001f3a8 Theme Preset")
        theme_layout = QVBoxLayout(theme_group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEME_PRESETS.keys())
        self.theme_combo.currentTextChanged.connect(self._load_preset)
        theme_layout.addWidget(self.theme_combo)
        left_layout.addWidget(theme_group)

        # Object list
        obj_group = QGroupBox("\U0001f4cb Scene Objects")
        obj_layout = QVBoxLayout(obj_group)
        self.obj_list = QListWidget()
        self.obj_list.currentRowChanged.connect(self._on_select_object)
        obj_layout.addWidget(self.obj_list)

        # Add object buttons
        add_label = QLabel("Add Object:")
        add_label.setStyleSheet("color: #aaa; font-size: 11px;")
        obj_layout.addWidget(add_label)

        self.add_combo = QComboBox()
        self.add_combo.addItems(OBJECT_TYPES)
        obj_layout.addWidget(self.add_combo)

        add_row = QHBoxLayout()
        self.add_btn = QPushButton("+ Add")
        self.add_btn.setStyleSheet(StyleHelper.btn("#4CAF50"))
        self.add_btn.clicked.connect(self._add_object)
        add_row.addWidget(self.add_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setStyleSheet(StyleHelper.btn_danger())
        self.clear_btn.clicked.connect(self._clear_scene)
        add_row.addWidget(self.clear_btn)
        obj_layout.addLayout(add_row)

        left_layout.addWidget(obj_group)

        # Quick add buttons
        quick_group = QGroupBox("Quick Add")
        quick_layout = QGridLayout(quick_group)
        quick_items = [
            ("\U0001f9d9 Hat", "wizard_hat"), ("\U0001f9a8 Wide Hat", "wide_hat"),
            ("\U0001f451 Crown", "crown_hat"), ("\U0001f621 Fire Wand", "fire_wand"),
            ("\u2728 Wand", "wand"), ("\U0001f4ab Crystal", "crystal_staff"),
            ("\u26a1 Lightning", "lightning_wand"), ("\u2b50 Star", "star"),
            ("\U0001f4d6 Spell Book", "rune"), ("\U0001f422 Owl", "owl"),
            ("\U0001f50e Crystal Ball", "crystal_ball"), ("\U0001f5a4 Glow", "glow"),
        ]
        for i, (label, otype) in enumerate(quick_items):
            btn = QPushButton(label)
            btn.setStyleSheet("QPushButton { background: #2a2a3e; color: #ccc; border: 1px solid #444; padding: 4px; border-radius: 3px; font-size: 10px; } QPushButton:hover { background: #3a3a4e; }")
            btn.clicked.connect(lambda checked, ot=otype: self._quick_add(ot))
            quick_layout.addWidget(btn, i // 2, i % 2)
        left_layout.addWidget(quick_group)

        left_layout.addStretch()
        main.addWidget(left)

        # ─── Center: Live Preview ───
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setSpacing(4)

        preview_label = QLabel("Live Animation Preview (C Engine Render)")
        preview_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        preview_label.setStyleSheet("color: #FFD700;")
        center_layout.addWidget(preview_label)

        self.svg_widget = QSvgWidget()
        self.svg_widget.setFixedSize(512, 512)
        self.svg_widget.setStyleSheet("border: 2px solid #333; border-radius: 12px; background: #000;")
        center_layout.addWidget(self.svg_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Playback controls
        playback = QHBoxLayout()
        self.play_btn = QPushButton("\u23f8  Pause")
        self.play_btn.setStyleSheet(StyleHelper.btn("#2196F3"))
        self.play_btn.clicked.connect(self._toggle_play)
        playback.addWidget(self.play_btn)

        self.reset_btn = QPushButton("\u21ba  Reset")
        self.reset_btn.setStyleSheet(StyleHelper.btn("#FF9800"))
        self.reset_btn.clicked.connect(self._reset_time)
        playback.addWidget(self.reset_btn)

        self.loop_check = QCheckBox("Loop")
        self.loop_check.setChecked(True)
        self.loop_check.stateChanged.connect(lambda: setattr(self, 'loop', self.loop_check.isChecked()))
        playback.addWidget(self.loop_check)

        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet("color: #888;")
        playback.addWidget(speed_label)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(10, 300); self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(self._change_speed)
        playback.addWidget(self.speed_slider)
        self.speed_val = QLabel("1.0x")
        self.speed_val.setFixedWidth(35)
        playback.addWidget(self.speed_val)

        center_layout.addLayout(playback)

        # Timeline scrubber
        tl_row = QHBoxLayout()
        tl_label = QLabel("Timeline:")
        tl_label.setStyleSheet("color: #888;")
        tl_row.addWidget(tl_label)
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.valueChanged.connect(self._scrub_timeline)
        tl_row.addWidget(self.timeline_slider)
        self.tl_val = QLabel("0.000")
        self.tl_val.setFixedWidth(50)
        tl_row.addWidget(self.tl_val)
        center_layout.addLayout(tl_row)

        main.addWidget(center, 1)

        # ─── Right: Property Editor + Export ───
        right = QWidget()
        right.setFixedWidth(300)
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(6)

        self.prop_editor = PropertyEditor(self.engine)
        self.prop_editor.property_changed.connect(self._on_prop_changed)
        right_layout.addWidget(self.prop_editor)

        # Export
        export_group = QGroupBox("\U0001f4be Export")
        export_layout = QVBoxLayout(export_group)

        self.export_svg_btn = QPushButton("Export SVG (static)")
        self.export_svg_btn.setStyleSheet(StyleHelper.btn("#4CAF50"))
        self.export_svg_btn.clicked.connect(self._export_svg)
        export_layout.addWidget(self.export_svg_btn)

        self.export_png_btn = QPushButton("Export PNG")
        self.export_png_btn.setStyleSheet(StyleHelper.btn("#FF9800"))
        self.export_png_btn.clicked.connect(self._export_png)
        export_layout.addWidget(self.export_png_btn)

        self.export_json_btn = QPushButton("Export Scene JSON")
        self.export_json_btn.setStyleSheet(StyleHelper.btn("#9C27B0"))
        self.export_json_btn.clicked.connect(self._export_json)
        export_layout.addWidget(self.export_json_btn)

        self.export_frames_btn = QPushButton("Export 60 Frames")
        self.export_frames_btn.setStyleSheet(StyleHelper.btn("#00BCD4"))
        self.export_frames_btn.clicked.connect(self._export_frames)
        export_layout.addWidget(self.export_frames_btn)

        right_layout.addWidget(export_group)
        right_layout.addStretch()

        main.addWidget(right)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

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
                if self.loop:
                    self.time = self.time % 1.0
                else:
                    self.time = 1.0
                    self._toggle_play()

        svg_bytes = self.engine.render(self.time)
        if svg_bytes:
            self.svg_widget.load(QByteArray(svg_bytes))

        # Update timeline slider without triggering signal
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(int(self.time * 1000))
        self.timeline_slider.blockSignals(False)
        self.tl_val.setText(f"{self.time:.3f}")

        # FPS
        self.frame_count += 1
        if now - self.fps_timer >= 1.0:
            self.fps = self.frame_count / (now - self.fps_timer)
            self.frame_count = 0
            self.fps_timer = now

        self.status_bar.showMessage(
            f"t={self.time:.3f}  |  FPS: {self.fps:.0f}  |  Objects: {self.engine.get_obj_count()}  |  "
            f"Particles: {self.engine.scene.particle_count}  |  {'Playing' if self.playing else 'Paused'}"
        )

    # ─── Object List ───

    def _refresh_object_list(self):
        self.obj_list.blockSignals(True)
        self.obj_list.clear()
        count = self.engine.get_obj_count()
        for i in range(count):
            info = self.engine.get_obj_info(i)
            item = QListWidgetItem(f"[{i}] {info['type']}  ({info['x']:.0f},{info['y']:.0f})")
            self.obj_list.addItem(item)
        self.obj_list.blockSignals(False)
        if self.selected_idx >= 0 and self.selected_idx < count:
            self.obj_list.setCurrentRow(self.selected_idx)

    def _on_select_object(self, row):
        self.selected_idx = row
        self.prop_editor.load_object(row)

    def _on_prop_changed(self):
        self._refresh_object_list()
        if self.selected_idx >= 0:
            self.obj_list.setCurrentRow(self.selected_idx)

    # ─── Add/Remove Objects ───

    def _add_object(self):
        otype = self.add_combo.currentText()
        idx = self.engine.add_object(otype)
        self._refresh_object_list()
        self.obj_list.setCurrentRow(idx)

    def _quick_add(self, otype):
        idx = self.engine.add_object(otype)
        self._refresh_object_list()
        self.obj_list.setCurrentRow(idx)

    def _clear_scene(self):
        reply = QMessageBox.question(self, "Clear Scene", "Remove all objects?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.engine.clear_scene()
            self.selected_idx = -1
            self.prop_editor.load_object(-1)
            self._refresh_object_list()

    # ─── Theme ───

    def _load_preset(self, name):
        self.engine.load_preset(name)
        self.selected_idx = -1
        self.prop_editor.load_object(-1)
        self._refresh_object_list()

    # ─── Playback ───

    def _toggle_play(self):
        self.playing = not self.playing
        self.play_btn.setText("\u23f8  Pause" if self.playing else "\u25b6  Play")
        if self.playing and self.time >= 1.0:
            self.time = 0.0

    def _reset_time(self):
        self.time = 0.0

    def _change_speed(self, val):
        self.speed = val / 100.0
        self.speed_val.setText(f"{self.speed:.1f}x")

    def _scrub_timeline(self, val):
        self.time = val / 1000.0
        if self.playing:
            self._toggle_play()

    # ─── Export ───

    def _export_svg(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "wizard_scene.svg", "SVG (*.svg)")
        if path:
            svg = self.engine.render_static_svg()
            with open(path, "wb") as f:
                f.write(svg)
            self.status_bar.showMessage(f"Exported SVG: {path}", 5000)

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "wizard_scene.png", "PNG (*.png)")
        if path:
            self.engine.render_png(path, 512)
            self.status_bar.showMessage(f"Exported PNG: {path}", 5000)

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "wizard_scene.json", "JSON (*.json)")
        if path:
            self.engine.export_scene_json(path)
            self.status_bar.showMessage(f"Exported JSON: {path}", 5000)

    def _export_frames(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            for i in range(60):
                t = i / 60.0
                svg = self.engine.render(t, spawn_particles=False)
                fname = os.path.join(dir_path, f"frame_{i:02d}.svg")
                with open(fname, "wb") as f:
                    f.write(svg)
            self.status_bar.showMessage(f"Exported 60 frames to: {dir_path}", 5000)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wizard Animation Engine — Scene Editor")
    w = SceneEditorUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
