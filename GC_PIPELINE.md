# [@clean:MARK_FILE]{[@reason<moved_to_pipeline_folder>][@session<f1c530fe>][@agent<devin>][@date<2026-06-29>][@replaced_by<core/Piplines/PIPELINE_BCL_CODE_LIFECYCLE.md>]}

# BCL Code Lifecycle — The Cycle

> **MOVED:** This file has been moved to `core/Piplines/PIPELINE_BCL_CODE_LIFECYCLE.md`.
> The content below is the original (preserved for history). The new file includes
> the full session conversation, the `gc_delete` command design, and verified DB state.
>
> **Status:** Design (replaces the earlier dumpster proposal)
> **Date:** 2026-06-28
> **Author:** wws + Devin
> **Domain:** `Dom_Unified` / `Dom_Bcl`
> **Depends on:** BCL Code Graph Pipeline (existing), DomReuse (existing), UnifiedAst (existing), MySQL `vb_code_test`

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

---

## 2. What Already Exists (don't rebuild this)

### BCL Code Graph Pipeline (`core/Dom_Bcl/`, `core/Piplines/BCL_CODE_GRAPH_PIPELINE.md`)

10-stage pipeline that ingests `.py` files into MySQL `vb_code_test`:
- **655 methods, 63 classes, 4,147 edges** already ingested
- Every method has: BCL identity token, features (has_print, returns_tuple3, etc.), IR, source code, graph edges (calls, inherits, contains)
- Tables: `bcl_files`, `bcl_classes`, `bcl_methods`, `bcl_edges`, `bcl_units`, `bcl_stamps`

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

### 4.2 No new dumpster table

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

**Not a new utility class.** Extend `DomReuse` with three new commands:

| Command | What it does | Status |
|---|---|---|
| `retire_sweep` | Find `[@clean]` marks, update DB status, remove from file | NEW |
| `sync` | Detect changed methods, create new versions in DB | NEW |
| `recover` | Restore retired/superseded method from DB to file | NEW |

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

# PURGE: archive dead units (weight-based GC)
ok, data, err = dr.Run("purge", {"threshold": -5})
```

---

## 7. The Graph Engine — Walking the Code

You mentioned: "using a graph system, a graph engine, you can go around it and see how it works."

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
| `rm` on `[@clean:MARK_FILE]`-tagged file | Block | **Allow** — DB already has the content |
| `rm` on untagged file | Block | Block (unchanged) |
| `purge` (weight-based archival) | N/A | **Allow** — soft archive, status change only |
| Hard delete of DB rows | N/A | **Block** — requires explicit approval |

---

## 9. Implementation Order

1. **Schema migration** — `ALTER TABLE bcl_methods` and `bcl_classes` to add `status`, `version`, `retired_at`, `retire_reason`, `recovered_at`, `recover_count`, `superseded_by` columns
2. **`retire_sweep` command** in DomReuse — find `[@clean]` marks, update DB, remove from files
3. **`sync` command** in DomReuse — detect changed methods, create new versions
4. **`recover` command** in DomReuse — restore retired methods from DB to files
5. **Hook reconfiguration** — tiered safety model
6. **Verify** — VBStyle gate, test on a real file, confirm round-trip (retire → recover)

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

The lifecycle approach is **less code, more capability, and uses what you already built.**

---

## 11. Relationship to Existing Systems

| System | Relationship |
|---|---|
| **BCL Code Graph Pipeline** | INGEST stage — code → DB. Already built. |
| **DomReuse** | REUSE + RETIRE + SYNC + RECOVER + WEIGHT + PURGE. Extended, not replaced. |
| **BCL Compiler** | Reverse: BCL IR → code. Complementary to the cycle. |
| **DomSystem** | Manages service lifecycle (MySQL, Neo4j, Qdrant, daemon). The code lifecycle is separate but parallel — same pattern, different domain. |
| **UnifiedAst** | Parses BCL tags. The `[@clean]` mark is just another BCL tag. |
| **MagneticGraph** | Walks the code graph. With `status` column, becomes time-aware. |
| **DomExecutionEngine** | Can trigger `retire_sweep` and `sync` on each tick or session end. |
| **destruction guard hook** | Reconfigured for tiered safety (mark = safe, hard delete = blocked). |
