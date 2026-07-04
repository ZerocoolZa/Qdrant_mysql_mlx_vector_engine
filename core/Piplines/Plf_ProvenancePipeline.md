# [@GHOST]{[@file<PROVENANCE_PIPELINE.md>][@domain<Dom_Unified>][@role<pipeline_doc>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}

# Provenance Pipeline — Search → Report → Copy → Track

## Overview

The provenance pipeline is a unified workflow that lets you **search** for files/code, **copy** them to a destination (file, folder, or SQLite), and **track provenance** — a complete record of where every copied file came from.

This replaces 18 fragmented files:
- `msearch.py`, `search_engine.py`, `BgeSearch.py` (search)
- `reporting_engine.py`, `report_engine.py`, `bcl_reporter.py`, `stats_report.py` (reporting)
- `backup_engine.py` x2 (file copying)
- `CodeIngester.py`, `ingest.py` (code ingestion)
- `vbs_code_index.py`, `Rule_Gui.py` (provenance tracking)

All unified into one class: **`DomReport`** in `core/Dom_Unified/DomReport.py`.

---

## Pipeline Stages

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌────────────┐    ┌─────────┐
│  SEARCH │ -> │ REPORT  │ -> │   COPY   │ -> │ PROVENANCE │ -> │ VERIFY  │
└─────────┘    └─────────┘    └──────────┘    └────────────┘    └─────────┘
   find           format         copy to         record           check
   files          results        dest            lineage          hashes
```

### Stage 1: SEARCH

Find files by name pattern, content match, or regex.

```python
from Dom_Unified import DomReport

dr = DomReport()

# Find all .py files containing "class Config"
ok, results, err = dr.Run("search", {
    "path": "/Users/wws/Qdrant_mysql_mlx_vector_engine",
    "pattern": "*.py",
    "content": "class Config"
})
# results["results"] = [{"file": "...", "name": "Config.py", "size": 1234, "relative": "..."}]
```

### Stage 2: REPORT

Generate markdown reports from search results, copy history, or file inventory.

```python
# Report search results as markdown
ok, report, err = dr.Run("report", {
    "type": "search_results",
    "search_results": results["results"]
})

# Report file inventory of a directory
ok, report, err = dr.Run("report", {
    "type": "file_inventory",
    "path": "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph"
})

# Report copy history
ok, report, err = dr.Run("report", {"type": "copy_history"})

# Report provenance chain for a specific file
ok, report, err = dr.Run("report", {
    "type": "provenance_chain",
    "dest": "/tmp/copied/Config.py"
})
```

### Stage 3: COPY

Copy files to one of three destinations:

#### 3a. Copy to a single combined file

```python
ok, data, err = dr.Run("copy_to_file", {
    "sources": ["file1.py", "file2.py", "file3.py"],
    "dest": "/tmp/combined.py",
    "include_header": True
})
# Creates /tmp/combined.py with provenance headers:
#   # SOURCE: /path/to/file1.py
#   # HASH: sha256:abc123...
#   <content>
#   # SOURCE: /path/to/file2.py
#   ...
```

#### 3b. Copy to a folder (preserving structure)

```python
ok, data, err = dr.Run("copy_to_folder", {
    "sources": ["src/Config.py", "src/Engine.py"],
    "dest": "/tmp/copied/",
    "preserve_structure": True,
    "base_path": "src/"
})
# Creates /tmp/copied/Config.py and /tmp/copied/Engine.py
# Provenance recorded in SQLite
```

#### 3c. Copy to SQLite (with full content storage)

```python
ok, data, err = dr.Run("copy_to_sqlite", {
    "sources": ["Config.py", "Engine.py"],
    "db": "/tmp/store.db",
    "include_content": True
})
# Stores file content + metadata in SQLite file_store table
# Provenance recorded in provenance table
```

### Stage 4: PROVENANCE

Query the provenance chain for any file.

```python
# Where did this copied file come from?
ok, chain, err = dr.Run("provenance", {
    "dest": "/tmp/copied/Config.py"
})
# chain["records"] = [{
#   "source_path": "/original/Config.py",
#   "dest_path": "/tmp/copied/Config.py",
#   "source_hash": "abc123...",
#   "dest_hash": "abc123...",
#   "file_size": 1234,
#   "copied_at": "2026-06-27T..."
# }]

# What files were copied from this source?
ok, chain, err = dr.Run("provenance", {
    "source": "/original/Config.py"
})

# List all copy operations
ok, data, err = dr.Run("list_copies", {"limit": 50})
```

### Stage 5: VERIFY

Check that copied files still match their original hashes.

```python
ok, data, err = dr.Run("verify_lineage", {"db": "/tmp/store.db"})
# data = {
#   "total": 10,
#   "verified": 9,
#   "mismatches": [{"dest": "...", "expected": "...", "actual": "..."}],
#   "missing": ["/tmp/copied/deleted.py"],
#   "integrity": "FAIL"
# }
```

---

## SQLite Schema

### provenance table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment ID |
| source_path | TEXT | Original file path |
| dest_path | TEXT | Destination path (or `sqlite:db:table:id`) |
| dest_type | TEXT | `file`, `folder`, or `sqlite` |
| source_hash | TEXT | SHA-256 of source file |
| dest_hash | TEXT | SHA-256 of destination |
| file_size | INTEGER | File size in bytes |
| copied_at | TEXT | ISO timestamp |
| file_store_id | INTEGER | FK to file_store (for SQLite copies) |

### file_store table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment ID |
| source_path | TEXT | Original file path |
| file_name | TEXT | Base file name |
| file_size | INTEGER | File size in bytes |
| source_hash | TEXT | SHA-256 hash |
| content | TEXT | File content (if include_content=True) |
| stored_at | TEXT | ISO timestamp |

---

## Full Pipeline Example

```python
from Dom_Unified import DomReport

dr = DomReport(param={"default_db": "/tmp/my_provenance.db"})

# 1. SEARCH — find all Config.py files
ok, results, err = dr.Run("search", {
    "path": "/Users/wws/Qdrant_mysql_mlx_vector_engine",
    "pattern": "Config*.py"
})
print(f"Found {results['count']} config files")

# 2. REPORT — generate inventory of what we found
ok, report, err = dr.Run("report", {
    "type": "search_results",
    "search_results": results["results"]
})
# report = markdown string

# 3. COPY — copy all config files to a single combined file
sources = [r["file"] for r in results["results"]]
ok, data, err = dr.Run("copy_to_file", {
    "sources": sources,
    "dest": "/tmp/all_configs_combined.py"
})

# 4. PROVENANCE — check where each file came from
ok, chain, err = dr.Run("provenance", {
    "dest": "/tmp/all_configs_combined.py"
})
for record in chain["records"]:
    print(f"  {record['source_path']} -> {record['dest_path']}  hash={record['source_hash'][:8]}")

# 5. VERIFY — check integrity
ok, data, err = dr.Run("verify_lineage")
print(f"Integrity: {data['integrity']}  verified={data['verified']}/{data['total']}")
```

---

## Integration with Dom_Unified

DomReport integrates with the rest of the Dom_Unified package:

| Class | Role |
|-------|------|
| `UnifiedAst` | Parse files before copying (extract classes, methods, violations) |
| `CacheDb` | Cache parsed AST results (avoid re-parsing copied files) |
| `ErrorCapture` | Capture VBStyle violations found during search |
| `DatabaseManager` | Store provenance in MySQL (not just SQLite) |
| `ConfigCascade` | Generate config files for copied code in new locations |
| `DomReport` | Search, copy, track provenance, generate reports |

---

## VBStyle Compliance

- `__init__(self, mem=None, db=None, param=None)` — standard constructor
- `Run(self, command, params=None)` — dispatch entry point
- `self.state` dict — no `self._` attributes
- `_p(self, params, key, default)` — param helper
- `read_state()` — returns `(1, dict(self.state), None)`
- `set_config(params)` — returns `(1, dict(self.state["config"]), None)`
- All methods return `Tuple3`: `(1, data, None)` or `(0, None, (code, desc, 0))`
- No `print()`, no decorators, no hardcoded paths, no tabs
