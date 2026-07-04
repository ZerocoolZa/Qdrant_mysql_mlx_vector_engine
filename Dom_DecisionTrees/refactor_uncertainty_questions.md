#[@GHOST]{file_path="Dom_DecisionTrees/refactor_uncertainty_questions.md" date="2026-08-18" author="Devin" session_id="decision-tree-refactor" context="20 questions to resolve uncertainty around DecisionTreeGui_v1.py refactor into multi-file VBStyle structure"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE BCL-in BCL-out Run dispatch no-print"}
#[@FILEID]{id="refactor_uncertainty_questions.md" domain="Dom_DecisionTrees" authority="UncertaintyNarrow"}
#[@SUMMARY]{summary="20 decision points for refactoring DecisionTreeGui_v1.py into app.py, canvas.py, tree_builder.py, Config.py, main_decision_trees.py"}
#[@CLASS]{class="UncertaintyNarrow" domain="Dom_DecisionTrees" authority="single"}
#[@METHOD]{method="Generate" type="question"}

# DecisionTreeGui_v1.py Refactor — 20 Uncertainty Questions

## Context
`DecisionTreeGui_v1.py` (1600+ lines, single file) is being refactored into:
- `app.py` — DecisionTreeApp class (main window)
- `canvas.py` — QGraphicsScene/View, TreeNode, JsonHighlighter
- `tree_builder.py` — TreeBuilder class (DB queries, tree construction)
- `Config.py` — constants, colors, stylesheet, paths
- `main_decision_trees.py` — entry point

Each question below has concrete options. Pick one per question.

---

## Architecture Decisions

### Q1. Who holds the DB connection?
- **A)** `TreeBuilder` holds `self.conn` — it owns all DB access, opens/closes internally
- **B)** `DecisionTreeApp` holds `self.conn` — passes `cur` to TreeBuilder methods as a parameter
- **C)** `DomSystem` holds the connection — both classes call `DomSystem.Run("query", ...)` and never touch sqlite3 directly
- **D)** `main_decision_trees.py` opens the connection — passes it to both app and tree_builder as constructor args

### Q2. Should TreeBuilder use DomSystem or raw sqlite3?
- **A)** Use `DomSystem.Run("query", sql)` for all DB access — follows the rule "use DomSystem for IO"
- **B)** Keep raw `sqlite3.connect()` — TreeBuilder is a leaf module, no need for DomSystem overhead
- **C)** Use DomSystem for reads, raw sqlite3 for writes — hybrid approach
- **D)** Use DomSystem only if it already supports SQLite (check first, then decide)

### Q3. Where is ErrorHandler created?
- **A)** Created in `main_decision_trees.py`, passed to `DecisionTreeApp` as constructor arg
- **B)** Created inside `DecisionTreeApp.__init__` as `self.error_handler`
- **C)** Created as a singleton in `ErrorHandler.py` module, imported everywhere
- **D)** Created in `TreeBuilder.__init__` since that is where most errors occur

### Q4. How does canvas.py get BCL_NODE_COLORS and NODE_RADIUS?
- **A)** Import directly from Config: `from Config import BCL_NODE_COLORS, NODE_RADIUS`
- **B)** Receive as constructor args: `CanvasScene(colors=BCL_NODE_COLORS, radius=NODE_RADIUS)`
- **C)** Read from `self.state` dict that Config populates at init
- **D)** Hardcode in canvas.py — they are visual constants, not config

### Q5. Where does JsonHighlighter live?
- **A)** Stays in `canvas.py` — it is a visual concern, belongs with canvas
- **B)** Moves to separate `highlighters.py` — reusable across other GUIs
- **C)** Moves to `core/Dom_Gui/highlighters.py` — shared GUI utility
- **D)** Moves to `Config.py` as a function that returns a styled QTextDocument

### Q6. Where does TreeNode live?
- **A)** Stays in `canvas.py` — it is a QGraphicsItem, belongs with canvas
- **B)** Moves to `tree_builder.py` — it is a tree structure concern
- **C)** Moves to separate `models.py` — shared data model used by both canvas and tree_builder
- **D)** Stays in `canvas.py` but tree_builder imports it from there

---

## Error Handling Decisions

### Q7. Which signal handlers get wrapped with ErrorHandler?
- **A)** Every signal handler — no exceptions, uniform safety net
- **B)** Only handlers that touch DB/IO — pure UI handlers (search filter, tab switch) do not need wrapping
- **C)** Only handlers that can raise exceptions (DB, file IO, JSON parse) — UI-only handlers skip it
- **D)** Wrap all by default, but use `ErrorHandler.Run("silent", ...)` for UI-only so it logs but does not popup

### Q8. How does ErrorHandler report errors?
- **A)** Always show `QMessageBox.critical()` — user must see every error
- **B)** Always log silently to status bar — no popups, ever
- **C)** Configurable per call: `ErrorHandler.Run("popup", ...)` vs `ErrorHandler.Run("silent", ...)` — caller decides
- **D)** Silent for warnings (status bar), popup for errors (QMessageBox) — severity-based

### Q9. What do TreeBuilder methods return?
- **A)** Return `Tuple3` directly: `(1, TreeNode, None)` or `(0, None, (code, desc, 0))`
- **B)** Return raw `TreeNode` — caller wraps in Tuple3 if needed
- **C)** Return `Tuple3` for queries, raw `TreeNode` for build steps — mixed based on operation type
- **D)** Return a dict: `{"ok": True, "node": TreeNode, "error": None}` — easier to debug than Tuple3

### Q10. Does ErrorHandler retry DB queries automatically?
- **A)** Yes — retry up to 3 times with 1-second delay, then report
- **B)** No — capture and report immediately, no retry logic
- **C)** Configurable: `ErrorHandler.Run("retry", ...)` for idempotent reads, `ErrorHandler.Run("once", ...)` for writes
- **D)** Retry only on `sqlite3.OperationalError: database is locked` — all other errors report immediately

---

## File Structure Decisions

### Q11. How are menus declared?
- **A)** Manual setup in `app.py` — `QMenuBar` code with `addAction()` calls
- **B)** WCL `[@MENU]` tags in a `.wcl` file — engine parses and builds menus
- **C)** Config-driven — `Config.MENUS` dict that `app.py` iterates to build menus
- **D)** No menus — use a toolbar with buttons instead (simpler, fewer moving parts)

### Q12. Where does apply_style() live?
- **A)** Stays as a method in `app.py` — `DecisionTreeApp.apply_style(self)`
- **B)** Moves to `Config.py` as `STYLESHEET` string constant — `app.setStyleSheet(Config.STYLESHEET)`
- **C)** Moves to separate `theme.py` module — `from theme import apply_style; apply_style(app)`
- **D)** Stays in `app.py` but reads values from `Config.py` (colors, fonts) — hybrid

### Q13. Where is the entry point (`if __name__ == "__main__"`)?
- **A)** `main_decision_trees.py` — separate entry point file, imports and runs `DecisionTreeApp`
- **B)** `app.py` — `DecisionTreeApp` file has the `if __name__` block at the bottom
- **C)** Both — `app.py` has it for standalone testing, `main_decision_trees.py` has it for production
- **D)** `main_decision_trees.py` only — `app.py` is importable, never run directly

### Q14. How is canvas.py structured?
- **A)** Single `canvas.py` file — `CanvasScene`, `CanvasView`, `TreeNode`, `JsonHighlighter` all in one
- **B)** Sub-package `canvas/` — `nodes.py` (TreeNode), `edges.py` (edge drawing), `view.py` (CanvasView), `scene.py` (CanvasScene)
- **C)** Single `canvas.py` for CanvasScene+CanvasView, separate `models.py` for TreeNode, separate `highlighters.py` for JsonHighlighter
- **D)** Single `canvas.py` — but TreeNode and JsonHighlighter move to `tree_builder.py` and `Config.py` respectively

---

## Behavior Preservation Decisions

### Q15. Fix the build_shell resize bug?
- **A)** Yes — fix `self.resize(int(parts[0]), int(parts[0]))` to `self.resize(int(parts[0]), int(parts[1]))`
- **B)** No — preserve v1 behavior exactly, even bugs, document it as known issue
- **C)** Fix it but add a config flag `PRESERVE_V1_BUGS = False` so it can be toggled
- **D)** Fix it and add a test that verifies both dimensions are used correctly

### Q16. Where does post_build() live?
- **A)** Method on `DecisionTreeApp` — `self.post_build()` — it orchestrates UI + DB
- **B)** Inline in `main_decision_trees.py` — run after `app.show()` in the entry point
- **C)** Method on `TreeBuilder` — `tree_builder.post_build(app)` — it is mostly DB queries
- **D)** Split: DB parts in `TreeBuilder.post_build_db()`, UI parts in `DecisionTreeApp.post_build_ui()`

### Q17. Where does load_bcl_engine() live?
- **A)** Stays in `app.py` — `DecisionTreeApp.load_bcl_engine(self)` — it is app initialization
- **B)** Moves to `tree_builder.py` — `TreeBuilder.load_bcl_engine(self)` — it is BCL-related
- **C)** Moves to separate `bcl_bridge.py` — dedicated module for BCL engine interaction
- **D)** Moves to `main_decision_trees.py` — run before app creation, pass engine to app

### Q18. Should closeEvent use ErrorHandler?
- **A)** Yes — wrap DB close and config save in `ErrorHandler.Run("consume", ...)` — safe shutdown
- **B)** No — closeEvent should be simple try/except, do not add ErrorHandler overhead to shutdown
- **C)** Only wrap the config save — DB close is safe (sqlite3 handles it), config save can fail on disk
- **D)** Wrap both but use silent mode — log errors but do not block window close with popups

---

## VBStyle Compliance Decisions

### Q19. Should canvas widgets follow full VBStyle?
- **A)** Yes — every file has `__init__(self, mem, db, param)`, `Run()`, `self.state`, Tuple3 returns
- **B)** No — PyQt subclasses (QGraphicsScene, QGraphicsItem) cannot follow VBStyle, exempt them
- **C)** Partial — `TreeBuilder` and `DecisionTreeApp` follow VBStyle, canvas widgets are exempt
- **D)** Partial — all files have GHOST/VBSTYLE/FILEID headers but only non-PyQt classes follow Run()/Tuple3

### Q20. Should DecisionTreeApp have a Run() dispatch?
- **A)** Yes — `Run(self, command, params)` dispatches to internal methods (`"build_tree"`, `"load_config"`, etc.)
- **B)** No — keep direct method calls (`app.build_tree()`, `app.load_config()`) — it is a GUI class, not a service
- **C)** Yes for DB operations, no for UI operations — `Run("query_db", ...)` but `app.show_tree()` directly
- **D)** Yes — but only for external callers (main_decision_trees.py calls `app.Run("init", ...)`), internal methods stay direct

---

## Highest-Impact Questions (answer these first)

| Priority | Question | Why it matters |
|----------|----------|----------------|
| 1        | Q2       | DomSystem vs raw sqlite3 changes every DB call in TreeBuilder |
| 2        | Q7       | Error wrapping scope affects every signal handler |
| 3        | Q11      | WCL menus vs manual changes the entire menu architecture |
| 4        | Q20      | Run() dispatch changes how every caller interacts with the app |
| 5        | Q19      | VBStyle compliance scope affects every file's structure |
| 6        | Q1       | DB connection ownership affects constructor signatures |
| 7        | Q14      | Canvas structure affects import graph and file count |
| 8        | Q13      | Entry point location affects how the app is launched |

## Answer format
For each question, reply with the letter only:
```
Q1: A
Q2: C
Q3: B
...
```
Or write "skip" for questions you do not care about — I will pick the default (first option).
