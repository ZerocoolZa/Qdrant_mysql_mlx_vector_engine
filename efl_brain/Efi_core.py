#!/usr/bin/env python3
"""
EFL Brain — single entry point.

All code lives in efl_brain.db. This file just connects and dispatches.
No imports of other scripts. Everything runs from the database.

Usage:
  python3 efl.py build          — pull from MySQL + ingest all scripts + build units
  python3 efl.py graph          — build code graph
  python3 efl.py engine         — run graph engine (rank, hot paths, repair candidates)
  python3 efl.py query <domain> — query the graph for a domain
  python3 efl.py assemble <pat> — assemble a pipeline from proven units
  python3 efl.py trace <Cls.m>  — trace method dependencies
  python3 efl.py reuse <pat>    — find units matching a pattern
  python3 efl.py diff <domain>  — diff expected vs existing
  python3 efl.py diff_all       — diff all domains
  python3 efl.py plan <domain>  — implementation plan for gaps
  python3 efl.py status         — show database summary
  python3 efl.py exec <Cls.m>   — execute a method from the database
"""

import sqlite3
import os
import sys
import ast
import re
import hashlib
import mysql.connector
from collections import defaultdict, deque
from datetime import datetime

from Config_efl_brain import (
    DB_PATH, TARGET_CLASSES, ENGINE_SCRIPTS,
    MYSQL_CONFIG, PRAGMA_FOREIGN_KEYS,
    SCHEMA_ALL, SCHEMA_VIEWS, SCHEMA_INDEXES, SEED_ALL,
    SQL_CREATE_TEST_FEEDBACK, SQL_CREATE_EXECUTION_LOG,
    SQL_CREATE_LEARNED_FIXES, SQL_INSERT_FEEDBACK, SQL_CLEAR_FEEDBACK,
)

# ═══════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ═══════════════════════════════════════════════════════════════

def get_conn():
    return sqlite3.connect(DB_PATH)

# ═══════════════════════════════════════════════════════════════
# BUILD — pull everything into efl_brain.db
# ═══════════════════════════════════════════════════════════════

def init_schema(conn):
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS code_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            source_code TEXT,
            hash TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            domain TEXT,
            source TEXT DEFAULT 'mysql',
            class_code TEXT,
            description TEXT,
            method_count INTEGER DEFAULT 0,
            ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(class_name, source)
        );
        CREATE TABLE IF NOT EXISTS methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            method_name TEXT NOT NULL,
            params TEXT,
            method_code TEXT,
            is_dunder INTEGER DEFAULT 0,
            is_run INTEGER DEFAULT 0,
            is_init INTEGER DEFAULT 0,
            returns_tuple3 INTEGER DEFAULT 0,
            has_ast INTEGER DEFAULT 0,
            has_re INTEGER DEFAULT 0,
            has_try INTEGER DEFAULT 0,
            code_len INTEGER DEFAULT 0,
            line_start INTEGER,
            source TEXT DEFAULT 'mysql',
            ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_name TEXT NOT NULL,
            unit_type TEXT DEFAULT 'computational',
            class_name TEXT,
            method_ids TEXT,
            method_names TEXT,
            description TEXT,
            method_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS graph_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id INTEGER,
            class_name TEXT,
            method_name TEXT,
            node_type TEXT DEFAULT 'method',
            in_degree INTEGER DEFAULT 0,
            out_degree INTEGER DEFAULT 0,
            is_entry INTEGER DEFAULT 0,
            is_exit INTEGER DEFAULT 0,
            UNIQUE(class_name, method_name)
        );
        CREATE TABLE IF NOT EXISTS graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_class TEXT,
            source_method TEXT,
            target_class TEXT,
            target_method TEXT,
            edge_type TEXT DEFAULT 'call',
            source_method_id INTEGER,
            target_method_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS execution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER,
            method_id INTEGER,
            class_name TEXT,
            method_name TEXT,
            input_state TEXT,
            output_state TEXT,
            action_taken TEXT,
            success INTEGER,
            error_msg TEXT,
            reward REAL DEFAULT 0,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS unit_graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_unit_id INTEGER,
            target_unit_id INTEGER,
            source_unit_name TEXT,
            target_unit_name TEXT,
            edge_type TEXT,
            weight REAL DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS unit_rankings (
            unit_id INTEGER PRIMARY KEY,
            unit_name TEXT,
            connectivity REAL,
            reuse_frequency REAL,
            complexity REAL,
            execution_success REAL,
            overall_score REAL,
            rank INTEGER
        );
        CREATE TABLE IF NOT EXISTS expectation_graph (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            element_type TEXT NOT NULL,
            element_name TEXT NOT NULL,
            purpose TEXT,
            expected_returns TEXT,
            required_methods TEXT,
            edge_from TEXT,
            edge_to TEXT,
            edge_type TEXT,
            UNIQUE(domain, element_type, element_name)
        );
        CREATE TABLE IF NOT EXISTS diff_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            gap_type TEXT NOT NULL,
            element_name TEXT NOT NULL,
            purpose TEXT,
            existing_count INTEGER DEFAULT 0,
            existing_locations TEXT,
            status TEXT DEFAULT 'MISSING',
            suggested_action TEXT,
            priority TEXT DEFAULT 'medium',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_methods_class ON methods(class_id);
        CREATE INDEX IF NOT EXISTS idx_methods_name ON methods(method_name);
        CREATE INDEX IF NOT EXISTS idx_methods_class_name ON methods(class_name);
        CREATE INDEX IF NOT EXISTS idx_methods_source ON methods(source);
        CREATE INDEX IF NOT EXISTS idx_classes_source ON classes(source);
        CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges(source_class, source_method);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges(target_class, target_method);
    """)
    conn.commit()


def pull_mysql(conn):
    try:
        mysql_conn = mysql.connector.connect(user='root', host='localhost', port=3306, database='vb_code_test')
    except Exception as e:
        print(f"  MySQL connection failed: {e}")
        return 0, 0

    mcur = mysql_conn.cursor(dictionary=True)
    sc = conn.cursor()

    total_classes = 0
    total_methods = 0

    for cls_name in TARGET_CLASSES:
        mcur.execute("SELECT id, class_name, domain, class_code, description FROM vb_classes WHERE class_name = %s", (cls_name,))
        cls_row = mcur.fetchone()
        if not cls_row:
            continue

        sc.execute("INSERT OR REPLACE INTO classes (class_name, domain, source, class_code, description) VALUES (?, ?, 'mysql', ?, ?)",
            (cls_row['class_name'], cls_row.get('domain') or '', cls_row.get('class_code') or '', cls_row.get('description') or ''))
        class_id = sc.lastrowid
        total_classes += 1

        mcur.execute("SELECT id, method_name, method_code, params, line_start FROM vb_methods WHERE class_id = %s ORDER BY line_start, id", (cls_row['id'],))
        method_count = 0
        for m in mcur.fetchall():
            code = m.get('method_code') or ''
            sc.execute("""INSERT INTO methods (class_id, class_name, method_name, params, method_code,
                is_dunder, is_run, is_init, returns_tuple3, has_ast, has_re, has_try, code_len, line_start, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'mysql')""",
                (class_id, cls_row['class_name'], m['method_name'], m.get('params') or '', code,
                 1 if (m['method_name'].startswith('__') and m['method_name'].endswith('__')) else 0,
                 1 if m['method_name'] == 'Run' else 0,
                 1 if m['method_name'] == '__init__' else 0,
                 1 if 'return (' in code and ', ' in code and ')' in code else 0,
                 1 if 'ast.' in code or 'ast ' in code else 0,
                 1 if 're.' in code or 'import re' in code else 0,
                 1 if 'try:' in code else 0,
                 len(code), m.get('line_start')))
            method_count += 1
            total_methods += 1

        sc.execute("UPDATE classes SET method_count = ? WHERE id = ?", (method_count, class_id))

    conn.commit()
    mysql_conn.close()
    return total_classes, total_methods


def ingest_script(conn, filepath, source_tag):
    if not os.path.exists(filepath):
        return 0

    with open(filepath, 'r') as f:
        source = f.read()

    file_hash = hashlib.md5(source.encode()).hexdigest()
    sc = conn.cursor()
    sc.execute("INSERT OR REPLACE INTO code_files (file_path, file_name, source_code, hash) VALUES (?, ?, ?, ?)",
        (filepath, os.path.basename(filepath), source, file_hash))

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0

    count = 0
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            cls_name = node.name
            class_code = ast.get_source_segment(source, node) or ""
            docstring = ""
            if node.body and isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                    docstring = node.body[0].value.value.strip()

            sc.execute("INSERT OR REPLACE INTO classes (class_name, domain, source, class_code, description) VALUES (?, ?, ?, ?, ?)",
                (cls_name, source_tag, source_tag, class_code, docstring))
            class_id = sc.lastrowid

            method_count = 0
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    code = ast.get_source_segment(source, item) or "\n".join(source.splitlines()[item.lineno-1:item.end_lineno])
                    params = ", ".join(arg.arg for arg in item.args.args)
                    sc.execute("""INSERT INTO methods (class_id, class_name, method_name, params, method_code,
                        is_dunder, is_run, is_init, returns_tuple3, has_ast, has_re, has_try, code_len, line_start, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (class_id, cls_name, item.name, params, code,
                         1 if (item.name.startswith('__') and item.name.endswith('__')) else 0,
                         1 if item.name == 'Run' else 0,
                         1 if item.name == '__init__' else 0,
                         1 if 'return (' in code and ', ' in code and ')' in code else 0,
                         1 if 'ast.' in code or 'ast ' in code else 0,
                         1 if 're.' in code or 'import re' in code else 0,
                         1 if 'try:' in code else 0,
                         len(code), item.lineno, source_tag))
                    method_count += 1
                    count += 1
            sc.execute("UPDATE classes SET method_count = ? WHERE id = ?", (method_count, class_id))

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.col_offset == 0:
            code = ast.get_source_segment(source, node) or "\n".join(source.splitlines()[node.lineno-1:node.end_lineno])
            params = ", ".join(arg.arg for arg in node.args.args)
            sc.execute("SELECT id FROM classes WHERE class_name = '<module>' AND source = ?", (source_tag,))
            row = sc.fetchone()
            if row:
                module_class_id = row[0]
            else:
                sc.execute("INSERT INTO classes (class_name, domain, source, class_code, description) VALUES ('<module>', ?, ?, '', 'Top-level functions')", (source_tag, source_tag))
                module_class_id = sc.lastrowid

            sc.execute("""INSERT INTO methods (class_id, class_name, method_name, params, method_code,
                is_dunder, is_run, is_init, returns_tuple3, has_ast, has_re, has_try, code_len, line_start, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (module_class_id, '<module>', node.name, params, code,
                 1 if (node.name.startswith('__') and node.name.endswith('__')) else 0,
                 1 if node.name == 'Run' else 0, 0,
                 1 if 'return (' in code and ', ' in code and ')' in code else 0,
                 1 if 'ast.' in code or 'ast ' in code else 0,
                 1 if 're.' in code or 'import re' in code else 0,
                 1 if 'try:' in code else 0,
                 len(code), node.lineno, source_tag))
            count += 1

    conn.commit()
    return count


def build_units(conn):
    sc = conn.cursor()
    sc.execute("DELETE FROM units")

    UNIT_PATTERNS = [
        ("init_run", [r'__init__', r'Run']),
        ("scan_fix_verify", [r'[Ss]can|[Dd]etect|[Ff]ind', r'[Ff]ix|[Rr]epair|[Aa]pply|[Pp]atch', r'[Vv]erify|[Pp]roof|[Tt]est|[Cc]heck']),
        ("parse_transform_build", [r'[Pp]arse|[Rr]ead|[Ll]oad', r'[Tt]ransform|[Cc]onvert|[Rr]ewrite|[Nn]ormalize', r'[Bb]uild|[Gg]enerate|[Cc]reate|[Ww]rite|[Ee]mit']),
        ("plan_apply_rollback", [r'[Pp]lan|[Pp]ropose|[Ss]uggest', r'[Aa]pply|[Ee]xecute|[Rr]un|[Dd]ispatch', r'[Rr]ollback|[Rr]evert|[Cc]leanup|[Cc]lose']),
        ("read_process_write", [r'[Rr]ead|[Ff]etch|[Gg]et', r'[Pp]rocess|[Tt]ransform|[Aa]nalyze|[Ss]core', r'[Ww]rite|[Ss]ave|[Ss]tore|[Pp]ut']),
        ("learn_score_adapt", [r'[Ll]earn|[Ee]xtract|[Cc]ollect', r'[Ss]core|[Rr]ate|[Ee]val', r'[Aa]dapt|[Uu]pdate|[Tt]une|[Pp]romote']),
    ]

    sc.execute("SELECT id, class_name, method_count FROM classes ORDER BY class_name")
    classes = sc.fetchall()
    unit_count = 0

    for class_id, class_name, method_count in classes:
        sc.execute("SELECT id, method_name, method_code, code_len FROM methods WHERE class_id = ? ORDER BY line_start, id", (class_id,))
        methods = sc.fetchall()
        if len(methods) < 2:
            continue

        for unit_type, patterns in UNIT_PATTERNS:
            matched = []
            for pattern in patterns:
                for m in methods:
                    if re.search(pattern, m[1], re.IGNORECASE) and m not in matched:
                        matched.append(m)
                        break
            if len(matched) >= 2:
                sc.execute("INSERT INTO units (unit_name, unit_type, class_name, method_ids, method_names, description, method_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f"{class_name}:{unit_type}", unit_type, class_name,
                     ",".join(str(m[0]) for m in matched),
                     " → ".join(m[1] for m in matched),
                     f"{unit_type}: {' → '.join(m[1] for m in matched)}", len(matched)))
                unit_count += 1

    conn.commit()
    return unit_count


def build_graph(conn):
    c = conn.cursor()
    c.executescript("DELETE FROM graph_edges; DELETE FROM graph_nodes;")

    c.execute("SELECT id, class_name, method_name, method_code, source FROM methods")
    all_methods = c.fetchall()

    method_lookup = {}
    method_codes = {}
    class_methods = defaultdict(set)

    for mid, cls, mname, code, src in all_methods:
        method_lookup[(cls, mname)] = mid
        method_codes[(cls, mname)] = code or ""
        class_methods[cls].add(mname)

    all_class_names = set(class_methods.keys())
    edges = set()
    dispatch_map = {}

    for (cls, mname), code in method_codes.items():
        if mname != "Run" or not code or "command ==" not in code:
            continue
        for m in re.finditer(r'command\s*==\s*["\'](\w+)["\']', code):
            cmd = m.group(1)
            if cmd in class_methods.get(cls, set()):
                dispatch_map[(cls, cmd)] = cmd
                edges.add((cls, "Run", cls, cmd, "dispatch"))

    for (cls, mname), code in method_codes.items():
        if not code or len(code) < 10:
            continue
        try:
            tree = ast.parse(code)
        except SyntaxError:
            for m in re.finditer(r'self\.(\w+)\s*\([^)]*\)\s*\.Run\s*\(\s*["\'](\w+)["\']', code):
                if m.group(1) in all_class_names:
                    edges.add((cls, mname, m.group(1), m.group(2), "vbstyle_cross" if (m.group(1), m.group(2)) in dispatch_map else "vbstyle_cross_miss"))
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func
                if isinstance(attr.value, ast.Name) and attr.value.id == "self":
                    if attr.attr in class_methods.get(cls, set()):
                        edges.add((cls, mname, cls, attr.attr, "internal_call"))
                elif isinstance(attr.value, ast.Call) and isinstance(attr.value.func, ast.Attribute):
                    inner = attr.value.func
                    if isinstance(inner.value, ast.Name) and inner.value.id == "self" and attr.attr == "Run":
                        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                            tc = inner.attr
                            tcmd = node.args[0].value
                            if tc in all_class_names:
                                edges.add((cls, mname, tc, tcmd, "vbstyle_cross" if (tc, tcmd) in dispatch_map else "vbstyle_cross_miss"))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func
                if isinstance(attr.value, ast.Name) and attr.value.id in all_class_names:
                    if attr.attr in class_methods.get(attr.value.id, set()):
                        edges.add((cls, mname, attr.value.id, attr.attr, "cross_call"))

    for (cls, mname), code in method_codes.items():
        if not code:
            continue
        for m in re.finditer(r'self\.(\w+)\s*\([^)]*\)\s*\.Run\s*\(\s*["\'](\w+)["\']', code):
            if m.group(1) in all_class_names:
                edges.add((cls, mname, m.group(1), m.group(2), "vbstyle_cross" if (m.group(1), m.group(2)) in dispatch_map else "vbstyle_cross_miss"))

    in_deg = defaultdict(int)
    out_deg = defaultdict(int)
    for src_cls, src_meth, tgt_cls, tgt_meth, etype in edges:
        if etype not in ("cross_class_miss", "vbstyle_cross_miss"):
            out_deg[(src_cls, src_meth)] += 1
            in_deg[(tgt_cls, tgt_meth)] += 1

    for (cls, mname), mid in method_lookup.items():
        ind = in_deg.get((cls, mname), 0)
        outd = out_deg.get((cls, mname), 0)
        c.execute("INSERT OR IGNORE INTO graph_nodes (method_id, class_name, method_name, in_degree, out_degree, is_entry, is_exit) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mid, cls, mname, ind, outd, 1 if ind > 3 and outd <= 2 else 0, 1 if outd > 3 and ind <= 1 else 0))

    for src_cls, src_meth, tgt_cls, tgt_meth, etype in edges:
        c.execute("INSERT INTO graph_edges (source_class, source_method, target_class, target_method, edge_type, source_method_id, target_method_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (src_cls, src_meth, tgt_cls, tgt_meth, etype, method_lookup.get((src_cls, src_meth)), method_lookup.get((tgt_cls, tgt_meth))))

    conn.commit()
    return len(edges), len(method_lookup)


def cmd_build():
    print("EFL BRAIN — BUILD")
    print("=" * 50)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("  Removed old database")

    conn = get_conn()
    init_schema(conn)

    print("  Pulling from MySQL...")
    cls_count, meth_count = pull_mysql(conn)
    print(f"    {cls_count} classes, {meth_count} methods")

    base = os.path.dirname(os.path.abspath(__file__))
    for script in ENGINE_SCRIPTS:
        path = os.path.join(base, script)
        if os.path.exists(path):
            tag = script.replace(".py", "")
            n = ingest_script(conn, path, tag)
            print(f"    Ingested {script}: {n} methods")

    print("  Building compute units...")
    units = build_units(conn)
    print(f"    {units} units")

    print("  Building code graph...")
    edges, nodes = build_graph(conn)
    print(f"    {edges} edges, {nodes} nodes")

    conn.close()
    print(f"\n  Database: {DB_PATH}")
    print("  Done.")


# ═══════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════

def cmd_status():
    conn = get_conn()
    c = conn.cursor()

    print("EFL BRAIN — STATUS")
    print("=" * 50)

    for table in ['code_files', 'classes', 'methods', 'units', 'graph_edges', 'graph_nodes', 'execution_log', 'unit_graph_edges', 'unit_rankings', 'expectation_graph', 'diff_results']:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table:25s} {c.fetchone()[0]:6d} rows")

    print(f"\n  By source:")
    c.execute("SELECT source, COUNT(*) FROM classes GROUP BY source ORDER BY COUNT(*) DESC")
    for src, cnt in c.fetchall():
        print(f"    classes  {src:20s} {cnt}")
    c.execute("SELECT source, COUNT(*) FROM methods GROUP BY source ORDER BY COUNT(*) DESC")
    for src, cnt in c.fetchall():
        print(f"    methods  {src:20s} {cnt}")

    size = os.path.getsize(DB_PATH)
    print(f"\n  Size: {size / 1024:.1f} KB")
    print(f"  Path: {DB_PATH}")
    conn.close()


# ═══════════════════════════════════════════════════════════════
# EXEC — run a method from the database
# ═══════════════════════════════════════════════════════════════

def cmd_exec(class_name, method_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT method_code, params FROM methods WHERE class_name = ? AND method_name = ?", (class_name, method_name))
    row = c.fetchone()
    if not row:
        print(f"  Method not found: {class_name}.{method_name}")
        conn.close()
        return

    code = row[0]
    params = row[1] or ""
    print(f"  Executing: {class_name}.{method_name}({params})")
    print(f"  Code ({len(code)} chars):")
    print("-" * 50)
    print(code)
    print("-" * 50)

    # Log the execution attempt
    try:
        local_ns = {}
        exec(code, {}, local_ns)
        # If it's a function, try to call it
        for name, obj in local_ns.items():
            if callable(obj) and not name.startswith('_'):
                print(f"\n  Defined: {name}")
        c.execute("INSERT INTO execution_log (class_name, method_name, success, action_taken) VALUES (?, ?, 1, 'exec')", (class_name, method_name))
        print("  Status: OK (defined successfully)")
    except Exception as e:
        c.execute("INSERT INTO execution_log (class_name, method_name, success, error_msg, action_taken) VALUES (?, ?, 0, ?, 'exec')", (class_name, method_name, str(e)))
        print(f"  Status: ERROR — {e}")

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# QUERY / TRACE / REUSE / DIFF — delegated to stored code
# ═══════════════════════════════════════════════════════════════

def cmd_query(domain):
    conn = get_conn()
    c = conn.cursor()
    print(f"QUERY: {domain}")
    print("=" * 50)

    c.execute("SELECT class_name, source, method_count FROM classes WHERE LOWER(class_name) LIKE ? ORDER BY method_count DESC", (f"%{domain}%",))
    classes = c.fetchall()
    print(f"\n  Classes ({len(classes)}):")
    for cls in classes:
        print(f"    {cls[0]:45s}  {cls[2]:3d} methods  [{cls[1]}]")

    c.execute("SELECT class_name, method_name, code_len, source FROM methods WHERE LOWER(method_name) LIKE ? OR LOWER(class_name) LIKE ? ORDER BY code_len DESC LIMIT 30", (f"%{domain}%", f"%{domain}%"))
    methods = c.fetchall()
    print(f"\n  Methods ({len(methods)}):")
    for m in methods:
        print(f"    {m[0]:35s}.{m[1]:30s}  {m[2]:6d} chars  [{m[3]}]")

    c.execute("SELECT unit_name, unit_type, method_names FROM units WHERE LOWER(unit_type) LIKE ? OR LOWER(class_name) LIKE ? ORDER BY unit_name", (f"%{domain}%", f"%{domain}%"))
    units = c.fetchall()
    print(f"\n  Units ({len(units)}):")
    for u in units:
        print(f"    {u[0]:50s}  type={u[1]}")
        print(f"      → {u[2]}")
    conn.close()


def cmd_trace(class_name, method_name):
    conn = get_conn()
    c = conn.cursor()
    print(f"TRACE: {class_name}.{method_name}")
    print("=" * 50)

    c.execute("SELECT id, code_len, source FROM methods WHERE class_name = ? AND method_name = ?", (class_name, method_name))
    m = c.fetchone()
    if not m:
        print("  Not found")
        conn.close()
        return

    print(f"\n  Method: {m[2]} source, {m[1]} chars")

    c.execute("SELECT target_class, target_method, edge_type FROM graph_edges WHERE source_class = ? AND source_method = ?", (class_name, method_name))
    print(f"\n  Calls out:")
    for e in c.fetchall():
        print(f"    → {e[0]}.{e[1]}  [{e[2]}]")

    c.execute("SELECT source_class, source_method, edge_type FROM graph_edges WHERE target_class = ? AND target_method = ?", (class_name, method_name))
    print(f"\n  Called by:")
    for e in c.fetchall():
        print(f"    ← {e[0]}.{e[1]}  [{e[2]}]")

    # Transitive deps
    visited = set()
    queue = deque([(class_name, method_name)])
    deps = set()
    while queue:
        cls, meth = queue.popleft()
        if (cls, meth) in visited:
            continue
        visited.add((cls, meth))
        c.execute("SELECT target_class, target_method FROM graph_edges WHERE source_class = ? AND source_method = ? AND edge_type NOT IN ('cross_class_miss', 'vbstyle_cross_miss')", (cls, meth))
        for row in c.fetchall():
            dep = (row[0], row[1])
            if dep not in visited:
                deps.add(dep)
                queue.append(dep)

    print(f"\n  Full dependency tree ({len(deps)}):")
    for cls, meth in sorted(deps):
        print(f"    {cls}.{meth}")
    conn.close()


def cmd_reuse(pattern):
    conn = get_conn()
    c = conn.cursor()
    print(f"REUSE: {pattern}")
    print("=" * 50)

    c.execute("SELECT unit_name, unit_type, method_names, method_count FROM units WHERE LOWER(unit_type) LIKE ? ORDER BY unit_name", (f"%{pattern}%",))
    units = c.fetchall()
    print(f"\n  Found {len(units)} units:\n")
    for u in units:
        print(f"    {u[0]:50s}  methods={u[3]}")
        print(f"      → {u[2]}")
    conn.close()


# ═══════════════════════════════════════════════════════════════
# EXPECTATIONS + DIFF (inline, no external file needed)
# ═══════════════════════════════════════════════════════════════

def cmd_diff(domain=None):
    # Import expectation definitions inline
    EXPECTATIONS = _get_expectations()
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Ensure expectation table exists
    c.execute("""CREATE TABLE IF NOT EXISTS expectation_graph (
        id INTEGER PRIMARY KEY AUTOINCREMENT, domain TEXT, element_type TEXT, element_name TEXT,
        purpose TEXT, expected_returns TEXT, required_methods TEXT,
        edge_from TEXT, edge_to TEXT, edge_type TEXT,
        UNIQUE(domain, element_type, element_name))""")
    c.execute("""CREATE TABLE IF NOT EXISTS diff_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT, domain TEXT, gap_type TEXT, element_name TEXT,
        purpose TEXT, existing_count INTEGER DEFAULT 0, existing_locations TEXT,
        status TEXT DEFAULT 'MISSING', suggested_action TEXT, priority TEXT DEFAULT 'medium',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    # Build expectations
    c.execute("DELETE FROM expectation_graph")
    for dom, spec in EXPECTATIONS.items():
        for m in spec.get("required_methods", []):
            c.execute("INSERT OR REPLACE INTO expectation_graph (domain, element_type, element_name, purpose, expected_returns) VALUES (?, 'method', ?, ?, ?)", (dom, m["name"], m["purpose"], m["returns"]))
        for u in spec.get("required_units", []):
            c.execute("INSERT OR REPLACE INTO expectation_graph (domain, element_type, element_name, purpose, required_methods) VALUES (?, 'unit', ?, ?, ?)", (dom, u["name"], f"Unit: {' → '.join(u['methods'])}", ",".join(u["methods"])))
        for e in spec.get("required_edges", []):
            c.execute("INSERT OR REPLACE INTO expectation_graph (domain, element_type, element_name, edge_from, edge_to, edge_type) VALUES (?, 'edge', ?, ?, ?, ?)", (dom, f"{e['from']}→{e['to']}", e["from"], e["to"], e["type"]))
    conn.commit()

    domains = [domain] if domain else list(EXPECTATIONS.keys())

    print("DIFF ENGINE" + (f": {domain}" if domain else ": ALL DOMAINS"))
    print("=" * 50)

    for dom in domains:
        c.execute("DELETE FROM diff_results WHERE domain = ?", (dom,))
        c.execute("SELECT * FROM expectation_graph WHERE domain = ? ORDER BY element_type, element_name", (dom,))
        expectations = c.fetchall()

        if not expectations:
            continue

        print(f"\n  DOMAIN: {dom}")
        gaps = []

        for exp in expectations:
            etype = exp["element_type"]
            ename = exp["element_name"]

            if etype == "method":
                c.execute("SELECT class_name, method_name FROM methods WHERE LOWER(method_name) LIKE ?", (f"%{ename}%",))
                existing = c.fetchall()
            elif etype == "unit":
                req = (exp["required_methods"] or "").split(",")
                found = []
                for m in req:
                    c.execute("SELECT DISTINCT unit_name FROM units WHERE LOWER(method_names) LIKE ?", (f"%{m}%",))
                    found.extend(r[0] for r in c.fetchall())
                existing = list(set(found)) if found else []
            elif etype == "edge":
                c.execute("SELECT source_class, source_method, target_class, target_method FROM graph_edges WHERE LOWER(source_method) LIKE ? AND LOWER(target_method) LIKE ? LIMIT 3", (f"%{exp['edge_from']}%", f"%{exp['edge_to']}%"))
                existing = c.fetchall()
            else:
                existing = []

            status = "FOUND" if existing else "MISSING"
            action = "REUSE" if existing else ("CREATE" if etype != "edge" else "CREATE_EDGE")
            priority = "low" if existing else ("high" if etype == "method" else "medium")

            c.execute("INSERT INTO diff_results (domain, gap_type, element_name, purpose, existing_count, status, suggested_action, priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (dom, etype, ename, exp["purpose"] or "", len(existing), status, action, priority))
            gaps.append((etype, ename, status))

        found = sum(1 for g in gaps if g[2] == "FOUND")
        missing = sum(1 for g in gaps if g[2] == "MISSING")
        print(f"    Expected: {len(gaps)}  Found: {found}  Missing: {missing}  Coverage: {found/len(gaps)*100:.0f}%")

        if missing:
            c.execute("SELECT element_name, gap_type, suggested_action, priority FROM diff_results WHERE domain = ? AND status = 'MISSING' ORDER BY priority DESC", (dom,))
            for row in c.fetchall():
                print(f"      [{row['priority'].upper():6s}] {row['gap_type']:8s} {row['element_name']:25s} → {row['suggested_action']}")

    conn.commit()
    conn.close()


def _get_expectations():
    return {
        "repair": {"description": "Code repair domain", "required_methods": [
            {"name": "detect", "purpose": "Identify faults", "returns": "Tuple3"},
            {"name": "diagnose", "purpose": "Classify faults", "returns": "Tuple3"},
            {"name": "fix", "purpose": "Apply repair", "returns": "Tuple3"},
            {"name": "verify", "purpose": "Verify repair", "returns": "Tuple3"},
            {"name": "rollback", "purpose": "Undo failed repair", "returns": "Tuple3"},
            {"name": "report", "purpose": "Generate report", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "detect_diagnose_fix", "methods": ["detect", "diagnose", "fix"], "type": "scan_fix_verify"},
            {"name": "fix_verify_rollback", "methods": ["fix", "verify", "rollback"], "type": "plan_apply_rollback"},
        ], "required_edges": [
            {"from": "detect", "to": "diagnose", "type": "call_relation"},
            {"from": "diagnose", "to": "fix", "type": "call_relation"},
            {"from": "fix", "to": "verify", "type": "call_relation"},
            {"from": "verify", "to": "rollback", "type": "conditional"},
        ]},
        "generate": {"description": "Code generation domain", "required_methods": [
            {"name": "generate", "purpose": "Generate code", "returns": "Tuple3"},
            {"name": "build", "purpose": "Build class/file", "returns": "Tuple3"},
            {"name": "validate", "purpose": "Validate generated code", "returns": "Tuple3"},
            {"name": "write", "purpose": "Write to file", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "generate_validate_write", "methods": ["generate", "validate", "write"], "type": "parse_transform_build"},
        ], "required_edges": [
            {"from": "generate", "to": "validate", "type": "call_relation"},
            {"from": "validate", "to": "write", "type": "call_relation"},
        ]},
        "parse": {"description": "Parsing domain", "required_methods": [
            {"name": "tokenize", "purpose": "Tokenize source", "returns": "Tuple3"},
            {"name": "parse", "purpose": "Parse into AST", "returns": "Tuple3"},
            {"name": "extract", "purpose": "Extract components", "returns": "Tuple3"},
            {"name": "transform", "purpose": "Transform AST", "returns": "Tuple3"},
            {"name": "emit", "purpose": "Emit code", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "parse_extract_transform", "methods": ["parse", "extract", "transform"], "type": "parse_transform_build"},
        ], "required_edges": [
            {"from": "tokenize", "to": "parse", "type": "call_relation"},
            {"from": "parse", "to": "extract", "type": "call_relation"},
            {"from": "extract", "to": "transform", "type": "call_relation"},
            {"from": "transform", "to": "emit", "type": "call_relation"},
        ]},
        "scan": {"description": "Scanning domain", "required_methods": [
            {"name": "scan", "purpose": "Scan code", "returns": "Tuple3"},
            {"name": "detect", "purpose": "Detect patterns", "returns": "Tuple3"},
            {"name": "report", "purpose": "Report findings", "returns": "Tuple3"},
            {"name": "fix", "purpose": "Fix issues", "returns": "Tuple3"},
            {"name": "verify", "purpose": "Verify fixes", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "scan_fix_verify", "methods": ["scan", "fix", "verify"], "type": "scan_fix_verify"},
        ], "required_edges": [
            {"from": "scan", "to": "detect", "type": "call_relation"},
            {"from": "scan", "to": "fix", "type": "call_relation"},
            {"from": "fix", "to": "verify", "type": "call_relation"},
        ]},
        "db": {"description": "Database domain", "required_methods": [
            {"name": "connect", "purpose": "Connect to DB", "returns": "Tuple3"},
            {"name": "query", "purpose": "Execute query", "returns": "Tuple3"},
            {"name": "insert", "purpose": "Insert record", "returns": "Tuple3"},
            {"name": "update", "purpose": "Update record", "returns": "Tuple3"},
            {"name": "commit", "purpose": "Commit transaction", "returns": "Tuple3"},
            {"name": "rollback", "purpose": "Rollback transaction", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "connect_query_commit", "methods": ["connect", "query", "commit"], "type": "read_process_write"},
        ], "required_edges": [
            {"from": "connect", "to": "query", "type": "call_relation"},
            {"from": "query", "to": "commit", "type": "call_relation"},
        ]},
        "test": {"description": "Testing domain", "required_methods": [
            {"name": "setup", "purpose": "Setup test env", "returns": "Tuple3"},
            {"name": "execute", "purpose": "Execute test", "returns": "Tuple3"},
            {"name": "assert", "purpose": "Assert condition", "returns": "Tuple3"},
            {"name": "verify", "purpose": "Verify outcome", "returns": "Tuple3"},
            {"name": "teardown", "purpose": "Cleanup", "returns": "Tuple3"},
            {"name": "report", "purpose": "Test report", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "setup_execute_teardown", "methods": ["setup", "execute", "teardown"], "type": "scan_fix_verify"},
        ], "required_edges": [
            {"from": "setup", "to": "execute", "type": "call_relation"},
            {"from": "execute", "to": "assert", "type": "call_relation"},
            {"from": "assert", "to": "teardown", "type": "call_relation"},
        ]},
        "learn": {"description": "Learning domain", "required_methods": [
            {"name": "collect", "purpose": "Collect data", "returns": "Tuple3"},
            {"name": "extract", "purpose": "Extract features", "returns": "Tuple3"},
            {"name": "learn", "purpose": "Learn from data", "returns": "Tuple3"},
            {"name": "score", "purpose": "Score rules", "returns": "Tuple3"},
            {"name": "adapt", "purpose": "Adapt strategy", "returns": "Tuple3"},
            {"name": "store", "purpose": "Store knowledge", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "learn_score_adapt", "methods": ["learn", "score", "adapt"], "type": "learn_score_adapt"},
        ], "required_edges": [
            {"from": "collect", "to": "extract", "type": "call_relation"},
            {"from": "extract", "to": "learn", "type": "call_relation"},
            {"from": "learn", "to": "score", "type": "call_relation"},
            {"from": "score", "to": "adapt", "type": "call_relation"},
        ]},
        "gui": {"description": "GUI domain", "required_methods": [
            {"name": "create", "purpose": "Create widget", "returns": "Tuple3"},
            {"name": "show", "purpose": "Show widget", "returns": "Tuple3"},
            {"name": "hide", "purpose": "Hide widget", "returns": "Tuple3"},
            {"name": "layout", "purpose": "Arrange widgets", "returns": "Tuple3"},
            {"name": "event", "purpose": "Handle event", "returns": "Tuple3"},
            {"name": "render", "purpose": "Render UI", "returns": "Tuple3"},
            {"name": "update", "purpose": "Update state", "returns": "Tuple3"},
            {"name": "close", "purpose": "Close and cleanup", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "create_layout_show", "methods": ["create", "layout", "show"], "type": "parse_transform_build"},
        ], "required_edges": [
            {"from": "create", "to": "layout", "type": "call_relation"},
            {"from": "layout", "to": "show", "type": "call_relation"},
            {"from": "event", "to": "render", "type": "call_relation"},
        ]},
        "fault_inject": {"description": "Fault injection domain", "required_methods": [
            {"name": "inject", "purpose": "Inject fault", "returns": "Tuple3"},
            {"name": "mutate", "purpose": "Mutate code", "returns": "Tuple3"},
            {"name": "corrupt", "purpose": "Corrupt element", "returns": "Tuple3"},
            {"name": "validate", "purpose": "Validate fault", "returns": "Tuple3"},
            {"name": "classify", "purpose": "Classify fault", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "inject_validate_classify", "methods": ["inject", "validate", "classify"], "type": "scan_fix_verify"},
        ], "required_edges": [
            {"from": "inject", "to": "validate", "type": "call_relation"},
            {"from": "validate", "to": "classify", "type": "call_relation"},
        ]},
        "orchestrate": {"description": "Orchestration domain", "required_methods": [
            {"name": "dispatch", "purpose": "Dispatch command", "returns": "Tuple3"},
            {"name": "route", "purpose": "Route request", "returns": "Tuple3"},
            {"name": "coordinate", "purpose": "Coordinate authorities", "returns": "Tuple3"},
            {"name": "monitor", "purpose": "Monitor state", "returns": "Tuple3"},
            {"name": "recover", "purpose": "Recover from failure", "returns": "Tuple3"},
        ], "required_units": [
            {"name": "dispatch_route_coordinate", "methods": ["dispatch", "route", "coordinate"], "type": "scan_fix_verify"},
        ], "required_edges": [
            {"from": "dispatch", "to": "route", "type": "call_relation"},
            {"from": "route", "to": "coordinate", "type": "call_relation"},
            {"from": "monitor", "to": "recover", "type": "conditional"},
        ]},
    }


# ═══════════════════════════════════════════════════════════════
# FEEDBACK — read test_runner results, show failures + suggest repairs
# ═══════════════════════════════════════════════════════════════

def cmd_feedback(domain=None):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS test_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        method_name TEXT NOT NULL,
        status TEXT NOT NULL,
        error_detail TEXT,
        error_type TEXT,
        run_id TEXT,
        source TEXT DEFAULT 'test_runner',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(domain, method_name, run_id)
    )""")
    conn.commit()

    print("TEST FEEDBACK" + (f": {domain}" if domain else ": ALL DOMAINS"))
    print("=" * 60)

    where = "WHERE status IN ('FAIL','ERROR')"
    params = ()
    if domain:
        where += " AND domain = ?"
        params = (domain,)

    c.execute(f"SELECT domain, method_name, status, error_detail, error_type, run_id FROM test_feedback {where} ORDER BY error_type, domain, method_name", params)
    failures = c.fetchall()

    if not failures:
        print("  No failures recorded. Run test_runner first.")
        conn.close()
        return

    by_type = {}
    for f in failures:
        etype = f["error_type"] or "UNKNOWN"
        if etype not in by_type:
            by_type[etype] = []
        by_type[etype].append(f)

    print(f"\n  Total failures: {len(failures)}")
    print()

    for etype, items in sorted(by_type.items(), key=lambda x: -len(x[1])):
        print(f"  [{etype}] — {len(items)} failures")
        for item in items[:5]:
            print(f"    {item['domain']:15s}.{item['method_name']:30s} {str(item['error_detail'])[:50]}")
        if len(items) > 5:
            print(f"    ... and {len(items) - 5} more")
        print()

    c.execute("""SELECT domain, COUNT(*) as total,
        SUM(CASE WHEN status='PASS' THEN 1 ELSE 0 END) as pass_count,
        SUM(CASE WHEN status IN ('FAIL','ERROR') THEN 1 ELSE 0 END) as fail_count
        FROM test_feedback GROUP BY domain ORDER BY fail_count DESC""")
    summary = c.fetchall()
    if summary:
        print("  DOMAIN SUMMARY:")
        for row in summary:
            pct = row["pass_count"] / row["total"] * 100 if row["total"] else 0
            print(f"    {row['domain']:15s}: {row['pass_count']:3d} pass / {row['total']:3d} total ({pct:.0f}%) — {row['fail_count']} failures")

    c.execute("""SELECT error_type, COUNT(*) as cnt FROM test_feedback
        WHERE status IN ('FAIL','ERROR') GROUP BY error_type ORDER BY cnt DESC""")
    patterns = c.fetchall()
    if patterns:
        print("\n  REPAIR PRIORITIES:")
        for p in patterns:
            suggestion = {
                'NAME_ERROR': 'Add missing imports or helper definitions to test namespace',
                'IMPORT_ERROR': 'Fix module path or add missing dom_*.py file',
                'MISSING_IMPL': 'Implement missing method in domain class',
                'EXEC_ERROR': 'Fix syntax or compilation error in test method',
                'FILE_ERROR': 'Fix file path handling in test or helper',
                'RUNTIME_ERROR': 'Debug runtime exception in domain method',
            }.get(p["error_type"], 'Investigate failure pattern')
            print(f"    [{p['error_type']:15s}] {p['cnt']:3d} cases → {suggestion}")

    c.execute("""SELECT domain, method_name, error_type, error_detail
        FROM test_feedback WHERE status IN ('FAIL','ERROR')
        AND error_type IN ('NAME_ERROR','IMPORT_ERROR','MISSING_IMPL')
        ORDER BY error_type, domain LIMIT 20""")
    actionable = c.fetchall()
    if actionable:
        print("\n  ACTIONABLE FIXES (can be auto-repaired):")
        for a in actionable:
            print(f"    {a['error_type']:15s} {a['domain']:15s}.{a['method_name']:30s}")

    conn.close()


# ═══════════════════════════════════════════════════════════════
# MAIN DISPATCH
# ═══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("EFL Brain — single entry point")
        print()
        print("Usage: python3 efl.py <command> [args]")
        print()
        print("Commands:")
        print("  build          Pull MySQL + ingest all scripts + build units + graph")
        print("  status         Show database summary")
        print("  query <domain> Query methods/classes/units for a domain")
        print("  trace <Cls.m>  Trace method dependencies")
        print("  reuse <pattern> Find units matching a pattern")
        print("  diff [domain]  Diff expected vs existing (all domains if none given)")
        print("  exec <Cls.m>   Execute a method from the database")
        print("  feedback [dom] Show test failures + repair priorities from test_runner")
        print("  pipeline       Run the full orchestrator pipeline (build→connect→simulate→diff→repair→scan→report)")
        print()
        print("Examples:")
        print("  python3 efl.py build")
        print("  python3 efl.py status")
        print("  python3 efl.py query repair")
        print("  python3 efl.py trace BrkAI.Repair")
        print("  python3 efl.py diff repair")
        print("  python3 efl.py exec BrkAI.Repair")
        print("  python3 efl.py pipeline")
        return

    cmd = sys.argv[1].lower()

    if cmd == "build":
        cmd_build()
    elif cmd == "status":
        cmd_status()
    elif cmd == "query" and len(sys.argv) >= 3:
        cmd_query(sys.argv[2])
    elif cmd == "trace" and len(sys.argv) >= 3:
        parts = sys.argv[2].split(".")
        if len(parts) == 2:
            cmd_trace(parts[0], parts[1])
        else:
            print("Format: trace Class.method")
    elif cmd == "reuse" and len(sys.argv) >= 3:
        cmd_reuse(sys.argv[2])
    elif cmd == "diff":
        cmd_diff(sys.argv[2] if len(sys.argv) >= 3 else None)
    elif cmd == "exec" and len(sys.argv) >= 3:
        parts = sys.argv[2].split(".")
        if len(parts) == 2:
            cmd_exec(parts[0], parts[1])
        else:
            print("Format: exec Class.method")
    elif cmd == "feedback":
        cmd_feedback(sys.argv[2] if len(sys.argv) >= 3 else None)
    elif cmd == "pipeline":
        from Efi_orchestrator import Orchestrator
        orch = Orchestrator()
        ok, data, err = orch.Run("run")
        if ok:
            print("=" * 70)
            print("  ORCHESTRATOR PIPELINE — COMPLETE")
            print("=" * 70)
            print(f"\n  Steps: {data['total_steps']} total, {data['steps_ok']} ok, {data['steps_failed']} failed")
            print(f"  Duration: {data['total_duration']}s\n")
            for step in orch.state["steps"]:
                status = "OK" if step["ok"] else "FAIL"
                print(f"    Step {step['step']}: {step['name']:12s}  {status:4s}  {step['duration']:.3f}s")
                if step["ok"] and step["data"]:
                    for k, v in step["data"].items():
                        if isinstance(v, dict):
                            for k2, v2 in v.items():
                                print(f"      {k2:20s} {v2}")
                        elif not isinstance(v, (list,)):
                            print(f"      {k:20s} {v}")
                elif step["error"]:
                    print(f"      ERROR: {step['error']}")
            print("=" * 70)
        else:
            print(f"Pipeline failed: {err}")
            sys.exit(1)
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'python3 efl.py' for help.")


if __name__ == "__main__":
    main()
