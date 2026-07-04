#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/utils/_test_engine.py"
# date="2026-06-26" author="Devin" session_id="phase5-quality"
# context="Project Digital Twin Phase 5 Section 50 Test Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="test_engine.py" domain="twin_test" authority="TestEngine"}
# [@SUMMARY]{summary="Test authority running unit, integration, regression tests and tracking coverage and history."}
# [@CLASS]{class="TestEngine" domain="test" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="run_unit_tests" type="command"}
# [@METHOD]{method="run_integration_tests" type="command"}
# [@METHOD]{method="run_regression" type="command"}
# [@METHOD]{method="get_coverage" type="command"}
# [@METHOD]{method="find_missing_tests" type="command"}
# [@METHOD]{method="test_history" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="Connect" type="helper"}
# [@METHOD]{method="__init__" type="ctor"}
"""
TestEngine -- authority for running tests, tracking coverage and test history.
Implements Section 50 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: run_unit_tests, run_integration_tests, run_regression, get_coverage, find_missing_tests, test_history.
"""
import os
import sqlite3
import subprocess
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
UNIT_TEST_SCRIPT = "test_everything.py"
INTEGRATION_SCRIPT = "domain_loader.py"


class TestEngine:
    """Authority for unit, integration, regression tests and coverage tracking."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "unit_test_script": UNIT_TEST_SCRIPT,
                "integration_script": INTEGRATION_SCRIPT,
                "cwd": os.path.dirname(os.path.abspath(__file__)),
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
        if command == "run_unit_tests":
            return self.RunUnitTests(params)
        elif command == "run_integration_tests":
            return self.RunIntegrationTests(params)
        elif command == "run_regression":
            return self.RunRegression(params)
        elif command == "get_coverage":
            return self.GetCoverage(params)
        elif command == "find_missing_tests":
            return self.FindMissingTests(params)
        elif command == "find_failed_tests":
            return self.FindFailedTests(params)
        elif command == "find_passed_tests":
            return self.FindPassedTests(params)
        elif command == "test_history":
            return self.TestHistory(params)
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

    def ParseTestResults(self, stdout):
        passed = 0
        failed = 0
        for line in stdout.splitlines():
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
        return passed, failed

    def StoreObservation(self, observation_type, subject, evidence, confidence):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "confidence, created) VALUES (?, ?, ?, ?, ?)",
                (
                    observation_type,
                    subject,
                    evidence,
                    confidence,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return cur.lastrowid
        except sqlite3.Error:
            return None

    def RunUnitTests(self, params):
        cwd = self._p(params, "cwd", self.state["config"]["cwd"])
        script = self._p(
            params, "unit_test_script", self.state["config"]["unit_test_script"]
        )
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
            return (0, None, ("TEST_TIMEOUT", "Unit test suite timed out", 0))
        except OSError as exc:
            return (0, None, ("TEST_ERROR", str(exc), 0))
        passed, failed = self.ParseTestResults(proc.stdout)
        total = passed + failed
        evidence = "passed=" + str(passed) + " failed=" + str(failed)
        self.StoreObservation("test_result", "unit_tests", evidence, float(passed) if total else 0.0)
        result = {
            "passed": passed,
            "failed": failed,
            "total": total,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
        self.state["results"].append(result)
        return (1, result, None)

    def RunIntegrationTests(self, params):
        cwd = self._p(params, "cwd", self.state["config"]["cwd"])
        script = self._p(
            params, "integration_script", self.state["config"]["integration_script"]
        )
        script_path = os.path.join(cwd, script)
        if not os.path.isfile(script_path):
            return (0, None, ("SCRIPT_NOT_FOUND", script_path, 0))
        try:
            proc = subprocess.run(
                ["python3", script],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("TEST_TIMEOUT", "Integration test timed out", 0))
        except OSError as exc:
            return (0, None, ("TEST_ERROR", str(exc), 0))
        passed, failed = self.ParseTestResults(proc.stdout)
        total = passed + failed
        evidence = "passed=" + str(passed) + " failed=" + str(failed)
        self.StoreObservation(
            "test_result", "integration_tests", evidence, float(passed) if total else 0.0
        )
        result = {
            "passed": passed,
            "failed": failed,
            "total": total,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
        self.state["results"].append(result)
        return (1, result, None)

    def RunRegression(self, params):
        current = self.RunUnitTests(params)
        if current[0] != 1:
            return current
        current_result = current[1]
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT observation_id, subject, evidence, created "
                "FROM observations WHERE observation_type='test_result' "
                "ORDER BY created DESC LIMIT 1"
            )
            row = cur.fetchone()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        if not row:
            result = {
                "improved": 0,
                "regressed": 0,
                "same": 0,
                "current": current_result,
                "previous": None,
                "note": "no previous test result",
            }
            return (1, result, None)
        prev_id, prev_subject, prev_evidence, prev_created = row
        prev_passed = 0
        prev_failed = 0
        if prev_evidence:
            for token in prev_evidence.split():
                if token.startswith("passed="):
                    try:
                        prev_passed = int(token.split("=")[1])
                    except (ValueError, IndexError):
                        pass
                elif token.startswith("failed="):
                    try:
                        prev_failed = int(token.split("=")[1])
                    except (ValueError, IndexError):
                        pass
        prev_total = prev_passed + prev_failed
        curr_total = current_result["total"]
        improved = 0
        regressed = 0
        same = 0
        if curr_total > 0 and prev_total > 0:
            curr_rate = current_result["passed"] / curr_total
            prev_rate = prev_passed / prev_total
            if curr_rate > prev_rate:
                improved = 1
            elif curr_rate < prev_rate:
                regressed = 1
            else:
                same = 1
        elif curr_total > 0 and prev_total == 0:
            improved = 1
        else:
            same = 1
        result = {
            "improved": improved,
            "regressed": regressed,
            "same": same,
            "current": current_result,
            "previous": {
                "observation_id": prev_id,
                "subject": prev_subject,
                "evidence": prev_evidence,
                "created": prev_created,
                "passed": prev_passed,
                "failed": prev_failed,
                "total": prev_total,
            },
        }
        self.state["results"].append(result)
        return (1, result, None)

    def GetCoverage(self, params):
        cwd = self._p(params, "cwd", self.state["config"]["cwd"])
        test_script = self._p(
            params, "unit_test_script", self.state["config"]["unit_test_script"]
        )
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM methods")
            total_methods = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        test_path = os.path.join(cwd, test_script)
        test_content = ""
        if os.path.isfile(test_path):
            try:
                with open(test_path, "r", encoding="utf-8") as fh:
                    test_content = fh.read()
            except OSError:
                test_content = ""
        try:
            cur = conn.cursor()
            cur.execute("SELECT method_name FROM methods")
            all_methods = [row[0] for row in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        covered = 0
        for mname in all_methods:
            if mname and mname in test_content:
                covered += 1
        percentage = 0.0
        if total_methods > 0:
            percentage = round((covered / total_methods) * 100, 2)
        result = {
            "covered": covered,
            "total": total_methods,
            "percentage": percentage,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def FindMissingTests(self, params):
        cwd = self._p(params, "cwd", self.state["config"]["cwd"])
        test_script = self._p(
            params, "unit_test_script", self.state["config"]["unit_test_script"]
        )
        test_path = os.path.join(cwd, test_script)
        test_content = ""
        if os.path.isfile(test_path):
            try:
                with open(test_path, "r", encoding="utf-8") as fh:
                    test_content = fh.read()
            except OSError:
                test_content = ""
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT method_id, method_name, class_id FROM methods ORDER BY method_name"
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        missing = []
        for row in rows:
            method_id, method_name, class_id = row
            if method_name in ("Run", "_p", "read_state", "set_config", "Connect", "__init__"):
                continue
            if method_name and method_name not in test_content:
                missing.append(
                    {
                        "method_id": method_id,
                        "method_name": method_name,
                        "class_id": class_id,
                    }
                )
        result = {
            "missing": missing[:DEFAULT_LIMIT],
            "count": len(missing),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def TestHistory(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT observation_id, observation_type, subject, evidence, "
                "confidence, created FROM observations "
                "WHERE observation_type='test_result' ORDER BY created"
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        history = []
        for row in rows:
            history.append(
                {
                    "observation_id": row[0],
                    "observation_type": row[1],
                    "subject": row[2],
                    "evidence": row[3],
                    "confidence": row[4],
                    "created": row[5],
                }
            )
        result = {
            "history": history[:limit],
            "count": len(history),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def FindFailedTests(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT knowledge_id, problem, solution, tags, fix_result, created "
                "FROM knowledge WHERE tags LIKE '%test%' AND fix_result='failure' "
                "ORDER BY created DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        failed = []
        for row in rows:
            failed.append({
                "knowledge_id": row[0],
                "problem": row[1],
                "solution": row[2],
                "tags": row[3],
                "fix_result": row[4],
                "created": row[5],
            })
        result = {
            "failed_tests": failed,
            "count": len(failed),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def FindPassedTests(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT knowledge_id, problem, solution, tags, fix_result, created "
                "FROM knowledge WHERE tags LIKE '%test%' AND fix_result='success' "
                "ORDER BY created DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        passed = []
        for row in rows:
            passed.append({
                "knowledge_id": row[0],
                "problem": row[1],
                "solution": row[2],
                "tags": row[3],
                "fix_result": row[4],
                "created": row[5],
            })
        result = {
            "passed_tests": passed,
            "count": len(passed),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)
