#!/usr/bin/env python3
# [@GHOST]{[@file<test_knowledge_base.py>][@domain<Dom_Report>][@role<test>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<test_suite>][@return<tuple3>][@orch<KnowledgeBase>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Test suite for KnowledgeBase — verifies lookup, search, and diagnosis enrichment.}
# [@CLASS]{TestKnowledgeBase}
# [@METHOD]{Run,TestConnect,TestSearchMistakes,TestSearchSolutions,TestLookupEnrichesHistory,TestLookupEnrichesRepair,TestLookupEnrichesPrevention,TestLookupNoMatch,TestInvestigateWithKB,TestRecordFinding,TestNoDB,TestUnknownCommand,read_state,set_config}
# [@FILEID]{core/Dom_Report/test_knowledge_base.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Report.ReportUnit import ReportUnit
from core.Dom_Report.Investigator import Investigator
from core.Dom_Report.KnowledgeBase import KnowledgeBase
from core.Dom_Report import Config


class TestKnowledgeBase:
    """Test suite for KnowledgeBase. VBStyle compliant."""

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

    def _FreshKB(self):
        return KnowledgeBase()

    def _BuildFailureReport(self):
        ru = ReportUnit()
        ru.Run("open", {"operation": "ReadFile", "source": "FileIO.read_file"})
        ru.Run("emit", {"kind": "input", "name": "path", "value": "/nonexistent/missing.py"})
        ru.Run("emit", {"kind": "issue", "name": "file_not_found", "value": "File not found", "severity": "error"})
        ru.Run("result", {"ok": False, "reason": "File not found"})
        ru.Run("finalize", {})
        return ru

    def _RunAll(self, params):
        self.TestConnect(params)
        self.TestSearchMistakes(params)
        self.TestSearchSolutions(params)
        self.TestLookupEnrichesHistory(params)
        self.TestLookupEnrichesRepair(params)
        self.TestLookupEnrichesPrevention(params)
        self.TestLookupNoMatch(params)
        self.TestInvestigateWithKB(params)
        self.TestRecordFinding(params)
        self.TestNoDB(params)
        self.TestUnknownCommand(params)
        total = len(self.state["results"])
        failed = len(self.state["errors"])
        passed = total - failed
        summary = "Total: %d, Passed: %d, Failed: %d" % (total, passed, failed)
        ok = failed == 0
        return (1 if ok else 0, {"summary": summary, "passed": passed, "failed": failed, "results": list(self.state["results"])}, None if ok else ("ERR_TESTS", summary, 0))

    def TestConnect(self, params):
        kb = self._FreshKB()
        match = kb.state["connected"] is True
        self._Log("kb_connect", match, "connected=%s" % kb.state["connected"])

    def TestSearchMistakes(self, params):
        kb = self._FreshKB()
        ok, results, err = kb.Run("search_mistakes", {"term": "missing"})
        match = ok == 1 and len(results) > 0
        self._Log("kb_search_mistakes", match, "count=%d" % len(results))

    def TestSearchSolutions(self, params):
        kb = self._FreshKB()
        ok, results, err = kb.Run("search_solutions", {"term": "cascade"})
        match = ok == 1
        self._Log("kb_search_solutions", match, "count=%d" % len(results))

    def TestLookupEnrichesHistory(self, params):
        kb = self._FreshKB()
        diagnosis = {
            Config.CATEGORY_HISTORY: {
                "seen_before": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base lookup"},
                "known_problem": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base lookup"},
                "is_new": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base lookup"},
            }
        }
        ok, enriched, err = kb.Run("lookup", {"diagnosis": diagnosis, "operation": "ReadFile", "reason": "missing"})
        hist = enriched.get(Config.CATEGORY_HISTORY, {})
        match = (hist.get("seen_before", {}).get("status") == Config.ANSWER_KNOWN and
                 hist.get("is_new", {}).get("status") == Config.ANSWER_KNOWN)
        self._Log("kb_enriches_history", match, "seen=%s is_new=%s" % (hist.get("seen_before", {}).get("status"), hist.get("is_new", {}).get("status")))

    def TestLookupEnrichesRepair(self, params):
        kb = self._FreshKB()
        diagnosis = {
            Config.CATEGORY_REPAIR: {
                "is_fixable": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base lookup"},
                "known_fix": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base lookup"},
                "which_fix_worked": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base lookup"},
                "can_auto_apply": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base lookup"},
            }
        }
        ok, enriched, err = kb.Run("lookup", {"diagnosis": diagnosis, "operation": "ReadFile", "reason": "missing"})
        rep = enriched.get(Config.CATEGORY_REPAIR, {})
        match = (rep.get("is_fixable", {}).get("status") == Config.ANSWER_KNOWN and
                 rep.get("known_fix", {}).get("status") == Config.ANSWER_KNOWN)
        self._Log("kb_enriches_repair", match, "fixable=%s fix=%s" % (rep.get("is_fixable", {}).get("status"), rep.get("known_fix", {}).get("status")))

    def TestLookupEnrichesPrevention(self, params):
        kb = self._FreshKB()
        diagnosis = {
            Config.CATEGORY_PREVENTION: {
                "how_prevent": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base"},
                "missing_guard": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base"},
                "detect_earlier": {"status": Config.ANSWER_PENDING, "answer": "needs knowledge base"},
            }
        }
        ok, enriched, err = kb.Run("lookup", {"diagnosis": diagnosis, "operation": "ReadFile", "reason": "missing"})
        prev = enriched.get(Config.CATEGORY_PREVENTION, {})
        match = (prev.get("how_prevent", {}).get("status") == Config.ANSWER_KNOWN and
                 prev.get("missing_guard", {}).get("status") == Config.ANSWER_KNOWN)
        self._Log("kb_enriches_prevention", match, "prevent=%s guard=%s" % (prev.get("how_prevent", {}).get("status"), prev.get("missing_guard", {}).get("status")))

    def TestLookupNoMatch(self, params):
        kb = self._FreshKB()
        diagnosis = {
            Config.CATEGORY_HISTORY: {
                "seen_before": {"status": Config.ANSWER_PENDING, "answer": "pending"},
            }
        }
        ok, enriched, err = kb.Run("lookup", {"diagnosis": diagnosis, "operation": "UnknownOp", "reason": "zzz_nonexistent_zzz"})
        hist = enriched.get(Config.CATEGORY_HISTORY, {})
        match = hist.get("seen_before", {}).get("status") == Config.ANSWER_PENDING
        self._Log("kb_no_match_stays_pending", match, "seen=%s" % hist.get("seen_before", {}).get("status"))

    def TestInvestigateWithKB(self, params):
        ru = self._BuildFailureReport()
        kb = self._FreshKB()
        inv = Investigator()
        ok, diagnosis, err = inv.Run("investigate", {"report": ru.state["report"], "knowledge_base": kb})
        hist = diagnosis.get(Config.CATEGORY_HISTORY, {})
        rep = diagnosis.get(Config.CATEGORY_REPAIR, {})
        history_answered = hist.get("seen_before", {}).get("status") == Config.ANSWER_KNOWN
        repair_answered = rep.get("is_fixable", {}).get("status") == Config.ANSWER_KNOWN
        match = ok == 1 and history_answered and repair_answered
        self._Log("investigate_with_kb", match, "history=%s repair=%s" % (history_answered, repair_answered))

    def TestRecordFinding(self, params):
        kb = self._FreshKB()
        ok, finding, err = kb.Run("record_finding", {"category": "test", "finding": "test finding"})
        match = ok == 1 and finding["finding"] == "test finding" and len(kb.state["findings"]) == 1
        self._Log("kb_record_finding", match, "findings=%d" % len(kb.state["findings"]))

    def TestNoDB(self, params):
        kb = KnowledgeBase(param={"db_path": "/nonexistent/db.sqlite"})
        match = kb.state["connected"] is False
        ok, results, err = kb.Run("search_mistakes", {"term": "test"})
        match2 = ok == 1 and results == []
        self._Log("kb_no_db_graceful", match and match2, "connected=%s results=%s" % (kb.state["connected"], results))

    def TestUnknownCommand(self, params):
        kb = self._FreshKB()
        ok, _, err = kb.Run("bogus")
        match = ok == 0 and err is not None and err[0] == "ERR_UNKNOWN_CMD"
        self._Log("kb_unknown_command", match, "err=%s" % str(err))


def main():
    suite = TestKnowledgeBase()
    ok, result, err = suite.Run("run_all")
    for line in result["results"]:
        sys.stdout.write(line + "\n")
    sys.stdout.write("\n" + result["summary"] + "\n")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
