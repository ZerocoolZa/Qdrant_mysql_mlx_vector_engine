#!/usr/bin/env python3
# [@GHOST]{[@file<Report.py>][@domain<Dom_Report>][@role<collector>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<collector>][@return<tuple3>][@orch<ReportUnit>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Report — collects facts, classifies into 7 question slots, computes derived facts at finalize. The container between emission and presentation.}
# [@CLASS]{Report}
# [@METHOD]{Run,Open,Emit,Result,Finalize,Render,Status,GetFacts,GetSlot,CountSlot,ComputeSummary,read_state,set_config}
# [@FILEID]{core/Dom_Report/Report.py

import datetime

from . import Config
from .Fact import Fact


class Report:
    """Collects facts into 7 question slots.

    The 7 slots mirror the reader's cognitive sequence:
        1. operation     — what was done
        2. source        — where it happened (implementation detail)
        3. inputs        — what went in
        4. outputs       — what came out
        5. observations  — what was observed
        6. occurrences   — what occurred (events, issues, messages)
        7. outcome       — what was the result

    self.state:
        state['operation']:   operation name (slot 1)
        state['source']:      default source stamped on facts (slot 2)
        state['slots']:       dict of slot_name → list of Fact instances
        state['status']:      'open' | 'finalized' | 'rendered'
        state['result']:      'ok' | 'fail' | 'partial' (set by Result)
        state['reason']:      failure reason
        state['created']:     ISO timestamp of Open
        state['finalized']:   ISO timestamp of Finalize
        state['rendered']:    last rendered string
        state['fact_count']:  total facts received
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "operation": "",
            "source": "",
            "slots": {slot: [] for slot in Config.QUESTION_SLOTS},
            "status": "open",
            "result": "",
            "reason": "",
            "created": "",
            "finalized": "",
            "rendered": "",
            "fact_count": 0,
        }
        if param:
            self.set_config(param)

    def Run(self, command, params=None):
        dispatch = {
            "open": self.Open,
            "emit": self.Emit,
            "result": self.Result,
            "finalize": self.Finalize,
            "render": self.Render,
            "status": self.Status,
            "get_facts": self.GetFacts,
            "get_slot": self.GetSlot,
            "count_slot": self.CountSlot,
            "compute_summary": self.ComputeSummary,
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
        return (1, {
            "operation": self.state["operation"],
            "source": self.state["source"],
            "status": self.state["status"],
            "result": self.state["result"],
            "reason": self.state["reason"],
            "created": self.state["created"],
            "finalized": self.state["finalized"],
            "fact_count": self.state["fact_count"],
            "slot_counts": {s: len(self.state["slots"][s]) for s in Config.QUESTION_SLOTS},
        }, None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state and key not in ("slots",):
                self.state[key] = val
        return (1, dict(self.state), None)

    def Open(self, params):
        operation = self._p(params, "operation", "Report")
        source = self._p(params, "source", "")
        self.state["operation"] = operation
        self.state["source"] = source
        self.state["slots"] = {slot: [] for slot in Config.QUESTION_SLOTS}
        self.state["status"] = "open"
        self.state["result"] = ""
        self.state["reason"] = ""
        self.state["created"] = datetime.datetime.now().isoformat()
        self.state["finalized"] = ""
        self.state["rendered"] = ""
        self.state["fact_count"] = 0
        if source:
            source_fact = Fact(param={
                "kind": "message",
                "name": "source",
                "value": source,
                "timestamp": self.state["created"],
            })
            self.state["slots"][Config.SLOT_SOURCE].append(source_fact)
            self.state["fact_count"] += 1
        return (1, True, None)

    def Emit(self, params):
        if self.state["status"] != "open":
            return (0, None, ("ERR_STATUS", "report not open", 0))
        kind = self._p(params, "kind", "message")
        name = self._p(params, "name", "")
        value = self._p(params, "value")
        if not name:
            return (0, None, ("ERR_PARAMS", "name required", 0))
        fact = Fact(param={
            "kind": kind,
            "name": name,
            "value": value,
            "severity": self._p(params, "severity", ""),
            "unit": self._p(params, "unit", ""),
            "detail": self._p(params, "detail", ""),
            "timestamp": datetime.datetime.now().isoformat(),
            "source": self._p(params, "source", self.state["source"]),
            "file": self._p(params, "file", ""),
            "line": self._p(params, "line", 0),
        })
        slot = Config.KIND_TO_SLOT.get(kind, Config.SLOT_OCCURRENCES)
        self.state["slots"][slot].append(fact)
        self.state["fact_count"] += 1
        return (1, fact, None)

    def Result(self, params):
        if self.state["status"] != "open":
            return (0, None, ("ERR_STATUS", "report not open", 0))
        ok_flag = self._p(params, "ok", True)
        reason = self._p(params, "reason", "")
        if ok_flag:
            self.state["result"] = "ok"
            self.state["reason"] = ""
        else:
            self.state["result"] = "fail"
            self.state["reason"] = reason
        result_fact = Fact(param={
            "kind": Config.KIND_RESULT,
            "name": "outcome",
            "value": self.state["result"],
            "detail": reason,
            "timestamp": datetime.datetime.now().isoformat(),
            "source": self.state["source"],
        })
        self.state["slots"][Config.SLOT_OUTCOME].append(result_fact)
        self.state["fact_count"] += 1
        return (1, {"result": self.state["result"], "reason": self.state["reason"]}, None)

    def Finalize(self, params=None):
        if self.state["status"] != "open":
            return (0, None, ("ERR_STATUS", "report not open", 0))
        if not self.state["result"]:
            errors = sum(1 for f in self.state["slots"][Config.SLOT_OCCURRENCES]
                         if f.state["kind"] == Config.KIND_ISSUE and f.state["severity"] == Config.SEVERITY_ERROR)
            self.state["result"] = "ok" if errors == 0 else "fail"
            if self.state["result"] == "fail":
                self.state["reason"] = "errors detected during execution"
        ok, summary_fact, _ = self.ComputeSummary({})
        if ok:
            self.state["slots"][Config.SLOT_OCCURRENCES].append(summary_fact)
            self.state["fact_count"] += 1
        self.state["status"] = "finalized"
        self.state["finalized"] = datetime.datetime.now().isoformat()
        passed, failed = self._tally()
        return (1, {
            "status": self.state["status"],
            "result": self.state["result"],
            "reason": self.state["reason"],
            "passed": passed,
            "failed": failed,
            "facts": self.state["fact_count"],
        }, None)

    def ComputeSummary(self, params=None):
        passed, failed = self._tally()
        summary_fact = Fact(param={
            "kind": "summary",
            "name": "summary",
            "value": {"passed": passed, "failed": failed, "total": passed + failed},
            "timestamp": datetime.datetime.now().isoformat(),
        })
        return (1, summary_fact, None)

    def _tally(self):
        passed = 0
        failed = 0
        for f in self.state["slots"][Config.SLOT_OCCURRENCES]:
            if f.state["kind"] == Config.KIND_EVENT and f.state["name"] == "status":
                if f.state["value"] == "success":
                    passed += 1
                elif f.state["value"] == "error":
                    failed += 1
            if f.state["kind"] == Config.KIND_ISSUE:
                if f.state["severity"] == Config.SEVERITY_ERROR:
                    failed += 1
                elif f.state["severity"] == Config.SEVERITY_INFO:
                    passed += 1
        return (passed, failed)

    def Render(self, params):
        renderer = self._p(params, "renderer")
        if renderer is None:
            return (0, None, ("ERR_RENDERER", "renderer required", 0))
        if self.state["status"] == "open":
            ok, _, err = self.Finalize({})
            if not ok:
                return (ok, None, err)
        ok, text, err = renderer.Run("render", {
            "report": self,
            "use_color": self._p(params, "use_color", True),
            "verbosity": self._p(params, "verbosity", Config.VERBOSITY_NORMAL),
        })
        if not ok:
            return (ok, None, err)
        self.state["rendered"] = text
        self.state["status"] = "rendered"
        return (1, text, None)

    def Status(self, params=None):
        if self.state["status"] == "open":
            return (0, None, ("ERR_OPEN", "report not finalized", 0))
        passed, failed = self._tally()
        summary = {
            "operation": self.state["operation"],
            "result": self.state["result"],
            "reason": self.state["reason"],
            "passed": passed,
            "failed": failed,
            "total": passed + failed,
            "facts": self.state["fact_count"],
        }
        if self.state["result"] == "ok":
            return (1, summary, None)
        return (0, summary, ("ERR_REPORT", "report has failures", 0))

    def GetFacts(self, params=None):
        all_facts = []
        for slot in Config.QUESTION_SLOTS:
            all_facts.extend(self.state["slots"][slot])
        return (1, all_facts, None)

    def GetSlot(self, params):
        slot = self._p(params, "slot")
        if slot not in self.state["slots"]:
            return (0, None, ("ERR_SLOT", "unknown slot: %s" % slot, 0))
        return (1, list(self.state["slots"][slot]), None)

    def CountSlot(self, params):
        slot = self._p(params, "slot")
        if slot not in self.state["slots"]:
            return (0, None, ("ERR_SLOT", "unknown slot: %s" % slot, 0))
        return (1, len(self.state["slots"][slot]), None)
