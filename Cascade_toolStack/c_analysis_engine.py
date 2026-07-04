"""
C Analysis Engine — Stage 3 Integration Layer
Orchestrator + Report Generator + CLI
Imports Stage 2 functions from c_analysis_core, connects them into a system.
"""
import os
import sys
import hashlib
from datetime import datetime
from collections import defaultdict

from c_analysis_core import (
    extract_functions, function_body_ranges, function_body_sizes,
    function_arity, static_vs_exported,
    extract_struct_fields, extract_enums, extract_global_vars,
    build_call_graph, dead_functions, circular_dependencies,
    extract_todos, extract_sql_queries, extract_mysql_tables,
    extract_ifdef_blocks, max_nesting_depth,
    header_dependency_tree, extract_bcl_packets,
)


# =========================
# ORCHESTRATOR
# =========================

class CodeAnalyzer:
    """Single orchestrator — runs all Stage 2 functions, returns unified report."""

    def __init__(self, code: str = ""):
        self.code = code
        self._cache = {}

    def load(self, code: str):
        self.code = code
        self._cache = {}

    def _run(self, key: str, func, *args):
        if key not in self._cache:
            self._cache[key] = func(*args)
        return self._cache[key]

    def functions(self):
        return self._run("functions", extract_functions, self.code)

    def body_ranges(self):
        return self._run("ranges", function_body_ranges, self.code)

    def body_sizes(self):
        return self._run("sizes", function_body_sizes, self.code)

    def arity(self):
        return self._run("arity", function_arity, self.code)

    def visibility(self):
        return self._run("vis", static_vs_exported, self.code)

    def structs(self):
        return self._run("structs", extract_struct_fields, self.code)

    def enums(self):
        return self._run("enums", extract_enums, self.code)

    def globals(self):
        return self._run("globals", extract_global_vars, self.code)

    def call_graph(self):
        return self._run("graph", build_call_graph, self.code)

    def dead(self):
        return self._run("dead", dead_functions, self.code)

    def cycles(self):
        return self._run("cycles", circular_dependencies, self.call_graph())

    def todos(self):
        return self._run("todos", extract_todos, self.code)

    def sql(self):
        return self._run("sql", extract_sql_queries, self.code)

    def tables(self):
        return self._run("tables", extract_mysql_tables, self.code)

    def ifdef(self):
        return self._run("ifdef", extract_ifdef_blocks, self.code)

    def nesting(self):
        return self._run("nesting", max_nesting_depth, self.code)

    def headers(self):
        return self._run("headers", header_dependency_tree, self.code)

    def bcl_packets(self):
        return self._run("packets", extract_bcl_packets, self.code)

    def run_all(self) -> dict:
        return {
            "functions": self.functions(),
            "body_ranges": self.body_ranges(),
            "body_sizes": self.body_sizes(),
            "arity": self.arity(),
            "visibility": self.visibility(),
            "structs": self.structs(),
            "enums": self.enums(),
            "globals": self.globals(),
            "call_graph": dict(self.call_graph()),
            "dead_functions": self.dead(),
            "circular": self.cycles(),
            "todos": self.todos(),
            "sql": self.sql(),
            "mysql_tables": self.tables(),
            "ifdef": self.ifdef(),
            "max_nesting": self.nesting(),
            "headers": self.headers(),
            "bcl_packets": self.bcl_packets(),
            "summary": self._summary(),
        }

    def _summary(self) -> dict:
        return {
            "function_count": len(self.functions()),
            "dead_count": len(self.dead()),
            "cycle_count": len(self.cycles()),
            "max_nesting": self.nesting(),
            "todo_count": len(self.todos()),
            "sql_count": len(self.sql()),
            "struct_count": len(self.structs()),
            "enum_count": len(self.enums()),
            "global_count": len(self.globals()),
            "bcl_packet_count": len(self.bcl_packets()),
        }


# =========================
# CROSS-FILE RESOLVER
# =========================

class CrossFileResolver:
    """Resolves symbols across multiple files, builds cross-file call graph."""

    def __init__(self):
        self.files = {}  # fname -> CodeAnalyzer
        self.func_to_file = {}

    def add_file(self, fname: str, code: str):
        analyzer = CodeAnalyzer(code)
        self.files[fname] = analyzer
        for func_name, _, _ in analyzer.functions():
            self.func_to_file[func_name] = fname

    def cross_file_calls(self) -> dict:
        cross = {}
        for fname, analyzer in self.files.items():
            targets = []
            graph = analyzer.call_graph()
            file_funcs = set(f[0] for f in analyzer.functions())
            for caller, callees in graph.items():
                for callee in callees:
                    if callee in self.func_to_file and self.func_to_file[callee] != fname:
                        targets.append((caller, callee, self.func_to_file[callee]))
            cross[fname] = targets
        return cross

    def circular_file_deps(self) -> list:
        cross = self.cross_file_calls()
        file_deps = defaultdict(set)
        for fname, calls in cross.items():
            for _, _, target_file in calls:
                file_deps[fname].add(target_file)

        circulars = []
        for f1 in file_deps:
            for f2 in file_deps[f1]:
                if f1 in file_deps.get(f2, set()):
                    pair = tuple(sorted([f1, f2]))
                    if pair not in circulars:
                        circulars.append(pair)
        return circulars

    def all_reports(self) -> dict:
        return {fname: a.run_all() for fname, a in self.files.items()}


# =========================
# REPORT ENGINE
# =========================

class ReportEngine:
    """Markdown report generator from analysis results."""

    def generate_overview(self, all_data: dict, cross: dict, circulars: list) -> str:
        total_funcs = sum(d["summary"]["function_count"] for d in all_data.values())
        total_dead = sum(d["summary"]["dead_count"] for d in all_data.values())
        total_sql = sum(d["summary"]["sql_count"] for d in all_data.values())
        total_todos = sum(d["summary"]["todo_count"] for d in all_data.values())
        total_pkts = sum(d["summary"]["bcl_packet_count"] for d in all_data.values())
        total_cycles = sum(len(d["circular"]) for d in all_data.values())

        lines = [
            "## Overview\n",
            "| Metric | Value |",
            "|---|---|",
            f"| Files | {len(all_data)} |",
            f"| Functions | {total_funcs} |",
            f"| Dead functions | {total_dead} |",
            f"| SQL queries | {total_sql} |",
            f"| TODOs | {total_todos} |",
            f"| BCL packets | {total_pkts} |",
            f"| Intra-file cycles | {total_cycles} |",
            f"| Cross-file circular deps | {len(circulars)} |",
            "",
        ]
        return "\n".join(lines)

    def generate_summary_table(self, all_data: dict) -> str:
        lines = [
            "## Summary Table\n",
            "| File | Funcs | Dead | SQL | TODO | Pkt | Nest | Cycles |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for fname in sorted(all_data, key=lambda f: -all_data[f]["summary"]["function_count"]):
            d = all_data[fname]
            s = d["summary"]
            lines.append(
                f"| {fname} | {s['function_count']} | {s['dead_count']} | "
                f"{s['sql_count']} | {s['todo_count']} | {s['bcl_packet_count']} | "
                f"{s['max_nesting']} | {len(d['circular'])} |"
            )
        lines.append("")
        return "\n".join(lines)

    def generate_cross_graph(self, cross: dict) -> str:
        lines = ["## Cross-File Call Graph\n", "| Caller File | Function | -> | Target File |", "|---|---|---|---|"]
        for src in sorted(cross):
            for caller, callee, target in sorted(cross[src], key=lambda x: (x[2], x[1])):
                lines.append(f"| {src} | `{caller}` | -> | {target} |")
        lines.append("")
        return "\n".join(lines)

    def generate_per_file(self, all_data: dict) -> str:
        lines = []
        for fname in sorted(all_data, key=lambda f: -all_data[f]["summary"]["function_count"]):
            d = all_data[fname]
            s = d["summary"]
            lines.append(f"\n---\n\n## {fname}\n")
            lines.append(f"| Property | Value |")
            lines.append(f"|---|---|")
            lines.append(f"| Functions | {s['function_count']} |")
            lines.append(f"| Dead | {s['dead_count']} |")
            lines.append(f"| Max nesting | {s['max_nesting']} |")
            lines.append(f"| SQL queries | {s['sql_count']} |")
            lines.append(f"| BCL packets | {s['bcl_packet_count']} |")
            lines.append(f"| TODOs | {s['todo_count']} |")
            lines.append("")

            # Functions table
            if d["functions"]:
                lines.append(f"### Functions ({s['function_count']})\n")
                lines.append("| Name | Arity | Visibility | Body size |")
                lines.append("|---|---|---|---|")
                vis = d["visibility"]
                sizes = d["body_sizes"]
                arity = d["arity"]
                for name, params, _ in d["functions"]:
                    v = vis.get(name, "?")
                    sz = sizes.get(name, 0)
                    ar = arity.get(name, 0)
                    lines.append(f"| `{name}` | {ar} | {v} | {sz} |")
                lines.append("")

            # Dead functions
            if d["dead_functions"]:
                lines.append(f"### Dead ({len(d['dead_functions'])})\n")
                for df in d["dead_functions"]:
                    lines.append(f"- `{df}`")
                lines.append("")

            # Call graph
            if d["call_graph"]:
                lines.append("### Intra-File Call Graph\n")
                lines.append("| Caller | Callees |")
                lines.append("|---|---|")
                for caller, callees in sorted(d["call_graph"].items()):
                    lines.append(f"| `{caller}` | {', '.join(sorted(callees))} |")
                lines.append("")

            # Cycles
            if d["circular"]:
                lines.append(f"### Cycles ({len(d['circular'])})\n")
                for cyc in d["circular"]:
                    lines.append(f"- `{' -> '.join(cyc)}`")
                lines.append("")

            # SQL
            if d["sql"]:
                lines.append(f"### SQL ({len(d['sql'])})\n")
                for q in d["sql"][:10]:
                    short = q[:80] + "..." if len(q) > 80 else q
                    lines.append(f"- `{short}`")
                if len(d["sql"]) > 10:
                    lines.append(f"- ... ({len(d['sql']) - 10} more)")
                lines.append("")

            # BCL packets
            if d["bcl_packets"]:
                lines.append(f"### BCL Packets ({len(d['bcl_packets'])})\n")
                for pkt_name, pkt_body in d["bcl_packets"][:10]:
                    lines.append(f"- `[@{pkt_name}]` — `{pkt_body[:60]}`")
                if len(d["bcl_packets"]) > 10:
                    lines.append(f"- ... ({len(d['bcl_packets']) - 10} more)")
                lines.append("")

            # Structs
            if d["structs"]:
                lines.append("### Structs\n")
                for sname, fields in d["structs"].items():
                    lines.append(f"- `struct {sname}` ({len(fields)} fields)")
                lines.append("")

            # Enums
            if d["enums"]:
                lines.append("### Enums\n")
                for ename, consts in d["enums"].items():
                    lines.append(f"- `enum {ename}` ({len(consts)} constants)")
                lines.append("")

            # Headers
            if d["headers"]:
                lines.append("### Includes\n")
                for h in d["headers"]:
                    lines.append(f"- `{h}`")
                lines.append("")

            # TODOs
            if d["todos"]:
                lines.append(f"### TODOs ({len(d['todos'])})\n")
                for tag, text in d["todos"]:
                    lines.append(f"- **{tag}**: {text}")
                lines.append("")

        return "\n".join(lines)

    def write_report(self, all_data: dict, cross: dict, circulars: list, path: str):
        with open(path, "w") as f:
            f.write(f"# C Code Analysis Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write(self.generate_overview(all_data, cross, circulars))
            f.write("\n")
            f.write(self.generate_summary_table(all_data))
            f.write("\n")
            if circulars:
                f.write("## Circular File Dependencies\n\n")
                for a, b in circulars:
                    f.write(f"- `{a}` <-> `{b}`\n")
                f.write("\n")
            f.write(self.generate_cross_graph(cross))
            f.write("\n")
            f.write(self.generate_per_file(all_data))


# =========================
# CLI — ENTRY POINT
# =========================

def main():
    args = sys.argv[1:]

    if not args:
        print("C Analysis Engine — Stage 3 Integration")
        print("")
        print("Usage: c_analysis_engine.py <directory> [--output FILE]")
        print("")
        print("Options:")
        print("  --output FILE   Write markdown report to FILE (default: analysis_report.md)")
        print("  --json          Output JSON instead of markdown")
        print("")
        return 1

    directory = args[0]
    output = "analysis_report.md"
    json_mode = "--json" in args

    if "--output" in args:
        idx = args.index("--output") + 1
        if idx < len(args):
            output = args[idx]

    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory")
        return 1

    resolver = CrossFileResolver()

    for root, _, files in os.walk(directory):
        for fn in sorted(files):
            if fn.endswith(".c"):
                path = os.path.join(root, fn)
                with open(path, "r", errors="ignore") as f:
                    code = f.read()
                resolver.add_file(fn, code)

    cross = resolver.cross_file_calls()
    circulars = resolver.circular_file_deps()
    all_data = resolver.all_reports()

    if json_mode:
        import json
        with open(output, "w") as f:
            json.dump(all_data, f, indent=2, default=str)
    else:
        engine = ReportEngine()
        engine.write_report(all_data, cross, circulars, output)

    total_funcs = sum(d["summary"]["function_count"] for d in all_data.values())
    total_dead = sum(d["summary"]["dead_count"] for d in all_data.values())
    print(f"Report: {output}")
    print(f"Files: {len(all_data)} | Funcs: {total_funcs} | Dead: {total_dead} | Circular: {len(circulars)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
