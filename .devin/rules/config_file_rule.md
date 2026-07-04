# CONFIG FILE RULE

## Rule: Mandatory Config File Per Folder

### R1 — Config Presence
Every folder in the workspace that contains configuration, settings, schema, paths, or constants **must** have a config file named `Config_<foldername>.py`. This file is the single source of truth for that folder's configuration.

### R2 — Config Content
The `Config_<foldername>.py` file must contain:
- All settings, paths, schema, constants, and variables used by files in that folder
- Environment variable overrides where applicable
- A singleton instance (`cfg = Config()`) for consumption by other files
- No hardcoded values in any other file in the folder — all values come from the config

### R3 — Mandatory File Index
Every `Config_<foldername>.py` file **must** contain a `FILE_INDEX` constant — a complete list of **all files** in that folder. No exceptions.

### R4 — File Index Structure
Each entry in `FILE_INDEX` must include:
- `file` — filename
- `purpose` — what the file does
- `classes` — all class names defined in the file
- `methods` — all method names (with class prefix)
- `functions` — all standalone functions
- `properties` — all `@property` accessors (if applicable)
- `created` — creation date
- `modified` — last modified date
- `size` — file size in bytes
- `lines` — line count

### R5 — File Index Maintenance
The `FILE_INDEX` must be updated **whenever any file is added, removed, or modified** in the folder. No exceptions. An outdated `FILE_INDEX` is a violation of this rule.

### R6 — File Index Access
The config class must expose `FILE_INDEX` as a class attribute and provide getter methods:
- `GetFileIndex()` — returns full index with all metadata
- `GetFileList()` — returns list of filenames only

### R7 — No Hardcoding (Zero Tolerance)
No file in the workspace may contain hardcoded values. This includes:
- **Paths** — no literal file paths. All paths must come from config (`cfg.PATH_TO_X`)
- **Hosts / ports / URLs** — no literal `localhost:3306`. Must come from config
- **Database names** — no literal `vb_shared`. Must come from config
- **Credentials** — no passwords, usernames, tokens in code. Must come from env vars via config
- **Table names** — no literal table names in queries. Must come from config
- **Schema names** — no literal schema names. Must come from config
- **Magic numbers** — no literal numbers in logic. Define as constants in config
- **String constants** — no repeated string literals. Define as constants in config

**Every value that could change between environments must live in the config file.**

If a value appears in code and is not derived from config or an environment variable, it is a violation.

### R8 — Config Is the Single Source of Truth
Every folder's `Config_<foldername>.py` is the **only** place where settings are defined. No other file in that folder may define its own settings, paths, or constants independently. All files must import from the config singleton:

```python
from Config_<foldername> import cfg
```

If a file needs a value, it reads it from `cfg`. It does not define its own.

### R9 — Everything Inside Config (No External Files)
The `Config_<foldername>.py` file must be self-contained. Everything the folder needs lives inside it:
- **Documentation** — `ABOUT`, `HELP`, `README` as string constants. No `.md` files.
- **SQL schema** — `SCHEMA_SQL`, `SEED_SQL` as string constants. No `.sql` files.
- **Config seed data** — embedded as SQL string. No external seed files.
- **Static resources** — embedded as compressed base64 constants. No loose resource files.
- **Settings** — all paths, hosts, ports, credentials, table names as class attributes or config DB rows.
- **File index** — `FILE_INDEX` constant listing all files in the folder.

**If it can be put in config, it goes in config. No external files for anything config can hold.**

### R10 — Code Graph
The `FILE_INDEX` must serve as a **code graph** — a complete structural map of the folder. It must capture:
- **Class hierarchy** — which classes inherit from which
- **Method signatures** — method name, parameters, return type
- **Function signatures** — function name, parameters, return type
- **Dependencies** — what each file imports (local imports only)
- **Call graph** — which methods/functions call which other methods/functions in the folder
- **Properties** — all `@property` accessors with their return types
- **Entry points** — which files have `if __name__ == "__main__"` blocks
- **Dispatch maps** — which classes have `Run()` dispatch and what commands they map

This code graph must be maintained alongside `FILE_INDEX` — updated whenever files change. No exceptions.

### R11 — VBStyle Enforcement via FILE_INDEX
The `FILE_INDEX` must verify and record VBStyle compliance for each file:
- **Ghost header** — present? yes/no
- **VBStyle header** — present? yes/no
- **AI guide block** — present? yes/no (config files only)
- **Class headers** — present on all classes? yes/no
- **Method headers** — present on all methods? yes/no
- **Naming compliance** — PascalCase classes, UPPERCASE constants, camelCase methods? yes/no
- **No print** — confirmed no print statements? yes/no
- **No hardcode** — confirmed no hardcoded values? yes/no
- **No decorators** — confirmed no decorators? yes/no
- **No tabs** — confirmed spaces only? yes/no

If any file fails VBStyle compliance, the `FILE_INDEX` must flag it. Non-compliant files are violations.

### R12 — File Integrity Check
The `FILE_INDEX` must store a hash (SHA256) for each file. On load, config can verify that files have not been modified outside the index. If a file's hash doesn't match, the index is stale and must be updated.

### R13 — Dependency Validation
The config must track and validate:
- **Python imports** — are all imported modules available? List missing packages.
- **Requirements** — does the folder have a `requirements.txt`? Are all deps pinned?
- **Cross-folder deps** — does this folder import from another folder's config? Is that config available?
- **Version pins** — are all third-party packages pinned to specific versions?

### R14 — Dead Code Detection
The code graph in `FILE_INDEX` must flag:
- **Unused classes** — classes never imported or instantiated by any other file in the folder
- **Unused methods** — methods never called by any other method in the folder
- **Unused functions** — standalone functions never called
- **Unused constants** — config constants never referenced by any file

Dead code must be flagged for removal.

### R15 — TODO/FIXME/HACK Scanning
The `FILE_INDEX` must scan each file for:
- `TODO` — pending work
- `FIXME` — known bugs
- `HACK` — temporary workarounds
- `XXX` — warning/danger markers
- `NOQA` — suppressed linter warnings

Each marker must be listed with file, line number, and the comment text. These are technical debt that must be tracked.

### R16 — Cross-Folder Consistency
The config must validate references to other folders:
- **Import paths** — if folder A imports from folder B, folder B's config must exist
- **Shared table names** — if two folders reference the same MySQL table, the table name must be identical in both configs
- **Shared env vars** — if two folders use the same env var, it must be documented in both configs
- **Schema references** — if folder A writes to a table that folder B reads, both configs must agree on the schema

### R17 — File Size and Complexity Limits
The `FILE_INDEX` must flag files that exceed limits:
- **Max lines per file** — 1000 lines. Files over 1000 lines must be split.
- **Max methods per class** — 30 methods. Classes over 30 methods must be split.
- **Max parameters per method** — 7 parameters. Methods with more must use a params dict.
- **Max nesting depth** — 4 levels. Deeper nesting must be refactored.

### R18 — Config Self-Validation
On load, the config must validate itself:
- **All paths exist** — every path defined in config must point to an existing file or directory (or be creatable)
- **All env var names are valid** — uppercase, no spaces, no special chars
- **All SQL is valid syntax** — embedded SQL must parse without errors
- **All getters return values** — every getter method must return a non-None value
- **Singleton is instantiable** — `cfg = Config()` must succeed without errors
- **FILE_INDEX matches actual files** — every file in the folder must be in the index, and every file in the index must exist

### R19 — Config Holds Values, Not Imports
The config file stores **values** — paths, hosts, ports, schema, docs, settings. It does **not** import third-party libraries on behalf of other files.

**Wrong:**
```python
# Config.py
from PyQt6 import QtWidgets, QtGui  # DON'T do this in config

# chat_mover.py
from Config import cfg
cfg.QtWidgets.QMainWindow(...)  # accessing PyQt6 through config
```

**Right:**
```python
# Config.py — only imports it needs for itself (os, sqlite3, zlib, etc.)

# chat_mover.py
from PyQt6 import QtWidgets, QtGui       # import what YOU need
from Config_chat_mover import cfg         # import config for VALUES only
```

Each file imports its own dependencies directly. Config is not a proxy for imports. Config is a source of values.

### R20 — Startup Order
Config always loads first. The startup flow is:

1. User runs a Python file (e.g., `python chat_mover.py`)
2. File's first local import: `from Config_<foldername> import cfg`
3. Config boots cold — creates SQLite DB from embedded SQL if missing, loads values, applies env var overrides
4. Config validates FILE_INDEX, checks VBStyle compliance, runs self-validation
5. Singleton `cfg` is ready
6. File uses `cfg.MYSQL_HOST`, `cfg.SCHEMA_SQL`, etc. for all values
7. File imports its own third-party dependencies (PyQt6, mysql.connector, etc.) directly

**Nothing runs before config. Config is always the first import.**
