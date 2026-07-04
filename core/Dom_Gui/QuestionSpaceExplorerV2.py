#!/usr/bin/env python3
# [@GHOST]{[@file<QuestionSpaceExplorerV2.py>][@domain<Dom_Gui>][@role<neural_inquiry>][@auth<devin>][@date<2026-07-04>][@ver<3.0.0>][@session<neural-question-space>]}
# [@VBSTYLE]{[@auth<devin>][@role<neural_inquiry>][@return<tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{V3 — Neural network of thinking. 3D semantic graph with edge weights, activation spreading, Hebbian learning, backpropagation, wave dynamics, fact graph layer, growth simulation, save/load brain state.}
# [@CLASS]{QuestionSpaceExplorerV2}
# [@METHOD]{Run,InitDb,LoadWeights,Activate,Spread,Train,Backprop,Wave,Grow,SaveBrain,LoadBrain,read_state,set_config}
# [@FILEID]{core/Dom_Gui/QuestionSpaceExplorerV2.py

"""
QuestionSpaceExplorerV2 V3 — Neural network of thinking.

Features:
  1. Edge weights from 141K real questions (strong vs weak synapses)
  2. Activation spreading (click = fire, spreads to neighbors)
  3. Hebbian learning (Train button strengthens co-activated edges)
  4. Backpropagation (select target, find best path to it)
  5. Wave dynamics (activation pulses travel along edges over time)
  6. Fact graph layer (yin/yang — facts feed activation into semantic graph)
  7. Growth simulation (holes slowly grow new edges = learning new reasoning)
  8. Save/load brain state (persist trained weights to MySQL)

Run: python3 QuestionSpaceExplorerV2.py
"""

import sys
import math
import sqlite3
import random
import json
import heapq
from collections import defaultdict, Counter, deque
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QToolBar, QSlider, QCheckBox,
    QSplitter, QTextEdit, QFrame, QInputDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPainterPath,
    QLinearGradient, QAction,
)


ATOMS = {
    "interrogative": ["WHAT", "WHO", "WHERE", "WHEN", "WHY", "HOW", "WHICH", "WHOM", "WHOSE"],
    "auxiliary": ["DO", "DID", "DOES", "IS", "ARE", "WAS", "WERE", "HAS", "HAVE", "HAD",
                   "CAN", "COULD", "SHOULD", "WOULD", "WILL", ""],
    "subject": ["{PERSON}", "{THING}", "{OBJECT}", "{SYSTEM}", "{USER}", "{FILE}",
                "{GRAPH}", "{LAW}", "{NODE}", "{EDGE}"],
    "action": ["GO", "CREATE", "DELETE", "MOVE", "READ", "WRITE", "BUILD",
               "LINK", "GENERATE", "CONNECT", ""],
    "object": ["{TARGET}", "{FILE}", "{DATABASE}", "{NODE}", "{GRAPH}",
               "{LAW}", "{QUESTION}", "{EDGE}", ""],
    "modifier": ["TODAY", "YESTERDAY", "NOW", "FIRST", "LAST", "NEAR",
                 "INSIDE", "OUTSIDE", "BEFORE", "AFTER", ""],
}

TOKEN_DIM = {
    "WHERE": "location", "WHEN": "temporal", "WHY": "causality", "HOW": "procedure",
    "WHAT": "identity", "WHO": "entity", "WHICH": "identity", "WHOM": "entity",
    "WHOSE": "entity", "TODAY": "temporal", "YESTERDAY": "temporal", "NOW": "temporal",
    "FIRST": "ordinal", "LAST": "ordinal", "BEFORE": "temporal", "AFTER": "temporal",
    "NEAR": "spatial", "INSIDE": "spatial", "OUTSIDE": "spatial",
}

DIM_COLORS = {
    "location": QColor(46, 120, 200), "temporal": QColor(40, 160, 80),
    "causality": QColor(200, 60, 60), "procedure": QColor(180, 130, 40),
    "identity": QColor(120, 80, 180), "entity": QColor(70, 110, 160),
    "spatial": QColor(80, 140, 100), "ordinal": QColor(140, 80, 120),
    "unknown": QColor(80, 80, 100),
}

LAYER_COLORS = {
    "inquiry": QColor(120, 80, 180),
    "bclir_class": QColor(40, 140, 200),
    "bclir_method": QColor(30, 100, 160),
    "bcl_rule": QColor(200, 140, 40),
    "graph": QColor(60, 160, 100),
    "comp_unit": QColor(220, 80, 60),
    "bcl_unit": QColor(180, 100, 200),
    "method_inv": QColor(80, 180, 180),
    "know_node": QColor(240, 200, 60),
    "know_answer": QColor(200, 180, 40),
    "know_problem": QColor(220, 60, 60),
    "know_solution": QColor(60, 200, 120),
    "memory_unit": QColor(100, 220, 220),
}

LAYER_NAMES = {
    "inquiry": "Inquiry Basis",
    "bclir_class": "BCLIR Class",
    "bclir_method": "BCLIR Method",
    "bcl_rule": "BCL Rule",
    "graph": "Graph Node",
    "comp_unit": "Computational Unit",
    "bcl_unit": "BCL Unit",
    "method_inv": "Method Inventory",
    "know_node": "Knowledge Q-Node",
    "know_answer": "Knowledge Answer",
    "know_problem": "Known Problem",
    "know_solution": "Known Solution",
    "memory_unit": "Memory Unit",
}

SLOTS = ["interrogative", "auxiliary", "subject", "action", "object", "modifier"]

IMPOSSIBLE = set()
_IMPOSSIBLE_RULES = [
    ("interrogative", "WHERE", "modifier", "FIRST"), ("interrogative", "WHERE", "modifier", "LAST"),
    ("interrogative", "WHY", "modifier", "NEAR"), ("interrogative", "WHY", "modifier", "INSIDE"),
    ("interrogative", "WHY", "modifier", "OUTSIDE"),
    ("interrogative", "HOW", "modifier", "YESTERDAY"), ("interrogative", "HOW", "modifier", "BEFORE"),
    ("interrogative", "HOW", "modifier", "AFTER"),
    ("interrogative", "WHO", "object", "{DATABASE}"), ("interrogative", "WHO", "object", "{GRAPH}"),
    ("interrogative", "WHO", "object", "{LAW}"), ("interrogative", "WHO", "object", "{NODE}"),
    ("interrogative", "WHO", "object", "{EDGE}"),
    ("interrogative", "WHOM", "subject", "{FILE}"), ("interrogative", "WHOM", "subject", "{GRAPH}"),
    ("interrogative", "WHOM", "subject", "{DATABASE}"),
    ("interrogative", "WHOSE", "subject", "{FILE}"), ("interrogative", "WHOSE", "subject", "{EDGE}"),
    ("interrogative", "WHEN", "modifier", "NEAR"), ("interrogative", "WHEN", "modifier", "INSIDE"),
    ("interrogative", "WHEN", "modifier", "OUTSIDE"),
    ("auxiliary", "HAS", "action", "GO"), ("auxiliary", "HAVE", "action", "GO"),
    ("auxiliary", "HAD", "action", "GO"),
    ("auxiliary", "IS", "action", "CREATE"), ("auxiliary", "IS", "action", "DELETE"),
    ("auxiliary", "IS", "action", "MOVE"), ("auxiliary", "IS", "action", "BUILD"),
    ("auxiliary", "IS", "action", "LINK"), ("auxiliary", "IS", "action", "GENERATE"),
    ("auxiliary", "IS", "action", "CONNECT"),
    ("auxiliary", "ARE", "action", "CREATE"), ("auxiliary", "ARE", "action", "DELETE"),
    ("auxiliary", "ARE", "action", "BUILD"),
    ("auxiliary", "WAS", "action", "CREATE"), ("auxiliary", "WAS", "action", "DELETE"),
    ("auxiliary", "WERE", "action", "BUILD"),
]
for sa, va, sb, vb in _IMPOSSIBLE_RULES:
    IMPOSSIBLE.add((sa, va, sb, vb))

FACT_GRAPH = [
    {"subject": "John", "relation": "went_to", "object": "Paris",
     "context": {"time": "yesterday", "reason": "business"},
     "questions": [
         ("interrogative:WHERE", "Where did John go?"),
         ("interrogative:WHO", "Who went to Paris?"),
         ("interrogative:WHEN", "When did John go to Paris?"),
         ("interrogative:WHY", "Why did John go to Paris?"),
         ("interrogative:HOW", "How did John get to Paris?"),
         ("interrogative:WHAT", "What is the relation between John and Paris?"),
     ]},
    {"subject": "John", "relation": "works_at", "object": "Acme",
     "context": {"time": "since 2020"},
     "questions": [
         ("interrogative:WHERE", "Where does John work?"),
         ("interrogative:WHO", "Who works at Acme?"),
         ("interrogative:WHEN", "Since when does John work at Acme?"),
         ("interrogative:WHAT", "What is John's role at Acme?"),
     ]},
    {"subject": "Paris", "relation": "located_in", "object": "France",
     "context": {},
     "questions": [
         ("interrogative:WHERE", "Where is Paris?"),
         ("interrogative:WHAT", "What is Paris part of?"),
         ("interrogative:WHO", "What is in France?"),
     ]},
    {"subject": "Acme", "relation": "builds", "object": "GraphEngine",
     "context": {"time": "ongoing"},
     "questions": [
         ("interrogative:WHAT", "What does Acme build?"),
         ("interrogative:WHO", "Who builds GraphEngine?"),
         ("interrogative:HOW", "How does Acme build GraphEngine?"),
         ("interrogative:WHY", "Why does Acme build GraphEngine?"),
     ]},
    {"subject": "GraphEngine", "relation": "uses", "object": "SQLite",
     "context": {"mode": "RAM"},
     "questions": [
         ("interrogative:WHAT", "What does GraphEngine use?"),
         ("interrogative:HOW", "How does GraphEngine use SQLite?"),
         ("interrogative:WHY", "Why does GraphEngine use SQLite?"),
     ]},
]


class NeuralGraph3D(QWidget):
    """3D neural graph with activation spreading and weighted edges."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = {
            "nodes": [],
            "edges": [],
            "holes": [],
            "weights": {},
            "activations": {},
            "rot_x": -0.4,
            "rot_y": 0.3,
            "zoom": 1.0,
            "hover": None,
            "selected": None,
            "auto_rotate": True,
            "spread_decay": 0.92,
            "max_activation": 1.0,
            "pulses": [],
            "path_highlight": [],
            "fact_active": None,
            "wave_mode": False,
        }
        self._drag = False
        self._last = None
        self._pos3d = {}
        self._vel = {}
        self._tick_count = 0
        self.setMinimumSize(600, 500)
        self.setStyleSheet("background: #080a10;")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._Tick)
        self._timer.start(50)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, params):
        if isinstance(params, dict):
            self.state.update(params)
        return (1, dict(self.state), None)

    def SetGraph(self, nodes, edges, holes, weights):
        self.state["nodes"] = nodes
        self.state["edges"] = edges
        self.state["holes"] = holes
        self.state["weights"] = weights
        self.state["activations"] = {n["id"]: 0.0 for n in nodes}
        self._InitLayout()
        self.update()

    def _InitLayout(self):
        nodes = self.state["nodes"]
        n = len(nodes)
        self._pos3d = {}
        self._vel = {}
        for i, node in enumerate(nodes):
            phi = math.acos(1 - 2 * (i + 0.5) / n)
            theta = math.pi * (1 + 5 ** 0.5) * i
            r = 180
            self._pos3d[node["id"]] = [
                r * math.sin(phi) * math.cos(theta),
                r * math.sin(phi) * math.sin(theta),
                r * math.cos(phi),
            ]
            self._vel[node["id"]] = [0, 0, 0]
        for _ in range(100):
            self._ForceStep()

    def _ForceStep(self):
        nodes = self.state["nodes"]
        edges = self.state["edges"]
        pos = self._pos3d
        vel = self._vel
        if not pos:
            return
        rep = 1200
        att = 0.003
        damp = 0.82
        pull = 0.002
        for n1 in nodes:
            nid1 = n1["id"]
            if nid1 not in pos:
                continue
            fx = fy = fz = 0
            for n2 in nodes:
                nid2 = n2["id"]
                if nid1 == nid2 or nid2 not in pos:
                    continue
                dx = pos[nid1][0] - pos[nid2][0]
                dy = pos[nid1][1] - pos[nid2][1]
                dz = pos[nid1][2] - pos[nid2][2]
                d = math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01
                f = rep / (d * d)
                fx += f * dx / d
                fy += f * dy / d
                fz += f * dz / d
            fx -= pull * pos[nid1][0]
            fy -= pull * pos[nid1][1]
            fz -= pull * pos[nid1][2]
            vel[nid1][0] = (vel[nid1][0] + fx) * damp
            vel[nid1][1] = (vel[nid1][1] + fy) * damp
            vel[nid1][2] = (vel[nid1][2] + fz) * damp
        es = set((e["source"], e["target"]) for e in edges)
        for sid, tid in es:
            if sid not in pos or tid not in pos:
                continue
            dx = pos[tid][0] - pos[sid][0]
            dy = pos[tid][1] - pos[sid][1]
            dz = pos[tid][2] - pos[sid][2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01
            w = self.state["weights"].get("%s|%s" % (sid, tid), 1.0)
            f = att * d * (0.5 + w * 0.5)
            vel[sid][0] += f * dx / d
            vel[sid][1] += f * dy / d
            vel[sid][2] += f * dz / d
            vel[tid][0] -= f * dx / d
            vel[tid][1] -= f * dy / d
            vel[tid][2] -= f * dz / d
        for nid in pos:
            pos[nid][0] += vel[nid][0]
            pos[nid][1] += vel[nid][1]
            pos[nid][2] += vel[nid][2]

    def _Project(self, x, y, z):
        rx = self.state["rot_x"]
        ry = self.state["rot_y"]
        cy, sy = math.cos(ry), math.sin(ry)
        cx, sx = math.cos(rx), math.sin(rx)
        x2 = x * cy - z * sy
        z2 = x * sy + z * cy
        y2 = y * cx - z2 * sx
        z3 = y * sx + z2 * cx
        fov = 700
        zoom = self.state["zoom"]
        s = fov / (fov + z3) * zoom
        return self.width() / 2 + x2 * s, self.height() / 2 + y2 * s, s, z3

    def _Tick(self):
        self._tick_count += 1
        if self.state["auto_rotate"] and not self._drag:
            self.state["rot_y"] += 0.005
        acts = self.state["activations"]
        decay = self.state["spread_decay"]
        changed = False
        for nid in acts:
            if acts[nid] > 0.01:
                acts[nid] *= decay
                changed = True
            elif acts[nid] != 0:
                acts[nid] = 0
                changed = True

        pulses = self.state["pulses"]
        if pulses:
            new_pulses = []
            for pulse in pulses:
                pulse["progress"] += pulse["speed"]
                if pulse["progress"] < 1.0:
                    if pulse["progress"] > 0.5 and not pulse.get("delivered"):
                        pulse["delivered"] = True
                        tgt = pulse["target"]
                        src = pulse["source"]
                        w = self.state["weights"].get("%s|%s" % (src, tgt),
                            self.state["weights"].get("%s|%s" % (tgt, src), 0.05))
                        acts[tgt] = min(1.0, acts.get(tgt, 0) + pulse["strength"] * w)
                    new_pulses.append(pulse)
                else:
                    changed = True
            self.state["pulses"] = new_pulses
            changed = True

        if changed or self.state["auto_rotate"] or pulses:
            self.update()

    def Activate(self, node_id, strength=1.0):
        acts = self.state["activations"]
        acts[node_id] = min(1.0, acts.get(node_id, 0) + strength)
        edges = self.state["edges"]
        weights = self.state["weights"]
        if self.state.get("wave_mode"):
            self._EmitPulses(node_id, strength)
        else:
            for e in edges:
                src = e["source"]
                tgt = e["target"]
                w = weights.get("%s|%s" % (src, tgt), weights.get("%s|%s" % (tgt, src), 0.05))
                if src == node_id:
                    spread = strength * 0.4 * w
                    acts[tgt] = min(1.0, acts.get(tgt, 0) + spread)
                elif tgt == node_id:
                    spread = strength * 0.4 * w
                    acts[src] = min(1.0, acts.get(src, 0) + spread)
        self.state["selected"] = node_id
        self.update()

    def _EmitPulses(self, node_id, strength):
        edges = self.state["edges"]
        weights = self.state["weights"]
        for e in edges:
            src = e["source"]
            tgt = e["target"]
            w = weights.get("%s|%s" % (src, tgt), weights.get("%s|%s" % (tgt, src), 0.05))
            if src == node_id:
                self.state["pulses"].append({
                    "source": src, "target": tgt,
                    "progress": 0.0, "speed": 0.04 + w * 0.03,
                    "strength": strength * 0.5, "delivered": False,
                })
            elif tgt == node_id:
                self.state["pulses"].append({
                    "source": tgt, "target": src,
                    "progress": 0.0, "speed": 0.04 + w * 0.03,
                    "strength": strength * 0.5, "delivered": False,
                })

    def SetPathHighlight(self, path_edges):
        self.state["path_highlight"] = path_edges
        self.update()

    def ClearPathHighlight(self):
        self.state["path_highlight"] = []
        self.update()

    def ActivateFromFact(self, fact_idx, node_ids):
        """Fact graph feeds activation into semantic nodes."""
        self.state["fact_active"] = fact_idx
        for nid in node_ids:
            self.Activate(nid, 0.7)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            closest = self._PickNode(pos.x(), pos.y())
            if closest:
                self.Activate(closest["id"], 1.0)
                parent = self.parent()
                while parent and not isinstance(parent, QuestionSpaceExplorerV2):
                    parent = parent.parent()
                if parent:
                    parent.OnNodeActivated(closest)
            else:
                self._drag = True
                self._last = pos
        elif event.button() == Qt.MouseButton.RightButton:
            pos = event.position()
            closest = self._PickNode(pos.x(), pos.y())
            if closest:
                self.state["backprop_target"] = closest["id"]
                parent = self.parent()
                while parent and not isinstance(parent, QuestionSpaceExplorerV2):
                    parent = parent.parent()
                if parent:
                    parent.OnBackpropTarget(closest)

    def _PickNode(self, mx, my):
        closest = None
        closest_d = 999
        for node in self.state["nodes"]:
            nid = node["id"]
            if nid not in self._pos3d:
                continue
            sx, sy, scale, _ = self._Project(*self._pos3d[nid])
            d = ((sx - mx) ** 2 + (sy - my) ** 2) ** 0.5
            if d < 18 * scale and d < closest_d:
                closest_d = d
                closest = node
        return closest

    def mouseMoveEvent(self, event):
        if self._drag and self._last:
            dx = event.position().x() - self._last.x()
            dy = event.position().y() - self._last.y()
            self.state["rot_y"] += dx * 0.01
            self.state["rot_x"] += dy * 0.01
            self._last = event.position()
            self.update()
        else:
            node = self._PickNode(event.position().x(), event.position().y())
            if node != self.state.get("hover"):
                self.state["hover"] = node
                self.update()

    def mouseReleaseEvent(self, event):
        self._drag = False
        self._last = None

    def wheelEvent(self, event):
        d = event.angleDelta().y()
        if d > 0:
            self.state["zoom"] *= 1.15
        else:
            self.state["zoom"] /= 1.15
        self.state["zoom"] = max(0.2, min(5.0, self.state["zoom"]))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor(8, 10, 16))

        painter.setPen(QPen(QColor(16, 18, 26), 1))
        for x in range(0, rect.width(), 60):
            painter.drawLine(QPointF(x, 0), QPointF(x, rect.height()))
        for y in range(0, rect.height(), 60):
            painter.drawLine(QPointF(0, y), QPointF(rect.width(), y))

        nodes = self.state["nodes"]
        edges = self.state["edges"]
        holes = self.state["holes"]
        weights = self.state["weights"]
        acts = self.state["activations"]
        pos = self._pos3d

        if not nodes or not pos:
            painter.setPen(QPen(QColor(100, 100, 120)))
            painter.setFont(QFont("Menlo", 14))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             "Building neural graph...")
            return

        proj = {}
        depths = {}
        for node in nodes:
            nid = node["id"]
            if nid not in pos:
                continue
            sx, sy, s, d = self._Project(*pos[nid])
            proj[nid] = (sx, sy, s)
            depths[nid] = d

        hole_set = set((h["source"], h["target"]) for h in holes)
        max_w = max(weights.values()) if weights else 1.0

        edge_list = []
        for e in edges:
            src, tgt = e["source"], e["target"]
            if src not in proj or tgt not in proj:
                continue
            avg_d = (depths[src] + depths[tgt]) / 2
            edge_list.append((avg_d, e))
        edge_list.sort(key=lambda x: x[0], reverse=True)

        path_set = set()
        for pe in self.state.get("path_highlight", []):
            path_set.add((pe[0], pe[1]))

        for avg_d, e in edge_list:
            src, tgt = e["source"], e["target"]
            sx1, sy1, s1 = proj[src]
            sx2, sy2, s2 = proj[tgt]
            is_hole = (src, tgt) in hole_set
            is_path = (src, tgt) in path_set or (tgt, src) in path_set
            w = weights.get("%s|%s" % (src, tgt), weights.get("%s|%s" % (tgt, src), 0.0))
            a_src = acts.get(src, 0)
            a_tgt = acts.get(tgt, 0)
            a_avg = (a_src + a_tgt) / 2

            if is_path:
                painter.setPen(QPen(QColor(100, 255, 100, 220), 3))
            elif is_hole:
                painter.setPen(QPen(QColor(120, 40, 40, 50), 1, Qt.PenStyle.DashLine))
            else:
                dim = e.get("dimension", "unknown")
                if dim == "bclir":
                    base = QColor(40, 100, 160)
                elif dim == "bcl":
                    base = QColor(180, 130, 40)
                elif dim == "graph":
                    base = QColor(50, 130, 80)
                elif dim == "cross_layer":
                    base = QColor(140, 100, 200)
                else:
                    base = DIM_COLORS.get(dim, QColor(60, 70, 90))
                if a_avg > 0.05:
                    r = int(base.red() + (255 - base.red()) * a_avg)
                    g = int(base.green() + (200 - base.green()) * a_avg)
                    b = int(base.blue() + (80 - base.blue()) * a_avg)
                    alpha = int(60 + 195 * a_avg)
                    thick = 1 + 3 * w / max_w + 2 * a_avg
                    painter.setPen(QPen(QColor(r, g, b, alpha), thick))
                else:
                    alpha = int(max(20, 120 - abs(avg_d) * 0.2))
                    thick = 0.5 + 2.5 * w / max_w
                    painter.setPen(QPen(QColor(base.red(), base.green(), base.blue(), alpha), thick))
            painter.drawLine(QPointF(sx1, sy1), QPointF(sx2, sy2))

        pulses = self.state.get("pulses", [])
        for pulse in pulses:
            src = pulse["source"]
            tgt = pulse["target"]
            prog = pulse["progress"]
            if src not in proj or tgt not in proj:
                continue
            sx1, sy1, s1 = proj[src]
            sx2, sy2, s2 = proj[tgt]
            px = sx1 + (sx2 - sx1) * prog
            py = sy1 + (sy2 - sy1) * prog
            pr = 4 * s1
            glow = QColor(255, 220, 80, 200)
            painter.setBrush(QBrush(glow))
            painter.setPen(QPen(QColor(255, 240, 120, 255), 1))
            painter.drawEllipse(QPointF(px, py), pr, pr)

        node_list = sorted(depths.items(), key=lambda x: x[1], reverse=True)
        for nid, depth in node_list:
            node = None
            for n in nodes:
                if n["id"] == nid:
                    node = n
                    break
            if not node:
                continue
            sx, sy, scale = proj[nid]
            layer = node.get("layer", "inquiry")
            if layer == "inquiry":
                dim = node.get("dimension", "unknown")
                base = DIM_COLORS.get(dim, QColor(80, 80, 100))
            else:
                base = LAYER_COLORS.get(layer, QColor(80, 80, 100))
            act = acts.get(nid, 0)
            if layer == "bclir_class":
                r = max(6, 16 * scale)
            elif layer == "bclir_method":
                r = max(3, 8 * scale)
            elif layer == "bcl_rule":
                r = max(4, 10 * scale)
            else:
                r = max(5, 12 * scale)

            if act > 0.05:
                glow_r = r + 15 * act
                for gr in range(int(glow_r), int(r), -2):
                    ga = int(80 * act * (1 - (gr - r) / max(glow_r - r, 1)))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor(255, 220, 80, ga), 1))
                    painter.drawEllipse(QPointF(sx, sy), gr, gr)

            grad = QLinearGradient(sx, sy - r, sx, sy + r)
            if act > 0.1:
                grad.setColorAt(0, QColor(255, 230, 100))
                grad.setColorAt(1, QColor(200, 150, 30))
            else:
                grad.setColorAt(0, base.lighter(140))
                grad.setColorAt(1, base.darker(160))
            painter.setBrush(QBrush(grad))

            is_hover = self.state.get("hover") and self.state["hover"]["id"] == nid
            is_sel = self.state.get("selected") == nid
            if is_sel:
                painter.setPen(QPen(QColor(255, 200, 50), 2.5))
                r += 4
            elif is_hover:
                painter.setPen(QPen(QColor(180, 200, 255), 2))
                r += 2
            else:
                painter.setPen(QPen(base.lighter(180), 1))
            painter.drawEllipse(QPointF(sx, sy), r, r)

            if scale > 0.35 or is_hover or is_sel or act > 0.3:
                label_color = QColor(255, 240, 180) if act > 0.1 else QColor(160, 170, 190)
                painter.setPen(QPen(label_color))
                painter.setFont(QFont("Menlo", max(6, int(7 * scale)), QFont.Weight.Bold))
                painter.drawText(QRectF(sx - r - 5, sy - r - 14, 2 * r + 10, 14),
                                 Qt.AlignmentFlag.AlignCenter, node["label"][:10])

        hover = self.state.get("hover")
        sel = self.state.get("selected")
        info_node = None
        if sel and isinstance(sel, dict):
            info_node = sel
        elif hover and isinstance(hover, dict):
            info_node = hover
        elif sel and isinstance(sel, str):
            for n in nodes:
                if n["id"] == sel:
                    info_node = n
                    break
        if info_node:
            nid = info_node["id"]
            act = acts.get(nid, 0)
            conn = sum(1 for e in edges if e["source"] == nid or e["target"] == nid)
            painter.setPen(QPen(QColor(255, 220, 100)))
            painter.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(15, rect.height() - 60, 400, 20),
                             Qt.AlignmentFlag.AlignLeft,
                             "%s  [%s]  %s" % (info_node["label"], info_node["type"],
                                LAYER_NAMES.get(info_node.get("layer", "inquiry"),
                                info_node.get("dimension", "?"))))
            painter.setPen(QPen(QColor(180, 190, 210)))
            painter.setFont(QFont("Menlo", 9))
            painter.drawText(QRectF(15, rect.height() - 42, 400, 20),
                             Qt.AlignmentFlag.AlignLeft,
                             "connections: %d  activation: %.0f%%" % (conn, act * 100))

        painter.setPen(QPen(QColor(60, 60, 80)))
        painter.setFont(QFont("Menlo", 8))
        painter.drawText(QRectF(rect.width() - 130, 12, 120, 18),
                         Qt.AlignmentFlag.AlignRight, "zoom: %.1fx" % self.state["zoom"])
        painter.drawText(QRectF(10, 12, 300, 18),
                         Qt.AlignmentFlag.AlignLeft, "click=activate  drag=rotate  wheel=zoom")
        active_count = sum(1 for v in acts.values() if v > 0.05)
        pulse_count = len(self.state.get("pulses", []))
        wave_str = " | %d pulses" % pulse_count if pulse_count else ""
        fact_str = ""
        if self.state.get("fact_active") is not None:
            fact_str = " | FACT[%d]" % self.state["fact_active"]
        path_str = ""
        if self.state.get("path_highlight"):
            path_str = " | PATH: %d edges" % len(self.state["path_highlight"])
        painter.drawText(QRectF(0, rect.height() - 18, rect.width(), 18),
                         Qt.AlignmentFlag.AlignCenter,
                         "%d nodes | %d edges | %d holes | %d active%s%s%s" % (
                             len(nodes), len(edges) - len(holes), len(holes),
                             active_count, wave_str, fact_str, path_str))


class InfoPanel(QFrame):
    """Clean info panel — shows activation log and stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background: #0c0e16; border: none; border-left: 1px solid #1a1c28; }"
        )
        self.setFixedWidth(300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("NEURAL ACTIVITY")
        title.setStyleSheet("color: #5070a0; font-size: 10px; font-weight: bold; font-family: Menlo;")
        layout.addWidget(title)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(
            "QTextEdit { background: #080a10; color: #a0b0c0; font-family: Menlo; font-size: 10px; border: 1px solid #1a1c28; border-radius: 4px; }"
        )
        layout.addWidget(self.log)

        self.stats = QLabel("Ready")
        self.stats.setStyleSheet("color: #607080; font-size: 10px; font-family: Menlo; padding: 4px;")
        self.stats.setWordWrap(True)
        layout.addWidget(self.stats)

    def Log(self, text):
        self.log.append(text)

    def SetStats(self, text):
        self.stats.setText(text)


class QuestionSpaceExplorerV2(QMainWindow):
    """V2 — Neural network of thinking. Clean, focused, 3D-first."""

    def __init__(self):
        super().__init__()
        self.state = {
            "db": None,
            "nodes": [],
            "edges": [],
            "holes": [],
            "weights": {},
            "activation_log": [],
            "train_count": 0,
        }
        self.setWindowTitle("Neural Inquiry — 3D Semantic Graph V2")
        self.setStyleSheet("QMainWindow { background: #080a10; }")
        self.InitDb()
        self.InitUi()
        self.LoadWeightsFromDb()
        self.BuildGraph()

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, params):
        if isinstance(params, dict):
            self.state.update(params)
        return (1, dict(self.state), None)

    def InitDb(self):
        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.execute("CREATE TABLE token (id INTEGER PRIMARY KEY, type TEXT, value TEXT, dimension TEXT)")
        idx = 1
        for token_type, values in ATOMS.items():
            for val in values:
                dim = TOKEN_DIM.get(val.upper(), None)
                db.execute("INSERT INTO token (id, type, value, dimension) VALUES (?, ?, ?, ?)",
                           (idx, token_type, val, dim))
                idx += 1
        db.commit()
        self.state["db"] = db

    def LoadWeightsFromDb(self):
        """Load edge weights from 141K real questions in MySQL."""
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host="localhost", user="root", password="",
                database="laws", unix_socket="/tmp/mysql.sock"
            )
            cur = conn.cursor()
            cur.execute("SELECT questionText, question_type_id FROM question LIMIT 50000")
            rows = cur.fetchall()
            cur.close()
            conn.close()
        except Exception:
            rows = []

        word_map = {}
        for val in ATOMS["interrogative"]:
            word_map[val.lower()] = val
        for val in ATOMS["subject"]:
            word_map[val.lower()] = val
        for val in ATOMS["action"]:
            if val:
                word_map[val.lower()] = val
        for val in ATOMS["object"]:
            if val:
                word_map[val.lower()] = val
        for val in ATOMS["modifier"]:
            if val:
                word_map[val.lower()] = val

        pair_counts = Counter()
        for text, qtype_id in rows:
            if not text:
                continue
            lower = text.strip().lower()
            found_tokens = set()
            for keyword, token in word_map.items():
                if keyword in lower:
                    found_tokens.add(token)
            found_list = sorted(found_tokens)
            for i in range(len(found_list)):
                for j in range(i + 1, len(found_list)):
                    pair_counts[(found_list[i], found_list[j])] += 1

        weights = {}
        max_count = max(pair_counts.values()) if pair_counts else 1
        for (t1, t2), cnt in pair_counts.items():
            for s1 in SLOTS:
                if t1 in ATOMS.get(s1, []):
                    for s2 in SLOTS:
                        if t2 in ATOMS.get(s2, []) and s1 < s2:
                            key = "%s:%s|%s:%s" % (s1, t1, s2, t2)
                            weights[key] = cnt / max_count
                            break
                    break
        self.state["weights"] = weights

    def BuildGraph(self):
        db = self.state["db"]
        cur = db.execute("SELECT type, value, dimension FROM token WHERE value != '' ORDER BY type, value")
        nodes = []
        for t, v, d in cur.fetchall():
            nodes.append({"id": "%s:%s" % (t, v), "label": v, "type": t, "dimension": d or "unknown"})

        node_ids = set(n["id"] for n in nodes)
        edges = []
        holes = []
        for i, t1 in enumerate(SLOTS):
            for j, t2 in enumerate(SLOTS):
                if i >= j:
                    continue
                for v1 in ATOMS.get(t1, []):
                    if not v1:
                        continue
                    for v2 in ATOMS.get(t2, []):
                        if not v2:
                            continue
                        is_imp = (t1, v1, t2, v2) in IMPOSSIBLE
                        dim = TOKEN_DIM.get(v1.upper(), TOKEN_DIM.get(v2.upper(), "unknown"))
                        edge = {
                            "source": "%s:%s" % (t1, v1),
                            "target": "%s:%s" % (t2, v2),
                            "dimension": dim or "unknown",
                            "is_hole": is_imp,
                        }
                        if edge["source"] in node_ids and edge["target"] in node_ids:
                            edges.append(edge)
                            if is_imp:
                                holes.append(edge)

        self.state["nodes"] = nodes
        self.state["edges"] = edges
        self.state["holes"] = holes
        self.graph.SetGraph(nodes, edges, holes, self.state["weights"])

        w_count = len(self.state["weights"])
        self.info.SetStats("Nodes: %d | Edges: %d | Holes: %d\nWeighted: %d edges from real questions" % (
            len(nodes), len(edges) - len(holes), len(holes), w_count
        ))
        self.info.Log("=" * 40)
        self.info.Log("Neural graph initialized")
        self.info.Log("  %d semantic atoms" % len(nodes))
        self.info.Log("  %d synapses" % (len(edges) - len(holes)))
        self.info.Log("  %d dormant (holes)" % len(holes))
        self.info.Log("  %d weighted edges" % w_count)
        self.info.Log("=" * 40)
        self.info.Log("")
        self.info.Log("Click any node to activate.")
        self.info.Log("Activation spreads to neighbors.")
        self.info.Log("")

    def InitUi(self):
        central = QWidget()
        central.setStyleSheet("background: #080a10;")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar("Neural", self)
        toolbar.setMovable(False)
        toolbar.setStyleSheet(
            "QToolBar { background: #0c0e16; border: none; border-bottom: 1px solid #1a1c28; padding: 3px; spacing: 6px; }"
            "QToolBar QToolButton { background: #14161e; color: #8090a0; border: 1px solid #20222e; padding: 5px 14px; border-radius: 4px; font-size: 11px; font-family: Menlo; }"
            "QToolBar QToolButton:hover { background: #1e2030; color: #a0b0c0; }"
            "QToolBar QToolButton:checked { background: #2a3040; color: #c0d0e0; border-color: #4060a0; }"
            "QToolBar QLabel { color: #506070; font-size: 10px; font-family: Menlo; padding: 0 6px; }"
        )
        self.addToolBar(toolbar)

        self.act_rotate = QAction("Auto-Rotate", self)
        self.act_rotate.setCheckable(True)
        self.act_rotate.setChecked(True)
        self.act_rotate.triggered.connect(self.OnToggleRotate)
        toolbar.addAction(self.act_rotate)

        self.act_train = QAction("Train", self)
        self.act_train.setToolTip("Run Hebbian learning — strengthen frequently used edges")
        self.act_train.triggered.connect(self.OnTrain)
        toolbar.addAction(self.act_train)

        self.act_reset = QAction("Reset", self)
        self.act_reset.setToolTip("Reset all activations to zero")
        self.act_reset.triggered.connect(self.OnReset)
        toolbar.addAction(self.act_reset)

        self.act_reload = QAction("Reload Weights", self)
        self.act_reload.setToolTip("Reload edge weights from MySQL")
        self.act_reload.triggered.connect(self.OnReloadWeights)
        toolbar.addAction(self.act_reload)

        toolbar.addSeparator()

        self.act_wave = QAction("Wave Mode", self)
        self.act_wave.setCheckable(True)
        self.act_wave.setToolTip("Toggle wave dynamics — pulses travel along edges over time")
        self.act_wave.triggered.connect(self.OnToggleWave)
        toolbar.addAction(self.act_wave)

        self.act_backprop = QAction("Backprop", self)
        self.act_backprop.setToolTip("Find best path from selected node to a target (right-click node = set target)")
        self.act_backprop.triggered.connect(self.OnBackprop)
        toolbar.addAction(self.act_backprop)

        self.act_fact = QAction("Fact Graph", self)
        self.act_fact.setToolTip("Activate fact graph — facts feed activation into semantic nodes")
        self.act_fact.triggered.connect(self.OnFactGraph)
        toolbar.addAction(self.act_fact)

        self.act_grow = QAction("Grow", self)
        self.act_grow.setToolTip("Growth simulation — holes slowly grow new edges (learning new reasoning)")
        self.act_grow.triggered.connect(self.OnGrow)
        toolbar.addAction(self.act_grow)

        self.act_save = QAction("Save Brain", self)
        self.act_save.setToolTip("Save trained weights to MySQL")
        self.act_save.triggered.connect(self.OnSaveBrain)
        toolbar.addAction(self.act_save)

        self.act_load = QAction("Load Brain", self)
        self.act_load.setToolTip("Load trained weights from MySQL")
        self.act_load.triggered.connect(self.OnLoadBrain)
        toolbar.addAction(self.act_load)

        toolbar.addSeparator()

        self.act_layers = QAction("Load Layers", self)
        self.act_layers.setToolTip("Load BCLIR + BCL + Graph layers from MySQL — wire all three into the neural graph")
        self.act_layers.triggered.connect(self.OnLoadLayers)
        toolbar.addAction(self.act_layers)

        self.act_layer_info = QAction("?", self)
        self.act_layer_info.setToolTip("Show layer statistics")
        self.act_layer_info.triggered.connect(self.OnLayerInfo)
        toolbar.addAction(self.act_layer_info)

        self.act_codebase = QAction("Load Codebase", self)
        self.act_codebase.setToolTip("Scan local codebase: files, classes, methods, VBStyle violations — wire into graph")
        self.act_codebase.triggered.connect(self.OnLoadCodebase)
        toolbar.addAction(self.act_codebase)

        self.act_cunits = QAction("Load C Units", self)
        self.act_cunits.setToolTip("Load 46 C BCL units from bcl_tool binary — wire as graph nodes with category clusters")
        self.act_cunits.triggered.connect(self.OnLoadCUnits)
        toolbar.addAction(self.act_cunits)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("Spread:"))
        self.spread_slider = QSlider(Qt.Orientation.Horizontal)
        self.spread_slider.setRange(50, 99)
        self.spread_slider.setValue(92)
        self.spread_slider.setFixedWidth(80)
        self.spread_slider.setStyleSheet(
            "QSlider { background: #14161e; border: 1px solid #20222e; border-radius: 4px; }"
            "QSlider::handle:horizontal { background: #4060a0; width: 12px; margin: -1px; border-radius: 4px; }"
        )
        self.spread_slider.valueChanged.connect(self.OnSpreadChange)
        toolbar.addWidget(self.spread_slider)

        spacer = QWidget()
        spacer.setFixedWidth(20)
        toolbar.addWidget(spacer)

        self.status_label = QLabel("Ready — click a node to activate")
        self.status_label.setStyleSheet("color: #506070; font-size: 10px; font-family: Menlo; padding-right: 10px;")
        toolbar.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        self.graph = NeuralGraph3D()
        splitter.addWidget(self.graph)

        self.info = InfoPanel()
        splitter.addWidget(self.info)
        splitter.setSizes([900, 300])
        splitter.setStyleSheet(
            "QSplitter::handle { background: #1a1c28; width: 2px; }"
        )

    def OnNodeActivated(self, node):
        nid = node["id"]
        label = node["label"]
        dim = node.get("dimension", "?")
        acts = self.graph.state["activations"]
        active_neighbors = []
        for e in self.state["edges"]:
            if e["source"] == nid:
                w = self.state["weights"].get("%s|%s" % (e["source"], e["target"]),
                    self.state["weights"].get("%s|%s" % (e["target"], e["source"]), 0))
                if acts.get(e["target"], 0) > 0.05:
                    target_node = None
                    for n in self.state["nodes"]:
                        if n["id"] == e["target"]:
                            target_node = n
                            break
                    if target_node:
                        active_neighbors.append((target_node["label"], w))
            elif e["target"] == nid:
                w = self.state["weights"].get("%s|%s" % (e["source"], e["target"]),
                    self.state["weights"].get("%s|%s" % (e["target"], e["source"]), 0))
                if acts.get(e["source"], 0) > 0.05:
                    src_node = None
                    for n in self.state["nodes"]:
                        if n["id"] == e["source"]:
                            src_node = n
                            break
                    if src_node:
                        active_neighbors.append((src_node["label"], w))

        self.info.Log("FIRE: %s [%s]" % (label, dim))
        if active_neighbors:
            for nl, w in sorted(active_neighbors, key=lambda x: x[1], reverse=True)[:5]:
                self.info.Log("  -> %s (w=%.2f)" % (nl, w))
        else:
            self.info.Log("  (spreading to neighbors...)")

        self.state["activation_log"].append(label)
        self.status_label.setText("Activated: %s | Total fires: %d" % (label, len(self.state["activation_log"])))

    def OnToggleRotate(self):
        self.graph.state["auto_rotate"] = self.act_rotate.isChecked()

    def OnTrain(self):
        """Hebbian learning — edges between co-activated nodes strengthen."""
        acts = self.graph.state["activations"]
        weights = self.state["weights"]
        strengthened = 0
        for e in self.state["edges"]:
            src = e["source"]
            tgt = e["target"]
            a_src = acts.get(src, 0)
            a_tgt = acts.get(tgt, 0)
            if a_src > 0.1 and a_tgt > 0.1:
                key = "%s|%s" % (src, tgt)
                rev_key = "%s|%s" % (tgt, src)
                old_w = weights.get(key, weights.get(rev_key, 0.05))
                new_w = min(1.0, old_w + 0.05 * a_src * a_tgt)
                weights[key] = new_w
                strengthened += 1
        self.state["train_count"] += 1
        self.info.Log("")
        self.info.Log("TRAIN: %d edges strengthened (cycle %d)" % (strengthened, self.state["train_count"]))
        self.info.Log("")
        self.status_label.setText("Trained: %d edges strengthened | Cycles: %d" % (
            strengthened, self.state["train_count"]))

    def OnReset(self):
        for nid in self.graph.state["activations"]:
            self.graph.state["activations"][nid] = 0.0
        self.graph.state["selected"] = None
        self.graph.update()
        self.info.Log("")
        self.info.Log("RESET: all activations cleared")
        self.info.Log("")

    def OnReloadWeights(self):
        self.LoadWeightsFromDb()
        self.graph.state["weights"] = self.state["weights"]
        self.info.Log("")
        self.info.Log("RELOAD: %d weighted edges from MySQL" % len(self.state["weights"]))
        self.info.Log("")

    def OnSpreadChange(self, val):
        self.graph.state["spread_decay"] = val / 100.0

    def OnToggleWave(self):
        self.graph.state["wave_mode"] = self.act_wave.isChecked()
        mode = "ON" if self.act_wave.isChecked() else "OFF"
        self.info.Log("")
        self.info.Log("WAVE MODE: %s" % mode)
        if self.act_wave.isChecked():
            self.info.Log("  Pulses travel along edges over time")
            self.info.Log("  Click a node to emit waves")
        self.info.Log("")
        self.status_label.setText("Wave mode: %s" % mode)

    def OnBackpropTarget(self, node):
        self.info.Log("")
        self.info.Log("TARGET SET: %s [%s]" % (node["label"], node.get("dimension", "?")))
        self.info.Log("  Now click Backprop to find best path")
        self.info.Log("")
        self.status_label.setText("Target: %s — click Backprop" % node["label"])

    def OnBackprop(self):
        source_id = self.graph.state.get("selected")
        target_id = self.graph.state.get("backprop_target")
        if not source_id:
            self.info.Log("BACKPROP: No source — click a node first")
            return
        if not target_id:
            self.info.Log("BACKPROP: No target — right-click a node to set target")
            return
        if source_id == target_id:
            self.info.Log("BACKPROP: source == target")
            return

        adj = defaultdict(list)
        for e in self.state["edges"]:
            src = e["source"]
            tgt = e["target"]
            if e.get("is_hole"):
                continue
            w = self.state["weights"].get("%s|%s" % (src, tgt),
                self.state["weights"].get("%s|%s" % (tgt, src), 0.05))
            cost = 1.0 / (w + 0.01)
            adj[src].append((tgt, cost))
            adj[tgt].append((src, cost))

        dist = {source_id: 0}
        prev = {}
        pq = [(0, source_id)]
        visited = set()
        while pq:
            d, nid = heapq.heappop(pq)
            if nid in visited:
                continue
            visited.add(nid)
            if nid == target_id:
                break
            for neighbor, cost in adj[nid]:
                nd = d + cost
                if neighbor not in dist or nd < dist[neighbor]:
                    dist[neighbor] = nd
                    prev[neighbor] = nid
                    heapq.heappush(pq, (nd, neighbor))

        if target_id not in dist:
            self.info.Log("BACKPROP: No path found from %s to %s" % (source_id, target_id))
            return

        path = [target_id]
        cur = target_id
        while cur in prev:
            cur = prev[cur]
            path.append(cur)
        path.reverse()

        path_edges = []
        for i in range(len(path) - 1):
            path_edges.append((path[i], path[i + 1]))

        self.graph.SetPathHighlight(path_edges)
        for nid in path:
            self.graph.state["activations"][nid] = max(self.graph.state["activations"].get(nid, 0), 0.6)

        src_label = self._NodeIdToLabel(source_id)
        tgt_label = self._NodeIdToLabel(target_id)
        path_labels = [self._NodeIdToLabel(n) for n in path]

        self.info.Log("")
        self.info.Log("BACKPROP: %s -> %s" % (src_label, tgt_label))
        self.info.Log("  Path (%d hops):" % (len(path) - 1))
        self.info.Log("  " + " -> ".join(path_labels))
        self.info.Log("  Total cost: %.2f (lower = stronger path)" % dist[target_id])
        self.info.Log("")
        self.status_label.setText("Backprop: %d-hop path found (cost %.2f)" % (
            len(path) - 1, dist[target_id]))

    def _NodeIdToLabel(self, nid):
        for n in self.state["nodes"]:
            if n["id"] == nid:
                return n["label"]
        return nid

    def OnFactGraph(self):
        items = []
        for i, fact in enumerate(FACT_GRAPH):
            items.append("%d. %s --%s--> %s (%d questions)" % (
                i, fact["subject"], fact["relation"], fact["object"], len(fact["questions"])
            ))
        choice, ok = QInputDialog.getItem(
            self, "Fact Graph", "Select a fact to activate:", items, 0, False
        )
        if not ok or not choice:
            return
        idx = int(choice.split(".")[0])
        fact = FACT_GRAPH[idx]
        node_ids = []
        for nid, qtext in fact["questions"]:
            for n in self.state["nodes"]:
                if n["id"] == nid:
                    node_ids.append(nid)
                    break

        self.graph.ActivateFromFact(idx, node_ids)

        self.info.Log("")
        self.info.Log("FACT: %s --%s--> %s" % (fact["subject"], fact["relation"], fact["object"]))
        self.info.Log("  Context: %s" % fact.get("context", {}))
        self.info.Log("  Activating %d semantic nodes:" % len(node_ids))
        for nid, qtext in fact["questions"]:
            label = self._NodeIdToLabel(nid)
            self.info.Log("    %s -> \"%s\"" % (label, qtext))
        self.info.Log("")
        self.status_label.setText("Fact activated: %s --%s--> %s" % (
            fact["subject"], fact["relation"], fact["object"]))

    def OnGrow(self):
        holes = self.state["holes"]
        if not holes:
            self.info.Log("GROW: No holes to grow")
            return
        grown = 0
        weights = self.state["weights"]
        for hole in holes[:10]:
            src = hole["source"]
            tgt = hole["target"]
            key = "%s|%s" % (src, tgt)
            old_w = weights.get(key, 0.0)
            new_w = old_w + 0.1
            weights[key] = min(0.5, new_w)
            hole["is_hole"] = False
            grown += 1

        self.state["holes"] = [h for h in self.state["holes"] if h.get("is_hole", True)]
        self.graph.state["weights"] = weights
        self.graph.state["holes"] = self.state["holes"]
        self.graph.update()

        self.info.Log("")
        self.info.Log("GROW: %d dormant synapses activated" % grown)
        self.info.Log("  New reasoning pathways emerging")
        self.info.Log("  Remaining holes: %d" % len(self.state["holes"]))
        self.info.Log("")
        self.status_label.setText("Grown: %d new edges | Holes remaining: %d" % (
            grown, len(self.state["holes"])))

    def OnSaveBrain(self):
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host="localhost", user="root", password="",
                database="vb_shared", unix_socket="/tmp/mysql.sock"
            )
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS neural_brain_state")
            cur.execute("""CREATE TABLE neural_brain_state (
                edge_key VARCHAR(200) PRIMARY KEY,
                weight FLOAT NOT NULL,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            weights = self.state["weights"]
            for key, w in weights.items():
                cur.execute("INSERT INTO neural_brain_state (edge_key, weight) VALUES (%s, %s)",
                            (key, w))
            conn.commit()
            cur.close()
            conn.close()
            self.info.Log("")
            self.info.Log("SAVE: %d edge weights saved to MySQL (vb_shared.neural_brain_state)" % len(weights))
            self.info.Log("")
            self.status_label.setText("Brain saved: %d weights" % len(weights))
        except Exception as ex:
            self.info.Log("SAVE ERROR: %s" % str(ex))
            self.status_label.setText("Save failed: %s" % str(ex)[:50])

    def OnLoadBrain(self):
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host="localhost", user="root", password="",
                database="vb_shared", unix_socket="/tmp/mysql.sock"
            )
            cur = conn.cursor()
            cur.execute("SELECT edge_key, weight FROM neural_brain_state")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            if not rows:
                self.info.Log("LOAD: No saved brain state found")
                return
            weights = {}
            for key, w in rows:
                weights[key] = float(w)
            self.state["weights"] = weights
            self.graph.state["weights"] = weights
            self.graph.update()
            self.info.Log("")
            self.info.Log("LOAD: %d edge weights loaded from MySQL" % len(weights))
            self.info.Log("")
            self.status_label.setText("Brain loaded: %d weights" % len(weights))
        except Exception as ex:
            self.info.Log("LOAD ERROR: %s" % str(ex))
            self.status_label.setText("Load failed: %s" % str(ex)[:50])

    def OnLoadLayers(self):
        """Load BCLIR + BCL + Graph layers from MySQL and wire into the neural graph."""
        self.info.Log("")
        self.info.Log("LOADING THREE-LAYER ARCHITECTURE...")
        self.info.Log("")
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host="localhost", user="root", password="",
                database="vb_shared", unix_socket="/tmp/mysql.sock"
            )
            cur = conn.cursor()

            existing_nodes = list(self.state["nodes"])
            existing_edges = list(self.state["edges"])
            existing_ids = set(n["id"] for n in existing_nodes)
            new_nodes = []
            new_edges = []
            weights = self.state["weights"]

            # Layer 1: BCLIR — top classes by method count
            cur.execute("""
                SELECT c.id, c.class_name, LEFT(c.description, 80)
                FROM vb_code_test.vb_classes c
                ORDER BY c.id LIMIT 60
            """)
            class_ids = {}
            for cid, cname, cdesc in cur.fetchall():
                nid = "bclir_class:%s" % cname
                if nid not in existing_ids:
                    new_nodes.append({
                        "id": nid, "label": cname[:15],
                        "type": "class", "dimension": "bclir_class",
                        "layer": "bclir_class",
                        "desc": cdesc or "",
                    })
                    class_ids[cname] = cid
                    existing_ids.add(nid)

            # Layer 1b: BCLIR — methods for top classes
            cur.execute("""
                SELECT m.method_name, c.class_name, m.params
                FROM vb_code_test.vb_methods m
                JOIN vb_code_test.vb_classes c ON m.class_id = c.id
                WHERE c.class_name IN (%s)
                LIMIT 150
            """ % ",".join("'%s'" % c for c in class_ids.keys()))
            method_class_map = {}
            for mname, cname, mparams in cur.fetchall():
                if "__" in mname:
                    continue
                nid = "bclir_method:%s.%s" % (cname, mname)
                if nid not in existing_ids:
                    new_nodes.append({
                        "id": nid, "label": mname[:12],
                        "type": "method", "dimension": "bclir_method",
                        "layer": "bclir_method",
                        "class": cname,
                    })
                    existing_ids.add(nid)
                    method_class_map[nid] = "bclir_class:%s" % cname

            # BCLIR edges: class -> method (contains)
            for m_nid, c_nid in method_class_map.items():
                if c_nid in existing_ids:
                    new_edges.append({
                        "source": c_nid, "target": m_nid,
                        "dimension": "bclir", "is_hole": False,
                    })
                    weights["%s|%s" % (c_nid, m_nid)] = 0.8

            # Layer 2: BCL — rules
            cur.execute("""
                SELECT rule, LEFT(description, 80) FROM vb_shared.rules LIMIT 30
            """)
            rule_nodes = []
            for rule_name, rule_desc in cur.fetchall():
                safe_name = rule_name.replace(" ", "_")[:20]
                nid = "bcl_rule:%s" % safe_name
                if nid not in existing_ids:
                    new_nodes.append({
                        "id": nid, "label": safe_name[:15],
                        "type": "rule", "dimension": "bcl_rule",
                        "layer": "bcl_rule",
                        "desc": rule_desc or "",
                    })
                    existing_ids.add(nid)
                    rule_nodes.append(nid)

            # BCL edges: rules -> classes they govern (connect to first few classes)
            class_nids = ["bclir_class:%s" % c for c in class_ids.keys()][:10]
            for r_nid in rule_nodes:
                for c_nid in class_nids[:3]:
                    new_edges.append({
                        "source": r_nid, "target": c_nid,
                        "dimension": "bcl", "is_hole": False,
                    })
                    weights["%s|%s" % (r_nid, c_nid)] = 0.3

            # Layer 3: Graph — co-occurrence edges
            cur.execute("""
                SELECT entity_a, entity_b, relationship_type, weight
                FROM vb_shared.code_co_occurrence
                WHERE entity_a != entity_b
                ORDER BY weight DESC LIMIT 200
            """)
            graph_node_names = set()
            for ea, eb, rel, w in cur.fetchall():
                na_id = "graph:%s" % ea
                nb_id = "graph:%s" % eb
                if na_id not in existing_ids:
                    new_nodes.append({
                        "id": na_id, "label": ea[:12],
                        "type": "graph_node", "dimension": "graph",
                        "layer": "graph",
                    })
                    existing_ids.add(na_id)
                    graph_node_names.add(ea)
                if nb_id not in existing_ids:
                    new_nodes.append({
                        "id": nb_id, "label": eb[:12],
                        "type": "graph_node", "dimension": "graph",
                        "layer": "graph",
                    })
                    existing_ids.add(nb_id)
                    graph_node_names.add(eb)
                new_edges.append({
                    "source": na_id, "target": nb_id,
                    "dimension": "graph", "is_hole": False,
                })
                weights["%s|%s" % (na_id, nb_id)] = float(w) * 0.3

            # Cross-layer edges: inquiry atoms -> BCLIR classes
            # Map interrogatives to classes by semantic keyword matching
            INQUIRY_KEYWORDS = {
                "WHAT": ["class", "object", "thing", "system", "file", "graph", "node", "edge", "law", "question"],
                "WHO": ["user", "person", "agent", "authority", "auth", "controller"],
                "WHERE": ["path", "location", "file", "database", "store", "memory", "disk"],
                "WHEN": ["time", "runtime", "schedule", "cron", "event", "log", "history"],
                "WHY": ["error", "exception", "cause", "reason", "problem", "fail", "crash"],
                "HOW": ["method", "process", "build", "create", "generate", "parse", "search", "run"],
                "WHICH": ["rule", "law", "governance", "standard", "style", "validate"],
                "WHOM": ["user", "person", "agent"],
                "WHOSE": ["authority", "auth", "owner", "domain"],
            }
            inquiry_class_links = 0
            for atom, keywords in INQUIRY_KEYWORDS.items():
                atom_nid = "interrogative:%s" % atom
                if atom_nid not in existing_ids:
                    continue
                for node in new_nodes:
                    if node.get("layer") == "bclir_class":
                        desc = (node.get("desc", "") or "").lower()
                        label = (node.get("label", "") or "").lower()
                        text = desc + " " + label
                        for kw in keywords:
                            if kw in text:
                                new_edges.append({
                                    "source": atom_nid, "target": node["id"],
                                    "dimension": "cross_layer", "is_hole": False,
                                })
                                weights["%s|%s" % (atom_nid, node["id"])] = 0.25
                                inquiry_class_links += 1
                                break

            # Cross-layer edges: BCLIR classes -> graph nodes (by name match)
            cross_graph_links = 0
            for node in new_nodes:
                if node.get("layer") == "bclir_class":
                    label = node.get("label", "")
                    for gname in graph_node_names:
                        if label.lower() in gname.lower() or gname.lower() in label.lower():
                            g_nid = "graph:%s" % gname
                            if g_nid in existing_ids:
                                new_edges.append({
                                    "source": node["id"], "target": g_nid,
                                    "dimension": "cross_layer", "is_hole": False,
                                })
                                weights["%s|%s" % (node["id"], g_nid)] = 0.2
                                cross_graph_links += 1
                                break

            cur.close()
            conn.close()

            all_nodes = existing_nodes + new_nodes
            all_edges = existing_edges + new_edges
            all_holes = [e for e in all_edges if e.get("is_hole")]

            self.state["nodes"] = all_nodes
            self.state["edges"] = all_edges
            self.state["holes"] = all_holes
            self.state["weights"] = weights

            for n in all_nodes:
                if n["id"] not in self.graph.state["activations"]:
                    self.graph.state["activations"][n["id"]] = 0.0

            self.graph.SetGraph(all_nodes, all_edges, all_holes, weights)

            # Count layers
            layer_counts = Counter(n.get("layer", "inquiry") for n in all_nodes)
            edge_dims = Counter(e.get("dimension", "unknown") for e in all_edges)

            self.info.Log("=" * 40)
            self.info.Log("THREE-LAYER ARCHITECTURE LOADED")
            self.info.Log("=" * 40)
            self.info.Log("")
            self.info.Log("LAYER 1 — BCLIR (Structure):")
            self.info.Log("  %d classes" % layer_counts.get("bclir_class", 0))
            self.info.Log("  %d methods" % layer_counts.get("bclir_method", 0))
            self.info.Log("  %d contains edges" % edge_dims.get("bclir", 0))
            self.info.Log("")
            self.info.Log("LAYER 2 — BCL (Semantics):")
            self.info.Log("  %d rules" % layer_counts.get("bcl_rule", 0))
            self.info.Log("  %d governs edges" % edge_dims.get("bcl", 0))
            self.info.Log("")
            self.info.Log("LAYER 3 — Graph (Topology):")
            self.info.Log("  %d graph nodes" % layer_counts.get("graph", 0))
            self.info.Log("  %d co-occurrence edges" % edge_dims.get("graph", 0))
            self.info.Log("")
            self.info.Log("CROSS-LAYER WIRING:")
            self.info.Log("  %d inquiry->class links" % inquiry_class_links)
            self.info.Log("  %d class->graph links" % cross_graph_links)
            self.info.Log("  %d cross-layer edges" % edge_dims.get("cross_layer", 0))
            self.info.Log("")
            self.info.Log("TOTAL: %d nodes | %d edges" % (len(all_nodes), len(all_edges)))
            self.info.Log("")
            self.info.Log("Click any node — activation spreads")
            self.info.Log("across ALL THREE LAYERS.")
            self.info.Log("")

            self.status_label.setText("3 layers loaded: %d nodes | %d edges | %d cross-layer" % (
                len(all_nodes), len(all_edges), edge_dims.get("cross_layer", 0)
            ))

        except Exception as ex:
            self.info.Log("LOAD LAYERS ERROR: %s" % str(ex))
            self.status_label.setText("Load layers failed: %s" % str(ex)[:50])

    def OnLoadCodebase(self):
        """Scan local codebase for files/classes/methods/violations and wire into the neural graph."""
        self.info.Log("")
        self.info.Log("SCANNING LOCAL CODEBASE...")
        self.info.Log("")

        try:
            import os
            import ast
            import re as _re

            GHOST_RE = _re.compile(r'\[@GHOST\]', _re.IGNORECASE)
            VBSTYLE_RE = _re.compile(r'\[@VBSTYLE\]', _re.IGNORECASE)

            SKIP_DIRS = {".git", "__pycache__", "node_modules", ".codeium",
                         "treasure_trove_backup", ".codex", ".venv", "venv"}

            root_path = "/Users/wws/Qdrant_mysql_mlx_vector_engine"

            existing_nodes = list(self.state["nodes"])
            existing_edges = list(self.state["edges"])
            existing_ids = set(n["id"] for n in existing_nodes)
            new_nodes = []
            new_edges = []
            weights = self.state["weights"]

            file_count = 0
            class_count = 0
            method_count = 0
            violation_count = 0
            vbstyle_compliant = 0
            no_header_count = 0

            # Limit to keep graph manageable
            MAX_FILES = 300
            MAX_CLASSES = 400
            MAX_METHODS = 800

            file_nodes = []
            class_nodes = []
            method_nodes = []
            violation_nodes = []

            for dirpath, dirnames, filenames in os.walk(root_path):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for fn in sorted(filenames):
                    if not fn.endswith(".py"):
                        continue
                    if file_count >= MAX_FILES:
                        break

                    fp = os.path.join(dirpath, fn)
                    rel_path = os.path.relpath(fp, root_path)

                    try:
                        with open(fp, "r", errors="ignore") as f:
                            content = f.read()
                    except Exception:
                        continue

                    file_count += 1

                    has_ghost = bool(GHOST_RE.search(content[:500]))
                    has_vbs = bool(VBSTYLE_RE.search(content[:500]))

                    if not has_ghost and not has_vbs:
                        no_header_count += 1

                    # File node
                    file_nid = "cb_file:%s" % rel_path
                    if file_nid not in existing_ids:
                        file_violations = 0
                        # Quick violation check
                        for line in content.split("\n"):
                            stripped = line.lstrip()
                            if stripped.startswith("print(") and not stripped.startswith("#"):
                                file_violations += 1
                            if _re.match(r'\s+self\._', line) and not stripped.startswith("#"):
                                file_violations += 1

                        violation_count += file_violations

                        new_nodes.append({
                            "id": file_nid,
                            "label": fn[:18],
                            "type": "file",
                            "dimension": "cb_file",
                            "layer": "cb_file",
                            "path": rel_path,
                            "has_ghost": has_ghost,
                            "has_vbs": has_vbs,
                            "violations": file_violations,
                        })
                        existing_ids.add(file_nid)
                        file_nodes.append(file_nid)

                        # Violation node for files with many violations
                        if file_violations > 10:
                            viol_nid = "cb_violation:%s" % rel_path
                            if viol_nid not in existing_ids:
                                new_nodes.append({
                                    "id": viol_nid,
                                    "label": "VIOLATIONS:%d" % file_violations,
                                    "type": "violation",
                                    "dimension": "cb_violation",
                                    "layer": "cb_violation",
                                    "file": rel_path,
                                    "count": file_violations,
                                })
                                existing_ids.add(viol_nid)
                                violation_nodes.append(viol_nid)

                                # Edge: violation -> file
                                new_edges.append({
                                    "source": viol_nid,
                                    "target": file_nid,
                                    "dimension": "cb_violation",
                                    "is_hole": False,
                                })
                                weights["%s|%s" % (viol_nid, file_nid)] = 0.9

                    # Parse AST for classes
                    try:
                        tree = ast.parse(content, filename=fp)
                    except SyntaxError:
                        continue

                    for node in ast.walk(tree):
                        if not isinstance(node, ast.ClassDef):
                            continue
                        if class_count >= MAX_CLASSES:
                            break

                        class_count += 1
                        cname = node.name
                        method_names = [n.name for n in node.body
                                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                        has_run = "Run" in method_names
                        is_vbstyle = has_ghost and has_vbs and has_run

                        if is_vbstyle:
                            vbstyle_compliant += 1

                        class_nid = "cb_class:%s.%s" % (rel_path, cname)
                        if class_nid not in existing_ids:
                            new_nodes.append({
                                "id": class_nid,
                                "label": cname[:15],
                                "type": "class",
                                "dimension": "cb_class",
                                "layer": "cb_class",
                                "file": rel_path,
                                "has_run": has_run,
                                "is_vbstyle": is_vbstyle,
                                "method_count": len(method_names),
                            })
                            existing_ids.add(class_nid)
                            class_nodes.append(class_nid)

                            # Edge: file -> class (defines)
                            if file_nid in existing_ids:
                                new_edges.append({
                                    "source": file_nid,
                                    "target": class_nid,
                                    "dimension": "cb_defines",
                                    "is_hole": False,
                                })
                                weights["%s|%s" % (file_nid, class_nid)] = 0.8

                        # Method nodes (limited)
                        for mname in method_names:
                            if "__" in mname:
                                continue
                            if method_count >= MAX_METHODS:
                                break
                            method_count += 1

                            meth_nid = "cb_method:%s.%s.%s" % (rel_path, cname, mname)
                            if meth_nid not in existing_ids:
                                new_nodes.append({
                                    "id": meth_nid,
                                    "label": mname[:12],
                                    "type": "method",
                                    "dimension": "cb_method",
                                    "layer": "cb_method",
                                    "class": cname,
                                    "file": rel_path,
                                    "is_run": mname == "Run",
                                })
                                existing_ids.add(meth_nid)
                                method_nodes.append(meth_nid)

                                # Edge: class -> method (contains)
                                if class_nid in existing_ids:
                                    new_edges.append({
                                        "source": class_nid,
                                        "target": meth_nid,
                                        "dimension": "cb_contains",
                                        "is_hole": False,
                                    })
                                    w = 0.9 if mname == "Run" else 0.5
                                    weights["%s|%s" % (class_nid, meth_nid)] = w

                if file_count >= MAX_FILES:
                    break

            # Cross-layer edges: inquiry atoms -> codebase files
            INQUIRY_CODEBASE = {
                "WHAT": ["file", "class", "graph", "node", "edge", "scanner", "parser"],
                "WHO": ["agent", "authority", "auth", "controller", "worker"],
                "WHERE": ["path", "file", "db", "store", "memory", "disk"],
                "WHEN": ["time", "runtime", "event", "log", "history"],
                "WHY": ["error", "exception", "cause", "problem", "fail", "violation"],
                "HOW": ["method", "process", "build", "create", "generate", "parse", "scan", "run"],
                "WHICH": ["rule", "style", "validate", "violation", "check"],
                "WHOSE": ["authority", "auth", "owner", "domain"],
            }

            inquiry_links = 0
            for atom, keywords in INQUIRY_CODEBASE.items():
                atom_nid = "interrogative:%s" % atom
                if atom_nid not in existing_ids:
                    continue
                for fnid in file_nodes[:80]:
                    fn_node = next((n for n in new_nodes if n["id"] == fnid), None)
                    if not fn_node:
                        continue
                    text = (fn_node.get("path", "") + " " + fn_node.get("label", "")).lower()
                    for kw in keywords:
                        if kw in text:
                            new_edges.append({
                                "source": atom_nid,
                                "target": fnid,
                                "dimension": "cross_layer",
                                "is_hole": False,
                            })
                            weights["%s|%s" % (atom_nid, fnid)] = 0.2
                            inquiry_links += 1
                            break

            # Cross-layer: BCLIR classes -> codebase classes (by name match)
            bclir_links = 0
            bclir_class_ids = [n["id"] for n in existing_nodes if n.get("layer") == "bclir_class"]
            for cnid in class_nodes[:100]:
                cn_node = next((n for n in new_nodes if n["id"] == cnid), None)
                if not cn_node:
                    continue
                cname_lower = cn_node.get("label", "").lower()
                for bid in bclir_class_ids[:30]:
                    b_node = next((n for n in existing_nodes if n["id"] == bid), None)
                    if not b_node:
                        continue
                    bname_lower = b_node.get("label", "").lower()
                    if bname_lower and bname_lower in cname_lower:
                        new_edges.append({
                            "source": bid,
                            "target": cnid,
                            "dimension": "cross_layer",
                            "is_hole": False,
                        })
                        weights["%s|%s" % (bid, cnid)] = 0.3
                        bclir_links += 1
                        break

            all_nodes = existing_nodes + new_nodes
            all_edges = existing_edges + new_edges
            all_holes = [e for e in all_edges if e.get("is_hole")]

            self.state["nodes"] = all_nodes
            self.state["edges"] = all_edges
            self.state["holes"] = all_holes
            self.state["weights"] = weights

            for n in all_nodes:
                if n["id"] not in self.graph.state["activations"]:
                    self.graph.state["activations"][n["id"]] = 0.0

            self.graph.SetGraph(all_nodes, all_edges, all_holes, weights)

            layer_counts = Counter(n.get("layer", "inquiry") for n in all_nodes)
            edge_dims = Counter(e.get("dimension", "unknown") for e in all_edges)

            self.info.Log("=" * 40)
            self.info.Log("CODEBASE SCAN LOADED")
            self.info.Log("=" * 40)
            self.info.Log("")
            self.info.Log("LAYER 4 — CODEBASE (Local Files):")
            self.info.Log("  Files scanned:       %d" % file_count)
            self.info.Log("  Files with GHOST:    %d" % (file_count - no_header_count))
            self.info.Log("  Files NO header:     %d" % no_header_count)
            self.info.Log("  File nodes:          %d" % layer_counts.get("cb_file", 0))
            self.info.Log("  Violation nodes:     %d" % layer_counts.get("cb_violation", 0))
            self.info.Log("")
            self.info.Log("  Classes found:       %d" % class_count)
            self.info.Log("  VBStyle compliant:   %d" % vbstyle_compliant)
            self.info.Log("  Without Run():       %d" % (class_count - vbstyle_compliant))
            self.info.Log("  Class nodes:         %d" % layer_counts.get("cb_class", 0))
            self.info.Log("")
            self.info.Log("  Methods found:       %d" % method_count)
            self.info.Log("  Method nodes:        %d" % layer_counts.get("cb_method", 0))
            self.info.Log("  Total violations:    %d" % violation_count)
            self.info.Log("")
            self.info.Log("EDGES:")
            self.info.Log("  file->class (defines):   %d" % edge_dims.get("cb_defines", 0))
            self.info.Log("  class->method (contains): %d" % edge_dims.get("cb_contains", 0))
            self.info.Log("  violation->file:          %d" % edge_dims.get("cb_violation", 0))
            self.info.Log("  inquiry->file (cross):    %d" % inquiry_links)
            self.info.Log("  bclir->cb_class (cross):  %d" % bclir_links)
            self.info.Log("")
            self.info.Log("TOTAL: %d nodes | %d edges" % (len(all_nodes), len(all_edges)))
            self.info.Log("")
            self.info.Log("Click any node — activation spreads")
            self.info.Log("across ALL layers including codebase.")
            self.info.Log("")

            self.status_label.setText("Codebase loaded: %d nodes | %d edges | %d files | %d classes" % (
                len(all_nodes), len(all_edges), file_count, class_count
            ))

        except Exception as ex:
            self.info.Log("CODEBASE SCAN ERROR: %s" % str(ex))
            self.status_label.setText("Codebase scan failed: %s" % str(ex)[:50])

    def OnLoadCUnits(self):
        """Load C BCL units from bcl_tool binary and wire into the neural graph."""
        self.info.Log("")
        self.info.Log("LOADING C BCL UNITS...")
        self.info.Log("")

        try:
            import subprocess
            import os

            bcl_tool = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bcl_units/bcl_tool"
            if not os.path.exists(bcl_tool):
                bcl_tool = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/bcl_tool"

            if not os.path.exists(bcl_tool):
                self.info.Log("ERROR: bcl_tool binary not found")
                self.status_label.setText("C units: binary not found")
                return

            # Run: bcl_tool list
            proc = subprocess.run([bcl_tool, "list"], capture_output=True, text=True, timeout=10)
            output = proc.stdout.strip()

            # Parse BCL output: [@OK]{[@COUNT]{N}[@UNIT]{[@NAME]{...}[@CATEGORY]{...}[@HELP]{...}[@STATUS]{...}}...}
            units = []
            import re as _re
            unit_pattern = _re.compile(r'\[@NAME\]\{([^}]+)\}\[@CATEGORY\]\{([^}]+)\}\[@HELP\]\{([^}]+)\}\[@STATUS\]\{([^}]+)\}')
            for m in unit_pattern.finditer(output):
                units.append({
                    "name": m.group(1),
                    "category": m.group(2),
                    "help": m.group(3),
                    "status": m.group(4),
                })

            if not units:
                self.info.Log("ERROR: no units parsed from bcl_tool output")
                self.status_label.setText("C units: parse failed")
                return

            existing_nodes = list(self.state["nodes"])
            existing_edges = list(self.state["edges"])
            existing_ids = set(n["id"] for n in existing_nodes)
            new_nodes = []
            new_edges = []
            weights = self.state["weights"]

            # Category colors
            CAT_COLORS = {
                "chat": "#E74C3C",
                "clean": "#F5A623",
                "build": "#3498DB",
                "graph": "#2ECC71",
                "config": "#9B59B6",
                "search": "#1ABC9C",
                "security": "#E74C3C",
                "graph_engine": "#2ECC71",
                "vbast": "#E67E22",
                "vsstyle": "#3498DB",
            }

            # Create category cluster nodes
            categories = {}
            for u in units:
                cat = u["category"]
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(u)

            cat_nodes = []
            for cat_name, cat_units in categories.items():
                cat_nid = "cunit_cat:%s" % cat_name
                if cat_nid not in existing_ids:
                    color = CAT_COLORS.get(cat_name, "#888888")
                    new_nodes.append({
                        "id": cat_nid,
                        "label": cat_name[:15],
                        "type": "cunit_category",
                        "dimension": "cunit_category",
                        "layer": "cunit_category",
                        "category": cat_name,
                        "unit_count": len(cat_units),
                        "color": color,
                    })
                    existing_ids.add(cat_nid)
                    cat_nodes.append(cat_nid)

            # Create unit nodes
            unit_nodes = []
            for u in units:
                unit_nid = "cunit:%s" % u["name"]
                if unit_nid not in existing_ids:
                    new_nodes.append({
                        "id": unit_nid,
                        "label": u["name"][:15],
                        "type": "cunit",
                        "dimension": "cunit",
                        "layer": "cunit",
                        "name": u["name"],
                        "category": u["category"],
                        "help": u["help"],
                        "status": u["status"],
                    })
                    existing_ids.add(unit_nid)
                    unit_nodes.append(unit_nid)

                    # Edge: category -> unit (contains)
                    cat_nid = "cunit_cat:%s" % u["category"]
                    if cat_nid in existing_ids:
                        new_edges.append({
                            "source": cat_nid,
                            "target": unit_nid,
                            "dimension": "cunit_contains",
                            "is_hole": False,
                        })
                        weights["%s|%s" % (cat_nid, unit_nid)] = 0.8

            # Cross-layer: inquiry atoms -> C unit categories
            INQUIRY_CUNIT = {
                "WHAT": ["file", "class", "graph", "node", "edge", "scanner", "parser", "index", "code"],
                "WHO": ["agent", "authority", "auth", "controller", "worker", "guard"],
                "WHERE": ["path", "file", "db", "store", "cache", "memory", "search"],
                "WHEN": ["time", "runtime", "event", "log", "trace", "schedule"],
                "WHY": ["error", "exception", "cause", "problem", "fail", "violation", "gap"],
                "HOW": ["method", "process", "build", "create", "generate", "parse", "scan", "run", "merge", "clean", "search", "index", "enforce", "check"],
                "WHICH": ["rule", "style", "validate", "violation", "check", "compliance", "schema"],
                "WHOSE": ["authority", "auth", "owner", "domain", "category"],
            }

            inquiry_links = 0
            for atom, keywords in INQUIRY_CUNIT.items():
                atom_nid = "interrogative:%s" % atom
                if atom_nid not in existing_ids:
                    continue
                for cat_nid in cat_nodes:
                    cat_node = next((n for n in new_nodes if n["id"] == cat_nid), None)
                    if not cat_node:
                        continue
                    cat_text = (cat_node.get("category", "") + " " + cat_node.get("label", "")).lower()
                    for kw in keywords:
                        if kw in cat_text:
                            new_edges.append({
                                "source": atom_nid,
                                "target": cat_nid,
                                "dimension": "cross_layer",
                                "is_hole": False,
                            })
                            weights["%s|%s" % (atom_nid, cat_nid)] = 0.25
                            inquiry_links += 1
                            break

            # Cross-layer: vsstyle category -> codebase classes
            vsstyle_cat_nid = "cunit_cat:vsstyle"
            cb_class_ids = [n["id"] for n in existing_nodes if n.get("layer") == "cb_class"]
            vsstyle_links = 0
            if vsstyle_cat_nid in existing_ids:
                for cnid in cb_class_ids[:50]:
                    new_edges.append({
                        "source": vsstyle_cat_nid,
                        "target": cnid,
                        "dimension": "cross_layer",
                        "is_hole": False,
                    })
                    weights["%s|%s" % (vsstyle_cat_nid, cnid)] = 0.15
                    vsstyle_links += 1

            # Cross-layer: config category -> BCLIR classes
            config_cat_nid = "cunit_cat:config"
            bclir_ids = [n["id"] for n in existing_nodes if n.get("layer") == "bclir_class"]
            config_links = 0
            if config_cat_nid in existing_ids:
                for bid in bclir_ids[:20]:
                    new_edges.append({
                        "source": config_cat_nid,
                        "target": bid,
                        "dimension": "cross_layer",
                        "is_hole": False,
                    })
                    weights["%s|%s" % (config_cat_nid, bid)] = 0.2
                    config_links += 1

            all_nodes = existing_nodes + new_nodes
            all_edges = existing_edges + new_edges
            all_holes = [e for e in all_edges if e.get("is_hole")]

            self.state["nodes"] = all_nodes
            self.state["edges"] = all_edges
            self.state["holes"] = all_holes
            self.state["weights"] = weights

            for n in all_nodes:
                if n["id"] not in self.graph.state["activations"]:
                    self.graph.state["activations"][n["id"]] = 0.0

            self.graph.SetGraph(all_nodes, all_edges, all_holes, weights)

            layer_counts = Counter(n.get("layer", "inquiry") for n in all_nodes)
            edge_dims = Counter(e.get("dimension", "unknown") for e in all_edges)

            self.info.Log("=" * 40)
            self.info.Log("C BCL UNITS LOADED")
            self.info.Log("=" * 40)
            self.info.Log("")
            self.info.Log("LAYER 5 — C BCL UNITS (bcl_tool binary):")
            self.info.Log("  Total units:         %d" % len(units))
            self.info.Log("  Categories:          %d" % len(categories))
            self.info.Log("  Category nodes:      %d" % layer_counts.get("cunit_category", 0))
            self.info.Log("  Unit nodes:          %d" % layer_counts.get("cunit", 0))
            self.info.Log("")
            self.info.Log("CATEGORIES:")
            for cat_name, cat_units in sorted(categories.items()):
                self.info.Log("  %-20s %d units" % (cat_name, len(cat_units)))
            self.info.Log("")
            self.info.Log("EDGES:")
            self.info.Log("  category->unit:      %d" % edge_dims.get("cunit_contains", 0))
            self.info.Log("  inquiry->category:   %d" % inquiry_links)
            self.info.Log("  vsstyle->cb_class:   %d" % vsstyle_links)
            self.info.Log("  config->bclir:       %d" % config_links)
            self.info.Log("  cross-layer total:   %d" % edge_dims.get("cross_layer", 0))
            self.info.Log("")
            self.info.Log("TOTAL: %d nodes | %d edges" % (len(all_nodes), len(all_edges)))
            self.info.Log("")
            self.info.Log("Click any node — activation spreads")
            self.info.Log("across ALL layers including C units.")
            self.info.Log("")

            self.status_label.setText("C units: %d units | %d categories | %d nodes total" % (
                len(units), len(categories), len(all_nodes)
            ))

        except Exception as ex:
            self.info.Log("C UNITS LOAD ERROR: %s" % str(ex))
            self.status_label.setText("C units failed: %s" % str(ex)[:50])

    def OnLayerInfo(self):
        nodes = self.state["nodes"]
        edges = self.state["edges"]
        layer_counts = Counter(n.get("layer", "inquiry") for n in nodes)
        edge_dims = Counter(e.get("dimension", "unknown") for e in edges)
        self.info.Log("")
        self.info.Log("LAYER INFO:")
        for layer, count in sorted(layer_counts.items()):
            name = LAYER_NAMES.get(layer, layer)
            self.info.Log("  %-15s %4d nodes" % (name, count))
        self.info.Log("")
        self.info.Log("EDGE TYPES:")
        for dim, count in sorted(edge_dims.items()):
            self.info.Log("  %-15s %4d edges" % (dim, count))
        self.info.Log("")
        self.status_label.setText("Layers: %d nodes | %d edges" % (len(nodes), len(edges)))


def Main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Menlo", 10))
    screen = app.primaryScreen().geometry()
    window = QuestionSpaceExplorerV2()
    window.resize(screen.width() - 20, screen.height() - 60)
    window.move(10, 25)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(Main())
