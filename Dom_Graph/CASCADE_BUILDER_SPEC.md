# Cascade Builder CLI — Spec Plan

## Overview

A self-contained C binary that generates VBStyle source files from embedded templates,
using an in-memory SQLite database as the knowledge base. The AI fills in method
implementations one at a time via BCL markers. Based on the proven `devindocs.c` and
`wcmd.c` architecture.

## Proven Patterns Reused

| Pattern | Source File | What It Proves |
|---|---|---|
| Embedded SQLite `:memory:` | `wcmd.c` line 294, `bcl_mem_unit.c` line 62 | In-memory DB opens on startup, no external files |
| `SEED_SQL[]` C string | `wcmd.c` line 185, `devindocs.c` line 222 | Schema compiled into binary |
| `TPL_SEED[]` struct array | `devindocs.c` line 246 | Template content embedded as C struct array |
| `db_open()` seed function | `wcmd.c` line 292, `devindocs.c` line 725 | Opens DB, runs schema, inserts seed data |
| `cmd_gen()` query+write | `devindocs.c` line 1444 | Queries template by type+name, writes file |
| Build pipeline | `devindocs_build.sh` + `devindocs_gen_header.py` | Python converts files to C headers, cc compiles |
| BCL parser | `core/Dom_Bcl/bcl_parser.py` | Parses `[@SECTION]{...}` markers |
| BCL C parser | `core/Dom_Bcl_C_ver/` | C version of BCL parser |

## Spec Graph — Classes

Each class is a planned C file in the cascade CLI.

| Name | Category | Dispatch | Description |
|---|---|---|---|
| CascadeEngine | META | engine | Main entry point, command dispatch, lifecycle |
| TemplateStore | CRUD | template | Query templates from embedded SQLite, render placeholders |
| MarkerScanner | CRUD | scan | Scan source files for BCL markers, extract section IDs |
| TaskQueue | CRUD | task | Manage pending/done/blocked tasks in SQLite |
| PromptBuilder | TRANSFORM | prompt | Build AI prompts from template + task + dependencies |
| PatchInserter | TRANSFORM | patch | Replace marker body in source file with AI output |
| Validator | INTEGRITY | validate | Check syntax, unresolved markers, duplicate definitions |
| BclParser | UTILITY | bcl | Parse `[@SECTION]{...}` markers from source text |
| PlaceholderFiller | TRANSFORM | fill | Replace `{{Key}}` placeholders in template text |
| BuildPipeline | UTILITY | build | Shell script + Python generator for embedding templates |

## Spec Graph — Edges

| Source | Destination | Edge Type |
|---|---|---|
| CascadeEngine | TemplateStore | calls |
| CascadeEngine | MarkerScanner | calls |
| CascadeEngine | TaskQueue | calls |
| CascadeEngine | PromptBuilder | calls |
| CascadeEngine | PatchInserter | calls |
| CascadeEngine | Validator | calls |
| TemplateStore | PlaceholderFiller | uses |
| MarkerScanner | BclParser | uses |
| PatchInserter | BclParser | uses |
| TaskQueue | MarkerScanner | feeds |
| PromptBuilder | TaskQueue | reads |
| PromptBuilder | TemplateStore | reads |
| PatchInserter | TaskQueue | updates |
| Validator | MarkerScanner | checks |
| BuildPipeline | TemplateStore | generates |

## Spec Graph — Categories

| Category | Color | Meaning |
|---|---|---|
| META | #f9e2af | Engine core, lifecycle, dispatch |
| CRUD | #a6e3a1 | Storage and retrieval operations |
| TRANSFORM | #fab387 | Data transformation (prompts, patches, placeholders) |
| INTEGRITY | #f38ba8 | Validation and verification |
| UTILITY | #89b4fa | Parsers, build tools |

## Database Schema (Embedded SQLite `:memory:`)

### Static Tables (seeded at startup, read-only)

```sql
CREATE TABLE templates (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    language TEXT NOT NULL,
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    rules TEXT,
    version INTEGER DEFAULT 1
);

CREATE TABLE prompts (
    id INTEGER PRIMARY KEY,
    pass TEXT NOT NULL,
    kind TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE rules (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    body TEXT NOT NULL
);

CREATE TABLE languages (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    extension TEXT,
    comment_prefix TEXT,
    marker_format TEXT
);
```

### Dynamic Tables (per-project, read-write)

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marker_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    class_name TEXT,
    method_name TEXT,
    pass TEXT DEFAULT 'implement',
    status TEXT DEFAULT 'pending',
    depends_on TEXT,
    priority INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    content_hash TEXT
);

CREATE TABLE markers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    file_path TEXT NOT NULL,
    marker_id TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    stage TEXT DEFAULT 'pending',
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

## Commands

| Command | Args | What It Does |
|---|---|---|
| `cascade new` | `--name <Name> --domain <Domain> --commands "a,b,c"` | Query template, fill placeholders, write skeleton file, scan markers, populate tasks |
| `cascade next` | (none) | Return next pending task with context (class, method, deps, prompt) |
| `cascade apply` | `<task_id> <patch_file>` | Read patch, locate marker in source, replace body, update task status, validate |
| `cascade status` | (none) | Show task counts: pending, done, blocked, failed |
| `cascade list` | `--file <path>` | List all markers in a file with their stage |
| `cascade templates` | (none) | List all available templates from embedded DB |
| `cascade validate` | `--file <path>` | Check for unresolved markers, syntax errors, duplicate definitions |
| `cascade regenerate` | `<task_id>` | Reset task to pending, clear previous implementation |

## Template Format

Templates use `{{Key}}` placeholders filled at render time:

```c
//@GHOST]{file_path="{{FilePath}}" date="{{Date}}" author="{{Author}}" session_id="{{SessionId}}" context="{{Context}}"}
//@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//@FILEID]{id="{{FileId}}" domain="{{Domain}}" authority="{{Authority}}"}
//@SUMMARY]{summary="{{Summary}}"}
//@CLASS]{class="{{ClassName}}" domain="{{Domain}}" authority="single"}
{{MethodMarkers}}

#include "{{Header}}"

static struct { int initialized; } STATE;

{{MethodBodies}}
```

## BCL Marker Format (in generated files)

After template rendering, each method body contains a BCL marker:

```c
/* [@SECTION]{("id";"{{ClassName}}.Init")("stage";"pending")("deps";"")("returns";"int")} */
int {{ClassName}}_Init(void) {
    return BclResult_Err(bcl_out, out_sz, 50, "not implemented - pending");
}
```

The scanner parses `[@SECTION]{...}` and extracts:
- `id` — unique task identifier (ClassName.Method)
- `stage` — pending | stub | complete
- `deps` — comma-separated task IDs this depends on
- `returns` — return type for prompt context

## Build Pipeline

```
templates/
    c_unit.tpl
    python_module.tpl
    header.tpl
        |
        v
build/gen_templates.py  (reads .tpl files, escapes to C strings)
        |
        v
cascade_templates.h    (static const char TPL_C_UNIT[] = "...";)
        |
        v
cc -O2 -o cascade cascade.c -lsqlite3
        |
        v
cascade (self-contained binary)
```

## Implementation Order

| Step | What | Proven By | Lines (est) |
|---|---|---|---|
| 1 | `SEED_SQL[]` + `db_open()` | wcmd.c line 185-296 | ~80 |
| 2 | `TPL_SEED[]` with one c_unit template | devindocs.c line 246 | ~60 |
| 3 | `PlaceholderFiller` — replace `{{Key}}` with values | string replacement | ~40 |
| 4 | `cascade new` command — render + write file | devindocs.c cmd_gen | ~50 |
| 5 | `BclParser` — extract `[@SECTION]` markers from file | bcl_parser.py exists | ~80 |
| 6 | `MarkerScanner` — scan file, populate tasks table | calls BclParser | ~60 |
| 7 | `cascade next` — query next pending task | SQL query | ~30 |
| 8 | `PromptBuilder` — build prompt from task + template | string assembly | ~50 |
| 9 | `PatchInserter` — replace marker body in file | text replacement | ~60 |
| 10 | `cascade apply` — read patch, insert, update task | calls PatchInserter | ~40 |
| 11 | `Validator` — check unresolved markers | scan for pending stage | ~40 |
| 12 | `cascade status` / `cascade list` / `cascade validate` | SQL queries | ~60 |

Total estimate: ~650 lines of C. One file. One binary.

## What Already Exists (Do Not Rebuild)

| Component | File Path | Status |
|---|---|---|
| Embedded SQLite pattern | `/Users/wws/bin/devindocs.c` | Complete, shipping |
| Build pipeline (tpl to C header) | `/Users/wws/bin/devindocs_build.sh` | Complete, shipping |
| Python escape generator | `/Users/wws/bin/devindocs_gen_header.py` | Complete, shipping |
| BCL parser (Python) | `core/Dom_Bcl/bcl_parser.py` | Complete |
| BCL parser (C) | `core/Dom_Bcl_C_ver/` | Complete |
| VBStyle C unit template | `Cascade_toolStack/bcl_units/bcl_smartcli.c` | Complete, example |
| wcmd.c architecture | `Cascade_toolStack/bin_tools/wcmd.c` | Complete, 2060 lines |
| bcl_mem_unit.c architecture | `core/Dom_Bcl_C_ver/bcl_mem_unit.c` | Complete, 550 lines |

## What Needs To Be Built

Only 4 new functions on top of the devindocs.c pattern:

1. **PlaceholderFiller** — `{{Key}}` replacement (not in devindocs)
2. **MarkerScanner** — BCL `[@SECTION]` extraction (not in devindocs)
3. **TaskQueue** — pending/done/blocked management (not in devindocs)
4. **PatchInserter** — replace marker body in source file (not in devindocs)

Everything else (db_open, SEED_SQL, TPL_SEED, cmd_gen, cmd_templates) already exists in devindocs.c and can be copied directly.

## Risks

| Risk | Mitigation |
|---|---|
| BCL parser in C may not handle all marker formats | Use Python bcl_parser.py via popen() if C parser fails |
| Template placeholder collision with BCL `{}` | Placeholders use `{{}}`, BCL uses `[]{}`, no collision |
| Large templates exceed C string literal limits | Use adjacent string concatenation, no practical limit |
| Multiple projects need separate task state | Per-project SQLite file at `.cascade/state.db` |
| AI output doesn't match marker boundaries | Validator checks for unresolved markers after apply |
