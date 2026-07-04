#!/usr/bin/env python3
# [@GHOST]{[@file<test_diagnostic_db.py>][@domain<Dom_Report>][@role<test>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<test_suite>][@return<tuple3>][@orch<DiagnosticDB>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Test suite for DiagnosticDB — verifies CRUD on all 11 tables of the diagnostic_kb MySQL database.}
# [@CLASS]{TestDiagnosticDB}
# [@METHOD]{Run,TestConnect,TestStoreIncident,TestStoreFact,TestStoreDiagnosis,TestStoreCause,TestStoreFix,TestStorePrevention,TestStoreEvidence,TestCreateProblem,TestAddSolution,TestAddLearnedRule,TestLinkIncidentProblem,TestGetIncident,TestGetDiagnosis,TestSearchProblems,TestSearchLearnedRules,TestSearchSolutions,TestUnknownCommand,read_state,set_config}
# [@FILEID]{core/Dom_Report/test_diagnostic_db.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Report.DiagnosticDB import DiagnosticDB
from core.Dom_Report.ReportUnit import ReportUnit
from core.Dom_Report.Investigator import Investigator
from core.Dom_Report import Config


class TestDiagnosticDB:
    """Test suite for DiagnosticDB. VBStyle compliant."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "results": [],
            "errors": [],
        }

    def Run(self, command, params=None):
        dispatch = {
            "run_all": self._RunAll,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", command, 0))
        return handler(params or {})

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state:
                self.state[key] = val
        return (1, dict(self.state), None)

    def _Log(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        line = "[" + status + "] " + name + (" — " + detail if detail else "")
        self.state["results"].append(line)
        if not ok:
            self.state["errors"].append(line)
        return line

    def _FreshDB(self):
        return DiagnosticDB()

    def _StoreTestIncident(self, db):
        ok, incident_id, err = db.Run("store_incident", {
            "operation": "TestReadFile",
            "source": "TestDiagnosticDB",
            "result": "fail",
            "reason": "File not found: /test/missing.py",
            "fact_count": 5,
        })
        return (ok, incident_id, err)

    def _RunAll(self, params):
        self.TestConnect(params)
        self.TestStoreIncident(params)
        self.TestStoreFact(params)
        self.TestStoreDiagnosis(params)
        self.TestStoreCause(params)
        self.TestStoreFix(params)
        self.TestStorePrevention(params)
        self.TestStoreEvidence(params)
        self.TestCreateProblem(params)
        self.TestAddSolution(params)
        self.TestAddLearnedRule(params)
        self.TestLinkIncidentProblem(params)
        self.TestGetIncident(params)
        self.TestGetDiagnosis(params)
        self.TestSearchProblems(params)
        self.TestSearchLearnedRules(params)
        self.TestSearchSolutions(params)
        self.TestUnknownCommand(params)
        total = len(self.state["results"])
        failed = len(self.state["errors"])
        passed = total - failed
        summary = "Total: %d, Passed: %d, Failed: %d" % (total, passed, failed)
        ok = failed == 0
        return (1 if ok else 0, {"summary": summary, "passed": passed, "failed": failed, "results": list(self.state["results"])}, None if ok else ("ERR_TESTS", summary, 0))

    def TestConnect(self, params):
        db = self._FreshDB()
        match = db.state["connected"] is True
        self._Log("ddb_connect", match, "connected=%s" % db.state["connected"])

    def TestStoreIncident(self, params):
        db = self._FreshDB()
        ok, incident_id, err = self._StoreTestIncident(db)
        match = ok == 1 and incident_id > 0
        self._Log("ddb_store_incident", match, "id=%d err=%s" % (incident_id, str(err)))

    def TestStoreFact(self, params):
        db = self._FreshDB()
        ok, incident_id, _ = self._StoreTestIncident(db)
        ok2, _, err2 = db.Run("store_fact", {
            "incident_id": incident_id,
            "slot": "inputs",
            "kind": "input",
            "name": "path",
            "value": "/test/missing.py",
        })
        match = ok2 == 1
        self._Log("ddb_store_fact", match, "ok=%d err=%s" % (ok2, str(err2)))

    def TestStoreDiagnosis(self, params):
        db = self._FreshDB()
        ok, incident_id, _ = self._StoreTestIncident(db)
        diagnosis = {
            Config.CATEGORY_IDENTITY: {
                "what_happened": {"status": Config.ANSWER_KNOWN, "answer": "TestReadFile"},
            },
            Config.CATEGORY_OUTCOME: {
                "did_pass": {"status": Config.ANSWER_KNOWN, "answer": "no"},
            },
        }
        ok2, count, err2 = db.Run("store_diagnosis", {"incident_id": incident_id, "diagnosis": diagnosis})
        match = ok2 == 1 and count == 2
        self._Log("ddb_store_diagnosis", match, "stored=%d" % count)

    def TestStoreCause(self, params):
        db = self._FreshDB()
        ok, incident_id, _ = self._StoreTestIncident(db)
        ok2, _, err2 = db.Run("store_cause", {
            "incident_id": incident_id,
            "cause_type": "root",
            "cause_text": "File does not exist on disk",
            "severity": 3,
        })
        match = ok2 == 1
        self._Log("ddb_store_cause", match, "ok=%d" % ok2)

    def TestStoreFix(self, params):
        db = self._FreshDB()
        ok, incident_id, _ = self._StoreTestIncident(db)
        ok2, _, err2 = db.Run("store_fix", {
            "incident_id": incident_id,
            "fix_type": "recommended",
            "fix_action": "Check file exists before reading",
            "confidence": 0.85,
        })
        match = ok2 == 1
        self._Log("ddb_store_fix", match, "ok=%d" % ok2)

    def TestStorePrevention(self, params):
        db = self._FreshDB()
        ok, incident_id, _ = self._StoreTestIncident(db)
        ok2, _, err2 = db.Run("store_prevention", {
            "incident_id": incident_id,
            "prevention_type": "guard",
            "rule_text": "Validate file path with os.path.exists() before read_file",
        })
        match = ok2 == 1
        self._Log("ddb_store_prevention", match, "ok=%d" % ok2)

    def TestStoreEvidence(self, params):
        db = self._FreshDB()
        ok, incident_id, _ = self._StoreTestIncident(db)
        ok2, _, err2 = db.Run("store_evidence", {
            "incident_id": incident_id,
            "evidence_type": "error_message",
            "content": "FileNotFoundError: /test/missing.py",
            "source_file": "FileIO.py",
            "source_line": 42,
        })
        match = ok2 == 1
        self._Log("ddb_store_evidence", match, "ok=%d" % ok2)

    def TestCreateProblem(self, params):
        db = self._FreshDB()
        ok, problem_id, err = db.Run("create_problem", {
            "problem": "FileNotFoundError on read",
            "description": "Attempted to read a file that does not exist",
            "category": "filesystem",
        })
        match = ok == 1 and problem_id > 0
        self._Log("ddb_create_problem", match, "id=%d" % problem_id)

    def TestAddSolution(self, params):
        db = self._FreshDB()
        ok, problem_id, _ = db.Run("create_problem", {
            "problem": "TestSolutionProblem",
            "category": "test",
        })
        ok2, _, err2 = db.Run("add_solution", {
            "problem_id": problem_id,
            "solution": "Check path exists before reading",
            "weight": 0.8,
            "auto_apply": 1,
        })
        match = ok2 == 1
        self._Log("ddb_add_solution", match, "ok=%d" % ok2)

    def TestAddLearnedRule(self, params):
        db = self._FreshDB()
        ok, _, err = db.Run("add_learned_rule", {
            "pattern": "read_file without exists check",
            "fix_action": "Add os.path.exists() guard before read_file",
            "category": "error_handling",
            "confidence": 0.9,
        })
        match = ok == 1
        self._Log("ddb_add_learned_rule", match, "ok=%d" % ok)

    def TestLinkIncidentProblem(self, params):
        db = self._FreshDB()
        ok, incident_id, _ = self._StoreTestIncident(db)
        ok2, problem_id, _ = db.Run("create_problem", {
            "problem": "FileNotFoundError on read",
            "category": "filesystem",
        })
        ok3, _, err3 = db.Run("link_incident_problem", {
            "incident_id": incident_id,
            "problem_id": problem_id,
        })
        match = ok3 == 1
        self._Log("ddb_link_incident_problem", match, "ok=%d" % ok3)

    def TestGetIncident(self, params):
        db = self._FreshDB()
        ok, incident_id, _ = self._StoreTestIncident(db)
        db.Run("store_fact", {
            "incident_id": incident_id,
            "slot": "inputs",
            "kind": "input",
            "name": "path",
            "value": "/test/missing.py",
        })
        ok2, incident, err2 = db.Run("get_incident", {"incident_id": incident_id})
        match = ok2 == 1 and incident["operation"] == "TestReadFile" and len(incident["facts"]) >= 1
        self._Log("ddb_get_incident", match, "op=%s facts=%d" % (incident.get("operation", "?"), len(incident.get("facts", []))))

    def TestGetDiagnosis(self, params):
        db = self._FreshDB()
        ok, incident_id, _ = self._StoreTestIncident(db)
        db.Run("store_diagnosis", {"incident_id": incident_id, "diagnosis": {
            Config.CATEGORY_IDENTITY: {"what_happened": {"status": "known", "answer": "TestReadFile"}},
        }})
        ok2, answers, err2 = db.Run("get_diagnosis", {"incident_id": incident_id})
        match = ok2 == 1 and len(answers) >= 1
        self._Log("ddb_get_diagnosis", match, "answers=%d" % len(answers))

    def TestSearchProblems(self, params):
        db = self._FreshDB()
        db.Run("create_problem", {"problem": "FileNotFoundError test search", "category": "test"})
        ok, results, err = db.Run("search_problems", {"search": "FileNotFoundError"})
        match = ok == 1 and len(results) > 0
        self._Log("ddb_search_problems", match, "count=%d" % len(results))

    def TestSearchLearnedRules(self, params):
        db = self._FreshDB()
        db.Run("add_learned_rule", {
            "pattern": "test pattern for search",
            "fix_action": "test fix for search",
            "category": "test",
            "confidence": 0.5,
        })
        ok, results, err = db.Run("search_learned_rules", {"search": "test pattern"})
        match = ok == 1 and len(results) > 0
        self._Log("ddb_search_learned_rules", match, "count=%d" % len(results))

    def TestSearchSolutions(self, params):
        db = self._FreshDB()
        ok, problem_id, _ = db.Run("create_problem", {"problem": "TestSolutionSearch", "category": "test"})
        db.Run("add_solution", {"problem_id": problem_id, "solution": "test solution for search", "weight": 0.7})
        ok2, results, err2 = db.Run("search_solutions", {"search": "test solution"})
        match = ok2 == 1 and len(results) > 0
        self._Log("ddb_search_solutions", match, "count=%d" % len(results))

    def TestUnknownCommand(self, params):
        db = self._FreshDB()
        ok, _, err = db.Run("bogus")
        match = ok == 0 and err is not None and err[0] == "ERR_UNKNOWN_CMD"
        self._Log("ddb_unknown_command", match, "err=%s" % str(err))


def main():
    suite = TestDiagnosticDB()
    ok, result, err = suite.Run("run_all")
    for line in result["results"]:
        sys.stdout.write(line + "\n")
    sys.stdout.write("\n" + result["summary"] + "\n")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
