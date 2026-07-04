#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/naming_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Phase 4 Section 47 Naming Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="naming_engine.py" domain="twin_naming" authority="NamingEngine"}
# [@SUMMARY]{summary="Naming authority that checks naming conventions, finds duplicate and similar names, reports violations and suggests corrected names for the Project Digital Twin."}
# [@CLASS]{class="NamingEngine" domain="naming" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="check_rules" type="command"}
# [@METHOD]{method="find_duplicates" type="command"}
# [@METHOD]{method="find_similar" type="command"}
# [@METHOD]{method="find_violations" type="command"}
# [@METHOD]{method="suggest_names" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<NamingEngine: checks naming conventions finds duplicate/similar names reports violations suggests corrected names. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations.>][@todos<none>]}
"""
NamingEngine -- authority for naming convention checking and suggestions.
Implements Section 47 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: check_rules, find_duplicates, find_similar, find_violations,
          suggest_names.
The engine verifies PascalCase classes, UPPER_CASE constants and
snake_case methods, detects duplicate and similar names via Levenshtein
distance, reports violations and suggests corrected names following
the project conventions.
"""
import ast
import keyword
import os
import re
import sqlite3
import textwrap
import builtins
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
PASCAL_CASE_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
UPPER_CASE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SIMILAR_DISTANCE = 2
RESERVED_WORDS = set(keyword.kwlist) | set(dir(builtins))


class NamingEngine:
    """Authority for naming convention checks, duplicates and suggestions."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "similar_distance": SIMILAR_DISTANCE,
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
        if command == "check_rules":
            return self.CheckRules(params)
        elif command == "find_duplicates":
            return self.FindDuplicates(params)
        elif command == "find_similar":
            return self.FindSimilar(params)
        elif command == "find_violations":
            return self.FindViolations(params)
        elif command == "suggest_names":
            return self.SuggestNames(params)
        elif command == "reserved_word_detection":
            return self.ReservedWordDetection(params)
        elif command == "naming_consistency":
            return self.NamingConsistency(params)
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

    def CheckRules(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT class_id, class_name FROM classes ORDER BY class_id LIMIT ?",
            (limit,),
        )
        classes = cur.fetchall()
        class_compliant = 0
        class_violations = 0
        for cid, cname in classes:
            if PASCAL_CASE_RE.match(cname or ""):
                class_compliant += 1
            else:
                class_violations += 1
        cur.execute(
            "SELECT method_id, method_name, is_dunder FROM methods "
            "ORDER BY method_id LIMIT ?",
            (limit,),
        )
        methods = cur.fetchall()
        method_compliant = 0
        method_violations = 0
        for mid, mname, is_dunder in methods:
            if is_dunder:
                method_compliant += 1
                continue
            if SNAKE_CASE_RE.match(mname or "") or PASCAL_CASE_RE.match(mname or ""):
                method_compliant += 1
            else:
                method_violations += 1
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config_constants'")
        constant_compliant = 0
        constant_violations = 0
        if cur.fetchone() is not None:
            cur.execute("SELECT name FROM config_constants ORDER BY name LIMIT ?", (limit,))
            for (nm,) in cur.fetchall():
                if UPPER_CASE_RE.match(nm or ""):
                    constant_compliant += 1
                else:
                    constant_violations += 1
        total = class_compliant + class_violations + method_compliant + method_violations + constant_compliant + constant_violations
        compliant = class_compliant + method_compliant + constant_compliant
        score = round((compliant / total * 100), 2) if total else 100.0
        record = {
            "classes": {
                "compliant": class_compliant,
                "violations": class_violations,
                "total": len(classes),
            },
            "methods": {
                "compliant": method_compliant,
                "violations": method_violations,
                "total": len(methods),
            },
            "constants": {
                "compliant": constant_compliant,
                "violations": constant_violations,
            },
            "compliance_score": score,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def FindDuplicates(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_name, COUNT(*) FROM methods "
            "GROUP BY method_name HAVING COUNT(*) > 1 "
            "ORDER BY COUNT(*) DESC LIMIT ?",
            (limit,),
        )
        method_dupes = [
            {"name": r[0], "count": r[1]} for r in cur.fetchall()
        ]
        cur.execute(
            "SELECT class_name, COUNT(*) FROM classes "
            "GROUP BY class_name HAVING COUNT(*) > 1 "
            "ORDER BY COUNT(*) DESC LIMIT ?",
            (limit,),
        )
        class_dupes = [
            {"name": r[0], "count": r[1]} for r in cur.fetchall()
        ]
        record = {
            "duplicate_methods": method_dupes,
            "duplicate_classes": class_dupes,
            "total": len(method_dupes) + len(class_dupes),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def FindSimilar(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        max_dist = self._p(
            params, "max_distance", self.state["config"]["similar_distance"]
        )
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_name FROM methods ORDER BY method_name LIMIT ?",
            (limit,),
        )
        names = [r[0] for r in cur.fetchall()]
        similar = []
        seen = set()
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a = names[i]
                b = names[j]
                if a == b:
                    continue
                dist = self.Levenshtein(a, b)
                if dist <= max_dist:
                    pair_key = a + "|" + b if a < b else b + "|" + a
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)
                    similar.append({
                        "name_a": a,
                        "name_b": b,
                        "distance": dist,
                    })
        similar.sort(key=lambda x: x["distance"])
        record = {
            "similar_pairs": similar,
            "count": len(similar),
            "max_distance": max_dist,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def Levenshtein(self, a, b):
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            curr = [i]
            for j, cb in enumerate(b, 1):
                cost = 0 if ca == cb else 1
                curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
            prev = curr
        return prev[len(b)]

    def FindViolations(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        violations = []
        cur.execute(
            "SELECT class_id, class_name FROM classes ORDER BY class_id LIMIT ?",
            (limit,),
        )
        for cid, cname in cur.fetchall():
            if not PASCAL_CASE_RE.match(cname or ""):
                violations.append({
                    "kind": "class",
                    "id": cid,
                    "name": cname,
                    "rule": "PascalCase",
                })
        cur.execute(
            "SELECT method_id, method_name, is_dunder FROM methods "
            "ORDER BY method_id LIMIT ?",
            (limit,),
        )
        for mid, mname, is_dunder in cur.fetchall():
            if is_dunder:
                continue
            if not (SNAKE_CASE_RE.match(mname or "") or PASCAL_CASE_RE.match(mname or "")):
                violations.append({
                    "kind": "method",
                    "id": mid,
                    "name": mname,
                    "rule": "snake_case_or_PascalCase",
                })
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config_constants'")
        if cur.fetchone() is not None:
            cur.execute("SELECT name FROM config_constants ORDER BY name LIMIT ?", (limit,))
            for (nm,) in cur.fetchall():
                if not UPPER_CASE_RE.match(nm or ""):
                    violations.append({
                        "kind": "constant",
                        "id": None,
                        "name": nm,
                        "rule": "UPPER_CASE",
                    })
        record = {
            "violations": violations,
            "count": len(violations),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def SuggestNames(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        viol_result = self.FindViolations({"limit": limit})
        if viol_result[0] != 1:
            return viol_result
        violations = viol_result[1]["violations"]
        suggestions = []
        for v in violations:
            suggested = self.SuggestFor(v)
            suggestions.append({
                "kind": v["kind"],
                "id": v["id"],
                "current": v["name"],
                "rule": v["rule"],
                "suggested": suggested,
            })
        record = {
            "suggestions": suggestions,
            "count": len(suggestions),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def SuggestFor(self, violation):
        nm = violation["name"] or ""
        rule = violation["rule"]
        if rule == "PascalCase":
            return self.ToPascalCase(nm)
        if rule == "UPPER_CASE":
            return self.ToUpperCase(nm)
        if rule == "snake_case_or_PascalCase":
            if nm and nm[0].isupper():
                return self.ToPascalCase(nm)
            return self.ToSnakeCase(nm)
        return nm

    def ToPascalCase(self, name):
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", name)
        parts = cleaned.split()
        if not parts:
            return name
        return "".join(p[:1].upper() + p[1:] for p in parts)

    def ToSnakeCase(self, name):
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name)
        parts = re.split(r"([A-Z][^A-Z]*)", cleaned)
        merged = []
        for part in parts:
            if not part:
                continue
            merged.append(part)
        joined = "_".join(merged)
        joined = re.sub(r"_+", "_", joined)
        return joined.lower().strip("_")

    def ToUpperCase(self, name):
        cleaned = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", cleaned)
        return cleaned.upper().strip("_")

    def SafeParse(self, code):
        if not code:
            return None
        try:
            return ast.parse(textwrap.dedent(code))
        except SyntaxError:
            return None

    def ReservedWordDetection(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, method_code, parameters, start_line "
            "FROM methods WHERE method_code IS NOT NULL "
            "ORDER BY method_id LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        violations = []
        for mid, mname, code, params_json, start_line in rows:
            if mname in RESERVED_WORDS:
                violations.append({
                    "method_id": mid,
                    "method_name": mname,
                    "name_type": "method_name",
                    "reserved_word": mname,
                    "line": start_line or 0,
                })
            if params_json:
                try:
                    parsed = __import__("json").loads(params_json)
                    if isinstance(parsed, list):
                        for p in parsed:
                            if isinstance(p, str) and p in RESERVED_WORDS:
                                violations.append({
                                    "method_id": mid,
                                    "method_name": mname,
                                    "name_type": "parameter",
                                    "reserved_word": p,
                                    "line": start_line or 0,
                                })
                except (ValueError, TypeError):
                    pass
            tree = self.SafeParse(code)
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name) and node.id in RESERVED_WORDS:
                        if isinstance(node.ctx, ast.Store):
                            violations.append({
                                "method_id": mid,
                                "method_name": mname,
                                "name_type": "variable",
                                "reserved_word": node.id,
                                "line": (start_line or 0) + node.lineno,
                            })
                    if isinstance(node, ast.arg) and node.arg in RESERVED_WORDS:
                        violations.append({
                            "method_id": mid,
                            "method_name": mname,
                            "name_type": "argument",
                            "reserved_word": node.arg,
                            "line": (start_line or 0) + node.lineno,
                        })
        record = {
            "violations": violations[:limit],
            "count": len(violations),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def NamingConsistency(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_name FROM methods ORDER BY method_id LIMIT ?",
            (limit * 5,),
        )
        method_names = [r[0] for r in cur.fetchall() if r[0]]
        cur.execute(
            "SELECT class_name FROM classes ORDER BY class_id LIMIT ?",
            (limit * 5,),
        )
        class_names = [r[0] for r in cur.fetchall() if r[0]]
        concept_groups = {}
        for name in method_names + class_names:
            tokens = re.split(r"[_A-Z]", name)
            for token in tokens:
                token_lower = token.lower()
                if len(token_lower) >= 4:
                    concept_groups.setdefault(token_lower, set()).add(name)
        inconsistencies = []
        for concept, names in concept_groups.items():
            if len(names) < 2:
                continue
            variants = list(names)
            has_snake = any(SNAKE_CASE_RE.match(n) for n in variants)
            has_pascal = any(PASCAL_CASE_RE.match(n) for n in variants)
            has_camel = any(n[0].islower() and any(c.isupper() for c in n) for n in variants)
            style_count = sum(1 for x in (has_snake, has_pascal, has_camel) if x)
            if style_count > 1:
                inconsistencies.append({
                    "concept": concept,
                    "variants": sorted(variants),
                    "styles": {
                        "snake_case": has_snake,
                        "PascalCase": has_pascal,
                        "camelCase": has_camel,
                    },
                })
        inconsistencies.sort(key=lambda x: len(x["variants"]), reverse=True)
        inconsistencies = inconsistencies[:limit]
        record = {
            "inconsistencies": inconsistencies,
            "count": len(inconsistencies),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)
