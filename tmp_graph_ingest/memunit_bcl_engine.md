# MemUnit: Central BCL Execution Engine

## Origin

This document is the fourth design group — the **MemUnit base class design**.
MemUnit is the central execution engine that owns the BCL parser, dispatch,
validation, and result wrapping. Every VBStyle class inherits from it.

The idea: BCL parser lives in ONE place (MemUnit), not duplicated across
224 classes. Subclasses only define action names, param schemas, and method bodies.

---

# The Problem: Current State

Right now, every class has its own dispatch table inside `Run()`:

```python
class GraphEngine:
    def Run(self, command, params):
        dispatch = {
            "plan": self.PlanView,
            "spec": self.SpecView,
            "search": self.Search,
            ...
        }
        handler = dispatch.get(command)
        return handler(params)
```

```python
class CascadeEngine:
    def Run(self, command, params):
        dispatch = {
            "start": self.Start,
            "validate": self.Validate,
            ...
        }
        handler = dispatch.get(command)
        return handler(params)
```

**224 classes, 224 dispatch tables, 224 copies of the same pattern.**

No central parser. No central validation. No BCL in/out. Each class reinvents
the same wheel.

---

# The Solution: MemUnit as Base Class

```
MemUnit (base class — ONE copy)
  ├── BCL parser (parse input token)
  ├── DISPATCH builder (auto-build from ACTIONS)
  ├── Param validator (check required params)
  ├── Result wrapper (wrap Tuple3 into BCL output)
  └── Cleanup (post-execution cleanup)
  
Subclasses only define:
  ├── ACTIONS = {"command": ("param1", "param2"), ...}
  └── Method bodies (def Search(self, params): ...)
```

## How It Works

```
Input:  [@Run]{("command";"search");("query";"mysql");("limit";50)}
         |
         v
MemUnit.Run(bcl_token)
         |
         ├── 1. PARSE: BCL token → command + params dict
         |      command = "search"
         |      params = {"query": "mysql", "limit": 50}
         |
         ├── 2. VALIDATE: check params against ACTIONS schema
         |      ACTIONS["search"] = ("query", "domain", "limit")
         |      "query" is present ✓
         |      "limit" is present ✓
         |      "domain" is optional (not in required list)
         |
         ├── 3. DISPATCH: lookup method from command
         |      handler = self.Search
         |
         ├── 4. EXECUTE: call handler(params)
         |      result = self.Search({"query": "mysql", "limit": 50})
         |      result = (1, {"results": [...]}, "")
         |
         ├── 5. WRAP: Tuple3 → BCL output
         |      ok=True  → [@Pass]{("data";{"results":[...]})}
         |      ok=False → [@Fail]{("error";"not found")}
         |
         └── 6. CLEANUP: post-execution state reset
                  |
                  v
Output: [@Pass]{("data";{"results":[...]})}
```

---

# MemUnit Class Design

## VBStyle Header

```
# [@GHOST]
# Ghost header — MemUnit
# Purpose: Central BCL execution engine. Owns parser, dispatch, validation.
# Layer: Base class. Every VBStyle class inherits from MemUnit.
# Contract: Run(bcl_input) → bcl_output. BCL in, BCL out.
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37),
#        @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24),
#        @underscore(19), @run(43), @t3(50), @state(41), @ctor(40),
#        @memunit(32), @dismap(31), @enums(21), @hidden(23)
```

## Core Structure

```python
class MemUnit:
    """Base class. BCL parser + dispatch + validation + cleanup.
    
    Subclasses define:
      ACTIONS    — dict mapping command strings to param tuples
      Method bodies — def MethodName(self, params) → (ok, data, error)
    
    MemUnit handles:
      Parse     — BCL input → command + params
      Validate  — check params against ACTIONS schema
      Dispatch  — route to correct method
      Wrap      — Tuple3 → BCL output
      Cleanup   — post-execution state reset
    """
    
    ACTIONS = {}  # subclass overrides
    
    def __init__(self):
        self.state = {}
    
    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error).
        
        Accepts TWO input forms:
          1. Python: Run("search", {"query": "mysql"})
          2. BCL:    Run("[@Run]{(\"command\";\"search\");(\"query\";\"mysql\")}")
        
        Returns Tuple3 always.
        """
        if isinstance(command, str):
            # Python form — direct dispatch
            return self._Execute(command, params or {})
        else:
            # BCL form — parse first
            parsed = self._ParseBcl(command)
            return self._Execute(parsed["command"], parsed["params"])
    
    def _Execute(self, command, params):
        """Validate → Dispatch → Execute → Return."""
        # 1. Validate command exists
        if command not in self.ACTIONS:
            return (0, None, "unknown_command: " + str(command))
        
        # 2. Validate required params
        required = self.ACTIONS[command]
        for key in required:
            if key not in params:
                return (0, None, "missing_param: " + key)
        
        # 3. Dispatch
        method_name = self._CommandToMethod(command)
        handler = getattr(self, method_name, None)
        if handler is None:
            return (0, None, "no_method: " + method_name)
        
        # 4. Execute
        try:
            result = handler(params)
        except Exception as exc:
            return (0, None, "execution_error: " + str(exc))
        
        # 5. Cleanup
        self._Cleanup()
        
        # 6. Return Tuple3
        return result
    
    def _CommandToMethod(self, command):
        """Convert command string to method name.
        'search' → 'Search'
        'add_class' → 'AddClass'
        'status' → 'Status'
        """
        return "".join(word.capitalize() for word in command.split("_"))
    
    def _Cleanup(self):
        """Post-execution cleanup. Override in subclass if needed."""
        pass
    
    def _ParseBcl(self, bcl_text):
        """Parse BCL token → command + params dict.
        Uses BCL parser from BCL/bcl_parser.py.
        """
        from bcl_parser import parse_text
        ast = parse_text(bcl_text)
        root = ast.children[0] if ast.children else ast
        
        command = ""
        params = {}
        
        for tup in root.tuples:
            if len(tup) >= 2 and tup[0] == "command":
                command = tup[1]
            elif len(tup) >= 2:
                params[tup[0]] = tup[1]
        
        return {"command": command, "params": params}
    
    def _WrapResult(self, ok, data, error):
        """Wrap Tuple3 into BCL output token."""
        if ok:
            return '[@Pass]{("data";' + str(data) + ')}'
        else:
            return '[@Fail]{("error";"' + error + '")}'
```

## Subclass Example: GraphEngine

```python
class GraphEngine(MemUnit):
    """Graph views + algorithms executor. GATED by CascadeEngine."""
    
    ACTIONS = {
        "plan": ("domain",),
        "spec": ("domain",),
        "flow": ("domain",),
        "lifecycle": (),
        "dependency": (),
        "error": (),
        "orchestration": (),
        "gap": ("domain",),
        "inspect": ("filepath",),
        "verify": (),
        "bfs": ("start_node",),
        "dfs": ("start_node",),
        "cycle": (),
        "path": ("start_node", "end_node"),
        "topology": (),
        "search": ("query",),
        "instructions": (),
        "code": (),
        "add_class": ("name", "domain"),
        "remove_class": ("name",),
        "status": (),
    }
    
    def __init__(self):
        super().__init__()
        self.state["db_path"] = cfg.DB_PATH
        self.state["domain"] = cfg.DOMAIN
    
    def PlanView(self, params):
        domain = params.get("domain", self.state["domain"])
        # ... query DB, build result ...
        return (1, {"view": "plan", "steps": steps}, None)
    
    def Search(self, params):
        query = params["query"]
        # ... search logic ...
        return (1, {"results": results}, None)
    
    def Status(self, params):
        return (1, {"nodes": count, "edges": count}, None)
```

**No dispatch table. No parser. No validation code. Just ACTIONS + methods.**

---

# BCL Input/Output Contract

## Input Form 1: Python (direct)

```python
ge = GraphEngine()
ok, data, err = ge.Run("search", {"query": "mysql"})
```

## Input Form 2: BCL (parsed)

```python
ge = GraphEngine()
bcl_input = '[@Run]{("command";"search");("query";"mysql")}'
ok, data, err = ge.Run(bcl_input, None)
```

## Output: Always Tuple3

```python
(1, {"results": [...]}, "")       # success
(0, None, "missing_param: query")  # failure
```

## BCL Output (optional wrap)

```
[@Pass]{("data";{"results":[...]})}     # success
[@Fail]{("error";"missing_param: query")}  # failure
```

---

# The 6-Stage MemUnit Pipeline

From MySQL rule id=223: "MemUnit owner of param validate execute cleanup"

```
Stage 1: PARSE
  Input: BCL token OR Python (command, params)
  Output: command string + params dict
  Owner: MemUnit._ParseBcl() or direct

Stage 2: VALIDATE
  Input: command + params
  Check: command exists in ACTIONS
  Check: required params present
  Output: (ok, validated_params) or (fail, error)
  Owner: MemUnit._Execute()

Stage 3: DISPATCH
  Input: validated command
  Action: convert command → method name
  Action: getattr(self, method_name)
  Output: handler reference
  Owner: MemUnit._CommandToMethod()

Stage 4: EXECUTE
  Input: handler + params
  Action: handler(params)
  Output: Tuple3 (ok, data, error)
  Owner: subclass method body

Stage 5: WRAP (optional)
  Input: Tuple3
  Action: convert to BCL token if BCL output needed
  Output: [@Pass]{...} or [@Fail]{...}
  Owner: MemUnit._WrapResult()

Stage 6: CLEANUP
  Input: execution state
  Action: reset temporary state, close connections
  Output: clean state
  Owner: MemUnit._Cleanup() or subclass override
```

---

# ACTIONS Schema Design

## Format

```python
ACTIONS = {
    "command_name": ("required_param1", "required_param2"),
}
```

- Key = command string (what the caller sends)
- Value = tuple of required param names
- Optional params are NOT listed (method uses params.get() with default)

## Examples

```python
# GraphEngine
ACTIONS = {
    "search": ("query",),           # requires query, domain optional
    "path": ("start_node", "end_node"),  # requires both
    "status": (),                   # no params required
}

# CascadeEngine
ACTIONS = {
    "start": ("idea",),             # requires idea, spec_path optional
    "validate": ("run_id",),        # requires run_id
    "commit": ("run_id",),          # requires run_id
    "status": (),                   # no params
}

# DecisionEngine
ACTIONS = {
    "start": (),
    "step": (),
    "auto": (),
    "end": (),
    "status": (),
}
```

## Command-to-Method Mapping

```
"search"       → Search()
"add_class"    → AddClass()
"start_node"   → StartNode()  (unlikely, but follows rule)
"status"       → Status()
"plan"         → Plan()
"bfs"          → Bfs()
"dfs"          → Dfs()
```

Rule: `command.split("_")` → capitalize each word → join. Simple, deterministic.

---

# What Subclasses NO LONGER Need

## Before (current pattern — every class):

```python
class GraphEngine:
    def __init__(self):
        self.state = {"db_path": "...", "domain": "..."}
    
    def Run(self, command, params):
        if params is None:
            params = {}
        dispatch = {
            "plan": self.PlanView,
            "spec": self.SpecView,
            "search": self.Search,
            # ... 20 entries
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: " + command)
        return handler(params)
    
    def PlanView(self, params): ...
    def Search(self, params): ...
```

## After (with MemUnit):

```python
class GraphEngine(MemUnit):
    ACTIONS = {
        "plan": ("domain",),
        "spec": ("domain",),
        "search": ("query",),
        # ... just the schema
    }
    
    def __init__(self):
        super().__init__()
        self.state["db_path"] = "..."
        self.state["domain"] = "..."
    
    def Plan(self, params): ...    # was PlanView
    def Search(self, params): ...
```

**Removed from every subclass:**
- `Run()` method (inherited from MemUnit)
- Dispatch table (auto-built from ACTIONS)
- Param None check (MemUnit handles)
- Unknown command check (MemUnit handles)
- Error wrapping (MemUnit handles)

**Kept in subclass:**
- `ACTIONS` dict (schema only)
- `__init__()` (state setup)
- Method bodies (actual logic)

---

# Migration Path

## Phase 1: Create MemUnit base class
- Write `MemUnit.py` with BCL parser integration
- Write `_Execute`, `_CommandToMethod`, `_ParseBcl`, `_WrapResult`, `_Cleanup`
- Test standalone with mock subclass

## Phase 2: Migrate GraphEngine
- Add `class GraphEngine(MemUnit):`
- Replace `Run()` with `ACTIONS` dict
- Rename methods if needed (PlanView → Plan)
- Test: `ge.Run("search", {"query": "mysql"})` still works

## Phase 3: Migrate remaining classes
- CascadeEngine, DecisionEngine, Inspect, Verify, GraphViewer
- GraphOrchestrator (special — forwards to other MemUnits)
- One class at a time, test after each

## Phase 4: Migrate vb_code_test classes
- 224 classes in MySQL — these are the bulk
- Can be auto-migrated: extract dispatch table → generate ACTIONS dict
- Use the Fast Method (in-memory SQLite) for batch migration

## Phase 5: Enable BCL input/output
- MemUnit already supports both Python and BCL input
- Enable BCL output wrapping for inter-system communication
- Now any MemUnit can receive BCL from any other MemUnit

---

# MySQL References: MemUnit in the Knowledge Base

## vb_shared.rules (6 hits)

| id | rule | description |
|----|------|-------------|
| 2 | Fixed 5-element state structure | self.state = {config: {}, catalog: [], results: [], memunit: mem, db_manager: db} |
| 15 | Run method dispatch pattern | Outer Run dispatches to nested authorities: return self.AuthorityName(mem=self.state[memunit], db=self.state[db_manager], param=params).Run(subcommand) |
| 32 | hidden | no hidden or implicit behavior all actions explicit |
| 41 | memunit | all code execute only in memunit |
| 223 | MemUnit owner of param validate execute cleanup | Must: MemUnit owner of param validate execute cleanup |
| 268 | Methods must declare capability metadata | Every method must declare domain, input type, output type, cost, execution stage. MEMUNIT uses this metadata for resolution. |
| 269 | MEMUNIT resolves all binding | No class ever binds itself. No method ever belongs to a class. Everything is resolved at runtime by MEMUNIT during orchestration graph construction. |

## vb_shared.learned_rules (15 hits)

| id | pattern | fix_action | category | confidence |
|----|---------|------------|----------|------------|
| 16649 | replace working memunit methods | prohibition | general | 0.7 |
| 18456 | ensure code follows rule: memunit | requirement | general | 0.95 |
| 18624 | memunit owner of param validate execute cleanup | requirement | general | 0.95 |
| 18670 | memunit resolves all binding | requirement | general | 0.95 |
| 19066 | class with run must declare memunit authority | prohibition | architecture | 0.95 |
| 19080 | fix: add_memunit_decl (applied 24 times) | fix | correctness | 0.95 |
| 19435 | execution goes through memunit | fix | general | 0.7 |
| 19453 | run unit files directly. memunit | prohibition | general | 0.7 |
| 19461 | self-run and do not bypass memunit | prohibition | general | 0.7 |
| 19518 | need you to re-explain memunit every time | prohibition | general | 0.7 |
| 19519 | self-run, must route through memunit | prohibition | general | 0.7 |
| 19938 | write a replacement memunit unless explicitly ordered | prohibition | general | 0.7 |
| 24049 | implement class: memunit | requirement | architecture | 0.7 |
| 24875 | class brackets: contract definition layer, table inside memunit init | requirement | architecture | 0.7 |
| 24884 | bracket annotation for memunit | requirement | general | 0.7 |

## vb_shared.tokens (2 hits)

| id | name | meaning |
|----|------|---------|
| 2289 | [@CascadeSearchMemDb] | [@Pass]{("VBStyle architecture. MemDB SQLite in-memory. Hardware-aware threads.";92)}[@Fail]{("Original is C/C++ only. Must adapt for Python/Swift/MD";} |
| 2305 | [@bcl-command] | BCL Command form — executes action, active, run through MemUnit |

## Key Rules Summary

1. **All execution goes through MemUnit** (rule 41, id=19435) — no bypassing
2. **MemUnit owns: param → validate → execute → cleanup** (rule 223, id=18624)
3. **MemUnit resolves all binding** (rule 269, id=18670) — no class binds itself
4. **Class with Run must declare MemUnit authority** (id=19066) — mandatory
5. **Do not replace working MemUnit methods** (id=16649) — prohibition
6. **Do not write replacement MemUnit unless ordered** (id=19938) — prohibition
7. **BCL commands run through MemUnit** (token id=2305) — active form
8. **Implement class: MemUnit** (id=24049) — this is a PENDING requirement
9. **Methods declare capability metadata** (rule 268) — domain, input, output, cost, stage
10. **No hidden behavior** (rule 32) — all actions explicit

## Critical Finding

Rule id=24049 ("implement class: memunit") is a **pending requirement** —
the knowledge base has been asking for MemUnit to be implemented as a real
class for some time. This document is the design for that implementation.

The learned_rules show MemUnit has been discussed 15 times, with rules about:
- Not bypassing it (id=19453, 19461, 19519)
- Not replacing it (id=16649, 19938)
- Requiring it (id=18456, 18624, 18670, 24049)
- Fixing code to declare it (id=19080 — applied 24 times!)

The fix `add_memunit_decl` was applied 24 times (id=19080, confidence 0.7),
meaning 24 classes were patched to declare MemUnit authority. This confirms
the pattern is real and enforced, but the base class itself was never built.

---

# Existing BCL Parser (Already Built)

The BCL parser already exists at `BCL/bcl_parser.py`:

```
BCL/bcl_lexer.py     — tokenizer (text → tokens)
BCL/bcl_parser.py    — recursive descent parser (tokens → BCLNode AST)
BCL/bcl_validator.py — validates AST against rules
BCL/bcl_fixer.py     — fixes common BCL issues
BCL/bcl_engine.py    — evaluation engine
BCL/bcl_config.py    — BCL config form parser
```

### BCLParser features:
- `BCLNode` class with `name`, `tuples`, `children`, `parent`
- `node.get("key")` — read value from tuples
- `node.set("key", "value")` — update tuple value
- `node.to_bcl()` — serialize back to BCL text (round-trip)
- `parse_text(text)` — convenience: text → AST

### MemUnit integration:
```python
from bcl_parser import parse_text

def _ParseBcl(self, bcl_text):
    ast = parse_text(bcl_text)
    root = ast.children[0] if ast.children else ast
    command = ""
    params = {}
    for tup in root.tuples:
        if len(tup) >= 2 and tup[0] == "command":
            command = tup[1]
        elif len(tup) >= 2:
            params[tup[0]] = tup[1]
    return {"command": command, "params": params}
```

The parser is already built. MemUnit just needs to USE it.

---

# Design Decisions

## Why BCL input AND Python input?

MemUnit accepts both forms:
```python
# Python (for internal calls)
ge.Run("search", {"query": "mysql"})

# BCL (for inter-system / external calls)
ge.Run('[@Run]{("command";"search");("query";"mysql")}', None)
```

Python form is for class-to-class calls (fast, no parse overhead).
BCL form is for external input (tokens from MySQL, chat, other systems).

## Why ACTIONS dict instead of decorators?

VBStyle rule `@decorators(20)` prohibits decorators. So instead of:

```python
@action("search", requires=("query",))
def Search(self, params): ...
```

We use:

```python
ACTIONS = {
    "search": ("query",),
}

def Search(self, params): ...
```

Plain dict, plain methods. No decorator magic.

## Why not enums for commands?

VBStyle rule `@enums(21)` prohibits enums. Commands are strings:

```python
ACTIONS = {"search": ("query",)}    # ✓ string keys
```

Not:

```python
class Command(Enum):
    SEARCH = "search"               # ✗ prohibited
```

## Why _CommandToMethod instead of explicit mapping?

Auto-conversion is deterministic and removes boilerplate:

```
"search"     → "Search"      → self.Search
"add_class"  → "AddClass"    → self.AddClass
"status"     → "Status"      → self.Status
```

No need for a separate method mapping dict. The command name IS the method name
(just capitalized). If a method needs a different name, override `_CommandToMethod`.

---

# Summary

```
Before:  224 classes × (Run + dispatch + validate + error handling) = 224 copies
After:   1 MemUnit + 224 classes × (ACTIONS + methods) = 1 copy of logic

Before:  Each class reinvents dispatch
After:   MemUnit owns dispatch, subclass owns logic

Before:  No BCL input support
After:   BCL and Python input both supported

Before:  No central param validation
After:   MemUnit validates against ACTIONS schema

Before:  No central cleanup
After:   MemUnit calls _Cleanup() after every execution
```

**One parser. One dispatch. One validation. One cleanup. 224 subclasses.**
