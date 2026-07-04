#!/usr/bin/env python3
# [@GHOST]{[@file<RendererTerminal.py>][@domain<Dom_Report>][@role<renderer>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<renderer>][@return<tuple3>][@orch<Report>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{TerminalRenderer v3 — walks 7 question slots in order, presents facts filtered by verbosity. Slot 1 + 7 always shown.}
# [@CLASS]{RendererTerminal}
# [@METHOD]{Run,render,read_state,set_config,render_spine,render_slot,render_fact,render_summary}
# [@FILEID]{core/Dom_Report/RendererTerminal.py

import datetime

from . import Config
from .Fact import Fact


class RendererTerminal:
    """Walks 7 question slots in order, presents facts.

    Verbosity controls which slots are shown:
        quiet:   slots 1 (operation) + 7 (outcome) only
        normal:  slots 1 + 6 (issues only) + 7
        verbose: all 7 slots

    self.state:
        state['lines']:     accumulated output lines
        state['use_color']: whether to emit ANSI codes
        state['verbosity']: current verbosity level
        state['stats']:     render counters
    """

    SLOT_LABELS = {
        Config.SLOT_OPERATION: "Operation",
        Config.SLOT_SOURCE: "Source",
        Config.SLOT_INPUTS: "Inputs",
        Config.SLOT_OUTPUTS: "Outputs",
        Config.SLOT_OBSERVATIONS: "Observations",
        Config.SLOT_OCCURRENCES: "Occurrences",
        Config.SLOT_OUTCOME: "Outcome",
    }

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "lines": [],
            "use_color": True,
            "verbosity": Config.VERBOSITY_NORMAL,
            "stats": {"facts": 0, "slots": 0},
        }
        if param:
            self.set_config(param)

    def Run(self, command, params=None):
        dispatch = {
            "render": self.render,
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

    def render(self, params):
        report = self._p(params, "report")
        self.state["use_color"] = self._p(params, "use_color", True)
        self.state["verbosity"] = self._p(params, "verbosity", Config.VERBOSITY_NORMAL)
        if self.state["verbosity"] not in Config.VERBOSITY_LEVELS:
            self.state["verbosity"] = Config.VERBOSITY_NORMAL
        if report is None:
            return (0, None, ("ERR_REPORT", "report required", 0))
        ok, rstate, _ = report.Run("read_state", {})
        if not ok:
            return (ok, None, _)
        self.state["lines"] = []
        self.state["stats"] = {"facts": 0, "slots": 0}
        self._render_spine(rstate)
        verbose = self.state["verbosity"] == Config.VERBOSITY_VERBOSE
        normal = self.state["verbosity"] == Config.VERBOSITY_NORMAL
        if verbose or normal:
            self._emit("")
            if verbose:
                self._render_slot_full(report, Config.SLOT_SOURCE)
                self._render_slot_full(report, Config.SLOT_INPUTS)
                self._render_slot_full(report, Config.SLOT_OUTPUTS)
                self._render_slot_full(report, Config.SLOT_OBSERVATIONS)
            if verbose:
                self._render_slot_full(report, Config.SLOT_OCCURRENCES)
            elif normal:
                self._render_slot_issues_only(report, Config.SLOT_OCCURRENCES)
        text = "\n".join(self.state["lines"])
        return (1, text, None)

    def _render_spine(self, rstate):
        operation = rstate.get("operation", "Report")
        result = rstate.get("result", "ok")
        reason = rstate.get("reason", "")
        result_label = {"ok": "PASS", "fail": "FAIL", "partial": "PARTIAL", "": "OPEN"}.get(result, result.upper())
        result_color = Config.COLOR_GREEN if result == "ok" else Config.COLOR_RED if result == "fail" else Config.COLOR_YELLOW
        self._emit(self._color(Config.COLOR_BOLD, operation))
        self._emit(self._color(Config.COLOR_DIM, "=" * min(len(operation), Config.TERMINAL_WIDTH)))
        self._emit("")
        spine_line = "Result: %s" % self._color(result_color, result_label)
        if reason:
            spine_line += "  —  %s" % self._color(result_color, reason)
        self._emit(self._color(Config.COLOR_BOLD, spine_line))

    def _render_slot_full(self, report, slot_name):
        ok, facts, _ = report.Run("get_slot", {"slot": slot_name})
        if not ok or not facts:
            return
        self.state["stats"]["slots"] += 1
        label = self.SLOT_LABELS.get(slot_name, slot_name.title())
        self._emit(self._color(Config.COLOR_BOLD, label))
        for fact in facts:
            if fact.state["kind"] == "summary":
                self._render_summary(fact)
            else:
                self._render_fact(fact)
        self._emit("")

    def _render_slot_issues_only(self, report, slot_name):
        ok, facts, _ = report.Run("get_slot", {"slot": slot_name})
        if not ok or not facts:
            return
        issues = [f for f in facts if f.state["kind"] in (Config.KIND_ISSUE, "summary")]
        if not issues:
            return
        self.state["stats"]["slots"] += 1
        label = self.SLOT_LABELS.get(slot_name, slot_name.title())
        self._emit(self._color(Config.COLOR_BOLD, label))
        for fact in issues:
            if fact.state["kind"] == "summary":
                self._render_summary(fact)
            else:
                self._render_fact(fact)
        self._emit("")

    def _render_fact(self, fact):
        self.state["stats"]["facts"] += 1
        kind = fact.state["kind"]
        name = fact.state["name"]
        value = fact.state["value"]
        unit = fact.state["unit"]
        severity = fact.state["severity"]
        detail = fact.state["detail"]
        if kind == Config.KIND_ISSUE:
            sym = Config.SEVERITY_SYMBOLS.get(severity, "!")
            color = Config.SEVERITY_COLORS.get(severity, Config.COLOR_YELLOW)
            line = "%s %s" % (self._color(color, sym), name)
            if value:
                line += ": %s" % self._format_value(value)
            self._emit(line)
            if detail:
                self._emit(self._color(Config.COLOR_DIM, "    " + detail))
        elif kind == Config.KIND_EVENT:
            sym = Config.KIND_SYMBOLS.get(kind, "→")
            line = "%s %s" % (self._color(Config.COLOR_BLUE, sym), name)
            if value:
                line += ": %s" % self._format_value(value)
            self._emit(line)
        elif kind == Config.KIND_MESSAGE:
            sym = Config.KIND_SYMBOLS.get(kind, "•")
            line = "%s %s" % (self._color(Config.COLOR_CYAN, sym), name)
            if value:
                line += ": %s" % self._format_value(value)
            self._emit(line)
        elif kind == Config.KIND_RECOMMENDATION:
            sym = Config.KIND_SYMBOLS.get(kind, "↳")
            line = "%s %s" % (self._color(Config.COLOR_MAGENTA, sym), name)
            if value:
                line += ": %s" % self._format_value(value)
            self._emit(line)
        elif kind == Config.KIND_RESULT:
            pass  # outcome is rendered in the spine
        else:
            unit_str = (" " + unit) if unit else ""
            line = "%s: %s%s" % (name, self._format_value(value), unit_str)
            self._emit(line)
            if detail:
                self._emit(self._color(Config.COLOR_DIM, "    " + detail))

    def _render_summary(self, fact):
        val = fact.state["value"]
        if not isinstance(val, dict):
            return
        passed = val.get("passed", 0)
        failed = val.get("failed", 0)
        total = val.get("total", 0)
        status = "PASS" if failed == 0 else "FAIL"
        status_color = Config.COLOR_GREEN if failed == 0 else Config.COLOR_RED
        line = "Summary: %s  passed=%d  failed=%d  total=%d" % (
            self._color(status_color, status), passed, failed, total
        )
        self._emit(self._color(Config.COLOR_BOLD, line))
        bar_total = 30
        if total > 0:
            bar_pass = (passed * bar_total) // total
            bar_fail = bar_total - bar_pass
        else:
            bar_pass = 0
            bar_fail = 0
        bar = self._color(Config.COLOR_GREEN, "#" * bar_pass) + self._color(Config.COLOR_RED, "#" * bar_fail)
        self._emit("[" + bar + "]")

    # ─── helpers ────────────────────────────────────────────────────────────

    def _emit(self, line):
        self.state["lines"].append(line)

    def _color(self, code, text):
        if not self.state["use_color"] or not Config.USE_COLOR:
            return text
        return code + text + Config.COLOR_RESET

    def _format_value(self, value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            if isinstance(value, float) and abs(value) < 1:
                return "%.4f" % value
            return str(value)
        return str(value)
