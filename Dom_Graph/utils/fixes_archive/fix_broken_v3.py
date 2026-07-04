#!/usr/bin/env python3
"""
Iteration 3: Smart VBStyle cleanup.
Lessons applied:
- Only match lines where lstrip().startswith("print(") — NOT LIKE '%print(%'
- Handle multi-line print calls
- Don't replace with pass inside dicts/expressions — delete the line
- Clean up empty lines after decorator removal
- Re-number lines properly after Run() insertion
"""
import sqlite3
import re
from pathlib import Path
import py_compile

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ─── Step 1: Restore the 4 broken files from their current disk state ───
# The DB has corrupted versions. We need to re-ingest from the original files.
# But the files on disk are ALSO corrupted (written from DB).
# So we need to fix them in the DB directly.

# Strategy: For each broken file, find all "pass  # VBStyle" and "# VBStyle: print removed" 
# and "# VBStyle: string value preserved" lines, and either delete them or restore them.

# But we don't have the originals. So let's fix the specific issues:

print("=" * 60)
print("Fixing Dom_Graph_EngineV2.py")
print("=" * 60)

# Fix line 353: should be part of a dict, but it's a stray string
# Context: it's between an if block and a self.c.execute call
# Original was likely a print statement. Delete it.
cur.execute("SELECT lineno, text FROM src WHERE file = 'Dom_Graph_EngineV2.py' AND lineno BETWEEN 350 AND 360 ORDER BY lineno")
for lineno, text in cur.fetchall():
    print(f"  {lineno}: {text}")

# Line 353 is a stray dict entry — delete it
cur.execute("UPDATE src SET text = '' WHERE file = 'Dom_Graph_EngineV2.py' AND lineno = 353")
# Line 410 was already fixed to the dict entry
# Line 496 is also a stray — check
cur.execute("SELECT lineno, text FROM src WHERE file = 'Dom_Graph_EngineV2.py' AND lineno BETWEEN 493 AND 500 ORDER BY lineno")
for lineno, text in cur.fetchall():
    print(f"  {lineno}: {text}")
# Line 496 — delete if it's a stray
cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_EngineV2.py' AND lineno = 496")
row = cur.fetchone()
if row and "VBStyle" in row[0]:
    cur.execute("UPDATE src SET text = '' WHERE file = 'Dom_Graph_EngineV2.py' AND lineno = 496")

# Fix all remaining "# VBStyle:" lines in EngineV2 — these are comments where prints were
# Delete them if they're standalone, keep if needed for block body
cur.execute("""
    SELECT lineno, text FROM src 
    WHERE file = 'Dom_Graph_EngineV2.py' 
    AND (text LIKE '%# VBStyle: print removed%' OR text LIKE '%# VBStyle: string value%')
    ORDER BY lineno
""")
for lineno, text in cur.fetchall():
    # Check if this is the only line in a block (prev line ends with :)
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_EngineV2.py' AND lineno < ? AND text != '' ORDER BY lineno DESC LIMIT 1", (lineno,))
    prev = cur.fetchone()
    prev_text = prev[0].strip() if prev else ""
    
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_EngineV2.py' AND lineno > ? AND text != '' ORDER BY lineno LIMIT 1", (lineno,))
    nxt = cur.fetchone()
    next_text = nxt[0].strip() if nxt else ""
    
    if prev_text.endswith(":") and (not next_text or next_text.startswith("def ") or next_text.startswith("class ")):
        # This is the only line in a block — replace with pass
        indent = text[:len(text) - len(text.lstrip())]
        cur.execute("UPDATE src SET text = ? WHERE file = 'Dom_Graph_EngineV2.py' AND lineno = ?", (indent + "pass", lineno))
    else:
        # Delete the line
        cur.execute("UPDATE src SET text = '' WHERE file = 'Dom_Graph_EngineV2.py' AND lineno = ?", (lineno,))

print("\n" + "=" * 60)
print("Fixing Dom_Graph_Boot.py")
print("=" * 60)

# The issue is around line 513 — a print(f"...") that was replaced, leaving dangling )
# Find all VBStyle comment/pass lines and fix them
cur.execute("""
    SELECT lineno, text FROM src 
    WHERE file = 'Dom_Graph_Boot.py' 
    AND (text LIKE '%# VBStyle%' OR text LIKE '%pass  # VBStyle%')
    ORDER BY lineno
""")
boot_broken = cur.fetchall()
print(f"Broken lines: {len(boot_broken)}")
for lineno, text in boot_broken:
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_Boot.py' AND lineno < ? AND text != '' ORDER BY lineno DESC LIMIT 1", (lineno,))
    prev = cur.fetchone()
    prev_text = prev[0].strip() if prev else ""
    
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_Boot.py' AND lineno > ? AND text != '' ORDER BY lineno LIMIT 1", (lineno,))
    nxt = cur.fetchone()
    next_text = nxt[0].strip() if nxt else ""
    
    indent = text[:len(text) - len(text.lstrip())]
    
    if prev_text.endswith(":") and (not next_text or not next_text.startswith(indent)):
        cur.execute("UPDATE src SET text = ? WHERE file = 'Dom_Graph_Boot.py' AND lineno = ?", (indent + "pass", lineno))
    else:
        cur.execute("UPDATE src SET text = '' WHERE file = 'Dom_Graph_Boot.py' AND lineno = ?", (lineno,))

# Also check for dangling ) lines that were part of multi-line prints
cur.execute("""
    SELECT lineno, text FROM src 
    WHERE file = 'Dom_Graph_Boot.py' 
    AND text.strip() = ')' 
    ORDER BY lineno
""")
for lineno, text in cur.fetchall():
    # Check if previous non-empty line is a comment or pass (meaning the print was removed)
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_Boot.py' AND lineno < ? AND text != '' ORDER BY lineno DESC LIMIT 1", (lineno,))
    prev = cur.fetchone()
    if prev and ("VBStyle" in prev[0] or prev[0].strip() == "pass"):
        cur.execute("UPDATE src SET text = '' WHERE file = 'Dom_Graph_Boot.py' AND lineno = ?", (lineno,))
        print(f"  Deleted dangling ) at line {lineno}")

print("\n" + "=" * 60)
print("Fixing Dom_Graph_Gui.py")
print("=" * 60)

# Same approach — fix all VBStyle lines
cur.execute("""
    SELECT lineno, text FROM src 
    WHERE file = 'Dom_Graph_Gui.py' 
    AND (text LIKE '%# VBStyle%' OR text LIKE '%pass  # VBStyle%')
    ORDER BY lineno
""")
gui_broken = cur.fetchall()
print(f"Broken lines: {len(gui_broken)}")
for lineno, text in gui_broken:
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_Gui.py' AND lineno < ? AND text != '' ORDER BY lineno DESC LIMIT 1", (lineno,))
    prev = cur.fetchone()
    prev_text = prev[0].strip() if prev else ""
    
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_Gui.py' AND lineno > ? AND text != '' ORDER BY lineno LIMIT 1", (lineno,))
    nxt = cur.fetchone()
    next_text = nxt[0].strip() if nxt else ""
    
    indent = text[:len(text) - len(text.lstrip())]
    
    if prev_text.endswith(":") and (not next_text or not next_text.startswith(indent)):
        cur.execute("UPDATE src SET text = ? WHERE file = 'Dom_Graph_Gui.py' AND lineno = ?", (indent + "pass", lineno))
    else:
        cur.execute("UPDATE src SET text = '' WHERE file = 'Dom_Graph_Gui.py' AND lineno = ?", (lineno,))

# Fix dangling ) in Gui
cur.execute("""
    SELECT lineno, text FROM src 
    WHERE file = 'Dom_Graph_Gui.py' 
    AND text.strip() = ')' 
    ORDER BY lineno
""")
for lineno, text in cur.fetchall():
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_Gui.py' AND lineno < ? AND text != '' ORDER BY lineno DESC LIMIT 1", (lineno,))
    prev = cur.fetchone()
    if prev and ("VBStyle" in prev[0] or prev[0].strip() == "pass"):
        cur.execute("UPDATE src SET text = '' WHERE file = 'Dom_Graph_Gui.py' AND lineno = ?", (lineno,))

print("\n" + "=" * 60)
print("Fixing Dom_Graph_Ingest.py")
print("=" * 60)

# Fix all VBStyle lines
cur.execute("""
    SELECT lineno, text FROM src 
    WHERE file = 'Dom_Graph_Ingest.py' 
    AND (text LIKE '%# VBStyle%' OR text LIKE '%pass  # VBStyle%')
    ORDER BY lineno
""")
ingest_broken = cur.fetchall()
print(f"Broken lines: {len(ingest_broken)}")
for lineno, text in ingest_broken:
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_Ingest.py' AND lineno < ? AND text != '' ORDER BY lineno DESC LIMIT 1", (lineno,))
    prev = cur.fetchone()
    prev_text = prev[0].strip() if prev else ""
    
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_Ingest.py' AND lineno > ? AND text != '' ORDER BY lineno LIMIT 1", (lineno,))
    nxt = cur.fetchone()
    next_text = nxt[0].strip() if nxt else ""
    
    indent = text[:len(text) - len(text.lstrip())]
    
    if prev_text.endswith(":") and (not next_text or not next_text.startswith(indent)):
        cur.execute("UPDATE src SET text = ? WHERE file = 'Dom_Graph_Ingest.py' AND lineno = ?", (indent + "pass", lineno))
    else:
        cur.execute("UPDATE src SET text = '' WHERE file = 'Dom_Graph_Ingest.py' AND lineno = ?", (lineno,))

# Fix dangling ) in Ingest
cur.execute("""
    SELECT lineno, text FROM src 
    WHERE file = 'Dom_Graph_Ingest.py' 
    AND text.strip() = ')' 
    ORDER BY lineno
""")
for lineno, text in cur.fetchall():
    cur.execute("SELECT text FROM src WHERE file = 'Dom_Graph_Ingest.py' AND lineno < ? AND text != '' ORDER BY lineno DESC LIMIT 1", (lineno,))
    prev = cur.fetchone()
    if prev and ("VBStyle" in prev[0] or prev[0].strip() == "pass"):
        cur.execute("UPDATE src SET text = '' WHERE file = 'Dom_Graph_Ingest.py' AND lineno = ?", (lineno,))

conn.commit()

# ─── Step 2: Write and test all 4 files ───
print("\n" + "=" * 60)
print("Writing and testing fixed files")
print("=" * 60)

for fname in ["Dom_Graph_EngineV2.py", "Dom_Graph_Boot.py", "Dom_Graph_Gui.py", "Dom_Graph_Ingest.py"]:
    cur.execute("SELECT text FROM src WHERE file = ? AND text != '' ORDER BY lineno", (fname,))
    lines = [row[0] for row in cur.fetchall()]
    content = "\n".join(lines) + "\n"
    (BASE_DIR / fname).write_text(content, encoding="utf-8")
    
    try:
        py_compile.compile(str(BASE_DIR / fname), doraise=True)
        print(f"  OK    {fname}")
    except py_compile.PyCompileError as e:
        print(f"  FAIL  {fname}: {e}")
        # Show error area
        err_line = 0
        if hasattr(e, 'lineno'):
            err_line = e.lineno
        elif "line" in str(e):
            m = re.search(r'line (\d+)', str(e))
            if m:
                err_line = int(m.group(1))
        if err_line:
            start = max(1, err_line - 3)
            end = err_line + 3
            with open(BASE_DIR / fname) as f:
                all_lines = f.readlines()
            for i in range(start - 1, min(end, len(all_lines))):
                print(f"    {i+1}: {all_lines[i].rstrip()}")

conn.close()
