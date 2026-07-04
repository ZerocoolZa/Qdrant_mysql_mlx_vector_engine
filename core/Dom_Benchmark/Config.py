#[@GHOST]{file_path="core/Dom_Benchmark/Config.py" date="2026-07-04" author="Devin" session_id="benchmark-framework" context="Configuration constants for the Error Fix Benchmark Framework. Cross-platform, Python 3.9-3.14, 100+ error cases, BCL persistence, MySQL knowledge sync."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="Config.py" domain="dom_benchmark" authority="BenchmarkConfig"}
#[@SUMMARY]{summary="Configuration constants for the Error Fix Benchmark Framework. Paths, MySQL connection, scoring weights, confidence thresholds, BCL types, sandbox settings, timing limits, TUI colors."}
#[@CLASS]{class="BenchmarkConfig" domain="dom_benchmark" authority="config"}
#[@METHOD]{method="read" type="config"}
#[@METHOD]{method="write" type="config"}

"""Config — Constants for the Error Fix Benchmark Framework.

All behavioral settings live here. No secrets, no env vars.
MySQL connection uses the existing project defaults.
"""

import os
import sys
import platform

# ── PROJECT PATHS ──
PROJECT_ROOT = os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine")
BENCHMARK_DIR = os.path.join(PROJECT_ROOT, "core", "Dom_Benchmark")
SANDBOX_DIR = os.path.join(BENCHMARK_DIR, "sandbox")
KNOWLEDGE_DIR = os.path.join(BENCHMARK_DIR, "knowledge")
RESULTS_DIR = os.path.join(BENCHMARK_DIR, "results")
REPLAY_DIR = os.path.join(BENCHMARK_DIR, "replay")

# ── MYSQL ──
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASS = ""
MYSQL_DB = "vb_shared"
MYSQL_PORT = 3306
MYSQL_SOCKET = "/tmp/mysql.sock"

# ── ERROR KNOWLEDGE TABLES ──
ERROR_KNOWLEDGE_TABLE = "error_knowledge"
FIX_ATTEMPTS_TABLE = "fix_attempts"
EXECUTION_LOG_TABLE = "execution_log"
LEARNED_RULES_TABLE = "learned_rules"
KNOW_PROBLEMS_TABLE = "know_problems"
KNOW_SOLUTIONS_TABLE = "know_solutions"

# ── BCL TYPES ──
BCL_TYPE_ERROR_FIX = "ERROR_FIX"
BCL_TYPE_BENCHMARK_RESULT = "BENCHMARK_RESULT"
BCL_TYPE_TEST_CASE = "TEST_CASE"
BCL_TYPE_FIX_CANDIDATE = "FIX_CANDIDATE"
BCL_TYPE_VALIDATION = "VALIDATION"
BCL_TYPE_LEARNING = "LEARNING"

# ── SCORING WEIGHTS ──
SCORE_BASE = 100000
SCORE_PER_FIX = 5000
SCORE_PER_REMAINING_ERROR = -1000
SCORE_PER_CHANGED_LINE = -5
SCORE_PER_ATTEMPT = -10
SCORE_PER_PASS = -50
SCORE_BONUS_CLEAN = 50000
SCORE_BONUS_CONSERVATIVE = 10000
SCORE_BONUS_FAST = 5000
SCORE_BONUS_SELF_VALIDATING = 8000
SCORE_PENALTY_FALSE_POSITIVE = -20000
SCORE_PENALTY_SYNTAX_ERROR = -50000
SCORE_PENALTY_TIMEOUT = -30000
SCORE_PENALTY_CRASH = -40000

# ── CONFIDENCE THRESHOLDS ──
MIN_CONFIDENCE = 0.30
PROMOTE_THRESHOLD = 0.75
DEMOTE_THRESHOLD = 0.25
MAX_CONFIDENCE = 0.99
CONFIDENCE_DECAY = 0.95
CONFIDENCE_BOOST = 1.05
INITIAL_CONFIDENCE = 0.50

# ── SANDBOX SETTINGS ──
SANDBOX_TIMEOUT_SEC = 10
SANDBOX_MAX_MEMORY_MB = 256
SANDBOX_MAX_OUTPUT_CHARS = 65536
SANDBOX_CLEANUP = True
SANDBOX_USE_TEMP_DIR = True

# ── TIMING ──
TIMING_PRECISION = 6
TIMING_WARN_MS = 5000
TIMING_TIMEOUT_MS = 30000

# ── LIMITS ──
MAX_FIX_ATTEMPTS = 5
MAX_PASS_COUNT = 10
MAX_CACHE_SIZE = 500
MAX_TRACEBACK_LEN = 4096
MAX_FIX_LEN = 2048
MAX_BCL_PACKET = 8192
MAX_RESULTS_DISPLAY = 50

# ── PYTHON VERSION COMPATIBILITY ──
PYTHON_MIN_VERSION = (3, 9)
PYTHON_MAX_VERSION = (3, 14)
CURRENT_PYTHON = sys.version_info[:2]

# ── PLATFORM ──
PLATFORM_NAME = platform.system()
PLATFORM_IS_MACOS = PLATFORM_NAME == "Darwin"
PLATFORM_IS_LINUX = PLATFORM_NAME == "Linux"
PLATFORM_IS_WINDOWS = PLATFORM_NAME == "Windows"
PLATFORM_ARCH = platform.machine()

# ── ERROR FAMILIES ──
ERROR_FAMILY_RUNTIME = "runtime"
ERROR_FAMILY_SYNTAX = "syntax"
ERROR_FAMILY_IMPORT = "import"
ERROR_FAMILY_OS = "os"
ERROR_FAMILY_WARNING = "warning"
ERROR_FAMILY_ASYNC = "async"
ERROR_FAMILY_THREADING = "threading"
ERROR_FAMILY_ENCODING = "encoding"

ERROR_FAMILIES = [
    ERROR_FAMILY_RUNTIME,
    ERROR_FAMILY_SYNTAX,
    ERROR_FAMILY_IMPORT,
    ERROR_FAMILY_OS,
    ERROR_FAMILY_WARNING,
    ERROR_FAMILY_ASYNC,
    ERROR_FAMILY_THREADING,
    ERROR_FAMILY_ENCODING,
]

# ── STANDARD PYTHON EXCEPTIONS (3.9-3.14) ──
STANDARD_EXCEPTIONS = [
    "BaseException",
    "SystemExit",
    "KeyboardInterrupt",
    "GeneratorExit",
    "Exception",
    "StopIteration",
    "StopAsyncIteration",
    "ArithmeticError",
    "OverflowError",
    "ZeroDivisionError",
    "FloatingPointError",
    "AssertionError",
    "AttributeError",
    "BufferError",
    "EOFError",
    "ImportError",
    "ModuleNotFoundError",
    "LookupError",
    "IndexError",
    "KeyError",
    "MemoryError",
    "NameError",
    "UnboundLocalError",
    "OSError",
    "BlockingIOError",
    "ChildProcessError",
    "ConnectionError",
    "BrokenPipeError",
    "ConnectionAbortedError",
    "ConnectionRefusedError",
    "ConnectionResetError",
    "FileExistsError",
    "FileNotFoundError",
    "InterruptedError",
    "IsADirectoryError",
    "NotADirectoryError",
    "PermissionError",
    "ProcessLookupError",
    "TimeoutError",
    "ReferenceError",
    "RuntimeError",
    "NotImplementedError",
    "RecursionError",
    "SyntaxError",
    "IndentationError",
    "TabError",
    "SystemError",
    "TypeError",
    "ValueError",
    "UnicodeError",
    "UnicodeDecodeError",
    "UnicodeEncodeError",
    "UnicodeTranslateError",
    "Warning",
    "DeprecationWarning",
    "PendingDeprecationWarning",
    "RuntimeWarning",
    "SyntaxWarning",
    "UserWarning",
    "FutureWarning",
    "ImportWarning",
    "UnicodeWarning",
    "BytesWarning",
    "ResourceWarning",
    "EncodingWarning",
]

# ── TUI COLORS (Rich) ──
COLOR_PASS = "green"
COLOR_FAIL = "red"
COLOR_WARN = "yellow"
COLOR_INFO = "cyan"
COLOR_DIM = "dim"
COLOR_BOLD = "bold"
COLOR_ERROR = "bright_red"
COLOR_SUCCESS = "bright_green"
COLOR_HEADER = "bright_cyan"
COLOR_SCORE_HIGH = "bright_green"
COLOR_SCORE_MID = "yellow"
COLOR_SCORE_LOW = "bright_red"

# ── DASHBOARD SETTINGS ──
DASHBOARD_REFRESH_SEC = 1
DASHBOARD_MAX_ROWS = 50
DASHBOARD_SHOW_PASSED = True
DASHBOARD_SHOW_FAILED = True
DASHBOARD_SHOW_TIMING = True

# ── LEARNING CURVE ──
LEARNING_WINDOW = 20
LEARNING_MIN_SAMPLES = 5
LEARNING_SMOOTHING = 0.3

# ── REGRESSION ──
REGRESSION_BASELINE_FILE = "baseline.json"
REGRESSION_TOLERANCE = 0.05
REGRESSION_MIN_CASES = 10

# ── PLUGIN ARCHITECTURE ──
PLUGIN_DIR = os.path.join(BENCHMARK_DIR, "plugins")
PLUGIN_ENTRY_POINT = "register"
PLUGIN_MIN_API_VERSION = 1

# ── BCL PERSISTENCE ──
BCL_KNOWLEDGE_FILE = os.path.join(KNOWLEDGE_DIR, "benchmark_knowledge.bcl")
BCL_RESULTS_FILE = os.path.join(RESULTS_DIR, "benchmark_results.bcl")
BCL_REPLAY_FILE = os.path.join(REPLAY_DIR, "benchmark_replay.bcl")

# ── REPLAY ──
REPLAY_MAX_STEPS = 1000
REPLAY_SAVE_INTERVAL = 10

# ── VERIFICATION ──
VERIFY_PY_COMPILE = True
VERIFY_AST_PARSE = True
VERIFY_RE_RUN = True
VERIFY_SELF_VALIDATING = True
