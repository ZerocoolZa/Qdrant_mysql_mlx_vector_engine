#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/ContextCompiler.py"
# date="2026-08-18" author="Devin" session_id="memunit-build"
# context="ContextCompiler: walks MemUnit graph + BCL code graph, produces narrative packet for LLM"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="ContextCompiler.py" domain="memunit" authority="ContextCompiler"}
# [@SUMMARY]{summary="ContextCompiler queries MemUnit reasoning state + BCL code graph, walks dependencies, assembles a compact narrative packet for LLM injection. Graph is storage. Narrative is injection. Never dumps raw graph."}
# [@CLASS]{class="ContextCompiler" domain="memunit" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="BuildPacket" type="command"}
# [@METHOD]{method="BuildAnchor" type="helper"}
# [@METHOD]{method="BuildOpenLoops" type="helper"}
# [@METHOD]{method="BuildRecentDecisions" type="helper"}
# [@METHOD]{method="BuildCodeContext" type="helper"}
# [@METHOD]{method="BuildBlockers" type="helper"}
# [@METHOD]{method="EstimateTokens" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Walks MemUnit graph + BCL code graph, produces narrative packet for LLM injection. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded MAX_CODE_PREVIEW=800, MAX_EDGES_IN_PACKET=15, MAX_DECISIONS=5, MAX_OPEN_LOOPS=20. Docstring contains print() example.>][@todos<Move max constants to Config.py. Remove print() from docstring example.>]}
"""
ContextCompiler -- Assembles narrative context packets from MemUnit + BCL code graph.

Pipeline:
  1. Query MemUnit for active task, open loops, recent decisions, blockers
  2. If task is linked to BCL code, query code graph for method + edges + source
  3. Serialize as narrative (NOT graph) for LLM injection
  4. Log packet to mu_packets

Usage:
  cc = ContextCompiler(param={"db_name": "vb_code_test"})
  result = cc.Run("build_packet", {"task_id": 1})
  print(result[1]["packet_text"])
"""
from typing import Any, Dict, List, Tuple

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

MAX_CODE_PREVIEW = 800
MAX_EDGES_IN_PACKET = 15
MAX_DECISIONS = 5
MAX_OPEN_LOOPS = 20


class ContextCompiler:
    """Walks MemUnit + BCL graph, produces narrative packets for LLM."""

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
            cursor.execute("SELECT * FROM mu_nodes WHERE id = %s", (task_id,))
            task = cursor.fetchone()
            if not task:
                cursor.close()
                return (0, None, ("NOT_FOUND", "task node not found", 0))
            root_id = task.get("root_id") or task_id
        root = None
        if root_id:
            cursor.execute("SELECT * FROM mu_nodes WHERE id = %s", (root_id,))
            root = cursor.fetchone()
        if not root and task:
            root = task
        anchor = self.BuildAnchor(cursor, task, root, root_id)
        open_loops = self.BuildOpenLoops(cursor, root_id)
        decisions = self.BuildRecentDecisions(cursor, root_id)
        blockers = self.BuildBlockers(cursor, root_id)
        code_context = self.BuildCodeContext(cursor, task)
        sections = [anchor, blockers, open_loops, decisions, code_context]
        packet_text = "\n\n".join(s for s in sections if s)
        token_count = self.EstimateTokens(packet_text)
        cursor.close()
        self._log_packet(task_id, packet_text, token_count)
        self.state["stats"]["packets_built"] += 1
        self.state["stats"]["total_tokens"] += token_count
        return (1, {
            "packet_text": packet_text,
            "token_count": token_count,
            "sections": len(sections),
        }, None)

    def BuildAnchor(self, cursor, task, root, root_id):
        lines = ["[ANCHOR]"]
        if root:
            lines.append("goal = " + str(root.get("title", "")))
            if root.get("content"):
                lines.append("goal_detail = " + str(root["content"][:300]))
        if task:
            lines.append("current_task = " + str(task.get("title", "")))
            lines.append("task_status = " + str(task.get("node_status", "")))
            if task.get("content"):
                lines.append("task_state = " + str(task["content"][:500]))
        cursor.execute(
            "SELECT * FROM mu_nodes WHERE root_id = %s AND node_status = %s ORDER BY created_at",
            (root_id, "ACTIVE")
        )
        active = cursor.fetchall()
        if active:
            lines.append("active_items = " + ", ".join(
                a["title"] for a in active[:5]
            ))
        return "\n".join(lines)

    def BuildBlockers(self, cursor, root_id):
        cursor.execute(
            """SELECT n.* FROM mu_nodes n
               JOIN mu_edges e ON e.target_id = n.id
               WHERE n.root_id = %s AND n.node_status = %s
               AND e.edge_type = %s""",
            (root_id, "BLOCKED", "BLOCKS")
        )
        blocked = cursor.fetchall()
        if not blocked:
            return ""
        lines = ["[BLOCKERS]"]
        for b in blocked:
            lines.append("- " + str(b["title"]) + ": " + str(b.get("content", "")[:200]))
        return "\n".join(lines)

    def BuildOpenLoops(self, cursor, root_id):
        cursor.execute(
            """SELECT * FROM mu_nodes WHERE root_id = %s
               AND uncertainty IS NOT NULL
               AND node_status NOT IN (%s, %s)
               ORDER BY created_at LIMIT %s""",
            (root_id, "RESOLVED", "CLOSED", MAX_OPEN_LOOPS)
        )
        loops = cursor.fetchall()
        if not loops:
            return ""
        lines = ["[OPEN_LOOPS]"]
        for loop in loops:
            lines.append("- " + str(loop["title"]) + " | uncertainty: " + str(loop["uncertainty"][:200]))
        return "\n".join(lines)

    def BuildRecentDecisions(self, cursor, root_id):
        cursor.execute(
            """SELECT * FROM mu_nodes WHERE root_id = %s AND node_type = %s
               ORDER BY created_at DESC LIMIT %s""",
            (root_id, "DECISION", MAX_DECISIONS)
        )
        decisions = cursor.fetchall()
        if not decisions:
            return ""
        lines = ["[RECENT_DECISIONS]"]
        for d in decisions:
            line = "- " + str(d["title"])
            if d.get("content"):
                line += " because: " + str(d["content"][:200])
            lines.append(line)
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
                    """SELECT edge_type, certainty, target, target_method_row_id
                       FROM bcl_edges WHERE bcl_method_id = %s
                       ORDER BY edge_type LIMIT %s""",
                    (bcl_method_id, MAX_EDGES_IN_PACKET)
                )
                edges = cursor.fetchall()
                if edges:
                    lines.append("edges:")
                    for e in edges:
                        resolved = " [resolved]" if e.get("target_method_row_id") else ""
                        lines.append("  " + str(e["edge_type"]) + " -> " +
                                     str(e["target"])[:50] + " (" +
                                     str(e["certainty"]) + ")" + resolved)
        if bcl_class_id and not bcl_method_id:
            cursor.execute(
                """SELECT c.*, v.domain, v.role, v.description
                   FROM bcl_classes c
                   LEFT JOIN vb_classes v ON c.source_class_id = v.id
                   WHERE c.id = %s""",
                (bcl_class_id,)
            )
            cls = cursor.fetchone()
            if cls:
                lines.append("class = " + str(cls.get("class_name", "")))
                lines.append("domain = " + str(cls.get("domain", "")))
                lines.append("role = " + str(cls.get("role", "")))
                cursor.execute(
                    "SELECT method_name, method_type FROM bcl_methods WHERE bcl_class_id = %s ORDER BY method_name",
                    (bcl_class_id,)
                )
                methods = cursor.fetchall()
                if methods:
                    lines.append("methods (" + str(len(methods)) + "):")
                    for m in methods[:20]:
                        lines.append("  " + str(m["method_name"]) + " [" + str(m["method_type"]) + "]")
        return "\n".join(lines)

    def EstimateTokens(self, text):
        if not text:
            return 0
        return int(len(text) / 3.5)

    def _log_packet(self, task_id, packet_text, token_count):
        if not self.state["conn"]:
            return
        cursor = self.state["conn"].cursor()
        cursor.execute(
            "INSERT INTO mu_packets (task_id, packet_text, token_count) VALUES (%s, %s, %s)",
            (task_id, packet_text, token_count)
        )
        self.state["conn"].commit()
        cursor.close()

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
