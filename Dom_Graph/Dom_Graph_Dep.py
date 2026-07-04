from Config import Config
#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Dependency Graph Viewer rendering WHY classes connect. Tkinter GUI with edge justifications and dependency chains. No #[@...] headers. No Run dispatch. No Tuple3 returns. Import before shebang. Has hardcoded color values and window geometry. Uses tkinter (not PyQt6). Multiple hardcoded EDGE_REASONS.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Move import after shebang. Move hardcoded colors/geometry to Config.py.>]}
"""
Dependency Graph Viewer -- renders WHY each class connects to another.
Fourth of the seven graph tools:
    spec_graph.py      -> "What exists?"
    spec_flow.py       -> "How does it move?"
    gap_graph.py       -> "What's missing?"
    dep_graph.py       -> "Why does it connect?"   <-- this file
    error_graph.py     -> "Where does it fail?"
    lifecycle_graph.py -> "When does it run?"
    orch_graph.py      -> "Who calls who?"
Every edge has a REASON. This viewer shows the justification for each
dependency and traces dependency chains (A -> B -> C) so you can see
the full "why" behind the structure.
"""
import math
import tkinter as tk
from collections import defaultdict, deque
# ─── Shared spec data ────────────────────────────────────────────────────────
# ─── Edge justifications (the "why") ─────────────────────────────────────────
EDGE_REASONS = {
    "FEEDS":       "Output of {src} is the input to {dst} -- data flows forward",
    "PAIRS":       "{src} and {dst} are opposite operations -- one undoes the other",
    "TRIGGERS":    "{src} detects a condition that {dst} must handle",
    "FALLBACK":    "When {src} cannot fully succeed, {dst} is the recovery path",
    "USES":        "{src} calls {dst} as a subroutine to do its job",
    "ENABLES":     "{src} unlocks the ability for {dst} to run (e.g. password access)",
    "ALTERNATIVE": "{src} is an alternative way to do what {dst} does",
    "WRAPS":       "{src} orchestrates batch/parallel calls to {dst}",
    "MEASURES":    "{src} measures the performance of {dst}",
}
class DepGraph:
    """Visual graph of WHY classes depend on each other + dependency chains."""
    def __init__(self, root):
        self.root = root
        self.root.title("dom_compression -- Dependency Graph (Why does it connect?)")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e2e")
        self.nodes = [{"id": n[0], "type": n[1], "dispatch": n[2], "desc": n[3]} for n in Config.GRAPH_CLASSES]
        self.edges = [{"src": e[0], "dst": e[1], "type": e[2]} for e in Config.GRAPH_EDGES]
        self.node_map = {n["id"]: n for n in self.nodes}
        self.node_ids = [n["id"] for n in self.nodes]
        self.selected_node = None
        self.hover_node = None
        self.node_items = {}
        self.node_positions = {}
        self.active_categories = set(Config.GRAPH_CATEGORIES.keys())
        self.adj_out = defaultdict(list)
        self.adj_in = defaultdict(list)
        for e in self.edges:
            self.adj_out[e["src"]].append((e["dst"], e["type"]))
            self.adj_in[e["dst"]].append((e["src"], e["type"]))
        self.BuildUI()
        self.UpdateLegend()
        self.LayoutNodes()
        self.DrawGraph()
    def TraceChains(self, start, direction="down", max_depth=8):
        """Trace all dependency chains from start node.
        direction='down' -> what this depends on (adj_out)
        direction='up'   -> what depends on this (adj_in)
        Returns list of chains (each a list of node ids)."""
        chains = []
        adj = self.adj_out if direction == "down" else self.adj_in
        queue = deque([(start, [start])])
        while queue:
            node, path = queue.popleft()
            if len(path) > max_depth:
                continue
            neighbors = adj.get(node, [])
            if not neighbors:
                if len(path) > 1:
                    chains.append(path)
                continue
            extended = False
            for dst, _ in neighbors:
                if dst in path:
                    continue
                queue.append((dst, path + [dst]))
                extended = True
            if not extended and len(path) > 1:
                chains.append(path)
        return (1, chains, None)
        return chains
    def BuildUI(self):
        top = tk.Frame(self.root, bg="#1e1e2e", height=50)
        top.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(top, text="dom_compression -- Dependency Graph (Why does it connect?)",
                 fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
        info = f"  Classes={len(self.nodes)}  Edges={len(self.edges)}"
        tk.Label(top, text=info, fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 11)).pack(side=tk.LEFT, padx=10)
        tk.Button(top, text="Chain Report", command=self.ChainReport,
                  bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(side=tk.RIGHT, padx=5)
        ff = tk.Frame(self.root, bg="#1e1e2e")
        ff.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(ff, text="Filter:", fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.cat_vars = {}
        for cat, color in Config.GRAPH_CATEGORIES.items():
            cnt = sum(1 for n in self.nodes if n["type"] == cat)
            var = tk.IntVar(value=1)
            self.cat_vars[cat] = var
            tk.Checkbutton(ff, text=f"{cat} ({cnt})", variable=var,
                           bg="#1e1e2e", fg=color, selectcolor="#313244",
                           font=("Helvetica", 9),
                           command=self.OnFilterChange).pack(side=tk.LEFT, padx=3)
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(main, bg="#11111b", highlightthickness=0, cursor="hand2")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        df = tk.Frame(main, bg="#1e1e2e", width=450)
        df.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        df.pack_propagate(False)
        tk.Label(df, text="Dependency Details", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 13, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))
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
        tk.Label(self.legend_frame, text="Edge Types (Why):", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        for et, ec in Config.GRAPH_EDGE_COLORS.items():
            reason = EDGE_REASONS.get(et, "").split("--")[0].strip()
            row = tk.Frame(self.legend_frame, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            c = tk.Canvas(row, width=20, height=12, bg="#1e1e2e", highlightthickness=0)
            c.pack(side=tk.LEFT)
            c.create_line(2, 6, 18, 6, fill=ec, width=2)
            tk.Label(row, text=f" {et} -- {reason}", fg=ec, bg="#1e1e2e",
                     font=("Helvetica", 8)).pack(side=tk.LEFT)
        return (1, None, None)
    def OnFilterChange(self):
        self.active_categories = {c for c, v in self.cat_vars.items() if v.get()}
        self.DrawGraph()
        return (1, None, None)
    def LayoutNodes(self):
        self.node_positions = {}
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 1400, 900
        cx, cy = w / 2, h / 2
        radius = min(cx, cy) - 120
        visible = [n for n in self.nodes if n["type"] in self.active_categories]
        if not visible:
            return (1, None, None)
        cat_nodes = defaultdict(list)
        for n in visible:
            cat_nodes[n["type"]].append(n)
        for ci, cat in enumerate(Config.GRAPH_CATEGORIES):
            if cat not in cat_nodes:
                continue
            ca = 2 * math.pi * ci / len(Config.GRAPH_CATEGORIES) - math.pi / 2
            cx2 = cx + radius * 0.65 * math.cos(ca)
            cy2 = cy + radius * 0.65 * math.sin(ca)
            sr = 50 + len(cat_nodes[cat]) * 12
            for ni, node in enumerate(cat_nodes[cat]):
                sa = ca + (ni - len(cat_nodes[cat]) / 2 + 0.5) * (math.pi / 7)
                self.node_positions[node["id"]] = (cx2 + sr * math.cos(sa),
                                                   cy2 + sr * math.sin(sa))
    def DrawGraph(self):
        self.canvas.delete("all")
        self.node_items = {}
        if self.canvas.winfo_width() > 1:
            self.LayoutNodes()
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
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            self.canvas.create_text(mx, my, text=e["type"], fill=color,
                                    font=("Helvetica", 6, "bold"))
        for node in self.nodes:
            nid = node["id"]
            if nid not in self.node_positions or node["type"] not in self.active_categories:
                continue
            x, y = self.node_positions[nid]
            r = 18
            ol = "#f9e2af" if nid == self.selected_node else "#cdd6f4"
            ow = 3 if nid == self.selected_node else 1
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill=Config.GRAPH_CATEGORIES.get(node["type"], "#6c7086"),
                                           outline=ol, width=ow)
            self.node_items[item] = nid
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
    def ShowDetail(self, nid):
        node = self.node_map.get(nid, {})
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        info = f"Class:    {nid}\nCategory: {node.get('type', '?')}\nDispatch: {node.get('dispatch', '?')}\n\n"
        info += "Dependencies (WHY it connects):\n"
        for dst, etype in self.adj_out.get(nid, []):
            reason = EDGE_REASONS.get(etype, "").format(src=nid, dst=dst)
            info += f"  ->[{etype}] {dst}\n     WHY: {reason}\n"
        info += "\nDependents (who depends on this):\n"
        for src, etype in self.adj_in.get(nid, []):
            reason = EDGE_REASONS.get(etype, "").format(src=src, dst=nid)
            info += f"  <-[{etype}] {src}\n     WHY: {reason}\n"
        down_chains = self.TraceChains(nid, "down")
        up_chains = self.TraceChains(nid, "up")
        info += f"\nDependency chains DOWN ({len(down_chains)}):\n"
        for ch in down_chains[:8]:
            info += f"  {' -> '.join(ch)}\n"
        info += f"\nDependency chains UP ({len(up_chains)}):\n"
        for ch in up_chains[:8]:
            info += f"  {' -> '.join(ch)}\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def ChainReport(self):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        r = "=== DEPENDENCY CHAIN REPORT ===\n\n"
        for nid in self.node_ids:
            down = self.TraceChains(nid, "down")
            if down:
                r += f"{nid} depends on ({len(down)} chains):\n"
                for ch in down[:5]:
                    r += f"  {' -> '.join(ch)}\n"
                if len(down) > 5:
                    r += f"  ... and {len(down) - 5} more\n"
                r += "\n"
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
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
if __name__ == "__main__":
    root = tk.Tk()
    app = DomGraphDep(root)
    root.mainloop()
