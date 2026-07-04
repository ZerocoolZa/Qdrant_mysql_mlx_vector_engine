#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/bcl_projector.py"
# date="2026-08-18" author="Devin" session_id="bcl-ir-build"
# context="BCL_COMPILER_PLAN section 19: BCL projector that generates .bcl view from classified IR"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_projector.py" domain="bcl_ir" authority="BclProjector"}
# [@SUMMARY]{summary="BCL projector that generates derived .bcl view files from classified METHOD_IR records. BCL is a view, not the source of truth."}
# [@CLASS]{class="BclProjector" domain="bcl_ir" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="ProjectAll" type="command"}
# [@METHOD]{method="ProjectClass" type="command"}
# [@METHOD]{method="ProjectMethod" type="command"}
# [@METHOD]{method="ProjectDomain" type="command"}
# [@METHOD]{method="ProjectFile" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
"""
BclProjector -- generates derived BCL view from classified METHOD_IR.

Implements section 19.4 (BCL is a derived projection, not source of truth):
  - @CLASS blocks from AST-extracted classes
  - @METHOD blocks from classified IR
  - @DOMAIN blocks from domain clusters
  - @DEPENDENCIES from call + execution edges
  - @STATE_USAGE from state-coupling graph
  - @RESOURCE_USAGE from resource graph
  - certainty tier annotations [CERTAIN]/[PROBABLE]/[UNKNOWN]

BCL is GENERATED, not hand-written. Editing BCL does not change code.
Code changes --> IR changes --> BCL regenerates.
"""
from typing import Any, Dict, List, Tuple
from collections import defaultdict


class BclProjector:
    """Generates derived BCL view from classified METHOD_IR records."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "output_dir": None,
                "include_edges": True,
                "include_certainty": True,
                "include_deterministic_flag": True,
            },
            "bcl_output": {},  # class_id -> bcl text
            "domain_output": {},  # domain_id -> bcl text
            "file_output": {},  # file_id -> bcl text
            "stats": {
                "classes_projected": 0,
                "methods_projected": 0,
                "domains_projected": 0,
            },
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "project_all":
            return self.ProjectAll(params)
        elif command == "project_class":
            return self.ProjectClass(params)
        elif command == "project_method":
            return self.ProjectMethod(params)
        elif command == "project_domain":
            return self.ProjectDomain(params)
        elif command == "project_file":
            return self.ProjectFile(params)
        elif command == "project_unit":
            return self.ProjectUnit(params)
        elif command == "project_units":
            return self.ProjectUnits(params)
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
    # PROJECTION ENTRY POINTS
    # ================================================================

    def ProjectAll(self, params):
        extractor = self._p(params, "extractor")
        if not extractor:
            return (0, None, ("MISSING_PARAM", "extractor (IrExtractor instance) required", 0))
        methods = extractor.state["methods"]
        classes = extractor.state["classes"]
        for class_id, cls_data in classes.items():
            class_methods = [methods[mid] for mid in cls_data["methods"] if mid in methods]
            bcl_text = self._generate_class_bcl(cls_data, class_methods)
            self.state["bcl_output"][class_id] = bcl_text
            self.state["stats"]["classes_projected"] += 1
            self.state["stats"]["methods_projected"] += len(class_methods)
        free_methods = [ir for mid, ir in methods.items() if ir["class_id"] is None]
        if free_methods:
            bcl_text = self._generate_free_methods_bcl(free_methods)
            self.state["bcl_output"]["__free_functions__"] = bcl_text
        domains = self._compute_domains(extractor)
        for domain_id, domain_classes in domains.items():
            bcl_text = self._generate_domain_bcl(domain_id, domain_classes, classes, methods)
            self.state["domain_output"][domain_id] = bcl_text
            self.state["stats"]["domains_projected"] += 1
        return (1, {
            "classes_projected": self.state["stats"]["classes_projected"],
            "methods_projected": self.state["stats"]["methods_projected"],
            "domains_projected": self.state["stats"]["domains_projected"],
            "bcl_output_keys": list(self.state["bcl_output"].keys())[:10],
        }, None)

    def ProjectClass(self, params):
        extractor = self._p(params, "extractor")
        class_id = self._p(params, "class_id")
        if not extractor or not class_id:
            return (0, None, ("MISSING_PARAM", "extractor and class_id required", 0))
        if class_id not in extractor.state["classes"]:
            return (0, None, ("NOT_FOUND", class_id, 0))
        cls_data = extractor.state["classes"][class_id]
        methods = [extractor.state["methods"][mid] for mid in cls_data["methods"] if mid in extractor.state["methods"]]
        bcl_text = self._generate_class_bcl(cls_data, methods)
        self.state["bcl_output"][class_id] = bcl_text
        return (1, {"class_id": class_id, "bcl": bcl_text}, None)

    def ProjectMethod(self, params):
        extractor = self._p(params, "extractor")
        method_id = self._p(params, "method_id")
        if not extractor or not method_id:
            return (0, None, ("MISSING_PARAM", "extractor and method_id required", 0))
        if method_id not in extractor.state["methods"]:
            return (0, None, ("NOT_FOUND", method_id, 0))
        ir = extractor.state["methods"][method_id]
        bcl_text = self._generate_method_bcl(ir)
        return (1, {"method_id": method_id, "bcl": bcl_text}, None)

    def ProjectDomain(self, params):
        extractor = self._p(params, "extractor")
        if not extractor:
            return (0, None, ("MISSING_PARAM", "extractor required", 0))
        domains = self._compute_domains(extractor)
        domain_id = self._p(params, "domain_id")
        if domain_id and domain_id in domains:
            bcl_text = self._generate_domain_bcl(domain_id, domains[domain_id],
                                                  extractor.state["classes"],
                                                  extractor.state["methods"])
            return (1, {"domain_id": domain_id, "bcl": bcl_text}, None)
        results = {}
        for did, dclasses in domains.items():
            results[did] = self._generate_domain_bcl(did, dclasses,
                                                      extractor.state["classes"],
                                                      extractor.state["methods"])
        return (1, results, None)

    def ProjectFile(self, params):
        extractor = self._p(params, "extractor")
        file_id = self._p(params, "file_id")
        if not extractor or not file_id:
            return (0, None, ("MISSING_PARAM", "extractor and file_id required", 0))
        if file_id not in extractor.state["files"]:
            return (0, None, ("NOT_FOUND", file_id, 0))
        file_data = extractor.state["files"][file_id]
        classes = [extractor.state["classes"][cid] for cid in file_data["classes"] if cid in extractor.state["classes"]]
        methods = [extractor.state["methods"][mid] for mid in file_data["methods"] if mid in extractor.state["methods"]]
        bcl_text = self._generate_file_bcl(file_data, classes, methods)
        self.state["file_output"][file_id] = bcl_text
        return (1, {"file_id": file_id, "bcl": bcl_text}, None)

    def ProjectUnit(self, params):
        extractor = self._p(params, "extractor")
        partitioner = self._p(params, "partitioner")
        unit_id = self._p(params, "unit_id")
        if not extractor or not partitioner or not unit_id:
            return (0, None, ("MISSING_PARAM", "extractor, partitioner, unit_id required", 0))
        if unit_id not in partitioner.state["units"]:
            return (0, None, ("NOT_FOUND", unit_id, 0))
        unit = partitioner.state["units"][unit_id]
        methods = [extractor.state["methods"][mid] for mid in unit["method_ids"] if mid in extractor.state["methods"]]
        bcl_text = self._generate_unit_bcl(unit, methods, partitioner)
        return (1, {"unit_id": unit_id, "bcl": bcl_text}, None)

    def ProjectUnits(self, params):
        extractor = self._p(params, "extractor")
        partitioner = self._p(params, "partitioner")
        if not extractor or not partitioner:
            return (0, None, ("MISSING_PARAM", "extractor and partitioner required", 0))
        units = partitioner.state["units"]
        output = {}
        big_units = [(uid, u) for uid, u in units.items() if u["method_count"] >= 3]
        big_units.sort(key=lambda x: -x[1]["method_count"])
        for uid, unit in big_units[:50]:
            methods = [extractor.state["methods"][mid] for mid in unit["method_ids"] if mid in extractor.state["methods"]]
            bcl_text = self._generate_unit_bcl(unit, methods, partitioner)
            output[uid] = bcl_text
        return (1, {"unit_count": len(output), "bcl_output": output}, None)

    # ================================================================
    # BCL GENERATION (private)
    # ================================================================

    def _generate_class_bcl(self, cls_data, methods):
        lines = []
        lines.append("@CLASS " + cls_data["name"])
        if cls_data["bases"]:
            lines.append("  @INHERITS " + ", ".join(cls_data["bases"]))
        lines.append("  @FILE " + cls_data["file_id"].split("/")[-1])
        lines.append("  @METHOD_COUNT " + str(len(methods)))
        lines.append("")
        for ir in methods:
            method_bcl = self._generate_method_bcl(ir)
            for mline in method_bcl.split("\n"):
                lines.append("  " + mline)
            lines.append("")
        return "\n".join(lines)

    def _generate_method_bcl(self, ir):
        lines = []
        mtype = ir.get("method_type", "UNKNOWN")
        det = ir.get("deterministic_subset", False)
        lines.append("@METHOD " + ir["name"] + "(" + mtype + ")")
        inputs_str = ", ".join(
            (p["type"] + " " + p["name"]) if p.get("type") else p["name"]
            for p in ir["inputs"]
        )
        lines.append("  @INPUTS (" + inputs_str + ")")
        if ir["outputs"]:
            lines.append("  @OUTPUTS (" + ", ".join(ir["outputs"]) + ")")
        if ir["is_async"]:
            lines.append("  @ASYNC")
        cf = ir["control_flow"]
        cf_tags = []
        if cf["branching"]:
            cf_tags.append("BRANCH")
        if cf["loops"]:
            cf_tags.append("LOOP")
        if cf["recursion"]:
            cf_tags.append("RECURSION")
        if cf_tags:
            lines.append("  @CONTROL_FLOW " + ", ".join(cf_tags))
        ep = ir["exception_profile"]
        if ep["throws_exceptions"]:
            lines.append("  @THROWS")
        if ep["handles_exceptions"]:
            lines.append("  @HANDLES_EXCEPTIONS")
        call_edges = [e for e in ir["edges"] if e["edge_type"] == "CALL"]
        if call_edges:
            calls = []
            for e in call_edges[:10]:
                tag = e["target"]
                if self.state["config"]["include_certainty"]:
                    tag += " [" + e["certainty"] + "]"
                calls.append(tag)
            lines.append("  @CALLS " + ", ".join(calls))
            if len(call_edges) > 10:
                lines.append("  -- ... and " + str(len(call_edges) - 10) + " more calls")
        state_reads = [e for e in ir["edges"] if e["edge_type"] == "STATE_READ"]
        state_writes = [e for e in ir["edges"] if e["edge_type"] == "STATE_WRITE"]
        if state_reads:
            reads = [e["target"] + " [" + e["certainty"] + "]" for e in state_reads[:5]]
            lines.append("  @STATE_READS " + ", ".join(reads))
        if state_writes:
            writes = [e["target"] + " [" + e["certainty"] + "]" for e in state_writes[:5]]
            lines.append("  @STATE_WRITES " + ", ".join(writes))
        resource_edges = [e for e in ir["edges"] if e["edge_type"] == "RESOURCE"]
        if resource_edges:
            resources = []
            for e in resource_edges[:5]:
                tag = e["resource_type"] + ":" + e["target"] + " [" + e["certainty"] + "]"
                resources.append(tag)
            lines.append("  @RESOURCES " + ", ".join(resources))
        if self.state["config"]["include_deterministic_flag"]:
            lines.append("  @DETERMINISTIC_SUBSET " + str(det))
        cs = ir["certainty_summary"]
        lines.append("  @CERTAINTY certain=" + str(cs["certain_count"]) +
                      " probable=" + str(cs["probable_count"]) +
                      " unknown=" + str(cs["unknown_count"]))
        if cs["is_state_opaque"]:
            lines.append("  @STATE_OPAQUE")
        if cs["is_dispatch_opaque"]:
            lines.append("  @DISPATCH_OPAQUE")
        return "\n".join(lines)

    def _generate_free_methods_bcl(self, methods):
        lines = ["@FREE_FUNCTIONS"]
        lines.append("  @METHOD_COUNT " + str(len(methods)))
        lines.append("")
        for ir in methods:
            method_bcl = self._generate_method_bcl(ir)
            for mline in method_bcl.split("\n"):
                lines.append("  " + mline)
            lines.append("")
        return "\n".join(lines)

    def _generate_domain_bcl(self, domain_id, class_ids, classes, methods):
        lines = []
        lines.append("@DOMAIN " + domain_id)
        lines.append("  @CLASS_COUNT " + str(len(class_ids)))
        lines.append("  @CLASSES " + ", ".join(
            classes[cid]["name"] if cid in classes else cid for cid in class_ids
        ))
        all_resources = set()
        all_types = defaultdict(int)
        for cid in class_ids:
            if cid not in classes:
                continue
            for mid in classes[cid]["methods"]:
                if mid not in methods:
                    continue
                ir = methods[mid]
                all_types[ir.get("method_type", "UNKNOWN")] += 1
                for e in ir["edges"]:
                    if e["edge_type"] == "RESOURCE" and e["resource_type"]:
                        all_resources.add(e["resource_type"])
        if all_resources:
            lines.append("  @RESOURCES " + ", ".join(sorted(all_resources)))
        if all_types:
            type_str = ", ".join(t + "=" + str(c) for t, c in sorted(all_types.items()))
            lines.append("  @TYPE_DISTRIBUTION " + type_str)
        return "\n".join(lines)

    def _generate_file_bcl(self, file_data, classes, methods):
        lines = []
        fname = file_data["path"].split("/")[-1]
        lines.append("@FILE " + fname)
        lines.append("  @HASH " + file_data["hash"])
        lines.append("  @LINES " + str(file_data["line_count"]))
        lines.append("  @CLASSES " + str(len(classes)))
        lines.append("  @METHODS " + str(len(methods)))
        lines.append("")
        for cls in classes:
            cls_methods = [methods[mid] for mid in cls["methods"] if mid in methods]
            cls_bcl = self._generate_class_bcl(cls, cls_methods)
            for cline in cls_bcl.split("\n"):
                lines.append("  " + cline)
            lines.append("")
        for m in methods:
            if m["class_id"] is None:
                method_bcl = self._generate_method_bcl(m)
                for mline in method_bcl.split("\n"):
                    lines.append("  " + mline)
                lines.append("")
        return "\n".join(lines)

    # ================================================================
    # DOMAIN COMPUTATION (section 22.7)
    # ================================================================

    def _compute_domains(self, extractor):
        classes = extractor.state["classes"]
        methods = extractor.state["methods"]
        class_resources = {}
        for class_id, cls_data in classes.items():
            resources = set()
            for mid in cls_data["methods"]:
                if mid not in methods:
                    continue
                for e in methods[mid]["edges"]:
                    if e["edge_type"] == "RESOURCE" and e["resource_type"]:
                        resources.add(e["resource_type"])
            class_resources[class_id] = resources
        adjacency = defaultdict(set)
        class_list = list(class_resources.keys())
        for i in range(len(class_list)):
            for j in range(i + 1, len(class_list)):
                cid_a = class_list[i]
                cid_b = class_list[j]
                shared = class_resources[cid_a] & class_resources[cid_b]
                if len(shared) >= 2:
                    adjacency[cid_a].add(cid_b)
                    adjacency[cid_b].add(cid_a)
        visited = set()
        domains = {}
        domain_counter = 0
        for cid in class_list:
            if cid in visited:
                continue
            if cid not in adjacency:
                domain_counter += 1
                domains["domain_" + str(domain_counter)] = [cid]
                visited.add(cid)
                continue
            stack = [cid]
            component = []
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)
                for neighbor in adjacency[node]:
                    if neighbor not in visited:
                        stack.append(neighbor)
            domain_counter += 1
            domains["domain_" + str(domain_counter)] = component
        return domains

    def _generate_unit_bcl(self, unit, methods, partitioner):
        lines = []
        lines.append("@UNIT " + unit["unit_id"])
        lines.append("  @METHOD_COUNT " + str(unit["method_count"]))
        class_names = []
        for cid in unit["class_ids"]:
            if "::" in cid:
                class_names.append(cid.split("::")[-1])
            else:
                class_names.append(cid)
        if class_names:
            lines.append("  @CLASSES " + ", ".join(class_names))
        file_names = [f.split("/")[-1] for f in unit["file_ids"]]
        if file_names:
            lines.append("  @FILES " + ", ".join(file_names))
        mt = unit["method_types"]
        if mt:
            type_str = ", ".join(t + "=" + str(c) for t, c in sorted(mt.items()))
            lines.append("  @TYPE_DISTRIBUTION " + type_str)
        if unit["resources"]:
            lines.append("  @RESOURCES " + ", ".join(unit["resources"]))
        if unit["state_keys"]:
            shown = unit["state_keys"][:8]
            lines.append("  @STATE_KEYS " + ", ".join(shown))
            if len(unit["state_keys"]) > 8:
                lines.append("  -- ... and " + str(len(unit["state_keys"]) - 8) + " more state keys")
        lines.append("  @CLOSED " + str(unit["is_closed"]))
        lines.append("  @INTERNAL_CALLS " + str(unit["internal_calls"]))
        ext_count = len(unit["external_calls"])
        if ext_count:
            lines.append("  @EXTERNAL_CALLS " + str(ext_count))
            ext_targets = set()
            for ec in unit["external_calls"][:10]:
                if ec.get("target_unit"):
                    ext_targets.add(ec["target_unit"])
                elif ec.get("target"):
                    ext_targets.add(ec["target"])
            if ext_targets:
                lines.append("  @DEPENDS_ON " + ", ".join(sorted(ext_targets)[:8]))
        unit_deps = partitioner.state["unit_graph"].get(unit["unit_id"], set())
        if unit_deps:
            lines.append("  @UNIT_DEPENDENCIES " + ", ".join(sorted(unit_deps)[:10]))
        lines.append("")
        for ir in methods[:10]:
            method_bcl = self._generate_method_bcl(ir)
            for mline in method_bcl.split("\n"):
                lines.append("  " + mline)
            lines.append("")
        if len(methods) > 10:
            lines.append("  -- ... and " + str(len(methods) - 10) + " more methods")
        return "\n".join(lines)
