#!/usr/bin/env python3
# [@GHOST]{[@file<__init__.py>][@domain<reports>][@role<package>][@auth<cascade>][@date<2026-07-03>][@ver<1.0.0>][@session<reports-package>]}
# [@VBSTYLE]{[@auth<cascade>][@role<package>][@return<none>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{reports — self-contained report package. from reports import * gives ReportUnit, Report, Fact, RendererTerminal, Config, all constants.}
# [@FILEID]{Packages/reports/__init__.py

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
    "ReportUnit", "Report", "Fact", "RendererTerminal", "Config",
    "Investigator", "KnowledgeBase", "DiagnosticDB",
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
    "USE_COLOR",
]

__version__ = "1.0.0"