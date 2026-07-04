from Config import Config
#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Error Graph Viewer rendering WHERE domain fails and recovery routes. Tkinter GUI. No #[@...] headers. No Run dispatch. No Tuple3 returns. Import before shebang. Has hardcoded color values and window geometry. Uses tkinter. Multiple hardcoded color constants.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Move import after shebang. Move hardcoded colors to Config.py.>]}
"""
Error Graph Viewer -- renders WHERE the domain fails and how it recovers.
Fifth of the seven graph tools:
    spec_graph.py      -> "What exists?"
    spec_flow.py       -> "How does it move?"
    gap_graph.py       -> "What's missing?"
    dep_graph.py       -> "Why does it connect?"
    error_graph.py     -> "Where does it fail?"   <-- this file
    lifecycle_graph.py -> "When does it run?"
    orch_graph.py      -> "Who calls who?"
Shows every error path extracted from the spec flows, the failure modes
of each class, and the recovery routes (FALLBACK / TRIGGERS edges) that
connect error producers to error handlers.
"""
import math
import tkinter as tk
from collections import defaultdict
RECOVERY_EDGE_TYPES = {"FALLBACK", "TRIGGERS"}
RECOVERY_COLOR = "#fab387"
ERROR_COLOR = "#f38ba8"
NO_ERROR_COLOR = "#a6e3a1"
ERROR_NODE_COLOR = "#f38ba8"
HANDLER_COLOR = "#89b4fa"
class ErrorGraph:
    """Visual graph of error paths, failure modes, and recovery routes."""
    def __init__(self, root):
        self.root = root
        self.root.title("dom_compression -- Error Graph (Where does it fail?)")
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
        # Extract error steps from flows
        self.class_errors = {}       # class -> [error_desc, ...]
        self.class_has_error = {}    # class -> bool
        for cn in self.node_ids:
            flow = Config.GRAPH_FLOWS.get(cn, [])
            errors = [desc for st, desc in flow if st == "error"]
            self.class_errors[cn] = errors
            self.class_has_error[cn] = len(errors) > 0
        # Recovery routes: edges of type FALLBACK or TRIGGERS
        self.recovery_edges = [e for e in self.edges if e["type"] in RECOVERY_EDGE_TYPES]
        # Classes that are error handlers (dst of recovery edges)
        self.error_handlers = set(e["dst"] for e in self.recovery_edges)
        self.BuildUI()
        self.UpdateLegend()
        self.LayoutNodes()
        self.DrawGraph()
    def BuildUI(self):
        top = tk.Frame(self.root, bg="#1e1e2e", height=50)
        top.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(top, text="dom_compression -- Error Graph (Where does it fail?)",
                 fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
        err_count = sum(1 for v in self.class_has_error.values() if v)
        no_err = sum(1 for v in self.class_has_error.values() if not v)
        info = f"  With errors={err_count}  No errors={no_err}  Recovery routes={len(self.recovery_edges)}"
        tk.Label(top, text=info, fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 11)).pack(side=tk.LEFT, padx=10)
        tk.Button(top, text="Error Report", command=self.ErrorReport,
                  bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(side=tk.RIGHT, padx=5)
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(main, bg="#11111b", highlightthickness=0, cursor="hand2")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        df = tk.Frame(main, bg="#1e1e2e", width=450)
        df.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        df.pack_propagate(False)
        tk.Label(df, text="Error Details", fg="#cdd6f4", bg="#1e1e2e",
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
        tk.Label(self.legend_frame, text="Node Colors:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        for label, color in [("Has error paths", ERROR_NODE_COLOR),
                             ("Error handler / recovery", HANDLER_COLOR),
                             ("No error handling", NO_ERROR_COLOR)]:
            row = tk.Frame(self.legend_frame, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            c = tk.Canvas(row, width=12, height=12, bg="#1e1e2e", highlightthickness=0)
            c.pack(side=tk.LEFT)
            c.create_oval(2, 2, 10, 10, fill=color, outline="")
            tk.Label(row, text=f" {label}", fg=color, bg="#1e1e2e",
                     font=("Helvetica", 9)).pack(side=tk.LEFT)
        tk.Label(self.legend_frame, text="", bg="#1e1e2e").pack()
        tk.Label(self.legend_frame, text="Edges:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        row = tk.Frame(self.legend_frame, bg="#1e1e2e")
        row.pack(fill=tk.X, pady=1)
        c = tk.Canvas(row, width=20, height=12, bg="#1e1e2e", highlightthickness=0)
        c.pack(side=tk.LEFT)
        c.create_line(2, 6, 18, 6, fill=RECOVERY_COLOR, width=2, arrow=tk.LAST)
        tk.Label(row, text=" Recovery route (FALLBACK/TRIGGERS)",
                 fg=RECOVERY_COLOR, bg="#1e1e2e",
                 font=("Helvetica", 9)).pack(side=tk.LEFT)
        return (1, None, None)
    def LayoutNodes(self):
        self.node_positions = {}
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 1400, 900
        cx, cy = w / 2, h / 2
        radius = min(cx, cy) - 120
        # Layout: error producers on left arc, handlers on right arc, no-error on outer
        error_nodes = [n for n in self.nodes if self.class_has_error.get(n["id"], False)]
        handler_nodes = [n for n in self.nodes if n["id"] in self.error_handlers]
        clean_nodes = [n for n in self.nodes if not self.class_has_error.get(n["id"], False)
                       and n["id"] not in self.error_handlers]
        def place_arc(nodes_list, start_angle, end_angle, r):
            n = len(nodes_list)
            if n == 0:
                return (1, None, None)
            for i, node in enumerate(nodes_list):
                angle = start_angle + (end_angle - start_angle) * (i / max(n - 1, 1))
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                self.node_positions[node["id"]] = (x, y)
        place_arc(error_nodes, math.pi * 0.75, math.pi * 1.25, radius * 0.8)
        place_arc(handler_nodes, -math.pi * 0.25, math.pi * 0.25, radius * 0.8)
        place_arc(clean_nodes, math.pi * 0.3, math.pi * 0.7, radius * 1.0)
    def DrawGraph(self):
        self.canvas.delete("all")
        self.node_items = {}
        if self.canvas.winfo_width() > 1:
            self.LayoutNodes()
        # Recovery edges
        for e in self.recovery_edges:
            s, d = e["src"], e["dst"]
            if s not in self.node_positions or d not in self.node_positions:
                continue
            x1, y1 = self.node_positions[s]
            x2, y2 = self.node_positions[d]
            self.canvas.create_line(x1, y1, x2, y2, fill=RECOVERY_COLOR, width=3,
                                    arrow=tk.LAST, arrowshape=(10, 10, 8))
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            self.canvas.create_text(mx, my, text=e["type"], fill=RECOVERY_COLOR,
                                    font=("Helvetica", 7, "bold"))
        # Nodes
        for node in self.nodes:
            nid = node["id"]
            if nid not in self.node_positions:
                continue
            x, y = self.node_positions[nid]
            r = 20
            if nid in self.error_handlers:
                fill = HANDLER_COLOR
            elif self.class_has_error.get(nid, False):
                fill = ERROR_NODE_COLOR
            else:
                fill = NO_ERROR_COLOR
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
        info = f"Class:    {nid}\nCategory: {node.get('type', '?')}\n\n"
        errors = self.class_errors.get(nid, [])
        if errors:
            info += f"Error paths ({len(errors)}):\n"
            for err in errors:
                info += f"  ! {err}\n"
        else:
            info += "Error paths: NONE (no error handling in flow!)\n"
        # Recovery routes FROM this class
        rec_out = [e for e in self.recovery_edges if e["src"] == nid]
        if rec_out:
            info += f"\nRecovery routes FROM {nid} ({len(rec_out)}):\n"
            for e in rec_out:
                info += f"  ->[{e['type']}] {e['dst']}\n"
        # Recovery routes TO this class
        rec_in = [e for e in self.recovery_edges if e["dst"] == nid]
        if rec_in:
            info += f"\nRecovery routes TO {nid} ({len(rec_in)}):\n"
            for e in rec_in:
                info += f"  <-[{e['type']}] {e['src']}\n"
        if nid in self.error_handlers:
            info += "\n  This class IS an error handler.\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def ErrorReport(self):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        r = "=== ERROR REPORT ===\n\n"
        r += "Config.GRAPH_CLASSES WITH ERROR HANDLING:\n"
        for nid in self.node_ids:
            errors = self.class_errors.get(nid, [])
            if errors:
                r += f"  {nid} ({len(errors)} errors):\n"
                for err in errors:
                    r += f"    ! {err}\n"
        r += "\n"
        r += "Config.GRAPH_CLASSES WITH NO ERROR HANDLING:\n"
        no_err = [nid for nid in self.node_ids if not self.class_errors.get(nid)]
        for nid in no_err:
            r += f"  ! {nid} -- no error path defined\n"
        r += "\n"
        r += f"RECOVERY ROUTES ({len(self.recovery_edges)}):\n"
        for e in self.recovery_edges:
            r += f"  {e['src']} ->[{e['type']}] {e['dst']}\n"
        r += "\n"
        r += f"ERROR HANDLERS: {sorted(self.error_handlers)}\n"
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