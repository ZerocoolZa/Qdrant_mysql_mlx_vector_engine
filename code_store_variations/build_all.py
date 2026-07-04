#!/usr/bin/env python3
"""
Build 20 schema variations for code-in-database.
Each variation tests a different approach to storing and running code as records.
All ingest the same file (GhostQAEngine.py) and get benchmarked.
"""

import sqlite3
import ast
import os
import sys
import time
import zlib
import json
import textwrap

PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_FILE = os.path.join(PARENT, "qa_engine", "GhostQAEngine.py")
VAR_DIR = os.path.dirname(os.path.abspath(__file__))


# ─── Parser ───────────────────────────────────────────────────────────

def parse_file(filepath):
    with open(filepath) as f:
        source = f.read()
    tree = ast.parse(source)
    classes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a.arg for a in item.args.args]
                code = ast.get_source_segment(source, item) or ""
                methods.append({
                    "name": item.name,
                    "params": ", ".join(params),
                    "code": code,
                    "is_dunder": 1 if item.name.startswith("__") and item.name.endswith("__") else 0,
                    "line_start": item.lineno,
                    "line_end": item.end_lineno or item.lineno,
                    "returns_tuple3": 1 if "return (" in code and ", " in code else 0,
                })
        class_code = ast.get_source_segment(source, node) or ""
        docstring = ast.get_docstring(node) or ""
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
        has_init = any(m["name"] == "__init__" for m in methods)
        has_run = any(m["name"] == "Run" for m in methods)
        has_state = "self.state" in class_code or 'self["state"]' in class_code
        has_self_ = "self._" in class_code
        classes.append({
            "name": node.name,
            "code": class_code,
            "docstring": docstring.strip(),
            "line_start": node.lineno,
            "bases": ",".join(bases),
            "methods": methods,
            "has_init": has_init,
            "has_run": has_run,
            "has_state": has_state,
            "has_self_": has_self_,
            "is_vbstyle": has_init and has_run and has_state,
        })
    return classes


# ─── 20 Schema Definitions ────────────────────────────────────────────

def v01_minimal(conn, classes):
    """V01: Minimal — classes + methods, code only."""
    c = conn.cursor()
    c.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT, source_file TEXT)")
    c.execute("CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))")
    for cls in classes:
        c.execute("INSERT INTO classes (class_name, class_code, source_file) VALUES (?,?,?)", (cls["name"], cls["code"], TARGET_FILE))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_id, method_name, method_code) VALUES (?,?,?)", (cid, m["name"], m["code"]))
    conn.commit()


def v02_vb_code_test_clone(conn, classes):
    """V02: vb_code_test clone — domain, role, return_type, params, is_dunder."""
    c = conn.cursor()
    c.execute("""CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, domain TEXT, role TEXT,
        return_type TEXT, description TEXT, class_code TEXT, source_id INTEGER, created_at TEXT)""")
    c.execute("""CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, params TEXT,
        method_code TEXT, is_dunder INTEGER DEFAULT 0, line_start INTEGER, created_at TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))""")
    for cls in classes:
        c.execute("INSERT INTO classes (class_name, description, class_code) VALUES (?,?,?)", (cls["name"], cls["docstring"], cls["code"]))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_id, method_name, params, method_code, is_dunder, line_start) VALUES (?,?,?,?,?,?)",
                      (cid, m["name"], m["params"], m["code"], m["is_dunder"], m["line_start"]))
    conn.commit()


def v03_token_registry_style(conn, classes):
    """V03: token_registry style — boot_stage, boot_priority, execution_mode, bracket."""
    c = conn.cursor()
    c.execute("""CREATE TABLE classes (id INTEGER PRIMARY KEY, name TEXT, description TEXT, bracket TEXT,
        boot_stage TEXT, boot_priority INTEGER, memunit_entry_flag INTEGER DEFAULT 0, execution_mode TEXT)""")
    c.execute("""CREATE TABLE methods (id INTEGER PRIMARY KEY, uuid TEXT, class_id INTEGER, name TEXT, code TEXT,
        description TEXT, bracket TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))""")
    for cls in classes:
        c.execute("INSERT INTO classes (name, description) VALUES (?,?)", (cls["name"], cls["docstring"]))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (uuid, class_id, name, code) VALUES (?,?,?,?)",
                      (f"{cls['name']}_{m['name']}", cid, m["name"], m["code"]))
    conn.commit()


def v04_vb_shared_style(conn, classes):
    """V04: vb_shared style — versioning, code_registry as separate table."""
    c = conn.cursor()
    c.execute("""CREATE TABLE code_classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT,
        description TEXT, version INTEGER DEFAULT 1, created_at TEXT)""")
    c.execute("""CREATE TABLE code_registry (id INTEGER PRIMARY KEY, token_name TEXT, language TEXT, code TEXT,
        description TEXT, version INTEGER DEFAULT 1, code_classes_id INTEGER, FOREIGN KEY(code_classes_id) REFERENCES code_classes(id))""")
    for cls in classes:
        c.execute("INSERT INTO code_classes (class_name, class_code, description) VALUES (?,?,?)", (cls["name"], cls["code"], cls["docstring"]))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO code_registry (token_name, language, code, code_classes_id) VALUES (?,?,?,?)",
                      (f"[@{m['name']}]", "python", m["code"], cid))
    conn.commit()


def v05_full_governance(conn, classes):
    """V05: Full governance — classes + methods + violations + compliance."""
    c = conn.cursor()
    c.execute("""CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT,
        is_vbstyle INTEGER, has_run_method INTEGER, has_tuple3 INTEGER)""")
    c.execute("""CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT,
        is_vbstyle INTEGER, returns_tuple3 INTEGER, FOREIGN KEY(class_id) REFERENCES classes(id))""")
    c.execute("""CREATE TABLE violations (id INTEGER PRIMARY KEY, method_id INTEGER, rule_id TEXT, kind TEXT, message TEXT, FOREIGN KEY(method_id) REFERENCES methods(id))""")
    c.execute("""CREATE TABLE compliance (method_id INTEGER PRIMARY KEY, violation_count INTEGER DEFAULT 0, last_scanned TEXT)""")
    for cls in classes:
        c.execute("INSERT INTO classes (class_name, class_code, is_vbstyle, has_run_method, has_tuple3) VALUES (?,?,?,?,?)",
                  (cls["name"], cls["code"], cls["is_vbstyle"], cls["has_run"], 1 if cls["has_run"] else 0))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_id, method_name, method_code, is_vbstyle, returns_tuple3) VALUES (?,?,?,?,?)",
                      (cid, m["name"], m["code"], m["returns_tuple3"], m["returns_tuple3"]))
            mid = c.lastrowid
            vcount = 0
            if "self._" in m["code"]:
                c.execute("INSERT INTO violations (method_id, rule_id, kind, message) VALUES (?,?,?,?)",
                          (mid, "INTSTATE", "self._", "self._ used instead of self.state"))
                vcount += 1
            if "print(" in m["code"]:
                c.execute("INSERT INTO violations (method_id, rule_id, kind, message) VALUES (?,?,?,?)",
                          (mid, "PRINT", "print", "print() used"))
                vcount += 1
            c.execute("INSERT INTO compliance (method_id, violation_count) VALUES (?,?)", (mid, vcount))
    conn.commit()


def v06_orchestrated(conn, classes):
    """V06: Orchestrated — classes + methods + pipeline orchestration."""
    c = conn.cursor()
    c.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT)")
    c.execute("CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))")
    c.execute("CREATE TABLE orchestration (id INTEGER PRIMARY KEY, pipeline TEXT, sequence INTEGER, class_id INTEGER, role TEXT)")
    for i, cls in enumerate(classes):
        c.execute("INSERT INTO classes (class_name, class_code) VALUES (?,?)", (cls["name"], cls["code"]))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_id, method_name, method_code) VALUES (?,?,?)", (cid, m["name"], m["code"]))
        c.execute("INSERT INTO orchestration (pipeline, sequence, class_id, role) VALUES (?,?,?,?)",
                  ("qa_pipeline", i+1, cid, cls["name"].lower()))
    conn.commit()


def v07_executable(conn, classes):
    """V07: Executable — classes + methods + execution_log."""
    c = conn.cursor()
    c.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT)")
    c.execute("CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))")
    c.execute("CREATE TABLE execution_log (id INTEGER PRIMARY KEY, execution_id TEXT, method_id INTEGER, status TEXT, result TEXT, started_at TEXT, completed_at TEXT)")
    for cls in classes:
        c.execute("INSERT INTO classes (class_name, class_code) VALUES (?,?)", (cls["name"], cls["code"]))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_id, method_name, method_code) VALUES (?,?,?)", (cid, m["name"], m["code"]))
    conn.commit()


def v08_ast_nodes(conn, classes):
    """V08: AST nodes — finest granularity, each statement stored."""
    c = conn.cursor()
    c.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT, class_code TEXT)")
    c.execute("CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))")
    c.execute("CREATE TABLE ast_nodes (id INTEGER PRIMARY KEY, method_id INTEGER, node_type TEXT, line_start INTEGER, code TEXT, FOREIGN KEY(method_id) REFERENCES methods(id))")
    for cls in classes:
        c.execute("INSERT INTO classes (class_name, class_code) VALUES (?,?)", (cls["name"], cls["code"]))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_id, method_name, method_code) VALUES (?,?,?)", (cid, m["name"], m["code"]))
            mid = c.lastrowid
            try:
                tree = ast.parse(m["code"])
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Assign, ast.Return, ast.If, ast.For, ast.While, ast.Expr)):
                        seg = ast.get_source_segment(m["code"], node)
                        if seg:
                            c.execute("INSERT INTO ast_nodes (method_id, node_type, line_start, code) VALUES (?,?,?,?)",
                                      (mid, type(node).__name__, node.lineno, seg))
            except Exception:
                pass
    conn.commit()


def v09_flat(conn, classes):
    """V09: Flat — one table, everything denormalized."""
    c = conn.cursor()
    c.execute("CREATE TABLE code_flat (id INTEGER PRIMARY KEY, class_name TEXT, method_name TEXT, class_code TEXT, method_code TEXT, params TEXT, is_dunder INTEGER, line_start INTEGER)")
    for cls in classes:
        for m in cls["methods"]:
            c.execute("INSERT INTO code_flat (class_name, method_name, class_code, method_code, params, is_dunder, line_start) VALUES (?,?,?,?,?,?,?)",
                      (cls["name"], m["name"], cls["code"], m["code"], m["params"], m["is_dunder"], m["line_start"]))
    conn.commit()


def v10_method_centric(conn, classes):
    """V10: Method-centric — methods table only, class info as columns."""
    c = conn.cursor()
    c.execute("""CREATE TABLE methods (id INTEGER PRIMARY KEY, class_name TEXT, method_name TEXT, method_code TEXT,
        params TEXT, class_code TEXT, class_docstring TEXT, is_dunder INTEGER, line_start INTEGER,
        is_vbstyle INTEGER, returns_tuple3 INTEGER)""")
    for cls in classes:
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_name, method_name, method_code, params, class_code, class_docstring, is_dunder, line_start, is_vbstyle, returns_tuple3) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (cls["name"], m["name"], m["code"], m["params"], cls["code"], cls["docstring"], m["is_dunder"], m["line_start"], cls["is_vbstyle"], m["returns_tuple3"]))
    conn.commit()


def v11_bracket_metadata(conn, classes):
    """V11: Bracket metadata — VBStyle bracket tokens as separate table."""
    c = conn.cursor()
    c.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT, bracket TEXT)")
    c.execute("CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT, bracket TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))")
    c.execute("CREATE TABLE brackets (id INTEGER PRIMARY KEY, entity_type TEXT, entity_id INTEGER, token TEXT, value TEXT)")
    for cls in classes:
        bracket = f"[@VBSTYLE]{{[@class<{cls['name']}>][@return<Tuple3>]}}"
        c.execute("INSERT INTO classes (class_name, class_code, bracket) VALUES (?,?,?)", (cls["name"], cls["code"], bracket))
        cid = c.lastrowid
        c.execute("INSERT INTO brackets (entity_type, entity_id, token, value) VALUES (?,?,?,?)", ("class", cid, "@class", cls["name"]))
        c.execute("INSERT INTO brackets (entity_type, entity_id, token, value) VALUES (?,?,?,?)", ("class", cid, "@return", "Tuple3"))
        for m in cls["methods"]:
            mbracket = f"[@method<{m['name']}>]"
            c.execute("INSERT INTO methods (class_id, method_name, method_code, bracket) VALUES (?,?,?,?)", (cid, m["name"], m["code"], mbracket))
            mid = c.lastrowid
            c.execute("INSERT INTO brackets (entity_type, entity_id, token, value) VALUES (?,?,?,?)", ("method", mid, "@method", m["name"]))
    conn.commit()


def v12_dependency_graph(conn, classes):
    """V12: Dependency graph — methods + method_dependencies."""
    c = conn.cursor()
    c.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT, bases TEXT)")
    c.execute("CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))")
    c.execute("CREATE TABLE method_deps (id INTEGER PRIMARY KEY, method_id INTEGER, dep_class TEXT, dep_method TEXT)")
    for cls in classes:
        c.execute("INSERT INTO classes (class_name, class_code, bases) VALUES (?,?,?)", (cls["name"], cls["code"], cls["bases"]))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_id, method_name, method_code) VALUES (?,?,?)", (cid, m["name"], m["code"]))
            mid = c.lastrowid
            for other_cls in classes:
                if other_cls["name"] in m["code"] and other_cls["name"] != cls["name"]:
                    for other_m in other_cls["methods"]:
                        if f".{other_m['name']}(" in m["code"] or f".{other_m['name']} " in m["code"]:
                            c.execute("INSERT INTO method_deps (method_id, dep_class, dep_method) VALUES (?,?,?)",
                                      (mid, other_cls["name"], other_m["name"]))
    conn.commit()


def v13_versioned(conn, classes):
    """V13: Versioned — append-only, no updates, full history."""
    c = conn.cursor()
    c.execute("""CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT, class_code TEXT, version INTEGER DEFAULT 1,
        is_current INTEGER DEFAULT 1, created_at TEXT)""")
    c.execute("""CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT,
        version INTEGER DEFAULT 1, is_current INTEGER DEFAULT 1, created_at TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))""")
    for cls in classes:
        c.execute("INSERT INTO classes (class_name, class_code, version, is_current) VALUES (?,?,?,?)",
                  (cls["name"], cls["code"], 1, 1))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_id, method_name, method_code, version, is_current) VALUES (?,?,?,?,?)",
                      (cid, m["name"], m["code"], 1, 1))
    conn.commit()


def v14_search_optimized(conn, classes):
    """V14: Search-optimized — FTS5 full-text search on method_code."""
    c = conn.cursor()
    c.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT)")
    c.execute("CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))")
    c.execute("CREATE VIRTUAL TABLE methods_fts USING fts5(method_id, method_code, method_name)")
    for cls in classes:
        c.execute("INSERT INTO classes (class_name, class_code) VALUES (?,?)", (cls["name"], cls["code"]))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO methods (class_id, method_name, method_code) VALUES (?,?,?)", (cid, m["name"], m["code"]))
            mid = c.lastrowid
            c.execute("INSERT INTO methods_fts (method_id, method_code, method_name) VALUES (?,?,?)", (mid, m["code"], m["name"]))
    conn.commit()


def v15_compressed(conn, classes):
    """V15: Compressed — store code zlib-compressed."""
    c = conn.cursor()
    c.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code BLOB, code_size INTEGER)")
    c.execute("CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code BLOB, code_size INTEGER, FOREIGN KEY(class_id) REFERENCES classes(id))")
    for cls in classes:
        compressed = zlib.compress(cls["code"].encode())
        c.execute("INSERT INTO classes (class_name, class_code, code_size) VALUES (?,?,?)", (cls["name"], compressed, len(cls["code"])))
        cid = c.lastrowid
        for m in cls["methods"]:
            mc = zlib.compress(m["code"].encode())
            c.execute("INSERT INTO methods (class_id, method_name, method_code, code_size) VALUES (?,?,?,?)",
                      (cid, m["name"], mc, len(m["code"])))
    conn.commit()


def v16_json_columns(conn, classes):
    """V16: JSON columns — store metadata as JSON in a single column."""
    c = conn.cursor()
    c.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT, metadata TEXT)")
    c.execute("CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT, metadata TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))")
    for cls in classes:
        meta = json.dumps({"docstring": cls["docstring"], "bases": cls["bases"], "is_vbstyle": cls["is_vbstyle"],
                           "has_init": cls["has_init"], "has_run": cls["has_run"], "has_state": cls["has_state"]})
        c.execute("INSERT INTO classes (class_name, class_code, metadata) VALUES (?,?,?)", (cls["name"], cls["code"], meta))
        cid = c.lastrowid
        for m in cls["methods"]:
            mmeta = json.dumps({"params": m["params"], "is_dunder": m["is_dunder"], "line_start": m["line_start"],
                                "returns_tuple3": m["returns_tuple3"]})
            c.execute("INSERT INTO methods (class_id, method_name, method_code, metadata) VALUES (?,?,?,?)",
                      (cid, m["name"], m["code"], mmeta))
    conn.commit()


def v17_modular(conn, classes):
    """V17: Modular — split into code + governance + exec in same DB with clear boundaries."""
    c = conn.cursor()
    c.execute("CREATE TABLE code_classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT, source_file TEXT)")
    c.execute("CREATE TABLE code_methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT, FOREIGN KEY(class_id) REFERENCES code_classes(id))")
    c.execute("CREATE TABLE gov_violations (id INTEGER PRIMARY KEY, method_id INTEGER, rule_id TEXT, message TEXT)")
    c.execute("CREATE TABLE exec_log (id INTEGER PRIMARY KEY, method_id INTEGER, status TEXT, result TEXT, timestamp TEXT)")
    for cls in classes:
        c.execute("INSERT INTO code_classes (class_name, class_code, source_file) VALUES (?,?,?)", (cls["name"], cls["code"], TARGET_FILE))
        cid = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO code_methods (class_id, method_name, method_code) VALUES (?,?,?)", (cid, m["name"], m["code"]))
            mid = c.lastrowid
            if "self._" in m["code"]:
                c.execute("INSERT INTO gov_violations (method_id, rule_id, message) VALUES (?,?,?)", (mid, "INTSTATE", "self._ used"))
    conn.commit()


def v18_event_sourced(conn, classes):
    """V18: Event-sourced — append-only event log, reconstruct state from events."""
    c = conn.cursor()
    c.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, event_type TEXT, entity_type TEXT, entity_name TEXT, data TEXT, timestamp TEXT)")
    for cls in classes:
        c.execute("INSERT INTO events (event_type, entity_type, entity_name, data) VALUES (?,?,?,?)",
                  ("CREATE", "class", cls["name"], json.dumps({"code": cls["code"], "docstring": cls["docstring"]})))
        for m in cls["methods"]:
            c.execute("INSERT INTO events (event_type, entity_type, entity_name, data) VALUES (?,?,?,?)",
                      ("CREATE", "method", f"{cls['name']}.{m['name']}", json.dumps({"code": m["code"], "params": m["params"]})))
    conn.commit()


def v19_graph_model(conn, classes):
    """V19: Graph model — nodes and edges, class=nodes, calls=edges."""
    c = conn.cursor()
    c.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, node_type TEXT, name TEXT, code TEXT)")
    c.execute("CREATE TABLE edges (id INTEGER PRIMARY KEY, source_id INTEGER, target_id INTEGER, edge_type TEXT)")
    for cls in classes:
        c.execute("INSERT INTO nodes (node_type, name, code) VALUES (?,?,?)", ("class", cls["name"], cls["code"]))
        cls_node = c.lastrowid
        for m in cls["methods"]:
            c.execute("INSERT INTO nodes (node_type, name, code) VALUES (?,?,?)", ("method", f"{cls['name']}.{m['name']}", m["code"]))
            m_node = c.lastrowid
            c.execute("INSERT INTO edges (source_id, target_id, edge_type) VALUES (?,?,?)", (cls_node, m_node, "contains"))
            for other_cls in classes:
                if other_cls["name"] in m["code"] and other_cls["name"] != cls["name"]:
                    c.execute("SELECT id FROM nodes WHERE name=? AND node_type='class'", (other_cls["name"],))
                    row = c.fetchone()
                    if row:
                        c.execute("INSERT INTO edges (source_id, target_id, edge_type) VALUES (?,?,?)", (m_node, row[0], "calls"))
    conn.commit()


def v20_hybrid(conn, classes):
    """V20: Hybrid best — code + governance + orchestration + exec + search + versioning."""
    c = conn.cursor()
    c.execute("""CREATE TABLE classes (id INTEGER PRIMARY KEY, class_name TEXT UNIQUE, class_code TEXT,
        domain TEXT, description TEXT, source_file TEXT, line_start INTEGER,
        is_vbstyle INTEGER, has_run_method INTEGER, has_tuple3 INTEGER,
        version INTEGER DEFAULT 1, created_at TEXT)""")
    c.execute("""CREATE TABLE methods (id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT, method_code TEXT,
        params TEXT, signature TEXT, is_dunder INTEGER, is_vbstyle INTEGER, returns_tuple3 INTEGER,
        line_start INTEGER, version INTEGER DEFAULT 1, created_at TEXT, FOREIGN KEY(class_id) REFERENCES classes(id))""")
    c.execute("CREATE TABLE orchestration (id INTEGER PRIMARY KEY, pipeline TEXT, sequence INTEGER, class_id INTEGER, role TEXT)")
    c.execute("CREATE TABLE violations (id INTEGER PRIMARY KEY, method_id INTEGER, rule_id TEXT, kind TEXT, message TEXT)")
    c.execute("CREATE TABLE execution_log (id INTEGER PRIMARY KEY, method_id INTEGER, status TEXT, result TEXT, started_at TEXT, completed_at TEXT)")
    c.execute("CREATE VIRTUAL TABLE search_idx USING fts5(method_id, method_code, class_name, method_name)")
    for i, cls in enumerate(classes):
        c.execute("""INSERT INTO classes (class_name, class_code, description, source_file, line_start,
            is_vbstyle, has_run_method, has_tuple3, version) VALUES (?,?,?,?,?,?,?,?,?)""",
            (cls["name"], cls["code"], cls["docstring"], TARGET_FILE, cls["line_start"],
             cls["is_vbstyle"], cls["has_run"], 1, 1))
        cid = c.lastrowid
        c.execute("INSERT INTO orchestration (pipeline, sequence, class_id, role) VALUES (?,?,?,?)",
                  ("qa_pipeline", i+1, cid, cls["name"].lower()))
        for m in cls["methods"]:
            sig = f"{m['name']}({m['params']})"
            c.execute("""INSERT INTO methods (class_id, method_name, method_code, params, signature, is_dunder,
                is_vbstyle, returns_tuple3, line_start, version) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (cid, m["name"], m["code"], m["params"], sig, m["is_dunder"], m["returns_tuple3"], m["returns_tuple3"], m["line_start"], 1))
            mid = c.lastrowid
            c.execute("INSERT INTO search_idx (method_id, method_code, class_name, method_name) VALUES (?,?,?,?)",
                      (mid, m["code"], cls["name"], m["name"]))
            if "self._" in m["code"]:
                c.execute("INSERT INTO violations (method_id, rule_id, kind, message) VALUES (?,?,?,?)",
                          (mid, "INTSTATE", "self._", "self._ used instead of self.state"))
            if "print(" in m["code"]:
                c.execute("INSERT INTO violations (method_id, rule_id, kind, message) VALUES (?,?,?,?)",
                          (mid, "PRINT", "print", "print() used"))
    conn.commit()


# ─── Benchmark ────────────────────────────────────────────────────────

VARIATIONS = [
    ("v01_minimal", v01_minimal, "Minimal: classes + methods, code only"),
    ("v02_vb_code_test", v02_vb_code_test_clone, "vb_code_test clone: domain, role, params, is_dunder"),
    ("v03_token_registry", v03_token_registry_style, "token_registry: boot_stage, bracket, uuid"),
    ("v04_vb_shared", v04_vb_shared_style, "vb_shared: versioning, code_registry table"),
    ("v05_governance", v05_full_governance, "Full governance: + violations + compliance"),
    ("v06_orchestrated", v06_orchestrated, "Orchestrated: + pipeline orchestration"),
    ("v07_executable", v07_executable, "Executable: + execution_log"),
    ("v08_ast_nodes", v08_ast_nodes, "AST nodes: finest granularity, each statement"),
    ("v09_flat", v09_flat, "Flat: one denormalized table"),
    ("v10_method_centric", v10_method_centric, "Method-centric: methods only, class as columns"),
    ("v11_bracket_meta", v11_bracket_metadata, "Bracket metadata: VBStyle tokens as table"),
    ("v12_dependency_graph", v12_dependency_graph, "Dependency graph: + method_deps"),
    ("v13_versioned", v13_versioned, "Versioned: append-only, is_current flag"),
    ("v14_search_fts", v14_search_optimized, "Search-optimized: FTS5 on method_code"),
    ("v15_compressed", v15_compressed, "Compressed: zlib on code columns"),
    ("v16_json_cols", v16_json_columns, "JSON columns: metadata as JSON"),
    ("v17_modular", v17_modular, "Modular: code + governance + exec boundaries"),
    ("v18_event_sourced", v18_event_sourced, "Event-sourced: append-only event log"),
    ("v19_graph_model", v19_graph_model, "Graph model: nodes + edges"),
    ("v20_hybrid_best", v20_hybrid, "Hybrid best: code + gov + orch + exec + search + versioning"),
]


def benchmark_variation(name, builder, desc, classes):
    db_path = os.path.join(VAR_DIR, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)

    # Ingest time
    t0 = time.time()
    builder(conn, classes)
    ingest_ms = (time.time() - t0) * 1000

    c = conn.cursor()

    # Table count
    tables = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]

    # Row count
    total_rows = 0
    for t in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%' AND name NOT LIKE '%_data%' AND name NOT LIKE '%_idx%' AND name NOT LIKE '%_config%' AND name NOT LIKE '%_content%' AND name NOT LIKE '%_docsize%'").fetchall():
        cnt = c.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
        total_rows += cnt

    # Query: find all methods with self._
    t0 = time.time()
    try:
        if name == "v09_flat":
            self_count = c.execute("SELECT COUNT(*) FROM code_flat WHERE method_code LIKE '%self._%'").fetchone()[0]
        elif name == "v10_method_centric":
            self_count = c.execute("SELECT COUNT(*) FROM methods WHERE method_code LIKE '%self._%'").fetchone()[0]
        elif name == "v18_event_sourced":
            self_count = c.execute("SELECT COUNT(*) FROM events WHERE data LIKE '%self._%' AND entity_type='method'").fetchone()[0]
        elif name == "v15_compressed":
            self_count = 0
            for row in c.execute("SELECT method_code FROM methods").fetchall():
                try:
                    code = zlib.decompress(row[0]).decode()
                    if "self._" in code:
                        self_count += 1
                except Exception:
                    pass
        else:
            self_count = c.execute("SELECT COUNT(*) FROM methods WHERE method_code LIKE '%self._%'").fetchone()[0]
    except Exception:
        self_count = -1
    query_ms = (time.time() - t0) * 1000

    # Exec: reconstruct and run a method
    t0 = time.time()
    exec_ok = False
    try:
        if name == "v09_flat":
            row = c.execute("SELECT class_code FROM code_flat WHERE class_name='ModeRouter' LIMIT 1").fetchone()
        elif name == "v10_method_centric":
            row = c.execute("SELECT class_code FROM methods WHERE class_name='ModeRouter' LIMIT 1").fetchone()
        elif name == "v18_event_sourced":
            row = c.execute("SELECT data FROM events WHERE entity_name='ModeRouter' AND event_type='CREATE' LIMIT 1").fetchone()
            if row:
                code = json.loads(row[0])["code"]
                ns = {}
                exec(code, ns)
                cls = ns.get("ModeRouter")
                if cls:
                    inst = cls()
                    result = inst.Run("route", {"qtype": "yes_no", "features": ["yes_no_form"]})
                    exec_ok = result[0] == 1
        elif name == "v15_compressed":
            row = c.execute("SELECT class_code FROM classes WHERE class_name='ModeRouter'").fetchone()
            if row:
                code = zlib.decompress(row[0]).decode()
                ns = {}
                exec(code, ns)
                cls = ns.get("ModeRouter")
                if cls:
                    inst = cls()
                    result = inst.Run("route", {"qtype": "yes_no", "features": ["yes_no_form"]})
                    exec_ok = result[0] == 1
        else:
            row = c.execute("SELECT class_code FROM classes WHERE class_name='ModeRouter'").fetchone()
            if not row:
                row = c.execute("SELECT class_code FROM code_classes WHERE class_name='ModeRouter'").fetchone()
            if row:
                code = row[0]
                ns = {}
                exec(code, ns)
                cls = ns.get("ModeRouter")
                if cls:
                    inst = cls()
                    result = inst.Run("route", {"qtype": "yes_no", "features": ["yes_no_form"]})
                    exec_ok = result[0] == 1
    except Exception:
        exec_ok = False
    exec_ms = (time.time() - t0) * 1000

    # DB size
    db_size = os.path.getsize(db_path)

    # Can check compliance?
    has_violations = tables > 2 and name not in ("v01_minimal", "v09_flat", "v10_method_centric")

    # Can search code?
    can_search = name in ("v14_search_fts", "v20_hybrid_best") or True  # all can LIKE search

    # Can version?
    can_version = name in ("v04_vb_shared", "v13_versioned", "v20_hybrid_best")

    # Can orchestrate?
    can_orchestrate = name in ("v06_orchestrated", "v17_modular", "v20_hybrid_best")

    # Can exec from DB?
    can_exec = exec_ok

    conn.close()

    return {
        "name": name,
        "desc": desc,
        "tables": tables,
        "rows": total_rows,
        "ingest_ms": round(ingest_ms, 1),
        "query_ms": round(query_ms, 1),
        "exec_ms": round(exec_ms, 1),
        "exec_ok": exec_ok,
        "db_size": db_size,
        "self_count": self_count,
        "has_violations": has_violations,
        "can_version": can_version,
        "can_orchestrate": can_orchestrate,
        "can_exec": can_exec,
    }


def main():
    print("Parsing GhostQAEngine.py...")
    classes = parse_file(TARGET_FILE)
    print(f"  Found {len(classes)} classes, {sum(len(c['methods']) for c in classes)} methods\n")

    results = []
    for name, builder, desc in VARIATIONS:
        print(f"  Building {name}...", end=" ", flush=True)
        try:
            r = benchmark_variation(name, builder, desc, classes)
            results.append(r)
            print(f"OK ({r['tables']} tables, {r['rows']} rows, {r['db_size']} bytes)")
        except Exception as e:
            print(f"FAIL: {e}")
            results.append({"name": name, "desc": desc, "error": str(e)})

    # Report
    print("\n" + "=" * 130)
    print("20 VARIATION COMPARISON")
    print("=" * 130)
    print(f"\n{'Name':22s} {'Tables':>6s} {'Rows':>6s} {'Ingest':>8s} {'Query':>8s} {'Exec':>8s} {'Size':>8s} {'ExecOK':>7s} {'Viol':>5s} {'Ver':>4s} {'Orch':>5s} {'self._':>7s}")
    print("-" * 130)

    for r in results:
        if "error" in r:
            print(f"{r['name']:22s} ERROR: {r['error'][:50]}")
            continue
        print(f"{r['name']:22s} {r['tables']:6d} {r['rows']:6d} {r['ingest_ms']:7.1f}ms {r['query_ms']:7.1f}ms {r['exec_ms']:7.1f}ms {r['db_size']:7d}b {'Y' if r['exec_ok'] else 'X':>7s} {'Y' if r['has_violations'] else 'X':>5s} {'Y' if r['can_version'] else 'X':>4s} {'Y' if r['can_orchestrate'] else 'X':>5s} {r['self_count']:7d}")

    # Feature matrix
    print("\n" + "=" * 130)
    print("FEATURE MATRIX")
    print("=" * 130)
    print(f"\n{'Name':22s} {'Exec':>5s} {'Govern':>7s} {'Search':>7s} {'Version':>8s} {'Orchest':>8s} {'Compress':>9s} {'AST':>5s} {'Graph':>6s} {'Events':>7s}")
    print("-" * 90)

    features = {
        "v01_minimal": ["Y","N","Y","N","N","N","N","N","N","N"],
        "v02_vb_code_test": ["Y","N","Y","N","N","N","N","N","N","N"],
        "v03_token_registry": ["Y","N","Y","N","N","N","N","N","N","N"],
        "v04_vb_shared": ["Y","N","Y","Y","N","N","N","N","N","N"],
        "v05_governance": ["Y","Y","Y","N","N","N","N","N","N","N"],
        "v06_orchestrated": ["Y","N","Y","N","Y","N","N","N","N","N"],
        "v07_executable": ["Y","N","Y","N","N","N","N","N","N","N"],
        "v08_ast_nodes": ["Y","N","Y","N","N","N","N","Y","N","N"],
        "v09_flat": ["Y","N","Y","N","N","N","N","N","N","N"],
        "v10_method_centric": ["Y","N","Y","N","N","N","N","N","N","N"],
        "v11_bracket_meta": ["Y","N","Y","N","N","N","N","N","N","N"],
        "v12_dependency_graph": ["Y","N","Y","N","N","N","N","N","Y","N"],
        "v13_versioned": ["Y","N","Y","Y","N","N","N","N","N","N"],
        "v14_search_fts": ["Y","N","Y","N","N","N","N","N","N","N"],
        "v15_compressed": ["Y","N","N","N","N","N","Y","N","N","N"],
        "v16_json_cols": ["Y","N","Y","N","N","N","N","N","N","N"],
        "v17_modular": ["Y","Y","Y","N","N","N","N","N","N","N"],
        "v18_event_sourced": ["Y","N","Y","Y","N","N","N","N","N","Y"],
        "v19_graph_model": ["Y","N","Y","N","N","N","N","N","Y","N"],
        "v20_hybrid_best": ["Y","Y","Y","Y","Y","N","N","N","N","N"],
    }

    for name, _, _ in VARIATIONS:
        f = features.get(name, ["?"]*10)
        print(f"{name:22s} {f[0]:>5s} {f[1]:>7s} {f[2]:>7s} {f[3]:>8s} {f[4]:>8s} {f[5]:>9s} {f[6]:>5s} {f[7]:>6s} {f[8]:>7s}")

    # Winners
    print("\n" + "=" * 130)
    print("WINNERS BY CATEGORY")
    print("=" * 130)

    valid = [r for r in results if "error" not in r]
    if valid:
        fastest_ingest = min(valid, key=lambda x: x["ingest_ms"])
        fastest_query = min(valid, key=lambda x: x["query_ms"])
        fastest_exec = min(valid, key=lambda x: x["exec_ms"] if x["exec_ok"] else 9999)
        smallest = min(valid, key=lambda x: x["db_size"])
        most_features = max(valid, key=lambda x: sum([x["has_violations"], x["can_version"], x["can_orchestrate"], x["exec_ok"]]))

        print(f"\n  Fastest ingest:   {fastest_ingest['name']} ({fastest_ingest['ingest_ms']}ms)")
        print(f"  Fastest query:    {fastest_query['name']} ({fastest_query['query_ms']}ms)")
        print(f"  Fastest exec:     {fastest_exec['name']} ({fastest_exec['exec_ms']}ms)")
        print(f"  Smallest DB:      {smallest['name']} ({smallest['db_size']} bytes)")
        print(f"  Most features:    {most_features['name']} (violations={most_features['has_violations']}, version={most_features['can_version']}, orch={most_features['can_orchestrate']}, exec={most_features['can_exec']})")


if __name__ == "__main__":
    main()
