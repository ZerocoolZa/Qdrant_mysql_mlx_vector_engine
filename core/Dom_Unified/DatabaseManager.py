# [@GHOST]{[@file<DatabaseManager.py>][@domain<Dom_Unified>][@role<database>][@auth<cascade>][@date<2026-06-27>][@ver<2.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<database>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Unified DatabaseManager — MySQL + SQLite + Neo4j. Accepts commands, returns results.}
# [@CLASS]{DatabaseManager}
# [@METHOD]{Run,Connect,Disconnect,Query,Execute,Insert,Update,Delete,Begin,Commit,Rollback,InitSchema,BulkInsert,Cypher}

"""
Unified DatabaseManager — accepts parameters, returns results.

Three backends: MySQL, SQLite, Neo4j.
Caller picks the backend via db_type. DatabaseManager just runs the command.

USAGE:
    from Dom_Unified import DatabaseManager

    # MySQL
    db = DatabaseManager(param={"db_type": "mysql", "db_name": "bcl_ir"})
    ok, rows, err = db.Run("query", {"sql": "SELECT * FROM bcl_classes LIMIT 5"})

    # SQLite
    db = DatabaseManager(param={"db_type": "sqlite", "sqlite_path": "/path/to.db"})

    # Neo4j
    db = DatabaseManager(param={"db_type": "neo4j", "neo4j_uri": "bolt://localhost:7687"})
    ok, data, err = db.Run("cypher", {"query": "MATCH (n:Method) RETURN n.name LIMIT 5"})
"""

import sqlite3

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

try:
    from neo4j import GraphDatabase
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False


class DatabaseManager:
    """
    Unified database manager for MySQL and SQLite.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_type": "sqlite",
                "db_host": "localhost",
                "db_user": "root",
                "db_password": "",
                "db_name": "default",
                "sqlite_path": ":memory:",
                "autocommit": True,
                "neo4j_uri": "bolt://localhost:7687",
                "neo4j_user": "neo4j",
                "neo4j_password": "",
            },
            "conn": None,
            "stats": {"queries": 0, "rows_affected": 0, "errors": 0, "transactions": 0},
        }
        if param:
            for key, val in param.items():
                if key in self.state["config"]:
                    self.state["config"][key] = val
        self._connect()

    def Run(self, command, params=None):
        dispatch = {
            "connect": self._cmd_connect,
            "disconnect": self._cmd_disconnect,
            "query": self._cmd_query,
            "query_one": self._cmd_query_one,
            "execute": self._cmd_execute,
            "insert": self._cmd_insert,
            "insert_many": self._cmd_insert_many,
            "update": self._cmd_update,
            "delete": self._cmd_delete,
            "begin": self._cmd_begin,
            "commit": self._cmd_commit,
            "rollback": self._cmd_rollback,
            "init_schema": self._cmd_init_schema,
            "table_exists": self._cmd_table_exists,
            "count": self._cmd_count,
            "cypher": self._cmd_cypher,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"Unknown: {command}", 0))
        return handler(params or {})

    def read_state(self, params=None):
        safe = {k: v for k, v in self.state.items() if k != "conn"}
        return (1, safe, None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # CONNECTION
    # ════════════════════════════════════════════

    def _connect(self):
        cfg = self.state["config"]
        try:
            if cfg["db_type"] == "mysql":
                if not HAS_MYSQL:
                    return
                self.state["conn"] = mysql.connector.connect(
                    user=cfg["db_user"],
                    password=cfg["db_password"],
                    host=cfg["db_host"],
                    database=cfg["db_name"],
                )
                self.state["conn"].autocommit = cfg["autocommit"]
            elif cfg["db_type"] == "neo4j":
                if not HAS_NEO4J:
                    return
                if cfg["neo4j_user"] and cfg["neo4j_password"]:
                    self.state["conn"] = GraphDatabase.driver(
                        cfg["neo4j_uri"],
                        auth=(cfg["neo4j_user"], cfg["neo4j_password"]),
                    )
                else:
                    self.state["conn"] = GraphDatabase.driver(
                        cfg["neo4j_uri"],
                        auth=None,
                    )
            else:
                self.state["conn"] = sqlite3.connect(cfg["sqlite_path"])
                self.state["conn"].row_factory = sqlite3.Row
        except Exception:
            self.state["conn"] = None

    def _cmd_connect(self, params):
        self._connect()
        if self.state["conn"] is None:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_CONNECT", "connection failed", 0))
        return (1, {"connected": True, "db_type": self.state["config"]["db_type"]}, None)

    def _cmd_disconnect(self, params):
        if self.state["conn"]:
            self.state["conn"].close()
            self.state["conn"] = None
        return (1, {"disconnected": True}, None)

    def _placeholder(self):
        return "%s" if self.state["config"]["db_type"] == "mysql" else "?"

    def _cursor(self):
        if not self.state["conn"]:
            self._connect()
        if not self.state["conn"]:
            return None
        return self.state["conn"].cursor()

    def _rows_to_dicts(self, rows, cursor):
        if not rows:
            return []
        if self.state["config"]["db_type"] == "mysql":
            cols = [desc[0] for desc in cursor.description] if cursor.description else []
            return [dict(zip(cols, row)) for row in rows]
        else:
            return [dict(row) for row in rows]

    # ════════════════════════════════════════════
    # QUERY (SELECT)
    # ════════════════════════════════════════════

    def _cmd_query(self, params):
        sql = self._p(params, "sql")
        args = self._p(params, "args", [])
        if not sql:
            return (0, None, ("ERR_NO_SQL", "params['sql'] required", 0))
        cursor = self._cursor()
        if not cursor:
            return (0, None, ("ERR_NO_CONN", "no database connection", 0))
        try:
            cursor.execute(sql, args)
            rows = cursor.fetchall()
            result = self._rows_to_dicts(rows, cursor)
            self.state["stats"]["queries"] += 1
            cursor.close()
            return (1, result, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            cursor.close()
            return (0, None, ("ERR_QUERY", str(e), 0))

    def _cmd_query_one(self, params):
        sql = self._p(params, "sql")
        args = self._p(params, "args", [])
        if not sql:
            return (0, None, ("ERR_NO_SQL", "params['sql'] required", 0))
        cursor = self._cursor()
        if not cursor:
            return (0, None, ("ERR_NO_CONN", "no database connection", 0))
        try:
            cursor.execute(sql, args)
            row = cursor.fetchone()
            cursor.close()
            self.state["stats"]["queries"] += 1
            if not row:
                return (1, None, None)
            if self.state["config"]["db_type"] == "mysql":
                cols = [desc[0] for desc in cursor.description]
                return (1, dict(zip(cols, row)), None)
            else:
                return (1, dict(row), None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            cursor.close()
            return (0, None, ("ERR_QUERY", str(e), 0))

    # ════════════════════════════════════════════
    # EXECUTE (INSERT/UPDATE/DELETE)
    # ════════════════════════════════════════════

    def _cmd_execute(self, params):
        sql = self._p(params, "sql")
        args = self._p(params, "args", [])
        if not sql:
            return (0, None, ("ERR_NO_SQL", "params['sql'] required", 0))
        cursor = self._cursor()
        if not cursor:
            return (0, None, ("ERR_NO_CONN", "no database connection", 0))
        try:
            cursor.execute(sql, args)
            if self.state["config"]["autocommit"]:
                self.state["conn"].commit()
            affected = cursor.rowcount
            last_id = None
            if self.state["config"]["db_type"] == "sqlite":
                last_id = cursor.lastrowid
            elif cursor.lastrowid:
                last_id = cursor.lastrowid
            self.state["stats"]["rows_affected"] += affected
            cursor.close()
            return (1, {"affected": affected, "last_id": last_id}, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            cursor.close()
            return (0, None, ("ERR_EXECUTE", str(e), 0))

    def _cmd_insert(self, params):
        table = self._p(params, "table")
        data = self._p(params, "data", {})
        if not table or not data:
            return (0, None, ("ERR_PARAMS", "table and data required", 0))
        ph = self._placeholder()
        cols = ", ".join(data.keys())
        placeholders = ", ".join([ph] * len(data))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        return self._cmd_execute({"sql": sql, "args": list(data.values())})

    def _cmd_insert_many(self, params):
        table = self._p(params, "table")
        columns = self._p(params, "columns", [])
        rows = self._p(params, "rows", [])
        if not table or not columns or not rows:
            return (0, None, ("ERR_PARAMS", "table, columns, rows required", 0))
        ph = self._placeholder()
        cols = ", ".join(columns)
        placeholders = ", ".join([ph] * len(columns))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        cursor = self._cursor()
        if not cursor:
            return (0, None, ("ERR_NO_CONN", "no database connection", 0))
        try:
            cursor.executemany(sql, rows)
            if self.state["config"]["autocommit"]:
                self.state["conn"].commit()
            affected = cursor.rowcount
            self.state["stats"]["rows_affected"] += affected
            cursor.close()
            return (1, {"affected": affected, "inserted": len(rows)}, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            cursor.close()
            return (0, None, ("ERR_INSERT_MANY", str(e), 0))

    def _cmd_update(self, params):
        table = self._p(params, "table")
        data = self._p(params, "data", {})
        where = self._p(params, "where", {})
        if not table or not data:
            return (0, None, ("ERR_PARAMS", "table and data required", 0))
        ph = self._placeholder()
        set_clause = ", ".join([f"{k}={ph}" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause}"
        args = list(data.values())
        if where:
            where_clause = " AND ".join([f"{k}={ph}" for k in where.keys()])
            sql += f" WHERE {where_clause}"
            args.extend(where.values())
        return self._cmd_execute({"sql": sql, "args": args})

    def _cmd_delete(self, params):
        table = self._p(params, "table")
        where = self._p(params, "where", {})
        if not table:
            return (0, None, ("ERR_PARAMS", "table required", 0))
        ph = self._placeholder()
        sql = f"DELETE FROM {table}"
        args = []
        if where:
            where_clause = " AND ".join([f"{k}={ph}" for k in where.keys()])
            sql += f" WHERE {where_clause}"
            args = list(where.values())
        return self._cmd_execute({"sql": sql, "args": args})

    # ════════════════════════════════════════════
    # TRANSACTION
    # ════════════════════════════════════════════

    def _cmd_begin(self, params):
        if not self.state["conn"]:
            return (0, None, ("ERR_NO_CONN", "no connection", 0))
        if self.state["config"]["db_type"] == "mysql":
            self.state["conn"].start_transaction()
        else:
            self.state["conn"].execute("BEGIN")
        self.state["stats"]["transactions"] += 1
        return (1, {"transaction": "started"}, None)

    def _cmd_commit(self, params):
        if not self.state["conn"]:
            return (0, None, ("ERR_NO_CONN", "no connection", 0))
        self.state["conn"].commit()
        return (1, {"transaction": "committed"}, None)

    def _cmd_rollback(self, params):
        if not self.state["conn"]:
            return (0, None, ("ERR_NO_CONN", "no connection", 0))
        self.state["conn"].rollback()
        return (1, {"transaction": "rolled back"}, None)

    # ════════════════════════════════════════════
    # SCHEMA
    # ════════════════════════════════════════════

    def _cmd_init_schema(self, params):
        schema = self._p(params, "schema", [])
        if not schema:
            return (0, None, ("ERR_PARAMS", "schema (list of DDL statements) required", 0))
        cursor = self._cursor()
        if not cursor:
            return (0, None, ("ERR_NO_CONN", "no connection", 0))
        executed = 0
        errors = []
        for ddl in schema:
            try:
                cursor.execute(ddl)
                executed += 1
            except Exception as e:
                errors.append(str(e))
        if self.state["config"]["autocommit"]:
            self.state["conn"].commit()
        cursor.close()
        if errors and executed == 0:
            return (0, None, ("ERR_SCHEMA", errors[0], 0))
        return (1, {"executed": executed, "errors": errors}, None)

    def _cmd_table_exists(self, params):
        table = self._p(params, "table")
        if not table:
            return (0, None, ("ERR_PARAMS", "table required", 0))
        if self.state["config"]["db_type"] == "mysql":
            ok, rows, err = self._cmd_query({
                "sql": "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
                "args": [self.state["config"]["db_name"], table]
            })
        else:
            ok, rows, err = self._cmd_query({
                "sql": "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                "args": [table]
            })
        if not ok:
            return (0, None, err)
        return (1, len(rows) > 0, None)

    def _cmd_count(self, params):
        table = self._p(params, "table")
        where = self._p(params, "where", "")
        if not table:
            return (0, None, ("ERR_PARAMS", "table required", 0))
        sql = f"SELECT COUNT(*) as cnt FROM {table}"
        if where:
            sql += f" WHERE {where}"
        ok, row, err = self._cmd_query_one({"sql": sql})
        if not ok:
            return (0, None, err)
        return (1, row["cnt"] if row else 0, None)

    # ════════════════════════════════════════════
    # CYPHER (Neo4j only)
    # ════════════════════════════════════════════

    def _cmd_cypher(self, params):
        query = self._p(params, "query")
        args = self._p(params, "args", {})
        if not query:
            return (0, None, ("ERR_NO_QUERY", "params['query'] required", 0))
        if not HAS_NEO4J:
            return (0, None, ("ERR_NO_NEO4J", "neo4j driver not installed — pip install neo4j", 0))
        if not self.state["conn"]:
            self._connect()
        if not self.state["conn"]:
            return (0, None, ("ERR_NO_CONN", "neo4j connection failed — is the server running?", 0))
        try:
            with self.state["conn"].session() as session:
                result = session.run(query, args)
                records = []
                for record in result:
                    records.append(dict(record))
                self.state["stats"]["queries"] += 1
                return (1, records, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_CYPHER", str(e), 0))


# ════════════════════════════════════════════
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# ════════════════════════════════════════════

_db_instances = {}

def _get_db(db_type="sqlite", **kwargs):
    """Get or create a DatabaseManager instance."""
    key = f"{db_type}:{kwargs.get('db_name', kwargs.get('sqlite_path', 'default'))}"
    if key not in _db_instances:
        param = {"db_type": db_type}
        param.update(kwargs)
        _db_instances[key] = DatabaseManager(param=param)
    return _db_instances[key]

def db_query(db_type, sql, args=None, **kwargs):
    """One-shot query. Returns list of dict rows."""
    db = _get_db(db_type, **kwargs)
    ok, rows, err = db.Run("query", {"sql": sql, "args": args or []})
    return rows if ok else []

def db_execute(db_type, sql, args=None, **kwargs):
    """One-shot execute. Returns affected count."""
    db = _get_db(db_type, **kwargs)
    ok, data, err = db.Run("execute", {"sql": sql, "args": args or []})
    return data.get("affected", 0) if ok else 0

def db_insert(db_type, table, data, **kwargs):
    """One-shot insert. Returns last_id."""
    db = _get_db(db_type, **kwargs)
    ok, data_result, err = db.Run("insert", {"table": table, "data": data})
    return data_result.get("last_id") if ok else None
