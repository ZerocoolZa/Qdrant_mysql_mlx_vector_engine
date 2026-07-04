#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/EventLogStore.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="Append-only event log file writer/reader. Durable truth on disk. JSON Lines format. Write-ahead before in-RAM mutation."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="EventLogStore.py" domain="event_log" authority="EventLogStore"}
# [@SUMMARY]{summary="Append-only JSON Lines event log on disk. Sole durable truth. Write-ahead durability: events appended to file before in-RAM DB mutated. Reader yields events for replay."}
# [@CLASS]{class="EventLogStore" domain="event_log" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="Append" type="command"}
# [@METHOD]{method="ReadAll" type="query"}
# [@METHOD]{method="ReadFrom" type="query"}
# [@METHOD]{method="ReadLast" type="query"}
# [@METHOD]{method="TruncateAt" type="command"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Append-only JSON Lines event log on disk. VBStyle: Run dispatch, Tuple3, self.state. Has hardcoded DEFAULT_LOG_PATH constant.>][@todos<Consider making DEFAULT_LOG_PATH configurable via param instead of module constant.>]}
"""
EventLogStore -- Append-only JSON Lines event log on disk.

The .log file is the SOLE DURABLE TRUTH. Every MemUnit mutation appends
an event here BEFORE mutating the in-RAM SQLite DB (write-ahead durability).

File format: one JSON object per line (JSON Lines / jsonl).
- id is monotonic, gapless, never reused
- every line is self-contained
- corruption recovery = truncate at last valid line + replay

Usage:
  log = EventLogStore(param={"log_path": "/path/to/memunit_events.log"})
  log.Run("open", {})
  ok, data, err = log.Run("append", {"event": {...}})
  ok, data, err = log.Run("read_all", {})
  ok, data, err = log.Run("read_from", {"start_id": 100})
"""
import json
import os
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Tuple

DEFAULT_LOG_PATH = "memunit_events.log"


class EventLogStore:
    """Append-only event log file. Durable truth on disk."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "log_path": DEFAULT_LOG_PATH,
            },
            "next_id": 1,
            "stats": {
                "appended": 0,
                "reads": 0,
                "truncations": 0,
            },
        }
        if param:
            self.state["config"].update(param)
        self._sync_next_id()

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _sync_next_id(self):
        path = self.state["config"]["log_path"]
        if not os.path.exists(path):
            self.state["next_id"] = 1
            return
        max_id = 0
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("id", 0) > max_id:
                            max_id = obj["id"]
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        self.state["next_id"] = max_id + 1

    def _compute_hash(self, event):
        canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def Run(self, command, params=None):
        dispatch = {
            "append": self.Append,
            "read_all": self.ReadAll,
            "read_from": self.ReadFrom,
            "read_last": self.ReadLast,
            "truncate_at": self.TruncateAt,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def Append(self, params):
        event = self._p(params, "event")
        if not event:
            return (0, None, ("MISSING_EVENT", "event dict required", 0))
        if not isinstance(event, dict):
            return (0, None, ("BAD_EVENT", "event must be dict", 0))
        event_id = self.state["next_id"]
        event["id"] = event_id
        if "ts" not in event:
            event["ts"] = datetime.utcnow().isoformat() + "Z"
        if "event_hash" not in event:
            event["event_hash"] = self._compute_hash(event)
        path = self.state["config"]["log_path"]
        line = json.dumps(event, separators=(",", ":"))
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as ex:
            return (0, None, ("WRITE_FAILED", str(ex), 0))
        self.state["next_id"] = event_id + 1
        self.state["stats"]["appended"] += 1
        return (1, {"id": event_id, "event": event}, None)

    def ReadAll(self, params):
        path = self.state["config"]["log_path"]
        if not os.path.exists(path):
            self.state["stats"]["reads"] += 1
            return (1, {"events": [], "count": 0}, None)
        events = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError as ex:
            return (0, None, ("READ_FAILED", str(ex), 0))
        self.state["stats"]["reads"] += 1
        return (1, {"events": events, "count": len(events)}, None)

    def ReadFrom(self, params):
        start_id = self._p(params, "start_id", 1)
        path = self.state["config"]["log_path"]
        if not os.path.exists(path):
            self.state["stats"]["reads"] += 1
            return (1, {"events": [], "count": 0}, None)
        events = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("id", 0) >= start_id:
                            events.append(obj)
                    except json.JSONDecodeError:
                        continue
        except OSError as ex:
            return (0, None, ("READ_FAILED", str(ex), 0))
        self.state["stats"]["reads"] += 1
        return (1, {"events": events, "count": len(events)}, None)

    def ReadLast(self, params):
        path = self.state["config"]["log_path"]
        if not os.path.exists(path):
            self.state["stats"]["reads"] += 1
            return (1, {"last": None, "count": 0}, None)
        last = None
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        last = json.loads(line)
                        count += 1
                    except json.JSONDecodeError:
                        continue
        except OSError as ex:
            return (0, None, ("READ_FAILED", str(ex), 0))
        self.state["stats"]["reads"] += 1
        return (1, {"last": last, "count": count}, None)

    def TruncateAt(self, params):
        keep_id = self._p(params, "keep_id")
        if keep_id is None:
            return (0, None, ("MISSING_PARAM", "keep_id required", 0))
        path = self.state["config"]["log_path"]
        if not os.path.exists(path):
            return (1, {"truncated": 0}, None)
        kept = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("id", 0) <= keep_id:
                            kept.append(line)
                    except json.JSONDecodeError:
                        continue
            with open(path, "w", encoding="utf-8") as fh:
                for line in kept:
                    fh.write(line + "\n")
        except OSError as ex:
            return (0, None, ("TRUNCATE_FAILED", str(ex), 0))
        self.state["stats"]["truncations"] += 1
        self._sync_next_id()
        return (1, {"truncated": len(kept)}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "next_id": self.state["next_id"],
            "stats": self.state["stats"],
        }, None)

    def set_config(self, params):
        for key in ("log_path",):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        self._sync_next_id()
        return (1, {"config": self.state["config"]}, None)
