#!/usr/bin/env python3
"""
Code Intelligence MySQL — persistent powerhouse for AST code structures.

Creates and manages a MySQL database 'code_intel' that stores:
  - Every scan run with aggregate stats
  - Every file with full metrics + score + BCL + hash
  - Every function with complexity, nesting, args, issues, suggestions
  - Every class with method count
  - Every dependency edge
  - Every change between runs (added/modified/deleted + score delta)

This is the permanent store. SQLite is the scratch pad. MySQL is the memory.

Tables:
  ci_scan_runs     — one row per scan
  ci_files         — per-file metrics + scores
  ci_functions     — per-function metrics + complexity
  ci_classes       — per-class registry
  ci_dependencies  — import edges
  ci_change_log    — file added/modified/deleted between runs

Usage:
    from code_intel_mysql import CodeIntelMySQL
    db = CodeIntelMySQL()
    db.ingest_scores(scores, graph, root_folder)
    rows = db.query_god_functions()
"""

import mysql.connector
import time
import hashlib
import os
from typing import Dict, List, Optional, Tuple, Any


SCHEMA_STATEMENTS = [
    "CREATE DATABASE IF NOT EXISTS code_intel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",

    """CREATE TABLE IF NOT EXISTS code_intel.ci_scan_runs (
        run_id         INT AUTO_INCREMENT PRIMARY KEY,
        timestamp      DOUBLE NOT NULL,
        root_folder    VARCHAR(512) NOT NULL,
        total_files    INT NOT NULL,
        parsed_ok      INT NOT NULL,
        parse_errors   INT NOT NULL,
        avg_score      DOUBLE NOT NULL,
        grade_a        INT NOT NULL,
        grade_b        INT NOT NULL,
        grade_c        INT NOT NULL,
        grade_d        INT NOT NULL,
        grade_e        INT NOT NULL,
        grade_f        INT NOT NULL,
        cycles         INT NOT NULL,
        unused_imports INT NOT NULL,
        god_functions  INT NOT NULL,
        empty_functions INT NOT NULL
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS code_intel.ci_files (
        file_id     INT AUTO_INCREMENT PRIMARY KEY,
        run_id      INT NOT NULL,
        file_path   VARCHAR(512) NOT NULL,
        module_name VARCHAR(512) NOT NULL,
        lines       INT NOT NULL,
        functions   INT NOT NULL,
        classes     INT NOT NULL,
        loops       INT NOT NULL,
        ifs         INT NOT NULL,
        max_depth   INT NOT NULL,
        imports     INT NOT NULL,
        score       INT NOT NULL,
        grade       VARCHAR(2) NOT NULL,
        structure   INT NOT NULL,
        complexity  INT NOT NULL,
        hygiene     INT NOT NULL,
        bcl         INT NOT NULL,
        bcl_format  VARCHAR(32) NOT NULL,
        bcl_tags    VARCHAR(256) NOT NULL,
        file_hash   VARCHAR(64) NOT NULL,
        issues      TEXT NOT NULL,
        parse_error TEXT,
        INDEX idx_files_run (run_id),
        INDEX idx_files_path (file_path),
        INDEX idx_files_grade (grade),
        INDEX idx_files_score (score),
        FOREIGN KEY (run_id) REFERENCES code_intel.ci_scan_runs(run_id)
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS code_intel.ci_functions (
        func_id     INT AUTO_INCREMENT PRIMARY KEY,
        file_id     INT NOT NULL,
        run_id      INT NOT NULL,
        name        VARCHAR(256) NOT NULL,
        line        INT NOT NULL,
        end_line    INT NOT NULL,
        lines       INT NOT NULL,
        args        INT NOT NULL,
        branches    INT NOT NULL,
        loops       INT NOT NULL,
        max_depth   INT NOT NULL,
        complexity  INT NOT NULL,
        issues      VARCHAR(512) NOT NULL,
        suggestions TEXT NOT NULL,
        is_method   TINYINT NOT NULL DEFAULT 0,
        class_name  VARCHAR(256) DEFAULT NULL,
        INDEX idx_funcs_file (file_id),
        INDEX idx_funcs_run (run_id),
        INDEX idx_funcs_name (name),
        INDEX idx_funcs_complexity (complexity),
        INDEX idx_funcs_class (class_name),
        FOREIGN KEY (file_id) REFERENCES code_intel.ci_files(file_id),
        FOREIGN KEY (run_id) REFERENCES code_intel.ci_scan_runs(run_id)
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS code_intel.ci_classes (
        class_id     INT AUTO_INCREMENT PRIMARY KEY,
        file_id      INT NOT NULL,
        run_id       INT NOT NULL,
        name         VARCHAR(256) NOT NULL,
        line         INT NOT NULL,
        method_count INT NOT NULL,
        bases        VARCHAR(512) DEFAULT NULL,
        INDEX idx_classes_file (file_id),
        INDEX idx_classes_run (run_id),
        INDEX idx_classes_name (name),
        FOREIGN KEY (file_id) REFERENCES code_intel.ci_files(file_id),
        FOREIGN KEY (run_id) REFERENCES code_intel.ci_scan_runs(run_id)
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS code_intel.ci_dependencies (
        dep_id   INT AUTO_INCREMENT PRIMARY KEY,
        run_id   INT NOT NULL,
        source   VARCHAR(512) NOT NULL,
        target   VARCHAR(512) NOT NULL,
        INDEX idx_deps_source (source),
        INDEX idx_deps_target (target),
        INDEX idx_deps_run (run_id),
        FOREIGN KEY (run_id) REFERENCES code_intel.ci_scan_runs(run_id)
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS code_intel.ci_change_log (
        change_id   INT AUTO_INCREMENT PRIMARY KEY,
        run_id      INT NOT NULL,
        file_path   VARCHAR(512) NOT NULL,
        change_type VARCHAR(16) NOT NULL,
        old_score   INT,
        new_score   INT,
        delta       INT,
        timestamp   DOUBLE NOT NULL,
        INDEX idx_changes_run (run_id),
        INDEX idx_changes_file (file_path),
        INDEX idx_changes_type (change_type),
        FOREIGN KEY (run_id) REFERENCES code_intel.ci_scan_runs(run_id)
    ) ENGINE=InnoDB""",
]


class CodeIntelMySQL:

    def __init__(self, host: str = "localhost", port: int = 3306,
                 user: str = "root", password: str = "", database: str = "code_intel"):
        self.conn = mysql.connector.connect(
            host=host, port=port, user=user, password=password,
            charset="utf8mb4", collation="utf8mb4_unicode_ci"
        )
        self.cursor = self.conn.cursor(dictionary=True)
        self._init_schema()
        self.conn.database = database
        self.current_run_id: Optional[int] = None

    def _init_schema(self):
        for stmt in SCHEMA_STATEMENTS:
            self.cursor.execute(stmt)
        self.conn.commit()

    def close(self):
        self.cursor.close()
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

    def _last_run_id(self) -> Optional[int]:
        self.cursor.execute("SELECT run_id FROM code_intel.ci_scan_runs ORDER BY run_id DESC LIMIT 1")
        row = self.cursor.fetchone()
        return row["run_id"] if row else None

    def _last_run_files(self, run_id: int) -> Dict[str, Tuple[str, int]]:
        self.cursor.execute(
            "SELECT file_path, file_hash, score FROM code_intel.ci_files WHERE run_id = %s",
            (run_id,)
        )
        return {r["file_path"]: (r["file_hash"], r["score"]) for r in self.cursor.fetchall()}

    def _grade_counts(self, scores: list) -> dict:
        counts = {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0, "f": 0}
        for s in scores:
            g = s.grade.lower()
            if g in counts:
                counts[g] += 1
        return counts

    def ingest_scores(self, scores: list, graph, root_folder: str) -> int:
        """Ingest a full scan into MySQL. Returns run_id."""
        total = len(scores)
        avg = sum(s.score for s in scores) / total if total else 0
        gc = self._grade_counts(scores)
        cycles = len(graph.cycles)
        unused = sum(len(s.metrics.unused_imports) for s in scores)
        god = sum(
            1 for s in scores
            for fm in s.metrics.function_metrics
            if "HIGH_COMPLEXITY" in fm.issues
        )
        empty = sum(len(s.metrics.empty_functions) for s in scores)
        parsed_ok = sum(1 for s in scores if not s.metrics.parse_error)
        parse_errors = total - parsed_ok

        self.cursor.execute(
            "INSERT INTO code_intel.ci_scan_runs "
            "(timestamp, root_folder, total_files, parsed_ok, parse_errors, avg_score, "
            "grade_a, grade_b, grade_c, grade_d, grade_e, grade_f, "
            "cycles, unused_imports, god_functions, empty_functions) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (time.time(), root_folder, total, parsed_ok, parse_errors, avg,
             gc["a"], gc["b"], gc["c"], gc["d"], gc["e"], gc["f"],
             cycles, unused, god, empty)
        )
        run_id = self.cursor.lastrowid
        self.current_run_id = run_id

        prev_run = self._last_run_id()
        prev_files = self._last_run_files(prev_run) if prev_run and prev_run != run_id else {}
        current_paths = set()

        for s in scores:
            fpath = s.metrics.file
            current_paths.add(fpath)
            fhash = self._file_hash(fpath, root_folder)
            bcl_tags_str = ",".join(s.metrics.bcl_tags)
            issues_str = ",".join(s.metrics.issues)

            mod_name = fpath
            if fpath.endswith(".py"):
                mod_name = fpath[:-3].replace(os.sep, ".")

            self.cursor.execute(
                "INSERT INTO code_intel.ci_files "
                "(run_id, file_path, module_name, lines, functions, classes, loops, ifs, "
                "max_depth, imports, score, grade, structure, complexity, hygiene, "
                "bcl, bcl_format, bcl_tags, file_hash, issues, parse_error) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (run_id, fpath, mod_name, s.metrics.lines, s.metrics.functions,
                 s.metrics.classes, s.metrics.loops, s.metrics.ifs, s.metrics.max_depth,
                 len(s.metrics.imports), s.score, s.grade, s.structure, s.complexity,
                 s.hygiene, s.bcl, s.metrics.bcl_format, bcl_tags_str, fhash,
                 issues_str, s.metrics.parse_error)
            )
            file_id = self.cursor.lastrowid

            for fm in s.metrics.function_metrics:
                is_method = fm.name.startswith("__") or "." in fm.name
                class_name = None
                if hasattr(fm, "class_name") and fm.class_name:
                    class_name = fm.class_name

                self.cursor.execute(
                    "INSERT INTO code_intel.ci_functions "
                    "(file_id, run_id, name, line, end_line, lines, args, branches, loops, "
                    "max_depth, complexity, issues, suggestions, is_method, class_name) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (file_id, run_id, fm.name, fm.line, fm.end_line, fm.lines, fm.args,
                     fm.branches, fm.loops, fm.max_depth, fm.complexity,
                     ",".join(fm.issues), "|".join(getattr(fm, "suggestions", [])),
                     1 if is_method else 0, class_name)
                )

            for edge_source in graph.edges:
                for edge_target in graph.edges[edge_source]:
                    self.cursor.execute(
                        "INSERT INTO code_intel.ci_dependencies (run_id, source, target) VALUES (%s, %s, %s)",
                        (run_id, edge_source, edge_target)
                    )

            prev_hash, prev_score = prev_files.get(fpath, ("", None))
            if prev_hash == "" and fhash != "":
                self._log_change(run_id, fpath, "ADDED", None, s.score)
            elif fhash != prev_hash and fhash != "" and prev_hash != "":
                self._log_change(run_id, fpath, "MODIFIED", prev_score, s.score)
            elif fhash == "" and prev_hash != "":
                self._log_change(run_id, fpath, "DELETED", prev_score, None)

        for old_path, (old_hash, old_score) in prev_files.items():
            if old_path not in current_paths:
                self._log_change(run_id, old_path, "DELETED", old_score, None)

        self.conn.commit()
        return run_id

    def _log_change(self, run_id: int, file_path: str, change_type: str,
                    old_score: Optional[int], new_score: Optional[int]):
        delta = None
        if old_score is not None and new_score is not None:
            delta = new_score - old_score
        self.cursor.execute(
            "INSERT INTO code_intel.ci_change_log "
            "(run_id, file_path, change_type, old_score, new_score, delta, timestamp) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (run_id, file_path, change_type, old_score, new_score, delta, time.time())
        )

    def cleanup_old_runs(self, keep: int = 5):
        """Delete scan runs older than the N most recent. Keeps DB from growing forever."""
        self.cursor.execute(
            "SELECT run_id FROM code_intel.ci_scan_runs ORDER BY run_id DESC LIMIT %s",
            (keep,)
        )
        keep_ids = [r["run_id"] for r in self.cursor.fetchall()]
        if not keep_ids:
            return
        placeholders = ",".join(["%s"] * len(keep_ids))

        self.cursor.execute(f"DELETE FROM code_intel.ci_functions WHERE run_id NOT IN ({placeholders})", keep_ids)
        self.cursor.execute(f"DELETE FROM code_intel.ci_classes WHERE run_id NOT IN ({placeholders})", keep_ids)
        self.cursor.execute(f"DELETE FROM code_intel.ci_dependencies WHERE run_id NOT IN ({placeholders})", keep_ids)
        self.cursor.execute(f"DELETE FROM code_intel.ci_change_log WHERE run_id NOT IN ({placeholders})", keep_ids)
        self.cursor.execute(f"DELETE FROM code_intel.ci_files WHERE run_id NOT IN ({placeholders})", keep_ids)
        self.cursor.execute(f"DELETE FROM code_intel.ci_scan_runs WHERE run_id NOT IN ({placeholders})", keep_ids)
        self.conn.commit()

    # -----------------------------------------------------------------------
    # QUERY API — same as SQLite but backed by MySQL
    # -----------------------------------------------------------------------

    def _run_id(self) -> int:
        return self.current_run_id or self._last_run_id()

    def query_god_functions(self, limit: int = 20) -> List[dict]:
        self.cursor.execute(
            "SELECT fu.name, fu.line, fu.lines, fu.complexity, fu.branches, fu.loops, "
            "fu.max_depth, fu.issues, fi.file_path, fi.module_name, fi.grade "
            "FROM code_intel.ci_functions fu "
            "JOIN code_intel.ci_files fi ON fu.file_id = fi.file_id "
            "WHERE fu.run_id = %s AND fu.complexity > 10 "
            "ORDER BY fu.complexity DESC LIMIT %s",
            (self._run_id(), limit)
        )
        return self.cursor.fetchall()

    def query_regressed_files(self) -> List[dict]:
        self.cursor.execute(
            "SELECT file_path, old_score, new_score, delta "
            "FROM code_intel.ci_change_log WHERE change_type = 'MODIFIED' AND delta < 0 "
            "ORDER BY delta ASC"
        )
        return self.cursor.fetchall()

    def query_improved_files(self) -> List[dict]:
        self.cursor.execute(
            "SELECT file_path, old_score, new_score, delta "
            "FROM code_intel.ci_change_log WHERE change_type = 'MODIFIED' AND delta > 0 "
            "ORDER BY delta DESC"
        )
        return self.cursor.fetchall()

    def query_new_files(self) -> List[dict]:
        self.cursor.execute(
            "SELECT file_path, new_score FROM code_intel.ci_change_log WHERE change_type = 'ADDED'"
        )
        return self.cursor.fetchall()

    def query_deleted_files(self) -> List[dict]:
        self.cursor.execute(
            "SELECT file_path, old_score FROM code_intel.ci_change_log WHERE change_type = 'DELETED'"
        )
        return self.cursor.fetchall()

    def query_file_detail(self, file_path: str) -> Optional[dict]:
        self.cursor.execute(
            "SELECT * FROM code_intel.ci_files WHERE file_path = %s AND run_id = %s",
            (file_path, self._run_id())
        )
        return self.cursor.fetchone()

    def query_functions_in_file(self, file_path: str) -> List[dict]:
        self.cursor.execute(
            "SELECT fu.* FROM code_intel.ci_functions fu "
            "JOIN code_intel.ci_files fi ON fu.file_id = fi.file_id "
            "WHERE fi.file_path = %s AND fi.run_id = %s ORDER BY fu.line",
            (file_path, self._run_id())
        )
        return self.cursor.fetchall()

    def query_dependents(self, module_name: str) -> List[str]:
        self.cursor.execute(
            "SELECT DISTINCT source FROM code_intel.ci_dependencies "
            "WHERE target = %s AND run_id = %s",
            (module_name, self._run_id())
        )
        return [r["source"] for r in self.cursor.fetchall()]

    def query_dependencies(self, module_name: str) -> List[str]:
        self.cursor.execute(
            "SELECT DISTINCT target FROM code_intel.ci_dependencies "
            "WHERE source = %s AND run_id = %s",
            (module_name, self._run_id())
        )
        return [r["target"] for r in self.cursor.fetchall()]

    def query_files_by_grade(self, grade: str) -> List[dict]:
        self.cursor.execute(
            "SELECT file_path, score, functions, classes, lines, bcl "
            "FROM code_intel.ci_files WHERE grade = %s AND run_id = %s ORDER BY score DESC",
            (grade.upper(), self._run_id())
        )
        return self.cursor.fetchall()

    def query_missing_bcl(self) -> List[dict]:
        self.cursor.execute(
            "SELECT file_path, score, bcl_format, bcl_tags, issues "
            "FROM code_intel.ci_files WHERE run_id = %s AND bcl < 10 AND parse_error IS NULL "
            "ORDER BY score DESC",
            (self._run_id(),)
        )
        return self.cursor.fetchall()

    def query_function_by_name(self, name: str) -> List[dict]:
        self.cursor.execute(
            "SELECT fu.name, fu.line, fu.lines, fu.complexity, fu.issues, "
            "fi.file_path, fi.module_name, fi.grade "
            "FROM code_intel.ci_functions fu "
            "JOIN code_intel.ci_files fi ON fu.file_id = fi.file_id "
            "WHERE fu.run_id = %s AND fu.name LIKE %s "
            "ORDER BY fu.complexity DESC",
            (self._run_id(), "%" + name + "%")
        )
        return self.cursor.fetchall()

    def query_scan_history(self, limit: int = 10) -> List[dict]:
        self.cursor.execute(
            "SELECT * FROM code_intel.ci_scan_runs ORDER BY run_id DESC LIMIT %s",
            (limit,)
        )
        return self.cursor.fetchall()

    def query_stats(self) -> dict:
        self.cursor.execute(
            "SELECT * FROM code_intel.ci_scan_runs WHERE run_id = %s",
            (self._run_id(),)
        )
        return self.cursor.fetchone() or {}

    def query_search(self, query: str) -> List[dict]:
        self.cursor.execute(
            "SELECT fi.file_path, fi.score, fi.grade, fu.name as func_name, "
            "fu.complexity, fu.line "
            "FROM code_intel.ci_files fi "
            "LEFT JOIN code_intel.ci_functions fu ON fi.file_id = fu.file_id "
            "WHERE fi.run_id = %s AND (fi.file_path LIKE %s OR fu.name LIKE %s) "
            "ORDER BY fi.score DESC",
            (self._run_id(), "%" + query + "%", "%" + query + "%")
        )
        return self.cursor.fetchall()

    def query_top_files(self, limit: int = 20) -> List[dict]:
        self.cursor.execute(
            "SELECT file_path, score, grade, functions, classes, lines, bcl "
            "FROM code_intel.ci_files WHERE run_id = %s ORDER BY score DESC LIMIT %s",
            (self._run_id(), limit)
        )
        return self.cursor.fetchall()

    def query_bottom_files(self, limit: int = 20) -> List[dict]:
        self.cursor.execute(
            "SELECT file_path, score, grade, functions, classes, lines, bcl "
            "FROM code_intel.ci_files WHERE run_id = %s ORDER BY score ASC LIMIT %s",
            (self._run_id(), limit)
        )
        return self.cursor.fetchall()

    def query_all_functions(self, limit: int = 500, offset: int = 0) -> List[dict]:
        """Iterate over ALL functions in the codebase. For bulk analysis."""
        self.cursor.execute(
            "SELECT fu.name, fu.line, fu.lines, fu.complexity, fu.branches, fu.loops, "
            "fu.max_depth, fu.args, fu.issues, fu.class_name, fu.is_method, "
            "fi.file_path, fi.module_name, fi.grade, fi.score "
            "FROM code_intel.ci_functions fu "
            "JOIN code_intel.ci_files fi ON fu.file_id = fi.file_id "
            "WHERE fu.run_id = %s "
            "ORDER BY fi.file_path, fu.line LIMIT %s OFFSET %s",
            (self._run_id(), limit, offset)
        )
        return self.cursor.fetchall()

    def query_all_classes(self) -> List[dict]:
        """All classes in the codebase."""
        self.cursor.execute(
            "SELECT cl.name, cl.line, cl.method_count, cl.bases, "
            "fi.file_path, fi.module_name, fi.grade "
            "FROM code_intel.ci_classes cl "
            "JOIN code_intel.ci_files fi ON cl.file_id = fi.file_id "
            "WHERE cl.run_id = %s ORDER BY fi.file_path, cl.line",
            (self._run_id(),)
        )
        return self.cursor.fetchall()

    def query_function_count(self) -> int:
        self.cursor.execute(
            "SELECT COUNT(*) as cnt FROM code_intel.ci_functions WHERE run_id = %s",
            (self._run_id(),)
        )
        row = self.cursor.fetchone()
        return row["cnt"] if row else 0

    def query_class_count(self) -> int:
        self.cursor.execute(
            "SELECT COUNT(*) as cnt FROM code_intel.ci_classes WHERE run_id = %s",
            (self._run_id(),)
        )
        row = self.cursor.fetchone()
        return row["cnt"] if row else 0

    def query_deep_nesting(self, threshold: int = 8) -> List[dict]:
        """All functions with nesting above threshold."""
        self.cursor.execute(
            "SELECT fu.name, fu.line, fu.max_depth, fu.complexity, "
            "fi.file_path, fi.module_name "
            "FROM code_intel.ci_functions fu "
            "JOIN code_intel.ci_files fi ON fu.file_id = fi.file_id "
            "WHERE fu.run_id = %s AND fu.max_depth > %s "
            "ORDER BY fu.max_depth DESC",
            (self._run_id(), threshold)
        )
        return self.cursor.fetchall()

    def query_long_functions(self, threshold: int = 50) -> List[dict]:
        """All functions longer than threshold lines."""
        self.cursor.execute(
            "SELECT fu.name, fu.line, fu.lines, fu.complexity, "
            "fi.file_path, fi.module_name "
            "FROM code_intel.ci_functions fu "
            "JOIN code_intel.ci_files fi ON fu.file_id = fi.file_id "
            "WHERE fu.run_id = %s AND fu.lines > %s "
            "ORDER BY fu.lines DESC",
            (self._run_id(), threshold)
        )
        return self.cursor.fetchall()

    def query_hotspot_files(self, limit: int = 20) -> List[dict]:
        """Files with most issues — the ones that need attention most."""
        self.cursor.execute(
            "SELECT file_path, score, grade, lines, functions, issues "
            "FROM code_intel.ci_files WHERE run_id = %s AND parse_error IS NULL "
            "ORDER BY (LENGTH(issues) - LENGTH(REPLACE(issues, ',', ''))) DESC "
            "LIMIT %s",
            (self._run_id(), limit)
        )
        return self.cursor.fetchall()
