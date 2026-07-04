# AST Code Intelligence — Master Plan

## Current State (Layer 1: AST Structure)

| Component | Status | Store |
|-----------|--------|-------|
| File metrics (lines, imports, BCL, score, grade) | DONE | SQLite + MySQL |
| Function/method definitions (9,783 rows) | DONE | SQLite v2 normalized |
| Class registry (732 classes) | DONE | SQLite v2 |
| Complexity metrics (cyclomatic, nesting, branches) | DONE | SQLite v2 |
| Call names inside functions | DONE (text, not resolved) | SQLite v2 |
| Dead code detection (empty, pass-only) | DONE | SQLite v2 |
| Dependency graph (file-level imports) | DONE | SQLite + MySQL |
| Change tracking (file-level) | DONE | SQLite + MySQL |
| Boilerplate filtering (main, __init__, etc) | DONE | SQLite v2 |

## What's Missing — 16 Gaps

### Layer 2: Symbol Table
- **What:** Variable types, resolved names, scope mapping per function
- **Why:** Know what each identifier refers to — local, arg, global, imported, builtin
- **How:** Walk AST, track Name nodes, resolve to scope (arg/local/global/import/builtin)
- **Table:** `ci_symbols` (def_id, name, scope, resolved_type, line)

### Layer 3: Control Flow Graph (CFG)
- **What:** Possible execution paths through each function
- **Why:** Find unreachable code, all exit points, path count
- **How:** Build basic blocks from AST, connect with branch edges
- **Table:** `ci_cfg_blocks` (block_id, def_id, start_line, end_line, type)
- **Table:** `ci_cfg_edges` (from_block, to_block, condition)

### Layer 4: Data Flow Graph (DFG)
- **What:** How variables flow — origin, mutation, usage
- **Why:** Track taint, find unused assignments, detect mutations
- **How:** Track Assign → Name → Read chains through function body
- **Table:** `ci_data_flow` (def_id, var_name, origin_line, mutated_at, used_at, is_arg)

### Layer 5: Intermediate Representation (IR)
- **What:** Language-independent representation of each function
- **Why:** Enables cross-language analysis, BCL compilation, pattern matching
- **How:** Convert AST body to flat instruction list (assign, call, branch, return)
- **Table:** `ci_ir` (def_id, seq, opcode, operand1, operand2, operand3)

### Layer 6: Call Graph (Resolved Edges)
- **What:** Function A in file X calls function B in file Y — resolved
- **Why:** True dependency analysis, impact analysis, cycle detection at function level
- **How:** Match call_names to def_names across files using import graph
- **Table:** `ci_call_edges` (caller_def_id, callee_def_id, callee_name, is_cross_file)

### Layer 7: BCL Mapping
- **What:** Each definition mapped to BCL tags and compliance
- **Why:** Know which functions have BCL, which are missing it, BCL score per def
- **How:** Read BCL headers from file, map to function range
- **Columns on ci_definitions:** bcl_tags, bcl_score, bcl_compliant

### Scoring (Per-Function)
- **What:** Score and grade for every definition, not just files
- **Why:** Rank functions by quality, find worst functions to refactor
- **How:** Apply scoring formula: complexity + nesting + length + issues - docstring - BCL
- **Columns on ci_definitions:** score, grade (already exist, currently zero)

### Change Tracking (Function-Level)
- **What:** Which functions were added/modified/deleted between runs
- **Why:** Track code evolution at function granularity
- **How:** Hash function body text, compare between runs
- **Table:** `ci_def_changes` (run_id, def_id, change_type, old_hash, new_hash)

### Cross-File Call Resolution
- **What:** When func A in file X calls func B in file Y — the resolved edge
- **Why:** True impact analysis — "if I change B, what breaks?"
- **How:** Use import graph + def name matching to resolve calls
- **Part of:** ci_call_edges

### Class Hierarchy
- **What:** Inheritance tree — parent classes, MRO, overridden methods
- **Why:** Know which methods override, which are new, polymorphism analysis
- **How:** Parse ClassDef bases, resolve to class_ids, build tree
- **Columns on ci_classes:** bases (text), parent_class_id (FK)
- **Table:** `ci_class_hierarchy` (class_id, parent_class_id, depth)

### Import Graph (in def store)
- **What:** File-level import edges stored alongside definitions
- **Why:** Resolve cross-file calls, build module dependency graph
- **How:** Already in ast_ranker graph, need to persist to def store
- **Table:** `ci_imports` (file_id, imported_module, is_local, resolved_file_id)

### Decorators Resolved
- **What:** What each decorator does — property, staticmethod, classmethod, dataclass
- **Why:** Know if method is getter/setter, if class is dataclass, if method is async
- **How:** Map decorator names to known categories
- **Column on ci_definitions:** decorator_types (property, staticmethod, classmethod, dataclass, other)

### Return Paths
- **What:** All return statements in a function, inferred return types
- **Why:** Know what a function produces, detect missing returns, inconsistent returns
- **How:** Walk AST for Return nodes, infer type from returned expression
- **Table:** `ci_returns` (def_id, line, returns_type, is_explicit)

### Exception Paths
- **What:** What exceptions each function can raise
- **Why:** Know failure modes, find unhandled exceptions, error propagation chains
- **How:** Walk AST for Raise nodes, match exception types
- **Table:** `ci_raises` (def_id, line, exception_type, is_explicit)

### Mutation Analysis
- **What:** Which arguments get mutated, which are read-only
- **Why:** Know side effects of function calls, detect unsafe patterns
- **How:** Track arg names through Assign/AugAssign/Attribute writes
- **Table:** `ci_arg_mutations` (def_id, arg_name, mutated, mutation_count)

### Side Effects
- **What:** File I/O, network, DB calls detected in function body
- **Why:** Know which functions are pure, which have side effects
- **How:** Match call names to known I/O patterns (open, write, send, execute, etc)
- **Column on ci_definitions:** side_effects (none, io, network, db, mixed)

## Build Order (Priority)

| Phase | Gap | Effort | Value |
|-------|-----|--------|-------|
| 1 | Per-function scoring | Small | HIGH — every def gets score/grade |
| 2 | Call graph resolved edges | Medium | HIGH — true impact analysis |
| 3 | Class hierarchy | Small | MEDIUM — inheritance tree |
| 4 | Decorators resolved | Small | MEDIUM — property/static/classmethod |
| 5 | Return paths | Small | MEDIUM — what functions produce |
| 6 | Exception paths | Small | MEDIUM — failure modes |
| 7 | Side effects detection | Small | MEDIUM — pure vs impure |
| 8 | Import graph in def store | Small | HIGH — cross-file resolution |
| 9 | Change tracking (def-level) | Medium | HIGH — evolution tracking |
| 10 | BCL mapping per def | Medium | HIGH — BCL compliance per function |
| 11 | Symbol table | Large | MEDIUM — type inference |
| 12 | CFG | Large | HIGH — unreachable code, path analysis |
| 13 | Data flow | Large | HIGH — taint, mutation tracking |
| 14 | IR | Large | MEDIUM — cross-language, BCL compilation |
| 15 | Mutation analysis | Medium | LOW — arg side effects |
| 16 | Cross-file call resolution | Medium | HIGH — combines call graph + import graph |

## Target Schema (v3)

```
ci_runs
ci_files
ci_classes
  + bases, parent_class_id
ci_class_hierarchy (new)
ci_definitions
  + bcl_tags, bcl_score, bcl_compliant
  + decorator_types
  + side_effects
  + score, grade (populate, not just zero)
ci_imports (new)
ci_call_edges (new)
ci_returns (new)
ci_raises (new)
ci_symbols (new, L2)
ci_cfg_blocks (new, L3)
ci_cfg_edges (new, L3)
ci_data_flow (new, L4)
ci_ir (new, L5)
ci_def_changes (new)
ci_arg_mutations (new)
```

## Query Power After All Phases

```sql
-- "What breaks if I change function X?"
SELECT caller_name, caller_file FROM ci_call_edges WHERE callee_def_id = ?;

-- "Which functions have no docstring AND high complexity?"
SELECT name, file_path, cyclomatic FROM ci_definitions
WHERE has_docstring = 0 AND cyclomatic > 10 ORDER BY cyclomatic DESC;

-- "Which functions are pure (no side effects)?"
SELECT name, file_path FROM ci_definitions WHERE side_effects = 'none';

-- "Which functions can raise but don't catch?"
SELECT d.name, r.exception_type FROM ci_raises r
JOIN ci_definitions d ON r.def_id = d.def_id
WHERE d.def_id NOT IN (SELECT def_id FROM ci_definitions WHERE tries > 0);

-- "What did I change since last scan?"
SELECT * FROM ci_def_changes WHERE run_id = ?;

-- "Which methods override parent?"
SELECT c.name, c.file_path, p.name as parent_class
FROM ci_definitions d
JOIN ci_classes c ON d.class_id = c.class_id
JOIN ci_class_hierarchy h ON c.class_id = h.class_id
JOIN ci_classes p ON h.parent_class_id = p.class_id
WHERE d.name IN (SELECT name FROM ci_definitions WHERE class_id = p.class_id);
```
