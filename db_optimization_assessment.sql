-- ============================================================
-- MySQL Storage Optimization Auditor — 6-Phase Analysis
-- ============================================================
-- Produces a single prioritized roadmap with estimated savings.
-- Portable: discovers schema from information_schema.
-- Safe: READ-ONLY. No modifications to any database.
-- ============================================================

USE vb_shared;
DROP TEMPORARY TABLE IF EXISTS opt_findings;

CREATE TEMPORARY TABLE opt_findings (
    phase VARCHAR(20),
    priority INT,
    category VARCHAR(50),
    object_name VARCHAR(255),
    problem VARCHAR(200),
    evidence VARCHAR(500),
    est_saving_mb DECIMAL(10,1),
    risk VARCHAR(10),
    effort VARCHAR(10),
    recommended_action VARCHAR(500)
);

-- ============================================================
-- PHASE 1: INVENTORY
-- ============================================================
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P1-Inventory', 0, 'Database Size', table_schema,
    'Baseline size',
    CONCAT(COUNT(*), ' tables, ', ROUND(SUM(data_length)/1024/1024,1), ' MB data, ', ROUND(SUM(index_length)/1024/1024,1), ' MB index'),
    0.0, 'None', 'None', 'Baseline measurement'
FROM information_schema.tables 
WHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
GROUP BY table_schema;

-- ============================================================
-- PHASE 2: PHYSICAL ANALYSIS
-- ============================================================

-- 2a: InnoDB Fragmentation
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P2-Physical',
    CASE WHEN data_free/1024/1024 > 500 THEN 1 WHEN data_free/1024/1024 > 100 THEN 2 ELSE 3 END,
    'Fragmentation',
    CONCAT(table_schema, '.', table_name),
    'InnoDB free space (DATA_FREE)',
    CONCAT('data=', ROUND(data_length/1024/1024,1), ' MB, free=', ROUND(data_free/1024/1024,1), ' MB (', ROUND(data_free/GREATEST(data_length,1)*100), '%)'),
    ROUND(data_free/1024/1024,1),
    'None', 'Low', 'OPTIMIZE TABLE to reclaim fragmented space'
FROM information_schema.tables 
WHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
AND engine = 'InnoDB' AND data_free > 10*1024*1024
ORDER BY data_free DESC LIMIT 30;

-- 2b: Large Object Distribution
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P2-Physical', 3, 'Large Objects',
    CONCAT(c.table_schema, '.', c.table_name, '.', c.column_name),
    CONCAT('Column type: ', c.data_type),
    CONCAT('TEXT-type in table with ~', t.table_rows, ' rows'),
    0.0, 'Varies', 'Medium',
    'Audit for compression or content-addressable storage'
FROM information_schema.columns c
JOIN information_schema.tables t ON c.table_schema = t.table_schema AND c.table_name = t.table_name
WHERE c.data_type IN ('longtext','mediumtext','text','longblob','mediumblob','blob')
AND c.table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
AND t.table_rows > 1000
ORDER BY t.table_rows DESC LIMIT 50;

-- 2c: Oversized VARCHAR
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P2-Physical', 5, 'Data Types',
    CONCAT(c.table_schema, '.', c.table_name, '.', c.column_name),
    CONCAT('Oversized: ', c.data_type, '(', c.character_maximum_length, ')'),
    CONCAT('~', t.table_rows, ' rows'),
    0.0, 'Low', 'Medium',
    'Review if smaller type suffices'
FROM information_schema.columns c
JOIN information_schema.tables t ON c.table_schema = t.table_schema AND c.table_name = t.table_name
WHERE c.data_type = 'varchar' AND c.character_maximum_length > 1000
AND c.table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
AND t.table_rows > 10000
ORDER BY c.character_maximum_length DESC LIMIT 30;

-- 2d: Index Bloat
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P2-Physical',
    CASE WHEN index_length/1024/1024 > 100 THEN 2 WHEN index_length/1024/1024 > 20 THEN 3 ELSE 4 END,
    'Index Bloat',
    CONCAT(table_schema, '.', table_name),
    'Index exceeds 20% of data',
    CONCAT('data=', ROUND(data_length/1024/1024,1), ' MB, idx=', ROUND(index_length/1024/1024,1), ' MB (', ROUND(index_length/GREATEST(data_length,1)*100), '%)'),
    ROUND(index_length/1024/1024 * 0.3, 1),
    'Low', 'Medium',
    'Audit for duplicate/overlapping/unused indexes'
FROM information_schema.tables 
WHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
AND data_length > 0 AND index_length / data_length > 0.2
ORDER BY index_length DESC LIMIT 20;

-- ============================================================
-- PHASE 3: LOGICAL ANALYSIS
-- ============================================================

-- 3a: Empty Tables
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P3-Logical', 4, 'Empty Tables',
    CONCAT(table_schema, '.', table_name),
    'Zero rows',
    CONCAT('0 rows, ', ROUND(data_length/1024/1024,2), ' MB allocated'),
    ROUND((data_length + index_length)/1024/1024, 2),
    'Low', 'Low', 'DROP TABLE if confirmed unused'
FROM information_schema.tables 
WHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
AND table_rows = 0
ORDER BY (data_length + index_length) DESC;

-- 3b: Tiny Databases
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P3-Logical', 6, 'Tiny Databases', table_schema,
    'Database under 1 MB',
    CONCAT(ROUND(SUM(data_length+index_length)/1024/1024,2), ' MB, ', COUNT(*), ' tables'),
    ROUND(SUM(data_length+index_length)/1024/1024, 2),
    'Low', 'Low', 'Consolidate into vb_shared or drop if unused'
FROM information_schema.tables 
WHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
GROUP BY table_schema
HAVING SUM(data_length+index_length)/1024/1024 < 1.0;

-- 3c: Duplicate Table Names Across Databases
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P3-Logical', 1, 'Duplicate Databases',
    CONCAT(table_name, ' in ', GROUP_CONCAT(table_schema ORDER BY table_schema SEPARATOR ', ')),
    'Same table name in multiple databases',
    CONCAT('Found in ', COUNT(*), ' databases'),
    0.0, 'Medium', 'Medium',
    'Compare schemas and row counts. Merge into one canonical database.'
FROM information_schema.tables
WHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
GROUP BY table_name
HAVING COUNT(*) > 1 AND SUM(table_rows) > 0
ORDER BY COUNT(*) DESC LIMIT 20;

-- 3d: Repeated String Columns (normalization candidates)
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P3-Logical', 5, 'Normalization', column_name,
    'Repeated string column across tables',
    CONCAT('Appears in ', COUNT(*), ' tables'),
    0.0, 'Medium', 'High',
    'Create lookup table with integer FK'
FROM information_schema.columns
WHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
AND data_type = 'varchar' AND character_maximum_length <= 100
AND column_name NOT LIKE '%_id' AND column_name NOT LIKE '%_hash'
AND column_name NOT LIKE '%_path' AND column_name NOT LIKE '%_name'
GROUP BY column_name
HAVING COUNT(*) > 3
ORDER BY COUNT(*) DESC LIMIT 20;

-- ============================================================
-- PHASE 4: OPTIMIZATION OPPORTUNITIES
-- ============================================================

-- 4a: Compression candidates (high avg row size)
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P4-Opportunity',
    CASE WHEN data_length/GREATEST(table_rows,1) > 30000 THEN 2 WHEN data_length/GREATEST(table_rows,1) > 10000 THEN 3 ELSE 4 END,
    'Compression',
    CONCAT(table_schema, '.', table_name),
    'High average row size — text-heavy',
    CONCAT(table_rows, ' rows, ', ROUND(data_length/1024/1024,1), ' MB, avg ', ROUND(data_length/GREATEST(table_rows,1)), ' B/row'),
    CASE WHEN data_length/GREATEST(table_rows,1) > 30000 THEN ROUND(data_length/1024/1024 * 0.6, 1)
         WHEN data_length/GREATEST(table_rows,1) > 10000 THEN ROUND(data_length/1024/1024 * 0.4, 1)
         ELSE ROUND(data_length/1024/1024 * 0.2, 1) END,
    'Low', 'Medium',
    'Enable ROW_FORMAT=COMPRESSED or compress at application layer'
FROM information_schema.tables 
WHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
AND table_rows > 1000 AND data_length/GREATEST(table_rows,1) > 5000
ORDER BY data_length DESC LIMIT 30;

-- 4b: Archive candidates (timestamp columns + large tables)
INSERT INTO opt_findings (phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action)
SELECT 
    'P4-Opportunity', 3, 'Archive',
    CONCAT(table_schema, '.', table_name),
    'Table has timestamp column — archive candidate',
    CONCAT('~', table_rows, ' rows, ', ROUND(data_length/1024/1024,1), ' MB'),
    ROUND(data_length/1024/1024 * 0.5, 1),
    'Low', 'Medium',
    'Partition by date. Move old partitions to archive.'
FROM information_schema.tables t
WHERE t.table_schema NOT IN ('information_schema','mysql','performance_schema','sys')
AND t.table_rows > 10000 AND t.data_length/1024/1024 > 10
AND EXISTS (
    SELECT 1 FROM information_schema.columns c 
    WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name 
    AND c.column_name IN ('created_at','timestamp','date','created','updated_at')
)
ORDER BY t.data_length DESC LIMIT 20;

-- ============================================================
-- PHASE 5: SAVINGS ROLLUP (computed in final output instead)
-- ============================================================
-- Skipped inline rollup — MySQL cannot INSERT INTO temp table
-- while SELECTing from it simultaneously. Rollup is computed
-- in the Phase 6 output queries instead.

-- ============================================================
-- PHASE 6: PRIORITIZED ROADMAP — Final Output
-- ============================================================

-- Savings rollup by category
SELECT '=== SAVINGS BY CATEGORY ===' AS section, '' AS category, '' AS findings, '' AS total_mb, '' AS action;
SELECT 
    category,
    COUNT(*) AS findings,
    CONCAT(ROUND(SUM(est_saving_mb),1), ' MB') AS total_saving,
    CONCAT('Total from ', category, ': ', ROUND(SUM(est_saving_mb),1), ' MB') AS action
FROM opt_findings
WHERE est_saving_mb > 0
GROUP BY category
ORDER BY SUM(est_saving_mb) DESC;

-- Full detailed report
SELECT phase, priority, category, object_name, problem, evidence, est_saving_mb, risk, effort, recommended_action
FROM opt_findings
ORDER BY 
    CASE WHEN phase = 'P1-Inventory' THEN 0 WHEN phase = 'P2-Physical' THEN 1
         WHEN phase = 'P3-Logical' THEN 2 WHEN phase = 'P4-Opportunity' THEN 3 END,
    priority ASC, est_saving_mb DESC;

-- Prioritized roadmap (actionable only)
SELECT '=== PRIORITIZED ROADMAP ===' AS section, '' AS `rank`, '' AS optimization, '' AS object, '' AS saving, '' AS risk, '' AS effort, '' AS action;

SELECT 
    ROW_NUMBER() OVER (ORDER BY est_saving_mb DESC) AS `rank`,
    category AS optimization, object_name,
    CONCAT(est_saving_mb, ' MB') AS estimated_saving,
    risk, effort, recommended_action
FROM opt_findings
WHERE est_saving_mb > 0 AND phase IN ('P2-Physical','P3-Logical','P4-Opportunity')
ORDER BY est_saving_mb DESC LIMIT 30;

-- Grand total
SELECT '=== GRAND TOTAL ===' AS section, '' AS `rank`, '' AS optimization, '' AS object,
    CONCAT(ROUND(SUM(est_saving_mb)/1024, 2), ' GB potential savings') AS saving,
    '' AS risk, '' AS effort, '' AS action
FROM opt_findings WHERE est_saving_mb > 0 AND phase IN ('P2-Physical','P3-Logical','P4-Opportunity');

-- Current size
SELECT '=== CURRENT SIZE ===' AS section, '' AS `rank`, '' AS optimization,
    CONCAT(COUNT(*), ' tables, ', COUNT(DISTINCT table_schema), ' databases') AS object,
    CONCAT(ROUND(SUM(data_length+index_length)/1024/1024/1024, 2), ' GB') AS saving,
    '' AS risk, '' AS effort, '' AS action
FROM information_schema.tables 
WHERE table_schema NOT IN ('information_schema','mysql','performance_schema','sys');

DROP TEMPORARY TABLE IF EXISTS opt_findings;
