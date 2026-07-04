#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/InRamDb.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="In-RAM SQLite connection + schema for MemUnit event-sourcing. :memory: DB is the working projection, rebuilt on every startup from the durable event-log file."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="InRamDb.py" domain="ram_db" authority="InRamDb"}
# [@SUMMARY]{summary="Opens :memory: SQLite, creates all 11 MemUnit tables, single connection, BEGIN/COMMIT transactions. Disposable - rebuildable from event log at any time."}
# [@CLASS]{class="InRamDb" domain="ram_db" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="Open" type="command"}
# [@METHOD]{method="InitSchema" type="command"}
# [@METHOD]{method="Close" type="command"}
# [@METHOD]{method="Execute" type="command"}
# [@METHOD]{method="Query" type="query"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<In-RAM SQLite working projection for MemUnit event-sourcing. Opens :memory: DB, creates 11 tables, single connection. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}
"""
InRamDb -- In-RAM SQLite working projection for MemUnit event-sourcing.

The :memory: database is the live working state. It is rebuilt on every
startup by replaying the durable event-log file. It can be dropped at any
time and rebuilt from the event log + snapshots.

Tables (all in :memory:):
  mu_events, mu_ast_nodes, mu_ast_versions, mu_bcl_stamps,
  mu_trace_steps, mu_dependency_edges, mu_node_state, mu_edge_state,
  mu_semantic_tags, mu_execution_state, mu_snapshots

Usage:
  db = InRamDb()
  db.Run("open", {})
  db.Run("init_schema", {})
  ok, data, err = db.Run("execute", {"sql": "INSERT INTO ...", "params": [...]})
  ok, rows, err = db.Run("query", {"sql": "SELECT ...", "params": [...]})
"""
import sqlite3
from typing import Any, Dict, List, Tuple

SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS mu_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL CHECK (type IN (
            'EVENT_NODE_CREATED','EVENT_NODE_UPDATED','EVENT_STATE_CHANGED',
            'EVENT_EDGE_CREATED','EVENT_TAG_ADDED','EVENT_TASK_STARTED',
            'EVENT_TASK_COMPLETED','EVENT_ERROR_RAISED','EVENT_CODE_GRAPH_CHANGED',
            'EVENT_AST_NODE_CREATED','EVENT_AST_VERSION_ADDED','EVENT_AST_NODE_DESTROYED',
            'EVENT_BCL_STAMP_ATTACHED','EVENT_BCL_STAMP_SUPERSEDED',
            'EVENT_TRACE_STEP_APPENDED','EVENT_DEPENDENCY_EDGE_ADDED',
            'EVENT_ROLLBACK','EVENT_CHECKPOINT'
        )),
        ts TEXT NOT NULL,
        target_node INTEGER,
        target_edge INTEGER,
        ast_node_id INTEGER,
        ast_version_before INTEGER,
        ast_version_after INTEGER,
        trace_id TEXT,
        session_id TEXT,
        parent_event_id INTEGER,
        cause TEXT,
        before_state TEXT,
        after_state TEXT,
        event_hash TEXT
    )""",
    """CREATE INDEX IF NOT EXISTS idx_events_type ON mu_events(type)""",
    """CREATE INDEX IF NOT EXISTS idx_events_node ON mu_events(ast_node_id)""",
    """CREATE INDEX IF NOT EXISTS idx_events_trace ON mu_events(trace_id)""",
    """CREATE INDEX IF NOT EXISTS idx_events_session ON mu_events(session_id)""",
    """CREATE INDEX IF NOT EXISTS idx_events_parent ON mu_events(parent_event_id)""",
    """CREATE INDEX IF NOT EXISTS idx_events_ts ON mu_events(ts)""",
    """CREATE TABLE IF NOT EXISTS mu_ast_nodes (
        node_id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_type TEXT NOT NULL CHECK (node_type IN ('FILE','CLASS','METHOD','BLOCK')),
        symbolic_name TEXT NOT NULL,
        parent_node_id INTEGER,
        file_path TEXT,
        line_range TEXT,
        hash_base TEXT NOT NULL,
        created_event_id INTEGER NOT NULL,
        destroyed_event_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (parent_node_id) REFERENCES mu_ast_nodes(node_id)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_nodes_type ON mu_ast_nodes(node_type)""",
    """CREATE INDEX IF NOT EXISTS idx_nodes_parent ON mu_ast_nodes(parent_node_id)""",
    """CREATE INDEX IF NOT EXISTS idx_nodes_symbolic ON mu_ast_nodes(symbolic_name)""",
    """CREATE INDEX IF NOT EXISTS idx_nodes_file ON mu_ast_nodes(file_path)""",
    """CREATE INDEX IF NOT EXISTS idx_nodes_live ON mu_ast_nodes(destroyed_event_id)""",
    """CREATE TABLE IF NOT EXISTS mu_ast_versions (
        version_id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id INTEGER NOT NULL,
        version_no INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        content_blob TEXT,
        content_format TEXT NOT NULL CHECK (content_format IN ('SOURCE','AST_JSON')),
        blob_uri TEXT,
        created_event_id INTEGER NOT NULL,
        superseded_event_id INTEGER,
        is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
        created_at TEXT NOT NULL,
        UNIQUE (node_id, version_no),
        FOREIGN KEY (node_id) REFERENCES mu_ast_nodes(node_id)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_versions_node ON mu_ast_versions(node_id)""",
    """CREATE INDEX IF NOT EXISTS idx_versions_hash ON mu_ast_versions(content_hash)""",
    """CREATE INDEX IF NOT EXISTS idx_versions_current ON mu_ast_versions(node_id, is_current)""",
    """CREATE TABLE IF NOT EXISTS mu_bcl_stamps (
        stamp_id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id INTEGER NOT NULL,
        ast_version_id INTEGER NOT NULL,
        trace_id TEXT NOT NULL,
        scope_binding TEXT NOT NULL CHECK (scope_binding IN ('FULL','PARTIAL','DELTA')),
        coverage_detail TEXT,
        intent_vector TEXT NOT NULL,
        dependency_set TEXT NOT NULL,
        event_refs TEXT NOT NULL,
        state_status TEXT NOT NULL CHECK (state_status IN ('ACTIVE','STALE','BROKEN','DERIVED')) DEFAULT 'ACTIVE',
        confidence_score REAL NOT NULL DEFAULT 1.0,
        validation_state TEXT NOT NULL CHECK (validation_state IN ('UNVERIFIED','VERIFIED','FAILED')) DEFAULT 'UNVERIFIED',
        created_event_id INTEGER NOT NULL,
        superseded_by INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (node_id) REFERENCES mu_ast_nodes(node_id),
        FOREIGN KEY (ast_version_id) REFERENCES mu_ast_versions(version_id),
        FOREIGN KEY (superseded_by) REFERENCES mu_bcl_stamps(stamp_id)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_stamps_node ON mu_bcl_stamps(node_id)""",
    """CREATE INDEX IF NOT EXISTS idx_stamps_version ON mu_bcl_stamps(ast_version_id)""",
    """CREATE INDEX IF NOT EXISTS idx_stamps_trace ON mu_bcl_stamps(trace_id)""",
    """CREATE INDEX IF NOT EXISTS idx_stamps_status ON mu_bcl_stamps(state_status)""",
    """CREATE INDEX IF NOT EXISTS idx_stamps_active ON mu_bcl_stamps(superseded_by)""",
    """CREATE TABLE IF NOT EXISTS mu_trace_steps (
        step_id INTEGER PRIMARY KEY AUTOINCREMENT,
        trace_id TEXT NOT NULL,
        step_no INTEGER NOT NULL,
        decision TEXT NOT NULL,
        input_nodes TEXT NOT NULL,
        transformation TEXT NOT NULL,
        output_nodes TEXT NOT NULL,
        event_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (trace_id, step_no)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_trace_steps_trace ON mu_trace_steps(trace_id)""",
    """CREATE INDEX IF NOT EXISTS idx_trace_steps_step ON mu_trace_steps(trace_id, step_no)""",
    """CREATE TABLE IF NOT EXISTS mu_dependency_edges (
        edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_node_id INTEGER NOT NULL,
        to_node_id INTEGER NOT NULL,
        from_version_id INTEGER NOT NULL,
        to_version_id INTEGER,
        edge_type TEXT NOT NULL CHECK (edge_type IN ('READS','WRITES','CALLS','IMPORTS','INHERITS','GRAPH')),
        evidence_event_id INTEGER NOT NULL,
        validity_state TEXT NOT NULL CHECK (validity_state IN ('VALID','SUPERSEDED','BROKEN')) DEFAULT 'VALID',
        created_at TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS idx_edges_from ON mu_dependency_edges(from_node_id)""",
    """CREATE INDEX IF NOT EXISTS idx_edges_to ON mu_dependency_edges(to_node_id)""",
    """CREATE INDEX IF NOT EXISTS idx_edges_from_ver ON mu_dependency_edges(from_version_id)""",
    """CREATE INDEX IF NOT EXISTS idx_edges_type ON mu_dependency_edges(edge_type)""",
    """CREATE INDEX IF NOT EXISTS idx_edges_validity ON mu_dependency_edges(validity_state)""",
    """CREATE TABLE IF NOT EXISTS mu_node_state (
        node_id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_type TEXT NOT NULL,
        semantic_tag TEXT,
        current_state TEXT NOT NULL DEFAULT 'OPEN',
        version INTEGER NOT NULL DEFAULT 1,
        title TEXT,
        content TEXT,
        uncertainty TEXT,
        parent_id INTEGER,
        root_id INTEGER,
        bcl_method_id INTEGER,
        bcl_class_id INTEGER,
        confidence REAL NOT NULL DEFAULT 1.0,
        last_touch TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS idx_node_state_state ON mu_node_state(current_state)""",
    """CREATE INDEX IF NOT EXISTS idx_node_state_root ON mu_node_state(root_id)""",
    """CREATE TABLE IF NOT EXISTS mu_edge_state (
        edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_node INTEGER NOT NULL,
        to_node INTEGER NOT NULL,
        edge_type TEXT NOT NULL,
        strength REAL NOT NULL DEFAULT 1.0,
        validity_state TEXT NOT NULL DEFAULT 'VALID',
        evidence TEXT,
        certainty TEXT NOT NULL DEFAULT 'PROBABLE',
        last_touch TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS idx_edge_state_from ON mu_edge_state(from_node)""",
    """CREATE INDEX IF NOT EXISTS idx_edge_state_to ON mu_edge_state(to_node)""",
    """CREATE TABLE IF NOT EXISTS mu_semantic_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id INTEGER NOT NULL,
        tag TEXT NOT NULL,
        confidence_score REAL NOT NULL DEFAULT 0.5,
        source TEXT NOT NULL DEFAULT 'manual'
    )""",
    """CREATE INDEX IF NOT EXISTS idx_tags_node ON mu_semantic_tags(node_id)""",
    """CREATE TABLE IF NOT EXISTS mu_execution_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        active_node INTEGER,
        execution_path TEXT,
        open_loops TEXT,
        blocked_by TEXT,
        last_error TEXT,
        active_ast_versions TEXT,
        rollback_point_event INTEGER,
        last_rollback_at TEXT,
        last_touch TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS idx_exec_task ON mu_execution_state(task_id)""",
    """CREATE INDEX IF NOT EXISTS idx_exec_rollback ON mu_execution_state(rollback_point_event)""",
    """CREATE TABLE IF NOT EXISTS mu_snapshots (
        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        taken_at_event_id INTEGER NOT NULL,
        taken_at_ts TEXT NOT NULL,
        snapshot_file TEXT NOT NULL,
        ast_node_versions TEXT NOT NULL,
        active_stamps TEXT NOT NULL,
        trace_ids TEXT NOT NULL,
        dependency_edge_ids TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS idx_snapshots_event ON mu_snapshots(taken_at_event_id)""",
]


class InRamDb:
    """In-RAM SQLite working projection. Disposable. Rebuildable."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": ":memory:",
            },
            "conn": None,
            "stats": {
                "opened": 0,
                "executes": 0,
                "queries": 0,
                "transactions": 0,
            },
        }
        if param:
            self.state["config"].update(param)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "open": self.Open,
            "init_schema": self.InitSchema,
            "close": self.Close,
            "execute": self.Execute,
            "executemany": self.ExecuteMany,
            "query": self.Query,
            "begin": self.Begin,
            "commit": self.Commit,
            "rollback_tx": self.RollbackTx,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def Open(self, params):
        path = self._p(params, "db_path", self.state["config"]["db_path"])
        try:
            self.state["conn"] = sqlite3.connect(path)
            self.state["conn"].row_factory = sqlite3.Row
            self.state["conn"].execute("PRAGMA journal_mode=MEMORY")
            self.state["conn"].execute("PRAGMA synchronous=OFF")
            self.state["conn"].execute("PRAGMA foreign_keys=ON")
        except Exception as ex:
            return (0, None, ("OPEN_FAILED", str(ex), 0))
        self.state["stats"]["opened"] += 1
        return (1, {"db_path": path, "open": True}, None)

    def InitSchema(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "not open", 0))
        cur = self.state["conn"].cursor()
        for stmt in SCHEMA_SQL:
            cur.execute(stmt)
        self.state["conn"].commit()
        cur.close()
        return (1, {"statements_executed": len(SCHEMA_SQL)}, None)

    def Close(self, params):
        if self.state["conn"]:
            self.state["conn"].close()
            self.state["conn"] = None
        return (1, {"closed": True}, None)

    def Execute(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "not open", 0))
        sql = self._p(params, "sql")
        if not sql:
            return (0, None, ("MISSING_SQL", "sql required", 0))
        sql_params = self._p(params, "params", [])
        try:
            cur = self.state["conn"].cursor()
            cur.execute(sql, sql_params)
            self.state["conn"].commit()
            last_id = cur.lastrowid
            rowcount = cur.rowcount
            cur.close()
        except Exception as ex:
            return (0, None, ("EXEC_FAILED", str(ex), 0))
        self.state["stats"]["executes"] += 1
        return (1, {"lastrowid": last_id, "rowcount": rowcount}, None)

    def ExecuteMany(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "not open", 0))
        sql = self._p(params, "sql")
        if not sql:
            return (0, None, ("MISSING_SQL", "sql required", 0))
        seq = self._p(params, "seq", [])
        try:
            cur = self.state["conn"].cursor()
            cur.executemany(sql, seq)
            self.state["conn"].commit()
            rowcount = cur.rowcount
            cur.close()
        except Exception as ex:
            return (0, None, ("EXEC_FAILED", str(ex), 0))
        self.state["stats"]["executes"] += 1
        return (1, {"rowcount": rowcount}, None)

    def Query(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "not open", 0))
        sql = self._p(params, "sql")
        if not sql:
            return (0, None, ("MISSING_SQL", "sql required", 0))
        sql_params = self._p(params, "params", [])
        try:
            cur = self.state["conn"].cursor()
            cur.execute(sql, sql_params)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.close()
        except Exception as ex:
            return (0, None, ("QUERY_FAILED", str(ex), 0))
        self.state["stats"]["queries"] += 1
        return (1, {"rows": rows, "count": len(rows), "columns": cols}, None)

    def Begin(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "not open", 0))
        self.state["conn"].execute("BEGIN")
        return (1, {"begun": True}, None)

    def Commit(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "not open", 0))
        self.state["conn"].commit()
        self.state["stats"]["transactions"] += 1
        return (1, {"committed": True}, None)

    def RollbackTx(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "not open", 0))
        self.state["conn"].rollback()
        return (1, {"rolled_back": True}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "stats": self.state["stats"],
            "open": self.state["conn"] is not None,
        }, None)

    def set_config(self, params):
        for key in ("db_path",):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        return (1, {"config": self.state["config"]}, None)
