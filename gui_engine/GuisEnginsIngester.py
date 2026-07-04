#!/usr/bin/env python3
# [@GHOST]{[@file<GuisEnginsIngester.py>][@domain<gui_engine>][@role<ingester>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<hierarchy_ingester>][@return<tuple3>][@orch<none>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Parses GUI engine files into GuisEngins.db — file>>class>>comp_unit>>method with BCL stamps for every block}
# [@CLASS]{[@name<GuisEnginsIngester>][@domain<gui_engine>][@authority<single>]}

import ast
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

DB_PATH = Path(__file__).parent / "GuisEngins.db"
SQL_PATH = Path(__file__).parent / "GuisEngins_db.sql"

QT_WINDOW_BASES = {
    "QMainWindow", "QWidget", "QDialog", "QFrame", "QSplitter",
    "QTabWidget", "QStackedWidget", "QScrollArea", "QGroupBox",
}

VBSTYLE_RUN_NAMES = {"Run", "run", "Execute", "execute"}
VBSTYLE_STATE_NAMES = {"state", "State", "self.state"}
TUPLE3_PATTERN = re.compile(r"return\s*\(\s*[01]\s*,")
DISPATCH_PATTERN = re.compile(r"(if|elif)\s+(command|cmd)\s*==\s*['\"]")


class GuisEnginsIngester:
    """Ingest GUI engine files into GuisEngins.db with BCL stamps at every level.

    Hierarchy: file >> class >> comp_unit >> method
    BCL stamps generated for EVERY block with reasoning and details.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"db_path": str(DB_PATH)},
            "catalog": [],
            "results": [],
        }
        self.db_path = str(DB_PATH)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.stats = {"files": 0, "classes": 0, "comp_units": 0, "methods": 0, "stamps": 0, "edges": 0}

    def Run(self, command, params=None):
        if command == "ingest_file":
            return self._ingest_file(params.get("path"))
        elif command == "ingest_dir":
            return self._ingest_dir(params.get("path"), params.get("language", "python"))
        elif command == "ingest_all_gui_engines":
            return self._ingest_all_gui_engines()
        elif command == "query_file":
            return self._query_file(params.get("path"))
        elif command == "query_class":
            return self._query_class(params.get("name"))
        elif command == "query_method":
            return self._query_method(params.get("class_name"), params.get("method_name"))
        elif command == "query_stamps":
            return self._query_stamps(params.get("scope_type"), params.get("class_name"))
        elif command == "Say":
            return self._say(params.get("topic", "overview"))
        elif command == "stats":
            return self._get_stats()
        elif command == "read_state":
            return self.read_state()
        elif command == "reset":
            return self._reset()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def _init_db(self):
        with open(SQL_PATH, "r") as f:
            self.cursor.executescript(f.read())
        self.conn.commit()

    def _reset(self):
        self._init_db()
        for table in ("gui_edges", "gui_bcl_stamps", "gui_methods", "gui_comp_units", "gui_classes", "gui_files"):
            self.cursor.execute("DELETE FROM {}".format(table))
        self.conn.commit()
        self.stats = {k: 0 for k in self.stats}
        return (1, {"reset": True}, None)

    def _ingest_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            return self._ingest_source(file_path, source, "python")
        except Exception as e:
            return (0, None, ("read_error", str(e), 0))

    def _ingest_dir(self, dir_path, language="python"):
        ingested = 0
        errors = []
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules", ".venv")]
            for fname in files:
                if fname.endswith(".py"):
                    fpath = os.path.join(root, fname)
                    ok, data, err = self._ingest_file(fpath)
                    if ok:
                        ingested += 1
                    else:
                        errors.append({"file": fpath, "error": err[1] if err else "unknown"})
        return (1, {"ingested": ingested, "errors": errors}, None)

    def _ingest_all_gui_engines(self):
        roots = [
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/gui_engine",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/dynamic_gui",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/dynamic_gui",
            "/Users/wws/contestsystem/my_new_repo/GuiSystem",
            "/Users/wws/contestsystem/gui",
            "/Users/wws/contestsystem/Application_stage_builder/Core",
            "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Magic_Clipboard_gui",
            "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/PRj_codex-notes/Boot_Engine",
            "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/PRj_codex-notes/Gui_Engine",
            "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/App_Gui_Main_System",
        ]
        extra_files = [
            "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/runtime_gui_engine.py",
        ]
        total = 0
        all_errors = []
        for root in roots:
            if os.path.isdir(root):
                ok, data, err = self._ingest_dir(root)
                if ok:
                    total += data["ingested"]
                    all_errors.extend(data.get("errors", []))
        for fpath in extra_files:
            if os.path.isfile(fpath):
                ok, data, err = self._ingest_file(fpath)
                if ok:
                    total += 1
        return (1, {"total_ingested": total, "errors": all_errors}, None)

    def _ingest_source(self, file_path, source, language):
        self._init_db()
        file_hash = hashlib.sha256(source.encode()).hexdigest()[:16]
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            return (0, None, ("parse_error", str(e), e.lineno or 0))

        file_name = os.path.basename(file_path)
        file_id = self._store_file(file_path, file_name, language, file_hash, source, tree)
        stamps = []
        edges = []

        file_stamps = self._stamp_file(file_path, source, tree)
        stamps.extend(file_stamps)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cls_id, cls_stamps, cls_edges = self._store_class(file_path, file_id, node, source)
                stamps.extend(cls_stamps)
                edges.extend(cls_edges)

                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        unit_id, unit_stamps, unit_edges = self._store_comp_unit_and_method(
                            file_path, cls_id, node.name, child, source)
                        stamps.extend(unit_stamps)
                        edges.extend(unit_edges)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not self._is_inside_class(node, tree):
                    unit_id, unit_stamps, unit_edges = self._store_comp_unit_and_method(
                        file_path, None, None, node, source)
                    stamps.extend(unit_stamps)
                    edges.extend(unit_edges)

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imp_stamps = self._stamp_import(file_path, node)
                stamps.extend(imp_stamps)

        self._store_stamps(stamps)
        self._store_edges(edges)

        self.stats["files"] += 1
        self.conn.commit()
        return (1, {
            "file": file_path,
            "classes": self.stats.get("classes", 0),
            "stamps": len(stamps),
            "edges": len(edges),
        }, None)

    def _is_inside_class(self, func_node, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if child is func_node:
                        return True
        return False

    def _store_file(self, file_path, file_name, language, file_hash, source, tree):
        line_count = len(source.splitlines())
        purpose = self._extract_file_purpose(source)
        domain = self._extract_file_domain(source)
        self.cursor.execute("""
            INSERT OR REPLACE INTO gui_files (file_path, file_name, language, file_hash, full_source, line_count, purpose, domain)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (file_path, file_name, language, file_hash, source, line_count, purpose, domain))
        self._clear_file_data(file_path)
        self.conn.commit()
        return self.cursor.lastrowid

    def _clear_file_data(self, file_path):
        for table in ("gui_edges", "gui_bcl_stamps", "gui_methods", "gui_comp_units", "gui_classes"):
            self.cursor.execute("DELETE FROM {} WHERE file_path = ?".format(table), (file_path,))

    def _store_class(self, file_path, file_id, node, source):
        base_class = None
        if node.bases:
            for b in node.bases:
                if isinstance(b, ast.Name):
                    base_class = b.id
                elif isinstance(b, ast.Attribute):
                    base_class = b.attr
        is_qt = 1 if base_class in QT_WINDOW_BASES else 0
        method_count = sum(1 for c in node.body if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)))
        source_text = self._get_source_segment(source, node.lineno, node.end_lineno)
        purpose = self._extract_docstring(node)
        domain = self._extract_class_domain(source_text)

        self.cursor.execute("""
            INSERT INTO gui_classes (file_id, file_path, class_name, base_class, line_start, line_end, method_count, is_qt_window, source_text, purpose, domain)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (file_id, file_path, node.name, base_class, node.lineno, node.end_lineno or node.lineno,
              method_count, is_qt, source_text, purpose, domain))
        cls_id = self.cursor.lastrowid
        self.stats["classes"] += 1

        stamps = []
        stamps.append(self._make_stamp("CLASS", cls_id, file_path, node.name, None, None,
            "GHOST", "class_name", node.name,
            "Class identity", "name={}".format(node.name)))
        stamps.append(self._make_stamp("CLASS", cls_id, file_path, node.name, None, None,
            "VBSTYLE", "base_class", base_class or "none",
            "Inheritance", "base={}".format(base_class)))
        stamps.append(self._make_stamp("CLASS", cls_id, file_path, node.name, None, None,
            "DOMAIN", "domain", domain or "unknown",
            "Responsibility domain", "domain={}".format(domain)))
        stamps.append(self._make_stamp("CLASS", cls_id, file_path, node.name, None, None,
            "SUMMARY", "purpose", purpose or "no docstring",
            "What this class does", "methods={}".format(method_count)))
        if is_qt:
            stamps.append(self._make_stamp("CLASS", cls_id, file_path, node.name, None, None,
                "WIDGET", "qt_base", base_class,
                "Qt window class", "inherits from Qt widget"))
        has_run = any(c.name in VBSTYLE_RUN_NAMES for c in node.body if isinstance(c, ast.FunctionDef))
        has_state = any("state" in str(ast.dump(c)) for c in node.body if isinstance(c, ast.FunctionDef))
        if has_run:
            stamps.append(self._make_stamp("CLASS", cls_id, file_path, node.name, None, None,
                "VBSTYLE", "has_run", "true",
                "VBStyle Run method present", "dispatch entry point"))
        if has_state:
            stamps.append(self._make_stamp("CLASS", cls_id, file_path, node.name, None, None,
                "VBSTYLE", "has_state", "true",
                "VBStyle state dict present", "self.state pattern"))

        edges = []
        if base_class:
            edges.append({
                "file_path": file_path, "from_class": node.name, "from_method": None,
                "to_class": base_class, "to_method": None, "edge_type": "INHERITS",
                "line_num": node.lineno, "evidence": "class {}({})".format(node.name, base_class),
            })
        return cls_id, stamps, edges

    def _store_comp_unit_and_method(self, file_path, class_id, class_name, node, source):
        unit_name = node.name
        unit_type = self._classify_unit(node, class_name)
        source_text = self._get_source_segment(source, node.lineno, node.end_lineno)
        docstring = self._extract_docstring(node)
        calls = self._extract_calls(node)
        returns = self._extract_returns(node)
        params = self._extract_params(node)
        is_vbstyle = 1 if node.name in VBSTYLE_RUN_NAMES or "self.state" in source_text else 0
        has_run = 1 if node.name in VBSTYLE_RUN_NAMES else 0
        has_state = 1 if "self.state" in source_text else 0
        returns_t3 = 1 if TUPLE3_PATTERN.search(source_text) else 0

        self.cursor.execute("""
            INSERT INTO gui_comp_units (class_id, file_path, class_name, unit_name, unit_type, line_start, line_end, line_count, source_text, docstring, calls, returns, params, is_vbstyle, has_run, has_state, returns_tuple3)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (class_id, file_path, class_name or "", unit_name, unit_type,
              node.lineno, node.end_lineno or node.lineno,
              (node.end_lineno or node.lineno) - node.lineno + 1,
              source_text, docstring, calls, returns, params,
              is_vbstyle, has_run, has_state, returns_t3))
        unit_id = self.cursor.lastrowid
        self.stats["comp_units"] += 1

        widget_refs = self._extract_widget_refs(node)
        is_handler = 1 if node.name.startswith("_On") or node.name.startswith("on_") else 0

        self.cursor.execute("""
            INSERT INTO gui_methods (comp_unit_id, file_path, class_name, method_name, line_start, line_end, line_count, source_text, docstring, params, calls, widget_refs, is_handler, is_vbstyle, returns_tuple3)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (unit_id, file_path, class_name or "", unit_name,
              node.lineno, node.end_lineno or node.lineno,
              (node.end_lineno or node.lineno) - node.lineno + 1,
              source_text, docstring, params, calls, widget_refs, is_handler, is_vbstyle, returns_t3))
        method_id = self.cursor.lastrowid
        self.stats["methods"] += 1

        stamps = self._stamp_comp_unit(file_path, class_name, unit_name, unit_type, unit_id, node, source_text, docstring, calls, returns, params, is_vbstyle, has_run, has_state, returns_t3, widget_refs)

        edges = []
        for called in calls.split(","):
            called = called.strip()
            if called and called != "":
                edges.append({
                    "file_path": file_path, "from_class": class_name or "",
                    "from_method": unit_name, "to_class": "", "to_method": called,
                    "edge_type": "CALLS", "line_num": node.lineno,
                    "evidence": "{}.{}() calls {}".format(class_name or "?", unit_name, called),
                })

        return unit_id, stamps, edges

    def _classify_unit(self, node, class_name):
        name = node.name
        source = ast.dump(node)
        if name == "__init__":
            return "INIT"
        if name in VBSTYLE_RUN_NAMES:
            return "RUN"
        if DISPATCH_PATTERN.search(source):
            return "DISPATCH"
        if name.startswith("_On") or name.startswith("on_"):
            return "HANDLER"
        if any(kw in name.lower() for kw in ("render", "draw", "paint")):
            return "RENDERER"
        if any(kw in name.lower() for kw in ("build", "create", "construct", "assemble")):
            return "BUILDER"
        if any(kw in name.lower() for kw in ("parse", "extract", "read")):
            return "PARSER"
        if any(kw in name.lower() for kw in ("validate", "check", "verify")):
            return "VALIDATOR"
        if any(kw in name.lower() for kw in ("scan", "walk", "visit")):
            return "SCANNER"
        if any(kw in name.lower() for kw in ("write", "store", "save", "persist")):
            return "WRITER"
        if any(kw in name.lower() for kw in ("load", "fetch", "get")):
            return "READER"
        if name.startswith("test_") or name.startswith("Test"):
            return "FUNCTION"
        if class_name is None:
            return "FUNCTION"
        return "METHOD"

    def _stamp_comp_unit(self, file_path, class_name, unit_name, unit_type, unit_id, node, source_text, docstring, calls, returns, params, is_vbstyle, has_run, has_state, returns_t3, widget_refs):
        stamps = []
        cn = class_name or ""
        stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
            "GHOST", "unit_name", unit_name,
            "Unit identity", "type={}".format(unit_type)))
        stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
            "METHOD", "method_type", unit_type,
            "Classification of this computational unit", "classified as {}".format(unit_type)))
        if docstring:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "SUMMARY", "docstring", docstring[:200],
                "What this unit does", "docstring present"))
        if params:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "PARAMS", "signature", params,
                "Input parameters", "params={}".format(params)))
        if calls:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "CALLS", "dependencies", calls,
                "Methods this unit calls", "calls={}".format(calls[:200])))
        if returns:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "RETURN", "return_type", returns,
                "What this unit returns", "returns={}".format(returns)))
        if returns_t3:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "TUPLE3", "returns_tuple3", "true",
                "VBStyle Tuple3 return pattern", "(ok, data, error)"))
        if is_vbstyle:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "VBSTYLE", "is_vbstyle", "true",
                "Follows VBStyle pattern", "Run/state pattern detected"))
        if has_run:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "RUN", "dispatch_entry", "true",
                "This is the Run dispatch entry point", "command->method routing"))
        if has_state:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "STATE", "uses_state_dict", "true",
                "Uses self.state dict pattern", "no self._ variables"))
        if widget_refs:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "WIDGETS", "widget_refs", widget_refs,
                "Qt widgets referenced", "touches: {}".format(widget_refs[:200])))
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
            "LINES", "line_count", str(line_count),
            "Size of this unit", "lines {}-{} ({})".format(node.lineno, node.end_lineno or node.lineno, line_count)))
        complexity = self._estimate_complexity(source_text)
        if complexity > 0:
            stamps.append(self._make_stamp("COMP_UNIT", unit_id, file_path, cn, unit_name, None,
                "COMPLEXITY", "estimated", str(complexity),
                "Estimated cyclomatic complexity", "branches+loops={}".format(complexity)))
        return stamps

    def _stamp_file(self, file_path, source, tree):
        stamps = []
        file_id_row = self.cursor.execute("SELECT id FROM gui_files WHERE file_path = ?", (file_path,)).fetchone()
        file_id = file_id_row["id"] if file_id_row else 0
        class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        func_count = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        line_count = len(source.splitlines())
        purpose = self._extract_file_purpose(source)
        domain = self._extract_file_domain(source)

        stamps.append(self._make_stamp("FILE", file_id, file_path, None, None, None,
            "GHOST", "file_path", file_path,
            "File identity", "path={}".format(file_path)))
        stamps.append(self._make_stamp("FILE", file_id, file_path, None, None, None,
            "SUMMARY", "purpose", purpose or "no docstring",
            "What this file does", "purpose={}".format(purpose)))
        stamps.append(self._make_stamp("FILE", file_id, file_path, None, None, None,
            "DOMAIN", "domain", domain or "unknown",
            "Responsibility domain", "domain={}".format(domain)))
        stamps.append(self._make_stamp("FILE", file_id, file_path, None, None, None,
            "LINES", "line_count", str(line_count),
            "File size", "{} lines".format(line_count)))
        stamps.append(self._make_stamp("FILE", file_id, file_path, None, None, None,
            "CLASSES", "class_count", str(class_count),
            "Number of classes in file", "{} classes".format(class_count)))
        stamps.append(self._make_stamp("FILE", file_id, file_path, None, None, None,
            "METHODS", "func_count", str(func_count),
            "Number of functions/methods", "{} functions".format(func_count)))
        return stamps

    def _stamp_import(self, file_path, node):
        stamps = []
        file_id_row = self.cursor.execute("SELECT id FROM gui_files WHERE file_path = ?", (file_path,)).fetchone()
        file_id = file_id_row["id"] if file_id_row else 0
        if isinstance(node, ast.Import):
            for alias in node.names:
                stamps.append(self._make_stamp("FILE", file_id, file_path, None, None, None,
                    "IMPORT", "module", alias.name,
                    "Imports module", "import {}".format(alias.name)))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                stamps.append(self._make_stamp("FILE", file_id, file_path, None, None, None,
                    "IMPORT", "from_module", "{}.{}".format(module, alias.name),
                    "Imports from module", "from {} import {}".format(module, alias.name)))
        return stamps

    def _make_stamp(self, scope_type, scope_id, file_path, class_name, unit_name, method_name,
                    stamp_tag, stamp_key, stamp_value, reasoning, details):
        self.stats["stamps"] += 1
        return {
            "scope_type": scope_type, "scope_id": scope_id, "file_path": file_path,
            "class_name": class_name, "unit_name": unit_name, "method_name": method_name,
            "stamp_tag": stamp_tag, "stamp_key": stamp_key, "stamp_value": str(stamp_value)[:500],
            "reasoning": reasoning, "details": details, "line_num": None,
        }

    def _store_stamps(self, stamps):
        for s in stamps:
            self.cursor.execute("""
                INSERT INTO gui_bcl_stamps (scope_type, scope_id, file_path, class_name, unit_name, method_name, stamp_tag, stamp_key, stamp_value, reasoning, details, line_num)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (s["scope_type"], s["scope_id"], s["file_path"], s.get("class_name"),
                  s.get("unit_name"), s.get("method_name"), s["stamp_tag"], s["stamp_key"],
                  s["stamp_value"], s["reasoning"], s["details"], s.get("line_num")))

    def _store_edges(self, edges):
        for e in edges:
            self.cursor.execute("""
                INSERT INTO gui_edges (file_path, from_class, from_method, to_class, to_method, edge_type, line_num, evidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (e["file_path"], e["from_class"], e["from_method"], e["to_class"],
                  e["to_method"], e["edge_type"], e["line_num"], e.get("evidence", "")))
            self.stats["edges"] += 1

    def _extract_docstring(self, node):
        if (node.body and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)):
            return node.body[0].value.value.strip()
        return None

    def _extract_file_purpose(self, source):
        lines = source.splitlines()
        for line in lines[:30]:
            line = line.strip()
            if line.startswith('"""') or line.startswith("'''"):
                end = line.find('"""', 3) if '"""' in line else line.find("'''", 3)
                if end > 0:
                    return line[3:end].strip()
            if line.startswith("# PURPOSE:") or line.startswith("# PURPOSE "):
                return line.replace("# PURPOSE:", "").replace("# PURPOSE ", "").strip()
        return None

    def _extract_file_domain(self, source):
        for line in source.splitlines()[:20]:
            line = line.strip()
            if "DOMAIN:" in line:
                return line.split("DOMAIN:")[1].strip()
            if "[@domain<" in line.lower():
                m = re.search(r'\[@domain<([^>]+)>', line, re.IGNORECASE)
                if m:
                    return m.group(1)
        return None

    def _extract_class_domain(self, source_text):
        for line in source_text.splitlines()[:10]:
            if "DOMAIN:" in line:
                return line.split("DOMAIN:")[1].strip()
        return None

    def _extract_calls(self, node):
        calls = []
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Name):
                    calls.append(n.func.id)
                elif isinstance(n.func, ast.Attribute):
                    calls.append(n.func.attr)
        seen = []
        for c in calls:
            if c not in seen:
                seen.append(c)
        return ",".join(seen[:30])

    def _extract_returns(self, node):
        returns = []
        for n in ast.walk(node):
            if isinstance(n, ast.Return):
                if isinstance(n.value, ast.Tuple):
                    returns.append("tuple")
                elif isinstance(n.value, ast.Constant):
                    returns.append(str(n.value.value))
                elif isinstance(n.value, ast.Name):
                    returns.append(n.value.id)
                elif n.value is None:
                    returns.append("none")
                else:
                    returns.append("expr")
        return ",".join(set(returns)) if returns else ""

    def _extract_params(self, node):
        args = [a.arg for a in node.args.args]
        return ",".join(args)

    def _extract_widget_refs(self, node):
        refs = []
        for n in ast.walk(node):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
                if n.value.id == "self":
                    refs.append(n.attr)
        seen = []
        for r in refs:
            if r not in seen:
                seen.append(r)
        return ",".join(seen[:20])

    def _estimate_complexity(self, source_text):
        complexity = 1
        for kw in ("if ", "elif ", "for ", "while ", "and ", "or ", "except "):
            complexity += source_text.count(kw)
        return complexity

    def _get_source_segment(self, source, start, end):
        lines = source.splitlines()
        if start and end:
            return "\n".join(lines[start - 1:end])
        return ""

    def _query_file(self, path):
        self.cursor.execute("SELECT * FROM gui_files WHERE file_path = ?", (path,))
        f = self.cursor.fetchone()
        if not f:
            return (0, None, ("not_found", path, 0))
        self.cursor.execute("SELECT * FROM gui_classes WHERE file_path = ? ORDER BY line_start", (path,))
        classes = [dict(r) for r in self.cursor.fetchall()]
        self.cursor.execute("SELECT * FROM gui_bcl_stamps WHERE file_path = ? AND scope_type = 'FILE' ORDER BY stamp_tag", (path,))
        file_stamps = [dict(r) for r in self.cursor.fetchall()]
        return (1, {"file": dict(f), "classes": classes, "file_stamps": file_stamps}, None)

    def _query_class(self, name):
        self.cursor.execute("SELECT * FROM gui_classes WHERE class_name = ?", (name,))
        classes = [dict(r) for r in self.cursor.fetchall()]
        if not classes:
            return (0, None, ("not_found", name, 0))
        for cls in classes:
            self.cursor.execute("SELECT * FROM gui_comp_units WHERE class_name = ? AND file_path = ? ORDER BY line_start", (name, cls["file_path"]))
            cls["units"] = [dict(r) for r in self.cursor.fetchall()]
            self.cursor.execute("SELECT * FROM gui_bcl_stamps WHERE class_name = ? AND scope_type = 'CLASS' AND file_path = ? ORDER BY stamp_tag", (name, cls["file_path"]))
            cls["stamps"] = [dict(r) for r in self.cursor.fetchall()]
        return (1, classes, None)

    def _query_method(self, class_name, method_name):
        self.cursor.execute("SELECT * FROM gui_methods WHERE class_name = ? AND method_name = ?", (class_name, method_name))
        methods = [dict(r) for r in self.cursor.fetchall()]
        if not methods:
            return (0, None, ("not_found", "{}.{}".format(class_name, method_name), 0))
        for m in methods:
            self.cursor.execute("SELECT * FROM gui_bcl_stamps WHERE class_name = ? AND unit_name = ? AND file_path = ? ORDER BY stamp_tag", (class_name, method_name, m["file_path"]))
            m["stamps"] = [dict(r) for r in self.cursor.fetchall()]
        return (1, methods, None)

    def _query_stamps(self, scope_type, class_name):
        if class_name:
            self.cursor.execute("SELECT * FROM gui_bcl_stamps WHERE scope_type = ? AND class_name = ? ORDER BY stamp_tag", (scope_type, class_name))
        else:
            self.cursor.execute("SELECT * FROM gui_bcl_stamps WHERE scope_type = ? ORDER BY stamp_tag", (scope_type,))
        return (1, [dict(r) for r in self.cursor.fetchall()], None)

    def _say(self, topic):
        if topic == "overview":
            return self._say_overview()
        elif topic == "classes":
            return self._say_classes()
        elif topic == "stamps":
            return self._say_stamp_summary()
        return (0, None, ("unknown_topic", topic, 0))

    def _say_overview(self):
        self.cursor.execute("SELECT COUNT(*) FROM gui_files")
        files = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM gui_classes")
        classes = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM gui_comp_units")
        units = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM gui_methods")
        methods = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM gui_bcl_stamps")
        stamps = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM gui_edges")
        edges = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT stamp_tag, COUNT(*) as cnt FROM gui_bcl_stamps GROUP BY stamp_tag ORDER BY cnt DESC")
        tag_counts = [dict(r) for r in self.cursor.fetchall()]
        lines = []
        lines.append("GuisEngins.db OVERVIEW:")
        lines.append("  Files: {}".format(files))
        lines.append("  Classes: {}".format(classes))
        lines.append("  Comp Units: {}".format(units))
        lines.append("  Methods: {}".format(methods))
        lines.append("  BCL Stamps: {}".format(stamps))
        lines.append("  Edges: {}".format(edges))
        lines.append("")
        lines.append("BCL STAMP TAGS:")
        for t in tag_counts:
            lines.append("  {}: {}".format(t["stamp_tag"], t["cnt"]))
        return (1, "\n".join(lines), None)

    def _say_classes(self):
        self.cursor.execute("SELECT class_name, file_path, base_class, method_count, domain, purpose FROM gui_classes ORDER BY file_path, class_name")
        rows = [dict(r) for r in self.cursor.fetchall()]
        lines = ["ALL CLASSES ({}):".format(len(rows)), ""]
        current_file = ""
        for r in rows:
            fname = r["file_path"].split("/")[-1]
            if fname != current_file:
                current_file = fname
                lines.append("--- {} ---".format(fname))
            base = " ({})".format(r["base_class"]) if r["base_class"] else ""
            domain = " [{}]".format(r["domain"]) if r["domain"] else ""
            lines.append("  {}{}{} - {} methods".format(r["class_name"], base, domain, r["method_count"]))
        return (1, "\n".join(lines), None)

    def _say_stamp_summary(self):
        self.cursor.execute("SELECT scope_type, COUNT(*) as cnt FROM gui_bcl_stamps GROUP BY scope_type ORDER BY cnt DESC")
        scope_counts = [dict(r) for r in self.cursor.fetchall()]
        self.cursor.execute("SELECT stamp_tag, scope_type, COUNT(*) as cnt FROM gui_bcl_stamps GROUP BY stamp_tag, scope_type ORDER BY stamp_tag, scope_type")
        tag_scope = [dict(r) for r in self.cursor.fetchall()]
        lines = ["BCL STAMP SUMMARY:", ""]
        lines.append("BY SCOPE:")
        for s in scope_counts:
            lines.append("  {}: {} stamps".format(s["scope_type"], s["cnt"]))
        lines.append("")
        lines.append("BY TAG AND SCOPE:")
        current_tag = ""
        for t in tag_scope:
            if t["stamp_tag"] != current_tag:
                current_tag = t["stamp_tag"]
                lines.append("  {}:".format(t["stamp_tag"]))
            lines.append("    {}: {}".format(t["scope_type"], t["cnt"]))
        return (1, "\n".join(lines), None)

    def _get_stats(self):
        return self._say_overview()

    def read_state(self):
        return (1, {"stats": self.stats, "db_path": self.db_path}, None)

    def close(self):
        self.conn.commit()
        self.conn.close()


if __name__ == "__main__":
    ing = GuisEnginsIngester()
    ing.Run("reset")
    ok, data, err = ing.Run("ingest_all_gui_engines")
    if ok:
        print("Ingested {} files".format(data["total_ingested"]))
        if data.get("errors"):
            print("Errors: {}".format(len(data["errors"])))
    else:
        print("Error:", err)
    ok, text, err = ing.Run("Say", {"topic": "overview"})
    if ok:
        print()
        print(text)
    ok, text, err = ing.Run("Say", {"topic": "classes"})
    if ok:
        print()
        print(text)
    ok, text, err = ing.Run("Say", {"topic": "stamps"})
    if ok:
        print()
        print(text)
    ing.close()
