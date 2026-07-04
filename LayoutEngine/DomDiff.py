#[@GHOST]{[@file<DomDiff.py>][@domain<layout_dom_diff>][@role<incremental_invalidation>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<diff>][@return<Tuple3>][@state<previous,current,diff>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/DomDiff.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{DOM diff/incremental invalidation — computes added/removed/changed node sets between two tree states. Adapted from IRStateCache.diff pattern in _extracted_existing.py}
#[@CLASS]{DomDiff — snapshots a LayoutNode tree, diffs against previous snapshot, returns what changed for targeted reflow}
#[@METHOD]{Run dispatch: snapshot, diff, changed_nodes, read_state, set_config}

import copy
import Config
from LayoutNode import LayoutNode


class DomDiff:
    """DOM diff engine for incremental reflow.

    Adapted from the IRStateCache.diff() pattern in the extracted code
    (_extracted_existing.py line 5404): snapshot current state, compare
    against previous, return added/removed/changed sets.

    Instead of dirty flags alone, this gives the Lifecycle pipeline a precise
    list of WHICH nodes changed and HOW — so the solver can skip re-measuring
    entire subtrees that didn't change at all.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "previous": {},   # nid -> snapshot dict
            "current": {},    # nid -> snapshot dict
            "last_diff": None,
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "snapshot": self.snapshot,
            "diff": self.diff,
            "changed_nodes": self.changed_nodes,
            "commit": self.commit,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # snapshot: capture current tree state into self.state["current"]
    # Call commit() between snapshots to roll current -> previous.
    # ------------------------------------------------------------------
    def snapshot(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("missing_root", "snapshot requires {'root': LayoutNode}", 0))
        current = {}
        ok, data, err = root.walk({"order": "pre"})
        if not ok:
            return (0, None, err)
        for node in data:
            current[node.state["nid"]] = self._snapshot_node(node)
        self.state["current"] = current
        return (1, len(current), None)

    def _snapshot_node(self, node):
        s = node.state
        rect = s["rect"]
        measure = s["measure"]
        return {
            "nid": s["nid"],
            "kind": s["kind"],
            "constraints": dict(s["constraints"]),
            "style": dict(s["style"]),
            "content": s["content"],
            "rect": (rect.x, rect.y, rect.w, rect.h) if rect else None,
            "measure": (measure.w, measure.h) if measure else None,
            "child_count": len(s["children"]),
            "dirty": s["dirty"],
        }

    # ------------------------------------------------------------------
    # commit: roll current -> previous (call after processing a diff)
    # ------------------------------------------------------------------
    def commit(self, params=None):
        self.state["previous"] = self.state["current"]
        self.state["current"] = {}
        return (1, True, None)

    # ------------------------------------------------------------------
    # diff: compare current vs previous -> added/removed/changed
    # ------------------------------------------------------------------
    def diff(self, params):
        prev = self.state["previous"]
        curr = self.state["current"]
        prev_keys = set(prev.keys())
        curr_keys = set(curr.keys())

        added = [curr[k] for k in sorted(curr_keys - prev_keys)]
        removed = [prev[k] for k in sorted(prev_keys - curr_keys)]
        changed = []
        for k in sorted(curr_keys & prev_keys):
            if self._node_changed(prev[k], curr[k]):
                changed.append({"nid": k, "before": prev[k], "after": curr[k]})

        result = {"added": added, "removed": removed, "changed": changed}
        self.state["last_diff"] = result
        return (1, result, None)

    def _node_changed(self, a, b):
        # Compare the fields that affect layout
        if a["kind"] != b["kind"]:
            return True
        if a["constraints"] != b["constraints"]:
            return True
        if a["style"] != b["style"]:
            return True
        if a["content"] != b["content"]:
            return True
        if a["child_count"] != b["child_count"]:
            return True
        if a["rect"] != b["rect"]:
            return True
        return False

    # ------------------------------------------------------------------
    # changed_nodes: return list of nids that changed (for targeted reflow)
    # ------------------------------------------------------------------
    def changed_nodes(self, params):
        if self.state["last_diff"] is None:
            ok, data, err = self.diff({})
            if not ok:
                return (0, None, err)
        d = self.state["last_diff"]
        nids = set()
        for n in d["added"]:
            nids.add(n["nid"])
        for n in d["changed"]:
            nids.add(n["nid"])
        return (1, sorted(nids), None)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        return (1, {
            "previous_count": len(self.state["previous"]),
            "current_count": len(self.state["current"]),
            "has_diff": self.state["last_diff"] is not None,
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        return (1, True, None)
