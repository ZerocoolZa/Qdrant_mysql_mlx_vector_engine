# BCL Template Maker Pipeline — Header Editor → Stamp → Capsule

> **Core thesis:** Files without identity don't exist. The BCL Template Maker
> is the tool that generates, edits, and stamps BCL headers onto files.
> It makes the bracket templates that become file identities.
> Every file gets: `[@GHOST]`, `[@VBSTYLE]`, `[@FILEID]`, `[@SUMMARY]`,
> `[@CLASS]`, `[@METHOD]` — the complete identity block.

---

## Pipeline Overview

```
File (no header)
       ↓
  BCL Header Editor (PyQt6 GUI)
       ↓
  Select Template → Fill Fields (file_path, identity, purpose, date, author, session_id)
       ↓
  Generate BCL Header Block
       ↓
  Preview (live syntax highlighting)
       ↓
  Save → bcl_header.txt (template file)
       ↓
  Stamp Engine → Inject header into .py files
       ↓
  Capsule Builder → Build self-contained archive
       ↓
  Verify → Check all files carry identity
```

---

## Stages

### Stage 1: BCL HEADER EDITOR — Template Maker GUI

**Tool:** `/Users/wws/Downloads/file_header_preview.py` (`BCLEditor` class)

A PyQt6 GUI application with:

- **Code editor** with line numbers and BCL syntax highlighting
- **Template buttons** — one-click insert of BCL bracket templates:
  - `#[@GHOST]` — file identity (file_path, identity, purpose, date, version, author, chat_link)
  - `#[@VBSTYLE]` — VBStyle compliance (auth, role, return, orch, no, model)
  - `#[@CLASS]` — class metadata (class, domain, authority)
  - `#[@METHOD]` — method metadata (method, type)
  - `#[@FILEID]` — file ID (session_id, context, purpose)
  - `#[@SUMMARY]` — session summary

- **Template format:**
```python
TEMPLATES = {
    "ghost":   '#[@GHOST]{("";"";"";"";"";"";"")}',
    "vbstyle": '#[@VBSTYLE]{("";"";"";"";"";"")}',
    "class":   '#[@CLASS]{("";"";"";"")}',
    "method":  '#[@METHOD]{("";"";"")}',
    "fileid":  '#[@FILEID]{("";"";"")}',
    "summary": '#[@SUMMARY]{("")}',
}
```

- **BCL syntax highlighter** (`BCLHighlighter` class):
  - Highlights `[@TOKEN]` brackets
  - Highlights `("key";"value")` tuples
  - Highlights `#` comments
  - Highlights Python keywords inside BCL blocks
  - Highlights docstrings

- **Live reload** — watches `bcl_header.txt` for changes, auto-reloads
- **Save** — writes the edited header to `bcl_header.txt` for use by stampers

### Stage 2: BCL HEADER TEMPLATE — The Blank Form

**Tool:** `/Users/wws/Downloads/bcl_header.txt`

The saved template from the editor. This is the blank BCL header that gets
stamped onto files. It contains the structure with empty fields:

```python
"""
#[@GHOST]{("file_path=";"identity=";"purpose=";"date=2026-06-26";"version=1.0";"author=Cascade";"chat_link=mysql://devin/devin_chat_turns?session_id=")}
#[@VBSTYLE]{("auth=Cascade";"role=domain";"return=Tuple3";"orch=none";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete")}
#[@FILEID]{("session_id=";"context=";"purpose=")}
#[@SUMMARY]{("")}
"""
```

### Stage 3: STAMP ENGINE — Inject Headers into Files

**Tool:** `/Users/wws/Downloads/stamp_and_capsule.py`

Stamps BCL headers onto all `.py` files:

1. **Scan** — find all `.py` files in target directory
2. **Check** — `has_bcl_header(filepath)` — does file already have `#[@GHOST]`?
3. **Extract** — `extract_description(filepath)` — get first docstring or comment
4. **Generate** — `make_bcl_header(filepath, description)` — fill template with file-specific data
5. **Inject** — prepend the BCL header to the file content
6. **Write** — save the stamped file

**File types stamped:** `.py`, `.sql`, `.md`, `.txt`, `.json`, `.yaml`, `.yml`, `.c`, `.sh`

### Stage 4: CAPSULE BUILDER — Self-Contained Archive

**Tool:** `/Users/wws/Downloads/capsule_builder.py`

Builds a self-contained capsule from a chat session:

1. **Load BCL header template** from `bcl_header.txt` (saved by the editor)
2. **Scan chat for file references** — regex finds all `/Users/.../*.py` paths
3. **For each file:**
   - Check if file has BCL header → if not, stamp it
   - Extract description (first docstring or comment)
   - Read file content
   - Compress content with zlib
   - Base64 encode for embedding in markdown
4. **Build capsule markdown:**
   - Session metadata (name, ID, date)
   - File inventory (path, identity, description, size)
   - Compressed code blocks per file
   - Statistics (file count, total size, compressed size)

### Stage 5: VBSTYLE VERIFICATION — Check All Files Carry Identity

**Tools:** `core/Dom_Vsstyle/vbs_rule_enforcer.py`, `core/Dom_Vsstyle/vbs_compliance.py`

After stamping, verify every file carries its identity:

**Compliance checks per file:**
- `ghost_header` — `#[@GHOST]` present
- `vbstyle_header` — `#[@VBSTYLE]` present
- `tuple3_return` — methods return Tuple3
- `state_dict` — `self.state = {}` present
- `pascal_case` — class names PascalCase
- `uppercase_constants` — constants UPPERCASE
- `no_print` — no print() calls
- `no_decorators` — no @property/@staticmethod/@classmethod
- `no_self_underscore` — no self._xxx
- `no_tabs` — spaces only
- `has_run` — Run() dispatch exists

**Rule enforcer operations:**
- `scan_file` — scan single file
- `scan_folder` — scan all .py files in directory
- `auto_fix` — automatically fix safe violations
- `check_vbstyle` — full compliance check

### Stage 6: RULE TOKEN GENERATION — Canonical Rule Storage

**Tools:** `core/Dom_Vsstyle/vbs_rule_engine.py`, `core/Dom_Vsstyle/vbs_rule_writer.py`

The BCL templates are themselves governed by rules stored as BCL tokens:

- **Source:** `.md` files (obey.md, vbstyle_rules.md, config_file_rule.md)
- **Canonical store:** MySQL `vb_shared.rule_tokens` (238 tokens)
- **Format:** `name=[@ConceptName]`, `bracket_body=("detail...";92)`
- **Categories:** Architecture, State, Method, Forbidden, Format, Naming, Paths, Database, FileOps, Workflow, Meta, Other
- **Meta-tokens:** `[@MetaOneConcept]`, `[@MetaCheckFirst]`, `[@MetaNoDupBody]`, `[@MetaGroupDomain]`, `[@MetaNameIsConcept]`, `[@MetaNoPrefix]`

**Rule engine operations:**
- Extract rules from .md files
- Load canonical tokens from MySQL
- Analyse gap/duplicate/conflict
- Create tokens (dedup-gated, dry_run default, commit=True to execute)
- Search, propose, edit, fix

### Stage 7: RULE VISUALIZATION — Graphs from Rule Tokens

**Tools:** `core/Dom_Vsstyle/vbs_rule_cluster_graph.py`, `vbs_rule_coverage_graph.py`, `vbs_rule_gap_graph.py`

Three graph views of the rule token space:

| Graph | What It Shows |
|---|---|
| **Cluster Graph** | Tokens grouped by shared keywords — concept proximity clusters |
| **Coverage Graph** | Bipartite: 185 .md rules (left) vs 238 canonical tokens (right). Green=covered, orange=weak, red=missing |
| **Gap Graph** | Only weak/missing rules with their closest token match — actionable view |

---

## The BCL Header Fields (Complete Identity)

Every file that goes through the template maker gets these fields:

### `[@GHOST]` — File Identity
| Field | Purpose |
|---|---|
| `file_path` | Absolute path to the file |
| `identity` | Human-readable name (e.g. "BCL Header Editor") |
| `purpose` | What the file does (one sentence) |
| `date` | Creation date (YYYY-MM-DD) |
| `version` | Version number |
| `author` | Who created it (Cascade, Devin, etc.) |
| `chat_link` | MySQL link to the session that created it |

### `[@VBSTYLE]` — Compliance Declaration
| Field | Purpose |
|---|---|
| `auth` | Author identity |
| `role` | File role (domain, tool, gui, domain_gui, etc.) |
| `return` | Return type (Tuple3) |
| `orch` | Orchestration mode (none, memunit, etc.) |
| `no` | What's forbidden (no_decorators, no_print, no_hardcoded) |
| `model` | Architecture model (one_class_one_domain_one_authority_complete) |

### `[@FILEID]` — Session Context
| Field | Purpose |
|---|---|
| `session_id` | Devin session ID (e.g. "mirror-theory") |
| `context` | Session name (e.g. "Windsurf Decryption + ChatGPT Export") |
| `purpose` | This file's purpose within the session |

### `[@SUMMARY]` — Session Summary
| Field | Purpose |
|---|---|
| (single value) | What happened in the session that created this file |

### `[@CLASS]` — Class Metadata (optional, for class files)
| Field | Purpose |
|---|---|
| `class` | Class name |
| `domain` | Domain name |
| `authority` | Authority level (single, shared, etc.) |

### `[@METHOD]` — Method Metadata (optional, for method documentation)
| Field | Purpose |
|---|---|
| `method` | Method name |
| `type` | Method type (dispatch, command, query, helper, ctor, etc.) |

---

## File Locations

```
BCL TEMPLATE MAKER PIPELINE FILES:
├── /Users/wws/Downloads/
│   ├── file_header_preview.py             — BCL Header Editor (PyQt6 GUI, template maker)
│   ├── bcl_header.txt                     — Saved BCL header template (blank form)
│   ├── stamp_and_capsule.py               — Stamp headers on all .py files + build capsule
│   ├── capsule_builder.py                 — Build self-contained session capsule
│   └── session_capsule.md                 — Example capsule output
│
├── core/Dom_Vsstyle/                      — VBStyle verification domain
│   ├── vbs_parser.py                      — Parse BCL headers from files
│   ├── vbs_compliance.py                  — Check VBStyle compliance
│   ├── vbs_rule_enforcer.py               — Scan + auto-fix violations
│   ├── vbs_rule_engine.py                 — Rule token authority (238 tokens)
│   ├── vbs_rule_reader.py                 — Read rules from .md files
│   ├── vbs_rule_writer.py                 — Write rule tokens to MySQL
│   ├── vbs_rule_cluster_graph.py          — Cluster graph (tokens by shared keywords)
│   ├── vbs_rule_coverage_graph.py         — Coverage graph (rules vs tokens)
│   ├── vbs_rule_gap_graph.py              — Gap graph (missing/weak rules)
│   ├── vbs_code_index.py                  — MySQL code_index CRUD
│   ├── vbs_registry.py                    — Format + output registry
│   └── vbs_main.py                        — Orchestrator entry point
│
├── core/Dom_Bcl/
│   ├── BclGenerator.py                    — AST → FeatureMap → RuleEngine → BCL header
│   ├── BclStampBuilder.py                 — Build BCL stamps from reasoning
│   └── BclStampStore.py                   — CRUD for BCL stamps
│
└── MySQL vb_shared:
    └── rule_tokens (238 tokens)           — Canonical BCL rule tokens
```

---

## Current Status

| Component | Status | Data |
|---|---|---|
| BCL Header Editor (PyQt6 GUI) | **DONE** | — |
| Template buttons (6 types) | **DONE** | GHOST, VBSTYLE, CLASS, METHOD, FILEID, SUMMARY |
| BCL syntax highlighter | **DONE** | — |
| Live reload | **DONE** | — |
| bcl_header.txt (template file) | **DONE** | — |
| Stamp engine (inject headers) | **DONE** | — |
| Capsule builder | **DONE** | — |
| VBStyle compliance checking | **DONE** | 12+ checks |
| VBStyle rule enforcement | **DONE** | scan + auto-fix |
| Rule token engine (238 tokens) | **DONE** | — |
| Rule cluster graph | **DONE** | — |
| Rule coverage graph | **DONE** | — |
| Rule gap graph | **DONE** | — |
| BclGenerator (AST → BCL header) | **DONE** | — |
| BclStampBuilder (reasoning stamps) | **DONE** | — |
| BclStampStore (stamp CRUD) | **DONE** | — |
| All .py files carry identity | **MOSTLY DONE** | Some files may still lack headers |
