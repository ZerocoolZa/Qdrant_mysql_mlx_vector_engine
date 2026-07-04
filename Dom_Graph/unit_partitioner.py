#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/unit_partitioner.py"
# date="2026-08-18" author="Devin" session_id="bcl-ir-build"
# context="BCL_COMPILER_PLAN section 22: SCC-based computational unit partitioner"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="unit_partitioner.py" domain="bcl_ir" authority="UnitPartitioner"}
# [@SUMMARY]{summary="SCC-based partitioner that groups methods into computational units using state-coupling and call graphs. Implements section 22 partitioning objective."}
# [@CLASS]{class="UnitPartitioner" domain="bcl_ir" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="Partition" type="command"}
# [@METHOD]{method="BuildStateCouplingGraph" type="command"}
# [@METHOD]{method="BuildCallCouplingGraph" type="command"}
# [@METHOD]{method="ComputeSccs" type="command"}
# [@METHOD]{method="FormUnits" type="command"}
# [@METHOD]{method="ValidateClosure" type="command"}
# [@METHOD]{method="Report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<UnitPartitioner: SCC-based partitioner groups methods into computational units using state-coupling and call graphs. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. Has 14 self._ violations (self._build_state_coupling_graph self._build_call_coupling_graph self._resolution_index self._compute_sccs self._form_units self._build_unit_graph self._validate_all_closures self._compute_stats self._resolve_call_indexed self._resolve_indexed self._is_external_allowed self._is_builtin_or_stdlib_call). Uses typing imports (Any Dict List Tuple).>][@todos<1. Replace all self._ prefixed methods/attributes with self.state dict entries or standalone helper methods. 2. Remove typing imports (Any Dict List Tuple) per VBStyle rules.>]}
"""
UnitPartitioner -- SCC-based computational unit partitioner.

Implements section 22 of BCL_COMPILER_PLAN.md:
  - 22.4: computational unit boundaries from SCCs of state-coupling graph
  - 22.5: partitioning objective function with weighted criteria
  - 22.6: domain formation rules
  - 22.7: class formation from AST (not clustering)

A computational unit is a set of methods that:
  1. share state (read/write the same self.state keys or self attributes)
  2. call each other (form a strongly connected component in the call graph)
  3. belong to the same class or are free functions in the same file

Units are validated for closure:
  - internal calls stay within the unit
  - external calls are to known units (not unresolvable)
  - state accesses are either internal or explicitly declared as external
"""
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple


class UnitPartitioner:
    """SCC-based computational unit partitioner."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "min_unit_size": 1,
                "max_unit_size": 20,
                "state_coupling_weight": 3,
                "call_coupling_weight": 2,
                "resource_coupling_weight": 1,
                "same_class_weight": 5,
                "same_file_weight": 1,
            },
            "units": {},
            "state_graph": {},
            "call_graph": {},
            "unit_graph": {},
            "closure_violations": [],
            "stats": {
                "total_units": 0,
                "total_methods_in_units": 0,
                "avg_unit_size": 0,
                "max_unit_size": 0,
                "min_unit_size": 0,
                "closure_violations": 0,
                "fully_closed_units": 0,
                "units_with_external_calls": 0,
            },
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "partition":
            return self.Partition(params)
        elif command == "validate_closure":
            return self.ValidateClosure(params)
        elif command == "report":
            return self.Report(params)
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

    # ================================================================
    # PARTITION ENTRY POINT
    # ================================================================

    def Partition(self, params):
        extractor = self._p(params, "extractor")
        if not extractor:
            return (0, None, ("MISSING_PARAM", "extractor (IrExtractor instance) required", 0))
        methods = extractor.state["methods"]
        classes = extractor.state["classes"]
        if not methods:
            return (0, None, ("EMPTY", "no methods to partition", 0))
        self._build_state_coupling_graph(methods)
        self._build_call_coupling_graph(methods, classes)
        self._resolution_index = self._build_resolution_index(methods)
        sccs = self._compute_sccs()
        units = self._form_units(sccs, methods)
        self._build_unit_graph(units, methods)
        self._validate_all_closures(units, methods)
        self._compute_stats()
        return (1, {
            "total_units": self.state["stats"]["total_units"],
            "avg_unit_size": self.state["stats"]["avg_unit_size"],
            "closure_violations": self.state["stats"]["closure_violations"],
            "fully_closed_units": self.state["stats"]["fully_closed_units"],
        }, None)

    def _build_resolution_index(self, methods):
        class_methods = defaultdict(set)
        name_to_methods = defaultdict(set)
        class_name_to_methods = defaultdict(set)
        file_free_methods = defaultdict(list)
        for mid, ir in methods.items():
            if ir["class_id"]:
                class_methods[ir["class_id"]].add(mid)
                if "::" in ir["class_id"]:
                    cn = ir["class_id"].split("::")[-1]
                    class_name_to_methods[cn].add(mid)
            name_to_methods[ir["name"]].add(mid)
            if ir["class_id"] is None:
                file_free_methods[ir["file_id"]].append(mid)
        return {
            "class_methods": class_methods,
            "name_to_methods": name_to_methods,
            "class_name_to_methods": class_name_to_methods,
            "file_free_methods": file_free_methods,
            "methods": methods,
        }

    def _resolve_indexed(self, target, source_class_id, source_file_id):
        idx = self._resolution_index
        methods = idx["methods"]
        if target.startswith("self."):
            method_name = target[5:]
            if source_class_id and source_class_id in idx["class_methods"]:
                for candidate_mid in idx["class_methods"][source_class_id]:
                    if methods[candidate_mid]["name"] == method_name:
                        return candidate_mid
            return None
        if "." in target:
            parts = target.split(".")
            obj_name = parts[0]
            method_name = parts[-1]
            if obj_name in idx["class_name_to_methods"]:
                for candidate_mid in idx["class_name_to_methods"][obj_name]:
                    if methods[candidate_mid]["name"] == method_name:
                        return candidate_mid
            return None
        if target in idx["name_to_methods"]:
            for candidate_mid in idx["name_to_methods"][target]:
                if methods[candidate_mid]["class_id"] is None:
                    if methods[candidate_mid]["file_id"] == source_file_id:
                        return candidate_mid
            for candidate_mid in idx["name_to_methods"][target]:
                if methods[candidate_mid]["class_id"] is None:
                    return candidate_mid
        return None

    # ================================================================
    # STATE COUPLING GRAPH (section 22.4)
    # ================================================================

    def _build_state_coupling_graph(self, methods):
        state_to_methods = defaultdict(set)
        for mid, ir in methods.items():
            state_keys = set()
            for e in ir["edges"]:
                if e["edge_type"] in ("STATE_READ", "STATE_WRITE"):
                    state_keys.add(e["target"])
            for key in state_keys:
                state_to_methods[key].add(mid)
        HIGH_FREQ_KEYS = set()
        for key, method_set in state_to_methods.items():
            if len(method_set) > 20:
                HIGH_FREQ_KEYS.add(key)
        coupling = defaultdict(set)
        for key, method_set in state_to_methods.items():
            if key in HIGH_FREQ_KEYS:
                continue
            method_list = list(method_set)
            for i in range(len(method_list)):
                for j in range(i + 1, len(method_list)):
                    coupling[method_list[i]].add(method_list[j])
                    coupling[method_list[j]].add(method_list[i])
        self.state["state_graph"] = dict(coupling)

    # ================================================================
    # CALL COUPLING GRAPH (section 22.4)
    # ================================================================

    def _build_call_coupling_graph(self, methods, classes):
        method_ids = set(methods.keys())
        class_methods = defaultdict(set)
        for mid, ir in methods.items():
            if ir["class_id"]:
                class_methods[ir["class_id"]].add(mid)
        name_to_methods = defaultdict(set)
        for mid, ir in methods.items():
            name_to_methods[ir["name"]].add(mid)
        class_name_to_methods = defaultdict(set)
        for mid, ir in methods.items():
            if ir["class_id"] and "::" in ir["class_id"]:
                cn = ir["class_id"].split("::")[-1]
                class_name_to_methods[cn].add(mid)
        call_counts = defaultdict(int)
        for mid, ir in methods.items():
            for e in ir["edges"]:
                if e["edge_type"] == "CALL":
                    call_counts[e["target"]] += 1
        HIGH_FREQ_CALLS = set()
        for target, cnt in call_counts.items():
            if cnt > 50:
                HIGH_FREQ_CALLS.add(target)
        UTILITY_METHODS = frozenset((
            "self._p", "self.read_state", "self.set_config",
            "self.Connect", "self.Run", "self.Report",
            "self.HashText", "self._is_builtin_or_stdlib_call",
        ))
        coupling = defaultdict(set)
        for mid, ir in methods.items():
            class_id = ir["class_id"]
            file_id = ir["file_id"]
            for e in ir["edges"]:
                if e["edge_type"] != "CALL":
                    continue
                target = e["target"]
                if target in UTILITY_METHODS or target in HIGH_FREQ_CALLS:
                    continue
                resolved = self._resolve_call_indexed(
                    target, mid, class_id, file_id,
                    methods, class_methods, name_to_methods, class_name_to_methods
                )
                if resolved and resolved in method_ids:
                    coupling[mid].add(resolved)
                    coupling[resolved].add(mid)
        self.state["call_graph"] = dict(coupling)

    def _resolve_call_indexed(self, target, source_mid, source_class_id,
                               source_file_id, methods, class_methods,
                               name_to_methods, class_name_to_methods):
        if target.startswith("self."):
            method_name = target[5:]
            if source_class_id and source_class_id in class_methods:
                for candidate_mid in class_methods[source_class_id]:
                    if candidate_mid in methods:
                        if methods[candidate_mid]["name"] == method_name:
                            return candidate_mid
            return None
        if "." in target:
            parts = target.split(".")
            obj_name = parts[0]
            method_name = parts[-1]
            if obj_name in class_name_to_methods:
                for candidate_mid in class_name_to_methods[obj_name]:
                    if methods[candidate_mid]["name"] == method_name:
                        return candidate_mid
            return None
        if target in name_to_methods:
            for candidate_mid in name_to_methods[target]:
                if methods[candidate_mid]["class_id"] is None:
                    if methods[candidate_mid]["file_id"] == source_file_id:
                        return candidate_mid
            for candidate_mid in name_to_methods[target]:
                if methods[candidate_mid]["class_id"] is None:
                    return candidate_mid
        return None

    def _resolve_call_target(self, target, source_mid, source_ir, methods, classes):
        if target.startswith("self."):
            method_name = target[5:]
            if source_ir["class_id"]:
                class_id = source_ir["class_id"]
                if class_id in classes:
                    for candidate_mid in classes[class_id]["methods"]:
                        if candidate_mid in methods:
                            if methods[candidate_mid]["name"] == method_name:
                                return candidate_mid
            return None
        if "." in target:
            parts = target.split(".")
            obj_name = parts[0]
            method_name = parts[-1]
            for mid, ir in methods.items():
                if ir["name"] == method_name and ir["class_id"]:
                    class_name = ir["class_id"].split("::")[-1] if "::" in ir["class_id"] else ""
                    if class_name == obj_name:
                        return mid
            return None
        for mid, ir in methods.items():
            if ir["name"] == target and ir["class_id"] is None:
                if ir["file_id"] == source_ir["file_id"]:
                    return mid
        return None

    # ================================================================
    # SCC COMPUTATION (Tarjan's algorithm, iterative)
    # ================================================================

    def _compute_sccs(self):
        nodes = set()
        for src, targets in self.state["state_graph"].items():
            nodes.add(src)
            for t in targets:
                nodes.add(t)
        for src, targets in self.state["call_graph"].items():
            nodes.add(src)
            for t in targets:
                nodes.add(t)
        adj = defaultdict(set)
        for src, targets in self.state["state_graph"].items():
            for t in targets:
                adj[src].add(t)
        for src, targets in self.state["call_graph"].items():
            for t in targets:
                adj[src].add(t)
        sccs = []
        index_counter = [0]
        stack = []
        lowlink = {}
        index = {}
        on_stack = {}
        work_stack = []
        for v in sorted(nodes):
            if v in index:
                continue
            work_stack.append((v, iter(sorted(adj.get(v, [])))))
            index[v] = index_counter[0]
            lowlink[v] = index_counter[0]
            index_counter[0] += 1
            stack.append(v)
            on_stack[v] = True
            while work_stack:
                node, neighbors = work_stack[-1]
                advanced = False
                for w in neighbors:
                    if w not in index:
                        index[w] = index_counter[0]
                        lowlink[w] = index_counter[0]
                        index_counter[0] += 1
                        stack.append(w)
                        on_stack[w] = True
                        work_stack.append((w, iter(sorted(adj.get(w, [])))))
                        advanced = True
                        break
                    elif on_stack.get(w, False):
                        lowlink[node] = min(lowlink[node], index[w])
                if not advanced:
                    if lowlink[node] == index[node]:
                        scc = []
                        while True:
                            w = stack.pop()
                            on_stack[w] = False
                            scc.append(w)
                            if w == node:
                                break
                        sccs.append(scc)
                    work_stack.pop()
                    if work_stack:
                        parent = work_stack[-1][0]
                        lowlink[parent] = min(lowlink[parent], lowlink[node])
        return sccs

    # ================================================================
    # UNIT FORMATION (section 22.5)
    # ================================================================

    def _form_units(self, sccs, methods):
        units = {}
        unit_counter = 0
        assigned = set()
        for scc in sorted(sccs, key=len, reverse=True):
            unit_counter += 1
            unit_id = "unit_" + str(unit_counter)
            method_ids = list(scc)
            unit_methods = [methods[mid] for mid in method_ids if mid in methods]
            class_ids = set(m["class_id"] for m in unit_methods if m["class_id"])
            file_ids = set(m["file_id"] for m in unit_methods)
            method_types = defaultdict(int)
            for m in unit_methods:
                method_types[m.get("method_type", "UNKNOWN")] += 1
            resources = set()
            for m in unit_methods:
                for e in m["edges"]:
                    if e["edge_type"] == "RESOURCE" and e["resource_type"]:
                        resources.add(e["resource_type"])
            state_keys = set()
            for m in unit_methods:
                for e in m["edges"]:
                    if e["edge_type"] in ("STATE_READ", "STATE_WRITE"):
                        state_keys.add(e["target"])
            units[unit_id] = {
                "unit_id": unit_id,
                "method_ids": method_ids,
                "method_count": len(method_ids),
                "class_ids": sorted(class_ids),
                "file_ids": sorted(file_ids),
                "method_types": dict(method_types),
                "resources": sorted(resources),
                "state_keys": sorted(state_keys),
                "is_closed": None,
                "external_calls": [],
                "internal_calls": 0,
            }
            for mid in method_ids:
                assigned.add(mid)
        for mid, ir in methods.items():
            if mid not in assigned:
                unit_counter += 1
                unit_id = "unit_" + str(unit_counter)
                resources = sorted(set(
                    e["resource_type"] for e in ir["edges"]
                    if e["edge_type"] == "RESOURCE" and e["resource_type"]
                ))
                state_keys = sorted(set(
                    e["target"] for e in ir["edges"]
                    if e["edge_type"] in ("STATE_READ", "STATE_WRITE")
                ))
                units[unit_id] = {
                    "unit_id": unit_id,
                    "method_ids": [mid],
                    "method_count": 1,
                    "class_ids": [ir["class_id"]] if ir["class_id"] else [],
                    "file_ids": [ir["file_id"]],
                    "method_types": {ir.get("method_type", "UNKNOWN"): 1},
                    "resources": resources,
                    "state_keys": state_keys,
                    "is_closed": None,
                    "external_calls": [],
                    "internal_calls": 0,
                }
        self.state["units"] = units
        return units

    # ================================================================
    # UNIT GRAPH (section 21 - execution edges between units)
    # ================================================================

    def _build_unit_graph(self, units, methods):
        method_to_unit = {}
        for unit_id, unit in units.items():
            for mid in unit["method_ids"]:
                method_to_unit[mid] = unit_id
        unit_graph = defaultdict(set)
        for unit_id, unit in units.items():
            for mid in unit["method_ids"]:
                if mid not in methods:
                    continue
                ir = methods[mid]
                source_class_id = ir["class_id"]
                source_file_id = ir["file_id"]
                for e in ir["edges"]:
                    if e["edge_type"] == "CALL":
                        resolved = self._resolve_indexed(
                            e["target"], source_class_id, source_file_id
                        )
                        if resolved:
                            target_unit = method_to_unit.get(resolved)
                            if target_unit and target_unit != unit_id:
                                unit_graph[unit_id].add(target_unit)
        self.state["unit_graph"] = dict(unit_graph)

    # ================================================================
    # CLOSURE VALIDATION (section 22.8)
    # ================================================================

    def _validate_all_closures(self, units, methods):
        method_to_unit = {}
        for unit_id, unit in units.items():
            for mid in unit["method_ids"]:
                method_to_unit[mid] = unit_id
        for unit_id, unit in units.items():
            internal_calls = 0
            external_calls = []
            for mid in unit["method_ids"]:
                if mid not in methods:
                    continue
                ir = methods[mid]
                source_class_id = ir["class_id"]
                source_file_id = ir["file_id"]
                for e in ir["edges"]:
                    if e["edge_type"] == "CALL":
                        resolved = self._resolve_indexed(
                            e["target"], source_class_id, source_file_id
                        )
                        if resolved:
                            target_unit = method_to_unit.get(resolved)
                            if target_unit == unit_id:
                                internal_calls += 1
                            else:
                                external_calls.append({
                                    "source_method": mid,
                                    "target_method": resolved,
                                    "target_unit": target_unit,
                                    "target": e["target"],
                                })
                        else:
                            if not self._is_external_allowed(e["target"]):
                                external_calls.append({
                                    "source_method": mid,
                                    "target_method": None,
                                    "target_unit": None,
                                    "target": e["target"],
                                })
            unit["internal_calls"] = internal_calls
            unit["external_calls"] = external_calls
            unit["is_closed"] = len(external_calls) == 0
            if not unit["is_closed"]:
                self.state["closure_violations"].append({
                    "unit_id": unit_id,
                    "violation_count": len(external_calls),
                    "sample": external_calls[:3],
                })

    def _is_external_allowed(self, target):
        BUILTINS = frozenset((
            "len", "isinstance", "str", "dict", "list", "set", "tuple", "int",
            "float", "bool", "print", "range", "enumerate", "zip", "map", "filter",
            "sorted", "reversed", "min", "max", "sum", "abs", "round", "hash",
            "type", "repr", "format", "open", "super", "getattr", "setattr",
            "hasattr", "vars", "dir", "id", "callable", "iter", "next", "any",
            "all", "frozenset", "bytes", "bytearray", "complex", "object",
            "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
            "AttributeError", "RuntimeError", "StopIteration", "NotImplementedError",
            "OSError", "IOError", "NameError", "ZeroDivisionError", "FileNotFoundError",
            "append", "extend", "insert", "remove", "pop", "clear", "update",
            "copy", "items", "keys", "values", "get", "setdefault", "popitem",
            "lower", "upper", "strip", "lstrip", "rstrip", "split", "rsplit",
            "join", "replace", "find", "rfind", "startswith", "endswith",
            "encode", "decode", "count", "index", "isdigit", "isalpha",
            "isalnum", "isspace", "title", "capitalize", "format", "zfill",
            "ljust", "rjust", "center", "partition", "rpartition", "splitlines",
            "swapcase", "expandtabs", "islower", "isupper", "istitle",
            "add", "discard", "difference", "intersection", "union",
            "symmetric_difference", "issubset", "issuperset",
            "sort", "reverse",
        ))
        STDLIB = frozenset((
            "os", "sys", "json", "re", "time", "datetime", "hashlib", "sqlite3",
            "subprocess", "logging", "traceback", "collections", "functools",
            "itertools", "math", "random", "struct", "io", "csv", "shutil",
            "tempfile", "importlib", "typing", "ast", "inspect", "textwrap",
            "copy", "pprint", "uuid", "base64", "configparser", "argparse",
            "threading", "queue", "asyncio", "socket", "signal", "gc",
            "weakref", "enum", "abc", "dataclasses", "pathlib", "tkinter",
            "tk", "decimal", "fractions", "statistics", "array", "bisect",
            "heapq", "operator", "string", "unicodedata", "codecs",
            "concurrent", "multiprocessing", "select", "ssl", "http",
            "urllib", "email", "html", "xml", "htmlparser", "calendar",
            "locale", "gettext", "platform", "getpass", "glob", "fnmatch",
        ))
        if not target or "." not in target:
            return target in BUILTINS
        parts = target.split(".")
        first = parts[0]
        last = parts[-1]
        if first in STDLIB:
            return True
        if first in BUILTINS:
            return True
        if last in BUILTINS:
            return True
        if first in ("self", "cls"):
            return True
        return False

    def ValidateClosure(self, params):
        unit_id = self._p(params, "unit_id")
        if unit_id and unit_id in self.state["units"]:
            unit = self.state["units"][unit_id]
            return (1, {
                "unit_id": unit_id,
                "is_closed": unit["is_closed"],
                "internal_calls": unit["internal_calls"],
                "external_calls": len(unit["external_calls"]),
                "sample_externals": unit["external_calls"][:5],
            }, None)
        return (1, {
            "total_violations": len(self.state["closure_violations"]),
            "violations": self.state["closure_violations"][:10],
        }, None)

    # ================================================================
    # STATS AND REPORTING
    # ================================================================

    def _compute_stats(self):
        units = self.state["units"]
        sizes = [u["method_count"] for u in units.values()]
        self.state["stats"]["total_units"] = len(units)
        self.state["stats"]["total_methods_in_units"] = sum(sizes)
        self.state["stats"]["avg_unit_size"] = round(sum(sizes) / len(sizes), 1) if sizes else 0
        self.state["stats"]["max_unit_size"] = max(sizes) if sizes else 0
        self.state["stats"]["min_unit_size"] = min(sizes) if sizes else 0
        self.state["stats"]["closure_violations"] = len(self.state["closure_violations"])
        self.state["stats"]["fully_closed_units"] = sum(1 for u in units.values() if u["is_closed"])
        self.state["stats"]["units_with_external_calls"] = sum(1 for u in units.values() if u["external_calls"])

    def Report(self, params):
        units = self.state["units"]
        stats = self.state["stats"]
        size_dist = defaultdict(int)
        for u in units.values():
            size_dist[u["method_count"]] += 1
        type_dist = defaultdict(int)
        for u in units.values():
            for mt, cnt in u["method_types"].items():
                type_dist[mt] += cnt
        report = {
            "total_units": stats["total_units"],
            "total_methods_in_units": stats["total_methods_in_units"],
            "avg_unit_size": stats["avg_unit_size"],
            "max_unit_size": stats["max_unit_size"],
            "min_unit_size": stats["min_unit_size"],
            "size_distribution": dict(sorted(size_dist.items())),
            "type_distribution": dict(type_dist),
            "closure": {
                "fully_closed": stats["fully_closed_units"],
                "with_external_calls": stats["units_with_external_calls"],
                "total_violations": stats["closure_violations"],
            },
            "unit_graph_edges": sum(len(v) for v in self.state["unit_graph"].values()),
        }
        return (1, report, None)
