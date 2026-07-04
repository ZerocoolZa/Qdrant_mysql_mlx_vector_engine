#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Efi Graph Viewer loading typed-state code graph and rendering as interactive node-edge graph. Tkinter GUI. No #[@...] headers (uses old-style comment blocks). No Run dispatch. No Tuple3 returns. File references Efi_graph_viewer.py in header but filename is Dom_Graph_Viewer.py. Uses Config_efl_brain import. Has hardcoded NODE_COLORS and EDGE_COLORS dicts.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Fix filename reference in header. Move hardcoded colors to Config.py.>]}
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Efi_graph_viewer.py
# Domain:   efl_brain
# Authority: Visualizes the typed-state code graph
# DB:       None
# ============================================================================
"""
Efi Graph Viewer — loads Efi_code_graph.json (typed-state format) and renders
it as an interactive node-edge graph.
Node colors by type:
  CONFIG   — purple (root, boot origin)
  MEMUNIT  — green (has Run() + self.state)
  CLASS    — blue (regular class)
  FUNCTION — cyan (standalone function)
  FILE_PY  — light blue (Python file, no classes parsed)
  FILE_JSON— orange (data)
  FILE_MD  — yellow (docs)
  FILE_DB  — dark gray (database)
  FOLDER   — gray (structural)
Edge colors by type:
  IMPORTS   — green (valid dependency)
  CONTAINS  — gray (structural)
  DEFINES   — blue (parent defines child)
Derived overlays:
  Cycle edges — red (STOP)
  Missing dep — yellow warning (WARN)
"""
import json
import os
import math
import tkinter as tk
import Config_efl_brain as Config
# No JSON files — read from efl_brain.db (the dinner table)
DB_PATH = Config.DB_PATH
NODE_COLORS = {
    "CONFIG":   "#cba6f7",
    "MEMUNIT":  "#a6e3a1",
    "CLASS":    "#89b4fa",
    "FUNCTION": "#94e2d5",
    "FILE_PY":  "#74c7ec",
    "FILE_JSON":"#fab387",
    "FILE_MD":  "#f9e2af",
    "FILE_DB":  "#45475a",
    "FOLDER":   "#6c7086",
}
EDGE_COLORS = {
    "IMPORTS":    "#a6e3a1",
    "CONTAINS":   "#45475a",
    "DEFINES":    "#89b4fa",
    "CALLS":      "#f38ba8",
    "ASSOCIATES": "#f9e2af",
}
NODE_RADIUS = {
    "FOLDER":   18,
    "CONFIG":   16,
    "MEMUNIT":  15,
    "FILE_DB":  14,
    "FILE_PY":  13,
    "FILE_JSON":12,
    "FILE_MD":  12,
    "CLASS":    10,
    "FUNCTION": 8,
}
class GraphViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Efi Brain — Typed-State Code Graph")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e2e")
        self.graph_data = None
        self.nodes = []
        self.edges = []
        self.node_map = {}
        self.node_positions = {}
        self.selected_node = None
        self.hover_node = None
        self.canvas = None
        self.detail_text = None
        self.node_items = {}
        self.filter_var = None
        self.active_types = set()
        self.LoadGraph()
        self.BuildUI()
        self.LayoutNodes()
    def LoadGraph(self):
        # Read from the dinner table (efl_brain.db) — no more JSON files
        from Efi_brain_db import BrainDb
        db = BrainDb(DB_PATH)
        db.Connect()
        links = db.ReadPredictionLinks()
        blast = db.ReadBlastRadius()
        db.Disconnect()
        # If DB has no graph data, build it live from the agent graph
        if not links:
            from Efi_agent_graph import AgentGraph
            g = AgentGraph()
            g.Build(Config.BASE_DIR)
            g.WriteToDb()
            db = BrainDb(DB_PATH)
            db.Connect()
            links = db.ReadPredictionLinks()
            db.Disconnect()
        # Convert DB data to viewer format
        self.nodes = []
        self.edges = []
        seen_nodes = set()
        for link in links:
            src = link.get("source_node", "")
            dst = link.get("target_node", "")
            if src and src not in seen_nodes:
                self.nodes.append({"id": src, "type": "FILE_PY", "path": src})
                seen_nodes.add(src)
            if dst and dst not in seen_nodes:
                self.nodes.append({"id": dst, "type": "FILE_PY", "path": dst})
                seen_nodes.add(dst)
            self.edges.append({"source": src, "target": dst, "type": "PREDICTS"})
        self.node_map = {n["id"]: n for n in self.nodes}
        self.active_types = set(n["type"] for n in self.nodes)
        return (1, None, None)
    def LoadAgentGraphLive(self):
        """Build the agent graph live and load it.
        Lazy import — no module-level coupling to Efi_agent_graph.py."""
        from Efi_agent_graph import AgentGraph, ROOT
        ag = AgentGraph()
        ag.Build(ROOT)
        self.graph_data = ag.Export()
        self.nodes = self.graph_data.get("nodes", [])
        self.edges = self.graph_data.get("edges", [])
        self.node_map = {n["id"]: n for n in self.nodes}
        self.active_types = set(n["type"] for n in self.nodes)
        return (1, None, None)
    def BuildUI(self):
        top = tk.Frame(self.root, bg="#1e1e2e", height=50)
        top.pack(fill=tk.X, padx=10, pady=5)
        title = tk.Label(top, text="Efi Brain — Typed-State Graph",
                         fg="#cdd6f4", bg="#1e1e2e",
                         font=("Helvetica", 16, "bold"))
        title.pack(side=tk.LEFT)
        prim = self.graph_data.get("primitives", {})
        types = self.graph_data.get("node_types", {})
        derived = self.graph_data.get("derived", {})
        info_text = f"  V={prim.get('node_count',0)}  E={prim.get('edge_count',0)}  Types={len(types)}  DAG={'Yes' if derived.get('is_dag') else 'No'}"
        info = tk.Label(top, text=info_text, fg="#94a3b8", bg="#1e1e2e",
                        font=("Helvetica", 11))
        info.pack(side=tk.LEFT, padx=10)
        reload_btn = tk.Button(top, text="Reload", command=self.Reload,
                               bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                               font=("Helvetica", 10), padx=10)
        reload_btn.pack(side=tk.RIGHT)
        # Filter bar
        filter_frame = tk.Frame(self.root, bg="#1e1e2e")
        filter_frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(filter_frame, text="Filter:", fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        for ntype, color in NODE_COLORS.items():
            if ntype not in types:
                continue
            var = tk.IntVar(value=1)
            cb = tk.Checkbutton(filter_frame, text=f"{ntype} ({types.get(ntype,0)})",
                                variable=var, bg="#1e1e2e", fg=color,
                                selectcolor="#313244", activebackground="#1e1e2e",
                                activeforeground=color, font=("Helvetica", 9),
                                command=lambda v=var, t=ntype: self.ToggleFilter(v, t))
            cb.var = var
            cb.pack(side=tk.LEFT, padx=3)
        # Main area
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(main, bg="#11111b", highlightthickness=0,
                                cursor="hand2")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_frame = tk.Frame(main, bg="#1e1e2e", width=400)
        detail_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        detail_frame.pack_propagate(False)
        detail_label = tk.Label(detail_frame, text="Node Details",
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
        tk.Label(legend, text="Node Types:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        for ntype, color in NODE_COLORS.items():
            if ntype not in types:
                continue
            row = tk.Frame(legend, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            tk.Canvas(row, width=12, height=12, bg="#1e1e2e",
                      highlightthickness=0).create_oval(2, 2, 10, 10, fill=color, outline="")
            tk.Label(row, text=f" {ntype}", fg=color, bg="#1e1e2e",
                     font=("Helvetica", 9)).pack(side=tk.LEFT)
        tk.Label(legend, text="", bg="#1e1e2e").pack()
        tk.Label(legend, text="Edge Types:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        for etype, ecolor in EDGE_COLORS.items():
            row = tk.Frame(legend, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            tk.Canvas(row, width=20, height=12, bg="#1e1e2e",
                      highlightthickness=0).create_line(2, 6, 18, 6, fill=ecolor, width=2)
            tk.Label(row, text=f" {etype}", fg=ecolor, bg="#1e1e2e",
                     font=("Helvetica", 9)).pack(side=tk.LEFT)
        # Cycle warning
        cycle_count = derived.get("cycle_count", 0)
        if cycle_count > 0:
            tk.Label(legend, text=f"\n⚠ {cycle_count} CYCLES DETECTED",
                     fg="#f38ba8", bg="#1e1e2e",
                     font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        else:
            tk.Label(legend, text="\n✓ DAG — No cycles",
                     fg="#a6e3a1", bg="#1e1e2e",
                     font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        self.canvas.bind("<Motion>", self.OnMotion)
        self.canvas.bind("<Button-1>", self.OnClick)
        self.canvas.bind("<Configure>", self.OnResize)
        return (1, None, None)
    def ToggleFilter(self, var, ntype):
        if var.get():
            self.active_types.add(ntype)
        else:
            self.active_types.discard(ntype)
        self.DrawGraph()
        return (1, None, None)
    def LayoutNodes(self):
        if not self.nodes:
            return (1, None, None)
        cx, cy = 700, 450
        radius = min(cx, cy) - 100
        visible = [n for n in self.nodes if n["type"] in self.active_types]
        n = len(visible)
        if n == 0:
            return (1, None, None)
        for i, node in enumerate(visible):
            angle = 2 * math.pi * i / n - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            self.node_positions[node["id"]] = (x, y)
    def DrawGraph(self):
        self.canvas.delete("all")
        self.node_items = {}
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w > 1 and h > 1:
            cx, cy = w / 2, h / 2
            radius = min(cx, cy) - 100
            visible = [n for n in self.nodes if n["type"] in self.active_types]
            n = len(visible)
            if n > 0:
                for i, node in enumerate(visible):
                    angle = 2 * math.pi * i / n - math.pi / 2
                    x = cx + radius * math.cos(angle)
                    y = cy + radius * math.sin(angle)
                    self.node_positions[node["id"]] = (x, y)
        cycles = self.graph_data.get("derived", {}).get("cycles", [])
        cycle_nodes = set()
        for cycle in cycles:
            for node_id in cycle:
                cycle_nodes.add(node_id)
        # Draw edges
        for edge in self.edges:
            src_id = edge["src"]
            dst_id = edge["dst"]
            if src_id not in self.node_positions or dst_id not in self.node_positions:
                continue
            src_node = self.node_map.get(src_id, {})
            dst_node = self.node_map.get(dst_id, {})
            if src_node.get("type") not in self.active_types:
                continue
            if dst_node.get("type") not in self.active_types:
                continue
            x1, y1 = self.node_positions[src_id]
            x2, y2 = self.node_positions[dst_id]
            etype = edge.get("type", "DEPENDS_ON")
            is_cycle = src_id in cycle_nodes and dst_id in cycle_nodes
            if is_cycle:
                color = "#f38ba8"
                width = 2
            else:
                color = EDGE_COLORS.get(etype, "#45475a")
                width = 1 if etype == "CONTAINS" else 2 if etype == "IMPORTS" else 1
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width,
                                    arrow=tk.LAST, arrowshape=(8, 8, 6),
                                    dash=(3, 2) if etype == "CONTAINS" else None)
        # Draw nodes
        for node in self.nodes:
            nid = node["id"]
            if nid not in self.node_positions:
                continue
            ntype = node.get("type", "FILE_PY")
            if ntype not in self.active_types:
                continue
            x, y = self.node_positions[nid]
            fill = NODE_COLORS.get(ntype, "#6c7086")
            r = NODE_RADIUS.get(ntype, 12)
            is_cycle = nid in cycle_nodes
            outline = "#f38ba8" if is_cycle else ("#f9e2af" if nid == self.selected_node else "#cdd6f4")
            outline_width = 3 if is_cycle or nid == self.selected_node else 1
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill=fill, outline=outline,
                                           width=outline_width)
            self.node_items[item] = nid
            label_text = nid.split("::")[-1] if "::" in nid else os.path.basename(nid)
            if len(label_text) > 22:
                label_text = label_text[:19] + "..."
            self.canvas.create_text(x, y + r + 10, text=label_text,
                                    fill="#cdd6f4", font=("Helvetica", 7))
        return (1, None, None)
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
        ntype = node.get("type", "UNKNOWN")
        state = node.get("state", {})
        path = node.get("path", "")
        name = node_id.split("::")[-1] if "::" in node_id else os.path.basename(node_id)
        info = f"Name:   {name}\n"
        info += f"Type:   {ntype}\n"
        info += f"ID:     {node_id}\n"
        if path:
            info += f"Path:   {path}\n"
        info += f"Exists: {state.get('exists', '?')}\n"
        if state.get("size"):
            info += f"Size:   {state.get('size', 0)} bytes\n"
        if state.get("hash"):
            info += f"Hash:   {state.get('hash', '')}\n"
        # State details for classes/memunits
        if ntype in ("CLASS", "MEMUNIT"):
            info += f"\nClass:  {state.get('class_name', '')}\n"
            info += f"Has Run:   {state.get('has_run', False)}\n"
            info += f"Has State: {state.get('has_state', False)}\n"
            info += f"Methods:   {state.get('method_count', 0)}\n"
            methods = state.get("methods", [])
            if methods:
                info += f"  [{', '.join(methods[:10])}"
                if len(methods) > 10:
                    info += f", ... +{len(methods)-10}"
                info += "]\n"
            bases = state.get("bases", [])
            if bases:
                info += f"Bases:     {bases}\n"
        if ntype == "FUNCTION":
            info += f"\nFunction:  {state.get('function_name', '')}\n"
            info += f"Params:    {state.get('param_count', 0)}\n"
            params = state.get("params", [])
            if params:
                info += f"  [{', '.join(params)}]\n"
        # Edges
        outgoing = [e for e in self.edges if e["src"] == node_id]
        incoming = [e for e in self.edges if e["dst"] == node_id]
        info += f"\nOutgoing ({len(outgoing)}):\n"
        for e in outgoing:
            tgt = e["dst"].split("::")[-1] if "::" in e["dst"] else os.path.basename(e["dst"])
            info += f"  →[{e['type']}] {tgt}\n"
        info += f"\nIncoming ({len(incoming)}):\n"
        for e in incoming:
            src = e["src"].split("::")[-1] if "::" in e["src"] else os.path.basename(e["src"])
            info += f"  ←[{e['type']}] {src}\n"
        # Cycle check
        cycles = self.graph_data.get("derived", {}).get("cycles", [])
        in_cycle = any(node_id in c for c in cycles)
        info += f"\nIn Cycle: {'YES ⚠' if in_cycle else 'No'}\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def Reload(self):
        self.LoadGraph()
        self.LayoutNodes()
        self.DrawGraph()
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
    app = GraphViewer(root)
    root.mainloop()
