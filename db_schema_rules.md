# Relational Database Schema Design Rules — SQLite & MySQL

**Version:** 1.0.0 · **Generated:** 2026-06-21

A unified, atomic rule set for relational schema design in **SQLite** and **MySQL**, extracted from
official documentation and supplemented with established relational theory. Each rule is intended to
be directly implementable in a rule engine or linter.

## Severity legend

| Severity   | Meaning                                                                                  |
|------------|------------------------------------------------------------------------------------------|
| `STRICT`   | Engine-enforced. Violation raises an error or is impossible at runtime.                 |
| `GUIDELINE`| Documented best practice / recommendation. Not enforced as a hard error by the engine.  |

## Source legend

- **SQLite**: `https://www.sqlite.org/...`
- **MySQL**: `https://dev.mysql.com/doc/refman/8.4/en/...`
- **Theory**: Wikipedia summaries of Codd/Boyce-Codd normalization (cite the original papers).

---

## a. Schema integrity rules

| ID         | Engines        | Severity   | Rule                                                                                                                                                       | Source |
|------------|----------------|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| SCHEMA-001 | sqlite, mysql  | GUIDELINE  | Every table should have a primary key; if no logical unique non-null column exists, use an auto-increment surrogate key.                                  | [InnoDB index types][1], [InnoDB best practices][2], [SQLite CREATE TABLE][3] |
| SCHEMA-002 | sqlite         | STRICT     | An `INTEGER PRIMARY KEY` column is an alias for the rowid and stores a unique 64-bit signed integer automatically; `NULL` is converted to a new unique integer. Only `INTEGER` (not `INT`) is the rowid alias. | [SQLite CREATE TABLE][3], [SQLite STRICT][4] |
| SCHEMA-003 | sqlite         | STRICT     | PRIMARY KEY columns are implicitly `NOT NULL` (`NULL` into `INTEGER PRIMARY KEY` is auto-converted).                                                      | [SQLite STRICT][4] |
| SCHEMA-004 | sqlite, mysql  | STRICT     | `UNIQUE` rejects duplicate non-NULL values; multiple NULLs are distinct and all permitted (NULLS-distinct interpretation).                                | [SQLite CREATE INDEX][5], [MySQL CREATE TABLE][6] |
| SCHEMA-005 | sqlite, mysql  | STRICT     | `CHECK` must evaluate true or NULL for every row; false rejects the row. `CHECK` cannot reference subqueries or other tables.                             | [SQLite CREATE TABLE][3], [MySQL CHECK][7] |
| SCHEMA-006 | sqlite, mysql  | STRICT     | `NOT NULL` rejects NULL on insert/update; a column with no explicit DEFAULT and no NOT NULL defaults to NULL.                                             | [SQLite CREATE TABLE][3], [MySQL defaults][8] |
| SCHEMA-007 | sqlite         | STRICT     | A `DEFAULT` expression is constant only if it has no subqueries, column/table refs, bound parameters, or double-quoted string literals; else rejected.   | [SQLite CREATE TABLE][3] |
| SCHEMA-008 | sqlite         | STRICT     | `CREATE TABLE ... AS SELECT` produces a table with no PK, no constraints, NULL defaults, BINARY collation.                                                | [SQLite CREATE TABLE][3] |
| SCHEMA-009 | mysql          | STRICT     | With no PK, InnoDB uses the first `UNIQUE` index whose key columns are all `NOT NULL` as the clustered index.                                             | [InnoDB index types][1] |
| SCHEMA-010 | mysql          | STRICT     | With no PK and no suitable all-NOT-NULL UNIQUE index, InnoDB creates a hidden clustered index `GEN_CLUST_INDEX` on a synthetic 6-byte row ID.             | [InnoDB index types][1] |
| SCHEMA-011 | mysql          | STRICT     | Primary key columns are implicitly `NOT NULL` in InnoDB.                                                                                                  | [MySQL CREATE TABLE][6] |

## b. Referential integrity rules

| ID       | Engines        | Severity   | Rule                                                                                                                                                       | Source |
|----------|----------------|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| REF-001  | sqlite         | STRICT     | FK constraints are **disabled by default**; enable per-connection with `PRAGMA foreign_keys = ON`. Cannot be toggled inside a multi-statement transaction. | [SQLite FK][9] |
| REF-002  | mysql          | STRICT     | FK checking is enabled by default (`foreign_key_checks=ON`); dynamic, global + session scope.                                                             | [MySQL FK][10] |
| REF-003  | sqlite, mysql  | STRICT     | A FK is satisfied if any child key column is NULL, or a matching parent row exists; add `NOT NULL` on child column(s) to forbid NULL child keys.          | [SQLite FK][9], [MySQL FK][10] |
| REF-004  | sqlite         | STRICT     | The parent key must be the PK or collectively under a `UNIQUE` constraint/index using the same collations declared in the parent `CREATE TABLE`.          | [SQLite FK][9] |
| REF-005  | sqlite         | STRICT     | Composite FK parent and child keys must have identical cardinality.                                                                                       | [SQLite FK][9] |
| REF-006  | sqlite         | STRICT     | Referencing a parent PK without naming columns requires the parent PK column count to equal the child key column count.                                   | [SQLite FK][9] |
| REF-007  | sqlite         | GUIDELINE  | An index on the child key columns is not required but strongly recommended; without it, FK enforcement does a linear scan of the child table.             | [SQLite FK][9] |
| REF-008  | mysql          | STRICT     | Parent and child tables must use the same storage engine and cannot be temporary.                                                                         | [MySQL FK][10] |
| REF-009  | mysql          | STRICT     | Corresponding FK/referenced columns must have similar types; for `INTEGER`/`DECIMAL` size and sign must match; nonbinary string columns must share charset and collation (length may differ). | [MySQL FK][10] |
| REF-010  | mysql          | STRICT     | An index where the FK columns are the first columns (same order) is required; it is auto-created if missing and may be silently dropped if a later index serves the FK. | [MySQL FK][10] |
| REF-011  | mysql          | GUIDELINE  | Referencing a non-unique index as parent key is deprecated (needs `restrict_fk_on_non_standard_key`); use PK or UNIQUE.                                    | [MySQL FK][10] |
| REF-012  | mysql          | STRICT     | Index prefixes on FK columns are unsupported, so `BLOB`/`TEXT` cannot be in a foreign key.                                                                | [MySQL FK][10] |
| REF-013  | mysql          | STRICT     | InnoDB disallows FKs on user-partitioned tables (parent or child); NDB allows only KEY/LINEAR KEY partitioning.                                            | [MySQL FK][10] |
| REF-014  | mysql          | STRICT     | A table in a FK relationship cannot be `ALTER`ed to another storage engine until the FK constraints are dropped.                                          | [MySQL FK][10] |
| REF-015  | mysql          | STRICT     | A FK cannot reference a virtual generated column.                                                                                                         | [MySQL FK][10] |
| REF-016  | mysql          | STRICT     | A FK constraint name (`CONSTRAINT symbol`) must be unique in the database; duplicate → errno 121.                                                         | [MySQL FK][10] |
| REF-017  | sqlite, mysql  | STRICT     | Referential actions: `NO ACTION` (default), `RESTRICT`, `CASCADE`, `SET NULL`, `SET DEFAULT`.                                                            | [SQLite FK][9], [MySQL FK][10] |
| REF-018  | sqlite, mysql  | STRICT     | Default action when none specified is `NO ACTION`.                                                                                                        | [SQLite FK][9], [MySQL FK][10] |
| REF-019  | mysql          | STRICT     | For InnoDB, `NO ACTION` == `RESTRICT` (immediate). NDB treats `NO ACTION` as deferred (commit-time).                                                     | [MySQL FK][10] |
| REF-020  | mysql          | STRICT     | `ON DELETE/UPDATE SET DEFAULT` is parsed but rejected by InnoDB and NDB — do not use.                                                                     | [MySQL FK][10] |
| REF-021  | sqlite, mysql  | GUIDELINE  | With `SET NULL`, child key columns must not be `NOT NULL`.                                                                                                | [MySQL FK][10], [SQLite FK][9] |
| REF-022  | sqlite         | STRICT     | `RESTRICT` is enforced immediately even when the FK is `DEFERRABLE INITIALLY DEFERRED`.                                                                   | [SQLite FK][9] |
| REF-023  | sqlite         | STRICT     | `ON DELETE SET DEFAULT` still requires the default value to match an existing parent row, else the delete violates the FK.                                | [SQLite FK][9] |
| REF-024  | mysql          | STRICT     | Cascaded FK actions do not activate triggers.                                                                                                             | [MySQL FK][10] |
| REF-025  | mysql          | STRICT     | A FK on a stored generated column cannot use `CASCADE`/`SET NULL`/`SET DEFAULT` for ON UPDATE, nor `SET NULL`/`SET DEFAULT` for ON DELETE; same for the base column of a stored generated column. | [MySQL FK][10] |
| REF-026  | mysql          | STRICT     | Do not define multiple `ON UPDATE CASCADE` clauses between the same two tables acting on the same parent/child column.                                    | [MySQL FK][10] |

## c. Indexing and performance rules

| ID      | Engines        | Severity   | Rule                                                                                                                                                       | Source |
|---------|----------------|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| IDX-001 | sqlite, mysql  | GUIDELINE  | Index columns used in `WHERE`, `JOIN`, `ORDER BY`, `GROUP BY` to avoid full table scans.                                                                  | [MySQL opt indexes][11], [SQLite CREATE INDEX][5] |
| IDX-002 | sqlite, mysql  | GUIDELINE  | Order composite-index columns so the leftmost prefix matches the query's equality/range predicates; only a leftmost prefix is usable.                     | [MySQL multi-col indexes][12], [SQLite CREATE INDEX][5] |
| IDX-003 | sqlite, mysql  | GUIDELINE  | Avoid indexing low-cardinality or rarely-filtered columns; every index adds write + storage overhead.                                                     | [MySQL opt indexes][11] |
| IDX-004 | sqlite         | STRICT     | Expression indexes may not reference other tables, subqueries, or non-deterministic functions; only columns of the indexed table.                         | [SQLite CREATE INDEX][5] |
| IDX-005 | sqlite         | GUIDELINE  | Use partial indexes (`CREATE INDEX ... WHERE <expr>`) to index only relevant rows and shrink index size.                                                  | [SQLite CREATE INDEX][5], [SQLite partial index][13] |
| IDX-006 | sqlite         | STRICT     | No arbitrary limit on indexes per table; columns per index bounded by `SQLITE_LIMIT_COLUMN`.                                                              | [SQLite CREATE INDEX][5] |
| IDX-007 | sqlite         | STRICT     | `NULLS FIRST/LAST` unsupported in indexes; NULLs sort smallest (start of ASC, end of DESC).                                                               | [SQLite CREATE INDEX][5] |
| IDX-008 | mysql          | GUIDELINE  | InnoDB secondary indexes store the PK value, not a row pointer — keep the PK narrow to minimize secondary index size.                                     | [InnoDB index types][1] |
| IDX-009 | mysql          | GUIDELINE  | Use a short, monotonically increasing PK for InnoDB to reduce page splits and fragmentation.                                                              | [InnoDB index types][1], [MySQL PK opt][14] |
| IDX-010 | mysql          | STRICT     | Index prefixes supported for CHAR/VARCHAR/BINARY/VARBINARY/TEXT/BLOB; TEXT/BLOB indexes must specify a prefix length.                                     | [MySQL column indexes][15], [MySQL FK][10] |
| IDX-011 | mysql          | GUIDELINE  | Defining FKs on join columns ensures they are indexed and improves join performance; FKs also propagate deletes/updates.                                 | [InnoDB best practices][2], [MySQL FK opt][16] |
| IDX-012 | mysql          | STRICT     | Dropping an index required by an FK is rejected; drop the FK first.                                                                                       | [MySQL FK][10] |

## d. Data type rules

| ID      | Engines        | Severity   | Rule                                                                                                                                                       | Source |
|---------|----------------|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| DT-001  | sqlite         | STRICT     | SQLite uses dynamic typing: any column (except `INTEGER PRIMARY KEY`) can store any of NULL/INTEGER/REAL/TEXT/BLOB; declared type only sets affinity.     | [SQLite datatypes][17] |
| DT-002  | sqlite         | STRICT     | Affinity rules (ordered): `INT`→INTEGER; `CHAR`/`CLOB`/`TEXT`→TEXT; `BLOB`/no type→BLOB; `REAL`/`FLOA`/`DOUB`→REAL; else NUMERIC. Order is significant.   | [SQLite datatypes][17] |
| DT-003  | sqlite         | STRICT     | No native BOOLEAN; booleans stored as INTEGER 0/1; `TRUE`/`FALSE` are aliases for 1/0.                                                                    | [SQLite datatypes][17] |
| DT-004  | sqlite         | GUIDELINE  | No native DATE/TIME; store as TEXT (ISO8601), REAL (Julian day), or INTEGER (Unix time). Pick one format consistently per column.                         | [SQLite datatypes][17] |
| DT-005  | sqlite         | STRICT     | In a STRICT table every column must declare a type from {INT, INTEGER, REAL, TEXT, BLOB, ANY}; other type names are syntax errors.                        | [SQLite STRICT][4] |
| DT-006  | sqlite         | STRICT     | In a STRICT table, a value that cannot be losslessly coerced raises `SQLITE_CONSTRAINT_DATATYPE`; `ANY` accepts any value with no coercion.               | [SQLite STRICT][4] |
| DT-007  | sqlite         | STRICT     | In a STRICT table, `INT PRIMARY KEY` is NOT a rowid alias; only `INTEGER PRIMARY KEY` is.                                                                 | [SQLite STRICT][4] |
| DT-008  | mysql          | STRICT     | MySQL enforces static typing: numeric, date/time, string (CHAR/VARCHAR/BINARY/VARBINARY/BLOB/TEXT/ENUM/SET), spatial, JSON.                               | [MySQL data types][18] |
| DT-009  | mysql          | STRICT     | For `DECIMAL`/`NUMERIC`: M = precision, D = scale; D ≤ M−2 and D ≤ 30.                                                                                     | [MySQL data types][18] |
| DT-010  | mysql          | STRICT     | `fsp` for TIME/DATETIME/TIMESTAMP is 0–6; default 0 (not the SQL standard 6).                                                                             | [MySQL data types][18] |
| DT-011  | mysql          | GUIDELINE  | Use the smallest type that reliably holds the range (e.g. TINYINT vs BIGINT, DATE vs DATETIME) to shrink rows and improve buffer-pool efficiency.         | [MySQL data size][19], [MySQL opt types][20] |
| DT-012  | mysql          | GUIDELINE  | Use `FLOAT`/`DOUBLE` for approximate values; `DECIMAL`/`NUMERIC` for exact monetary/counted values.                                                       | [MySQL fixed-point][21], [MySQL opt numeric][22] |
| DT-013  | mysql          | STRICT     | `TIMESTAMP` is converted session-TZ→UTC on store and back on retrieval; `DATETIME` is stored literally with no TZ conversion. Choose accordingly.         | [MySQL DATETIME][23] |

## e. Naming and metadata rules

| ID      | Engines        | Severity   | Rule                                                                                                                                                       | Source |
|---------|----------------|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| NAM-001 | sqlite         | STRICT     | Table names starting with `sqlite_` are reserved; creating one is an error.                                                                               | [SQLite CREATE TABLE][3] |
| NAM-002 | sqlite, mysql  | STRICT     | `CREATE TABLE` fails on a same-name table/index/view unless `IF NOT EXISTS` is given; `IF NOT EXISTS` does not suppress conflicting-index errors.         | [SQLite CREATE TABLE][3], [MySQL CREATE TABLE][6] |
| NAM-003 | mysql          | STRICT     | Identifier case sensitivity depends on `lower_case_table_names`; backtick-quote (or double-quote under `ANSI_QUOTES`).                                    | [MySQL identifier case][24] |
| NAM-004 | sqlite, mysql  | GUIDELINE  | Use consistent, descriptive, snake_case identifiers; avoid SQL reserved keywords as identifiers.                                                          | [SQLite keywords][25], [MySQL keywords][26] |
| NAM-005 | sqlite, mysql  | GUIDELINE  | Name FK constraints explicitly (`CONSTRAINT symbol`) for reliable drop/error references; auto-generated names are implementation-dependent.               | [MySQL FK][10] |

## f. Normalization rules

These are engine-agnostic relational-theory guidelines (Codd 1970–1974), applicable to both engines.

| ID      | Engines        | Severity   | Rule                                                                                                                                                       | Source |
|---------|----------------|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| NORM-001 | sqlite, mysql | GUIDELINE  | **1NF**: every column holds atomic single-valued values; no repeating groups or arrays.                                                                   | [1NF][27] |
| NORM-002 | sqlite, mysql | GUIDELINE  | **2NF**: no non-prime attribute depends on only a proper subset of a composite candidate key (eliminate partial-key dependencies).                       | [2NF][28] |
| NORM-003 | sqlite, mysql | GUIDELINE  | **3NF**: no non-prime attribute is transitively dependent on a candidate key (eliminate transitive dependencies).                                         | [3NF][29] |
| NORM-004 | sqlite, mysql | GUIDELINE  | **BCNF**: every non-trivial FD X→Y has X as a superkey; every determinant is a candidate key.                                                              | [BCNF][30] |
| NORM-005 | sqlite, mysql | GUIDELINE  | Model M:N relationships with a junction/associative table carrying FKs to both sides — never embedded lists.                                              | [Associative entity][31] |
| NORM-006 | sqlite, mysql | GUIDELINE  | Denormalize for read performance only after 3NF/BCNF and only with documented justification; it trades write integrity/storage for read speed.            | [MySQL DB structure opt][32] |

## g. Engine-specific rules (SQLite vs MySQL differences)

| ID      | Engines        | Severity   | Rule                                                                                                                                                       | Source |
|---------|----------------|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| ENG-001 | sqlite         | GUIDELINE  | SQLite FKs are OFF by default; MySQL `foreign_key_checks` ON by default. Linters should flag SQLite schemas defining FKs without enabling `PRAGMA foreign_keys`. | [SQLite FK][9], [MySQL FK][10] |
| ENG-002 | sqlite, mysql  | GUIDELINE  | Type enforcement differs: SQLite (non-STRICT) coerces by affinity and stores any type; MySQL enforces declared types. For portability use SQLite STRICT tables or only INT/INTEGER/REAL/TEXT/BLOB. | [SQLite datatypes][17], [SQLite STRICT][4], [MySQL data types][18] |
| ENG-003 | sqlite, mysql  | GUIDELINE  | Boolean/date-time types differ: SQLite has no native BOOLEAN/DATE/TIME (stored as INTEGER/TEXT/REAL); MySQL has native DATE/DATETIME/TIMESTAMP/TIME/YEAR. Don't rely on a native boolean cross-engine. | [SQLite datatypes][17], [MySQL data types][18] |
| ENG-004 | mysql          | STRICT     | InnoDB stores row data in the clustered index (the PK); all secondary indexes embed the PK. Design PKs with InnoDB clustering in mind.                    | [InnoDB index types][1] |
| ENG-005 | sqlite         | STRICT     | SQLite has no per-table storage engine and no clustered index; `INTEGER PRIMARY KEY` rowid is the closest analog.                                         | [SQLite CREATE TABLE][3], [SQLite WITHOUT ROWID][33] |
| ENG-006 | sqlite, mysql  | GUIDELINE  | `ALTER TABLE` differs sharply: SQLite supports only rename/add-column/rename-column/drop-column and cannot add/remove constraints in place; MySQL supports full ALTER. Plan migrations accordingly. | [SQLite ALTER][34], [MySQL ALTER][35] |
| ENG-007 | mysql          | GUIDELINE  | Use `ENGINE=InnoDB` (default) for transactional, FK-critical schemas; other engines (MyISAM, MEMORY) lack FK support and/or crash safety — use only with justification. | [InnoDB best practices][2], [MySQL storage engines][36] |

---

## Deduplication & unified canonical set notes

- **Merged across engines** (identical or near-identical behavior): REF-003, REF-017, REF-018,
  IDX-001, IDX-002, NORM-001..005, NAM-002, NAM-004, NAM-005, ENG-002, ENG-003.
- **Kept separate** where behavior diverges: FK default state (REF-001 vs REF-002), type
  enforcement (DT-001/DT-005 vs DT-008), clustered index (SCHEMA-009/010/ENG-004 vs ENG-005),
  `SET DEFAULT` support (REF-020 vs REF-023), ALTER capabilities (ENG-006).
- **Normalization** (NORM-*) is engine-agnostic relational theory and applies to both as GUIDELINEs.

## Machine-readable form

The complete rule set is also exported as JSON suitable for a rule engine / linter at:
`db_schema_rules.json`.

<!-- Sources -->
[1]: https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html
[2]: https://dev.mysql.com/doc/refman/8.4/en/innodb-best-practices.html
[3]: https://www.sqlite.org/lang_createtable.html
[4]: https://www.sqlite.org/stricttables.html
[5]: https://www.sqlite.org/lang_createindex.html
[6]: https://dev.mysql.com/doc/refman/8.4/en/create-table.html
[7]: https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html
[8]: https://dev.mysql.com/doc/refman/8.4/en/data-type-defaults.html
[9]: https://www.sqlite.org/foreignkeys.html
[10]: https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html
[11]: https://dev.mysql.com/doc/refman/8.4/en/optimization-indexes.html
[12]: https://dev.mysql.com/doc/refman/8.4/en/multiple-column-indexes.html
[13]: https://www.sqlite.org/partialindex.html
[14]: https://dev.mysql.com/doc/refman/8.4/en/primary-key-optimization.html
[15]: https://dev.mysql.com/doc/refman/8.4/en/column-indexes.html
[16]: https://dev.mysql.com/doc/refman/8.4/en/foreign-key-optimization.html
[17]: https://www.sqlite.org/datatype3.html
[18]: https://dev.mysql.com/doc/refman/8.4/en/data-types.html
[19]: https://dev.mysql.com/doc/refman/8.4/en/data-size.html
[20]: https://dev.mysql.com/doc/refman/8.4/en/optimize-data-types.html
[21]: https://dev.mysql.com/doc/refman/8.4/en/fixed-point-types.html
[22]: https://dev.mysql.com/doc/refman/8.4/en/optimize-numeric.html
[23]: https://dev.mysql.com/doc/refman/8.4/en/datetime.html
[24]: https://dev.mysql.com/doc/refman/8.4/en/identifier-case-sensitivity.html
[25]: https://www.sqlite.org/lang_keywords.html
[26]: https://dev.mysql.com/doc/refman/8.4/en/keywords.html
[27]: https://en.wikipedia.org/wiki/First_normal_form
[28]: https://en.wikipedia.org/wiki/Second_normal_form
[29]: https://en.wikipedia.org/wiki/Third_normal_form
[30]: https://en.wikipedia.org/wiki/Boyce%E2%80%93Codd_normal_form
[31]: https://en.wikipedia.org/wiki/Associative_entity
[32]: https://dev.mysql.com/doc/refman/8.4/en/optimizing-database-structure.html
[33]: https://www.sqlite.org/withoutrowid.html
[34]: https://www.sqlite.org/lang_altertable.html
[35]: https://dev.mysql.com/doc/refman/8.4/en/alter-table.html
[36]: https://dev.mysql.com/doc/refman/8.4/en/storage-engines.html
