#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/ingest_bcl.py"
# date="2026-06-27" author="Cascade" session_id="bcl-ingest"
# context="Ingest all BCL folder .py files into SQLite inventory database"}
# [@VBSTYLE]{standard="VBStyle" version="1"}
# [@FILEID]{id="ingest_bcl.py" domain="BCL"}
# [@SUMMARY]{summary="One-shot ingestion: parse all .py files with AST, extract classes/methods/imports/constants/violations into bcl_inventory.db"}

import ast
import os
import sqlite3
import hashlib
import json


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bcl_inventory.db")


def StableId(*parts):
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def ExtractMethod(node, file_id, class_id, class_name):
    name = node.name
    params = [a.arg for a in node.args.args if a.arg != "self"]
    calls = []
    self_attrs = []
    has_print = False
    has_nested = False
    branch_count = 0
    loop_count = 0
    return_count = 0
    has_tuple3 = False
    decorator_names = []
    for dec in node.decorator_list:
        try:
            decorator_names.append(ast.unparse(dec))
        except Exception:
            decorator_names.append("?")
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
                if func.id == "print":
                    has_print = True
            elif isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name) and func.value.id == "self":
                    self_attrs.append(func.attr)
                calls.append(func.attr)
        elif isinstance(child, (ast.If, ast.ExceptHandler)):
            branch_count += 1
        elif isinstance(child, (ast.For, ast.While)):
            loop_count += 1
        elif isinstance(child, ast.Return):
            return_count += 1
            if isinstance(child.value, ast.Tuple) and len(child.value.elts) == 3:
                has_tuple3 = True
            elif child.value and isinstance(child.value, ast.Call):
                call = child.value
                if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "self":
                    has_tuple3 = True
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if child is not node:
                has_nested = True
    complexity = 1 + branch_count + loop_count
    docstring = ast.get_docstring(node) or ""
    method_id = StableId(file_id, class_id, name, node.lineno)
    return {
        "id": method_id, "file_id": file_id, "class_id": class_id,
        "class_name": class_name, "method_name": name,
        "params": json.dumps(params), "return_count": return_count,
        "has_tuple3": has_tuple3,
        "decorator_names": json.dumps(decorator_names),
        "decorator_count": len(decorator_names),
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "line_start": node.lineno, "line_end": node.end_lineno,
        "line_span": (node.end_lineno or node.lineno) - node.lineno,
        "calls": json.dumps(calls[:20]), "call_count": len(calls),
        "self_attrs": json.dumps(sorted(set(self_attrs))),
        "branch_count": branch_count, "loop_count": loop_count,
        "complexity": complexity, "has_print": has_print,
        "has_nested_func": has_nested, "docstring": docstring[:200],
    }


def Main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
CREATE TABLE files (
    id TEXT PRIMARY KEY, filepath TEXT, filename TEXT,
    line_count INTEGER, import_count INTEGER, class_count INTEGER,
    has_run INTEGER, has_state INTEGER, has_tuple3 INTEGER,
    has_print INTEGER, has_decorators INTEGER, has_self_underscore INTEGER,
    has_enum INTEGER, has_slots INTEGER, has_property INTEGER,
    docstring TEXT
);
CREATE TABLE imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT, module TEXT, name TEXT, alias TEXT, is_wildcard INTEGER
);
CREATE TABLE classes (
    id TEXT PRIMARY KEY, file_id TEXT, class_name TEXT, bases TEXT,
    has_init INTEGER, has_run INTEGER, has_state INTEGER,
    method_count INTEGER, line_start INTEGER, line_end INTEGER,
    docstring TEXT, nested_classes TEXT
);
CREATE TABLE methods (
    id TEXT PRIMARY KEY, file_id TEXT, class_id TEXT, class_name TEXT,
    method_name TEXT, params TEXT, return_count INTEGER, has_tuple3 INTEGER,
    decorator_names TEXT, decorator_count INTEGER, is_async INTEGER,
    line_start INTEGER, line_end INTEGER, line_span INTEGER,
    calls TEXT, call_count INTEGER, self_attrs TEXT,
    branch_count INTEGER, loop_count INTEGER, complexity INTEGER,
    has_print INTEGER, has_nested_func INTEGER, docstring TEXT
);
CREATE TABLE constants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT, class_id TEXT, scope TEXT,
    name TEXT, value_type TEXT, value_repr TEXT
);
CREATE TABLE violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT, class_name TEXT, method_name TEXT,
    rule TEXT, severity TEXT, description TEXT
);
""")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_count = 0
    for fname in sorted(os.listdir(script_dir)):
        if not fname.endswith(".py") or fname == "ingest_bcl.py":
            continue
        fpath = os.path.join(script_dir, fname)
        source = open(fpath).read()
        lines = source.splitlines()
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            db.execute("INSERT INTO violations (file_id, class_name, method_name, rule, severity, description) VALUES (?,?,?,?,?,?)",
                (StableId(fpath), "", "", "syntax_error", "critical", str(exc)))
            continue
        file_id = StableId(fpath)
        imports = []
        classes = []
        methods = []
        constants = []
        violations = []
        module_doc = ast.get_docstring(tree) or ""
        # AST-based detection: only flag real code, not string literals
        has_print = False
        has_decorators = False
        has_self_underscore = False
        has_property = False
        for node2 in ast.walk(tree):
            if isinstance(node2, ast.Call):
                func = node2.func
                if isinstance(func, ast.Name) and func.id == "print":
                    has_print = True
            if isinstance(node2, ast.Attribute):
                if isinstance(node2.value, ast.Name) and node2.value.id == "self":
                    if node2.attr.startswith("_") and node2.attr not in ("_p", "__init__"):
                        has_self_underscore = True
        # Check decorators on function/class defs only
        for node2 in ast.walk(tree):
            if isinstance(node2, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for dec in node2.decorator_list:
                    dec_name = ""
                    try:
                        dec_name = ast.unparse(dec)
                    except Exception:
                        pass
                    if dec_name in ("@property", "@staticmethod", "@classmethod", "property", "staticmethod", "classmethod"):
                        has_decorators = True
                        if dec_name in ("@property", "property"):
                            has_property = True
        has_enum = any(isinstance(node2, ast.ClassDef) and any(
            (isinstance(b, ast.Name) and b.id == "Enum") for b in node2.bases
        ) for node2 in ast.walk(tree))
        has_slots = "__slots__" in source
        has_run_any = False
        has_state_any = False
        has_tuple3_any = False

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append((file_id, alias.name, "", alias.asname or "", 0))
                else:
                    mod = node.module or ""
                    for alias in node.names:
                        is_wild = 1 if alias.name == "*" else 0
                        imports.append((file_id, mod, alias.name, alias.asname or "", is_wild))
            elif isinstance(node, ast.ClassDef):
                class_name = node.name
                bases = []
                for b in node.bases:
                    try:
                        bases.append(ast.unparse(b))
                    except Exception:
                        bases.append("?")
                class_id = StableId(file_id, class_name, node.lineno)
                class_has_init = False
                class_has_run = False
                class_has_state = False
                class_methods = []
                nested = []
                class_doc = ast.get_docstring(node) or ""
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m = ExtractMethod(item, file_id, class_id, class_name)
                        class_methods.append(m)
                        if item.name == "__init__":
                            class_has_init = True
                        if item.name == "Run":
                            class_has_run = True
                            has_run_any = True
                        try:
                            if "self.state" in ast.unparse(item):
                                class_has_state = True
                                has_state_any = True
                        except Exception:
                            pass
                        if m["has_tuple3"]:
                            has_tuple3_any = True
                        if m["method_name"].startswith("_") and m["method_name"] not in ("_p", "__init__"):
                            violations.append((file_id, class_name, m["method_name"],
                                "self_underscore", "high", "Method uses underscore prefix"))
                        if m["has_print"]:
                            violations.append((file_id, class_name, m["method_name"],
                                "print_statement", "high", "Uses print()"))
                        if m["decorator_count"] > 0:
                            violations.append((file_id, class_name, m["method_name"],
                                "decorator", "high", "Has decorators: " + ",".join(json.loads(m["decorator_names"]))))
                        if not m["has_tuple3"] and item.name not in ("__init__", "_p"):
                            violations.append((file_id, class_name, m["method_name"],
                                "no_tuple3", "medium", "Method does not return Tuple3"))
                    elif isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                val_type = type(item.value).__name__
                                try:
                                    val_repr = ast.unparse(item.value)[:100]
                                except Exception:
                                    val_repr = "?"
                                constants.append((file_id, class_id, "class", target.id, val_type, val_repr))
                    elif isinstance(item, ast.ClassDef):
                        nested.append(item.name)
                if not class_has_run:
                    violations.append((file_id, class_name, "",
                        "no_run", "high", "Class has no Run() dispatch"))
                if not class_has_state:
                    violations.append((file_id, class_name, "",
                        "no_state", "high", "Class has no self.state dict"))
                classes.append({
                    "id": class_id, "file_id": file_id, "class_name": class_name,
                    "bases": json.dumps(bases), "has_init": class_has_init,
                    "has_run": class_has_run, "has_state": class_has_state,
                    "method_count": len(class_methods),
                    "line_start": node.lineno, "line_end": node.end_lineno,
                    "docstring": class_doc[:200],
                    "nested_classes": json.dumps(nested),
                })
                methods.extend(class_methods)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        try:
                            val_repr = ast.unparse(node.value)[:100]
                        except Exception:
                            val_repr = "?"
                        constants.append((file_id, "", "module", target.id, type(node.value).__name__, val_repr))

        if has_print and len(classes) > 0:
            violations.append((file_id, "", "", "print_statement", "high", "File contains print()"))
        if has_decorators and len(classes) > 0:
            violations.append((file_id, "", "", "decorator", "high", "File contains decorators"))
        if has_self_underscore and len(classes) > 0:
            violations.append((file_id, "", "", "self_underscore", "high", "File contains self._"))
        if has_enum and len(classes) > 0:
            violations.append((file_id, "", "", "enum_usage", "high", "File uses Enum"))
        if has_slots and len(classes) > 0:
            violations.append((file_id, "", "", "slots_usage", "high", "File uses __slots__"))
        if has_property and len(classes) > 0:
            violations.append((file_id, "", "", "property_decorator", "high", "File uses @property"))

        db.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (file_id, fpath, fname, len(lines), len(imports), len(classes),
             1 if has_run_any else 0, 1 if has_state_any else 0, 1 if has_tuple3_any else 0,
             1 if has_print else 0, 1 if has_decorators else 0,
             1 if has_self_underscore else 0, 1 if has_enum else 0,
             1 if has_slots else 0, 1 if has_property else 0, module_doc[:200]))
        for imp in imports:
            db.execute("INSERT INTO imports (file_id, module, name, alias, is_wildcard) VALUES (?,?,?,?,?)", imp)
        for c in classes:
            db.execute("INSERT INTO classes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (c["id"], c["file_id"], c["class_name"], c["bases"], c["has_init"],
                 c["has_run"], c["has_state"], c["method_count"], c["line_start"],
                 c["line_end"], c["docstring"], c["nested_classes"]))
        for m in methods:
            db.execute("INSERT INTO methods VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (m["id"], m["file_id"], m["class_id"], m["class_name"], m["method_name"],
                 m["params"], m["return_count"], m["has_tuple3"], m["decorator_names"],
                 m["decorator_count"], m["is_async"], m["line_start"], m["line_end"],
                 m["line_span"], m["calls"], m["call_count"], m["self_attrs"],
                 m["branch_count"], m["loop_count"], m["complexity"], m["has_print"],
                 m["has_nested_func"], m["docstring"]))
        for c in constants:
            db.execute("INSERT INTO constants (file_id, class_id, scope, name, value_type, value_repr) VALUES (?,?,?,?,?,?)", c)
        for v in violations:
            db.execute("INSERT INTO violations (file_id, class_name, method_name, rule, severity, description) VALUES (?,?,?,?,?,?)", v)
        file_count += 1

    db.commit()
    counts = {
        "files": db.execute("SELECT COUNT(*) FROM files").fetchone()[0],
        "imports": db.execute("SELECT COUNT(*) FROM imports").fetchone()[0],
        "classes": db.execute("SELECT COUNT(*) FROM classes").fetchone()[0],
        "methods": db.execute("SELECT COUNT(*) FROM methods").fetchone()[0],
        "constants": db.execute("SELECT COUNT(*) FROM constants").fetchone()[0],
        "violations": db.execute("SELECT COUNT(*) FROM violations").fetchone()[0],
    }
    db.close()
    for k, v in counts.items():
        print("%s: %d" % (k, v))


if __name__ == "__main__":
    Main()
