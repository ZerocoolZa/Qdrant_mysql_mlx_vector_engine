#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/Config.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Project Digital Twin Config -- schema DDL and constants for all 75 sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="Config.py" domain="twin_config" authority="Config"}
# [@SUMMARY]{summary="Configuration and schema DDL for the Project Digital Twin system. All table definitions, indexes, views, and constants."}
# [@CLASS]{class="Config" domain="config" authority="single"}
# [@METHOD]{method="GetSchema" type="command"}
# [@METHOD]{method="GetViews" type="command"}
# [@METHOD]{method="GetIndexes" type="command"}
# [@METHOD]{method="GetConstants" type="command"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_NAME = "dom_graph_twin.db"
DEFAULT_DB_PATH = os.path.join(BASE_DIR, DEFAULT_DB_NAME)

VERSION = "1.0"
SESSION_ID = "twin-rewrite"

EXPECTED_TABLES = [
    "files",
    "classes",
    "methods",
    "edges",
    "knowledge",
    "snapshots",
    "attempts",
    "observations",
]

SCHEMA_SQL = """
-- Section 6: FILES table
CREATE TABLE IF NOT EXISTS files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    path TEXT NOT NULL,
    extension TEXT,
    hash TEXT,
    bcl TEXT,
    size INTEGER,
    imports TEXT,
    exports TEXT,
    class_count INTEGER,
    function_count INTEGER,
    method_count INTEGER,
    dependencies TEXT,
    created TEXT,
    modified TEXT,
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',
    encoding TEXT,
    language TEXT
);

-- Section 7: CLASS SPLIT table
CREATE TABLE IF NOT EXISTS classes (
    class_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER REFERENCES files(file_id),
    class_name TEXT NOT NULL,
    parent TEXT,
    interfaces TEXT,
    bcl TEXT,
    start_line INTEGER,
    end_line INTEGER,
    method_count INTEGER,
    properties TEXT,
    fields TEXT,
    dependencies TEXT,
    relationships TEXT,
    is_vbstyle INTEGER DEFAULT 0,
    has_run_method INTEGER DEFAULT 0,
    has_tuple3 INTEGER DEFAULT 0,
    cyclomatic_complexity REAL DEFAULT 0,
    hash TEXT,
    version INTEGER DEFAULT 1
);

-- Section 8: METHOD SPLIT table
CREATE TABLE IF NOT EXISTS methods (
    method_id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER REFERENCES classes(class_id),
    file_id INTEGER REFERENCES files(file_id),
    method_name TEXT NOT NULL,
    bcl TEXT,
    signature TEXT,
    parameters TEXT,
    return_type TEXT,
    visibility TEXT,
    start_line INTEGER,
    end_line INTEGER,
    method_code TEXT,
    cyclomatic_complexity REAL DEFAULT 0,
    dependencies TEXT,
    calls TEXT,
    called_by TEXT,
    is_dunder INTEGER DEFAULT 0,
    is_vbstyle INTEGER DEFAULT 0,
    returns_tuple3 INTEGER DEFAULT 0,
    has_print INTEGER DEFAULT 0,
    has_decorator INTEGER DEFAULT 0,
    has_self_underscore INTEGER DEFAULT 0,
    line_count INTEGER,
    hash TEXT,
    version INTEGER DEFAULT 1
);

-- Section 4.24: EDGES table (store entire graph)
CREATE TABLE IF NOT EXISTS edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_type TEXT NOT NULL,
    src_id INTEGER NOT NULL,
    dst_type TEXT NOT NULL,
    dst_id INTEGER NOT NULL,
    edge_type TEXT NOT NULL,
    evidence TEXT,
    confidence REAL DEFAULT 100.0,
    created TEXT
);

-- Section 3: ERROR KNOWLEDGE table (all 20 sub-sections)
-- 3.1 error table, 3.2 fix table, 3.3 failed attempt, 3.4 success
-- 3.5 stack trace, 3.6 exception type, 3.7 file, 3.8 class, 3.9 method
-- 3.10 line number, 3.11 variables, 3.12 inputs, 3.13 outputs
-- 3.14 root cause, 3.15 human fix, 3.16 AI fix, 3.17 confidence
-- 3.18 similar errors, 3.19 resolution time, 3.20 learn from previous
CREATE TABLE IF NOT EXISTS knowledge (
    knowledge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem TEXT NOT NULL,
    question TEXT,
    answer TEXT,
    is_best INTEGER DEFAULT 0,
    evidence TEXT,
    confidence INTEGER DEFAULT 0,
    file_id INTEGER REFERENCES files(file_id),
    class_id INTEGER REFERENCES classes(class_id),
    method_id INTEGER REFERENCES methods(method_id),
    error_type TEXT,
    error_text TEXT,
    stack_trace TEXT,
    fix_applied TEXT,
    fix_result TEXT,
    resolution_time_ms INTEGER,
    line_number INTEGER,
    variables TEXT,
    inputs TEXT,
    outputs TEXT,
    root_cause TEXT,
    human_fix TEXT,
    ai_fix TEXT,
    graph_changes TEXT,
    created TEXT,
    tags TEXT
);

-- Section 18: VERSION SNAPSHOTS table
-- 18.1 before fix, 18.2 after fix, 18.3 auto restore point
-- 18.4 branch experiments, 18.5 compare, 18.6 restore, 18.7 notes, 18.8 timeline
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_type TEXT NOT NULL,
    file_id INTEGER REFERENCES files(file_id),
    class_id INTEGER REFERENCES classes(class_id),
    method_id INTEGER REFERENCES methods(method_id),
    content TEXT NOT NULL,
    hash TEXT NOT NULL,
    created TEXT,
    notes TEXT
);

-- Section 12: FIX ENGINE attempts table
-- 12.1 find error, 12.2 search similar, 12.3 rank fixes, 12.4 apply candidate
-- 12.5 compile, 12.6 run tests, 12.7 compare output, 12.8 rollback if failed
-- 12.9 record outcome, 12.10 learn result
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    method_id INTEGER REFERENCES methods(method_id),
    action TEXT,
    before_code TEXT,
    after_code TEXT,
    compile_result INTEGER,
    test_result INTEGER,
    error_text TEXT,
    rollback INTEGER DEFAULT 0,
    knowledge_id INTEGER REFERENCES knowledge(knowledge_id),
    created TEXT
);

-- Section 53: OBSERVATION ENGINE table
-- 53.1 everything seen, 53.2 everything changed, 53.3 everything learned
-- 53.4 everything ignored, 53.5 unknowns, 53.6 assumptions
-- 53.7 confirmed facts, 53.8 evidence links
CREATE TABLE IF NOT EXISTS observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_type TEXT NOT NULL,
    subject TEXT,
    evidence TEXT,
    confidence REAL DEFAULT 50.0,
    file_id INTEGER REFERENCES files(file_id),
    class_id INTEGER REFERENCES classes(class_id),
    method_id INTEGER REFERENCES methods(method_id),
    created TEXT
);

-- Section 17: PROJECT FINGERPRINTING table
CREATE TABLE IF NOT EXISTS fingerprints (
    fingerprint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint_type TEXT NOT NULL,
    target_id INTEGER,
    hash TEXT NOT NULL,
    created TEXT
);

-- Section 36: COMPILER KNOWLEDGE table
CREATE TABLE IF NOT EXISTS compiler_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_type TEXT NOT NULL,
    message TEXT,
    file_id INTEGER REFERENCES files(file_id),
    build_time_ms INTEGER,
    compiler_version TEXT,
    created TEXT
);

-- Section 37: RUNTIME KNOWLEDGE table
CREATE TABLE IF NOT EXISTS runtime_log (
    runtime_id INTEGER PRIMARY KEY AUTOINCREMENT,
    runtime_type TEXT NOT NULL,
    subject TEXT,
    detail TEXT,
    created TEXT
);

-- Section 39: SQL ANALYZER table
CREATE TABLE IF NOT EXISTS sql_log (
    sql_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    query_plan TEXT,
    execution_ms INTEGER,
    rows_returned INTEGER,
    created TEXT
);

-- Section 41: SOURCE EVOLUTION table
CREATE TABLE IF NOT EXISTS evolution_log (
    evolution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evolution_type TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    description TEXT,
    created TEXT
);

-- Section 42: CALL PATH DATABASE table
CREATE TABLE IF NOT EXISTS call_paths (
    call_path_id INTEGER PRIMARY KEY AUTOINCREMENT,
    method_id INTEGER REFERENCES methods(method_id),
    path_type TEXT NOT NULL,
    path_data TEXT,
    created TEXT
);

-- Section 50: TEST KNOWLEDGE table
CREATE TABLE IF NOT EXISTS test_log (
    test_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_type TEXT NOT NULL,
    test_name TEXT,
    result TEXT,
    error_text TEXT,
    duration_ms INTEGER,
    created TEXT
);

-- Section 51: API KNOWLEDGE table
CREATE TABLE IF NOT EXISTS api_log (
    api_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT,
    method TEXT,
    parameters TEXT,
    response_code INTEGER,
    response_body TEXT,
    created TEXT
);

-- Section 52: CONFIGURATION ENGINE table
CREATE TABLE IF NOT EXISTS config_log (
    config_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_type TEXT NOT NULL,
    key TEXT,
    value TEXT,
    source TEXT,
    created TEXT
);

-- Section 38: MEMORY FORENSICS table
CREATE TABLE IF NOT EXISTS memory_log (
    memory_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_type TEXT NOT NULL,
    detail TEXT,
    size_bytes INTEGER,
    created TEXT
);

-- Section 40: FILE FORENSICS table
CREATE TABLE IF NOT EXISTS file_forensics (
    forensic_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER REFERENCES files(file_id),
    action TEXT NOT NULL,
    old_path TEXT,
    new_path TEXT,
    old_hash TEXT,
    new_hash TEXT,
    created TEXT
);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_files_name ON files(file_name);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash);
CREATE INDEX IF NOT EXISTS idx_classes_file ON classes(file_id);
CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(class_name);
CREATE INDEX IF NOT EXISTS idx_classes_hash ON classes(hash);
CREATE INDEX IF NOT EXISTS idx_methods_class ON methods(class_id);
CREATE INDEX IF NOT EXISTS idx_methods_file ON methods(file_id);
CREATE INDEX IF NOT EXISTS idx_methods_name ON methods(method_name);
CREATE INDEX IF NOT EXISTS idx_methods_hash ON methods(hash);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_type, src_id);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_type, dst_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_problem ON knowledge(problem);
CREATE INDEX IF NOT EXISTS idx_knowledge_error_type ON knowledge(error_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_confidence ON knowledge(confidence);
CREATE INDEX IF NOT EXISTS idx_snapshots_type ON snapshots(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_snapshots_method ON snapshots(method_id);
CREATE INDEX IF NOT EXISTS idx_attempts_method ON attempts(method_id);
CREATE INDEX IF NOT EXISTS idx_attempts_knowledge ON attempts(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_observations_type ON observations(observation_type);
CREATE INDEX IF NOT EXISTS idx_observations_method ON observations(method_id);
"""

VIEWS_SQL = """
-- Section 35: PROJECT DIGITAL TWIN views
CREATE VIEW IF NOT EXISTS v_file_summary AS
SELECT f.file_id, f.file_name, f.path, f.extension, f.hash,
       COUNT(DISTINCT c.class_id) AS class_count,
       COUNT(DISTINCT m.method_id) AS method_count
FROM files f
LEFT JOIN classes c ON c.file_id = f.file_id
LEFT JOIN methods m ON m.file_id = f.file_id
GROUP BY f.file_id;

CREATE VIEW IF NOT EXISTS v_class_summary AS
SELECT c.class_id, c.class_name, c.parent, c.file_id, f.file_name,
       COUNT(DISTINCT m.method_id) AS method_count,
       c.is_vbstyle, c.has_run_method, c.has_tuple3
FROM classes c
LEFT JOIN methods m ON m.class_id = c.class_id
LEFT JOIN files f ON f.file_id = c.file_id
GROUP BY c.class_id;

CREATE VIEW IF NOT EXISTS v_method_summary AS
SELECT m.method_id, m.method_name, m.class_id, c.class_name,
       m.signature, m.cyclomatic_complexity, m.is_vbstyle,
       m.returns_tuple3, m.has_print, m.has_decorator, m.has_self_underscore
FROM methods m
LEFT JOIN classes c ON c.class_id = m.class_id;

CREATE VIEW IF NOT EXISTS v_edge_summary AS
SELECT e.edge_type, COUNT(*) AS edge_count
FROM edges e
GROUP BY e.edge_type;

CREATE VIEW IF NOT EXISTS v_knowledge_summary AS
SELECT k.knowledge_id, k.problem, k.error_type, k.confidence,
       k.fix_result, k.resolution_time_ms, k.root_cause
FROM knowledge k;

CREATE VIEW IF NOT EXISTS v_dead_methods AS
SELECT m.method_id, m.method_name, c.class_name
FROM methods m
LEFT JOIN classes c ON c.class_id = m.class_id
WHERE m.method_id NOT IN (
    SELECT dst_id FROM edges WHERE dst_type = 'method' AND edge_type = 'calls'
);

CREATE VIEW IF NOT EXISTS v_orphan_classes AS
SELECT c.class_id, c.class_name
FROM classes c
WHERE c.class_id NOT IN (
    SELECT src_id FROM edges WHERE src_type = 'class'
) AND c.class_id NOT IN (
    SELECT dst_id FROM edges WHERE dst_type = 'class'
);

CREATE VIEW IF NOT EXISTS v_hotspots AS
SELECT m.method_id, m.method_name, c.class_name,
       m.cyclomatic_complexity,
       COUNT(e.edge_id) AS incoming_calls
FROM methods m
LEFT JOIN classes c ON c.class_id = m.class_id
LEFT JOIN edges e ON e.dst_type = 'method' AND e.dst_id = m.method_id
    AND e.edge_type = 'calls'
GROUP BY m.method_id
HAVING m.cyclomatic_complexity >= 10 AND incoming_calls >= 3
ORDER BY m.cyclomatic_complexity DESC;

CREATE VIEW IF NOT EXISTS v_vbstyle_violations AS
SELECT m.method_id, m.method_name, c.class_name, f.file_name,
       m.has_print, m.has_decorator, m.has_self_underscore,
       m.returns_tuple3, m.is_vbstyle
FROM methods m
LEFT JOIN classes c ON c.class_id = m.class_id
LEFT JOIN files f ON f.file_id = m.file_id
WHERE m.has_print = 1 OR m.has_decorator = 1
    OR m.has_self_underscore = 1 OR m.returns_tuple3 = 0;

CREATE VIEW IF NOT EXISTS v_duplicate_methods AS
SELECT hash, COUNT(*) AS dup_count, GROUP_CONCAT(method_name) AS method_names
FROM methods
WHERE hash IS NOT NULL
GROUP BY hash
HAVING COUNT(*) > 1;

CREATE VIEW IF NOT EXISTS v_snapshot_timeline AS
SELECT s.snapshot_id, s.snapshot_type, s.created, s.notes,
       f.file_name, c.class_name, m.method_name
FROM snapshots s
LEFT JOIN files f ON f.file_id = s.file_id
LEFT JOIN classes c ON c.class_id = s.class_id
LEFT JOIN methods m ON m.method_id = s.method_id
ORDER BY s.created DESC;
"""

FTS_SQL = """
-- Section 20: SEMANTIC SEARCH FTS5
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    problem, question, answer, error_type,
    content='knowledge', content_rowid='knowledge_id'
);
"""


class Config:
    """Configuration authority for the Project Digital Twin system."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "base_dir": BASE_DIR,
                "db_path": DEFAULT_DB_PATH,
                "version": VERSION,
                "session_id": SESSION_ID,
                "expected_tables": list(EXPECTED_TABLES),
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "get_schema":
            return self.GetSchema(params)
        elif command == "get_views":
            return self.GetViews(params)
        elif command == "get_indexes":
            return self.GetIndexes(params)
        elif command == "get_constants":
            return self.GetConstants(params)
        elif command == "get_fts":
            return (1, FTS_SQL, None)
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
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def GetSchema(self, params):
        return (1, SCHEMA_SQL, None)

    def GetViews(self, params):
        return (1, VIEWS_SQL, None)

    def GetIndexes(self, params):
        return (1, INDEXES_SQL, None)

    def GetConstants(self, params):
        constants = {
            "BASE_DIR": BASE_DIR,
            "DEFAULT_DB_NAME": DEFAULT_DB_NAME,
            "DEFAULT_DB_PATH": DEFAULT_DB_PATH,
            "VERSION": VERSION,
            "SESSION_ID": SESSION_ID,
            "EXPECTED_TABLES": list(EXPECTED_TABLES),
        }
        return (1, constants, None)


cfg = Config()
