# Dom_Common — Shared Module Design Document

[@GHOST]{file_path="core/Dom_Common/DESIGN.md" date="2026-07-04" author="devin" session_id="bcl-common-module" context="Design document for Dom_Common module — 5 shared classes: ClassBCL, ClassRules, ClassGraph, ClassTest, ClassErrors. Self-learning error→fix system with live debugging / hot-fix."}

## Overview

Dom_Common is the shared module between C BCL units (Cascade_toolStack/bcl_units/) and Python domain code (core/Dom_Vsstyle/, core/Dom_Db/, core/Dom_Gui/). It provides 5 classes that are used by all domains:

1. **ClassBCL** — BCL packet parser/writer (shared format between C and Python)
2. **ClassRules** — Rule checking, editing, updating, creating (the "law")
3. **ClassGraph** — Wraps Reports v4 execution graph / code structure / code flow
4. **ClassTest** — Wraps ClassTester from Reports v4 for in-Python testing
5. **ClassErrors** — Self-learning error→fix system with live debugging / hot-fix

## Prior Art (Found in Codebase + MySQL)

The error→fix system was built before, scattered across 6 files:

| File | What It Does |
|---|---|
| `bin_tools/ai_fix_data_gen.c` | Generates synthetic error samples, 40D features → 16D fix actions |
| `bin_tools/coretotch_fix.c` | C-based SGD training engine (40→64→16 MLP) |
| `bin_tools/ErrorFixTrainer.py` | Python error→lesson generator, SQLite storage |
| `bin_tools/ai_fix_bridge.py` | Bridge: receives error text → suggests fix |
| `bcl_units/bcl_error_fix.c` | BCL unit: queries MySQL learned_rules for fixes |
| `bin_tools/fix_training.json` | Training data |

MySQL tables:
- `error_knowledge` (139 entries) — error signatures with cause, solution, fix_code, confidence, frequency
- `fix_attempts` — tracks success/failed/partial for each fix attempt
- `execution_log` — every command with stdout/stderr linked to error_id
- `learned_rules` (10,540) — patterns with fix_actions, confidence, success/failure counts
- `know_solutions` — auto-apply solutions with fault_code, scope, weight

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Dom_Common                               │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ ClassBCL │  │ClassRules│  │ClassGraph│  │ ClassTest│    │
│  │          │  │          │  │          │  │          │    │
│  │ parse    │  │ check    │  │ exec_graph│  │ test_cls │    │
│  │ write    │  │ edit     │  │ code_str  │  │ test_mth │    │
│  │ extract  │  │ update   │  │ code_flow │  │ test_all │    │
│  │ validate │  │ create   │  │ knowledge │  │ assert   │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   ClassErrors                         │   │
│  │                                                       │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │   │
│  │  │ Compare │→ │  Fix    │→ │  Test   │→ │Promote  │ │   │
│  │  │         │  │         │  │         │  │         │ │   │
│  │  │signature│  │candidate│  │run fix  │  │write BCL│ │   │
│  │  │match    │  │generate │  │verify   │  │sync DB  │ │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │   │
│  │                                                       │   │
│  │  Live Debug: halt → fix → write back → re-run         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## ClassErrors — The Self-Learning Loop

```
Error Occurs
    │
    ▼
┌─────────────────┐
│ 1. CAPTURE      │  Error text, traceback, file, line, class, method
│                 │  + execution graph context (from ClassGraph)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. SIGNATURE    │  Generate error signature (type + context hash)
│                 │  e.g. "AttributeError:MyClass.missing_method"
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. COMPARE      │  Search in-RAM cache + MySQL error_knowledge
│                 │  Match by signature or fuzzy match
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
   MATCH    NO MATCH
    │         │
    ▼         ▼
┌─────────┐ ┌─────────────────┐
│ 4a.     │ │ 4b. GENERATE    │  Use execution graph context
│ APPLY   │ │     CANDIDATE   │  + error type + fix templates
│ KNOWN   │ │     FIX         │  to generate candidate fix
│ FIX     │ └────────┬────────┘
└────┬────┘          │
     │               ▼
     │     ┌─────────────────┐
     │     │ 5. TEST FIX     │  Apply fix to in-RAM copy
     │     │                 │  Run py_compile / exec
     │     │                 │  Check if error is resolved
     │     └────────┬────────┘
     │              │
     │         ┌────┴────┐
     │         │         │
     │        PASS      FAIL
     │         │         │
     │         ▼         ▼
     │     ┌─────────┐ ┌─────────────────┐
     │     │ 6.      │ │ 6b. TRY NEXT    │  Try another candidate
     │     │ PROMOTE │ │     CANDIDATE   │  or escalate to manual
     │     │         │ └─────────────────┘
     │     │ write   │
     │     │ BCL to  │
     │     │ file    │
     │     │ sync    │
     │     │ MySQL   │
     │     └────┬────┘
     │          │
     └──────┬───┘
            │
            ▼
┌─────────────────┐
│ 7. TRACK        │  Record in fix_attempts
│                 │  Adjust confidence
│                 │  Update frequency
└─────────────────┘
```

## Live Debugging / Hot-Fix

The key feature the user remembers:

```
Execution Running
    │
    ▼
Error Occurs (halt execution)
    │
    ▼
┌─────────────────┐
│ CAPTURE context │  Current file, line, class, method
│                 │  + execution graph up to error point
│                 │  + variable state at error
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ FIND FIX        │  Compare to known errors
│                 │  Generate candidate if new
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ APPLY FIX       │  Modify code in-RAM
│                 │  Write fix to file as BCL packet
│                 │  [@ERROR_FIX]{[@SIGNATURE]{...}[@FIX]{...}}
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RE-RUN          │  Re-execute from error point
│                 │  If pass → continue execution
│                 │  If fail → try next fix or halt
└─────────────────┘
```

## BCL Format for Error Fixes

Error fixes are written as BCL packets in the same Python file:

```python
#[@ERROR_FIX]{[@SIGNATURE]{AttributeError:MyClass.missing_method}
#[@ERROR_TYPE]{AttributeError}
#[@CLASS]{MyClass}
#[@METHOD]{missing_method}
#[@CAUSE]{Object does not have the requested attribute}
#[@SOLUTION]{Check __init__ for self.attr assignment}
#[@FIX_CODE]{self.attr = None  # add to __init__}
#[@CONFIDENCE]{0.92}
#[@FREQUENCY]{2}
#[@LAST_SEEN]{2026-07-04 12:00:00}
#[@STATUS]{promoted}}
```

## File Structure

```
core/Dom_Common/
├── DESIGN.md           ← this document
├── __init__.py         ← exports all 5 classes
├── ClassBCL.py         ← BCL packet parser/writer
├── ClassRules.py       ← rule checking, editing, updating, creating
├── ClassGraph.py       ← wraps Reports v4 execution graph / code structure
├── ClassTest.py        ← wraps ClassTester for in-Python testing
├── ClassErrors.py      ← self-learning error→fix system with live debugging
└── Config.py           ← shared constants (MySQL config, paths, dimensions)
```

## Integration Points

- **C BCL units** → call ClassBCL via subprocess (bcl_tool) for BCL parsing
- **Python domains** → import Dom_Common classes directly
- **Reports v4** → ClassGraph calls `bcl_tool reports execution_graph` / `code_structure`
- **MySQL** → ClassErrors syncs with error_knowledge, fix_attempts, learned_rules
- **Live debugging** → ClassErrors hooks into Python execution via try/except + exec()

## Config

Config.py holds shared constants:
- MySQL connection (host, user, pass, socket, port, db)
- BCL tool path (Cascade_toolStack/bcl_units/bcl_tool)
- Neural model dimensions (INPUT_DIM=40, HIDDEN_DIM=64, OUTPUT_DIM=16)
- Error types (16 standard Python error types)
- Fix actions (16 fix action categories)
- Confidence thresholds (min_confidence=0.5, promote_threshold=0.8)
- Live debug settings (max_retries=3, halt_on_error=True)
