#!/usr/bin/env python3
# [@GHOST]{[@file<HeatmapRenderer.py>][@domain<gui>][@role<heatmap_renderer>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<heatmap_renderer>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{HeatmapRenderer — PyQt6 widget that renders EnergyFieldGraph as live heatmap. Red=bad, green=good. Force-directed animation. Target boxes show good state. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{HeatmapRenderer}
# [@METHOD]{Run,show,stop,step,tick,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<PyQt6 widget rendering EnergyFieldGraph as live heatmap. Red=bad, green=good, force-directed animation. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
HeatmapRenderer — Live PyQt6 heatmap for EnergyFieldGraph.

WHAT IT RENDERS:
  - Each node as a colored circle (red=far from target, green=arrived)
  - Target position as dashed blue box (the GOOD state)
  - Signal arrows showing direction of movement
  - Energy history bar at bottom
  - Real-time animation at 60fps

DEPENDS ON:
  - EnergyFieldGraph — the physics engine

USAGE:
  from EnergyFieldGraph import EnergyFieldGraph
  from HeatmapRenderer import HeatmapRenderer
  from PyQt6.QtWidgets import QApplication
  import sys

  engine = EnergyFieldGraph()
  engine.Run("build", {"nodes": [
      {"id": "Toolbar", "bad_x": 50, "bad_y": 50, "good_x": 300, "good_y": 50},
      {"id": "Sidebar", "bad_x": 50, "bad_y": 200, "good_x": 50, "good_y": 200},
      {"id": "Editor", "bad_x": 400, "bad_y": 300, "good_x": 400, "good_y": 250},
  ]})

  app = QApplication(sys.argv)
  renderer = HeatmapRenderer(param={"engine": engine})
  renderer.Run("show")
  sys.exit(app.exec())
"""

import sys
import math
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont


# ════════════════════════════════════════════
# RENDER CONSTANTS
# ════════════════════════════════════════════

RENDER_FPS = 16           # ms between frames (~60fps)
RENDER_WIDTH = 900
RENDER_HEIGHT = 600
RENDER_NODE_RADIUS = 20
RENDER_BG_COLOR = (20, 20, 20)
RENDER_TARGET_COLOR = (80, 200, 255)
RENDER_TEXT_COLOR = (255, 255, 255)
RENDER_ARROW_COLOR = (255, 255, 0)


class HeatmapRenderer(QWidget):
    """
    PyQt6 widget that renders EnergyFieldGraph as a live heatmap.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        super().__init__()
        p = param or {}
        self.state = {
            "config": {
                "fps": RENDER_FPS,
                "width": RENDER_WIDTH,
                "height": RENDER_HEIGHT,
                "node_radius": RENDER_NODE_RADIUS,
            },
            "engine": p.get("engine", None),
            "timer": None,
            "running": False,
            "step_count": 0,
            "max_steps": p.get("max_steps", 0),  # 0 = infinite
            "auto_stop": p.get("auto_stop", True),
        }
        self.setMinimumSize(self.state["config"]["width"], self.state["config"]["height"])
        self.setWindowTitle("UI Energy Field Heatmap")

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
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: %s" % command, 0))
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
        """Manually step the engine without timer."""
        if not self.state["engine"]:
            return (0, None, ("ERR_PARAMS", "engine required", 0))
        ok, data, err = self.state["engine"].Run("step")
        if not ok:
            return (0, None, err)
        self.update()
        return (1, data, None)

    def cmd_tick(self, params):
        """One timer tick — step engine + repaint."""
        self.tick()
        return (1, {"ticked": True}, None)

    # ════════════════════════════════════════════
    # INTERNAL — Qt painting
    # ════════════════════════════════════════════

    def tick(self):
        if not self.state["engine"]:
            return
        ok, data, err = self.state["engine"].Run("step")
        if not ok:
            return
        self.state["step_count"] += 1
        # Auto-stop if converged
        if self.state["auto_stop"] and data.get("converged", False):
            self.cmd_stop({})
        # Auto-stop at max steps
        maxSteps = self.state["max_steps"]
        if maxSteps > 0 and self.state["step_count"] >= maxSteps:
            self.cmd_stop({})
        self.update()

    def heatColor(self, score):
        """score: 0.0=red(far), 1.0=green(arrived)"""
        r = int(255 * (1.0 - score))
        g = int(255 * score)
        b = 120
        return QColor(r, g, b)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        bg = QColor(*RENDER_BG_COLOR)
        painter.fillRect(self.rect(), bg)

        engine = self.state["engine"]
        if not engine:
            painter.setPen(QPen(QColor(*RENDER_TEXT_COLOR)))
            painter.drawText(20, 30, "No engine connected")
            return

        # Get heatmap data
        ok, heatData, err = engine.Run("heatmap")
        if not ok:
            return

        ok, sigData, err2 = engine.Run("signal")
        if not ok:
            return

        radius = self.state["config"]["node_radius"]

        # Draw edges (relationships)
        painter.setPen(QPen(QColor(60, 60, 60), 1, Qt.PenStyle.DashLine))
        for edge in engine.state["edges"]:
            a = engine.state["nodes"].get(edge["a"])
            b = engine.state["nodes"].get(edge["b"])
            if a and b:
                painter.drawLine(int(a["x"] + radius), int(a["y"] + radius),
                                 int(b["x"] + radius), int(b["y"] + radius))

        # Draw target boxes (GOOD state)
        targetPen = QPen(QColor(*RENDER_TARGET_COLOR), 1, Qt.PenStyle.DashLine)
        painter.setPen(targetPen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for nodeId, heat in heatData["heatmap"].items():
            painter.drawRect(int(heat["good_x"]), int(heat["good_y"]), radius * 2, radius * 2)

        # Draw signal arrows
        arrowPen = QPen(QColor(*RENDER_ARROW_COLOR), 2)
        painter.setPen(arrowPen)
        for nodeId, sig in sigData["signals"].items():
            node = engine.state["nodes"].get(nodeId)
            if not node:
                continue
            sx = sig["signal_x"]
            sy = sig["signal_y"]
            mag = math.sqrt(sx * sx + sy * sy)
            if mag > 2:
                startX = int(node["x"] + radius)
                startY = int(node["y"] + radius)
                endX = int(startX + sx * 0.3)
                endY = int(startY + sy * 0.3)
                painter.drawLine(startX, startY, endX, endY)

        # Draw nodes (heatmap circles)
        font = QFont("Arial", 10)
        painter.setFont(font)
        for nodeId, heat in heatData["heatmap"].items():
            color = self.heatColor(heat["color"]["score"])
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(*RENDER_TEXT_COLOR), 1))
            painter.drawEllipse(int(heat["x"]), int(heat["y"]), radius * 2, radius * 2)
            # Label
            painter.setPen(QPen(QColor(*RENDER_TEXT_COLOR)))
            painter.drawText(int(heat["x"]), int(heat["y"] - 5), heat["label"])

        # Status text
        painter.setPen(QPen(QColor(*RENDER_TEXT_COLOR)))
        font2 = QFont("Arial", 12)
        painter.setFont(font2)
        statusY = self.height() - 20
        step = engine.state["step_count"]
        energy = sigData["total_energy"]
        converged = "✅ CONVERGED" if engine.state["converged"] else "🔄 OPTIMIZING"
        painter.drawText(10, statusY, "Step: %d  |  Energy: %.2f  |  %s" % (step, energy, converged))

        # Energy bar at bottom
        barY = self.height() - 10
        barWidth = self.width() - 20
        energyMax = 500.0
        energyNorm = min(energy / energyMax, 1.0)
        barFilled = int(barWidth * (1.0 - energyNorm))
        painter.fillRect(10, barY, barFilled, 4, QColor(0, 255, 0))
        painter.fillRect(10 + barFilled, barY, barWidth - barFilled, 4, QColor(255, 0, 0))


# ════════════════════════════════════════════
# MAIN — standalone demo
# ════════════════════════════════════════════

def main():
    from EnergyFieldGraph import EnergyFieldGraph
    app = QApplication(sys.argv)
    engine = EnergyFieldGraph()
    engine.Run("build", {"nodes": [
        {"id": "Toolbar",  "bad_x": 50,  "bad_y": 50,  "good_x": 300, "good_y": 50},
        {"id": "Sidebar",  "bad_x": 50,  "bad_y": 200, "good_x": 50,  "good_y": 200},
        {"id": "Editor",   "bad_x": 400, "bad_y": 300, "good_x": 400, "good_y": 250},
        {"id": "Status",   "bad_x": 400, "bad_y": 550, "good_x": 400, "good_y": 500},
        {"id": "Search",   "bad_x": 700, "bad_y": 100, "good_x": 600, "good_y": 100},
        {"id": "Settings", "bad_x": 700, "bad_y": 400, "good_x": 650, "good_y": 400},
    ], "edges": [
        {"a": "Toolbar", "b": "Sidebar", "type": "GROUP"},
        {"a": "Sidebar", "b": "Editor", "type": "FLOW"},
        {"a": "Editor", "b": "Status", "type": "FLOW"},
    ]})
    renderer = HeatmapRenderer(param={"engine": engine})
    renderer.Run("show")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
