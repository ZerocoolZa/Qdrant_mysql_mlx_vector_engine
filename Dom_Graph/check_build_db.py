#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Debug script that queries _BuildDb method location from SQLite. NO VBStyle headers. print() x4. No Run() dispatch, no class, no Tuple3 returns. Hardcoded /Users/wws/ path. Not VBStyle compliant -- debug utility script.>][@todos<1. Add VBStyle identity headers. 2. Remove print() calls. 3. Wrap in a class with Run() dispatch and Tuple3 returns. 4. Remove hardcoded /Users/wws/ path.>]}
"""Update _BuildDb to execute GRAPH_SCHEMA and populate graph tables."""
import sqlite3
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_ingest.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Find _BuildDb method
cur.execute("SELECT lineno, text FROM source_lines WHERE file = 'Config.py' AND text LIKE '%def _BuildDb%'")
print("_BuildDb location:")
for lineno, text in cur.fetchall():
    print(f"  Line {lineno}: {text}")

# Show _BuildDb method body
cur.execute("SELECT lineno, text FROM source_lines WHERE file = 'Config.py' AND lineno BETWEEN 1080 and 1138")
print("\n_BuildDb method:")
for lineno, text in cur.fetchall():
    print(f"{lineno:4}: {text}")

conn.close()
