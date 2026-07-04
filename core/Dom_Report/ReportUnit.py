#!/usr/bin/env python3
# [@GHOST]{[@file<ReportUnit.py>][@domain<Dom_Report>][@role<facade>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<facade>][@return<tuple3>][@orch<VbsMain>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{ReportUnit v3 — facade. The ONLY class application code imports. Open+Emit+Result+Render. One fact type, one emit method, 7 question slots.}
# [@CLASS]{ReportUnit}
# [@METHOD]{Run,Open,Emit,Result,Finalize,Render,Status,GetFacts,read_state,set_config}
# [@WCL]{[@self_contained<true>][@input<facts>][@output<terminal_text>][@commands<open|emit|result|finalize|render|status|get_facts|read_state|set_config>]}
# [@FILEID]{core/Dom_Report/ReportUnit.py

from .Report import Report
from .RendererTerminal import RendererTerminal
from . import Config


class ReportUnit:
    """Facade — the only class application code imports.

    SPINE (required minimum):
        Open(operation, source)    — what operation, which code produced it
        Result(ok, reason)        — did it succeed, and if not why

    CONTENT (optional enrichment — emit as many facts as you want):
        Emit(kind, name, value)   — one method, 8 kinds

    LIFECYCLE:
        Open, Emit, Result, Finalize, Render(verbosity), Status

    VERBOSITY:
        quiet:   spine only (operation + outcome)
        normal:  spine + issues + summary
        verbose: spine + all 7 slots

    self.state:
        state['report']:     Report instance
        state['renderer']:   RendererTerminal instance
        state['use_color']:  color toggle
        state['verbosity']:  default verbosity for Render
        state['stats']:      op counters
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "report": None,
            "renderer": RendererTerminal(),
            "use_color": True,
            "verbosity": Config.VERBOSITY_NORMAL,
            "stats": {"emits": 0, "renders": 0},
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
            "use_color": self.state["use_color"],
            "verbosity": self.state["verbosity"],
            "stats": dict(self.state["stats"]),
            "has_report": self.state["report"] is not None,
        }, None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state and key not in ("report", "renderer"):
                self.state[key] = val
        return (1, dict(self.state), None)

    def _require_open(self):
        if self.state["report"] is None:
            return (0, None, ("ERR_NOT_OPEN", "call Open first", 0))
        return (1, True, None)

    # ================================================================
    # SPINE
    # ================================================================

    def Open(self, params):
        operation = self._p(params, "operation", "Report")
        source = self._p(params, "source", "")
        self.state["report"] = Report()
        self.state["stats"] = {"emits": 0, "renders": 0}
        ok, _, err = self.state["report"].Run("open", {"operation": operation, "source": source})
        if not ok:
            return (ok, None, err)
        return (1, True, None)

    def Result(self, params):
        ok, _, err = self._require_open()
        if not ok:
            return (ok, None, err)
        ok_flag = self._p(params, "ok", True)
        reason = self._p(params, "reason", "")
        return self.state["report"].Run("result", {"ok": ok_flag, "reason": reason})

    # ================================================================
    # CONTENT
    # ================================================================

    def Emit(self, params):
        ok, _, err = self._require_open()
        if not ok:
            return (ok, None, err)
        ok, fact, err = self.state["report"].Run("emit", params)
        if not ok:
            return (ok, None, err)
        self.state["stats"]["emits"] += 1
        return (1, fact, None)

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def Finalize(self, params=None):
        ok, _, err = self._require_open()
        if not ok:
            return (ok, None, err)
        return self.state["report"].Run("finalize", {})

    def Render(self, params=None):
        ok, _, err = self._require_open()
        if not ok:
            return (ok, None, err)
        use_color = self._p(params, "use_color", self.state["use_color"])
        verbosity = self._p(params, "verbosity", self.state["verbosity"])
        ok, text, err = self.state["report"].Run("render", {
            "renderer": self.state["renderer"],
            "use_color": use_color,
            "verbosity": verbosity,
        })
        if not ok:
            return (ok, None, err)
        self.state["stats"]["renders"] += 1
        return (1, text, None)

    def Status(self, params=None):
        ok, _, err = self._require_open()
        if not ok:
            return (ok, None, err)
        return self.state["report"].Run("status", {})

    def GetFacts(self, params=None):
        ok, _, err = self._require_open()
        if not ok:
            return (ok, None, err)
        return self.state["report"].Run("get_facts", {})
