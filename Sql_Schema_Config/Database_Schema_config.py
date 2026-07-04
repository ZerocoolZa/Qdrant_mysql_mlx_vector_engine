#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Database_Schema_config.py
# Domain:   Schema Lint Configuration
# Authority: Single source of truth for all schema validation rules
# DB:       None (this IS the config)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — NO hardcoded paths. All paths derived from BASE_DIR.
#
# AI GUIDE — READ THIS FIRST
# ----------------------------------------------------------------------------
# This file is the single source of truth for schema lint rules.
# It contains 36 structural rules across 4 domains, plus 80 design rules
# extracted from official SQLite and MySQL documentation (engine-tagged):
#
#   STRUCTURAL (36 rules, 4 domains):
#   1. Integrity / correctness     — schema is valid
#   2. Normalization / design      — schema is well designed
#   3. Performance / indexing      — schema is query efficient
#   4. Naming / metadata           — schema is clean and maintainable
#
#   DESIGN (80 rules, 7 categories, engine-tagged SQLite / MySQL / both):
#   a. Schema integrity            g. Engine-specific differences
#   b. Referential integrity        (see DB_DESIGN_DOMAINS for full list)
#   c. Indexing and performance
#   d. Data type
#   e. Naming and metadata
#   f. Normalization
#
# To add a rule:
#   1. Add a tuple to Config.RULES
#   2. If new check_type, add a check function to the engine
#
# To toggle a rule:
#   Change True/False in the tuple
#
# To tune a threshold:
#   Change the class attribute (e.g. MAX_LOB_COLUMNS = 1 → 3)
# ============================================================================

import os


class Config:
    # ------------------------------------------------------------------------
    # BASE DIRECTORY
    # ------------------------------------------------------------------------
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # ------------------------------------------------------------------------
    # ENGINE PATHS
    # ------------------------------------------------------------------------
    ENGINE_PATH = os.path.join(BASE_DIR, "..", "efl_brain", "schema_lint_engine.py")
    C_ENGINE_PATH = os.path.join(os.path.expanduser("~"), "bin", "schemalint")

    # ------------------------------------------------------------------------
    # VERSIONS
    # ------------------------------------------------------------------------
    CONFIG_VERSION = "2.1"
    RULE_COUNT = 36
    DB_DESIGN_RULE_COUNT = 80
    TOTAL_RULE_COUNT = 116

    # ------------------------------------------------------------------------
    # SEVERITIES
    # ------------------------------------------------------------------------
    SEVERITY_HIGH = "high"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_LOW = "low"

    # Engine-enforced vs best-practice (from official SQLite/MySQL docs research).
    # STRICT    = engine raises an error / impossible at runtime.
    # GUIDELINE = documented best practice; not a hard engine error.
    SEVERITY_STRICT = "strict"
    SEVERITY_GUIDELINE = "guideline"

    # Engine tags for DB_DESIGN_RULES below.
    ENGINE_SQLITE = "sqlite"
    ENGINE_MYSQL = "mysql"

    # ------------------------------------------------------------------------
    # THRESHOLDS — tune these to control rule sensitivity
    # ------------------------------------------------------------------------
    MAX_LOB_COLUMNS = 1
    MAX_TABLE_COLUMNS = 30
    MAX_INDEX_COLUMNS = 4
    MIN_TABLES_FOR_SPREAD = 3

    # ------------------------------------------------------------------------
    # TYPE LISTS
    # ------------------------------------------------------------------------
    LOB_TYPES = ["TEXT", "BLOB"]
    BOOLEAN_TYPES = ["INTEGER", "INT", "BOOLEAN", "BOOL", "TINYINT"]

    # ------------------------------------------------------------------------
    # NAMING PATTERNS
    # ------------------------------------------------------------------------
    BAD_COLUMN_PATTERNS = [r"^.*\.ID$"]
    CSV_INDICATORS = ["_list", "_ids", "_csv", "_tags", "_names"]
    BAD_TIMESTAMP_NAMES = ["timestamp", "time", "ts", "datetime"]
    BOOLEAN_PREFIXES = ["is_", "has_"]
    FK_SUFFIX = "_id"

    # ------------------------------------------------------------------------
    # SQL RESERVED WORDS
    # ------------------------------------------------------------------------
    SQL_RESERVED_WORDS = [
        "abort", "action", "add", "after", "all", "alter", "analyze", "and", "as",
        "asc", "attach", "autoincrement", "before", "begin", "between", "by",
        "cascade", "case", "cast", "check", "collate", "column", "commit",
        "conflict", "constraint", "create", "cross", "current_date",
        "current_time", "current_timestamp", "database", "default", "deferrable",
        "deferred", "delete", "desc", "detach", "distinct", "drop", "each",
        "else", "end", "escape", "except", "exclusive", "exists", "explain",
        "fail", "for", "foreign", "from", "full", "glob", "group", "having",
        "if", "ignore", "immediate", "in", "index", "indexed", "initially",
        "inner", "insert", "instead", "intersect", "into", "is", "isnull",
        "join", "key", "left", "like", "limit", "match", "natural", "no",
        "not", "notnull", "null", "of", "offset", "on", "or", "order", "outer",
        "plan", "pragma", "primary", "query", "raise", "references", "regexp",
        "reindex", "rename", "replace", "restrict", "right", "rollback", "row",
        "savepoint", "select", "set", "table", "temp", "temporary", "then",
        "timestamp", "to", "transaction", "trigger", "union", "unique",
        "update", "using", "vacuum", "values", "view", "virtual", "when",
        "where",
    ]

    # ------------------------------------------------------------------------
    # RULES — (id, description, severity, check_type, enabled)
    # ------------------------------------------------------------------------
    # To add a rule: add a tuple here. If check_type is new, add a check
    # function to the engine. No other changes needed.
    # To disable a rule: change True to False.
    # ------------------------------------------------------------------------

    RULES = [
        # --- 1. INTEGRITY / CORRECTNESS — schema is valid ---
        ("must_have_pk",              "Every table MUST have a primary key",                          "high",   "table_must_have_pk",              True),
        ("pk_must_not_be_nullable",   "Primary key columns MUST NOT be nullable",                     "high",   "pk_must_not_be_nullable",         True),
        ("fk_type_must_match",        "FK column type MUST match referenced PK type",                 "medium", "fk_type_must_match",              True),
        ("no_fk_self_reference",      "FKs MUST NOT self-reference the PK",                           "medium", "no_fk_self_reference",            True),
        ("no_fk_cycles",              "Tables MUST NOT have cyclical FK relationships",               "high",   "no_table_cycles",                 True),
        ("no_orphaned_fk",            "FK MUST reference a table that exists",                        "high",   "no_orphaned_fk_target",           True),
        ("no_fk_missing_ref_col",     "FK referenced column MUST exist on target table",              "high",   "no_fk_missing_ref_column",        True),
        ("must_enforce_fk",           "Database MUST enforce foreign keys",                            "high",   "must_enforce_foreign_keys",       True),
        ("no_without_rowid_no_pk",    "WITHOUT ROWID tables MUST have a primary key",                 "high",   "no_without_rowid_without_pk",     True),
        ("no_autoincr_non_integer",   "AUTOINCREMENT MUST NOT be on non-INTEGER PK",                  "medium", "no_autoincrement_non_integer",    True),

        # --- 2. NORMALIZATION / DESIGN — schema is well designed ---
        ("no_all_nullable",           "Tables MUST NOT have all nullable non-PK columns",             "medium", "no_all_nullable_columns",         True),
        ("no_single_column_tables",   "Tables MUST NOT have fewer than 2 columns",                    "low",    "no_single_column_table",          True),
        ("no_composite_pk",           "Tables SHOULD NOT use composite primary keys",                 "medium", "no_composite_pk",                 True),
        ("no_incrementing_columns",   "Tables MUST NOT have incrementing column names",               "medium", "no_incrementing_columns",         True),
        ("no_csv_in_text",            "TEXT columns MUST NOT have CSV-indicator names",               "medium", "no_csv_in_text_column",           True),
        ("no_wide_table",             "Tables MUST NOT have more than 30 columns",                    "medium", "no_wide_table",                   True),
        ("no_column_spread",          "Same non-FK column in 3+ tables suggests denormalization",     "low",    "no_duplicate_column_spread",      True),

        # --- 3. PERFORMANCE / INDEXING — schema is query efficient ---
        ("fk_must_have_index",        "Every FK column MUST have an index",                           "low",    "fk_must_have_index",              True),
        ("pk_must_be_first",          "Primary key columns MUST be declared first",                   "low",    "pk_must_be_first",                True),
        ("no_redundant_indexes",      "Tables MUST NOT have redundant indexes",                       "high",   "no_redundant_indexes",            True),
        ("no_duplicate_indexes",      "Tables MUST NOT have exact duplicate indexes",                 "medium", "no_duplicate_indexes",            True),
        ("no_nullable_in_unique",     "Unique indexes MUST NOT contain nullable columns",             "medium", "no_nullable_in_unique_index",     True),
        ("no_index_too_many_cols",    "Indexes MUST NOT have more than 4 columns",                    "low",    "no_index_too_many_columns",       True),
        ("no_over_indexed",           "Tables MUST NOT have more indexes than columns",               "low",    "no_over_indexed_table",           True),

        # --- 4. NAMING / METADATA — schema is clean and maintainable ---
        ("no_reserved_words",         "Names MUST NOT be SQL reserved words",                         "medium", "name_must_not_be_in_list",        True),
        ("no_spaces_in_names",        "Names MUST NOT contain spaces",                                "medium", "name_must_not_contain_spaces",    True),
        ("no_bad_column_names",       "Columns MUST NOT be named bare ID",                            "low",    "no_bad_column_names",             True),
        ("no_string_null_default",    "Defaults MUST NOT be string NULL",                             "medium", "no_string_null_default",          True),
        ("no_mixed_naming_case",      "Column names MUST NOT mix snake_case and camelCase",           "low",    "no_inconsistent_naming_case",     True),
        ("no_col_prefix_match_table", "Column names MUST NOT redundantly prefix table name",          "low",    "no_column_prefix_match_table",    True),
        ("no_bool_wrong_type",        "is_*/has_* columns MUST be INTEGER type",                      "low",    "no_boolean_without_prefix",       True),
        ("no_timestamp_naming",       "Columns MUST NOT be named timestamp/time (use created_at)",    "medium", "no_timestamp_naming",             True),
        ("fk_must_have_id_suffix",    "Foreign key columns MUST end with _id",                        "low",    "fk_column_must_have_id_suffix",   True),
        ("column_type_consistent",    "Same column name MUST have same type across tables",           "medium", "column_type_consistent",          True),

        # --- OPTIONAL (disabled by default) ---
        ("no_empty_tables",           "Tables MUST NOT be empty",                                     "low",    "no_empty_table",                  False),
        ("no_table_without_indexes",  "Tables MUST NOT lack indexes entirely",                        "low",    "no_table_without_indexes",        False),
    ]

    # ------------------------------------------------------------------------
    # RULE DOMAINS — for documentation and reporting
    # ------------------------------------------------------------------------
    DOMAINS = {
        "integrity": [
            "must_have_pk", "pk_must_not_be_nullable", "fk_type_must_match",
            "no_fk_self_reference", "no_fk_cycles", "no_orphaned_fk",
            "no_fk_missing_ref_col", "must_enforce_fk", "no_without_rowid_no_pk",
            "no_autoincr_non_integer",
        ],
        "normalization": [
            "no_all_nullable", "no_single_column_tables", "no_composite_pk",
            "no_incrementing_columns", "no_csv_in_text", "no_wide_table",
            "no_column_spread",
        ],
        "performance": [
            "fk_must_have_index", "pk_must_be_first", "no_redundant_indexes",
            "no_duplicate_indexes", "no_nullable_in_unique",
            "no_index_too_many_cols", "no_over_indexed",
        ],
        "naming": [
            "no_reserved_words", "no_spaces_in_names", "no_bad_column_names",
            "no_string_null_default", "no_mixed_naming_case",
            "no_col_prefix_match_table", "no_bool_wrong_type",
            "no_timestamp_naming", "fk_must_have_id_suffix",
            "column_type_consistent",
        ],
    }

    # ------------------------------------------------------------------------
    # SCHEMA HEALTH SCORING — weights per severity
    # ------------------------------------------------------------------------
    SCORE_WEIGHTS = {
        "high": 10,
        "medium": 3,
        "low": 1,
    }
    SCORE_MAX = 100

    # ------------------------------------------------------------------------
    # ABOUT — short description for --about output
    # ------------------------------------------------------------------------
    ABOUT = (
        "Schema Lint Config v2.1 — 116 rules total (36 structural + 80 design). "
        "4 structural domains: integrity, normalization, performance, naming. "
        "7 design categories: schema_integrity, referential_integrity, "
        "indexing_performance, data_type, naming_metadata, normalization, "
        "engine_specific. Design rules are engine-tagged (SQLite / MySQL / both) "
        "with STRICT (engine-enforced) or GUIDELINE (best practice) severity. "
        "No AI, no learning, no external dependencies. Pure structural predicates."
    )

    # ------------------------------------------------------------------------
    # HELP — quick reference for --help output
    # ------------------------------------------------------------------------
    HELP = """
Schema Lint Config v2.1 — 116 Rules (36 structural + 80 design)

USAGE:
    python3 schema_lint_engine.py <database.db | schema.sql>
    schemalint <database.db | schema.sql> [--json] [--score]

STRUCTURAL RULE DOMAINS (36 rules, SQLite-focused, apply to both engines):
    integrity      (10 rules) — schema is valid
    normalization  ( 7 rules) — schema is well designed
    performance    ( 7 rules) — schema is query efficient
    naming         (10 rules) — schema is clean and maintainable
    optional       ( 2 rules) — disabled by default

DESIGN RULE CATEGORIES (80 rules, engine-tagged SQLite / MySQL / both):
    schema_integrity       (11 rules) — PK, UNIQUE, CHECK, NOT NULL, clustered
    referential_integrity  (26 rules) — FK constraints, actions, type matching
    indexing_performance   (12 rules) — composite indexes, PK width, prefixes
    data_type              (13 rules) — affinity, STRICT tables, MySQL types
    naming_metadata        ( 5 rules) — reserved names, identifiers, FK naming
    normalization          ( 6 rules) — 1NF/2NF/3NF/BCNF, junction tables
    engine_specific        ( 7 rules) — SQLite vs MySQL behavioral differences

SEVERITY:
    high / medium / low    — structural rules
    strict / guideline     — design rules (strict = engine-enforced error)

ENGINE TAGGING (design rules only):
    [sqlite]  — applies to SQLite only
    [mysql]   — applies to MySQL (InnoDB) only
    [both]    — applies identically to either engine

TO ADD A RULE:
    1. Add a tuple to Config.RULES or Config.DB_DESIGN_RULES
    2. If new check_type, add a check function to the engine

TO TOGGLE A RULE:
    Change True/False in the tuple

TO TUNE A THRESHOLD:
    Change the class attribute (e.g. MAX_LOB_COLUMNS = 1 → 3)
"""

    # ==========================================================================
    # DB_DESIGN_RULES — MySQL + SQLite schema design rules from official docs
    # --------------------------------------------------------------------------
    # These 80 rules are extracted from official SQLite and MySQL documentation.
    # Full sources and rationale: db_schema_rules.json / db_schema_rules.md
    # at the repository root.
    #
    # ENGINE TAGGING:
    #   Each rule carries an `engines` list — [ENGINE_SQLITE], [ENGINE_MYSQL],
    #   or [ENGINE_SQLITE, ENGINE_MYSQL]. Rules tagged ENGINE_MYSQL apply
    #   ONLY to MySQL (InnoDB). Rules tagged ENGINE_SQLITE apply ONLY to
    #   SQLite. Rules tagged both apply identically to either engine.
    #
    #   Where SQLite and MySQL behavior DIFFERS (FK default state, type
    #   enforcement, clustered index, SET DEFAULT support, ALTER capabilities),
    #   separate engine-specific rules are kept rather than merged.
    #
    # TUPLE FORMAT (extends RULES with an engines field):
    #   (id, description, severity, check_type, enabled, engines)
    #
    # SEVERITY:
    #   SEVERITY_STRICT    = engine-enforced (raises error at runtime)
    #   SEVERITY_GUIDELINE = documented best practice (not a hard error)
    # ==========================================================================

    DB_DESIGN_RULES = [
        # --- a. SCHEMA INTEGRITY ---
        ("SCHEMA-001", "Every table should have a primary key; use auto-increment surrogate if no logical unique non-null column",          SEVERITY_GUIDELINE, "every_table_has_pk",                  True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("SCHEMA-002", "INTEGER PRIMARY KEY is the rowid alias and auto-stores a unique 64-bit int (NULL becomes a new unique int)",        SEVERITY_STRICT,    "integer_pk_is_rowid_alias",           True,  [ENGINE_SQLITE]),
        ("SCHEMA-003", "PRIMARY KEY columns are implicitly NOT NULL in SQLite",                                                             SEVERITY_STRICT,    "sqlite_pk_implicit_not_null",         True,  [ENGINE_SQLITE]),
        ("SCHEMA-004", "UNIQUE rejects duplicate non-NULL values; multiple NULLs are distinct and all permitted",                           SEVERITY_STRICT,    "unique_nulls_distinct",               True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("SCHEMA-005", "CHECK must evaluate true or NULL for every row; cannot reference subqueries or other tables",                       SEVERITY_STRICT,    "check_no_subquery_or_other_table",    True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("SCHEMA-006", "NOT NULL rejects NULL on insert/update; column without DEFAULT and without NOT NULL defaults to NULL",             SEVERITY_STRICT,    "not_null_default_semantics",          True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("SCHEMA-007", "SQLite DEFAULT expression must be constant (no subqueries, column/table refs, bound params, double-quoted text)",  SEVERITY_STRICT,    "sqlite_default_must_be_constant",     True,  [ENGINE_SQLITE]),
        ("SCHEMA-008", "CREATE TABLE AS SELECT yields a table with no PK, no constraints, NULL defaults, BINARY collation",                 SEVERITY_STRICT,    "ctas_has_no_constraints",             True,  [ENGINE_SQLITE]),
        ("SCHEMA-009", "Without a PK, InnoDB uses the first all-NOT-NULL UNIQUE index as the clustered index",                              SEVERITY_STRICT,    "innodb_unique_fallback_clustered",    True,  [ENGINE_MYSQL]),
        ("SCHEMA-010", "Without PK or suitable UNIQUE index, InnoDB creates hidden GEN_CLUST_INDEX on a synthetic 6-byte row ID",           SEVERITY_STRICT,    "innodb_hidden_clustered_index",       True,  [ENGINE_MYSQL]),
        ("SCHEMA-011", "Primary key columns are implicitly NOT NULL in InnoDB",                                                             SEVERITY_STRICT,    "mysql_pk_implicit_not_null",          True,  [ENGINE_MYSQL]),

        # --- b. REFERENTIAL INTEGRITY ---
        ("REF-001", "SQLite FK constraints are OFF by default; enable per-connection with PRAGMA foreign_keys = ON",                        SEVERITY_STRICT,    "sqlite_fk_enabled_pragma",            True,  [ENGINE_SQLITE]),
        ("REF-002", "MySQL foreign_key_checks is ON by default; dynamic, global + session scope",                                           SEVERITY_STRICT,    "mysql_fk_checks_default_on",          True,  [ENGINE_MYSQL]),
        ("REF-003", "FK satisfied if any child key is NULL or matching parent row exists; add NOT NULL to forbid NULL child keys",          SEVERITY_STRICT,    "fk_null_satisfies_constraint",        True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("REF-004", "SQLite parent key must be PK or under a UNIQUE index with the same collations as the parent CREATE TABLE",             SEVERITY_STRICT,    "sqlite_parent_key_unique_collation",  True,  [ENGINE_SQLITE]),
        ("REF-005", "Composite FK parent and child keys must have identical cardinality",                                                   SEVERITY_STRICT,    "composite_fk_cardinality_match",      True,  [ENGINE_SQLITE]),
        ("REF-006", "Referencing a parent PK without naming columns requires parent PK column count to equal child key count",              SEVERITY_STRICT,    "sqlite_fk_unnamed_pk_count_match",    True,  [ENGINE_SQLITE]),
        ("REF-007", "An index on SQLite child key columns is strongly recommended to avoid linear scans on FK enforcement",                  SEVERITY_GUIDELINE, "sqlite_child_key_index_recommended",  True,  [ENGINE_SQLITE]),
        ("REF-008", "MySQL FK parent and child tables must use the same storage engine and cannot be temporary",                            SEVERITY_STRICT,    "mysql_fk_same_engine_no_temp",        True,  [ENGINE_MYSQL]),
        ("REF-009", "MySQL FK/referenced columns must have similar types; INTEGER/DECIMAL size+sign must match; string cols share charset", SEVERITY_STRICT,    "mysql_fk_column_type_match",          True,  [ENGINE_MYSQL]),
        ("REF-010", "MySQL requires an index where FK columns are first in order; auto-created if missing, may be silently dropped later",   SEVERITY_STRICT,    "mysql_fk_index_required",             True,  [ENGINE_MYSQL]),
        ("REF-011", "Referencing a non-unique index as MySQL FK parent key is deprecated; use PK or UNIQUE",                                SEVERITY_GUIDELINE, "mysql_fk_parent_must_be_unique",      True,  [ENGINE_MYSQL]),
        ("REF-012", "MySQL index prefixes on FK columns unsupported; BLOB/TEXT cannot be in a foreign key",                                 SEVERITY_STRICT,    "mysql_fk_no_blob_text_prefix",        True,  [ENGINE_MYSQL]),
        ("REF-013", "InnoDB disallows FKs on user-partitioned tables; NDB allows only KEY/LINEAR KEY partitioning",                         SEVERITY_STRICT,    "mysql_fk_no_user_partitioning",       True,  [ENGINE_MYSQL]),
        ("REF-014", "A MySQL table in a FK relationship cannot be ALTERed to another storage engine until FKs are dropped",                 SEVERITY_STRICT,    "mysql_fk_no_engine_change_with_fk",   True,  [ENGINE_MYSQL]),
        ("REF-015", "A MySQL FK cannot reference a virtual generated column",                                                               SEVERITY_STRICT,    "mysql_fk_no_virtual_generated_ref",   True,  [ENGINE_MYSQL]),
        ("REF-016", "A MySQL FK constraint name (CONSTRAINT symbol) must be unique in the database (duplicate -> errno 121)",               SEVERITY_STRICT,    "mysql_fk_name_unique_in_db",          True,  [ENGINE_MYSQL]),
        ("REF-017", "Referential actions allowed: NO ACTION (default), RESTRICT, CASCADE, SET NULL, SET DEFAULT",                           SEVERITY_STRICT,    "fk_referential_actions_allowed",      True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("REF-018", "Default referential action when none specified is NO ACTION",                                                          SEVERITY_STRICT,    "fk_default_action_no_action",         True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("REF-019", "InnoDB: NO ACTION == RESTRICT (immediate); NDB: NO ACTION is deferred to commit",                                      SEVERITY_STRICT,    "mysql_no_action_semantics",           True,  [ENGINE_MYSQL]),
        ("REF-020", "MySQL ON DELETE/UPDATE SET DEFAULT is parsed but rejected by InnoDB and NDB; do not use",                              SEVERITY_STRICT,    "mysql_no_set_default_action",         True,  [ENGINE_MYSQL]),
        ("REF-021", "With SET NULL, child key columns must not be declared NOT NULL",                                                       SEVERITY_GUIDELINE, "fk_set_null_child_not_null",          True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("REF-022", "SQLite RESTRICT is enforced immediately even when FK is DEFERRABLE INITIALLY DEFERRED",                                SEVERITY_STRICT,    "sqlite_restrict_immediate",           True,  [ENGINE_SQLITE]),
        ("REF-023", "SQLite ON DELETE SET DEFAULT still requires the default to match an existing parent row",                              SEVERITY_STRICT,    "sqlite_set_default_needs_parent",     True,  [ENGINE_SQLITE]),
        ("REF-024", "MySQL cascaded FK actions do not activate triggers",                                                                   SEVERITY_STRICT,    "mysql_cascade_no_trigger",            True,  [ENGINE_MYSQL]),
        ("REF-025", "MySQL FK on stored generated column restricts CASCADE/SET NULL/SET DEFAULT actions",                                   SEVERITY_STRICT,    "mysql_fk_generated_col_action_limit", True,  [ENGINE_MYSQL]),
        ("REF-026", "Do not define multiple ON UPDATE CASCADE clauses between the same two tables on the same column",                      SEVERITY_STRICT,    "mysql_no_duplicate_cascade",          True,  [ENGINE_MYSQL]),

        # --- c. INDEXING AND PERFORMANCE ---
        ("IDX-001", "Index columns used in WHERE, JOIN, ORDER BY, GROUP BY to avoid full table scans",                                      SEVERITY_GUIDELINE, "index_predicate_columns",             True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("IDX-002", "Order composite-index columns so the leftmost prefix matches query predicates; only leftmost prefix is usable",       SEVERITY_GUIDELINE, "composite_index_leftmost_prefix",     True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("IDX-003", "Avoid indexing low-cardinality or rarely-filtered columns; every index adds write + storage overhead",                 SEVERITY_GUIDELINE, "no_low_cardinality_index",            True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("IDX-004", "SQLite expression indexes may not reference other tables, subqueries, or non-deterministic functions",                 SEVERITY_STRICT,    "sqlite_expr_index_no_nondeterminism", True,  [ENGINE_SQLITE]),
        ("IDX-005", "Use SQLite partial indexes (WHERE clause) to index only relevant rows and shrink index size",                          SEVERITY_GUIDELINE, "sqlite_partial_index_recommended",    True,  [ENGINE_SQLITE]),
        ("IDX-006", "SQLite: no arbitrary per-table index limit; columns per index bounded by SQLITE_LIMIT_COLUMN",                         SEVERITY_STRICT,    "sqlite_index_column_limit",           True,  [ENGINE_SQLITE]),
        ("IDX-007", "SQLite NULLS FIRST/LAST unsupported in indexes; NULLs sort smallest",                                                  SEVERITY_STRICT,    "sqlite_no_nulls_first_last_index",    True,  [ENGINE_SQLITE]),
        ("IDX-008", "InnoDB secondary indexes store the PK value, not a row pointer; keep PK narrow",                                       SEVERITY_GUIDELINE, "innodb_keep_pk_narrow",               True,  [ENGINE_MYSQL]),
        ("IDX-009", "Use a short, monotonically increasing PK for InnoDB to reduce page splits and fragmentation",                          SEVERITY_GUIDELINE, "innodb_short_monotonic_pk",           True,  [ENGINE_MYSQL]),
        ("IDX-010", "MySQL index prefixes supported for CHAR/VARCHAR/BINARY/VARBINARY/TEXT/BLOB; TEXT/BLOB indexes need prefix length",     SEVERITY_STRICT,    "mysql_text_blob_index_prefix",        True,  [ENGINE_MYSQL]),
        ("IDX-011", "Defining FKs on MySQL join columns ensures they are indexed and improves join performance",                            SEVERITY_GUIDELINE, "mysql_fk_on_join_columns",            True,  [ENGINE_MYSQL]),
        ("IDX-012", "Dropping a MySQL index required by an FK is rejected; drop the FK first",                                              SEVERITY_STRICT,    "mysql_no_drop_fk_index",              True,  [ENGINE_MYSQL]),

        # --- d. DATA TYPE ---
        ("DT-001", "SQLite dynamic typing: any column (except INTEGER PRIMARY KEY) can store NULL/INTEGER/REAL/TEXT/BLOB; type sets affinity",  SEVERITY_STRICT,  "sqlite_dynamic_typing",               True,  [ENGINE_SQLITE]),
        ("DT-002", "SQLite affinity rules (ordered): INT->INTEGER; CHAR/CLOB/TEXT->TEXT; BLOB/no type->BLOB; REAL/FLOA/DOUB->REAL; else NUMERIC", SEVERITY_STRICT, "sqlite_affinity_rules",          True,  [ENGINE_SQLITE]),
        ("DT-003", "SQLite has no native BOOLEAN; booleans stored as INTEGER 0/1; TRUE/FALSE are aliases for 1/0",                          SEVERITY_STRICT,    "sqlite_no_native_boolean",            True,  [ENGINE_SQLITE]),
        ("DT-004", "SQLite has no native DATE/TIME; store as TEXT (ISO8601), REAL (Julian), or INTEGER (Unix). Pick one per column",        SEVERITY_GUIDELINE, "sqlite_datetime_format_consistent",   True,  [ENGINE_SQLITE]),
        ("DT-005", "SQLite STRICT table: every column must declare a type from {INT,INTEGER,REAL,TEXT,BLOB,ANY}; other names are errors",    SEVERITY_STRICT,    "sqlite_strict_table_types",           True,  [ENGINE_SQLITE]),
        ("DT-006", "SQLite STRICT table: non-losslessly-coercible value raises SQLITE_CONSTRAINT_DATATYPE; ANY accepts any value",          SEVERITY_STRICT,    "sqlite_strict_datatype_error",        True,  [ENGINE_SQLITE]),
        ("DT-007", "SQLite STRICT table: INT PRIMARY KEY is NOT a rowid alias; only INTEGER PRIMARY KEY is",                                SEVERITY_STRICT,    "sqlite_strict_int_pk_not_rowid",      True,  [ENGINE_SQLITE]),
        ("DT-008", "MySQL enforces static typing: numeric, date/time, string, spatial, JSON categories",                                    SEVERITY_STRICT,    "mysql_static_typing",                 True,  [ENGINE_MYSQL]),
        ("DT-009", "MySQL DECIMAL/NUMERIC: M=precision, D=scale; D <= M-2 and D <= 30",                                                     SEVERITY_STRICT,    "mysql_decimal_precision_scale",       True,  [ENGINE_MYSQL]),
        ("DT-010", "MySQL fsp for TIME/DATETIME/TIMESTAMP is 0-6; default 0 (not SQL standard 6)",                                          SEVERITY_STRICT,    "mysql_fsp_range",                     True,  [ENGINE_MYSQL]),
        ("DT-011", "Use the smallest MySQL type that reliably holds the range (TINYINT vs BIGINT, DATE vs DATETIME)",                       SEVERITY_GUIDELINE, "mysql_smallest_type",                 True,  [ENGINE_MYSQL]),
        ("DT-012", "Use FLOAT/DOUBLE for approximate values; DECIMAL/NUMERIC for exact monetary/counted values",                            SEVERITY_GUIDELINE, "mysql_exact_vs_approx_numeric",       True,  [ENGINE_MYSQL]),
        ("DT-013", "MySQL TIMESTAMP converts session-TZ<->UTC on store/retrieval; DATETIME stores literally with no TZ conversion",         SEVERITY_STRICT,    "mysql_timestamp_tz_conversion",       True,  [ENGINE_MYSQL]),

        # --- e. NAMING AND METADATA ---
        ("NAM-001", "SQLite table names starting with 'sqlite_' are reserved; creating one is an error",                                    SEVERITY_STRICT,    "sqlite_no_sqlite_prefix",             True,  [ENGINE_SQLITE]),
        ("NAM-002", "CREATE TABLE fails on same-name table/index/view unless IF NOT EXISTS; IF NOT EXISTS does not suppress index errors",  SEVERITY_STRICT,    "create_table_if_not_exists_semantics",True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("NAM-003", "MySQL identifier case sensitivity depends on lower_case_table_names; backtick-quote (or double-quote under ANSI_QUOTES)", SEVERITY_STRICT,  "mysql_identifier_case",               True,  [ENGINE_MYSQL]),
        ("NAM-004", "Use consistent descriptive snake_case identifiers; avoid SQL reserved keywords as identifiers",                        SEVERITY_GUIDELINE, "consistent_snake_case_identifiers",   True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("NAM-005", "Name FK constraints explicitly (CONSTRAINT symbol) for reliable drop/error references",                                SEVERITY_GUIDELINE, "explicit_fk_constraint_names",        True,  [ENGINE_SQLITE, ENGINE_MYSQL]),

        # --- f. NORMALIZATION (engine-agnostic relational theory) ---
        ("NORM-001", "1NF: every column holds atomic single-valued values; no repeating groups or arrays",                                  SEVERITY_GUIDELINE, "nf1_atomic_columns",                  True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("NORM-002", "2NF: no non-prime attribute depends on only a proper subset of a composite candidate key",                            SEVERITY_GUIDELINE, "nf2_no_partial_key_dep",              True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("NORM-003", "3NF: no non-prime attribute transitively dependent on a candidate key",                                               SEVERITY_GUIDELINE, "nf3_no_transitive_dep",               True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("NORM-004", "BCNF: every non-trivial FD X->Y has X as a superkey; every determinant is a candidate key",                           SEVERITY_GUIDELINE, "bcnf_every_determinant_is_superkey",  True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("NORM-005", "Model M:N relationships with a junction table carrying FKs to both sides; never embedded lists",                      SEVERITY_GUIDELINE, "m_to_n_junction_table",               True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("NORM-006", "Denormalize for read performance only after 3NF/BCNF and only with documented justification",                         SEVERITY_GUIDELINE, "denormalize_only_with_justification", True,  [ENGINE_SQLITE, ENGINE_MYSQL]),

        # --- g. ENGINE-SPECIFIC DIFFERENCES (SQLite vs MySQL) ---
        ("ENG-001", "SQLite FKs OFF by default vs MySQL ON by default; flag SQLite schemas defining FKs without enabling PRAGMA",           SEVERITY_GUIDELINE, "fk_default_state_divergence",         True,  [ENGINE_SQLITE]),
        ("ENG-002", "Type enforcement differs: SQLite coerces by affinity, MySQL enforces types; use STRICT tables or INT/REAL/TEXT/BLOB",  SEVERITY_GUIDELINE, "type_enforcement_portability",        True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("ENG-003", "Boolean/datetime types differ: SQLite has no native BOOLEAN/DATE/TIME; MySQL has native DATE/DATETIME/TIMESTAMP/etc",  SEVERITY_GUIDELINE, "boolean_datetime_type_portability",   True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("ENG-004", "InnoDB stores row data in the clustered index (PK); all secondary indexes embed the PK",                               SEVERITY_STRICT,    "innodb_clustered_index_design",       True,  [ENGINE_MYSQL]),
        ("ENG-005", "SQLite has no per-table storage engine and no clustered index; INTEGER PRIMARY KEY rowid is the closest analog",       SEVERITY_STRICT,    "sqlite_no_clustered_index",           True,  [ENGINE_SQLITE]),
        ("ENG-006", "ALTER TABLE differs: SQLite supports only rename/add/rename/drop column; MySQL supports full ALTER including FK",      SEVERITY_GUIDELINE, "alter_table_capability_gap",          True,  [ENGINE_SQLITE, ENGINE_MYSQL]),
        ("ENG-007", "Use ENGINE=InnoDB (default) for transactional FK-critical schemas; other engines lack FK support/crash safety",        SEVERITY_GUIDELINE, "prefer_innodb_engine",                True,  [ENGINE_MYSQL]),
    ]

    # ------------------------------------------------------------------------
    # DB_DESIGN_DOMAINS — 7 categories for documentation and reporting
    # ------------------------------------------------------------------------
    DB_DESIGN_DOMAINS = {
        "schema_integrity": [
            "SCHEMA-001", "SCHEMA-002", "SCHEMA-003", "SCHEMA-004", "SCHEMA-005",
            "SCHEMA-006", "SCHEMA-007", "SCHEMA-008", "SCHEMA-009", "SCHEMA-010",
            "SCHEMA-011",
        ],
        "referential_integrity": [
            "REF-001", "REF-002", "REF-003", "REF-004", "REF-005", "REF-006",
            "REF-007", "REF-008", "REF-009", "REF-010", "REF-011", "REF-012",
            "REF-013", "REF-014", "REF-015", "REF-016", "REF-017", "REF-018",
            "REF-019", "REF-020", "REF-021", "REF-022", "REF-023", "REF-024",
            "REF-025", "REF-026",
        ],
        "indexing_performance": [
            "IDX-001", "IDX-002", "IDX-003", "IDX-004", "IDX-005", "IDX-006",
            "IDX-007", "IDX-008", "IDX-009", "IDX-010", "IDX-011", "IDX-012",
        ],
        "data_type": [
            "DT-001", "DT-002", "DT-003", "DT-004", "DT-005", "DT-006", "DT-007",
            "DT-008", "DT-009", "DT-010", "DT-011", "DT-012", "DT-013",
        ],
        "naming_metadata": [
            "NAM-001", "NAM-002", "NAM-003", "NAM-004", "NAM-005",
        ],
        "normalization": [
            "NORM-001", "NORM-002", "NORM-003", "NORM-004", "NORM-005", "NORM-006",
        ],
        "engine_specific": [
            "ENG-001", "ENG-002", "ENG-003", "ENG-004", "ENG-005", "ENG-006", "ENG-007",
        ],
    }

    # ------------------------------------------------------------------------
    # DB_DESIGN_SCORE_WEIGHTS — weights per severity for design rules
    # ------------------------------------------------------------------------
    DB_DESIGN_SCORE_WEIGHTS = {
        SEVERITY_STRICT: 10,
        SEVERITY_GUIDELINE: 3,
    }

    # ------------------------------------------------------------------------
    # ALL_RULES — legacy RULES (5-tuple) + DB_DESIGN_RULES (6-tuple),
    # normalized to 6-tuples by adding engines=[ENGINE_SQLITE, ENGINE_MYSQL]
    # to legacy rules (they were SQLite-focused but apply structurally to both).
    # ------------------------------------------------------------------------
    ALL_RULES = [
        (*r, ["sqlite", "mysql"]) for r in RULES
    ] + DB_DESIGN_RULES

    # ==========================================================================
    # AUTO_FIXABLE_RULES — 14 rules with mechanical, no-reasoning fixes
    # --------------------------------------------------------------------------
    # These rules have exactly one obvious fix. No decision tree needed.
    # The engine can auto-generate the fix SQL without human input.
    #
    # Format: (rule_id, check_type, fix_type, fix_action)
    #   fix_type   = "rename" | "drop" | "create" | "alter" | "pragma"
    #   fix_action = template string the engine fills in
    # ==========================================================================

    AUTO_FIXABLE_RULES = [
        ("fk_must_have_id_suffix",       "fk_column_must_have_id_suffix",   "rename", "ALTER TABLE {table} RENAME COLUMN {column} TO {column}_id;"),
        ("no_bad_column_names",          "no_bad_column_names",             "rename", "ALTER TABLE {table} RENAME COLUMN {column} TO {table}_ID;"),
        ("no_spaces_in_names",           "name_must_not_contain_spaces",    "rename", "ALTER TABLE {table} RENAME COLUMN {column} TO {column_underscore};"),
        ("no_string_null_default",       "no_string_null_default",          "alter",  "ALTER TABLE {table} RENAME COLUMN {column} TO {column}_tmp; ALTER TABLE {table} ADD COLUMN {column} {type} NOT NULL DEFAULT {real_default};"),
        ("no_column_prefix_match_table", "no_column_prefix_match_table",    "rename", "ALTER TABLE {table} RENAME COLUMN {column} TO {stripped};"),
        ("no_duplicate_indexes",         "no_duplicate_indexes",            "drop",   "DROP INDEX {index_name};"),
        ("no_redundant_indexes",         "no_redundant_indexes",            "drop",   "DROP INDEX {index_name};"),
        ("fk_must_have_index",           "fk_must_have_index",              "create", "CREATE INDEX idx_{table}_{column} ON {table}({column});"),
        ("no_bool_wrong_type",           "no_boolean_without_prefix",       "alter",  "ALTER TABLE {table} RENAME COLUMN {column} TO {column}_tmp; ALTER TABLE {table} ADD COLUMN {column} INTEGER;"),
        ("no_timestamp_naming",          "no_timestamp_naming",             "rename", "ALTER TABLE {table} RENAME COLUMN {column} TO created_at;"),
        ("no_autoincr_non_integer",      "no_autoincrement_non_integer",    "alter",  "-- Recreate table with INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("must_enforce_fk",              "must_enforce_foreign_keys",       "pragma", "PRAGMA foreign_keys = ON;"),
        ("no_reserved_words",            "name_must_not_be_in_list",        "rename", "ALTER TABLE {table} RENAME COLUMN {column} TO {column}_col;"),
        ("NAM-001",                      "sqlite_no_sqlite_prefix",         "rename", "ALTER TABLE {table} RENAME TO {table}_tbl;"),
    ]

    # ==========================================================================
    # DECISION_TREE_RULES — remaining rules need if/then/else logic
    # --------------------------------------------------------------------------
    # These rules cannot be auto-fixed because the fix depends on context.
    # Each will get a decision tree: condition → branch → fix.
    # To be implemented in the C engine as per-rule branching logic.
    #
    # Example decision tree for no_fk_cycles:
    #   IF cycle has 2 tables:
    #     → remove the FK on the less-critical table
    #   ELSE IF cycle has 3+ tables:
    #     → introduce a junction table to break the cycle
    #   ELSE:
    #     → flag for human review
    #
    # Example decision tree for no_too_many_lobs:
    #   IF table has > 5 TEXT columns:
    #     → split into parent + detail table
    #   ELSE IF table has 2-5 TEXT columns:
    #     → check if any can be normalized to a lookup table
    #   ELSE:
    #     → may be intentional (code storage), disable rule for this table
    #
    # Example decision tree for must_have_pk:
    #   IF table has a single unique non-null column:
    #     → make it the PRIMARY KEY
    #   ELSE IF table has no unique column:
    #     → add INTEGER PRIMARY KEY surrogate
    #   ELSE IF table has composite unique:
    #     → add INTEGER PRIMARY KEY surrogate, keep unique as constraint
    # ==========================================================================

    # ==========================================================================
    # DECISION_TREES — full if/then/else logic for each contextual rule
    # --------------------------------------------------------------------------
    # Format: (rule_id, [branches])
    #   branch = (condition, action, fix_sql_template)
    #   condition = string the C engine evaluates against schema metadata
    #   action    = human-readable description of what this branch does
    #   fix_sql   = template with {placeholders} the engine fills in
    #
    # The engine evaluates branches top-to-bottom. First match wins.
    # If no branch matches → flag for human review.
    # ==========================================================================

    DECISION_TREES = [
        ("must_have_pk", [
            ("table has single unique non-null column",
             "Make that column the PRIMARY KEY",
             "ALTER TABLE {table} RENAME TO {table}_old; CREATE TABLE {table} ({column} {type} PRIMARY KEY, ...); -- migrate data"),
            ("table has no unique column at all",
             "Add INTEGER PRIMARY KEY surrogate",
             "ALTER TABLE {table} ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;"),
            ("table has composite unique index",
             "Add surrogate PK, keep unique as constraint",
             "ALTER TABLE {table} ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT; -- unique index already enforces business key"),
        ]),

        ("pk_must_not_be_nullable", [
            ("column is INTEGER PRIMARY KEY (SQLite rowid alias)",
             "No fix needed — SQLite auto-assigns, PRAGMA reports nullable but it is not",
             "-- false positive: INTEGER PRIMARY KEY is never truly nullable in SQLite"),
            ("column is TEXT or other non-INTEGER PK",
             "Add NOT NULL to the PK column",
             "ALTER TABLE {table} RENAME TO {table}_old; CREATE TABLE {table} ({column} {type} NOT NULL PRIMARY KEY, ...); -- migrate data"),
        ]),

        ("fk_type_must_match", [
            ("child column type is TEXT, parent PK is INTEGER",
             "Change child column to INTEGER to match parent PK",
             "ALTER TABLE {table} RENAME COLUMN {column} TO {column}_tmp; ALTER TABLE {table} ADD COLUMN {column} INTEGER; UPDATE {table} SET {column} = CAST({column}_tmp AS INTEGER);"),
            ("child column type is INTEGER, parent PK is TEXT",
             "Change child column to TEXT to match parent PK",
             "ALTER TABLE {table} RENAME COLUMN {column} TO {column}_tmp; ALTER TABLE {table} ADD COLUMN {column} TEXT; UPDATE {table} SET {column} = CAST({column}_tmp AS TEXT);"),
            ("types differ but both are integer-family (INT vs BIGINT)",
             "No fix needed — integer-family types are compatible",
             "-- acceptable: INT and BIGINT are interchangeable for FK purposes"),
        ]),

        ("no_fk_self_reference", [
            ("table self-references its own PK as FK",
             "Remove the self-referencing FK — model the relationship differently",
             "ALTER TABLE {table} DROP FOREIGN KEY({fk_name}); -- or recreate table without self-FK"),
            ("self-reference is intentional (tree/hierarchy structure)",
             "Keep FK but add a CHECK constraint to prevent root-level cycles",
             "-- keep self-FK for hierarchy; add app-level cycle prevention"),
        ]),

        ("no_fk_cycles", [
            ("cycle involves exactly 2 tables",
             "Remove the FK on the less-critical table (the one that is more often written to)",
             "ALTER TABLE {table} DROP FOREIGN KEY({fk_name}); -- break A→B→A cycle"),
            ("cycle involves 3+ tables",
             "Introduce a junction table to break the cycle",
             "CREATE TABLE {junction} (id INTEGER PRIMARY KEY, {col_a} INTEGER, {col_b} INTEGER, FOREIGN KEY({col_a}) REFERENCES {table_a}, FOREIGN KEY({col_b}) REFERENCES {table_b}); -- remove direct FKs"),
            ("cycle is intentional (mutual dependency by design)",
             "Keep both FKs but make one DEFERRABLE INITIALLY DEFERRED",
             "-- keep cycle; make one FK DEFERRABLE to allow insert order"),
        ]),

        ("no_orphaned_fk", [
            ("FK references a table that does not exist in schema",
             "Either create the missing parent table or drop the FK",
             "CREATE TABLE {ref_table} (...); -- OR: ALTER TABLE {table} DROP FOREIGN KEY({fk_name});"),
            ("FK table name has a typo or case mismatch",
             "Fix the FK to reference the correct table name",
             "ALTER TABLE {table} DROP FOREIGN KEY({fk_name}); ALTER TABLE {table} ADD FOREIGN KEY({column}) REFERENCES {correct_table}({ref_col});"),
        ]),

        ("no_fk_missing_ref_col", [
            ("referenced column does not exist on parent table",
             "Either add the column to the parent or fix the FK to reference an existing column",
             "ALTER TABLE {ref_table} ADD COLUMN {ref_col} {type}; -- OR: fix FK to reference {existing_col}"),
            ("referenced column exists but is not PK or UNIQUE",
             "Add a UNIQUE index on the referenced column",
             "CREATE UNIQUE INDEX idx_{ref_table}_{ref_col} ON {ref_table}({ref_col});"),
        ]),

        ("no_without_rowid_no_pk", [
            ("table is WITHOUT ROWID and has no PK",
             "Either add a PRIMARY KEY or remove WITHOUT ROWID",
             "ALTER TABLE {table} RENAME TO {table}_old; CREATE TABLE {table} (...) PRIMARY KEY({column}); -- or remove WITHOUT ROWID"),
        ]),

        ("no_all_nullable", [
            ("all non-PK columns are nullable and table has no NOT NULL columns",
             "Add NOT NULL to at least one business-critical column",
             "ALTER TABLE {table} RENAME COLUMN {column} TO {column}_tmp; ALTER TABLE {table} ADD COLUMN {column} {type} NOT NULL; -- pick the most critical column"),
            ("table is a pure link/junction table where nullability is intentional",
             "Add NOT NULL to the FK columns at minimum",
             "ALTER TABLE {table} RENAME COLUMN {fk_col} TO {fk_col}_tmp; ALTER TABLE {table} ADD COLUMN {fk_col} INTEGER NOT NULL;"),
        ]),

        ("no_single_column_tables", [
            ("table has only 1 column and it is the PK",
             "This is likely a lookup/enum table — add a name/label column",
             "ALTER TABLE {table} ADD COLUMN name TEXT NOT NULL;"),
            ("table has only 1 column and it is not a PK",
             "Add a PK and a meaningful second column",
             "ALTER TABLE {table} ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;"),
        ]),

        ("no_composite_pk", [
            ("composite PK is on a junction/link table",
             "Keep composite PK — this is the correct pattern for junction tables",
             "-- acceptable: composite PK on junction table is standard practice"),
            ("composite PK is on a regular entity table",
             "Add a surrogate INTEGER PRIMARY KEY, demote composite to UNIQUE constraint",
             "ALTER TABLE {table} ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT; CREATE UNIQUE INDEX idx_{table}_business_key ON {table}({col1}, {col2});"),
        ]),

        ("no_incrementing_columns", [
            ("columns are col1, col2, col3, col4 (sequential numbering)",
             "Rename to meaningful names based on their actual purpose",
             "ALTER TABLE {table} RENAME COLUMN {old_name} TO {meaningful_name};"),
            ("columns are genuinely numbered (e.g. address_line_1, address_line_2)",
             "Keep names — numbered suffix is intentional for repeated fields",
             "-- acceptable: numbered suffix is meaningful for repeated attributes"),
        ]),

        ("no_csv_in_text", [
            ("column name contains _list, _ids, _csv, _tags and stores delimited values",
             "Create a junction table to normalize the 1:N relationship",
             "CREATE TABLE {table}_{tag} ({table}_id INTEGER, {tag}_value TEXT, FOREIGN KEY({table}_id) REFERENCES {table}(id));"),
            ("column name contains _tags but stores a single tag value",
             "Rename the column to remove the plural/list indicator",
             "ALTER TABLE {table} RENAME COLUMN {column} TO {singular_name};"),
        ]),

        ("no_wide_table", [
            ("table has > 30 columns",
             "Split into parent + child table grouping related columns",
             "CREATE TABLE {table}_detail ({table}_id INTEGER, {grouped_cols}); -- move related columns to detail table"),
            ("table has > 30 columns but all are needed in one row (wide entity)",
             "Keep table but document the justification",
             "-- acceptable: wide entity by design (e.g. configuration table)"),
        ]),

        ("no_column_spread", [
            ("column appears in 3+ tables and is an audit column (created_at, updated_at)",
             "No fix needed — audit columns are expected in every table",
             "-- acceptable: audit columns (created_at, updated_at) are intentionally spread"),
            ("column appears in 3+ tables with same name but different meaning",
             "Rename the column in each table to reflect its actual meaning",
             "ALTER TABLE {table} RENAME COLUMN {column} TO {table}_{column};"),
            ("column appears in 3+ tables with same name and same meaning (denormalization)",
             "Move to a shared lookup table and use FK references",
             "CREATE TABLE {lookup} (id INTEGER PRIMARY KEY, {column} {type}); -- replace spread columns with FK"),
        ]),

        ("no_nullable_in_unique", [
            ("column in unique index is nullable and should not be",
             "Add NOT NULL to the column",
             "ALTER TABLE {table} RENAME COLUMN {column} TO {column}_tmp; ALTER TABLE {table} ADD COLUMN {column} {type} NOT NULL; UPDATE {table} SET {column} = {column}_tmp;"),
            ("column is intentionally nullable (partial uniqueness is desired)",
             "Use a partial index instead of a full unique index",
             "DROP INDEX {index_name}; CREATE UNIQUE INDEX {index_name} ON {table}({column}) WHERE {column} IS NOT NULL;"),
        ]),

        ("no_index_too_many_cols", [
            ("index has > 4 columns",
             "Drop the index and create a narrower one on the most selective columns",
             "DROP INDEX {index_name}; CREATE INDEX {index_name}_narrow ON {table}({col1}, {col2});"),
            ("all columns in the index are genuinely needed for query predicates",
             "Keep index but document the justification",
             "-- acceptable: all columns are used in query predicates"),
        ]),

        ("no_over_indexed", [
            ("table has more indexes than columns",
             "Drop indexes that are not used by any query — keep PK and FK indexes",
             "DROP INDEX {index_name}; -- keep only PK, unique, and FK indexes"),
            ("table has many indexes but all serve distinct query patterns",
             "Keep indexes but document the justification",
             "-- acceptable: each index serves a distinct query pattern"),
        ]),

        ("no_mixed_naming_case", [
            ("some columns use snake_case, others use camelCase",
             "Rename all camelCase columns to snake_case for consistency",
             "ALTER TABLE {table} RENAME COLUMN {camel} TO {snake};"),
            ("some columns use PascalCase (likely from an ORM or code generator)",
             "Rename all PascalCase columns to snake_case",
             "ALTER TABLE {table} RENAME COLUMN {pascal} TO {snake};"),
        ]),

        ("column_type_consistent", [
            ("same column name has INTEGER in one table and TEXT in another",
             "Align to the type used by the majority of tables",
             "ALTER TABLE {minority_table} RENAME COLUMN {column} TO {column}_tmp; ALTER TABLE {minority_table} ADD COLUMN {column} {majority_type};"),
            ("types differ because the columns have different meanings despite same name",
             "Rename the column in one table to clarify its distinct meaning",
             "ALTER TABLE {table} RENAME COLUMN {column} TO {table}_{column};"),
        ]),

        ("pk_must_be_first", [
            ("PK column is not the first column declared in CREATE TABLE",
             "Recreate table with PK column first (column order matters for readability)",
             "ALTER TABLE {table} RENAME TO {table}_old; CREATE TABLE {table} ({pk_col} {pk_type} PRIMARY KEY, ...rest...); -- migrate data"),
            ("PK is composite and first column is not the most selective",
             "Reorder composite PK so most selective column is first",
             "ALTER TABLE {table} RENAME TO {table}_old; CREATE TABLE {table} ({most_selective_col} {type}, {second_col} {type}, PRIMARY KEY({most_selective_col}, {second_col}), ...); -- migrate data"),
        ]),
    ]
