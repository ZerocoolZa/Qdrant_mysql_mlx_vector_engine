#!/usr/bin/env python3
#[@GHOST]{[@file<ast_def_store.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<ast_def_store>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
"""
AST Definition Store — one table, one row per function/method definition.

This is Layer 1: the structural substrate. Every function, every method,
every lambda — flattened into a single queryable table.

Schema: ci_definitions
  One row = one callable definition in the codebase.

Usage:
    from ast_def_store import AstDefStore
    store = AstDefStore("/tmp/ast_definitions.sqlite")
    store.ingest_scores(scores, root_folder)
    rows = store.query_all()
"""

import sqlite3
import time
import hashlib
import os
import ast
from typing import Dict, List, Optional, Tuple, Any


class AstDefStore:
    """Single-table SQLite store: one row per function/method definition."""

    SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ci_definitions (
    def_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL,

    -- identity
    name            TEXT NOT NULL,
    qualname        TEXT NOT NULL,
    kind            TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    module_name     TEXT NOT NULL,
    line_start      INTEGER NOT NULL,
    line_end        INTEGER NOT NULL,
    col_offset      INTEGER NOT NULL,
    end_col_offset  INTEGER NOT NULL,

    -- ownership
    class_name      TEXT,
    is_method       INTEGER NOT NULL DEFAULT 0,
    is_nested       INTEGER NOT NULL DEFAULT 0,
    parent_name     TEXT,
    decorator_count INTEGER NOT NULL DEFAULT 0,
    decorator_names TEXT,

    -- signature
    arg_count       INTEGER NOT NULL DEFAULT 0,
    arg_names       TEXT,
    has_vararg      INTEGER NOT NULL DEFAULT 0,
    has_kwarg       INTEGER NOT NULL DEFAULT 0,
    has_defaults    INTEGER NOT NULL DEFAULT 0,
    returns_annotation TEXT,

    -- body structure
    body_lines      INTEGER NOT NULL DEFAULT 0,
    docstring       TEXT,
    has_docstring   INTEGER NOT NULL DEFAULT 0,

    -- complexity
    cyclomatic      INTEGER NOT NULL DEFAULT 0,
    branches        INTEGER NOT NULL DEFAULT 0,
    loops           INTEGER NOT NULL DEFAULT 0,
    ifs             INTEGER NOT NULL DEFAULT 0,
    tries           INTEGER NOT NULL DEFAULT 0,
    withs           INTEGER NOT NULL DEFAULT 0,
    max_nesting     INTEGER NOT NULL DEFAULT 0,

    -- calls inside this def
    call_count      INTEGER NOT NULL DEFAULT 0,
    call_names      TEXT,
    recursive       INTEGER NOT NULL DEFAULT 0,

    -- variables
    assign_count    INTEGER NOT NULL DEFAULT 0,
    local_vars      TEXT,

    -- imports used
    imports_used    TEXT,

    -- dead code
    is_empty        INTEGER NOT NULL DEFAULT 0,
    is_pass_only    INTEGER NOT NULL DEFAULT 0,
    unused_imports  TEXT,

    -- scoring
    score           INTEGER NOT NULL DEFAULT 0,
    grade           TEXT NOT NULL,
    issues          TEXT,
    suggestions     TEXT,

    -- metadata
    file_hash       TEXT NOT NULL,
    source_code     TEXT,
    ast_hash        TEXT,
    timestamp       REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_def_run ON ci_definitions(run_id);
CREATE INDEX IF NOT EXISTS idx_def_name ON ci_definitions(name);
CREATE INDEX IF NOT EXISTS idx_def_qualname ON ci_definitions(qualname);
CREATE INDEX IF NOT EXISTS idx_def_file ON ci_definitions(file_path);
CREATE INDEX IF NOT EXISTS idx_def_class ON ci_definitions(class_name);
CREATE INDEX IF NOT EXISTS idx_def_kind ON ci_definitions(kind);
CREATE INDEX IF NOT EXISTS idx_def_complexity ON ci_definitions(cyclomatic);
CREATE INDEX IF NOT EXISTS idx_def_score ON ci_definitions(score);
CREATE INDEX IF NOT EXISTS idx_def_grade ON ci_definitions(grade);

CREATE TABLE IF NOT EXISTS ci_def_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL NOT NULL,
    root_folder TEXT NOT NULL,
    total_defs  INTEGER NOT NULL,
    total_files INTEGER NOT NULL
);
"""

    def __init__(self, db_path: str = "/tmp/ast_definitions.sqlite"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(self.SCHEMA_SQL)
        self.conn.commit()
        self.current_run_id: Optional[int] = None

    def close(self):
        self.conn.close()

    def _file_hash(self, file_path: str, root: str) -> str:
        abs_path = os.path.join(root, file_path)
        if not os.path.isfile(abs_path):
            return ""
        try:
            with open(abs_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def _extract_definitions(self, tree: ast.AST, file_path: str,
                             module_name: str, file_hash: str,
                             run_id: int, root: str,
                             source_lines: str = "") -> List[dict]:
        """Walk the AST and extract every function/method definition as a flat row."""
        rows = []

        class DefExtractor(ast.NodeVisitor):

            def __init__(self):
                self.scope_stack: List[str] = []
                self.class_stack: List[str] = []
                self.depth = 0
                self.seen: set = set()

            def _count_body(self, node) -> dict:
                """Count structural elements inside a function body."""
                counts = {
                    "branches": 0, "loops": 0, "ifs": 0, "tries": 0, "withs": 0,
                    "calls": 0, "call_names": [], "assigns": 0, "local_vars": set(),
                    "max_nesting": 0, "imports_used": set(),
                }

                class BodyCounter(ast.NodeVisitor):
                    def __init__(self):
                        self.depth = 0
                        self.max_depth = 0
                        self.in_def = False

                    def _visit_body(self, node):
                        for child in ast.iter_child_nodes(node):
                            self.visit(child)

                    def generic_visit(self, node):
                        self.depth += 1
                        self.max_depth = max(self.max_depth, self.depth)
                        super().generic_visit(node)
                        self.depth -= 1

                    def visit_If(self, node):
                        counts["ifs"] += 1
                        counts["branches"] += 1
                        self.generic_visit(node)

                    def visit_For(self, node):
                        counts["loops"] += 1
                        counts["branches"] += 1
                        self.generic_visit(node)

                    def visit_While(self, node):
                        counts["loops"] += 1
                        counts["branches"] += 1
                        self.generic_visit(node)

                    def visit_Try(self, node):
                        counts["tries"] += 1
                        counts["branches"] += 1
                        self.generic_visit(node)

                    def visit_With(self, node):
                        counts["withs"] += 1
                        self.generic_visit(node)

                    def visit_Call(self, node):
                        counts["calls"] += 1
                        if isinstance(node.func, ast.Name):
                            counts["call_names"].append(node.func.id)
                        elif isinstance(node.func, ast.Attribute):
                            counts["call_names"].append(node.func.attr)
                        self.generic_visit(node)

                    def visit_Assign(self, node):
                        counts["assigns"] += 1
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                counts["local_vars"].add(target.id)
                        self.generic_visit(node)

                    def visit_Import(self, node):
                        for alias in node.names:
                            counts["imports_used"].add(alias.name)
                        self.generic_visit(node)

                    def visit_ImportFrom(self, node):
                        if node.module:
                            counts["imports_used"].add(node.module)
                        self.generic_visit(node)

                counter = BodyCounter()
                counter._visit_body(node)
                counts["max_nesting"] = counter.max_depth
                counts["cyclomatic"] = counts["branches"] + 1
                counts["call_names"] = list(set(counts["call_names"]))
                counts["local_vars"] = list(counts["local_vars"])
                counts["imports_used"] = list(counts["imports_used"])
                return counts

            def _is_empty(self, node) -> Tuple[int, int]:
                is_empty = 0
                is_pass = 0
                if len(node.body) == 0:
                    is_empty = 1
                elif len(node.body) == 1:
                    if isinstance(node.body[0], ast.Pass):
                        is_pass = 1
                        is_empty = 1
                    elif isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                        is_pass = 0
                return is_empty, is_pass

            def _get_docstring(self, node) -> Tuple[str, int]:
                if node.body and isinstance(node.body[0], ast.Expr):
                    if isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                        return node.body[0].value.value, 1
                return "", 0

            def _get_decorators(self, node) -> Tuple[int, str]:
                names = []
                for dec in getattr(node, "decorator_list", []):
                    if isinstance(dec, ast.Name):
                        names.append(dec.id)
                    elif isinstance(dec, ast.Attribute):
                        names.append(dec.attr)
                    elif isinstance(dec, ast.Call):
                        if isinstance(dec.func, ast.Name):
                            names.append(dec.func.id)
                        elif isinstance(dec.func, ast.Attribute):
                            names.append(dec.func.attr)
                return len(names), ",".join(names)

            def _get_args(self, node) -> dict:
                args = node.args
                arg_names = [a.arg for a in args.args]
                return {
                    "count": len(arg_names),
                    "names": ",".join(arg_names),
                    "has_vararg": 1 if args.vararg else 0,
                    "has_kwarg": 1 if args.kwarg else 0,
                    "has_defaults": 1 if args.defaults else 0,
                }

            def _get_returns(self, node) -> str:
                if node.returns:
                    try:
                        return ast.unparse(node.returns)
                    except Exception:
                        return str(type(node.returns).__name__)
                return ""

            def _make_row(self, node, kind: str) -> dict:
                scope = self.scope_stack[:]
                parent = scope[-1] if scope else None
                class_name = None
                is_method = 0
                is_nested = 0

                if kind == "method":
                    class_name = self.class_stack[-1] if self.class_stack else None
                    is_method = 1
                if self.scope_stack:
                    is_nested = 1

                qualname = ".".join(scope + [node.name]) if scope else node.name
                dec_count, dec_names = self._get_decorators(node)
                arg_info = self._get_args(node)
                docstring, has_doc = self._get_docstring(node)
                is_empty, is_pass = self._is_empty(node)
                body_counts = self._count_body(node)

                line_end = getattr(node, "end_lineno", node.lineno) or node.lineno
                end_col = getattr(node, "end_col_offset", 0) or 0

                recursive = 0
                if node.name in body_counts["call_names"]:
                    recursive = 1

                try:
                    source_code = ast.unparse(node)
                except Exception:
                    source_code = ""

                try:
                    ast_hash = hashlib.md5(
                        ast.dump(node, annotate_fields=False).encode()
                    ).hexdigest()
                except Exception:
                    ast_hash = ""

                return {
                    "name": node.name,
                    "qualname": qualname,
                    "kind": kind,
                    "file_path": file_path,
                    "module_name": module_name,
                    "line_start": node.lineno,
                    "line_end": line_end,
                    "col_offset": node.col_offset or 0,
                    "end_col_offset": end_col,
                    "class_name": class_name,
                    "is_method": is_method,
                    "is_nested": is_nested,
                    "parent_name": parent,
                    "decorator_count": dec_count,
                    "decorator_names": dec_names,
                    "arg_count": arg_info["count"],
                    "arg_names": arg_info["names"],
                    "has_vararg": arg_info["has_vararg"],
                    "has_kwarg": arg_info["has_kwarg"],
                    "has_defaults": arg_info["has_defaults"],
                    "returns_annotation": self._get_returns(node),
                    "body_lines": line_end - node.lineno + 1,
                    "docstring": docstring[:500] if docstring else "",
                    "has_docstring": has_doc,
                    "cyclomatic": body_counts["cyclomatic"],
                    "branches": body_counts["branches"],
                    "loops": body_counts["loops"],
                    "ifs": body_counts["ifs"],
                    "tries": body_counts["tries"],
                    "withs": body_counts["withs"],
                    "max_nesting": body_counts["max_nesting"],
                    "call_count": body_counts["calls"],
                    "call_names": ",".join(body_counts["call_names"]),
                    "recursive": recursive,
                    "assign_count": body_counts["assigns"],
                    "local_vars": ",".join(body_counts["local_vars"]),
                    "imports_used": ",".join(body_counts["imports_used"]),
                    "is_empty": is_empty,
                    "is_pass_only": is_pass,
                    "unused_imports": "",
                    "score": 0,
                    "grade": "",
                    "issues": "",
                    "suggestions": "",
                    "file_hash": file_hash,
                    "source_code": source_code,
                    "ast_hash": ast_hash,
                    "timestamp": time.time(),
                    "run_id": run_id,
                }

            SKIP_NAMES = {
                "main", "__main__", "__init__", "__init_subclass__",
                "__new__", "__del__", "__enter__", "__exit__",
                "__post_init__",
            }

            def visit_FunctionDef(self, node):
                key = (node.name, node.lineno, id(node))
                if key in self.seen:
                    return
                self.seen.add(key)
                if node.name in self.SKIP_NAMES:
                    self.scope_stack.append(node.name)
                    self.generic_visit(node)
                    self.scope_stack.pop()
                    return
                kind = "function"
                if self.class_stack:
                    kind = "method"
                elif self.scope_stack:
                    kind = "nested_function"
                row = self._make_row(node, kind)
                rows.append(row)
                self.scope_stack.append(node.name)
                self.generic_visit(node)
                self.scope_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                key = (node.name, node.lineno, id(node))
                if key in self.seen:
                    return
                self.seen.add(key)
                self.scope_stack.append(node.name)
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()
                self.scope_stack.pop()

        extractor = DefExtractor()
        extractor.visit(tree)
        return rows

    def ingest_scores(self, scores: list, root_folder: str) -> int:
        """Ingest all definitions from scored files. Returns run_id."""
        cursor = self.conn.execute(
            "INSERT INTO ci_def_runs (timestamp, root_folder, total_defs, total_files) "
            "VALUES (?, ?, 0, ?)",
            (time.time(), root_folder, len(scores))
        )
        run_id = cursor.lastrowid
        self.current_run_id = run_id

        total_defs = 0
        score_map = {}
        for s in scores:
            fpath = s.metrics.file
            fhash = self._file_hash(fpath, root_folder)
            mod_name = fpath[:-3].replace(os.sep, ".") if fpath.endswith(".py") else fpath
            score_map[fpath] = s

            abs_path = os.path.join(root_folder, fpath)
            if not os.path.isfile(abs_path):
                continue

            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    source = f.read()
                tree = ast.parse(source)
            except Exception:
                continue

            def_rows = self._extract_definitions(tree, fpath, mod_name, fhash, run_id, root_folder, source)

            fm_map = {}
            for fm in s.metrics.function_metrics:
                fm_map[(fm.name, fm.line)] = fm

            for row in def_rows:
                fm = fm_map.get((row["name"], row["line_start"]))
                if fm:
                    row["score"] = getattr(fm, "score", 0)
                    row["grade"] = getattr(fm, "grade", "")
                    row["issues"] = ",".join(fm.issues)
                    row["suggestions"] = "|".join(getattr(fm, "suggestions", []))

                self.conn.execute(
                    "INSERT INTO ci_definitions "
                    "(run_id, name, qualname, kind, file_path, module_name, "
                    "line_start, line_end, col_offset, end_col_offset, "
                    "class_name, is_method, is_nested, parent_name, "
                    "decorator_count, decorator_names, "
                    "arg_count, arg_names, has_vararg, has_kwarg, has_defaults, returns_annotation, "
                    "body_lines, docstring, has_docstring, "
                    "cyclomatic, branches, loops, ifs, tries, withs, max_nesting, "
                    "call_count, call_names, recursive, "
                    "assign_count, local_vars, imports_used, "
                    "is_empty, is_pass_only, unused_imports, "
                    "score, grade, issues, suggestions, "
                    "file_hash, source_code, ast_hash, timestamp) "
                    "VALUES (" + ",".join(["?"] * 49) + ")",
                    (row["run_id"], row["name"], row["qualname"], row["kind"],
                     row["file_path"], row["module_name"],
                     row["line_start"], row["line_end"], row["col_offset"], row["end_col_offset"],
                     row["class_name"], row["is_method"], row["is_nested"], row["parent_name"],
                     row["decorator_count"], row["decorator_names"],
                     row["arg_count"], row["arg_names"], row["has_vararg"], row["has_kwarg"],
                     row["has_defaults"], row["returns_annotation"],
                     row["body_lines"], row["docstring"], row["has_docstring"],
                     row["cyclomatic"], row["branches"], row["loops"], row["ifs"],
                     row["tries"], row["withs"], row["max_nesting"],
                     row["call_count"], row["call_names"], row["recursive"],
                     row["assign_count"], row["local_vars"], row["imports_used"],
                     row["is_empty"], row["is_pass_only"], row["unused_imports"],
                     row["score"], row["grade"], row["issues"], row["suggestions"],
                     row["file_hash"], row["source_code"], row["ast_hash"], row["timestamp"])
                )
                total_defs += 1

        self.conn.execute(
            "UPDATE ci_def_runs SET total_defs = ? WHERE run_id = ?",
            (total_defs, run_id)
        )
        self.conn.commit()
        return run_id

    # -----------------------------------------------------------------------
    # QUERY API
    # -----------------------------------------------------------------------

    def _run_id(self) -> int:
        if self.current_run_id:
            return self.current_run_id
        row = self.conn.execute("SELECT run_id FROM ci_def_runs ORDER BY run_id DESC LIMIT 1").fetchone()
        return row["run_id"] if row else 0

    def query_all(self, limit: int = 500, offset: int = 0) -> List[dict]:
        """All definitions, paginated."""
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? ORDER BY file_path, line_start LIMIT ? OFFSET ?",
            (self._run_id(), limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_by_name(self, name: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND name LIKE ? ORDER BY cyclomatic DESC",
            (self._run_id(), "%" + name + "%")
        ).fetchall()
        return [dict(r) for r in rows]

    def query_by_file(self, file_path: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND file_path = ? ORDER BY line_start",
            (self._run_id(), file_path)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_by_class(self, class_name: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND class_name = ? ORDER BY line_start",
            (self._run_id(), class_name)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_methods(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND is_method = 1 ORDER BY file_path, line_start",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_functions(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND is_method = 0 ORDER BY file_path, line_start",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_recursive(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND recursive = 1",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_empty(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND is_empty = 1",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_no_docstring(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND has_docstring = 0 AND kind != 'nested_function'",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_high_complexity(self, threshold: int = 10) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND cyclomatic > ? ORDER BY cyclomatic DESC",
            (self._run_id(), threshold)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_deep_nesting(self, threshold: int = 8) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND max_nesting > ? ORDER BY max_nesting DESC",
            (self._run_id(), threshold)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_long_functions(self, threshold: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND body_lines > ? ORDER BY body_lines DESC",
            (self._run_id(), threshold)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_callers_of(self, func_name: str) -> List[dict]:
        """Find all definitions that call a given function."""
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND call_names LIKE ? ORDER BY file_path",
            (self._run_id(), "%" + func_name + "%")
        ).fetchall()
        return [dict(r) for r in rows]

    def query_decorated(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND decorator_count > 0 ORDER BY decorator_count DESC",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_with_vararg(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND has_vararg = 1",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_stats(self) -> dict:
        run_id = self._run_id()
        row = self.conn.execute(
            "SELECT COUNT(*) as total, "
            "SUM(is_method) as methods, "
            "SUM(is_method = 0) as functions, "
            "SUM(is_nested) as nested, "
            "SUM(recursive) as recursive, "
            "SUM(is_empty) as empty, "
            "SUM(has_docstring) as documented, "
            "SUM(has_docstring = 0) as undocumented, "
            "AVG(cyclomatic) as avg_complexity, "
            "AVG(body_lines) as avg_lines, "
            "MAX(cyclomatic) as max_complexity, "
            "MAX(body_lines) as max_lines "
            "FROM ci_definitions WHERE run_id = ?",
            (run_id,)
        ).fetchone()
        return dict(row) if row else {}

    def query_kind_summary(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT kind, COUNT(*) as cnt, AVG(cyclomatic) as avg_cx, AVG(body_lines) as avg_lines "
            "FROM ci_definitions WHERE run_id = ? GROUP BY kind ORDER BY cnt DESC",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_search(self, query: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_definitions WHERE run_id = ? AND "
            "(name LIKE ? OR qualname LIKE ? OR file_path LIKE ? OR class_name LIKE ? OR docstring LIKE ?) "
            "ORDER BY file_path, line_start",
            (self._run_id(), "%" + query + "%", "%" + query + "%",
             "%" + query + "%", "%" + query + "%", "%" + query + "%")
        ).fetchall()
        return [dict(r) for r in rows]

    def query_call_graph(self) -> List[dict]:
        """Build a call graph: def_name -> [called_names]."""
        rows = self.conn.execute(
            "SELECT name, qualname, file_path, call_names FROM ci_definitions WHERE run_id = ?",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_duplicate_names(self) -> List[dict]:
        """Functions with the same name in different files."""
        rows = self.conn.execute(
            "SELECT name, COUNT(*) as cnt, GROUP_CONCAT(file_path, ' | ') as files "
            "FROM ci_definitions WHERE run_id = ? "
            "GROUP BY name HAVING cnt > 1 ORDER BY cnt DESC",
            (self._run_id(),)
        ).fetchall()
        return [dict(r) for r in rows]
