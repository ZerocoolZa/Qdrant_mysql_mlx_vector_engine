#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Debug script that looks up class names in DB class_registry. NO VBStyle headers. print() x4. No Run() dispatch, no class, no Tuple3 returns. Hardcoded /Users/wws/ path. Not VBStyle compliant -- debug utility script.>][@todos<1. Add VBStyle identity headers. 2. Remove print() calls. 3. Wrap in a class with Run() dispatch and Tuple3 returns. 4. Remove hardcoded /Users/wws/ path.>]}
"""Debug class lookup in DB."""
import sqlite3
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check Config class
cur.execute("SELECT * FROM class_registry WHERE class_name = 'Config'")
print("Config lookup:", cur.fetchone())

# Check all class names
cur.execute("SELECT class_name FROM class_registry")
print("\nAll class names:")
for row in cur.fetchall():
    print(f"  '{row[0]}'")

# Check SpecGraphViewer
cur.execute("SELECT * FROM class_registry WHERE class_name = 'SpecGraphViewer'")
print("\nSpecGraphViewer lookup:", cur.fetchone())

conn.close()
