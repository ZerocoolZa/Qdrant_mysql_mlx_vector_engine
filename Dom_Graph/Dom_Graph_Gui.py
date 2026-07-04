#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<DB Architecture GUI visual mapper with tkinter. Three work streams: DB Guarded, DB Normalized, Analyzer. No #[@...] headers. No Run dispatch. No Tuple3 returns. Has hardcoded DB_PATH with absolute path. Has hardcoded color constants (BG, PANEL, CARD, etc). Uses tkinter. 1836 lines.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Move DB_PATH and colors to Config.py. Remove absolute hardcoded path.>]}
"""
DB Architecture GUI — Visual mapper with REAL graphics
Three work streams shown as drawn diagrams:
  1. DB Guarded (security container — drawn as a vault with 4 layers)
  2. DB Normalized (type/domain/category — drawn as connected tables)
  3. Analyzer (graph aspect engine — drawn as actual node/edge graph)
"""
import tkinter as tk
from tkinter import ttk
import sqlite3
import os
import math
from datetime import datetime
DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"
# Colors
BG = "#0d1117"
PANEL = "#161b22"
CARD = "#21262d"
TEXT = "#e6edf3"
ACCENT = "#f85149"
GREEN = "#3fb950"
YELLOW = "#d29922"
RED = "#f85149"
BLUE = "#58a6ff"
PURPLE = "#bc8cff"
ORANGE = "#db6d28"
GRAY = "#484f58"
DARK = "#010409"
class DbArchitectureGui:
    
    def __init__(self, root):
        self.root = root
        self.root.title("DB Architecture — Guard + Normalize + Analyze")
        self.root.geometry("1500x950")
        self.root.configure(bg=BG)
        
        # Header
        header = tk.Frame(root, bg=DARK, height=40)
        header.pack(fill="x", padx=5, pady=3)
        tk.Label(header, text="DB ARCHITECTURE MAPPER", font=("Courier", 16, "bold"),
                 fg=ACCENT, bg=DARK).pack(side="left", padx=10)
        tk.Label(header, text="Guard  +  Normalize  +  Analyze", font=("Courier", 11),
                 fg=TEXT, bg=DARK).pack(side="left", padx=15)
        tk.Label(header, text=datetime.now().strftime("%Y-%m-%d %H:%M"),
                 font=("Courier", 9), fg=GRAY, bg=DARK).pack(side="right", padx=10)
        
        # Notebook
        style = ttk.Style()
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=TEXT,
                        padding=[15, 8], font=("Courier", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", CARD)],
                  foreground=[("selected", ACCENT)])
        
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=5, pady=3)
        
        # Tabs
        self.guard_tab = tk.Frame(notebook, bg=BG)
        notebook.add(self.guard_tab, text="  1. GUARD  ")
        self.build_guard_tab()
        
        self.norm_tab = tk.Frame(notebook, bg=BG)
        notebook.add(self.norm_tab, text="  2. NORMALIZE  ")
        self.build_normalize_tab()
        
        self.analyze_tab = tk.Frame(notebook, bg=BG)
        notebook.add(self.analyze_tab, text="  3. ANALYZE  ")
        self.build_analyze_tab()
        
        self.reason_tab = tk.Frame(notebook, bg=BG)
        notebook.add(self.reason_tab, text="  4. REASON (What's Missing)  ")
        self.build_reason_tab()
        self.yinyang_tab = tk.Frame(notebook, bg=BG)
        notebook.add(self.yinyang_tab, text="  5. YIN/YANG (Red vs Blue)  ")
        self.build_yinyang_tab()
        # Status
        self.status = tk.Label(root, text="Loading...", font=("Courier", 9),
                               fg=GRAY, bg=DARK, anchor="w")
        self.status.pack(fill="x", padx=5, pady=2)
        
        # Live refresh — poll DB every 3 seconds
        self.auto_refresh = True
        self.last_node_count = 0
        self.last_edge_count = 0
        self.last_class_count = 0
        self.last_method_count = 0
        
        self.load_data()
        self.start_live_refresh()
    def build_guard_tab(self):
        canvas = tk.Canvas(self.guard_tab, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.guard_tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        self.guard_canvas = canvas
        canvas.bind("<Configure>", lambda e: self.draw_guard())
        self.guard_drawn = False
        return (1, None, None)
    def draw_guard(self):
        c = self.guard_canvas
        c.delete("all")
        
        w = c.winfo_width()
        if w < 100:
            w = 1400
        
        cx = w // 2
        y = 30
        
        # Title
        c.create_text(cx, y, text="SECURITY CONTAINER", font=("Courier", 20, "bold"),
                      fill=ACCENT)
        y += 25
        c.create_text(cx, y, text="AI must pass ALL 4 layers before DB write",
                      font=("Courier", 11), fill=YELLOW)
        y += 30
        
        # Draw the container (vault shape)
        vault_w = 600
        vault_x = cx - vault_w // 2
        vault_top = y
        vault_h = 520
        
        # Vault background
        c.create_rectangle(vault_x - 10, vault_top - 10,
                          vault_x + vault_w + 10, vault_top + vault_h + 10,
                          outline=GREEN, width=3, fill=DARK)
        
        # Vault label
        c.create_text(cx, vault_top - 20, text="┌── SECURITY CONTAINER ──┐",
                      font=("Courier", 12, "bold"), fill=GREEN)
        
        y = vault_top + 20
        
        # AI enters
        c.create_text(cx, y, text="AI wants to write to DB",
                      font=("Courier", 10), fill=ORANGE)
        y += 15
        self.draw_arrow_down(c, cx, y, 20, ORANGE)
        y += 25
        
        # Layer 1: Registry
        self.draw_layer(c, cx, y, vault_w - 40, "1", "REGISTRY", "ID Check",
                        ["domain_registry  →  Is domain registered?",
                         "type_registry     →  Is type registered?",
                         "category_registry →  Is category registered?"],
                        BLUE, "Tested (Approach E). NOT applied yet.")
        y += 120
        
        self.draw_pass_fail(c, cx, y, "PASS →", "FAIL → BLOCK", GREEN, RED)
        y += 30
        
        # Layer 2: Cognitive Loop
        self.draw_layer(c, cx, y, vault_w - 40, "2", "COGNITIVE LOOP", "Reasoning Check",
                        ["Problem → Question → Answer",
                         "Constraint → Mistake → Solution → Verify",
                         "All 7 nodes must exist before code enters"],
                        PURPLE, "38 nodes exist for workflow. Gate NOT built.")
        y += 120
        
        self.draw_pass_fail(c, cx, y, "PASS →", "FAIL → BLOCK", GREEN, RED)
        y += 30
        
        # Layer 3: VBStyle
        self.draw_layer(c, cx, y, vault_w - 40, "3", "VBSTYLE", "Style Check",
                        ["Run() dispatch + Tuple3 returns",
                         "self.state dict, no self._",
                         "No print, no decorators, no hardcoded paths"],
                        ACCENT, "Checker exists. Gate NOT built.")
        y += 120
        
        self.draw_pass_fail(c, cx, y, "PASS →", "FAIL → BLOCK", GREEN, RED)
        y += 30
        
        # Layer 4: Verify
        self.draw_layer(c, cx, y, vault_w - 40, "4", "VERIFY", "Post-Insert Check",
                        ["py_compile passes",
                         "search_idx updated, BCL created",
                         "execution_log entry exists"],
                        GREEN, "Checks exist. Rollback NOT built.")
        y += 120
        
        # ALL PASS
        self.draw_arrow_down(c, cx, y, 20, GREEN)
        y += 25
        
        # Result
        c.create_rectangle(cx - 150, y, cx + 150, y + 35,
                          outline=GREEN, width=2, fill="#0d2818")
        c.create_text(cx, y + 18, text="INSERT ALLOWED", font=("Courier", 14, "bold"),
                      fill=GREEN)
        y += 50
        
        # DB
        c.create_rectangle(cx - 80, y, cx + 80, y + 40,
                          outline=BLUE, width=2, fill="#0d1a2e")
        c.create_text(cx, y + 20, text="v20_hybrid_best.db", font=("Courier", 10, "bold"),
                      fill=BLUE)
        y += 55
        
        # Vault bottom
        c.create_text(cx, y, text="└──────────────────────────┘",
                      font=("Courier", 12, "bold"), fill=GREEN)
        y += 30
        
        # Warning box
        warn_y = y + 20
        c.create_rectangle(50, warn_y, w - 50, warn_y + 120,
                          outline=RED, width=2, fill="#1a0d0d")
        c.create_text(cx, warn_y + 15, text="WHAT HAPPENED WITHOUT THIS CONTAINER",
                      font=("Courier", 11, "bold"), fill=RED)
        c.create_text(cx, warn_y + 45,
                      text="Devin inserted Dom_workflow (class + 19 methods + 38 nodes + 61 edges)",
                      font=("Courier", 9), fill=TEXT)
        c.create_text(cx, warn_y + 60,
                      text="WITHOUT: domain registered, cognitive loop reviewed, VBStyle verified",
                      font=("Courier", 9), fill=TEXT)
        c.create_text(cx, warn_y + 75,
                      text="Result: DB polluted, trust broken, user lost their train of thought",
                      font=("Courier", 9), fill=TEXT)
        c.create_text(cx, warn_y + 100,
                      text="This container would have BLOCKED all of it.",
                      font=("Courier", 10, "bold"), fill=YELLOW)
        
        # Task link
        c.create_text(cx, warn_y + 145,
                      text="TRACKED AS: TASK-085 (P0 Critical) in TaskPlanner",
                      font=("Courier", 10, "bold"), fill=YELLOW)
        
        # Set scroll region
        c.configure(scrollregion=(0, 0, w, warn_y + 170))
        return (1, None, None)
    def draw_layer(self, canvas, cx, y, width, num, title, subtitle, items, color, status):
        """Draw a layer box with number, title, items, and status"""
        x1 = cx - width // 2
        x2 = cx + width // 2
        
        # Box
        canvas.create_rectangle(x1, y, x2, y + 90,
                                outline=color, width=2, fill=CARD)
        
        # Number circle
        canvas.create_oval(x1 + 8, y + 8, x1 + 28, y + 28,
                          fill=color, outline=color)
        canvas.create_text(x1 + 18, y + 18, text=num, font=("Courier", 12, "bold"),
                          fill=DARK)
        
        # Title
        canvas.create_text(x1 + 45, y + 15, text=title, font=("Courier", 12, "bold"),
                          fill=color, anchor="w")
        canvas.create_text(x1 + 45, y + 30, text=subtitle, font=("Courier", 9),
                          fill=GRAY, anchor="w")
        
        # Items
        for i, item in enumerate(items):
            canvas.create_text(x1 + 45, y + 48 + i * 14, text=item,
                              font=("Courier", 9), fill=TEXT, anchor="w")
        
        # Status
        canvas.create_text(x2 - 10, y + 80, text=status, font=("Courier", 8),
                          fill=YELLOW, anchor="e")
        return (1, None, None)
    def draw_pass_fail(self, canvas, cx, y, pass_text, fail_text, pass_color, fail_color):
        """Draw pass/fail arrows"""
        canvas.create_text(cx - 80, y, text=pass_text, font=("Courier", 9, "bold"),
                          fill=pass_color)
        canvas.create_text(cx + 80, y, text=fail_text, font=("Courier", 9, "bold"),
                          fill=fail_color)
        return (1, None, None)
    def draw_arrow_down(self, canvas, x, y, length, color):
        """Draw a downward arrow"""
        canvas.create_line(x, y, x, y + length, fill=color, width=2)
        canvas.create_polygon(x - 5, y + length, x + 5, y + length, x, y + length + 8,
                             fill=color)
        return (1, None, None)
    def build_normalize_tab(self):
        canvas = tk.Canvas(self.norm_tab, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.norm_tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        self.norm_canvas = canvas
        canvas.bind("<Configure>", lambda e: self.draw_normalize())
        return (1, None, None)
    def draw_normalize(self):
        c = self.norm_canvas
        c.delete("all")
        
        w = c.winfo_width()
        if w < 100:
            w = 1400
        cx = w // 2
        y = 20
        
        # Title
        c.create_text(cx, y, text="NORMALIZE — Type / Domain / Category",
                      font=("Courier", 18, "bold"), fill=ACCENT)
        y += 30
        
        # Draw 3 registry tables as connected boxes
        table_w = 280
        table_h = 160
        gap = 40
        total_w = table_w * 3 + gap * 2
        start_x = cx - total_w // 2
        
        # Table 1: domain_registry
        tx = start_x
        self.draw_table_box(c, tx, y, table_w, table_h, "domain_registry", BLUE,
                           [("domain_id", "INTEGER PK"),
                            ("name", "TEXT UNIQUE"),
                            ("description", "TEXT"),
                            ("created_at", "TEXT")])
        
        # Table 2: type_registry
        tx = start_x + table_w + gap
        self.draw_table_box(c, tx, y, table_w, table_h, "type_registry", PURPLE,
                           [("type_id", "INTEGER PK"),
                            ("name", "TEXT UNIQUE"),
                            ("description", "TEXT"),
                            ("applies_to", "TEXT")])
        
        # Table 3: category_registry
        tx = start_x + (table_w + gap) * 2
        self.draw_table_box(c, tx, y, table_w, table_h, "category_registry", ORANGE,
                           [("category_id", "INTEGER PK"),
                            ("domain", "TEXT NOT NULL"),
                            ("name", "TEXT NOT NULL"),
                            ("description", "TEXT")])
        
        y += table_h + 20
        
        # Connection lines (registries feed into data tables)
        c.create_text(cx, y, text="↓  These registries feed into  ↓",
                      font=("Courier", 10), fill=GRAY)
        y += 25
        
        # Data tables
        data_w = 200
        data_h = 100
        data_gap = 20
        data_tables = [
            ("classes", BLUE, ["id", "class_name", "domain*"]),
            ("methods", PURPLE, ["id", "class_id", "method_name"]),
            ("decision_nodes", ORANGE, ["node_id", "domain*", "node_type*", "category*"]),
            ("decision_edges", GREEN, ["edge_id", "from_node", "to_node"]),
        ]
        
        total_dw = data_w * len(data_tables) + data_gap * (len(data_tables) - 1)
        start_dx = cx - total_dw // 2
        
        for i, (name, color, cols) in enumerate(data_tables):
            dx = start_dx + i * (data_w + data_gap)
            self.draw_table_box(c, dx, y, data_w, data_h, name, color,
                               [(col, "") for col in cols], small=True)
            
            # Draw connection from registries to this table
            if '*' in str(cols):
                # Draw line from top registries
                c.create_line(dx + data_w // 2, y, dx + data_w // 2, y - 15,
                             fill=GRAY, dash=(3, 3))
        
        y += data_h + 30
        
        # Triggers section
        c.create_text(cx, y, text="TRIGGERS (Enforcement Layer)",
                      font=("Courier", 14, "bold"), fill=YELLOW)
        y += 25
        
        trig_box = tk.Frame
        c.create_rectangle(cx - 400, y, cx + 400, y + 120,
                          outline=YELLOW, width=2, fill=CARD)
        
        triggers_text = [
        ]
        for i, line in enumerate(triggers_text):
            c.create_text(cx - 380, y + 15 + i * 14, text=line,
                          font=("Courier", 9), fill=TEXT, anchor="w")
        
        y += 140
        
        # Test result
        c.create_rectangle(cx - 300, y, cx + 300, y + 80,
                          outline=GREEN, width=2, fill="#0d2818")
        c.create_text(cx, y + 15, text="TEST RESULT: Approach E WON",
                      font=("Courier", 12, "bold"), fill=GREEN)
        c.create_text(cx, y + 35,
                      text="5 approaches tested on real data (81 domains, 4 types, 7 categories)",
                      font=("Courier", 9), fill=TEXT)
        c.create_text(cx, y + 50,
                      text="Winner: registry + text columns + triggers",
                      font=("Courier", 9), fill=TEXT)
        c.create_text(cx, y + 65,
                      text="Test file: dom_compression/test_registry_schema.py",
                      font=("Courier", 8), fill=GRAY)
        
        # Current state
        y += 100
        c.create_text(cx, y, text="CURRENT STATE (from DB)",
                      font=("Courier", 12, "bold"), fill=ACCENT)
        y += 25
        
        state_lines = [
        ]
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cc = conn.cursor()
            cc.execute("SELECT COUNT(DISTINCT domain) FROM classes WHERE domain IS NOT NULL")
            state_lines[0] = "Domains in classes table: " + str(cc.fetchone()[0]) + " unique"
            cc.execute("SELECT COUNT(DISTINCT domain) FROM decision_nodes WHERE domain IS NOT NULL")
            state_lines[1] = "Domains in decision_nodes: " + str(cc.fetchone()[0])
            cc.execute("SELECT COUNT(DISTINCT node_type) FROM decision_nodes")
            state_lines[2] = "Node types: " + str(cc.fetchone()[0])
            cc.execute("SELECT COUNT(DISTINCT category) FROM decision_nodes WHERE category != ''")
            state_lines[3] = "Categories: " + str(cc.fetchone()[0])
            cc.execute("SELECT COUNT(*) FROM decision_nodes WHERE domain='graph_engine' AND (category IS NULL OR category='')")
            state_lines[4] = "graph_engine nodes with EMPTY category: " + str(cc.fetchone()[0])
            cc.execute("SELECT COUNT(*) FROM decision_nodes WHERE domain='workflow'")
            state_lines[5] = "workflow nodes: " + str(cc.fetchone()[0]) + " (category filled)"
            cc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='domain_registry'")
            state_lines[6] = "Registry tables: " + ("BUILT" if cc.fetchone() else "NOT BUILT")
            conn.close()
        except:
            pass
        
        for i, line in enumerate(state_lines):
            color = GREEN if "BUILT" in line else (YELLOW if "EMPTY" in line or "NOT BUILT" in line else TEXT)
            c.create_text(cx - 250, y + i * 16, text=line,
                          font=("Courier", 9), fill=color, anchor="w")
        
        y += len(state_lines) * 16 + 20
        
        c.configure(scrollregion=(0, 0, w, y))
        return (1, None, None)
    def draw_table_box(self, canvas, x, y, w, h, name, color, columns, small=False):
        """Draw a database table as a box with columns"""
        # Header
        canvas.create_rectangle(x, y, x + w, y + 30, fill=color, outline=color)
        canvas.create_text(x + w // 2, y + 15, text=name, font=("Courier", 11, "bold"),
                          fill=DARK)
        
        # Body
        canvas.create_rectangle(x, y + 30, x + w, y + h, fill=CARD, outline=color)
        
        # Columns
        for i, (col_name, col_type) in enumerate(columns):
            cy = y + 40 + i * 18
            canvas.create_text(x + 10, cy, text=col_name, font=("Courier", 9),
                              fill=TEXT, anchor="w")
            if col_type:
                canvas.create_text(x + w - 10, cy, text=col_type, font=("Courier", 8),
                                  fill=GRAY, anchor="e")
        return (1, None, None)
    def build_analyze_tab(self):
        # Top: stats
        top = tk.Frame(self.analyze_tab, bg=BG, height=60)
        top.pack(fill="x", padx=5, pady=3)
        
        self.stat_labels = {}
        stats = [("nodes", "Nodes"), ("edges", "Edges"), ("domains", "Domains"),
                 ("classes", "Classes"), ("methods", "Methods"), ("plans", "Plans")]
        for i, (key, label) in enumerate(stats):
            card = tk.Frame(top, bg=CARD, relief="flat", bd=1)
            card.grid(row=0, column=i, padx=3, pady=3, sticky="ew")
            tk.Label(card, text=label, font=("Courier", 8), fg=GRAY, bg=CARD).pack(padx=8, pady=2)
            vl = tk.Label(card, text="...", font=("Courier", 18, "bold"), fg=GREEN, bg=CARD)
            vl.pack(padx=8, pady=2)
            self.stat_labels[key] = vl
        
        # Canvas for graph drawing
        canvas = tk.Canvas(self.analyze_tab, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.analyze_tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        self.graph_canvas = canvas
        canvas.bind("<Configure>", lambda e: self.draw_graph())
        return (1, None, None)
    def draw_graph(self):
        c = self.graph_canvas
        c.delete("all")
        
        w = c.winfo_width()
        if w < 100:
            w = 1400
        cx = w // 2
        y = 20
        
        # Title
        c.create_text(cx, y, text="GRAPH ASPECT ENGINE — Cognitive Loops",
                      font=("Courier", 16, "bold"), fill=ACCENT)
        y += 25
        
        # Load nodes from DB
        try:
            conn = sqlite3.connect(DB_PATH)
            cc = conn.cursor()
            
            # Get all domains
            cc.execute("SELECT DISTINCT domain FROM decision_nodes WHERE domain IS NOT NULL ORDER BY domain")
            domains = [r[0] for r in cc.fetchall()]
            
            for domain in domains:
                # Draw domain header
                c.create_text(cx, y, text=domain.upper(), font=("Courier", 14, "bold"),
                              fill=BLUE)
                y += 20
                
                # Get categories for this domain
                cc.execute("""SELECT category, COUNT(*) FROM decision_nodes
                             WHERE domain=? AND category IS NOT NULL AND category != ''
                             GROUP BY category ORDER BY category""", (domain,))
                cats = cc.fetchall()
                
                if not cats:
                    c.create_text(cx, y, text="(no categories — needs filling)",
                                  font=("Courier", 9), fill=YELLOW)
                    y += 15
                    continue
                
                # Draw each category as a cognitive loop circle
                loop_w = 900
                loop_x = cx - loop_w // 2
                
                for cat_name, cat_count in cats:
                    # Draw the 7-step loop as circles
                    steps = ["Problem", "Question", "Answer", "Constraint",
                            "Mistake", "Solution", "Verify"]
                    
                    # Check which steps exist
                    cc.execute("""SELECT name, node_type FROM decision_nodes
                                 WHERE domain=? AND category=?""", (domain, cat_name))
                    nodes = cc.fetchall()
                    existing = []
                    for step in steps:
                        found = any(step in n[0] for n in nodes)
                        existing.append(found)
                    
                    # Draw label
                    c.create_text(loop_x, y + 15, text=cat_name + ":",
                                  font=("Courier", 10, "bold"), fill=ORANGE, anchor="w")
                    
                    # Draw 7 circles in a row
                    circle_r = 18
                    circle_gap = 50
                    start_cx = loop_x + 80
                    
                    for i, step in enumerate(steps):
                        sx = start_cx + i * circle_gap
                        sy = y + 15
                        
                        color = GREEN if existing[i] else RED
                        fill_color = "#0d2818" if existing[i] else "#1a0d0d"
                        
                        c.create_oval(sx - circle_r, sy - circle_r,
                                     sx + circle_r, sy + circle_r,
                                     outline=color, width=2, fill=fill_color)
                        
                        # Step name (short)
                        short = step[:4]
                        c.create_text(sx, sy, text=short, font=("Courier", 7, "bold"),
                                     fill=color)
                        
                        # Full name below
                        c.create_text(sx, sy + circle_r + 8, text=step,
                                     font=("Courier", 7), fill=TEXT)
                        
                        # Arrow to next
                        if i < len(steps) - 1:
                            ax1 = sx + circle_r
                            ax2 = sx + circle_gap - circle_r
                            c.create_line(ax1, sy, ax2, sy, fill=GRAY, width=1,
                                         arrow="last")
                    
                    # Status
                    all_exist = all(existing)
                    status = "COMPLETE" if all_exist else "INCOMPLETE"
                    status_color = GREEN if all_exist else RED
                    c.create_text(start_cx + 7 * circle_gap + 10, y + 15,
                                 text="[" + status + "]",
                                 font=("Courier", 9, "bold"), fill=status_color, anchor="w")
                    
                    y += 50
                
                # Draw edges count
                cc.execute("""SELECT COUNT(*) FROM decision_edges e
                             JOIN decision_nodes n ON e.from_node=n.node_id
                             WHERE n.domain=?""", (domain,))
                edge_count = cc.fetchone()[0]
                c.create_text(cx, y, text="Edges: " + str(edge_count),
                              font=("Courier", 9), fill=GRAY)
                y += 20
                
                # Draw a sample edge graph (root → operations)
                if domain == 'workflow':
                    self.draw_workflow_graph(c, cx, y, cc)
                    y += 200
                
                y += 15
            
            conn.close()
            
        except Exception as e:
            c.create_text(cx, y, text="Error: " + str(e), font=("Courier", 10), fill=RED)
            y += 20
        
        # Gate status
        y += 10
        c.create_text(cx, y, text="GATE STATUS", font=("Courier", 14, "bold"), fill=ACCENT)
        y += 25
        
        gate_items = [
            ("Registry tables", "NOT BUILT", RED),
            ("Triggers", "NOT BUILT", RED),
            ("Cognitive loop gate", "NOT BUILT", RED),
            ("VBStyle gate", "NOT BUILT", RED),
            ("Verify gate", "NOT BUILT", RED),
            ("Execution contracts", "BUILT", GREEN),
            ("Execution log", "0 entries", YELLOW),
        ]
        
        for label, status, color in gate_items:
            c.create_text(cx - 150, y, text=label, font=("Courier", 10), fill=TEXT, anchor="w")
            c.create_text(cx + 150, y, text=status, font=("Courier", 10, "bold"),
                         fill=color, anchor="e")
            y += 18
        
        c.configure(scrollregion=(0, 0, w, y + 20))
        return (1, None, None)
    def draw_workflow_graph(self, canvas, cx, y, cc):
        """Draw the workflow root → 5 operations as a graph"""
        # Root node
        root_r = 25
        canvas.create_oval(cx - root_r, y, cx + root_r, y + root_r * 2,
                          outline=BLUE, width=2, fill="#0d1a2e")
        canvas.create_text(cx, y + root_r, text="ROOT", font=("Courier", 8, "bold"),
                          fill=BLUE)
        
        # 5 operation nodes
        ops = ["PRJ", "INDEX", "CONFIG", "VALIDATE", "REPORT"]
        op_colors = [ORANGE, PURPLE, ACCENT, YELLOW, GREEN]
        op_w = 80
        op_h = 30
        gap = 20
        total_w = op_w * 5 + gap * 4
        start_x = cx - total_w // 2
        
        for i, (op, color) in enumerate(zip(ops, op_colors)):
            ox = start_x + i * (op_w + gap) + op_w // 2
            oy = y + 80
            
            # Edge from root
            canvas.create_line(cx, y + root_r * 2, ox, oy, fill=color, width=1,
                              arrow="last", dash=(3, 3))
            
            # Operation box
            canvas.create_rectangle(ox - op_w // 2, oy, ox + op_w // 2, oy + op_h,
                                   outline=color, width=2, fill=CARD)
            canvas.create_text(ox, oy + op_h // 2, text=op, font=("Courier", 8, "bold"),
                              fill=color)
            
            # 7-step mini loop below
            steps_short = ["P", "Q", "A", "C", "M", "S", "V"]
            step_r = 8
            step_gap = 16
            step_start = ox - (step_gap * 6) // 2
            
            for j, s in enumerate(steps_short):
                sx = step_start + j * step_gap
                sy = oy + op_h + 15
                canvas.create_oval(sx - step_r, sy - step_r, sx + step_r, sy + step_r,
                                  outline=color, width=1, fill=DARK)
                canvas.create_text(sx, sy, text=s, font=("Courier", 6), fill=color)
                
                if j < 6:
                    canvas.create_line(sx + step_r, sy, sx + step_gap - step_r, sy,
                                      fill=GRAY, width=1)
            
            # Terminal nodes
            ty = oy + op_h + 35
            canvas.create_oval(ox - 12, ty, ox + 12, ty + 24,
                              outline=GREEN, width=1, fill="#0d2818")
            canvas.create_text(ox, ty + 12, text="OK", font=("Courier", 6), fill=GREEN)
        return (1, None, None)
    def build_reason_tab(self):
        """Reasoning engine — analyzes the DB and reports what's missing"""
        canvas = tk.Canvas(self.reason_tab, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.reason_tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        self.reason_canvas = canvas
        canvas.bind("<Configure>", lambda e: self.draw_reason())
        return (1, None, None)
    def draw_reason(self):
        c = self.reason_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 100:
            w = 1400
        cx = w // 2
        y = 20
        # Title
        c.create_text(cx, y, text="REASONING ENGINE — What's Missing & Why It Matters",
                      font=("Courier", 16, "bold"), fill=ACCENT)
        y += 25
        if not os.path.exists(DB_PATH):
            c.create_text(cx, y, text="DB not found", fill=RED)
            c.configure(scrollregion=(0, 0, w, y + 20))
            return (1, None, None)
        conn = sqlite3.connect(DB_PATH)
        cc = conn.cursor()
        # ═══ Gather all findings ═══
        # Format: (category, severity, issue, why, fix, verify, color)
        findings = []
        # Helper: safe query (won't crash on missing tables)
        def safe_count(table, query, default=0):
            try:
                cc.execute(query)
                return (1, cc.fetchone()[0], None)
            except sqlite3.OperationalError:
                return (1, default, None)
        def table_exists(name):
            cc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
            return (1, cc.fetchone() is not None, None)
        def trigger_exists(name):
            cc.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name=?", (name,))
            return (1, cc.fetchone() is not None, None)
        # ── 1. GUARD GAPS ──
        # Registry tables
        has_domain_reg = table_exists('domain_registry')
        has_type_reg = table_exists('type_registry')
        has_cat_reg = table_exists('category_registry')
        if not has_domain_reg:
            findings.append(("GUARD", "CRITICAL", "domain_registry table does not exist",
                            "Any AI can insert any domain text — no validation. Typos like 'workfow' vs 'workflow' will pollute the DB.",
                            "Build domain_registry table + triggers (Approach E tested and proven)",
                            "Run: SELECT COUNT(*) FROM domain_registry — should show 81 domains. Then try INSERT with bad domain — should FAIL.",
                            RED))
        if not has_type_reg:
            findings.append(("GUARD", "CRITICAL", "type_registry table does not exist",
                            "Node types (action, check, fallback, question) are not enforced. AI could invent new types.",
                            "Build type_registry table + triggers",
                            "Run: SELECT name FROM type_registry — should show 4+ types.",
                            RED))
        if not has_cat_reg:
            findings.append(("GUARD", "CRITICAL", "category_registry table does not exist",
                            "Categories (prj, index, config, etc.) are not enforced. AI could invent new categories.",
                            "Build category_registry table + triggers",
                            "Run: SELECT domain, name FROM category_registry — should show categories per domain.",
                            RED))
        # Triggers — check for SPECIFIC trigger names, not just any trigger with 'validate'
        required_triggers = ['validate_node_domain', 'validate_node_type', 'validate_class_domain']
        missing_triggers = [t for t in required_triggers if not trigger_exists(t)]
        if missing_triggers and (has_domain_reg or has_type_reg):
            findings.append(("GUARD", "CRITICAL", "Missing validation triggers: " + ", ".join(missing_triggers),
                            "Registry tables may exist but without triggers, nothing enforces them. The DB is still an open door.",
                            "Create BEFORE INSERT triggers: " + ", ".join(missing_triggers),
                            "Run: SELECT name FROM sqlite_master WHERE type='trigger' — should list all 3.",
                            RED))
        elif not has_domain_reg and not has_type_reg:
            findings.append(("GUARD", "CRITICAL", "No validation triggers exist",
                            "Nothing prevents invalid inserts. The DB is an open door — exactly what happened when Devin inserted without permission.",
                            "Create BEFORE INSERT triggers that check domain/type/category against registries",
                            "Run: SELECT name FROM sqlite_master WHERE type='trigger' — should show validation triggers.",
                            RED))
        # Cognitive loop gate
        if not trigger_exists('validate_cognitive_loop'):
            findings.append(("GUARD", "HIGH", "No cognitive loop gate exists",
                            "Code can enter the DB without Problem→Question→Answer→Constraint→Mistake→Solution→Verify. This is the guardrail that prevents AI corruption.",
                            "Build trigger that checks 7 cognitive loop nodes exist before allowing class/method insert",
                            "Try inserting a class without cognitive loop nodes — should be BLOCKED.",
                            YELLOW))
        # VBStyle violations
        violations = safe_count('violations', "SELECT COUNT(*) FROM violations")
        if violations > 0:
            findings.append(("GUARD", "MEDIUM", str(violations) + " VBStyle violations exist in DB",
                            "Code in DB that doesn't follow VBStyle rules. Inconsistent.",
                            "Fix violations or mark as resolved",
                            "Run: SELECT COUNT(*) FROM violations — should be 0.",
                            YELLOW))
        elif not table_exists('violations'):
            findings.append(("GUARD", "CRITICAL", "violations table does not exist",
                            "VBStyle violations can't be tracked. No way to know if code follows the rules.",
                            "Create violations table",
                            "Run: SELECT name FROM sqlite_master WHERE name='violations' — should exist.",
                            RED))
        # Execution log
        log_entries = safe_count('execution_log', "SELECT COUNT(*) FROM execution_log")
        if log_entries == 0:
            findings.append(("GUARD", "MEDIUM", "Execution log is empty",
                            "No runs have been logged. No audit trail. If something goes wrong, there's no history.",
                            "Run the graph engine through the decision tree to populate execution_log",
                            "Run: SELECT COUNT(*) FROM execution_log — should be > 0 after a test run.",
                            YELLOW))
        # BCL identity tokens — CRITICAL check
        if table_exists('bcl_identity'):
            cc.execute("SELECT COUNT(*) FROM classes")
            total_classes = cc.fetchone()[0]
            cc.execute("""SELECT COUNT(*) FROM classes c
                         WHERE NOT EXISTS (SELECT 1 FROM bcl_identity
                         WHERE entity_type='class' AND entity_id=c.id)""")
            missing_bcl_classes = cc.fetchone()[0]
            if missing_bcl_classes > 0:
                findings.append(("GUARD", "CRITICAL", str(missing_bcl_classes) + " of " + str(total_classes) + " classes missing BCL identity tokens",
                                "BCL tokens are the 'passport' for code. Without them, the system can't verify what code is allowed to execute or trace execution back to its source.",
                                "Run bcl_identity_generator.py to create tokens for all classes",
                                "Run: SELECT COUNT(*) FROM bcl_identity WHERE entity_type='class' — should equal class count.",
                                RED))
            cc.execute("SELECT COUNT(*) FROM methods")
            total_methods_bcl = cc.fetchone()[0]
            cc.execute("""SELECT COUNT(*) FROM methods m
                         WHERE NOT EXISTS (SELECT 1 FROM bcl_identity
                         WHERE entity_type='method' AND entity_id=m.id)""")
            missing_bcl_methods = cc.fetchone()[0]
            if missing_bcl_methods > 0:
                findings.append(("GUARD", "CRITICAL", str(missing_bcl_methods) + " of " + str(total_methods_bcl) + " methods missing BCL identity tokens",
                                "Methods without BCL tokens can't be traced or verified. The system can't answer 'what does this method do?'",
                                "Run bcl_identity_generator.py to create tokens for all methods",
                                "Run: SELECT COUNT(*) FROM bcl_identity WHERE entity_type='method' — should equal method count.",
                                RED))
        else:
            findings.append(("GUARD", "CRITICAL", "bcl_identity table does not exist",
                            "The BCL identity registry is missing. Code can't be verified or traced. This is a core guard.",
                            "Create bcl_identity table and populate with tokens for all classes/methods",
                            "Run: SELECT name FROM sqlite_master WHERE name='bcl_identity' — should exist.",
                            RED))
        # ── 2. NORMALIZATION GAPS ──
        # graph_engine nodes with empty category
        empty_cat_count = safe_count('decision_nodes',
            "SELECT COUNT(*) FROM decision_nodes WHERE domain='graph_engine' AND (category IS NULL OR category='')")
        if empty_cat_count > 0:
            findings.append(("NORMALIZE", "HIGH", str(empty_cat_count) + " graph_engine nodes have empty category",
                            "Cascade created 44 nodes but didn't assign categories. The category column was added later for workflow. graph_engine nodes are inconsistent.",
                            "Assign categories to graph_engine nodes (howto, rules, verify, error, pipeline, permissions, when, why, alternatives, codegraph)",
                            "Run: SELECT COUNT(*) FROM decision_nodes WHERE domain='graph_engine' AND (category IS NULL OR category='') — should be 0.",
                            YELLOW))
        # Domain consistency
        cc.execute("SELECT DISTINCT domain FROM classes WHERE domain IS NOT NULL")
        class_domains = set(r[0] for r in cc.fetchall())
        cc.execute("SELECT DISTINCT domain FROM decision_nodes WHERE domain IS NOT NULL")
        node_domains = set(r[0] for r in cc.fetchall())
        only_in_classes = class_domains - node_domains
        only_in_nodes = node_domains - class_domains
        if only_in_classes:
            findings.append(("NORMALIZE", "MEDIUM", str(len(only_in_classes)) + " domains in classes but NOT in decision_nodes",
                            "These domains have code but no cognitive loop. No reasoning graph. An AI can't follow a tried-and-tested path for them.",
                            "Create cognitive loop nodes for: " + ", ".join(list(only_in_classes)[:5]),
                            "Run: SELECT DISTINCT domain FROM decision_nodes — should match classes domains.",
                            YELLOW))
        if only_in_nodes:
            findings.append(("NORMALIZE", "LOW", str(len(only_in_nodes)) + " domains in decision_nodes but NOT in classes",
                            "These domains have reasoning nodes but no code. The cognitive loop exists but the capability doesn't.",
                            "Add code for: " + ", ".join(list(only_in_nodes)[:5]),
                            "Run: SELECT DISTINCT domain FROM classes — should include these domains.",
                            BLUE))
        # Domain typos — improved with fuzzy matching
        from difflib import SequenceMatcher
        domain_names = [d for d in (class_domains | node_domains) if d]
        typos = []
        for i, d1 in enumerate(domain_names):
            for d2 in domain_names[i+1:]:
                if d1 == d2:
                    continue
                # Case difference
                if d1.lower() == d2.lower():
                    typos.append(d1 + " vs " + d2 + " (case)")
                # Fuzzy match (similar but not identical)
                else:
                    ratio = SequenceMatcher(None, d1.lower(), d2.lower()).ratio()
                    if 0.8 < ratio < 1.0:
                        typos.append(d1 + " vs " + d2 + " (similar)")
        if typos:
            findings.append(("NORMALIZE", "HIGH", "Domain typos/similar names detected: " + ", ".join(typos[:5]),
                            "Similar domain names cause confusion and pollution. This is exactly what the registry prevents.",
                            "Build registry + triggers to block invalid domains. Merge or rename duplicates.",
                            "Run: SELECT DISTINCT domain FROM classes ORDER BY domain — check for duplicates.",
                            RED))
        # Closure status
        if table_exists('closure_status'):
            closure_count = safe_count('closure_status', "SELECT COUNT(*) FROM closure_status")
            if closure_count == 0:
                findings.append(("NORMALIZE", "HIGH", "closure_status table is empty",
                                "Closure tracking is not populated. The system can't verify which domains are complete.",
                                "Populate closure_status with domain completeness metrics",
                                "Run: SELECT COUNT(*) FROM closure_status — should be > 0.",
                                YELLOW))
            else:
                cc.execute("SELECT domain, closure_pct FROM closure_status WHERE closure_pct < 100")
                incomplete = cc.fetchall()
                if incomplete:
                    domains_str = ", ".join(d[0] + " (" + str(d[1]) + "%)" for d in incomplete[:5])
                    findings.append(("NORMALIZE", "MEDIUM", str(len(incomplete)) + " domains not fully closed: " + domains_str,
                                    "These domains have incomplete cognitive loops. Not all 7 steps are present.",
                                    "Complete missing steps for: " + domains_str,
                                    "Run: SELECT domain, closure_pct FROM closure_status WHERE closure_pct < 100 — should be empty.",
                                    YELLOW))
        else:
            findings.append(("NORMALIZE", "HIGH", "closure_status table does not exist",
                            "Domain closure tracking is missing. Can't verify completeness.",
                            "Create closure_status table with domain metrics",
                            "Run: SELECT name FROM sqlite_master WHERE name='closure_status' — should exist.",
                            YELLOW))
        # ── 3. COGNITIVE LOOP GAPS ──
        cc.execute("SELECT DISTINCT domain FROM decision_nodes WHERE domain IS NOT NULL ORDER BY domain")
        all_domains = [r[0] for r in cc.fetchall()]
        steps = ["Problem", "Question", "Answer", "Constraint", "Mistake", "Solution", "Verify"]
        for domain in all_domains:
            cc.execute("SELECT DISTINCT category FROM decision_nodes WHERE domain=? AND category IS NOT NULL AND category != ''", (domain,))
            cats = [r[0] for r in cc.fetchall()]
            if not cats:
                findings.append(("COGNITIVE", "HIGH", domain + " has nodes but NO categories",
                                "Nodes exist but aren't categorized. AI can't sort or search by operation.",
                                "Assign categories to all " + domain + " nodes",
                                "Run: SELECT category, COUNT(*) FROM decision_nodes WHERE domain='" + domain + "' GROUP BY category — should show categories.",
                                YELLOW))
                continue
            for cat in cats:
                if cat in ('root', 'terminal'):
                    continue
                cc.execute("SELECT name FROM decision_nodes WHERE domain=? AND category=?", (domain, cat))
                nodes = [r[0] for r in cc.fetchall()]
                # Use word boundary regex for accurate matching
                import re
                missing_steps = []
                for step in steps:
                    pattern = r'\b' + re.escape(step) + r'\b'
                    if not any(re.search(pattern, n, re.IGNORECASE) for n in nodes):
                        missing_steps.append(step)
                if missing_steps:
                    findings.append(("COGNITIVE", "HIGH",
                                    domain + "/" + cat + " missing: " + ", ".join(missing_steps),
                                    "Cognitive loop is INCOMPLETE. The " + cat + " operation can't be fully reasoned through. An AI following the graph would hit a dead end.",
                                    "Create nodes for missing steps: " + ", ".join(missing_steps),
                                    "Run: SELECT name FROM decision_nodes WHERE domain='" + domain + "' AND category='" + cat + "' — should show all 7 steps.",
                                    RED))
        # Orphan nodes (no incoming edges, not root)
        try:
            cc.execute("""SELECT dn.node_id, dn.name, dn.domain FROM decision_nodes dn
                         WHERE NOT EXISTS (SELECT 1 FROM decision_edges WHERE to_node=dn.node_id)
                         AND dn.node_type != 'root'""")
            orphans = cc.fetchall()
            if orphans:
                findings.append(("COGNITIVE", "HIGH", str(len(orphans)) + " orphan nodes (no incoming edges)",
                                "These nodes are unreachable. They represent dead code paths that can never execute. Indicates incomplete graph design.",
                                "Connect them to the graph or delete them. Examples: " + ", ".join(r[1] for r in orphans[:3]),
                                "Run: SELECT COUNT(*) FROM decision_nodes dn WHERE NOT EXISTS (SELECT 1 FROM decision_edges WHERE to_node=dn.node_id) AND dn.node_type != 'root' — should be 0.",
                                YELLOW))
        except sqlite3.OperationalError:
            pass
        # Dead-end nodes (no outgoing edges, not terminal)
        try:
            cc.execute("""SELECT dn.node_id, dn.name, dn.domain FROM decision_nodes dn
                         WHERE NOT EXISTS (SELECT 1 FROM decision_edges WHERE from_node=dn.node_id)
                         AND dn.node_type != 'terminal'""")
            dead_ends = cc.fetchall()
            if dead_ends:
                findings.append(("COGNITIVE", "HIGH", str(len(dead_ends)) + " dead-end nodes (no outgoing edges)",
                                "The graph can reach these nodes but can't proceed. Incomplete paths. AI would get stuck here.",
                                "Add outgoing edges or mark as terminal. Examples: " + ", ".join(r[1] for r in dead_ends[:3]),
                                "Run: SELECT COUNT(*) FROM decision_nodes dn WHERE NOT EXISTS (SELECT 1 FROM decision_edges WHERE from_node=dn.node_id) AND dn.node_type != 'terminal' — should be 0.",
                                YELLOW))
        except sqlite3.OperationalError:
            pass
        # Empty node payloads
        try:
            cc.execute("SELECT COUNT(*) FROM decision_nodes WHERE payload IS NULL OR payload = ''")
            empty_payloads = cc.fetchone()[0]
            if empty_payloads > 0:
                findings.append(("COGNITIVE", "HIGH", str(empty_payloads) + " nodes have empty payloads",
                                "Nodes without payloads can't execute. They're placeholders with no behavior. Incomplete definitions.",
                                "Fill in payloads for these nodes with BCL instructions or action descriptions",
                                "Run: SELECT COUNT(*) FROM decision_nodes WHERE payload IS NULL OR payload = '' — should be 0.",
                                YELLOW))
        except sqlite3.OperationalError:
            pass
        # ── 4. ANALYZER GAPS ──
        # Run state
        run_count = safe_count('run_state', "SELECT COUNT(*) FROM run_state")
        if run_count == 0:
            findings.append(("ANALYZER", "MEDIUM", "No runs have been executed",
                            "The graph engine has never been run. Nodes and edges exist but nothing has been traversed. We don't know if the graph actually works.",
                            "Run the graph engine through a test path",
                            "Run: SELECT COUNT(*) FROM run_state — should be > 0 after a test run.",
                            YELLOW))
        # Execution contracts — check all node types have contracts
        if table_exists('execution_contracts'):
            cc.execute("SELECT COUNT(*) FROM execution_contracts")
            contract_count = cc.fetchone()[0]
            cc.execute("SELECT DISTINCT node_type FROM decision_nodes")
            all_node_types = set(r[0] for r in cc.fetchall())
            cc.execute("SELECT DISTINCT node_type FROM execution_contracts")
            contracted_types = set(r[0] for r in cc.fetchall())
            missing_contracts = all_node_types - contracted_types
            if contract_count < 4:
                findings.append(("ANALYZER", "MEDIUM", "Only " + str(contract_count) + " execution contracts (need 4)",
                                "Not all node types have contracts. Some transitions aren't validated.",
                                "Create contracts for: action, check, question, fallback",
                                "Run: SELECT node_type FROM execution_contracts — should show all 4 types.",
                                YELLOW))
            if missing_contracts:
                findings.append(("ANALYZER", "HIGH", "Node types without contracts: " + ", ".join(missing_contracts),
                                "These node types exist in the graph but have no execution contract. Transitions can't be validated.",
                                "Create contracts for: " + ", ".join(missing_contracts),
                                "Run: SELECT node_type FROM execution_contracts — should include all node types.",
                                YELLOW))
        else:
            findings.append(("ANALYZER", "HIGH", "execution_contracts table does not exist",
                            "No type system for nodes. Invalid transitions aren't caught before runtime.",
                            "Build execution_contracts table (was built before — check if it was lost)",
                            "Run: SELECT name FROM sqlite_master WHERE name='execution_contracts' — should exist.",
                            RED))
        # Plans with no steps
        if table_exists('plans') and table_exists('plan_steps'):
            cc.execute("""SELECT p.name FROM plans p
                         WHERE NOT EXISTS (SELECT 1 FROM plan_steps WHERE plan_id=p.id)""")
            empty_plans = cc.fetchall()
            if empty_plans:
                findings.append(("ANALYZER", "MEDIUM", str(len(empty_plans)) + " plans have no steps: " + ", ".join(r[0] for r in empty_plans[:3]),
                                "Plans without steps are incomplete. They represent intentions with no execution path.",
                                "Add steps to these plans",
                                "Run: SELECT p.name FROM plans p WHERE NOT EXISTS (SELECT 1 FROM plan_steps WHERE plan_id=p.id) — should be empty.",
                                YELLOW))
        # Orchestration entries
        if table_exists('orchestration') and table_exists('plans'):
            orch_count = safe_count('orchestration', "SELECT COUNT(*) FROM orchestration")
            if orch_count == 0:
                findings.append(("ANALYZER", "HIGH", "No orchestration entries exist",
                                "Plans can't be executed without orchestration. The execution order is undefined.",
                                "Create orchestration entries for all plans",
                                "Run: SELECT COUNT(*) FROM orchestration — should be > 0.",
                                YELLOW))
            else:
                cc.execute("""SELECT COUNT(DISTINCT p.id) FROM plans p
                             WHERE p.id NOT IN (SELECT plan_id FROM orchestration WHERE plan_id IS NOT NULL)""")
                unorchestrated = cc.fetchone()[0]
                if unorchestrated > 0:
                    findings.append(("ANALYZER", "HIGH", str(unorchestrated) + " plans have no orchestration",
                                    "These plans exist but can't be executed — no orchestration defines their execution order.",
                                    "Create orchestration entries for these plans",
                                    "Run: SELECT COUNT(*) FROM plans WHERE id NOT IN (SELECT plan_id FROM orchestration) — should be 0.",
                                    YELLOW))
        # Computational units missing for classes
        if table_exists('computational_units') and table_exists('classes'):
            cc.execute("""SELECT COUNT(*) FROM classes c
                         WHERE NOT EXISTS (SELECT 1 FROM computational_units WHERE class_id=c.id)""")
            missing_units = cc.fetchone()[0]
            if missing_units > 0:
                findings.append(("ANALYZER", "MEDIUM", str(missing_units) + " classes have no computational units",
                                "Computational units group tightly-coupled methods. Without them, the system can't understand which methods work together.",
                                "Create computational units for these classes",
                                "Run: SELECT COUNT(*) FROM classes c WHERE NOT EXISTS (SELECT 1 FROM computational_units WHERE class_id=c.id) — should be 0.",
                                YELLOW))
        # Search index sync
        if table_exists('search_idx') and table_exists('methods'):
            search_count = safe_count('search_idx', "SELECT COUNT(*) FROM search_idx")
            cc.execute("SELECT COUNT(*) FROM methods")
            method_total = cc.fetchone()[0]
            if search_count < method_total * 0.9:
                findings.append(("ANALYZER", "MEDIUM", "Search index out of sync: " + str(search_count) + " entries for " + str(method_total) + " methods",
                                "FTS5 search index doesn't match method count. AI can't find code by keyword.",
                                "Rebuild search_idx from methods table",
                                "Run: SELECT COUNT(*) FROM search_idx — should be close to method count.",
                                YELLOW))
        # View descriptors
        if not table_exists('view_descriptors'):
            findings.append(("ANALYZER", "LOW", "view_descriptors table does not exist",
                            "Views are not defined as SQL projections. The 8 graph views (Plan, Spec, Flow, etc.) aren't formalized.",
                            "Build view_descriptors table with 8 view definitions",
                            "Run: SELECT name FROM sqlite_master WHERE name='view_descriptors' — should exist.",
                            BLUE))
        # Schema registry
        if not table_exists('graph_schema_registry'):
            findings.append(("ANALYZER", "LOW", "graph_schema_registry table does not exist",
                            "No schema versioning. Schema could drift without detection.",
                            "Build graph_schema_registry table",
                            "Run: SELECT name FROM sqlite_master WHERE name='graph_schema_registry' — should exist.",
                            BLUE))
        # ── 5. DB HEALTH ──
        null_domain_classes = safe_count('classes', "SELECT COUNT(*) FROM classes WHERE domain IS NULL OR domain = ''")
        if null_domain_classes > 0:
            findings.append(("HEALTH", "MEDIUM", str(null_domain_classes) + " classes have no domain",
                            "These classes are unclassified. They can't be found by domain search.",
                            "Assign domains to these classes",
                            "Run: SELECT COUNT(*) FROM classes WHERE domain IS NULL OR domain = '' — should be 0.",
                            YELLOW))
        # Methods without Tuple3
        no_tuple3 = safe_count('methods', "SELECT COUNT(*) FROM methods WHERE returns_tuple3 = 0")
        cc.execute("SELECT COUNT(*) FROM methods")
        total_methods = cc.fetchone()[0]
        if no_tuple3 > 0:
            pct = (no_tuple3 / total_methods * 100) if total_methods > 0 else 0
            findings.append(("HEALTH", "MEDIUM", str(no_tuple3) + " of " + str(total_methods) + " methods don't return Tuple3 (" + str(round(pct, 1)) + "%)",
                            "VBStyle requires all methods return Tuple3. These don't follow the rule.",
                            "Refactor methods to return (1, data, None) or (0, None, error)",
                            "Run: SELECT COUNT(*) FROM methods WHERE returns_tuple3 = 0 — should be 0.",
                            YELLOW))
        # Methods with print() in code (Python check, not SQL LIKE)
        try:
            cc.execute("SELECT id, method_name, method_code FROM methods")
            print_methods = []
            self_underscore_methods = []
            decorator_methods = []
            hardcoded_path_methods = []
            for r in cc.fetchall():
                mid, mname, mcode = r
                if not mcode:
                    continue
                # Check for print() not in comments
                for line in mcode.split('\n'):
                    stripped = line.strip()
                    if 'print(' in stripped and not stripped.startswith('#'):
                        print_methods.append(mname)
                        break
                # Check for self._ (literal underscore)
                if 'self._' in mcode:
                    self_underscore_methods.append(mname)
                # Check for decorators
                for line in mcode.split('\n'):
                    stripped = line.strip()
                    if stripped.startswith('@') and not stripped.startswith('@GHOST') and not stripped.startswith('@VBSTYLE'):
                        decorator_methods.append(mname)
                        break
                # Check for hardcoded paths
                if '/Users/' in mcode or '/home/' in mcode or 'C:\\\\' in mcode:
                    # Exclude if it's in a comment or docstring line
                    for line in mcode.split('\n'):
                        stripped = line.strip()
                        if ('/Users/' in stripped or '/home/' in stripped) and not stripped.startswith('#'):
                            hardcoded_path_methods.append(mname)
                            break
            if print_methods:
                findings.append(("HEALTH", "MEDIUM", str(len(print_methods)) + " methods use print(): " + ", ".join(print_methods[:3]),
                                "VBStyle forbids print() — use return Tuple3.",
                                "Remove all print() calls",
                                "Run: grep -n 'print(' *.py — should be empty",
                                YELLOW))
            if self_underscore_methods:
                findings.append(("HEALTH", "MEDIUM", str(len(self_underscore_methods)) + " methods use self._ (private attributes): " + ", ".join(self_underscore_methods[:3]),
                                "VBStyle requires self.state dict only, no self._private. These break the state management model.",
                                "Replace self._xxx with self.state['xxx']",
                                "Run: SELECT method_name FROM methods WHERE method_code LIKE '%self._%' — should be empty (check with Python, not SQL LIKE).",
                                YELLOW))
            if decorator_methods:
                findings.append(("HEALTH", "MEDIUM", str(len(decorator_methods)) + " methods use decorators: " + ", ".join(decorator_methods[:3]),
                                "VBStyle forbids decorators. They add hidden behavior the reasoning engine can't track.",
                                "Remove @property, @staticmethod, @classmethod decorators",
                                "Run: grep '@' in method_code (excluding @GHOST, @VBSTYLE) — should find nothing.",
                                YELLOW))
            if hardcoded_path_methods:
                findings.append(("HEALTH", "MEDIUM", str(len(hardcoded_path_methods)) + " methods have hardcoded paths: " + ", ".join(hardcoded_path_methods[:3]),
                                "Hardcoded paths break portability. Code won't run in different environments.",
                                "Replace hardcoded paths with Config class paths",
                                "Run: grep '/Users/' in method_code — should find nothing.",
                                YELLOW))
        except sqlite3.OperationalError:
            pass
        # Undocumented computational units
        if table_exists('computational_units'):
            cc.execute("SELECT COUNT(*) FROM computational_units WHERE description IS NULL OR description = ''")
            undocumented = cc.fetchone()[0]
            if undocumented > 0:
                findings.append(("HEALTH", "LOW", str(undocumented) + " computational units have no description",
                                "Undocumented units are hard to understand. AI can't reason about what they do.",
                                "Add descriptions to all computational units",
                                "Run: SELECT COUNT(*) FROM computational_units WHERE description IS NULL OR description = '' — should be 0.",
                                BLUE))
        conn.close()
        # ═══ Draw findings ═══
        # Summary banner
        critical = sum(1 for f in findings if f[1] == "CRITICAL")
        high = sum(1 for f in findings if f[1] == "HIGH")
        medium = sum(1 for f in findings if f[1] == "MEDIUM")
        low = sum(1 for f in findings if f[1] == "LOW")
        c.create_text(cx, y, text="FINDINGS: " + str(len(findings)) + " total  —  " +
                      str(critical) + " CRITICAL  |  " + str(high) + " HIGH  |  " +
                      str(medium) + " MEDIUM  |  " + str(low) + " LOW",
                      font=("Courier", 12, "bold"), fill=ACCENT)
        y += 25
        # Color legend
        legend_y = y
        c.create_rectangle(cx - 350, legend_y, cx - 330, legend_y + 12, fill=RED, outline=RED)
        c.create_text(cx - 325, legend_y + 6, text="CRITICAL", font=("Courier", 8), fill=RED, anchor="w")
        c.create_rectangle(cx - 220, legend_y, cx - 200, legend_y + 12, fill=YELLOW, outline=YELLOW)
        c.create_text(cx - 195, legend_y + 6, text="HIGH", font=("Courier", 8), fill=YELLOW, anchor="w")
        c.create_rectangle(cx - 130, legend_y, cx - 110, legend_y + 12, fill="#856404", outline="#856404")
        c.create_text(cx - 105, legend_y + 6, text="MEDIUM", font=("Courier", 8), fill="#d29922", anchor="w")
        c.create_rectangle(cx, legend_y, cx + 20, legend_y + 12, fill=BLUE, outline=BLUE)
        c.create_text(cx + 25, legend_y + 6, text="LOW", font=("Courier", 8), fill=BLUE, anchor="w")
        y += 25
        # Group by category
        categories = ["GUARD", "NORMALIZE", "COGNITIVE", "ANALYZER", "HEALTH"]
        cat_colors = {"GUARD": RED, "NORMALIZE": PURPLE, "COGNITIVE": ORANGE, "ANALYZER": BLUE, "HEALTH": GREEN}
        for cat in categories:
            cat_findings = [f for f in findings if f[0] == cat]
            if not cat_findings:
                continue
            # Category header
            c.create_text(50, y, text="[" + cat + "] " + str(len(cat_findings)) + " findings",
                          font=("Courier", 12, "bold"), fill=cat_colors[cat], anchor="w")
            y += 20
            # Each finding — now with VERIFY line
            for finding in cat_findings:
                area, severity, issue, why, fix, verify, color = finding
                # Severity dot
                c.create_oval(60, y + 4, 72, y + 16, fill=color, outline=color)
                # Issue
                c.create_text(80, y + 10, text=issue, font=("Courier", 10, "bold"),
                              fill=color, anchor="w")
                y += 18
                # Why it matters
                c.create_text(90, y, text="WHY: " + why, font=("Courier", 9),
                              fill=TEXT, anchor="w")
                y += 14
                # Fix
                c.create_text(90, y, text="FIX: " + fix, font=("Courier", 9),
                              fill=GREEN, anchor="w")
                y += 14
                # Verify
                c.create_text(90, y, text="VERIFY: " + verify, font=("Courier", 8),
                              fill=BLUE, anchor="w")
                y += 18
            y += 10
        # ═══ Reasoning summary ═══
        y += 10
        c.create_text(cx, y, text="REASONING SUMMARY", font=("Courier", 14, "bold"), fill=ACCENT)
        y += 25
        summary_lines = []
        if critical > 0:
            summary_lines.append(("The DB is NOT guarded. " + str(critical) + " critical gaps allow AI to insert anything.", RED))
        else:
            summary_lines.append(("The DB guard is partially built. No critical gaps.", GREEN))
        if high > 0:
            summary_lines.append((str(high) + " high-priority gaps need attention before the system is reliable.", YELLOW))
        if empty_cat_count > 0:
            summary_lines.append(("graph_engine has " + str(empty_cat_count) + " nodes without categories — can't sort or search.", YELLOW))
        domains_without_loops = len(only_in_classes)
        if domains_without_loops > 0:
            summary_lines.append((str(domains_without_loops) + " domains have code but no cognitive loop — no reasoning path for AI.", YELLOW))
        if log_entries == 0:
            summary_lines.append(("Graph engine has never been run — we don't know if it actually works.", YELLOW))
        if not has_domain_reg:
            summary_lines.append(("Without registry tables, any AI can pollute the DB with typos. This is what happened.", RED))
        summary_lines.append(("TASK-085 (P0) tracks the full gate build. Priority: registry first, then cognitive loop gate.", GREEN))
        for line, color in summary_lines:
            c.create_text(50, y, text="→ " + line, font=("Courier", 10), fill=color, anchor="w")
            y += 16
        y += 10
        # The big picture
        c.create_text(cx, y, text="THE BIG PICTURE", font=("Courier", 12, "bold"), fill=ACCENT)
        y += 20
        c.create_text(50, y, text="What you're building:", font=("Courier", 10, "bold"), fill=TEXT, anchor="w")
        y += 15
        c.create_text(70, y, text="A self-modifying execution topology where code, failure, and reasoning all compile into the same structure.",
                      font=("Courier", 9), fill=TEXT, anchor="w")
        y += 15
        c.create_text(70, y, text="Code → graph → execution → failure logs → new graph → next run",
                      font=("Courier", 9), fill=GREEN, anchor="w")
        y += 15
        c.create_text(70, y, text="That closes the loop. But the loop is NOT closed yet.",
                      font=("Courier", 9), fill=YELLOW, anchor="w")
        y += 20
        c.create_text(50, y, text="What's working:", font=("Courier", 10, "bold"), fill=GREEN, anchor="w")
        y += 15
        c.create_text(70, y, text="✓ Code in DB (classes, methods, computational units)", font=("Courier", 9), fill=GREEN, anchor="w")
        y += 14
        c.create_text(70, y, text="✓ Cognitive loop nodes for workflow domain (38 nodes, 61 edges)", font=("Courier", 9), fill=GREEN, anchor="w")
        y += 14
        c.create_text(70, y, text="✓ Execution contracts (4 node types validated)", font=("Courier", 9), fill=GREEN, anchor="w")
        y += 14
        c.create_text(70, y, text="✓ BCL instructions (11 tokens as executable graph)", font=("Courier", 9), fill=GREEN, anchor="w")
        y += 14
        c.create_text(70, y, text="✓ Plans + orchestration", font=("Courier", 9), fill=GREEN, anchor="w")
        y += 20
        c.create_text(50, y, text="What's NOT working:", font=("Courier", 10, "bold"), fill=RED, anchor="w")
        y += 15
        c.create_text(70, y, text="✗ No registry — typos can pollute the DB", font=("Courier", 9), fill=RED, anchor="w")
        y += 14
        c.create_text(70, y, text="✗ No gate — AI can insert without permission", font=("Courier", 9), fill=RED, anchor="w")
        y += 14
        c.create_text(70, y, text="✗ No cognitive loop gate — code without reasoning enters freely", font=("Courier", 9), fill=RED, anchor="w")
        y += 14
        c.create_text(70, y, text="✗ graph_engine nodes uncategorized", font=("Courier", 9), fill=YELLOW, anchor="w")
        y += 14
        c.create_text(70, y, text="✗ Graph engine never run — untested", font=("Courier", 9), fill=YELLOW, anchor="w")
        y += 14
        c.create_text(70, y, text="✗ Most domains have no cognitive loop", font=("Courier", 9), fill=YELLOW, anchor="w")
        y += 20
        c.create_text(50, y, text="Build order (what to do next):", font=("Courier", 10, "bold"), fill=ACCENT, anchor="w")
        y += 15
        c.create_text(70, y, text="1. Build registry tables + triggers (Approach E — tested)", font=("Courier", 9), fill=GREEN, anchor="w")
        y += 14
        c.create_text(70, y, text="2. Fill graph_engine categories (44 nodes need categorizing)", font=("Courier", 9), fill=TEXT, anchor="w")
        y += 14
        c.create_text(70, y, text="3. Build cognitive loop gate (trigger that checks 7 nodes before insert)", font=("Courier", 9), fill=TEXT, anchor="w")
        y += 14
        c.create_text(70, y, text="4. Run the graph engine (test the decision tree end-to-end)", font=("Courier", 9), fill=TEXT, anchor="w")
        y += 14
        c.create_text(70, y, text="5. Create cognitive loops for remaining domains", font=("Courier", 9), fill=TEXT, anchor="w")
        y += 14
        c.create_text(70, y, text="6. Close the loop: execution → failure logs → new graph → next run", font=("Courier", 9), fill=TEXT, anchor="w")
        c.configure(scrollregion=(0, 0, w, y + 20))
    def build_yinyang_tab(self):
        """Yin/Yang adversarial visualization — red vs blue, see who wins"""
        # Top control bar
        ctrl = tk.Frame(self.yinyang_tab, bg=PANEL, height=50)
        ctrl.pack(fill="x", padx=5, pady=3)
        tk.Label(ctrl, text="YIN (Red — Attacker)", font=("Courier", 10, "bold"),
                 fg=RED, bg=PANEL).pack(side="left", padx=10)
        tk.Label(ctrl, text="vs", font=("Courier", 10), fg=GRAY, bg=PANEL).pack(side="left")
        tk.Label(ctrl, text="YANG (Blue — Defender)", font=("Courier", 10, "bold"),
                 fg=BLUE, bg=PANEL).pack(side="left", padx=10)
        # Controls
        tk.Label(ctrl, text="Steps:", font=("Courier", 9), fg=TEXT, bg=PANEL).pack(side="left", padx=(20, 5))
        self.yinyang_steps = tk.Entry(ctrl, width=6, font=("Courier", 9), bg=CARD, fg=TEXT,
                                      insertbackground=TEXT)
        self.yinyang_steps.insert(0, "200")
        self.yinyang_steps.pack(side="left")
        tk.Label(ctrl, text="Yin Strength:", font=("Courier", 9), fg=TEXT, bg=PANEL).pack(side="left", padx=(10, 5))
        self.yinyang_strength = tk.Entry(ctrl, width=6, font=("Courier", 9), bg=CARD, fg=TEXT,
                                         insertbackground=TEXT)
        self.yinyang_strength.insert(0, "0.6")
        self.yinyang_strength.pack(side="left")
        tk.Label(ctrl, text="Aggression:", font=("Courier", 9), fg=TEXT, bg=PANEL).pack(side="left", padx=(10, 5))
        self.yinyang_aggression = tk.Entry(ctrl, width=6, font=("Courier", 9), bg=CARD, fg=TEXT,
                                           insertbackground=TEXT)
        self.yinyang_aggression.insert(0, "0.4")
        self.yinyang_aggression.pack(side="left")
        self.yinyang_run_btn = tk.Button(ctrl, text="RUN BATTLE", font=("Courier", 10, "bold"),
                                         bg=ACCENT, fg=DARK, activebackground=RED,
                                         command=self.run_yinyang)
        self.yinyang_run_btn.pack(side="left", padx=15)
        self.yinyang_status = tk.Label(ctrl, text="Ready", font=("Courier", 9),
                                       fg=GRAY, bg=PANEL)
        self.yinyang_status.pack(side="left", padx=10)
        # Canvas for visualization
        canvas = tk.Canvas(self.yinyang_tab, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.yinyang_tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.yinyang_canvas = canvas
        self.yinyang_result = None
        self.draw_yinyang_placeholder()
        return (1, None, None)
    def draw_yinyang_placeholder(self):
        c = self.yinyang_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 100:
            w = 1400
        cx = w // 2
        y = 100
        c.create_text(cx, y, text="YIN / YANG — ADVERSARIAL SIMULATION",
                      font=("Courier", 18, "bold"), fill=ACCENT)
        y += 30
        c.create_text(cx, y, text="Red attacks. Blue defends. See who wins.",
                      font=("Courier", 12), fill=TEXT)
        y += 30
        # Draw yin/yang symbol
        radius = 60
        c.create_oval(cx - radius, y, cx + radius, y + radius * 2,
                      outline=GRAY, width=2, fill=DARK)
        # Red half (top)
        c.create_arc(cx - radius, y, cx + radius, y + radius * 2,
                     start=90, extent=180, style="pieslice", fill="#1a0d0d", outline=RED)
        # Blue half (bottom)
        c.create_arc(cx - radius, y, cx + radius, y + radius * 2,
                     start=270, extent=180, style="pieslice", fill="#0d1a2e", outline=BLUE)
        # Small circles
        c.create_oval(cx - 15, y + radius - 15, cx + 15, y + radius + 15,
                      fill="#1a0d0d", outline=RED)
        c.create_oval(cx - 8, y + radius - 8, cx + 8, y + radius + 8,
                      fill=RED, outline=RED)
        c.create_oval(cx - 15, y + radius - 15, cx + 15, y + radius + 15,
                      fill="#0d1a2e", outline=BLUE)
        y += radius * 2 + 40
        c.create_text(cx, y, text="Press RUN BATTLE to start",
                      font=("Courier", 11), fill=YELLOW)
        y += 20
        c.create_text(cx, y, text="Yang explores the graph. Yin attacks with poison, fear, blocks, false rewards.",
                      font=("Courier", 9), fill=GRAY)
        y += 15
        c.create_text(cx, y, text="Yang defends through consolidation (sleep). Winner is decided by survival + coverage.",
                      font=("Courier", 9), fill=GRAY)
        c.configure(scrollregion=(0, 0, w, y + 20))
        return (1, None, None)
    def run_yinyang(self):
        """Run the yin/yang simulation in a background thread"""
        self.yinyang_run_btn.config(state="disabled", text="RUNNING...")
        self.yinyang_status.config(text="Building graph...", fg=YELLOW)
        import threading
        def run_in_bg():
            try:
                self.yinyang_status.config(text="Running simulation...", fg=YELLOW)
                result = self.execute_yinyang()
                self.yinyang_result = result
                self.yinyang_status.config(text="Done — drawing results", fg=GREEN)
                self.draw_yinyang_result(result)
                self.yinyang_run_btn.config(state="normal", text="RUN BATTLE")
            except Exception as e:
                self.yinyang_status.config(text="Error: " + str(e), fg=RED)
                self.yinyang_run_btn.config(state="normal", text="RUN BATTLE")
        t = threading.Thread(target=run_in_bg, daemon=True)
        t.start()
        return (1, None, None)
        return (1, None, None)
    def execute_yinyang(self):
        """Execute the yin/yang simulation using the agent graph engine"""
        import sys
        sys.path.insert(0, "/Users/wws/Qdrant_mysql_mlx_vector_engine/efl_brain")
        try:
            from Efi_agent_graph import AgentGraph, ROOT
        except ImportError as e:
            return (1, {"error": "Cannot import Efi_agent_graph: " + str(e)}, None)
        try:
            steps = int(self.yinyang_steps.get())
            yin_strength = float(self.yinyang_strength.get())
            yin_aggression = float(self.yinyang_aggression.get())
        except ValueError:
            return (1, {"error": "Invalid parameters"}, None)
        graph = AgentGraph()
        graph.Build(ROOT)
        # Find a start node
        config_nodes = [nid for nid in graph.nodes if graph.nodes[nid].type == "CONFIG"]
        if config_nodes:
            start = config_nodes[0]
        else:
            start = list(graph.nodes.keys())[0] if graph.nodes else None
        if not start:
            return (1, {"error": "No nodes in graph"}, None)
        ok, result, err = graph.Run("yin_yang", {
            "start": start,
            "steps": steps,
            "yin_strength": yin_strength,
            "yin_aggression": yin_aggression,
        })
        if not ok:
            return (1, {"error": err}, None)
        return (1, result, None)
    def draw_yinyang_result(self, result):
        """Draw the yin/yang battle results as red vs blue"""
        c = self.yinyang_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 100:
            w = 1400
        cx = w // 2
        y = 20
        if "error" in result:
            c.create_text(cx, y, text="ERROR: " + result["error"],
                          font=("Courier", 12), fill=RED)
            c.configure(scrollregion=(0, 0, w, y + 20))
            return (1, None, None)
        # Title
        c.create_text(cx, y, text="BATTLE RESULTS — YIN vs YANG",
                      font=("Courier", 18, "bold"), fill=ACCENT)
        y += 25
        # ═══ Determine winner ═══
        yang_score = 0
        yin_score = 0
        # Yang scores for survival, coverage, goals, resistance
        coverage = result.get("coverage", 0)
        goals_completed = result.get("goals", {}).get("completed", 0)
        goals_total = result.get("goals", {}).get("total_goals", 1)
        yang_resisted = result.get("yang_resisted", 0)
        edges_grown = result.get("edges_grown", 0)
        edges_pruned = result.get("edges_pruned", 0)
        prediction_links = result.get("prediction_links", 0)
        steps_taken = result.get("steps", 0)
        unique_visited = result.get("unique_nodes_visited", 0)
        total_nodes = result.get("total_nodes", 1)
        emotion = result.get("emotion", {})
        mood = emotion.get("mood", 0)
        frustration = emotion.get("frustration", 0)
        consolidation = result.get("consolidation", {})
        sleep_cycles = consolidation.get("consolidation_count", 0)
        links_pruned = consolidation.get("links_pruned", 0)
        fear_decayed = consolidation.get("fear_decayed", 0)
        novelty_refreshed = consolidation.get("novelty_refreshed", 0)
        yin = result.get("yin", {})
        yin_attacks = yin.get("attack_count", 0)
        yin_attacks_detail = yin.get("attacks", {})
        poison_count = yin_attacks_detail.get("poison_links", 0)
        fear_count = yin_attacks_detail.get("inject_fear", 0)
        block_count = yin_attacks_detail.get("block_nodes", 0)
        false_reward_count = yin_attacks_detail.get("false_reward", 0)
        # Yang score: coverage + goals + resistance + mood - frustration
        yang_score = (coverage * 100 * 2 +
                      goals_completed * 50 +
                      yang_resisted * 5 +
                      mood * 100 +
                      sleep_cycles * 10 +
                      links_pruned * 3)
        # Yin score: attacks landed + frustration caused + links pruned by yin
        yin_score = (yin_attacks * 10 +
                     frustration * 100 +
                     poison_count * 15 +
                     block_count * 10 +
                     false_reward_count * 12 +
                     fear_count * 8)
        # Determine winner
        if yang_score > yin_score:
            winner = "YANG (Blue)"
            winner_color = BLUE
            winner_bg = "#0d1a2e"
        elif yin_score > yang_score:
            winner = "YIN (Red)"
            winner_color = RED
            winner_bg = "#1a0d0d"
        else:
            winner = "DRAW"
            winner_color = YELLOW
            winner_bg = "#1a1a0d"
        # ═══ Winner banner ═══
        banner_y = y
        c.create_rectangle(50, banner_y, w - 50, banner_y + 50,
                          outline=winner_color, width=3, fill=winner_bg)
        c.create_text(cx, banner_y + 25, text="WINNER: " + winner,
                      font=("Courier", 20, "bold"), fill=winner_color)
        y += 70
        # ═══ Score bars — red vs blue ═══
        c.create_text(cx, y, text="SCORE BATTLE", font=("Courier", 14, "bold"), fill=ACCENT)
        y += 25
        max_score = max(yang_score, yin_score, 1)
        bar_w = 500
        bar_x = cx - bar_w // 2
        # Yang bar (blue, left to right)
        yang_bar_len = int((yang_score / max_score) * bar_w)
        c.create_rectangle(bar_x, y, bar_x + bar_w, y + 25, outline=GRAY, fill=DARK)
        c.create_rectangle(bar_x, y, bar_x + yang_bar_len, y + 25, outline=BLUE, fill=BLUE)
        c.create_text(bar_x + 5, y + 12, text="YANG " + str(int(yang_score)),
                      font=("Courier", 10, "bold"), fill=DARK if yang_bar_len > 60 else BLUE, anchor="w")
        y += 30
        # Yin bar (red, left to right)
        yin_bar_len = int((yin_score / max_score) * bar_w)
        c.create_rectangle(bar_x, y, bar_x + bar_w, y + 25, outline=GRAY, fill=DARK)
        c.create_rectangle(bar_x, y, bar_x + yin_bar_len, y + 25, outline=RED, fill=RED)
        c.create_text(bar_x + 5, y + 12, text="YIN  " + str(int(yin_score)),
                      font=("Courier", 10, "bold"), fill=DARK if yin_bar_len > 60 else RED, anchor="w")
        y += 40
        # ═══ Two columns: Yang (blue, left) vs Yin (red, right) ═══
        col_w = (w - 60) // 2
        yang_x = 30
        yin_x = 30 + col_w + 20
        # Yang column header
        c.create_rectangle(yang_x, y, yang_x + col_w, y + 30,
                          outline=BLUE, width=2, fill="#0d1a2e")
        c.create_text(yang_x + col_w // 2, y + 15, text="YANG (Blue — Defender)",
                      font=("Courier", 12, "bold"), fill=BLUE)
        y_yang = y + 40
        # Yang stats
        yang_stats = [
            ("Steps Taken", str(steps_taken)),
            ("Nodes Visited", str(unique_visited) + " / " + str(total_nodes)),
            ("Coverage", str(round(coverage * 100, 1)) + "%"),
            ("Goals Completed", str(goals_completed) + " / " + str(goals_total)),
            ("Prediction Links", str(prediction_links)),
            ("Edges Grown", str(edges_grown)),
            ("Edges Pruned", str(edges_pruned)),
            ("Blocked Encounters Resisted", str(yang_resisted)),
            ("Mood", str(round(mood, 4))),
            ("Frustration", str(round(frustration, 4))),
        ]
        for label, value in yang_stats:
            c.create_text(yang_x + 10, y_yang, text=label + ":",
                          font=("Courier", 9), fill=GRAY, anchor="w")
            c.create_text(yang_x + col_w - 10, y_yang, text=value,
                          font=("Courier", 9, "bold"), fill=BLUE, anchor="e")
            y_yang += 16
        y_yang += 10
        # Yang defense (consolidation)
        c.create_text(yang_x, y_yang, text="DEFENSE (Consolidation/Sleep):",
                      font=("Courier", 10, "bold"), fill=BLUE, anchor="w")
        y_yang += 18
        defense_stats = [
            ("Sleep Cycles", str(sleep_cycles)),
            ("Poisoned Links Pruned", str(links_pruned)),
            ("Fear Decayed", str(round(fear_decayed, 4))),
            ("Novelty Refreshed", str(novelty_refreshed)),
        ]
        for label, value in defense_stats:
            c.create_text(yang_x + 10, y_yang, text=label + ":",
                          font=("Courier", 9), fill=GRAY, anchor="w")
            c.create_text(yang_x + col_w - 10, y_yang, text=value,
                          font=("Courier", 9, "bold"), fill=GREEN, anchor="e")
            y_yang += 16
        # Yin column header
        c.create_rectangle(yin_x, y, yin_x + col_w, y + 30,
                          outline=RED, width=2, fill="#1a0d0d")
        c.create_text(yin_x + col_w // 2, y + 15, text="YIN (Red — Attacker)",
                      font=("Courier", 12, "bold"), fill=RED)
        y_yin = y + 40
        # Yin stats
        yin_stats = [
            ("Total Attacks", str(yin_attacks)),
            ("Strength", str(round(yin.get("strength", 0), 2))),
            ("Aggression", str(round(yin.get("aggression", 0), 2))),
            ("Intelligence", str(round(yin.get("intelligence", 0), 2))),
        ]
        for label, value in yin_stats:
            c.create_text(yin_x + 10, y_yin, text=label + ":",
                          font=("Courier", 9), fill=GRAY, anchor="w")
            c.create_text(yin_x + col_w - 10, y_yin, text=value,
                          font=("Courier", 9, "bold"), fill=RED, anchor="e")
            y_yin += 16
        y_yin += 10
        # Attack breakdown
        c.create_text(yin_x, y_yin, text="ATTACK BREAKDOWN:",
                      font=("Courier", 10, "bold"), fill=RED, anchor="w")
        y_yin += 18
        attacks = [
            ("Poison Links", poison_count, "#e74c3c"),
            ("Inject Fear", fear_count, "#c0392b"),
            ("Block Nodes", block_count, "#e67e22"),
            ("False Reward", false_reward_count, "#a93226"),
        ]
        for label, count, color in attacks:
            c.create_text(yin_x + 10, y_yin, text=label + ":",
                          font=("Courier", 9), fill=GRAY, anchor="w")
            c.create_text(yin_x + col_w - 10, y_yin, text=str(count),
                          font=("Courier", 9, "bold"), fill=color, anchor="e")
            y_yin += 16
        # Attack bars
        y_yin += 10
        max_attack = max(poison_count, fear_count, block_count, false_reward_count, 1)
        for label, count, color in attacks:
            c.create_text(yin_x + 10, y_yin, text=label,
                          font=("Courier", 8), fill=GRAY, anchor="w")
            bar_len = int((count / max_attack) * 200)
            c.create_rectangle(yin_x + 100, y_yin - 5, yin_x + 100 + bar_len, y_yin + 5,
                              fill=color, outline=color)
            c.create_text(yin_x + 100 + bar_len + 5, y_yin, text=str(count),
                          font=("Courier", 8), fill=TEXT, anchor="w")
            y_yin += 14
        y = max(y_yang, y_yin) + 30
        # ═══ Battle timeline ═══
        c.create_text(cx, y, text="BATTLE TIMELINE", font=("Courier", 14, "bold"), fill=ACCENT)
        y += 25
        path = result.get("path", [])
        if path:
            # Draw timeline as a line with dots — blue for normal, red for under attack
            timeline_w = w - 100
            timeline_x = 50
            timeline_y = y
            # Background line
            c.create_line(timeline_x, timeline_y, timeline_x + timeline_w, timeline_y,
                         fill=GRAY, width=2)
            # Plot each step
            step_count = len(path)
            if step_count > 0:
                step_gap = timeline_w / max(step_count, 1)
                for i, step_data in enumerate(path):
                    sx = timeline_x + int(i * step_gap)
                    under_attack = step_data.get("under_attack", False)
                    success = step_data.get("success", False)
                    if under_attack:
                        c.create_oval(sx - 3, timeline_y - 3, sx + 3, timeline_y + 3,
                                     fill=RED, outline=RED)
                    elif success:
                        c.create_oval(sx - 2, timeline_y - 2, sx + 2, timeline_y + 2,
                                     fill=BLUE, outline=BLUE)
                    else:
                        c.create_oval(sx - 1, timeline_y - 1, sx + 1, timeline_y + 1,
                                     fill=GRAY, outline=GRAY)
            # Legend
            y += 20
            c.create_oval(timeline_x, y, timeline_x + 8, y + 8, fill=BLUE, outline=BLUE)
            c.create_text(timeline_x + 12, y + 4, text="Success (Yang explored)",
                          font=("Courier", 8), fill=BLUE, anchor="w")
            c.create_oval(timeline_x + 200, y, timeline_x + 208, y + 8, fill=RED, outline=RED)
            c.create_text(timeline_x + 212, y + 4, text="Under Attack (Yin struck)",
                          font=("Courier", 8), fill=RED, anchor="w")
            c.create_oval(timeline_x + 420, y, timeline_x + 428, y + 8, fill=GRAY, outline=GRAY)
            c.create_text(timeline_x + 432, y + 4, text="Neutral",
                          font=("Courier", 8), fill=GRAY, anchor="w")
            y += 20
            # Stats line
            attacks_in_timeline = sum(1 for s in path if s.get("under_attack", False))
            successes = sum(1 for s in path if s.get("success", False))
            c.create_text(cx, y, text="Steps: " + str(step_count) +
                         "  |  Successes: " + str(successes),
                         font=("Courier", 9), fill=TEXT)
            y += 20
        # ═══ Yin attacks log ═══
        yin_attacks_log = result.get("yin_attacks", [])
        if yin_attacks_log:
            c.create_text(cx, y, text="YIN ATTACK LOG (first 20)",
                          font=("Courier", 12, "bold"), fill=RED)
            y += 20
            for i, attack in enumerate(yin_attacks_log[:20]):
                step = attack.get("step", "?")
                atk_type = attack.get("attack", "?")
                conf_before = attack.get("yang_confidence_before", 0)
                c.create_text(50, y, text="Step " + str(step).ljust(4) +
                             "  →  " + atk_type.ljust(15),
                             font=("Courier", 8), fill=RED, anchor="w")
                y += 12
            if len(yin_attacks_log) > 20:
                c.create_text(50, y, text="... " + str(len(yin_attacks_log) - 20) + " more attacks",
                              font=("Courier", 8), fill=GRAY, anchor="w")
                y += 12
        y += 20
        # ═══ Verdict ═══
        c.create_text(cx, y, text="VERDICT", font=("Courier", 14, "bold"), fill=ACCENT)
        y += 20
        if winner == "YANG (Blue)":
            verdict = "Yang survived and explored " + str(round(coverage * 100, 1)) + "% of the graph."
            verdict += " Despite " + str(yin_attacks) + " attacks, Yang maintained mood at " + str(round(mood, 3)) + "."
            verdict += " Consolidation (sleep) pruned " + str(links_pruned) + " poisoned links."
            verdict_color = BLUE
        elif winner == "YIN (Red)":
            verdict = "Yin broke Yang's confidence with " + str(yin_attacks) + " attacks."
            verdict += " Yang's frustration reached " + str(round(frustration, 3)) + "."
            verdict += " Coverage was only " + str(round(coverage * 100, 1)) + "%."
            verdict_color = RED
        else:
            verdict = "Both sides fought to a draw."
            verdict_color = YELLOW
        # Wrap verdict text
        words = verdict.split()
        line = ""
        for word in words:
            test_line = line + word + " "
            if len(test_line) > 100:
                c.create_text(50, y, text=line, font=("Courier", 9), fill=verdict_color, anchor="w")
                y += 14
                line = word + " "
            else:
                line = test_line
        if line:
            c.create_text(50, y, text=line, font=("Courier", 9), fill=verdict_color, anchor="w")
            y += 14
        c.configure(scrollregion=(0, 0, w, y + 20))
    def load_data(self):
        if not os.path.exists(DB_PATH):
            self.status.config(text="DB not found", fg=RED)
            return (1, None, None)
        
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            # Stats
            c.execute("SELECT COUNT(*) FROM decision_nodes")
            node_count = c.fetchone()[0]
            self.stat_labels["nodes"].config(text=str(node_count))
            c.execute("SELECT COUNT(*) FROM decision_edges")
            edge_count = c.fetchone()[0]
            self.stat_labels["edges"].config(text=str(edge_count))
            c.execute("SELECT COUNT(DISTINCT domain) FROM decision_nodes WHERE domain IS NOT NULL")
            self.stat_labels["domains"].config(text=str(c.fetchone()[0]))
            c.execute("SELECT COUNT(*) FROM classes")
            class_count = c.fetchone()[0]
            self.stat_labels["classes"].config(text=str(class_count))
            c.execute("SELECT COUNT(*) FROM methods")
            method_count = c.fetchone()[0]
            self.stat_labels["methods"].config(text=str(method_count))
            c.execute("SELECT COUNT(*) FROM plans")
            self.stat_labels["plans"].config(text=str(c.fetchone()[0]))
            
            conn.close()
            
            # Track changes for live refresh
            changed = (node_count != self.last_node_count or
                       edge_count != self.last_edge_count or
                       class_count != self.last_class_count or
                       method_count != self.last_method_count)
            
            self.last_node_count = node_count
            self.last_edge_count = edge_count
            self.last_class_count = class_count
            self.last_method_count = method_count
            
            if changed:
                self.status.config(text="DB CHANGED — refreshing... (nodes=" + str(node_count) + " edges=" + str(edge_count) + ")", fg=YELLOW)
            else:
                now = datetime.now().strftime("%H:%M:%S")
                self.status.config(text="Live — " + now + " — monitoring v20_hybrid_best.db (nodes=" + str(node_count) + " edges=" + str(edge_count) + ")", fg=GREEN)
            
            # Draw all tabs
            self.draw_guard()
            self.draw_normalize()
            self.draw_graph()
            self.draw_reason()
            
        except Exception as e:
            self.status.config(text="Error: " + str(e), fg=RED)
    def start_live_refresh(self):
        """Poll DB every 3 seconds for changes"""
        def poll():
            if self.auto_refresh:
                self.load_data()
            self.root.after(3000, poll)
        self.root.after(3000, poll)
        return (1, None, None)
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