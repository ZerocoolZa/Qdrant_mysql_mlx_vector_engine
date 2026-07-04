#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/build_pipeline.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 32 Build Pipeline"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="build_pipeline.py" domain="twin_build" authority="BuildPipeline"}
# [@SUMMARY]{summary="Build pipeline authority that orchestrates scan, parse, index, BCL extract, graph build, validate, learn, store, test, and report."}
# [@CLASS]{class="BuildPipeline" domain="build" authority="single"}
# [@METHOD]{method="build" type="command"}
# [@METHOD]{method="build_step" type="command"}
# [@METHOD]{method="rebuild" type="command"}
# [@METHOD]{method="incremental_build" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<BuildPipeline: orchestrates scan/parse/index/BCL/graph/validate/learn/store/test/report. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
BuildPipeline -- Build pipeline orchestrator.
Implements Section 32 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: build, build_step, rebuild, incremental_build.
"""
import ast
import hashlib
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import ingestion_engine
import graph_builder
import bcl_engine
import validation_engine
import knowledge_engine
import report_engine


class BuildPipeline:
    """Build pipeline orchestrator."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
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
        if command == "build":
            return self.Build(params)
        elif command == "build_step":
            return self.BuildStep(params)
        elif command == "rebuild":
            return self.Rebuild(params)
        elif command == "incremental_build":
            return self.IncrementalBuild(params)

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

    def Scan(self, params):
        target_dir = self._p(params, "target_dir", _THIS_DIR)
        ing = ingestion_engine.IngestionEngine(param=self.state["config"])
        res = ing.Run("scan", {"target_dir": target_dir})
        if res[0] != 1:
            return res
        self.state["results"].append({"step": "scan", "data": res[1]})
        return res

    def Parse(self, params):
        target_dir = self._p(params, "target_dir", _THIS_DIR)
        py_files = sorted(pathlib.Path(target_dir).rglob("*.py"))
        parsed = 0
        failed = []
        for pyf in py_files:
            try:
                text = pyf.read_text(encoding="utf-8", errors="replace")
                ast.parse(text, filename=str(pyf))
                parsed += 1
            except SyntaxError as exc:
                failed.append({"file": str(pyf), "error": str(exc)})
        result = {"parsed": parsed, "failed": failed, "total": len(py_files)}
        self.state["results"].append({"step": "parse", "data": result})
        return (1, result, None)

    def Index(self, params):
        target_dir = self._p(params, "target_dir", _THIS_DIR)
        ing = ingestion_engine.IngestionEngine(param=self.state["config"])
        res = ing.Run("ingest_directory", {"target_dir": target_dir})
        if res[0] != 1:
            return res
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files")
        file_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        class_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        method_count = cur.fetchone()[0]
        result = {
            "files": file_count,
            "classes": class_count,
            "methods": method_count,
            "ingest_result": res[1],
        }
        self.state["results"].append({"step": "index", "data": result})
        return (1, result, None)

    def BclExtract(self, params):
        bcl_eng = bcl_engine.BclEngine(param=self.state["config"])
        res = bcl_eng.Run("extract_bcl", params)
        if res[0] != 1:
            return res
        missing_res = bcl_eng.Run("report_missing", params)
        result = {
            "extract_result": res[1],
            "missing": missing_res[1] if missing_res[0] == 1 else None,
        }
        self.state["results"].append({"step": "bcl_extract", "data": result})
        return (1, result, None)

    def GraphBuild(self, params):
        gb = graph_builder.GraphBuilder(param=self.state["config"])
        res = gb.Run("build_all", params)
        if res[0] != 1:
            return res
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        edge_count = cur.fetchone()[0]
        cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        by_type = {row[0]: row[1] for row in cur.fetchall()}
        result = {"edges": edge_count, "by_type": by_type, "build_result": res[1]}
        self.state["results"].append({"step": "graph_build", "data": result})
        return (1, result, None)

    def Validate(self, params):
        ve = validation_engine.ValidationEngine(param=self.state["config"])
        res = ve.Run("validate_all", params)
        if res[0] != 1:
            return res
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        integrity = cur.fetchone()[0]
        result = {"integrity": integrity, "validation_result": res[1]}
        self.state["results"].append({"step": "validate", "data": result})
        return (1, result, None)

    def Learn(self, params):
        ke = knowledge_engine.KnowledgeEngine(param=self.state["config"])
        res = ke.Run("learn", params)
        if res[0] != 1:
            return res
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM knowledge")
        knowledge_count = cur.fetchone()[0]
        result = {"knowledge_rows": knowledge_count, "learn_result": res[1]}
        self.state["results"].append({"step": "learn", "data": result})
        return (1, result, None)

    def Store(self, params):
        conn = self.Connect()
        conn.commit()
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        integrity = cur.fetchone()[0]
        result = {"committed": True, "integrity": integrity}
        self.state["results"].append({"step": "store", "data": result})
        return (1, result, None)

    def Test(self, params):
        cwd = self._p(params, "cwd", _THIS_DIR)
        script = self._p(params, "test_script", "test_everything.py")
        script_path = os.path.join(cwd, script)
        if not os.path.isfile(script_path):
            return (0, None, ("TEST_NOT_FOUND", script_path, 0))
        try:
            proc = subprocess.run(
                ["python3", script],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("TEST_TIMEOUT", "Test suite timed out", 0))
        except OSError as exc:
            return (0, None, ("TEST_ERROR", str(exc), 0))
        passed = 0
        failed = 0
        for line in proc.stdout.splitlines():
            if "RESULTS:" in line:
                parts = line.split("RESULTS:")[1].strip()
                for token in parts.split(","):
                    token = token.strip()
                    if "passed" in token:
                        try:
                            passed = int(token.split()[0])
                        except (ValueError, IndexError):
                            pass
                    elif "failed" in token:
                        try:
                            failed = int(token.split()[0])
                        except (ValueError, IndexError):
                            pass
        result = {
            "passed": passed,
            "failed": failed,
            "total": passed + failed,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-500:],
            "stderr_tail": proc.stderr[-500:],
        }
        self.state["results"].append({"step": "test", "data": result})
        return (1, result, None)

    def Report(self, params):
        re_eng = report_engine.ReportEngine(param=self.state["config"])
        res = re_eng.Run("full_report", params)
        if res[0] != 1:
            return res
        result = {"report": res[1]}
        self.state["results"].append({"step": "report", "data": result})
        return (1, result, None)

    def Build(self, params):
        steps = {}
        step_order = [
            ("scan", self.Scan),
            ("parse", self.Parse),
            ("index", self.Index),
            ("bcl_extract", self.BclExtract),
            ("graph_build", self.GraphBuild),
            ("validate", self.Validate),
            ("learn", self.Learn),
            ("store", self.Store),
            ("test", self.Test),
            ("report", self.Report),
        ]
        all_ok = True
        for step_name, step_fn in step_order:
            skip = self._p(params, "skip_" + step_name, False)
            if skip:
                steps[step_name] = {"skipped": True}
                continue
            try:
                res = step_fn(params)
                if res[0] == 1:
                    steps[step_name] = res[1]
                else:
                    steps[step_name] = {"error": res[2]}
                    all_ok = False
                    if not self._p(params, "continue_on_error", False):
                        break
            except Exception as exc:
                steps[step_name] = {"error": str(exc)}
                all_ok = False
                if not self._p(params, "continue_on_error", False):
                    break
        steps["all_ok"] = all_ok
        steps["created"] = datetime.now(timezone.utc).isoformat()
        return (1, {"build": steps}, None)

    def BuildStep(self, params):
        step_name = self._p(params, "step_name")
        if not step_name:
            return (0, None, ("NO_PARAM", "step_name required", 0))
        step_map = {
            "scan": self.Scan,
            "parse": self.Parse,
            "index": self.Index,
            "bcl_extract": self.BclExtract,
            "graph_build": self.GraphBuild,
            "validate": self.Validate,
            "learn": self.Learn,
            "store": self.Store,
            "test": self.Test,
            "report": self.Report,
        }
        step_fn = step_map.get(step_name)
        if step_fn is None:
            return (0, None, ("UNKNOWN_STEP", "Unknown step: " + str(step_name), 0))
        return step_fn(params)

    def Rebuild(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        for table in ("edges", "methods", "classes", "files", "knowledge", "attempts", "observations"):
            try:
                cur.execute("DELETE FROM " + table)
            except sqlite3.OperationalError:
                pass
        conn.commit()
        return self.Build(params)

    def IncrementalBuild(self, params):
        target_dir = self._p(params, "target_dir", _THIS_DIR)
        py_files = sorted(pathlib.Path(target_dir).rglob("*.py"))
        current_hashes = {}
        for pyf in py_files:
            try:
                text = pyf.read_text(encoding="utf-8", errors="replace")
                current_hashes[str(pyf)] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            except OSError:
                continue
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT path, hash FROM files WHERE status='active'")
        db_hashes = {row[0]: row[1] for row in cur.fetchall()}
        changed = []
        added = []
        removed = []
        for fpath, fhash in current_hashes.items():
            if fpath not in db_hashes:
                added.append(fpath)
            elif db_hashes[fpath] != fhash:
                changed.append(fpath)
        for fpath in db_hashes:
            if fpath not in current_hashes:
                removed.append(fpath)
        if not changed and not added and not removed:
            return (1, {"incremental": True, "changed": [], "added": [], "removed": [], "message": "no changes detected"}, None)
        ing = ingestion_engine.IngestionEngine(param=self.state["config"])
        for fpath in changed + added:
            ing.Run("ingest_file", {"file_path": fpath})
        for fpath in removed:
            cur.execute("UPDATE files SET status='deleted' WHERE path=?", (fpath,))
        conn.commit()
        if changed or added:
            self.GraphBuild(params)
            self.Validate(params)
        result = {
            "incremental": True,
            "changed": changed,
            "added": added,
            "removed": removed,
            "changed_count": len(changed),
            "added_count": len(added),
            "removed_count": len(removed),
        }
        return (1, result, None)

