# ChatMover Refactor Pipeline v1 — by Cascade

> **Principle:** The database becomes the editing surface. Python files become an export format. The real source of truth = normalized code objects + relationships + reasoning + history + configuration.

---

## Pipeline Overview

```
Source Code
     │
     ▼
1. INGEST ──────────→ SQLite: code_units, files, graph_edges
     │
     ▼
2. GRAPH ───────────→ Structural dependency map (who calls what)
     │
     ▼
3. REASON ──────────→ BCL stamp per class/method (purpose, gotchas, failure modes)
     │
     ▼
4. REGRAPH ─────────→ Semantic graph (change impact, danger zones)
     │
     ▼
5. VALIDATE ────────→ violations table (VBStyle, missing Run/Tuple3, dead methods, etc.)
     │
     ▼
6. PLAN ────────────→ Ordered change list with impact analysis. Nothing touched yet.
     │
     ▼
7. REPAIR ──────────→ Fix violations in DB rows. Every change = new version.
     │
     ▼
8. CONFIG EXTRACT ──→ Hardcoded values → config_values table → Config.py
     │
     ▼
9. EXPORT + VERIFY ─→ DB rows → files. Compile, lint, test, hash, BCL validate.
     │
     ▼
10. ARCHIVE ────────→ Old files → archive/. New files become canonical.
```

---

## Database Schema

### `code_units` — one row per class/method/function/import

| Column | Type | Description |
|--------|------|-------------|
| id | INT PK | Auto-increment |
| file_path | TEXT | Absolute path of source file |
| unit_type | TEXT | class / method / function / import |
| class_name | TEXT | Parent class (NULL for top-level) |
| unit_name | TEXT | Name of the unit |
| source_text | TEXT | Full source code of this unit |
| line_start | INT | Starting line in original file |
| line_end | INT | Ending line |
| return_type | TEXT | Tuple3 / None / unknown |
| dispatch_keys | TEXT | Comma-separated Run() command keys |
| calls | TEXT | Comma-separated names this unit calls |
| imports | TEXT | For import rows: imported names |
| decorators | TEXT | Comma-separated decorator names |
| is_vbstyle | INT | 1=pass, 0=violation |
| content_hash | TEXT | SHA-256 of source_text |
| ingested_at | TEXT | Timestamp |

### `files` — one row per ingested file

| Column | Type | Description |
|--------|------|-------------|
| file_path | TEXT UNIQUE | Path |
| line_count | INT | Total lines |
| class_count | INT | Classes in file |
| method_count | INT | Methods in file |
| function_count | INT | Top-level functions |
| import_count | INT | Import statements |
| content_hash | TEXT | SHA-256 of full file |

### `graph_edges` — dependency relationships

| Column | Type | Description |
|--------|------|-------------|
| source_file | TEXT | Origin file |
| source_class | TEXT | Origin class |
| source_unit | TEXT | Origin method/function |
| target_name | TEXT | What it references |
| edge_type | TEXT | calls / imports / contains |

### `bcl_stamps` (step 3) — AI reasoning per unit

| Column | Type | Description |
|--------|------|-------------|
| unit_id | INT FK | References code_units.id |
| purpose | TEXT | What this unit does |
| inputs | TEXT | Expected params |
| outputs | TEXT | Return shape |
| assumptions | TEXT | Preconditions |
| invariants | TEXT | What must hold |
| side_effects | TEXT | Mutations, IO, etc. |
| failure_modes | TEXT | How it breaks |
| dependencies | TEXT | What it relies on |
| confidence | REAL | 0.0–1.0 |
| stamp_hash | TEXT | Hash of stamp content |
| created_at | TEXT | Timestamp |

### `violations` (step 5) — detected issues

| Column | Type | Description |
|--------|------|-------------|
| unit_id | INT FK | References code_units.id |
| violation_type | TEXT | print / decorator / self._ / no_tuple3 / hardcoded / etc. |
| severity | TEXT | error / warning |
| detail | TEXT | Description |
| status | TEXT | open / planned / fixed |

### `config_values` (step 8) — extracted configurable values

| Column | Type | Description |
|--------|------|-------------|
| unit_id | INT FK | Where it was found |
| key | TEXT | Config key (e.g. DB_HOST) |
| value | TEXT | Current value |
| default | TEXT | Default value |
| allowed_range | TEXT | Constraints |
| description | TEXT | What it controls |

---

## Steps in Detail

### Step 1: INGEST

**Input:** `chat_mover/*.py`
**Tool:** `ingest.py` (AST-based parser)
**Output:** `chatmover_code.db` with `code_units`, `files`, `graph_edges`
**Status:** ✅ DONE — 15 files, 288 units, 1,430 edges, 60 violations

What it does:
- Parse every .py file with Python's `ast` module
- Extract classes, methods, functions, imports as separate rows
- Detect Run() dispatch keys from if/elif chains
- Detect return type (Tuple3, None, unknown)
- Extract call graph (what calls what)
- Basic VBStyle check (no print, no decorators, no self._)
- SHA-256 hash every unit for change detection

### Step 2: GRAPH

**Input:** `chatmover_code.db`
**Output:** Dependency map queries + gap analysis

Graph queries:
- Who calls what: `SELECT source_class, source_unit, target_name FROM graph_edges WHERE edge_type='calls'`
- Dead methods: methods never referenced in any calls edge
- Circular deps: recursive CTE on graph_edges
- Import graph: which files depend on which
- **Missing targets:** calls edges where target_name doesn't match any code_units.unit_name → broken references

### Step 3: REASON

**Input:** Every code_units row where unit_type IN ('class', 'method', 'function')
**Process:** AI reads source_text, writes BCL stamp
**Output:** bcl_stamps table populated

Stamp fields per unit:
- Purpose — what this unit does
- Inputs — expected params
- Outputs — return shape
- Assumptions — preconditions
- Invariants — what must hold
- Side effects — mutations, IO, etc.
- Failure modes — how it breaks
- Dependencies — what it relies on
- Confidence — 0.0 to 1.0

### Step 4: REGRAPH

**Input:** graph_edges + bcl_stamps
**Output:** Semantic graph — edges annotated with reasoning

Now you can ask:
- "If I change method X, what breaks?" → follow calls edges + read failure_modes from stamps
- "Which methods are fragile?" → WHERE confidence < 0.7
- "What are the danger zones?" → methods with high failure_modes count + many dependents

### Step 5: VALIDATE

**Input:** code_units + bcl_stamps
**Output:** violations table

Checks:
- print() in source_text → violation
- decorators present → violation
- self._ in method → violation
- return_type != Tuple3 on methods → violation
- missing Run() on class → violation
- missing bcl_stamp → violation
- duplicate method names → violation
- dead methods (no incoming calls edge) → warning
- circular dependencies → error
- hardcoded values (strings, numbers in source) → warning

### Step 6: PLAN

**Input:** violations table
**Output:** Ordered change list with impact analysis

For each violation:
- What to change
- Which rows affected
- What depends on it (from graph_edges)
- Execution order (topological sort)
- Risk level

Nothing is modified until the whole plan is validated.

### Step 7: REPAIR

**Input:** Validated plan
**Process:** Modify source_text in code_units rows
**Every change:** new content_hash, old version archived in code_units_history
**Output:** Clean rows with is_vbstyle=1

### Step 8: CONFIG EXTRACTION

**Input:** All source_text rows
**Process:** Find hardcoded values (strings, numbers, paths, URLs)
**Output:** config_values table + updated source_text rows with placeholders

Config.py becomes the single source of all knobs. Code becomes logic-only.

### Step 9: EXPORT + VERIFY

**Input:** code_units rows (cleaned, repaired)
**Process:** `SELECT source_text FROM code_units WHERE file_path=? ORDER BY line_start` → write file
**Verify:** py_compile, lint, hash compare, BCL validation, graph validation
**Output:** New .py files in chat_mover/

### Step 10: ARCHIVE

**Input:** Old files
**Process:** Move to chat_mover/archive/ with timestamp
**Output:** Clean, modular, VBStyle-compliant chat_mover/

---

## Target File Structure (post-refactor)

| File | Role | Source |
|------|------|--------|
| Config.py | All config (stays) | Existing + extracted values |
| chat_mover.py | Orchestrator (stays) | Existing |
| vscode.py | GUI (stays) | Existing |
| db.py | DB manager (new) | Merged from CascadeIngester + MySQLIngester + Devin_Chat_msql DB code |
| ingest.py | All ingesters (new) | Merged from CascadeIngester + DevinIngester + ChatGPTIngester |
| decrypt.py | Decrypt + parse + export (new) | Merged from decrypt_pb + scan_trajectory + export_md + find_key |

---

## Constraints

- VBStyle: PascalCase classes, Run() dispatch, Tuple3 returns, no decorators, no print, no self._, no hardcoded values
- One class per file (after refactor)
- Config.py holds all configurable values
- Database is source of truth during pipeline
- Files are export format only
- Every change creates a new version (history table)

---

## Current Status

| Step | Status | Result |
|------|--------|--------|
| 1. INGEST | ✅ DONE | 15 files, 288 units, 1,430 edges, 60 violations |
| 2. GRAPH | ✅ DONE | See findings below |
| 3. REASON | ⬜ PENDING | |
| 4. REGRAPH | ⬜ PENDING | |
| 5. VALIDATE | ⬜ PENDING | |
| 6. PLAN | ⬜ PENDING | |
| 7. REPAIR | ⬜ PENDING | |
| 8. CONFIG EXTRACT | ⬜ PENDING | |
| 9. EXPORT + VERIFY | ⬜ PENDING | |
| 10. ARCHIVE | ⬜ PENDING | |
