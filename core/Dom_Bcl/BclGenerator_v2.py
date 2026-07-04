#!/usr/bin/env python3
#[@GHOST]{("file_path=core/Dom_Bcl/BclGenerator_v2.py";"identity=BclGenerator_v2.py";"purpose=";"date=2026-06-28";"version=1.0";"author=Cascade";"chat_link=")}
#[@VBSTYLE]{[@pass]{"return=Tuple3";"dispatch=Run";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete"}[@fail]{"decorators_found";"print_found";"hardcoded_values";"self._used"}}
#[@FILEID]{("session_id=auto";"context=Auto-stamped by header watcher";"purpose=")}
#[@SUMMARY]{("Created on 2026-06-28";"auto_stamped=true")}

#!/usr/bin/env python3
"""
BclGenerator_v2.py — 20x upgrade: full AST → BCL compiler.
3-level BCL (file → class → method) + functions, imports, complexity,
domain inference, async detection, type annotations, class constants,
inheritance graph, batch mode, SQLite export, summary stats.
Deterministic. No heuristics outside rule definitions.
"""

import ast
import hashlib
import os
import datetime
import sys
import json
import sqlite3
import math


# ═══ RULE DEFINITIONS (strict format) ═══════════════════════════════

RULES = [
    {"id": "@print(22)",       "scope": "method", "severity": "hard", "predicate": lambda f: f["has_print"],            "description": "Disallow print() in method scope"},
    {"id": "@decorators(20)",  "scope": "method", "severity": "hard", "predicate": lambda f: f["decorator_count"] > 0,  "description": "No @staticmethod/@property/@classmethod"},
    {"id": "@underscore(19)",  "scope": "method", "severity": "hard", "predicate": lambda f: f["has_self_underscore"],  "description": "No self._xxx access"},
    {"id": "@t3(50)",          "scope": "method", "severity": "hard", "predicate": lambda f: f["return_count"] > 0 and not f["returns_tuple3"], "description": "All methods must return Tuple3"},
    {"id": "@pascal(38)",      "scope": "class",  "severity": "hard", "predicate": lambda c: c["class_name"] and not c["class_name"][:1].isupper(), "description": "Classes must be PascalCase"},
    {"id": "@run(43)",         "scope": "class",  "severity": "hard", "predicate": lambda c: not c["has_run"],    "description": "Class must have Run() method"},
    {"id": "@ctor(40)",        "scope": "class",  "severity": "hard", "predicate": lambda c: not c["has_init"],  "description": "Class must have __init__"},
    {"id": "@state(41)",       "scope": "class",  "severity": "hard", "predicate": lambda c: not c["has_state"],  "description": "Class must use self.state dict"},
    {"id": "@tabs(25)",        "scope": "class",  "severity": "hard", "predicate": lambda c: c["has_tabs"],      "description": "No tabs, spaces only"},
    {"id": "@upper(39)",       "scope": "class",  "severity": "soft", "predicate": lambda c: any(not n.isupper() for n in c["class_constants"]), "description": "Class constants must be UPPERCASE"},
    {"id": "@whitespace(26)",  "scope": "file",   "severity": "soft", "predicate": lambda f: f["has_trailing_ws"], "description": "No trailing whitespace"},
    {"id": "@hardcode(24)",    "scope": "method", "severity": "soft", "predicate": lambda f: f["hardcoded_count"] > 3, "description": "More than 3 hardcoded string/number literals"},
]


# ═══ RULE ENGINE ════════════════════════════════════════════════════

class RuleEngine:
    def __init__(self, rules=None, mem=None, db=None, param=None):
        self.state = {
            "rules": rules or [],
            "config": {},
        }
        if param:
            for key, value in param.items():
                self.state[key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "evaluate_method":
            return self.EvaluateMethod(params)
        elif command == "evaluate_class":
            return self.EvaluateClass(params)
        elif command == "evaluate_file":
            return self.EvaluateFile(params)
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

    def EvaluateMethod(self, params):
        mf = self._p(params, "features")
        if mf is None:
            return (0, None, ("MISSING_PARAM", "features required", 0))
        violations = []
        for r in self.state["rules"]:
            if r["scope"] == "method":
                if r["predicate"](mf):
                    violations.append({"rule": r["id"], "scope": "method", "method": mf["name"], "severity": r["severity"], "description": r["description"]})
        return (1, violations, None)

    def EvaluateClass(self, params):
        cf = self._p(params, "features")
        if cf is None:
            return (0, None, ("MISSING_PARAM", "features required", 0))
        violations = []
        for r in self.state["rules"]:
            if r["scope"] == "class":
                if r["predicate"](cf):
                    violations.append({"rule": r["id"], "scope": "class", "severity": r["severity"], "description": r["description"]})
        return (1, violations, None)

    def EvaluateFile(self, params):
        ff = self._p(params, "features")
        if ff is None:
            return (0, None, ("MISSING_PARAM", "features required", 0))
        violations = []
        for r in self.state["rules"]:
            if r["scope"] == "file":
                if r["predicate"](ff):
                    violations.append({"rule": r["id"], "scope": "file", "severity": r["severity"], "description": r["description"]})
        return (1, violations, None)


# ═══ FEATURE EXTRACTION ═════════════════════════════════════════════

DOMAIN_KEYWORDS = {
    "search": ["search", "query", "retrieve", "find", "lookup", "match"],
    "index": ["index", "idx", "ann", "hnsw", "faiss", "qdrant"],
    "embed": ["embed", "vector", "encoding", "codebert", "transformer"],
    "storage": ["store", "save", "load", "db", "sqlite", "disk", "file"],
    "config": ["config", "setting", "param", "option", "preference"],
    "gui": ["gui", "widget", "window", "panel", "button", "render", "display"],
    "parse": ["parse", "token", "lex", "syntax", "ast", "grammar"],
    "network": ["http", "socket", "request", "response", "api", "url", "client"],
    "security": ["auth", "encrypt", "decrypt", "hash", "password", "token", "key"],
    "audit": ["audit", "log", "trace", "monitor", "metric", "report"],
    "graph": ["graph", "node", "edge", "vertex", "traverse", "adjacency"],
    "memory": ["memory", "cache", "buffer", "pool", "mem"],
    "text": ["text", "string", "char", "word", "sentence", "document"],
    "ingest": ["ingest", "import", "consume", "batch", "pipeline", "feed"],
    "transform": ["transform", "convert", "map", "remap", "translate", "adapt"],
    "runtime": ["runtime", "execute", "run", "dispatch", "command", "schedule"],
    "validate": ["validate", "check", "verify", "assert", "test", "inspect"],
    "compress": ["compress", "zip", "gzip", "deflate", "archive", "pack"],
    "style": ["style", "theme", "color", "font", "css", "layout", "skin"],
    "workflow": ["workflow", "step", "stage", "flow", "process", "pipeline"],
}


def infer_domain(mf, cf):
    signals = []
    text = (mf["name"] + " " + cf["class_name"] + " " + " ".join(mf["calls"]) + " " + " ".join(mf["self_attrs"])).lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                signals.append(domain)
                break
    if not signals:
        return "unknown"
    from collections import Counter
    counts = Counter(signals)
    return counts.most_common(1)[0][0]


def cyclomatic_complexity(mf):
    return 1 + mf["branch_count"] + mf["loop_count"]


def extract_method_features(node, class_name):
    mf = {
        "name": node.name,
        "class_name": class_name,
        "params": [a.arg for a in node.args.args],
        "param_defaults": [],
        "decorators": [ast.dump(d) for d in node.decorator_list],
        "decorator_names": [],
        "decorator_count": len(node.decorator_list),
        "return_count": 0,
        "returns_tuple3": False,
        "return_annotation": ast.dump(node.returns) if node.returns else None,
        "has_print": False,
        "has_self_underscore": False,
        "has_self_attr": False,
        "self_attrs": [],
        "calls": [],
        "call_count": 0,
        "branch_count": 0,
        "loop_count": 0,
        "line_span": (getattr(node, "end_lineno", node.lineno) - node.lineno),
        "is_async": isinstance(node, (ast.AsyncFunctionDef,)),
        "hardcoded_count": 0,
        "string_constants": [],
        "assignments": [],
        "nested_funcs": [],
        "lineno": node.lineno,
        "end_lineno": getattr(node, "end_lineno", node.lineno),
    }

    for d in node.decorator_list:
        if isinstance(d, ast.Name):
            mf["decorator_names"].append(d.id)
        elif isinstance(d, ast.Attribute):
            mf["decorator_names"].append(d.attr)

    for default in node.args.defaults:
        try:
            mf["param_defaults"].append(ast.dump(default))
        except Exception:
            mf["param_defaults"].append("UNKNOWN")

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name) and func.id == "print":
                mf["has_print"] = True
            if isinstance(func, ast.Attribute):
                mf["call_count"] += 1
                mf["calls"].append(func.attr)
            elif isinstance(func, ast.Name):
                mf["call_count"] += 1
                mf["calls"].append(func.id)

        if isinstance(child, ast.Attribute):
            if isinstance(child.value, ast.Name) and child.value.id == "self":
                mf["has_self_attr"] = True
                mf["self_attrs"].append(child.attr)
                if child.attr.startswith("_") and child.attr not in ("__init__",):
                    mf["has_self_underscore"] = True

        if isinstance(child, ast.Return) and child.value:
            mf["return_count"] += 1
            if isinstance(child.value, ast.Tuple) and len(child.value.elts) == 3:
                mf["returns_tuple3"] = True

        if isinstance(child, (ast.If, ast.Match)):
            mf["branch_count"] += 1
        if isinstance(child, (ast.For, ast.While)):
            mf["loop_count"] += 1

        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            mf["string_constants"].append(child.value[:60])
            mf["hardcoded_count"] += 1
        if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
            if child.value not in (0, 1, -1, 2, True, False):
                mf["hardcoded_count"] += 1

        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    mf["assignments"].append(target.id)

        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not node:
            mf["nested_funcs"].append(child.name)

    mf["complexity"] = cyclomatic_complexity(mf)
    return mf


def extract_class_features(node, source_lines):
    class_name = node.name
    methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    method_features = [extract_method_features(m, class_name) for m in methods]

    docstring = ast.get_docstring(node)

    has_run = any(m.name == "Run" for m in methods)
    has_init = any(m.name == "__init__" for m in methods)

    has_state = False
    class_constants = []
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute):
            if isinstance(child.value, ast.Name) and child.value.id == "self":
                if child.attr == "state":
                    has_state = True
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    class_constants.append(target.id)

    has_tabs = any("\t" in line for line in source_lines)

    bases_clean = []
    for b in node.bases:
        if isinstance(b, ast.Name):
            bases_clean.append(b.id)
        elif isinstance(b, ast.Attribute):
            bases_clean.append(b.attr)
        else:
            bases_clean.append(ast.dump(b))

    nested_classes = [n.name for n in node.body if isinstance(n, ast.ClassDef)]

    return {
        "class_name": class_name,
        "docstring": docstring,
        "methods": method_features,
        "method_names": [m.name for m in methods],
        "has_run": has_run,
        "has_init": has_init,
        "has_state": has_state,
        "has_tabs": has_tabs,
        "lineno": node.lineno,
        "end_lineno": getattr(node, "end_lineno", node.lineno),
        "bases": bases_clean,
        "class_constants": class_constants,
        "nested_classes": nested_classes,
        "method_count": len(methods),
        "total_complexity": sum(mf["complexity"] for mf in method_features),
    }


def extract_file_features(tree, source, source_lines):
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"type": "import", "module": alias.name, "alias": alias.asname})
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append({"type": "from", "module": mod, "name": alias.name, "alias": alias.asname})

    module_docstring = ast.get_docstring(tree)
    has_trailing_ws = any(line.rstrip() != line for line in source_lines)
    standalone_functions = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    standalone_async = [n.name for n in tree.body if isinstance(n, ast.AsyncFunctionDef)]

    return {
        "module_docstring": module_docstring,
        "imports": imports,
        "import_count": len(imports),
        "has_trailing_ws": has_trailing_ws,
        "standalone_functions": standalone_functions,
        "standalone_function_count": len(standalone_functions),
        "standalone_async": standalone_async,
        "line_count": len(source_lines),
    }


def build_inheritance_graph(tree):
    edges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            child = node.name
            for base in node.bases:
                if isinstance(base, ast.Name):
                    edges.append({"child": child, "parent": base.id})
                elif isinstance(base, ast.Attribute):
                    edges.append({"child": child, "parent": base.attr})
    return edges


# ═══ BCL GENERATION (3-level + extras) ══════════════════════════════

def generate_summary(cf):
    if cf["docstring"]:
        return cf["docstring"].strip().split("\n")[0][:120]
    methods = cf["method_names"]
    if not methods:
        return f"Class {cf['class_name']} with no methods"
    return f"Class {cf['class_name']} — methods: {', '.join(methods[:8])}"


def generate_file_bcl(filepath, source, ff, class_results, file_violations):
    file_hash = hashlib.md5(source.encode()).hexdigest()[:8]
    today = datetime.date.today().isoformat()
    filename = os.path.basename(filepath)
    total_classes = len(class_results)
    total_methods = sum(r["method_count"] for r in class_results)
    total_violations = sum(r["violation_count"] for r in class_results) + len(file_violations)
    all_compliant = total_violations == 0

    lines = []
    lines.append(f"#[@FILE]      {filename} path={filepath}")
    lines.append(f"#[@FILEID]    md5={file_hash} date={today} lines={ff['line_count']} classes={total_classes} methods={total_methods}")
    lines.append(f"#[@FDOC]      {(ff['module_docstring'] or 'NONE')[:100]}")
    lines.append(f"#[@FIMPORTS]  count={ff['import_count']} modules={','.join(i['module'] for i in ff['imports'][:12])}")
    lines.append(f"#[@FFUNCS]    count={ff['standalone_function_count']} names={','.join(ff['standalone_functions'][:8])}")
    lines.append(f"#[@FASYNC]    {','.join(ff['standalone_async']) if ff['standalone_async'] else 'NONE'}")
    lines.append(f"#[@FSTAT]     violations={total_violations} compliant={all_compliant}")
    if file_violations:
        lines.append(f"#[@FVIOLATE]  {'; '.join(v['rule'] for v in file_violations)}")
    return "\n".join(lines)


def generate_method_bcl(mf, method_violations, class_name):
    vstr = "; ".join(v["rule"] for v in method_violations) if method_violations else "NONE"
    params_str = ",".join(mf["params"]) if mf["params"] else "NONE"
    calls_str = ",".join(mf["calls"][:10]) if mf["calls"] else "NONE"
    self_attrs_str = ",".join(sorted(set(mf["self_attrs"]))) if mf["self_attrs"] else "NONE"
    decorators_str = ",".join(mf["decorator_names"]) if mf["decorator_names"] else "NONE"
    strings_str = ",".join(mf["string_constants"][:5]) if mf["string_constants"] else "NONE"
    nested_str = ",".join(mf["nested_funcs"]) if mf["nested_funcs"] else "NONE"
    domain = infer_domain(mf, {"class_name": class_name})
    async_tag = "async " if mf["is_async"] else ""

    lines = []
    lines.append(f"  #[@METHOD]     {async_tag}{mf['name']}")
    lines.append(f"  #[@PARAMS]     {params_str}")
    lines.append(f"  #[@RETURNS]    count={mf['return_count']} tuple3={mf['returns_tuple3']} annotation={mf['return_annotation'] or 'NONE'}")
    lines.append(f"  #[@CALLS]      count={mf['call_count']} targets={calls_str}")
    lines.append(f"  #[@SELF]       attrs={self_attrs_str}")
    lines.append(f"  #[@DECORATE]   count={mf['decorator_count']} items={decorators_str}")
    lines.append(f"  #[@FLOW]       branches={mf['branch_count']} loops={mf['loop_count']} complexity={mf['complexity']} span={mf['line_span']}")
    lines.append(f"  #[@HARDCODE]   count={mf['hardcoded_count']} strings={strings_str}")
    lines.append(f"  #[@NESTED]     {nested_str}")
    lines.append(f"  #[@DOMAIN]     {domain}")
    lines.append(f"  #[@MVIOLATE]   {vstr}")
    return "\n".join(lines)


def generate_class_bcl(filepath, source, cf, all_violations, class_violations, method_violations_by_name):
    file_hash = hashlib.md5(source.encode()).hexdigest()[:8]
    today = datetime.date.today().isoformat()
    filename = os.path.basename(filepath)

    compliant = len(all_violations) == 0
    class_vstr = "; ".join(v["rule"] for v in class_violations) if class_violations else "NONE"
    all_vstr = "; ".join(v["rule"] for v in all_violations) if all_violations else "NONE"
    summary = generate_summary(cf)
    method_str = ", ".join(cf["method_names"]) if cf["method_names"] else "NONE"
    constants_str = ", ".join(cf["class_constants"]) if cf["class_constants"] else "NONE"
    nested_str = ", ".join(cf["nested_classes"]) if cf["nested_classes"] else "NONE"

    lines = []
    lines.append(f"#[@GHOST]      file={filepath} date={today} author=BclGenerator_v2 hash={file_hash}")
    lines.append(f"#[@VBSTYLE]    compliant={compliant} violations={len(all_violations)} rules={all_vstr}")
    lines.append(f"#[@CLASS]      {cf['class_name']}")
    lines.append(f"#[@CSUMMARY]   {summary}")
    lines.append(f"#[@CMETHODS]   {method_str}")
    lines.append(f"#[@CVIOLATE]   {class_vstr}")
    lines.append(f"#[@CBASES]     {','.join(cf['bases']) if cf['bases'] else 'NONE'}")
    lines.append(f"#[@CCONST]     {constants_str}")
    lines.append(f"#[@CNESTED]    {nested_str}")
    lines.append(f"#[@CBODY]      lines={cf['lineno']}-{cf['end_lineno']}")
    lines.append(f"#[@CCOMPLEX]   total={cf['total_complexity']} avg={cf['total_complexity'] / max(cf['method_count'], 1):.1f}")

    for mf in cf["methods"]:
        mv = method_violations_by_name.get(mf["name"], [])
        lines.append(generate_method_bcl(mf, mv, cf["class_name"]))

    return "\n".join(lines)


# ═══ FULL PIPELINE ══════════════════════════════════════════════════

def process_file(filepath):
    with open(filepath, "r") as f:
        source = f.read()
    source_lines = source.splitlines()
    tree = ast.parse(source, filename=filepath)

    engine = RuleEngine(RULES)
    ff = extract_file_features(tree, source, source_lines)
    file_violations_result = engine.Run("evaluate_file", {"features": ff})
    file_violations = []
    if file_violations_result[0] == 1 and file_violations_result[1]:
        rv = file_violations_result[1]
        if isinstance(rv, dict):
            file_violations = rv.get("violations", [])
        elif isinstance(rv, list):
            file_violations = rv

    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cf = extract_class_features(node, source_lines)

            class_v_result = engine.Run("evaluate_class", {"features": cf})
            class_violations = []
            if class_v_result[0] == 1 and class_v_result[1]:
                rv = class_v_result[1]
                if isinstance(rv, dict):
                    class_violations = rv.get("violations", [])
                elif isinstance(rv, list):
                    class_violations = rv

            method_violations = []
            for mf in cf["methods"]:
                mv_result = engine.Run("evaluate_method", {"features": mf})
                if mv_result[0] == 1 and mv_result[1]:
                    rv = mv_result[1]
                    if isinstance(rv, dict):
                        method_violations.extend(rv.get("violations", []))
                    elif isinstance(rv, list):
                        method_violations.extend(rv)

            all_violations = class_violations + method_violations

            method_violations_by_name = {}
            for mv in method_violations:
                method_violations_by_name.setdefault(mv["method"], []).append(mv)

            bcl = generate_class_bcl(filepath, source, cf, all_violations, class_violations, method_violations_by_name)

            call_edges = []
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(m):
                        if isinstance(child, ast.Call):
                            if isinstance(child.func, ast.Attribute):
                                call_edges.append({"caller": m.name, "callee": child.func.attr, "type": "attr"})
                            elif isinstance(child.func, ast.Name):
                                call_edges.append({"caller": m.name, "callee": child.func.id, "type": "name"})

            results.append({
                "file": filepath,
                "class": cf["class_name"],
                "methods": cf["method_names"],
                "method_count": cf["method_count"],
                "docstring": cf["docstring"],
                "violations": all_violations,
                "violation_count": len(all_violations),
                "class_violations": class_violations,
                "method_violations": method_violations,
                "compliant": len(all_violations) == 0,
                "bcl_header": bcl,
                "call_edges": call_edges,
                "method_features": cf["methods"],
                "class_constants": cf["class_constants"],
                "bases": cf["bases"],
                "nested_classes": cf["nested_classes"],
                "total_complexity": cf["total_complexity"],
            })

    inheritance = build_inheritance_graph(tree)
    file_bcl = generate_file_bcl(filepath, source, ff, results, file_violations)

    return {
        "filepath": filepath,
        "file_bcl": file_bcl,
        "file_features": ff,
        "file_violations": file_violations,
        "classes": results,
        "inheritance_graph": inheritance,
        "class_count": len(results),
        "total_methods": sum(r["method_count"] for r in results),
        "total_violations": sum(r["violation_count"] for r in results) + len(file_violations),
        "total_call_edges": sum(len(r["call_edges"]) for r in results),
        "total_complexity": sum(r["total_complexity"] for r in results),
    }


def process_directory(dirpath):
    all_results = []
    for root, dirs, files in os.walk(dirpath):
        if ".git" in root or "__pycache__" in root or "node_modules" in root:
            continue
        for fn in files:
            if fn.endswith(".py"):
                fp = os.path.join(root, fn)
                try:
                    all_results.append(process_file(fp))
                except Exception as e:
                    all_results.append({
                        "filepath": fp,
                        "error": str(e),
                        "class_count": 0,
                        "total_methods": 0,
                        "total_violations": 0,
                        "total_call_edges": 0,
                        "total_complexity": 0,
                    })
    return all_results


def export_sqlite(results, db_path):
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS bcl_files (filepath TEXT, class_count INTEGER, method_count INTEGER, violation_count INTEGER, call_edges INTEGER, complexity INTEGER, bcl TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS bcl_classes (filepath TEXT, class_name TEXT, method_count INTEGER, violation_count INTEGER, compliant INTEGER, complexity INTEGER, bases TEXT, bcl TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS bcl_methods (filepath TEXT, class_name TEXT, method_name TEXT, params TEXT, return_count INTEGER, returns_tuple3 INTEGER, call_count INTEGER, complexity INTEGER, domain TEXT, violations TEXT, is_async INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS bcl_call_graph (filepath TEXT, class_name TEXT, caller TEXT, callee TEXT, call_type TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS bcl_inheritance (filepath TEXT, child TEXT, parent TEXT)")

    for r in results:
        if "error" in r:
            continue
        cur.execute("INSERT INTO bcl_files VALUES (?,?,?,?,?,?,?)", (r["filepath"], r["class_count"], r["total_methods"], r["total_violations"], r["total_call_edges"], r["total_complexity"], r["file_bcl"]))
        for c in r["classes"]:
            cur.execute("INSERT INTO bcl_classes VALUES (?,?,?,?,?,?,?,?)", (c["file"], c["class"], c["method_count"], c["violation_count"], int(c["compliant"]), c["total_complexity"], ",".join(c["bases"]), c["bcl_header"]))
            for mf in c["method_features"]:
                mv_str = ";".join(v["rule"] for v in c["method_violations"] if v.get("method") == mf["name"])
                from collections import Counter
                domain = infer_domain(mf, {"class_name": c["class"]})
                cur.execute("INSERT INTO bcl_methods VALUES (?,?,?,?,?,?,?,?,?,?,?)", (c["file"], c["class"], mf["name"], ",".join(mf["params"]), mf["return_count"], int(mf["returns_tuple3"]), mf["call_count"], mf["complexity"], domain, mv_str, int(mf["is_async"])))
            for e in c["call_edges"]:
                cur.execute("INSERT INTO bcl_call_graph VALUES (?,?,?,?,?)", (c["file"], c["class"], e["caller"], e["callee"], e["type"]))
        for edge in r["inheritance_graph"]:
            cur.execute("INSERT INTO bcl_inheritance VALUES (?,?,?)", (r["filepath"], edge["child"], edge["parent"]))

    db.commit()
    db.close()


def print_summary(all_results):
    total_files = len(all_results)
    total_classes = sum(r.get("class_count", 0) for r in all_results)
    total_methods = sum(r.get("total_methods", 0) for r in all_results)
    total_violations = sum(r.get("total_violations", 0) for r in all_results)
    total_edges = sum(r.get("total_call_edges", 0) for r in all_results)
    total_complexity = sum(r.get("total_complexity", 0) for r in all_results)
    errors = sum(1 for r in all_results if "error" in r)

    sys.stdout.write("\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("SUMMARY STATISTICS\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write(f"  Files processed:    {total_files}\n")
    sys.stdout.write(f"  Errors:             {errors}\n")
    sys.stdout.write(f"  Classes found:      {total_classes}\n")
    sys.stdout.write(f"  Methods found:      {total_methods}\n")
    sys.stdout.write(f"  Total violations:   {total_violations}\n")
    sys.stdout.write(f"  Call graph edges:   {total_edges}\n")
    sys.stdout.write(f"  Total complexity:   {total_complexity}\n")
    sys.stdout.write(f"  Avg complexity:     {total_complexity / max(total_methods, 1):.1f}\n")

    compliant_classes = sum(1 for r in all_results for c in r.get("classes", []) if c["compliant"])
    non_compliant = total_classes - compliant_classes
    sys.stdout.write(f"  Compliant classes:  {compliant_classes}/{total_classes} ({compliant_classes / max(total_classes, 1) * 100:.0f}%)\n")
    sys.stdout.write(f"  Non-compliant:      {non_compliant}\n")

    from collections import Counter
    all_violations = []
    for r in all_results:
        for c in r.get("classes", []):
            for v in c["violations"]:
                all_violations.append(v["rule"])
    if all_violations:
        counts = Counter(all_violations)
        sys.stdout.write(f"\n  Top violations:\n")
        for rule, cnt in counts.most_common(10):
            sys.stdout.write(f"    {rule:20s} x{cnt}\n")

    all_domains = []
    for r in all_results:
        for c in r.get("classes", []):
            for mf in c["method_features"]:
                all_domains.append(infer_domain(mf, {"class_name": c["class"]}))
    if all_domains:
        dcounts = Counter(all_domains)
        sys.stdout.write(f"\n  Top inferred domains:\n")
        for domain, cnt in dcounts.most_common(10):
            sys.stdout.write(f"    {domain:20s} x{cnt}\n")

    sys.stdout.write("=" * 70 + "\n")


def main():
    if len(sys.argv) < 2:
        sys.stdout.write("Usage: python3 BclGenerator_v2.py <file.py|dir> [--json] [--stamp] [--sqlite DB] [--summary]\n")
        sys.stdout.write("  --json      Output as JSON\n")
        sys.stdout.write("  --stamp     Write BCL headers to file(s)\n")
        sys.stdout.write("  --sqlite DB Export to SQLite database\n")
        sys.stdout.write("  --summary   Print summary statistics only\n")
        sys.exit(1)

    target = sys.argv[1]
    output_json = "--json" in sys.argv
    stamp = "--stamp" in sys.argv
    summary_only = "--summary" in sys.argv
    sqlite_path = None
    if "--sqlite" in sys.argv:
        idx = sys.argv.index("--sqlite")
        sqlite_path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "bcl_export.db"

    if os.path.isdir(target):
        all_results = process_directory(target)
    elif os.path.isfile(target):
        all_results = [process_file(target)]
    else:
        sys.stdout.write(f"ERROR: Not found: {target}\n")
        sys.exit(1)

    if sqlite_path:
        export_sqlite(all_results, sqlite_path)
        sys.stdout.write(f"[SQLITE] Exported to {sqlite_path}\n")

    if summary_only:
        print_summary(all_results)
        return

    if output_json:
        sys.stdout.write(json.dumps(all_results, indent=2, default=str) + "\n")
    else:
        for r in all_results:
            if "error" in r:
                sys.stdout.write(f"[ERROR] {r['filepath']}: {r['error']}\n")
                continue
            sys.stdout.write("#" * 70 + "\n")
            sys.stdout.write("# FILE-LEVEL BCL\n")
            sys.stdout.write("#" * 70 + "\n")
            sys.stdout.write(r["file_bcl"] + "\n\n")

            if r["inheritance_graph"]:
                sys.stdout.write("#[@INHERITANCE]\n")
                for edge in r["inheritance_graph"]:
                    sys.stdout.write(f"  {edge['child']} -> {edge['parent']}\n")
                sys.stdout.write("\n")

            for c in r["classes"]:
                sys.stdout.write("=" * 70 + "\n")
                sys.stdout.write("# CLASS-LEVEL BCL\n")
                sys.stdout.write("=" * 70 + "\n")
                sys.stdout.write(c["bcl_header"] + "\n")

                sys.stdout.write("-" * 40 + "\n")
                sys.stdout.write(f"CALL EDGES ({len(c['call_edges'])}):\n")
                for e in c["call_edges"]:
                    sys.stdout.write(f"  {e['caller']} -> {e['callee']} ({e['type']})\n")
                sys.stdout.write("=" * 70 + "\n\n")

            if stamp and os.path.isfile(r["filepath"]):
                with open(r["filepath"], "r") as f:
                    content = f.read()
                if "#[@GHOST]" not in content:
                    full_bcl = r["file_bcl"] + "\n\n"
                    for c in r["classes"]:
                        full_bcl += c["bcl_header"] + "\n\n"
                    with open(r["filepath"], "w") as f:
                        f.write(full_bcl + content)
                    sys.stdout.write(f"[STAMPED] {r['filepath']}\n")
                else:
                    sys.stdout.write(f"[SKIP] {r['filepath']} already has BCL\n")

        print_summary(all_results)


if __name__ == "__main__":
    main()
