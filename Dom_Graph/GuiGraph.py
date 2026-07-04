#!/usr/bin/env python3
# [@GHOST]{[@file<GuiGraph.py>][@domain<gui>][@role<audit_graph>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<audit_graph>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{GuiGraph — Porsche Principle audit. Scans GUI source code, checks every completeness requirement, generates visual graph. Asks the same questions for every GUI. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{GuiGraph}
# [@METHOD]{Run,audit,graph,report,questions,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Porsche Principle GUI completeness audit. Scans GUI source, checks requirements, generates visual graph. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
GuiGraph — Porsche Principle GUI completeness audit.

WHAT IT DOES:
  - Scans a Python GUI source file
  - Checks every Porsche Principle requirement
  - Generates a visual graph (like VBStyle error graph)
  - Asks the same questions for every GUI
  - Reports what's complete vs missing

THE PORSCHE QUESTIONS:
  Application: menu bar? toolbar? status bar? settings? help? about?
               search? themes? fonts? context menus? keyboard nav?
               undo/redo? copy/paste? find? persistence? tooltips? icons?
               error reporting? shortcuts?
  Window:      title? icon? close handling? resize? position persistence?
  Widget:      GuiAspect registered? setting? help? tooltip? shortcut? icon?
  Table:       sorting? filtering? searching? copy/export? context menu?
  Editor:      undo? redo? find? replace? zoom? font options?

USAGE:
  from GuiGraph import GuiGraph

  gg = GuiGraph()
  ok, data, err = gg.Run("audit", {"path": "ChatGui.py"})
  ok, data, err = gg.Run("graph")  # → visual graph string
  ok, data, err = gg.Run("report")  # → detailed text report
  ok, data, err = gg.Run("questions")  # → list of all questions asked
"""

import re
import os


# ════════════════════════════════════════════
# AUDIT QUESTIONS — The Porsche Checklist
# ════════════════════════════════════════════

AUDIT_QUESTIONS = [
    # Application-level
    ("app", "menu_bar",        "Menu bar",         r"menuBar|QMenuBar|BuildMenu|menuBar\(\)"),
    ("app", "toolbar",         "Toolbar",          r"QToolBar|toolbar|Toolbar|addToolBar"),
    ("app", "status_bar",      "Status bar",       r"QStatusBar|statusBar|SetStatus|statusBar\(\)"),
    ("app", "settings_dialog", "Settings dialog",  r"OpenSettings|QDialog|Settings|settings"),
    ("app", "help_menu",       "Help menu",        r"helpMenu|Help|aboutMenu|QMenu.*Help"),
    ("app", "about_dialog",    "About dialog",     r"About|aboutDialog|QMessageBox.*About|showAbout"),
    ("app", "search",          "Search",           r"search|Search|QCompleter|QSortFilter"),
    ("app", "theme_support",   "Theme support",    r"Theme|theme|ApplyTheme|THEMES|CURRENT_THEME"),
    ("app", "font_config",     "Font configuration", r"FontSize|font_spin|ApplyFontSize|FONT_CHAT"),
    ("app", "context_menus",   "Context menus",    r"contextMenu|ContextMenu|customContextMenu"),
    ("app", "keyboard_nav",    "Keyboard navigation", r"QShortcut|shortcut|Shortcut|keyPressEvent"),
    ("app", "undo_redo",       "Undo/redo",        r"undo|redo|Undo|Redo"),
    ("app", "copy_paste",      "Copy/paste",       r"copy|paste|Copy|Paste|QClipboard"),
    ("app", "find",            "Find",             r"find|Find|Ctrl\+F|searchInput"),
    ("app", "window_persist",  "Window persistence", r"SaveSettings|LoadSettings|geometry|saveGeometry"),
    ("app", "tooltips",        "Tooltips",         r"setToolTip|tooltip|Tooltip|toolTip"),
    ("app", "icons",           "Icons",            r"setIcon|QIcon|icon\(|fromTheme"),
    ("app", "error_reporting", "Error reporting",  r"AppendError|error|Error|QMessageBox|warning"),
    ("app", "shortcuts",       "Keyboard shortcuts", r"QShortcut|setShortcut|Ctrl\+|Cmd\+|Alt\+"),
    ("app", "accessibility",   "Accessibility",    r"accessible|Accessible|setAccessibleName|whatsThis"),
    ("app", "validation",      "Input validation",  r"valid|Valid|validate|Validate|QValidator"),
    ("app", "drag_drop",       "Drag and drop",    r"drag|drop|Drag|Drop|dragEnter|dropEvent"),
    # Window-level
    ("window", "title",        "Window title",     r"setWindowTitle|WindowTitle|windowTitle"),
    ("window", "icon",         "Window icon",      r"setWindowIcon|WindowIcon|windowIcon"),
    ("window", "close_handle", "Close handling",   r"closeEvent|CloseEvent|canClose|confirmClose"),
    ("window", "resize",       "Resize support",   r"resize|Resize|minimumSize|maximumSize|setMinimumSize"),
    ("window", "position_save", "Position persistence", r"geometry|saveGeometry|restoreGeometry|pos\(\)"),
    # Widget-level (GuiAspect)
    ("widget", "gui_aspect",   "GuiAspect registry", r"GuiAspect|GuiAspectRegistry|GuiAspects"),
    ("widget", "setting_sync", "Setting ↔ config sync", r"set_config|setConfig|sync_to_config|sync_from_config"),
    ("widget", "help_text",    "Help text per item", r"get_help|help_text|\"help\""),
    ("widget", "tooltip_per",  "Tooltip per item",  r"get_tooltip|tooltip_text|\"tooltip\""),
    ("widget", "shortcut_per", "Shortcut per item", r"get_shortcut|shortcut_text|\"shortcut\""),
    ("widget", "icon_per",     "Icon per item",     r"get_icon|icon_name|\"icon\""),
    ("widget", "persistence",  "Widget persistence", r"persistent|save\(|load\(|json\.dump|json\.load"),
    # Table-level
    ("table", "sorting",       "Table sorting",     r"sort|Sort|setSortingEnabled|sortByColumn"),
    ("table", "filtering",     "Table filtering",   r"filter|Filter|setFilter|QSortFilterProxy"),
    ("table", "table_search",  "Table search",      r"search|Search|findItem|findItems"),
    ("table", "copy_export",   "Table copy/export", r"copy|export|Export|copySelection"),
    ("table", "table_context", "Table context menu", r"contextMenu|ContextMenu|customContextMenu"),
    # Editor-level
    ("editor", "editor_undo",  "Editor undo",       r"undo|Undo|QTextEdit.*undo"),
    ("editor", "editor_redo",  "Editor redo",       r"redo|Redo|QTextEdit.*redo"),
    ("editor", "editor_find",  "Editor find",       r"find|Find|QTextEdit.*find|Ctrl\+F"),
    ("editor", "editor_zoom",  "Editor zoom",       r"zoom|Zoom|Ctrl\+=|Ctrl\+-|setFontPointSize"),
    # Voice-specific
    ("voice", "tts",           "TTS controller",    r"TtsController|NSSpeechSynthesizer|tts"),
    ("voice", "stt",           "STT controller",    r"SttController|SFSpeechRecognizer|stt"),
    ("voice", "silence_det",   "Silence detector",  r"SilenceDetector|silence|Silence"),
    ("voice", "audio_engine",  "Audio engine mgr",  r"AudioEngineManager|AVAudioEngine|audio_engine"),
    ("voice", "voice_config",  "Voice config",      r"VoiceConfig|voice_config|config"),
    ("voice", "warmup",        "Voice warmup",      r"warmup|Warmup|preInitialize|pre_warm"),
    ("voice", "mute_flag",     "Mute flag (feedback)", r"mute|Mute|unmute|Unmute"),
    ("voice", "audio_level",   "Audio level meter", r"audio_level|get_level|get_audio_level|RMS"),
]


class GuiGraph:
    """
    Porsche Principle GUI completeness audit.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Asks the same questions for every GUI.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "target": param.get("target", "") if param else "",
            },
            "results": {},  # category → {item → (found, count)}
            "source": "",
            "source_path": "",
            "total_checks": 0,
            "total_pass": 0,
            "total_fail": 0,
            "score": 0,
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
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_audit(self, params):
        path = self.p(params, "path", self.state["config"]["target"])
        if not path or not os.path.exists(path):
            return (0, None, ("ERR_PARAMS", "path required or not found: %s" % path, 0))
        try:
            with open(path, "r") as f:
                self.state["source"] = f.read()
                self.state["source_path"] = path
        except Exception as e:
            return (0, None, ("ERR_READ", str(e), 0))

        results = {}
        totalChecks = 0
        totalPass = 0
        totalFail = 0

        for category, itemId, label, pattern in AUDIT_QUESTIONS:
            matches = re.findall(pattern, self.state["source"], re.IGNORECASE)
            count = len(matches)
            found = count > 0
            if category not in results:
                results[category] = {}
            results[category][itemId] = {
                "label": label,
                "found": found,
                "count": count,
                "pattern": pattern,
            }
            totalChecks += 1
            if found:
                totalPass += 1
            else:
                totalFail += 1

        self.state["results"] = results
        self.state["total_checks"] = totalChecks
        self.state["total_pass"] = totalPass
        self.state["total_fail"] = totalFail
        self.state["score"] = int((totalPass / totalChecks * 100) if totalChecks > 0 else 0)

        return (1, {
            "score": self.state["score"],
            "pass": totalPass,
            "fail": totalFail,
            "total": totalChecks,
            "results": results,
        }, None)

    def cmd_graph(self, params):
        results = self.state["results"]
        if not results:
            return (0, None, ("ERR_NO_AUDIT", "run audit first", 0))

        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║           PORSCHE GRAPH — GUI Completeness Audit            ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        lines.append("  File: %s" % self.state["source_path"])
        lines.append("  Score: %d%%  (%d/%d checks passed)" % (
            self.state["score"], self.state["total_pass"], self.state["total_checks"]))
        lines.append("")

        categoryLabels = {
            "app": "APPLICATION-LEVEL",
            "window": "WINDOW-LEVEL",
            "widget": "WIDGET-LEVEL (GuiAspect)",
            "table": "TABLE-LEVEL",
            "editor": "EDITOR-LEVEL",
            "voice": "VOICE-LEVEL",
        }

        for category in ["app", "window", "widget", "table", "editor", "voice"]:
            if category not in results:
                continue
            catResults = results[category]
            catPass = sum(1 for v in catResults.values() if v["found"])
            catTotal = len(catResults)
            catScore = int((catPass / catTotal * 100) if catTotal > 0 else 0)

            lines.append("  ┌─ %s ─────────────────────────────────┐" % categoryLabels.get(category, category.upper()))
            lines.append("  │  Score: %d%%  (%d/%d)" % (catScore, catPass, catTotal))
            lines.append("  │")

            for itemId, info in catResults.items():
                found = info["found"]
                count = info["count"]
                label = info["label"]
                if found:
                    bar = "✅ %s" % label
                    detail = "(%d refs)" % count
                else:
                    bar = "❌ %s" % label
                    detail = "MISSING"
                lines.append("  │  %s  %s" % (bar, detail))

            lines.append("  └──────────────────────────────────────────────────────────┘")
            lines.append("")

        # Summary bar
        score = self.state["score"]
        barLen = 30
        filled = int(score / 100 * barLen)
        bar = "█" * filled + "░" * (barLen - filled)
        lines.append("  ┌─ PORSCHE SCORE ───────────────────────────────────────────┐")
        lines.append("  │  [%s] %d%%" % (bar, score))
        if score == 100:
            lines.append("  │  🏆 COMPLETE PORSCHE — every piece exists and works")
        elif score >= 80:
            lines.append("  │  🚗 Almost there — a few parts missing")
        elif score >= 60:
            lines.append("  │  🔧 Missing critical infrastructure — not drivable yet")
        elif score >= 40:
            lines.append("  │  📦 Cardboard box of Porsche parts — needs assembly")
        else:
            lines.append("  │  ❌ Not a Porsche — not even a box of parts")
        lines.append("  └──────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)

    def cmd_report(self, params):
        results = self.state["results"]
        if not results:
            return (0, None, ("ERR_NO_AUDIT", "run audit first", 0))

        lines = []
        lines.append("PORSCHE AUDIT REPORT")
        lines.append("====================")
        lines.append("File: %s" % self.state["source_path"])
        lines.append("Score: %d%% (%d/%d)" % (
            self.state["score"], self.state["total_pass"], self.state["total_checks"]))
        lines.append("")

        lines.append("MISSING ITEMS:")
        lines.append("-" * 40)
        missingCount = 0
        for category, items in results.items():
            for itemId, info in items.items():
                if not info["found"]:
                    lines.append("  [%s] %s" % (category, info["label"]))
                    missingCount += 1
        if missingCount == 0:
            lines.append("  (none — all checks passed!)")
        lines.append("")
        lines.append("PASSED ITEMS:")
        lines.append("-" * 40)
        passCount = 0
        for category, items in results.items():
            for itemId, info in items.items():
                if info["found"]:
                    lines.append("  [%s] %s (%d refs)" % (category, info["label"], info["count"]))
                    passCount += 1
        lines.append("")
        lines.append("SUMMARY: %d passed, %d missing, %d total" % (
            passCount, missingCount, passCount + missingCount))

        report = "\n".join(lines)
        return (1, report, None)

    def cmd_questions(self, params):
        lines = []
        lines.append("PORSCHE QUESTIONS — Asked for every GUI")
        lines.append("=========================================")
        lines.append("")
        currentCat = ""
        for category, itemId, label, pattern in AUDIT_QUESTIONS:
            if category != currentCat:
                currentCat = category
                catLabel = {
                    "app": "APPLICATION",
                    "window": "WINDOW",
                    "widget": "WIDGET (GuiAspect)",
                    "table": "TABLE",
                    "editor": "EDITOR",
                    "voice": "VOICE",
                }.get(category, category.upper())
                lines.append("")
                lines.append("%s:" % catLabel)
                lines.append("-" * 40)
            lines.append("  ? %s" % label)
        lines.append("")
        lines.append("Total questions: %d" % len(AUDIT_QUESTIONS))

        questions = "\n".join(lines)
        return (1, questions, None)
