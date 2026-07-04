#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_config.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstyle-fix"
# context="BCL Config — Rules, syntax, constants for Bracket Command Language. Single source of truth."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="UPPERCASE constants BASE_DIR derived no hardcoded paths"}
# [@FILEID]{id="bcl_config.py" domain="BCL" authority="config"}
# [@SUMMARY]{summary="BCL domain config: syntax rules, BCL forms, IR rules, lexer constants, engine constants, domain keywords. Config file — exempt from @run @t3 @state."}

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── BCL RULES (from vb_shared.rules table) ─────────────────────────────────

RULES = [
    {"id": 24, "name": "bracket_format", "rule": "Token must be in format [@Token] (capital first letter)", "check": "container_name_must_start_capital", "severity": "high"},
    {"id": 162, "name": "no_regex_guessing", "rule": "NO regex bracket guessing — must use real bracket parser", "check": "parser_must_be_real", "severity": "high"},
    {"id": 220, "name": "real_bracket_parser", "rule": "Must use real bracket parser (not regex)", "check": "parser_must_be_real", "severity": "high"},
    {"id": 999, "name": "weight_position", "rule": "Weight MUST be the last element in every bracket tuple", "check": "weight_must_be_last", "severity": "high", "format": '{("step1";"step2";92)}'},
]

# ─── SYNTAX ─────────────────────────────────────────────────────────────────

SYNTAX = {
    "container_open": "[@",
    "container_close": "]",
    "brace_open": "{",
    "brace_close": "}",
    "tuple_open": "(",
    "tuple_close": ")",
    "separator": ";",
    "quote": '"',
    "weight_type": "int",
    "weight_min": 0,
    "weight_max": 100,
    "name_chars": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",
}

# ─── BRANCH TOKENS ──────────────────────────────────────────────────────────

BRANCH_TOKENS = ["Pass", "Fail"]
OPTIONAL_BRANCH_TOKENS = ["Unsure", "Wait"]

# ─── BCL FORMS ──────────────────────────────────────────────────────────────

BCL_FORMS = {
    "config": {"description": "Config form — describes state, passive, read by dom_config", "format": '[@name]{("key";"value")}', "example": '[@bcl-config]'},
    "command": {"description": "Command form — executes action, active, run through MemUnit", "format": '[@name]{("action";weight)}', "example": '[@bcl-command]'},
    "token": {"description": "Simple token — flat, no braces (obey.md style)", "format": '[@tag] ("desc";"desc2")', "example": '[@tuples] ("all methods must return Tuple3")'},
    "decision_tree": {"description": "Decision tree — nested Pass/Fail/Unsure with weights", "format": '[@rule]{[@check]{[@Pass]{("fix";weight)}[@Fail]{...}}}', "example": '[@QuestionWhat]{[@Pass]{("text";92)}[@Fail]{("text";92)}}'},
}

# ─── IR COMPILER RULES (VBStyle compliance for IR compilation) ──────────────

IR_RULES = [
    {"id": "@print(22)", "scope": "method", "severity": "hard", "predicate": lambda f: f["has_print"], "description": "Disallow print() in method scope"},
    {"id": "@decorators(20)", "scope": "method", "severity": "hard", "predicate": lambda f: f["decorator_count"] > 0, "description": "No @staticmethod/@property/@classmethod"},
    {"id": "@underscore(19)", "scope": "method", "severity": "hard", "predicate": lambda f: f["has_self_underscore"], "description": "No self._xxx access"},
    {"id": "@t3(50)", "scope": "method", "severity": "hard", "predicate": lambda f: f["return_count"] > 0 and not f["returns_tuple3"], "description": "All methods must return Tuple3"},
    {"id": "@hardcode(24)", "scope": "method", "severity": "soft", "predicate": lambda f: f["hardcoded_count"] > 3, "description": "More than 3 hardcoded literals"},
    {"id": "@eval(53)", "scope": "method", "severity": "hard", "predicate": lambda f: f.get("has_eval", False), "description": "eval()/exec() usage forbidden"},
    {"id": "@subprocess(55)", "scope": "method", "severity": "hard", "predicate": lambda f: f.get("has_subprocess", False), "description": "os.system()/subprocess usage requires review"},
    {"id": "@complexity(56)", "scope": "method", "severity": "soft", "predicate": lambda f: f.get("complexity", 0) > 10, "description": "Cyclomatic complexity > 10"},
    {"id": "@nesting(57)", "scope": "method", "severity": "soft", "predicate": lambda f: f.get("max_nesting", 0) > 4, "description": "Max nesting depth > 4"},
    {"id": "@pascal(38)", "scope": "class", "severity": "hard", "predicate": lambda c: c["class_name"] and not c["class_name"][:1].isupper(), "description": "Classes must be PascalCase"},
    {"id": "@run(43)", "scope": "class", "severity": "hard", "predicate": lambda c: not c["has_run"], "description": "Class must have Run() method"},
    {"id": "@ctor(40)", "scope": "class", "severity": "hard", "predicate": lambda c: not c["has_init"], "description": "Class must have __init__"},
    {"id": "@state(41)", "scope": "class", "severity": "hard", "predicate": lambda c: not c["has_state"], "description": "Class must use self.state dict"},
    {"id": "@tabs(25)", "scope": "class", "severity": "hard", "predicate": lambda c: c["has_tabs"], "description": "No tabs, spaces only"},
    {"id": "@upper(39)", "scope": "class", "severity": "soft", "predicate": lambda c: any(not n.isupper() for n in c["class_constants"]), "description": "Class constants must be UPPERCASE"},
    {"id": "@whitespace(26)", "scope": "file", "severity": "soft", "predicate": lambda f: f["has_trailing_ws"], "description": "No trailing whitespace"},
    {"id": "@deadimport(58)", "scope": "file", "severity": "soft", "predicate": lambda f: len(f.get("dead_imports", [])) > 0, "description": "Unused imports detected"},
]

# ─── DOMAIN KEYWORDS ────────────────────────────────────────────────────────

DOMAIN_KEYWORDS = {
    "search": ["search", "query", "retrieve", "find", "lookup", "match"],
    "index": ["index", "idx", "ann", "hnsw", "faiss", "qdrant"],
    "embed": ["embed", "vector", "encoding", "codebert", "transformer"],
    "storage": ["store", "save", "load", "db", "sqlite", "disk", "file"],
    "config": ["config", "setting", "param", "option", "preference"],
    "gui": ["gui", "widget", "window", "panel", "button", "render", "display"],
    "parse": ["parse", "token", "lex", "syntax", "ast", "grammar"],
    "network": ["http", "socket", "request", "response", "api", "url", "client"],
    "security": ["auth", "encrypt", "decrypt", "hash", "password", "token", "key"],
    "audit": ["audit", "log", "trace", "monitor", "metric", "report"],
    "graph": ["graph", "node", "edge", "vertex", "traverse", "adjacency"],
    "memory": ["memory", "cache", "buffer", "pool", "mem"],
    "text": ["text", "string", "char", "word", "sentence", "document"],
    "ingest": ["ingest", "import", "consume", "batch", "pipeline", "feed"],
    "transform": ["transform", "convert", "map", "remap", "translate", "adapt"],
    "runtime": ["runtime", "execute", "run", "dispatch", "command", "schedule"],
    "validate": ["validate", "check", "verify", "assert", "test", "inspect"],
    "compress": ["compress", "zip", "gzip", "deflate", "archive", "pack"],
    "style": ["style", "theme", "color", "font", "css", "layout", "skin"],
    "workflow": ["workflow", "step", "stage", "flow", "process", "pipeline"],
}

DOMAIN_EXCLUDE = {"key": {"keys", "keyboard", "keypress"}}

# ─── LEXER CONSTANTS (moved from bcl_lexer.py) ──────────────────────────────

ESCAPE_MAP = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", ";": ";"}

CONTAINER_OPEN = 1
BRACE_OPEN = 2
BRACE_CLOSE = 3
PAREN_OPEN = 4
PAREN_CLOSE = 5
SEMICOLON = 6
STRING = 7
NUMBER = 8
BAREWORD = 9
EOF = 10

TYPE_NAMES = {
    CONTAINER_OPEN: "CONTAINER_OPEN",
    BRACE_OPEN: "BRACE_OPEN",
    BRACE_CLOSE: "BRACE_CLOSE",
    PAREN_OPEN: "PAREN_OPEN",
    PAREN_CLOSE: "PAREN_CLOSE",
    SEMICOLON: "SEMICOLON",
    STRING: "STRING",
    NUMBER: "NUMBER",
    BAREWORD: "BAREWORD",
    EOF: "EOF",
}

WHITESPACE = " \t\n\r"
DELIMITERS = " \t\n\r;(){}[]\""

# ─── ENGINE CONSTANTS (moved from bcl_engine.py) ────────────────────────────

STAGES = ["LEX", "PARSE", "VALIDATE", "FIX", "SERIALIZE"]
MAX_FIX_CYCLES = 3

ALLOWED_TRANSITIONS = {
    "LEX": {"PARSE"},
    "PARSE": {"VALIDATE"},
    "VALIDATE": {"FIX", "SERIALIZE"},
    "FIX": {"VALIDATE"},
    "SERIALIZE": set(),
}

# ─── FIXER CONSTANTS (moved from bcl_fixer.py) ──────────────────────────────

FIXER_MAX_ITERATIONS = 5
WEIGHT_MIN = 0
WEIGHT_MAX = 100
