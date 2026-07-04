# [@GHOST]{[@file<PIPELINE_BCL_CODE_LIFECYCLE.md>][@domain<Dom_Bcl>][@role<pipeline_doc>][@auth<wws+cascade>][@date<2026-06-28>][@ver<2.0>][@session<mango-maraca>]}
# [@VBSTYLE]{[@auth<system>][@role<pipeline_doc>][@return<n/a>][@orch<DomReuse>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{BCL Code Lifecycle Pipeline — the cycle: INGEST → REUSE → WEIGHT → RETIRE → SYNC → RECOVER. Code never leaves the DB. Files are cache. The GC pipeline replaces rm: check DB first, then strip, then trash.}
# [@CLASS]{CodeLifecycle}
# [@METHOD]{retire_sweep,sync,recover}
# [@FILEID]{core/Piplines/PIPELINE_BCL_CODE_LIFECYCLE.md}

# BCL Code Lifecycle Pipeline — The Cycle

> **Status:** DESIGN — schema migration and commands not yet implemented
> **Date:** 2026-06-28
> **Author:** wws + Devin (session: mango-maraca)
> **Domain:** `Dom_Unified` / `Dom_Bcl`
> **Depends on:** BCL Code Graph Pipeline (existing, working), DomReuse (existing, working), UnifiedAst (existing), MySQL `vb_code_test`
> **Moved from:** `GC_PIPELINE.md` (project root) → `core/Piplines/PIPELINE_BCL_CODE_LIFECYCLE.md`
> **Replaces:** the earlier dumpster proposal (no separate trash table needed)

---

## 0. Origin — The Conversation That Produced This Design

This pipeline was designed during session `mango-maraca` (2026-06-28). The conversation started when the destruction-guard hook blocked an `rm` command on `service_manager.py`. The user questioned whether the block was valid, then proposed a better approach than blunt deletion.

### User's original idea (verbatim from session):

> "when AI writes code and files and whatever, that a file would be marked for deletion by a tag, you know, like by a BCL inside, and then the garbage collector would see that and would take the file and put it into a trash, trash bin DB... not actually delete it, it would save it somewhere with provenance... a come behind you and clean up"

### User connecting it to the BCL DB (verbatim):

> "we have the db with the bcl, bcl ir, graph, code... these different sections they get tagged and the garbage collector would go through and do sweeps"

### User's refined design — the key insight (verbatim):

> "instead of a dumpster table, we'll use that BCL and BCLIR and code and graph... we put it there and then if it's there... then it's in the BCL table, then essentially it's not lost, it's just kept there... the bigger idea was that AI writes functions, methods, and classes, instead of rewriting them all the time... you search the database, get what you need, copy from there and use it. And if it's not there, then when you're writing code, your utility would find, identify the methods that are not in the database, copy them into the database... like a cycle, like a cycle."

### The rm rule (user's directive, 2026-06-29):

> "the rm command must not be directly run. the gc code should be run. basically the pipeline would be conditional — meaning if the file, the code, the methods, classes etc is in the db (the main db, the one with bcl, bcl ir, graph aspect) then the file would be cleared out of all def, class, and then the gc pipeline code would trash the file in the bin."

### AI assessment of the block (from session):

The block was **valid** (correct per safety rules — `rm` on a file the AI did not just create requires explicit per-action confirmation). But the brain's reasoning was **garbage**:
- Targets included shell tokens (`&&`, `echo`, `DELETED`, `root`) — not file targets
- Learned rules were irrelevant (CSS/UI, evidence channels)
- Known problems were generic exception names (`DeprecationWarning`, `ReferenceError`)

The real problem: the hook is **blunt**. It treats any `rm` as catastrophic because there's no recovery path. The GC pipeline fixes this — if code is in the DB, deletion is safe because recovery is always possible.

---

## 1. The Core Idea

**The database is the source of truth. The files are just a cache.**

Code never gets lost because it never leaves the database. When code is "retired" from a file, it doesn't go to a dumpster — it's already in `bcl_methods` / `bcl_classes` with its BCL identity, IR, source, and graph edges. It just gets a status change: `active → retired`. Still there. Still queryable. Still graphable. Still recoverable.

AI stops writing code from scratch. Instead of rewriting the same method 50 times, the cycle is:

```
     INGEST  ✓  (BCL Code Graph Pipeline — code → DB, already built)
        ↓
     REUSE   ✓  (DomReuse — DB → code, search + retrieve + deliver, already built)
        ↓
     WEIGHT  ✓  (DomReuse — survival scores, purge at -5, already built)
        ↓
     PURGE   ✓  (DomReuse — archives dead units, already built)
        ↓
     RETIRE  ✗  MISSING — [@clean] mark → sweep from file → DB status = retired
        ↓
     SYNC    ✗  MISSING — code changed in file → DB row updated (version++)
        ↓
     RECOVER ✗  MISSING — DB status: retired → active, code restored to file
        ↓
     (back to INGEST / REUSE)
```

It's a **cycle**, not a pipeline. Code flows around it forever.

### The rm replacement flow (the key rule):

```
AI wants to "delete" a file
        ↓
  GC pipeline runs (NOT rm directly)
        ↓
  CONDITIONAL CHECK: Is the file's code in the BCL DB?
  (bcl_methods + bcl_classes + bcl_edges — with BCL identity, IR, graph)
        ↓
   ┌──── YES ────┐         ┌──── NO ────┐
   ↓             ↓         ↓            ↓
  Code is safe  Clear the  BLOCK        Code would
  in DB         file of    (can't       be lost
  → strip all   defs/      delete)      forever
  defs/classes  classes
  → trash the   → then
  file          trash it
```

**The AI never runs `rm` directly.** The GC pipeline runs first, checks the DB, and only if the code is already preserved in the DB does it strip the file and trash it. If the code is NOT in the DB, the delete is blocked because the code would be lost forever.

---

## 2. What Already Exists (don't rebuild this)

### BCL Code Graph Pipeline (`core/Piplines/BCL_CODE_GRAPH_PIPELINE.md`, `core/Dom_Bcl/`)

10-stage pipeline that ingests `.py` files into MySQL `vb_code_test`:
- **655 methods, 63 classes, 4,147 edges** already ingested (verified 2026-06-29)
- Every method has: BCL identity token, features (has_print, returns_tuple3, etc.), IR, source code, graph edges (calls, inherits, contains)
- Tables: `bcl_files`, `bcl_classes`, `bcl_methods`, `bcl_edges`, `bcl_units`, `bcl_stamps`

Pipeline stages (all DONE):
```
.py Files → AST Parse → Extract Classes/Methods/Functions
                ↓
    Computational Units (tightly coupled groups)
                ↓
    BCL Identity Tokens (nametags for every entity)
                ↓
    MySQL vb_code_test (bcl_classes, bcl_methods, bcl_units)
                ↓
    Code Graph (bcl_edges: calls, inherits, contains)
                ↓
    BCL Stamps (reasoning traces linked to methods)
                ↓
    BCL Projection (.bcl view files — derived, not source)
```

Tools built: `ingest_bcl.py`, `bcl_mysql_ingestor.py`, `bcl_extractor.py`, `BclGenerator.py`, `bcl_compiler.py`, `bcl_engine.py`, `bcl_identity_generator.py`, `bcl_projector.py`, `BclStampBuilder.py`, `BclStampStore.py`

### DomReuse (`core/Dom_Unified/DomReuse.py`)

Code retrieval before generation. **"STOP AI FROM WRITING CODE OVER AND OVER."**
- `find` — search by BCL stamp, graph edges, keyword, signature
- `retrieve` — get source code from DB
- `deliver` — copy code into target file
- `test` — compile + VBStyle check
- `fix` — fix broken code, update DB
- `reweight` — survival score (reused +1, fixed -2+1, compliant +5, dead -1/month)
- `strongest` / `weakest` — rank by weight
- `purge` — archive dead units (weight < -5)

Weighting system (the existing garbage collector):

| Event | Weight change |
|---|---|
| Reused | +1 |
| Fixed a bug | -2, then +1 when fixed |
| VBStyle compliant | +5 |
| Has tests | +3 |
| Has BCL | +2 |
| No violations | +2 |
| High complexity | -1 |
| Dead for a month | -1 |
| Duplicated | -3 |
| **Purge threshold** | **-5** → archived |

### BCL Compiler (`core/Dom_Bcl/BCL_COMPILER_PLAN.md`)

Reverse direction: BCL IR → plan → AST → code. Deterministic 5-phase compiler. AI only for unknown verbs.

---

## 3. What's Missing (build this)

### 3.1 RETIRE — `[@clean]` mark → sweep → DB status change

**Mark phase** (AI does this instead of deleting code):

The AI wraps retired code in a triple-quoted string tagged with `[@clean]`. The file stays valid Python. The BCL headers travel inside the string:

```python
# [@clean:MARK]{[@reason<replaced_by_DomSystem_v2>][@session<abc123>][@agent<devin>][@date<2026-06-28>][@bcl_method_id<42>]}
_CLEAN_BCL_ = """
[@GHOST]{[@file<old_service_manager.py>][@domain<Dom_Unified>][@role<deprecated>]}
[@VBSTYLE]{[@auth<cascade>][@role<service_manager>][@return<Tuple3>]}

class ServiceManager:
    def __init__(self):
        self.services = SERVICES
    def is_running(self, name):
        ...
"""
# [@clean:END]
```

Key: the mark includes `@bcl_method_id` — the link to the existing DB row. No separate dumpster needed.

**The `"""` trick is the core insight.** By wrapping retired code in a triple-quoted string assigned to a sentinel variable (`_CLEAN_BCL_ = """..."""`), the file stays valid Python *before* the sweep even runs. This means:
- `py_compile` always passes — even mid-refactor with marks everywhere
- The BCL headers (`[@GHOST]`, `[@VBSTYLE]`, etc.) live *inside* the string, so provenance travels with the code into the DB
- The GC parser is dead simple — it finds string literals containing `[@clean:MARK]`, not arbitrary block balancing
- The AI can unmark by just converting the string back to code (no data has moved yet)

**Sweep phase** (`DomReuse.Run("retire_sweep", {...})` or a new `CodeLifecycle` utility):

1. Walk the codebase, find every `[@clean:MARK]...[@clean:END]` block
2. For each marked block:
   - Extract the `@bcl_method_id` from the mark metadata
   - Extract the content (the retired code + its BCL headers)
   - `UPDATE bcl_methods SET status='retired', retired_at=NOW(), retire_reason=... WHERE id=@bcl_method_id`
   - Mark the method's graph edges as `SUPERSEDED` (not deleted)
   - Remove the `_CLEAN_BCL_ = """..."""` block from the file
3. Return a sweep report

**Result:** the code is gone from the file but still in the DB with `status='retired'`. The graph still shows the edges (marked superseded). Nothing is lost.

### 3.2 SYNC — code changed in file → DB row updated

When code changes in a file (not retired, just modified), the DB should track versions:

1. `DomReuse.Run("sync", {"file_path": "core/Dom_Unified/DomSystem.py"})`
2. For each method in the file:
   - Compute current AST hash
   - Compare to DB `ast_hash` for that method
   - If different: `UPDATE bcl_methods SET status='superseded' WHERE id=current_id`
   - `INSERT INTO bcl_methods (..., status='active', version=old_version+1)` — new row
   - Update graph edges to point to the new method ID
3. Old version kept with `status='superseded'` — recoverable

### 3.3 RECOVER — DB status: retired → active, code restored to file

```python
ok, data, err = dom_reuse.Run("recover", {"method_id": 42})
```

1. `SELECT * FROM bcl_methods WHERE id=42 AND status='retired'`
2. Get the source code from the DB row
3. Write it back to the original file (or a new file if the original no longer exists)
4. `UPDATE bcl_methods SET status='active', recovered_at=NOW() WHERE id=42`
5. Restore graph edges from `SUPERSEDED` back to `ACTIVE`
6. Increment `recover_count`

### 3.4 GC DELETE — the rm replacement (the key rule)

This is the command that replaces `rm` for AI agents:

```python
ok, data, err = dom_reuse.Run("gc_delete", {"file_path": "path/to/file.py"})
```

**Flow:**
1. Parse the file → extract all class names and method names
2. For each class: `SELECT id FROM bcl_classes WHERE class_name=? AND file_path=?`
3. For each method: `SELECT id FROM bcl_methods WHERE method_name=? AND class_name=? AND file_path=?`
4. **CONDITIONAL CHECK:** Are ALL classes and methods in the DB?
   - **YES** → all code is preserved in DB:
     - `UPDATE bcl_methods SET status='retired' WHERE file_path=?`
     - `UPDATE bcl_classes SET status='retired' WHERE file_path=?`
     - Strip the file: remove all `def` and `class` blocks (leave imports/comments)
     - Move the stripped file to trash bin (`.trash/` folder or DB blob)
     - Return `(1, {"retired_methods": N, "retired_classes": M, "trashed_to": path}, None)`
   - **NO** → some code is NOT in the DB, would be lost forever:
     - **BLOCK the delete**
     - Return `(0, None, ("CODE_NOT_IN_DB", "File has N methods not in DB — run ingest first", 0))`
     - List which methods/classes are missing so the AI can ingest them first

**The AI never runs `rm` directly.** This command is the only sanctioned deletion path.

---

## 4. Schema Changes (minimal)

### 4.1 Add `status` column to `bcl_methods` and `bcl_classes`

```sql
ALTER TABLE bcl_methods ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
ALTER TABLE bcl_methods ADD COLUMN version INT NOT NULL DEFAULT 1;
ALTER TABLE bcl_methods ADD COLUMN retired_at DATETIME NULL;
ALTER TABLE bcl_methods ADD COLUMN retire_reason TEXT NULL;
ALTER TABLE bcl_methods ADD COLUMN recovered_at DATETIME NULL;
ALTER TABLE bcl_methods ADD COLUMN recover_count INT NOT NULL DEFAULT 0;
ALTER TABLE bcl_methods ADD COLUMN superseded_by INT NULL;

ALTER TABLE bcl_classes ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
ALTER TABLE bcl_classes ADD COLUMN version INT NOT NULL DEFAULT 1;
ALTER TABLE bcl_classes ADD COLUMN retired_at DATETIME NULL;
ALTER TABLE bcl_classes ADD COLUMN retire_reason TEXT NULL;

ALTER TABLE bcl_edges ADD COLUMN edge_status VARCHAR(20) NOT NULL DEFAULT 'active';
```

Status values: `active` / `retired` / `superseded` / `dead` (purged by weight)

### 4.2 Current DB state (verified 2026-06-29)

```
vb_code_test.bcl_methods: 655 rows, 26 columns (NO status, NO version, NO retired_at)
vb_code_test.bcl_classes: 63 rows
vb_code_test.bcl_edges: 4,147 rows
vb_code_test.bcl_files: 54 rows
vb_code_test.bcl_units: 24 rows
vb_code_test.bcl_stamps: 1 row (basically unused)
```

The schema migration has NOT been run. None of the lifecycle columns exist yet.

### 4.3 No new dumpster table

The existing `bcl_methods` / `bcl_classes` tables ARE the permanent store. A retired method is just a row with `status='retired'`. No separate trash bin.

---

## 5. The `[@clean]` Mark Syntax

### 5.1 Section mark (retire a method or block)

```python
# [@clean:MARK]{[@reason<...>][@session<...>][@agent<...>][@date<...>][@bcl_method_id<42>]}
_CLEAN_BCL_ = """
...retired code with BCL headers inside...
"""
# [@clean:END]
```

The triple-quoted string keeps the file valid Python. The BCL headers inside preserve provenance. The `@bcl_method_id` links to the DB row.

### 5.2 Whole-file mark

```python
# [@clean:MARK_FILE]{[@reason<...>][@session<...>][@bcl_class_id<7>]}
```

Single tag in the file header. The sweep stores the whole file content in the DB (the `bcl_methods` rows for that file get `status='retired'`) and removes the file.

### 5.3 Tag grammar

```
[@clean:MARK]        — begin of a section mark (inside a triple-quoted string)
[@clean:END]         — end of a section mark (comment after the string)
[@clean:MARK_FILE]   — marks an entire file for collection
```

Mark metadata: `@reason`, `@session`, `@agent`, `@date`, `@bcl_method_id` (or `@bcl_class_id` for files), `@replaced_by` (optional)

---

## 6. Where This Lives

**Not a new utility class.** Extend `DomReuse` with four new commands:

| Command | What it does | Status |
|---|---|---|
| `retire_sweep` | Find `[@clean]` marks, update DB status, remove from file | NEW |
| `sync` | Detect changed methods, create new versions in DB | NEW |
| `recover` | Restore retired/superseded method from DB to file | NEW |
| `gc_delete` | The rm replacement — check DB, strip file, trash | NEW |

Existing DomReuse commands that already work:

| Command | What it does | Status |
|---|---|---|
| `find` | Search DB by BCL/graph/keyword | EXISTS |
| `retrieve` | Get source code from DB | EXISTS |
| `deliver` | Copy code to target file | EXISTS |
| `test` | Compile + VBStyle check | EXISTS |
| `fix` | Fix broken code, update DB | EXISTS |
| `reweight` | Update survival score | EXISTS |
| `purge` | Archive dead units (weight < -5) | EXISTS |

The full cycle using DomReuse:

```python
from Dom_Unified import DomReuse
dr = DomReuse()

# REUSE: find a method that does X
ok, data, err = dr.Run("find", {"intent": "parse file and extract classes"})

# RETIRE: mark old code with [@clean], then sweep
ok, data, err = dr.Run("retire_sweep", {"path": "core/Dom_Unified/"})

# SYNC: update DB after code changes
ok, data, err = dr.Run("sync", {"file_path": "core/Dom_Unified/DomSystem.py"})

# RECOVER: bring back a retired method
ok, data, err = dr.Run("recover", {"method_id": 42})

# GC DELETE: the rm replacement — check DB first, then strip + trash
ok, data, err = dr.Run("gc_delete", {"file_path": "core/Dom_Unified/old_file.py"})

# PURGE: archive dead units (weight-based GC)
ok, data, err = dr.Run("purge", {"threshold": -5})
```

---

## 7. The Graph Engine — Walking the Code

This already exists in two forms:

1. **`bcl_edges` table** (4,147 edges) — `calls`, `inherits`, `contains`, `imports`, `depends` with certainty levels. Queryable via SQL.

2. **`MagneticGraph`** (`core/Dom_Unified/MagneticGraph.py`) — graph traversal engine that walks the BCL code graph. Can find paths between methods, detect clusters, identify hotspots.

3. **Neo4j** (managed by DomSystem) — the same edges can be projected into Neo4j for interactive graph traversal.

With the `status` column, the graph becomes **time-aware**:
- `active` edges = current code relationships
- `superseded` edges = old relationships (code was replaced)
- `retired` edges = code was retired but edges preserved for history

You can query: "show me the active graph" vs "show me the full history including retired code" vs "show me what changed since last week."

---

## 8. Hook Integration

The destruction-guard hook should be reconfigured:

| Operation | Current | With lifecycle |
|---|---|---|
| AI deletes code lines directly | Not caught | **Warn** — should use `[@clean]` mark instead |
| `[@clean:MARK]` in file | N/A | **Allow** — always safe, code stays in DB |
| `retire_sweep` | N/A | **Allow** — just updates DB status |
| `gc_delete` on file with all code in DB | Block | **Allow** — DB already has the content |
| `gc_delete` on file with code NOT in DB | Block | **Block** — code would be lost forever |
| `rm` on `[@clean:MARK_FILE]`-tagged file | Block | **Allow** — DB already has the content |
| `rm` on untagged file | Block | **Block** (unchanged) |
| `purge` (weight-based archival) | N/A | **Allow** — soft archive, status change only |
| Hard delete of DB rows | N/A | **Block** — requires explicit approval |

**The key change:** `rm` is never run directly by the AI. The `gc_delete` command is the only sanctioned deletion path, and it checks the DB first.

---

## 9. Implementation Order

1. **Schema migration** — `ALTER TABLE bcl_methods` and `bcl_classes` to add `status`, `version`, `retired_at`, `retire_reason`, `recovered_at`, `recover_count`, `superseded_by` columns
2. **`gc_delete` command** in DomReuse — the rm replacement: check DB, strip file, trash (THIS IS THE PRIORITY — it's what the user asked for)
3. **`retire_sweep` command** in DomReuse — find `[@clean]` marks, update DB, remove from files
4. **`sync` command** in DomReuse — detect changed methods, create new versions
5. **`recover` command** in DomReuse — restore retired methods from DB to files
6. **Hook reconfiguration** — tiered safety model (gc_delete = allow if DB has code, rm = always block for AI)
7. **Verify** — VBStyle gate, test on a real file, confirm round-trip (retire → recover, gc_delete → recover)

---

## 10. Why This Is Better Than the Dumpster

| Dumpster approach (old) | Lifecycle approach (this) |
|---|---|
| New `code_dumpster` table | Uses existing `bcl_methods` with `status` column |
| Separate GC utility | Extends existing `DomReuse` |
| Provenance stored in dumpster row | Provenance already in BCL headers + DB |
| Graph edges lost on retirement | Graph edges marked `SUPERSEDED`, preserved |
| Recovery = query dumpster, re-insert | Recovery = `status: retired → active` |
| No version tracking | `version` column tracks method evolution |
| AI still writes code from scratch | AI searches DB first (DomReuse `find`), copies |
| `rm` is the only deletion path | `gc_delete` checks DB first, `rm` blocked for AI |

The lifecycle approach is **less code, more capability, and uses what you already built.**

---

## 11. Relationship to Existing Systems

| System | Relationship |
|---|---|
| **BCL Code Graph Pipeline** | INGEST stage — code → DB. Already built. 655 methods, 4,147 edges. |
| **DomReuse** | REUSE + RETIRE + SYNC + RECOVER + GC_DELETE + WEIGHT + PURGE. Extended, not replaced. |
| **BCL Compiler** | Reverse: BCL IR → code. Complementary to the cycle. |
| **DomSystem** | Manages service lifecycle (MySQL, Neo4j, Qdrant, daemon). The code lifecycle is separate but parallel — same pattern, different domain. |
| **UnifiedAst** | Parses BCL tags. The `[@clean]` mark is just another BCL tag. |
| **MagneticGraph** | Walks the code graph. With `status` column, becomes time-aware. |
| **DomExecutionEngine** | Can trigger `retire_sweep` and `sync` on each tick or session end. |
| **destruction guard hook** | Reconfigured for tiered safety (gc_delete = safe if DB has code, rm = always blocked for AI). |

---

## 12. Provenance — Session Trail

| Date | Session | What happened |
|---|---|---|
| 2026-06-28 10:56 | mango-maraca | Hook blocked `rm service_manager.py` — user questioned the block |
| 2026-06-28 10:57 | mango-maraca | AI assessed: block valid, brain reasoning garbage (shell tokens counted as targets, irrelevant learned rules) |
| 2026-06-28 11:02 | mango-maraca | User proposed: mark code with BCL tags, GC sweeps, save to trash DB with provenance |
| 2026-06-28 11:08 | mango-maraca | User refined: use `"""` triple-quoted string so file stays valid Python |
| 2026-06-28 11:13 | mango-maraca | AI wrote `GC_PIPELINE.md` at project root |
| 2026-06-28 11:17 | mango-maraca | AI connected it to existing BCL Code Graph Pipeline + DomReuse |
| 2026-06-28 11:22 | mango-maraca | User gave the key insight: DB is source of truth, files are cache, it's a cycle not a dumpster |
| 2026-06-28 11:25 | mango-maraca | AI confirmed DomReuse already has most of the cycle built — only RETIRE/SYNC/RECOVER missing |
| 2026-06-29 | (this session) | Moved `GC_PIPELINE.md` → `core/Piplines/PIPELINE_BCL_CODE_LIFECYCLE.md`, added session conversation, added `gc_delete` command design (the rm replacement), verified DB state (655 methods, no status column yet) |
