#!/usr/bin/env python3
# [@GHOST]{[@file<test_report_unit.py>][@domain<Dom_Report>][@role<test>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<test_suite>][@return<tuple3>][@orch<ReportUnit>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Test suite for Dom_Report v3 — verifies Fact, 7 question slots, verbosity, lifecycle, error paths.}
# [@CLASS]{TestReportUnit}
# [@METHOD]{Run,TestOpen,TestSpineMinimum,TestSpineFail,TestEmit,TestSlotRouting,TestEmitAllKinds,TestResult,TestFinalize,TestStatus,TestRenderVerbose,TestRenderNormal,TestRenderQuiet,TestRenderNoColor,TestGetFacts,TestNoOpen,TestUnknownCommand,TestFactPrimitive,TestReportPrimitive,TestRendererPrimitive,read_state,set_config}
# [@FILEID]{core/Dom_Report/test_report_unit.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Report.ReportUnit import ReportUnit
from core.Dom_Report.Fact import Fact
from core.Dom_Report.Report import Report
from core.Dom_Report.RendererTerminal import RendererTerminal
from core.Dom_Report import Config


class TestReportUnit:
    """Test suite for Dom_Report v3. VBStyle compliant."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "results": [],
            "errors": [],
            "ru": None,
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

    def _Fresh(self):
        self.state["ru"] = ReportUnit()
        return self.state["ru"]

    def _RunAll(self, params):
        self.TestOpen(params)
        self.TestSpineMinimum(params)
        self.TestSpineFail(params)
        self.TestEmit(params)
        self.TestSlotRouting(params)
        self.TestEmitAllKinds(params)
        self.TestResult(params)
        self.TestFinalize(params)
        self.TestStatus(params)
        self.TestRenderVerbose(params)
        self.TestRenderNormal(params)
        self.TestRenderQuiet(params)
        self.TestRenderNoColor(params)
        self.TestGetFacts(params)
        self.TestNoOpen(params)
        self.TestUnknownCommand(params)
        self.TestFactPrimitive(params)
        self.TestReportPrimitive(params)
        self.TestRendererPrimitive(params)
        total = len(self.state["results"])
        failed = len(self.state["errors"])
        passed = total - failed
        summary = "Total: %d, Passed: %d, Failed: %d" % (total, passed, failed)
        ok = failed == 0
        return (1 if ok else 0, {"summary": summary, "passed": passed, "failed": failed, "results": list(self.state["results"])}, None if ok else ("ERR_TESTS", summary, 0))

    # ── spine ──────────────────────────────────────────────────────────────

    def TestOpen(self, params):
        ru = self._Fresh()
        ok, _, err = ru.Run("open", {"operation": "TrainModel", "source": "Trainer.train"})
        self._Log("open", ok == 1, "ok=%d err=%s" % (ok, str(err)))
        ok, state, _ = ru.Run("read_state", {})
        self._Log("open_has_report", state["has_report"] is True, "has_report=%s" % state["has_report"])

    def TestSpineMinimum(self, params):
        ru = self._Fresh()
        ru.Run("open", {"operation": "ParseFile"})
        ru.Run("result", {"ok": True})
        ok, text, err = ru.Run("render", {"verbosity": "quiet", "use_color": False})
        match = ok == 1 and "ParseFile" in text and "PASS" in text
        self._Log("spine_minimum", match, "text=%r" % text[:80])

    def TestSpineFail(self, params):
        ru = self._Fresh()
        ru.Run("open", {"operation": "ParseFile"})
        ru.Run("result", {"ok": False, "reason": "syntax error at line 42"})
        ok, text, err = ru.Run("render", {"verbosity": "quiet", "use_color": False})
        match = ok == 1 and "FAIL" in text and "syntax error" in text
        self._Log("spine_fail_reason", match, "text=%r" % text[:80])

    # ── emit + slot routing ────────────────────────────────────────────────

    def TestEmit(self, params):
        ru = self._Fresh()
        ru.Run("open", {"operation": "Var"})
        ok, fact, err = ru.Run("emit", {"kind": "input", "name": "lr", "value": 0.01})
        match = ok == 1 and isinstance(fact, Fact) and fact.state["value"] == 0.01
        self._Log("emit_basic", match, "value=%s" % fact.state["value"])

    def TestSlotRouting(self, params):
        ru = self._Fresh()
        ru.Run("open", {"operation": "Route"})
        ru.Run("emit", {"kind": "input", "name": "file", "value": "data.txt"})
        ru.Run("emit", {"kind": "output", "name": "rows", "value": 42})
        ru.Run("emit", {"kind": "measurement", "name": "elapsed", "value": 0.34, "unit": "s"})
        ru.Run("emit", {"kind": "event", "name": "status", "value": "started"})
        ru.Run("emit", {"kind": "issue", "name": "warning", "value": "GPU hot", "severity": "warning"})
        report = ru.state["report"]
        ok1, c_in, _ = report.Run("count_slot", {"slot": Config.SLOT_INPUTS})
        ok2, c_out, _ = report.Run("count_slot", {"slot": Config.SLOT_OUTPUTS})
        ok3, c_obs, _ = report.Run("count_slot", {"slot": Config.SLOT_OBSERVATIONS})
        ok4, c_occ, _ = report.Run("count_slot", {"slot": Config.SLOT_OCCURRENCES})
        match = ok1 and c_in == 1 and ok2 and c_out == 1 and ok3 and c_obs == 1 and ok4 and c_occ == 2
        self._Log("slot_routing", match, "in=%d out=%d obs=%d occ=%d" % (c_in, c_out, c_obs, c_occ))

    def TestEmitAllKinds(self, params):
        ru = self._Fresh()
        ru.Run("open", {"operation": "Kinds"})
        kinds_tested = []
        for kind in Config.FACT_KINDS:
            if kind == Config.KIND_RESULT:
                continue
            ok, fact, err = ru.Run("emit", {"kind": kind, "name": "test_" + kind, "value": "val"})
            if ok == 1:
                kinds_tested.append(kind)
        match = len(kinds_tested) == 7
        self._Log("emit_all_kinds", match, "tested=%d" % len(kinds_tested))

    # ── result + lifecycle ─────────────────────────────────────────────────

    def TestResult(self, params):
        ru = self._Fresh()
        ru.Run("open", {"operation": "Result"})
        ok, data, err = ru.Run("result", {"ok": False, "reason": "crashed"})
        match = ok == 1 and data["result"] == "fail" and data["reason"] == "crashed"
        self._Log("result_fail", match, "data=%s" % data)

    def TestFinalize(self, params):
        ru = self._Fresh()
        ru.Run("open", {"operation": "Fin"})
        ru.Run("emit", {"kind": "issue", "name": "err", "value": "boom", "severity": "error"})
        ok, data, err = ru.Run("finalize", {})
        match = ok == 1 and data["result"] == "fail" and data["failed"] >= 1
        self._Log("finalize_auto_fail", match, "data=%s" % data)

    def TestStatus(self, params):
        ru = self._Fresh()
        ru.Run("open", {"operation": "Status"})
        ru.Run("emit", {"kind": "event", "name": "status", "value": "success"})
        ru.Run("finalize", {})
        ok, data, err = ru.Run("status", {})
        match = ok == 1 and data["result"] == "ok" and data["operation"] == "Status"
        self._Log("status_ok", match, "data=%s" % data)

    # ── render with verbosity ──────────────────────────────────────────────

    def _BuildRichReport(self):
        ru = self._Fresh()
        ru.Run("open", {"operation": "TrainModel", "source": "Trainer.train"})
        ru.Run("emit", {"kind": "input", "name": "learning_rate", "value": 0.01})
        ru.Run("emit", {"kind": "input", "name": "epochs", "value": 250})
        ru.Run("emit", {"kind": "output", "name": "model_path", "value": "/tmp/model.bin"})
        ru.Run("emit", {"kind": "measurement", "name": "elapsed", "value": 12.44, "unit": "s"})
        ru.Run("emit", {"kind": "measurement", "name": "memory", "value": 5368709120, "unit": "bytes"})
        ru.Run("emit", {"kind": "event", "name": "checkpoint", "value": "saved"})
        ru.Run("emit", {"kind": "issue", "name": "gpu_warning", "value": "GPU at 87%", "severity": "warning"})
        ru.Run("emit", {"kind": "issue", "name": "crash", "value": "model collapsed", "severity": "error"})
        ru.Run("emit", {"kind": "message", "name": "info", "value": "using MPS backend"})
        ru.Run("result", {"ok": False, "reason": "model collapsed at epoch 43"})
        return ru

    def TestRenderVerbose(self, params):
        ru = self._BuildRichReport()
        ok, text, err = ru.Run("render", {"verbosity": "verbose", "use_color": False})
        has_lr = "learning_rate" in text
        has_model = "model_path" in text
        has_elapsed = "elapsed" in text
        has_checkpoint = "checkpoint" in text
        has_gpu = "GPU at 87%" in text or "gpu_warning" in text
        has_crash = "model collapsed" in text or "crash" in text
        has_info = "using MPS" in text or "info" in text
        has_spine = "TrainModel" in text and "FAIL" in text
        match = ok == 1 and has_spine and has_lr and has_model and has_elapsed and has_checkpoint and has_gpu and has_crash and has_info
        self._Log("render_verbose_shows_all", match, "spine=%s lr=%s out=%s obs=%s evt=%s warn=%s err=%s msg=%s" % (has_spine, has_lr, has_model, has_elapsed, has_checkpoint, has_gpu, has_crash, has_info))

    def TestRenderNormal(self, params):
        ru = self._BuildRichReport()
        ok, text, err = ru.Run("render", {"verbosity": "normal", "use_color": False})
        has_spine = "TrainModel" in text and "FAIL" in text
        has_gpu = "GPU at 87%" in text or "gpu_warning" in text
        has_crash = "model collapsed" in text or "crash" in text
        has_summary = "Summary" in text
        has_lr = "learning_rate" in text
        has_checkpoint = "checkpoint" in text
        has_info = "using MPS" in text
        match = ok == 1 and has_spine and has_gpu and has_crash and has_summary and not has_lr and not has_checkpoint and not has_info
        self._Log("render_normal_issues_only", match, "spine=%s warn=%s err=%s sum=%s lr=%s evt=%s msg=%s" % (has_spine, has_gpu, has_crash, has_summary, has_lr, has_checkpoint, has_info))

    def TestRenderQuiet(self, params):
        ru = self._BuildRichReport()
        ok, text, err = ru.Run("render", {"verbosity": "quiet", "use_color": False})
        has_spine = "TrainModel" in text and "FAIL" in text and "model collapsed at epoch 43" in text
        has_lr = "learning_rate" in text
        has_events = "checkpoint" in text or "GPU" in text
        has_summary = "Summary" in text
        match = ok == 1 and has_spine and not has_lr and not has_events and not has_summary
        self._Log("render_quiet_spine_only", match, "spine=%s lr=%s events=%s sum=%s" % (has_spine, has_lr, has_events, has_summary))

    def TestRenderNoColor(self, params):
        ru = self._BuildRichReport()
        ok, text, err = ru.Run("render", {"verbosity": "verbose", "use_color": False})
        has_ansi = "\033[" in text
        match = ok == 1 and not has_ansi
        self._Log("render_no_color", match, "has_ansi=%s" % has_ansi)

    # ── get_facts ──────────────────────────────────────────────────────────

    def TestGetFacts(self, params):
        ru = self._Fresh()
        ru.Run("open", {"operation": "Facts", "source": "Test.run"})
        ru.Run("emit", {"kind": "input", "name": "a", "value": 1})
        ru.Run("emit", {"kind": "output", "name": "b", "value": 2})
        ru.Run("result", {"ok": True})
        ok, facts, err = ru.Run("get_facts", {})
        match = ok == 1 and len(facts) >= 4
        self._Log("get_facts", match, "count=%d" % len(facts))

    # ── error paths ────────────────────────────────────────────────────────

    def TestNoOpen(self, params):
        ru = self._Fresh()
        ok, _, err = ru.Run("emit", {"kind": "input", "name": "x", "value": 1})
        match = ok == 0 and err is not None and err[0] == "ERR_NOT_OPEN"
        self._Log("no_open_error", match, "err=%s" % str(err))

    def TestUnknownCommand(self, params):
        ru = self._Fresh()
        ok, _, err = ru.Run("bogus")
        match = ok == 0 and err is not None and err[0] == "ERR_UNKNOWN_CMD"
        self._Log("unknown_command", match, "err=%s" % str(err))

    # ── primitives ─────────────────────────────────────────────────────────

    def TestFactPrimitive(self, params):
        f = Fact(param={"kind": "measurement", "name": "elapsed", "value": 12.4, "unit": "s"})
        ok, state, _ = f.Run("read_state", {})
        match = ok == 1 and state["kind"] == "measurement" and state["name"] == "elapsed" and state["value"] == 12.4 and state["unit"] == "s"
        self._Log("fact_primitive", match, "kind=%s name=%s value=%s" % (state["kind"], state["name"], state["value"]))

    def TestReportPrimitive(self, params):
        r = Report()
        r.Run("open", {"operation": "Test", "source": "Test.run"})
        ok, state, _ = r.Run("read_state", {})
        match = ok == 1 and state["operation"] == "Test" and state["source"] == "Test.run" and state["status"] == "open"
        self._Log("report_primitive", match, "op=%s source=%s status=%s" % (state["operation"], state["source"], state["status"]))
        r.Run("emit", {"kind": "input", "name": "x", "value": 1})
        ok, count, _ = r.Run("count_slot", {"slot": Config.SLOT_INPUTS})
        match2 = ok == 1 and count == 1
        self._Log("report_slot_count", match2, "inputs=%d" % count)

    def TestRendererPrimitive(self, params):
        rnd = RendererTerminal()
        ok, state, _ = rnd.Run("read_state", {})
        match = ok == 1 and "lines" in state and "verbosity" in state
        self._Log("renderer_primitive", match, "keys=%s" % sorted(state.keys()))


def main():
    suite = TestReportUnit()
    ok, result, err = suite.Run("run_all")
    for line in result["results"]:
        sys.stdout.write(line + "\n")
    sys.stdout.write("\n" + result["summary"] + "\n")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
