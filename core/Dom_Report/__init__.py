#!/usr/bin/env python3
# [@GHOST]{[@file<__init__.py>][@domain<Dom_Report>][@role<package>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<package>][@return<none>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Dom_Report v3 — universal information collector + diagnostic investigator + knowledge base + MySQL diagnostic DB. 1 fact type, 7 question slots, 6 diagnostic categories, 3 verbosity levels.}
# [@WCL]{[@exports<ReportUnit Report Fact Investigator KnowledgeBase DiagnosticDB RendererTerminal Config>]}
# [@FILEID]{core/Dom_Report/__init__.py

from .Config import (
    KIND_INPUT, KIND_OUTPUT, KIND_MEASUREMENT, KIND_EVENT, KIND_ISSUE,
    KIND_MESSAGE, KIND_RESULT, KIND_RECOMMENDATION, FACT_KINDS,
    SLOT_OPERATION, SLOT_SOURCE, SLOT_INPUTS, SLOT_OUTPUTS,
    SLOT_OBSERVATIONS, SLOT_OCCURRENCES, SLOT_OUTCOME, QUESTION_SLOTS,
    KIND_TO_SLOT,
    SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO,
    VERBOSITY_QUIET, VERBOSITY_NORMAL, VERBOSITY_VERBOSE, VERBOSITY_LEVELS,
    TERMINAL_WIDTH, INDENT_UNIT,
    COLOR_RESET, COLOR_BOLD, COLOR_DIM, COLOR_RED, COLOR_GREEN,
    COLOR_YELLOW, COLOR_BLUE, COLOR_CYAN, COLOR_MAGENTA,
    SEVERITY_SYMBOLS, SEVERITY_COLORS, KIND_SYMBOLS,
    CATEGORY_IDENTITY, CATEGORY_OUTCOME, CATEGORY_CAUSE,
    CATEGORY_HISTORY, CATEGORY_REPAIR, CATEGORY_PREVENTION,
    DIAGNOSTIC_CATEGORIES, DIAGNOSTIC_QUESTIONS,
    REPORT_ANSWERED, KB_ANSWERED, PARTIAL_ANSWERED,
    ANSWER_KNOWN, ANSWER_UNKNOWN, ANSWER_PENDING, ANSWER_NOT_APPLICABLE,
    USE_COLOR,
)
from .Fact import Fact
from .Report import Report
from .RendererTerminal import RendererTerminal
from .ReportUnit import ReportUnit
from .Investigator import Investigator
from .KnowledgeBase import KnowledgeBase
from .DiagnosticDB import DiagnosticDB

__all__ = [
    "ReportUnit", "Report", "Fact", "Investigator", "KnowledgeBase", "DiagnosticDB", "RendererTerminal", "Config",
    "KIND_INPUT", "KIND_OUTPUT", "KIND_MEASUREMENT", "KIND_EVENT",
    "KIND_ISSUE", "KIND_MESSAGE", "KIND_RESULT", "KIND_RECOMMENDATION",
    "FACT_KINDS",
    "SLOT_OPERATION", "SLOT_SOURCE", "SLOT_INPUTS", "SLOT_OUTPUTS",
    "SLOT_OBSERVATIONS", "SLOT_OCCURRENCES", "SLOT_OUTCOME", "QUESTION_SLOTS",
    "KIND_TO_SLOT",
    "SEVERITY_ERROR", "SEVERITY_WARNING", "SEVERITY_INFO",
    "VERBOSITY_QUIET", "VERBOSITY_NORMAL", "VERBOSITY_VERBOSE", "VERBOSITY_LEVELS",
    "TERMINAL_WIDTH", "INDENT_UNIT",
    "COLOR_RESET", "COLOR_BOLD", "COLOR_DIM", "COLOR_RED", "COLOR_GREEN",
    "COLOR_YELLOW", "COLOR_BLUE", "COLOR_CYAN", "COLOR_MAGENTA",
    "SEVERITY_SYMBOLS", "SEVERITY_COLORS", "KIND_SYMBOLS",
    "CATEGORY_IDENTITY", "CATEGORY_OUTCOME", "CATEGORY_CAUSE",
    "CATEGORY_HISTORY", "CATEGORY_REPAIR", "CATEGORY_PREVENTION",
    "DIAGNOSTIC_CATEGORIES", "DIAGNOSTIC_QUESTIONS",
    "REPORT_ANSWERED", "KB_ANSWERED", "PARTIAL_ANSWERED",
    "ANSWER_KNOWN", "ANSWER_UNKNOWN", "ANSWER_PENDING", "ANSWER_NOT_APPLICABLE",
    "USE_COLOR",
]

__version__ = "3.0.0"
