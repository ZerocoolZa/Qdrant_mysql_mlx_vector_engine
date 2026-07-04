#!/usr/bin/env python3
# [@GHOST]{[@file<CodeGraph.py>][@domain<code>][@role<audit_graph>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<audit_graph>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{CodeGraph — VBStyle compliance audit. Scans Python source, checks every VBStyle rule, generates visual graph. Same questions for every file. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{CodeGraph}
# [@METHOD]{Run,audit,graph,report,questions,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<VBStyle compliance audit tool. Scans Python source, checks all VBStyle rules, generates visual graph. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded AUDIT_QUESTIONS list with patterns. Uses ast module for parsing.>][@todos<Move audit question patterns to Config.py or external config>]}
"""
CodeGraph — VBStyle code compliance audit.

WHAT IT DOES:
  - Scans a Python source file (or directory)
  - Checks every VBStyle rule
  - Generates a visual graph (like GuiGraph but for code)
  - Asks the same questions for every file
  - Reports what's compliant vs violating

THE VBSTYLE QUESTIONS:
  Headers:   Ghost header? VBStyle header? Class header? Method header?
  Structure: Run() dispatch? __init__ signature? self.state dict? read_state? set_config?
  Returns:   Tuple3 returns? error tuple format?
  Forbidden: print()? @property? @staticmethod? @classmethod? self._? tabs? hardcoded? enums?
  Required:  PascalCase classes? UPPERCASE constants? _p helper? one class per file?

USAGE:
  from CodeGraph import CodeGraph

  cg = CodeGraph()
  ok, data, err = cg.Run("audit", {"path": "VoiceEngine.py"})
  ok, data, err = cg.Run("graph")    # → visual graph string
  ok, data, err = cg.Run("report")   # → detailed text report
  ok, data, err = cg.Run("questions")  # → list of all questions

  # Audit multiple files:
  ok, data, err = cg.Run("audit", {"path": "."})  # scans all .py in directory
"""

import re
import os
import ast


# ════════════════════════════════════════════
# AUDIT QUESTIONS — The VBStyle Checklist
# ════════════════════════════════════════════

# Each question: (category, id, label, check_type, pattern_or_check)
# check_type: "forbidden" = must NOT find, "required" = MUST find, "count" = count occurrences

AUDIT_QUESTIONS = [
    # Headers
    ("header", "ghost_header",     "Ghost header",        "required",  r"#\s*\[@GHOST\]"),
    ("header", "vbsty_header",     "VBStyle header",      "required",  r"#\s*\[@VBSTYLE\]"),
    ("header", "class_header",     "Class header",        "required",  r"#\s*\[@CLASS\]"),
    ("header", "method_header",    "Method header",       "required",  r"#\s*\[@METHOD\]"),
    ("header", "summary_header",   "Summary header",      "required",  r"#\s*\[@SUMMARY\]"),
    # Structure
    ("structure", "run_dispatch",     "Run() dispatch",        "required",  r"def Run\(self"),
    ("structure", "init_signature",   "__init__(mem,db,param)", "required",  r"def __init__\(self,\s*mem\s*=\s*None,\s*db\s*=\s*None,\s*param\s*=\s*None\)"),
    ("structure", "state_dict",       "self.state dict",       "required",  r"self\.state\s*=\s*\{"),
    ("structure", "read_state",       "read_state method",     "required",  r"def read_state\(self"),
    ("structure", "set_config",       "set_config method",     "required",  r"def set_config\(self"),
    ("structure", "p_helper",         "_p helper",             "required",  r"def p\(self,\s*params"),
    ("structure", "dispatch_dict",    "Dispatch dictionary",   "required",  r"dispatch\s*=\s*\{"),
    ("structure", "one_class",        "One class per file",    "required",  r"^class\s+\w+"),
    # Returns
    ("returns", "tuple3_success",  "Tuple3 success (1,data,None)", "required", r"return\s*\(1,"),
    ("returns", "tuple3_error",    "Tuple3 error (0,None,err)",   "required", r"return\s*\(0,\s*None,"),
    ("returns", "error_format",    "Error tuple (code,desc,0)",   "required", r"\(\"ERR_"),
    # Forbidden
    ("forbidden", "no_print",        "No print()",           "forbidden", r"\bprint\s*\("),
    ("forbidden", "no_property",     "No @property",         "forbidden", r"@property"),
    ("forbidden", "no_staticmethod", "No @staticmethod",     "forbidden", r"@staticmethod"),
    ("forbidden", "no_classmethod",  "No @classmethod",      "forbidden", r"@classmethod"),
    ("forbidden", "no_self_underscore", "No self._",         "forbidden", r"self\._"),
    ("forbidden", "no_tabs",         "No tabs",              "forbidden", r"\t"),
    ("forbidden", "no_hardcoded",    "No hardcoded strings", "forbidden", r"(?<![#\w])\"(localhost|127\.0\.0\.1|root|password|3306|8080|admin|secret)\""),
    ("forbidden", "no_enum",         "No enums",             "forbidden", r"\bEnum\b|\bIntEnum\b|\bauto\(\)"),
    ("forbidden", "no_trailing_ws",  "No trailing whitespace", "forbidden", r" +$"),
    # Required style
    ("style", "pascal_case",     "PascalCase classes",       "required",  r"class\s+[A-Z][a-zA-Z0-9]*\b"),
    ("style", "uppercase_const", "UPPERCASE constants",      "required",  r"^[A-Z][A-Z0-9_]+\s*="),
    ("style", "spaces_only",     "Spaces (no tabs)",         "required",  r"^    \S"),
    # Error handling
    ("errors", "crash_on_err",   "Crash on error (if not ok)", "required", r"if\s+not\s+ok"),
    ("errors", "no_bare_except", "No bare except",            "forbidden", r"except\s*:"),
    ("errors", "no_silent_err",  "No silent continue",        "forbidden", r"except\s+Exception\s*:\s*\n\s*pass"),
]


class CodeGraph:
    """
    VBStyle code compliance audit.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Asks the same questions for every code file.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "target": param.get("target", "") if param else "",
            },
            "files": {},  # path → results
            "results": {},  # aggregated results (single file mode)
            "source": "",
            "source_path": "",
            "total_checks": 0,
            "total_pass": 0,
            "total_fail": 0,
            "score": 0,
            "mode": "single",  # single or directory
        }

    def Run(self, command, params=None):
        dispatch = {
            "audit": self.cmd_audit,
            "graph": self.cmd_graph,
            "report": self.cmd_report,
            "questions": self.cmd_questions,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # INTERNAL — audit a single file
    # ════════════════════════════════════════════

    def auditFile(self, path):
        try:
            with open(path, "r") as f:
                src = f.read()
        except Exception as e:
            return None, str(e)

        results = {}
        totalChecks = 0
        totalPass = 0
        totalFail = 0

        for category, itemId, label, checkType, pattern in AUDIT_QUESTIONS:
            try:
                matches = re.findall(pattern, src, re.MULTILINE)
            except Exception:
                matches = []
            count = len(matches)

            if checkType == "forbidden":
                found = count == 0
                status = "PASS" if found else "FAIL"
            elif checkType == "required":
                found = count > 0
                status = "PASS" if found else "FAIL"
            else:
                found = count > 0
                status = "PASS" if found else "FAIL"

            results[itemId] = {
                "category": category,
                "label": label,
                "check_type": checkType,
                "found": found,
                "count": count,
                "status": status,
            }
            totalChecks += 1
            if found:
                totalPass += 1
            else:
                totalFail += 1

        score = int((totalPass / totalChecks * 100) if totalChecks > 0 else 0)
        return {
            "results": results,
            "total_checks": totalChecks,
            "total_pass": totalPass,
            "total_fail": totalFail,
            "score": score,
            "source": src,
        }, None

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_audit(self, params):
        path = self.p(params, "path", self.state["config"]["target"])
        if not path or not os.path.exists(path):
            return (0, None, ("ERR_PARAMS", "path required or not found: %s" % path, 0))

        if os.path.isdir(path):
            # Directory mode — audit all .py files
            self.state["mode"] = "directory"
            allFiles = {}
            for fname in sorted(os.listdir(path)):
                if fname.endswith(".py") and not fname.startswith("__"):
                    fpath = os.path.join(path, fname)
                    auditResult, err = self.auditFile(fpath)
                    if auditResult:
                        allFiles[fname] = auditResult
            self.state["files"] = allFiles

            # Aggregate
            totalChecks = 0
            totalPass = 0
            totalFail = 0
            for fname, data in allFiles.items():
                totalChecks += data["total_checks"]
                totalPass += data["total_pass"]
                totalFail += data["total_fail"]
            self.state["total_checks"] = totalChecks
            self.state["total_pass"] = totalPass
            self.state["total_fail"] = totalFail
            self.state["score"] = int((totalPass / totalChecks * 100) if totalChecks > 0 else 0)
            self.state["source_path"] = path + " (directory, %d files)" % len(allFiles)
            return (1, {
                "mode": "directory",
                "files": len(allFiles),
                "score": self.state["score"],
                "pass": totalPass,
                "fail": totalFail,
                "total": totalChecks,
            }, None)
        else:
            # Single file mode
            self.state["mode"] = "single"
            auditResult, err = self.auditFile(path)
            if err:
                return (0, None, ("ERR_AUDIT", err, 0))
            self.state["results"] = auditResult["results"]
            self.state["total_checks"] = auditResult["total_checks"]
            self.state["total_pass"] = auditResult["total_pass"]
            self.state["total_fail"] = auditResult["total_fail"]
            self.state["score"] = auditResult["score"]
            self.state["source"] = auditResult["source"]
            self.state["source_path"] = path
            return (1, {
                "mode": "single",
                "score": self.state["score"],
                "pass": self.state["total_pass"],
                "fail": self.state["total_fail"],
                "total": self.state["total_checks"],
            }, None)

    def cmd_graph(self, params):
        if self.state["mode"] == "directory" and self.state["files"]:
            return self.graphDirectory()
        return self.graphSingle()

    def graphSingle(self):
        results = self.state["results"]
        if not results:
            return (0, None, ("ERR_NO_AUDIT", "run audit first", 0))

        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║           CODE GRAPH — VBStyle Compliance Audit             ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        lines.append("  File: %s" % self.state["source_path"])
        lines.append("  Score: %d%%  (%d/%d checks passed)" % (
            self.state["score"], self.state["total_pass"], self.state["total_checks"]))
        lines.append("")

        categoryLabels = {
            "header": "HEADERS",
            "structure": "STRUCTURE",
            "returns": "RETURNS (Tuple3)",
            "forbidden": "FORBIDDEN",
            "style": "STYLE",
            "errors": "ERROR HANDLING",
        }

        for category in ["header", "structure", "returns", "forbidden", "style", "errors"]:
            catItems = {k: v for k, v in results.items() if v["category"] == category}
            if not catItems:
                continue
            catPass = sum(1 for v in catItems.values() if v["found"])
            catTotal = len(catItems)
            catScore = int((catPass / catTotal * 100) if catTotal > 0 else 0)

            lines.append("  ┌─ %s ─%s─┐" % (categoryLabels.get(category, category.upper()), "─" * max(0, 30 - len(categoryLabels.get(category, category.upper())))))
            lines.append("  │  Score: %d%%  (%d/%d)" % (catScore, catPass, catTotal))
            lines.append("  │")

            for itemId, info in catItems.items():
                found = info["found"]
                count = info["count"]
                label = info["label"]
                checkType = info["check_type"]
                if found:
                    if checkType == "forbidden":
                        status = "✅ NONE"
                        detail = "(0 found — good)"
                    else:
                        status = "✅ FOUND"
                        detail = "(%d refs)" % count
                else:
                    if checkType == "forbidden":
                        status = "❌ FOUND"
                        detail = "(%d violations!)" % count
                    else:
                        status = "❌ MISSING"
                        detail = "(0 refs)"
                lines.append("  │  %s  %-30s  %s" % (status, label, detail))

            lines.append("  └%s┘" % ("─" * 62))
            lines.append("")

        score = self.state["score"]
        barLen = 30
        filled = int(score / 100 * barLen)
        bar = "█" * filled + "░" * (barLen - filled)
        lines.append("  ┌─ VBSTYLE SCORE ────────────────────────────────────────────┐")
        lines.append("  │  [%s] %d%%" % (bar, score))
        if score == 100:
            lines.append("  │  🏆 FULLY VBSTYLE COMPLIANT — every rule passes")
        elif score >= 90:
            lines.append("  │  ✅ Nearly perfect — minor violations")
        elif score >= 75:
            lines.append("  │  ⚠️  Mostly compliant — some rules broken")
        elif score >= 50:
            lines.append("  │  🔧 Needs work — multiple violations")
        else:
            lines.append("  │  ❌ Not VBStyle compliant — major rework needed")
        lines.append("  └────────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)

    def graphDirectory(self):
        files = self.state["files"]
        if not files:
            return (0, None, ("ERR_NO_AUDIT", "run audit first", 0))

        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║        CODE GRAPH — VBStyle Directory Audit (%d files)       ║" % len(files))
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        lines.append("  Directory: %s" % self.state["source_path"])
        lines.append("  Total Score: %d%%  (%d/%d checks passed across all files)" % (
            self.state["score"], self.state["total_pass"], self.state["total_checks"]))
        lines.append("")
        lines.append("  %-30s  %6s  %6s  %6s  %6s  %s" % ("File", "Score", "Pass", "Fail", "Total", "Bar"))
        lines.append("  " + "-" * 80)

        for fname, data in sorted(files.items()):
            score = data["score"]
            passes = data["total_pass"]
            fails = data["total_fail"]
            total = data["total_checks"]
            barLen = 20
            filled = int(score / 100 * barLen)
            bar = "█" * filled + "░" * (barLen - filled)
            icon = "🏆" if score == 100 else ("✅" if score >= 90 else ("⚠️" if score >= 75 else "❌"))
            lines.append("  %-30s  %5d%%  %6d  %6d  %6d  %s %s" % (
                fname, score, passes, fails, total, bar, icon))

        lines.append("")
        # Overall bar
        score = self.state["score"]
        barLen = 30
        filled = int(score / 100 * barLen)
        bar = "█" * filled + "░" * (barLen - filled)
        lines.append("  ┌─ DIRECTORY VBSTYLE SCORE ──────────────────────────────────┐")
        lines.append("  │  [%s] %d%%" % (bar, score))
        perfect = sum(1 for f in files.values() if f["score"] == 100)
        lines.append("  │  Perfect files: %d/%d" % (perfect, len(files)))
        lines.append("  └────────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)

    def cmd_report(self, params):
        if self.state["mode"] == "directory" and self.state["files"]:
            return self.reportDirectory()
        return self.reportSingle()

    def reportSingle(self):
        results = self.state["results"]
        if not results:
            return (0, None, ("ERR_NO_AUDIT", "run audit first", 0))

        lines = []
        lines.append("VBSTYLE AUDIT REPORT")
        lines.append("====================")
        lines.append("File: %s" % self.state["source_path"])
        lines.append("Score: %d%% (%d/%d)" % (
            self.state["score"], self.state["total_pass"], self.state["total_checks"]))
        lines.append("")

        lines.append("VIOLATIONS:")
        lines.append("-" * 40)
        violationCount = 0
        for itemId, info in results.items():
            if not info["found"]:
                lines.append("  [%s] %s — %s" % (
                    info["category"], info["label"],
                    "%d found" % info["count"] if info["check_type"] == "forbidden" else "MISSING"))
                violationCount += 1
        if violationCount == 0:
            lines.append("  (none — all checks passed!)")
        lines.append("")
        lines.append("COMPLIANT:")
        lines.append("-" * 40)
        passCount = 0
        for itemId, info in results.items():
            if info["found"]:
                lines.append("  [%s] %s (%d refs)" % (info["category"], info["label"], info["count"]))
                passCount += 1
        lines.append("")
        lines.append("SUMMARY: %d passed, %d violations, %d total" % (
            passCount, violationCount, passCount + violationCount))

        report = "\n".join(lines)
        return (1, report, None)

    def reportDirectory(self):
        files = self.state["files"]
        lines = []
        lines.append("VBSTYLE DIRECTORY AUDIT REPORT")
        lines.append("===============================")
        lines.append("Directory: %s" % self.state["source_path"])
        lines.append("Overall Score: %d%% (%d/%d)" % (
            self.state["score"], self.state["total_pass"], self.state["total_checks"]))
        lines.append("")
        lines.append("PER-FILE BREAKDOWN:")
        lines.append("-" * 60)
        for fname, data in sorted(files.items()):
            lines.append("  %s: %d%% (%d pass, %d fail)" % (
                fname, data["score"], data["total_pass"], data["total_fail"]))
            for itemId, info in data["results"].items():
                if not info["found"]:
                    lines.append("    ❌ [%s] %s" % (info["category"], info["label"]))
        lines.append("")
        perfect = sum(1 for f in files.values() if f["score"] == 100)
        lines.append("Perfect files: %d/%d" % (perfect, len(files)))

        report = "\n".join(lines)
        return (1, report, None)

    def cmd_questions(self, params):
        lines = []
        lines.append("VBSTYLE QUESTIONS — Asked for every code file")
        lines.append("==============================================")
        lines.append("")
        currentCat = ""
        for category, itemId, label, checkType, pattern in AUDIT_QUESTIONS:
            if category != currentCat:
                currentCat = category
                catLabel = {
                    "header": "HEADERS",
                    "structure": "STRUCTURE",
                    "returns": "RETURNS (Tuple3)",
                    "forbidden": "FORBIDDEN",
                    "style": "STYLE",
                    "errors": "ERROR HANDLING",
                }.get(category, category.upper())
                lines.append("")
                lines.append("%s:" % catLabel)
                lines.append("-" * 40)
            checkWord = "must NOT have" if checkType == "forbidden" else "must have"
            lines.append("  ? %s  (%s)" % (label, checkWord))
        lines.append("")
        lines.append("Total questions: %d" % len(AUDIT_QUESTIONS))

        questions = "\n".join(lines)
        return (1, questions, None)
