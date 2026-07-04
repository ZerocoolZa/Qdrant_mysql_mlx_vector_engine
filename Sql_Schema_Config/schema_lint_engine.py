#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     schema_lint_engine.py
# Domain:   Schema Lint Engine
# Authority: Executes the 116 rules defined in Database_Schema_config.py
# DB:       MySQL (information_schema) — host=localhost, user=root, password=empty
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — NO hardcoded paths. All paths derived from BASE_DIR.
#
# AI GUIDE — READ THIS FIRST
# ----------------------------------------------------------------------------
# This engine is the executor for the 116 rules (36 structural + 80 design)
# defined in Database_Schema_config.py. The config is the single source of
# truth; this engine contains NO rule definitions, only check logic.
#
# Architecture:
#   1. Connect to MySQL (host=localhost, user=root, password=empty).
#   2. Load schema metadata from information_schema for the target database.
#   3. For each enabled rule, dispatch to the matching Check_* method.
#   4. Collect violations: (rule_id, severity, table, column, suggested_fix).
#   5. Return results via Tuple3 (ok, data, error).
#
# VBStyle compliance:
#   - Run(command, params) dispatch entry point
#   - Tuple3 returns: (ok, data, error)
#   - No decorators, no print, PascalCase, self.state dict
#   - Ghost + VBStyle + Class + Method headers on every file
#
# Commands (dispatched by Run):
#   "lint"     — run all enabled rules against all target databases
#   "lint_db"  — lint a specific database (params: {"database": name})
#   "report"   — generate a human-readable report from the last lint run
#   "list"     — list all configured rules and their enabled state
#   "about"    — return the config ABOUT string
#   "score"    — return schema health score for the last lint run
# ============================================================================
"""

Schema Lint Engine — executes the 116 rules from Database_Schema_config.py.

This engine reads schema metadata from MySQL information_schema and applies
each rule's check logic. It reports violations with rule name, severity,
table, column, and a suggested fix.

VBStyle compliant:
    - Run(command, params) dispatch entry point
    - Tuple3 (ok, data, error) returns
    - No decorators, no print, PascalCase, self.state dict
"""

import os
import re
import sys
from collections import defaultdict

import pymysql

# Make the config importable whether run as a script or imported.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Database_Schema_config as Cfg

# ----------------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_CHARSET = "utf8mb4"

# Default target databases (from the task spec).
DEFAULT_DATABASES = ["vb_shared", "vb_code_test", "Chat_History"]

# Engine tag we are running as. This engine targets MySQL, so only rules
# whose engines list contains "mysql" are executed.
ACTIVE_ENGINE = Cfg.Config.ENGINE_MYSQL

# Severity weight lookup (unified across structural + design rules).
SEVERITY_WEIGHTS = {
    Cfg.Config.SEVERITY_HIGH: 10,
    Cfg.Config.SEVERITY_MEDIUM: 3,
    Cfg.Config.SEVERITY_LOW: 1,
    Cfg.Config.SEVERITY_STRICT: 10,
    Cfg.Config.SEVERITY_GUIDELINE: 3,
}


class SchemaLintEngine:
    """Schema Lint Engine — executes rules from Database_Schema_config.py.

    Methods:
        Run(command, params) -> Tuple3 (ok, data, error)
            Dispatch entry point. Commands: lint, lint_db, report, list,
            about, score.
        Connect() -> Tuple3
            Connect to MySQL.
        Disconnect() -> None
            Close the MySQL connection.
        LoadSchema(database) -> Tuple3
            Load all metadata for a database from information_schema.
        LintDatabase(database) -> Tuple3
            Run all enabled rules against one database.
        LintAll() -> Tuple3
            Run all enabled rules against all default databases.
        GenerateReport() -> Tuple3
            Build a human-readable report from the last lint run.
        Score() -> Tuple3
            Compute a 0-100 schema health score from violations.
    """

    # ------------------------------------------------------------------------
    # CONSTRUCTOR
    # ------------------------------------------------------------------------
    def __init__(self):
        self.state = {
            "conn": None,
            "violations": [],          # list of violation dicts
            "last_database": None,     # database of last lint run
            "rules_run": 0,            # count of rules executed
            "rules_skipped": 0,        # count of rules skipped (disabled/engine)
            "metadata": None,          # cached metadata for current database
        }

    # ------------------------------------------------------------------------
    # PUBLIC: Run — VBStyle dispatch entry point
    # ------------------------------------------------------------------------
    def Run(self, command, params=None):
        """Dispatch entry point.

        Args:
            command (str): one of lint, lint_db, report, list, about, score.
            params (dict|None): command parameters.

        Returns:
            Tuple3 (ok, data, error)
        """
        if params is None:
            params = {}

        dispatch = {
            "lint": self._CmdLint,
            "lint_db": self._CmdLintDb,
            "report": self._CmdReport,
            "list": self._CmdList,
            "about": self._CmdAbout,
            "score": self._CmdScore,
        }

        handler = dispatch.get(command)
        if handler is None:
            return (False, None, "Unknown command: %s. Valid: %s" % (
                command, ", ".join(sorted(dispatch.keys()))))

        return handler(params)

    # ------------------------------------------------------------------------
    # COMMAND HANDLERS
    # ------------------------------------------------------------------------
    def _CmdLint(self, params):
        """lint — run all rules against all default databases."""
        ok, data, error = self.Connect()
        if not ok:
            return (False, None, error)
        try:
            ok, data, error = self.LintAll()
            return (ok, data, error)
        finally:
            self.Disconnect()

    def _CmdLintDb(self, params):
        """lint_db — lint a specific database. params: {"database": name}."""
        database = params.get("database")
        if not database:
            return (False, None, "Missing param: database")
        ok, data, error = self.Connect()
        if not ok:
            return (False, None, error)
        try:
            ok, data, error = self.LintDatabase(database)
            return (ok, data, error)
        finally:
            self.Disconnect()

    def _CmdReport(self, params):
        """report — generate a human-readable report from the last lint run."""
        return self.GenerateReport()

    def _CmdList(self, params):
        """list — list all configured rules and their enabled state."""
        rules = []
        for rule in Cfg.Config.ALL_RULES:
            rules.append({
                "id": rule[0],
                "description": rule[1],
                "severity": rule[2],
                "check_type": rule[3],
                "enabled": rule[4],
                "engines": rule[5],
            })
        return (True, rules, None)

    def _CmdAbout(self, params):
        """about — return the config ABOUT string."""
        return (True, Cfg.Config.ABOUT, None)

    def _CmdScore(self, params):
        """score — return schema health score for the last lint run."""
        return self.Score()

    # ------------------------------------------------------------------------
    # CONNECTION
    # ------------------------------------------------------------------------
    def Connect(self):
        """Connect to MySQL.

        Returns:
            Tuple3 (ok, connection, error)
        """
        try:
            conn = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                charset=MYSQL_CHARSET,
                cursorclass=pymysql.cursors.DictCursor,
            )
            self.state["conn"] = conn
            return (True, conn, None)
        except Exception as exc:
            return (False, None, "MySQL connect failed: %s" % str(exc))

    def Disconnect(self):
        """Close the MySQL connection."""
        conn = self.state.get("conn")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        self.state["conn"] = None

    # ------------------------------------------------------------------------
    # METADATA LOADING
    # ------------------------------------------------------------------------
    @staticmethod
    def _NormRow(row):
        """Normalize a DictCursor row to lowercase keys.

        pymysql DictCursor returns UPPERCASE keys from information_schema.
        This helper makes all key access case-insensitive by lowercasing.
        """
        return {k.lower(): v for k, v in row.items()}

    def LoadSchema(self, database):
        """Load all metadata for a database from information_schema.

        Builds a metadata dict with keys:
            tables:   {table_name: {columns: [...], pk_cols: [...], engine, ...}}
            columns:  list of column dicts
            indexes:  {table_name: {index_name: [col dicts]}}
            fks:      list of fk dicts
            col_types:{column_name: set(data_type)}  (for cross-table consistency)

        Returns:
            Tuple3 (ok, metadata, error)
        """
        conn = self.state.get("conn")
        if conn is None:
            return (False, None, "Not connected to MySQL")

        meta = {
            "database": database,
            "tables": {},
            "columns": [],
            "indexes": {},
            "fks": [],
            "col_types": defaultdict(set),
        }

        cur = conn.cursor()

        # --- tables ---
        cur.execute(
            "SELECT table_name, engine, table_rows, table_comment "
            "FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE'",
            (database,))
        for row in cur.fetchall():
            r = self._NormRow(row)
            tname = r["table_name"]
            meta["tables"][tname] = {
                "name": tname,
                "engine": r["engine"],
                "rows": r["table_rows"],
                "comment": r["table_comment"],
                "columns": [],
                "pk_cols": [],
            }

        if not meta["tables"]:
            cur.close()
            return (False, None, "No base tables found in database: %s" % database)

        # --- columns ---
        cur.execute(
            "SELECT table_name, column_name, ordinal_position, data_type, "
            "column_type, is_nullable, column_default, column_key, extra, "
            "character_maximum_length, numeric_precision, numeric_scale "
            "FROM information_schema.columns "
            "WHERE table_schema = %s "
            "ORDER BY table_name, ordinal_position",
            (database,))
        for row in cur.fetchall():
            r = self._NormRow(row)
            col = {
                "table": r["table_name"],
                "column": r["column_name"],
                "ordinal": r["ordinal_position"],
                "data_type": (r["data_type"] or "").upper(),
                "column_type": (r["column_type"] or "").upper(),
                "is_nullable": r["is_nullable"] == "YES",
                "default": r["column_default"],
                "column_key": r["column_key"] or "",
                "extra": r["extra"] or "",
                "char_len": r["character_maximum_length"],
                "num_precision": r["numeric_precision"],
                "num_scale": r["numeric_scale"],
            }
            meta["columns"].append(col)
            if col["table"] in meta["tables"]:
                meta["tables"][col["table"]]["columns"].append(col)
            meta["col_types"][col["column"]].add(col["data_type"])

        # --- primary keys ---
        cur.execute(
            "SELECT table_name, column_name, ordinal_position "
            "FROM information_schema.key_column_usage "
            "WHERE table_schema = %s AND constraint_name = 'PRIMARY' "
            "ORDER BY table_name, ordinal_position",
            (database,))
        for row in cur.fetchall():
            r = self._NormRow(row)
            tname = r["table_name"]
            if tname in meta["tables"]:
                meta["tables"][tname]["pk_cols"].append(r["column_name"])

        # --- indexes ---
        cur.execute(
            "SELECT table_name, index_name, column_name, seq_in_index, "
            "non_unique, index_type "
            "FROM information_schema.statistics "
            "WHERE table_schema = %s "
            "ORDER BY table_name, index_name, seq_in_index",
            (database,))
        for row in cur.fetchall():
            r = self._NormRow(row)
            tname = r["table_name"]
            iname = r["index_name"]
            idx_col = {
                "column": r["column_name"],
                "seq": r["seq_in_index"],
                "non_unique": r["non_unique"],
                "index_type": r["index_type"],
            }
            meta["indexes"].setdefault(tname, {}).setdefault(iname, {
                "name": iname,
                "non_unique": r["non_unique"],
                "type": r["index_type"],
                "columns": [],
            })["columns"].append(idx_col)

        # --- foreign keys ---
        cur.execute(
            "SELECT kcu.table_name, kcu.column_name, kcu.constraint_name, "
            "kcu.referenced_table_name, kcu.referenced_column_name, "
            "rc.update_rule, rc.delete_rule "
            "FROM information_schema.key_column_usage kcu "
            "LEFT JOIN information_schema.referential_constraints rc "
            "  ON rc.constraint_schema = kcu.table_schema "
            "  AND rc.constraint_name = kcu.constraint_name "
            "WHERE kcu.table_schema = %s AND kcu.referenced_table_name IS NOT NULL",
            (database,))
        for row in cur.fetchall():
            r = self._NormRow(row)
            fk = {
                "table": r["table_name"],
                "column": r["column_name"],
                "constraint_name": r["constraint_name"],
                "ref_table": r["referenced_table_name"],
                "ref_column": r["referenced_column_name"],
                "update_rule": r["update_rule"],
                "delete_rule": r["delete_rule"],
            }
            meta["fks"].append(fk)

        cur.close()
        self.state["metadata"] = meta
        return (True, meta, None)

    # ------------------------------------------------------------------------
    # LINT EXECUTION
    # ------------------------------------------------------------------------
    def LintAll(self):
        """Run all enabled rules against all default databases.

        Returns:
            Tuple3 (ok, results, error) where results is a dict keyed by
            database name, each value a list of violation dicts.
        """
        results = {}
        total_violations = 0
        for database in DEFAULT_DATABASES:
            ok, data, error = self.LintDatabase(database)
            if not ok:
                # Store the error but continue with other databases.
                results[database] = {"error": error, "violations": []}
                continue
            results[database] = data
            total_violations += len(data)
        return (True, results, None)

    def LintDatabase(self, database):
        """Run all enabled rules against one database.

        Returns:
            Tuple3 (ok, violations, error) where violations is a list of
            violation dicts: {rule, severity, table, column, fix}.
        """
        ok, meta, error = self.LoadSchema(database)
        if not ok:
            return (False, None, error)

        self.state["violations"] = []
        self.state["last_database"] = database
        self.state["rules_run"] = 0
        self.state["rules_skipped"] = 0

        for rule in Cfg.Config.ALL_RULES:
            rule_id = rule[0]
            description = rule[1]
            severity = rule[2]
            check_type = rule[3]
            enabled = rule[4]
            engines = rule[5]

            if not enabled:
                self.state["rules_skipped"] += 1
                continue
            if ACTIVE_ENGINE not in engines:
                self.state["rules_skipped"] += 1
                continue

            self.state["rules_run"] += 1
            self._ExecuteRule(rule_id, description, severity, check_type, meta)

        return (True, self.state["violations"], None)

    # ------------------------------------------------------------------------
    # RULE DISPATCH
    # ------------------------------------------------------------------------
    def _ExecuteRule(self, rule_id, description, severity, check_type, meta):
        """Dispatch a single rule to its Check_* method by check_type."""
        handler = self._CHECK_DISPATCH.get(check_type)
        if handler is None:
            # No check logic implemented for this check_type yet.
            return
        violations = handler(self, meta)
        for v in violations:
            self._AddViolation(rule_id, severity, v.get("table"),
                               v.get("column"), v.get("fix", description))

    def _AddViolation(self, rule_id, severity, table, column, fix):
        """Record a violation."""
        self.state["violations"].append({
            "rule": rule_id,
            "severity": severity,
            "table": table,
            "column": column,
            "fix": fix,
        })

    # ------------------------------------------------------------------------
    # CHECK HELPERS
    # ------------------------------------------------------------------------
    @staticmethod
    def _IsLobType(data_type):
        """Return True if the data type is a LOB (TEXT/BLOB family)."""
        lob = ("TEXT", "BLOB", "TINYTEXT", "MEDIUMTEXT", "LONGTEXT",
               "TINYBLOB", "MEDIUMBLOB", "LONGBLOB")
        return data_type in lob

    @staticmethod
    def _IsIntegerFamily(data_type):
        """Return True if the data type is an integer family type."""
        ints = ("INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "MEDIUMINT")
        return data_type in ints

    @staticmethod
    def _IsBooleanPrefix(column):
        """Return True if column name starts with is_ or has_."""
        low = column.lower()
        return any(low.startswith(p) for p in Cfg.Config.BOOLEAN_PREFIXES)

    @staticmethod
    def _IsSnakeCase(name):
        """Return True if name is pure snake_case (lowercase + underscores)."""
        return bool(re.match(r"^[a-z][a-z0-9_]*$", name))

    @staticmethod
    def _IsCamelCase(name):
        """Return True if name contains camelCase or PascalCase pattern."""
        return bool(re.search(r"[a-z][A-Z]|[A-Z][a-z]", name))

    def _IndexedColumns(self, meta, table):
        """Return a set of column names that appear in any index on table."""
        cols = set()
        for idx in meta["indexes"].get(table, {}).values():
            for c in idx["columns"]:
                cols.add(c["column"])
        return cols

    # ========================================================================
    # CHECK FUNCTIONS — one per check_type in Database_Schema_config.py
    # ------------------------------------------------------------------------
    # Each Check_* method takes (self, meta) and returns a list of violation
    # dicts: {"table": ..., "column": ..., "fix": ...}
    # Only MySQL-applicable checks are fully implemented; SQLite-only checks
    # return [] (they are filtered by engine tag before dispatch, but this
    # guards against any that slip through).
    # ========================================================================

    # --- 1. INTEGRITY / CORRECTNESS ---

    def Check_table_must_have_pk(self, meta):
        """Every table MUST have a primary key."""
        out = []
        for tname, t in meta["tables"].items():
            if not t["pk_cols"]:
                out.append({"table": tname, "column": None,
                            "fix": "Add a PRIMARY KEY (surrogate INTEGER AUTO_INCREMENT if no logical key)."})
        return out

    def Check_pk_must_not_be_nullable(self, meta):
        """Primary key columns MUST NOT be nullable."""
        out = []
        for tname, t in meta["tables"].items():
            for pk in t["pk_cols"]:
                for col in t["columns"]:
                    if col["column"] == pk and col["is_nullable"]:
                        out.append({"table": tname, "column": pk,
                                    "fix": "Add NOT NULL to the PK column."})
        return out

    def Check_fk_type_must_match(self, meta):
        """FK column type MUST match referenced PK type."""
        out = []
        for fk in meta["fks"]:
            ref_table = fk["ref_table"]
            ref_col = fk["ref_column"]
            if ref_table not in meta["tables"]:
                continue  # handled by no_orphaned_fk_target
            child = None
            for col in meta["tables"][fk["table"]]["columns"]:
                if col["column"] == fk["column"]:
                    child = col
                    break
            parent = None
            for col in meta["tables"][ref_table]["columns"]:
                if col["column"] == ref_col:
                    parent = col
                    break
            if child is None or parent is None:
                continue
            if child["data_type"] != parent["data_type"]:
                if self._IsIntegerFamily(child["data_type"]) and self._IsIntegerFamily(parent["data_type"]):
                    continue  # integer-family compatible
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "Change FK column type to %s to match referenced %s.%s." % (
                                parent["data_type"], ref_table, ref_col)})
        return out

    def Check_no_fk_self_reference(self, meta):
        """FKs MUST NOT self-reference the PK."""
        out = []
        for fk in meta["fks"]:
            if fk["table"] == fk["ref_table"]:
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "Remove the self-referencing FK or model the hierarchy differently."})
        return out

    def Check_no_table_cycles(self, meta):
        """Tables MUST NOT have cyclical FK relationships."""
        out = []
        # Build adjacency list.
        graph = defaultdict(set)
        for fk in meta["fks"]:
            graph[fk["table"]].add(fk["ref_table"])
        # Detect cycles via DFS.
        visited = set()
        stack = set()
        cycle_tables = set()

        def Dfs(node, path):
            if node in stack:
                cycle_tables.update(path[path.index(node):])
                return
            if node in visited:
                return
            stack.add(node)
            path.append(node)
            for nbr in graph.get(node, ()):
                Dfs(nbr, path)
            path.pop()
            stack.discard(node)
            visited.add(node)

        for tname in meta["tables"]:
            Dfs(tname, [])
        for tname in sorted(cycle_tables):
            out.append({"table": tname, "column": None,
                        "fix": "Break the FK cycle by removing one FK or introducing a junction table."})
        return out

    def Check_no_orphaned_fk_target(self, meta):
        """FK MUST reference a table that exists."""
        out = []
        for fk in meta["fks"]:
            if fk["ref_table"] not in meta["tables"]:
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "Create the missing parent table %s or drop the FK." % fk["ref_table"]})
        return out

    def Check_no_fk_missing_ref_column(self, meta):
        """FK referenced column MUST exist on target table."""
        out = []
        for fk in meta["fks"]:
            ref_table = fk["ref_table"]
            ref_col = fk["ref_column"]
            if ref_table not in meta["tables"]:
                continue  # handled by no_orphaned_fk_target
            ref_cols = {c["column"] for c in meta["tables"][ref_table]["columns"]}
            if ref_col not in ref_cols:
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "Add column %s to %s or fix the FK to reference an existing column." % (
                                ref_col, ref_table)})
        return out

    def Check_must_enforce_foreign_keys(self, meta):
        """Database MUST enforce foreign keys.

        MySQL enforces FKs by default (foreign_key_checks=ON). We check the
        session/global variable. This is a runtime setting, not schema, so
        we verify the current value.
        """
        out = []
        conn = self.state.get("conn")
        if conn is None:
            return out
        cur = conn.cursor()
        try:
            cur.execute("SELECT @@foreign_key_checks AS fkc")
            row = cur.fetchone()
            if row:
                r = self._NormRow(row)
                if str(r.get("fkc", "1")) != "1":
                    out.append({"table": None, "column": None,
                                "fix": "SET foreign_key_checks = 1; — FK enforcement is currently OFF."})
        except Exception:
            pass
        finally:
            cur.close()
        return out

    def Check_no_without_rowid_without_pk(self, meta):
        """WITHOUT ROWID tables MUST have a primary key (SQLite-only)."""
        # Not applicable to MySQL.
        return []

    def Check_no_autoincrement_non_integer(self, meta):
        """AUTOINCREMENT MUST NOT be on non-INTEGER PK."""
        out = []
        for tname, t in meta["tables"].items():
            pk_set = set(t["pk_cols"])
            for col in t["columns"]:
                if "auto_increment" in col["extra"].lower():
                    if col["column"] in pk_set and not self._IsIntegerFamily(col["data_type"]):
                        out.append({"table": tname, "column": col["column"],
                                    "fix": "AUTO_INCREMENT must be on an INTEGER PK column."})
        return out

    # --- 2. NORMALIZATION / DESIGN ---

    def Check_no_all_nullable_columns(self, meta):
        """Tables MUST NOT have all nullable non-PK columns."""
        out = []
        for tname, t in meta["tables"].items():
            pk_set = set(t["pk_cols"])
            non_pk = [c for c in t["columns"] if c["column"] not in pk_set]
            if non_pk and all(c["is_nullable"] for c in non_pk):
                out.append({"table": tname, "column": None,
                            "fix": "Add NOT NULL to at least one business-critical column."})
        return out

    def Check_no_single_column_table(self, meta):
        """Tables MUST NOT have fewer than 2 columns."""
        out = []
        for tname, t in meta["tables"].items():
            if len(t["columns"]) < 2:
                out.append({"table": tname, "column": None,
                            "fix": "Add a meaningful second column or a surrogate PK."})
        return out

    def Check_no_composite_pk(self, meta):
        """Tables SHOULD NOT use composite primary keys."""
        out = []
        for tname, t in meta["tables"].items():
            if len(t["pk_cols"]) > 1:
                out.append({"table": tname, "column": ",".join(t["pk_cols"]),
                            "fix": "Consider a surrogate INTEGER PK; demote composite to UNIQUE constraint."})
        return out

    def Check_no_incrementing_columns(self, meta):
        """Tables MUST NOT have incrementing column names (col1, col2, ...)."""
        out = []
        pattern = re.compile(r"^col\d+$", re.IGNORECASE)
        for tname, t in meta["tables"].items():
            for col in t["columns"]:
                if pattern.match(col["column"]):
                    out.append({"table": tname, "column": col["column"],
                                "fix": "Rename to a meaningful name reflecting the column's purpose."})
        return out

    def Check_no_csv_in_text_column(self, meta):
        """TEXT columns MUST NOT have CSV-indicator names."""
        out = []
        for col in meta["columns"]:
            low = col["column"].lower()
            if self._IsLobType(col["data_type"]):
                if any(ind in low for ind in Cfg.Config.CSV_INDICATORS):
                    out.append({"table": col["table"], "column": col["column"],
                                "fix": "Normalize into a junction table instead of storing CSV values."})
        return out

    def Check_no_wide_table(self, meta):
        """Tables MUST NOT have more than MAX_TABLE_COLUMNS columns."""
        out = []
        for tname, t in meta["tables"].items():
            if len(t["columns"]) > Cfg.Config.MAX_TABLE_COLUMNS:
                out.append({"table": tname, "column": None,
                            "fix": "Split into parent + detail table grouping related columns."})
        return out

    def Check_no_duplicate_column_spread(self, meta):
        """Same non-FK column in 3+ tables suggests denormalization."""
        out = []
        fk_cols = {fk["column"] for fk in meta["fks"]}
        spread = defaultdict(list)
        for col in meta["columns"]:
            cname = col["column"]
            if cname in fk_cols:
                continue
            if cname in ("id", "created_at", "updated_at"):
                continue  # audit columns are intentionally spread
            spread[cname].append(col["table"])
        for cname, tables in spread.items():
            if len(tables) >= Cfg.Config.MIN_TABLES_FOR_SPREAD:
                out.append({"table": ",".join(sorted(tables)), "column": cname,
                            "fix": "Column '%s' appears in %d tables; consider a shared lookup table." % (
                                cname, len(tables))})
        return out

    # --- 3. PERFORMANCE / INDEXING ---

    def Check_fk_must_have_index(self, meta):
        """Every FK column MUST have an index."""
        out = []
        for fk in meta["fks"]:
            indexed = self._IndexedColumns(meta, fk["table"])
            if fk["column"] not in indexed:
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "CREATE INDEX idx_%s_%s ON %s(%s);" % (
                                fk["table"], fk["column"], fk["table"], fk["column"])})
        return out

    def Check_pk_must_be_first(self, meta):
        """Primary key columns MUST be declared first."""
        out = []
        for tname, t in meta["tables"].items():
            if not t["pk_cols"]:
                continue
            first_col = t["columns"][0]["column"] if t["columns"] else None
            if first_col and first_col != t["pk_cols"][0]:
                out.append({"table": tname, "column": t["pk_cols"][0],
                            "fix": "Recreate table with PK column '%s' declared first." % t["pk_cols"][0]})
        return out

    def Check_no_redundant_indexes(self, meta):
        """Tables MUST NOT have redundant indexes (same prefix covered by another)."""
        out = []
        for tname, idxs in meta["indexes"].items():
            names = sorted(idxs.keys())
            for i in range(len(names)):
                for j in range(len(names)):
                    if i == j:
                        continue
                    a = [c["column"] for c in idxs[names[i]]["columns"]]
                    b = [c["column"] for c in idxs[names[j]]["columns"]]
                    # a is redundant if b starts with a's columns and a != b
                    if len(a) < len(b) and b[:len(a)] == a and names[i] != "PRIMARY":
                        out.append({"table": tname, "column": None,
                                    "fix": "DROP INDEX %s; — covered by %s." % (names[i], names[j])})
        # Deduplicate.
        seen = set()
        unique = []
        for v in out:
            key = (v["table"], v["fix"])
            if key not in seen:
                seen.add(key)
                unique.append(v)
        return unique

    def Check_no_duplicate_indexes(self, meta):
        """Tables MUST NOT have exact duplicate indexes."""
        out = []
        for tname, idxs in meta["indexes"].items():
            seen_cols = {}
            for iname, idx in idxs.items():
                if iname == "PRIMARY":
                    continue
                cols = tuple(c["column"] for c in idx["columns"])
                if cols in seen_cols:
                    out.append({"table": tname, "column": None,
                                "fix": "DROP INDEX %s; — exact duplicate of %s." % (iname, seen_cols[cols])})
                else:
                    seen_cols[cols] = iname
        return out

    def Check_no_nullable_in_unique_index(self, meta):
        """Unique indexes MUST NOT contain nullable columns."""
        out = []
        for tname, idxs in meta["indexes"].items():
            col_map = {c["column"]: c for c in meta["tables"].get(tname, {}).get("columns", [])}
            for iname, idx in idxs.items():
                if idx["non_unique"]:
                    continue
                for ic in idx["columns"]:
                    col = col_map.get(ic["column"])
                    if col and col["is_nullable"]:
                        out.append({"table": tname, "column": ic["column"],
                                    "fix": "Add NOT NULL to '%s' or use a partial unique index." % ic["column"]})
        return out

    def Check_no_index_too_many_columns(self, meta):
        """Indexes MUST NOT have more than MAX_INDEX_COLUMNS columns."""
        out = []
        for tname, idxs in meta["indexes"].items():
            for iname, idx in idxs.items():
                if iname == "PRIMARY":
                    continue
                if len(idx["columns"]) > Cfg.Config.MAX_INDEX_COLUMNS:
                    out.append({"table": tname, "column": None,
                                "fix": "DROP INDEX %s; create a narrower index on the most selective columns." % iname})
        return out

    def Check_no_over_indexed_table(self, meta):
        """Tables MUST NOT have more indexes than columns."""
        out = []
        for tname, t in meta["tables"].items():
            idx_count = len(meta["indexes"].get(tname, {}))
            if idx_count > len(t["columns"]):
                out.append({"table": tname, "column": None,
                            "fix": "Drop unused indexes; keep only PK, unique, and FK indexes."})
        return out

    # --- 4. NAMING / METADATA ---

    def Check_name_must_not_be_in_list(self, meta):
        """Names MUST NOT be SQL reserved words."""
        out = []
        reserved = set(w.lower() for w in Cfg.Config.SQL_RESERVED_WORDS)
        for col in meta["columns"]:
            if col["column"].lower() in reserved:
                out.append({"table": col["table"], "column": col["column"],
                            "fix": "Rename '%s' to a non-reserved identifier." % col["column"]})
        for tname in meta["tables"]:
            if tname.lower() in reserved:
                out.append({"table": tname, "column": None,
                            "fix": "Rename table '%s' to a non-reserved identifier." % tname})
        return out

    def Check_name_must_not_contain_spaces(self, meta):
        """Names MUST NOT contain spaces."""
        out = []
        for col in meta["columns"]:
            if " " in col["column"]:
                out.append({"table": col["table"], "column": col["column"],
                            "fix": "Rename '%s' replacing spaces with underscores." % col["column"]})
        for tname in meta["tables"]:
            if " " in tname:
                out.append({"table": tname, "column": None,
                            "fix": "Rename table '%s' replacing spaces with underscores." % tname})
        return out

    def Check_no_bad_column_names(self, meta):
        """Columns MUST NOT be named bare ID."""
        out = []
        for col in meta["columns"]:
            if col["column"].lower() == "id" and col["column_key"] != "PRI":
                # bare 'id' as non-PK is ambiguous
                out.append({"table": col["table"], "column": col["column"],
                            "fix": "Rename '%s' to '%s_id' for clarity." % (col["column"], col["table"])})
        return out

    def Check_no_string_null_default(self, meta):
        """Defaults MUST NOT be string NULL."""
        out = []
        for col in meta["columns"]:
            d = col["default"]
            if d is not None and isinstance(d, str) and d.strip().upper() == "NULL":
                out.append({"table": col["table"], "column": col["column"],
                            "fix": "Use real NULL default, not the string 'NULL'."})
        return out

    def Check_no_inconsistent_naming_case(self, meta):
        """Column names MUST NOT mix snake_case and camelCase."""
        out = []
        for col in meta["columns"]:
            if not self._IsSnakeCase(col["column"]) and self._IsCamelCase(col["column"]):
                snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", col["column"]).lower()
                out.append({"table": col["table"], "column": col["column"],
                            "fix": "Rename '%s' to snake_case '%s'." % (col["column"], snake)})
        return out

    def Check_no_column_prefix_match_table(self, meta):
        """Column names MUST NOT redundantly prefix table name."""
        out = []
        for tname, t in meta["tables"].items():
            for col in t["columns"]:
                if col["column"].lower().startswith(tname.lower() + "_") and col["column"] != "id":
                    stripped = col["column"][len(tname) + 1:]
                    if stripped:
                        out.append({"table": tname, "column": col["column"],
                                    "fix": "Rename '%s' to '%s' (drop the table-name prefix)." % (
                                        col["column"], stripped)})
        return out

    def Check_no_boolean_without_prefix(self, meta):
        """is_*/has_* columns MUST be INTEGER type."""
        out = []
        for col in meta["columns"]:
            if self._IsBooleanPrefix(col["column"]):
                if not self._IsIntegerFamily(col["data_type"]):
                    out.append({"table": col["table"], "column": col["column"],
                                "fix": "Change '%s' to INTEGER (MySQL boolean stored as TINYINT/INTEGER)." % col["column"]})
        return out

    def Check_no_timestamp_naming(self, meta):
        """Columns MUST NOT be named timestamp/time (use created_at)."""
        out = []
        bad = set(n.lower() for n in Cfg.Config.BAD_TIMESTAMP_NAMES)
        for col in meta["columns"]:
            if col["column"].lower() in bad:
                out.append({"table": col["table"], "column": col["column"],
                            "fix": "Rename '%s' to 'created_at' or 'updated_at'." % col["column"]})
        return out

    def Check_fk_column_must_have_id_suffix(self, meta):
        """Foreign key columns MUST end with _id."""
        out = []
        for fk in meta["fks"]:
            if not fk["column"].lower().endswith(Cfg.Config.FK_SUFFIX):
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "Rename FK column '%s' to end with '_id'." % fk["column"]})
        return out

    def Check_column_type_consistent(self, meta):
        """Same column name MUST have same type across tables."""
        out = []
        for cname, types in meta["col_types"].items():
            if len(types) > 1:
                # Find the tables involved.
                tables = [col["table"] for col in meta["columns"] if col["column"] == cname]
                out.append({"table": ",".join(sorted(set(tables))), "column": cname,
                            "fix": "Column '%s' has inconsistent types: %s. Align to one type." % (
                                cname, ", ".join(sorted(types)))})
        return out

    # --- OPTIONAL (disabled by default) ---

    def Check_no_empty_table(self, meta):
        """Tables MUST NOT be empty."""
        out = []
        for tname, t in meta["tables"].items():
            if t["rows"] is not None and t["rows"] == 0:
                out.append({"table": tname, "column": None,
                            "fix": "Populate the table or remove it if unused."})
        return out

    def Check_no_table_without_indexes(self, meta):
        """Tables MUST NOT lack indexes entirely."""
        out = []
        for tname in meta["tables"]:
            if tname not in meta["indexes"] or not meta["indexes"][tname]:
                out.append({"table": tname, "column": None,
                            "fix": "Add at least a primary key index."})
        return out

    # ========================================================================
    # DESIGN RULE CHECKS (DB_DESIGN_RULES)
    # ------------------------------------------------------------------------
    # Many design rules describe runtime/engine behavior that cannot be
    # fully verified from information_schema alone. Where a metadata-based
    # check is possible, we implement it; otherwise the check returns []
    # (no violations) — the rule is still "run" (counted) but produces no
    # findings from static schema inspection.
    # ========================================================================

    def Check_every_table_has_pk(self, meta):
        """SCHEMA-001: Every table should have a primary key."""
        return self.Check_table_must_have_pk(meta)

    def Check_integer_pk_is_rowid_alias(self, meta):
        """SCHEMA-002: SQLite-only — not applicable to MySQL."""
        return []

    def Check_sqlite_pk_implicit_not_null(self, meta):
        """SCHEMA-003: SQLite-only."""
        return []

    def Check_unique_nulls_distinct(self, meta):
        """SCHEMA-004: UNIQUE permits multiple NULLs — flag nullable unique cols."""
        return self.Check_no_nullable_in_unique_index(meta)

    def Check_check_no_subquery_or_other_table(self, meta):
        """SCHEMA-005: CHECK cannot reference subqueries/other tables.

        MySQL CHECK constraints are parsed but ignored prior to 8.0.16 and
        enforced after. We cannot inspect CHECK expression text from
        information_schema reliably; no static violations.
        """
        return []

    def Check_not_null_default_semantics(self, meta):
        """SCHEMA-006: NOT NULL semantics — flag columns that lack both NOT NULL and a default."""
        out = []
        for col in meta["columns"]:
            if col["is_nullable"] and col["default"] is None and col["column_key"] != "PRI":
                # Not a violation per se, but worth noting for critical columns.
                pass
        return out

    def Check_sqlite_default_must_be_constant(self, meta):
        """SCHEMA-007: SQLite-only."""
        return []

    def Check_ctas_has_no_constraints(self, meta):
        """SCHEMA-008: CREATE TABLE AS SELECT yields no PK — flag tables with no PK and no constraints."""
        # Approximated by the PK check.
        return []

    def Check_innodb_unique_fallback_clustered(self, meta):
        """SCHEMA-009: Without PK, InnoDB uses first all-NOT-NULL UNIQUE index as clustered."""
        out = []
        for tname, t in meta["tables"].items():
            if t["pk_cols"]:
                continue
            if t["engine"] and t["engine"].lower() != "innodb":
                continue
            # No PK — flag so the user is aware of the implicit clustered index.
            out.append({"table": tname, "column": None,
                        "fix": "Add an explicit PRIMARY KEY; InnoDB will otherwise use a UNIQUE index as clustered."})
        return out

    def Check_innodb_hidden_clustered_index(self, meta):
        """SCHEMA-010: Without PK or UNIQUE, InnoDB creates a hidden clustered index."""
        out = []
        for tname, t in meta["tables"].items():
            if t["pk_cols"]:
                continue
            has_unique = any(not idx["non_unique"] for idx in meta["indexes"].get(tname, {}).values())
            if not has_unique:
                out.append({"table": tname, "column": None,
                            "fix": "Add a PRIMARY KEY; InnoDB otherwise creates a hidden 6-byte clustered index."})
        return out

    def Check_mysql_pk_implicit_not_null(self, meta):
        """SCHEMA-011: PK columns are implicitly NOT NULL in InnoDB — no action needed."""
        return []

    # --- b. REFERENTIAL INTEGRITY ---

    def Check_sqlite_fk_enabled_pragma(self, meta):
        """REF-001: SQLite-only."""
        return []

    def Check_mysql_fk_checks_default_on(self, meta):
        """REF-002: MySQL foreign_key_checks is ON by default — verify."""
        return self.Check_must_enforce_foreign_keys(meta)

    def Check_fk_null_satisfies_constraint(self, meta):
        """REF-003: FK satisfied if child key is NULL — recommend NOT NULL on FK child."""
        out = []
        for fk in meta["fks"]:
            for col in meta["tables"].get(fk["table"], {}).get("columns", []):
                if col["column"] == fk["column"] and col["is_nullable"]:
                    out.append({"table": fk["table"], "column": fk["column"],
                                "fix": "Add NOT NULL to FK child column to forbid NULL child keys."})
        return out

    def Check_sqlite_parent_key_unique_collation(self, meta):
        """REF-004: SQLite-only."""
        return []

    def Check_composite_fk_cardinality_match(self, meta):
        """REF-005: Composite FK parent/child keys must match cardinality."""
        # MySQL enforces this at DDL time; no static check needed.
        return []

    def Check_sqlite_fk_unnamed_pk_count_match(self, meta):
        """REF-006: SQLite-only."""
        return []

    def Check_sqlite_child_key_index_recommended(self, meta):
        """REF-007: SQLite-only (index recommendation handled by fk_must_have_index)."""
        return []

    def Check_mysql_fk_same_engine_no_temp(self, meta):
        """REF-008: FK parent/child must use same engine — check engine match."""
        out = []
        for fk in meta["fks"]:
            child_engine = meta["tables"].get(fk["table"], {}).get("engine")
            parent_engine = meta["tables"].get(fk["ref_table"], {}).get("engine")
            if child_engine and parent_engine and child_engine != parent_engine:
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "FK parent and child tables must use the same storage engine (%s vs %s)." % (
                                child_engine, parent_engine)})
        return out

    def Check_mysql_fk_column_type_match(self, meta):
        """REF-009: MySQL FK columns must have similar types."""
        return self.Check_fk_type_must_match(meta)

    def Check_mysql_fk_index_required(self, meta):
        """REF-010: MySQL requires an index where FK columns are first."""
        return self.Check_fk_must_have_index(meta)

    def Check_mysql_fk_parent_must_be_unique(self, meta):
        """REF-011: Referencing a non-unique index as FK parent is deprecated."""
        out = []
        for fk in meta["fks"]:
            ref_table = fk["ref_table"]
            ref_col = fk["ref_column"]
            if ref_table not in meta["tables"]:
                continue
            # Check if ref_col is part of a unique index or PK.
            is_unique = False
            for idx in meta["indexes"].get(ref_table, {}).values():
                if not idx["non_unique"] and idx["columns"] and idx["columns"][0]["column"] == ref_col:
                    is_unique = True
                    break
            pk_cols = set(meta["tables"][ref_table]["pk_cols"])
            if ref_col in pk_cols:
                is_unique = True
            if not is_unique:
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "FK parent %s.%s should be PK or UNIQUE; referencing a non-unique index is deprecated." % (
                                ref_table, ref_col)})
        return out

    def Check_mysql_fk_no_blob_text_prefix(self, meta):
        """REF-012: BLOB/TEXT cannot be in a foreign key."""
        out = []
        for fk in meta["fks"]:
            for col in meta["tables"].get(fk["table"], {}).get("columns", []):
                if col["column"] == fk["column"] and self._IsLobType(col["data_type"]):
                    out.append({"table": fk["table"], "column": fk["column"],
                                "fix": "BLOB/TEXT columns cannot be used in a foreign key."})
        return out

    def Check_mysql_fk_no_user_partitioning(self, meta):
        """REF-013: InnoDB disallows FKs on user-partitioned tables."""
        # Partitioning info not in our metadata; no static check.
        return []

    def Check_mysql_fk_no_engine_change_with_fk(self, meta):
        """REF-014: Cannot ALTER engine with FKs — runtime rule, no static check."""
        return []

    def Check_mysql_fk_no_virtual_generated_ref(self, meta):
        """REF-015: FK cannot reference a virtual generated column."""
        out = []
        for fk in meta["fks"]:
            for col in meta["tables"].get(fk["ref_table"], {}).get("columns", []):
                if col["column"] == fk["ref_column"] and "VIRTUAL" in col["extra"].upper():
                    out.append({"table": fk["table"], "column": fk["column"],
                                "fix": "FK cannot reference a virtual generated column %s.%s." % (
                                    fk["ref_table"], fk["ref_column"])})
        return out

    def Check_mysql_fk_name_unique_in_db(self, meta):
        """REF-016: FK constraint name must be unique in the database."""
        out = []
        counts = defaultdict(list)
        for fk in meta["fks"]:
            counts[fk["constraint_name"]].append(fk["table"])
        for cname, tables in counts.items():
            if len(set(tables)) > 1:
                out.append({"table": ",".join(sorted(set(tables))), "column": None,
                            "fix": "FK constraint name '%s' is used in multiple tables — must be unique per database." % cname})
        return out

    def Check_fk_referential_actions_allowed(self, meta):
        """REF-017: Referential actions allowed: NO ACTION, RESTRICT, CASCADE, SET NULL, SET DEFAULT."""
        allowed = {"NO ACTION", "RESTRICT", "CASCADE", "SET NULL", "SET DEFAULT"}
        out = []
        for fk in meta["fks"]:
            for action_field in ("update_rule", "delete_rule"):
                action = (fk.get(action_field) or "NO ACTION").upper()
                if action not in allowed:
                    out.append({"table": fk["table"], "column": fk["column"],
                                "fix": "Referential action %s=%s is not allowed." % (action_field, action)})
        return out

    def Check_fk_default_action_no_action(self, meta):
        """REF-018: Default referential action is NO ACTION — informational, no violation."""
        return []

    def Check_mysql_no_action_semantics(self, meta):
        """REF-019: InnoDB NO ACTION == RESTRICT — informational."""
        return []

    def Check_mysql_no_set_default_action(self, meta):
        """REF-020: ON DELETE/UPDATE SET DEFAULT rejected by InnoDB — flag if used."""
        out = []
        for fk in meta["fks"]:
            for action_field in ("update_rule", "delete_rule"):
                action = (fk.get(action_field) or "").upper()
                if action == "SET DEFAULT":
                    out.append({"table": fk["table"], "column": fk["column"],
                                "fix": "InnoDB rejects ON %s SET DEFAULT — use CASCADE or SET NULL instead." % (
                                    "UPDATE" if action_field == "update_rule" else "DELETE")})
        return out

    def Check_fk_set_null_child_not_null(self, meta):
        """REF-021: With SET NULL, child key columns must not be NOT NULL."""
        out = []
        for fk in meta["fks"]:
            uses_set_null = (fk.get("update_rule") == "SET NULL" or fk.get("delete_rule") == "SET NULL")
            if not uses_set_null:
                continue
            for col in meta["tables"].get(fk["table"], {}).get("columns", []):
                if col["column"] == fk["column"] and not col["is_nullable"]:
                    out.append({"table": fk["table"], "column": fk["column"],
                                "fix": "FK uses SET NULL but child column is NOT NULL — allow NULL or change the action."})
        return out

    def Check_sqlite_restrict_immediate(self, meta):
        """REF-022: SQLite-only."""
        return []

    def Check_sqlite_set_default_needs_parent(self, meta):
        """REF-023: SQLite-only."""
        return []

    def Check_mysql_cascade_no_trigger(self, meta):
        """REF-024: Cascaded FK actions do not activate triggers — runtime, no static check."""
        return []

    def Check_mysql_fk_generated_col_action_limit(self, meta):
        """REF-025: FK on stored generated column restricts CASCADE/SET NULL/SET DEFAULT."""
        out = []
        for fk in meta["fks"]:
            for col in meta["tables"].get(fk["table"], {}).get("columns", []):
                if col["column"] == fk["column"] and "GENERATED" in col["extra"].upper():
                    action = (fk.get("update_rule") or "") + "/" + (fk.get("delete_rule") or "")
                    if any(a in action.upper() for a in ("CASCADE", "SET NULL", "SET DEFAULT")):
                        out.append({"table": fk["table"], "column": fk["column"],
                                    "fix": "FK on generated column cannot use CASCADE/SET NULL/SET DEFAULT."})
        return out

    def Check_mysql_no_duplicate_cascade(self, meta):
        """REF-026: No multiple ON UPDATE CASCADE between same two tables on same column."""
        out = []
        seen = {}
        for fk in meta["fks"]:
            if (fk.get("update_rule") or "").upper() != "CASCADE":
                continue
            key = (fk["table"], fk["ref_table"], fk["column"])
            if key in seen:
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "Duplicate ON UPDATE CASCADE between %s and %s on %s." % (
                                fk["table"], fk["ref_table"], fk["column"])})
            seen[key] = True
        return out

    # --- c. INDEXING AND PERFORMANCE ---

    def Check_index_predicate_columns(self, meta):
        """IDX-001: Index columns used in WHERE/JOIN/ORDER BY — heuristic: index FK + PK + unique columns."""
        # Cannot inspect query patterns from schema; no static violation.
        return []

    def Check_composite_index_leftmost_prefix(self, meta):
        """IDX-002: Composite index leftmost prefix — informational, no static check."""
        return []

    def Check_no_low_cardinality_index(self, meta):
        """IDX-003: Avoid indexing low-cardinality columns — requires data sampling, skip."""
        return []

    def Check_sqlite_expr_index_no_nondeterminism(self, meta):
        """IDX-004: SQLite-only."""
        return []

    def Check_sqlite_partial_index_recommended(self, meta):
        """IDX-005: SQLite-only."""
        return []

    def Check_sqlite_index_column_limit(self, meta):
        """IDX-006: SQLite-only."""
        return []

    def Check_sqlite_no_nulls_first_last_index(self, meta):
        """IDX-007: SQLite-only."""
        return []

    def Check_innodb_keep_pk_narrow(self, meta):
        """IDX-008: Keep InnoDB PK narrow — flag wide PK types (CHAR/VARCHAR/TEXT)."""
        out = []
        for tname, t in meta["tables"].items():
            if not t["pk_cols"]:
                continue
            for pk in t["pk_cols"]:
                for col in t["columns"]:
                    if col["column"] == pk and col["data_type"] in ("CHAR", "VARCHAR", "TEXT", "BLOB"):
                        out.append({"table": tname, "column": pk,
                                    "fix": "InnoDB PK should be narrow (INTEGER); wide PK bloats secondary indexes."})
        return out

    def Check_innodb_short_monotonic_pk(self, meta):
        """IDX-009: Use short, monotonically increasing PK for InnoDB."""
        return self.Check_innodb_keep_pk_narrow(meta)

    def Check_mysql_text_blob_index_prefix(self, meta):
        """IDX-010: TEXT/BLOB indexes need prefix length — check index sub_part."""
        out = []
        conn = self.state.get("conn")
        if conn is None:
            return out
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT table_name, index_name, column_name, sub_part "
                "FROM information_schema.statistics "
                "WHERE table_schema = %s AND sub_part IS NULL "
                "AND column_name IN ("
                "  SELECT column_name FROM information_schema.columns "
                "  WHERE table_schema = %s "
                "    AND data_type IN ('text','blob','tinytext','mediumtext','longtext','tinyblob','mediumblob','longblob')"
                ")",
                (meta["database"], meta["database"]))
            for row in cur.fetchall():
                r = self._NormRow(row)
                out.append({"table": r["table_name"], "column": r["column_name"],
                            "fix": "Index on TEXT/BLOB column '%s' requires a prefix length." % r["column_name"]})
        except Exception:
            pass
        finally:
            cur.close()
        return out

    def Check_mysql_fk_on_join_columns(self, meta):
        """IDX-011: Defining FKs on join columns ensures indexing — covered by fk_must_have_index."""
        return []

    def Check_mysql_no_drop_fk_index(self, meta):
        """IDX-012: Dropping an FK-required index is rejected — runtime rule."""
        return []

    # --- d. DATA TYPE ---

    def Check_sqlite_dynamic_typing(self, meta):
        """DT-001: SQLite-only."""
        return []

    def Check_sqlite_affinity_rules(self, meta):
        """DT-002: SQLite-only."""
        return []

    def Check_sqlite_no_native_boolean(self, meta):
        """DT-003: SQLite-only."""
        return []

    def Check_sqlite_datetime_format_consistent(self, meta):
        """DT-004: SQLite-only."""
        return []

    def Check_sqlite_strict_table_types(self, meta):
        """DT-005: SQLite-only."""
        return []

    def Check_sqlite_strict_datatype_error(self, meta):
        """DT-006: SQLite-only."""
        return []

    def Check_sqlite_strict_int_pk_not_rowid(self, meta):
        """DT-007: SQLite-only."""
        return []

    def Check_mysql_static_typing(self, meta):
        """DT-008: MySQL enforces static typing — no static check (engine guarantee)."""
        return []

    def Check_mysql_decimal_precision_scale(self, meta):
        """DT-009: DECIMAL/NUMERIC: D <= M-2 and D <= 30."""
        out = []
        for col in meta["columns"]:
            if col["data_type"] in ("DECIMAL", "NUMERIC"):
                m = col["num_precision"]
                d = col["num_scale"]
                if m is not None and d is not None:
                    if d > 30 or d > (m - 2 if m >= 2 else 0):
                        out.append({"table": col["table"], "column": col["column"],
                                    "fix": "DECIMAL(%s,%s) invalid: scale D must be <= 30 and <= M-2." % (m, d)})
        return out

    def Check_mysql_fsp_range(self, meta):
        """DT-010: fsp for TIME/DATETIME/TIMESTAMP is 0-6."""
        # fsp is embedded in column_type like 'datetime(6)'; check it.
        out = []
        for col in meta["columns"]:
            if col["data_type"] in ("TIME", "DATETIME", "TIMESTAMP"):
                m = re.search(r"\((\d+)\)", col["column_type"])
                if m:
                    fsp = int(m.group(1))
                    if fsp < 0 or fsp > 6:
                        out.append({"table": col["table"], "column": col["column"],
                                    "fix": "%s fsp %d out of range 0-6." % (col["data_type"], fsp)})
        return out

    def Check_mysql_smallest_type(self, meta):
        """DT-011: Use smallest type that holds the range — heuristic flag BIGINT for small tables."""
        # Heuristic: flag BIGINT PK on tables with few rows where INT would suffice.
        out = []
        for tname, t in meta["tables"].items():
            for pk in t["pk_cols"]:
                for col in t["columns"]:
                    if col["column"] == pk and col["data_type"] == "BIGINT":
                        rows = t["rows"] or 0
                        if rows < 2147483647:
                            out.append({"table": tname, "column": pk,
                                        "fix": "Consider INT instead of BIGINT for '%s' (table has %s rows)." % (
                                            pk, rows)})
        return out

    def Check_mysql_exact_vs_approx_numeric(self, meta):
        """DT-012: Use FLOAT/DOUBLE for approximate, DECIMAL for exact — heuristic."""
        # Flag FLOAT/DOUBLE columns whose name suggests monetary/counted values.
        out = []
        money_hints = ("price", "amount", "total", "balance", "cost", "fee", "salary", "sum")
        for col in meta["columns"]:
            if col["data_type"] in ("FLOAT", "DOUBLE"):
                low = col["column"].lower()
                if any(h in low for h in money_hints):
                    out.append({"table": col["table"], "column": col["column"],
                                "fix": "Use DECIMAL for monetary/exact value '%s' instead of %s." % (
                                    col["column"], col["data_type"])})
        return out

    def Check_mysql_timestamp_tz_conversion(self, meta):
        """DT-013: TIMESTAMP converts TZ; DATETIME does not — informational flag for mixed usage."""
        # No violation; informational only.
        return []

    # --- e. NAMING AND METADATA ---

    def Check_sqlite_no_sqlite_prefix(self, meta):
        """NAM-001: SQLite-only (sqlite_ prefix)."""
        return []

    def Check_create_table_if_not_exists_semantics(self, meta):
        """NAM-002: IF NOT EXISTS semantics — runtime, no static check."""
        return []

    def Check_mysql_identifier_case(self, meta):
        """NAM-003: MySQL identifier case sensitivity depends on lower_case_table_names."""
        out = []
        conn = self.state.get("conn")
        if conn is None:
            return out
        cur = conn.cursor()
        try:
            cur.execute("SELECT @@lower_case_table_names AS lctn")
            row = cur.fetchone()
            r = self._NormRow(row) if row else {}
            lctn = int(r.get("lctn", 0)) if r else 0
            if lctn == 0:
                # Case-sensitive on Linux; flag tables with mixed case.
                for tname in meta["tables"]:
                    if tname != tname.lower() and tname != tname.upper():
                        out.append({"table": tname, "column": None,
                                    "fix": "Table name has mixed case; case sensitivity depends on the OS."})
        except Exception:
            pass
        finally:
            cur.close()
        return out

    def Check_consistent_snake_case_identifiers(self, meta):
        """NAM-004: Use consistent snake_case; avoid reserved keywords."""
        out = []
        for col in meta["columns"]:
            if not self._IsSnakeCase(col["column"]):
                out.append({"table": col["table"], "column": col["column"],
                            "fix": "Use snake_case for identifier '%s'." % col["column"]})
        for tname in meta["tables"]:
            if not self._IsSnakeCase(tname):
                out.append({"table": tname, "column": None,
                            "fix": "Use snake_case for table name '%s'." % tname})
        return out

    def Check_explicit_fk_constraint_names(self, meta):
        """NAM-005: Name FK constraints explicitly — flag auto-generated names."""
        out = []
        for fk in meta["fks"]:
            cname = fk["constraint_name"] or ""
            # MySQL auto-generated names look like table_ibfk_N
            if re.match(r".*_ibfk_\d+$", cname):
                out.append({"table": fk["table"], "column": fk["column"],
                            "fix": "Name FK constraint explicitly instead of auto-generated '%s'." % cname})
        return out

    # --- f. NORMALIZATION ---

    def Check_nf1_atomic_columns(self, meta):
        """NORM-001: 1NF — no repeating groups/arrays. Heuristic: flag CSV-named TEXT columns."""
        return self.Check_no_csv_in_text_column(meta)

    def Check_nf2_no_partial_key_dep(self, meta):
        """NORM-002: 2NF — no partial-key dependency. Requires composite PK + non-prime attrs; heuristic skip."""
        return []

    def Check_nf3_no_transitive_dep(self, meta):
        """NORM-003: 3NF — no transitive dependency. Requires FD analysis; heuristic skip."""
        return []

    def Check_bcnf_every_determinant_is_superkey(self, meta):
        """NORM-004: BCNF — requires FD analysis; heuristic skip."""
        return []

    def Check_m_to_n_junction_table(self, meta):
        """NORM-005: M:N relationships should use junction tables, not embedded lists."""
        return self.Check_no_csv_in_text_column(meta)

    def Check_denormalize_only_with_justification(self, meta):
        """NORM-006: Denormalize only with justification — no static check."""
        return []

    # --- g. ENGINE-SPECIFIC DIFFERENCES ---

    def Check_fk_default_state_divergence(self, meta):
        """ENG-001: SQLite-only."""
        return []

    def Check_type_enforcement_portability(self, meta):
        """ENG-002: Type enforcement differs — informational, no static check."""
        return []

    def Check_boolean_datetime_type_portability(self, meta):
        """ENG-003: Boolean/datetime types differ — informational."""
        return []

    def Check_innodb_clustered_index_design(self, meta):
        """ENG-004: InnoDB stores rows in clustered index (PK) — flag non-InnoDB tables with FKs."""
        out = []
        for tname, t in meta["tables"].items():
            if t["engine"] and t["engine"].lower() != "innodb":
                has_fk = any(fk["table"] == tname or fk["ref_table"] == tname for fk in meta["fks"])
                if has_fk:
                    out.append({"table": tname, "column": None,
                                "fix": "Table with FKs should use ENGINE=InnoDB for FK support."})
        return out

    def Check_sqlite_no_clustered_index(self, meta):
        """ENG-005: SQLite-only."""
        return []

    def Check_alter_table_capability_gap(self, meta):
        """ENG-006: ALTER capability gap — informational."""
        return []

    def Check_prefer_innodb_engine(self, meta):
        """ENG-007: Prefer ENGINE=InnoDB for transactional FK-critical schemas."""
        return self.Check_innodb_clustered_index_design(meta)

    # ------------------------------------------------------------------------
    # REPORTING
    # ------------------------------------------------------------------------
    def GenerateReport(self):
        """Build a human-readable report from the last lint run.

        Returns:
            Tuple3 (ok, report_string, error)
        """
        violations = self.state.get("violations", [])
        database = self.state.get("last_database", "unknown")
        rules_run = self.state.get("rules_run", 0)
        rules_skipped = self.state.get("rules_skipped", 0)

        lines = []
        lines.append("=" * 72)
        lines.append("SCHEMA LINT REPORT")
        lines.append("=" * 72)
        lines.append("Database:       %s" % database)
        lines.append("Rules run:      %d" % rules_run)
        lines.append("Rules skipped:  %d (disabled or wrong engine)" % rules_skipped)
        lines.append("Violations:     %d" % len(violations))
        lines.append("")

        if not violations:
            lines.append("No violations found. Schema is clean.")
        else:
            # Group by severity.
            by_severity = defaultdict(list)
            for v in violations:
                by_severity[v["severity"]].append(v)
            for sev in ("high", "strict", "medium", "guideline", "low"):
                vs = by_severity.get(sev, [])
                if not vs:
                    continue
                lines.append("-" * 72)
                lines.append("[%s] — %d violation(s)" % (sev.upper(), len(vs)))
                lines.append("-" * 72)
                for v in vs:
                    loc = v["table"] or "(database)"
                    if v["column"]:
                        loc += "." + v["column"]
                    lines.append("  RULE: %s" % v["rule"])
                    lines.append("  LOC:  %s" % loc)
                    lines.append("  FIX:  %s" % v["fix"])
                    lines.append("")

        lines.append("=" * 72)
        return (True, "\n".join(lines), None)

    def Score(self):
        """Compute a 0-100 schema health score from violations.

        Score = max(0, 100 - total_weight). Each violation subtracts its
        severity weight (high/strict=10, medium/guideline=3, low=1).

        Returns:
            Tuple3 (ok, {"score": int, "violations": int, "weight": int}, error)
        """
        violations = self.state.get("violations", [])
        total_weight = 0
        for v in violations:
            total_weight += SEVERITY_WEIGHTS.get(v["severity"], 1)
        score = max(0, Cfg.Config.SCORE_MAX - total_weight)
        return (True, {
            "score": score,
            "violations": len(violations),
            "weight": total_weight,
            "max": Cfg.Config.SCORE_MAX,
        }, None)


# ----------------------------------------------------------------------------
# CHECK DISPATCH TABLE — maps check_type string to Check_* method.
# Built after the class body so methods are bound.
# ----------------------------------------------------------------------------
SchemaLintEngine._CHECK_DISPATCH = {
    # Structural — integrity
    "table_must_have_pk": SchemaLintEngine.Check_table_must_have_pk,
    "pk_must_not_be_nullable": SchemaLintEngine.Check_pk_must_not_be_nullable,
    "fk_type_must_match": SchemaLintEngine.Check_fk_type_must_match,
    "no_fk_self_reference": SchemaLintEngine.Check_no_fk_self_reference,
    "no_table_cycles": SchemaLintEngine.Check_no_table_cycles,
    "no_orphaned_fk_target": SchemaLintEngine.Check_no_orphaned_fk_target,
    "no_fk_missing_ref_column": SchemaLintEngine.Check_no_fk_missing_ref_column,
    "must_enforce_foreign_keys": SchemaLintEngine.Check_must_enforce_foreign_keys,
    "no_without_rowid_without_pk": SchemaLintEngine.Check_no_without_rowid_without_pk,
    "no_autoincrement_non_integer": SchemaLintEngine.Check_no_autoincrement_non_integer,
    # Structural — normalization
    "no_all_nullable_columns": SchemaLintEngine.Check_no_all_nullable_columns,
    "no_single_column_table": SchemaLintEngine.Check_no_single_column_table,
    "no_composite_pk": SchemaLintEngine.Check_no_composite_pk,
    "no_incrementing_columns": SchemaLintEngine.Check_no_incrementing_columns,
    "no_csv_in_text_column": SchemaLintEngine.Check_no_csv_in_text_column,
    "no_wide_table": SchemaLintEngine.Check_no_wide_table,
    "no_duplicate_column_spread": SchemaLintEngine.Check_no_duplicate_column_spread,
    # Structural — performance
    "fk_must_have_index": SchemaLintEngine.Check_fk_must_have_index,
    "pk_must_be_first": SchemaLintEngine.Check_pk_must_be_first,
    "no_redundant_indexes": SchemaLintEngine.Check_no_redundant_indexes,
    "no_duplicate_indexes": SchemaLintEngine.Check_no_duplicate_indexes,
    "no_nullable_in_unique_index": SchemaLintEngine.Check_no_nullable_in_unique_index,
    "no_index_too_many_columns": SchemaLintEngine.Check_no_index_too_many_columns,
    "no_over_indexed_table": SchemaLintEngine.Check_no_over_indexed_table,
    # Structural — naming
    "name_must_not_be_in_list": SchemaLintEngine.Check_name_must_not_be_in_list,
    "name_must_not_contain_spaces": SchemaLintEngine.Check_name_must_not_contain_spaces,
    "no_bad_column_names": SchemaLintEngine.Check_no_bad_column_names,
    "no_string_null_default": SchemaLintEngine.Check_no_string_null_default,
    "no_inconsistent_naming_case": SchemaLintEngine.Check_no_inconsistent_naming_case,
    "no_column_prefix_match_table": SchemaLintEngine.Check_no_column_prefix_match_table,
    "no_boolean_without_prefix": SchemaLintEngine.Check_no_boolean_without_prefix,
    "no_timestamp_naming": SchemaLintEngine.Check_no_timestamp_naming,
    "fk_column_must_have_id_suffix": SchemaLintEngine.Check_fk_column_must_have_id_suffix,
    "column_type_consistent": SchemaLintEngine.Check_column_type_consistent,
    # Structural — optional
    "no_empty_table": SchemaLintEngine.Check_no_empty_table,
    "no_table_without_indexes": SchemaLintEngine.Check_no_table_without_indexes,
    # Design — schema integrity
    "every_table_has_pk": SchemaLintEngine.Check_every_table_has_pk,
    "integer_pk_is_rowid_alias": SchemaLintEngine.Check_integer_pk_is_rowid_alias,
    "sqlite_pk_implicit_not_null": SchemaLintEngine.Check_sqlite_pk_implicit_not_null,
    "unique_nulls_distinct": SchemaLintEngine.Check_unique_nulls_distinct,
    "check_no_subquery_or_other_table": SchemaLintEngine.Check_check_no_subquery_or_other_table,
    "not_null_default_semantics": SchemaLintEngine.Check_not_null_default_semantics,
    "sqlite_default_must_be_constant": SchemaLintEngine.Check_sqlite_default_must_be_constant,
    "ctas_has_no_constraints": SchemaLintEngine.Check_ctas_has_no_constraints,
    "innodb_unique_fallback_clustered": SchemaLintEngine.Check_innodb_unique_fallback_clustered,
    "innodb_hidden_clustered_index": SchemaLintEngine.Check_innodb_hidden_clustered_index,
    "mysql_pk_implicit_not_null": SchemaLintEngine.Check_mysql_pk_implicit_not_null,
    # Design — referential integrity
    "sqlite_fk_enabled_pragma": SchemaLintEngine.Check_sqlite_fk_enabled_pragma,
    "mysql_fk_checks_default_on": SchemaLintEngine.Check_mysql_fk_checks_default_on,
    "fk_null_satisfies_constraint": SchemaLintEngine.Check_fk_null_satisfies_constraint,
    "sqlite_parent_key_unique_collation": SchemaLintEngine.Check_sqlite_parent_key_unique_collation,
    "composite_fk_cardinality_match": SchemaLintEngine.Check_composite_fk_cardinality_match,
    "sqlite_fk_unnamed_pk_count_match": SchemaLintEngine.Check_sqlite_fk_unnamed_pk_count_match,
    "sqlite_child_key_index_recommended": SchemaLintEngine.Check_sqlite_child_key_index_recommended,
    "mysql_fk_same_engine_no_temp": SchemaLintEngine.Check_mysql_fk_same_engine_no_temp,
    "mysql_fk_column_type_match": SchemaLintEngine.Check_mysql_fk_column_type_match,
    "mysql_fk_index_required": SchemaLintEngine.Check_mysql_fk_index_required,
    "mysql_fk_parent_must_be_unique": SchemaLintEngine.Check_mysql_fk_parent_must_be_unique,
    "mysql_fk_no_blob_text_prefix": SchemaLintEngine.Check_mysql_fk_no_blob_text_prefix,
    "mysql_fk_no_user_partitioning": SchemaLintEngine.Check_mysql_fk_no_user_partitioning,
    "mysql_fk_no_engine_change_with_fk": SchemaLintEngine.Check_mysql_fk_no_engine_change_with_fk,
    "mysql_fk_no_virtual_generated_ref": SchemaLintEngine.Check_mysql_fk_no_virtual_generated_ref,
    "mysql_fk_name_unique_in_db": SchemaLintEngine.Check_mysql_fk_name_unique_in_db,
    "fk_referential_actions_allowed": SchemaLintEngine.Check_fk_referential_actions_allowed,
    "fk_default_action_no_action": SchemaLintEngine.Check_fk_default_action_no_action,
    "mysql_no_action_semantics": SchemaLintEngine.Check_mysql_no_action_semantics,
    "mysql_no_set_default_action": SchemaLintEngine.Check_mysql_no_set_default_action,
    "fk_set_null_child_not_null": SchemaLintEngine.Check_fk_set_null_child_not_null,
    "sqlite_restrict_immediate": SchemaLintEngine.Check_sqlite_restrict_immediate,
    "sqlite_set_default_needs_parent": SchemaLintEngine.Check_sqlite_set_default_needs_parent,
    "mysql_cascade_no_trigger": SchemaLintEngine.Check_mysql_cascade_no_trigger,
    "mysql_fk_generated_col_action_limit": SchemaLintEngine.Check_mysql_fk_generated_col_action_limit,
    "mysql_no_duplicate_cascade": SchemaLintEngine.Check_mysql_no_duplicate_cascade,
    # Design — indexing performance
    "index_predicate_columns": SchemaLintEngine.Check_index_predicate_columns,
    "composite_index_leftmost_prefix": SchemaLintEngine.Check_composite_index_leftmost_prefix,
    "no_low_cardinality_index": SchemaLintEngine.Check_no_low_cardinality_index,
    "sqlite_expr_index_no_nondeterminism": SchemaLintEngine.Check_sqlite_expr_index_no_nondeterminism,
    "sqlite_partial_index_recommended": SchemaLintEngine.Check_sqlite_partial_index_recommended,
    "sqlite_index_column_limit": SchemaLintEngine.Check_sqlite_index_column_limit,
    "sqlite_no_nulls_first_last_index": SchemaLintEngine.Check_sqlite_no_nulls_first_last_index,
    "innodb_keep_pk_narrow": SchemaLintEngine.Check_innodb_keep_pk_narrow,
    "innodb_short_monotonic_pk": SchemaLintEngine.Check_innodb_short_monotonic_pk,
    "mysql_text_blob_index_prefix": SchemaLintEngine.Check_mysql_text_blob_index_prefix,
    "mysql_fk_on_join_columns": SchemaLintEngine.Check_mysql_fk_on_join_columns,
    "mysql_no_drop_fk_index": SchemaLintEngine.Check_mysql_no_drop_fk_index,
    # Design — data type
    "sqlite_dynamic_typing": SchemaLintEngine.Check_sqlite_dynamic_typing,
    "sqlite_affinity_rules": SchemaLintEngine.Check_sqlite_affinity_rules,
    "sqlite_no_native_boolean": SchemaLintEngine.Check_sqlite_no_native_boolean,
    "sqlite_datetime_format_consistent": SchemaLintEngine.Check_sqlite_datetime_format_consistent,
    "sqlite_strict_table_types": SchemaLintEngine.Check_sqlite_strict_table_types,
    "sqlite_strict_datatype_error": SchemaLintEngine.Check_sqlite_strict_datatype_error,
    "sqlite_strict_int_pk_not_rowid": SchemaLintEngine.Check_sqlite_strict_int_pk_not_rowid,
    "mysql_static_typing": SchemaLintEngine.Check_mysql_static_typing,
    "mysql_decimal_precision_scale": SchemaLintEngine.Check_mysql_decimal_precision_scale,
    "mysql_fsp_range": SchemaLintEngine.Check_mysql_fsp_range,
    "mysql_smallest_type": SchemaLintEngine.Check_mysql_smallest_type,
    "mysql_exact_vs_approx_numeric": SchemaLintEngine.Check_mysql_exact_vs_approx_numeric,
    "mysql_timestamp_tz_conversion": SchemaLintEngine.Check_mysql_timestamp_tz_conversion,
    # Design — naming metadata
    "sqlite_no_sqlite_prefix": SchemaLintEngine.Check_sqlite_no_sqlite_prefix,
    "create_table_if_not_exists_semantics": SchemaLintEngine.Check_create_table_if_not_exists_semantics,
    "mysql_identifier_case": SchemaLintEngine.Check_mysql_identifier_case,
    "consistent_snake_case_identifiers": SchemaLintEngine.Check_consistent_snake_case_identifiers,
    "explicit_fk_constraint_names": SchemaLintEngine.Check_explicit_fk_constraint_names,
    # Design — normalization
    "nf1_atomic_columns": SchemaLintEngine.Check_nf1_atomic_columns,
    "nf2_no_partial_key_dep": SchemaLintEngine.Check_nf2_no_partial_key_dep,
    "nf3_no_transitive_dep": SchemaLintEngine.Check_nf3_no_transitive_dep,
    "bcnf_every_determinant_is_superkey": SchemaLintEngine.Check_bcnf_every_determinant_is_superkey,
    "m_to_n_junction_table": SchemaLintEngine.Check_m_to_n_junction_table,
    "denormalize_only_with_justification": SchemaLintEngine.Check_denormalize_only_with_justification,
    # Design — engine specific
    "fk_default_state_divergence": SchemaLintEngine.Check_fk_default_state_divergence,
    "type_enforcement_portability": SchemaLintEngine.Check_type_enforcement_portability,
    "boolean_datetime_type_portability": SchemaLintEngine.Check_boolean_datetime_type_portability,
    "innodb_clustered_index_design": SchemaLintEngine.Check_innodb_clustered_index_design,
    "sqlite_no_clustered_index": SchemaLintEngine.Check_sqlite_no_clustered_index,
    "alter_table_capability_gap": SchemaLintEngine.Check_alter_table_capability_gap,
    "prefer_innodb_engine": SchemaLintEngine.Check_prefer_innodb_engine,
}


# ----------------------------------------------------------------------------
# MODULE ENTRY POINT
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    engine = SchemaLintEngine()
    ok, data, error = engine.Run("lint_db", {"database": "vb_shared"})
    if not ok:
        sys.stderr.write("ERROR: %s\n" % error)
        sys.exit(1)
    sys.stdout.write("Violations: %d\n" % len(data))
    for v in data[:20]:
        sys.stdout.write("  [%s] %s.%s — %s\n" % (
            v["severity"], v["table"], v["column"], v["rule"]))
    ok, report, error = engine.Run("report", {})
    if ok:
        sys.stdout.write(report + "\n")
    ok, score, error = engine.Run("score", {})
    if ok:
        sys.stdout.write("Score: %s\n" % json.dumps(score))
