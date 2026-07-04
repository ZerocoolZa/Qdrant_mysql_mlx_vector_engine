#!/usr/bin/env python3
"""
Add the Cognitive Loop for the workflow domain into v20_hybrid_best.db.

The cognitive loop is:
  Problem → Question → Answer → Constraint → Mistake → Solution → Verify

Each step becomes a decision_node with edges connecting them.
This is NOT documentation — it's an executable graph that the
DecisionEngine walks to guide any AI through workflow operations.

The workflow domain has 5 operations (prj, index, config, validate, report).
Each operation gets its own cognitive loop.
"""

import sqlite3
from datetime import datetime

DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"


# ════════════════════════════════════════════════════════════════════════
# COGNITIVE LOOP NODES FOR WORKFLOW DOMAIN
# Each operation gets: Problem → Question → Answer → Constraint →
#                      Mistake → Solution → Verify
# ════════════════════════════════════════════════════════════════════════

WORKFLOW_NODES = [
    # ═══ ROOT: Workflow domain entry ═══
    {
        "id": "wf_root",
        "name": "WorkflowDomain",
        "node_type": "question",
        "domain": "workflow",
        "payload": "What workflow operation do you need? Options: prj, index, config, validate, report",
        "category": "root",
    },

    # ═══ PRJ OPERATION — Cognitive Loop ═══
    {
        "id": "wf_prj_problem",
        "name": "PrjProblem",
        "node_type": "action",
        "domain": "workflow",
        "payload": "PROBLEM: A new folder is needed for a domain. The folder must exist before any code or config can be placed in it.",
        "category": "prj",
    },
    {
        "id": "wf_prj_question",
        "name": "PrjQuestion",
        "node_type": "question",
        "domain": "workflow",
        "payload": "QUESTION: What is the domain name and where should the folder be created? params: {domain, base}",
        "category": "prj",
    },
    {
        "id": "wf_prj_answer",
        "name": "PrjAnswer",
        "node_type": "action",
        "domain": "workflow",
        "payload": "ANSWER: Run Dom_workflow.Run('prj', {action:'create', folder:base/domain, name:domain}) → creates folder, sets state",
        "category": "prj",
    },
    {
        "id": "wf_prj_constraint",
        "name": "PrjConstraint",
        "node_type": "check",
        "domain": "workflow",
        "payload": "CONSTRAINT: Folder must exist after creation. Check: os.path.isdir(folder). Folder name must be lowercase, single word or snake_case.",
        "category": "prj",
    },
    {
        "id": "wf_prj_mistake",
        "name": "PrjMistake",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "MISTAKE: Folder creation failed — permission denied or path too long or invalid characters. Recovery: try /tmp/ as base, or sanitize domain name.",
        "category": "prj",
    },
    {
        "id": "wf_prj_solution",
        "name": "PrjSolution",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "SOLUTION: If permission denied → use /tmp/domain. If invalid chars → replace spaces with underscores. If exists → proceed (not an error).",
        "category": "prj",
    },
    {
        "id": "wf_prj_verify",
        "name": "PrjVerify",
        "node_type": "check",
        "domain": "workflow",
        "payload": "VERIFY: os.path.isdir(folder) == True. state['folder'] is set. state['project_name'] is set. Return Tuple3(1, {folder, name}, None).",
        "category": "prj",
    },

    # ═══ INDEX OPERATION — Cognitive Loop ═══
    {
        "id": "wf_idx_problem",
        "name": "IndexProblem",
        "node_type": "action",
        "domain": "workflow",
        "payload": "PROBLEM: Need to know what files exist in the folder and extract their structure (classes, methods, VBStyle, BCL) as BCL entries.",
        "category": "index",
    },
    {
        "id": "wf_idx_question",
        "name": "IndexQuestion",
        "node_type": "question",
        "domain": "workflow",
        "payload": "QUESTION: Which folder to scan? params: {folder}. Are there .py files? Non-.py files?",
        "category": "index",
    },
    {
        "id": "wf_idx_answer",
        "name": "IndexAnswer",
        "node_type": "action",
        "domain": "workflow",
        "payload": "ANSWER: Run Dom_workflow.Run('index', {folder}) → scans all .py files with AST, scans non-.py files, generates BCL entries with 15 fields each.",
        "category": "index",
    },
    {
        "id": "wf_idx_constraint",
        "name": "IndexConstraint",
        "node_type": "check",
        "domain": "workflow",
        "payload": "CONSTRAINT: Every BCL entry must have 15 fields: file, purpose, classes, methods, functions, vbstyle, vbstyle_passed, vbstyle_total, vbstyle_failed, bcl, bcl_headers, created, modified, size, lines. Every entry must have created and modified dates.",
        "category": "index",
    },
    {
        "id": "wf_idx_mistake",
        "name": "IndexMistake",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "MISTAKE: AST parse failed (syntax error in .py file). Recovery: fall back to regex parsing. If regex fails too, record error in state['errors'] and skip file.",
        "category": "index",
    },
    {
        "id": "wf_idx_solution",
        "name": "IndexSolution",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "SOLUTION: Use _regex_parse() as fallback. If file is empty or unreadable, generate a minimal BCL entry with just filename and size=0.",
        "category": "index",
    },
    {
        "id": "wf_idx_verify",
        "name": "IndexVerify",
        "node_type": "check",
        "domain": "workflow",
        "payload": "VERIFY: len(state['files']) > 0. Each entry is a valid BCL token starting with [@File:. Each entry has created and modified dates. Return Tuple3(1, entries, None).",
        "category": "index",
    },

    # ═══ CONFIG OPERATION — Cognitive Loop ═══
    {
        "id": "wf_cfg_problem",
        "name": "ConfigProblem",
        "node_type": "action",
        "domain": "workflow",
        "payload": "PROBLEM: The folder needs a Config.py based on the gold standard, with a BCL FILE_INDEX listing every file.",
        "category": "config",
    },
    {
        "id": "wf_cfg_question",
        "name": "ConfigQuestion",
        "node_type": "question",
        "domain": "workflow",
        "payload": "QUESTION: Does Config.py already exist? If yes, replace FILE_INDEX. If no, create from template. params: {folder, domain, action:'full'}",
        "category": "config",
    },
    {
        "id": "wf_cfg_answer",
        "name": "ConfigAnswer",
        "node_type": "action",
        "domain": "workflow",
        "payload": "ANSWER: Run Dom_workflow.Run('config', {folder, domain, action:'full'}) → creates Config.py from gold standard template, scans files, appends BCL FILE_INDEX.",
        "category": "config",
    },
    {
        "id": "wf_cfg_constraint",
        "name": "ConfigConstraint",
        "node_type": "check",
        "domain": "workflow",
        "payload": "CONSTRAINT: Config.py MUST have: Ghost header, VBStyle header, FILE_INDEX (BCL format), config class with SQLite backend, env overrides, singleton. FILE_INDEX entries must be BCL tokens, not Python dicts.",
        "category": "config",
    },
    {
        "id": "wf_cfg_mistake",
        "name": "ConfigMistake",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "MISTAKE: Config.py write failed (permission denied). Or FILE_INDEX replacement failed (regex didn't match). Recovery: check permissions, use line-by-line replacement instead of regex.",
        "category": "config",
    },
    {
        "id": "wf_cfg_solution",
        "name": "ConfigSolution",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "SOLUTION: If permission denied → write to /tmp first, then copy. If regex fails → use line-by-line scan to find FILE_INDEX block boundaries. If template f-string fails → escape braces.",
        "category": "config",
    },
    {
        "id": "wf_cfg_verify",
        "name": "ConfigVerify",
        "node_type": "check",
        "domain": "workflow",
        "payload": "VERIFY: Config.py exists. Has FILE_INDEX. FILE_INDEX has entries. Each entry is BCL format. Config class exists. Singleton exists. Return Tuple3(1, {config_path, files_indexed}, None).",
        "category": "config",
    },

    # ═══ VALIDATE OPERATION — Cognitive Loop ═══
    {
        "id": "wf_val_problem",
        "name": "ValidateProblem",
        "node_type": "action",
        "domain": "workflow",
        "payload": "PROBLEM: Need to verify all .py files in the folder follow VBStyle rules (9 rules) before they can be used.",
        "category": "validate",
    },
    {
        "id": "wf_val_question",
        "name": "ValidateQuestion",
        "node_type": "question",
        "domain": "workflow",
        "payload": "QUESTION: Which files to validate? All .py files or a single file? params: {folder, file:optional}",
        "category": "validate",
    },
    {
        "id": "wf_val_answer",
        "name": "ValidateAnswer",
        "node_type": "action",
        "domain": "workflow",
        "payload": "ANSWER: Run Dom_workflow.Run('validate', {folder}) → checks 9 VBStyle rules on each .py file: ghost_header, vbstyle_header, tuple3_return, state_dict, run_dispatch, no_decorators, no_print, no_self_underscore, no_hardcoded_paths.",
        "category": "validate",
    },
    {
        "id": "wf_val_constraint",
        "name": "ValidateConstraint",
        "node_type": "check",
        "domain": "workflow",
        "payload": "CONSTRAINT: 9 rules must be checked. is_compliant = all 9 pass. failed_rules lists which failed. has_bcl checks for BCL headers. Results must be Tuple3.",
        "category": "validate",
    },
    {
        "id": "wf_val_mistake",
        "name": "ValidateMistake",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "MISTAKE: File not readable (encoding error). Recovery: use errors='replace' when reading. If file is binary, skip and log error.",
        "category": "validate",
    },
    {
        "id": "wf_val_solution",
        "name": "ValidateSolution",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "SOLUTION: If encoding error → open with errors='replace'. If binary file → skip. If empty file → mark as not compliant with 0/9 rules.",
        "category": "validate",
    },
    {
        "id": "wf_val_verify",
        "name": "ValidateVerify",
        "node_type": "check",
        "domain": "workflow",
        "payload": "VERIFY: Results dict has total, passed, failed, details. Each detail has file, is_compliant, rules_passed, rules_total, failed_rules. Return Tuple3(1, results, None).",
        "category": "validate",
    },

    # ═══ REPORT OPERATION — Cognitive Loop ═══
    {
        "id": "wf_rep_problem",
        "name": "ReportProblem",
        "node_type": "action",
        "domain": "workflow",
        "payload": "PROBLEM: Need a summary of the folder state — what files exist, VBStyle compliance, BCL coverage, errors.",
        "category": "report",
    },
    {
        "id": "wf_rep_question",
        "name": "ReportQuestion",
        "node_type": "question",
        "domain": "workflow",
        "payload": "QUESTION: What format? text (table), bcl (raw BCL tokens), or summary (counts only)? params: {folder, format}",
        "category": "report",
    },
    {
        "id": "wf_rep_answer",
        "name": "ReportAnswer",
        "node_type": "action",
        "domain": "workflow",
        "payload": "ANSWER: Run Dom_workflow.Run('report', {folder, format}) → generates report. text: table with file/lines/vbstyle/bcl/purpose. bcl: raw BCL entries. summary: counts only.",
        "category": "report",
    },
    {
        "id": "wf_rep_constraint",
        "name": "ReportConstraint",
        "node_type": "check",
        "domain": "workflow",
        "payload": "CONSTRAINT: Report must include: total files, VBStyle compliant count, BCL coverage count, total lines, errors. If format=text, must be aligned table. If format=bcl, must be raw BCL tokens.",
        "category": "report",
    },
    {
        "id": "wf_rep_mistake",
        "name": "ReportMistake",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "MISTAKE: No files indexed yet (state['files'] is empty). Recovery: run Index first, then generate report.",
        "category": "report",
    },
    {
        "id": "wf_rep_solution",
        "name": "ReportSolution",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "SOLUTION: If state['files'] is empty → call Index({folder}) first. If folder doesn't exist → return error. If format unknown → default to text.",
        "category": "report",
    },
    {
        "id": "wf_rep_verify",
        "name": "ReportVerify",
        "node_type": "check",
        "domain": "workflow",
        "payload": "VERIFY: Report is a string. Contains file count. Contains VBStyle count. Contains BCL count. Return Tuple3(1, report_string, None).",
        "category": "report",
    },

    # ═══ TERMINAL NODES ═══
    {
        "id": "wf_success",
        "name": "WorkflowComplete",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "SUCCESS: Workflow operation completed. Log to execution_log. Return to wf_root for next operation or exit.",
        "category": "terminal",
    },
    {
        "id": "wf_failed",
        "name": "WorkflowFailed",
        "node_type": "fallback",
        "domain": "workflow",
        "payload": "FAILED: Workflow operation could not complete after all recovery attempts. Log error. Report what failed and what was tried.",
        "category": "terminal",
    },
]

# ════════════════════════════════════════════════════════════════════════
# EDGES — connect the cognitive loop steps
# Each operation: problem → question → answer → constraint → verify
#                 constraint fail → mistake → solution → answer (retry)
#                 verify pass → success
#                 verify fail → mistake
# ════════════════════════════════════════════════════════════════════════

WORKFLOW_EDGES = [
    # Root → operations
    {"from": "wf_root", "to": "wf_prj_problem", "condition": "prj"},
    {"from": "wf_root", "to": "wf_idx_problem", "condition": "index"},
    {"from": "wf_root", "to": "wf_cfg_problem", "condition": "config"},
    {"from": "wf_root", "to": "wf_val_problem", "condition": "validate"},
    {"from": "wf_root", "to": "wf_rep_problem", "condition": "report"},

    # PRJ loop
    {"from": "wf_prj_problem", "to": "wf_prj_question", "condition": "success"},
    {"from": "wf_prj_question", "to": "wf_prj_answer", "condition": "answered"},
    {"from": "wf_prj_answer", "to": "wf_prj_constraint", "condition": "success"},
    {"from": "wf_prj_answer", "to": "wf_prj_mistake", "condition": "fail"},
    {"from": "wf_prj_constraint", "to": "wf_prj_verify", "condition": "pass"},
    {"from": "wf_prj_constraint", "to": "wf_prj_mistake", "condition": "fail"},
    {"from": "wf_prj_mistake", "to": "wf_prj_solution", "condition": "fail"},
    {"from": "wf_prj_solution", "to": "wf_prj_answer", "condition": "retry"},
    {"from": "wf_prj_solution", "to": "wf_failed", "condition": "unrecoverable"},
    {"from": "wf_prj_verify", "to": "wf_success", "condition": "pass"},
    {"from": "wf_prj_verify", "to": "wf_prj_mistake", "condition": "fail"},

    # INDEX loop
    {"from": "wf_idx_problem", "to": "wf_idx_question", "condition": "success"},
    {"from": "wf_idx_question", "to": "wf_idx_answer", "condition": "answered"},
    {"from": "wf_idx_answer", "to": "wf_idx_constraint", "condition": "success"},
    {"from": "wf_idx_answer", "to": "wf_idx_mistake", "condition": "fail"},
    {"from": "wf_idx_constraint", "to": "wf_idx_verify", "condition": "pass"},
    {"from": "wf_idx_constraint", "to": "wf_idx_mistake", "condition": "fail"},
    {"from": "wf_idx_mistake", "to": "wf_idx_solution", "condition": "fail"},
    {"from": "wf_idx_solution", "to": "wf_idx_answer", "condition": "retry"},
    {"from": "wf_idx_solution", "to": "wf_failed", "condition": "unrecoverable"},
    {"from": "wf_idx_verify", "to": "wf_success", "condition": "pass"},
    {"from": "wf_idx_verify", "to": "wf_idx_mistake", "condition": "fail"},

    # CONFIG loop
    {"from": "wf_cfg_problem", "to": "wf_cfg_question", "condition": "success"},
    {"from": "wf_cfg_question", "to": "wf_cfg_answer", "condition": "answered"},
    {"from": "wf_cfg_answer", "to": "wf_cfg_constraint", "condition": "success"},
    {"from": "wf_cfg_answer", "to": "wf_cfg_mistake", "condition": "fail"},
    {"from": "wf_cfg_constraint", "to": "wf_cfg_verify", "condition": "pass"},
    {"from": "wf_cfg_constraint", "to": "wf_cfg_mistake", "condition": "fail"},
    {"from": "wf_cfg_mistake", "to": "wf_cfg_solution", "condition": "fail"},
    {"from": "wf_cfg_solution", "to": "wf_cfg_answer", "condition": "retry"},
    {"from": "wf_cfg_solution", "to": "wf_failed", "condition": "unrecoverable"},
    {"from": "wf_cfg_verify", "to": "wf_success", "condition": "pass"},
    {"from": "wf_cfg_verify", "to": "wf_cfg_mistake", "condition": "fail"},

    # VALIDATE loop
    {"from": "wf_val_problem", "to": "wf_val_question", "condition": "success"},
    {"from": "wf_val_question", "to": "wf_val_answer", "condition": "answered"},
    {"from": "wf_val_answer", "to": "wf_val_constraint", "condition": "success"},
    {"from": "wf_val_answer", "to": "wf_val_mistake", "condition": "fail"},
    {"from": "wf_val_constraint", "to": "wf_val_verify", "condition": "pass"},
    {"from": "wf_val_constraint", "to": "wf_val_mistake", "condition": "fail"},
    {"from": "wf_val_mistake", "to": "wf_val_solution", "condition": "fail"},
    {"from": "wf_val_solution", "to": "wf_val_answer", "condition": "retry"},
    {"from": "wf_val_solution", "to": "wf_failed", "condition": "unrecoverable"},
    {"from": "wf_val_verify", "to": "wf_success", "condition": "pass"},
    {"from": "wf_val_verify", "to": "wf_val_mistake", "condition": "fail"},

    # REPORT loop
    {"from": "wf_rep_problem", "to": "wf_rep_question", "condition": "success"},
    {"from": "wf_rep_question", "to": "wf_rep_answer", "condition": "answered"},
    {"from": "wf_rep_answer", "to": "wf_rep_constraint", "condition": "success"},
    {"from": "wf_rep_answer", "to": "wf_rep_mistake", "condition": "fail"},
    {"from": "wf_rep_constraint", "to": "wf_rep_verify", "condition": "pass"},
    {"from": "wf_rep_constraint", "to": "wf_rep_mistake", "condition": "fail"},
    {"from": "wf_rep_mistake", "to": "wf_rep_solution", "condition": "fail"},
    {"from": "wf_rep_solution", "to": "wf_rep_answer", "condition": "retry"},
    {"from": "wf_rep_solution", "to": "wf_failed", "condition": "unrecoverable"},
    {"from": "wf_rep_verify", "to": "wf_success", "condition": "pass"},
    {"from": "wf_rep_verify", "to": "wf_rep_mistake", "condition": "fail"},

    # Success → back to root (for next operation)
    {"from": "wf_success", "to": "wf_root", "condition": "success"},
]


def main():
    print("=" * 60)
    print("ADDING COGNITIVE LOOP FOR WORKFLOW DOMAIN")
    print("Problem → Question → Answer → Constraint → Mistake → Solution → Verify")
    print("=" * 60)

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Check schema — do we have a domain column in decision_nodes?
    c.execute("PRAGMA table_info(decision_nodes)")
    columns = [r[1] for r in c.fetchall()]
    has_domain = 'domain' in columns
    has_category = 'category' in columns

    print(f"\n  decision_nodes columns: {columns}")
    print(f"  Has domain column: {has_domain}")
    print(f"  Has category column: {has_category}")

    # Add domain column if missing
    if not has_domain:
        c.execute("ALTER TABLE decision_nodes ADD COLUMN domain TEXT DEFAULT ''")
        print("  Added 'domain' column to decision_nodes")
    if not has_category:
        c.execute("ALTER TABLE decision_nodes ADD COLUMN category TEXT DEFAULT ''")
        print("  Added 'category' column to decision_nodes")

    # Clear existing workflow nodes (in case of re-run)
    c.execute("DELETE FROM decision_nodes WHERE domain='workflow'")
    c.execute("DELETE FROM decision_edges WHERE from_node LIKE 'wf_%' OR to_node LIKE 'wf_%'")

    # Insert nodes
    print(f"\n[1] Inserting {len(WORKFLOW_NODES)} cognitive loop nodes...")
    for node in WORKFLOW_NODES:
        c.execute("""
            INSERT INTO decision_nodes (name, node_type, domain, payload, category)
            VALUES (?, ?, ?, ?, ?)
        """, (node["name"], node["node_type"], node["domain"],
              node["payload"], node["category"]))

    # Get node IDs (they were auto-generated) — map our internal IDs to DB node_ids
    c.execute("SELECT node_id, name, node_type, domain, category FROM decision_nodes WHERE domain='workflow' ORDER BY node_id")
    db_nodes = c.fetchall()
    print("\n  Nodes inserted:")
    for r in db_nodes:
        print(f"    {r[0]:3} {r[1]:25} type={r[2]:10} cat={r[4]}")

    # Build node_map: our internal ID (e.g. "wf_root") → DB node_id
    # Match by name: "WorkflowDomain" → "wf_root"
    name_to_internal = {n["name"]: n["id"] for n in WORKFLOW_NODES}
    node_map = {}
    for db_id, name, ntype, domain, cat in db_nodes:
        internal_id = name_to_internal.get(name)
        if internal_id:
            node_map[internal_id] = db_id

    print(f"\n  Node map: {len(node_map)} of {len(WORKFLOW_NODES)} nodes mapped")

    # Insert edges
    print(f"\n[2] Inserting {len(WORKFLOW_EDGES)} cognitive loop edges...")
    inserted = 0
    for edge in WORKFLOW_EDGES:
        from_id = node_map.get(edge["from"])
        to_id = node_map.get(edge["to"])
        if from_id and to_id:
            c.execute("""
                INSERT INTO decision_edges (from_node, to_node, condition, weight)
                VALUES (?, ?, ?, 1.0)
            """, (from_id, to_id, edge["condition"]))
            inserted += 1
        else:
            print(f"    WARNING: edge {edge['from']}→{edge['to']} — node not found!")

    print(f"    Inserted {inserted} edges")

    # Show the cognitive loops
    print(f"\n[3] Cognitive loops for workflow domain:")
    operations = ["prj", "idx", "cfg", "val", "rep"]
    for op in operations:
        print(f"\n  {op.upper()} loop:")
        c.execute("""SELECT n.name, n.node_type, n.payload, e.condition, n2.name as next_name
                     FROM decision_nodes n
                     LEFT JOIN decision_edges e ON n.node_id = e.from_node
                     LEFT JOIN decision_nodes n2 ON e.to_node = n2.node_id
                     WHERE n.domain='workflow' AND n.category=?
                     ORDER BY n.node_id, e.weight DESC""", (op,))
        for r in c.fetchall():
            payload_short = r[2][:60] if r[2] else ""
            next_name = r[4] if r[4] else "(none)"
            condition = r[3] if r[3] else ""
            print(f"    {r[0]:25} [{r[1]:10}] → {next_name:25} ({condition})")
            print(f"      {payload_short}")

    # Summary
    c.execute("SELECT COUNT(*) FROM decision_nodes WHERE domain='workflow'")
    wf_nodes = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM decision_edges WHERE from_node IN (SELECT node_id FROM decision_nodes WHERE domain='workflow')")
    wf_edges = c.fetchone()[0]
    c.execute("SELECT node_type, COUNT(*) FROM decision_nodes WHERE domain='workflow' GROUP BY node_type")
    type_counts = c.fetchall()

    conn.commit()
    conn.close()

    print(f"\n{'=' * 60}")
    print("COGNITIVE LOOP ADDED TO DB")
    print(f"{'=' * 60}")
    print(f"""
  Workflow domain now has:
    {wf_nodes} decision nodes (cognitive loop steps)
    {wf_edges} decision edges (transitions between steps)

  Node types:
    {type_counts}

  Each operation (prj, index, config, validate, report) has:
    Problem    → what needs to be done
    Question   → what params are needed
    Answer     → how to do it (calls Dom_workflow.Run)
    Constraint → what rules must be satisfied
    Mistake    → what can go wrong
    Solution   → how to recover
    Verify     → how to check it worked

  The DecisionEngine can now walk this graph to guide
  any AI through workflow operations — with recovery paths
  for every possible failure.
""")


if __name__ == "__main__":
    main()
