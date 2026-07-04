#!/usr/bin/env python3
"""
Iteration 4: Clean fix approach.
The DB is corrupted for 4 files. Instead of patching line-by-line in DB,
we'll:
1. Read each broken file from disk
2. Fix the Python directly with string replacement
3. Re-ingest the fixed files into DB
4. Verify compilation
"""
import re
from pathlib import Path
import py_compile

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")

def fix_file(fname):
    path = BASE_DIR / fname
    content = path.read_text()
    lines = content.split("\n")
    fixed_lines = []
    skip_next_close = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Skip "pass  # VBStyle: no print" lines
        if stripped == "pass  # VBStyle: no print":
            # Check context: is this the only line in a block?
            prev_stripped = fixed_lines[-1].strip() if fixed_lines else ""
            indent = line[:len(line) - len(line.lstrip())]
            
            if prev_stripped.endswith(":"):
                # Only line in a block — keep pass
                fixed_lines.append(indent + "pass")
            else:
                # Not the only line — skip it (delete)
                continue
            continue
        
        # Skip "# VBStyle: print removed" lines  
        if stripped == "# VBStyle: print removed":
            prev_stripped = fixed_lines[-1].strip() if fixed_lines else ""
            indent = line[:len(line) - len(line.lstrip())]
            
            if prev_stripped.endswith(":"):
                fixed_lines.append(indent + "pass")
            else:
                continue
            continue
        
        # Skip "# VBStyle: string value preserved" lines
        if stripped == "# VBStyle: string value preserved":
            continue
        
        # Fix stray dict entries that got misplaced (from bad print replacement inside dicts)
        # These look like: "some_key": "some value",
        # but are NOT inside a dict context (prev line is not { or comma)
        if stripped.startswith('"') and stripped.endswith(",") and "VBStyle" not in stripped:
            prev_stripped = fixed_lines[-1].strip() if fixed_lines else ""
            # If prev line doesn't look like dict context, skip this stray line
            if not (prev_stripped.endswith("{") or prev_stripped.endswith(",") or prev_stripped.endswith(":")):
                # This is a stray dict entry — skip it
                continue
        
        # Fix dangling ) lines (from multi-line print calls that were partially removed)
        if stripped == ")" or stripped == "))":
            prev_stripped = fixed_lines[-1].strip() if fixed_lines else ""
            # If prev line is pass or a comment, this ) is dangling — skip it
            if prev_stripped == "pass" or prev_stripped.startswith("#"):
                continue
        
        fixed_lines.append(line)
    
    new_content = "\n".join(fixed_lines) + "\n"
    path.write_text(new_content, encoding="utf-8")
    
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"  OK    {fname} ({len(fixed_lines)} lines)")
        return True
    except py_compile.PyCompileError as e:
        print(f"  FAIL  {fname}: {e}")
        # Show error area
        err_line = 0
        m = re.search(r'line (\d+)', str(e))
        if m:
            err_line = int(m.group(1))
        if err_line:
            start = max(1, err_line - 3)
            end = min(err_line + 3, len(fixed_lines))
            for j in range(start - 1, end):
                print(f"    {j+1}: {fixed_lines[j]}")
        return False

print("=" * 60)
print("Fixing 4 broken files")
print("=" * 60)

results = []
for fname in ["Dom_Graph_EngineV2.py", "Dom_Graph_Boot.py", "Dom_Graph_Gui.py", "Dom_Graph_Ingest.py"]:
    result = fix_file(fname)
    results.append((fname, result))

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
for fname, ok in results:
    status = "OK" if ok else "FAIL"
    print(f"  {status:4}  {fname}")
