from Config import Config
#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Orchestration Graph Viewer rendering WHO calls WHO. Tkinter GUI with call/dispatch tree. No #[@...] headers. No Run dispatch. No Tuple3 returns. Import before shebang. Has hardcoded CALL_EDGE_TYPES, color values, window geometry. Uses tkinter.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Move import after shebang. Move hardcoded colors/data to Config.py.>]}
"""
Orchestration Graph Viewer -- renders WHO calls WHO in the domain.
Seventh of the seven graph tools:
    spec_graph.py      -> "What exists?"
    spec_flow.py       -> "How does it move?"
    gap_graph.py       -> "What's missing?"
    dep_graph.py       -> "Why does it connect?"
    error_graph.py     -> "Where does it fail?"
    lifecycle_graph.py -> "When does it run?"
    orch_graph.py      -> "Who calls who?"   <-- this file
Shows the dispatch/call tree: which class triggers which, wrapper and
batch relationships, and the full orchestration hierarchy. The root
nodes are entry points (classes that no one calls); leaves are terminal
classes (classes that call nothing).
"""
import math
import tkinter as tk
from collections import defaultdict
CALL_EDGE_TYPES = {"USES", "WRAPS", "FEEDS", "ENABLES", "TRIGGERS", "FALLBACK", "MEASURES"}
CALL_COLOR = "#89b4fa"
WRAP_COLOR = "#89dceb"
ROOT_COLOR = "#a6e3a1"
LEAF_COLOR = "#f9e2af"
class OrchGraph:
    """Visual graph of the call/dispatch tree -- who calls who."""
    def __init__(self, root):
        self.root = root
        self.root.title("dom_compression -- Orchestration Graph (Who calls who?)")
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
        # Build call adjacency from edges + flow call steps
        self.call_out = defaultdict(list)   # src -> [(dst, edge_type)]
        self.call_in = defaultdict(list)    # dst -> [(src, edge_type)]
        for e in self.edges:
            if e["type"] in CALL_EDGE_TYPES:
                self.call_out[e["src"]].append((e["dst"], e["type"]))
                self.call_in[e["dst"]].append((e["src"], e["type"]))
        # Extract call relationships from flow "call" steps
        for cn, flow in Config.GRAPH_FLOWS.items():
            for st, desc in flow:
                if st == "call":
                    # Parse "ClassName -- description" or "ClassName.all -- ..."
                    target = desc.split("--")[0].strip().split(".")[0].strip()
                    if target in self.node_map and target != cn:
                        if (target, "CALL") not in self.call_out[cn]:
                            self.call_out[cn].append((target, "CALL"))
                            self.call_in[target].append((cn, "CALL"))
        # Roots: classes that no one calls (entry points)
        self.roots = [nid for nid in self.node_ids if not self.call_in.get(nid)]
        # Leaves: classes that call nothing (terminal)
        self.leaves = [nid for nid in self.node_ids if not self.call_out.get(nid)]
        self.BuildUI()
        self.UpdateLegend()
        self.LayoutNodes()
    def BuildUI(self):
        top = tk.Frame(self.root, bg="#1e1e2e", height=50)
        top.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(top, text="dom_compression -- Orchestration Graph (Who calls who?)",
                 fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
        info = f"  Roots={len(self.roots)}  Leaves={len(self.leaves)}  Call edges={sum(len(v) for v in self.call_out.values())}"
        tk.Label(top, text=info, fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 11)).pack(side=tk.LEFT, padx=10)
        tk.Button(top, text="Orchestration Report", command=self.OrchReport,
                  bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(side=tk.RIGHT, padx=5)
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(main, bg="#11111b", highlightthickness=0, cursor="hand2")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        df = tk.Frame(main, bg="#1e1e2e", width=450)
        df.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        df.pack_propagate(False)
        tk.Label(df, text="Orchestration Details", fg="#cdd6f4", bg="#1e1e2e",
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
        tk.Label(self.legend_frame, text="Node Roles:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        for label, color in [("Root (entry point -- no one calls it)", ROOT_COLOR),
                             ("Leaf (terminal -- calls nothing)", LEAF_COLOR),
                             ("Intermediate (called + calls)", "#89b4fa")]:
            row = tk.Frame(self.legend_frame, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            c = tk.Canvas(row, width=12, height=12, bg="#1e1e2e", highlightthickness=0)
            c.pack(side=tk.LEFT)
            c.create_oval(2, 2, 10, 10, fill=color, outline="")
            tk.Label(row, text=f" {label}", fg=color, bg="#1e1e2e",
                     font=("Helvetica", 8)).pack(side=tk.LEFT)
        tk.Label(self.legend_frame, text="", bg="#1e1e2e").pack()
        tk.Label(self.legend_frame, text="Call Types:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        for et, ec in [("USES", CALL_COLOR), ("WRAPS", WRAP_COLOR), ("CALL", "#cba6f7"),
                       ("FEEDS", "#a6e3a1"), ("ENABLES", "#94e2d5")]:
            row = tk.Frame(self.legend_frame, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            c = tk.Canvas(row, width=20, height=12, bg="#1e1e2e", highlightthickness=0)
            c.pack(side=tk.LEFT)
            c.create_line(2, 6, 18, 6, fill=ec, width=2, arrow=tk.LAST)
            tk.Label(row, text=f" {et}", fg=ec, bg="#1e1e2e",
                     font=("Helvetica", 9)).pack(side=tk.LEFT)
        return (1, None, None)
    def LayoutNodes(self):
        """Tree layout: roots at top, children below by depth level."""
        self.node_positions = {}
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 1400, 900
        # Compute depth for each node (BFS from roots)
        depth = {}
        from collections import deque
        queue = deque()
        for r in self.roots:
            depth[r] = 0
            queue.append(r)
        while queue:
            nid = queue.popleft()
            for dst, _ in self.call_out.get(nid, []):
                if dst not in depth or depth[dst] > depth[nid] + 1:
                    depth[dst] = depth[nid] + 1
                    queue.append(dst)
        # Nodes not reached from roots get max depth + 1
        max_depth = max(depth.values()) if depth else 0
        for nid in self.node_ids:
            if nid not in depth:
                depth[nid] = max_depth + 1
                max_depth = max(max_depth, depth[nid])
        # Group by depth level
        levels = defaultdict(list)
        for nid, d in depth.items():
            levels[d].append(nid)
        # Place nodes: each level is a horizontal row
        level_h = h / max(max_depth + 1, 1)
        for d, nodes_at_d in levels.items():
            n = len(nodes_at_d)
            spacing = (w - 100) / max(n, 1)
            for i, nid in enumerate(sorted(nodes_at_d)):
                x = 50 + spacing * (i + 0.5)
                y = level_h * d + level_h / 2
                self.node_positions[nid] = (x, y)
        return (1, None, None)
    def DrawGraph(self):
        self.canvas.delete("all")
        self.node_items = {}
        if self.canvas.winfo_width() > 1:
            self.LayoutNodes()
        # Draw call edges
        for src, calls in self.call_out.items():
            if src not in self.node_positions:
                continue
            x1, y1 = self.node_positions[src]
            for dst, etype in calls:
                if dst not in self.node_positions:
                    continue
                x2, y2 = self.node_positions[dst]
                if etype == "WRAPS":
                    color = WRAP_COLOR
                    width = 3
                elif etype == "CALL":
                    color = "#cba6f7"
                    width = 2
                else:
                    color = CALL_COLOR
                    width = 2
                self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width,
                                        arrow=tk.LAST, arrowshape=(8, 8, 6))
        # Draw nodes
        for node in self.nodes:
            nid = node["id"]
            if nid not in self.node_positions:
                continue
            x, y = self.node_positions[nid]
            r = 18
            if nid in self.roots:
                fill = ROOT_COLOR
            elif nid in self.leaves:
                fill = LEAF_COLOR
            else:
                fill = Config.GRAPH_CATEGORIES.get(node["type"], "#6c7086")
            ol = "#f9e2af" if nid == self.selected_node else "#cdd6f4"
            ow = 3 if nid == self.selected_node else 1
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill=fill, outline=ol, width=ow)
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
        if nid in self.roots:
            info += "Role: ROOT (entry point -- no one calls this)\n"
        elif nid in self.leaves:
            info += "Role: LEAF (terminal -- calls nothing)\n"
        else:
            info += "Role: INTERMEDIATE (called by others + calls others)\n"
        # Who calls this
        callers = self.call_in.get(nid, [])
        if callers:
            info += f"\nCalled BY ({len(callers)}):\n"
            for src, etype in callers:
                info += f"  <-[{etype}] {src}\n"
        else:
            info += "\nCalled BY: nobody (root)\n"
        # What this calls
        callees = self.call_out.get(nid, [])
        if callees:
            info += f"\nCalls ({len(callees)}):\n"
            for dst, etype in callees:
                info += f"  ->[{etype}] {dst}\n"
        else:
            info += "\nCalls: nothing (leaf)\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def OrchReport(self):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        r = "=== ORCHESTRATION REPORT ===\n\n"
        r += f"ROOTS / ENTRY POINTS ({len(self.roots)}):\n"
        for nid in self.roots:
            r += f"  {nid} (dispatch: {self.node_map[nid]['dispatch']})\n"
        r += "\n"
        r += f"LEAVES / TERMINAL ({len(self.leaves)}):\n"
        for nid in self.leaves:
            r += f"  {nid}\n"
        r += "\n"
        r += "CALL TREE (who calls who):\n"
        for nid in self.node_ids:
            callees = self.call_out.get(nid, [])
            if callees:
                r += f"  {nid} calls:\n"
                for dst, etype in callees:
                    r += f"    ->[{etype}] {dst}\n"
        r += "\n"
        r += "CALLED-BY TREE (who is called by who):\n"
        for nid in self.node_ids:
            callers = self.call_in.get(nid, [])
            if callers:
                r += f"  {nid} is called by:\n"
                for src, etype in callers:
                    r += f"    <-[{etype}] {src}\n"
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
    app = OrchGraph(root)
    root.mainloop()
