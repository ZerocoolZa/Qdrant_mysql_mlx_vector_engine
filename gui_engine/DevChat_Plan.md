# GUI Engine — DevChat Plan

> **Module**: `gui_engine/`
> **Created**: 2026-06-22
> **Status**: Working — engine built, needs Ghost settings panel

---

## What Was Built (Session History)

### Session 1 — GUI Engine Refactor (history_2ebe8b3b7d2f4178)
- Refactored Chat Memory GUI to be config-driven
- Leveraged existing GUI Engine from `GuiSystem/engine.py`
- Created configuration files for GUI elements
- Connected GUI logic to chat memory handlers
- Used `WidgetBuilder.Run(command, params) -> Tuple3` pattern

### Session 2 — GUI Engine Module
- Built `gui_engine.py` — standalone GUI engine (PyQt6)
- Built `Config.py` — GUI configuration
- Built `config_extractor.py` — extract config from schema
- Built `edge_case_test.py` — edge case testing

### Related Sessions
- Original `GuiSystem/engine.py` (1045 lines) was built in contestsystem
- 100% config-driven PyQt6 renderer
- WidgetBuilder maps type strings to PyQt6 classes
- Supports: QTextEdit, QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox, QSlider, QSpinBox, QFrame, QWidget, QGroupBox, QProgressBar, QRadioButton, QTabWidget, QSplitter, QScrollArea, QStackedWidget, QToolBar, QTableView, QTreeView, QListView, FaceWidget, ChatBubble
- ConfigWatcher supports hot-reload of JSON configs
- ConfigStore provides SQLite-backed config storage

---

## Current File Inventory

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `gui_engine.py` | ~600 | Config-driven PyQt6 GUI renderer | Working |
| `Config.py` | ~200 | GUI configuration constants | Working |
| `config_extractor.py` | ~300 | Extract config from schema for auto-generation | Working |
| `edge_case_test.py` | ~200 | Edge case tests | Working |

---

## What Works

- Config-driven GUI rendering from schema
- WidgetBuilder with Run/Tuple3 VBStyle pattern
- Supports 20+ PyQt6 widget types
- Config extraction for auto-generating panels
- Edge case testing

---

## What's Broken / Incomplete

### P1 — Should Fix
1. **ConfigWatcher reads JSON** — PLAN.md says no JSON. Need to convert to BCL/SQLite config loading.
2. **No settings property panel** — PLAN.md build order step 8 calls for `gui/settings_gui.py` with tree + search + combos. Not built yet.
3. **Not connected to Ghost config** — GUI doesn't read/write Ghost's config.py

### P2 — Nice to Have
4. **No unit tests** (edge_case_test.py is manual, not automated)
5. **No hot-reload from SQLite** — ConfigWatcher only watches JSON files
6. **No BCL config support** — only reads JSON

---

## Next Steps

1. **Convert ConfigWatcher** — read from SQLite/BCL instead of JSON
2. **Build settings property panel** — tree structure, search bar, combo boxes (PLAN.md Section 3)
3. **Connect to Ghost config** — GUI reads/writes `ghost/config.py`
4. **Add BCL config support** — parse BCL-formatted config values
5. **Add automated unit tests**

---

## Integration with Ghost Core

GUI engine becomes the **SettingsGUI** in Ghost (PLAN.md build order step 8):

```
ghost/gui/settings_gui.py
  └── uses gui_engine.py WidgetBuilder for rendering
  └── reads config schema from ghost/config.py
  └── auto-generates property panel (tree + search + combos)
  └── writes changes back to SQLite config table in BCL format
  └── `ghost settings` command opens this panel
```

The GUI also serves as the **code editor** for the SQLite code-as-filesystem — editing methods stored as rows in the `methods` table.
