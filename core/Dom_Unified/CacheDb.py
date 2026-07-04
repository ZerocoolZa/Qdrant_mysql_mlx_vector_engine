# [@GHOST]{[@file<CacheDb.py>][@domain<Dom_Unified>][@role<cache>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<cache>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{SQLite cache for parsed AST results. Avoids re-parsing unchanged files.}
# [@CLASS]{CacheDb}
# [@METHOD]{Run,Get,Put,Invalidate,GetStale,Stats}

"""
SQLite cache for Dom_Unified.

Stores parsed AST results so files don't get re-parsed every time.
Keyed by file_path + mtime — if file changes, cache entry is stale.

Tables:
    ast_cache:    file_path, mtime, classes_json, methods_json, edges_json, violations_json, parsed_at
    error_knowledge: id, file_path, rule, severity, message, line_num, captured_at, reuse_count
"""

import json
import os
import sqlite3
import time

from .Config import SQLITE_PATH, CACHE_TTL_SECONDS


class CacheDb:
    """SQLite cache for parsed AST results + error knowledge base."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"sqlite_path": SQLITE_PATH, "cache_ttl": CACHE_TTL_SECONDS},
            "stats": {"cache_hits": 0, "cache_misses": 0, "errors_captured": 0, "errors_reused": 0},
        }
        self.conn = None
        self._init_db()

    def Run(self, command, params=None):
        dispatch = {
            "get": self._cmd_get,
            "put": self._cmd_put,
            "invalidate": self._cmd_invalidate,
            "get_stale": self._cmd_get_stale,
            "stats": self._cmd_stats,
            "capture_error": self._cmd_capture_error,
            "query_errors": self._cmd_query_errors,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"Unknown: {command}", 0))
        return handler(params or {})

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, values):
        for key, val in values.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    # ════════════════════════════════════════════
    # INTERNAL
    # ════════════════════════════════════════════

    def _init_db(self):
        path = self.state["config"]["sqlite_path"]
        self.conn = sqlite3.connect(path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ast_cache (
                file_path     TEXT PRIMARY KEY,
                mtime         REAL NOT NULL,
                size          INTEGER NOT NULL,
                classes_json  TEXT,
                methods_json  TEXT,
                edges_json    TEXT,
                violations_json TEXT,
                summary_json  TEXT,
                parsed_at     REAL NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS error_knowledge (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path     TEXT,
                rule          TEXT,
                severity      TEXT,
                message       TEXT,
                line_num      INTEGER,
                captured_at   REAL NOT NULL,
                reuse_count   INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_error_rule ON error_knowledge(rule)
        """)
        self.conn.commit()

    def _file_mtime(self, file_path):
        try:
            st = os.stat(file_path)
            return (st.st_mtime, st.st_size)
        except OSError:
            return (0, 0)

    def _is_stale(self, file_path, cached_mtime, cached_size, parsed_at):
        mtime, size = self._file_mtime(file_path)
        if mtime != cached_mtime or size != cached_size:
            return True
        ttl = self.state["config"]["cache_ttl"]
        if ttl > 0 and (time.time() - parsed_at) > ttl:
            return True
        return False

    # ════════════════════════════════════════════
    # COMMANDS — CACHE
    # ════════════════════════════════════════════

    def _cmd_get(self, params):
        """Get cached parse result. Returns (1, data, None) if fresh, (0, None, ("STALE",..)) if stale."""
        file_path = params.get("file")
        if not file_path:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))

        row = self.conn.execute(
            "SELECT mtime, size, classes_json, methods_json, edges_json, violations_json, "
            "summary_json, parsed_at FROM ast_cache WHERE file_path = ?",
            (file_path,)
        ).fetchone()

        if not row:
            self.state["stats"]["cache_misses"] += 1
            return (0, None, ("MISS", "not in cache", 0))

        mtime, size, cj, mj, ej, vj, sj, parsed_at = row
        if self._is_stale(file_path, mtime, size, parsed_at):
            self.state["stats"]["cache_misses"] += 1
            return (0, None, ("STALE", "file changed or TTL expired", 0))

        self.state["stats"]["cache_hits"] += 1
        data = {
            "classes": json.loads(cj) if cj else [],
            "methods": json.loads(mj) if mj else [],
            "edges": json.loads(ej) if ej else [],
            "violations": json.loads(vj) if vj else [],
            "summary": json.loads(sj) if sj else {},
            "parsed_at": parsed_at,
        }
        return (1, data, None)

    def _cmd_put(self, params):
        """Store parse result in cache."""
        file_path = params.get("file")
        if not file_path:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        data = params.get("data", {})
        mtime, size = self._file_mtime(file_path)
        now = time.time()

        self.conn.execute("""
            INSERT OR REPLACE INTO ast_cache
                (file_path, mtime, size, classes_json, methods_json, edges_json,
                 violations_json, summary_json, parsed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_path, mtime, size,
            json.dumps(data.get("classes", [])),
            json.dumps(data.get("methods", [])),
            json.dumps(data.get("edges", [])),
            json.dumps(data.get("violations", [])),
            json.dumps(data.get("summary", {})),
            now
        ))
        self.conn.commit()
        return (1, {"cached": True, "file": file_path}, None)

    def _cmd_invalidate(self, params):
        """Remove a file from cache."""
        file_path = params.get("file")
        if not file_path:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        self.conn.execute("DELETE FROM ast_cache WHERE file_path = ?", (file_path,))
        self.conn.commit()
        return (1, {"invalidated": True, "file": file_path}, None)

    def _cmd_get_stale(self, params):
        """Find all stale cache entries."""
        rows = self.conn.execute(
            "SELECT file_path, mtime, size, parsed_at FROM ast_cache"
        ).fetchall()
        stale = []
        for file_path, mtime, size, parsed_at in rows:
            if self._is_stale(file_path, mtime, size, parsed_at):
                stale.append(file_path)
        return (1, stale, None)

    def _cmd_stats(self, params):
        return (1, dict(self.state["stats"]), None)

    # ════════════════════════════════════════════
    # COMMANDS — ERROR KNOWLEDGE
    # ════════════════════════════════════════════

    def _cmd_capture_error(self, params):
        """Capture a violation/error as reusable knowledge."""
        file_path = params.get("file", "")
        rule = params.get("rule", "")
        severity = params.get("severity", "error")
        message = params.get("message", "")
        line_num = params.get("line", 0)
        now = time.time()

        # Check if this exact error already exists
        existing = self.conn.execute(
            "SELECT id, reuse_count FROM error_knowledge WHERE rule = ? AND message = ? LIMIT 1",
            (rule, message)
        ).fetchone()

        if existing:
            # Increment reuse count — same error seen again
            self.conn.execute(
                "UPDATE error_knowledge SET reuse_count = reuse_count + 1 WHERE id = ?",
                (existing[0],)
            )
            self.state["stats"]["errors_reused"] += 1
        else:
            self.conn.execute("""
                INSERT INTO error_knowledge
                    (file_path, rule, severity, message, line_num, captured_at, reuse_count)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (file_path, rule, severity, message, line_num, now))
            self.state["stats"]["errors_captured"] += 1

        self.conn.commit()
        return (1, {"captured": True, "rule": rule}, None)

    def _cmd_query_errors(self, params):
        """Query error knowledge by rule or file."""
        rule = params.get("rule")
        file_path = params.get("file")
        limit = params.get("limit", 20)

        if rule:
            rows = self.conn.execute(
                "SELECT rule, severity, message, line_num, file_path, reuse_count "
                "FROM error_knowledge WHERE rule LIKE ? ORDER BY reuse_count DESC LIMIT ?",
                (f"%{rule}%", limit)
            ).fetchall()
        elif file_path:
            rows = self.conn.execute(
                "SELECT rule, severity, message, line_num, file_path, reuse_count "
                "FROM error_knowledge WHERE file_path = ? ORDER BY captured_at DESC LIMIT ?",
                (file_path, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT rule, severity, message, line_num, file_path, reuse_count "
                "FROM error_knowledge ORDER BY reuse_count DESC LIMIT ?",
                (limit,)
            ).fetchall()

        results = []
        for row in rows:
            results.append({
                "rule": row[0], "severity": row[1], "message": row[2],
                "line": row[3], "file": row[4], "reuse_count": row[5],
            })
        return (1, results, None)
