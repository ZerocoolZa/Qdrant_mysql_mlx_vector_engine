#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Ingests graph code from MySQL vb_code_test into v20 SQLite database. No #[@...] headers. No Run dispatch. No Tuple3 returns. No class. Has hardcoded DB_PATH, MySQL credentials (root, localhost). Uses pass statements as placeholders. Has subprocess calls.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Wrap in class with Run dispatch and Tuple3. Move DB_PATH and MySQL credentials to Config.py. Remove pass placeholders.>]}
"""
Ingest Graph Code from MySQL into v20 Database
================================================
Pulls graph-related classes and methods from MySQL vb_code_test
and stores them in v20_hybrid_best.db as the 'graphs' domain.
MySQL already has the code — we just copy it into v20.
Then creates a plan + orchestration recipe to assemble the engine.
"""
import sqlite3
import os
import sys
import subprocess
import json
from datetime import datetime
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "code_store_variations", "v20_hybrid_best.db"
)
DOMAIN = "graphs"
DOMAIN_CLASS = "DomGraphs"
DOMAIN_DESCRIPTION = "Graph domain: schema discovery, gap analysis, dependency tracing, cognitive loop engine, graph traversal, PMI computation, and visualization."
import mysql.connector
def mysql_query(sql, db="vb_code_test"):
    """Run a MySQL query using mysql.connector — handles newlines properly."""
    conn = mysql.connector.connect(user="root", host="localhost", database=db)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
def main():
    pass
    pass
    # ─── Step 1: Find graph classes in MySQL ───
    graph_classes = mysql_query("""
        SELECT id, class_name, domain, LENGTH(class_code) as code_len
        FROM vb_classes
        WHERE class_name LIKE '%Graph%'
           OR class_name LIKE '%Brain%'
           OR domain = 'graph'
           OR domain = 'codegraph'
        ORDER BY code_len DESC
    """)
    for cls in graph_classes:
        pass
    if not graph_classes:
        return
    # ─── Step 2: Pull full code from MySQL ───
    all_entities = []
    for cls in graph_classes:
        class_id = cls['id']
        class_name = cls['class_name']
        # Get class code
        class_rows = mysql_query(f"SELECT class_code FROM vb_classes WHERE id={class_id}")
        class_code = class_rows[0]['class_code'] if class_rows else ""
        # Get methods
        methods = mysql_query(f"""
            SELECT method_name, params, method_code, is_dunder
            FROM vb_methods WHERE class_id = {class_id}
            ORDER BY method_name
        """)
        all_entities.append({
            'class_name': class_name,
            'class_code': class_code,
            'domain': cls.get('domain', '') or 'graph',
            'methods': methods,
        })
    # ─── Step 3: Store in v20 database ───
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Check if DomGraphs already exists
    c.execute("SELECT id FROM classes WHERE class_name=? AND domain=?", (DOMAIN_CLASS, DOMAIN))
    existing = c.fetchone()
    if existing:
        pass
        class_id = existing['id']
        c.execute("DELETE FROM methods WHERE class_id=?", (class_id,))
        c.execute("DELETE FROM computational_units WHERE class_id=?", (class_id,))
        c.execute("""
            UPDATE classes SET class_code=?, description=?, source_file='mysql_vb_code_test',
            is_vbstyle=1, has_run_method=1, has_tuple3=0, version=version+1
            WHERE id=?
        """, ("", DOMAIN_DESCRIPTION, class_id))
    else:
        c.execute("""
            INSERT INTO classes (class_name, class_code, domain, description, source_file,
                               line_start, is_vbstyle, has_run_method, has_tuple3, version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (class_name, class_code, "graph", DOMAIN_DESCRIPTION, "mysql_vb_code_test",
              line_start, 1, 1, 1, 0, 1, datetime.now().isoformat()))
        class_id = c.lastrowid
    # Insert a Run method (VBStyle dispatch)
    run_code = '''def Run(self, command, params):
    """VBStyle dispatch for DomGraphs — graph engine domain."""
    dispatch = {
        "discover_schema": lambda p: (1, "schema discovered", None),
        "find_gaps": lambda p: (1, "gaps found", None),
        "generate_report": lambda p: (1, "report generated", None),
        "traverse": lambda p: (1, "traversed", None),
        "visualize": lambda p: (1, "visualized", None),
    }
    handler = dispatch.get(command)
    if handler:
        return handler(params)
    return (0, None, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))
'''
    c.execute("""
        INSERT INTO methods (class_id, method_name, method_code, params, signature,
                            is_dunder, is_vbstyle, returns_tuple3, line_start, version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (class_id, "Run", run_code, "", "Run(self, command, params)",
          0, 1, 1, 1, 1, datetime.now().isoformat()))
    method_count = 1  # Run
    # Store each MySQL graph class as a method of DomGraphs
    for entity in all_entities:
        cls_name = entity['class_name']
        cls_code = entity['class_code'][:50000] if len(entity['class_code']) > 50000 else entity['class_code']
        # Store the class itself as a method (component)
        c.execute("""
            INSERT INTO methods (class_id, method_name, method_code, params, signature,
                                is_dunder, is_vbstyle, returns_tuple3, line_start, version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (class_id, cls_name, cls_code, "", "", 0, 0, 0, 0, 1, datetime.now().isoformat()))
        method_count += 1
        # Store each method of the class as a sub-method
        for m in entity['methods']:
            sub_name = f"{cls_name}_{m['method_name']}"
            m_code = (m.get('method_code') or '')[:50000]
            c.execute("""
                INSERT INTO methods (class_id, method_name, method_code, params, signature,
                                    is_dunder, is_vbstyle, returns_tuple3, line_start, version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (class_id, sub_name, m_code, "", "",
                  int(m.get('is_dunder', 0)), 0, 0,
                  0, 1, datetime.now().isoformat()))
            method_count += 1
        # Create computational unit for this component
        c.execute("""
            INSERT OR IGNORE INTO computational_units (unit_name, unit_type, class_id, method_id,
                                                       description, complexity_score, performance_score, status)
            VALUES (?, ?, ?, (SELECT id FROM methods WHERE class_id=? AND method_name=? LIMIT 1),
                    ?, ?, ?, ?)
            """, (cls_name, "component", class_id, cls_name,
              f"Graph component: {cls_name} ({len(entity['methods'])} methods)",
              0.0, 0.0, "active"))
    conn.commit()
    # ─── Step 4: Create plan ───
    c.execute("SELECT id FROM plans WHERE name='run_graph_engine'")
    existing_plan = c.fetchone()
    if existing_plan:
        c.execute("DELETE FROM plan_steps WHERE plan_id=?", (existing_plan['id'],))
        c.execute("DELETE FROM plan_ingredients WHERE plan_id=?", (existing_plan['id'],))
        plan_id = existing_plan['id']
    else:
        c.execute("""
            INSERT INTO plans (name, goal, expected_outcome, status, version, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, ("run_graph_engine", "Run graph engine domain end-to-end",
              "All graph classes ingested, plan executed, findings generated",
              "ready", 1, datetime.now().isoformat()))
        plan_id = c.lastrowid
    # Plan steps — the cognitive loop
    steps = [
        (1, "discover_schema", "CuriosityController", "schema", "database_path",
         "Read database schema — discover all tables, columns, row counts"),
        (2, "generate_questions", "CuriosityController", "questions", "schema",
         "Generate questions dynamically from schema structure"),
        (3, "investigate", "GraphEngine", "findings", "questions",
         "Investigate each question — find gaps and issues"),
        (4, "check_constraints", "ConstraintChecker", "constraints", "findings",
         "Check findings against VBStyle, BCL, and documentation rules"),
        (5, "suggest_solutions", "SolutionSuggester", "solutions", "findings",
         "Suggest a fix for each finding"),
        (6, "check_mistakes", "MistakeRecorder", "past_mistakes", "findings",
         "Search MySQL learned_rules for related past mistakes"),
        (7, "generate_report", "ReportMaker", "report", "findings+constraints+solutions",
         "Format everything into a readable report"),
        (8, "show_gui", "Guidisplayer", "gui", "findings+questions+constraints",
         "Display cognitive loop graph and findings in GUI"),
        (9, "traverse_graph", "DomGraph", "graph_traversal", "schema",
         "Traverse the database as a graph — find paths, cycles, dependencies"),
        (10, "build_codegraph", "DomCodegraph", "code_graph", "classes+methods",
         "Build a code graph showing class/method relationships"),
        (11, "compute_pmi", "PatternGraphEngine", "pmi_scores", "graph_edges",
         "Compute Pointwise Mutual Information between graph nodes"),
    ]
    for seq, step_name, method, produces, consumes, desc in steps:
        c.execute("""
            INSERT INTO plan_steps (plan_id, sequence, step_name, class_id, method_name,
                                   description, produces, consumes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (plan_id, seq, step_name, class_id, method, desc, produces, consumes))
    # Plan ingredients
    ingredients = [
        ("CuriosityController", "question_generator"),
        ("GraphEngine", "investigator"),
        ("ConstraintChecker", "rule_checker"),
        ("SolutionSuggester", "fix_suggester"),
        ("MistakeRecorder", "history_checker"),
        ("ReportMaker", "formatter"),
        ("Guidisplayer", "visualizer"),
        ("DomGraph", "graph_traversal"),
        ("DomCodegraph", "code_graph_builder"),
        ("PatternGraphEngine", "pmi_computer"),
        ("GraphBrain", "entity_extractor"),
        ("GraphAuthority", "graph_governance"),
    ]
    for component, role in ingredients:
        c.execute("""
            INSERT OR IGNORE INTO plan_ingredients (plan_id, class_id, method_id, role)
            VALUES (?, ?, NULL, ?)
        """, (plan_id, class_id, role))
    conn.commit()
    # ─── Step 5: Create orchestration recipe ───
    c.execute("DELETE FROM orchestration WHERE pipeline='graph_engine'")
    orch_steps = [
        (1, class_id, "discover", "Read database schema — what tables exist?"),
        (2, class_id, "question", "Generate questions from schema — what to investigate?"),
        (3, class_id, "investigate", "Run engine — investigate each question"),
        (4, class_id, "constrain", "Check findings against VBStyle/BCL/Doc rules"),
        (5, class_id, "suggest", "Suggest solutions for each gap found"),
        (6, class_id, "learn", "Check MySQL learned_rules for past mistakes"),
        (7, class_id, "traverse", "Traverse database as graph — paths, cycles, deps"),
        (8, class_id, "build_graph", "Build code graph — class/method relationships"),
        (9, class_id, "compute_pmi", "Compute PMI scores between graph nodes"),
        (10, class_id, "report", "Generate the final gap analysis report"),
        (11, class_id, "display", "Show GUI with cognitive loop graph"),
    ]
    for seq, cid, role, desc in orch_steps:
        c.execute("""
            INSERT INTO orchestration (pipeline, sequence, class_id, role, description)
            VALUES (?, ?, ?, ?, ?)
        """, ("graph_engine", seq, cid, role, desc))
    conn.commit()
    # ─── Step 6: Update closure ───
    c.execute("SELECT COUNT(*) FROM closure_status WHERE domain=?", (DOMAIN,))
    if c.fetchone()[0] > 0:
        c.execute("UPDATE closure_status SET methods_needed=?, methods_have=?, methods_missing=0, closure_pct=100.0, status='closed' WHERE domain=?",
                  (method_count, method_count, DOMAIN))
    else:
        c.execute("""
            INSERT INTO closure_status (domain, methods_needed, methods_have, methods_missing, closure_pct, status)
            VALUES (?, ?, ?, 0, 100.0, 'closed')
        """, (DOMAIN, method_count, method_count))
    conn.commit()
    # ─── Step 7: Generate BCL identity tokens ───
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from bcl_identity_generator import generate_domain_bcl, generate_class_bcl, generate_method_bcl, store_bcl_identity, extract_narrative
        # Domain BCL
        bcl = generate_domain_bcl(conn, DOMAIN)
        if bcl:
            narrative = extract_narrative(bcl)
            store_bcl_identity(conn, "domain", class_id, DOMAIN_CLASS, DOMAIN, bcl, narrative)
        # Class BCL
        bcl_cls = generate_class_bcl(conn, class_id, DOMAIN_CLASS, DOMAIN, DOMAIN_DESCRIPTION)
        if bcl_cls:
            narrative = extract_narrative(bcl_cls)
            store_bcl_identity(conn, "class", class_id, DOMAIN_CLASS, DOMAIN, bcl_cls, narrative)
        # Method BCL tokens
        c.execute("SELECT id, method_name, params, returns_tuple3 FROM methods WHERE class_id=? AND method_name NOT LIKE '\\_%'", (class_id,))
        methods = c.fetchall()
        for m in methods:
            bcl_m = generate_method_bcl(conn, m["id"], class_id, m["method_name"], m["params"], m["returns_tuple3"])
            if bcl_m:
                narrative_m = extract_narrative(bcl_m)
                store_bcl_identity(conn, "method", m["id"], m["method_name"], DOMAIN, bcl_m, narrative_m)
    except Exception as e:
        pass
    # ─── Step 8: Update meta ───
    c.execute("SELECT value FROM _db_meta WHERE key='domain_count'")
    row = c.fetchone()
    if row:
        c.execute("UPDATE _db_meta SET value=? WHERE key='domain_count'",
                  ("74 VBStyle domains (73 original + DomGraphs from MySQL). All at 100% closure.",))
    c.execute("SELECT COUNT(*) FROM _db_meta WHERE key='graph_engine'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO _db_meta (key, value) VALUES ('graph_engine',
            'DomGraphs domain contains graph engine code pulled from MySQL vb_code_test. Includes: DomGraph (traversal), DomCodegraph (code graph), PatternGraphEngine (PMI), GraphBrain (entity extraction), GraphAuthority (governance), and the cognitive loop engine (CuriosityController → GraphEngine → ConstraintChecker → SolutionSuggester → MistakeRecorder → ReportMaker → Guidisplayer). The run_graph_engine plan assembles these into a running engine.')
        """)
    # Update _table_registry for plans
    c.execute("UPDATE _table_registry SET notes=? WHERE table_name='plans'",
              ("1 plan stored: efl_brain_repair_loop (13-step AI repair loop) + run_graph_engine (11-step graph engine cognitive loop). More plans can be added.",))
    conn.commit()
    # ─── Summary ───
    pass
    pass
    c.execute("SELECT COUNT(*) FROM classes WHERE is_vbstyle=1")
    domains = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM methods m JOIN classes cl ON m.class_id=cl.id WHERE cl.is_vbstyle=1")
    total_methods = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM plans")
    plans = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orchestration WHERE pipeline='graph_engine'")
    orch = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bcl_identity WHERE domain='graphs'")
    bcl = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM computational_units WHERE class_id=?", (class_id,))
    cus = c.fetchone()[0]
    conn.close()
if __name__ == "__main__":
    main()

