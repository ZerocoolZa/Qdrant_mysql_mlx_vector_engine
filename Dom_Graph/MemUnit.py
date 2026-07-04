#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/MemUnit.py"
# date="2026-08-18" author="Devin" session_id="memunit-build"
# context="MemUnit: RAM-backed cognitive index for LLM reasoning state"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="MemUnit.py" domain="memunit" authority="MemUnit"}
# [@SUMMARY]{summary="MemUnit stores reasoning state (tasks, decisions, facts, errors) as nodes in MySQL. Tracks uncertainty (never compressed), edges between reasoning steps, and task state transitions. Connected to BCL code graph via bcl_method_id and bcl_class_id FKs."}
# [@CLASS]{class="MemUnit" domain="memunit" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="InitSchema" type="command"}
# [@METHOD]{method="CreateNode" type="command"}
# [@METHOD]{method="UpdateNode" type="command"}
# [@METHOD]{method="TransitionState" type="command"}
# [@METHOD]{method="CreateEdge" type="command"}
# [@METHOD]{method="QueryChain" type="query"}
# [@METHOD]{method="QueryOpenLoops" type="query"}
# [@METHOD]{method="QueryRecentDecisions" type="query"}
# [@METHOD]{method="QueryChildren" type="query"}
# [@METHOD]{method="LogPacket" type="command"}
# [@METHOD]{method="RestoreFromArchive" type="command"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<RAM-backed cognitive index for LLM reasoning state. Stores tasks, decisions, facts, errors as nodes in MySQL. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}
"""
MemUnit -- Reasoning state store for LLM cognitive architecture.

Tables (in vb_code_test):
  mu_nodes    -- tasks, decisions, facts, errors, questions
  mu_edges    -- DEPENDS, PRODUCES, RESOLVES, BLOCKS, REFUTES
  mu_packets  -- context packet injection log

Connected to BCL code graph:
  mu_nodes.bcl_method_id -> bcl_methods.id
  mu_nodes.bcl_class_id  -> bcl_classes.id

Usage:
  mu = MemUnit(param={"db_name": "vb_code_test"})
  mu.Run("init_schema", {})
  mu.Run("create_node", {"node_type": "TASK", "title": "build MemUnit"})
  mu.Run("create_node", {"node_type": "DECISION", "title": "use 3 tables", "parent_id": 1, "root_id": 1})
  mu.Run("create_edge", {"source_id": 2, "target_id": 1, "edge_type": "PRODUCES"})
  mu.Run("transition_state", {"node_id": 1, "to_state": "ACTIVE", "reason": "started work"})
  chain = mu.Run("query_chain", {"root_id": 1})
"""
from datetime import datetime
from typing import Any, Dict, List, Tuple

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

NODE_TYPE_TASK = "TASK"
NODE_TYPE_DECISION = "DECISION"
NODE_TYPE_FACT = "FACT"
NODE_TYPE_ERROR = "ERROR"
NODE_TYPE_QUESTION = "QUESTION"
NODE_TYPE_GOAL = "GOAL"

STATUS_OPEN = "OPEN"
STATUS_ACTIVE = "ACTIVE"
STATUS_BLOCKED = "BLOCKED"
STATUS_RESOLVED = "RESOLVED"
STATUS_CLOSED = "CLOSED"

EDGE_DEPENDS = "DEPENDS"
EDGE_PRODUCES = "PRODUCES"
EDGE_RESOLVES = "RESOLVES"
EDGE_BLOCKS = "BLOCKS"
EDGE_REFUTES = "REFUTES"
EDGE_SUPPORTS = "SUPPORTS"
EDGE_TRIGGERS = "TRIGGERS"

CERTAINTY_CERTAIN = "CERTAIN"
CERTAINTY_PROBABLE = "PROBABLE"
CERTAINTY_UNKNOWN = "UNKNOWN"

VALID_TRANSITIONS = {
    STATUS_OPEN: [STATUS_ACTIVE],
    STATUS_ACTIVE: [STATUS_BLOCKED, STATUS_RESOLVED],
    STATUS_BLOCKED: [STATUS_ACTIVE],
    STATUS_RESOLVED: [STATUS_CLOSED, STATUS_ACTIVE],
    STATUS_CLOSED: [STATUS_ACTIVE],
}


class MemUnit:
    """Reasoning state store. Nodes + edges + state machine + packet log."""

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
            "stats": {
                "nodes_created": 0,
                "edges_created": 0,
                "transitions": 0,
                "packets_logged": 0,
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
            "get_node": self.GetNode,
            "transition_state": self.TransitionState,
            "create_edge": self.CreateEdge,
            "query_chain": self.QueryChain,
            "query_open_loops": self.QueryOpenLoops,
            "query_recent_decisions": self.QueryRecentDecisions,
            "query_children": self.QueryChildren,
            "query_active": self.QueryActive,
            "log_packet": self.LogPacket,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def InitSchema(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        cursor = self.state["conn"].cursor()
        statements = [
            """CREATE TABLE IF NOT EXISTS mu_nodes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                node_type VARCHAR(20) NOT NULL,
                node_status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
                title VARCHAR(255) NOT NULL,
                content TEXT,
                uncertainty TEXT,
                parent_id INT,
                root_id INT,
                task_id INT,
                bcl_method_id INT,
                bcl_class_id INT,
                confidence DECIMAL(3,2) DEFAULT 1.00,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                closed_at DATETIME,
                INDEX idx_type (node_type),
                INDEX idx_status (node_status),
                INDEX idx_parent (parent_id),
                INDEX idx_root (root_id),
                INDEX idx_task (task_id),
                INDEX idx_bcl_method (bcl_method_id),
                INDEX idx_bcl_class (bcl_class_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS mu_edges (
                id INT AUTO_INCREMENT PRIMARY KEY,
                source_id INT NOT NULL,
                target_id INT NOT NULL,
                edge_type VARCHAR(20) NOT NULL,
                certainty VARCHAR(10) NOT NULL DEFAULT 'PROBABLE',
                evidence TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_source (source_id),
                INDEX idx_target (target_id),
                INDEX idx_type (edge_type),
                INDEX idx_certainty (certainty)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS mu_packets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_id INT,
                packet_text TEXT,
                token_count INT DEFAULT 0,
                response_node_id INT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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
        node_type = self._p(params, "node_type", NODE_TYPE_TASK)
        title = self._p(params, "title")
        if not title:
            return (0, None, ("MISSING_TITLE", "title is required", 0))
        content = self._p(params, "content")
        uncertainty = self._p(params, "uncertainty")
        parent_id = self._p(params, "parent_id")
        root_id = self._p(params, "root_id")
        task_id = self._p(params, "task_id")
        bcl_method_id = self._p(params, "bcl_method_id")
        bcl_class_id = self._p(params, "bcl_class_id")
        confidence = self._p(params, "confidence", 1.0)
        if parent_id and not root_id:
            root_id = parent_id
        if not task_id and root_id:
            task_id = root_id
        cursor = self.state["conn"].cursor()
        cursor.execute(
            """INSERT INTO mu_nodes
               (node_type, node_status, title, content, uncertainty,
                parent_id, root_id, task_id, bcl_method_id, bcl_class_id, confidence)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (node_type, STATUS_OPEN, title, content, uncertainty,
             parent_id, root_id, task_id, bcl_method_id, bcl_class_id, confidence)
        )
        node_id = cursor.lastrowid
        self.state["conn"].commit()
        cursor.close()
        self.state["last_node_id"] = node_id
        self.state["stats"]["nodes_created"] += 1
        return (1, {"node_id": node_id, "title": title, "node_type": node_type}, None)

    def UpdateNode(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_NODE_ID", "node_id is required", 0))
        cursor = self.state["conn"].cursor()
        updates = []
        values = []
        for field in ("content", "uncertainty", "confidence", "title"):
            val = self._p(params, field)
            if val is not None:
                updates.append(field + " = %s")
                values.append(val)
        if not updates:
            return (0, None, ("NO_UPDATES", "no fields to update", 0))
        values.append(node_id)
        cursor.execute(
            "UPDATE mu_nodes SET " + ", ".join(updates) + " WHERE id = %s",
            values
        )
        self.state["conn"].commit()
        cursor.close()
        return (1, {"node_id": node_id, "updated_fields": len(updates)}, None)

    def GetNode(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_NODE_ID", "node_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute("SELECT * FROM mu_nodes WHERE id = %s", (node_id,))
        node = cursor.fetchone()
        cursor.close()
        if not node:
            return (0, None, ("NOT_FOUND", "node not found", 0))
        return (1, node, None)

    def TransitionState(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        node_id = self._p(params, "node_id")
        to_state = self._p(params, "to_state")
        reason = self._p(params, "reason", "")
        if not node_id or not to_state:
            return (0, None, ("MISSING_PARAM", "node_id and to_state required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute("SELECT node_status FROM mu_nodes WHERE id = %s", (node_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return (0, None, ("NOT_FOUND", "node not found", 0))
        from_state = row["node_status"]
        allowed = VALID_TRANSITIONS.get(from_state, [])
        if to_state not in allowed:
            cursor.close()
            return (0, None, ("INVALID_TRANSITION",
                              "cannot go from " + from_state + " to " + to_state, 0))
        closed_at = None
        if to_state in (STATUS_RESOLVED, STATUS_CLOSED):
            closed_at = datetime.now()
        cursor = self.state["conn"].cursor()
        cursor.execute(
            "UPDATE mu_nodes SET node_status = %s, closed_at = %s WHERE id = %s",
            (to_state, closed_at, node_id)
        )
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["transitions"] += 1
        return (1, {
            "node_id": node_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
        }, None)

    def CreateEdge(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        source_id = self._p(params, "source_id")
        target_id = self._p(params, "target_id")
        edge_type = self._p(params, "edge_type", EDGE_DEPENDS)
        certainty = self._p(params, "certainty", CERTAINTY_PROBABLE)
        evidence = self._p(params, "evidence")
        if not source_id or not target_id:
            return (0, None, ("MISSING_PARAM", "source_id and target_id required", 0))
        if certainty == CERTAINTY_CERTAIN and not evidence:
            return (0, None, ("NO_EVIDENCE",
                              "CERTAIN edges require evidence", 0))
        cursor = self.state["conn"].cursor()
        cursor.execute(
            """INSERT INTO mu_edges (source_id, target_id, edge_type, certainty, evidence)
               VALUES (%s, %s, %s, %s, %s)""",
            (source_id, target_id, edge_type, certainty, evidence)
        )
        edge_id = cursor.lastrowid
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["edges_created"] += 1
        return (1, {"edge_id": edge_id, "edge_type": edge_type}, None)

    def QueryChain(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        root_id = self._p(params, "root_id")
        if not root_id:
            return (0, None, ("MISSING_PARAM", "root_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM mu_nodes WHERE root_id = %s ORDER BY created_at",
            (root_id,)
        )
        nodes = cursor.fetchall()
        node_ids = [n["id"] for n in nodes]
        edges = []
        if node_ids:
            placeholders = ",".join(["%s"] * len(node_ids))
            cursor.execute(
                "SELECT * FROM mu_edges WHERE source_id IN (" + placeholders +
                ") OR target_id IN (" + placeholders + ")",
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
                """SELECT * FROM mu_nodes WHERE root_id = %s
                   AND uncertainty IS NOT NULL
                   AND node_status NOT IN (%s, %s)
                   ORDER BY created_at""",
                (root_id, STATUS_RESOLVED, STATUS_CLOSED)
            )
        else:
            cursor.execute(
                """SELECT * FROM mu_nodes WHERE uncertainty IS NOT NULL
                   AND node_status NOT IN (%s, %s)
                   ORDER BY created_at""",
                (STATUS_RESOLVED, STATUS_CLOSED)
            )
        loops = cursor.fetchall()
        cursor.close()
        return (1, {"open_loops": loops, "count": len(loops)}, None)

    def QueryRecentDecisions(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        root_id = self._p(params, "root_id")
        limit = self._p(params, "limit", 5)
        cursor = self.state["conn"].cursor(dictionary=True)
        if root_id:
            cursor.execute(
                """SELECT * FROM mu_nodes WHERE root_id = %s AND node_type = %s
                   ORDER BY created_at DESC LIMIT %s""",
                (root_id, NODE_TYPE_DECISION, limit)
            )
        else:
            cursor.execute(
                """SELECT * FROM mu_nodes WHERE node_type = %s
                   ORDER BY created_at DESC LIMIT %s""",
                (NODE_TYPE_DECISION, limit)
            )
        decisions = cursor.fetchall()
        cursor.close()
        return (1, {"decisions": decisions, "count": len(decisions)}, None)

    def QueryChildren(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        parent_id = self._p(params, "parent_id")
        if not parent_id:
            return (0, None, ("MISSING_PARAM", "parent_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM mu_nodes WHERE parent_id = %s ORDER BY created_at",
            (parent_id,)
        )
        children = cursor.fetchall()
        cursor.close()
        return (1, {"children": children, "count": len(children)}, None)

    def QueryActive(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        root_id = self._p(params, "root_id")
        cursor = self.state["conn"].cursor(dictionary=True)
        if root_id:
            cursor.execute(
                "SELECT * FROM mu_nodes WHERE root_id = %s AND node_status = %s ORDER BY created_at",
                (root_id, STATUS_ACTIVE)
            )
        else:
            cursor.execute(
                "SELECT * FROM mu_nodes WHERE node_status = %s ORDER BY created_at",
                (STATUS_ACTIVE,)
            )
        active = cursor.fetchall()
        cursor.close()
        return (1, {"active_nodes": active, "count": len(active)}, None)

    def LogPacket(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        task_id = self._p(params, "task_id")
        packet_text = self._p(params, "packet_text")
        token_count = self._p(params, "token_count", 0)
        response_node_id = self._p(params, "response_node_id")
        if not packet_text:
            return (0, None, ("MISSING_PARAM", "packet_text is required", 0))
        cursor = self.state["conn"].cursor()
        cursor.execute(
            """INSERT INTO mu_packets (task_id, packet_text, token_count, response_node_id)
               VALUES (%s, %s, %s, %s)""",
            (task_id, packet_text, token_count, response_node_id)
        )
        packet_id = cursor.lastrowid
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["packets_logged"] += 1
        return (1, {"packet_id": packet_id, "token_count": token_count}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "last_node_id": self.state["last_node_id"],
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
