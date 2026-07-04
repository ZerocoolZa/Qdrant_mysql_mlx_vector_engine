#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_visitor.py"
# date="2026-06-27" author="Cascade" session_id="bcl-missing-classes"
# context="BCL Visitor — reusable tree traversal pattern, replaces duplicated walking in engine/validator/fixer"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_visitor.py" domain="BCL" authority="BCLVisitor"}
# [@SUMMARY]{summary="BCL Visitor: generic traverser for BCLNode trees. Supports pre-order, post-order, find-by-name, find-by-path, count, collect. Replaces duplicated WalkTree/FindByName/ValidateNode logic."}
# [@CLASS]{class="BCLVisitor" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="traverse" type="command"}
# [@METHOD]{method="find_by_name" type="command"}
# [@METHOD]{method="find_by_path" type="command"}
# [@METHOD]{method="count_nodes" type="command"}
# [@METHOD]{method="collect" type="command"}
# [@METHOD]{method="collect_where" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from bcl_parser import BCLNode


class BCLVisitor:
    """Generic tree visitor for BCLNode AST trees."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "results": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "traverse":
            return self.Traverse(params)
        elif command == "find_by_name":
            return self.FindByName(params)
        elif command == "find_by_path":
            return self.FindByPath(params)
        elif command == "count_nodes":
            return self.CountNodes(params)
        elif command == "collect":
            return self.Collect(params)
        elif command == "collect_where":
            return self.CollectWhere(params)
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

    def Traverse(self, params):
        root = self._p(params, "root")
        mode = self._p(params, "mode", "pre")
        callback = self._p(params, "callback")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        self.state["results"] = []
        self.TraverseNode(root, mode, callback, 0)
        return (1, {"visited": len(self.state["results"]), "results": self.state["results"]}, None)

    def TraverseNode(self, node, mode, callback, depth):
        if mode == "pre":
            self.ApplyCallback(node, callback, depth)
        for child in node.state["children"]:
            self.TraverseNode(child, mode, callback, depth + 1)
        if mode == "post":
            self.ApplyCallback(node, callback, depth)
        return (1, True, None)

    def ApplyCallback(self, node, callback, depth):
        entry = {"name": node.state["name"], "depth": depth, "tuples": len(node.state["tuples"]), "children": len(node.state["children"])}
        path_result = node.Run("path", {})
        entry["path"] = path_result[1] if path_result[0] == 1 else ""
        if callback is not None:
            cb_result = callback(node, depth)
            if cb_result is not None:
                entry["callback_result"] = cb_result
        self.state["results"].append(entry)
        return (1, True, None)

    def FindByName(self, params):
        root = self._p(params, "root")
        name = self._p(params, "name")
        if root is None or name is None:
            return (0, None, ("MISSING_PARAM", "root and name required", 0))
        result = self.SearchByName(root, name)
        if result is not None:
            return (1, result, None)
        return (1, None, None)

    def SearchByName(self, node, name):
        if node.state["name"] == name:
            return node
        for child in node.state["children"]:
            found = self.SearchByName(child, name)
            if found is not None:
                return found
        return None

    def FindByPath(self, params):
        root = self._p(params, "root")
        path = self._p(params, "path")
        if root is None or path is None:
            return (0, None, ("MISSING_PARAM", "root and path required", 0))
        if path == "/root" or not path:
            return (1, root, None)
        parts = path.strip("/").split("/")
        if parts and parts[0] == "root":
            parts = parts[1:]
        current = root
        for part in parts:
            found = None
            for child in current.state["children"]:
                if child.state["name"] == part:
                    found = child
                    break
            if found is None:
                return (1, None, None)
            current = found
        return (1, current, None)

    def CountNodes(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        count = self.CountRecursive(root)
        return (1, count, None)

    def CountRecursive(self, node):
        count = 1
        for child in node.state["children"]:
            count += self.CountRecursive(child)
        return count

    def Collect(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        entries = []
        self.CollectEntries(root, entries, 0)
        return (1, {"entries": entries, "count": len(entries)}, None)

    def CollectEntries(self, node, entries, depth):
        path_result = node.Run("path", {})
        path_str = path_result[1] if path_result[0] == 1 else ""
        entries.append({
            "name": node.state["name"],
            "path": path_str,
            "depth": depth,
            "tuples": len(node.state["tuples"]),
            "children": len(node.state["children"]),
        })
        for child in node.state["children"]:
            self.CollectEntries(child, entries, depth + 1)
        return (1, True, None)

    def CollectWhere(self, params):
        root = self._p(params, "root")
        predicate = self._p(params, "predicate")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        if predicate is None:
            return (0, None, ("MISSING_PARAM", "predicate required", 0))
        matches = []
        self.CollectWhereRecursive(root, predicate, matches)
        return (1, {"matches": matches, "count": len(matches)}, None)

    def CollectWhereRecursive(self, node, predicate, matches):
        if predicate(node):
            path_result = node.Run("path", {})
            path_str = path_result[1] if path_result[0] == 1 else ""
            matches.append({
                "name": node.state["name"],
                "path": path_str,
                "tuples": len(node.state["tuples"]),
                "children": len(node.state["children"]),
            })
        for child in node.state["children"]:
            self.CollectWhereRecursive(child, predicate, matches)
        return (1, True, None)
