<!-- [@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<VBStyle cleanup lessons learned iteration log. Documents database refactoring approach, knowledge model, backup rules. No VBStyle violations (markdown doc).>][@todos<none>]} -->
# VBStyle Cleanup — Lessons Learned (Iteration Log)

## Context
Refactoring Dom_Graph Python files in SQLite database (`dom_graph_work.db`).
Goal: Remove all VBStyle violations (print, decorators, self._, missing Run(), etc.)
All work done in the database using the Fast Method.

## LESSON 0: BACKUP FIRST (NON-NEGOTIABLE)
```
Question: "Are you about to modify the database?"
Answer:   "Copy the .db file BEFORE any operation. No exceptions."

Question: "Do you have a verified backup?"
Answer:   "Hash both copies. If hashes match, proceed. If not, stop."

Question: "Is the backup read-only?"
Answer:   "chmod 444 backup.db — prevent accidental modification."

Question: "Can you restore from backup?"
Answer:   "Test restore before proceeding. Untested backup = no backup."
```
**Rule:** Before ANY write operation to the database:
1. `cp dom_graph_work.db dom_graph_work.bak.db`
2. `chmod 444 dom_graph_work.bak.db`
3. Verify both files have same hash
4. Only then proceed with modifications
5. If anything breaks: `cp dom_graph_work.bak.db dom_graph_work.db`

## KNOWLEDGE MODEL: PROBLEMS → QUESTIONS → ANSWERS
Every problem encountered generates questions. Each question has multiple possible answers.
The knowledge table stores this as Q&A pairs:

```
PROBLEM: "print() inside dict literal causes SyntaxError"

  QUESTION 1: "Is this line an actual print() call or a string literal?"
    ANSWER 1a: "Check lstrip().startswith('print(') — only match actual calls"
    ANSWER 1b: "Check paren depth — if inside dict, don't touch"
    ANSWER 1c: "Use AST parse to distinguish code from string context"
    BEST: 1a (simplest, fastest, correct for 95% of cases)

  QUESTION 2: "What context is this line in?"
    ANSWER 2a: "Read previous line — if ends with { or comma, it's dict context"
    ANSWER 2b: "Track paren depth from start of statement"
    ANSWER 2c: "Parse the whole file with AST to get exact context"
    BEST: 2a (fast, no parsing needed)

  QUESTION 3: "How to fix the broken file after wrong removal?"
    ANSWER 3a: "Restore from backup, reapply with smarter matcher"
    ANSWER 3b: "Manually fix each broken line by reading context"
    ANSWER 3c: "Re-ingest original file, start over"
    BEST: 3a (fastest, guarantees clean state)
```

This means the knowledge table schema is:
- `problem` — what went wrong
- `question` — what we need to know to fix it
- `answer` — a possible solution
- `is_best` — which answer worked best
- `evidence` — proof it worked (compile result, test result)
- `confidence` — how sure we are (0-100)

## Final State
- **Files**: 17 `Dom_Graph_*.py` files + `Config.py` (all compile, all tests pass)
- **Tests**: 205 passed, 0 failed
- **Classes**: 38 (simple names: `SpecGraph`, `PlanGraph`, `Node`, `Edge`, etc.)
- **Methods**: 1,480
- **Config constants**: 42

## Iteration Log

### Iteration 1: Naive print() removal
**Approach:** `SELECT * FROM src WHERE text LIKE '%print(%'` → replace with `pass`
**Broke:** 4 files (EngineV2, Boot, Gui, Ingest)
**Root causes:**
1. **String literal false positives** — `"no_print": "No print() statements"` matched because `print(` appears inside a string value in a dict. Replacing with `pass` inside a dict literal = SyntaxError.
2. **Comment false positives** — Lines like `# print() is forbidden` matched.
3. **Multi-line print false positives** — `print(f"...\n"` spanning multiple lines. Only first line matched, leaving dangling `)`.
4. **Bare expression context** — `pass` after a bare string expression = `SyntaxError: illegal target for annotation`.

**Lesson:** Only match lines where `lstrip().startswith("print(")` — NOT `LIKE '%print(%'`.

### Iteration 2: Context-aware pass replacement
**Approach:** Check previous/next line to decide: dict entry → comment, if/except → pass, standalone → comment
**Broke:** Still 4 files — context detection imperfect
**Root causes:**
1. Dict entry detection missed entries where prev line doesn't end with comma
2. Multi-line function calls (`c.create_text(...)`) had print lines as part of argument concatenation — removing them broke the call
3. `pass` replaced inside `for` loop bodies that had more code → indentation errors

**Lesson:** Don't replace print() with pass at all. Instead:
- If print() is the ONLY statement in a block → replace with `pass`
- If print() is among other statements → DELETE the line entirely
- If print() spans multiple lines → delete ALL lines of the print call

### Iteration 3: Direct file fixing
**Approach:** Read broken files from disk, fix with string replacement, re-ingest
**Broke:** Nothing — but required manual inspection of each error
**Root causes found:**
1. **Stray dict entries** — `"no_print_statements": "No print() in VBStyle code",` appeared between an if block and a for loop — a dict value that was part of a print() call got partially replaced
2. **Multi-line string concatenation in function calls** — `c.create_text(50, y, text="Step " + str(step) + \n "  →  " + atk_type + \n font=("Courier", 8)...)` — the `+` before `font=` was from a print line that got removed, leaving `+` instead of `,`
3. **SQL INSERT params lost** — `c.execute("INSERT ... VALUES (?, ?, ...)", \n (class_name, class_code, ...))` — the params tuple was on a print line that got removed
4. **Stray f-string fragments** — Lines like `Source: MySQL vb_code_test (pulled {len(all_entities)} graph classes)` left orphaned from a multi-line print

**Lesson:** Print removal must understand multi-line context:
- Check if the line is inside a function call (paren depth > 0)
- Check if the line is a continuation of a previous line (ends with `+` or `,`)
- Check if the line is a SQL parameter tuple

### Iteration 4: Class name consistency
**Approach:** VBStyle cleanup renamed classes in DB (DomGraph* → simple names), wrote to disk
**Broke:** 23 test failures — Config.py FILE_REGISTRY and GRAPH_PIPELINE still had DomGraph* names
**Root cause:** The cleanup script renamed classes in source files but didn't update Config.py's registry constants

**Lesson:** When renaming classes, ALWAYS update:
1. `FILE_REGISTRY` in Config.py (keys are class names)
2. `GRAPH_PIPELINE` in Config.py (stage names are class names)
3. Test files that reference class names
4. `domain_loader.py` instantiation examples

### Iteration 5: Final alignment
**Approach:** Fix Config.py constants, fix test expectations, re-ingest, re-test
**Result:** 205 passed, 0 failed

## Rules Captured

### Print Removal Rules (CRITICAL)
1. **NEVER use `LIKE '%print(%'`** — matches string literals, comments, dict values
2. **ONLY match `lstrip().startswith("print(")`** — actual print() calls
3. **Check multi-line context** — if previous line ends with `+` or `,`, the print is part of a larger expression
4. **Check paren depth** — if inside a function call, removing a line breaks the call
5. **If print is only statement in block** → replace with `pass`
6. **If print is among other statements** → delete line
7. **Multi-line print** → delete ALL lines from `print(` to closing `)`

### Decorator Removal Rules
1. Match lines where `lstrip().startswith("@")` and contains `staticmethod|property|classmethod|abstractmethod`
2. Delete the line (text='')
3. Clean up consecutive empty lines after deletion

### Run() Insertion Rules
1. Find class start line
2. Find class end (next class or EOF)
3. Find last method in class
4. Find last method's end (first line with ≤4 spaces indent after method)
5. Insert Run() template at that position
6. Re-number all subsequent lines in that file

### Class Rename Rules
1. When renaming classes, ALWAYS update Config.py:
   - `FILE_REGISTRY` keys
   - `GRAPH_PIPELINE` stage names
2. Update test files that reference class names
3. Update `domain_loader.py` instantiation examples
4. Re-ingest and re-test after rename

### __init__ Signature Rules
1. VBStyle requires: `def __init__(self, mem=None, db=None, param=None)`
2. Existing classes have domain-specific params (root, conn, node_id, etc.)
3. Don't blindly replace — keep existing params if class is a data primitive
4. Run() dispatch is more important than __init__ signature for first pass

### self._ Rules
1. `self._` is forbidden in VBStyle — use `self.state` dict
2. SQL `LIKE '%self._%'` matches `self.id`, `self.type` (underscore is wildcard)
3. Must use `LIKE '%self\_%' ESCAPE '\'` or regex `\bself\._`
4. Most `self.xxx` attributes are fine — only `self._xxx` (underscore prefix) is forbidden

## File Status (Final)

| File | Lines | Compile | Notes |
|------|-------|---------|-------|
| Config.py | ~1031 | OK | Central config, all constants |
| Dom_Graph_Agent.py | ~2459 | OK | AgentGraph + Node/Edge/Goal classes |
| Dom_Graph_Boot.py | ~553 | OK | BootGraph + ExecutionGraph |
| Dom_Graph_Code.py | ~341 | OK | Node/Edge/TypedGraph |
| Dom_Graph_Dep.py | ~282 | OK | DepGraph |
| Dom_Graph_Engine.py | ~694 | OK | GraphEngine + CuriosityController + ReportMaker |
| Dom_Graph_EngineV2.py | ~814 | OK | GraphEngineV2 + ConstraintChecker + SolutionSuggester etc |
| Dom_Graph_Error.py | ~266 | OK | ErrorGraph |
| Dom_Graph_Flow.py | ~275 | OK | SpecFlow |
| Dom_Graph_Gap.py | ~544 | OK | GapGraph |
| Dom_Graph_Gui.py | ~1837 | OK | DbArchitectureGui |
| Dom_Graph_Ingest.py | ~307 | OK | IngestGraphFromMysql |
| Dom_Graph_Lifecycle.py | ~249 | OK | LifecycleGraph |
| Dom_Graph_Orch.py | ~302 | OK | OrchGraph |
| Dom_Graph_Plan.py | ~610 | OK | PlanGraph + PlanNode |
| Dom_Graph_Runtime.py | ~767 | OK | RuntimeTwinPopulate |
| Dom_Graph_Spec.py | ~331 | OK | SpecGraph |
| Dom_Graph_Viewer.py | ~409 | OK | GraphViewer |

## What Would Make This Automatic (Future Vision)

If we iterate this 1000x, we'd build:
1. **AST-aware print removal** — parse the file, find actual print() calls, remove them while preserving structure
2. **Multi-line call detector** — track paren depth to know if a line is inside a function call
3. **Auto-fix broken syntax** — after removal, compile, find errors, auto-fix (stray +, dangling ), missing params)
4. **Class rename propagator** — rename a class, auto-update all references in Config, tests, and other files
5. **VBStyle validator** — scan all files for violations, report exact line numbers, auto-fix
6. **One-shot cleanup script** — ingest, detect all violations, fix all, write, verify — in one run
