#!/usr/bin/env python3
"""
Ingest all 73 impl_*.py files into v20_hybrid_best.db.

For each impl_*.py file:
  1. Parse the class with AST
  2. UPDATE the existing class row (replace stub class_code with real code)
     or INSERT a new class row if it doesn't exist (15 new domains)
  3. DELETE old methods for that class
  4. INSERT fresh method rows from the AST

This replaces the 58 stub entries with real functional implementations
and adds 15 new domain classes that were missing from the DB.
"""

import ast
import os
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v20_hybrid_best.db")
IMPL_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_impl_file(filepath):
    """Parse an impl_*.py file and extract class info + methods."""
    with open(filepath, "r") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        class_name = node.name
        class_code = ast.get_source_segment(source, node) or ""
        if not class_code:
            lines = source.splitlines()
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else len(lines)
            class_code = "\n".join(lines[start:end])

        docstring = ast.get_docstring(node) or ""

        has_run = False
        has_tuple3 = False
        is_vbstyle = 1

        methods = []
        for item in ast.iter_child_nodes(node):
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            method_name = item.name
            is_dunder = 1 if method_name.startswith("__") and method_name.endswith("__") else 0

            method_code = ast.get_source_segment(source, item) or ""
            if not method_code:
                lines = source.splitlines()
                start = item.lineno - 1
                end = item.end_lineno if item.end_lineno else len(lines)
                method_code = "\n".join(lines[start:end])

            params_list = []
            for arg in item.args.args:
                params_list.append(arg.arg)
            params = ", ".join(params_list)

            sig = f"def {method_name}({params})"
            line_start = item.lineno

            if method_name == "Run":
                has_run = True

            if "tuple" in method_code.lower() or "return (1," in method_code or "return (0," in method_code:
                has_tuple3 = True

            methods.append({
                "method_name": method_name,
                "method_code": method_code,
                "params": params,
                "signature": sig,
                "is_dunder": is_dunder,
                "is_vbstyle": 1,
                "returns_tuple3": 1 if has_tuple3 else 0,
                "line_start": line_start,
            })

        domain = class_name.replace("Dom", "").lower()
        if class_name == "DomWwsIndex":
            domain = "wws_index"
        elif class_name == "DomDbInv":
            domain = "db_inv"
        elif class_name == "DomDbStudio":
            domain = "db_studio"
        elif class_name == "DomIngestCli":
            domain = "ingest_cli"
        elif class_name == "DomIngestGui":
            domain = "ingest_gui"
        elif class_name == "DomCodegraph":
            domain = "codegraph"

        return {
            "class_name": class_name,
            "class_code": class_code,
            "domain": domain,
            "description": docstring,
            "source_file": os.path.basename(filepath),
            "is_vbstyle": is_vbstyle,
            "has_run_method": 1 if has_run else 0,
            "has_tuple3": 1 if has_tuple3 else 0,
            "methods": methods,
        }

    return None


def main():
    impl_files = sorted([f for f in os.listdir(IMPL_DIR) if f.startswith("impl_") and f.endswith(".py")])
    print(f"Found {len(impl_files)} impl_*.py files")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    updated = 0
    inserted = 0
    methods_total = 0
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    for fname in impl_files:
        filepath = os.path.join(IMPL_DIR, fname)
        info = parse_impl_file(filepath)
        if not info:
            print(f"  SKIP {fname} — no class found")
            continue

        cur.execute("SELECT id FROM classes WHERE class_name = ?", (info["class_name"],))
        row = cur.fetchone()

        if row:
            class_id = row[0]
            cur.execute("""
                UPDATE classes SET
                    class_code = ?, domain = ?, description = ?, source_file = ?,
                    is_vbstyle = ?, has_run_method = ?, has_tuple3 = ?,
                    version = version + 1, created_at = ?
                WHERE id = ?
            """, (
                info["class_code"], info["domain"], info["description"], info["source_file"],
                info["is_vbstyle"], info["has_run_method"], info["has_tuple3"],
                now, class_id
            ))
            updated += 1
        else:
            cur.execute("""
                INSERT INTO classes
                    (class_name, class_code, domain, description, source_file,
                     line_start, is_vbstyle, has_run_method, has_tuple3, version, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, 1, ?)
            """, (
                info["class_name"], info["class_code"], info["domain"], info["description"],
                info["source_file"], info["is_vbstyle"], info["has_run_method"],
                info["has_tuple3"], now
            ))
            class_id = cur.lastrowid
            inserted += 1

        cur.execute("DELETE FROM methods WHERE class_id = ?", (class_id,))

        for m in info["methods"]:
            cur.execute("""
                INSERT INTO methods
                    (class_id, method_name, method_code, params, signature,
                     is_dunder, is_vbstyle, returns_tuple3, line_start, version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                class_id, m["method_name"], m["method_code"], m["params"],
                m["signature"], m["is_dunder"], m["is_vbstyle"],
                m["returns_tuple3"], m["line_start"], now
            ))
            methods_total += 1

        print(f"  {'UPDATE' if row else 'INSERT'} {info['class_name']:25s} domain={info['domain']:15s} methods={len(info['methods'])}")

    conn.commit()
    conn.close()

    print(f"\nDone: {updated} classes updated, {inserted} classes inserted, {methods_total} methods written")


if __name__ == "__main__":
    main()
