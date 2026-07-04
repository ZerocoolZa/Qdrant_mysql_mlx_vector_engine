from Config import Config
#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Lifecycle Graph Viewer rendering WHEN classes run in domain lifecycle. Tkinter GUI with swim-lane layout. No #[@...] headers. No Run dispatch. No Tuple3 returns. Import before shebang. Has hardcoded color values and window geometry. Uses tkinter.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Move import after shebang. Move hardcoded colors/geometry to Config.py.>]}
"""
Lifecycle Graph Viewer -- renders WHEN each class runs in the domain lifecycle.
Sixth of the seven graph tools:
    spec_graph.py      -> "What exists?"
    spec_flow.py       -> "How does it move?"
    gap_graph.py       -> "What's missing?"
    dep_graph.py       -> "Why does it connect?"
    error_graph.py     -> "Where does it fail?"
    lifecycle_graph.py -> "When does it run?"   <-- this file
    orch_graph.py      -> "Who calls who?"
Shows the temporal ordering of classes across lifecycle phases:
    CREATE -> READ -> UPDATE -> DESTROY -> VERIFY -> RECOVER
Each class is mapped to a phase. The swim-lane layout shows which classes
run at which stage, and temporal arrows show the expected progression.
"""
import math
import tkinter as tk
from collections import defaultdict
# ─── Shared spec data ────────────────────────────────────────────────────────
# ─── Lifecycle phases (temporal ordering) ─────────────────────────────────────
# Each phase is a stage in the life of an archive.
# Classes are mapped to the phase where they primarily operate.
class LifecycleGraph:
    """Visual graph of temporal lifecycle phases and when classes run."""
    def __init__(self, root):
        self.root = root
        self.root.title("dom_compression -- Lifecycle Graph (When does it run?)")
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
        # Group classes by phase
        self.phase_classes = defaultdict(list)
        for nid in self.node_ids:
            phase = Config.GRAPH_CLASS_PHASE.get(nid, "READ")
            self.phase_classes[phase].append(nid)
        self.BuildUI()
        self.UpdateLegend()
        self.LayoutNodes()
    def BuildUI(self):
        top = tk.Frame(self.root, bg="#1e1e2e", height=50)
        top.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(top, text="dom_compression -- Lifecycle Graph (When does it run?)",
                 fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
        info = f"  Classes={len(self.nodes)}  Phases={len(Config.GRAPH_LIFECYCLE_PHASES)}"
        tk.Label(top, text=info, fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 11)).pack(side=tk.LEFT, padx=10)
        tk.Button(top, text="Lifecycle Report", command=self.LifecycleReport,
                  bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(side=tk.RIGHT, padx=5)
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(main, bg="#11111b", highlightthickness=0, cursor="hand2")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        df = tk.Frame(main, bg="#1e1e2e", width=450)
        df.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        df.pack_propagate(False)
        tk.Label(df, text="Lifecycle Details", fg="#cdd6f4", bg="#1e1e2e",
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
        tk.Label(self.legend_frame, text="Lifecycle Phases:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        for name, color, desc in Config.GRAPH_LIFECYCLE_PHASES:
            cnt = len(self.phase_classes.get(name, []))
            row = tk.Frame(self.legend_frame, bg="#1e1e2e")
            row.pack(fill=tk.X, pady=1)
            c = tk.Canvas(row, width=12, height=12, bg="#1e1e2e", highlightthickness=0)
            c.pack(side=tk.LEFT)
            c.create_rectangle(2, 2, 10, 10, fill=color, outline="")
            tk.Label(row, text=f" {name} ({cnt}) -- {desc}", fg=color, bg="#1e1e2e",
                     font=("Helvetica", 8)).pack(side=tk.LEFT)
        return (1, None, None)
    def LayoutNodes(self):
        """Swim-lane layout: phases as horizontal lanes, classes within each lane."""
        self.node_positions = {}
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 1400, 900
        lane_h = h / len(Config.GRAPH_LIFECYCLE_PHASES)
        for pi, (phase_name, _, _) in enumerate(Config.GRAPH_LIFECYCLE_PHASES):
            classes = self.phase_classes.get(phase_name, [])
            n = len(classes)
            if n == 0:
                continue
            spacing = (w - 120) / max(n, 1)
            for ci, nid in enumerate(classes):
                x = 60 + spacing * (ci + 0.5)
                y = lane_h * pi + lane_h / 2
                self.node_positions[nid] = (x, y)
        return (1, None, None)
    def DrawGraph(self):
        self.canvas.delete("all")
        self.node_items = {}
        if self.canvas.winfo_width() > 1:
            self.LayoutNodes()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 1400, 900
        # Draw phase lanes (background bands)
        lane_h = h / len(Config.GRAPH_LIFECYCLE_PHASES)
        for pi, (phase_name, color, desc) in enumerate(Config.GRAPH_LIFECYCLE_PHASES):
            y1 = lane_h * pi
            y2 = lane_h * (pi + 1)
            self.canvas.create_rectangle(0, y1, w, y2, fill=color, stipple="gray12", outline="")
            self.canvas.create_text(10, y1 + 15, text=phase_name, fill=color,
                                    anchor=tk.W, font=("Helvetica", 12, "bold"))
            self.canvas.create_text(10, y1 + 32, text=desc, fill="#6c7086",
                                    anchor=tk.W, font=("Helvetica", 7))
        # Draw temporal progression arrows between phases
        for pi in range(len(Config.GRAPH_LIFECYCLE_PHASES) - 1):
            y1 = lane_h * (pi + 1) - 15
            y2 = lane_h * (pi + 1) + 15
            self.canvas.create_line(w - 30, y1, w - 30, y2, fill="#cdd6f4", width=2,
                                    arrow=tk.LAST, arrowshape=(8, 8, 6))
        # Draw edges (only between classes in adjacent or same phases)
        for e in self.edges:
            s, d = e["src"], e["dst"]
            if s not in self.node_positions or d not in self.node_positions:
                continue
            x1, y1 = self.node_positions[s]
            x2, y2 = self.node_positions[d]
            self.canvas.create_line(x1, y1, x2, y2, fill="#45475a", width=1,
                                    arrow=tk.LAST, arrowshape=(6, 6, 4))
        # Draw nodes
        for node in self.nodes:
            nid = node["id"]
            if nid not in self.node_positions:
                continue
            x, y = self.node_positions[nid]
            r = 16
            phase = Config.GRAPH_CLASS_PHASE.get(nid, "READ")
            fill = Config.GRAPH_PHASE_COLORS.get(phase, "#6c7086")
            ol = "#f9e2af" if nid == self.selected_node else "#1e1e2e"
            ow = 3 if nid == self.selected_node else 1
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill=fill, outline=ol, width=ow)
            self.node_items[item] = nid
            self.canvas.create_text(x, y + r + 8, text=nid,
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
        phase = Config.GRAPH_CLASS_PHASE.get(nid, "READ")
        phase_idx = Config.GRAPH_PHASE_ORDER.index(phase) if phase in Config.GRAPH_PHASE_ORDER else -1
        info = f"Class:    {nid}\nCategory: {node.get('type', '?')}\nPhase:    {phase} (stage {phase_idx + 1}/{len(Config.GRAPH_PHASE_ORDER)})\n\n"
        # Temporal predecessors (classes in earlier phases that connect to this)
        predecessors = []
        for e in self.edges:
            if e["dst"] == nid:
                src_phase = Config.GRAPH_CLASS_PHASE.get(e["src"], "READ")
                if Config.GRAPH_PHASE_ORDER.index(src_phase) < phase_idx:
                    predecessors.append((e["src"], e["type"], src_phase))
        if predecessors:
            info += "Temporal predecessors (runs before):\n"
            for src, etype, sp in predecessors:
                info += f"  <-[{etype}] {src} ({sp})\n"
        else:
            info += "Temporal predecessors: none (entry point)\n"
        # Temporal successors (classes in later phases)
        successors = []
        for e in self.edges:
            if e["src"] == nid:
                dst_phase = Config.GRAPH_CLASS_PHASE.get(e["dst"], "READ")
                if Config.GRAPH_PHASE_ORDER.index(dst_phase) > phase_idx:
                    successors.append((e["dst"], e["type"], dst_phase))
        if successors:
            info += "\nTemporal successors (runs after):\n"
            for dst, etype, dp in successors:
                info += f"  ->[{etype}] {dst} ({dp})\n"
        else:
            info += "\nTemporal successors: none (terminal point)\n"
        # Same-phase peers
        peers = [c for c in self.phase_classes.get(phase, []) if c != nid]
        if peers:
            info += f"\nSame-phase peers ({phase}): {', '.join(peers)}\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def LifecycleReport(self):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        r = "=== LIFECYCLE REPORT ===\n\n"
        for phase_name, color, desc in Config.GRAPH_LIFECYCLE_PHASES:
            classes = self.phase_classes.get(phase_name, [])
            r += f"{phase_name} -- {desc}\n"
            r += f"  Classes ({len(classes)}): {', '.join(classes)}\n\n"
        r += "TEMPORAL FLOW:\n"
        r += "  " + " -> ".join(Config.GRAPH_PHASE_ORDER) + "\n"
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
    app = LifecycleGraph(root)
    root.mainloop()
