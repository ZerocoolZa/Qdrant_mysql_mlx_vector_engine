#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<One-shot rename script: renames files and classes in DB to Dom_Graph convention. NOT VBStyle: no VBStyle headers no class no Run() dispatch no Tuple3 returns. Has 44 print() calls. Hardcoded path (/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph). Procedural script with no class structure.>][@todos<1. Add VBStyle headers. 2. Remove print() calls. 3. Remove hardcoded paths. 4. Wrap in class with Run() dispatch and Tuple3 returns.>]}
"""
Rename all files and classes in the database to Dom_Graph convention.
All work done in dom_graph_work.db, then files written from DB in one pass.
"""
import sqlite3
from pathlib import Path
import py_compile
import os

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

# ─── Rename mapping: old_file → new_file ───
FILE_RENAMES = {
    "Config.py":              "Config.py",              # stays
    "DbArchitectureGui.py":   "Dom_Graph_Gui.py",
    "DepGraph.py":            "Dom_Graph_Dep.py",
    "EfiAgentGraph.py":       "Dom_Graph_Agent.py",
    "EfiBootGraph.py":        "Dom_Graph_Boot.py",
    "EfiCodeGraph.py":        "Dom_Graph_Code.py",
    "EfiGraphViewer.py":      "Dom_Graph_Viewer.py",
    "ErrorGraph.py":          "Dom_Graph_Error.py",
    "GapGraph.py":            "Dom_Graph_Gap.py",
    "GraphEngine.py":         "Dom_Graph_Engine.py",
    "GraphEngineV2.py":       "Dom_Graph_EngineV2.py",
    "IngestGraphFromMysql.py":"Dom_Graph_Ingest.py",
    "LifecycleGraph.py":      "Dom_Graph_Lifecycle.py",
    "OrchGraph.py":           "Dom_Graph_Orch.py",
    "PlanGraph.py":           "Dom_Graph_Plan.py",
    "RuntimeTwinPopulate.py": "Dom_Graph_Runtime.py",
    "SpecFlow.py":            "Dom_Graph_Flow.py",
    "SpecGraph.py":           "Dom_Graph_Spec.py",
    # Helper scripts — keep as-is or remove
    "build_registry.py":      "build_registry.py",
    "domain_loader.py":       "domain_loader.py",
    "extract_classes.py":     "extract_classes.py",
    "ingest_to_db.py":        "ingest_to_db.py",
    "query_db.py":            "query_db.py",
    "refactor_family.py":     "refactor_family.py",
    "test_domain.py":         "test_domain.py",
    "test_everything.py":     "test_everything.py",
    "verify_db.py":           "verify_db.py",
    "work_from_db.py":        "work_from_db.py",
}

# ─── Class renames: old_name → new_name ───
CLASS_RENAMES = {
    "Config":                 "Config",                # stays
    "DBArchitectureGUI":      "DomGraphGui",
    "DepGraphViewer":         "DomGraphDep",
    "AgentNode":              "DomGraphAgentNode",
    "Edge":                   "DomGraphEdge",
    "PredictionLink":         "DomGraphPredictionLink",
    "WorldModel":             "DomGraphWorldModel",
    "Goal":                   "DomGraphGoal",
    "GoalSystem":             "DomGraphGoalSystem",
    "EmotionalState":         "DomGraphEmotionalState",
    "Consolidation":          "DomGraphConsolidation",
    "AdversarialAgent":       "DomGraphAdversarialAgent",
    "MysqlKnowledgeConnector":"DomGraphMysqlConnector",
    "AgentGraph":             "DomGraphAgent",
    "ExecutionGraph":         "DomGraphExecution",
    "Node":                   "DomGraphNode",
    "TypedGraph":             "DomGraphTyped",
    "GraphViewer":            "DomGraphViewer",
    "ErrorGraphViewer":       "DomGraphError",
    "GapGraphViewer":         "DomGraphGap",
    "CuriosityController":    "DomGraphCuriosity",
    "GraphEngine":            "DomGraphEngine",
    "ReportMaker":            "DomGraphReport",
    "ConstraintChecker":      "DomGraphConstraint",
    "SolutionSuggester":      "DomGraphSolution",
    "MistakeRecorder":        "DomGraphMistake",
    "GUIDisplayer":           "DomGraphGuiDisplay",
    "LifecycleGraphViewer":   "DomGraphLifecycle",
    "OrchGraphViewer":        "DomGraphOrch",
    "PlanNode":               "DomGraphPlanNode",
    "PlanGraphViewer":        "DomGraphPlan",
    "SpecFlowAnalyzer":       "DomGraphFlow",
    "SpecGraphViewer":        "DomGraphSpec",
}

# ─── File-internal renames (import references, string literals) ───
# These are module names that appear in import statements
MODULE_RENAMES = {
    "DbArchitectureGui":   "Dom_Graph_Gui",
    "DepGraph":            "Dom_Graph_Dep",
    "EfiAgentGraph":       "Dom_Graph_Agent",
    "EfiBootGraph":        "Dom_Graph_Boot",
    "EfiCodeGraph":        "Dom_Graph_Code",
    "EfiGraphViewer":      "Dom_Graph_Viewer",
    "ErrorGraph":          "Dom_Graph_Error",
    "GapGraph":            "Dom_Graph_Gap",
    "GraphEngine":         "Dom_Graph_Engine",
    "IngestGraphFromMysql":"Dom_Graph_Ingest",
    "LifecycleGraph":      "Dom_Graph_Lifecycle",
    "OrchGraph":           "Dom_Graph_Orch",
    "PlanGraph":           "Dom_Graph_Plan",
    "RuntimeTwinPopulate": "Dom_Graph_Runtime",
    "SpecFlow":            "Dom_Graph_Flow",
    "SpecGraph":           "Dom_Graph_Spec",
}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 60)
print("STEP 1: Rename files in src table")
print("=" * 60)
for old_file, new_file in FILE_RENAMES.items():
    if old_file != new_file:
        cur.execute("UPDATE src SET file = ? WHERE file = ?", (new_file, old_file))
        affected = cur.rowcount
        print(f"  {old_file:30} → {new_file:30} ({affected} lines)")
    else:
        print(f"  {old_file:30} (no change)")

print("\n" + "=" * 60)
print("STEP 2: Rename class definitions in src table")
print("=" * 60)
for old_name, new_name in CLASS_RENAMES.items():
    if old_name != new_name:
        # Rename class definition line: "class OldName(" → "class NewName("
        cur.execute("UPDATE src SET text = REPLACE(text, ?, ?) WHERE text LIKE ?", (f"class {old_name}(", f"class {new_name}(", f"class {old_name}(%"))
        affected = cur.rowcount
        if affected > 0:
            print(f"  class {old_name:30} → {new_name:30} ({affected} lines)")

print("\n" + "=" * 60)
print("STEP 3: Rename class references in src table (all files)")
print("=" * 60)
for old_name, new_name in CLASS_RENAMES.items():
    if old_name != new_name:
        # Replace all references to old class name in all source lines
        # Be careful: only replace whole-word matches
        cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE ?", (f"%{old_name}%",))
        rows = cur.fetchall()
        count = 0
        for file, lineno, text in rows:
            new_text = text
            # Replace whole-word occurrences: OldName not part of a longer identifier
            # Use simple boundary detection
            import re
            new_text = re.sub(r'\b' + re.escape(old_name) + r'\b', new_name, new_text)
            if new_text != text:
                cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", (new_text, file, lineno))
                count += 1
        if count > 0:
            print(f"  {old_name:30} → {new_name:30} ({count} references patched)")

print("\n" + "=" * 60)
print("STEP 4: Rename module imports in src table")
print("=" * 60)
for old_mod, new_mod in MODULE_RENAMES.items():
    if old_mod != new_mod:
        # Replace import statements: "from OldMod import" → "from NewMod import"
        # and "import OldMod" → "import NewMod"
        cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE ? OR text LIKE ?", (f"%from {old_mod} import%", f"%import {old_mod}%"))
        rows = cur.fetchall()
        count = 0
        for file, lineno, text in rows:
            new_text = text.replace(f"from {old_mod} import", f"from {new_mod} import")
            new_text = new_text.replace(f"import {old_mod}", f"import {new_mod}")
            if new_text != text:
                cur.execute("UPDATE src SET text = ? WHERE file = ? AND lineno = ?", (new_text, file, lineno))
                count += 1
        if count > 0:
            print(f"  module {old_mod:25} → {new_mod:25} ({count} imports patched)")

print("\n" + "=" * 60)
print("STEP 5: Update class_registry table")
print("=" * 60)
for old_name, new_name in CLASS_RENAMES.items():
    if old_name != new_name:
        cur.execute("UPDATE class_registry SET class_name = ?, class_text = REPLACE(class_text, ?, ?) WHERE class_name = ?", 
                     (new_name, f"class {old_name}", f"class {new_name}", old_name))
        affected = cur.rowcount
        if affected > 0:
            print(f"  {old_name:30} → {new_name:30} ({affected} rows)")

# Update file column in class_registry
for old_file, new_file in FILE_RENAMES.items():
    if old_file != new_file:
        cur.execute("UPDATE class_registry SET file = ? WHERE file = ?", (new_file, old_file))
        affected = cur.rowcount
        if affected > 0:
            print(f"  file {old_file:30} → {new_file:30} ({affected} rows)")

print("\n" + "=" * 60)
print("STEP 6: Update FILE_REGISTRY in config_constants")
print("=" * 60)
# Get current FILE_REGISTRY value
cur.execute("SELECT value FROM config_constants WHERE name = 'FILE_REGISTRY'")
row = cur.fetchone()
if row:
    import ast
    registry = ast.literal_eval(row[0])
    new_registry = {}
    for key, val in registry.items():
        new_key = FILE_RENAMES.get(key, key)
        if isinstance(val, dict):
            new_val = {}
            for k2, v2 in val.items():
                # Update class names in values
                new_k2 = CLASS_RENAMES.get(k2, k2)
                if isinstance(v2, str):
                    new_v2 = v2
                    for old_n, new_n in CLASS_RENAMES.items():
                        new_v2 = new_v2.replace(old_n, new_n)
                    for old_f, new_f in FILE_RENAMES.items():
                        new_v2 = new_v2.replace(old_f, new_f)
                else:
                    new_v2 = v2
                new_val[new_k2] = new_v2
        else:
            new_val = val
            if isinstance(val, str):
                for old_n, new_n in CLASS_RENAMES.items():
                    new_val = new_val.replace(old_n, new_n)
                for old_f, new_f in FILE_RENAMES.items():
                    new_val = new_val.replace(old_f, new_f)
        new_registry[new_key] = new_val
    cur.execute("UPDATE config_constants SET value = ? WHERE name = 'FILE_REGISTRY'", (str(new_registry),))
    print(f"  FILE_REGISTRY updated: {len(new_registry)} entries")

# Update GRAPH_PIPELINE in config_constants
cur.execute("SELECT value FROM config_constants WHERE name = 'GRAPH_PIPELINE'")
row = cur.fetchone()
if row:
    pipeline = ast.literal_eval(row[0])
    new_pipeline = []
    for entry in pipeline:
        new_entry = list(entry)
        if isinstance(new_entry[0], str):
            new_entry[0] = CLASS_RENAMES.get(new_entry[0], new_entry[0])
        if len(new_entry) > 1 and isinstance(new_entry[1], str):
            for old_f, new_f in FILE_RENAMES.items():
                new_entry[1] = new_entry[1].replace(old_f, new_f)
        new_pipeline.append(tuple(new_entry))
    cur.execute("UPDATE config_constants SET value = ? WHERE name = 'GRAPH_PIPELINE'", (str(new_pipeline),))
    print(f"  GRAPH_PIPELINE updated: {len(new_pipeline)} stages")

conn.commit()
print("\n" + "=" * 60)
print("STEP 7: Write all files from DB to disk")
print("=" * 60)

# Get all unique files from src table
cur.execute("SELECT DISTINCT file FROM src ORDER BY file")
db_files = [row[0] for row in cur.fetchall()]

for fname in db_files:
    cur.execute("SELECT text FROM src WHERE file = ? ORDER BY lineno", (fname,))
    lines = [row[0] for row in cur.fetchall()]
    content = "\n".join(lines) + "\n"
    out_path = BASE_DIR / fname
    out_path.write_text(content, encoding="utf-8")
    print(f"  Written: {fname:35} ({len(lines)} lines)")

print("\n" + "=" * 60)
print("STEP 8: Delete old files that were renamed")
print("=" * 60)
for old_file, new_file in FILE_RENAMES.items():
    if old_file != new_file:
        old_path = BASE_DIR / old_file
        if old_path.exists():
            old_path.unlink()
            print(f"  Deleted: {old_file}")

print("\n" + "=" * 60)
print("STEP 9: Verify all files compile")
print("=" * 60)
all_ok = True
for fname in db_files:
    if not fname.endswith(".py"):
        continue
    path = BASE_DIR / fname
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"  OK    {fname}")
    except Exception as e:
        print(f"  FAIL  {fname}: {e}")
        all_ok = False

print("\n" + "=" * 60)
if all_ok:
    print("ALL FILES COMPILE ✓")
else:
    print("SOME FILES FAILED ✗")

print(f"\nRenamed {sum(1 for o,n in FILE_RENAMES.items() if o!=n)} files, {sum(1 for o,n in CLASS_RENAMES.items() if o!=n)} classes")
conn.close()
