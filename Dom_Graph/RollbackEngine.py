#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/RollbackEngine.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="Append-only rollback. RollbackTo(T) appends EVENT_ROLLBACK that re-points is_current. Never deletes history. Disk-first durability."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="RollbackEngine.py" domain="rollback" authority="RollbackEngine"}
# [@SUMMARY]{summary="Append-only RollbackTo(target_event_id). Appends EVENT_ROLLBACK to disk first, then re-points is_current in-RAM. History preserved forever. Never deletes."}
# [@CLASS]{class="RollbackEngine" domain="rollback" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="RollbackTo" type="command"}
# [@METHOD]{method="QueryRollbacks" type="query"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Append-only rollback engine. RollbackTo appends EVENT_ROLLBACK that re-points is_current. Never deletes history. Disk-first durability. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}
"""
RollbackEngine -- Append-only rollback. Never deletes history.

RollbackTo(T) appends an EVENT_ROLLBACK that re-points is_current to the
versions that were current at event T. The history of what was rolled back
is preserved forever - you can always rebuild at T-1 to see pre-rollback
state.

DURABILITY RULE: event appended to disk file BEFORE in-RAM DB mutated.

Usage:
  rb = RollbackEngine(mem=log, db=db, replay=replay_engine)
  ok, data, err = rb.Run("rollback_to", {"target_event_id": 10})
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

EVENT_ROLLBACK = "EVENT_ROLLBACK"


class RollbackEngine:
    """Append-only rollback. Never deletes. Disk-first durability."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "session_id": "default",
            },
            "mem": mem,
            "db": db,
            "replay": None,
            "stats": {
                "rollbacks": 0,
                "queries": 0,
            },
        }
        if param:
            if "replay" in param:
                self.state["replay"] = param["replay"]
                param = {k: v for k, v in param.items() if k != "replay"}
            self.state["config"].update(param)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "rollback_to": self.RollbackTo,
            "query_rollbacks": self.QueryRollbacks,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def RollbackTo(self, params):
        target = self._p(params, "target_event_id")
        if target is None:
            return (0, None, ("MISSING_PARAM", "target_event_id required", 0))
        log = self.state["mem"]
        db = self.state["db"]
        replay = self.state["replay"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem and db required", 0))
        if not replay:
            return (0, None, ("NO_REPLAY", "replay engine required", 0))
        r = log.Run("read_state", {})
        latest_event_id = r[1]["next_id"] - 1
        r = db.Run("query", {
            "sql": "SELECT node_id, version_id FROM mu_ast_versions WHERE is_current=1",
            "params": [],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", "cannot read current versions", 0))
        current_versions = {str(row["node_id"]): row["version_id"] for row in r[1]["rows"]}
        r = replay.Run("rebuild_at", {"event_id": target})
        if r[0] != 1:
            return (0, None, ("REBUILD_FAILED", str(r[2]), 0))
        r = db.Run("query", {
            "sql": "SELECT node_id, version_id FROM mu_ast_versions WHERE is_current=1",
            "params": [],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", "cannot read target versions", 0))
        target_versions = {str(row["node_id"]): row["version_id"] for row in r[1]["rows"]}
        r = replay.Run("rebuild_at", {"event_id": latest_event_id})
        if r[0] != 1:
            return (0, None, ("RESTORE_FAILED", str(r[2]), 0))
        ts = datetime.utcnow().isoformat() + "Z"
        event = {
            "type": EVENT_ROLLBACK,
            "ts": ts,
            "session_id": self.state["config"]["session_id"],
            "cause": self._p(params, "cause", "rollback to event " + str(target)),
            "before": current_versions,
            "after": target_versions,
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        event_id = r[1]["id"]
        r = db.Run("execute", {
            "sql": """INSERT INTO mu_events
                (id, type, ts, trace_id, session_id, cause, before_state, after_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            "params": [event_id, EVENT_ROLLBACK, ts, None,
                       self.state["config"]["session_id"],
                       event["cause"],
                       json.dumps(current_versions),
                       json.dumps(target_versions)],
        })
        for node_id, version_id in target_versions.items():
            db.Run("execute", {
                "sql": "UPDATE mu_ast_versions SET is_current=0 WHERE node_id=?",
                "params": [int(node_id)],
            })
            db.Run("execute", {
                "sql": "UPDATE mu_ast_versions SET is_current=1 WHERE node_id=? AND version_id=?",
                "params": [int(node_id), int(version_id)],
            })
        self.state["stats"]["rollbacks"] += 1
        return (1, {
            "event_id": event_id,
            "target_event_id": target,
            "nodes_rolled_back": len(target_versions),
        }, None)

    def QueryRollbacks(self, params):
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        limit = self._p(params, "limit", 20)
        r = db.Run("query", {
            "sql": "SELECT * FROM mu_events WHERE type=? ORDER BY id DESC LIMIT ?",
            "params": [EVENT_ROLLBACK, limit],
        })
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"rollbacks": r[1]["rows"], "count": r[1]["count"]}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "stats": self.state["stats"],
        }, None)

    def set_config(self, params):
        replay = self._p(params, "replay")
        if replay:
            self.state["replay"] = replay
        for key in ("session_id",):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        return (1, {"config": self.state["config"]}, None)
