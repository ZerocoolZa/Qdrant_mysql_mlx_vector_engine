# What You Need To Know — Core Architecture

## Folder Structure

```
core/
  __init__.py              ← package root (importable from any folder)
  core_spec.md             ← full spec: 22 VBStyle classes, dependency graph
  core_class_registry.md   ← 237KB registry of all classes/methods
  core_class_extractor.py  ← extracts classes from Python source

  Dom_Unified/             ← INFRASTRUCTURE LAYER (service control, config, AST, cache)
    Config.py              ← unified config: DB_HOST, DB_USER, service paths, graph settings
    DomSystem.py           ← service controller: Run("start"/"stop"/"is_running", {"service": "mysql"})
    ConfigCascade.py       ← Cascade-specific config (50KB)
    DatabaseManager.py     ← db_query, db_execute, db_insert helpers
    DomExecutionEngine.py  ← execution engine (43KB)
    DomIndexer.py          ← file indexer (49KB)
    DomReport.py           ← structured reporting
    DomReuse.py            ← reuse pattern detection
    DomSessionGraph.py     ← session graphing
    LocalAgent.py          ← local AI agent (31KB)
    MagneticGraph.py       ← magnetic radius search
    MemoryObject.py        ← memory object pattern
    Neo4jGraph.py          ← Neo4j graph operations
    UnifiedAst.py          ← AST parsing via vbast C binary + SQLite cache
    CacheDb.py             ← SQLite cache for parsed ASTs
    ErrorCapture.py        ← error capture + knowledge
    unified_cache.db       ← 16MB SQLite cache
    reuse_weights.db       ← reuse pattern weights

  Dom_Bcl/                 ← BCL (Binary Compression Language) layer (49 items)
  Dom_Graph/               ← Graph engine (6 items)
  Dom_Gui/                 ← GUI domain: builder, bus, config, db, graphs, node, parser, router, theme
  Dom_Vsstyle/             ← VBStyle validation (15 items)
  Dom_system/              ← System domain
  Piplines/                ← Pipeline specs (31 .md files)
    Plf_ChatmoverPipeline.md  ← THE chat ingestion pipeline spec
  utility/                 ← Utility functions (26 items)
```

## Service Management (DomSystem)

```python
from Dom_Unified.DomSystem import DomSystem

ds = DomSystem()
ds.Run("start", {"service": "mysql"})       # starts mysqld via direct binary
ds.Run("stop", {"service": "mysql"})        # stops mysqld
ds.Run("is_running", {"service": "mysql"})  # returns (1, {"running": True/False, "pid": N}, None)
ds.Run("start_all", {})                     # start all services
```

Services managed: mysql, neo4j, qdrant, sqlite (always available)
MySQL binary: /opt/homebrew/opt/mysql@8.0/bin/mysqld
Config source: core/Dom_Unified/Config.py (GRAPH_MYSQL_HOST, GRAPH_MYSQL_USER, GRAPH_MYSQL_PORT)

## Config Hierarchy

```
core/Dom_Unified/Config.py          ← SINGLE SOURCE OF TRUTH
  GRAPH_MYSQL_HOST = "localhost"
  GRAPH_MYSQL_USER = "root"
  GRAPH_MYSQL_PORT = 3306
  GRAPH_MYSQL_DB_VB = "vb_shared"
  GRAPH_MYSQL_DB_BCL = "bcl_ir"

ChatGPTManager/Config.py            ← SECONDARY (imports from Dom_Unified)
  from Dom_Unified.Config import GRAPH_MYSQL_HOST as DB_HOST, ...
  DB_NAME = "chatgpt_chats"  (app-specific)
  Also loads GUI metadata from ConfigDB (themes, tooltips, shortcuts, menus)

gui_engine/gui_engine.py            ← STYLE ENGINE
  StyleDBV2 → SQLite style storage (color.background, font.size, spacing.padding)
  StyleEngineV2 → selector engine (object.property.value)
  QtStyleRendererV2 → applies QSS + fonts to QWidget
  UIDBV4 → UI tree in SQLite (parent/child nodes, components)
  GUIDecisionEngine → AI reasoning for component selection (stubbed at TASK-058)
```

## ChatMover Pipeline (core/Piplines/Plf_ChatmoverPipeline.md)

```
PHASE 1: INGESTION
  ChatGPT JSON  → MySQL chatgpt_chats (conversations, messages)
  Cascade .pb   → MySQL cascade_chats (trajectories, rounds, messages)
  Devin JSON    → MySQL devin (devin_sessions, devin_messages, devin_tool_calls)
  SQLite DBs    → MySQL Chat_History (sessions, messages, prompts)
  Disk .md      → MySQL Chat_History

PHASE 2: COMPRESSION
  MySQL chats → BCL tokens → SQLite bcl_chat_store.db
  Stage 1: regex/dict extraction (deterministic, milliseconds)
  Stage 2: AI semantic pass (compressed index, fits in AI context)
  [@CHATSOURCE] links back to original
```

## ChatGPTManager Commands

```bash
python3 main.py token          # extract access token from Chrome via CDP
python3 main.py extract        # extract cookies from Chrome
python3 main.py fetch          # fetch all chats from ChatGPT API
python3 main.py ingest         # load chats into MySQL
python3 main.py all            # full pipeline: token + cookies + fetch + ingest
python3 main.py status         # show ChatGPT MySQL database stats
python3 main.py viewer         # launch PyQt6 GUI
python3 main.py cascade-all    # decrypt + ingest Cascade .pb files
python3 main.py devin-sync     # sync Devin SQLite to MySQL
python3 main.py capsule-all    # build unified capsules for all sessions
```

## VBStyle Rules (ALL classes follow)

- `__init__(self, mem=None, db=None, param=None)`
- `self.state = {}` dict (NO `self._` variables)
- `Run(self, command, params=None)` dispatch method
- `read_state(self)` / `set_config(self, config)`
- All methods return Tuple3: `(1, data, None)` or `(0, None, (code, desc, 0))`
- No print(), no decorators, no hardcoded paths
- PascalCase classes, UPPERCASE constants, spaces only

## Integration Pattern (for any external app)

```python
# 1. Add core/ to sys.path
import sys, os
sys.path.insert(0, "/Users/wws/Qdrant_mysql_mlx_vector_engine/core")

# 2. Import unified config + service management
from Dom_Unified.Config import GRAPH_MYSQL_HOST, GRAPH_MYSQL_USER, GRAPH_MYSQL_PORT
from Dom_Unified.DomSystem import DomSystem

# 3. Ensure MySQL running (no manual brew commands)
ds = DomSystem()
ds.Run("start", {"service": "mysql"})

# 4. Your app config imports from Dom_Unified (secondary config)
# In your Config.py:
#   from Dom_Unified.Config import GRAPH_MYSQL_HOST as DB_HOST
#   DB_NAME = "your_app_db"  # app-specific
```
