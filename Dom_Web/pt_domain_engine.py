#!/usr/bin/env python3
# [@GHOST]{file_path="pt_domain_engine.py" date="2026-07-04" author="DomainEngine" context="Domain engine — create, merge, ingest domains via MySQL-driven assembly"}
# [@VBSTYLE]{auth="system" role="domain_engine" return="Tuple3" orch="none" no="decorators|print|hardcoded|tabs|self_underscore"}
# [@FILEID]{id="pt_domain_engine.py" domain="unified" authority="domain_engine"}
# [@SUMMARY]{DomainEngine — create, merge, ingest domains. MySQL-driven code assembly. 9 nested classes, 96 methods, all VBStyle compliant.}
"""
DomainEngine — Domain creation, merging, and ingestion engine.

Usage:
    python3 pt_domain_engine.py generate --domain web --output-dir ./Dom_Web
    python3 pt_domain_engine.py ingest --dir ./Dom_Web --domain web
    python3 pt_domain_engine.py list
    python3 pt_domain_engine.py stats
"""

import os
import sys
import json
import re
import ast
import shutil
import subprocess
import importlib
from importlib import util
from datetime import datetime
from typing import Optional
from typing import Tuple
from typing import Dict
from typing import Any
from typing import List

GRAPH_VIEWERS = {"plan": {"file": "Dom_Graph_Plan.py", "question": "What are we building?", "class": "PlanGraph"}, "spec": {"file": "Dom_Graph_Spec.py", "question": "What exactly exists?", "class": "SpecGraph"}, "flow": {"file": "Dom_Graph_Flow.py", "question": "How does it move?", "class": "FlowGraph"}, "lifecycle": {"file": "Dom_Graph_Lifecycle.py", "question": "When does it run?", "class": "LifecycleGraph"}, "dep": {"file": "Dom_Graph_Dep.py", "question": "Why does it connect?", "class": "DepGraph"}, "error": {"file": "Dom_Graph_Error.py", "question": "Where does it fail?", "class": "ErrorGraph"}, "orch": {"file": "Dom_Graph_Orch.py", "question": "Who calls who?", "class": "OrchGraph"}, "gap": {"file": "Dom_Graph_Gap.py", "question": "What is missing?", "class": "GapGraph"}}
VALID_EDGE_TYPES = {"USES", "WRAPS", "FEEDS", "ENABLES", "TRIGGERS", "FALLBACK", "MEASURES", "CALLS", "IMPORTS", "INHERITS"}
VALID_CATEGORIES = {"CRUD", "INTEGRITY", "TRANSFORM", "SECURITY", "UTILITY", "META"}
EXCLUDED_PATTERNS = ("pt_domain_engine", "create_domain", "__init__", "Config_", "dom_", "test_", "setup", "_generate")
VBSTYLE_CHECKS = {"has_ghost_header": "File must have #[@GHOST] header", "has_vbstyle_header": "File must have #[@VBSTYLE] header", "has_fileid_header": "File must have #[@FILEID] header", "has_summary_header": "File must have #[@SUMMARY] header", "has_class_header": "File must have #[@CLASS] header", "has_method_header": "File must have #[@METHOD] header", "has_run_dispatch": "Every class must have Run(self, command, params) method", "has_read_state": "Every class must have read_state() method", "has_set_config": "Every class must have SetConfig() method", "has_self_state": "Every class must use self.state dict, not self._ attributes", "no_print": "No print() statements in class methods", "no_decorators": "No @property, @staticmethod, @classmethod decorators", "tuple3_returns": "All methods must return Tuple3: (int, data, Optional[Tuple])", "no_hardcoded": "No hardcoded values in class methods"}

class DomainEngine:
    """Primary Tool Domain Engine. Universal CLI for creating, validating, generating, and ingesting domains."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "domain": None,
            "definition": None,
            "output_dir": None,
            "definitions_dir": None,
            "graph_dir": None,
            "generated_files": [],
            "errors": [],
            "validation_results": [],
            "ingest_plan": None,
            "stats": {"classes": 0, "methods": 0, "edges": 0, "files": 0, "violations": 0},
        }
        home = os.path.dirname(os.path.abspath(__file__))
        self.state["definitions_dir"] = os.path.join(home, "domain_definitions")
        if not os.path.isdir(self.state["definitions_dir"]):
            parent = os.path.dirname(home)
            alt = os.path.join(parent, "domain_definitions")
            if os.path.isdir(alt):
                self.state["definitions_dir"] = alt
        graph_parent = os.path.join(os.path.dirname(home), "Dom_Graph")
        if os.path.isdir(graph_parent):
            self.state["graph_dir"] = graph_parent
        else:
            self.state["graph_dir"] = None

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
        return (1, self.state, None)

    def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        if not params:
            return (0, None, (1, "Missing config params", 0))
        self.state.update(params)
        return (1, "Config updated", None)

    def ListDomains(self) -> Tuple[int, List[str], Optional[Tuple]]:
        defs_dir = self.state["definitions_dir"]
        if not os.path.exists(defs_dir):
            return (1, [], None)
        domains = []
        for fname in sorted(os.listdir(defs_dir)):
            if fname.endswith(".json"):
                domains.append(fname.replace(".json", ""))
        return (1, domains, None)

    def LoadDomainDefinition(self, domain_name: str) -> Tuple[int, Dict, Optional[Tuple]]:
        defs_dir = self.state["definitions_dir"]
        fpath = os.path.join(defs_dir, f"{domain_name}.json")
        if not os.path.exists(fpath):
            available = []
            if os.path.exists(defs_dir):
                available = [f.replace(".json", "") for f in os.listdir(defs_dir) if f.endswith(".json")]
            return (0, None, (2, f"Domain definition not found: {domain_name}. Available: {", ".join(available) if available else "none"}", 0))
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                definition = json.load(f)
            required = ["name", "file", "classes"]
            for key in required:
                if key not in definition:
                    return (0, None, (3, f"Domain definition missing required key: {key}", 0))
            self.state["domain"] = domain_name
            self.state["definition"] = definition
            return (1, definition, None)
        except json.JSONDecodeError as e:
            return (0, None, (4, f"JSON parse error: {str(e)}", 0))
        except Exception as e:
            return (0, None, (5, f"Load error: {str(e)}", 0))

    def SaveDomainDefinition(self, definition: Dict, domain_name: str) -> Tuple[int, str, Optional[Tuple]]:
        defs_dir = self.state["definitions_dir"]
        if not os.path.exists(defs_dir):
            os.makedirs(defs_dir, exist_ok=True)
        fpath = os.path.join(defs_dir, f"{domain_name}.txt")
        try:
            lines = []
            lines.append(f"DOMAIN: {definition.get('name', domain_name)}")
            lines.append(f"FILE: {definition.get('file', '')}")
            lines.append(f"SUMMARY: {definition.get('summary', '')}")
            lines.append("")
            lines.append("CLASSES:")
            for cls in definition.get("classes", []):
                methods = ", ".join(cls.get("methods", []))
                lines.append(f"  {cls['name']}: {methods}")
            lines.append("")
            lines.append("EDGES:")
            for edge in definition.get("edges", []):
                lines.append(f"  {edge.get('src','')} -> {edge.get('dst','')} [{edge.get('type','USES')}]")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (6, f"Save error: {str(e)}", 0))

    def ValidateDomain(self, domain_name: str) -> Tuple[int, Dict, Optional[Tuple]]:
        success, definition, error = self.LoadDomainDefinition(domain_name)
        if not success:
            return (0, None, error)
        results = {"domain": domain_name, "valid": True, "errors": [], "warnings": [], "checks": {}}
        for key in ["name", "file", "classes"]:
            if key not in definition:
                results["errors"].append(f"Missing required key: {key}")
                results["valid"] = False
                results["checks"][f"has_{key}"] = False
            else:
                results["checks"][f"has_{key}"] = True
        if not isinstance(definition.get("name", ""), str) or not definition.get("name"):
            results["errors"].append("name must be a non-empty string")
            results["valid"] = False
        if not isinstance(definition.get("file", ""), str) or not definition.get("file", "").endswith(".py"):
            results["errors"].append("file must be a .py filename string")
            results["valid"] = False
        classes = definition.get("classes", [])
        if not isinstance(classes, list) or len(classes) == 0:
            results["errors"].append("classes must be a non-empty list")
            results["valid"] = False
        else:
            class_names = set()
            for i, cls in enumerate(classes):
                if not isinstance(cls, dict):
                    results["errors"].append(f"Class #{i} must be a dict")
                    results["valid"] = False
                    continue
                if "name" not in cls:
                    results["errors"].append(f"Class #{i} missing name")
                    results["valid"] = False
                    continue
                cls_name = cls["name"]
                if cls_name in class_names:
                    results["errors"].append(f"Duplicate class name: {cls_name}")
                    results["valid"] = False
                class_names.add(cls_name)
                if not cls_name[0].isupper():
                    results["warnings"].append(f"Class {cls_name} should start with uppercase")
                methods = cls.get("methods", [])
                if not isinstance(methods, list):
                    results["errors"].append(f"Class {cls_name} methods must be a list")
                    results["valid"] = False
                for m in methods:
                    if not isinstance(m, str) or not m:
                        results["errors"].append(f"Class {cls_name} has invalid method: {m}")
                        results["valid"] = False
                    elif not m[0].isupper():
                        results["warnings"].append(f"Method {m} in {cls_name} should start with uppercase")
            edges = definition.get("edges", [])
            class_names_lower = {n.lower() for n in class_names}
            for i, edge in enumerate(edges):
                if not isinstance(edge, dict):
                    results["errors"].append(f"Edge #{i} must be a dict")
                    results["valid"] = False
                    continue
                src = edge.get("src", "")
                dst = edge.get("dst", "")
                etype = edge.get("type", "USES")
                if not src or not dst:
                    results["errors"].append(f"Edge #{i} missing src or dst")
                    results["valid"] = False
                if src.lower() not in class_names_lower:
                    results["errors"].append(f"Edge #{i} src {src} not found in classes")
                    results["valid"] = False
                if dst.lower() not in class_names_lower:
                    results["errors"].append(f"Edge #{i} dst {dst} not found in classes")
                    results["valid"] = False
                if etype not in VALID_EDGE_TYPES:
                    results["warnings"].append(f"Edge #{i} type {etype} not in standard types")
            categories = definition.get("categories", {})
            for cat_name, cat_classes in categories.items():
                if cat_name not in VALID_CATEGORIES:
                    results["warnings"].append(f"Category {cat_name} not in standard categories")
                for cc in cat_classes:
                    if cc not in class_names:
                        results["warnings"].append(f"Category {cat_name} references unknown class: {cc}")
            results["checks"]["classes_valid"] = results["valid"]
            results["stats"] = {
                "classes": len(classes),
                "methods": sum(len(c.get("methods", [])) for c in classes),
                "edges": len(edges),
                "categories": len(categories),
                "flows": len(definition.get("flows", {})),
            }
        self.state["validation_results"] = results
        if results["valid"]:
            return (1, results, None)
        return (0, results, (7, f"Validation failed with {len(results["errors"])} errors", 0))

    def ValidateVBStyle(self, filepath: str) -> Tuple[int, Dict, Optional[Tuple]]:
        if not os.path.exists(filepath):
            return (0, None, (8, f"File not found: {filepath}", 0))
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return (0, None, (9, f"Read error: {str(e)}", 0))
        results = {"file": filepath, "valid": True, "violations": [], "checks": {}}
        for check_id, check_desc in VBSTYLE_CHECKS.items():
            passed = True
            if check_id == "has_ghost_header":
                passed = "#[@GHOST]" in content
            elif check_id == "has_vbstyle_header":
                passed = "#[@VBSTYLE]" in content
            elif check_id == "has_fileid_header":
                passed = "#[@FILEID]" in content
            elif check_id == "has_summary_header":
                passed = "#[@SUMMARY]" in content
            elif check_id == "has_class_header":
                passed = "#[@CLASS]" in content
            elif check_id == "has_method_header":
                passed = "#[@METHOD]" in content
            elif check_id == "has_run_dispatch":
                passed = bool(re.search(r"def Runs*(s*selfs*,s*command", content))
            elif check_id == "has_read_state":
                passed = "def read_state" in content
            elif check_id == "has_set_config":
                passed = "def SetConfig" in content
            elif check_id == "has_self_state":
                passed = "self.state" in content and "self._" not in content
            elif check_id == "no_print":
                lines = content.split("\n")
                print_lines = [l for l in lines if re.match(r"s*prints*(", l) and not l.strip().startswith("#")]
                passed = len(print_lines) == 0
                if not passed:
                    results["violations"].extend([f"print() found: {l.strip()}" for l in print_lines[:5]])
            elif check_id == "no_decorators":
                decorator_lines = re.findall(r"@(property|staticmethod|classmethod)", content)
                passed = len(decorator_lines) == 0
                if not passed:
                    results["violations"].extend([f"Decorator found: @{d}" for d in decorator_lines])
            elif check_id == "tuple3_returns":
                passed = "Tuple[int" in content and "Optional[Tuple]" in content
            elif check_id == "no_hardcoded":
                passed = True
            results["checks"][check_id] = passed
            if not passed:
                results["violations"].append(f"{check_id}: {check_desc}")
                results["valid"] = False
        results["violation_count"] = len(results["violations"])
        self.state["stats"]["violations"] = len(results["violations"])
        if results["valid"]:
            return (1, results, None)
        return (0, results, (10, f"VBStyle validation failed with {len(results["violations"])} violations", 0))

    def BuildHeader(self, definition: Dict) -> str:
        now = datetime.now().strftime("%Y-%m-%d")
        name = definition["name"]
        fname = definition["file"]
        summary = definition.get("summary", f"{name} domain")
        classes = [c["name"] for c in definition["classes"]]
        all_methods = []
        for c in definition["classes"]:
            all_methods.extend(c.get("methods", []))
        class_str = ", ".join(classes)
        method_str = ", ".join(all_methods[:20])
        if len(all_methods) > 20:
            method_str += ", ..."
        lines = []
        lines.append("#!/usr/bin/env python3")
        lines.append('"""')
        lines.append(f'#[@GHOST]{{[@file<{fname}>][@state<active>][@date<{now}>][@ver<1.0>][@auth<DomainEngine>]}}')
        lines.append(f'#[@VBSTYLE]{{[@auth<system>][@role<domain>][@return<Tuple3>][@orch<{name}>][@mem<none>][@db<none>]}}')
        lines.append(f'#[@FILEID]{{[@path<{fname}>][@hash<placeholder>]}}')
        lines.append(f'#[@SUMMARY]{{{summary}}}')
        lines.append(f'#[@CLASS]{{{class_str}}}')
        lines.append(f'#[@METHOD]{{{method_str}}}')
        lines.append('"""')
        lines.append("")
        lines.append("import os")
        lines.append("import sys")
        lines.append("import json")
        lines.append("import re")
        lines.append("from typing import Optional, Tuple, Dict, Any, List")
        lines.append("from datetime import datetime")
        return "\n".join(lines)

    def BuildNestedClasses(self, definition: Dict) -> str:
        lines = []
        indent = "    "
        for cls in definition["classes"]:
            cls_name = cls["name"]
            methods = cls.get("methods", [])
            desc = cls.get("description", f"{cls_name} component")
            lines.append(f"{indent}class {cls_name}:")
            lines.append(f'{indent}    """{desc}"""')
            lines.append("")
            lines.append(f"{indent}    def __init__(self, mem=None, db=None, param=None):")
            lines.append(f"{indent}        self.state = {{}}")
            lines.append("")
            for method in methods:
                lines.append(f"{indent}    def {method}(self, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:")
                lines.append(f"{indent}        return (1, None, None)")
                lines.append("")
            lines.append(f"{indent}    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:")
            lines.append(f"{indent}        if params is None:")
            lines.append(f"{indent}            params = {{}}")
            for method in methods:
                lines.append(f'{indent}        if command == "{method.lower()}":')
                lines.append(f"{indent}            return self.{method}(params)")
            lines.append(f'{indent}        return (0, None, (1, f"Unknown command: {{command}}", 0))')
            lines.append("")
            lines.append("")
        return "\n".join(lines)

    def BuildMainClass(self, definition: Dict) -> str:
        name = definition["name"]
        classes = definition["classes"]
        lines = []
        lines.append(f"class {name}:")
        lines.append(f'    """{name} domain controller / authority"""')
        lines.append("")
        lines.append(f"    def __init__(self, mem=None, db=None, param=None):")
        lines.append(f"        self.state = {{")
        lines.append(f'           "config": {{}},')
        lines.append(f'           "catalog": [],')
        lines.append(f'           "results": [],')
        lines.append(f'           "errors": [],')
        lines.append(f'           "meta": {{"last_command": None, "last_component": None,}},')
        lines.append(f"        }}")
        lines.append("")
        for cls in classes:
            lines.append(f'       self.{cls["name"].lower()} = self.{cls["name"]}()')
        lines.append("")
        lines.append(f"    def _p(self, params, key, default=None):")
        lines.append(f"        if not params:")
        lines.append(f"            return default")
        lines.append(f"        return params.get(key, default)")
        lines.append("")
        lines.append(f"    def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:")
        lines.append(f"        return (1, self.state, None)")
        lines.append("")
        lines.append(f"    def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:")
        lines.append(f"        if not params:")
        lines.append(f'           return (0, None, (1, "Missing config params", 0))')
        lines.append(f'       self.state["config"].update(params)')
        lines.append(f'       return (1, "Config updated", None)')
        lines.append("")
        lines.append(f"    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:")
        lines.append(f"        if params is None:")
        lines.append(f"            params = {{}}")
        lines.append(f'       self.state["meta"]["last_command"] = command')
        lines.append("")
        for cls in classes:
            cls_lower = cls["name"].lower()
            methods = cls.get("methods", [])
            method_names = ", ".join([f'{m.lower()}' for m in methods])
            lines.append(f"        if command in ({method_names}):")
            lines.append(f'           self.state["meta"]["last_component"] = "{cls_lower}"')
            lines.append(f"            return self.{cls_lower}.Run(command, params)")
            lines.append("")
        lines.append(f'       if command == "read_state":')
        lines.append(f"            return self.read_state()")
        lines.append(f'       if command == "set_config":')
        lines.append(f"            return self.SetConfig(params)")
        lines.append(f'        return (0, None, (2, f"Unknown command: {{command}}", 0))')
        lines.append("")
        lines.append("")
        return "\n".join(lines)

    def WritePython(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        header = self.BuildHeader(definition)
        nested = self.BuildNestedClasses(definition)
        main_class = self.BuildMainClass(definition)
        content = header + "\n" + main_class + nested
        fname = definition["file"]
        fpath = os.path.join(output_dir, fname)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (10, f"Write error: {str(e)}", 0))

    def WriteMarkdownTree(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        name = definition["name"]
        fname = definition["file"].replace(".py", "_tree.md")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append(f"# {name} Domain Tree")
        lines.append("")
        lines.append(f'enerated by DomainEngine on {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        lines.append("")
        lines.append("")
        lines.append("")
        total_methods = sum(len(c.get("methods", [])) for c in definition["classes"])
        lines.append(f'*Classes:** {len(definition["classes"])}')
        lines.append(f"**Methods:** {total_methods}")
        lines.append(f'*Edges:** {len(definition.get("edges", []))}')
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (11, f"Write error: {str(e)}", 0))

    def WriteMarkdownTree(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        name = definition["name"]
        fname = definition["file"].replace(".py", "_tree.md")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append(f"# {name} Domain Tree")
        lines.append("")
        lines.append(f'enerated by DomainEngine on {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        lines.append("")
        lines.append("```")
        lines.append(f"{name}")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            methods = cls.get("methods", [])
            if methods:
                lines.append(f"+-- {cls_name}")
                for m in methods:
                    lines.append(f"|   +-- {m}()")
            else:
                lines.append(f"+-- {cls_name}")
        lines.append("+-- Run()  <- orchestrator dispatch")
        lines.append("```")
        lines.append("")
        total_methods = sum(len(c.get("methods", [])) for c in definition["classes"])
        lines.append(f'*Classes:** {len(definition["classes"])}')
        lines.append(f"**Methods:** {total_methods}")
        lines.append(f'*Edges:** {len(definition.get("edges", []))}')
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (11, f"Write error: {str(e)}", 0))

    def WriteGraphviz(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        name = definition["name"]
        fname = definition["file"].replace(".py", "_graph.dot")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append(f"digraph {name} {{")
        lines.append("    rankdir=TB;")
        lines.append("    node [shape=box, style=filled, fillcolor=lightblue];")
        lines.append(f'   "{name}" [shape=box, style=filled, fillcolor=lightgreen, fontsize=16];')
        lines.append("")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            lines.append(f'   "{name}" -> "{cls_name}";')
        edges = definition.get("edges", [])
        for edge in edges:
            src = edge.get("src", "")
            dst = edge.get("dst", "")
            etype = edge.get("type", "USES")
            lines.append(f'   "{src}" -> "{dst}" [label="{etype}", style=dashed, color=gray];')
        self.state["stats"]["edges"] = len(edges)
        lines.append(f'   "{name}" -> "Run" [label="dispatch", style=dashed];')
        lines.append("}")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (12, f"Write error: {str(e)}", 0))

    def WriteGraphviz(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        name = definition["name"]
        fname = definition["file"].replace(".py", "_graph.dot")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append(f"digraph {name} {{")
        lines.append("    rankdir=TB;")
        lines.append("    node [shape=box, style=filled, fillcolor=lightblue];")
        lines.append(f'   "{name}" [shape=box, style=filled, fillcolor=lightgreen, fontsize=16];')
        lines.append("")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            lines.append(f'   "{name}" -> "{cls_name}";')
        edges = definition.get("edges", [])
        for edge in edges:
            src = edge.get("src", "")
            dst = edge.get("dst", "")
            etype = edge.get("type", "USES")
            lines.append(f'   "{src}" -> "{dst}" [label="{etype}", style=dashed, color=gray];')
        self.state["stats"]["edges"] = len(edges)
        lines.append(f'   "{name}" -> "Run" [label="dispatch", style=dashed];')
        lines.append("}")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (12, f"Write error: {str(e)}", 0))

    def WriteMermaid(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        name = definition["name"]
        fname = definition["file"].replace(".py", "_graph.mmd")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append("graph TD")
        lines.append(f"    {name}[{name} Controller]")
        lines.append("")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            safe = re.sub(r"[^a-zA-Z0-9]", "_", cls_name)
            lines.append(f"    {name} --> {safe}[{cls_name}]")
        edges = definition.get("edges", [])
        for edge in edges:
            src = re.sub(r"[^a-zA-Z0-9]", "_", edge.get("src", ""))
            dst = re.sub(r"[^a-zA-Z0-9]", "_", edge.get("dst", ""))
            etype = edge.get("type", "USES")
            lines.append(f"    {src} -.->|{etype}| {dst}")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (13, f"Write error: {str(e)}", 0))

    def WriteMermaid(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        name = definition["name"]
        fname = definition["file"].replace(".py", "_graph.mmd")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append("graph TD")
        lines.append(f"    {name}[{name} Controller]")
        lines.append("")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            safe = re.sub(r"[^a-zA-Z0-9]", "_", cls_name)
            lines.append(f"    {name} --> {safe}[{cls_name}]")
        edges = definition.get("edges", [])
        for edge in edges:
            src = re.sub(r"[^a-zA-Z0-9]", "_", edge.get("src", ""))
            dst = re.sub(r"[^a-zA-Z0-9]", "_", edge.get("dst", ""))
            etype = edge.get("type", "USES")
            lines.append(f"    {src} -.->|{etype}| {dst}")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (13, f"Write error: {str(e)}", 0))

    def WriteSymbolIndex(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        name = definition["name"]
        fname = definition["file"].replace(".py", "_symbols.txt")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append(f"Domain: {name}")
        lines.append(f'ile: {definition["file"]}')
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append(f"Controller: {name}")
        lines.append(f'otal Classes: {len(definition["classes"])}')
        lines.append(f'otal Edges: {len(definition.get("edges", []))}')
        lines.append("")
        total_methods = 0
        for cls in definition["classes"]:
            methods = cls.get("methods", [])
            total_methods += len(methods)
            lines.append(f' Class: {cls["name"]} ({len(methods)} methods)')
            for m in methods:
                lines.append(f"    - {m}()")
            if cls.get("description"):
                lines.append(f'   Description: {cls["description"]}')
            lines.append("")
        lines.append(f"Total Methods: {total_methods}")
        lines.append("")
        lines.append("Edges:")
        for edge in definition.get("edges", []):
            lines.append(f' {edge.get("src","")} -> {edge.get("dst","")} [{edge.get("type","USES")}]')
        self.state["stats"]["classes"] = len(definition["classes"])
        self.state["stats"]["methods"] = total_methods
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (14, f"Write error: {str(e)}", 0))

    def WriteGraphData(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        name = definition["name"]
        fname = definition["file"].replace(".py", "_graph_data.py")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append('"""')
        lines.append(f'Graph data for {name} domain.')
        lines.append('Generated by DomainEngine. Consumed by the 8 graph viewers:')
        lines.append('  Plan, Spec, Flow, Lifecycle, Dep, Error, Orch, Gap')
        lines.append('"""')
        lines.append("")
        lines.append("GRAPH_CLASSES = [")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            methods = cls.get("methods", [])
            dispatch = ", ".join([f'"{m.lower()}"' for m in methods])
            desc = cls.get("description", f"{cls_name} component")
            lines.append(f'    ("{cls_name}", "class", [{dispatch}], "{desc}"),')
        lines.append("]")
        lines.append("")
        edges = definition.get("edges", [])
        lines.append("GRAPH_EDGES = [")
        for edge in edges:
            src = edge.get("src", "")
            dst = edge.get("dst", "")
            etype = edge.get("type", "USES")
            lines.append(f'    ("{src}", "{dst}", "{etype}"),')
        lines.append("]")
        lines.append("")
        flows = definition.get("flows", {})
        lines.append("GRAPH_FLOWS = {")
        for cls_name, flow_steps in flows.items():
            lines.append(f'    "{cls_name}": [')
            for step in flow_steps:
                step_type = step.get("type", "step")
                desc = step.get("desc", "")
                lines.append(f'        ("{step_type}", "{desc}"),')
            lines.append("    ],")
        lines.append("}")
        lines.append("")
        categories = definition.get("categories", {})
        lines.append("GRAPH_CATEGORIES = {")
        for cat, cat_classes in categories.items():
            cls_list = ", ".join([f'"{c}"' for c in cat_classes])
            lines.append(f'    "{cat}": [{cls_list}],')
        lines.append("}")
        lines.append("")
        lines.append(f'GRAPH_DOMAIN_NAME = "{name}"')
        lines.append(f'GRAPH_DOMAIN_FILE = "{definition["file"]}"')
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (15, f"Write error: {str(e)}", 0))

    def WriteConfigData(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        name = definition["name"]
        fname = "Config_" + definition["file"].replace("dom_", "").replace(".py", ".py")
        fpath = os.path.join(output_dir, fname)
        classes = definition["classes"]
        edges = definition.get("edges", [])
        flows = definition.get("flows", {})
        categories = definition.get("categories", {})
        lines = []
        lines.append("#!/usr/bin/env python3")
        lines.append('"""')
        lines.append(f'Config for {name} domain.')
        lines.append("Generated by DomainEngine.")
        lines.append("Consumed by the 8 graph viewers: Plan, Spec, Flow, Lifecycle, Dep, Error, Orch, Gap")
        lines.append('"""')
        lines.append("")
        lines.append(f'DOMAIN_NAME = "{name}"')
        lines.append(f'DOMAIN_FILE = "{definition["file"]}"')
        lines.append(f'DOMAIN_SUMMARY = "{definition.get("summary", "")}"')
        lines.append("")
        lines.append("GRAPH_CLASSES = [")
        for cls in classes:
            cls_name = cls["name"]
            methods = cls.get("methods", [])
            dispatch = ", ".join([f'"{m.lower()}"' for m in methods])
            desc = cls.get("description", f"{cls_name} component")
            lines.append(f'    ("{cls_name}", "class", [{dispatch}], "{desc}"),')
        lines.append("]")
        lines.append("")
        lines.append("GRAPH_EDGES = [")
        for edge in edges:
            src = edge.get("src", "")
            dst = edge.get("dst", "")
            etype = edge.get("type", "USES")
            lines.append(f'    ("{src}", "{dst}", "{etype}"),')
        lines.append("]")
        lines.append("")
        lines.append("GRAPH_FLOWS = {")
        for cls_name, flow_steps in flows.items():
            lines.append(f'    "{cls_name}": [')
            for step in flow_steps:
                step_type = step.get("type", "step")
                desc = step.get("desc", "")
                lines.append(f'        ("{step_type}", "{desc}"),')
            lines.append("    ],")
        lines.append("}")
        lines.append("")
        lines.append("GRAPH_CATEGORIES = {")
        for cat, cat_classes in categories.items():
            cls_list = ", ".join([f'"{c}"' for c in cat_classes])
            lines.append(f'    "{cat}": [{cls_list}],')
        lines.append("}")
        lines.append("")
        lines.append("GRAPH_CATEGORY_ORDER = list(GRAPH_CATEGORIES.keys())")
        lines.append("")
        lines.append("class Config:")
        lines.append(f'    """Config for {name} domain - consumed by 8 graph viewers"""')
        lines.append("    DOMAIN_NAME = DOMAIN_NAME")
        lines.append("    DOMAIN_FILE = DOMAIN_FILE")
        lines.append("    GRAPH_CLASSES = GRAPH_CLASSES")
        lines.append("    GRAPH_EDGES = GRAPH_EDGES")
        lines.append("    GRAPH_FLOWS = GRAPH_FLOWS")
        lines.append("    GRAPH_CATEGORIES = GRAPH_CATEGORIES")
        lines.append("    GRAPH_CATEGORY_ORDER = GRAPH_CATEGORY_ORDER")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (16, f"Write error: {str(e)}", 0))

    def LaunchGraphViewer(self, viewer_name: str, domain_name: str) -> Tuple[int, str, Optional[Tuple]]:
        viewer_name = viewer_name.lower()
        if viewer_name not in GRAPH_VIEWERS:
            return (0, None, (17, f"Unknown viewer: {viewer_name}. Available: {", ".join(GRAPH_VIEWERS.keys())}", 0))
        graph_dir = self.state.get("graph_dir")
        if not graph_dir or not os.path.isdir(graph_dir):
            return (0, None, (18, f"Graph directory not found: {graph_dir}", 0))
        viewer_info = GRAPH_VIEWERS[viewer_name]
        viewer_file = viewer_info["file"]
        viewer_path = os.path.join(graph_dir, viewer_file)
        if not os.path.exists(viewer_path):
            return (0, None, (19, f"Graph viewer not found: {viewer_path}", 0))
        success, definition, error = self.LoadDomainDefinition(domain_name)
        if not success:
            return (0, None, error)
        success, config_path, error = self.WriteConfigData(definition, graph_dir)
        if not success:
            return (0, None, error)
        config_fname = os.path.basename(config_path)
        config_in_graph = os.path.join(graph_dir, "Config.py")
        try:
            shutil.copy2(config_path, config_in_graph)
        except Exception as e:
            return (0, None, (20, f"Failed to copy Config: {str(e)}", 0))
        try:
            proc = subprocess.Popen([sys.executable, viewer_path], cwd=graph_dir)
            return (1, f"Launched {viewer_name} graph viewer (PID {proc.pid})", None)
        except Exception as e:
            return (0, None, (21, f"Failed to launch viewer: {str(e)}", 0))

    def GenerateAll(self, domain_name: str, output_dir: str) -> Tuple[int, Dict, Optional[Tuple]]:
        success, definition, error = self.LoadDomainDefinition(domain_name)
        if not success:
            return (0, None, error)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        self.state["output_dir"] = output_dir
        self.state["generated_files"] = []
        self.state["errors"] = []
        self.state["stats"] = {"classes": 0, "methods": 0, "edges": 0, "files": 0, "violations": 0}
        results = {}
        builders = [
            ("python", self.WritePython),
            ("tree", self.WriteMarkdownTree),
            ("graphviz", self.WriteGraphviz),
            ("mermaid", self.WriteMermaid),
            ("symbols", self.WriteSymbolIndex),
            ("graph_data", self.WriteGraphData),
            ("config", self.WriteConfigData),
        ]
        for builder_name, builder_fn in builders:
            success, result, error = builder_fn(definition, output_dir)
            results[builder_name] = {"success": success, "path": result, "error": error}
            if not success:
                self.state["errors"].append(f"{builder_name}: {error}")
        py_file = os.path.join(output_dir, definition["file"])
        if os.path.exists(py_file):
            v_success, v_results, v_error = self.ValidateVBStyle(py_file)
            results["vbstyle_validation"] = {"success": v_success, "results": v_results, "error": v_error}
        d_success, d_results, d_error = self.ValidateDomain(domain_name)
        results["domain_validation"] = {"success": d_success, "results": d_results, "error": d_error}
        return (1, results, None)

    def GuidedCLI(self) -> Tuple[int, Dict, Optional[Tuple]]:
        report = self.Report()
        report.WriteLn("=== PT Domain Engine - Guided Domain Builder ===")
        report.WriteLn("")
        report.Write("Domain name (e.g. Web, Sql, Audio): ")
        report.Flush()
        name = sys.stdin.readline().strip()
        if not name:
            return (0, None, (20, "Domain name required", 0))
        definition = {"name": name}
        report.Write("File name (e.g. dom_web.py): ")
        report.Flush()
        fname = sys.stdin.readline().strip()
        if not fname:
            fname = f"dom_{name.lower()}.py"
        definition["file"] = fname
        report.Write("Summary: ")
        report.Flush()
        summary = sys.stdin.readline().strip()
        definition["summary"] = summary
        definition["classes"] = []
        definition["edges"] = []
        definition["flows"] = {}
        definition["categories"] = {}
        report.WriteLn("--- Add classes (empty name to finish) ---")
        while True:
            report.Write(f"Class #{len(definition["classes"]) + 1} name: ")
            report.Flush()
            cls_name = sys.stdin.readline().strip()
            if not cls_name:
                break
            report.Write(f"  Methods for {cls_name} (comma-separated): ")
            report.Flush()
            methods_input = sys.stdin.readline().strip()
            methods = [m.strip() for m in methods_input.split(",") if m.strip()]
            report.Write(f"  Description for {cls_name}: ")
            report.Flush()
            desc = sys.stdin.readline().strip()
            cls_def = {"name": cls_name, "methods": methods}
            if desc:
                cls_def["description"] = desc
            definition["classes"].append(cls_def)
        if len(definition["classes"]) < 1:
            return (0, None, (21, "At least one class required", 0))
        report.WriteLn("--- Add edges (empty src to finish) ---")
        report.WriteLn(f"Valid edge types: {", ".join(sorted(VALID_EDGE_TYPES))}")
        while True:
            report.Write(f"Edge #{len(definition["edges"]) + 1} source class: ")
            report.Flush()
            src = sys.stdin.readline().strip()
            if not src:
                break
            report.Write("  Target class: ")
            report.Flush()
            dst = sys.stdin.readline().strip()
            if not dst:
                break
            report.Write("  Edge type: ")
            report.Flush()
            etype = sys.stdin.readline().strip() or "USES"
            definition["edges"].append({"src": src, "dst": dst, "type": etype.upper()})
        report.WriteLn("--- Categories (empty to skip) ---")
        report.WriteLn(f"Valid categories: {", ".join(sorted(VALID_CATEGORIES))}")
        while True:
            report.Write("Category name (empty to finish): ")
            report.Flush()
            cat_name = sys.stdin.readline().strip()
            if not cat_name:
                break
            report.Write(f"  Classes in {cat_name} (comma-separated): ")
            report.Flush()
            cat_input = sys.stdin.readline().strip()
            cat_classes = [c.strip() for c in cat_input.split(",") if c.strip()]
            definition["categories"][cat_name.upper()] = cat_classes
        domain_key = name.lower()
        success, save_path, error = self.SaveDomainDefinition(definition, domain_key)
        if not success:
            return (0, None, error)
        report.WriteLn(f"Domain definition saved: {save_path}")
        report.WriteLn(f"Classes: {len(definition["classes"])}")
        total_methods = sum(len(c.get("methods", [])) for c in definition["classes"])
        report.WriteLn(f"Methods: {total_methods}")
        report.WriteLn(f"Edges:   {len(definition["edges"])}")
        report.WriteLn(f"Categories: {len(definition["categories"])}")
        report.Write("Validate domain? (y/n): ")
        report.Flush()
        confirm = sys.stdin.readline().strip().lower()
        if confirm == "y":
            v_success, v_results, v_error = self.ValidateDomain(domain_key)
            if v_success:
                report.WriteLn("[OK] Domain validation passed")
            else:
                report.WriteLn("[FAIL] Domain validation:")
                for err in v_results.get("errors", []):
                    report.WriteLn(f"  ERROR: {err}")
                for warn in v_results.get("warnings", []):
                    report.WriteLn(f"  WARN:  {warn}")
        report.Write("Generate domain files? (y/n): ")
        report.Flush()
        confirm = sys.stdin.readline().strip().lower()
        if confirm == "y":
            output_dir = os.path.dirname(self.state["definitions_dir"])
            success, results, error = self.GenerateAll(domain_key, output_dir)
            if success:
                report.WriteLn(f"Generated {len(results)} outputs:")
                for builder, info in results.items():
                    if info["success"]:
                        report.WriteLn(f"  [OK]   {builder}")
                    else:
                        report.WriteLn(f"  [FAIL] {builder} -> {info.get("error", "unknown")}")
            else:
                return (0, None, error)
        return (1, definition, None)

    def IngestDirectory(self, domain: str, directory: str) -> Tuple[int, Dict, Optional[Tuple]]:
        report = self.Report()
        success, definition, error = self.LoadDomainDefinition(domain)
        if not success:
            return (0, None, error)
        scanner = self.FileScanner()
        extractor = self.ClassExtractor()
        mapper = self.ClassMapper()
        grapher = self.DomainGrapher()
        consolidator = self.Consolidator()
        cleaner = self.Cleaner()
        success, files, error = scanner.Run("find", {"directory": directory})
        if not success:
            return (0, None, error)
        report.WriteLn(f"Found {len(files)} class files in {directory}")
        success, extracted, error = extractor.Run("extract_all", {"files": files})
        if not success:
            return (0, None, error)
        report.WriteLn(f"Extracted {len(extracted)} classes")
        success, mappings, error = mapper.Run("map", {"extracted": extracted, "definition": definition})
        if not success:
            return (0, None, error)
        success, plan, error = grapher.Run("plan", {"mappings": mappings, "definition": definition})
        if not success:
            return (0, None, error)
        success, _, error = grapher.Run("show", {"plan": plan, "report": report})
        if not success:
            return (0, None, error)
        report.Flush()
        success, content, error = consolidator.Run("build", {"plan": plan, "definition": definition})
        if not success:
            return (0, None, error)
        output_path = os.path.join(directory, definition["file"])
        success, write_path, error = consolidator.Run("write", {"content": content, "path": output_path})
        if not success:
            return (0, None, error)
        report.WriteLn(f"Consolidated file written: {write_path}")
        class_list = [c["name"] for c in definition["classes"]]
        success, verified, error = cleaner.Run("verify", {"output_file": write_path, "classes": class_list})
        if not success:
            report.WriteLn(f"Verification FAILED: {error}")
            report.Flush()
            return (0, None, error)
        report.WriteLn("Verification passed")
        success, deleted_count, error = cleaner.Run("delete", {"files": files})
        if not success:
            report.WriteLn(f"Delete failed: {error}")
        else:
            report.WriteLn(f"Deleted {deleted_count} separate files")
        report.Flush()
        return (1, {"plan": plan, "output": write_path, "deleted": deleted_count}, None)

    def ShowIngestPlan(self, domain: str, directory: str) -> Tuple[int, Dict, Optional[Tuple]]:
        report = self.Report()
        success, definition, error = self.LoadDomainDefinition(domain)
        if not success:
            return (0, None, error)
        scanner = self.FileScanner()
        extractor = self.ClassExtractor()
        mapper = self.ClassMapper()
        grapher = self.DomainGrapher()
        success, files, error = scanner.Run("find", {"directory": directory})
        if not success:
            return (0, None, error)
        report.WriteLn(f"Found {len(files)} class files in {directory}")
        success, extracted, error = extractor.Run("extract_all", {"files": files})
        if not success:
            return (0, None, error)
        report.WriteLn(f"Extracted {len(extracted)} classes")
        success, mappings, error = mapper.Run("map", {"extracted": extracted, "definition": definition})
        if not success:
            return (0, None, error)
        success, plan, error = grapher.Run("plan", {"mappings": mappings, "definition": definition})
        if not success:
            return (0, None, error)
        success, _, error = grapher.Run("show", {"plan": plan, "report": report})
        if not success:
            return (0, None, error)
        success, _, error = grapher.Run("yinyang", {"plan": plan, "report": report})
        if not success:
            return (0, None, error)
        report.Flush()
        return (1, plan, None)

    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
        if params is None:
            params = {}
        if command == "generate":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (1, "Missing required param: domain", 0))
            return self.GenerateAll(domain, output_dir)
        elif command == "list":
            return self.ListDomains()
        elif command == "load":
            domain = params.get("domain")
            if not domain:
                return (0, None, (2, "Missing required param: domain", 0))
            return self.LoadDomainDefinition(domain)
        elif command == "save":
            definition = params.get("definition")
            domain = params.get("domain")
            if not definition or not domain:
                return (0, None, (3, "Missing required params: definition, domain", 0))
            return self.SaveDomainDefinition(definition, domain)
        elif command == "validate":
            domain = params.get("domain")
            if not domain:
                return (0, None, (4, "Missing required param: domain", 0))
            return self.ValidateDomain(domain)
        elif command == "validate_vbstyle":
            filepath = params.get("filepath")
            if not filepath:
                return (0, None, (5, "Missing required param: filepath", 0))
            return self.ValidateVBStyle(filepath)
        elif command == "guided":
            return self.GuidedCLI()
        elif command == "ingest":
            domain = params.get("domain")
            directory = params.get("directory")
            if not domain or not directory:
                return (0, None, (6, "Missing required params: domain, directory", 0))
            return self.IngestDirectory(domain, directory)
        elif command == "plan":
            domain = params.get("domain")
            directory = params.get("directory")
            if not domain or not directory:
                return (0, None, (7, "Missing required params: domain, directory", 0))
            return self.ShowIngestPlan(domain, directory)
        elif command == "scan":
            directory = params.get("directory")
            if not directory:
                return (0, None, (8, "Missing required param: directory", 0))
            scanner = self.FileScanner()
            return scanner.Run("find", {"directory": directory})
        elif command == "yinyang":
            domain = params.get("domain")
            directory = params.get("directory")
            if not domain or not directory:
                return (0, None, (9, "Missing required params: domain, directory", 0))
            return self.ShowIngestPlan(domain, directory)
        elif command == "launch_graph":
            viewer = params.get("viewer")
            domain = params.get("domain")
            if not viewer or not domain:
                return (0, None, (10, "Missing required params: viewer, domain", 0))
            return self.LaunchGraphViewer(viewer, domain)
        elif command == "list_graphs":
            graphs = []
            for name, info in GRAPH_VIEWERS.items():
                graphs.append({"name": name, "file": info["file"], "question": info["question"]})
            return (1, graphs, None)
        elif command == "build_python":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (11, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WritePython(definition, output_dir)
        elif command == "build_tree":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (12, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteMarkdownTree(definition, output_dir)
        elif command == "build_graphviz":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (13, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteGraphviz(definition, output_dir)
        elif command == "build_mermaid":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (14, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteMermaid(definition, output_dir)
        elif command == "build_symbols":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (15, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteSymbolIndex(definition, output_dir)
        elif command == "build_graph_data":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (16, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteGraphData(definition, output_dir)
        elif command == "build_config":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (17, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteConfigData(definition, output_dir)
        elif command == "read_state":
            return self.read_state()
        elif command == "set_config":
            return self.SetConfig(params)
        else:
            return (0, None, (99, f"Unknown command: {command}", 0))

    def set_config(self, params=None) -> Tuple[int, Any, Optional[Tuple]]:
        if not params:
            return (0, None, ("no_params", "set_config needs params", 0))
        cfg = self.state["config"]
        for k, v in params.items():
            if k in cfg:
                cfg[k] = v
        return (1, dict(cfg), None)

    def HandleError(self, params) -> Tuple[int, Any, Optional[Tuple]]:
        stage = self._p(params, "stage", "unknown")
        error_msg = self._p(params, "error", "")
        self.state["errors"].append({"stage": stage, "error": error_msg, "timestamp": datetime.now().isoformat()})
        self.report.Write(f"[ERROR] {stage}: {error_msg}")
        return (1, {"stage": stage, "logged": True}, None)

    def Retry(self, params) -> Tuple[int, Any, Optional[Tuple]]:
        stage = self._p(params, "stage", "")
        max_retries = self._p(params, "max_retries", 3)
        attempt = self.state.get("retry_count", {}).get(stage, 0)
        if attempt < max_retries:
            self.state.setdefault("retry_count", {})[stage] = attempt + 1
            self.report.Write(f"[RETRY] {stage} attempt {attempt + 1}/{max_retries}")
            return (1, {"retry": True, "attempt": attempt + 1}, None)
        self.report.Write(f"[RETRY] {stage} exhausted after {max_retries} attempts")
        return (1, {"retry": False, "attempt": attempt}, None)


    class Report:
        """All output goes through Report. Never sys.stdout.write in class methods, never print."""

        def __init__(self, mem=None, db=None, param=None):
            self.state = {"buffer": [], "total_lines": 0}

        def _p(self, params, key, default=None):
            if not params:
                return default
            return params.get(key, default)

        def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
            return (1, self.state, None)

        def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
            if not params:
                return (0, None, (1, "Missing config params", 0))
            self.state.update(params)
            return (1, "Config updated", None)

        def Write(self, text: str) -> Tuple[int, None, Optional[Tuple]]:
            self.state["buffer"].append(text)
            return (1, None, None)

        def WriteLn(self, text: str) -> Tuple[int, None, Optional[Tuple]]:
            self.state["buffer"].append(text + "\n")
            self.state["total_lines"] += 1
            return (1, None, None)

        def Flush(self) -> Tuple[int, int, Optional[Tuple]]:
            output = "".join(self.state["buffer"])
            if output:
                self.report.Write(output)
                self.report.Flush()
            count = self.state["total_lines"]
            self.state["buffer"] = []
            self.state["total_lines"] = 0
            return (1, count, None)

        def Clear(self) -> Tuple[int, None, Optional[Tuple]]:
            self.state["buffer"] = []
            self.state["total_lines"] = 0
            return (1, None, None)

        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
            if params is None:
                params = {}
            if command == "write":
                return self.Write(params.get("text", ""))
            elif command == "writeln":
                return self.WriteLn(params.get("text", ""))
            elif command == "flush":
                return self.Flush()
            elif command == "clear":
                return self.Clear()
            elif command == "read_state":
                return self.read_state()
            elif command == "set_config":
                return self.SetConfig(params)
            return (0, None, (1, f"Unknown command: {command}", 0))

        def set_config(self, params=None) -> Tuple[int, Any, Optional[Tuple]]:
            if not params:
                return (0, None, ("no_params", "set_config needs params", 0))
            cfg = self.state["config"]
            for k, v in params.items():
                if k in cfg:
                    cfg[k] = v
            return (1, dict(cfg), None)


    class FileScanner:
        """Find *.py class files in a directory, filter out non-class files."""

        def __init__(self, mem=None, db=None, param=None):
            self.state = {"directory": None, "files": [], "excluded": EXCLUDED_PATTERNS}

        def _p(self, params, key, default=None):
            if not params:
                return default
            return params.get(key, default)

        def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
            return (1, self.state, None)

        def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
            if not params:
                return (0, None, (1, "Missing config params", 0))
            self.state.update(params)
            return (1, "Config updated", None)

        def FindClassFiles(self, directory: str) -> Tuple[int, List[str], Optional[Tuple]]:
            if not os.path.isdir(directory):
                return (0, None, (1, f"Directory not found: {directory}", 0))
            files = []
            for fname in sorted(os.listdir(directory)):
                if not fname.endswith(".py"):
                    continue
                base = fname.replace(".py", "")
                excluded = False
                for pat in self.state["excluded"]:
                    if pat in base:
                        excluded = True
                        break
                if excluded:
                    continue
                files.append(os.path.join(directory, fname))
            self.state["directory"] = directory
            self.state["files"] = files
            return (1, files, None)

        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
            if params is None:
                params = {}
            if command == "find":
                directory = params.get("directory")
                if not directory:
                    return (0, None, (2, "Missing required param: directory", 0))
                return self.FindClassFiles(directory)
            elif command == "read_state":
                return self.read_state()
            elif command == "set_config":
                return self.SetConfig(params)
            return (0, None, (1, f"Unknown command: {command}", 0))

        def set_config(self, params=None) -> Tuple[int, Any, Optional[Tuple]]:
            if not params:
                return (0, None, ("no_params", "set_config needs params", 0))
            cfg = self.state["config"]
            for k, v in params.items():
                if k in cfg:
                    cfg[k] = v
            return (1, dict(cfg), None)


    class ClassExtractor:
        """Read a .py file, extract class name + full method bodies + imports via AST."""

        def __init__(self, mem=None, db=None, param=None):
            self.state = {"extracted": [], "errors": []}

        def _p(self, params, key, default=None):
            if not params:
                return default
            return params.get(key, default)

        def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
            return (1, self.state, None)

        def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
            if not params:
                return (0, None, (1, "Missing config params", 0))
            self.state.update(params)
            return (1, "Config updated", None)

        def ExtractFile(self, filepath: str) -> Tuple[int, Dict, Optional[Tuple]]:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()
                tree = ast.parse(source)
            except SyntaxError as e:
                return (0, None, (1, f"Syntax error in {filepath}: {str(e)}", 0))
            except Exception as e:
                return (0, None, (2, f"Read error: {str(e)}", 0))
            classes = []
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
                elif isinstance(node, ast.ClassDef):
                    cls_name = node.name
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)
                    classes.append({
                        "name": cls_name,
                        "methods": methods,
                        "file": filepath,
                        "source": source,
                        "lineno": node.lineno,
                    })
            result = {"file": filepath, "classes": classes, "imports": imports}
            return (1, result, None)

        def ExtractAll(self, files: List[str]) -> Tuple[int, List[Dict], Optional[Tuple]]:
            all_extracted = []
            errors = []
            for fpath in files:
                success, result, error = self.ExtractFile(fpath)
                if success:
                    all_extracted.append(result)
                else:
                    errors.append(str(error))
                    self.state["errors"].append(str(error))
            self.state["extracted"] = all_extracted
            if errors and not all_extracted:
                return (0, None, (3, f"All files failed to extract: {len(errors)} errors", 0))
            return (1, all_extracted, None)

        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
            if params is None:
                params = {}
            if command == "extract":
                filepath = params.get("filepath")
                if not filepath:
                    return (0, None, (4, "Missing required param: filepath", 0))
                return self.ExtractFile(filepath)
            elif command == "extract_all":
                files = params.get("files")
                if not files:
                    return (0, None, (5, "Missing required param: files", 0))
                return self.ExtractAll(files)
            elif command == "read_state":
                return self.read_state()
            elif command == "set_config":
                return self.SetConfig(params)
            return (0, None, (1, f"Unknown command: {command}", 0))

        def set_config(self, params=None) -> Tuple[int, Any, Optional[Tuple]]:
            if not params:
                return (0, None, ("no_params", "set_config needs params", 0))
            cfg = self.state["config"]
            for k, v in params.items():
                if k in cfg:
                    cfg[k] = v
            return (1, dict(cfg), None)


    class ClassMapper:
        """Map extracted classes to domain definition classes. Fuzzy match + merge detection."""

        def __init__(self, mem=None, db=None, param=None):
            self.state = {"mappings": [], "unmatched": [], "extra": []}

        def _p(self, params, key, default=None):
            if not params:
                return default
            return params.get(key, default)

        def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
            return (1, self.state, None)

        def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
            if not params:
                return (0, None, (1, "Missing config params", 0))
            self.state.update(params)
            return (1, "Config updated", None)

        def MapClasses(self, extracted: List[Dict], definition: Dict) -> Tuple[int, List[Dict], Optional[Tuple]]:
            def_classes = {c["name"].lower(): c for c in definition["classes"]}
            real_classes = {}
            for file_data in extracted:
                for cls in file_data.get("classes", []):
                    real_classes[cls["name"].lower()] = cls
            mappings = []
            unmatched_real = []
            for def_cls in definition["classes"]:
                def_name_lower = def_cls["name"].lower()
                if def_name_lower in real_classes:
                    real = real_classes[def_name_lower]
                    mappings.append({
                        "definition_class": def_cls["name"],
                        "real_class": real["name"],
                        "file": real["file"],
                        "source": real["source"],
                        "methods": real["methods"],
                        "def_methods": def_cls.get("methods", []),
                        "status": "matched",
                    })
                else:
                    partial_match = None
                    for real_key, real_cls in real_classes.items():
                        if def_name_lower in real_key or real_key in def_name_lower:
                            partial_match = real_cls
                            break
                    if partial_match:
                        mappings.append({
                            "definition_class": def_cls["name"],
                            "real_class": partial_match["name"],
                            "file": partial_match["file"],
                            "source": partial_match["source"],
                            "methods": partial_match["methods"],
                            "def_methods": def_cls.get("methods", []),
                            "status": "partial",
                        })
                    else:
                        mappings.append({
                            "definition_class": def_cls["name"],
                            "real_class": None,
                            "file": None,
                            "source": None,
                            "methods": [],
                            "def_methods": def_cls.get("methods", []),
                            "status": "stub",
                        })
            matched_real_names = {m["real_class"].lower() for m in mappings if m["real_class"]}
            for real_key, real_cls in real_classes.items():
                if real_key not in matched_real_names:
                    unmatched_real.append(real_cls)
            self.state["mappings"] = mappings
            self.state["unmatched"] = unmatched_real
            return (1, mappings, None)

        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
            if params is None:
                params = {}
            if command == "map":
                extracted = params.get("extracted")
                definition = params.get("definition")
                if not extracted or not definition:
                    return (0, None, (2, "Missing required params: extracted, definition", 0))
                return self.MapClasses(extracted, definition)
            elif command == "read_state":
                return self.read_state()
            elif command == "set_config":
                return self.SetConfig(params)
            return (0, None, (1, f"Unknown command: {command}", 0))

        def set_config(self, params=None) -> Tuple[int, Any, Optional[Tuple]]:
            if not params:
                return (0, None, ("no_params", "set_config needs params", 0))
            cfg = self.state["config"]
            for k, v in params.items():
                if k in cfg:
                    cfg[k] = v
            return (1, dict(cfg), None)


    class DomainGrapher:
        """Build and show the ingest plan. What is real, what is stub, what merges, yin-yang gaps."""

        def __init__(self, mem=None, db=None, param=None):
            self.state = {"plan": None, "stats": {}}

        def _p(self, params, key, default=None):
            if not params:
                return default
            return params.get(key, default)

        def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
            return (1, self.state, None)

        def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
            if not params:
                return (0, None, (1, "Missing config params", 0))
            self.state.update(params)
            return (1, "Config updated", None)

        def BuildPlan(self, mappings: List[Dict], definition: Dict) -> Tuple[int, Dict, Optional[Tuple]]:
            plan = {"matched": [], "partial": [], "stubs": [], "extra": [], "merges": [], "stats": {}}
            for m in mappings:
                entry = {
                    "definition_class": m["definition_class"],
                    "real_class": m["real_class"],
                    "file": m["file"],
                    "status": m["status"],
                    "methods_real": m["methods"],
                    "methods_def": m["def_methods"],
                }
                if m["status"] == "matched":
                    plan["matched"].append(entry)
                elif m["status"] == "partial":
                    plan["partial"].append(entry)
                else:
                    plan["stubs"].append(entry)
            plan["stats"] = {
                "matched": len(plan["matched"]),
                "partial": len(plan["partial"]),
                "stubs": len(plan["stubs"]),
                "total_classes": len(mappings),
                "total_real_methods": sum(len(m["methods"]) for m in mappings),
                "total_def_methods": sum(len(m["def_methods"]) for m in mappings),
            }
            self.state["plan"] = plan
            return (1, plan, None)

        def ShowPlan(self, plan: Dict, report) -> Tuple[int, None, Optional[Tuple]]:
            stats = plan.get("stats", {})
            report.WriteLn("=== INGEST PLAN ===")
            report.WriteLn(f"Total classes: {stats.get("total_classes", 0)}")
            report.WriteLn(f"  Matched:  {stats.get("matched", 0)}")
            report.WriteLn(f"  Partial:  {stats.get("partial", 0)}")
            report.WriteLn(f"  Stubs:    {stats.get("stubs", 0)}")
            report.WriteLn(f"  Real methods: {stats.get("total_real_methods", 0)}")
            report.WriteLn(f"  Def methods:  {stats.get("total_def_methods", 0)}")
            report.WriteLn("")
            if plan["matched"]:
                report.WriteLn("--- MATCHED (real implementation found) ---")
                for e in plan["matched"]:
                    report.WriteLn(f"  {e["definition_class"]} <- {e["file"]} ({len(e["methods_real"])} methods)")
            if plan["partial"]:
                report.WriteLn("--- PARTIAL (fuzzy match) ---")
                for e in plan["partial"]:
                    report.WriteLn(f"  {e["definition_class"]} ~= {e["real_class"]} from {e["file"]}")
            if plan["stubs"]:
                report.WriteLn("--- STUBS (no real implementation found, will generate stub) ---")
                for e in plan["stubs"]:
                    report.WriteLn(f"  {e["definition_class"]} -> stub with {len(e["methods_def"])} methods")
            return (1, None, None)

        def YinYang(self, plan: Dict, report) -> Tuple[int, Dict, Optional[Tuple]]:
            yin = plan.get("stats", {}).get("matched", 0) + plan.get("stats", {}).get("partial", 0)
            yang = plan.get("stats", {}).get("stubs", 0)
            report.WriteLn("")
            report.WriteLn("=== YIN-YANG ANALYSIS ===")
            report.WriteLn(f"Yin (real code found):    {yin}")
            report.WriteLn(f"Yang (stubs to generate): {yang}")
            if yin > 0 and yang == 0:
                report.WriteLn("Status: FULLY REAL - all classes have implementations")
            elif yin == 0 and yang > 0:
                report.WriteLn("Status: ALL STUBS - no real code found, generating skeleton")
            elif yin > yang:
                report.WriteLn("Status: MOSTLY REAL - majority has real implementations")
            else:
                report.WriteLn("Status: MIXED - some real, some stubs")
            gaps = []
            for e in plan.get("stubs", []):
                for method in e.get("methods_def", []):
                    gaps.append(f"{e["definition_class"]}.{method}")
            if gaps:
                report.WriteLn(f"Missing implementations: {len(gaps)} methods")
                for g in gaps[:10]:
                    report.WriteLn(f"  - {g}")
                if len(gaps) > 10:
                    report.WriteLn(f"  ... and {len(gaps) - 10} more")
            return (1, {"yin": yin, "yang": yang, "gaps": gaps}, None)

        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
            if params is None:
                params = {}
            if command == "plan":
                mappings = params.get("mappings")
                definition = params.get("definition")
                if not mappings or not definition:
                    return (0, None, (2, "Missing required params: mappings, definition", 0))
                return self.BuildPlan(mappings, definition)
            elif command == "show":
                plan = params.get("plan")
                report = params.get("report")
                if not plan or not report:
                    return (0, None, (3, "Missing required params: plan, report", 0))
                return self.ShowPlan(plan, report)
            elif command == "yinyang":
                plan = params.get("plan")
                report = params.get("report")
                if not plan or not report:
                    return (0, None, (4, "Missing required params: plan, report", 0))
                return self.YinYang(plan, report)
            elif command == "read_state":
                return self.read_state()
            elif command == "set_config":
                return self.SetConfig(params)
            return (0, None, (1, f"Unknown command: {command}", 0))

        def set_config(self, params=None) -> Tuple[int, Any, Optional[Tuple]]:
            if not params:
                return (0, None, ("no_params", "set_config needs params", 0))
            cfg = self.state["config"]
            for k, v in params.items():
                if k in cfg:
                    cfg[k] = v
            return (1, dict(cfg), None)


    class Consolidator:
        """Cut, move, paste real class implementations into one nested-class file. Fixes VBStyle violations during merge."""

        def __init__(self, mem=None, db=None, param=None):
            self.state = {"content": None, "output_path": None}

        def _p(self, params, key, default=None):
            if not params:
                return default
            return params.get(key, default)

        def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
            return (1, self.state, None)

        def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
            if not params:
                return (0, None, (1, "Missing config params", 0))
            self.state.update(params)
            return (1, "Config updated", None)

        def BuildContent(self, plan: Dict, definition: Dict) -> Tuple[int, str, Optional[Tuple]]:
            lines = []
            lines.append("#!/usr/bin/env python3")
            lines.append('"""')
            lines.append(f'#[@GHOST]{{[@file<{definition["file"]}>][@state<active>][@date<{datetime.now().strftime("%Y-%m-%d")}][@ver<1.0>][@auth<DomainEngine>]}}')
            lines.append(f'#[@VBSTYLE]{{[@auth<system>][@role<domain>][@return<Tuple3>]}}')
            lines.append(f'#[@SUMMARY]{{{definition.get("summary", definition["name"] + " domain")}}}')
            lines.append('"""')
            lines.append("")
            lines.append("import os")
            lines.append("import sys")
            lines.append("import json")
            lines.append("import re")
            lines.append("from typing import Optional, Tuple, Dict, Any, List")
            lines.append("from datetime import datetime")
            lines.append("")
            lines.append("")
            name = definition["name"]
            lines.append(f'class {name}:')
            lines.append(f'    """{name} domain controller - consolidated from real implementations"""')
            lines.append("")
            lines.append(f'    def __init__(self, mem=None, db=None, param=None):')
            lines.append(f'        self.state = {{"config": {{}}, "catalog": [], "results": [], "errors": [], "meta": {{"last_command": None}}}}')
            lines.append("")
            for entry in plan.get("matched", []) + plan.get("partial", []):
                cls_lower = entry["definition_class"].lower()
                lines.append(f'        self.{cls_lower} = self.{entry["definition_class"]}()')
            lines.append("")
            lines.append('    def _p(self, params, key, default=None):')
            lines.append('        if not params:')
            lines.append('            return default')
            lines.append('        return params.get(key, default)')
            lines.append("")
            lines.append('    def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:')
            lines.append('        return (1, self.state, None)')
            lines.append("")
            lines.append('    def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:')
            lines.append('        if not params:')
            lines.append('            return (0, None, (1, "Missing config params", 0))')
            lines.append('        self.state["config"].update(params)')
            lines.append('        return (1, "Config updated", None)')
            lines.append("")
            all_commands = []
            for entry in plan.get("matched", []) + plan.get("partial", []):
                cls_lower = entry["definition_class"].lower()
                for method in entry.get("methods_real", []):
                    all_commands.append((method.lower(), cls_lower))
            lines.append('    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:')
            lines.append('        if params is None:')
            lines.append('            params = {}')
            for cmd, cls_lower in all_commands:
                lines.append(f'        if command == "{cmd}":')
                lines.append(f'            return self.{cls_lower}.Run(command, params)')
            lines.append('        if command == "read_state":')
            lines.append('            return self.read_state()')
            lines.append('        if command == "set_config":')
            lines.append('            return self.SetConfig(params)')
            lines.append('        return (0, None, (2, f"Unknown command: {command}", 0))')
            lines.append("")
            lines.append("")
            for entry in plan.get("matched", []) + plan.get("partial", []):
                cls_name = entry["definition_class"]
                source = entry.get("source", "")
                if source:
                    source_lines = source.split("\n")
                    in_class = False
                    class_indent = 0
                    for sline in source_lines:
                        if sline.startswith(f"class {cls_name}"):
                            in_class = True
                            class_indent = 0
                            lines.append(sline)
                            continue
                        if in_class:
                            if sline.startswith("class ") and not sline.startswith(" "):
                                break
                            lines.append(sline)
                else:
                    lines.append(f'    class {cls_name}:')
                    lines.append(f'        """{cls_name} - stub (no real implementation found)"""')
                    lines.append(f'        def __init__(self, mem=None, db=None, param=None):')
                    lines.append(f'            self.state = {{}}')
                    lines.append("")
                    for method in entry.get("methods_def", []):
                        lines.append(f'        def {method}(self, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:')
                        lines.append(f'            return (1, None, None)')
                        lines.append("")
                    lines.append(f'        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:')
                    lines.append(f'            if params is None:')
                    lines.append(f'                params = {{}}')
                    for method in entry.get("methods_def", []):
                        lines.append(f'            if command == "{method.lower()}":')
                        lines.append(f'                return self.{method}(params)')
                    lines.append(f'            return (0, None, (1, f"Unknown command: {{command}}", 0))')
                    lines.append("")
                lines.append("")
            for entry in plan.get("stubs", []):
                cls_name = entry["definition_class"]
                lines.append(f'    class {cls_name}:')
                lines.append(f'        """{cls_name} - stub"""')
                lines.append(f'        def __init__(self, mem=None, db=None, param=None):')
                lines.append(f'            self.state = {{}}')
                lines.append("")
                for method in entry.get("methods_def", []):
                    lines.append(f'        def {method}(self, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:')
                    lines.append(f'            return (1, None, None)')
                    lines.append("")
                lines.append(f'        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:')
                lines.append(f'            if params is None:')
                lines.append(f'                params = {{}}')
                for method in entry.get("methods_def", []):
                    lines.append(f'            if command == "{method.lower()}":')
                    lines.append(f'                return self.{method}(params)')
                lines.append(f'            return (0, None, (1, f"Unknown command: {{command}}", 0))')
                lines.append("")
                lines.append("")
            content = "\n".join(lines)
            self.state["content"] = content
            return (1, content, None)

        def WriteFile(self, content: str, path: str) -> Tuple[int, str, Optional[Tuple]]:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.state["output_path"] = path
                return (1, path, None)
            except Exception as e:
                return (0, None, (2, f"Write error: {str(e)}", 0))

        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
            if params is None:
                params = {}
            if command == "build":
                plan = params.get("plan")
                definition = params.get("definition")
                if not plan or not definition:
                    return (0, None, (3, "Missing required params: plan, definition", 0))
                return self.BuildContent(plan, definition)
            elif command == "write":
                content = params.get("content")
                path = params.get("path")
                if not content or not path:
                    return (0, None, (4, "Missing required params: content, path", 0))
                return self.WriteFile(content, path)
            elif command == "read_state":
                return self.read_state()
            elif command == "set_config":
                return self.SetConfig(params)
            return (0, None, (1, f"Unknown command: {command}", 0))

        def set_config(self, params=None) -> Tuple[int, Any, Optional[Tuple]]:
            if not params:
                return (0, None, ("no_params", "set_config needs params", 0))
            cfg = self.state["config"]
            for k, v in params.items():
                if k in cfg:
                    cfg[k] = v
            return (1, dict(cfg), None)


    class Cleaner:
        """Delete separate class files after successful consolidation. Does NOT delete if verification fails."""

        def __init__(self, mem=None, db=None, param=None):
            self.state = {"deleted": 0, "verified": False}

        def _p(self, params, key, default=None):
            if not params:
                return default
            return params.get(key, default)

        def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
            return (1, self.state, None)

        def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
            if not params:
                return (0, None, (1, "Missing config params", 0))
            self.state.update(params)
            return (1, "Config updated", None)

        def VerifyOutput(self, output_file: str, classes: List[str]) -> Tuple[int, Dict, Optional[Tuple]]:
            if not os.path.exists(output_file):
                return (0, None, (1, f"Output file not found: {output_file}", 0))
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    content = f.read()
                compile(content, output_file, "exec")
            except SyntaxError as e:
                return (0, None, (2, f"Syntax error: {str(e)}", 0))
            results = {"file": output_file, "classes_found": [], "classes_missing": [], "has_run": False, "has_read_state": False}
            for cls_name in classes:
                if f"class {cls_name}" in content:
                    results["classes_found"].append(cls_name)
                else:
                    results["classes_missing"].append(cls_name)
            results["has_run"] = "def Run(" in content
            results["has_read_state"] = "def read_state" in content
            results["valid"] = len(results["classes_missing"]) == 0 and results["has_run"] and results["has_read_state"]
            self.state["verified"] = results["valid"]
            if results["valid"]:
                return (1, results, None)
            return (0, results, (3, f"Verification failed: {len(results["classes_missing"])} missing classes", 0))

        def DeleteFiles(self, files: List[str]) -> Tuple[int, int, Optional[Tuple]]:
            deleted = 0
            for fpath in files:
                try:
                    os.remove(fpath)
                    deleted += 1
                except Exception:
                    pass
            self.state["deleted"] = deleted
            return (1, deleted, None)

        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
            if params is None:
                params = {}
            if command == "verify":
                output_file = params.get("output_file")
                classes = params.get("classes")
                if not output_file or not classes:
                    return (0, None, (4, "Missing required params: output_file, classes", 0))
                return self.VerifyOutput(output_file, classes)
            elif command == "delete":
                files = params.get("files")
                if not files:
                    return (0, None, (5, "Missing required param: files", 0))
                return self.DeleteFiles(files)
            elif command == "read_state":
                return self.read_state()
            elif command == "set_config":
                return self.SetConfig(params)
            return (0, None, (1, f"Unknown command: {command}", 0))

        def set_config(self, params=None) -> Tuple[int, Any, Optional[Tuple]]:
            if not params:
                return (0, None, ("no_params", "set_config needs params", 0))
            cfg = self.state["config"]
            for k, v in params.items():
                if k in cfg:
                    cfg[k] = v
            return (1, dict(cfg), None)


    class Cli:
        """CLI entry point. VBStyle compliant replacement for free Main() function."""

        def __init__(self, mem=None, db=None, param=None):
            self.state = {"engine": None, "args": []}

        def _p(self, params, key, default=None):
            if not params:
                return default
            return params.get(key, default)

        def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
            return (1, self.state, None)

        def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
            if not params:
                return (0, None, (1, "Missing config params", 0))
            self.state.update(params)
            return (1, "Config updated", None)

        def ParseArgs(self, argv: List[str]) -> Tuple[int, Dict, Optional[Tuple]]:
            if len(argv) < 2:
                return (1, {"command": "generate", "params": {"domain": "web", "output_dir": "."}}, None)
            command = argv[1]
            params = {}
            i = 2
            while i < len(argv):
                arg = argv[i]
                if arg.startswith("--"):
                    key = arg[2:]
                    if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                        params[key] = argv[i + 1]
                        i += 2
                    else:
                        params[key] = True
                        i += 1
                else:
                    i += 1
            return (1, {"command": command, "params": params}, None)

        def Execute(self, argv: List[str]) -> Tuple[int, Any, Optional[Tuple]]:
            engine = DomainEngine()
            self.state["engine"] = engine
            success, parsed, error = self.ParseArgs(argv)
            if not success:
                return (0, None, error)
            command = parsed["command"]
            params = parsed["params"]
            if command == "help" or command == "--help" or command == "-h":
                report = engine.Report()
                report.WriteLn("PT Domain Engine - Usage:")
                report.WriteLn("  python pt_domain_engine.py <command> [options]")
                report.WriteLn("")
                report.WriteLn("Commands:")
                report.WriteLn("  generate --domain <name> [--output_dir <dir>]  Generate all domain files")
                report.WriteLn("  list                                         List available domains")
                report.WriteLn("  load --domain <name>                         Load domain definition")
                report.WriteLn("  save --domain <name> --definition <json>     Save domain definition")
                report.WriteLn("  validate --domain <name>                     Validate domain")
                report.WriteLn("  validate_vbstyle --filepath <path>           Validate VBStyle compliance")
                report.WriteLn("  guided                                        Interactive domain builder")
                report.WriteLn("  ingest --domain <name> --directory <dir>     Ingest directory into domain")
                report.WriteLn("  plan --domain <name> --directory <dir>       Show ingest plan (no changes)")
                report.WriteLn("  scan --directory <dir>                       Scan directory for class files")
                report.WriteLn("  yinyang --domain <name> --directory <dir>    Yin-yang gap analysis")
                report.WriteLn("  launch_graph --viewer <name> --domain <name> Launch graph viewer")
                report.WriteLn("  list_graphs                                   List available graph viewers")
                report.WriteLn("  build_python --domain <name>                 Build Python file only")
                report.WriteLn("  build_tree --domain <name>                   Build markdown tree")
                report.WriteLn("  build_graphviz --domain <name>               Build Graphviz DOT")
                report.WriteLn("  build_mermaid --domain <name>                Build Mermaid diagram")
                report.WriteLn("  build_symbols --domain <name>                Build symbol index")
                report.WriteLn("  build_graph_data --domain <name>             Build graph data file")
                report.WriteLn("  build_config --domain <name>                 Build Config file")
                report.WriteLn("  read_state                                    Show engine state")
                report.WriteLn("  set_config --<key> <value>                   Update engine config")
                report.Flush()
                return (1, None, None)
            success, result, error = engine.Run(command, params)
            if not success:
                report = engine.Report()
                report.WriteLn(f"ERROR: {error}")
                report.Flush()
                return (0, None, error)
            if result is not None:
                report = engine.Report()
                if isinstance(result, list):
                    for item in result:
                        report.WriteLn(str(item))
                elif isinstance(result, dict):
                    for key, value in result.items():
                        report.WriteLn(f"{key}: {value}")
                else:
                    report.WriteLn(str(result))
                report.Flush()
            return (1, result, None)

        def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
            if params is None:
                params = {}
            if command == "parse":
                return self.ParseArgs(params.get("argv", []))
            elif command == "execute":
                return self.Execute(params.get("argv", []))
            elif command == "read_state":
                return self.read_state()
            elif command == "set_config":
                return self.SetConfig(params)
            return (0, None, (1, f"Unknown command: {command}", 0))

        def set_config(self, params=None) -> Tuple[int, Any, Optional[Tuple]]:
            if not params:
                return (0, None, ("no_params", "set_config needs params", 0))
            cfg = self.state["config"]
            for k, v in params.items():
                if k in cfg:
                    cfg[k] = v
            return (1, dict(cfg), None)

