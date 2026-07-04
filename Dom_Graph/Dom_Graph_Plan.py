from Config import Config
#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Plan Graph Viewer — editable pre-spec entry point. Tkinter GUI with candidate extraction, drag nodes, export to SPEC.md. No #[@...] headers. No Run dispatch. No Tuple3 returns. Import before shebang. Mutates Config at runtime (GRAPH_CATEGORY_ORDER, GRAPH_OPERATION_VERBS). Has hardcoded color values and window geometry. Uses tkinter.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Move import after shebang. Stop mutating Config at runtime. Move hardcoded data to Config.py.>]}
"""
Plan Graph Viewer -- the pre-spec entry point of the spec engine.
Eighth and final viewer:
    plan_graph.py      -> "What's the dream?"   <-- this file (EDITABLE)
    spec_graph.py      -> "What exists?"
    spec_flow.py       -> "How does it move?"
    gap_graph.py       -> "What's missing?"
    dep_graph.py       -> "Why does it connect?"
    error_graph.py     -> "Where does it fail?"
    lifecycle_graph.py -> "When does it run?"
    orch_graph.py      -> "Who calls who?"
The other 7 are read-only inspectors of a finished spec. The Plan Graph
is the only one that is EDITABLE -- you build the shape here, then export
it as SPEC.md for the other viewers to inspect.
Workflow:
    1. Paste/type a raw idea in the left panel
    2. Click "Extract Candidates" -- heuristic noun/verb phrase detection
       proposes candidate classes
    3. Drag nodes on the canvas to group them visually
    4. Click a node to cycle its category color
    5. Double-click to rename, right-click to delete
    6. Add new nodes manually with the "Add Node" button
    7. Export to SPEC.md when the plan looks right
"""
import json
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
# ─── Categories (shared with all viewers) ─────────────────────────────────────
Config.GRAPH_CATEGORY_ORDER = ["CRUD", "INTEGRITY", "TRANSFORM", "SECURITY", "UTILITY", "META"]
# ─── Candidate extraction heuristics ─────────────────────────────────────────
# Known operation verbs that map to common VBStyle class names.
# These are domain-agnostic patterns that appear across many domains.
Config.GRAPH_OPERATION_VERBS = [
    "compress", "extract", "read", "write", "info", "list", "search", "stream",
    "convert", "verify", "split", "join", "encrypt", "decrypt", "repair",
    "strip", "rename", "merge", "diff", "optimize", "benchmark", "hash",
    "walk", "batch", "create", "delete", "update", "insert", "remove",
    "load", "save", "export", "import", "parse", "validate", "authenticate",
    "authorize", "configure", "monitor", "log", "cache", "sync", "backup",
    "restore", "archive", "scan", "filter", "sort", "count", "check",
    "test", "debug", "trace", "profile", "schedule", "queue", "dispatch",
    "render", "format", "encode", "decode", "pack", "unpack", "send",
    "receive", "connect", "disconnect", "open", "close", "start", "stop",
    "pause", "resume", "reset", "clear", "flush", "commit", "rollback",
]
# Map verbs to a default category
Config.GRAPH_VERB_CATEGORY = {
    "compress": "CRUD", "extract": "CRUD", "read": "CRUD", "write": "CRUD",
    "create": "CRUD", "delete": "CRUD", "update": "CRUD", "insert": "CRUD",
    "remove": "CRUD", "strip": "CRUD", "rename": "CRUD", "load": "CRUD",
    "save": "CRUD", "open": "CRUD", "close": "CRUD", "clear": "CRUD",
    "flush": "CRUD", "pack": "CRUD", "unpack": "CRUD",
    "verify": "INTEGRITY", "validate": "INTEGRITY", "check": "INTEGRITY",
    "test": "INTEGRITY", "hash": "INTEGRITY", "repair": "INTEGRITY",
    "scan": "INTEGRITY", "debug": "INTEGRITY", "trace": "INTEGRITY",
    "authenticate": "SECURITY", "authorize": "SECURITY",
    "encrypt": "SECURITY", "decrypt": "SECURITY",
    "convert": "TRANSFORM", "merge": "TRANSFORM", "split": "TRANSFORM",
    "join": "TRANSFORM", "optimize": "TRANSFORM", "format": "TRANSFORM",
    "encode": "TRANSFORM", "decode": "TRANSFORM",
    "search": "UTILITY", "stream": "UTILITY", "walk": "UTILITY",
    "batch": "UTILITY", "filter": "UTILITY", "sort": "UTILITY",
    "dispatch": "UTILITY", "queue": "UTILITY", "schedule": "UTILITY",
    "render": "UTILITY", "send": "UTILITY", "receive": "UTILITY",
    "connect": "UTILITY", "disconnect": "UTILITY",
    "info": "META", "list": "META", "diff": "META", "benchmark": "META",
    "count": "META", "profile": "META", "log": "META", "monitor": "META",
    "configure": "META",
    "export": "UTILITY", "import": "UTILITY", "parse": "UTILITY",
    "backup": "INTEGRITY", "restore": "INTEGRITY", "archive": "CRUD",
    "cache": "UTILITY", "sync": "UTILITY",
    "start": "UTILITY", "stop": "UTILITY", "pause": "UTILITY",
    "resume": "UTILITY", "reset": "UTILITY", "commit": "CRUD",
    "rollback": "INTEGRITY",
}
# Noun phrase pattern: Capitalized word or word followed by "archive/file/data/record"
NOUN_PATTERN = re.compile(
    r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)*)\b'  # PascalCase words
)
# Also catch "the X" or "a X" patterns where X is a meaningful noun
OPERATION_PATTERN = re.compile(
    r'\b(' + '|'.join(Config.GRAPH_OPERATION_VERBS) + r')\b',
    re.IGNORECASE
)
def ToPascalCase(word):
    """Convert a lowercase word to PascalCase."""
    if not word:
        return word
    return word[0].upper() + word[1:].lower()
def ExtractCandidates(text):
    """Extract candidate class names from raw idea text.
    Returns list of (name, category, dispatch, description) tuples."""
    found = {}  # name -> (category, dispatch, description)
    # 1. Find operation verbs
    for m in OPERATION_PATTERN.finditer(text):
        verb = m.group(1).lower()
        name = ToPascalCase(verb)
        if name not in found:
            cat = Config.GRAPH_VERB_CATEGORY.get(verb, "UTILITY")
            desc = f"{verb} operation"
            found[name] = (cat, verb, desc)
    # 2. Find PascalCase nouns (potential class names already named in the idea)
    for m in NOUN_PATTERN.finditer(text):
        name = m.group(1)
        if len(name) < 3:
            continue
        if name in found:
            continue
        # Skip common English words that happen to be PascalCase
        if name.lower() in {"the", "and", "but", "for", "not", "all", "any", "yes", "no",
                            "also", "then", "when", "what", "who", "how", "why", "where",
                            "this", "that", "these", "those", "some", "each", "both",
                            "into", "from", "with", "without", "about", "click"}:
            continue
        found[name] = ("META", name.lower(), f"{name} entity")
    # 3. Find "X manager/handler/engine/builder/factory" patterns
    role_pattern = re.compile(
        r'\b(\w+)\s+(manager|handler|engine|builder|factory|reader|writer|'
        r'parser|loader|saver|checker|validator|monitor|logger|cache|queue)\b',
        re.IGNORECASE
    )
    for m in role_pattern.finditer(text):
        prefix = m.group(1)
        role = m.group(2).lower()
        name = ToPascalCase(prefix) + ToPascalCase(role)
        if name not in found:
            cat = Config.GRAPH_VERB_CATEGORY.get(role, "UTILITY")
            found[name] = (cat, name.lower(), f"{prefix} {role}")
    return [(name, cat, disp, desc) for name, (cat, disp, desc) in found.items()]
class PlanNode:
    """A candidate class in the plan graph."""
    def __init__(self, root):
        self.root = root
        self.root.title("dom_compression -- Plan Graph (What's the dream?)")
        self.root.geometry("1500x950")
        self.root.configure(bg="#1e1e2e")
        self.nodes = []           # list of PlanNode
        self.selected = None      # selected node name
        self.hover_node = None
        self.dragging = None
        self.drag_offset = (0, 0)
        self.node_items = {}      # canvas item -> node name
        self.node_radius = 22
        self.plan_file = os.path.join(os.path.dirname(__file__), "plan_state.json")
        self.BuildUI()
        self.DrawGraph()
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
class PlanGraph:
    """Editable pre-spec graph -- idea -> structure -> SPEC.md export."""
    def __init__(self, root):
        self.root = root
        self.root.title("dom_compression -- Plan Graph (What's the dream?)")
        self.root.geometry("1500x950")
        self.root.configure(bg="#1e1e2e")
        self.nodes = []           # list of PlanNode
        self.selected = None      # selected node name
        self.hover_node = None
        self.dragging = None
        self.drag_offset = (0, 0)
        self.node_items = {}      # canvas item -> node name
        self.node_radius = 22
        self.plan_file = os.path.join(os.path.dirname(__file__), "plan_state.json")
        self.BuildUI()
        self.DrawGraph()
    def BuildUI(self):
        # Top bar
        top = tk.Frame(self.root, bg="#1e1e2e", height=50)
        top.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(top, text="dom_compression -- Plan Graph (What's the dream?)",
                 fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
        cnt_label_text = f"  Candidates={len(self.nodes)}"
        self.count_label = tk.Label(top, text=cnt_label_text, fg="#94a3b8",
                                    bg="#1e1e2e", font=("Helvetica", 11))
        self.count_label.pack(side=tk.LEFT, padx=10)
        tk.Button(top, text="Export SPEC.md", command=self.ExportSpec,
                  bg="#a6e3a1", fg="#1e1e2e", relief=tk.FLAT,
                  font=("Helvetica", 10, "bold"), padx=10).pack(side=tk.RIGHT, padx=5)
        tk.Button(top, text="Save Plan", command=self.SavePlan,
                  bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(side=tk.RIGHT, padx=5)
        tk.Button(top, text="Load Plan", command=self.LoadPlan,
                  bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(side=tk.RIGHT, padx=5)
        # Main area: 3 panels
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        # Left: idea input
        left = tk.Frame(main, bg="#1e1e2e", width=350)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left.pack_propagate(False)
        tk.Label(left, text="Raw Idea / Conversation", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))
        self.idea_text = tk.Text(left, bg="#181825", fg="#cdd6f4",
                                 font=("Courier", 10), wrap=tk.WORD,
                                 relief=tk.FLAT, padx=10, pady=10)
        self.idea_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        self.idea_text.insert("1.0",
            "Paste your raw idea here.\n\n"
            "Example:\n"
            "I want a module that can compress files into zip, tar, gz. "
            "It should extract them back. I need to read files inside archives "
            "without extracting. I want to search inside archives. "
            "It should verify integrity and repair corrupted ones. "
            "I need encrypt and decrypt with passwords. "
            "Split large archives into parts and join them back.\n\n"
            "Click 'Extract Candidates' to scan for class names."
        )
        btn_frame = tk.Frame(left, bg="#1e1e2e")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(btn_frame, text="Extract Candidates", command=self.ExtractFromIdea,
                  bg="#89b4fa", fg="#1e1e2e", relief=tk.FLAT,
                  font=("Helvetica", 10, "bold"), padx=10).pack(fill=tk.X, pady=2)
        tk.Button(btn_frame, text="Add Node", command=self.AddNode,
                  bg="#313244", fg="#cdd6f4", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(fill=tk.X, pady=2)
        tk.Button(btn_frame, text="Clear All", command=self.ClearAll,
                  bg="#f38ba8", fg="#1e1e2e", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(fill=tk.X, pady=2)
        # Instructions
        tk.Label(left, text="", bg="#1e1e2e").pack()
        tk.Label(left, text="Controls:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W, padx=10)
        tk.Label(left, text="  Drag: move node\n"
                            "  Click: select + cycle category\n"
                            "  Double-click: rename\n"
                            "  Right-click: delete\n"
                            "  Shift+click: edit description",
                 fg="#94a3b8", bg="#1e1e2e", justify=tk.LEFT,
                 font=("Helvetica", 9)).pack(anchor=tk.W, padx=10)
        # Center: canvas
        self.canvas = tk.Canvas(main, bg="#11111b", highlightthickness=0,
                                cursor="hand2")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Right: detail panel
        right = tk.Frame(main, bg="#1e1e2e", width=400)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right.pack_propagate(False)
        tk.Label(right, text="Node Properties", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 13, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))
        # Editable fields
        form = tk.Frame(right, bg="#1e1e2e")
        form.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(form, text="Name:", fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 10)).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(form, textvariable=self.name_var, bg="#181825",
                                   fg="#cdd6f4", font=("Helvetica", 10), width=25)
        self.name_entry.grid(row=0, column=1, pady=2, padx=5)
        tk.Label(form, text="Dispatch:", fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 10)).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.dispatch_var = tk.StringVar()
        self.dispatch_entry = tk.Entry(form, textvariable=self.dispatch_var,
                                       bg="#181825", fg="#cdd6f4",
                                       font=("Helvetica", 10), width=25)
        self.dispatch_entry.grid(row=1, column=1, pady=2, padx=5)
        tk.Label(form, text="Category:", fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 10)).grid(row=2, column=0, sticky=tk.W, pady=2)
        self.cat_var = tk.StringVar(value="UTILITY")
        self.cat_combo = tk.OptionMenu(form, self.cat_var, *Config.GRAPH_CATEGORY_ORDER,
                                       command=self.OnCategoryChange)
        self.cat_combo.config(bg="#181825", fg="#cdd6f4", font=("Helvetica", 10))
        self.cat_combo.grid(row=2, column=1, pady=2, padx=5, sticky=tk.W)
        tk.Label(form, text="Description:", fg="#94a3b8", bg="#1e1e2e",
                 font=("Helvetica", 10)).grid(row=3, column=0, sticky=tk.NW, pady=2)
        self.desc_text = tk.Text(form, bg="#181825", fg="#cdd6f4",
                                 font=("Helvetica", 10), width=25, height=3,
                                 relief=tk.FLAT)
        self.desc_text.grid(row=3, column=1, pady=2, padx=5)
        tk.Button(right, text="Apply Changes", command=self.ApplyNodeEdit,
                  bg="#a6e3a1", fg="#1e1e2e", relief=tk.FLAT,
                  font=("Helvetica", 10, "bold"), padx=10).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(right, text="Delete Node", command=self.DeleteSelected,
                  bg="#f38ba8", fg="#1e1e2e", relief=tk.FLAT,
                  font=("Helvetica", 10), padx=10).pack(fill=tk.X, padx=10, pady=2)
        # Legend
        tk.Label(right, text="", bg="#1e1e2e").pack()
        tk.Label(right, text="Categories:", fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W, padx=10)
        for cat, color in Config.GRAPH_CATEGORIES.items():
            row = tk.Frame(right, bg="#1e1e2e")
            row.pack(fill=tk.X, padx=10, pady=1)
            c = tk.Canvas(row, width=12, height=12, bg="#1e1e2e", highlightthickness=0)
            c.pack(side=tk.LEFT)
            c.create_oval(2, 2, 10, 10, fill=color, outline="")
            tk.Label(row, text=f" {cat}", fg=color, bg="#1e1e2e",
                     font=("Helvetica", 9)).pack(side=tk.LEFT)
        # Canvas bindings
        self.canvas.bind("<Button-1>", self.OnClick)
        self.canvas.bind("<B1-Motion>", self.OnDrag)
        self.canvas.bind("<ButtonRelease-1>", self.OnRelease)
        self.canvas.bind("<Double-Button-1>", self.OnDoubleClick)
        self.canvas.bind("<Button-3>", self.OnRightClick)
        self.canvas.bind("<Shift-Button-1>", self.OnShiftClick)
        self.canvas.bind("<Motion>", self.OnMotion)
        self.canvas.bind("<Configure>", self.OnResize)
        return (1, None, None)
    def ExtractFromIdea(self):
        text = self.idea_text.get("1.0", tk.END)
        candidates = ExtractCandidates(text)
        if not candidates:
            messagebox.showinfo("Extract", "No candidates found in the idea text.")
            return (1, None, None)
        # Place new nodes in a grid on the canvas
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 800, 600
        existing_names = {n.name for n in self.nodes}
        added = 0
        cols = max(w // 120, 4)
        start_x = 80
        start_y = 80
        for i, (name, cat, disp, desc) in enumerate(candidates):
            if name in existing_names:
                continue
            col = i % cols
            row = i // cols
            x = start_x + col * 120
            y = start_y + row * 100
            self.nodes.append(PlanNode(name, cat, disp, desc, x, y))
            added += 1
        self.UpdateCount()
        self.DrawGraph()
        messagebox.showinfo("Extract",
                            f"Extracted {added} new candidates.\n"
                            f"Total nodes: {len(self.nodes)}")
    def AddNode(self):
        name = f"Class{len(self.nodes) + 1}"
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            w, h = 800, 600
        node = PlanNode(name, "UTILITY", name.lower(), "New class", w // 2, h // 2)
        self.nodes.append(node)
        self.selected = name
        self.UpdateCount()
        self.DrawGraph()
        self.ShowNodeProperties(name)
        return (1, None, None)
    def ClearAll(self):
        if messagebox.askyesno("Clear", "Delete all nodes?"):
            self.nodes = []
            self.selected = None
            self.UpdateCount()
            self.DrawGraph()
            self.ClearProperties()
        return (1, None, None)
    def DeleteSelected(self):
        if not self.selected:
            return (1, None, None)
        self.nodes = [n for n in self.nodes if n.name != self.selected]
        self.selected = None
        self.UpdateCount()
        self.DrawGraph()
        self.ClearProperties()
    def DeleteNode(self, name):
        self.nodes = [n for n in self.nodes if n.name != name]
        if self.selected == name:
            self.selected = None
            self.ClearProperties()
        self.UpdateCount()
        self.DrawGraph()
        return (1, None, None)
    def CycleCategory(self, name):
        node = self.FindNode(name)
        if not node:
            return (1, None, None)
        idx = Config.GRAPH_CATEGORY_ORDER.index(node.category) if node.category in Config.GRAPH_CATEGORY_ORDER else 0
        node.category = Config.GRAPH_CATEGORY_ORDER[(idx + 1) % len(Config.GRAPH_CATEGORY_ORDER)]
        self.DrawGraph()
        self.ShowNodeProperties(name)
    def FindNode(self, name):
        for n in self.nodes:
            if n.name == name:
                return (1, n, None)
        return (1, None, None)
    def GetNodeAt(self, x, y):
        for n in self.nodes:
            dx = x - n.x
            dy = y - n.y
            if dx * dx + dy * dy <= self.node_radius * self.node_radius:
                return (1, n.name, None)
        return (1, None, None)
    def DrawGraph(self):
        self.canvas.delete("all")
        self.node_items = {}
        for node in self.nodes:
            x, y = node.x, node.y
            r = self.node_radius
            fill = Config.GRAPH_CATEGORIES.get(node.category, "#6c7086")
            ol = "#f9e2af" if node.name == self.selected else "#cdd6f4"
            ow = 3 if node.name == self.selected else 1
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill=fill, outline=ol, width=ow)
            self.node_items[item] = node.name
            self.canvas.create_text(x, y, text=node.name[:8],
                                    fill="#1e1e2e", font=("Helvetica", 7, "bold"))
            self.canvas.create_text(x, y + r + 10, text=node.name,
                                    fill="#cdd6f4", font=("Helvetica", 8))
            self.canvas.create_text(x, y + r + 22, text=node.category,
                                    fill=Config.GRAPH_CATEGORIES.get(node.category, "#6c7086"),
                                    font=("Helvetica", 7))
        return (1, None, None)
    def UpdateCount(self):
        self.count_label.config(text=f"  Candidates={len(self.nodes)}")
        return (1, None, None)
    def OnMotion(self, event):
        node = self.GetNodeAt(event.x, event.y)
        if node != self.hover_node:
            self.hover_node = node
            self.canvas.configure(cursor="hand2" if node else "arrow")
        return (1, None, None)
    def OnClick(self, event):
        node_name = self.GetNodeAt(event.x, event.y)
        if node_name:
            self.selected = node_name
            node = self.FindNode(node_name)
            if node:
                self.dragging = node_name
                self.drag_offset = (event.x - node.x, event.y - node.y)
            self.ShowNodeProperties(node_name)
            self.DrawGraph()
        else:
            self.selected = None
            self.ClearProperties()
            self.DrawGraph()
        return (1, None, None)
    def OnDrag(self, event):
        if self.dragging:
            node = self.FindNode(self.dragging)
            if node:
                node.x = event.x - self.drag_offset[0]
                node.y = event.y - self.drag_offset[1]
                self.DrawGraph()
        return (1, None, None)
    def OnRelease(self, event):
        self.dragging = None
        return (1, None, None)
    def OnDoubleClick(self, event):
        node_name = self.GetNodeAt(event.x, event.y)
        if node_name:
            new_name = self.PromptString("Rename Node", "New name:", node_name)
            if new_name and new_name != node_name:
                node = self.FindNode(node_name)
                if node:
                    node.name = new_name
                    node.dispatch = new_name.lower()
                    self.selected = new_name
                    self.DrawGraph()
                    self.ShowNodeProperties(new_name)
        return (1, None, None)
    def OnRightClick(self, event):
        node_name = self.GetNodeAt(event.x, event.y)
        if node_name:
            self.DeleteNode(node_name)
        return (1, None, None)
    def OnShiftClick(self, event):
        node_name = self.GetNodeAt(event.x, event.y)
        if node_name:
            self.selected = node_name
            self.ShowNodeProperties(node_name)
            self.DrawGraph()
        return (1, None, None)
    def OnResize(self, event):
        self.DrawGraph()
        return (1, None, None)
    def PromptString(self, title, prompt, default=""):
        """Simple prompt dialog using a Toplevel window."""
        result = [default]
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.geometry("300x120")
        dlg.configure(bg="#1e1e2e")
        dlg.transient(self.root)
        dlg.grab_set()
        tk.Label(dlg, text=prompt, fg="#cdd6f4", bg="#1e1e2e",
                 font=("Helvetica", 11)).pack(pady=10)
        entry = tk.Entry(dlg, bg="#181825", fg="#cdd6f4", font=("Helvetica", 11),
                         width=30)
        entry.insert(0, default)
        entry.pack(pady=5)
        entry.focus_set()
        entry.select_range(0, tk.END)
        def on_ok():
            result[0] = entry.get()
            dlg.destroy()
        def on_cancel():
            result[0] = None
            dlg.destroy()
        btn_frame = tk.Frame(dlg, bg="#1e1e2e")
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="OK", command=on_ok, bg="#a6e3a1", fg="#1e1e2e",
                  relief=tk.FLAT, font=("Helvetica", 10), padx=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=on_cancel, bg="#313244", fg="#cdd6f4",
                  relief=tk.FLAT, font=("Helvetica", 10), padx=15).pack(side=tk.LEFT, padx=5)
        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: on_cancel())
        self.root.wait_window(dlg)
        return (1, result[0], None)
    def ShowNodeProperties(self, name):
        node = self.FindNode(name)
        if not node:
            return (1, None, None)
        self.name_var.set(node.name)
        self.dispatch_var.set(node.dispatch)
        self.cat_var.set(node.category)
        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert("1.0", node.description)
    def ClearProperties(self):
        self.name_var.set("")
        self.dispatch_var.set("")
        self.cat_var.set("UTILITY")
        self.desc_text.delete("1.0", tk.END)
        return (1, None, None)
    def ApplyNodeEdit(self):
        if not self.selected:
            return (1, None, None)
        node = self.FindNode(self.selected)
        if not node:
            return (1, None, None)
        node.name = self.name_var.get() or node.name
        node.dispatch = self.dispatch_var.get() or node.name.lower()
        node.category = self.cat_var.get()
        node.description = self.desc_text.get("1.0", tk.END).strip()
        self.selected = node.name
        self.DrawGraph()
    def OnCategoryChange(self, value):
        if self.selected:
            node = self.FindNode(self.selected)
            if node:
                node.category = value
                self.DrawGraph()
        return (1, None, None)
    def ExportSpec(self):
        if not self.nodes:
            messagebox.showwarning("Export", "No nodes to export. Add some candidates first.")
            return (1, None, None)
        spec_path = os.path.join(os.path.dirname(__file__), "SPEC_EXPORTED.md")
        lines = []
        lines.append("# Exported Spec (from Plan Graph)\n")
        lines.append("## Domain Name\n`exported_domain`\n")
        lines.append("## Purpose\nAuto-generated from Plan Graph candidates.\n")
        lines.append("## Classes\n")
        for i, node in enumerate(sorted(self.nodes, key=lambda n: n.name)):
            lines.append(f"### {i + 1}. {node.name}\n")
            lines.append(f"{node.description}\n")
            lines.append(f"- Run dispatch key: `{node.dispatch}`\n")
            lines.append(f"- Category: {node.category}\n")
            lines.append(f"- Returns: Tuple3 `(ok, data, error)`\n\n")
        lines.append("## VBStyle Rules\n")
        lines.append("- Every class has `Run(command, params)` dispatch entry\n")
        lines.append("- Every method returns Tuple3 `(ok, data, error)`\n")
        lines.append("- No decorators, no print, no hardcoded paths\n")
        lines.append("- PascalCase classes, UPPERCASE constants\n")
        lines.append("- `self.state` dict (no `self._`)\n")
        with open(spec_path, "w") as f:
            f.write("\n".join(lines))
        # Also export as Python constants for the other viewers
        py_path = os.path.join(os.path.dirname(__file__), "spec_data_exported.py")
        py_lines = ["# Auto-generated from Plan Graph -- import this in other viewers\n"]
        py_lines.append("Config.GRAPH_CLASSES = [\n")
        for node in sorted(self.nodes, key=lambda n: n.name):
            py_lines.append(
                f'    ("{node.name}", "{node.category}", "{node.dispatch}", '
                f'"{node.description}"),\n'
            )
        py_lines.append("]\n")
        py_lines.append("Config.GRAPH_EDGES = []  # define relationships in Spec Graph\n")
        with open(py_path, "w") as f:
            f.write("".join(py_lines))
        messagebox.showinfo("Export",
                            f"Exported {len(self.nodes)} classes to:\n"
                            f"  {spec_path}\n  {py_path}")
    def SavePlan(self):
        data = {
            "nodes": [
                {"name": n.name, "category": n.category, "dispatch": n.dispatch,
                 "description": n.description, "x": n.x, "y": n.y}
                for n in self.nodes
            ]
        }
        with open(self.plan_file, "w") as f:
            json.dump(data, f, indent=2)
        messagebox.showinfo("Save", f"Plan saved to {self.plan_file}")
        return (1, None, None)
    def LoadPlan(self):
        if not os.path.exists(self.plan_file):
            messagebox.showwarning("Load", f"No plan file at {self.plan_file}")
            return (1, None, None)
        with open(self.plan_file, "r") as f:
            data = json.load(f)
        self.nodes = []
        for nd in data.get("nodes", []):
            self.nodes.append(PlanNode(
                nd["name"], nd["category"], nd["dispatch"],
                nd["description"], nd.get("x", 0), nd.get("y", 0)
            ))
        self.selected = None
        self.UpdateCount()
        self.DrawGraph()
        self.ClearProperties()
        messagebox.showinfo("Load", f"Loaded {len(self.nodes)} nodes from plan.")
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
    app = PlanGraph(root)
    root.mainloop()
