/*
 * ingest_codebase.sql — Create and populate the Cascade Codebase SQLite DB
 *
 * Run: sqlite3 cascade_codebase.db < ingest_codebase.sql
 *
 * This DB ingests every source file in Cascade_toolStack so we can
 * query functions, flags, constants, patterns, and capabilities.
 * It is the searchable knowledge base for building VBStyle .c files.
 */

-- ══════════════════════════════════════════════════════════════
-- SCHEMA
-- ══════════════════════════════════════════════════════════════

PRAGMA journal_mode = WAL;

-- Source files (one row per .c / .h / .py file)
CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path   TEXT NOT NULL UNIQUE,
    file_name   TEXT NOT NULL,
    file_ext    TEXT NOT NULL,           -- .c, .h, .py
    file_size   INTEGER,
    line_count  INTEGER,
    version     TEXT,                    -- "5.0", "v4", "1.0", etc.
    vbstyle     INTEGER DEFAULT 0,       -- 1 = VBStyle compliant, 0 = not
    purpose     TEXT,                    -- one-line description
    content     TEXT,                    -- full file content
    ingested_at TEXT DEFAULT (datetime('now'))
);

-- Functions extracted from each file
CREATE TABLE IF NOT EXISTS functions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL,
    func_name   TEXT NOT NULL,
    return_type TEXT,                    -- "Tuple3", "void", "int", etc.
    signature   TEXT,                    -- full signature
    purpose     TEXT,                    -- one-line purpose
    line_num    INTEGER,
    category    TEXT,                    -- "config", "search", "report", "utility", "command", "dispatch"
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- CLI flags / commands extracted from each file
CREATE TABLE IF NOT EXISTS commands (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL,
    cmd_name    TEXT NOT NULL,           -- "search", "--semantic", "DIR", etc.
    cmd_type    TEXT NOT NULL,           -- "command", "flag", "subcommand"
    argument    TEXT,                    -- "<keyword>", "<N>", etc.
    purpose     TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Constants / hardcoded values
CREATE TABLE IF NOT EXISTS constants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL,
    const_name  TEXT NOT NULL,
    const_value TEXT,
    purpose     TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Integrations (MySQL, SQLite, Qdrant, Python, etc.)
CREATE TABLE IF NOT EXISTS integrations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL,
    integration TEXT NOT NULL,           -- "MySQL", "SQLite", "Qdrant", "Python3", "PyQt6"
    usage       TEXT,                    -- "config", "search", "ingestion", "GUI"
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- VBStyle pattern catalog (extracted patterns for reuse)
CREATE TABLE IF NOT EXISTS patterns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_name    TEXT NOT NULL,       -- "Run_dispatch", "Tuple3_return", "State_struct"
    pattern_type    TEXT NOT NULL,       -- "dispatch", "return", "state", "config", "report"
    source_file     TEXT,                -- which file demonstrates this pattern
    code_snippet    TEXT,                -- the actual code
    description     TEXT
);

-- ══════════════════════════════════════════════════════════════
-- INDEXES
-- ══════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_files_name ON files(file_name);
CREATE INDEX IF NOT EXISTS idx_files_vbstyle ON files(vbstyle);
CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(func_name);
CREATE INDEX IF NOT EXISTS idx_functions_file ON functions(file_id);
CREATE INDEX IF NOT EXISTS idx_functions_cat ON functions(category);
CREATE INDEX IF NOT EXISTS idx_commands_file ON commands(file_id);
CREATE INDEX IF NOT EXISTS idx_commands_name ON commands(cmd_name);
CREATE INDEX IF NOT EXISTS idx_constants_file ON constants(file_id);
CREATE INDEX IF NOT EXISTS idx_integrations_file ON integrations(file_id);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);

-- ══════════════════════════════════════════════════════════════
-- VBSTYLE PATTERN CATALOG (the templates for new .c files)
-- ══════════════════════════════════════════════════════════════

INSERT INTO patterns (pattern_name, pattern_type, source_file, code_snippet, description) VALUES
('Run_dispatch', 'dispatch', 'msearch_v5.c',
'Tuple3 Cascade_Run(CascadeState *state, const char *command, void *params) {
    for (int i = 0; COMMANDS[i].name; i++) {
        if (strcmp(COMMANDS[i].name, command) == 0)
            return COMMANDS[i].fn(state, params);
    }
    return Tuple3_Err(ERR_UNKNOWN_CMD, command);
}',
'Function pointer table dispatch. Every VBStyle tool has a Run() entry point that routes commands to handler functions.'),

('CommandBinding_table', 'dispatch', 'msearch_v5.c',
'static const CommandBinding COMMANDS[] = {
    { "search",   Cmd_Search,   "MySQL keyword search" },
    { "hybrid",   Cmd_Hybrid,   "MySQL + Qdrant combined" },
    { NULL, NULL, NULL }
};',
'Static array of {name, function, description} bindings. NULL-terminated. This IS the dispatch table.'),

('Tuple3_return', 'return', 'cascade_toolstack.h',
'typedef struct {
    int  ok;           /* 1 = success, 0 = failure */
    void *data;        /* result data (type-specific) */
    int  error_code;   /* ERR_* constant */
    char error_msg[MAX_ERROR_MSG];
} Tuple3;

static inline Tuple3 Tuple3_Ok(void *data) {
    Tuple3 t = { .ok = 1, .data = data, .error_code = ERR_NONE, .error_msg = "" };
    return t;
}

static inline Tuple3 Tuple3_Err(int code, const char *msg) {
    Tuple3 t = { .ok = 0, .data = NULL, .error_code = code, .error_msg = "" };
    if (msg) strncpy(t.error_msg, msg, MAX_ERROR_MSG - 1);
    return t;
}',
'Every function returns Tuple3 (ok, data, error). No exceptions, no global state. Constructors for success and error.'),

('State_struct', 'state', 'msearch_v5.c',
'typedef struct {
    Config       config;              /* loaded from SQLite */
    TableSchema  schema[MAX_TABLES];  /* all tables + metadata */
    int          table_count;
    int          output_mode;         /* OUTPUT_TEXT or OUTPUT_JSON */
    int          search_mode;
    int          dump_mode;
    int          verbose;
    char         current_db[128];
    MYSQL       *mysql_conn;
} CascadeState;',
'All state in one struct, heap-allocated. No globals. Passed to every function. This IS the class instance.'),

('Config_from_SQLite', 'config', 'msearch_v5.c',
'Tuple3 Config_Load(CascadeState *state, const char *db_path) {
    sqlite3 *db;
    if (sqlite3_open(db_path, &db) != SQLITE_OK)
        return Tuple3_Err(ERR_CONFIG_LOAD, "cannot open config db");
    /* read key-value pairs into state->config */
    sqlite3_close(db);
    return Tuple3_Ok(NULL);
}',
'No hardcoded paths. All config loaded from SQLite key-value table. Fallback to defaults if DB missing.'),

('Report_layer', 'report', 'msearch_v5.c',
'void Report_Init(ReportState *rs, int mode);
void Report_TableHeader(ReportState *rs, const TableSchema *ts, int show_relevance);
void Report_Row(ReportState *rs, MYSQL_ROW row, ...);
void Report_TableFooter(ReportState *rs);
void Report_Finalize(ReportState *rs);',
'No raw printf. All output goes through Report_* functions that handle both TEXT and JSON modes.'),

('BCL_header', 'state', 'cascade_spine.c',
'/*
 * [@GHOST]{[@file<xxx.c>][@domain<xxx>][@role<dispatch>][@auth<cascade>][@date<2026-06-22>][@ver<5.0>]}
 * [@VBSTYLE]{[@auth<cascade>][@role<dispatch>][@return<Tuple3>][@no<hardcoded_paths|raw_printf|globals>]}
 */',
'Every VBStyle-for-C file starts with BCL metadata headers. Ghost header + VBStyle header.'),

('SQL_injection_fix', 'security', 'msearch_v5.c',
'/* Escape user input before building SQL */
char escaped[BUF * 2];
mysql_real_escape_string(state->mysql_conn, escaped, keyword, strlen(keyword));',
'Use mysql_real_escape_string() on ALL user input. Never concatenate raw strings into SQL.'),

('Shell_escape_fix', 'security', 'msearch_v5.c',
'void Util_EscapeShell(const char *in, char *out, size_t out_sz) {
    /* Wrap arg in single quotes, escape embedded quotes */
    size_t j = 0;
    out[j++] = 0x27;  /* single quote */
    for (size_t i = 0; in[i] && j + 4 < out_sz; i++) {
        if (in[i] == 0x27) {  /* embedded single quote */
            out[j++] = 0x27; out[j++] = 0x5C; out[j++] = 0x27; out[j++] = 0x27;
        } else {
            out[j++] = in[i];
        }
    }
    out[j++] = 0x27;  /* closing single quote */
    out[j] = 0;
}',
'Wrap shell arguments in single quotes. Escape embedded single quotes. Prevents command injection via popen().'),

('Store_result_fix', 'security', 'msearch_v5.c',
'/* Use mysql_store_result, not mysql_use_result */
MYSQL_RES *res = mysql_store_result(conn);
/* ... process rows ... */
mysql_free_result(res);  /* MUST free before next query */',
'mysql_store_result() buffers the entire result set. Prevents "commands out of sync" errors when doing nested queries.'),

('Heap_allocation', 'state', 'msearch_v5.c',
'/* Allocate state on heap, not stack */
CascadeState *state = (CascadeState *)calloc(1, sizeof(CascadeState));
if (!state) { fprintf(stderr, "out of memory\n"); return 1; }',
'State structs can be large (100KB+). Never put on stack. calloc ensures zero-initialization. Free at end.');
