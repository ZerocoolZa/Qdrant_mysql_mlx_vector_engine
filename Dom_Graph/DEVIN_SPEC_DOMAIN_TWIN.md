<!-- [@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Devin implementation spec for Project Digital Twin domain codebase refactoring engine. Describes 5-table SQLite architecture for ingesting Python domain, storing files/classes/methods, building relationship graphs, tracking errors/fixes. Comprehensive spec with SQL DDL. No VBStyle violations applicable to markdown.>][@todos<none>]} -->
# Devin Implementation Spec — Project Digital Twin
# Domain Codebase Refactoring Engine

## GOAL
Build a SQLite-based system that ingests an entire Python domain (e.g. Dom_Graph), stores every file/class/method as rows, builds relationship graphs, tracks errors/fixes as Q&A knowledge, and enables safe automated refactoring — all from SQL queries over 5 core tables.

## TARGET DIRECTORY
`/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/`

## EXISTING ASSETS
- `dom_graph_work.db` — already has `src(file, lineno, text)` and `config_constants`, `class_registry`, `method_registry` tables
- `Config.py` — has SCHEMA_SQL, GRAPH_SCHEMA, FILE_REGISTRY, GRAPH_PIPELINE, PRIMITIVES
- `ingest_to_db.py` — ingests files line-by-line into `src` table
- `build_registry.py` — extracts classes/methods into registry tables
- `domain_loader.py` — loads classes from DB, instantiates them
- `test_everything.py` — 205 tests, all passing
- `VBSTYLE_LESSONS.md` — lessons learned from 5 iterations of cleanup

## CORE ARCHITECTURE: 5 TABLES + 3 AUXILIARY

### TABLE 1: files
```sql
CREATE TABLE files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    path TEXT NOT NULL,
    extension TEXT,
    hash TEXT,
    bcl TEXT,
    size INTEGER,
    imports TEXT,          -- JSON array of imported modules
    exports TEXT,          -- JSON array of exported names
    class_count INTEGER DEFAULT 0,
    function_count INTEGER DEFAULT 0,
    method_count INTEGER DEFAULT 0,
    dependencies TEXT,     -- JSON array of file dependencies
    created TEXT,
    modified TEXT,
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',  -- active, deprecated, deleted
    encoding TEXT DEFAULT 'utf-8',
    language TEXT DEFAULT 'python'
);
```

### TABLE 2: classes
```sql
CREATE TABLE classes (
    class_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(file_id),
    class_name TEXT NOT NULL,
    parent TEXT,           -- parent class name if any
    interfaces TEXT,       -- JSON array
    bcl TEXT,
    start_line INTEGER,
    end_line INTEGER,
    method_count INTEGER DEFAULT 0,
    properties TEXT,       -- JSON array of property names
    fields TEXT,           -- JSON array of field names
    dependencies TEXT,     -- JSON array of class names this depends on
    relationships TEXT,    -- JSON array of {type, target}
    is_vbstyle INTEGER DEFAULT 0,
    has_run_method INTEGER DEFAULT 0,
    has_tuple3 INTEGER DEFAULT 0,
    cyclomatic_complexity REAL DEFAULT 0,
    hash TEXT,
    version INTEGER DEFAULT 1
);
```

### TABLE 3: methods
```sql
CREATE TABLE methods (
    method_id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL REFERENCES classes(class_id),
    file_id INTEGER NOT NULL REFERENCES files(file_id),
    method_name TEXT NOT NULL,
    bcl TEXT,
    signature TEXT,
    parameters TEXT,       -- JSON array of param names
    return_type TEXT,
    visibility TEXT DEFAULT 'public',  -- public, private, protected
    start_line INTEGER,
    end_line INTEGER,
    method_code TEXT,      -- FULL method source code as one string
    cyclomatic_complexity REAL DEFAULT 0,
    dependencies TEXT,     -- JSON array of method names this calls
    calls TEXT,            -- JSON array of outgoing call targets
    called_by TEXT,        -- JSON array of incoming callers
    is_dunder INTEGER DEFAULT 0,
    is_vbstyle INTEGER DEFAULT 0,
    returns_tuple3 INTEGER DEFAULT 0,
    has_print INTEGER DEFAULT 0,
    has_decorator INTEGER DEFAULT 0,
    has_self_underscore INTEGER DEFAULT 0,
    line_count INTEGER DEFAULT 0,
    hash TEXT,
    version INTEGER DEFAULT 1
);
```

### TABLE 4: edges
```sql
CREATE TABLE edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_type TEXT NOT NULL,   -- 'file', 'class', 'method'
    src_id INTEGER NOT NULL,
    dst_type TEXT NOT NULL,   -- 'file', 'class', 'method'
    dst_id INTEGER NOT NULL,
    edge_type TEXT NOT NULL,  -- 'imports', 'inherits', 'calls', 'uses', 'depends_on', 'overrides'
    evidence TEXT,            -- why this edge exists (line number, AST node)
    confidence REAL DEFAULT 100.0,
    created TEXT
);
CREATE INDEX idx_edges_src ON edges(src_type, src_id);
CREATE INDEX idx_edges_dst ON edges(dst_type, dst_id);
CREATE INDEX idx_edges_type ON edges(edge_type);
```

### TABLE 5: knowledge (Q&A engine)
```sql
CREATE TABLE knowledge (
    knowledge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem TEXT NOT NULL,     -- what went wrong
    question TEXT NOT NULL,    -- what we need to know
    answer TEXT NOT NULL,      -- a possible solution
    is_best INTEGER DEFAULT 0, -- 1 if this is the best answer
    evidence TEXT,             -- proof it worked (compile result, test result)
    confidence INTEGER DEFAULT 0,  -- 0-100
    file_id INTEGER REFERENCES files(file_id),
    class_id INTEGER REFERENCES classes(class_id),
    method_id INTEGER REFERENCES methods(method_id),
    error_type TEXT,           -- SyntaxError, ImportError, etc.
    error_text TEXT,
    stack_trace TEXT,
    fix_applied TEXT,
    fix_result TEXT,           -- 'success', 'failure', 'partial'
    resolution_time_ms INTEGER,
    created TEXT,
    tags TEXT                  -- JSON array for categorization
);
CREATE INDEX idx_knowledge_problem ON knowledge(problem);
CREATE INDEX idx_knowledge_error_type ON knowledge(error_type);
```

### AUXILIARY TABLE 1: snapshots
```sql
CREATE TABLE snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_type TEXT NOT NULL,  -- 'before_fix', 'after_fix', 'manual'
    file_id INTEGER REFERENCES files(file_id),
    class_id INTEGER REFERENCES classes(class_id),
    method_id INTEGER REFERENCES methods(method_id),
    content TEXT NOT NULL,        -- full content at snapshot time
    hash TEXT NOT NULL,
    created TEXT NOT NULL,
    notes TEXT
);
```

### AUXILIARY TABLE 2: attempts
```sql
CREATE TABLE attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    method_id INTEGER REFERENCES methods(method_id),
    action TEXT NOT NULL,        -- 'remove_print', 'add_run', 'rename_class', etc.
    before_code TEXT,
    after_code TEXT,
    compile_result INTEGER,      -- 1=pass, 0=fail
    test_result INTEGER,         -- 1=pass, 0=fail
    error_text TEXT,
    rollback INTEGER DEFAULT 0,  -- 1 if rolled back
    knowledge_id INTEGER REFERENCES knowledge(knowledge_id),
    created TEXT
);
```

### AUXILIARY TABLE 3: observations
```sql
CREATE TABLE observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_type TEXT NOT NULL,  -- 'fact', 'assumption', 'unknown', 'confirmed', 'ignored'
    subject TEXT NOT NULL,           -- what we observed
    evidence TEXT,                   -- how we know
    confidence REAL DEFAULT 0,
    file_id INTEGER REFERENCES files(file_id),
    class_id INTEGER REFERENCES classes(class_id),
    method_id INTEGER REFERENCES methods(method_id),
    created TEXT
);
```

---

## SECTION-BY-SECTION IMPLEMENTATION SPEC

### SECTION 1: BACKUP PHASE
**Tables used:** snapshots (auxiliary)
**Implementation:**
- 1.1 Create Primary Backup: `shutil.copy2(db_path, db_path + '.bak')`
- 1.2 Verify Backup Integrity: `PRAGMA integrity_check` on backup
- 1.3 Create Secondary Backup: copy to different directory
- 1.4 Store Secondary Backup Offline: copy to `~/backups/` or external
- 1.5 Hash Both Backups: `hashlib.sha256(file_bytes).hexdigest()`, compare
- 1.6 Record Backup Metadata: INSERT into snapshots table
- 1.7 Make Backups Read-Only: `os.chmod(backup_path, 0o444)`
- 1.8 Create Restore Test: copy backup to temp, open, verify tables
- 1.9 Log Backup Session: INSERT observation 'backup_created'
- 1.10 Never Modify Original Database: enforce via wrapper that checks `db_path != original_db_path`
**Devin task:** Write `backup_engine.py` with class `BackupEngine` that has `Run(command, params)` dispatch. Commands: `create_backup`, `verify_backup`, `restore_backup`, `list_backups`.

### SECTION 2: SANDBOX PHASE (IN-RAM SQLITE)
**Tables used:** all (loaded into RAM copy)
**Implementation:**
- 2.1 Load Backup into RAM SQLite: `sqlite3.connect(':memory:')`, read from backup file, execute script
- 2.2 Verify Schema: `SELECT name FROM sqlite_master WHERE type='table'` — compare to expected list
- 2.3 Verify Table Counts: `SELECT COUNT(*) FROM <table>` for each — compare to original
- 2.4 Verify Foreign Keys: `PRAGMA foreign_key_check`
- 2.5 Verify Indexes: `SELECT name FROM sqlite_master WHERE type='index'`
- 2.6 Verify Constraints: `PRAGMA check_foreign_keys`
- 2.7 Enable Rollback: `BEGIN TRANSACTION` before every experiment
- 2.8 Snapshot Before Every Experiment: `INSERT INTO snapshots ...`
- 2.9 Auto Restore After Failure: `ROLLBACK` on exception, `COMMIT` only on success
- 2.10 Never Touch Original Database: sandbox only operates on `:memory:` copy
**Devin task:** Write `sandbox_engine.py` with class `SandboxEngine`. Commands: `load`, `verify`, `begin_experiment`, `commit`, `rollback`, `get_state`.

### SECTION 3: ERROR KNOWLEDGE DATABASE
**Tables used:** knowledge, attempts
**Implementation:**
- 3.1-3.4 Create tables: knowledge + attempts (schema above)
- 3.5 Store Stack Trace: `traceback.format_exc()` → knowledge.stack_trace
- 3.6 Store Exception Type: `type(e).__name__` → knowledge.error_type
- 3.7-3.9 Store File/Class/Method: link via file_id, class_id, method_id
- 3.10 Store Line Number: parse from traceback
- 3.11 Store Variables: `locals()` snapshot as JSON → knowledge.evidence
- 3.12-3.13 Store Inputs/Outputs: function args and return value
- 3.14 Store Root Cause: analysis of stack trace → knowledge.problem
- 3.15-3.16 Store Human/AI Fix: the fix text → knowledge.answer
- 3.17 Store Confidence: 0-100 based on similarity to past successes
- 3.18 Store Similar Errors: `SELECT * FROM knowledge WHERE error_type=? AND problem LIKE ?`
- 3.19 Store Resolution Time: `time.time() - start_time`
- 3.20 Learn From Previous Fixes: query knowledge table before attempting fix
**Devin task:** Write `knowledge_engine.py` with class `KnowledgeEngine`. Commands: `record_error`, `record_fix`, `search_similar`, `learn`, `get_best_fix`.

### SECTION 4: GRAPH ORIGINAL CODEBASE
**Tables used:** files, classes, methods, edges
**Implementation:**
- 4.1 Parse Entire Project: `ast.parse(file_content)` for each .py file
- 4.2 Build File Graph: edges where src_type='file', dst_type='file', edge_type='imports'
- 4.3 Build Folder Graph: group files by directory, edges for parent-child
- 4.4 Build Import Graph: parse `import X` and `from X import Y` statements
- 4.5 Build Dependency Graph: edges where edge_type='depends_on'
- 4.6 Build Class Graph: edges where src_type='class', dst_type='class'
- 4.7 Build Method Graph: edges where src_type='method', dst_type='method'
- 4.8 Build Function Graph: standalone functions (not in classes)
- 4.9 Build Call Graph: parse `self.method()` and `Class.method()` calls → edges edge_type='calls'
- 4.10 Build Variable Graph: parse assignments, track variable scope
- 4.11 Build Object Graph: track object instantiation `X()` in method code
- 4.12 Build Event Graph: track event handlers, callbacks, signals
- 4.13 Build Runtime Flow: order methods by call sequence
- 4.14 Build Execution Flow: trace from entry point through call graph
- 4.15 Build Database Flow: find SQL queries in method_code
- 4.16 Build GUI Flow: find Tkinter/Qt calls in method_code
- 4.17 Build Thread Graph: find threading.Thread, asyncio usage
- 4.18 Build Memory Graph: find malloc, alloc, large data structures
- 4.19 Detect Cycles: DFS over edges, report back edges → observations
- 4.20 Detect Dead Code: methods with no incoming edges (called_by is empty)
- 4.21 Detect Duplicate Code: hash method_code, find matching hashes
- 4.22 Detect Orphans: classes with no edges, files with no imports/exports
- 4.23 Detect Hotspots: methods with high cyclomatic_complexity + high incoming edges
- 4.24 Store Entire Graph: all edges INSERTed into edges table
**Devin task:** Write `graph_builder.py` with class `GraphBuilder`. Commands: `build_all`, `build_file_graph`, `build_class_graph`, `build_method_graph`, `build_call_graph`, `detect_cycles`, `detect_dead_code`, `detect_duplicates`, `detect_orphans`, `detect_hotspots`.

### SECTION 5: INGESTION
**Tables used:** files
**Implementation:**
- 5.1 Scan Files: `pathlib.Path(dir).rglob('*.py')`
- 5.2 Compute File Hash: `hashlib.sha256(content.encode()).hexdigest()`
- 5.3 Compute BCL Hash: extract BCL header, hash separately
- 5.4 Detect Duplicates: `SELECT file_id FROM files WHERE hash=?`
- 5.5 Detect Version: compare hash to previous, increment version if changed
- 5.6 Detect Language: by extension (.py=python, .c=C, .swift=Swift)
- 5.7 Detect Encoding: `chardet.detect(content)`
- 5.8 Detect Dependencies: parse import statements
- 5.9 Record Metadata: INSERT into files table
- 5.10 Store Raw Source: store in files table or separate file_content table
**Devin task:** Write `ingestion_engine.py` with class `IngestionEngine`. Commands: `scan`, `ingest_file`, `ingest_directory`, `detect_duplicates`, `update_changed`.

### SECTION 6: TABLE 1 (FILES)
**Already specified above.** This is the `files` table schema.
**Devin task:** Add this table to Config.py SCHEMA_SQL, create in DB.

### SECTION 7: TABLE 2 (CLASS SPLIT)
**Already specified above.** This is the `classes` table schema.
**Devin task:** Add this table to Config.py SCHEMA_SQL. Populate by AST-parsing each file, extracting class definitions with start_line, end_line, parent, methods list.

### SECTION 8: TABLE 3 (METHOD SPLIT)
**Already specified above.** This is the `methods` table schema.
**Devin task:** Add this table to Config.py SCHEMA_SQL. Populate by AST-parsing each class, extracting method definitions with full source code as `method_code` text field.

### SECTION 9: BCL NORMALIZATION
**Tables used:** files, classes, methods (bcl column)
**Implementation:**
- 9.1-9.4 Every file/class/method/function has BCL: check `bcl IS NOT NULL AND bcl != ''`
- 9.5 Stored As Pure Text: BCL stored as-is, no JSON conversion
- 9.6-9.8 Never Reformatted/Wrapped/Tokenized: original BCL block preserved
- 9.9 Original Block Preserved: store the full `[@BCL]{...}` block
- 9.10 Hash Protected: `hashlib.sha256(bcl_text.encode()).hexdigest()` stored in hash column
**Devin task:** Write `bcl_engine.py` with class `BclEngine`. Commands: `extract_bcl`, `verify_bcl`, `compare_bcl`, `hash_bcl`, `report_missing`.

### SECTION 10: STATIC ANALYSIS
**Tables used:** classes, methods, edges
**Implementation:**
- 10.1 AST Parse: `ast.parse(file_content)` — store AST node types
- 10.2 Symbol Table: extract all names, scopes
- 10.3 Import Resolution: resolve `from X import Y` to actual file paths
- 10.4 Type Analysis: infer types from assignments and returns
- 10.5 Scope Analysis: track local/global/nonlocal
- 10.6 Constant Detection: find `UPPER_CASE = value` at module level
- 10.7 Global Detection: find `global X` statements
- 10.8 Dead Code Detection: methods with no incoming edges
- 10.9 Duplicate Detection: methods with same hash or similar AST
- 10.10 Complexity Analysis: `cyclomatic_complexity` = count of if/for/while/except/and/or/with
**Devin task:** Write `static_analyzer.py` with class `StaticAnalyzer`. Commands: `analyze_file`, `analyze_all`, `get_complexity`, `find_dead_code`, `find_duplicates`.

### SECTION 11: RELATIONSHIP EXTRACTION
**Tables used:** edges
**Implementation:**
- 11.1 File→File: parse import statements, resolve to file paths
- 11.2 File→Class: file_id → class_id (already in classes table)
- 11.3 Class→Class: parse inheritance, composition
- 11.4 Class→Method: class_id → method_id (already in methods table)
- 11.5 Method→Method: parse `self.X()` calls → edges edge_type='calls'
- 11.6 Method→Variable: parse variable reads/writes in method_code
- 11.7 Method→Database: find `cursor.execute`, `conn.execute` in method_code
- 11.8 Method→GUI: find Tkinter/Qt calls in method_code
- 11.9 Method→API: find `requests.get/post`, `urllib` calls
- 11.10 Method→Thread: find `threading.Thread`, `asyncio` usage
**Devin task:** Write `relationship_extractor.py` with class `RelationshipExtractor`. Commands: `extract_all`, `extract_file_edges`, `extract_class_edges`, `extract_method_edges`.

### SECTION 12: FIX ENGINE
**Tables used:** knowledge, attempts, methods, snapshots
**Implementation:**
- 12.1 Find Error: compile error or test failure
- 12.2 Search Similar Errors: `SELECT * FROM knowledge WHERE error_type=? AND problem LIKE ? ORDER BY confidence DESC`
- 12.3 Rank Previous Fixes: order by confidence, success rate
- 12.4 Apply Candidate: update method_code in methods table
- 12.5 Compile: `py_compile.compile(temp_file, doraise=True)`
- 12.6 Run Tests: execute test_everything.py, parse results
- 12.7 Compare Output: diff test results before/after
- 12.8 Rollback If Failed: restore from snapshot, `ROLLBACK TRANSACTION`
- 12.9 Record Outcome: INSERT into attempts table
- 12.10 Learn Result: UPDATE knowledge SET confidence=confidence+5 WHERE answer matched
**Devin task:** Write `fix_engine.py` with class `FixEngine`. Commands: `find_error`, `search_fixes`, `apply_fix`, `compile_check`, `run_tests`, `rollback`, `record_outcome`, `learn`.

### SECTION 13: VALIDATION
**Tables used:** all
**Implementation:**
- 13.1 Syntax: `py_compile.compile(file, doraise=True)`
- 13.2 Imports: try `import <module>` for each file
- 13.3 References: check all names resolve (no NameError)
- 13.4 Runtime: instantiate class, call Run()
- 13.5 Unit Tests: run test_everything.py
- 13.6 Integration Tests: run domain_loader.py
- 13.7 Memory: `tracemalloc` snapshot before/after
- 13.8 Database: `PRAGMA integrity_check`
- 13.9 Performance: `time.time()` around key operations
- 13.10 Regression: compare test results to previous run
**Devin task:** Write `validation_engine.py` with class `ValidationEngine`. Commands: `validate_syntax`, `validate_imports`, `validate_references`, `validate_runtime`, `validate_tests`, `validate_all`.

### SECTION 14: KNOWLEDGE STORAGE
**Tables used:** knowledge, observations, snapshots
**Implementation:**
- 14.1 Store Error: INSERT into knowledge (problem, error_type, error_text, stack_trace)
- 14.2 Store Fix: INSERT into knowledge (answer, is_best=1 if worked)
- 14.3 Store Patch: store diff in attempts.after_code
- 14.4 Store Explanation: natural language description in knowledge.evidence
- 14.5 Store Graph Changes: diff edges table before/after
- 14.6 Store Before/After: snapshots table
- 14.7 Store Confidence: 0-100 in knowledge.confidence
- 14.8 Store Evidence: compile result, test result in knowledge.evidence
- 14.9 Store Learning: UPDATE knowledge SET confidence based on success/failure
- 14.10 Update Search Index: create FTS5 virtual table on knowledge
```sql
CREATE VIRTUAL TABLE knowledge_fts USING fts5(problem, question, answer, error_type, content='knowledge', content_rowid='knowledge_id');
```
**Devin task:** Extend `knowledge_engine.py` with these commands.

### SECTION 15: REPORTING
**Tables used:** all (read-only queries)
**Implementation:**
- 15.1 Error Timeline: `SELECT created, problem, error_type FROM knowledge ORDER BY created`
- 15.2 Fix Timeline: `SELECT created, answer, fix_result FROM knowledge WHERE answer IS NOT NULL ORDER BY created`
- 15.3 Dependency Report: `SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type`
- 15.4 Duplicate Report: `SELECT method_name, COUNT(*) FROM methods GROUP BY hash HAVING COUNT(*)>1`
- 15.5 Complexity Report: `SELECT method_name, cyclomatic_complexity FROM methods ORDER BY cyclomatic_complexity DESC LIMIT 20`
- 15.6 BCL Coverage: `SELECT SUM(bcl IS NOT NULL)/COUNT(*) * 100 FROM methods`
- 15.7 Graph Coverage: `SELECT COUNT(DISTINCT src_id)+COUNT(DISTINCT dst_id) FROM edges` / total entities
- 15.8 Method Coverage: methods with has_run_method=1 / total methods
- 15.9 Test Coverage: passed tests / total tests
- 15.10 Health Score: weighted average of all above
**Devin task:** Write `report_engine.py` with class `ReportEngine`. Commands: `error_timeline`, `fix_timeline`, `dependency_report`, `duplicate_report`, `complexity_report`, `bcl_coverage`, `health_score`, `full_report`.

### SECTION 16: CONTINUOUS LOOP
**Implementation:** This is the orchestrator that calls all engines in sequence.
```python
# Pseudocode for Run("continuous_loop"):
while True:
    scan()          # 16.1
    ingest()        # 16.2
    index()         # 16.3
    graph()         # 16.4
    detect()        # 16.5 — find violations
    search()        # 16.6 — search knowledge for fixes
    repair()        # 16.7 — apply fixes
    validate()      # 16.8 — compile + test
    learn()         # 16.9 — record outcomes
    # 16.10 repeat
    if no_violations and all_tests_pass:
        break
```
**Devin task:** Write `continuous_loop.py` with class `ContinuousLoop`. Commands: `run_full_cycle`, `run_n_cycles`, `detect_and_fix`, `run_until_clean`.

### SECTION 17: PROJECT FINGERPRINTING
**Tables used:** files, classes, methods
**Implementation:**
- 17.1 Project Hash: hash of all file hashes concatenated
- 17.2 File Hashes: already in files.hash
- 17.3 Class Hashes: already in classes.hash
- 17.4 Method Hashes: already in methods.hash
- 17.5 BCL Hashes: hash of bcl column
- 17.6 Dependency Hashes: hash of edges table content
- 17.7 Graph Hash: hash of all edges
- 17.8 Snapshot ID: link to snapshots table
- 17.9 Change Signature: diff of hashes between snapshots
- 17.10 Integrity Verification: compare current hashes to stored
**Devin task:** Write `fingerprint_engine.py` with class `FingerprintEngine`. Commands: `fingerprint_project`, `fingerprint_file`, `fingerprint_class`, `fingerprint_method`, `compare_fingerprints`, `verify_integrity`.

### SECTION 18: VERSION SNAPSHOTS
**Tables used:** snapshots
**Implementation:**
- 18.1 Snapshot Before Fix: INSERT into snapshots with type='before_fix'
- 18.2 Snapshot After Fix: INSERT into snapshots with type='after_fix'
- 18.3 Automatic Restore Point: snapshot before every method update
- 18.4 Branch Experiments: create copy of DB, experiment, compare
- 18.5 Compare Snapshots: `SELECT content FROM snapshots WHERE method_id=? ORDER BY created`
- 18.6 Restore Snapshot: `UPDATE methods SET method_code=? WHERE method_id=?`
- 18.7 Snapshot Notes: notes column
- 18.8 Snapshot Timeline: `SELECT * FROM snapshots ORDER BY created`
**Devin task:** Write `snapshot_engine.py` with class `SnapshotEngine`. Commands: `create_snapshot`, `restore_snapshot`, `compare_snapshots`, `list_snapshots`, `timeline`.

### SECTION 19: CODE DIFFERENCE ENGINE
**Tables used:** files, classes, methods, snapshots
**Implementation:**
- 19.1 File Diff: `difflib.unified_diff(before, after)`
- 19.2 Class Diff: compare class rows before/after
- 19.3 Method Diff: compare method_code before/after
- 19.4 AST Diff: parse both versions, compare AST trees
- 19.5 Graph Diff: compare edges table before/after
- 19.6 Dependency Diff: compare edges where edge_type='depends_on'
- 19.7 BCL Diff: compare bcl column before/after
- 19.8 Database Diff: compare schema, row counts
- 19.9 Runtime Diff: compare test results before/after
**Devin task:** Write `diff_engine.py` with class `DiffEngine`. Commands: `diff_file`, `diff_class`, `diff_method`, `diff_ast`, `diff_graph`, `diff_all`.

### SECTION 20: SEMANTIC SEARCH
**Tables used:** files, classes, methods, knowledge (FTS5)
**Implementation:**
- 20.1 Search by Name: `SELECT * FROM methods WHERE method_name LIKE ?`
- 20.2 Search by BCL: `SELECT * FROM methods WHERE bcl LIKE ?`
- 20.3 Search by Signature: `SELECT * FROM methods WHERE signature LIKE ?`
- 20.4 Search by Error: `SELECT * FROM knowledge WHERE problem LIKE ?`
- 20.5 Search by Fix: `SELECT * FROM knowledge WHERE answer LIKE ?`
- 20.6 Search by Dependency: `SELECT * FROM edges WHERE edge_type=? AND (src_id=? OR dst_id=?)`
- 20.7 Search by Call Chain: recursive CTE over edges where edge_type='calls'
- 20.8 Search by Variable: parse method_code for variable names
- 20.9 Search by Comment: `SELECT * FROM methods WHERE method_code LIKE '%#%?%'`
- 20.10 Search by Behavior: FTS5 full-text search on method_code
**Devin task:** Write `search_engine.py` with class `SearchEngine`. Commands: `search_name`, `search_bcl`, `search_signature`, `search_error`, `search_fix`, `search_dependency`, `search_call_chain`, `search_variable`, `search_comment`, `search_behavior`, `search_all`.

### SECTION 21: EXECUTION TRACING
**Tables used:** methods, edges
**Implementation:**
- 21.1 Entry Point: find methods called by `if __name__ == '__main__'`
- 21.2 Call Order: BFS/DFS over edges where edge_type='calls'
- 21.3 Stack Trace: `traceback.format_stack()` at each method entry
- 21.4 Memory Usage: `tracemalloc.get_traced_memory()` before/after
- 21.5 Object Lifetime: track `__init__` to `__del__` calls
- 21.6 SQL Calls: find `execute`, `executemany`, `commit` in method_code
- 21.7 API Calls: find `requests`, `urllib` in method_code
- 21.8 File IO: find `open()`, `read()`, `write()` in method_code
- 21.9 Thread Activity: find `Thread`, `Lock`, `Queue` in method_code
- 21.10 Exit Path: find `return`, `raise`, `sys.exit` in method_code
**Devin task:** Write `trace_engine.py` with class `TraceEngine`. Commands: `find_entry_points`, `trace_calls`, `trace_sql`, `trace_io`, `trace_threads`, `trace_exit_paths`.

### SECTION 22: IMPACT ANALYSIS
**Tables used:** edges, methods, classes
**Implementation:**
- 22.1 What Uses This: `SELECT * FROM edges WHERE dst_type=? AND dst_id=?`
- 22.2 What Breaks: recursive query — who depends on things that depend on this
- 22.3 What Depends On It: `SELECT * FROM edges WHERE dst_id=? AND edge_type IN ('depends_on','calls','imports')`
- 22.4 Reverse Call Graph: recursive CTE: `WITH RECURSIVE reverse_calls AS (SELECT * FROM edges WHERE dst_id=? UNION SELECT e.* FROM edges e JOIN reverse_calls r ON e.dst_id=r.src_id) SELECT * FROM reverse_calls;`
- 22.5 Forward Call Graph: same but `src_id=?` and join on `dst_id=r.src_id`
- 22.6 Ripple Radius: count of nodes in reverse call graph
- 22.7 Risk Score: `ripple_radius * cyclomatic_complexity / 10`
- 22.8 Confidence Score: based on graph completeness and test coverage
**Devin task:** Write `impact_engine.py` with class `ImpactEngine`. Commands: `what_uses`, `what_breaks`, `reverse_call_graph`, `forward_call_graph`, `ripple_radius`, `risk_score`.

### SECTION 23: DUPLICATE DETECTION
**Tables used:** files, classes, methods
**Implementation:**
- 23.1 Duplicate Files: `SELECT hash, COUNT(*) FROM files GROUP BY hash HAVING COUNT(*)>1`
- 23.2 Duplicate Classes: `SELECT class_name, hash, COUNT(*) FROM classes GROUP BY hash HAVING COUNT(*)>1`
- 23.3 Duplicate Methods: `SELECT method_name, hash, COUNT(*) FROM methods GROUP BY hash HAVING COUNT(*)>1`
- 23.4 Duplicate Logic: compare AST structures (normalize variable names, compare)
- 23.5 Duplicate SQL: extract SQL from method_code, hash, compare
- 23.6 Duplicate Constants: `SELECT value, COUNT(*) FROM config_constants GROUP BY value HAVING COUNT(*)>1`
- 23.7 Duplicate Imports: `SELECT imports FROM files` — find common subsets
- 23.8 Duplicate BCL: `SELECT bcl, COUNT(*) FROM methods GROUP BY bcl HAVING COUNT(*)>1`
- 23.9 Duplicate Algorithms: compare method_code with normalized whitespace
**Devin task:** Write `duplicate_engine.py` with class `DuplicateEngine`. Commands: `find_duplicate_files`, `find_duplicate_classes`, `find_duplicate_methods`, `find_duplicate_sql`, `find_duplicate_constants`, `find_all_duplicates`.

### SECTION 24: PATTERN ENGINE
**Tables used:** methods, classes, observations
**Implementation:**
- 24.1 Detect Design Patterns: match AST patterns for Singleton, Factory, Observer, etc.
- 24.2 Detect Anti-Patterns: God class (too many methods), long methods, deep nesting
- 24.3 Detect Code Smells: `has_print=1`, `has_decorator=1`, `has_self_underscore=1`
- 24.4 Detect Naming Patterns: PascalCase classes, UPPER_CASE constants, camelCase methods
- 24.5 Detect Architecture Rules: check VBStyle rules (Run() exists, Tuple3 returns)
- 24.6 Detect User Rules: check against rules in Config.py
- 24.7 Detect Violations: `SELECT * FROM methods WHERE has_print=1 OR has_decorator=1 OR has_self_underscore=1`
- 24.8 Suggest Improvements: based on violations found
**Devin task:** Write `pattern_engine.py` with class `PatternEngine`. Commands: `detect_patterns`, `detect_antipatterns`, `detect_smells`, `detect_violations`, `suggest_improvements`.

### SECTION 25: ARCHITECTURE VALIDATOR
**Tables used:** edges, classes, methods, files
**Implementation:**
- 25.1 Circular Dependencies: DFS over edges, detect back edges
- 25.2 Layer Violations: check if GUI imports from data layer, etc.
- 25.3 Invalid Imports: check if importing from deleted/nonexistent files
- 25.4 Missing Interfaces: classes that should implement an interface but don't
- 25.5 Missing Classes: references to class names not in classes table
- 25.6 Missing Methods: calls to method names not in methods table
- 25.7 Missing Files: import targets not in files table
- 25.8 Broken References: any reference to nonexistent entity
**Devin task:** Write `arch_validator.py` with class `ArchValidator`. Commands: `check_circular`, `check_layers`, `check_imports`, `check_missing`, `check_all`.

### SECTION 26: DATABASE VALIDATOR
**Tables used:** all (meta)
**Implementation:**
- 26.1 Missing Tables: compare actual tables to expected schema
- 26.2 Missing Indexes: check expected indexes exist
- 26.3 Missing Foreign Keys: `PRAGMA foreign_key_check`
- 26.4 Broken Constraints: `PRAGMA check_constraints`
- 26.5 Duplicate Rows: check for duplicate PKs
- 26.6 Orphan Rows: rows with FK pointing to nonexistent parent
- 26.7 Integrity Check: `PRAGMA integrity_check`
- 26.8 Optimization Check: `PRAGMA optimize`
**Devin task:** Write `db_validator.py` with class `DbValidator`. Commands: `check_tables`, `check_indexes`, `check_foreign_keys`, `check_integrity`, `check_all`.

### SECTION 27: BCL VALIDATOR
**Tables used:** files, classes, methods
**Implementation:**
- 27.1 Exists: `SELECT COUNT(*) FROM methods WHERE bcl IS NULL OR bcl=''`
- 27.2 Valid Format: regex check `^\[@\w+\]\{.*\}`
- 27.3 Complete: check all required BCL fields present
- 27.4 Hash Valid: recompute hash, compare to stored
- 27.5 Matches Code: compare BCL description to actual code behavior
- 27.6 Matches Database: compare BCL to DB metadata
- 27.7 References Valid: check BCL references resolve
- 27.8 Parent Exists: check BCL parent reference exists
**Devin task:** Extend `bcl_engine.py` with commands: `validate_exists`, `validate_format`, `validate_complete`, `validate_hash`, `validate_all`.

### SECTION 28: KNOWLEDGE GRAPH
**Tables used:** edges, knowledge, observations
**Implementation:** This is a VIEW that unifies all entity types into one graph.
```sql
CREATE VIEW knowledge_graph AS
SELECT 'file' AS entity_type, file_id AS entity_id, file_name AS label FROM files
UNION ALL
SELECT 'class', class_id, class_name FROM classes
UNION ALL
SELECT 'method', method_id, method_name FROM methods
UNION ALL
SELECT 'error', knowledge_id, problem FROM knowledge WHERE error_type IS NOT NULL
UNION ALL
SELECT 'fix', knowledge_id, answer FROM knowledge WHERE answer IS NOT NULL;
```
**Devin task:** Create this view in the schema. Add queries to traverse it.

### SECTION 29: AI MEMORY
**Tables used:** knowledge, observations
**Implementation:**
- 29.1 Previous Errors: `SELECT * FROM knowledge WHERE error_type IS NOT NULL ORDER BY created DESC`
- 29.2 Previous Fixes: `SELECT * FROM knowledge WHERE answer IS NOT NULL ORDER BY created DESC`
- 29.3 Previous Successes: `SELECT * FROM knowledge WHERE fix_result='success'`
- 29.4 Previous Failures: `SELECT * FROM knowledge WHERE fix_result='failure'`
- 29.5 User Rules: stored in Config.py constants
- 29.6 Coding Rules: stored in knowledge table with tags=['rule']
- 29.7 Architecture Rules: stored in knowledge table with tags=['architecture']
- 29.8 Learned Patterns: stored in knowledge table with tags=['pattern'] and high confidence
**Devin task:** Write `memory_engine.py` with class `MemoryEngine`. Commands: `recall_errors`, `recall_fixes`, `recall_successes`, `recall_failures`, `recall_rules`, `recall_patterns`, `recall_all`.

### SECTION 30: CONFIDENCE ENGINE
**Tables used:** knowledge, attempts
**Implementation:**
- 30.1 Parse Confidence: 100 if AST parse succeeds, 0 if fails
- 30.2 Match Confidence: similarity score 0-100 when matching patterns
- 30.3 Graph Confidence: percentage of entities with edges
- 30.4 Repair Confidence: based on similar past fixes success rate
- 30.5 Runtime Confidence: based on test pass rate
- 30.6 Test Confidence: passed/total tests * 100
- 30.7 Overall Confidence: weighted average of all above
**Devin task:** Write `confidence_engine.py` with class `ConfidenceEngine`. Commands: `parse_confidence`, `match_confidence`, `graph_confidence`, `repair_confidence`, `test_confidence`, `overall_confidence`.

### SECTION 31: SAFETY ENGINE
**Tables used:** snapshots
**Implementation:**
- 31.1 Never Touch Original: all writes go through sandbox first
- 31.2 Always Rollback: `ROLLBACK` on any exception
- 31.3 Verify Before Save: compile check before writing to disk
- 31.4 Verify After Save: compile check after writing to disk
- 31.5 Verify Graph: edge count unchanged unless intentional
- 31.6 Verify Database: `PRAGMA integrity_check` after write
- 31.7 Verify Runtime: instantiate + Run() after write
- 31.8 Verify Output: test suite passes after write
**Devin task:** Write `safety_engine.py` with class `SafetyEngine`. Commands: `safe_write`, `verify_before`, `verify_after`, `verify_all`, `emergency_rollback`.

### SECTION 32: BUILD PIPELINE
**Implementation:** This is the main orchestrator.
```python
# Run("build"):
scan()          # 32.1
parse()         # 32.2 — AST parse all files
index()         # 32.3 — populate files/classes/methods tables
bcl_extract()   # 32.4 — extract BCL from all entities
graph_build()   # 32.5 — build all edges
validate()      # 32.6 — run validation engine
learn()         # 32.7 — extract patterns, store in knowledge
store()         # 32.8 — commit to DB
test()          # 32.9 — run test suite
report()        # 32.10 — generate health report
```
**Devin task:** Write `build_pipeline.py` with class `BuildPipeline`. Commands: `build`, `build_step`, `rebuild`, `incremental_build`.

### SECTION 33: ROOT CAUSE ENGINE
**Tables used:** edges, knowledge, methods
**Implementation:**
- 33.1 Surface Error: the visible error (compile failure, test failure)
- 33.2 Walk Backward: from error method, follow reverse call graph
- 33.3 Dependency Analysis: check edges for the failing method
- 33.4 Data Flow Analysis: trace variable origin through method calls
- 33.5 Control Flow Analysis: trace branch/loop path that led to error
- 33.6 Origin Detection: find the first method in the chain that introduced the bug
- 33.7 First Cause: the root method/line that caused the cascade
- 33.8 Secondary Causes: methods that propagated the error
- 33.9 Cascading Effects: all methods affected by the root cause
**Devin task:** Write `root_cause_engine.py` with class `RootCauseEngine`. Commands: `analyze_error`, `walk_backward`, `find_origin`, `get_cascade`, `full_analysis`.

### SECTION 34: SELF-CHECK ENGINE
**Tables used:** snapshots, observations
**Implementation:**
- 34.1 Did Anything Change?: compare hashes before/after
- 34.2 Was It Expected?: check if change was in planned scope
- 34.3 Did Tests Pass?: run test suite
- 34.4 Did Graph Change?: compare edge count/types
- 34.5 Did Database Change?: compare row counts
- 34.6 Did BCL Change?: compare BCL hashes
- 34.7 Did Runtime Change?: compare test results
- 34.8 Is Confidence Higher?: compare confidence scores
**Devin task:** Write `self_check_engine.py` with class `SelfCheckEngine`. Commands: `check_changes`, `check_expected`, `check_tests`, `check_graph`, `check_all`.

### SECTION 35: PROJECT DIGITAL TWIN
**Implementation:** This is the culmination — the entire system IS the digital twin.
- 35.1 Entire Codebase in Database: files + classes + methods tables
- 35.2 Entire Dependency Graph: edges table
- 35.3 Entire Runtime Model: execution traces (section 21)
- 35.4 Entire BCL Model: bcl columns in all tables
- 35.5 Entire Error History: knowledge table
- 35.6 Entire Fix History: knowledge + attempts tables
- 35.7 Entire Architecture Model: edges + classes + observations
- 35.8 Entire Evolution Timeline: snapshots table
- 35.9 Queryable Knowledge Base: FTS5 + SQL views
- 35.10 Safe Simulation Before Real Changes: sandbox engine (section 2)
**Devin task:** Write `digital_twin.py` with class `DigitalTwin`. Commands: `get_state`, `simulate_change`, `query`, `export_snapshot`, `import_snapshot`, `compare_twins`.

### SECTION 36: COMPILER KNOWLEDGE
**Tables used:** knowledge
**Implementation:**
- 36.1 Compiler Errors: `py_compile.PyCompileError` → store in knowledge
- 36.2 Compiler Warnings: `warnings` module capture
- 36.3 Linker Errors: for C code (if applicable)
- 36.4 Build Logs: store full build output
- 36.5 Build Time: `time.time()` measurement
- 36.6 Build History: `SELECT * FROM knowledge WHERE tags LIKE '%build%'`
- 36.7 Build Environment: Python version, OS, dependencies
- 36.8 Compiler Version: `sys.version`
**Devin task:** Write `compiler_engine.py` with class `CompilerEngine`. Commands: `compile_file`, `compile_all`, `get_errors`, `get_warnings`, `build_history`.

### SECTION 37: RUNTIME KNOWLEDGE
**Tables used:** observations
**Implementation:**
- 37.1 Live Objects: `gc.get_objects()` filtered by type
- 37.2 Memory Map: `tracemalloc` snapshots
- 37.3 Heap: `gc.get_objects()` with sizes
- 37.4 Stack: `traceback.format_stack()`
- 37.5 Open Files: `psutil.Process().open_files()`
- 37.6 Open Sockets: `psutil.Process().connections()`
- 37.7 Threads: `threading.enumerate()`
- 37.8 Timers: track `threading.Timer` instances
- 37.9 Handles: `psutil.Process().num_handles()`
- 37.10 Resource Usage: `psutil.Process().memory_info()`, `cpu_percent()`
**Devin task:** Write `runtime_engine.py` with class `RuntimeEngine`. Commands: `snapshot`, `get_objects`, `get_memory`, `get_threads`, `get_resources`.

### SECTION 38: MEMORY FORENSICS
**Tables used:** observations
**Implementation:**
- 38.1 Memory Leak Detection: compare tracemalloc snapshots, find growing allocations
- 38.2 Object Lifetime: track `__init__` to `__del__` timestamps
- 38.3 Allocation History: log all allocations over time
- 38.4 Deallocation History: log all frees
- 38.5 Fragmentation: analyze allocation size distribution
- 38.6 Peak Usage: max memory from tracemalloc
- 38.7 Growth Trend: linear regression on memory over time
- 38.8 Leak History: `SELECT * FROM observations WHERE observation_type='memory_leak'`
**Devin task:** Write `memory_forensics.py` with class `MemoryForensics`. Commands: `detect_leaks`, `track_lifetime`, `allocation_history`, `peak_usage`, `growth_trend`.

### SECTION 39: SQL ANALYZER
**Tables used:** observations
**Implementation:**
- 39.1 Query History: log every `execute()` call
- 39.2 Query Plan: `EXPLAIN QUERY PLAN <sql>`
- 39.3 Slow Queries: queries taking > 100ms
- 39.4 Missing Indexes: compare queries to indexes, suggest additions
- 39.5 Table Usage: `SELECT * FROM edges WHERE edge_type='database_access'`
- 39.6 Transaction History: log BEGIN/COMMIT/ROLLBACK
- 39.7 Lock Analysis: detect `database is locked` errors
- 39.8 Deadlock Analysis: detect deadlock patterns
**Devin task:** Write `sql_analyzer.py` with class `SqlAnalyzer`. Commands: `log_query`, `explain_plan`, `find_slow`, `suggest_indexes`, `transaction_history`.

### SECTION 40: FILE FORENSICS
**Tables used:** files, observations
**Implementation:**
- 40.1 Creation Date: `os.path.getctime()`
- 40.2 Modification History: `os.path.getmtime()` + snapshots
- 40.3 Rename History: track file_name changes in files table
- 40.4 Move History: track path changes in files table
- 40.5 Ownership: `os.stat().st_uid`
- 40.6 Permissions: `oct(os.stat().st_mode)`
- 40.7 Encoding: `chardet.detect()`
- 40.8 File Signature: first 16 bytes as hex
- 40.9 Hash Timeline: `SELECT created, hash FROM snapshots WHERE file_id=? ORDER BY created`
**Devin task:** Write `file_forensics.py` with class `FileForensics`. Commands: `get_metadata`, `rename_history`, `hash_timeline`, `permissions_check`.

### SECTION 41: SOURCE EVOLUTION
**Tables used:** snapshots, files, classes, methods
**Implementation:**
- 41.1 Class Timeline: `SELECT * FROM classes WHERE class_name=? ORDER BY version`
- 41.2 Method Timeline: `SELECT * FROM methods WHERE method_name=? ORDER BY version`
- 41.3 Variable Timeline: track variable name changes
- 41.4 Dependency Timeline: track edge changes over time
- 41.5 Architecture Timeline: track class structure changes
- 41.6 Error Timeline: `SELECT * FROM knowledge WHERE error_type IS NOT NULL ORDER BY created`
- 41.7 Fix Timeline: `SELECT * FROM knowledge WHERE answer IS NOT NULL ORDER BY created`
- 41.8 Refactor Timeline: `SELECT * FROM attempts ORDER BY created`
**Devin task:** Write `evolution_engine.py` with class `EvolutionEngine`. Commands: `class_timeline`, `method_timeline`, `dependency_timeline`, `error_timeline`, `fix_timeline`, `refactor_timeline`.

### SECTION 42: CALL PATH DATABASE
**Tables used:** edges (edge_type='calls')
**Implementation:**
- 42.1 Incoming Calls: `SELECT * FROM edges WHERE dst_type='method' AND dst_id=? AND edge_type='calls'`
- 42.2 Outgoing Calls: `SELECT * FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls'`
- 42.3 Recursive Calls: method that calls itself (src_id == dst_id)
- 42.4 Event Calls: methods triggered by events (GUI callbacks)
- 42.5 Async Calls: methods with `async` or `await`
- 42.6 Callback Chains: follow callback registrations
- 42.7 Signal Chains: follow signal/slot connections
- 42.8 Complete Execution Paths: DFS from entry point, enumerate all paths
**Devin task:** Write `call_path_engine.py` with class `CallPathEngine`. Commands: `incoming`, `outgoing`, `recursive`, `async_calls`, `execution_paths`, `call_chain`.

### SECTION 43: DATA FLOW ENGINE
**Tables used:** methods, edges
**Implementation:**
- 43.1 Variable Origin: find first assignment of a variable (AST walk)
- 43.2 Variable Mutation: find all assignments to a variable
- 43.3 Variable Lifetime: from first assignment to last use
- 43.4 Parameter Flow: trace parameter through method calls
- 43.5 Return Flow: trace return values through call chain
- 43.6 Database Flow: trace data from SQL queries through code
- 43.7 File Flow: trace data from file reads through code
- 43.8 Network Flow: trace data from network calls through code
**Devin task:** Write `data_flow_engine.py` with class `DataFlowEngine`. Commands: `trace_variable`, `trace_parameter`, `trace_return`, `trace_database_flow`, `trace_file_flow`.

### SECTION 44: CONTROL FLOW ENGINE
**Tables used:** methods
**Implementation:**
- 44.1 Branches: count `if/elif/else` in method_code
- 44.2 Loops: count `for/while` in method_code
- 44.3 Switches: (Python has no switch, but match/case in 3.10+)
- 44.4 Exceptions: count `try/except/finally` in method_code
- 44.5 Early Returns: count `return` before end of method
- 44.6 Exit Paths: all possible return/raise points
- 44.7 Unreachable Code: code after unconditional return/raise
- 44.8 Infinite Loops: `while True` without break
**Devin task:** Write `control_flow_engine.py` with class `ControlFlowEngine`. Commands: `analyze_branches`, `analyze_loops`, `find_unreachable`, `find_infinite_loops`, `exit_paths`.

### SECTION 45: SYMBOL DATABASE
**Tables used:** classes, methods, observations
**Implementation:**
- 45.1 Classes: already in classes table
- 45.2 Methods: already in methods table
- 45.3 Variables: extract from AST, store in observations
- 45.4 Constants: extract from Config.py, store in config_constants
- 45.5 Enums: find `class X(Enum)` patterns
- 45.6 Structs: (Python has no structs, but namedtuples)
- 45.7 Interfaces: find abstract base classes
- 45.8 Typedefs: find `TypeAlias` or `X = TypeVar`
**Devin task:** Write `symbol_engine.py` with class `SymbolEngine`. Commands: `get_all_symbols`, `get_variables`, `get_constants`, `get_enums`, `get_interfaces`.

### SECTION 46: TYPE SYSTEM
**Tables used:** methods, observations
**Implementation:**
- 46.1 Type Definitions: extract from type hints
- 46.2 Type Inference: infer types from assignments
- 46.3 Casts: find `cast()`, `typing.Cast`
- 46.4 Conversions: find `int()`, `str()`, `float()`, `list()` calls
- 46.5 Nullable Analysis: find `Optional`, `None` checks
- 46.6 Generic Analysis: find `TypeVar`, `Generic`
- 46.7 Compatibility: check if types match across calls
- 46.8 Violations: type mismatches
**Devin task:** Write `type_engine.py` with class `TypeEngine`. Commands: `extract_types`, `infer_types`, `find_violations`, `check_compatibility`.

### SECTION 47: NAMING ENGINE
**Tables used:** classes, methods, observations
**Implementation:**
- 47.1 Naming Rules: PascalCase classes, UPPER_CASE constants, snake_case methods
- 47.2 Duplicate Names: `SELECT method_name, COUNT(*) FROM methods GROUP BY method_name HAVING COUNT(*)>1`
- 47.3 Similar Names: Levenshtein distance on names
- 47.4 Reserved Words: check against Python keywords
- 47.5 User Standards: check against VBStyle rules
- 47.6 Consistency: check naming convention adherence
- 47.7 Violations: list all naming violations
- 47.8 Suggestions: propose better names
**Devin task:** Write `naming_engine.py` with class `NamingEngine`. Commands: `check_rules`, `find_duplicates`, `find_similar`, `find_violations`, `suggest_names`.

### SECTION 48: CODE QUALITY ENGINE
**Tables used:** methods, classes
**Implementation:**
- 48.1 Complexity: `cyclomatic_complexity` from methods table
- 48.2 Readability: line length, comment ratio, naming quality
- 48.3 Maintainability: complexity + dependency count + test coverage
- 48.4 Cohesion: methods in a class should relate to class purpose
- 48.5 Coupling: count of dependencies per class
- 48.6 Reuse: how many times a method is called (incoming edges)
- 48.7 Documentation: ratio of docstrings to methods
- 48.8 Stability: how often a method changes (version count)
**Devin task:** Write `quality_engine.py` with class `QualityEngine`. Commands: `complexity_score`, `readability_score`, `maintainability_score`, `cohesion_score`, `coupling_score`, `quality_report`.

### SECTION 49: REFACTOR ENGINE
**Tables used:** methods, classes, files, snapshots, attempts
**Implementation:**
- 49.1 Safe Rename: rename method/class, update all references in edges, write back
- 49.2 Safe Move: move method to different class, update class_id
- 49.3 Safe Extract: extract code block into new method
- 49.4 Safe Inline: inline method body at call site, remove method
- 49.5 Safe Split: split large method into smaller ones
- 49.6 Safe Merge: merge duplicate methods into one
- 49.7 Safe Delete: remove method if no incoming edges
- 49.8 Safe Replace: replace method body with new implementation
Each operation: snapshot before → apply → compile → test → snapshot after → record
**Devin task:** Write `refactor_engine.py` with class `RefactorEngine`. Commands: `safe_rename`, `safe_move`, `safe_extract`, `safe_inline`, `safe_split`, `safe_merge`, `safe_delete`, `safe_replace`.

### SECTION 50: TEST KNOWLEDGE
**Tables used:** knowledge, observations
**Implementation:**
- 50.1 Unit Tests: run test_everything.py, store results
- 50.2 Integration Tests: run domain_loader.py, store results
- 50.3 Regression Tests: compare test results to previous run
- 50.4 Coverage: `coverage.py` results
- 50.5 Failed Tests: `SELECT * FROM knowledge WHERE tags LIKE '%test%' AND fix_result='failure'`
- 50.6 Passed Tests: `SELECT * FROM knowledge WHERE tags LIKE '%test%' AND fix_result='success'`
- 50.7 Missing Tests: methods with no test coverage
- 50.8 Test History: `SELECT * FROM observations WHERE observation_type='test_result' ORDER BY created`
**Devin task:** Write `test_engine.py` with class `TestEngine`. Commands: `run_unit_tests`, `run_integration_tests`, `run_regression`, `get_coverage`, `find_missing_tests`, `test_history`.

### SECTION 51: API KNOWLEDGE
**Tables used:** observations, edges
**Implementation:**
- 51.1 Endpoints: find `@app.route`, `def handle_` patterns
- 51.2 Parameters: extract from function signatures
- 51.3 Responses: extract return values
- 51.4 Errors: extract error responses
- 51.5 Authentication: find auth checks
- 51.6 Rate Limits: find rate limiting code
- 51.7 Dependencies: which methods does each endpoint call
- 51.8 Usage Graph: edges for API call patterns
**Devin task:** Write `api_engine.py` with class `ApiEngine`. Commands: `find_endpoints`, `get_parameters`, `get_responses`, `get_dependencies`, `usage_graph`.

### SECTION 52: CONFIGURATION ENGINE
**Tables used:** config_constants (existing), observations
**Implementation:**
- 52.1 Config Files: identify Config.py and similar
- 52.2 Environment Variables: find `os.environ`, `os.getenv`
- 52.3 Feature Flags: find conditional features
- 52.4 Build Options: find build-related config
- 52.5 Runtime Options: find runtime config
- 52.6 Defaults: extract default values
- 52.7 Overrides: find override patterns
- 52.8 Validation: check config completeness
**Devin task:** Write `config_engine.py` with class `ConfigEngine`. Commands: `scan_config`, `get_constants`, `find_env_vars`, `find_feature_flags`, `validate_config`.

### SECTION 53: OBSERVATION ENGINE
**Tables used:** observations
**Implementation:**
- 53.1 Everything Seen: `SELECT * FROM observations`
- 53.2 Everything Changed: `SELECT * FROM observations WHERE observation_type='change'`
- 53.3 Everything Learned: `SELECT * FROM knowledge WHERE confidence > 50`
- 53.4 Everything Ignored: `SELECT * FROM observations WHERE observation_type='ignored'`
- 53.5 Unknowns: `SELECT * FROM observations WHERE observation_type='unknown'`
- 53.6 Assumptions: `SELECT * FROM observations WHERE observation_type='assumption'`
- 53.7 Confirmed Facts: `SELECT * FROM observations WHERE observation_type='confirmed'`
- 53.8 Evidence Links: `SELECT * FROM observations WHERE evidence IS NOT NULL`
**Devin task:** Write `observation_engine.py` with class `ObservationEngine`. Commands: `observe`, `recall_all`, `recall_changes`, `recall_learned`, `recall_unknowns`, `confirm_fact`.

### SECTION 54: UNKNOWN ENGINE
**Tables used:** observations
**Implementation:**
- 54.1 Missing Classes: referenced but not in classes table
- 54.2 Missing Files: imported but not in files table
- 54.3 Missing Methods: called but not in methods table
- 54.4 Missing Definitions: referenced names not defined anywhere
- 54.5 Unknown Types: type hints that reference unknown types
- 54.6 Unknown Dependencies: import targets that can't be resolved
- 54.7 Unknown Runtime: methods that have never been called in tests
- 54.8 Unknown Behavior: methods with no documentation
**Devin task:** Write `unknown_engine.py` with class `UnknownEngine`. Commands: `find_missing_classes`, `find_missing_methods`, `find_missing_files`, `find_unknowns`, `report_unknowns`.

### SECTION 55: DECISION ENGINE
**Tables used:** knowledge, attempts, observations
**Implementation:**
- 55.1 Candidate Fixes: `SELECT * FROM knowledge WHERE problem LIKE ? AND answer IS NOT NULL`
- 55.2 Rank Fixes: ORDER BY confidence DESC, fix_result='success' first
- 55.3 Risk Analysis: impact_engine.risk_score for affected methods
- 55.4 Cost Analysis: estimate lines changed, methods affected
- 55.5 Benefit Analysis: how many violations removed, tests fixed
- 55.6 Simulation: apply in sandbox, measure outcome
- 55.7 Validation: compile + test in sandbox
- 55.8 Final Decision: choose fix with best confidence/risk ratio
**Devin task:** Write `decision_engine.py` with class `DecisionEngine`. Commands: `get_candidates`, `rank_fixes`, `analyze_risk`, `simulate`, `decide`.

### SECTION 56: ORCHESTRATION ENGINE
**Tables used:** all
**Implementation:**
- 56.1 Task Queue: list of pending refactoring tasks
- 56.2 Worker Queue: tasks currently being processed
- 56.3 Dependency Queue: tasks waiting on other tasks
- 56.4 Priority Queue: order by risk score (high risk = high priority)
- 56.5 Retry Queue: failed tasks to retry
- 56.6 Rollback Queue: tasks that need rollback
- 56.7 Learning Queue: tasks that need knowledge update
- 56.8 Reporting Queue: tasks that need reporting
**Devin task:** Write `orchestration_engine.py` with class `OrchestrationEngine`. Commands: `enqueue`, `dequeue`, `prioritize`, `retry`, `rollback`, `process_queue`, `get_status`.

### SECTION 57: DIGITAL EVIDENCE ENGINE
**Tables used:** knowledge, attempts, snapshots, observations
**Implementation:**
- 57.1 Every Conclusion Linked to Evidence: knowledge.evidence IS NOT NULL
- 57.2 Every Fix Linked to Error: knowledge.knowledge_id linked via attempts.knowledge_id
- 57.3 Every Error Linked to Source: knowledge.file_id, class_id, method_id
- 57.4 Every Source Linked to Graph: edges reference file_id/class_id/method_id
- 57.5 Every Graph Linked to BCL: edges.evidence contains BCL reference
- 57.6 Every BCL Linked to Code: bcl column in methods references method_code
- 57.7 Every Code Change Linked to Snapshot: attempts.before_code/after_code
- 57.8 Full Audit Trail: `SELECT * FROM attempts JOIN knowledge ON attempts.knowledge_id = knowledge.knowledge_id JOIN snapshots ON attempts.method_id = snapshots.method_id ORDER BY created`
**Devin task:** Write `evidence_engine.py` with class `EvidenceEngine`. Commands: `verify_evidence_chain`, `get_audit_trail`, `link_evidence`, `find_unlinked`.

### SECTION 58: PROJECT DNA
**Tables used:** all (aggregate queries)
**Implementation:**
- 58.1 Coding Style DNA: distribution of naming conventions, indentation, line length
- 58.2 Architecture DNA: class hierarchy depth, coupling distribution, layer count
- 58.3 Naming DNA: most common name patterns, prefixes, suffixes
- 58.4 Error DNA: most common error types, error frequency
- 58.5 Fix DNA: most common fix patterns, success rate by fix type
- 58.6 Dependency DNA: import graph density, most depended-on modules
- 58.7 Runtime DNA: memory usage pattern, call frequency distribution
- 58.8 Project Identity: hash of all DNA features = unique project fingerprint
**Devin task:** Write `dna_engine.py` with class `DnaEngine`. Commands: `extract_dna`, `compare_dna`, `project_identity`, `style_dna`, `architecture_dna`, `error_dna`, `fix_dna`.

### SECTION 59: PREDICTION ENGINE
**Tables used:** knowledge, methods, edges
**Implementation:**
- 59.1 Predict Next Error: based on error history patterns and current code state
- 59.2 Predict Broken Code: methods with high complexity + recent changes
- 59.3 Predict Side Effects: ripple radius of planned changes
- 59.4 Predict Build Failure: presence of syntax errors, import errors
- 59.5 Predict Runtime Failure: methods with no tests + high complexity
- 59.6 Predict Performance Impact: methods on hot path with high complexity
- 59.7 Predict Refactor Risk: ripple radius * complexity * lack of tests
- 59.8 Predict Maintenance Cost: complexity + coupling + change frequency
**Devin task:** Write `prediction_engine.py` with class `PredictionEngine`. Commands: `predict_next_error`, `predict_broken_code`, `predict_side_effects`, `predict_build_failure`, `predict_refactor_risk`, `predict_maintenance_cost`.

### SECTION 60: AUTONOMOUS REASONING LOOP
**Implementation:** This is the top-level AI loop that ties everything together.
```python
# Run("autonomous_reason"):
observe()           # 60.1 — scan current state
parse()             # 60.2 — parse all files
understand()        # 60.3 — build graph, extract relationships
graph()             # 60.4 — build all edges
correlate()         # 60.5 — find patterns, correlations
search_memory()     # 60.6 — query knowledge table
search_history()    # 60.7 — query snapshots, attempts
generate_hypotheses() # 60.8 — propose fixes
simulate()          # 60.9 — test in sandbox
validate()          # 60.10 — compile + test
repair()            # 60.11 — apply fix
verify()            # 60.12 — verify result
learn()             # 60.13 — record outcome in knowledge
record()            # 60.14 — store in observations
# 60.15 repeat
```
**Devin task:** Write `autonomous_loop.py` with class `AutonomousLoop`. Commands: `reason`, `run_cycle`, `run_until_clean`, `run_n_cycles`.

### SECTION 70: META-LEARNING ENGINE
**Tables used:** knowledge, attempts
**Implementation:**
- 70.1 Learn from past runs: analyze attempts table, find success/failure patterns
- 70.2 Improve graph accuracy: refine edge detection based on missed edges
- 70.3 Optimize repair strategies: rank fix types by success rate, prefer best
- 70.4 Evolve detection heuristics: adjust violation detection thresholds
- 70.5 Reduce repeated failure classes: blacklist fixes that consistently fail
- 70.6 Improve prediction models: adjust prediction weights based on accuracy
- 70.7 Adapt schema automatically: add columns/tables as new needs arise
- 70.8 Self-benchmarking: measure improvement over time (error rate, fix rate)
**Devin task:** Write `meta_learning_engine.py` with class `MetaLearningEngine`. Commands: `learn_from_history`, `optimize_strategies`, `evolve_heuristics`, `benchmark`, `improve`.

### SECTION 71: EXECUTION FORMAT KERNEL
**Implementation:** This controls how the system outputs results.
- 71.1 Strict Output Mode: output only structured data (JSON/SQL), no prose
- 71.2 Single-block enforcement: all output in one response block
- 71.3 No auxiliary commentary: no "Here's what I found..." text
- 71.4 No narrative injection: no storytelling in output
- 71.5 Raw structure output: pure data
- 71.6 User-format compliance: match requested format exactly
- 71.7 Hard boundary enforcement: no text before/after output block
- 71.8 Format violation termination: stop if format is violated
**Devin task:** Write `format_kernel.py` with class `FormatKernel`. Commands: `set_mode`, `validate_output`, `enforce_boundaries`.

### SECTION 72: CONTEXT CONTINUITY ENGINE
**Implementation:** Ensures sequential processing without rework.
- 72.1 Sequential module continuation lock: track last processed index
- 72.2 Prevent redefinition of existing indices: check before creating
- 72.3 Append-only structural expansion: never overwrite, only add
- 72.4 No backtracking overwrite: don't redo completed sections
- 72.5 Continuation pointer registry: store last completed step
- 72.6 Section jump prevention: must process in order
- 72.7 Strict index continuity: verify index sequence
**Devin task:** Write `continuity_engine.py` with class `ContinuityEngine`. Commands: `get_pointer`, `set_pointer`, `verify_continuity`, `next_section`.

### SECTION 73: ERROR RESISTANCE LAYER
**Implementation:** Handles bad input gracefully.
- 73.1 Invalid instruction detection: validate commands before execution
- 73.2 Conflicting constraint resolver: when two rules conflict, pick higher priority
- 73.3 Partial instruction recovery: if part of instruction fails, recover what's possible
- 73.4 Input ambiguity isolation: separate ambiguous from clear instructions
- 73.5 Execution-safe fallback: if unknown command, return Tuple3 error
- 73.6 Deterministic output recovery: same input always produces same output
- 73.7 Rule conflict prioritization: resolve by rule priority
**Devin task:** Write `error_resistance.py` with class `ErrorResistance`. Commands: `validate_instruction`, `resolve_conflict`, `safe_fallback`, `recover_partial`.

### SECTION 74: OUTPUT INTEGRITY CORE
**Implementation:** Validates output before returning.
- 74.1 Block boundary enforcement: output must be complete blocks
- 74.2 Encoding consistency: all output UTF-8
- 74.3 Structural completeness: all required fields present
- 74.4 Missing section detection: check all expected sections exist
- 74.5 Output schema lock: output must match expected schema
- 74.6 Corruption detection: hash output, compare to expected
- 74.7 Final render pass: validate before returning
**Devin task:** Write `output_integrity.py` with class `OutputIntegrity`. Commands: `validate_block`, `check_completeness`, `check_schema`, `final_validate`.

### SECTION 75: CONTINUATION PROTOCOL
**Implementation:** For multi-step processing.
- 75.1 Append-only continuation: never reprint previous sections
- 75.2 No reprint of previous: check if section already output
- 75.3 No summarization of prior: don't summarize what was already said
- 75.4 Strict next-index alignment: continue from exact next index
- 75.5 Linear expansion: only add, never replace
- 75.6 Forced sequential numbering: maintain strict numbering
- 75.7 End-state pointer tracking: store final state for resumption
**Devin task:** Extend `continuity_engine.py` with these commands.

---

## FILE STRUCTURE FOR DEVIN

```
Dom_Graph/
├── Config.py                    # Add 5-table schema to SCHEMA_SQL
├── backup_engine.py             # Section 1
├── sandbox_engine.py            # Section 2
├── knowledge_engine.py          # Section 3, 14, 29
├── graph_builder.py             # Section 4
├── ingestion_engine.py          # Section 5
├── bcl_engine.py                # Section 9, 27
├── static_analyzer.py           # Section 10
├── relationship_extractor.py    # Section 11
├── fix_engine.py                # Section 12
├── validation_engine.py         # Section 13
├── report_engine.py             # Section 15
├── continuous_loop.py           # Section 16
├── fingerprint_engine.py        # Section 17
├── snapshot_engine.py           # Section 18
├── diff_engine.py               # Section 19
├── search_engine.py             # Section 20
├── trace_engine.py              # Section 21
├── impact_engine.py             # Section 22
├── duplicate_engine.py          # Section 23
├── pattern_engine.py            # Section 24
├── arch_validator.py            # Section 25
├── db_validator.py              # Section 26
├── memory_engine.py             # Section 29
├── confidence_engine.py         # Section 30
├── safety_engine.py             # Section 31
├── build_pipeline.py            # Section 32
├── root_cause_engine.py         # Section 33
├── self_check_engine.py         # Section 34
├── digital_twin.py              # Section 35
├── compiler_engine.py           # Section 36
├── runtime_engine.py            # Section 37
├── memory_forensics.py          # Section 38
├── sql_analyzer.py              # Section 39
├── file_forensics.py            # Section 40
├── evolution_engine.py          # Section 41
├── call_path_engine.py          # Section 42
├── data_flow_engine.py          # Section 43
├── control_flow_engine.py       # Section 44
├── symbol_engine.py             # Section 45
├── type_engine.py               # Section 46
├── naming_engine.py             # Section 47
├── quality_engine.py            # Section 48
├── refactor_engine.py           # Section 49
├── test_engine.py               # Section 50
├── api_engine.py                # Section 51
├── config_engine.py             # Section 52
├── observation_engine.py        # Section 53
├── unknown_engine.py            # Section 54
├── decision_engine.py           # Section 55
├── orchestration_engine.py      # Section 56
├── evidence_engine.py           # Section 57
├── dna_engine.py                # Section 58
├── prediction_engine.py         # Section 59
├── autonomous_loop.py           # Section 60
├── meta_learning_engine.py      # Section 70
├── format_kernel.py             # Section 71
├── continuity_engine.py         # Section 72, 75
├── error_resistance.py          # Section 73
└── output_integrity.py          # Section 74
```

## VBSTYLE REQUIREMENTS FOR ALL FILES
- Every class: `__init__(self, mem=None, db=None, param=None)`, `self.state` dict, `Run(self, command, params=None)` dispatch
- All methods return Tuple3: `(1, data, None)` or `(0, None, (code, desc, 0))`
- No print(), no decorators, no self._, no tabs, no enums
- PascalCase classes, UPPERCASE constants, spaces only
- One class per file

## PRIORITY ORDER FOR DEVIN
1. **Phase 1 (Foundation):** Sections 1, 2, 5, 6, 7, 8, 9 — backup, sandbox, ingestion, 3 core tables, BCL
2. **Phase 2 (Graph):** Sections 4, 11, 17, 18 — graph building, relationships, fingerprinting, snapshots
3. **Phase 3 (Knowledge):** Sections 3, 12, 14, 29 — error DB, fix engine, knowledge storage, AI memory
4. **Phase 4 (Analysis):** Sections 10, 20-24, 42-48 — static analysis, search, impact, duplicates, patterns
5. **Phase 5 (Quality):** Sections 13, 25-27, 31, 34, 50 — validation, validators, safety, self-check, tests
6. **Phase 6 (Intelligence):** Sections 33, 53-60 — root cause, observation, unknown, decision, prediction, autonomous loop
7. **Phase 7 (Meta):** Sections 70-75 — meta-learning, format, continuity, error resistance, output integrity

## VERIFY AFTER EACH PHASE
- `py_compile` all files
- `python3 test_everything.py` — all 205+ tests pass
- No VBStyle violations (audit_vbstyle.py)
- DB integrity check passes
