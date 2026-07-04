#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_engine.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="Stage 5: BCL Engine — orchestrator for full pipeline LEX PARSE VALIDATE FIX SERIALIZE"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_engine.py" domain="BCL" authority="BCLEngine"}
# [@SUMMARY]{summary="BCL Engine: orchestrates lexer parser validator fixer serializer. Strict FSM, convergence loop, CRUD with clone-test-commit."}
# [@CLASS]{class="BCLEngine" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="run_pipeline" type="command"}
# [@METHOD]{method="load_file" type="command"}
# [@METHOD]{method="save_file" type="command"}
# [@METHOD]{method="create" type="command"}
# [@METHOD]{method="update" type="command"}
# [@METHOD]{method="delete" type="command"}
# [@METHOD]{method="read" type="command"}
# [@METHOD]{method="list_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import hashlib

from bcl_lexer import BCLTokenizer
from bcl_parser import BCLParser, BCLNode
from bcl_validator import BCLValidator
from bcl_fixer import BCLFixer

from bcl_config import STAGES, MAX_FIX_CYCLES, ALLOWED_TRANSITIONS


class BCLEngine:
    """Orchestrator: runs the full BCL pipeline with strict FSM enforcement."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"auto_fix": True},
            "result": None,
            "allowed_next": {"LEX"},
            "memunit": mem,
            "db_manager": db,
        }
        self.validator = BCLValidator()
        self.fixer = BCLFixer()
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "run_pipeline":
            return self.RunPipeline(params)
        elif command == "load_file":
            return self.LoadFile(params)
        elif command == "save_file":
            return self.SaveFile(params)
        elif command == "create":
            return self.Create(params)
        elif command == "update":
            return self.Update(params)
        elif command == "delete":
            return self.Delete(params)
        elif command == "read":
            return self.Read(params)
        elif command == "list_all":
            return self.ListAll(params)
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

    def CloneAst(self, node):
        new_node = BCLNode(node.state["name"])
        new_node.state["tuples"] = [list(t) for t in node.state["tuples"]]
        for child in node.state["children"]:
            new_child = self.CloneAst(child)
            new_child.state["parent"] = new_node
            new_node.state["children"].append(new_child)
        return (1, new_node, None)

    def AstHash(self, node):
        if node is None:
            return (1, "0" * 32, None)
        def Walk(n):
            out = [n.state["name"], str(n.state["tuples"])]
            for c in n.state["children"]:
                out.append(Walk(c))
            return "|".join(out)
        return (1, hashlib.md5(Walk(node).encode()).hexdigest(), None)

    def EnterStage(self, stage_name, stages_run):
        allowed = self.state["allowed_next"]
        if stage_name not in allowed:
            return (0, None, ("STAGE_VIOLATION",
                              "Expected %s got %s" % (sorted(allowed), stage_name), 0))
        stages_run.append(stage_name)
        self.state["allowed_next"] = ALLOWED_TRANSITIONS[stage_name]
        return (1, True, None)

    def Serialize(self, root):
        lines = []
        for child in root.state["children"]:
            bcl_result = child.ToBcl({"indent": 0})
            if bcl_result[0] == 1:
                lines.append(bcl_result[1])
        return (1, "\n".join(lines), None)

    def FindByName(self, root, name):
        if root.state["name"] == name:
            return (1, root, None)
        for child in root.state["children"]:
            result = self.FindByName(child, name)
            if result[0] == 1 and result[1] is not None:
                return result
        return (1, None, None)

    def CountNodes(self, node):
        if node is None:
            return (1, 0, None)
        count = 1
        for child in node.state["children"]:
            count_result = self.CountNodes(child)
            count += count_result[1]
        return (1, count, None)

    def RunPipeline(self, params):
        text = self._p(params, "text")
        if text is None:
            return (0, None, ("MISSING_PARAM", "text required", 0))
        self.state["allowed_next"] = {"LEX"}
        stages_run = []
        errors = []
        tokens = []
        ast_root = None
        report_dict = None
        fixes = []
        fixed = False
        status = "PASS"
        auto_fix = self.state["config"].get("auto_fix", True)

        enter_result = self.EnterStage("LEX", stages_run)
        if enter_result[0] == 0:
            return enter_result
        tokenizer = BCLTokenizer()
        tok_result = tokenizer.Run("tokenize", {"text": text})
        if tok_result[0] == 0:
            return (0, None, ("LEXER_ERROR", str(tok_result[2]), 0))
        tokens = tok_result[1]["tokens"]

        enter_result = self.EnterStage("PARSE", stages_run)
        if enter_result[0] == 0:
            return enter_result
        parser = BCLParser()
        parse_result = parser.Run("parse", {"tokens": tokens})
        if parse_result[0] == 0:
            return (0, None, ("PARSER_ERROR", str(parse_result[2]), 0))
        ast_root = parse_result[1]["root"]

        cycle = 0
        prev_hash = None
        while cycle <= MAX_FIX_CYCLES:
            enter_result = self.EnterStage("VALIDATE", stages_run)
            if enter_result[0] == 0:
                return enter_result
            val_result = self.validator.Run("validate", {"root": ast_root})
            if val_result[0] == 0:
                return val_result
            report_dict = val_result[1]
            violation_count = len(report_dict["violations"])

            if report_dict["ok"]:
                status = "PASS"
                if fixes:
                    fixed = True
                break

            if not auto_fix or not report_dict["violations"]:
                if not report_dict["violations"] and report_dict["warnings"]:
                    status = "PASS"
                else:
                    status = "FAIL"
                break

            hash_result = self.AstHash(ast_root)
            current_hash = hash_result[1]
            if current_hash == prev_hash:
                status = "FAIL"
                errors.append("Fix convergence stalled: AST stopped changing")
                break
            prev_hash = current_hash

            enter_result = self.EnterStage("FIX", stages_run)
            if enter_result[0] == 0:
                return enter_result
            fix_result = self.fixer.Run("fix", {"root": ast_root, "report": self.BuildReport(report_dict)})
            if fix_result[0] == 0:
                return fix_result
            new_fixes = fix_result[1]["actions"]
            fixes.extend(new_fixes)
            snapshot = fix_result[1]["snapshot"]

            reval_result = self.validator.Run("validate", {"root": ast_root})
            if reval_result[0] == 0:
                return reval_result
            new_violation_count = len(reval_result[1]["violations"])
            if new_violation_count > violation_count and new_fixes:
                restore_result = self.fixer.Run("restore", {"snapshot": snapshot})
                if restore_result[0] == 1:
                    ast_root = restore_result[1]["root"]
                status = "FAIL"
                errors.append("Fix regression: violations increased (%d to %d) reverted" % (violation_count, new_violation_count))
                reval2 = self.validator.Run("validate", {"root": ast_root})
                if reval2[0] == 1:
                    report_dict = reval2[1]
                break
            cycle += 1
        else:
            status = "FAIL"
            errors.append("Fix convergence limit reached (%d cycles)" % MAX_FIX_CYCLES)

        self.state["allowed_next"] = {"SERIALIZE"}
        text_out = None
        text_mode = None
        if ast_root is not None:
            enter_result = self.EnterStage("SERIALIZE", stages_run)
            if enter_result[0] == 0:
                return enter_result
            ser_result = self.Serialize(ast_root)
            text_out = ser_result[1]
            text_mode = "PASS" if status == "PASS" else "DIAGNOSTIC"

        node_count = self.CountNodes(ast_root)[1]
        result = {
            "status": status,
            "fixed": fixed,
            "tokens": tokens,
            "ast": ast_root,
            "report": report_dict,
            "fixes": fixes,
            "text": text_out,
            "text_mode": text_mode,
            "errors": errors,
            "stages_run": stages_run,
            "node_count": node_count,
            "ok": status == "PASS",
        }
        self.state["result"] = result
        return (1, result, None)

    def BuildReport(self, report_dict):
        from bcl_validator import ValidationReport, Violation
        report = ValidationReport()
        for v in report_dict.get("violations", []):
            report.Run("add", {"violation": Violation(v["rule_id"], v["rule_name"], v["severity"], v["path"], v["message"])})
        for w in report_dict.get("warnings", []):
            report.Run("add", {"violation": Violation(w["rule_id"], w["rule_name"], "low", w["path"], w["message"])})
        return (1, report, None)

    def LoadFile(self, params):
        path = self._p(params, "path")
        if path is None:
            return (0, None, ("MISSING_PARAM", "path required", 0))
        try:
            with open(path, "r") as f:
                text = f.read()
        except OSError as exc:
            return (0, None, ("FILE_READ_FAILED", str(exc), 0))
        return self.RunPipeline({"text": text})

    def SaveFile(self, params):
        path = self._p(params, "path")
        result = self._p(params, "result")
        if path is None or result is None:
            return (0, None, ("MISSING_PARAM", "path and result required", 0))
        if result.get("ok") and result.get("text"):
            try:
                with open(path, "w") as f:
                    f.write(result["text"])
            except OSError as exc:
                return (0, None, ("FILE_WRITE_FAILED", str(exc), 0))
            return (1, {"saved": True, "path": path}, None)
        return (1, {"saved": False, "reason": "result not ok or no text"}, None)

    def Create(self, params):
        root = self._p(params, "root")
        parent_name = self._p(params, "parent_name")
        node = self._p(params, "node")
        if root is None or node is None:
            return (0, None, ("MISSING_PARAM", "root and node required", 0))
        clone_result = self.CloneAst(root)
        test_root = clone_result[1]
        if parent_name is None:
            test_parent = test_root
        else:
            find_result = self.FindByName(test_root, parent_name)
            if find_result[1] is None:
                return (0, None, ("PARENT_NOT_FOUND", str(parent_name), 0))
            test_parent = find_result[1]
        test_node_clone = self.CloneAst(node)[1]
        test_parent.state["children"].append(test_node_clone)
        test_node_clone.state["parent"] = test_parent
        val_result = self.validator.Run("validate", {"root": test_root})
        if val_result[0] == 0:
            return val_result
        if not val_result[1]["ok"]:
            return (0, None, ("VALIDATION_FAILED", str([v["message"] for v in val_result[1]["violations"]]), 0))
        if parent_name is None:
            real_parent = root
        else:
            real_parent = self.FindByName(root, parent_name)[1]
        real_parent.state["children"].append(node)
        node.state["parent"] = real_parent
        return (1, {"created": True, "parent": real_parent.state["name"]}, None)

    def Update(self, params):
        root = self._p(params, "root")
        container_name = self._p(params, "container_name")
        key = self._p(params, "key")
        new_value = self._p(params, "new_value")
        if root is None or container_name is None or key is None:
            return (0, None, ("MISSING_PARAM", "root container_name key required", 0))
        clone_result = self.CloneAst(root)
        test_root = clone_result[1]
        find_result = self.FindByName(test_root, container_name)
        if find_result[1] is None:
            return (0, None, ("CONTAINER_NOT_FOUND", str(container_name), 0))
        test_node = find_result[1]
        test_node.Run("set", {"key": key, "value": new_value})
        val_result = self.validator.Run("validate", {"root": test_root})
        if val_result[0] == 0:
            return val_result
        if not val_result[1]["ok"]:
            return (0, None, ("VALIDATION_FAILED", str([v["message"] for v in val_result[1]["violations"]]), 0))
        real_node = self.FindByName(root, container_name)[1]
        real_node.Run("set", {"key": key, "value": new_value})
        return (1, {"updated": True, "container": container_name, "key": key}, None)

    def Delete(self, params):
        root = self._p(params, "root")
        container_name = self._p(params, "container_name")
        if root is None or container_name is None:
            return (0, None, ("MISSING_PARAM", "root and container_name required", 0))
        clone_result = self.CloneAst(root)
        test_root = clone_result[1]
        removed = self.RemoveByName(test_root, container_name)
        if not removed[1]:
            return (0, None, ("CONTAINER_NOT_FOUND", str(container_name), 0))
        self.fixer.Run("cleanup_empty", {"root": test_root})
        val_result = self.validator.Run("validate", {"root": test_root})
        if val_result[0] == 0:
            return val_result
        if not val_result[1]["ok"]:
            return (0, None, ("VALIDATION_FAILED", str([v["message"] for v in val_result[1]["violations"]]), 0))
        self.RemoveByName(root, container_name)
        self.fixer.Run("cleanup_empty", {"root": root})
        return (1, {"deleted": True, "container": container_name}, None)

    def RemoveByName(self, node, name):
        for i, child in enumerate(node.state["children"]):
            if child.state["name"] == name:
                del node.state["children"][i]
                return (1, True, None)
            sub_result = self.RemoveByName(child, name)
            if sub_result[1]:
                return sub_result
        return (1, False, None)

    def Read(self, params):
        root = self._p(params, "root")
        container_name = self._p(params, "container_name")
        if root is None or container_name is None:
            return (0, None, ("MISSING_PARAM", "root and container_name required", 0))
        find_result = self.FindByName(root, container_name)
        if find_result[1] is None:
            return (0, None, ("CONTAINER_NOT_FOUND", str(container_name), 0))
        node = find_result[1]
        path_result = node.Run("path", {})
        path_str = path_result[1] if path_result[0] == 1 else ""
        return (1, {"name": node.state["name"], "path": path_str,
                    "tuples": node.state["tuples"], "children": len(node.state["children"])}, None)

    def ListAll(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        entries = []
        for child in root.state["children"]:
            self.WalkTree(child, entries, 0)
        return (1, {"entries": entries, "count": len(entries)}, None)

    def WalkTree(self, node, entries, depth):
        path_result = node.Run("path", {})
        path_str = path_result[1] if path_result[0] == 1 else ""
        entries.append({"name": node.state["name"], "path": path_str, "depth": depth,
                        "tuples": len(node.state["tuples"]), "children": len(node.state["children"])})
        for child in node.state["children"]:
            self.WalkTree(child, entries, depth + 1)
        return (1, True, None)
