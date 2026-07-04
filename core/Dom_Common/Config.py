#!/usr/bin/env python3
#[@GHOST]{file_path="core/Dom_Common/Config.py" date="2026-07-04" author="devin" session_id="bcl-common-module" context="Shared constants for Dom_Common module. MySQL config, BCL tool path, neural model dimensions, error types, fix actions, confidence thresholds, live debug settings."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="Config.py" domain="dom_common" authority="Config"}
#[@SUMMARY]{summary="Shared constants for Dom_Common: MySQL config, BCL tool path, neural model dims, error types, fix actions, confidence thresholds, live debug settings."}
#[@CLASS]{class="Config" domain="dom_common" authority="constants"}
#[@METHOD]{method="none" type="constants"}

"""Config — Shared constants for Dom_Common module.

All Dom_Common classes read from this module. No hard-coded values
in any class file. Change here, affects all.
"""

import os

# ── MySQL Connection ──
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASS = ""
MYSQL_SOCKET = "/tmp/mysql.sock"
MYSQL_PORT = 0
MYSQL_DB = "vb_shared"

# ── BCL Tool Path ──
BCL_TOOL_PATH = os.path.expanduser(
    "~/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/bcl_tool"
)

# ── Neural Model Dimensions (from ai_fix_data_gen.c) ──
INPUT_DIM = 40
HIDDEN_DIM = 64
OUTPUT_DIM = 16

# ── Error Types (16 standard Python error types, from ai_fix_data_gen.c) ──
ERROR_TYPES = [
    "ModuleNotFoundError", "ImportError", "FileNotFoundError", "AttributeError",
    "KeyError", "IndexError", "IndentationError", "NameError",
    "ValueError", "TypeError", "SyntaxError", "RuntimeError",
    "ConnectionError", "PermissionError", "RecursionError", "UnicodeDecodeError",
]

# ── Fix Actions (16 fix action categories, from ai_fix_data_gen.c) ──
FIX_ACTIONS = [
    "install_module",      # 0: ModuleNotFoundError
    "fix_import_name",     # 1: ImportError
    "check_path",          # 2: FileNotFoundError
    "check_attribute",     # 3: AttributeError
    "use_get_or_check",    # 4: KeyError
    "check_length",        # 5: IndexError
    "fix_indentation",     # 6: IndentationError
    "define_variable",     # 7: NameError
    "validate_input",      # 8: ValueError
    "cast_or_convert",     # 9: TypeError
    "fix_syntax",          # 10: SyntaxError
    "handle_runtime",      # 11: RuntimeError
    "check_connection",    # 12: ConnectionError
    "check_permissions",   # 13: PermissionError
    "add_base_case",       # 14: RecursionError
    "fix_encoding",        # 15: UnicodeDecodeError
]

# ── Error Type → Fix Action Mapping ──
ERROR_TO_FIX = {
    "ModuleNotFoundError": 0,
    "ImportError": 1,
    "FileNotFoundError": 2,
    "AttributeError": 3,
    "KeyError": 4,
    "IndexError": 5,
    "IndentationError": 6,
    "NameError": 7,
    "ValueError": 8,
    "TypeError": 9,
    "SyntaxError": 10,
    "RuntimeError": 11,
    "ConnectionError": 12,
    "PermissionError": 13,
    "RecursionError": 14,
    "UnicodeDecodeError": 15,
}

# ── Fix Templates (from ai_fix_bridge.py DEFAULT_RULES) ──
FIX_TEMPLATES = {
    "ModuleNotFoundError": {
        "fix_description": "Module not installed or wrong name. Try: pip install <module> or check import spelling.",
        "fix_action": "check_import",
        "examples": [
            {"bad": "import nonexistent_xyz", "good": "import os  # use a real module"},
            {"bad": "import nump", "good": "import numpy as np  # typo: nump -> numpy"},
        ],
    },
    "ImportError": {
        "fix_description": "Name does not exist in the module. Check the module's exports or API docs.",
        "fix_action": "check_import_name",
        "examples": [
            {"bad": "from os import notarealthing", "good": "from os import path  # check available names"},
        ],
    },
    "FileNotFoundError": {
        "fix_description": "File or directory does not exist. Check path spelling, use absolute paths, or create the file first.",
        "fix_action": "check_path",
        "examples": [
            {"bad": "open('/nonexistent/file.txt')", "good": "open(os.path.expanduser('~/file.txt'))  # use real path"},
        ],
    },
    "AttributeError": {
        "fix_description": "Object does not have that attribute. Check the class API or use getattr() with a default.",
        "fix_action": "check_attribute",
        "examples": [
            {"bad": "obj.nonexistent_method()", "good": "getattr(obj, 'method', default_fn)()  # safe access"},
        ],
    },
    "KeyError": {
        "fix_description": "Key not in dictionary. Use dict.get(key) with a default or check key existence first.",
        "fix_action": "use_get_or_check",
        "examples": [
            {"bad": "value = my_dict['missing_key']", "good": "value = my_dict.get('missing_key', default_value)"},
        ],
    },
    "IndexError": {
        "fix_description": "List index out of range. Check len() before accessing or use try/except.",
        "fix_action": "check_length",
        "examples": [
            {"bad": "print(my_list[10])", "good": "if len(my_list) > 10: print(my_list[10])"},
        ],
    },
    "NameError": {
        "fix_description": "Variable or function name used before assignment or import.",
        "fix_action": "define_variable",
        "examples": [
            {"bad": "print(undefined_var)", "good": "undefined_var = None  # define first\nprint(undefined_var)"},
        ],
    },
    "ValueError": {
        "fix_description": "Invalid value conversion. Validate input before casting.",
        "fix_action": "validate_input",
        "examples": [
            {"bad": "int('abc')", "good": "try: int('abc')\nexcept ValueError: int(0)  # fallback"},
        ],
    },
    "TypeError": {
        "fix_description": "Type mismatch in operation. Cast or convert types.",
        "fix_action": "cast_or_convert",
        "examples": [
            {"bad": "result = '5' + 3", "good": "result = int('5') + 3  # cast to int"},
        ],
    },
    "SyntaxError": {
        "fix_description": "Invalid Python syntax. Check line indicated in traceback.",
        "fix_action": "fix_syntax",
        "examples": [
            {"bad": "if True print('yes')", "good": "if True: print('yes')  # add colon"},
        ],
    },
    "IndentationError": {
        "fix_description": "Mixed tabs/spaces or incorrect indentation. Use 4 spaces consistently.",
        "fix_action": "fix_indentation",
        "examples": [
            {"bad": "def foo():\nreturn 42", "good": "def foo():\n    return 42  # indent 4 spaces"},
        ],
    },
    "ZeroDivisionError": {
        "fix_description": "Attempted to divide by zero. Check divisor before dividing.",
        "fix_action": "check_divisor",
        "examples": [
            {"bad": "x = 1 / 0", "good": "x = 1 / (y if y != 0 else 1)  # guard divisor"},
        ],
    },
}

# ── Confidence Thresholds ──
MIN_CONFIDENCE = 0.5       # below this, fix is "candidate"
PROMOTE_THRESHOLD = 0.8    # above this, fix is "promoted" (auto-apply)
DEMOTE_THRESHOLD = 0.3     # below this, fix is "deprecated"

# ── Live Debug Settings ──
LIVE_DEBUG_MAX_RETRIES = 3       # max fix attempts before giving up
LIVE_DEBUG_HALT_ON_ERROR = True  # halt execution on error
LIVE_DEBUG_WRITE_BACK = True     # write fix to file after successful test
LIVE_DEBUG_RE_RUN = True         # re-run from error point after fix

# ── VBStyle Rules (from bcl_rule_enforcer.c) ──
VBSTYLE_RULES = [
    "NoPrint", "NoDecorators", "NoSelfUnderscore",
    "GhostHeader", "VBStyleHeader", "RunDispatch",
    "PascalCase", "NoTabs", "NoTrailingWs",
]

# ── Paths ──
PROJECT_ROOT = os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine")
CASCADE_TOOLSTACK = os.path.join(PROJECT_ROOT, "Cascade_toolStack")
BCL_UNITS = os.path.join(CASCADE_TOOLSTACK, "bcl_units")
BIN_TOOLS = os.path.join(CASCADE_TOOLSTACK, "bin_tools")
CORE_DIR = os.path.join(PROJECT_ROOT, "core")

# ── BCL Packet Types ──
BCL_TYPE_OK = "[@OK]"
BCL_TYPE_ERR = "[@ERR]"
BCL_TYPE_REPORT = "[@REPORT]"
BCL_TYPE_ERROR_FIX = "[@ERROR_FIX]"

# ── Error Knowledge Table Schema ──
ERROR_KNOWLEDGE_TABLE = "error_knowledge"
FIX_ATTEMPTS_TABLE = "fix_attempts"
EXECUTION_LOG_TABLE = "execution_log"
LEARNED_RULES_TABLE = "learned_rules"
KNOW_SOLUTIONS_TABLE = "know_solutions"
