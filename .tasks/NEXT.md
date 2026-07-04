# Next

## TASK-099: Convert pb_reader.py into BCL Cascade Encrypted Chat Tool (VBStyle)
**Priority:** P1 | **Tags:** vbstyle, bcl, pb-reader, cascade, encrypted, chat, refactor
**Updated:** 2026-07-03 23:52

Convert `chat_mover/pb_reader.py` (1,040 lines) into a VBStyle-compliant BCL unit. Rename from "pbReader" to "BclCascadeEncryptedChat" — a tool for decrypting and searching Windsurf Cascade .pb chat files.

### Current State

- **File:** `chat_mover/pb_reader.py` (1,040 lines)
- **Function:** Decrypts and searches Windsurf Cascade `.pb` (protobuf) chat files from `~/.codeium/windsurf/`
- **Current CLI commands:** `scan`, `list`, `load-all`, `stats`, `load`, `read`, `search`, `export`
- **Search scopes:** all, user, assistant, commands
- **Discovered files:** 13 cascade `.pb` files + memories files (total ~130MB)
- **RAM DB:** In-memory SQLite for loaded trajectories, steps, messages, commands, checkpoints

### Target

- **Class name:** `BclCascadeEncryptedChat`
- **File name:** `BclCascadeEncryptedChat.py` (or keep `pb_reader.py` as alias — human review)
- **Location:** `chat_mover/` (same directory)
- **VBStyle compliance:** Full — headers, Run() dispatch, Tuple3 returns, self.state dict, no print/decorators/self._/hardcode/tabs

### Plan

- Step 1: Read and analyze full 1,040-line `pb_reader.py` — extract all classes, functions, imports, constants, protobuf definitions
- Step 2: Design BCL header block — `[@GHOST]`, `[@VBSTYLE]`, `[@FILEID]`, `[@SUMMARY]`, `[@CLASS]`, `[@METHOD]` headers for the file and each class
- Step 3: Refactor into VBStyle class `BclCascadeEncryptedChat`:
  - `__init__(self, mem=None, db=None, param=None)` — standard ctor
  - `self.state` dict (NO `self._`)
  - `Run(self, command, params=None)` — dispatch: scan | list | load_all | stats | load | read | search | export | read_state | set_config
  - All methods return Tuple3: `(1, data, None)` or `(0, None, (code, desc, 0))`
  - `_p()` helper for logging
  - No `print()`, no `@property`/`@staticmethod`/`@classmethod`, no hardcoded values
  - All constants UPPERCASE in Config or class-level
  - PascalCase, spaces only, no tabs
- Step 4: Extract constants into Config.py (scan path, RAM DB schema, search defaults, export formats)
- Step 5: Preserve all existing functionality:
  - Protobuf parsing of `.pb` files
  - In-memory SQLite DB for trajectories/steps/messages
  - Full-text search across loaded chat content
  - Export to markdown
  - Scan/list/load-all/stats commands
- Step 6: Test end-to-end:
  - `python3 BclCascadeEncryptedChat.py scan` — finds all .pb files
  - `python3 BclCascadeEncryptedChat.py load-all` — loads all into RAM
  - `python3 BclCascadeEncryptedChat.py stats` — shows RAM DB statistics
  - `python3 BclCascadeEncryptedChat.py search "law migration"` — returns matching chat content
  - `python3 BclCascadeEncryptedChat.py export --trajectory <id>` — exports to markdown
- Step 7: Verify VBStyle compliance:
  - `py_compile` passes
  - `grep print(` = zero
  - `grep @staticmethod|@property|@classmethod` = zero
  - `grep self\._` = zero
  - All methods return Tuple3
  - `Run()` exists
  - BCL headers present
- Step 8: Wire into `chat_mover/Config.py` if one exists, or create one
- Risks: (1) Protobuf schema may be undocumented — reverse-engineered from .pb files; (2) Large .pb files (37MB) may need streaming; (3) `.codeiumignore` blocks direct file access — may need to work via run_command

---

## TASK-100: Move memunit_gui.py to Wayne GUI Folder + VBStyle Cleanup
**Priority:** P1 | **Tags:** gui, memunit, vbstyle, move, organize, cascade-toolstack
**Updated:** 2026-07-03 23:54

Move `Cascade_toolStack/memunit_gui.py` (36,845 bytes, PyQt6) to Wayne's GUI folder. Then VBStyle-comply the file and ensure it still runs.

### Current State

- **File:** `Cascade_toolStack/memunit_gui.py` (36,845 bytes, PyQt6 GUI)
- **Function:** Visual tree showing MemUnit architecture (DOM_IO, GPU, DB) + live BCL console for dispatch
- **Runs successfully** — confirmed via `python3 memunit_gui.py` (exit code 0)
- **Warning:** `qt.qpa.fonts: Populating font family aliases took 64 ms. Replace uses of missing font family "Monospace"` — needs font fix

### Plan

- Step 1: Identify Wayne's GUI folder (likely `core/Dom_Gui/` or similar — verify with user)
- Step 2: Move `memunit_gui.py` from `Cascade_toolStack/` to the GUI folder
- Step 3: Fix "Monospace" font warning — replace with a valid system font (e.g. "Menlo" or "Courier" on macOS)
- Step 4: VBStyle compliance:
  - Add BCL headers (`[@GHOST]`, `[@VBSTYLE]`, `[@FILEID]`, `[@SUMMARY]`, `[@CLASS]`, `[@METHOD]`)
  - Add `Run(self, command, params=None)` dispatch if not present
  - Ensure Tuple3 returns on all methods
  - Remove `print()` calls
  - Remove any `@property`/`@staticmethod`/`@classmethod`
  - Remove any `self._` (use `self.state` dict)
  - No hardcoded values (extract to Config)
- Step 5: Verify it still runs after move + cleanup:
  - `python3 memunit_gui.py` launches without errors
  - Tree displays correctly (MemUnit -> DOM_IO, GPU, DB)
  - BCL console dispatches commands
- Step 6: Wire into the GUI folder's Config.py if one exists
- Risks: (1) Moving may break import paths — check for relative imports; (2) PyQt6 GUI classes may need significant refactor for VBStyle (no @property, no self._); (3) Font fix is trivial but needs macOS-specific font name

---

## TASK-101: Convert All Cascade_toolStack Code into BCL Units for MCP Execution
**Priority:** P0 | **Tags:** bcl, vbstyle, cascade-toolstack, mcp, conversion, organize
**Updated:** 2026-07-03 23:57

Convert all Python and C code in Cascade_toolStack/ into BCL units that can be planned and executed via Cascade MCP server. Every file becomes a VBStyle-compliant BCL unit with Run() dispatch, Tuple3 returns, and BCL headers.

### Current Inventory

**Root .py files (18):** Databse_combinder.py, ErrorFixTrainer.py, ai_fix_bridge.py, bcl_3pass_builder.py, bcl_build.py, bcl_inserter.py, build_c_codebase_db.py, c_analysis_core.py, c_analysis_engine.py, demo_analyzer.py, filename_engine.py, graph_cascade_cli.py, memunit_gui.py (-> TASK-100), pipeline_executor.py, ram_state_engine.py, strips_planner.py, test_module.py, transform_graph_engine.py

**bin_tools/ (104 items):** C binaries (Cleaner.c, ErrorFixTrainer.c, PbReader.c, bcl_builder.c, cascade_cli.c, codeingest.c, cognitive_core.c, discovery.c, mdmerge.c, msearch.c, schemalint.c, smartcli.c, vbcheck.c, wcmd.c, windir.c), Python tools (LocalAgent.py, ai_fix_bridge.py, analyze_code.py, cognition_fabric.py, dedupe_explorer.py, gemini_cli.py, msearch_mcp_server.py, msearch_qdrant.py, router_cli.py), databases (ErrorFixTrainer.db, cognition_cache.db, online_projects.db), compiled binaries, debug symbols, .old files

**bcl_units/ (42 items):** C BCL stubs (bcl_*.c), bcl_toolstack.h, BCL_UNIT_MAP.md, mac_command_crawler.py, mac_command_database.py, mac_commands.db, mac_commands_comprehensive.db, destruction guard specs, empty subdirs (.backup, .merged, .new, .orig, .patch, downloads)

**vbast/ (10 items):** ast_walker.c, bcl_stamper.c, dom_unified.py, graph_builder.c, mysql_store.c, vbast.c, vbast.h, vbstyle_check.c, Makefile, compiled vbast binary

**arch_test/ (10 items):** MemUnit_real.py, MemBus_real.py, Executor_real.py, memdb_real.py, arch_graph.py, boot_test.py, run_codegraph_compare.py, run_codegraph_on_arch.py, SVGs

**Databases (6):** cascade_unified.db (154M), cascade_unified.sql (171M), c_codebase.db (118M), pipeline_graph.db (45M), state_memory.db (2.5M), cascade_archive.db (1.2M), bcl_build.db (44K)

**Built_tools/ (35 items):** Compiled binaries + symlinks to system tools (rg, ack, grep, find, which, etc.)

**Duplicates found:** ai_fix_bridge.py (root + bin_tools + Built_tools), ErrorFixTrainer.py (root + bin_tools + Built_tools), cascade_cli (root + bin_tools + Built_tools)

### Plan

- Step 1: AUDIT - Full inventory of every file, classify as: keep/convert, archive, delete, deduplicate
- Step 2: DEDUPLICATE - Remove triplicated files (ai_fix_bridge.py, ErrorFixTrainer.py, cascade_cli). Keep canonical version, archive others
- Step 3: CLEAN DEAD FILES - Remove .old files (web.c.old, web.h.old), debug symbols (mdmerge_debug.dSYM), empty subdirs (.backup/.merged/.new/.orig/.patch with 0 items), .DS_Store
- Step 4: DATABASE AUDIT - Check each .db file: is it actively used? Is it backed up? Document purpose, size, last-modified, whether it can be archived
- Step 5: CONVERT ROOT .py FILES - Each of the 17 remaining .py files (excluding memunit_gui.py -> TASK-100) becomes a VBStyle BCL unit:
  - Add BCL headers ([@GHOST], [@VBSTYLE], [@FILEID], [@SUMMARY], [@CLASS], [@METHOD])
  - Add Run(self, command, params=None) dispatch
  - Ensure Tuple3 returns, self.state dict, no print/decorators/self._
  - Extract constants to Config
- Step 6: CONVERT bin_tools/ .py FILES - Same VBStyle conversion for all Python files in bin_tools/
- Step 7: CONVERT vbast/ .py FILES - VBStyle conversion for dom_unified.py
- Step 8: C FILES - Document each .c file with BCL header comments, classify as: production tool, experimental, archived
- Step 9: BCL UNIT MAP - Update bcl_units/BCL_UNIT_MAP.md with full inventory of all converted units, their Run() commands, and dependencies
- Step 10: MCP WIRING - Wire all BCL units into Cascade MCP server so they can be planned and executed via taskplanner
- Step 11: VERIFY - py_compile all .py files, grep for violations, test Run() dispatch on each unit
- Step 12: ARCHIVE - Move dead/duplicate/superseded files to archive folder, document what was removed
- Risks: (1) Large databases (154M, 118M) - do NOT delete, archive if unused; (2) C binaries may be actively used - verify before archiving; (3) bcl_units/ has mac_commands_comprehensive.db (18M) - verify if needed; (4) Built_tools/ symlinks to system tools (rg, ack, grep) - remove symlinks, keep actual compiled tools

---

## TASK-102: Merge All Cascade_toolStack Databases into One Unified Database
**Priority:** P0 | **Tags:** database, merge, unify, cascade-toolstack, safety, migration
**Updated:** 2026-07-03 23:56

Identify all databases in Cascade_toolStack, generate a safe merge plan to consolidate them into one unified database, test the plan, then remove the old databases only after verification.

### Current Databases Found

| # | File | Size | Location | Purpose (TBD) |
|---|------|------|----------|---------------|
| 1 | cascade_unified.db | 154M | root | Unknown — largest DB, needs schema audit |
| 2 | cascade_unified.sql | 171M | root | SQL dump of cascade_unified.db |
| 3 | c_codebase.db | 118M | root | C codebase analysis data |
| 4 | pipeline_graph.db | 45M | root | Pipeline graph data |
| 5 | state_memory.db | 2.5M | root | State memory engine data |
| 6 | cascade_archive.db | 1.2M | root | Archive data |
| 7 | bcl_build.db | 44K | root | BCL build data |
| 8 | ErrorFixTrainer.db | 104K | bin_tools/ | Error fix training data |
| 9 | cognition_cache.db | 68K | bin_tools/ | Cognition cache |
| 10 | cognition_cache.db | 12K | Built_tools/ | Cognition cache (duplicate?) |
| 11 | online_projects.db | 24K | bin_tools/ | Online projects |
| 12 | mac_commands.db | 60K | bcl_units/ | Mac command database |
| 13 | mac_commands_comprehensive.db | 18M | bcl_units/ | Comprehensive mac commands |

**Total: ~510M across 13 database files (12 unique + 1 duplicate)**

### Plan

- Step 1: SCHEMA AUDIT - For each database, run `sqlite3 <db> .schema` and `sqlite3 <db> .tables` to document every table, column, and index. Record row counts per table.
- Step 2: OVERLAP ANALYSIS - Compare schemas across all databases. Identify:
  - Tables with same name in different DBs (potential merge candidates)
  - Tables with same structure but different names (potential duplicates)
  - Tables that are unique to one DB (must be preserved as-is)
  - Foreign key relationships that cross DB boundaries
- Step 3: UNIFIED SCHEMA DESIGN - Design a single unified database schema that:
  - Preserves every table from every source DB (no data loss)
  - Resolves naming conflicts (prefix tables with source DB name if needed)
  - Adds a `source_db` column to every table for provenance tracking
  - Maintains all indexes and constraints
- Step 4: MERGE PLAN - Generate step-by-step SQL migration plan:
  - CREATE new unified DB with merged schema
  - ATTACH each source DB
  - INSERT INTO unified SELECT FROM source (with provenance column)
  - Verify row counts match (source sum = unified total per table)
- Step 5: DRY RUN - Execute the merge plan in a temporary copy (copy all .db files to /tmp, run merge there). Verify:
  - Every table exists in unified DB
  - Row counts: sum of source tables = unified table count
  - No data corruption (spot check random rows)
  - All indexes present
  - Query performance acceptable
- Step 6: REVIEW - Present merge results to user for approval:
  - Before/after row counts
  - Unified schema
  - Total size comparison (unified vs sum of parts)
  - Any conflicts found and how they were resolved
- Step 7: EXECUTE - After user approval, execute merge on real databases:
  - Backup all original .db files to archive folder first
  - Run the verified merge plan
  - Verify the unified DB
- Step 8: CODE UPDATE - Update all Python/C code that references individual .db files to point to the unified DB. Search for hardcoded paths like `cascade_unified.db`, `c_codebase.db`, `pipeline_graph.db`, etc.
- Step 9: VERIFY CODE - Run all tools that use databases to confirm they work with the unified DB
- Step 10: CLEANUP - After all code verified working with unified DB:
  - Keep backups in archive folder (do NOT delete yet)
  - Remove original .db files from active directories
  - Update documentation
  - User confirms cleanup is safe before final deletion
- Risks: (1) 510M total data — merge may produce large unified DB; (2) Some DBs may be SQLite, others MySQL — verify engine; (3) c_codebase.db (118M) may have complex schema with many tables; (4) Code may have hardcoded DB paths that break after merge; (5) cascade_unified.sql is a dump — may be stale, verify against .db; (6) cognition_cache.db appears in two locations — determine which is canonical

---

## TASK-103: Investigate BCL Unit Map — Audit 21 Registered C Units vs Actual Files
**Priority:** P0 | **Tags:** investigation, bcl-units, audit, c-code, architecture
**Updated:** 2026-07-04 00:01

The BCL_UNIT_MAP.md documents 21 registered C units (8 IMPLEMENTED, 13 SHELL stubs) plus a proposed migration to split msearch into 8 search units. Investigate the gap between the map and reality.

### Key Questions

- Which of the 8 IMPLEMENTED C units actually compile and run?
- Which of the 13 SHELL stubs have been filled in since the map was written?
- The map proposes deleting bcl_msearch.c and bcl_magnetic.c — has this been done?
- The map proposes renaming 5 files (bcl_msearch_qdrant.c -> bcl_search_vector.c, etc.) — have these been renamed?
- The map proposes 3 NEW files (bcl_search_web.c, bcl_search_fs.c, bcl_search_db.c) — do they exist?
- bcl_tool_main.c is the entry point — does it still reference the old unit names?

### Plan

- Step 1: List all .c files in bcl_units/ and compare against BCL_UNIT_MAP.md
- Step 2: For each IMPLEMENTED unit, try compiling it (make <target>) and running its commands
- Step 3: For each SHELL unit, check if it has been expanded beyond 43 lines (the stub size)
- Step 4: Check if bcl_tool_main.c registration list matches actual files
- Step 5: Check if bcl_toolstack.h declarations match actual function signatures
- Step 6: Document: what exists, what is stale, what is missing
- Output: Updated BCL_UNIT_MAP.md reflecting current reality

---

## TASK-104: Investigate Root Python Engine Files — Map Classes, Dependencies, and VBStyle Compliance
**Priority:** P0 | **Tags:** investigation, python, vbstyle, audit, cascade-toolstack
**Updated:** 2026-07-04 00:01

The 18 root .py files in Cascade_toolStack/ are the Python engine layer. None have been audited for VBStyle compliance or inter-file dependencies. This is a prerequisite for TASK-101.

### Key Files to Investigate

| File | Size | Likely Purpose |
|---|---|---|
| ram_state_engine.py | 56K | RAM state management — possibly the core state machine |
| strips_planner.py | 42K | STRIPS-style AI planner — goal/ precondition/ effect model |
| bcl_build.py | 37K | BCL builder — constructs BCL packets from code |
| pipeline_executor.py | 26K | Pipeline execution engine — runs the 10 pipelines |
| bcl_3pass_builder.py | 27K | 3-pass BCL builder — multi-phase compilation |
| build_c_codebase_db.py | 23K | Builds c_codebase.db (118M) from C source analysis |
| ErrorFixTrainer.py | 22K | Trains error fix models — connects to .cascade_fix_rules |
| ai_fix_bridge.py | 15K | Bridges AI fix suggestions to code changes |
| c_analysis_engine.py | 15K | C code analysis engine — AST parsing for C |
| filename_engine.py | 13K | Filename normalization/ routing engine |
| graph_cascade_cli.py | 9K | CLI for cascade graph operations |
| bcl_inserter.py | 10K | Inserts BCL packets into target files |
| c_analysis_core.py | 6K | Core C analysis primitives |
| transform_graph_engine.py | 5K | Graph transformation engine |
| Databse_combinder.py | 3K | Database combiner (note: typo in name) |
| demo_analyzer.py | 1K | Demo/ test analyzer |
| test_module.py | 2K | Test module |
| memunit_gui.py | 37K | -> TASK-100 (moved to GUI folder) |

### Plan

- Step 1: For each .py file, extract: class names, method names, imports (internal + external), hardcoded paths, DB references
- Step 2: Check VBStyle compliance: has Run()? has Tuple3? has print()? has @property/@staticmethod? has self._? has BCL headers?
- Step 3: Map inter-file dependencies (which file imports which)
- Step 4: Identify which files reference which .db files (for TASK-102 cross-reference)
- Step 5: Identify dead code (files not imported by anything, functions never called)
- Step 6: Check for the typo file Databse_combinder.py — is it actively used or can it be renamed?
- Output: Dependency graph + VBStyle compliance report per file

---

## TASK-105: Investigate bin_tools/ — Classify 104 Files as Production, Experimental, or Dead
**Priority:** P1 | **Tags:** investigation, bin-tools, audit, classification, cascade-toolstack
**Updated:** 2026-07-04 00:01

bin_tools/ has 104 items — a mix of C source, compiled binaries, Python tools, databases, debug symbols, and .old files. Need to classify each as production, experimental, or dead for the cleanup in TASK-101.

### Key Questions

- Which compiled binaries are actively used vs stale builds?
- web.c.old and web.h.old — safe to delete?
- mdmerge_debug + mdmerge_debug.dSYM — debug artifacts, safe to remove?
- mdmerge_modular/ (35 items) — is this the active version or superseded by bin_tools/mdmerge?
- msearch_v4.c vs msearch_v5.c vs msearch.c — which is the current version?
- wcmd.c vs wcmd_v1.c — which is current?
- coretotch_fix + coretotch_fix.c + coretotch_fix.conf — what is this? Is it needed?
- fix_training.json (25K) — training data for ErrorFixTrainer, still needed?
- node_mem_flags.sh, node_mem_profile.json, node_mem_profile.txt — Node.js memory profiling, still relevant?
- v8_flags_research.md — V8 engine research, still relevant?
- .cascade_fix_weights.bin (14K) — binary weights for fix system, still used?
- mcp_mem_audit.md — MCP memory audit report, still relevant?

### Plan

- Step 1: For each .c file: check if it compiles, check if a binary exists in Built_tools/, check if referenced by Makefile
- Step 2: For each .py file: check if imported by any root .py file, check if it runs standalone
- Step 3: For each binary: check last-modified date, compare against source .c date
- Step 4: For .old, .dSYM, debug files: confirm safe to archive
- Step 5: For mdmerge_modular/ (35 items): compare against bin_tools/mdmerge — which is canonical?
- Step 6: Classify each file: PRODUCTION (keep), EXPERIMENTAL (archive), DEAD (delete)
- Output: Classification table with rationale per file

---

## TASK-106: Investigate vbast/ Subsystem — VBStyle AST Stamper Architecture
**Priority:** P1 | **Tags:** investigation, vbast, ast, vbstyle, architecture, cascade-toolstack
**Updated:** 2026-07-04 00:01

vbast/ is a C-based VBStyle AST system with 10 files. It appears to be a standalone tool for walking ASTs, stamping BCL headers, and checking VBStyle compliance. Need to understand its role and whether it overlaps with existing Python VBStyle tools.

### Files

| File | Size | Purpose (TBD) |
|---|---|---|
| ast_walker.c | 40K | AST traversal engine |
| vbast.c | 9K | Main entry point |
| vbast.h | 9K | Shared header |
| graph_builder.c | 12K | Builds graph from AST |
| mysql_store.c | 13K | Stores AST data in MySQL |
| bcl_stamper.c | 5K | Stamps BCL headers onto files |
| vbstyle_check.c | 7K | VBStyle compliance checker |
| dom_unified.py | 16K | Python domain unified tool |
| Makefile | 3K | Build system |
| vbast (binary) | 54K | Compiled binary |

### Key Questions

- Does vbast overlap with Vbs_Code_Verifiation/vbs_rule_engine.py (the Python VBStyle checker)?
- Does bcl_stamper.c overlap with the BCL header stamper in chat_mover/?
- Does mysql_store.c connect to vb_shared or a different database?
- Is dom_unified.py related to core/Dom_Unified/ or is it a separate thing?
- Does vbstyle_check.c implement the same rules as vb_shared.rule_tokens?
- Is vbast actively used or has it been superseded by Python tools?

### Plan

- Step 1: Read vbast.c and vbast.h to understand the architecture
- Step 2: Read bcl_stamper.c — compare with Python BCL stamping tools
- Step 3: Read vbstyle_check.c — compare with vbs_rule_engine.py rules
- Step 4: Read dom_unified.py — check if it relates to core/Dom_Unified/
- Step 5: Check if vbast binary runs: `./vbast --help` or `./vbast` with no args
- Step 6: Check Makefile for build targets and dependencies
- Step 7: Search codebase for references to vbast (who calls it?)
- Output: Architecture summary + overlap analysis with Python tools

---

## TASK-108: Investigate Built_tools/ — Remove System Symlinks, Keep Compiled Tools
**Priority:** P1 | **Tags:** investigation, built-tools, symlinks, cleanup, cascade-toolstack
**Updated:** 2026-07-04 00:01

Built_tools/ has 35 items. Some are compiled Cascade tools (bcl_tool, cascade_cli, msearch, mdmerge, etc.) but many are 7-byte symlinks to system utilities (rg, ack, grep, find, which, whereis, locate, mdfind, fd, fdfind, ag, dir). These symlinks are unnecessary and clutter the folder.

### Plan

- Step 1: Identify all 7-byte files (these are likely symlinks: `rg -> /usr/local/bin/rg` etc.)
- Step 2: Verify each is a symlink with `file` or `readlink`
- Step 3: Remove system tool symlinks (rg, ack, ag, grep, find, which, whereis, locate, mdfind, fd, fdfind, dir)
- Step 4: Keep compiled Cascade tools: bcl_tool, cascade_cli, msearch, msearch2, msearch3, mdmerge, schemalint, vbcheck, wcmd, smartcli, ghostctl, cognitive_core, codeingest, devindocs, dir, Cleaner, db_exec_demo
- Step 5: Check for duplicate tools (msearch vs msearch2 vs msearch3 — which is current?)
- Step 6: Check cognitive_cache.db (12K) — duplicate of bin_tools/cognition_cache.db?
- Step 7: Check cascade_cli_graph.svg — is this generated or hand-drawn?
- Output: Clean Built_tools/ with only compiled Cascade binaries

---

## TASK-109: Investigate .cascade_fix_rules and ErrorFixTrainer System — AI Error Fix Pipeline
**Priority:** P1 | **Tags:** investigation, error-fix, ai, training, cascade-toolstack
**Updated:** 2026-07-04 00:01

The Cascade_toolStack contains an AI error fix system spanning multiple files: `.cascade_fix_rules` (6K JSON with 15 error patterns), `ErrorFixTrainer.py` (22K), `ai_fix_bridge.py` (15K), `bin_tools/ErrorFixTrainer.c` (16K), `bin_tools/fix_training.json` (25K), `.cascade_fix_weights.bin` (15K). Need to understand the full pipeline.

### Key Questions

- What is the training pipeline? (rules -> trainer -> weights -> bridge -> code fixes?)
- How does .cascade_fix_rules (JSON) relate to MySQL vb_shared.learned_rules?
- Is ErrorFixTrainer.py (Python) or ErrorFixTrainer.c (C) the canonical version?
- What does .cascade_fix_weights.bin contain — neural weights, scoring weights, or rule priorities?
- How does ai_fix_bridge.py connect to the codebase — does it auto-apply fixes?
- Is fix_training.json training data for a model or rule examples?
- Does this system connect to the cascade_cli error detection pipeline?

### Plan

- Step 1: Read .cascade_fix_rules — catalog all 15 error patterns and their fix actions
- Step 2: Read ErrorFixTrainer.py — understand the training loop, model, and output
- Step 3: Read ai_fix_bridge.py — understand how fixes are applied to code
- Step 4: Check if .cascade_fix_weights.bin is loadable (try Python pickle, numpy, json)
- Step 5: Read bin_tools/fix_training.json — what training examples does it contain?
- Step 6: Compare ErrorFixTrainer.py vs ErrorFixTrainer.c — which is newer, which is canonical?
- Step 7: Search for references to cascade_fix in other files — who consumes this system?
- Step 8: Check if this overlaps with Vbs_Code_Verifiation/ error tracking
- Output: Full pipeline diagram + data flow + canonical file identification

---

## TASK-110: Investigate Makefile Build System — Map All Targets and Dependencies
**Priority:** P2 | **Tags:** investigation, makefile, build, c-code, cascade-toolstack
**Updated:** 2026-07-04 00:01

The root Makefile builds msearch_v5, spine_test, and cascade_cli. But there are also Makefiles in bcl_units/ and vbast/. Need to understand the complete build system.

### Plan

- Step 1: Read root Makefile — catalog all targets, variables, dependencies
- Step 2: Read bcl_units/Makefile — what does it build? (bcl_tool?)
- Step 3: Read vbast/Makefile — what does it build? (vbast binary?)
- Step 4: Check: are there any other Makefiles or build scripts in subdirectories?
- Step 5: Try running `make -n` (dry run) on each Makefile to see what would be built
- Step 6: Check if all source files referenced in Makefiles actually exist
- Step 7: Identify orphaned .c files not referenced by any Makefile
- Step 8: Check if config_seed.sql has been applied (does ~/.config/cascade/cascade.db exist?)
- Output: Complete build system map + orphaned files list

---

## TASK-111: Investigate Inter-System Connections — How Cascade_toolStack Connects to the Rest of the Codebase
**Priority:** P0 | **Tags:** investigation, architecture, connections, dependencies, cascade-toolstack
**Updated:** 2026-07-04 00:01

Cascade_toolStack does not exist in isolation. It connects to MySQL (vb_shared, diagnostic_kb), Qdrant, the BCL system, the VBStyle system, and the pipeline system. Need to map all external connections.

### Key Questions

- Which files connect to MySQL? Which databases? Which tables?
- Which files connect to Qdrant? Which collections?
- Which files reference core/Dom_* domains?
- Which files reference chat_mover/ tools?
- Which files reference Vbs_Code_Verifiation/?
- Which files reference core/Piplines/?
- Does the cascade_cli in Cascade_toolStack relate to the cascade_cli.py in Downloads/?
- Does the config_seed.sql connect to the ~/.config/cascade/ config system?
- How does the MemUnit architecture relate to the Dom_Graph architecture?

### Plan

- Step 1: Grep all .py files for import statements referencing other directories
- Step 2: Grep all .c files for #include statements referencing external headers
- Step 3: Grep all files for MySQL connection strings (localhost:3306, mysql_real_connect)
- Step 4: Grep all files for Qdrant references (localhost:6333, qdrant)
- Step 5: Grep all files for hardcoded paths (/Users/wws/, ~/.config/, ~/.codeium/)
- Step 6: Map: Cascade_toolStack file -> external system -> specific resource (DB/table/collection/path)
- Step 7: Identify circular dependencies or broken references
- Output: Connection map showing all external dependencies

---
