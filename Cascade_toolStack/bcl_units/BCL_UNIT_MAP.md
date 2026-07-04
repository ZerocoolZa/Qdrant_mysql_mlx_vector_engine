# BCL Unit Map — Complete Architecture

## Design Principle

Each BCL unit owns its **full pipeline** (retrieve -> parse -> normalize -> output BCL).
No shared transform layers. No paradigm mixing.
Split by **source**, not by method.

---

## Current Units (21 registered, 22 .c files)

### IMPLEMENTED — Full working code (8 files)

| File | Lines | Unit Name | Category | Impl Status | Commands |
|---|---|---|---|---|---|
| `bcl_pb_reader.c` | 667 | pb_reader | chat | IMPLEMENTED | scan, load-all, search, stats, read_state, set_config |
| `bcl_msearch.c` | 1213 | msearch | search | IMPLEMENTED | search, count, where, stats, search_files, search_schema, search_all_db, search_all_mysql, hybrid, read_state, set_config |
| `bcl_msearch_qdrant.c` | 647 | msearch_qdrant | search | IMPLEMENTED | semantic, multi, full, qstats, read_state, set_config |
| `bcl_msearch_magnetic.c` | 667 | msearch_magnetic | search | IMPLEMENTED | magnetic, read_state, set_config |
| `bcl_msearch_registry.c` | 380 | msearch_registry | search | IMPLEMENTED | discover_schema, detect_route, load_registry, read_state, set_config |
| `bcl_msearch_ranking.c` | 455 | msearch_ranking | search | IMPLEMENTED | score, understandings, where_to_store, read_state, set_config |
| `bcl_msearch_help.c` | 158 | msearch_help | search | IMPLEMENTED | help, rules, usage, read_state, set_config |
| `bcl_tool_main.c` | 322 | (entry point) | infra | IMPLEMENTED | list, dispatch, CLI entry |

### SHELL — Stub only, needs implementation (13 files)

| File | Lines | Unit Name | Category | Impl Status | Commands implemented | Commands needed |
|---|---|---|---|---|---|---|
| `bcl_chat_ingest.c` | 57 | chat_ingest | chat | SHELL | read_state, set_config | ingest, schema, summary, list_files |
| `bcl_cleaner.c` | 43 | cleaner | clean | SHELL | read_state, set_config | scan, clean, purge, report |
| `bcl_ghostctl.c` | 43 | ghostctl | clean | SHELL | read_state, set_config | scan, purge, control, report |
| `bcl_mdmerge.c` | 43 | mdmerge | build | SHELL | read_state, set_config | merge, list, preview, config |
| `bcl_wcmd.c` | 43 | wcmd | build | SHELL | read_state, set_config | execute, list, validate |
| `bcl_windir.c` | 43 | windir | build | SHELL | read_state, set_config | create, list, tree, move |
| `bcl_discovery.c` | 43 | discovery | graph | SHELL | read_state, set_config | discover, analyze, graph, report |
| `bcl_codeingest.c` | 43 | codeingest | graph | SHELL | read_state, set_config | ingest, parse, index, query |
| `bcl_schemalint.c` | 43 | schemalint | config | SHELL | read_state, set_config | lint, check, report, fix |
| `bcl_vbcheck.c` | 43 | vbcheck | config | SHELL | read_state, set_config | check, report, fix, config |
| `bcl_smartcli.c` | 43 | smartcli | config | SHELL | read_state, set_config | execute, validate, learn, config |
| `bcl_cognitive_core.c` | 43 | cognitive | config | SHELL | read_state, set_config | think, reason, learn, recall |
| `bcl_error_fix.c` | 43 | error_fix | config | SHELL | read_state, set_config | train, fix, learn, report |
| `bcl_magnetic.c` | 43 | magnetic | search | SHELL | read_state, set_config | (duplicate of msearch_magnetic — DELETE) |

### Infrastructure (not registered as units)

| File | Purpose |
|---|---|
| `bcl_tool_main.c` | Entry point — registers all units, CLI dispatch |
| `bcl_toolstack.h` | Shared header — declares all unit functions |
| `Makefile` | Build system — compiles all units into `bcl_tool` |

### Summary

| Status | Count | Lines |
|---|---|---|
| IMPLEMENTED | 8 files | 4,909 lines |
| SHELL | 13 files | 559 lines |
| TOTAL | 21 files | 5,125 lines |

---

## Problem: msearch Family is Too Large

`bcl_msearch.c` has grown into a monolith. It contains:
- MySQL keyword search (its original purpose)
- Filesystem search (`search_files` — no MySQL needed)
- Schema-aware database search (`search_schema`, `search_all_db`, `search_all_mysql`)
- Hybrid search (`hybrid` — MySQL + Qdrant)
- Count, stats, where utilities

The first tree mixed three paradigms in one hierarchy:
1. Storage domains (MySQL, filesystem, vector DB)
2. Retrieval methods (search, scan, query, fetch)
3. Transformation layers (parse, rank, normalize, chunk)

The fix: split by **source**, each unit owns its full pipeline.

---

## Proposed Search Architecture (source-based)

```
SEARCH
|
|-- bcl_search_web.c        -- URL fetch + HTML parse + text extract
|-- bcl_search_fs.c         -- dir walk + ext filter + content grep + time filter
|-- bcl_search_db.c         -- MySQL schema discovery + query + row normalize
|-- bcl_search_vector.c     -- Qdrant embed + search + result normalize
|-- bcl_search_composite.c  -- hybrid + magnetic (coordinates across sources)
|-- bcl_search_registry.c   -- routing: which source for which query
|-- bcl_search_ranking.c    -- scoring across sources
+-- bcl_search_help.c       -- AI rules
```

8 units. Each owns its full pipeline. No paradigm mixing.

### bcl_search_web.c (NEW)
Source: online URLs and web documents.
Pipeline: URL input -> HTTP fetch -> HTML parse -> boilerplate strip -> text extract -> BCL output.
Commands:
  - fetch       -- fetch single URL, return text content
  - search_web  -- search online docs (if API available)
  - read_url    -- fetch and parse to BCL packet
No MySQL dependency. Pure HTTP + parse.

### bcl_search_fs.c (NEW)
Source: local filesystem.
Pipeline: dir walk -> ext filter -> time filter -> content grep -> line extract -> BCL output.
Commands:
  - search_files    -- recursive dir walk, ext + content + time filters
  - search_folders  -- list directories, tree view
  - search_code     -- AST-aware code search (functions, classes, imports)
No MySQL dependency. Pure filesystem + text scan.
Owns: inode metadata, binary vs text classification, .gitignore-style exclude rules.

### bcl_search_db.c (NEW — absorbs bcl_msearch.c)
Source: MySQL databases.
Pipeline: schema discovery -> column detection -> query build -> execute -> row normalize -> BCL output.
Commands:
  - search           -- keyword across known tables (from current bcl_msearch.c)
  - count            -- count matches per table
  - where            -- table discovery
  - stats            -- database statistics
  - search_schema    -- schema-aware column search
  - search_all_db    -- cross-database (vb_shared + CODEBASE)
  - search_all_mysql -- auto-discover all MySQL databases
Owns: schema registry, column type detection, query cost awareness, row-to-BCL normalization.
Also owns: `build_match` utility (mode-aware WHERE clause builder), `escape_like`, `truncate_text`.

### bcl_search_vector.c (RENAMED from bcl_msearch_qdrant.c)
Source: Qdrant vector database.
Pipeline: text input -> embed -> vector search -> result fetch -> normalize -> BCL output.
Commands:
  - semantic  -- vector similarity search
  - multi     -- multi-dimension search
  - full      -- 12-section semantic object search
  - qstats    -- Qdrant collection stats
  - hybrid    -- MySQL + Qdrant combined (moved from bcl_msearch.c)
Owns: embedding call, Qdrant API, result scoring, fusion model.

### bcl_search_composite.c (RENAMED from bcl_msearch_magnetic.c)
Coordinates across multiple sources via Run() calls to other units.
Pipeline: query -> route to sources -> collect results -> merge -> rank -> BCL output.
Commands:
  - magnetic  -- context reconstruction with radius expansion
  - hybrid    -- (alternative entry point, delegates to vector unit)
Owns: cross-source orchestration, result merging, dedup.

### bcl_search_registry.c (RENAMED from bcl_msearch_registry.c)
Routing layer: determines which source handles which query.
Commands:
  - discover_schema  -- schema discovery for a database
  - detect_route     -- keyword pattern -> source routing
  - load_registry    -- load table_registry metadata
Owns: routing rules, schema metadata, table type classification.

### bcl_search_ranking.c (RENAMED from bcl_msearch_ranking.c)
Scoring layer: ranks results across sources.
Commands:
  - score          -- score table relevance
  - understandings -- fetch class understandings
  - where_to_store -- suggest storage location
Owns: relevance scoring, context boost, sort by relevance.

### bcl_search_help.c (RENAMED from bcl_msearch_help.c)
AI guidance and usage rules.
Commands:
  - help   -- full help text
  - rules  -- AI usage rules (examine all results, reason over all)
  - usage  -- usage examples
Owns: rule text, usage examples, AI behavioral constraints.

---

## Migration Plan

### Phase 1: Extract filesystem search
Move `search_files` function + `search_files` command from `bcl_msearch.c` into new `bcl_search_fs.c`.
Remove `<dirent.h>` and `<sys/stat.h>` from `bcl_msearch.c`.

### Phase 2: Extract all database search into bcl_search_db.c
Move `search`, `count`, `where`, `stats`, `search_schema`, `search_all_db`, `search_all_mysql` commands from `bcl_msearch.c` into new `bcl_search_db.c`.
Move `build_match`, `escape_like`, `escape_sql`, `truncate_text`, `search_one_table`, `count_keyword`, `stats_all`, `discover_tables` functions there too.
`bcl_msearch.c` becomes empty -> delete it.

### Phase 3: Move hybrid to vector unit
Move `hybrid` command from `bcl_msearch.c` into `bcl_search_vector.c` (renamed from `bcl_msearch_qdrant.c`).

### Phase 4: Rename existing units
- `bcl_msearch_qdrant.c`     -> `bcl_search_vector.c`
- `bcl_msearch_magnetic.c`   -> `bcl_search_composite.c`
- `bcl_msearch_registry.c`   -> `bcl_search_registry.c`
- `bcl_msearch_ranking.c`    -> `bcl_search_ranking.c`
- `bcl_msearch_help.c`       -> `bcl_search_help.c`

### Phase 5: Update header + Makefile + main
Update `bcl_toolstack.h` declarations.
Update `Makefile` source list.
Update `bcl_tool_main.c` registration.
Delete `bcl_msearch.c` (empty after extraction).
Delete `bcl_magnetic.c` (duplicate of msearch_magnetic, superseded).

---

## Final Unit Count

After migration: 23 total units (8 search + 15 non-search)

### Search units (8 — replacing 7 msearch units):

```
bcl_search_web.c         -- web/URL search (NEW)
bcl_search_fs.c          -- filesystem search (NEW)
bcl_search_db.c          -- MySQL database search (NEW, absorbs bcl_msearch.c)
bcl_search_vector.c      -- Qdrant vector search (renamed from bcl_msearch_qdrant.c)
bcl_search_composite.c   -- hybrid + magnetic (renamed from bcl_msearch_magnetic.c)
bcl_search_registry.c    -- routing (renamed from bcl_msearch_registry.c)
bcl_search_ranking.c     -- scoring (renamed from bcl_msearch_ranking.c)
bcl_search_help.c        -- AI rules (renamed from bcl_msearch_help.c)
```

### Non-search units (15 — unchanged):

```
bcl_pb_reader.c          -- chat (encrypted .pb reader)
bcl_chat_ingest.c        -- chat (AST code ingester)
bcl_cleaner.c            -- clean (cache cleaner)
bcl_ghostctl.c           -- clean (system cleanup)
bcl_mdmerge.c            -- build (markdown merger)
bcl_wcmd.c               -- build (window commands)
bcl_windir.c             -- build (window directory)
bcl_discovery.c          -- graph (code discovery)
bcl_codeingest.c         -- graph (code ingestion)
bcl_schemalint.c         -- config (schema linter)
bcl_vbcheck.c            -- config (VBStyle checker)
bcl_smartcli.c           -- config (smart CLI)
bcl_cognitive_core.c     -- config (cognitive core)
bcl_error_fix.c          -- config (error fix trainer)
bcl_tool_main.c          -- infrastructure (entry point)
```

### Deleted:

```
bcl_msearch.c            -- absorbed into bcl_search_db.c
bcl_magnetic.c           -- duplicate, superseded by bcl_search_composite.c
```

---

## Complete File Listing (all .c files in bcl_units/)

```
bcl_chat_ingest.c
bcl_cleaner.c
bcl_codeingest.c
bcl_cognitive_core.c
bcl_discovery.c
bcl_error_fix.c
bcl_ghostctl.c
bcl_magnetic.c            -- DELETE (superseded)
bcl_mdmerge.c
bcl_msearch.c             -- DELETE (absorbed into bcl_search_db.c)
bcl_msearch_help.c        -- RENAME to bcl_search_help.c
bcl_msearch_magnetic.c    -- RENAME to bcl_search_composite.c
bcl_msearch_qdrant.c      -- RENAME to bcl_search_vector.c
bcl_msearch_ranking.c     -- RENAME to bcl_search_ranking.c
bcl_msearch_registry.c    -- RENAME to bcl_search_registry.c
bcl_pb_reader.c
bcl_schemalint.c
bcl_smartcli.c
bcl_tool_main.c
bcl_vbcheck.c
bcl_wcmd.c
bcl_windir.c
```

New files to create:
```
bcl_search_web.c          -- NEW
bcl_search_fs.c           -- NEW
bcl_search_db.c           -- NEW (absorbs bcl_msearch.c content)
```
