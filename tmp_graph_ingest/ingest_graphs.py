#!/usr/bin/env python3
"""
Graph Code Ingestion — puts all graph code into v20_hybrid_best.db.

Reads graph-related .py files from:
  - dom_compression/    (8 spec graph viewers)
  - efl_brain/          (code graph, agent graph, boot graph, viewer, etc.)
  - code_store_variations/ (DomGraph, DomCodegraph, CodeStore)

Parses with AST, extracts classes + methods, inserts into the DB
with domain='graph_engine' tagging.

Also creates bcl_instructions table — BCL-format decision tree for AI agents.
"""

import sqlite3
import ast
import os
import hashlib
import time
import textwrap

T0 = time.time()

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"

# ─── Files to ingest ──────────────────────────────────────────────────────

BASE = "/Users/wws/Qdrant_mysql_mlx_vector_engine"

INGEST_FILES = [
    # dom_compression — 8 spec graph viewers
    (f"{BASE}/dom_compression/plan_graph.py",       "graph_engine", "plan_view"),
    (f"{BASE}/dom_compression/spec_graph.py",       "graph_engine", "spec_view"),
    (f"{BASE}/dom_compression/spec_flow.py",        "graph_engine", "flow_view"),
    (f"{BASE}/dom_compression/lifecycle_graph.py",  "graph_engine", "lifecycle_view"),
    (f"{BASE}/dom_compression/dep_graph.py",        "graph_engine", "dependency_view"),
    (f"{BASE}/dom_compression/error_graph.py",      "graph_engine", "error_view"),
    (f"{BASE}/dom_compression/orch_graph.py",       "graph_engine", "orchestration_view"),
    (f"{BASE}/dom_compression/gap_graph.py",        "graph_engine", "gap_view"),
    # efl_brain — graph analysis brothers
    (f"{BASE}/efl_brain/Efi_code_graph.py",         "graph_engine", "code_graph"),
    (f"{BASE}/efl_brain/Efi_agent_graph.py",        "graph_engine", "agent_graph"),
    (f"{BASE}/efl_brain/Efi_boot_graph.py",         "graph_engine", "boot_graph"),
    (f"{BASE}/efl_brain/Efi_graph_viewer.py",       "graph_engine", "graph_viewer"),
    (f"{BASE}/efl_brain/Efi_connector.py",          "graph_engine", "graph_connector"),
    (f"{BASE}/efl_brain/Efi_orchestrator.py",       "graph_engine", "graph_orchestrator"),
    (f"{BASE}/efl_brain/Efi_brain_db.py",           "graph_engine", "graph_db"),
    (f"{BASE}/efl_brain/Efi_repair.py",             "graph_engine", "graph_repair"),
    (f"{BASE}/efl_brain/Efi_solution_engine.py",    "graph_engine", "graph_solution"),
    (f"{BASE}/efl_brain/Efi_knowledge_archaeology.py", "graph_engine", "graph_archaeology"),
    (f"{BASE}/efl_brain/Efi_core.py",               "graph_engine", "graph_core"),
    (f"{BASE}/efl_brain/Efi_ram_ai.py",             "graph_engine", "graph_ram_ai"),
    (f"{BASE}/efl_brain/Efi_agent_brain.py",        "graph_engine", "graph_agent_brain"),
    (f"{BASE}/efl_brain/Efi_formal_spec.py",        "graph_engine", "graph_formal_spec"),
    # code_store_variations — graph algorithm MemUnits
    (f"{BASE}/code_store_variations/impl_graph.py",     "graph_engine", "dom_graph"),
    (f"{BASE}/code_store_variations/impl_codegraph.py", "graph_engine", "dom_codegraph"),
    (f"{BASE}/code_store_variations/CodeStore.py",      "graph_engine", "code_store"),
]


def ParsePythonFile(filepath):
    """Parse a .py file with AST, return (classes, methods, file_hash)."""
    with open(filepath, "r", errors="replace") as f:
        source = f.read()
    file_hash = hashlib.sha256(source.encode()).hexdigest()[:16]
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"  WARN: Syntax error in {filepath}: {e}")
        return [], [], file_hash

    classes = []
    methods = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            class_code = ast.get_source_segment(source, node) or ""
            bases = [ast.dump(b) for b in node.bases]
            is_memunit = "Run" in [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            has_state = "self.state" in class_code

            classes.append({
                "name": class_name,
                "code": class_code,
                "bases": ",".join(bases),
                "is_memunit": is_memunit,
                "has_state": has_state,
                "line_start": node.lineno,
            })

            for item in node.body:
                if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                    method_name = item.name
                    method_code = ast.get_source_segment(source, item) or ""
                    params = [arg.arg for arg in item.args.args]
                    is_dunder = method_name.startswith("__") and method_name.endswith("__")
                    is_vbstyle = method_name == "Run" or method_name[0].isupper()
                    returns_tuple3 = "return (1," in method_code or "return (0," in method_code or "return (True," in method_code or "return (False," in method_code

                    methods.append({
                        "class_name": class_name,
                        "method_name": method_name,
                        "method_code": method_code,
                        "params": ",".join(params),
                        "signature": f"def {method_name}({', '.join(params)})",
                        "is_dunder": is_dunder,
                        "is_vbstyle": is_vbstyle,
                        "returns_tuple3": returns_tuple3,
                        "line_start": item.lineno,
                    })

    return classes, methods, file_hash


def IngestFiles(db_path, ingest_files):
    """Ingest all files into the database."""
    db = sqlite3.connect(db_path)
    cur = db.cursor()

    # Get max class id
    cur.execute("SELECT MAX(id) FROM classes")
    max_class_id = cur.fetchone()[0] or 0

    # Get max method id
    cur.execute("SELECT MAX(id) FROM methods")
    max_method_id = cur.fetchone()[0] or 0

    total_classes = 0
    total_methods = 0
    skipped = 0

    for filepath, domain, subdomain in ingest_files:
        if not os.path.exists(filepath):
            print(f"  SKIP: {filepath} — not found")
            skipped += 1
            continue

        filename = os.path.basename(filepath)
        classes, methods, file_hash = ParsePythonFile(filepath)

        print(f"  {filename:40s}  {len(classes):2d} classes  {len(methods):3d} methods")

        for cls in classes:
            max_class_id += 1
            full_class_name = f"{subdomain}_{cls['name']}"
            # Check if already exists
            cur.execute("SELECT id FROM classes WHERE class_name=? AND domain=?", (full_class_name, domain))
            existing = cur.fetchone()
            if existing:
                cur.execute("""UPDATE classes SET class_code=?, line_start=?, version=version+1 
                              WHERE id=?""",
                           (cls["code"], cls["line_start"], existing[0]))
                class_id = existing[0]
            else:
                cur.execute("""INSERT INTO classes 
                    (class_name, class_code, domain, line_start, version, created_at)
                    VALUES (?,?,?,?,?,datetime('now'))""",
                           (full_class_name, cls["code"], domain, cls["line_start"], 1))
                class_id = cur.lastrowid
            total_classes += 1

            # Insert methods for this class
            for mth in methods:
                if mth["class_name"] != cls["name"]:
                    continue
                max_method_id += 1
                cur.execute("""INSERT INTO methods
                    (class_id, method_name, method_code, params, signature, 
                     is_dunder, is_vbstyle, returns_tuple3, line_start, version, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
                           (class_id, mth["method_name"], mth["method_code"],
                            mth["params"], mth["signature"], mth["is_dunder"],
                            mth["is_vbstyle"], mth["returns_tuple3"], mth["line_start"], 1))
                total_methods += 1

                # Update search index
                cur.execute("""INSERT INTO search_idx (method_id, method_code, class_name, method_name)
                    VALUES (?,?,?,?)""",
                           (cur.lastrowid, mth["method_code"], full_class_name, mth["method_name"]))

    db.commit()

    # Add orchestration entries for graph_engine domain
    cur.execute("DELETE FROM orchestration WHERE pipeline='graph_engine'")
    seq = 0
    for filepath, domain, subdomain in ingest_files:
        if not os.path.exists(filepath):
            continue
        filename = os.path.basename(filepath)
        cur.execute("SELECT id FROM classes WHERE class_name LIKE ? AND domain='graph_engine'",
                   (f"%{subdomain.replace('_view','').replace('graph_','').title()}%",))
        row = cur.fetchone()
        class_id = row[0] if row else None
        seq += 1
        cur.execute("""INSERT INTO orchestration (pipeline, sequence, class_id, role, description)
            VALUES (?,?,?,?,?)""",
                   ("graph_engine", seq, class_id, subdomain, filename))

    db.commit()

    # Update plan_steps for graph_engine pipeline
    cur.execute("""SELECT id FROM plans WHERE name='graph_engine_pipeline'""")
    plan_row = cur.fetchone()
    if not plan_row:
        cur.execute("""INSERT INTO plans (name, description, goal, ingredients_needed, expected_outcome, status)
            VALUES (?,?,?,?,?,?)""",
                   ("graph_engine_pipeline",
                    "Unified graph engine — all graph views in one VBStyle domain",
                    "Build a single GraphEngine MemUnit that dispatches to 8+ graph views, sharing data and rendering",
                    "DomGraph, DomCodegraph, GraphViewer, PlanView, SpecView, FlowView, LifecycleView, DependencyView, ErrorView, OrchestrationView, GapView",
                    "Run('plan', {domain:'x'}) opens plan view; Run('gap', {domain:'x'}) opens gap view; all share spec_data",
                    "active"))
        plan_id = cur.lastrowid

        steps = [
            ("Ingest graph code", "graph_engine", "Collect all graph code from 3 folders into DB"),
            ("Create BCL instructions", "graph_engine", "Write BCL decision tree for AI agents"),
            ("Build GraphEngine MemUnit", "graph_engine", "Run() dispatch to all views"),
            ("Build GraphViewer", "graph_engine", "Shared Tkinter rendering for all views"),
            ("Build PlanView", "graph_engine", "Editable idea → candidates → spec"),
            ("Build SpecView", "graph_engine", "Classes, nodes, edges, categories"),
            ("Build FlowView", "graph_engine", "Execution paths, step-by-step logic"),
            ("Build LifecycleView", "graph_engine", "Temporal phases, swim-lane ordering"),
            ("Build DependencyView", "graph_engine", "Edge justifications, dependency chains"),
            ("Build ErrorView", "graph_engine", "Error paths, failure modes, recovery"),
            ("Build OrchestrationView", "graph_engine", "Call tree, roots, leaves, dispatch"),
            ("Build GapView", "graph_engine", "Missing pairs, CRUD closure, coverage"),
            ("Build GUI", "graph_engine", "Visualize and manage graph codegraph"),
            ("Verify", "graph_engine", "Run all views, check Tuple3 returns, no errors"),
        ]
        for i, (name, dom, desc) in enumerate(steps, 1):
            cur.execute("""INSERT INTO plan_steps (plan_id, sequence, step_name, domain, description)
                VALUES (?,?,?,?,?)""",
                       (plan_id, i, name, dom, desc))
    else:
        plan_id = plan_row[0]

    db.commit()
    db.close()

    print(f"\n=== INGESTION COMPLETE ===")
    print(f"Files processed: {len(ingest_files) - skipped}")
    print(f"Files skipped:   {skipped}")
    print(f"Classes inserted: {total_classes}")
    print(f"Methods inserted: {total_methods}")
    print(f"Time: {time.time()-T0:.1f}s")
    return total_classes, total_methods


def CreateBclInstructions(db_path):
    """Create bcl_instructions table with BCL-format decision tree for AI agents."""
    db = sqlite3.connect(db_path)
    cur = db.cursor()

    cur.execute("DROP TABLE IF EXISTS bcl_instructions")
    cur.execute("""CREATE TABLE bcl_instructions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_name TEXT NOT NULL,
        bcl_content TEXT NOT NULL,
        category TEXT NOT NULL,
        weight INTEGER DEFAULT 50,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    instructions = [
        # ─── HOW TO ADD CODE ───────────────────────────────────────────────
        ("AddDomCode",
         '[@AddDomCode]{'
         '("Step1";"Search v20_hybrid_best.db classes table for existing similar code")'
         '("Step2";"Check domain column — if domain=graph_engine, code belongs here")'
         '("Step3";"Parse new .py file with AST — extract classes and methods")'
         '("Step4";"Insert into classes table with domain=graph_engine")'
         '("Step5";"Insert methods into methods table with is_vbstyle and returns_tuple3 flags")'
         '("Step6";"Update search_idx FTS5 table for full-text search")'
         '("Step7";"Run py_compile to verify — no syntax errors")'
         '("Step8";"Run violations check — no VBStyle rule violations")'
         '("Weight";"100")'
         '}',
         "howto", 100),

        # ─── WHAT CODE STYLE ───────────────────────────────────────────────
        ("CodeStyle",
         '[@CodeStyle]{'
         '[@Pass]{("VBStyle compliant — Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE constants";92)}'
         '[@Fail]{("No print statements, no decorators, no hardcoded paths, no self._ prefix, no tabs";92)}'
         '("Rule1";"Run(self, command, params=None) — single dispatch entry")'
         '("Rule2";"return (1, data, None) or (0, None, error) — Tuple3 always")'
         '("Rule3";"self.state = {} — no self._private attributes")'
         '("Rule4";"PascalCase classes, UPPERCASE constants, camelCase methods")'
         '("Rule5";"Ghost header + VBStyle header + class header + method header")'
         '("Rule6";"No print() — use return values for communication")'
         '("Rule7";"No decorators — @property, @staticmethod forbidden")'
         '("Rule8";"No hardcoded paths — all from Config class")'
         '("Weight";"95")'
         '}',
         "rules", 95),

        # ─── WHERE MUST IT GO ──────────────────────────────────────────────
        ("WhereDoesCodeGo",
         '[@WhereDoesCodeGo]{'
         '[@Pass]{("domain=graph_engine in classes table of v20_hybrid_best.db";92)}'
         '[@Fail]{("Do NOT create new .py files — code lives in the database";92)}'
         '("Table";"classes — class_name, class_code, domain, line_start")'
         '("Table";"methods — class_id FK, method_name, method_code, is_vbstyle, returns_tuple3")'
         '("Table";"search_idx — FTS5 full-text index on method_code")'
         '("Table";"orchestration — pipeline=graph_engine, sequence, role")'
         '("Table";"plan_steps — step-by-step build plan")'
         '("Table";"violations — rule violations per method")'
         '("Table";"bcl_instructions — THIS TABLE — decision tree for AI")'
         '("Weight";"90")'
         '}',
         "where", 90),

        # ─── HOW TO VERIFY ─────────────────────────────────────────────────
        ("HowToVerify",
         '[@HowToVerify]{'
         '("Check1";"py_compile — no syntax errors")'
         '("Check2";"ast.parse — valid Python AST")'
         '("Check3";"Run() method exists — is_vbstyle=1 in methods table")'
         '("Check4";"returns_tuple3=1 — at least one Tuple3 return")'
         '("Check5";"self.state present — no self._ attributes")'
         '("Check6";"No print() calls in method_code")'
         '("Check7";"No decorator syntax in class_code")'
         '("Check8";"violations table empty for this method_id")'
         '("Check9";"search_idx updated — FTS query finds the method")'
         '("Check10";"orchestration entry exists — pipeline=graph_engine")'
         '("Weight";"95")'
         '}',
         "verify", 95),

        # ─── DECISION TREE: ERROR HANDLING ─────────────────────────────────
        ("ErrorDecisionTree",
         '[@ErrorDecisionTree]{'
         '[@SyntaxError]{'
         '[@Pass]{("Fix syntax in class_code, UPDATE classes table, re-run py_compile";90)}'
         '[@Fail]{("If unfixable — mark version=version+1, log in violations table, skip";80)}'
         '("Action";"Fix or skip")'
         '("Weight";"85")'
         '}'
         '[@MissingRun]{'
         '[@Pass]{("Add Run(self, command, params=None) dispatch method to class";90)}'
         '[@Fail]{("If class is not a MemUnit — set is_vbstyle=0, domain=graph_engine_helper";80)}'
         '("Action";"Add Run or mark as helper")'
         '("Weight";"85")'
         '}'
         '[@MissingTuple3]{'
         '[@Pass]{("Refactor returns to (1, data, None) or (0, None, error)";90)}'
         '[@Fail]{("If method is void — return (1, None, None)";80)}'
         '("Action";"Refactor returns")'
         '("Weight";"80")'
         '}'
         '[@HardcodedPath]{'
         '[@Pass]{("Replace with Config.BASE_DIR or Config path constant";90)}'
         '[@Fail]{("If path is test-only — wrap in try/except, log to violations";80)}'
         '("Action";"Replace with Config")'
         '("Weight";"85")'
         '}'
         '[@ImportError]{'
         '[@Pass]{("Check if module exists in DB — search_idx query for class_name";90)}'
         '[@Fail]{("If missing — create stub class in DB, mark status=draft";80)}'
         '("Action";"Find in DB or create stub")'
         '("Weight";"80")'
         '}'
         '[@ViolationFound]{'
         '[@Pass]{("Fix the specific rule violation — UPDATE method_code";90)}'
         '[@Fail]{("If rule is not applicable — mark violation as resolved with note";80)}'
         '("Action";"Fix or mark resolved")'
         '("Weight";"85")'
         '}'
         '("Weight";"90")'
         '}',
         "error_handling", 90),

        # ─── WHEN TO ADD CODE ──────────────────────────────────────────────
        ("WhenToAddCode",
         '[@WhenToAddCode]{'
         '[@Pass]{("New graph view needed — Run() dispatch does not handle this command yet";92)}'
         '[@Pass]{("Existing method has bug — fix in method_code, increment version";90)}'
         '[@Pass]{("New domain data — add to spec_data, not to code";88)}'
         '[@Pass]{("Performance issue — refactor method_code in place";85)}'
         '[@Fail]{("Do NOT add code if search_idx already finds similar method";92)}'
         '[@Fail]{("Do NOT add code if plan_steps says step is done";90)}'
         '[@Fail]{("Do NOT add code if violations table has unresolved items for this class";88)}'
         '("Weight";"85")'
         '}',
         "when", 85),

        # ─── WHY VBSTYLE ───────────────────────────────────────────────────
        ("WhyVBStyle",
         '[@WhyVBStyle]{'
         '("Reason1";"Run() dispatch = single entry point = testable")'
         '("Reason2";"Tuple3 returns = consistent error handling = debuggable")'
         '("Reason3";"self.state dict = no hidden attributes = inspectable")'
         '("Reason4";"No print = no side effects = pure functions")'
         '("Reason5";"No decorators = no magic = readable")'
         '("Reason6";"No hardcoded paths = portable = deployable")'
         '("Reason7";"Code in DB = searchable = reusable = no file sprawl")'
         '("Reason8";"BCL instructions = AI can understand and follow rules")'
         '("Weight";"80")'
         '}',
         "why", 80),

        # ─── ALTERNATIVE STEPS ─────────────────────────────────────────────
        ("AlternativeSteps",
         '[@AlternativeSteps]{'
         '[@Step1Fail]{'
         '[@Pass]{("Search MySQL vb_shared.learned_rules for similar problem";90)}'
         '[@Fail]{("Search CODEBASE.python_files for similar pattern";85)}'
         '("Weight";"80")'
         '}'
         '[@Step2Fail]{'
         '[@Pass]{("Check efl_brain.db for existing graph implementation";90)}'
         '[@Fail]{("Check code_store_variations/ for DomGraph/DomCodegraph";85)}'
         '("Weight";"80")'
         '}'
         '[@Step3Fail]{'
         '[@Pass]{("Create minimal stub class — Run() returns (0, None, not_implemented)";90)}'
         '[@Fail]{("Log to violations table — mark as gap";85)}'
         '("Weight";"75")'
         '}'
         '[@VerifyFail]{'
         '[@Pass]{("Read bcl_instructions ErrorDecisionTree for this error type";90)}'
         '[@Fail]{("Ask human — log question in violations table with kind=question";85)}'
         '("Weight";"80")'
         '}'
         '("Weight";"85")'
         '}',
         "alternatives", 85),

        # ─── AM I ALLOWED ──────────────────────────────────────────────────
        ("AmIAllowed",
         '[@AmIAllowed]{'
         '[@Pass]{("Yes — if domain=graph_engine and plan_steps status != done";92)}'
         '[@Pass]{("Yes — if fixing a violation in violations table";90)}'
         '[@Pass]{("Yes — if adding a new graph view to the dispatch";88)}'
         '[@Fail]{("No — if code already exists in search_idx (duplicate)";92)}'
         '[@Fail]{("No — if plan_steps says step is done and no violation exists";90)}'
         '[@Fail]{("No — if code is not VBStyle compliant and cannot be refactored";88)}'
         '[@Fail]{("No — if adding a new .py file instead of DB row (nofiles rule)";92)}'
         '("Weight";"88")'
         '}',
         "permissions", 88),

        # ─── GRAPH ENGINE PIPELINE ─────────────────────────────────────────
        ("GraphEnginePipeline",
         '[@GraphEnginePipeline]{'
         '("Step1";"Plan — what capabilities does the domain need?")'
         '("Step2";"Spec — what classes exist? nodes, edges, categories")'
         '("Step3";"Flow — how does data move? execution paths")'
         '("Step4";"Lifecycle — when does each class run? temporal phases")'
         '("Step5";"Dependency — why do classes connect? edge justifications")'
         '("Step6";"Error — where does it fail? error paths, recovery routes")'
         '("Step7";"Orchestration — who calls who? call tree, dispatch hierarchy")'
         '("Step8";"Gap — what is missing? pairs, CRUD closure, coverage areas")'
         '("Step9";"Code — Devin writes VBStyle MemUnits")'
         '("Step10";"Verify — compare plan vs actual code (efl_brain inspect)")'
         '("Weight";"95")'
         '}',
         "pipeline", 95),

        # ─── KNOWLEDGE CODEGRAPH ───────────────────────────────────────────
        ("KnowledgeCodegraph",
         '[@KnowledgeCodegraph]{'
         '("Purpose";"Map all graph code in v20_hybrid_best.db to a knowledge graph")'
         '("Nodes";"classes table rows with domain=graph_engine")'
         '("Edges";"orchestration table — pipeline=graph_engine, sequence, role")'
         '("Traversal";"BFS from GraphEngine to PlanView to SpecView to GapView")'
         '("Cycle";"Plan to Spec to Flow to Gap to Code to Verify to Plan (loop)")'
         '("Query";"SELECT class_name, method_name FROM classes JOIN methods WHERE domain=graph_engine")'
         '("Search";"SELECT * FROM search_idx WHERE search_idx MATCH graph")'
         '("Violations";"SELECT * FROM violations JOIN methods ON violations.method_id=methods.id")'
         '("Plans";"SELECT * FROM plan_steps WHERE plan_id in graph_engine_pipeline")'
         '("Weight";"90")'
         '}',
         "codegraph", 90),
    ]

    for token_name, bcl_content, category, weight in instructions:
        cur.execute("""INSERT INTO bcl_instructions (token_name, bcl_content, category, weight)
            VALUES (?,?,?,?)""",
                   (token_name, bcl_content, category, weight))

    db.commit()

    # Verify
    cur.execute("SELECT COUNT(*) FROM bcl_instructions")
    count = cur.fetchone()[0]
    print(f"\n=== BCL INSTRUCTIONS CREATED ===")
    print(f"Instructions: {count}")
    cur.execute("SELECT token_name, category, weight FROM bcl_instructions ORDER BY weight DESC")
    for name, cat, w in cur.fetchall():
        print(f"  {name:30s}  {cat:20s}  weight={w}")

    db.close()
    return count


def VerifyIngestion(db_path):
    """Verify the ingestion worked."""
    db = sqlite3.connect(db_path)
    cur = db.cursor()

    print(f"\n=== VERIFICATION ===")

    # Graph engine classes
    cur.execute("SELECT COUNT(*) FROM classes WHERE domain='graph_engine'")
    cls_count = cur.fetchone()[0]
    print(f"graph_engine classes: {cls_count}")

    # Graph engine methods
    cur.execute("""SELECT COUNT(*) FROM methods m JOIN classes c ON m.class_id=c.id 
                   WHERE c.domain='graph_engine'""")
    mth_count = cur.fetchone()[0]
    print(f"graph_engine methods: {mth_count}")

    # VBStyle methods
    cur.execute("""SELECT COUNT(*) FROM methods m JOIN classes c ON m.class_id=c.id 
                   WHERE c.domain='graph_engine' AND m.is_vbstyle=1""")
    vb_count = cur.fetchone()[0]
    print(f"VBStyle methods: {vb_count}")

    # Tuple3 methods
    cur.execute("""SELECT COUNT(*) FROM methods m JOIN classes c ON m.class_id=c.id 
                   WHERE c.domain='graph_engine' AND m.returns_tuple3=1""")
    t3_count = cur.fetchone()[0]
    print(f"Tuple3 methods: {t3_count}")

    # Search index
    cur.execute("SELECT COUNT(*) FROM search_idx WHERE search_idx MATCH 'graph'")
    search_count = cur.fetchone()[0]
    print(f"Search 'graph' hits: {search_count}")

    # Orchestration
    cur.execute("SELECT COUNT(*) FROM orchestration WHERE pipeline='graph_engine'")
    orch_count = cur.fetchone()[0]
    print(f"Orchestration entries: {orch_count}")

    # Plan steps
    cur.execute("""SELECT COUNT(*) FROM plan_steps ps JOIN plans p ON ps.plan_id=p.id 
                   WHERE p.name='graph_engine_pipeline'""")
    plan_count = cur.fetchone()[0]
    print(f"Plan steps: {plan_count}")

    # BCL instructions
    cur.execute("SELECT COUNT(*) FROM bcl_instructions")
    bcl_count = cur.fetchone()[0]
    print(f"BCL instructions: {bcl_count}")

    # All tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print(f"\nAll tables ({len(tables)}): {', '.join(tables)}")

    # Total DB size
    db.close()
    db_size = os.path.getsize(db_path) / 1024 / 1024
    print(f"DB size: {db_size:.1f} MB")

    print(f"\n=== TOTAL TIME: {time.time()-T0:.1f}s ===")


if __name__ == "__main__":
    print("=== GRAPH CODE INGESTION ===")
    print(f"DB: {DB_PATH}")
    print(f"Files to ingest: {len(INGEST_FILES)}")
    print()

    total_classes, total_methods = IngestFiles(DB_PATH, INGEST_FILES)
    bcl_count = CreateBclInstructions(DB_PATH)
    VerifyIngestion(DB_PATH)
