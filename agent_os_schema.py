#!/usr/bin/env python3
"""
Ghost: agent_os_schema
Class: AgentOsSchema
Method: Run / Connect / ListTables / DescribeTable / GetArtifact / InsertArtifact / LogEvent

VBStyle compliant: Run() dispatch, Tuple3 (ok, data, error), no decorators,
no print, no hardcoded values, PascalCase classes, UPPERCASE constants,
self.state dict (no self._).

Documents the agent_os MySQL schema (MASTER_PLAN Phase 1) and provides a
connection function plus CRUD helpers for the artifact, event_log,
agent_state, gui_config, and agent_registry tables.
"""

import hashlib
import json
from typing import Any, Dict, Tuple

import pymysql

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = ""
DB_NAME = "agent_os"

SCHEMA: Dict[str, Any] = {
    "database": "agent_os",
    "tables": {
        "artifact": {
            "purpose": "Code, notes, configs, schemas — the agent's persistent work products.",
            "columns": {
                "id": "BIGINT AUTO_INCREMENT PRIMARY KEY",
                "kind": "VARCHAR(50) NOT NULL  -- code|note|config|schema",
                "language": "VARCHAR(20)  -- python|c|swift|markdown|sql",
                "name": "VARCHAR(255)",
                "content": "LONGTEXT",
                "checksum": "VARCHAR(64)",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            },
            "indexes": ["idx_kind", "idx_language", "idx_name"],
        },
        "event_log": {
            "purpose": "Append-only event stream for agent actions and GUI events.",
            "columns": {
                "id": "BIGINT AUTO_INCREMENT PRIMARY KEY",
                "event_type": "VARCHAR(100) NOT NULL",
                "payload": "JSON",
                "timestamp": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            },
            "indexes": ["idx_event_type", "idx_timestamp"],
        },
        "agent_state": {
            "purpose": "Per-agent persistent state (JSON blob).",
            "columns": {
                "agent_id": "VARCHAR(100) PRIMARY KEY",
                "state_json": "JSON",
                "updated_at": "TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            },
            "indexes": [],
        },
        "gui_config": {
            "purpose": "DB-driven GUI layout config — widget specs as JSON.",
            "columns": {
                "widget_id": "VARCHAR(100) PRIMARY KEY",
                "config_json": "JSON",
                "updated_at": "TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            },
            "indexes": [],
        },
        "agent_registry": {
            "purpose": "Registry of known agents and their capabilities.",
            "columns": {
                "agent_id": "VARCHAR(100) PRIMARY KEY",
                "name": "VARCHAR(255) NOT NULL",
                "capabilities": "JSON",
                "registered_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            },
            "indexes": [],
        },
    },
}


class AgentOsSchema:
    """VBStyle schema manager + connection provider for the agent_os database."""

    def __init__(self, mem: Any = None, db: Any = None, param: Any = None):
        self.state: Dict[str, Any] = {
            "config": {
                "host": DB_HOST,
                "port": DB_PORT,
                "user": DB_USER,
                "password": DB_PASSWORD,
                "database": DB_NAME,
            },
            "catalog": [],
            "results": [],
        }
        self.mem = mem
        self.conn = None

    # ------------------------------------------------------------------
    # VBStyle dispatch
    # ------------------------------------------------------------------
    def Run(self, command: str, params: Dict[str, Any]) -> Tuple[int, Any, Any]:
        if command == "connect":
            return self.Connect(params)
        if command == "list_tables":
            return self.ListTables(params)
        if command == "describe_table":
            return self.DescribeTable(params)
        if command == "get_artifact":
            return self.GetArtifact(params)
        if command == "insert_artifact":
            return self.InsertArtifact(params)
        if command == "log_event":
            return self.LogEvent(params)
        if command == "get_schema":
            return (1, SCHEMA, None)
        if command == "read_state":
            return (1, self.state.copy(), None)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def Connect(self, params: Dict[str, Any]) -> Tuple[int, Any, Any]:
        try:
            cfg = dict(self.state["config"])
            if params:
                cfg.update(params)
            self.conn = pymysql.connect(
                host=cfg.get("host", DB_HOST),
                port=int(cfg.get("port", DB_PORT)),
                user=cfg.get("user", DB_USER),
                password=cfg.get("password", DB_PASSWORD),
                database=cfg.get("database", DB_NAME),
                autocommit=True,
            )
            self.state["connected"] = True
            return (1, {"connected": True, "database": cfg.get("database", DB_NAME)}, None)
        except Exception as e:
            return (0, None, ("CONNECT_ERROR", str(e), 0))

    def _cursor(self):
        if self.conn is None:
            ok, data, err = self.Connect({})
            if not ok:
                raise RuntimeError(err)
        return self.conn.cursor()

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------
    def ListTables(self, params: Dict[str, Any]) -> Tuple[int, Any, Any]:
        try:
            cur = self._cursor()
            cur.execute("SHOW TABLES")
            tables = [r[0] for r in cur.fetchall()]
            cur.close()
            self.state["catalog"] = tables
            return (1, tables, None)
        except Exception as e:
            return (0, None, ("LIST_TABLES_ERROR", str(e), 0))

    def DescribeTable(self, params: Dict[str, Any]) -> Tuple[int, Any, Any]:
        try:
            table = params.get("table", "")
            if not table:
                return (0, None, ("MISSING_PARAM", "table is required", 0))
            cur = self._cursor()
            cur.execute(f"DESCRIBE `{table}`")
            cols = [{"field": r[0], "type": r[1], "null": r[2], "key": r[3],
                     "default": r[4], "extra": r[5]} for r in cur.fetchall()]
            cur.close()
            return (1, cols, None)
        except Exception as e:
            return (0, None, ("DESCRIBE_ERROR", str(e), 0))

    # ------------------------------------------------------------------
    # Artifact CRUD
    # ------------------------------------------------------------------
    def GetArtifact(self, params: Dict[str, Any]) -> Tuple[int, Any, Any]:
        try:
            artifact_id = params.get("id")
            kind = params.get("kind")
            limit = int(params.get("limit", 100))
            cur = self._cursor()
            if artifact_id is not None:
                cur.execute("SELECT id,kind,language,name,content,checksum,created_at,updated_at "
                            "FROM artifact WHERE id=%s", (artifact_id,))
            elif kind is not None:
                cur.execute("SELECT id,kind,language,name,content,checksum,created_at,updated_at "
                            "FROM artifact WHERE kind=%s LIMIT %s", (kind, limit))
            else:
                cur.execute("SELECT id,kind,language,name,content,checksum,created_at,updated_at "
                            "FROM artifact LIMIT %s", (limit,))
            rows = cur.fetchall()
            cur.close()
            return (1, rows, None)
        except Exception as e:
            return (0, None, ("GET_ARTIFACT_ERROR", str(e), 0))

    def InsertArtifact(self, params: Dict[str, Any]) -> Tuple[int, Any, Any]:
        try:
            kind = params.get("kind", "")
            language = params.get("language")
            name = params.get("name")
            content = params.get("content", "")
            if not kind:
                return (0, None, ("MISSING_PARAM", "kind is required", 0))
            checksum = hashlib.sha256((content or "").encode()).hexdigest()
            cur = self._cursor()
            cur.execute(
                "INSERT INTO artifact (kind, language, name, content, checksum) "
                "VALUES (%s,%s,%s,%s,%s)",
                (kind, language, name, content, checksum),
            )
            new_id = cur.lastrowid
            cur.close()
            return (1, {"id": new_id, "checksum": checksum}, None)
        except Exception as e:
            return (0, None, ("INSERT_ARTIFACT_ERROR", str(e), 0))

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------
    def LogEvent(self, params: Dict[str, Any]) -> Tuple[int, Any, Any]:
        try:
            event_type = params.get("event_type", "")
            payload = params.get("payload", {})
            if not event_type:
                return (0, None, ("MISSING_PARAM", "event_type is required", 0))
            payload_str = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)
            cur = self._cursor()
            cur.execute(
                "INSERT INTO event_log (event_type, payload) VALUES (%s, %s)",
                (event_type, payload_str),
            )
            new_id = cur.lastrowid
            cur.close()
            return (1, {"id": new_id}, None)
        except Exception as e:
            return (0, None, ("LOG_EVENT_ERROR", str(e), 0))

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def read_state(self) -> Dict[str, Any]:
        return self.state.copy()

    def set_config(self, config: Dict[str, Any]) -> Tuple[int, Any, Any]:
        try:
            self.state["config"].update(config)
            return (1, self.state["config"].copy(), None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))


# ---------------------------------------------------------------------------
# Module-level connection helper (for non-VBStyle callers)
# ---------------------------------------------------------------------------
def get_connection(database: str = DB_NAME) -> "pymysql.Connection":
    """Return a pymysql connection to agent_os (or another DB if specified)."""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=database,
        autocommit=True,
    )


if __name__ == "__main__":
    # Smoke test
    schema = AgentOsSchema()
    ok, data, err = schema.Run("connect", {})
    if not ok:
        raise SystemExit(f"connect failed: {err}")
    ok, tables, err = schema.Run("list_tables", {})
    if not ok:
        raise SystemExit(f"list_tables failed: {err}")
    print(f"agent_os tables: {tables}")
    ok, arts, err = schema.Run("get_artifact", {"kind": "code", "limit": 3})
    if ok:
        print(f"sample code artifacts: {len(arts)} rows")
