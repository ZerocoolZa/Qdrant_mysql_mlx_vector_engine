#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/ContextReconstructor.py"
# date="2026-08-18" author="Devin" session_id="memunit-v2"
# context="Version 2: Context Reconstructor. Builds LLM packets from event-sourced MemUnit. Includes cause chains, error lineage, semantic tags. Deterministic."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="ContextReconstructor.py" domain="memunit" authority="ContextReconstructor"}
# [@SUMMARY]{summary="Reconstructs context packets from event-sourced MemUnit. Walks event log for cause chains. Includes semantic tags, error lineage, execution state. Outputs narrative packet for LLM injection."}
# [@CLASS]{class="ContextReconstructor" domain="memunit" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="BuildPacket" type="command"}
# [@METHOD]{method="BuildAnchor" type="helper"}
# [@METHOD]{method="BuildActiveSubgraph" type="helper"}
# [@METHOD]{method="BuildCauseChain" type="helper"}
# [@METHOD]{method="BuildOpenLoops" type="helper"}
# [@METHOD]{method="BuildErrorLineage" type="helper"}
# [@METHOD]{method="BuildSemanticSummary" type="helper"}
# [@METHOD]{method="BuildCodeContext" type="helper"}
# [@METHOD]{method="EstimateTokens" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Version 2 context reconstructor from event-sourced MemUnit. Builds cause chains, error lineage, semantic tags. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded MAX_CODE_PREVIEW=800, MAX_EDGES=15, MAX_EVENTS=10, MAX_LOOPS=20, MAX_CAUSE_DEPTH=5. Docstring contains print() example.>][@todos<Move max constants to Config.py. Remove print() from docstring example.>]}
"""
ContextReconstructor -- Version 2 packet builder.

Reconstructs context from event-sourced MemUnit.
Includes: cause chains, error lineage, semantic tags, execution state.

RULE: Context is always reconstructed. Never stored.
RULE: LLM never sees raw graph. Only reconstructed slices.

Usage:
  cr = ContextReconstructor()
  result = cr.Run('build_packet', {'task_id': 1, 'root_id': 1})
  print(result[1]['packet_text'])
"""
import json
from typing import Any, Dict, List, Tuple

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

MAX_CODE_PREVIEW = 800
MAX_EDGES = 15
MAX_EVENTS = 10
MAX_LOOPS = 20
MAX_CAUSE_DEPTH = 5


class ContextReconstructor:
    """Reconstructs narrative packets from event-sourced MemUnit."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_host": "localhost",
                "db_user": "root",
                "db_password": "",
                "db_name": "vb_code_test",
            },
            "conn": None,
            "stats": {
                "packets_built": 0,
                "total_tokens": 0,
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
            "build_packet": self.BuildPacket,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def BuildPacket(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        task_id = self._p(params, "task_id")
        root_id = self._p(params, "root_id")
        if not task_id and not root_id:
            return (0, None, ("MISSING_PARAM", "task_id or root_id required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        task = None
        if task_id:
            cursor.execute("SELECT * FROM mu_node_state WHERE node_id = %s", (task_id,))
            task = cursor.fetchone()
            if not task:
                cursor.close()
                return (0, None, ("NOT_FOUND", "task not found", 0))
            root_id = task.get("root_id") or task_id
        root = None
        if root_id:
            cursor.execute("SELECT * FROM mu_node_state WHERE node_id = %s", (root_id,))
            root = cursor.fetchone()
        if not root and task:
            root = task
        anchor = self.BuildAnchor(cursor, task, root, root_id)
        subgraph = self.BuildActiveSubgraph(cursor, root_id)
        call_chains = self.BuildCallChains(cursor, task)
        cause_chain = self.BuildCauseChain(cursor, task_id)
        open_loops = self.BuildOpenLoops(cursor, root_id)
        error_lineage = self.BuildErrorLineage(cursor, root_id)
        semantic = self.BuildSemanticSummary(cursor, root_id)
        code_ctx = self.BuildCodeContext(cursor, task)
        exec_state = self.BuildExecutionState(cursor, root_id)
        sections = [anchor, subgraph, call_chains, cause_chain, open_loops,
                    error_lineage, semantic, code_ctx, exec_state]
        packet_text = "\n\n".join(s for s in sections if s)
        token_count = self.EstimateTokens(packet_text)
        cursor.close()
        self.state["stats"]["packets_built"] += 1
        self.state["stats"]["total_tokens"] += token_count
        return (1, {
            "packet_text": packet_text,
            "token_count": token_count,
            "sections": len([s for s in sections if s]),
        }, None)

    def BuildAnchor(self, cursor, task, root, root_id):
        lines = ["[ANCHOR]"]
        if root:
            lines.append("goal = " + str(root.get("title", "")))
            if root.get("content"):
                lines.append("goal_detail = " + str(root["content"][:300]))
            lines.append("goal_state = " + str(root.get("current_state", "")))
        if task:
            lines.append("current_task = " + str(task.get("title", "")))
            lines.append("task_state = " + str(task.get("current_state", "")))
            lines.append("task_version = " + str(task.get("version", 1)))
            if task.get("content"):
                lines.append("task_detail = " + str(task["content"][:500]))
        cursor.execute(
            "SELECT * FROM mu_node_state WHERE root_id = %s AND current_state = %s ORDER BY node_id",
            (root_id, "ACTIVE")
        )
        active = cursor.fetchall()
        if active:
            lines.append("active_items = " + ", ".join(
                a["title"] for a in active[:5]
            ))
        return "\n".join(lines)

    def BuildActiveSubgraph(self, cursor, root_id):
        cursor.execute(
            "SELECT * FROM mu_node_state WHERE root_id = %s ORDER BY node_id",
            (root_id,)
        )
        nodes = cursor.fetchall()
        if not nodes:
            return ""
        node_ids = [n["node_id"] for n in nodes]
        placeholders = ",".join(["%s"] * len(node_ids))
        cursor.execute(
            "SELECT * FROM mu_edge_state WHERE from_node IN (" + placeholders +
            ") AND validity_state = %s ORDER BY edge_id",
            node_ids + ["VALID"]
        )
        edges = cursor.fetchall()
        lines = ["[ACTIVE_SUBGRAPH]"]
        for n in nodes:
            state_marker = ""
            if n.get("current_state") == "ACTIVE":
                state_marker = " *ACTIVE*"
            elif n.get("current_state") == "BLOCKED":
                state_marker = " *BLOCKED*"
            elif n.get("current_state") == "RESOLVED":
                state_marker = " [resolved]"
            lines.append("  " + str(n["node_type"]) + ": " + str(n["title"]) + state_marker)
        if edges:
            lines.append("  edges:")
            for e in edges[:MAX_EDGES]:
                lines.append("    " + str(e["edge_type"]) + ": " +
                             str(e["from_node"]) + " -> " + str(e["to_node"]) +
                             " (" + str(e["certainty"]) + ")")
        return "\n".join(lines)

    def BuildCallChains(self, cursor, task):
        if not task:
            return ""
        bcl_method_id = task.get("bcl_method_id")
        if not bcl_method_id:
            return ""
        cursor.execute(
            """SELECT e.edge_type, e.certainty, e.target,
                      m_target.method_name as target_name,
                      m_target.method_type as target_type
               FROM bcl_edges e
               LEFT JOIN bcl_methods m_target ON e.target_method_row_id = m_target.id
               WHERE e.bcl_method_id = %s
               ORDER BY e.edge_type, e.certainty DESC LIMIT 20""",
            (bcl_method_id,)
        )
        outgoing = cursor.fetchall()
        cursor.execute(
            """SELECT e.edge_type, e.certainty, m_src.method_name as source_name,
                      m_src.method_type as source_type
               FROM bcl_edges e
               JOIN bcl_methods m_src ON e.bcl_method_id = m_src.id
               WHERE e.target_method_row_id = %s
               ORDER BY e.edge_type LIMIT 10""",
            (bcl_method_id,)
        )
        incoming = cursor.fetchall()
        if not outgoing and not incoming:
            return ""
        lines = ["[CALL_CHAINS]"]
        if outgoing:
            lines.append("  outgoing:")
            for e in outgoing:
                target_display = e.get("target_name") or str(e.get("target", ""))[:40]
                target_type = e.get("target_type", "")
                if target_type:
                    target_display += " [" + target_type + "]"
                lines.append("    " + str(e["edge_type"]) + " -> " +
                             target_display + " (" + str(e["certainty"]) + ")")
        if incoming:
            lines.append("  incoming:")
            for e in incoming:
                src_display = str(e.get("source_name", "?"))
                src_type = e.get("source_type", "")
                if src_type:
                    src_display += " [" + src_type + "]"
                lines.append("    " + str(e["edge_type"]) + " <- " +
                             src_display + " (" + str(e["certainty"]) + ")")
        return "\n".join(lines)

    def BuildCauseChain(self, cursor, task_id):
        if not task_id:
            return ""
        cursor.execute(
            """SELECT * FROM mu_events WHERE target_node = %s
               ORDER BY id DESC LIMIT %s""",
            (task_id, MAX_CAUSE_DEPTH)
        )
        events = cursor.fetchall()
        if not events:
            return ""
        lines = ["[CAUSE_CHAIN]"]
        for e in reversed(events):
            cause = e.get("cause", "")
            etype = e.get("event_type", "")
            lines.append("  " + str(etype) + ": " + str(cause))
        return "\n".join(lines)

    def BuildOpenLoops(self, cursor, root_id):
        cursor.execute(
            """SELECT * FROM mu_node_state WHERE root_id = %s
               AND uncertainty IS NOT NULL
               AND current_state NOT IN (%s, %s)
               ORDER BY node_id LIMIT %s""",
            (root_id, "RESOLVED", "CLOSED", MAX_LOOPS)
        )
        loops = cursor.fetchall()
        if not loops:
            return ""
        lines = ["[OPEN_LOOPS]"]
        for loop in loops:
            lines.append("- " + str(loop["title"]) +
                         " | uncertainty: " + str(loop["uncertainty"][:200]))
        return "\n".join(lines)

    def BuildErrorLineage(self, cursor, root_id):
        cursor.execute(
            """SELECT * FROM mu_events WHERE event_type = %s
               AND target_node IN (
                   SELECT node_id FROM mu_node_state WHERE root_id = %s
               )
               ORDER BY id DESC LIMIT %s""",
            ("ERROR_RAISED", root_id, MAX_EVENTS)
        )
        errors = cursor.fetchall()
        if not errors:
            return ""
        lines = ["[ERROR_LINEAGE]"]
        for e in errors:
            after = e.get("after_state", "")
            try:
                after_data = json.loads(after) if after else {}
            except (json.JSONDecodeError, TypeError):
                after_data = {}
            lines.append("- " + str(e.get("cause", "")) +
                         " | " + str(after_data.get("error", ""))[:200])
        return "\n".join(lines)

    def BuildSemanticSummary(self, cursor, root_id):
        cursor.execute(
            """SELECT st.tag, st.confidence_score, ns.title
               FROM mu_semantic_tags st
               JOIN mu_node_state ns ON st.node_id = ns.node_id
               WHERE ns.root_id = %s
               ORDER BY st.confidence_score DESC LIMIT 10""",
            (root_id,)
        )
        tags = cursor.fetchall()
        if not tags:
            return ""
        lines = ["[SEMANTIC_SUMMARY]"]
        for t in tags:
            lines.append("  " + str(t["tag"]) + " (" +
                         str(t["confidence_score"]) + ") -> " +
                         str(t["title"]))
        return "\n".join(lines)

    def BuildCodeContext(self, cursor, task):
        if not task:
            return ""
        bcl_method_id = task.get("bcl_method_id")
        bcl_class_id = task.get("bcl_class_id")
        if not bcl_method_id and not bcl_class_id:
            return ""
        lines = ["[CODE_CONTEXT]"]
        if bcl_method_id:
            cursor.execute(
                """SELECT m.*, c.class_name, v.method_code
                   FROM bcl_methods m
                   LEFT JOIN bcl_classes c ON m.bcl_class_id = c.id
                   LEFT JOIN vb_methods v ON m.source_method_id = v.id
                   WHERE m.id = %s""",
                (bcl_method_id,)
            )
            method = cursor.fetchone()
            if method:
                lines.append("method = " + str(method.get("method_name", "")) +
                             " [" + str(method.get("method_type", "")) + "]")
                lines.append("class = " + str(method.get("class_name", "")))
                code = method.get("method_code", "")
                if code:
                    lines.append("source = " + str(code[:MAX_CODE_PREVIEW]))
                cursor.execute(
                    """SELECT edge_type, certainty, target
                       FROM bcl_edges WHERE bcl_method_id = %s
                       ORDER BY edge_type LIMIT %s""",
                    (bcl_method_id, MAX_EDGES)
                )
                edges = cursor.fetchall()
                if edges:
                    lines.append("call_edges:")
                    for e in edges:
                        lines.append("  " + str(e["edge_type"]) + " -> " +
                                     str(e["target"])[:50] + " (" +
                                     str(e["certainty"]) + ")")
        return "\n".join(lines)

    def BuildExecutionState(self, cursor, root_id):
        cursor.execute(
            "SELECT * FROM mu_execution_state WHERE task_id = %s", (root_id,)
        )
        exec_row = cursor.fetchone()
        if not exec_row:
            return ""
        lines = ["[EXECUTION_STATE]"]
        if exec_row.get("active_node"):
            lines.append("active_node = " + str(exec_row["active_node"]))
        if exec_row.get("execution_path"):
            lines.append("path = " + str(exec_row["execution_path"][:300]))
        if exec_row.get("open_loops"):
            lines.append("open_loops = " + str(exec_row["open_loops"][:300]))
        if exec_row.get("blocked_by"):
            lines.append("blocked_by = " + str(exec_row["blocked_by"][:300]))
        if exec_row.get("last_error"):
            lines.append("last_error = " + str(exec_row["last_error"][:300]))
        return "\n".join(lines)

    def EstimateTokens(self, text):
        if not text:
            return 0
        return int(len(text) / 3.5)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
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
