#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_schema.py"
# date="2026-06-27" author="Cascade" session_id="bcl-missing-classes"
# context="BCL Schema — declarative validation schema, replaces hardcoded rules in bcl_config and bcl_validator"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_schema.py" domain="BCL" authority="BCLSchema"}
# [@SUMMARY]{summary="BCL Schema: declarative rule definitions for BCL containers. Each rule has id, name, severity, predicate, description. Loaded by BCLValidator."}
# [@CLASS]{class="BCLSchema" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="add_rule" type="command"}
# [@METHOD]{method="get_rules" type="command"}
# [@METHOD]{method="check_node" type="command"}
# [@METHOD]{method="load_defaults" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from bcl_config import WEIGHT_MIN, WEIGHT_MAX, BRANCH_TOKENS, OPTIONAL_BRANCH_TOKENS, VALID_NAME_CHARS


class BCLSchema:
    """Declarative validation schema for BCL containers."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "rules": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "add_rule":
            return self.AddRule(params)
        elif command == "get_rules":
            return self.GetRules(params)
        elif command == "check_node":
            return self.CheckNode(params)
        elif command == "load_defaults":
            return self.LoadDefaults(params)
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

    def AddRule(self, params):
        rule_id = self._p(params, "rule_id")
        rule_name = self._p(params, "rule_name")
        severity = self._p(params, "severity", "high")
        description = self._p(params, "description", "")
        predicate = self._p(params, "predicate")
        if rule_id is None or rule_name is None:
            return (0, None, ("MISSING_PARAM", "rule_id and rule_name required", 0))
        rule = {
            "id": rule_id,
            "name": rule_name,
            "severity": severity,
            "description": description,
            "predicate": predicate,
        }
        self.state["rules"].append(rule)
        return (1, rule, None)

    def GetRules(self, params=None):
        return (1, {"rules": self.state["rules"], "count": len(self.state["rules"])}, None)

    def CheckNode(self, params):
        node = self._p(params, "node")
        if node is None:
            return (0, None, ("MISSING_PARAM", "node required", 0))
        violations = []
        for rule in self.state["rules"]:
            predicate = rule.get("predicate")
            if predicate is None:
                continue
            try:
                result = predicate(node)
                if result:
                    path_result = node.Run("path", {})
                    path_str = path_result[1] if path_result[0] == 1 else ""
                    violations.append({
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "severity": rule["severity"],
                        "path": path_str,
                        "message": rule["description"],
                    })
            except Exception:
                pass
        return (1, {"violations": violations, "count": len(violations), "ok": len(violations) == 0}, None)

    def LoadDefaults(self, params=None):
        self.state["rules"] = []
        self.AddRule({"rule_id": 24, "rule_name": "bracket_format", "severity": "high",
                       "description": "Container name must start with capital letter",
                       "predicate": lambda n: n.state["name"] and not n.state["name"][0].isupper()})
        self.AddRule({"rule_id": 25, "rule_name": "invalid_chars", "severity": "high",
                       "description": "Container name has invalid characters",
                       "predicate": lambda n: n.state["name"] and any(ch not in VALID_NAME_CHARS for ch in n.state["name"])})
        self.AddRule({"rule_id": 10, "rule_name": "container_uniqueness", "severity": "high",
                       "description": "Duplicate sibling container names",
                       "predicate": lambda n: len(set(c.state["name"] for c in n.state["children"])) < len(n.state["children"])})
        self.AddRule({"rule_id": 11, "rule_name": "branch_pair", "severity": "high",
                       "description": "Pass without Fail or vice versa",
                       "predicate": lambda n: self.HasIncompleteBranch(n)})
        self.AddRule({"rule_id": 999, "rule_name": "weight_position", "severity": "high",
                       "description": "Weight out of range or wrong type",
                       "predicate": lambda n: self.HasWeightViolation(n)})
        self.AddRule({"rule_id": 0, "rule_name": "empty_container", "severity": "low",
                       "description": "Container has no tuples and no children",
                       "predicate": lambda n: not n.state["tuples"] and not n.state["children"] and n.state["name"] != "root"})
        return (1, {"loaded": len(self.state["rules"])}, None)

    def HasIncompleteBranch(self, node):
        child_names = set(c.state["name"] for c in node.state["children"])
        has_pass = "Pass" in child_names
        has_fail = "Fail" in child_names
        return (has_pass and not has_fail) or (has_fail and not has_pass)

    def HasWeightViolation(self, node):
        for t in node.state["tuples"]:
            if not t:
                continue
            last = t[-1]
            if isinstance(last, float):
                return True
            if isinstance(last, int):
                if last < WEIGHT_MIN or last > WEIGHT_MAX:
                    return True
        return False
