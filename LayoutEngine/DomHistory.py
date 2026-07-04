#[@GHOST]{[@file<DomHistory.py>][@domain<layout_history>][@role<event_sourcing>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<history>][@return<Tuple3>][@state<events,snapshots,cursor>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/DomHistory.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Event-sourced DOM history — undo/redo + DB serialization. Adapted from EventStore + Snapshot + StateCache in _extracted_existing.py}
#[@CLASS]{DomHistory — records layout mutations as events, supports replay/undo/redo, serializes to DB-ready dicts}
#[@METHOD]{Run dispatch: record, undo, redo, replay, serialize, restore, read_state, set_config}

import time
import copy
import Config
from LayoutNode import LayoutNode


class LayoutEvent:
    """A single layout mutation event (immutable record)."""

    def __init__(self, nid, event_type, payload, timestamp=None):
        self.id = "evt_" + str(int(time.time() * 1000000)) + "_" + nid
        self.nid = nid
        self.event_type = event_type   # add / remove / set_config / move
        self.payload = payload
        self.timestamp = timestamp or time.time()

    def to_dict(self):
        return {
            "id": self.id,
            "nid": self.nid,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class DomHistory:
    """Event-sourced history for the Layout Graph DOM.

    Adapted from EventStore + Snapshot + StateCache in the extracted code
    (_extracted_existing.py lines 5689, 5796, 5802):
      - EventStore: append-only event log with replay
      - Snapshot: cached state at a point in time
      - StateCache: event_id -> snapshot map for fast restore

    This adds undo/redo and DB serialization to the LayoutNode tree.
    Every mutation (add/remove/set_config) is recorded as a LayoutEvent.
    Undo replays events up to a cursor; redo moves the cursor forward.
    serialize() produces a DB-ready list of event dicts that can be stored
    in MySQL and replayed to reconstruct the exact tree.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "events": [],       # append-only list of LayoutEvent
            "cursor": -1,       # index of last applied event (-1 = empty)
            "snapshots": {},    # cursor_index -> serialized tree state
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "record": self.record,
            "undo": self.undo,
            "redo": self.redo,
            "replay": self.replay,
            "serialize": self.serialize,
            "restore": self.restore,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # record: append a mutation event + advance cursor
    # ------------------------------------------------------------------
    def record(self, params):
        nid = self._p(params, "nid")
        event_type = self._p(params, "event_type")
        payload = self._p(params, "payload", {})
        if nid is None or event_type is None:
            return (0, None, ("missing_param", "record requires nid + event_type", 0))
        event = LayoutEvent(nid, event_type, payload)
        # If we're not at the end (undo happened), truncate future events
        if self.state["cursor"] < len(self.state["events"]) - 1:
            self.state["events"] = self.state["events"][:self.state["cursor"] + 1]
            # Drop snapshots beyond cursor
            self.state["snapshots"] = {
                k: v for k, v in self.state["snapshots"].items()
                if k <= self.state["cursor"]
            }
        self.state["events"].append(event)
        self.state["cursor"] = len(self.state["events"]) - 1
        return (1, event.to_dict(), None)

    # ------------------------------------------------------------------
    # undo: move cursor back by N (default 1)
    # ------------------------------------------------------------------
    def undo(self, params):
        steps = self._p(params, "steps", 1)
        if self.state["cursor"] < 0:
            return (0, None, ("nothing_to_undo", "no events to undo", 0))
        self.state["cursor"] = max(-1, self.state["cursor"] - steps)
        return (1, self.state["cursor"], None)

    # ------------------------------------------------------------------
    # redo: move cursor forward by N (default 1)
    # ------------------------------------------------------------------
    def redo(self, params):
        steps = self._p(params, "steps", 1)
        if self.state["cursor"] >= len(self.state["events"]) - 1:
            return (0, None, ("nothing_to_redo", "at end of history", 0))
        self.state["cursor"] = min(
            len(self.state["events"]) - 1,
            self.state["cursor"] + steps,
        )
        return (1, self.state["cursor"], None)

    # ------------------------------------------------------------------
    # replay: apply events 0..cursor to a root tree
    # ------------------------------------------------------------------
    def replay(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("missing_root", "replay requires {'root': LayoutNode}", 0))
        # Walk to build nid -> node map
        ok, data, err = root.walk({"order": "pre"})
        if not ok:
            return (0, None, err)
        nid_map = {n.state["nid"]: n for n in data}
        applied = 0
        for i in range(self.state["cursor"] + 1):
            evt = self.state["events"][i]
            target = nid_map.get(evt.nid)
            if target is None:
                # Node may have been added by a prior event — try re-walk
                ok, data, err = root.walk({"order": "pre"})
                if ok:
                    nid_map = {n.state["nid"]: n for n in data}
                    target = nid_map.get(evt.nid)
            if target is None:
                continue
            if evt.event_type == "set_config":
                target.Run("set_config", evt.payload)
            elif evt.event_type == "add":
                child = evt.payload.get("node")
                if child is not None:
                    target.Run("add", {"node": child})
                    nid_map[child.state["nid"]] = child
            elif evt.event_type == "remove":
                target.Run("remove", {"nid": evt.payload.get("child_nid")})
            applied += 1
        return (1, applied, None)

    # ------------------------------------------------------------------
    # serialize: produce DB-ready list of event dicts (for MySQL storage)
    # ------------------------------------------------------------------
    def serialize(self, params):
        events = []
        for i in range(self.state["cursor"] + 1):
            evt = self.state["events"][i]
            events.append(evt.to_dict())
        return (1, events, None)

    # ------------------------------------------------------------------
    # restore: rebuild history from a serialized event list (from DB)
    # ------------------------------------------------------------------
    def restore(self, params):
        events = self._p(params, "events")
        if not isinstance(events, list):
            return (0, None, ("bad_param", "restore requires {'events': list}", 0))
        self.state["events"] = []
        self.state["snapshots"] = {}
        self.state["cursor"] = -1
        for ed in events:
            evt = LayoutEvent(
                ed.get("nid"),
                ed.get("event_type"),
                ed.get("payload", {}),
                ed.get("timestamp"),
            )
            evt.id = ed.get("id", evt.id)
            self.state["events"].append(evt)
        self.state["cursor"] = len(self.state["events"]) - 1
        return (1, len(self.state["events"]), None)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self, params=None):
        return (1, {
            "event_count": len(self.state["events"]),
            "cursor": self.state["cursor"],
            "can_undo": self.state["cursor"] >= 0,
            "can_redo": self.state["cursor"] < len(self.state["events"]) - 1,
            "snapshot_count": len(self.state["snapshots"]),
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        return (1, True, None)
