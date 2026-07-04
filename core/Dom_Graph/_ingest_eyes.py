#!/usr/bin/env python3
"""Ingest 26 Eyes files into dom_graph.db — break into classes, methods, edges"""
import sqlite3, ast, os, hashlib, json

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dom_graph.db")
conn = sqlite3.connect(DB)
cur = conn.cursor()

files_to_ingest = [
    os.path.join(os.path.dirname(DB), "eyes_26.py"),
    os.path.join(os.path.dirname(DB), "codegraph_26eyes.py"),
    os.path.join(os.path.dirname(DB), "eyes_26_v1.py"),
]

for fpath in files_to_ingest:
    fname = os.path.basename(fpath)
    with open(fpath, "r") as f:
        content = f.read()
    file_hash = hashlib.sha256(content.encode()).hexdigest()
    size = len(content)

    tree = ast.parse(content, filename=fpath)
    imports = []
    classes = []
    methods = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.ClassDef):
            methods_list = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods_list.append(item.name)
            classes.append({
                "name": node.name,
                "lineno": node.lineno,
                "methods": methods_list,
            })
            methods.extend(methods_list)

    class_count = len(classes)
    method_count = len(methods)

    cur.execute(
        "INSERT OR REPLACE INTO files "
        "(file_name, path, extension, hash, size, imports, class_count, function_count, method_count, status, language) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (fname, os.path.abspath(fpath), ".py", file_hash, size,
         json.dumps(imports), class_count, 0, method_count, "active", "python"),
    )
    file_id = cur.execute(
        "SELECT file_id FROM files WHERE file_name=?", (fname,)
    ).fetchone()[0]

    for cls in classes:
        cur.execute(
            "INSERT INTO class_registry (file, class_name, lineno, class_text, method_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (fname, cls["name"], cls["lineno"], "", len(cls["methods"])),
        )
        class_id = cur.lastrowid
        for mname in cls["methods"]:
            cur.execute(
                "INSERT INTO method_registry (class_id, method_name, lineno, method_text) "
                "VALUES (?, ?, ?, ?)",
                (class_id, mname, 0, ""),
            )

    print("{}: {} classes, {} methods, {} imports".format(
        fname, class_count, method_count, len(imports)))

conn.commit()

total_classes = cur.execute("SELECT COUNT(*) FROM class_registry").fetchone()[0]
total_methods = cur.execute("SELECT COUNT(*) FROM method_registry").fetchone()[0]
total_files = cur.execute("SELECT COUNT(*) FROM files").fetchone()[0]
total_edges = cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
print()
print("DB TOTALS: {} files, {} classes, {} methods, {} edges".format(
    total_files, total_classes, total_methods, total_edges))

conn.close()
print("DONE")
