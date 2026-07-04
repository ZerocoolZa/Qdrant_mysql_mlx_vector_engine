#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_rule_coverage_graph.py>][@domain<Vbs_Code_Verifiation>][@role<coverage_graph>][@auth<cascade>][@date<2026-06-26>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<coverage_graph>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
CoverageGraph: bipartite visualization of .md rules vs rule_tokens.
Left column = 185 extracted rules (green=covered, orange=weak, red=missing).
Right column = 238 canonical tokens (blue).
Edges drawn only for weak and missing to keep the graph readable.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vbs_rule_engine import RuleEngine

CANVAS_W = 1400
CANVAS_H = 900
LEFT_X = 120
RIGHT_X = 1280
DOT_R = 3
Y_START = 80
RULE_SPACING = 4
TOKEN_SPACING = 3


class CoverageGraph:
    """Bipartite coverage graph: rules on left, tokens on right."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "engine": None,
            "root": None,
            "canvas": None,
            "tooltip": None,
            "rules": [],
            "tokens": [],
            "covered": [],
            "weak": [],
            "missing": [],
            "rule_positions": {},
            "token_positions": {},
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
            eng.Run("extract_all", {})
            eng.Run("load_tokens", {})
            a = eng.Run("analyze", {})
            if not a[0]:
                eng.Run("close", {})
                return (0, None, ("ANALYZE_ERROR", a[2], 0))
            self.state["engine"] = eng
            self.state["rules"] = eng.state["extracted"]
            self.state["tokens"] = eng.state["tokens"]
            self.state["covered"] = a[1]["covered"]
            self.state["weak"] = a[1]["weak"]
            self.state["missing"] = a[1]["missing"]
            return (1, {
                "rules": len(self.state["rules"]),
                "tokens": len(self.state["tokens"]),
                "covered": len(self.state["covered"]),
                "weak": len(self.state["weak"]),
                "missing": len(self.state["missing"]),
            }, None)
        except Exception as e:
            return (0, None, ("BUILD_ERROR", str(e), 0))

    def show(self, params=None):
        try:
            r = self.build_data(params)
            if not r[0]:
                return r
            root = tk.Tk()
            root.title("VBStyle Rule Coverage Graph")
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
            self._draw()
            canvas.bind("<Motion>", self._on_motion)
            canvas.bind("<Leave>", self._on_leave)
            root.mainloop()
            return (1, {"shown": True}, None)
        except Exception as e:
            return (0, None, ("SHOW_ERROR", str(e), 0))

    def _draw(self):
        canvas = self.state["canvas"]
        canvas.delete("all")
        rules = self.state["rules"]
        tokens = self.state["tokens"]
        covered_rids = {c["rid"] for c in self.state["covered"]}
        weak_rids = {w["rid"] for w in self.state["weak"]}
        missing_rids = {m["rid"] for m in self.state["missing"]}
        canvas.create_text(10, 10, text="COVERAGE GRAPH", anchor=tk.NW, font=("Helvetica", 16, "bold"))
        canvas.create_text(10, 35, text="Rules: %d  |  Tokens: %d  |  Covered: %d  |  Weak: %d  |  Missing: %d" % (
            len(rules), len(tokens), len(self.state["covered"]), len(self.state["weak"]), len(self.state["missing"])),
            anchor=tk.NW, font=("Helvetica", 11))
        canvas.create_text(10, 55, text="Green=Covered  Orange=Weak  Red=Missing  Blue=Token  (edges only for weak/missing)",
            anchor=tk.NW, font=("Helvetica", 9))
        for i, rule in enumerate(rules):
            y = Y_START + i * RULE_SPACING
            x = LEFT_X
            rid = rule["rid"]
            if rid in covered_rids:
                color = "green"
            elif rid in weak_rids:
                color = "orange"
            elif rid in missing_rids:
                color = "red"
            else:
                color = "gray"
            canvas.create_oval(x - DOT_R, y - DOT_R, x + DOT_R, y + DOT_R, fill=color, outline=color)
            self.state["rule_positions"][rid] = (x, y, rule["text"][:80])
        for i, tok in enumerate(tokens):
            y = Y_START + i * TOKEN_SPACING
            x = RIGHT_X
            canvas.create_oval(x - DOT_R, y - DOT_R, x + DOT_R, y + DOT_R, fill="blue", outline="blue")
            self.state["token_positions"][tok["name"]] = (x, y, tok["body"][:80])
        for w in self.state["weak"]:
            rp = self.state["rule_positions"].get(w["rid"])
            tp = self.state["token_positions"].get(w["closest"])
            if rp and tp:
                canvas.create_line(rp[0], rp[1], tp[0], tp[1], fill="orange", width=1)
        for m in self.state["missing"]:
            rp = self.state["rule_positions"].get(m["rid"])
            if rp:
                canvas.create_text(rp[0] + 8, rp[1], text="X", fill="red", font=("Helvetica", 7, "bold"))
        canvas.create_text(LEFT_X, Y_START - 15, text="RULES (%d)" % len(rules),
                           anchor=tk.S, font=("Helvetica", 10, "bold"))
        canvas.create_text(RIGHT_X, Y_START - 15, text="TOKENS (%d)" % len(tokens),
                           anchor=tk.S, font=("Helvetica", 10, "bold"))
        max_h = max(len(rules) * RULE_SPACING, len(tokens) * TOKEN_SPACING) + Y_START + 50
        canvas.configure(scrollregion=(0, 0, CANVAS_W, max_h))

    def _on_motion(self, event):
        canvas = self.state["canvas"]
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        closest = None
        closest_dist = 999
        for rid, (rx, ry, rtext) in self.state["rule_positions"].items():
            d = abs(x - rx) + abs(y - ry)
            if d < closest_dist and d < 15:
                closest_dist = d
                closest = "%s: %s" % (rid, rtext)
        for name, (tx, ty, tbody) in self.state["token_positions"].items():
            d = abs(x - tx) + abs(y - ty)
            if d < closest_dist and d < 15:
                closest_dist = d
                closest = "%s: %s" % (name, tbody)
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
