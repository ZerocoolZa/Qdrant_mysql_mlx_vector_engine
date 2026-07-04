#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_analyzer.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstyle-fix"
# context="BCL IR PostAnalyzer — cross-file analysis: dead code, cycles, hot paths"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_analyzer.py" domain="BCL" authority="PostAnalyzer"}
# [@SUMMARY]{summary="BCL PostAnalyzer: dead code detection, cycle detection, hot paths, cross-file edges, file dependencies."}
# [@CLASS]{class="PostAnalyzer" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="post_analyze" type="command"}
# [@METHOD]{method="find_cycles" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import hashlib
from collections import Counter

from bcl_serializer import BCLSerializer


class PostAnalyzer:
    """Cross-file analysis: dead code, cycles, hot paths."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "analysis": None,
            "serializer": BCLSerializer(),
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "post_analyze":
            return self.PostAnalyze(params)
        elif command == "find_cycles":
            return self.FindCycles(params)
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

    def StableId(self, filepath, node_type, name, lineno):
        raw = "%s:%s:%s:%s" % (filepath, node_type, name, lineno)
        return (1, hashlib.md5(raw.encode()).hexdigest()[:12], None)

    def FindCycles(self, params):
        node = self._p(params, "node")
        graph = self._p(params, "graph")
        visited = self._p(params, "visited", set())
        path = self._p(params, "path", [])
        cycles = self._p(params, "cycles", [])
        if node is None or graph is None:
            return (0, None, ("MISSING_PARAM", "node and graph required", 0))
        if node in path:
            idx = path.index(node)
            cycle = path[idx:]
            if len(cycle) >= 2:
                cycles.append(cycle)
            return (1, cycles, None)
        if node in visited:
            return (1, cycles, None)
        visited.add(node)
        path.append(node)
        for neighbor in graph.get(node, set()):
            self.FindCycles({"node": neighbor, "graph": graph, "visited": visited, "path": path, "cycles": cycles})
        path.pop()
        return (1, cycles, None)

    def PostAnalyze(self, params):
        results = self._p(params, "results")
        if results is None:
            return (0, None, ("MISSING_PARAM", "results required", 0))
        serializer = self.state["serializer"]
        global_methods = {}
        global_classes = {}
        all_edges = []
        file_imports = {}
        for r in results:
            if "error" in r:
                continue
            fp = r["filepath"]
            syms = r.get("symbols", {})
            file_imports[fp] = syms.get("imports", [])
            for cls in syms.get("classes", []):
                global_classes[cls["name"]] = {"id": cls["id"], "file": fp, "methods": {m["name"]: m["id"] for m in cls["methods"]}}
                for m in cls["methods"]:
                    global_methods[m["name"]] = {"id": m["id"], "class": cls["name"], "file": fp}
            for e in syms.get("edges", []):
                e["caller_file"] = fp
                all_edges.append(e)
        incoming = Counter()
        for e in all_edges:
            incoming[e["callee"]] += 1
        dead_methods = []
        for r in results:
            if "error" in r:
                continue
            fp = r["filepath"]
            for cls in r.get("symbols", {}).get("classes", []):
                for m in cls["methods"]:
                    if m["name"] not in ("__init__", "Run", "read_state", "set_config") and incoming.get(m["name"], 0) == 0:
                        dead_methods.append({"filepath": fp, "class": cls["name"], "method": m["name"], "id": m["id"]})
        hot_paths = []
        for method_name, count in incoming.most_common(20):
            if count >= 3 and method_name in global_methods:
                gm = global_methods[method_name]
                hot_paths.append({"filepath": gm["file"], "class": gm["class"], "method": method_name, "id": gm["id"], "incoming": count})
        method_to_methods = {}
        for e in all_edges:
            caller_key = e["method_id"]
            if caller_key not in method_to_methods:
                method_to_methods[caller_key] = set()
            if e["callee"] in global_methods:
                method_to_methods[caller_key].add(global_methods[e["callee"]]["id"])
        cycles = []
        for start_id in method_to_methods:
            self.FindCycles({"node": start_id, "graph": method_to_methods, "visited": set(), "path": [], "cycles": cycles})
        unique_cycles = []
        seen_cycle_sigs = set()
        for c in cycles:
            sig = frozenset(c)
            if sig not in seen_cycle_sigs:
                seen_cycle_sigs.add(sig)
                unique_cycles.append(c)
        xedges = []
        seen_xedges = set()
        for e in all_edges:
            if e["callee"] in global_classes:
                target_cls = global_classes[e["callee"]]
                caller_fp = e.get("caller_file", "")
                if target_cls["file"] != caller_fp:
                    xkey = (e["caller_class"], e["caller_method"], e["callee"], target_cls["file"])
                    if xkey not in seen_xedges:
                        seen_xedges.add(xkey)
                        xedges.append({"caller_file": caller_fp, "caller_class": e["caller_class"], "caller_method": e["caller_method"], "callee": e["callee"], "resolved_file": target_cls["file"], "resolved_class": target_cls["file"], "method_id": e["method_id"]})
        file_deps = []
        seen_deps = set()
        for fp, imps in file_imports.items():
            for imp in imps:
                mod = imp.get("module", "")
                mod_base = mod.replace(".", "/")
                for other_fp in file_imports:
                    if other_fp != fp:
                        other_base = os.path.basename(other_fp).replace(".py", "")
                        if mod_base == other_base or mod == other_base:
                            dep_key = (fp, other_fp, mod)
                            if dep_key not in seen_deps:
                                seen_deps.add(dep_key)
                                file_deps.append({"src": fp, "dst": other_fp, "import": mod})
        extra_blocks = []
        for dm in dead_methods:
            sid = self.StableId(dm["filepath"], "deadcode", "%s.%s" % (dm["class"], dm["method"]), dm["id"][:6])
            ser = serializer.Run("serialize_metric", {"filepath": dm["filepath"], "key": "deadcode", "value": dm["method"], "file_id": dm["id"]})
            if ser[0] == 1:
                extra_blocks.append(ser[1])
        for hp in hot_paths:
            ser = serializer.Run("serialize_metric", {"filepath": hp["filepath"], "key": "hotpath_%s" % hp["method"], "value": hp["incoming"], "file_id": hp["id"]})
            if ser[0] == 1:
                extra_blocks.append(ser[1])
        for c in unique_cycles[:50]:
            cycle_str = "->".join(c)
            sid = self.StableId("global", "cycle", cycle_str, len(c))
            ser = serializer.Run("serialize_metric", {"filepath": "global", "key": "cycle", "value": cycle_str, "file_id": sid[1]})
            if ser[0] == 1:
                extra_blocks.append(ser[1])
        for xe in xedges:
            ser = serializer.Run("serialize_metric", {"filepath": xe["caller_file"], "key": "xedge_%s" % xe["callee"], "value": xe["resolved_class"], "file_id": xe["method_id"]})
            if ser[0] == 1:
                extra_blocks.append(ser[1])
        for fd in file_deps:
            sid = self.StableId(fd["src"], "file", os.path.basename(fd["src"]), 1)
            ser = serializer.Run("serialize_metric", {"filepath": fd["src"], "key": "dep", "value": fd["import"], "file_id": sid[1]})
            if ser[0] == 1:
                extra_blocks.append(ser[1])
        file_dep_graph = {}
        for fd in file_deps:
            if fd["src"] not in file_dep_graph:
                file_dep_graph[fd["src"]] = set()
            file_dep_graph[fd["src"]].add(fd["dst"])
        circ_imports = []
        for start_fp in file_dep_graph:
            self.FindCycles({"node": start_fp, "graph": file_dep_graph, "visited": set(), "path": [], "cycles": circ_imports})
        unique_circ = []
        seen_circ_sigs = set()
        for c in circ_imports:
            sig = frozenset(c)
            if sig not in seen_circ_sigs and len(c) >= 2:
                seen_circ_sigs.add(sig)
                unique_circ.append(c)
        for c in unique_circ[:20]:
            circ_str = " -> ".join(os.path.basename(f) for f in c)
            sid_list = []
            for f in c:
                sid = self.StableId(f, "file", os.path.basename(f), 1)
                sid_list.append(sid[1])
            ser = serializer.Run("serialize_metric", {"filepath": "import", "key": "circ_import", "value": circ_str, "file_id": sid_list[0] if sid_list else "0"})
            if ser[0] == 1:
                extra_blocks.append(ser[1])
        analysis = {
            "extra_bcl": "\n\n".join(extra_blocks),
            "extra_count": len(extra_blocks),
            "dead_count": len(dead_methods),
            "cycle_count": len(unique_cycles),
            "circ_import_count": len(unique_circ),
            "hotpath_count": len(hot_paths),
            "xedge_count": len(xedges),
            "dep_count": len(file_deps),
            "total_methods": len(global_methods),
            "total_classes": len(global_classes),
            "total_edges": len(all_edges),
        }
        self.state["analysis"] = analysis
        return (1, analysis, None)
