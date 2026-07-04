# Smart System Search

A PyQt6 mini GUI for searching MySQL databases with predictive autocomplete, minimize-to-floating-ball, and VBStyle compliance checking.

Built and debugged on macOS M1 (Apple Silicon). Every platform-specific workaround is documented here and captured as a `[@FloatingBall]` GUI token in the `vb_shared.gui_tokens` table.

---

## Quick Start

```bash
cd /Users/wws/Qdrant_mysql_mlx_vector_engine/Smart_system_seach
python3 Gui_Smart_search.py
```

**Requirements:**
- Python 3.10+
- PyQt6 (`pip install PyQt6`)
- mysql-connector-python (`pip install mysql-connector-python`)
- MySQL running on localhost with two databases:
  - `vb_shared` (61 tables — search target)
  - `token_registry` (autocomplete source: `words` + `word_locations`)

**First run:** Builds SQLite caches from MySQL (~55s). UI stays responsive during build.
**Subsequent runs:** Loads from SQLite cache (~3s startup).

---

## Files

| File | Purpose | Lines |
|---|---|---|
| `Gui_Smart_search.py` | Main GUI application | 1006 |
| `dom_smart_search.py` | VBStyle search domain (MySQL + EFL SQLite) | 736 |
| `Classifier_smart_system.py` | Code classifier (language detection, VBStyle compliance) | 792 |
| `Config_smart_system.py` | Gold-standard config (flat UPPERCASE constants) | 245 |
| `.bigrams.sqlite` | SQLite cache for bigram prediction model (6 MB) | — |
| `.wordfreq.sqlite` | SQLite cache for word frequencies (188 KB) | — |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Gui_Smart_search.py                 │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │            MiniSearchGui (QWidget)            │   │
│  │                                               │   │
│  │  ┌─────────────────────────────────────┐     │   │
│  │  │  Results (QListWidget)               │     │   │
│  │  │  - table list when empty             │     │   │
│  │  │  - hit list when searching           │     │   │
│  │  └─────────────────────────────────────┘     │   │
│  │  ┌─────────────────────────────────────┐     │   │
│  │  │  GhostLineEdit (QLineEdit)           │     │   │
│  │  │  - grey ghost-text autocomplete      │     │   │
│  │  │  - Tab to accept                     │     │   │
│  │  └─────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────┘   │
│                       │                              │
│          ┌────────────┼────────────┐                 │
│          ▼            ▼            ▼                 │
│   ┌──────────┐ ┌──────────┐ ┌──────────────┐        │
│   │ MySQL    │ │ SQLite   │ │ FloatingBall │        │
│   │ vb_shared│ │ caches   │ │ (minimized)  │        │
│   │ (search) │ │ (autocomplete)│           │        │
│   └──────────┘ └──────────┘ └──────────────┘        │
│         │            │                              │
│         ▼            ▼                              │
│   ┌──────────┐ ┌──────────┐                         │
│   │ 61 tables│ │ words    │                         │
│   │ LIKE scan│ │ bigrams  │                         │
│   └──────────┘ └──────────┘                         │
│                  ▲                                   │
│                  │                                   │
│           ┌──────────────┐                          │
│           │ token_registry│                          │
│           │ (MySQL)       │                          │
│           │ 28K words     │                          │
│           │ 225K locations│                          │
│           └──────────────┘                          │
└─────────────────────────────────────────────────────┘

VBStyle domain modules (NOT used by GUI — see Known Gaps):
┌─────────────────────────────────────────────────────┐
│  dom_smart_search.py    SmartSearch.Run()            │
│    10 commands: search, detect_language,             │
│    vbstyle_check, report, find_list, efl_search,     │
│    scan_class, scan_all, read_state, set_config      │
│                                                      │
│  Classifier_smart_system.py  SmartClassifier.Run()   │
│    12 commands: detect_language, vbstyle_check,      │
│    scan_code, scan_class, count_methods,             │
│    efl_classify, efl_class_detail, efl_zero_methods, │
│    efl_vbstyle_summary, efl_method_violations,       │
│    read_state, set_config                            │
│                                                      │
│  Config_smart_system.py   All UPPERCASE constants    │
└─────────────────────────────────────────────────────┘
```

---

## Feature 1: Smart MySQL Search

### How it works

The search bar queries **all text columns across all 61 tables** in the `vb_shared` database. Pattern adapted from `mysql_cli_search.py`.

### Search flow

1. User types in `GhostLineEdit`
2. `textChanged` signal fires → starts 200ms debounce timer
3. After 200ms of no typing → `_do_search()` runs
4. `search_source(query)` calls `_mysql_search(keyword)`
5. For each table in `vb_shared`:
   - Query `INFORMATION_SCHEMA.COLUMNS` for text-type columns
   - Build `SELECT * FROM table WHERE col1 LIKE %kw% OR col2 LIKE %kw% ... LIMIT 10`
   - Collect matching rows
6. Results displayed as `table_name | value_snippet` in the QListWidget

### Text column types searched

```python
TEXT_TYPES = {"char", "varchar", "text", "tinytext", "mediumtext", "longtext"}
```

### Empty query behavior

When the search bar is empty, the GUI shows all 61 table names in `vb_shared` as `[table] name` entries. This gives the user a starting point.

### Debounce

200ms debounce per the `[@SearchBar]` GUI token spec. Prevents hammering MySQL on every keystroke.

### Result activation

- **Double-click** a result → `_activate(text)` parses the hit string
- **Enter** → activates the first selected result (or first result if none selected)
- Hit format `table | snippet` → status bar shows `Hit in {table}: {snippet}`
- Table format `[table] name` → status bar shows `Browsing table: {name}`

---

## Feature 2: Predictive Autocomplete (Ghost Text)

### Two prediction modes

#### Mode 1: Mid-word prefix matching

When the user is typing a word (no trailing space), the GUI searches the top 500 most frequent words for one that starts with what they've typed:

```python
for word, count in word_freq.most_common(500):
    if word.lower().startswith(current_word.lower()) \
       and word.lower() != current_word.lower() \
       and len(word) > len(current_word):
        suggestion = word
        break
```

**Example:** Type `def` → ghost text shows `__init__` (most common word starting with "def")

#### Mode 2: Bigram prediction (after space)

When the user types a space after a complete word, the GUI queries SQLite for the most common next word:

```sql
SELECT word2 FROM bigrams WHERE word1 = ? ORDER BY freq DESC LIMIT 1
```

**Example:** Type `class ` (with space) → ghost text shows the most common word after "class"

### Tokenizer

Uses the same tokenizer as `tokenized_context_search.py` (`TokenizedSearchIndex.tokenize_text`):

```python
def _tokenize(text: str):
    words = re.findall(r'\b[a-zA-Z0-9_]+\b', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 2]
```

Rules:
- **Lowercase** everything
- **Word-boundary** alphanumeric + underscores only
- **Exclude stop words** (the, and, or, but, in, on, at, to, for, of, with, by, from, as, is, was, are, were, be, been, being, have, has, had, do, does, did, will, would, could, should, may, might, must, shall, can, need, dare, a, an, this, that, these, those, i, you, he, she, it, we, they, what, which, who, whom, whose, where, when, why, how, there, here, if, then, else, because, although, though, while, since, until, unless, before, after, during, through, over, under, again, further, then, once, all, both, each, few, more, most, other, some, such, no, nor, not, only, own, same, so, than, too, very, just, also, now, get, like, know, mean, well, back, still)
- **Exclude words with len <= 2** (no "if", "is", "to" etc.)

### Ghost text interaction

| Key | Action |
|---|---|
| **Tab** | Accept the ghost text suggestion |
| **Arrow keys** | Clear ghost text |
| **Enter / Return** | Clear ghost text, trigger search |
| **Esc** | Clear ghost text, minimize to ball |
| **Any other key** | Restart 250ms prediction timer |

### Ghost text rendering

Grey text (`QColor(120, 130, 145)`) drawn at the cursor position via `paintEvent`:

```python
def paintEvent(self, e):
    super().paintEvent(e)
    if self._ghost_text:
        painter = QPainter(self)
        painter.setPen(_GHOST_COLOR)
        painter.setFont(self.font())
        cursor_rect = self.cursorRect()
        x = cursor_rect.x()
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        painter.drawText(x, y, self._ghost_text)
```

---

## Feature 3: Bigram Model + SQLite Cache

### Data source

| Database | Table | Rows | Purpose |
|---|---|---|---|
| `token_registry` | `words` | 28,039 | Word frequencies |
| `token_registry` | `word_locations` | 225,182 | Line text for bigram building |

### Why not SQL self-join?

The original `vbstyle_class_clarifier.py` used a SQL self-join on `word_locations`:

```sql
SELECT w1.word, w2.word, COUNT(*) FROM word_locations w1
JOIN word_locations w2 ON w1.file_id = w2.file_id AND w2.line_number = w1.line_number
```

This hangs on 225K rows — a line with 20 words produces 190 pairs, and 225K lines × that = millions of join rows. The query never completes.

### Solution: Python tokenization + SQLite cache

1. **First run** (~55s): Stream `line_text` from MySQL in batches of 5000 rows
2. Tokenize each line with `_tokenize()` (stop words filtered, len > 2)
3. Build consecutive word pairs in Python: `bigrams[w1][w2] += 1`
4. Save to SQLite file with indexes:
   ```sql
   CREATE TABLE bigrams (word1 TEXT, word2 TEXT, freq INTEGER);
   CREATE INDEX idx_bigram_w1 ON bigrams(word1);
   CREATE INDEX idx_bigram_w1w2 ON bigrams(word1, word2);
   ```
5. **Subsequent runs** (~3s): Open SQLite file, query via indexed SELECT

### Cache files

| File | Size | Contents |
|---|---|---|
| `.wordfreq.sqlite` | 188 KB | 5,000 words with frequencies |
| `.bigrams.sqlite` | 6 MB | 92,338 bigram pairs with frequencies |

### AutocompleteLoader (non-blocking)

The bigram model loads via `AutocompleteLoader`, which uses `QTimer` chunks to avoid freezing the UI:

- Processes 5000 MySQL rows per 10ms tick
- Yields back to the Qt event loop between batches
- UI stays fully responsive during the 55s first-run build
- Calls back to `_on_autocomplete_loaded` when done

### Why not QThread?

QThread caused a segfault on macOS M1 with PyQt6 (exit code 139). The QTimer chunk approach is safer on Cocoa.

---

## Feature 4: Minimize to Floating Ball

### The problem

On macOS, making a PyQt6 window float above all other apps and minimize to a floating ball has many traps:

1. `WindowStaysOnTopHint` on the main window → Cocoa refuses to minimize it (zoom-down-up-down flicker)
2. `Qt.Tool` without parent → unreliable on Cocoa
3. `X11BypassWindowManagerHint` → breaks Cocoa window management
4. `pyobjc` `objc.objc_object(ptr)` → fails on M1 with `sip.voidptr` conversion
5. `hide()` instead of `showMinimized()` → Cocoa re-shows the window causing flicker
6. `changeEvent` alone → spurious `WindowMinimized` events during startup
7. Showing ball AFTER hiding parent → app deactivates, ball never appears
8. `WA_ShowWithoutActivating` → prevents ball from appearing at all

### The solution (Pindrop pattern)

The floating ball uses the same native Cocoa properties as Pindrop's `DotFloatingIndicator.swift`:

```python
def _apply_pindrop_ball_style(widget):
    ns_window = _get_nswindow(widget)

    # NSStatusWindowLevel = 25 — above all normal app windows
    _ns_msg_int(ns_window, "setLevel:", 25)

    # collectionBehavior = canJoinAllSpaces | stationary | ignoresCycle | fullScreenAuxiliary
    # = 1 | 16 | 64 | 256 = 337
    _ns_msg_int(ns_window, "setCollectionBehavior:", 337)

    # Show even if app is not active
    _ns_msg(ns_window, "orderFrontRegardless")

    # Don't hide when app loses focus
    _ns_msg_int(ns_window, "setHidesOnDeactivate:", 0)
```

### Why ctypes instead of pyobjc?

PyQt6's `sip.voidptr` cannot be converted to pyobjc's `objc.objc_object` on M1 (Apple Silicon). The conversion raises a type error. Using `ctypes` to call `objc_msgSend` directly bypasses this:

```python
_OBJC_LIB = ctypes.CDLL(ctypes.util.find_library("objc"))
_OBJC_LIB.objc_msgSend.restype = ctypes.c_void_p
_OBJC_LIB.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
```

### Native window properties set

| Property | Value | Effect |
|---|---|---|
| `level` | 25 (`NSStatusWindowLevel`) | Floats above all normal app windows |
| `collectionBehavior` | 337 | Visible on all Spaces, stationary, fullscreen auxiliary |
| `orderFrontRegardless` | — | Shows even when app is not active |
| `setHidesOnDeactivate:` | 0 (false) | Survives app switching |

### Qt window flags for the ball

```python
self.setWindowFlags(
    Qt.WindowType.FramelessWindowHint      # no title bar
    | Qt.WindowType.WindowStaysOnTopHint   # stay on top (Qt level)
    | Qt.WindowType.SplashScreen           # reliable frameless on macOS
)
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
```

### Ball appearance

- 64x64 pixels, circular
- Bright blue (`#1f6feb`) with glow effect (4 layers of decreasing alpha)
- White "Q" letter centered
- Inner highlight (white, alpha 40) for 3D effect

### Ball interaction

| Action | Result |
|---|---|
| **Click** (no drag) | Restore main window |
| **Drag** (move >3px) | Reposition ball without restoring |
| **Hover** | Tooltip: "Click to restore Mini Search" |

### Periodic re-assert

Every 2 seconds, the ball re-applies the Pindrop-style native properties. This ensures the ball survives:
- App switching (Cmd+Tab)
- Space switching (Ctrl+Arrow)
- Display sleep/wake

### Minimize flow

1. User presses **Esc** (or yellow dot, or Cmd+M)
2. `_minimize_to_ball()` saves the window geometry
3. Ball is positioned at top-right of where the window was
4. Ball is shown **before** the window minimizes (critical — if shown after, app deactivates)
5. `_apply_pindrop_ball_style(ball)` sets native Cocoa properties
6. `self.showMinimized()` lets macOS minimize the window normally
7. 500ms re-entrancy guard prevents double-minimize

### Restore flow

1. User clicks the ball
2. `_restore_from_ball()` hides the ball
3. `self.setWindowState(WindowNoState)` + `self.showNormal()` restores from minimized
4. Saved geometry is restored
5. `self.raise_()` + `self.activateWindow()` brings window to front
6. Search bar gets focus

### Esc shortcut

```python
self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
self.esc_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
```

`ApplicationShortcut` context is critical — without it, `QLineEdit` swallows the Esc key and the shortcut never fires.

### Startup guards

| Guard | Purpose |
|---|---|
| `_initialized` | Don't react to minimize events until window has been visible for 1s |
| `_minimizing` | Prevent re-entrancy during the 500ms minimize flow |
| `_self_hiding` | Distinguish our hide() from system hide() |

macOS sends spurious `WindowMinimized` events during window initialization. The `_initialized` flag (set after 1s delay via `_mark_initialized`) prevents the ball from appearing on startup.

### Native minimize (yellow dot / Cmd+M)

`changeEvent` intercepts `WindowStateChange` to `WindowMinimized`:

```python
def changeEvent(self, e):
    if e.type() == QEvent.Type.WindowStateChange:
        state = self.windowState()
        if self._initialized and not self._minimizing \
           and (state & Qt.WindowState.WindowMinimized):
            self._minimize_to_ball()
```

This catches the yellow minimize button and Cmd+M, routing them through the same ball-show flow as Esc.

---

## Feature 5: GUI Token Capture

The `[@FloatingBall]` token was captured in the `vb_shared.gui_tokens` MySQL table (token #19) to preserve every lesson learned during development.

### Token schema

```sql
CREATE TABLE gui_tokens (
    id int AUTO_INCREMENT PRIMARY KEY,
    token_name varchar(100) UNIQUE NOT NULL,
    gui_type varchar(50) NOT NULL,
    bracket_body longtext,
    required_behaviors text,
    forbidden_behaviors text,
    unknown_areas text,
    design_practices text,
    code_reference varchar(100),
    pass_state text,
    fail_state text,
    unknown_state text,
    authority_rank varchar(50) DEFAULT 'layout',
    description varchar(255),
    version int DEFAULT 1,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);
```

### Captured token

| Field | Value |
|---|---|
| `token_name` | `[@FloatingBall]` |
| `gui_type` | `overlay` |
| `authority_rank` | `safety` |
| `bracket_body` | Frameless, WindowStaysOnTop, NSStatusLevel=25, CollectionBehavior=337, OrderFrontRegardless, HidesOnDeactivate=False, DragMovable, ClickRestores, Size=64px |
| `required_behaviors` | All working patterns (ctypes objc_msgSend, showMinimized not hide, no WindowStaysOnTop on parent, Esc ApplicationShortcut, periodic re-assert) |
| `forbidden_behaviors` | All failed approaches (hide() flicker, WindowStaysOnTop on parent, pyobjc on M1, X11BypassWindowManagerHint, Tool without parent, WA_ShowWithoutActivating) |
| `pass_state` | Frameless, Level=25, CollectionBehavior=337, OrderFrontRegardless, Click restores, Drag moves, No flicker, Survives Space switch |
| `fail_state` | hide() flicker, WindowStaysOnTop on parent, pyobjc fails on M1, Ball not visible, Zoom down-up-down, Lost on Space switch |
| `code_reference` | `mini_search_gui.py:FloatingBall` |

### Other GUI tokens in vb_shared (18 total before this work)

`[@DetailPane]`, `[@DialogForm]`, `[@FormLayout]`, `[@ListView]`, `[@MenuBar]`, `[@ModalDialog]`, `[@Notification]`, `[@ProgressBar]`, `[@SearchBar]`, `[@ShortcutKeys]`, `[@SplitPane]`, `[@StatusBar]`, `[@ZebraStriping]`, `[@TableView]`, `[@Tabs]`, `[@Toolbar]`, `[@TreeView]`, `[@Wizard]`

---

## Feature 6: VBStyle Domain Modules

### dom_smart_search.py — `SmartSearch` class

VBStyle-compliant search domain. Searches MySQL `code_classes` + EFL SQLite DB. Detects language (Python/C/Swift/Markdown). Checks VBStyle compliance.

- Ghost + VBStyle headers
- `Run()` dispatch entry point returning Tuple3 `(ok, data, error)`
- No decorators, no print, no hardcoded paths
- Reads all config from `Config_smart_system.py`

**Dispatch commands (10):**

| Command | Method | Purpose |
|---|---|---|
| `search` | `Search()` | Search MySQL `code_classes` |
| `detect_language` | `DetectLanguage()` | Detect Python/C/Swift/Markdown |
| `vbstyle_check` | `VbstyleCheck()` | Check VBStyle compliance |
| `report` | `Report()` | Generate search report |
| `find_list` | `FindList()` | Load `Find_list.py` |
| `efl_search` | `EflSearch()` | Search EFL SQLite DB |
| `scan_class` | `ScanClass()` | Scan a single class |
| `scan_all` | `ScanAll()` | Scan all classes |
| `read_state` | `ReadState()` | Return internal state dict |
| `set_config` | `SetConfig()` | Update config |

### Classifier_smart_system.py — `SmartClassifier` class

VBStyle-compliant code classifier. Classifies code: language detection, VBStyle compliance, class tree extraction, BCL header parsing. No search — search is handled by `Gui_Smart_search.py`.

**Dispatch commands (12):**

| Command | Method | Purpose |
|---|---|---|
| `detect_language` | `DetectLanguage()` | Detect Python/C/Swift/Markdown |
| `vbstyle_check` | `VbstyleCheck()` | Check VBStyle compliance (9 rules) |
| `scan_code` | `ScanCode()` | Scan code for classes/methods |
| `scan_class` | `ScanClass()` | Scan a single class |
| `count_methods` | `CountMethodsCmd()` | Count methods in code |
| `efl_classify` | `EflClassify()` | Classify EFL entries |
| `efl_class_detail` | `EflClassDetail()` | Detail on one EFL class |
| `efl_zero_methods` | `EflZeroMethods()` | Find EFL classes with 0 methods |
| `efl_vbstyle_summary` | `EflVbstyleSummary()` | VBStyle summary across EFL |
| `efl_method_violations` | `EflMethodViolations()` | Method-level VBStyle violations |
| `read_state` | `ReadState()` | Return internal state dict |
| `set_config` | `SetConfig()` | Update config |

### Language detection logic

Both `SmartSearch` and `SmartClassifier` share the same language detection:

1. Take first 500 chars of code (`DEFAULT_LANGUAGE_HEAD_SCAN`)
2. Match against markers in order:
   - **C**: `#include <stdio`, `#include <stdlib`, `#include <math`, `#include <Foundation`, `struct ` + `typedef`
   - **Swift**: `import Foundation`, `MTLDevice`, `MTLBuffer`, `MTLCommand`, `func ` + `->`, `let ` + `var `
   - **Python**: `#@GHOST`, `#@VBSTYLE`, `def `, `class `, `#!/usr/bin/env python3`, `from __future__`, `import `
   - **Markdown**: `# ` (but not `def `), `Yes`, `This file`
3. Return `unknown` if no match

### VBStyle compliance checks (9 rules)

Checked via regex in `VbstyleCheck()`:

| Rule | Regex | What it checks |
|---|---|---|
| `ghost_header` | `#\[@GHOST\]` | Has `[@GHOST]` header |
| `vbstyle_header` | `#\[@VBSTYLE\]` | Has `[@VBSTYLE]` header |
| `tuple3_return` | `Tuple3\|tuple3` | Returns Tuple3 |
| `state_dict` | `self\.state\s*=` | Uses `self.state` dict |
| `run_dispatch` | `def\s+Run\s*\(` | Has `Run()` dispatch |
| `no_decorators` | `^\s*@(?:staticmethod\|classmethod\|property\|abstractmethod\|functools)` | No decorators (inverted) |
| `no_print` | `\bprint\s*\(` | No print statements (inverted) |
| `no_self_underscore` | `self\._[a-z]` | No `self._` private attrs (inverted) |
| `no_hardcoded_paths` | `["\']/(?:Users\|home\|tmp\|var\|opt)/` | No hardcoded paths (inverted) |

### Config_smart_system.py

Gold-standard config file. Flat UPPERCASE constants, no dicts, no hardcoded values in classes. All other modules import from here.

**Constant categories:**

| Category | Examples | Count |
|---|---|---|
| Database paths | `DB_PATH_EFL_BRAIN`, `DB_NAME_VB_SHARED`, `DB_HOST_LOCALHOST` | 5 |
| Search terms | `SEARCH_TERM_AI`, `SEARCH_TERM_NEURAL`, `SEARCH_TERM_VECTOR` | 17 |
| Language markers | `LANG_MARKER_C_STDIO`, `LANG_MARKER_SWIFT_IMPORT`, `LANG_MARKER_PYTHON_DEF` | 16 |
| VBStyle patterns | `VBSTYLE_PATTERN_GHOST`, `VBSTYLE_PATTERN_DECORATOR` | 9 |
| VBStyle rule names | `RULE_GHOST_HEADER`, `RULE_NO_DECORATORS` | 9 |
| Default params | `DEFAULT_SEARCH_LIMIT=50`, `DEFAULT_LANGUAGE_HEAD_SCAN=500` | 4 |
| Scaffold generator | `SCAFFOLD_ID=118`, `SCAFFOLD_CLASS_NAME` | 9 |
| Language names | `LANG_NAME_PYTHON`, `LANG_NAME_C`, `LANG_NAME_SWIFT` | 5 |
| Commands | `CMD_SEARCH`, `CMD_DETECT_LANGUAGE`, `CMD_VBSTYLE_CHECK` | 8 |
| Error codes | `ERR_UNKNOWN_COMMAND`, `ERR_MISSING_PARAM` | 7 |
| Source types | `SOURCE_MYSQL`, `SOURCE_EFL`, `TABLE_CODE_CLASSES` | 3 |
| GUI: DB config | `DB_NAME_TOKEN_REGISTRY` | 1 |
| GUI: Cache files | `CACHE_FILE_BIGRAM`, `CACHE_FILE_WORDFREQ` | 2 |
| GUI: Colors | `COLOR_GHOST_TEXT_R/G/B`, `COLOR_BALL_*` | 8 |

---

## Feature 7: Entry Point

```python
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MiniSearchGui")
    gui = MiniSearchGui()
    gui.show()
    gui.search.setFocus()
    _debug(f"started; native_level={_NATIVE_LEVEL_AVAILABLE}")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

- Sets application name to `MiniSearchGui`
- Creates the main window
- Shows window and focuses the search bar immediately
- Logs whether native macOS level control is available
- `sys.exit(app.exec())` blocks until window closes

---

## Known Gaps & TODOs

These are issues I found while writing this README. They should be addressed in future work.

### Gap 1: GUI doesn't use the VBStyle domain modules

`Gui_Smart_search.py` has its own `_mysql_search()` function and does NOT import `SmartSearch` or `SmartClassifier`. The domain modules (`dom_smart_search.py`, `Classifier_smart_system.py`) are unused by the GUI.

**Fix:** Replace `_mysql_search()` in `Gui_Smart_search.py` with:
```python
from dom_smart_search import SmartSearch
searcher = SmartSearch()
ok, data, err = searcher.Run("search", {"query": query})
```

### Gap 2: Config is out of sync with GUI

`Config_smart_system.py` defines:
```python
CACHE_FILE_BIGRAM = '.bigram_cache.pkl'    # stale — GUI uses .bigrams.sqlite
CACHE_FILE_WORDFREQ = '.wordfreq_cache.pkl' # stale — GUI uses .wordfreq.sqlite
```

But `Gui_Smart_search.py` hardcodes:
```python
_BIGRAM_DB = ".bigrams.sqlite"
_WORDFREQ_DB = ".wordfreq.sqlite"
```

**Fix:** GUI should import from config, and config should be updated to `.sqlite` names.

### Gap 3: GUI colors hardcoded instead of from config

`Config_smart_system.py` defines:
```python
COLOR_GHOST_TEXT_R = 120
COLOR_GHOST_TEXT_G = 130
COLOR_GHOST_TEXT_B = 145
COLOR_BALL_BORDER = '#58a6ff'
COLOR_BALL_FILL = '#1f6feb'
COLOR_BALL_LETTER = '#ffffff'
```

But `Gui_Smart_search.py` hardcodes all of these:
```python
_GHOST_COLOR = QColor(120, 130, 145)
p.setPen(QPen(QColor("#58a6ff"), 3))
p.setBrush(QColor("#1f6feb"))
p.setPen(QColor("#ffffff"))
```

**Fix:** GUI should import colors from config.

### Gap 4: GUI is not VBStyle compliant

The domain modules follow VBStyle (Run dispatch, Tuple3, state dict, no decorators, no hardcoded paths). But `Gui_Smart_search.py` does NOT:
- No `Run()` dispatch
- No Tuple3 returns
- Hardcoded paths (`/Users/wws/...`)
- Hardcoded MySQL config (`user="root"`, `database="vb_shared"`)
- Uses `print()` via `_debug()`
- No `[@GHOST]` / `[@VBSTYLE]` headers

This is a deliberate tradeoff — PyQt6 GUIs don't naturally fit the VBStyle dispatch pattern. But the hardcoded values should at least come from `Config_smart_system.py`.

### Gap 5: Dead code — `_load_word_freq()` and `_load_bigrams()`

The standalone functions `_load_word_freq()` (lines 200-240) and `_load_bigrams()` (lines 243-300) exist but are never called. The `AutocompleteLoader` class (lines 303-447) duplicates their logic internally.

**Fix:** Delete the standalone functions, or refactor `AutocompleteLoader` to call them.

### Gap 6: TODO — table browsing unfinished

In `_activate()`:
```python
if text.startswith("[table] "):
    table = text[8:]
    self.status_label.setText(f"Browsing table: {table}")
    # TODO: show table contents
```

Double-clicking a table name in the empty-query list only updates the status bar. It doesn't actually show the table's contents.

**Fix:** Implement table browsing — show first N rows in the results list, or open a detail view.

### Gap 7: No result highlighting

Search results show `table | snippet` but the matching text within the snippet is not highlighted. Adding `<mark>`-style highlighting (via `QListWidgetItem` with HTML rich text) would improve scannability.

### Gap 8: No search history

There's no up-arrow history navigation in the search bar (like a shell). Adding a history list would let users re-run previous queries quickly.

### Gap 9: No fuzzy matching

Search uses `LIKE %keyword%` — exact substring match. Fuzzy matching (trigram, Levenshtein) would help with typos and partial matches.

### Gap 10: Bigram cache not auto-refreshed

If new files are ingested into `token_registry.word_locations`, the `.bigrams.sqlite` cache becomes stale. There's no automatic refresh — the user must manually delete the cache file.

**Fix:** Check `word_locations` row count on startup; if it changed since cache was built, rebuild automatically.

---

## Performance

| Operation | First run | With cache |
|---|---|---|
| Load word frequencies | 0.1s (MySQL) | <0.1s (SQLite) |
| Build bigram model | 55s (MySQL + tokenize) | <0.1s (SQLite) |
| Ghost text prediction (mid-word) | <1ms | <1ms |
| Ghost text prediction (bigram) | <1ms (SQLite SELECT) | <1ms |
| MySQL search (61 tables) | 0.5-2s | 0.5-2s |
| **Total startup** | **~55s** | **~3s** |

---

## Debugging

All debug output goes to stderr with `[mini_search]` prefix:

```bash
python3 Gui_Smart_search.py 2>&1 | grep mini_search
```

### Key debug messages

| Message | Meaning |
|---|---|
| `started; native_level=True` | ctypes objc_msgSend loaded successfully |
| `loaded 5000 words from SQLite cache` | Word frequency cache hit |
| `loaded 92338 bigrams from SQLite cache` | Bigram cache hit |
| `building bigram SQLite cache (first run, ~55s)` | Cache miss, rebuilding |
| `ball: level=25, collectionBehavior=337` | Pindrop-style properties applied |
| `minimize_to_ball called` | Esc / yellow dot / Cmd+M triggered |
| `window initialized (ready for minimize-to-ball)` | 1s startup guard passed |
| `ball clicked → restore` | User clicked ball to restore window |

---

## Database Dependencies

### vb_shared (search target)

```
61 tables including:
  gui_tokens          — GUI component patterns (19 tokens)
  code_classes        — VBStyle class registry
  code_registry       — Code registry
  class_understandings — Class analysis
  class_graph         — Class relationships
  instructions        — System instructions
  token_master        — 5815 token names
  tokens              — Token definitions
  ...
```

### token_registry (autocomplete source)

```
words            — 28,039 words with frequencies
word_locations   — 225,182 line text entries
```

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| **Tab** | Accept ghost-text autocomplete suggestion |
| **Enter** | Activate selected result (or first result) |
| **Esc** | Minimize to floating ball |
| **Double-click** | Activate result item |
| **Cmd+M** | Minimize to floating ball (native, routed via changeEvent) |
| **Yellow dot** | Minimize to floating ball (native, routed via changeEvent) |

---

## Platform Notes

### macOS M1 (Apple Silicon) — tested

- **ctypes objc_msgSend** required (pyobjc fails with sip.voidptr)
- **SplashScreen flag** for frameless on-top (Qt.Tool unreliable on Cocoa)
- **No WindowStaysOnTopHint on main window** (Cocoa fights minimize)
- **showMinimized() not hide()** (avoids zoom-down-up-down flicker)
- **ApplicationShortcut for Esc** (QLineEdit swallows Esc otherwise)
- **1s startup guard** (spurious WindowMinimized events during init)
- **QTimer chunks not QThread** (QThread segfaults on M1 with PyQt6)

### Linux (X11) — untested

- X11BypassWindowManagerHint would work here (but is NOT used — it breaks macOS)
- WindowStaysOnTopHint works normally
- Qt.Tool works without parent

### Windows — untested

- WindowStaysOnTopHint works normally
- Qt.Tool works without parent
- ctypes objc_msgSend is not available (no-op fallback)

---

## Provenance

| Component | Source | Adapted from |
|---|---|---|
| Floating ball native properties | Pindrop `DotFloatingIndicator.swift` | `NSPanel` + `nonactivatingPanel` + `level = .mainMenu + 1` + `collectionBehavior` |
| Ghost-text autocomplete | `vbstyle_class_clarifier.py` `GhostTextEdit` | Word freq + bigram model, adapted for QLineEdit |
| Bigram model | `vbstyle_class_clarifier.py` `load_bigrams_from_db` | SQL self-join replaced with Python tokenization (SQL hangs on 225K rows) |
| Tokenizer | `tokenized_context_search.py` `TokenizedSearchIndex.tokenize_text` | Stop words + len > 2 filter |
| MySQL search | `mysql_cli_search.py` `MySQLSearchCLI` | LIKE-based scan across all text columns |
| GUI token capture | `vb_shared.gui_tokens` table | `[@FloatingBall]` token #19 |

---

## File Locations

```
/Users/wws/Qdrant_mysql_mlx_vector_engine/Smart_system_seach/
├── Gui_Smart_search.py           # Main GUI (1006 lines)
├── dom_smart_search.py           # VBStyle search domain (736 lines)
├── Classifier_smart_system.py    # VBStyle classifier domain (792 lines)
├── Config_smart_system.py        # Config constants (245 lines)
├── .bigrams.sqlite               # Bigram cache (6 MB, auto-generated)
├── .wordfreq.sqlite              # Word freq cache (188 KB, auto-generated)
└── README.md                     # This file
```

---

## Deleting the Cache

If the autocomplete data is stale (e.g. new files ingested into `token_registry`), delete the SQLite caches to force a rebuild on next launch:

```bash
rm /Users/wws/Qdrant_mysql_mlx_vector_engine/Smart_system_seach/.bigrams.sqlite
rm /Users/wws/Qdrant_mysql_mlx_vector_engine/Smart_system_seach/.wordfreq.sqlite
```

Next launch will rebuild from MySQL (~55s), then subsequent launches use the fresh cache.
