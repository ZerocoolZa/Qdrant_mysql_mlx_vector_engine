#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_registry.py>][@domain<Vbs_Code_Verifiation>][@role<reporting>][@auth<cascade>][@date<2026-06-26>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<reporting>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
Registry: VBStyle registry authority.
Read, write, edit, update registry entries and output.
Formats parsed domain data into markdown, indexes to MySQL.
"""

import os

from . import Config_Vbs_Code_Verifiation as Config


class Registry:
    """VBStyle registry authority — read, write, edit, update registry output."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "catalog": [],
            "results": [],
            "entries": {},
            "output_path": None,
        }

    #[@format_tree]{[@params<<params>][@return<Tuple3>][@purpose<format class/method tree as aligned text lines with markers>]}
    def format_tree(self, params):
        try:
            domain = params.get("domain", {})
            tree_entries = domain.get("classes", [])
            class_compliance = domain.get("class_compliance", {})
            bcl_headers = domain.get("bcl_headers", {})
            output = []

            for entry in tree_entries:
                entry_type = entry[0]
                level = entry[1]
                name = entry[2]
                access_path = entry[3]
                extra = entry[4] if len(entry) > 4 else None

                prefix = "    " * level

                if entry_type == "class":
                    display = "{}class {}".format(prefix, name)
                    pad = max(2, 50 - len(display))
                    comment = "# {}".format(access_path) if access_path else ""
                    comp = class_compliance.get(access_path)
                    if comp:
                        if comp.get("is_compliant"):
                            marker = " [VBStyle]"
                        else:
                            failed = comp.get("failed_rules", [])
                            marker = " [NOT VBStyle: {}]".format(",".join(failed))
                        comment += marker
                    bcl_info = bcl_headers.get(("class", access_path))
                    if bcl_info:
                        if bcl_info.get("parsed_ok") and bcl_info.get("validation_ok") is not False:
                            comment += " [BCL:OK]"
                        elif bcl_info.get("parsed_ok") and bcl_info.get("validation_ok") is False:
                            violations = len(bcl_info.get("validation_violations", []))
                            comment += " [BCL:FAIL({})]".format(violations)
                        else:
                            comment += " [BCL:PARSE_ERROR]"
                    else:
                        comment += " [BCL:MISSING]"
                    output.append("{}{}{}".format(display, " " * pad, comment))
                else:
                    params_str = extra.get("params", "") if extra else ""
                    purpose = extra.get("purpose", "") if extra else ""
                    return_type = extra.get("return", "") if extra else ""
                    display = "{}def {}({})".format(prefix, name, params_str)
                    pad = max(2, 55 - len(display))
                    parts = []
                    if purpose:
                        parts.append(purpose)
                    if return_type:
                        parts.append("returns: {}".format(return_type))
                    if return_type and "Tuple3" in return_type:
                        parts.append("[Tuple3]")
                    elif extra and extra.get("is_boilerplate") and name == "Run":
                        parts.append("[dispatch]")
                    bcl_info = bcl_headers.get(("method", name))
                    if bcl_info:
                        if bcl_info.get("parsed_ok") and bcl_info.get("validation_ok") is not False:
                            parts.append("[BCL:OK]")
                        elif bcl_info.get("parsed_ok") and bcl_info.get("validation_ok") is False:
                            violations = len(bcl_info.get("validation_violations", []))
                            parts.append("[BCL:FAIL({})]".format(violations))
                        else:
                            parts.append("[BCL:PARSE_ERROR]")
                    else:
                        parts.append("[BCL:MISSING]")
                    comment = " ".join(parts) if parts else ""
                    if comment:
                        output.append("{}{}# {}".format(display, " " * pad, comment))
                    else:
                        output.append(display)

            return (1, {"lines": output}, None)
        except Exception as e:
            return (0, None, ("FORMAT_TREE_ERROR", str(e), 0))

    #[@write]{[@params<<params>][@return<Tuple3>][@purpose<generate full registry markdown from parsed domains and write to file>]}
    def write(self, params):
        try:
            domains = params.get("domains", [])
            output_path = params.get("output_path", Config.DEFAULT_OUTPUT)
            index = params.get("index", None)

            output = []
            output.append("# VBStyle Domain Registry")
            output.append("")
            output.append("Complete class hierarchy with access paths and method details for all {} dom_*.py domain files.".format(len(domains)))
            output.append("")
            output.append("## Summary")
            output.append("")
            output.append("| File | Lines | Root Class | Sub-Authorities | VBStyle | BCL Coverage | BCL Valid |")
            output.append("|------|-------|------------|-----------------|---------|--------------|-----------|")

            for d in domains:
                sub_str = ", ".join(d.get("sub_authorities", [])) if d.get("sub_authorities") else "---"
                comp = d.get("file_compliance", {})
                status = "YES" if comp.get("is_compliant") else "NO"
                cov = d.get("bcl_coverage", {})
                total_items = cov.get("total_classes", 0) + cov.get("total_methods", 0)
                items_with_bcl = cov.get("classes_with_bcl", 0) + cov.get("methods_with_bcl", 0)
                bcl_cov_str = "{}/{}".format(items_with_bcl, total_items)
                bcl_valid_str = "{}/{}".format(cov.get("bcl_valid", 0), items_with_bcl) if items_with_bcl else "---"
                output.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                    d.get("filename", ""), d.get("total_lines", 0),
                    d.get("root_class", ""), sub_str, status, bcl_cov_str, bcl_valid_str))

            output.append("")
            output.append("---")
            output.append("")

            compliant_count = sum(1 for d in domains if d.get("file_compliance", {}).get("is_compliant"))
            non_compliant_count = len(domains) - compliant_count
            output.append("## VBStyle Compliance Overview")
            output.append("")
            output.append("- **Compliant:** {}/{} files".format(compliant_count, len(domains)))
            output.append("- **Non-compliant:** {}/{} files".format(non_compliant_count, len(domains)))
            output.append("")
            output.append("### Rule Breakdown")
            output.append("")
            output.append("| Rule | Description | Pass | Fail |")
            output.append("|------|-------------|------|------|")
            for rule_key, rule_desc in Config.VBSTYLE_RULES:
                pass_count = sum(1 for d in domains if d.get("file_compliance", {}).get(rule_key))
                fail_count = len(domains) - pass_count
                output.append("| {} | {} | {} | {} |".format(rule_key, rule_desc, pass_count, fail_count))
            output.append("")
            output.append("---")
            output.append("")

            total_classes_all = sum(d.get("bcl_coverage", {}).get("total_classes", 0) for d in domains)
            classes_with_bcl_all = sum(d.get("bcl_coverage", {}).get("classes_with_bcl", 0) for d in domains)
            total_methods_all = sum(d.get("bcl_coverage", {}).get("total_methods", 0) for d in domains)
            methods_with_bcl_all = sum(d.get("bcl_coverage", {}).get("methods_with_bcl", 0) for d in domains)
            bcl_valid_all = sum(d.get("bcl_coverage", {}).get("bcl_valid", 0) for d in domains)
            bcl_invalid_all = sum(d.get("bcl_coverage", {}).get("bcl_invalid", 0) for d in domains)
            bcl_val_pass_all = sum(d.get("bcl_coverage", {}).get("bcl_validation_passed", 0) for d in domains)
            bcl_val_fail_all = sum(d.get("bcl_coverage", {}).get("bcl_validation_failed", 0) for d in domains)

            output.append("## BCL Coverage Overview")
            output.append("")
            output.append("- **Classes with BCL headers:** {}/{}".format(classes_with_bcl_all, total_classes_all))
            output.append("- **Methods with BCL headers:** {}/{}".format(methods_with_bcl_all, total_methods_all))
            output.append("- **BCL parsed OK:** {}".format(bcl_valid_all))
            output.append("- **BCL parse errors:** {}".format(bcl_invalid_all))
            output.append("- **BCL validation passed:** {}".format(bcl_val_pass_all))
            output.append("- **BCL validation failed:** {}".format(bcl_val_fail_all))
            output.append("")
            output.append("---")
            output.append("")

            total_classes = 0
            total_methods = 0
            total_lines = 0
            compliant_classes = 0
            non_compliant_classes = 0

            for d in domains:
                fname = d.get("filename", "")
                domain_name = fname.replace("dom_", "").replace(".py", "")
                comp = d.get("file_compliance", {})
                cov = d.get("bcl_coverage", {})
                status = "[VBStyle]" if comp.get("is_compliant") else "[NOT VBStyle]"
                output.append("## {} {}".format(fname, status))
                output.append("**Root:** {} ({}) — {} domain".format(
                    d.get("root_class", ""), d.get("total_lines", 0), domain_name))

                if d.get("sub_authorities"):
                    output.append("**Authorities:** {}".format(", ".join(d["sub_authorities"])))

                output.append("**VBStyle:** {}/{} rules passed".format(
                    comp.get("passed_count", 0), comp.get("total_checks", 9)))
                if comp.get("failed_rules"):
                    output.append("**Failed:** {}".format(", ".join(comp["failed_rules"])))

                total_items = cov.get("total_classes", 0) + cov.get("total_methods", 0)
                items_with_bcl = cov.get("classes_with_bcl", 0) + cov.get("methods_with_bcl", 0)
                output.append("**BCL:** {}/{} headers found, {} parsed OK, {} validation passed".format(
                    items_with_bcl, total_items, cov.get("bcl_valid", 0), cov.get("bcl_validation_passed", 0)))

                for key, info in d.get("bcl_headers", {}).items():
                    if info.get("validation_ok") is False:
                        item_type, item_name = key
                        for v in info.get("validation_violations", []):
                            output.append("  - **BCL violation** on {} `{}`: [rule {}] {}".format(
                                item_type, item_name, v.get("rule_id", ""), v.get("message", "")))
                    elif not info.get("parsed_ok") and info.get("parse_error"):
                        item_type, item_name = key
                        output.append("  - **BCL parse error** on {} `{}`: {}".format(
                            item_type, item_name, info["parse_error"]))

                output.append("")
                output.append("```")

                tree_r = self.format_tree({"domain": d})
                if tree_r[0]:
                    tree_lines = tree_r[1]["lines"]
                    for line in tree_lines:
                        if line.strip().startswith("class "):
                            total_classes += 1
                            if "[VBStyle]" in line:
                                compliant_classes += 1
                            elif "[NOT VBStyle]" in line:
                                non_compliant_classes += 1
                        elif line.strip().startswith("def "):
                            total_methods += 1
                    output.extend(tree_lines)
                output.append("```")
                output.append("")

                total_lines += d.get("total_lines", 0)

                if index:
                    self.index_domain(index, d)

            output.append("---")
            output.append("")
            output.append("*{} domain files, {:,} total lines, {} classes ({} VBStyle, {} not), {} methods*".format(
                len(domains), total_lines, total_classes, compliant_classes, non_compliant_classes, total_methods))
            output.append("*BCL: {}/{} headers, {} parsed OK, {} validation passed*".format(
                classes_with_bcl_all + methods_with_bcl_all,
                total_classes_all + total_methods_all,
                bcl_valid_all, bcl_val_pass_all))

            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(output))

            self.state["output_path"] = output_path
            self.state["entries"]["domains"] = domains

            return (1, {
                "output_path": output_path,
                "domains": len(domains),
                "classes": total_classes,
                "methods": total_methods,
                "lines": total_lines,
            }, None)
        except Exception as e:
            return (0, None, ("WRITE_ERROR", str(e), 0))

    #[@read]{[@params<<params>][@return<Tuple3>][@purpose<read registry entries from state>]}
    def read(self, params=None):
        return (1, {"entries": self.state["entries"], "output_path": self.state["output_path"]}, None)

    #[@edit]{[@params<<params>][@return<Tuple3>][@purpose<edit a specific domain entry in registry state>]}
    def edit(self, params):
        try:
            filename = params.get("filename", "")
            updates = params.get("updates", {})
            domains = self.state["entries"].get("domains", [])
            for d in domains:
                if d.get("filename") == filename:
                    d.update(updates)
                    return (1, {"edited": filename}, None)
            return (0, None, ("ENTRY_NOT_FOUND", filename, 0))
        except Exception as e:
            return (0, None, ("EDIT_ERROR", str(e), 0))

    #[@update]{[@params<<params>][@return<Tuple3>][@purpose<update registry output file with new domain data>]}
    def update(self, params):
        try:
            domains = params.get("domains", self.state["entries"].get("domains", []))
            output_path = params.get("output_path", self.state["output_path"] or Config.DEFAULT_OUTPUT)
            return self.write({"domains": domains, "output_path": output_path})
        except Exception as e:
            return (0, None, ("UPDATE_ERROR", str(e), 0))

    #[@index_domain]{[@params<<params>][@return<Tuple3>][@purpose<index parsed domain into MySQL code_index via CodeIndex>]}
    def index_domain(self, params):
        try:
            index = params.get("index")
            domain = params.get("domain")
            if not index or not domain:
                return (0, None, ("MISSING_PARAMS", "index and domain required", 0))

            fname = domain.get("filename", "")
            class_stack = []

            for entry in domain.get("classes", []):
                entry_type = entry[0]
                level = entry[1]
                name = entry[2]
                access_path = entry[3]
                extra = entry[4] if len(entry) > 4 else None

                if entry_type == "class":
                    while class_stack and class_stack[-1][0] >= level:
                        class_stack.pop()
                    class_stack.append((level, name, access_path))

                    comp = domain.get("class_compliance", {}).get(access_path)
                    is_compliant = comp.get("is_compliant", False) if comp else False
                    bcl_info = domain.get("bcl_headers", {}).get(("class", access_path))
                    has_bcl = bcl_info is not None and bcl_info.get("parsed_ok")

                    if level == 0:
                        index.Run("write_class", {
                            "class_name": name,
                            "access_path": access_path or name,
                            "source_file": fname,
                            "line_num": 0,
                            "bcl_header": has_bcl,
                            "vbstyle_compliant": is_compliant,
                        })
                    else:
                        parent = class_stack[0][1] if class_stack else ""
                        index.Run("write_authority", {
                            "authority_name": name,
                            "parent_class": parent,
                            "source_file": fname,
                        })

                elif entry_type == "method":
                    method_params = extra.get("params", "") if extra else ""
                    purpose = extra.get("purpose", "") if extra else ""
                    return_type = extra.get("return", "") if extra else ""
                    is_boilerplate = extra.get("is_boilerplate", False) if extra else False
                    has_bcl = extra.get("has_bcl", False) if extra else False
                    returns_tuple3 = "Tuple3" in (return_type or "") or "tuple3" in (return_type or "")

                    if class_stack:
                        parent = class_stack[-1][1]
                    else:
                        parent = domain.get("root_class", "Unknown")
                        if parent == "(none)":
                            parent = "Unknown"

                    index.Run("write_method", {
                        "method_name": name,
                        "class_name": parent,
                        "params": method_params,
                        "purpose": purpose,
                        "source_file": fname,
                        "line_num": 0,
                        "is_boilerplate": is_boilerplate,
                        "has_bcl": has_bcl,
                        "returns_tuple3": returns_tuple3,
                    })

            return (1, {"indexed": True}, None)
        except Exception as e:
            return (0, None, ("INDEX_ERROR", str(e), 0))

    #[@read_state]{[@params<<params>][@return<Tuple3>][@purpose<read Registry state>]}
    def read_state(self, params=None):
        return (1, self.state, None)

    #[@set_config]{[@params<<params>][@return<Tuple3>][@purpose<set Registry config>]}
    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))

    #[@Run]{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch Registry commands>]}
    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "format_tree": self.format_tree,
            "write": self.write,
            "read": self.read,
            "edit": self.edit,
            "update": self.update,
            "index_domain": self.index_domain,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))
