#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_parser.py>][@domain<Vbs_Code_Verifiation>][@role<analysis>][@auth<cascade>][@date<2026-06-26>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<analysis>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
Parser: VBStyle parsing authority.
Parses domains, Python files, BCL headers, and markdown documents.
Read, edit, and update parsed structures.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "BCL"))

try:
    from bcl_lexer import BCLTokenizer
    from bcl_parser import BCLParser
    from bcl_validator import BCLValidator
    _BCL_AVAILABLE = True
except ImportError:
    _BCL_AVAILABLE = False

from . import Config_Vbs_Code_Verifiation as Config


class Parser:
    """VBStyle parsing authority — domains, files, BCL headers, documents."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "catalog": [],
            "results": [],
            "parsed_files": {},
            "parsed_headers": {},
        }

    #[@clean_params]{[@params<<params>][@return<Tuple3>][@purpose<simplify parameter strings by removing self>]}
    def clean_params(self, params):
        try:
            params_raw = params.get("params_raw", "")
            p = params_raw.replace("self, ", "").replace("self", "").strip()
            if p.endswith(","):
                p = p[:-1].strip()
            return (1, {"params": p}, None)
        except Exception as e:
            return (0, None, ("CLEAN_PARAMS_ERROR", str(e), 0))

    #[@extract_header]{[@params<<params>][@return<Tuple3>][@purpose<extract full BCL header from comment line multi-line aware>]}
    def extract_header(self, params):
        try:
            line = params.get("line", "")
            lines_list = params.get("lines_list", [])
            line_idx = params.get("line_idx", 0)

            m = Config.BCL_HEADER_START_RE.match(line)
            if not m:
                return (1, {"raw_bcl": None}, None)

            raw_parts = []
            brace_depth = 0
            started = False

            for j in range(line_idx, min(line_idx + 20, len(lines_list))):
                raw_line = lines_list[j].rstrip()
                if not raw_line:
                    break

                stripped = raw_line.lstrip()
                if stripped.startswith("#"):
                    content = stripped[1:].lstrip()
                    if content.startswith("\\"):
                        content = content[1:].lstrip()
                else:
                    if started:
                        break
                    else:
                        content = stripped

                raw_parts.append(content)
                brace_depth += content.count("{") - content.count("}")
                started = True

                if brace_depth <= 0 and "}" in content:
                    break

            raw_bcl = "\n".join(raw_parts) if raw_parts else None
            return (1, {"raw_bcl": raw_bcl}, None)
        except Exception as e:
            return (0, None, ("EXTRACT_ERROR", str(e), 0))

    #[@extract_fields]{[@params<<params>][@return<Tuple3>][@purpose<extract purpose params return from header body>]}
    def extract_fields(self, params):
        try:
            header_body = params.get("header_body", "")
            fields = {}

            m = Config.PURPOSE_RE.search(header_body)
            if m:
                fields["purpose"] = m.group(1)
            m = Config.PARAMS_RE.search(header_body)
            if m:
                fields["params"] = m.group(1)
            m = Config.RETURN_RE.search(header_body)
            if m:
                fields["return"] = m.group(1)

            return (1, fields, None)
        except Exception as e:
            return (0, None, ("FIELD_ERROR", str(e), 0))

    #[@parse_header]{[@params<<params>][@return<Tuple3>][@purpose<parse BCL header using lexer parser validator pipeline>]}
    def parse_header(self, params):
        try:
            raw_bcl = params.get("raw_bcl", "")
            info = {
                "raw_text": raw_bcl,
                "container_name": "",
                "has_header": True,
                "parsed_ok": False,
                "parse_error": "",
                "validation_ok": None,
                "validation_violations": [],
                "tuples": [],
                "children_count": 0,
            }

            name_match = re.search(r'\[@(\w+)\]', raw_bcl)
            if name_match:
                info["container_name"] = name_match.group(1)

            if not _BCL_AVAILABLE:
                info["parse_error"] = "BCL modules not available"
                return (1, info, None)

            try:
                tokenizer = BCLTokenizer(raw_bcl)
                tokens = tokenizer.tokenize()
            except Exception as e:
                info["parse_error"] = "Lexer: {}".format(e)
                return (1, info, None)

            try:
                parser = BCLParser(tokens)
                ast = parser.parse()
                if ast.children:
                    node = ast.children[0]
                    info["tuples"] = node.tuples
                    info["children_count"] = len(node.children)
                info["parsed_ok"] = True
            except Exception as e:
                info["parse_error"] = "Parser: {}".format(e)
                return (1, info, None)

            try:
                validator = BCLValidator()
                report = validator.validate(ast)
                info["validation_ok"] = report.ok
                info["validation_violations"] = [
                    {"rule_id": v.rule_id, "message": v.message}
                    for v in report.violations
                ]
            except Exception as e:
                info["parse_error"] = "Validator: {}".format(e)

            return (1, info, None)
        except Exception as e:
            return (0, None, ("PARSE_ERROR", str(e), 0))

    #[@parse_file]{[@params<<params>][@return<Tuple3>][@purpose<parse a Python source file and extract class hierarchy with methods>]}
    def parse_file(self, params):
        try:
            filepath = params.get("filepath", "")
            if not os.path.exists(filepath):
                return (0, None, ("FILE_NOT_FOUND", filepath, 0))

            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                lines_list = fh.readlines()

            total = len(lines_list)
            fname = os.path.basename(filepath)

            class_stack = []
            tree_entries = []
            class_ranges = {}
            bcl_headers = {}
            root_class = None
            sub_authorities = []
            pending_header = None
            pending_bcl_raw = None

            total_methods_found = 0
            methods_with_bcl = 0
            total_classes_found = 0
            classes_with_bcl = 0

            for i, line in enumerate(lines_list):
                stripped = line.rstrip()
                if not stripped:
                    continue

                header_match = Config.HEADER_RE.match(stripped)
                bcl_start = Config.BCL_HEADER_START_RE.match(stripped)
                if bcl_start:
                    r = self.extract_header({
                        "line": stripped,
                        "lines_list": lines_list,
                        "line_idx": i,
                    })
                    if r[0] and r[1] and r[1]["raw_bcl"]:
                        pending_bcl_raw = r[1]["raw_bcl"]
                    if header_match:
                        pending_header = (header_match.group(1), header_match.group(2))
                    continue

                class_match = Config.CLASS_RE.match(stripped)
                if class_match:
                    indent = len(class_match.group(1))
                    name = class_match.group(2)
                    total_classes_found += 1

                    while class_stack and class_stack[-1][0] >= indent:
                        popped = class_stack.pop()
                        popped_path = ".".join([c[1] for c in class_stack] + [popped[1]])
                        if popped_path in class_ranges and class_ranges[popped_path][1] == 0:
                            class_ranges[popped_path] = (class_ranges[popped_path][0], i)

                    path_parts = [c[1] for c in class_stack] + [name]
                    access_path = ".".join(path_parts)
                    level = len(class_stack)
                    class_stack.append((indent, name, i))

                    if level == 0 and root_class is None:
                        root_class = name
                    elif level == 1:
                        sub_authorities.append(name)

                    if pending_bcl_raw:
                        r = self.parse_header({"raw_bcl": pending_bcl_raw})
                        if r[0] and r[1]:
                            bcl_headers[("class", access_path)] = r[1]
                        classes_with_bcl += 1
                        pending_bcl_raw = None

                    class_ranges[access_path] = (i, 0)
                    tree_entries.append(("class", level, name, access_path, None))
                    pending_header = None
                    continue

                def_match = Config.DEF_RE.match(stripped)
                if def_match and class_stack:
                    indent = len(def_match.group(1))
                    name = def_match.group(2)
                    params_raw = def_match.group(3).strip()
                    total_methods_found += 1

                    if name.startswith("__") and name.endswith("__") and name != "__init__":
                        pending_header = None
                        pending_bcl_raw = None
                        continue

                    r = self.clean_params({"params_raw": params_raw})
                    params_clean = r[1]["params"] if r[0] else ""

                    purpose = ""
                    return_type = ""
                    if pending_header:
                        hdr_body = pending_header[1]
                        r = self.extract_fields({"header_body": hdr_body})
                        if r[0] and r[1]:
                            purpose = r[1].get("purpose", "")
                            return_type = r[1].get("return", "")
                            if not params_clean:
                                params_clean = r[1].get("params", "")

                    if pending_bcl_raw:
                        r = self.parse_header({"raw_bcl": pending_bcl_raw})
                        if r[0] and r[1]:
                            bcl_headers[("method", name)] = r[1]
                        methods_with_bcl += 1
                        pending_bcl_raw = None

                    is_boilerplate = name in Config.BOILERPLATE_METHODS

                    if indent > class_stack[-1][0]:
                        level = len(class_stack)
                    else:
                        level = len(class_stack) - 1

                    extra = {
                        "params": params_clean,
                        "purpose": purpose,
                        "return": return_type,
                        "is_boilerplate": is_boilerplate,
                        "has_bcl": ("method", name) in bcl_headers,
                    }
                    tree_entries.append(("method", level, name, None, extra))
                    pending_header = None

            for path, (start, end) in class_ranges.items():
                if end == 0:
                    class_ranges[path] = (start, total)

            domain_file = {
                "filename": fname,
                "filepath": filepath,
                "total_lines": total,
                "root_class": root_class or "(none)",
                "sub_authorities": sub_authorities,
                "classes": tree_entries,
                "class_ranges": class_ranges,
                "bcl_headers": bcl_headers,
                "bcl_coverage": {
                    "total_classes": total_classes_found,
                    "classes_with_bcl": classes_with_bcl,
                    "total_methods": total_methods_found,
                    "methods_with_bcl": methods_with_bcl,
                    "bcl_valid": sum(1 for info in bcl_headers.values() if info.get("parsed_ok")),
                    "bcl_invalid": sum(1 for info in bcl_headers.values() if not info.get("parsed_ok")),
                    "bcl_validation_passed": sum(1 for info in bcl_headers.values()
                                                 if info.get("validation_ok")),
                    "bcl_validation_failed": sum(1 for info in bcl_headers.values()
                                                 if info.get("validation_ok") is False),
                },
            }

            self.state["parsed_files"][filepath] = domain_file
            return (1, domain_file, None)
        except Exception as e:
            return (0, None, ("PARSE_ERROR", str(e), 0))

    #[@parse_document]{[@params<<params>][@return<Tuple3>][@purpose<parse a markdown document and extract BCL headers and structure>]}
    def parse_document(self, params):
        try:
            filepath = params.get("filepath", "")
            if not os.path.exists(filepath):
                return (0, None, ("FILE_NOT_FOUND", filepath, 0))

            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()

            lines_list = content.splitlines(keepends=True)
            sections = []
            bcl_blocks = []
            current_section = None
            current_level = 0

            for i, line in enumerate(lines_list):
                stripped = line.rstrip()

                if stripped.startswith("#"):
                    heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
                    if heading_match:
                        if current_section:
                            sections.append(current_section)
                        current_section = {
                            "title": heading_match.group(2),
                            "level": len(heading_match.group(1)),
                            "start_line": i,
                            "end_line": len(lines_list),
                            "content_lines": [],
                        }
                        continue

                bcl_start = Config.BCL_HEADER_START_RE.match(stripped)
                if bcl_start:
                    r = self.extract_header({
                        "line": stripped,
                        "lines_list": lines_list,
                        "line_idx": i,
                    })
                    if r[0] and r[1] and r[1]["raw_bcl"]:
                        parse_r = self.parse_header({"raw_bcl": r[1]["raw_bcl"]})
                        if parse_r[0] and parse_r[1]:
                            bcl_blocks.append({
                                "line": i,
                                "info": parse_r[1],
                            })

                if current_section:
                    current_section["content_lines"].append(stripped)

            if current_section:
                sections.append(current_section)

            for idx, sec in enumerate(sections):
                if idx + 1 < len(sections):
                    sec["end_line"] = sections[idx + 1]["start_line"]

            result = {
                "filepath": filepath,
                "total_lines": len(lines_list),
                "sections": sections,
                "bcl_blocks": bcl_blocks,
                "section_count": len(sections),
                "bcl_block_count": len(bcl_blocks),
            }

            return (1, result, None)
        except Exception as e:
            return (0, None, ("PARSE_DOC_ERROR", str(e), 0))

    #[@read_parsed]{[@params<<params>][@return<Tuple3>][@purpose<read a previously parsed file from state>]}
    def read_parsed(self, params):
        try:
            filepath = params.get("filepath", "")
            if filepath in self.state["parsed_files"]:
                return (1, self.state["parsed_files"][filepath], None)
            return (0, None, ("NOT_PARSED", filepath, 0))
        except Exception as e:
            return (0, None, ("READ_PARSED_ERROR", str(e), 0))

    #[@update_parsed]{[@params<<params>][@return<Tuple3>][@purpose<update a previously parsed file entry in state>]}
    def update_parsed(self, params):
        try:
            filepath = params.get("filepath", "")
            updates = params.get("updates", {})
            if filepath not in self.state["parsed_files"]:
                return (0, None, ("NOT_PARSED", filepath, 0))
            self.state["parsed_files"][filepath].update(updates)
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("UPDATE_PARSED_ERROR", str(e), 0))

    #[@edit_header]{[@params<<params>][@return<Tuple3>][@purpose<edit a parsed BCL header in state>]}
    def edit_header(self, params):
        try:
            key = params.get("key")
            updates = params.get("updates", {})
            if key in self.state["parsed_headers"]:
                self.state["parsed_headers"][key].update(updates)
                return (1, {"updated": True}, None)
            return (0, None, ("HEADER_NOT_FOUND", str(key), 0))
        except Exception as e:
            return (0, None, ("EDIT_HEADER_ERROR", str(e), 0))

    #[@read_state]{[@params<<params>][@return<Tuple3>][@purpose<read Parser state>]}
    def read_state(self, params=None):
        return (1, self.state, None)

    #[@set_config]{[@params<<params>][@return<Tuple3>][@purpose<set Parser config>]}
    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))

    #[@Run]{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch Parser commands>]}
    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "clean_params": self.clean_params,
            "extract_header": self.extract_header,
            "extract_fields": self.extract_fields,
            "parse_header": self.parse_header,
            "parse_file": self.parse_file,
            "parse_document": self.parse_document,
            "read_parsed": self.read_parsed,
            "update_parsed": self.update_parsed,
            "edit_header": self.edit_header,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))
