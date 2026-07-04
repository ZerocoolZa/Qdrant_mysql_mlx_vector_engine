#!/usr/bin/env python3
#[@GHOST]{file_path="core/Dom_Common/ClassRules.py" date="2026-07-04" author="devin" session_id="bcl-common-module" context="VBStyle rule checker, editor, updater, creator. Checks .py files against VBSTYLE_RULES, manages learned_rules in MySQL. The law of the codebase."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="ClassRules.py" domain="dom_common" authority="ClassRules"}
#[@SUMMARY]{summary="ClassRules — VBStyle rule checker/editor/updater/creator. Checks .py files against VBSTYLE_RULES (NoPrint, NoDecorators, NoSelfUnderscore, GhostHeader, VBStyleHeader, RunDispatch, PascalCase, NoTabs, NoTrailingWs). Manages learned_rules table in MySQL: create, update, edit, list, get."}
#[@CLASS]{class="ClassRules" domain="dom_common" authority="rules"}
#[@METHOD]{method="check_file" type="checker"}
#[@METHOD]{method="check_dir" type="checker"}
#[@METHOD]{method="create" type="writer"}
#[@METHOD]{method="update" type="writer"}
#[@METHOD]{method="edit" type="writer"}
#[@METHOD]{method="list_rules" type="reader"}
#[@METHOD]{method="get_rule" type="reader"}
#[@METHOD]{method="read_state" type="state"}
#[@METHOD]{method="set_config" type="config"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="_p" type="helper"}

"""ClassRules — VBStyle rule checker, editor, updater, creator.

This class is the law of the codebase. It checks .py files against
the VBSTYLE_RULES defined in Config, and manages the learned_rules
table in MySQL (create, update, edit, list, get).

VBStyle rules enforced:
  NoPrint          — no print() calls
  NoDecorators     — no @property, @staticmethod, @classmethod
  NoSelfUnderscore — no self._ patterns
  GhostHeader      — file has [@GHOST] in first 500 chars
  VBStyleHeader    — file has [@VBSTYLE] in first 500 chars
  RunDispatch      — if file has 'class ', it must have 'def Run'
  PascalCase       — if file has 'class X', X starts with uppercase
  NoTabs           — no tab characters
  NoTrailingWs     — no trailing whitespace on lines
"""

import os
import re

import mysql.connector

try:
    from Config import (
    VBSTYLE_RULES,
    MYSQL_HOST,
    MYSQL_USER,
    MYSQL_PASS,
    MYSQL_SOCKET,
    MYSQL_DB,
    MIN_CONFIDENCE,
)
except ImportError:
    from .Config import (
    VBSTYLE_RULES,
    MYSQL_HOST,
    MYSQL_USER,
    MYSQL_PASS,
    MYSQL_SOCKET,
    MYSQL_DB,
    MIN_CONFIDENCE,
)

# ── Error Codes ──
ERR_UNKNOWN_CMD = "RULES_UNKNOWN_COMMAND"
ERR_BAD_PARAMS = "RULES_BAD_PARAMS"
ERR_FILE_READ = "RULES_FILE_READ_ERROR"
ERR_MYSQL_CONNECT = "RULES_MYSQL_CONNECT_ERROR"
ERR_MYSQL_QUERY = "RULES_MYSQL_QUERY_ERROR"
ERR_RULE_EXISTS = "RULES_RULE_EXISTS"
ERR_RULE_NOT_FOUND = "RULES_RULE_NOT_FOUND"

# ── Decorators to detect ──
FORBIDDEN_DECORATORS = ("@property", "@staticmethod", "@classmethod")

# ── Regex patterns ──
RE_PRINT = re.compile(r"\bprint\s*\(")
RE_CLASS_DEF = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
RE_SELF_UNDERSCORE = re.compile(r"\bself\._")


class ClassRules:
    """VBStyle rule checker/editor/updater/creator. The law of the codebase."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param
        self.state = {
            "class": "ClassRules",
            "initialized": True,
            "total_checks": 0,
            "total_violations": 0,
            "last_path": None,
            "last_error": None,
            "mysql_connected": False,
            "config": {},
        }

    def _p(self, label, value):
        """Helper to log state transitions. No-op safe."""
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "check_file": self.cmd_check_file,
            "check_dir": self.cmd_check_dir,
            "create": self.cmd_create,
            "update": self.cmd_update,
            "edit": self.cmd_edit,
            "list_rules": self.cmd_list_rules,
            "get_rule": self.cmd_get_rule,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (ERR_UNKNOWN_CMD, "Unknown command: " + str(command), 0))
        return handler(params)

    # ── Command handlers ──

    def cmd_check_file(self, params):
        """Check a single .py file against VBSTYLE_RULES."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict with 'path'", 0))
        path = params.get("path")
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path' key", 0))
        if not isinstance(path, str):
            return (0, None, (ERR_BAD_PARAMS, "path must be a string", 0))
        if not os.path.isfile(path):
            return (0, None, (ERR_FILE_READ, "file not found: " + path, 0))
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            self.state["last_error"] = str(exc)
            return (0, None, (ERR_FILE_READ, "cannot read file: " + str(exc), 0))
        violations = self._check_content(content)
        count = len(violations)
        compliant = count == 0
        self.state["total_checks"] = self.state.get("total_checks", 0) + 1
        self.state["total_violations"] = self.state.get("total_violations", 0) + count
        self.state["last_path"] = path
        self._p("check_file", count)
        result = {
            "violations": violations,
            "compliant": compliant,
            "count": count,
        }
        return (1, result, None)

    def cmd_check_dir(self, params):
        """Walk a directory and check every .py file."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict with 'path'", 0))
        path = params.get("path")
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path' key", 0))
        if not isinstance(path, str):
            return (0, None, (ERR_BAD_PARAMS, "path must be a string", 0))
        if not os.path.isdir(path):
            return (0, None, (ERR_FILE_READ, "directory not found: " + path, 0))
        files = []
        total_violations = 0
        compliant = 0
        violating = 0
        for root, dirs, filenames in os.walk(path):
            for fname in sorted(filenames):
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                ok, data, err = self.cmd_check_file({"path": fpath})
                if ok != 1:
                    files.append({
                        "path": fpath,
                        "error": err[1] if err else "unknown",
                        "violations": [],
                        "compliant": False,
                        "count": 0,
                    })
                    violating = violating + 1
                    continue
                vcount = data.get("count", 0)
                total_violations = total_violations + vcount
                if data.get("compliant", False):
                    compliant = compliant + 1
                else:
                    violating = violating + 1
                files.append({
                    "path": fpath,
                    "violations": data.get("violations", []),
                    "compliant": data.get("compliant", False),
                    "count": vcount,
                })
        self._p("check_dir", len(files))
        result = {
            "files": files,
            "total_violations": total_violations,
            "compliant": compliant,
            "violating": violating,
        }
        return (1, result, None)

    def cmd_create(self, params):
        """Create a new rule in MySQL learned_rules table."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        rule_name = params.get("rule_name")
        rule_def = params.get("rule_def")
        if rule_name is None or rule_def is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'rule_name' or 'rule_def'", 0))
        if not isinstance(rule_name, str):
            return (0, None, (ERR_BAD_PARAMS, "rule_name must be a string", 0))
        if not isinstance(rule_def, dict):
            return (0, None, (ERR_BAD_PARAMS, "rule_def must be a dict", 0))
        ok, conn, err = self._connect_mysql()
        if ok != 1:
            return (0, None, err)
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT pattern FROM learned_rules WHERE pattern = %s LIMIT 1",
                (rule_name,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                cursor.close()
                return (0, None, (ERR_RULE_EXISTS, "rule already exists: " + rule_name, 0))
            pattern = rule_name
            fix_action = rule_def.get("fix_action", "")
            confidence = rule_def.get("confidence", MIN_CONFIDENCE)
            description = rule_def.get("description", "")
            cursor.execute(
                "INSERT INTO learned_rules (pattern, fix_action, confidence, description) "
                "VALUES (%s, %s, %s, %s)",
                (pattern, fix_action, confidence, description),
            )
            conn.commit()
            cursor.close()
        except mysql.connector.Error as exc:
            self.state["last_error"] = str(exc)
            self._close_mysql(conn)
            return (0, None, (ERR_MYSQL_QUERY, "create failed: " + str(exc), 0))
        self._close_mysql(conn)
        self._p("create", rule_name)
        result = {"created": True, "rule": rule_name}
        return (1, result, None)

    def cmd_update(self, params):
        """Update an existing rule in MySQL learned_rules table."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        rule_name = params.get("rule_name")
        new_def = params.get("new_def")
        if rule_name is None or new_def is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'rule_name' or 'new_def'", 0))
        if not isinstance(rule_name, str):
            return (0, None, (ERR_BAD_PARAMS, "rule_name must be a string", 0))
        if not isinstance(new_def, dict):
            return (0, None, (ERR_BAD_PARAMS, "new_def must be a dict", 0))
        ok, conn, err = self._connect_mysql()
        if ok != 1:
            return (0, None, err)
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT pattern FROM learned_rules WHERE pattern = %s LIMIT 1",
                (rule_name,),
            )
            existing = cursor.fetchone()
            if existing is None:
                cursor.close()
                return (0, None, (ERR_RULE_NOT_FOUND, "rule not found: " + rule_name, 0))
            fix_action = new_def.get("fix_action", None)
            confidence = new_def.get("confidence", None)
            description = new_def.get("description", None)
            fields = []
            values = []
            if fix_action is not None:
                fields.append("fix_action = %s")
                values.append(fix_action)
            if confidence is not None:
                fields.append("confidence = %s")
                values.append(confidence)
            if description is not None:
                fields.append("description = %s")
                values.append(description)
            if len(fields) == 0:
                cursor.close()
                return (0, None, (ERR_BAD_PARAMS, "new_def has no updatable fields", 0))
            values.append(rule_name)
            sql = "UPDATE learned_rules SET " + ", ".join(fields) + " WHERE pattern = %s"
            cursor.execute(sql, tuple(values))
            conn.commit()
            cursor.close()
        except mysql.connector.Error as exc:
            self.state["last_error"] = str(exc)
            self._close_mysql(conn)
            return (0, None, (ERR_MYSQL_QUERY, "update failed: " + str(exc), 0))
        self._close_mysql(conn)
        self._p("update", rule_name)
        result = {"updated": True, "rule": rule_name}
        return (1, result, None)

    def cmd_edit(self, params):
        """Edit a single field of a rule in MySQL."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        rule_name = params.get("rule_name")
        field = params.get("field")
        value = params.get("value")
        if rule_name is None or field is None or value is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'rule_name', 'field', or 'value'", 0))
        if not isinstance(rule_name, str) or not isinstance(field, str):
            return (0, None, (ERR_BAD_PARAMS, "rule_name and field must be strings", 0))
        allowed_fields = ("fix_action", "confidence", "description", "pattern")
        if field not in allowed_fields:
            return (0, None, (ERR_BAD_PARAMS, "field must be one of: " + ", ".join(allowed_fields), 0))
        ok, conn, err = self._connect_mysql()
        if ok != 1:
            return (0, None, err)
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT pattern FROM learned_rules WHERE pattern = %s LIMIT 1",
                (rule_name,),
            )
            existing = cursor.fetchone()
            if existing is None:
                cursor.close()
                return (0, None, (ERR_RULE_NOT_FOUND, "rule not found: " + rule_name, 0))
            sql = "UPDATE learned_rules SET " + field + " = %s WHERE pattern = %s"
            cursor.execute(sql, (value, rule_name))
            conn.commit()
            cursor.close()
        except mysql.connector.Error as exc:
            self.state["last_error"] = str(exc)
            self._close_mysql(conn)
            return (0, None, (ERR_MYSQL_QUERY, "edit failed: " + str(exc), 0))
        self._close_mysql(conn)
        self._p("edit", rule_name)
        result = {"edited": True, "rule": rule_name, "field": field}
        return (1, result, None)

    def cmd_list_rules(self, params):
        """List all rules from MySQL learned_rules table."""
        ok, conn, err = self._connect_mysql()
        if ok != 1:
            return (0, None, err)
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT pattern, fix_action, confidence FROM learned_rules ORDER BY pattern"
            )
            rows = cursor.fetchall()
            cursor.close()
        except mysql.connector.Error as exc:
            self.state["last_error"] = str(exc)
            self._close_mysql(conn)
            return (0, None, (ERR_MYSQL_QUERY, "list failed: " + str(exc), 0))
        self._close_mysql(conn)
        rules = []
        for row in rows:
            rules.append({
                "pattern": row.get("pattern"),
                "fix_action": row.get("fix_action"),
                "confidence": row.get("confidence"),
            })
        self._p("list_rules", len(rules))
        result = {"rules": rules}
        return (1, result, None)

    def cmd_get_rule(self, params):
        """Get a single rule by pattern from MySQL."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict with 'rule_name'", 0))
        rule_name = params.get("rule_name")
        if rule_name is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'rule_name' key", 0))
        if not isinstance(rule_name, str):
            return (0, None, (ERR_BAD_PARAMS, "rule_name must be a string", 0))
        ok, conn, err = self._connect_mysql()
        if ok != 1:
            return (0, None, err)
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT pattern, fix_action, confidence, description "
                "FROM learned_rules WHERE pattern = %s LIMIT 1",
                (rule_name,),
            )
            row = cursor.fetchone()
            cursor.close()
        except mysql.connector.Error as exc:
            self.state["last_error"] = str(exc)
            self._close_mysql(conn)
            return (0, None, (ERR_MYSQL_QUERY, "get_rule failed: " + str(exc), 0))
        self._close_mysql(conn)
        if row is None:
            return (0, None, (ERR_RULE_NOT_FOUND, "rule not found: " + rule_name, 0))
        self._p("get_rule", rule_name)
        result = {"rule": {
            "pattern": row.get("pattern"),
            "fix_action": row.get("fix_action"),
            "confidence": row.get("confidence"),
            "description": row.get("description"),
        }}
        return (1, result, None)

    def cmd_read_state(self, params):
        """Return current state dict."""
        return (1, self.state, None)

    def cmd_set_config(self, params):
        """Set config from params dict."""
        if params is None:
            self.state["config"] = {}
            return (1, None, None)
        if not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        self.state["config"] = params
        self._p("config", list(params.keys()))
        return (1, None, None)

    # ── Internal: rule checking ──

    def _check_content(self, content):
        """Check file content against all VBSTYLE_RULES. Returns list of violation dicts."""
        violations = []
        lines = content.split("\n")
        header_region = content[:500]

        # NoPrint: no print() calls
        if RE_PRINT.search(content):
            for idx, line in enumerate(lines):
                if RE_PRINT.search(line):
                    violations.append({
                        "rule": "NoPrint",
                        "line": idx + 1,
                        "detail": "print() call found",
                    })

        # NoDecorators: no @property, @staticmethod, @classmethod
        for idx, line in enumerate(lines):
            stripped = line.strip()
            for dec in FORBIDDEN_DECORATORS:
                if stripped.startswith(dec):
                    violations.append({
                        "rule": "NoDecorators",
                        "line": idx + 1,
                        "detail": "forbidden decorator: " + dec,
                    })

        # NoSelfUnderscore: no self._ patterns
        for idx, line in enumerate(lines):
            if RE_SELF_UNDERSCORE.search(line):
                violations.append({
                    "rule": "NoSelfUnderscore",
                    "line": idx + 1,
                    "detail": "self._ pattern found",
                })

        # GhostHeader: file has [@GHOST] in first 500 chars
        if "[@GHOST]" not in header_region:
            violations.append({
                "rule": "GhostHeader",
                "line": 0,
                "detail": "missing [@GHOST] header in first 500 chars",
            })

        # VBStyleHeader: file has [@VBSTYLE] in first 500 chars
        if "[@VBSTYLE]" not in header_region:
            violations.append({
                "rule": "VBStyleHeader",
                "line": 0,
                "detail": "missing [@VBSTYLE] header in first 500 chars",
            })

        # RunDispatch: if file has 'class ', it must have 'def Run'
        has_class = "class " in content
        has_run = re.search(r"def\s+Run\s*\(", content) is not None
        if has_class and not has_run:
            violations.append({
                "rule": "RunDispatch",
                "line": 0,
                "detail": "file has 'class ' but no 'def Run' dispatch",
            })

        # PascalCase: if file has 'class X', X starts with uppercase
        for match in RE_CLASS_DEF.finditer(content):
            class_name = match.group(1)
            if class_name and not class_name[0].isupper():
                line_num = content[:match.start()].count("\n") + 1
                violations.append({
                    "rule": "PascalCase",
                    "line": line_num,
                    "detail": "class name '" + class_name + "' does not start with uppercase",
                })

        # NoTabs: no tab characters
        for idx, line in enumerate(lines):
            if "\t" in line:
                violations.append({
                    "rule": "NoTabs",
                    "line": idx + 1,
                    "detail": "tab character found",
                })

        # NoTrailingWs: no trailing whitespace on lines
        for idx, line in enumerate(lines):
            if len(line) > 0 and line != line.rstrip():
                violations.append({
                    "rule": "NoTrailingWs",
                    "line": idx + 1,
                    "detail": "trailing whitespace found",
                })

        return violations

    # ── Internal: MySQL ──

    def _connect_mysql(self):
        """Connect to MySQL. Returns Tuple3 (ok, conn, err)."""
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASS,
                database=MYSQL_DB,
                unix_socket=MYSQL_SOCKET,
            )
            self.state["mysql_connected"] = True
            return (1, conn, None)
        except mysql.connector.Error as exc:
            self.state["mysql_connected"] = False
            self.state["last_error"] = str(exc)
            return (0, None, (ERR_MYSQL_CONNECT, "connect failed: " + str(exc), 0))

    def _close_mysql(self, conn):
        """Close a MySQL connection safely."""
        try:
            if conn is not None and conn.is_connected():
                conn.close()
        except mysql.connector.Error:
            pass
        self.state["mysql_connected"] = False
