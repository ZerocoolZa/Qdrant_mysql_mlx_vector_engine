-- ui_db_v4.sql — Schema for UIDBV4 (UI component tree)
-- Tables: components, ui_nodes, ui_screens

CREATE TABLE IF NOT EXISTS components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_type TEXT NOT NULL,
    component_name TEXT NOT NULL,
    base_component TEXT,
    properties TEXT,
    UNIQUE(component_type, component_name)
);

CREATE TABLE IF NOT EXISTS ui_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER,
    component_id INTEGER NOT NULL,
    node_name TEXT NOT NULL,
    properties TEXT,
    order_index INTEGER DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES ui_nodes(id),
    FOREIGN KEY (component_id) REFERENCES components(id)
);

CREATE TABLE IF NOT EXISTS ui_screens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screen_name TEXT NOT NULL UNIQUE,
    root_node_id INTEGER NOT NULL,
    FOREIGN KEY (root_node_id) REFERENCES ui_nodes(id)
);
