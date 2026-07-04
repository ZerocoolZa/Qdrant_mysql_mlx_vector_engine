#!/usr/bin/env python3
"""
Database Gap Graph — scans the REAL v20 database and finds ALL gaps.

Unlike the domain-specific graph tools (gap_graph.py etc.) which are
hardcoded for the archive domain, this tool reads the actual database
and checks:

  1. DOCUMENTATION gaps  — tables/columns without docs
  2. BCL IDENTITY gaps   — entities without BCL tokens or missing fields
  3. CLOSURE gaps        — domains with missing methods
  4. STRUCTURE gaps      — missing pairs, missing CRUD, isolated domains
  5. ORCHESTRATION gaps  — domains not used in any pipeline
  6. PLAN gaps           — too few plans for the number of domains
  7. EXECUTION gaps      — nothing has run
  8. VIOLATION gaps      — VBStyle rule violations

Output: text report + optional GUI graph showing gaps visually.
"""

import sqlite3
import os
import sys
import json
from collections import defaultdict

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "code_store_variations", "v20_hybrid_best.db"
)


# ════════════════════════════════════════════════════════════════════════
# GAP DETECTOR — reads the real database and finds all gaps
# ════════════════════════════════════════════════════════════════════════

class DatabaseGapDetector:
    """Scans v20_hybrid_best.db and reports every gap found."""

    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.c = self.conn.cursor()
        self.gaps = []

    def add_gap(self, category, severity, entity, issue, detail=""):
        self.gaps.append({
            "category": category,
            "severity": severity,
            "entity": entity,
            "issue": issue,
            "detail": detail,
        })

    # ─── 1. DOCUMENTATION GAPS ───────────────────────────────────────

    def check_documentation(self):
        """Tables without _table_registry entries, columns without _column_docs."""
        # Get all real tables (exclude FTS5 virtual tables and sqlite internal)
        self.c.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE '%_fts%'
            AND name NOT LIKE 'search_idx%'
            AND name NOT LIKE 'bcl_search%'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        all_tables = [r[0] for r in self.c.fetchall()]

        # Check _table_registry
        self.c.execute("SELECT table_name FROM _table_registry")
        registered = set(r[0] for r in self.c.fetchall())

        for table in all_tables:
            if table not in registered:
                self.add_gap("DOCUMENTATION", "high", table,
                             "Table not in _table_registry",
                             f"Table '{table}' exists but has no entry in _table_registry. AI won't know what it's for.")

        # Check _column_docs for each table
        self.c.execute("SELECT DISTINCT table_name FROM _column_docs")
        documented_tables = set(r[0] for r in self.c.fetchall())

        for table in all_tables:
            if table not in documented_tables:
                self.add_gap("DOCUMENTATION", "high", table,
                             "Table has no column docs",
                             f"Table '{table}' has no entries in _column_docs. AI won't understand its columns.")

            # Check individual columns
            self.c.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in self.c.fetchall()]
            self.c.execute("SELECT column_name FROM _column_docs WHERE table_name=?", (table,))
            documented_cols = set(r[0] for r in self.c.fetchall())

            for col in columns:
                if col not in documented_cols:
                    self.add_gap("DOCUMENTATION", "medium", f"{table}.{col}",
                                 "Column not documented",
                                 f"Column '{col}' in table '{table}' has no _column_docs entry.")

    # ─── 2. BCL IDENTITY GAPS ────────────────────────────────────────

    def check_bcl_identity(self):
        """Entities without BCL tokens, or tokens missing required fields."""
        required_fields = [
            "identity", "capabilities", "used_in_pipelines",
            "depends_on", "depended_by", "closure", "self_narrative"
        ]

        # Check VBStyle classes without BCL tokens
        self.c.execute("SELECT id, class_name FROM classes WHERE is_vbstyle=1")
        vb_classes = self.c.fetchall()
        vb_class_ids = set(r["id"] for r in vb_classes)

        self.c.execute("SELECT entity_id FROM bcl_identity WHERE entity_type='class'")
        bcl_class_ids = set(r["entity_id"] for r in self.c.fetchall())

        for cls in vb_classes:
            if cls["id"] not in bcl_class_ids:
                self.add_gap("BCL_IDENTITY", "high", cls["class_name"],
                             "VBStyle class has no BCL token",
                             f"Class '{cls['class_name']}' is VBStyle but has no BCL identity token.")

        # Check BCL tokens for missing fields
        self.c.execute("SELECT entity_type, entity_name, bcl_token FROM bcl_identity WHERE entity_type='domain'")
        for row in self.c.fetchall():
            bcl = row["bcl_token"]
            missing = [f for f in required_fields if f not in bcl]
            if missing:
                self.add_gap("BCL_IDENTITY", "medium", row["entity_name"],
                             f"BCL token missing fields: {', '.join(missing)}",
                             f"Domain '{row['entity_name']}' BCL token doesn't answer all 7 W-questions.")

        # Check parent_id chain
        self.c.execute("""
            SELECT entity_type, entity_name, parent_id FROM bcl_identity
            WHERE entity_type IN ('class', 'method') AND parent_id IS NULL
        """)
        for row in self.c.fetchall():
            self.add_gap("BCL_IDENTITY", "low", row["entity_name"],
                         f"{row['entity_type']} has no parent_id (orphan in chain)",
                         f"Entity '{row['entity_name']}' should have a parent_id linking to its parent.")

    # ─── 3. CLOSURE GAPS ─────────────────────────────────────────────

    def check_closure(self):
        """Domains with missing methods (closure < 100%)."""
        self.c.execute("SELECT domain, closure_pct, methods_missing, status FROM closure_status")
        for row in self.c.fetchall():
            if row["closure_pct"] < 100.0:
                self.add_gap("CLOSURE", "high", row["domain"],
                             f"Domain not fully closed ({row['closure_pct']}%)",
                             f"Domain '{row['domain']}' is missing {row['methods_missing']} methods. Status: {row['status']}.")

    # ─── 4. STRUCTURE GAPS ───────────────────────────────────────────

    def check_structure(self):
        """Missing pairs, missing CRUD, isolated domains."""
        # Get all VBStyle method names
        self.c.execute("""
            SELECT DISTINCT m.method_name FROM methods m
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle=1 AND m.method_name NOT LIKE '\\_%'
        """)
        all_methods = set(r[0] for r in self.c.fetchall())

        # Missing pairs
        expected_pairs = [
            ("compress", "decompress"), ("encrypt", "decrypt"), ("sign", "verify"),
            ("serialize", "deserialize"), ("encode", "decode"), ("import", "export"),
            ("load", "save"), ("start", "stop"), ("open", "close"), ("add", "remove"),
            ("create", "delete"), ("push", "pop"), ("lock", "unlock"),
            ("connect", "disconnect"), ("register", "unregister"),
            ("subscribe", "unsubscribe"), ("begin", "end"),
        ]
        for a, b in expected_pairs:
            has_a = a in all_methods
            has_b = b in all_methods
            if has_a and not has_b:
                self.add_gap("STRUCTURE", "medium", f"{a}/{b}",
                             f"Missing pair: {a}() exists but {b}() is missing",
                             f"Method '{a}' exists but its opposite '{b}' was not found.")
            elif has_b and not has_a:
                self.add_gap("STRUCTURE", "medium", f"{a}/{b}",
                             f"Missing pair: {b}() exists but {a}() is missing",
                             f"Method '{b}' exists but its opposite '{a}' was not found.")

        # CRUD gaps per domain
        crud = {
            "create": ["create", "add", "insert", "write", "compress", "generate", "build", "make"],
            "read":   ["read", "get", "fetch", "load", "list", "search", "find", "query"],
            "update": ["update", "edit", "modify", "rename", "patch", "set", "convert", "transform"],
            "delete": ["delete", "remove", "drop", "clear", "purge", "forget", "strip", "destroy"],
        }

        self.c.execute("SELECT DISTINCT domain FROM classes WHERE is_vbstyle=1 ORDER BY domain")
        domains = [r[0] for r in self.c.fetchall()]

        for domain in domains:
            self.c.execute("""
                SELECT DISTINCT m.method_name FROM methods m
                JOIN classes cl ON m.class_id = cl.id
                WHERE cl.is_vbstyle=1 AND cl.domain=? AND m.method_name NOT LIKE '\\_%'
            """, (domain,))
            methods = set(r[0].lower() for r in self.c.fetchall())
            missing = [r for r in crud if not any(m in crud[r] for m in methods)]
            if missing:
                self.add_gap("STRUCTURE", "low", domain,
                             f"CRUD gap: missing {', '.join(missing)}",
                             f"Domain '{domain}' has no {', '.join(missing)} operation.")

    # ─── 5. ORCHESTRATION GAPS ───────────────────────────────────────

    def check_orchestration(self):
        """Domains not used in any pipeline."""
        self.c.execute("""
            SELECT DISTINCT cl.domain FROM classes cl
            WHERE cl.is_vbstyle=1 AND cl.id NOT IN (
                SELECT class_id FROM orchestration
            )
            ORDER BY cl.domain
        """)
        isolated = [r[0] for r in self.c.fetchall()]
        for domain in isolated:
            self.add_gap("ORCHESTRATION", "medium", domain,
                         "Domain not used in any pipeline",
                         f"Domain '{domain}' is built and closed but not wired into any orchestration pipeline.")

    # ─── 6. PLAN GAPS ────────────────────────────────────────────────

    def check_plans(self):
        """Too few plans for the number of domains."""
        self.c.execute("SELECT COUNT(*) FROM plans")
        plan_count = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM classes WHERE is_vbstyle=1")
        domain_count = self.c.fetchone()[0]

        if plan_count < 5:
            self.add_gap("PLANS", "high", "system",
                         f"Only {plan_count} plan(s) for {domain_count} domains",
                         f"The system has {domain_count} VBStyle domains but only {plan_count} plan(s). Most domains are unused.")

        # Check for plans with no steps
        self.c.execute("SELECT id, name FROM plans")
        for plan in self.c.fetchall():
            self.c.execute("SELECT COUNT(*) FROM plan_steps WHERE plan_id=?", (plan["id"],))
            step_count = self.c.fetchone()[0]
            if step_count == 0:
                self.add_gap("PLANS", "high", plan["name"],
                             "Plan has no steps",
                             f"Plan '{plan['name']}' exists but has no plan_steps.")

    # ─── 7. EXECUTION GAPS ───────────────────────────────────────────

    def check_execution(self):
        """Nothing has actually run."""
        self.c.execute("SELECT COUNT(*) FROM execution_log")
        exec_count = self.c.fetchone()[0]
        if exec_count == 0:
            self.add_gap("EXECUTION", "medium", "system",
                         "No execution log entries — nothing has run",
                         "The execution_log table is empty. No plan or method has been executed.")

    # ─── 8. VIOLATION GAPS ───────────────────────────────────────────

    def check_violations(self):
        """VBStyle rule violations."""
        self.c.execute("SELECT kind, COUNT(*) as cnt FROM violations GROUP BY kind ORDER BY cnt DESC")
        for row in self.c.fetchall():
            self.add_gap("VIOLATIONS", "low", row["kind"],
                         f"{row['cnt']} violations of rule: {row['kind']}",
                         f"Found {row['cnt']} methods violating VBStyle rule '{row['kind']}'.")

    # ─── RUN ALL CHECKS ──────────────────────────────────────────────

    def run_all(self):
        self.gaps = []
        self.check_documentation()
        self.check_bcl_identity()
        self.check_closure()
        self.check_structure()
        self.check_orchestration()
        self.check_plans()
        self.check_execution()
        self.check_violations()
        return self.gaps

    def report(self):
        """Generate a text report of all gaps."""
        gaps = self.run_all()

        # Group by category
        by_category = defaultdict(list)
        for g in gaps:
            by_category[g["category"]].append(g)

        lines = []
        lines.append("=" * 70)
        lines.append("DATABASE GAP REPORT")
        lines.append("=" * 70)
        lines.append(f"\nTotal gaps found: {len(gaps)}")
        lines.append("")

        # Summary by category
        lines.append("── SUMMARY BY CATEGORY ──")
        for cat in ["DOCUMENTATION", "BCL_IDENTITY", "CLOSURE", "STRUCTURE",
                     "ORCHESTRATION", "PLANS", "EXECUTION", "VIOLATIONS"]:
            count = len(by_category.get(cat, []))
            if count == 0:
                lines.append(f"  ✅ {cat:15}: no gaps")
            else:
                lines.append(f"  ⚠️  {cat:15}: {count} gaps")

        # Detail by category
        for cat in ["DOCUMENTATION", "BCL_IDENTITY", "CLOSURE", "STRUCTURE",
                     "ORCHESTRATION", "PLANS", "EXECUTION", "VIOLATIONS"]:
            items = by_category.get(cat, [])
            if not items:
                continue
            lines.append(f"\n── {cat} ({len(items)} gaps) ──")
            for g in items[:20]:  # Show first 20
                lines.append(f"  [{g['severity']:6}] {g['entity']:30}: {g['issue']}")
            if len(items) > 20:
                lines.append(f"  ... and {len(items) - 20} more")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)

    def close(self):
        self.conn.close()


# ════════════════════════════════════════════════════════════════════════
# GUI GRAPH VIEWER — shows gaps visually
# ════════════════════════════════════════════════════════════════════════

def show_gui(gaps):
    """Show gaps in a tkinter GUI graph."""
    try:
        import math
        import tkinter as tk
    except ImportError:
        print("tkinter not available — skipping GUI")
        return

    # Group gaps by category
    by_category = defaultdict(list)
    for g in gaps:
        by_category[g["category"]].append(g)

    root = tk.Tk()
    root.title("Database Gap Graph — v20_hybrid_best.db")
    root.geometry("1200x800")
    root.configure(bg="#1e1e2e")

    # Title
    title = tk.Label(root, text=f"Database Gap Graph — {len(gaps)} gaps found",
                     fg="#cdd6f4", bg="#1e1e2e", font=("Helvetica", 16, "bold"))
    title.pack(pady=10)

    # Canvas
    canvas = tk.Canvas(root, bg="#1e1e2e", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Colors per category
    CAT_COLORS = {
        "DOCUMENTATION": "#f38ba8",  # red
        "BCL_IDENTITY":  "#fab387",  # orange
        "CLOSURE":       "#f9e2af",  # yellow
        "STRUCTURE":     "#a6e3a1",  # green
        "ORCHESTRATION": "#89b4fa",  # blue
        "PLANS":         "#cba6f7",  # purple
        "EXECUTION":     "#f38ba8",  # red
        "VIOLATIONS":    "#94e2d5",  # teal
    }

    SEVERITY_COLORS = {
        "high":   "#f38ba8",
        "medium": "#f9e2af",
        "low":    "#a6e3a1",
    }

    # Draw category nodes in a circle
    categories = list(by_category.keys())
    cx, cy = 600, 350
    radius = 250

    cat_positions = {}
    for i, cat in enumerate(categories):
        angle = (2 * math.pi * i) / max(len(categories), 1) - math.pi / 2
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        cat_positions[cat] = (x, y)

        # Draw category node
        color = CAT_COLORS.get(cat, "#89b4fa")
        canvas.create_oval(x - 40, y - 25, x + 40, y + 25,
                          fill=color, outline="#1e1e2e", width=2)
        canvas.create_text(x, y, text=f"{cat}\n{len(by_category[cat])} gaps",
                          fill="#1e1e2e", font=("Helvetica", 8, "bold"))

        # Draw gap items around the category
        items = by_category[cat]
        for j, item in enumerate(items[:8]):  # Show up to 8 per category
            item_angle = angle + (j - len(items[:8]) / 2) * 0.15
            ix = cx + (radius + 120) * math.cos(item_angle)
            iy = cy + (radius + 120) * math.sin(item_angle)

            sev_color = SEVERITY_COLORS.get(item["severity"], "#a6e3a1")

            # Line from category to item
            canvas.create_line(x, y, ix, iy, fill=sev_color, width=1, dash=(2, 2))

            # Item node
            canvas.create_oval(ix - 6, iy - 6, ix + 6, iy + 6,
                              fill=sev_color, outline="#1e1e2e", width=1)

            # Item label (truncated)
            label = item["entity"][:20]
            canvas.create_text(ix, iy + 15, text=label,
                             fill="#cdd6f4", font=("Helvetica", 7))

    # Center node
    canvas.create_oval(cx - 60, cy - 30, cx + 60, cy + 30,
                      fill="#cba6f7", outline="#1e1e2e", width=2)
    canvas.create_text(cx, cy, text="v20 DATABASE\n73 domains",
                      fill="#1e1e2e", font=("Helvetica", 10, "bold"))

    # Legend
    legend = tk.Frame(root, bg="#1e1e2e")
    legend.pack(pady=5)
    for sev, col in [("high", "#f38ba8"), ("medium", "#f9e2af"), ("low", "#a6e3a1")]:
        tk.Label(legend, text=f" {sev}", fg=col, bg="#1e1e2e",
                font=("Helvetica", 9)).pack(side=tk.LEFT, padx=10)

    root.mainloop()


# ════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════

def main():
    detector = DatabaseGapDetector()

    if "--gui" in sys.argv:
        gaps = detector.run_all()
        print(f"Found {len(gaps)} gaps. Opening GUI...")
        show_gui(gaps)
    else:
        print(detector.report())

    detector.close()


if __name__ == "__main__":
    main()
