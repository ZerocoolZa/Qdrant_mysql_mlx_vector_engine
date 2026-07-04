#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/bcl_cli.py"
# date="2026-08-18" author="Devin" session_id="bcl-ir-build"
# context="BCL_COMPILER_PLAN: CLI runner for full IR extraction + partitioning + BCL projection pipeline"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_cli.py" domain="bcl_ir" authority="BclCli"}
# [@SUMMARY]{summary="CLI runner that executes the full BCL pipeline: extract IR, classify, partition into units, project BCL, report stats."}
# [@CLASS]{class="BclCli" domain="bcl_ir" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="Execute" type="command"}
# [@METHOD]{method="ReportText" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
"""
BclCli -- CLI runner for the full BCL pipeline.

Usage:
  python3 bcl_cli.py <root_dir> [options]

Options:
  --report         Print summary report only
  --bcl            Print BCL output for all classes
  --units          Print computational unit BCL
  --unit UID       Print BCL for specific unit
  --method MID     Print BCL for specific method
  --class CID      Print BCL for specific class
  --json           Output as JSON
  --quiet          Suppress progress output

Pipeline:
  1. IrExtractor.ScanDir -> extract IR from all .py files
  2. IrExtractor.ClassifyAll -> classify methods as IO/CORE/LINK/INIT
  3. IrExtractor.BuildGraph -> build call/state/resource graphs
  4. UnitPartitioner.Partition -> form computational units via SCC
  5. BclProjector.ProjectAll -> generate BCL output
  6. Report stats
"""
import sys
import json
from typing import Any, Dict, List, Tuple

from ir_extractor import IrExtractor
from unit_partitioner import UnitPartitioner
from bcl_projector import BclProjector


class BclCli:
    """CLI runner for the full BCL pipeline."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "root": None,
                "mode": "report",
                "unit_id": None,
                "method_id": None,
                "class_id": None,
                "json_output": False,
                "quiet": False,
            },
            "extractor": None,
            "partitioner": None,
            "projector": None,
            "report": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "execute":
            return self.Execute(params)
        elif command == "report_text":
            return self.ReportText(params)
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
        return (1, {"config": dict(self.state["config"])}, None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Execute(self, params):
        root = self._p(params, "root") or self.state["config"]["root"]
        if not root:
            return (0, None, ("MISSING_PARAM", "root directory required", 0))
        mode = self._p(params, "mode", self.state["config"]["mode"])
        quiet = self._p(params, "quiet", self.state["config"]["quiet"])
        ext = IrExtractor()
        if not quiet:
            print("Scanning " + root + " ...")
        r = ext.Run("scan_dir", {"root": root})
        if r[0] != 1:
            return (0, None, r[2])
        if not quiet:
            print("  " + str(r[1]["files_scanned"]) + " files, " +
                  str(r[1]["total_methods"]) + " methods, " +
                  str(r[1]["total_classes"]) + " classes")
        ext.Run("classify_all", {})
        ext.Run("build_graph", {})
        if not quiet:
            print("Classified and graphed.")
        part = UnitPartitioner()
        pr = part.Run("partition", {"extractor": ext})
        if pr[0] != 1:
            return (0, None, pr[2])
        if not quiet:
            print("  " + str(pr[1]["total_units"]) + " units, " +
                  str(pr[1]["fully_closed_units"]) + " closed, " +
                  str(pr[1]["closure_violations"]) + " open")
        proj = BclProjector()
        proj.Run("project_all", {"extractor": ext})
        self.state["extractor"] = ext
        self.state["partitioner"] = part
        self.state["projector"] = proj
        ir_report = ext.Run("report", {})[1]
        unit_report = part.Run("report", {})[1]
        self.state["report"] = {
            "ir": ir_report,
            "units": unit_report,
        }
        if mode == "json":
            return (1, self.state["report"], None)
        if mode == "report":
            text = self._format_report(ir_report, unit_report)
            return (1, text, None)
        if mode == "bcl":
            lines = []
            for cid, bcl in proj.state["bcl_output"].items():
                lines.append(bcl)
                lines.append("")
            return (1, "\n".join(lines), None)
        if mode == "units":
            unit_id = self._p(params, "unit_id")
            if unit_id:
                r = proj.Run("project_unit", {
                    "extractor": ext, "partitioner": part, "unit_id": unit_id
                })
                if r[0] == 1:
                    return (1, r[1]["bcl"], None)
                return r
            r = proj.Run("project_units", {"extractor": ext, "partitioner": part})
            if r[0] == 1:
                lines = []
                for uid, bcl in r[1]["bcl_output"].items():
                    lines.append(bcl)
                    lines.append("")
                return (1, "\n".join(lines), None)
            return r
        if mode == "method":
            method_id = self._p(params, "method_id")
            if not method_id:
                return (0, None, ("MISSING_PARAM", "method_id required for method mode", 0))
            r = proj.Run("project_method", {"extractor": ext, "method_id": method_id})
            if r[0] == 1:
                return (1, r[1]["bcl"], None)
            return r
        if mode == "class":
            class_id = self._p(params, "class_id")
            if not class_id:
                return (0, None, ("MISSING_PARAM", "class_id required for class mode", 0))
            r = proj.Run("project_class", {"extractor": ext, "class_id": class_id})
            if r[0] == 1:
                return (1, r[1]["bcl"], None)
            return r
        return (1, self.state["report"], None)

    def ReportText(self, params):
        if not self.state["report"]:
            return (0, None, ("NO_DATA", "run execute first", 0))
        ir = self.state["report"]["ir"]
        units = self.state["report"]["units"]
        return (1, self._format_report(ir, units), None)

    def _format_report(self, ir, units):
        lines = []
        lines.append("=== BCL PIPELINE REPORT ===")
        lines.append("")
        lines.append("IR EXTRACTION:")
        lines.append("  Files:       " + str(ir["total_files"]))
        lines.append("  Classes:     " + str(ir["total_classes"]))
        lines.append("  Methods:     " + str(ir["total_methods"]))
        lines.append("  Edges:       " + str(ir["total_edges"]))
        ec = ir["edge_certainty"]
        lines.append("  CERTAIN:     " + str(ec["CERTAIN"]) + " (" + str(ec["certain_pct"]) + "%)")
        lines.append("  PROBABLE:    " + str(ec["PROBABLE"]) + " (" + str(ec["probable_pct"]) + "%)")
        lines.append("  UNKNOWN:     " + str(ec["UNKNOWN"]) + " (" + str(ec["unknown_pct"]) + "%)")
        lines.append("")
        lines.append("METHOD CLASSIFICATION:")
        mt = ir["method_types"]
        total_m = sum(mt.values()) if mt else 1
        for t in ("IO", "CORE", "LINK", "INIT", "CLEANUP"):
            cnt = mt.get(t, 0)
            lines.append("  " + t + ": " + str(cnt) + " (" +
                         str(round(cnt / total_m * 100, 1)) + "%)")
        det = ir["deterministic_subset"]
        lines.append("  DETERMINISTIC_SUBSET: " + str(det["count"]) + " (" + str(det["pct"]) + "%)")
        lines.append("")
        lines.append("COMPUTATIONAL UNITS:")
        lines.append("  Total units:    " + str(units["total_units"]))
        lines.append("  Methods in units: " + str(units["total_methods_in_units"]))
        lines.append("  Avg unit size:  " + str(units["avg_unit_size"]))
        lines.append("  Max unit size:  " + str(units["max_unit_size"]))
        lines.append("  Min unit size:  " + str(units["min_unit_size"]))
        cl = units["closure"]
        lines.append("  Fully closed:   " + str(cl["fully_closed"]))
        lines.append("  With externals: " + str(cl["with_external_calls"]))
        lines.append("  Closure violations: " + str(cl["total_violations"]))
        lines.append("  Unit graph edges: " + str(units["unit_graph_edges"]))
        lines.append("")
        lines.append("SIZE DISTRIBUTION:")
        for size, cnt in sorted(units["size_distribution"].items()):
            if cnt > 0:
                lines.append("  " + str(size) + " methods: " + str(cnt) + " units")
        lines.append("")
        lines.append("TYPE DISTRIBUTION ACROSS UNITS:")
        td = units["type_distribution"]
        for t in ("IO", "CORE", "LINK", "INIT", "CLEANUP"):
            cnt = td.get(t, 0)
            if cnt > 0:
                lines.append("  " + t + ": " + str(cnt))
        if ir["parse_errors"] > 0:
            lines.append("")
            lines.append("PARSE ERRORS: " + str(ir["parse_errors"]))
            for err in ir.get("errors", [])[:5]:
                lines.append("  " + str(err))
        return "\n".join(lines)


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 bcl_cli.py <root_dir> [--report|--bcl|--units|--unit UID|--method MID|--class CID|--json|--quiet]")
        sys.exit(1)
    root = args[0]
    mode = "report"
    unit_id = None
    method_id = None
    class_id = None
    json_output = False
    quiet = False
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "--report":
            mode = "report"
        elif arg == "--bcl":
            mode = "bcl"
        elif arg == "--units":
            mode = "units"
        elif arg == "--unit":
            mode = "units"
            i += 1
            if i < len(args):
                unit_id = args[i]
        elif arg == "--method":
            mode = "method"
            i += 1
            if i < len(args):
                method_id = args[i]
        elif arg == "--class":
            mode = "class"
            i += 1
            if i < len(args):
                class_id = args[i]
        elif arg == "--json":
            json_output = True
            mode = "json"
        elif arg == "--quiet":
            quiet = True
        i += 1
    cli = BclCli(param={"root": root, "mode": mode, "quiet": quiet})
    r = cli.Run("execute", {
        "root": root, "mode": mode, "unit_id": unit_id,
        "method_id": method_id, "class_id": class_id,
        "quiet": quiet, "json": json_output,
    })
    if r[0] == 1:
        if isinstance(r[1], str):
            print(r[1])
        else:
            print(json.dumps(r[1], indent=2, default=str))
    else:
        print("ERROR: " + str(r[2]))
        sys.exit(1)


if __name__ == "__main__":
    main()
