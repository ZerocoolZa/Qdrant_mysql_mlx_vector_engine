# GUI Lessons — Dom_DecisionTrees

## 1. Use the engine to build the GUI shell

**Bad:** v1 manually creates every `QSplitter`, `QVBoxLayout`, `QComboBox`, `QPushButton`, `QTabWidget`, `QPlainTextEdit`, `QLabel`, `QSpinBox`, `QLineEdit` — 1,700 lines of hand-built UI.

**Do:**
1. Write WCL declarations in `Config.py` (widget types, names, parents, properties, signals, handlers)
2. Main file imports `GUIParser` from `core.Dom_Gui`
3. Call `parser.parse_string(WCL_CONFIG)` → get tree + signals + gui_meta
4. Import `GUIBuilder` from `core.Dom_Gui`
5. Call `builder.build(tree, signals)` → engine instantiates all widgets, applies properties, adds to parents, routes signals to handlers
6. Call `self.setCentralWidget(self.widgets["central"])` — engine builds it as a root node
7. Main file contains handler methods only — no widget construction code

**Files involved:**
- `Dom_DecisionTrees/Config.py` — `WCL_CONFIG` string with `[@WIDGET]` and `[@SIGNAL]` declarations
- `core/Dom_Gui/parser.py` — `GUIParser.parse_string()` → tree of `GUITreeNode` objects
- `core/Dom_Gui/builder.py` — `GUIBuilder.build()` → dict of `{name: QWidget}`, auto-connects signals via `EventRouter`
- `core/Dom_Gui/router.py` — `EventRouter.route()` → connects `widget.signal` to `host.handler` by name

## 2. Import the core system domain for IO and error handling

**Bad:** v1 does `import sqlite3` and `self.conn = sqlite3.connect(self.db_path)` directly. No system layer involved. If the DB file is missing or the table schema is wrong, the error is a raw Python exception that crashes the event loop.

**Do:**
1. Import `ErrorHandler` from `core.utility.error_handler`
2. Import `DomSystem` from `core.Dom_Unified` for service lifecycle (MySQL, SQLite, etc.)
3. Create `ErrorHandler` instance in `__init__`: `self.error_handler = ErrorHandler()`
4. All DB connections go through the system layer, not raw `sqlite3.connect()`
5. All file IO goes through the system layer, not raw `open()`

**Concrete imports:**
```python
import sys
CORE_DIR = str(Path(__file__).resolve().parent.parent / "core")
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from utility.error_handler import ErrorHandler
from Dom_Unified import DomSystem
```

**What `ErrorHandler` provides (from `core/utility/error_handler.py`):**
- `Run("capture", {error_code, raw_message, source_module, exception})` → logs to SQLite, classifies severity, returns Tuple3
- `Run("consume", {result, source})` → pass any Tuple3 from any `Run()` call, auto-captures failures
- `Run("retry", {fn, attempts, delay, backoff})` → retry with exponential backoff
- `Run("circuit_breaker", {name, threshold})` → prevents cascading failures
- `Run("health_check", {})` → reports breaker states and error counts

**What `DomSystem` provides (from `core/Dom_Unified/DomSystem.py`):**
- `Run("acquire", {service: "sqlite"})` → lazy-load with refcount
- `Run("release", {service: "sqlite"})` → decrement refcount
- `Run("is_running", {service: "sqlite"})` → check state
- `Run("health", {service: "sqlite"})` → health check
- `Run("recover", {service: "sqlite"})` → auto-restart on failure

## 3. Wrap every signal handler in ErrorHandler

**Bad:** v1 signal handlers call `self.conn.cursor()` directly. If `self.conn` is `None` (DB failed to connect), the handler throws an unhandled exception. The PyQt6 event loop crashes. The traceback dumps to terminal. The GUI freezes. The user has to kill the process.

Specific vulnerable methods in v1:
- `show_stats()` — `self.conn.cursor()` with no try/except, no error handler
- `build_tree_data()` — `self.conn.cursor()` with only a `None` check, no error capture
- `populate_code_tabs()` — `self.conn.cursor()` with only a `None` check
- `rebuild_tree()` — `self.conn.cursor()` with only a `None` check
- `on_json_changed()` — has `try/except json.JSONDecodeError` but doesn't route to ErrorHandler

**Do:**
1. Every signal handler wraps its body in `ErrorHandler.Run("consume", {result, source})`
2. If the handler calls a DB query, wrap it: `result = self.error_handler.Run("retry", {fn: self._do_query, attempts: 3, delay: 0.5})`
3. If the result is `(0, None, err)`, show the error in the status bar, don't crash
4. Example pattern:
```python
def on_node_selected(self, node):
    result = self._query_node_data(node)
    code, data, err = self.error_handler.Run("consume", {
        "result": result,
        "source": "DecisionTreeApp.on_node_selected"
    })
    if code == 0:
        self.statusBar().showMessage(f"Error: {err}")
        return
    # ... use data ...
```

## 4. Split into focused files

**Bad:** v1 is one 1,700-line file with shell building + canvas + DB queries + BCL parsing + dependency graph + handlers + boot + menus + theme + config save/load.

**Do — 5 files:**

| File | Contains | Lines |
|------|----------|-------|
| `Config.py` | WCL declarations (`WCL_CONFIG`), `TREE_CONFIG_DEFAULT`, `COLOR_SCHEMES`, `BCL_NODE_COLORS`, `NODE_RADIUS`, `DB_PATH` | ~270 |
| `canvas.py` | `JsonHighlighter`, `TreeNode`, `MovableNodeItem`, `EdgeItem`, `DecisionTreeCanvas` — custom QGraphicsView canvas only | ~400 |
| `tree_builder.py` | `TreeBuilder` class — `build_tree_data()`, `build_by_category()`, `build_by_file()`, `build_by_class()`, `build_dep_graph()`, `build_bcl_tree()` — DB queries and tree construction only | ~300 |
| `app.py` | `DecisionTreeApp(QMainWindow)` — handler methods only (`on_mode_changed`, `on_combo_changed`, `on_search_changed`, `schedule_json_update`, `rebuild_tree`, `on_node_selected`, etc.). No widget construction. No DB queries directly — delegates to `TreeBuilder`. | ~300 |
| `main_decision_trees.py` | Boot sequence only: create `QApplication`, import engine, parse WCL, build shell, set central widget, create canvas, insert as tab, populate combos, connect canvas signals, show window | ~80 |

## 5. The boot sequence in main_decision_trees.py

**Bad:** v1 boot is scattered across `__init__`, `build_shell()`, `post_build()`, `setup_menu()`, `connect_db()`, `rebuild_tree()` — all in one file, mixed with domain logic.

**Do — exact boot sequence in `main_decision_trees.py`:**

```
Step 1: sys.path setup — add core/ to path
Step 2: from Dom_Gui import GUIParser, GUIBuilder
Step 3: from utility.error_handler import ErrorHandler
Step 4: from Dom_DecisionTrees.Config import WCL_CONFIG, TREE_CONFIG_DEFAULT, COLOR_SCHEMES
Step 5: from Dom_DecisionTrees.canvas import DecisionTreeCanvas, JsonHighlighter
Step 6: from Dom_DecisionTrees.tree_builder import TreeBuilder
Step 7: from Dom_DecisionTrees.app import DecisionTreeApp
Step 8: app = QApplication(sys.argv)
Step 9: parser = GUIParser(); parser.parse_string(WCL_CONFIG)
Step 10: gui = DecisionTreeApp(parser)  # host with handler methods
Step 11: builder = GUIBuilder(host=gui); gui.widgets = builder.build(parser.get_tree(), parser.get_signals())
Step 12: gui.setCentralWidget(gui.widgets["central"])
Step 13: gui.error_handler = ErrorHandler()
Step 14: gui.tree_builder = TreeBuilder(gui.error_handler)
Step 15: gui.canvas = DecisionTreeCanvas(gui.colors)
Step 16: gui.widgets["tabs"].insertTab(0, gui.canvas, "Decision Tree Canvas")
Step 17: gui.populate_combos()  # fill mode_combo, group_combo, orient_combo, max_spin
Step 18: gui.setup_menu()  # File/Database/View menus
Step 19: gui.apply_theme("dark")
Step 20: gui.show()
Step 21: sys.exit(app.exec())
```

## 6. Do what the user asked, in the order asked

**Bad:** User says "make a markdown file", I start writing Python code. User has to repeat the request angrily.

**Do:** Execute requests in the order given. If the user says "make a markdown file first", make the markdown file first. If the user says "enter summary mode", enter summary mode. Do not reorder priorities.
