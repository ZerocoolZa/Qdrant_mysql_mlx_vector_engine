# Ghost — Architecture & Planning Document

> **Status**: Draft for discussion. QA prototype (`qa_prototype.py`) working — 3-model pipeline tested.
> **Last updated**: 2026-06-21

---

## 1. What Is Ghost?

Ghost is a local AI brain. The user talks to it through a CLI or GUI. Behind the scenes, three services do the work:

```
User
  │
  ▼
Ghost CLI / GUI
  │
  ▼
GhostAPI (FastAPI)
  │
  ├── MLX    → runs LLM + embedding models on Apple Silicon
  ├── Qdrant → stores and searches vectors (semantic memory)
  └── MySQL  → stores structured data (projects, files, metadata, knowledge)
```

The user never sees MLX, Qdrant, or MySQL. They just talk to Ghost.

---

## 2. Existing Infrastructure (Discovered)

### MySQL — 11 Databases

| Database | Tables | Key contents |
|----------|--------|-------------|
| `vb_shared` | 59 | code_classes (247), tokens (281), token_master (5755), learned_rules (10341), know_nodes (1603), know_questions (132), know_answers (118), know_solutions (329), gui_tokens (18), class_understandings (33), class_graph (36), designrationale (273), rules (281), table_registry (69) |
| `CODEBASE` | 20 | python_files (786K), c_files (41K), swift_files (10K), json_files (12K), markdown_files (28K), yaml_files (6K), directories (16K), file_checkpoint (414K), ingestion_jobs (434K) |
| `vb_ingestion` | 24 | markdown_files (17K), json_files (3.9K), yaml_files (83), paths (2.6K), classifications (32) |
| `vbstyle_documents` | 31 | ingested_documents (3.9K), classes (249), methods (1.6K), words (28K), word_locations (248K), table_purpose_registry (31) |
| `vb_code_test` | 3 | vb_classes (851), vb_methods (12K), vb_class_test_results (1.3K) |
| `qa_system` | 10 | files (39), words (7K), word_locations (473K), qa_log (39) |
| `token_registry` | 3 | File_index (2), folder_registry (1), file_extension (2) |

**Connection**: `mysql -u root` (no password, localhost, port 3306)

### Qdrant — Already Running (13 Collections)

```
COLLECTION              POINTS    DIMS
dim_bracket               220     384
dim_capability          1388     384
dim_control_flow        3169     384
dim_data_flow           2040     384
dim_dependency          3191     384
dim_execution           2997     384
dim_file                   0     384
dim_lexical             4000     384
dim_lifecycle             187     384
dim_semantic            2291     384
dim_structural          4000     384
dim_type                1035     384
memory                     1     768
```

**URL**: `http://localhost:6333`
**Embedding model**: `BAAI/bge-small-en-v1.5` (384-dim, via sentence_transformers)
**Note**: `memory` collection uses 768-dim (different model)

### msearch Binary — Already Built

Location: `/Users/wws/bin/msearch` (Mach-O arm64, with `msearch.c` source + `msearch_qdrant.py` helper)

Capabilities:
- MySQL keyword search across all tables in any database
- Qdrant vector search (semantic, multi-dimension, hybrid)
- Auto-embeds queries via BGE (sentence_transformers)
- JSON output mode for programmatic use
- `--all-db` searches across vb_shared + CODEBASE
- `--hybrid` combines MySQL + Qdrant results
- `--qstats` shows collection stats
- `--where` shows where to store new data (routing)
- `--vbstyle` runs VBStyle enforcer via vbcheck

### Existing Binaries in /Users/wws/bin/

| Binary | Purpose |
|--------|---------|
| `msearch` | MySQL + Qdrant vector search |
| `ghostctl` | Ghost maintenance (clean, pip, py) |
| `vbcheck` | VBStyle enforcer |
| `smartcli` | Smart CLI |
| `wcmd` | Command tool |
| `dir` | Directory tool |
| `Cleaner` | Cleanup tool (C binary) |
| `db_exec_demo` | DB execution demo (C binary) |

### Existing GUI System

Location: `/Users/wws/contestsystem/my_new_repo/GuiSystem/`

- `engine.py` (1045 lines) — 100% config-driven PyQt6 renderer
  - `WidgetBuilder.Run(command, params) -> Tuple3` — VBStyle pattern
  - `EventHandler` — signal/slot controller
  - `ConfigWatcher` — hot-reload JSON configs
  - `AppWindow` — generic QMainWindow driven by config
  - `WIDGET_REGISTRY` — maps type strings to PyQt6 classes
  - Supports: QTextEdit, QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox, QSlider, QSpinBox, QFrame, QWidget, QGroupBox, QProgressBar, QRadioButton, QTabWidget, QSplitter, QScrollArea, QStackedWidget, QToolBar, QTableView, QTreeView, QListView, FaceWidget, ChatBubble

- `config_store.py` (481 lines) — SQLite-backed config storage
  - `ConfigStore.Run(command, params) -> Tuple3` — VBStyle pattern
  - Tables: gui_configs, gui_widgets, gui_annotations, generation_runs, constraints

- `model_backend.py` — MLX model backend
- `voice.py` — voice interface
- `webcam.py` — webcam interface
- `main.py` — entry point

### Existing MLX/Embedding Systems (from ContextRAM)

- **BrainChat v100-v400** (GhostEmbedder/) — MLX embeddings (bge-small-en-v1.5-8bit), Qwen2.5-Coder LLM, entity extraction, graph traversal, semantic search
- **CognitiveBrain** (KIMIK2.6) — full reasoning brain with ask/qna_query/reason_all/learn/remember
- **CoreML models**: TokenEmbedder, CodeEmbedder, MiniLM-L6-v2 (384dim), CustomReverseEmbedder

### VBStyle Patterns (from ContextRAM)

- Every class: `Run(command, params) -> Tuple[int, Any, Optional[str]]`
- Returns `(1, data, None)` on success, `(0, None, error)` on failure
- `self.state = {}` dict (no `self._` private attrs)
- No raw `open()`, no raw `mysql.connect()`, no `json.load()`
- Config via BCL (Bracket Configuration Language), not JSON
- MemUnit is the bus — classes communicate through `mem.get/put`

---

## 3. Config Architecture — The Central `config.py`

### Design Principles

1. **Single source of truth** — every configurable value lives in `config.py`
2. **GUI-driven** — a property panel GUI reads/writes these settings
3. **Tree-structured** — settings organized hierarchically (MySQL → host, port, user, ...; MLX → model, temp, ...)
4. **Searchable** — the GUI has a search bar to find any setting quickly
5. **Combo boxes** — enum-like settings get dropdowns (e.g. embedding model, distance metric)
6. **No hardcoding** — everything configurable, nothing buried in service code

### Config Tree Structure

```
config.py
│
├── MySQL
│   ├── host              [string]    "localhost"
│   ├── port              [int]       3306
│   ├── user              [string]    "root"
│   ├── password          [string]    ""
│   ├── database          [combo]     vb_shared | CODEBASE | vb_ingestion | vbstyle_documents | vb_code_test | qa_system | token_registry
│   ├── readonly_dbs      [list]      ["CODEBASE", "vb_ingestion", "vbstyle_documents"]
│   ├── pool_size         [int]       5
│   └── connect_timeout   [int]       10
│
├── Qdrant
│   ├── host              [string]    "localhost"
│   ├── port              [int]       6333
│   ├── url               [string]    "http://localhost:6333"  (derived)
│   ├── collections       [list]      ["dim_semantic", "dim_structural", ...]
│   ├── default_collection [combo]    dim_semantic | dim_structural | dim_dependency | ...
│   ├── embedding_dims    [int]       384
│   ├── distance_metric   [combo]     Cosine | Euclid | Dot
│   ├── batch_size        [int]       100
│   └── search_limit      [int]       10
│
├── MLX
│   ├── llm_model         [combo]     Qwen2.5-Coder-7B-4bit | Llama-3.2-3B-Instruct-4bit | custom
│   ├── llm_model_path    [string]    ""  (if combo = custom)
│   ├── embed_model       [combo]     BAAI/bge-small-en-v1.5 | mlx-community/bge-small-en-v1.5-mlx | custom
│   ├── embed_model_path  [string]    ""  (if combo = custom)
│   ├── embed_dims        [int]       384
│   ├── max_tokens        [int]       512
│   ├── temperature       [float]     0.7
│   ├── quantization      [combo]     4bit | 8bit | none
│   └── system_prompt     [text]      "You are Ghost, a local AI assistant..."
│
├── API
│   ├── host              [string]    "127.0.0.1"
│   ├── port              [int]       8000
│   ├── cors_origins      [list]      ["*"]
│   ├── api_key           [string]    ""  (empty = no auth)
│   └── debug             [bool]      True
│
├── CLI
│   ├── api_base_url      [string]    "http://127.0.0.1:8000"  (derived)
│   ├── output_format     [combo]     text | json | rich
│   └── timeout           [int]       30
│
├── GUI
│   ├── theme             [combo]     dark | light | auto
│   ├── window_width      [int]       800
│   ├── window_height     [int]       600
│   ├── config_store_path [string]    "~/.ghost/config_store.db"
│   └── property_panel    [bool]      True
│
├── Paths
│   ├── env_file          [string]    ".env"
│   ├── config_store      [string]    "~/.ghost/ghost.db"  (SQLite, BCL-formatted values)
│   ├── log_file          [string]    "~/.ghost/ghost.log"
│   └── data_dir          [string]    "~/.ghost/"
│
├── msearch
│   ├── binary_path       [string]    "/Users/wws/bin/msearch"
│   ├── qdrant_helper     [string]    "/Users/wws/bin/msearch_qdrant.py"
│   └── default_db        [string]    "vb_shared"
│
└── Logging
    ├── level             [combo]     DEBUG | INFO | WARNING | ERROR
    ├── format            [string]    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    └── to_file           [bool]      True
```

### Config Persistence Flow

```
.env file (defaults)
      |
      v
config.py (loads .env, exposes Config object)
      |
      +----------------+----------------+
      |                |                |
      v                v                v
  Services           API              CLI
      |                |                |
      |     +----------+                |
      |     |  GUI Property             |
      |     |  Panel (tree)             |
      |     |  + search bar             |
      |     |  + combo boxes            |
      |     +----------+                |
      |                |                |
      |                v                |
      |     SQLite config table  <--- GUI saves |
      |     (BCL-formatted values)                |
      |                |                |
      +----------------+----------------+
                  config.py reloads
```

### GUI Property Panel Design

```
+-- Ghost Settings ----------------------------------------+
| [Search: __________________________] [search icon]      |
|                                                         |
|  v MySQL                                                |
|    host         = localhost                             |
|    port         = 3306                                  |
|    user         = root                                  |
|    password     = ****                                  |
|    database     = [vb_shared        v]                  |
|    pool_size    = 5                                     |
|                                                         |
|  v Qdrant                                               |
|    host         = localhost                             |
|    port         = 6333                                  |
|    default_coll = [dim_semantic     v]                  |
|    embed_dims   = 384                                   |
|    distance     = [Cosine           v]                  |
|                                                         |
|  v MLX                                                  |
|    llm_model    = [Qwen2.5-Coder-7B v]                 |
|    embed_model  = [bge-small-en     v]                  |
|    max_tokens   = 512                                   |
|    temperature  = 0.7                                   |
|    quantization = [4bit            v]                   |
|                                                         |
|  v API                                                  |
|    host         = 127.0.0.1                             |
|    port         = 8000                                  |
|    debug        = [x]                                   |
|                                                         |
|  v Paths                                                |
|    env_file     = .env                                  |
|    log_file     = ~/.ghost/ghost.log                    |
|                                                         |
|  [Save]  [Reset]  [Import]  [Export]                    |
+---------------------------------------------------------+
```

- **Tree structure**: expandable/collapsible categories (MySQL, Qdrant, MLX, ...)
- **Search bar**: type "port" -> highlights all port settings across categories
- **Combo boxes**: dropdowns for enum-like values (database name, model name, metric, ...)
- **Save/Reset/Import/Export**: persist to SQLite config table (BCL format), reset to defaults, import/export .env files

### Config Schema (for GUI auto-generation)

The config will expose a schema that the GUI uses to auto-generate the property panel. Schema is defined in BCL notation:

```
[@schema]{
  (@section<mysql>;
    @field<host>(@type<str>;@default<"localhost">;@label<"Host">);
    @field<port>(@type<int>;@default<3306>;@label<"Port">);
    @field<database>(@type<combo>;@default<"vb_shared">;@label<"Database">;
      @options<("vb_shared";"CODEBASE";"vb_ingestion";"vbstyle_documents";"vb_code_test";"qa_system";"token_registry")>);
    @field<password>(@type<password>;@default<"">;@label<"Password">);
  );
  (@section<qdrant>;
    @field<default_collection>(@type<combo>;@default<"dim_semantic">;@label<"Default Collection">;
      @options<("dim_semantic";"dim_structural";"dim_dependency";...)>);
  );
  ...
}
```

The GUI reads this schema, builds the tree + combo boxes + text fields automatically.

---

## 4. What Ghost Does (Use Cases)

| Command | What happens | Backends touched |
|---------|-------------|-----------------|
| `ghost ask "what is BCL?"` | LLM answers, with context from Qdrant | MLX + Qdrant |
| `ghost search "auth handling"` | Semantic vector search | Qdrant (via msearch) |
| `ghost remember file.txt` | Embed -> Qdrant + MySQL metadata | MLX + Qdrant + MySQL |
| `ghost explain class Report` | Find class in MySQL, pull Qdrant context, LLM explains | MySQL + Qdrant + MLX |
| `ghost project create myapp` | Store project in MySQL | MySQL |
| `ghost report myapp` | Summarize project from MySQL + Qdrant | MySQL + Qdrant |
| `ghost embed "some text"` | Generate embedding | MLX |
| `ghost serve` | Start FastAPI server | All |
| `ghost settings` | Open settings GUI property panel | GUI |

---

## 5. Reuse Strategy — Don't Reinvent

| Need | Existing solution | How to reuse |
|------|------------------|-------------|
| Vector search | `msearch` binary + `msearch_qdrant.py` | Call via subprocess or import functions |
| Embeddings | `msearch_qdrant.py` `embed()` (BGE, 384-dim) | Import or replicate |
| Qdrant connection | `msearch_qdrant.py` `qdrant_get/post()` | Same REST API pattern |
| GUI rendering | `GuiSystem/engine.py` `WidgetBuilder` | Use or adapt for settings panel |
| Config storage | `GuiSystem/config_store.py` `ConfigStore` | SQLite-backed config store pattern |
| MySQL access | Existing `root@localhost` connection | Same credentials |
| VBStyle patterns | `Run()/Tuple3/state dict` | Follow for all new code |
| LLM | BrainChat's Qwen2.5-Coder via MLX | Reuse model path/config |

---

## 6. Architecture — File Structure

```
ghost/
├── config.py              <- ALL settings, schema, load/save, env loading
├── models/                <- Pydantic schemas (request/response)
│   ├── chat.py
│   ├── memory.py
│   ├── search.py
│   └── project.py
├── services/              <- Internal services (the three backends)
│   ├── mlx_service.py     <- LLM generation + embedding generation
│   ├── qdrant_service.py  <- Vector storage + semantic search
│   └── mysql_service.py   <- Structured data CRUD
├── api/                   <- FastAPI server
│   └── server.py          <- All endpoints
├── cli/                   <- Typer CLI
│   └── ghost_cli.py       <- ghost ask, search, remember, etc.
├── gui/                   <- Settings GUI
│   ├── settings_gui.py    <- Property panel with tree + search + combos
│   └── config_schema.py   <- Auto-generates panel from config schema
└── setup.py               <- `ghost` command entry point
```

---

## 7. Decisions (Locked In)

1. **MySQL database strategy**: Ghost **reads from ALL databases** (vb_shared, CODEBASE, vb_ingestion, vbstyle_documents, vb_code_test, qa_system, token_registry). If Ghost needs to write, the **GUI provides an option to create a new database** — no hardcoded write target.

2. **msearch reuse**: **Copy the content** from `msearch_qdrant.py` (and `msearch.c` if needed) into our project. It becomes a **VBStyle class** — not a subprocess call. The search logic lives inside Ghost as a proper service.

3. **GUI engine reuse**: **Copy `engine.py`** from `GuiSystem/` into our project. The settings property panel is built on top of the existing `WidgetBuilder` pattern.

4. **VBStyle compliance**: **100% for all projects.** Every class uses `Run(command, params) -> Tuple3`, `self.state` dict, no raw `open()`/`mysql.connect()`/`json.load()`, PascalCase classes, UPPERCASE constants.

5. **Config persistence format**: **BCL (Bracket Configuration Language)** is the config format. Example: `[@mysql_host]{("value"; "localhost")}`. **Storage medium is SQLite** (not JSON — JSON is never an option). The config values are serialized as BCL tokens and stored in a SQLite database. The GUI reads/writes BCL-formatted config values to SQLite.

6. **Embeddings**: Configurable — both `sentence_transformers` (BGE, as msearch uses) and MLX (as BrainChat uses) are options. Default: `sentence_transformers` with `BAAI/bge-small-en-v1.5` (384-dim) since that's what the existing Qdrant collections use.

7. **LLM model**: Configurable combo. Default: `Qwen2.5-Coder` (matching BrainChat). Options include Llama-3.2-3B and custom paths.

8. **QA pipeline**: 5-mode switchable cognition graph proven — 28-question benchmark across 10 aspects. Mode D (Retrieval + Qwen 1.5B LLM, no BERT) wins at 89% answer accuracy. Mode B (Retrieval + BERT QA) at 57%. Mode C (BERT + LLM format) = Mode B (no gain from formatting). See `GhostQAEngine.py`, `five_mode_runner.py`, and Appendix A.18.

9. **SQLite-as-filesystem**: Methods stored as rows (id, Method, BCL, Description, Class_id, Cat_id, Type_id). Linked tables: methods -> classes -> domains, methods -> categories, methods -> types. Config values in same SQLite DB in `config` table (BCL format).

10. **Config schema**: Config provides a schema for auto-generating the GUI property panel (tree structure, search, combo boxes).

### Key Constraint: No JSON

**JSON is never an option** for any storage, config, or data exchange in this project. All config persistence uses BCL format. All storage uses SQLite or MySQL. The GUI communicates with the API via Python objects / form data, not JSON files.

---

## 8. SQLite-as-Filesystem — Code Storage Architecture

### Concept

Ghost treats a **SQLite database as if it were a file system**. Instead of storing code in `.py` files on disk, methods are stored as **rows in a SQLite table**. This makes them easy to edit, test, version, and document with BCL.

### Table Schema

#### `methods` (primary table — each row = one method)

| Column         | Type    | Key | Description |
|---------------|---------|-----|-------------|
| id            | INTEGER | PK  | Auto-increment row ID |
| Method        | TEXT    |     | The actual Python code for the method |
| BCL           | TEXT    |     | BCL bracket metadata documenting the method's contract |
| Description   | TEXT    |     | Human-readable description of what the method does |
| Class_id      | INTEGER | FK  | -> classes.id (which class this method belongs to) |
| Cat_id        | INTEGER | FK  | -> categories.id (method category: service, domain, util, etc.) |
| Type_id       | INTEGER | FK  | -> types.id (method type: Run, helper, init, etc.) |

#### `classes` (each row = one VBStyle class)

| Column       | Type    | Key | Description |
|-------------|---------|-----|-------------|
| id          | INTEGER | PK  | Auto-increment |
| Class_name  | TEXT    |     | PascalCase class name (e.g. MlxService) |
| BCL         | TEXT    |     | BCL metadata for the class |
| Description | TEXT    |     | What the class does |
| Domain_id   | INTEGER | FK  | -> domains.id (which domain this class belongs to) |

#### `categories` (method categories)

| Column | Type    | Key | Description |
|-------|---------|-----|-------------|
| id    | INTEGER | PK  | Auto-increment |
| Name  | TEXT    |     | Category name (e.g. service, domain, utility, gui, cli) |
| BCL   | TEXT    |     | BCL metadata |

#### `types` (method types)

| Column | Type    | Key | Description |
|-------|---------|-----|-------------|
| id    | INTEGER | PK  | Auto-increment |
| Name  | TEXT    |     | Type name (e.g. Run, helper, init, dispatch, validate) |
| BCL   | TEXT    |     | BCL metadata |

#### `domains` (class domains)

| Column | Type    | Key | Description |
|-------|---------|-----|-------------|
| id    | INTEGER | PK  | Auto-increment |
| Name  | TEXT    |     | Domain name (e.g. mlx, qdrant, mysql, api, cli, gui) |
| BCL   | TEXT    |     | BCL metadata |

#### `config` (BCL-formatted config values)

| Column  | Type    | Key | Description |
|--------|---------|-----|-------------|
| id     | INTEGER | PK  | Auto-increment |
| Key    | TEXT    |     | Config key (e.g. mysql_host, qdrant_port) |
| BCL    | TEXT    |     | BCL-formatted value: `[@mysql_host]{("value"; "localhost")}` |
| Section| TEXT    |     | Category (mysql, qdrant, mlx, api, cli, gui, paths, msearch, logging) |

### Relationships

```
domains (1) ----< classes (N)
classes (1) ----< methods (N)
categories (1) --< methods (N)
types (1) ------< methods (N)
```

### BCL Documentation Per Method

Each method row has a `BCL` column that documents the method's contract:

```
[@Method<generate>]{(@class<MlxService>; @type<Run>; @returns<Tuple3>;
  @params<("prompt"; str; "system_prompt"; str; optional)>;
  @description<"Generate text using MLX LLM model">)}
```

This means:
- Every method is self-documenting
- The GUI can display BCL metadata alongside the code
- Tests can validate methods against their BCL contracts
- Search can index BCL tags for filtering

### Why SQLite Instead of Files?

- **Easy to edit**: GUI can edit method code in a text field, save directly to row
- **Easy to test**: Pull a method by ID, exec it, test it
- **Easy to version**: Track changes with timestamps or a history table
- **Easy to search**: SQL queries instead of grep
- **Easy to document**: BCL column right next to the code
- **Easy to link**: Class_id, Cat_id, Type_id FKs give structure
- **Portable**: One `.db` file contains the entire codebase

---

## 9. Pre-Populated Seed Data

The `types`, `categories`, `domains`, and `classes` tables are pre-populated at SQLite DB creation time. We know all of these upfront from the architecture.

### `domains` (seed)

| id | Name     | BCL |
|----|----------|-----|
| 1  | mlx      | `[@Domain<mlx>]{(@description<"MLX LLM + embedding model execution">)}` |
| 2  | qdrant   | `[@Domain<qdrant>]{(@description<"Vector storage and semantic search">)}` |
| 3  | mysql    | `[@Domain<mysql>]{(@description<"Structured data storage and queries">)}` |
| 4  | api      | `[@Domain<api>]{(@description<"FastAPI server and endpoints">)}` |
| 5  | cli      | `[@Domain<cli>]{(@description<"Typer CLI commands">)}` |
| 6  | gui      | `[@Domain<gui>]{(@description<"PyQt6 settings property panel">)}` |
| 7  | config   | `[@Domain<config>]{(@description<"Configuration management">)}` |
| 8  | msearch  | `[@Domain<msearch>]{(@description<"Search service ported from msearch">)}` |
| 9  | logging  | `[@Domain<logging>]{(@description<"Logging and diagnostics">)}` |

### `categories` (seed)

| id | Name     | BCL |
|----|----------|-----|
| 1  | service  | `[@Category<service>]{(@description<"Backend service class">)}` |
| 2  | domain   | `[@Category<domain>]{(@description<"VBStyle domain class">)}` |
| 3  | utility  | `[@Category<utility>]{(@description<"Utility/helper class">)}` |
| 4  | gui      | `[@Category<gui>]{(@description<"GUI component">)}` |
| 5  | cli      | `[@Category<cli>]{(@description<"CLI component">)}` |
| 6  | api      | `[@Category<api>]{(@description<"API endpoint handler">)}` |
| 7  | model    | `[@Category<model>]{(@description<"Pydantic request/response schema">)}` |

### `types` (seed)

| id | Name      | BCL |
|----|-----------|-----|
| 1  | Run       | `[@Type<Run>]{(@returns<Tuple3>; @description<"VBStyle dispatch entry point — THE only public method">)}` |
| 2  | init      | `[@Type<init>]{(@description<"Constructor / initialization">)}` |
| 3  | dispatch  | `[@Type<dispatch>]{(@description<"Internal command dispatcher inside Run">)}` |
| 4  | validate  | `[@Type<validate>]{(@description<"Input validation">)}` |
| 5  | embed     | `[@Type<embed>]{(@returns<list[float]>; @description<"Generate embedding vector">)}` |
| 6  | generate  | `[@Type<generate>]{(@returns<str>; @description<"Generate text via LLM">)}` |
| 7  | search    | `[@Type<search>]{(@returns<list>; @description<"Search vectors or records">)}` |
| 8  | upsert    | `[@Type<upsert>]{(@returns<bool>; @description<"Insert or update">)}` |
| 9  | delete    | `[@Type<delete>]{(@returns<bool>; @description<"Delete a record or vector">)}` |
| 10 | create    | `[@Type<create>]{(@returns<int>; @description<"Create a new record">)}` |
| 11 | list      | `[@Type<list>]{(@returns<list>; @description<"List records">)}` |
| 12 | report    | `[@Type<report>]{(@returns<dict>; @description<"Generate summary report">)}` |
| 13 | connect   | `[@Type<connect>]{(@description<"Establish connection to backend">)}` |
| 14 | close     | `[@Type<close>]{(@description<"Close connection">)}` |

**NO `helper` type.** VBStyle does not use helpers. All logic goes through `Run()` dispatch. Internal methods are dispatched commands within `Run()`, not standalone helpers.

### `classes` (seed — planned VBStyle classes)

| id | Class_name      | Domain_id | Cat_id  | BCL |
|----|----------------|-----------|---------|-----|
| 1  | Config         | 7 (config) | 2 (domain) | `[@Class<Config>]{(@returns<Tuple3>; @description<"Central configuration management">)}` |
| 2  | MlxService     | 1 (mlx)   | 1 (service) | `[@Class<MlxService>]{(@returns<Tuple3>; @description<"MLX LLM + embedding execution">)}` |
| 3  | QdrantService  | 2 (qdrant) | 1 (service) | `[@Class<QdrantService>]{(@returns<Tuple3>; @description<"Qdrant vector storage and search">)}` |
| 4  | MysqlService   | 3 (mysql) | 1 (service) | `[@Class<MysqlService>]{(@returns<Tuple3>; @description<"MySQL structured data access">)}` |
| 5  | SearchService  | 8 (msearch) | 1 (service) | `[@Class<SearchService>]{(@returns<Tuple3>; @description<"Hybrid search ported from msearch">)}` |
| 6  | GhostAPI       | 4 (api)   | 6 (api)   | `[@Class<GhostAPI>]{(@returns<Tuple3>; @description<"FastAPI server with all endpoints">)}` |
| 7  | GhostCLI       | 5 (cli)   | 5 (cli)   | `[@Class<GhostCLI>]{(@returns<Tuple3>; @description<"Typer CLI entry point">)}` |
| 8  | SettingsGUI    | 6 (gui)   | 4 (gui)   | `[@Class<SettingsGUI>]{(@returns<Tuple3>; @description<"PyQt6 property panel for config">)}` |
| 9  | CodeStore      | 7 (config) | 1 (service) | `[@Class<CodeStore>]{(@returns<Tuple3>; @description<"SQLite-as-filesystem code storage">)}` |
| 10 | BCLParser      | 7 (config) | 3 (utility) | `[@Class<BCLParser>]{(@returns<Tuple3>; @description<"BCL bracket parsing and serialization">)}` |
| 11 | GhostQA        | 1 (mlx)   | 1 (service) | `[@Class<GhostQA>]{(@returns<Tuple3>; @description<"5-mode QA engine: retrieval / BERT QA / BERT+LLM / LLM-only / QA-only. Benchmark-proven: Mode D (LLM) 89% answer accuracy, Mode B (BERT) 64%. See Appendix A.18">)}` |

### VBStyle Rules (enforced by `vbcheck`)

The `vbcheck` binary at `/Users/wws/bin/vbcheck` loads rules from MySQL `vb_shared.instructions` and enforces them on every `.py` file. The rules below are sourced from the real `vb_shared` database — the `rules` table (281 entries), `learned_rules` table (10,341 entries), `governance` table (58 entries), and `rule_tokens` table (bracket-format tokens with weights).

#### A. Prohibition Rules (mandatory — violation = fail)

These are the hard bans. No exceptions. No "just this once." Every file is checked.

| # | Rule ID | Rule | Description | Source |
|---|---------|------|-------------|--------|
| 1 | `no_decorators` | NO decorators | No @property, @staticmethod, @dataclass, @classmethod, @abstractmethod. No method/class/function decorators ever. | rules.id=6, severity=mandatory |
| 2 | `no_print` | NO print statements | No print() in class methods or authorities. Use Report class or return strings. Applies to Python (print), C (printf/fprintf/puts/perror), Swift (print). | rules.id=7, severity=mandatory. Mined from 35+ chat occurrences, confidence 0.95 |
| 3 | `no_hardcoded` | NO hardcoded paths | No hardcoded file paths, database paths, or config values. Everything from config/params. | rules.id=8, severity=mandatory. Mined from 104 chat occurrences, confidence 0.95 |
| 4 | `no_ABC` | NO ABC / inheritance | No Abstract Base Classes, no class inheritance, no interface inheritance. Every class is standalone. | rules.id=9, severity=mandatory |
| 5 | `no_flat` | NO flat class structure | No single flat class with all methods. Must use nested authority classes. | rules.id=10, severity=mandatory |
| 6 | `no_direct_db` | NO direct DB access in main class | DB operations must be in nested DB authority. Outer class only orchestrates. | rules.id=11, severity=mandatory |
| 7 | `no_utility_funcs` | NO utility functions | No _ok/_err/_safe helper wrapper functions. Use direct tuple returns only. | rules.id=5, severity=mandatory |
| 8 | `no_self_underscore` | NO self._ variables | All state in self.state dictionary. No self._cache, self._conn, self._init, etc. | rules.id=36/51/87/93/130 (listed 5 times). Token [@StateDictOnly] weight=92 |
| 9 | `no_imports` | NO direct imports between units | No direct imports, no file references. MemUnit is the bus. Components communicate through MemDB/MemBus. | rules.id=1 (no_direct), learned_rules |
| 10 | `no_enums` | NO enums | No `from enum import Enum`. Use constants or bracket tokens instead. | learned_rules, DEHWMP ban |
| 11 | `no_main_block` | NO \_\_main\_\_ blocks | Units are not scripts. No `if __name__ == "__main__"` in unit files. | learned_rules |
| 12 | `no_async` | NO async/await | No async functions, no await. Synchronous only. | learned_rules |
| 13 | `no_context_mgrs` | NO context managers on custom objects | No `with` statements on custom objects. Built-in `with open()` is OK (but raw open() is still banned). | learned_rules |

**The DEHWMP Ban**: The bracket tag registry (doc_1772) explicitly bans these patterns:
- **D**ecorators ([@DECO]) — function wrapping function, hidden behavior
- **E**nums ([@ENUM]) — fixed enumeration, inflexible
- **H**idden ([@HIDN]) — implicit behavior, magic
- **W**rappers ([@WRAP]) — unnecessary wrapping
- **M**agic ([@MGC]) — magic methods, dunder abuse

#### B. Constraint Rules (guideline — structural requirements)

These define the shape of every VBStyle class. Not optional — they are the structural contract.

| # | Rule | Description | Source |
|---|------|-------------|--------|
| 1 | **1 class = 1 domain = 1 authority** | Single outer class = domain controller. Nested inner classes = authorities (sub-domains). Visual hierarchy == code hierarchy. | rules.id=1, category=constraint |
| 2 | **Fixed 5-element state structure** | `self.state = {config: {}, catalog: [], results: [], memunit: mem, db_manager: db}` | rules.id=2, category=constraint |
| 3 | **Strict Tuple3 return pattern** | Success: `(1, data, None)`. Failure: `(0, {}, (ERROR_CODE, error_msg, 0))`. No bare returns, no dict returns, no 4-tuples. | rules.id=4, category=constraint |
| 4 | **Nested authority classes** | Nested classes end with `Authority` suffix (e.g., `JsonConfig`, `EnvConfig`, `GrepSearch`). Each has own `Run()` method, instantiated on demand. | rules.id=12-13, category=constraint |
| 5 | **Standard \_\_init\_\_ signature** | `def __init__(self, mem=None, db=None, param=None)` — three optional params, no others. | rules.id=14, category=constraint |
| 6 | **Run method dispatch pattern** | Outer Run dispatches to nested authorities: `return self.AuthorityName(mem=self.state['memunit'], db=self.state['db_manager'], param=params).Run(subcommand, params)` | rules.id=15, category=constraint |
| 7 | **Annotation syntax** | `#[@VBSTYLE]{[@auth<system>][@role<domain_name>][@return<Tuple3>][@orch<none>][@no<decorators\|print\|hardcoded_paths\|abc\|inheritance>]}` | rules.id=16, category=constraint |
| 8 | **100% pattern consistency** | VBStyle is a rigid, enforced standard with zero deviation across all domain files. | rules.id=17, category=constraint |
| 9 | **UNKNOWN_COMMAND error handling** | Every Run method must return `(0, {}, (UNKNOWN_COMMAND, f"Unknown command: {command}", 0))` for unknown commands. Never raise. | rules.id=18, category=constraint |
| 10 | **read_state returns state snapshot** | `read_state()` must return `(1, {state: self.state}, None)` | rules.id=19, category=constraint |
| 11 | **set_config updates config** | `set_config(values)` must update `self.state['config']` and return `(1, self.state['config'], None)` | rules.id=20, category=constraint |
| 12 | **Weight position in brackets** | Weight MUST be the last element in every bracket tuple. Format: `{("step1";"step2";92)}` | rules.id=999, severity=critical |

#### C. Requirement Rules (mandatory — must exist)

| # | Rule | Description | Source |
|---|------|-------------|--------|
| 1 | **Mandatory methods** | Every class must implement `read_state()`, `set_config(values)`, and `Run(command, params)`. | rules.id=3, severity=mandatory |
| 2 | **Ghost header on line 1** | Every file starts with `#[Ghost{[filename][state][date][version][author]}]` | governance table, priority=1 |
| 3 | **VBStyle header on line 2** | Every file has `#[@VBSTYLE]{...}` annotation | governance table, priority=1 |

#### D. Verifier Rules (R001-R013, from doc_1594)

The VBStyle Verifier (`vbcheck`) checks every file against these automated rules:

| Rule ID | Check Name | Languages | What it checks | Message |
|---------|-----------|-----------|----------------|---------|
| R001 | `ghost_header` | py, c, swift, cs | Line 1 starts with `# Ghost{` or `#[Ghost{` | "Ghost header required" |
| R002 | `print_statements` | py | Not contains `print(` in non-comment lines | "print() not allowed" |
| R003 | `decorators` | py | Not contains `@property`, `@staticmethod`, etc. | "No decorators" |
| R004 | `enums` | py | Not contains `from enum import` | "No enums" |
| R005 | `abc_inheritance` | py | Not contains `ABC`, `ABCMeta`, `abstractmethod` | "No ABC/inheritance" |
| R006 | `raw_int_returns` | py | No bare `return 0` or `return 1` | "No raw int returns" |
| R007 | `printf_usage` | c | Not contains `printf(`, `fprintf(`, `puts(`, `perror(` | "No printf style output" |
| R008 | `print_swift` | swift | Not contains `print(` | "No print in Swift" |
| R009-R012 | Language-specific | various | Additional checks per language | Various |
| R013 | `hardcoded_config` | py, c, swift, cs | Not contains `config.ini`, `App_Claude`, `hardcoded_path` | "No hardcoded config values" |

#### E. Governance Rules (priority 1 — blocking gates)

From the `governance` table (58 entries, priority 1 = critical blocking gates):

| Governance Action | Description |
|-------------------|-------------|
| Check VBStyle compliance before DB ingestion | HARD BLOCKING GATE — no code enters DB without passing vbcheck |
| Create timestamped backup before DB modification | HARD BLOCKING GATE — no DB change without backup |
| Verify backup hashes before proceeding | SHA256 hash comparison before destructive operations |
| Investigate existing infrastructure before creating new | Check existing code/CLI/DB before building new mechanisms |
| Use database operations instead of file edits | DB is source of truth. Populate tables first, then regenerate files |
| Multi-angle code review | Single perspective misses 80% of issues. Review from multiple angles |
| VerifyBeforeSchemaSuggest | AI must run verification queries before suggesting schema changes |
| Defensive thinking everywhere | Check empty code, validate observations, limit file counts |
| Failure hardening | Specific exception handling, batch limits (max 10000 files) |
| Ghost Header pattern | File metadata scanning at file tops |
| VBStyle Header pattern | Rule codes, dispatch pattern in header |
| Run Dispatch pattern | Command dispatch via Run() returning Tuple3 |
| Constructor Signature pattern | Standard `__init__(self, mem=None, db=None, param=None)` |
| State Dictionary pattern | `self.state = {config: {}, catalog: [], results: []}` |

**Truth Hierarchy** (from governance table):

```
Governance (hard rules)  >  Semantic reasoning  >  Statistical patterns
```

A governance rule overrides any semantic reasoning. Semantic reasoning overrides statistical patterns.

#### F. Learned Rules (mined from chat data, confidence >= 0.9)

From the `learned_rules` table (10,341 entries). These are rules mined from real chat conversations between Wayne and AI models. The confidence score reflects how often the pattern was observed:

| Pattern | Occurrences | Confidence | Category |
|---------|-------------|------------|----------|
| Have print statements | 35 chats | 0.95 | general |
| print() call in method code | 18 chats | 0.95 | general |
| Have hardcoded default parameters | 104 chats | 0.95 | architecture |
| Have hardcoded paths, models, or db names | 104 chats | 0.95 | architecture |
| self._ usage without self.state | — | 0.95 | general |
| Raise exceptions for expected failures | — | 0.95 | error_handling |
| Add features, files, explanations unnecessarily | — | 0.95 | general |

#### G. Rule Tokens (bracket format, from `rule_tokens` table)

Rules are also encoded as bracket tokens with weights (0-100, higher = stronger):

| Token | Description | Weight |
|-------|-------------|--------|
| `[@StateDictOnly]` | No self._ variables, use self.state dictionary | 92 |
| `[@Domain]` | Each class must own exactly one domain/authority | — |
| `[@Run]` | Run(command, params) dispatch entry point | — |
| `[@T3]` | Tuple3 return: (ok, data, error) | — |
| `[@Ghost]` | All code must have Ghost Header | — |
| `[@VBSTY]` | All code must have VBStyle Header | — |
| `[@Pascal]` | Class names PascalCase, no underscores | — |
| `[@Ctor]` | Constructor: `__init__(self, mem=None, db=None, param=None)` | — |
| `[@Noself]` | No self._ variables, use self.state | — |
| `[@Print]` | Do not use print statements | — |
| `[@Hardcode]` | No hardcoded anything | — |
| `[@Decorators]` | No @property, @staticmethod etc. | — |
| `[@Enums]` | Do not use enums | — |

#### H. Enforcement Pipeline

**Enforcement**: Run `vbcheck` on every file before committing. Ghost will integrate `vbcheck` as a pre-save validation step when writing methods to the SQLite code store.

```
ghost write method -> vbcheck validation -> save to SQLite methods table
```

The full enforcement pipeline:

```
1. AI generates code
2. vbcheck validates code (R001-R013)
3. If fail -> violation stored in know_lessons -> correction stored in learned_rules
4. If pass -> code ingested into database (code_classes table)
5. Before ingestion: HARD BLOCKING GATE (governance check)
6. Before DB modification: timestamped backup + hash verification
7. After ingestion: code available for search (MySQL + Qdrant)
```

#### I. The Zero-Drift Philosophy

All rules derive from one principle: **Zero-Drift**. No drifting. No half-shapes. No broken syntax. The system stays exactly as designed.

- Every file has a Ghost header (no exceptions)
- Every method returns Tuple3 (no exceptions)
- Every state is in self.state (no self._ variables)
- Every path comes from config (no hardcoding)
- Every output goes through report() (no print())
- Every bracket is complete (no missing brackets)
- Every class owns one domain (no scattered ownership)

**The five-year proof**: Every rule is a battle scar from a real drift event. print() was banned because AI kept adding print(). self._ was banned because AI kept creating private variables. Hardcoding was banned because AI kept hardcoding paths. The rules are not theoretical — they are empirical.

### Seed Flow

```
1. Create SQLite DB (ghost.db)
2. Create all tables (methods, classes, categories, types, domains, config)
3. INSERT seed rows into domains (9 rows)
4. INSERT seed rows into categories (7 rows)
5. INSERT seed rows into types (14 rows)
6. INSERT seed rows into classes (11 rows)
7. config table starts empty — populated by Config class on first run
8. methods table starts empty — populated as we write each method
```

---

## 10. Proposed Build Order

1. **SQLite schema** — create the `.db` with tables: methods, classes, categories, types, domains, config
2. **config.py** — VBStyle class, reads/writes config table in SQLite (BCL format), env loading, schema for GUI
3. **Review config.py together** <- we stop here and review
4. **services/** — port msearch_qdrant.py as VBStyle class, mlx service, mysql service (stored as methods in SQLite)
5. **models/** — Pydantic schemas (API request/response, not for storage)
6. **api/server.py** — FastAPI endpoints
7. **cli/ghost_cli.py** — Typer CLI
8. **setup.py** — `ghost` entry point
9. **gui/settings_gui.py** — copy engine.py, build property panel (after core works)

---

## 11. Q&A — For Local AI to Answer

> **Instructions**: Fill in the answer below each question. Delete the question once answered and move the decision to Section 7 (Decisions). Leave any you're unsure about — Wayne will decide.

---

**Q1: MemUnit**

Ghost is standalone. MemUnit is in the MySQL common DB with many components. Should Ghost:
- (A) Build a lightweight MemUnit (shared state dict, mem.get/put interface)?
- (B) Import the existing MemUnit from contestsystem?
- (C) Skip MemUnit — classes are independent enough for this project?

If (A), what's the minimum interface needed?
If (B), what's the import path and what dependencies come with it?

**A1**: _(local AI fill in here)_

---

**Q2: FastAPI + VBStyle Decorator Conflict**

FastAPI uses `@app.get("/ask")` decorators. VBStyle bans decorators. Options:
- (A) Use FastAPI decorators — exception for API layer only
- (B) Write our own HTTP server (no framework decorators)
- (C) Use FastAPI's `app.add_api_route()` programmatic registration — no decorators
- (D) Fork FastAPI and write a BCL-based API layer

**A2**: _(local AI fill in here)_

---

**Q3: SQLite Methods Table — What Goes in the Method Column?**

Clarified that it's a DB manager pattern (params in, results out, SQL stored in config). But:
- Does the `Method` column contain SQL only?
- Or does it also contain Python code?
- If SQL only, where does Python logic live (embedding generation, LLM calls)?

**A3**: _(local AI fill in here)_

---

**Q4: engine.py Uses JSON Internally — How to Handle?**

engine.py's ConfigWatcher reads `.json` files. We said no JSON. Options:
- (A) Rewrite engine.py config loading to read SQLite/BCL
- (B) Keep engine.py as-is, feed it dicts from our BCL/SQLite layer (convert BCL -> dict at the boundary)
- (C) Copy engine.py and modify ConfigWatcher to read from SQLite

**A4**: _(local AI fill in here)_

---

**Q5: no_utility_funcs — Shared Validation Logic**

VBStyle bans `_ok/_err/_safe` wrappers. If multiple Run() commands need the same validation:
- (A) Duplicate validation in each branch
- (B) Nested ValidationAuthority class with own Run()
- (C) Validation in dispatch layer before routing

**A5**: _(local AI fill in here)_

---

**Q6: `__main__` Block Ban — CLI Entry Point**

VBStyle bans `if __name__ == "__main__"`. The `ghost` CLI needs an entry point. Options:
- (A) Separate `main.py` — explicitly NOT a VBStyle unit, just a bootstrap
- (B) `setup.py` `entry_points` calls a function directly
- (C) `__main__.py` in the ghost package

**A6**: _(local AI fill in here)_

---

**Q7: BCL Parser — Which Source to Use?**

Found two:
1. `ClassBrackets` in `/Users/wws/contestsystem/workspace/Core/foundation.py` (lines 214-288) — VBStyle-compliant, 75 lines, handles `[@key<value>]` only. Commands: detect, parse, emit.
2. Full parser in `/Users/wws/contestsystem/chat_resources/code/py/vbstyle_config.py` (551 lines) — handles nested `{...}` with 1/2/3/4-tuple properties, `BracketProp` class. NOT VBStyle-compliant (uses `__slots__`, no Run() dispatch, imports json).

**Recommendation**: Copy `ClassBrackets` from foundation.py as the base (already VBStyle-compliant), then extend it to handle nested `{...}` containers and multi-tuple properties. This gives a VBStyle-compliant BCL parser that handles both flat metadata and nested config values.

**A7**: _(local AI fill in here)_

---

**Q8: Config Defaults — Format in Code?**

Config.py has built-in defaults (no .env). On first run, writes to SQLite config table. Should defaults be:
- (A) Python dicts in config.py, converted to BCL when written to SQLite?
- (B) BCL strings in config.py, written directly to SQLite?

**A8**: _(local AI fill in here)_

---

**Q9: No-JSON Rule Scope — External APIs?**

Qdrant REST API returns JSON. msearch_qdrant.py uses `json.loads()`. Does the no-JSON rule apply to:
- (A) Only our storage/config layer. External API parsing is fine.
- (B) Everything including external responses. Must convert to BCL.

**A9**: _(local AI fill in here)_

---

**Q10: Ghost Header Format**

Three formats seen:
- Plan: `#[Ghost{[filename][state][date][version][author]}]`
- VBStyle rules: `#[@VBSTYLE]{[@auth<system>][@role<...>][@return<Tuple3>]...}`
- foundation.py: `#[@GHOST]{[@file<foundation.py>][@state<active>][@date<2026-05-31>][@ver<1.0>][@auth<system>]}`

Which exact format for Ghost header (line 1) and VBStyle header (line 2)?

**A10**: _(local AI fill in here)_

---

**Q11: Does Ghost Need a Report Class?**

VBStyle says "every output goes through report()" and "no print()". Does Ghost need a Report class for all output (CLI messages, API responses, GUI notifications)? Or can Run() methods return strings directly and the CLI/API layer handles display?

**A11**: _(local AI fill in here)_

---

**Q12: SQLite DB Location — Default Path?**

Config.py has built-in defaults. What's the default SQLite path?
- `~/.ghost/ghost.db`?
- `./ghost.db` (project directory)?
- Somewhere else?

And should the SQLite DB be created automatically on first run if it doesn't exist?

**A12**: _(local AI fill in here)_

---

**Q13: Class Count — Are 11 Classes Enough?**

Current seed has 11 classes: Config, MlxService, QdrantService, MysqlService, SearchService, GhostAPI, GhostCLI, SettingsGUI, CodeStore, BCLParser, GhostQA.

Missing potential classes:
- MemUnit (if needed)?
- Report (for output)?
- Bootstrap/Orchestrator (boot sequence)?
- ErrorCapture (error handling)?

Should these be added to the seed, or are they unnecessary?

**A13**: _(local AI fill in here)_

---

**Q14: Qdrant `memory` Collection — 768-dim?**

All Qdrant collections are 384-dim except `memory` (768-dim). What model generates 768-dim vectors? Should Ghost support both 384 and 768? Or ignore the `memory` collection?

**A14**: _(local AI fill in here)_

---

# Appendix A — Model Support: QA / Retrieval Engine Specification

> **Core Principle**: The system must treat all intelligence components as interchangeable execution nodes, not fixed architecture. No single pipeline is assumed.

---

## A.1. Execution Modes

The system must support multiple runtime modes, selectable per run or per test. Pipeline stages are independently configurable.

**Mode A — Embedding + Retrieval Only (NO QA)**

```
Question → Embedding Model → Vector Search (Qdrant / RAM / FAISS) → Return Top-K Evidence
```

Use case: fast lookup, deterministic evidence return, debugging retrieval quality.

**Mode B — Embedding + QA Extractor (No LLM)**

```
Question → Embedding Model → Retrieval → QA Model (BERT / CoreML QA) → Extracted Span Answer
```

Use case: strict extractive systems, high precision factual systems, no synthesis allowed.

**Mode C — Embedding + QA + LLM (Hybrid Intelligence)**

```
Question → Embedding Model → Retrieval → QA Model (extract candidates) → LLM (1.5B or configurable) → Final Answer
```

Use case: readable responses, structured synthesis, explanation layer over evidence.

**Mode D — Embedding + LLM Only (No QA layer)**

```
Question → Embedding Model → Retrieval → LLM only (no span extraction)
```

Use case: flexible reasoning, weak/no strict extraction constraints, conversational systems.

**Mode E — QA Only (No Embeddings)**

```
Question + Document → QA Model directly
```

Use case: single-document extraction, CoreML/BERT style span QA testing.

---

## A.2. Model Selection

All models must be configurable. No model names may be hardcoded into execution paths. Model configuration must be stored separately from code.

**Embedding Models (selectable at runtime):**
- BGE
- E5
- Nomic
- MiniLM
- CodeBERT (for code corpora)
- GraphCodeBERT
- Future models

**QA Models (selectable at runtime):**
- CoreML QA (Apple BERT-SQuAD)
- BERT QA
- DistilBERT QA
- CodeBERT QA (if applicable)
- Future QA engines

**LLM Models (optional, selectable at runtime):**
- 1.5B local model (Qwen2.5-Coder via MLX)
- Larger cloud models (optional future plug-in)

QA engine configuration:
- Confidence threshold
- Max answer length
- Span extraction mode
- Multi-answer mode

---

## A.3. Storage Modes

The system must support multiple embedding storage strategies. Storage mode must be configurable.

**RAM Only:**
- Document loaded into RAM, chunks created in RAM, embeddings generated in RAM
- Search and QA extraction performed in RAM
- All embeddings discarded after execution

**Persistent Vector Store:**
- Embeddings stored in vector database
- Future queries reuse stored embeddings

**Hybrid:**
- RAM cache used first, persistent vector store as backing store
- Frequently accessed embeddings remain resident in RAM

---

## A.4. Vector Backend Selection

Vector backend must be configurable. No execution path may assume a specific vector database.

Supported examples:
- Qdrant
- FAISS
- SQLite Vector
- RAM Index
- Future backends

---

## A.5. Embedding Persistence Policy

Embedding persistence must be configurable.

Options:
- Never Save
- Save On Demand
- Always Save
- Save Only High Value Documents
- Save Only Curated Knowledge
- Refresh Existing Embeddings
- Force Rebuild

---

## A.6. Embedding Refresh Policy

The system must support:
- Full rebuild
- Incremental rebuild
- Changed document rebuild
- Manual rebuild
- Scheduled rebuild

---

## A.7. Hardware Awareness

The system must be aware of available resources. Hardware information must influence execution strategy.

**Detect:**
- CPU cores
- RAM size / Free RAM
- GPU availability / GPU memory
- Apple Metal / MPS
- Disk capacity / Disk free space

**Execution device modes (configurable):**
- **CPU Mode** — Force CPU execution
- **GPU Mode** — Force GPU execution
- **Auto Mode** — Automatically choose best device
- **Hybrid Mode** — Split workloads across devices when beneficial

**Resource limits (configurable):**
- Max RAM usage
- Max VRAM usage
- Max chunk count
- Max embedding count
- Max document size
- Max retrieval depth
- Max QA context size

---

## A.8. Retrieval Configuration

Support configurable retrieval settings:
- Top-K
- Similarity threshold
- Distance metric
- Chunk size
- Chunk overlap
- Retrieval depth
- Reranking enabled/disabled

---

## A.9. Config Object (Required Standard)

All runs must be driven by a single config object. Shown here as a schema representation (actual storage is BCL in SQLite, not JSON):

```
[@qa_config]{
  (@mode<A|B|C|D|E>;
   @embedding_model<...>;
   @qa_model<...>;
   @llm_model<...>;
   @vector_store<qdrant|ram|faiss>;
   @store_embeddings<true|false>;
   @hardware<(@cpu<true>;@gpu<true>;@mps<true>)>;
   @thresholds<(@qa_confidence<5.0>;@retrieval_top_k<5>)>)
}
```

---

## A.10. Truth Classification

Support configurable result classification.

Required modes:
- TRUE
- FALSE
- UNKNOWN

Classification thresholds must be configurable.

---

## A.11. Performance Metrics

Record metrics for every run:
- Embed latency
- Retrieval latency
- QA latency
- Total latency
- RAM usage
- VRAM usage
- Disk usage
- Retrieval score
- QA confidence

---

## A.12. Failure Attribution

Every failure must identify the failing stage:
- DOCUMENT_LOAD
- CHUNKING
- EMBEDDING
- VECTOR_STORE
- RETRIEVAL
- RERANKING
- QA_EXTRACTION
- CLASSIFICATION
- RESOURCE_LIMIT

---

## A.13. Testability Requirement

Every configuration must be: runnable independently, benchmarkable, comparable against other configs, logged with full stage metrics.

Each run must record: retrieval success, QA accuracy, final answer correctness, failure stage, latency per component.

---

## A.14. Key Design Constraint

No component is allowed to assume:
- embeddings are always persistent
- QA model is always present
- LLM exists
- vector DB exists

Everything must degrade gracefully.

---

## A.15. Future-Proofing Rule

The architecture must treat all of the following as replaceable components:
- Embedding models
- QA models
- Vector stores
- Rerankers
- LLMs
- Storage policies

No component may become a permanent architectural dependency.

---

## A.16. Core Insight

The system is not "a QA system". It is:

**A switchable cognition graph over stored memory**

where:
- **Embeddings** = routing layer
- **Vector DB** = memory substrate
- **QA model** = extraction layer
- **LLM** = interpretation layer

If implemented correctly, the biggest win is: **you can prove which combination is optimal, instead of guessing.**

---

## A.17. Open Question: Auto-Routing vs Explicit Mode

Should the system dynamically choose the mode per query (auto-routing), or should mode always be explicitly selected for reproducibility in testing?

**Decision**: _(pending — needs user input)_

---

## A.18. Empirical Results — 5-Mode Benchmark

> **Source**: `five_mode_runner.py` + `GhostQAEngine.py` + `pinnacle_harness.py` (28 test questions across 10 aspects)

### Overall Results

| Mode | Name | Mode Correct | Answer Correct | Avg Latency |
|------|------|-------------|---------------|-------------|
| A | Retrieval Only | 0/28 (0%)* | 0/28 (0%)* | 54ms |
| B | Retrieval + BERT QA | 18/28 (64%) | 16/28 (57%) | 738ms |
| C | Retrieval + BERT + LLM Format | 18/28 (64%) | 16/28 (57%) | 750ms |
| D | Retrieval + LLM (no BERT) | 22/28 (79%) | 25/28 (89%) | 978ms |
| E | QA Only (no embeddings) | 0/28 (0%)** | 0/28 (0%)** | 0ms |

\*Mode A returns `RETRIEVAL_ONLY` — not designed for classification, just evidence return.

\*\*Mode E requires context param (direct document QA). Harness sends questions without context, so it correctly errors. Mode E is for single-document extraction testing.

### Key Findings

**Mode D wins overall**: 79% mode accuracy, 89% answer accuracy. Only 240ms slower than BERT.

**Mode C = Mode B**: LLM formatting on top of BERT adds 12ms latency for zero accuracy gain. The LLM only formats the already-classified BERT answer — it doesn't change classification. **Mode C is not worth it.**

### Per-Aspect Breakdown (Mode B vs Mode D)

| Aspect | BERT (B) | LLM (D) | Winner |
|--------|----------|---------|--------|
| chunking | 100% / 0% | 100% / 100% | D (answer) |
| code | 100% / 50% | 100% / 100% | D (answer) |
| conversation | 0% / 0% | 100% / 100% | D |
| false_positive | 33% / 33% | 0% / 100% | B (mode), D (answer) |
| hierarchy | 50% / 0% | 100% / 50% | D |
| multi_evidence | 100% / 0% | 100% / 100% | D (answer) |
| near_miss | 100% / 100% | 50% / 50% | B |
| negation | 0% / 100% | 0% / 100% | Tie (both fail mode) |
| retrieval | 100% / 67% | 100% / 100% | D (answer) |
| temporal | 100% / 50% | 100% / 100% | D (answer) |
| unknowns | 25% / 100% | 100% / 100% | D |

### Tradeoff Pattern

**BERT wins on:**
- Near-miss disambiguation (port 7012 = "a typo" — BERT extracts the span, Qwen says NOT FOUND)
- False positive mode classification (BERT extracts something → sometimes correctly FALSE)

**Qwen wins on:**
- Conversation/decision questions (100% vs 0%)
- Code extraction (constructor signature — Qwen gets it right, BERT mangles underscores)
- Temporal reasoning (old vs current — Qwen distinguishes, BERT returns same answer for both)
- Multi-fact synthesis (MemDB definition — Qwen synthesizes, BERT picks wrong span)
- Unknown detection (100% vs 25% — Qwen says NOT FOUND, BERT hallucinates from wrong context)

### Unknown Detection — Critical Safety Metric

| Mode | Unknowns (U01-U04) | False Positives (F01-F03) |
|------|-------------------|--------------------------|
| B (BERT) | 1/4 (25%) | 1/3 (33%) |
| D (Qwen) | 4/4 (100%) | 0/3 (0%) |

Qwen never hallucinates on unknowns (4/4 correct NOT FOUND). BERT extracts from wrong context, often classified as TRUE (hallucination).

### Architecture Verdict

The spec was right — this is a switchable cognition graph, and the data proves no single mode is optimal everywhere:

- **Mode A**: Use for retrieval debugging, evidence return, human-in-the-loop
- **Mode B**: Use for strict extractive tasks (ports, names, negation, near-miss)
- **Mode D**: Use for structural knowledge, code, conversation, temporal, unknown-safe QA
- **Mode E**: Use for single-document extraction testing (needs context param)

### Next Step: Auto-Routing

The data suggests auto-routing: classify the question type and route to BERT or Qwen based on which mode wins for that aspect. But as section A.17 noted — for reproducibility in testing, mode should be explicitly selectable.

### Implementation Files

- `GhostQAEngine.py` — 5-mode engine with graceful degradation
- `five_mode_runner.py` — experiment runner for all 5 modes
- `pinnacle_harness.py` — 28-question test harness across 10 aspects

---

# Appendix B — Truth-Processing Engine: 3-Mode Cognitive Pipeline

> **Core Insight**: Models are not intelligence — they are stage operators in a deterministic cognition pipeline. Models are not meant to be fused into one brain. They are meant to be sequenced as roles in a pipeline.

---

## B.1. The Architectural Breakthrough

The QA prototype (Appendix A) proved that retrieval + extraction + explanation works. But the deeper insight is that these are not "model combinations" — they are **separate cognitive layers with hard state transitions**.

This is not a QA system with models. It is a **mode-separated truth-processing engine**.

---

## B.2. Phase 1 — Grounding (Truth Extraction)

```
Chat / Docs / DB
    ↓
Retriever (BGE embedding + Qdrant search)
    ↓
QA Extractor (Apple CoreML BERT-SQuAD)
    ↓
FACTS ONLY
    ↓
FACT STORE (structured, versioned truth)
```

**Output is NOT an answer.** It is structured truth:

- `Rule A = true`
- `Rule B = false`
- `MemDB = in-memory registry`
- `Boot order = config → memdb → ast`

**This is truth compression mode.** No reasoning. No explanation. No formatting. Just extracted reality.

---

## B.3. Phase 2 — Logic (Reasoning Over Truth)

```
FACT STORE
    ↓
Reasoner (LLM or reasoning engine)
    ↓
Apply logic / interpretation
    ↓
Decisions
```

**This layer does NOT search documents.** It ONLY operates on extracted truth.

Example:

```
Input facts:
  Print statements = NOT allowed
  Hardcoding = NOT allowed
  MemUnit = execution authority

Query:
  Can I use print statements in debugging?

Output:
  No — debugging via print statements violates system rules.
```

---

## B.4. Phase 3 — Action (Execution / Generation)

```
Decisions
    ↓
Task execution / generation
    ↓
Code / config / response / decision
```

Example:

```
Input: Generate safe debug strategy

Output:
  Use structured logging instead of print statements.
  Enable trace-level MemUnit hooks.
```

---

## B.5. The FACT STORE — The Missing Piece

The critical architectural component is a **persistent intermediate object**: the FACT STORE.

This is what sits between Phase 1 (grounding) and Phase 2 (logic). It is:

- **Versioned** — track truth changes over time
- **Testable** — verify extracted facts against source
- **Replayable** — re-run logic on same facts
- **Auditable** — trace any decision back to its source facts

### FACT STORE Schema (Proposed)

```
facts table:
  id          INTEGER PK
  fact_text   TEXT        — the extracted fact ("print statements = NOT allowed")
  source      TEXT        — where it came from ("qdrant:dim_semantic:point_42")
  confidence  REAL        — QA extraction confidence (5.69)
  phase       TEXT        — "grounding"
  version     INTEGER     — version number for truth tracking
  created_at  TIMESTAMP
  bcl         TEXT        — BCL metadata: [@fact]{(@source<...>;@confidence<...>)}

fact_relations table:
  id          INTEGER PK
  fact_id_a   INTEGER FK  —> facts.id
  fact_id_b   INTEGER FK  —> facts.id
  relation    TEXT        — "contradicts", "supports", "extends", "supersedes"
  bcl         TEXT
```

---

## B.6. Why This Is Stronger Than Single-LLM Systems

```
❌ Wrong:     Question → LLM → Answer
❌ Semi-RAG:  Question → Retrieve → QA → Answer
✅ Ghost:     Phase 1 (Ground) → Phase 2 (Reason) → Phase 3 (Act)
```

Because now:
- **Truth is stable** — facts persist in FACT STORE, not regenerated each query
- **Reasoning is repeatable** — same facts → same decisions
- **Output is controllable** — each phase has clear boundaries
- **Every failure is traceable** — identify which phase failed (grounding vs logic vs action)

The QA prototype already proved: most failures are not retrieval failures — they are **interpretation boundary failures**. This architecture removes that ambiguity completely.

---

## B.7. State Machine of Intelligence

This is not model blending. It is not an ensemble. It is:

**A state machine of intelligence.**

```
[Document/Chat/DB] --grounding--> [FACT STORE] --logic--> [Decisions] --action--> [Output]
```

Each transition is a hard state boundary. Each phase has its own model, its own config, its own metrics. Phases are independently testable and swappable.

---

## B.8. Relationship to Appendix A

Appendix A defines the **configurable model graph** — which models run in which modes (A-E).

Appendix B defines the **cognitive pipeline** — how truth flows through the system in 3 phases.

Together:
- **Appendix A** = "which models and how to configure them"
- **Appendix B** = "what the models do and how truth flows between them"

The execution modes from Appendix A map to the phases:

| Appendix A Mode | Appendix B Phase |
|-----------------|-----------------|
| Mode A (Retrieval Only) | Phase 1 partial (no QA extraction) |
| Mode B (Retrieval + QA) | Phase 1 complete (grounding) |
| Mode C (Retrieval + QA + LLM) | Phase 1 + Phase 2 + Phase 3 |
| Mode D (Retrieval + LLM) | Phase 1 partial + Phase 2/3 (no QA extraction) |
| Mode E (QA Only) | Phase 1 with direct document input |

---

## B.9. FACT STORE — Already Exists

**Resolved**: The FACT STORE is not a new build. It already exists in `vb_shared` MySQL, populated with real data:

| Table | Rows | Purpose |
|-------|------|---------|
| `know_answers` | 123 | Canonical assertions (24 canonical, avg conf 0.86) |
| `know_nodes` | 1,694 | Epistemic lifecycle graph (513 open, 1,087 answered, 40 stabilized, 54 collapsed) |
| `know_memory_units` | 16 | Compressed memory clusters (stability_score 0.9179) |
| `learned_rules` | 10,540 | Compressed experience patterns with success/failure counts |
| `know_questions` | 137 | Questions across 24 categories |
| `decision_principles` | 6 | Core governance principles |

**Provenance**: All existing data was populated by `cascade_llm_generated` — a different model than Qwen 1.5B.

**The actual problem**: The three levels (philosophy, algorithm, database) are disconnected from the Qwen engine. The task is not to build a Fact Store — it is to **connect the existing Fact Store to Mode D**.

---

# Appendix C — Unified Architecture: 3-Layer Epistemic System

> **Core Insight**: You are not building a QA system. You are building a routed epistemic system with three layers. The Fact Store is not cache, not brain — it is an epistemic grounding layer that stores previously validated truth under current system rules.

---

## C.1. The Three Layers

```
           ┌──────────────────────┐
           │  VBStyle / Cascade   │
           │  (rules + meaning)   │
           └─────────┬────────────┘
                     │
     governance      │
                     ▼
┌──────────────────────────────────┐
│     Fact Store (MySQL)           │
│  stabilized belief memory graph  │
└───────────┬──────────────────────┘
            │
   grounding│
            ▼
┌──────────────────────────────────┐
│  Mode D / BERT / Router Layer    │
│  (live inference engine)         │
└──────────────────────────────────┘
```

| Layer | Role | State | Speed |
|-------|------|-------|-------|
| Runtime Intelligence (Mode D/Qwen/BERT) | Live brain — inference per query | Stateless | 978ms |
| Fact Store (MySQL know_* tables) | Stabilized belief memory | Persistent | 5ms lookup |
| VBStyle / Cascade | Meta-reasoning + governance | Historical | Offline |

---

## C.2. Correct System Flow

```
STEP 1 — Query arrives
    Query Interpreter classifies intent
    detects: negation, code, temporal, existence presupposition

STEP 2 — Fact Store check (MySQL)
    Check: is_canonical == true
           AND confidence >= threshold (0.90-0.93)
           AND node_state == stabilized
           AND version is latest
           AND no contradiction flag
    → If PASS: return instantly (5ms path)

STEP 3 — Mode D inference (Qwen)
    If NOT in Fact Store:
    retrieve Qdrant chunks → run Qwen Mode D → produce answer + confidence

STEP 4 — Promotion engine
    After Mode D:
    If confidence high:
        write to know_answers
        create/update know_nodes
        set state = answered → maybe stabilized
        attach provenance = "qwen_1.5b"

STEP 5 — Collapse cycle (periodic)
    When density threshold reached:
    run collapse algorithm → generate memory_units → compress rule patterns
```

---

## C.3. Epistemic Lifecycle (know_nodes)

The 4-state lifecycle already exists in the database:

| State | Meaning | Count | Avg Confidence |
|-------|---------|-------|---------------|
| `open` | Hypothesis — question asked, no answer yet | 513 | 0.0035 |
| `answered` | Candidate truth — answer produced | 1,087 | 0.8949 |
| `stabilized` | Accepted truth — confirmed across queries | 40 | 0.9188 |
| `collapsed` | Compressed knowledge — folded into memory unit | 54 | — |

**This is a belief crystallization system**, not a cache or database.

---

## C.4. The 6-Phase Collapse Algorithm

Already designed and tested:

1. **Tree Traversal** — recursive CTE walks the QA tree
2. **Dependency Graph** — construct from `qa_edges` relationships
3. **Rule Extraction** — parse answers for ALWAYS/NEVER/WHEN/IF patterns
4. **Summary Generation** — compress tree into single summary
5. **Stability Score** — `coverage(30%) + confidence(30%) + depth_balance(20%) + consistency(20%)`
6. **Memory Unit Creation** — write to `know_memory_units`, mark tree as `collapsed`

### Coverage Gate (Critical Guardrail)

No collapse until:
- `categories_covered >= 3`
- `unresolved_nodes = 0`
- `avg_depth >= 2`

**Nut vs Plastic analogy**: Nut = fully explored concept space (safe to compress). Plastic = early summary over sparse exploration (premature collapse).

---

## C.5. Contradiction Resolution Protocol

The one missing piece. When new Mode D inference contradicts existing canonical truth:

```
IF new_answer.confidence >= 0.93:
    IF contradicts existing canonical:
        flag = "conflict"
        require re-validation (Mode D + evidence comparison)
    ELSE:
        promote to canonical
        update version
ELSE:
    store as non-canonical candidate
```

### Contradiction Handling States

| Situation | Action |
|-----------|--------|
| New answer matches canonical | Return canonical (5ms) |
| New answer is novel (no existing) | Store as `answered`, provenance=`qwen_1.5b` |
| New answer contradicts, high confidence | Flag as `conflict`, require re-validation |
| New answer contradicts, low confidence | Store as non-canonical candidate |
| Canonical answer contradicted by 2+ sources | Demote to `answered`, trigger re-validation |

---

## C.6. Existing Stabilized Truths (Sample)

These are already in the database at confidence 1.0:

- "System has persistent memory — check existing state before requesting changes"
- "Full conversation ingestion with permanent storage and reuse"
- "WHEN/WHEN NOT rules are executable conditions, not descriptions"
- "System ASSEMBLES GUIs from learned design rules conditioned on context"
- "Learning is concrete: correction → storage → reuse"

---

## C.7. Philosophical Roots (VBStyle Book)

The book at `/Users/wws/bin/vbstyle-book/` (56 chapters, 31,344 words) defines the philosophical foundation:

- **Chapter 17, Rule 61** (`@know`): "Stores truths with signatures, linked to methods and execution. The knowledge base accumulates facts derived from execution."
- **Chapter 19, Rules 66-69** (`@exp @clu @map @col`): The EXPAND-CLUSTER-MAP-COLLAPSE analysis method. COLLAPSE = "extract the stable invariant jewel."

---

## C.8. What Needs to Happen

This is not building something new. This is **connecting what already exists** at three levels into one pipeline:

1. **Wire Qwen Mode D** (89% answer accuracy) into the existing `know_nodes` pipeline
2. **Qwen answers** → insert into `know_nodes` as `answered` with confidence and `provenance="qwen_1.5b"`
3. **Same answer confirmed** across multiple queries → promote to `stabilized`
4. **Stabilized tree meets coverage gate** → run collapse algorithm → create memory unit
5. **Future queries** → check `know_answers` first (5ms). If high-confidence canonical exists, return it. If not, run Mode D (978ms) and write back.

### Open Questions

- Should the collapse algorithm be implemented as MySQL stored procedures or as Python methods in `GhostQAEngine`?
- Should existing `cascade_llm_generated` data be kept, or start fresh with Qwen as the provenance source?
- Should the existing `context` JSON field in `know_nodes` be migrated to BCL format?