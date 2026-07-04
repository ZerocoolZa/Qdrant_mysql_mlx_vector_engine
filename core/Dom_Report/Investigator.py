#!/usr/bin/env python3
# [@GHOST]{[@file<Investigator.py>][@domain<Dom_Report>][@role<investigator>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<investigator>][@return<tuple3>][@orch<VbsMain>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Investigator — Layer 2. Reads a finalized report, runs the 6-category diagnostic protocol. Answers what it can from the report, marks the rest as pending (knowledge base lookup). Does NOT modify the report.}
# [@CLASS]{Investigator}
# [@METHOD]{Run,Investigate,InvestigateIdentity,InvestigateOutcome,InvestigateCause,InvestigateHistory,InvestigateRepair,InvestigatePrevention,RenderDiagnosis,read_state,set_config}
# [@FILEID]{core/Dom_Report/Investigator.py

from . import Config


class Investigator:
    """Layer 2 — the detective.

    Reads a finalized report (the case file) and runs the diagnostic protocol:
    6 categories of stable questions. Answers what it can from the report.
    Marks the rest as pending (knowledge base lookup, later).

    The investigator NEVER modifies the report. It reads it like a detective
    reads a case file — with respect, without changing it.

    self.state:
        state['diagnosis']:   dict of category → dict of question → (status, answer)
        state['report_state']: snapshot of the report's read_state at investigation time
        state['facts_count']:  number of facts in the report
        state['investigated']: whether Investigate has been run
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "diagnosis": {},
            "report_state": None,
            "facts_count": 0,
            "investigated": False,
        }
        if param:
            self.set_config(param)

    def Run(self, command, params=None):
        dispatch = {
            "investigate": self.Investigate,
            "render_diagnosis": self.RenderDiagnosis,
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

    def Investigate(self, params):
        report = self._p(params, "report")
        kb = self._p(params, "knowledge_base")
        if report is None:
            return (0, None, ("ERR_REPORT", "report required", 0))
        ok, rstate, _ = report.Run("read_state", {})
        if not ok:
            return (ok, None, _)
        ok, facts, _ = report.Run("get_facts", {})
        if not ok:
            return (ok, None, _)
        self.state["report_state"] = rstate
        self.state["facts_count"] = len(facts)
        self.state["diagnosis"] = {}
        self._investigate_identity(rstate, facts)
        self._investigate_outcome(rstate, facts)
        self._investigate_cause(rstate, facts)
        self._investigate_history(rstate, facts)
        self._investigate_repair(rstate, facts)
        self._investigate_prevention(rstate, facts)
        if kb is not None:
            ok_kb, enriched, err_kb = kb.Run("lookup", {
                "diagnosis": dict(self.state["diagnosis"]),
                "operation": rstate.get("operation", ""),
                "reason": rstate.get("reason", ""),
            })
            if ok_kb:
                self.state["diagnosis"] = enriched
        self.state["investigated"] = True
        return (1, dict(self.state["diagnosis"]), None)

    def _answer(self, category, question, status, answer):
        if category not in self.state["diagnosis"]:
            self.state["diagnosis"][category] = {}
        self.state["diagnosis"][category][question] = {"status": status, "answer": answer}

    def _investigate_identity(self, rstate, facts):
        self._answer(Config.CATEGORY_IDENTITY, "what_happened", Config.ANSWER_KNOWN, rstate["operation"])
        source = rstate.get("source", "")
        self._answer(Config.CATEGORY_IDENTITY, "where", Config.ANSWER_KNOWN if source else Config.ANSWER_UNKNOWN, source if source else "not recorded")
        self._answer(Config.CATEGORY_IDENTITY, "who", Config.ANSWER_KNOWN if source else Config.ANSWER_UNKNOWN, source if source else "not recorded")

    def _investigate_outcome(self, rstate, facts):
        result = rstate.get("result", "")
        is_ok = result == "ok"
        self._answer(Config.CATEGORY_OUTCOME, "did_pass", Config.ANSWER_KNOWN, "yes" if is_ok else "no")
        self._answer(Config.CATEGORY_OUTCOME, "did_fail", Config.ANSWER_KNOWN, "no" if is_ok else "yes")
        outputs = [f for f in facts if f.state["kind"] == Config.KIND_OUTPUT]
        if outputs:
            output_summary = ", ".join("%s=%s" % (f.state["name"], f.state["value"]) for f in outputs)
            self._answer(Config.CATEGORY_OUTCOME, "what_produced", Config.ANSWER_KNOWN, output_summary)
        else:
            self._answer(Config.CATEGORY_OUTCOME, "what_produced", Config.ANSWER_KNOWN, "nothing")

    def _investigate_cause(self, rstate, facts):
        result = rstate.get("result", "")
        reason = rstate.get("reason", "")
        if result == "ok":
            self._answer(Config.CATEGORY_CAUSE, "why", Config.ANSWER_NOT_APPLICABLE, "operation succeeded")
            self._answer(Config.CATEGORY_CAUSE, "root_cause", Config.ANSWER_NOT_APPLICABLE, "operation succeeded")
            self._answer(Config.CATEGORY_CAUSE, "was_expected", Config.ANSWER_NOT_APPLICABLE, "n/a — success")
        else:
            self._answer(Config.CATEGORY_CAUSE, "why", Config.ANSWER_KNOWN if reason else Config.ANSWER_UNKNOWN, reason if reason else "no reason recorded")
            self._answer(Config.CATEGORY_CAUSE, "root_cause", Config.ANSWER_PENDING, "needs knowledge base lookup")
            issues = [f for f in facts if f.state["kind"] == Config.KIND_ISSUE]
            if issues:
                self._answer(Config.CATEGORY_CAUSE, "was_expected", Config.ANSWER_UNKNOWN, "unknown — %d issue(s) recorded" % len(issues))
            else:
                self._answer(Config.CATEGORY_CAUSE, "was_expected", Config.ANSWER_UNKNOWN, "unknown — no issues recorded")

    def _investigate_history(self, rstate, facts):
        self._answer(Config.CATEGORY_HISTORY, "seen_before", Config.ANSWER_PENDING, "needs knowledge base lookup")
        self._answer(Config.CATEGORY_HISTORY, "known_problem", Config.ANSWER_PENDING, "needs knowledge base lookup")
        self._answer(Config.CATEGORY_HISTORY, "is_new", Config.ANSWER_PENDING, "needs knowledge base lookup")

    def _investigate_repair(self, rstate, facts):
        result = rstate.get("result", "")
        if result == "ok":
            self._answer(Config.CATEGORY_REPAIR, "is_fixable", Config.ANSWER_NOT_APPLICABLE, "n/a — operation succeeded")
            self._answer(Config.CATEGORY_REPAIR, "known_fix", Config.ANSWER_NOT_APPLICABLE, "n/a — operation succeeded")
            self._answer(Config.CATEGORY_REPAIR, "which_fix_worked", Config.ANSWER_NOT_APPLICABLE, "n/a — operation succeeded")
            self._answer(Config.CATEGORY_REPAIR, "can_auto_apply", Config.ANSWER_NOT_APPLICABLE, "n/a — operation succeeded")
        else:
            recs = [f for f in facts if f.state["kind"] == Config.KIND_RECOMMENDATION]
            if recs:
                rec_text = "; ".join(f.state["value"] for f in recs)
                self._answer(Config.CATEGORY_REPAIR, "is_fixable", Config.ANSWER_KNOWN, "yes — recommendation emitted")
                self._answer(Config.CATEGORY_REPAIR, "known_fix", Config.ANSWER_KNOWN, rec_text)
            else:
                self._answer(Config.CATEGORY_REPAIR, "is_fixable", Config.ANSWER_PENDING, "needs knowledge base lookup")
                self._answer(Config.CATEGORY_REPAIR, "known_fix", Config.ANSWER_PENDING, "needs knowledge base lookup")
            self._answer(Config.CATEGORY_REPAIR, "which_fix_worked", Config.ANSWER_PENDING, "needs knowledge base lookup")
            self._answer(Config.CATEGORY_REPAIR, "can_auto_apply", Config.ANSWER_PENDING, "needs knowledge base lookup")

    def _investigate_prevention(self, rstate, facts):
        result = rstate.get("result", "")
        if result == "ok":
            self._answer(Config.CATEGORY_PREVENTION, "how_prevent", Config.ANSWER_NOT_APPLICABLE, "n/a — operation succeeded")
            self._answer(Config.CATEGORY_PREVENTION, "missing_guard", Config.ANSWER_NOT_APPLICABLE, "n/a — operation succeeded")
            self._answer(Config.CATEGORY_PREVENTION, "detect_earlier", Config.ANSWER_NOT_APPLICABLE, "n/a — operation succeeded")
        else:
            self._answer(Config.CATEGORY_PREVENTION, "how_prevent", Config.ANSWER_PENDING, "needs knowledge base + analysis")
            self._answer(Config.CATEGORY_PREVENTION, "missing_guard", Config.ANSWER_PENDING, "needs knowledge base + analysis")
            self._answer(Config.CATEGORY_PREVENTION, "detect_earlier", Config.ANSWER_PENDING, "needs knowledge base + analysis")

    def RenderDiagnosis(self, params=None):
        use_color = self._p(params, "use_color", True)
        if not self.state["investigated"]:
            return (0, None, ("ERR_NOT_INVESTIGATED", "call Investigate first", 0))
        lines = []
        rstate = self.state["report_state"]
        operation = rstate.get("operation", "Unknown")
        result = rstate.get("result", "unknown")
        result_label = {"ok": "PASS", "fail": "FAIL", "partial": "PARTIAL"}.get(result, result.upper())
        lines.append(self._color(use_color, Config.COLOR_BOLD, "Investigation: %s" % operation))
        lines.append(self._color(use_color, Config.COLOR_DIM, "=" * min(len("Investigation: " + operation), Config.TERMINAL_WIDTH)))
        lines.append("")
        for category in Config.DIAGNOSTIC_CATEGORIES:
            questions = Config.DIAGNOSTIC_QUESTIONS.get(category, ())
            answers = self.state["diagnosis"].get(category, {})
            if not answers:
                continue
            lines.append(self._color(use_color, Config.COLOR_BOLD, category.title()))
            for q in questions:
                a = answers.get(q, {"status": Config.ANSWER_UNKNOWN, "answer": ""})
                status = a["status"]
                symbol = self._status_symbol(status)
                color = self._status_color(status)
                line = "  %s %s: %s" % (
                    self._color(use_color, color, symbol),
                    q,
                    a["answer"],
                )
                lines.append(line)
            lines.append("")
        return (1, "\n".join(lines), None)

    def _status_symbol(self, status):
        return {
            Config.ANSWER_KNOWN: "✓",
            Config.ANSWER_UNKNOWN: "?",
            Config.ANSWER_PENDING: "⏳",
            Config.ANSWER_NOT_APPLICABLE: "—",
        }.get(status, "?")

    def _status_color(self, status):
        return {
            Config.ANSWER_KNOWN: Config.COLOR_GREEN,
            Config.ANSWER_UNKNOWN: Config.COLOR_YELLOW,
            Config.ANSWER_PENDING: Config.COLOR_CYAN,
            Config.ANSWER_NOT_APPLICABLE: Config.COLOR_DIM,
        }.get(status, Config.COLOR_YELLOW)

    def _color(self, use_color, code, text):
        if not use_color or not Config.USE_COLOR:
            return text
        return code + text + Config.COLOR_RESET
