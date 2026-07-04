#!/usr/bin/env python3
# [@GHOST]{file_path="core/Dom_Db/AuthorityManager.py" date="2026-07-04" author="Devin" context="Authority table CRUD manager for laws database"}
# [@VBSTYLE]{auth="system" role="authority_manager" return="Tuple3" orch="none" no="decorators|print|hardcoded|tabs|self_underscore"}
# [@FILEID]{id="AuthorityManager.py" domain="database" authority="authority_manager"}
# [@SUMMARY]{CRUD operations for 8 authority tables: status, priority, severity, confidence, type, question_type, domain, category.}

"""
AuthorityManager — CRUD operations for authority tables in the laws database.

All methods return Tuple3: (1, data, None) on success, (0, None, (code, desc, 0)) on failure.
Uses mysql.connector. No shell commands. No JSON output (LAW14 compliant).
"""

import mysql.connector
from typing import Tuple, List, Dict, Any, Optional


AUTHORITY_TABLES = [
    "status", "priority", "severity", "confidence",
    "type", "QuestionType", "domain", "category",
]


class AuthorityManager:
    """Manages CRUD operations for authority tables in the laws database."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param
        self.state = {
            "host": "localhost",
            "user": "root",
            "password": "",
            "database": "laws",
            "connection": None,
        }
        self._p = self.PHelper

    def PHelper(self, key, default=None):
        return self.state.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "connect": self.Connect,
            "disconnect": self.Disconnect,
            "list_tables": self.ListTables,
            "list_entries": self.ListEntries,
            "get_entry": self.GetEntry,
            "add_entry": self.AddEntry,
            "update_entry": self.UpdateEntry,
            "delete_entry": self.DeleteEntry,
            "search_entries": self.SearchEntries,
            "check_references": self.CheckReferences,
            "get_stats": self.GetStats,
            "validate_name": self.ValidateName,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))
        if params is None:
            return handler()
        return handler(params)

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, config):
        if not isinstance(config, dict):
            return (0, None, ("INVALID_CONFIG", "Config must be a dict", 0))
        self.state.update(config)
        return (1, dict(self.state), None)

    def Connect(self, params=None):
        try:
            conn = mysql.connector.connect(
                host=self.state["host"],
                user=self.state["user"],
                password=self.state["password"],
                database=self.state["database"],
            )
            self.state["connection"] = conn
            return (1, True, None)
        except mysql.connector.Error as e:
            return (0, None, ("CONNECT_ERROR", str(e), 0))

    def Disconnect(self, params=None):
        conn = self.state.get("connection")
        if conn and conn.is_connected():
            conn.close()
            self.state["connection"] = None
        return (1, True, None)

    def GetCursor(self):
        conn = self.state.get("connection")
        if not conn or not conn.is_connected():
            ok, _, err = self.Connect()
            if not ok:
                return None, err
            conn = self.state["connection"]
        return conn.cursor(dictionary=True), None

    def ListTables(self, params=None):
        return (1, list(AUTHORITY_TABLES), None)

    def ListEntries(self, params):
        table = params.get("table")
        if table not in AUTHORITY_TABLES:
            return (0, None, ("INVALID_TABLE", f"Table '{table}' not in authority list", 0))
        cur, err = self.GetCursor()
        if err:
            return (0, None, err)
        try:
            cur.execute(f"SELECT * FROM `{table}` ORDER BY id")
            rows = cur.fetchall()
            cur.close()
            return (1, rows, None)
        except mysql.connector.Error as e:
            return (0, None, ("QUERY_ERROR", str(e), 0))

    def GetEntry(self, params):
        table = params.get("table")
        entry_id = params.get("id")
        if table not in AUTHORITY_TABLES:
            return (0, None, ("INVALID_TABLE", f"Table '{table}' not in authority list", 0))
        cur, err = self.GetCursor()
        if err:
            return (0, None, err)
        try:
            cur.execute(f"SELECT * FROM `{table}` WHERE id=%s", (entry_id,))
            row = cur.fetchone()
            cur.close()
            if row is None:
                return (0, None, ("NOT_FOUND", f"Entry id={entry_id} not found in {table}", 0))
            return (1, row, None)
        except mysql.connector.Error as e:
            return (0, None, ("QUERY_ERROR", str(e), 0))

    def AddEntry(self, params):
        table = params.get("table")
        name = params.get("name", "").strip()
        description = params.get("description", "").strip()
        if table not in AUTHORITY_TABLES:
            return (0, None, ("INVALID_TABLE", f"Table '{table}' not in authority list", 0))
        if not name:
            return (0, None, ("EMPTY_NAME", "Name is required", 0))
        ok, _, err = self.ValidateName({"table": table, "name": name})
        if not ok:
            return (0, None, err)
        cur, err = self.GetCursor()
        if err:
            return (0, None, err)
        try:
            cur.execute(f"SELECT MAX(sort_order) as max_sort FROM `{table}`")
            max_sort = cur.fetchone()
            next_sort = (max_sort["max_sort"] or 0) + 1 if max_sort else 1
            cur.close()
            conn = self.state["connection"]
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO `{table}` (name, description, sort_order, is_active) VALUES (%s, %s, %s, 1)",
                (name, description, next_sort),
            )
            new_id = cur.lastrowid
            conn.commit()
            cur.close()
            return (1, {"id": new_id, "name": name, "description": description}, None)
        except mysql.connector.Error as e:
            if "Duplicate" in str(e):
                return (0, None, ("DUPLICATE_NAME", f"Name '{name}' already exists in {table}", 0))
            return (0, None, ("INSERT_ERROR", str(e), 0))

    def UpdateEntry(self, params):
        table = params.get("table")
        entry_id = params.get("id")
        name = params.get("name")
        description = params.get("description")
        is_active = params.get("is_active")
        if table not in AUTHORITY_TABLES:
            return (0, None, ("INVALID_TABLE", f"Table '{table}' not in authority list", 0))
        cur, err = self.GetCursor()
        if err:
            return (0, None, err)
        try:
            sets = []
            values = []
            if name is not None:
                name = name.strip()
                if not name:
                    return (0, None, ("EMPTY_NAME", "Name cannot be empty", 0))
                ok, _, err = self.ValidateName({"table": table, "name": name, "exclude_id": entry_id})
                if not ok:
                    return (0, None, err)
                sets.append("name=%s")
                values.append(name)
            if description is not None:
                sets.append("description=%s")
                values.append(description.strip())
            if is_active is not None:
                sets.append("is_active=%s")
                values.append(1 if is_active else 0)
            if not sets:
                return (0, None, ("NO_FIELDS", "No fields to update", 0))
            values.append(entry_id)
            cur.close()
            conn = self.state["connection"]
            cur = conn.cursor()
            cur.execute(
                f"UPDATE `{table}` SET {', '.join(sets)} WHERE id=%s",
                values,
            )
            affected = cur.rowcount
            conn.commit()
            cur.close()
            if affected == 0:
                return (0, None, ("NOT_FOUND", f"Entry id={entry_id} not found in {table}", 0))
            return (1, {"id": entry_id, "updated": affected}, None)
        except mysql.connector.Error as e:
            if "Duplicate" in str(e):
                return (0, None, ("DUPLICATE_NAME", f"Name '{name}' already exists in {table}", 0))
            return (0, None, ("UPDATE_ERROR", str(e), 0))

    def DeleteEntry(self, params):
        table = params.get("table")
        entry_id = params.get("id")
        force = params.get("force", False)
        if table not in AUTHORITY_TABLES:
            return (0, None, ("INVALID_TABLE", f"Table '{table}' not in authority list", 0))
        ok, ref_count, err = self.CheckReferences({"table": table, "id": entry_id})
        if not ok:
            return (0, None, err)
        total_refs = sum(ref_count.values()) if ref_count else 0
        if total_refs > 0 and not force:
            return (0, None, ("HAS_REFERENCES",
                f"Entry id={entry_id} in {table} has {total_refs} references: {ref_count}. Use force=True to null them first.", 0))
        if total_refs > 0 and force:
            ok, _, err = self.NullRefs(table, entry_id, ref_count)
            if not ok:
                return (0, None, err)
        cur, err = self.GetCursor()
        if err:
            return (0, None, err)
        try:
            cur.close()
            conn = self.state["connection"]
            cur = conn.cursor()
            cur.execute(f"DELETE FROM `{table}` WHERE id=%s", (entry_id,))
            affected = cur.rowcount
            conn.commit()
            cur.close()
            if affected == 0:
                return (0, None, ("NOT_FOUND", f"Entry id={entry_id} not found in {table}", 0))
            return (1, {"id": entry_id, "deleted": affected, "refs_nulled": total_refs}, None)
        except mysql.connector.Error as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def NullRefs(self, table, entry_id, ref_count):
        fk_map = {
            "type": "typeId",
            "QuestionType": "question_type_id",
            "status": "statusId",
            "priority": "priorityId",
            "severity": "severityId",
            "confidence": "confidenceId",
            "domain": "domainId",
            "category": "categoryId",
        }
        fk_col = fk_map.get(table)
        if not fk_col:
            return (1, True, None)
        conn = self.state["connection"]
        cur = conn.cursor()
        for ref_table, count in ref_count.items():
            if count > 0:
                try:
                    cur.execute(
                        f"UPDATE `{ref_table}` SET {fk_col}=NULL WHERE {fk_col}=%s",
                        (entry_id,),
                    )
                except mysql.connector.Error:
                    pass
        conn.commit()
        cur.close()
        return (1, True, None)

    def CheckReferences(self, params):
        table = params.get("table")
        entry_id = params.get("id")
        if table not in AUTHORITY_TABLES:
            return (0, None, ("INVALID_TABLE", f"Table '{table}' not in authority list", 0))
        fk_map = {
            "type": "typeId",
            "QuestionType": "question_type_id",
            "status": "statusId",
            "priority": "priorityId",
            "severity": "severityId",
            "confidence": "confidenceId",
            "domain": "domainId",
            "category": "categoryId",
        }
        fk_col = fk_map.get(table)
        if not fk_col:
            return (1, {}, None)
        cur, err = self.GetCursor()
        if err:
            return (0, None, err)
        try:
            cur.execute("SHOW TABLES")
            all_tables = [r[list(r.keys())[0]] for r in cur.fetchall()]
            cur.close()
            refs = {}
            for ref_table in all_tables:
                if ref_table == table:
                    continue
                cur, _ = self.GetCursor()
                cur.execute(f"DESCRIBE `{ref_table}`")
                cols = [c["Field"] for c in cur.fetchall()]
                cur.close()
                if fk_col in cols:
                    cur, _ = self.GetCursor()
                    cur.execute(f"SELECT COUNT(*) as cnt FROM `{ref_table}` WHERE {fk_col}=%s", (entry_id,))
                    row = cur.fetchone()
                    count = row["cnt"] if row else 0
                    cur.close()
                    if count > 0:
                        refs[ref_table] = count
            return (1, refs, None)
        except mysql.connector.Error as e:
            return (0, None, ("REF_CHECK_ERROR", str(e), 0))

    def SearchEntries(self, params):
        table = params.get("table")
        query = params.get("query", "").strip()
        if table not in AUTHORITY_TABLES:
            return (0, None, ("INVALID_TABLE", f"Table '{table}' not in authority list", 0))
        if not query:
            return self.ListEntries({"table": table})
        cur, err = self.GetCursor()
        if err:
            return (0, None, err)
        try:
            pattern = f"%{query}%"
            cur.execute(
                f"SELECT * FROM `{table}` WHERE name LIKE %s OR description LIKE %s ORDER BY id",
                (pattern, pattern),
            )
            rows = cur.fetchall()
            cur.close()
            return (1, rows, None)
        except mysql.connector.Error as e:
            return (0, None, ("QUERY_ERROR", str(e), 0))

    def GetStats(self, params=None):
        stats = {}
        cur, err = self.GetCursor()
        if err:
            return (0, None, err)
        try:
            for table in AUTHORITY_TABLES:
                cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
                row = cur.fetchone()
                stats[table] = row["cnt"] if row else 0
            cur.close()
            stats["total"] = sum(stats.values())
            return (1, stats, None)
        except mysql.connector.Error as e:
            return (0, None, ("STATS_ERROR", str(e), 0))

    def ValidateName(self, params):
        table = params.get("table")
        name = params.get("name", "").strip()
        exclude_id = params.get("exclude_id")
        if table not in AUTHORITY_TABLES:
            return (0, None, ("INVALID_TABLE", f"Table '{table}' not in authority list", 0))
        issues = []
        if name != name.lower():
            issues.append("Name must be lowercase (snake_case)")
        if " " in name:
            issues.append("Name must not contain spaces")
        if "\t" in name:
            issues.append("Name must not contain tabs")
        if name.upper() == name and len(name) > 3 and "_" in name:
            issues.append("Name must not be ALL_CAPS")
        if name == "n/a":
            issues.append("Use 'not_applicable' instead of 'n/a'")
        if issues:
            return (0, None, ("VALIDATION_FAILED", "; ".join(issues), 0))
        cur, err = self.GetCursor()
        if err:
            return (0, None, err)
        try:
            if exclude_id:
                cur.execute(
                    f"SELECT id FROM `{table}` WHERE name=%s AND id != %s",
                    (name, exclude_id),
                )
            else:
                cur.execute(f"SELECT id FROM `{table}` WHERE name=%s", (name,))
            row = cur.fetchone()
            cur.close()
            if row:
                return (0, None, ("DUPLICATE_NAME", f"Name '{name}' already exists in {table}", 0))
            return (1, True, None)
        except mysql.connector.Error as e:
            return (0, None, ("QUERY_ERROR", str(e), 0))
