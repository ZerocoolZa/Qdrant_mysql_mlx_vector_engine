#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Utility script to query DB for graph data patterns. NOT VBStyle: no VBStyle headers no class no Run() dispatch no Tuple3 returns. Has 6 print() calls. Hardcoded path (/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph). Procedural script with no class structure.>][@todos<1. Add VBStyle headers. 2. Remove print() calls. 3. Remove hardcoded paths. 4. Wrap in class with Run() dispatch and Tuple3 returns.>]}
"""Query DB to find graph data patterns."""
import sqlite3
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check for graph data variables
graph_vars = ["CATEGORIES", "CLASSES", "EDGES", "FLOWS", "REDGES", "ECOLORS", "EDGE_COLORS", "SCOLORS",
              "LIFECYCLE_PHASES", "CLASS_PHASE", "PHASE_COLORS", "PHASE_ORDER", "OPERATION_VERBS", "VERB_CATEGORY"]

print("Graph data variables in files:")
for var in graph_vars:
    cur.execute("SELECT DISTINCT file FROM src WHERE text LIKE ?", (var + "=%",))
    files = [row[0] for row in cur.fetchall()]
    if files:
        print(f"  {var:25} in {len(files)} files: {', '.join(files)}")

# Check which files have "from Config import"
print("\nFiles with Config import:")
cur.execute("SELECT DISTINCT file FROM src WHERE text LIKE '%from Config import%'")
for row in cur.fetchall():
    print(f"  {row[0]}")

# Check graph pipeline files
graph_files = ["PlanGraph.py", "SpecGraph.py", "SpecFlow.py", "LifecycleGraph.py", "DepGraph.py", "ErrorGraph.py", "OrchGraph.py", "GapGraph.py"]
print("\nGraph pipeline files status:")
for f in graph_files:
    cur.execute("SELECT COUNT(*) FROM src WHERE file = ?", (f,))
    lines = cur.fetchone()[0]
    print(f"  {f:20} {lines} lines")

conn.close()
