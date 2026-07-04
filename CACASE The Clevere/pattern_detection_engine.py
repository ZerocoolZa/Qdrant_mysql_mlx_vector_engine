#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/pattern_detection_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 24: Pattern Detection -- 7 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="pattern_detection_engine.py" domain="twin_pattern" authority="PatternDetectionEngine"}
# [@SUMMARY]{summary="Pattern detection authority: detect design patterns, anti-patterns, code smells, architecture rules, user rules, violations, suggest improvements."}
# [@CLASS]{class="PatternDetectionEngine" domain="pattern" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="detect_design_patterns" type="command"}
# [@METHOD]{method="detect_anti_patterns" type="command"}
# [@METHOD]{method="detect_code_smells" type="command"}
# [@METHOD]{method="detect_naming_patterns" type="command"}
# [@METHOD]{method="detect_architecture_rules" type="command"}
# [@METHOD]{method="detect_user_rules" type="command"}
# [@METHOD]{method="detect_violations" type="command"}
# [@METHOD]{method="suggest_improvements" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import re
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class PatternDetectionEngine:
    """Authority for detecting patterns and suggesting improvements."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
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
        if command == "detect_design_patterns":
            return self.DetectDesignPatterns(params)
        elif command == "detect_anti_patterns":
            return self.DetectAntiPatterns(params)
        elif command == "detect_code_smells":
            return self.DetectCodeSmells(params)
        elif command == "detect_naming_patterns":
            return self.DetectNamingPatterns(params)
        elif command == "detect_architecture_rules":
            return self.DetectArchitectureRules(params)
        elif command == "detect_user_rules":
            return self.DetectUserRules(params)
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
        return (1, self.state["db_conn"], None)

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def DetectDesignPatterns(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        patterns = []
        try:
            cur.execute("SELECT class_id, class_name, method_count, parent, bcl FROM classes")
            for row in cur.fetchall():
                cid, cname, mcount, parent, bcl = row
                if mcount and mcount == 1:
                    cur.execute("SELECT method_name FROM methods WHERE class_id=? AND method_name='Run'", (cid,))
                    if cur.fetchone():
                        patterns.append({"pattern": "Command", "class_id": cid, "class_name": cname})
                if parent and parent != "object":
                    patterns.append({"pattern": "Inheritance", "class_id": cid, "class_name": cname, "parent": parent})
                if mcount and mcount > 15:
                    patterns.append({"pattern": "God Class", "class_id": cid, "class_name": cname, "method_count": mcount})
            cur.execute(
                "SELECT class_id, class_name FROM classes WHERE class_name LIKE '%Factory%' "
                "OR class_name LIKE '%Builder%' OR class_name LIKE '%Singleton%' "
                "OR class_name LIKE '%Observer%' OR class_name LIKE '%Adapter%'"
            )
            for row in cur.fetchall():
                patterns.append({"pattern": "Named Pattern", "class_id": row[0], "class_name": row[1]})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"patterns": patterns, "count": len(patterns)}, None)

    def DetectAntiPatterns(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        anti_patterns = []
        try:
            cur.execute("SELECT class_id, class_name, method_count FROM classes")
            for row in cur.fetchall():
                cid, cname, mcount = row
                if mcount and mcount > 20:
                    anti_patterns.append({"anti_pattern": "God Object", "class_id": cid, "class_name": cname, "method_count": mcount})
                if mcount and mcount < 2:
                    anti_patterns.append({"anti_pattern": "Anemic Class", "class_id": cid, "class_name": cname})
            cur.execute(
                "SELECT method_id, method_name, cyclomatic_complexity, nesting_depth "
                "FROM methods WHERE cyclomatic_complexity >= 15 OR nesting_depth >= 5"
            )
            for row in cur.fetchall():
                mid, mname, cc, nd = row
                if cc and cc >= 15:
                    anti_patterns.append({"anti_pattern": "High Complexity", "method_id": mid, "method_name": mname, "complexity": cc})
                if nd and nd >= 5:
                    anti_patterns.append({"anti_pattern": "Deep Nesting", "method_id": mid, "method_name": mname, "depth": nd})
            cur.execute(
                "SELECT file_id, file_path, line_count FROM files WHERE line_count > 500"
            )
            for row in cur.fetchall():
                anti_patterns.append({"anti_pattern": "Long File", "file_id": row[0], "file_path": row[1], "lines": row[2]})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"anti_patterns": anti_patterns, "count": len(anti_patterns)}, None)

    def DetectCodeSmells(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        smells = []
        try:
            cur.execute(
                "SELECT method_id, method_name, cyclomatic_complexity, line_count, "
                "parameter_count, nesting_depth FROM methods"
            )
            for row in cur.fetchall():
                mid, mname, cc, lc, pc, nd = row
                if cc and cc > 10:
                    smells.append({"smell": "Complex Method", "method_id": mid, "method_name": mname, "complexity": cc})
                if lc and lc > 50:
                    smells.append({"smell": "Long Method", "method_id": mid, "method_name": mname, "lines": lc})
                if pc and pc > 5:
                    smells.append({"smell": "Long Parameter List", "method_id": mid, "method_name": mname, "params": pc})
                if nd and nd > 4:
                    smells.append({"smell": "Deep Nesting", "method_id": mid, "method_name": mname, "depth": nd})
            cur.execute(
                "SELECT class_id, class_name, method_count FROM classes WHERE method_count > 15"
            )
            for row in cur.fetchall():
                smells.append({"smell": "Large Class", "class_id": row[0], "class_name": row[1], "methods": row[2]})
            cur.execute(
                "SELECT COUNT(*) FROM edges WHERE edge_type='calls' GROUP BY src_id HAVING COUNT(*) > 20"
            )
            for row in cur.fetchall():
                smells.append({"smell": "Shotgun Surgery", "call_count": row[0]})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"smells": smells, "count": len(smells)}, None)

    def DetectNamingPatterns(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        patterns = []
        try:
            cur.execute("SELECT class_name FROM classes")
            for row in cur.fetchall():
                cname = row[0] or ""
                if cname and not cname[0].isupper():
                    patterns.append({"pattern": "class_not_pascal_case", "class_name": cname})
                if cname and "_" in cname:
                    patterns.append({"pattern": "class_has_underscore", "class_name": cname})
                if cname and cname != cname.title() and cname.islower():
                    patterns.append({"pattern": "class_all_lower", "class_name": cname})
            cur.execute("SELECT method_name FROM methods")
            for row in cur.fetchall():
                mname = row[0] or ""
                if mname and "_" in mname and not mname.startswith("__"):
                    patterns.append({"pattern": "method_has_underscore", "method_name": mname})
                if mname and mname[0].isupper() and not mname.startswith("__"):
                    patterns.append({"pattern": "method_starts_uppercase", "method_name": mname})
            cur.execute("SELECT method_name, method_code FROM methods")
            for row in cur.fetchall():
                code = row[1] or ""
                constants = re.findall(r'([a-z][A-Z_0-9]{2,})\s*=', code)
                for const in constants:
                    patterns.append({"pattern": "constant_not_uppercase", "constant": const, "method_name": row[0]})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"naming_patterns": patterns, "count": len(patterns)}, None)

    def DetectArchitectureRules(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        violations = []
        try:
            cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=0")
            no_run = cur.fetchone()[0]
            if no_run:
                violations.append({"rule": "all_classes_must_have_run", "violations": no_run})
            cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=0")
            no_tuple3 = cur.fetchone()[0]
            if no_tuple3:
                violations.append({"rule": "all_methods_return_tuple3", "violations": no_tuple3})
            cur.execute("SELECT COUNT(*) FROM classes WHERE has_init=0")
            no_init = cur.fetchone()[0]
            if no_init:
                violations.append({"rule": "all_classes_have_init", "violations": no_init})
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
            prints = cur.fetchone()[0]
            if prints:
                violations.append({"rule": "no_print_statements", "violations": prints})
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_decorator=1")
            decorators = cur.fetchone()[0]
            if decorators:
                violations.append({"rule": "no_decorators", "violations": decorators})
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_self_underscore=1")
            underscores = cur.fetchone()[0]
            if underscores:
                violations.append({"rule": "no_self_underscore", "violations": underscores})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"violations": violations, "count": len(violations),
                    "compliant": len(violations) == 0}, None)

    def DetectUserRules(self, params):
        rules = self._p(params, "rules", [])
        if not rules:
            return (1, {"violations": [], "count": 0, "reason": "no rules provided"}, None)
        conn = self.Connect()[1]
        cur = conn.cursor()
        violations = []
        try:
            for rule in rules:
                rule_type = rule.get("type", "name_pattern")
                if rule_type == "name_pattern":
                    pattern = rule.get("pattern", "")
                    target = rule.get("target", "class")
                    if target == "class":
                        cur.execute("SELECT class_id, class_name FROM classes WHERE class_name NOT LIKE ?", (pattern,))
                    elif target == "method":
                        cur.execute("SELECT method_id, method_name FROM methods WHERE method_name NOT LIKE ?", (pattern,))
                    for row in cur.fetchall():
                        violations.append({"rule": rule.get("name", "unnamed"), "id": row[0], "name": row[1]})
                elif rule_type == "max_methods":
                    max_count = rule.get("max", 15)
                    cur.execute("SELECT class_id, class_name, method_count FROM classes WHERE method_count > ?", (max_count,))
                    for row in cur.fetchall():
                        violations.append({"rule": rule.get("name", "max_methods"), "class_id": row[0], "class_name": row[1], "method_count": row[2]})
                elif rule_type == "max_complexity":
                    max_cc = rule.get("max", 10)
                    cur.execute("SELECT method_id, method_name, cyclomatic_complexity FROM methods WHERE cyclomatic_complexity > ?", (max_cc,))
                    for row in cur.fetchall():
                        violations.append({"rule": rule.get("name", "max_complexity"), "method_id": row[0], "method_name": row[1], "complexity": row[2]})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"violations": violations, "count": len(violations)}, None)

    def DetectViolations(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        violations = []
        try:
            cur.execute("SELECT method_id, method_name, has_print, has_decorator, has_self_underscore, returns_tuple3 FROM methods")
            for row in cur.fetchall():
                mid, mname, prints, decorators, underscores, tuple3 = row
                if prints:
                    violations.append({"type": "print", "method_id": mid, "method_name": mname})
                if decorators:
                    violations.append({"type": "decorator", "method_id": mid, "method_name": mname})
                if underscores:
                    violations.append({"type": "self_underscore", "method_id": mid, "method_name": mname})
                if not tuple3:
                    violations.append({"type": "no_tuple3", "method_id": mid, "method_name": mname})
            cur.execute("SELECT class_id, class_name, has_run_method FROM classes WHERE has_run_method=0")
            for row in cur.fetchall():
                violations.append({"type": "no_run", "class_id": row[0], "class_name": row[1]})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"violations": violations, "count": len(violations)}, None)

    def SuggestImprovements(self, params):
        smells = self.DetectCodeSmells(params)
        anti = self.DetectAntiPatterns(params)
        violations = self.DetectViolations(params)
        suggestions = []
        if smells[0] == 1:
            for smell in smells[1]["smells"]:
                if smell["smell"] == "Complex Method":
                    suggestions.append({"target": smell["method_id"], "suggestion": "Break down method to reduce complexity", "priority": "high"})
                elif smell["smell"] == "Long Method":
                    suggestions.append({"target": smell["method_id"], "suggestion": "Extract sub-methods", "priority": "medium"})
                elif smell["smell"] == "Large Class":
                    suggestions.append({"target": smell["class_id"], "suggestion": "Split class into smaller classes", "priority": "high"})
        if anti[0] == 1:
            for ap in anti[1]["anti_patterns"]:
                if ap["anti_pattern"] == "God Object":
                    suggestions.append({"target": ap["class_id"], "suggestion": "Decompose God Object", "priority": "high"})
                elif ap["anti_pattern"] == "Long File":
                    suggestions.append({"target": ap["file_id"], "suggestion": "Split file into modules", "priority": "medium"})
        if violations[0] == 1:
            for v in violations[1]["violations"]:
                if v["type"] == "print":
                    suggestions.append({"target": v["method_id"], "suggestion": "Remove print statement", "priority": "high"})
                elif v["type"] == "no_tuple3":
                    suggestions.append({"target": v["method_id"], "suggestion": "Return Tuple3", "priority": "high"})
                elif v["type"] == "no_run":
                    suggestions.append({"target": v["class_id"], "suggestion": "Add Run dispatch method", "priority": "high"})
        return (1, {"suggestions": suggestions, "count": len(suggestions)}, None)
