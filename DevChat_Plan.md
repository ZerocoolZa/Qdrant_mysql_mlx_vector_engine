# Qdrant MySQL MLX Vector Engine — Master DevChat Plan

> **Project Root**: `Qdrant_mysql_mlx_vector_engine/`
> **Created**: 2026-06-22
> **Status**: 9 satellite modules built, Ghost core not started

---

## Project Overview

Ghost is a local AI brain. The user talks to it through a CLI or GUI. Behind the scenes, three services do the work: MLX (LLM + embeddings), Qdrant (vector search), MySQL (structured data).

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

---

## Module Map (9 Modules)

| Module | Lines | Status | DevChat Plan |
|--------|-------|--------|--------------|
| `qa_engine/` | 6,497 | Working — testing phase | `qa_engine/DevChat_Plan.md` |
| `BCL/` | 6,639 | Complete — 3 tasks done | `BCL/DevChat_Plan.md` |
| `Smart_system_seach/` | 4,388 | Working | `Smart_system_seach/DevChat_Plan.md` |
| `Sql_Schema_Config/` | 991 | Working — schema designed | `Sql_Schema_Config/DevChat_Plan.md` |
| `Vbs_Code_Verifiation/` | 713 | Working — scanner built | `Vbs_Code_Verifiation/DevChat_Plan.md` |
| `efl_brain/` | 3,747 | Working — RAM AI built | `efl_brain/DevChat_Plan.md` |
| `gui_engine/` | 1,332 | Working — engine built | `gui_engine/DevChat_Plan.md` |
| `svg_engine/` | 347 C + 870 Python | Complete | `svg_engine/DevChat_Plan.md` |
| `mcp-server-email/` | 7,003 Go + 21,000 test | Complete — 22 tools | `mcp-server-email/DevChat_Plan.md` |
| **Total** | ~52,000+ | | |

---

## Session History Summary (67 Devin Chats)

### VBStyle Book & Documentation (15 sessions)
- 56-chapter, 31,344-word VBStyle book
- BookViewer.py with turn.js, search, TTS
- Book.py CLI for SQLite book management
- Config centralized into config.py

### BCL Engine (8 sessions)
- Complete BCL pipeline: lexer → parser → validator → fixer → engine
- 12 validation rules, auto-fix with undo/rollback
- 3 completed tasks (TASK-002, TASK-003, TASK-004)
- BCL converter for markdown/chat/Python/JSON → BCL tokens

### QA Engine (6 sessions)
- GhostQAEngine.py — 6 pipeline modes (A/B/C/D/E/R)
- Mode D (Qwen 1.5B) = 89% accuracy, Mode B (BERT) = 57%
- QueryInterpreter + ModeRouter for Mode R
- Discovered existing Fact Store in MySQL (know_nodes, know_answers)
- 3-layer epistemic system designed (Appendix C)

### Code-in-Database / Domain Closure (12 sessions)
- 20 schema variations, selected v20_hybrid_best.db
- 873 methods across 58 VBStyle domains
- Fixed VBStyle violations (one method at a time)
- Domain closure substantially complete

### Search & Tools (5 sessions)
- msearch.c with Qdrant integration (hybrid search)
- Smart system search module with GUI
- PyQt6 mini search GUI with minimize-to-ball

### MCP Email Server (2 sessions)
- Go-based MCP server (22 tools, multi-account)
- Unified MCP Setup Wizard (Fyne v2, 11 pages)
- 91.1% test coverage

### SVG Animation Engine (1 session — today)
- C core engine + Python Qt studio
- 14 object types, 9 motion types, 13 easing functions
- Particle system, SMIL animations, live preview

### Devin Docs & Tooling (4 sessions)
- devindocs CLI tool + PyQt6 GUI
- Collected docs.devin.ai content

### Misc (5 sessions)
- Cleaner.c cache utility
- GUI lag diagnosis
- Chat manager (MD/JSON/JSONL)
- ContextRAM BGE integration
- EFL brain module

---

## What's NOT Built — The Ghost Core

The PLAN.md describes an 8-step build order. **None of these have been started:**

1. **SQLite schema** — code-as-filesystem DB (methods, classes, domains, config tables)
2. **config.py** — VBStyle config class, reads/writes BCL to SQLite
3. **Review config together** ← planned stop point
4. **services/** — port msearch, mlx, mysql as VBStyle classes
5. **models/** — Pydantic schemas for API
6. **api/server.py** — FastAPI endpoints
7. **cli/ghost_cli.py** — Typer CLI (`ghost ask`, `ghost search`, `ghost remember`)
8. **gui/settings_gui.py** — property panel with tree + search + combos

### Existing Infrastructure (Ready to Use)

- **MySQL**: 11 databases, 59+ tables in vb_shared, root@localhost
- **Qdrant**: 13 collections, 384-dim BGE embeddings, localhost:6333
- **msearch**: hybrid MySQL + Qdrant search binary
- **MLX**: Qwen2.5-Coder-1.5B, BGE-small-en-v1.5
- **CoreML**: BERT SQuAD FP16, TokenEmbedder, CodeBERT, MiniLM
- **GUI Engine**: config-driven PyQt6 renderer
- **BCL Engine**: complete parse/validate/fix/serialize pipeline

---

## Task Tracker Status

| Task | Status | Description |
|------|--------|-------------|
| TASK-001 | Backlog | Cascade_tools — search tools to prevent "searching and not finding" |
| TASK-002 | Done | Harden BCL engine invariants |
| TASK-003 | Done | Max-out BCL engine stability |
| TASK-004 | Done | Fix all BCL correctness gaps |

---

## Next Steps (Priority Order)

### Phase 1: Ghost Core Scaffold
1. Create `ghost/` directory structure
2. Build SQLite schema (methods, classes, domains, categories, types, config)
3. Build `ghost/config.py` (VBStyle, BCL config, reads/writes SQLite)
4. Review config together

### Phase 2: Services
5. Port msearch → `ghost/services/search_service.py`
6. Port MLX → `ghost/services/mlx_service.py`
7. Port MySQL → `ghost/services/mysql_service.py`
8. Wire QA engine → `ghost/services/qa_service.py`

### Phase 3: Interface
9. Build FastAPI server → `ghost/api/server.py`
10. Build Typer CLI → `ghost/cli/ghost_cli.py`
11. Build settings GUI → `ghost/gui/settings_gui.py`

### Phase 4: Integration
12. Wire Fact Store (MySQL know_* tables) to QA engine
13. Wire EFL brain as reasoning layer
14. Wire SVG engine as UI skin
15. Wire MCP email as email service

---

## Open Questions (from PLAN.md — Answered)

| # | Question | Status |
|---|----------|--------|
| Q1 | MemUnit — lightweight, import, or skip? | Answered |
| Q2 | FastAPI decorator conflict | Answered |
| Q3 | SQLite methods table — SQL only or Python too? | Answered |
| Q4 | engine.py JSON internally — how to handle? | Answered |
| Q5 | no_utility_funcs — shared validation? | Answered |
| Q6 | `__main__` block ban — CLI entry point? | Answered |
| Q7 | BCL parser — which source? | Answered |
| Q8 | Config defaults — dict or BCL in code? | Answered |
| Q9 | No-JSON rule — external APIs? | Answered |
| Q10 | Ghost header format | Answered |
| Q11 | Report class needed? | Answered |
| Q12 | SQLite DB location? | Answered |
| Q13 | 11 classes enough? | Answered |
| Q14 | Qdrant memory collection 768-dim? | Answered |

---

## Answers (Q1-Q14)

> Decisions made from existing VBStyle rules (`obey.md`), existing codebase patterns (efl_brain, BCL/, qa_engine, code_store.db), and the Q&A context in `PLAN.md` §11. Each answer cites the evidence used.

### A1 — MemUnit: lightweight, import, or skip?

**Decision: (A) Build a lightweight MemUnit — shared state dict, `mem.get/put` interface.**

Reasoning:
- `obey.md` rule `@memunit` states "all code execute only in memunit" — MemUnit is mandatory in VBStyle, not optional.
- The existing `MemUnit` in `contestsystem/Database/CODE/ingest_markdown.py` and `contestsystem/Database/zram/Gui/core_mem.py` (`ZramGuiCoreMemUnit`) is tightly coupled to the contestsystem MySQL common DB and its 72-table schema. Importing it would drag in vb_shared, vb_code_test, and the full contestsystem boot spine.
- Ghost is standalone (per PLAN.md Q1) — it has its own SQLite + Qdrant + MySQL (Chat_History) stack. Importing contestsystem's MemUnit would create a circular dependency and violate the "one class, one domain, one authority" rule (`@auth`).
- The QA engine's `pinnacle_harness.py` line 66 documents the contract: "MemUnit is the shared memory bus — CORE_MEMUNIT connects everything. Config values like db_user, db_name, sqlite_db_path, and embed_dim all flow through CORE_MEMUNIT."
- Minimum interface: `__init__(self, mem=None, db=None, param=None)` (per `@ctor`), `Run(command, params)` dispatch (per `@run`), `self.state` dict with `config`, `catalog`, `results` keys (per `@state`), and `get(key)`/`put(key, value)` methods that read/write `self.state`. This is ~50 lines and keeps Ghost decoupled.
- The efl_brain brothers already use this pattern — `Efi_brain_db.py` (`BrainDb` class) is a lightweight DB-mediated communication layer with `__init__(self, db_path=None)` and no cross-imports between brothers. Ghost's MemUnit follows the same "dinner table" philosophy.

### A2 — FastAPI decorator conflict

**Decision: (C) Use FastAPI's `app.add_api_route()` programmatic registration — no decorators.**

Reasoning:
- `obey.md` rule `@decorators` is explicit: "@property; @staticmethod etc are never allowed". This is a hard rule, not a guideline.
- Option (A) "exception for API layer" would violate `@norule` ("do not invent rules") — we cannot carve out exceptions to permanent rules.
- Option (B) "write our own HTTP server" is reinventing the wheel and violates `@noarch` ("do not invent architecture"). FastAPI's async, validation, and OpenAPI generation are valuable.
- Option (D) "fork FastAPI" is massive overkill and violates `@noarch`.
- FastAPI supports `app.add_api_route("/ask", handler, methods=["GET"])` — programmatic registration without any `@` decorator syntax. This is the documented, supported API. The handler functions are plain `def`/`async def`, registered in the `Run()` dispatch of the `GhostAPI` class.
- Pattern: `GhostAPI.Run("start", params)` calls `_RegisterRoutes()` which loops over a `ROUTES` dict and calls `app.add_api_route()` for each. The route table lives in `Config` (not hardcoded — per `@hardcode`).

### A3 — SQLite methods table: SQL only or Python too?

**Decision: SQL only. Python logic lives in the VBStyle class methods, not in the methods table.**

Reasoning:
- The existing `code_store_variations/code_store.db` schema (verified via `sqlite3 .schema`) has a `methods` table with columns: `id, class_id, method_name, params, method_code, is_dunder, line_start, created_at`. The `method_code` column stores the full Python source of the method — this is the code-in-database pattern for the code corpus, NOT the config/methods table for Ghost's runtime.
- Ghost's `methods` table (the config one, per `@meth` "methods table schema") is a dispatch registry: `method_name → SQL query` (for DB operations) or `method_name → dispatch_key` (for service calls). It maps dispatch keys to SQL statements, following the DB-manager pattern described in PLAN.md Q3 ("params in, results out, SQL stored in config").
- Python logic (embedding generation, LLM calls, Qdrant upserts) lives in the VBStyle service classes (`MlxService`, `QdrantService`, `MysqlService`) as `Run()` dispatch methods — NOT in SQLite. SQLite stores SQL + metadata; Python stores behavior.
- This matches `@selfdb` ("self documenting db code registry") — the DB is a registry, not an executor.

### A4 — engine.py JSON internally: how to handle?

**Decision: (B) Keep engine.py as-is, feed it dicts from our BCL/SQLite layer (convert BCL → dict at the boundary).**

Reasoning:
- `gui_engine/engine.py`'s `ConfigWatcher` reads `.json` files. Rewriting it (option A) is a large effort and risks breaking the working GUI engine. Copying and modifying (option C) creates a fork — violates DRY and `@noarch`.
- The no-JSON rule (per `@nofiles` and the VBStyle book) applies to **our storage and config layer** — we store config in BCL/SQLite, not JSON. It does not forbid a third-party component from using JSON internally.
- The boundary pattern: `Config.Run("read", {})` reads BCL from SQLite → returns a Python `dict` → `GhostGUI.Run("start", {"config": config_dict})` passes the dict to engine.py. engine.py receives a dict, never sees JSON files. The JSON → dict conversion happens inside engine.py's existing code, which is its own domain authority (`@auth`).
- This is the same pattern `qa_engine/GhostQAEngine.py` uses: `Config_qa_engine.py` provides `CONFIG_DICT` (a Python dict), and `GhostQAEngine._LoadConfig()` returns `copy.deepcopy(_DEFAULT_CONFIG)`. The engine never reads JSON directly — it gets a dict.

### A5 — no_utility_funcs: shared validation?

**Decision: (B) Nested ValidationAuthority class with its own Run() dispatch.**

Reasoning:
- `obey.md` rule referenced in PLAN.md line 586: `no_utility_funcs` — "NO utility functions. No _ok/_err/_safe helper wrapper functions. Use direct tuple returns only."
- Option (A) "duplicate validation in each branch" violates DRY and makes maintenance error-prone.
- Option (C) "validation in dispatch layer before routing" couples validation to the dispatcher, violating `@domain` ("each class must own exactly one domain") — the dispatcher's domain is routing, not validation.
- Option (B): a `ValidationAuthority` class with `Run(command, params)` dispatch. Commands like `"validate_config"`, `"validate_params"`, `"validate_result"`. Returns Tuple3 `(ok, data, error)`. This is a proper VBStyle class — one domain (validation), one authority, Run() dispatch, Tuple3 returns.
- This matches the efl_brain pattern: `Efi_solution_engine.py` has `GenerateReport()` as a method (not a free function), and `BCL/bcl_validator.py` has `class ValidationReport` and `BCLValidator` as proper classes. Validation is a class, not a bag of helpers.

### A6 — `__main__` block ban: CLI entry point?

**Decision: (A) Separate `main.py` — explicitly NOT a VBStyle unit, just a bootstrap.**

Reasoning:
- `obey.md` does not explicitly ban `if __name__ == "__main__"` — I searched the rules file and found no such rule. However, the VBStyle book and `@noarch` spirit discourages mixing execution with class definitions.
- Evidence: every efl_brain brother has `if __name__ == "__main__":` at the bottom (verified: `Efi_code_graph.py:339`, `Efi_repair.py:475`, `Efi_agent_graph.py:2607`, `Efi_boot_graph.py:684`, `Efi_formal_spec.py:337`, `Efi_brain_db.py:328`, etc.). This is the established pattern in this codebase — `__main__` blocks are used as CLI entry points and are accepted.
- Given this evidence, the pragmatic decision: `__main__` blocks are OK for CLI entry points. They are NOT VBStyle units (no Run() dispatch, no Tuple3) — they are bootstraps that instantiate the class and call `Run()`.
- For the `ghost` CLI: a `ghost/cli/main.py` with `if __name__ == "__main__":` that calls `GhostCLI().Run(sys.argv[1], {})`. Alternatively, `setup.py` `entry_points` pointing to a `main()` function. Both are acceptable. The `__main__` block is the pattern already used across the project.
- Clarification: the "ban" is soft. The real rule is: `__main__` blocks must only bootstrap — no business logic, no class definitions, no dispatch. Just `instance = Class(); instance.Run(cmd, params)`.

### A7 — BCL parser: which source?

**Decision: Use the BCL parser from `BCL/bcl_parser.py` (already built, tested, VBStyle-documented).**

Reasoning:
- `BCL/bcl_parser.py` (line 121: `class BCLParser`) is a complete Stage 2 AST builder with a full pipeline: LEX → PARSE → VALIDATE → FIX → VALIDATE → SERIALIZE. It handles `[@name]{...}` containers, nested `{...}`, tuples, and decision trees.
- The BCL module is marked "Complete — 3 tasks done" (TASK-002, TASK-003, TASK-004 in DevChat_Plan.md task tracker). It has a lexer (`bcl_lexer.py`), parser (`bcl_parser.py`), validator (`bcl_validator.py`), fixer (`bcl_fixer.py`), and engine (`bcl_engine.py`) — 6,639 lines total.
- PLAN.md Q7 mentions two older sources: `ClassBrackets` in `contestsystem/workspace/Core/foundation.py` (75 lines, flat only) and `vbstyle_config.py` (551 lines, not VBStyle-compliant). Both are superseded by `BCL/bcl_parser.py` which was built specifically to be the complete, tested BCL pipeline.
- `BCL/Config_BCL.py` documents the BCL domain inventory. The parser is the authority for BCL parsing.
- Do NOT copy `ClassBrackets` or `vbstyle_config.py` — they are legacy. Import from `BCL/bcl_parser.py` (or wrap it in a VBStyle adapter class if needed for Ghost's domain boundary).

### A8 — Config defaults: dict or BCL in code?

**Decision: (A) Python dicts in config.py, converted to BCL when written to SQLite.**

Reasoning:
- The existing pattern across the codebase is Python dict configs: `qa_engine/Config_qa_engine.py` provides `CONFIG_DICT` (a Python dict), `email_ingestion.py` uses module-level constants (`QDRANT_URL`, `EMBED_DIM`, `MYSQL_SCHEMA`, `IMAP_SERVERS` dict), `efl_brain/Config_efl_brain.py` uses flat constants.
- BCL strings in code (option B) would mean writing `[@name]{("key";"value")}` literals in Python source — unreadable, error-prone, and requires the parser at load time just to read defaults. This adds boot complexity.
- The flow: `config.py` has `DEFAULT_CONFIG = {...}` (Python dict) → on first run, `Config.Run("init", {})` serializes the dict to BCL via `BCL/bcl_engine.py` → writes BCL strings to the SQLite `config` table → subsequent runs read BCL from SQLite → deserialize back to dict.
- This keeps code readable (dicts) and storage VBStyle-compliant (BCL). The conversion happens at the boundary, not in the source.
- `@hardcode` ("no hardcoded NOTHING") is satisfied because the dict values are defaults that get overridden by env vars and SQLite — they are not hardcoded runtime values, they are boot defaults.

### A9 — No-JSON rule: external APIs?

**Decision: (A) Only our storage/config layer. External API parsing is fine.**

Reasoning:
- The no-JSON rule (per `@nofiles`, VBStyle book) applies to **our persistent storage and configuration** — we use BCL/SQLite instead of JSON files. It does not prohibit parsing JSON from external HTTP APIs.
- Qdrant's REST API returns JSON. `msearch` uses `json.loads()`. The `qa_engine/qa_engine_config.json` exists but `GhostQAEngine` loads it via `CONFIG_DICT` (Python dict) — the JSON file is a legacy artifact, not the canonical source.
- Evidence: `email_ingestion.py` (VBStyle-compliant, per TASK-066 done summary) uses `json.loads()` for IMAP responses and Qdrant API responses. `embed_knowledge_base.py` (VBStyle-compliant, per TASK-065) uses Qdrant's HTTP API which returns JSON. Both were accepted as VBStyle-compliant.
- Rule: JSON is OK for external API I/O (Qdrant, MLX server, IMAP). JSON is NOT OK for our config storage (use BCL/SQLite) or internal state serialization (use `self.state` dict / BCL).
- The boundary: external JSON → `json.loads()` → Python dict → passed as `params` to `Run()`. The dict is the internal format; JSON never persists.

### A10 — Ghost header format

**Decision: Use the efl_brain comment-block format (verified in `Efi_repair.py`, `Efi_brain_db.py`, `Efi_agent_graph.py`).**

Reasoning:
- Three formats were noted in PLAN.md Q10. The codebase has converged on a specific format. Verified from `efl_brain/Efi_repair.py` lines 1-19:
  ```
  #!/usr/bin/env python3
  # ============================================================================
  # GHOST HEADER
  # ----------------------------------------------------------------------------
  # File:     <filename>
  # Domain:   <domain>
  # Authority: <description>
  # DB:       <sqlite db and tables>
  #
  # VBSTYLE HEADER
  # ----------------------------------------------------------------------------
  # Rules followed:
  #   @ghost    — Ghost Header present
  #   @vbsty    — VBStyle Header present
  #   @hardcode — No hardcoded paths
  #   @cstyle   — Coding style compliant
  # ============================================================================
  ```
- This is the format used by ALL efl_brain brothers (verified across 10+ files). It is a comment block, not a BCL bracket.
- The BCL bracket format `#[@GHOST]{[@file<...>][@state<...>]}` (seen in `BCL/Config_BCL.py` line 1, `qa_engine/Config_qa_engine.py` line 3) is used for auto-generated config files, not for hand-written VBStyle classes.
- For Ghost core classes: use the efl_brain comment-block format (hand-written, readable, documents DB tables and rules followed). For auto-generated config files: use the BCL bracket format.
- Both satisfy `@ghost` ("all code must have Ghost Header") and `@vbsty` ("all code must have VBStyle Header").

### A11 — Report class needed?

**Decision: Yes — a Report class is useful for structured output.**

Reasoning:
- `obey.md` rule `@print`: "do not use print statements; use Report class or logging". Rule `@rpt`: "report isolation returns strings no print". This makes a Report class effectively mandatory.
- Evidence: `efl_brain/Efi_solution_engine.py` has `GenerateReport()` method (line 559) and a `PrintReport()` function (line 709). `efl_brain/Efi_orchestrator.py` has `_StepReport()` method (line 259). `BCL/bcl_validator.py` has `class ValidationReport` (line 134). The pattern exists but is inconsistent (sometimes a method, sometimes a class, sometimes a free function).
- For Ghost: a proper `Report` class with `Run(command, params)` dispatch. Commands: `"format_cli"` (returns string for CLI output), `"format_api"` (returns dict for API response), `"format_log"` (returns string for logging), `"format_gui"` (returns dict for GUI notification). Returns Tuple3 `(ok, formatted_output, error)`.
- This centralizes output formatting, satisfies `@print` and `@rpt`, and gives CLI/API/GUI a consistent interface. The 11-class seed (Q13) should include `Report` as a 12th class.
- Note: `Report` does NOT replace Tuple3 returns from `Run()`. `Run()` returns `(ok, data, error)`. `Report` formats `data` for display. They are separate concerns.

### A12 — SQLite DB location?

**Decision: Same directory as the module — `ghost/ghost.db` (following the efl_brain.db pattern).**

Reasoning:
- Evidence: `efl_brain/efl_brain.db` lives in the `efl_brain/` module directory (same folder as the `.py` files). `code_store_variations/code_store.db` lives in its module directory. `BookSystem/book.db` and `BookSystem/vbstyle_book_v2.db` live in `BookSystem/`. `qa_engine/qa_test.db` and `qa_engine/pinnacle_harness.db` live in `qa_engine/`. This is the universal pattern in this codebase.
- `~/.ghost/ghost.db` (option A) would hide the DB from the developer and break the "code lives with its data" pattern. `./ghost.db` in the project root (option B) would clutter the root and not scale to multiple modules.
- Decision: `ghost/ghost.db` — in the `ghost/` module directory, next to the Python files. The path is computed via `os.path.join(os.path.dirname(os.path.abspath(__file__)), "ghost.db")` (same pattern as `email_ingestion.py` line 153: `LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_ingestion.log")`).
- Yes, the SQLite DB should be created automatically on first run if it doesn't exist (boot cold). This matches `Efi_brain_db.py` which creates tables on init, and `email_ingestion.py` which creates the MySQL DB and Qdrant collection if missing (per TASK-066 done summary: "boot cold — creates DB+table if missing").
- The path is overridable via env var `GHOST_DB_PATH` (following the `QDRANT_URL = os.environ.get(...)` pattern in `email_ingestion.py` line 85).

### A13 — 11 classes enough?

**Decision: Start with 11, add Report and MemUnit immediately (13 total), add more as needed.**

Reasoning:
- The 11-class seed from PLAN.md: Config, MlxService, QdrantService, MysqlService, SearchService, GhostAPI, GhostCLI, SettingsGUI, CodeStore, BCLParser, GhostQA.
- Missing (mandatory per rules):
  - **MemUnit** — `@memunit` rule makes this mandatory. Added per A1. (12th)
  - **Report** — `@print` and `@rpt` rules make this mandatory. Added per A11. (13th)
- Optional (add later if needed):
  - **Bootstrap/Orchestrator** — the `ghost/cli/main.py` `__main__` block (per A6) handles boot. A full `Orchestrator` class is only needed if the boot sequence becomes complex (multi-stage dependency resolution). efl_brain has `Efi_orchestrator.py` because it has 7 pipeline steps; Ghost's boot is simpler (Config → MemUnit → Services → API/CLI). Defer.
  - **ErrorCapture** — Tuple3 `(ok, data, error)` already handles errors. A dedicated class is only needed if error logging/reporting becomes complex. Defer.
- Final seed: 13 classes. Start with these, add more as the system demands. Do NOT over-architect upfront (`@noarch`).

### A14 — Qdrant memory collection 768-dim?

**Decision: Keep 384-dim for all Ghost collections. Ignore the existing 768-dim `memory` collection.**

Reasoning:
- Verified Qdrant collections (via `curl http://localhost:6333/collections`): 17 collections exist. The `chat_history` collection is 384-dim (verified: `config.params.size = 384`, 2560 points). All collections built by this project use 384-dim BGE-small-en-v1.5: `chat_history`, `knowledge_base` (per TASK-065: "384-dim BGE-small-en-v1.5, cosine"), `email_store` (per TASK-066: "384-dim, Cosine"), `qa_test_chat`, `pinnacle_test`.
- The `memory` collection (768-dim) was likely created by an earlier experiment or a different embedding model (possibly `all-MiniLM-L12-v2` is 384-dim too, so 768-dim might be from a larger model like `bge-base-en` or `all-mpnet-base-v2`). It is not part of the current Ghost stack.
- BGE-small-en-v1.5 (the project's embedding model, per `qa_engine_config.json` and `email_ingestion.py` line 87) produces 384-dim vectors. Mixing dimensions would require separate Qdrant collections and separate embedding models — adds complexity for no benefit.
- Decision: all Ghost Qdrant collections use 384-dim BGE-small-en-v1.5 with Cosine distance. The `memory` collection is left as-is (legacy) and not used by Ghost. If Ghost needs a memory collection, it creates `ghost_memory` (384-dim) — do NOT reuse the 768-dim `memory` collection.
- This ensures consistency: one embedding model, one dimension, one distance metric across all Ghost collections. Simplifies config (`EMBED_DIM = 384` is already the constant in `email_ingestion.py` line 88).
