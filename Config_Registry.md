* Config Registry — All Config Files in the Workspace

> Auto-generated catalog of every `config*.*` file, organized by folder.
> Each section is named `Config_<folder>.py` after the folder it belongs to.

---

## Config_chat_mover.py

**Path:** `chat_mover/Config.py`
**Pattern:** SQLite-backed key/value/description (gold standard)
**DB:** `~/.config/chat_mover/chat_mover_config.db`

### Variables

| Key                | Default          | Description              |
| ------------------ | ---------------- | ------------------------ |
| mysql_host         | localhost        | MySQL server hostname    |
| mysql_port         | 3306             | MySQL port               |
| mysql_user         | root             | MySQL username           |
| mysql_pass         | (empty)          | MySQL password           |
| mysql_charset      | utf8mb4          | MySQL charset            |
| mysql_autocommit   | 0                | MySQL autocommit         |
| mysql_timeout      | 10               | Connection timeout       |
| dest_db            | Chat_History     | Destination database     |
| source_tables      | (JSON)           | Source table definitions |
| qdrant_host        | localhost        | Qdrant hostname          |
| qdrant_port        | 6333             | Qdrant port              |
| qdrant_collection  | chat_messages    | Qdrant collection        |
| embed_model        | all-MiniLM-L6-v2 | Embedding model          |
| embed_dimensions   | 384              | Vector dimensions        |
| embed_max_tokens   | 256              | Max tokens               |
| batch_size         | 500              | Import batch size        |
| batch_size_min     | 50               | Min batch size           |
| max_rows_per_table | 50000            | Row limit                |
| log_file           | (BASE_DIR)       | Log path                 |
| log_max_bytes      | 10485760         | Log rotation size        |
| log_backup_count   | 5                | Log backups              |
| lock_file          | (BASE_DIR)       | Lock path                |
| disk_folders       | []               | Disk scan folders        |
| skip_filenames     | []               | Skip filenames           |
| skip_paths         | []               | Skip paths               |

### Rules

- All values in SQLite `config(key, value, description)` table
- `CONFIG_SEED_SQL` embedded — creates table + seeds values via `executescript`
- Env var overrides: `CHAT_MOVER_MYSQL_HOST`, `MYSQL_PASSWORD`, etc.
- No hardcoded values — everything from DB
- DB stored at `~/.config/chat_mover/` — not in project folder
- Singleton: `cfg = ChatMoverConfig()`
- Properties for typed access: `_get`, `_get_int`, `_get_bool`, `_get_json`
- Embedded `SCHEMA_SQL` for MySQL destination (sessions, messages, prompts, pipeline_state, error_knowledge)

---

## Config_BookSystem.py

**Path:** `BookSystem/config.py`
**Pattern:** Class attributes (gold standard template, 4393 lines)
**DB:** `book.db` (SQLite, in project folder)

### Variables

| Category  | Attributes                                                                                                   |
| --------- | ------------------------------------------------------------------------------------------------------------ |
| Paths     | `BASE_DIR`, `DB_PATH` (env: `BOOK_DB`), `MARKDOWN_PATH`                                              |
| Versions  | `CLI_VERSION`, `VIEWER_VERSION`, `SCHEMA_VERSION`                                                      |
| Viewer    | `WINDOW_TITLE`, `WINDOW_WIDTH`, `WINDOW_HEIGHT`, `BOOK_TITLE`, `BOOK_SUBTITLE`                     |
| Flipbook  | `FLIPBOOK_WIDTH`, `FLIPBOOK_HEIGHT`                                                                      |
| Colors    | `COLOR_HIGHLIGHT`, `COLOR_ANNOTATION`, `COLOR_SEARCH`                                                  |
| Tooltips  | `TOOLTIPS` dict (prev, next, export, refresh, search, highlight, annotate, help, about, read, stop, voice) |
| Theme     | `THEME` dict (window_bg, toolbar, Qt styles, dialog styles)                                                |
| Schema    | Embedded SQL (15 tables, 5 views)                                                                            |
| Docs      | `ABOUT`, `HELP`, `README` constants                                                                    |
| Resources | `TURNJS_COMPRESSED` (base64 embedded)                                                                      |

### Rules

- `@ghost(33)` — Ghost Header present
- `@vbsty(34)` — VBStyle Header present
- `@cstyle(35)` — C-style code
- `@clshdr(36)` — Class header
- `@mthdr(37)` — Method header
- `@pascal(38)` — PascalCase classes
- `@upper(39)` — UPPERCASE constants
- `@print(22)` — No print statements
- `@decorators(20)` — No decorators
- `@hardcode(24)` — No hardcoded paths, all from BASE_DIR
- `@underscore(19)` — No underscores in class names
- `@tabs(25)` — No tabs
- `@whitespace(26)` — No trailing whitespace
- `@enums(21)` — No enums
- `@hidden(23)` — No hidden behavior
- `@auth(52)` — Authority documented
- `@rpt(54)` — Report structure
- Env var override: `BOOK_DB`, `BOOK_SCHEMA`
- Singleton: `cfg = Config()`

---

## Config_BCL.py

**Path:** `BCL/bcl_config.py` + `BCL/config.py`
**Pattern:** Rule definitions + BookSystem config copy

### Variables (bcl_config.py)

| Variable  | Description                                       |
| --------- | ------------------------------------------------- |
| `RULES` | List of rule dicts from `vb_shared.rules` table |

### Rules Defined

- Rule 24: Token must be `[@Token]` (capital first letter)
- Rule 162: NO regex bracket guessing — must use real bracket parser
- Rule 220: Must use real bracket parser
- Rule 999: Weight MUST be last element in bracket tuple

### BCL Forms

- **config:** `[@name]{("key";"value")}` — passive, read by dom_config
- **command:** `[@name]{("action";weight)}` — active, run through MemUnit
- **token:** `[@tag] ("desc";"desc2")` — flat, no braces
- **decision_tree:** `[@rule]{[@check]{[@Pass]{...}[@Fail]{...}}}`

### Rules (config.py — same as BookSystem)

- Same as `Config_BookSystem.py` (this is a copy of BookSystem config)

---

## Config_smart_system.py (consolidated — formerly Config_Smart_system_seach.py)

**Path:** `Smart_system_seach/Config_smart_system.py`
**Pattern:** Flat UPPERCASE constants (no class, no dict)
**Note:** `Config_Smart_system_seach.py` was merged into this file (TASK-073) — domain inventory (FILES/CLASSES/VBSTYLE_COMPLIANCE/DOMAIN) now lives here too.

### Variables

| Category         | Constants                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DB Paths         | `DB_PATH_EFL_BRAIN`, `DB_NAME_VB_SHARED`, `DB_HOST_LOCALHOST`, `DB_USER_ROOT`, `DB_CHARSET_UTF8MB4`                                                                                                                                                                                                                                                                                                                                                                                               |
| Search Terms     | `SEARCH_TERM_INRAM_AI`, `SEARCH_TERM_EFL`, `SEARCH_TERM_SURVIVOR`, `SEARCH_TERM_PROMOTE`, `SEARCH_TERM_FIX`, `SEARCH_TERM_LEARN`, `SEARCH_TERM_ERROR`, `SEARCH_TERM_AI`, `SEARCH_TERM_NEURAL`, `SEARCH_TERM_MODEL`, `SEARCH_TERM_TRAIN`, `SEARCH_TERM_INFER`, `SEARCH_TERM_EMBED`, `SEARCH_TERM_VECTOR`, `SEARCH_TERM_QDRANT`, `SEARCH_TERM_SEARCH`, `SEARCH_TERM_SCORE`, `SEARCH_TERM_RANK`, `SEARCH_TERM_SELECT`, `SEARCH_TERM_WEIGHT`, `SEARCH_TERM_AUTHORITY` |
| Language Markers | `LANG_MARKER_C_STDIO`, `LANG_MARKER_C_STDLIB`, `LANG_MARKER_C_MATH`, `LANG_MARKER_C_FOUNDATION`, `LANG_MARKER_SWIFT_IMPORT`, `LANG_MARKER_SWIFT_MTL_DEVICE`, `LANG_MARKER_SWIFT_MTL_BUFFER`, `LANG_MARKER_SWIFT_MTL_COMMAND`, `LANG_MARKER_SWIFT_FUNC`, `LANG_MARKER_SWIFT_ARROW`, `LANG_MARKER_SWIFT_LET`, `LANG_MARKER_SWIFT_VAR`                                                                                                                                                 |
| VBStyle Patterns | `VBSTYLE_PATTERN_TUPLE3`, `VBSTYLE_PATTERN_DECORATOR`                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Rule Names       | `RULE_NO_DECORATORS`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Scaffold Names   | `SCAFFOLD_NAME_SURVIVOR_SELECT`, `SCAFFOLD_NAME_REPLAY_MEMORY`                                                                                                                                                                                                                                                                                                                                                                                                                                          |

### Rules

- `@upper(39)` — All constants UPPERCASE
- `@hardcode(24)` — No hardcoded values in class
- `@pascal(38)` — PascalCase for class references
- Flat module-level constants — no class wrapper
- `from pathlib import Path` — `BASE_DIR = Path(__file__).parent`

---

## Config_Sql_Schema_Config.py

**Path:** `Sql_Schema_Config/Database_Schema_config.py`
**Pattern:** Class attributes with rule tuples

### Variables

| Category     | Attributes                                                       |
| ------------ | ---------------------------------------------------------------- |
| Rules        | `RULES` — 36 structural rules across 4 domains                |
| Design Rules | 80 design rules, 7 categories, engine-tagged (SQLite/MySQL/both) |
| Thresholds   | `MAX_LOB_COLUMNS`, etc. (class attributes)                     |

### Rule Domains

1. **Integrity/correctness** — schema is valid
2. **Normalization/design** — schema is well designed
3. **Performance/indexing** — schema is query efficient
4. **Naming/metadata** — schema is clean and maintainable

### Rules

- `@ghost` — Ghost Header present
- `@vbsty` — VBStyle Header present
- `@hardcode` — No hardcoded paths
- To add rule: add tuple to `Config.RULES`
- To toggle: change True/False in tuple
- To tune threshold: change class attribute

---

## Config_code_store_variations.py

**Path:** `code_store_variations/Config.py` + `code_store_variations/impl_config.py`
**Pattern:** Test config + VBStyle dispatch config

### Variables (Config.py)

| Variable                       | Description                      |
| ------------------------------ | -------------------------------- |
| `BASE_DIR`                   | `Path(__file__).parent`        |
| `DB_PATH`                    | `code_store.db`                |
| `DOM_PATH`                   | Hardcoded path to Domains folder |
| `PASS`, `FAIL`, `ERRORS` | Test counters                    |

### Functions

- `ResetCounters()` — reset test state
- `GetResults()` — return pass/fail/errors dict
- `CheckTuple3(r, label)` — validate Tuple3 return

### Variables (impl_config.py)

| Variable       | Description                                                |
| -------------- | ---------------------------------------------------------- |
| `self.state` | dict with config, catalog, results, profiles, watches, env |

### Rules

- `@ghost` — Ghost Header present
- `@vbsty` — VBStyle Header present
- `@no<decorators|print|hardcoded_paths>` — No decorators, print, or hardcoded paths
- `Run(command, params)` dispatch pattern
- Tuple3 returns: `(ok, data, error)`
- `self.state` dict (no `self._`)

---

## Config_efl_brain.py

**Path:** `efl_brain/Config_efl_brain.py`
**Pattern:** Flat UPPERCASE constants + VBStyle class with Run() dispatch (1009 lines)
**DB:** `efl_brain/efl_brain.db` (SQLite)
**Template:** `dom_config` from `vb_shared.code_classes` (id=278)

### Variables (module-level constants — backward compat)

| Category          | Constants                                                        |
| ----------------- | ---------------------------------------------------------------- |
| Paths             | `BASE_DIR`, `DB_PATH`, `SCHEMA_PATH`                             |
| MySQL             | `MYSQL_CONFIG` dict (host, user, password, database)             |
| Pragma            | `PRAGMA_FOREIGN_KEYS`                                            |
| Target Classes    | `TARGET_CLASSES` list (114 class names for ingestion)            |
| Engine Scripts    | `ENGINE_SCRIPTS` list (6 scripts to ingest)                      |
| Schema            | 17 table definitions (`SCHEMA_DOMAINS` through `SCHEMA_RULES`)   |
| Views             | 2 view definitions (`SCHEMA_VIEW_GRAPH_NODES`, `SCHEMA_VIEW_UNIT_RANKINGS`) |
| Indexes           | 22 index definitions in `SCHEMA_INDEXES` list                    |
| Seeds             | 3 seed SQL (`SEED_DOMAINS`, `SEED_UNIT_TYPES`, `SEED_VBSTYLE_CONTRACTS`) |
| Extra Tables      | `SQL_CREATE_TEST_FEEDBACK`, `SQL_CREATE_LEARNED_FIXES`, `SQL_CREATE_EXECUTION_LOG` |
| Lint Rules        | 37 rules in `LINT_RULES` list (id, description, severity, check_type, enabled) |
| Thresholds        | `MAX_LOB_COLUMNS`, `MAX_COLUMNS_PER_TABLE`, `MAX_INDEXES_PER_TABLE`, `MAX_FK_PER_TABLE`, `MIN_ROW_COUNT` |
| Reserved Words    | `SQL_RESERVED_WORDS` list (30 words)                             |
| VBStyle           | `VBSTYLE_REQUIREMENTS` list (10 requirements)                    |

### VBStyle Class: ConfigEflBrain

| Component       | Methods                                                              |
| --------------- | -------------------------------------------------------------------- |
| Main            | `Run(command, params)`, `_get`, `_set`, `_mysql`, `_vbstyle`, `read_state`, `set_config` |
| SchemaConfig    | `Run`, `_all`, `_tables`, `_views`, `_indexes`, `_seed`, `_full_schema`, `read_state`, `set_config` |
| LintConfig      | `Run`, `_rules`, `_thresholds`, `_reserved`, `_enabled`, `read_state`, `set_config` |
| TargetConfig    | `Run`, `_all`, `_classes`, `_scripts`, `read_state`, `set_config`   |
| BracketProp     | `set`, `reset`, `to_dict`                                            |
| BracketContainer| `add_prop`, `add_container`, `get_prop`, `get_container`, `get`, `set`, `to_dict` |

### Run() Dispatch Commands

| Command      | Returns                                        |
| ------------ | ---------------------------------------------- |
| `get`        | Config value by key                            |
| `set`        | Set config value by key                        |
| `schema`     | All schema components (tables, views, indexes) |
| `seed`       | Seed SQL statements                            |
| `lint`       | Lint rules list                                |
| `targets`    | Target classes + engine scripts                |
| `mysql`      | MySQL connection config                        |
| `vbstyle`    | VBStyle requirements list                      |
| `read_state` | Full state snapshot                            |
| `set_config` | Bulk set config values                         |

### Rules

- `@ghost(33)` — Ghost Header present
- `@vbsty(34)` — VBStyle Header present
- `@clshdr(36)` — Class header present
- `@mthdr(37)` — Method headers present
- `@pascal(38)` — PascalCase class names
- `@upper(39)` — UPPERCASE constants
- `@print(22)` — No print statements
- `@decorators(20)` — No decorators
- `@hardcode(24)` — No hardcoded paths, all from BASE_DIR
- `@run(43)` — Run() dispatch present
- `@t3(50)` — Tuple3 returns `(ok, data, error)`
- `@state(41)` — `self.state` dict
- `@ctor(40)` — `__init__(mem, db, param)` constructor
- Singleton: `cfg = ConfigEflBrain()` at module bottom
- Backward compat: module-level constants preserved for existing imports

---

## Config_gui_engine.py

**Path:** `gui_engine/Config.py` + `gui_engine/config_extractor.py`
**Pattern:** Auto-generated flat constants

### Variables (Config.py)

| Category    | Constants                                                                                                                                                                                                   |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DB Paths    | `DB_PATH_V2`, `DB_PATH_V4`, `DB_PATH_TOKEN_REGISTRY`                                                                                                                                                  |
| Defaults    | `DEFAULT_ORDER_INDEX`                                                                                                                                                                                     |
| Fallbacks   | `FALLBACK_COLOR_BORDER`, `FALLBACK_FORMAT_BORDER_WIDTH`, `FALLBACK_MATCH_REASON`, `FALLBACK_PRIORITY`, `FALLBACK_SCORE`                                                                           |
| Table Names | `TABLE_BASE_SCORE`, `TABLE_CONDITION_EXPRESSION`, `TABLE_GUI_DECISION`, `TABLE_GUI_UI_DB`, `TABLE_MATCH_REASON`, `TABLE_MAX_SCORE`, `TABLE_RESOLUTION_EXPRESSION`, `TABLE_SCORE_EXPRESSION` |
| Booleans    | `BOOL_FALSE`, `BOOL_TRUE`                                                                                                                                                                               |
| Sizes       | `SIZE_0`, `SIZE_1`, `SIZE_2`, `SIZE_4`, `SIZE_8`, `SIZE_20`, `SIZE_100`                                                                                                                       |
| Ports       | `PORT_2026`                                                                                                                                                                                               |
| Floats      | `NUM_0_3`                                                                                                                                                                                                 |

### config_extractor.py

- Regex-based extractor (no AST needed)
- Reads Python files and extracts config-like values
- Outputs `Config.py` with UPPERCASE constants
- Extracts: module constants, strings, numbers, defaults, get fallbacks, classes, methods

### Rules

- Auto-generated by `config_extractor.py`
- All constants UPPERCASE
- No class wrapper — flat module constants
- Sources documented in header comment

---

## Config_qa_engine.py

**Path:** `qa_engine/Config_qa_engine.py`
**Pattern:** Flat UPPERCASE constants + pipeline mode dicts

### Variables

| Category       | Constants                                                                                     |
| -------------- | --------------------------------------------------------------------------------------------- |
| Identity       | `QA_ENGINE_VERSION`, `QA_ENGINE_NAME`                                                     |
| Paths          | `CONFIG_JSON_PATH`, `BERT_SQUAD_MODEL_PATH`, `PINNACLE_DB_PATH`, `TEST_COLLECTION`    |
| Pipeline Modes | `PIPELINE_MODE_A` through `PIPELINE_MODE_R`, `PIPELINE_MODES` dict, `MODE_NAMES` dict |

### Pipeline Modes

- **A:** embed → search
- **B:** embed → search → qa_extract → classify
- **C:** embed → search → qa_extract → classify → llm_format
- **D:** embed → search → llm_extract → classify
- **E:** qa_extract → classify
- **R:** embed → search → route → classify

### Rules

- `@ghost` — Ghost Header present
- `@vbsty` — VBStyle Header present
- `@no<decorators|print|hardcoded_paths>` — No decorators, print, or hardcoded paths
- All constants UPPERCASE
- Paths derived from `BASE_DIR`
- No hardcoded values in engine or runners

---

## Config_svg_engine.py

**Path:** `svg_engine/Config_svg_engine.py`
**Pattern:** Flat UPPERCASE constants + theme presets dict

### Variables

| Category     | Constants                                                                                                                         |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| Identity     | `SVG_ENGINE_VERSION`, `SVG_ENGINE_NAME`                                                                                       |
| Paths        | `LIB_PATH`, `C_SOURCE_PATH`, `QA_CONFIG_PATH`, `BERT_SQUAD_MODEL_PATH`                                                    |
| Scene        | `SCENE_WIDTH`, `SCENE_HEIGHT`, `ANIMATION_FRAMES`, `ANIMATION_FPS`, `MAX_OBJECTS`, `MAX_KEYFRAMES`, `MAX_PARTICLES` |
| Object Types | `OBJECT_TYPES` list (16 types)                                                                                                  |
| Themes       | `THEME_PRESETS` dict                                                                                                            |

### Rules

- `@ghost` — Ghost Header present
- `@vbsty` — VBStyle Header present
- `@no<decorators|print|hardcoded_paths>` — No decorators, print, or hardcoded paths
- All constants UPPERCASE
- Paths derived from `BASE_DIR` or `QA_ENGINE_DIR`
- No hardcoded values in engine or UI

---

## Config_MAC_Config.py

**Path:** `MAC_Config/config_email.py`
**Pattern:** Class attributes with env var loading

### Variables

| Category | Attributes                                                   |
| -------- | ------------------------------------------------------------ |
| Base     | `BASE_DIR`                                                 |
| Email    | Yahoo IMAP/SMTP, Gmail IMAP/SMTP, Outlook IMAP/SMTP settings |
| OAuth    | Google OAuth2 credentials (from env vars)                    |
| MySQL    | Storage settings                                             |
| Folders  | Folder mappings                                              |
| Filters  | Filter keywords                                              |

### Rules

- `@ghost` — Ghost Header present
- `@vbsty` — VBStyle Header present
- `@hardcode` — NO hardcoded secrets, all from env vars
- `LoadEnv()` function — reads `.env` file if available
- All credentials from environment variables — NEVER hardcoded

---

## Config_Cascade_toolStack.py

**Path:** `Cascade_toolStack/config_seed.sql`
**Pattern:** SQL seed file (C binary config)

### Variables

| Key                       | Default               | Description                  |
| ------------------------- | --------------------- | ---------------------------- |
| mysql_host                | localhost             | MySQL server hostname        |
| mysql_user                | root                  | MySQL username               |
| mysql_pass                | (empty)               | MySQL password               |
| mysql_db                  | vb_shared             | Default database             |
| mysql_port                | 3306                  | MySQL port                   |
| default_limit             | 50                    | Default row limit per table  |
| qdrant_url                | http://localhost:6333 | Qdrant REST API URL          |
| qdrant_helper             | (empty)               | Path to msearch_qdrant.py    |
| qdrant_default_collection | dim_semantic          | Default Qdrant collection    |
| qdrant_default_top        | 10                    | Default vector results count |
| vbcheck_path              | (empty)               | Path to vbcheck binary       |

### Rules

- All values configurable — no hardcoded paths in C binary
- `CREATE TABLE IF NOT EXISTS config(key, value, description)`
- `INSERT OR IGNORE` — idempotent seeding
- Same key/value/description pattern as `chat_mover/Config.py`

---

## Cross-Cutting Config Rules (from VBStyle /code workflow)

These rules apply to ALL config files:

| #  | Tag             | Rule                                                                            |
| -- | --------------- | ------------------------------------------------------------------------------- |
| 19 | `@underscore` | No `_` in class names                                                         |
| 20 | `@decorators` | No `@property` / `@staticmethod` / `@classmethod` (except config getters) |
| 21 | `@enums`      | No enums                                                                        |
| 22 | `@print`      | No print statements                                                             |
| 23 | `@hidden`     | No hidden or implicit behavior                                                  |
| 24 | `@hardcode`   | Nothing hardcoded — all values configurable                                    |
| 25 | `@tabs`       | No tabs                                                                         |
| 26 | `@whitespace` | No trailing whitespace                                                          |
| 33 | `@ghost`      | Ghost Header present                                                            |
| 34 | `@vbsty`      | VBStyle Header present                                                          |
| 35 | `@cstyle`     | C-style code formatting                                                         |
| 36 | `@clshdr`     | Class header required                                                           |
| 37 | `@mthdr`      | Method header required                                                          |
| 38 | `@pascal`     | PascalCase class names                                                          |
| 39 | `@upper`      | UPPERCASE constants                                                             |
| 52 | `@auth`       | Authority documented                                                            |
| 54 | `@rpt`        | Report structure                                                                |

### Config-Specific Rules (not applicable to config files)

| #  | Tag        | Note                                                              |
| -- | ---------- | ----------------------------------------------------------------- |
| 40 | `@ctor`  | Constructor — config uses `__init__` for loading, not MemUnit  |
| 41 | `@state` | `self.state` dict — config uses class attributes or properties |
| 43 | `@run`   | `Run()` dispatch — config is passive, no dispatch              |
| 45 | `@cfg`   | Config accessor — config IS the accessor                         |
| 50 | `@t3`    | Tuple3 returns — config returns values, not tuples               |

### Common Patterns Across All Configs

1. **BASE_DIR** — `os.path.dirname(os.path.abspath(__file__))` or `Path(__file__).parent`
2. **Env var overrides** — `os.environ.get("VAR_NAME", default)`
3. **Singleton** — `cfg = Config()` at module bottom
4. **Embedded schema** — SQL string constant for cold boot
5. **Docs as constants** — `ABOUT`, `HELP`, `README` as string constants
6. **No external files** — everything in one Python file or SQLite DB
7. **UPPERCASE constants** — all config values use `UPPER_CASE` naming
8. **Ghost + VBStyle headers** — every config file has both
