#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<One-shot cleanup script: renames classes removes print() removes decorators adds Run() dispatch writes files from DB. NOT VBStyle: no VBStyle headers no class no Run() dispatch no Tuple3 returns. Has 34 print() calls. Hardcoded path (/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph). Ironic: script enforces VBStyle on other files but is not VBStyle itself.>][@todos<1. Add VBStyle headers. 2. Remove print() calls. 3. Remove hardcoded paths. 4. Wrap in class with Run() dispatch and Tuple3 returns.>]}
"""
VBStyle cleanup in database.
1. Rename classes to simple names (Node, Edge, etc.)
2. Remove print() statements
3. Remove @staticmethod/@property/@classmethod decorators
4. Add Run() dispatch to classes that don't have it
5. Write all files from DB
"""
import sqlite3
import re
from pathlib import Path
import py_compile

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

# Class renames: DomGraph* → simple name
CLASS_RENAMES = {
    "DomGraphAgentNode": "AgentNode",
    "DomGraphEdge": "Edge",
    "DomGraphPredictionLink": "PredictionLink",
    "DomGraphWorldModel": "WorldModel",
    "DomGraphGoal": "Goal",
    "DomGraphGoalSystem": "GoalSystem",
    "DomGraphEmotionalState": "EmotionalState",
    "DomGraphConsolidation": "Consolidation",
    "DomGraphAdversarialAgent": "AdversarialAgent",
    "DomGraphMysqlConnector": "MysqlConnector",
    "DomGraphAgent": "AgentGraph",
    "DomGraphExecution": "ExecutionGraph",
    "DomGraphNode": "Node",
    "DomGraphTyped": "TypedGraph",
    "DomGraphViewer": "GraphViewer",
    "DomGraphError": "ErrorGraph",
    "DomGraphGap": "GapGraph",
    "DomGraphCuriosity": "CuriosityController",
    "DomGraphEngine": "GraphEngine",
    "DomGraphReport": "ReportMaker",
    "DomGraphConstraint": "ConstraintChecker",
    "DomGraphSolution": "SolutionSuggester",
    "DomGraphMistake": "MistakeRecorder",
    "DomGraphGuiDisplay": "Guidisplayer",
    "DomGraphLifecycle": "LifecycleGraph",
    "DomGraphOrch": "OrchGraph",
    "DomGraphPlanNode": "PlanNode",
    "DomGraphPlan": "PlanGraph",
    "DomGraphFlow": "SpecFlow",
    "DomGraphSpec": "SpecGraph",
    "DomGraphGui": "DbArchitectureGui",
}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 60)
print("STEP 1: Rename classes back to simple names")
print("=" * 60)
for old_name, new_name in CLASS_RENAMES.items():
    if old_name != new_name:
        # Rename in src table - class definition
        cur.execute("UPDATE src SET text = REPLACE(text, ?, ?) WHERE text LIKE ?", 
                     (f"class {old_name}(", f"class {new_name}(", f"class {old_name}(%"))
        def_affected = cur.rowcount
        
        # Rename all references in src table
        cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE ?", (f"%{old_name}%",))
        rows = cur.fetchall()
        ref_count = 0
        for file, lineno, text in rows:
            new_text = re.sub(r'\b' + re.escape(old_name) + r'\b', new_name, text)
            if new_text != text:
                cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", (new_text, file, lineno))
                ref_count += 1
        
        if def_affected > 0 or ref_count > 0:
            print(f"  {old_name:30} → {new_name:30} (def:{def_affected} refs:{ref_count})")

        # Update class_registry
        cur.execute("UPDATE class_registry SET class_name = ?, class_text = REPLACE(class_text, ?, ?) WHERE class_name = ?",
                     (new_name, f"class {old_name}", f"class {new_name}", old_name))

print("\n" + "=" * 60)
print("STEP 2: Remove print() statements")
print("=" * 60)

# Get all print lines
cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE '%print(%' AND file LIKE 'Dom_Graph_%' ORDER BY file, lineno")
print_lines = cur.fetchall()
print_count = 0
for file, lineno, text in print_lines:
    stripped = text.strip()
    # Skip lines that are inside strings (comments about print)
    if stripped.startswith("#"):
        continue
    # Skip lines that mention "print" in string literals but aren't print calls
    if "print(" not in stripped:
        continue
    # Skip lines in string content (like "no print()")
    if '"print(' in stripped or "'print(" in stripped:
        continue
    # Replace print() with pass or remove the line
    # If it's a standalone print line, replace with pass (keeping indentation)
    indent = text[:len(text) - len(text.lstrip())]
    cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", (indent + "pass  # VBStyle: no print", file, lineno))
    print_count += 1

print(f"  Removed {print_count} print() statements")

print("\n" + "=" * 60)
print("STEP 3: Remove @staticmethod/@property/@classmethod decorators")
print("=" * 60)

# Get decorator lines (only actual decorator lines, not string content)
cur.execute("""
    SELECT file, lineno, text FROM src 
    WHERE (text LIKE '%@staticmethod%' OR text LIKE '%@property%' OR text LIKE '%@classmethod%' OR text LIKE '%@abstractmethod%')
    AND text LIKE '@%'
    ORDER BY file, lineno
""")
decorator_lines = cur.fetchall()
dec_count = 0
for file, lineno, text in decorator_lines:
    # Delete the decorator line by replacing with empty string
    cur.execute("UPDATE src SET text = '' WHERE file = ? AND lineno = ?", (file, lineno))
    dec_count += 1

print(f"  Removed {dec_count} decorator lines")

print("\n" + "=" * 60)
print("STEP 4: Add Run() dispatch to classes without it")
print("=" * 60)

# Find classes without Run() method
cur.execute("SELECT DISTINCT class_name, file FROM class_registry WHERE class_name != 'Config'")
all_classes = cur.fetchall()
classes_without_run = []
for class_name, file in all_classes:
    cur.execute("SELECT lineno FROM src WHERE file = ? AND text LIKE '    def Run(%' LIMIT 1", (file,))
    if not cur.fetchone():
        classes_without_run.append((class_name, file))

print(f"  Classes without Run(): {len(classes_without_run)}")
for class_name, file in classes_without_run:
    print(f"    {class_name:30} in {file}")

# For each class without Run(), add a basic Run() dispatch after __init__
for class_name, file in classes_without_run:
    # Find the __init__ method end (next def at same indent level)
    cur.execute("SELECT lineno FROM src WHERE file = ? AND text LIKE 'class %' ORDER BY lineno", (file,))
    class_lines = [row[0] for row in cur.fetchall()]
    
    # Find this class's line
    cur.execute("SELECT lineno FROM src WHERE file = ? AND text LIKE ? ORDER BY lineno", (file, f"class {class_name}%"))
    class_start = cur.fetchone()
    if not class_start:
        continue
    class_start = class_start[0]
    
    # Find the next class after this one
    next_class = None
    for cl in class_lines:
        if cl > class_start:
            next_class = cl
            break
    
    # Find the last method before next class (or end of file)
    if next_class:
        cur.execute("SELECT MAX(lineno) FROM src WHERE file = ? AND lineno < ? AND text LIKE '    def %'", (file, next_class))
    else:
        cur.execute("SELECT MAX(lineno) FROM src WHERE file = ? AND text LIKE '    def %'", (file,))
    
    last_method_line = cur.fetchone()[0]
    if not last_method_line:
        continue
    
    # Find the end of the last method (next line that's not indented more than 4 spaces)
    cur.execute("SELECT lineno, text FROM src WHERE file = ? AND lineno > ? ORDER BY lineno", (file, last_method_line))
    insert_after = last_method_line
    for lineno, text in cur.fetchall():
        if next_class and lineno >= next_class:
            break
        if text.strip() == "":
            insert_after = lineno
            continue
        if not text.startswith("        "):
            break
        insert_after = lineno
    
    # Insert Run() method after insert_after
    # Shift all lines after insert_after by 5
    cur.execute("SELECT MAX(lineno) FROM src WHERE file = ?", (file,))
    max_lineno = cur.fetchone()[0]
    
    run_method_lines = [
        (insert_after + 1, "    def Run(self, command, params=None):"),
        (insert_after + 2, "        dispatch = {"),
        (insert_after + 3, "            'read_state': self.read_state,"),
        (insert_after + 4, "            'set_config': self.set_config,"),
        (insert_after + 5, "        }"),
        (insert_after + 6, "        handler = dispatch.get(command)"),
        (insert_after + 7, "        if handler:"),
        (insert_after + 8, "            return handler(params or {})"),
        (insert_after + 9, "        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))"),
    ]
    
    # Shift existing lines
    shift = len(run_method_lines)
    cur.execute("SELECT lineno, text FROM src WHERE file = ? AND lineno > ? ORDER BY lineno DESC", (file, insert_after))
    rows = cur.fetchall()
    for lineno, text in rows:
        cur.execute("UPDATE src SET lineno = ? WHERE file = ? AND lineno = ?", (lineno + shift, file, lineno))
    
    # Insert Run() method lines
    for new_lineno, new_text in run_method_lines:
        cur.execute("INSERT INTO src (file, lineno, text) VALUES (?, ?, ?)", (file, new_lineno, new_text))
    
    print(f"  Added Run() to {class_name} in {file} after line {insert_after}")

conn.commit()

print("\n" + "=" * 60)
print("STEP 5: Write all files from DB")
print("=" * 60)

cur.execute("SELECT DISTINCT file FROM src WHERE file LIKE 'Dom_Graph_%' OR file = 'Config.py' ORDER BY file")
db_files = [row[0] for row in cur.fetchall()]

for fname in db_files:
    cur.execute("SELECT text FROM src WHERE file = ? AND text != '' ORDER BY lineno", (fname,))
    lines = [row[0] for row in cur.fetchall()]
    content = "\n".join(lines) + "\n"
    out_path = BASE_DIR / fname
    out_path.write_text(content, encoding="utf-8")
    print(f"  Written: {fname:35} ({len(lines)} lines)")

print("\n" + "=" * 60)
print("STEP 6: Verify compilation")
print("=" * 60)
all_ok = True
for fname in db_files:
    if not fname.endswith(".py"):
        continue
    try:
        py_compile.compile(str(BASE_DIR / fname), doraise=True)
        print(f"  OK    {fname}")
    except Exception as e:
        print(f"  FAIL  {fname}: {e}")
        all_ok = False

print(f"\n{'ALL FILES COMPILE ✓' if all_ok else 'SOME FILES FAILED ✗'}")
conn.close()
