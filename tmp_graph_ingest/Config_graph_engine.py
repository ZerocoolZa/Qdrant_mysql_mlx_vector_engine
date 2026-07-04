# [@GHOST]
# Ghost header — Config_graph_engine
# Purpose: All paths, constants, schema, GUI settings for graph engine domain
# Pattern: BookSystem/config.py gold standard
# [@VBSTYLE]
# VBStyle: Config class, class attributes only, no Run(), no Tuple3
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @tabs(25), @whitespace(26), @enums(21), @hidden(23), @auth(52), @rpt(54)

import os

class ConfigGraphEngine:
    """All configuration for the graph engine domain. Single source of truth."""

    # === PATHS ===
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "graph_engine_dev.db")
    TMP_DIR = os.path.join(BASE_DIR, "runs")
    SPEC_PATH = os.path.join(BASE_DIR, "SPEC.md")

    # Env override
    if os.environ.get("GRAPH_ENGINE_DB"):
        DB_PATH = os.environ.get("GRAPH_ENGINE_DB")

    # === DOMAIN ===
    DOMAIN = "graph_engine"

    # === LIMITS ===
    MAX_RETRY = 3
    MAX_STEPS = 50
    PRUNE_THRESHOLD = 0.1
    PROMOTE_THRESHOLD = 3
    STALE_RUN_TIMEOUT_SECONDS = 3600

    # === CASCADE STAGES ===
    STAGES = [
        "plan",
        "spec",
        "flow",
        "lifecycle",
        "dependency",
        "error",
        "orchestration",
        "gap",
    ]

    STAGE_QUESTIONS = {
        "plan": "What are we building?",
        "spec": "What exactly exists?",
        "flow": "How does it move?",
        "lifecycle": "When does it run?",
        "dependency": "Why does it connect?",
        "error": "Where does it fail?",
        "orchestration": "Who calls who?",
        "gap": "What is missing?",
    }

    STAGE_VERDICTS = ("pass", "fail", "rewrite", "unknown")

    # === RUN STATES ===
    RUN_STATES = ("running", "paused", "completed", "failed", "blocked", "passed", "timeout")

    # === NODE TYPES ===
    NODE_TYPES = ("question", "action", "check", "fallback", "cascade_stage")

    # === GUI ===
    GUI_WINDOW = {"width": 1200, "height": 800, "title": "Graph Engine"}
    GUI_BG = "#1e1e2e"
    GUI_FG = "#cdd6f4"
    GUI_ACCENT = "#89b4fa"

    COLORS = {
        "node_default": "#89b4fa",
        "node_action": "#a6e3a1",
        "node_check": "#f9e2af",
        "node_fallback": "#f38ba8",
        "node_question": "#cba6f7",
        "edge_default": "#6c7086",
        "edge_success": "#a6e3a1",
        "edge_fail": "#f38ba8",
        "edge_highlight": "#f9e2af",
        "background": "#1e1e2e",
        "text": "#cdd6f4",
    }

    # === SCHEMA SQL ===
    SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cascade_runs (
    run_id TEXT PRIMARY KEY,
    idea TEXT,
    spec_path TEXT,
    current_stage TEXT,
    status TEXT DEFAULT 'running',
    loop_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cascade_stage_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    stage TEXT,
    graph_snapshot TEXT,
    verdict TEXT,
    issues TEXT,
    issue_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES cascade_runs(run_id)
);

CREATE TABLE IF NOT EXISTS cascade_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT,
    rule_text TEXT,
    violation_action TEXT,
    severity INTEGER DEFAULT 1,
    query_template TEXT
);

CREATE TABLE IF NOT EXISTS decision_nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT,
    name TEXT,
    node_type TEXT,
    payload TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decision_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node INTEGER,
    to_node INTEGER,
    condition TEXT,
    weight REAL DEFAULT 1.0,
    FOREIGN KEY(from_node) REFERENCES decision_nodes(node_id),
    FOREIGN KEY(to_node) REFERENCES decision_nodes(node_id)
);

CREATE TABLE IF NOT EXISTS execution_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    node_id INTEGER,
    status TEXT,
    output TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(node_id) REFERENCES decision_nodes(node_id)
);

CREATE TABLE IF NOT EXISTS run_state (
    run_id TEXT PRIMARY KEY,
    current_node INTEGER,
    state TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(current_node) REFERENCES decision_nodes(node_id)
);

CREATE TABLE IF NOT EXISTS run_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    domain TEXT,
    total_nodes INTEGER,
    nodes_executed INTEGER,
    nodes_failed INTEGER,
    fallbacks_created INTEGER,
    duration_seconds REAL,
    success INTEGER,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

    # === ERROR MESSAGES ===
    ERRORS = {
        "cascade_not_passed": "cascade_not_passed: run CascadeEngine.Run('validate') first",
        "cascade_blocked": "cascade_blocked: {stage} stage failed",
        "max_retry_exceeded": "max_retry_exceeded: pipeline loop limit reached",
        "max_steps_exceeded": "max_steps_exceeded: auto-run step limit reached",
        "bcl_token_not_found": "bcl_token_not_found: {payload}",
        "current_node_deleted": "current_node_deleted: run state points to removed node",
        "permission_denied": "permission_denied: AmIAllowed check failed",
        "tkinter_unavailable": "tkinter_unavailable: headless mode",
        "terminal_node": "terminal_node: no outgoing edges, run completed",
        "dedup_skipped": "dedup_skipped: fallback node already exists",
    }

    # === STATUS MESSAGES ===
    STATUS = {
        "cascade_started": "Cascade run started",
        "cascade_passed": "All 8 stages passed — ready for code",
        "cascade_failed": "Cascade run blocked — see stage results",
        "degs_started": "DEGS run started",
        "degs_completed": "DEGS run completed",
        "degs_paused": "DEGS run paused",
        "ingest_done": "Ingestion complete",
        "verify_passed": "Verification passed",
        "verify_failed": "Verification failed",
    }

    # === ABOUT ===
    ABOUT = "Graph Engine Domain — unified graph code reasoning system. Cascade validates, GraphEngine executes, DEGS evolves."

    # === GETTERS ===
    @classmethod
    def GetDbPath(cls):
        return cls.DB_PATH

    @classmethod
    def GetTmpDir(cls):
        return cls.TMP_DIR

    @classmethod
    def GetStages(cls):
        return cls.STAGES

    @classmethod
    def GetSchemaSql(cls):
        return cls.SCHEMA_SQL

    @classmethod
    def GetError(cls, key, **kwargs):
        msg = cls.ERRORS.get(key, key)
        if kwargs:
            return msg.format(**kwargs)
        return msg


cfg = ConfigGraphEngine()
