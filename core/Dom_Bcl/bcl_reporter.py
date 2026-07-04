#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_reporter.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="BCL IR SummaryReporter — summary statistics for compilation results"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_reporter.py" domain="BCL" authority="SummaryReporter"}
# [@SUMMARY]{summary="BCL SummaryReporter: computes summary stats from compilation results. Returns dict, no stdout."}
# [@CLASS]{class="SummaryReporter" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="print_summary" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from collections import Counter


class SummaryReporter:
    """Compute summary statistics for compilation results."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "summary": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "print_summary":
            return self.PrintSummary(params)
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

    def PrintSummary(self, params):
        results = self._p(params, "results")
        analysis = self._p(params, "analysis")
        if results is None:
            return (0, None, ("MISSING_PARAM", "results required", 0))
        total_files = len(results)
        errors = sum(1 for r in results if "error" in r)
        total_blocks = sum(r.get("block_count", 0) for r in results)
        total_classes = sum(r.get("class_count", 0) for r in results)
        total_methods = sum(r.get("method_count", 0) for r in results)
        total_violations = sum(r.get("violation_count", 0) for r in results)
        rule_counts = Counter()
        severity_counts = Counter()
        top_violators = Counter()
        for r in results:
            if "error" in r:
                continue
            for block in r.get("bcl", "").split("\n\n"):
                for line in block.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("[@FIELD]   rule="):
                        rule_id = stripped.split("rule=")[1].strip()
                        rule_counts[rule_id] += 1
                    if stripped.startswith("[@FIELD]   severity="):
                        sev = stripped.split("severity=")[1].strip()
                        severity_counts[sev] += 1
                    if stripped.startswith("[@FIELD]   target="):
                        tgt = stripped.split("target=")[1].strip()
                        top_violators[tgt] += 1
        summary = {
            "files": total_files,
            "errors": errors,
            "blocks": total_blocks,
            "classes": total_classes,
            "methods": total_methods,
            "violations": total_violations,
            "blocks_per_file": total_blocks // max(total_files - errors, 1),
            "rule_breakdown": dict(rule_counts.most_common()),
            "severity_breakdown": dict(severity_counts.most_common()),
            "top_violators": dict(top_violators.most_common(10)),
        }
        if analysis:
            summary["analysis"] = {
                "global_methods": analysis.get("total_methods", 0),
                "global_classes": analysis.get("total_classes", 0),
                "total_edges": analysis.get("total_edges", 0),
                "dead_code": analysis.get("dead_count", 0),
                "circular_cycles": analysis.get("cycle_count", 0),
                "circular_imports": analysis.get("circ_import_count", 0),
                "hot_paths": analysis.get("hotpath_count", 0),
                "cross_file_edges": analysis.get("xedge_count", 0),
                "file_dependencies": analysis.get("dep_count", 0),
                "extra_ir_blocks": analysis.get("extra_count", 0),
            }
        self.state["summary"] = summary
        return (1, summary, None)
