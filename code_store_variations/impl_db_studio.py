import os
import sqlite3
import json
import tempfile


class DomDbStudio:
    """DB Studio domain: schema browsing, comparison, design, migration, and reporting using sqlite3."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "connections": {}, "schemas": {}, "migrations": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "browse": self.browse, "compare": self.compare, "design": self.design,
            "edit": self.edit, "import": self.import_, "migrate": self.migrate,
            "monitor": self.monitor, "optimize": self.optimize, "report": self.report,
            "visualize": self.visualize,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _connect(self, path):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    def _temp_db(self):
        path = os.path.join(tempfile.gettempdir(), f"dbstudio_{os.getpid()}.db")
        return path

    def browse(self, params=None):
        params = params or {}
        try:
            path = params.get("path") or self._temp_db()
            table = params.get("table")
            conn = self._connect(path)
            cur = conn.cursor()
            if table:
                cur.execute(f'SELECT * FROM "{table}" LIMIT 100')
                rows = [dict(r) for r in cur.fetchall()]
                result = {"domain": "db_studio", "method": "browse", "path": path, "table": table, "rows": rows, "count": len(rows)}
            else:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r["name"] for r in cur.fetchall()]
                result = {"domain": "db_studio", "method": "browse", "path": path, "tables": tables, "count": len(tables)}
            conn.close()
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BROWSE_ERROR", str(e), 0))

    def compare(self, params=None):
        params = params or {}
        try:
            left = params.get("left") or {}
            right = params.get("right") or {}
            left_keys = set(left.keys()) if isinstance(left, dict) else set(left)
            right_keys = set(right.keys()) if isinstance(right, dict) else set(right)
            added = list(right_keys - left_keys)
            removed = list(left_keys - right_keys)
            common = list(left_keys & right_keys)
            result = {"domain": "db_studio", "method": "compare", "added": added, "removed": removed, "common": common}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPARE_ERROR", str(e), 0))

    def design(self, params=None):
        params = params or {}
        try:
            schema = params.get("schema") or {}
            self.state["schemas"][schema.get("name", "default")] = schema
            result = {"domain": "db_studio", "method": "design", "schema": schema, "total_schemas": len(self.state["schemas"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DESIGN_ERROR", str(e), 0))

    def edit(self, params=None):
        params = params or {}
        try:
            path = params.get("path") or self._temp_db()
            table = params.get("table", "")
            op = params.get("op", "update")
            data = params.get("data") or {}
            conn = self._connect(path)
            cur = conn.cursor()
            affected = 0
            if op == "insert" and table and data:
                cols = ",".join(data.keys())
                ph = ",".join(["?"] * len(data))
                cur.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({ph})', list(data.values()))
                affected = cur.rowcount
                conn.commit()
            elif op == "update" and table and data:
                sets = ",".join([f'{k}=?' for k in data.keys()])
                cur.execute(f'UPDATE "{table}" SET {sets}', list(data.values()))
                affected = cur.rowcount
                conn.commit()
            conn.close()
            result = {"domain": "db_studio", "method": "edit", "path": path, "table": table, "op": op, "affected": affected}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EDIT_ERROR", str(e), 0))

    def import_(self, params=None):
        params = params or {}
        try:
            path = params.get("path") or self._temp_db()
            table = params.get("table", "imported")
            rows = params.get("rows") or []
            conn = self._connect(path)
            cur = conn.cursor()
            if rows:
                cols = list(rows[0].keys())
                col_def = ",".join([f'"{c}" TEXT' for c in cols])
                cur.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_def})')
                ph = ",".join(["?"] * len(cols))
                for r in rows:
                    cur.execute(f'INSERT INTO "{table}" ({",".join(cols)}) VALUES ({ph})', [r.get(c) for c in cols])
                conn.commit()
            conn.close()
            result = {"domain": "db_studio", "method": "import", "path": path, "table": table, "imported": len(rows)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IMPORT_ERROR", str(e), 0))

    def migrate(self, params=None):
        params = params or {}
        try:
            path = params.get("path") or self._temp_db()
            sql = params.get("sql") or ""
            conn = self._connect(path)
            cur = conn.cursor()
            cur.executescript(sql)
            conn.commit()
            conn.close()
            entry = {"sql": sql, "ts": __import__("time").time()}
            self.state["migrations"].append(entry)
            result = {"domain": "db_studio", "method": "migrate", "path": path, "applied": True, "total_migrations": len(self.state["migrations"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MIGRATE_ERROR", str(e), 0))

    def monitor(self, params=None):
        params = params or {}
        try:
            path = params.get("path") or self._temp_db()
            conn = self._connect(path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r["name"] for r in cur.fetchall()]
            sizes = {}
            for t in tables:
                cur.execute(f'SELECT COUNT(*) AS c FROM "{t}"')
                sizes[t] = cur.fetchone()["c"]
            conn.close()
            result = {"domain": "db_studio", "method": "monitor", "path": path, "tables": tables, "row_counts": sizes}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MONITOR_ERROR", str(e), 0))

    def optimize(self, params=None):
        params = params or {}
        try:
            path = params.get("path") or self._temp_db()
            conn = self._connect(path)
            cur = conn.cursor()
            cur.execute("VACUUM")
            conn.commit()
            conn.close()
            size = os.path.getsize(path) if os.path.exists(path) else 0
            result = {"domain": "db_studio", "method": "optimize", "path": path, "optimized": True, "size_bytes": size}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("OPTIMIZE_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            path = params.get("path") or self._temp_db()
            conn = self._connect(path)
            cur = conn.cursor()
            cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
            schema = [{"name": r["name"], "sql": r["sql"]} for r in cur.fetchall()]
            conn.close()
            result = {"domain": "db_studio", "method": "report", "path": path, "schema": schema, "table_count": len(schema)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def visualize(self, params=None):
        params = params or {}
        try:
            path = params.get("path") or self._temp_db()
            conn = self._connect(path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r["name"] for r in cur.fetchall()]
            conn.close()
            dot = "digraph db {\n"
            for t in tables:
                dot += f'  "{t}" [shape=box];\n'
            dot += "}\n"
            result = {"domain": "db_studio", "method": "visualize", "path": path, "tables": tables, "dot": dot}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VISUALIZE_ERROR", str(e), 0))
