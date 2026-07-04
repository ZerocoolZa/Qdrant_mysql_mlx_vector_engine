-- gui_engine_db.sql — Schema for GUI code graph database
-- Stores every PyQt6 widget, style, signal, and layout as queryable rows
-- Nodes = widgets, edges = parent-child + signal-handler + style-on + layout-of

CREATE TABLE IF NOT EXISTS gui_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_hash TEXT,
    full_source TEXT,
    line_count INTEGER DEFAULT 0,
    class_count INTEGER DEFAULT 0,
    widget_count INTEGER DEFAULT 0,
    signal_count INTEGER DEFAULT 0,
    style_count INTEGER DEFAULT 0,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gui_classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    class_name TEXT NOT NULL,
    base_class TEXT,
    line_start INTEGER,
    line_end INTEGER,
    is_qmainwindow INTEGER DEFAULT 0,
    method_count INTEGER DEFAULT 0,
    FOREIGN KEY (file_path) REFERENCES gui_files(file_path)
);
CREATE INDEX IF NOT EXISTS idx_gc_class ON gui_classes(class_name);
CREATE INDEX IF NOT EXISTS idx_gc_file ON gui_classes(file_path);

CREATE TABLE IF NOT EXISTS gui_widgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    class_name TEXT,
    widget_var TEXT NOT NULL,
    widget_type TEXT NOT NULL,
    widget_text TEXT,
    parent_var TEXT,
    parent_type TEXT,
    line_num INTEGER,
    context TEXT,
    properties_json TEXT,
    FOREIGN KEY (file_path) REFERENCES gui_files(file_path)
);
CREATE INDEX IF NOT EXISTS idx_gw_var ON gui_widgets(widget_var);
CREATE INDEX IF NOT EXISTS idx_gw_type ON gui_widgets(widget_type);
CREATE INDEX IF NOT EXISTS idx_gw_file ON gui_widgets(file_path);
CREATE INDEX IF NOT EXISTS idx_gw_class ON gui_widgets(class_name);

CREATE TABLE IF NOT EXISTS gui_styles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    class_name TEXT,
    widget_var TEXT,
    selector TEXT,
    property_name TEXT,
    property_value TEXT,
    raw_stylesheet TEXT,
    line_num INTEGER,
    FOREIGN KEY (file_path) REFERENCES gui_files(file_path)
);
CREATE INDEX IF NOT EXISTS idx_gs_var ON gui_styles(widget_var);
CREATE INDEX IF NOT EXISTS idx_gs_file ON gui_styles(file_path);

CREATE TABLE IF NOT EXISTS gui_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    class_name TEXT,
    widget_var TEXT NOT NULL,
    signal_name TEXT NOT NULL,
    handler_name TEXT NOT NULL,
    handler_type TEXT,
    line_num INTEGER,
    FOREIGN KEY (file_path) REFERENCES gui_files(file_path)
);
CREATE INDEX IF NOT EXISTS idx_gsig_var ON gui_signals(widget_var);
CREATE INDEX IF NOT EXISTS idx_gsig_handler ON gui_signals(handler_name);
CREATE INDEX IF NOT EXISTS idx_gsig_file ON gui_signals(file_path);

CREATE TABLE IF NOT EXISTS gui_layouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    class_name TEXT,
    layout_var TEXT NOT NULL,
    layout_type TEXT NOT NULL,
    parent_var TEXT,
    line_num INTEGER,
    FOREIGN KEY (file_path) REFERENCES gui_files(file_path)
);
CREATE INDEX IF NOT EXISTS idx_gl_var ON gui_layouts(layout_var);
CREATE INDEX IF NOT EXISTS idx_gl_file ON gui_layouts(file_path);

CREATE TABLE IF NOT EXISTS gui_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    from_var TEXT,
    to_var TEXT,
    edge_type TEXT NOT NULL CHECK (edge_type IN
        ('CONTAINS','SIGNAL_TO','STYLE_ON','LAYOUT_OF','PARENT_OF','ADD_WIDGET','ADD_TAB','SET_CENTRAL')),
    line_num INTEGER,
    evidence TEXT,
    FOREIGN KEY (file_path) REFERENCES gui_files(file_path)
);
CREATE INDEX IF NOT EXISTS idx_ge_from ON gui_edges(from_var);
CREATE INDEX IF NOT EXISTS idx_ge_to ON gui_edges(to_var);
CREATE INDEX IF NOT EXISTS idx_ge_type ON gui_edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_ge_file ON gui_edges(file_path);

CREATE TABLE IF NOT EXISTS gui_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    class_name TEXT,
    method_name TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    is_handler INTEGER DEFAULT 0,
    widget_refs TEXT,
    FOREIGN KEY (file_path) REFERENCES gui_files(file_path)
);
CREATE INDEX IF NOT EXISTS idx_gm_class ON gui_methods(class_name);
CREATE INDEX IF NOT EXISTS idx_gm_method ON gui_methods(method_name);
CREATE INDEX IF NOT EXISTS idx_gm_file ON gui_methods(file_path);

CREATE TABLE IF NOT EXISTS gui_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_type TEXT NOT NULL,
    file_path TEXT,
    class_name TEXT,
    widget_var TEXT,
    description TEXT,
    severity TEXT DEFAULT 'info',
    found_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_gf_type ON gui_findings(finding_type);
