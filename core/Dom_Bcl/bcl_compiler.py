#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_compiler.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="BCL IR IRCompiler — compiles Python files/directories to BCL IR"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_compiler.py" domain="BCL" authority="IRCompiler"}
# [@SUMMARY]{summary="BCL IRCompiler: compiles Python AST to BCL IR blocks. Uses FeatureExtractor, RuleEngine, BCLSerializer."}
# [@CLASS]{class="IRCompiler" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="compile_file" type="command"}
# [@METHOD]{method="compile_directory" type="command"}
# [@METHOD]{method="stable_id" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import ast
import hashlib
import os
import json

from bcl_serializer import BCLSerializer
from bcl_extractor import FeatureExtractor
from bcl_rules import RuleEngine


class IRCompiler:
    """Compile Python files/directories to BCL IR."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "serializer": None,
            "extractor": None,
            "engine": None,
            "results": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            rules = param.get("rules")
            self.state["serializer"] = BCLSerializer()
            self.state["extractor"] = FeatureExtractor()
            self.state["engine"] = RuleEngine(param={"rules": rules or []})
            for key, value in param.items():
                if key != "rules":
                    self.state["config"][key] = value
        else:
            self.state["serializer"] = BCLSerializer()
            self.state["extractor"] = FeatureExtractor()
            self.state["engine"] = RuleEngine()

    def Run(self, command, params=None):
        params = params or {}
        if command == "compile_file":
            return self.CompileFile(params)
        elif command == "compile_directory":
            return self.CompileDirectory(params)
        elif command == "stable_id":
            return self.StableId(params)
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

    def StableId(self, params):
        filepath = self._p(params, "filepath")
        node_type = self._p(params, "node_type")
        name = self._p(params, "name")
        lineno = self._p(params, "lineno")
        if filepath is None or node_type is None or name is None:
            return (0, None, ("MISSING_PARAM", "filepath node_type name required", 0))
        raw = "%s:%s:%s:%s" % (filepath, node_type, name, lineno)
        return (1, hashlib.md5(raw.encode()).hexdigest()[:12], None)

    def CompileFile(self, params):
        filepath = self._p(params, "filepath")
        if filepath is None:
            return (0, None, ("MISSING_PARAM", "filepath required", 0))
        try:
            with open(filepath, "r") as f:
                source = f.read()
        except OSError as exc:
            return (0, None, ("FILE_READ_FAILED", str(exc), 0))
        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as exc:
            return (0, None, ("PARSE_ERROR", str(exc), 0))
        extractor = self.state["extractor"]
        serializer = self.state["serializer"]
        engine = self.state["engine"]
        ff_result = extractor.Run("extract_file_features", {"tree": tree, "source": source, "source_lines": source.splitlines()})
        if ff_result[0] == 0:
            return ff_result
        ff = ff_result[1]
        file_id_result = self.StableId({"filepath": filepath, "node_type": "file", "name": os.path.basename(filepath), "lineno": 1})
        file_id = file_id_result[1]
        fv_result = engine.Run("evaluate_file", {"features": ff})
        file_violations = fv_result[1]["violations"] if fv_result[0] == 1 else []
        bcl_blocks = []
        ser_result = serializer.Run("serialize_file", {"filepath": filepath, "source": source, "features": ff, "file_id": file_id})
        if ser_result[0] == 1:
            bcl_blocks.append(ser_result[1])
        for fv in file_violations:
            vser = serializer.Run("serialize_violation", {"rule_id": fv["rule"], "scope": "file", "parent_id": file_id, "severity": fv["severity"], "description": fv["description"]})
            if vser[0] == 1:
                bcl_blocks.append(vser[1])
        class_nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        total_violations = len(file_violations)
        sym_classes = []
        sym_edges = []
        for node in class_nodes:
            cf_result = extractor.Run("extract_class_features", {"node": node, "source_lines": source.splitlines()})
            if cf_result[0] == 0:
                continue
            cf = cf_result[1]
            cid_result = self.StableId({"filepath": filepath, "node_type": "class", "name": cf["class_name"], "lineno": cf["lineno"]})
            class_id = cid_result[1]
            cv_result = engine.Run("evaluate_class", {"features": cf})
            class_violations = cv_result[1]["violations"] if cv_result[0] == 1 else []
            method_violations_all = []
            for mf in cf["methods"]:
                mv_result = engine.Run("evaluate_method", {"features": mf})
                if mv_result[0] == 1:
                    method_violations_all.extend(mv_result[1]["violations"])
            total_violations += len(class_violations) + len(method_violations_all)
            cser = serializer.Run("serialize_class", {"filepath": filepath, "source": source, "features": cf, "class_id": class_id, "file_id": file_id, "violations": class_violations})
            if cser[0] == 1:
                bcl_blocks.append(cser[1])
            for cv in class_violations:
                vser = serializer.Run("serialize_violation", {"rule_id": cv["rule"], "scope": "class", "parent_id": class_id, "severity": cv["severity"], "description": cv["description"]})
                if vser[0] == 1:
                    bcl_blocks.append(vser[1])
            sym_methods = []
            for mf in cf["methods"]:
                mid_result = self.StableId({"filepath": filepath, "node_type": "method", "name": "%s.%s" % (cf["class_name"], mf["name"]), "lineno": mf["lineno"]})
                method_id = mid_result[1]
                mv = [v for v in method_violations_all if v.get("method") == mf["name"]]
                mser = serializer.Run("serialize_method", {"filepath": filepath, "features": mf, "method_id": method_id, "class_id": class_id, "violations": mv})
                if mser[0] == 1:
                    bcl_blocks.append(mser[1])
                for v in mv:
                    vser = serializer.Run("serialize_violation", {"rule_id": v["rule"], "scope": "method", "parent_id": method_id, "method_name": mf["name"], "severity": v["severity"], "description": v["description"]})
                    if vser[0] == 1:
                        bcl_blocks.append(vser[1])
                sym_methods.append({"name": mf["name"], "id": method_id})
                edge_seq = 0
                for cs in mf.get("call_sites", []):
                    eser = serializer.Run("serialize_edge", {"filepath": filepath, "caller_class": cf["class_name"], "caller_method": mf["name"], "callee": cs["callee"], "edge_type": cs["type"], "caller_method_id": method_id, "call_lineno": "%s_%d" % (cs["lineno"], edge_seq)})
                    if eser[0] == 1:
                        bcl_blocks.append(eser[1])
                    sym_edges.append({"caller_class": cf["class_name"], "caller_method": mf["name"], "callee": cs["callee"], "method_id": method_id})
                    edge_seq += 1
            sym_classes.append({"name": cf["class_name"], "id": class_id, "methods": sym_methods})
            for b in node.bases:
                if isinstance(b, ast.Name):
                    iser = serializer.Run("serialize_inherit", {"filepath": filepath, "child": cf["class_name"], "parent_name": b.id})
                    if iser[0] == 1:
                        bcl_blocks.append(iser[1])
                elif isinstance(b, ast.Attribute):
                    iser = serializer.Run("serialize_inherit", {"filepath": filepath, "child": cf["class_name"], "parent_name": b.attr})
                    if iser[0] == 1:
                        bcl_blocks.append(iser[1])
        result = {
            "filepath": filepath, "file_id": file_id,
            "bcl": "\n\n".join(bcl_blocks), "block_count": len(bcl_blocks),
            "class_count": len(class_nodes),
            "method_count": sum(len(c["methods"]) for c in sym_classes),
            "violation_count": total_violations,
            "symbols": {"classes": sym_classes, "edges": sym_edges, "imports": ff.get("imports", [])},
            "file_hash": hashlib.md5(source.encode()).hexdigest(),
        }
        return (1, result, None)

    def CompileDirectory(self, params):
        dirpath = self._p(params, "dirpath")
        incremental = self._p(params, "incremental", False)
        if dirpath is None:
            return (0, None, ("MISSING_PARAM", "dirpath required", 0))
        cache = {}
        cache_path = os.path.join(dirpath, ".bcl_cache")
        if incremental and os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    cache = json.load(f)
            except (OSError, json.JSONDecodeError):
                cache = {}
        results = []
        skipped = 0
        for root, dirs, files in os.walk(dirpath):
            if ".git" in root or "__pycache__" in root or "node_modules" in root:
                continue
            for fn in sorted(files):
                if not fn.endswith(".py"):
                    continue
                fp = os.path.join(root, fn)
                try:
                    with open(fp, "r") as f:
                        source = f.read()
                    file_hash = hashlib.md5(source.encode()).hexdigest()
                    if incremental and cache.get(fp) == file_hash:
                        skipped += 1
                        results.append({"filepath": fp, "error": "CACHED", "block_count": 0, "class_count": 0, "method_count": 0, "violation_count": 0})
                        continue
                    result = self.CompileFile({"filepath": fp})
                    if result[0] == 1:
                        results.append(result[1])
                        cache[fp] = file_hash
                    else:
                        results.append({"filepath": fp, "error": str(result[2]), "block_count": 0, "class_count": 0, "method_count": 0, "violation_count": 0})
                except Exception as exc:
                    results.append({"filepath": fp, "error": str(exc), "block_count": 0, "class_count": 0, "method_count": 0, "violation_count": 0})
        if incremental:
            try:
                with open(cache_path, "w") as f:
                    json.dump(cache, f)
            except OSError:
                pass
        self.state["results"] = results
        return (1, {"results": results, "skipped": skipped, "compiled": len(results) - skipped}, None)
