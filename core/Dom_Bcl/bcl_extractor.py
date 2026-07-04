#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_extractor.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstyle-fix"
# context="BCL IR FeatureExtractor — extracts features from AST nodes for IR compilation"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_extractor.py" domain="BCL" authority="FeatureExtractor"}
# [@SUMMARY]{summary="BCL FeatureExtractor: extracts method/class/file features from Python AST. No regex, no print."}
# [@CLASS]{class="FeatureExtractor" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="extract_method_features" type="command"}
# [@METHOD]{method="extract_class_features" type="command"}
# [@METHOD]{method="extract_file_features" type="command"}
# [@METHOD]{method="infer_domain" type="command"}
# [@METHOD]{method="categorize_string" type="command"}
# [@METHOD]{method="extract_param_type" type="command"}
# [@METHOD]{method="compute_max_nesting" type="command"}
# [@METHOD]{method="walk_method_body" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import ast
from collections import Counter

from bcl_config import IR_RULES, DOMAIN_KEYWORDS, DOMAIN_EXCLUDE


class FeatureExtractor:
    """Extract features from AST nodes for IR compilation."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "rules": IR_RULES,
            "domain_keywords": DOMAIN_KEYWORDS,
            "domain_exclude": DOMAIN_EXCLUDE,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "extract_method_features":
            return self.ExtractMethodFeatures(params)
        elif command == "extract_class_features":
            return self.ExtractClassFeatures(params)
        elif command == "extract_file_features":
            return self.ExtractFileFeatures(params)
        elif command == "infer_domain":
            return self.InferDomain(params)
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

    def CategorizeString(self, s):
        sl = s.lower()
        sql_kws = ("select ", "insert ", "create table", "update ", "delete ", "alter table", "drop ")
        err_kws = ("error", "failed", "exception", "invalid", "cannot", "unable")
        for kw in sql_kws:
            if kw in sl:
                return (1, "sql", None)
        for kw in err_kws:
            if kw in sl:
                return (1, "error", None)
        if "{" in s and "}" in s:
            return (1, "format", None)
        if len(s) <= 30 and s.replace("_", "").isalnum() and not s.startswith("http"):
            return (1, "command", None)
        return (1, "other", None)

    def ExtractParamType(self, arg):
        if arg.annotation is None:
            return (1, None, None)
        if isinstance(arg.annotation, ast.Name):
            return (1, arg.annotation.id, None)
        if isinstance(arg.annotation, ast.Constant):
            return (1, str(arg.annotation.value), None)
        if isinstance(arg.annotation, ast.Attribute):
            return (1, arg.annotation.attr, None)
        return (1, "complex", None)

    def ComputeMaxNesting(self, node, depth):
        max_d = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                if hasattr(ast, "Match") and isinstance(child, ast.Match):
                    pass
                child_result = self.ComputeMaxNesting(child, depth + 1)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            else:
                child_result = self.ComputeMaxNesting(child, depth)
            if child_result[0] == 1 and child_result[1] > max_d:
                max_d = child_result[1]
        return (1, max_d, None)

    def WalkMethodBody(self, node, mf, method_node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not method_node:
            mf["nested_funcs"].append(node.name)
            for child in ast.iter_child_nodes(node):
                self.WalkMethodBody(child, mf, method_node)
            return (1, True, None)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "print":
                mf["has_print"] = True
            if isinstance(func, ast.Name) and func.id in ("eval", "exec", "compile"):
                mf["has_eval"] = True
            if isinstance(func, ast.Attribute):
                mf["call_count"] += 1
                mf["calls"].append(func.attr)
                if func.attr in ("system", "popen", "run", "Popen", "call", "check_call", "check_output"):
                    if isinstance(func.value, ast.Name) and func.value.id in ("os", "subprocess"):
                        mf["has_subprocess"] = True
            elif isinstance(func, ast.Name):
                mf["call_count"] += 1
                mf["calls"].append(func.id)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                mf["has_self_attr"] = True
                mf["self_attrs"].append(node.attr)
                if node.attr.startswith("_") and node.attr not in ("__init__",):
                    mf["has_self_underscore"] = True
        if isinstance(node, ast.Return) and node.value:
            mf["return_count"] += 1
            if isinstance(node.value, ast.Tuple) and len(node.value.elts) == 3:
                mf["returns_tuple3"] = True
        if isinstance(node, (ast.If,)):
            mf["branch_count"] += 1
        if hasattr(ast, "Match") and isinstance(node, ast.Match):
            mf["branch_count"] += 1
        if isinstance(node, (ast.For, ast.While)):
            mf["loop_count"] += 1
        if isinstance(node, ast.Dict):
            for val in node.values:
                if val is not None:
                    self.WalkMethodBody(val, mf, method_node)
            return (1, True, None)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            cat_result = self.CategorizeString(node.value)
            cat = cat_result[1] if cat_result[0] == 1 else "other"
            mf["string_categories"][cat] = mf["string_categories"].get(cat, 0) + 1
            mf["string_constants"].append(node.value[:50])
            mf["hardcoded_count"] += 1
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if node.value not in (0, 1, -1, 2, True, False):
                mf["hardcoded_count"] += 1
        for child in ast.iter_child_nodes(node):
            self.WalkMethodBody(child, mf, method_node)
        return (1, True, None)

    def ExtractMethodFeatures(self, params):
        node = self._p(params, "node")
        class_name = self._p(params, "class_name", "")
        if node is None:
            return (0, None, ("MISSING_PARAM", "node required", 0))
        mf = {
            "name": node.name, "class_name": class_name,
            "params": [a.arg for a in node.args.args],
            "param_types": [],
            "decorator_names": [], "decorator_count": len(node.decorator_list),
            "return_count": 0, "returns_tuple3": False, "return_annotation": None,
            "has_print": False, "has_eval": False, "has_subprocess": False,
            "has_self_underscore": False, "has_self_attr": False, "self_attrs": [],
            "calls": [], "call_count": 0, "branch_count": 0, "loop_count": 0,
            "max_nesting": 0, "line_span": (getattr(node, "end_lineno", node.lineno) - node.lineno),
            "is_async": isinstance(node, (ast.AsyncFunctionDef,)),
            "hardcoded_count": 0, "string_constants": [],
            "string_categories": {"sql": 0, "error": 0, "format": 0, "command": 0, "other": 0},
            "nested_funcs": [], "local_var_count": 0,
            "halstead_operators": 0, "halstead_operands": 0,
            "lineno": node.lineno, "end_lineno": getattr(node, "end_lineno", node.lineno),
        }
        for a in node.args.args:
            pt = self.ExtractParamType(a)
            mf["param_types"].append(pt[1] if pt[0] == 1 else None)
        if node.returns:
            if isinstance(node.returns, ast.Name):
                mf["return_annotation"] = node.returns.id
            elif isinstance(node.returns, ast.Constant):
                mf["return_annotation"] = str(node.returns.value)
            else:
                mf["return_annotation"] = "complex"
        for d in node.decorator_list:
            if isinstance(d, ast.Name):
                mf["decorator_names"].append(d.id)
            elif isinstance(d, ast.Attribute):
                mf["decorator_names"].append(d.attr)
        for child in ast.iter_child_nodes(node):
            self.WalkMethodBody(child, mf, node)
        mf["call_sites"] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    mf["call_sites"].append({"callee": child.func.attr, "type": "attr", "lineno": getattr(child, "lineno", 0)})
                elif isinstance(child.func, ast.Name):
                    mf["call_sites"].append({"callee": child.func.id, "type": "name", "lineno": getattr(child, "lineno", 0)})
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name) and not target.id.isupper():
                        mf["local_var_count"] += 1
        for child in ast.walk(node):
            if isinstance(child, (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.AugAssign)):
                mf["halstead_operators"] += 1
            if isinstance(child, ast.Name):
                mf["halstead_operands"] += 1
            if isinstance(child, ast.Constant):
                mf["halstead_operands"] += 1
        nest_result = self.ComputeMaxNesting(node, 0)
        mf["max_nesting"] = nest_result[1] if nest_result[0] == 1 else 0
        mf["complexity"] = 1 + mf["branch_count"] + mf["loop_count"]
        mf["halstead_volume"] = mf["halstead_operators"] + mf["halstead_operands"]
        return (1, mf, None)

    def InferDomain(self, params):
        mf = self._p(params, "mf")
        class_name = self._p(params, "class_name", "")
        if mf is None:
            return (0, None, ("MISSING_PARAM", "mf required", 0))
        text = (mf["name"] + " " + class_name + " " + " ".join(mf.get("calls", [])) + " " + " ".join(mf.get("self_attrs", []))).lower()
        tokens = []
        current = []
        for ch in text:
            if ch.isalpha() or ch == "_":
                current.append(ch)
            else:
                if current:
                    tokens.append("".join(current))
                    current = []
        if current:
            tokens.append("".join(current))
        signals = []
        for domain, keywords in self.state["domain_keywords"].items():
            for kw in keywords:
                matched = False
                exclude = self.state["domain_exclude"].get(kw, set())
                for tok in tokens:
                    if tok in exclude:
                        continue
                    if tok == kw or tok.startswith(kw):
                        matched = True
                        break
                if matched:
                    signals.append(domain)
                    break
        if not signals:
            return (1, "unknown", None)
        counts = Counter(signals)
        return (1, counts.most_common(1)[0][0], None)

    def ExtractClassFeatures(self, params):
        node = self._p(params, "node")
        source_lines = self._p(params, "source_lines", [])
        if node is None:
            return (0, None, ("MISSING_PARAM", "node required", 0))
        class_name = node.name
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        method_features = []
        for m in methods:
            mr = self.ExtractMethodFeatures({"node": m, "class_name": class_name})
            if mr[0] == 1:
                method_features.append(mr[1])
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
                bases_clean.append("complex")
        nested_classes = [n.name for n in node.body if isinstance(n, ast.ClassDef)]
        wmc = sum(mf["complexity"] for mf in method_features)
        all_calls = []
        for mf in method_features:
            all_calls.extend(mf["calls"])
        rfc = len(set(all_calls + [m.name for m in methods]))
        method_shared_attrs = []
        for mf in method_features:
            method_shared_attrs.append(set(mf["self_attrs"]))
        lcom = 0
        for i in range(len(method_shared_attrs)):
            for j in range(i + 1, len(method_shared_attrs)):
                if not method_shared_attrs[i] & method_shared_attrs[j]:
                    lcom += 1
        has_dispatch = False
        has_singleton = False
        has_factory = False
        for child in ast.walk(node):
            if isinstance(child, ast.Dict):
                has_dispatch = True
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                        if target.attr in ("_instance", "instance"):
                            has_singleton = True
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                if child.func.id in ("type", "getattr", "setattr"):
                    has_factory = True
        patterns = []
        if has_dispatch:
            patterns.append("dispatch")
        if has_singleton:
            patterns.append("singleton")
        if has_factory:
            patterns.append("factory")
        cf = {
            "class_name": class_name, "docstring": ast.get_docstring(node),
            "methods": method_features, "method_names": [m.name for m in methods],
            "has_run": has_run, "has_init": has_init, "has_state": has_state,
            "has_tabs": has_tabs, "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", node.lineno),
            "bases": bases_clean, "class_constants": class_constants,
            "nested_classes": nested_classes, "method_count": len(methods),
            "total_complexity": sum(mf["complexity"] for mf in method_features),
            "wmc": wmc, "rfc": rfc, "lcom": lcom,
            "patterns": ",".join(patterns) if patterns else "NONE",
        }
        return (1, cf, None)

    def ExtractFileFeatures(self, params):
        tree = self._p(params, "tree")
        source_lines = self._p(params, "source_lines", [])
        if tree is None:
            return (0, None, ("MISSING_PARAM", "tree required", 0))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"module": alias.name, "alias": alias.asname})
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append({"module": mod, "name": alias.name, "alias": alias.asname})
        standalone_functions = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        standalone_async = [n.name for n in tree.body if isinstance(n, ast.AsyncFunctionDef)]
        all_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                all_names.add(node.id)
            if isinstance(node, ast.Attribute):
                all_names.add(node.attr)
        dead_imports = []
        for imp in imports:
            ref_name = imp.get("alias") or imp.get("name") or imp["module"].split(".")[-1]
            if ref_name == "*":
                continue
            if ref_name not in all_names and imp["module"] not in all_names:
                dead_imports.append(ref_name)
        ff = {
            "module_docstring": ast.get_docstring(tree),
            "imports": imports, "import_count": len(imports),
            "dead_imports": dead_imports,
            "has_trailing_ws": any(line.rstrip() != line for line in source_lines),
            "standalone_functions": standalone_functions,
            "standalone_function_count": len(standalone_functions),
            "standalone_async": standalone_async,
            "line_count": len(source_lines),
        }
        return (1, ff, None)
