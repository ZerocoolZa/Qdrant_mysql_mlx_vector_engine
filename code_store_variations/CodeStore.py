#!/usr/bin/env python3
"""
CodeStore — VBStyle code-in-database system.

Stores classes and methods as records in a local SQLite database.
1 class = 1 row in classes table.
1 method = 1 row in methods table, FK to class.

This implements the @nofiles rule: "use single database with class table
and method table PKFK; code in database only"

Usage:
    python3 CodeStore.py ingest GhostQAEngine.py
    python3 CodeStore.py list
    python3 CodeStore.py show GhostQAEngine
    python3 CodeStore.py exec GhostQAEngine Run '{"command":"read_state"}'
"""

import sqlite3
import ast
import json
import os
import sys
import textwrap

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "code_store.db")


def InitDB(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT NOT NULL UNIQUE,
        domain TEXT,
        role TEXT,
        return_type TEXT,
        description TEXT,
        class_code TEXT,
        source_file TEXT,
        line_start INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        method_name TEXT NOT NULL,
        params TEXT,
        method_code TEXT,
        is_dunder INTEGER DEFAULT 0,
        line_start INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
    )""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_methods_class ON methods(class_id)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_methods_name ON methods(method_name)""")
    conn.commit()
    return conn


def ParsePythonFile(filepath):
    """Parse a Python file into classes and methods using AST."""
    with open(filepath, "r") as f:
        source = f.read()

    tree = ast.parse(source)
    classes = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = []
                for arg in item.args.args:
                    params.append(arg.arg)
                is_dunder = item.name.startswith("__") and item.name.endswith("__")

                method_lines = ast.get_source_segment(source, item)
                if method_lines is None:
                    method_lines = "\n".join(source.splitlines()[item.lineno-1:item.end_lineno])

                methods.append({
                    "method_name": item.name,
                    "params": ", ".join(params),
                    "method_code": method_lines,
                    "is_dunder": 1 if is_dunder else 0,
                    "line_start": item.lineno,
                })

        class_code = ast.get_source_segment(source, node)
        if class_code is None:
            class_lines = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    seg = ast.get_source_segment(source, item)
                    if seg:
                        class_lines.append(seg)
            class_code = "\n".join(class_lines)

        docstring = ""
        if node.body and isinstance(node.body[0], ast.Expr):
            if isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                docstring = node.body[0].value.value

        classes.append({
            "class_name": node.name,
            "class_code": class_code,
            "description": docstring.strip() if docstring else "",
            "line_start": node.lineno,
            "methods": methods,
        })

    return classes


def IngestFile(filepath, conn):
    """Parse a Python file and store all classes + methods in the DB."""
    classes = ParsePythonFile(filepath)
    c = conn.cursor()
    ingested = 0

    for cls in classes:
        c.execute("SELECT id FROM classes WHERE class_name = ?", (cls["class_name"],))
        existing = c.fetchone()
        if existing:
            c.execute("""UPDATE classes SET class_code=?, description=?, source_file=?, line_start=?
                WHERE class_name=?""",
                (cls["class_code"], cls["description"], filepath, cls["line_start"], cls["class_name"]))
            class_id = existing[0]
            c.execute("DELETE FROM methods WHERE class_id = ?", (class_id,))
        else:
            c.execute("""INSERT INTO classes (class_name, description, class_code, source_file, line_start)
                VALUES (?, ?, ?, ?, ?)""",
                (cls["class_name"], cls["description"], cls["class_code"], filepath, cls["line_start"]))
            class_id = c.lastrowid

        for m in cls["methods"]:
            c.execute("""INSERT INTO methods (class_id, method_name, params, method_code, is_dunder, line_start)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (class_id, m["method_name"], m["params"], m["method_code"], m["is_dunder"], m["line_start"]))

        ingested += 1
        method_count = len(cls["methods"])
        print(f"  Ingested: {cls['class_name']} ({method_count} methods)")

    conn.commit()
    return ingested


def ListClasses(conn):
    c = conn.cursor()
    rows = c.execute("""
        SELECT cl.class_name, cl.domain, cl.description,
               COUNT(m.id) as method_count, cl.source_file
        FROM classes cl
        LEFT JOIN methods m ON m.class_id = cl.id
        GROUP BY cl.id
        ORDER BY cl.class_name
    """).fetchall()
    print(f"\n{'Class':30s} {'Methods':>8s} {'Domain':15s} {'Source':30s}")
    print("-" * 90)
    for name, domain, desc, mc, src in rows:
        src_short = os.path.basename(src) if src else ""
        print(f"{name:30s} {mc:8d} {(domain or ''):15s} {src_short:30s}")
    print(f"\nTotal: {len(rows)} classes")


def ShowClass(conn, class_name):
    c = conn.cursor()
    row = c.execute("SELECT * FROM classes WHERE class_name = ?", (class_name,)).fetchone()
    if not row:
        print(f"Class not found: {class_name}")
        return
    print(f"\nClass: {row[1]}")
    print(f"Domain: {row[2] or '(none)'}")
    print(f"Description: {row[4] or '(none)'}")
    print(f"Source: {row[6] or '(none)'}")
    print(f"Line: {row[7]}")

    methods = c.execute("SELECT method_name, params, is_dunder, line_start FROM methods WHERE class_id = ? ORDER BY line_start",
                        (row[0],)).fetchall()
    print(f"\nMethods ({len(methods)}):")
    print(f"  {'Name':25s} {'Params':30s} {'Dunder':>7s} {'Line':>5s}")
    print("  " + "-" * 70)
    for mname, mparams, mdunder, mline in methods:
        print(f"  {mname:25s} {(mparams or ''):30s} {'Y' if mdunder else 'N':>7s} {mline:5d}")


def ShowMethod(conn, class_name, method_name):
    c = conn.cursor()
    row = c.execute("""SELECT m.method_code, m.params, m.line_start
        FROM methods m
        JOIN classes c ON m.class_id = c.id
        WHERE c.class_name = ? AND m.method_name = ?""",
        (class_name, method_name)).fetchone()
    if not row:
        print(f"Method not found: {class_name}.{method_name}")
        return
    print(f"\n--- {class_name}.{method_name} ---")
    print(f"Params: {row[1]}")
    print(f"Line: {row[2]}")
    print(f"\n{row[0]}")


def ExecMethod(conn, class_name, method_name, args_json):
    """Reconstruct a class from DB and execute one method."""
    c = conn.cursor()
    cls_row = c.execute("SELECT class_code FROM classes WHERE class_name = ?", (class_name,)).fetchone()
    if not cls_row:
        print(f"Class not found: {class_name}")
        return

    try:
        args = json.loads(args_json) if args_json else {}
    except json.JSONDecodeError as e:
        print(f"Invalid JSON args: {e}")
        return

    namespace = {}
    exec(cls_row[0], namespace)
    cls = namespace.get(class_name)
    if not cls:
        print(f"Class {class_name} not found in reconstructed code")
        return

    instance = cls()
    method = getattr(instance, method_name, None)
    if not method or not callable(method):
        print(f"Method {method_name} not found on {class_name}")
        return

    # VBStyle Run() takes (command, params) — if args is a dict with "command", unpack
    if method_name == "Run" and isinstance(args, dict) and "command" in args:
        result = method(args.get("command"), args.get("params"))
    elif isinstance(args, dict):
        result = method(args)
    elif args:
        result = method(args)
    else:
        result = method()
    print(f"Result: {result}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    conn = InitDB()

    if cmd == "ingest":
        if len(sys.argv) < 3:
            print("Usage: ingest <file.py> [file2.py ...]")
            sys.exit(1)
        for filepath in sys.argv[2:]:
            if not os.path.exists(filepath):
                print(f"File not found: {filepath}")
                continue
            print(f"\nIngesting: {filepath}")
            count = IngestFile(filepath, conn)
            print(f"  {count} classes ingested")

    elif cmd == "list":
        ListClasses(conn)

    elif cmd == "show":
        if len(sys.argv) < 3:
            print("Usage: show <ClassName> [methodName]")
            sys.exit(1)
        if len(sys.argv) >= 4:
            ShowMethod(conn, sys.argv[2], sys.argv[3])
        else:
            ShowClass(conn, sys.argv[2])

    elif cmd == "exec":
        if len(sys.argv) < 4:
            print("Usage: exec <ClassName> <methodName> [json_args]")
            sys.exit(1)
        args_json = sys.argv[4] if len(sys.argv) >= 5 else ""
        ExecMethod(conn, sys.argv[2], sys.argv[3], args_json)

    elif cmd == "count":
        c = conn.cursor()
        cls_count = c.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
        meth_count = c.execute("SELECT COUNT(*) FROM methods").fetchone()[0]
        print(f"Classes: {cls_count}")
        print(f"Methods: {meth_count}")

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: search <keyword>")
            sys.exit(1)
        keyword = sys.argv[2]
        rows = c.execute("""SELECT c.class_name, m.method_name, m.line_start
            FROM methods m
            JOIN classes c ON m.class_id = c.id
            WHERE m.method_code LIKE ? OR m.method_name LIKE ?
            ORDER BY c.class_name, m.line_start""",
            (f"%{keyword}%", f"%{keyword}%")).fetchall()
        print(f"\nSearch '{keyword}': {len(rows)} matches")
        for cn, mn, ln in rows:
            print(f"  {cn}.{mn} (line {ln})")

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)

    conn.close()


if __name__ == "__main__":
    main()
