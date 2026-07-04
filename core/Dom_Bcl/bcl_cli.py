#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_cli.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="BCL IR CLIHandler — CLI argument parsing and pipeline orchestration"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_cli.py" domain="BCL" authority="CLIHandler"}
# [@SUMMARY]{summary="BCL CLIHandler: parses CLI args, dispatches to compiler/analyzer/exporter/validator/query/reporter."}
# [@CLASS]{class="CLIHandler" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="main" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sys

from bcl_compiler import IRCompiler
from bcl_exporter import IRExporter
from bcl_query import IRQuery
from bcl_validator import IRValidator
from bcl_analyzer import PostAnalyzer
from bcl_reporter import SummaryReporter


class CLIHandler:
    """Handle CLI arguments and orchestrate the BCL pipeline."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "compiler": None,
            "analyzer": None,
            "exporter": None,
            "validator": None,
            "query": None,
            "reporter": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "main":
            return self.Main(params)
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

    def InitSubsystems(self):
        self.state["compiler"] = IRCompiler()
        self.state["analyzer"] = PostAnalyzer()
        self.state["exporter"] = IRExporter()
        self.state["validator"] = IRValidator()
        self.state["query"] = IRQuery()
        self.state["reporter"] = SummaryReporter()
        return (1, True, None)

    def Main(self, params):
        argv = self._p(params, "argv", sys.argv)
        if len(argv) < 2:
            return (0, None, ("NO_ARGS", "Usage: python3 bcl_cli.py <file.py|dir> [flags]", 0))
        self.InitSubsystems()
        target = argv[1]
        summary_only = "--summary" in argv
        stamp = "--stamp" in argv
        do_analyze = "--analyze" in argv
        do_validate = "--validate" in argv
        do_incremental = "--incremental" in argv
        query_str = None
        max_complexity = None
        sqlite_path = None
        mysql_path = None
        if "--sqlite" in argv:
            idx = argv.index("--sqlite")
            sqlite_path = argv[idx + 1] if idx + 1 < len(argv) else "bcl_ir.db"
        if "--mysql" in argv:
            idx = argv.index("--mysql")
            mysql_path = argv[idx + 1] if idx + 1 < len(argv) else "bcl_ir_mysql.db"
        if "--query" in argv:
            idx = argv.index("--query")
            query_str = argv[idx + 1] if idx + 1 < len(argv) else ""
        if "--max-complexity" in argv:
            idx = argv.index("--max-complexity")
            max_complexity = int(argv[idx + 1]) if idx + 1 < len(argv) else 10
        if not os.path.exists(target):
            return (0, None, ("NOT_FOUND", "Target not found: " + target, 0))
        compiler = self.state["compiler"]
        if os.path.isdir(target):
            compile_result = compiler.Run("compile_directory", {"path": target, "incremental": do_incremental})
        else:
            compile_result = compiler.Run("compile_file", {"path": target})
        if compile_result[0] == 0:
            return compile_result
        results = compile_result[1].get("results", [])
        if query_str:
            query = self.state["query"]
            q_result = query.Run("query_ir", {"results": results, "query_str": query_str})
            if q_result[0] == 0:
                return q_result
            return (1, {"query_matches": q_result[1]["matches"], "count": q_result[1]["count"]}, None)
        analysis = None
        if do_analyze or mysql_path:
            analyzer = self.state["analyzer"]
            a_result = analyzer.Run("post_analyze", {"results": results})
            if a_result[0] == 1:
                analysis = a_result[1]
        if sqlite_path:
            exporter = self.state["exporter"]
            exporter.Run("export_sqlite_bcl", {"results": results, "db_path": sqlite_path})
        if mysql_path:
            exporter = self.state["exporter"]
            exporter.Run("export_mysql_bcl", {"results": results, "db_name": mysql_path, "analysis": analysis})
        if do_validate:
            validator = self.state["validator"]
            v_result = validator.Run("validate_ir", {"results": results})
            if v_result[0] == 1:
                issues = v_result[1].get("issues", [])
                if issues:
                    return (1, {"validation_issues": issues[:20], "count": len(issues)}, None)
        if summary_only:
            reporter = self.state["reporter"]
            s_result = reporter.Run("print_summary", {"results": results, "analysis": analysis})
            if s_result[0] == 1:
                return (1, {"summary": s_result[1]}, None)
        return (1, {"results": results, "analysis": analysis, "stamped": stamp}, None)
