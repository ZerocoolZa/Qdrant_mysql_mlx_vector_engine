# [@GHOST]{[@file<Dom_Reuse.py>][@domain<Dom_Unified>][@role<reuse_authority>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<reuse_authority>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{DomReuse — search BCL+graph+code, retrieve, test, fix, weight. Stop AI rewriting code. Only the strong survive.}
# [@CLASS]{DomReuse}
# [@METHOD]{Run,find,retrieve,deliver,test,fix,reweight,weakest,strongest,purge}

"""
DomReuse — code retrieval before generation.

STOP AI FROM WRITING CODE OVER AND OVER.

Pipeline:
  1. FIND      — search MySQL by BCL stamp, graph edges, keyword, signature
  2. RETRIEVE  — get the actual source code from the database
  3. DELIVER   — copy the code into the target file
  4. TEST      — compile check, VBStyle check
  5. FIX       — if broken, fix it, put corrected version back in DB
  6. WEIGHT    — every unit carries a weight score. Strong rise, weak sink, dead purged.

DIMENSIONS:
  - BCL stamp  — behavioral fingerprint (what the code DOES, not just its name)
  - Graph      — relationships (what it CALLS, what it IMPORTS, what STATE it reads)
  - Code       — the actual source text, ready to copy
  - Weight     — survival score (reused +1, fixed -2+1, compliant +5, dead -1/month)

USAGE:
  from Dom_Unified.Dom_Reuse import DomReuse

  dr = DomReuse()

  # Find a method that does X (by BCL behavior, not just name)
  ok, data, err = dr.Run("find", {"intent": "parse file and extract classes", "limit": 5})

  # Find by signature pattern
  ok, data, err = dr.Run("find", {"signature": "Run(self, command, params=None)", "limit": 5})

  # Find by graph — what methods call 'parse' and return Tuple3?
  ok, data, err = dr.Run("find", {"calls": "parse", "returns_tuple3": True})

  # Retrieve the actual source code
  ok, code, err = dr.Run("retrieve", {"method_id": 42})

  # Deliver — copy code into a target file
  ok, data, err = dr.Run("deliver", {"method_id": 42, "target_file": "/path/to/new_module.py"})

  # Test — compile + VBStyle check
  ok, data, err = dr.Run("test", {"method_id": 42})

  # Fix — mark as broken, provide fix, update DB
  ok, data, err = dr.Run("fix", {"method_id": 42, "fixed_source": "...", "note": "was missing Tuple3 return"})

  # Reweight — recalculate weight for a unit
  ok, data, err = dr.Run("reweight", {"method_id": 42})

  # Strongest — top units by weight
  ok, data, err = dr.Run("strongest", {"limit": 10})

  # Weakest — bottom units (candidates for purge)
  ok, data, err = dr.Run("weakest", {"limit": 10})

  # Purge — archive dead units (weight below threshold)
  ok, data, err = dr.Run("purge", {"threshold": -5})
"""

import os
import sqlite3
import datetime

try:
    from .DatabaseManager import DatabaseManager
    HAS_DM = True
except Exception:
    HAS_DM = False

try:
    from core.utility.msearch import MSearch
    HAS_MSEARCH = True
except Exception:
    HAS_MSEARCH = False

try:
    from .Dom_Indexer import DomIndexer
    HAS_INDEXER = True
except Exception:
    HAS_INDEXER = False


WEIGHT_REUSED = 1
WEIGHT_FIXED_BUG = -2
WEIGHT_FIXED_NOW = 1
WEIGHT_VBSTYLE_COMPLIANT = 5
WEIGHT_HAS_TESTS = 3
WEIGHT_HAS_BCL = 2
WEIGHT_NO_VIOLATIONS = 2
WEIGHT_HIGH_COMPLEXITY = -1
WEIGHT_DEAD_PER_MONTH = -1
WEIGHT_DUPLICATED = -3
WEIGHT_PURGE_THRESHOLD = -5


class DomReuse:
    """
    Code retrieval before generation. Search BCL + graph + code, retrieve, test, fix, weight.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "mysql_db": param.get("mysql_db", "bcl_ir") if param else "bcl_ir",
                "mysql_host": param.get("mysql_host", "localhost") if param else "localhost",
                "mysql_user": param.get("mysql_user", "root") if param else "root",
                "mysql_password": param.get("mysql_password", "") if param else "",
                "weight_db": param.get("weight_db", os.path.join(os.path.dirname(__file__), "reuse_weights.db")) if param else os.path.join(os.path.dirname(__file__), "reuse_weights.db"),
                "purge_threshold": param.get("purge_threshold", WEIGHT_PURGE_THRESHOLD) if param else WEIGHT_PURGE_THRESHOLD,
            },
            "stats": {"finds": 0, "retrieves": 0, "delivers": 0, "tests": 0, "fixes": 0, "reweights": 0, "purges": 0, "errors": 0},
        }
        self.mysql = None
        self.msearch = None
        self.indexer = None
        self.weight_conn = None
        self.graph = None
        self.memory = None
        self._init_mysql()
        self._init_msearch()
        self._init_indexer()
        self._init_weight_db()
        self._init_graph()
        self._init_memory()

    def Run(self, command, params=None):
        dispatch = {
            "find": self._cmd_find,
            "retrieve": self._cmd_retrieve,
            "deliver": self._cmd_deliver,
            "test": self._cmd_test,
            "fix": self._cmd_fix,
            "reweight": self._cmd_reweight,
            "strongest": self._cmd_strongest,
            "weakest": self._cmd_weakest,
            "purge": self._cmd_purge,
            "weight": self._cmd_get_weight,
            "find_in_files": self._cmd_find_in_files,
            "find_in_graph": self._cmd_find_in_graph,
            "magnetic": self._cmd_magnetic,
            "full": self._cmd_full,
            "magnetic_search": self._cmd_magnetic_search,
            "magnetic_graph": self._cmd_magnetic_graph,
            "compile": self._cmd_compile,
            "recall": self._cmd_recall,
            "update": self._cmd_update_memory,
            "evolve": self._cmd_evolve,
            "list_memory": self._cmd_list_memory,
            "forget": self._cmd_forget,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"Unknown: {command}", 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _init_mysql(self):
        if not HAS_DM:
            return
        self.mysql = DatabaseManager(param={
            "db_type": "mysql",
            "db_host": self.state["config"]["mysql_host"],
            "db_user": self.state["config"]["mysql_user"],
            "db_password": self.state["config"]["mysql_password"],
            "db_name": self.state["config"]["mysql_db"],
        })

    def _init_msearch(self):
        if not HAS_MSEARCH:
            return
        try:
            self.msearch = MSearch()
        except Exception:
            self.msearch = None

    def _init_indexer(self):
        if not HAS_INDEXER:
            return
        try:
            self.indexer = DomIndexer()
        except Exception:
            self.indexer = None

    def _init_weight_db(self):
        self.weight_conn = sqlite3.connect(self.state["config"]["weight_db"])
        self.weight_conn.row_factory = sqlite3.Row
        c = self.weight_conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS unit_weights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_type TEXT NOT NULL,
                unit_id INTEGER NOT NULL,
                unit_name TEXT,
                file_path TEXT,
                weight REAL DEFAULT 0,
                reuse_count INTEGER DEFAULT 0,
                fix_count INTEGER DEFAULT 0,
                last_used TEXT,
                last_fixed TEXT,
                created_at TEXT,
                UNIQUE(unit_type, unit_id)
            );
            CREATE TABLE IF NOT EXISTS weight_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_type TEXT,
                unit_id INTEGER,
                delta REAL,
                reason TEXT,
                logged_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_w_unit ON unit_weights(unit_type, unit_id);
            CREATE INDEX IF NOT EXISTS idx_w_weight ON unit_weights(weight);
        """)
        self.weight_conn.commit()

    def _init_graph(self):
        try:
            from .MagneticGraph import MagneticGraph
            self.graph = MagneticGraph()
        except Exception:
            self.graph = None

    def _init_memory(self):
        try:
            from .MemoryObject import MemoryObject
            self.memory = MemoryObject()
        except Exception:
            self.memory = None

    # ════════════════════════════════════════════
    # FIND — search by BCL, graph, keyword, signature
    # ════════════════════════════════════════════

    def _cmd_find(self, params):
        intent = self._p(params, "intent")
        name = self._p(params, "name")
        pattern = self._p(params, "pattern")
        signature = self._p(params, "signature")
        calls = self._p(params, "calls")
        semantic = self._p(params, "semantic", False)
        hybrid = self._p(params, "hybrid", False)
        limit = self._p(params, "limit", 10)
        keyword = name or pattern or intent or signature or calls
        if not keyword:
            return (0, None, ("ERR_PARAMS", "intent, name, pattern, signature, or calls required", 0))
        if name and "%" not in name:
            search_key = name
        elif pattern:
            search_key = pattern.replace("%", "")
        else:
            search_key = keyword
        if self.msearch:
            if hybrid:
                ok, data, err = self.msearch.Run("hybrid", {"keyword": search_key, "top": limit})
            elif semantic:
                ok, data, err = self.msearch.Run("semantic", {"keyword": search_key, "top": limit})
            else:
                ok, data, err = self.msearch.Run("search", {"keyword": search_key, "limit": limit})
            if ok and data:
                results = self._extract_methods_from_msearch(data)
                if results:
                    weighted = []
                    for row in results:
                        weight = self._get_weight("method", row.get("id", 0))
                        row["weight"] = weight
                        row["source"] = "msearch"
                        weighted.append(row)
                    weighted.sort(key=lambda x: x["weight"], reverse=True)
                    self.state["stats"]["finds"] += 1
                    return (1, {"count": len(weighted), "results": weighted, "engine": "msearch"}, None)
        if not self.mysql:
            return (0, None, ("ERR_NO_MYSQL", "MySQL not available and msearch failed", 0))
        results = []
        cols = "id, class_name, method_name, file_path, line_start, line_end, method_type, ast_hash, inputs, outputs, certain_count, probable_count"
        if name:
            ok, rows, err = self.mysql.Run("query", {
                "sql": f"SELECT {cols} FROM bcl_methods WHERE method_name = %s LIMIT %s",
                "args": [name, limit]
            })
            if ok:
                results = rows
        elif pattern:
            ok, rows, err = self.mysql.Run("query", {
                "sql": f"SELECT {cols} FROM bcl_methods WHERE method_name LIKE %s LIMIT %s",
                "args": [pattern, limit]
            })
            if ok:
                results = rows
        elif signature:
            ok, rows, err = self.mysql.Run("query", {
                "sql": f"SELECT {cols} FROM bcl_methods WHERE inputs LIKE %s LIMIT %s",
                "args": [f"%{signature}%", limit]
            })
            if ok:
                results = rows
        elif calls:
            ok, rows, err = self.mysql.Run("query", {
                "sql": f"SELECT DISTINCT m.id, m.class_name, m.method_name, m.file_path, m.line_start, m.line_end FROM bcl_methods m JOIN bcl_edges e ON e.source_method_id LIKE CONCAT(m.file_path, '::', m.class_name, '.', m.method_name) WHERE e.target LIKE %s AND e.edge_type = 'CALL' LIMIT %s",
                "args": [f"%{calls}%", limit]
            })
            if ok:
                results = rows
        elif intent:
            ok, rows, err = self.mysql.Run("query", {
                "sql": f"SELECT {cols} FROM bcl_methods WHERE method_name LIKE %s OR class_name LIKE %s LIMIT %s",
                "args": [f"%{intent}%", f"%{intent}%", limit]
            })
            if ok:
                results = rows
        weighted = []
        for row in results:
            weight = self._get_weight("method", row["id"])
            weighted.append({**row, "weight": weight})
        weighted.sort(key=lambda x: x["weight"], reverse=True)
        self.state["stats"]["finds"] += 1
        return (1, {"count": len(weighted), "results": weighted, "engine": "mysql_fallback"}, None)

    def _extract_methods_from_msearch(self, data):
        """Extract method-like results from msearch output."""
        results = []
        tables = data.get("tables", []) if isinstance(data, dict) else data
        if isinstance(tables, dict):
            tables = [tables]
        for table in tables:
            if not isinstance(table, dict):
                continue
            rows = table.get("rows", [])
            table_name = table.get("table", "")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                method_name = row.get("method_name", row.get("entity_name", row.get("class_name", "")))
                class_name = row.get("class_name", "")
                file_path = row.get("file_path", row.get("source_file", ""))
                if method_name:
                    results.append({
                        "id": row.get("id", row.get("fact_id", 0)),
                        "class_name": class_name,
                        "method_name": method_name,
                        "file_path": file_path,
                        "table": table_name,
                        "raw": row,
                    })
        return results

    # ════════════════════════════════════════════
    # RETRIEVE — get the actual source code from DB
    # ════════════════════════════════════════════

    def _cmd_retrieve(self, params):
        if not self.mysql:
            return (0, None, ("ERR_NO_MYSQL", "MySQL not available", 0))
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        if method_id:
            ok, rows, err = self.mysql.Run("query", {
                "sql": "SELECT id, class_name, method_name, file_path, line_start, line_end, method_type, ast_hash, inputs, outputs FROM bcl_methods WHERE id = %s",
                "args": [method_id]
            })
        elif class_id:
            ok, rows, err = self.mysql.Run("query", {
                "sql": "SELECT id, class_name, file_path, line_start, line_end FROM bcl_classes WHERE id = %s",
                "args": [class_id]
            })
        else:
            return (0, None, ("ERR_PARAMS", "method_id or class_id required", 0))
        if not ok or not rows:
            return (0, None, ("ERR_NOT_FOUND", "unit not found in database", 0))
        unit = rows[0]
        source_text = self._read_source_from_disk(unit.get("file_path", ""), unit.get("line_start", 0), unit.get("line_end", 0))
        unit["source_text"] = source_text
        self._bump_reuse("method" if method_id else "class", method_id or class_id, unit.get("method_name", unit.get("class_name", "")), unit.get("file_path", ""))
        self.state["stats"]["retrieves"] += 1
        return (1, unit, None)

    def _read_source_from_disk(self, file_path, line_start, line_end):
        if not file_path or not os.path.exists(file_path):
            return ""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            start = max(0, (line_start or 1) - 1)
            end = line_end or len(lines)
            return "".join(lines[start:end])
        except Exception:
            return ""

    # ════════════════════════════════════════════
    # DELIVER — copy code into a target file
    # ════════════════════════════════════════════

    def _cmd_deliver(self, params):
        if not self.mysql:
            return (0, None, ("ERR_NO_MYSQL", "MySQL not available", 0))
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        target_file = self._p(params, "target_file")
        if not target_file:
            return (0, None, ("ERR_PARAMS", "target_file required", 0))
        ok, unit, err = self._cmd_retrieve({"method_id": method_id, "class_id": class_id})
        if not ok:
            return (0, None, err)
        source = unit.get("source_text", "")
        if not source:
            return (0, None, ("ERR_NO_SOURCE", "no source_text in database for this unit", 0))
        mode = self._p(params, "mode", "append")
        try:
            if mode == "overwrite" or not os.path.exists(target_file):
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(source)
            else:
                with open(target_file, "a", encoding="utf-8") as f:
                    f.write("\n\n" + source)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_WRITE", str(e), 0))
        self.state["stats"]["delivers"] += 1
        return (1, {
            "delivered": True,
            "target_file": target_file,
            "mode": mode,
            "source_file": unit.get("source_file", ""),
            "unit_name": unit.get("method_name", unit.get("class_name", "")),
            "bytes_written": len(source),
        }, None)

    # ════════════════════════════════════════════
    # TEST — compile + VBStyle check
    # ════════════════════════════════════════════

    def _cmd_test(self, params):
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        ok, unit, err = self._cmd_retrieve({"method_id": method_id, "class_id": class_id})
        if not ok:
            return (0, None, err)
        source = unit.get("source_text", "")
        checks = {
            "compiles": False,
            "has_run": False,
            "has_tuple3": False,
            "has_state_dict": False,
            "no_print": False,
            "no_decorators": False,
            "no_self_underscore": False,
        }
        try:
            compile(source, "<unit>", "exec")
            checks["compiles"] = True
        except SyntaxError:
            checks["compiles"] = False
        checks["has_run"] = "def Run(" in source
        checks["has_tuple3"] = "(1," in source and "None)" in source
        checks["has_state_dict"] = "self.state" in source
        checks["no_print"] = "print(" not in source
        checks["no_decorators"] = "@property" not in source and "@staticmethod" not in source and "@classmethod" not in source
        checks["no_self_underscore"] = "self._" not in source
        passed = sum(1 for v in checks.values() if v)
        is_compliant = passed == len(checks)
        self.state["stats"]["tests"] += 1
        return (1, {
            "unit_id": method_id or class_id,
            "checks": checks,
            "passed": passed,
            "total": len(checks),
            "compliant": is_compliant,
        }, None)

    # ════════════════════════════════════════════
    # FIX — mark broken, provide fix, update DB
    # ════════════════════════════════════════════

    def _cmd_fix(self, params):
        if not self.mysql:
            return (0, None, ("ERR_NO_MYSQL", "MySQL not available", 0))
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        fixed_source = self._p(params, "fixed_source")
        note = self._p(params, "note", "")
        if not fixed_source:
            return (0, None, ("ERR_PARAMS", "fixed_source required", 0))
        unit_type = "method" if method_id else "class"
        unit_id = method_id or class_id
        if method_id:
            ok, _, err = self.mysql.Run("execute", {
                "sql": "UPDATE bcl_methods SET source_text = %s WHERE id = %s",
                "args": [fixed_source, method_id]
            })
        else:
            ok, _, err = self.mysql.Run("execute", {
                "sql": "UPDATE bcl_classes SET source_text = %s WHERE id = %s",
                "args": [fixed_source, class_id]
            })
        if not ok:
            return (0, None, err)
        self._adjust_weight(unit_type, unit_id, WEIGHT_FIXED_BUG, f"bug fixed: {note}")
        self._adjust_weight(unit_type, unit_id, WEIGHT_FIXED_NOW, "fix applied")
        self._bump_fix(unit_type, unit_id)
        self.state["stats"]["fixes"] += 1
        return (1, {
            "fixed": True,
            "unit_type": unit_type,
            "unit_id": unit_id,
            "note": note,
            "weight_delta": WEIGHT_FIXED_BUG + WEIGHT_FIXED_NOW,
        }, None)

    # ════════════════════════════════════════════
    # WEIGHT — survival score
    # ════════════════════════════════════════════

    def _cmd_reweight(self, params):
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        unit_type = "method" if method_id else "class"
        unit_id = method_id or class_id
        if not self.mysql:
            return (0, None, ("ERR_NO_MYSQL", "MySQL not available", 0))
        if method_id:
            ok, rows, err = self.mysql.Run("query", {"sql": "SELECT * FROM bcl_methods WHERE id = %s", "args": [method_id]})
        else:
            ok, rows, err = self.mysql.Run("query", {"sql": "SELECT * FROM bcl_classes WHERE id = %s", "args": [class_id]})
        if not ok or not rows:
            return (0, None, ("ERR_NOT_FOUND", "unit not found", 0))
        unit = rows[0]
        source = unit.get("source_text", "")
        weight = 0
        if "def Run(" in source:
            weight += WEIGHT_VBSTYLE_COMPLIANT
        if "(1," in source and "None)" in source:
            weight += WEIGHT_NO_VIOLATIONS
        if "self.state" in source:
            weight += WEIGHT_VBSTYLE_COMPLIANT
        if "print(" in source:
            weight -= WEIGHT_NO_VIOLATIONS
        if "@property" in source or "@staticmethod" in source:
            weight -= WEIGHT_NO_VIOLATIONS
        if "self._" in source:
            weight -= WEIGHT_NO_VIOLATIONS
        existing = self._get_weight_record(unit_type, unit_id)
        if existing:
            weight += existing["reuse_count"] * WEIGHT_REUSED
            weight -= existing["fix_count"] * 1
        self._set_weight(unit_type, unit_id, unit.get("method_name", unit.get("class_name", "")), unit.get("source_file", ""), weight)
        self.state["stats"]["reweights"] += 1
        return (1, {"unit_type": unit_type, "unit_id": unit_id, "weight": weight}, None)

    def _cmd_get_weight(self, params):
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        unit_type = "method" if method_id else "class"
        unit_id = method_id or class_id
        weight = self._get_weight(unit_type, unit_id)
        record = self._get_weight_record(unit_type, unit_id)
        if not record:
            return (1, {"weight": 0, "reuse_count": 0, "fix_count": 0}, None)
        return (1, dict(record), None)

    def _cmd_strongest(self, params):
        limit = self._p(params, "limit", 10)
        c = self.weight_conn.cursor()
        c.execute("SELECT * FROM unit_weights ORDER BY weight DESC LIMIT ?", [limit])
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "units": rows}, None)

    def _cmd_weakest(self, params):
        limit = self._p(params, "limit", 10)
        c = self.weight_conn.cursor()
        c.execute("SELECT * FROM unit_weights ORDER BY weight ASC LIMIT ?", [limit])
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "units": rows}, None)

    def _cmd_purge(self, params):
        threshold = self._p(params, "threshold", self.state["config"]["purge_threshold"])
        c = self.weight_conn.cursor()
        c.execute("SELECT * FROM unit_weights WHERE weight < ?", [threshold])
        purged = [dict(r) for r in c.fetchall()]
        c.execute("DELETE FROM unit_weights WHERE weight < ?", [threshold])
        self.weight_conn.commit()
        self.state["stats"]["purges"] += len(purged)
        return (1, {"purged": len(purged), "threshold": threshold, "units": purged}, None)

    # ════════════════════════════════════════════
    # LAYER 2: FIND IN FILES — grep actual file contents on disk
    # ════════════════════════════════════════════

    def _cmd_find_in_files(self, params):
        pattern = self._p(params, "pattern")
        path = self._p(params, "path", "/Users/wws/Qdrant_mysql_mlx_vector_engine")
        limit = self._p(params, "limit", 20)
        if not pattern:
            return (0, None, ("ERR_PARAMS", "pattern required", 0))
        import subprocess
        try:
            cmd = ["rg", "--line-number", "--no-heading", "--color", "never", f"--max-count={limit}", pattern, path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            matches = []
            for line in result.stdout.strip().split("\n"):
                if ":" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        matches.append({"file": parts[0], "line": int(parts[1]), "text": parts[2][:200]})
            self.state["stats"]["finds"] += 1
            return (1, {"count": len(matches), "results": matches, "engine": "ripgrep"}, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_GREP", str(e), 0))

    # ════════════════════════════════════════════
    # LAYER 3: FIND IN GRAPH — DomIndexer in-RAM AST query
    # ════════════════════════════════════════════

    def _cmd_find_in_graph(self, params):
        if not self.indexer:
            return (0, None, ("ERR_NO_INDEXER", "DomIndexer not available", 0))
        method_name = self._p(params, "method_name")
        class_name = self._p(params, "class_name")
        edge_type = self._p(params, "edge_type")
        bcl_stamp = self._p(params, "bcl_stamp")
        limit = self._p(params, "limit", 20)
        if method_name:
            ok, data, err = self.indexer.Run("find_method", {"name": method_name, "limit": limit})
        elif class_name:
            ok, data, err = self.indexer.Run("find_class", {"name": class_name, "limit": limit})
        elif edge_type:
            ok, data, err = self.indexer.Run("edges", {"edge_type": edge_type, "limit": limit})
        elif bcl_stamp:
            ok, data, err = self.indexer.Run("bcl", {"pattern": bcl_stamp, "limit": limit})
        else:
            return (0, None, ("ERR_PARAMS", "method_name, class_name, edge_type, or bcl_stamp required", 0))
        if not ok:
            return (0, None, err)
        self.state["stats"]["finds"] += 1
        return (1, {"count": data.get("count", 0) if isinstance(data, dict) else len(data), "results": data, "engine": "domindexer"}, None)

    # ════════════════════════════════════════════
    # MAGNETIC SEARCH — magnetic_runtime C binary (17 modules)
    # Pulls results from all directions: files, chats, docs, code, graph
    # Like magneto — attracts everything related to the query
    # ════════════════════════════════════════════

    def _cmd_magnetic(self, params):
        query = self._p(params, "query")
        mode = self._p(params, "mode", "search")
        fields = self._p(params, "fields", "")
        if not query and mode == "search":
            return (0, None, ("ERR_PARAMS", "query required", 0))
        binary = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Cascade_toolStack", "bin_tools", "magnetic")
        if not os.path.exists(binary):
            return (0, None, ("ERR_NO_BINARY", f"magnetic binary not found at {binary}", 0))
        import subprocess
        try:
            if mode == "convergence":
                cmd = [binary, "--convergence", fields or query]
            elif mode == "bootstrap":
                cmd = [binary, "--bootstrap"]
            else:
                cmd = [binary, query]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.state["stats"]["errors"] += 1
                return (0, None, ("ERR_MAGNETIC", result.stderr.strip()[:200], 0))
            output = result.stdout.strip()
            try:
                import json
                data = json.loads(output)
            except Exception:
                data = {"raw": output}
            self.state["stats"]["finds"] += 1
            return (1, {"count": 1, "results": data, "engine": "magnetic", "mode": mode, "query": query}, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_MAGNETIC_EXEC", str(e), 0))

    # ════════════════════════════════════════════
    # FULL SEMANTIC OBJECT — one search, all 12 sections
    # ════════════════════════════════════════════

    def _cmd_full(self, params):
        query = self._p(params, "query") or self._p(params, "keyword") or self._p(params, "name")
        limit = self._p(params, "limit", 10)
        mode = self._p(params, "mode", "contains")
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))
        if not self.msearch:
            return (0, None, ("ERR_NO_MSEARCH", "msearch not available", 0))
        ok, data, err = self.msearch.Run("full", {"keyword": query, "limit": limit, "mode": mode})
        if not ok:
            return (0, None, err)
        self.state["stats"]["finds"] += 1
        # MSearch wraps output in {"tables": [...]}, unwrap it
        raw = data
        if isinstance(raw, dict) and "tables" in raw:
            tables = raw["tables"]
            if tables and isinstance(tables[0], dict):
                raw = tables[0]
        sections = raw.get("sections", {}) if isinstance(raw, dict) else {}
        section_counts = {}
        for key, val in sections.items():
            section_counts[key] = len(val) if isinstance(val, list) else (1 if val else 0)
        return (1, {
            "query": query,
            "engine": "msearch_full",
            "section_counts": section_counts,
            "sections": sections,
            "actions": raw.get("actions", []),
        }, None)

    # ════════════════════════════════════════════
    # MAGNETIC SEARCH — context reconstruction with radius expansion
    # Finds keyword, expands ±N messages around each hit, returns context packet
    # ════════════════════════════════════════════

    def _cmd_magnetic_search(self, params):
        query = self._p(params, "query") or self._p(params, "keyword") or self._p(params, "name")
        radius = self._p(params, "radius", 200)
        limit = self._p(params, "limit", 10)
        mode = self._p(params, "mode", "contains")
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))
        if not self.msearch:
            return (0, None, ("ERR_NO_MSEARCH", "msearch not available", 0))
        mp = {"keyword": query, "radius": radius, "limit": limit, "mode": mode}
        if self._p(params, "chat_only"):
            mp["chat_only"] = True
        if self._p(params, "graph_only"):
            mp["graph_only"] = True
        ok, data, err = self.msearch.Run("magnetic", mp)
        if not ok:
            return (0, None, err)
        self.state["stats"]["finds"] += 1
        raw = data
        if isinstance(raw, dict) and "tables" in raw:
            tables = raw["tables"]
            if tables and isinstance(tables[0], dict):
                raw = tables[0]
        packet = raw.get("packet", {}) if isinstance(raw, dict) else {}
        section_counts = {}
        for key, val in packet.items():
            if val is None:
                section_counts[key] = 0
            elif isinstance(val, list):
                section_counts[key] = len(val)
            elif isinstance(val, dict):
                section_counts[key] = sum(len(v) for v in val.values() if isinstance(v, list))
            else:
                section_counts[key] = 1
        return (1, {
            "query": query,
            "radius": radius,
            "engine": "magnetic",
            "section_counts": section_counts,
            "packet": packet,
            "actions": raw.get("actions", []),
        }, None)

    # ════════════════════════════════════════════
    # MAGNETIC GRAPH — multi-hop relationship traversal
    # chat -> file -> class -> BCL -> graph -> callers -> rules -> chat
    # ════════════════════════════════════════════

    def _cmd_magnetic_graph(self, params):
        query = self._p(params, "query") or self._p(params, "keyword") or self._p(params, "name")
        max_hops = self._p(params, "max_hops", 3)
        radius = self._p(params, "radius", 200)
        limit = self._p(params, "limit", 10)
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))
        if not self.graph:
            return (0, None, ("ERR_NO_GRAPH", "MagneticGraph not available", 0))
        ok, data, err = self.graph.Run("traverse", {
            "query": query,
            "max_hops": max_hops,
            "radius": radius,
            "limit": limit,
        })
        if not ok:
            return (0, None, err)
        self.state["stats"]["finds"] += 1
        return (1, {
            "query": query,
            "engine": "magnetic_graph",
            "total_hops": data.get("total_hops", 0),
            "total_nodes": data.get("total_nodes", 0),
            "total_edges": data.get("total_edges", 0),
            "hops": data.get("hops", []),
            "nodes": data.get("nodes", {}),
            "provenance": data.get("provenance", []),
        }, None)

    # ════════════════════════════════════════════
    # MEMORY OBJECT — compile, recall, evolve persistent memory
    # ════════════════════════════════════════════

    def _cmd_compile(self, params):
        if not self.memory:
            return (0, None, ("ERR_NO_MEMORY", "MemoryObject not available", 0))
        ok, data, err = self.memory.Run("compile", params)
        if ok:
            self.state["stats"]["finds"] += 1
        return (ok, data, err)

    def _cmd_recall(self, params):
        if not self.memory:
            return (0, None, ("ERR_NO_MEMORY", "MemoryObject not available", 0))
        ok, data, err = self.memory.Run("recall", params)
        if ok:
            self.state["stats"]["finds"] += 1
        return (ok, data, err)

    def _cmd_evolve(self, params):
        if not self.memory:
            return (0, None, ("ERR_NO_MEMORY", "MemoryObject not available", 0))
        ok, data, err = self.memory.Run("evolve", params)
        return (ok, data, err)

    def _cmd_update_memory(self, params):
        if not self.memory:
            return (0, None, ("ERR_NO_MEMORY", "MemoryObject not available", 0))
        ok, data, err = self.memory.Run("update", params)
        return (ok, data, err)

    def _cmd_list_memory(self, params):
        if not self.memory:
            return (0, None, ("ERR_NO_MEMORY", "MemoryObject not available", 0))
        ok, data, err = self.memory.Run("list", params)
        return (ok, data, err)

    def _cmd_forget(self, params):
        if not self.memory:
            return (0, None, ("ERR_NO_MEMORY", "MemoryObject not available", 0))
        ok, data, err = self.memory.Run("forget", params)
        return (ok, data, err)

    # ════════════════════════════════════════════
    # WEIGHT HELPERS
    # ════════════════════════════════════════════

    def _get_weight_record(self, unit_type, unit_id):
        c = self.weight_conn.cursor()
        c.execute("SELECT * FROM unit_weights WHERE unit_type = ? AND unit_id = ?", [unit_type, unit_id])
        return c.fetchone()

    def _get_weight(self, unit_type, unit_id):
        rec = self._get_weight_record(unit_type, unit_id)
        return rec["weight"] if rec else 0

    def _set_weight(self, unit_type, unit_id, name, file_path, weight):
        c = self.weight_conn.cursor()
        now = datetime.datetime.now().isoformat()
        c.execute("""
            INSERT INTO unit_weights (unit_type, unit_id, unit_name, file_path, weight, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(unit_type, unit_id) DO UPDATE SET weight = ?, unit_name = ?, file_path = ?
        """, [unit_type, unit_id, name, file_path, weight, now, weight, name, file_path])
        self.weight_conn.commit()

    def _adjust_weight(self, unit_type, unit_id, delta, reason):
        c = self.weight_conn.cursor()
        now = datetime.datetime.now().isoformat()
        c.execute("SELECT weight FROM unit_weights WHERE unit_type = ? AND unit_id = ?", [unit_type, unit_id])
        row = c.fetchone()
        current = row["weight"] if row else 0
        new_weight = current + delta
        c.execute("""
            INSERT INTO unit_weights (unit_type, unit_id, weight, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(unit_type, unit_id) DO UPDATE SET weight = ?
        """, [unit_type, unit_id, new_weight, now, new_weight])
        c.execute("INSERT INTO weight_log (unit_type, unit_id, delta, reason, logged_at) VALUES (?, ?, ?, ?, ?)",
                  [unit_type, unit_id, delta, reason, now])
        self.weight_conn.commit()

    def _bump_reuse(self, unit_type, unit_id, name, file_path):
        c = self.weight_conn.cursor()
        now = datetime.datetime.now().isoformat()
        c.execute("SELECT reuse_count, weight FROM unit_weights WHERE unit_type = ? AND unit_id = ?", [unit_type, unit_id])
        row = c.fetchone()
        if row:
            c.execute("UPDATE unit_weights SET reuse_count = ?, weight = ?, last_used = ? WHERE unit_type = ? AND unit_id = ?",
                      [row["reuse_count"] + 1, row["weight"] + WEIGHT_REUSED, now, unit_type, unit_id])
        else:
            c.execute("INSERT INTO unit_weights (unit_type, unit_id, unit_name, file_path, weight, reuse_count, last_used, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      [unit_type, unit_id, name, file_path, WEIGHT_REUSED, 1, now, now])
        c.execute("INSERT INTO weight_log (unit_type, unit_id, delta, reason, logged_at) VALUES (?, ?, ?, ?, ?)",
                  [unit_type, unit_id, WEIGHT_REUSED, "retrieved", now])
        self.weight_conn.commit()

    def _bump_fix(self, unit_type, unit_id):
        c = self.weight_conn.cursor()
        now = datetime.datetime.now().isoformat()
        c.execute("SELECT fix_count FROM unit_weights WHERE unit_type = ? AND unit_id = ?", [unit_type, unit_id])
        row = c.fetchone()
        if row:
            c.execute("UPDATE unit_weights SET fix_count = ?, last_fixed = ? WHERE unit_type = ? AND unit_id = ?",
                      [row["fix_count"] + 1, now, unit_type, unit_id])
        self.weight_conn.commit()
