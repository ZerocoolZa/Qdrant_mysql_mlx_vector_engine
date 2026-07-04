#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/compiler_engine.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 36 Compiler Knowledge"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="compiler_engine.py" domain="twin_compiler" authority="CompilerEngine"}
# [@SUMMARY]{summary="Compiler authority that compiles files, aggregates compile results, and tracks compiler errors, warnings, and build history."}
# [@CLASS]{class="CompilerEngine" domain="compiler" authority="single"}
# [@METHOD]{method="compile_file" type="command"}
# [@METHOD]{method="compile_all" type="command"}
# [@METHOD]{method="get_errors" type="command"}
# [@METHOD]{method="get_warnings" type="command"}
# [@METHOD]{method="build_history" type="command"}
# [@METHOD]{method="build_environment" type="command"}
# [@METHOD]{method="compiler_version" type="command"}
# [@METHOD]{method="linker_errors" type="command"}
# [@METHOD]{method="build_logs" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<CompilerEngine: compiles files, aggregates errors/warnings, tracks build history. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
CompilerEngine -- Compiler knowledge authority.
Implements Section 36 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: compile_file, compile_all, get_errors, get_warnings, build_history,
          build_environment, compiler_version, linker_errors, build_logs.
"""
import json
import os
import sqlite3
import sys
import time
import warnings
import platform
import traceback
from datetime import datetime, timezone
import py_compile
import pathlib

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
SLOW_THRESHOLD_MS = 100


class CompilerEngine:
    """Compiler knowledge authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "scan_dir": os.path.dirname(os.path.abspath(__file__)),
            },
            "catalog": [],
            "results": [],
            "errors": [],
            "warnings": [],
            "build_logs": [],
            "last_build_time_ms": 0,
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "compile_file":
            return self.CompileFile(params)
        elif command == "compile_all":
            return self.CompileAll(params)
        elif command == "get_errors":
            return self.GetErrors(params)
        elif command == "get_warnings":
            return self.GetWarnings(params)
        elif command == "build_history":
            return self.BuildHistory(params)
        elif command == "build_environment":
            return self.BuildEnvironment(params)
        elif command == "compiler_version":
            return self.CompilerVersion(params)
        elif command == "linker_errors":
            return self.LinkerErrors(params)
        elif command == "build_logs":
            return self.BuildLogs(params)

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

    def CompileFile(self, params):
        # 36.1 Compiler Errors, 36.2 Compiler Warnings, 36.4 Build Logs, 36.5 Build Time
        file_path = self._p(params, "file_path")
        if not file_path or not os.path.isfile(file_path):
            return (0, None, ("NO_FILE", "File not found", 0))
        captured_warnings = []
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            start = time.time()
            try:
                py_compile.compile(file_path, doraise=True)
                elapsed_ms = int((time.time() - start) * 1000)
                self.state["last_build_time_ms"] = elapsed_ms
                for w in caught:
                    captured_warnings.append({
                        "category": w.category.__name__,
                        "message": str(w.message),
                        "filename": str(w.filename),
                        "lineno": w.lineno,
                    })
                self.state["warnings"].extend(captured_warnings)
                log_entry = {
                    "file": file_path, "passed": True, "time_ms": elapsed_ms,
                    "warnings": captured_warnings, "created": datetime.now(timezone.utc).isoformat(),
                }
                self.state["build_logs"].append(log_entry)
                self.state["errors"] = [e for e in self.state["errors"] if e.get("file") != file_path]
                self.RecordBuild(file_path, True, elapsed_ms, None, captured_warnings)
                return (1, {"passed": True, "file": file_path, "time_ms": elapsed_ms,
                            "warnings": captured_warnings}, None)
            except py_compile.PyCompileError as exc:
                elapsed_ms = int((time.time() - start) * 1000)
                self.state["last_build_time_ms"] = elapsed_ms
                err_text = str(exc)
                err_entry = {
                    "file": file_path, "error": err_text, "time_ms": elapsed_ms,
                    "created": datetime.now(timezone.utc).isoformat(),
                }
                self.state["errors"].append(err_entry)
                log_entry = dict(err_entry)
                log_entry["passed"] = False
                self.state["build_logs"].append(log_entry)
                self.RecordBuild(file_path, False, elapsed_ms, err_text, captured_warnings)
                return (1, {"passed": False, "file": file_path, "error": err_text,
                            "time_ms": elapsed_ms, "warnings": captured_warnings}, None)
            except SyntaxError as exc:
                elapsed_ms = int((time.time() - start) * 1000)
                self.state["last_build_time_ms"] = elapsed_ms
                err_text = "SyntaxError: " + str(exc) + " (line " + str(exc.lineno) + ")"
                err_entry = {
                    "file": file_path, "error": err_text, "time_ms": elapsed_ms,
                    "line": exc.lineno, "created": datetime.now(timezone.utc).isoformat(),
                }
                self.state["errors"].append(err_entry)
                log_entry = dict(err_entry)
                log_entry["passed"] = False
                self.state["build_logs"].append(log_entry)
                self.RecordBuild(file_path, False, elapsed_ms, err_text, captured_warnings)
                return (1, {"passed": False, "file": file_path, "error": err_text,
                            "time_ms": elapsed_ms, "line": exc.lineno}, None)

    def RecordBuild(self, file_path, passed, elapsed_ms, error_text, warn_list):
        # 36.1 store compile errors in knowledge, 36.4 build logs in observations
        conn = self.Connect()
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        tags = json.dumps(["build", "compile"])
        if not passed:
            cur.execute(
                "INSERT INTO knowledge (problem, question, answer, error_type, error_text, "
                "stack_trace, resolution_time_ms, created, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("Compile failed: " + file_path, "Why did compile fail?", "",
                 "CompileError", error_text, traceback.format_exc() if error_text else None,
                 elapsed_ms, now, tags))
        cur.execute(
            "INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
            "VALUES (?, ?, ?, ?, ?)",
            ("build_log", file_path,
             json.dumps({"passed": passed, "time_ms": elapsed_ms,
                         "error": error_text, "warnings": warn_list}),
             100 if passed else 0, now))
        conn.commit()

    def CompileAll(self, params):
        # 36.4 Build Logs, 36.5 Build Time, 36.6 Build History
        scan_dir = self._p(params, "scan_dir", self.state["config"]["scan_dir"])
        if not os.path.isdir(scan_dir):
            return (0, None, ("NO_DIR", "Scan directory not found", 0))
        py_files = list(pathlib.Path(scan_dir).rglob("*.py"))
        passed = 0
        failed = 0
        errors = []
        all_warnings = []
        start = time.time()
        for pf in py_files:
            res = self.CompileFile({"file_path": str(pf)})
            if res[0] == 1:
                data = res[1]
                if data.get("passed"):
                    passed += 1
                else:
                    failed += 1
                    errors.append({"file": str(pf), "error": data.get("error", "")[:200]})
                all_warnings.extend(data.get("warnings", []))
        elapsed_ms = int((time.time() - start) * 1000)
        self.state["last_build_time_ms"] = elapsed_ms
        summary = {
            "total": len(py_files), "passed": passed, "failed": failed,
            "errors": errors, "warnings": all_warnings, "time_ms": elapsed_ms,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
            "VALUES (?, ?, ?, ?, ?)",
            ("build_log", "compile_all:" + scan_dir, json.dumps(summary),
             100 if failed == 0 else 0, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, summary, None)

    def GetErrors(self, params):
        # 36.1 return compilation errors from last run + knowledge table
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, error_text, line_number, created "
                    "FROM knowledge WHERE error_type='CompileError' OR error_type='PyCompileError' "
                    "ORDER BY created DESC")
        results = [{"knowledge_id": r[0], "problem": r[1], "error_text": r[2],
                    "line": r[3], "created": r[4]} for r in cur.fetchall()]
        return (1, {"errors": results, "count": len(results),
                    "last_run_errors": self.state["errors"]}, None)

    def GetWarnings(self, params):
        # 36.2 return warnings captured during compile
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, evidence FROM observations "
                    "WHERE observation_type='warning' ORDER BY observation_id DESC")
        results = [{"observation_id": r[0], "subject": r[1], "evidence": r[2]} for r in cur.fetchall()]
        return (1, {"warnings": results, "count": len(results),
                    "last_run_warnings": self.state["warnings"]}, None)

    def BuildHistory(self, params):
        # 36.6 track compile results over time in observations table
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, evidence, created FROM observations "
                    "WHERE observation_type='build_log' ORDER BY created DESC")
        results = []
        for r in cur.fetchall():
            entry = {"observation_id": r[0], "subject": r[1], "created": r[3]}
            try:
                entry["detail"] = json.loads(r[2]) if r[2] else None
            except Exception:
                entry["detail"] = r[2]
            results.append(entry)
        cur.execute("SELECT knowledge_id, problem, created FROM knowledge "
                    "WHERE tags LIKE '%build%' ORDER BY created DESC")
        knowledge_builds = [{"knowledge_id": r[0], "problem": r[1], "created": r[2]}
                            for r in cur.fetchall()]
        return (1, {"build_history": results, "knowledge_builds": knowledge_builds,
                    "count": len(results)}, None)

    def BuildEnvironment(self, params):
        # 36.7 Build Environment: Python version, OS, dependencies
        env = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "os_name": os.name,
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "executable": sys.executable,
        }
        try:
            import pip
            env["pip_version"] = pip.__version__ if hasattr(pip, "__version__") else "unknown"
        except Exception:
            env["pip_version"] = "unavailable"
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
            "VALUES (?, ?, ?, ?, ?)",
            ("fact", "build_environment", json.dumps(env), 100,
             datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"environment": env}, None)

    def CompilerVersion(self, params):
        # 36.8 Compiler Version: sys.version
        info = {
            "sys_version": sys.version,
            "version_info": list(sys.version_info),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
            "build_info": platform.python_build(),
        }
        return (1, {"compiler_version": info}, None)

    def LinkerErrors(self, params):
        # 36.3 Linker Errors: for C code (if applicable)
        scan_dir = self._p(params, "scan_dir", self.state["config"]["scan_dir"])
        c_files = list(pathlib.Path(scan_dir).rglob("*.c")) if os.path.isdir(scan_dir) else []
        linker_errors = []
        if not c_files:
            return (1, {"linker_errors": [], "c_files": 0, "note": "No C files found"}, None)
        import subprocess
        for cf in c_files:
            try:
                proc = subprocess.run(
                    ["cc", "-c", str(cf), "-o", "/dev/null"],
                    capture_output=True, text=True, timeout=30)
                if proc.returncode != 0:
                    linker_errors.append({"file": str(cf), "error": proc.stderr[:500]})
            except FileNotFoundError:
                return (1, {"linker_errors": [], "c_files": len(c_files),
                            "note": "C compiler (cc) not available"}, None)
            except Exception as exc:
                linker_errors.append({"file": str(cf), "error": str(exc)[:500]})
        return (1, {"linker_errors": linker_errors, "c_files": len(c_files),
                    "error_count": len(linker_errors)}, None)

    def BuildLogs(self, params):
        # 36.4 store/retrieve full build output
        log_text = self._p(params, "log_text")
        if log_text:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                "VALUES (?, ?, ?, ?, ?)",
                ("build_log", "manual_log", log_text, 50,
                 datetime.now(timezone.utc).isoformat()))
            conn.commit()
            self.state["build_logs"].append({"manual": log_text,
                                             "created": datetime.now(timezone.utc).isoformat()})
            return (1, {"stored": True}, None)
        return (1, {"build_logs": self.state["build_logs"],
                    "count": len(self.state["build_logs"])}, None)

