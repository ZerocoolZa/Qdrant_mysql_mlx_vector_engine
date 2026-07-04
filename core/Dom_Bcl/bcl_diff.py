#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_diff.py"
# date="2026-06-27" author="Cascade" session_id="bcl-missing-classes"
# context="BCL Diff — structured before/after AST comparison"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_diff.py" domain="BCL" authority="BCLDiff"}
# [@SUMMARY]{summary="BCL Diff: compares two BCLNode AST trees, produces structured diff entries (added, removed, changed, moved)."}
# [@CLASS]{class="BCLDiff" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="diff" type="command"}
# [@METHOD]{method="diff_nodes" type="command"}
# [@METHOD]{method="diff_tuples" type="command"}
# [@METHOD]{method="node_signature" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import hashlib


class BCLDiff:
    """Compare two BCLNode AST trees and produce structured diff."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "diff": [],
            "added": 0,
            "removed": 0,
            "changed": 0,
            "moved": 0,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "diff":
            return self.Diff(params)
        elif command == "diff_nodes":
            return self.DiffNodes(params)
        elif command == "diff_tuples":
            return self.DiffTuples(params)
        elif command == "node_signature":
            return self.NodeSignature(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def NodeSignature(self, params):
        node = self._p(params, "node")
        if node is None:
            return (0, None, ("MISSING_PARAM", "node required", 0))
        path_result = node.Run("path", {})
        path_str = path_result[1] if path_result[0] == 1 else ""
        tuple_str = str(node.state["tuples"])
        child_names = ",".join(sorted(c.state["name"] for c in node.state["children"]))
        raw = "%s|%s|%s" % (path_str, tuple_str, child_names)
        sig = hashlib.md5(raw.encode()).hexdigest()[:12]
        return (1, {"path": path_str, "signature": sig, "tuples": len(node.state["tuples"]), "children": len(node.state["children"])}, None)

    def Diff(self, params):
        before = self._p(params, "before")
        after = self._p(params, "after")
        if before is None or after is None:
            return (0, None, ("MISSING_PARAM", "before and after required", 0))
        self.state["diff"] = []
        self.state["added"] = 0
        self.state["removed"] = 0
        self.state["changed"] = 0
        self.state["moved"] = 0
        before_map = self.BuildNodeMap(before)
        after_map = self.BuildNodeMap(after)
        for name, info in after_map.items():
            if name not in before_map:
                self.state["diff"].append({"type": "added", "name": name, "path": info["path"]})
                self.state["added"] += 1
            else:
                before_info = before_map[name]
                self.DiffTuples({"name": name, "before_tuples": before_info["tuples"], "after_tuples": info["tuples"]})
                if before_info["path"] != info["path"]:
                    self.state["diff"].append({"type": "moved", "name": name, "from": before_info["path"], "to": info["path"]})
                    self.state["moved"] += 1
                before_children = set(c.state["name"] for c in before_info["node"].state["children"])
                after_children = set(c.state["name"] for c in info["node"].state["children"])
                removed_children = before_children - after_children
                for rc in removed_children:
                    self.state["diff"].append({"type": "removed", "name": rc, "parent": name})
                    self.state["removed"] += 1
        for name, info in before_map.items():
            if name not in after_map:
                self.state["diff"].append({"type": "removed", "name": name, "path": info["path"]})
                self.state["removed"] += 1
        return (1, {
            "diff": self.state["diff"],
            "added": self.state["added"],
            "removed": self.state["removed"],
            "changed": self.state["changed"],
            "moved": self.state["moved"],
            "total": len(self.state["diff"]),
        }, None)

    def BuildNodeMap(self, root):
        node_map = {}
        self.CollectNodes(root, node_map)
        return node_map

    def CollectNodes(self, node, node_map):
        path_result = node.Run("path", {})
        path_str = path_result[1] if path_result[0] == 1 else ""
        node_map[node.state["name"]] = {
            "path": path_str,
            "tuples": [list(t) for t in node.state["tuples"]],
            "node": node,
        }
        for child in node.state["children"]:
            self.CollectNodes(child, node_map)
        return (1, True, None)

    def DiffTuples(self, params):
        name = self._p(params, "name")
        before_tuples = self._p(params, "before_tuples", [])
        after_tuples = self._p(params, "after_tuples", [])
        if before_tuples is None or after_tuples is None:
            return (0, None, ("MISSING_PARAM", "before_tuples and after_tuples required", 0))
        before_set = set(str(t) for t in before_tuples)
        after_set = set(str(t) for t in after_tuples)
        added_tuples = after_set - before_set
        removed_tuples = before_set - after_set
        if added_tuples or removed_tuples:
            self.state["diff"].append({
                "type": "changed",
                "name": name,
                "tuples_added": list(added_tuples),
                "tuples_removed": list(removed_tuples),
            })
            self.state["changed"] += 1
        return (1, {"added": list(added_tuples), "removed": list(removed_tuples)}, None)

    def DiffNodes(self, params):
        before = self._p(params, "before")
        after = self._p(params, "after")
        if before is None or after is None:
            return (0, None, ("MISSING_PARAM", "before and after required", 0))
        before_sig = self.NodeSignature({"node": before})
        after_sig = self.NodeSignature({"node": after})
        changes = []
        if before_sig[1]["signature"] != after_sig[1]["signature"]:
            changes.append({"type": "node_changed", "before": before_sig[1], "after": after_sig[1]})
        before_children = {c.state["name"]: c for c in before.state["children"]}
        after_children = {c.state["name"]: c for c in after.state["children"]}
        for cname, cnode in after_children.items():
            if cname not in before_children:
                changes.append({"type": "child_added", "name": cname})
            else:
                sub_result = self.DiffNodes({"before": before_children[cname], "after": cnode})
                if sub_result[0] == 1:
                    changes.extend(sub_result[1])
        for cname in before_children:
            if cname not in after_children:
                changes.append({"type": "child_removed", "name": cname})
        return (1, changes, None)
