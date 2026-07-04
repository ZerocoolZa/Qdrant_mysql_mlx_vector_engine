-- GuisEngins_db.sql — Schema for GUIs Engines database
-- Stores every GUI engine file, class, computational unit, method
-- With BCL stamps (reasoning + details) for EVERY block
-- Hierarchy: file >> class >> comp_unit >> method >> bcl_stamp

CREATE TABLE IF NOT EXISTS gui_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'python',
    file_hash TEXT,
    full_source TEXT,
    line_count INTEGER DEFAULT 0,
    purpose TEXT,
    domain TEXT,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gui_classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    class_name TEXT NOT NULL,
    base_class TEXT,
    line_start INTEGER,
    line_end INTEGER,
    method_count INTEGER DEFAULT 0,
    is_qt_window INTEGER DEFAULT 0,
    source_text TEXT,
    purpose TEXT,
    domain TEXT,
    FOREIGN KEY (file_id) REFERENCES gui_files(id)
);
CREATE INDEX IF NOT EXISTS idx_gse_gc_class ON gui_classes(class_name);
CREATE INDEX IF NOT EXISTS idx_gse_gc_file ON gui_classes(file_path);

CREATE TABLE IF NOT EXISTS gui_comp_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    class_name TEXT NOT NULL,
    unit_name TEXT NOT NULL,
    unit_type TEXT NOT NULL CHECK (unit_type IN
        ('METHOD','FUNCTION','INIT','RUN','DISPATCH','HANDLER','RENDERER',
         'BUILDER','PARSER','VALIDATOR','SCANNER','READER','WRITER',
         'PROPERTY','LAMBDA','NESTED','MAIN_BLOCK','MODULE_CONST')),
    line_start INTEGER,
    line_end INTEGER,
    line_count INTEGER DEFAULT 0,
    source_text TEXT,
    docstring TEXT,
    calls TEXT,
    returns TEXT,
    params TEXT,
    is_vbstyle INTEGER DEFAULT 0,
    has_run INTEGER DEFAULT 0,
    has_state INTEGER DEFAULT 0,
    returns_tuple3 INTEGER DEFAULT 0,
    FOREIGN KEY (class_id) REFERENCES gui_classes(id)
);
CREATE INDEX IF NOT EXISTS idx_gse_gcu_class ON gui_comp_units(class_name);
CREATE INDEX IF NOT EXISTS idx_gse_gcu_file ON gui_comp_units(file_path);
CREATE INDEX IF NOT EXISTS idx_gse_gcu_type ON gui_comp_units(unit_type);

CREATE TABLE IF NOT EXISTS gui_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comp_unit_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    class_name TEXT NOT NULL,
    method_name TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    line_count INTEGER DEFAULT 0,
    source_text TEXT,
    docstring TEXT,
    params TEXT,
    calls TEXT,
    widget_refs TEXT,
    is_handler INTEGER DEFAULT 0,
    is_vbstyle INTEGER DEFAULT 0,
    returns_tuple3 INTEGER DEFAULT 0,
    FOREIGN KEY (comp_unit_id) REFERENCES gui_comp_units(id)
);
CREATE INDEX IF NOT EXISTS idx_gse_gm_class ON gui_methods(class_name);
CREATE INDEX IF NOT EXISTS idx_gse_gm_method ON gui_methods(method_name);
CREATE INDEX IF NOT EXISTS idx_gse_gm_file ON gui_methods(file_path);

CREATE TABLE IF NOT EXISTS gui_bcl_stamps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_type TEXT NOT NULL CHECK (scope_type IN
        ('FILE','CLASS','COMP_UNIT','METHOD')),
    scope_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    class_name TEXT,
    unit_name TEXT,
    method_name TEXT,
    stamp_tier TEXT NOT NULL DEFAULT 'SURFACE',
    stamp_tag TEXT NOT NULL,
    stamp_key TEXT,
    stamp_value TEXT,
    reasoning TEXT,
    details TEXT,
    line_num INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_gse_gbs_scope ON gui_bcl_stamps(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_gse_gbs_tag ON gui_bcl_stamps(stamp_tag);
CREATE INDEX IF NOT EXISTS idx_gse_gbs_file ON gui_bcl_stamps(file_path);
CREATE INDEX IF NOT EXISTS idx_gse_gbs_class ON gui_bcl_stamps(class_name);

CREATE TABLE IF NOT EXISTS gui_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    from_class TEXT,
    from_method TEXT,
    to_class TEXT,
    to_method TEXT,
    edge_type TEXT NOT NULL CHECK (edge_type IN
        ('CALLS','CONTAINS','INHERITS','IMPORTS','REFERENCES','DECORATES',
         'DISPATCHES_TO','RETURNS_TO','SIGNAL_TO')),
    line_num INTEGER,
    evidence TEXT
);
CREATE INDEX IF NOT EXISTS idx_gse_ge_from ON gui_edges(from_class, from_method);
CREATE INDEX IF NOT EXISTS idx_gse_ge_to ON gui_edges(to_class, to_method);
CREATE INDEX IF NOT EXISTS idx_gse_ge_type ON gui_edges(edge_type);
