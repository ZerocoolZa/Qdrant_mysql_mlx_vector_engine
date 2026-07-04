#!/usr/bin/env python3
"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/StampEngine.py";"identity=StampEngine";"purpose=Stage 3a: Surface stamp every METHOD unit in code_graph.db. Extract purpose, side_effects, callers, confidence. Store in stamps table.";"date=2026-06-27";"version=1.0";"author=Devin";"chat_link=sqlite://code_graph.db/stamps")}
#[@VBSTYLE]{("auth=Devin";"role=tool";"return=Tuple3";"orch=none";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete")}
#[@FILEID]{("session_id=code-graph-pipeline";"context=Code Graph Pipeline Stage 3a";"purpose=Surface stamp extraction for all METHOD units")}
#[@SUMMARY]{("Stage 3a of the code graph pipeline. For every METHOD unit in code_units, extracts a surface stamp: purpose (from docstring or BCL header), side_effects (SQL writes, file writes, state mutations), callers (from called_by), confidence (0.5 default). Stores stamps in BCL-native [@Stamp]{} format in the stamps table. No AI reasoning — pure extraction.")}
"""
import ast
import os
import re
import sqlite3
import sys
import hashlib
import argparse
from datetime import datetime, timezone


DB_PATH = "code_graph.db"

STAMP_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stamps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    stamp_text TEXT NOT NULL,
    stamp_tier TEXT NOT NULL DEFAULT 'SURFACE',
    purpose TEXT,
    side_effects TEXT,
    callers TEXT,
    confidence REAL DEFAULT 0.5,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    superseded_by INTEGER,
    FOREIGN KEY (unit_id) REFERENCES code_units(id)
);
CREATE INDEX IF NOT EXISTS idx_stamps_unit ON stamps(unit_id);
CREATE INDEX IF NOT EXISTS idx_stamps_hash ON stamps(content_hash);
CREATE INDEX IF NOT EXISTS idx_stamps_tier ON stamps(stamp_tier);
CREATE INDEX IF NOT EXISTS idx_stamps_active ON stamps(unit_id) WHERE superseded_by IS NULL;
"""


class StampEngine:
    """Stage 3a: Surface stamp extraction for all METHOD units."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": DB_PATH,
            },
            "stamped": 0,
            "skipped": 0,
            "errors": 0,
            "conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "stamp_all":
            return self.StampAll(params)
        elif command == "stamp_unit":
            return self.StampUnit(params)
        elif command == "query_stamps":
            return self.QueryStamps(params)
        elif command == "query_unstamped":
            return self.QueryUnstamped(params)
        elif command == "stats":
            return self.Stats(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def _connect(self):
        if self.state["conn"] is None:
            db_path = self.state["config"]["db_path"]
            if not os.path.isfile(db_path):
                return (0, None, ("DB_NOT_FOUND", "Database not found: " + db_path, 0))
            self.state["conn"] = sqlite3.connect(db_path)
            self.state["conn"].row_factory = sqlite3.Row
        return self.state["conn"]

    def _init_schema(self):
        conn = self._connect()
        if isinstance(conn, tuple):
            return conn
        conn.executescript(STAMP_SCHEMA_SQL)
        conn.commit()
        return conn

    def _extract_purpose(self, source_text, docstring):
        """Extract a one-sentence purpose from docstring or BCL header."""
        if docstring:
            first_line = docstring.strip().split("\n")[0].strip()
            if first_line:
                return first_line[:200]
        if source_text:
            bcl_match = re.search(r'\[@SUMMARY\]\{[^}]*"purpose=([^"]+)"', source_text)
            if bcl_match:
                return bcl_match.group(1)[:200]
            bcl_match = re.search(r'\[@SUMMARY\]\{[^}]*summary="([^"]+)"', source_text)
            if bcl_match:
                return bcl_match.group(1)[:200]
            comment_match = re.search(r'#\s*(.*)', source_text.split("\n")[0])
            if comment_match:
                return comment_match.group(1).strip()[:200]
        return ""

    def _extract_side_effects(self, source_text):
        """Detect SQL writes, file writes, state mutations."""
        effects = []
        if not source_text:
            return ""
        text = source_text.lower()
        if any(kw in text for kw in ["insert into", "update ", "delete from", ".execute("]):
            if any(kw in text for kw in ["insert", "update", "delete"]):
                effects.append("SQL_WRITE")
        if any(kw in text for kw in ["open(", "write(", "writelines(", ".write_text"]):
            effects.append("FILE_WRITE")
        if any(kw in text for kw in ["self.state[", "self.state."]):
            if "=" in source_text and "self.state[" in text:
                effects.append("STATE_MUTATION")
        if "subprocess" in text or "os.system" in text:
            effects.append("SUBPROCESS")
        if "commit()" in text:
            effects.append("DB_COMMIT")
        if "cursor.close()" in text or "conn.close()" in text:
            effects.append("DB_CLOSE")
        if ".connect(" in text:
            effects.append("DB_CONNECT")
        if "return (1," in source_text and "return (0," in source_text:
            effects.append("TUPLE3_DISPATCH")
        return ",".join(effects)

    def _extract_callers(self, called_by):
        """Extract caller list from called_by field."""
        if not called_by:
            return ""
        return called_by.strip()

    def _compute_confidence(self, purpose, side_effects, callers, source_text):
        """Compute confidence based on available information."""
        confidence = 0.3
        if purpose:
            confidence += 0.1
        if side_effects:
            confidence += 0.1
        if callers:
            confidence += 0.05
        if source_text and len(source_text) > 50:
            confidence += 0.05
        if min(confidence, 0.5) < 0.5:
            return round(confidence, 2)
        return 0.5

    def _build_stamp_text(self, unit, purpose, side_effects, callers, confidence):
        """Build BCL-native [@Stamp]{...} format."""
        stamp = (
            "[@Stamp]{"
            "\"unit_id=" + str(unit["id"]) + "\""
            " \"class=" + str(unit["class_name"] or "") + "\""
            " \"method=" + str(unit["method_name"] or "") + "\""
            " \"purpose=" + (purpose or "unknown") + "\""
            " \"side_effects=" + (side_effects or "none") + "\""
            " \"callers=" + (callers or "none") + "\""
            " \"confidence=" + str(confidence) + "\""
            " \"tier=SURFACE\""
            "}"
        )
        return stamp

    def StampAll(self, params):
        conn = self._init_schema()
        if isinstance(conn, tuple):
            return conn
        cur = conn.cursor()
        cur.execute(
            "SELECT id, file_path, class_name, method_name, source_text, "
            "docstring, calls, called_by, content_hash, is_vbstyle "
            "FROM code_units WHERE unit_type='METHOD'"
        )
        methods = cur.fetchall()
        stamped = 0
        skipped = 0
        errors = 0
        for row in methods:
            unit = dict(row)
            content_hash = unit["content_hash"] or ""
            if not content_hash:
                source = unit["source_text"] or ""
                content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
            cur.execute(
                "SELECT id FROM stamps WHERE unit_id=? AND content_hash=? "
                "AND superseded_by IS NULL",
                (unit["id"], content_hash)
            )
            existing = cur.fetchone()
            if existing:
                skipped += 1
                continue
            purpose = self._extract_purpose(unit["source_text"], unit["docstring"])
            side_effects = self._extract_side_effects(unit["source_text"])
            callers = self._extract_callers(unit["called_by"])
            confidence = self._compute_confidence(
                purpose, side_effects, callers, unit["source_text"]
            )
            stamp_text = self._build_stamp_text(
                unit, purpose, side_effects, callers, confidence
            )
            try:
                cur.execute(
                    "INSERT INTO stamps "
                    "(unit_id, content_hash, stamp_text, stamp_tier, "
                    "purpose, side_effects, callers, confidence) "
                    "VALUES (?, ?, ?, 'SURFACE', ?, ?, ?, ?)",
                    (unit["id"], content_hash, stamp_text,
                     purpose, side_effects, callers, confidence)
                )
                stamped += 1
            except sqlite3.Error:
                errors += 1
        conn.commit()
        self.state["stamped"] = stamped
        self.state["skipped"] = skipped
        self.state["errors"] = errors
        result = {
            "stamped": stamped,
            "skipped": skipped,
            "errors": errors,
            "total_methods": len(methods),
        }
        return (1, result, None)

    def StampUnit(self, params):
        unit_id = self._p(params, "unit_id")
        if not unit_id:
            return (0, None, ("MISSING_PARAM", "unit_id is required", 0))
        conn = self._init_schema()
        if isinstance(conn, tuple):
            return conn
        cur = conn.cursor()
        cur.execute(
            "SELECT id, file_path, class_name, method_name, source_text, "
            "docstring, calls, called_by, content_hash, is_vbstyle "
            "FROM code_units WHERE id=? AND unit_type='METHOD'",
            (unit_id,)
        )
        row = cur.fetchone()
        if not row:
            return (0, None, ("UNIT_NOT_FOUND", "No METHOD unit with id=" + str(unit_id), 0))
        unit = dict(row)
        content_hash = unit["content_hash"] or hashlib.sha256(
            (unit["source_text"] or "").encode("utf-8")).hexdigest()
        purpose = self._extract_purpose(unit["source_text"], unit["docstring"])
        side_effects = self._extract_side_effects(unit["source_text"])
        callers = self._extract_callers(unit["called_by"])
        confidence = self._compute_confidence(
            purpose, side_effects, callers, unit["source_text"]
        )
        stamp_text = self._build_stamp_text(
            unit, purpose, side_effects, callers, confidence
        )
        cur.execute(
            "UPDATE stamps SET superseded_by=NULL WHERE unit_id=? AND superseded_by IS NULL",
            (unit_id,)
        )
        cur.execute(
            "INSERT INTO stamps "
            "(unit_id, content_hash, stamp_text, stamp_tier, "
            "purpose, side_effects, callers, confidence) "
            "VALUES (?, ?, ?, 'SURFACE', ?, ?, ?, ?)",
            (unit["id"], content_hash, stamp_text,
             purpose, side_effects, callers, confidence)
        )
        stamp_id = cur.lastrowid
        conn.commit()
        result = {
            "stamp_id": stamp_id,
            "unit_id": unit_id,
            "purpose": purpose,
            "side_effects": side_effects,
            "callers": callers,
            "confidence": confidence,
            "stamp_text": stamp_text,
        }
        return (1, result, None)

    def QueryStamps(self, params):
        class_name = self._p(params, "class_name")
        method_name = self._p(params, "method_name")
        tier = self._p(params, "tier", "SURFACE")
        conn = self._connect()
        if isinstance(conn, tuple):
            return conn
        cur = conn.cursor()
        sql = (
            "SELECT s.id, s.unit_id, s.stamp_text, s.purpose, s.side_effects, "
            "s.callers, s.confidence, s.created_at, "
            "u.class_name, u.method_name, u.file_path "
            "FROM stamps s JOIN code_units u ON s.unit_id=u.id "
            "WHERE s.superseded_by IS NULL AND s.stamp_tier=?"
        )
        args = [tier]
        if class_name:
            sql += " AND u.class_name=?"
            args.append(class_name)
        if method_name:
            sql += " AND u.method_name=?"
            args.append(method_name)
        sql += " ORDER BY u.class_name, u.method_name"
        cur.execute(sql, args)
        rows = cur.fetchall()
        stamps = []
        for row in rows:
            stamps.append(dict(row))
        return (1, {"stamps": stamps, "count": len(stamps)}, None)

    def QueryUnstamped(self, params):
        conn = self._connect()
        if isinstance(conn, tuple):
            return conn
        cur = conn.cursor()
        cur.execute(
            "SELECT u.id, u.class_name, u.method_name, u.file_path "
            "FROM code_units u "
            "WHERE u.unit_type='METHOD' AND u.id NOT IN "
            "(SELECT unit_id FROM stamps WHERE superseded_by IS NULL) "
            "ORDER BY u.class_name, u.method_name"
        )
        rows = cur.fetchall()
        unstamped = []
        for row in rows:
            unstamped.append(dict(row))
        return (1, {"unstamped": unstamped, "count": len(unstamped)}, None)

    def Stats(self, params):
        conn = self._connect()
        if isinstance(conn, tuple):
            return conn
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM code_units WHERE unit_type='METHOD'")
        total_methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM stamps WHERE superseded_by IS NULL")
        total_stamps = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM code_units WHERE unit_type='METHOD' "
            "AND id NOT IN (SELECT unit_id FROM stamps WHERE superseded_by IS NULL)"
        )
        unstamped = cur.fetchone()[0]
        cur.execute("SELECT AVG(confidence) FROM stamps WHERE superseded_by IS NULL")
        avg_conf = cur.fetchone()[0] or 0.0
        cur.execute(
            "SELECT side_effects, COUNT(*) as cnt FROM stamps "
            "WHERE superseded_by IS NULL GROUP BY side_effects "
            "ORDER BY cnt DESC LIMIT 10"
        )
        effect_dist = []
        for row in cur.fetchall():
            effect_dist.append({"side_effects": row[0], "count": row[1]})
        result = {
            "total_methods": total_methods,
            "total_stamps": total_stamps,
            "unstamped": unstamped,
            "coverage_pct": round((total_stamps / total_methods * 100), 2) if total_methods else 0,
            "avg_confidence": round(avg_conf, 3),
            "effect_distribution": effect_dist,
        }
        return (1, result, None)


def main():
    parser = argparse.ArgumentParser(description="StampEngine — Stage 3a surface stamping")
    parser.add_argument("--db", default=DB_PATH, help="Path to code_graph.db")
    parser.add_argument("--stamp-all", action="store_true", help="Stamp all METHOD units")
    parser.add_argument("--stats", action="store_true", help="Show stamp statistics")
    parser.add_argument("--unstamped", action="store_true", help="List unstamped methods")
    parser.add_argument("--query", nargs="*", metavar="KEY=VALUE",
                        help="Query stamps (class_name=X method_name=Y tier=SURFACE)")
    args = parser.parse_args()

    engine = StampEngine(param={"db_path": args.db})

    if args.stamp_all:
        result = engine.Run("stamp_all")
        if result[0] == 1:
            data = result[1]
            print("STAMPING COMPLETE:")
            print("  Stamped:  " + str(data["stamped"]))
            print("  Skipped:  " + str(data["skipped"]) + " (already had current stamp)")
            print("  Errors:   " + str(data["errors"]))
            print("  Total methods: " + str(data["total_methods"]))
        else:
            print("ERROR: " + str(result[2]))
        return

    if args.stats:
        result = engine.Run("stats")
        if result[0] == 1:
            data = result[1]
            print("STAMP STATISTICS:")
            print("  Total methods:  " + str(data["total_methods"]))
            print("  Total stamps:   " + str(data["total_stamps"]))
            print("  Unstamped:      " + str(data["unstamped"]))
            print("  Coverage:       " + str(data["coverage_pct"]) + "%")
            print("  Avg confidence: " + str(data["avg_confidence"]))
            print("\n  Side effect distribution:")
            for item in data["effect_distribution"]:
                print("    " + str(item["side_effects"] or "(none)") + ": " + str(item["count"]))
        else:
            print("ERROR: " + str(result[2]))
        return

    if args.unstamped:
        result = engine.Run("query_unstamped")
        if result[0] == 1:
            data = result[1]
            print("UNSTAMPED METHODS: " + str(data["count"]))
            for item in data["unstamped"][:50]:
                print("  " + str(item["class_name"]) + "." + str(item["method_name"]) + " (" + str(item["file_path"]) + ")")
            if data["count"] > 50:
                print("  ... and " + str(data["count"] - 50) + " more")
        else:
            print("ERROR: " + str(result[2]))
        return

    if args.query:
        params = {}
        for arg in args.query:
            if "=" in arg:
                key, value = arg.split("=", 1)
                params[key] = value
        result = engine.Run("query_stamps", params)
        if result[0] == 1:
            data = result[1]
            print("STAMPS: " + str(data["count"]))
            for item in data["stamps"][:50]:
                print("  [" + str(item["id"]) + "] " + str(item["class_name"]) + "." + str(item["method_name"]))
                print("      purpose: " + str(item["purpose"] or "(none)"))
                print("      effects: " + str(item["side_effects"] or "(none)"))
                print("      callers: " + str(item["callers"] or "(none)"))
                print("      confidence: " + str(item["confidence"]))
        else:
            print("ERROR: " + str(result[2]))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
