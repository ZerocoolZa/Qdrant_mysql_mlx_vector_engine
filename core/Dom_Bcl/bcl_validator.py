#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_validator.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="Stage 3: BCL Validator — AST in, violations out, read-only"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_validator.py" domain="BCL" authority="BCLValidator"}
# [@SUMMARY]{summary="BCL Validator: inspects AST, produces violations. Never mutates AST. Rules: container uniqueness, branch pairs, circular refs, bracket format, weight position."}
# [@CLASS]{class="BCLValidator" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="validate" type="command"}
# [@METHOD]{method="validate_text" type="command"}
# [@METHOD]{method="check_container_name" type="command"}
# [@METHOD]{method="check_weights" type="command"}
# [@METHOD]{method="check_duplicate_siblings" type="command"}
# [@METHOD]{method="check_branch_pairs" type="command"}
# [@METHOD]{method="check_circular_ref" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from bcl_parser import BCLNode
from bcl_lexer import BCLTokenizer, CONTAINER_OPEN, BAREWORD

BRANCH_TOKENS = ["Pass", "Fail"]
OPTIONAL_BRANCH_TOKENS = ["Unsure", "Wait"]
MAX_DEPTH = 256
WEIGHT_MIN = 0
WEIGHT_MAX = 100

VALID_NAME_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")

LOWERCASE_EXEMPT = {
    "schemalint", "meta", "severities", "engines", "thresholds", "score_weights",
    "patterns", "types", "reserved_words", "domains", "structural_rules",
    "design_rules", "auto_fixable", "decision_trees",
    "must_have_pk", "pk_must_not_be_nullable", "no_column_spread", "no_fk_cycles",
    "fk_must_have_id_suffix", "no_bad_column_names", "no_spaces_in_names",
    "no_string_null_default", "no_column_prefix_match_table", "no_duplicate_indexes",
    "no_redundant_indexes", "fk_must_have_index", "no_bool_wrong_type",
    "no_timestamp_naming", "no_autoincr_non_integer", "must_enforce_fk",
    "no_reserved_words", "sqlite_no_sqlite_prefix",
    "is_audit_column", "same_name_diff_meaning", "same_name_same_meaning",
    "has_single_unique_non_null_column", "has_composite_unique",
    "cycle_has_two_tables", "cycle_has_three_or_more", "cycle_is_intentional",
    "column_type_consistent", "fk_type_must_match", "no_all_nullable",
    "no_col_prefix_match_table", "no_composite_pk", "no_csv_in_text",
    "no_empty_tables", "no_fk_missing_ref_col", "no_fk_self_reference",
    "no_incrementing_columns", "no_index_too_many_cols", "no_mixed_naming_case",
    "no_nullable_in_unique", "no_orphaned_fk", "no_over_indexed",
    "no_single_column_tables", "no_table_without_indexes", "no_wide_table",
    "no_without_rowid_no_pk", "pk_must_be_first",
}


class Violation:
    """One rule violation produced by validator."""

    def __init__(self, rule_id=None, rule_name=None, severity=None, path=None, message=None, mem=None, db=None, param=None):
        self.state = {
            "rule_id": rule_id if rule_id is not None else 0,
            "rule_name": rule_name or "",
            "severity": severity or "",
            "path": path or "",
            "message": message or "",
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

    def ToDict(self, params=None):
        return (1, dict(self.state), None)


class ValidationReport:
    """Output of validation: status plus violations list."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "status": "PASS",
            "violations": [],
            "warnings": [],
        }
        if param:
            for key, value in param.items():
                self.state[key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "add":
            return self.Add(params)
        elif command == "is_ok":
            return self.IsOk(params)
        elif command == "summary":
            return self.Summary(params)
        elif command == "to_dict":
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

    def Add(self, params):
        violation = self._p(params, "violation")
        if violation is None:
            return (0, None, ("MISSING_PARAM", "violation required", 0))
        if violation.state["severity"] == "low":
            self.state["warnings"].append(violation)
            if self.state["status"] == "PASS":
                self.state["status"] = "WARN"
        else:
            self.state["violations"].append(violation)
            self.state["status"] = "FAIL"
        return (1, True, None)

    def IsOk(self, params=None):
        return (1, self.state["status"] == "PASS", None)

    def Summary(self, params=None):
        lines = ["Status: " + self.state["status"]]
        if self.state["violations"]:
            lines.append("Violations: " + str(len(self.state["violations"])))
            for v in self.state["violations"]:
                lines.append("  [rule %d] %s: %s" % (v.state["rule_id"], v.state["path"], v.state["message"]))
        if self.state["warnings"]:
            lines.append("Warnings: " + str(len(self.state["warnings"])))
            for w in self.state["warnings"]:
                lines.append("  [rule %d] %s: %s" % (w.state["rule_id"], w.state["path"], w.state["message"]))
        if not self.state["violations"] and not self.state["warnings"]:
            lines.append("All rules passed.")
        return (1, "\n".join(lines), None)

    def ToDict(self, params=None):
        v_dicts = []
        for v in self.state["violations"]:
            td = v.ToDict({})
            if td[0] == 1:
                v_dicts.append(td[1])
        w_dicts = []
        for w in self.state["warnings"]:
            td = w.ToDict({})
            if td[0] == 1:
                w_dicts.append(td[1])
        ok_result = self.IsOk({})
        ok_val = ok_result[1] if ok_result[0] == 1 else False
        return (1, {
            "status": self.state["status"],
            "violations": v_dicts,
            "warnings": w_dicts,
            "ok": ok_val,
        }, None)


class BCLValidator:
    """Check layer: inspects AST, produces ValidationReport. NEVER modifies AST."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "report": None,
            "errors": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "validate":
            return self.Validate(params)
        elif command == "validate_text":
            return self.ValidateText(params)
        elif command == "check_container_name":
            return self.CheckContainerName(params)
        elif command == "check_weights":
            return self.CheckWeights(params)
        elif command == "check_duplicate_siblings":
            return self.CheckDuplicateSiblings(params)
        elif command == "check_branch_pairs":
            return self.CheckBranchPairs(params)
        elif command == "check_circular_ref":
            return self.CheckCircularRef(params)
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

    def Validate(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        report = ValidationReport()
        for child in root.state["children"]:
            self.ValidateNode(child, report, [child.state["name"]], 1)
        self.state["report"] = report
        return (1, report.ToDict(), None)

    def ValidateNode(self, node, report, path_stack, depth):
        if depth > MAX_DEPTH:
            path_result = node.Run("path", {})
            path_str = path_result[1] if path_result[0] == 1 else ""
            report.Run("add", {"violation": Violation(0, "depth_limit", "high", path_str,
                                 "Depth %d exceeds limit %d" % (depth, MAX_DEPTH))})
            return (1, True, None)
        self.CheckContainerName({"node": node, "report": report})
        self.CheckWeights({"node": node, "report": report})
        self.CheckDuplicateSiblings({"node": node, "report": report})
        self.CheckBranchPairs({"node": node, "report": report})
        self.CheckCircularRef({"node": node, "report": report, "path_stack": path_stack})
        for child in node.state["children"]:
            self.ValidateNode(child, report, path_stack + [child.state["name"]], depth + 1)
        return (1, True, None)

    def ValidateText(self, params):
        text = self._p(params, "text")
        if text is None:
            return (0, None, ("MISSING_PARAM", "text required", 0))
        errors = []
        stack = []
        pairs = {"{": "}", "[": "]", "(": ")"}
        openers = set(pairs.keys())
        closers = set(pairs.values())
        for i, ch in enumerate(text):
            if ch in openers:
                stack.append((ch, i))
            elif ch in closers:
                if not stack:
                    errors.append("Unmatched %s at position %d" % (ch, i))
                    continue
                last_open, pos = stack.pop()
                if pairs[last_open] != ch:
                    errors.append("Mismatched bracket: %s at %d vs %s at %d" % (last_open, pos, ch, i))
        if stack:
            for ch, pos in stack:
                errors.append("Unclosed %s at position %d" % (ch, pos))
        return (1, {"errors": errors, "count": len(errors), "ok": len(errors) == 0}, None)

    def CheckContainerName(self, params):
        node = self._p(params, "node")
        report = self._p(params, "report")
        if node is None or report is None:
            return (0, None, ("MISSING_PARAM", "node and report required", 0))
        name = node.state["name"]
        if not name:
            path_result = node.Run("path", {})
            path_str = path_result[1] if path_result[0] == 1 else ""
            report.Run("add", {"violation": Violation(24, "bracket_format", "high", path_str,
                                 "Container name is empty")})
            return (1, True, None)
        if not name[0].isupper() and name not in LOWERCASE_EXEMPT:
            path_result = node.Run("path", {})
            path_str = path_result[1] if path_result[0] == 1 else ""
            report.Run("add", {"violation": Violation(24, "bracket_format", "high", path_str,
                                 "Container name %s must start with capital letter" % name)})
            return (1, True, None)
        for ch in name:
            if ch not in VALID_NAME_CHARS:
                path_result = node.Run("path", {})
                path_str = path_result[1] if path_result[0] == 1 else ""
                report.Run("add", {"violation": Violation(24, "bracket_format", "high", path_str,
                                     "Container name %s has invalid character %s" % (name, ch))})
                return (1, True, None)
        return (1, True, None)

    def CheckWeights(self, params):
        node = self._p(params, "node")
        report = self._p(params, "report")
        if node is None or report is None:
            return (0, None, ("MISSING_PARAM", "node and report required", 0))
        for i, t in enumerate(node.state["tuples"]):
            if not t:
                continue
            last = t[-1]
            if isinstance(last, float):
                path_result = node.Run("path", {})
                path_str = path_result[1] if path_result[0] == 1 else ""
                report.Run("add", {"violation": Violation(999, "weight_position", "high", path_str,
                                     "Tuple %d: weight must be integer got float %s" % (i, last))})
            elif isinstance(last, int):
                if last < WEIGHT_MIN or last > WEIGHT_MAX:
                    path_result = node.Run("path", {})
                    path_str = path_result[1] if path_result[0] == 1 else ""
                    report.Run("add", {"violation": Violation(999, "weight_position", "high", path_str,
                                         "Tuple %d: weight %d out of range (%d-%d)" % (i, last, WEIGHT_MIN, WEIGHT_MAX))})
            elif isinstance(last, str) and len(t) >= 3:
                stripped = last.strip()
                if stripped.lstrip("-").isdigit():
                    path_result = node.Run("path", {})
                    path_str = path_result[1] if path_result[0] == 1 else ""
                    report.Run("add", {"violation": Violation(999, "weight_position", "high", path_str,
                                         "Tuple %d: weight must be integer got string '%s'" % (i, last))})
                else:
                    try:
                        float(stripped)
                        path_result = node.Run("path", {})
                        path_str = path_result[1] if path_result[0] == 1 else ""
                        report.Run("add", {"violation": Violation(999, "weight_position", "high", path_str,
                                         "Tuple %d: weight must be integer got string '%s'" % (i, last))})
                    except ValueError:
                        pass
        return (1, True, None)

    def CheckDuplicateSiblings(self, params):
        node = self._p(params, "node")
        report = self._p(params, "report")
        if node is None or report is None:
            return (0, None, ("MISSING_PARAM", "node and report required", 0))
        seen = {}
        for child in node.state["children"]:
            if child.state["name"] in seen:
                child_path = child.Run("path", {})
                child_path_str = child_path[1] if child_path[0] == 1 else ""
                report.Run("add", {"violation": Violation(10, "container_uniqueness", "high", child_path_str,
                                     "Duplicate container [@%s] under [@%s]" % (child.state["name"], node.state["name"]))})
            else:
                seen[child.state["name"]] = True
        return (1, True, None)

    def CheckBranchPairs(self, params):
        node = self._p(params, "node")
        report = self._p(params, "report")
        if node is None or report is None:
            return (0, None, ("MISSING_PARAM", "node and report required", 0))
        child_names = set(child.state["name"] for child in node.state["children"])
        has_pass = "Pass" in child_names
        has_fail = "Fail" in child_names
        if has_pass and not has_fail:
            path_result = node.Run("path", {})
            path_str = path_result[1] if path_result[0] == 1 else ""
            report.Run("add", {"violation": Violation(11, "branch_pair", "high", path_str,
                                 "Container [@%s] has [@Pass] but missing [@Fail]" % node.state["name"])})
        elif has_fail and not has_pass:
            path_result = node.Run("path", {})
            path_str = path_result[1] if path_result[0] == 1 else ""
            report.Run("add", {"violation": Violation(11, "branch_pair", "high", path_str,
                                 "Container [@%s] has [@Fail] but missing [@Pass]" % node.state["name"])})
        return (1, True, None)

    def CheckCircularRef(self, params):
        node = self._p(params, "node")
        report = self._p(params, "report")
        path_stack = self._p(params, "path_stack")
        if node is None or report is None or path_stack is None:
            return (0, None, ("MISSING_PARAM", "node report path_stack required", 0))
        if len(path_stack) < 2:
            return (1, True, None)
        current_name = path_stack[-1]
        if current_name in BRANCH_TOKENS or current_name in OPTIONAL_BRANCH_TOKENS:
            return (1, True, None)
        if current_name in path_stack[:-1]:
            path_result = node.Run("path", {})
            path_str = path_result[1] if path_result[0] == 1 else ""
            report.Run("add", {"violation": Violation(12, "no_circular_refs", "high", path_str,
                                 "Circular reference: [@%s] repeats along path %s" % (current_name, "/".join(path_stack)))})

        return (1, True, None)


class IRValidator:
    """Validate IR consistency post-compilation."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "issues": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "validate_ir":
            return self.ValidateIr(params)
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

    def ValidateIr(self, params):
        results = self._p(params, "results")
        if results is None:
            return (0, None, ("MISSING_PARAM", "results required", 0))
        issues = []
        all_ids = set()
        all_parents = set()
        node_count = 0
        end_count = 0
        lexer = BCLTokenizer()
        for r in results:
            if "error" in r:
                continue
            bcl_text = r.get("bcl", "")
            lex_result = lexer.Run("tokenize", {"text": bcl_text})
            if lex_result[0] == 0:
                issues.append("LEX ERROR in %s: %s" % (r.get("filepath", "?"), lex_result[2]))
                continue
            tokens = lex_result[1]["tokens"]
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok["type"] == CONTAINER_OPEN and tok["value"] == "IRNODE":
                    node_count += 1
                    node_id = ""
                    parent_id = ""
                    j = i + 1
                    while j < len(tokens) and tokens[j]["type"] == BAREWORD:
                        bw = tokens[j]["value"]
                        if bw.startswith("id="):
                            node_id = bw[3:]
                        elif bw.startswith("parent="):
                            parent_id = bw[7:]
                        j += 1
                    if node_id in all_ids and node_id:
                        issues.append("DUPLICATE ID: %s in %s" % (node_id, r.get("filepath", "?")))
                    if node_id:
                        all_ids.add(node_id)
                    if parent_id:
                        all_parents.add(parent_id)
                    i = j
                elif tok["type"] == CONTAINER_OPEN and tok["value"] == "ENDNODE":
                    end_count += 1
                    i += 1
                else:
                    i += 1
        orphan_parents = all_parents - all_ids
        if orphan_parents:
            issues.append("ORPHAN PARENT REFS: %d parent IDs not found as nodes" % len(orphan_parents))
        if end_count != node_count:
            issues.append("MISMATCH: %d IRNODE tags but %d ENDNODE tags" % (node_count, end_count))
        self.state["issues"] = issues
        return (1, {"issues": issues, "count": len(issues), "ok": len(issues) == 0}, None)
