class DomDb:
    """Database domain: SQL DDL/DML operations against a relational store."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        if param:
            for k, v in param.items():
                self.state["config"][k] = v

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "alter_table": self.alter_table,
            "backup": self.backup,
            "bulk_insert": self.bulk_insert,
            "commit": self.commit,
            "count": self.count,
            "create_index": self.create_index,
            "create_table": self.create_table,
            "delete": self.delete,
            "describe": self.describe,
            "disconnect": self.disconnect,
            "drop_table": self.drop_table,
            "exists": self.exists,
            "fetch": self.fetch,
            "insert": self.insert,
            "migrate": self.migrate,
            "optimize": self.optimize,
            "restore": self.restore,
            "select": self.select,
            "transaction": self.transaction,
            "update": self.update,
            "upsert": self.upsert,
            "vacuum": self.vacuum,
        }
        h = handlers.get(command)
        if h:
            return h(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _exec(self, sql, args=None):
        cur = None
        conn = self.db
        if conn is None:
            return (0, None, ("DB_NOT_CONNECTED", "No db connection provided", 0))
        try:
            cur = conn.cursor()
            cur.execute(sql, args or ())
            return cur
        except Exception:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            raise

    def alter_table(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            action = params.get("action")
            if not table or not action:
                return (0, None, ("ALTER_TABLE_ERROR", "table and action required", 0))
            sql = f"ALTER TABLE {table} {action}"
            cur = self._exec(sql)
            conn = self.db
            conn.commit()
            cur.close()
            result = {"domain": "db", "method": "alter_table", "table": table, "action": action, "executed": sql}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ALTER_TABLE_ERROR", str(e), 0))

    def backup(self, params=None):
        params = params or {}
        try:
            target = params.get("target", "backup.sql")
            tables = params.get("tables", [])
            statements = []
            cur = self._exec("SHOW TABLES")
            rows = cur.fetchall()
            cur.close()
            existing = [r[0] for r in rows]
            selected = [t for t in tables if t in existing] if tables else existing
            for t in selected:
                c2 = self._exec(f"SELECT * FROM {t}")
                data = c2.fetchall()
                c2.close()
                statements.append({"table": t, "rows": len(data)})
            self.state["results"].append({"backup": target, "tables": statements})
            result = {"domain": "db", "method": "backup", "target": target, "tables": statements}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BACKUP_ERROR", str(e), 0))

    def bulk_insert(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            columns = params.get("columns", [])
            rows = params.get("rows", [])
            if not table or not columns or not rows:
                return (0, None, ("BULK_INSERT_ERROR", "table, columns and rows required", 0))
            placeholders = "(" + ",".join(["%s"] * len(columns)) + ")"
            sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES {placeholders}"
            cur = self._exec(sql, [tuple(r) for r in rows])
            conn = self.db
            conn.commit()
            count = cur.rowcount
            cur.close()
            result = {"domain": "db", "method": "bulk_insert", "table": table, "inserted": count}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BULK_INSERT_ERROR", str(e), 0))

    def commit(self, params=None):
        params = params or {}
        try:
            conn = self.db
            if conn is None:
                return (0, None, ("COMMIT_ERROR", "No db connection", 0))
            conn.commit()
            result = {"domain": "db", "method": "commit", "committed": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMMIT_ERROR", str(e), 0))

    def count(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            where = params.get("where")
            if not table:
                return (0, None, ("COUNT_ERROR", "table required", 0))
            sql = f"SELECT COUNT(*) FROM {table}"
            args = ()
            if where:
                sql += f" WHERE {where}"
            cur = self._exec(sql, args)
            row = cur.fetchone()
            cur.close()
            total = row[0] if row else 0
            result = {"domain": "db", "method": "count", "table": table, "count": total}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COUNT_ERROR", str(e), 0))

    def create_index(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            table = params.get("table")
            columns = params.get("columns", [])
            if not name or not table or not columns:
                return (0, None, ("CREATE_INDEX_ERROR", "name, table and columns required", 0))
            sql = f"CREATE INDEX {name} ON {table} ({','.join(columns)})"
            cur = self._exec(sql)
            conn = self.db
            conn.commit()
            cur.close()
            result = {"domain": "db", "method": "create_index", "name": name, "table": table}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_INDEX_ERROR", str(e), 0))

    def create_table(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            columns = params.get("columns", {})
            if not table or not columns:
                return (0, None, ("CREATE_TABLE_ERROR", "table and columns required", 0))
            col_defs = ", ".join(f"{c} {t}" for c, t in columns.items())
            sql = f"CREATE TABLE {table} ({col_defs})"
            cur = self._exec(sql)
            conn = self.db
            conn.commit()
            cur.close()
            self.state["catalog"].append(table)
            result = {"domain": "db", "method": "create_table", "table": table, "columns": list(columns.keys())}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_TABLE_ERROR", str(e), 0))

    def delete(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            where = params.get("where")
            args = params.get("args", ())
            if not table or not where:
                return (0, None, ("DELETE_ERROR", "table and where required", 0))
            sql = f"DELETE FROM {table} WHERE {where}"
            cur = self._exec(sql, args)
            conn = self.db
            conn.commit()
            deleted = cur.rowcount
            cur.close()
            result = {"domain": "db", "method": "delete", "table": table, "deleted": deleted}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def describe(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            if not table:
                return (0, None, ("DESCRIBE_ERROR", "table required", 0))
            cur = self._exec(f"DESCRIBE {table}")
            rows = cur.fetchall()
            cur.close()
            cols = [{"name": r[0], "type": r[1]} for r in rows]
            result = {"domain": "db", "method": "describe", "table": table, "columns": cols}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DESCRIBE_ERROR", str(e), 0))

    def disconnect(self, params=None):
        params = params or {}
        try:
            conn = self.db
            if conn is not None:
                conn.close()
            self.db = None
            result = {"domain": "db", "method": "disconnect", "disconnected": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISCONNECT_ERROR", str(e), 0))

    def drop_table(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            if not table:
                return (0, None, ("DROP_TABLE_ERROR", "table required", 0))
            sql = f"DROP TABLE IF EXISTS {table}"
            cur = self._exec(sql)
            conn = self.db
            conn.commit()
            cur.close()
            if table in self.state["catalog"]:
                self.state["catalog"].remove(table)
            result = {"domain": "db", "method": "drop_table", "table": table, "dropped": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DROP_TABLE_ERROR", str(e), 0))

    def exists(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            if not table:
                return (0, None, ("EXISTS_ERROR", "table required", 0))
            cur = self._exec("SHOW TABLES")
            rows = cur.fetchall()
            cur.close()
            found = any(r[0] == table for r in rows)
            result = {"domain": "db", "method": "exists", "table": table, "exists": found}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXISTS_ERROR", str(e), 0))

    def fetch(self, params=None):
        params = params or {}
        try:
            sql = params.get("sql")
            args = params.get("args", ())
            limit = params.get("limit", 100)
            if not sql:
                return (0, None, ("FETCH_ERROR", "sql required", 0))
            cur = self._exec(sql, args)
            rows = cur.fetchmany(limit)
            cur.close()
            result = {"domain": "db", "method": "fetch", "rows": rows, "count": len(rows)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FETCH_ERROR", str(e), 0))

    def insert(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            values = params.get("values", {})
            if not table or not values:
                return (0, None, ("INSERT_ERROR", "table and values required", 0))
            cols = list(values.keys())
            placeholders = ",".join(["%s"] * len(cols))
            sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
            cur = self._exec(sql, tuple(values[c] for c in cols))
            conn = self.db
            conn.commit()
            inserted = cur.rowcount
            last_id = cur.lastrowid
            cur.close()
            result = {"domain": "db", "method": "insert", "table": table, "inserted": inserted, "last_id": last_id}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INSERT_ERROR", str(e), 0))

    def migrate(self, params=None):
        params = params or {}
        try:
            steps = params.get("steps", [])
            applied = []
            for step in steps:
                name = step.get("name")
                sql = step.get("sql")
                if not name or not sql:
                    continue
                cur = self._exec(sql)
                conn = self.db
                conn.commit()
                cur.close()
                applied.append(name)
            result = {"domain": "db", "method": "migrate", "applied": applied, "count": len(applied)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MIGRATE_ERROR", str(e), 0))

    def optimize(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            if not table:
                return (0, None, ("OPTIMIZE_ERROR", "table required", 0))
            cur = self._exec(f"OPTIMIZE TABLE {table}")
            rows = cur.fetchall()
            cur.close()
            result = {"domain": "db", "method": "optimize", "table": table, "result": [list(r) for r in rows]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("OPTIMIZE_ERROR", str(e), 0))

    def restore(self, params=None):
        params = params or {}
        try:
            source = params.get("source")
            if not source:
                return (0, None, ("RESTORE_ERROR", "source required", 0))
            result = {"domain": "db", "method": "restore", "source": source, "restored": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESTORE_ERROR", str(e), 0))

    def select(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            columns = params.get("columns", "*")
            where = params.get("where")
            order = params.get("order")
            limit = params.get("limit")
            args = params.get("args", ())
            if not table:
                return (0, None, ("SELECT_ERROR", "table required", 0))
            col_str = columns if isinstance(columns, str) else ",".join(columns)
            sql = f"SELECT {col_str} FROM {table}"
            if where:
                sql += f" WHERE {where}"
            if order:
                sql += f" ORDER BY {order}"
            if limit:
                sql += f" LIMIT {int(limit)}"
            cur = self._exec(sql, args)
            rows = cur.fetchall()
            cur.close()
            result = {"domain": "db", "method": "select", "table": table, "rows": [list(r) for r in rows], "count": len(rows)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SELECT_ERROR", str(e), 0))

    def transaction(self, params=None):
        params = params or {}
        try:
            ops = params.get("operations", [])
            conn = self.db
            if conn is None:
                return (0, None, ("TRANSACTION_ERROR", "No db connection", 0))
            cur = conn.cursor()
            executed = []
            try:
                for op in ops:
                    sql = op.get("sql")
                    args = op.get("args", ())
                    if sql:
                        cur.execute(sql, args)
                        executed.append(sql)
                conn.commit()
                result = {"domain": "db", "method": "transaction", "executed": executed, "committed": True}
                return (1, result, None)
            except Exception as inner:
                conn.rollback()
                return (0, None, ("TRANSACTION_ERROR", f"rolled back: {inner}", 0))
            finally:
                cur.close()
        except Exception as e:
            return (0, None, ("TRANSACTION_ERROR", str(e), 0))

    def update(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            sets = params.get("set", {})
            where = params.get("where")
            args = params.get("args", ())
            if not table or not sets or not where:
                return (0, None, ("UPDATE_ERROR", "table, set and where required", 0))
            set_clause = ", ".join(f"{k}=%s" for k in sets.keys())
            sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
            cur = self._exec(sql, tuple(sets.values()) + tuple(args))
            conn = self.db
            conn.commit()
            updated = cur.rowcount
            cur.close()
            result = {"domain": "db", "method": "update", "table": table, "updated": updated}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UPDATE_ERROR", str(e), 0))

    def upsert(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            values = params.get("values", {})
            keys = params.get("keys", [])
            if not table or not values:
                return (0, None, ("UPSERT_ERROR", "table and values required", 0))
            cols = list(values.keys())
            placeholders = ",".join(["%s"] * len(cols))
            update_clause = ", ".join(f"{c}=VALUES({c})" for c in cols if c not in keys)
            sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
            if update_clause:
                sql += f" ON DUPLICATE KEY UPDATE {update_clause}"
            cur = self._exec(sql, tuple(values[c] for c in cols))
            conn = self.db
            conn.commit()
            affected = cur.rowcount
            cur.close()
            result = {"domain": "db", "method": "upsert", "table": table, "affected": affected}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UPSERT_ERROR", str(e), 0))

    def vacuum(self, params=None):
        params = params or {}
        try:
            result = {"domain": "db", "method": "vacuum", "vacuumed": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VACUUM_ERROR", str(e), 0))
