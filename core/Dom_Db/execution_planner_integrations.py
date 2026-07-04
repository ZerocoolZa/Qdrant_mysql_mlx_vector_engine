#!/usr/bin/env python3
#[@GHOST]{[@file<execution_planner_integrations.py>][@state<active>][@date<2026-07-01>][@ver<1.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<execution_planner_integrations>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}

import json
import os
import subprocess
import sqlite3
import time
from datetime import datetime


class ExecutionPlannerIntegrations:
    """Integrate ExecutionPlanner with AstRankEngine, BclPatternCollector,
    MySQL, ContextRAM, and msearch.

    Domain: cross-system orchestration wrapping ExecutionPlanner with the rest
    of the Dom_Db system (AST metrics, BCL compliance, persistence, search).
    Authority: owns integration glue between planner and external subsystems.
    """

    CTX_BINARY = "/Users/wws/contestsystem/ContextRAMSwift/.build/release/ctx"
    MSEARCH_BINARY = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/msearch"
    CTX_TIMEOUT = 30
    MSEARCH_TIMEOUT = 30
    MYSQL_HOST = "localhost"
    MYSQL_PORT = 3306
    MYSQL_USER = "root"
    MYSQL_DATABASE = "vb_shared"

    SPLIT_COMPLEXITY_THRESHOLD = 50.0
    MERGE_COMPLEXITY_THRESHOLD = 5.0
    COUPLING_REORDER_THRESHOLD = 3
    BCL_HEADER_KEYS = ("GHOST", "VBSTYLE")

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "ctx_binary": self.CTX_BINARY,
                "msearch_binary": self.MSEARCH_BINARY,
                "ctx_timeout": self.CTX_TIMEOUT,
                "msearch_timeout": self.MSEARCH_TIMEOUT,
                "mysql_host": self.MYSQL_HOST,
                "mysql_port": self.MYSQL_PORT,
                "mysql_user": self.MYSQL_USER,
                "mysql_database": self.MYSQL_DATABASE,
                "split_threshold": self.SPLIT_COMPLEXITY_THRESHOLD,
                "merge_threshold": self.MERGE_COMPLEXITY_THRESHOLD,
                "coupling_threshold": self.COUPLING_REORDER_THRESHOLD,
            },
            "last_command": None,
            "last_result": None,
            "cache": {},
        }
        if isinstance(param, dict):
            for k, v in param.items():
                self.state["config"][k] = v

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def _err(self, code, msg):
        return (0, None, (code, msg, 0))

    def _ok(self, data):
        return (1, data, None)

    def Run(self, command, params=None):
        dispatch = {
            "ast_analyze_units": self.AstAnalyzeUnits,
            "ast_optimize_plan": self.AstOptimizePlan,
            "bcl_check_units": self.BclCheckUnits,
            "bcl_repair_units": self.BclRepairUnits,
            "store_mysql": self.StoreMysql,
            "store_ctx": self.StoreCtx,
            "search_history": self.SearchHistory,
            "full_report": self.FullReport,
            "auto_plan": self.AutoPlan,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        fn = dispatch.get(command)
        if fn is None:
            return self._err("UNKNOWN_COMMAND", str(command))
        self.state["last_command"] = command
        result = fn(params or {})
        self.state["last_result"] = result
        return result

    def read_state(self, params=None):
        return (1, {
            "config": dict(self.state["config"]),
            "last_command": self.state["last_command"],
            "cache_keys": list(self.state["cache"].keys()),
        }, None)

    def set_config(self, config):
        if config is None:
            return self._err("NO_CONFIG", "config dict required")
        if not isinstance(config, dict):
            return self._err("BAD_CONFIG", "config must be a dict")
        for k, v in config.items():
            self.state["config"][k] = v
        return (1, {"updated": list(config.keys())}, None)

    # ------------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------------

    def NewAstEngine(self):
        try:
            from ast_rank_engine import AstRankEngine
        except Exception:
            try:
                import importlib.util as ilu
                here = os.path.dirname(os.path.abspath(__file__))
                p = os.path.join(here, "ast_rank_engine.py")
                spec = ilu.spec_from_file_location("ast_rank_engine", p)
                mod = ilu.module_from_spec(spec)
                spec.loader.exec_module(mod)
                AstRankEngine = mod.AstRankEngine
            except Exception as exc:
                return (0, None, ("IMPORT_FAIL", "ast_rank_engine import failed: " + str(exc), 0))
        return (1, AstRankEngine(), None)

    def NewBclCollector(self):
        try:
            from bcl_pattern_collector import BclPatternCollector
        except Exception:
            try:
                import importlib.util as ilu
                here = os.path.dirname(os.path.abspath(__file__))
                p = os.path.join(here, "bcl_pattern_collector.py")
                spec = ilu.spec_from_file_location("bcl_pattern_collector", p)
                mod = ilu.module_from_spec(spec)
                spec.loader.exec_module(mod)
                BclPatternCollector = mod.BclPatternCollector
            except Exception as exc:
                return (0, None, ("IMPORT_FAIL", "bcl_pattern_collector import failed: " + str(exc), 0))
        return (1, BclPatternCollector(), None)

    def FindFilesForClass(self, path, class_name):
        if not path or not os.path.isdir(path):
            return (1, [], None)
        target = class_name + ".py"
        found = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            if target in files:
                found.append(os.path.join(root, target))
        return (1, found, None)

    def GatherUnitMethods(self, planner, unit_name):
        ok, info, err = planner.Run("unit_info", {"unit_name": unit_name})
        if ok == 0:
            return (1, [], None)
        return (1, info.get("methods", []), None)

    def AnalyzeUnitMetrics(self, planner, unit_name, path, ast_engine):
        ok, methods, err = self.GatherUnitMethods(planner, unit_name)
        if ok == 0:
            return self._err("UNIT_METHODS_FAIL", str(err))
        origin_classes = []
        for m in methods:
            origin = m.get("origin") or m.get("origin_class") or ""
            if origin and origin not in origin_classes:
                origin_classes.append(origin)
        file_paths = []
        for cls in origin_classes:
            ok_f, files, err_f = self.FindFilesForClass(path, cls)
            if ok_f == 1:
                file_paths.extend(files)
        if not file_paths:
            return (1, {
                "unit_name": unit_name,
                "files": [],
                "complexity": 0.0,
                "cyclomatic": 0,
                "readability": 0.0,
                "coupling": 0,
                "method_count": len(methods),
            }, None)
        total_complexity = 0.0
        total_cyclomatic = 0
        total_readability = 0.0
        total_coupling = 0
        analyzed = []
        for fpath in file_paths:
            ok_a, metrics, err_a = ast_engine.Run("analyze", {"file": fpath})
            if ok_a == 1:
                total_complexity += metrics.get("complexity_score", 0.0)
                total_cyclomatic += metrics.get("cyclomatic_complexity", 0)
                analyzed.append(fpath)
            ok_r, rdata, err_r = ast_engine.Run("readability", {"file": fpath})
            if ok_r == 1:
                total_readability += rdata.get("readability_score", 0.0)
        ok_c, cdata, err_c = ast_engine.Run("coupling", {"path": path})
        if ok_c == 1:
            coupling_map = cdata.get("coupling", {}) if isinstance(cdata, dict) else {}
            if isinstance(coupling_map, dict):
                for fpath in file_paths:
                    entry = coupling_map.get(fpath)
                    if isinstance(entry, dict):
                        total_coupling += entry.get("fan_out", 0)
        n = len(analyzed) if analyzed else 1
        return (1, {
            "unit_name": unit_name,
            "files": analyzed,
            "complexity": round(total_complexity, 2),
            "cyclomatic": total_cyclomatic,
            "readability": round(total_readability / n, 2),
            "coupling": total_coupling,
            "method_count": len(methods),
        }, None)

    # ------------------------------------------------------------------
    # AST COMMANDS
    # ------------------------------------------------------------------

    def AstAnalyzeUnits(self, params):
        planner = self._p(params, "planner")
        path = self._p(params, "path")
        if planner is None:
            return self._err("NO_PLANNER", "planner instance required")
        if not path:
            return self._err("NO_PATH", "path required")
        ok, ast_engine, err = self.NewAstEngine()
        if ok == 0:
            return (0, None, err)
        ok_u, udata, err_u = planner.Run("list_units")
        if ok_u == 0:
            return (0, None, err_u)
        units = udata.get("units", [])
        unit_analysis = []
        for u in units:
            uname = u.get("unit_name", "")
            ok_m, metrics, err_m = self.AnalyzeUnitMetrics(planner, uname, path, ast_engine)
            if ok_m == 1:
                unit_analysis.append(metrics)
            else:
                unit_analysis.append({
                    "unit_name": uname,
                    "files": [],
                    "complexity": 0.0,
                    "cyclomatic": 0,
                    "readability": 0.0,
                    "coupling": 0,
                    "method_count": len(u.get("methods", [])),
                    "error": str(err_m),
                })
        ranked = sorted(
            unit_analysis,
            key=lambda x: x.get("complexity", 0.0),
            reverse=True,
        )
        most_complex = ranked[0] if ranked else None
        return self._ok({
            "unit_analysis": unit_analysis,
            "ranked": ranked,
            "most_complex": most_complex,
        })

    def AstOptimizePlan(self, params):
        planner = self._p(params, "planner")
        plan_name = self._p(params, "plan_name")
        path = self._p(params, "path")
        if planner is None:
            return self._err("NO_PLANNER", "planner instance required")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        ok_p, pinfo, err_p = planner.Run("plan_info", {"plan_name": plan_name})
        if ok_p == 0:
            return (0, None, err_p)
        unit_names = pinfo.get("units", [])
        if not path:
            path = self._p(params, "scan_path") or "."
        ok, ast_engine, err = self.NewAstEngine()
        if ok == 0:
            return (0, None, err)
        split_threshold = self.state["config"].get("split_threshold", self.SPLIT_COMPLEXITY_THRESHOLD)
        merge_threshold = self.state["config"].get("merge_threshold", self.MERGE_COMPLEXITY_THRESHOLD)
        coupling_threshold = self.state["config"].get("coupling_threshold", self.COUPLING_REORDER_THRESHOLD)
        suggestions = []
        split_candidates = []
        merge_candidates = []
        reorder_candidates = []
        for uname in unit_names:
            ok_m, metrics, err_m = self.AnalyzeUnitMetrics(planner, uname, path, ast_engine)
            if ok_m == 0:
                continue
            cx = metrics.get("complexity", 0.0)
            cyc = metrics.get("cyclomatic", 0)
            coup = metrics.get("coupling", 0)
            if cx >= split_threshold:
                split_candidates.append({
                    "unit_name": uname,
                    "complexity": cx,
                    "cyclomatic": cyc,
                    "reason": "complexity above split threshold",
                })
                suggestions.append("split unit " + uname + " (complexity=" + str(cx) + ")")
            if cx <= merge_threshold:
                merge_candidates.append({
                    "unit_name": uname,
                    "complexity": cx,
                    "reason": "complexity below merge threshold",
                })
                suggestions.append("merge unit " + uname + " into a related unit (low complexity)")
            if coup >= coupling_threshold:
                reorder_candidates.append({
                    "unit_name": uname,
                    "coupling": coup,
                    "reason": "high coupling; reorder earlier",
                })
                suggestions.append("reorder unit " + uname + " (coupling=" + str(coup) + ")")
        if len(merge_candidates) >= 2:
            suggestions.append("consider merging low-complexity units: " + ", ".join([c["unit_name"] for c in merge_candidates]))
        return self._ok({
            "suggestions": suggestions,
            "split_candidates": split_candidates,
            "merge_candidates": merge_candidates,
            "reorder_candidates": reorder_candidates,
        })

    # ------------------------------------------------------------------
    # BCL COMMANDS
    # ------------------------------------------------------------------

    def BclCheckUnits(self, params):
        planner = self._p(params, "planner")
        path = self._p(params, "path") or self._p(params, "root_path")
        if planner is None:
            return self._err("NO_PLANNER", "planner instance required")
        ok, bcl, err = self.NewBclCollector()
        if ok == 0:
            return (0, None, err)
        ok_u, udata, err_u = planner.Run("list_units")
        if ok_u == 0:
            return (0, None, err_u)
        units = udata.get("units", [])
        compliant = 0
        non_compliant = 0
        issues = []
        for u in units:
            uname = u.get("unit_name", "")
            ok_m, methods, err_m = self.GatherUnitMethods(planner, uname)
            if ok_m == 0:
                continue
            origin_classes = []
            for m in methods:
                origin = m.get("origin") or m.get("origin_class") or ""
                if origin and origin not in origin_classes:
                    origin_classes.append(origin)
            unit_files = []
            if path:
                for cls in origin_classes:
                    ok_f, files, err_f = self.FindFilesForClass(path, cls)
                    if ok_f == 1:
                        unit_files.extend(files)
            unit_has_issue = False
            for fpath in unit_files:
                if not os.path.isfile(fpath):
                    continue
                check_ok = self.FileHasBclHeaders(fpath)
                if not check_ok:
                    unit_has_issue = True
                    issues.append({
                        "unit_name": uname,
                        "file": fpath,
                        "issue": "missing or non-canonical BCL headers",
                    })
            if unit_has_issue:
                non_compliant += 1
            else:
                compliant += 1
        return self._ok({
            "compliant": compliant,
            "non_compliant": non_compliant,
            "issues": issues,
        })

    def FileHasBclHeaders(self, fpath):
        try:
            with open(fpath, "r", errors="replace") as f:
                head = "".join(f.readline() for _ in range(5))
        except Exception:
            return False
        has_ghost = "[@GHOST]" in head
        has_vbstyle = "[@VBSTYLE]" in head
        return has_ghost and has_vbstyle

    def BclRepairUnits(self, params):
        planner = self._p(params, "planner")
        dry_run = self._p(params, "dry_run", True)
        path = self._p(params, "path") or self._p(params, "root_path")
        if planner is None:
            return self._err("NO_PLANNER", "planner instance required")
        ok, bcl, err = self.NewBclCollector()
        if ok == 0:
            return (0, None, err)
        ok_u, udata, err_u = planner.Run("list_units")
        if ok_u == 0:
            return (0, None, err_u)
        units = udata.get("units", [])
        repair_files = set()
        for u in units:
            uname = u.get("unit_name", "")
            ok_m, methods, err_m = self.GatherUnitMethods(planner, uname)
            if ok_m == 0:
                continue
            origin_classes = []
            for m in methods:
                origin = m.get("origin") or m.get("origin_class") or ""
                if origin and origin not in origin_classes:
                    origin_classes.append(origin)
            if path:
                for cls in origin_classes:
                    ok_f, files, err_f = self.FindFilesForClass(path, cls)
                    if ok_f == 1:
                        for fp in files:
                            if not self.FileHasBclHeaders(fp):
                                repair_files.add(fp)
        if not repair_files:
            return self._ok({
                "repaired": 0,
                "dry_run": dry_run,
                "changes": [],
            })
        if path:
            bcl.set_config({"root_path": os.path.dirname(os.path.commonprefix(list(repair_files))) or path})
        ok_s, sdata, err_s = bcl.Run("scan", {"root_path": path} if path else None)
        if ok_s == 0:
            return (0, None, err_s)
        ok_d, canonical, err_d = bcl.Run("detect_canonical")
        if ok_d == 0:
            canonical = "ghost_header"
        ok_r, changes, err_r = bcl.Run("repair", {
            "dry_run": dry_run,
            "files": [os.path.basename(fp) for fp in repair_files],
        })
        if ok_r == 0:
            return (0, None, err_r)
        return self._ok({
            "repaired": len(changes),
            "dry_run": dry_run,
            "changes": changes,
        })

    # ------------------------------------------------------------------
    # MYSQL COMMANDS
    # ------------------------------------------------------------------

    def StoreMysql(self, params):
        planner = self._p(params, "planner")
        if planner is None:
            return self._err("NO_PLANNER", "planner instance required")
        host = self._p(params, "host", self.state["config"]["mysql_host"])
        port = self._p(params, "port", self.state["config"]["mysql_port"])
        user = self._p(params, "user", self.state["config"]["mysql_user"])
        password = self._p(params, "password", "")
        database = self._p(params, "database", self.state["config"]["mysql_database"])
        try:
            import mysql.connector
        except Exception as exc:
            return self._err("MYSQL_IMPORT_FAIL", "mysql.connector not available: " + str(exc))
        try:
            conn = mysql.connector.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
            )
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS execution_units ("
                "unit_name VARCHAR(255) NOT NULL, "
                "method_names TEXT, "
                "complexity_score REAL DEFAULT 0, "
                "created_at REAL DEFAULT 0)"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS execution_plans ("
                "plan_name VARCHAR(255) NOT NULL, "
                "unit_names TEXT, "
                "step_order TEXT, "
                "created_at REAL DEFAULT 0)"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS execution_results ("
                "plan_name VARCHAR(255) NOT NULL, "
                "step_index INT, "
                "unit_name VARCHAR(255), "
                "status VARCHAR(64), "
                "duration_ms REAL, "
                "timestamp REAL DEFAULT 0)"
            )
            conn.commit()
        except Exception as exc:
            return self._err("MYSQL_CONNECT_FAIL", str(exc))
        now = time.time()
        units_stored = 0
        plans_stored = 0
        results_stored = 0
        try:
            ok_u, udata, err_u = planner.Run("list_units")
            if ok_u == 1:
                for u in udata.get("units", []):
                    cur.execute(
                        "INSERT INTO execution_units (unit_name, method_names, complexity_score, created_at) "
                        "VALUES (%s, %s, %s, %s)",
                        (
                            u.get("unit_name", ""),
                            json.dumps(u.get("methods", [])),
                            0.0,
                            now,
                        ),
                    )
                    units_stored += 1
            ok_p, pdata, err_p = planner.Run("list_plans")
            if ok_p == 1:
                for p in pdata.get("plans", []):
                    cur.execute(
                        "INSERT INTO execution_plans (plan_name, unit_names, step_order, created_at) "
                        "VALUES (%s, %s, %s, %s)",
                        (
                            p.get("plan_name", ""),
                            json.dumps(p.get("units", [])),
                            json.dumps(p.get("order", [])),
                            now,
                        ),
                    )
                    plans_stored += 1
            ok_l, ldata, err_l = planner.Run("execution_log")
            if ok_l == 1:
                for entry in ldata.get("log", []):
                    cur.execute(
                        "INSERT INTO execution_results (plan_name, step_index, unit_name, status, duration_ms, timestamp) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            entry.get("plan", ""),
                            entry.get("step", 0),
                            entry.get("unit", ""),
                            entry.get("status", ""),
                            entry.get("duration_ms", 0),
                            now,
                        ),
                    )
                    results_stored += 1
            conn.commit()
        except Exception as exc:
            return self._err("MYSQL_STORE_FAIL", str(exc))
        finally:
            try:
                cur.close()
                conn.close()
            except Exception:
                pass
        return self._ok({
            "stored": {
                "units": units_stored,
                "plans": plans_stored,
                "results": results_stored,
            }
        })

    # ------------------------------------------------------------------
    # CONTEXT RAM COMMANDS
    # ------------------------------------------------------------------

    def StoreCtx(self, params):
        planner = self._p(params, "planner")
        if planner is None:
            return self._err("NO_PLANNER", "planner instance required")
        ctx_binary = self._p(params, "ctx_binary", self.state["config"]["ctx_binary"])
        timeout = self._p(params, "timeout", self.state["config"]["ctx_timeout"])
        plans_stored = 0
        results_stored = 0
        ok_p, pdata, err_p = planner.Run("list_plans")
        if ok_p == 0:
            return (0, None, err_p)
        for p in pdata.get("plans", []):
            content = "plan:" + p.get("plan_name", "") + " units=" + json.dumps(p.get("units", []))
            try:
                subprocess.run(
                    [ctx_binary, "put", "--type", "task", "--content", content, "--tags", "exec,plan"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                plans_stored += 1
            except Exception:
                pass
        ok_l, ldata, err_l = planner.Run("execution_log")
        if ok_l == 1:
            for entry in ldata.get("log", []):
                content = "result:" + entry.get("plan", "") + " step=" + str(entry.get("step", 0)) + " unit=" + entry.get("unit", "") + " status=" + entry.get("status", "")
                try:
                    subprocess.run(
                        [ctx_binary, "put", "--type", "result", "--content", content, "--tags", "exec,result"],
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                    results_stored += 1
                except Exception:
                    pass
        return self._ok({
            "stored": {
                "plans": plans_stored,
                "results": results_stored,
            }
        })

    # ------------------------------------------------------------------
    # MSEARCH COMMANDS
    # ------------------------------------------------------------------

    def SearchHistory(self, params):
        query = self._p(params, "query")
        if not query:
            return self._err("NO_QUERY", "query required")
        limit = self._p(params, "limit", 20)
        msearch_binary = self._p(params, "msearch_binary", self.state["config"]["msearch_binary"])
        timeout = self._p(params, "timeout", self.state["config"]["msearch_timeout"])
        if not os.path.isfile(msearch_binary):
            return self._err("BINARY_MISSING", "msearch binary not found: " + msearch_binary)
        try:
            proc = subprocess.run(
                [msearch_binary, query],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return self._err("MSEARCH_TIMEOUT", "msearch timed out")
        except Exception as exc:
            return self._err("MSEARCH_FAIL", str(exc))
        stdout = proc.stdout or ""
        results = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            results.append(line)
            if len(results) >= limit:
                break
        return self._ok({
            "results": results,
            "count": len(results),
        })

    # ------------------------------------------------------------------
    # FULL REPORT
    # ------------------------------------------------------------------

    def FullReport(self, params):
        planner = self._p(params, "planner")
        fmt = self._p(params, "format", "text")
        path = self._p(params, "path")
        if planner is None:
            return self._err("NO_PLANNER", "planner instance required")
        ok_s, stats, err_s = planner.Run("stats")
        ok_u, udata, err_u = planner.Run("list_units")
        ok_p, pdata, err_p = planner.Run("list_plans")
        ok_l, ldata, err_l = planner.Run("execution_log")
        report = {
            "generated_at": datetime.now().isoformat(),
            "stats": stats if ok_s == 1 else {},
            "units": udata.get("units", []) if ok_u == 1 else [],
            "unit_count": udata.get("count", 0) if ok_u == 1 else 0,
            "plans": pdata.get("plans", []) if ok_p == 1 else [],
            "plan_count": pdata.get("count", 0) if ok_p == 1 else 0,
            "execution_log": ldata.get("log", []) if ok_l == 1 else [],
            "log_count": ldata.get("count", 0) if ok_l == 1 else 0,
        }
        ok_ast, ast_engine, err_ast = self.NewAstEngine()
        if ok_ast == 1 and path:
            ast_units = []
            for u in report["units"]:
                uname = u.get("unit_name", "")
                ok_m, metrics, err_m = self.AnalyzeUnitMetrics(planner, uname, path, ast_engine)
                if ok_m == 1:
                    ast_units.append(metrics)
            report["ast_metrics"] = ast_units
        else:
            report["ast_metrics"] = []
        ok_bcl, bcl, err_bcl = self.NewBclCollector()
        if ok_bcl == 1:
            ok_c, cdata, err_c = self.BclCheckUnits({"planner": planner, "path": path})
            if ok_c == 1:
                report["bcl_compliance"] = cdata
            else:
                report["bcl_compliance"] = {}
        else:
            report["bcl_compliance"] = {}
        if fmt == "json":
            return self._ok(json.dumps(report, indent=2, default=str))
        lines = []
        lines.append("=== ExecutionPlanner Full Report ===")
        lines.append("Generated: " + report["generated_at"])
        lines.append("")
        lines.append("--- Stats ---")
        lines.append(json.dumps(report["stats"], indent=2, default=str))
        lines.append("")
        lines.append("--- Units (" + str(report["unit_count"]) + ") ---")
        for u in report["units"]:
            lines.append("  " + u.get("unit_name", "") + " methods=" + str(len(u.get("methods", []))))
        lines.append("")
        lines.append("--- Plans (" + str(report["plan_count"]) + ") ---")
        for p in report["plans"]:
            lines.append("  " + p.get("plan_name", "") + " units=" + str(len(p.get("units", []))))
        lines.append("")
        lines.append("--- Execution Log (" + str(report["log_count"]) + ") ---")
        for entry in report["execution_log"]:
            lines.append("  " + entry.get("plan", "") + " step=" + str(entry.get("step", 0)) + " " + entry.get("status", ""))
        lines.append("")
        lines.append("--- AST Metrics ---")
        for m in report["ast_metrics"]:
            lines.append("  " + m.get("unit_name", "") + " complexity=" + str(m.get("complexity", 0)) + " cyclomatic=" + str(m.get("cyclomatic", 0)))
        lines.append("")
        lines.append("--- BCL Compliance ---")
        lines.append(json.dumps(report["bcl_compliance"], indent=2, default=str))
        return self._ok("\n".join(lines))

    # ------------------------------------------------------------------
    # AUTO PLAN
    # ------------------------------------------------------------------

    def AutoPlan(self, params):
        path = self._p(params, "path")
        plan_name = self._p(params, "plan_name", "auto_generated")
        planner = self._p(params, "planner")
        if not path:
            return self._err("NO_PATH", "path required")
        if not os.path.isdir(path):
            return self._err("PATH_MISSING", "path does not exist: " + str(path))
        ok, ast_engine, err = self.NewAstEngine()
        if ok == 0:
            return (0, None, err)
        ok_s, scan_data, err_s = ast_engine.Run("scan", {"path": path})
        if ok_s == 0:
            return (0, None, err_s)
        run_classes = []
        import_map = {}
        for metrics in scan_data:
            fpath = metrics.get("file", "")
            if not fpath:
                continue
            base = os.path.splitext(os.path.basename(fpath))[0]
            try:
                with open(fpath, "r", errors="replace") as f:
                    source = f.read()
                import ast as ast_mod
                tree = ast_mod.parse(source, filename=fpath)
            except Exception:
                continue
            has_run = False
            imports = []
            for node in ast_mod.walk(tree):
                ntype = type(node).__name__
                if ntype == "ClassDef":
                    for item in node.body:
                        if type(item).__name__ in ("FunctionDef", "AsyncFunctionDef") and item.name == "Run":
                            has_run = True
                elif ntype == "Import":
                    for alias in node.names:
                        imports.append(alias.name)
                elif ntype == "ImportFrom":
                    if node.module:
                        imports.append(node.module)
            if has_run:
                run_classes.append(base)
                import_map[base] = [imp.split(".")[-1] for imp in imports]
        ordered = self.TopoSort(run_classes, import_map)
        if planner is not None:
            for cls in ordered:
                planner.Run("define_unit", {
                    "unit_name": cls,
                    "method_ids": [],
                    "method_names": ["Run"],
                })
            planner.Run("create_plan", {
                "plan_name": plan_name,
                "unit_names": ordered,
            })
        return self._ok({
            "plan_name": plan_name,
            "units": len(ordered),
            "order": ordered,
        })

    def TopoSort(self, nodes, dep_map):
        visited = set()
        result = []
        node_set = set(nodes)

        def visit(n):
            if n in visited:
                return
            visited.add(n)
            for dep in dep_map.get(n, []):
                if dep in node_set and dep not in visited:
                    visit(dep)
            result.append(n)

        for n in nodes:
            visit(n)
        return result
