#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/arch_validator.py"
# date="2026-06-26" author="Devin" session_id="phase5-quality"
# context="Project Digital Twin Phase 5 Section 25 Architecture Validator"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="arch_validator.py" domain="twin_arch" authority="ArchValidator"}
# [@SUMMARY]{summary="Architecture validator authority detecting circular deps, layer violations, broken imports and missing entities."}
# [@CLASS]{class="ArchValidator" domain="arch" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="check_circular" type="command"}
# [@METHOD]{method="check_layers" type="command"}
# [@METHOD]{method="check_imports" type="command"}
# [@METHOD]{method="check_missing" type="command"}
# [@METHOD]{method="check_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="Connect" type="helper"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Architecture validator detecting circular deps, layer violations, broken imports, missing entities. VBStyle: Run dispatch, Tuple3, self.state. Has hardcoded constants (DEFAULT_DB_NAME, DEFAULT_LIMIT, LAYER_ORDER, LAYER_KEYWORDS).>][@todos<Consider making LAYER_ORDER and LAYER_KEYWORDS configurable via param.>]}
"""
ArchValidator -- authority for validating architecture integrity of the Project Digital Twin.
Implements Section 25 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: check_circular, check_layers, check_imports, check_missing, check_all.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
LAYER_ORDER = ["gui", "flow", "orch", "engine", "data", "db"]
LAYER_KEYWORDS = {
    "gui": ["gui", "viewer", "tk", "qt", "widget"],
    "flow": ["flow", "plan", "lifecycle"],
    "orch": ["orch", "boot", "agent"],
    "engine": ["engine", "builder", "analyzer", "validator"],
    "data": ["ingest", "registry", "graph"],
    "db": ["db", "sqlite", "config"],
}


class ArchValidator:
    """Authority for architecture validation: cycles, layers, imports, missing entities."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "layer_order": list(LAYER_ORDER),
                "layer_keywords": dict(LAYER_KEYWORDS),
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
        if command == "check_circular":
            return self.CheckCircular(params)
        elif command == "check_layers":
            return self.CheckLayers(params)
        elif command == "check_imports":
            return self.CheckImports(params)
        elif command == "check_missing":
            return self.CheckMissing(params)
        elif command == "check_all":
            return self.CheckAll(params)
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

    def CheckCircular(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                "FROM edges WHERE src_type=dst_type"
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        adj = {}
        edge_map = {}
        for row in rows:
            edge_id, src_type, src_id, dst_type, dst_id, edge_type = row
            key = (src_type, src_id)
            adj.setdefault(key, []).append((dst_type, dst_id))
            edge_map[(key, (dst_type, dst_id))] = edge_id
        cycles = []
        visited = set()
        stack = set()
        path = []

        def dfs(node):
            visited.add(node)
            stack.add(node)
            path.append(node)
            for neighbor in adj.get(node, []):
                if neighbor in stack:
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    cycles.append(
                        {
                            "cycle": [
                                {"type": n[0], "id": n[1]} for n in cycle
                            ],
                            "edge_ids": [
                                edge_map.get((path[i], path[i + 1]), None)
                                for i in range(len(cycle) - 1)
                            ],
                        }
                    )
                elif neighbor not in visited:
                    dfs(neighbor)
            path.pop()
            stack.discard(node)

        for node in list(adj.keys()):
            if node not in visited:
                dfs(node)
        result = {
            "cycles": cycles,
            "count": len(cycles),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def DetectLayer(self, file_name):
        layer_keywords = self.state["config"].get("layer_keywords", LAYER_KEYWORDS)
        lower = file_name.lower()
        for layer, keywords in layer_keywords.items():
            for kw in keywords:
                if kw in lower:
                    return layer
        return None

    def CheckLayers(self, params):
        layer_order = self._p(
            params, "layer_order", self.state["config"].get("layer_order", LAYER_ORDER)
        )
        layer_keywords = self._p(
            params, "layer_keywords", self.state["config"].get("layer_keywords", LAYER_KEYWORDS)
        )
        if layer_order is not None:
            self.state["config"]["layer_order"] = layer_order
        if layer_keywords is not None:
            self.state["config"]["layer_keywords"] = layer_keywords
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT file_id, file_name, imports FROM files WHERE status='active'")
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        file_layer = {}
        for row in rows:
            file_id, file_name, imports_json = row
            file_layer[file_id] = self.DetectLayer(file_name)
        violations = []
        for row in rows:
            file_id, file_name, imports_json = row
            src_layer = file_layer.get(file_id)
            if src_layer is None:
                continue
            imports = []
            if imports_json:
                try:
                    imports = json.loads(imports_json)
                except (ValueError, TypeError):
                    imports = []
            for imp in imports:
                dst_layer = self.DetectLayer(str(imp))
                if dst_layer is None:
                    continue
                if src_layer in layer_order and dst_layer in layer_order:
                    if layer_order.index(src_layer) < layer_order.index(dst_layer):
                        violations.append(
                            {
                                "file_id": file_id,
                                "file_name": file_name,
                                "src_layer": src_layer,
                                "import": imp,
                                "dst_layer": dst_layer,
                                "violation": "layer_import_below",
                            }
                        )
        result = {
            "layer_order": layer_order,
            "violations": violations,
            "count": len(violations),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckImports(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT file_id, file_name, imports, path, status FROM files")
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        active_files = set()
        file_names = set()
        for row in rows:
            file_id, file_name, imports_json, path, status = row
            if status == "active":
                active_files.add(file_name)
                file_names.add(file_name)
        broken = []
        for row in rows:
            file_id, file_name, imports_json, path, status = row
            imports = []
            if imports_json:
                try:
                    imports = json.loads(imports_json)
                except (ValueError, TypeError):
                    imports = []
            for imp in imports:
                imp_str = str(imp)
                imp_base = imp_str.split(".")[0]
                if imp_base + ".py" not in file_names and imp_str not in file_names:
                    broken.append(
                        {
                            "file_id": file_id,
                            "file_name": file_name,
                            "import": imp_str,
                            "reason": "not_in_files_table",
                        }
                    )
        result = {
            "broken_imports": broken,
            "count": len(broken),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckMissing(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT method_name, method_code FROM methods")
            methods = cur.fetchall()
            cur.execute("SELECT class_name FROM classes")
            class_names = set(r[0] for r in cur.fetchall())
            cur.execute("SELECT method_name FROM methods")
            method_names = set(r[0] for r in cur.fetchall())
            cur.execute("SELECT file_name FROM files WHERE status='active'")
            file_names = set(r[0] for r in cur.fetchall())
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        missing_classes = []
        missing_methods = []
        missing_files = []
        for mname, code in methods:
            if not code:
                continue
            for line in code.splitlines():
                stripped = line.strip()
                if stripped.startswith("self.") and "(" in stripped:
                    callee = stripped.split("(")[0].replace("self.", "").strip()
                    if callee and callee not in method_names and callee not in (
                        "Run", "_p", "read_state", "set_config", "Connect"
                    ):
                        missing_methods.append(
                            {"caller": mname, "callee": callee}
                        )
                if "import " in stripped:
                    parts = stripped.split("import")
                    if len(parts) > 1:
                        target = parts[-1].strip().split(" ")[0].split(".")[0]
                        if target and target + ".py" not in file_names:
                            missing_files.append(
                                {"referer": mname, "import": target}
                            )
        for mname, code in methods:
            if not code:
                continue
            for token in code.replace("(", " ").replace(")", " ").split():
                token = token.strip()
                if token and token[0].isupper() and token not in class_names:
                    if token in ("True", "False", "None", "Self"):
                        continue
                    missing_classes.append(
                        {"referer": mname, "class": token}
                    )
        result = {
            "missing_classes": missing_classes[:DEFAULT_LIMIT],
            "missing_methods": missing_methods[:DEFAULT_LIMIT],
            "missing_files": missing_files[:DEFAULT_LIMIT],
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckAll(self, params):
        report = {"checks": {}}
        circular = self.CheckCircular(params)
        report["checks"]["circular"] = (
            circular[1] if circular[0] == 1 else {"error": circular[2]}
        )
        layers = self.CheckLayers(params)
        report["checks"]["layers"] = layers[1] if layers[0] == 1 else {"error": layers[2]}
        imports = self.CheckImports(params)
        report["checks"]["imports"] = imports[1] if imports[0] == 1 else {"error": imports[2]}
        missing = self.CheckMissing(params)
        report["checks"]["missing"] = missing[1] if missing[0] == 1 else {"error": missing[2]}
        total_violations = 0
        for check in report["checks"].values():
            if isinstance(check, dict):
                total_violations += check.get("count", 0)
                total_violations += len(check.get("missing_classes", []))
                total_violations += len(check.get("missing_methods", []))
                total_violations += len(check.get("missing_files", []))
        report["total_violations"] = total_violations
        report["passed"] = total_violations == 0
        report["created"] = datetime.now(timezone.utc).isoformat()
        self.state["results"].append(report)
        return (1, report, None)
