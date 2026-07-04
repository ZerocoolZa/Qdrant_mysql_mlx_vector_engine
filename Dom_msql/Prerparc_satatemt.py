#[@GHOST]
#[@VBSTYLE]
#[@FILEID] Prerparc_satatemt.py
#[@SUMMARY] SQL registry pipeline — RegisterTable, CRUD backfill, knowledge, validation
#[@CLASS] SqlRegistryPipeline
#[@METHOD] Run
#[@DATE] 2026-07-04
#[@AUTHOR] Wayne / Cascade
#[@SESSION] CHECKPOINT-10
#[@CONTEXT] laws DB — dbRegistry, dbRegistryKnowledge, RegisterTable procedure

"""
PlfSqlRegistry — SQL Registry Pipeline CLI

Commands:
    register    Create + register a table with CRUD SQL and knowledge objects
    backfill    Generate CRUD SQL for existing tables missing it
    knowledge   Add/retrieve knowledge objects for any registered table
    list        List all registered tables and CRUD coverage
    validate    Run ValidateAllDatabaseLaws
    show        Show full registration record for a table
    drop        Drop a registered table
    stats       Show registry statistics
"""

import argparse
import sys
import pymysql

HOST = "localhost"
PORT = 3306
USER = "root"
PASSWORD = ""
DATABASE = "laws"

KNOWLEDGE_FIELDS = [
    ("INSTRUCTIONS",   "instructions",    "AI Instructions"),
    ("GRAPH",          "graph",           "Execution Graph"),
    ("BCL",            "bcl",             "BCL Definition"),
    ("BCLIR",          "bclir",           "BCLIR Node"),
    ("EXPLANATION",    "explanation",     "Explanation"),
    ("ALGORITHM",      "algorithm",       "Algorithm"),
    ("EXECUTIONPLAN",  "execution_plan",  "Execution Plan"),
    ("EXAMPLES",       "examples",        "Examples"),
    ("LAWS",           "laws",            "Laws Enforced"),
]


class SqlRegistryPipeline:
    """Pipeline for SQL prepared statement management via dbRegistry."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": dict(HOST=HOST, PORT=PORT, USER=USER,
                                     PASSWORD=PASSWORD, DATABASE=DATABASE),
                      "last_result": None, "last_error": None}
        if param:
            self.state["config"].update(param)
        self._conn = None

    def Run(self, command, params=None):
        """Dispatch: (1, data, None) on success, (0, None, (code, desc, 0)) on failure."""
        dispatch = {
            "register": self._register, "backfill": self._backfill,
            "knowledge_add": self._knowledge_add, "knowledge_get": self._knowledge_get,
            "list": self._list, "validate": self._validate,
            "show": self._show, "drop": self._drop, "stats": self._stats,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))
        return handler(params or {})

    def _p(self):
        return self.state

    def read_state(self):
        return self.state

    def set_config(self, config):
        self.state["config"].update(config)
        return (1, {"config": self.state["config"]}, None)

    def _db(self):
        """Lazy single connection, reused across calls."""
        if self._conn is None or not self._conn.open:
            c = self.state["config"]
            self._conn = pymysql.connect(host=c["HOST"], port=c["PORT"], user=c["USER"],
                                         password=c["PASSWORD"], database=c["DATABASE"],
                                         charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
        return self._conn

    def _q(self, sql, args=None, commit=False):
        """Execute a query, return rows. Auto-commit if requested."""
        cur = self._db().cursor()
        cur.execute(sql, args or ())
        rows = cur.fetchall()
        if commit:
            self._db().commit()
        cur.close()
        return rows

    def _sp(self, proc, args, commit=False):
        """Call a stored procedure, return rows."""
        cur = self._db().cursor()
        cur.callproc(proc, args)
        rows = cur.fetchall()
        if commit:
            self._db().commit()
        cur.close()
        return rows

    def _need(self, params, fields):
        """Validate required params. Returns error tuple or None."""
        for f in fields:
            if f not in params:
                return (0, None, ("MISSING_PARAM", f"Missing: {f}", 0))
        return None

    def _cols(self, table):
        """Return ordered column names for a table."""
        return [r["COLUMN_NAME"] for r in self._q("""
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION
        """, (DATABASE, table))]

    # ── register ──────────────────────────────────────────────

    def _register(self, params):
        err = self._need(params, ["table", "display", "purpose", "pk", "create_sql"])
        if err:
            return err
        try:
            result = self._sp("RegisterTable", [
                params.get("database", DATABASE), params["table"], params["display"],
                params["purpose"], params.get("description", ""), params["pk"],
                params["create_sql"], params.get("select_all_sql", ""),
                params.get("select_by_id_sql", ""), params.get("insert_sql", ""),
                params.get("update_sql", ""), params.get("delete_sql", ""),
            ], commit=True)
            if not result:
                return (0, None, ("REGISTER_NO_RESULT", "No result returned", 0))
            rid = result[0]["id"]
            kn_added = self._attach_knowledge(rid, params.get("knowledge", []))
            return (1, {"registry_id": rid, "knowledge_added": kn_added}, None)
        except pymysql.Error as e:
            return (0, None, ("REGISTER_FAILED", str(e), 0))

    def _attach_knowledge(self, registry_id, knowledge_objects):
        """Batch-attach knowledge objects. Returns count added."""
        count = 0
        for kn in knowledge_objects:
            if kn.get("type") and kn.get("content"):
                self._sp("AddRegistryKnowledge",
                         [registry_id, kn["type"], kn.get("title", ""), kn["content"]],
                         commit=True)
                count += 1
        return count

    # ── backfill ──────────────────────────────────────────────

    def _backfill(self, params):
        db = params.get("database", DATABASE)
        try:
            tables = self._q("""
                SELECT id, tableName, primaryKeyColumn FROM dbRegistry
                WHERE (createSQL IS NULL OR createSQL = '') AND isActive = 1 AND databaseName = %s
            """, (db,))
            for t in tables:
                name, pk, tid = t["tableName"], t["primaryKeyColumn"] or "id", t["id"]
                cols = self._cols(name)
                has_ia = "isActive" in cols
                non_auto = [c for c in cols if c not in ("id", "createdAt", "created")]
                set_cols = [c for c in non_auto if c != pk]
                create_sql = self._reconstruct_create(name)
                crud = (
                    create_sql,
                    f"SELECT * FROM {name}" + (" WHERE isActive = 1" if has_ia else ""),
                    f"SELECT * FROM {name} WHERE {pk} = %s",
                    f"INSERT INTO {name} ({', '.join(non_auto)}) VALUES ({', '.join(['%s']*len(non_auto))})",
                    f"UPDATE {name} SET {', '.join(f'{c} = %s' for c in set_cols)} WHERE {pk} = %s",
                    f"DELETE FROM {name} WHERE {pk} = %s",
                )
                self._q("""UPDATE dbRegistry SET createSQL=%s, selectAllSQL=%s, selectByIdSQL=%s,
                          insertSQL=%s, updateSQL=%s, deleteSQL=%s, version=version+1 WHERE id=%s""",
                        crud + (tid,), commit=True)
            return (1, {"backfilled": len(tables)}, None)
        except pymysql.Error as e:
            return (0, None, ("BACKFILL_FAILED", str(e), 0))

    def _reconstruct_create(self, table):
        """Reconstruct CREATE TABLE from information_schema."""
        col_rows = self._q("""
            SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, EXTRA, COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION
        """, (DATABASE, table))
        fk_rows = self._q("""
            SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL
        """, (DATABASE, table))
        defs = []
        for c in col_rows:
            d = f"  {c['COLUMN_NAME']} {c['COLUMN_TYPE']}"
            d += " NOT NULL" if c["IS_NULLABLE"] == "NO" else " DEFAULT NULL"
            if c.get("EXTRA") and "auto_increment" in c["EXTRA"]:
                d += " AUTO_INCREMENT"
            if c["COLUMN_KEY"] == "PRI":
                d += " PRIMARY KEY"
            defs.append(d)
        for fk in fk_rows:
            defs.append(f"  CONSTRAINT fk_{table}_{fk['COLUMN_NAME']} "
                        f"FOREIGN KEY ({fk['COLUMN_NAME']}) "
                        f"REFERENCES {fk['REFERENCED_TABLE_NAME']}({fk['REFERENCED_COLUMN_NAME']})")
        return f"CREATE TABLE {table} (\n" + ",\n".join(defs) + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"

    # ── knowledge ─────────────────────────────────────────────

    def _knowledge_add(self, params):
        err = self._need(params, ["registry_id", "type", "content"])
        if err:
            return err
        try:
            r = self._sp("AddRegistryKnowledge",
                         [params["registry_id"], params["type"],
                          params.get("title", ""), params["content"]], commit=True)
            return (1, {"knowledge": r}, None)
        except pymysql.Error as e:
            return (0, None, ("KNOWLEDGE_ADD_FAILED", str(e), 0))

    def _knowledge_get(self, params):
        err = self._need(params, ["registry_id", "type"])
        if err:
            return err
        try:
            r = self._sp("GetRegistryKnowledge", [params["registry_id"], params["type"]])
            return (1, {"knowledge": r}, None)
        except pymysql.Error as e:
            return (0, None, ("KNOWLEDGE_GET_FAILED", str(e), 0))

    # ── list / show / drop / validate / stats ─────────────────

    def _list(self, params):
        try:
            rows = self._q("""
                SELECT id, tableName, displayName,
                       createSQL IS NOT NULL AND createSQL != '' as has_create,
                       insertSQL IS NOT NULL AND insertSQL != '' as has_insert,
                       updateSQL IS NOT NULL AND updateSQL != '' as has_update,
                       deleteSQL IS NOT NULL AND deleteSQL != '' as has_delete,
                       version, isActive
                FROM dbRegistry WHERE databaseName = %s ORDER BY id
            """, (params.get("database", DATABASE),))
            return (1, {"tables": rows}, None)
        except pymysql.Error as e:
            return (0, None, ("LIST_FAILED", str(e), 0))

    def _show(self, params):
        err = self._need(params, ["table"])
        if err:
            return err
        try:
            r = self._q("SELECT * FROM dbRegistry WHERE databaseName=%s AND tableName=%s",
                        (params.get("database", DATABASE), params["table"]))
            if not r:
                return (0, None, ("NOT_FOUND", f"Table {params['table']} not registered", 0))
            return (1, {"record": r[0]}, None)
        except pymysql.Error as e:
            return (0, None, ("SHOW_FAILED", str(e), 0))

    def _drop(self, params):
        err = self._need(params, ["table"])
        if err:
            return err
        try:
            r = self._sp("DropRegisteredTable",
                         [params.get("database", DATABASE), params["table"]], commit=True)
            return (1, {"dropped": r}, None)
        except pymysql.Error as e:
            return (0, None, ("DROP_FAILED", str(e), 0))

    def _validate(self, params):
        try:
            r = self._sp("ValidateAllDatabaseLaws", [params.get("database", DATABASE)])
            return (1, {"violations": r}, None)
        except pymysql.Error as e:
            return (0, None, ("VALIDATE_FAILED", str(e), 0))

    def _stats(self, params):
        db = params.get("database", DATABASE)
        try:
            s = self._q("""
                SELECT COUNT(*) as total, SUM(isActive=1) as active,
                       SUM(createSQL IS NOT NULL AND createSQL!='') as has_create,
                       SUM(insertSQL IS NOT NULL AND insertSQL!='') as has_insert,
                       SUM(updateSQL IS NOT NULL AND updateSQL!='') as has_update,
                       SUM(deleteSQL IS NOT NULL AND deleteSQL!='') as has_delete
                FROM dbRegistry WHERE databaseName=%s
            """, (db,))[0]
            s["knowledge_objects"] = self._q("SELECT COUNT(*) as c FROM dbRegistryKnowledge")[0]["c"]
            return (1, {"stats": s}, None)
        except pymysql.Error as e:
            return (0, None, ("STATS_FAILED", str(e), 0))

    def close(self):
        if self._conn and self._conn.open:
            self._conn.close()


# ── CLI ────────────────────────────────────────────────────────

def _print_rows(rows, cols=None):
    if not rows:
        print("  (empty)")
        return
    cols = cols or list(rows[0].keys())
    w = {c: max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    fmt = "  " + "  ".join(f"{{{c}:<{w[c]}}}" for c in cols)
    print(fmt.format(**{c: c for c in cols}))
    print("  " + "-" * (sum(w.values()) + 2 * (len(cols) - 1)))
    for r in rows:
        print(fmt.format(**{c: str(r.get(c, "")) for c in cols}))


def main():
    p = argparse.ArgumentParser(description="PlfSqlRegistry — SQL Registry Pipeline CLI")
    sub = p.add_subparsers(dest="command")

    # register
    pr = sub.add_parser("register")
    pr.add_argument("--db", default=DATABASE)
    pr.add_argument("--table", required=True)
    pr.add_argument("--display", required=True)
    pr.add_argument("--purpose", required=True)
    pr.add_argument("--description", default="")
    pr.add_argument("--pk", default="id")
    pr.add_argument("--create-sql", required=True)
    for flag in ("select-all-sql", "select-by-id-sql", "insert-sql", "update-sql", "delete-sql"):
        pr.add_argument(f"--{flag}", default="")
    for kn_type, kn_flag, kn_title in KNOWLEDGE_FIELDS:
        pr.add_argument(f"--{kn_flag.replace('_', '-')}", default="", help=kn_title)

    # simple --db commands
    for cmd in ("backfill", "list", "validate", "stats"):
        sp = sub.add_parser(cmd)
        sp.add_argument("--db", default=DATABASE)

    # knowledge
    pk = sub.add_parser("knowledge")
    pk.add_argument("--registry-id", type=int, required=True)
    pk.add_argument("--type", required=True)
    pk.add_argument("--title", default="")
    pk.add_argument("--content", default="")
    pk.add_argument("--get", action="store_true")

    # show / drop
    for cmd in ("show", "drop"):
        sp = sub.add_parser(cmd)
        sp.add_argument("--db", default=DATABASE)
        sp.add_argument("--table", required=True)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(1)

    pipe = SqlRegistryPipeline()

    if args.command == "register":
        knowledge = [{"type": t, "title": title, "content": getattr(args, f.replace("-", "_"))}
                     for t, f, title in KNOWLEDGE_FIELDS if getattr(args, f.replace("-", "_"))]
        ok, data, err = pipe.Run("register", {
            "database": args.db, "table": args.table, "display": args.display,
            "purpose": args.purpose, "description": args.description, "pk": args.pk,
            "create_sql": args.create_sql, "select_all_sql": args.select_all_sql,
            "select_by_id_sql": args.select_by_id_sql, "insert_sql": args.insert_sql,
            "update_sql": args.update_sql, "delete_sql": args.delete_sql,
            "knowledge": knowledge,
        })
    elif args.command == "knowledge":
        cmd = "knowledge_get" if args.get else "knowledge_add"
        ok, data, err = pipe.Run(cmd, {"registry_id": args.registry_id, "type": args.type,
                                       "title": args.title, "content": args.content})
    else:
        ok, data, err = pipe.Run(args.command, {"database": args.db,
                                                 "table": getattr(args, "table", None)})

    pipe.close()

    if not ok:
        print(f"  ERROR: {err[1]}")
        sys.exit(1)

    out = {
        "list": lambda: _print_rows(data["tables"], ["id", "tableName", "displayName", "has_create", "has_insert", "has_update", "has_delete", "version"]),
        "stats": lambda: print(f"  Total: {data['stats']['total']}  Active: {data['stats']['active']}  Knowledge: {data['stats']['knowledge_objects']}\n  CRUD: create={data['stats']['has_create']}  insert={data['stats']['has_insert']}  update={data['stats']['has_update']}  delete={data['stats']['has_delete']}"),
        "validate": lambda: _print_rows(data["violations"], ["violation"]) if data["violations"] else print("  No violations."),
        "backfill": lambda: print(f"  Backfilled: {data['backfilled']}"),
        "register": lambda: print(f"  Registered: id={data['registry_id']}  Knowledge: {data['knowledge_added']}"),
        "knowledge": lambda: _print_rows(data["knowledge"], ["id", "registryId", "knowledgeType", "title", "version"]) if isinstance(data.get("knowledge"), list) else print(f"  Added: {data}"),
        "show": lambda: [print(f"  {k}: {str(v)[:77]}...") if v and len(str(v)) > 80 else print(f"  {k}: {v}") for k, v in data["record"].items()],
    }
    out.get(args.command, lambda: print(f"  OK: {data}"))()


if __name__ == "__main__":
    main()
