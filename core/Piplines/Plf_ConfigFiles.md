# The Config File Manual

> **Road 12 on the CodeGPS Garmin** — Standardized configuration files across all domains.

---

## Preface

This manual is the authoritative reference for every `Config.py` and `Config_*.py` file in the project. It exists because config files were being written ad-hoc — different structures, different headers, different conventions — making it impossible for an AI model (or a human) to open any config file and immediately understand the domain.

The goal: **every config file follows the same structure, the same order, the same rules.**

---

## Index

| Chapter | Title | Question Answered |
|---|---|---|
| 1 | What Is a Config File? | What is this thing? |
| 2 | Why Config Files Exist | Why do we need them? |
| 3 | Where to Make a Config File | Where does it go? |
| 4 | How to Make a Config File | How do I create one? |
| 5 | The Five Mandatory Sections | What must be in it? |
| 6 | Optional Sections | What can be in it? |
| 7 | File Inventory System | How does the file index work? |
| 8 | The Config Class | How does the programmatic API work? |
| 9 | What Reads Config Files | Who consumes them? |
| 10 | How the Config Works at Runtime | How does it actually function? |
| 11 | Read, Write, Update Lifecycle | How is it made, read, written, updated? |
| 12 | Universal vs Domain-Specific | What belongs here vs elsewhere? |
| 13 | BCL Token Format | What's the token syntax? |
| 14 | Templates | What do I copy to start? |
| 15 | Anti-Patterns | What NOT to do? |
| 16 | How to Migrate an Old Config | I have a bad config, how do I fix it? |
| 17 | Connection to Other Systems | How does config connect to VBStyle, BCL, GUI? |
| 18 | Validation | How do I check if it's correct? |
| 19 | Current Config Audit | What's the state right now? |
| 20 | Pipeline Stages | How do we fix all configs? |
| 21 | History and Evolution | How did we get here? |
| 22 | FAQ | Common questions, quick answers |
| — | Glossary | What do the terms mean? |
| — | Reference Config Files | Where are the examples? |

---

## Chapter 1 — What Is a Config File?

A config file is the **front door** to a domain. It is a single Python file that tells you everything you need to know about a domain folder:

- **What files exist** in the domain
- **What each file does** (purpose, one-line)
- **What classes and methods** are defined
- **Whether each file is VBStyle compliant**
- **What constants, paths, and settings** the domain uses
- **How to query the domain** programmatically via `Run()` dispatch

Every domain folder has exactly one: `Config.py` or `Config_<DomainName>.py`.

A config file is NOT:
- A settings file (it's a full Python module with a class)
- A standalone script (it has no `if __name__ == "__main__"`)
- A documentation file (it's machine-readable, but also human-readable)
- Optional (every domain MUST have one)

---

## Chapter 2 — Why Config Files Exist

### 2.1 The Problem They Solve

Before this standard, config files were written ad-hoc. Different AI sessions created configs with different structures, different headers, different conventions. The result:

- **No AI could understand a domain by reading its config** — because every config looked different
- **No validation was possible** — because there was no standard to validate against
- **Universal content got buried** in domain configs (e.g. Garmin Navigator in `Dom_Gui/config.py`)
- **File inventories were missing** — you had to `ls` the folder and read every file to know what was there
- **No programmatic access** — configs were just flat constants, no `Run()` dispatch

### 2.2 The Goal

**Every config file follows the same structure, the same order, the same rules.** You open one, you know where everything is. You open any other, it's in the same place.

### 2.3 What Happens Without This Standard

- An AI opens `Dom_Gui/config.py` and sees 170 lines of Garmin Navigator text. It thinks the domain IS the Navigator. It doesn't know about `parser.py`, `builder.py`, `router.py` — because there's no file inventory.
- An AI opens `Dom_DecisionTrees/Config.py` and sees no headers, no BCL tokens, no Config class. It has no idea what the domain is about without reading every file.
- A human opens `Dom_Graph/Config.py` and sees headers claiming a Config class exists, but the body is 1100 lines of flat constants with no class. The headers lie.

### 2.4 What Happens With This Standard

- Any AI opens any config → reads Section 2 (file inventory) → immediately knows every file, class, method, and VBStyle status
- Any AI reads Section 5 (README) → understands the architecture and data flow
- Any code calls `Config.Run("read_state")` → gets domain name, version, DB path, file count
- Validation runs automatically → catches missing files, bad tokens, universal content leaks

---

## Chapter 3 — Where to Make a Config File

### 3.1 Location Rule

One config file per domain folder, in the folder root:

```
project_root/
├── Config.py                          ← root project config (gold standard)
├── core/
│   ├── Dom_Gui/
│   │   └── config.py                  ← Dom_Gui domain config
│   ├── Dom_Bcl/
│   │   └── Config_BCL.py              ← Dom_Bcl domain config
│   ├── Dom_Graph/
│   │   └── Config.py                  ← Dom_Graph domain config
│   ├── Dom_Unified/
│   │   └── Config.py                  ← universal config (Garmin, etc.)
│   └── Dom_Vsstyle/
│       └── Config_Vbs_Code_Verifiation.py
├── Dom_DecisionTrees/
│   └── Config.py
├── Dom_Graph/
│   └── Config.py
└── gui_engine/
    └── Config.py
```

### 3.2 Naming Convention

| Pattern | When | Example |
|---|---|---|
| `Config.py` | Default — when domain has one config | `core/Dom_Gui/config.py` |
| `Config_<DomainName>.py` | When domain name needs disambiguation | `Config_BCL.py`, `Config_Vbs_Code_Verifiation.py` |

### 3.3 What About Subdomains?

If a domain has subfolders that are significant enough to have their own config, the subfolder gets its own `Config.py`. Example:

```
core/Dom_Bcl/
├── Config_BCL.py          ← main BCL config
├── Dom_Bcl_C_ver/         ← C version subdomain
│   └── (may have its own Config.py if needed)
```

### 3.4 Where NOT to Put a Config File

- In a subfolder that is not a domain (e.g. `core/Piplines/` — these are pipeline docs, not domains)
- In the root of a utility folder (utilities share `core/utility/Config.py`)
- As a duplicate (one config per domain, no backups, no `Config_old.py`)

---

## Chapter 4 — How to Make a Config File

### 4.1 When to Make One

A config file must exist **before** any other file is created in a domain. It is the first file. Everything else references it.

### 4.2 Who Makes One

- **Cascade** — when planning a new domain (creates the skeleton)
- **Devin** — when building a full domain (creates complete config)
- **Prj_VBScanner.py** — regenerates Section 2 (file inventory) only

### 4.3 Minimal Example

```python
#!/usr/bin/env python3
#[@GHOST]{[@file<Config.py>][@domain<MyDomain>][@role<config>][@auth<cascade>][@date<2026-06-29>][@ver<1.0.0>]}
#[@VBSTYLE]{[@auth<system>][@role<domain_config>][@return<tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}
#[@SUMMARY]{One-line description of what this domain does}
#[@FILEID]{[@file<Config.py>][@domain<MyDomain>][@date<2026-06-29>][@ver<1.0.0>]}
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOMAIN_VERSION = "1.0.0"
DB_PATH = os.path.join(BASE_DIR, "my_domain.db")
FILE_INDEX = [
    "# [@File:main_py]{(\"file\";\"main.py\")(\"purpose\";\"Entry point\")(\"classes\";\"Main\")(\"methods\";\"Run,read_state\")(\"vbstyle\";\"True\")(\"lines\";\"120\")}",
]
FILES = {"main.py": {"purpose": "Entry point", "lines": 120, "classes": ["Main"], "methods": ["Run"], "vbstyle": True}}
CLASSES = {"Main": {"file": "main.py", "methods": ["__init__", "Run", "read_state"]}}
class Config:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {}
        self.mem = mem
        self.db = db
        self.param = param
    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state()
        elif command == "get_file_index":
            return (1, FILE_INDEX, None)
        elif command == "get_files":
            return (1, FILES, None)
        elif command == "get_classes":
            return (1, CLASSES, None)
        return (0, None, ("unknown_command", command, 0))
    def read_state(self):
        return (1, {"domain": "MyDomain", "version": DOMAIN_VERSION, "db_path": DB_PATH}, None)
```

---

## Chapter 5 — The Five Mandatory Sections

Every config file MUST contain these five sections **in this order**. No skipping. No reordering.

```
Section 1: BCL HEADERS          — identity + compliance
Section 2: FILE INVENTORY       — what files exist here
Section 3: DOMAIN CONSTANTS     — the actual config values
Section 4: CONFIG CLASS         — programmatic access
Section 5: README / AI-GRAPH    — human + AI explanation
```

### 2.1 Section 1 — BCL Headers

| Header | Purpose | Fields |
|---|---|---|
| `[@GHOST]` | Identity | file, domain, role, auth, date, ver |
| `[@VBSTYLE]` | Compliance | auth, role, return, orch, no |
| `[@SUMMARY]` | One-line description | What the domain does |
| `[@FILEID]` | File stamp | file, domain, date, ver |

Rules: domain name matches folder name, author is `cascade`/`devin`/`system`, version is semantic. First lines of file, before imports.

### 2.2 Section 2 — File Inventory

Machine-readable index of every `.py` file in the domain. Two formats accepted:
- `FILE_INDEX` — BCL token strings (preferred, gold standard)
- `FILES` + `CLASSES` dicts (acceptable, human-readable)

See Chapter 3 for details.

### 2.3 Section 3 — Domain Constants

What goes here: `BASE_DIR`, `DOMAIN_VERSION`, DB paths, MySQL config, domain maps, themes, schemas, intervals.

What does NOT go here: universal content (see Chapter 6), hardcoded paths, `print()`, decorators, tabs.

### 2.4 Section 4 — Config Class

VBStyle-compliant class with `Run()` dispatch, `read_state()`, `set_config()`, Tuple3 returns. See Chapter 4.

### 2.5 Section 5 — README / AI-Graph

Domain-specific architecture, data flow, file explanations, mental models. **No universal content.** See Chapter 6.

---

## Chapter 3 — File Inventory System

### 3.1 What Is the File Inventory?

A complete, machine-readable index of every `.py` file in the domain folder. It answers: what files exist, what each does, what classes/methods are defined, VBStyle compliance, BCL header presence.

### 3.2 Format 1 — FILE_INDEX (BCL Tokens, Preferred)

```python
FILE_INDEX = [
    "# [@File:parser_py]{(\"file\";\"parser.py\")(\"purpose\";\"Parses BCL declarations\")(\"classes\";\"BCLParser\")(\"methods\";\"parse,tokenize\")(\"vbstyle\";\"True\")(\"vbstyle_passed\";\"9\")(\"vbstyle_total\";\"9\")(\"vbstyle_failed\";\"\")(\"bcl\";\"True\")(\"bcl_headers\";\"GHOST,VBSTYLE,SUMMARY\")(\"lines\";\"180\")}",
]
```

Fields per entry: `file`, `purpose`, `classes`, `methods`, `functions`, `vbstyle`, `vbstyle_passed`, `vbstyle_total`, `vbstyle_failed`, `bcl`, `bcl_headers`, `created`, `modified`, `size`, `lines`.

### 3.3 Format 2 — FILES + CLASSES Dicts (Acceptable)

```python
FILES = {
    "parser.py": {"purpose": "Parses BCL declarations", "lines": 180, "classes": ["BCLParser"], "methods": ["parse"], "vbstyle": True},
}
CLASSES = {
    "BCLParser": {"file": "parser.py", "methods": ["__init__", "parse", "tokenize"]},
}
```

### 3.4 Generation

Auto-generated by `Prj_VBScanner.py`:
```bash
python3 Prj_VBScanner.py core/Dom_Gui --append-only
```

Manual edits will be overwritten. Scanner walks folder, parses AST, extracts metadata, checks VBStyle, generates BCL tokens.

### 3.5 Completeness Rule

**Every** `.py` file in the domain folder must have an entry. Missing entry = validation fail.

---

## Chapter 4 — The Config Class

### 4.1 Purpose

Provides programmatic access via VBStyle `Run()` dispatch:
```python
from core.Dom_Gui.config import Config
cfg = Config()
state = cfg.Run("read_state")  # (1, {"domain": "Dom_Gui", ...}, None)
```

### 4.2 Required Methods

| Method | Command | Returns |
|---|---|---|
| `__init__` | — | Sets `self.state`, `self.mem`, `self.db`, `self.param` |
| `Run` | dispatch | Routes to methods based on command |
| `read_state` | `"read_state"` | `(1, {domain, version, db_path, file_count}, None)` |
| `set_config` | `"set_config"` | `(1, updated_state, None)` |
| — | `"get_file_index"` | `(1, FILE_INDEX, None)` |
| — | `"get_files"` | `(1, FILES, None)` |
| — | `"get_classes"` | `(1, CLASSES, None)` |
| — | `"get_constants"` | `(1, constants_dict, None)` |
| — | `"get_readme"` | `(1, readme_string, None)` |

### 4.3 VBStyle Rules

- `__init__(self, mem=None, db=None, param=None)` — standard signature
- `self.state` dict — NO `self._`
- All methods return Tuple3
- No `@property`, `@staticmethod`, `@classmethod`
- No `print()`, PascalCase, UPPERCASE constants

### 4.4 Full Example

```python
class Config:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {}
        self.mem = mem
        self.db = db
        self.param = param

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state()
        elif command == "set_config":
            return self.set_config(params or {})
        elif command == "get_file_index":
            return (1, FILE_INDEX, None)
        elif command == "get_files":
            return (1, FILES, None)
        elif command == "get_classes":
            return (1, CLASSES, None)
        elif command == "get_constants":
            return (1, self._get_constants(), None)
        elif command == "get_readme":
            return (1, README_TEXT, None)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self):
        return (1, {"domain": "Dom_Gui", "version": DOMAIN_VERSION, "db_path": DB_PATH, "file_count": len(FILES)}, None)

    def set_config(self, params):
        for key, value in (params or {}).items():
            self.state[key] = value
        return (1, self.state, None)

    def _get_constants(self):
        return {"DOMAIN_VERSION": DOMAIN_VERSION, "DB_PATH": DB_PATH}
```

---

## Chapter 5 — Read, Write, Update Lifecycle

### 5.1 How Config Files Are Made

```
Step 1: Create file with BCL headers (Section 1)
Step 2: Run Prj_VBScanner.py → file inventory (Section 2)
Step 3: Add domain constants (Section 3)
Step 4: Add Config class (Section 4)
Step 5: Add README text (Section 5)
Step 6: Validate (Chapter 8)
Step 7: Verify (py_compile + import test)
```

### 5.2 How Config Files Are Read

- **Humans:** Open file, sections in fixed order, jump to what you need
- **AI models:** Read Section 2 (inventory) for domain graph, Section 5 (README) for architecture, query via `Run()`
- **Other code:** Import and call `Run()`

### 5.3 How Config Files Are Written

- **Cascade** — initial creation, structural fixes
- **Devin** — full domain builds
- **Prj_VBScanner.py** — file inventory regeneration only (Section 2)

### 5.4 How Config Files Are Updated

| What Changed | How |
|---|---|
| New file added/deleted | Re-run `Prj_VBScanner.py` |
| Method added to file | Re-run `Prj_VBScanner.py` |
| Domain constant changed | Edit Section 3 directly |
| Config class method added | Edit Section 4 directly |
| README updated | Edit Section 5 directly |
| Universal content found | Move to `Dom_Unified/Config.py`, import if needed |

### 5.5 Version Bumping

| Change | Bump |
|---|---|
| New file in inventory | Patch (1.0.0 → 1.0.1) |
| New constant | Patch |
| New Config method | Minor (1.0.0 → 1.1.0) |
| Section structure changed | Major (1.0.0 → 2.0.0) |
| Universal content extracted | Minor |

---

## Chapter 6 — Universal vs Domain-Specific

### 6.1 The Rule

**If a concept applies to 2 or more domains, it does NOT belong in one domain's config file.**

Universal content goes in `core/Dom_Unified/Config.py`. Domain configs import from there if needed.

### 6.2 Classification Table

| Content | Type | Lives In |
|---|---|---|
| Garmin Navigator (roads, dimensions, help) | Universal | `core/Dom_Unified/Config.py` |
| Pipeline definitions (10 roads) | Universal | `core/Piplines/Plf_*.md` |
| VBStyle rules | Universal | `core/Dom_Vsstyle/Config_Vbs_Code_Verifiation.py` |
| BCL syntax rules | Universal | `core/Dom_Bcl/Config_BCL.py` |
| MySQL connection config | Domain | each domain's own `Config.py` |
| Widget maps | Domain | `core/Dom_Gui/config.py` only |
| Signal maps | Domain | `core/Dom_Gui/config.py` only |
| Theme palettes | Domain | `core/Dom_Gui/config.py` only |
| DB paths | Domain | each domain's own `Config.py` |
| RAM bus schema | Domain | `core/Dom_Gui/config.py` only |

### 6.3 How to Detect Universal Content

Ask: "Does this describe only this domain, or the whole system?"

- "Widget maps for PyQt6" → only Dom_Gui → **domain-specific**
- "Navigator that drives every road in the codebase" → all domains → **universal**
- "BCL token syntax rules" → all domains use BCL → **universal**
- "Theme palettes (midnight, forest)" → only GUI → **domain-specific**

### 6.4 Importing Universal Content

```python
# In core/Dom_Gui/config.py
from core.Dom_Unified.Config import NAVIGATOR_CONFIG
```

Or via Config class:
```python
from core.Dom_Unified.Config import Config as UnifiedConfig
unified = UnifiedConfig()
nav = unified.Run("get_navigator_config")
```

---

## Chapter 7 — BCL Token Format

### 7.1 What Is BCL?

BCL (Bracket Command Language) is the token format used throughout the project. In config files, it is used for the file inventory (`FILE_INDEX`).

### 7.2 Token Syntax

```
[@File:name]{("field";"value")("field2";"value2")...}
```

- `[@File:name]` — container name, always `File` for file inventory
- `{...}` — container body
- `("field";"value")` — tuple, semicolon-separated
- Strings quoted with double quotes
- No trailing semicolons

### 7.3 Example

```
[@File:parser_py]{("file";"parser.py")("purpose";"Parses BCL declarations")("classes";"BCLParser")("methods";"parse,tokenize")("vbstyle";"True")("lines";"180")}
```

### 7.4 Parsing

BCL tokens are parsed by `core/Dom_Bcl/bcl_lexer.py` + `bcl_parser.py`:

```python
from core.Dom_Bcl.bcl_lexer import BCLTokenizer
from core.Dom_Bcl.bcl_parser import BCLParser
tokens = BCLTokenizer()
tokens.tokenize(text)
parser = BCLParser()
root = parser.parse(tokens.tokens)
```

### 7.5 Validation

Every BCL token in `FILE_INDEX` must be parseable by the BCL lexer. Malformed tokens fail validation.

---

## Chapter 8 — Validation

### 8.1 What Is Checked

| # | Check | How |
|---|---|---|
| 1 | BCL headers present | `[@GHOST]`, `[@VBSTYLE]`, `[@SUMMARY]`, `[@FILEID]` at top |
| 2 | File inventory complete | Every `.py` in folder has an entry |
| 3 | BCL tokens well-formed | Parseable by `bcl_lexer.py` |
| 4 | Domain constants only | No universal/cross-domain content |
| 5 | Config class exists | Has `Run()`, `read_state()`, `set_config()`, returns Tuple3 |
| 6 | VBStyle compliant | No `print()`, no decorators, no `self._`, no tabs, no hardcoded paths |
| 7 | Section order correct | Headers → Inventory → Constants → Class → README |
| 8 | py_compile passes | `python3 -m py_compile config.py` exits 0 |
| 9 | Import test passes | `from config import Config; c = Config(); c.Run("read_state")` returns `(1, ...)` |

### 8.2 Validation Commands

```bash
# Single file
python3 -m py_compile core/Dom_Gui/config.py
python3 -c "from core.Dom_Gui.config import Config; c = Config(); r = c.Run('read_state'); assert r[0] == 1"

# All config files
python3 Prj_VBScanner.py --validate-configs
```

### 8.3 Common Failures

| Failure | Cause | Fix |
|---|---|---|
| Missing headers | AI didn't add `[@GHOST]` etc. | Add Section 1 |
| Inventory incomplete | New file added, scanner not re-run | Run `Prj_VBScanner.py` |
| Universal content in domain config | AI put Garmin Navigator in `Dom_Gui` | Move to `Dom_Unified/Config.py` |
| No Config class | AI wrote flat constants only | Add Section 4 class |
| VBStyle violation | `print()`, `self._`, decorators | Remove violations |
| Wrong section order | README before constants | Reorder to standard |

---

## Chapter 9 — Current Config Audit

### 9.1 Status Table

| Config File | Headers | Inventory | BCL Tokens | Config Class | Universal Leaked | Status |
|---|---|---|---|---|---|---|
| `Config.py` (root) | GHOST + VBSTYLE | FILE_INDEX | Yes | Config class | No | **GOLD** |
| `Config_BCL.py` | GHOST + VBSTYLE | FILES + CLASSES | No | No | No | Partial |
| `Dom_Graph/Config.py` | GHOST + VBSTYLE + REVIEW | No | No | Claimed, missing | No | Partial |
| `core/Dom_Gui/config.py` | GHOST + VBSTYLE + SUMMARY | No | No | No | YES (Garmin) | **FAIL** |
| `Dom_DecisionTrees/Config.py` | None | DESCRIPTIONS (partial) | No | No | No | **FAIL** |
| `gui_engine/Config.py` | Unknown | Unknown | Unknown | Unknown | Unknown | Audit needed |

### 9.2 Fix Priority

| Priority | File | Issue | Fix |
|---|---|---|---|
| P0 | `core/Dom_Gui/config.py` | Garmin Navigator leaked in | Move to `Dom_Unified/Config.py`, add inventory, add Config class |
| P1 | `Dom_DecisionTrees/Config.py` | No headers, no BCL, no class | Add all 5 sections |
| P1 | `Dom_Graph/Config.py` | Claims class but body is flat | Implement Config class, add inventory |
| P2 | `core/Dom_Bcl/Config_BCL.py` | Has FILES but no BCL tokens, no class | Add BCL token format, add Config class |
| P2 | `gui_engine/Config.py` | Unknown status | Audit and fix |
| P3 | All other `Config*.py` files | Audit each | Fix as needed |

---

## Chapter 10 — Pipeline Stages

```
Stage 1: AUDIT     — Scan all Config*.py files, compare against standard
Stage 2: EXTRACT   — Move universal content to universal location
Stage 3: INVENTORY — Generate BCL file inventory for each domain
Stage 4: CLASS     — Add Config class with Run() dispatch
Stage 5: HEADERS   — Ensure all BCL headers present and correct
Stage 6: VALIDATE  — Run all validation checks
Stage 7: VERIFY    — py_compile + import test
```

### Stage 1: Audit

Scan every `Config*.py` file. For each, check: headers present? inventory complete? Config class exists? universal content leaked? VBStyle followed?

Output: `config_audit_report.json` with pass/fail per file per check.

### Stage 2: Extract Universal Content

Move cross-domain content out of domain configs:
- Garmin Navigator → `core/Dom_Unified/Config.py`
- Any other universal concepts → same location
- Domain configs import from universal if needed

### Stage 3: Inventory Generation

```bash
python3 Prj_VBScanner.py core/Dom_Gui --append-only
```

Scanner walks folder, parses AST, extracts metadata, generates BCL tokens.

### Stage 4: Config Class

Add standard Config class to each config file with `Run()` dispatch, `read_state()`, `set_config()`, Tuple3 returns.

### Stage 5: Headers

Ensure all 4 headers present and correct:
```python
#[@GHOST]{[@file<Config.py>][@domain<DomainName>]...}
#[@VBSTYLE]{[@auth<system>][@role<domain_config>]...}
#[@SUMMARY]{One-line description}
#[@FILEID]{[@file<Config.py>][@domain<DomainName>]...}
```

### Stage 6: Validate

Run all 9 checks from Chapter 8. Output pass/fail report.

### Stage 7: Verify

```bash
python3 -m py_compile core/Dom_Gui/config.py
python3 -c "from core.Dom_Gui.config import Config; c = Config(); print(c.Run('read_state'))"
```

---

## Glossary

| Term | Definition |
|---|---|
| **BCL** | Bracket Command Language. Token format: `[@name]{("field";"value")}` |
| **BCL Headers** | `[@GHOST]`, `[@VBSTYLE]`, `[@SUMMARY]`, `[@FILEID]` at top of file |
| **Config Class** | VBStyle-compliant class with `Run()` dispatch providing programmatic access |
| **Domain** | A folder containing related code (e.g. `Dom_Gui`, `Dom_Bcl`, `Dom_Graph`) |
| **Domain-Specific** | Content that only applies to one domain |
| **FILE_INDEX** | List of BCL token strings indexing every `.py` file in a domain |
| **FILES Dict** | Alternative human-readable file inventory format |
| **Garmin Navigator** | Universal graph exploration engine — navigates all domains, all pipelines |
| **GHOST Header** | Identity stamp: file, domain, role, author, date, version |
| **Gold Standard** | The `Config.py` in project root — the reference implementation |
| **Prj_VBScanner.py** | Tool that auto-generates file inventory by scanning `.py` files |
| **Section Order** | Headers → Inventory → Constants → Class → README (mandatory order) |
| **Tuple3** | Return format: `(1, data, None)` for success, `(0, None, (code, desc, 0))` for failure |
| **Universal** | Content that applies to 2+ domains — lives in `core/Dom_Unified/Config.py` |
| **VBSTYLE Header** | Compliance flags: return type, orchestration, prohibitions |
| **VBStyle** | Coding standard: Run() dispatch, Tuple3, no print, no decorators, no self._, PascalCase, UPPERCASE |

---

## Reference Config Files

| File | Location | Role |
|---|---|---|
| Gold Standard | `Config.py` (root) | Reference for FILE_INDEX BCL token format |
| BCL Reference | `core/Dom_Bcl/Config_BCL.py` | Reference for FILES + CLASSES dict format |
| VBStyle Rules | `core/Dom_Vsstyle/Config_Vbs_Code_Verifiation.py` | VBStyle compliance rules |
| This Manual | `core/Piplines/Plf_ConfigFiles.md` | The standard itself |
