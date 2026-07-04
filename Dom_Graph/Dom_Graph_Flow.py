from Config import Config
#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Spec Flow Analyzer with relationship graph and execution flow graph. Tkinter GUI. No #[@...] headers. No Run dispatch. No Tuple3 returns. Import before shebang. Has hardcoded color values and window geometry. Uses tkinter. Single class SpecFlow but no VBStyle compliance.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Move import after shebang. Move hardcoded colors/geometry to Config.py.>]}
"""Spec Flow Analyzer — relationship graph + execution flow graph for pre-build planning."""
import math, tkinter as tk
from tkinter import ttk
class SpecFlow:
    def __init__(self, root):
        self.root = root
        self.root.title("Dom_Graph — Spec Flow Analyzer")
        self.root.geometry("1500x950")
        self.root.configure(bg="#1e1e2e")
        self.mode = "relationship"
        self.selected_node = None
        self.hover_node = None
        self.node_items = {}
        self.node_positions = {}
        self.active_cats = set(Config.GRAPH_CATEGORIES.keys())
        self.nodes = [{"id":n[0],"type":n[1],"dispatch":n[2],"desc":n[3]} for n in Config.GRAPH_CLASSES]
        self.edges = [{"src":e[0],"dst":e[1],"type":e[2]} for e in Config.GRAPH_EDGES]
        self.node_map = {n["id"]:n for n in self.nodes}
        self.BuildUI()
        self.UpdateLegend()
        self.DrawGraph()
    def BuildUI(self):
        top = tk.Frame(self.root, bg="#1e1e2e", height=50)
        top.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(top, text="Dom_Graph — Spec Flow Analyzer", fg="#cdd6f4", bg="#1e1e2e", font=("Helvetica",16,"bold")).pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="relationship")
        tk.Radiobutton(top, text="Relationship", variable=self.mode_var, value="relationship", command=self.SwitchMode, bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", font=("Helvetica",10)).pack(side=tk.LEFT, padx=15)
        tk.Radiobutton(top, text="Flow", variable=self.mode_var, value="flow", command=self.SwitchMode, bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", font=("Helvetica",10)).pack(side=tk.LEFT, padx=5)
        tk.Label(top, text=f"  Classes={len(self.nodes)} Edges={len(self.edges)}", fg="#94a3b8", bg="#1e1e2e", font=("Helvetica",11)).pack(side=tk.LEFT, padx=10)
        tk.Button(top, text="Gap Analysis", command=self.GapAnalysis, bg="#313244", fg="#cdd6f4", relief=tk.FLAT, font=("Helvetica",10), padx=10).pack(side=tk.RIGHT, padx=5)
        self.class_var = tk.StringVar(value="Compress")
        tk.Label(top, text="Class:", fg="#94a3b8", bg="#1e1e2e", font=("Helvetica",10)).pack(side=tk.RIGHT, padx=5)
        cb = ttk.Combobox(top, textvariable=self.class_var, values=[c[0] for c in Config.GRAPH_CLASSES], state="readonly", width=15, font=("Helvetica",10))
        cb.pack(side=tk.RIGHT, padx=2)
        cb.bind("<<ComboboxSelected>>", self.OnClassSelect)
        self.filter_frame = tk.Frame(self.root, bg="#1e1e2e")
        self.filter_frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(self.filter_frame, text="Filter:", fg="#94a3b8", bg="#1e1e2e", font=("Helvetica",10)).pack(side=tk.LEFT)
        self.cat_vars = {}
        for cat, color in Config.GRAPH_CATEGORIES.items():
            cnt = sum(1 for n in self.nodes if n["type"]==cat)
            var = tk.IntVar(value=1)
            self.cat_vars[cat] = var
            tk.Checkbutton(self.filter_frame, text=f"{cat} ({cnt})", variable=var, bg="#1e1e2e", fg=color, selectcolor="#313244", font=("Helvetica",9), command=self.OnFilterChange).pack(side=tk.LEFT, padx=3)
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(main, bg="#11111b", highlightthickness=0, cursor="hand2")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        df = tk.Frame(main, bg="#1e1e2e", width=450)
        df.pack(side=tk.RIGHT, fill=tk.Y, padx=(10,0))
        df.pack_propagate(False)
        self.detail_label = tk.Label(df, text="Details", fg="#cdd6f4", bg="#1e1e2e", font=("Helvetica",13,"bold"))
        self.detail_label.pack(anchor=tk.W, padx=10, pady=(10,5))
        self.detail_text = tk.Text(df, bg="#181825", fg="#cdd6f4", font=("Courier",10), wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10, state=tk.DISABLED)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        self.legend_frame = tk.Frame(df, bg="#1e1e2e")
        self.legend_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        self.canvas.bind("<Motion>", self.OnMotion)
        self.canvas.bind("<Button-1>", self.OnClick)
        self.canvas.bind("<Configure>", self.OnResize)
        return (1, None, None)
    def UpdateLegend(self):
        for w in self.legend_frame.winfo_children():
            w.destroy()
        tk.Label(self.legend_frame, text="Legend:", fg="#cdd6f4", bg="#1e1e2e", font=("Helvetica",10,"bold")).pack(anchor=tk.W)
        if self.mode == "relationship":
            tk.Label(self.legend_frame, text="Categories:", fg="#cdd6f4", bg="#1e1e2e", font=("Helvetica",9,"bold")).pack(anchor=tk.W)
            for cat, color in Config.GRAPH_CATEGORIES.items():
                cnt = sum(1 for n in self.nodes if n["type"]==cat)
                row = tk.Frame(self.legend_frame, bg="#1e1e2e")
                row.pack(fill=tk.X, pady=1)
                tk.Canvas(row, width=12, height=12, bg="#1e1e2e", highlightthickness=0).create_oval(2,2,10,10, fill=color, outline="")
                tk.Label(row, text=f" {cat} ({cnt})", fg=color, bg="#1e1e2e", font=("Helvetica",9)).pack(side=tk.LEFT)
            tk.Label(self.legend_frame, text="", bg="#1e1e2e").pack()
            tk.Label(self.legend_frame, text="Edges:", fg="#cdd6f4", bg="#1e1e2e", font=("Helvetica",9,"bold")).pack(anchor=tk.W)
            for et, ec in Config.GRAPH_EDGE_COLORS.items():
                row = tk.Frame(self.legend_frame, bg="#1e1e2e")
                row.pack(fill=tk.X, pady=1)
                tk.Canvas(row, width=20, height=12, bg="#1e1e2e", highlightthickness=0).create_line(2,6,18,6, fill=ec, width=2)
                tk.Label(row, text=f" {et}", fg=ec, bg="#1e1e2e", font=("Helvetica",9)).pack(side=tk.LEFT)
        else:
            tk.Label(self.legend_frame, text="Step Types:", fg="#cdd6f4", bg="#1e1e2e", font=("Helvetica",9,"bold")).pack(anchor=tk.W)
            for st, sc in Config.GRAPH_FLOW_COLORS.items():
                row = tk.Frame(self.legend_frame, bg="#1e1e2e")
                row.pack(fill=tk.X, pady=1)
                tk.Canvas(row, width=16, height=12, bg="#1e1e2e", highlightthickness=0).create_rectangle(2,1,14,11, fill=sc, outline="")
                tk.Label(row, text=f" {st}", fg=sc, bg="#1e1e2e", font=("Helvetica",9)).pack(side=tk.LEFT)
        return (1, None, None)
    def SwitchMode(self):
        self.mode = self.mode_var.get()
        if self.mode == "flow":
            self.filter_frame.pack_forget()
            self.detail_label.config(text=f"Flow: {self.class_var.get()}")
        else:
            self.filter_frame.pack(fill=tk.X, padx=10, pady=2)
            self.canvas.master.master.pack_children(before=self.canvas)
            self.detail_label.config(text="Class Details")
        self.UpdateLegend()
        self.DrawGraph()
        return (1, None, None)
    def OnClassSelect(self, event):
        if self.mode == "flow":
            self.detail_label.config(text=f"Flow: {self.class_var.get()}")
            self.DrawGraph()
            self.ShowFlowDetail(self.class_var.get())
        return (1, None, None)
    def OnFilterChange(self):
        self.active_cats = {c for c,v in self.cat_vars.items() if v.get()}
        if self.mode == "relationship":
            self.DrawGraph()
        return (1, None, None)
    def DrawGraph(self):
        if self.mode == "relationship":
            self.DrawRel()
        else:
            self.DrawFlow()
        return (1, None, None)
    def DrawRel(self):
        self.canvas.delete("all")
        self.node_items = {}
        self.node_positions = {}
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        return (1, None, None)
        cx, cy, radius = w/2, h/2, min(w,h)/2 - 120
        visible = [n for n in self.nodes if n["type"] in self.active_cats]
        return (1, None, None)
        cat_nodes = {}
        for n in visible:
            cat_nodes.setdefault(n["type"], []).append(n)
        for ci, cat in enumerate(Config.GRAPH_CATEGORIES):
            if cat not in cat_nodes: continue
            ca = 2*math.pi*ci/len(Config.GRAPH_CATEGORIES) - math.pi/2
            cx2, cy2 = cx + radius*0.65*math.cos(ca), cy + radius*0.65*math.sin(ca)
            sr = 50 + len(cat_nodes[cat])*12
            for ni, node in enumerate(cat_nodes[cat]):
                sa = ca + (ni - len(cat_nodes[cat])/2 + 0.5) * (math.pi/7)
                self.node_positions[node["id"]] = (cx2 + sr*math.cos(sa), cy2 + sr*math.sin(sa))
        for e in self.edges:
            s, d = e["src"], e["dst"]
            if s not in self.node_positions or d not in self.node_positions: continue
            if self.node_map[s]["type"] not in self.active_cats or self.node_map[d]["type"] not in self.active_cats: continue
            x1,y1 = self.node_positions[s]
            x2,y2 = self.node_positions[d]
            self.canvas.create_line(x1,y1,x2,y2, fill=Config.GRAPH_EDGE_COLORS.get(e["type"],"#45475a"), width=2, arrow=tk.LAST, arrowshape=(8,8,6))
        for node in self.nodes:
            nid = node["id"]
            if nid not in self.node_positions or node["type"] not in self.active_cats: continue
            x, y = self.node_positions[nid]
            r = 18
            ol = "#f9e2af" if nid == self.selected_node else "#cdd6f4"
            ow = 3 if nid == self.selected_node else 1
            item = self.canvas.create_oval(x-r,y-r,x+r,y+r, fill=Config.GRAPH_CATEGORIES.get(node["type"],"#6c7086"), outline=ol, width=ow)
            self.node_items[item] = nid
            self.canvas.create_text(x, y+r+10, text=nid, fill="#cdd6f4", font=("Helvetica",8))
    def DrawFlow(self):
        self.canvas.delete("all")
        self.node_items = {}
        cn = self.class_var.get()
        flow = Config.GRAPH_FLOWS.get(cn, [])
        return (1, None, None)
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        return (1, None, None)
        bw, bh, gap = 380, 32, 12
        sx = w/2 - bw/2
        sy = 30
        for i in range(len(flow)-1):
            y1 = sy + i*(bh+gap)
            y2 = sy + (i+1)*(bh+gap)
            st2 = flow[i+1][0]
            lc = "#f38ba8" if st2 == "error" else "#45475a"
            self.canvas.create_line(sx+bw/2, y1+bh, sx+bw/2, y2, fill=lc, width=2, arrow=tk.LAST, arrowshape=(8,8,6))
        for i, (st, desc) in enumerate(flow):
            y = sy + i*(bh+gap)
            color = Config.GRAPH_FLOW_COLORS.get(st, "#6c7086")
            if st == "decision":
                cx2, cy2 = sx+bw/2, y+bh/2
                item = self.canvas.create_polygon(cx2,cy2-bh/2-3, sx+bw,cy2, cx2,cy2+bh/2+3, sx,cy2, fill=color, outline="#cdd6f4", width=1)
            else:
                item = self.canvas.create_rectangle(sx, y, sx+bw, y+bh, fill=color, outline="#cdd6f4", width=1)
            self.node_items[item] = i
            self.canvas.create_text(sx+5, y+bh/2, text=st.upper(), fill="#1e1e2e", font=("Helvetica",7,"bold"), anchor=tk.W)
            dd = desc if len(desc)<=65 else desc[:62]+"..."
            self.canvas.create_text(sx+bw/2, y+bh/2+1, text=dd, fill="#1e1e2e", font=("Helvetica",8))
        self.ShowFlowDetail(cn)
    def GetNodeAt(self, x, y):
        items = self.canvas.find_overlapping(x-5, y-5, x+5, y+5)
        for item in items:
            if item in self.node_items: return self.node_items[item]
        return (1, None, None)
    def OnMotion(self, event):
        node = self.GetNodeAt(event.x, event.y)
        if node != self.hover_node:
            self.hover_node = node
            self.canvas.configure(cursor="hand2" if node else "arrow")
        return (1, None, None)
    def OnClick(self, event):
        node = self.GetNodeAt(event.x, event.y)
        return (1, None, None)
        if self.mode == "relationship":
            self.selected_node = node
            self.ShowRelDetail(node)
            self.DrawRel()
        else:
            self.ShowFlowStep(self.class_var.get(), node)
    def OnResize(self, event):
        self.DrawGraph()
        return (1, None, None)
    def ShowRelDetail(self, nid):
        node = self.node_map.get(nid, {})
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        out = [e for e in self.edges if e["src"]==nid]
        inc = [e for e in self.edges if e["dst"]==nid]
        info = f"Class:    {nid}\nCategory: {node.get('type','?')}\nDispatch: {node.get('dispatch','?')}\nDesc:     {node.get('desc','')}\n\nOutgoing ({len(out)}):\n"
        for e in out: info += f"  ->[{e['type']}] {e['dst']}\n"
        info += f"\nIncoming ({len(inc)}):\n"
        for e in inc: info += f"  <-[{e['type']}] {e['src']}\n"
        if not out and not inc: info += "\n  ISOLATED!\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def ShowFlowDetail(self, cn):
        flow = Config.GRAPH_FLOWS.get(cn, [])
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        counts = {}
        for st, _ in flow: counts[st] = counts.get(st, 0) + 1
        info = f"Flow: {cn}\nSteps: {len(flow)}\n\nBreakdown:\n"
        for st in ["io","step","decision","call","return","error"]:
            if st in counts: info += f"  {st}: {counts[st]}\n"
        has_error = "error" in counts
        has_return = "return" in counts
        has_decision = "decision" in counts
        info += f"\nChecks:\n  Has input: {'io' in counts}\n  Has output: {'return' in counts}\n  Has decisions: {has_decision}\n  Has error paths: {has_error}\n"
        if not has_error: info += "  ! NO ERROR HANDLING\n"
        if not has_return: info += "  ! NO RETURN POINT\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
        return (1, None, None)
    def ShowFlowStep(self, cn, idx):
        flow = Config.GRAPH_FLOWS.get(cn, [])
        return (1, None, None)
        st, desc = flow[idx]
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        info = f"Step {idx+1}/{len(flow)}\nType: {st}\nDesc: {desc}\n\n"
        if idx > 0: info += f"Prev: [{flow[idx-1][0]}] {flow[idx-1][1]}\n"
        if idx < len(flow)-1: info += f"Next: [{flow[idx+1][0]}] {flow[idx+1][1]}\n"
        self.detail_text.insert("1.0", info)
        self.detail_text.config(state=tk.DISABLED)
    def GapAnalysis(self):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        r = "=== GAP ANALYSIS ===\n\n"
        isolated = [n["id"] for n in self.nodes if not any(e["src"]==n["id"] or e["dst"]==n["id"] for e in self.edges)]
        r += f"ISOLATED ({len(isolated)}): {isolated or 'None'}\n\n"
        r += "Config.GRAPH_CATEGORIES:\n"
        for cat in Config.GRAPH_CATEGORIES:
            names = [n["id"] for n in self.nodes if n["type"]==cat]
            r += f"  {cat} ({len(names)}): {', '.join(names)}\n"
        r += "\nEXPECTED PAIRS:\n"
        for a,b in [("Compress","Extract"),("Encrypt","Decrypt"),("Split","Join"),("Write","Strip"),("Read","Write")]:
            has = any((e["src"]==a and e["dst"]==b) or (e["src"]==b and e["dst"]==a) for e in self.edges)
            r += f"  {a}<->{b}: {'OK' if has else 'MISSING!'}\n"
        r += f"\nTOTAL: {len(self.nodes)} classes, {len(self.edges)} edges\n"
        r += f"Flows defined: {len(Config.GRAPH_FLOWS)}/{len(self.nodes)}\n"
        missing_flows = [n["id"] for n in self.nodes if n["id"] not in Config.GRAPH_FLOWS]
        if missing_flows: r += f"MISSING Config.GRAPH_FLOWS: {missing_flows}\n"
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