-- style_db_v2.sql — Schema for StyleDBV2 (GUI object styling)
-- Tables: gui_objects, property_stores, style_selectors

CREATE TABLE IF NOT EXISTS gui_objects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_type TEXT NOT NULL,
    object_name TEXT NOT NULL,
    UNIQUE(object_type, object_name)
);

CREATE TABLE IF NOT EXISTS property_stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS style_selectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    property_name TEXT NOT NULL,
    property_value TEXT,
    UNIQUE(object_id, store_id, property_name),
    FOREIGN KEY (object_id) REFERENCES gui_objects(id),
    FOREIGN KEY (store_id) REFERENCES property_stores(id)
);
