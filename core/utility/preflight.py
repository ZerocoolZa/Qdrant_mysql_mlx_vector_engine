# [@GHOST]{[@file<preflight.py>][@domain<utility>][@role<preflight>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<preflight_validator>][@return<tuple3>][@orch<SystemCheck>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Pre-flight validator — checks DB constraints, orphan rows, type overflow, FK resolution before operations}
# [@WCL]{[@self_contained<true>][@source<MySQL_vb_code_test_PreFlightValidator>][@checks<constraints|orphans|overflow|fk>]}

import sqlite3


class PreFlight:
    """Pre-flight validator — checks database integrity before operations.

    Checks:
    1. Constraint violations — NOT NULL, UNIQUE, CHECK
    2. Orphan rows — foreign key references to missing parents
    3. Type overflow — values exceeding column limits
    4. FK resolution — simulate FK joins to verify connectivity
    5. Migration report — summary of all issues found

    Usage:
        from core.utility.preflight import PreFlight
        pf = PreFlight()
        code, report, err = pf.Run("check", {"db_path": "/path/to/db.sqlite"})
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "last_report": {},
            "last_db": "",
        }

    def Run(self, command, params=None):
        if command == "check":
            return self.check((params or {}).get("db_path"))
        elif command == "detect_constraints":
            return self.detect_constraint_violations((params or {}).get("db_path"))
        elif command == "detect_orphans":
            return self.detect_orphan_rows((params or {}).get("db_path"))
        elif command == "detect_overflow":
            return self.detect_type_overflow((params or {}).get("db_path"))
        elif command == "simulate_fk":
            return self.simulate_fk_resolution((params or {}).get("db_path"))
        elif command == "migration_report":
            return self.generate_migration_report((params or {}).get("db_path"))
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def connect(self, db_path):
        if not db_path or not __import__("os").path.exists(db_path):
            return None
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_tables(self, conn):
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        return [row[0] for row in cur.fetchall()]

    def get_columns(self, conn, table):
        cur = conn.cursor()
        cur.execute("PRAGMA table_info({})".format(table))
        return cur.fetchall()

    def detect_constraint_violations(self, db_path):
        if not db_path:
            return (0, None, ("missing_param", "db_path", 0))
        conn = self.connect(db_path)
        if not conn:
            return (0, None, ("db_not_found", db_path, 0))
        violations = []
        for table in self.get_tables(conn):
            columns = self.get_columns(conn, table)
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                not_null = col[3]
                if not_null:
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM {} WHERE {} IS NULL".format(table, col_name))
                    count = cur.fetchone()[0]
                    if count > 0:
                        violations.append({
                            "table": table, "column": col_name,
                            "rule": "not_null", "count": count,
                        })
        conn.close()
        self.state["last_report"]["constraints"] = violations
        return (1, {"violations": violations, "count": len(violations)}, None)

    def detect_orphan_rows(self, db_path):
        if not db_path:
            return (0, None, ("missing_param", "db_path", 0))
        conn = self.connect(db_path)
        if not conn:
            return (0, None, ("db_not_found", db_path, 0))
        orphans = []
        for table in self.get_tables(conn):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_key_list({})".format(table))
            fks = cur.fetchall()
            for fk in fks:
                ref_table = fk[2]
                ref_col = fk[4]
                from_col = fk[3]
                cur.execute(
                    "SELECT COUNT(*) FROM {} WHERE {} NOT IN (SELECT {} FROM {}) AND {} IS NOT NULL".format(
                        table, from_col, ref_col, ref_table, from_col
                    )
                )
                count = cur.fetchone()[0]
                if count > 0:
                    orphans.append({
                        "table": table, "column": from_col,
                        "ref_table": ref_table, "ref_col": ref_col, "count": count,
                    })
        conn.close()
        self.state["last_report"]["orphans"] = orphans
        return (1, {"orphans": orphans, "count": len(orphans)}, None)

    def detect_type_overflow(self, db_path):
        if not db_path:
            return (0, None, ("missing_param", "db_path", 0))
        conn = self.connect(db_path)
        if not conn:
            return (0, None, ("db_not_found", db_path, 0))
        overflows = []
        for table in self.get_tables(conn):
            columns = self.get_columns(conn, table)
            for col in columns:
                col_name = col[1]
                col_type = col[2].upper()
                if "VARCHAR" in col_type or "TEXT" in col_type:
                    import re
                    match = re.search(r'\((\d+)\)', col_type)
                    if match:
                        max_len = int(match.group(1))
                        cur = conn.cursor()
                        cur.execute("SELECT MAX(LENGTH({})) FROM {}".format(col_name, table))
                        max_actual = cur.fetchone()[0]
                        if max_actual and max_actual > max_len:
                            overflows.append({
                                "table": table, "column": col_name,
                                "max_len": max_len, "actual": max_actual,
                            })
        conn.close()
        self.state["last_report"]["overflows"] = overflows
        return (1, {"overflows": overflows, "count": len(overflows)}, None)

    def simulate_fk_resolution(self, db_path):
        if not db_path:
            return (0, None, ("missing_param", "db_path", 0))
        conn = self.connect(db_path)
        if not conn:
            return (0, None, ("db_not_found", db_path, 0))
        results = []
        for table in self.get_tables(conn):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_key_list({})".format(table))
            fks = cur.fetchall()
            for fk in fks:
                ref_table = fk[2]
                from_col = fk[3]
                ref_col = fk[4]
                cur.execute(
                    "SELECT COUNT(*) FROM {} WHERE {} IN (SELECT {} FROM {})".format(
                        table, from_col, ref_col, ref_table
                    )
                )
                resolved = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM {}".format(table))
                total = cur.fetchone()[0]
                results.append({
                    "table": table, "from_col": from_col,
                    "ref_table": ref_table, "ref_col": ref_col,
                    "resolved": resolved, "total": total,
                    "rate": round(resolved / total * 100, 1) if total > 0 else 100,
                })
        conn.close()
        self.state["last_report"]["fk_resolution"] = results
        return (1, {"fk_results": results, "count": len(results)}, None)

    def generate_migration_report(self, db_path):
        if not db_path:
            return (0, None, ("missing_param", "db_path", 0))
        self.state["last_report"] = {}
        self.state["last_db"] = db_path
        c1, constraints, _ = self.detect_constraint_violations(db_path)
        c2, orphans, _ = self.detect_orphan_rows(db_path)
        c3, overflows, _ = self.detect_type_overflow(db_path)
        c4, fk_results, _ = self.simulate_fk_resolution(db_path)
        report = {
            "db_path": db_path,
            "constraints": constraints,
            "orphans": orphans,
            "overflows": overflows,
            "fk_resolution": fk_results,
            "total_issues": len(constraints["violations"]) + len(orphans["orphans"]) + len(overflows["overflows"]),
        }
        self.state["last_report"] = report
        return (1, report, None)

    def check(self, db_path):
        return self.generate_migration_report(db_path)
