#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Core/utility/Config.py"
# date="2026-06-27" author="Cascade" session_id="utility-config"
# context="Config for Core/utility scripts. Paths, settings, targets. Globally reusable."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="UPPERCASE constants BASE_DIR derived"}
# [@FILEID]{id="Config.py" domain="utility" authority="config"}
# [@SUMMARY]{summary="Configures all utility scripts. Targets are registered here, utilities accept overrides via params."}

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

# ─── TARGETS ────────────────────────────────────────────────────────────────
# Each target = a set of source files to combine into one output file.
# Utilities accept any target via params — these are just defaults.

TARGETS = {
    "BCL": {
        "source_dir": os.path.join(PROJECT_ROOT, "BCL"),
        "output_path": os.path.join(PROJECT_ROOT, "BCL", "bcl_all.py"),
        "config_path": os.path.join(PROJECT_ROOT, "BCL", "bcl_config.py"),
        "files": [
            "bcl_parser.py", "bcl_lexer.py", "bcl_validator.py",
            "bcl_fixer.py", "bcl_engine.py", "bcl_visitor.py",
            "bcl_diff.py", "bcl_schema.py", "bcl_merger.py",
            "bcl_formatter.py", "bcl_roundtrip.py", "bcl_cache.py",
            "bcl_serializer.py", "bcl_exporter.py", "bcl_importer.py",
            "bcl_extractor.py", "bcl_rules.py", "bcl_compiler.py",
            "bcl_analyzer.py", "bcl_query.py", "bcl_reporter.py",
        ],
        "renames": {
            "Violation": "BCLViolation",
            "ValidationReport": "BCLValidationReport",
            "IRValidator": "BCLIRValidator",
            "FixAction": "BCLFixAction",
            "IRExporter": "BCLIRExporter",
            "FeatureExtractor": "BCLFeatureExtractor",
            "RuleEngine": "BCLRuleEngine",
            "IRCompiler": "BCLIRCompiler",
            "PostAnalyzer": "BCLPostAnalyzer",
            "IRQuery": "BCLIRQuery",
            "SummaryReporter": "BCLSummaryReporter",
        },
        "import_header": "from bcl_config import (\n"
            "    ESCAPE_MAP, CONTAINER_OPEN, BRACE_OPEN, BRACE_CLOSE,\n"
            "    PAREN_OPEN, PAREN_CLOSE, SEMICOLON, STRING, NUMBER, BAREWORD, EOF,\n"
            "    TYPE_NAMES, WHITESPACE, DELIMITERS,\n"
            "    STAGES, MAX_FIX_CYCLES, ALLOWED_TRANSITIONS,\n"
            "    FIXER_MAX_ITERATIONS, WEIGHT_MIN, WEIGHT_MAX,\n"
            "    BRANCH_TOKENS, OPTIONAL_BRANCH_TOKENS,\n"
            "    IR_RULES, DOMAIN_KEYWORDS, DOMAIN_EXCLUDE,\n"
            ")\n\n"
            "VALID_NAME_CHARS = set(\"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-\")\n\n",
        "patches": [
            {
                "find": '        self.state["report"] = report\n        return (1, report.ToDict(), None)',
                "replace": '        self.state["report"] = report\n        td = report.ToDict()\n        return (1, td[1] if td[0] == 1 else {}, None)',
            },
            {
                "find": '        actions = []\n        sorted_violations = sorted(report.state["violations"], key=lambda v: v.rule_id)',
                "replace": '        actions = []\n'
                    '        if hasattr(report, "state"):\n'
                    '            violations = report.state["violations"]\n'
                    '        elif isinstance(report, dict):\n'
                    '            violations = []\n'
                    '            for vd in report.get("violations", []):\n'
                    '                vobj = BCLViolation(vd.get("rule_id", 0), vd.get("rule_name", ""), vd.get("severity", ""), vd.get("path", ""), vd.get("message", ""))\n'
                    '                violations.append(vobj)\n'
                    '        else:\n'
                    '            violations = []\n'
                    '        sorted_violations = sorted(violations, key=lambda v: v.state["rule_id"])',
            },
            {
                "find": 'fix_result = self.fixer.Run("fix", {"root": ast_root, "report": self.BuildReport(report_dict)})',
                "replace": 'fix_result = self.fixer.Run("fix", {"root": ast_root, "report": report_dict})',
            },
        ],
    },
}

# ─── FIX INDENT SETTINGS ────────────────────────────────────────────────────

INDENT_SPACES = 4

# ─── UTILITY PATHS ──────────────────────────────────────────────────────────

CORE_DIR = os.path.join(PROJECT_ROOT, "core")
SCAN_DIRS = [
    os.path.join(CORE_DIR, "Dom_Gui"),
    os.path.join(CORE_DIR, "Dom_Vsstyle"),
    os.path.join(CORE_DIR, "utility"),
]
ERROR_LOG_DB = os.path.join(PROJECT_ROOT, "error_log.db")
ERROR_HANDLER_DB = os.path.join(PROJECT_ROOT, "error_handler.db")

# ─── INDEXER SETTINGS ───────────────────────────────────────────────────────

INDEXER_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", ".pytest_cache", ".mypy_cache"}
INDEXER_EXTENSIONS = [".py", ".c", ".h", ".cpp", ".hpp", ".mm", ".m", ".metal", ".swift", ".sh", ".sql", ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".html", ".css", ".js", ".ts", ".csv", ".conf", ".cfg", ".rmd", ".bin", ".db", ".sqlite", ".bak", ".zip", ".gz", ".tar", ".so", ".dylib", ".a", ".o", ".plist", ".png", ".jpg", ".jpeg", ".svg", ".icns", ".pdf"]
INDEXER_HASH_THRESHOLD = 100 * 1024 * 1024
INDEXER_DB_PATH = os.path.join(PROJECT_ROOT, "file_index.db")

# ─── VBS SCANNER SETTINGS ───────────────────────────────────────────────────

SCANNER_CHECK_PRINT = True
SCANNER_CHECK_DECORATORS = True
SCANNER_CHECK_SELF_UNDER = True
SCANNER_CHECK_HEADERS = True
SCANNER_CHECK_RUN = True
SCANNER_CHECK_TUPLE3 = True
SCANNER_CHECK_NAMING = True
SCANNER_CHECK_TABS = True
SCANNER_CHECK_TRAILING_WS = True

# ─── CLEANER SETTINGS ───────────────────────────────────────────────────────

CLEANER_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", ".tox"}
CLEANER_REMOVE_DIRS = {"__pycache__"}
CLEANER_REMOVE_EXTS = {".pyc", ".pyo", ".tmp", ".DS_Store"}
CLEANER_DRY_RUN = True

# ─── ERROR HANDLER SETTINGS ─────────────────────────────────────────────────

ERROR_MAX_LOG_ENTRIES = 500
ERROR_SEVERITY_INFO = "info"
ERROR_SEVERITY_WARNING = "warning"
ERROR_SEVERITY_ERROR = "error"
ERROR_SEVERITY_CRITICAL = "critical"
ERROR_RECOVERY_IGNORE = "ignore"
ERROR_RECOVERY_RETRY = "retry"
ERROR_RECOVERY_ROLLBACK = "rollback"
ERROR_RECOVERY_CANCEL = "cancel"
ERROR_RECOVERY_SNAPSHOT = "snapshot"
ERROR_RECOVERY_MARK_INVALID = "mark_invalid"
ERROR_RECOVERY_REQUEST_USER = "request_user"

# ─── ERROR TRACKER (MySQL) ──────────────────────────────────────────────────

ERROR_TRACKER_MYSQL = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "vb_shared",
    "unix_socket": "/tmp/mysql.sock",
}

# ─── PREFLIGHT SETTINGS ─────────────────────────────────────────────────────

PREFLIGHT_CHECK_CONSTRAINTS = True
PREFLIGHT_CHECK_ORPHANS = True
PREFLIGHT_CHECK_OVERFLOW = True
PREFLIGHT_CHECK_FK = True

# ─── DOM AUDIT SETTINGS ─────────────────────────────────────────────────────

AUDIT_MAX_HISTORY = 1000

# ─── DIFF CHECK SETTINGS ────────────────────────────────────────────────────

DIFF_IGNORE_WHITESPACE = False

# ─── STATS REPORT SETTINGS ──────────────────────────────────────────────────

STATS_REPORT_FORMAT = "markdown"

# ─── CONTENT EXTRACT SETTINGS ───────────────────────────────────────────────

EXTRACT_CHECK_PRINT = True
EXTRACT_CHECK_DECORATORS = True
EXTRACT_CHECK_HARDcoded_PATHS = True
EXTRACT_CHECK_SQL = True
EXTRACT_CHECK_FILE_IO = True

# ─── VBS TEST SETTINGS ──────────────────────────────────────────────────────

TEST_TIMEOUT_SECONDS = 30
TEST_BENCHMARK_DEFAULT_ITERATIONS = 100

# ─── BACKUP SETTINGS ────────────────────────────────────────────────────────

BACKUP_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", ".pytest_cache", ".mypy_cache"}
BACKUP_SKIP_EXTS = {".pyc", ".pyo", ".DS_Store", ".tmp"}
BACKUP_S3_BUCKET = ""
BACKUP_S3_PREFIX = "backups/"
BACKUP_EMAIL_PROVIDER = "gmail"
BACKUP_TO_EMAIL = ""
BACKUP_GIT_REMOTE = "origin"
BACKUP_GIT_BRANCH = ""
BACKUP_COMMIT_MSG = "Automated backup"

# ─── ORCHESTRATION (BCL-style rules) ────────────────────────────────────────
# [@ORCH]{what<SystemCheck>when<startup>where<CORE_DIR>why<verify_integrity>order<1>on_fail<report>}
# [@ORCH]{what<Indexer>when<startup>where<SCAN_DIRS>why<build_index>order<2>on_fail<continue>}
# [@ORCH]{what<VbsScanner>when<startup>where<CORE_DIR>why<find_violations>order<3>on_fail<report>}
# [@ORCH]{what<Cleaner>when<startup>where<CORE_DIR>why<remove_artifacts>order<4>on_fail<continue>}
# [@ORCH]{what<ErrorHandler>when<error>where<any>why<capture_and_recover>order<1>on_fail<escalate>}
# [@ORCH]{what<ErrorTracker>when<error>where<MySQL>why<lookup_lesson>order<2>on_fail<continue>}
# [@ORCH]{what<DomAudit>when<change>where<CORE_DIR>why<drift_detect>order<1>on_fail<report>}
# [@ORCH]{what<DiffCheck>when<change>where<CORE_DIR>why<diff_index>order<2>on_fail<continue>}
# [@ORCH]{what<StatsReport>when<scheduled>where<CORE_DIR>why<generate_report>order<1>on_fail<continue>}
# [@ORCH]{what<PreFlight>when<db_change>where<sqlite>why<db_integrity>order<1>on_fail<report>}
# [@ORCH]{what<VbsTest>when<code_change>where<CORE_DIR>why<run_tests>order<1>on_fail<report>}
# [@ORCH]{what<ContentExtract>when<scan>where<CORE_DIR>why<extract_metadata>order<1>on_fail<continue>}
# [@ORCH]{what<Backup>when<scheduled>where<PROJECT_ROOT>why<full_redundancy_backup>order<10>on_fail<report>}

TRIGGERS = {
    "startup": [
        {"util": "SystemCheck", "command": "check_all", "params": {"root": None},
         "why": "verify integrity of all core/ files", "order": 1, "on_fail": "report"},
        {"util": "Indexer", "command": "scan_dir", "params": {"path": None},
         "why": "build file/class/method index", "order": 2, "on_fail": "continue"},
        {"util": "VbsScanner", "command": "scan_dir", "params": {"path": None},
         "why": "find VBStyle violations", "order": 3, "on_fail": "report"},
        {"util": "Cleaner", "command": "clean", "params": {"path": None, "dry_run": True},
         "why": "remove build artifacts", "order": 4, "on_fail": "continue"},
    ],
    "error": [
        {"util": "ErrorHandler", "command": "consume", "params": {"result": None},
         "why": "capture and classify error", "order": 1, "on_fail": "escalate"},
        {"util": "ErrorTracker", "command": "match", "params": {"error_text": None},
         "why": "lookup known lessons for this error", "order": 2, "on_fail": "continue"},
        {"util": "ErrorHandler", "command": "get_recovery_policy", "params": {"error_code": None},
         "why": "determine recovery action", "order": 3, "on_fail": "cancel"},
    ],
    "change": [
        {"util": "DomAudit", "command": "drift", "params": {"name": "core_index", "data": None},
         "why": "detect drift from baseline", "order": 1, "on_fail": "report"},
        {"util": "DiffCheck", "command": "compare", "params": {"before": None, "after": None},
         "why": "diff before/after index", "order": 2, "on_fail": "continue"},
        {"util": "StatsReport", "command": "report_dir", "params": {"path": None},
         "why": "regenerate stats report", "order": 3, "on_fail": "continue"},
    ],
    "code_change": [
        {"util": "VbsTest", "command": "vbs_check_folder", "params": {"path": None},
         "why": "verify VBStyle compliance", "order": 1, "on_fail": "report"},
        {"util": "VbsTest", "command": "compile_file", "params": {"path": None},
         "why": "compile check changed files", "order": 2, "on_fail": "report"},
        {"util": "ContentExtract", "command": "extract_file", "params": {"path": None},
         "why": "extract metadata from changed file", "order": 3, "on_fail": "continue"},
    ],
    "db_change": [
        {"util": "PreFlight", "command": "check", "params": {"db_path": None},
         "why": "verify DB integrity", "order": 1, "on_fail": "report"},
    ],
    "scheduled": [
        {"util": "StatsReport", "command": "report_dir", "params": {"path": None},
         "why": "generate periodic stats report", "order": 1, "on_fail": "continue"},
        {"util": "DomAudit", "command": "report", "params": {},
         "why": "audit trail report", "order": 2, "on_fail": "continue"},
        {"util": "ErrorHandler", "command": "get_stats", "params": {},
         "why": "error statistics summary", "order": 3, "on_fail": "continue"},
        {"util": "Backup", "command": "backup_all", "params": {"project": None},
         "why": "full redundancy backup (zip + s3 + email + git)", "order": 10, "on_fail": "report"},
    ],
    "backup": [
        {"util": "Backup", "command": "backup_all", "params": {"project": None},
         "why": "full redundancy backup — zip, s3, email, git push", "order": 1, "on_fail": "report"},
    ],
}

ON_FAIL_ACTIONS = {
    "report": "log failure and include in report",
    "continue": "log failure but continue to next step",
    "escalate": "escalate to higher severity",
    "cancel": "stop pipeline immediately",
}

# ─── SCHEDULES ──────────────────────────────────────────────────────────────
# Config stores the schedules. Orchestrator reads them and runs on timer.
# interval = seconds between runs. 0 = manual only. enabled = on/off.
# [@SCHED]{trigger<startup>interval<0>enabled<true>description<runs once on boot>}
# [@SCHED]{trigger<scheduled>interval<3600>enabled<true>description<hourly stats+backup>}
# [@SCHED]{trigger<backup>interval<86400>enabled<true>description<daily full backup>}
# [@SCHED]{trigger<error>interval<0>enabled<true>description<runs on error event>}
# [@SCHED]{trigger<change>interval<0>enabled<true>description<runs on index change>}
# [@SCHED]{trigger<code_change>interval<0>enabled<true>description<runs on file edit>}
# [@SCHED]{trigger<db_change>interval<0>enabled<true>description<runs on DB change>}

SCHEDULES = {
    "startup": {
        "trigger": "startup",
        "interval": 0,
        "enabled": True,
        "description": "runs once on boot",
        "last_run": 0,
    },
    "scheduled": {
        "trigger": "scheduled",
        "interval": 3600,
        "enabled": True,
        "description": "hourly stats + audit + backup",
        "last_run": 0,
    },
    "backup": {
        "trigger": "backup",
        "interval": 86400,
        "enabled": True,
        "description": "daily full redundancy backup",
        "last_run": 0,
    },
    "error": {
        "trigger": "error",
        "interval": 0,
        "enabled": True,
        "description": "runs on error event (event-driven)",
        "last_run": 0,
    },
    "change": {
        "trigger": "change",
        "interval": 0,
        "enabled": True,
        "description": "runs on index change (event-driven)",
        "last_run": 0,
    },
    "code_change": {
        "trigger": "code_change",
        "interval": 0,
        "enabled": True,
        "description": "runs on file edit (event-driven)",
        "last_run": 0,
    },
    "db_change": {
        "trigger": "db_change",
        "interval": 0,
        "enabled": True,
        "description": "runs on DB change (event-driven)",
        "last_run": 0,
    },
}

# ─── WEB SCRAPER SETTINGS ───────────────────────────────────────────────────

SCRAPER_TIMEOUT = 15
SCRAPER_DELAY = 0.1
SCRAPER_RETRIES = 2
SCRAPER_MAX_WORKERS = 8
SCRAPER_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
SCRAPER_DB_PATH = os.path.join(PROJECT_ROOT, "scraped_data.db")

# Scraping targets — each target defines a site to scrape and how
SCRAPER_TARGETS = {
    "ss64_mac": {
        "base_url": "https://ss64.com/mac/",
        "description": "SS64 macOS command reference",
        "method": "urllib",
        "extract_text": True,
        "extract_links": True,
    },
    "ss64_bash": {
        "base_url": "https://ss64.com/bash/",
        "description": "SS64 Bash command reference",
        "method": "urllib",
        "extract_text": True,
        "extract_links": True,
    },
    "ss64_nt": {
        "base_url": "https://ss64.com/nt/",
        "description": "SS64 Windows command reference",
        "method": "urllib",
        "extract_text": True,
        "extract_links": True,
    },
}

# ─── REPORT CLASS ───────────────────────────────────────────────────────────


class ConfigReport:
    """Report generator for utility build/test results. VBStyle compliant."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "passed": 0,
            "failed": 0,
            "entries": [],
            "summary": "",
        }
        if param:
            for key, value in param.items():
                self.state[key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "add":
            return self.Add(params)
        elif command == "summary":
            return self.Summary(params)
        elif command == "clear":
            return self.Clear(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state[key] = value
        return (1, dict(self.state), None)

    def Add(self, params):
        name = self._p(params, "name")
        ok = self._p(params, "ok", False)
        detail = self._p(params, "detail", "")
        if name is None:
            return (0, None, ("MISSING_PARAM", "name required", 0))
        entry = {"name": name, "ok": ok, "detail": detail}
        self.state["entries"].append(entry)
        if ok:
            self.state["passed"] += 1
        else:
            self.state["failed"] += 1
        return (1, entry, None)

    def Summary(self, params):
        total = self.state["passed"] + self.state["failed"]
        pct = (self.state["passed"] * 100 // total) if total > 0 else 0
        lines = []
        for entry in self.state["entries"]:
            tag = "PASS" if entry["ok"] else "FAIL"
            line = "%s: %s" % (tag, entry["name"])
            if entry["detail"]:
                line += " (%s)" % entry["detail"]
            lines.append(line)
        lines.append("")
        lines.append("Total: %d passed, %d failed, %d%% success" % (self.state["passed"], self.state["failed"], pct))
        result = "\n".join(lines)
        self.state["summary"] = result
        return (1, result, None)

    def Clear(self, params):
        self.state["passed"] = 0
        self.state["failed"] = 0
        self.state["entries"] = []
        self.state["summary"] = ""
        return (1, True, None)
