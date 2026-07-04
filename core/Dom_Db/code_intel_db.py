#!/usr/bin/env python3
"""
Code Intelligence Database — persistent SQLite store for AST code structures.

Stores every file, class, function, dependency, and score across scans.
Tracks changes (new/modified/deleted) between runs. Queryable knowledge base.

Schema:
  scan_runs     — one row per scan execution
  files         — per-file metrics + scores + BCL info
  functions     — per-function metrics + complexity + issues
  classes       — per-class registry
  dependencies  — import edges between modules
  change_log    — file added/modified/deleted between runs

Usage:
    from code_intel_db import CodeIntelDB
    db = CodeIntelDB("/tmp/code_intel.sqlite")
    db.ingest_scores(scores, graph, root_folder)
    db.query_god_functions()
    db.query_regressed_files()
"""

import sqlite3
import time
import hashlib
import os
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scan_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL NOT NULL,
    root_folder TEXT NOT NULL,
    total_files INTEGER NOT NULL,
    avg_score   REAL NOT NULL,
    grade_a     INTEGER NOT NULL,
    cycles      INTEGER NOT NULL,
    unused_imports INTEGER NOT NULL,
    god_functions  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    file_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL,
    file_path   TEXT NOT NULL,
    module_name TEXT NOT NULL,
    lines       INTEGER NOT NULL,
    functions   INTEGER NOT NULL,
    classes     INTEGER NOT NULL,
    loops       INTEGER NOT NULL,
    ifs         INTEGER NOT NULL,
    max_depth   INTEGER NOT NULL,
    imports     INTEGER NOT NULL,
    score       INTEGER NOT NULL,
    grade       TEXT NOT NULL,
    structure   INTEGER NOT NULL,
    complexity  INTEGER NOT NULL,
    hygiene     INTEGER NOT NULL,
    bcl         INTEGER NOT NULL,
    bcl_format  TEXT NOT NULL,
    bcl_tags    TEXT NOT NULL,
    file_hash   TEXT NOT NULL,
    issues      TEXT NOT NULL,
    parse_error TEXT,
    FOREIGN KEY (run_id) REFERENCES scan_runs(run_id)
);

CREATE TABLE IF NOT EXISTS functions (
    func_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL,
    name        TEXT NOT NULL,
    line        INTEGER NOT NULL,
    end_line    INTEGER NOT NULL,
    lines       INTEGER NOT NULL,
    args        INTEGER NOT NULL,
    branches    INTEGER NOT NULL,
    loops       INTEGER NOT NULL,
    max_depth   INTEGER NOT NULL,
    complexity  INTEGER NOT NULL,
    issues      TEXT NOT NULL,
    suggestions TEXT NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);

CREATE TABLE IF NOT EXISTS classes (
    class_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL,
    name        TEXT NOT NULL,
    line        INTEGER NOT NULL,
    method_count INTEGER NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);

CREATE TABLE IF NOT EXISTS dependencies (
    dep_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL,
    source      TEXT NOT NULL,
    target      TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES scan_runs(run_id)
);

CREATE TABLE IF NOT EXISTS change_log (
    change_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL,
    file_path   TEXT NOT NULL,
    change_type TEXT NOT NULL,
    old_score   INTEGER,
    new_score   INTEGER,
    delta       INTEGER,
    timestamp   REAL NOT NULL,
    FOREIGN KEY (run_id) REFERENCES scan_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_files_run ON files(run_id);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path, run_id);
CREATE INDEX IF NOT EXISTS idx_funcs_file ON functions(file_id);
CREATE INDEX IF NOT EXISTS idx_funcs_name ON functions(name);
CREATE INDEX IF NOT EXISTS idx_deps_source ON dependencies(source);
CREATE INDEX IF NOT EXISTS idx_deps_target ON dependencies(target);
CREATE INDEX IF NOT EXISTS idx_changes_run ON change_log(run_id);
CREATE INDEX IF NOT EXISTS idx_changes_file ON change_log(file_path);
"""


class CodeIntelDB:

    def __init__(self, db_path: str = "/tmp/code_intel.sqlite"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
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

    def _last_run_id(self) -> Optional[int]:
        row = self.conn.execute(
            "SELECT run_id FROM scan_runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        return row["run_id"] if row else None

    def _last_run_files(self, run_id: int) -> Dict[str, Tuple[str, int]]:
        """Return {file_path: (file_hash, score)} from previous run."""
        rows = self.conn.execute(
            "SELECT file_path, file_hash, score FROM files WHERE run_id = ?",
            (run_id,)
        ).fetchall()
        return {r["file_path"]: (r["file_hash"], r["score"]) for r in rows}

    def ingest_scores(self, scores: list, graph, root_folder: str) -> int:
        """Ingest a full scan's results into the database.

        Returns the run_id.
        """
        total = len(scores)
        avg = sum(s.score for s in scores) / total if total else 0
        grade_a = sum(1 for s in scores if s.grade == "A")
        cycles = len(graph.cycles)
        unused = sum(len(s.metrics.unused_imports) for s in scores)
        god = sum(
            1 for s in scores
            for fm in s.metrics.function_metrics
            if "HIGH_COMPLEXITY" in fm.issues
        )

        cursor = self.conn.execute(
            "INSERT INTO scan_runs (timestamp, root_folder, total_files, avg_score, grade_a, cycles, unused_imports, god_functions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), root_folder, total, avg, grade_a, cycles, unused, god)
        )
        run_id = cursor.lastrowid
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

            cursor = self.conn.execute(
                "INSERT INTO files (run_id, file_path, module_name, lines, functions, classes, "
                "loops, ifs, max_depth, imports, score, grade, structure, complexity, hygiene, "
                "bcl, bcl_format, bcl_tags, file_hash, issues, parse_error) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, fpath, mod_name, s.metrics.lines, s.metrics.functions,
                 s.metrics.classes, s.metrics.loops, s.metrics.ifs, s.metrics.max_depth,
                 len(s.metrics.imports), s.score, s.grade, s.structure, s.complexity,
                 s.hygiene, s.bcl, s.metrics.bcl_format, bcl_tags_str, fhash,
                 issues_str, s.metrics.parse_error)
            )
            file_id = cursor.lastrowid

            for fm in s.metrics.function_metrics:
                self.conn.execute(
                    "INSERT INTO functions (file_id, name, line, end_line, lines, args, "
                    "branches, loops, max_depth, complexity, issues, suggestions) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (file_id, fm.name, fm.line, fm.end_line, fm.lines, fm.args,
                     fm.branches, fm.loops, fm.max_depth, fm.complexity,
                     ",".join(fm.issues), "|".join(fm.suggestions))
                )

            for edge_source in graph.edges:
                for edge_target in graph.edges[edge_source]:
                    self.conn.execute(
                        "INSERT INTO dependencies (run_id, source, target) VALUES (?, ?, ?)",
                        (run_id, edge_source, edge_target)
                    )

            prev_hash, prev_score = prev_files.get(fpath, ("", None))
            if prev_hash == "" and fhash != "":
                self._log_change(run_id, fpath, "ADDED", None, s.score)
            elif fhash != prev_hash and fhash != "" and prev_hash != "":
                self._log_change(run_id, fpath, "MODIFIED", prev_score, s.score)
            elif fhash != prev_hash and fhash == "" and prev_hash != "":
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
        self.conn.execute(
            "INSERT INTO change_log (run_id, file_path, change_type, old_score, new_score, delta, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, file_path, change_type, old_score, new_score, delta, time.time())
        )

    # -----------------------------------------------------------------------
    # QUERY API
    # -----------------------------------------------------------------------

    def query_god_functions(self, limit: int = 20) -> List[dict]:
        """Return the highest-complexity functions across all runs."""
        rows = self.conn.execute(
            "SELECT f.name, f.line, f.lines, f.complexity, f.branches, f.loops, "
            "f.max_depth, f.issues, fi.file_path, fi.module_name "
            "FROM functions f JOIN files fi ON f.file_id = fi.file_id "
            "WHERE fi.run_id = ? AND f.complexity > 10 "
            "ORDER BY f.complexity DESC LIMIT ?",
            (self.current_run_id or self._last_run_id(), limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_regressed_files(self) -> List[dict]:
        """Files whose score dropped since last run."""
        rows = self.conn.execute(
            "SELECT file_path, old_score, new_score, delta "
            "FROM change_log WHERE change_type = 'MODIFIED' AND delta < 0 "
            "ORDER BY delta ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def query_improved_files(self) -> List[dict]:
        """Files whose score improved since last run."""
        rows = self.conn.execute(
            "SELECT file_path, old_score, new_score, delta "
            "FROM change_log WHERE change_type = 'MODIFIED' AND delta > 0 "
            "ORDER BY delta DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def query_new_files(self) -> List[dict]:
        """Files added since last run."""
        rows = self.conn.execute(
            "SELECT file_path, new_score FROM change_log WHERE change_type = 'ADDED'"
        ).fetchall()
        return [dict(r) for r in rows]

    def query_deleted_files(self) -> List[dict]:
        """Files deleted since last run."""
        rows = self.conn.execute(
            "SELECT file_path, old_score FROM change_log WHERE change_type = 'DELETED'"
        ).fetchall()
        return [dict(r) for r in rows]

    def query_file_detail(self, file_path: str) -> Optional[dict]:
        """Get full detail for a specific file."""
        run_id = self.current_run_id or self._last_run_id()
        row = self.conn.execute(
            "SELECT * FROM files WHERE file_path = ? AND run_id = ?",
            (file_path, run_id)
        ).fetchone()
        return dict(row) if row else None

    def query_functions_in_file(self, file_path: str) -> List[dict]:
        """Get all functions for a specific file."""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT fu.* FROM functions fu JOIN files fi ON fu.file_id = fi.file_id "
            "WHERE fi.file_path = ? AND fi.run_id = ? ORDER BY fu.line",
            (file_path, run_id)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_dependents(self, module_name: str) -> List[str]:
        """Who imports this module?"""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT DISTINCT source FROM dependencies WHERE target = ? AND run_id = ?",
            (module_name, run_id)
        ).fetchall()
        return [r["source"] for r in rows]

    def query_dependencies(self, module_name: str) -> List[str]:
        """What does this module import?"""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT DISTINCT target FROM dependencies WHERE source = ? AND run_id = ?",
            (module_name, run_id)
        ).fetchall()
        return [r["target"] for r in rows]

    def query_files_by_grade(self, grade: str) -> List[dict]:
        """All files with a specific grade."""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT file_path, score, functions, classes, lines "
            "FROM files WHERE grade = ? AND run_id = ? ORDER BY score DESC",
            (grade, run_id)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_missing_bcl(self) -> List[dict]:
        """Files missing required BCL tags."""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT file_path, score, bcl_format, bcl_tags, issues "
            "FROM files WHERE run_id = ? AND bcl < 10 AND parse_error IS NULL "
            "ORDER BY score DESC",
            (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_unused_imports_summary(self) -> List[dict]:
        """Files with unused imports."""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT file_path, issues FROM files WHERE run_id = ? AND issues LIKE '%UNUSED_IMPORT%'",
            (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_function_by_name(self, name: str) -> List[dict]:
        """Find all functions with a given name across the codebase."""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT fu.name, fu.line, fu.lines, fu.complexity, fu.issues, "
            "fi.file_path, fi.module_name "
            "FROM functions fu JOIN files fi ON fu.file_id = fi.file_id "
            "WHERE fi.run_id = ? AND fu.name LIKE ? "
            "ORDER BY fu.complexity DESC",
            (run_id, "%" + name + "%")
        ).fetchall()
        return [dict(r) for r in rows]

    def query_scan_history(self, limit: int = 10) -> List[dict]:
        """Recent scan runs."""
        rows = self.conn.execute(
            "SELECT * FROM scan_runs ORDER BY run_id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_stats(self) -> dict:
        """Overall codebase statistics for latest run."""
        run_id = self.current_run_id or self._last_run_id()
        row = self.conn.execute(
            "SELECT total_files, avg_score, grade_a, cycles, unused_imports, god_functions "
            "FROM scan_runs WHERE run_id = ?",
            (run_id,)
        ).fetchone()
        return dict(row) if row else {}

    def query_search(self, query: str) -> List[dict]:
        """Full-text search across file paths and function names."""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT fi.file_path, fi.score, fi.grade, fu.name as func_name, "
            "fu.complexity, fu.line "
            "FROM files fi LEFT JOIN functions fu ON fi.file_id = fu.file_id "
            "WHERE fi.run_id = ? AND (fi.file_path LIKE ? OR fu.name LIKE ?) "
            "ORDER BY fi.score DESC",
            (run_id, "%" + query + "%", "%" + query + "%")
        ).fetchall()
        return [dict(r) for r in rows]

    def query_top_files(self, limit: int = 20) -> List[dict]:
        """Top-ranked files."""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT file_path, score, grade, functions, classes, lines, bcl "
            "FROM files WHERE run_id = ? ORDER BY score DESC LIMIT ?",
            (run_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def query_bottom_files(self, limit: int = 20) -> List[dict]:
        """Worst-ranked files."""
        run_id = self.current_run_id or self._last_run_id()
        rows = self.conn.execute(
            "SELECT file_path, score, grade, functions, classes, lines, bcl "
            "FROM files WHERE run_id = ? ORDER BY score ASC LIMIT ?",
            (run_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]
