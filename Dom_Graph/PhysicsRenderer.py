#!/usr/bin/env python3
# [@GHOST]{[@file<PhysicsRenderer.py>][@domain<gui>][@role<physics_renderer>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<physics_renderer>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{PhysicsRenderer — PyQt6 widget that renders GraphPhysics as live shake-the-bowl animation. Separate canvas + control panel. Items bounce, collide, settle. Temperature slider, shake button, energy bar. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{PhysicsRenderer}
# [@METHOD]{Run,show,stop,step,tick,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<PyQt6 widget rendering GraphPhysics as live shake-the-bowl animation. Items bounce, collide, settle. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
PhysicsRenderer — Live PyQt6 renderer for GraphPhysics shake-the-bowl engine.

WHAT IT SHOWS:
  - Each item as a colored rectangle (red=overlapping, green=settled)
  - Anchor targets as dashed outlines (where items should go)
  - Force lines between items (green=attract, red=repel)
  - Velocity arrows showing direction of movement
  - Temperature bar (hot → frozen)
  - Energy bar at bottom
  - Shake button + temperature slider

DEPENDS ON:
  - GraphPhysics — the physics annealing engine

USAGE:
  from GraphPhysics import GraphPhysics
  from PhysicsRenderer import PhysicsRenderer
  from PyQt6.QtWidgets import QApplication
  import sys

  engine = GraphPhysics()
  engine.Run("add", {"id": "toolbar", "type": "Toolbar", "x": 400, "y": 300, "w": 600, "h": 30})
  engine.Run("anchor", {"id": "toolbar", "edge": "top", "strength": 0.9})
  engine.Run("shake", {"temperature": 0.8})

  app = QApplication(sys.argv)
  renderer = PhysicsRenderer(param={"engine": engine})
  renderer.Run("show")
  sys.exit(app.exec())
"""

import sys
import math
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QSlider, QLabel,
    QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont


# ════════════════════════════════════════════
# RENDER CONSTANTS
# ════════════════════════════════════════════

RENDER_FPS = 16               # ms between frames (~60fps)
RENDER_WIDTH = 1000
RENDER_HEIGHT = 600
RENDER_PANEL_HEIGHT = 70      # control panel at bottom
RENDER_BG_COLOR = (25, 25, 35)
RENDER_ITEM_COLOR = (80, 140, 220)
RENDER_OVERLAP_COLOR = (220, 60, 60)
RENDER_SETTLED_COLOR = (60, 200, 100)
RENDER_ANCHOR_COLOR = (255, 200, 80)
RENDER_TEXT_COLOR = (255, 255, 255)
RENDER_ATTRACT_COLOR = (80, 220, 100)
RENDER_REPEL_COLOR = (220, 80, 80)
RENDER_VELOCITY_COLOR = (255, 255, 0)


class PhysicsCanvas(QWidget):
    """Inner canvas widget — draws the physics simulation."""

    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        self.setMinimumSize(RENDER_WIDTH, RENDER_HEIGHT)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        bg = QColor(*RENDER_BG_COLOR)
        painter.fillRect(self.rect(), bg)

        engine = self.renderer.state["engine"]
        if not engine:
            painter.setPen(QPen(QColor(*RENDER_TEXT_COLOR)))
            painter.drawText(20, 30, "No engine connected")
            return

        cfg = engine.state["config"]
        canvasW = RENDER_WIDTH
        canvasH = RENDER_HEIGHT

        # Draw canvas boundary
        painter.setPen(QPen(QColor(60, 60, 80), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(5, 5, canvasW - 10, canvasH - 10)

        # Draw anchor targets (dashed outlines)
        anchorPen = QPen(QColor(*RENDER_ANCHOR_COLOR), 1, Qt.PenStyle.DashLine)
        painter.setPen(anchorPen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for itemId, anchor in engine.state["anchors"].items():
            item = engine.state["items"].get(itemId)
            if not item:
                continue
            if anchor["edge"] == "top":
                tx, ty = item["x"], cfg["boundary_margin"]
            elif anchor["edge"] == "bottom":
                tx, ty = item["x"], canvasH - cfg["boundary_margin"] - item["h"]
            elif anchor["edge"] == "left":
                tx, ty = cfg["boundary_margin"], item["y"]
            elif anchor["edge"] == "right":
                tx, ty = canvasW - cfg["boundary_margin"] - item["w"], item["y"]
            elif anchor["edge"] == "center":
                tx, ty = (canvasW - item["w"]) / 2.0, (canvasH - item["h"]) / 2.0
            else:
                tx, ty = item["x"], item["y"]
            painter.drawRect(int(tx), int(ty), item["w"], item["h"])
            painter.setPen(QPen(QColor(*RENDER_ANCHOR_COLOR)))
            font = QFont("Arial", 8)
            painter.setFont(font)
            painter.drawText(int(tx + 2), int(ty + 10), "A:%s" % anchor["edge"][:1].upper())
            painter.setPen(anchorPen)

        # Draw force lines
        for f in engine.state["forces"]:
            a = engine.state["items"].get(f["a"])
            b = engine.state["items"].get(f["b"])
            if not a or not b:
                continue
            if f["type"] == "attract":
                pen = QPen(QColor(*RENDER_ATTRACT_COLOR), 2, Qt.PenStyle.DotLine)
            else:
                pen = QPen(QColor(*RENDER_REPEL_COLOR), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            ax = int(a["x"] + a["w"] / 2)
            ay = int(a["y"] + a["h"] / 2)
            bx = int(b["x"] + b["w"] / 2)
            by = int(b["y"] + b["h"] / 2)
            painter.drawLine(ax, ay, bx, by)

        # Draw items
        font = QFont("Arial", 10)
        painter.setFont(font)
        items = list(engine.state["items"].values())
        for i, item in enumerate(items):
            overlapping = False
            for j, other in enumerate(items):
                if i == j:
                    continue
                if engine.itemsOverlap(item, other):
                    overlapping = True
                    break
            speed = math.sqrt(item["vx"] ** 2 + item["vy"] ** 2)
            if overlapping:
                color = QColor(*RENDER_OVERLAP_COLOR)
            elif speed < 0.5:
                color = QColor(*RENDER_SETTLED_COLOR)
            else:
                color = QColor(*RENDER_ITEM_COLOR)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(*RENDER_TEXT_COLOR), 1))
            painter.drawRect(int(item["x"]), int(item["y"]), item["w"], item["h"])
            painter.setPen(QPen(QColor(*RENDER_TEXT_COLOR)))
            painter.drawText(int(item["x"] + 4), int(item["y"] + 14), item["label"])

            # Velocity arrow
            if speed > 0.5:
                painter.setPen(QPen(QColor(*RENDER_VELOCITY_COLOR), 2))
                cx = int(item["x"] + item["w"] / 2)
                cy = int(item["y"] + item["h"] / 2)
                ex = int(cx + item["vx"] * 5)
                ey = int(cy + item["vy"] * 5)
                painter.drawLine(cx, cy, ex, ey)

        # Status overlay
        painter.setPen(QPen(QColor(*RENDER_TEXT_COLOR)))
        font2 = QFont("Arial", 11)
        painter.setFont(font2)
        temp = engine.state["temperature"]
        ok, eData, _ = engine.Run("energy")
        energy = eData["energy"] if eData else 0
        collisions = eData["collisions"] if eData else 0
        step = engine.state["step_count"]
        if temp > 0.5:
            tempStatus = "HOT"
        elif temp > 0.1:
            tempStatus = "WARM"
        elif temp > 0.001:
            tempStatus = "COOL"
        else:
            tempStatus = "FROZEN"
        painter.drawText(10, canvasH - 25,
            "Step: %d  |  Energy: %.1f  |  Collisions: %d  |  Temp: %.3f %s" % (
                step, energy, collisions, temp, tempStatus))

        # Energy bar
        barY = canvasH - 12
        barWidth = canvasW - 20
        energyMax = 2000.0
        energyNorm = min(energy / energyMax, 1.0)
        barFilled = int(barWidth * (1.0 - energyNorm))
        painter.fillRect(10, barY, barFilled, 4, QColor(60, 200, 100))
        painter.fillRect(10 + barFilled, barY, barWidth - barFilled, 4, QColor(220, 60, 60))


class PhysicsRenderer(QMainWindow):
    """
    PyQt6 main window that renders GraphPhysics as a live shake-the-bowl animation.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Separate canvas widget + control panel.
    """

    def __init__(self, mem=None, db=None, param=None):
        super().__init__()
        p = param or {}
        self.state = {
            "config": {
                "fps": RENDER_FPS,
                "width": RENDER_WIDTH,
                "height": RENDER_HEIGHT + RENDER_PANEL_HEIGHT,
                "canvas_w": RENDER_WIDTH,
                "canvas_h": RENDER_HEIGHT,
            },
            "engine": p.get("engine", None),
            "timer": None,
            "running": False,
            "step_count": 0,
            "auto_anneal": p.get("auto_anneal", True),
            "cooling": p.get("cooling", 0.98),
        }
        self.setWindowTitle("Graph Physics — Shake the Bowl")
        self.setFixedSize(RENDER_WIDTH, RENDER_HEIGHT + RENDER_PANEL_HEIGHT)
        self.buildUI()

    def Run(self, command, params=None):
        dispatch = {
            "show": self.cmd_show,
            "stop": self.cmd_stop,
            "step": self.cmd_step,
            "tick": self.cmd_tick,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "unknown command", 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, {k: v for k, v in self.state.items() if k != "timer"}, None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # UI BUILD — canvas on top, controls at bottom
    # ════════════════════════════════════════════

    def buildUI(self):
        central = QWidget()
        mainLayout = QVBoxLayout(central)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)

        # Canvas widget (top)
        self.canvas = PhysicsCanvas(self)
        mainLayout.addWidget(self.canvas)

        # Control panel (bottom)
        panel = QWidget()
        panel.setFixedHeight(RENDER_PANEL_HEIGHT)
        panel.setStyleSheet("background-color: rgb(35, 35, 45);")
        panelLayout = QHBoxLayout(panel)
        panelLayout.setContentsMargins(10, 5, 10, 5)

        # Shake button
        shakeBtn = QPushButton("SHAKE")
        shakeBtn.setStyleSheet("QPushButton { background-color: rgb(200, 60, 60); color: white; font-size: 14px; padding: 8px 16px; border-radius: 4px; }")
        shakeBtn.clicked.connect(self.onShake)
        panelLayout.addWidget(shakeBtn)

        # Freeze button
        freezeBtn = QPushButton("FREEZE")
        freezeBtn.setStyleSheet("QPushButton { background-color: rgb(60, 100, 200); color: white; font-size: 14px; padding: 8px 16px; border-radius: 4px; }")
        freezeBtn.clicked.connect(self.onFreeze)
        panelLayout.addWidget(freezeBtn)

        # Reset button
        resetBtn = QPushButton("RESET")
        resetBtn.setStyleSheet("QPushButton { background-color: rgb(80, 80, 80); color: white; font-size: 14px; padding: 8px 16px; border-radius: 4px; }")
        resetBtn.clicked.connect(self.onReset)
        panelLayout.addWidget(resetBtn)

        # Temperature slider
        tempLabel = QLabel("Temp:")
        tempLabel.setStyleSheet("color: white; font-size: 12px;")
        panelLayout.addWidget(tempLabel)

        self.tempSlider = QSlider(Qt.Orientation.Horizontal)
        self.tempSlider.setRange(0, 100)
        self.tempSlider.setValue(80)
        self.tempSlider.setStyleSheet("QSlider { max-width: 150px; }")
        self.tempSlider.valueChanged.connect(self.onTempChange)
        panelLayout.addWidget(self.tempSlider)

        self.tempValueLabel = QLabel("0.80")
        self.tempValueLabel.setStyleSheet("color: rgb(255, 200, 80); font-size: 12px; min-width: 30px;")
        panelLayout.addWidget(self.tempValueLabel)

        panelLayout.addStretch()

        # Status label
        self.statusLabel = QLabel("Ready")
        self.statusLabel.setStyleSheet("color: rgb(150, 200, 255); font-size: 12px;")
        panelLayout.addWidget(self.statusLabel)

        mainLayout.addWidget(panel)
        self.setCentralWidget(central)

    def onShake(self):
        if not self.state["engine"]:
            return
        self.state["engine"].Run("shake", {"temperature": 0.8})
        self.tempSlider.setValue(80)
        self.statusLabel.setText("SHAKING!")

    def onFreeze(self):
        if not self.state["engine"]:
            return
        self.state["engine"].Run("shake", {"temperature": 0.0})
        self.tempSlider.setValue(0)
        self.statusLabel.setText("FROZEN")

    def onReset(self):
        if not self.state["engine"]:
            return
        for item in self.state["engine"].state["items"].values():
            item["vx"] = 0.0
            item["vy"] = 0.0
        self.state["engine"].state["temperature"] = 0.0
        self.state["engine"].state["step_count"] = 0
        self.state["engine"].state["energy_history"] = []
        self.tempSlider.setValue(0)
        self.statusLabel.setText("Reset")

    def onTempChange(self, value):
        temp = value / 100.0
        if self.state["engine"]:
            self.state["engine"].Run("shake", {"temperature": temp})
        self.tempValueLabel.setText("%.2f" % temp)
        if temp > 0.5:
            self.statusLabel.setText("HOT")
        elif temp > 0.1:
            self.statusLabel.setText("WARM")
        elif temp > 0.001:
            self.statusLabel.setText("COOL")
        else:
            self.statusLabel.setText("FROZEN")

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_show(self, params):
        if not self.state["engine"]:
            return (0, None, ("ERR_PARAMS", "engine required in constructor", 0))
        self.state["timer"] = QTimer(self)
        self.state["timer"].timeout.connect(self.tick)
        self.state["timer"].start(self.state["config"]["fps"])
        self.state["running"] = True
        self.show()
        return (1, {"showing": True, "fps": self.state["config"]["fps"]}, None)

    def cmd_stop(self, params):
        if self.state["timer"]:
            self.state["timer"].stop()
        self.state["running"] = False
        return (1, {"stopped": True}, None)

    def cmd_step(self, params):
        if not self.state["engine"]:
            return (0, None, ("ERR_PARAMS", "engine required", 0))
        ok, data, err = self.state["engine"].Run("step")
        if not ok:
            return (0, None, err)
        self.canvas.update()
        return (1, data, None)

    def cmd_tick(self, params):
        self.tick()
        return (1, {"ticked": True}, None)

    # ════════════════════════════════════════════
    # INTERNAL — animation loop
    # ════════════════════════════════════════════

    def tick(self):
        engine = self.state["engine"]
        if not engine:
            return
        # Auto-cool if temperature > 0
        if self.state["auto_anneal"] and engine.state["temperature"] > 0.001:
            engine.state["temperature"] *= self.state["cooling"]
            if engine.state["temperature"] < 0.001:
                engine.state["temperature"] = 0.0
                engine.state["frozen"] = True
                self.statusLabel.setText("Settled")
        ok, data, err = engine.Run("step")
        if not ok:
            return
        self.state["step_count"] += 1
        # Update slider to reflect cooling
        tempVal = int(engine.state["temperature"] * 100)
        self.tempSlider.blockSignals(True)
        self.tempSlider.setValue(tempVal)
        self.tempValueLabel.setText("%.2f" % engine.state["temperature"])
        self.tempSlider.blockSignals(False)
        self.canvas.update()


# ════════════════════════════════════════════
# MAIN — standalone demo
# ════════════════════════════════════════════

def main():
    from GraphPhysics import GraphPhysics
    app = QApplication(sys.argv)
    engine = GraphPhysics()
    # Items scattered in wrong positions
    engine.Run("add", {"id": "toolbar", "type": "Toolbar", "x": 400, "y": 300, "w": 600, "h": 30})
    engine.Run("add", {"id": "sidebar", "type": "Sidebar", "x": 700, "y": 100, "w": 200, "h": 400})
    engine.Run("add", {"id": "editor", "type": "Editor", "x": 50, "y": 500, "w": 400, "h": 300})
    engine.Run("add", {"id": "status", "type": "StatusBar", "x": 300, "y": 50, "w": 400, "h": 20})
    engine.Run("add", {"id": "panel", "type": "Panel", "x": 600, "y": 600, "w": 300, "h": 200})
    # Anchors
    engine.Run("anchor", {"id": "toolbar", "edge": "top", "strength": 0.9})
    engine.Run("anchor", {"id": "sidebar", "edge": "left", "strength": 0.8})
    engine.Run("anchor", {"id": "status", "edge": "bottom", "strength": 0.7})
    engine.Run("anchor", {"id": "editor", "edge": "center", "strength": 0.5})
    # Forces
    engine.Run("force", {"a": "toolbar", "b": "sidebar", "type": "repel", "strength": 0.6})
    engine.Run("force", {"a": "editor", "b": "panel", "type": "attract", "strength": 0.4})
    # Start shaking
    engine.Run("shake", {"temperature": 0.8})
    renderer = PhysicsRenderer(param={"engine": engine})
    renderer.Run("show")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
