-- [@GHOST]{file_path="core/Dom_Bcl/python_structure_schema.sql";"identity=python_structure_schema.sql";"purpose=MySQL schema for multi-layer BCL IR storage";"date=2026-06-28";"version=1.0";"author=Cascade";"chat_link=")}
-- [@VBSTYLE]{[@Pass]{"CONFIG";"Tuple3";"report()";"Run()";"self.state";"PascalCase";"UPPERCASE";"spaces"}[@Fail]{"print";"decorators";"hardcoded";"self._";"tabs";"trailing_whitespace"}[@Unsure]{""}}
-- [@FILEID]{("session_id=auto";"context=MySQL schema for BCL IR graph storage";"purpose=Multi-layer code structure")}
-- [@SUMMARY]{("Created on 2026-06-28";"auto_stamped=true")}

-- ============================================================================
-- PYTHON STRUCTURE — Multi-Layer BCL IR Storage (DB-First Identity)
-- ============================================================================
-- 8 dimensions per code object:
--   1. ID           — stable hash-based identity (survives renames, moves)
--   2. BCL          — human-readable BCL header ([@FILE], [@CLASS], [@METHOD])
--   3. BCL_IR       — machine IR blocks ([@IRNODE]...[@ENDNODE])
--   4. GRAPH        — parent/child + call/inherit edges (by ID, not name)
--   5. CODE         — source snippet (optional, for reconstruction)
--   6. DESCRIPTION  — AI-generated semantic description
--   7. CLASSIFICATION — VBStyle compliance, violations, patterns
--   8. DOMAIN       — inferred domain (storage, gui, parse, network, etc.)
--
-- DB-FIRST PRINCIPLE:
--   id + parent_id = identity (never changes)
--   namespace = logical address (bin_tools.DedupeExplorer._build_ui)
--   filepath = provenance only (where it came from, optional)
--   Files are export format, not source of truth
-- ============================================================================

CREATE TABLE IF NOT EXISTS python_structure (
    -- ── 1. ID (DB-First) ───────────────────────────────────
    id              VARCHAR(64) PRIMARY KEY,  -- stable hash, never changes
    content_hash    VARCHAR(64) NOT NULL,     -- SHA256 of source, dedup key
    object_type     VARCHAR(20) NOT NULL,     -- file | class | method | function
    object_name     VARCHAR(500) NOT NULL,    -- DedupeExplorer, _build_ui, etc.
    parent_id       VARCHAR(64),              -- graph hierarchy, NOT filepath
    namespace       TEXT,                     -- bin_tools.DedupeExplorer._build_ui

    -- ── PROVENANCE (optional, just where it came from) ────
    filepath        TEXT,                     -- original path, may be NULL
    filename        VARCHAR(500),             -- original filename, may be NULL
    start_line      INT,                      -- original line range
    end_line        INT,

    -- ── 2. BCL ─────────────────────────────────────────────
    bcl_header      TEXT,                   -- human-readable BCL ([@GHOST], [@VBSTYLE], etc.)

    -- ── 3. BCL_IR ──────────────────────────────────────────
    bcl_ir          TEXT,                   -- machine IR block ([@IRNODE]...[@ENDNODE])
    ir_type         VARCHAR(20),            -- file | class | method | edge | inherit | violate | metric

    -- ── 4. GRAPH (by ID, not name) ────────────────────────
    graph_edges     TEXT,                   -- JSON: [{type:"calls",target_id:"abc123",target_name:"setWindowTitle",lineno:30}, ...]
    inheritance     TEXT,                   -- JSON: [{child_id:"1b2a...", parent_name:"QMainWindow"}, ...]
    call_count      INT DEFAULT 0,
    method_count    INT DEFAULT 0,

    -- ── 5. CODE ────────────────────────────────────────────
    source_snippet  TEXT,                   -- optional: ast.unparse() for reconstruction
    signature       TEXT,                   -- def __init__(self) -> None
    imports         TEXT,                   -- JSON array of imports (file-level only)

    -- ── 6. DESCRIPTION ─────────────────────────────────────
    description     TEXT,                   -- AI-generated: "Initializes DedupeExplorer GUI, connects to CODEBASE DB"
    docstring       TEXT,                   -- extracted from AST

    -- ── 7. CLASSIFICATION ──────────────────────────────────
    violations      TEXT,                   -- JSON: [{rule:"@run(43)",severity:"hard"}, ...]
    violation_count INT DEFAULT 0,
    compliant       BOOLEAN DEFAULT TRUE,
    complexity      INT DEFAULT 0,
    max_nesting     INT DEFAULT 0,
    branch_count    INT DEFAULT 0,
    loop_count      INT DEFAULT 0,
    has_print       BOOLEAN DEFAULT FALSE,
    has_self_underscore BOOLEAN DEFAULT FALSE,
    returns_tuple3  BOOLEAN DEFAULT FALSE,
    has_run         BOOLEAN DEFAULT FALSE,
    has_state       BOOLEAN DEFAULT FALSE,
    patterns        VARCHAR(200),           -- dispatch, singleton, factory, etc.

    -- ── 8. DOMAIN ──────────────────────────────────────────
    domain          VARCHAR(50),            -- storage, gui, parse, network, security, etc.
    sub_domain      VARCHAR(50),            -- more specific: mysql, pyqt, ast, etc.

    -- ── META ───────────────────────────────────────────────
    line_count      INT,
    file_size       BIGINT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uniq_hash_type (content_hash, object_type),
    INDEX idx_parent (parent_id),
    INDEX idx_type (object_type),
    INDEX idx_domain (domain),
    INDEX idx_namespace (namespace(255)),
    INDEX idx_compliant (compliant),
    INDEX idx_name (object_name(255))
);

-- ============================================================================
-- GRAPH EDGES — separate table for queryable relationships
-- ============================================================================
CREATE TABLE IF NOT EXISTS python_graph_edges (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    source_id       VARCHAR(64) NOT NULL,   -- caller method ID (stable)
    target_id       VARCHAR(64),            -- callee ID if resolved, NULL if external
    target_name     VARCHAR(500) NOT NULL,  -- callee name (for unresolved calls)
    edge_type       VARCHAR(20) NOT NULL,   -- calls | inherits | contains | imports
    call_lineno     INT,

    INDEX idx_source (source_id),
    INDEX idx_target_id (target_id),
    INDEX idx_target_name (target_name(255)),
    INDEX idx_edge_type (edge_type)
);

-- ============================================================================
-- BCL IR BLOCKS — raw IR nodes for round-trip reconstruction
-- ============================================================================
CREATE TABLE IF NOT EXISTS python_bcl_ir (
    id              VARCHAR(64) PRIMARY KEY,
    parent_id       VARCHAR(64),
    ir_type         VARCHAR(20) NOT NULL,   -- file | class | method | edge | inherit | violate
    bcl_block       TEXT NOT NULL,          -- full [@IRNODE]...[@ENDNODE] block
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ir_parent (parent_id),
    INDEX idx_ir_type (ir_type)
);
