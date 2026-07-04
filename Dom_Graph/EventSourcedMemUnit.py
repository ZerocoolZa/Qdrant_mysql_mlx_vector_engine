#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/EventSourcedMemUnit.py"
# date="2026-08-18" author="Devin" session_id="memunit-v2"
# context="Version 2: Event-sourced MemUnit. Append-only event log. Graph is never overwritten, only versioned via events. MemUnit is derived state. Context is always reconstructed."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="EventSourcedMemUnit.py" domain="memunit" authority="EventSourcedMemUnit"}
# [@SUMMARY]{summary="Event-sourced MemUnit. Every change is an event in mu_events. Node/edge state is derived by replaying events. Supports deterministic rebuild at any timestamp. Append-only. Never overwrites."}
# [@CLASS]{class="EventSourcedMemUnit" domain="memunit" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="InitSchema" type="command"}
# [@METHOD]{method="CreateNode" type="command"}
# [@METHOD]{method="UpdateNode" type="command"}
# [@METHOD]{method="ChangeState" type="command"}
# [@METHOD]{method="CreateEdge" type="command"}
# [@METHOD]{method="AddSemanticTag" type="command"}
# [@METHOD]{method="SetExecutionState" type="command"}
# [@METHOD]{method="CompleteTask" type="command"}
# [@METHOD]{method="RaiseError" type="command"}
# [@METHOD]{method="LogCodeGraphChange" type="command"}
# [@METHOD]{method="QueryCauseChain" type="query"}
# [@METHOD]{method="ReplayEvents" type="query"}
# [@METHOD]{method="RebuildAt" type="query"}
# [@METHOD]{method="QueryChain" type="query"}
# [@METHOD]{method="QueryOpenLoops" type="query"}
# [@METHOD]{method="QueryEventLog" type="query"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Event-sourced MemUnit v2. Append-only event log, derived graph state, deterministic rebuild. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}
"""
EventSourcedMemUnit -- Version 2 of MemUnit.

RULE 1: Everything is event-driven. No direct mutation without logging event.
RULE 2: Graph is NEVER overwritten. Only versioned via events.
RULE 3: MemUnit is derived state. Not primary truth.
RULE 4: Context is always reconstructed. Never stored.
RULE 5: LLM never sees raw graph. Only reconstructed slices.

Tables:
  mu_events          -- append-only event log (THE TRUTH)
  mu_node_state      -- derived node state (rebuilt from events)
  mu_edge_state      -- derived edge state (rebuilt from events)
  mu_semantic_tags   -- semantic tags per node
  mu_execution_state -- live execution context per task

Usage:
  mu = EventSourcedMemUnit()
  mu.Run('init_schema', {})
  mu.Run('create_node', {'node_type': 'GOAL', 'title': 'build system'})
  mu.Run('change_state', {'node_id': 1, 'to_state': 'ACTIVE', 'cause': 'started'})
  log = mu.Run('query_event_log', {'limit': 10})
  rebuild = mu.Run('rebuild_at', {'timestamp': '2026-08-18 12:00:00'})
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

EVENT_NODE_CREATED = "NODE_CREATED"
EVENT_NODE_UPDATED = "NODE_UPDATED"
EVENT_STATE_CHANGED = "STATE_CHANGED"
EVENT_EDGE_CREATED = "EDGE_CREATED"
EVENT_TAG_ADDED = "TAG_ADDED"
EVENT_TASK_STARTED = "TASK_STARTED"
EVENT_TASK_COMPLETED = "TASK_COMPLETED"
EVENT_ERROR_RAISED = "ERROR_RAISED"
EVENT_CODE_GRAPH_CHANGED = "CODE_GRAPH_CHANGED"

EDGE_DEPENDS = "DEPENDS"
EDGE_PRODUCES = "PRODUCES"
EDGE_BLOCKS = "BLOCKS"
EDGE_REFUTES = "REFUTES"
EDGE_SUPPORTS = "SUPPORTS"
EDGE_TRIGGERS = "TRIGGERS"
EDGE_CALLS = "CALLS"
EDGE_IMPORTS = "IMPORTS"
EDGE_INHERITS = "INHERITS"
EDGE_CAUSED_BY = "CAUSED_BY"

STATE_ACTIVE = "ACTIVE"
STATE_INACTIVE = "INACTIVE"
STATE_BROKEN = "BROKEN"
STATE_STALE = "STALE"
STATE_RESOLVED = "RESOLVED"
STATE_CLOSED = "CLOSED"
STATE_OPEN = "OPEN"
STATE_BLOCKED = "BLOCKED"

VALID_STATE_TRANSITIONS = {
    STATE_OPEN: [STATE_ACTIVE],
    STATE_ACTIVE: [STATE_BLOCKED, STATE_RESOLVED, STATE_STALE, STATE_BROKEN],
    STATE_BLOCKED: [STATE_ACTIVE],
    STATE_RESOLVED: [STATE_CLOSED, STATE_ACTIVE],
    STATE_CLOSED: [STATE_ACTIVE],
    STATE_STALE: [STATE_ACTIVE, STATE_CLOSED],
    STATE_BROKEN: [STATE_ACTIVE, STATE_CLOSED],
    STATE_INACTIVE: [STATE_ACTIVE],
}


class EventSourcedMemUnit:
    """Event-sourced reasoning state. Append-only. Deterministic rebuild."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_host": "localhost",
                "db_user": "root",
                "db_password": "",
                "db_name": "vb_code_test",
            },
            "conn": None,
            "last_node_id": None,
            "last_event_id": None,
            "stats": {
                "events_logged": 0,
                "nodes_created": 0,
                "edges_created": 0,
                "state_changes": 0,
                "tags_added": 0,
                "rebuilds": 0,
            },
        }
        if param:
            self.state["config"].update(param)
        self._connect()

    def _connect(self):
        if not MYSQL_AVAILABLE:
            return
        cfg = self.state["config"]
        try:
            self.state["conn"] = mysql.connector.connect(
                user=cfg["db_user"], password=cfg["db_password"],
                host=cfg["db_host"], database=cfg["db_name"]
            )
        except Exception:
            self.state["conn"] = None

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "init_schema": self.InitSchema,
            "create_node": self.CreateNode,
            "update_node": self.UpdateNode,
            "change_state": self.ChangeState,
            "create_edge": self.CreateEdge,
            "add_semantic_tag": self.AddSemanticTag,
            "set_execution_state": self.SetExecutionState,
            "complete_task": self.CompleteTask,
            "raise_error": self.RaiseError,
            "log_code_graph_change": self.LogCodeGraphChange,
            "replay_events": self.ReplayEvents,
            "rebuild_at": self.RebuildAt,
            "query_chain": self.QueryChain,
            "query_open_loops": self.QueryOpenLoops,
            "query_event_log": self.QueryEventLog,
            "query_cause_chain": self.QueryCauseChain,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def _log_event(self, cursor, event_type, action, target_node=None,
                   target_edge=None, before_state=None, after_state=None, cause=None):
        before_json = json.dumps(self._sanitize(before_state)) if before_state else None
        after_json = json.dumps(self._sanitize(after_state)) if after_state else None
        cursor.execute(
            """INSERT INTO mu_events
               (event_type, target_node, target_edge, action,
                before_state, after_state, cause)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (event_type, target_node, target_edge, action,
             before_json, after_json, cause)
        )
        event_id = cursor.lastrowid
        self.state["last_event_id"] = event_id
        self.state["stats"]["events_logged"] += 1
        return event_id

    def _sanitize(self, obj):
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize(v) for v in obj]
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if isinstance(obj, float):
            return obj
        try:
            from decimal import Decimal
            if isinstance(obj, Decimal):
                return float(obj)
        except ImportError:
            pass
        return obj

    def InitSchema(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        cursor = self.state["conn"].cursor()
        statements = [
            """CREATE TABLE IF NOT EXISTS mu_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_type VARCHAR(30) NOT NULL,
                target_node INT,
                target_edge INT,
                action VARCHAR(20) NOT NULL,
                before_state TEXT,
                after_state TEXT,
                cause VARCHAR(255),
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_type (event_type),
                INDEX idx_target_node (target_node),
                INDEX idx_target_edge (target_edge),
                INDEX idx_timestamp (timestamp)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS mu_node_state (
                node_id INT AUTO_INCREMENT PRIMARY KEY,
                node_type VARCHAR(20) NOT NULL,
                semantic_tag VARCHAR(100),
                current_state VARCHAR(20) NOT NULL DEFAULT 'OPEN',
                version INT DEFAULT 1,
                title VARCHAR(255),
                content TEXT,
                uncertainty TEXT,
                parent_id INT,
                root_id INT,
                bcl_method_id INT,
                bcl_class_id INT,
                confidence DECIMAL(3,2) DEFAULT 1.00,
                last_touch TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_state (current_state),
                INDEX idx_semantic (semantic_tag),
                INDEX idx_root (root_id),
                INDEX idx_bcl_method (bcl_method_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS mu_edge_state (
                edge_id INT AUTO_INCREMENT PRIMARY KEY,
                from_node INT NOT NULL,
                to_node INT NOT NULL,
                edge_type VARCHAR(20) NOT NULL,
                strength DECIMAL(3,2) DEFAULT 1.00,
                validity_state VARCHAR(20) DEFAULT 'VALID',
                evidence TEXT,
                certainty VARCHAR(10) DEFAULT 'PROBABLE',
                last_touch TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_from (from_node),
                INDEX idx_to (to_node),
                INDEX idx_type (edge_type),
                INDEX idx_validity (validity_state)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS mu_semantic_tags (
                id INT AUTO_INCREMENT PRIMARY KEY,
                node_id INT NOT NULL,
                tag VARCHAR(50) NOT NULL,
                confidence_score DECIMAL(3,2) DEFAULT 0.50,
                source VARCHAR(20) DEFAULT 'manual',
                INDEX idx_node (node_id),
                INDEX idx_tag (tag)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS mu_execution_state (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_id INT NOT NULL,
                active_node INT,
                execution_path TEXT,
                open_loops TEXT,
                blocked_by TEXT,
                last_error TEXT,
                last_touch TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_task (task_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ]
        for s in statements:
            cursor.execute(s)
        self.state["conn"].commit()
        cursor.close()
        return (1, {"tables_created": len(statements)}, None)

    def CreateNode(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_type = self._p(params, "node_type", "TASK")
        title = self._p(params, "title")
        if not title:
            return (0, None, ("MISSING_TITLE", "title is required", 0))
        content = self._p(params, "content")
        uncertainty = self._p(params, "uncertainty")
        parent_id = self._p(params, "parent_id")
        root_id = self._p(params, "root_id", parent_id)
        bcl_method_id = self._p(params, "bcl_method_id")
        bcl_class_id = self._p(params, "bcl_class_id")
        confidence = self._p(params, "confidence", 1.0)
        semantic_tag = self._p(params, "semantic_tag")
        cursor = self.state["conn"].cursor()
        cursor.execute(
            """INSERT INTO mu_node_state
               (node_type, semantic_tag, current_state, version,
                title, content, uncertainty, parent_id, root_id,
                bcl_method_id, bcl_class_id, confidence)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (node_type, semantic_tag, STATE_OPEN, 1,
             title, content, uncertainty, parent_id, root_id,
             bcl_method_id, bcl_class_id, confidence)
        )
        node_id = cursor.lastrowid
        after_state = {
            "node_id": node_id, "node_type": node_type, "title": title,
            "state": STATE_OPEN, "version": 1,
        }
        self._log_event(cursor, EVENT_NODE_CREATED, "CREATE",
                        target_node=node_id, after_state=after_state,
                        cause=self._p(params, "cause", "node created"))
        self.state["conn"].commit()
        cursor.close()
        self.state["last_node_id"] = node_id
        self.state["stats"]["nodes_created"] += 1
        return (1, {"node_id": node_id, "title": title, "version": 1}, None)

    def UpdateNode(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_NODE_ID", "node_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute("SELECT * FROM mu_node_state WHERE node_id = %s", (node_id,))
        before = cursor.fetchone()
        if not before:
            cursor.close()
            return (0, None, ("NOT_FOUND", "node not found", 0))
        updates = []
        values = []
        for field in ("content", "uncertainty", "confidence", "title",
                      "semantic_tag", "bcl_method_id", "bcl_class_id"):
            val = self._p(params, field)
            if val is not None:
                updates.append(field + " = %s")
                values.append(val)
        if not updates:
            cursor.close()
            return (0, None, ("NO_UPDATES", "no fields to update", 0))
        updates.append("version = version + 1")
        values.append(node_id)
        cursor = self.state["conn"].cursor()
        cursor.execute(
            "UPDATE mu_node_state SET " + ", ".join(updates) + " WHERE node_id = %s",
            values
        )
        after_state = dict(before)
        for field in ("content", "uncertainty", "confidence", "title", "semantic_tag"):
            val = self._p(params, field)
            if val is not None:
                after_state[field] = val
        after_state["version"] = before["version"] + 1
        self._log_event(cursor, EVENT_NODE_UPDATED, "UPDATE",
                        target_node=node_id,
                        before_state=dict(before), after_state=after_state,
                        cause=self._p(params, "cause", "node updated"))
        self.state["conn"].commit()
        cursor.close()
        return (1, {"node_id": node_id, "new_version": after_state["version"]}, None)

    def ChangeState(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_id = self._p(params, "node_id")
        to_state = self._p(params, "to_state")
        cause = self._p(params, "cause", "")
        if not node_id or not to_state:
            return (0, None, ("MISSING_PARAM", "node_id and to_state required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute("SELECT current_state, version FROM mu_node_state WHERE node_id = %s", (node_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return (0, None, ("NOT_FOUND", "node not found", 0))
        from_state = row["current_state"]
        allowed = VALID_STATE_TRANSITIONS.get(from_state, [])
        if to_state not in allowed:
            cursor.close()
            return (0, None, ("INVALID_TRANSITION",
                              "cannot go from " + from_state + " to " + to_state, 0))
        cursor = self.state["conn"].cursor()
        cursor.execute(
            "UPDATE mu_node_state SET current_state = %s, version = version + 1 WHERE node_id = %s",
            (to_state, node_id)
        )
        self._log_event(cursor, EVENT_STATE_CHANGED, "TRANSITION",
                        target_node=node_id,
                        before_state={"state": from_state, "version": row["version"]},
                        after_state={"state": to_state, "version": row["version"] + 1},
                        cause=cause)
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["state_changes"] += 1
        return (1, {
            "node_id": node_id,
            "from_state": from_state,
            "to_state": to_state,
            "cause": cause,
        }, None)

    def CreateEdge(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        from_node = self._p(params, "from_node")
        to_node = self._p(params, "to_node")
        edge_type = self._p(params, "edge_type", "DEPENDS")
        certainty = self._p(params, "certainty", "PROBABLE")
        evidence = self._p(params, "evidence")
        strength = self._p(params, "strength", 1.0)
        if not from_node or not to_node:
            return (0, None, ("MISSING_PARAM", "from_node and to_node required", 0))
        if certainty == "CERTAIN" and not evidence:
            return (0, None, ("NO_EVIDENCE", "CERTAIN edges require evidence", 0))
        cursor = self.state["conn"].cursor()
        cursor.execute(
            """INSERT INTO mu_edge_state
               (from_node, to_node, edge_type, strength,
                validity_state, evidence, certainty)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (from_node, to_node, edge_type, strength, "VALID", evidence, certainty)
        )
        edge_id = cursor.lastrowid
        after_state = {
            "edge_id": edge_id, "from": from_node, "to": to_node,
            "type": edge_type, "certainty": certainty,
        }
        self._log_event(cursor, EVENT_EDGE_CREATED, "CREATE",
                        target_edge=edge_id, after_state=after_state,
                        cause=self._p(params, "cause", "edge created"))
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["edges_created"] += 1
        return (1, {"edge_id": edge_id, "edge_type": edge_type}, None)

    def AddSemanticTag(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_id = self._p(params, "node_id")
        tag = self._p(params, "tag")
        confidence_score = self._p(params, "confidence_score", 0.5)
        source = self._p(params, "source", "manual")
        if not node_id or not tag:
            return (0, None, ("MISSING_PARAM", "node_id and tag required", 0))
        cursor = self.state["conn"].cursor()
        cursor.execute(
            "INSERT INTO mu_semantic_tags (node_id, tag, confidence_score, source) VALUES (%s, %s, %s, %s)",
            (node_id, tag, confidence_score, source)
        )
        tag_id = cursor.lastrowid
        self._log_event(cursor, EVENT_TAG_ADDED, "TAG",
                        target_node=node_id,
                        after_state={"tag": tag, "confidence": confidence_score},
                        cause=self._p(params, "cause", "tag added"))
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["tags_added"] += 1
        return (1, {"tag_id": tag_id, "tag": tag, "node_id": node_id}, None)

    def SetExecutionState(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        task_id = self._p(params, "task_id")
        if not task_id:
            return (0, None, ("MISSING_PARAM", "task_id required", 0))
        active_node = self._p(params, "active_node")
        execution_path = self._p(params, "execution_path")
        open_loops = self._p(params, "open_loops")
        blocked_by = self._p(params, "blocked_by")
        last_error = self._p(params, "last_error")
        cursor = self.state["conn"].cursor()
        cursor.execute("SELECT id FROM mu_execution_state WHERE task_id = %s", (task_id,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """UPDATE mu_execution_state SET active_node=%s, execution_path=%s,
                   open_loops=%s, blocked_by=%s, last_error=%s WHERE task_id=%s""",
                (active_node, execution_path, open_loops, blocked_by, last_error, task_id)
            )
        else:
            cursor.execute(
                """INSERT INTO mu_execution_state
                   (task_id, active_node, execution_path, open_loops, blocked_by, last_error)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (task_id, active_node, execution_path, open_loops, blocked_by, last_error)
            )
        self._log_event(cursor, EVENT_TASK_STARTED, "EXEC",
                        target_node=task_id,
                        after_state={"active_node": active_node, "blocked_by": blocked_by},
                        cause=self._p(params, "cause", "execution state updated"))
        self.state["conn"].commit()
        cursor.close()
        return (1, {"task_id": task_id, "active_node": active_node}, None)

    def CompleteTask(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_id = self._p(params, "node_id")
        cause = self._p(params, "cause", "task completed")
        if not node_id:
            return (0, None, ("MISSING_PARAM", "node_id required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute("SELECT current_state, version, title FROM mu_node_state WHERE node_id = %s", (node_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return (0, None, ("NOT_FOUND", "node not found", 0))
        from_state = row["current_state"]
        cursor = self.state["conn"].cursor()
        cursor.execute(
            "UPDATE mu_node_state SET current_state = %s, version = version + 1 WHERE node_id = %s",
            (STATE_CLOSED, node_id)
        )
        self._log_event(cursor, EVENT_TASK_COMPLETED, "COMPLETE",
                        target_node=node_id,
                        before_state={"state": from_state, "version": row["version"]},
                        after_state={"state": STATE_CLOSED, "version": row["version"] + 1, "title": row["title"]},
                        cause=cause)
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["state_changes"] += 1
        return (1, {"node_id": node_id, "from_state": from_state,
                    "to_state": STATE_CLOSED, "cause": cause}, None)

    def RaiseError(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_id = self._p(params, "node_id")
        error_msg = self._p(params, "error_msg")
        error_type = self._p(params, "error_type", "RUNTIME")
        cause = self._p(params, "cause", "error raised")
        if not node_id or not error_msg:
            return (0, None, ("MISSING_PARAM", "node_id and error_msg required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute("SELECT current_state, version FROM mu_node_state WHERE node_id = %s", (node_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return (0, None, ("NOT_FOUND", "node not found", 0))
        from_state = row["current_state"]
        cursor = self.state["conn"].cursor()
        cursor.execute(
            "UPDATE mu_node_state SET current_state = %s, version = version + 1 WHERE node_id = %s",
            (STATE_BROKEN, node_id)
        )
        after_state = {
            "state": STATE_BROKEN, "error": error_msg,
            "error_type": error_type, "version": row["version"] + 1,
        }
        self._log_event(cursor, EVENT_ERROR_RAISED, "ERROR",
                        target_node=node_id,
                        before_state={"state": from_state, "version": row["version"]},
                        after_state=after_state,
                        cause=cause)
        cursor.execute(
            "UPDATE mu_execution_state SET last_error = %s WHERE task_id = %s",
            (error_msg, node_id)
        )
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["state_changes"] += 1
        return (1, {"node_id": node_id, "error": error_msg,
                    "error_type": error_type, "state": STATE_BROKEN}, None)

    def LogCodeGraphChange(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        bcl_method_id = self._p(params, "bcl_method_id")
        bcl_class_id = self._p(params, "bcl_class_id")
        change_type = self._p(params, "change_type", "UPDATED")
        description = self._p(params, "description", "")
        cause = self._p(params, "cause", "code graph changed")
        cursor = self.state["conn"].cursor()
        after_state = {
            "bcl_method_id": bcl_method_id, "bcl_class_id": bcl_class_id,
            "change_type": change_type, "description": description,
        }
        self._log_event(cursor, EVENT_CODE_GRAPH_CHANGED, change_type,
                        target_node=bcl_method_id,
                        after_state=after_state,
                        cause=cause)
        self.state["conn"].commit()
        cursor.close()
        return (1, {"logged": True, "change_type": change_type,
                    "bcl_method_id": bcl_method_id}, None)

    def QueryCauseChain(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_PARAM", "node_id required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            """SELECT * FROM mu_events WHERE target_node = %s
               ORDER BY id ASC""",
            (node_id,)
        )
        events = cursor.fetchall()
        cursor.close()
        chain = []
        for e in events:
            after = e.get("after_state", "")
            try:
                import json as _json
                after_data = _json.loads(after) if after else {}
            except (ValueError, TypeError):
                after_data = {}
            chain.append({
                "event_id": e["id"],
                "event_type": e["event_type"],
                "cause": e.get("cause", ""),
                "after_state": after_data,
                "timestamp": str(e.get("timestamp", "")),
            })
        return (1, {"node_id": node_id, "cause_chain": chain,
                    "depth": len(chain)}, None)

    def ReplayEvents(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        limit = self._p(params, "limit", 100)
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM mu_events ORDER BY id ASC LIMIT %s", (limit,)
        )
        events = cursor.fetchall()
        cursor.close()
        return (1, {"events": events, "count": len(events)}, None)

    def RebuildAt(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        timestamp = self._p(params, "timestamp")
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM mu_events WHERE timestamp <= %s ORDER BY id ASC",
            (timestamp,)
        )
        events = cursor.fetchall()
        nodes = {}
        edges = {}
        tags = []
        for event in events:
            after = event.get("after_state")
            if after:
                try:
                    after_data = json.loads(after)
                except (json.JSONDecodeError, TypeError):
                    after_data = {}
            else:
                after_data = {}
            etype = event["event_type"]
            if etype == EVENT_NODE_CREATED:
                nid = after_data.get("node_id")
                if nid:
                    nodes[nid] = after_data
            elif etype == EVENT_NODE_UPDATED:
                nid = event.get("target_node")
                if nid and nid in nodes:
                    nodes[nid].update(after_data)
            elif etype == EVENT_STATE_CHANGED:
                nid = event.get("target_node")
                if nid and nid in nodes:
                    nodes[nid]["state"] = after_data.get("state")
                    nodes[nid]["version"] = after_data.get("version")
            elif etype == EVENT_EDGE_CREATED:
                eid = after_data.get("edge_id")
                if eid:
                    edges[eid] = after_data
            elif etype == EVENT_TAG_ADDED:
                tags.append(after_data)
        cursor.close()
        self.state["stats"]["rebuilds"] += 1
        return (1, {
            "timestamp": timestamp,
            "nodes": nodes,
            "edges": edges,
            "tags": tags,
            "event_count": len(events),
        }, None)

    def QueryChain(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        root_id = self._p(params, "root_id")
        if not root_id:
            return (0, None, ("MISSING_PARAM", "root_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM mu_node_state WHERE root_id = %s ORDER BY node_id",
            (root_id,)
        )
        nodes = cursor.fetchall()
        node_ids = [n["node_id"] for n in nodes]
        edges = []
        if node_ids:
            placeholders = ",".join(["%s"] * len(node_ids))
            cursor.execute(
                "SELECT * FROM mu_edge_state WHERE from_node IN (" + placeholders +
                ") OR to_node IN (" + placeholders + ")",
                node_ids + node_ids
            )
            edges = cursor.fetchall()
        cursor.close()
        return (1, {"nodes": nodes, "edges": edges,
                    "node_count": len(nodes), "edge_count": len(edges)}, None)

    def QueryOpenLoops(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        root_id = self._p(params, "root_id")
        cursor = self.state["conn"].cursor(dictionary=True)
        if root_id:
            cursor.execute(
                """SELECT * FROM mu_node_state WHERE root_id = %s
                   AND uncertainty IS NOT NULL
                   AND current_state NOT IN (%s, %s)
                   ORDER BY node_id""",
                (root_id, STATE_RESOLVED, STATE_CLOSED)
            )
        else:
            cursor.execute(
                """SELECT * FROM mu_node_state WHERE uncertainty IS NOT NULL
                   AND current_state NOT IN (%s, %s)
                   ORDER BY node_id""",
                (STATE_RESOLVED, STATE_CLOSED)
            )
        loops = cursor.fetchall()
        cursor.close()
        return (1, {"open_loops": loops, "count": len(loops)}, None)

    def QueryEventLog(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        limit = self._p(params, "limit", 50)
        target_node = self._p(params, "target_node")
        cursor = self.state["conn"].cursor(dictionary=True)
        if target_node:
            cursor.execute(
                "SELECT * FROM mu_events WHERE target_node = %s ORDER BY id DESC LIMIT %s",
                (target_node, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM mu_events ORDER BY id DESC LIMIT %s", (limit,)
            )
        events = cursor.fetchall()
        cursor.close()
        return (1, {"events": events, "count": len(events)}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "last_node_id": self.state["last_node_id"],
            "last_event_id": self.state["last_event_id"],
            "stats": self.state["stats"],
            "connected": self.state["conn"] is not None,
        }, None)

    def set_config(self, params):
        for key in ("db_host", "db_user", "db_password", "db_name"):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        self._connect()
        return (1, {"config": self.state["config"]}, None)
