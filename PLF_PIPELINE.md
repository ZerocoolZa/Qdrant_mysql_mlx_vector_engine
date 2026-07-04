# Code Graph Pipeline — Binding Specification

> **Core thesis:** The database is the editing surface. Python files are an
> export format. The real source of truth is normalized code objects,
> relationships, reasoning stamps, history, and configuration — all queryable,
> all validated, all versioned.

---

## Pipeline Overview

```
 0. SYNC       — file hashes vs DB hashes, flag drift
 1. INGEST     — files → rows (full file + per unit)
 2. GRAPH      — structural edges (CALLS, CONTAINS, IMPORTS)
 3. REASON     — stamps per unit (surface + deep + mine past)
 4. REGRAPH    — semantic edges (DEPENDS_ON, BREAKS, RISKS)
 5. VALIDATE   — queryable checks (VBStyle, dead code, cycles)
 6. PLAN       — proposed changes + impact analysis (nothing modified yet)
 7. REPAIR     — fix violations in DB rows (every change = new version)
 8. CONFIG     — extract knobs from code → Config metadata
 9. EXPORT     — DB → files (from full-file rows, verified)
10. VERIFY     — compile + test + diff (only proceed if green)
11. ARCHIVE    — old files archived, new files become canonical
```

---

## Stage 0: SYNC

Before every pipeline run, compare file hashes to DB hashes.

- File hash matches DB hash → no action
- File hash differs from DB hash → file was edited outside pipeline → flag conflict
- File exists on disk but not in DB → new file, ingest
- File exists in DB but not on disk → deleted, flag

**Output:** drift report. No automatic resolution. User decides:
re-ingest (DB was wrong) or keep DB version (file edit was unauthorized).

---

## Stage 1: INGEST

Read every `.py` file once. Extract:

| Unit type | What it captures |
|---|---|
| FILE | Full source text (stored in `code_files` for round-trip export) |
| CLASS | Class definition, docstring, line range |
| METHOD | Method within a class, source, calls, dispatch keys, return type |
| FUNCTION | Top-level function, source, calls |
| MODULE_CONST | UPPERCASE constants (PORT, HOST, TIMEOUT, etc.) |
| IMPORT | Import block, imported modules |
| MAIN_BLOCK | `if __name__ == "__main__":` block |

**Tables:**
- `code_files` — one row per file, full source text, file hash
- `code_units` — one row per unit (class/method/function/const/import)
- `code_edges` — dependency edges (CALLS, CONTAINS)

**Tool:** `CodeIngester.py` (SQLite for testing, MySQL for production)

**Verified:** Dom_Graph directory → 134 files, 2,649 units, 12,558 edges.

---

## Stage 2: GRAPH

Build the structural graph from `code_edges`.

Edge types:
- `CONTAINS` — class contains method
- `CALLS` — method calls another method
- `IMPORTS` — file imports module (future)
- `INHERITS` — class inherits from class (future)
- `REFERENCES` — method references a constant (future)

**Queries available after this stage:**
```sql
-- What calls what
SELECT from_class, from_method, to_method FROM code_edges WHERE edge_type='CALLS';

-- Who calls RollbackTo
SELECT called_by FROM code_units WHERE method_name='RollbackTo';

-- Dead methods (no callers)
SELECT class_name, method_name FROM code_units
WHERE unit_type='METHOD' AND (called_by IS NULL OR called_by='');

-- Most connected methods (high change impact)
SELECT method_name, LENGTH(calls) as call_count FROM code_units
WHERE unit_type='METHOD' ORDER BY call_count DESC LIMIT 20;
```

No reasoning yet. Pure structure.

---

## Stage 3: REASON (the hard part)

Three sub-stages, ordered by cost:

### 3a. SURFACE STAMP (cheap, automated, always runs)

For every METHOD unit, extract:
- `purpose` — one sentence from docstring or BCL `[@SUMMARY]`
- `signature` — params, return type (already in `code_units`)
- `side_effects` — SQL writes, file writes, state mutations (grep source_text)
- `callers` — from `called_by` column (already populated)
- `confidence` — 0.5 default (surface only, not deeply reasoned)

**Cost:** seconds. No AI reasoning needed. Pure extraction.

### 3b. DEEP STAMP (expensive, on-demand only)

For selected methods (high caller count, about to be modified, user-requested):
- `gotchas` — things that look fine but will bite you
- `failure_cascades` — what breaks downstream when this breaks
- `cross_system_invariants` — constraints spanning multiple files
- `change_impact` — what else breaks if you modify this
- `absences` — what the code deliberately does NOT handle
- `confidence` — calibrated based on tracing depth

**Cost:** 10-15 minutes per method. Requires AI reasoning across files.

**Triggers:**
- PLAN stage requests it (method is about to be modified)
- High caller count (> 5 callers = high change impact)
- Stale surface stamp (hash mismatch)
- User explicitly requests it

### 3c. MINE PAST (cheap, high-value, runs before 3a)

Scan `devin_messages` (32,989 rows), `cascade_chats.messages` (35,118 rows),
`chatgpt_chats.messages` (19,932 rows) for findings about each method:

- "Found a bug in..." → `[@KnownBugs]`
- "This doesn't work because..." → `[@Gotchas]`
- "The fix is..." → `[@FixesApplied]`
- "This is wrong because..." → `[@KnownBugs]`
- "I discovered that..." → `[@Gotchas]`

**Cost:** SQL queries. No AI reasoning. Real scars from real sessions.

**Stamp format:** BCL-native `[@TAG]{...}` syntax (not JSON).

---

## Stage 4: REGRAPH

Now graph the reasoning, not just the structure.

New edge types in `code_edges`:
- `DEPENDS_ON` — method A depends on method B's behavior (not just calls)
- `BREAKS` — changing method A breaks method B
- `RISKS` — method A has a known risk that affects method B
- `CONFLICTS` — method A and method B have contradictory assumptions

These edges are derived from deep stamps, not from code structure.

**Danger zones:** methods with > 3 BREAKS edges are fragile. Mark them.
**Safe paths:** methods with 0 BREAKS edges and high confidence are safe to modify.

---

## Stage 5: VALIDATE

The database becomes the authority. Run hundreds of checks:

| Check | Query |
|---|---|
| Missing Run() | `SELECT * FROM code_units WHERE is_vbstyle=1 AND method_name!='Run' AND parent_class IS NOT NULL AND class_name NOT IN (SELECT class_name FROM code_units WHERE method_name='Run')` |
| Missing Tuple3 | `SELECT * FROM code_units WHERE is_vbstyle=1 AND return_type!='Tuple3' AND unit_type='METHOD'` |
| Dead methods | `SELECT * FROM code_units WHERE unit_type='METHOD' AND (called_by IS NULL OR called_by='')` |
| Circular deps | graph traversal on CALLS edges |
| Missing BCL | `SELECT * FROM code_units WHERE unit_type='METHOD' AND content_hash NOT IN (SELECT content_hash FROM stamps)` |
| Duplicate methods | `SELECT method_name, COUNT(*) FROM code_units WHERE unit_type='METHOD' GROUP BY method_name HAVING COUNT(*)>1` |
| Naming violations | `SELECT * FROM code_units WHERE method_name LIKE '_%' AND unit_type='METHOD'` (self._ prefix) |
| Missing stamps | units with no stamp attached |

Everything is queryable. Everything is fixable.

---

## Stage 6: PLAN (the smartest stage)

Generate a complete list of proposed changes BEFORE modifying anything.

For each violation found in Stage 5:
1. What is the violation?
2. What is the fix?
3. What methods does the fix touch?
4. What methods call the touched methods? (impact radius)
5. What stamps need updating?
6. What is the execution order? (dependencies between fixes)
7. What is the risk level? (low/medium/high)

**Output:** a plan document. Nothing is modified until the whole plan is
validated. This prevents cascading errors during automated refactoring.

---

## Stage 7: REPAIR

The AI fixes violations — not in files, inside the database.

Every change:
1. Creates a new `code_units` row (old row kept, marked as superseded)
2. Updates `code_edges` to reflect new structure
3. Triggers re-reasoning (Stage 3b) for the modified method
4. Triggers re-reasoning for all callers (they may be affected)

**The database is the editing surface.** Renaming a class becomes:
```sql
UPDATE code_units SET class_name='NewName' WHERE class_name='OldName';
-- Then validate, then export
```

---

## Stage 8: CONFIG EXTRACTION

Find every configurable value in the code:

```python
PORT = 8080           → config metadata: {key: PORT, default: 8080, ...}
HOST = "localhost"    → config metadata: {key: HOST, default: "localhost", ...}
cfg["timeout"]        → config metadata: {key: timeout, source: cfg, ...}
```

Move them into a `config_metadata` table:
- key name
- default value
- current value
- allowed range/type
- where it's used (which methods reference it)
- documentation

Now "change the port" is a structured query, not a grep-and-pray operation.

---

## Stage 9: EXPORT

Rebuild files from the database.

**Critical:** export from `code_files.full_source`, NOT from `code_units.source_text`.
Per-unit rows are for querying and reasoning. Full-file rows are for
reconstruction. This preserves imports, comments, blank lines, and everything
between methods.

After export:
- Compare exported file hash to DB file hash
- If they match → round-trip verified
- If they differ → either intentional change (from REPAIR) or round-trip bug

---

## Stage 10: VERIFY

Before replacing anything:
1. `py_compile` every exported file
2. Run existing tests (`test_memunit_event_sourcing.py`, `test_spec_compliance.py`)
3. Compare file hashes (exported vs original)
4. BCL validation (every method has a stamp)
5. Graph validation (no orphan nodes, no broken edges)

Only if ALL checks pass → proceed to ARCHIVE.

If any check fails → halt, report, do not archive.

---

## Stage 11: ARCHIVE

- Old source files → `archive/YYYY-MM-DD/` directory
- New source files (from EXPORT) become canonical
- DB records the archive event (which files, when, why)
- Old files are preserved, never deleted

---

## Database Schema

### `code_files` — full file text for round-trip export
```sql
CREATE TABLE code_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE,
    file_hash TEXT,
    full_source TEXT,
    line_count INTEGER,
    class_count INTEGER,
    method_count INTEGER,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### `code_units` — one row per unit (the table IS the file)
```sql
CREATE TABLE code_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT,
    file_hash TEXT,
    class_name TEXT,
    method_name TEXT,
    unit_type TEXT NOT NULL,  -- FILE|CLASS|METHOD|FUNCTION|MODULE_CONST|IMPORT|MAIN_BLOCK
    source_text TEXT,
    docstring TEXT,
    return_type TEXT,
    dispatch_key TEXT,
    calls TEXT,               -- comma-separated method names this calls
    called_by TEXT,           -- who calls this (reverse edges)
    imports TEXT,
    line_start INTEGER,
    line_end INTEGER,
    parent_class TEXT,
    is_vbstyle INTEGER DEFAULT 0,
    content_hash TEXT,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### `code_edges` — dependency graph
```sql
CREATE TABLE code_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_class TEXT,
    from_method TEXT,
    to_class TEXT,
    to_method TEXT,
    edge_type TEXT NOT NULL,  -- CALLS|IMPORTS|CONTAINS|INHERITS|DECORATES|REFERENCES
    evidence_line INTEGER
);
```

### `stamps` — reasoning attached to code (Stage 3)
```sql
CREATE TABLE stamps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER,           -- FK to code_units.id
    content_hash TEXT,         -- hash of the code when stamped
    stamp_text TEXT,           -- BCL-native [@Stamp]{...} format
    stamp_tier TEXT,           -- SURFACE|DEEP|MINED
    confidence REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    superseded_by INTEGER,     -- FK to stamps.id (append-only supersession)
    FOREIGN KEY (unit_id) REFERENCES code_units(id)
);
```

### `config_metadata` — extracted knobs (Stage 8)
```sql
CREATE TABLE config_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name TEXT,
    default_value TEXT,
    current_value TEXT,
    value_type TEXT,
    allowed_range TEXT,
    used_in_methods TEXT,      -- comma-separated method names
    documentation TEXT,
    source_file TEXT,
    source_line INTEGER
);
```

---

## Current Status

| Stage | Status | Tool |
|---|---|---|
| 0. SYNC | not built | — |
| 1. INGEST | **DONE** | `CodeIngester.py` |
| 2. GRAPH | **DONE** (structural edges populated) | SQL queries |
| 3. REASON | not built | — |
| 4. REGRAPH | not built | — |
| 5. VALIDATE | not built | — |
| 6. PLAN | not built | — |
| 7. REPAIR | not built | — |
| 8. CONFIG | not built | — |
| 9. EXPORT | not built | — |
| 10. VERIFY | not built | — |
| 11. ARCHIVE | not built | — |

**Tested on:** Dom_Graph directory → 134 files, 2,649 units, 12,558 edges.
SQLite for testing. MySQL schema exists for production.
