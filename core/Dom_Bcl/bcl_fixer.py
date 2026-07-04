#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_fixer.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="Stage 4: BCL Fixer — controlled mutation engine, violations in, patched AST out"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_fixer.py" domain="BCL" authority="BCLFixer"}
# [@SUMMARY]{summary="BCL Fixer: applies rule-driven transformations to AST. Deterministic, single-pass, with rollback snapshot."}
# [@CLASS]{class="BCLFixer" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="fix" type="command"}
# [@METHOD]{method="restore" type="command"}
# [@METHOD]{method="fix_container_name" type="command"}
# [@METHOD]{method="fix_weight" type="command"}
# [@METHOD]{method="find_by_path" type="command"}
# [@METHOD]{method="cleanup_empty" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from bcl_parser import BCLNode
from bcl_validator import Violation, ValidationReport, LOWERCASE_EXEMPT
from bcl_config import FIXER_MAX_ITERATIONS, WEIGHT_MIN, WEIGHT_MAX


class FixAction:
    """One recorded transformation log entry."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "rule_id": "",
            "path": "",
            "action": "",
            "old_value": None,
            "new_value": None,
        }
        if param:
            for key, value in param.items():
                self.state[key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "to_dict":
            return self.ToDict(params)
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
            self.state[key] = value
        return (1, dict(self.state), None)

    def ToDict(self, params):
        return (1, dict(self.state), None)


class BCLFixer:
    """Fix engine: applies rule-driven transformations to AST."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "actions": [],
            "snapshot": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "fix":
            return self.Fix(params)
        elif command == "restore":
            return self.Restore(params)
        elif command == "fix_container_name":
            return self.FixContainerName(params)
        elif command == "fix_weight":
            return self.FixWeight(params)
        elif command == "find_by_path":
            return self.FindByPath(params)
        elif command == "cleanup_empty":
            return self.CleanupEmpty(params)
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

    def CloneNode(self, node, parent=None):
        new_node = BCLNode(node.state["name"], parent=parent)
        new_node.state["tuples"] = [list(t) for t in node.state["tuples"]]
        for child in node.state["children"]:
            new_node.state["children"].append(self.CloneNode(child, new_node))
        return (1, new_node, None)

    def Fix(self, params):
        root = self._p(params, "root")
        report = self._p(params, "report")
        if root is None or report is None:
            return (0, None, ("MISSING_PARAM", "root and report required", 0))
        snapshot_result = self.CloneNode(root)
        snapshot = snapshot_result[1]
        self.state["snapshot"] = snapshot
        actions = []
        sorted_violations = sorted(report.state["violations"], key=lambda v: v.rule_id)
        for violation in sorted_violations:
            if violation.state["rule_id"] == 24:
                result = self.FixContainerName({"root": root, "violation": violation})
                if result[0] == 1 and result[1] is not None:
                    actions.append(result[1])
            elif violation.state["rule_id"] == 999:
                result = self.FixWeight({"root": root, "violation": violation})
                if result[0] == 1 and result[1] is not None:
                    actions.append(result[1])
        action_dicts = []
        for a in actions:
            td = a.ToDict({})
            if td[0] == 1:
                action_dicts.append(td[1])
        self.state["actions"] = action_dicts
        return (1, {"root": root, "actions": action_dicts,
                    "action_count": len(actions), "snapshot": snapshot}, None)

    def Restore(self, params):
        snapshot = self._p(params, "snapshot")
        if snapshot is None:
            snapshot = self.state.get("snapshot")
        if snapshot is None:
            return (0, None, ("NO_SNAPSHOT", "No snapshot available for restore", 0))
        clone_result = self.CloneNode(snapshot)
        return (1, {"root": clone_result[1]}, None)

    def FixContainerName(self, params):
        root = self._p(params, "root")
        violation = self._p(params, "violation")
        if root is None or violation is None:
            return (0, None, ("MISSING_PARAM", "root and violation required", 0))
        find_result = self.FindByPath({"root": root, "path": violation.state["path"]})
        if find_result[0] == 0 or find_result[1] is None:
            return (1, None, None)
        node = find_result[1]
        old_name = node.state["name"]
        if not old_name:
            return (1, None, None)
        if old_name[0].islower() and old_name not in LOWERCASE_EXEMPT:
            new_name = old_name[0].upper() + old_name[1:]
            node.state["name"] = new_name
            action = FixAction(param={"rule_id": 24, "path": violation.state["path"], "action": "capitalize_name", "old_value": old_name, "new_value": new_name})
            return (1, action, None)
        return (1, None, None)

    def FixWeight(self, params):
        root = self._p(params, "root")
        violation = self._p(params, "violation")
        if root is None or violation is None:
            return (0, None, ("MISSING_PARAM", "root and violation required", 0))
        find_result = self.FindByPath({"root": root, "path": violation.state["path"]})
        if find_result[0] == 0 or find_result[1] is None:
            return (1, None, None)
        node = find_result[1]
        old_values = []
        new_values = []
        fixed = False
        for t in node.state["tuples"]:
            if not t:
                continue
            last = t[-1]
            if isinstance(last, float):
                old_values.append(last)
                t[-1] = int(last)
                new_values.append(t[-1])
                fixed = True
            elif isinstance(last, int):
                if last < WEIGHT_MIN:
                    old_values.append(last)
                    t[-1] = WEIGHT_MIN
                    new_values.append(WEIGHT_MIN)
                    fixed = True
                elif last > WEIGHT_MAX:
                    old_values.append(last)
                    t[-1] = WEIGHT_MAX
                    new_values.append(WEIGHT_MAX)
                    fixed = True
        if fixed:
            action = FixAction(param={"rule_id": 999, "path": violation.state["path"], "action": "fix_weight", "old_value": old_values, "new_value": new_values})
            return (1, action, None)
        return (1, None, None)

    def FindByPath(self, params):
        root = self._p(params, "root")
        path = self._p(params, "path")
        if root is None or path is None:
            return (0, None, ("MISSING_PARAM", "root and path required", 0))
        if path == "/root" or not path:
            return (1, root, None)
        parts = path.strip("/").split("/")
        if not parts or parts == ["root"]:
            return (1, root, None)
        if parts[0] == "root":
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

    def CleanupEmpty(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        actions = []
        self.CleanupNode(root, actions)
        self.VerifyConnectivity(root, None, actions)
        action_dicts = []
        for a in actions:
            td = a.ToDict({})
            if td[0] == 1:
                action_dicts.append(td[1])
        return (1, {"actions": action_dicts,
                    "action_count": len(action_dicts)}, None)

    def CleanupNode(self, node, actions):
        removed = []
        for i, child in enumerate(node.state["children"]):
            if not child.state["name"] and not child.state["tuples"] and not child.state["children"]:
                removed.append(i)
        for i in reversed(removed):
            node.state["children"].pop(i)
            path_result = node.Run("path", {})
            path_str = path_result[1] if path_result[0] == 1 else ""
            actions.append(FixAction(param={"rule_id": 0, "path": path_str, "action": "remove_empty", "old_value": None, "new_value": None}))
        for child in node.state["children"]:
            self.CleanupNode(child, actions)
        return (1, True, None)

    def VerifyConnectivity(self, node, parent, actions):
        if node is not self.state.get("cleanup_root", node):
            if node.state["parent"] is not parent:
                node.state["parent"] = parent
                path_result = node.Run("path", {})
                path_str = path_result[1] if path_result[0] == 1 else ""
                actions.append(FixAction(param={"rule_id": 0, "path": path_str, "action": "relink_orphan", "old_value": "stale_parent", "new_value": parent.state["name"] if parent else "root"}))
            if parent and node not in parent.state["children"]:
                parent.state["children"].append(node)
                path_result = node.Run("path", {})
                path_str = path_result[1] if path_result[0] == 1 else ""
                actions.append(FixAction(param={"rule_id": 0, "path": path_str, "action": "reattach_orphan", "old_value": None, "new_value": parent.state["name"] if parent else "root"}))
        for child in node.state["children"]:
            self.VerifyConnectivity(child, node, actions)
        return (1, True, None)
