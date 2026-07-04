#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Utility script to view Config.py structure from DB. NOT VBStyle: no VBStyle headers no class no Run() dispatch no Tuple3 returns. Has 5 print() calls. Hardcoded path (/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph). Procedural script with no class structure.>][@todos<1. Add VBStyle headers. 2. Remove print() calls. 3. Remove hardcoded paths. 4. Wrap in class with Run() dispatch and Tuple3 returns.>]}
"""View Config.py structure from DB."""
import sqlite3
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_ingest.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Find SCHEMA_SQL location
cur.execute("SELECT lineno, text FROM source_lines WHERE file = 'Config.py' AND text LIKE '%SCHEMA_SQL%'")
for lineno, text in cur.fetchall():
    print(f"Line {lineno}: {text}")

# Find the closing triple quote
cur.execute("SELECT lineno, text FROM source_lines WHERE file = 'Config.py' AND text LIKE '%\"\"\"%'")
print("\nTriple quote locations:")
for lineno, text in cur.fetchall():
    print(f"Line {lineno}: {text}")

# Show lines around the error (line 1003)
cur.execute("SELECT lineno, text FROM source_lines WHERE file = 'Config.py' AND lineno BETWEEN 990 AND 1010")
print("\nLines 990-1010:")
for lineno, text in cur.fetchall():
    print(f"{lineno:4}: {text}")

conn.close()
