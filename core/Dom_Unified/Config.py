# [@GHOST]{[@file<Config.py>][@domain<Dom_Unified>][@role<config>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<config>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Config for Dom_Unified — paths, SQLite location, cache settings}
# [@CLASS]{UnifiedConfig}
# [@METHOD]{Run,read_state,set_config,get_path}

"""
Config for Dom_Unified package.
All paths and settings live here — one place to change.
"""

import os
import time
import tempfile

UNIFIED_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(UNIFIED_ROOT))

SQLITE_PATH = os.path.join(UNIFIED_ROOT, "unified_cache.db")
VBAST_BIN = os.path.expanduser("~/bin/vbast")
VBAST_FALLBACK = os.path.join(PROJECT_ROOT, "Cascade_toolStack", "vbast", "vbast")

CACHE_TTL_SECONDS = 3600
AUTO_REPARSE = True
CAPTURE_ERRORS = True

# ============================================================================
# domain_dom_graph — Graph settings + BCL questions for 8-graph pipeline
# ============================================================================

GRAPH_NEO4J_URI = "bolt://localhost:7687"
GRAPH_NEO4J_USER = ""
GRAPH_NEO4J_PASSWORD = ""
GRAPH_STAGING_DB = ":memory:"
GRAPH_MYSQL_HOST = "localhost"
GRAPH_MYSQL_USER = "root"
GRAPH_MYSQL_PORT = 3306
GRAPH_MYSQL_DB_VB = "vb_shared"
GRAPH_MYSQL_DB_BCL = "bcl_ir"
GRAPH_BATCH_SIZE = 500
GRAPH_MAX_WORKERS = 4
GRAPH_MAX_HOPS = 3
GRAPH_LIMIT = 10

GRAPH_TABLE_MAP = {
    "class_graph": {
        "mysql_db": "vb_shared",
        "node_label": "Class",
        "edge_type": "RELATES_TO",
        "source_col": "source_class",
        "target_col": "target_class",
        "rel_col": "relationship",
    },
    "bcl_edges": {
        "mysql_db": "bcl_ir",
        "node_label": "Method",
        "edge_type": "CALLS",
        "source_col": "source_method_id",
        "target_col": "target",
        "rel_col": "edge_type",
        "filter": "WHERE edge_type = 'CALL'",
    },
    "bcl_classes": {
        "mysql_db": "bcl_ir",
        "node_label": "Class",
        "edge_type": None,
        "source_col": "class_name",
    },
    "bcl_methods": {
        "mysql_db": "bcl_ir",
        "node_label": "Method",
        "edge_type": None,
        "source_col": "method_name",
    },
    "graph_nodes": {
        "mysql_db": "vb_shared",
        "node_label": "Token",
        "edge_type": None,
        "source_col": "name",
        "extra_col": "node_type",
    },
    "graph_edges": {
        "mysql_db": "vb_shared",
        "node_label": "Token",
        "edge_type": "CO_OCCURS",
        "source_col": "from_node",
        "target_col": "to_node",
        "rel_col": "edge_type",
    },
    "know_edges": {
        "mysql_db": "vb_shared",
        "node_label": "Token",
        "edge_type": "KNOWS",
        "source_col": "from_node_id",
        "target_col": "to_node_id",
        "rel_col": "relation_type",
    },
}

# Graph questions stored in MySQL vb_shared.graph_config (domain='dom_graph')
# Each question has: section, question_key, bcl_tag, question_text, cypher_query
GRAPH_QUESTIONS_DB = "vb_shared"
GRAPH_QUESTIONS_TABLE = "graph_config"
GRAPH_QUESTIONS_DOMAIN = "dom_graph"

# ============================================================================
# domain_local_agent — MLX agent settings (GPU/RAM/CPU management)
# ============================================================================

AGENT_MSEARCH_BIN = os.path.join(PROJECT_ROOT, "Cascade_toolStack", "Built_tools", "msearch")
AGENT_DEFAULT_MODEL = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
AGENT_MAX_TOOL_TOKENS = 80
AGENT_MAX_ANSWER_TOKENS = 300
AGENT_MAX_STEPS = 4
AGENT_MAX_CONTEXT = 8
AGENT_MSEARCH_MAX_CHARS = 3000
AGENT_MSEARCH_TIMEOUT = 10
AGENT_TEMPERATURE = 0.0
AGENT_MIN_RAM_GB = 1.0
AGENT_MAX_CPU_PERCENT = 90
AGENT_LOCK_FILE = os.path.join(tempfile.gettempdir(), "dom_unified_localagent.lock")

# ============================================================================
# domain_dom_system — DomSystem service lifecycle + resource authority
# Manages MySQL, Neo4j, Qdrant, SQLite as lazy-loaded, refcounted, idle-unloaded
# resources. RAM-budget aware (reuses AGENT_MIN_RAM_GB / AGENT_MAX_CPU_PERCENT).
# ============================================================================

DOM_IDLE_TIMEOUT_SECONDS = 300
DOM_MAX_RESTARTS = 3
DOM_HEALTH_FAILS_BEFORE_RESTART = 2
DOM_STOP_TIMEOUT_SECONDS = 10
DOM_START_WAIT_SECONDS = 15
DOM_HEALTH_CHECK_INTERVAL = 60
DOM_RAM_BUDGET_GB = AGENT_MIN_RAM_GB
DOM_RAM_BUDGET_MB = int(DOM_RAM_BUDGET_GB * 1024)
DOM_RETIRED_PLISTS_DIR = os.path.expanduser("~/.local/share/dom_system/retired_plists")
DOM_LAUNCH_MODE_BREW = "brew"
DOM_LAUNCH_MODE_DIRECT = "direct"
DOM_LAUNCH_MODE_ALWAYS = "always"
DOM_LAUNCH_MODE_LAUNCHD = "launchd"

DOM_SERVICE_MODE_TRANSIENT = "transient"
DOM_SERVICE_MODE_BATCH = "batch"
DOM_SERVICE_MODE_CONSTANT = "constant"
DOM_SERVICE_MODE_PINNED = "pinned"

DOM_SERVICE_MODES = {
    DOM_SERVICE_MODE_TRANSIENT: {"timeout_multiplier": 1, "description": "quick query, normal idle timeout"},
    DOM_SERVICE_MODE_BATCH: {"timeout_multiplier": 6, "description": "batch processing, 6x idle timeout"},
    DOM_SERVICE_MODE_CONSTANT: {"timeout_multiplier": 24, "description": "long-running, 24x idle timeout"},
    DOM_SERVICE_MODE_PINNED: {"timeout_multiplier": 0, "description": "never unload (explicit pin)"},
}

DOM_SERVICES = {
    "qdrant": {
        "name": "Qdrant Vector DB",
        "launch_mode": DOM_LAUNCH_MODE_DIRECT,
        "binary": os.path.expanduser("~/.local/bin/qdrant/qdrant"),
        "args": ["--config-path", os.path.expanduser("~/.local/bin/qdrant/config.yaml")],
        "stop_args": [],
        "pidfile": os.path.expanduser("~/.local/bin/qdrant/qdrant.pid"),
        "logfile": os.path.expanduser("~/.local/bin/qdrant/qdrant.log"),
        "host": "127.0.0.1",
        "port": 6333,
        "health_check": "http",
        "health_url": "http://127.0.0.1:6333/healthz",
        "deps": [],
        "est_ram_mb": 256,
        "est_cpu_percent": 5,
        "uses_gpu": False,
        "uses_io": True,
    },
    "mysql": {
        "name": "MySQL 8.0",
        "launch_mode": DOM_LAUNCH_MODE_DIRECT,
        "binary": "/opt/homebrew/opt/mysql@8.0/bin/mysqld",
        "args": [
            "--basedir=/opt/homebrew/opt/mysql@8.0",
            "--datadir=/opt/homebrew/var/mysql",
            "--plugin-dir=/opt/homebrew/opt/mysql@8.0/lib/plugin",
            "--log-error=/opt/homebrew/var/mysql/nwm.err",
            "--pid-file=/opt/homebrew/var/mysql/nwm.pid",
            "--socket=/tmp/mysql.sock",
        ],
        "stop_args": [],
        "pidfile": "/opt/homebrew/var/mysql/nwm.pid",
        "logfile": "/opt/homebrew/var/mysql/nwm.err",
        "host": "127.0.0.1",
        "port": 3306,
        "health_check": "tcp",
        "deps": [],
        "est_ram_mb": 512,
        "est_cpu_percent": 5,
        "uses_gpu": False,
        "uses_io": True,
    },
    "neo4j": {
        "name": "Neo4j Graph DB",
        "launch_mode": DOM_LAUNCH_MODE_DIRECT,
        "binary": "/opt/homebrew/opt/neo4j/bin/neo4j",
        "args": ["start"],
        "stop_args": ["stop"],
        "pidfile": "/opt/homebrew/var/neo4j/run/neo4j.pid",
        "logfile": "/opt/homebrew/var/neo4j/logs/neo4j.log",
        "host": "127.0.0.1",
        "port": 7474,
        "health_check": "tcp",
        "deps": [],
        "est_ram_mb": 768,
        "est_cpu_percent": 10,
        "uses_gpu": False,
        "uses_io": True,
    },
    "sqlite": {
        "name": "SQLite (file-based)",
        "launch_mode": DOM_LAUNCH_MODE_ALWAYS,
        "binary": "",
        "args": [],
        "stop_args": [],
        "pidfile": "",
        "logfile": "",
        "host": "",
        "port": 0,
        "health_check": "none",
        "deps": [],
        "est_ram_mb": 0,
        "est_cpu_percent": 0,
        "uses_gpu": False,
        "uses_io": True,
    },
    "devin_sync_daemon": {
        "name": "Devin Sync Daemon (SQLite to MySQL)",
        "launch_mode": DOM_LAUNCH_MODE_LAUNCHD,
        "binary": "/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python",
        "args": [os.path.expanduser("~/Downloads/devin_sync_daemon.py"), "--watch"],
        "stop_args": [],
        "plist": os.path.expanduser("~/Library/LaunchAgents/com.wws.devin-sync.plist"),
        "launchd_label": "com.wws.devin-sync",
        "pidfile": "",
        "logfile": "",
        "host": "",
        "port": 0,
        "health_check": "process",
        "process_pattern": "devin_sync_daemon.py",
        "deps": ["mysql"],
        "est_ram_mb": 17,
        "est_cpu_percent": 0,
        "uses_gpu": False,
        "uses_io": True,
    },
    "brain_server": {
        "name": "Brain Server (Node.js Express + SQLite)",
        "launch_mode": DOM_LAUNCH_MODE_DIRECT,
        "binary": "/opt/homebrew/bin/node",
        "args": [os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine/Dom_Graph/brain_server/server.js")],
        "stop_args": [],
        "pidfile": "",
        "logfile": os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine/Dom_Graph/brain_server/brain_server.log"),
        "host": "127.0.0.1",
        "port": 7777,
        "health_check": "http",
        "health_url": "http://127.0.0.1:7777/health",
        "deps": [],
        "est_ram_mb": 50,
        "est_cpu_percent": 1,
        "uses_gpu": False,
        "uses_io": True,
    },
    "kill_weather": {
        "name": "Weather App Killer (replaces infinite-loop script)",
        "launch_mode": DOM_LAUNCH_MODE_DIRECT,
        "binary": "/bin/bash",
        "args": [os.path.expanduser("~/.local/bin/kill_weather_forever.sh")],
        "stop_args": [],
        "pidfile": "",
        "logfile": "",
        "host": "",
        "port": 0,
        "health_check": "process",
        "process_pattern": "kill_weather_forever.sh",
        "deps": [],
        "est_ram_mb": 2,
        "est_cpu_percent": 0,
        "uses_gpu": False,
        "uses_io": False,
    },
    "tame_langserver": {
        "name": "Language Server Tamer (kills runaway language_server_macos_arm)",
        "launch_mode": DOM_LAUNCH_MODE_DIRECT,
        "binary": "/bin/bash",
        "args": ["-c", "pkill -f language_server_macos_arm 2>/dev/null; sleep 1; pkill -9 -f language_server_macos_arm 2>/dev/null; echo done"],
        "stop_args": [],
        "pidfile": "",
        "logfile": "",
        "host": "",
        "port": 0,
        "health_check": "process",
        "process_pattern": "tame_langserver",
        "deps": [],
        "est_ram_mb": 2,
        "est_cpu_percent": 0,
        "uses_gpu": False,
        "uses_io": False,
    },
}

DOM_SERVICE_NAMES = list(DOM_SERVICES.keys())

# ============================================================================
# domain_execution_engine — ExecutionEngine settings
# Closed-loop execution substrate: InRamDb + VB scanner + graph + gate + report
# ============================================================================

EXEC_DB_PATH = ":memory:"
EXEC_OUTPUT_TARGET = "screen"
EXEC_HALT_ON_VIOLATION = True
EXEC_AUTO_REPAIR = True
EXEC_AUDIT_BEFORE_EXECUTE = True
EXEC_GATE_BEFORE_EXECUTE = True
EXEC_REPORT_AFTER_EXECUTE = True
EXEC_MYSQL_HOST = "localhost"
EXEC_MYSQL_USER = "root"
EXEC_MYSQL_PASS = ""
EXEC_MYSQL_DB = "vb_shared"
EXEC_RULES_DOMAIN = "domvbstyle"
EXEC_VIOLATION_STATUS_OPEN = "OPEN"
EXEC_VIOLATION_STATUS_FIXED = "FIXED"
EXEC_MAX_EVENTS = 10000
EXEC_SESSION_ID = str(int(time.time()))

# ============================================================================
# Session Graph — compass for AI sessions
# ============================================================================

SESSION_GRAPH_MYSQL_HOST = "localhost"
SESSION_GRAPH_MYSQL_USER = "root"
SESSION_GRAPH_MYSQL_PASS = ""
SESSION_GRAPH_MYSQL_DB = "vb_shared"
SESSION_GRAPH_DEFAULT_DATE_FORMAT = "%Y-%m-%d"
SESSION_GRAPH_BAR_LENGTH = 40

EXEC_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS exec_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        class_name TEXT,
        method_name TEXT,
        command TEXT,
        file_path TEXT,
        input_params TEXT,
        output_data TEXT,
        state TEXT,
        rule_tag TEXT,
        violation TEXT,
        solution TEXT,
        cause TEXT,
        fix_action TEXT,
        timestamp TEXT NOT NULL,
        session_id TEXT
    )""",
    """CREATE INDEX IF NOT EXISTS idx_exec_type ON exec_events(event_type)""",
    """CREATE INDEX IF NOT EXISTS idx_exec_class ON exec_events(class_name)""",
    """CREATE INDEX IF NOT EXISTS idx_exec_ts ON exec_events(timestamp)""",
    """CREATE INDEX IF NOT EXISTS idx_exec_violation ON exec_events(violation)""",
    """CREATE TABLE IF NOT EXISTS exec_violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_tag TEXT NOT NULL,
        class_name TEXT,
        method_name TEXT,
        file_path TEXT,
        line_number INTEGER,
        violation_text TEXT NOT NULL,
        cause TEXT,
        solution TEXT,
        fix_action TEXT,
        status TEXT NOT NULL DEFAULT 'OPEN',
        created_at TEXT NOT NULL,
        resolved_at TEXT
    )""",
    """CREATE INDEX IF NOT EXISTS idx_viol_rule ON exec_violations(rule_tag)""",
    """CREATE INDEX IF NOT EXISTS idx_viol_status ON exec_violations(status)""",
    """CREATE INDEX IF NOT EXISTS idx_viol_class ON exec_violations(class_name)""",
    """CREATE TABLE IF NOT EXISTS exec_fix_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        violation_id INTEGER NOT NULL,
        attempt_type TEXT NOT NULL,
        result TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (violation_id) REFERENCES exec_violations(id)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_fix_violation ON exec_fix_attempts(violation_id)""",
    """CREATE TABLE IF NOT EXISTS exec_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'RUNNING',
        current_class TEXT,
        current_method TEXT,
        halted_reason TEXT,
        last_event_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS idx_state_session ON exec_state(session_id)""",
    """CREATE INDEX IF NOT EXISTS idx_state_status ON exec_state(status)""",
]

EXEC_DOC = (
    "ExecutionEngine — Deterministic execution substrate with enforced semantic correctness gates.\n"
    "This is NOT a logging system. NOT an agent. NOT a debugger.\n"
    "This is a closed execution loop with enforced truth constraints.\n\n"
    "ARCHITECTURE:\n"
    "    CONFIG (truth definition)\n"
    "           |\n"
    "    InRam SQLite BUS (event bus)\n"
    "           |\n"
    "    GRAPH ENGINE (relation reasoning)\n"
    "           |\n"
    "    VB STYLE SCANNER (rule enforcement)\n"
    "           |\n"
    "    PREEXECUTION GATE (HALT or PASS)\n"
    "           |\n"
    "    EXECUTION (run method)\n"
    "           |\n"
    "    RESULT WRITER (InRamDb)\n"
    "           |\n"
    "    REPORT STREAMER (terminal/db)\n\n"
    "FLOW (no bypass paths):\n"
    "    Run() called -> WriteEvent -> InRamDb -> Graph resolves -> VB Scanner audits ->\n"
    "    PreExecutionGate decides: PASS -> execute -> write result -> report\n"
    "                             FAIL -> halt -> write violation -> report -> return error\n\n"
    "RULES ENFORCED:\n"
    "    [@crashonerr] — ok == 0 -> halt immediately\n"
    "    [@errtrap] — all errors via ErrorCapture full cycle\n"
    "    [@nohardcodedep] — all config from Config.py\n"
    "    [@mustmemunit] — sessions via MemoryObject\n"
    "    [@mustreport] — output via DomReport\n"
    "    [@aisequence] — do what told in sequence\n"
)

# ============================================================================
# domain_voice — TTS (macOS say) + STT (SFSpeechRecognizer) settings
# ============================================================================

VOICE_ENABLED = False
VOICE_NAME = "Samantha"
VOICE_RATE = 180
VOICE_TTS_ENGINE = "say"

STT_ENABLED = False
STT_LANGUAGE = "en-US"
STT_ON_DEVICE = True
STT_BUFFER_SIZE = 4096
STT_SILENCE_TIMEOUT = 2.5
STT_MIN_LISTEN = 1.0
STT_MAX_TIMEOUT = 60
STT_RUNLOOP_INTERVAL = 0.05
STT_SILENCE_THRESHOLD = 0.01  # RMS audio level threshold for speech vs silence

MACOS_VOICES = [
    "Samantha", "Alex", "Daniel", "Karen", "Moira", "Tessa",
    "Fiona", "Veena", "Susan", "Allison", "Ava", "Tom",
    "Lee", "Olivia", "Serena", "Nora", "Rishi", "Aaron",
]


class UnifiedConfig:
    """Config holder for Dom_Unified."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "sqlite_path": SQLITE_PATH,
                "vbast_path": VBAST_BIN if os.path.exists(VBAST_BIN) else VBAST_FALLBACK,
                "cache_ttl": CACHE_TTL_SECONDS,
                "auto_reparse": AUTO_REPARSE,
                "capture_errors": CAPTURE_ERRORS,
                "graph_neo4j_uri": GRAPH_NEO4J_URI,
                "graph_neo4j_user": GRAPH_NEO4J_USER,
                "graph_neo4j_password": GRAPH_NEO4J_PASSWORD,
                "graph_staging_db": GRAPH_STAGING_DB,
                "graph_mysql_host": GRAPH_MYSQL_HOST,
                "graph_mysql_user": GRAPH_MYSQL_USER,
                "graph_mysql_port": GRAPH_MYSQL_PORT,
                "graph_mysql_db_vb": GRAPH_MYSQL_DB_VB,
                "graph_mysql_db_bcl": GRAPH_MYSQL_DB_BCL,
                "graph_batch_size": GRAPH_BATCH_SIZE,
                "graph_max_workers": GRAPH_MAX_WORKERS,
                "graph_max_hops": GRAPH_MAX_HOPS,
                "graph_limit": GRAPH_LIMIT,
                "graph_table_map": GRAPH_TABLE_MAP,
                "graph_questions_db": GRAPH_QUESTIONS_DB,
                "graph_questions_table": GRAPH_QUESTIONS_TABLE,
                "graph_questions_domain": GRAPH_QUESTIONS_DOMAIN,
                "agent_msearch_bin": AGENT_MSEARCH_BIN,
                "agent_default_model": AGENT_DEFAULT_MODEL,
                "agent_max_tool_tokens": AGENT_MAX_TOOL_TOKENS,
                "agent_max_answer_tokens": AGENT_MAX_ANSWER_TOKENS,
                "agent_max_steps": AGENT_MAX_STEPS,
                "agent_max_context": AGENT_MAX_CONTEXT,
                "agent_msearch_max_chars": AGENT_MSEARCH_MAX_CHARS,
                "agent_msearch_timeout": AGENT_MSEARCH_TIMEOUT,
                "agent_temperature": AGENT_TEMPERATURE,
                "agent_min_ram_gb": AGENT_MIN_RAM_GB,
                "agent_max_cpu_percent": AGENT_MAX_CPU_PERCENT,
                "agent_lock_file": AGENT_LOCK_FILE,
                "dom_idle_timeout_seconds": DOM_IDLE_TIMEOUT_SECONDS,
                "dom_max_restarts": DOM_MAX_RESTARTS,
                "dom_health_fails_before_restart": DOM_HEALTH_FAILS_BEFORE_RESTART,
                "dom_stop_timeout_seconds": DOM_STOP_TIMEOUT_SECONDS,
                "dom_start_wait_seconds": DOM_START_WAIT_SECONDS,
                "dom_health_check_interval": DOM_HEALTH_CHECK_INTERVAL,
                "dom_ram_budget_gb": DOM_RAM_BUDGET_GB,
                "dom_ram_budget_mb": DOM_RAM_BUDGET_MB,
                "dom_launch_mode_brew": DOM_LAUNCH_MODE_BREW,
                "dom_launch_mode_direct": DOM_LAUNCH_MODE_DIRECT,
                "dom_launch_mode_always": DOM_LAUNCH_MODE_ALWAYS,
                "dom_launch_mode_launchd": DOM_LAUNCH_MODE_LAUNCHD,
                "dom_retired_plists_dir": DOM_RETIRED_PLISTS_DIR,
                "dom_service_mode_transient": DOM_SERVICE_MODE_TRANSIENT,
                "dom_service_mode_batch": DOM_SERVICE_MODE_BATCH,
                "dom_service_mode_constant": DOM_SERVICE_MODE_CONSTANT,
                "dom_service_mode_pinned": DOM_SERVICE_MODE_PINNED,
                "dom_service_modes": DOM_SERVICE_MODES,
                "dom_services": DOM_SERVICES,
                "dom_service_names": DOM_SERVICE_NAMES,
                "exec_db_path": EXEC_DB_PATH,
                "exec_output_target": EXEC_OUTPUT_TARGET,
                "exec_halt_on_violation": EXEC_HALT_ON_VIOLATION,
                "exec_auto_repair": EXEC_AUTO_REPAIR,
                "exec_audit_before_execute": EXEC_AUDIT_BEFORE_EXECUTE,
                "exec_gate_before_execute": EXEC_GATE_BEFORE_EXECUTE,
                "exec_report_after_execute": EXEC_REPORT_AFTER_EXECUTE,
                "exec_mysql_host": EXEC_MYSQL_HOST,
                "exec_mysql_user": EXEC_MYSQL_USER,
                "exec_mysql_pass": EXEC_MYSQL_PASS,
                "exec_mysql_db": EXEC_MYSQL_DB,
                "exec_rules_domain": EXEC_RULES_DOMAIN,
                "exec_session_id": EXEC_SESSION_ID,
                "exec_schema": EXEC_SCHEMA,
                "exec_doc": EXEC_DOC,
                "session_graph_mysql_host": SESSION_GRAPH_MYSQL_HOST,
                "session_graph_mysql_user": SESSION_GRAPH_MYSQL_USER,
                "session_graph_mysql_pass": SESSION_GRAPH_MYSQL_PASS,
                "session_graph_mysql_db": SESSION_GRAPH_MYSQL_DB,
                "session_graph_default_date_format": SESSION_GRAPH_DEFAULT_DATE_FORMAT,
                "session_graph_bar_length": SESSION_GRAPH_BAR_LENGTH,
                "voice_enabled": VOICE_ENABLED,
                "voice_name": VOICE_NAME,
                "voice_rate": VOICE_RATE,
                "voice_tts_engine": VOICE_TTS_ENGINE,
                "stt_enabled": STT_ENABLED,
                "stt_language": STT_LANGUAGE,
                "stt_on_device": STT_ON_DEVICE,
                "stt_buffer_size": STT_BUFFER_SIZE,
                "stt_silence_timeout": STT_SILENCE_TIMEOUT,
                "stt_min_listen": STT_MIN_LISTEN,
                "stt_max_timeout": STT_MAX_TIMEOUT,
                "stt_runloop_interval": STT_RUNLOOP_INTERVAL,
                "macos_voices": MACOS_VOICES,
            },
            "initialized": True,
        }

    def Run(self, command, params=None):
        if command == "get_path":
            key = params.get("key", "vbast_path") if params else "vbast_path"
            return (1, self.state["config"].get(key), None)
        if command == "set":
            if not params:
                return (0, None, ("ERR_NO_PARAMS", "params required", 0))
            for key, val in params.items():
                if key in self.state["config"]:
                    self.state["config"][key] = val
            return (1, dict(self.state["config"]), None)
        return (0, None, ("ERR_UNKNOWN_CMD", f"Unknown: {command}", 0))

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, values):
        for key, val in values.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)
