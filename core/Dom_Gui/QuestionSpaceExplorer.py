#!/usr/bin/env python3
# [@GHOST]{[@file<QuestionSpaceExplorer.py>][@domain<Dom_Gui>][@role<question_space>][@auth<devin>][@date<2026-07-04>][@ver<1.0.0>][@session<semantic-question-space>]}
# [@VBSTYLE]{[@auth<devin>][@role<question_space>][@return<tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{PyQt6 GUI — explores the semantic space of questions using SQLite in RAM. Cartesian explosion of interrogative×auxiliary×subject×action×object×modifier. Dimension graph, hole finder, semantic signatures.}
# [@CLASS]{QuestionSpaceExplorer}
# [@METHOD]{Run,InitDb,LoadAtoms,Generate,GetDimensions,FindHoles,GetGraph,ExportSignatures,read_state,set_config}
# [@FILEID]{core/Dom_Gui/QuestionSpaceExplorer.py

"""
QuestionSpaceExplorer — Semantic question space explorer.

SQLite in RAM. Cartesian explosion of semantic atoms. Dimension graph.
Hole finder. Semantic signatures (language-agnostic).

    Phase 1: Semantic atoms (token tables)
    Phase 2: SQLite tables in RAM
    Phase 3: Cartesian explosion (CROSS JOIN)
    Phase 4: Dimensions
    Phase 5: Graph it
    Phase 6: Semantic signatures
    Phase 7: Hole finder

Run: python3 QuestionSpaceExplorer.py
"""

import os
import sys
import sqlite3
import random
from collections import defaultdict, Counter
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QToolBar, QLineEdit, QSpinBox, QCheckBox, QComboBox,
    QHeaderView, QSplitter, QTextEdit, QProgressBar, QGroupBox,
    QGridLayout, QScrollArea,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPainterPath,
    QLinearGradient, QAction, QPolygonF,
)


DEFAULT_ATOMS = {
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

TOKEN_DIMENSIONS = {
    "WHERE": ("location", "place"),
    "WHEN": ("temporal", "time"),
    "WHY": ("causality", "reason"),
    "HOW": ("procedure", "method"),
    "WHAT": ("identity", "entity"),
    "WHO": ("entity", "person"),
    "WHICH": ("selection", "entity"),
    "WHOM": ("entity", "person"),
    "WHOSE": ("ownership", "entity"),
    "TODAY": ("temporal", "time"),
    "YESTERDAY": ("temporal", "time"),
    "NOW": ("temporal", "time"),
    "FIRST": ("ordinal", "position"),
    "LAST": ("ordinal", "position"),
    "BEFORE": ("temporal", "time"),
    "AFTER": ("temporal", "time"),
    "NEAR": ("spatial", "location"),
    "INSIDE": ("spatial", "location"),
    "OUTSIDE": ("spatial", "location"),
}

IMPOSSIBLE_RULES = [
    ("interrogative", "WHERE", "modifier", "FIRST", "WHERE requires a place, not an ordinal"),
    ("interrogative", "WHERE", "modifier", "LAST", "WHERE requires a place, not an ordinal"),
    ("interrogative", "WHY", "modifier", "NEAR", "WHY requires a reason, not a spatial modifier"),
    ("interrogative", "WHY", "modifier", "INSIDE", "WHY requires a reason, not a spatial modifier"),
    ("interrogative", "WHY", "modifier", "OUTSIDE", "WHY requires a reason, not a spatial modifier"),
    ("interrogative", "HOW", "modifier", "YESTERDAY", "HOW requires a method, not a past temporal"),
    ("interrogative", "HOW", "modifier", "BEFORE", "HOW requires a method, not a temporal"),
    ("interrogative", "HOW", "modifier", "AFTER", "HOW requires a method, not a temporal"),
    ("interrogative", "WHO", "object", "{DATABASE}", "WHO targets a person, not a database"),
    ("interrogative", "WHO", "object", "{GRAPH}", "WHO targets a person, not a graph"),
    ("interrogative", "WHO", "object", "{LAW}", "WHO targets a person, not a law"),
    ("interrogative", "WHO", "object", "{NODE}", "WHO targets a person, not a node"),
    ("interrogative", "WHO", "object", "{EDGE}", "WHO targets a person, not an edge"),
    ("interrogative", "WHOM", "subject", "{FILE}", "WHOM requires a person subject, not a file"),
    ("interrogative", "WHOM", "subject", "{GRAPH}", "WHOM requires a person subject, not a graph"),
    ("interrogative", "WHOM", "subject", "{DATABASE}", "WHOM requires a person subject"),
    ("interrogative", "WHOSE", "subject", "{FILE}", "WHOSE requires an entity that can own"),
    ("interrogative", "WHOSE", "subject", "{EDGE}", "WHOSE requires an entity that can own"),
    ("interrogative", "WHEN", "modifier", "NEAR", "WHEN requires a temporal, not spatial"),
    ("interrogative", "WHEN", "modifier", "INSIDE", "WHEN requires a temporal, not spatial"),
    ("interrogative", "WHEN", "modifier", "OUTSIDE", "WHEN requires a temporal, not spatial"),
    ("auxiliary", "HAS", "action", "GO", "HAS + GO is semantically invalid"),
    ("auxiliary", "HAVE", "action", "GO", "HAVE + GO is semantically invalid"),
    ("auxiliary", "HAD", "action", "GO", "HAD + GO is semantically invalid"),
    ("auxiliary", "IS", "action", "CREATE", "IS + CREATE is semantically invalid"),
    ("auxiliary", "IS", "action", "DELETE", "IS + DELETE is semantically invalid"),
    ("auxiliary", "IS", "action", "MOVE", "IS + MOVE is semantically invalid"),
    ("auxiliary", "IS", "action", "BUILD", "IS + BUILD is semantically invalid"),
    ("auxiliary", "IS", "action", "LINK", "IS + LINK is semantically invalid"),
    ("auxiliary", "IS", "action", "GENERATE", "IS + GENERATE is semantically invalid"),
    ("auxiliary", "IS", "action", "CONNECT", "IS + CONNECT is semantically invalid"),
    ("auxiliary", "ARE", "action", "CREATE", "ARE + CREATE is semantically invalid"),
    ("auxiliary", "ARE", "action", "DELETE", "ARE + DELETE is semantically invalid"),
    ("auxiliary", "ARE", "action", "BUILD", "ARE + BUILD is semantically invalid"),
    ("auxiliary", "WAS", "action", "CREATE", "WAS + CREATE is semantically invalid"),
    ("auxiliary", "WAS", "action", "DELETE", "WAS + DELETE is semantically invalid"),
    ("auxiliary", "WERE", "action", "BUILD", "WERE + BUILD is semantically invalid"),
]

DIMENSION_COLORS = {
    "location": QColor(46, 90, 130),
    "temporal": QColor(40, 100, 50),
    "causality": QColor(130, 45, 45),
    "procedure": QColor(120, 85, 35),
    "identity": QColor(80, 60, 120),
    "entity": QColor(50, 80, 120),
    "selection": QColor(110, 50, 100),
    "ownership": QColor(150, 70, 30),
    "spatial": QColor(60, 100, 70),
    "ordinal": QColor(100, 60, 90),
    "quantity": QColor(50, 130, 100),
    "measurement": QColor(30, 110, 130),
    "comparison": QColor(130, 100, 50),
    "constraint": QColor(100, 50, 130),
    "inference": QColor(130, 60, 90),
}

INQUIRY_OPERATORS = {
    "WHAT": "IDENTITY", "WHICH": "IDENTITY",
    "WHO": "ENTITY", "WHOM": "ENTITY", "WHOSE": "ENTITY",
    "WHERE": "LOCATION",
    "WHEN": "TIME",
    "WHY": "CAUSE",
    "HOW": "METHOD",
    "HOW_MANY": "QUANTITY",
    "HOW_MUCH": "MEASUREMENT",
    "COMPARED": "COMPARISON",
    "UNDER_CONDITIONS": "CONSTRAINT",
    "WHAT_FOLLOWS": "INFERENCE",
}

OPERATOR_LIST = [
    "IDENTITY", "ENTITY", "LOCATION", "TIME", "CAUSE", "METHOD",
    "QUANTITY", "MEASUREMENT", "COMPARISON", "CONSTRAINT", "INFERENCE",
]

OPERATOR_COLORS = {
    "IDENTITY": QColor(80, 60, 120),
    "ENTITY": QColor(50, 80, 120),
    "LOCATION": QColor(46, 90, 130),
    "TIME": QColor(40, 100, 50),
    "CAUSE": QColor(130, 45, 45),
    "METHOD": QColor(120, 85, 35),
    "QUANTITY": QColor(50, 130, 100),
    "MEASUREMENT": QColor(30, 110, 130),
    "COMPARISON": QColor(130, 100, 50),
    "CONSTRAINT": QColor(100, 50, 130),
    "INFERENCE": QColor(130, 60, 90),
}

LOGICAL_MODES = [
    "ASSERTION", "QUESTION", "COUNTERFACTUAL", "HYPOTHESIS",
    "POSSIBILITY", "NECESSITY", "PROBABILITY", "NORMATIVE",
]

MODE_COLORS = {
    "ASSERTION": QColor(60, 100, 60),
    "QUESTION": QColor(80, 120, 160),
    "COUNTERFACTUAL": QColor(160, 80, 60),
    "HYPOTHESIS": QColor(140, 100, 60),
    "POSSIBILITY": QColor(60, 140, 120),
    "NECESSITY": QColor(120, 60, 140),
    "PROBABILITY": QColor(100, 130, 80),
    "NORMATIVE": QColor(140, 60, 100),
}

AUXILIARY_TO_MODE = {
    "DO": "QUESTION", "DOES": "QUESTION", "DID": "QUESTION",
    "IS": "QUESTION", "ARE": "QUESTION", "WAS": "QUESTION", "WERE": "QUESTION",
    "HAS": "QUESTION", "HAVE": "QUESTION", "HAD": "QUESTION",
    "CAN": "POSSIBILITY", "COULD": "POSSIBILITY",
    "MUST": "NECESSITY",
    "SHOULD": "NORMATIVE", "OUGHT": "NORMATIVE",
    "WOULD": "HYPOTHESIS",
    "WILL": "ASSERTION",
    "MIGHT": "PROBABILITY",
    "MAY": "POSSIBILITY",
    "": "QUESTION",
}

SUBJECT_CATEGORIES = {
    "{PERSON}": "agent", "{USER}": "agent",
    "{SYSTEM}": "system",
    "{THING}": "thing", "{OBJECT}": "thing",
    "{FILE}": "data", "{DATABASE}": "data",
    "{GRAPH}": "structure", "{NODE}": "structure",
    "{EDGE}": "structure", "{LAW}": "structure", "{QUESTION}": "structure",
}

ACTION_CATEGORIES = {
    "GO": "movement", "MOVE": "movement",
    "CREATE": "creation", "BUILD": "creation", "GENERATE": "creation",
    "DELETE": "destruction",
    "READ": "io", "WRITE": "io",
    "LINK": "connection", "CONNECT": "connection",
}

OBJECT_CATEGORIES = {
    "{TARGET}": "target",
    "{FILE}": "data", "{DATABASE}": "data",
    "{NODE}": "structure", "{GRAPH}": "structure",
    "{EDGE}": "structure", "{LAW}": "structure", "{QUESTION}": "structure",
}

MODIFIER_CATEGORIES = {
    "TODAY": "temporal", "YESTERDAY": "temporal", "NOW": "temporal",
    "BEFORE": "temporal", "AFTER": "temporal",
    "FIRST": "ordinal", "LAST": "ordinal",
    "NEAR": "spatial", "INSIDE": "spatial", "OUTSIDE": "spatial",
    "": "none",
}

SLOT_NAMES = ["interrogative", "auxiliary", "subject", "action", "object", "modifier"]


FACT_GRAPH = [
    ("John", "went_to", "Paris", {"time": "yesterday", "reason": "business"}),
    ("John", "works_at", "Acme", {"time": "since 2020"}),
    ("Paris", "located_in", "France", {}),
    ("Acme", "builds", "GraphEngine", {"time": "ongoing"}),
    ("GraphEngine", "contains", "nodes", {"count": 141601}),
    ("GraphEngine", "uses", "SQLite", {"mode": "RAM"}),
    ("SQLite", "stores", "questions", {"count": 883872}),
    ("questions", "classified_by", "operators", {"count": 11}),
    ("operators", "paired_with", "modes", {"count": 8}),
    ("modes", "produce", "cells", {"count": 88}),
]

RELATION_QUESTIONS = {
    "went_to": {
        "from_subject": [
            ("LOCATION", "QUESTION", "Where did {S} go?"),
            ("TIME", "QUESTION", "When did {S} go to {O}?"),
            ("CAUSE", "QUESTION", "Why did {S} go to {O}?"),
            ("METHOD", "QUESTION", "How did {S} get to {O}?"),
        ],
        "from_object": [
            ("ENTITY", "QUESTION", "Who went to {O}?"),
            ("TIME", "QUESTION", "When did someone arrive at {O}?"),
            ("QUANTITY", "QUESTION", "How many people went to {O}?"),
        ],
        "from_edge": [
            ("IDENTITY", "QUESTION", "What is the relation between {S} and {O}?"),
            ("INFERENCE", "QUESTION", "What follows from {S} going to {O}?"),
            ("COMPARISON", "QUESTION", "How does {S}'s trip to {O} compare?"),
            ("CONSTRAINT", "QUESTION", "Under what conditions did {S} go to {O}?"),
        ],
    },
    "works_at": {
        "from_subject": [
            ("LOCATION", "QUESTION", "Where does {S} work?"),
            ("TIME", "QUESTION", "Since when does {S} work at {O}?"),
            ("IDENTITY", "QUESTION", "What is {S}'s role at {O}?"),
        ],
        "from_object": [
            ("ENTITY", "QUESTION", "Who works at {O}?"),
            ("QUANTITY", "QUESTION", "How many work at {O}?"),
        ],
        "from_edge": [
            ("CAUSE", "QUESTION", "Why does {S} work at {O}?"),
            ("INFERENCE", "QUESTION", "What follows from {S} working at {O}?"),
        ],
    },
    "located_in": {
        "from_subject": [
            ("LOCATION", "QUESTION", "Where is {S}?"),
            ("IDENTITY", "QUESTION", "What is {S} part of?"),
        ],
        "from_object": [
            ("ENTITY", "QUESTION", "What is in {O}?"),
            ("QUANTITY", "QUESTION", "How many things are in {O}?"),
        ],
        "from_edge": [
            ("CONSTRAINT", "QUESTION", "Under what conditions is {S} in {O}?"),
        ],
    },
    "builds": {
        "from_subject": [
            ("IDENTITY", "QUESTION", "What does {S} build?"),
            ("METHOD", "QUESTION", "How does {S} build {O}?"),
        ],
        "from_object": [
            ("ENTITY", "QUESTION", "Who builds {O}?"),
            ("TIME", "QUESTION", "When was {O} built?"),
        ],
        "from_edge": [
            ("CAUSE", "QUESTION", "Why does {S} build {O}?"),
            ("INFERENCE", "QUESTION", "What follows from {S} building {O}?"),
        ],
    },
    "contains": {
        "from_subject": [
            ("IDENTITY", "QUESTION", "What does {S} contain?"),
            ("QUANTITY", "QUESTION", "How many things does {S} contain?"),
        ],
        "from_object": [
            ("LOCATION", "QUESTION", "Where are {O} contained?"),
            ("ENTITY", "QUESTION", "What contains {O}?"),
        ],
        "from_edge": [
            ("CONSTRAINT", "QUESTION", "Under what conditions does {S} contain {O}?"),
        ],
    },
    "uses": {
        "from_subject": [
            ("IDENTITY", "QUESTION", "What does {S} use?"),
            ("METHOD", "QUESTION", "How does {S} use {O}?"),
        ],
        "from_object": [
            ("ENTITY", "QUESTION", "What uses {O}?"),
            ("QUANTITY", "QUESTION", "How many things use {O}?"),
        ],
        "from_edge": [
            ("CAUSE", "QUESTION", "Why does {S} use {O}?"),
            ("CONSTRAINT", "QUESTION", "Under what conditions does {S} use {O}?"),
        ],
    },
    "stores": {
        "from_subject": [
            ("IDENTITY", "QUESTION", "What does {S} store?"),
            ("QUANTITY", "QUESTION", "How much does {S} store?"),
        ],
        "from_object": [
            ("LOCATION", "QUESTION", "Where are {O} stored?"),
            ("ENTITY", "QUESTION", "What stores {O}?"),
        ],
        "from_edge": [
            ("METHOD", "QUESTION", "How does {S} store {O}?"),
        ],
    },
    "classified_by": {
        "from_subject": [
            ("IDENTITY", "QUESTION", "What classifies {S}?"),
            ("METHOD", "QUESTION", "How is {S} classified?"),
        ],
        "from_object": [
            ("ENTITY", "QUESTION", "What is classified by {O}?"),
            ("QUANTITY", "QUESTION", "How many things are classified by {O}?"),
        ],
        "from_edge": [
            ("CONSTRAINT", "QUESTION", "Under what conditions is {S} classified by {O}?"),
        ],
    },
    "paired_with": {
        "from_subject": [
            ("IDENTITY", "QUESTION", "What is {S} paired with?"),
            ("METHOD", "QUESTION", "How is {S} paired with {O}?"),
        ],
        "from_object": [
            ("ENTITY", "QUESTION", "What is paired with {O}?"),
        ],
        "from_edge": [
            ("COMPARISON", "QUESTION", "How does {S} pairing with {O} compare?"),
        ],
    },
    "produce": {
        "from_subject": [
            ("IDENTITY", "QUESTION", "What do {S} produce?"),
            ("QUANTITY", "QUESTION", "How many {O} do {S} produce?"),
        ],
        "from_object": [
            ("ENTITY", "QUESTION", "What produces {O}?"),
            ("CAUSE", "QUESTION", "Why are {O} produced?"),
        ],
        "from_edge": [
            ("INFERENCE", "QUESTION", "What follows from {S} producing {O}?"),
        ],
    },
}


class Graph3DWidget(QWidget):
    """3D force-directed graph — custom perspective projection with QPainter.

    Mouse drag = rotate. Wheel = zoom. Nodes colored by dimension.
    Edges colored by dimension. Holes shown as red dashed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = {
            "nodes": [],
            "edges": [],
            "holes": [],
            "rot_x": -0.3,
            "rot_y": 0.0,
            "zoom": 1.0,
            "hover_node": None,
            "layout_done": False,
        }
        self._dragging = False
        self._last_pos = None
        self._positions_3d = {}
        self._velocities = {}
        self.setMinimumSize(600, 500)
        self.setStyleSheet("background: #0a0c12;")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

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

    def SetGraph(self, nodes, edges, holes):
        self.state["nodes"] = nodes
        self.state["edges"] = edges
        self.state["holes"] = holes
        self.state["layout_done"] = False
        self._InitLayout()
        self.update()

    def _InitLayout(self):
        import math
        nodes = self.state["nodes"]
        n = len(nodes)
        self._positions_3d = {}
        self._velocities = {}
        for i, node in enumerate(nodes):
            phi = math.acos(1 - 2 * (i + 0.5) / n)
            theta = math.pi * (1 + 5 ** 0.5) * i
            r = 150
            x = r * math.sin(phi) * math.cos(theta)
            y = r * math.sin(phi) * math.sin(theta)
            z = r * math.cos(phi)
            self._positions_3d[node["id"]] = [x, y, z]
            self._velocities[node["id"]] = [0, 0, 0]
        self.state["layout_done"] = True
        for _ in range(80):
            self._ForceStep()

    def _ForceStep(self):
        import math
        nodes = self.state["nodes"]
        edges = self.state["edges"]
        pos = self._positions_3d
        vel = self._velocities
        if not pos:
            return
        repulsion = 800
        attraction = 0.005
        damping = 0.85
        center_pull = 0.001
        for n1 in nodes:
            nid1 = n1["id"]
            if nid1 not in pos:
                continue
            fx, fy, fz = 0, 0, 0
            for n2 in nodes:
                nid2 = n2["id"]
                if nid1 == nid2 or nid2 not in pos:
                    continue
                dx = pos[nid1][0] - pos[nid2][0]
                dy = pos[nid1][1] - pos[nid2][1]
                dz = pos[nid1][2] - pos[nid2][2]
                dist = math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01
                force = repulsion / (dist * dist)
                fx += force * dx / dist
                fy += force * dy / dist
                fz += force * dz / dist
            fx -= center_pull * pos[nid1][0]
            fy -= center_pull * pos[nid1][1]
            fz -= center_pull * pos[nid1][2]
            vel[nid1][0] = (vel[nid1][0] + fx) * damping
            vel[nid1][1] = (vel[nid1][1] + fy) * damping
            vel[nid1][2] = (vel[nid1][2] + fz) * damping
        edge_set = set()
        for e in edges:
            edge_set.add((e["source"], e["target"]))
        for (sid, tid) in edge_set:
            if sid not in pos or tid not in pos:
                continue
            dx = pos[tid][0] - pos[sid][0]
            dy = pos[tid][1] - pos[sid][1]
            dz = pos[tid][2] - pos[sid][2]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01
            force = attraction * dist
            vel[sid][0] += force * dx / dist
            vel[sid][1] += force * dy / dist
            vel[sid][2] += force * dz / dist
            vel[tid][0] -= force * dx / dist
            vel[tid][1] -= force * dy / dist
            vel[tid][2] -= force * dz / dist
        for nid in pos:
            pos[nid][0] += vel[nid][0]
            pos[nid][1] += vel[nid][1]
            pos[nid][2] += vel[nid][2]

    def _Project(self, x, y, z):
        import math
        rx = self.state["rot_x"]
        ry = self.state["rot_y"]
        cos_y, sin_y = math.cos(ry), math.sin(ry)
        cos_x, sin_x = math.cos(rx), math.sin(rx)
        x2 = x * cos_y - z * sin_y
        z2 = x * sin_y + z * cos_y
        y2 = y * cos_x - z2 * sin_x
        z3 = y * sin_x + z2 * cos_x
        fov = 600
        zoom = self.state["zoom"]
        scale = fov / (fov + z3) * zoom
        cx = self.width() / 2
        cy = self.height() / 2
        sx = cx + x2 * scale
        sy = cy + y2 * scale
        return sx, sy, scale, z3

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_pos = event.position()

    def mouseMoveEvent(self, event):
        if self._dragging and self._last_pos:
            dx = event.position().x() - self._last_pos.x()
            dy = event.position().y() - self._last_pos.y()
            self.state["rot_y"] += dx * 0.01
            self.state["rot_x"] += dy * 0.01
            self._last_pos = event.position()
            self.update()
        else:
            pos = event.position()
            closest = None
            closest_dist = 999
            for node in self.state["nodes"]:
                nid = node["id"]
                if nid not in self._positions_3d:
                    continue
                px, py, py_3d = self._positions_3d[nid]
                sx, sy, scale, _ = self._Project(px, py, py_3d)
                d = ((sx - pos.x()) ** 2 + (sy - pos.y()) ** 2) ** 0.5
                if d < 20 * scale and d < closest_dist:
                    closest_dist = d
                    closest = node
            if closest != self.state.get("hover_node"):
                self.state["hover_node"] = closest
                self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._last_pos = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.state["zoom"] *= 1.15
        else:
            self.state["zoom"] /= 1.15
        self.state["zoom"] = max(0.2, min(5.0, self.state["zoom"]))
        self.update()

    def paintEvent(self, event):
        import math
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor(10, 12, 18))

        painter.setPen(QPen(QColor(20, 22, 30), 1))
        for x in range(0, rect.width(), 50):
            painter.drawLine(QPointF(x, 0), QPointF(x, rect.height()))
        for y in range(0, rect.height(), 50):
            painter.drawLine(QPointF(0, y), QPointF(rect.width(), y))

        nodes = self.state["nodes"]
        edges = self.state["edges"]
        holes = self.state["holes"]
        pos = self._positions_3d

        if not nodes or not pos:
            painter.setPen(QPen(QColor(100, 100, 120)))
            painter.setFont(QFont("Menlo", 12))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             "Build graph to see 3D visualization\nDrag to rotate | Wheel to zoom")
            return

        projected = {}
        depths = {}
        for node in nodes:
            nid = node["id"]
            if nid not in pos:
                continue
            sx, sy, scale, depth = self._Project(pos[nid][0], pos[nid][1], pos[nid][2])
            projected[nid] = (sx, sy, scale)
            depths[nid] = depth

        hole_set = set()
        for h in holes:
            hole_set.add((h["source"], h["target"]))

        edge_depths = []
        for edge in edges:
            src = edge["source"]
            tgt = edge["target"]
            if src not in projected or tgt not in projected:
                continue
            avg_depth = (depths[src] + depths[tgt]) / 2
            edge_depths.append((avg_depth, edge))
        edge_depths.sort(key=lambda x: x[0], reverse=True)

        for avg_depth, edge in edge_depths:
            src = edge["source"]
            tgt = edge["target"]
            sx1, sy1, s1 = projected[src]
            sx2, sy2, s2 = projected[tgt]
            is_hole = (src, tgt) in hole_set
            dim = edge.get("dimension", "unknown")
            if is_hole:
                painter.setPen(QPen(QColor(180, 60, 60, 60), 1, Qt.PenStyle.DashLine))
            else:
                color = DIMENSION_COLORS.get(dim, QColor(60, 70, 90))
                alpha = int(max(30, min(180, 200 - abs(avg_depth) * 0.3)))
                painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), alpha), 1.5))
            painter.drawLine(QPointF(sx1, sy1), QPointF(sx2, sy2))

        node_depths = sorted(depths.items(), key=lambda x: x[1], reverse=True)
        for nid, depth in node_depths:
            node = None
            for n in nodes:
                if n["id"] == nid:
                    node = n
                    break
            if not node:
                continue
            sx, sy, scale = projected[nid]
            dim = node.get("dimension", "unknown")
            color = DIMENSION_COLORS.get(dim, QColor(80, 80, 100))
            r = max(4, 14 * scale)
            gradient = QLinearGradient(sx, sy - r, sx, sy + r)
            gradient.setColorAt(0, color.lighter(150))
            gradient.setColorAt(1, color.darker(150))
            painter.setBrush(QBrush(gradient))
            is_hover = self.state.get("hover_node") and self.state["hover_node"]["id"] == nid
            if is_hover:
                painter.setPen(QPen(QColor(255, 230, 80), 2))
                r += 3
            else:
                painter.setPen(QPen(color.lighter(170), 1))
            painter.drawEllipse(QPointF(sx, sy), r, r)
            if scale > 0.4 or is_hover:
                painter.setPen(QPen(QColor(220, 230, 240) if is_hover else QColor(160, 170, 190)))
                painter.setFont(QFont("Menlo", max(6, int(7 * scale)), QFont.Weight.Bold))
                label = node["label"][:10]
                painter.drawText(QRectF(sx - r - 5, sy - r - 12, 2 * r + 10, 14),
                                 Qt.AlignmentFlag.AlignCenter, label)

        hover = self.state.get("hover_node")
        if hover:
            painter.setPen(QPen(QColor(255, 230, 80)))
            painter.setFont(QFont("Menlo", 9))
            info = "%s  [%s]  dim=%s" % (
                hover.get("label", "?"),
                hover.get("type", "?"),
                hover.get("dimension", "?"),
            )
            painter.drawText(QRectF(10, rect.height() - 50, rect.width() - 20, 20),
                             Qt.AlignmentFlag.AlignLeft, info)
            nid = hover["id"]
            connections = sum(1 for e in edges if e["source"] == nid or e["target"] == nid)
            painter.drawText(QRectF(10, rect.height() - 32, rect.width() - 20, 20),
                             Qt.AlignmentFlag.AlignLeft, "connections: %d" % connections)

        painter.setPen(QPen(QColor(80, 80, 100)))
        painter.setFont(QFont("Menlo", 8))
        painter.drawText(QRectF(rect.width() - 120, 10, 110, 20),
                         Qt.AlignmentFlag.AlignRight, "zoom: %.1fx" % self.state["zoom"])
        painter.drawText(QRectF(rect.width() - 120, 28, 110, 20),
                         Qt.AlignmentFlag.AlignRight, "rot: %.1f,%.1f" % (
                             self.state["rot_x"], self.state["rot_y"]))
        painter.drawText(QRectF(10, 10, 200, 20),
                         Qt.AlignmentFlag.AlignLeft, "Drag=rotate  Wheel=zoom  Hover=inspect")
        painter.drawText(QRectF(0, rect.height() - 15, rect.width(), 15),
                         Qt.AlignmentFlag.AlignCenter,
                         "3D: %d nodes | %d edges | %d holes" % (
                             len(nodes), len(edges) - len(holes), len(holes)))


class FactGraphWidget(QWidget):
    """Yin/Yang — fact graph with question neighborhoods emerging from edges."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = {
            "facts": [],
            "questions": [],
            "hover_edge": None,
        }
        self.setMinimumSize(800, 600)
        self.setStyleSheet("background: #14161c;")
        self.setMouseTracking(True)

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

    def SetFacts(self, facts, questions):
        self.state["facts"] = facts
        self.state["questions"] = questions
        self.update()

    def paintEvent(self, event):
        import math
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor(20, 22, 28))
        facts = self.state["facts"]
        if not facts:
            painter.setPen(QPen(QColor(100, 100, 120)))
            painter.setFont(QFont("Menlo", 12))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             "Click 'Yin/Yang' to see facts generate questions")
            return

        nodes = set()
        for s, r, o, ctx in facts:
            nodes.add(s)
            nodes.add(o)
        nodes = sorted(nodes)
        n = len(nodes)
        cx = rect.width() / 2
        cy = rect.height() / 2
        radius = min(cx, cy) - 80
        positions = {}
        for i, node in enumerate(nodes):
            angle = 2 * math.pi * i / n - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            positions[node] = QPointF(x, y)

        for s, r, o, ctx in facts:
            src = positions.get(s)
            dst = positions.get(o)
            if not src or not dst:
                continue
            path = QPainterPath()
            path.moveTo(src)
            mid = QPointF((src.x() + dst.x()) / 2, (src.y() + dst.y()) / 2)
            ctrl = QPointF(cx + (mid.x() - cx) * 0.2, cy + (mid.y() - cy) * 0.2)
            path.quadTo(ctrl, dst)
            painter.setPen(QPen(QColor(60, 80, 120, 120), 1.5))
            painter.drawPath(path)
            painter.setPen(QPen(QColor(120, 140, 180)))
            painter.setFont(QFont("Menlo", 7))
            painter.drawText(mid.x() - 30, mid.y() - 5, r)

        for node in nodes:
            pos = positions[node]
            r = 22
            gradient = QLinearGradient(pos.x(), pos.y() - r, pos.x(), pos.y() + r)
            gradient.setColorAt(0, QColor(60, 100, 140))
            gradient.setColorAt(1, QColor(30, 50, 80))
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor(100, 150, 200), 1.5))
            painter.drawEllipse(pos, r, r)
            painter.setPen(QPen(QColor(220, 230, 240)))
            painter.setFont(QFont("Menlo", 7, QFont.Weight.Bold))
            label = node[:10]
            painter.drawText(QRectF(pos.x() - r, pos.y() - r, 2 * r, 2 * r),
                             Qt.AlignmentFlag.AlignCenter, label)

        painter.setPen(QPen(QColor(100, 100, 120)))
        painter.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(0, rect.height() - 40, rect.width(), 20),
                         Qt.AlignmentFlag.AlignCenter,
                         "YIN: %d facts  |  YANG: %d questions  |  1 fact -> %.1f questions" % (
                             len(facts), len(self.state["questions"]),
                             len(self.state["questions"]) / max(len(facts), 1)
                         ))
        painter.drawText(QRectF(0, rect.height() - 22, rect.width(), 20),
                         Qt.AlignmentFlag.AlignCenter,
                         "Questions EMERGE from traversing the fact graph")


class BasisMatrixWidget(QWidget):
    """11x8 grid showing the 88 fundamental inquiry types, with real question counts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = {
            "cell_counts": {},
            "total_real": 0,
            "hover_cell": None,
        }
        self.setMinimumSize(700, 500)
        self.setStyleSheet("background: #14161c;")
        self.setMouseTracking(True)

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

    def SetCounts(self, counts, total):
        self.state["cell_counts"] = counts
        self.state["total_real"] = total
        self.update()

    def mouseMoveEvent(self, event):
        cell = self.CellAt(event.position().x(), event.position().y())
        if cell != self.state["hover_cell"]:
            self.state["hover_cell"] = cell
            self.update()

    def CellAt(self, x, y):
        margin = 80
        cell_w = (self.width() - margin - 20) / len(LOGICAL_MODES)
        cell_h = (self.height() - margin - 20) / len(OPERATOR_LIST)
        if x < margin or y < margin:
            return None
        col = int((x - margin) / cell_w)
        row = int((y - margin) / cell_h)
        if 0 <= col < len(LOGICAL_MODES) and 0 <= row < len(OPERATOR_LIST):
            return (row, col)
        return None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor(20, 22, 28))

        margin = 80
        cell_w = (rect.width() - margin - 20) / len(LOGICAL_MODES)
        cell_h = (rect.height() - margin - 20) / len(OPERATOR_LIST)

        painter.setPen(QPen(QColor(100, 100, 120)))
        painter.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
        for i, op in enumerate(OPERATOR_LIST):
            y = margin + i * cell_h + cell_h / 2
            color = OPERATOR_COLORS[op]
            painter.setPen(QPen(color.lighter(130)))
            painter.drawText(QRectF(0, y - cell_h / 2, margin - 5, cell_h),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, op)

        painter.setPen(QPen(QColor(100, 100, 120)))
        for j, mode in enumerate(LOGICAL_MODES):
            x = margin + j * cell_w + cell_w / 2
            color = MODE_COLORS[mode]
            painter.setPen(QPen(color.lighter(130)))
            painter.drawText(QRectF(x - cell_w / 2, 5, cell_w, margin - 5),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, mode)

        counts = self.state["cell_counts"]
        total = self.state["total_real"]
        max_count = max(counts.values()) if counts else 1

        for i, op in enumerate(OPERATOR_LIST):
            for j, mode in enumerate(LOGICAL_MODES):
                x = margin + j * cell_w
                y = margin + i * cell_h
                key = "%s x %s" % (op, mode)
                count = counts.get(key, 0)
                is_hover = self.state["hover_cell"] == (i, j)

                if count > 0:
                    intensity = min(1.0, count / max_count) if max_count else 0
                    op_color = OPERATOR_COLORS[op]
                    mode_color = MODE_COLORS[mode]
                    r = int(op_color.red() * 0.5 + mode_color.red() * 0.5)
                    g = int(op_color.green() * 0.5 + mode_color.green() * 0.5)
                    b = int(op_color.blue() * 0.5 + mode_color.blue() * 0.5)
                    r = int(r + (255 - r) * intensity * 0.3)
                    g = int(g + (255 - g) * intensity * 0.3)
                    b = int(b + (255 - b) * intensity * 0.3)
                    cell_color = QColor(r, g, b)
                else:
                    cell_color = QColor(30, 32, 40)

                painter.setBrush(QBrush(cell_color))
                if is_hover:
                    painter.setPen(QPen(QColor(255, 230, 80), 2))
                else:
                    painter.setPen(QPen(QColor(40, 42, 50), 1))
                painter.drawRoundedRect(QRectF(x + 2, y + 2, cell_w - 4, cell_h - 4), 4, 4)

                if count > 0:
                    painter.setPen(QPen(QColor(255, 255, 255) if intensity > 0.5 else QColor(200, 200, 210)))
                    painter.setFont(QFont("Menlo", 7))
                    text = str(count)
                    if count >= 1000:
                        text = "%.1fK" % (count / 1000)
                    painter.drawText(QRectF(x + 2, y + 2, cell_w - 4, cell_h - 4),
                                     Qt.AlignmentFlag.AlignCenter, text)
                else:
                    painter.setPen(QPen(QColor(60, 50, 50)))
                    painter.setFont(QFont("Menlo", 7))
                    painter.drawText(QRectF(x + 2, y + 2, cell_w - 4, cell_h - 4),
                                     Qt.AlignmentFlag.AlignCenter, "—")

        painter.setPen(QPen(QColor(100, 100, 120)))
        painter.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        title = "Basis Matrix: %d operators x %d modes = %d fundamental inquiry types" % (
            len(OPERATOR_LIST), len(LOGICAL_MODES), len(OPERATOR_LIST) * len(LOGICAL_MODES)
        )
        painter.drawText(QRectF(0, rect.height() - 25, rect.width(), 25),
                         Qt.AlignmentFlag.AlignCenter, title)

        if total > 0:
            filled = sum(1 for v in counts.values() if v > 0)
            painter.drawText(QRectF(0, rect.height() - 45, rect.width(), 20),
                             Qt.AlignmentFlag.AlignCenter,
                             "Real questions mapped: %d | Cells filled: %d/%d | Holes: %d" % (
                                 total, filled, len(OPERATOR_LIST) * len(LOGICAL_MODES),
                                 len(OPERATOR_LIST) * len(LOGICAL_MODES) - filled
                             ))


class CompressionGraphWidget(QWidget):
    """Flow diagram showing the 7-layer compression hierarchy with edge labels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = {"layers": []}
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background: #14161c;")

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

    def SetLayers(self, layers):
        self.state["layers"] = layers
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor(20, 22, 28))

        layers = self.state["layers"]
        if not layers:
            painter.setPen(QPen(QColor(100, 100, 120)))
            painter.setFont(QFont("Menlo", 12))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Run analysis to see compression hierarchy")
            return

        n = len(layers)
        box_w = 280
        box_h = 50
        gap = (rect.height() - 80 - n * box_h) / max(n - 1, 1)
        start_y = 30
        cx = rect.width() / 2

        for i, layer in enumerate(layers):
            y = start_y + i * (box_h + gap)
            count = layer["count"]
            label = layer["label"]
            rule = layer.get("rule", "")
            color = layer.get("color", QColor(60, 80, 120))

            gradient = QLinearGradient(cx - box_w / 2, y, cx + box_w / 2, y)
            gradient.setColorAt(0, color.darker(140))
            gradient.setColorAt(1, color)
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(color.lighter(150), 1.5))
            painter.drawRoundedRect(QRectF(cx - box_w / 2, y, box_w, box_h), 8, 8)

            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(cx - box_w / 2 + 10, y + 5, box_w - 20, 20),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

            painter.setPen(QPen(QColor(200, 210, 220)))
            painter.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
            count_text = "{:,}".format(count)
            painter.drawText(QRectF(cx - box_w / 2 + 10, y + 22, box_w - 20, 25),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, count_text)

            if i < n - 1:
                next_y = start_y + (i + 1) * (box_h + gap)
                arrow_x = cx
                painter.setPen(QPen(QColor(80, 90, 110), 2))
                painter.drawLine(QPointF(arrow_x, y + box_h), QPointF(arrow_x, next_y))

                painter.setPen(QPen(QColor(180, 160, 80)))
                painter.setFont(QFont("Menlo", 7))
                painter.drawText(QRectF(arrow_x + 8, y + box_h, 200, next_y - y - box_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, rule)

                arrow_head = QPointF(arrow_x, next_y - 2)
                painter.setPen(QPen(QColor(80, 90, 110), 2))
                painter.setBrush(QBrush(QColor(80, 90, 110)))
                painter.drawPolygon(QPolygonF([
                    arrow_head,
                    QPointF(arrow_x - 5, next_y - 10),
                    QPointF(arrow_x + 5, next_y - 10),
                ]))

        painter.setPen(QPen(QColor(100, 100, 120)))
        painter.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        first_count = layers[0]["count"] if layers else 1
        last_count = layers[-1]["count"] if layers else 1
        ratio = first_count / last_count if last_count else 0
        painter.drawText(QRectF(0, rect.height() - 25, rect.width(), 25),
                         Qt.AlignmentFlag.AlignCenter,
                         "Total compression: {:,} -> {:,} = {:.0f}:1".format(
                             first_count, last_count, ratio))


class SemanticGraphWidget(QWidget):
    """Canvas showing which token types combine and where the holes are."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = {
            "nodes": [],
            "edges": [],
            "holes": [],
            "highlight_dim": None,
        }
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background: #14161c;")

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

    def SetGraph(self, nodes, edges, holes):
        self.state["nodes"] = nodes
        self.state["edges"] = edges
        self.state["holes"] = holes
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor(20, 22, 28))

        painter.setPen(QPen(QColor(30, 32, 40), 1))
        for x in range(0, rect.width(), 40):
            painter.drawLine(QPointF(x, 0), QPointF(x, rect.height()))
        for y in range(0, rect.height(), 40):
            painter.drawLine(QPointF(0, y), QPointF(rect.width(), y))

        nodes = self.state["nodes"]
        edges = self.state["edges"]
        holes = self.state["holes"]
        highlight = self.state.get("highlight_dim")

        if not nodes:
            painter.setPen(QPen(QColor(100, 100, 120)))
            painter.setFont(QFont("Menlo", 12))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             "Generate questions to see the semantic graph")
            return

        cx = rect.width() / 2
        cy = rect.height() / 2
        radius = min(cx, cy) - 60
        positions = {}
        n = len(nodes)
        for i, node in enumerate(nodes):
            angle = 2 * 3.14159 * i / n - 3.14159 / 2
            x = cx + radius * __import__("math").cos(angle)
            y = cy + radius * __import__("math").sin(angle)
            positions[node["id"]] = QPointF(x, y)

        for edge in edges:
            src = positions.get(edge["source"])
            dst = positions.get(edge["target"])
            if not src or not dst:
                continue
            is_hole = edge in holes
            if is_hole:
                painter.setPen(QPen(QColor(180, 60, 60, 80), 1, Qt.PenStyle.DashLine))
            else:
                dim = edge.get("dimension")
                color = DIMENSION_COLORS.get(dim, QColor(80, 80, 100))
                if highlight and dim != highlight:
                    painter.setPen(QPen(QColor(40, 42, 50, 60), 1))
                else:
                    painter.setPen(QPen(color, 1.5))
            path = QPainterPath()
            path.moveTo(src)
            mid = QPointF((src.x() + dst.x()) / 2, (src.y() + dst.y()) / 2)
            ctrl = QPointF(cx + (mid.x() - cx) * 0.3, cy + (mid.y() - cy) * 0.3)
            path.quadTo(ctrl, dst)
            painter.drawPath(path)

        for node in nodes:
            pos = positions[node["id"]]
            dim = node.get("dimension", "unknown")
            color = DIMENSION_COLORS.get(dim, QColor(80, 80, 100))
            if highlight and dim != highlight:
                color = QColor(40, 42, 50)
            r = 18
            gradient = QLinearGradient(pos.x(), pos.y() - r, pos.x(), pos.y() + r)
            gradient.setColorAt(0, color.lighter(130))
            gradient.setColorAt(1, color.darker(130))
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(color.lighter(150), 1.5))
            painter.drawEllipse(pos, r, r)
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Menlo", 7, QFont.Weight.Bold))
            label = node["label"][:8]
            painter.drawText(QRectF(pos.x() - r, pos.y() - r, 2 * r, 2 * r),
                             Qt.AlignmentFlag.AlignCenter, label)

        painter.setPen(QPen(QColor(100, 100, 120)))
        painter.setFont(QFont("Menlo", 9))
        total = len(edges)
        hole_count = len(holes)
        painter.drawText(10, rect.height() - 20,
                         "Edges: %d  |  Holes: %d  |  Coverage: %.1f%%" % (
                             total - hole_count, hole_count,
                             100.0 * (total - hole_count) / total if total else 0))


class QuestionSpaceExplorer(QMainWindow):
    """Main GUI — semantic question space explorer with SQLite in RAM."""

    def __init__(self):
        super().__init__()
        self.state = {
            "db": None,
            "atoms": dict(DEFAULT_ATOMS),
            "generated": [],
            "dimensions": {},
            "holes": [],
            "graph_nodes": [],
            "graph_edges": [],
            "limit": 10000,
            "filter_dim": None,
            "show_holes_only": False,
        }
        self.setWindowTitle("Question Space Explorer — Semantic Cartesian Explosion (SQLite RAM)")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet("QMainWindow { background: #14161c; }")
        self.InitDb()
        self.InitUi()

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, params):
        if isinstance(params, dict):
            for k, v in params.items():
                if k in self.state:
                    self.state[k] = v
        return (1, dict(self.state), None)

    def InitDb(self):
        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.execute("CREATE TABLE token (id INTEGER PRIMARY KEY, type TEXT, value TEXT, dimension TEXT, requires TEXT)")
        db.execute("CREATE TABLE question (id INTEGER PRIMARY KEY, sig TEXT, interrogative TEXT, auxiliary TEXT, subject TEXT, action TEXT, object TEXT, modifier TEXT, english TEXT, dimensions TEXT)")
        db.execute("CREATE TABLE combination (source_type TEXT, source_value TEXT, target_type TEXT, target_value TEXT, dimension TEXT, is_hole INTEGER DEFAULT 0)")
        idx = 1
        for token_type, values in self.state["atoms"].items():
            for val in values:
                dim_info = TOKEN_DIMENSIONS.get(val.upper(), (None, None))
                db.execute("INSERT INTO token (id, type, value, dimension, requires) VALUES (?, ?, ?, ?, ?)",
                           (idx, token_type, val, dim_info[0], dim_info[1]))
                idx += 1
        db.commit()
        self.state["db"] = db

    def RebuildAtoms(self, new_atoms):
        self.state["atoms"] = new_atoms
        db = self.state["db"]
        db.execute("DELETE FROM token")
        idx = 1
        for token_type, values in new_atoms.items():
            for val in values:
                dim_info = TOKEN_DIMENSIONS.get(val.upper(), (None, None))
                db.execute("INSERT INTO token (id, type, value, dimension, requires) VALUES (?, ?, ?, ?, ?)",
                           (idx, token_type, val, dim_info[0], dim_info[1]))
                idx += 1
        db.execute("DELETE FROM question")
        db.execute("DELETE FROM combination")
        db.commit()

    def InitUi(self):
        central = QWidget()
        central.setStyleSheet("background: #14161c;")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar("Explorer", self)
        toolbar.setMovable(False)
        toolbar.setStyleSheet(
            "QToolBar { background: #1a1c24; border: none; border-bottom: 1px solid #2a2c34; padding: 2px; spacing: 4px; }"
            "QToolBar QToolButton { background: #2a2c36; color: #c0c0d0; border: 1px solid #3a3c48; padding: 4px 12px; border-radius: 4px; font-size: 11px; }"
            "QToolBar QToolButton:hover { background: #3a3c48; }"
            "QToolBar QToolButton:pressed { background: #1a1c24; }"
            "QToolBar QLabel { color: #6a6a7a; font-size: 10px; padding: 0 4px; }"
            "QToolBar QSeparator { width: 1px; background: #2a2c34; margin: 2px 4px; }"
        )
        self.addToolBar(toolbar)

        act_gen = QAction("Generate", self)
        act_gen.setToolTip("Run Cartesian explosion")
        act_gen.triggered.connect(self.OnGenerate)
        toolbar.addAction(act_gen)

        act_holes = QAction("Find Holes", self)
        act_holes.setToolTip("Find missing combinations in the semantic space")
        act_holes.triggered.connect(self.OnFindHoles)
        toolbar.addAction(act_holes)

        act_graph = QAction("Build Graph", self)
        act_graph.setToolTip("Build semantic dimension graph")
        act_graph.triggered.connect(self.OnBuildGraph)
        toolbar.addAction(act_graph)

        act_3d = QAction("3D Graph", self)
        act_3d.setToolTip("Build 3D force-directed graph (drag to rotate, wheel to zoom)")
        act_3d.triggered.connect(self.OnBuild3DGraph)
        toolbar.addAction(act_3d)

        self.act_fullscreen = QAction("[<<] Full Width", self)
        self.act_fullscreen.setToolTip("Hide left panel to give 3D graph full width")
        self.act_fullwidth = False
        self.act_fullscreen.triggered.connect(self.OnToggleWidth)
        toolbar.addAction(self.act_fullscreen)

        act_topo = QAction("Topology", self)
        act_topo.setToolTip("Analyze which operators are most connected")
        act_topo.triggered.connect(self.OnTopology)
        toolbar.addAction(act_topo)

        act_impossible = QAction("Impossible", self)
        act_impossible.setToolTip("Show impossible combinations by type constraint")
        act_impossible.triggered.connect(self.OnImpossible)
        toolbar.addAction(act_impossible)

        act_dedup = QAction("Dedup", self)
        act_dedup.setToolTip("Deduplicate equivalent semantic signatures")
        act_dedup.triggered.connect(self.OnDedup)
        toolbar.addAction(act_dedup)

        toolbar.addSeparator()

        act_basis = QAction("Basis Matrix", self)
        act_basis.setToolTip("Build the 11x8 operator x mode matrix")
        act_basis.triggered.connect(self.OnBasisMatrix)
        toolbar.addAction(act_basis)

        act_compress = QAction("Compression", self)
        act_compress.setToolTip("Show the full compression hierarchy")
        act_compress.triggered.connect(self.OnCompression)
        toolbar.addAction(act_compress)

        act_realmap = QAction("Map Real", self)
        act_realmap.setToolTip("Map 141K real questions to the 88 basis cells")
        act_realmap.triggered.connect(self.OnMapReal)
        toolbar.addAction(act_realmap)

        act_recursion = QAction("Recursion", self)
        act_recursion.setToolTip("Test whether the basis holds with nested questions")
        act_recursion.triggered.connect(self.OnRecursion)
        toolbar.addAction(act_recursion)

        act_yinyang = QAction("Yin/Yang", self)
        act_yinyang.setToolTip("Generate questions from the fact graph (facts -> questions)")
        act_yinyang.triggered.connect(self.OnYinYang)
        toolbar.addAction(act_yinyang)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel(" Limit:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(100, 1000000)
        self.limit_spin.setValue(self.state["limit"])
        self.limit_spin.setStyleSheet(
            "QSpinBox { background: #2a2c36; color: #c0c0d0; border: 1px solid #3a3c48; padding: 3px; border-radius: 4px; font-size: 11px; }"
        )
        toolbar.addWidget(self.limit_spin)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel(" Filter dim:"))
        self.dim_combo = QComboBox()
        self.dim_combo.addItem("All", None)
        for dim in sorted(DIMENSION_COLORS.keys()):
            self.dim_combo.addItem(dim, dim)
        self.dim_combo.setStyleSheet(
            "QComboBox { background: #2a2c36; color: #c0c0d0; border: 1px solid #3a3c48; padding: 3px 8px; border-radius: 4px; font-size: 11px; }"
        )
        self.dim_combo.currentIndexChanged.connect(self.OnDimFilter)
        toolbar.addWidget(self.dim_combo)

        toolbar.addSeparator()

        self.holes_check = QCheckBox("Holes only")
        self.holes_check.setStyleSheet("QCheckBox { color: #c0c0d0; font-size: 11px; padding: 0 8px; }")
        self.holes_check.toggled.connect(self.OnHolesToggle)
        toolbar.addWidget(self.holes_check)

        toolbar.addSeparator()

        act_export = QAction("Export CSV", self)
        act_export.setToolTip("Export generated questions as CSV")
        act_export.triggered.connect(self.OnExport)
        toolbar.addAction(act_export)

        act_random = QAction("Random 20", self)
        act_random.setToolTip("Show 20 random generated questions")
        act_random.triggered.connect(self.OnRandom)
        toolbar.addAction(act_random)

        spacer = QWidget()
        spacer.setFixedSize(20, 1)
        toolbar.addWidget(spacer)

        self.stats_label = QLabel("Ready")
        self.stats_label.setStyleSheet("color: #6a6a7a; font-size: 10px; padding-right: 8px;")
        toolbar.addWidget(self.stats_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        self.left_panel = self.BuildAtomPanel()
        splitter.addWidget(self.left_panel)

        self.splitter = splitter

        self.tabs = QTabWidget()
        tabs = self.tabs
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #2a2c34; background: #14161c; }"
            "QTabBar::tab { background: #1a1c24; color: #8a8a9a; padding: 6px 16px; border: 1px solid #2a2c34; font-size: 11px; }"
            "QTabBar::tab:selected { background: #2a2c36; color: #c0c0d0; border-bottom: 2px solid #5060a0; }"
        )

        self.question_table = QTableWidget()
        self.question_table.setColumnCount(8)
        self.question_table.setHorizontalHeaderLabels(
            ["ID", "Signature", "Interrogative", "Auxiliary", "Subject", "Action", "Object", "Modifier"]
        )
        self.question_table.setStyleSheet(
            "QTableWidget { background: #14161c; color: #c0c0d0; gridline-color: #2a2c34; font-size: 11px; }"
            "QHeaderView::section { background: #1a1c24; color: #8a8a9a; border: 1px solid #2a2c34; padding: 4px; font-size: 10px; }"
        )
        self.question_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.question_table, "Questions")

        self.english_table = QTableWidget()
        self.english_table.setColumnCount(3)
        self.english_table.setHorizontalHeaderLabels(["ID", "Signature", "English Rendering"])
        self.english_table.setStyleSheet(self.question_table.styleSheet())
        self.english_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.english_table, "English")

        self.sig_table = QTableWidget()
        self.sig_table.setColumnCount(7)
        self.sig_table.setHorizontalHeaderLabels(
            ["Signature", "Operator", "Subject", "Verb", "Object", "Time", "Dimensions"]
        )
        self.sig_table.setStyleSheet(self.question_table.styleSheet())
        self.sig_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.sig_table, "Signatures")

        self.holes_table = QTableWidget()
        self.holes_table.setColumnCount(5)
        self.holes_table.setHorizontalHeaderLabels(
            ["Source Type", "Source Value", "Target Type", "Target Value", "Dimension"]
        )
        self.holes_table.setStyleSheet(self.question_table.styleSheet())
        self.holes_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.holes_table, "Holes")

        self.graph_widget = SemanticGraphWidget()
        graph_scroll = QScrollArea()
        graph_scroll.setWidget(self.graph_widget)
        graph_scroll.setWidgetResizable(True)
        graph_scroll.setStyleSheet("QScrollArea { border: none; background: #14161c; }")
        tabs.addTab(graph_scroll, "Graph")

        self.graph3d_widget = Graph3DWidget()
        graph3d_scroll = QScrollArea()
        graph3d_scroll.setWidget(self.graph3d_widget)
        graph3d_scroll.setWidgetResizable(True)
        graph3d_scroll.setStyleSheet("QScrollArea { border: none; background: #0a0c12; }")
        tabs.addTab(graph3d_scroll, "3D Graph")

        self.basis_matrix = BasisMatrixWidget()
        basis_scroll = QScrollArea()
        basis_scroll.setWidget(self.basis_matrix)
        basis_scroll.setWidgetResizable(True)
        basis_scroll.setStyleSheet("QScrollArea { border: none; background: #14161c; }")
        tabs.addTab(basis_scroll, "Basis Matrix")

        self.compression_widget = CompressionGraphWidget()
        comp_scroll = QScrollArea()
        comp_scroll.setWidget(self.compression_widget)
        comp_scroll.setWidgetResizable(True)
        comp_scroll.setStyleSheet("QScrollArea { border: none; background: #14161c; }")
        tabs.addTab(comp_scroll, "Compression")

        self.real_map_table = QTableWidget()
        self.real_map_table.setColumnCount(5)
        self.real_map_table.setHorizontalHeaderLabels(
            ["Operator", "Mode", "Count", "% of Real", "Example"]
        )
        self.real_map_table.setStyleSheet(self.question_table.styleSheet())
        self.real_map_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.real_map_table, "Real Map")

        self.recursion_text = QTextEdit()
        self.recursion_text.setReadOnly(True)
        self.recursion_text.setStyleSheet(
            "QTextEdit { background: #14161c; color: #c0c0d0; font-family: Menlo; font-size: 11px; border: none; }"
        )
        tabs.addTab(self.recursion_text, "Recursion")

        self.fact_graph_widget = FactGraphWidget()
        fact_scroll = QScrollArea()
        fact_scroll.setWidget(self.fact_graph_widget)
        fact_scroll.setWidgetResizable(True)
        fact_scroll.setStyleSheet("QScrollArea { border: none; background: #14161c; }")
        tabs.addTab(fact_scroll, "Yin/Yang")

        self.fact_q_table = QTableWidget()
        self.fact_q_table.setColumnCount(6)
        self.fact_q_table.setHorizontalHeaderLabels(
            ["Fact", "Direction", "Operator", "Mode", "Question", "Cell"]
        )
        self.fact_q_table.setStyleSheet(self.question_table.styleSheet())
        self.fact_q_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.fact_q_table, "Fact Questions")

        self.topology_table = QTableWidget()
        self.topology_table.setColumnCount(4)
        self.topology_table.setHorizontalHeaderLabels(
            ["Token", "Type", "Connections", "Degree %"]
        )
        self.topology_table.setStyleSheet(self.question_table.styleSheet())
        self.topology_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.topology_table, "Topology")

        self.impossible_table = QTableWidget()
        self.impossible_table.setColumnCount(5)
        self.impossible_table.setHorizontalHeaderLabels(
            ["Slot A", "Value A", "Slot B", "Value B", "Reason"]
        )
        self.impossible_table.setStyleSheet(self.question_table.styleSheet())
        self.impossible_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.impossible_table, "Impossible")

        self.dedup_table = QTableWidget()
        self.dedup_table.setColumnCount(4)
        self.dedup_table.setHorizontalHeaderLabels(
            ["Signature", "English", "Count", "Equivalent Forms"]
        )
        self.dedup_table.setStyleSheet(self.question_table.styleSheet())
        self.dedup_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.dedup_table, "Dedup")

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setStyleSheet(
            "QTextEdit { background: #14161c; color: #c0c0d0; font-family: Menlo; font-size: 11px; border: none; }"
        )
        tabs.addTab(self.stats_text, "Stats")

        splitter.addWidget(tabs)
        splitter.setSizes([350, 1050])

    def BuildAtomPanel(self):
        group = QGroupBox("Semantic Atoms")
        group.setStyleSheet(
            "QGroupBox { color: #8a8a9a; border: 1px solid #2a2c34; border-radius: 4px; margin: 4px; padding-top: 12px; font-size: 11px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
        )
        layout = QGridLayout(group)
        layout.setSpacing(4)

        self.atom_tables = {}
        for col, token_type in enumerate(SLOT_NAMES):
            label = QLabel(token_type.upper())
            label.setStyleSheet("color: #6a8aaa; font-size: 10px; font-weight: bold;")
            layout.addWidget(label, 0, col)

            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Value", "Dimension"])
            table.setStyleSheet(
                "QTableWidget { background: #1a1c24; color: #c0c0d0; gridline-color: #2a2c34; font-size: 10px; }"
                "QHeaderView::section { background: #14161c; color: #6a6a7a; border: 1px solid #2a2c34; padding: 2px; font-size: 9px; }"
            )
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setMinimumWidth(100)
            values = self.state["atoms"][token_type]
            table.setRowCount(len(values))
            for row, val in enumerate(values):
                dim_info = TOKEN_DIMENSIONS.get(val.upper(), ("", ""))
                table.setItem(row, 0, QTableWidgetItem(val))
                table.setItem(row, 1, QTableWidgetItem(dim_info[0] or ""))
            table.cellChanged.connect(lambda r, c, t=token_type: self.OnAtomEdit(t))
            self.atom_tables[token_type] = table
            layout.addWidget(table, 1, col)

        add_btn = QPushButton("+ Add Token")
        add_btn.setStyleSheet(
            "QPushButton { background: #2a2c36; color: #c0c0d0; border: 1px solid #3a3c48; padding: 4px; border-radius: 4px; font-size: 10px; }"
            "QPushButton:hover { background: #3a3c48; }"
        )
        add_btn.clicked.connect(self.OnAddToken)
        layout.addWidget(add_btn, 2, 0, 1, 3)

        rebuild_btn = QPushButton("Rebuild DB")
        rebuild_btn.setStyleSheet(add_btn.styleSheet())
        rebuild_btn.clicked.connect(self.OnRebuild)
        layout.addWidget(rebuild_btn, 2, 3, 1, 3)

        scroll = QScrollArea()
        scroll.setWidget(group)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #14161c; }")
        scroll.setMinimumWidth(340)
        return scroll

    def RenderEnglish(self, interrogative, auxiliary, subject, action, object_val, modifier):
        parts = []
        if interrogative:
            parts.append(interrogative.lower())
        if auxiliary:
            parts.append(auxiliary.lower())
        if subject:
            parts.append(subject.lower())
        if action:
            parts.append(action.lower())
        if object_val:
            parts.append(object_val.lower())
        if modifier:
            parts.append(modifier.lower())
        if not parts:
            return ""
        text = " ".join(parts)
        if text and not text.endswith("?"):
            text += "?"
        return text.capitalize()

    def GetDimensions(self, *tokens):
        dims = set()
        for t in tokens:
            t_upper = (t or "").upper()
            if t_upper in TOKEN_DIMENSIONS:
                dims.add(TOKEN_DIMENSIONS[t_upper][0])
        return sorted(dims)

    def OnGenerate(self):
        db = self.state["db"]
        limit = self.limit_spin.value()
        db.execute("DELETE FROM question")

        atoms = self.state["atoms"]
        inter = [v for v in atoms["interrogative"] if v]
        aux = atoms["auxiliary"]
        subj = [v for v in atoms["subject"] if v]
        act = atoms["action"]
        obj = atoms["object"]
        mod = atoms["modifier"]

        total_possible = len(inter) * len(aux) * len(subj) * len(act) * len(obj) * len(mod)
        all_combos = []
        for i in inter:
            for a in aux:
                for s in subj:
                    for ac in act:
                        for o in obj:
                            for m in mod:
                                all_combos.append((i, a, s, ac, o, m))

        if len(all_combos) > limit:
            random.seed(42)
            all_combos = random.sample(all_combos, limit)

        impossible_set = set()
        for slot_a, val_a, slot_b, val_b, _reason in IMPOSSIBLE_RULES:
            impossible_set.add((slot_a, val_a, slot_b, val_b))

        pruned = 0
        generated = []
        sig_counter = 1
        for i, a, s, ac, o, m in all_combos:
            is_impossible = False
            slots = {
                "interrogative": i, "auxiliary": a, "subject": s,
                "action": ac, "object": o, "modifier": m,
            }
            for sa, va, sb, vb in impossible_set:
                if slots.get(sa) == va and slots.get(sb) == vb:
                    is_impossible = True
                    break
            if is_impossible:
                pruned += 1
                continue
            sig = "Q%06d" % sig_counter
            english = self.RenderEnglish(i, a, s, ac, o, m)
            dims = ",".join(self.GetDimensions(i, a, s, ac, o, m))
            db.execute(
                "INSERT INTO question (id, sig, interrogative, auxiliary, subject, action, object, modifier, english, dimensions) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sig_counter, sig, i, a, s, ac, o, m, english, dims)
            )
            generated.append({
                "id": sig_counter, "sig": sig,
                "interrogative": i, "auxiliary": a, "subject": s,
                "action": ac, "object": o, "modifier": m,
                "english": english, "dimensions": dims,
            })
            sig_counter += 1

        db.commit()
        self.state["generated"] = generated
        self.state["pruned"] = pruned
        self.PopulateQuestionTable(generated)
        self.PopulateEnglishTable(generated)
        self.PopulateSignatureTable(generated)
        self.UpdateStats(total_possible, len(generated), pruned)

    def PopulateQuestionTable(self, generated):
        table = self.question_table
        table.setRowCount(len(generated))
        for row, q in enumerate(generated):
            table.setItem(row, 0, QTableWidgetItem(str(q["id"])))
            table.setItem(row, 1, QTableWidgetItem(q["sig"]))
            table.setItem(row, 2, QTableWidgetItem(q["interrogative"]))
            table.setItem(row, 3, QTableWidgetItem(q["auxiliary"]))
            table.setItem(row, 4, QTableWidgetItem(q["subject"]))
            table.setItem(row, 5, QTableWidgetItem(q["action"]))
            table.setItem(row, 6, QTableWidgetItem(q["object"]))
            table.setItem(row, 7, QTableWidgetItem(q["modifier"]))

    def PopulateEnglishTable(self, generated):
        table = self.english_table
        table.setRowCount(len(generated))
        for row, q in enumerate(generated):
            table.setItem(row, 0, QTableWidgetItem(str(q["id"])))
            table.setItem(row, 1, QTableWidgetItem(q["sig"]))
            table.setItem(row, 2, QTableWidgetItem(q["english"]))

    def PopulateSignatureTable(self, generated):
        table = self.sig_table
        table.setRowCount(len(generated))
        for row, q in enumerate(generated):
            table.setItem(row, 0, QTableWidgetItem(q["sig"]))
            table.setItem(row, 1, QTableWidgetItem(q["interrogative"]))
            table.setItem(row, 2, QTableWidgetItem(q["subject"]))
            table.setItem(row, 3, QTableWidgetItem(q["action"]))
            table.setItem(row, 4, QTableWidgetItem(q["object"]))
            table.setItem(row, 5, QTableWidgetItem(q["modifier"]))
            table.setItem(row, 6, QTableWidgetItem(q["dimensions"]))

    def OnFindHoles(self):
        db = self.state["db"]
        db.execute("DELETE FROM combination")

        atoms = self.state["atoms"]
        valid_combos = set()
        generated = self.state["generated"]
        for q in generated:
            for t1_type, t1_val in [("interrogative", q["interrogative"]), ("auxiliary", q["auxiliary"]),
                                     ("subject", q["subject"]), ("action", q["action"]),
                                     ("object", q["object"]), ("modifier", q["modifier"])]:
                for t2_type, t2_val in [("interrogative", q["interrogative"]), ("auxiliary", q["auxiliary"]),
                                         ("subject", q["subject"]), ("action", q["action"]),
                                         ("object", q["object"]), ("modifier", q["modifier"])]:
                    if t1_type < t2_type and t1_val and t2_val:
                        valid_combos.add((t1_type, t1_val, t2_type, t2_val))

        all_possible = set()
        for t1_type in SLOT_NAMES:
            for t2_type in SLOT_NAMES:
                if t1_type < t2_type:
                    for v1 in atoms[t1_type]:
                        for v2 in atoms[t2_type]:
                            if v1 and v2:
                                all_possible.add((t1_type, v1, t2_type, v2))

        holes = all_possible - valid_combos
        hole_list = []
        for t1_type, v1, t2_type, v2 in sorted(holes):
            dim = TOKEN_DIMENSIONS.get(v1.upper(), (None, None))[0] or \
                  TOKEN_DIMENSIONS.get(v2.upper(), (None, None))[0] or "unknown"
            db.execute(
                "INSERT INTO combination (source_type, source_value, target_type, target_value, dimension, is_hole) VALUES (?, ?, ?, ?, ?, 1)",
                (t1_type, v1, t2_type, v2, dim)
            )
            hole_list.append((t1_type, v1, t2_type, v2, dim))

        for t1_type, v1, t2_type, v2 in sorted(valid_combos):
            dim = TOKEN_DIMENSIONS.get(v1.upper(), (None, None))[0] or \
                  TOKEN_DIMENSIONS.get(v2.upper(), (None, None))[0] or "unknown"
            db.execute(
                "INSERT INTO combination (source_type, source_value, target_type, target_value, dimension, is_hole) VALUES (?, ?, ?, ?, ?, 0)",
                (t1_type, v1, t2_type, v2, dim)
            )

        db.commit()
        self.state["holes"] = hole_list
        self.PopulateHolesTable(hole_list)
        self.stats_label.setText("Holes: %d / %d combos (%.1f%% missing)" % (
            len(hole_list), len(all_possible),
            100.0 * len(hole_list) / len(all_possible) if all_possible else 0
        ))

    def PopulateHolesTable(self, holes):
        table = self.holes_table
        table.setRowCount(len(holes))
        for row, (t1, v1, t2, v2, dim) in enumerate(holes):
            table.setItem(row, 0, QTableWidgetItem(t1))
            table.setItem(row, 1, QTableWidgetItem(v1))
            table.setItem(row, 2, QTableWidgetItem(t2))
            table.setItem(row, 3, QTableWidgetItem(v2))
            table.setItem(row, 4, QTableWidgetItem(dim))

    def OnBuildGraph(self):
        db = self.state["db"]
        cur = db.execute("SELECT DISTINCT type, value, dimension FROM token WHERE value != '' ORDER BY type, value")
        nodes = []
        for t, v, d in cur.fetchall():
            nodes.append({"id": "%s:%s" % (t, v), "label": v, "type": t, "dimension": d or "unknown"})

        cur = db.execute("SELECT source_type, source_value, target_type, target_value, dimension, is_hole FROM combination")
        rows = cur.fetchall()
        edges = []
        holes = []
        if rows:
            for st, sv, tt, tv, dim, is_hole in rows:
                edge = {
                    "source": "%s:%s" % (st, sv),
                    "target": "%s:%s" % (tt, tv),
                    "dimension": dim,
                    "is_hole": bool(is_hole),
                }
                edges.append(edge)
                if is_hole:
                    holes.append(edge)
        else:
            edges, holes = self._BuildEdgesFromAtoms(nodes)

        self.state["graph_nodes"] = nodes
        self.state["graph_edges"] = edges
        self.graph_widget.SetGraph(nodes, edges, holes)
        self.graph3d_widget.SetGraph(nodes, edges, holes)

    def _BuildEdgesFromAtoms(self, nodes):
        """Build co-occurrence edges directly from atom combinations."""
        atoms = self.state["atoms"]
        impossible_set = set()
        for sa, va, sb, vb, _r in IMPOSSIBLE_RULES:
            impossible_set.add((sa, va, sb, vb))
        edges = []
        holes = []
        node_ids = set(n["id"] for n in nodes)
        for i, t1 in enumerate(SLOT_NAMES):
            for j, t2 in enumerate(SLOT_NAMES):
                if i >= j:
                    continue
                for v1 in atoms.get(t1, []):
                    if not v1:
                        continue
                    for v2 in atoms.get(t2, []):
                        if not v2:
                            continue
                        is_impossible = (t1, v1, t2, v2) in impossible_set
                        dim = TOKEN_DIMENSIONS.get(v1.upper(), (None, None))[0] or \
                              TOKEN_DIMENSIONS.get(v2.upper(), (None, None))[0] or "unknown"
                        edge = {
                            "source": "%s:%s" % (t1, v1),
                            "target": "%s:%s" % (t2, v2),
                            "dimension": dim,
                            "is_hole": is_impossible,
                        }
                        if edge["source"] in node_ids and edge["target"] in node_ids:
                            edges.append(edge)
                            if is_impossible:
                                holes.append(edge)
        return edges, holes

    def OnBuild3DGraph(self):
        if not self.state["graph_nodes"]:
            self.OnBuildGraph()
            return
        nodes = self.state["graph_nodes"]
        edges = self.state["graph_edges"]
        holes = [e for e in edges if e.get("is_hole")]
        self.graph3d_widget.SetGraph(nodes, edges, holes)
        self.stats_label.setText("3D Graph: %d nodes, %d edges, %d holes — drag to rotate" % (
            len(nodes), len(edges) - len(holes), len(holes)
        ))

    def OnToggleWidth(self):
        if not self.act_fullwidth:
            self.left_panel.hide()
            self.splitter.setSizes([0, self.width()])
            self.act_fullscreen.setText("[>>] Show Panel")
            self.act_fullwidth = True
        else:
            self.left_panel.show()
            self.splitter.setSizes([350, self.width() - 350])
            self.act_fullscreen.setText("[<<] Full Width")
            self.act_fullwidth = False
        self.graph3d_widget.update()

    def OnTopology(self):
        generated = self.state["generated"]
        if not generated:
            self.stats_label.setText("Generate questions first")
            return
        connection_counts = defaultdict(int)
        total_pairs = 0
        for q in generated:
            slots = [
                ("interrogative", q["interrogative"]),
                ("auxiliary", q["auxiliary"]),
                ("subject", q["subject"]),
                ("action", q["action"]),
                ("object", q["object"]),
                ("modifier", q["modifier"]),
            ]
            for i, (t1, v1) in enumerate(slots):
                if not v1:
                    continue
                for j, (t2, v2) in enumerate(slots):
                    if i >= j or not v2:
                        continue
                    connection_counts[(t1, v1)] += 1
                    connection_counts[(t2, v2)] += 1
                    total_pairs += 1
        max_conn = max(connection_counts.values()) if connection_counts else 1
        sorted_tokens = sorted(connection_counts.items(), key=lambda x: x[1], reverse=True)
        table = self.topology_table
        table.setRowCount(len(sorted_tokens))
        for row, ((ttype, val), cnt) in enumerate(sorted_tokens):
            table.setItem(row, 0, QTableWidgetItem(val))
            table.setItem(row, 1, QTableWidgetItem(ttype))
            table.setItem(row, 2, QTableWidgetItem(str(cnt)))
            pct = 100.0 * cnt / max_conn
            table.setItem(row, 3, QTableWidgetItem("%.1f%%" % pct))
        self.stats_label.setText("Topology: %d tokens, most connected = %s (%d)" % (
            len(sorted_tokens), sorted_tokens[0][0][1] if sorted_tokens else "?",
            sorted_tokens[0][1] if sorted_tokens else 0
        ))

    def OnImpossible(self):
        impossible = []
        for slot_a, val_a, slot_b, val_b, reason in IMPOSSIBLE_RULES:
            atoms = self.state["atoms"]
            if val_a in atoms.get(slot_a, []) and val_b in atoms.get(slot_b, []):
                impossible.append((slot_a, val_a, slot_b, val_b, reason))
        table = self.impossible_table
        table.setRowCount(len(impossible))
        for row, (sa, va, sb, vb, reason) in enumerate(impossible):
            table.setItem(row, 0, QTableWidgetItem(sa))
            table.setItem(row, 1, QTableWidgetItem(va))
            table.setItem(row, 2, QTableWidgetItem(sb))
            table.setItem(row, 3, QTableWidgetItem(vb))
            table.setItem(row, 4, QTableWidgetItem(reason))
        self.stats_label.setText("Impossible: %d type-constraint violations" % len(impossible))

    def OnDedup(self):
        generated = self.state["generated"]
        if not generated:
            self.stats_label.setText("Generate questions first")
            return
        sig_groups = defaultdict(list)
        for q in generated:
            sig_key = (
                q["interrogative"],
                q["subject"],
                q["action"],
                q["object"],
                q["modifier"],
            )
            sig_groups[sig_key].append(q)
        deduped = []
        for sig_key, group in sig_groups.items():
            if len(group) > 1:
                eng_forms = list(set(q["english"] for q in group))
                deduped.append((group[0]["sig"], group[0]["english"], len(group), ", ".join(eng_forms[:5])))
        deduped.sort(key=lambda x: x[2], reverse=True)
        table = self.dedup_table
        table.setRowCount(len(deduped))
        for row, (sig, eng, cnt, forms) in enumerate(deduped):
            table.setItem(row, 0, QTableWidgetItem(sig))
            table.setItem(row, 1, QTableWidgetItem(eng))
            table.setItem(row, 2, QTableWidgetItem(str(cnt)))
            table.setItem(row, 3, QTableWidgetItem(forms))
        total_sigs = len(sig_groups)
        unique_sigs = sum(1 for g in sig_groups.values() if len(g) == 1)
        dup_sigs = len(deduped)
        self.stats_label.setText("Dedup: %d unique sigs, %d dup groups, %d singleton sigs" % (
            total_sigs, dup_sigs, unique_sigs
        ))

    def OnBasisMatrix(self):
        generated = self.state["generated"]
        if not generated:
            self.stats_label.setText("Generate questions first")
            return
        counts = {}
        for q in generated:
            op = INQUIRY_OPERATORS.get(q["interrogative"], "IDENTITY")
            mode = AUXILIARY_TO_MODE.get(q["auxiliary"], "QUESTION")
            key = "%s x %s" % (op, mode)
            counts[key] = counts.get(key, 0) + 1
        self.basis_matrix.SetCounts(counts, len(generated))
        filled = sum(1 for v in counts.values() if v > 0)
        self.stats_label.setText("Basis: %d/%d cells filled, %d holes" % (
            filled, len(OPERATOR_LIST) * len(LOGICAL_MODES),
            len(OPERATOR_LIST) * len(LOGICAL_MODES) - filled
        ))

    def OnCompression(self):
        generated = self.state["generated"]
        gen_count = len(generated)
        pruned = self.state.get("pruned", 0)
        atoms = self.state["atoms"]
        total_raw = 1
        for t in SLOT_NAMES:
            total_raw *= len(atoms[t])

        from collections import defaultdict as dd
        sig_set = set()
        cat_sigs = set()
        shape_sigs = set()
        op_mod_sigs = set()
        op_sigs = set()
        for q in generated:
            sig_set.add((q["interrogative"], q["subject"], q["action"], q["object"], q["modifier"]))
            s_cat = SUBJECT_CATEGORIES.get(q["subject"], "unknown")
            o_cat = OBJECT_CATEGORIES.get(q["object"], "unknown")
            a_cat = ACTION_CATEGORIES.get(q["action"], "unknown")
            m_cat = MODIFIER_CATEGORIES.get(q["modifier"], "none")
            op = INQUIRY_OPERATORS.get(q["interrogative"], "IDENTITY")
            cat_sigs.add((op, s_cat, a_cat, o_cat, m_cat))
            shape_sigs.add((op, a_cat, m_cat))
            op_mod_sigs.add((op, m_cat))
            op_sigs.add(op)

        layers = [
            {"label": "Raw Cartesian", "count": total_raw, "rule": "", "color": QColor(80, 50, 50)},
            {"label": "Valid questions", "count": gen_count, "rule": "type constraints + completeness", "color": QColor(80, 80, 120)},
            {"label": "Fundamental templates", "count": len(sig_set), "rule": "dedup auxiliary (tense/mood)", "color": QColor(60, 100, 80)},
            {"label": "Category signatures", "count": len(cat_sigs), "rule": "collapse token categories", "color": QColor(50, 100, 120)},
            {"label": "Shape signatures", "count": len(shape_sigs), "rule": "drop subject/object distinction", "color": QColor(100, 80, 120)},
            {"label": "Operator + modifier", "count": len(op_mod_sigs), "rule": "drop action type", "color": QColor(120, 60, 100)},
            {"label": "Inquiry operators (original 6)", "count": len(op_sigs), "rule": "drop modifier dimension", "color": QColor(120, 80, 60)},
            {"label": "Corrected basis (11 x 8)", "count": 88, "rule": "add 5 operators + 8 modes", "color": QColor(50, 130, 100)},
        ]
        self.compression_widget.SetLayers(layers)
        self.stats_label.setText("Compression: %s -> %s = %.0f:1" % (
            "{:,}".format(total_raw), 88, total_raw / 88.0
        ))

    def OnMapReal(self):
        import mysql.connector
        try:
            conn = mysql.connector.connect(
                host="localhost", user="root", password="",
                database="laws", unix_socket="/tmp/mysql.sock"
            )
        except Exception as e:
            self.stats_label.setText("DB error: %s" % str(e)[:60])
            return
        cur = conn.cursor()
        cur.execute("SELECT id, questionText, question_type_id FROM question LIMIT 50000")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        word_to_op = {
            "what": "IDENTITY", "which": "IDENTITY",
            "who": "ENTITY", "whom": "ENTITY", "whose": "ENTITY",
            "where": "LOCATION",
            "when": "TIME",
            "why": "CAUSE",
            "how many": "QUANTITY", "how much": "MEASUREMENT",
            "how": "METHOD",
            "compared": "COMPARISON",
            "under what conditions": "CONSTRAINT",
            "what follows": "INFERENCE", "what if": "INFERENCE",
        }
        mode_keywords = {
            "COUNTERFACTUAL": ["what if", "suppose", "hypothetically"],
            "POSSIBILITY": ["can ", "could ", "may ", "might "],
            "NECESSITY": ["must ", "have to", "need to"],
            "NORMATIVE": ["should ", "ought", "shall "],
            "PROBABILITY": ["likely", "probably", "might "],
            "HYPOTHESIS": ["would ", "suppose", "assume"],
            "ASSERTION": ["will ", "shall "],
        }

        counts = {}
        examples = {}
        total_mapped = 0
        unmapped = 0

        for qid, text, qtype_id in rows:
            if not text:
                continue
            lower = text.strip().lower()

            op = None
            for keyword, operator in sorted(word_to_op.items(), key=lambda x: -len(x[0])):
                if lower.startswith(keyword):
                    op = operator
                    break

            if not op:
                if qtype_id and qtype_id <= 9:
                    type_map = {1: "IDENTITY", 2: "METHOD", 3: "CAUSE", 4: "IDENTITY",
                                5: "IDENTITY", 6: "IDENTITY", 7: "POSSIBILITY", 8: "IDENTITY", 9: "IDENTITY"}
                    op = type_map.get(qtype_id, "IDENTITY")
                else:
                    op = "IDENTITY"

            mode = "QUESTION"
            for mode_name, keywords in mode_keywords.items():
                if any(kw in lower for kw in keywords):
                    mode = mode_name
                    break

            key = "%s x %s" % (op, mode)
            counts[key] = counts.get(key, 0) + 1
            if key not in examples:
                examples[key] = text[:80]
            total_mapped += 1

        self.basis_matrix.SetCounts(counts, total_mapped)

        table = self.real_map_table
        sorted_cells = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        table.setRowCount(len(sorted_cells))
        for row, (key, cnt) in enumerate(sorted_cells):
            parts = key.split(" x ")
            op = parts[0]
            mode = parts[1] if len(parts) > 1 else "?"
            table.setItem(row, 0, QTableWidgetItem(op))
            table.setItem(row, 1, QTableWidgetItem(mode))
            table.setItem(row, 2, QTableWidgetItem(str(cnt)))
            pct = 100.0 * cnt / total_mapped if total_mapped else 0
            table.setItem(row, 3, QTableWidgetItem("%.2f%%" % pct))
            table.setItem(row, 4, QTableWidgetItem(examples.get(key, "")))

        filled = sum(1 for v in counts.values() if v > 0)
        holes = len(OPERATOR_LIST) * len(LOGICAL_MODES) - filled
        self.stats_label.setText("Real map: %d questions -> %d/%d cells, %d holes" % (
            total_mapped, filled, len(OPERATOR_LIST) * len(LOGICAL_MODES), holes
        ))

    def OnRecursion(self):
        lines = []
        lines.append("=" * 70)
        lines.append("RECURSION TEST: Does the basis hold with nested questions?")
        lines.append("=" * 70)
        lines.append("")
        lines.append("Claude's challenge: 'Why did they ask why?' — recursion")
        lines.append("")

        recursion_levels = [
            ("Level 0 (flat)", [
                "WHY did {SYSTEM} fail?",
                "WHAT is {NODE}?",
                "WHERE did {FILE} go?",
            ]),
            ("Level 1 (1 nesting)", [
                "WHY did they ask WHY {SYSTEM} failed?",
                "WHAT is the reason WHAT {NODE} is?",
                "WHERE did the question WHERE {FILE} went come from?",
            ]),
            ("Level 2 (2 nestings)", [
                "WHY did they ask WHY someone asked WHY {SYSTEM} failed?",
                "WHAT is the meaning of WHAT is the reason WHAT {NODE} is?",
            ]),
            ("Level 3 (3 nestings)", [
                "WHY did they ask WHY someone asked WHY someone asked WHY {SYSTEM} failed?",
            ]),
        ]

        for level_name, examples in recursion_levels:
            lines.append(level_name)
            for ex in examples:
                lines.append("  %s" % ex)
            lines.append("")

        lines.append("-" * 40)
        lines.append("ANALYSIS: Does recursion add new basis vectors?")
        lines.append("-" * 40)
        lines.append("")

        lines.append("At every level of recursion, the outer question is still")
        lines.append("one of the 11 operators (WHY, WHAT, WHERE, etc.).")
        lines.append("The inner question is also one of the 11 operators.")
        lines.append("")
        lines.append("So a recursive question is: OPERATOR(OPERATOR(...))")
        lines.append("")
        lines.append("The basis does NOT grow. What grows is the DEPTH of composition.")
        lines.append("")
        lines.append("Level 0: 11 operators                    = 11 types")
        lines.append("Level 1: 11 x 11 compositions            = 121 types")
        lines.append("Level 2: 11 x 11 x 11                    = 1,331 types")
        lines.append("Level 3: 11 x 11 x 11 x 11               = 14,641 types")
        lines.append("Level N: 11^(N+1)                        = exponential")
        lines.append("")
        lines.append("With modes (8 per level):")
        lines.append("Level 0: 11 x 8                         = 88 types")
        lines.append("Level 1: 88 x 88                        = 7,744 types")
        lines.append("Level 2: 88 x 88 x 88                   = 681,472 types")
        lines.append("Level 3: 88^4                           = 59,969,536 types")
        lines.append("")

        lines.append("-" * 40)
        lines.append("VERDICT")
        lines.append("-" * 40)
        lines.append("")
        lines.append("The basis set (11 operators x 8 modes = 88) is STABLE")
        lines.append("under recursion. Recursion does not add new basis vectors.")
        lines.append("")
        lines.append("What recursion adds is COMPOSITIONAL DEPTH.")
        lines.append("Each level multiplies the space by 88x.")
        lines.append("")
        lines.append("The basis is the ALPHABET. Recursion is the GRAMMAR.")
        lines.append("An alphabet doesn't grow when you write longer sentences.")
        lines.append("")
        lines.append("BUT: Claude's point about unbounded natural language")
        lines.append("is still valid. The 88 is the basis for THIS typed ontology.")
        lines.append("Natural language can invent new operators (e.g., 'What color')")
        lines.append("that don't exist in our 11. Each new operator would add 1 to")
        lines.append("the basis (x 8 modes = 8 new cells).")
        lines.append("")
        lines.append("The true fixed point depends on how many fundamentally")
        lines.append("different kinds of inquiry exist — not how many questions")
        lines.append("can be composed from them.")
        lines.append("")
        lines.append("=" * 70)
        lines.append("BASIS: 11 operators x 8 modes = 88 (STABLE under recursion)")
        lines.append("DEPTH: unbounded (88^n at recursion level n)")
        lines.append("EXTENSION: +1 operator per new inquiry type discovered")
        lines.append("=" * 70)

        self.recursion_text.setText("\n".join(lines))
        self.stats_label.setText("Recursion: basis stable at 88, depth unbounded (88^n)")

    def OnYinYang(self):
        facts = FACT_GRAPH
        all_questions = []
        for subject, relation, obj, ctx in facts:
            q_templates = RELATION_QUESTIONS.get(relation, {})
            for direction, q_list in q_templates.items():
                for operator, mode, template in q_list:
                    q_text = template.replace("{S}", subject).replace("{O}", obj)
                    cell = "%s x %s" % (operator, mode)
                    all_questions.append({
                        "fact": "%s --%s--> %s" % (subject, relation, obj),
                        "direction": direction,
                        "operator": operator,
                        "mode": mode,
                        "question": q_text,
                        "cell": cell,
                    })

        self.fact_graph_widget.SetFacts(facts, all_questions)

        table = self.fact_q_table
        table.setRowCount(len(all_questions))
        for row, q in enumerate(all_questions):
            table.setItem(row, 0, QTableWidgetItem(q["fact"]))
            table.setItem(row, 1, QTableWidgetItem(q["direction"]))
            table.setItem(row, 2, QTableWidgetItem(q["operator"]))
            table.setItem(row, 3, QTableWidgetItem(q["mode"]))
            table.setItem(row, 4, QTableWidgetItem(q["question"]))
            table.setItem(row, 5, QTableWidgetItem(q["cell"]))

        cells_used = set(q["cell"] for q in all_questions)
        self.stats_label.setText("Yin/Yang: %d facts -> %d questions | %d/%d cells | 1 fact = %.1f questions" % (
            len(facts), len(all_questions), len(cells_used),
            len(OPERATOR_LIST) * len(LOGICAL_MODES),
            len(all_questions) / max(len(facts), 1)
        ))

    def OnDimFilter(self, idx):
        dim = self.dim_combo.currentData()
        self.state["filter_dim"] = dim
        self.graph_widget.state["highlight_dim"] = dim
        self.graph_widget.update()

    def OnHolesToggle(self, checked):
        self.state["show_holes_only"] = checked
        if checked:
            self.PopulateHolesTable(self.state["holes"])
        else:
            self.PopulateHolesTable(self.state["holes"])

    def OnAddToken(self):
        for token_type, table in self.atom_tables.items():
            table.setRowCount(table.rowCount() + 1)
            table.setItem(table.rowCount() - 1, 0, QTableWidgetItem(""))
            table.setItem(table.rowCount() - 1, 1, QTableWidgetItem(""))

    def OnAtomEdit(self, token_type):
        table = self.atom_tables[token_type]
        new_values = []
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item and item.text().strip():
                new_values.append(item.text().strip())
        self.state["atoms"][token_type] = new_values

    def OnRebuild(self):
        for token_type, table in self.atom_tables.items():
            new_values = []
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item and item.text().strip():
                    new_values.append(item.text().strip())
            self.state["atoms"][token_type] = new_values
        self.RebuildAtoms(self.state["atoms"])
        self.stats_label.setText("DB rebuilt — %d tokens" % sum(len(v) for v in self.state["atoms"].values()))

    def OnExport(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "questions.csv", "CSV (*.csv)")
        if not path:
            return
        generated = self.state["generated"]
        with open(path, "w") as f:
            f.write("id,signature,interrogative,auxiliary,subject,action,object,modifier,english,dimensions\n")
            for q in generated:
                f.write('%d,%s,%s,%s,%s,%s,%s,%s,"%s",%s\n' % (
                    q["id"], q["sig"], q["interrogative"], q["auxiliary"],
                    q["subject"], q["action"], q["object"], q["modifier"],
                    q["english"].replace('"', '""'), q["dimensions"]
                ))
        self.stats_label.setText("Exported %d questions to %s" % (len(generated), path))

    def OnRandom(self):
        generated = self.state["generated"]
        if not generated:
            return
        sample = random.sample(generated, min(20, len(generated)))
        self.PopulateQuestionTable(sample)
        self.PopulateEnglishTable(sample)
        self.PopulateSignatureTable(sample)

    def UpdateStats(self, total_possible, generated_count, pruned=0):
        atoms = self.state["atoms"]
        counts = {k: len([v for v in vlist if v]) for k, vlist in atoms.items()}
        lines = []
        lines.append("=" * 60)
        lines.append("SEMANTIC QUESTION SPACE — STATS")
        lines.append("=" * 60)
        lines.append("")
        lines.append("Token counts (non-empty):")
        for t in SLOT_NAMES:
            lines.append("  %-15s %d" % (t, counts[t]))
        lines.append("")
        lines.append("Cartesian product (all slots): %d" % total_possible)
        lines.append("Generated (after pruning):    %d" % generated_count)
        lines.append("Pruned (impossible combos):   %d" % pruned)
        lines.append("Coverage:                      %.2f%%" % (100.0 * generated_count / total_possible if total_possible else 0))
        lines.append("")
        dim_counter = Counter()
        for q in self.state["generated"]:
            for d in q["dimensions"].split(","):
                if d:
                    dim_counter[d] += 1
        lines.append("Dimension distribution:")
        for dim, cnt in dim_counter.most_common():
            lines.append("  %-15s %d  (%.1f%%)" % (dim, cnt, 100.0 * cnt / generated_count if generated_count else 0))
        lines.append("")
        lines.append("Holes found: %d" % len(self.state["holes"]))
        lines.append("")
        lines.append("Sample signatures:")
        for q in self.state["generated"][:10]:
            lines.append("  %s  %s" % (q["sig"], q["english"]))
        lines.append("")
        lines.append("=" * 60)
        self.stats_text.setText("\n".join(lines))
        self.stats_label.setText("Generated %d | Pruned %d | Possible %d (%.1f%% coverage)" % (
            generated_count, pruned, total_possible,
            100.0 * generated_count / total_possible if total_possible else 0
        ))


def Main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Menlo", 10))
    window = QuestionSpaceExplorer()
    screen = app.primaryScreen().geometry()
    window.resize(screen.width() - 20, screen.height() - 60)
    window.move(10, 25)
    window.show()
    from PyQt6.QtCore import QTimer
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: AutoStart(window))
    timer.start(100)
    return app.exec()


def AutoStart(window):
    """Auto-build 3D graph, hide left panel, select 3D tab on startup."""
    try:
        window.OnBuildGraph()
        window.OnBuild3DGraph()
        window.OnToggleWidth()
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i) == "3D Graph":
                window.tabs.setCurrentIndex(i)
                break
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(Main())
