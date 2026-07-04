-- [@GHOST]{[@file<config_seed.sql>][@domain<search>][@role<config_seed>][@auth<cascade>][@date<2026-06-22>][@ver<5.0>]}

-- Config seed for CascadeSearch v5
-- All values configurable — no hardcoded paths in the C binary

CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    description TEXT
);

INSERT OR IGNORE INTO config VALUES
('mysql_host',              'localhost',                          'MySQL server hostname'),
('mysql_user',              'root',                               'MySQL username'),
('mysql_pass',              '',                                   'MySQL password (empty = no password)'),
('mysql_db',                'vb_shared',                          'Default database'),
('mysql_port',              '3306',                               'MySQL port'),
('default_limit',           '50',                                 'Default row limit per table'),
('qdrant_url',              'http://localhost:6333',              'Qdrant REST API URL'),
('qdrant_helper',           '',                                   'Path to msearch_qdrant.py (empty = auto-detect from HOME)'),
('qdrant_default_collection','dim_semantic',                      'Default Qdrant collection'),
('qdrant_default_top',      '10',                                 'Default number of vector results'),
('vbcheck_path',            '',                                   'Path to vbcheck binary (empty = auto-detect from HOME)');
