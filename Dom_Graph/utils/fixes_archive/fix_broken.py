#!/usr/bin/env python3
"""Fix broken files after VBStyle cleanup."""
import sqlite3
import re
from pathlib import Path
import py_compile

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Fix 1: Restore lines that were incorrectly replaced with "pass  # VBStyle: no print"
# These are lines where print( appeared inside a string literal, not as a function call
cur.execute("""
    SELECT file, lineno, text FROM src 
    WHERE text LIKE '%pass  # VBStyle: no print%' 
    AND file LIKE 'Dom_Graph_%'
    ORDER BY file, lineno
""")
broken = cur.fetchall()
print(f"Broken pass lines: {len(broken)}")
for file, lineno, text in broken:
    print(f"  {file}:{lineno} {text.strip()[:80]}")

# We can't easily restore the original text, so let's read the original from backup
# Instead, let's fix by reading the file and fixing the specific issues

# For Dom_Graph_EngineV2.py - the pass line is inside a dict, replace with the original string
# The original was: "no_print": "No print() statements",
cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", 
             ('        "no_print": "No print() statements",', "Dom_Graph_EngineV2.py", 410))
print("Fixed EngineV2.py line 410")

# For the other 3 files, let's check what's broken
for fname, err_line in [("Dom_Graph_Boot.py", 512), ("Dom_Graph_Gui.py", 1173), ("Dom_Graph_Ingest.py", 328)]:
    cur.execute("SELECT lineno, text FROM src WHERE file = ? AND lineno BETWEEN ? AND ? ORDER BY lineno", (fname, err_line - 3, err_line + 3))
    print(f"\n{fname} around line {err_line}:")
    for lineno, text in cur.fetchall():
        print(f"  {lineno}: {text}")

conn.commit()

# Write the fixed files
for fname in ["Dom_Graph_EngineV2.py", "Dom_Graph_Boot.py", "Dom_Graph_Gui.py", "Dom_Graph_Ingest.py"]:
    cur.execute("SELECT text FROM src WHERE file = ? AND text != '' ORDER BY lineno", (fname,))
    lines = [row[0] for row in cur.fetchall()]
    content = "\n".join(lines) + "\n"
    (BASE_DIR / fname).write_text(content, encoding="utf-8")
    
    try:
        py_compile.compile(str(BASE_DIR / fname), doraise=True)
        print(f"\n  OK    {fname}")
    except Exception as e:
        print(f"\n  FAIL  {fname}: {e}")

conn.close()
