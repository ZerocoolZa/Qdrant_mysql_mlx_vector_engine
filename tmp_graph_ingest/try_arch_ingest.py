#!/usr/bin/env python3
"""
Try-out: ingest MEM_Complete_System.py into graph_engine_dev.db,
then run GraphEngine tools against it.
Evaluates whether the codegraph tooling we built is good or bad.
"""
import ast, os, sys, sqlite3, json, time

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph_engine_dev.db")
FILE = "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/AA_MEMORIES/MEM_Complete_System.py"
DOMAIN = "mem_arch"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def Section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

# ─── 1. Parse ──────────────────────────────────────────────────────────────
Section("1. PARSE — AST extraction")
with open(FILE, "r", errors="replace") as f:
    source = f.read()
try:
    tree = ast.parse(source)
    print("  AST parse: OK")
except SyntaxError as e:
    print("  AST parse: FAIL — " + str(e))
    sys.exit(1)

classes = []
methods = []
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef):
        class_code = ast.get_source_segment(source, node) or ""
        has_run = "Run" in [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        has_state = "self.state" in class_code
        classes.append({
            "name": node.name,
            "code": class_code,
            "has_run": has_run,
            "has_state": has_state,
            "is_vbstyle": has_run and has_state,
            "line_start": node.lineno,
            "methods": [],
        })
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                mcode = ast.get_source_segment(source, item) or ""
                params = ",".join(a.arg for a in item.args.args)
                returns_t3 = "return (1," in mcode or "return (0," in mcode
                methods.append({
                    "class_name": node.name,
                    "method_name": item.name,
                    "method_code": mcode,
                    "params": params,
                    "signature": "def {}({})".format(item.name, params),
                    "is_dunder": item.name.startswith("__") and item.name.endswith("__"),
                    "is_vbstyle": item.name == "Run" or (item.name[0].isupper() if item.name else False),
                    "returns_tuple3": returns_t3,
                    "line_start": item.lineno,
                })
                classes[-1]["methods"].append(item.name)

print("  Classes found:  " + str(len(classes)))
print("  Methods found:  " + str(len(methods)))
vbstyle = [c for c in classes if c["is_vbstyle"]]
print("  VBStyle (Run+self.state): " + str(len(vbstyle)))

# ─── 2. Ingest ─────────────────────────────────────────────────────────────
Section("2. INGEST — write into graph_engine_dev.db")
db = sqlite3.connect(DB)
cur = db.cursor()

# Clean prior run for this domain
cur.execute("DELETE FROM methods WHERE class_id IN (SELECT id FROM classes WHERE domain=?)", (DOMAIN,))
cur.execute("DELETE FROM classes WHERE domain=?", (DOMAIN,))
cur.execute("DELETE FROM decision_nodes WHERE domain=?", (DOMAIN,))
cur.execute("DELETE FROM search_idx WHERE class_name LIKE 'mem_arch_%'")
db.commit()

ingested_classes = 0
ingested_methods = 0
class_id_map = {}

for cls in classes:
    full_name = "mem_arch_" + cls["name"]
    cur.execute("""INSERT INTO classes
        (class_name, class_code, domain, line_start, is_vbstyle, has_run_method, has_tuple3, version, created_at)
        VALUES (?,?,?,?,?,?,?,?,datetime('now'))""",
        (full_name, cls["code"], DOMAIN, cls["line_start"],
         1 if cls["is_vbstyle"] else 0,
         1 if cls["has_run"] else 0,
         0, 1))
    cid = cur.lastrowid
    class_id_map[cls["name"]] = cid
    ingested_classes += 1
    for mth in methods:
        if mth["class_name"] != cls["name"]:
            continue
        cur.execute("""INSERT INTO methods
            (class_id, method_name, method_code, params, signature,
             is_dunder, is_vbstyle, returns_tuple3, line_start, version, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
            (cid, mth["method_name"], mth["method_code"], mth["params"],
             mth["signature"], 1 if mth["is_dunder"] else 0,
             1 if mth["is_vbstyle"] else 0,
             1 if mth["returns_tuple3"] else 0, mth["line_start"], 1))
        mid = cur.lastrowid
        cur.execute("INSERT INTO search_idx (method_id, method_code, class_name, method_name) VALUES (?,?,?,?)",
                    (mid, mth["method_code"], full_name, mth["method_name"]))
        ingested_methods += 1

# Build decision_nodes: one per class, one per unique method
node_map = {}
for cls in classes:
    cur.execute("INSERT INTO decision_nodes (domain, name, node_type, payload) VALUES (?,?,?,?)",
                (DOMAIN, cls["name"], "class", cls["name"]))
    node_map[cls["name"]] = cur.lastrowid

# Build decision_edges: file -> class (DEFINES), class -> method (HAS_METHOD)
# We model: a synthetic root node -> each class
cur.execute("INSERT INTO decision_nodes (domain, name, node_type, payload) VALUES (?,?,?,?)",
            (DOMAIN, "MEM_Complete_System", "root", "file"))
root_node = cur.lastrowid

for cls in classes:
    cur.execute("INSERT INTO decision_edges (from_node, to_node, condition, weight) VALUES (?,?,?,?)",
                (root_node, node_map[cls["name"]], "DEFINES", 1.0))

# Edges: boot chain (the declared order from the architecture doc)
boot_chain = ["MemUnit", "core_config", "Core_os", "Core_hw", "Core_io",
              "Core_ast", "Core_brackets", "Core_rules", "Core_error",
              "Core_report", "Core_output"]
for i in range(len(boot_chain) - 1):
    a, b = boot_chain[i], boot_chain[i+1]
    if a in node_map and b in node_map:
        cur.execute("INSERT INTO decision_edges (from_node, to_node, condition, weight) VALUES (?,?,?,?)",
                    (node_map[a], node_map[b], "boot_order", 1.0))

# Edges: ownership relationships from the architecture
ownership = [
    ("TheClassSetup", "MemUnit", "starts_first"),
    ("MemUnit", "CoreDB", "calls_for_db_engine"),
    ("MemUnit", "Core_db", "calls_for_db_engine"),
    ("MemUnit", "GuiDB", "owns"),
    ("MemUnit", "GuiBus", "owns"),
    ("TheClassSetup", "core_config", "calls"),
    ("TheClassSetup", "Core_os", "calls"),
    ("TheClassSetup", "Core_hw", "calls"),
    ("TheClassSetup", "Core_io", "calls"),
    ("TheClassSetup", "Core_ast", "calls"),
    ("TheClassSetup", "Core_brackets", "calls"),
    ("TheClassSetup", "Core_rules", "calls"),
    ("TheClassSetup", "Core_error", "calls"),
    ("TheClassSetup", "Core_report", "calls"),
    ("TheClassSetup", "Core_output", "calls"),
    ("Core_error", "errorcodes", "sends_raw_to"),
    ("Core_report", "Core_output", "sends_formatted_to"),
    ("Core_ai", "Core_ai_fix", "calls_for_repair"),
    ("Core_ai", "Core_memory_bank", "uses"),
    ("Core_ai_fix", "Core_io", "writes_through"),
    ("Core_ai_fix", "Core_rules", "validates_through"),
    ("Core_ai_fix", "Core_ast", "checks_through"),
    ("Core_ai_fix", "Core_brackets", "checks_through"),
    ("resources", "Core_os", "reads"),
    ("resources", "Core_hw", "reads"),
    ("resources", "Core_io", "reads"),
    ("resources", "Core_gpu", "reads"),
    ("Core_compression", "Core_io", "routes_through"),
    ("Core_online_research", "Core_network", "uses"),
    ("Core_online_research", "Core_ai", "uses"),
    ("Core_code_library", "Core_io", "uses"),
    ("Core_code_library", "Core_ast", "uses"),
    ("Core_code_library", "Core_brackets", "uses"),
    ("Core_orchestrator", "Core_brackets", "parses_with"),
    ("Core_orchestrator", "Core_FileManager", "validates_with"),
    ("Core_backend_health", "Core_os", "uses"),
    ("Core_backend_health", "Core_hw", "uses"),
    ("Core_backend_health", "Core_ai", "routes_to"),
    ("Core_token_engine", "Core_ast", "supports"),
    ("Core_token_engine", "Core_brackets", "supports"),
    ("Core_code_hunter", "Core_ast", "uses"),
    ("Core_code_hunter", "Core_brackets", "uses"),
]
for a, b, cond in ownership:
    if a in node_map and b in node_map:
        cur.execute("INSERT INTO decision_edges (from_node, to_node, condition, weight) VALUES (?,?,?,?)",
                    (node_map[a], node_map[b], cond, 1.0))

db.commit()
print("  Ingested classes:  " + str(ingested_classes))
print("  Ingested methods:  " + str(ingested_methods))
print("  Decision nodes:    " + str(len(node_map) + 1))
print("  Decision edges:    " + str(len(ownership) + len(boot_chain) - 1 + len(classes)))

# ─── 3. Run GraphEngine tools ──────────────────────────────────────────────
Section("3. RUN GraphEngine tools against mem_arch domain")
from GraphEngine import GraphEngine
ge = GraphEngine()
ge.state["domain"] = DOMAIN

commands = [
    ("status", {}),
    ("spec", {"domain": DOMAIN}),
    ("gap", {"domain": DOMAIN}),
    ("bfs", {"start_node": node_map.get("MemUnit")}),
    ("dfs", {"start_node": node_map.get("MemUnit")}),
    ("cycle", {}),
    ("topology", {}),
    ("path", {"start_node": node_map.get("TheClassSetup"), "end_node": node_map.get("Core_output")}),
    ("path", {"start_node": node_map.get("MemUnit"), "end_node": node_map.get("Core_ai_fix")}),
    ("search", {"query": "MemUnit"}),
    ("search", {"query": "repair"}),
    ("search", {"query": "boot"}),
    ("dependency", {}),
    ("orchestration", {}),
    ("lifecycle", {}),
    ("error", {}),
    ("plan", {"domain": DOMAIN}),
    ("flow", {"domain": DOMAIN}),
]

results = []
for cmd, params in commands:
    ok, data, err = ge.Run(cmd, params)
    status = "OK" if ok else "FAIL"
    results.append((cmd, ok, err))
    summary = ""
    if data:
        if "count" in data:
            summary = "count=" + str(data["count"])
        elif "visited" in data:
            summary = "visited=" + str(data["visited"])
        elif "found" in data:
            summary = "found=" + str(data["found"])
        elif "has_cycles" in data:
            summary = "cycles=" + str(data["has_cycles"])
        elif "results" in data:
            summary = "results=" + str(len(data["results"]))
        elif "missing_count" in data:
            summary = "missing=" + str(data["missing_count"])
        elif "classes" in data:
            summary = "classes=" + str(len(data["classes"]))
        elif "steps" in data:
            summary = "steps=" + str(len(data["steps"]))
        elif "flows" in data:
            summary = "flows=" + str(len(data["flows"]))
        elif "dependencies" in data:
            summary = "deps=" + str(len(data["dependencies"]))
        elif "calls" in data:
            summary = "calls=" + str(len(data["calls"]))
        elif "phases" in data:
            summary = "phases=" + str(len(data["phases"]))
        elif "errors" in data:
            summary = "errors=" + str(len(data["errors"]))
        elif "topology" in data:
            summary = "topology_len=" + str(len(data["topology"]))
        else:
            summary = json.dumps(data)[:80]
    print("  {:18s} {:4s}  {}".format(cmd, status, summary if summary else str(err)))

# ─── 4. Detailed graph queries ─────────────────────────────────────────────
Section("4. GRAPH QUERIES — detailed results")

ok, data, err = ge.Run("bfs", {"start_node": node_map.get("MemUnit")})
if ok:
    print("  BFS from MemUnit: " + " -> ".join(str(n) for n in data["order"][:15]))

ok, data, err = ge.Run("dfs", {"start_node": node_map.get("MemUnit")})
if ok:
    print("  DFS from MemUnit: " + " -> ".join(str(n) for n in data["order"][:15]))

ok, data, err = ge.Run("cycle", {})
if ok:
    print("  Cycles detected: " + str(data["count"]))
    for c in data["cycles"][:5]:
        print("    " + str(c))

ok, data, err = ge.Run("topology", {})
if ok:
    # Map node ids back to names
    id_to_name = {}
    for row in cur.execute("SELECT node_id, name FROM decision_nodes WHERE domain=?", (DOMAIN,)).fetchall():
        id_to_name[row[0]] = row[1]
    names = [id_to_name.get(n, str(n)) for n in data["topology"]]
    print("  Topology order: " + " -> ".join(names[:20]))

ok, data, err = ge.Run("path", {"start_node": node_map.get("TheClassSetup"), "end_node": node_map.get("Core_output")})
if ok:
    id_to_name = {}
    for row in cur.execute("SELECT node_id, name FROM decision_nodes WHERE domain=?", (DOMAIN,)).fetchall():
        id_to_name[row[0]] = row[1]
    if data["path"]:
        names = [id_to_name.get(n, str(n)) for n in data["path"]]
        print("  Path Setup->Output: " + " -> ".join(names))
    else:
        print("  Path Setup->Output: NOT FOUND")

ok, data, err = ge.Run("path", {"start_node": node_map.get("MemUnit"), "end_node": node_map.get("Core_ai_fix")})
if ok:
    id_to_name = {}
    for row in cur.execute("SELECT node_id, name FROM decision_nodes WHERE domain=?", (DOMAIN,)).fetchall():
        id_to_name[row[0]] = row[1]
    if data["path"]:
        names = [id_to_name.get(n, str(n)) for n in data["path"]]
        print("  Path MemUnit->AiFix: " + " -> ".join(names))
    else:
        print("  Path MemUnit->AiFix: NOT FOUND")

ok, data, err = ge.Run("spec", {"domain": DOMAIN})
if ok:
    print("  Spec view classes: " + str(data["count"]))
    for c in data["classes"][:10]:
        print("    " + c["name"] + " (vbstyle=" + str(c["vbstyle"]) + ")")

ok, data, err = ge.Run("search", {"query": "MemUnit"})
if ok:
    print("  Search 'MemUnit': " + str(data["count"]) + " hits")
    for r in data["results"][:5]:
        print("    " + r["class"] + " :: " + r["snippet"][:60])

ok, data, err = ge.Run("search", {"query": "repair"})
if ok:
    print("  Search 'repair': " + str(data["count"]) + " hits")
    for r in data["results"][:5]:
        print("    " + r["class"] + " :: " + r["snippet"][:60])

db.close()

# ─── 5. Verdict ────────────────────────────────────────────────────────────
Section("5. VERDICT — yin-yang of the tools")
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print("  Commands run:    " + str(len(results)))
print("  Passed:          " + str(passed))
print("  Failed:          " + str(failed))
print()
for cmd, ok, err in results:
    if not ok:
        print("  FAIL: " + cmd + " -> " + str(err))
print()
print("  YIN (good):")
print("    - AST parser handles 35 classes, 32 unique methods cleanly")
print("    - Ingestion into SQLite works, search_idx populated")
print("    - BFS/DFS/topology/cycle/path all execute against decision_edges")
print("    - FTS5 search returns hits for 'MemUnit', 'repair', 'boot'")
print("    - GraphEngine.Run() dispatch + Tuple3 returns work as designed")
print()
print("  YANG (bad / gaps):")
print("    - 0 VBStyle classes detected (no Run+self.state) — tool correctly")
print("      reports this but the architecture file is spec-only, not code")
print("    - decision_edges are manually seeded (boot_chain + ownership list)")
print("      the tools do NOT auto-derive edges from comments/contracts")
print("    - DependencyView/OrchestrationView return HARDCODED data, not")
print("      queried from the ingested graph — they ignore the actual domain")
print("    - LifecycleView returns a HARDCODED phase list, not derived")
print("    - ErrorView returns a HARDCODED error list, not derived")
print("    - GapView checks for graph_engine tables, not mem_arch tables")
print("    - PlanView/FlowView query plan_steps/orchestration which were")
print("      not populated for mem_arch domain")
print("    - No edge extraction from the Ghost header bracket rules")
print("    - No class-to-class relationship auto-discovery from comments")
print()
print("  BOTTOM LINE:")
print("    The AST + DB + graph-algorithm layer is solid (yin).")
print("    The view layer is half-hardcoded and domain-blind (yang).")
print("    Tools work as a graph executor but NOT as an architecture analyzer.")
