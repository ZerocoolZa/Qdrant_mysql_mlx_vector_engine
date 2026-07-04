#!/usr/bin/env python3
"""
Methods-only store. One table. Zero noise.

  ci_methods
    - def_id        PK
    - name          method name
    - class_name    owning class
    - qualname      Class.method
    - cyclomatic    complexity
    - max_nesting   deepest nesting
    - body_lines    lines of code
    - arg_count     number of args
    - arg_names     arg names (comma string)
    - returns       return annotation
    - call_count    how many calls inside
    - call_names    what it calls (comma string)
    - recursive     calls itself
    - decorators    decorator names
    - has_docstring has a docstring
    - docstring     the docstring text
    - is_empty      empty body

That's it. 17 columns. Pure signal.

Usage:
    from methods_store import MethodsStore
    store = MethodsStore()
    store.ingest_from_v2("/tmp/ast_definitions_v2.sqlite")
    rows = store.all_methods()
"""

import sqlite3
import os
from typing import List, Dict, Optional

from SuperConfig import DB


SCHEMA = """
CREATE TABLE IF NOT EXISTS ci_methods (
    def_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    class_name    TEXT NOT NULL,
    qualname      TEXT NOT NULL,
    cyclomatic    INTEGER NOT NULL DEFAULT 0,
    max_nesting   INTEGER NOT NULL DEFAULT 0,
    body_lines    INTEGER NOT NULL DEFAULT 0,
    arg_count     INTEGER NOT NULL DEFAULT 0,
    arg_names     TEXT,
    returns       TEXT,
    call_count    INTEGER NOT NULL DEFAULT 0,
    call_names    TEXT,
    recursive     INTEGER NOT NULL DEFAULT 0,
    decorators    TEXT,
    has_docstring INTEGER NOT NULL DEFAULT 0,
    docstring     TEXT,
    is_empty      INTEGER NOT NULL DEFAULT 0,
    source_code   TEXT,
    ast_hash      TEXT
);

CREATE INDEX IF NOT EXISTS idx_m_name       ON ci_methods(name);
CREATE INDEX IF NOT EXISTS idx_m_class      ON ci_methods(class_name);
CREATE INDEX IF NOT EXISTS idx_m_qualname   ON ci_methods(qualname);
CREATE INDEX IF NOT EXISTS idx_m_cx         ON ci_methods(cyclomatic);
CREATE INDEX IF NOT EXISTS idx_m_calls      ON ci_methods(call_count);
CREATE INDEX IF NOT EXISTS idx_m_asthash    ON ci_methods(ast_hash);
"""


class MethodsStore:

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = DB.METHODS_DB
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def ingest_from_v2(self, v2_path: str = None):
        """Pull only methods from v2 normalized DB into clean one-table store."""
        if v2_path is None:
            v2_path = DB.AST_DEFINITIONS_V2_DB
        src = sqlite3.connect(v2_path)
        src.row_factory = sqlite3.Row
        s = src.cursor()

        s.execute("""
            SELECT d.name, d.qualname, d.cyclomatic, d.max_nesting, d.body_lines,
                   d.arg_count, d.arg_names, d.returns_annotation, d.call_count,
                   d.call_names, d.recursive, d.decorator_names, d.has_docstring,
                   d.docstring, d.is_empty, c.name as class_name,
                   d.source_code, d.ast_hash
            FROM ci_definitions d
            LEFT JOIN ci_classes c ON d.class_id = c.class_id
            WHERE d.kind = 'method'
            ORDER BY c.name, d.line_start
        """)
        rows = s.fetchall()

        for r in rows:
            self.conn.execute(
                "INSERT INTO ci_methods "
                "(name, class_name, qualname, cyclomatic, max_nesting, body_lines, "
                "arg_count, arg_names, returns, call_count, call_names, recursive, "
                "decorators, has_docstring, docstring, is_empty, source_code, ast_hash) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["name"], r["class_name"], r["qualname"],
                 r["cyclomatic"], r["max_nesting"], r["body_lines"],
                 r["arg_count"], r["arg_names"], r["returns_annotation"],
                 r["call_count"], r["call_names"], r["recursive"],
                 r["decorator_names"], r["has_docstring"],
                 r["docstring"], r["is_empty"],
                 r["source_code"], r["ast_hash"])
            )

        self.conn.commit()
        src.close()
        return len(rows)

    def all_methods(self, limit: int = 500, offset: int = 0) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_methods ORDER BY class_name, name LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]

    def by_class(self, class_name: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_methods WHERE class_name = ? ORDER BY name",
            (class_name,)
        ).fetchall()
        return [dict(r) for r in rows]

    def by_name(self, name: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_methods WHERE name LIKE ? ORDER BY cyclomatic DESC",
            ("%" + name + "%",)
        ).fetchall()
        return [dict(r) for r in rows]

    def god_methods(self, threshold: int = 10) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_methods WHERE cyclomatic > ? ORDER BY cyclomatic DESC",
            (threshold,)
        ).fetchall()
        return [dict(r) for r in rows]

    def callers_of(self, method_name: str) -> List[dict]:
        """Which methods call a given method name."""
        rows = self.conn.execute(
            "SELECT * FROM ci_methods WHERE call_names LIKE ? ORDER BY class_name, name",
            ("%" + method_name + "%",)
        ).fetchall()
        return [dict(r) for r in rows]

    def most_connected(self, limit: int = 20) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ci_methods ORDER BY call_count DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def classes(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT class_name, COUNT(*) as method_count, "
            "AVG(cyclomatic) as avg_cx, MAX(cyclomatic) as max_cx, "
            "SUM(body_lines) as total_lines "
            "FROM ci_methods GROUP BY class_name ORDER BY method_count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        row = self.conn.execute(
            "SELECT COUNT(*) as total, "
            "COUNT(DISTINCT class_name) as classes, "
            "COUNT(DISTINCT name) as distinct_names, "
            "AVG(cyclomatic) as avg_cx, MAX(cyclomatic) as max_cx, "
            "AVG(body_lines) as avg_lines, MAX(body_lines) as max_lines, "
            "SUM(recursive) as recursive, SUM(is_empty) as empty, "
            "SUM(has_docstring) as documented "
            "FROM ci_methods"
        ).fetchone()
        return dict(row) if row else {}

    def find_connections(self, method_name: str) -> Dict:
        """
        Dynamic connection experiment:
        Given a method name, find:
        - Who calls it
        - What it calls
        - Methods in same class
        - Methods with same name in other classes
        """
        result = {}

        target = self.conn.execute(
            "SELECT * FROM ci_methods WHERE name = ? LIMIT 1", (method_name,)
        ).fetchone()

        if not target:
            return {"error": f"Method '{method_name}' not found"}

        target = dict(target)

        # Who calls this method
        callers = self.conn.execute(
            "SELECT class_name, name, qualname, cyclomatic FROM ci_methods "
            "WHERE call_names LIKE ? AND qualname != ?",
            ("%" + method_name + "%", target["qualname"])
        ).fetchall()
        result["called_by"] = [dict(r) for r in callers]

        # What this method calls
        call_names = [c.strip() for c in (target["call_names"] or "").split(",") if c.strip()]
        if call_names:
            placeholders = ",".join(["?"] * len(call_names))
            called = self.conn.execute(
                f"SELECT class_name, name, qualname, cyclomatic FROM ci_methods "
                f"WHERE name IN ({placeholders}) GROUP BY qualname",
                call_names
            ).fetchall()
            result["calls"] = [dict(r) for r in called]
        else:
            result["calls"] = []

        # Methods in same class
        siblings = self.conn.execute(
            "SELECT name, qualname, cyclomatic, call_count FROM ci_methods "
            "WHERE class_name = ? AND name != ? ORDER BY name",
            (target["class_name"], method_name)
        ).fetchall()
        result["siblings"] = [dict(r) for r in siblings]

        # Same method name in other classes (interface/pattern detection)
        same_name = self.conn.execute(
            "SELECT class_name, qualname, cyclomatic FROM ci_methods "
            "WHERE name = ? AND class_name != ? ORDER BY class_name",
            (method_name, target["class_name"])
        ).fetchall()
        result["same_name_elsewhere"] = [dict(r) for r in same_name]

        return result

    def experiment_combine(self, method_a: str, method_b: str) -> Dict:
        """
        Experiment: given two method names, find overlap and connection paths.
        - Do they call each other?
        - Do they share called methods?
        - Are they in the same class?
        - What methods connect A to B?
        """
        a = self.conn.execute(
            "SELECT * FROM ci_methods WHERE name = ? LIMIT 1", (method_a,)
        ).fetchone()
        b = self.conn.execute(
            "SELECT * FROM ci_methods WHERE name = ? LIMIT 1", (method_b,)
        ).fetchone()

        if not a or not b:
            return {"error": "One or both methods not found"}

        a, b = dict(a), dict(b)
        a_calls = set(c.strip() for c in (a["call_names"] or "").split(",") if c.strip())
        b_calls = set(c.strip() for c in (b["call_names"] or "").split(",") if c.strip())

        return {
            "a": {"qualname": a["qualname"], "class": a["class_name"], "cx": a["cyclomatic"]},
            "b": {"qualname": b["qualname"], "class": b["class_name"], "cx": b["cyclomatic"]},
            "same_class": a["class_name"] == b["class_name"],
            "a_calls_b": method_b in a_calls,
            "b_calls_a": method_a in b_calls,
            "shared_calls": list(a_calls & b_calls),
            "a_only_calls": list(a_calls - b_calls),
            "b_only_calls": list(b_calls - a_calls),
        }


if __name__ == "__main__":
    db_path = DB.METHODS_DB
    if os.path.exists(db_path):
        os.remove(db_path)

    store = MethodsStore(db_path)
    count = store.ingest_from_v2()
    stats = store.stats()

    print(f"=== METHODS-ONLY STORE ===")
    print(f"  Total methods:    {stats['total']}")
    print(f"  Distinct classes: {stats['classes']}")
    print(f"  Distinct names:   {stats['distinct_names']}")
    print(f"  Avg complexity:   {stats['avg_cx']:.1f}")
    print(f"  Max complexity:   {stats['max_cx']}")
    print(f"  Avg body lines:   {stats['avg_lines']:.0f}")
    print(f"  Max body lines:   {stats['max_lines']}")
    print(f"  Recursive:        {stats['recursive']}")
    print(f"  Empty:            {stats['empty']}")
    print(f"  Documented:       {stats['documented']}")

    print(f"\n=== TOP 10 GOD METHODS ===")
    for m in store.god_methods(15)[:10]:
        print(f"  cx={m['cyclomatic']:3d} lines={m['body_lines']:4d} {m['qualname']}")

    print(f"\n=== TOP 10 MOST CONNECTED ===")
    for m in store.most_connected(10):
        print(f"  calls={m['call_count']:3d} {m['qualname']}")

    print(f"\n=== EXPERIMENT: find_connections('Run') ===")
    conn_info = store.find_connections("Run")
    print(f"  Called by:   {len(conn_info.get('called_by', []))} methods")
    print(f"  Calls:       {len(conn_info.get('calls', []))} methods")
    print(f"  Siblings:    {len(conn_info.get('siblings', []))} methods")
    print(f"  Same name:   {len(conn_info.get('same_name_elsewhere', []))} classes")

    print(f"\n=== EXPERIMENT: combine('Run', 'Scan') ===")
    combo = store.experiment_combine("Run", "Scan")
    if "error" not in combo:
        print(f"  A: {combo['a']['qualname']} (cx={combo['a']['cx']})")
        print(f"  B: {combo['b']['qualname']} (cx={combo['b']['cx']})")
        print(f"  Same class:      {combo['same_class']}")
        print(f"  A calls B:       {combo['a_calls_b']}")
        print(f"  B calls A:       {combo['b_calls_a']}")
        print(f"  Shared calls:    {combo['shared_calls'][:10]}")
        print(f"  A-only calls:    {combo['a_only_calls'][:10]}")
        print(f"  B-only calls:    {combo['b_only_calls'][:10]}")

    store.close()
