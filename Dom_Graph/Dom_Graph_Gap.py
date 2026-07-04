from Config import Config
#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Gap Graph Viewer rendering what is MISSING from VBStyle domain spec. Tkinter GUI with overlay and missing-only modes. No #[@...] headers. No Run dispatch. No Tuple3 returns. Import before shebang. Has hardcoded EXPECTED_PAIRS, CRUD_ROLES, COVERAGE_AREAS, color values, window geometry. Uses tkinter.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Move import after shebang. Move hardcoded data to Config.py.>]}
"""
Gap Graph Viewer — renders what is MISSING from a VBStyle domain spec.
Third of the three graph tools:
    spec_graph.py  -> "What exists?"
    spec_flow.py   -> "How does it move?"
    gap_graph.py   -> "What's missing?"   <-- this file
The graph is NOT the intelligence. The intelligence is the flow that
reasons over the graph. This viewer makes the holes visible so an AI
reasoning pass (or a human) can drive spec revision.
Two render modes:
    overlay       -- spec graph with missing nodes/edges highlighted in red
    missing-only  -- show only the gaps
Gap detection covers what graph edges alone miss:
    - Missing pairs     (Encrypt<->Decrypt, Split<->Join, ...)
    - Missing CRUD      (Create/Read/Update/Delete closure)
    - Missing coverage  (Error / Validation / Recovery / Detection /
                         Configuration / Metrics / Authority / Dispatch)
"""
import math
import tkinter as tk
from tkinter import ttk
from collections import Counter
# ─── Shared spec data (kept identical to spec_graph.py / spec_flow.py) ───────
# ─── Gap rules (data-driven, not hardcoded to compression) ───────────────────
# Each rule is a name + a checker that returns a list of gap dicts:
#   {"kind": ..., "detail": ..., "severity": "high"|"medium"|"low"}
# Rules reason about MEANING, not just edges -- this is what graph edges miss.
# Opposite-operation pairs. If one side exists, the other must exist AND be
# connected by a PAIRS edge. AI reasoning: "I see Encrypt -- where is Decrypt?"
EXPECTED_PAIRS = [
    ("Compress", "Extract"),
    ("Encrypt",  "Decrypt"),
    ("Split",    "Join"),
    ("Write",    "Strip"),
    ("Read",     "Write"),
]
# CRUD closure. A domain that has Create+Read+Update (Write/Rename/Strip count
# as update) but no Delete is missing a lifecycle step.
# AI reasoning: "I see Compress/Extract/Read/Write -- where is Delete?"
CRUD_ROLES = {
    "create": ["Compress"],
    "read":   ["Read", "List", "Info", "Search"],
    "update": ["Write", "Rename", "Strip"],
    "delete": ["Strip"],  # Strip removes files -- closest to delete
}
# Coverage areas. Graph edges cannot detect these; they require semantic
# reasoning about the domain as a whole.
COVERAGE_AREAS = [
    ("Error Handling",  "INTEGRITY", ["Repair", "Verify"]),
    ("Validation",      "INTEGRITY", ["Verify"]),
    ("Recovery",        "INTEGRITY", ["Repair"]),
    ("Detection",       "INTEGRITY", ["Verify", "Hash"]),
    ("Configuration",   "META",      ["Info"]),
    ("Metrics",         "META",      ["Benchmark", "Info"]),
    ("Authority",       "SECURITY",  ["Encrypt", "Decrypt"]),
    ("Dispatch",        "UTILITY",   ["Batch"]),
]
GAP_COLORS = {
    "high":   "#f38ba8",  # red    -- hard gap, opposite op missing
    "medium": "#fab387",  # orange -- coverage hole
    "low":    "#f9e2af",  # yellow -- weak / isolated
}
GAP_NODE_COLOR   = "#f38ba8"
GAP_EDGE_COLOR   = "#f38ba8"
OK_NODE_COLOR    = "#a6e3a1"
class GapGraph:
    """Visual graph of what is MISSING from a VBStyle domain spec."""
    def __init__(self, root):
        self.root = root
        self.root.title("dom_compression -- Gap Graph (What's Missing?)")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e2e")
        self.nodes = [{"id": n[0], "type": n[1], "dispatch": n[2], "desc": n[3]} for n in Config.GRAPH_CLASSES]
        self.edges = [{"src": e[0], "dst": e[1], "type": e[2]} for e in Config.GRAPH_EDGES]
        self.node_map = {n["id"]: n for n in self.nodes}
        self.node_ids = [n["id"] for n in self.nodes]
        self.mode = "overlay"          # "overlay" | "missing"
        self.selected_gap = None
        self.hover_node = None
        self.node_items = {}
        self.node_positions = {}
        self.active_categories = set(Config.GRAPH_CATEGORIES.keys())
        # Computed gaps (list of gap dicts). Recomputed on demand.
        self.gaps = []
        self.gap_nodes = set()         # node ids that are involved in a gap
        self.gap_edges = set()         # (src, dst) tuples for missing-pair edges
        self.ComputeGaps()
        self.BuildUI()
        self.UpdateLegend()
        self.DrawGraph()
    def ComputeGaps(self):
        self.gaps = []
        self.gap_nodes = set()
        self.gap_edges = set()
        node_ids = set(self.node_ids)
        # 1. Missing opposite pairs.
        #    "I see Encrypt -- where is Decrypt?"
        for a, b in EXPECTED_PAIRS:
            has_a = a in node_ids
            has_b = b in node_ids
            if has_a and not has_b:
                self.gaps.append({
                    "kind": "missing_pair",
                    "detail": f"{a} exists but opposite {b} is missing",
                    "severity": "high",
                    "nodes": [a],
                    "missing": b,
                })
                self.gap_nodes.add(a)
            elif has_b and not has_a:
                self.gaps.append({
                    "kind": "missing_pair",
                    "detail": f"{b} exists but opposite {a} is missing",
                    "severity": "high",
                    "nodes": [b],
                    "missing": a,
                })
                self.gap_nodes.add(b)
            elif has_a and has_b:
                # Both exist -- check they are connected by a PAIRS edge.
                connected = any(
                    ((e["src"] == a and e["dst"] == b) or
                     (e["src"] == b and e["dst"] == a))
                    and e["type"] == "PAIRS"
                    for e in self.edges
                )
                if not connected:
                    self.gaps.append({
                        "kind": "missing_pair_edge",
                        "detail": f"{a} and {b} both exist but no PAIRS edge",
                        "severity": "medium",
                        "nodes": [a, b],
                    })
                    self.gap_nodes.update([a, b])
                    self.gap_edges.add((a, b))
        # 2. CRUD closure.
        #    "I see Create/Read/Update -- where is Delete?"
        present_roles = {}
        for role, members in CRUD_ROLES.items():
            present_roles[role] = [m for m in members if m in node_ids]
        if present_roles["create"] and present_roles["read"] and present_roles["update"] \
                and not present_roles["delete"]:
            self.gaps.append({
                "kind": "missing_crud",
                "detail": "Create/Read/Update present but no Delete operation",
                "severity": "high",
                "nodes": [],
                "missing": "Delete",
            })
        # Weak delete: Strip is the only delete-like op. Flag as low.
        if present_roles["delete"] == ["Strip"]:
            self.gaps.append({
                "kind": "weak_crud",
                "detail": "Delete lifecycle covered only by Strip (file removal), "
                          "no domain-level Delete/Archive-Delete class",
                "severity": "low",
                "nodes": ["Strip"],
                "missing": "DeleteArchive",
            })
            self.gap_nodes.add("Strip")
        # 3. Coverage areas.
        #    Graph looks complete but has no Error Handling / Validation / etc.
        for area, expected_cat, required in COVERAGE_AREAS:
            present = [r for r in required if r in node_ids]
            if not present:
                self.gaps.append({
                    "kind": "missing_coverage",
                    "detail": f"{area} coverage missing -- no {required}",
                    "severity": "medium",
                    "nodes": [],
                    "missing": area,
                })
            elif len(present) < len(required) / 2:
                self.gaps.append({
                    "kind": "weak_coverage",
                    "detail": f"{area} coverage weak -- only {present}",
                    "severity": "low",
                    "nodes": present,
                })
                self.gap_nodes.update(present)
        # 4. Isolated nodes (no edges at all).
        for n in self.nodes:
            nid = n["id"]
            has_edge = any(e["src"] == nid or e["dst"] == nid for e in self.edges)
            if not has_edge:
                self.gaps.append({
                    "kind": "isolated",
                    "detail": f"{nid} has no connections to any other class",
                    "severity": "low",
                    "nodes": [nid],
                })
                self.gap_nodes.add(nid)
        # 5. Duplicate dispatch keys (would collide at runtime).
        dispatches = [n["dispatch"] for n in self.nodes]
        counts = Counter(dispatches)
        for k, v in counts.items():
            if v > 1:
                dups = [n["id"] for n in self.nodes if n["dispatch"] == k]
                self.gaps.append({
                    "kind": "duplicate_dispatch",
                    "detail": f"dispatch key '{k}' shared by {dups}",
                    "severity": "high",
                    "nodes": dups,
                })
                self.gap_nodes.update(dups)
        return (1, None, None)
    def BuildUI(self):
        top = tk.Frame(self.root, bg="#1e1e2e", height=50)
        top.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(top, text="dom_compression -- Gap Graph (What's Missing?)",
                 fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value=self.mode)
        tk.Radiobutton(top, text="Overlay", variable=self.mode_var, value="overlay",
                       command=self.SwitchMode, bg="#1e1e2e", fg="#cdd6f4",
                       selectcolor="#313244", font=("Helvetica", 10)).pack(side=tk.LEFT, padx=15)
        tk.Radiobutton(top, text="Missing-only", variable=self.mode_var, value="missing",
                       command=self.SwitchMode, bg="#1e1e2e", fg="#cdd6f4",
                       selectcolor="#313244", font=("Helvetica", 10)).pack(side=tk.LEFT, padx=5)
        gap_count = len(self.gaps)
        high = sum(1 for g in self.gaps if g["severity"] == "high")
        med = sum(1 for g in self.gaps if g["severity"] == "medium")
        low = sum(1 for g in self.gaps if g["severity"] == "low")
        summary = f"  Gaps={gap_count}  High={high}  Medium={med}  Low={low}"
        tk.Label(top, text=summary, fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 11)).pack(side=tk.LEFT, padx=10)
        tk.Button(top, text="Gap Report", command=self.GapReport,
                  bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(side=tk.RIGHT, padx=5)
        # Category filter
        self.filter_frame = tk.Frame(self.root, bg="#1e1e2e")
        self.filter_frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(self.filter_frame, text="Filter:", fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.cat_vars = {}
        for cat, color in Config.GRAPH_CATEGORIES.items():
            cnt = sum(1 for n in self.nodes if n["type"] == cat)
            var = tk.IntVar(value=1)
            self.cat_vars[cat] = var
            tk.Checkbutton(self.filter_frame, text=f"{cat} ({cnt})", variable=var,
                           bg="#1e1e2e", fg=color, selectcolor="#313244",
                           font=("Helvetica", 9),
                           command=self.OnFilterChange).pack(side=tk.LEFT, padx=3)
        # Main area
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(main, bg="#11111b", highlightthickness=0, cursor="hand2")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        df = tk.Frame(main, bg="#1e1e2e", width=450)
        df.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        df.pack_propagate(False)
        self.detail_label = tk.Label(df, text="Gap Details", fg="#cdd6f4", bg="#1e1e2e",
                                     font=("Helvetica", 13, "bold"))
        self.detail_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        self.detail_text = tk.Text(df, bg="#181825", fg="#cdd6f4", font=("Courier", 10),
                                   wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10,
                                   state=tk.DISABLED)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.legend_frame = tk.Frame(df, bg="#1e1e2e")
        self.legend_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.canvas.bind("<Motion>", self.OnMotion)
        self.canvas.bind("<Button-1>", self.OnClick)
        self.canvas.bind("<Configure>", self.OnResize)
        return (1, None, None)
    def UpdateLegend(self):
        for w in self.legend_frame.winfo_children():
            w.destroy()
        tk.Label(self.legend_frame, text="Legend:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        if self.mode == "overlay":
            tk.Label(self.legend_frame, text="Nodes:", fg="#cdd6f4", bg="#1e1e2e",
                     font=("Helvetica", 9, "bold")).pack(anchor=tk.W)
            for label, color in [("OK (no gap)", OK_NODE_COLOR),
                                 ("GAP (involved in a gap)", GAP_NODE_COLOR)]:
                row = tk.Frame(self.legend_frame, bg="#1e1e2e")
                row.pack(fill=tk.X, pady=1)
                c = tk.Canvas(row, width=12, height=12, bg="#1e1e2e", highlightthickness=0)
                c.pack(side=tk.LEFT)
                c.create_oval(2, 2, 10, 10, fill=color, outline="")
                tk.Label(row, text=f" {label}", fg=color, bg="#1e1e2e",
                         font=("Helvetica", 9)).pack(side=tk.LEFT)
            tk.Label(self.legend_frame, text="", bg="#1e1e2e").pack()
            tk.Label(self.legend_frame, text="Edges:", fg="#cdd6f4", bg="#1e1e2e",
                     font=("Helvetica", 9, "bold")).pack(anchor=tk.W)
            for et, ec in Config.GRAPH_EDGE_COLORS.items():
                row = tk.Frame(self.legend_frame, bg="#1e1e2e")
                row.pack(fill=tk.X, pady=1)
                c = tk.Canvas(row, width=20, height=12, bg="#1e1e2e", highlightthickness=0)
                c.pack(side=tk.LEFT)
                c.create_line(2, 6, 18, 6, fill=ec, width=2)
                tk.Label(row, text=f" {et}", fg=ec, bg="#1e1e2e",
                         font=("Helvetica", 9)).pack(side=tk.LEFT)
            row = tk.Frame(self.legend_frame, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            c = tk.Canvas(row, width=20, height=12, bg="#1e1e2e", highlightthickness=0)
            c.pack(side=tk.LEFT)
            c.create_line(2, 6, 18, 6, fill=GAP_EDGE_COLOR, width=2, dash=(4, 2))
            tk.Label(row, text=" MISSING PAIR", fg=GAP_EDGE_COLOR, bg="#1e1e2e",
                     font=("Helvetica", 9)).pack(side=tk.LEFT)
        else:
            tk.Label(self.legend_frame, text="Gap Severity:", fg="#cdd6f4", bg="#1e1e2e",
                     font=("Helvetica", 9, "bold")).pack(anchor=tk.W)
            for sev, col in GAP_COLORS.items():
                row = tk.Frame(self.legend_frame, bg="#1e1e2e")
                row.pack(fill=tk.X, pady=1)
                c = tk.Canvas(row, width=12, height=12, bg="#1e1e2e", highlightthickness=0)
                c.pack(side=tk.LEFT)
                c.create_oval(2, 2, 10, 10, fill=col, outline="")
                tk.Label(row, text=f" {sev}", fg=col, bg="#1e1e2e",
                         font=("Helvetica", 9)).pack(side=tk.LEFT)
        return (1, None, None)
    def SwitchMode(self):
        self.mode = self.mode_var.get()
        if self.mode == "missing":
            self.filter_frame.pack_forget()
            self.detail_label.config(text="Gap List (missing-only)")
        else:
            self.filter_frame.pack(fill=tk.X, padx=10, pady=2)
            self.detail_label.config(text="Gap Details")
        self.UpdateLegend()
        self.DrawGraph()
        return (1, None, None)
    def OnFilterChange(self):
        self.active_categories = {c for c, v in self.cat_vars.items() if v.get()}
        if self.mode == "overlay":
            self.DrawGraph()
        return (1, None, None)
    def DrawGraph(self):
        if self.mode == "overlay":
            self.DrawOverlay()
        else:
            self.DrawMissingOnly()
        return (1, None, None)
    def LayoutCircle(self, visible):
        positions = {}
        if not visible:
            return (1, positions, None)
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 1400, 900
        cx, cy = w / 2, h / 2
        radius = min(cx, cy) - 120
        cat_nodes = {}
        for n in visible:
            cat_nodes.setdefault(n["type"], []).append(n)
        for ci, cat in enumerate(Config.GRAPH_CATEGORIES):
            if cat not in cat_nodes:
                continue
            ca = 2 * math.pi * ci / len(Config.GRAPH_CATEGORIES) - math.pi / 2
            cx2 = cx + radius * 0.65 * math.cos(ca)
            cy2 = cy + radius * 0.65 * math.sin(ca)
            sr = 50 + len(cat_nodes[cat]) * 12
            for ni, node in enumerate(cat_nodes[cat]):
                sa = ca + (ni - len(cat_nodes[cat]) / 2 + 0.5) * (math.pi / 7)
                positions[node["id"]] = (cx2 + sr * math.cos(sa),
                                         cy2 + sr * math.sin(sa))
        return (1, positions, None)
    def DrawOverlay(self):
        self.canvas.delete("all")
        self.node_items = {}
        visible = [n for n in self.nodes if n["type"] in self.active_categories]
        self.node_positions = self.LayoutCircle(visible)
        if not self.node_positions:
            return (1, None, None)
        # Existing edges (dimmed if not a gap edge)
        for e in self.edges:
            s, d = e["src"], e["dst"]
            if s not in self.node_positions or d not in self.node_positions:
                continue
            if self.node_map[s]["type"] not in self.active_categories:
                continue
            if self.node_map[d]["type"] not in self.active_categories:
                continue
            x1, y1 = self.node_positions[s]
            x2, y2 = self.node_positions[d]
            color = Config.GRAPH_EDGE_COLORS.get(e["type"], "#45475a")
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2,
                                    arrow=tk.LAST, arrowshape=(8, 8, 6))
        # Missing-pair edges (dashed red)
        for (a, b) in self.gap_edges:
            if a in self.node_positions and b in self.node_positions:
                x1, y1 = self.node_positions[a]
                x2, y2 = self.node_positions[b]
                self.canvas.create_line(x1, y1, x2, y2, fill=GAP_EDGE_COLOR,
                                        width=2, dash=(6, 4), arrow=tk.LAST,
                                        arrowshape=(8, 8, 6))
        # Nodes -- gap nodes red, others green-ish by category
        for node in visible:
            nid = node["id"]
            if nid not in self.node_positions:
                continue
            x, y = self.node_positions[nid]
            r = 18
            if nid in self.gap_nodes:
                fill = GAP_NODE_COLOR
                outline = "#f9e2af"
                ow = 3
            else:
                fill = Config.GRAPH_CATEGORIES.get(node["type"], "#6c7086")
                outline = "#cdd6f4"
                ow = 1
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill=fill, outline=outline, width=ow)
            self.node_items[item] = nid
            self.canvas.create_text(x, y + r + 10, text=nid,
                                    fill="#cdd6f4", font=("Helvetica", 8))
    def DrawMissingOnly(self):
        self.canvas.delete("all")
        self.node_items = {}
        if not self.gaps:
            self.canvas.create_text(self.canvas.winfo_width() / 2,
                                    self.canvas.winfo_height() / 2,
                                    text="No gaps detected -- domain looks complete.",
                                    fill="#a6e3a1", font=("Helvetica", 16, "bold"))
            return (1, None, None)
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 1400, 900
        # One row per gap, grouped by severity.
        sev_order = ["high", "medium", "low"]
        sev_gaps = {s: [] for s in sev_order}
        for g in self.gaps:
            sev_gaps[g["severity"]].append(g)
        row_h = 40
        gap_y = 40
        idx = 0
        for sev in sev_order:
            if not sev_gaps[sev]:
                continue
            self.canvas.create_text(20, gap_y - 20,
                                    text=f"{sev.upper()} ({len(sev_gaps[sev])})",
                                    fill=GAP_COLORS[sev], anchor=tk.W,
                                    font=("Helvetica", 12, "bold"))
            for g in sev_gaps[sev]:
                y = gap_y
                box_x = 20
                box_w = w - 40
                item = self.canvas.create_rectangle(box_x, y, box_x + box_w, y + row_h - 4,
                                                    fill=GAP_COLORS[sev], outline="#1e1e2e")
                self.node_items[item] = idx
                label = f"[{g['kind']}] {g['detail']}"
                if len(label) > 90:
                    label = label[:87] + "..."
                self.canvas.create_text(box_x + 10, y + (row_h - 4) / 2,
                                        text=label, fill="#1e1e2e", anchor=tk.W,
                                        font=("Helvetica", 10))
                gap_y += row_h
                idx += 1
            gap_y += 20
    def GetNodeAt(self, x, y):
        items = self.canvas.find_overlapping(x - 5, y - 5, x + 5, y + 5)
        for item in items:
            if item in self.node_items:
                return (1, self.node_items[item], None)
        return (1, None, None)
    def OnMotion(self, event):
        node = self.GetNodeAt(event.x, event.y)
        if node != self.hover_node:
            self.hover_node = node
            self.canvas.configure(cursor="hand2" if node is not None else "arrow")
        return (1, None, None)
    def OnClick(self, event):
        target = self.GetNodeAt(event.x, event.y)
        if target is None:
            return (1, None, None)
        if self.mode == "overlay":
            # target is a node id
            self.ShowNodeGaps(target)
        else:
            # target is a gap index
            self.ShowGapDetail(target)
    def OnResize(self, event):
        self.DrawGraph()
        return (1, None, None)
    def ShowNodeGaps(self, nid):
        node = self.node_map.get(nid, {})
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        info = f"Class:    {nid}\nCategory: {node.get('type', '?')}\nDispatch: {node.get('dispatch', '?')}\n\n"
        related = [g for g in self.gaps if nid in g.get("nodes", [])]
        if related:
            info += f"Gaps involving {nid} ({len(related)}):\n"
            for g in related:
                info += f"  [{g['severity']}] {g['kind']}: {g['detail']}\n"
        else:
            info += "No gaps involve this class.\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def ShowGapDetail(self, idx):
        if idx >= len(self.gaps):
            return (1, None, None)
        g = self.gaps[idx]
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        info = f"Gap #{idx + 1}\nKind:     {g['kind']}\nSeverity: {g['severity']}\n\nDetail:\n  {g['detail']}\n\n"
        if g.get("nodes"):
            info += f"Classes involved: {', '.join(g['nodes'])}\n"
        if g.get("missing"):
            info += f"Missing element:  {g['missing']}\n"
        info += "\nSuggested spec revision:\n"
        info += f"  Add or connect: {g.get('missing', g.get('nodes', ['?']))}\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
    def GapReport(self):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        r = "=== GAP REPORT ===\n\n"
        r += f"Total gaps: {len(self.gaps)}\n"
        for sev in ["high", "medium", "low"]:
            cnt = sum(1 for g in self.gaps if g["severity"] == sev)
            r += f"  {sev}: {cnt}\n"
        r += "\n"
        for sev in ["high", "medium", "low"]:
            sev_gaps = [g for g in self.gaps if g["severity"] == sev]
            if not sev_gaps:
                continue
            r += f"--- {sev.upper()} ({len(sev_gaps)}) ---\n"
            for i, g in enumerate(sev_gaps):
                r += f"  {i + 1}. [{g['kind']}] {g['detail']}\n"
                if g.get("missing"):
                    r += f"     -> add: {g['missing']}\n"
            r += "\n"
        r += "=== COVERAGE CHECKS ===\n"
        for area, _, required in COVERAGE_AREAS:
            present = [x for x in required if x in set(self.node_ids)]
            status = "OK" if present else "MISSING"
            r += f"  {area}: {status} ({present})\n"
        self.detail_text.insert("1.0", r)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))