# Code Ingestion Pipeline

> **Road 11 on the CodeGPS Garmin** — the SQLite Fast Method for code analysis and merging.

## Purpose

Ingest Python source files (`.py`) into a normalized SQLite database, enabling:
- **Code merging** — query method bodies from multiple files, assemble into one unified class
- **Code analysis** — find duplicates, overlaps, call graphs, VBStyle compliance
- **Code search** — SQL queries instead of grep, with structured results
- **Refactoring** — rename tracking, method extraction, class consolidation

This is the pipeline that powers the **SQLite Fast Method** — the approach used to merge `Prj_VBScanner.py` + `config_extractor.py` + `ConfigCascade.py` into one unified class (2026-06-28).

## Pipeline Stages

```
Stage 1: INGEST     — Read .py files → Parse → Store in SQLite
Stage 2: QUERY      — SQL queries to find classes, methods, constants, patterns
Stage 3: ANALYZE    — Identify overlaps, duplicates, unique methods
Stage 4: ASSEMBLE   — Query method bodies → Write merged/output file
Stage 5: VERIFY     — py_compile + VBStyle checks on output
```

### Stage 1: Ingest

**Tool:** `codeingest` (native C, `Cascade_toolStack/bin_tools/codeingest.c`)

**Binary:** `Cascade_toolStack/Built_tools/codeingest`

**Compile:**
```bash
cc -O2 -o codeingest codeingest.c -lsqlite3
```

**Usage:**
```bash
# Single file
./codeingest ConfigCascade.py -o /tmp/work.db --status

# Directory (all .py files)
./codeingest core/Dom_Unified/ -o /tmp/work.db --status

# Query an existing database
./codeingest --query /tmp/work.db "SELECT source_file, class_name FROM classes"

# Print schema
./codeingest --schema
```

**Schema (6 tables):**

| Table | Columns | Purpose |
|---|---|---|
| `source_files` | filename, filepath, content, line_count | Full source text + metadata |
| `classes` | source_file, class_name, methods (CSV), line_start, line_end | Class definitions with method lists |
| `functions` | source_file, func_name, args, line_start, line_end, body, is_method, parent_class | All functions/methods with full body text |
| `constants` | source_file, name, value, line | Module-level UPPERCASE constants |
| `imports` | source_file, module, alias, line | Import statements |
| `regex_patterns` | source_file, var_name, pattern, line | `re.compile()` patterns |

**Parser:** Regex-based (no Python AST needed). Handles:
- `class X:` definitions with method tracking
- `def foo(args):` with body extraction by indentation
- `UPPERCASE = value` module-level constants
- `import X` / `from X import Y` statements
- `re.compile(...)` regex pattern extraction
- Method vs function distinction (inside class context)
- Body extraction by line range with proper indentation tracking

### Stage 2: Query

Once files are ingested, SQL queries replace grep/find:

```sql
-- Find all classes and their method counts
SELECT source_file, class_name,
       LENGTH(methods) - LENGTH(REPLACE(methods, ',', '')) + 1 AS method_count
FROM classes;

-- Find duplicate method names across files
SELECT func_name, GROUP_CONCAT(source_file) as files, COUNT(*) as count
FROM functions GROUP BY func_name HAVING count > 1;

-- Find all methods of a specific class
SELECT func_name, args, line_start, line_end
FROM functions WHERE parent_class = 'ConfigCascade' ORDER BY line_start;

-- Find all regex patterns
SELECT source_file, var_name, pattern FROM regex_patterns;

-- Get a method body for assembly
SELECT body FROM functions
WHERE source_file = 'ConfigCascade' AND func_name = '_cmd_scan';
```

### Stage 3: Analyze

Compare method inventories across source files:

```sql
-- Methods only in file A
SELECT func_name FROM functions WHERE source_file = 'A'
EXCEPT
SELECT func_name FROM functions WHERE source_file = 'B';

-- Methods in both files (overlap)
SELECT func_name FROM functions WHERE source_file = 'A'
INTERSECT
SELECT func_name FROM functions WHERE source_file = 'B';
```

### Stage 4: Assemble

Query method bodies and write the merged file:
1. Query `functions.body` for each method needed
2. Concatenate with proper class structure, headers, dispatch table
3. Write to output `.py` file

### Stage 5: Verify

```bash
python3 -m py_compile output.py     # Syntax check
python3 -W error -m py_compile output.py  # Strict (warnings as errors)
```

## Existing Python Ingestion Tools

The C tool (`codeingest`) is the native version. Python equivalents exist:

| Tool | Location | Schema | Notes |
|---|---|---|---|
| `CodeIngester.py` | workspace root | `code_files`, `code_units`, `code_edges` | Full AST-based, with call graph edges, VBStyle detection |
| `Efi_core.py` | `efl_brain/` | `code_files`, `classes`, `methods`, `units` | AST-based, with unit pattern detection (scan→fix→verify etc.) |
| `codeingest.c` | `Cascade_toolStack/bin_tools/` | 6 tables (see above) | Native C, regex-based, no Python dependency |

## When to Use This Pipeline

- **Merging multiple Python files** into one unified class
- **Auditing a directory** for all classes, methods, constants
- **Finding duplicate code** across files
- **Extracting method bodies** for reassembly
- **Pre-merge analysis** — what's unique vs overlapping
- **Post-merge verification** — did all methods make it in?

## Proven Results

| Task | Files Ingested | Methods Found | Merged Output | Date |
|---|---|---|---|---|
| ConfigCascade merge | 3 (ConfigCascade, Prj_VBScanner, config_extractor) | 39 unique | 1,209 lines, 12 dispatch commands | 2026-06-28 |
| Dom_Graph cleanup | 17 files | 1,480 methods | 205 tests pass | 2026-06-27 |

## Road Color Status

| Stage | Color | Notes |
|---|---|---|
| Ingest | **Green** | C tool compiled, tested, working |
| Query | **Green** | SQL queries validated |
| Analyze | **Green** | Overlap detection working |
| Assemble | **Green** | Method body extraction + file assembly working |
| Verify | **Green** | py_compile + VBStyle checks pass |
