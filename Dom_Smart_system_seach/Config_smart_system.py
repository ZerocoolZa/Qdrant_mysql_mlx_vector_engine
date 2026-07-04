#!/usr/bin/env python3
"""Smart System Config — gold standard config (flat UPPERCASE constants, no dicts, no hardcoded values in class)"""

from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Database Paths ────────────────────────────────────────────
DB_PATH_EFL_BRAIN = 'efl_brain/efl_brain.db'
DB_NAME_VB_SHARED = 'vb_shared'
DB_HOST_LOCALHOST = 'localhost'
DB_USER_ROOT = 'root'
DB_CHARSET_UTF8MB4 = 'utf8mb4'

# ── Search Terms ──────────────────────────────────────────────
SEARCH_TERM_INRAM_AI = 'inram ai'
SEARCH_TERM_EFL = 'efl'
SEARCH_TERM_SURVIVOR = 'survivor'
SEARCH_TERM_PROMOTE = 'promote'
SEARCH_TERM_FIX = 'fix'
SEARCH_TERM_LEARN = 'learn'
SEARCH_TERM_ERROR = 'error'
SEARCH_TERM_AI = 'ai'
SEARCH_TERM_NEURAL = 'neural'
SEARCH_TERM_MODEL = 'model'
SEARCH_TERM_TRAIN = 'train'
SEARCH_TERM_INFER = 'infer'
SEARCH_TERM_EMBED = 'embed'
SEARCH_TERM_VECTOR = 'vector'
SEARCH_TERM_QDRANT = 'qdrant'
SEARCH_TERM_SEARCH = 'search'
SEARCH_TERM_SCORE = 'score'
SEARCH_TERM_RANK = 'rank'
SEARCH_TERM_SELECT = 'select'
SEARCH_TERM_WEIGHT = 'weight'
SEARCH_TERM_AUTHORITY = 'authority'

# ── Language Detection Markers ────────────────────────────────
LANG_MARKER_C_STDIO = '#include <stdio'
LANG_MARKER_C_STDLIB = '#include <stdlib'
LANG_MARKER_C_MATH = '#include <math'
LANG_MARKER_C_FOUNDATION = '#include <Foundation'
LANG_MARKER_SWIFT_IMPORT = 'import Foundation'
LANG_MARKER_SWIFT_MTL_DEVICE = 'MTLDevice'
LANG_MARKER_SWIFT_MTL_BUFFER = 'MTLBuffer'
LANG_MARKER_SWIFT_MTL_COMMAND = 'MTLCommand'
LANG_MARKER_SWIFT_FUNC = 'func '
LANG_MARKER_SWIFT_ARROW = '->'
LANG_MARKER_SWIFT_LET = 'let '
LANG_MARKER_SWIFT_VAR = 'var '
LANG_MARKER_PYTHON_GHOST = '#@GHOST'
LANG_MARKER_PYTHON_VBSTYLE = '#@VBSTYLE'
LANG_MARKER_PYTHON_DEF = 'def '
LANG_MARKER_PYTHON_CLASS = 'class '
LANG_MARKER_PYTHON_SHEBANG = '#!/usr/bin/env python3'
LANG_MARKER_PYTHON_FUTURE = 'from __future__'
LANG_MARKER_PYTHON_IMPORT = 'import '
LANG_MARKER_MARKDOWN_HASH = '# '
LANG_MARKER_MARKDOWN_YES = 'Yes'
LANG_MARKER_MARKDOWN_THIS_FILE = 'This file'

# ── VBStyle Patterns ──────────────────────────────────────────
VBSTYLE_PATTERN_GHOST = r'#\[@GHOST\]'
VBSTYLE_PATTERN_VBSTYLE = r'#\[@VBSTYLE\]'
VBSTYLE_PATTERN_TUPLE3 = r'Tuple3|tuple3'
VBSTYLE_PATTERN_STATE_DICT = r'self\.state\s*='
VBSTYLE_PATTERN_RUN_DISPATCH = r'def\s+Run\s*\('
VBSTYLE_PATTERN_DECORATOR = r'^\s*@(?:staticmethod|classmethod|property|abstractmethod|functools)'
VBSTYLE_PATTERN_PRINT = r'\bprint\s*\('
VBSTYLE_PATTERN_SELF_UNDERSCORE = r'self\._[a-z]'
VBSTYLE_PATTERN_HARDCODED_PATH = r'["\']/(?:Users|home|tmp|var|opt)/'

# ── VBStyle Rule Names ────────────────────────────────────────
RULE_GHOST_HEADER = 'ghost_header'
RULE_VBSTYLE_HEADER = 'vbstyle_header'
RULE_TUPLE3_RETURN = 'tuple3_return'
RULE_STATE_DICT = 'state_dict'
RULE_RUN_DISPATCH = 'run_dispatch'
RULE_NO_DECORATORS = 'no_decorators'
RULE_NO_PRINT = 'no_print'
RULE_NO_SELF_UNDERSCORE = 'no_self_underscore'
RULE_NO_HARDCODED_PATHS = 'no_hardcoded_paths'

# ── Default Parameters ────────────────────────────────────────
DEFAULT_SEARCH_LIMIT = 50
DEFAULT_EFL_SEARCH_LIMIT = 50
DEFAULT_CODE_PREVIEW_LENGTH = 120
DEFAULT_LANGUAGE_HEAD_SCAN = 500

# ── Scaffold Generator ────────────────────────────────────────
SCAFFOLD_ID = 118
SCAFFOLD_CLASS_NAME = 'generate_vbstyle_magnetic_scaffolds'
SCAFFOLD_NAME_FIELD_EXPAND = 'Lib_FieldExpandEngine'
SCAFFOLD_NAME_RADIUS_COMPUTE = 'Lib_RadiusComputeEngine'
SCAFFOLD_NAME_CONVERGENCE_SCORE = 'Lib_ConvergenceScoreEngine'
SCAFFOLD_NAME_SURVIVOR_SELECT = 'Lib_SurvivorSelectEngine'
SCAFFOLD_NAME_REPLAY_MEMORY = 'Lib_ReplayMemoryEngine'
SCAFFOLD_NAME_END_STATE_LOCK = 'Lib_EndStateLockEngine'
SCAFFOLD_NAME_END_CANDIDATE = 'Lib_EndCandidateEngine'
SCAFFOLD_NAME_CONVERGENCE_RUN = 'Lib_ConvergenceRunEngine'

# ── Language Names ────────────────────────────────────────────
LANG_NAME_PYTHON = 'Python'
LANG_NAME_C = 'C'
LANG_NAME_SWIFT = 'Swift'
LANG_NAME_MARKDOWN = 'Markdown'
LANG_NAME_UNKNOWN = 'unknown'

# ── Commands ──────────────────────────────────────────────────
CMD_SEARCH = 'search'
CMD_DETECT_LANGUAGE = 'detect_language'
CMD_VBSTYLE_CHECK = 'vbstyle_check'
CMD_REPORT = 'report'
CMD_FIND_LIST = 'find_list'
CMD_EFL_SEARCH = 'efl_search'
CMD_READ_STATE = 'read_state'
CMD_SET_CONFIG = 'set_config'

# ── Error Codes ───────────────────────────────────────────────
ERR_UNKNOWN_COMMAND = 'UNKNOWN_COMMAND'
ERR_MISSING_PARAM = 'MISSING_PARAM'
ERR_LOAD_FAILED = 'LOAD_FAILED'
ERR_MYSQL_ERROR = 'MYSQL_ERROR'
ERR_EFL_DB_MISSING = 'EFL_DB_MISSING'
ERR_EFL_DB_ERROR = 'EFL_DB_ERROR'
ERR_MISSING_KEY = 'MISSING_KEY'

# ── Source ────────────────────────────────────────────────────
SOURCE_MYSQL = 'mysql'
SOURCE_EFL = 'efl'
TABLE_CODE_CLASSES = 'code_classes'

# ── GUI: Database Config ──────────────────────────────────────
DB_NAME_TOKEN_REGISTRY = 'token_registry'

# ── GUI: Cache Files ──────────────────────────────────────────
CACHE_FILE_BIGRAM = '.bigrams.sqlite'
CACHE_FILE_WORDFREQ = '.wordfreq.sqlite'

# ── GUI: Colors ───────────────────────────────────────────────
COLOR_GHOST_TEXT_R = 120
COLOR_GHOST_TEXT_G = 130
COLOR_GHOST_TEXT_B = 145
COLOR_BALL_OUTER_R = 31
COLOR_BALL_OUTER_G = 111
COLOR_BALL_OUTER_B = 235
COLOR_BALL_BORDER = '#58a6ff'
COLOR_BALL_FILL = '#1f6feb'
COLOR_BALL_LETTER = '#ffffff'
COLOR_HIGHLIGHT_R = 255
COLOR_HIGHLIGHT_G = 255
COLOR_HIGHLIGHT_B = 255
COLOR_HIGHLIGHT_A = 40
COLOR_BG_MAIN = '#0d1117'
COLOR_BG_INPUT = '#161b22'
COLOR_BORDER = '#30363d'
COLOR_TEXT_MAIN = '#c9d1d9'
COLOR_TEXT_LABEL = '#8b949e'

# ── GUI: Window Sizes ─────────────────────────────────────────
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 480
BALL_SIZE = 64
BALL_CIRCLE_X = 4
BALL_CIRCLE_Y = 4
BALL_CIRCLE_W = 56
BALL_CIRCLE_H = 56
BALL_GLOW_LAYERS = 4
BALL_HIGHLIGHT_X = 10
BALL_HIGHLIGHT_Y = 8
BALL_HIGHLIGHT_W = 20
BALL_HIGHLIGHT_H = 16

# ── GUI: Timers (ms) ──────────────────────────────────────────
TIMER_DEBOUNCE = 200
TIMER_AUTOCOMPLETE = 250
TIMER_RAISE_BALL = 2000
TIMER_CHUNK_YIELD = 10
TIMER_INIT_DELAY = 100
TIMER_INIT_GUARD = 1000
TIMER_MINIMIZE_GUARD = 500

# ── GUI: MySQL Query Limits ───────────────────────────────────
MYSQL_FETCH_BATCH = 5000
MYSQL_WORD_LIMIT = 5000
MYSQL_SEARCH_LIMIT = 50
MYSQL_SNIPPET_LENGTH = 80
MYSQL_TABLE_HITS = 10

# ── GUI: Text Types ───────────────────────────────────────────
TEXT_TYPE_CHAR = 'char'
TEXT_TYPE_VARCHAR = 'varchar'
TEXT_TYPE_TEXT = 'text'
TEXT_TYPE_TINYTEXT = 'tinytext'
TEXT_TYPE_MEDIUMTEXT = 'mediumtext'
TEXT_TYPE_LONGTEXT = 'longtext'

# ── GUI: SQL Queries ──────────────────────────────────────────
SQL_SHOW_TABLES = 'SHOW TABLES'
SQL_SELECT_COLUMNS = 'SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s'
SQL_SELECT_WORDS = 'SELECT word, frequency FROM words ORDER BY frequency DESC LIMIT 5000'
SQL_SELECT_LINE_TEXT = 'SELECT line_text FROM word_locations'

# ── GUI: Fonts ────────────────────────────────────────────────
FONT_NAME_HELVETICA = 'Helvetica'
FONT_SIZE_BALL = 16

# ── GUI: App Names ────────────────────────────────────────────
APP_NAME_MINI_SEARCH = 'MiniSearchGui'
WINDOW_TITLE = 'Mini Search'
BALL_LETTER = 'Q'

# ── GUI: Placeholder Text ─────────────────────────────────────
PLACEHOLDER_SEARCH = 'Search vb_shared…  (Tab = autocomplete, Esc = ball)'
STATUS_INITIAL = 'Type to search…'
STATUS_LOADING = 'Loading autocomplete…'
STATUS_SEARCHING = 'Searching…'
STATUS_LOADING_TABLES = 'Loading…'

# ── GUI: macOS Native Window ──────────────────────────────────
NS_STATUS_LEVEL = 25
NS_COLLECTION_CAN_JOIN_ALL = 1
NS_COLLECTION_STATIONARY = 16
NS_COLLECTION_IGNORES_CYCLE = 64
NS_COLLECTION_FULLSCREEN_AUX = 256
NS_COLLECTION_BEHAVIOR = 1 | 16 | 64 | 256

# ── GUI: Splitter Sizes ───────────────────────────────────────
SPLITTER_HANDLE_WIDTH = 4
SPLITTER_TOP_SIZE = 360
SPLITTER_BOTTOM_SIZE = 80
LAYOUT_MARGIN = 6
LAYOUT_SPACING = 4

# ── GUI: Autocomplete ─────────────────────────────────────────
AUTOCOMPLETE_PREFIX_MIN = 1
AUTOCOMPLETE_WORD_SCAN = 500
AUTOCOMPLETE_MIN_WORD_LEN = 2
TOKENIZE_MIN_WORD_LEN = 2

# ── GUI: Drag Threshold ───────────────────────────────────────
DRAG_THRESHOLD = 3

# ── GUI: Window Opacity ───────────────────────────────────────
WINDOW_OPACITY_MIN = 0.1


# ── SQLite Schema SQL ────────────────────────────────────────
SQL_CREATE_WORDFREQ = 'CREATE TABLE IF NOT EXISTS word_freq (word TEXT PRIMARY KEY, freq INTEGER NOT NULL)'
SQL_INDEX_WORD_PREFIX = 'CREATE INDEX IF NOT EXISTS idx_word_prefix ON word_freq(word)'
SQL_DELETE_WORDFREQ = 'DELETE FROM word_freq'
SQL_UPSERT_WORDFREQ = 'INSERT INTO word_freq (word, freq) VALUES (?, ?) ON CONFLICT(word) DO UPDATE SET freq = freq + excluded.freq'
SQL_SELECT_WORD_PREFIX = 'SELECT word, freq FROM word_freq WHERE word LIKE ? ORDER BY freq DESC LIMIT 20'

SQL_CREATE_BIGRAMS = 'CREATE TABLE IF NOT EXISTS bigrams (w1 TEXT NOT NULL, w2 TEXT NOT NULL, freq INTEGER NOT NULL, PRIMARY KEY(w1,w2))'
SQL_INDEX_BIGRAM_W1 = 'CREATE INDEX IF NOT EXISTS idx_bigram_w1 ON bigrams(w1)'
SQL_INDEX_BIGRAM_W1_FREQ = 'CREATE INDEX IF NOT EXISTS idx_bigram_w1_freq ON bigrams(w1, freq DESC)'
SQL_DELETE_BIGRAMS = 'DELETE FROM bigrams'
SQL_UPSERT_BIGRAM = 'INSERT INTO bigrams (w1, w2, freq) VALUES (?, ?, ?) ON CONFLICT(w1,w2) DO UPDATE SET freq = freq + excluded.freq'
SQL_SELECT_BIGRAM_NEXT = 'SELECT w2, freq FROM bigrams WHERE w1 = ? ORDER BY freq DESC LIMIT 20'
SQL_COUNT_BIGRAMS = 'SELECT COUNT(*) FROM bigrams'

SQL_CREATE_TRIGRAMS = 'CREATE TABLE IF NOT EXISTS trigrams (w1 TEXT, w2 TEXT, w3 TEXT, freq INTEGER, PRIMARY KEY(w1,w2,w3))'
SQL_INDEX_TRIGRAM = 'CREATE INDEX IF NOT EXISTS idx_tri ON trigrams(w1, w2, freq DESC)'
SQL_DELETE_TRIGRAMS = 'DELETE FROM trigrams'
SQL_UPSERT_TRIGRAM = 'INSERT INTO trigrams (w1, w2, w3, freq) VALUES (?, ?, ?, ?) ON CONFLICT(w1,w2,w3) DO UPDATE SET freq = freq + excluded.freq'
SQL_SELECT_TRIGRAM_NEXT = 'SELECT w3, freq FROM trigrams WHERE w1 = ? AND w2 = ? ORDER BY freq DESC LIMIT 20'
SQL_COUNT_TRIGRAMS = 'SELECT COUNT(*) FROM trigrams'

SQL_SELECT_EFL_CLASSES = 'SELECT id, class_name, domain, method_count FROM classes WHERE class_name LIKE ? OR class_code LIKE ? OR description LIKE ? ORDER BY method_count DESC LIMIT ?'

# -- User History (personalization layer) --
SQL_CREATE_USER_HISTORY = 'CREATE TABLE IF NOT EXISTS user_history (word TEXT, context TEXT, freq INTEGER, PRIMARY KEY(word, context))'
SQL_UPSERT_USER_HISTORY = 'INSERT INTO user_history (word, context, freq) VALUES (?, ?, 1) ON CONFLICT(word, context) DO UPDATE SET freq = freq + 1'
SQL_SELECT_USER_HISTORY_PREFIX = 'SELECT word, freq FROM user_history WHERE word LIKE ? AND context = ? ORDER BY freq DESC LIMIT 20'
SQL_SELECT_USER_HISTORY_BIGRAM = 'SELECT word, freq FROM user_history WHERE context = ? ORDER BY freq DESC LIMIT 20'

# -- Ranking Weights --
RANK_WEIGHT_SYMBOL = 100
RANK_WEIGHT_TRIGRAM = 80
RANK_WEIGHT_BIGRAM = 60
RANK_WEIGHT_PREFIX = 40
RANK_WEIGHT_USER_HISTORY = 120
SQL_SELECT_CLASSES_BY_PREFIX = 'SELECT class_name, method_count FROM classes WHERE class_name LIKE ? ORDER BY method_count DESC LIMIT 20'
SQL_SELECT_METHODS_BY_PREFIX = 'SELECT method_name, class_name FROM methods WHERE method_name LIKE ? ORDER BY class_name LIMIT 20'
EFL_DB_PATH = str(BASE_DIR.parent / DB_PATH_EFL_BRAIN)

# ── EFL Brain Schema (Gold Standard from schema_v2.sql) ──────
EFL_SCHEMA_DOMAINS = 'CREATE TABLE IF NOT EXISTS domains (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT)'
EFL_SCHEMA_UNIT_TYPES = 'CREATE TABLE IF NOT EXISTS unit_types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT)'
EFL_SCHEMA_CODE_FILES = 'CREATE TABLE IF NOT EXISTS code_files (id INTEGER PRIMARY KEY AUTOINCREMENT, file_path TEXT NOT NULL UNIQUE, file_name TEXT NOT NULL, source_code TEXT NOT NULL, hash TEXT UNIQUE, created_at TEXT DEFAULT CURRENT_TIMESTAMP)'
EFL_SCHEMA_CLASSES = 'CREATE TABLE IF NOT EXISTS classes (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER REFERENCES code_files(id) ON DELETE SET NULL, class_name TEXT NOT NULL, domain_id INTEGER REFERENCES domains(id), source TEXT NOT NULL DEFAULT \'mysql\', class_code TEXT, description TEXT, ingested_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(class_name, source))'
EFL_SCHEMA_METHODS = 'CREATE TABLE IF NOT EXISTS methods (id INTEGER PRIMARY KEY AUTOINCREMENT, class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE, method_name TEXT NOT NULL, params TEXT, method_code TEXT NOT NULL, is_dunder INTEGER DEFAULT 0, is_run INTEGER DEFAULT 0, is_init INTEGER DEFAULT 0, returns_tuple3 INTEGER DEFAULT 0, has_ast INTEGER DEFAULT 0, has_re INTEGER DEFAULT 0, has_try INTEGER DEFAULT 0, line_start INTEGER, ingested_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(class_id, method_name, line_start))'
EFL_SCHEMA_FUNCTIONS = 'CREATE TABLE IF NOT EXISTS functions (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER REFERENCES code_files(id) ON DELETE SET NULL, function_name TEXT NOT NULL, domain_id INTEGER REFERENCES domains(id), source TEXT NOT NULL, params TEXT, function_code TEXT NOT NULL, line_start INTEGER, ingested_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(source, function_name, line_start))'
EFL_SCHEMA_UNITS = 'CREATE TABLE IF NOT EXISTS units (id INTEGER PRIMARY KEY AUTOINCREMENT, class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE, unit_type_id INTEGER NOT NULL REFERENCES unit_types(id), description TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(class_id, unit_type_id))'
EFL_SCHEMA_UNIT_METHODS = 'CREATE TABLE IF NOT EXISTS unit_methods (id INTEGER PRIMARY KEY AUTOINCREMENT, unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE, method_id INTEGER NOT NULL REFERENCES methods(id) ON DELETE CASCADE, position INTEGER NOT NULL DEFAULT 0, UNIQUE(unit_id, method_id), UNIQUE(unit_id, position))'
EFL_SCHEMA_GRAPH_EDGES = 'CREATE TABLE IF NOT EXISTS graph_edges (id INTEGER PRIMARY KEY AUTOINCREMENT, source_method_id INTEGER NOT NULL REFERENCES methods(id) ON DELETE CASCADE, target_method_id INTEGER REFERENCES methods(id) ON DELETE SET NULL, edge_type TEXT NOT NULL DEFAULT \'internal_call\')'
EFL_SCHEMA_UNIT_GRAPH_EDGES = 'CREATE TABLE IF NOT EXISTS unit_graph_edges (id INTEGER PRIMARY KEY AUTOINCREMENT, source_unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE, target_unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE, edge_type TEXT NOT NULL DEFAULT \'unit_call\', weight REAL DEFAULT 1.0, UNIQUE(source_unit_id, target_unit_id, edge_type))'
EFL_SCHEMA_EXECUTION_LOG = 'CREATE TABLE IF NOT EXISTS execution_log (id INTEGER PRIMARY KEY AUTOINCREMENT, unit_id INTEGER REFERENCES units(id) ON DELETE SET NULL, method_id INTEGER REFERENCES methods(id) ON DELETE SET NULL, input_state TEXT NOT NULL, output_state TEXT, action_taken TEXT NOT NULL, success INTEGER, error_msg TEXT, reward REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)'
EFL_SCHEMA_EXPECTATION_GRAPH = 'CREATE TABLE IF NOT EXISTS expectation_graph (id INTEGER PRIMARY KEY AUTOINCREMENT, domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE, element_type TEXT NOT NULL, element_name TEXT NOT NULL, purpose TEXT, expected_returns TEXT, edge_from TEXT, edge_to TEXT, edge_type TEXT, UNIQUE(domain_id, element_type, element_name))'
EFL_SCHEMA_DIFF_RESULTS = 'CREATE TABLE IF NOT EXISTS diff_results (id INTEGER PRIMARY KEY AUTOINCREMENT, domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE, expectation_id INTEGER REFERENCES expectation_graph(id) ON DELETE CASCADE, gap_type TEXT NOT NULL, element_name TEXT NOT NULL, purpose TEXT, existing_count INTEGER DEFAULT 0, status TEXT DEFAULT \'MISSING\', suggested_action TEXT, priority TEXT DEFAULT \'medium\', created_at TEXT DEFAULT CURRENT_TIMESTAMP)'
EFL_SCHEMA_VBSTYLE_CONTRACTS = 'CREATE TABLE IF NOT EXISTS vbstyle_contracts (id INTEGER PRIMARY KEY AUTOINCREMENT, domain_id INTEGER REFERENCES domains(id) ON DELETE CASCADE, method_name TEXT NOT NULL, required INTEGER DEFAULT 1, requires_run INTEGER DEFAULT 0, requires_init INTEGER DEFAULT 0, requires_tuple3 INTEGER DEFAULT 1, min_params INTEGER DEFAULT 0, max_params INTEGER DEFAULT 5, requires_pascalcase INTEGER DEFAULT 1, requires_no_print INTEGER DEFAULT 1, requires_no_decorator INTEGER DEFAULT 1, expected_dependencies TEXT, UNIQUE(domain_id, method_name))'
EFL_SCHEMA_VBSTYLE_METHOD_SHAPE = 'CREATE TABLE IF NOT EXISTS vbstyle_method_shape (method_id INTEGER PRIMARY KEY REFERENCES methods(id) ON DELETE CASCADE, contract_id INTEGER REFERENCES vbstyle_contracts(id) ON DELETE SET NULL, tuple3_compliant INTEGER, param_compliant INTEGER, naming_compliant INTEGER, no_print_compliant INTEGER, no_decorator_compliant INTEGER, shape_score REAL NOT NULL DEFAULT 0, vbstyle_status TEXT NOT NULL DEFAULT \'UNKNOWN\', validated_at TEXT DEFAULT CURRENT_TIMESTAMP)'
EFL_SCHEMA_ERROR_CASES = 'CREATE TABLE IF NOT EXISTS error_cases (id INTEGER PRIMARY KEY AUTOINCREMENT, method_id INTEGER REFERENCES methods(id) ON DELETE SET NULL, broken_code TEXT NOT NULL, error_type TEXT NOT NULL, error_message TEXT, fixed_code TEXT, re_run_success INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)'
EFL_SCHEMA_RULES = 'CREATE TABLE IF NOT EXISTS rules (id INTEGER PRIMARY KEY AUTOINCREMENT, rule_name TEXT, error_signature TEXT NOT NULL UNIQUE, fix_pattern TEXT, uses INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, confidence REAL DEFAULT 0, extracted_from_case INTEGER REFERENCES error_cases(id) ON DELETE SET NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)'

EFL_SCHEMA_ALL = [
    EFL_SCHEMA_DOMAINS, EFL_SCHEMA_UNIT_TYPES, EFL_SCHEMA_CODE_FILES,
    EFL_SCHEMA_CLASSES, EFL_SCHEMA_METHODS, EFL_SCHEMA_FUNCTIONS,
    EFL_SCHEMA_UNITS, EFL_SCHEMA_UNIT_METHODS, EFL_SCHEMA_GRAPH_EDGES,
    EFL_SCHEMA_UNIT_GRAPH_EDGES, EFL_SCHEMA_EXECUTION_LOG,
    EFL_SCHEMA_EXPECTATION_GRAPH, EFL_SCHEMA_DIFF_RESULTS,
    EFL_SCHEMA_VBSTYLE_CONTRACTS, EFL_SCHEMA_VBSTYLE_METHOD_SHAPE,
    EFL_SCHEMA_ERROR_CASES, EFL_SCHEMA_RULES,
]

EFL_PRAGMA_FOREIGN_KEYS = 'PRAGMA foreign_keys = ON'

EFL_SEED_DOMAINS = "INSERT OR IGNORE INTO domains (name, description) VALUES ('repair','Code repair and fault recovery'),('generate','Code generation'),('parse','Code parsing and AST extraction'),('scan','Code scanning and analysis'),('db','Database operations'),('test','Code testing'),('learn','Learning and adaptation'),('gui','GUI and UI'),('fault_inject','Fault injection'),('orchestrate','System orchestration')"
EFL_SEED_UNIT_TYPES = "INSERT OR IGNORE INTO unit_types (name, description) VALUES ('init_run','Init then Run dispatch'),('scan_fix_verify','Scan then Fix then Verify'),('parse_transform_build','Parse then Transform then Build'),('plan_apply_rollback','Plan then Apply then Rollback'),('read_process_write','Read then Process then Write'),('learn_score_adapt','Learn then Score then Adapt')"

# ── SQLite PRAGMAs ────────────────────────────────────────────
PRAGMA_BUILD_WAL = 'PRAGMA journal_mode=WAL'
PRAGMA_BUILD_SYNC = 'PRAGMA synchronous=OFF'
PRAGMA_BUILD_TEMP = 'PRAGMA temp_store=MEMORY'
PRAGMA_BUILD_CACHE = 'PRAGMA cache_size=-50000'
PRAGMA_BUILD_MMAP = 'PRAGMA mmap_size=30000000000'
PRAGMA_RUNTIME_SYNC = 'PRAGMA synchronous=NORMAL'
PRAGMA_RUNTIME_CACHE = 'PRAGMA cache_size=-10000'

# ── MySQL Config ─────────────────────────────────────────────
MYSQL_AUTOCOMMIT = True

# ── Autocomplete Runtime ─────────────────────────────────────
AUTOCOMPLETE_PREFIX_LIMIT = 20
AUTOCOMPLETE_NEXT_LIMIT = 20
LRU_CACHE_SIZE = 5000
AUTOCOMPLETE_DB_NAME = 'autocomplete.db'

# ── GUI: Misc ────────────────────────────────────────────────
BALL_TOOLTIP = 'Click to restore Mini Search'
DEBUG_PREFIX = '[mini_search]'

# ── Stop Words (for tokenizer) ────────────────────────────────
STOP_WORDS = frozenset({
    'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
    'a', 'an', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
    'it', 'we', 'they', 'what', 'which', 'who', 'whom', 'whose', 'where',
    'when', 'why', 'how', 'there', 'here', 'if', 'then', 'else', 'because',
    'although', 'though', 'while', 'since', 'until', 'unless', 'before',
    'after', 'during', 'through', 'over', 'under', 'again', 'further', 'then',
    'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'both',
    'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
    'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
    'also', 'now', 'get', 'like', 'know', 'mean', 'well', 'back', 'still',
})

# ── GUI: Table Viewer (TASK-069) ─────────────────────────────
TABLE_VIEWER_PAGE_SIZE = 100
TABLE_VIEWER_MAX_WIDTH = 900
TABLE_VIEWER_MAX_HEIGHT = 600
SQL_SELECT_TABLE_CONTENTS = 'SELECT * FROM `{table}` LIMIT {limit} OFFSET {offset}'
SQL_COUNT_TABLE_ROWS = 'SELECT COUNT(*) FROM `{table}`'

# ── Domain File Inventory (merged from Config_Smart_system_seach.py) ──
DOMAIN = 'Smart_system_seach'
FILE_COUNT = 8
CLASS_COUNT = 10

FILES = {
    "Classifier_smart_system.py": {
        "purpose": "Smart Classifier Domain.",
        "lines": 743,
        "classes": ["SmartClassifier"],
        "methods": [],
    },
    "Config_smart_system.py": {
        "purpose": "Smart System Config — gold standard config (flat UPPERCASE constants, no dicts, no hardcoded values in class)",
        "lines": 360,
        "classes": [],
        "methods": [],
    },
    "Engine_smart_search.py": {
        "purpose": "Smart Search Engine Domain.",
        "lines": 752,
        "classes": ["StyleWindow", "SmartSearch"],
        "methods": ["_debug", "_tokenize", "_apply_build_pragmas", "_apply_runtime_pragmas", "AcRuntimeConn", "AcPrefixSearch", "AcBigramNext", "AcTrigramNext", "AcSymbolSearch", "AcUserHistoryPrefix", "AcUserHistoryBigram", "AcRecordAccept", "AcInitHistory", "AcRankedSuggestions", "DetectStyleMode", "LoadWordFreqChunked", "LoadBigramsChunked", "LoadTrigramsChunked", "LoadAutocomplete", "_mysql_search", "search_source"],
    },
    "Extract_qa_pairs.py": {
        "purpose": "Extract question→answer pairs from MySQL vb_shared chat tables into a",
        "lines": 590,
        "classes": ["QaPairExtractor"],
        "methods": ["_strip_noise_light", "_strip_noise_question", "_normalize_for_hash", "_compute_hash", "_is_followup", "_split_sentences", "_extract_questions", "_split_cascade_blocks", "_extract_chatgpt_pairs", "_find_assistant_responses", "main"],
    },
    "Extract_user_questions.py": {
        "purpose": "Extract and classify all user questions from MySQL vb_shared chat tables",
        "lines": 510,
        "classes": ["UserQuestionExtractor"],
        "methods": ["_strip_noise", "_split_sentences", "_is_question", "_clean_question", "_extract_questions_from_message", "_split_chat_blocks", "_extract_json_user_messages", "main"],
    },
    "Gui_Smart_search.py": {
        "purpose": "Mini Search GUI — PyQt6 (macOS M1 tested)",
        "lines": 661,
        "classes": ["GhostLineEdit", "FloatingBall", "MiniSearchGui"],
        "methods": ["_debug", "_get_nswindow", "_ns_msg", "_ns_msg_int", "_ns_get_int", "_apply_pindrop_ball_style", "main"],
    },
    "View_user_questions.py": {
        "purpose": "Quick viewer for user_questions table in autocomplete.db.",
        "lines": 123,
        "classes": ["QuestionViewer"],
        "methods": ["main"],
    },
    "dot_command_bar.py": {
        "purpose": "Dot-Notation Command Bar — Floating Toolbar",
        "lines": 657,
        "classes": ["DotCommandBar"],
        "methods": ["build_property_db", "_human_name", "_human_type", "_human_prop", "find_running_widgets"],
    },
}

CLASSES = {
    "SmartClassifier": {
        "file": "Classifier_smart_system.py",
        "methods": ["__init__", "Run", "MysqlConn", "DetectLanguage", "DetectLangInternal", "VbstyleCheck", "CountMethodsCmd", "CountMethods", "ScanCode", "ScanClass", "ExtractClassTree", "ExtractBclHeader", "CheckCompliancePerClass", "EflConn", "EflClassify", "EflClassDetail", "EflZeroMethods", "EflVbstyleSummary", "EflMethodViolations", "ReadState", "SetConfig"],
    },
    "StyleWindow": {
        "file": "Engine_smart_search.py",
        "methods": ["__init__", "Push", "Mode", "Reset"],
    },
    "SmartSearch": {
        "file": "Engine_smart_search.py",
        "methods": ["__init__", "Run", "MysqlConn", "Search", "EflSearch", "LoadFindList", "FindList", "Report", "ReadState", "SetConfig"],
    },
    "QaPairExtractor": {
        "file": "Extract_qa_pairs.py",
        "methods": ["__init__", "Run", "ReadState", "SetConfig", "MysqlConn", "InitSqlite", "Extract", "_process_cascade_doc", "_process_chatgpt_doc", "_insert_pair", "_build_summary"],
    },
    "UserQuestionExtractor": {
        "file": "Extract_user_questions.py",
        "methods": ["__init__", "Run", "ReadState", "SetConfig", "MysqlConn", "InitSqlite", "Extract", "_classify_and_prepare", "_insert_batch", "_build_summary"],
    },
    "GhostLineEdit": {
        "file": "Gui_Smart_search.py",
        "methods": ["__init__", "set_model", "_on_text_changed", "_get_current_word", "_get_previous_word", "_update_ghost", "_accept_ghost", "keyPressEvent", "paintEvent"],
    },
    "FloatingBall": {
        "file": "Gui_Smart_search.py",
        "methods": ["__init__", "_reassert_on_top", "showEvent", "hideEvent", "mousePressEvent", "mouseMoveEvent", "mouseReleaseEvent", "paintEvent"],
    },
    "MiniSearchGui": {
        "file": "Gui_Smart_search.py",
        "methods": ["__init__", "_init_autocomplete", "_ac_tick", "_on_autocomplete_loaded", "_on_search_debounced", "_do_search", "_on_enter", "_on_item_activated", "_activate", "_minimize_to_ball", "showEvent", "_mark_initialized", "hideEvent", "changeEvent", "_restore_from_ball", "closeEvent"],
    },
    "QuestionViewer": {
        "file": "View_user_questions.py",
        "methods": ["__init__", "_load", "_on_filter", "_populate"],
    },
    "DotCommandBar": {
        "file": "dot_command_bar.py",
        "methods": ["__init__", "_build_ui", "_start_drag", "_do_drag", "_refresh_windows", "_on_input", "_update_props_table", "_on_suggestion_click", "_run_command"],
    },
}

VBSTYLE_COMPLIANCE = {
    "total_files": 8,
    "files_with_Run": 4,
    "files_with_state": 4,
    "files_with_print": 0,
    "files_with_decorator": 0,
    "pass_rate": 50.0,
}
