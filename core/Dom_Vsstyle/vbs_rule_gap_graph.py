#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_rule_gap_graph.py>][@domain<Vbs_Code_Verifiation>][@role<gap_graph>][@auth<cascade>][@date<2026-06-26>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<gap_graph>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
GapGraph: focuses only on the weak and missing rules.
Shows each gap rule, its closest token match, the score, and why the match is weak.
This is the actionable view — these are the rules that need tokens created.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vbs_rule_engine import RuleEngine

CANVAS_W = 1200
CANVAS_H = 800


class GapGraph:
    """Gap graph: weak and missing rules with their closest token matches."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "engine": None,
            "root": None,
            "canvas": None,
            "tooltip": None,
            "weak": [],
            "missing": [],
            "layout": [],
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
            self.state["weak"] = a[1]["weak"]
            self.state["missing"] = a[1]["missing"]
            return (1, {
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
            root.title("VBStyle Rule Gap Graph")
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
            self._build_layout()
            self._draw()
            canvas.bind("<Motion>", self._on_motion)
            canvas.bind("<Leave>", self._on_leave)
            root.mainloop()
            return (1, {"shown": True}, None)
        except Exception as e:
            return (0, None, ("SHOW_ERROR", str(e), 0))

    def _build_layout(self):
        layout = []
        all_gaps = []
        for m in self.state["missing"]:
            all_gaps.append({"type": "MISSING", "rid": m["rid"], "source": m["source"],
                             "text": m["text"], "closest": m.get("closest"), "score": m.get("score", 0.0)})
        for w in self.state["weak"]:
            all_gaps.append({"type": "WEAK", "rid": w["rid"], "source": w["source"],
                             "text": w["text"], "closest": w.get("closest"), "score": w.get("score", 0.0)})
        y = 100
        row_h = 90
        for gap in all_gaps:
            rule_x = 80
            token_x = 700
            layout.append({
                "gap": gap,
                "rule_pos": (rule_x, y + 20),
                "token_pos": (token_x, y + 20),
                "bar_pos": (rule_x + 120, y + 50),
            })
            y += row_h
        self.state["layout"] = layout

    def _draw(self):
        canvas = self.state["canvas"]
        canvas.delete("all")
        canvas.create_text(10, 10, text="GAP GRAPH", anchor=tk.NW, font=("Helvetica", 16, "bold"))
        canvas.create_text(10, 35, text="Weak: %d  |  Missing: %d  |  Total gaps: %d" % (
            len(self.state["weak"]), len(self.state["missing"]),
            len(self.state["weak"]) + len(self.state["missing"])),
            anchor=tk.NW, font=("Helvetica", 11))
        canvas.create_text(10, 55, text="Orange=Weak (partial match)  Red=Missing (no match)  Bar length=match score",
                           anchor=tk.NW, font=("Helvetica", 9))
        canvas.create_text(80, 75, text="RULE (.md source)", anchor=tk.NW, font=("Helvetica", 10, "bold"))
        canvas.create_text(700, 75, text="CLOSEST TOKEN", anchor=tk.NW, font=("Helvetica", 10, "bold"))
        canvas.create_text(400, 75, text="MATCH SCORE", anchor=tk.NW, font=("Helvetica", 10, "bold"))
        for item in self.state["layout"]:
            gap = item["gap"]
            rx, ry = item["rule_pos"]
            tx, ty = item["token_pos"]
            bx, by = item["bar_pos"]
            if gap["type"] == "MISSING":
                color = "red"
            else:
                color = "orange"
            canvas.create_oval(rx - 5, ry - 5, rx + 5, ry + 5, fill=color, outline=color)
            label = "%s [%s]" % (gap["rid"], gap["source"])
            canvas.create_text(rx + 12, ry - 8, text=label, anchor=tk.NW, font=("Helvetica", 8, "bold"), fill=color)
            canvas.create_text(rx + 12, ry + 4, text=gap["text"][:70], anchor=tk.NW, font=("Helvetica", 7))
            if gap["closest"]:
                canvas.create_oval(tx - 5, ty - 5, tx + 5, ty + 5, fill="blue", outline="blue")
                canvas.create_text(tx + 12, ty - 8, text=gap["closest"], anchor=tk.NW, font=("Helvetica", 8, "bold"))
                eng = self.state["engine"]
                if eng:
                    tok_body = ""
                    for t in eng.state["tokens"]:
                        if t["name"] == gap["closest"]:
                            tok_body = t["body"][:60]
                            break
                    canvas.create_text(tx + 12, ty + 4, text=tok_body, anchor=tk.NW, font=("Helvetica", 7))
                canvas.create_line(rx + 5, ry, tx - 5, ty, fill=color, width=1, dash=(3, 3))
                bar_w = int(gap["score"] * 200)
                canvas.create_rectangle(bx, by - 8, bx + 200, by, outline="gray")
                canvas.create_rectangle(bx, by - 8, bx + bar_w, by, fill=color, outline=color)
                canvas.create_text(bx + 210, by - 4, text="%.2f" % gap["score"], anchor=tk.W, font=("Helvetica", 8))
            else:
                canvas.create_text(tx, ty, text="NO MATCH", anchor=tk.W, font=("Helvetica", 8, "bold"), fill="red")
                canvas.create_text(bx, by - 4, text="0.00", anchor=tk.W, font=("Helvetica", 8))
        max_y = len(self.state["layout"]) * 90 + 120
        canvas.configure(scrollregion=(0, 0, CANVAS_W, max_y))

    def _on_motion(self, event):
        canvas = self.state["canvas"]
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        closest = None
        closest_dist = 999
        for item in self.state["layout"]:
            rx, ry = item["rule_pos"]
            d = abs(x - rx) + abs(y - ry)
            if d < closest_dist and d < 20:
                closest_dist = d
                g = item["gap"]
                closest = "%s [%s]\nRule: %s\nClosest: %s (score=%.2f)" % (
                    g["rid"], g["source"], g["text"][:80], g.get("closest", "NONE"), g.get("score", 0.0))
            tx, ty = item["token_pos"]
            d2 = abs(x - tx) + abs(y - ty)
            if d2 < closest_dist and d2 < 20:
                closest_dist = d2
                g = item["gap"]
                closest = "Token: %s\nMatches rule: %s\nScore: %.2f" % (
                    g.get("closest", "NONE"), g["rid"], g.get("score", 0.0))
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
