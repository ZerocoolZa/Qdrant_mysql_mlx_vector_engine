#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<VBStyle violation audit script. VBStyle violations: no identity headers (no @GHOST/@VBSTYLE/@FILEID/@SUMMARY/@CLASS/@METHOD), uses print() extensively, no class, no Run() dispatch, no Tuple3, no self.state, hardcoded BASE_DIR and DB_PATH, script-style not class-based.>][@todos<Add full identity headers. Convert to class-based with Run() dispatch. Remove all print() calls. Make paths configurable via param.>]}
"""Audit VBStyle violations in the database."""
import sqlite3
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 1. Print statements
cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE '%print(%' AND file LIKE 'Dom_Graph_%' ORDER BY file, lineno")
prints = cur.fetchall()
print(f"Print statements: {len(prints)}")
for file, lineno, text in prints[:20]:
    print(f"  {file}:{lineno} {text.strip()[:80]}")
if len(prints) > 20:
    print(f"  ... and {len(prints)-20} more")

# 2. Decorators
cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE '%@property%' OR text LIKE '%@staticmethod%' OR text LIKE '%@classmethod%' OR text LIKE '%@abstractmethod%' ORDER BY file, lineno")
decorators = cur.fetchall()
print(f"\nDecorators: {len(decorators)}")
for file, lineno, text in decorators:
    print(f"  {file}:{lineno} {text.strip()}")

# 3. Classes without Run() method
cur.execute("SELECT DISTINCT class_name FROM class_registry WHERE class_name != 'Config'")
all_classes = [row[0] for row in cur.fetchall()]
classes_with_run = set()
for cls in all_classes:
    cur.execute("SELECT file FROM class_registry WHERE class_name = ? LIMIT 1", (cls,))
    file = cur.fetchone()[0]
    cur.execute("SELECT lineno FROM src WHERE file = ? AND text LIKE '    def Run(%' LIMIT 1", (file,))
    if cur.fetchone():
        classes_with_run.add(cls)
classes_without_run = set(all_classes) - classes_with_run
print(f"\nClasses without Run(): {len(classes_without_run)}")
for cls in sorted(classes_without_run):
    print(f"  {cls}")

# 4. Classes without __init__(self, mem=None, db=None, param=None)
cur.execute("""
    SELECT file, lineno, text FROM src 
    WHERE text LIKE '    def __init__(self,%' 
    AND text NOT LIKE '%mem=None%' 
    AND file LIKE 'Dom_Graph_%'
    ORDER BY file, lineno
""")
bad_init = cur.fetchall()
print(f"\n__init__ without VBStyle signature: {len(bad_init)}")
for file, lineno, text in bad_init:
    print(f"  {file}:{lineno} {text.strip()[:80]}")

# 5. self._ usage (forbidden)
cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE '%self._%' AND file LIKE 'Dom_Graph_%' ORDER BY file, lineno")
self_underscore = cur.fetchall()
print(f"\nself._ usage: {len(self_underscore)}")
for file, lineno, text in self_underscore[:10]:
    print(f"  {file}:{lineno} {text.strip()[:80]}")

# 6. Count total lines per file
cur.execute("SELECT file, COUNT(*) FROM src WHERE file LIKE 'Dom_Graph_%' GROUP BY file ORDER BY file")
print(f"\nFile line counts:")
for file, count in cur.fetchall():
    print(f"  {file:35} {count} lines")

conn.close()
