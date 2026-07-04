#!/usr/bin/env python3
"""
Fix broken files after VBStyle cleanup.
Lessons learned:
1. print() inside string literals (dict values, comments) must NOT be replaced
2. pass inside a dict literal is a syntax error — need to remove the line entirely or restore original
3. pass after a bare expression (like a string) is invalid syntax
4. Empty lines from deleted decorators cause indentation errors — need to clean up

Strategy: Re-ingest the 4 broken files from their original state, then apply
a SMARTER print removal that only targets actual print() CALLS (line starts with
optional whitespace followed by 'print(').
"""
import sqlite3
import re
from pathlib import Path
import py_compile

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Step 1: Find all "pass  # VBStyle: no print" lines and fix them
# If the line is inside a dict (previous line ends with comma or {), restore as comment
# If the line is a standalone statement, keep pass but fix indentation
# If the line is after a string expression, replace with a comment

cur.execute("""
    SELECT file, lineno, text FROM src 
    WHERE text LIKE '%pass  # VBStyle: no print%' 
    AND file LIKE 'Dom_Graph_%'
    ORDER BY file, lineno
""")
broken_lines = cur.fetchall()
print(f"Broken pass lines to fix: {len(broken_lines)}")

for file, lineno, text in broken_lines:
    # Get the previous non-empty line for context
    cur.execute("SELECT text FROM src WHERE file = ? AND lineno < ? AND text != '' ORDER BY lineno DESC LIMIT 1", (file, lineno))
    prev_row = cur.fetchone()
    prev_text = prev_row[0].strip() if prev_row else ""
    
    # Get the next non-empty line
    cur.execute("SELECT text FROM src WHERE file = ? AND lineno > ? AND text != '' ORDER BY lineno LIMIT 1", (file, lineno))
    next_row = cur.fetchone()
    next_text = next_row[0].strip() if next_row else ""
    
    indent = text[:len(text) - len(text.lstrip())]
    
    # Case 1: Inside a dict literal (prev ends with { or comma, next starts with " or })
    if prev_text.endswith("{") or prev_text.endswith(",") or next_text.startswith("}") or next_text.startswith('"') or next_text.startswith("'"):
        # This was a string value in a dict — restore as a comment
        cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", (indent + "# VBStyle: string value preserved", file, lineno))
        continue
    
    # Case 2: After a bare string or expression (prev is a string assignment or expression)
    if prev_text.startswith('"') or prev_text.startswith("'") or prev_text.endswith(":"):
        # Replace with a comment
        cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", (indent + "# VBStyle: print removed", file, lineno))
        continue
    
    # Case 3: Inside an if/except block — keep pass but without the comment
    if prev_text.endswith(":") or next_text.startswith("return") or next_text.startswith("break") or next_text.startswith("continue"):
        cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", (indent + "pass", file, lineno))
        continue
    
    # Case 4: In a function body with more code after — replace with comment
    if next_text and not next_text.startswith("pass"):
        cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", (indent + "# VBStyle: print removed", file, lineno))
        continue
    
    # Case 5: Standalone pass at end of block — keep it
    cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", (indent + "pass", file, lineno))

conn.commit()
print("Fixed all broken pass lines")

# Step 2: Fix Dom_Graph_EngineV2.py line 410 — restore the dict entry
cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", 
             ('        "no_print": "No print() statements",', "Dom_Graph_EngineV2.py", 410))
# Also fix line 353 and 496
cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?",
             ('        "no_print_statements": "No print() in VBStyle code",', "Dom_Graph_EngineV2.py", 353))
cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?",
             ('        "Print statements": "Remove all print() calls, use return Tuple3",', "Dom_Graph_EngineV2.py", 496))

# Step 3: Fix Dom_Graph_Boot.py — indentation issue at line 512
# The issue is likely a comment line with wrong indentation after a deleted decorator
cur.execute("SELECT lineno, text FROM src WHERE file = 'Dom_Graph_Boot.py' AND lineno BETWEEN 508 AND 520 ORDER BY lineno")
for lineno, text in cur.fetchall():
    print(f"  Boot {lineno}: {text}")

# Step 4: Fix Dom_Graph_Gui.py — indentation at line 1173
cur.execute("SELECT lineno, text FROM src WHERE file = 'Dom_Graph_Gui.py' AND lineno BETWEEN 1168 AND 1180 ORDER BY lineno")
for lineno, text in cur.fetchall():
    print(f"  Gui {lineno}: {text}")

# Step 5: Fix Dom_Graph_Ingest.py — indentation at line 328
cur.execute("SELECT lineno, text FROM src WHERE file = 'Dom_Graph_Ingest.py' AND lineno BETWEEN 323 AND 335 ORDER BY lineno")
for lineno, text in cur.fetchall():
    print(f"  Ingest {lineno}: {text}")

conn.commit()

# Step 6: Write and test all 4 files
for fname in ["Dom_Graph_EngineV2.py", "Dom_Graph_Boot.py", "Dom_Graph_Gui.py", "Dom_Graph_Ingest.py"]:
    cur.execute("SELECT text FROM src WHERE file = ? AND text != '' ORDER BY lineno", (fname,))
    lines = [row[0] for row in cur.fetchall()]
    content = "\n".join(lines) + "\n"
    (BASE_DIR / fname).write_text(content, encoding="utf-8")
    
    try:
        py_compile.compile(str(BASE_DIR / fname), doraise=True)
        print(f"  OK    {fname}")
    except Exception as e:
        print(f"  FAIL  {fname}: {e}")
        # Show the error area
        if hasattr(e, 'lineno') and e.lineno:
            err_line = e.lineno
            cur.execute("SELECT lineno, text FROM src WHERE file = ? AND lineno BETWEEN ? AND ? ORDER BY lineno", (fname, err_line - 2, err_line + 2))
            for lineno, text in cur.fetchall():
                print(f"    {lineno}: {text}")

conn.close()
