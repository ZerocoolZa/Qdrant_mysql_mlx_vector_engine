-- [@GHOST]{file_path="core/Dom_Bloodhound/bloodhound_db_schema.sql" date="2026-07-04" author="Devin" session_id="bloodhound-db" context="Bloodhound DB Schema — Database-backed code storage. All code (C, Python, SQL, etc.) lives in the database as computational units. No loose files. The GUI reconstructs files only when compiling. This is the foundation of the AI-native development environment."}
-- [@VBSTYLE]{standard="VBStyle" version="1" rules="UPPERCASE PascalCase sql-schema"}
-- [@FILEID]{id="bloodhound_db_schema.sql" domain="dom_bloodhound" authority="BloodhoundDB"}
-- [@SUMMARY]{summary="Bloodhound DB Schema — Database-first code storage. Tables: bh_units (computational units), bh_methods, bh_classes, bh_dependencies, bh_observations, bh_errors, bh_history, bh_graphs, bh_embeddings, bh_ai_memory, bh_ai_interactions, bh_events, bh_builds, bh_plugins. All code is data. Files are temporary build artifacts."}

-- Bloodhound DB Schema — Database-First Code Storage
-- Database: bloodhound (MySQL, localhost, root, no password)
--
-- Philosophy: The database IS the source of truth. Not files.
-- Code, metadata, relationships, history, AI reasoning — all first-class data.
-- Files are generated only when compiling.

CREATE DATABASE IF NOT EXISTS bloodhound CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bloodhound;

-- ═══════════════════════════════════════════════════════════
-- COMPUTATIONAL UNITS — The core entity
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_units (
    unit_id         INT AUTO_INCREMENT PRIMARY KEY,
    unit_name       VARCHAR(255) NOT NULL,
    language        VARCHAR(20) NOT NULL DEFAULT 'c',        -- c, cpp, python, sql, etc.
    code            LONGTEXT NOT NULL,                        -- the actual source code
    documentation   TEXT,
    version         INT NOT NULL DEFAULT 1,
    hash            VARCHAR(64) NOT NULL,                     -- SHA-256 of code
    status          ENUM('active','deprecated','draft') DEFAULT 'active',
    complexity      INT DEFAULT 0,                            -- cyclomatic complexity
    trust_score     FLOAT DEFAULT 0.5,                        -- 0.0 to 1.0
    owner           VARCHAR(100),                             -- who created it
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (unit_name),
    INDEX idx_language (language),
    INDEX idx_status (status),
    INDEX idx_hash (hash)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- CLASSES
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_classes (
    class_id        INT AUTO_INCREMENT PRIMARY KEY,
    class_name      VARCHAR(255) NOT NULL,
    unit_id         INT,
    description     TEXT,
    authority       VARCHAR(100),                             -- single authority pattern
    domain          VARCHAR(100),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES bh_units(unit_id) ON DELETE SET NULL,
    INDEX idx_name (class_name)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- METHODS / FUNCTIONS
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_methods (
    method_id       INT AUTO_INCREMENT PRIMARY KEY,
    method_name     VARCHAR(255) NOT NULL,
    class_id        INT,
    unit_id         INT,
    signature       TEXT,                                     -- full function signature
    body            LONGTEXT,                                 -- method body code
    return_type     VARCHAR(100),
    parameters      TEXT,                                     -- JSON array of params
    line_start      INT,
    line_end        INT,
    complexity      INT DEFAULT 0,
    is_async        TINYINT DEFAULT 0,
    is_deterministic TINYINT DEFAULT 0,
    has_branching   TINYINT DEFAULT 0,
    has_loops       TINYINT DEFAULT 0,
    has_recursion   TINYINT DEFAULT 0,
    throws_exceptions TINYINT DEFAULT 0,
    handles_exceptions TINYINT DEFAULT 0,
    ai_explanation  TEXT,                                     -- AI-generated explanation
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES bh_classes(class_id) ON DELETE SET NULL,
    FOREIGN KEY (unit_id) REFERENCES bh_units(unit_id) ON DELETE SET NULL,
    INDEX idx_name (method_name),
    INDEX idx_class (class_id)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- DEPENDENCIES — Call graph edges
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_dependencies (
    dep_id          INT AUTO_INCREMENT PRIMARY KEY,
    source_method_id INT NOT NULL,
    target_method_id INT NOT NULL,
    dep_type        ENUM('calls','imports','uses','reads','writes','inherits','composes') DEFAULT 'calls',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_method_id) REFERENCES bh_methods(method_id) ON DELETE CASCADE,
    FOREIGN KEY (target_method_id) REFERENCES bh_methods(method_id) ON DELETE CASCADE,
    INDEX idx_source (source_method_id),
    INDEX idx_target (target_method_id),
    INDEX idx_type (dep_type)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- OBSERVATIONS — AI learning from runs
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_observations (
    observation_id  INT AUTO_INCREMENT PRIMARY KEY,
    unit_id         INT,
    method_id       INT,
    observation     TEXT NOT NULL,
    observation_type ENUM('performance','bug','pattern','improvement','risk') DEFAULT 'pattern',
    confidence      FLOAT DEFAULT 0.5,
    source          VARCHAR(100),                             -- which AI made this observation
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES bh_units(unit_id) ON DELETE SET NULL,
    FOREIGN KEY (method_id) REFERENCES bh_methods(method_id) ON DELETE SET NULL,
    INDEX idx_unit (unit_id),
    INDEX idx_type (observation_type)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- ERRORS — Known errors per unit/method
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_errors (
    error_id        INT AUTO_INCREMENT PRIMARY KEY,
    unit_id         INT,
    method_id       INT,
    error_type      VARCHAR(100),
    error_message   TEXT,
    severity        ENUM('info','warning','error','critical') DEFAULT 'error',
    status          ENUM('open','fixed','ignored') DEFAULT 'open',
    ai_suggestion   TEXT,                                     -- AI suggested fix
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fixed_at        TIMESTAMP NULL,
    FOREIGN KEY (unit_id) REFERENCES bh_units(unit_id) ON DELETE SET NULL,
    FOREIGN KEY (method_id) REFERENCES bh_methods(method_id) ON DELETE SET NULL,
    INDEX idx_unit (unit_id),
    INDEX idx_severity (severity),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- HISTORY — Version history of every unit
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_history (
    history_id      INT AUTO_INCREMENT PRIMARY KEY,
    unit_id         INT NOT NULL,
    version         INT NOT NULL,
    code            LONGTEXT NOT NULL,
    hash            VARCHAR(64) NOT NULL,
    change_summary  TEXT,
    changed_by      VARCHAR(100),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES bh_units(unit_id) ON DELETE CASCADE,
    INDEX idx_unit_version (unit_id, version)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- EMBEDDINGS — Vector embeddings for semantic search
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_embeddings (
    embedding_id    INT AUTO_INCREMENT PRIMARY KEY,
    unit_id         INT,
    method_id       INT,
    embedding       BLOB,                                     -- vector embedding
    embedding_model VARCHAR(100),                             -- which model generated it
    dimensions      INT DEFAULT 384,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES bh_units(unit_id) ON DELETE SET NULL,
    FOREIGN KEY (method_id) REFERENCES bh_methods(method_id) ON DELETE SET NULL,
    INDEX idx_unit (unit_id)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- AI MEMORY — Every AI interaction stored forever
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_ai_memory (
    memory_id       INT AUTO_INCREMENT PRIMARY KEY,
    agent_name      VARCHAR(50) NOT NULL,                     -- devin, claude, gpt, gemini, cascade, local
    agent_type      ENUM('mcp','api','local','cascade') DEFAULT 'mcp',
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    confidence      FLOAT DEFAULT 0.5,
    context         TEXT,                                     -- what was the context
    unit_id         INT,
    method_id       INT,
    outcome         ENUM('success','partial','failed','pending') DEFAULT 'pending',
    tokens_used     INT DEFAULT 0,
    latency_ms      INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES bh_units(unit_id) ON DELETE SET NULL,
    FOREIGN KEY (method_id) REFERENCES bh_methods(method_id) ON DELETE SET NULL,
    INDEX idx_agent (agent_name),
    INDEX idx_outcome (outcome),
    INDEX idx_created (created_at)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- AI AGENTS — Registered AI agents (MCP connections)
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_ai_agents (
    agent_id        INT AUTO_INCREMENT PRIMARY KEY,
    agent_name      VARCHAR(50) NOT NULL UNIQUE,              -- devin, claude, gpt, gemini
    agent_type      ENUM('mcp','api','local','cascade') DEFAULT 'mcp',
    endpoint        VARCHAR(255),                             -- MCP server URL or API endpoint
    api_key         VARCHAR(255),                             -- encrypted
    model           VARCHAR(100),                             -- model name
    capabilities    TEXT,                                     -- JSON array: ["code","explain","fix","test"]
    is_active       TINYINT DEFAULT 1,
    total_calls     INT DEFAULT 0,
    success_count   INT DEFAULT 0,
    avg_confidence  FLOAT DEFAULT 0.5,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used       TIMESTAMP NULL,
    INDEX idx_active (is_active)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- EVENTS — EventBus persistent log
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_events (
    event_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id          INT NOT NULL,
    timestamp_ns    BIGINT NOT NULL,
    kind            SMALLINT NOT NULL,
    severity        SMALLINT DEFAULT 0,
    source          VARCHAR(100),
    phase           VARCHAR(100),
    entity          VARCHAR(255),
    name            VARCHAR(255),
    value           TEXT,
    parent_id       BIGINT,
    source_line     INT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run (run_id),
    INDEX idx_kind (kind),
    INDEX idx_source (source),
    INDEX idx_timestamp (timestamp_ns)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- BUILDS — Build history
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_builds (
    build_id        INT AUTO_INCREMENT PRIMARY KEY,
    build_command   TEXT NOT NULL,
    status          ENUM('pending','running','success','failed') DEFAULT 'pending',
    exit_code       INT,
    stdout          LONGTEXT,
    stderr          LONGTEXT,
    duration_ms     INT,
    units_built     INT DEFAULT 0,
    ai_review       TEXT,                                     -- AI review of build
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- PLUGINS — Registered plugins
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_plugins (
    plugin_id       INT AUTO_INCREMENT PRIMARY KEY,
    plugin_name     VARCHAR(100) NOT NULL UNIQUE,
    plugin_type     ENUM('compiler','language','debugger','profiler','ai','graph','viewer','tool') DEFAULT 'tool',
    version         VARCHAR(20),
    is_active       TINYINT DEFAULT 1,
    config          TEXT,                                     -- JSON config
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type (plugin_type),
    INDEX idx_active (is_active)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- RUNS — Execution runs
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bh_runs (
    run_id          INT AUTO_INCREMENT PRIMARY KEY,
    build_id        INT,
    status          ENUM('pending','running','completed','failed','aborted') DEFAULT 'pending',
    event_count     INT DEFAULT 0,
    error_count     INT DEFAULT 0,
    duration_ms     INT,
    started_at      TIMESTAMP NULL,
    completed_at    TIMESTAMP NULL,
    FOREIGN KEY (build_id) REFERENCES bh_builds(build_id) ON DELETE SET NULL,
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════
-- SEED DATA — Register AI agents
-- ═══════════════════════════════════════════════════════════

INSERT IGNORE INTO bh_ai_agents (agent_name, agent_type, endpoint, model, capabilities, is_active) VALUES
('Devin',    'mcp', 'http://localhost:8080', 'devin-glm-5.2', '["code","explain","fix","test","debug","refactor"]', 1),
('Claude',   'mcp', 'http://localhost:8081', 'claude-sonnet-4', '["code","explain","fix","analyze","document"]', 1),
('GPT',      'mcp', 'http://localhost:8082', 'gpt-4o', '["code","explain","fix","test","generate"]', 1),
('Gemini',   'mcp', 'http://localhost:8083', 'gemini-2.5-flash', '["code","explain","search","summarize"]', 1),
('Cascade',  'cascade', 'local', 'cascade-planner', '["plan","orchestrate","delegate"]', 1),
('Local-LLM','local', 'mlx://localhost', 'mlx-community/Phi-3', '["code","explain","fix"]', 0);

-- ═══════════════════════════════════════════════════════════
-- SEED DATA — Register plugins
-- ═══════════════════════════════════════════════════════════

INSERT IGNORE INTO bh_plugins (plugin_name, plugin_type, version, is_active) VALUES
('C Compiler',      'compiler', '1.0', 1),
('Python Runtime',  'language', '3.13', 1),
('EventBus Debug',  'debugger', '1.0', 1),
('ImPlot Profiler', 'profiler', '1.0', 1),
('ImNodes Graph',   'graph',    '1.0', 1),
('Devin MCP',       'ai',       '1.0', 1),
('Claude MCP',      'ai',       '1.0', 1),
('SQLite Viewer',   'viewer',   '1.0', 1);

-- ═══════════════════════════════════════════════════════════
-- VIEWS — Common queries
-- ═══════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_unit_summary AS
SELECT
    u.unit_id, u.unit_name, u.language, u.status, u.complexity, u.trust_score,
    COUNT(DISTINCT m.method_id) AS method_count,
    COUNT(DISTINCT e.error_id) AS open_errors,
    COUNT(DISTINCT o.observation_id) AS observations,
    u.updated_at
FROM bh_units u
LEFT JOIN bh_methods m ON m.unit_id = u.unit_id
LEFT JOIN bh_errors e ON e.unit_id = u.unit_id AND e.status = 'open'
LEFT JOIN bh_observations o ON o.unit_id = u.unit_id
GROUP BY u.unit_id;

CREATE OR REPLACE VIEW v_call_graph AS
SELECT
    sm.method_name AS source_method,
    tm.method_name AS target_method,
    d.dep_type
FROM bh_dependencies d
JOIN bh_methods sm ON d.source_method_id = sm.method_id
JOIN bh_methods tm ON d.target_method_id = tm.method_id;

CREATE OR REPLACE VIEW v_ai_stats AS
SELECT
    agent_name,
    COUNT(*) AS total_interactions,
    SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS successes,
    AVG(confidence) AS avg_confidence,
    AVG(latency_ms) AS avg_latency,
    MAX(created_at) AS last_used
FROM bh_ai_memory
GROUP BY agent_name;
