#!/usr/bin/env python3
"""
Voice Matcher GUI — Sleek modern interface.
Talk into your mic, it analyzes your voice live with a real-time spectrum
analyzer, then matches you to the closest Kokoro-82M voice.

Usage: python3 voice_matcher_gui.py
"""

# ── Standard library ─────────────────────────────────────────────────────────
import sys
import time
import math
from pathlib import Path

# ── Third-party ──────────────────────────────────────────────────────────────
import numpy as np

# ── PyQt6 ────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QComboBox,
    QSlider, QTabWidget, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QCheckBox
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QPointF, QRectF
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPainter, QPen, QLinearGradient, QBrush,
    QPolygonF, QPainterPath, QRadialGradient
)

# ── Backend (all workers, data, and audio helpers) ───────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from voice_matcher_workers import (
    MicMonitorWorker, CalibrationWorker, LiveRecordWorker,
    AnalysisWorker, MatchWorker, TTSWorker,
    load_reference_db, KOKORO_VOICES,
    list_input_devices, list_recordings, play_audio_file,
)

# ── Color palette ────────────────────────────────────────────────────────────
COL_BG          = QColor(12, 12, 16)       # main background (darker)
COL_BG_CARD     = QColor(22, 22, 28)       # card background
COL_BG_CARD_ALT = QColor(28, 28, 36)       # card background (alt)
COL_ACCENT      = QColor(0, 200, 180)      # teal accent
COL_ACCENT_2    = QColor(120, 80, 255)     # purple accent
COL_RECORD      = QColor(255, 60, 80)      # red-pink (record)
COL_RECORD_HOT  = QColor(255, 100, 120)    # hot pink (record active)
COL_TEXT        = QColor(225, 225, 232)    # main text
COL_TEXT_DIM    = QColor(120, 120, 135)    # dimmed text
COL_GOOD        = QColor(76, 220, 130)     # green (good match)
COL_WARN        = QColor(255, 200, 60)     # yellow (warning)
COL_BAD         = QColor(255, 90, 70)      # red (bad match)
COL_GRID        = QColor(35, 35, 45)       # grid lines
COL_BORDER      = QColor(38, 38, 48)       # subtle card borders

# ── Global stylesheet ────────────────────────────────────────────────────────
STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: rgb({COL_BG.red()}, {COL_BG.green()}, {COL_BG.blue()});
    color: rgb({COL_TEXT.red()}, {COL_TEXT.green()}, {COL_TEXT.blue()});
    font-family: "Helvetica Neue", Arial;
    font-size: 13px;
}}
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: rgb({COL_TEXT_DIM.red()}, {COL_TEXT_DIM.green()}, {COL_TEXT_DIM.blue()});
    padding: 8px 22px;
    margin-right: 1px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QTabBar::tab:selected {{
    color: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
    border-bottom: 2px solid rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
}}
QTabBar::tab:hover:!selected {{
    color: rgb({COL_TEXT.red()}, {COL_TEXT.green()}, {COL_TEXT.blue()});
}}
QGroupBox {{
    background-color: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()});
    border: 1px solid rgb({COL_BORDER.red()}, {COL_BORDER.green()}, {COL_BORDER.blue()});
    border-radius: 10px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
}}
QPushButton {{
    background-color: rgb({COL_BG_CARD_ALT.red()}, {COL_BG_CARD_ALT.green()}, {COL_BG_CARD_ALT.blue()});
    color: rgb({COL_TEXT.red()}, {COL_TEXT.green()}, {COL_TEXT.blue()});
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: rgb(42, 42, 54);
}}
QPushButton:pressed {{
    background-color: rgb(34, 34, 44);
}}
QPushButton:disabled {{
    color: rgb(60, 60, 72);
    background-color: rgb(26, 26, 32);
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: rgb(35, 35, 45);
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    background: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
    border-radius: 7px;
    margin: -5px 0;
}}
QSlider::handle:horizontal:hover {{
    background: rgb(0, 230, 205);
}}
QSlider::sub-page:horizontal {{
    background: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
    border-radius: 2px;
}}
QComboBox {{
    background: rgb({COL_BG_CARD_ALT.red()}, {COL_BG_CARD_ALT.green()}, {COL_BG_CARD_ALT.blue()});
    border: 1px solid rgb({COL_BORDER.red()}, {COL_BORDER.green()}, {COL_BORDER.blue()});
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()});
    border: 1px solid rgb({COL_BORDER.red()}, {COL_BORDER.green()}, {COL_BORDER.blue()});
    selection-background-color: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
    selection-color: black;
}}
QTextEdit {{
    background: rgb(16, 16, 22);
    border: 1px solid rgb({COL_BORDER.red()}, {COL_BORDER.green()}, {COL_BORDER.blue()});
    border-radius: 8px;
    padding: 10px;
    color: rgb({COL_TEXT.red()}, {COL_TEXT.green()}, {COL_TEXT.blue()});
}}
QTableWidget {{
    background: rgb(16, 16, 22);
    border: 1px solid rgb({COL_BORDER.red()}, {COL_BORDER.green()}, {COL_BORDER.blue()});
    border-radius: 8px;
    gridline-color: rgb(30, 30, 40);
    color: rgb({COL_TEXT.red()}, {COL_TEXT.green()}, {COL_TEXT.blue()});
    selection-background-color: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
    selection-color: black;
}}
QHeaderView::section {{
    background: rgb(26, 26, 34);
    color: rgb({COL_TEXT_DIM.red()}, {COL_TEXT_DIM.green()}, {COL_TEXT_DIM.blue()});
    border: none;
    padding: 6px 8px;
    font-weight: 600;
    font-size: 11px;
}}
QProgressBar {{
    background: rgb(22, 22, 30);
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: white;
    font-size: 10px;
}}
QProgressBar::chunk {{
    border-radius: 4px;
}}
QLabel {{
    color: rgb({COL_TEXT.red()}, {COL_TEXT.green()}, {COL_TEXT.blue()});
    background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()});
}}
QCheckBox {{
    color: rgb({COL_TEXT_DIM.red()}, {COL_TEXT_DIM.green()}, {COL_TEXT_DIM.blue()});
    font-size: 12px;
    spacing: 6px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1.5px solid rgb(50,50,62); border-radius: 3px;
    background: rgb(20,20,26);
}}
QCheckBox::indicator:checked {{
    background: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
    border-color: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
}}
"""


# =============================================================================
# UI helper functions
# =============================================================================

def make_card(title=None):
    """Create a styled card container with optional title header."""
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()});
            border: 1px solid rgb({COL_BORDER.red()}, {COL_BORDER.green()}, {COL_BORDER.blue()});
            border-radius: 10px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    if title:
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()}); "
            f"font-size: 11px; font-weight: 700; border: none; "
            f"background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()}); "
            f"letter-spacing: 2px; padding-bottom: 2px;"
        )
        layout.addWidget(lbl)
    return frame, layout


def styled_label(text, dim=False, size=12, bold=False):
    """Create a pre-styled QLabel with card background, padding and minimum height."""
    lbl = QLabel(text)
    c = COL_TEXT_DIM if dim else COL_TEXT
    weight = "700" if bold else "400"
    lbl.setStyleSheet(
        f"color: rgb({c.red()}, {c.green()}, {c.blue()}); "
        f"font-size: {size}px; font-weight: {weight}; "
        f"border: none; "
        f"background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()}); "
        f"padding: 1px 4px;"
    )
    lbl.setMinimumHeight(size + 6)
    return lbl


# =============================================================================
# Widgets — Mic level bar
# =============================================================================

class MicLevelBar(QWidget):
    """Live mic level bar with peak hold marker.
    Shows green/yellow/red zones and a peak hold line."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.level = 0.0
        self.peak = 0.0
        self.peak_decay = 0.0
        self.active = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(30)

    def set_level(self, level):
        if math.isnan(level) or math.isinf(level) or level < 0:
            level = 0
        self.level = max(0, min(level, 1.0))
        if self.level > self.peak:
            self.peak = self.level
            self.peak_decay = 0.0

    def set_peak(self, peak):
        self.peak = max(0, min(peak, 1.0))

    def _tick(self):
        self.peak_decay += 0.016
        self.peak -= self.peak_decay * 0.015
        self.peak = max(0, self.peak)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        pad = 2
        bar_w = w - pad * 2
        bar_h = h - pad * 2

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 20, 28))
        painter.drawRoundedRect(QRectF(pad, pad, bar_w, bar_h), 4, 4)

        # Zone markers (faint background segments)
        for frac, color in [(0.5, QColor(255, 200, 60, 25)),
                            (0.8, QColor(255, 80, 100, 25))]:
            x = pad + bar_w * frac
            painter.setPen(QPen(color, 1))
            painter.drawLine(QPointF(x, pad + 2), QPointF(x, pad + bar_h - 2))

        # Level fill
        lv = self.level
        fill_w = int(lv * bar_w)
        if fill_w > 2:
            # Gradient: green -> yellow -> red
            grad = QLinearGradient(pad, 0, pad + bar_w, 0)
            grad.setColorAt(0, QColor(0, 220, 130))
            grad.setColorAt(0.5, QColor(255, 200, 60))
            grad.setColorAt(0.8, QColor(255, 100, 80))
            grad.setColorAt(1.0, QColor(255, 60, 60))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(pad, pad, fill_w, bar_h), 4, 4)

        # Peak hold marker
        if self.peak > 0.02:
            px = pad + int(self.peak * bar_w)
            painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
            painter.drawLine(QPointF(px, pad), QPointF(px, pad + bar_h))

        # Label
        painter.setPen(QColor(200, 200, 210, 180))
        font = QFont("Helvetica Neue", 9)
        font.setBold(True)
        painter.setFont(font)
        label = f"MIC  {int(self.level * 100):3d}%"
        painter.drawText(QRectF(pad + 6, pad, bar_w - 12, bar_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

        painter.end()


# =============================================================================
# Widgets — Visualizer
# =============================================================================

class VisualizerWidget(QWidget):
    """Real-time audio visualizer with switchable modes:
       bars, wave, wave+bars, circular, oscilloscope."""

    MODE_BARS = 0
    MODE_WAVE = 1
    MODE_COMBO = 2
    MODE_CIRCULAR = 3
    MODE_OSC = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setMaximumHeight(280)
        self.mode = self.MODE_BARS
        self.num_bars = 48
        self.bar_values = np.zeros(self.num_bars, dtype=np.float64)
        self.peak_values = np.zeros(self.num_bars, dtype=np.float64)
        self.peak_decay = np.zeros(self.num_bars, dtype=np.float64)
        self.wave_buffer = np.zeros(0, dtype=np.float64)
        self.wave_max_samples = 4000
        self.is_active = False
        self.level = 0.0
        self.phase = 0.0
        # Oscilloscope persistence: last 3 waveform frames (newest first)
        self.osc_frames = []
        self.osc_max_frames = 3
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(30)

    def set_mode(self, mode):
        self.mode = mode
        self.update()

    def add_spectrum(self, spectrum):
        n = len(spectrum)
        if n < 2:
            return
        spectrum = np.nan_to_num(spectrum, nan=0.0, posinf=1.0, neginf=0.0)
        for i in range(self.num_bars):
            start = int((i / self.num_bars) ** 2.0 * n)
            end = int(((i + 1) / self.num_bars) ** 2.0 * n)
            if end <= start:
                end = start + 1
            end = min(end, n)
            val = float(np.max(spectrum[start:end])) if end > start else 0.0
            if val > self.bar_values[i]:
                self.bar_values[i] = val
            if val > self.peak_values[i]:
                self.peak_values[i] = val
                self.peak_decay[i] = 0.0
        self.level = float(np.max(self.bar_values))
        self.update()

    def add_waveform(self, chunk):
        self.wave_buffer = np.append(self.wave_buffer, chunk)
        if len(self.wave_buffer) > self.wave_max_samples:
            self.wave_buffer = self.wave_buffer[-self.wave_max_samples:]
        # Capture oscilloscope frame (copy of current buffer)
        if self.mode == self.MODE_OSC:
            self.osc_frames.insert(0, np.copy(self.wave_buffer))
            if len(self.osc_frames) > self.osc_max_frames:
                self.osc_frames = self.osc_frames[:self.osc_max_frames]
        if self.mode in (self.MODE_WAVE, self.MODE_COMBO, self.MODE_OSC):
            self.update()

    def _tick(self):
        self.phase += 0.05
        self.bar_values *= 0.85
        self.peak_decay += 0.016
        self.peak_values -= self.peak_decay * 0.02
        self.peak_values = np.maximum(self.peak_values, 0)
        if self.is_active or np.max(self.bar_values) > 0.01 or len(self.wave_buffer) > 0:
            self.update()

    def clear(self):
        self.bar_values[:] = 0
        self.peak_values[:] = 0
        self.peak_decay[:] = 0
        self.wave_buffer = np.zeros(0, dtype=np.float64)
        self.osc_frames = []
        self.level = 0
        self.update()

    def set_active(self, active):
        self.is_active = active
        if not active:
            self.clear()

    def _get_color(self, val):
        if val > 0.7:
            return QColor(255, 80, 100), QColor(200, 40, 80)
        elif val > 0.4:
            return QColor(255, 180, 60), QColor(200, 120, 40)
        else:
            return QColor(0, 220, 180), QColor(0, 140, 130)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        pad = 12

        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_grad.setColorAt(0, QColor(16, 16, 22))
        bg_grad.setColorAt(1, QColor(10, 10, 14))
        painter.fillRect(self.rect(), bg_grad)

        if not self.is_active and np.max(self.bar_values) < 0.01 and len(self.wave_buffer) < 2:
            painter.end()
            return

        if self.mode == self.MODE_BARS:
            self._draw_bars(painter, w, h, pad)
        elif self.mode == self.MODE_WAVE:
            self._draw_wave(painter, w, h, pad)
        elif self.mode == self.MODE_COMBO:
            self._draw_wave(painter, w, h, pad, alpha=80)
            self._draw_bars(painter, w, h, pad, alpha=120)
        elif self.mode == self.MODE_CIRCULAR:
            self._draw_circular(painter, w, h, pad)
        elif self.mode == self.MODE_OSC:
            self._draw_oscilloscope(painter, w, h, pad)

        painter.end()

    def _draw_bars(self, painter, w, h, pad, alpha=255):
        draw_w = w - pad * 2
        draw_h = h - pad * 2
        bar_w = draw_w / self.num_bars
        gap = max(1, bar_w * 0.15)
        actual_bar_w = bar_w - gap

        # Grid lines
        painter.setPen(QPen(QColor(30, 30, 40, alpha // 3), 1))
        for frac in [0.25, 0.5, 0.75]:
            y = pad + draw_h * frac
            painter.drawLine(pad, int(y), w - pad, int(y))

        for i in range(self.num_bars):
            val = float(self.bar_values[i])
            val = max(0, min(val, 1.0))
            bar_h = val * draw_h
            x = pad + i * bar_w + gap / 2
            y = pad + draw_h - bar_h
            top_c, bot_c = self._get_color(val)
            top_c.setAlpha(alpha)
            bot_c.setAlpha(alpha)

            if bar_h > 1:
                grad = QLinearGradient(0, y, 0, y + bar_h)
                grad.setColorAt(0, top_c)
                grad.setColorAt(1, bot_c)
                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(x, y, actual_bar_w, bar_h), 2, 2)

            peak = float(self.peak_values[i])
            peak = max(0, min(peak, 1.0))
            if peak > 0.05:
                peak_y = pad + draw_h - peak * draw_h
                painter.setPen(QPen(QColor(255, 255, 255, min(180, alpha)), 2))
                painter.drawLine(QPointF(x, peak_y), QPointF(x + actual_bar_w, peak_y))

        self._draw_level_bar(painter, w, h, pad, alpha)

    def _draw_wave(self, painter, w, h, pad, alpha=255):
        draw_w = w - pad * 2
        draw_h = h - pad * 2
        mid = pad + draw_h / 2.0

        # Grid
        painter.setPen(QPen(QColor(30, 30, 40, alpha // 3), 1))
        painter.drawLine(pad, int(mid), w - pad, int(mid))
        for frac in [0.25, 0.75]:
            y = pad + draw_h * frac
            painter.drawLine(pad, int(y), w - pad, int(y))

        if len(self.wave_buffer) < 2:
            return

        n = len(self.wave_buffer)
        if n > draw_w:
            step = n // int(draw_w)
            samples = self.wave_buffer[::step][:int(draw_w)]
        else:
            samples = self.wave_buffer
        n = len(samples)

        # Auto-scale to fill 90% of height
        max_val = float(np.max(np.abs(samples))) if n > 0 else 0.0
        max_val = max(max_val, 0.001)
        scale = 0.9 / max_val  # auto-scale to fill height

        top_c, bot_c = self._get_color(min(max_val, 1.0))
        top_c.setAlpha(alpha)
        bot_c.setAlpha(alpha)

        # Filled waveform — use full height
        points_top = []
        points_bot = []
        for i in range(n):
            x = pad + (i / max(n - 1, 1)) * draw_w
            val = float(samples[i]) * scale
            val = max(-1.0, min(val, 1.0))
            points_top.append(QPointF(x, mid - val * draw_h * 0.48))
            points_bot.append(QPointF(x, mid + val * draw_h * 0.48))

        # Gradient fill
        grad = QLinearGradient(0, pad, 0, pad + draw_h)
        c1 = QColor(top_c)
        c1.setAlpha(alpha // 5)
        c2 = QColor(top_c)
        c2.setAlpha(alpha)
        grad.setColorAt(0, c1)
        grad.setColorAt(0.5, c2)
        grad.setColorAt(1, c1)
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        poly = QPolygonF(points_top + list(reversed(points_bot)))
        painter.drawPolygon(poly)

        # Bright wave line on top
        pen = QPen(top_c)
        pen.setWidth(2)
        painter.setPen(pen)
        path = QPainterPath()
        for i in range(n):
            x = pad + (i / max(n - 1, 1)) * draw_w
            val = float(samples[i]) * scale
            val = max(-1.0, min(val, 1.0))
            y = mid - val * draw_h * 0.48
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.drawPath(path)

        # Mirror line (bottom half) for depth
        pen2 = QPen(QColor(top_c.red(), top_c.green(), top_c.blue(), alpha // 2))
        pen2.setWidth(1)
        painter.setPen(pen2)
        path2 = QPainterPath()
        for i in range(n):
            x = pad + (i / max(n - 1, 1)) * draw_w
            val = float(samples[i]) * scale
            val = max(-1.0, min(val, 1.0))
            y = mid + val * draw_h * 0.48
            if i == 0:
                path2.moveTo(x, y)
            else:
                path2.lineTo(x, y)
        painter.drawPath(path2)

        self._draw_level_bar(painter, w, h, pad, alpha)

    def _draw_circular(self, painter, w, h, pad):
        cx = w / 2.0
        cy = h / 2.0
        radius = min(w, h) / 2.0 - pad - 20
        mid_r = radius * 0.4

        # Background rings
        painter.setPen(QPen(QColor(30, 30, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for r_frac in [0.4, 0.7, 1.0]:
            painter.drawEllipse(QPointF(cx, cy), radius * r_frac, radius * r_frac)

        # Draw bars radially
        n = self.num_bars
        for i in range(n):
            val = float(self.bar_values[i])
            val = max(0, min(val, 1.0))
            if val < 0.02:
                continue
            angle = (i / n) * 2 * math.pi - math.pi / 2
            r1 = mid_r
            r2 = mid_r + val * (radius - mid_r)
            top_c, bot_c = self._get_color(val)

            x1 = cx + math.cos(angle) * r1
            y1 = cy + math.sin(angle) * r1
            x2 = cx + math.cos(angle) * r2
            y2 = cy + math.sin(angle) * r2

            pen = QPen(top_c, 3)
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Center circle with pulse
        pulse = (math.sin(self.phase) + 1) / 2
        center_r = mid_r * 0.5 + pulse * 4
        grad = QRadialGradient(cx, cy, center_r)
        lv = max(0, min(self.level, 1.0))
        top_c, _ = self._get_color(lv)
        grad.setColorAt(0, top_c)
        grad.setColorAt(1, QColor(20, 20, 30))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(top_c, 2))
        painter.drawEllipse(QPointF(cx, cy), center_r, center_r)

        # Waveform overlaid in center as oscilloscope
        if len(self.wave_buffer) > 2:
            n = min(len(self.wave_buffer), 200)
            step = len(self.wave_buffer) // n
            samples = self.wave_buffer[::step][:n]
            max_val = max(float(np.max(np.abs(samples))), 0.001)
            pen = QPen(QColor(255, 255, 255, 180), 1.5)
            painter.setPen(pen)
            path = QPainterPath()
            for i in range(n):
                x = cx - center_r * 0.8 + (i / max(n - 1, 1)) * center_r * 1.6
                val = float(samples[i]) / max_val
                y = cy + val * center_r * 0.4
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)

    def _draw_oscilloscope(self, painter, w, h, pad):
        """Classic green-phosphor oscilloscope: thin bright green trace with
        persistence/afterglow (last 3 frames at decreasing alpha)."""
        draw_w = w - pad * 2
        draw_h = h - pad * 2
        mid = pad + draw_h / 2.0

        # CRT-style dark green background tint
        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_grad.setColorAt(0, QColor(8, 18, 12))
        bg_grad.setColorAt(1, QColor(4, 10, 8))
        painter.fillRect(self.rect(), bg_grad)

        # Grid — faint green phosphor lines
        grid_pen = QPen(QColor(20, 80, 50, 120), 1)
        painter.setPen(grid_pen)
        painter.drawLine(pad, int(mid), w - pad, int(mid))
        for frac in [0.25, 0.5, 0.75]:
            y = pad + draw_h * frac
            painter.drawLine(pad, int(y), w - pad, int(y))
            x = pad + draw_w * frac
            painter.drawLine(int(x), pad, int(x), h - pad)

        # Persistence: draw older frames first at decreasing alpha
        # osc_frames is newest-first, so iterate reversed (oldest first)
        frames = list(reversed(self.osc_frames))
        for idx, frame in enumerate(frames):
            # oldest (idx 0) -> dimmest, newest (last) -> brightest
            age_from_newest = (len(frames) - 1 - idx)
            alpha = max(40, 220 - age_from_newest * 70)
            self._draw_osc_trace(painter, frame, w, h, pad, draw_w, draw_h, mid, alpha)

        # If no frames yet but wave_buffer has data, draw current buffer
        if not frames and len(self.wave_buffer) >= 2:
            self._draw_osc_trace(painter, self.wave_buffer, w, h, pad, draw_w, draw_h, mid, 220)

        self._draw_level_bar(painter, w, h, pad, alpha=200)

    def _draw_osc_trace(self, painter, samples, w, h, pad, draw_w, draw_h, mid, alpha):
        """Draw a single green-phosphor trace."""
        n = len(samples)
        if n < 2:
            return
        if n > draw_w:
            step = n // int(draw_w)
            samples = samples[::step][:int(draw_w)]
            n = len(samples)
        max_val = float(np.max(np.abs(samples))) if n > 0 else 0.0
        max_val = max(max_val, 0.001)
        scale = 0.9 / max_val

        # Glow underlay — thicker, dimmer
        glow_color = QColor(80, 255, 140, max(20, alpha // 3))
        glow_pen = QPen(glow_color, 5)
        glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(glow_pen)
        path_glow = QPainterPath()
        for i in range(n):
            x = pad + (i / max(n - 1, 1)) * draw_w
            val = float(samples[i]) * scale
            val = max(-1.0, min(val, 1.0))
            y = mid - val * draw_h * 0.45
            if i == 0:
                path_glow.moveTo(x, y)
            else:
                path_glow.lineTo(x, y)
        painter.drawPath(path_glow)

        # Bright thin trace on top
        bright = QColor(140, 255, 170, alpha)
        pen = QPen(bright, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        path = QPainterPath()
        for i in range(n):
            x = pad + (i / max(n - 1, 1)) * draw_w
            val = float(samples[i]) * scale
            val = max(-1.0, min(val, 1.0))
            y = mid - val * draw_h * 0.45
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.drawPath(path)

    def _draw_level_bar(self, painter, w, h, pad, alpha=255):
        draw_h = h - pad * 2
        level_x = w - pad - 8
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 20, 28))
        painter.drawRoundedRect(QRectF(level_x, pad, 4, draw_h), 2, 2)
        lv = max(0, min(self.level, 1.0))
        if lv > 0:
            lh = lv * draw_h
            if lv > 0.7:
                lc = QColor(255, 80, 100)
            elif lv > 0.4:
                lc = QColor(255, 180, 60)
            else:
                lc = QColor(0, 220, 180)
            lc.setAlpha(alpha)
            painter.setBrush(lc)
            painter.drawRoundedRect(QRectF(level_x, pad + draw_h - lh, 4, lh), 2, 2)


# =============================================================================
# Widgets — Record button
# =============================================================================

class RecordButton(QWidget):
    """Circular record button with pulsing glow when recording."""
    clicked_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 100)
        self.is_recording = False
        self.pulse_phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(30)
        self._hover = False

    def _tick(self):
        if self.is_recording:
            self.pulse_phase += 0.06
            self.update()

    def set_recording(self, recording):
        self.is_recording = recording
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_signal.emit()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        cx, cy = w / 2, h / 2
        radius = 38

        if self.is_recording:
            # Pulsing glow rings
            pulse = (math.sin(self.pulse_phase) + 1) / 2  # 0..1
            for ring in range(3):
                r = radius + 8 + ring * 8 + pulse * 6
                alpha = int(60 * (1 - ring * 0.3) * (1 - pulse * 0.5))
                painter.setPen(QPen(QColor(255, 60, 80, alpha), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), r, r)

            # Main circle — red
            grad = QRadialGradient(cx - 8, cy - 8, radius)
            grad.setColorAt(0, QColor(255, 120, 140))
            grad.setColorAt(1, QColor(200, 30, 50))
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor(255, 80, 100), 2))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

            # Stop square
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255))
            sq = 16
            painter.drawRoundedRect(QRectF(cx - sq/2, cy - sq/2, sq, sq), 3, 3)
        else:
            # Idle state — teal accent
            if self._hover:
                glow = QRadialGradient(cx, cy, radius + 20)
                glow.setColorAt(0, QColor(0, 200, 180, 40))
                glow.setColorAt(1, QColor(0, 200, 180, 0))
                painter.setBrush(QBrush(glow))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(cx, cy), radius + 18, radius + 18)

            grad = QRadialGradient(cx - 8, cy - 8, radius)
            grad.setColorAt(0, QColor(40, 50, 65))
            grad.setColorAt(1, QColor(20, 25, 35))
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(COL_ACCENT, 2))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

            # Record dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(COL_RECORD)
            painter.drawEllipse(QPointF(cx, cy), 14, 14)

        painter.end()


# =============================================================================
# Widgets — Status indicator dot
# =============================================================================

class StatusDot(QWidget):
    """Pulsing colored dot for header status indication.
       States: idle (gray), recording (red pulsing), analyzed (teal), matching (yellow)."""

    STATE_IDLE = "idle"
    STATE_RECORDING = "recording"
    STATE_ANALYZED = "analyzed"
    STATE_MATCHING = "matching"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.state = self.STATE_IDLE
        self.pulse_phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)

    def _tick(self):
        if self.state == self.STATE_RECORDING:
            self.pulse_phase += 0.12
            self.update()

    def set_state(self, state):
        self.state = state
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2.0, self.height() / 2.0

        if self.state == self.STATE_RECORDING:
            pulse = (math.sin(self.pulse_phase) + 1) / 2  # 0..1
            # Pulsing glow rings
            for ring in range(2):
                r = 5 + ring * 3 + pulse * 4
                alpha = int(90 * (1 - ring * 0.4) * (1 - pulse * 0.4))
                painter.setPen(QPen(QColor(255, 60, 80, alpha), 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), r, r)
            core = QColor(255, 70, 90)
        elif self.state == self.STATE_ANALYZED:
            core = COL_ACCENT
        elif self.state == self.STATE_MATCHING:
            core = COL_WARN
        else:  # idle
            core = QColor(110, 110, 120)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(core)
        painter.drawEllipse(QPointF(cx, cy), 5, 5)
        painter.end()


# =============================================================================
# Main GUI window
# =============================================================================

class VoiceMatcherGUI(QMainWindow):

    # ── Init + Setup ───────────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Matcher")
        self.setMinimumSize(960, 780)
        self.user_features = {}
        self.match_results = []
        self.recording_worker = None
        self.analysis_worker = None
        self.match_worker = None
        self.tts_worker = None
        self.calibration_worker = None

        # Recording countdown timer
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._tick_countdown)
        self.countdown_seconds = 0

        # Play-all-top-5 sequential playback state
        self.playall_queue = []
        self.playall_index = 0
        self.playall_timer = QTimer(self)
        self.playall_timer.setSingleShot(True)
        self.playall_timer.timeout.connect(self._playall_next)

        # Mic monitor worker (continuous level detection)
        self.mic_monitor = None

        self.ref_db = load_reference_db()
        if self.ref_db is None or len(self.ref_db.get("voices", {})) < 20:
            QMessageBox.warning(self, "Reference DB Missing",
                                "Kokoro reference database not built.\n"
                                "Run: python3 build_reference_db.py")

        self.setup_ui()

        # Start mic monitor after UI is built
        self._start_mic_monitor()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet(f"background-color: rgb(8, 8, 12); border-bottom: 1px solid rgb({COL_BORDER.red()}, {COL_BORDER.green()}, {COL_BORDER.blue()});")
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(24, 0, 24, 0)
        hlayout.setSpacing(10)

        title = QLabel("VOICE  MATCHER")
        title.setStyleSheet(f"color: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()}); font-size: 14px; font-weight: 800; letter-spacing: 3px; border: none; background: rgb(8,8,12);")
        hlayout.addWidget(title)
        self.status_dot = StatusDot()
        hlayout.addWidget(self.status_dot)
        hlayout.addStretch()
        self.header_status = QLabel("Ready")
        self.header_status.setStyleSheet(
            f"color: rgb({COL_TEXT_DIM.red()}, {COL_TEXT_DIM.green()}, {COL_TEXT_DIM.blue()}); "
            f"font-size: 11px; border: none; background: rgb(8,8,12);"
        )
        hlayout.addWidget(self.header_status)
        layout.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self.build_record_tab(), "RECORD")
        tabs.addTab(self.build_match_tab(), "MATCH")
        tabs.addTab(self.build_compare_tab(), "COMPARE")
        tabs.addTab(self.build_features_tab(), "FEATURES")
        layout.addWidget(tabs)

        self.status_label = QLabel("Ready — press record and speak naturally")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(30)
        self.status_label.setStyleSheet(
            f"color: rgb({COL_TEXT_DIM.red()}, {COL_TEXT_DIM.green()}, {COL_TEXT_DIM.blue()}); "
            f"font-size: 11px; padding: 6px; background: rgb(8,8,12); border: none;"
        )
        layout.addWidget(self.status_label)

    def keyPressEvent(self, event):
        """Spacebar toggles recording; all other keys pass through."""
        if event.key() == Qt.Key.Key_Space:
            focus = QApplication.focusWidget()
            if isinstance(focus, (QPushButton, QSlider)):
                super().keyPressEvent(event)
                return
            self.toggle_recording()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Clean up mic monitor on exit."""
        self._stop_mic_monitor()
        super().closeEvent(event)

    # ── Tab 1: Record ─────────────────────────────────────────────────────────

    def build_record_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Visualizer card
        spec_card, spec_layout = make_card()

        # Header row: mic selector on left, view mode buttons on right
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        # Mic selector — at top, where you'd expect input selection
        header_row.addWidget(styled_label("Mic", dim=True, size=11, bold=True))
        self.mic_combo = QComboBox()
        self.mic_combo.setFixedHeight(26)
        self.refresh_mic_devices()
        header_row.addWidget(self.mic_combo, 2)

        self.refresh_mic_btn = QPushButton("↻")
        self.refresh_mic_btn.setFixedWidth(28)
        self.refresh_mic_btn.setFixedHeight(26)
        self.refresh_mic_btn.clicked.connect(self.refresh_mic_devices)
        header_row.addWidget(self.refresh_mic_btn)

        # Separator between mic and view modes
        sep_mic = QLabel("│")
        sep_mic.setStyleSheet(f"color: rgb(50,50,60); background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()}); border: none;")
        header_row.addWidget(sep_mic)

        # View mode buttons
        self.view_mode_btns = []
        for mode_name, mode_val in [("Bars", 0), ("Wave", 1), ("Combo", 2), ("Circle", 3), ("Osc", 4)]:
            btn = QPushButton(mode_name)
            btn.setFixedHeight(24)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent; color: rgb(110,110,125);
                    border: none; border-radius: 4px;
                    padding: 2px 10px; font-size: 11px; font-weight: 600;
                }
                QPushButton:checked {
                    background: rgb(0,200,180); color: black;
                }
                QPushButton:hover:!checked {
                    color: rgb(200,200,210);
                }
            """)
            btn.clicked.connect(lambda checked, v=mode_val: self.set_view_mode(v))
            self.view_mode_btns.append(btn)
            header_row.addWidget(btn)
        self.view_mode_btns[0].setChecked(True)
        spec_layout.addLayout(header_row)

        self.spectrum_widget = VisualizerWidget()
        spec_layout.addWidget(self.spectrum_widget)

        # Level bar
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setFixedHeight(6)
        self.level_bar.setTextVisible(False)
        self.level_bar.setStyleSheet("""
            QProgressBar { background: rgb(25,25,32); border: none; border-radius: 3px; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 rgb(0,220,180), stop:0.6 rgb(255,200,60), stop:1 rgb(255,80,100));
                border-radius: 3px; }
        """)
        spec_layout.addWidget(self.level_bar)
        layout.addWidget(spec_card)

        # ── Mic input card: level bar + calibrate + auto ─────────────────────
        mic_card, mic_layout = make_card()
        mic_layout.setSpacing(8)

        # Mic level bar
        self.mic_level_bar = MicLevelBar()
        mic_layout.addWidget(self.mic_level_bar)

        # Calibrate + Auto row
        mic_btn_row = QHBoxLayout()
        mic_btn_row.setSpacing(8)

        self.calibrate_btn = QPushButton("⚙ Calibrate")
        self.calibrate_btn.setFixedHeight(28)
        self.calibrate_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgb({COL_ACCENT_2.red()}, {COL_ACCENT_2.green()}, {COL_ACCENT_2.blue()});
                color: white; font-weight: 600; font-size: 11px;
                border-radius: 5px; padding: 0 14px;
            }}
            QPushButton:hover {{ background: rgb(140, 100, 255); }}
            QPushButton:disabled {{ background: rgb(36,36,46); color: rgb(70,70,82); }}
        """)
        self.calibrate_btn.clicked.connect(self.start_calibration)
        mic_btn_row.addWidget(self.calibrate_btn)

        self.auto_level_cb = QCheckBox("Auto-Level")
        self.auto_level_cb.setFixedHeight(28)
        self.auto_level_cb.setStyleSheet("""
            QCheckBox {
                color: rgb(110,110,125); font-size: 11px; font-weight: 600;
                spacing: 6px; padding: 0 10px;
                background: transparent; border: none;
            }
            QCheckBox:checked { color: rgb(0,200,180); }
            QCheckBox::indicator {
                width: 14px; height: 14px;
                border: 1.5px solid rgb(50,50,62); border-radius: 3px;
                background: rgb(20,20,26);
            }
            QCheckBox::indicator:checked {
                background: rgb(0,200,180); border-color: rgb(0,200,180);
            }
        """)
        self.auto_level_cb.toggled.connect(self.toggle_auto_level)
        mic_btn_row.addWidget(self.auto_level_cb)
        mic_btn_row.addStretch()
        mic_layout.addLayout(mic_btn_row)

        # Calibration status (hidden, only shows during calibration)
        self.calibrate_status = QLabel("")
        self.calibrate_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.calibrate_status.setWordWrap(True)
        self.calibrate_status.setFixedHeight(28)
        self.calibrate_status.setStyleSheet(
            f"color: rgb({COL_TEXT_DIM.red()}, {COL_TEXT_DIM.green()}, {COL_TEXT_DIM.blue()}); "
            f"font-size: 11px; padding: 2px 6px; border: none; "
            f"background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()});"
        )
        self.calibrate_status.setVisible(False)
        mic_layout.addWidget(self.calibrate_status)
        layout.addWidget(mic_card)

        # ── Record controls card: settings + record button ───────────────────
        ctrl_card, ctrl_layout = make_card()

        # ── Recording settings ──
        dur_row = QHBoxLayout()
        dur_row.setSpacing(8)
        dur_row.addWidget(styled_label("Duration", dim=True, size=12))
        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(3, 30)
        self.duration_slider.setValue(8)
        self.duration_slider.valueChanged.connect(
            lambda v: self.duration_label.setText(f"{v}s")
        )
        dur_row.addWidget(self.duration_slider, 1)
        self.duration_label = styled_label("8s", bold=True, size=14)
        self.duration_label.setFixedWidth(40)
        dur_row.addWidget(self.duration_label)

        sep = QLabel("│")
        sep.setStyleSheet(f"color: rgb(50,50,60); background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()}); border: none;")
        dur_row.addWidget(sep)

        dur_row.addWidget(styled_label("Sens", dim=True, size=12))
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(1, 500)
        self.gain_slider.setValue(50)
        self.gain_slider.valueChanged.connect(
            lambda v: self.gain_label.setText(f"{v/10:.1f}x")
        )
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        dur_row.addWidget(self.gain_slider, 1)
        self.gain_label = styled_label("5.0x", bold=True, size=14)
        self.gain_label.setFixedWidth(44)
        dur_row.addWidget(self.gain_label)

        sep2 = QLabel("│")
        sep2.setStyleSheet(f"color: rgb(50,50,60); background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()}); border: none;")
        dur_row.addWidget(sep2)

        dur_row.addWidget(styled_label("Gate", dim=True, size=12))
        self.gate_slider = QSlider(Qt.Orientation.Horizontal)
        self.gate_slider.setRange(0, 50)
        self.gate_slider.setValue(0)
        self.gate_slider.valueChanged.connect(
            lambda v: self.gate_label.setText(f"{v}%")
        )
        dur_row.addWidget(self.gate_slider, 1)
        self.gate_label = styled_label("0%", bold=True, size=14)
        self.gate_label.setFixedWidth(40)
        dur_row.addWidget(self.gate_label)
        ctrl_layout.addLayout(dur_row)

        # ── Record button ──
        rec_row = QHBoxLayout()
        rec_row.addStretch()
        self.record_btn = RecordButton()
        self.record_btn.clicked_signal.connect(self.toggle_recording)
        rec_row.addWidget(self.record_btn)
        rec_row.addStretch()
        ctrl_layout.addLayout(rec_row)

        self.rec_label = QLabel("Press to record")
        self.rec_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rec_label.setFixedHeight(20)
        self.rec_label.setStyleSheet(
            f"color: rgb({COL_TEXT_DIM.red()}, {COL_TEXT_DIM.green()}, {COL_TEXT_DIM.blue()}); "
            f"font-size: 11px; font-weight: 500; border: none; "
            f"background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()}); "
            f"padding: 1px 6px;"
        )
        ctrl_layout.addWidget(self.rec_label)

        self.countdown_label = QLabel("")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setFixedHeight(20)
        self.countdown_label.setStyleSheet(
            f"color: rgb({COL_RECORD.red()}, {COL_RECORD.green()}, {COL_RECORD.blue()}); "
            f"font-weight: 700; font-size: 13px; border: none; "
            f"background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()}); "
            f"padding: 1px 6px;"
        )
        self.countdown_label.setVisible(False)
        ctrl_layout.addWidget(self.countdown_label)

        # ── Section 4: Analysis status ──
        self.analysis_progress = QLabel("")
        self.analysis_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.analysis_progress.setFixedHeight(20)
        self.analysis_progress.setStyleSheet(
            f"color: rgb({COL_TEXT_DIM.red()}, {COL_TEXT_DIM.green()}, {COL_TEXT_DIM.blue()}); "
            f"font-size: 11px; border: none; "
            f"background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()}); "
            f"padding: 1px 6px;"
        )
        ctrl_layout.addWidget(self.analysis_progress)

        layout.addWidget(ctrl_card)

        # Result card
        result_card, result_layout = make_card("ANALYSIS RESULT")
        self.record_result = QTextEdit()
        self.record_result.setReadOnly(True)
        self.record_result.setFixedHeight(100)
        self.record_result.setStyleSheet("font-size: 13px; border: none; background: rgb(18,18,24); border-radius: 6px;")
        result_layout.addWidget(self.record_result)

        self.auto_match_btn = QPushButton("→  Find My Voice Match")
        self.auto_match_btn.setFixedHeight(44)
        self.auto_match_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()});
                color: black; font-weight: 700; font-size: 15px; border-radius: 8px;
            }}
            QPushButton:hover {{ background: rgb(0, 230, 210); }}
            QPushButton:disabled {{ background: rgb(30,30,38); color: rgb(70,70,80); }}
        """)
        self.auto_match_btn.clicked.connect(self.run_match)
        self.auto_match_btn.setEnabled(False)
        result_layout.addWidget(self.auto_match_btn)
        layout.addWidget(result_card)

        layout.addStretch()
        return widget

    def set_view_mode(self, mode):
        """Switch the visualizer display mode."""
        self.spectrum_widget.set_mode(mode)
        for i, btn in enumerate(self.view_mode_btns):
            btn.setChecked(i == mode)

    # ── Mic Monitor + Auto-Level ──────────────────────────────────────────────

    def refresh_mic_devices(self):
        """Populate the mic device dropdown with available input devices."""
        self.mic_combo.clear()
        try:
            for idx, name, is_default in list_input_devices():
                label = f"[{idx}] {name}"
                if is_default:
                    label += "  (default)"
                self.mic_combo.addItem(label, idx)
        except Exception:
            self.mic_combo.addItem("Default", None)
        # Restart monitor with new device if running
        if self.mic_monitor and self.mic_monitor.isRunning():
            self._stop_mic_monitor()
            self._start_mic_monitor()

    def _start_mic_monitor(self):
        """Start continuous mic level monitoring."""
        if self.recording_worker and self.recording_worker.isRunning():
            return  # don't run monitor while recording
        device = self.mic_combo.currentData() if self.mic_combo.count() > 0 else None
        gain = self.gain_slider.value() / 10.0 if hasattr(self, "gain_slider") else 1.0
        self.mic_monitor = MicMonitorWorker(device=device)
        self.mic_monitor.set_gain(gain)
        if hasattr(self, "auto_level_cb") and self.auto_level_cb.isChecked():
            self.mic_monitor.set_auto_level(True)
        self.mic_monitor.level_update.connect(self.mic_level_bar.set_level)
        self.mic_monitor.peak_update.connect(self.mic_level_bar.set_peak)
        self.mic_monitor.level_update.connect(self._on_mic_monitor_error_check)
        self.mic_monitor.auto_gain_update.connect(self._on_auto_gain_update)
        self.mic_monitor.start()

    def toggle_auto_level(self, enabled):
        """Toggle automatic gain adjustment."""
        if self.mic_monitor and self.mic_monitor.isRunning():
            self.mic_monitor.set_auto_level(enabled)
        if enabled:
            self.gain_slider.setEnabled(False)
            self.gain_label.setStyleSheet(
                f"color: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()}); "
                f"font-size: 12px; font-weight: 700; border: none; "
                f"background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()});"
            )
            self.status_label.setText("Auto-level ON — gain adjusts automatically")
        else:
            self.gain_slider.setEnabled(True)
            self.gain_label.setStyleSheet(
                f"color: rgb({COL_TEXT.red()}, {COL_TEXT.green()}, {COL_TEXT.blue()}); "
                f"font-size: 12px; font-weight: 700; border: none; "
                f"background: rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()});"
            )
            self.status_label.setText("Auto-level OFF — manual gain control")

    def _on_auto_gain_update(self, gain):
        """Update the gain slider/label when auto-level adjusts gain."""
        slider_val = int(max(1, min(gain * 10, 500)))
        # Block signals to avoid feedback loop
        self.gain_slider.blockSignals(True)
        self.gain_slider.setValue(slider_val)
        self.gain_slider.blockSignals(False)
        self.gain_label.setText(f"{gain:.1f}x")

    def _stop_mic_monitor(self):
        """Stop mic level monitoring."""
        if self.mic_monitor:
            self.mic_monitor.stop()
            self.mic_monitor.wait(500)
            self.mic_monitor = None

    def _on_mic_monitor_error_check(self, level):
        """If monitor reports -1, mic error."""
        if level < 0:
            self.mic_level_bar.set_level(0)

    def _restart_mic_monitor(self):
        """Restart monitor with current settings (called when gain/device changes)."""
        if self.mic_monitor and self.mic_monitor.isRunning():
            self._stop_mic_monitor()
        self._start_mic_monitor()

    def _on_gain_changed(self, value):
        """Update mic monitor gain in real-time when sensitivity slider moves."""
        gain = value / 10.0
        if self.mic_monitor and self.mic_monitor.isRunning():
            self.mic_monitor.set_gain(gain)

    # ── Mic Calibration ───────────────────────────────────────────────────────

    def start_calibration(self):
        """Run two-phase mic calibration: noise floor then voice level."""
        if self.recording_worker and self.recording_worker.isRunning():
            QMessageBox.warning(self, "Recording", "Stop recording first!")
            return
        if self.calibration_worker and self.calibration_worker.isRunning():
            self.calibration_worker.cancel()
            self.calibrate_btn.setEnabled(True)
            self.calibrate_status.setVisible(False)
            self._start_mic_monitor()
            return

        device = self.mic_combo.currentData()
        # Stop monitor during calibration
        self._stop_mic_monitor()

        self.calibrate_btn.setText("✕ Cancel")
        self.calibrate_btn.setEnabled(True)
        self.calibrate_status.setVisible(True)
        self.calibrate_status.setText("Starting calibration...")
        self.status_dot.set_state(StatusDot.STATE_MATCHING)

        self.calibration_worker = CalibrationWorker(device=device)
        self.calibration_worker.progress.connect(self.calibrate_status.setText)
        self.calibration_worker.progress.connect(self.status_label.setText)
        self.calibration_worker.level_update.connect(self.mic_level_bar.set_level)
        self.calibration_worker.phase_update.connect(self._on_calibrate_phase)
        self.calibration_worker.finished_calibration.connect(self._on_calibrate_done)
        self.calibration_worker.error.connect(self._on_calibrate_error)
        self.calibration_worker.start()

    def _on_calibrate_phase(self, phase):
        """Update UI based on calibration phase."""
        bg = f"rgb({COL_BG_CARD.red()}, {COL_BG_CARD.green()}, {COL_BG_CARD.blue()})"
        if phase == 1:
            self.calibrate_status.setStyleSheet(
                f"color: rgb({COL_WARN.red()}, {COL_WARN.green()}, {COL_WARN.blue()}); "
                f"font-size: 12px; font-weight: 700; padding: 2px 6px; border: none; "
                f"background: {bg};")
        elif phase == 2:
            self.calibrate_status.setStyleSheet(
                f"color: rgb({COL_GOOD.red()}, {COL_GOOD.green()}, {COL_GOOD.blue()}); "
                f"font-size: 12px; font-weight: 700; padding: 2px 6px; border: none; "
                f"background: {bg};")
        elif phase == 3:
            self.calibrate_status.setStyleSheet(
                f"color: rgb({COL_ACCENT.red()}, {COL_ACCENT.green()}, {COL_ACCENT.blue()}); "
                f"font-size: 12px; font-weight: 700; padding: 2px 6px; border: none; "
                f"background: {bg};")

    def _on_calibrate_done(self, result):
        """Apply calibration results to the sliders."""
        noise_floor = result["noise_floor"]
        voice_level = result["voice_level"]
        gain = result["gain"]
        gate = result["gate"]

        # Apply gain to slider (slider value = gain * 10)
        gain_slider_val = int(max(1, min(gain * 10, 500)))
        self.gain_slider.setValue(gain_slider_val)

        # Apply gate to slider
        self.gate_slider.setValue(gate)

        # Show results
        self.calibrate_status.setText(
            f"✓ Calibrated!  Noise: {noise_floor:.4f}  |  Voice: {voice_level:.4f}  |  "
            f"Gain: {gain:.1f}x  |  Gate: {gate}%"
        )
        self.status_label.setText(
            f"Calibration done — gain set to {gain:.1f}x, gate to {gate}%"
        )
        self.status_dot.set_state(StatusDot.STATE_ANALYZED)

        # Reset button
        self.calibrate_btn.setText("⚙ Calibrate")

        # Restart mic monitor with new settings
        QTimer.singleShot(500, self._start_mic_monitor)

        # Auto-hide status after 5 seconds
        QTimer.singleShot(5000, lambda: self.calibrate_status.setVisible(False))

    def _on_calibrate_error(self, err):
        """Handle calibration error."""
        self.calibrate_status.setText(f"Calibration error: {err}")
        self.status_label.setText(f"Calibration failed: {err}")
        self.status_dot.set_state(StatusDot.STATE_IDLE)
        self.calibrate_btn.setText("⚙ Calibrate")
        self._start_mic_monitor()

    # ── Recording + Analysis ──────────────────────────────────────────────────

    def toggle_recording(self):
        if self.recording_worker and self.recording_worker.isRunning():
            self.recording_worker.cancel()
            self.record_btn.set_recording(False)
            self.rec_label.setText("Press to record")
            self.spectrum_widget.set_active(False)
            self.level_bar.setValue(0)
            self.header_status.setText("Stopped")
            self.status_label.setText("Recording stopped")
            self._stop_countdown()
            self.status_dot.set_state(StatusDot.STATE_IDLE)
            # Restart mic monitor after recording stops
            QTimer.singleShot(300, self._start_mic_monitor)
        else:
            # Stop monitor while recording (recording worker handles its own input)
            self._stop_mic_monitor()
            duration = self.duration_slider.value()
            gain = self.gain_slider.value() / 10.0
            noise_gate = self.gate_slider.value() / 1000.0
            device = self.mic_combo.currentData()
            self.recording_worker = LiveRecordWorker(duration, gain=gain, noise_gate=noise_gate, device=device)
            self.recording_worker.level_update.connect(self.update_level)
            self.recording_worker.waveform_update.connect(self.spectrum_widget.add_waveform)
            self.recording_worker.spectrum_update.connect(self.spectrum_widget.add_spectrum)
            self.recording_worker.finished_recording.connect(self.on_recording_done)
            self.record_btn.set_recording(True)
            self.rec_label.setText(f"Recording for {duration}s — speak now!")
            self.spectrum_widget.clear()
            self.spectrum_widget.set_active(True)
            self.level_bar.setValue(0)
            self.analysis_progress.setText("")
            self.record_result.setPlainText("")
            self.auto_match_btn.setEnabled(False)
            self.header_status.setText("● REC")
            self.status_label.setText(f"Recording {duration}s... speak now!")
            self.status_dot.set_state(StatusDot.STATE_RECORDING)
            self._start_countdown(duration)
            self.recording_worker.start()

    def _start_countdown(self, duration):
        self.countdown_seconds = duration
        self.countdown_label.setText(f"Recording... {duration}s left")
        self.countdown_label.setVisible(True)
        self.countdown_timer.start()

    def _tick_countdown(self):
        self.countdown_seconds -= 1
        if self.countdown_seconds <= 0:
            self._stop_countdown()
        else:
            self.countdown_label.setText(f"Recording... {self.countdown_seconds}s left")

    def _stop_countdown(self):
        self.countdown_timer.stop()
        self.countdown_seconds = 0
        self.countdown_label.setVisible(False)
        self.countdown_label.setText("")

    def update_level(self, level):
        if level < 0 or math.isnan(level) or math.isinf(level):
            self.status_label.setText("Recording error")
            return
        self.level_bar.setValue(int(max(0, min(level, 1.0)) * 100))

    def on_recording_done(self, path):
        self.record_btn.set_recording(False)
        self.rec_label.setText("Press to record")
        self.spectrum_widget.set_active(False)
        self.level_bar.setValue(0)
        self._stop_countdown()
        self.header_status.setText("Analyzing...")
        self.status_label.setText(f"Recorded — analyzing...")
        self.status_dot.set_state(StatusDot.STATE_MATCHING)

        self.analysis_progress.setText("Analyzing your voice...")
        self.analysis_worker = AnalysisWorker(path)
        self.analysis_worker.progress.connect(self.analysis_progress.setText)
        self.analysis_worker.finished_analysis.connect(self.on_analysis_done)
        self.analysis_worker.error.connect(self.on_analysis_error)
        self.analysis_worker.start()

    def on_analysis_done(self, features):
        self.user_features = features
        pitch = features.get("pitchMean", 0)
        centroid = features.get("spectralCentroidMean", features.get("spectralCentroid", 0))
        breath = features.get("breathiness", 0)

        if pitch < 130:
            gender = "male (low)"
        elif pitch < 165:
            gender = "male (mid) / neutral"
        elif pitch < 200:
            gender = "female (low) / male (high)"
        else:
            gender = "female (high)"

        self.record_result.setHtml(
            f"<table cellpadding='4' style='color: rgb(230,230,235);'>"
            f"<tr><td style='color: rgb(130,130,145);'>Features</td><td>{len(features)} extracted</td></tr>"
            f"<tr><td style='color: rgb(130,130,145);'>Pitch</td><td><b>{pitch:.1f} Hz</b> — {gender}</td></tr>"
            f"<tr><td style='color: rgb(130,130,145);'>Brightness</td><td>{centroid:.0f} Hz</td></tr>"
            f"<tr><td style='color: rgb(130,130,145);'>Breathiness</td><td>{breath:.3f}</td></tr>"
            f"</table>"
        )
        self.analysis_progress.setText("✓ Ready to match")
        self.auto_match_btn.setEnabled(True)
        self.header_status.setText("Analyzed")
        self.status_label.setText("Analysis complete — press 'Find My Voice Match'")
        self.status_dot.set_state(StatusDot.STATE_ANALYZED)
        # Populate the Features tab with the extracted features
        self.update_features_display(features)

    def on_analysis_error(self, err):
        self.analysis_progress.setText(f"Error: {err}")
        self.header_status.setText("Error")
        self.status_label.setText(f"Analysis error: {err}")
        self.status_dot.set_state(StatusDot.STATE_IDLE)

    # ── Tab 2: Match ──────────────────────────────────────────────────────────

    def build_match_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        card, card_layout = make_card("VOICE MATCH RESULTS")
        info = styled_label("Ranked by similarity to your voice. Click a row to hear it.", dim=True, size=12)
        card_layout.addWidget(info)

        self.match_table = QTableWidget(0, 4)
        self.match_table.setHorizontalHeaderLabels(["#", "Voice", "Match", "Pitch"])
        self.match_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.match_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.match_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.match_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.match_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.match_table.setAlternatingRowColors(True)
        self.match_table.cellDoubleClicked.connect(self.play_selected_match)
        self.match_table.setStyleSheet("""
            QTableWidget { alternate-background-color: rgb(22,22,28); }
        """)
        card_layout.addWidget(self.match_table)

        # Test text + play
        self.match_test_text = QTextEdit()
        self.match_test_text.setPlainText("Hello, this is how your matched voice sounds.")
        self.match_test_text.setFixedHeight(44)
        card_layout.addWidget(self.match_test_text)

        btn_row = QHBoxLayout()
        self.play_match_btn = QPushButton("▶  Play Selected")
        self.play_match_btn.setFixedHeight(40)
        self.play_match_btn.clicked.connect(self.play_selected_match)
        btn_row.addWidget(self.play_match_btn)
        self.play_all_btn = QPushButton("▶▶  Play All Top 5")
        self.play_all_btn.setFixedHeight(40)
        self.play_all_btn.clicked.connect(self.play_all_top5)
        btn_row.addWidget(self.play_all_btn)
        self.rematch_btn = QPushButton("↻  Re-match")
        self.rematch_btn.setFixedHeight(40)
        self.rematch_btn.clicked.connect(self.run_match)
        btn_row.addWidget(self.rematch_btn)
        card_layout.addLayout(btn_row)
        layout.addWidget(card)

        # Detail card
        detail_card, detail_layout = make_card("FEATURE COMPARISON")
        self.detail_table = QTableWidget(0, 4)
        self.detail_table.setHorizontalHeaderLabels(["Feature", "You", "Matched", "Similarity"])
        self.detail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.detail_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.detail_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.detail_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.detail_table.setAlternatingRowColors(True)
        detail_layout.addWidget(self.detail_table)
        layout.addWidget(detail_card)

        return widget

    def run_match(self):
        if not self.user_features:
            QMessageBox.warning(self, "No analysis", "Record and analyze your voice first!")
            return
        if not self.ref_db or "voices" not in self.ref_db:
            QMessageBox.critical(self, "No reference DB", "Run: python3 build_reference_db.py")
            return

        self.status_label.setText("Matching to 28 Kokoro voices...")
        self.status_dot.set_state(StatusDot.STATE_MATCHING)
        self.match_worker = MatchWorker(self.user_features, self.ref_db, top_n=10)
        self.match_worker.progress.connect(self.status_label.setText)
        self.match_worker.finished_match.connect(self.on_match_done)
        self.match_worker.error.connect(self.on_match_error)
        self.match_worker.start()

    def on_match_done(self, results):
        self.match_results = results
        self.match_table.setRowCount(len(results))
        for i, r in enumerate(results):
            voice = r["voice"]
            score = r["score"]
            ref_pitch = self.ref_db["voices"][voice]["features"].get("pitchMean", 0)
            self.match_table.setItem(i, 0, QTableWidgetItem(f"#{i+1}"))
            self.match_table.setItem(i, 1, QTableWidgetItem(voice))
            score_item = QTableWidgetItem(f"{score*100:.1f}%")
            if score > 0.8:
                score_item.setBackground(COL_GOOD)
                score_item.setForeground(QColor(0, 0, 0))
            elif score > 0.6:
                score_item.setBackground(COL_WARN)
                score_item.setForeground(QColor(0, 0, 0))
            elif score > 0.4:
                score_item.setBackground(QColor(255, 140, 50))
            else:
                score_item.setBackground(COL_BAD)
            self.match_table.setItem(i, 2, score_item)
            self.match_table.setItem(i, 3, QTableWidgetItem(f"{ref_pitch:.0f} Hz"))
        if results:
            best = results[0]
            self.status_label.setText(f"Best match: {best['voice']} ({best['score']*100:.1f}%)")
            self.populate_detail_table(best)
        self.status_dot.set_state(StatusDot.STATE_ANALYZED)

    def on_match_error(self, err):
        self.status_label.setText(f"Match error: {err}")
        self.status_dot.set_state(StatusDot.STATE_IDLE)

    def populate_detail_table(self, match):
        diffs = match.get("diffs", {})
        self.detail_table.setRowCount(len(diffs))
        for i, (feat, data) in enumerate(sorted(diffs.items(), key=lambda x: x[1]["similarity"], reverse=True)):
            sim = data["similarity"]
            self.detail_table.setItem(i, 0, QTableWidgetItem(feat))
            self.detail_table.setItem(i, 1, QTableWidgetItem(f"{data['user']:.4f}"))
            self.detail_table.setItem(i, 2, QTableWidgetItem(f"{data['ref']:.4f}"))
            sim_item = QTableWidgetItem(f"{sim*100:.1f}%")
            if sim > 0.8:
                sim_item.setBackground(COL_GOOD)
            elif sim > 0.5:
                sim_item.setBackground(COL_WARN)
            else:
                sim_item.setBackground(COL_BAD)
            self.detail_table.setItem(i, 3, sim_item)

    # ── Playback ──────────────────────────────────────────────────────────────

    def play_selected_match(self):
        row = self.match_table.currentRow()
        if row < 0 and self.match_results:
            row = 0
        if row < 0 or row >= len(self.match_results):
            return
        voice = self.match_results[row]["voice"]
        text = self.match_test_text.toPlainText().strip() or "Hello."
        output = f"/tmp/voice_match_{voice}_{int(time.time())}.wav"
        self.status_label.setText(f"Playing {voice}...")
        self.tts_worker = TTSWorker(text, voice, output)
        self.tts_worker.progress.connect(self.status_label.setText)
        self.tts_worker.finished_tts.connect(lambda: self.status_label.setText(f"Played {voice}"))
        self.tts_worker.error.connect(lambda e: self.status_label.setText(f"Error: {e}"))
        self.tts_worker.start()

    def play_all_top5(self):
        """Play each of the top 5 matched voices sequentially with the test
        text, with a 1-second pause between each."""
        if not self.match_results:
            QMessageBox.warning(self, "No matches", "Run a match first!")
            return
        self.playall_queue = self.match_results[:5]
        self.playall_index = 0
        self.play_all_btn.setEnabled(False)
        self.play_match_btn.setEnabled(False)
        self.status_dot.set_state(StatusDot.STATE_MATCHING)
        self._playall_next()

    def _playall_next(self):
        if self.playall_index >= len(self.playall_queue):
            # Finished all
            self.play_all_btn.setEnabled(True)
            self.play_match_btn.setEnabled(True)
            self.status_label.setText("Finished playing top 5")
            self.status_dot.set_state(StatusDot.STATE_ANALYZED)
            return
        r = self.playall_queue[self.playall_index]
        voice = r["voice"]
        text = self.match_test_text.toPlainText().strip() or "Hello."
        output = f"/tmp/voice_match_all_{self.playall_index}_{voice}_{int(time.time())}.wav"
        self.status_label.setText(f"Playing {self.playall_index + 1}/{len(self.playall_queue)}: {voice}...")
        self.tts_worker = TTSWorker(text, voice, output)
        self.tts_worker.progress.connect(self.status_label.setText)

        def _on_done():
            self.playall_index += 1
            if self.playall_index < len(self.playall_queue):
                # 1-second pause before next voice
                self.status_label.setText("Pausing...")
                self.playall_timer.start(1000)
            else:
                self._playall_next()

        self.tts_worker.finished_tts.connect(_on_done)
        self.tts_worker.error.connect(lambda e: self.status_label.setText(f"Error: {e}"))
        self.tts_worker.start()

    # ── Tab 3: Compare ────────────────────────────────────────────────────────

    def build_compare_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        card, card_layout = make_card("A / B COMPARISON")

        # Your recording
        rec_row = QHBoxLayout()
        rec_row.addWidget(styled_label("Your recording", dim=True, size=12))
        self.recording_combo = QComboBox()
        self.refresh_recordings()
        rec_row.addWidget(self.recording_combo, 1)
        self.refresh_rec_btn = QPushButton("↻")
        self.refresh_rec_btn.setFixedWidth(36)
        self.refresh_rec_btn.clicked.connect(self.refresh_recordings)
        rec_row.addWidget(self.refresh_rec_btn)
        self.play_rec_btn = QPushButton("▶  Play")
        self.play_rec_btn.setFixedHeight(36)
        self.play_rec_btn.clicked.connect(self.play_my_recording)
        rec_row.addWidget(self.play_rec_btn)
        card_layout.addLayout(rec_row)

        # Kokoro voice
        match_row = QHBoxLayout()
        match_row.addWidget(styled_label("Kokoro voice", dim=True, size=12))
        self.compare_voice_combo = QComboBox()
        for v in KOKORO_VOICES:
            self.compare_voice_combo.addItem(v)
        match_row.addWidget(self.compare_voice_combo, 1)
        self.play_compare_btn = QPushButton("▶  Play")
        self.play_compare_btn.setFixedHeight(36)
        self.play_compare_btn.clicked.connect(self.play_compare_voice)
        match_row.addWidget(self.play_compare_btn)
        card_layout.addLayout(match_row)

        self.compare_text = QTextEdit()
        self.compare_text.setPlainText("The quick brown fox jumps over the lazy dog.")
        self.compare_text.setFixedHeight(44)
        card_layout.addWidget(self.compare_text)
        layout.addWidget(card)

        # Reference table
        ref_card, ref_layout = make_card("ALL 28 KOKORO VOICES")
        self.ref_table = QTableWidget(0, 4)
        self.ref_table.setHorizontalHeaderLabels(["Voice", "Pitch", "Brightness", "Breathiness"])
        self.ref_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.ref_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.ref_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.ref_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.ref_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ref_table.setAlternatingRowColors(True)
        self.ref_table.cellDoubleClicked.connect(self.play_ref_voice)
        ref_layout.addWidget(self.ref_table)
        self.populate_ref_table()
        layout.addWidget(ref_card)

        return widget

    def refresh_recordings(self):
        self.recording_combo.clear()
        for name, path in list_recordings():
            self.recording_combo.addItem(name, path)

    def play_my_recording(self):
        path = self.recording_combo.currentData()
        if play_audio_file(path):
            self.status_label.setText("Playing your recording...")

    def play_compare_voice(self):
        voice = self.compare_voice_combo.currentText()
        text = self.compare_text.toPlainText().strip()
        if not text:
            return
        output = f"/tmp/voice_compare_{voice}_{int(time.time())}.wav"
        self.tts_worker = TTSWorker(text, voice, output)
        self.tts_worker.progress.connect(self.status_label.setText)
        self.tts_worker.finished_tts.connect(lambda: self.status_label.setText(f"Played {voice}"))
        self.tts_worker.error.connect(lambda e: self.status_label.setText(f"Error: {e}"))
        self.tts_worker.start()

    def play_ref_voice(self, row, col):
        if not self.ref_db:
            return
        voices = sorted(self.ref_db["voices"].keys())
        if row >= len(voices):
            return
        voice = voices[row]
        audio_path = self.ref_db["voices"][voice].get("audio_path")
        if play_audio_file(audio_path):
            self.status_label.setText(f"Playing {voice}...")

    def populate_ref_table(self):
        if not self.ref_db:
            return
        voices = sorted(self.ref_db["voices"].keys())
        self.ref_table.setRowCount(len(voices))
        for i, v in enumerate(voices):
            feats = self.ref_db["voices"][v]["features"]
            pitch = feats.get("pitchMean", 0)
            centroid = feats.get("spectralCentroidMean", feats.get("spectralCentroid", 0))
            breath = feats.get("breathiness", 0)
            self.ref_table.setItem(i, 0, QTableWidgetItem(v))
            self.ref_table.setItem(i, 1, QTableWidgetItem(f"{pitch:.1f}"))
            self.ref_table.setItem(i, 2, QTableWidgetItem(f"{centroid:.0f}"))
            self.ref_table.setItem(i, 3, QTableWidgetItem(f"{breath:.3f}"))

    # ── Tab 4: Features ───────────────────────────────────────────────────────

    def build_features_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        card, card_layout = make_card("YOUR VOICE FEATURES")
        self.features_table = QTableWidget(0, 2)
        self.features_table.setHorizontalHeaderLabels(["Feature", "Value"])
        self.features_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.features_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.features_table.setAlternatingRowColors(True)
        card_layout.addWidget(self.features_table)
        layout.addWidget(card)

        emo_card, emo_layout = make_card("EMOTION ESTIMATES")
        self.emotion_bars = {}
        for emo in ["excitement", "calmness", "stress", "confidence"]:
            row = QHBoxLayout()
            row.addWidget(styled_label(f"{emo.capitalize()}", size=13))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(8)
            bar.setTextVisible(False)
            bar.setStyleSheet("""
                QProgressBar { background: rgb(25,25,32); border: none; border-radius: 4px; }
                QProgressBar::chunk { border-radius: 4px;
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgb(120,80,255), stop:1 rgb(0,200,180)); }
            """)
            row.addWidget(bar, 1)
            val = styled_label("—", bold=True, size=13)
            val.setFixedWidth(50)
            row.addWidget(val)
            emo_layout.addLayout(row)
            self.emotion_bars[emo] = (bar, val)
        layout.addWidget(emo_card)

        layout.addStretch()
        return widget

    def update_features_display(self, features):
        important = ["pitchMean", "pitchStd", "pitchRange", "pitchMedian",
                     "spectralCentroidMean", "spectralCentroid",
                     "rmsMean", "breathiness", "roughness", "harmonicityMean",
                     "jitterLocal", "shimmerLocal", "speechRate", "tempo",
                     "zeroCrossingRate", "silenceRatio"]
        sorted_keys = [k for k in important if k in features]
        other = sorted([k for k in features if k not in important and k != "timestamp"])
        all_keys = sorted_keys + other
        self.features_table.setRowCount(len(all_keys))
        for i, key in enumerate(all_keys):
            val = features[key]
            val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
            self.features_table.setItem(i, 0, QTableWidgetItem(key))
            self.features_table.setItem(i, 1, QTableWidgetItem(val_str))
        for emo, (bar, label) in self.emotion_bars.items():
            val = features.get(emo, 0)
            bar.setValue(int(val * 100))
            label.setText(f"{val:.2f}")


# =============================================================================
# Entry point
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, COL_BG)
    palette.setColor(QPalette.ColorRole.WindowText, COL_TEXT)
    palette.setColor(QPalette.ColorRole.Base, QColor(18, 18, 24))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(22, 22, 28))
    palette.setColor(QPalette.ColorRole.Text, COL_TEXT)
    palette.setColor(QPalette.ColorRole.Button, QColor(30, 30, 38))
    palette.setColor(QPalette.ColorRole.ButtonText, COL_TEXT)
    palette.setColor(QPalette.ColorRole.Highlight, COL_ACCENT)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)

    gui = VoiceMatcherGUI()
    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
