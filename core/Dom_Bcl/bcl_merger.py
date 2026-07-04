#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_merger.py"
# date="2026-06-27" author="Cascade" session_id="bcl-missing-classes"
# context="BCL Merger — merge multiple BCL documents into one tree"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_merger.py" domain="BCL" authority="BCLMerger"}
# [@SUMMARY]{summary="BCL Merger: combines multiple BCLNode AST trees into one. Handles conflicts (duplicate names), tuple merging, child merging."}
# [@CLASS]{class="BCLMerger" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="merge" type="command"}
# [@METHOD]{method="merge_node" type="command"}
# [@METHOD]{method="merge_tuples" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from bcl_parser import BCLNode


class BCLMerger:
    """Merge multiple BCLNode AST trees into one."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"strategy": "union"},
            "merged_count": 0,
            "conflicts": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "merge":
            return self.Merge(params)
        elif command == "merge_node":
            return self.MergeNode(params)
        elif command == "merge_tuples":
            return self.MergeTuples(params)
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

    def Merge(self, params):
        trees = self._p(params, "trees")
        if trees is None:
            return (0, None, ("MISSING_PARAM", "trees required", 0))
        if not trees:
            return (0, None, ("EMPTY_INPUT", "trees list is empty", 0))
        self.state["merged_count"] = 0
        self.state["conflicts"] = []
        merged_root = BCLNode("root")
        for tree in trees:
            for child in tree.state["children"]:
                self.MergeNodeIntoParent(child, merged_root)
            self.state["merged_count"] += 1
        return (1, {
            "root": merged_root,
            "merged_count": self.state["merged_count"],
            "conflicts": self.state["conflicts"],
            "conflict_count": len(self.state["conflicts"]),
        }, None)

    def MergeNodeIntoParent(self, source_node, target_parent):
        existing = None
        for child in target_parent.state["children"]:
            if child.state["name"] == source_node.state["name"]:
                existing = child
                break
        if existing is not None:
            self.MergeTuples({"target": existing, "source": source_node})
            for src_child in source_node.state["children"]:
                self.MergeNodeIntoParent(src_child, existing)
            path_result = existing.Run("path", {})
            path_str = path_result[1] if path_result[0] == 1 else ""
            self.state["conflicts"].append({
                "name": source_node.state["name"],
                "path": path_str,
                "action": "merged",
            })
        else:
            new_node = BCLNode(source_node.state["name"], parent=target_parent)
            new_node.state["tuples"] = [list(t) for t in source_node.state["tuples"]]
            for src_child in source_node.state["children"]:
                cloned = self.CloneSubtree(src_child, new_node)
                new_node.state["children"].append(cloned)
            target_parent.state["children"].append(new_node)
        return (1, True, None)

    def MergeTuples(self, params):
        target = self._p(params, "target")
        source = self._p(params, "source")
        if target is None or source is None:
            return (0, None, ("MISSING_PARAM", "target and source required", 0))
        existing_keys = set()
        for t in target.state["tuples"]:
            if t:
                existing_keys.add(str(t[0]))
        for t in source.state["tuples"]:
            if not t:
                continue
            key = str(t[0])
            if key not in existing_keys:
                target.state["tuples"].append(list(t))
                existing_keys.add(key)
        return (1, {"tuples": len(target.state["tuples"])}, None)

    def CloneSubtree(self, node, parent):
        new_node = BCLNode(node.state["name"], parent=parent)
        new_node.state["tuples"] = [list(t) for t in node.state["tuples"]]
        for child in node.state["children"]:
            cloned = self.CloneSubtree(child, new_node)
            new_node.state["children"].append(cloned)
        return new_node

    def MergeNode(self, params):
        target = self._p(params, "target")
        source = self._p(params, "source")
        if target is None or source is None:
            return (0, None, ("MISSING_PARAM", "target and source required", 0))
        self.MergeTuples({"target": target, "source": source})
        for src_child in source.state["children"]:
            self.MergeNodeIntoParent(src_child, target)
        return (1, {"merged": True, "tuples": len(target.state["tuples"]), "children": len(target.state["children"])}, None)
