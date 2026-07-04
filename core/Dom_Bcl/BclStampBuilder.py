#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/BclStampBuilder.py"
# date="2026-08-18" author="Devin" session_id="bcl-stamp"
# context="BCL Stamp Builder: takes LLM output (code + reasoning) and builds BCL stamps linked to MemUnit reasoning traces"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="BclStampBuilder.py" domain="bcl_stamp" authority="BclStampBuilder"}
# [@SUMMARY]{summary="Builds BCL stamps from LLM structured output. Each stamp links a BCL method to its reasoning trace in MemUnit. Stamps are persisted in bcl_stamps table. Also generates the [@BCL_STAMP] header block for file injection."}
# [@CLASS]{class="BclStampBuilder" domain="bcl_stamp" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="BuildStamp" type="command"}
# [@METHOD]{method="BuildStampFromReasoning" type="command"}
# [@METHOD]{method="InjectStampIntoCode" type="command"}
# [@METHOD]{method="GetStamp" type="query"}
# [@METHOD]{method="QueryStampsForMethod" type="query"}
# [@METHOD]{method="QueryStampsForClass" type="query"}
# [@METHOD]{method="InvalidateStamp" type="command"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
"""
BclStampBuilder -- Builds BCL stamps that link code to reasoning traces.

Pipeline:
  LLM GENERATES CODE + REASONING
        ↓
  BclStampBuilder.BuildStampFromReasoning()
        ↓
  bcl_stamps table (bcl_method_id -> mu_node_id, trace_id, goal, intent)
        ↓
  InjectStampIntoCode() -- adds [@BCL_STAMP] header to method_code
        ↓
  PreExecutionGate validates before execution

Stamp format (injected into source):
  # [@BCL_STAMP]{trace_id="tr_4410" goal="..." intent="..." source_nodes="..." changes_applied="..." rejected_paths="..." event_refs="..."}

Usage:
  builder = BclStampBuilder()
  result = builder.Run('build_stamp_from_reasoning', {
      'bcl_method_id': 123,
      'goal': 'reduce parsing latency',
      'intent': 'optimize tokenizer pipeline',
      'source_nodes': [1, 2, 3],
      'changes_applied': ['inline_cache', 'loop_unroll'],
      'rejected_paths': ['regex_parser'],
      'mu_node_id': 9,
      'event_refs': [38, 37, 36],
  })
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

STAMP_VALID = "VALID"
STAMP_STALE = "STALE"
STAMP_INVALID = "INVALID"
STAMP_REJECTED = "REJECTED"


class BclStampBuilder:
    """Builds BCL stamps linking code methods to reasoning traces."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_host": "localhost",
                "db_user": "root",
                "db_password": "",
                "db_name": "vb_code_test",
            },
            "conn": None,
            "last_stamp_id": None,
            "stats": {
                "stamps_built": 0,
                "stamps_injected": 0,
                "stamps_invalidated": 0,
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
            "build_stamp": self.BuildStamp,
            "build_stamp_from_reasoning": self.BuildStampFromReasoning,
            "inject_stamp_into_code": self.InjectStampIntoCode,
            "get_stamp": self.GetStamp,
            "query_stamps_for_method": self.QueryStampsForMethod,
            "query_stamps_for_class": self.QueryStampsForClass,
            "invalidate_stamp": self.InvalidateStamp,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def _generate_trace_id(self, bcl_method_id, mu_node_id):
        import hashlib
        raw = str(bcl_method_id) + ":" + str(mu_node_id) + ":" + str(datetime.now().timestamp())
        h = hashlib.md5(raw.encode()).hexdigest()[:8]
        return "tr_" + h

    def BuildStampFromReasoning(self, params):
        """Build a BCL stamp from LLM structured reasoning output."""
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        bcl_method_id = self._p(params, "bcl_method_id")
        if not bcl_method_id:
            return (0, None, ("MISSING_PARAM", "bcl_method_id is required", 0))
        bcl_class_id = self._p(params, "bcl_class_id")
        stamp_type = self._p(params, "stamp_type", "METHOD")
        goal = self._p(params, "goal", "")
        intent = self._p(params, "intent", "")
        source_nodes = self._p(params, "source_nodes", [])
        changes_applied = self._p(params, "changes_applied", [])
        rejected_paths = self._p(params, "rejected_paths", [])
        event_refs = self._p(params, "event_refs", [])
        mu_node_id = self._p(params, "mu_node_id")
        if not goal:
            return (0, None, ("MISSING_GOAL", "goal is required for stamp", 0))
        trace_id = self._generate_trace_id(bcl_method_id, mu_node_id)
        source_nodes_json = json.dumps(source_nodes) if source_nodes else None
        changes_json = json.dumps(changes_applied) if changes_applied else None
        rejected_json = json.dumps(rejected_paths) if rejected_paths else None
        event_refs_json = json.dumps(event_refs) if event_refs else None
        cursor = self.state["conn"].cursor()
        cursor.execute(
            """INSERT INTO bcl_stamps
               (bcl_method_id, bcl_class_id, stamp_type, trace_id,
                goal, intent, source_nodes, changes_applied,
                rejected_paths, event_refs, mu_node_id, stamp_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (bcl_method_id, bcl_class_id, stamp_type, trace_id,
             goal, intent, source_nodes_json, changes_json,
             rejected_json, event_refs_json, mu_node_id, STAMP_VALID)
        )
        stamp_id = cursor.lastrowid
        if event_refs:
            for ev_id in event_refs:
                cursor.execute(
                    """INSERT INTO bcl_stamp_events
                       (stamp_id, event_type, event_ref, cause)
                       VALUES (%s, %s, %s, %s)""",
                    (stamp_id, "EVENT_REF", str(ev_id), "linked from reasoning trace")
                )
        self.state["conn"].commit()
        cursor.close()
        self.state["last_stamp_id"] = stamp_id
        self.state["stats"]["stamps_built"] += 1
        return (1, {
            "stamp_id": stamp_id,
            "trace_id": trace_id,
            "bcl_method_id": bcl_method_id,
            "goal": goal,
            "intent": intent,
        }, None)

    def BuildStamp(self, params):
        """Build a minimal stamp (just goal + intent, no full reasoning)."""
        return self.BuildStampFromReasoning(params)

    def InjectStampIntoCode(self, params):
        """Inject [@BCL_STAMP] header block into method_code in vb_methods."""
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        stamp_id = self._p(params, "stamp_id")
        if not stamp_id:
            return (0, None, ("MISSING_PARAM", "stamp_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute("SELECT * FROM bcl_stamps WHERE id = %s", (stamp_id,))
        stamp = cursor.fetchone()
        if not stamp:
            cursor.close()
            return (0, None, ("NOT_FOUND", "stamp not found", 0))
        bcl_method_id = stamp["bcl_method_id"]
        cursor.execute(
            """SELECT v.id as vb_method_id, v.method_code as vb_code
               FROM bcl_methods m
               LEFT JOIN vb_methods v ON m.source_method_id = v.id
               WHERE m.id = %s""",
            (bcl_method_id,)
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return (0, None, ("NOT_FOUND", "bcl_method not found", 0))
        vb_method_id = row.get("vb_method_id")
        if not vb_method_id:
            cursor.close()
            return (0, None, ("NO_SOURCE", "bcl_method has no source_method_id link", 0))
        old_code = row.get("vb_code", "")
        if not old_code:
            cursor.close()
            return (0, None, ("NO_CODE", "source method has no code", 0))
        if "[@BCL_STAMP]" in old_code:
            lines = old_code.split("\n")
            new_lines = []
            for line in lines:
                if "[@BCL_STAMP]" not in line:
                    new_lines.append(line)
            old_code = "\n".join(new_lines)
        stamp_header = self._format_stamp_header(stamp)
        new_code = stamp_header + "\n" + old_code
        cursor = self.state["conn"].cursor()
        cursor.execute(
            "UPDATE vb_methods SET method_code = %s WHERE id = %s",
            (new_code, vb_method_id)
        )
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["stamps_injected"] += 1
        return (1, {
            "stamp_id": stamp_id,
            "vb_method_id": vb_method_id,
            "trace_id": stamp["trace_id"],
            "injected": True,
        }, None)

    def _format_stamp_header(self, stamp):
        """Format the [@BCL_STAMP] header block for injection into source."""
        parts = [
            'trace_id="' + str(stamp["trace_id"]) + '"',
            'goal="' + str(stamp.get("goal", "")) + '"',
        ]
        if stamp.get("intent"):
            parts.append('intent="' + str(stamp["intent"]) + '"')
        if stamp.get("source_nodes"):
            parts.append('source_nodes=' + str(stamp["source_nodes"]))
        if stamp.get("changes_applied"):
            parts.append('changes_applied=' + str(stamp["changes_applied"]))
        if stamp.get("rejected_paths"):
            parts.append('rejected_paths=' + str(stamp["rejected_paths"]))
        if stamp.get("event_refs"):
            parts.append('event_refs=' + str(stamp["event_refs"]))
        if stamp.get("mu_node_id"):
            parts.append('mu_node_id=' + str(stamp["mu_node_id"]))
        return "    # [@BCL_STAMP]{" + " ".join(parts) + "}"

    def GetStamp(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        stamp_id = self._p(params, "stamp_id")
        if not stamp_id:
            return (0, None, ("MISSING_PARAM", "stamp_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute("SELECT * FROM bcl_stamps WHERE id = %s", (stamp_id,))
        stamp = cursor.fetchone()
        cursor.close()
        if not stamp:
            return (0, None, ("NOT_FOUND", "stamp not found", 0))
        return (1, stamp, None)

    def QueryStampsForMethod(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        bcl_method_id = self._p(params, "bcl_method_id")
        if not bcl_method_id:
            return (0, None, ("MISSING_PARAM", "bcl_method_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM bcl_stamps WHERE bcl_method_id = %s ORDER BY created_at DESC",
            (bcl_method_id,)
        )
        stamps = cursor.fetchall()
        cursor.close()
        return (1, {"stamps": stamps, "count": len(stamps)}, None)

    def QueryStampsForClass(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        bcl_class_id = self._p(params, "bcl_class_id")
        if not bcl_class_id:
            return (0, None, ("MISSING_PARAM", "bcl_class_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM bcl_stamps WHERE bcl_class_id = %s ORDER BY created_at DESC",
            (bcl_class_id,)
        )
        stamps = cursor.fetchall()
        cursor.close()
        return (1, {"stamps": stamps, "count": len(stamps)}, None)

    def InvalidateStamp(self, params):
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        stamp_id = self._p(params, "stamp_id")
        reason = self._p(params, "reason", "stale")
        if not stamp_id:
            return (0, None, ("MISSING_PARAM", "stamp_id is required", 0))
        cursor = self.state["conn"].cursor()
        cursor.execute(
            "UPDATE bcl_stamps SET stamp_status = %s WHERE id = %s",
            (STAMP_STALE, stamp_id)
        )
        self.state["conn"].commit()
        cursor.close()
        self.state["stats"]["stamps_invalidated"] += 1
        return (1, {"stamp_id": stamp_id, "new_status": STAMP_STALE, "reason": reason}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "last_stamp_id": self.state["last_stamp_id"],
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
