#!/usr/bin/env python3
"""Config for Dom_DecisionTrees. All constants, paths, descriptions, purposes."""

from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "decision_trees.db"

SOURCES = [
    Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui"),
    Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Unified"),
    Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/gui_engine"),
    Path("/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Magic_Clipboard_gui"),
]

DESCRIPTIONS = {
    "parser.py": "Parses BCL bracket declarations from Python source into GUITreeNode tree. WCL format reader.",
    "builder.py": "Walks GUITreeNode tree, instantiates real PyQt6 widgets, applies layouts and properties from BCL config.",
    "router.py": "Event manager. Connects BCL SIGNAL declarations to real PyQt6 signal/slot connections on host object.",
    "bus.py": "In-RAM SQLite event bus for GUI signal/slot routing. Logs events, queues signals, dispatches to handlers.",
    "config.py": "Configuration for Dom_Gui. DB paths, MySQL config, themes (midnight/forest/sunset/ocean), RAM schema.",
    "node.py": "GUITreeNode data class. Holds widget type, name, parent, properties, children, tab_name, order, line_num.",
    "theme.py": "Theme loader. Applies color schemes and font settings to PyQt6 widgets.",
    "db.py": "SQLite DB connector for Dom_Gui. Connects to gui_engine.db, styles_v2.db, ui_v4.db.",
    "graphs.py": "Graph rendering helpers for Dom_Gui. Generates visual representations of widget trees.",
    "__init__.py": "Package init for Dom_Gui domain.",
    "clipboard_monitor.py": "Original clipboard monitor. Tracks clipboard changes and manages clipboard history.",
    "clipboard_monitor_v2.py": "Advanced clipboard monitor v2. Full GUI with history, search, categories, and clipboard management.",
    "code_compare_gui.py": "GUI for comparing two code snippets side by side with syntax highlighting.",
    "code_studio.py": "Code studio GUI. Editor with toolbar, file tree, and output panel.",
    "code_studio_redesigned.py": "Redesigned code studio with improved layout, tabbed editor, and integrated tools.",
    "design_validator_v3.py": "Design validator v3. Validates GUI designs against rules, checks completeness, reports violations.",
    "gui_decision_engine.py": "GUI decision engine. Executable UI reasoning: context ingestion, candidate generation, hard filter, conflict resolution, scoring, reason trace.",
    "gui_file_analyzer.py": "Analyzes GUI files for structure, dependencies, and design patterns.",
    "gui_loader.py": "Loads GUI definitions from DB or JSON files into widget tree structures.",
    "gui_rationale_db_setup.py": "Sets up SQLite DB for GUI rationale storage. Tables for decisions, principles, learnings.",
    "gui_rationale_generator.py": "Generates GUI design rationales from code analysis. Explains why each widget was chosen.",
    "model_backend.py": "Model backend for GUI. Connects UI to data models and business logic.",
    "qt_renderer.py": "Qt style renderer. Applies DB-stored styles to PyQt6 widgets as QSS.",
    "qt_renderer_v2.py": "Qt renderer v2. Improved style application with caching and inheritance.",
    "qt_renderer_v3.py": "Qt renderer v3. Hybrid architecture combining DB styles with engine-driven styles.",
    "ui_compiler_v4.py": "UI compiler v4. Builds UI tree from DB by recursively traversing nodes and merging component defaults.",
    "ui_db_v4.py": "UI database v4. SQLite schema for UI components, nodes, screens, and properties.",
    "ui_renderer_v4.py": "UI renderer v4. Renders tree to PyQt6 widgets. Maps component types to QPushButton, QLabel, QLineEdit, etc.",
    "ui_validator.py": "UI validator. Checks UI trees for completeness, required properties, and structural integrity.",
    "add_toolbar_rationale.py": "Documents rationale for toolbar additions. Explains why each toolbar action exists.",
    "Config.py": "Config for gui_engine. Paths to SQLite DBs, MySQL config, embedding settings.",
    "Config_gui_engine.py": "Extended config for gui_engine. DB paths, table names, embedding dimensions, batch sizes.",
    "GuiEmbedder.py": "Generates and stores vector embeddings for GUI components. Connects to Qdrant or local embedding model.",
    "GuiIngester.py": "Ingests GUI component definitions from Python source into SQLite. Parses widgets, styles, signals, layouts.",
    "GuisEnginsIngester.py": "Ingests GUI engine data from multiple sources. Handles SQLite, MySQL, and disk-based GUI definitions.",
    "config_extractor.py": "Extracts configuration values from Python source files. Finds constants, paths, and settings.",
    "edge_case_test.py": "Tests edge cases for GUI engine ingestion. Validates handling of malformed inputs and unusual structures.",
    "gui_engine.py": "Main GUI engine. Orchestrates ingestion, embedding, and querying of GUI components. Central entry point.",
    "CacheDb.py": "Cache database layer for Dom_Unified. Manages in-memory and on-disk caching of computed results.",
    "ConfigCascade.py": "Config Cascade engine. Scans .py files, extracts constants, generates Config.py automatically.",
    "DatabaseManager.py": "Database manager for Dom_Unified. Handles MySQL and SQLite connections, schema creation, migrations.",
    "DomExecutionEngine.py": "Execution engine for Dom_Unified. Runs pipeline stages, manages state transitions, tracks progress.",
    "DomIndexer.py": "Indexer for Dom_Unified. Indexes code, chat, and documents for fast retrieval.",
    "DomReport.py": "Report generator for Dom_Unified. Generates pipeline status reports, gap analysis, metrics.",
    "DomReuse.py": "Reuse engine for Dom_Unified. Finds reusable code patterns, tracks reuse weights, suggests duplicates.",
    "DomSessionGraph.py": "Session graph for Dom_Unified. Tracks conversation sessions as graph nodes and edges.",
    "DomSystem.py": "Main Dom system orchestrator. Coordinates all domains, routes commands, manages lifecycle.",
    "ErrorCapture.py": "Error capture for Dom_Unified. Catches errors, stores in SQLite, promotes to MySQL, learns from failures.",
    "LocalAgent.py": "Local agent for Dom_Unified. Runs tasks locally, manages subprocesses, handles agent communication.",
    "MagneticGraph.py": "Magnetic graph engine. Builds context radius around search hits, expands to natural boundaries.",
    "MemoryObject.py": "Memory object system for Dom_Unified. Manages persistent memory, state, and object lifecycle.",
    "Neo4jGraph.py": "Neo4j graph connector for Dom_Unified. Pushes nodes and edges to Neo4j for graph queries.",
    "UnifiedAst.py": "Unified AST processor. Parses Python source into AST, extracts classes, methods, imports.",
    "c_class_builder.py": "C class builder. Generates C code from Python class definitions for performance-critical paths.",
    "spec_graph_runner.py": "Spec graph runner. Executes specification graphs, validates pipeline stages against specs.",
}

PURPOSES = {
    "parser.py": "Parse BCL/WCL bracket declarations into widget tree",
    "builder.py": "Build PyQt6 widgets from parsed tree",
    "router.py": "Route signals to handler methods",
    "bus.py": "In-RAM event bus for signal/slot dispatch",
    "config.py": "Configuration and theme definitions",
    "node.py": "Data class for widget tree nodes",
    "theme.py": "Apply visual themes to widgets",
    "db.py": "Database access layer for GUI engine",
    "graphs.py": "Render widget trees as visual graphs",
    "__init__.py": "Package initialization",
    "clipboard_monitor.py": "Monitor system clipboard",
    "clipboard_monitor_v2.py": "Advanced clipboard management GUI",
    "code_compare_gui.py": "Side-by-side code comparison",
    "code_studio.py": "Code editor GUI",
    "code_studio_redesigned.py": "Improved code editor with tabs",
    "design_validator_v3.py": "Validate GUI design completeness",
    "gui_decision_engine.py": "Executable UI reasoning engine",
    "gui_file_analyzer.py": "Analyze GUI file structure",
    "gui_loader.py": "Load GUI definitions from DB/JSON",
    "gui_rationale_db_setup.py": "Setup rationale storage DB",
    "gui_rationale_generator.py": "Generate design rationales",
    "model_backend.py": "Connect UI to data models",
    "qt_renderer.py": "Apply QSS styles to widgets",
    "qt_renderer_v2.py": "Improved style renderer with caching",
    "qt_renderer_v3.py": "Hybrid style renderer",
    "ui_compiler_v4.py": "Compile DB nodes to UI tree",
    "ui_db_v4.py": "UI component database schema",
    "ui_renderer_v4.py": "Render UI tree to Qt widgets",
    "ui_validator.py": "Validate UI tree integrity",
    "add_toolbar_rationale.py": "Document toolbar decisions",
    "Config.py": "Configuration constants and paths",
    "Config_gui_engine.py": "Extended configuration for GUI engine pipeline",
    "GuiEmbedder.py": "Generate vector embeddings for GUI components",
    "GuiIngester.py": "Ingest GUI definitions from Python source",
    "GuisEnginsIngester.py": "Multi-source GUI engine ingestion",
    "config_extractor.py": "Extract config values from source files",
    "edge_case_test.py": "Test edge cases in ingestion",
    "gui_engine.py": "Main GUI engine orchestrator",
    "CacheDb.py": "Cache layer for computed results",
    "ConfigCascade.py": "Auto-generate Config.py from source",
    "DatabaseManager.py": "MySQL and SQLite connection manager",
    "DomExecutionEngine.py": "Run pipeline stages and track state",
    "DomIndexer.py": "Index code, chat, and documents",
    "DomReport.py": "Generate pipeline status reports",
    "DomReuse.py": "Find reusable code patterns",
    "DomSessionGraph.py": "Track sessions as graph nodes",
    "DomSystem.py": "Main system orchestrator",
    "ErrorCapture.py": "Capture and learn from errors",
    "LocalAgent.py": "Run local tasks and subprocesses",
    "MagneticGraph.py": "Context radius graph expansion",
    "MemoryObject.py": "Persistent memory and object lifecycle",
    "Neo4jGraph.py": "Push nodes and edges to Neo4j",
    "UnifiedAst.py": "Parse Python AST for extraction",
    "c_class_builder.py": "Generate C code from Python classes",
    "spec_graph_runner.py": "Execute and validate spec graphs",
}

LOCAL_MODULES = {
    "config", "Config", "Config_gui_engine", "Config_CoreMLLayout",
    "node", "parser", "builder", "router", "bus", "theme", "db", "graphs",
    "gui_engine", "GuiEmbedder", "GuiIngester", "GuisEnginsIngester",
    "config_extractor", "edge_case_test",
    "style_db", "style_db_v2", "style_db_v3", "StyleDB", "StyleDBV2", "StyleDBV3",
    "style_engine", "style_engine_v3", "StyleEngineV3",
    "qt_renderer", "QtStyleRenderer",
    "ui_db_v4", "UIDBV4",
    "ui_compiler_v4", "UICompilerV4",
    "ui_renderer_v4", "UIRendererV4",
    "ui_validator",
    "gui_loader", "gui_decision_engine", "gui_file_analyzer",
    "gui_rationale_db_setup", "gui_rationale_generator",
    "model_backend", "clipboard_monitor", "clipboard_monitor_v2",
    "code_compare_gui", "code_studio", "code_studio_redesigned",
    "design_validator_v3", "add_toolbar_rationale",
    "CacheDb", "ConfigCascade", "DatabaseManager", "DomExecutionEngine",
    "DomIndexer", "DomReport", "DomReuse", "DomSessionGraph", "DomSystem",
    "ErrorCapture", "LocalAgent", "MagneticGraph", "MemoryObject",
    "Neo4jGraph", "UnifiedAst", "c_class_builder", "spec_graph_runner",
}

# ─── GUI CONSTANTS (moved from DecisionTreeGui.py for config-driven engine) ──

TREE_CONFIG_DEFAULT = {
    "root_label": "Code Decision Tree",
    "group_by": "category",
    "show_methods": True,
    "show_file_count": True,
    "show_method_count": True,
    "filter_category": "",
    "filter_file": "",
    "max_methods_per_node": 30,
    "color_scheme": "dark",
    "node_spacing_x": 200,
    "node_spacing_y": 80,
    "node_width": 160,
    "node_height": 40,
    "orientation": "vertical",
    "show_arrows": True,
    "arrow_style": "curved"
}

COLOR_SCHEMES = {
    "dark": {
        "bg": "#1e1e2e",
        "canvas_bg": "#181825",
        "text": "#cdd6f4",
        "category": "#89b4fa",
        "file": "#a6e3a1",
        "method": "#f9e2af",
        "class": "#f5c2e7",
        "root": "#cba6f7",
        "selection": "#313244",
        "border": "#45475a",
        "arrow": "#585b70",
        "category_bg": "#1e1e2e",
        "file_bg": "#1a2a1a",
        "method_bg": "#2a2a1a",
        "root_bg": "#2a1a2a"
    },
    "light": {
        "bg": "#ffffff",
        "canvas_bg": "#f5f5f5",
        "text": "#1e1e2e",
        "category": "#1973e0",
        "file": "#40a02b",
        "method": "#df8e1d",
        "class": "#d20f87",
        "root": "#7c3aed",
        "selection": "#e6e6e6",
        "border": "#cccccc",
        "arrow": "#999999",
        "category_bg": "#e8f0fe",
        "file_bg": "#e8f5e9",
        "method_bg": "#fff8e1",
        "root_bg": "#f3e5f5"
    }
}

BCL_NODE_COLORS = {
    "Pass":   ("#10b981", "#06281f"),
    "Fail":   ("#ef4444", "#2a1010"),
    "Unsure": ("#f59e0b", "#2a2010"),
    "Wait":   ("#6366f1", "#1a1a2a"),
    "Rule":   ("#3b82f6", "#0f1a2a"),
    "Check":  ("#64748b", "#1a1a22"),
    "Leaf":   ("#a6e3a1", "#1a2a1a"),
}

NODE_RADIUS = 10

# ─── WCL (Wayne Cascade Language) GUI DECLARATIONS ──────────────────────────
# Parsed by GUIParser from core.Dom_Gui to build the GUI shell.
# Format: # [@TAG]{[@key<value>][@key<value>]}
# The canvas (DecisionTreeCanvas) is custom and inserted post-build.

WCL_CONFIG = """
# [@GUI]{[@size<1400x900>][@title<Decision Tree GUI — Dom_DecisionTrees>]}
# [@WIDGET]{[@type<QWidget>][@name<central>][@layout<VBox>]}
# [@WIDGET]{[@type<QSplitter>][@name<splitter>][@parent<central>]}
# [@WIDGET]{[@type<QWidget>][@name<left_panel>][@parent<splitter>][@layout<VBox>]}
# [@WIDGET]{[@type<QLabel>][@name<left_label>][@parent<left_panel>][@text<Tree Config (JSON) — edits update canvas live>]}
# [@WIDGET]{[@type<QPlainTextEdit>][@name<json_editor>][@parent<left_panel>]}
# [@WIDGET]{[@type<QWidget>][@name<ctrl_row>][@parent<left_panel>][@layout<HBox>]}
# [@WIDGET]{[@type<QLabel>][@name<mode_label>][@parent<ctrl_row>][@text<Mode:>]}
# [@WIDGET]{[@type<QComboBox>][@name<mode_combo>][@parent<ctrl_row>]}
# [@WIDGET]{[@type<QLabel>][@name<group_label>][@parent<ctrl_row>][@text<Group:>]}
# [@WIDGET]{[@type<QComboBox>][@name<group_combo>][@parent<ctrl_row>]}
# [@WIDGET]{[@type<QLabel>][@name<orient_label>][@parent<ctrl_row>][@text<Orient:>]}
# [@WIDGET]{[@type<QComboBox>][@name<orient_combo>][@parent<ctrl_row>]}
# [@WIDGET]{[@type<QLabel>][@name<max_label>][@parent<ctrl_row>][@text<Max:>]}
# [@WIDGET]{[@type<QSpinBox>][@name<max_spin>][@parent<ctrl_row>]}
# [@WIDGET]{[@type<QPushButton>][@name<rebuild_btn>][@parent<ctrl_row>][@text<Rebuild>]}
# [@WIDGET]{[@type<QPushButton>][@name<reset_zoom_btn>][@parent<ctrl_row>][@text<Fit View>]}
# [@WIDGET]{[@type<QWidget>][@name<search_row>][@parent<left_panel>][@layout<HBox>]}
# [@WIDGET]{[@type<QLabel>][@name<search_label>][@parent<search_row>][@text<Search:>]}
# [@WIDGET]{[@type<QLineEdit>][@name<search_box>][@parent<search_row>][@placeholder<highlight nodes by label...>]}
# [@WIDGET]{[@type<QPushButton>][@name<search_clear_btn>][@parent<search_row>][@text<Clear>]}
# [@WIDGET]{[@type<QWidget>][@name<right_panel>][@parent<splitter>][@layout<VBox>]}
# [@WIDGET]{[@type<QTabWidget>][@name<tabs>][@parent<right_panel>]}
# [@WIDGET]{[@type<QPlainTextEdit>][@name<code_preview>][@parent<tabs>][@tabname<Code Preview>][@readonly<true>]}
# [@WIDGET]{[@type<QPlainTextEdit>][@name<bcl_preview>][@parent<tabs>][@tabname<BCL / IR>][@readonly<true>]}
# [@WIDGET]{[@type<QPlainTextEdit>][@name<dep_preview>][@parent<tabs>][@tabname<Dependencies>][@readonly<true>]}
# [@WIDGET]{[@type<QPlainTextEdit>][@name<bcl_editor>][@parent<tabs>][@tabname<BCL Tuple Editor>][@readonly<true>]}
# [@SIGNAL]{[@widget<mode_combo>][@signal<currentTextChanged>][@handler<on_mode_changed>]}
# [@SIGNAL]{[@widget<group_combo>][@signal<currentTextChanged>][@handler<on_combo_changed>]}
# [@SIGNAL]{[@widget<orient_combo>][@signal<currentTextChanged>][@handler<on_combo_changed>]}
# [@SIGNAL]{[@widget<max_spin>][@signal<valueChanged>][@handler<on_combo_changed>]}
# [@SIGNAL]{[@widget<rebuild_btn>][@signal<clicked>][@handler<rebuild_tree>]}
# [@SIGNAL]{[@widget<reset_zoom_btn>][@signal<clicked>][@handler<on_fit_view>]}
# [@SIGNAL]{[@widget<search_box>][@signal<textChanged>][@handler<on_search_changed>]}
# [@SIGNAL]{[@widget<search_clear_btn>][@signal<clicked>][@handler<on_search_clear>]}
# [@SIGNAL]{[@widget<json_editor>][@signal<textChanged>][@handler<schedule_json_update>]}
"""
