# VBStyle DB-Driven Fix Pipeline — Granular Method Repair via SQL

> **Core thesis:** The DB is the work queue. 1 method = 1 row = 1 SQL UPDATE.
> Instead of opening files and editing manually, query the DB for violations,
> fix the `method_code` column, then sync back to `.py` files.
>
> "The DB already knows what's broken. Just ask it." — Devin, 2026-06-29

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────┐
│  dom_graph_work.db (the work queue)                         │
│                                                             │
│  methods table:                                             │
│    method_id  method_name  method_code  returns_tuple3      │
│    has_print  has_decorator  has_self_underscore  is_dunder │
│                                                             │
│  classes table:                                             │
│    class_id  class_name  is_vbstyle  has_run_method  ...    │
│                                                             │
│  files table:                                               │
│    file_id  file_name  path  ...                            │
└──────────────────────────────┬──────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
    Stage 1: SCAN         Stage 2: FIX         Stage 3: SYNC
    Query violations      AST transform        DB → .py files
    (SELECT)              + SQL UPDATE         (content-based)
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                        Stage 4: VERIFY
                        py_compile + grep
                        + re-index DB
                               │
                        Stage 5: ARCHIVE
                        Zip *.py → backup.zip
                        Double-verify (zip + DB)
                        Remove .py files
```

---

## Pipeline Stages

### Stage 1: SCAN — Query the DB for violations

**Tool:** `VbStyleFixEngine.py` (Run: `scan`)

**SQL queries:**

```sql
-- Methods missing Tuple3 returns (excluding __init__ which can't return)
SELECT m.method_id, m.method_name, f.file_name, m.start_line, m.end_line, m.method_code
FROM methods m JOIN files f ON m.file_id=f.file_id
WHERE m.returns_tuple3=0 AND m.is_dunder=0
ORDER BY f.file_name, m.start_line;

-- Methods with self._ violations
SELECT m.method_id, m.method_name, f.file_name, m.method_code
FROM methods m JOIN files f ON m.file_id=f.file_id
WHERE m.has_self_underscore=1;

-- Methods with print() calls
SELECT m.method_id, m.method_name, f.file_name, m.method_code
FROM methods m JOIN files f ON m.file_id=f.file_id
WHERE m.has_print=1;

-- Classes not VBStyle
SELECT c.class_name, f.file_name, c.is_vbstyle, c.has_run_method, c.has_tuple3
FROM classes c JOIN files f ON c.file_id=f.file_id
WHERE c.is_vbstyle=0 OR c.has_run_method=0 OR c.has_tuple3=0;
```

**Output:** Violation summary — counts per category, per file.

### Stage 2: FIX — AST transform + SQL UPDATE

**Tool:** `VbStyleFixEngine.py` (Run: `fix_tuple3`, `fix_self_`)

#### Fix 2a: Tuple3 wrapping (AST-based)

For each method with `returns_tuple3=0`:

1. Parse `method_code` with `ast.parse(textwrap.dedent(code))`
2. Walk AST for `ast.Return` nodes
3. For each return that's NOT already a 3-tuple:
   - `return None` → `return (1, None, None)`
   - `return X` → `return (1, X, None)`
   - bare `return` → `return (1, None, None)`
   - Multi-line `return {\n ... \n}` → `return (1, {\n ... \n}, None)`
4. If no return found, append `return (1, None, None)` at end
5. Use `end_lineno` to handle multi-line returns correctly

**Critical:** Parse the method directly (`ast.parse(dedented)`) — NOT wrapped
in a dummy class. Wrapping shifts line numbers by 1, corrupting the fix.

```sql
-- Batch UPDATE (1 method = 1 row = 1 UPDATE)
UPDATE methods SET method_code=?, returns_tuple3=1 WHERE method_id=?;
```

**Special case:** `__init__` methods are exempt — constructors can't
return Tuple3 (Python restriction). Mark them `returns_tuple3=1` to
exclude from future scans:

```sql
UPDATE methods SET returns_tuple3=1 WHERE is_dunder=1 AND returns_tuple3=0;
```

#### Fix 2b: self._ renaming

For each method with `has_self_underscore=1`:

1. Collect all method names starting with `_` (excluding `_p`, `__init__`)
2. Build rename map: `_Get` → `Get`, `_BuildDb` → `BuildDb`, etc.
3. Rename `def _Foo(` → `def Foo(` in method definitions
4. Rename `self._Foo(` → `self.Foo(` in all call sites (across ALL methods in DB)
5. Regex: `re.sub(r'\bself\._' + old[1:] + r'\b', 'self.' + new, code)`

```sql
-- Update the method definition
UPDATE methods SET method_code=?, has_self_underscore=0 WHERE method_id=?;

-- Update call sites in other methods
UPDATE methods SET method_code=? WHERE method_id=?;
```

**False positives:** Some `self._` matches are in string literals (e.g.,
GUI code that checks for `self._` violations). These should be cleared
manually:
```sql
UPDATE methods SET has_self_underscore=0 WHERE method_id IN (false_positive_ids);
```

#### Fix 2c: Update class flags

After all method fixes, flip class-level flags:

```sql
UPDATE classes SET is_vbstyle=1, has_tuple3=1
WHERE class_id IN (
    SELECT DISTINCT c.class_id FROM classes c
    JOIN methods m ON m.class_id=c.class_id
    GROUP BY c.class_id
    HAVING SUM(CASE WHEN m.returns_tuple3=0 AND m.is_dunder=0 THEN 1 ELSE 0 END)=0
       AND SUM(CASE WHEN m.has_print=1 THEN 1 ELSE 0 END)=0
       AND SUM(CASE WHEN m.has_self_underscore=1 THEN 1 ELSE 0 END)=0
);
```

### Stage 3: SYNC — Write fixed method_code back to .py files

**Tool:** `VbStyleFixEngine.py` (Run: `sync`)

**CRITICAL LESSON:** Do NOT use `start_line`/`end_line` from the DB for
line-range replacement. If any headers or lines were added to the file
after indexing, the line numbers are STALE and will corrupt the file.

**Correct approach — content-based find/replace:**

1. For each method in the DB (sorted by `start_line` DESC):
   - Find `def MethodName(` in the file content
   - Find the end of the method block (next `def` at same/lower indent,
     or next `class`, or EOF)
   - Replace the entire block with the fixed `method_code`
2. Process bottom-to-top so earlier positions don't shift
3. Do multiple passes until no changes (handles nested methods)

```python
# Pseudocode for content-based sync
for pass in range(5):
    def_positions = find_all_def_positions(content)
    for i in reversed(range(len(def_positions))):
        method_start = def_positions[i].pos
        method_end = find_next_def_at_same_or_lower_indent(i+1)
        mname = def_positions[i].name
        if mname in fix_map:
            content = content[:method_start] + fix_map[mname] + content[method_end:]
    if no_changes: break
```

### Stage 4: VERIFY — py_compile + grep + re-index

**Tool:** `VbStyleFixEngine.py` (Run: `verify`, `reindex`)

```bash
# 1. py_compile all fixed files
python3 -m py_compile Config.py Dom_Graph_Agent.py ...

# 2. Grep for remaining violations
grep -rn 'print(' *.py          # should be 0 (excluding strings)
grep -rn '@property\|@staticmethod\|@classmethod' *.py  # should be 0
grep -rn 'self\._[^p]' *.py    # should be 0 (excluding strings)

# 3. Re-index DB from fixed files
# Re-scan each .py file, update method_code + violation flags in DB
```

**Verification query:**
```sql
SELECT
  SUM(CASE WHEN returns_tuple3=0 AND is_dunder=0 THEN 1 ELSE 0 END) as no_tuple3,
  SUM(has_print) as has_print,
  SUM(has_decorator) as has_decorator,
  SUM(has_self_underscore) as self_underscore
FROM methods;
-- Expected: all 0

SELECT COUNT(*) FROM classes WHERE is_vbstyle=0;
-- Expected: 0
```

### Stage 5: ARCHIVE — Zip, double-verify, remove .py files

**Tool:** `VbStyleFixEngine.py` (Run: `archive`)

Once all files are verified (Stage 4 passes), the `.py` files are redundant —
the DB is the source of truth. This stage zips them into a backup archive,
double-verifies the zip and DB match, then removes the `.py` files.

**Critical:** This is a destructive step. The zip is the safety net. If the
zip is incomplete or the DB is missing files, DO NOT remove the .py files.

#### Step 5a: Verify DB completeness

```sql
-- Count files in DB
SELECT COUNT(*) FROM files;
-- Count classes in DB
SELECT COUNT(*) FROM classes;
-- Count methods in DB
SELECT COUNT(*) FROM methods;
```

Compare with actual file count on disk:
```bash
ls *.py | wc -l    # should match SELECT COUNT(*) FROM files
```

If counts don't match → STOP. Do not proceed to zip.

#### Step 5b: Zip the .py files

```bash
cd <target_dir>
zip -j <target_dir>_py_backup.zip *.py
```

The zip is stored in the same directory as the DB. Naming convention:
`<dirname>_py_backup_<YYYYMMDD>.zip` (e.g., `chat_mover_py_backup_20260629.zip`).

#### Step 5c: Double-verify (zip + DB)

**Verify 1 — zip contents:**
```bash
unzip -l <backup>.zip | grep '.py' | wc -l
# Should match the number of .py files that were on disk
```

**Verify 2 — DB has all files:**
```sql
SELECT file_name FROM files ORDER BY file_name;
```

**Verify 3 — cross-check: every file in zip exists in DB, and every file
in DB exists in zip.** If any mismatch → STOP. Do not remove .py files.

```python
# Pseudocode for cross-check
zip_files = set(get_zip_contents(backup_zip))
db_files = set(query_db("SELECT file_name FROM files"))
disk_files = set(f for f in os.listdir(".") if f.endswith(".py"))

assert zip_files == db_files == disk_files, "MISMATCH — abort"
# Only if all three match → proceed to remove
```

#### Step 5d: Remove .py files (only if 5c passes)

```bash
cd <target_dir>
rm *.py
```

**Exceptions — do NOT remove:**
- `__init__.py` — Python package marker, needed for imports
- Any file that was NOT ingested into the DB (e.g., new files created after indexing)
- Any file that failed verification in Stage 4

**After removal, the folder should contain:**
- `<dirname>_work.db` — the SQLite DB (source of truth)
- `<dirname>_py_backup_<YYYYMMDD>.zip` — the backup archive
- `__init__.py` — package marker (if it existed before)
- Any non-.py files (`.md`, `.json`, `.sh`, etc.)

**To restore from archive:**
```bash
unzip <dirname>_py_backup_<YYYYMMDD>.zip
# Or re-sync from DB:
python3 VbStyleFixEngine.py sync  # writes .py files from DB
```

#### Step 5e: Verify removal

```bash
# Confirm no .py files remain (except __init__.py)
ls *.py 2>/dev/null  # should be empty or just __init__.py

# Confirm DB still has all files
sqlite3 <dirname>_work.db "SELECT COUNT(*) FROM files"
# Should match the count before removal

# Confirm zip is intact
unzip -t <dirname>_py_backup_<YYYYMMDD>.zip  # -t = test integrity
```

---

## DB Schema (dom_graph_work.db)

### methods table (419 rows)

| Column | Type | Purpose |
|---|---|---|
| `method_id` | INTEGER PK | Unique method ID |
| `class_id` | INTEGER FK | Parent class |
| `file_id` | INTEGER FK | Source file |
| `method_name` | TEXT | Method name |
| `method_code` | TEXT | **Full method source code** |
| `start_line` | INTEGER | Line number in file (may be stale!) |
| `end_line` | INTEGER | End line number |
| `returns_tuple3` | INTEGER | 1 if returns (1, data, None) format |
| `has_print` | INTEGER | 1 if contains print() calls |
| `has_decorator` | INTEGER | 1 if contains @property etc. |
| `has_self_underscore` | INTEGER | 1 if contains self._ (not self._p) |
| `is_dunder` | INTEGER | 1 if __init__ etc. (exempt from Tuple3) |
| `is_vbstyle` | INTEGER | 1 if fully compliant |

### classes table (38 rows)

| Column | Type | Purpose |
|---|---|---|
| `class_id` | INTEGER PK | Unique class ID |
| `file_id` | INTEGER FK | Source file |
| `class_name` | TEXT | Class name |
| `is_vbstyle` | INTEGER | 1 if all methods compliant |
| `has_run_method` | INTEGER | 1 if has Run() dispatch |
| `has_tuple3` | INTEGER | 1 if all methods return Tuple3 |

### files table (170 rows)

| Column | Type | Purpose |
|---|---|---|
| `file_id` | INTEGER PK | Unique file ID |
| `file_name` | TEXT | Filename (e.g., `Config.py`) |
| `path` | TEXT | Full path |

---

## Tool: VbStyleFixEngine.py

**Location:** `Dom_Graph/VbStyleFixEngine.py`

**VBStyle class** with `Run()` dispatch:

| Command | What it does |
|---|---|
| `scan` | Query DB for all violations, return summary |
| `fix_tuple3` | AST-transform + SQL UPDATE all Tuple3 violations |
| `fix_self_` | Rename self._ methods + update call sites |
| `sync` | Write fixed method_code from DB → .py files |
| `reindex` | Re-scan .py files, update DB flags |
| `verify` | py_compile + grep + DB violation count |
| `all` | Run full pipeline: scan → fix → sync → reindex → verify |

**Usage:**
```bash
# Dry run (no DB changes, no file writes)
python3 VbStyleFixEngine.py scan --dry-run
python3 VbStyleFixEngine.py fix_tuple3 --dry-run

# Real run
python3 VbStyleFixEngine.py all

# Single command
python3 VbStyleFixEngine.py fix_tuple3
python3 VbStyleFixEngine.py sync
python3 VbStyleFixEngine.py verify
```

---

## Lessons Learned

### Lesson 1: DB line numbers go stale — use content-based sync, not line-range

**What happened:** After adding `#[@REVIEW]` headers to 161 files (shifting
all line numbers down by 1-2), the DB's `start_line`/`end_line` values
were stale. Using them for line-range replacement (`file_lines[s:e] =
new_code`) corrupted 9 of 17 files — methods were inserted at wrong
positions, breaking syntax.

**Fix:** Use content-based find/replace instead:
- Find each method by its `def Signature(` in the file content
- Find the end of the method block by scanning for the next `def` at
  same or lower indentation
- Replace the entire block
- Process bottom-to-top to avoid position shifts

**Rule:** NEVER trust DB line numbers for file editing if any file has
been modified after indexing. Always re-index before syncing, or use
content-based matching.

### Lesson 2: Parse methods directly, not wrapped in a dummy class

**What happened:** Wrapping method code in `class _Dummy:\n    def foo()...`
before `ast.parse()` shifted all AST line numbers by 1 (the class line).
This caused `ast.get_source_segment()` to return wrong content, and
`node.lineno` to point at the wrong line in the original code.

**Fix:** Parse the method directly:
```python
# WRONG — shifts line numbers
tree = ast.parse("class _Dummy:\n" + textwrap.indent(code, "    "))

# CORRECT — def is valid at module level
tree = ast.parse(textwrap.dedent(code))
```

### Lesson 3: __init__ methods are exempt from Tuple3

**What happened:** 33 `__init__` methods were flagged as `returns_tuple3=0`.
But constructors can't return Tuple3 — Python's `__init__` must return
`None`, and returning a tuple causes `TypeError: __init__() should return
None`.

**Fix:** Mark all dunder methods as exempt:
```sql
UPDATE methods SET returns_tuple3=1 WHERE is_dunder=1;
```

### Lesson 4: Multi-line returns need end_lineno

**What happened:** Methods like `return {\n "id": self.id,\n ...\n}`
broke when using single-line regex — the regex only matched the first
line, producing `return (1, {, None)` with the dict body orphaned.

**Fix:** Use AST `end_lineno` attribute to find the full extent of the
return statement, then wrap the entire block:
```python
start = node.lineno - 1
end = node.end_lineno - 1  # Python 3.8+
# Replace lines[start:end+1] as a unit
```

### Lesson 5: False positives in self._ detection

**What happened:** 3 methods were flagged for `self._` but the matches
were in string literals — GUI code that checks for `self._` violations
in other files (e.g., `"self.state dict, no self._"`).

**Fix:** After regex-based fixing, manually inspect remaining violations.
If `self._` only appears inside string literals or comments, clear the
flag:
```sql
UPDATE methods SET has_self_underscore=0 WHERE method_id IN (...);
```

### Lesson 6: Backup the DB before batch UPDATE

**What happened:** Batch SQL UPDATEs are irreversible. If the AST
transform produces wrong output, the original `method_code` is lost.

**Fix:** Always backup before fixing:
```bash
cp dom_graph_work.db dom_graph_work.bak.$(date +%Y%m%d_%H%M%S).db
```
The backup DB also serves as a reference for content-based sync (the
original method_code can be used to find methods in corrupted files).

### Lesson 7: Triple-verify before removing source files

**What happened:** After the DB is populated and verified, the .py files
are redundant. But removing them is irreversible — if the DB is corrupt
or incomplete, the code is lost.

**Fix:** Triple-verify before any file removal:
1. **Zip first** — `zip -j backup.zip *.py` (the zip is the safety net)
2. **Verify zip** — `unzip -l backup.zip` shows all files
3. **Verify DB** — `SELECT COUNT(*) FROM files` matches file count
4. **Cross-check** — every file in zip ∈ DB, every file in DB ∈ zip
5. **Only then** — `rm *.py` (but keep `__init__.py`)

If ANY mismatch at any step → STOP. Do not remove. Re-ingest or re-zip.

The DB is the source of truth, but the zip is the insurance policy.
Both must agree before the source files are removed.

---

## Proven Results

| Task | Files | Methods Fixed | Violations Before | Violations After | Date |
|---|---|---|---|---|---|
| Dom_Graph VBStyle fix | 17 | 386 | 345 Tuple3 + 13 self._ | 0 | 2026-06-29 |

### Before / After

| Metric | Before | After |
|---|---|---|
| Methods missing Tuple3 | 345 | 0 |
| Methods with self._ | 13 | 0 |
| Methods with print() | 0 | 0 |
| Classes not VBStyle | 38 | 0 |
| Files passing py_compile | 8/17 | 17/17 |

---

## When to Use This Pipeline

- **Batch VBStyle compliance** — fixing Tuple3, self._, print() across many files
- **Post-merge cleanup** — after merging multiple files, fix all violations at once
- **Pre-audit preparation** — get all methods compliant before running ArchValidator
- **Periodic compliance sweep** — re-index DB, scan, fix, sync, verify
- **Any DB-indexed codebase** — if `methods` table exists with `method_code` + violation flags

## Prerequisites

- SQLite DB with `methods`, `classes`, `files` tables (see schema above)
- `method_code` column containing full method source text
- Violation flags: `returns_tuple3`, `has_print`, `has_decorator`, `has_self_underscore`
- Python 3.8+ (for `ast.end_lineno`)
- `VbStyleFixEngine.py` in the same directory as the DB

## Road Color Status

| Stage | Color | Notes |
|---|---|---|
| Scan | **Green** | SQL queries working, violation counts accurate |
| Fix Tuple3 | **Green** | AST transform handles single-line, multi-line, bare returns |
| Fix self._ | **Green** | Rename + call-site update working across files |
| Sync | **Yellow** | Content-based sync works but requires care with stale line numbers |
| Verify | **Green** | py_compile + grep + DB re-index all working |
| Archive | **Green** | Zip + triple-verify + remove .py files (tested on chat_mover) |

---

## Related Pipelines

- [Plf_CodeIngestionPipeline.md](Plf_CodeIngestionPipeline.md) — ingests .py files into SQLite (Stage 1 of this pipeline depends on it)
- [Plf_ErrorCapturePipeline.md](Plf_ErrorCapturePipeline.md) — captures errors as reusable knowledge
- [Plf_PipelineBclCodeLifecycle.md](Plf_PipelineBclCodeLifecycle.md) — BCL code lifecycle (build → verify → ship)
