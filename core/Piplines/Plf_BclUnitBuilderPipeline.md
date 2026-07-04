# BCL Unit Builder Pipeline — Spec → Generate → Check → Compile → Register

> **Core thesis:** AI sends a BCL spec, the builder writes a complete `.c` BCL unit file,
> checks VBStyle compliance, compiles it, and registers it in the tool stack.
> New capability = new `.c` file. Exponentially growable — just add `.c` files.
>
> **Merged:** This pipeline doc now contains the full unit registry (28 units),
> detailed specs for all 12 new units (with DIM blocks, command tables, BCL packet formats),
> build order, registration order, and architecture diagram.

---

## Folder Layout

```
Cascade_toolStack/
├── bin_tools/
│   └── bcl_builder.c          ← The builder CLI (Devin built this, 590 lines)
├── bcl_units/
│   ├── bcl_toolstack.h         ← Shared header (unit interface, BCL parser, constants)
│   ├── bcl_tool_main.c         ← Single entry point (registers all units, CLI dispatch)
│   ├── bcl_pb_reader.c         ← Complete unit (AES-GCM decrypt, protobuf, SQLite)
│   ├── bcl_file_io.c           ← NOT BUILT — file operations unit
│   ├── bcl_mem_unit.c          ← NOT BUILT — in-RAM SQLite orchestration bus
│   ├── bcl_report.c            ← NOT BUILT — report generator from MemUnit
│   ├── bcl_db_manager.c        ← NOT BUILT — database manager
│   ├── bcl_config.c            ← NOT BUILT — config manager
│   ├── bcl_executor.c          ← NOT BUILT — command executor
│   ├── bcl_graph_engine.c      ← NOT BUILT — code graph engine
│   ├── bcl_parser_unit.c       ← NOT BUILT — BCL parser unit
│   ├── bcl_stamper_unit.c      ← NOT BUILT — BCL stamper unit
│   ├── bcl_validator_unit.c    ← NOT BUILT — validator unit
│   ├── bcl_builder_unit.c      ← NOT BUILT — builder unit (port from bin_tools)
│   ├── bcl_dictionary_unit.c   ← NOT BUILT — dictionary unit
│   ├── bcl_pb_reader.c         ← COMPLETE — AES-GCM decrypt, protobuf, SQLite
│   ├── bcl_chat_ingest.c       ← STUB — needs implementation
│   ├── bcl_cleaner.c           ← STUB — needs implementation
│   ├── bcl_msearch.c           ← STUB — needs implementation
│   ├── bcl_mdmerge.c           ← STUB — needs implementation
│   ├── bcl_discovery.c         ← STUB — needs implementation
│   ├── bcl_schemalint.c        ← STUB — needs implementation
│   ├── bcl_vbcheck.c           ← STUB — needs implementation
│   ├── bcl_ghostctl.c          ← STUB — needs implementation
│   ├── bcl_smartcli.c          ← STUB — needs implementation
│   ├── bcl_wcmd.c              ← STUB — needs implementation
│   ├── bcl_magnetic.c          ← STUB — needs implementation
│   ├── bcl_codeingest.c        ← STUB — needs implementation
│   ├── bcl_cognitive_core.c    ← STUB — needs implementation
│   ├── bcl_error_fix.c         ← STUB — needs implementation
│   ├── bcl_windir.c            ← STUB — needs implementation
│   ├── BCL_UNIT_SPEC.md        ← How to build BCL units (template, DIM block, protocol)
│   └── Makefile                ← Build system
└── vbast/                      ← Predecessor code (stamped as BCL units, function libraries)
    ├── vbast.h
    ├── ast_walker.c
    ├── bcl_stamper.c
    ├── graph_builder.c
    ├── vbstyle_check.c
    ├── mysql_store.c
    └── vbast.c

core/Dom_Bcl_C_ver/             ← Evolved C code (some have Run dispatch, most don't)
    ├── bcl_engine.h            ← Shared header (BCL parser, dictionary, validator, MemUnit)
    ├── bcl_dictionary.c        ← HAS Run dispatch (BclDictionary_Run)
    ├── bcl_mem_unit.c          ← HAS Dispatch (MemUnit_Dispatch) — port source for bcl_units/
    ├── bcl_parser.c            ← Function library — no Run dispatch
    ├── bcl_validator.c         ← Function library — no Run dispatch
    ├── bcl_config.c            ← Function library — no Run dispatch
    ├── bcl_stamper.c           ← Function library — no Run dispatch
    ├── bcl_graph_builder.c     ← Function library — no Run dispatch
    ├── bcl_graph_store.c       ← Function library — no Run dispatch
    ├── bcl_static_analyzer.c   ← Function library — no Run dispatch
    ├── bcl_ingestion_engine.c  ← Function library — no Run dispatch
    └── bcl_engine_cli.c        ← CLI tool — has main()

Cascade_toolStack/bin_tools/
    └── bcl_builder.c           ← The builder CLI (Devin built this, 590 lines)
```

---

## Build Status — What's Already Built vs What's Still Building

### Already Built (GREEN)

| Component | Location | Status | Notes |
|---|---|---|---|
| `bcl_builder.c` | `bin_tools/` | **COMPLETE** | 590 lines, generates .c files from BCL spec, auto-checks, auto-compiles |
| `bcl_toolstack.h` | `bcl_units/` | **COMPLETE** | Shared header, unit interface, BCL parser, constants |
| `bcl_tool_main.c` | `bcl_units/` | **COMPLETE** | Entry point, registers 17 units, CLI dispatch |
| `bcl_pb_reader.c` | `bcl_units/` | **COMPLETE** | AES-256-GCM decrypt, protobuf parse, in-RAM SQLite |
| `Makefile` | `bcl_units/` | **COMPLETE** | Build system for all units |
| `bcl_dictionary.c` | `core/Dom_Bcl_C_ver/` | **HAS Run** | BclDictionary_Run dispatch — needs port to bcl_units/ |
| `bcl_mem_unit.c` | `core/Dom_Bcl_C_ver/` | **HAS Dispatch** | MemUnit_Dispatch — needs port to bcl_units/ |

### Stub Units (YELLOW — generated but not implemented)

| Unit | File | Commands Needed |
|---|---|---|
| `chat_ingest` | `bcl_chat_ingest.c` | ingest, parse, index |
| `cleaner` | `bcl_cleaner.c` | clean, purge, scan |
| `msearch` | `bcl_msearch.c` | search, index, query |
| `mdmerge` | `bcl_mdmerge.c` | merge, split, list |
| `discovery` | `bcl_discovery.c` | scan, analyze, report |
| `schemalint` | `bcl_schemalint.c` | lint, check, fix |
| `vbcheck` | `bcl_vbcheck.c` | check, report, fix |
| `ghostctl` | `bcl_ghostctl.c` | stamp, verify, list |
| `smartcli` | `bcl_smartcli.c` | run, history, dry_run |
| `wcmd` | `bcl_wcmd.c` | exec, list, kill |
| `magnetic` | `bcl_magnetic.c` | search, radius, list |
| `codeingest` | `bcl_codeingest.c` | ingest, parse, store |
| `cognitive` | `bcl_cognitive_core.c` | think, reason, learn |
| `error_fix` | `bcl_error_fix.c` | analyze, fix, learn |
| `windir` | `bcl_windir.c` | list, tree, search |

### Not Built Yet (RED — need to be generated and implemented)

| Unit | Category | Source | Priority |
|---|---|---|---|
| `bcl_mem_unit.c` | orchestration | port from `core/Dom_Bcl_C_ver/bcl_mem_unit.c` | HIGH |
| `bcl_file_io.c` | io | build from scratch | HIGH |
| `bcl_config.c` | config | port from `core/Dom_Bcl_C_ver/bcl_config.c` | HIGH |
| `bcl_db_manager.c` | database | port from Python + C sources | HIGH |
| `bcl_parser_unit.c` | bcl | port from `core/Dom_Bcl_C_ver/bcl_parser.c` | MEDIUM |
| `bcl_dictionary_unit.c` | bcl | port from `core/Dom_Bcl_C_ver/bcl_dictionary.c` | MEDIUM |
| `bcl_stamper_unit.c` | bcl | port from `core/Dom_Bcl_C_ver/bcl_stamper.c` | MEDIUM |
| `bcl_validator_unit.c` | bcl | port from `core/Dom_Bcl_C_ver/bcl_validator.c` | MEDIUM |
| `bcl_builder_unit.c` | bcl | port from `bin_tools/bcl_builder.c` | MEDIUM |
| `bcl_report.c` | reporting | build from scratch | MEDIUM |
| `bcl_executor.c` | exec | port from `bin_tools/cascade_cli.c` | MEDIUM |
| `bcl_graph_engine.c` | graph | port from `core/Dom_Bcl_C_ver/bcl_graph_builder.c` | LOW |

---

## What is a BCL Unit?

A BCL unit is a C file that:
1. Has `[@GHOST]` / `[@VBSTYLE]` / `[@FILEID]` identity headers
2. Accepts BCL packets as input: `[@RUN]{[@CMD]{scan}[@PARAM]{...}}`
3. Returns BCL packets as output: `[@OK]{[@RESULT]{...}}` or `[@ERR]{[@CODE]{3}[@DESC]{...}}`
4. Has a Run dispatch function — every unit shares the same signature
5. Uses the DIM block pattern for variable declarations (VB `Dim` style)

**BCL in, BCL out.** No Tuple3 structs. No Param pointers. No typed function arguments.
The BCL string IS the interface. Every unit is interchangeable.

Without Run dispatch + BCL I/O, it's just a function library with a name tag — not a BCL unit.

---

## BCL Packet Protocol

### Input Packet (sent to unit)

```
[@RUN]{[@CMD]{command_name}[@PARAM]{[@KEY1]{value1}[@KEY2]{value2}}}
```

- `[@CMD]` — the command to execute (maps to enum → dispatch table)
- `[@PARAM]` — nested BCL containing key-value pairs for the command

### Success Packet (returned by unit)

```
[@OK]{[@RESULT]{[@COUNT]{161}[@FILES]{file1.pb,file2.pb}}}
```

- `[@OK]` — signals success
- `[@RESULT]` — nested BCL containing the result data

### Error Packet (returned by unit)

```
[@ERR]{[@CODE]{3}[@DESC]{db query failed}}
```

- `[@ERR]` — signals failure
- `[@CODE]` — numeric error code
- `[@DESC]` — human-readable description

### Universal Interface

Every unit has the same signature:
```c
const char *Unit_Run(Unit *u, Command cmd, const char *bcl_in);
```

All units are interchangeable. Any unit can call any other unit by passing BCL.
No struct casting. No type mismatches. BCL in, BCL out.

---

## Version Evolution (V1 → V5)

| Aspect | V1 (strings) | V2 (enum+fn ptr) | V4 (grouped) | V5 (BCL) |
|---|---|---|---|---|
| VBStyle pure | no | partial | yes | **yes** |
| Uniform interface | no | no | no | **yes — all units identical** |
| Dispatch speed | slow (strcmp) | fast (jump table) | fast (jump table) | fast (jump table) |
| Type safety | none | good | good | none (BCL is text) |
| Interoperability | none | none | none | **yes — any unit calls any unit** |
| Serialization | manual | manual | manual | **built-in (BCL is already serialized)** |
| Debugging | easy | easy | easy | **easy (read the BCL string)** |
| Memory | low | low | low | **lowest (no structs, just strings)** |

**V5 (BCL in, BCL out) is the canonical standard.**

---

## The Complete Unit Template

```c
// [@GHOST]{file_path="UNIT.c" date="DATE" author="AUTHOR" context="CONTEXT"}
// [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE BCL-in BCL-out Run dispatch"}
// [@FILEID]{id="UNIT.c" domain="DOMAIN" authority="AUTHORITY"}
// [@SUMMARY]{summary="SUMMARY"}
// [@CLASS]{class="AUTHORITY" domain="DOMAIN" authority="single"}
// [@METHOD]{method="Run" type="dispatch"}
// [@METHOD]{method="read_state" type="command"}
// [@METHOD]{method="set_config" type="command"}

#include "bcl_toolstack.h"
#include <sqlite3.h>
#include <string.h>
#include <stdlib.h>

/* ===== DIM BLOCK (declarations) ===== */

#define MAX_PATH 4096, MAX_BCL 65536;
typedef enum { CMD_READ_STATE = 0, CMD_SET_CONFIG, CMD_COUNT } Command;
typedef struct { char db_path[MAX_PATH]; sqlite3 *conn; int initialized; } Unit;
typedef const char *(*CmdFn)(Unit *, const char *bcl_in);

/* ===== INIT BLOCK (constructors + helpers) ===== */

static const char *OK(const char *bcl_result) { return bcl_result; }
static const char *ERR(int code, const char *desc) {
    static char err_buf[512];
    snprintf(err_buf, sizeof(err_buf), "[@ERR]{[@CODE]{%d}[@DESC]{%s}}", code, desc);
    return err_buf;
}

/* ===== FORWARD BLOCK (prototypes) ===== */

static const char *fn_read_state(Unit *u, const char *bcl_in);
static const char *fn_set_config(Unit *u, const char *bcl_in);

/* ===== DISPATCH BLOCK (jump table + entry) ===== */

static const CmdFn DISPATCH[CMD_COUNT] = { fn_read_state, fn_set_config };

void Unit_Init(Unit *u, const char *db_path) {
    memset(u, 0, sizeof(*u));
    strncpy(u->db_path, db_path, MAX_PATH - 1);
    u->initialized = 1;
}

/* accepts BCL → returns BCL */
const char *Unit_Run(Unit *u, Command cmd, const char *bcl_in) {
    if (cmd < 0 || cmd >= CMD_COUNT) return ERR(1, "unknown_command");
    return DISPATCH[cmd](u, bcl_in);
}

/* ===== GUTS BLOCK (implementation) ===== */

/* accepts BCL → returns BCL */
static const char *fn_read_state(Unit *u, const char *bcl_in) {
    /* in:  [@RUN]{[@CMD]{read_state}} */
    /* out: [@OK]{[@STATE]{[@DB_PATH]{...}[@INIT]{1}}} */
    static char buf[1024];
    snprintf(buf, sizeof(buf), "[@OK]{[@STATE]{[@DB_PATH]{%s}[@INIT]{%d}}}",
             u->db_path, u->initialized);
    return OK(buf);
}

/* accepts BCL → returns BCL */
static const char *fn_set_config(Unit *u, const char *bcl_in) {
    /* in:  [@RUN]{[@CMD]{set_config}[@PARAM]{[@DB_PATH]{/new/path}}} */
    /* out: [@OK]{[@CONFIG]{[@DB_PATH]{/new/path}}} */
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char path[MAX_PATH] = {0};
    BclParser_Extract(&parse, "DB_PATH", path, sizeof(path));
    BclParser_Free(&parse);
    if (path[0]) strncpy(u->db_path, path, MAX_PATH - 1);
    static char buf[1024];
    snprintf(buf, sizeof(buf), "[@OK]{[@CONFIG]{[@DB_PATH]{%s}}}", u->db_path);
    return OK(buf);
}
```

---

## MemUnit API (C Function Signatures)

```c
void   MemUnit_Init(MemUnit *mu);
void   MemUnit_Close(MemUnit *mu);
int    MemUnit_Dispatch(MemUnit *mu, const char *target_unit,
                        const char *command, const char *bcl_in,
                        char *bcl_out, size_t out_sz);
int    MemUnit_RegisterCommand(MemUnit *mu, const char *cmd_key,
                               const char *target_unit, const char *help_text,
                               const char *category, int requires_param,
                               const char *param_example);
int    MemUnit_SetState(MemUnit *mu, const char *key, const char *value);
const char * MemUnit_GetState(MemUnit *mu, const char *key);
int    MemUnit_LogError(MemUnit *mu, int command_id, int error_code,
                        const char *error_desc, ...);
```

---

## BCL Chat Compression Integration

The PB Chat Reader pipeline integrates with the BCL Chat Compression pipeline:

```
.pb files (encrypted)
    │
    ▼
1. PB Reader (decrypt + parse + in-RAM SQLite)
    │
    ▼
2. BCL Chat Compressor (Stage 1: code extraction)
    │  4,304 lines → 878 tokens in milliseconds
    │  Extracts: [@USER_SAYS], [@AI_SAYS], [@ERROR], [@FILE],
    │            [@COMMAND_RAN], [@FRUSTRATION_SIGNAL], [@QUESTION], [@TOPIC]
    │
    ▼
3. AI Semantic Pass (Stage 2: AI reasoning)
    │  Reads 878 tokens (not 4,304 lines)
    │  Extracts: [@PROBLEM], [@SOLUTION], [@ROOT_CAUSE], [@LESSON],
    │            [@DECISION], [@INTENT], [@MOOD], [@SUCCESS], [@FAILED]
    │
    ▼
4. BCL Token Store (compressed, searchable, attached to source)
    │  [@CHATSOURCE] links back to original .pb file
    │  ~200 tokens fit in AI context window
    │
    ▼
5. Search/Recall (msearch, Qdrant, or BCL query)
```

### Token Vocabulary (Stage 1 — Code Extraction)

| Token | Source | Method |
|---|---|---|
| `[@USER_SAYS]` | User messages | Header matching |
| `[@AI_SAYS]` | AI messages | Header matching |
| `[@ERROR]` | Errors | Regex: Error, TypeError, Traceback, FAILED |
| `[@FILE]` | File paths | Regex: `[\w/]+\.\w+` |
| `[@COMMAND_RAN]` | Shell commands | Code block matching |
| `[@FRUSTRATION_SIGNAL]` | User mood | Keyword dict: stuck, frozen, why, weird |
| `[@QUESTION]` | Questions | `?` detection |
| `[@TOPIC]` | Section headers | Heading detection |

### Token Vocabulary (Stage 2 — AI Semantic)

| Token | Meaning |
|---|---|
| `[@PROBLEM]` | What went wrong |
| `[@SOLUTION]` | How it was fixed |
| `[@ROOT_CAUSE]` | Why it happened |
| `[@LESSON]` | What to remember |
| `[@DECISION]` | Architecture/Design choice |
| `[@INTENT]` | What the user wanted |
| `[@MOOD]` | User emotional state |
| `[@SUCCESS]` | What worked |
| `[@FAILED]` | What didn't work |
| `[@USER_PREF]` | User preference learned |

### Attachment Concept

The compressed BCL file attaches to the source via `[@CHATSOURCE]`:

```
[@CHATSOURCE]{
    path="/Users/wws/.codeium/windsurf/cascade/a1f36eb2.pb";
    lines=3670;
    md5=63ff77a27e57;
    date="2026-06-29"
}
```

The BCL file is the **index**. The source chat is the **full text**.
AI reads the index first, drills down only when needed.

---

## Pipeline Overview

```
AI (or human) writes BCL spec
       ↓
  bcl_builder "[@MAKE]{[@FILE]{name.c}[@DOMAIN]{dom}[@AUTHORITY]{Auth}[@SUMMARY]{desc}[@METHODS]{m1,m2,m3}[@INCLUDES]{lib.h}}"
       ↓
  Parse BCL spec → extract fields (FILE, DOMAIN, AUTHORITY, SUMMARY, METHODS, INCLUDES)
       ↓
  Generate .c file with:
    ├── @GHOST / @VBSTYLE / @FILEID / @SUMMARY / @CLASS / @METHOD headers
    ├── Includes (stdio, stdlib, string + spec includes)
    ├── DIM block (constants, Command enum, Unit struct, CmdFn typedef)
    ├── INIT block (bcl_ok, bcl_err helpers)
    ├── FORWARD block (prototypes for all methods)
    ├── DISPATCH block (jump table + Init + Run)
    ├── GUTS block (method stubs with BCL in/out comments)
    └── Standalone #ifdef main for testing
       ↓
  Auto-check compliance (9-point checklist)
       ↓
  Auto-compile test (cc -DBCL_UNIT_STANDALONE)
       ↓
  Return: [@OK]{[@FILE]{...}[@LINES]{N}[@COMPILE]{1}[@CHECK]{PASS}}
       ↓
  AI fills in method implementations (the GUTS block)
       ↓
  Re-check + re-compile
       ↓
  Register in bcl_tool_main.c + Makefile
       ↓
  make && make test
```

---

## BCL Spec Format

The builder accepts BCL spec as a CLI argument or from a file:

```
[@MAKE]{
    [@FILE]{bcl_scanner.c}
    [@DOMAIN]{scanner}
    [@AUTHORITY]{Scanner}
    [@SUMMARY]{Scans files for patterns}
    [@METHODS]{scan,list,read,search}
    [@INCLUDES]{sqlite3.h,openssl/sha.h}
}
```

| Field | Required | Description |
|---|---|---|
| `[@FILE]` | yes | Output filename (e.g. `bcl_scanner.c`) |
| `[@DOMAIN]` | yes | Domain name (e.g. `scanner`, `chat`, `io`) |
| `[@AUTHORITY]` | yes | Class name / authority (e.g. `Scanner`, `PbReader`) |
| `[@SUMMARY]` | no | One-line description of the unit |
| `[@METHODS]` | no | Comma-separated command names (default: `run`) |
| `[@INCLUDES]` | no | Comma-separated extra includes |

---

## Generated Unit Structure (5 Blocks)

Every generated `.c` file has exactly five blocks:

### 1. DIM Block — declarations (VB Dim style)

```c
/* UPPERCASE CONSTANTS */
#define MAX_BCL 65536

typedef enum {
    CMD_SCAN = 0,
    CMD_LIST = 1,
    CMD_READ = 2,
    CMD_SEARCH = 3,
    CMD_COUNT
} Command;

typedef struct {
    char state[1024];
    char config[1024];
} Scanner;

typedef const char* (*CmdFn)(Scanner*, const char*, char*, int);
```

### 2. INIT Block — helpers

```c
static void bcl_ok(char* out, int sz, const char* result) {
    snprintf(out, sz, "[@OK]{%s}", result);
}

static void bcl_err(char* out, int sz, int code, const char* desc) {
    snprintf(out, sz, "[@ERR]{[@CODE]{%d}[@DESC]{%s}}", code, desc);
}
```

### 3. FORWARD Block — prototypes

```c
static const char* fn_scan(Scanner* u, const char* bcl_in, char* out, int out_sz);
static const char* fn_list(Scanner* u, const char* bcl_in, char* out, int out_sz);
static const char* fn_read(Scanner* u, const char* bcl_in, char* out, int out_sz);
static const char* fn_search(Scanner* u, const char* bcl_in, char* out, int out_sz);
```

### 4. DISPATCH Block — jump table + Init + Run

```c
static const CmdFn DISPATCH[CMD_COUNT] = {
    fn_scan, fn_list, fn_read, fn_search
};

void Scanner_Init(Scanner* u) {
    memset(u, 0, sizeof(*u));
}

const char* Scanner_Run(Scanner* u, Command cmd, const char* bcl_in, char* out, int out_sz) {
    if (cmd < 0 || cmd >= CMD_COUNT) {
        bcl_err(out, out_sz, 1, "unknown_command");
        return out;
    }
    return DISPATCH[cmd](u, bcl_in, out, out_sz);
}
```

### 5. GUTS Block — method stubs

```c
static const char* fn_scan(Scanner* u, const char* bcl_in, char* out, int out_sz) {
    /* IN:  [@RUN]{[@CMD]{scan}[@PARAM]{...}} */
    /* OUT: [@OK]{[@RESULT]{...}} */
    (void)u; (void)bcl_in;
    bcl_ok(out, out_sz, "[@RESULT]{implemented}");
    return out;
}
```

---

## Compliance Checklist (19 points)

A `.c` file is a BCL unit IF AND ONLY IF:

- [ ] Has `[@GHOST]` identity header
- [ ] Has `[@VBSTYLE]` header with rules
- [ ] Has `[@FILEID]` with domain and authority
- [ ] Has `[@SUMMARY]` describing purpose
- [ ] Has `[@CLASS]` and `[@METHOD]` declarations
- [ ] Has DIM block (grouped declarations, VB Dim style)
- [ ] Has INIT block (constructors + helpers)
- [ ] Has FORWARD block (prototypes)
- [ ] Has DISPATCH block (jump table + Init + Run)
- [ ] Has GUTS block (implementation)
- [ ] Run function accepts BCL string in, returns BCL string out
- [ ] Success returns `[@OK]{[@RESULT]{...}}`
- [ ] Error returns `[@ERR]{[@CODE]{...}[@DESC]{...}}`
- [ ] No `printf()` calls (except in `main()`)
- [ ] No `@property`, `@staticmethod`, `@classmethod` (Python vestige — N/A in C)
- [ ] No hardcoded paths (use config or BCL param)
- [ ] PascalCase functions, UPPERCASE constants
- [ ] Spaces only, no tabs
- [ ] No global variables except static buffers

**If any check fails, it's not a BCL unit — it's a function library with a name tag.**

The builder auto-checks these after generating. Missing any = `[@STATUS]{FAIL}` with details.

---

## Builder CLI Commands

```bash
# Generate unit from BCL spec (inline)
./bcl_builder "[@MAKE]{[@FILE]{bcl_scanner.c}[@DOMAIN]{scanner}[@AUTHORITY]{Scanner}[@SUMMARY]{Scans files}[@METHODS]{scan,list,read}[@INCLUDES]{sqlite3.h}}"

# Generate unit from BCL spec file
./bcl_builder --file spec.bcl

# Check compliance of existing unit
./bcl_builder --check bcl_units/bcl_scanner.c

# Compile-test a unit (standalone mode)
./bcl_builder --test bcl_units/bcl_scanner.c
```

---

## Output Format

### Success

```
[@OK]{[@FILE]{bcl_scanner.c}[@LINES]{142}}
[@OK]{[@FILE]{bcl_scanner.c}[@LINES]{142}[@VIOLATIONS]{0}[@STATUS]{PASS}}
[@OK]{[@FILE]{bcl_scanner.c}[@COMPILE]{1}[@RUN]{1}[@OUTPUT]{[@OK]{[@RESULT]{implemented}}[@WARNINGS]{(none)}}
```

### Error

```
[@ERR]{[@CODE]{3}[@DESC]{compile failed}}
```

---

## Integration Points

### With bcl_tool_main.c

After generating a unit, add registration:

```c
ToolStack_RegisterUnit(ts, "scanner", "scanner", "Scans files for patterns",
                       Scanner_Init, Scanner_Run, Scanner_Close, Scanner_State);
```

### With Makefile

Add to `UNIT_SRCS`:

```makefile
UNIT_SRCS = ... bcl_scanner.c ...
```

### With MemUnit

Register commands with MemUnit:

```
[@RUN]{[@CMD]{register}[@PARAM]{[@KEY]{scanner.scan}[@UNIT]{scanner}[@HELP]{scan files}[@CATEGORY]{scanner}[@REQUIRES_PARAM]{1}}}
```

---

## Existing Builder

- **File:** `Cascade_toolStack/bin_tools/bcl_builder.c` (590 lines)
- **Author:** Devin
- **Status:** Complete — parses BCL spec, generates .c file, auto-checks, auto-compiles
- **Compile:** `cc -O2 -Wall bcl_builder.c -o bcl_builder`

---

## Unit Registry — All 28 Units (1 complete + 15 stubs + 12 not built)

| # | Unit Name | Category | Status | Source |
|---|-----------|----------|--------|--------|
| 1 | `mem_unit` | orchestration | **NEW** | port from `core/Dom_Bcl_C_ver/bcl_mem_unit.c` |
| 2 | `file_io` | io | **NEW** | build from scratch |
| 3 | `report` | reporting | **NEW** | build from scratch |
| 4 | `db_manager` | database | **NEW** | port from `core/Dom_Unified/DatabaseManager.py` |
| 5 | `config` | config | **NEW** | port from `core/Dom_Bcl_C_ver/bcl_config.c` |
| 6 | `executor` | exec | **NEW** | port from `Cascade_toolStack/bin_tools/cascade_cli.c` |
| 7 | `graph_engine` | graph | **NEW** | port from `core/Dom_Bcl_C_ver/bcl_graph_builder.c` + `bcl_graph_store.c` |
| 8 | `bcl_parser` | bcl | **NEW** | port from `core/Dom_Bcl_C_ver/bcl_parser.c` |
| 9 | `stamper` | bcl | **NEW** | port from `core/Dom_Bcl_C_ver/bcl_stamper.c` |
| 10 | `validator` | bcl | **NEW** | port from `core/Dom_Bcl_C_ver/bcl_validator.c` |
| 11 | `bcl_builder` | bcl | **NEW** | port from `Cascade_toolStack/bin_tools/bcl_builder.c` |
| 12 | `dictionary` | bcl | **NEW** | port from `core/Dom_Bcl_C_ver/bcl_dictionary.c` |
| 13 | `pb_reader` | chat | **COMPLETE** | `bcl_units/bcl_pb_reader.c` |
| 14 | `chat_ingest` | chat | stub | `bcl_units/bcl_chat_ingest.c` |
| 15 | `cleaner` | clean | stub | `bcl_units/bcl_cleaner.c` |
| 16 | `msearch` | search | stub | `bcl_units/bcl_msearch.c` |
| 17 | `mdmerge` | build | stub | `bcl_units/bcl_mdmerge.c` |
| 18 | `discovery` | graph | stub | `bcl_units/bcl_discovery.c` |
| 19 | `schemalint` | config | stub | `bcl_units/bcl_schemalint.c` |
| 20 | `vbcheck` | config | stub | `bcl_units/bcl_vbcheck.c` |
| 21 | `ghostctl` | clean | stub | `bcl_units/bcl_ghostctl.c` |
| 22 | `smartcli` | exec | stub | `bcl_units/bcl_smartcli.c` |
| 23 | `wcmd` | build | stub | `bcl_units/bcl_wcmd.c` |
| 24 | `magnetic` | search | stub | `bcl_units/bcl_magnetic.c` |
| 25 | `codeingest` | graph | stub | `bcl_units/bcl_codeingest.c` |
| 26 | `cognitive` | config | stub | `bcl_units/bcl_cognitive_core.c` |
| 27 | `error_fix` | config | stub | `bcl_units/bcl_error_fix.c` |
| 28 | `windir` | build | stub | `bcl_units/bcl_windir.c` |

---

## BCL Specs for Builder (ready to feed to bcl_builder)

```
# Phase 1: Infrastructure
bcl_builder "[@MAKE]{[@FILE]{bcl_mem_unit.c}[@DOMAIN]{orchestration}[@AUTHORITY]{MemUnit}[@SUMMARY]{In-RAM SQLite orchestration bus}[@METHODS]{dispatch,register,set_state,get_state,log_error,command_count,result_count,read_state,set_config,close}[@INCLUDES]{sqlite3.h}}"

bcl_builder "[@MAKE]{[@FILE]{bcl_file_io.c}[@DOMAIN]{io}[@AUTHORITY]{FileIo}[@SUMMARY]{File I/O operations}[@METHODS]{read,write,search,edit,list,delete,exists,mkdir,stat,copy,move}[@INCLUDES]{sys/stat.h,dirent.h,unistd.h}}"

bcl_builder "[@MAKE]{[@FILE]{bcl_config.c}[@DOMAIN]{config}[@AUTHORITY]{Config}[@SUMMARY]{Configuration manager}[@METHODS]{load,save,get,set,list,delete}[@INCLUDES]{sqlite3.h}}"

bcl_builder "[@MAKE]{[@FILE]{bcl_db_manager.c}[@DOMAIN]{database}[@AUTHORITY]{DbManager}[@SUMMARY]{Database manager MySQL/SQLite}[@METHODS]{connect,query,exec,schema,tables,close}[@INCLUDES]{sqlite3.h,mysql.h}}"

# Phase 2: BCL Layer
bcl_builder "[@MAKE]{[@FILE]{bcl_parser_unit.c}[@DOMAIN]{bcl}[@AUTHORITY]{BclParser}[@SUMMARY]{BCL packet parser}[@METHODS]{parse,extract,validate,build}[@INCLUDES]{string.h}}"

bcl_builder "[@MAKE]{[@FILE]{bcl_dictionary_unit.c}[@DOMAIN]{bcl}[@AUTHORITY]{Dictionary}[@SUMMARY]{BCL token dictionary}[@METHODS]{lookup,list_tags,validate_tag,add_tag}[@INCLUDES]{sqlite3.h}}"

bcl_builder "[@MAKE]{[@FILE]{bcl_stamper_unit.c}[@DOMAIN]{bcl}[@AUTHORITY]{Stamper}[@SUMMARY]{BCL header stamper}[@METHODS]{stamp_ghost,stamp_vbstyle,stamp_fileid,stamp_all}[@INCLUDES]{string.h}}"

bcl_builder "[@MAKE]{[@FILE]{bcl_validator_unit.c}[@DOMAIN]{bcl}[@AUTHORITY]{Validator}[@SUMMARY]{VBStyle validator}[@METHODS]{validate_bcl,check_vbstyle,check_headers,check_tuple3}[@INCLUDES]{string.h}}"

bcl_builder "[@MAKE]{[@FILE]{bcl_builder_unit.c}[@DOMAIN]{bcl}[@AUTHORITY]{BclBuilder}[@SUMMARY]{BCL unit file generator}[@METHODS]{make,check,test}[@INCLUDES]{sys/stat.h}}"

# Phase 3: Tools
bcl_builder "[@MAKE]{[@FILE]{bcl_report.c}[@DOMAIN]{reporting}[@AUTHORITY]{Report}[@SUMMARY]{Report generator from MemUnit}[@METHODS]{summary,errors,commands,events,state,unit_status,export}[@INCLUDES]{sqlite3.h}}"

bcl_builder "[@MAKE]{[@FILE]{bcl_executor.c}[@DOMAIN]{exec}[@AUTHORITY]{Executor}[@SUMMARY]{Safe command executor}[@METHODS]{run,run_sql,run_python,dry_run,history}[@INCLUDES]{stdlib.h}}"

bcl_builder "[@MAKE]{[@FILE]{bcl_graph_engine.c}[@DOMAIN]{graph}[@AUTHORITY]{GraphEngine}[@SUMMARY]{Code graph engine}[@METHODS]{build,store,edges,calls,callers,imports}[@INCLUDES]{sqlite3.h}}"
```

---

## Unit 1: bcl_file_io.c — BCL File I/O Unit

### Purpose

All file domain operations as BCL commands. This is the universal file interface — every tool that needs to read, write, search, edit, list, or delete files goes through this unit. No tool touches the filesystem directly.

### Commands

| Command | Input BCL | Output BCL (success) | Output BCL (error) |
|---|---|---|---|
| `read` | `[@RUN]{[@CMD]{read}[@PARAM]{[@PATH]{/some/file.c}}}` | `[@OK]{[@CONTENT]{file contents here}[@SIZE]{4096}[@LINES]{120}}` | `[@ERR]{[@CODE]{1}[@DESC]{file not found}}` |
| `write` | `[@RUN]{[@CMD]{write}[@PARAM]{[@PATH]{/some/file.c}[@CONTENT]{file contents}}}` | `[@OK]{[@WRITTEN]{4096}}` | `[@ERR]{[@CODE]{2}[@DESC]{permission denied}}` |
| `search` | `[@RUN]{[@CMD]{search}[@PARAM]{[@DIR]{/some/dir}[@PATTERN]{*.c}[@RECURSE]{1}}}` | `[@OK]{[@MATCHES]{file1.c,file2.c}[@COUNT]{2}}` | `[@ERR]{[@CODE]{3}[@DESC]{dir not found}}` |
| `edit` | `[@RUN]{[@CMD]{edit}[@PARAM]{[@PATH]{/some/file.c}[@OLD]{old text}[@NEW]{new text}}}` | `[@OK]{[@EDITED]{1}[@REPLACEMENTS]{3}}` | `[@ERR]{[@CODE]{4}[@DESC]{old text not found}}` |
| `list` | `[@RUN]{[@CMD]{list}[@PARAM]{[@DIR]{/some/dir}}}` | `[@OK]{[@FILES]{file1.c,file2.c,subdir/}[@COUNT]{3}}` | `[@ERR]{[@CODE]{3}[@DESC]{dir not found}}` |
| `delete` | `[@RUN]{[@CMD]{delete}[@PARAM]{[@PATH]{/some/file.c}}}` | `[@OK]{[@DELETED]{1}}` | `[@ERR]{[@CODE]{5}[@DESC]{file not found}}` |
| `exists` | `[@RUN]{[@CMD]{exists}[@PARAM]{[@PATH]{/some/file.c}}}` | `[@OK]{[@EXISTS]{1}[@SIZE]{4096}[@MODE]{0644}}` | `[@OK]{[@EXISTS]{0}}` |
| `mkdir` | `[@RUN]{[@CMD]{mkdir}[@PARAM]{[@PATH]{/some/new/dir}}}` | `[@OK]{[@CREATED]{1}}` | `[@ERR]{[@CODE]{6}[@DESC]{dir already exists}}` |
| `stat` | `[@RUN]{[@CMD]{stat}[@PARAM]{[@PATH]{/some/file.c}}}` | `[@OK]{[@STAT]{[@SIZE]{4096}[@MODE]{0644}[@MTIME]{1719655200}[@TYPE]{file}}}` | `[@ERR]{[@CODE]{1}[@DESC]{file not found}}` |
| `copy` | `[@RUN]{[@CMD]{copy}[@PARAM]{[@SRC]{/from/file.c}[@DST]{/to/file.c}}}` | `[@OK]{[@COPIED]{4096}}` | `[@ERR]{[@CODE]{1}[@DESC]{src not found}}` |
| `move` | `[@RUN]{[@CMD]{move}[@PARAM]{[@SRC]{/from/file.c}[@DST]{/to/file.c}}}` | `[@OK]{[@MOVED]{1}}` | `[@ERR]{[@CODE]{1}[@DESC]{src not found}}` |

### DIM Block

```c
#define MAX_PATH 4096, MAX_CONTENT 1048576, MAX_MATCHES 256;
typedef enum {
    CMD_READ = 0, CMD_WRITE, CMD_SEARCH, CMD_EDIT, CMD_LIST,
    CMD_DELETE, CMD_EXISTS, CMD_MKDIR, CMD_STAT, CMD_COPY, CMD_MOVE,
    CMD_READ_STATE, CMD_SET_CONFIG, CMD_COUNT
} FileCmd;
typedef struct {
    char cwd[MAX_PATH];
    int recurse_default;
    int max_content_size;
} FileUnit;
typedef const char *(*FileCmdFn)(FileUnit *, const char *bcl_in);
```

### Includes

```c
#include "bcl_toolstack.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <dirent.h>
#include <unistd.h>
#include <errno.h>
```

### Integration

- Registered in `bcl_tool_main.c` as `file_io`
- Category: `io`
- Other units call it via BCL: `[@RUN]{[@CMD]{read}[@PARAM]{[@PATH]{...}}}`
- MemUnit routes file commands through this unit

---

## Unit 2: bcl_mem_unit.c — In-RAM SQLite Orchestration Bus

### Purpose

Universal orchestration layer for ALL tools. Every command flows through MemUnit. Every result gets recorded. No direct unit-to-unit calls — everything goes through the bus.

### Source

Port from `core/Dom_Bcl_C_ver/bcl_mem_unit.c` (551 lines). Adapt to BCL unit interface (BCL in, BCL out).

### 6 Tables

| Table | Purpose |
|---|---|
| `mu_commands` | Transport — every dispatched command recorded here |
| `mu_results` | Results — outcomes of executed commands |
| `mu_events` | Audit Trail — lifecycle / dispatch events |
| `mu_state` | Runtime State — key/value configuration |
| `mu_errors` | Error Detail — structured error records |
| `mu_cli_registry` | Command Registry — CLI command metadata |

### Commands (BCL interface)

| Command | Input BCL | Output BCL |
|---|---|---|
| `dispatch` | `[@RUN]{[@CMD]{dispatch}[@PARAM]{[@UNIT]{pb_reader}[@CMD]{scan}[@BCL_IN]{...}}}` | `[@OK]{[@CMD_ID]{42}[@STATUS]{pending}}` |
| `register` | `[@RUN]{[@CMD]{register}[@PARAM]{[@KEY]{pb_reader.scan}[@UNIT]{pb_reader}[@HELP]{scan .pb files}[@CATEGORY]{chat}[@REQUIRES_PARAM]{0}}}` | `[@OK]{[@REGISTERED]{1}}` |
| `set_state` | `[@RUN]{[@CMD]{set_state}[@PARAM]{[@KEY]{db_path}[@VALUE]{/path/to/db}}}` | `[@OK]{[@SET]{1}}` |
| `get_state` | `[@RUN]{[@CMD]{get_state}[@PARAM]{[@KEY]{db_path}}}` | `[@OK]{[@VALUE]{/path/to/db}}` |
| `log_error` | `[@RUN]{[@CMD]{log_error}[@PARAM]{[@CMD_ID]{42}[@CODE]{3}[@DESC]{db failed}[@UNIT]{pb_reader}[@SEVERITY]{error}}}` | `[@OK]{[@LOGGED]{1}}` |
| `command_count` | `[@RUN]{[@CMD]{command_count}}` | `[@OK]{[@COUNT]{42}}` |
| `result_count` | `[@RUN]{[@CMD]{result_count}}` | `[@OK]{[@COUNT]{38}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{[@INIT]{1}[@COMMANDS]{42}[@RESULTS]{38}[@EVENTS]{45}}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{[@DB_PATH]{/path}}}` | `[@OK]{[@CONFIG]{}}` |
| `close` | `[@RUN]{[@CMD]{close}}` | `[@OK]{[@CLOSED]{1}}` |

### Orchestration Flow

```
Caller (CLI/AI/other unit)
    |
    v
MemUnit.dispatch(unit, cmd, bcl_in)
    |
    +-- records to mu_commands (transport)
    +-- looks up unit in mu_cli_registry
    +-- calls target_unit.Run(cmd, bcl_in)
    |       |
    |       v
    |    Unit processes BCL input
    |    Unit returns BCL output
    |
    +-- records to mu_results (results)
    +-- records to mu_events (audit trail)
    +-- on error: records to mu_errors
    +-- returns BCL output to caller
```

### Key Principle

No direct unit-to-unit calls. If Unit A needs data from Unit B:
1. Unit A returns: `[@OK]{[@NEEDS]{[@UNIT]{file_io}[@CMD]{read}[@PARAM]{[@PATH]{...}}}}`
2. MemUnit dispatches that to Unit B
3. Unit B's result feeds back to Unit A

### DIM Block

```c
#define MU_MAX_VAL 4096, MU_MAX_CMD 65536, MU_MAX_RESULT 65536;
typedef enum {
    CMD_DISPATCH = 0, CMD_REGISTER, CMD_SET_STATE, CMD_GET_STATE,
    CMD_LOG_ERROR, CMD_COMMAND_COUNT, CMD_RESULT_COUNT,
    CMD_READ_STATE, CMD_SET_CONFIG, CMD_CLOSE, CMD_COUNT
} MuCmd;
typedef struct {
    void *conn;
    int initialized;
    int command_count;
    int result_count;
    int event_count;
} MemUnit;
typedef const char *(*MuCmdFn)(MemUnit *, const char *bcl_in);
```

### Includes

```c
#include "bcl_toolstack.h"
#include <sqlite3.h>
#include <string.h>
#include <stdlib.h>
```

### Integration

- Registered in `bcl_tool_main.c` as `mem_unit`
- Category: `orchestration`
- Initialized FIRST before all other units
- All other units register their commands with it
- CLI `./bcl_tool dispatch '[@UNIT]{...}[@CMD]{...}'` goes through MemUnit

---

## Unit 3: bcl_report.c — BCL Report Unit

### Purpose

Generate reports from MemUnit's audit trail, command history, error logs, and state. Produces BCL-formatted reports that can be saved to files or displayed in CLI.

### Commands

| Command | Input BCL | Output BCL |
|---|---|---|
| `summary` | `[@RUN]{[@CMD]{summary}}` | `[@OK]{[@REPORT]{[@TOTAL_CMDS]{42}[@SUCCESS]{38}[@FAILED]{4}[@UNITS]{16}[@UPTIME]{3600}}}` |
| `errors` | `[@RUN]{[@CMD]{errors}[@PARAM]{[@LIMIT]{10}}}` | `[@OK]{[@ERRORS]{[@ERR]{[@CODE]{3}[@DESC]{db failed}[@UNIT]{pb_reader}[@TS]{2026-06-29 08:00}}...}}` |
| `commands` | `[@RUN]{[@CMD]{commands}[@PARAM]{[@LIMIT]{20}[@UNIT]{pb_reader}}}` | `[@OK]{[@COMMANDS]{[@CMD]{[@ID]{42}[@UNIT]{pb_reader}[@CMD]{scan}[@STATUS]{ok}[@TS]{...}}...}}` |
| `events` | `[@RUN]{[@CMD]{events}[@PARAM]{[@LIMIT]{20}}}` | `[@OK]{[@EVENTS]{[@EVT]{[@TYPE]{CMD_DISPATCHED}[@DETAIL]{scan}[@TS]{...}}...}}` |
| `state` | `[@RUN]{[@CMD]{state}}` | `[@OK]{[@STATE]{[@KEY]{db_path}[@VALUE]{/path}...}}` |
| `unit_status` | `[@RUN]{[@CMD]{unit_status}[@PARAM]{[@UNIT]{pb_reader}}}` | `[@OK]{[@UNIT_STATUS]{[@NAME]{pb_reader}[@CMDS]{12}[@SUCCESS]{10}[@FAILED]{2}[@LAST]{2026-06-29 08:00}}}` |
| `export` | `[@RUN]{[@CMD]{export}[@PARAM]{[@FORMAT]{md}[@PATH]{/tmp/report.md}}}` | `[@OK]{[@EXPORTED]{/tmp/report.md}[@SIZE]{4096}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

### DIM Block

```c
#define MAX_REPORT 65536, MAX_LINE 1024;
typedef enum {
    CMD_SUMMARY = 0, CMD_ERRORS, CMD_COMMANDS, CMD_EVENTS,
    CMD_STATE, CMD_UNIT_STATUS, CMD_EXPORT,
    CMD_READ_STATE, CMD_SET_CONFIG, CMD_COUNT
} ReportCmd;
typedef struct {
    MemUnit *mu;
    char default_format[16];
    char default_path[MAX_PATH];
} ReportUnit;
typedef const char *(*ReportCmdFn)(ReportUnit *, const char *bcl_in);
```

### Integration

- Registered in `bcl_tool_main.c` as `report`
- Category: `reporting`
- Reads from MemUnit's tables (mu_commands, mu_results, mu_events, mu_errors, mu_state)
- Uses `bcl_file_io` to write exported reports
- CLI: `./bcl_tool report summary`, `./bcl_tool report errors`

---

## Unit 4: bcl_db_manager.c — Database Manager Unit

### Purpose

Universal database interface — MySQL, SQLite, connection pooling, queries, schema management. All database operations go through this unit. No tool connects to a database directly.

### Source

Port from `core/Dom_Unified/DatabaseManager.py` (Python) + `core/Dom_Bcl_C_ver/bcl_graph_store.c` (C SQLite/MySQL).

### Commands

| Command | Input BCL | Output BCL (success) |
|---|---|---|
| `connect` | `[@RUN]{[@CMD]{connect}[@PARAM]{[@ENGINE]{mysql}[@HOST]{localhost}[@USER]{root}[@DB]{vb_shared}}}` | `[@OK]{[@CONN]{1}[@ENGINE]{mysql}}` |
| `connect` | `[@RUN]{[@CMD]{connect}[@PARAM]{[@ENGINE]{sqlite}[@PATH]{/path/to.db}}}` | `[@OK]{[@CONN]{1}[@ENGINE]{sqlite}}` |
| `query` | `[@RUN]{[@CMD]{query}[@PARAM]{[@SQL]{SELECT * FROM learned_rules LIMIT 5}}}` | `[@OK]{[@ROWS]{3}[@DATA]{...}}` |
| `exec` | `[@RUN]{[@CMD]{exec}[@PARAM]{[@SQL]{INSERT INTO ...}}}` | `[@OK]{[@AFFECTED]{1}}` |
| `schema` | `[@RUN]{[@CMD]{schema}[@PARAM]{[@TABLE]{learned_rules}}}` | `[@OK]{[@COLUMNS]{...}}` |
| `tables` | `[@RUN]{[@CMD]{tables}}` | `[@OK]{[@TABLES]{...}}` |
| `close` | `[@RUN]{[@CMD]{close}}` | `[@OK]{[@CLOSED]{1}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{[@ENGINE]{mysql}[@CONN]{1}}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

### DIM Block

```c
#define MAX_SQL 65536, MAX_RESULT 1048576;
typedef enum {
    CMD_CONNECT = 0, CMD_QUERY, CMD_EXEC, CMD_SCHEMA,
    CMD_TABLES, CMD_CLOSE, CMD_READ_STATE, CMD_SET_CONFIG, CMD_COUNT
} DbCmd;
typedef struct {
    int engine;          /* 0=sqlite, 1=mysql */
    void *conn;          /* sqlite3* or MYSQL* */
    char host[256];
    char user[128];
    char db_name[128];
    char sqlite_path[MAX_PATH];
    int connected;
} DbUnit;
```

### Integration

- Registered in `bcl_tool_main.c` as `db_manager`
- Category: `database`
- Other units request DB access through MemUnit dispatch to this unit
- Supports both SQLite (via sqlite3.h) and MySQL (via mysql.h, conditional compile)

---

## Unit 5: bcl_config.c — Config Unit

### Purpose

Configuration management — load, save, get, set config values. JSON or SQLite-backed. All units read their config through this unit.

### Source

Port from `core/Dom_Bcl_C_ver/bcl_config.c` (already has config store logic).

### Commands

| Command | Input BCL | Output BCL |
|---|---|---|
| `load` | `[@RUN]{[@CMD]{load}[@PARAM]{[@PATH]{/path/to/config.json}}}` | `[@OK]{[@LOADED]{42}[@KEYS]{...}}` |
| `save` | `[@RUN]{[@CMD]{save}[@PARAM]{[@PATH]{/path/to/config.json}}}` | `[@OK]{[@SAVED]{42}}` |
| `get` | `[@RUN]{[@CMD]{get}[@PARAM]{[@KEY]{db_path}}}` | `[@OK]{[@VALUE]{/path/to/db}}` |
| `set` | `[@RUN]{[@CMD]{set}[@PARAM]{[@KEY]{db_path}[@VALUE]{/new/path}}}` | `[@OK]{[@SET]{1}}` |
| `list` | `[@RUN]{[@CMD]{list}}` | `[@OK]{[@KEYS]{...}[@COUNT]{42}}` |
| `delete` | `[@RUN]{[@CMD]{delete}[@PARAM]{[@KEY]{old_key}}}` | `[@OK]{[@DELETED]{1}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{...}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

### DIM Block

```c
#define MAX_CONFIG_KEY 256, MAX_CONFIG_VAL 4096, MAX_CONFIG_ENTRIES 256;
typedef enum {
    CMD_LOAD = 0, CMD_SAVE, CMD_GET, CMD_SET,
    CMD_LIST, CMD_DELETE, CMD_READ_STATE, CMD_SET_CONFIG, CMD_COUNT
} ConfigCmd;
typedef struct {
    char keys[MAX_CONFIG_ENTRIES][MAX_CONFIG_KEY];
    char values[MAX_CONFIG_ENTRIES][MAX_CONFIG_VAL];
    int count;
    char config_path[MAX_PATH];
} ConfigUnit;
```

---

## Unit 6: bcl_executor.c — Command Executor Unit

### Purpose

Safe command execution — runs shell commands, captures output, detects errors, queries knowledge base on failure. This is the Cascade CLI as a BCL unit.

### Source

Port from `Cascade_toolStack/bin_tools/cascade_cli.c` (already has state machine, error detection, KB lookup).

### Commands

| Command | Input BCL | Output BCL |
|---|---|---|
| `run` | `[@RUN]{[@CMD]{run}[@PARAM]{[@COMMAND]{ls -la}[@TIMEOUT]{30}}}` | `[@OK]{[@EXIT]{0}[@OUTPUT]{...}[@DURATION]{120}}` |
| `run_sql` | `[@RUN]{[@CMD]{run_sql}[@PARAM]{[@SQL]{SELECT 1}[@DB]{vb_shared}}}` | `[@OK]{[@EXIT]{0}[@OUTPUT]{...}}` |
| `run_python` | `[@RUN]{[@CMD]{run_python}[@PARAM]{[@FILE]{script.py}[@ARGS]{...}}}` | `[@OK]{[@EXIT]{0}[@OUTPUT]{...}}` |
| `dry_run` | `[@RUN]{[@CMD]{dry_run}[@PARAM]{[@COMMAND]{rm -rf /}}}` | `[@OK]{[@BLOCKED]{1}[@REASON]{destructive}}` |
| `history` | `[@RUN]{[@CMD]{history}[@PARAM]{[@LIMIT]{10}}}` | `[@OK]{[@COMMANDS]{...}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{...}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

### DIM Block

```c
#define MAX_CMD 65536, MAX_OUTPUT 1048576, MAX_HISTORY 100;
typedef enum {
    CMD_RUN = 0, CMD_RUN_SQL, CMD_RUN_PYTHON,
    CMD_DRY_RUN, CMD_HISTORY, CMD_READ_STATE, CMD_SET_CONFIG, CMD_COUNT
} ExecCmd;
typedef struct {
    int timeout_default;
    int max_output;
    char history[MAX_HISTORY][MAX_CMD];
    int history_count;
    int total_runs;
    int total_errors;
} ExecUnit;
```

---

## Unit 7: bcl_graph_engine.c — Graph Engine Unit

### Purpose

Code graph — build call/state/import edges from AST, store to DB, query graph relationships. Combines graph builder + graph store.

### Source

Port from `core/Dom_Bcl_C_ver/bcl_graph_builder.c` + `bcl_graph_store.c`.

### Commands

| Command | Input BCL | Output BCL |
|---|---|---|
| `build` | `[@RUN]{[@CMD]{build}[@PARAM]{[@FILE]{/path/to/file.py}}}` | `[@OK]{[@CLASSES]{3}[@METHODS]{12}[@EDGES]{45}}` |
| `store` | `[@RUN]{[@CMD]{store}[@PARAM]{[@FILE]{...}[@DB]{bcl_ir}}}` | `[@OK]{[@STORED]{60}}` |
| `edges` | `[@RUN]{[@CMD]{edges}[@PARAM]{[@FILE]{...}}}` | `[@OK]{[@EDGES]{...}}` |
| `calls` | `[@RUN]{[@CMD]{calls}[@PARAM]{[@METHOD]{ClassName.method}}}` | `[@OK]{[@CALLS]{...}}` |
| `callers` | `[@RUN]{[@CMD]{callers}[@PARAM]{[@METHOD]{ClassName.method}}}` | `[@OK]{[@CALLERS]{...}}` |
| `imports` | `[@RUN]{[@CMD]{imports}[@PARAM]{[@FILE]{...}}}` | `[@OK]{[@IMPORTS]{...}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{...}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

### DIM Block

```c
#define MAX_EDGES 8192, MAX_CLASSES 256, MAX_METHODS 2048;
typedef enum {
    CMD_BUILD = 0, CMD_STORE, CMD_EDGES, CMD_CALLS,
    CMD_CALLERS, CMD_IMPORTS, CMD_READ_STATE, CMD_SET_CONFIG, CMD_COUNT
} GraphCmd;
typedef struct {
    void *db_conn;
    char db_path[MAX_PATH];
    int total_classes;
    int total_methods;
    int total_edges;
} GraphUnit;
```

---

## Unit 8: bcl_parser_unit.c — BCL Parser Unit

### Purpose

Parse BCL text into structured nodes — `[@TAG]{value}` → tree of nodes. Used by all units to parse incoming BCL packets.

### Source

Port from `core/Dom_Bcl_C_ver/bcl_parser.c` + the parser already in `bcl_tool_main.c`.

### Commands

| Command | Input BCL | Output BCL |
|---|---|---|
| `parse` | `[@RUN]{[@CMD]{parse}[@PARAM]{[@TEXT]{[@OK]{[@COUNT]{3}}}}}` | `[@OK]{[@NODES]{2}[@TREE]{...}}` |
| `extract` | `[@RUN]{[@CMD]{extract}[@PARAM]{[@TEXT]{...}[@TAG]{COUNT}}}` | `[@OK]{[@VALUE]{3}}` |
| `validate` | `[@RUN]{[@CMD]{validate}[@PARAM]{[@TEXT]{[@OK]{...}}}}` | `[@OK]{[@VALID]{1}}` or `[@ERR]{[@CODE]{1}[@DESC]{unbalanced braces}}` |
| `build` | `[@RUN]{[@CMD]{build}[@PARAM]{[@TAG]{OK}[@VALUE]{[@COUNT]{3}}}}` | `[@OK]{[@BCL]{[@OK]{[@COUNT]{3}}}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{...}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

---

## Unit 9: bcl_stamper_unit.c — BCL Stamper Unit

### Purpose

Generate BCL headers (`[@GHOST]`, `[@VBSTYLE]`, `[@FILEID]`, `[@SUMMARY]`, `[@CLASS]`, `[@METHOD]`) for files. The stamper as a unit — other units call it to stamp their output.

### Source

Port from `core/Dom_Bcl_C_ver/bcl_stamper.c`.

### Commands

| Command | Input BCL | Output BCL |
|---|---|---|
| `stamp_ghost` | `[@RUN]{[@CMD]{stamp_ghost}[@PARAM]{[@FILE]{unit.c}[@AUTHOR]{Devin}[@CONTEXT]{...}}}` | `[@OK]{[@STAMP]{//[@GHOST]{...}}}` |
| `stamp_vbstyle` | `[@RUN]{[@CMD]{stamp_vbstyle}}` | `[@OK]{[@STAMP]{//[@VBSTYLE]{...}}}` |
| `stamp_fileid` | `[@RUN]{[@CMD]{stamp_fileid}[@PARAM]{[@ID]{unit.c}[@DOMAIN]{dom}[@AUTHORITY]{Auth}}}` | `[@OK]{[@STAMP]{//[@FILEID]{...}}}` |
| `stamp_all` | `[@RUN]{[@CMD]{stamp_all}[@PARAM]{[@FILE]{...}[@DOMAIN]{...}[@AUTHORITY]{...}[@SUMMARY]{...}}}` | `[@OK]{[@HEADER]{...}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{...}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

---

## Unit 10: bcl_validator_unit.c — Validator Unit

### Purpose

Validate BCL packets, VBStyle compliance, file headers. Checks that files have correct stamps, methods return Tuple3, no forbidden patterns.

### Source

Port from `core/Dom_Bcl_C_ver/bcl_validator.c` + `bcl_static_analyzer.c`.

### Commands

| Command | Input BCL | Output BCL |
|---|---|---|
| `validate_bcl` | `[@RUN]{[@CMD]{validate_bcl}[@PARAM]{[@TEXT]{[@OK]{[@COUNT]{3}}}}}` | `[@OK]{[@VALID]{1}[@NODES]{2}}` |
| `check_vbstyle` | `[@RUN]{[@CMD]{check_vbstyle}[@PARAM]{[@FILE]{unit.py}}}` | `[@OK]{[@VIOLATIONS]{0}[@STATUS]{PASS}}` |
| `check_headers` | `[@RUN]{[@CMD]{check_headers}[@PARAM]{[@FILE]{unit.c}}}` | `[@OK]{[@GHOST]{1}[@VBSTYLE]{1}[@FILEID]{1}[@SUMMARY]{1}}` |
| `check_tuple3` | `[@RUN]{[@CMD]{check_tuple3}[@PARAM]{[@FILE]{unit.py}}}` | `[@OK]{[@TUPLE3]{1}[@METHODS]{12}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{...}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

---

## Unit 11: bcl_builder_unit.c — BCL Builder Unit

### Purpose

Generate BCL unit .c files from BCL spec input. AI sends spec, builder writes the file, checks compliance, compiles. Already implemented in `bin_tools/bcl_builder.c`.

### Source

Port from `Cascade_toolStack/bin_tools/bcl_builder.c` (already working).

### Commands

| Command | Input BCL | Output BCL |
|---|---|---|
| `make` | `[@RUN]{[@CMD]{make}[@PARAM]{[@FILE]{name.c}[@DOMAIN]{dom}[@AUTHORITY]{Auth}[@SUMMARY]{...}[@METHODS]{m1,m2}[@INCLUDES]{lib.h}}}` | `[@OK]{[@FILE]{name.c}[@LINES]{112}[@COMPILE]{1}[@CHECK]{PASS}}` |
| `check` | `[@RUN]{[@CMD]{check}[@PARAM]{[@FILE]{unit.c}}}` | `[@OK]{[@VIOLATIONS]{0}[@STATUS]{PASS}}` |
| `test` | `[@RUN]{[@CMD]{test}[@PARAM]{[@FILE]{unit.c}}}` | `[@OK]{[@COMPILE]{1}[@RUN]{1}[@OUTPUT]{...}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{...}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

---

## Unit 12: bcl_dictionary_unit.c — BCL Dictionary Unit

### Purpose

BCL token dictionary — defines all valid `[@TAG]` tokens, their fields, their meaning. The schema authority. Other units query this to validate tokens or look up token definitions.

### Source

Port from `core/Dom_Bcl_C_ver/bcl_dictionary.c` (already has `BclDictionary_Run` dispatch).

### Commands

| Command | Input BCL | Output BCL |
|---|---|---|
| `lookup` | `[@RUN]{[@CMD]{lookup}[@PARAM]{[@TAG]{GHOST}}}` | `[@OK]{[@DEF]{file identity stamp}[@FIELDS]{file_path,date,author,context}}` |
| `list_tags` | `[@RUN]{[@CMD]{list_tags}}` | `[@OK]{[@TAGS]{GHOST,VBSTYLE,FILEID,SUMMARY,CLASS,METHOD,...}[@COUNT]{42}}` |
| `validate_tag` | `[@RUN]{[@CMD]{validate_tag}[@PARAM]{[@TAG]{GHOST}[@FIELDS]{file_path,date}}}` | `[@OK]{[@VALID]{1}}` or `[@ERR]{[@CODE]{1}[@DESC]{missing field: author}}` |
| `add_tag` | `[@RUN]{[@CMD]{add_tag}[@PARAM]{[@TAG]{NEW_TAG}[@DEF]{description}[@FIELDS]{f1,f2}}}` | `[@OK]{[@ADDED]{1}}` |
| `read_state` | `[@RUN]{[@CMD]{read_state}}` | `[@OK]{[@STATE]{...}}` |
| `set_config` | `[@RUN]{[@CMD]{set_config}[@PARAM]{...}}` | `[@OK]{[@CONFIG]{}}` |

---

## Build Order

### Phase 1: Infrastructure (must be first)

1. **`bcl_mem_unit.c`** — port from core, adapt to BCL in/out. Must be first — all other units depend on it.
2. **`bcl_file_io.c`** — new unit, all file operations. Second because many units need file access.
3. **`bcl_config.c`** — port from core. Third because units need config to initialize.
4. **`bcl_db_manager.c`** — port from Python + C. Fourth because units need DB access.

### Phase 2: BCL Layer (depends on Phase 1)

5. **`bcl_parser_unit.c`** — port from core. Needed by all units to parse BCL.
6. **`bcl_dictionary_unit.c`** — port from core. Token schema authority.
7. **`bcl_stamper_unit.c`** — port from core. Generates headers.
8. **`bcl_validator_unit.c`** — port from core. Validates compliance.
9. **`bcl_builder_unit.c`** — port from bin_tools. Generates new units.

### Phase 3: Tools (depends on Phase 1 + 2)

10. **`bcl_report.c`** — new unit, reads from MemUnit. Needs MemUnit populated.
11. **`bcl_executor.c`** — port from cascade_cli.c. Safe command execution.
12. **`bcl_graph_engine.c`** — port from core. Code graph operations.

### Phase 4: Fill stubs (existing 15 stub units)

13-28. Fill the existing stub units with real implementations, connecting them through MemUnit dispatch instead of direct calls.

---

## Registration Order in bcl_tool_main.c

```c
/* Phase 1: Infrastructure */
ToolStack_RegisterUnit(ts, "mem_unit",    "orchestration", "In-RAM SQLite orchestration bus",
                       MemUnit_Init, MemUnit_Run, MemUnit_Close, MemUnit_State);
ToolStack_RegisterUnit(ts, "file_io",     "io", "BCL file I/O unit",
                       FileUnit_Init, FileUnit_Run, FileUnit_Close, FileUnit_State);
ToolStack_RegisterUnit(ts, "config",      "config", "Configuration manager",
                       ConfigUnit_Init, ConfigUnit_Run, ConfigUnit_Close, ConfigUnit_State);
ToolStack_RegisterUnit(ts, "db_manager",  "database", "Database manager (MySQL/SQLite)",
                       DbUnit_Init, DbUnit_Run, DbUnit_Close, DbUnit_State);

/* Phase 2: BCL Layer */
ToolStack_RegisterUnit(ts, "bcl_parser",  "bcl", "BCL packet parser",
                       BclParserUnit_Init, BclParserUnit_Run, BclParserUnit_Close, BclParserUnit_State);
ToolStack_RegisterUnit(ts, "dictionary",  "bcl", "BCL token dictionary",
                       DictionaryUnit_Init, DictionaryUnit_Run, DictionaryUnit_Close, DictionaryUnit_State);
ToolStack_RegisterUnit(ts, "stamper",     "bcl", "BCL header stamper",
                       StamperUnit_Init, StamperUnit_Run, StamperUnit_Close, StamperUnit_State);
ToolStack_RegisterUnit(ts, "validator",   "bcl", "VBStyle validator",
                       ValidatorUnit_Init, ValidatorUnit_Run, ValidatorUnit_Close, ValidatorUnit_State);
ToolStack_RegisterUnit(ts, "bcl_builder", "bcl", "BCL unit file generator",
                       BclBuilderUnit_Init, BclBuilderUnit_Run, BclBuilderUnit_Close, BclBuilderUnit_State);

/* Phase 3: Tools */
ToolStack_RegisterUnit(ts, "report",      "reporting", "BCL report generator",
                       ReportUnit_Init, ReportUnit_Run, ReportUnit_Close, ReportUnit_State);
ToolStack_RegisterUnit(ts, "executor",    "exec", "Safe command executor",
                       ExecUnit_Init, ExecUnit_Run, ExecUnit_Close, ExecUnit_State);
ToolStack_RegisterUnit(ts, "graph_engine","graph", "Code graph engine",
                       GraphUnit_Init, GraphUnit_Run, GraphUnit_Close, GraphUnit_State);

/* Phase 4: Existing stubs */
ToolStack_RegisterUnit(ts, "pb_reader",   "chat",   "Encrypted .pb chat file reader",
                       PbReader_Init, PbReader_Run, PbReader_Close, PbReader_State);
ToolStack_RegisterUnit(ts, "chat_ingest", "chat",   "AST-based code ingester",
                       ChatIngest_Init, ChatIngest_Run, ChatIngest_Close, ChatIngest_State);
ToolStack_RegisterUnit(ts, "cleaner",     "clean",  "Cache and junk cleaner",
                       Cleaner_Init, Cleaner_Run, Cleaner_Close, Cleaner_State);
ToolStack_RegisterUnit(ts, "msearch",     "search", "MySQL/Qdrant semantic search",
                       Msearch_Init, Msearch_Run, Msearch_Close, Msearch_State);
ToolStack_RegisterUnit(ts, "mdmerge",     "build",  "Markdown file merger",
                       Mdmerge_Init, Mdmerge_Run, Mdmerge_Close, Mdmerge_State);
ToolStack_RegisterUnit(ts, "discovery",   "graph",  "Code discovery and analysis",
                       Discovery_Init, Discovery_Run, Discovery_Close, Discovery_State);
ToolStack_RegisterUnit(ts, "schemalint",  "config", "Database schema linter",
                       Schemalint_Init, Schemalint_Run, Schemalint_Close, Schemalint_State);
ToolStack_RegisterUnit(ts, "vbcheck",     "config", "VBStyle compliance checker",
                       Vbcheck_Init, Vbcheck_Run, Vbcheck_Close, Vbcheck_State);
ToolStack_RegisterUnit(ts, "ghostctl",    "clean",  "System-wide cleanup control",
                       Ghostctl_Init, Ghostctl_Run, Ghostctl_Close, Ghostctl_State);
ToolStack_RegisterUnit(ts, "smartcli",    "exec",   "Smart CLI executor",
                       Smartcli_Init, Smartcli_Run, Smartcli_Close, Smartcli_State);
ToolStack_RegisterUnit(ts, "wcmd",        "build",  "Window command processor",
                       Wcmd_Init, Wcmd_Run, Wcmd_Close, Wcmd_State);
ToolStack_RegisterUnit(ts, "magnetic",    "search", "Magnetic radius search",
                       Magnetic_Init, Magnetic_Run, Magnetic_Close, Magnetic_State);
ToolStack_RegisterUnit(ts, "codeingest",  "graph",  "Code ingestion engine",
                       Codeingest_Init, Codeingest_Run, Codeingest_Close, Codeingest_State);
ToolStack_RegisterUnit(ts, "cognitive",   "config", "Cognitive core engine",
                       CognitiveCore_Init, CognitiveCore_Run, CognitiveCore_Close, CognitiveCore_State);
ToolStack_RegisterUnit(ts, "error_fix",   "config", "Error fix trainer",
                       ErrorFix_Init, ErrorFix_Run, ErrorFix_Close, ErrorFix_State);
ToolStack_RegisterUnit(ts, "windir",      "build",  "Window directory manager",
                       Windir_Init, Windir_Run, Windir_Close, Windir_State);
```

---

## Makefile Addition

```makefile
UNIT_SRCS = bcl_mem_unit.c bcl_file_io.c bcl_config.c bcl_db_manager.c \
            bcl_parser_unit.c bcl_dictionary_unit.c bcl_stamper_unit.c \
            bcl_validator_unit.c bcl_builder_unit.c \
            bcl_report.c bcl_executor.c bcl_graph_engine.c \
            bcl_pb_reader.c bcl_chat_ingest.c bcl_cleaner.c \
            bcl_msearch.c bcl_mdmerge.c bcl_discovery.c \
            bcl_schemalint.c bcl_vbcheck.c bcl_ghostctl.c \
            bcl_smartcli.c bcl_wcmd.c bcl_magnetic.c \
            bcl_codeingest.c bcl_cognitive_core.c \
            bcl_error_fix.c bcl_windir.c bcl_tool_main.c
```

---

## Architecture Diagram

```
                    ┌─────────────────────────────────────────┐
                    │            bcl_tool (CLI)                │
                    │    bcl_tool list                         │
                    │    bcl_tool <unit> <cmd> [bcl_input]     │
                    │    bcl_tool dispatch <bcl_packet>        │
                    └────────────────┬────────────────────────┘
                                     │
                    ┌────────────────▼────────────────────────┐
                    │            mem_unit                      │
                    │     (In-RAM SQLite orchestration bus)    │
                    │   mu_commands, mu_results, mu_events,    │
                    │   mu_state, mu_errors, mu_cli_registry   │
                    └────────────────┬────────────────────────┘
                                     │ dispatches BCL packets
                    ┌────────────────┼────────────────┐
                    │                │                │
     ┌──────────────▼──┐  ┌─────────▼──────┐  ┌──────▼──────────┐
     │   file_io       │  │   db_manager   │  │   executor      │
     │   config        │  │   graph_engine │  │   report        │
     │   bcl_parser    │  │   dictionary   │  │   smartcli      │
     │   stamper       │  │   validator    │  │   wcmd          │
     │   bcl_builder   │  │   discovery    │  │   windir        │
     │   pb_reader     │  │   codeingest   │  │   cleaner       │
     │   chat_ingest   │  │   schemalint   │  │   ghostctl      │
     │   msearch       │  │   vbcheck      │  │   magnetic      │
     │   mdmerge       │  │   cognitive    │  │   error_fix     │
     └─────────────────┘  └────────────────┘  └─────────────────┘
```

All units communicate via BCL packets through MemUnit. No direct unit-to-unit calls.

---

## Garmin Road Mapping

This pipeline is **Road 9 (BCL Template Maker)** in the CodeGPS Garmin navigator:

```
Road 9: BCL Template Maker
  Stage 1: Header Editor (PyQt6 GUI)        ← GREEN (exists)
  Stage 2: Template Generation              ← GREEN (exists)
  Stage 3: Stamp Engine                     ← GREEN (exists)
  Stage 4: Capsule Builder                  ← GREEN (exists)
  Stage 5: Verify                           ← GREEN (exists)
  Stage 6: BCL Unit Builder (spec → .c)     ← GREEN (bcl_builder.c exists)
  Stage 7: Auto-check compliance            ← GREEN (builder does this)
  Stage 8: Auto-compile test                ← GREEN (builder does this)
  Stage 9: Register in tool stack           ← YELLOW (manual, not automated yet)
  Stage 10: MemUnit registration            ← GRAY (not built yet)
```

Road colors:
- Green = pipeline stage succeeded
- Red = pipeline stage failed
- Yellow = partial (manual step)
- Gray = not built yet
