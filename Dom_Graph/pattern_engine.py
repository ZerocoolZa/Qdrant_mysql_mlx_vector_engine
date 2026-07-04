#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/pattern_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Phase 4 Section 24 Pattern Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="pattern_engine.py" domain="twin_pattern" authority="PatternEngine"}
# [@SUMMARY]{summary="Pattern authority that detects design patterns, anti-patterns, code smells and VBStyle violations and suggests improvements."}
# [@CLASS]{class="PatternEngine" domain="pattern" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="detect_patterns" type="command"}
# [@METHOD]{method="detect_antipatterns" type="command"}
# [@METHOD]{method="detect_smells" type="command"}
# [@METHOD]{method="detect_violations" type="command"}
# [@METHOD]{method="suggest_improvements" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<PatternEngine: detects design patterns anti-patterns code smells VBStyle violations suggests improvements. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No actual print() calls or decorators in code (grep matches were string literals in suggestion messages). No self._ violations.>][@todos<none>]}
"""
PatternEngine -- authority for design pattern, anti-pattern and smell detection.
Implements Section 24 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: detect_patterns, detect_antipatterns, detect_smells,
          detect_violations, suggest_improvements.
"""
import ast
import json
import os
import re
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
GOD_CLASS_THRESHOLD = 20
LONG_METHOD_THRESHOLD = 50
DEEP_NESTING_THRESHOLD = 4


class PatternEngine:
    """Authority for detecting patterns, anti-patterns, smells and violations."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "god_class_threshold": GOD_CLASS_THRESHOLD,
                "long_method_threshold": LONG_METHOD_THRESHOLD,
                "deep_nesting_threshold": DEEP_NESTING_THRESHOLD,
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "detect_patterns":
            return self.DetectPatterns(params)
        elif command == "detect_antipatterns":
            return self.DetectAntipatterns(params)
        elif command == "detect_smells":
            return self.DetectSmells(params)
        elif command == "detect_violations":
            return self.DetectViolations(params)
        elif command == "suggest_improvements":
            return self.SuggestImprovements(params)
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

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]

    def SafeParse(self, code):
        if not code:
            return None
        try:
            return ast.parse(code)
        except SyntaxError:
            return None

    def DetectPatterns(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT class_id, class_name, method_count, properties, fields "
            "FROM classes ORDER BY class_id LIMIT ?",
            (limit,),
        )
        classes = cur.fetchall()
        cur.execute(
            "SELECT method_id, class_id, method_name, method_code "
            "FROM methods WHERE method_code IS NOT NULL ORDER BY method_id"
        )
        methods = cur.fetchall()
        method_by_class = {}
        method_names_by_class = {}
        for method_id, class_id, method_name, code in methods:
            method_by_class.setdefault(class_id, []).append(
                {"method_id": method_id, "method_name": method_name, "code": code}
            )
            method_names_by_class.setdefault(class_id, set()).add(method_name.lower())
        patterns = []
        for class_id, class_name, method_count, properties, fields in classes:
            names = method_names_by_class.get(class_id, set())
            if self.IsMatchSingleton(names):
                patterns.append(
                    {
                        "pattern": "Singleton",
                        "class_id": class_id,
                        "class_name": class_name,
                        "evidence": "instance/get_instance method present",
                    }
                )
            if self.IsMatchFactory(method_by_class.get(class_id, [])):
                patterns.append(
                    {
                        "pattern": "Factory",
                        "class_id": class_id,
                        "class_name": class_name,
                        "evidence": "method creates instances of other classes",
                    }
                )
            if self.IsMatchObserver(names):
                patterns.append(
                    {
                        "pattern": "Observer",
                        "class_id": class_id,
                        "class_name": class_name,
                        "evidence": "register/notify methods present",
                    }
                )
            if self.IsMatchStrategy(names, method_by_class.get(class_id, [])):
                patterns.append(
                    {
                        "pattern": "Strategy",
                        "class_id": class_id,
                        "class_name": class_name,
                        "evidence": "execute/strategy methods with interchangeable behavior",
                    }
                )
            if self.IsMatchAdapter(names, method_by_class.get(class_id, [])):
                patterns.append(
                    {
                        "pattern": "Adapter",
                        "class_id": class_id,
                        "class_name": class_name,
                        "evidence": "wraps/adapts interface of another class",
                    }
                )
            if self.IsMatchCommand(names):
                patterns.append(
                    {
                        "pattern": "Command",
                        "class_id": class_id,
                        "class_name": class_name,
                        "evidence": "execute/undo methods present",
                    }
                )
        report = {"pattern_count": len(patterns), "patterns": patterns}
        self.state["results"].append(report)
        return (1, report, None)

    def IsMatchSingleton(self, names):
        if "getinstance" in names or "get_instance" in names:
            return True
        if "instance" in names and "shared" in names:
            return True
        return False

    def IsMatchFactory(self, methods):
        for entry in methods:
            code = entry.get("code", "") or ""
            if "create" in entry.get("method_name", "").lower():
                tree = self.SafeParse(code)
                if tree is None:
                    if "return " in code and "(" in code:
                        return True
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(
                        node.func, ast.Name
                    ):
                        if node.func.id and node.func.id[0].isupper():
                            return True
        return False

    def IsMatchObserver(self, names):
        has_register = any("register" in n for n in names)
        has_notify = any("notify" in n for n in names)
        has_subscribe = any("subscribe" in n for n in names)
        return (has_register and has_notify) or (has_subscribe and has_notify)

    def IsMatchStrategy(self, names, methods):
        has_execute = any("execute" in n for n in names)
        has_strategy = any("strategy" in n for n in names)
        has_set = any(n.startswith("set") for n in names)
        if has_execute and (has_strategy or has_set):
            return True
        if has_strategy and has_set:
            return True
        return False

    def IsMatchAdapter(self, names, methods):
        has_adapt = any("adapt" in n for n in names)
        has_wrap = any("wrap" in n for n in names)
        if has_adapt or has_wrap:
            return True
        for entry in methods:
            code = entry.get("code", "") or ""
            tree = self.SafeParse(code)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    if node.value.id == "self" and node.attr in ("adaptee", "wrapped", "inner", "target"):
                        return True
        return False

    def IsMatchCommand(self, names):
        has_execute = any("execute" in n for n in names)
        has_undo = any("undo" in n for n in names)
        has_redo = any("redo" in n for n in names)
        return has_execute and (has_undo or has_redo)

    def DetectAntipatterns(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        god_threshold = self.state["config"]["god_class_threshold"]
        long_threshold = self.state["config"]["long_method_threshold"]
        deep_threshold = self.state["config"]["deep_nesting_threshold"]
        conn = self.Connect()
        cur = conn.cursor()
        antipatterns = []
        cur.execute(
            "SELECT class_id, class_name, method_count FROM classes "
            "WHERE method_count > ? ORDER BY method_count DESC LIMIT ?",
            (god_threshold, limit),
        )
        for class_id, class_name, method_count in cur.fetchall():
            antipatterns.append(
                {
                    "antipattern": "GodClass",
                    "class_id": class_id,
                    "class_name": class_name,
                    "method_count": method_count,
                    "threshold": god_threshold,
                }
            )
        cur.execute(
            "SELECT method_id, class_id, method_name, line_count, method_code "
            "FROM methods WHERE line_count > ? ORDER BY line_count DESC LIMIT ?",
            (long_threshold, limit),
        )
        for method_id, class_id, method_name, line_count, code in cur.fetchall():
            antipatterns.append(
                {
                    "antipattern": "LongMethod",
                    "method_id": method_id,
                    "class_id": class_id,
                    "method_name": method_name,
                    "line_count": line_count,
                    "threshold": long_threshold,
                }
            )
        cur.execute(
            "SELECT method_id, class_id, method_name, method_code FROM methods "
            "WHERE method_code IS NOT NULL LIMIT ?",
            (limit,),
        )
        for method_id, class_id, method_name, code in cur.fetchall():
            depth = self.MaxNestingDepth(code)
            if depth >= deep_threshold:
                antipatterns.append(
                    {
                        "antipattern": "DeepNesting",
                        "method_id": method_id,
                        "class_id": class_id,
                        "method_name": method_name,
                        "depth": depth,
                        "threshold": deep_threshold,
                    }
                )
        feature_envy = self.DetectFeatureEnvy(limit)
        antipatterns.extend(feature_envy)
        report = {"antipattern_count": len(antipatterns), "antipatterns": antipatterns}
        self.state["results"].append(report)
        return (1, report, None)

    def DetectFeatureEnvy(self, limit):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, class_id, method_name, method_code FROM methods "
            "WHERE method_code IS NOT NULL AND method_code != '' LIMIT ?",
            (limit * 3,),
        )
        feature_envy = []
        for method_id, class_id, method_name, code in cur.fetchall():
            tree = self.SafeParse(code)
            if tree is None:
                continue
            self_attr_count = 0
            foreign_attr_count = 0
            foreign_targets = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        if node.value.id == "self":
                            self_attr_count += 1
                        else:
                            foreign_attr_count += 1
                            foreign_targets[node.value.id] = foreign_targets.get(node.value.id, 0) + 1
            if foreign_attr_count > self_attr_count and foreign_attr_count >= 3:
                top_target = max(foreign_targets, key=foreign_targets.get)
                feature_envy.append({
                    "antipattern": "FeatureEnvy",
                    "method_id": method_id,
                    "class_id": class_id,
                    "method_name": method_name,
                    "self_attr_count": self_attr_count,
                    "foreign_attr_count": foreign_attr_count,
                    "envy_target": top_target,
                })
            if len(feature_envy) >= limit:
                break
        return feature_envy

    def MaxNestingDepth(self, code):
        tree = self.SafeParse(code)
        if tree is None:
            lines = code.splitlines()
            max_indent = 0
            for line in lines:
                stripped = line.lstrip(" ")
                if not stripped or stripped.startswith("#"):
                    continue
                indent = len(line) - len(stripped)
                depth = indent // 4
                if depth > max_indent:
                    max_indent = depth
            return max_indent

        def Walk(node, depth):
            max_depth = depth
            for child in ast.iter_child_nodes(node):
                if isinstance(
                    child,
                    (
                        ast.If,
                        ast.For,
                        ast.While,
                        ast.With,
                        ast.Try,
                        ast.ExceptHandler,
                    ),
                ):
                    child_depth = Walk(child, depth + 1)
                else:
                    child_depth = Walk(child, depth)
                if child_depth > max_depth:
                    max_depth = child_depth
            return max_depth

        return Walk(tree, 0)

    def DetectSmells(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        long_param_threshold = self._p(params, "long_param_threshold", 5)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, class_id, file_id, method_name, has_print, "
            "has_decorator, has_self_underscore, line_count, parameters, method_code "
            "FROM methods WHERE has_print=1 OR has_decorator=1 OR "
            "has_self_underscore=1 ORDER BY method_id LIMIT ?",
            (limit,),
        )
        smells = []
        for row in cur.fetchall():
            smells.append(
                {
                    "method_id": row[0],
                    "class_id": row[1],
                    "file_id": row[2],
                    "method_name": row[3],
                    "has_print": bool(row[4]),
                    "has_decorator": bool(row[5]),
                    "has_self_underscore": bool(row[6]),
                    "line_count": row[7],
                    "smell_type": "vbstyle_violation",
                }
            )
        cur.execute(
            "SELECT method_id, class_id, method_name, parameters, method_code "
            "FROM methods WHERE parameters IS NOT NULL AND parameters != '' "
            "ORDER BY method_id LIMIT ?",
            (limit * 3,),
        )
        for method_id, class_id, method_name, params_json, code in cur.fetchall():
            param_count = 0
            if params_json:
                try:
                    parsed = json.loads(params_json)
                    if isinstance(parsed, list):
                        param_count = len(parsed)
                    elif isinstance(parsed, dict):
                        param_count = len(parsed)
                except (ValueError, TypeError):
                    pass
            if param_count < long_param_threshold:
                tree = self.SafeParse(code)
                if tree is not None:
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef) and node.name == method_name:
                            param_count = len(node.args.args) + len(node.args.kwonlyargs)
                            break
            if param_count >= long_param_threshold:
                smells.append({
                    "method_id": method_id,
                    "class_id": class_id,
                    "method_name": method_name,
                    "param_count": param_count,
                    "threshold": long_param_threshold,
                    "smell_type": "long_parameter_list",
                })
        report = {"smell_count": len(smells), "smells": smells}
        self.state["results"].append(report)
        return (1, report, None)

    def DetectViolations(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        violations = []
        cur.execute(
            "SELECT method_id, class_id, method_name, is_vbstyle, returns_tuple3 "
            "FROM methods WHERE is_vbstyle=1 AND "
            "(returns_tuple3=0 OR method_name != 'Run') LIMIT ?",
            (limit,),
        )
        for row in cur.fetchall():
            violations.append(
                {
                    "type": "MethodVBStyleIncomplete",
                    "method_id": row[0],
                    "class_id": row[1],
                    "method_name": row[2],
                    "is_vbstyle": bool(row[3]),
                    "returns_tuple3": bool(row[4]),
                    "has_run_method": row[2] == "Run",
                }
            )
        cur.execute(
            "SELECT class_id, class_name, is_vbstyle, has_run_method "
            "FROM classes WHERE is_vbstyle=1 AND has_run_method=0 LIMIT ?",
            (limit,),
        )
        for row in cur.fetchall():
            violations.append(
                {
                    "type": "ClassMissingRun",
                    "class_id": row[0],
                    "class_name": row[1],
                    "is_vbstyle": bool(row[2]),
                    "has_run_method": bool(row[3]),
                }
            )
        report = {"violation_count": len(violations), "violations": violations}
        self.state["results"].append(report)
        return (1, report, None)

    def SuggestImprovements(self, params):
        violations = self.DetectViolations(params)[1]
        smells = self.DetectSmells(params)[1]
        antipatterns = self.DetectAntipatterns(params)[1]
        suggestions = []
        for v in violations.get("violations", []):
            if v["type"] == "MethodVBStyleIncomplete":
                suggestions.append(
                    {
                        "target": "method:" + str(v.get("method_id")),
                        "suggestion": "Method marked VBStyle but missing Tuple3 returns or Run dispatch; complete VBStyle contract.",
                        "priority": "high",
                    }
                )
            elif v["type"] == "ClassMissingRun":
                suggestions.append(
                    {
                        "target": "class:" + str(v.get("class_id")),
                        "suggestion": "Class marked VBStyle but has no Run dispatch method; add Run(self, command, params=None).",
                        "priority": "high",
                    }
                )
        for s in smells.get("smells", []):
            if s["has_print"]:
                suggestions.append(
                    {
                        "target": "method:" + str(s["method_id"]),
                        "suggestion": "Method contains print(); remove print statements per VBStyle rules.",
                        "priority": "medium",
                    }
                )
            if s["has_decorator"]:
                suggestions.append(
                    {
                        "target": "method:" + str(s["method_id"]),
                        "suggestion": "Method uses decorators; remove @staticmethod/@property/@classmethod per VBStyle rules.",
                        "priority": "medium",
                    }
                )
            if s["has_self_underscore"]:
                suggestions.append(
                    {
                        "target": "method:" + str(s["method_id"]),
                        "suggestion": "Method uses self._ attributes; convert to self.state dict entries.",
                        "priority": "medium",
                    }
                )
        for a in antipatterns.get("antipatterns", []):
            if a["antipattern"] == "GodClass":
                suggestions.append(
                    {
                        "target": "class:" + str(a["class_id"]),
                        "suggestion": "God class with " + str(a["method_count"]) + " methods; split into smaller authorities.",
                        "priority": "high",
                    }
                )
            elif a["antipattern"] == "LongMethod":
                suggestions.append(
                    {
                        "target": "method:" + str(a["method_id"]),
                        "suggestion": "Long method with " + str(a["line_count"]) + " lines; extract helper methods.",
                        "priority": "medium",
                    }
                )
            elif a["antipattern"] == "DeepNesting":
                suggestions.append(
                    {
                        "target": "method:" + str(a["method_id"]),
                        "suggestion": "Deep nesting depth " + str(a["depth"]) + "; flatten with early returns or guard clauses.",
                        "priority": "medium",
                    }
                )
            elif a["antipattern"] == "FeatureEnvy":
                suggestions.append(
                    {
                        "target": "method:" + str(a["method_id"]),
                        "suggestion": "Feature envy: method accesses " + str(a["foreign_attr_count"]) + " foreign attributes vs " + str(a["self_attr_count"]) + " self; move method to " + str(a.get("envy_target", "target")) + " class.",
                        "priority": "high",
                    }
                )
        for s in smells.get("smells", []):
            if s.get("smell_type") == "long_parameter_list":
                suggestions.append(
                    {
                        "target": "method:" + str(s["method_id"]),
                        "suggestion": "Long parameter list: " + str(s["param_count"]) + " parameters (threshold " + str(s["threshold"]) + "); introduce a parameter object.",
                        "priority": "medium",
                    }
                )
        report = {"suggestion_count": len(suggestions), "suggestions": suggestions}
        self.state["results"].append(report)
        return (1, report, None)
