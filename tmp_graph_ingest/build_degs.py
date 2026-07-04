#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     build_degs.py
# Domain:   graph_engine
# Authority: Creates DEGS schema + DecisionEngine + TmpWorkspace + seeds
#            decision_nodes from BCL instructions, then builds the GUI
# DB:       v20_hybrid_best.db
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — No hardcoded paths (all from constants)
#   @cstyle   — Coding style compliant
# ============================================================================

"""
DEGS Builder — creates the Decision Execution Graph System in v20_hybrid_best.db.

Steps:
  1. Create DEGS schema (4 tables)
  2. Seed decision_nodes from bcl_instructions (11 BCL tokens → 11 nodes)
  3. Seed decision_edges from BCL Pass/Fail branches
  4. Seed pipeline nodes (Plan → Spec → ... → Verify → loop)
  5. Verify schema + seeds
"""

import sqlite3
import json
import re
import time
import os

T0 = time.time()

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"
TMP_BASE = "/Users/wws/Qdrant_mysql_mlx_vector_engine/tmp_graph_ingest"


def CreateDegsSchema(db_path):
    """Create the 4 DEGS tables in v20_hybrid_best.db."""
    db = sqlite3.connect(db_path)
    cur = db.cursor()

    # Drop if exists (fresh start)
    for t in ["run_state", "execution_log", "decision_edges", "decision_nodes"]:
        cur.execute(f"DROP TABLE IF EXISTS {t}")

    cur.execute("""CREATE TABLE decision_nodes (
        node_id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT,
        name TEXT,
        node_type TEXT,
        payload TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE decision_edges (
        edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_node INTEGER,
        to_node INTEGER,
        condition TEXT,
        weight REAL DEFAULT 1.0,
        FOREIGN KEY(from_node) REFERENCES decision_nodes(node_id),
        FOREIGN KEY(to_node) REFERENCES decision_nodes(node_id)
    )""")

    cur.execute("""CREATE TABLE execution_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        node_id INTEGER,
        status TEXT,
        output TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(node_id) REFERENCES decision_nodes(node_id)
    )""")

    cur.execute("""CREATE TABLE run_state (
        run_id TEXT PRIMARY KEY,
        current_node INTEGER,
        state TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(current_node) REFERENCES decision_nodes(node_id)
    )""")

    db.commit()
    db.close()
    print("=== DEGS SCHEMA CREATED ===")
    print("  Tables: decision_nodes, decision_edges, execution_log, run_state")


def SeedFromBcl(db_path):
    """Seed decision_nodes from bcl_instructions table.
    Each BCL token becomes a decision_node.
    Parse Pass/Fail branches to create decision_edges."""
    db = sqlite3.connect(db_path)
    cur = db.cursor()

    # Read all BCL instructions
    cur.execute("SELECT id, token_name, bcl_content, category, weight FROM bcl_instructions ORDER BY weight DESC")
    instructions = cur.fetchall()

    node_map = {}  # token_name → node_id

    for inst_id, token_name, bcl_content, category, weight in instructions:
        # Create node for this BCL instruction
        cur.execute("""INSERT INTO decision_nodes (domain, name, node_type, payload)
            VALUES (?,?,?,?)""",
                   ("graph_engine", token_name, "action", bcl_content))
        node_id = cur.lastrowid
        node_map[token_name] = node_id

        # Parse Pass/Fail branches from BCL content
        # Look for [@Pass] and [@Fail] patterns
        pass_matches = re.findall(r'\[@Pass\]\{?\("([^"]+)";(\d+)\)', bcl_content)
        fail_matches = re.findall(r'\[@Fail\]\{?\("([^"]+)";(\d+)\)', bcl_content)

        # Create child nodes for Pass and Fail
        if pass_matches:
            pass_text = pass_matches[0][0]
            pass_weight = float(pass_matches[0][1]) / 100.0
            cur.execute("""INSERT INTO decision_nodes (domain, name, node_type, payload)
                VALUES (?,?,?,?)""",
                       ("graph_engine", f"{token_name}_pass", "check", pass_text))
            pass_node = cur.lastrowid
            cur.execute("""INSERT INTO decision_edges (from_node, to_node, condition, weight)
                VALUES (?,?,?,?)""",
                       (node_id, pass_node, "success", pass_weight))

        if fail_matches:
            fail_text = fail_matches[0][0]
            fail_weight = float(fail_matches[0][1]) / 100.0
            cur.execute("""INSERT INTO decision_nodes (domain, name, node_type, payload)
                VALUES (?,?,?,?)""",
                       ("graph_engine", f"{token_name}_fail", "fallback", fail_text))
            fail_node = cur.lastrowid
            cur.execute("""INSERT INTO decision_edges (from_node, to_node, condition, weight)
                VALUES (?,?,?,?)""",
                       (node_id, fail_node, "fail", fail_weight))

    # Create pipeline nodes: Plan → Spec → Flow → ... → Verify → loop
    pipeline_steps = [
        ("Plan", "action", "GraphEnginePipeline step 1 — what capabilities?"),
        ("Spec", "action", "GraphEnginePipeline step 2 — what classes exist?"),
        ("Flow", "action", "GraphEnginePipeline step 3 — how does data move?"),
        ("Lifecycle", "action", "GraphEnginePipeline step 4 — when does it run?"),
        ("Dependency", "action", "GraphEnginePipeline step 5 — why does it connect?"),
        ("Error", "action", "GraphEnginePipeline step 6 — where does it fail?"),
        ("Orchestration", "action", "GraphEnginePipeline step 7 — who calls who?"),
        ("Gap", "action", "GraphEnginePipeline step 8 — what is missing?"),
        ("Code", "action", "AddDomCode — write VBStyle MemUnits"),
        ("Verify", "check", "HowToVerify — check all rules"),
    ]

    pipeline_node_ids = []
    for name, node_type, payload in pipeline_steps:
        cur.execute("""INSERT INTO decision_nodes (domain, name, node_type, payload)
            VALUES (?,?,?,?)""",
                   ("graph_engine", f"pipeline_{name}", node_type, payload))
        pipeline_node_ids.append(cur.lastrowid)

    # Create edges: success → next step, fail → fallback
    for i, nid in enumerate(pipeline_node_ids):
        if i < len(pipeline_node_ids) - 1:
            # Success → next step
            cur.execute("""INSERT INTO decision_edges (from_node, to_node, condition, weight)
                VALUES (?,?,?,?)""",
                       (nid, pipeline_node_ids[i + 1], "success", 1.0))
        else:
            # Last step (Verify) success → END
            cur.execute("""INSERT INTO decision_nodes (domain, name, node_type, payload)
                VALUES (?,?,?,?)""",
                       ("graph_engine", "pipeline_END", "check", "Pipeline complete"))
            end_id = cur.lastrowid
            cur.execute("""INSERT INTO decision_edges (from_node, to_node, condition, weight)
                VALUES (?,?,?,?)""",
                       (nid, end_id, "success", 1.0))

        # Fail → fallback (review this step)
        cur.execute("""INSERT INTO decision_nodes (domain, name, node_type, payload)
            VALUES (?,?,?,?)""",
                   ("graph_engine", f"pipeline_{pipeline_steps[i][0]}_fallback", "fallback",
                    f"Review {pipeline_steps[i][0]} step — check violations and BCL instructions"))
        fallback_id = cur.lastrowid
        cur.execute("""INSERT INTO decision_edges (from_node, to_node, condition, weight)
            VALUES (?,?,?,?)""",
                   (nid, fallback_id, "fail", 0.5))

        # Fallback → back to this step (retry)
        cur.execute("""INSERT INTO decision_edges (from_node, to_node, condition, weight)
            VALUES (?,?,?,?)""",
                   (fallback_id, nid, "retry", 0.8))

    # Verify fail → loop back to Plan (with new knowledge)
    verify_id = pipeline_node_ids[-1]
    plan_id = pipeline_node_ids[0]
    cur.execute("""INSERT INTO decision_edges (from_node, to_node, condition, weight)
        VALUES (?,?,?,?)""",
               (verify_id, plan_id, "fail", 0.3))

    db.commit()

    # Summary
    cur.execute("SELECT COUNT(*) FROM decision_nodes")
    node_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM decision_edges")
    edge_count = cur.fetchone()[0]

    print(f"\n=== SEED COMPLETE ===")
    print(f"Decision nodes: {node_count}")
    print(f"Decision edges: {edge_count}")

    # Show pipeline
    print(f"\nPipeline nodes:")
    for name, _, _ in pipeline_steps:
        cur.execute("SELECT node_id FROM decision_nodes WHERE name=?", (f"pipeline_{name}",))
        nid = cur.fetchone()[0]
        cur.execute("SELECT to_node, condition, weight FROM decision_edges WHERE from_node=? ORDER BY weight DESC", (nid,))
        edges = cur.fetchall()
        edge_str = ", ".join(f"→{e[0]}({e[1]},w={e[2]})" for e in edges)
        print(f"  Node {nid:3d}: pipeline_{name:15s}  edges: {edge_str}")

    db.close()
    return node_count, edge_count


def VerifyDegs(db_path):
    """Verify the DEGS schema and seeds."""
    db = sqlite3.connect(db_path)
    cur = db.cursor()

    print(f"\n=== DEGS VERIFICATION ===")

    # Tables exist
    for t in ["decision_nodes", "decision_edges", "execution_log", "run_state"]:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        print(f"  {t:25s}  {cnt} rows")

    # Node types
    cur.execute("SELECT node_type, COUNT(*) FROM decision_nodes GROUP BY node_type")
    print(f"\n  Node types:")
    for nt, cnt in cur.fetchall():
        print(f"    {nt:15s}  {cnt}")

    # Edge conditions
    cur.execute("SELECT condition, COUNT(*) FROM decision_edges GROUP BY condition")
    print(f"\n  Edge conditions:")
    for cond, cnt in cur.fetchall():
        print(f"    {cond:15s}  {cnt}")

    # BCL instruction nodes
    cur.execute("""SELECT n.node_id, n.name, n.node_type, n.payload
                   FROM decision_nodes n
                   WHERE n.name NOT LIKE 'pipeline_%' AND n.name NOT LIKE '%_pass' AND n.name NOT LIKE '%_fail'
                   ORDER BY n.node_id""")
    print(f"\n  BCL instruction nodes:")
    for nid, name, nt, payload in cur.fetchall():
        print(f"    Node {nid:3d}: {name:30s}  type={nt:10s}  payload={payload[:60]}...")

    # All tables in DB
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print(f"\n  All DB tables ({len(tables)}): {', '.join(tables)}")

    db_size = os.path.getsize(db_path) / 1024 / 1024
    print(f"\n  DB size: {db_size:.1f} MB")
    print(f"  Time: {time.time()-T0:.1f}s")

    db.close()


if __name__ == "__main__":
    print("=== DEGS BUILDER ===")
    print(f"DB: {DB_PATH}")
    print()

    CreateDegsSchema(DB_PATH)
    SeedFromBcl(DB_PATH)
    VerifyDegs(DB_PATH)
