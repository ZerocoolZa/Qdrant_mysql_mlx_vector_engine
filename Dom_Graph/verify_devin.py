#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Verification script: compiles engine files checks VBStyle violations checks DB tables and tests. NOT VBStyle: no VBStyle headers no class no Run() dispatch no Tuple3 returns. Has 14 print() calls. Hardcoded path (/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph). Procedural script with no class structure.>][@todos<1. Add VBStyle headers. 2. Remove print() calls. 3. Remove hardcoded paths. 4. Wrap in class with Run() dispatch and Tuple3 returns.>]}
"""Verify all Devin-created engine files: compile, VBStyle, DB tables, tests."""
import py_compile
import os
import sqlite3
import glob
import sys

BASE = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph"
os.chdir(BASE)

# 1. Collect all engine files
patterns = [
    "*_engine.py", "*_analyzer.py", "*_validator.py", "*_forensics.py",
    "*_kernel.py", "*_resistance.py", "*_integrity.py", "*_loop.py",
    "*_pipeline.py", "*_twin.py", "graph_builder.py", "relationship_extractor.py",
    "continuous_loop.py",
]
files = set()
for p in patterns:
    files.update(glob.glob(p))
files = sorted(files)
# Exclude populate_twin.py (existing ingestion script, not an engine)
files = [f for f in files if f != "populate_twin.py"]

print(f"=== FILE COUNT: {len(files)} ===")

# 2. Compile check
ok = 0
fail = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        ok += 1
    except Exception as e:
        print(f"FAIL: {f}: {e}")
        fail += 1
print(f"=== COMPILE: {ok} OK, {fail} FAIL ===")

# 3. VBStyle violations
violations = {}
for f in files:
    with open(f) as fh:
        content = fh.read()
    v = []
    for i, line in enumerate(content.split("\n"), 1):
        stripped = line.lstrip()
        if stripped.startswith("print("):
            v.append(f"  L{i}: print()")
        if stripped.startswith("@staticmethod") or stripped.startswith("@property") or stripped.startswith("@classmethod"):
            v.append(f"  L{i}: decorator")
        if "\t" in line:
            v.append(f"  L{i}: tab")
    if v:
        violations[f] = v
if violations:
    print(f"=== VBSTYLE VIOLATIONS: {len(violations)} files ===")
    for f, vlist in violations.items():
        print(f"  {f}:")
        for v in vlist:
            print(v)
else:
    print("=== VBSTYLE: CLEAN ===")

# 4. DB tables
conn = sqlite3.connect("dom_graph_work.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f"=== DB TABLES ({len(tables)}) ===")
for t in ["files", "classes", "methods", "edges", "knowledge", "snapshots", "attempts", "observations"]:
    if t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        count = cur.fetchone()[0]
        print(f"  {t}: {count} rows")
    else:
        print(f"  {t}: MISSING!")

# 5. Views
cur.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
views = [r[0] for r in cur.fetchall()]
print(f"=== VIEWS: {views} ===")
conn.close()

print("=== DONE ===")
