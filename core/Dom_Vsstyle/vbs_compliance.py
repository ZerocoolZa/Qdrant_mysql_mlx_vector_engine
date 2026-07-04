#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_compliance.py>][@domain<Vbs_Code_Verifiation>][@role<validation>][@auth<cascade>][@date<2026-06-26>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<validation>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
Compliance: VBStyle compliance authority.
Check, create, edit, update compliance rules and results.
Full CRUD on rules and per-file/per-class compliance state.
"""

from . import Config_Vbs_Code_Verifiation as Config


class Compliance:
    """VBStyle compliance authority — check, create, edit, update rules and results."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "catalog": [],
            "results": [],
            "rules": {k: d for k, d in Config.VBSTYLE_RULES},
            "file_results": {},
            "class_results": {},
        }

    #[@check_lines]{[@params<<params>][@return<Tuple3>][@purpose<check VBStyle rules on a list of lines>]}
    def check_lines(self, params):
        try:
            lines_list = params.get("lines_list", [])
            full_text = "".join(lines_list)
            comp = {
                "ghost_header": bool(Config.GHOST_RE.search(full_text)),
                "vbstyle_header": bool(Config.VBSTYLE_RE.search(full_text)),
                "tuple3_return": bool(Config.TUPLE3_RE.search(full_text)),
                "state_dict": bool(Config.STATE_DICT_RE.search(full_text)),
                "run_dispatch": bool(Config.RUN_DISPATCH_RE.search(full_text)),
                "no_decorators": not any(Config.DECORATOR_RE.match(l) for l in lines_list),
                "no_print": not any(Config.PRINT_RE.search(l) for l in lines_list if not l.strip().startswith("#")),
                "no_self_underscore": not any(Config.SELF_UNDERSCORE_RE.search(l) for l in lines_list if not l.strip().startswith("#")),
                "no_hardcoded_paths": not any(Config.HARDCODED_PATH_RE.search(l) for l in lines_list if not l.strip().startswith("#")),
            }
            comp["is_compliant"] = all(comp[k] for k in Config.COMPLIANCE_KEYS)
            comp["passed_count"] = sum(comp[k] for k in Config.COMPLIANCE_KEYS)
            comp["total_checks"] = 9
            comp["failed_rules"] = [k for k in Config.COMPLIANCE_KEYS if not comp[k]]
            return (1, comp, None)
        except Exception as e:
            return (0, None, ("CHECK_LINES_ERROR", str(e), 0))

    #[@check]{[@params<<params>][@return<Tuple3>][@purpose<check VBStyle compliance for file and class ranges>]}
    def check(self, params):
        try:
            lines_list = params.get("lines_list", [])
            class_ranges = params.get("class_ranges", None)
            filepath = params.get("filepath", "")

            file_r = self.check_lines({"lines_list": lines_list})
            if not file_r[0]:
                return file_r
            file_comp = file_r[1]

            class_comp = {}
            if class_ranges:
                for access_path, (start, end) in class_ranges.items():
                    class_lines = lines_list[start:end]
                    r = self.check_lines({"lines_list": class_lines})
                    if r[0]:
                        class_comp[access_path] = r[1]

            if filepath:
                self.state["file_results"][filepath] = file_comp
                self.state["class_results"][filepath] = class_comp

            return (1, {"file": file_comp, "classes": class_comp}, None)
        except Exception as e:
            return (0, None, ("CHECK_ERROR", str(e), 0))

    #[@compliance_icon]{[@params<<params>][@return<Tuple3>][@purpose<return checkmark or cross for compliance>]}
    def compliance_icon(self, params):
        try:
            comp = params.get("compliance", {})
            icon = "[VBStyle]" if comp.get("is_compliant", False) else "[NOT VBStyle]"
            return (1, {"icon": icon}, None)
        except Exception as e:
            return (0, None, ("ICON_ERROR", str(e), 0))

    #[@create_rule]{[@params<<params>][@return<Tuple3>][@purpose<create a new compliance rule>]}
    def create_rule(self, params):
        try:
            key = params.get("key", "")
            desc = params.get("desc", "")
            if not key:
                return (0, None, ("MISSING_KEY", "Rule key required", 0))
            if key in self.state["rules"]:
                return (0, None, ("RULE_EXISTS", key, 0))
            self.state["rules"][key] = desc
            return (1, {"created": key}, None)
        except Exception as e:
            return (0, None, ("CREATE_RULE_ERROR", str(e), 0))

    #[@edit_rule]{[@params<<params>][@return<Tuple3>][@purpose<edit an existing compliance rule description>]}
    def edit_rule(self, params):
        try:
            key = params.get("key", "")
            desc = params.get("desc", "")
            if key not in self.state["rules"]:
                return (0, None, ("RULE_NOT_FOUND", key, 0))
            self.state["rules"][key] = desc
            return (1, {"edited": key}, None)
        except Exception as e:
            return (0, None, ("EDIT_RULE_ERROR", str(e), 0))

    #[@update_rule]{[@params<<params>][@return<Tuple3>][@purpose<update an existing compliance rule>]}
    def update_rule(self, params):
        try:
            key = params.get("key", "")
            desc = params.get("desc", "")
            if key not in self.state["rules"]:
                return (0, None, ("RULE_NOT_FOUND", key, 0))
            self.state["rules"][key] = desc
            return (1, {"updated": key}, None)
        except Exception as e:
            return (0, None, ("UPDATE_RULE_ERROR", str(e), 0))

    #[@read_rules]{[@params<<params>][@return<Tuple3>][@purpose<read all compliance rules>]}
    def read_rules(self, params=None):
        return (1, {"rules": self.state["rules"]}, None)

    #[@read_result]{[@params<<params>][@return<Tuple3>][@purpose<read compliance result for a file>]}
    def read_result(self, params):
        try:
            filepath = params.get("filepath", "")
            if filepath in self.state["file_results"]:
                return (1, {
                    "file": self.state["file_results"][filepath],
                    "classes": self.state["class_results"].get(filepath, {}),
                }, None)
            return (0, None, ("NO_RESULT", filepath, 0))
        except Exception as e:
            return (0, None, ("READ_RESULT_ERROR", str(e), 0))

    #[@update_result]{[@params<<params>][@return<Tuple3>][@purpose<update stored compliance result for a file>]}
    def update_result(self, params):
        try:
            filepath = params.get("filepath", "")
            file_comp = params.get("file_comp")
            class_comp = params.get("class_comp")
            if file_comp:
                self.state["file_results"][filepath] = file_comp
            if class_comp:
                self.state["class_results"][filepath] = class_comp
            return (1, {"updated": filepath}, None)
        except Exception as e:
            return (0, None, ("UPDATE_RESULT_ERROR", str(e), 0))

    #[@read_state]{[@params<<params>][@return<Tuple3>][@purpose<read Compliance state>]}
    def read_state(self, params=None):
        return (1, self.state, None)

    #[@set_config]{[@params<<params>][@return<Tuple3>][@purpose<set Compliance config>]}
    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))

    #[@Run]{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch Compliance commands>]}
    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "check": self.check,
            "check_lines": self.check_lines,
            "compliance_icon": self.compliance_icon,
            "create_rule": self.create_rule,
            "edit_rule": self.edit_rule,
            "update_rule": self.update_rule,
            "read_rules": self.read_rules,
            "read_result": self.read_result,
            "update_result": self.update_result,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))
