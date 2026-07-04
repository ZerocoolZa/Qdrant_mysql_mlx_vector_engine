#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_rule_cluster_graph.py>][@domain<Vbs_Code_Verifiation>][@role<cluster_graph>][@auth<cascade>][@date<2026-06-26>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<cluster_graph>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
ClusterGraph: tokens grouped by shared keywords.
Shows which tokens are conceptually related, potential duplicates,
and isolated concepts with no neighbors.

Nodes = tokens. Edges = shared distinctive keywords (score >= threshold).
Clusters naturally form by concept proximity.
"""

import os
import sys
import math
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vbs_rule_engine import RuleEngine

CANVAS_W = 1200
CANVAS_H = 800
EDGE_THRESHOLD = 0.5


class ClusterGraph:
    """Concept cluster graph: tokens connected by shared keywords."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "engine": None,
            "root": None,
            "canvas": None,
            "tooltip": None,
            "tokens": [],
            "edges": [],
            "positions": {},
            "isolated": [],
        }

    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "show": self.show,
            "build_data": self.build_data,
            "close": self.close,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))

    def build_data(self, params=None):
        try:
            eng = RuleEngine()
            r = eng.Run("open", {})
            if not r[0]:
                return (0, None, ("OPEN_ERROR", r[2], 0))
            eng.Run("load_tokens", {})
            tokens = eng.state["tokens"]
            self.state["engine"] = eng
            self.state["tokens"] = tokens
            edges = []
            for i in range(len(tokens)):
                for j in range(i + 1, len(tokens)):
                    sig_a = tokens[i]["signature"]
                    sig_b = tokens[j]["signature"]
                    if not sig_a or not sig_b:
                        continue
                    overlap = sig_a & sig_b
                    if not overlap:
                        continue
                    denom = max(1, min(len(sig_a), len(sig_b)))
                    score = len(overlap) / denom
                    distinctive = {w for w in overlap if len(w) >= 5}
                    if score >= EDGE_THRESHOLD and len(distinctive) >= 1:
                        edges.append({
                            "a": tokens[i]["name"],
                            "b": tokens[j]["name"],
                            "score": round(score, 2),
                            "shared": sorted(distinctive)[:5],
                        })
            self.state["edges"] = edges
            connected = set()
            for e in edges:
                connected.add(e["a"])
                connected.add(e["b"])
            self.state["isolated"] = [t["name"] for t in tokens if t["name"] not in connected]
            return (1, {
                "tokens": len(tokens),
                "edges": len(edges),
                "isolated": len(self.state["isolated"]),
            }, None)
        except Exception as e:
            return (0, None, ("BUILD_ERROR", str(e), 0))

    def show(self, params=None):
        try:
            r = self.build_data(params)
            if not r[0]:
                return r
            root = tk.Tk()
            root.title("VBStyle Rule Concept Cluster Graph")
            self.state["root"] = root
            frame = ttk.Frame(root)
            frame.pack(fill=tk.BOTH, expand=True)
            canvas = tk.Canvas(frame, width=CANVAS_W, height=CANVAS_H, bg="white", highlightthickness=0)
            hbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=canvas.xview)
            vbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
            canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
            hbar.pack(side=tk.BOTTOM, fill=tk.X)
            vbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.state["canvas"] = canvas
            self.state["tooltip"] = tk.Label(root, text="", relief=tk.SOLID, borderwidth=1,
                                             bg="lightyellow", font=("Helvetica", 9))
            self._layout_circular()
            self._draw()
            canvas.bind("<Motion>", self._on_motion)
            canvas.bind("<Leave>", self._on_leave)
            root.mainloop()
            return (1, {"shown": True}, None)
        except Exception as e:
            return (0, None, ("SHOW_ERROR", str(e), 0))

    def _layout_circular(self):
        tokens = self.state["tokens"]
        n = len(tokens)
        cx = CANVAS_W / 2
        cy = CANVAS_H / 2
        radius = min(CANVAS_W, CANVAS_H) / 2 - 60
        for i, tok in enumerate(tokens):
            angle = 2 * math.pi * i / n - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            self.state["positions"][tok["name"]] = (x, y, tok["category"], tok["body"][:60])

    def _draw(self):
        canvas = self.state["canvas"]
        canvas.delete("all")
        cat_colors = {
            "Forbidden": "red",
            "Architecture": "blue",
            "Method": "green",
            "Naming": "purple",
            "Format": "orange",
            "State": "brown",
            "Database": "darkblue",
            "Workflow": "darkgreen",
            "Meta": "gold",
            "Paths": "gray",
            "FileOps": "pink",
            "Other": "lightgray",
        }
        canvas.create_text(10, 10, text="CONCEPT CLUSTER GRAPH", anchor=tk.NW, font=("Helvetica", 16, "bold"))
        info = "Tokens: %d  |  Edges: %d  |  Isolated: %d" % (
            len(self.state["tokens"]), len(self.state["edges"]), len(self.state["isolated"]))
        canvas.create_text(10, 35, text=info, anchor=tk.NW, font=("Helvetica", 11))
        canvas.create_text(10, 55, text="Edge = shared distinctive keywords (score>=0.5). Color = category.",
                           anchor=tk.NW, font=("Helvetica", 9))
        for e in self.state["edges"]:
            pa = self.state["positions"].get(e["a"])
            pb = self.state["positions"].get(e["b"])
            if pa and pb:
                alpha = min(1.0, e["score"])
                width = max(1, int(alpha * 3))
                canvas.create_line(pa[0], pa[1], pb[0], pb[1], fill="gray", width=width)
        for name, (x, y, cat, body) in self.state["positions"].items():
            color = cat_colors.get(cat, "lightgray")
            r = 4
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline=color)
        canvas.configure(scrollregion=(0, 0, CANVAS_W, CANVAS_H))

    def _on_motion(self, event):
        canvas = self.state["canvas"]
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        closest = None
        closest_dist = 999
        for name, (nx, ny, cat, body) in self.state["positions"].items():
            d = math.sqrt((x - nx) ** 2 + (y - ny) ** 2)
            if d < closest_dist and d < 12:
                closest_dist = d
                closest = "%s [%s]: %s" % (name, cat, body)
        if closest:
            self.state["tooltip"].config(text=closest)
            self.state["tooltip"].place(x=event.x + 10, y=event.y + 10)
        else:
            self.state["tooltip"].place_forget()

    def _on_leave(self, event):
        self.state["tooltip"].place_forget()

    def close(self, params=None):
        try:
            if self.state["engine"]:
                self.state["engine"].Run("close", {})
            if self.state["root"]:
                self.state["root"].destroy()
            return (1, {"closed": True}, None)
        except Exception as e:
            return (0, None, ("CLOSE_ERROR", str(e), 0))

    def read_state(self, params=None):
        return (1, {k: v for k, v in self.state.items()
                    if k not in ("root", "canvas", "engine", "tooltip")}, None)

    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))
