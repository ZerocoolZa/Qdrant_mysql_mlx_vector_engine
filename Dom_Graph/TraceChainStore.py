#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/TraceChainStore.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="Trace chain steps. Deterministic replay. step_no must be contiguous from 1. No natural language - structured transitions only."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="TraceChainStore.py" domain="trace_replay" authority="TraceChainStore"}
# [@SUMMARY]{summary="Append + verify continuity for mu_trace_steps. step_no must be contiguous from 1 per trace_id. Emits EVENT_TRACE_STEP_APPENDED. VerifyContinuity checks for gaps."}
# [@CLASS]{class="TraceChainStore" domain="trace_replay" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="AppendStep" type="command"}
# [@METHOD]{method="QueryTrace" type="query"}
# [@METHOD]{method="VerifyContinuity" type="gate"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Trace chain steps for deterministic replay. Append + verify continuity. step_no must be contiguous from 1. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}
"""
TraceChainStore -- Deterministic replay trace chains.

Each trace_id has a sequence of steps (step_no 1, 2, 3, ...). Steps are
structured atoms (decision, input_nodes, transformation, output_nodes) -
NO natural language. The chain must be contiguous (no gaps in step_no).

EVENT FLOW:
  1. Append EVENT_TRACE_STEP_APPENDED to EventLogStore
  2. INSERT into mu_trace_steps (in-RAM)

Usage:
  tc = TraceChainStore(mem=log, db=db)
  ok, data, err = tc.Run("append_step", {
      "trace_id": "tr_abc",
      "decision": "PARSE_BCL_HEADER",
      "input_nodes": [1],
      "transformation": "extract_type_verb_noun",
      "output_nodes": [2],
  })
  ok, data, err = tc.Run("verify_continuity", {"trace_id": "tr_abc"})
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

EVENT_TRACE_STEP_APPENDED = "EVENT_TRACE_STEP_APPENDED"


class TraceChainStore:
    """Trace chain steps. Contiguous step_no. Structured atoms only."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "session_id": "default",
            },
            "mem": mem,
            "db": db,
            "stats": {
                "appended": 0,
                "queries": 0,
                "continuity_checks": 0,
                "broken": 0,
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
            "append_step": self.AppendStep,
            "query_trace": self.QueryTrace,
            "verify_continuity": self.VerifyContinuity,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def AppendStep(self, params):
        trace_id = self._p(params, "trace_id")
        decision = self._p(params, "decision")
        transformation = self._p(params, "transformation")
        if not trace_id or not decision or not transformation:
            return (0, None, ("MISSING_PARAM", "trace_id, decision, transformation required", 0))
        input_nodes = self._p(params, "input_nodes", [])
        output_nodes = self._p(params, "output_nodes", [])
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem and db required", 0))
        r = db.Run("query", {
            "sql": "SELECT MAX(step_no) as max_s FROM mu_trace_steps WHERE trace_id=?",
            "params": [trace_id],
        })
        max_s = 0
        if r[0] == 1 and r[1]["rows"]:
            max_s = r[1]["rows"][0].get("max_s") or 0
        step_no = max_s + 1
        ts = datetime.utcnow().isoformat() + "Z"
        event = {
            "type": EVENT_TRACE_STEP_APPENDED,
            "ts": ts,
            "trace_id": trace_id,
            "session_id": self.state["config"]["session_id"],
            "cause": self._p(params, "cause", "step appended"),
            "before": None,
            "after": {
                "step_no": step_no,
                "decision": decision,
                "input_nodes": input_nodes,
                "transformation": transformation,
                "output_nodes": output_nodes,
            },
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        event_id = r[1]["id"]
        r = db.Run("execute", {
            "sql": """INSERT INTO mu_trace_steps
                (trace_id, step_no, decision, input_nodes, transformation,
                 output_nodes, event_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            "params": [trace_id, step_no, decision,
                       json.dumps(input_nodes), transformation,
                       json.dumps(output_nodes), event_id, ts],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", str(r[2]), 0))
        self.state["stats"]["appended"] += 1
        return (1, {
            "step_no": step_no,
            "trace_id": trace_id,
            "event_id": event_id,
        }, None)

    def QueryTrace(self, params):
        trace_id = self._p(params, "trace_id")
        if not trace_id:
            return (0, None, ("MISSING_PARAM", "trace_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {
            "sql": "SELECT * FROM mu_trace_steps WHERE trace_id=? ORDER BY step_no",
            "params": [trace_id],
        })
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"steps": r[1]["rows"], "count": r[1]["count"]}, None)

    def VerifyContinuity(self, params):
        trace_id = self._p(params, "trace_id")
        if not trace_id:
            return (0, None, ("MISSING_PARAM", "trace_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {
            "sql": "SELECT step_no FROM mu_trace_steps WHERE trace_id=? ORDER BY step_no",
            "params": [trace_id],
        })
        if r[0] != 1:
            return r
        steps = [row["step_no"] for row in r[1]["rows"]]
        self.state["stats"]["continuity_checks"] += 1
        if not steps:
            return (1, {"continuous": True, "count": 0, "reason": "empty trace"}, None)
        expected = list(range(1, len(steps) + 1))
        if steps != expected:
            self.state["stats"]["broken"] += 1
            gaps = [s for s in expected if s not in steps]
            return (0, None, ("BROKEN_TRACE", "gaps at steps " + str(gaps), 0))
        return (1, {"continuous": True, "count": len(steps)}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "stats": self.state["stats"],
        }, None)

    def set_config(self, params):
        for key in ("session_id",):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        return (1, {"config": self.state["config"]}, None)
