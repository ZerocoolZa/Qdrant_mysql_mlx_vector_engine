#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<One-time build utility for populating twin DB tables. NOT VBStyle: no VBStyle headers no class no Run() dispatch no Tuple3 returns. Has 8 print() calls. Multiple standalone functions. Self-describes as NOT a VBStyle engine.>][@todos<1. Add VBStyle headers. 2. Remove print() calls. 3. Wrap in class with Run() dispatch and Tuple3 returns.>]}
"""
populate_twin.py -- Phase 1 population script for the Project Digital Twin.

One-time build utility (NOT a VBStyle engine; mirrors the role of
build_registry.py / ingest_to_db.py in this project). AST-parses every .py
file in the Dom_Graph directory and populates the files, classes, methods and
edges tables defined in DEVIN_SPEC_DOMAIN_TWIN.md.

Idempotent: clears the four twin tables before re-inserting so re-runs are safe.
"""
import ast
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dom_graph_work.db")

SELF_UNDERSCORE_RE = re.compile(r"self\._")
TUPLE3_RETURN_RE = re.compile(r"return\s*\(\s*[01]\s*,")


def file_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_imports(tree):
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append(mod + "." + alias.name if mod else alias.name)
    return imports


def method_signature(node):
    args = []
    for a in node.args.posonlyargs + node.args.args:
        args.append(a.arg)
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    for a in node.args.kwonlyargs:
        args.append(a.arg)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    return node.name + "(" + ", ".join(args) + ")"


def method_param_names(node):
    params = []
    for a in node.args.posonlyargs + node.args.args:
        params.append(a.arg)
    if node.args.vararg:
        params.append(node.args.vararg.arg)
    for a in node.args.kwonlyargs:
        params.append(a.arg)
    if node.args.kwarg:
        params.append(node.args.kwarg.arg)
    return params


def detect_tuple3_return(node):
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and isinstance(child.value, ast.Tuple):
            elts = child.value.elts
            if len(elts) >= 1 and isinstance(elts[0], ast.Constant) and elts[0].value in (0, 1):
                return 1
    return 0


def detect_self_underscore(source_lines):
    for line in source_lines:
        if SELF_UNDERSCORE_RE.search(line):
            return 1
    return 0


def detect_has_print(source_lines):
    for line in source_lines:
        stripped = line.lstrip()
        if stripped.startswith("print("):
            return 1
    return 0


def detect_has_decorator(node):
    if node.decorator_list:
        return 1
    return 0


def extract_calls(node):
    calls = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute):
                calls.add(func.attr)
            elif isinstance(func, ast.Name):
                calls.add(func.id)
    return sorted(c for c in calls if not c.startswith("<"))


def get_end_line(node, source_lines_count):
    if hasattr(node, "end_lineno") and node.end_lineno:
        return node.end_lineno
    end = node.lineno
    for child in ast.walk(node):
        ln = getattr(child, "lineno", None)
        if ln and ln > end:
            end = ln
        eln = getattr(child, "end_lineno", None)
        if eln and eln > end:
            end = eln
    return min(end, source_lines_count)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # Idempotent reset of twin tables (children first to satisfy FKs)
    cur.execute("DELETE FROM edges")
    cur.execute("DELETE FROM methods")
    cur.execute("DELETE FROM classes")
    cur.execute("DELETE FROM files")
    conn.commit()

    py_files = sorted(
        f for f in os.listdir(BASE_DIR)
        if f.endswith(".py") and os.path.isfile(os.path.join(BASE_DIR, f))
    )

    now = datetime.utcnow().isoformat()
    file_id_map = {}        # file_name -> file_id
    class_id_map = {}       # (file_name, class_name) -> class_id
    class_name_global = {}  # class_name -> [(file_id, class_id)]
    method_id_map = {}      # (file_name, class_name, method_name) -> method_id
    method_calls_map = {}   # method_id -> list of called names
    file_imports_map = {}   # file_name -> list of import strings

    # ---- PASS 1: files ----
    for fname in py_files:
        fpath = os.path.join(BASE_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            continue
        try:
            tree = ast.parse(content, filename=fname)
        except SyntaxError:
            # Skip files that do not parse (e.g. partial scripts)
            continue
        imports = extract_imports(tree)
        file_hash = file_sha256(content)
        size = os.path.getsize(fpath)
        class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        method_count = sum(
            1 for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) or isinstance(n, ast.AsyncFunctionDef)
        )
        cur.execute(
            "INSERT INTO files (file_name, path, extension, hash, size, imports, "
            "class_count, function_count, method_count, created, modified, language) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (fname, fpath, ".py", file_hash, size, json.dumps(imports),
             class_count, method_count, method_count, now, now, "python"),
        )
        fid = cur.lastrowid
        file_id_map[fname] = fid
        file_imports_map[fname] = imports

    conn.commit()

    # ---- PASS 2: classes + methods ----
    for fname in py_files:
        fpath = os.path.join(BASE_DIR, fname)
        fid = file_id_map.get(fname)
        if fid is None:
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            continue
        try:
            tree = ast.parse(content, filename=fname)
        except SyntaxError:
            continue
        source_lines = content.splitlines()
        line_count = len(source_lines)

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            cls_start = node.lineno
            cls_end = get_end_line(node, line_count)
            parent = ""
            if node.bases:
                base_names = []
                for b in node.bases:
                    if isinstance(b, ast.Name):
                        base_names.append(b.id)
                    elif isinstance(b, ast.Attribute):
                        base_names.append(b.attr)
                parent = ",".join(base_names)
            cls_methods = [
                m for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            has_run = 1 if any(m.name == "Run" for m in cls_methods) else 0
            cls_hash = file_sha256(ast.get_source_segment(content, node) or "")
            cur.execute(
                "INSERT INTO classes (file_id, class_name, parent, start_line, "
                "end_line, method_count, has_run_method, hash) VALUES (?,?,?,?,?,?,?,?)",
                (fid, node.name, parent, cls_start, cls_end,
                 len(cls_methods), has_run, cls_hash),
            )
            cid = cur.lastrowid
            class_id_map[(fname, node.name)] = cid
            class_name_global.setdefault(node.name, []).append((fid, cid))

            for m in cls_methods:
                m_start = m.lineno
                m_end = get_end_line(m, line_count)
                m_lines = source_lines[m_start - 1:m_end]
                m_code = "\n".join(m_lines)
                sig = method_signature(m)
                params = method_param_names(m)
                has_print = detect_has_print(m_lines)
                has_decorator = detect_has_decorator(m)
                has_self_underscore = detect_self_underscore(m_lines)
                returns_tuple3 = detect_tuple3_return(m)
                m_hash = file_sha256(m_code)
                is_dunder = 1 if m.name.startswith("__") and m.name.endswith("__") else 0
                calls = extract_calls(m)
                cur.execute(
                    "INSERT INTO methods (class_id, file_id, method_name, signature, "
                    "parameters, start_line, end_line, method_code, calls, is_dunder, "
                    "returns_tuple3, has_print, has_decorator, has_self_underscore, "
                    "line_count, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, fid, m.name, sig, json.dumps(params),
                     m_start, m_end, m_code, json.dumps(calls), is_dunder,
                     returns_tuple3, has_print, has_decorator, has_self_underscore,
                     len(m_lines), m_hash),
                )
                mid = cur.lastrowid
                method_id_map[(fname, node.name, m.name)] = mid
                method_calls_map[mid] = calls

    conn.commit()

    # ---- PASS 3: edges ----
    # 3a. file -> file (imports)
    # Build a lookup: module name (without .py) -> file_id
    module_to_file = {os.path.splitext(f)[0]: fid for f, fid in file_id_map.items()}
    file_name_to_id = dict(file_id_map)
    for fname, fid in file_id_map.items():
        for imp in file_imports_map.get(fname, []):
            top = imp.split(".")[0]
            dst_fid = module_to_file.get(top) or file_name_to_id.get(top + ".py")
            if dst_fid is not None and dst_fid != fid:
                cur.execute(
                    "INSERT INTO edges (src_type, src_id, dst_type, dst_id, "
                    "edge_type, evidence, created) VALUES (?,?,?,?,?,?,?)",
                    ("file", fid, "file", dst_fid, "imports", imp, now),
                )

    # 3b. class -> class (inheritance)
    for (fname, cls_name), cid in class_id_map.items():
        cur.execute("SELECT parent FROM classes WHERE class_id=?", (cid,))
        row = cur.fetchone()
        if not row or not row[0]:
            continue
        for parent_name in row[0].split(","):
            parent_name = parent_name.strip()
            if not parent_name:
                continue
            candidates = class_name_global.get(parent_name, [])
            for (pfid, pcid) in candidates:
                cur.execute(
                    "INSERT INTO edges (src_type, src_id, dst_type, dst_id, "
                    "edge_type, evidence, created) VALUES (?,?,?,?,?,?,?)",
                    ("class", cid, "class", pcid, "inherits",
                     parent_name, now),
                )

    # 3c. method -> method (calls)
    # Build a global method-name -> [method_id] index for resolution
    method_name_to_ids = {}
    for (fname, cls_name, mname), mid in method_id_map.items():
        method_name_to_ids.setdefault(mname, []).append(mid)
    for mid, calls in method_calls_map.items():
        for callee in calls:
            targets = method_name_to_ids.get(callee, [])
            for tid in targets:
                if tid == mid:
                    continue
                cur.execute(
                    "INSERT INTO edges (src_type, src_id, dst_type, dst_id, "
                    "edge_type, evidence, created) VALUES (?,?,?,?,?,?,?)",
                    ("method", mid, "method", tid, "calls", callee, now),
                )

    conn.commit()

    # ---- REPORT ----
    for tbl in ["files", "classes", "methods", "edges"]:
        cur.execute("SELECT COUNT(*) FROM " + tbl)
        print(tbl, cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
    print("methods.has_print=1", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM methods WHERE has_decorator=1")
    print("methods.has_decorator=1", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM methods WHERE has_self_underscore=1")
    print("methods.has_self_underscore=1", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=0")
    print("classes.has_run_method=0", cur.fetchone()[0])

    conn.close()


if __name__ == "__main__":
    main()
