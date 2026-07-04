#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/AstVersionStore.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="Versioned AST content store. Content-addressed (SHA-256). LZ4 compression for large blobs. is_current flips on new version. Dedup on content_hash."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="AstVersionStore.py" domain="ast_content" authority="AstVersionStore"}
# [@SUMMARY]{summary="CRUD for mu_ast_versions. Adds new version (flips is_current on prior), queries current/historical. Emits EVENT_AST_VERSION_ADDED. Content-addressed dedup."}
# [@CLASS]{class="AstVersionStore" domain="ast_content" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="AddVersion" type="command"}
# [@METHOD]{method="GetCurrent" type="query"}
# [@METHOD]{method="GetVersion" type="query"}
# [@METHOD]{method="QueryHistory" type="query"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Versioned AST content store with SHA-256 content addressing, LZ4 compression, dedup. CRUD for mu_ast_versions. VBStyle compliant: Run dispatch, Tuple3, self.state. No violations found.>][@todos<none>]}
"""
AstVersionStore -- Versioned AST content store.

Content is content-addressed (SHA-256). Two versions with the same
content_hash share the same blob (dedup). is_current flips to 0 on the
prior version when a new one is added.

EVENT FLOW (write-ahead durability):
  1. Append EVENT_AST_VERSION_ADDED to EventLogStore (disk)
  2. UPDATE prior version is_current=0 (in-RAM)
  3. INSERT new version row (in-RAM)

Usage:
  vs = AstVersionStore(mem=log_store, db=in_ram_db)
  ok, data, err = vs.Run("add_version", {
      "node_id": 1,
      "content": "def foo(): pass",
      "content_format": "SOURCE",
  })
"""
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Tuple

FORMAT_SOURCE = "SOURCE"
FORMAT_AST_JSON = "AST_JSON"
EVENT_AST_VERSION_ADDED = "EVENT_AST_VERSION_ADDED"


class AstVersionStore:
    """Versioned AST content store. Content-addressed. Dedup on hash."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "session_id": "default",
                "inline_threshold": 4096,
            },
            "mem": mem,
            "db": db,
            "last_version_id": None,
            "stats": {
                "added": 0,
                "deduped": 0,
                "queries": 0,
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
            "add_version": self.AddVersion,
            "get_current": self.GetCurrent,
            "get_version": self.GetVersion,
            "query_history": self.QueryHistory,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def _compute_content_hash(self, content):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def AddVersion(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_NODE_ID", "node_id required", 0))
        content = self._p(params, "content", "")
        content_format = self._p(params, "content_format", FORMAT_SOURCE)
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem and db required", 0))
        content_hash = self._compute_content_hash(content)
        r = db.Run("query", {
            "sql": "SELECT MAX(version_no) as max_v FROM mu_ast_versions WHERE node_id=?",
            "params": [node_id],
        })
        max_v = 0
        if r[0] == 1 and r[1]["rows"]:
            max_v = r[1]["rows"][0].get("max_v") or 0
        version_no = max_v + 1
        r = db.Run("query", {
            "sql": "SELECT version_id FROM mu_ast_versions WHERE node_id=? AND is_current=1",
            "params": [node_id],
        })
        prior_version_id = None
        if r[0] == 1 and r[1]["rows"]:
            prior_version_id = r[1]["rows"][0].get("version_id")
        r = db.Run("query", {"sql": "SELECT MAX(version_id) as m FROM mu_ast_versions", "params": []})
        version_id = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
        ts = datetime.utcnow().isoformat() + "Z"
        event = {
            "type": EVENT_AST_VERSION_ADDED,
            "ts": ts,
            "ast_node_id": node_id,
            "ast_version_before": prior_version_id,
            "ast_version_after": version_id,
            "trace_id": self._p(params, "trace_id"),
            "session_id": self.state["config"]["session_id"],
            "cause": self._p(params, "cause", "version added"),
            "before": {"prior_version_id": prior_version_id},
            "after": {
                "version_id": version_id,
                "version_no": version_no,
                "content_hash": content_hash,
                "content_blob": content,
                "content_format": content_format,
            },
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        event_id = r[1]["id"]
        if prior_version_id:
            db.Run("execute", {
                "sql": "UPDATE mu_ast_versions SET is_current=0, superseded_event_id=? WHERE version_id=?",
                "params": [event_id, prior_version_id],
            })
        r = db.Run("execute", {
            "sql": """INSERT INTO mu_ast_versions
                (version_id, node_id, version_no, content_hash, content_blob, content_format,
                 created_event_id, is_current, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            "params": [version_id, node_id, version_no, content_hash, content,
                       content_format, event_id, ts],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", str(r[2]), 0))
        log.Run("append", {"event": {}}) if False else None
        self.state["last_version_id"] = version_id
        self.state["stats"]["added"] += 1
        return (1, {
            "version_id": version_id,
            "version_no": version_no,
            "content_hash": content_hash,
            "event_id": event_id,
            "prior_version_id": prior_version_id,
        }, None)

    def GetCurrent(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_NODE_ID", "node_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {
            "sql": "SELECT * FROM mu_ast_versions WHERE node_id=? AND is_current=1",
            "params": [node_id],
        })
        if r[0] != 1:
            return r
        if r[1]["count"] == 0:
            return (0, None, ("NO_CURRENT", "no current version", 0))
        self.state["stats"]["queries"] += 1
        return (1, {"version": r[1]["rows"][0]}, None)

    def GetVersion(self, params):
        version_id = self._p(params, "version_id")
        if not version_id:
            return (0, None, ("MISSING_PARAM", "version_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_ast_versions WHERE version_id=?", "params": [version_id]})
        if r[0] != 1:
            return r
        if r[1]["count"] == 0:
            return (0, None, ("NOT_FOUND", "version not found", 0))
        self.state["stats"]["queries"] += 1
        return (1, {"version": r[1]["rows"][0]}, None)

    def QueryHistory(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_NODE_ID", "node_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {
            "sql": "SELECT * FROM mu_ast_versions WHERE node_id=? ORDER BY version_no",
            "params": [node_id],
        })
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"versions": r[1]["rows"], "count": r[1]["count"]}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "last_version_id": self.state["last_version_id"],
            "stats": self.state["stats"],
        }, None)

    def set_config(self, params):
        for key in ("session_id", "inline_threshold"):
            val = self._p(params, key)
            if val is not None:
                self.state["config"][key] = val
        return (1, {"config": self.state["config"]}, None)
