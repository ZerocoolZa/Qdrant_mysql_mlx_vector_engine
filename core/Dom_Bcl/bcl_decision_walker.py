#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Bcl/bcl_decision_walker.py"
# date="2026-06-28" author="Devin" session_id="bcl-review-fixes"
# context="BCL Decision Tree Walker — executes Pass/Fail/Unsure traversal with placeholder substitution"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state"}
# [@FILEID]{id="bcl_decision_walker.py" domain="BCL" authority="BCLDecisionWalker"}
# [@SUMMARY]{summary="Walks a BCL decision tree: finds rule_id, calls check functions, descends Pass/Fail/Unsure, emits fix SQL with placeholder substitution."}
# [@CLASS]{class="BCLDecisionWalker" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="walk" type="command"}
# [@METHOD]{method="walk_rule" type="command"}
# [@METHOD]{method="walk_check" type="command"}
# [@METHOD]{method="read_branch" type="command"}
# [@METHOD]{method="substitute" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from bcl_parser import BCLNode

PASS = "Pass"
FAIL = "Fail"
UNSURE = "Unsure"
WAIT = "Wait"


class BCLDecisionWalker:
    """Walks a BCL decision tree and emits fix SQL.

    Given a parsed BCL root, a rule_id, a dict of check functions
    (name -> callable(schema_meta) -> "Pass"/"Fail"/"Unsure"), and
    schema metadata, produces (fix_sql, weight, status).
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "last_result": None,
            "memunit": mem,
            "db_manager": db,
            "strict_checks": False,
        }
        if param:
            for key, value in param.items():
                self.state[key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "walk":
            return self.Walk(params)
        elif command == "walk_rule":
            return self.WalkRule(params)
        elif command == "walk_check":
            return self.WalkCheck(params)
        elif command == "read_branch":
            return self.ReadBranch(params)
        elif command == "substitute":
            return self.Substitute(params)
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

    def Walk(self, params):
        root = self._p(params, "root")
        rule_id = self._p(params, "rule_id")
        check_functions = self._p(params, "check_functions", {})
        schema_meta = self._p(params, "schema_meta", {})
        strict = self._p(params, "strict_checks", self.state.get("strict_checks", False))
        if root is None or rule_id is None:
            return (0, None, ("MISSING_PARAM", "root and rule_id required", 0))
        rule_node = self.FindRuleNode(root, rule_id)
        if rule_node is None:
            return (0, None, ("RULE_NOT_FOUND", "No container [@%s]" % rule_id, 0))
        result = self.WalkRule({"rule_node": rule_node, "check_functions": check_functions, "schema_meta": schema_meta, "strict_checks": strict})
        self.state["last_result"] = result[1] if result[0] == 1 else None
        return result

    def FindRuleNode(self, root, rule_id):
        stack = [root]
        while stack:
            node = stack.pop()
            if node.state["name"] == rule_id:
                return node
            for child in node.state["children"]:
                stack.append(child)
        return None

    def WalkRule(self, params):
        rule_node = self._p(params, "rule_node")
        check_functions = self._p(params, "check_functions", {})
        schema_meta = self._p(params, "schema_meta", {})
        strict = self._p(params, "strict_checks", False)
        if rule_node is None:
            return (0, None, ("MISSING_PARAM", "rule_node required", 0))
        for child in rule_node.state["children"]:
            cname = child.state["name"]
            if cname in (PASS, FAIL, UNSURE, WAIT):
                continue
            result = self.WalkCheck({"check_node": child, "check_functions": check_functions, "schema_meta": schema_meta, "strict_checks": strict})
            if result[0] == 0:
                return result
            if result[0] == 1 and result[1] is not None:
                return result
        branch_result = self.ReadBranch({"node": rule_node, "branch": FAIL, "schema_meta": schema_meta})
        if branch_result[0] == 1 and branch_result[1] is not None:
            return (1, branch_result[1], None)
        return (1, None, None)

    def WalkCheck(self, params):
        check_node = self._p(params, "check_node")
        check_functions = self._p(params, "check_functions", {})
        schema_meta = self._p(params, "schema_meta", {})
        strict = self._p(params, "strict_checks", False)
        if check_node is None:
            return (0, None, ("MISSING_PARAM", "check_node required", 0))
        check_name = check_node.state["name"]
        check_fn = check_functions.get(check_name)
        if check_fn is None:
            if strict:
                path_result = check_node.Run("path", {})
                path_str = path_result[1] if path_result[0] == 1 else ""
                return (0, None, ("CHECK_NOT_FOUND", "No check function registered for [@%s] at %s" % (check_name, path_str), 0))
            return (1, None, None)
        try:
            outcome = check_fn(schema_meta)
        except Exception:
            outcome = UNSURE
        if outcome == PASS:
            return self.ReadBranch({"node": check_node, "branch": PASS, "schema_meta": schema_meta})
        if outcome == UNSURE:
            unsure_result = self.ReadBranch({"node": check_node, "branch": UNSURE, "schema_meta": schema_meta})
            if unsure_result[0] == 1 and unsure_result[1] is not None:
                return unsure_result
            return self.ReadBranch({"node": check_node, "branch": FAIL, "schema_meta": schema_meta})
        fail_child = None
        for child in check_node.state["children"]:
            if child.state["name"] == FAIL:
                fail_child = child
                break
        if fail_child is None:
            return (1, None, None)
        nested_checks = [c for c in fail_child.state["children"] if c.state["name"] not in (PASS, FAIL, UNSURE, WAIT)]
        if nested_checks:
            for grandchild in nested_checks:
                sub = self.WalkCheck({"check_node": grandchild, "check_functions": check_functions, "schema_meta": schema_meta, "strict_checks": strict})
                if sub[0] == 0:
                    return sub
                if sub[0] == 1 and sub[1] is not None:
                    return sub
            return (1, None, None)
        return self.ReadBranch({"node": check_node, "branch": FAIL, "schema_meta": schema_meta})

    def ReadBranch(self, params):
        node = self._p(params, "node")
        branch = self._p(params, "branch")
        schema_meta = self._p(params, "schema_meta", {})
        if node is None or branch is None:
            return (0, None, ("MISSING_PARAM", "node and branch required", 0))
        for child in node.state["children"]:
            if child.state["name"] == branch:
                if child.state["tuples"]:
                    t = child.state["tuples"][0]
                    if t:
                        fix_raw = t[0] if isinstance(t[0], str) else str(t[0])
                        weight = t[-1] if isinstance(t[-1], (int, float)) else None
                        fix_sql = self.Substitute({"text": fix_raw, "schema_meta": schema_meta})[1]
                        return (1, {"fix_sql": fix_sql, "weight": weight, "status": branch}, None)
                return (1, None, None)
        return (1, None, None)

    def Substitute(self, params):
        text = self._p(params, "text", "")
        schema_meta = self._p(params, "schema_meta", {})
        if not isinstance(text, str):
            text = str(text)
        result = text
        for key, value in schema_meta.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return (1, result, None)
