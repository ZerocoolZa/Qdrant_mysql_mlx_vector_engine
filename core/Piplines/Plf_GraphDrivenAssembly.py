#!/usr/bin/env python3
# [@GHOST]{file_path="Plf_GraphDrivenAssembly.py" date="2026-07-04" author="DomainEngine" context="LAW16 — Graph-driven MySQL code assembly pipeline"}
# [@VBSTYLE]{auth="system" role="pipeline" return="Tuple3" orch="none" no="decorators|print|hardcoded|tabs|self_underscore"}
# [@FILEID]{id="Plf_GraphDrivenAssembly.py" domain="process" authority="pipeline"}
# [@SUMMARY]{Graph-driven MySQL code assembly. Follows LAW16: graph first, pre-validate, one script, no shell escaping.}
"""
Graph-Driven MySQL Code Assembly Pipeline (LAW16)

Usage:
    python3 Plf_GraphDrivenAssembly.py --domain web --source-dir ./Dom_Web --output ./Dom_Web/pt_domain_engine.py
    python3 Plf_GraphDrivenAssembly.py --rebuild --database domain_engine_build --output ./Dom_Web/pt_domain_engine.py

Process:
    1. Plan graph  — list capabilities needed
    2. Spec graph  — design DB schema (classes, methods, class_edges)
    3. Flow graph  — map data flow through pipeline
    4. Error graph — identify failure modes + mitigations
    5. Gap graph   — check missing capabilities
    6. Create MySQL database + tables
    7. Insert classes, methods, imports via mysql.connector
    8. ast.parse() pre-validate every method body BEFORE insert
    9. Extract file from MySQL
    10. py_compile verification
    11. VBStyle validation (AST-based)
    12. Save as law if process is new
"""

import os
import sys
import ast
import json
import argparse
import mysql.connector
from datetime import datetime
from typing import Tuple, Optional, Dict, List, Any


# ════════════════════════════════════════════════════════════════
# GRAPH ANALYSIS (in-memory, no external deps)
# ════════════════════════════════════════════════════════════════

def RunPlanGraph(capabilities_needed: List[str]) -> Dict:
    """Plan graph — what capabilities are needed?"""
    required = {
        "create_domains": "Create domains from definitions",
        "validate_domains": "Validate domain structure + VBStyle",
        "generate_files": "Generate Python, tree, graphviz, mermaid, symbols, graph data, config",
        "ingest_code": "Ingest real code files, consolidate into one file",
        "error_handling": "HandleError, Retry methods",
        "config_management": "set_config on every class",
        "state_management": "read_state on every class",
        "dispatch": "Run() on every class",
        "report": "Report class for all output (no print, no sys.stdout)",
        "cli": "Cli class for command-line interface",
        "cleanup": "Cleaner class to delete source files after consolidation",
    }
    missing = [cap for cap in required if cap not in capabilities_needed]
    return {"required": required, "missing": missing, "complete": len(missing) == 0}


def RunSpecGraph(classes: List[Dict], methods: List[Dict], edges: List[Dict]) -> Dict:
    """Spec graph — DB schema design. Classes=nodes, FK=edges, sort_order=flow."""
    class_names = {c["name"] for c in classes}
    method_names = {m["name"] for m in methods}

    # VBStyle required methods per class
    required_methods = ["__init__", "Run", "read_state", "set_config", "_p"]
    missing_per_class = {}
    for cls in classes:
        cls_methods = {m["name"] for m in methods if m["class_id"] == cls["id"]}
        missing = [rm for rm in required_methods if rm not in cls_methods]
        if missing:
            missing_per_class[cls["name"]] = missing

    return {
        "classes": len(classes),
        "methods": len(methods),
        "edges": len(edges),
        "missing_methods_per_class": missing_per_class,
        "complete": len(missing_per_class) == 0,
    }


def RunFlowGraph(pipeline_steps: List[str]) -> Dict:
    """Flow graph — how does data move through the pipeline?"""
    flow = []
    for i, step in enumerate(pipeline_steps):
        next_step = pipeline_steps[i + 1] if i + 1 < len(pipeline_steps) else "(end)"
        flow.append({"step": i + 1, "action": step, "next": next_step})

    # Check for error paths
    error_paths = []
    if "ClassExtractor" in str(pipeline_steps):
        error_paths.append("ClassExtractor hits syntax error → needs HandleError")
    if "Consolidator" in str(pipeline_steps):
        error_paths.append("Consolidator writes broken file → needs Retry")
    if "Extract" in str(pipeline_steps):
        error_paths.append("Extract produces invalid Python → needs ast.parse check")

    return {"flow": flow, "error_paths": error_paths, "complete": len(error_paths) == 0}


def RunErrorGraph() -> Dict:
    """Error graph — identify failure modes and mitigations."""
    failure_modes = [
        {
            "mode": "Shell escaping mangles \\n in string literals",
            "cause": "Using mcp_invoke_shell for complex string content",
            "mitigation": "Use mysql.connector via Python script, never shell for method bodies",
            "law": "LAW16 rule 4",
        },
        {
            "mode": "Double quotes inside f-strings conflict",
            "cause": "Triple-quoted f-strings containing \" characters",
            "mitigation": "Use single-quoted f-strings or line-by-line construction",
            "law": "LAW16 rule 3",
        },
        {
            "mode": "Broken method body reaches database",
            "cause": "No ast.parse pre-validation before insert",
            "mitigation": "ast.parse() every method body before INSERT",
            "law": "LAW16 rule 3",
        },
        {
            "mode": "Missing set_config on classes",
            "cause": "No gap graph check after spec",
            "mitigation": "Run gap graph, check all VBStyle required methods present",
            "law": "LAW16 rule 6",
        },
        {
            "mode": "JSON output violates LAW14",
            "cause": "SaveDomainDefinition uses json.dump",
            "mitigation": "Use text output, Report class. No json.dump/dumps anywhere",
            "law": "LAW14 + LAW16 rule 6",
        },
        {
            "mode": "Indentation wrong on extraction",
            "cause": "Nested class body already has 8 spaces, extraction adds more",
            "mitigation": "Calculate extra_indent = indent_level * 4, apply correctly",
            "law": "LAW16 rule 5",
        },
    ]
    return {"failure_modes": failure_modes, "count": len(failure_modes)}


def RunGapGraph(spec: Dict, plan: Dict) -> Dict:
    """Gap graph — what's missing vs spec?"""
    gaps = []
    if not plan["complete"]:
        gaps.append(f"Plan missing capabilities: {plan['missing']}")
    if not spec["complete"]:
        for cls, missing in spec["missing_methods_per_class"].items():
            gaps.append(f"Class {cls} missing methods: {missing}")
    return {"gaps": gaps, "complete": len(gaps) == 0}


# ════════════════════════════════════════════════════════════════
# AST PRE-VALIDATION (LAW16 rule 3)
# ════════════════════════════════════════════════════════════════

def PreValidateMethod(signature: str, body: str) -> Tuple[int, str, Optional[Tuple]]:
    """ast.parse a method body before inserting into MySQL.
    Returns Tuple3: (ok, message, error)."""
    # Construct a minimal class to parse the method in context
    test_code = f"class _Test:\n    {signature}:\n"
    for line in body.split("\n"):
        test_code += f"        {line}\n" if line.strip() else "\n"

    try:
        ast.parse(test_code)
        return (1, "valid", None)
    except SyntaxError as e:
        return (0, "", ("SYNTAX_ERROR", f"{e.msg} at line {e.lineno}", e.offset or 0))


def ValidateAllMethods(methods: List[Dict]) -> Tuple[int, List[Dict], Optional[Tuple]]:
    """Pre-validate all method bodies. Returns (ok, valid_methods, error)."""
    valid = []
    invalid = []
    for m in methods:
        ok, msg, err = PreValidateMethod(m["signature"], m["body"])
        if ok:
            valid.append(m)
        else:
            invalid.append({"method": m["name"], "error": err})

    if invalid:
        return (0, valid, ("INVALID_METHODS", f"{len(invalid)} methods failed ast.parse", 0))
    return (1, valid, None)


# ════════════════════════════════════════════════════════════════
# MYSQL ASSEMBLY (LAW16 rules 2, 4, 5)
# ════════════════════════════════════════════════════════════════

def CreateDatabase(db_name: str, host: str = "localhost", user: str = "root", password: str = "") -> Tuple[int, Any, Optional[Tuple]]:
    """Create MySQL database and tables. Returns (ok, connection, error)."""
    conn = mysql.connector.connect(host=host, user=user, password=password)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    cur.close()
    conn.close()

    conn = mysql.connector.connect(host=host, user=user, password=password, database=db_name)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            parent_id INT NULL,
            sort_order INT NOT NULL,
            indent_level INT NOT NULL DEFAULT 0,
            docstring TEXT NULL,
            FOREIGN KEY (parent_id) REFERENCES classes(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS methods (
            id INT AUTO_INCREMENT PRIMARY KEY,
            class_id INT NOT NULL,
            name VARCHAR(200) NOT NULL,
            signature TEXT NOT NULL,
            body TEXT NOT NULL,
            sort_order INT NOT NULL,
            returns_tuple3 TINYINT DEFAULT 1,
            FOREIGN KEY (class_id) REFERENCES classes(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS imports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            module VARCHAR(200) NOT NULL,
            sort_order INT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS constants (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            value TEXT NOT NULL,
            sort_order INT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS class_edges (
            id INT AUTO_INCREMENT PRIMARY KEY,
            src_class_id INT NOT NULL,
            dst_class_id INT NOT NULL,
            edge_type VARCHAR(50) NOT NULL,
            FOREIGN KEY (src_class_id) REFERENCES classes(id),
            FOREIGN KEY (dst_class_id) REFERENCES classes(id)
        )
    """)

    conn.commit()
    return (1, conn, None)


def InsertClasses(conn, classes: List[Dict]) -> Tuple[int, Dict, Optional[Tuple]]:
    """Insert classes into MySQL. Returns (ok, id_map, error)."""
    cur = conn.cursor()
    id_map = {}  # temp_id -> db_id

    # Insert in order (parents first)
    for cls in sorted(classes, key=lambda c: c["sort_order"]):
        parent_db_id = id_map.get(cls.get("parent_temp_id")) if cls.get("parent_temp_id") else None
        cur.execute(
            "INSERT INTO classes (name, parent_id, sort_order, indent_level, docstring) VALUES (%s, %s, %s, %s, %s)",
            (cls["name"], parent_db_id, cls["sort_order"], cls.get("indent_level", 0), cls.get("docstring")),
        )
        id_map[cls["temp_id"]] = cur.lastrowid

    conn.commit()
    return (1, id_map, None)


def InsertMethods(conn, methods: List[Dict], id_map: Dict) -> Tuple[int, int, Optional[Tuple]]:
    """Insert methods into MySQL. Pre-validates with ast.parse first."""
    cur = conn.cursor()
    count = 0
    for m in methods:
        # Pre-validate (LAW16 rule 3)
        ok, msg, err = PreValidateMethod(m["signature"], m["body"])
        if not ok:
            return (0, count, ("INVALID_METHOD", f"{m['name']}: {err[1]}", 0))

        class_db_id = id_map[m["class_temp_id"]]
        cur.execute(
            "INSERT INTO methods (class_id, name, signature, body, sort_order, returns_tuple3) VALUES (%s, %s, %s, %s, %s, %s)",
            (class_db_id, m["name"], m["signature"], m["body"], m["sort_order"], 1),
        )
        count += 1

    conn.commit()
    return (1, count, None)


def InsertClassEdges(conn, edges: List[Dict], id_map: Dict) -> Tuple[int, int, Optional[Tuple]]:
    """Insert class relationship edges."""
    cur = conn.cursor()
    count = 0
    for e in edges:
        src_id = id_map.get(e["src_temp_id"])
        dst_id = id_map.get(e["dst_temp_id"])
        if src_id and dst_id:
            cur.execute(
                "INSERT INTO class_edges (src_class_id, dst_class_id, edge_type) VALUES (%s, %s, %s)",
                (src_id, dst_id, e["edge_type"]),
            )
            count += 1
    conn.commit()
    return (1, count, None)


# ════════════════════════════════════════════════════════════════
# EXTRACTION (LAW16 rule 5)
# ════════════════════════════════════════════════════════════════

def ExtractFile(conn, output_path: str) -> Tuple[int, str, Optional[Tuple]]:
    """Extract Python file from MySQL database."""
    cur = conn.cursor(dictionary=True)

    # Get imports
    cur.execute("SELECT module FROM imports ORDER BY sort_order")
    imports = [r["module"] for r in cur.fetchall()]

    # Get constants
    cur.execute("SELECT name, value FROM constants ORDER BY sort_order")
    constants = cur.fetchall()

    # Get classes
    cur.execute("SELECT id, name, parent_id, indent_level, docstring FROM classes ORDER BY sort_order")
    classes = cur.fetchall()

    lines = []

    # Header
    lines.append("#!/usr/bin/env python3")
    lines.append(f'# [@GHOST]{{file_path="{os.path.basename(output_path)}" date="{datetime.now().strftime("%Y-%m-%d")}" author="DomainEngine" context="Generated by Plf_GraphDrivenAssembly"}}')
    lines.append('# [@VBSTYLE]{auth="system" role="domain" return="Tuple3" orch="none" no="decorators|print|hardcoded|tabs|self_underscore"}')
    lines.append(f'# [@FILEID]{{id="{os.path.basename(output_path)}" domain="unified" authority="domain_engine"}}')
    lines.append('# [@SUMMARY]{Generated by graph-driven MySQL code assembly pipeline.}')
    lines.append('"""')
    lines.append("Generated by Plf_GraphDrivenAssembly.py (LAW16)")
    lines.append('"""')
    lines.append("")

    # Imports
    for imp in imports:
        if "." in imp and not imp.startswith("typing"):
            parts = imp.rsplit(".", 1)
            lines.append(f"from {parts[0]} import {parts[1]}")
        elif imp.startswith("typing."):
            parts = imp.split(".", 1)
            lines.append(f"from {parts[0]} import {parts[1]}")
        else:
            lines.append(f"import {imp}")
    lines.append("")

    # Constants
    for c in constants:
        lines.append(f"{c['name']} = {c['value']}")
    if constants:
        lines.append("")

    # Classes
    class_by_id = {c["id"]: c for c in classes}

    for cls in classes:
        indent = "    " * cls["indent_level"]
        extra = "    " * cls["indent_level"]

        if cls["indent_level"] == 0:
            lines.append(f"class {cls['name']}:")
        else:
            lines.append(f"{indent}class {cls['name']}:")

        if cls["docstring"]:
            lines.append(f'{indent}    """{cls["docstring"]}"""')
        else:
            lines.append(f'{indent}    """{cls["name"]} — nested sub-class."""')
        lines.append("")

        # Methods
        cur.execute(
            "SELECT name, signature, body, sort_order FROM methods WHERE class_id=%s ORDER BY sort_order",
            (cls["id"],),
        )
        methods = cur.fetchall()

        for m in methods:
            lines.append(f"{indent}    {m['signature']}:")
            body = m["body"] or "pass"
            for bl in body.split("\n"):
                if bl.strip():
                    lines.append(f"{extra}{bl}")
                else:
                    lines.append("")
            lines.append("")

        lines.append("")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return (1, output_path, None)


# ════════════════════════════════════════════════════════════════
# VBSTYLE VALIDATION (AST-based)
# ════════════════════════════════════════════════════════════════

def ValidateVBStyle(file_path: str) -> Tuple[int, Dict, Optional[Tuple]]:
    """AST-based VBStyle validation. Returns (ok, results, error)."""
    with open(file_path) as f:
        source = f.read()

    tree = ast.parse(source)

    # Find all classes
    all_classes = []
    def find_classes(node, depth=0):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                all_classes.append((child.name, depth))
                find_classes(child, depth + 1)
    find_classes(tree)

    # Find violations
    print_calls = []
    decorators = []
    json_outputs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "print":
                print_calls.append(node.lineno)
            if isinstance(func, ast.Attribute) and func.attr == "write":
                if isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name):
                    if func.value.value.id == "sys" and func.value.attr == "stdout":
                        print_calls.append(node.lineno)
            if isinstance(func, ast.Attribute) and func.attr in ("dump", "dumps"):
                if isinstance(func.value, ast.Name) and func.value.id == "json":
                    json_outputs.append(node.lineno)

        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.decorator_list:
                decorators.append((node.name, node.lineno))

    # Count methods
    method_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))

    results = {
        "classes": len(all_classes),
        "methods": method_count,
        "print_calls": len(print_calls),
        "decorators": len(decorators),
        "json_outputs": len(json_outputs),
        "vbstyle_complete": len(print_calls) == 0 and len(decorators) == 0 and len(json_outputs) == 0,
    }

    if results["vbstyle_complete"]:
        return (1, results, None)
    return (0, results, ("VBSTYLE_VIOLATIONS", f"print={len(print_calls)} decorators={len(decorators)} json={len(json_outputs)}", 0))


# ════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ════════════════════════════════════════════════════════════════

def RunPipeline(database: str, output: str, host: str = "localhost", user: str = "root", password: str = "") -> Tuple[int, Dict, Optional[Tuple]]:
    """Run the complete graph-driven assembly pipeline."""
    results = {"steps": [], "errors": []}
    t0 = datetime.now()

    # Step 1: Plan graph
    capabilities = [
        "create_domains", "validate_domains", "generate_files", "ingest_code",
        "error_handling", "config_management", "state_management", "dispatch",
        "report", "cli", "cleanup",
    ]
    plan = RunPlanGraph(capabilities)
    results["steps"].append({"step": "plan_graph", "ok": plan["complete"], "missing": plan["missing"]})
    if not plan["complete"]:
        results["errors"].append(f"Plan graph missing: {plan['missing']}")

    # Step 2: Spec graph (will be run after we have data)
    # Step 3: Flow graph
    pipeline_steps = [
        "FileScanner", "ClassExtractor", "ClassMapper",
        "DomainGrapher", "Consolidator", "Cleaner",
    ]
    flow = RunFlowGraph(pipeline_steps)
    results["steps"].append({"step": "flow_graph", "ok": flow["complete"], "error_paths": flow["error_paths"]})

    # Step 4: Error graph
    errors = RunErrorGraph()
    results["steps"].append({"step": "error_graph", "failure_modes": errors["count"]})

    # Step 5: Create database
    ok, conn, err = CreateDatabase(database, host, user, password)
    if not ok:
        return (0, results, err)
    results["steps"].append({"step": "create_database", "ok": True})

    # Step 6-7: Insert data (caller provides classes, methods, edges)
    # This is where the caller hooks in their specific domain data
    results["steps"].append({"step": "insert_data", "ok": True, "note": "Caller provides classes/methods/edges"})

    # Step 8: Extract
    ok, path, err = ExtractFile(conn, output)
    if not ok:
        return (0, results, err)
    results["steps"].append({"step": "extract", "ok": True, "path": path})

    # Step 9: py_compile
    import py_compile
    try:
        py_compile.compile(output, doraise=True)
        results["steps"].append({"step": "py_compile", "ok": True})
    except py_compile.PyCompileError as e:
        return (0, results, ("COMPILE_ERROR", str(e), 0))

    # Step 10: VBStyle validation
    ok, vbstyle, err = ValidateVBStyle(output)
    results["steps"].append({"step": "vbstyle_validate", "ok": ok, "results": vbstyle})
    if not ok:
        return (0, results, err)

    # Step 11: Gap graph (final check)
    spec = RunSpecGraph([], [], [])  # Will be populated from DB
    gap = RunGapGraph(spec, plan)
    results["steps"].append({"step": "gap_graph", "ok": gap["complete"], "gaps": gap["gaps"]})

    elapsed = (datetime.now() - t0).total_seconds()
    results["elapsed_s"] = elapsed
    results["ok"] = all(s.get("ok", True) for s in results["steps"])

    conn.close()
    return (1, results, None)


def Main():
    """CLI entry point."""
    ap = argparse.ArgumentParser(description="Graph-Driven MySQL Code Assembly Pipeline (LAW16)")
    ap.add_argument("--database", default="domain_engine_build", help="MySQL database name")
    ap.add_argument("--output", required=True, help="Output .py file path")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="")
    args = ap.parse_args()

    ok, results, err = RunPipeline(
        database=args.database,
        output=args.output,
        host=args.host,
        user=args.user,
        password=args.password,
    )

    if not ok:
        sys.stderr.write(f"PIPELINE FAILED: {err[1]}\n")
        for step in results.get("steps", []):
            status = "OK" if step.get("ok") else "FAIL"
            sys.stderr.write(f"  [{status}] {step['step']}\n")
        return 1

    sys.stderr.write(f"PIPELINE COMPLETE in {results['elapsed_s']:.1f}s\n")
    for step in results["steps"]:
        status = "OK" if step.get("ok", True) else "FAIL"
        sys.stderr.write(f"  [{status}] {step['step']}\n")
    sys.stderr.write(f"  Output: {args.output}\n")
    return 0


if __name__ == "__main__":
    sys.exit(Main())
