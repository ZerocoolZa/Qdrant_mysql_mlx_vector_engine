#!/usr/bin/env python3
# [@GHOST]{[@file<Config.py>][@domain<Dom_Report>][@role<config>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<config>][@return<none>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Constants for Dom_Report v3 — 8 fact kinds, 7 question slots, verbosity levels, terminal layout, ANSI colors.}
# [@CLASS]{Config}
# [@FILEID]{core/Dom_Report/Config.py

import shutil

# ─── FACT KINDS (8) ─────────────────────────────────────────────────────────
# The open set of classifications. The collector accepts any string,
# but these are the ones it knows how to route into question slots.

KIND_INPUT = "input"
KIND_OUTPUT = "output"
KIND_MEASUREMENT = "measurement"
KIND_EVENT = "event"
KIND_ISSUE = "issue"
KIND_MESSAGE = "message"
KIND_RESULT = "result"
KIND_RECOMMENDATION = "recommendation"

FACT_KINDS = (
    KIND_INPUT, KIND_OUTPUT, KIND_MEASUREMENT,
    KIND_EVENT, KIND_ISSUE, KIND_MESSAGE,
    KIND_RESULT, KIND_RECOMMENDATION,
)

# ─── QUESTION SLOTS (7) ─────────────────────────────────────────────────────
# The fixed structure of every report. The collector routes facts into
# these slots by kind. The renderer walks them in this order.

SLOT_OPERATION = "operation"       # Q1: What was done?
SLOT_SOURCE = "source"             # Q2: Where did it happen? (implementation detail)
SLOT_INPUTS = "inputs"             # Q3: What went in?
SLOT_OUTPUTS = "outputs"           # Q4: What came out?
SLOT_OBSERVATIONS = "observations" # Q5: What was observed?
SLOT_OCCURRENCES = "occurrences"   # Q6: What occurred? (events, issues, messages)
SLOT_OUTCOME = "outcome"           # Q7: What was the outcome?

QUESTION_SLOTS = (
    SLOT_OPERATION, SLOT_SOURCE, SLOT_INPUTS, SLOT_OUTPUTS,
    SLOT_OBSERVATIONS, SLOT_OCCURRENCES, SLOT_OUTCOME,
)

# ─── KIND → SLOT ROUTING ────────────────────────────────────────────────────

KIND_TO_SLOT = {
    KIND_INPUT: SLOT_INPUTS,
    KIND_OUTPUT: SLOT_OUTPUTS,
    KIND_MEASUREMENT: SLOT_OBSERVATIONS,
    KIND_EVENT: SLOT_OCCURRENCES,
    KIND_ISSUE: SLOT_OCCURRENCES,
    KIND_MESSAGE: SLOT_OCCURRENCES,
    KIND_RESULT: SLOT_OUTCOME,
    KIND_RECOMMENDATION: SLOT_OCCURRENCES,
}

# ─── ISSUE SEVERITY ─────────────────────────────────────────────────────────

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# ─── VERBOSITY LEVELS ───────────────────────────────────────────────────────
# Controls which slots the renderer displays.
# Slot 1 (operation) and slot 7 (outcome) are ALWAYS shown.
#
# quiet:   slots 1 + 7
# normal:  slots 1 + 6 (issues only) + 7
# verbose: all 7 slots

VERBOSITY_QUIET = "quiet"
VERBOSITY_NORMAL = "normal"
VERBOSITY_VERBOSE = "verbose"
VERBOSITY_LEVELS = (VERBOSITY_QUIET, VERBOSITY_NORMAL, VERBOSITY_VERBOSE)

# ─── TERMINAL LAYOUT ────────────────────────────────────────────────────────

TERMINAL_WIDTH_FALLBACK = 80

def _detect_terminal_width():
    try:
        size = shutil.get_terminal_size((TERMINAL_WIDTH_FALLBACK, 24))
        return size.columns
    except Exception:
        return TERMINAL_WIDTH_FALLBACK

TERMINAL_WIDTH = _detect_terminal_width()
INDENT_UNIT = "  "

# ─── ANSI COLORS ────────────────────────────────────────────────────────────

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_MAGENTA = "\033[35m"

# ─── SEVERITY → SYMBOL / COLOR ──────────────────────────────────────────────

SEVERITY_SYMBOLS = {
    SEVERITY_ERROR: "✗",
    SEVERITY_WARNING: "!",
    SEVERITY_INFO: "•",
}

SEVERITY_COLORS = {
    SEVERITY_ERROR: COLOR_RED,
    SEVERITY_WARNING: COLOR_YELLOW,
    SEVERITY_INFO: COLOR_CYAN,
}

# ─── KIND → SYMBOL ──────────────────────────────────────────────────────────

KIND_SYMBOLS = {
    KIND_EVENT: "→",
    KIND_MESSAGE: "•",
    KIND_RECOMMENDATION: "↳",
}

# ─── DIAGNOSTIC PROTOCOL (Layer 2) ──────────────────────────────────────────
# The stable set of questions the investigator asks about every report.
# 6 categories, each with fixed questions.
# Some answers come from the report (Layer 1).
# Some come from the knowledge base (Layer 2, later).
# Some are "unknown" — pending further analysis.
# The questions NEVER change. Only the answers do.

CATEGORY_IDENTITY = "identity"
CATEGORY_OUTCOME = "outcome"
CATEGORY_CAUSE = "cause"
CATEGORY_HISTORY = "history"
CATEGORY_REPAIR = "repair"
CATEGORY_PREVENTION = "prevention"

DIAGNOSTIC_CATEGORIES = (
    CATEGORY_IDENTITY, CATEGORY_OUTCOME, CATEGORY_CAUSE,
    CATEGORY_HISTORY, CATEGORY_REPAIR, CATEGORY_PREVENTION,
)

# The stable questions within each category
DIAGNOSTIC_QUESTIONS = {
    CATEGORY_IDENTITY: (
        "what_happened",    # What operation was performed?
        "where",            # Where did it happen (source)?
        "who",              # Who produced it (source)?
    ),
    CATEGORY_OUTCOME: (
        "did_pass",         # Did it succeed?
        "did_fail",         # Did it fail?
        "what_produced",    # What was produced (outputs)?
    ),
    CATEGORY_CAUSE: (
        "why",              # Why did it fail (immediate reason)?
        "root_cause",       # What actually caused it?
        "was_expected",     # Was this failure expected?
    ),
    CATEGORY_HISTORY: (
        "seen_before",      # Has this happened before?
        "known_problem",    # Do we already know this problem?
        "is_new",           # Is this a new problem?
    ),
    CATEGORY_REPAIR: (
        "is_fixable",       # Is it fixable?
        "known_fix",        # Do we have a fix?
        "which_fix_worked", # Which fix worked before?
        "can_auto_apply",   # Can we apply it automatically?
    ),
    CATEGORY_PREVENTION: (
        "how_prevent",      # How do we stop it happening again?
        "missing_guard",    # What guard or validation is missing?
        "detect_earlier",   # Can we detect it earlier?
    ),
}

# Which categories the REPORT can answer (Layer 1)
REPORT_ANSWERED = (CATEGORY_IDENTITY, CATEGORY_OUTCOME)

# Which categories need the knowledge base (Layer 2, later)
KB_ANSWERED = (CATEGORY_HISTORY, CATEGORY_REPAIR, CATEGORY_PREVENTION)

# Which categories are partial (report gives immediate, KB gives root)
PARTIAL_ANSWERED = (CATEGORY_CAUSE,)

# Answer status
ANSWER_KNOWN = "known"
ANSWER_UNKNOWN = "unknown"
ANSWER_PENDING = "pending"       # needs knowledge base lookup
ANSWER_NOT_APPLICABLE = "n/a"    # question doesn't apply (e.g. "why" on a success)

# ─── COLOR TOGGLE ───────────────────────────────────────────────────────────

USE_COLOR = True
