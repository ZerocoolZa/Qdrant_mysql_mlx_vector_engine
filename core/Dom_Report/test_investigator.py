#!/usr/bin/env python3
# [@GHOST]{[@file<test_investigator.py>][@domain<Dom_Report>][@role<test>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<test_suite>][@return<tuple3>][@orch<Investigator>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Test suite for Investigator — verifies 6-category diagnostic protocol on success and failure reports.}
# [@CLASS]{TestInvestigator}
# [@METHOD]{Run,TestInvestigateSuccess,TestInvestigateFailure,TestIdentitySuccess,TestIdentityFailure,TestOutcomeSuccess,TestOutcomeFailure,TestCauseSuccess,TestCauseFailure,TestHistoryPending,TestRepairSuccess,TestRepairFailure,TestRepairWithRecommendation,TestPreventionSuccess,TestPreventionFailure,TestRenderDiagnosis,TestNoReport,TestNotInvestigated,TestUnknownCommand,read_state,set_config}
# [@FILEID]{core/Dom_Report/test_investigator.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Report.ReportUnit import ReportUnit
from core.Dom_Report.Investigator import Investigator
from core.Dom_Report import Config


class TestInvestigator:
    """Test suite for Investigator. VBStyle compliant."""

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

    def _BuildSuccessReport(self):
        ru = ReportUnit()
        ru.Run("open", {"operation": "ReadFile", "source": "FileIO.read_file"})
        ru.Run("emit", {"kind": "input", "name": "path", "value": "/tmp/test.py"})
        ru.Run("emit", {"kind": "output", "name": "line_count", "value": 42})
        ru.Run("emit", {"kind": "measurement", "name": "elapsed", "value": 0.001, "unit": "s"})
        ru.Run("emit", {"kind": "event", "name": "read", "value": "complete"})
        ru.Run("result", {"ok": True})
        ru.Run("finalize", {})
        return ru

    def _BuildFailureReport(self):
        ru = ReportUnit()
        ru.Run("open", {"operation": "ReadFile", "source": "FileIO.read_file"})
        ru.Run("emit", {"kind": "input", "name": "path", "value": "/nonexistent/missing.py"})
        ru.Run("emit", {"kind": "issue", "name": "file_not_found", "value": "File not found", "severity": "error", "detail": "the file does not exist on disk"})
        ru.Run("emit", {"kind": "recommendation", "name": "suggestion", "value": "verify path exists before reading"})
        ru.Run("result", {"ok": False, "reason": "File not found: /nonexistent/missing.py"})
        ru.Run("finalize", {})
        return ru

    def _RunAll(self, params):
        self.TestInvestigateSuccess(params)
        self.TestInvestigateFailure(params)
        self.TestIdentitySuccess(params)
        self.TestIdentityFailure(params)
        self.TestOutcomeSuccess(params)
        self.TestOutcomeFailure(params)
        self.TestCauseSuccess(params)
        self.TestCauseFailure(params)
        self.TestHistoryPending(params)
        self.TestRepairSuccess(params)
        self.TestRepairFailure(params)
        self.TestRepairWithRecommendation(params)
        self.TestPreventionSuccess(params)
        self.TestPreventionFailure(params)
        self.TestRenderDiagnosis(params)
        self.TestNoReport(params)
        self.TestNotInvestigated(params)
        self.TestUnknownCommand(params)
        total = len(self.state["results"])
        failed = len(self.state["errors"])
        passed = total - failed
        summary = "Total: %d, Passed: %d, Failed: %d" % (total, passed, failed)
        ok = failed == 0
        return (1 if ok else 0, {"summary": summary, "passed": passed, "failed": failed, "results": list(self.state["results"])}, None if ok else ("ERR_TESTS", summary, 0))

    # ── investigate ────────────────────────────────────────────────────────

    def TestInvestigateSuccess(self, params):
        ru = self._BuildSuccessReport()
        inv = Investigator()
        ok, diagnosis, err = inv.Run("investigate", {"report": ru.state["report"]})
        match = ok == 1 and len(diagnosis) == 6
        self._Log("investigate_success", match, "categories=%d" % len(diagnosis))

    def TestInvestigateFailure(self, params):
        ru = self._BuildFailureReport()
        inv = Investigator()
        ok, diagnosis, err = inv.Run("investigate", {"report": ru.state["report"]})
        match = ok == 1 and len(diagnosis) == 6
        self._Log("investigate_failure", match, "categories=%d" % len(diagnosis))

    # ── identity ───────────────────────────────────────────────────────────

    def TestIdentitySuccess(self, params):
        ru = self._BuildSuccessReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        ident = d.get(Config.CATEGORY_IDENTITY, {})
        match = (ident.get("what_happened", {}).get("answer") == "ReadFile" and
                 ident.get("where", {}).get("answer") == "FileIO.read_file" and
                 ident.get("who", {}).get("status") == Config.ANSWER_KNOWN)
        self._Log("identity_success", match, "what=%s where=%s" % (ident.get("what_happened", {}).get("answer"), ident.get("where", {}).get("answer")))

    def TestIdentityFailure(self, params):
        ru = self._BuildFailureReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        ident = d.get(Config.CATEGORY_IDENTITY, {})
        match = (ident.get("what_happened", {}).get("answer") == "ReadFile" and
                 ident.get("who", {}).get("answer") == "FileIO.read_file")
        self._Log("identity_failure", match, "what=%s" % ident.get("what_happened", {}).get("answer"))

    # ── outcome ────────────────────────────────────────────────────────────

    def TestOutcomeSuccess(self, params):
        ru = self._BuildSuccessReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        outcome = d.get(Config.CATEGORY_OUTCOME, {})
        match = (outcome.get("did_pass", {}).get("answer") == "yes" and
                 outcome.get("did_fail", {}).get("answer") == "no" and
                 "line_count" in outcome.get("what_produced", {}).get("answer", ""))
        self._Log("outcome_success", match, "pass=%s produced=%s" % (outcome.get("did_pass", {}).get("answer"), outcome.get("what_produced", {}).get("answer")))

    def TestOutcomeFailure(self, params):
        ru = self._BuildFailureReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        outcome = d.get(Config.CATEGORY_OUTCOME, {})
        match = (outcome.get("did_pass", {}).get("answer") == "no" and
                 outcome.get("did_fail", {}).get("answer") == "yes")
        self._Log("outcome_failure", match, "pass=%s fail=%s" % (outcome.get("did_pass", {}).get("answer"), outcome.get("did_fail", {}).get("answer")))

    # ── cause ──────────────────────────────────────────────────────────────

    def TestCauseSuccess(self, params):
        ru = self._BuildSuccessReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        cause = d.get(Config.CATEGORY_CAUSE, {})
        match = (cause.get("why", {}).get("status") == Config.ANSWER_NOT_APPLICABLE and
                 cause.get("root_cause", {}).get("status") == Config.ANSWER_NOT_APPLICABLE)
        self._Log("cause_success_na", match, "why=%s" % cause.get("why", {}).get("status"))

    def TestCauseFailure(self, params):
        ru = self._BuildFailureReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        cause = d.get(Config.CATEGORY_CAUSE, {})
        match = (cause.get("why", {}).get("status") == Config.ANSWER_KNOWN and
                 "File not found" in cause.get("why", {}).get("answer", "") and
                 cause.get("root_cause", {}).get("status") == Config.ANSWER_PENDING)
        self._Log("cause_failure_known_reason", match, "why=%s root=%s" % (cause.get("why", {}).get("status"), cause.get("root_cause", {}).get("status")))

    # ── history ────────────────────────────────────────────────────────────

    def TestHistoryPending(self, params):
        ru = self._BuildFailureReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        history = d.get(Config.CATEGORY_HISTORY, {})
        match = (history.get("seen_before", {}).get("status") == Config.ANSWER_PENDING and
                 history.get("known_problem", {}).get("status") == Config.ANSWER_PENDING and
                 history.get("is_new", {}).get("status") == Config.ANSWER_PENDING)
        self._Log("history_all_pending", match, "seen=%s known=%s new=%s" % (history.get("seen_before", {}).get("status"), history.get("known_problem", {}).get("status"), history.get("is_new", {}).get("status")))

    # ── repair ─────────────────────────────────────────────────────────────

    def TestRepairSuccess(self, params):
        ru = self._BuildSuccessReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        repair = d.get(Config.CATEGORY_REPAIR, {})
        match = repair.get("is_fixable", {}).get("status") == Config.ANSWER_NOT_APPLICABLE
        self._Log("repair_success_na", match, "fixable=%s" % repair.get("is_fixable", {}).get("status"))

    def TestRepairFailure(self, params):
        ru = self._BuildFailureReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        repair = d.get(Config.CATEGORY_REPAIR, {})
        match = (repair.get("is_fixable", {}).get("status") == Config.ANSWER_KNOWN and
                 repair.get("known_fix", {}).get("status") == Config.ANSWER_KNOWN)
        self._Log("repair_failure_with_rec", match, "fixable=%s fix=%s" % (repair.get("is_fixable", {}).get("status"), repair.get("known_fix", {}).get("status")))

    def TestRepairWithRecommendation(self, params):
        ru = self._BuildFailureReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        repair = d.get(Config.CATEGORY_REPAIR, {})
        fix_answer = repair.get("known_fix", {}).get("answer", "")
        match = "verify path" in fix_answer
        self._Log("repair_rec_content", match, "fix=%s" % fix_answer)

    # ── prevention ─────────────────────────────────────────────────────────

    def TestPreventionSuccess(self, params):
        ru = self._BuildSuccessReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        prev = d.get(Config.CATEGORY_PREVENTION, {})
        match = prev.get("how_prevent", {}).get("status") == Config.ANSWER_NOT_APPLICABLE
        self._Log("prevention_success_na", match, "prevent=%s" % prev.get("how_prevent", {}).get("status"))

    def TestPreventionFailure(self, params):
        ru = self._BuildFailureReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        d = inv.state["diagnosis"]
        prev = d.get(Config.CATEGORY_PREVENTION, {})
        match = (prev.get("how_prevent", {}).get("status") == Config.ANSWER_PENDING and
                 prev.get("missing_guard", {}).get("status") == Config.ANSWER_PENDING)
        self._Log("prevention_failure_pending", match, "prevent=%s guard=%s" % (prev.get("how_prevent", {}).get("status"), prev.get("missing_guard", {}).get("status")))

    # ── render ─────────────────────────────────────────────────────────────

    def TestRenderDiagnosis(self, params):
        ru = self._BuildFailureReport()
        inv = Investigator()
        inv.Run("investigate", {"report": ru.state["report"]})
        ok, text, err = inv.Run("render_diagnosis", {"use_color": False})
        has_op = "ReadFile" in text
        has_identity = "Identity" in text
        has_cause = "Cause" in text
        has_pending = "pending" in text.lower() or "needs" in text.lower()
        match = ok == 1 and has_op and has_identity and has_cause and has_pending
        self._Log("render_diagnosis", match, "op=%s ident=%s cause=%s pending=%s" % (has_op, has_identity, has_cause, has_pending))

    # ── error paths ────────────────────────────────────────────────────────

    def TestNoReport(self, params):
        inv = Investigator()
        ok, _, err = inv.Run("investigate", {})
        match = ok == 0 and err is not None and err[0] == "ERR_REPORT"
        self._Log("no_report_error", match, "err=%s" % str(err))

    def TestNotInvestigated(self, params):
        inv = Investigator()
        ok, _, err = inv.Run("render_diagnosis", {})
        match = ok == 0 and err is not None and err[0] == "ERR_NOT_INVESTIGATED"
        self._Log("not_investigated_error", match, "err=%s" % str(err))

    def TestUnknownCommand(self, params):
        inv = Investigator()
        ok, _, err = inv.Run("bogus")
        match = ok == 0 and err is not None and err[0] == "ERR_UNKNOWN_CMD"
        self._Log("unknown_command", match, "err=%s" % str(err))


def main():
    suite = TestInvestigator()
    ok, result, err = suite.Run("run_all")
    for line in result["results"]:
        sys.stdout.write(line + "\n")
    sys.stdout.write("\n" + result["summary"] + "\n")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
