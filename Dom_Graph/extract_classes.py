#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Script extracts class/method definitions from DB src table. NO VBStyle headers. print() x5. No Run() dispatch, no class, no Tuple3 returns. Hardcoded /Users/wws/ path. Not VBStyle compliant -- utility script.>][@todos<1. Add VBStyle identity headers. 2. Remove print() calls. 3. Wrap in a class with Run() dispatch and Tuple3 returns. 4. Remove hardcoded /Users/wws/ path.>]}
"""Extract all class definitions and their methods from DB."""
import sqlite3
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Find all class definitions
cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE 'class %' ORDER BY file, lineno")
classes = cur.fetchall()
print(f"Found {len(classes)} class definitions:")
for file, lineno, text in classes:
    print(f"  {file:30} line {lineno:4}: {text[:60]}")

# Find all method definitions
cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE '    def %' ORDER BY file, lineno")
methods = cur.fetchall()
print(f"\nFound {len(methods)} method definitions")

# Group methods by class
class_methods = {}
for file, lineno, text in methods:
    # Find which class this method belongs to (look backwards for 'class')
    cur.execute("SELECT lineno, text FROM src WHERE file = ? AND lineno < ? AND text LIKE 'class %' ORDER BY lineno DESC LIMIT 1", (file, lineno))
    class_row = cur.fetchone()
    if class_row:
        class_lineno, class_text = class_row
        class_name = class_text.split('(')[0].replace('class ', '').strip()
        key = f"{file}:{class_name}"
        if key not in class_methods:
            class_methods[key] = []
        class_methods[key].append((lineno, text))

print(f"\nMethods per class:")
for key, meths in sorted(class_methods.items()):
    print(f"  {key:40} {len(meths)} methods")

conn.close()
