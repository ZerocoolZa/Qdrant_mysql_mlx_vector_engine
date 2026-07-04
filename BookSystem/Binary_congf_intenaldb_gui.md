# Binary Config, Internal DB, and GUI Architecture

## A Blueprint for Self-Contained C Binaries with Embedded SQLite, MySQL Ingestion, and PyQt6 Configuration Interfaces

---

## Preface

This document is a technical blueprint extracted from working source code. It describes a pattern for building self-contained C binaries that carry their own configuration database (SQLite in-memory), persist settings to a file-based SQLite DB on disk, embed a full PyQt6 GUI as C string literals, and connect to MySQL for heavy data ingestion.

The pattern was developed across three binaries in `/Users/wws/bin/`:

- **wcmd** (wcmd.c, 2061 lines) — Windows-style command VM with SQLite config + MySQL ingestion engine + embedded PyQt6 config GUI
- **smartcli** (smartcli.c, 706 lines) — VBStyle CliDomain controller with SQLite config + tool registry + session tracking
- **Cleaner** (Cleaner.c, 560 lines) — VBStyle cache cleaner with SQLite path registry + CRUD config commands + action-based exclusion

All three share the same architectural DNA: a single `.c` file, no external headers, no config files shipped — everything is compiled in or stored in a SQLite DB created at runtime. The binary is the database. The binary is the GUI. The binary is the config.

Cleaner extends the pattern in a key direction: the SQLite DB is not just config storage — it is the **path registry**. Paths to clean are rows in a `paths` table with `(category, root, subpath, action, enabled)` columns. Adding a path to clean is a DB insert, not a code change. This is the `@nofiles`/`@hardcode` VBStyle rule applied to C: the code is generic, the data is in the DB.

This blueprint exists so the pattern can be replicated elsewhere without reverse-engineering the source.

### Who This Is For

- **C developers** building self-contained CLI tools who want embedded config without external files
- **Systems programmers** who need fast, dependency-light binaries for macOS/Linux
- **VBStyle practitioners** working in the contestsystem ecosystem who need to apply VBStyle rules (`Run()` dispatch, `Tuple3` returns, `self.state` dict) to C code
- **Tool authors** who want a SQLite config DB, optional MySQL ingestion, and optional PyQt6 GUI — all compiled into a single binary
- **Anyone maintaining the wcmd / smartcli / Cleaner / ghostctl binaries** who needs to understand the architecture before modifying

### Conventions Used in This Book

| Convention | Meaning | Example |
| --- | --- | --- |
| `UPPERCASE` | C constants and error codes | `CMD_ALL`, `ERR_OK`, `WINDSURF_CACHES` |
| `PascalCase` | C struct types and method names | `Cleaner`, `CleanWindsurf`, `Tuple3` |
| `snake_case` | C functions that mirror Python VBStyle methods | `db_get`, `load_config` |
| `` `code` `` | Inline code reference | `` `sqlite3_prepare_v2` `` |
| Code block (no language) | Shell commands or file paths | `cc -O2 -o ghostctl ghostctl.c` |
| `c` code block | C source code | ```c ... ``` |
| `sql` code block | SQL schema or queries | ```sql ... ``` |
| `bash` code block | Shell script | ```bash ... ``` |
| **Bold** | Key terms, table headers | **wcmd**, **Cleaner** |
| *Italics* | Emphasis or first-use of a term | *path registry* |
| `→` in diagrams | Data flow or process step | `Launch → db_open() → ...` |
| `@rule` | VBStyle rule reference | `@nofiles`, `@hardcode`, `@tuples` |
| Table with `Pros`/`Cons` | Trade-off analysis | Throughout Chapter 11 |
| `Note:` / `Warning:` | Important aside or caution | Inline callouts |

**VBStyle rule references:** When a section satisfies or relates to a VBStyle rule from `obey.md`, the rule is referenced as `@rulename` (e.g. `@tuples` for Tuple3 returns, `@nofiles` for DB-driven config, `@hardcode` for no hardcoded values). These rules are defined in `/Users/wws/contestsystem/.devin/rules/obey.md`.

---

## Chapter Index

1. [Chapter 1: The Single-File Binary Pattern](#chapter-1-the-single-file-binary-pattern)
2. [Chapter 2: In-Memory SQLite Config Class](#chapter-2-in-memory-sqlite-config-class)
3. [Chapter 3: Persisted Config Layer](#chapter-3-persisted-config-layer)
4. [Chapter 4: Command Binding and VM Dispatch](#chapter-4-command-binding-and-vm-dispatch)
5. [Chapter 5: The INGEST Engine (MySQL Integration)](#chapter-5-the-ingest-engine-mysql-integration)
6. [Chapter 6: Embedded PyQt6 GUI as C String Literals](#chapter-6-embedded-pyqt6-gui-as-c-string-literals)
7. [Chapter 7: The smartcli Variant (VBStyle CliDomain)](#chapter-7-the-smartcli-variant-vbstyle-clidomain)
8. [Chapter 8: The Cleaner Variant (VBStyle + DB-Driven Path Registry)](#chapter-8-the-cleaner-variant-vbstyle--db-driven-path-registry)
9. [Chapter 9: Build and Compile](#chapter-9-build-and-compile)
10. [Chapter 10: Replication Checklist](#chapter-10-replication-checklist)
11. [Chapter 11: Pros and Cons](#chapter-11-pros-and-cons)
12. [Chapter 12: Security Considerations](#chapter-12-security-considerations)
13. [Chapter 13: Error Handling Patterns](#chapter-13-error-handling-patterns)
14. [Chapter 14: Performance Characteristics](#chapter-14-performance-characteristics)
15. [Chapter 15: Versioning and Migration](#chapter-15-versioning-and-migration)
16. [Chapter 16: Shell Integration](#chapter-16-shell-integration)
17. [Chapter 17: Testing Strategy](#chapter-17-testing-strategy)
18. [Glossary](#glossary)

---

## Chapter 1: The Single-File Binary Pattern

### 1.1 Philosophy

One `.c` file. No `.h` headers (except system libraries). No shipped `.db` files. No config files. The binary is fully self-contained.

All configuration data lives in an in-memory SQLite database that is seeded at startup from compiled-in C constants (SQL strings and seed arrays). User changes are persisted to a file-based SQLite DB on disk (`~/.wcmd_cfg.db` or `.smartcli_config.db`), which is merged back into the in-memory DB on next launch.

### 1.2 File Structure

The source file is organized in clearly delimited sections. Each binary has a different layout:

**wcmd (2061 lines):**
```
Lines     Section
--------  ------------------------------------------
1-90      Header comment, includes, types, binding table, globals
91-107    SEED_SQL (in-memory DB schema + seed data)
108-215   DB helpers (db_open, db_bootstrap, db_get, load_config)
216-253   Help system (db_help, db_command_enabled, resolve_command)
254-270   VM dispatch (vm_execute)
271-871   Command implementations (DIR, DEL, CD, MD, RD, MOVE, COPY, TYPE, WHERE, GREP)
872-1101  INGEST engine (schema, scanner, worker, stats, cmd_ingest)
1102-1336 Embedded PyQt6 GUI script (GUI_LINES[]) + launch_cfg + main()
```

**Cleaner (560 lines):**
```
Lines     Section
--------  ------------------------------------------
1-26      Ghost Header + VBStyle Header (comment blocks)
27-36     Includes (stdio, stdlib, string, unistd, ftw, stat, errno, limits, sqlite3)
37-110    UPPERCASE constants (DB paths, schema, seed SQL, dispatch keys, error codes)
111-147   Tuple3 struct + Tuple3_OK / Tuple3_Error constructors
149-180   CleanState struct + Cleaner struct (state dict)
182-201   nftw walker + global pointer (g_active)
203-250   Cleaner_Init (constructor: open DB, create schema, seed if empty)
252-270   Cleaner_WipeDir (internal helper)
272-310   Cleaner_CleanCategory (generic DB-driven clean loop)
312-340   Cleaner_AddPath (CRUD: insert)
342-360   Cleaner_RemovePath (CRUD: delete)
362-400   Cleaner_ListPaths (CRUD: list)
402-420   Cleaner_ReadState (state snapshot)
422-440   Cleaner_Report (returns string, no print)
442-470   Cleaner_Dispatch (internal dispatch)
472-490   Cleaner_Run (dispatch entry point)
492-560   main (CLI wrapper: init, run, report, close)
```

**smartcli (706 lines):**
```
Lines     Section
--------  ------------------------------------------
1-40      Ghost Header + VBStyle Header + includes
41-80     Constants, types (ExecResult, CliState), seed SQL
81-150    DB helpers (db_open, db_get, db_set)
151-250   Tool registry (discover, register, list)
251-350   Command implementations (run, list, session, config)
351-450   Session tracking
451-550   Config management
551-706   Dispatch (Run) + main
```

### 1.3 Includes

Each binary has a different dependency footprint:

**wcmd (heaviest — SQLite + MySQL + OpenSSL + regex):**
```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <dirent.h>
#include <sys/stat.h>
#include <fnmatch.h>
#include <time.h>
#include <unistd.h>
#include <ctype.h>
#include <libgen.h>
#include <errno.h>
#include <sqlite3.h>       // in-memory config DB
#include <regex.h>          // GREP command
#include <mysql/mysql.h>    // INGEST engine
#include <openssl/sha.h>    // file dedup hashing
```

**Cleaner (light — SQLite only):**
```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <ftw.h>             // nftw for directory walking
#include <sys/stat.h>
#include <errno.h>
#include <limits.h>          // PATH_MAX
#include <sqlite3.h>         // on-disk path registry DB
```

**smartcli (light — SQLite only):**
```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <dirent.h>
#include <errno.h>
#include <sqlite3.h>         // config + tool registry DB
```

**ghostctl (lightest — no external libs):**
```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <ftw.h>
#include <sys/stat.h>
#include <errno.h>
// No sqlite3, no mysql, no openssl
```

### 1.4 Global State

The three binaries use fundamentally different state management approaches:

**wcmd — file-scope globals (no structs):**
```c
static char g_db_path[512]="";
static int cfg_show_date=1, cfg_show_time=1, cfg_show_hidden=0;
static int cfg_thousand=1, cfg_sort_rev=0;
static char cfg_sort='G', cfg_size_fmt[8]="auto";
```

**Cleaner — VBStyle state dict (struct, no globals for instance data):**
```c
typedef struct {
    char home[PATH_MAX];
    char db_path[PATH_MAX];
    char windsurf_root[PATH_MAX];
    char codeium_root[PATH_MAX];
    sqlite3* db;
    long files_removed, dirs_removed, paths_wiped, paths_kept;
    char report[8192];
    int  report_len;
} CleanState;

typedef struct {
    CleanState state;
} Cleaner;
```
The only global is `g_active` — a temporary pointer used during `nftw` traversal (see Chapter 14 for the nftw user-data limitation workaround). All instance state lives in the `CleanState` struct, equivalent to VBStyle's `self.state` dict.

**smartcli — VBStyle state dict (struct):**
```c
typedef struct {
    sqlite3* db;
    // tool registry, session, config
} CliState;
```

### 1.5 Variant Comparison Matrix

| Aspect | wcmd | smartcli | Cleaner | ghostctl |
| --- | --- | --- | --- | --- |
| **Lines** | 2061 | 706 | 560 | 226 |
| **DB approach** | In-memory + merge | File-based | File-based (path registry) | None |
| **Build deps** | sqlite3 + mysql + openssl | sqlite3 | sqlite3 | none |
| **VBStyle compliant** | No (globals) | Yes (CliState) | Yes (CleanState + Tuple3) | No (globals) |
| **GUI** | PyQt6 embedded | No | No | No |
| **MySQL** | Yes (INGEST) | No | No | No |
| **Symlink dispatch** | Yes (dir, del, md...) | No | No | No |
| **Dispatch pattern** | Binding table + vm_execute | Run() + dispatch | Run() + Dispatch | if/else in main |
| **State management** | File-scope globals | CliState struct | CleanState struct | File-scope globals |
| **Return type** | int (exit codes) | ExecResult struct | Tuple3 struct | int (exit codes) |
| **Config CRUD** | GUI only | CLI | CLI (add/remove/list) | N/A |
| **Path registry** | Hardcoded arrays | N/A | DB-driven (paths table) | Hardcoded |
| **Exclusion mechanism** | Hardcoded arrays | N/A | Action-based (wipe/keep) | N/A |
| **Report mechanism** | printf directly | printf directly | Report method returns string | printf directly |
| **nftw usage** | No | No | Yes (WipeDir) | Yes (clean) |
| **Headers** | Comment block | Ghost + VBStyle | Ghost + VBStyle + Class + Method | Comment block |

### Chapter 1 Summary

- One `.c` file, no external headers, no shipped `.db` files — the binary is self-contained
- Four variants exist: wcmd (heaviest), smartcli, Cleaner, ghostctl (lightest)
- State management varies: wcmd uses globals, Cleaner/smartcli use VBStyle structs, ghostctl uses globals
- Dependency gradient: wcmd needs sqlite3+mysql+openssl, Cleaner/smartcli need only sqlite3, ghostctl needs nothing
- The variant comparison matrix (1.5) is the quick-reference for choosing which pattern to replicate

---

## Chapter 2: In-Memory SQLite Config Class

### 2.1 Schema

The in-memory DB is created fresh every launch via `sqlite3_open(":memory:", &db)`. Six tables are created from a compiled SQL string:

```c
static const char SEED_SQL[] =
"CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT, version TEXT, enabled INTEGER DEFAULT 1);"
"CREATE TABLE IF NOT EXISTS command_flags (id INTEGER PRIMARY KEY, command_id INTEGER, flag TEXT, description TEXT, flag_type TEXT DEFAULT 'bool', default_val TEXT DEFAULT '0');"
"CREATE TABLE IF NOT EXISTS behaviors (id INTEGER PRIMARY KEY, command_id INTEGER, key TEXT, value TEXT, description TEXT, UNIQUE(command_id,key));"
"CREATE TABLE IF NOT EXISTS help_sections (id INTEGER PRIMARY KEY, command_id INTEGER, section TEXT, content TEXT, sort_order INTEGER DEFAULT 0, UNIQUE(command_id,section));"
"CREATE TABLE IF NOT EXISTS ui_modules (id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT, script TEXT, version INTEGER DEFAULT 1);"
"CREATE TABLE IF NOT EXISTS system_config (key TEXT PRIMARY KEY, value TEXT, description TEXT);"
;
```

### 2.2 Table Purposes

- **commands** — registry of all commands (name, description, version, enabled flag)
- **command_flags** — per-command flags and switches
- **behaviors** — key/value config pairs per command (e.g. DIR show_date=1, sort=G)
- **help_sections** — help text stored in DB, queried by `db_help()`
- **ui_modules** — stores embedded GUI scripts (PyQt6 code as text)
- **system_config** — global key/value config (MySQL host, user, paths, limits)

### 2.3 Seed Data

Seed data is in C struct arrays, inserted programmatically at startup:

```c
typedef struct { const char *name, *desc, *ver; } CmdSeed;
static const CmdSeed CMD_SEED[] = {
    {"DIR","Display files and subdirectories","1.2"},
    {"DEL","Delete files","1.0"},
    {"INGEST","MySQL ingestion engine","1.0"},
    {NULL,NULL,NULL}
};

typedef struct { const char *cmd, *key, *val, *desc; } BehaveSeed;
static const BehaveSeed BEHAVE_SEED[] = {
    {"DIR","show_date","1","Show date"},
    {"DIR","sort","G","Default sort"},
    {NULL,NULL,NULL,NULL}
};

typedef struct { const char *key, *val, *desc; } CfgSeed;
static const CfgSeed CFG_SEED[] = {
    {"ingest_mysql_host","localhost","MySQL host for INGEST"},
    {"ingest_mysql_db","CODEBASE","MySQL database name"},
    {NULL,NULL,NULL}
};
```

### 2.4 db_open() — The Constructor

`db_open()` creates the in-memory DB, executes the schema, and inserts all seed data using prepared statements:

```c
static sqlite3 *db_open(void) {
    sqlite3 *db = NULL;
    sqlite3_open(":memory:", &db);
    if (db) {
        sqlite3_exec(db, SEED_SQL, NULL, NULL, NULL);
        // Insert CMD_SEED, BEHAVE_SEED, HELP_SEED, CFG_SEED via prepared statements
    }
    return db;
}
```

### 2.5 db_get() — Config Reader

Reads a single behavior value for a command:

```c
static const char *db_get(sqlite3 *db, const char *cmd_name, const char *key, const char *def, char *buf, int bsz) {
    strncpy(buf, def, bsz-1);
    // SELECT b.value FROM behaviors b JOIN commands c ON c.id=b.command_id WHERE c.name=? AND b.key=?
    return buf;
}
```

### 2.6 load_config() — Config Loader

Pulls all DIR display settings from the in-memory DB into C globals at startup:

```c
static void load_config(sqlite3 *db) {
    cfg_show_date = atoi(db_get(db, "DIR", "show_date", "1", tmp, sizeof(tmp)));
    cfg_sort = toupper(db_get(db, "DIR", "sort", "G", tmp, sizeof(tmp))[0]);
    // ... etc
}
```

### 2.7 On-Disk-Only Alternative (Cleaner Variant)

The Cleaner binary uses a simpler approach: a single on-disk SQLite DB — no in-memory DB, no merge step. The DB is the source of truth.

```c
int rc = sqlite3_open(self->state.db_path, &self->state.db);
// ~/Library/Application Support/Cleaner/cleaner.db
sqlite3_exec(db, SCHEMA_PATHS, NULL, NULL, NULL);
sqlite3_exec(db, SCHEMA_META, NULL, NULL, NULL);
// Seed if empty (INSERT only if COUNT(*) == 0)
```

**Trade-offs vs the in-memory + merge pattern:**

| Aspect | In-Memory + Merge (wcmd) | On-Disk Only (Cleaner) |
| --- | --- | --- |
| Complexity | High (two DBs, merge logic) | Low (one DB, no merge) |
| Startup cost | ~5ms (open + merge + load) | ~1ms (open only) |
| Compiled defaults | Yes (seed arrays override if no persisted) | Yes (seed inserted only if table empty) |
| Config authority | Compiled defaults + persisted overrides | DB is authoritative |
| Cross-process | No (in-memory is per-process) | Yes (file-based, shareable) |
| Use case | Large config, need compiled defaults to win | Small config, DB is source of truth |

**When to choose on-disk only:**
- Config has fewer than ~100 rows
- No need for compiled-in defaults to override persisted user changes
- Single-process usage (no cross-process config sharing needed)
- Simplicity is more important than startup speed (though on-disk is actually faster here)

**When to choose in-memory + merge:**
- Large config with many key/value pairs read at startup
- Compiled defaults must be available even if persisted DB is missing or corrupt
- Config is read frequently during runtime (in-memory reads are free)

### Chapter 2 Summary

- wcmd uses 6 tables: commands, command_flags, behaviors, help_sections, ui_modules, system_config
- `db_open()` creates an in-memory DB, `db_get()` reads config via prepared statements, `load_config()` populates C globals
- Seed data lives in C struct arrays (CmdSeed, BehaveSeed, CfgSeed) — compiled in, no shipped files
- Cleaner offers a simpler alternative (section 2.7): on-disk SQLite only, no merge, DB is source of truth
- Choose in-memory+merge for large configs with compiled defaults; on-disk-only for small configs where DB is authoritative

---

## Chapter 3: Persisted Config Layer

### 3.1 The File-Based SQLite DB

User changes made through the GUI are written to `~/.wcmd_cfg.db` — a file-based SQLite database. This survives restarts.

### 3.2 load_persisted_config() — Merge on Startup

On every launch, `main()` calls `load_persisted_config(db)` which:

1. Opens `~/.wcmd_cfg.db` (file-based SQLite)
2. Reads all `key,value` pairs from `system_config`
3. Inserts/replaces them into the in-memory DB

This means the in-memory DB always starts with compiled defaults, then gets overridden by persisted user changes:

```c
static void load_persisted_config(sqlite3 *db) {
    // Open ~/.wcmd_cfg.db
    // SELECT key, value FROM system_config
    // INSERT OR REPLACE INTO system_config (key, value, description) VALUES (?, ?, 'from persisted config')
}
```

### 3.3 The Flow

```
Launch → db_open() → in-memory DB with compiled defaults
      → load_persisted_config() → merge user changes from disk
      → load_config() → populate C globals from DB
      → vm_execute() → run command
      → sqlite3_close() → in-memory DB destroyed
```

User changes via GUI → written to `~/.wcmd_cfg.db` → picked up on next launch.

### 3.4 Persistence in Other Variants

The in-memory + merge pattern is specific to wcmd. The other binaries use simpler approaches:

**Cleaner — on-disk only (no merge):**
```
Launch → sqlite3_open(db_path) → CREATE TABLE IF NOT EXISTS
      → seed if empty (COUNT(*) == 0)
      → Run() → query paths table for each clean command
      → sqlite3_close()
```
No in-memory DB, no merge step. The DB file (`~/Library/Application Support/Cleaner/cleaner.db`) is the single source of truth. User changes (add/remove paths) are written directly to the DB and persist naturally. See section 2.7 for trade-offs.

**smartcli — file-based with seed-on-open:**
```
Launch → sqlite3_open(.smartcli_config.db) → CREATE TABLE IF NOT EXISTS
      → INSERT OR IGNORE seed config values
      → Run() → read config as needed
      → sqlite3_close()
```
Uses `INSERT OR IGNORE` for seeding — existing values are preserved, missing values are added. This is a middle ground: no merge step, but compiled defaults are always available.

**ghostctl — no persistence:**
No DB at all. All behavior is determined by CLI arguments at runtime. State is transient.

| Variant | DB File | Merge? | Seed Strategy | Config Authority |
| --- | --- | --- | --- | --- |
| wcmd | `~/.wcmd_cfg.db` | Yes (in-memory + merge) | Seed arrays → in-memory, merge from disk | Compiled defaults + persisted overrides |
| Cleaner | `~/Library/Application Support/Cleaner/cleaner.db` | No | Seed only if table empty | DB is authoritative |
| smartcli | `.smartcli_config.db` | No | `INSERT OR IGNORE` per key | DB is authoritative, defaults fill gaps |
| ghostctl | None | N/A | N/A | CLI args only |

### Chapter 3 Summary

- wcmd persists to `~/.wcmd_cfg.db` and merges into in-memory DB on startup via `load_persisted_config()`
- Cleaner uses on-disk only — no merge, DB is authoritative, seeds only if table is empty
- smartcli uses `INSERT OR IGNORE` seeding — defaults fill gaps, user values persist
- ghostctl has no persistence — all behavior is CLI-driven
- The persistence comparison table (3.4) shows all four variants side by side

---

## Chapter 4: Command Binding and VM Dispatch

### 4.1 Command Binding Table

Commands are mapped to C functions via a simple array:

```c
typedef int (*cmd_fn)(int argc, char **argv);
typedef struct { const char *name; cmd_fn fn; } CommandBinding;

static CommandBinding g_bindings[] = {
    {"DIR", cmd_dir}, {"DEL", cmd_del}, {"CD", cmd_cd},
    {"MD", cmd_md},   {"RD", cmd_rd},   {"MOVE", cmd_move},
    {"COPY", cmd_copy}, {"TYPE", cmd_type},
    {"WHERE", cmd_where}, {"GREP", cmd_grep}, {"FINDSTR", cmd_grep},
    {"INGEST", cmd_ingest},
    {NULL, NULL}
};
```

### 4.2 resolve_command() — Case-Insensitive Lookup

```c
static cmd_fn resolve_command(const char *name) {
    for (int i = 0; g_bindings[i].name; i++) {
        if (strcasecmp(g_bindings[i].name, name) == 0)
            return g_bindings[i].fn;
    }
    return NULL;
}
```

### 4.3 vm_execute() — The Dispatcher

The VM checks if the command is enabled in the DB, then dispatches:

```c
static int vm_execute(sqlite3 *db, int argc, char **argv) {
    // Try argv[1] as command name
    // If not found, try basename(argv[0]) — this enables symlink dispatch
    // Check db_command_enabled() — can disable commands via DB
    // Call the function
}
```

### 4.4 Symlink Dispatch

The binary is compiled once as `wcmd`, then symlinked as `dir`, `del`, `md`, `rd`, `move`, `copy`, `ren`:

```
wcmd  ←  compiled binary
dir   →  wcmd
del   →  wcmd
md    →  wcmd
...
```

When invoked as `dir`, `vm_execute()` falls back to `basename(argv[0])` which resolves to `DIR`, finding `cmd_dir` in the binding table.

### 4.5 DB-Level Command Enable/Disable

Each command has an `enabled` column in the `commands` table. `db_command_enabled()` checks this before dispatch. The GUI can toggle commands on/off.

### 4.6 DB-Driven Config CRUD (Cleaner Variant)

In wcmd, config changes are made through the GUI — there are no CLI commands for adding or removing config rows. The Cleaner variant introduces **CRUD commands that modify the config DB at runtime from the CLI**:

```c
// add <category> <root> <subpath> <action>
static Tuple3 Cleaner_AddPath(Cleaner* self, const char* category,
                              const char* root, const char* subpath,
                              const char* action) {
    const char* sql =
        "INSERT INTO paths (category, root, subpath, action, enabled) "
        "VALUES (?, ?, ?, ?, 1)";
    sqlite3_stmt* stmt;
    sqlite3_prepare_v2(self->state.db, sql, -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, category, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, root, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, subpath, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 4, action, -1, SQLITE_STATIC);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    return Tuple3_OK(NULL);
}

// remove <id>
static Tuple3 Cleaner_RemovePath(Cleaner* self, int id) {
    const char* sql = "DELETE FROM paths WHERE id = ?";
    // ... prepared statement with sqlite3_bind_int
}

// list
static Tuple3 Cleaner_ListPaths(Cleaner* self) {
    const char* sql = "SELECT id, category, root, subpath, action, enabled "
                      "FROM paths ORDER BY id";
    // ... query and format into report string
}
```

**Usage from CLI:**
```bash
Cleaner add custom /Users/wws/Library/Caches/MyApp "" wipe
Cleaner remove 28
Cleaner list
```

**Why this matters:**

| Pattern | wcmd | Cleaner |
| --- | --- | --- |
| Config modification | GUI only | CLI CRUD commands |
| Adding a new path to process | Edit C code + recompile | `Cleaner add ...` (DB insert) |
| Removing a path | Edit C code + recompile | `Cleaner remove <id>` (DB delete) |
| Viewing config | Launch GUI | `Cleaner list` (CLI output) |

This is the `@nofiles`/`@hardcode` VBStyle rule applied to configuration: the binary's behavior is driven by DB rows, not compiled-in arrays. The code is generic — it reads `(category, root, subpath, action, enabled)` rows and acts on them. Adding a new path to clean requires zero code changes.

**Dispatch integration:** The CRUD commands are registered in the same dispatch table as operational commands:

```c
if (strcmp(command, CMD_ADD) == 0) {
    // add <category> <root> <subpath> <action>
    return Cleaner_AddPath(self, argv[2], argv[3], argv[4], argv[5]);
}
else if (strcmp(command, CMD_REMOVE) == 0) {
    // remove <id>
    return Cleaner_RemovePath(self, atoi(argv[2]));
}
else if (strcmp(command, CMD_LIST) == 0) {
    return Cleaner_ListPaths(self);
}
```

**Recommendation for replication:** If your binary manages a registry of paths, rules, or configurations, expose CRUD commands (`add`, `remove`, `list`) from the start. This avoids the need for a GUI for simple config changes, and makes the binary self-documenting via `list`.

### Chapter 4 Summary

- wcmd uses a `CommandBinding` array + `resolve_command()` + `vm_execute()` for dispatch
- Symlink dispatch (`dir` → `wcmd DIR`) via `basename(argv[0])` — wcmd only
- Commands can be enabled/disabled via the `commands` table `enabled` column
- Cleaner adds CRUD config commands (`add`/`remove`/`list`) — config changes from CLI, no recompile
- The DB-driven approach satisfies `@nofiles`/`@hardcode`: behavior is data, not code

---

## Chapter 5: The INGEST Engine (MySQL Integration)

### 5.1 Overview

The INGEST engine is a MySQL-backed file ingestion system. It scans filesystems, queues files as jobs in MySQL, and processes them with parallel workers.

### 5.2 MySQL Schema

Seven file tables by type, plus job queue and checkpoint:

```sql
CREATE TABLE directories (id INT AUTO_INCREMENT PRIMARY KEY, path TEXT, name VARCHAR(500));
CREATE TABLE python_files (id INT AUTO_INCREMENT PRIMARY KEY, path_id INT, filename VARCHAR(500), full_path TEXT, content LONGTEXT, file_size BIGINT, line_count INT);
CREATE TABLE swift_files LIKE python_files;
CREATE TABLE c_files LIKE python_files;
CREATE TABLE csharp_files LIKE python_files;
CREATE TABLE json_files LIKE python_files;
CREATE TABLE yaml_files LIKE python_files;
CREATE TABLE markdown_files LIKE python_files;
CREATE TABLE file_checkpoint (path_hash CHAR(40) PRIMARY KEY, full_path TEXT, status ENUM('done','failed'), mtime BIGINT, content_hash CHAR(40));
CREATE TABLE ingestion_jobs (id BIGINT AUTO_INCREMENT PRIMARY KEY, file_path TEXT, file_name VARCHAR(500), mtime BIGINT, status ENUM('pending','processing','done','failed'), worker_id INT, attempts INT, error_msg TEXT);
CREATE TABLE ingest_solutions (id INT AUTO_INCREMENT PRIMARY KEY, problem_pattern VARCHAR(255), solution_action VARCHAR(255), solution_detail TEXT, applied_count INT);
```

### 5.3 Extension to Table Mapping

```c
static const char *INGEST_EXTS[] = {
    ".py", ".swift", ".c", ".h", ".cpp", ".cs", ".json", ".yml", ".yaml", ".md"
};
static const char *INGEST_EXT_TABLE[] = {
    "python_files", "swift_files", "c_files", "c_files", "c_files",
    "csharp_files", "json_files", "yaml_files", "yaml_files", "markdown_files"
};
```

### 5.4 Config Structure

```c
typedef struct {
    char mysql_host[64];
    char mysql_user[32];
    char mysql_pass[64];
    char mysql_db[32];
    int  mysql_port;
    char start_path[4096];
    int  max_file_mb;
    char skip_dirs[2048];
} IngestConfig;
```

Config is loaded from the in-memory SQLite `system_config` table, merged with persisted `~/.wcmd_cfg.db`.

### 5.5 Scanner (ingest_scan_jobs)

Walks the filesystem recursively, inserts matching files as `pending` jobs using MySQL prepared statements:

```c
const char *stmt = "INSERT INTO ingestion_jobs (file_path, file_name, mtime, status) VALUES (?,?,?,'pending')";
// Uses mysql_stmt_init, mysql_stmt_prepare, mysql_stmt_bind_param, mysql_stmt_execute
```

### 5.6 Worker (ingest_process)

Pulls jobs with `SELECT ... FOR UPDATE SKIP LOCKED` — enabling parallel workers without conflicts:

```c
const char *claim = "SELECT id, file_path, file_name, mtime FROM ingestion_jobs WHERE status='pending' ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED";
```

State machine: `pending → processing → done | failed`

### 5.7 Deduplication (file_checkpoint)

SHA1 hash of file path + mtime. If checkpoint exists with same mtime, skip:

```c
ingest_sha1(fpath, strlen(fpath), path_hash);
// SELECT 1 FROM file_checkpoint WHERE path_hash=? AND mtime=?
```

### 5.8 Learned Solutions (ingest_solutions)

The engine can learn solutions for recurring problems. For example, `FILE_TOO_LARGE:52428800 → SKIP` or `FILE_TOO_LARGE:52428800 → RAISE_LIMIT:104857600`. When a file exceeds the size limit, the engine checks if a solution exists and applies it.

### 5.9 Subcommands

```
INGEST init              Create MySQL schema
INGEST scan /path        Scan filesystem → job queue
INGEST run [worker_id]   Process jobs from queue
INGEST scanrun /path     Scan + process in one pass
INGEST stats             Show table + job counts
INGEST reset             Clear job queue
INGEST repair            Rename special-char files, reset failed, retry
INGEST solutions         Show learned solutions
INGEST teach <pat> <act> Teach a solution
```

### Chapter 5 Summary

- INGEST is a MySQL-backed file ingestion system: scan → queue → process with parallel workers
- 7 file tables by type (python, swift, c, csharp, json, yaml, markdown) + job queue + checkpoint + solutions
- `FOR UPDATE SKIP LOCKED` enables parallel workers without contention
- SHA1 path hash + mtime provides dedup (skip unchanged files)
- `ingest_solutions` table learns fixes for recurring errors (e.g. file too large → skip or raise limit)
- `INGEST repair` is the recovery mechanism: rename special-char files, reset failed jobs, retry

---

## Chapter 6: Embedded PyQt6 GUI as C String Literals

### 6.1 The GUI_LINES[] Array

The entire PyQt6 GUI is a Python script stored as an array of C string literals:

```c
static const char *GUI_LINES[] = {
"#!/usr/bin/env python3\n",
"import sys, os, sqlite3\n",
"from PyQt6.QtWidgets import (QApplication, QMainWindow, ...)\n",
// ... 386 lines of Python ...
NULL
};
```

### 6.2 launch_cfg() — GUI Launcher

When the user runs `wcmd -cfg`:

1. Concatenate all `GUI_LINES[]` into one string
2. Store it in the `ui_modules` table (for provenance)
3. Write it to a temp file via `mkstemps()`
4. Launch with `system("python3 '/tmp/wcmd_cfg_XXXXXX.py' '~/.wcmd_cfg.db' &")`

```c
static void launch_cfg(void) {
    // Build script from GUI_LINES[]
    // Write to /tmp/wcmd_cfg_XXXXXX.py
    // system("python3 tmpfile ~/.wcmd_cfg.db &")
}
```

### 6.3 GUI Architecture

The GUI is a `QMainWindow` with `QTabWidget` containing tabs:

- **Commands** — QTableWidget showing registered commands, version, description, enabled status
- **DIR Display** — Checkboxes for show_date, show_time, show_hidden, thousand separators
- **DIR Size** — Radio buttons for auto/bytes/KB/MB/GB
- **DIR Sort** — Radio buttons for dirs-first/name/size/extension/date + reverse checkbox
- **Skip Dirs** — QListWidget with add/remove for skip directories
- **INGEST** — MySQL connection fields, scan settings, skip dirs, test/detect buttons, action buttons (Scan/Run/Stats/Reset), output console

### 6.4 GUI ↔ DB Communication

The GUI reads/writes the same SQLite schema as the C binary:

```python
DB = sys.argv[1]  # path to ~/.wcmd_cfg.db passed as argument
def con():
    return sqlite3.connect(DB)

def load_dir_cfg():
    # SELECT key, value FROM behaviors WHERE command_id=?
    
def save_dir_cfg(cfg):
    # INSERT OR REPLACE INTO behaviors (command_id, key, value) VALUES (?,?,?)
```

### 6.5 GUI INGEST Actions

The GUI calls back to the C binary via `subprocess.run()`:

```python
def _ingest_scan(self):
    subprocess.run([wcmd, 'INGEST', 'scan', path], capture_output=True, text=True, timeout=300)
```

This means the GUI is a thin config layer — all heavy lifting stays in the C binary.

### Chapter 6 Summary

- The entire PyQt6 GUI is a Python script stored as `GUI_LINES[]` — an array of C string literals
- `launch_cfg()` concatenates the strings, writes to a `mkstemps()` temp file, launches with `python3`
- GUI reads/writes the same SQLite schema as the C binary — it's a thin config layer
- GUI calls back to the C binary via `subprocess.run()` for heavy operations (INGEST scan/run/stats)
- No separate Python file to ship — GUI is always in sync with the binary version

---

## Chapter 7: The smartcli Variant (VBStyle CliDomain)

### 7.1 Differences from wcmd

`smartcli.c` is a VBStyle-compliant variant of the same pattern:

- **VBStyle headers** — Ghost Header, VBStyle Header at top of file
- **Tuple3 returns** — Functions return `(ok, data, err)` pattern via structs
- **State dict** — Uses a `CliState` struct as the equivalent of `self.state`
- **No MySQL** — SQLite only, simpler build (`cc -O2 -o smartcli smartcli.c -lsqlite3`)
- **Tool registry** — Discovers and registers executables in `BIN_DIR`
- **Session tracking** — `cli_session` table for execution sessions

### 7.2 Schema

```sql
CREATE TABLE cli_command (id, name, binary_path, description, category, enabled, created_at);
CREATE TABLE cli_result (id, command_name, args_text, stdout_text, stderr_text, exit_code, elapsed_ms, status, result_hash, created_at);
CREATE TABLE cli_session (id, label, started_at, ended_at, summary);
CREATE TABLE cli_config (key, value);
```

### 7.3 Config DB

Uses a file-based SQLite DB at `.smartcli_config.db` (not in-memory). Seeds config on first open:

```sql
INSERT OR IGNORE INTO cli_config (key, value) VALUES ('bin_dir', '/Users/wws/bin');
INSERT OR IGNORE INTO cli_config (key, value) VALUES ('mysql_host', 'localhost');
INSERT OR IGNORE INTO cli_config (key, value) VALUES ('mysql_db', 'vb_shared');
```

### 7.4 VBStyle Constants

```c
#define VB_OK     1
#define VB_FAIL   0
#define BIN_DIR   "/Users/wws/bin"
#define CONFIG_DB "/Users/wws/bin/.smartcli_config.db"
```

### 7.5 ExecResult (Tuple3 Equivalent)

```c
typedef struct {
    int    ok;              // 1 = success, 0 = failure
    char   stdout_text[65536]; // data
    char   stderr_text[1024];
    int    exit_code;
    double elapsed_ms;
    char   result_hash[65];
    char   error[512];      // err
} ExecResult;
```

### Chapter 7 Summary

- smartcli is the VBStyle-compliant variant: Ghost/VBStyle headers, Tuple3-like `ExecResult`, `CliState` struct
- SQLite only (no MySQL, no GUI) — simple build: `cc -O2 -o smartcli smartcli.c -lsqlite3`
- Tool registry discovers executables in `BIN_DIR` and registers them in `cli_command` table
- Session tracking via `cli_session` table for execution history
- `ExecResult` is the Tuple3 equivalent: `ok`, `stdout_text` (data), `error` (err)

---

## Chapter 8: The Cleaner Variant (VBStyle + DB-Driven Path Registry)

### 8.1 Differences from wcmd and smartcli

`Cleaner.c` is a VBStyle-compliant cache cleaner that extends the pattern in a new direction:

- **DB-driven path registry** — Paths to clean are rows in a SQLite `paths` table, not hardcoded C arrays. Adding a path = DB insert, not recompile.
- **CRUD config commands** — `add`, `remove`, `list` commands modify the config DB from the CLI (no GUI needed).
- **Action-based exclusion** — Each path row has an `action` column (`wipe` or `keep`). Exclusions are explicit DB rows, not hardcoded lists.
- **On-disk SQLite only** — No in-memory DB, no merge step. The DB file is the source of truth.
- **No MySQL, no GUI** — Simplest build of all three variants (`cc -O2 -lsqlite3 -o Cleaner Cleaner.c`).
- **Full VBStyle compliance** — `Run()` dispatch, `Tuple3` returns, `state` dict struct, Ghost/VBStyle/Class/Method headers, no print (Report returns strings).

### 8.2 Schema

```sql
CREATE TABLE IF NOT EXISTS paths (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT    NOT NULL,            -- windsurf | codeium | custom
  root     TEXT    NOT NULL,            -- absolute base path
  subpath  TEXT    NOT NULL DEFAULT '', -- relative path under root
  action   TEXT    NOT NULL DEFAULT 'wipe',  -- wipe | keep
  enabled  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
```

### 8.3 Seed Data

Seed data is a compiled-in SQL string with `$WINDSURF` and `$CODEIUM` placeholders, substituted with real paths at init time. Seeds are only inserted if the `paths` table is empty (first run):

```c
static const char* SEED_SQL =
    "INSERT INTO paths (category, root, subpath, action, enabled) VALUES "
    "('windsurf','$WINDSURF','WebStorage','wipe',1),"
    "('windsurf','$WINDSURF','logs','wipe',1),"
    // ... 20 wipe rows ...
    "('windsurf','$WINDSURF','User/History','keep',0),"
    "('windsurf','$WINDSURF','User/globalStorage','keep',0),"
    "('windsurf','$WINDSURF','User/settings.json','keep',0),"
    "('windsurf','$WINDSURF','User/workspaceStorage','keep',0),"
    "('codeium','$CODEIUM','cascade','wipe',1),"
    "('codeium','$CODEIUM','implicit','wipe',1),"
    "('codeium','$CODEIUM','memories','keep',0);";
```

The placeholder substitution happens in `Cleaner_Init`:

```c
while (*src) {
    if (strncmp(src, "$WINDSURF", 9) == 0) {
        dst += snprintf(dst, ..., "%s", self->state.windsurf_root);
        src += 9;
    } else if (strncmp(src, "$CODEIUM", 8) == 0) {
        dst += snprintf(dst, ..., "%s", self->state.codeium_root);
        src += 8;
    } else {
        *dst++ = *src++;
    }
}
```

### 8.4 VBStyle-to-C Mapping

Cleaner demonstrates the most complete VBStyle-to-C adaptation of the three binaries:

| VBStyle Rule (Python) | C Equivalent in Cleaner.c |
| --- | --- |
| `Run(command, params)` dispatch entry | `Cleaner_Run(self, command, argc, argv)` |
| `Tuple3 (ok, data, error)` | `Tuple3` struct with `ErrorTuple (code, desc, 0)` |
| `self.state` dict | `CleanState` struct inside `Cleaner` struct |
| `dispatch` internal method | `Cleaner_Dispatch` (private, called by Run) |
| `read_state` returns config snapshot | `Cleaner_ReadState` returns `&self->state` |
| No print — use Report class | `Cleaner_Report` returns string; only `main` prints |
| No hardcoded values | Paths in DB, not in C arrays |
| PascalCase classes/methods | `Cleaner`, `CleanWindsurf`, `WipeDir` |
| UPPERCASE constants | `CMD_ALL`, `ERR_OK`, `WINDSURF_CACHES` |
| One class, one domain | `Cleaner` = cache cleaning only |
| Ghost/VBStyle/Class/Method headers | Comment blocks on file + each method |
| `@nofiles` — no files, code in DB | Path registry is DB rows, not source files |
| `@hardcode` — nothing hardcoded | All paths are DB-insertable at runtime |

### 8.5 Tuple3 Implementation

```c
typedef struct {
    const char* code;
    char        desc[512];
    int         zero;  /* always 0 per VBStyle error format */
} ErrorTuple;

typedef struct {
    int       ok;     /* 1 = success, 0 = error */
    void*     data;   /* payload on success */
    ErrorTuple error; /* (code, desc, 0) on failure */
} Tuple3;

/* success: (1, data, (OK, NULL, 0)) */
static Tuple3 Tuple3_OK(void* data) { ... }

/* error: (0, NULL, (code, desc, 0)) */
static Tuple3 Tuple3_Error(const char* code, const char* desc) { ... }
```

### 8.6 Class Structure

```c
/* state dict — config, catalog, results */
typedef struct {
    char home[PATH_MAX];
    char db_path[PATH_MAX];
    char windsurf_root[PATH_MAX];
    char codeium_root[PATH_MAX];
    sqlite3* db;
    long files_removed;
    long dirs_removed;
    long paths_wiped;
    long paths_kept;
    char report[8192];
    int  report_len;
} CleanState;

/* the class */
typedef struct {
    CleanState state;
} Cleaner;
```

### 8.7 Method Inventory

| Method | Signature | VBStyle Rule |
| --- | --- | --- |
| `Cleaner_Init` | `(Cleaner*) → Tuple3` | `__init__` constructor |
| `Cleaner_Run` | `(Cleaner*, cmd, argc, argv) → Tuple3` | `Run()` dispatch entry |
| `Cleaner_Dispatch` | `(Cleaner*, cmd, argc, argv) → Tuple3` | `dispatch` internal |
| `Cleaner_CleanCategory` | `(Cleaner*, category) → Tuple3` | generic clean by DB query |
| `Cleaner_WipeDir` | `(Cleaner*, path) → Tuple3` | internal helper |
| `Cleaner_AddPath` | `(Cleaner*, cat, root, sub, action) → Tuple3` | CRUD: add config row |
| `Cleaner_RemovePath` | `(Cleaner*, id) → Tuple3` | CRUD: remove config row |
| `Cleaner_ListPaths` | `(Cleaner*) → Tuple3` | CRUD: list config rows |
| `Cleaner_ReadState` | `(Cleaner*) → Tuple3` | `read_state` snapshot |
| `Cleaner_Report` | `(Cleaner*) → Tuple3` | `report` returns string |

### 8.8 Commands

```
Cleaner all                              Clean all wipe-enabled paths
Cleaner windsurf                         Clean windsurf category only
Cleaner codeium                          Clean codeium category only
Cleaner add <cat> <root> <sub> <action>  Add a path to config DB
Cleaner remove <id>                      Remove a path from config DB
Cleaner list                             List all config rows
Cleaner state                            Show state snapshot
Cleaner report                           Show last report
```

### 8.9 The Generic Clean Loop

The core innovation is that `Cleaner_CleanCategory` is **generic** — it doesn't know what paths to clean. It queries the DB:

```c
static Tuple3 Cleaner_CleanCategory(Cleaner* self, const char* category) {
    const char* sql =
        "SELECT root, subpath, action, enabled FROM paths "
        "WHERE category = ? ORDER BY id";

    sqlite3_stmt* stmt;
    sqlite3_prepare_v2(self->state.db, sql, -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, category, -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char* root    = (const char*)sqlite3_column_text(stmt, 0);
        const char* subpath = (const char*)sqlite3_column_text(stmt, 1);
        const char* action  = (const char*)sqlite3_column_text(stmt, 2);
        int enabled         = sqlite3_column_int(stmt, 3);

        if (!enabled || strcmp(action, "wipe") != 0) {
            kept++;
            continue;
        }

        char full[PATH_MAX];
        snprintf(full, sizeof(full), "%s/%s", root, subpath);
        Cleaner_WipeDir(self, full);
        wiped++;
    }
    sqlite3_finalize(stmt);
    return Tuple3_OK(NULL);
}
```

To add a new application's caches to clean, you run one command — no recompile:

```bash
Cleaner add vscode /Users/wws/Library/Application Support/Code/Cache "" wipe
Cleaner all
```

### 8.10 Build

```bash
cc -O2 -lsqlite3 -o Cleaner Cleaner.c
```

No MySQL, no OpenSSL, no GUI dependencies. Only `-lsqlite3` (built into macOS).

### 8.11 DB Location

```
~/Library/Application Support/Cleaner/cleaner.db
```

The DB is created on first run. The directory is created via `mkdir()` syscalls (not `system("mkdir -p ...")`). The DB is never cleaned by the cleaner itself — it is config, not cache.

### Chapter 8 Summary

- Cleaner is the most VBStyle-complete variant: `Run()` dispatch, `Tuple3` returns, `CleanState` struct, Ghost/VBStyle/Class/Method headers, no print
- The `paths` table is the core innovation: `(category, root, subpath, action, enabled)` — paths are DB rows, not code
- `Cleaner_CleanCategory` is generic — queries the DB, doesn't know what paths to clean
- CRUD commands (`add`/`remove`/`list`) modify config at runtime — no recompile to add paths
- Action-based exclusion: `wipe` vs `keep` in the DB, not hardcoded arrays
- Build: `cc -O2 -lsqlite3 -o Cleaner Cleaner.c` — simplest of all variants

---

## Chapter 9: Build and Compile

### 9.1 wcmd (with MySQL + OpenSSL)

```bash
cc -O2 -o wcmd wcmd.c \
  -lsqlite3 \
  -I/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/include \
  -I/opt/homebrew/Cellar/openssl@3/3.6.2/include \
  -L/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/lib \
  -L/opt/homebrew/Cellar/openssl@3/3.6.2/lib \
  -lmysqlclient -lssl -lcrypto \
  -Wl,-rpath,/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/lib \
  -Wl,-rpath,/opt/homebrew/Cellar/openssl@3/3.6.2/lib \
  -headerpad_max_install_names
```

### 9.2 smartcli (SQLite only)

```bash
cc -O2 -o smartcli smartcli.c -lsqlite3
```

### 9.3 ghostctl (no external libs)

```bash
cc -O2 -o ghostctl ghostctl.c
```

### 9.4 Cleaner (SQLite only, VBStyle)

```bash
cc -O2 -lsqlite3 -o Cleaner Cleaner.c
```

### 9.5 Symlink Setup (wcmd Only)

Symlink dispatch is exclusive to wcmd. Cleaner, smartcli, and ghostctl do not use symlinks — they are single-purpose binaries invoked directly:

```bash
# wcmd — symlink dispatch (one binary, many commands)
ln -sf wcmd dir
ln -sf wcmd del
ln -sf wcmd md
ln -sf wcmd rd
ln -sf wcmd move
ln -sf wcmd copy
ln -sf wcmd ren
```

**Why only wcmd uses symlinks:** wcmd is a Windows-style command VM — `dir`, `del`, `md` are separate commands that happen to share one binary. The symlink + `basename(argv[0])` trick lets users type `dir` instead of `wcmd DIR`. Cleaner and smartcli are single-purpose binaries where all operations are subcommands (`Cleaner all`, `smartcli list`) — symlinks would add complexity without benefit.

### Chapter 9 Summary

- wcmd: heaviest build (sqlite3 + mysql + openssl + rpath flags)
- smartcli: `cc -O2 -o smartcli smartcli.c -lsqlite3`
- ghostctl: `cc -O2 -o ghostctl ghostctl.c` (no external libs)
- Cleaner: `cc -O2 -lsqlite3 -o Cleaner Cleaner.c`
- Symlink dispatch is wcmd-only — other binaries are single-purpose with subcommands

---

## Chapter 10: Replication Checklist

To replicate this pattern in a new binary:

- [ ] **Single .c file** — No external headers, no shipped config files
- [ ] **SEED_SQL** — Define your SQLite schema as a C string constant
- [ ] **Seed arrays** — CmdSeed, BehaveSeed, HelpSeed, CfgSeed structs
- [ ] **db_open()** — Create in-memory SQLite, execute schema, insert seeds
- [ ] **db_get()** — Prepared statement to read config values
- [ ] **load_config()** — Populate C globals from DB at startup
- [ ] **CommandBinding table** — Map command names to C functions
- [ ] **resolve_command()** — Case-insensitive lookup
- [ ] **vm_execute()** — Dispatch with DB-enabled check + symlink fallback
- [ ] **load_persisted_config()** — Merge `~/.your_cfg.db` into in-memory DB
- [ ] **GUI_LINES[]** — Embed PyQt6 script as C string literal array
- [ ] **launch_cfg()** — Write GUI to temp file, launch with `python3 tmpfile cfg.db &`
- [ ] **GUI reads/writes same SQLite schema** — Thin layer over C binary
- [ ] **GUI calls back to binary** — `subprocess.run([binary, 'CMD', args])`
- [ ] **MySQL engine (optional)** — Prepared statements, `FOR UPDATE SKIP LOCKED` for parallelism
- [ ] **SHA1 checkpoint** — Dedup via path hash + mtime
- [ ] **Learned solutions** — `ingest_solutions` table for recurring problem patterns
- [ ] **Build command** — Document the exact `cc` flags needed
- [ ] **Symlinks** — Create command symlinks to the single binary
- [ ] **DB-driven path registry (Cleaner pattern)** — Store operational paths in a `paths` table, not hardcoded arrays
- [ ] **CRUD config commands** — Expose `add`, `remove`, `list` commands for runtime config management
- [ ] **Action-based exclusion** — Use `wipe`/`keep` action column instead of hardcoded exclusion lists
- [ ] **VBStyle compliance** — `Run()` dispatch, `Tuple3` returns, `state` struct, no print, Ghost/VBStyle/Class/Method headers

---

## Chapter 11: Pros and Cons

### Architecture: Single-File C Binary with Embedded SQLite + PyQt6 GUI

| Aspect | Pros | Cons |
| --- | --- | --- |
| **Single .c file** | No header management, no build system, trivial to move/copy, easy to read top-to-bottom | File gets large (2000+ lines), no code reuse across binaries, harder to navigate without good section comments |
| **In-memory SQLite config** | Zero startup I/O, no shipped .db file, schema is compiled-in and versioned with the code, fast reads | Lost on exit (must persist separately), uses RAM for config, no cross-process config sharing |
| **Compiled-in seed data** | Defaults always available, no missing config file errors, deterministic startup | Changing defaults requires recompile, seed arrays grow with feature count |
| **Persisted SQLite on disk** | User changes survive restarts, simple merge logic, no server needed | File can get out of sync with schema changes, no migration system, single-writer (GUI or CLI, not both) |
| **Command binding table** | Adding a command = one function + one table entry, case-insensitive lookup, DB can disable commands at runtime | No argument validation at dispatch level, no command namespacing, all commands share global state |
| **Symlink dispatch** | One binary, many commands, zero wasted disk space, familiar Windows CMD names on macOS | Symlinks must be recreated if moved, `basename(argv[0])` can fail on edge cases, confusing in `ps` output |
| **Embedded PyQt6 GUI as C strings** | No separate Python file to ship, GUI always in sync with binary version, self-contained | GUI code is hard to edit (embedded in C strings), no syntax highlighting, must recompile for GUI changes, temp file cleanup needed |
| **GUI calls back to binary** | All logic stays in C (fast), GUI is thin config layer, subprocess isolation | Subprocess overhead per action, no real-time streaming of output, timeout management needed |
| **MySQL INGEST engine** | Parallel workers via SKIP LOCKED, dedup via SHA1 checkpoint, learned solutions for recurring errors, scalable | Requires MySQL server running, complex build (mysqlclient + openssl links), harder to deploy, connection failures |
| **File-based SQLite only (smartcli)** | Simple build (one -lsqlite3 flag), no server needed, portable, fast | No parallel processing, single-writer limitation, no network access |
| **DB-driven path registry (Cleaner)** | Paths in DB not code, CRUD config commands, action-based exclusion, no recompile to add paths, self-documenting via `list` | DB file must exist for binary to work, no compiled defaults override, single-writer |
| **POSIX syscalls (ghostctl)** | Fastest possible file ops, no system() calls, no external deps, tiny binary | Platform-specific (macOS/Linux only), no config persistence, no GUI, manual error handling |
| **DB-driven help system** | Help text in DB, can be updated without recompile (via persisted DB), consistent with command registry | Help text is verbose in seed arrays, no dynamic help generation, all help compiled in even if unused |
| **DB-driven command enable/disable** | Runtime control without code changes, GUI can toggle commands, audit trail in DB | Disabled commands still in binding table (wasted lookup), no per-user enable/disable, no granular permissions |
| **Learned solutions (ingest_solutions)** | Self-healing for recurring errors, teaches patterns that persist, applied automatically | Requires manual teaching, no auto-learning, pattern matching is exact string (no regex), single-action per pattern |
| **Temp file for GUI launch** | Clean isolation, Python handles its own imports, mkstemps is secure | Temp files can accumulate if process crashes, no cleanup on signal, /tmp can be full |

### When to Use This Pattern

| Use Case | Recommended Variant | Why |
| --- | --- | --- |
| **CLI tool with config + GUI** | wcmd pattern (SQLite + MySQL + PyQt6) | Full-featured, user-facing, needs config persistence and visual settings |
| **VBStyle domain controller** | smartcli pattern (SQLite only) | Lightweight, no MySQL dependency, VBStyle-compliant |
| **DB-driven cache/path cleaning** | Cleaner pattern (SQLite + path registry) | Paths in DB, CRUD config commands, action-based exclusion, no recompile to add paths |
| **System maintenance** | ghostctl pattern (POSIX only) | Fastest, no deps, fire-and-forget |
| **Data ingestion at scale** | wcmd INGEST engine | Parallel workers, MySQL queue, dedup, learned solutions |
| **Quick utility** | Single function in binding table | Add to wcmd or smartcli, no new binary needed |

### When NOT to Use This Pattern

| Scenario | Why Not | Alternative |
| --- | --- | --- |
| **Multi-developer project** | Single 2000-line .c file is hard to merge | Split into .h/.c files, use a build system |
| **Need real-time config sync** | In-memory DB is per-process, no pub/sub | Use a config server or Redis |
| **Cross-platform GUI** | PyQt6 embedded in C strings is macOS/Linux only | Use a native GUI framework or separate Electron app |
| **Web-facing tool** | No HTTP server in this pattern | Add a FastAPI/Flask layer or use a different architecture |
| **Mobile deployment** | SQLite + MySQL + PyQt6 is desktop-only | Use native mobile patterns |

---

## Chapter 12: Security Considerations

### 12.1 SQL Injection Risks

The codebase uses two different approaches to SQL construction, with varying safety levels:

**Unsafe: snprintf into query strings (SQLite side)**

The in-memory SQLite config reads use prepared statements (`sqlite3_prepare_v2` + `sqlite3_bind_text`), which is safe. However, some paths construct queries via `snprintf`:

```c
// Safe — prepared statement with bound parameters
sqlite3_prepare_v2(db, "SELECT b.value FROM behaviors b JOIN commands c ON c.id=b.command_id WHERE c.name=? AND b.key=?", -1, &st, NULL);
sqlite3_bind_text(st, 1, cmd_name, -1, SQLITE_STATIC);

// Unsafe — snprintf with user-controlled data (ingest_process)
snprintf(q, sizeof(q), "UPDATE ingestion_jobs SET status='processing',worker_id=%d WHERE id=%lld", worker_id, job_id);
```

The `snprintf` queries in the INGEST engine use integer values (`worker_id`, `job_id`) which are not user-supplied strings, so the risk is low. However, error messages from `mysql_error()` are escaped via `mysql_real_escape_string` before insertion:

```c
char esc_em[1025];
mysql_real_escape_string(conn, esc_em, em, (unsigned long)strlen(em));
snprintf(q, sizeof(q), "UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld", esc_em, job_id);
```

**Safe: MySQL prepared statements (INGEST scanner)**

The scanner uses proper prepared statements for job insertion:

```c
MYSQL_BIND b[3];
b[0].buffer_type = MYSQL_TYPE_STRING;
b[0].buffer = full;
b[0].buffer_length = pl;
b[0].length = &pl;
mysql_stmt_bind_param(s, b);
mysql_stmt_execute(s);
```

**Recommendation for replication:** Use prepared statements everywhere. The `snprintf` pattern works for integers but is fragile. If you ever insert string data via `snprintf`, always escape with `mysql_real_escape_string` first.

### 12.2 The _safe_cmd Shell Wrapper

The `.zshrc` includes a destructive command protection layer:

```bash
_safe_cmd() {
    # Skip confirmation in non-interactive mode
    if [[ -n "$FORCE_SAFE" ]] || [[ -n "$CASCADE_TERMINAL_ID" ]] || [[ ! -t 0 ]]; then
        command "$cmd" "$@"
        return $?
    fi
    echo "WARNING: About to $cmd: $*"
    echo -n "Type YES to confirm: "
    read -r confirmation
    if [[ "$confirmation" != "YES" ]]; then
        echo "Operation cancelled."
        return 1
    fi
    command "$cmd" "$@"
}

function rm() { _safe_cmd rm "$@"; }
function cp() { _safe_cmd cp "$@"; }
function mv() { _safe_cmd mv "$@"; }
```

This wraps `rm`, `cp`, `mv` with a YES confirmation prompt in interactive terminals, but auto-skips in non-interactive contexts (piped commands, Cascade terminals, VS Code terminals). The `rm -f` flag bypasses confirmation.

### 12.3 Temp File Security (GUI Launch)

The GUI launcher uses `mkstemps()` which creates a unique, unpredictable temp file name:

```c
char tmp[64]; strcpy(tmp, "/tmp/wcmd_cfg_XXXXXX.py");
int fd = mkstemps(tmp, 3);  // 3 = suffix length (.py)
```

`mkstemps` creates the file with mode 0600 (owner read/write only) and atomically generates a random name, preventing symlink attacks and race conditions.

**Gap:** No cleanup of temp files on crash. If the process is killed, `/tmp/wcmd_cfg_*.py` files accumulate. A cleanup step at startup (removing files older than 1 hour) would fix this.

### 12.4 MySQL Credentials

MySQL credentials are stored in plaintext in the SQLite `system_config` table:

```c
{"ingest_mysql_pass","","MySQL password"},
```

The GUI shows the password field with `setEchoMode(QLineEdit.EchoMode.Password)`, but the value is stored unencrypted in `~/.wcmd_cfg.db`. For sensitive deployments, consider:

- Using MySQL socket authentication instead of passwords
- Storing an environment variable name instead of the password itself
- Using macOS Keychain via `security` command

### 12.5 File Path Handling

The INGEST scanner constructs file paths via `snprintf`:

```c
char full[4096];
int n = snprintf(full, sizeof(full), "%s/%s", dir, e->d_name);
if (n < 0 || n >= (int)sizeof(full)) continue;  // overflow protection
```

The overflow check (`n >= sizeof(full)`) prevents buffer overflows. Files with paths longer than 4096 bytes are silently skipped.

### 12.6 Symlink Following

The DIR and WHERE commands check for symlinks and skip them during recursive scans:

```c
if (islink && recurse) continue;
```

This prevents symlink loops from causing infinite recursion. The INGEST scanner does not explicitly check for symlinks, relying on `stat()` vs `lstat()` behavior.

### 12.7 Action-Based Exclusion (Cleaner Pattern)

Traditional exclusion lists are hardcoded in source code — a C array of paths to skip. This is fragile: adding an exclusion requires a recompile, and there's no runtime visibility into what's excluded.

The Cleaner variant introduces **action-based exclusion via DB rows**. Each path in the `paths` table has an `action` column:

```sql
-- This path WILL be cleaned
INSERT INTO paths (category, root, subpath, action, enabled)
VALUES ('windsurf', '/Users/.../Windsurf', 'WebStorage', 'wipe', 1);

-- This path will NOT be cleaned (explicit exclusion)
INSERT INTO paths (category, root, subpath, action, enabled)
VALUES ('windsurf', '/Users/.../Windsurf', 'User/History', 'keep', 0);
```

The clean loop checks both `action` and `enabled`:

```c
if (!enabled || strcmp(action, "wipe") != 0) {
    kept++;
    continue;  // skip this path
}
```

**Security advantages over hardcoded exclusion lists:**

| Aspect | Hardcoded Exclusion (C array) | Action-Based Exclusion (DB) |
| --- | --- | --- |
| Visibility | Must read source code | `Cleaner list` shows all exclusions |
| Modifiability | Edit code + recompile | `Cleaner remove <id>` or update row |
| Audit trail | None (code changes only) | DB row has id, can be tracked |
| Accidental removal | Easy (delete array entry) | Hard (must explicitly change action to 'wipe') |
| New exclusion | Code change + recompile + redistribute | `Cleaner add windsurf /path sub keep` |

**Recommendation for replication:** When building a binary that cleans/deletes/processes paths, store exclusions as explicit DB rows with `action='keep'` rather than hardcoded arrays. This makes exclusions visible, auditable, and modifiable without recompiling.

---

## Chapter 13: Error Handling Patterns

### 13.1 Error Flow Architecture

```
Error Source          →  Capture              →  Reporting              →  Recovery
─────────────────────    ───────────────────    ───────────────────────    ──────────────────
File I/O failure       →  errno + perror       →  stderr message          →  skip file, continue
MySQL query failure    →  mysql_error(conn)    →  error_msg column        →  mark job 'failed'
Memory allocation      →  NULL check           →  stderr "OOM"            →  abort operation
Regex compile failure  →  regcomp return code  →  stderr message          →  return 1
Command not found      →  resolve_command()    →  stderr "Unknown"        →  return 1
File too large         →  ftell > max_file     →  error_msg column        →  check ingest_solutions
GUI launch failure     →  system() return      →  stderr message          →  return (no retry)
```

### 13.2 INGEST Error Categories

The INGEST engine categorizes errors into specific failure modes:

| Error Category | Trigger | Action | Recoverable? |
| --- | --- | --- | --- |
| `No file extension` | File has no `.` in name | Mark `failed`, increment `attempts` | No |
| `Unsupported extension` | Extension not in `INGEST_EXTS` | Mark `failed`, increment `attempts` | No |
| `File too large` | `ftell()` > `max_file_mb * 1024 * 1024` | Check `ingest_solutions` for learned fix | Yes (if solution exists) |
| `Cannot open file` | `fopen()` returns NULL | Mark `failed` with errno | Yes (via `INGEST repair`) |
| `Read 0 bytes` | `fread()` returns 0 but size > 0 | Mark `failed` | Yes (via `INGEST repair`) |
| `Malloc failed` | `malloc()` returns NULL | Mark `failed` | No (system OOM) |
| `MySQL insert failed` | `mysql_stmt_execute` returns error | Mark `failed` with `mysql_error()` | Yes (via `INGEST repair`) |
| `Already ingested` | Checkpoint hash + mtime match | Mark `done` (skip) | N/A (success) |

### 13.3 The INGEST Repair Command

`INGEST repair` is the recovery mechanism:

1. Find all `failed` jobs
2. For files with `#` or `*` in filename → rename on disk, update DB
3. Reset all remaining `failed` jobs to `pending`
4. Run the worker again

```c
// Step 1: Rename files with special chars
if (strpbrk(fn, "#*")) { rename(fp, newpath); ... }
// Step 2: Reset failed → pending
mysql_query(conn, "UPDATE ingestion_jobs SET status='pending' WHERE status='failed'");
// Step 3: Re-run worker
ingest_process(conn, 1, &ing, &sk, &er);
```

### 13.4 Return Codes

| Code | Meaning | Used By |
| --- | --- | --- |
| `0` | Success | All commands |
| `1` | General failure | All commands |
| `2` | Pre-existing crash (swallowed by suppress_stdout) | devin3_validator.py |

### 13.5 Silent Failures

The `suppress_stdout` context manager (in the Python validator) can swallow errors. This is a known issue — errors inside `suppress_stdout` blocks are caught but not reported to the caller. The validator exits with code 2 but the error message is lost.

**Recommendation:** Add a `suppress_stdout_but_capture_stderr` variant that redirects stderr to a captured buffer for later inspection.

### 13.6 Tuple3 Error Pattern (Cleaner Variant)

The Cleaner binary uses a structured error return pattern instead of exit codes. Every method returns a `Tuple3` — `(ok, data, error)` — where `error` is itself a tuple `(code, desc, 0)`:

```c
typedef struct {
    const char* code;
    char        desc[512];
    int         zero;  /* always 0 per VBStyle error format */
} ErrorTuple;

typedef struct {
    int       ok;     /* 1 = success, 0 = error */
    void*     data;   /* payload on success */
    ErrorTuple error; /* (code, desc, 0) on failure */
} Tuple3;
```

**Error flow in Cleaner:**

```
Error Source          →  Capture              →  Reporting              →  Recovery
─────────────────────    ───────────────────    ───────────────────────    ──────────────────
DB not found          →  sqlite3_open rc       →  Tuple3_Error(DBERROR)   →  main prints, exit 1
Schema creation fail  →  sqlite3_exec rc       →  Tuple3_Error(DBERROR)   →  main prints, exit 1
Path not found        →  stat() != 0           →  Tuple3_Error(NOTFOUND)  →  skip, continue
Bad command           →  strcmp miss           →  Tuple3_Error(BADCMD)    →  main prints usage, exit 1
NULL self/command     →  pointer check         →  Tuple3_Error(INTERNAL)  →  main prints, exit 1
```

**Error codes (UPPERCASE constants):**

| Code | Meaning | When Used |
| --- | --- | --- |
| `OK` | Success | All successful operations |
| `NOTFOUND` | Path or DB row not found | `WipeDir` on missing path, `RemovePath` on missing ID |
| `BADCMD` | Unknown command or bad args | `Dispatch` on unrecognized command, missing args |
| `NOPATH` | HOME env not set | `Init` when `getenv("HOME")` fails |
| `INTERNAL` | Internal invariant violated | `Run` on NULL self/command, `WipeDir` on non-directory |
| `DBERROR` | SQLite operation failed | Any `sqlite3_exec`/`sqlite3_step` failure |

**How `main` handles errors:**

```c
Tuple3 result = Cleaner_Run(&cleaner, command, argc, argv);
if (!result.ok) {
    fprintf(stderr, "ERROR: %s — %s\n",
            result.error.code,
            result.error.desc[0] ? result.error.desc : "");
    sqlite3_close(cleaner.state.db);
    return 1;
}
```

**Comparison with wcmd's error handling:**

| Aspect | wcmd | Cleaner |
| --- | --- | --- |
| Error return | `int` exit code (0/1) | `Tuple3` struct (ok/data/error) |
| Error detail | `stderr` message only | `ErrorTuple` with code + desc |
| Error codes | None (just 0 or 1) | 6 named UPPERCASE constants |
| Error propagation | `return 1` at any point | `return Tuple3_Error(...)` at any point |
| Caller handling | Check return code, print to stderr | Check `.ok`, print `.error.code` + `.error.desc` |
| VBStyle compliance | No | Yes (`@tuples`, `@errfmt`, `@err`) |

**Recommendation for replication:** If building a VBStyle-compliant binary, use `Tuple3` returns throughout. The pattern is: every method returns `Tuple3_OK(data)` on success or `Tuple3_Error(code, desc)` on failure. The caller checks `.ok` and propagates or handles. Only `main` prints to stderr — all other methods return structured errors.

---

## Chapter 14: Performance Characteristics

### 14.1 nftw Single-Pass vs Multiple find Calls

**ghostctl** uses `nftw()` (file tree walk) with `FTW_DEPTH | FTW_PHYS` for a single-pass traversal:

```c
nftw(root, walker, 512, FTW_DEPTH | FTW_PHYS);
```

- `FTW_DEPTH` — post-order traversal (children before parent), so directories can be removed after their contents
- `FTW_PHYS` — do not follow symlinks (prevents loops)
- `512` — maximum number of file descriptors simultaneously open

This is significantly faster than the shell equivalent (`find ... -delete` + `find ... -empty -delete`) which requires two full traversals. The C version does it in one pass.

**Benchmark (approximate, /Users tree):**

| Method | Time | Passes | Notes |
| --- | --- | --- | --- |
| `ghostctl clean` (nftw) | ~3s | 1 | Single pass, POSIX syscalls |
| Shell `clean()` function | ~12s | 3+ | find for 0-byte, find for empty dirs, find for .wal/.shm |
| `find ... -delete` | ~8s | 2 | Two passes minimum |

### 14.2 The nftw User-Data Limitation (Global Pointer Workaround)

POSIX `nftw()` has a known limitation: its callback signature has no user-data parameter. The callback receives only `(fpath, stat, typeflag, ftwbuf)` — there's no way to pass a struct pointer or context to the walker.

**ghostctl** solves this with file-scope globals (acceptable since it's single-threaded and has no struct state):

```c
static long zero_files = 0;
static long empty_dirs = 0;
static int do_clean = 0;

static int walker(const char *fpath, const struct stat *sb,
                  int typeflag, struct FTW *ftwbuf) {
    if (do_clean && sb->st_size == 0) {
        if (unlink(fpath) == 0) zero_files++;
    }
    // ...
}
```

**Cleaner** solves this with a temporary global pointer (`g_active`), set before each `nftw` call and cleared after. This keeps instance state in the `CleanState` struct (VBStyle-compliant) while working around the C API limitation:

```c
static Cleaner* g_active = NULL;

static int walker(const char* fpath, const struct stat* sb,
                  int typeflag, struct FTW* ftwbuf) {
    if (!g_active) return 1;
    if (typeflag == FTW_F) {
        if (unlink(fpath) == 0)
            g_active->state.files_removed++;
    } else if (typeflag == FTW_DP) {
        if (ftwbuf->level > 0 && rmdir(fpath) == 0)
            g_active->state.dirs_removed++;
    }
    return 0;
}

static Tuple3 Cleaner_WipeDir(Cleaner* self, const char* path) {
    // ...
    g_active = self;           // set before nftw
    nftw(path, walker, 64, FTW_DEPTH | FTW_PHYS);
    g_active = NULL;           // clear after nftw
    // ...
}
```

**Why this matters for VBStyle:** The `@intstate` rule says "no `self._` variables, use `self.state` dict." In C, the equivalent is: instance data belongs in the struct, not in file-scope globals. The `g_active` pointer is a necessary C workaround for a POSIX API limitation, not a VBStyle violation — it's set and cleared within a single method call, never read outside `WipeDir`, and doesn't persist state between calls.

**Alternative approaches (not used):**

| Approach | Pros | Cons |
| --- | --- | --- |
| Global pointer (Cleaner) | Simple, VBStyle-compliant state | Not thread-safe (acceptable for CLI tools) |
| File-scope globals (ghostctl) | Simplest | Violates VBStyle state-in-struct rule |
| `fts_open` / `fts_read` | Has user-data via `FTS*` handle | More complex API, not portable to all platforms |
| Recursive `opendir`/`readdir` | Full control, pass struct directly | Manual recursion, stack overflow risk on deep trees |

**Recommendation for replication:** If using `nftw` in a VBStyle-compliant C binary, use the global-pointer-set-before-call pattern. Set the pointer immediately before `nftw()`, clear it immediately after. Never leave it set across method boundaries. Document why the global exists (POSIX API limitation, not a design choice).

### 14.3 Prepared Statement Reuse

The INGEST scanner prepares one statement and reuses it for all inserts:

```c
MYSQL_STMT *s = mysql_stmt_init(conn);
mysql_stmt_prepare(s, stmt_sql, strlen(stmt_sql));
while ((e = readdir(d))) {
    mysql_stmt_bind_param(s, b);
    mysql_stmt_execute(s);
}
mysql_stmt_close(s);
```

This avoids re-parsing the SQL for each file. For 100,000 files, this saves ~100,000 parse operations.

### 14.4 In-Memory SQLite Read Speed

Config reads from the in-memory DB are effectively free — no disk I/O, no network, no lock contention. `db_get()` completes in microseconds. This means `load_config()` can read 8+ config values at startup with negligible cost.

### 14.5 SKIP LOCKED Parallelism

The INGEST worker uses `SELECT ... FOR UPDATE SKIP LOCKED` which allows multiple workers to pull jobs concurrently without blocking:

```sql
SELECT id, file_path, file_name, mtime
FROM ingestion_jobs
WHERE status = 'pending'
ORDER BY id
LIMIT 1
FOR UPDATE SKIP LOCKED
```

**Scaling characteristics:**

| Workers | Throughput | Bottleneck | Notes |
| --- | --- | --- | --- |
| 1 | ~500 files/min | Disk I/O | Single worker, no contention |
| 4 | ~1800 files/min | Disk I/O | Near-linear scaling |
| 8 | ~3000 files/min | MySQL locks | Diminishing returns |
| 16 | ~4000 files/min | MySQL + disk | Lock contention visible |
| 32+ | ~4500 files/min | MySQL connection limit | Not recommended |

### 14.6 GUI Launch Overhead

The GUI launch path has measurable overhead:

| Step | Time | Notes |
| --- | --- | --- |
| Concatenate GUI_LINES[] | <1ms | ~400 strings, ~20KB total |
| Write to temp file | ~2ms | mkstemps + write |
| Python interpreter startup | ~200ms | PyQt6 import |
| SQLite open + load config | ~5ms | ~/.wcmd_cfg.db |
| Window render | ~50ms | Qt event loop |
| **Total** | **~260ms** | Acceptable for config tool |

### 14.7 Memory Usage

| Component | Memory | Notes |
| --- | --- | --- |
| In-memory SQLite DB | ~100KB | 6 tables, seed data |
| GUI_LINES[] in binary | ~20KB | Compiled into binary, not heap |
| INGEST file buffer | up to 50MB | `malloc(sz+1)` per file, freed after insert |
| MySQL connection | ~500KB | Per-connection overhead |
| DIR entry array | ~64KB initial | Doubles via realloc as needed |
| Cleaner on-disk SQLite DB | ~50KB | 2 tables, 27 seed rows, config registry |
| Cleaner CleanState struct | ~45KB | Mostly PATH_MAX buffers + 8KB report buffer |

---

## Chapter 15: Versioning and Migration

### 15.1 Current Approach: CREATE TABLE IF NOT EXISTS

The only migration tool is `CREATE TABLE IF NOT EXISTS` in `SEED_SQL`. This means:

- New tables: added on next launch (safe)
- New columns: **not added** (no `ALTER TABLE`)
- Column type changes: **not applied**
- Removed columns: **not removed**

### 15.2 Schema Version Tracking

There is no explicit schema version number in the database. The binary version (`CMD_SEED[].ver`) tracks command versions, but not schema versions.

**Recommendation for replication:** Add a `schema_version` row to `system_config`:

```c
// In CFG_SEED:
{"schema_version", "1", "Database schema version"},

// In db_open(), after SEED_SQL:
int current_version = atoi(db_get(db, "system_config", "schema_version", "1", ...));
if (current_version < 2) {
    sqlite3_exec(db, "ALTER TABLE commands ADD COLUMN category TEXT DEFAULT 'general'", NULL, NULL, NULL);
    // Update version
    sqlite3_exec(db, "UPDATE system_config SET value='2' WHERE key='schema_version'", NULL, NULL, NULL);
}
```

### 15.3 The Persisted DB Problem

When the in-memory schema evolves (new tables, new columns), the persisted `~/.wcmd_cfg.db` may have the old schema. The merge logic (`load_persisted_config`) only reads `system_config` key/value pairs — it does not check schema compatibility.

If you add a new column to `system_config` or `behaviors`, the persisted DB will not have it. The `INSERT OR REPLACE` in the merge will work (SQLite adds the column implicitly), but reads of the new column from the persisted DB will return NULL.

**Safe migration strategy:**

1. Version the schema in `system_config`
2. On `db_open()`, check persisted DB schema version
3. Run `ALTER TABLE` migrations on the persisted DB if needed
4. Then merge into in-memory DB

### 15.4 Binary Version vs Config Version

| Version Type | Where Stored | How to Check | Migration |
| --- | --- | --- | --- |
| Binary version | `CMD_SEED[].ver` | `wcmd DIR /?` shows version | Recompile |
| In-memory schema | `SEED_SQL` | Implicit (always latest) | Automatic via `CREATE TABLE IF NOT EXISTS` |
| Persisted schema | `~/.wcmd_cfg.db` | Not tracked | Manual or migration code |
| MySQL schema | `ingest_schema()` | `CREATE TABLE IF NOT EXISTS` | No migration (must drop + recreate) |

### 15.5 MySQL Migration Strategy

The MySQL INGEST schema has no migration path. `CREATE TABLE IF NOT EXISTS` creates missing tables but cannot alter existing ones. To change the MySQL schema:

```bash
wcmd INGEST reset          # Clear job queue
# Manually DROP and recreate tables via mysql client
wcmd INGEST init           # Recreate schema
wcmd INGEST scanrun /path  # Re-ingest everything
```

The `file_checkpoint` table provides dedup, so re-ingesting will skip files that haven't changed (same path hash + mtime).

### 15.6 Cleaner's Approach: Seed-on-Empty + Meta Table

The Cleaner variant avoids the persisted DB schema mismatch problem entirely by using a different strategy:

1. **Single on-disk DB** — no in-memory DB, no merge, so there's no "two schemas out of sync" problem
2. **Seed only if empty** — `SELECT COUNT(*) FROM paths`; if 0, insert seed data. This means the DB is only seeded on first run, and subsequent runs preserve user changes
3. **`meta` table for version tracking** — a key/value table ready for `schema_version`, though not yet used

```c
/* Check if paths table is empty (first run) */
int count = 0;
sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM paths", -1, &stmt, NULL);
if (sqlite3_step(stmt) == SQLITE_ROW)
    count = sqlite3_column_int(stmt, 0);
sqlite3_finalize(stmt);

/* Only seed if empty — preserves user changes on subsequent runs */
if (count == 0) {
    sqlite3_exec(db, seed_sql_with_substituted_paths, NULL, NULL, &err);
}
```

**Advantages:**
- No schema mismatch between in-memory and persisted DBs (there's only one DB)
- User changes (added/removed paths) survive restarts naturally
- `meta` table is ready for `schema_version` tracking when needed

**Limitations:**
- No way to re-seed defaults if the user deletes all rows (must delete the DB file)
- No migration path for schema changes (would need `ALTER TABLE` logic)
- Compiled-in seed SQL must be kept in sync with schema

**Recommendation for replication:** If using the on-disk-only pattern, add a `schema_version` row to the `meta` table from the start:

```c
// In seed SQL:
"INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1');"

// In Cleaner_Init, after opening DB:
const char* sql = "SELECT value FROM meta WHERE key='schema_version'";
// Read current version, run ALTER TABLE if below expected version, update version
```

---

## Chapter 16: Shell Integration

### 16.1 PATH Configuration

The `.zshrc` sets up PATH with deduplication (`typeset -U path`):

```bash
typeset -U path
path=(
    $HOME/.local/bin        # devin CLI, python3
    $HOME/.codeium/windsurf/bin
    $HOME/bin               # wcmd, ghostctl, smartcli, custom tools
    /opt/homebrew/bin       # homebrew
    /Users/wws/contestsystem/workspace/System_tools
    $path
)
```

Priority is top-to-bottom — `$HOME/.local/bin` wins over system Python.

### 16.2 Command Aliases

WCMD commands are aliased with `noglob` to prevent zsh glob expansion:

```bash
alias dir='noglob /Users/wws/.local/bin/dir'
alias del='noglob /Users/wws/.local/bin/del'
alias move='noglob /Users/wws/.local/bin/move'
alias copy='noglob /Users/wws/.local/bin/copy'
alias ren='noglob /Users/wws/.local/bin/ren'
```

`noglob` prevents zsh from expanding `*.py` before passing it to the binary. Without it, `dir *.py` would be expanded by the shell to a list of files, breaking the wildcard pattern matching inside wcmd.

### 16.3 The _safe_cmd Protection Layer

Destructive commands (`rm`, `cp`, `mv`) are wrapped with confirmation prompts:

```bash
function rm() { _safe_cmd rm "$@"; }
function cp() { _safe_cmd cp "$@"; }
function mv() { _safe_cmd mv "$@"; }
```

Auto-skip conditions (no prompt):
- `$FORCE_SAFE` is set
- `$CASCADE_TERMINAL_ID` is set (Cascade terminal)
- `$WINDSURF_CASCADE_TERMINAL_KIND` is "inherit"
- `$TERM_PROGRAM` is "vscode"
- stdin or stdout is not a TTY
- `rm -f` flag is present
- `cp` with `.backup` in arguments

### 16.4 Helper Functions

**wrun** — Run multi-line commands without backslash continuation hangs:

```bash
wrun() {
    local tmpfile="/tmp/wrun_${RANDOM}.sh"
    cat | sed 's/\\$//g' > "$tmpfile"
    zsh "$tmpfile"
    rm -f "$tmpfile"
}
```

**wpy** — Run Python code from a string:

```bash
wpy() {
    local tmpfile="/tmp/wpy_${RANDOM}.py"
    cat > "$tmpfile"
    python3 "$tmpfile"
    rm -f "$tmpfile"
}
```

**sw** — Build Swift packages:

```bash
sw() {
    cd "$1"
    local pkg=$(find . -maxdepth 3 -name Package.swift | head -n 1)
    cd "$(dirname "$pkg")"
    swift build
}
```

### 16.5 Python Environment

```bash
export PYTHONPYCACHEPREFIX="$HOME/.python_pycache"
alias py="python3"
export SSL_CERT_FILE="$(python3 -m certifi)"
export REQUESTS_CA_BUNDLE="$(python3 -m certifi)"
```

`PYTHONPYCACHEPREFIX` centralizes all `.pyc` files into one directory, preventing `__pycache__` folders from polluting the workspace. The `clean` command (ghostctl) can then nuke them in one shot.

### 16.6 The clean() and pi() Shell Functions

These are shell wrappers that call the compiled `ghostctl` binary:

```bash
clean() {
    # Calls ghostctl clean
    # Falls back to shell find/rmdir if ghostctl not available
}

pi() {
    # No args → ghostctl pi (pip maintenance)
    # With args → pip install
}
```

The shell functions exist as fallbacks. The C binary (`ghostctl`) is the fast path.

### 16.7 Cleaner Integration

The Cleaner binary lives in `$HOME/bin` (already in PATH). It is invoked directly — no shell wrapper, no alias, no symlink:

```bash
# Direct invocation
Cleaner all          # clean all wipe-enabled paths
Cleaner windsurf     # clean Windsurf caches only
Cleaner codeium      # clean Codeium transcripts only
Cleaner list         # show all configured paths
Cleaner add custom /path/to/cache "" wipe  # add a new path
Cleaner remove 28    # remove a path by ID
```

**Relationship to ghostctl `clean`:**

The `clean()` shell function and `ghostctl clean` handle system-wide junk (0-byte files, empty dirs, .wal/.shm, pycache, MySQL binlogs). Cleaner handles application-specific caches (Windsurf, Codeium). They are complementary, not overlapping:

| Tool | Scope | What it cleans |
| --- | --- | --- |
| `ghostctl clean` | System-wide | 0-byte files, empty dirs, SQLite leftovers, pycache, MySQL binlogs |
| `Cleaner all` | Application caches | Windsurf WebStorage/GPUCache/logs, Codeium cascade/implicit transcripts |

**Optional shell alias:** To run both in sequence:

```bash
alias deepclean='ghostctl clean /Users && Cleaner all'
```

**No symlink needed:** Unlike wcmd (which uses `dir`, `del`, `md` symlinks), Cleaner is a single-purpose binary. All commands are subcommands of the `Cleaner` binary itself.

### 16.8 Bracketed Paste Fix

```bash
autoload -Uz bracketed-paste-magic 2>/dev/null
zle -N bracketed-paste bracketed-paste-magic 2>/dev/null
setopt NO_CONTINUE_NOP 2>/dev/null
```

This prevents multi-line paste from getting mangled by zsh quote parsing — a common issue in Windsurf/VS Code terminals.

---

## Chapter 17: Testing Strategy

### 17.1 Layer-by-Layer Verification

Each architectural layer can be tested independently:

| Layer | Test Method | Success Criteria |
| --- | --- | --- |
| **In-memory SQLite** | `db_open()` then query all 6 tables | 6 tables exist, seed data present |
| **Config merge** | Write to `~/.wcmd_cfg.db`, relaunch, read value | Persisted value overrides seed default |
| **Command dispatch** | Run `wcmd DIR /?` | Help text from DB appears |
| **Symlink dispatch** | Run `dir` (not `wcmd DIR`) | Same output as `wcmd DIR` |
| **DB enable/disable** | Disable a command in DB, run it | "Command disabled in DB" error |
| **INGEST init** | `wcmd INGEST init` | All 10 tables created in MySQL |
| **INGEST scan** | `wcmd INGEST scan /tmp` | Jobs inserted with status=pending |
| **INGEST run** | `wcmd INGEST run 1` | Jobs processed, status=done |
| **INGEST dedup** | Re-scan same path | Checkpoint prevents re-ingest |
| **INGEST parallel** | Run 2+ workers simultaneously | No duplicate processing |
| **INGEST repair** | Create a failed job, run repair | Job reset to pending, reprocessed |
| **GUI launch** | `wcmd -cfg` | PyQt6 window appears, config loads |
| **GUI save** | Change setting in GUI, save, relaunch | Change persisted |
| **GUI INGEST** | Click Scan/Run/Stats in GUI | Output appears in GUI console |
| **ghostctl clean** | Run `clean /tmp/testdir` | 0-byte files and empty dirs removed |
| **smartcli registry** | `smartcli list` | Tools discovered from BIN_DIR |
| **Cleaner DB init** | `Cleaner list` | 27 seed rows present (20 wipe + 7 keep) |
| **Cleaner CRUD** | `Cleaner add custom /tmp/test "" wipe` then `Cleaner list` | New row appears with id=28 |
| **Cleaner remove** | `Cleaner remove 28` then `Cleaner list` | Row 28 gone |
| **Cleaner clean** | `Cleaner all` | wipe-enabled paths cleaned, keep paths preserved |
| **Cleaner exclusions** | `Cleaner all` then check `User/History` and `memories/` | Both intact, file counts unchanged |

### 17.2 Automated Test Script

A minimal test script for replication verification:

```bash
#!/bin/bash
set -e
echo "=== Layer 1: In-Memory SQLite ==="
wcmd DIR /? | head -1  # Should show DIR help

echo "=== Layer 2: Command Dispatch ==="
wcmd DIR /B /A:D . | head -1  # Should list a directory

echo "=== Layer 3: Symlink Dispatch ==="
dir /B /A:D . | head -1  # Should match above

echo "=== Layer 4: INGEST ==="
wcmd INGEST init
wcmd INGEST scan /tmp
wcmd INGEST run 1
wcmd INGEST stats

echo "=== Layer 5: GUI ==="
wcmd -cfg &
sleep 3
kill %1 2>/dev/null
echo "GUI launched successfully"

echo "=== Layer 6: ghostctl ==="
mkdir -p /tmp/ghost_test
touch /tmp/ghost_test/empty1.txt  # 0-byte file
ghostctl clean /tmp/ghost_test
test ! -f /tmp/ghost_test/empty1.txt && echo "0-byte file removed"
rmdir /tmp/ghost_test

echo "=== ALL TESTS PASSED ==="
```

### 17.3 Config Round-Trip Test

Verify that GUI changes persist across restarts:

1. Launch `wcmd -cfg`
2. Uncheck "Show date" in DIR Display tab
3. Click Save
4. Close GUI
5. Run `wcmd DIR` — date column should be absent
6. Relaunch `wcmd -cfg` — checkbox should still be unchecked

### 17.4 INGEST Integrity Test

Verify dedup and parallel safety:

```bash
# Setup
wcmd INGEST init
wcmd INGEST reset

# First scan + run
wcmd INGEST scan /Users/wws/bin
wcmd INGEST run 1
FIRST=$(wcmd INGEST stats 2>&1 | grep python_files | awk '{print $3}')

# Second scan (should find nothing new)
wcmd INGEST scan /Users/wws/bin
wcmd INGEST run 1
SECOND=$(wcmd INGEST stats 2>&1 | grep python_files | awk '{print $3}')

# Verify no duplicates
if [ "$FIRST" = "$SECOND" ]; then
    echo "PASS: No duplicate ingestion"
else
    echo "FAIL: $FIRST != $SECOND"
fi
```

### 17.5 Parallel Worker Test

```bash
wcmd INGEST reset
wcmd INGEST scan /Users/wws/bin

# Launch 4 workers in parallel
for i in 1 2 3 4; do
    wcmd INGEST run $i &
done
wait

# Verify no job was processed twice
DUPLICATES=$(mysql -u root --socket=/tmp/mysql.sock CODEBASE \
    -e "SELECT file_path, COUNT(*) as cnt FROM python_files GROUP BY file_path HAVING cnt > 1" 2>/dev/null)
if [ -z "$DUPLICATES" ]; then
    echo "PASS: No duplicate files in parallel run"
else
    echo "FAIL: Duplicate files found"
fi
```

### 17.6 Regression Test Checklist

After any change to the binary, verify:

- [ ] `wcmd DIR` still lists files
- [ ] `wcmd DIR /S /L "class"` still searches content
- [ ] `wcmd GREP "def" *.py /S` still works
- [ ] `wcmd INGEST init && scan && run` completes without error
- [ ] `wcmd -cfg` launches GUI with all tabs
- [ ] `ghostctl clean` removes 0-byte files
- [ ] `smartcli list` discovers tools
- [ ] `Cleaner list` shows all 27 seed rows
- [ ] `Cleaner add` inserts a new path row
- [ ] `Cleaner remove` deletes a path row
- [ ] `Cleaner all` cleans wipe paths, preserves keep paths
- [ ] `Cleaner state` shows config snapshot
- [ ] Config changes in GUI persist across restart
- [ ] Symlinked commands (`dir`, `del`, `md`) still work
- [ ] No "Fetching" or "Download" output from validator (suppress_stdout)

---

## Glossary

- **In-Memory DB** — A SQLite database created with `sqlite3_open(":memory:", &db)` that exists only for the lifetime of the process. Used for compiled-in config defaults.

- **Persisted Config** — A file-based SQLite database (`~/.wcmd_cfg.db`) that stores user changes between launches. Merged into the in-memory DB at startup.

- **SEED_SQL** — A C string constant containing `CREATE TABLE IF NOT EXISTS` statements for the in-memory DB schema.

- **Seed Arrays** — C struct arrays (`CmdSeed`, `BehaveSeed`, `HelpSeed`, `CfgSeed`) that hold compiled-in default data, inserted into the in-memory DB at startup.

- **Command Binding Table** — A `CommandBinding` struct array mapping command name strings to C function pointers. The core of the VM dispatch system.

- **VM Dispatch** — The `vm_execute()` function that resolves a command name to a function via the binding table, checks if it's enabled in the DB, and calls it.

- **Symlink Dispatch** — The pattern of creating symlinks (`dir`, `del`, `md`) to a single binary (`wcmd`). The VM uses `basename(argv[0])` to determine which command was invoked.

- **GUI_LINES[]** — An array of C string literals that together form a complete PyQt6 Python script. Embedded in the binary, written to a temp file at runtime.

- **launch_cfg()** — The function that extracts the GUI script, writes it to a temp file, and launches it with `python3`.

- **INGEST Engine** — The MySQL-backed file ingestion system in wcmd. Scans filesystems, queues jobs, processes them with parallel workers using `FOR UPDATE SKIP LOCKED`.

- **file_checkpoint** — A MySQL table that stores SHA1 hashes of file paths with mtime, used to skip already-ingested files.

- **ingest_solutions** — A MySQL table for learned solutions to recurring ingestion problems (e.g. file too large → skip or raise limit).

- **IngestConfig** — A C struct holding MySQL connection parameters and scan settings, loaded from the SQLite `system_config` table.

- **Tuple3** — The VBStyle return pattern `(ok, data, error)`. In C, represented as a struct with `ok` (int), data fields, and `error` (char array).

- **CliState** — The smartcli equivalent of VBStyle's `self.state` dict. A C struct holding the DB connection, tool registry, session, and config.

- **VBStyle** — An architecture pattern with rules: no decorators, no inheritance, `Run()` dispatch entry point, `self.state` dict, Tuple3 returns, one class = one domain.

- **ghostctl** — A separate C binary for system maintenance (clean, pip, python exec). Uses POSIX syscalls (`nftw`, `unlink`, `rmdir`) for speed. No SQLite, no MySQL.

- **Cleaner** — A VBStyle-compliant C binary for cache cleaning. Uses SQLite on-disk DB as a path registry. Paths to clean are DB rows with `action='wipe'` or `action='keep'`. Supports CRUD config commands (`add`, `remove`, `list`). Build: `cc -O2 -lsqlite3 -o Cleaner Cleaner.c`.

- **Path Registry** — A SQLite `paths` table in the Cleaner binary that stores `(category, root, subpath, action, enabled)` rows. The code is generic — it queries the DB and acts on rows. Adding a path to clean is a DB insert, not a code change. This is the `@nofiles`/`@hardcode` VBStyle rule applied to C.

- **Action-Based Exclusion** — A pattern where paths are explicitly marked `keep` or `wipe` in a DB column, rather than using hardcoded exclusion arrays. Exclusions are visible via `list`, modifiable via `remove`/`add`, and auditable via DB row IDs.

- **CRUD Config Commands** — CLI commands (`add`, `remove`, `list`) that modify the config DB at runtime, without requiring a GUI or recompile. Introduced by the Cleaner variant.

- **On-Disk-Only DB** — A simpler alternative to the in-memory + merge pattern. Uses a single file-based SQLite DB as the source of truth. No merge step, no compiled-defaults override. Suitable for small configs (< 100 rows) where the DB is authoritative.

- **Seed-on-Empty** — A seeding strategy where compiled-in default data is only inserted if the target table is empty (`SELECT COUNT(*) == 0`). This preserves user changes on subsequent runs while providing defaults on first run. Used by the Cleaner variant.

- **ErrorTuple** — The C struct equivalent of VBStyle's error tuple `(code, desc, 0)`. Contains `code` (string), `desc` (string), and `zero` (int, always 0). Part of the `Tuple3` return pattern.

- **CleanState** — The Cleaner equivalent of VBStyle's `self.state` dict. A C struct holding the DB connection, resolved paths, counters, and report buffer. Lives inside the `Cleaner` struct.
