#!/usr/bin/env python3
# [@GHOST]{file_path="Dom_Graph/LawInserter.py" date="2026-07-04" author="Devin" session_id="bnd-laws" context="Prepared statement inserter for laws database. Uses parameterized queries — no string formatting in SQL. Connects lessons to law table and pattern table via proper prepared statements."}
# [@VBSTYLE]{standard="VBStyle" version="1"}
# [@FILEID]{id="LawInserter.py" domain="laws" authority="inserter"}
# [@SUMMARY]{summary="Prepared statement inserter for the laws database. Uses mysql.connector parameterized queries (%s placeholders) to safely insert laws, patterns, and staging records. No raw SQL string formatting."}
# [@CLASS]{class="LawInserter" domain="laws" authority="inserter"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="cmd_insert_law" type="write"}
# [@METHOD]{method="cmd_insert_pattern" type="write"}
# [@METHOD]{method="cmd_insert_lesson" type="write"}
# [@METHOD]{method="cmd_batch_lessons" type="write"}
# [@METHOD]{method="cmd_get_law" type="read"}
# [@METHOD]{method="cmd_list_laws" type="read"}
# [@METHOD]{method="cmd_stage_law" type="write"}

"""LawInserter — Prepared statement inserter for the laws database.

Uses mysql.connector parameterized queries with %s placeholders.
No string formatting in SQL. All values passed as tuple parameters.
This prevents SQL injection and handles special characters correctly.

Commands (via Run dispatch):
    insert_law    — insert one law using prepared statement
    insert_pattern — insert one pattern using prepared statement
    insert_lesson — insert one lesson as both law + pattern
    batch_lessons — insert multiple lessons at once
    get_law       — get a law by name
    list_laws     — list laws by domain
    stage_law     — stage a law for migration tracking
"""

import mysql.connector
from typing import Any, Dict, List, Optional, Tuple

# ── Connection config ──
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "laws",
}


class LawInserter:
    """Prepared statement inserter for the laws database."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param or {}
        self.state = {
            "class": "LawInserter",
            "initialized": True,
            "conn": None,
            "last_insert_id": 0,
            "last_error": "",
            "total_inserted": 0,
        }

    def _get_conn(self):
        """Get or create persistent connection."""
        if self.state["conn"] is None or not self.state["conn"].is_connected():
            try:
                self.state["conn"] = mysql.connector.connect(**DB_CONFIG)
            except Exception as e:
                self.state["last_error"] = str(e)
                return None
        return self.state["conn"]

    def _p(self, label, value):
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "insert_law": self.cmd_insert_law,
            "insert_pattern": self.cmd_insert_pattern,
            "insert_lesson": self.cmd_insert_lesson,
            "batch_lessons": self.cmd_batch_lessons,
            "get_law": self.cmd_get_law,
            "list_laws": self.cmd_list_laws,
            "stage_law": self.cmd_stage_law,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("LAW_UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    # ── Prepared statement: insert law ──

    def cmd_insert_law(self, params):
        """Insert a law using prepared statement (parameterized query).

        params:
            name        — law name
            statement   — law statement
            reasoning   — why this law exists
            enforcement — how to enforce it
            domain_id   — domain FK
            status_id   — status FK
            priority_id — priority FK
            severity_id — severity FK
            confidence_id — confidence FK
            type_id     — type FK
            category_id — category FK
        """
        required = ("name", "statement", "domain_id", "status_id", "priority_id", "severity_id")
        for field in required:
            if field not in params:
                return (0, None, ("LAW_MISSING_FIELD", field, 0))

        conn = self._get_conn()
        if conn is None:
            return (0, None, ("LAW_NO_CONN", self.state["last_error"], 0))

        # Prepared statement — %s placeholders, values passed as tuple
        sql = (
            "INSERT INTO law "
            "(name, statement, reasoning, enforcement, domainId, statusId, priorityId, severityId, confidenceId, typeId, categoryId) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        values = (
            params["name"],
            params["statement"],
            params.get("reasoning", ""),
            params.get("enforcement", ""),
            params["domain_id"],
            params["status_id"],
            params["priority_id"],
            params["severity_id"],
            params.get("confidence_id"),
            params.get("type_id"),
            params.get("category_id"),
        )

        try:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            law_id = cursor.lastrowid
            cursor.close()
            self.state["last_insert_id"] = law_id
            self.state["total_inserted"] += 1
            self._p("law_id", law_id)
            return (1, {"law_id": law_id, "name": params["name"]}, None)
        except Exception as e:
            self.state["last_error"] = str(e)
            return (0, None, ("LAW_INSERT_FAILED", str(e), 0))

    # ── Prepared statement: insert pattern ──

    def cmd_insert_pattern(self, params):
        """Insert a pattern using prepared statement.

        params:
            trigger_text  — what triggers the pattern
            sequence_text — what happens after trigger
            frequency     — how often seen
            confidence_id — confidence FK
            domain_id     — domain FK
            type_id       — type FK
            category_id   — category FK
            status_id     — status FK
            source_type   — source (cascade, devin, etc)
            session_id    — session identifier
        """
        required = ("trigger_text", "sequence_text", "domain_id", "status_id")
        for field in required:
            if field not in params:
                return (0, None, ("PATTERN_MISSING_FIELD", field, 0))

        conn = self._get_conn()
        if conn is None:
            return (0, None, ("LAW_NO_CONN", self.state["last_error"], 0))

        sql = (
            "INSERT INTO pattern "
            "(triggerText, sequenceText, frequency, confidenceId, domainId, typeId, categoryId, statusId, sourceType, sessionId) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        values = (
            params["trigger_text"],
            params["sequence_text"],
            params.get("frequency", 1),
            params.get("confidence_id"),
            params["domain_id"],
            params.get("type_id"),
            params.get("category_id"),
            params["status_id"],
            params.get("source_type", "devin"),
            params.get("session_id", ""),
        )

        try:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            pattern_id = cursor.lastrowid
            cursor.close()
            self.state["last_insert_id"] = pattern_id
            self.state["total_inserted"] += 1
            self._p("pattern_id", pattern_id)
            return (1, {"pattern_id": pattern_id, "trigger": params["trigger_text"][:50]}, None)
        except Exception as e:
            self.state["last_error"] = str(e)
            return (0, None, ("PATTERN_INSERT_FAILED", str(e), 0))

    # ── Insert lesson as both law + pattern ──

    def cmd_insert_lesson(self, params):
        """Insert a lesson as both a law AND a pattern.

        The law is the formal rule.
        The pattern is the observed behavior (trigger -> sequence).
        Both are linked via the same session_id and domain.
        """
        # First insert the law
        law_params = {
            "name": params.get("name", ""),
            "statement": params.get("statement", ""),
            "reasoning": params.get("reasoning", ""),
            "enforcement": params.get("enforcement", ""),
            "domain_id": params.get("domain_id", 186),
            "status_id": params.get("status_id", 45),
            "priority_id": params.get("priority_id", 12),
            "severity_id": params.get("severity_id", 17),
            "confidence_id": params.get("confidence_id", 32),
            "type_id": params.get("type_id", 62),
            "category_id": params.get("category_id", 35004),
        }
        ok_law, data_law, err_law = self.cmd_insert_law(law_params)

        # Then insert the pattern (trigger = lesson name, sequence = statement)
        pattern_params = {
            "trigger_text": params.get("name", ""),
            "sequence_text": params.get("statement", ""),
            "frequency": params.get("frequency", 1),
            "confidence_id": params.get("confidence_id", 32),
            "domain_id": params.get("domain_id", 186),
            "type_id": params.get("type_id", 62),
            "category_id": params.get("category_id", 35004),
            "status_id": params.get("status_id", 45),
            "source_type": params.get("source_type", "devin"),
            "session_id": params.get("session_id", "bnd-laws"),
        }
        ok_pat, data_pat, err_pat = self.cmd_insert_pattern(pattern_params)

        # Stage the law for migration tracking
        if ok_law:
            self.cmd_stage_law({
                "source_id": str(data_law["law_id"]),
                "source_table": "law",
                "target_id": data_law["law_id"],
            })

        if ok_law and ok_pat:
            return (1, {
                "law_id": data_law["law_id"],
                "pattern_id": data_pat["pattern_id"],
                "name": params.get("name", ""),
            }, None)
        else:
            errors = []
            if err_law:
                errors.append(str(err_law))
            if err_pat:
                errors.append(str(err_pat))
            return (0, None, ("LESSON_INSERT_PARTIAL", "; ".join(errors), 0))

    # ── Batch insert lessons ──

    def cmd_batch_lessons(self, params):
        """Insert multiple lessons at once using prepared statements.

        params:
            lessons — list of lesson dicts, each with:
                name, statement, reasoning, enforcement,
                domain_id, status_id, priority_id, severity_id,
                confidence_id, type_id, category_id
        """
        lessons = params.get("lessons", [])
        if not lessons:
            return (0, None, ("NO_LESSONS", "no lessons provided", 0))

        results = []
        errors = []
        for lesson in lessons:
            ok, data, err = self.cmd_insert_lesson(lesson)
            if ok:
                results.append(data)
            else:
                errors.append(str(err))

        return (1, {
            "total": len(lessons),
            "inserted": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }, None)

    # ── Stage law for migration tracking ──

    def cmd_stage_law(self, params):
        """Stage a law for migration tracking using prepared statement."""
        conn = self._get_conn()
        if conn is None:
            return (0, None, ("LAW_NO_CONN", self.state["last_error"], 0))

        sql = (
            "INSERT INTO lawStaging "
            "(sourceId, sourceTable, migrateStatus, targetId) "
            "VALUES (%s, %s, %s, %s)"
        )
        values = (
            params.get("source_id", ""),
            params.get("source_table", "law"),
            params.get("migrate_status", "complete"),
            params.get("target_id"),
        )

        try:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            staging_id = cursor.lastrowid
            cursor.close()
            return (1, {"staging_id": staging_id}, None)
        except Exception as e:
            return (0, None, ("STAGE_FAILED", str(e), 0))

    # ── Read: get law by name ──

    def cmd_get_law(self, params):
        """Get a law by name using prepared statement."""
        conn = self._get_conn()
        if conn is None:
            return (0, None, ("LAW_NO_CONN", self.state["last_error"], 0))

        sql = "SELECT id, name, statement, reasoning, enforcement FROM law WHERE name = %s"
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, (params.get("name", ""),))
            row = cursor.fetchone()
            cursor.close()
            if row:
                return (1, row, None)
            else:
                return (0, None, ("LAW_NOT_FOUND", params.get("name", ""), 0))
        except Exception as e:
            return (0, None, ("LAW_QUERY_FAILED", str(e), 0))

    # ── Read: list laws by domain ──

    def cmd_list_laws(self, params):
        """List laws by domain_id using prepared statement."""
        conn = self._get_conn()
        if conn is None:
            return (0, None, ("LAW_NO_CONN", self.state["last_error"], 0))

        domain_id = params.get("domain_id", 186)
        limit = params.get("limit", 20)
        sql = "SELECT id, name, statement FROM law WHERE domainId = %s ORDER BY id DESC LIMIT %s"
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, (domain_id, limit))
            rows = cursor.fetchall()
            cursor.close()
            return (1, {"count": len(rows), "laws": rows}, None)
        except Exception as e:
            return (0, None, ("LAW_QUERY_FAILED", str(e), 0))
