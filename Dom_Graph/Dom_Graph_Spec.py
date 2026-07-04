from Config import Config
#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Spec Graph Viewer rendering VBStyle domain spec as visual node-edge graph. Tkinter GUI for planning and gap analysis. No #[@...] headers. No Run dispatch. No Tuple3 returns. Import before shebang. Has hardcoded color values and window geometry. Uses tkinter.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Move import after shebang. Move hardcoded colors/geometry to Config.py.>]}
"""
Spec Graph Viewer — renders a VBStyle domain spec as a visual node-edge graph.
Used BEFORE building code, to verify domain coverage and find gaps.
Nodes = planned classes
Edges = relationships between classes
Colors = class category (CRUD, Integrity, Transform, Security, Utility, Meta)
"""
import math
import tkinter as tk
from collections import Counter
class SpecGraph:
    """Visual graph of a VBStyle domain spec — for planning and gap analysis."""
    def __init__(self, root):
        self.root = root
        self.root.title("Dom_Graph — Spec Graph (from DB)")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e2e")
        self.nodes = []
        self.edges = []
        self.node_map = {}
        self.node_positions = {}
        self.selected_node = None
        self.hover_node = None
        self.canvas = None
        self.detail_text = None
        self.node_items = {}
        self.active_categories = set(Config.GRAPH_CATEGORIES.keys())
        self.BuildData()
        self.BuildUI()
        self.LayoutNodes()
    def BuildData(self):
        for name, category, dispatch, desc in Config.GRAPH_CLASSES:
            self.nodes.append({
                "id": name,
                "type": category,
                "dispatch": dispatch,
                "description": desc,
            })
        for src, dst, etype in Config.GRAPH_EDGES:
            self.edges.append({"src": src, "dst": dst, "type": etype})
        self.node_map = {n["id"]: n for n in self.nodes}
        return (1, None, None)
    def BuildUI(self):
        # Top bar
        top = tk.Frame(self.root, bg="#1e1e2e", height=50)
        top.pack(fill=tk.X, padx=10, pady=5)
        title = tk.Label(top, text="Dom_Graph — Spec Graph (from DB)",
                         fg="#cdd6f4", bg="#1e1e2e",
                         font=("Helvetica", 16, "bold"))
        title.pack(side=tk.LEFT)
        info_text = f"  Classes={len(self.nodes)}  Edges={len(self.edges)}  Categories={len(Config.GRAPH_CATEGORIES)}"
        info = tk.Label(top, text=info_text, fg="#94a3b8", bg="#1e1e2e",
                        font=("Helvetica", 11))
        info.pack(side=tk.LEFT, padx=10)
        # Category filter bar
        filter_frame = tk.Frame(self.root, bg="#1e1e2e")
        filter_frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(filter_frame, text="Filter:", fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        for cat, color in Config.GRAPH_CATEGORIES.items():
            count = sum(1 for n in self.nodes if n["type"] == cat)
            var = tk.IntVar(value=1)
            cb = tk.Checkbutton(filter_frame, text=f"{cat} ({count})",
                                variable=var, bg="#1e1e2e", fg=color,
                                selectcolor="#313244", activebackground="#1e1e2e",
                                activeforeground=color, font=("Helvetica", 9),
                                command=lambda v=var, c=cat: self.ToggleFilter(v, c))
            cb.var = var
            cb.pack(side=tk.LEFT, padx=3)
        # Gap analysis button
        gap_btn = tk.Button(filter_frame, text="Gap Analysis",
                            command=self.GapAnalysis,
                            bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                            font=("Helvetica", 10), padx=10)
        gap_btn.pack(side=tk.RIGHT, padx=5)
        # Main area
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(main, bg="#11111b", highlightthickness=0,
                                cursor="hand2")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_frame = tk.Frame(main, bg="#1e1e2e", width=400)
        detail_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        detail_frame.pack_propagate(False)
        detail_label = tk.Label(detail_frame, text="Class Details",
                                fg="#cdd6f4", bg="#1e1e2e",
                                font=("Helvetica", 13, "bold"))
        detail_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        self.detail_text = tk.Text(detail_frame, bg="#181825", fg="#cdd6f4",
                                   font=("Courier", 10), wrap=tk.WORD,
                                   relief=tk.FLAT, padx=10, pady=10,
                                   state=tk.DISABLED)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        # Legend
        legend = tk.Frame(detail_frame, bg="#1e1e2e")
        legend.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Label(legend, text="Categories:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        for cat, color in Config.GRAPH_CATEGORIES.items():
            count = sum(1 for n in self.nodes if n["type"] == cat)
            row = tk.Frame(legend, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            c = tk.Canvas(row, width=12, height=12, bg="#1e1e2e",
                      highlightthickness=0)
            c.pack(side=tk.LEFT)
            c.create_oval(2, 2, 10, 10, fill=color, outline="")
            tk.Label(row, text=f" {cat} ({count})", fg=color, bg="#1e1e2e",
                     font=("Helvetica", 9)).pack(side=tk.LEFT)
        tk.Label(legend, text="", bg="#1e1e2e").pack()
        tk.Label(legend, text="Edge Types:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        for etype, ecolor in Config.GRAPH_EDGE_COLORS.items():
            row = tk.Frame(legend, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            c = tk.Canvas(row, width=20, height=12, bg="#1e1e2e",
                      highlightthickness=0)
            c.pack(side=tk.LEFT)
            c.create_line(2, 6, 18, 6, fill=ecolor, width=2)
            tk.Label(row, text=f" {etype}", fg=ecolor, bg="#1e1e2e",
                     font=("Helvetica", 9)).pack(side=tk.LEFT)
        self.canvas.bind("<Motion>", self.OnMotion)
        self.canvas.bind("<Button-1>", self.OnClick)
        self.canvas.bind("<Configure>", self.OnResize)
        return (1, None, None)
    def ToggleFilter(self, var, cat):
        if var.get():
            self.active_categories.add(cat)
        else:
            self.active_categories.discard(cat)
        self.DrawGraph()
        return (1, None, None)
    def LayoutNodes(self):
        self.node_positions = {}
        if not self.nodes:
            return (1, None, None)
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 1400, 900
        cx, cy = w / 2, h / 2
        radius = min(cx, cy) * 0.7
        visible = [n for n in self.nodes if n["type"] in self.active_categories]
        n = len(visible)
        if n == 0:
            return (1, None, None)
        # Group by category for clustered layout
        cat_order = list(Config.GRAPH_CATEGORIES.keys())
        cat_nodes = {}
        for node in visible:
            cat = node["type"]
            if cat not in cat_nodes:
                cat_nodes[cat] = []
            cat_nodes[cat].append(node)
        # Place only VISIBLE categories in a circle, nodes within each in an arc
        visible_cats = [c for c in cat_order if c in cat_nodes]
        num_cats = len(visible_cats)
        for ci, cat in enumerate(visible_cats):
            nodes_in_cat = cat_nodes[cat]
            cat_angle = 2 * math.pi * ci / num_cats - math.pi / 2
            cat_x = cx + (radius * 0.7) * math.cos(cat_angle)
            cat_y = cy + (radius * 0.7) * math.sin(cat_angle)
            sub_radius = 60 + len(nodes_in_cat) * 15
            for ni, node in enumerate(nodes_in_cat):
                sub_angle = cat_angle + (ni - len(nodes_in_cat) / 2 + 0.5) * (math.pi / 8)
                x = cat_x + sub_radius * math.cos(sub_angle)
                y = cat_y + sub_radius * math.sin(sub_angle)
                self.node_positions[node["id"]] = (x, y)
    def DrawGraph(self):
        self.canvas.delete("all")
        self.node_items = {}
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w > 1 and h > 1:
            self.LayoutNodes()
        # Draw edges
        for edge in self.edges:
            src_id = edge["src"]
            dst_id = edge["dst"]
            if src_id not in self.node_positions or dst_id not in self.node_positions:
                continue
            src_node = self.node_map.get(src_id, {})
            dst_node = self.node_map.get(dst_id, {})
            if src_node.get("type") not in self.active_categories:
                continue
            if dst_node.get("type") not in self.active_categories:
                continue
            x1, y1 = self.node_positions[src_id]
            x2, y2 = self.node_positions[dst_id]
            etype = edge.get("type", "FEEDS")
            color = Config.GRAPH_EDGE_COLORS.get(etype, "#45475a")
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2,
                                    arrow=tk.LAST, arrowshape=(8, 8, 6))
        # Draw nodes
        for node in self.nodes:
            nid = node["id"]
            if nid not in self.node_positions:
                continue
            ntype = node["type"]
            if ntype not in self.active_categories:
                continue
            x, y = self.node_positions[nid]
            fill = Config.GRAPH_CATEGORIES.get(ntype, "#6c7086")
            r = 18
            outline = "#f9e2af" if nid == self.selected_node else "#cdd6f4"
            outline_width = 3 if nid == self.selected_node else 1
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill=fill, outline=outline,
                                           width=outline_width)
            self.node_items[item] = nid
            self.canvas.create_text(x, y, text=nid[:6],
                                    fill="#1e1e2e", font=("Helvetica", 7, "bold"))
            self.canvas.create_text(x, y + r + 10, text=nid,
                                    fill="#cdd6f4", font=("Helvetica", 8))
        return (1, None, None)
    def GetNodeAt(self, x, y):
        items = self.canvas.find_overlapping(x - 20, y - 20, x + 20, y + 20)
        for item in items:
            if item in self.node_items:
                return (1, self.node_items[item], None)
        return (1, None, None)
    def OnMotion(self, event):
        node = self.GetNodeAt(event.x, event.y)
        if node != self.hover_node:
            self.hover_node = node
            self.canvas.configure(cursor="hand2" if node else "arrow")
        return (1, None, None)
    def OnClick(self, event):
        node = self.GetNodeAt(event.x, event.y)
        if node:
            self.selected_node = node
            self.ShowDetail(node)
            self.DrawGraph()
        else:
            self.selected_node = None
            self.detail_text.config(state=tk.NORMAL)
            self.detail_text.delete("1.0", tk.END)
            self.detail_text.config(state=tk.DISABLED)
            self.DrawGraph()
        return (1, None, None)
    def OnResize(self, event):
        self.DrawGraph()
        return (1, None, None)
    def ShowDetail(self, node_id):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        node = self.node_map.get(node_id, {})
        info = f"Class:     {node_id}\n"
        info += f"Category:  {node.get('type', '?')}\n"
        info += f"Dispatch:  {node.get('dispatch', '?')}\n"
        info += f"Desc:      {node.get('description', '')}\n"
        outgoing = [e for e in self.edges if e["src"] == node_id]
        incoming = [e for e in self.edges if e["dst"] == node_id]
        info += f"\nOutgoing ({len(outgoing)}):\n"
        for e in outgoing:
            info += f"  ->[{e['type']}] {e['dst']}\n"
        info += f"\nIncoming ({len(incoming)}):\n"
        for e in incoming:
            info += f"  <-[{e['type']}] {e['src']}\n"
        # Isolation check
        if not outgoing and not incoming:
            info += "\n  ISOLATED - no connections!\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def GapAnalysis(self):
        """Check for gaps in the domain — isolated nodes, missing pairs, missing CRUD."""
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        report = "=== GAP ANALYSIS ===\n\n"
        # 1. Isolated nodes (no edges)
        isolated = []
        for node in self.nodes:
            nid = node["id"]
            has_edge = any(e["src"] == nid or e["dst"] == nid for e in self.edges)
            if not has_edge:
                isolated.append(nid)
        if isolated:
            report += f"ISOLATED Config.GRAPH_CLASSES ({len(isolated)}):\n"
            for name in isolated:
                report += f"  ! {name} — no connections to other classes\n"
            report += "\n"
        else:
            report += "ISOLATED Config.GRAPH_CLASSES: None\n\n"
        # 2. Category coverage
        report += "CATEGORY COVERAGE:\n"
        for cat, color in Config.GRAPH_CATEGORIES.items():
            count = sum(1 for n in self.nodes if n["type"] == cat)
            names = [n["id"] for n in self.nodes if n["type"] == cat]
            report += f"  {cat} ({count}): {', '.join(names)}\n"
        report += "\n"
        # 3. Expected pairs (opposite operations)
        expected_pairs = [
            ("Compress", "Extract"),
            ("Encrypt", "Decrypt"),
            ("Split", "Join"),
            ("Write", "Strip"),
            ("Read", "Write"),
        ]
        report += "EXPECTED PAIRS:\n"
        for a, b in expected_pairs:
            has_edge = any(
                (e["src"] == a and e["dst"] == b) or
                (e["src"] == b and e["dst"] == a)
                for e in self.edges
            )
            status = "OK" if has_edge else "MISSING!"
            report += f"  {a} <-> {b}: {status}\n"
        report += "\n"
        # 4. CRUD completeness
        crud_ops = ["Compress", "Read", "Write", "Extract", "Strip", "Rename"]
        report += f"CRUD OPERATIONS ({len(crud_ops)}): {', '.join(crud_ops)}\n\n"
        # 5. Dispatch key uniqueness
        dispatches = [n["dispatch"] for n in self.nodes]
        counts = Counter(dispatches)
        dupes = [k for k, v in counts.items() if v > 1]
        if dupes:
            report += f"DUPLICATE DISPATCH KEYS: {dupes}\n"
        else:
            report += "DUPLICATE DISPATCH KEYS: None\n\n"
        # 6. Total summary
        report += f"TOTAL: {len(self.nodes)} classes, {len(self.edges)} edges, {len(Config.GRAPH_CATEGORIES)} categories\n"
        self.detail_text.insert("1.0", report)
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
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
if __name__ == "__main__":
    root = tk.Tk()
    app = SpecGraph(root)
    root.mainloop()
