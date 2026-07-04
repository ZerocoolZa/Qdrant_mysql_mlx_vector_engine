# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added — PB Chat Reader (TASK-105)

- **`chat_mover/pb_reader.py`** (NEW): VBStyle-compliant CLI tool that decrypts, parses, and searches Windsurf Cascade `.pb` chat files.
- **Decryption**: AES-256-GCM with hardcoded key `safeCodeiumworldKeYsecretBalloon` (extracted from `language_server_macos_arm` binary). File layout: `[12-byte nonce][ciphertext][16-byte GCM tag]`.
- **Parsing**: Generic protobuf wire-format walker — no `.proto` schema compilation needed. Extracts trajectory_id, cascade_id, steps, user_input, planner_response, run_command, checkpoints.
- **Storage**: In-RAM SQLite (`:memory:`) with 6 tables: trajectories, steps, user_messages, assistant_messages, commands, checkpoints.
- **CLI commands**: `scan` (list all .pb files), `list` (loaded trajectories), `load`/`load-all`, `read` (show chat), `search` (full-text search with scope filter), `export` (markdown export), `stats`.
- **Verified**: Scan found 145 .pb files (1 cascade, 1 implicit, 143 memories). Read decrypted a 3507-step Cascade conversation. Search found matches for "language server". Export produced 238 markdown rounds.
- **VBStyle compliant**: No print(), no decorators, no self._, Run() dispatch, Tuple3 returns, BCL headers.

### Added — Language Server Tamer + .codeiumignore (TASK-104)

- **`core/Dom_Unified/Config.py`**: Added `tame_langserver` service to `DOM_SERVICES` dict — kills runaway `language_server_macos_arm` process via `pkill`. Invokable via `DomSystem.Run("start", {"name": "tame_langserver"})`.
- **`.codeiumignore`** (NEW): Created at project root — excludes `*.db`, `node_modules/`, `__pycache__/`, `*.o`, `*.a`, `*.so`, `chat_mover/`, `chat_/`, build artifacts, virtual envs, and large data directories from Codeium/Windsurf language server indexing. Prevents the recurring 200%+ CPU / 1.3GB+ RAM spikes that cause Mac freezes.
- Root cause: language server re-indexes workspace on every file change. Workspace has 6.7GB data, 1952+ files, 16MB+ DB files. On 8GB M1 Mac, this causes immediate memory pressure → swap → CPU spike → system freeze.
- Chat history confirms 4+ prior incidents: 1.6GB (id 14373), 14GB leak (id 16336), 200%+ CPU indexing Swift (id 19962).

### Added — C Language Graph Extraction (TASK-103)

- **`bcl_ingestion_engine.c`**: Added `detect_language()` (LANG_PYTHON/LANG_C/LANG_UNKNOWN), `extract_c_params()`, `walk_c_ast()` — extracts C functions (as methods), `#include` (as imports), `struct`/`typedef` (as classes) using `tree_sitter_c()`.
- **`bcl_graph_builder.c`**: Added `extract_c_call()`, `extract_c_field_access()`, `walk_c_body_for_edges()` — extracts CALL, STATE_READ, STATE_WRITE, IMPORT edges from C AST.
- **Result**: All 11 C files now have rich graph edges (35-536 edges per file). Before: 0 edges for all C files.
- Edge types: IMPORT (includes), CALL (function calls), STATE_READ (struct field reads), STATE_WRITE (struct field writes).
- Synced to MySQL, rebuilt from DB — 12/12 units compiled, 0 failed.

### Added — BCL Dictionary Run() Dispatch + read_state + set_config (TASK-102 fix)

- **`bcl_dictionary.c`**: Added `BclDictionary_Run()` dispatch with 8-command function pointer table (populate, lookup, is_valid_tag, is_valid_in, get_rule, count, read_state, set_config). BCL in, BCL out.
- Added `fn_dict_read_state` and `fn_dict_set_config` wrapper functions for MemUnit orchestration.
- Removed dead empty if-block in `GetRule()`.
- **`bcl_engine.h`**: Moved `DictCommand` enum to shared header.

### Added — Central DB Architecture for C Code (TASK-091)

- **4-layer model**: MySQL `c_classes` (source of truth) → materializer →
  disk (.c/.h files, disposable) → compiled binary (runtime, no DB dependency)
- **`bcl_c_loader.py`** (`core/Dom_Bcl_C_ver/`): materializer script with
  Run() dispatch — `load_all`, `compile_all`, `build_all`, `build_changed`,
  `sync`, `verify_all`, `clean`, `status`, `manifest`
- **Topological sort** (Kahn's algorithm) over typed dependency edges
  (include/call/link) — resolves compile order from structured JSON in
  `dependencies` column
- **Incremental rebuild** via SHA256 hash comparison (like Make) — only
  recompiles changed units
- **Sync** — compares DB hashes vs disk hashes, reports drift + orphans
- **16 C units** in `c_classes` with `domain='bcl_c_engine'`: 7 active
  (vbast: GraphTypes, IngestionEngine, BclStamper, GraphBuilder,
  StaticAnalyzer, GraphStore, BclDispatcher) + 9 draft stubs
- Verified: clean + rebuild from DB produces identical working binary
  (`dom_graph_engine`, 54 KB) — tested on real Python file

### Added — DB-Driven VBStyle Fix Engine (TASK-090)

- **VbStyleFixEngine.py**: VBStyle class that reads violations from
  `dom_graph_work.db`, fixes method_code via AST transform, UPDATEs DB,
  syncs back to .py files. Run() dispatch: scan | fix_tuple3 | fix_self_ |
  sync | reindex | verify | all.
- Fixed 345 methods missing Tuple3 returns across 17 files
- Fixed 13 self._ violations (renamed _Get→Get, _BuildDb→BuildDb, etc.)
- All 38 classes now flagged is_vbstyle=1 in DB
- 17/17 files pass py_compile, 0 real violations remaining

### Added — LayoutEngine: unified Layout Graph kernel (TASK-089)

- **Unified Layout Graph DOM** (`LayoutEngine/LayoutNode.py`): single source of
  truth for both Qt and terminal renderers. 11 node types (Container/Row/Column/
  Block/Widget/Text/Table/Tree/Pipeline/Spacer/Divider), each carrying constraints,
  responsive spec, dirty flags, cached measure + rect.
- **Constraint solver** (`LayoutEngine/Constraints.py`): mini flexbox + CSS-grid
  solver. Resolves weights, enforces min/max, flex_grow/flex_shrink, justify/align,
  overflow shrink. Pure function of (tree, available size) -> Rects.
- **Lifecycle pipeline** (`LayoutEngine/Lifecycle.py`): build -> normalize ->
  measure -> solve -> layout -> render. Invalidation via dirty flags
  (MEASURE|LAYOUT|RENDER); incremental recompute skips clean subtrees.
- **Responsive layer** (`LayoutEngine/Responsive.py`): Bootstrap-like 12-column
  system with breakpoints xs/s/m/l/xl, cascade col_span selection, automatic
  row->column collapse at narrow widths.
- **CJK-aware text layout** (`LayoutEngine/TextLayout.py`): visible width
  (ANSI-stripped, East-Asian wide detection), word/char/hard wrap, truncate, pad.
- **ANSI theme system** (`LayoutEngine/AnsiTheme.py`): dark/light presets,
  colorize by role, style codes, box-drawing border glyphs.
- **Terminal renderer** (`LayoutEngine/TerminalRenderer.py`): compiles solved
  tree -> ANSI string canvas. Block/Table/Tree/Pipeline are visitors over the
  solved tree.
- **Qt renderer** (`LayoutEngine/QtRenderer.py`): compiles solved tree ->
  PyQt6 QWidgets with setGeometry. Lazy PyQt6 import so terminal path works
  headless. Both renderers consume the SAME tree.
- **Public facade** (`LayoutEngine/LayoutEngine.py`): `Engine.build(tree) ->
  Engine.render(target)` — one entry point for both render targets.
- **Verify**: 16/16 checks pass. py_compile all 11 source files. Solver
  weight 1:3:1 -> 22:54:22. Responsive row collapses at narrow width. Qt path
  builds 14 widgets with setGeometry from solver rects; same tree renders to
  24 ANSI lines. Invalidation propagates dirty to ancestors, clears after re-render.
- **VBStyle**: zero print()/decorators/self._/tabs in source files. All classes
  use self.state dict + Tuple3 returns + Run() dispatch.

### Added — Dom_DecisionTrees: full interactive canvas (TASK-099)

- **BCL decision-tree editor mode** in `Dom_DecisionTrees/DecisionTreeGui.py`: File→Open BCL File
  parses `.bcl` files via `core/Dom_Bcl/bcl_lexer.py` + `bcl_parser.py` and renders
  `[@rule]{[@Pass]{...}[@Fail]{...}[@Unsure]{...}}` as a colored tree (green Pass / red Fail /
  amber Unsure / blue Rule / slate Check). Weight shown as `[N]` on leaf nodes. Clicking a node
  populates a new "BCL Tuple Editor" tab (editable `value;value;weight` per line); File→Save BCL
  File serializes edits back via `BCLNode.ToBcl`.
- **Dependency-graph mode**: renders cross-file imports from the `dependencies` table as a
  directed graph; file nodes colored local vs external; click a file to list its imports.
- **Clickable canvas nodes**: `DecisionTreeCanvas` emits `nodeSelected(TreeNode)`; clicking a
  node in code-graph mode populates the previously-dead Code / BCL-IR / Dependencies tabs from
  the DB (method row → `methods.code` / `methods.bcl` / `methods.bcl_ir` + the file's imports).
- **Search box** that highlights matching nodes (yellow border).
- **File→Export PNG** renders the current canvas to a PNG file.
- **View menu** mode switchers (Code Graph / BCL Tree / Dependency Graph).

### Fixed — Dom_DecisionTrees

- **SQL injection** in `_build_by_category` / `_build_by_file` / `_build_by_class`: filter
  values were string-interpolated into SQL (`f"category = '{filter_cat}'"`). Now parameterized
  with `?` placeholders + params lists.
- **Invalid SQL in `_build_by_class`**: when no filters were set, `AND class_name IS NOT NULL`
  was appended after `GROUP BY`, producing a query that would fail at runtime. Now correctly
  placed in the `WHERE` clause in both the filtered and unfiltered branches.
- **`closeEvent` config persistence**: only the in-memory `tree_config` dict was saved, ignoring
  unsaved edits in the JSON editor. Now persists the editor's current text.
- **`QGraphicsRectItem.setRoundedRect`** does not exist in PyQt6 — removed (sharp corners);
  the canvas would have crashed on first render.
- **`QGraphicsPolygonItem`** was never imported — arrow-head rendering crashed. Import added.
- **`Signal` → `pyqtSignal`**: the installed PyQt6 only exposes the legacy signal name.
