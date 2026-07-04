#!/usr/bin/env python3
# [@GHOST]{[@file<BrainRenderer.py>][@domain<gui>][@role<brain_renderer>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<brain_renderer>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{BrainRenderer — PyQt6 live renderer for GuiAiBrain. Shows nodes moving, energy bar, learned weights changing, learning curve. The AI brain thinking in real time. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{BrainRenderer}
# [@METHOD]{Run,show,stop,tick,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<PyQt6 live renderer for GuiAiBrain showing nodes, energy bar, weights, learning curve. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded color values and layout dimensions. Uses QMainWindow subclass which may conflict with one-class-per-file rule.>][@todos<Move hardcoded colors/dimensions to Config.py. Consider separating renderer window class.>]}
"""
BrainRenderer — Live PyQt6 renderer for the GuiAiBrain.

WHAT IT SHOWS:
  LEFT SIDE:  The GUI layout — nodes as colored rectangles bouncing and settling
  RIGHT SIDE: The brain panel — learned weights, energy breakdown, learning curve

THE BRAIN PANEL SHOWS:
  - Current energy (big number, color-coded)
  - Energy breakdown (overlap, misalignment, constraint, unused, order reward)
  - Learned weights with bars (repulsion, dock_left, stability, etc.)
  - Learning curve (energy over time — should trend DOWN)
  - Weight evolution table (how weights changed)
  - Temperature and layout state

THE COLORS:
  - Nodes: blue=moving, green=settled, red=overlapping
  - Energy: green=stable, yellow=settling, red=unstable
  - Weights: bars grow as brain increases them

USAGE:
  from GuiAiBrain import GuiAiBrain
  from BrainRenderer import BrainRenderer
  from PyQt6.QtWidgets import QApplication
  import sys

  brain = GuiAiBrain()
  brain.Run("perceive", {"spec": ui_spec})
  brain.Run("anneal", {"temperature": 0.8})

  app = QApplication(sys.argv)
  renderer = BrainRenderer(param={"brain": brain})
  renderer.Run("show")
  sys.exit(app.exec())
"""

import sys
import math
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont


# ════════════════════════════════════════════
# RENDER CONSTANTS
# ════════════════════════════════════════════

RENDER_FPS = 33               # ms between frames (~30fps)
CANVAS_W = 600
CANVAS_H = 600
PANEL_W = 400
WINDOW_W = CANVAS_W + PANEL_W
WINDOW_H = CANVAS_H + 60     # +60 for bottom controls
BG_COLOR = (20, 20, 30)
PANEL_BG = (30, 30, 42)
ITEM_COLOR = (80, 140, 220)
OVERLAP_COLOR = (220, 60, 60)
SETTLED_COLOR = (60, 200, 100)
TEXT_COLOR = (220, 220, 220)
ANCHOR_COLOR = (255, 200, 80)
ENERGY_GOOD = (60, 200, 100)
ENERGY_MID = (255, 200, 50)
ENERGY_BAD = (220, 60, 60)
WEIGHT_COLOR = (100, 180, 255)
CURVE_COLOR = (100, 200, 255)


class BrainCanvas(QWidget):
    """Left side — draws the GUI layout nodes. Supports dragging + heatmap."""

    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        self.setFixedSize(CANVAS_W, CANVAS_H)
        self.setMouseTracking(True)
        self.dragId = None
        self.dragLastX = 0
        self.dragLastY = 0
        self.mouseX = 0
        self.mouseY = 0

    def mousePressEvent(self, event):
        brain = self.renderer.state["brain"]
        if not brain:
            return
        mx = event.position().x()
        my = event.position().y()
        # Find which node was clicked
        for nodeId, node in brain.state["graph"]["nodes"].items():
            if mx >= node["x"] and mx <= node["x"] + node["w"] and my >= node["y"] and my <= node["y"] + node["h"]:
                self.dragId = nodeId
                self.dragLastX = mx
                self.dragLastY = my
                self.renderer.state["brain"].state["layout_state"] = "user_drag"
                return

    def mouseMoveEvent(self, event):
        mx = event.position().x()
        my = event.position().y()
        self.mouseX = mx
        self.mouseY = my
        if self.dragId and self.renderer.state["brain"]:
            brain = self.renderer.state["brain"]
            node = brain.state["graph"]["nodes"].get(self.dragId)
            if node:
                # Inject drag as force override — move node toward mouse
                dx = mx - self.dragLastX
                dy = my - self.dragLastY
                node["vx"] = dx * 0.5
                node["vy"] = dy * 0.5
                self.dragLastX = mx
                self.dragLastY = my

    def mouseReleaseEvent(self, event):
        self.dragId = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(*BG_COLOR))

        brain = self.renderer.state["brain"]
        if not brain:
            painter.setPen(QPen(QColor(*TEXT_COLOR)))
            painter.drawText(20, 30, "No brain connected")
            return

        nodes = brain.state["graph"]["nodes"]
        constraints = brain.state["graph"]["constraints"]
        cfg = brain.state["config"]

        # Draw zone targets (VSCode structure)
        painter.setPen(QPen(QColor(50, 50, 70), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Top zone
        painter.drawRect(5, 5, CANVAS_W - 10, 40)
        painter.drawText(10, 25, "TOP ZONE")
        # Left zone
        painter.drawRect(5, 50, 200, CANVAS_H - 170)
        painter.drawText(10, 70, "LEFT ZONE")
        # Right zone
        painter.drawRect(CANVAS_W - 205, 50, 200, CANVAS_H - 170)
        painter.drawText(CANVAS_W - 200, 70, "RIGHT ZONE")
        # Bottom zone
        painter.drawRect(5, CANVAS_H - 115, CANVAS_W - 10, 110)
        painter.drawText(10, CANVAS_H - 95, "BOTTOM ZONE")
        # Center zone
        painter.drawRect(210, 50, CANVAS_W - 420, CANVAS_H - 170)
        painter.drawText(215, 70, "CENTER ZONE")

        # Draw anchor targets
        anchorPen = QPen(QColor(*ANCHOR_COLOR), 1, Qt.PenStyle.DashLine)
        painter.setPen(anchorPen)
        for con in constraints:
            node = nodes.get(con["id"])
            if not node:
                continue
            edge = con["edge"]
            if edge == "top":
                tx, ty = node["x"], 10
            elif edge == "bottom":
                tx, ty = node["x"], CANVAS_H - 110 - node["h"]
            elif edge == "left":
                tx, ty = 10, node["y"]
            elif edge == "right":
                tx, ty = CANVAS_W - 200, node["y"]
            else:
                tx, ty = node["x"], node["y"]
            painter.drawRect(int(tx), int(ty), node["w"], node["h"])

        # Compute per-node energy for heatmap
        nodeEnergies = self.computeNodeEnergies(brain)

        # Draw nodes
        font = QFont("Arial", 9)
        painter.setFont(font)
        nodeList = list(nodes.values())
        for i, node in enumerate(nodeList):
            overlapping = False
            overlapCount = 0
            for j, other in enumerate(nodeList):
                if i == j:
                    continue
                ax2 = node["x"] + node["w"]
                ay2 = node["y"] + node["h"]
                bx2 = other["x"] + other["w"]
                by2 = other["y"] + other["h"]
                if not (ax2 <= other["x"] or bx2 <= node["x"] or ay2 <= other["y"] or by2 <= node["y"]):
                    overlapping = True
                    overlapCount += 1
            speed = math.sqrt(node["vx"] ** 2 + node["vy"] ** 2)
            nodeId = node["id"]
            nodeEnergy = nodeEnergies.get(nodeId, 0)

            # Heatmap color — blend from green (low energy) to red (high energy)
            if overlapping:
                color = QColor(*OVERLAP_COLOR)
            elif speed < 0.5:
                # Heatmap: low energy = green, high = yellow, very high = orange
                eNorm = min(nodeEnergy / 200.0, 1.0)
                r = int(60 + eNorm * 195)
                g = int(200 - eNorm * 100)
                b = int(100 - eNorm * 80)
                color = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
            else:
                color = QColor(*ITEM_COLOR)

            # Highlight dragged node
            if nodeId == self.dragId:
                painter.setPen(QPen(QColor(255, 255, 0), 3))
            else:
                painter.setPen(QPen(QColor(*TEXT_COLOR), 1))

            painter.setBrush(QBrush(color))
            painter.drawRect(int(node["x"]), int(node["y"]), node["w"], node["h"])
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(int(node["x"] + 4), int(node["y"] + 14), node["label"])

            # Energy heatmap number
            painter.setPen(QPen(QColor(200, 200, 200)))
            fontTiny = QFont("Arial", 7)
            painter.setFont(fontTiny)
            painter.drawText(int(node["x"] + 4), int(node["y"] + node["h"] - 4), "e=%.0f" % nodeEnergy)
            painter.setFont(font)

            # Velocity arrow
            if speed > 0.5:
                painter.setPen(QPen(QColor(255, 255, 0), 2))
                cx = int(node["x"] + node["w"] / 2)
                cy = int(node["y"] + node["h"] / 2)
                ex = int(cx + node["vx"] * 3)
                ey = int(cy + node["vy"] * 3)
                painter.drawLine(cx, cy, ex, ey)

        # Status
        painter.setPen(QPen(QColor(*TEXT_COLOR)))
        font2 = QFont("Arial", 10)
        painter.setFont(font2)
        e = brain.state["energy"]
        temp = brain.state["temperature"]
        dragStr = "  DRAGGING: %s" % self.dragId if self.dragId else ""
        painter.drawText(10, CANVAS_H - 10,
            "E=%.0f  T=%.3f  State=%s  Adapt=%d%s" % (
                e["total"], temp, brain.state["layout_state"],
                brain.state["stats"]["adaptations"], dragStr))

    def computeNodeEnergies(self, brain):
        """Compute per-node energy for heatmap coloring."""
        nodes = brain.state["graph"]["nodes"]
        constraints = brain.state["graph"]["constraints"]
        cfg = brain.state["config"]
        cw = CANVAS_W
        ch = CANVAS_H
        energies = {}
        nodeList = list(nodes.values())
        for i, node in enumerate(nodeList):
            e = 0.0
            # Overlap energy
            for j, other in enumerate(nodeList):
                if i == j:
                    continue
                ox = max(0, min(node["x"] + node["w"], other["x"] + other["w"]) - max(node["x"], other["x"]))
                oy = max(0, min(node["y"] + node["h"], other["y"] + other["h"]) - max(node["y"], other["y"]))
                e += ox * oy * 0.1
            # Misalignment energy
            for con in constraints:
                if con["id"] != node["id"]:
                    continue
                edge = con["edge"]
                if edge == "left":
                    e += abs(node["x"] - 10) * con["strength"]
                elif edge == "right":
                    e += abs(node["x"] - (cw - 200)) * con["strength"]
                elif edge == "top":
                    e += abs(node["y"] - 10) * con["strength"]
                elif edge == "bottom":
                    e += abs(node["y"] - (ch - 110 - node["h"])) * con["strength"]
            # Motion energy
            speed = math.sqrt(node["vx"] ** 2 + node["vy"] ** 2)
            e += speed * 2
            energies[node["id"]] = e
        return energies


class BrainPanel(QWidget):
    """Right side — shows the brain's learned weights, energy, learning curve."""

    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        self.setFixedSize(PANEL_W, CANVAS_H)
        self.setStyleSheet("background-color: rgb(%d, %d, %d);" % PANEL_BG)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(*PANEL_BG))

        brain = self.renderer.state["brain"]
        if not brain:
            return

        e = brain.state["energy"]
        w = brain.state["weights"]
        wm = brain.state["world_model"]
        temp = brain.state["temperature"]
        y = 15

        # Title
        painter.setPen(QPen(QColor(100, 200, 255)))
        fontTitle = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(fontTitle)
        painter.drawText(10, y, "GUI AI BRAIN")
        y += 25

        # State
        painter.setPen(QPen(QColor(*TEXT_COLOR)))
        fontSmall = QFont("Arial", 9)
        painter.setFont(fontSmall)
        stateColor = QColor(60, 200, 100) if brain.state["layout_state"] == "stable" else QColor(255, 200, 50)
        painter.setPen(QPen(stateColor))
        painter.drawText(10, y, "State: %s  |  Ticks: %d  |  Adapt: %d" % (
            brain.state["layout_state"], brain.state["stats"]["ticks"],
            brain.state["stats"]["adaptations"]))
        y += 18

        # Temperature
        painter.setPen(QPen(QColor(*TEXT_COLOR)))
        tempStr = "Temp: %.4f" % temp
        if temp > 0.5:
            tempStr += " HOT"
        elif temp > 0.1:
            tempStr += " WARM"
        elif temp > 0.001:
            tempStr += " COOL"
        else:
            tempStr += " FROZEN"
        painter.drawText(10, y, tempStr)
        y += 22

        # Energy (big)
        fontBig = QFont("Arial", 18, QFont.Weight.Bold)
        painter.setFont(fontBig)
        if e["total"] < 0:
            eColor = QColor(60, 200, 100)
        elif e["total"] < 50:
            eColor = QColor(60, 200, 100)
        elif e["total"] < 500:
            eColor = QColor(255, 200, 50)
        else:
            eColor = QColor(220, 60, 60)
        painter.setPen(QPen(eColor))
        painter.drawText(10, y, "Energy: %.1f" % e["total"])
        y += 28

        # Energy bar
        barW = PANEL_W - 30
        energyNorm = min(abs(e["total"]) / 2000.0, 1.0)
        barFilled = int(barW * (1.0 - energyNorm))
        painter.fillRect(10, y, barFilled, 6, QColor(60, 200, 100))
        painter.fillRect(10 + barFilled, y, barW - barFilled, 6, QColor(220, 60, 60))
        y += 16

        # Energy breakdown
        painter.setPen(QPen(QColor(*TEXT_COLOR)))
        fontSmall2 = QFont("Arial", 8)
        painter.setFont(fontSmall2)
        painter.drawText(10, y, "ENERGY BREAKDOWN:")
        y += 14
        breakdown = [
            ("Overlap", e["overlap_cost"], (220, 60, 60)),
            ("Misalign", e["misalignment_cost"], (255, 200, 50)),
            ("Constrain", e["constraint_violation"], (220, 60, 60)),
            ("Unused", e["unused_space"], (150, 150, 150)),
            ("Order", e["order_reward"], (60, 200, 100)),
        ]
        for label, val, color in breakdown:
            painter.setPen(QPen(QColor(*TEXT_COLOR)))
            painter.drawText(15, y, "%-10s" % label)
            painter.setPen(QPen(QColor(*color)))
            painter.drawText(80, y, "%8.1f" % val)
            # Mini bar
            miniLen = min(int(abs(val) / 20), 100)
            if val < 0:
                painter.fillRect(150, y - 8, miniLen, 8, QColor(60, 200, 100))
            else:
                painter.fillRect(150, y - 8, miniLen, 8, QColor(*color))
            y += 13
        y += 8

        # Learned weights
        painter.setPen(QPen(QColor(100, 200, 255)))
        fontMed = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(fontMed)
        painter.drawText(10, y, "LEARNED WEIGHTS:")
        y += 16
        painter.setFont(fontSmall2)
        for wk in sorted(w.keys()):
            wv = w[wk]
            painter.setPen(QPen(QColor(*TEXT_COLOR)))
            painter.drawText(15, y, "%-18s" % wk)
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(120, y, "%.3f" % wv)
            # Weight bar
            barLen = min(int(wv * 30), 180)
            painter.fillRect(170, y - 8, barLen, 8, QColor(*WEIGHT_COLOR))
            y += 13
            if y > CANVAS_H - 120:
                break
        y += 10

        # Learning curve
        painter.setPen(QPen(QColor(100, 200, 255)))
        painter.setFont(fontMed)
        painter.drawText(10, y, "LEARNING CURVE:")
        y += 14
        hist = wm["energy_history"]
        if hist and y < CANVAS_H - 20:
            showSteps = min(len(hist), 30)
            maxE = max(max(hist), 1)
            minE = min(min(hist), 0)
            rangeE = max(maxE - minE, 1)
            curveW = PANEL_W - 30
            curveH = min(80, CANVAS_H - y - 10)
            # Draw curve as line graph
            painter.setPen(QPen(QColor(*CURVE_COLOR), 2))
            points = []
            for i in range(showSteps):
                idx = len(hist) - showSteps + i
                h = hist[idx]
                px = 10 + int(curveW * i / max(showSteps - 1, 1))
                py = y + curveH - int(curveH * (h - minE) / rangeE)
                py = max(y, min(y + curveH, py))
                points.append((px, py))
            for i in range(1, len(points)):
                painter.drawLine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
            # Draw min/max labels
            painter.setPen(QPen(QColor(*TEXT_COLOR)))
            painter.setFont(fontSmall2)
            painter.drawText(10, y - 2, "max=%.0f" % maxE)
            painter.drawText(10, y + curveH + 10, "min=%.0f" % minE)
            y += curveH + 20


class BrainRenderer(QMainWindow):
    """
    PyQt6 main window that renders GuiAiBrain live.
    Left: canvas with nodes. Right: brain panel with weights + energy + curve.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        super().__init__()
        p = param or {}
        self.state = {
            "config": {
                "fps": RENDER_FPS,
            },
            "brain": p.get("brain", None),
            "timer": None,
            "running": False,
            "auto_run": p.get("auto_run", True),
            "ticks_per_frame": p.get("ticks_per_frame", 3),
        }
        self.setWindowTitle("GUI AI Brain — Self-Organizing Layout")
        self.setFixedSize(WINDOW_W, WINDOW_H)
        self.buildUI()

    def Run(self, command, params=None):
        dispatch = {
            "show": self.cmd_show,
            "stop": self.cmd_stop,
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

    def buildUI(self):
        central = QWidget()
        mainLayout = QVBoxLayout(central)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)

        # Top area: canvas + brain panel side by side
        topWidget = QWidget()
        topLayout = QHBoxLayout(topWidget)
        topLayout.setContentsMargins(0, 0, 0, 0)
        topLayout.setSpacing(0)

        self.canvas = BrainCanvas(self)
        topLayout.addWidget(self.canvas)

        self.panel = BrainPanel(self)
        topLayout.addWidget(self.panel)

        mainLayout.addWidget(topWidget)

        # Bottom controls
        ctrlWidget = QWidget()
        ctrlWidget.setFixedHeight(60)
        ctrlWidget.setStyleSheet("background-color: rgb(35, 35, 45);")
        ctrlLayout = QHBoxLayout(ctrlWidget)
        ctrlLayout.setContentsMargins(10, 5, 10, 5)

        shakeBtn = QPushButton("SHAKE & LEARN")
        shakeBtn.setStyleSheet("QPushButton { background-color: rgb(200, 60, 60); color: white; font-size: 13px; padding: 8px 16px; border-radius: 4px; }")
        shakeBtn.clicked.connect(self.onShake)
        ctrlLayout.addWidget(shakeBtn)

        freezeBtn = QPushButton("FREEZE")
        freezeBtn.setStyleSheet("QPushButton { background-color: rgb(60, 100, 200); color: white; font-size: 13px; padding: 8px 16px; border-radius: 4px; }")
        freezeBtn.clicked.connect(self.onFreeze)
        ctrlLayout.addWidget(freezeBtn)

        resetBtn = QPushButton("RESET BRAIN")
        resetBtn.setStyleSheet("QPushButton { background-color: rgb(80, 80, 80); color: white; font-size: 13px; padding: 8px 16px; border-radius: 4px; }")
        resetBtn.clicked.connect(self.onReset)
        ctrlLayout.addWidget(resetBtn)

        ctrlLayout.addStretch()

        self.tickLabel = QLabel("Tick: 0")
        self.tickLabel.setStyleSheet("color: rgb(150, 200, 255); font-size: 12px;")
        ctrlLayout.addWidget(self.tickLabel)

        mainLayout.addWidget(ctrlWidget)
        self.setCentralWidget(central)

    def onShake(self):
        brain = self.state["brain"]
        if not brain:
            return
        brain.Run("anneal", {"temperature": 0.8})

    def onFreeze(self):
        brain = self.state["brain"]
        if not brain:
            return
        brain.Run("anneal", {"temperature": 0.0})

    def onReset(self):
        brain = self.state["brain"]
        if not brain:
            return
        for node in brain.state["graph"]["nodes"].values():
            node["vx"] = 0.0
            node["vy"] = 0.0
        brain.state["temperature"] = 0.0
        brain.state["world_model"]["energy_history"] = []
        brain.state["world_model"]["weight_history"] = []
        brain.state["stats"]["ticks"] = 0
        brain.state["stats"]["adaptations"] = 0

    def cmd_show(self, params):
        if not self.state["brain"]:
            return (0, None, ("ERR_PARAMS", "brain required in constructor", 0))
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

    def cmd_tick(self, params):
        self.tick()
        return (1, {"ticked": True}, None)

    def tick(self):
        brain = self.state["brain"]
        if not brain:
            return
        if self.state["auto_run"]:
            # Run multiple brain ticks per frame for faster convergence
            for _ in range(self.state["ticks_per_frame"]):
                ok, data, err = brain.Run("cycle", {"ticks": 1})
                if not ok:
                    break
        self.tickLabel.setText("Tick: %d  Adapt: %d  E: %.0f" % (
            brain.state["stats"]["ticks"],
            brain.state["stats"]["adaptations"],
            brain.state["energy"]["total"]))
        self.canvas.update()
        self.panel.update()


# ════════════════════════════════════════════
# MAIN — standalone demo
# ════════════════════════════════════════════

def main():
    from GuiAiBrain import GuiAiBrain
    app = QApplication(sys.argv)
    brain = GuiAiBrain()
    spec = {
        "items": [
            {"id": "toolbar", "type": "Toolbar", "role": "top", "x": 200, "y": 300, "w": 400, "h": 30, "label": "Toolbar"},
            {"id": "sidebar", "type": "Sidebar", "role": "left", "x": 400, "y": 100, "w": 180, "h": 350, "label": "Sidebar"},
            {"id": "editor", "type": "Editor", "role": "center", "x": 50, "y": 400, "w": 350, "h": 200, "label": "Editor"},
            {"id": "terminal", "type": "Terminal", "role": "bottom", "x": 100, "y": 50, "w": 400, "h": 80, "label": "Terminal"},
            {"id": "inspector", "type": "Inspector", "role": "right", "x": 50, "y": 100, "w": 180, "h": 300, "label": "Inspector"},
        ],
        "edges": [
            {"a": "toolbar", "b": "sidebar", "type": "adjacent", "strength": 0.5},
            {"a": "editor", "b": "terminal", "type": "adjacent", "strength": 0.4},
        ],
        "constraints": [
            {"id": "toolbar", "type": "dock", "edge": "top", "strength": 0.9},
            {"id": "sidebar", "type": "dock", "edge": "left", "strength": 0.8},
            {"id": "terminal", "type": "dock", "edge": "bottom", "strength": 0.7},
            {"id": "inspector", "type": "dock", "edge": "right", "strength": 0.6},
        ],
    }
    brain.Run("perceive", {"spec": spec})
    brain.Run("anneal", {"temperature": 0.8})
    renderer = BrainRenderer(param={"brain": brain, "ticks_per_frame": 2})
    renderer.Run("show")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
