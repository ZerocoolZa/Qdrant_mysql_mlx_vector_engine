# [@GHOST]{[@file<config.py>][@domain<Dom_Gui>][@role<config>][@auth<cascade>][@date<2026-06-27>][@ver<1.1.0>]}
# [@VBSTYLE]{[@auth<system>][@role<gui_config>][@return<none>][@orch<none>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Config for Dom_Gui — connects to gui_engine DBs, MySQL pipeline, RAM bus}
# [@WCL]{[@self_contained<true>][@no_external_config<true>][@prefix<config>]}

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_VERSION = "1.1.0"

# ─── EXISTING GUI ENGINE PATHS ─────────────────────────────────────────────
# gui_engine.db  — on-disk SQLite: widgets, styles, signals, layouts, edges (629 widgets)
# styles_v2.db   — on-disk SQLite: style properties (objects, stores, selectors)
# ui_v4.db       — on-disk SQLite: UI component tree (components, ui_nodes, ui_screens)
GUI_ENGINE_DIR = os.path.normpath(os.path.join(os.path.dirname(BASE_DIR), os.pardir, "gui_engine"))
GUI_ENGINE_DB = os.path.join(GUI_ENGINE_DIR, "gui_engine.db")
STYLE_DB_V2 = os.path.join(GUI_ENGINE_DIR, "styles_v2.db")
UI_DB_V4 = os.path.join(GUI_ENGINE_DIR, "ui_v4.db")
GUI_ENGINE_SQL = os.path.join(GUI_ENGINE_DIR, "gui_engine_db.sql")
STYLE_DB_V2_SQL = os.path.join(GUI_ENGINE_DIR, "style_db_v2.sql")
UI_DB_V4_SQL = os.path.join(GUI_ENGINE_DIR, "ui_db_v4.sql")

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "unix_socket": "/tmp/mysql.sock",
}

GUI_PIPELINE_DB = "gui_pipeline"
THEMES_TABLE = "themes"

DEFAULT_THEME = "midnight"

THEMES = {
    "midnight": {
        "bg": "#0d1117", "bg_alt": "#161b22", "border": "#30363d",
        "text": "#e6edf3", "muted": "#8b949e", "accent": "#58a6ff",
        "red": "#f85149", "green": "#3fb950", "yellow": "#d29922",
        "font": "Menlo",
    },
    "forest": {
        "bg": "#0D1117", "bg_alt": "#0D2818", "border": "#1a3a2a",
        "text": "#e6edf3", "muted": "#8b949e", "accent": "#3fb950",
        "red": "#f85149", "green": "#3fb950", "yellow": "#d29922",
        "font": "Menlo",
    },
    "sunset": {
        "bg": "#1a0a0a", "bg_alt": "#2a1010", "border": "#3a2020",
        "text": "#f0e0e0", "muted": "#a08080", "accent": "#e94560",
        "red": "#f85149", "green": "#3fb950", "yellow": "#d29922",
        "font": "Menlo",
    },
    "ocean": {
        "bg": "#0a0a14", "bg_alt": "#0D1B2A", "border": "#1a2a3a",
        "text": "#e0e0f0", "muted": "#8090a0", "accent": "#38BDF8",
        "red": "#f85149", "green": "#3fb950", "yellow": "#d29922",
        "font": "Menlo",
    },
}

WIDGET_MAP = {
    "QMainWindow": "QMainWindow",
    "QWidget": "QWidget",
    "QFrame": "QFrame",
    "QLabel": "QLabel",
    "QPushButton": "QPushButton",
    "QTextEdit": "QTextEdit",
    "QLineEdit": "QLineEdit",
    "QTabWidget": "QTabWidget",
    "QComboBox": "QComboBox",
    "QStatusBar": "QStatusBar",
    "QCheckBox": "QCheckBox",
    "QTableWidget": "QTableWidget",
    "QTableView": "QTableView",
    "QTreeView": "QTreeView",
    "QListView": "QListView",
    "QGraphicsView": "QGraphicsView",
    "QGraphicsScene": "QGraphicsScene",
    "QScrollArea": "QScrollArea",
    "QSplitter": "QSplitter",
    "QProgressBar": "QProgressBar",
    "QSlider": "QSlider",
    "QSpinBox": "QSpinBox",
    "QGroupBox": "QGroupBox",
    "QToolBar": "QToolBar",
    "QMenuBar": "QMenuBar",
    "QMenu": "QMenu",
    "QSystemTrayIcon": "QSystemTrayIcon",
    "QDialog": "QDialog",
    "QPlainTextEdit": "QPlainTextEdit",
    "QListWidget": "QListWidget",
    "QTreeWidget": "QTreeWidget",
    "QStackedWidget": "QStackedWidget",
    "QDockWidget": "QDockWidget",
}

SIGNAL_MAP = {
    "clicked": "clicked",
    "triggered": "triggered",
    "textChanged": "textChanged",
    "textEdited": "textEdited",
    "currentIndexChanged": "currentIndexChanged",
    "currentTextChanged": "currentTextChanged",
    "stateChanged": "stateChanged",
    "activated": "activated",
    "valueChanged": "valueChanged",
    "toggled": "toggled",
    "returnPressed": "returnPressed",
    "customContextMenuRequested": "customContextMenuRequested",
    "tabCloseRequested": "tabCloseRequested",
    "tabBarClicked": "tabBarClicked",
    "currentChanged": "currentChanged",
    "pageChanged": "pageChanged",
}

LAYOUT_MAP = {
    "VBox": "QVBoxLayout",
    "HBox": "QHBoxLayout",
    "Grid": "QGridLayout",
    "Form": "QFormLayout",
    "Stack": "QStackedLayout",
}

POLL_INTERVAL_MS = 500

# ─── RAM DB (in-memory SQLite for event/signal routing) ────────────────────
# This is the "GUI bus" — events, signals, slots stored in RAM SQLite
# Created at runtime by bus.py
RAM_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    source_widget TEXT,
    signal_name TEXT,
    handler_name TEXT,
    payload TEXT,
    status TEXT DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_name TEXT NOT NULL,
    signal_name TEXT NOT NULL,
    handler_name TEXT NOT NULL,
    connected_at TEXT DEFAULT (datetime('now')),
    UNIQUE(widget_name, signal_name, handler_name)
);
CREATE INDEX IF NOT EXISTS idx_evt_source ON events(source_widget);
CREATE INDEX IF NOT EXISTS idx_evt_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_slot_widget ON slots(widget_name);
"""

SCHEMA_SQL = """
CREATE DATABASE IF NOT EXISTS {db};
USE {db};
CREATE TABLE IF NOT EXISTS {table} (
    theme_name  VARCHAR(50) NOT NULL,
    `key`       VARCHAR(50) NOT NULL,
    value       VARCHAR(200) NOT NULL,
    category    VARCHAR(20) DEFAULT 'color',
    PRIMARY KEY (theme_name, `key`)
);
""".format(db=GUI_PIPELINE_DB, table=THEMES_TABLE)

# ─── GARMIN NAVIGATOR — HELP / ABOUT / IDEA ─────────────────────────────
# The Garmin Navigator is the GUI's graph exploration engine.
# Like a GPS that drives every road and comes back with a map,
# the Navigator drives every code path and comes back with truth.
#
# THE METAPHOR:
#   You have a city (the codebase). You want to know:
#     - Which roads connect? (call graph)
#     - Which roads are dead ends? (unreachable code)
#     - Which roads are one-way? (irreversible operations)
#     - Which roads have traffic? (hot paths, frequent calls)
#     - Which roads are broken? (missing imports, dead references)
#     - Which roads SHOULD connect but don't? (gap graph)
#     - Which roads SHOULD NOT connect but do? (coupling violations)
#
#   The Navigator dispatches drivers (probes) onto every road.
#   Each driver is a different car (a different perspective):
#     Car 1: Structural driver — "who exists?" (nodes, classes, files)
#     Car 2: Call driver — "who calls who?" (call graph, dispatch tree)
#     Car 3: Data driver — "what flows where?" (data flow, produces/consumes)
#     Car 4: Time driver — "when does it run?" (lifecycle, boot chain, phases)
#     Car 5: Failure driver — "where does it break?" (error paths, recovery)
#     Car 6: Gap driver — "what's missing?" (missing pairs, CRUD closure)
#     Car 7: Cross-domain driver — "what connects across boundaries?" (cross-domain links)
#     Car 8: Simulated driver — "what WOULD happen if...?" (what-if analysis)
#
#   Each driver comes back and reports:
#     - Roads found (edges discovered)
#     - Roads tried (paths attempted)
#     - Roads blocked (dead ends, errors)
#     - Roads suggested (should exist but don't)
#     - Roads warned (shouldn't exist but do)
#
#   The Navigator merges all driver reports into a multi-dimensional map.
#   The map shows the codebase from every angle simultaneously.
#   You can rotate the map (switch dimensions) and see different truths.
#
# THE MEMUNIT CONNECTION:
#   MemUnit is the city center (the kernel / gravity center).
#   MemDB roads are the command queue (streets where commands travel).
#   MemBus roads are the event routes (avenues where signals flow).
#   Executor roads are the dispatch paths (highways to registered targets).
#   Core worlds are districts (config, os, hw, io, error, report).
#   Utility services are buildings (Compress, Indexer, Backup, etc.).
#   Domains are neighborhoods (Dom_Bcl, Dom_Gui, Dom_Vsstyle, etc.).
#   Config is the map legend (what everything means).
#   Credentials is the key ring (who has access to what).
#   MSearch is the search engine (find any address in the city).
#
#   The Navigator answers:
#     "Can I get from Backup to Core_io?" -> yes, via Executor
#     "Can I get from ErrorHandler to Dom_Bcl?" -> yes, via MSearch
#     "Should Scheduler connect to Credentials?" -> yes, for scheduled backups
#     "Should VbsTest connect to MemBus?" -> not yet, but could for event-driven tests
#     "What happens if Core_config disappears?" -> everything breaks (single point of failure)
#     "What's the shortest path from MemUnit to Backup?" -> MemUnit -> Orchestrator -> Backup
#     "What roads exist but aren't used?" -> unused utilities, dead code
#     "What roads are used but don't exist?" -> missing imports, broken refs
#
# THE GARMIN GUI:
#   The GUI shows the map visually. You can:
#     - Zoom in on a domain (see classes and methods)
#     - Zoom out to see the whole kernel (all domains)
#     - Click a road to see what travels on it (data flow)
#     - Click a building to see who enters/exits (call graph)
#     - Click a district to see its internal roads (intra-domain)
#     - Switch between 2D (flat call graph) and 3D (layered architecture)
#     - See traffic lights (errors/blockers) in red
#     - See suggested roads (gaps) in yellow dashed lines
#     - See confirmed roads (working paths) in green
#     - See warned roads (coupling violations) in orange
#
#   The help section in the GUI explains all of this to the user.
#   The about section credits the architecture (MemUnit kernel, VBStyle, BCL).
#   The idea section is where new road suggestions are proposed and voted on.
#
# CONFIG FOR THE NAVIGATOR:
NAVIGATOR_CONFIG = {
    "enabled": True,
    "dimensions": [
        "structural",
        "callgraph",
        "dataflow",
        "lifecycle",
        "failure",
        "gap",
        "cross_domain",
        "simulation",
    ],
    "drivers_per_dimension": 1,
    "max_depth": 10,
    "timeout_seconds": 30,
    "report_format": "json",
    "visualize": True,
    "color_scheme": {
        "confirmed": "#3fb950",
        "suggested": "#d29922",
        "warned": "#e94560",
        "blocked": "#f85149",
        "unused": "#8b949e",
    },
}

HELP_TEXT = """
GARMIN NAVIGATOR — Graph Exploration Engine

The Navigator drives every road in your codebase and comes back with a map.

Each road is a connection between two points.
Each point is a class, method, file, or domain.
Each driver explores a different dimension.

DIMENSIONS:
  1. Structural — who exists? (nodes)
  2. Call Graph — who calls who? (edges)
  3. Data Flow — what flows where? (data movement)
  4. Lifecycle — when does it run? (temporal ordering)
  5. Failure — where does it break? (error paths)
  6. Gap — what's missing? (should exist but doesn't)
  7. Cross-Domain — what connects across boundaries?
  8. Simulation — what WOULD happen if...?

OUTPUTS:
  - Roads found (edges discovered)
  - Roads blocked (dead ends)
  - Roads suggested (gaps — should exist)
  - Roads warned (coupling violations)
  - Roads unused (dead code)

The map is multi-dimensional. Rotate it to see different truths.
"""

ABOUT_TEXT = """
GARMIN NAVIGATOR v1.0

Architecture: MemUnit Kernel (VBStyle)
Pattern: __init__(mem, db, param) + Run(command, params) -> Tuple3
Domains: Dom_Bcl, Dom_Gui, Dom_Vsstyle, Dom_Db, Dom_Graph, Dom_system
Services: 19 utilities (Compress, Indexer, Backup, ErrorHandler, MSearch, etc.)
Orchestration: Config.TRIGGERS (BCL-style rules)
Scheduling: Config.SCHEDULES (timer + event)
Credentials: env vars + .credentials file (base64)
Search: msearch binary (MySQL + Qdrant vector)

The Navigator is part of the Dom_Gui domain.
It uses the same Tuple3 + Run() pattern as everything else.
It connects to MemBus for events and MemDB for state.
"""

IDEA_TEXT = """
GARMIN NAVIGATOR — IDEA BOARD

Suggested roads to build:
  1. VbsTest -> MemBus (event-driven testing)
  2. Scheduler -> Credentials (scheduled credential rotation)
  3. MSearch -> Orchestrator (auto-trigger on search results)
  4. Backup -> MemDB (queue backups as commands)
  5. ErrorHandler -> MemBus (publish errors as events)
  6. Dom_Bcl -> Orchestrator (BCL rules define triggers)
  7. Dom_Vsstyle -> VbsTest (enforcer feeds test engine)
  8. Dom_Gui -> Scheduler (GUI triggers scheduled tasks)

Suggested roads to close:
  1. Core_config <-> Config.py (merge into single authority)
  2. MemDB <-> ErrorTracker (shared SQLite schema)
  3. MemBus <-> Scheduler (event-driven scheduling)
  4. Executor <-> Orchestrator (merge dispatch logic)

Roads to watch (coupling risks):
  1. ErrorHandler -> MySQL (direct dependency, should go through MSearch)
  2. Backup -> boto3 (external dependency, should wrap in try/catch)
  3. Config -> everything (changes ripple everywhere)
"""
