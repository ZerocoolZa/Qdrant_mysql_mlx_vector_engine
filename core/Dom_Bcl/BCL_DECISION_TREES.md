# BCL Decision Trees — Schema Lint Engine

## What is BCL?

BCL (Bracket Command Language) is the token format used in `vb_shared.tokens`. Every token is a `[@name]{...}` container holding tuples and nested containers.

## Token Table Examples (real data from vb_shared)

### Simple list token:
```
[@MigrateSQLiteToMySQL]{("Analyze SQLite schema";"Create MySQL DB";"Convert schema";"Copy data";"Create indexes";"Verify migration")}
```

### Decision tree token (Pass/Fail/Unsure with weights):
```
[@CascadeSearch]
    [@Pass]{("Uses existing tables flow_tokens + know_tokens only. No new tables.";92)}
    [@Fail]{("Any new table or column with underscore. Hardcoded paths in tokens.";92)}
    [@Unsure]{("Whether C binary interface is sufficient or needs wrapper rewrite.";92)}
    ("Purpose";"System-wide search using Mac native tools + in-memory cache + token persistence")
    ("Layer1";"Native: grep, find, mdfind, rg")
```

### Nested question token:
```
[@QuestionWhat]
    [@Pass]{("Defines the problem or concept itself.";92)}
    [@Fail]{("Jumping to solution without defining the problem.";92)}
    ("Question";"What exactly are we trying to solve or build?")
    ("Table";"tokens")
    ("Weight";"100")
    ("Required";"yes")
    ("Order";"1")
```

## BCL Syntax Rules

1. **Container**: `[@name]{...}` — name is the dispatch ID
2. **Tuple**: `("value1";"value2";"value3")` — semicolons inside parens
3. **Weight**: always the LAST element in a tuple: `("text";92)`
4. **Nesting**: containers can hold other containers: `[@outer]{[@inner]{(...)}}`
5. **No colons** in container names: `[@must_have_pk]` not `[@rule:must_have_pk]`
6. **No angle brackets** in this format: `[@name]` not `[@name<value>]`
7. **Properties**: `("key";"value")` inside containers

## Decision Tree Structure

A decision tree is a `[@rule_id]` container holding nested `[@check_id]` containers. Each check container has `[@Pass]` and `[@Fail]` branches.

### Branch types:

| Branch | Meaning | When to use |
|--------|---------|-------------|
| `[@Pass]` | Condition is TRUE | This fix applies — output the fix SQL |
| `[@Fail]` | Condition is FALSE | Try the next nested check |
| `[@Unsure]` | Cannot determine | Flag for human review |

### Tuple format inside Pass/Fail:

```
("fix_sql_or_comment";weight)
```

- **First value**: the fix SQL (or `-- comment` if no fix needed)
- **Last value**: confidence weight (0-100, higher = more confident)

### How the C engine reads it:

1. Engine finds `[@rule_id]` container
2. Inside it, finds first `[@check_id]` container
3. Calls C function `check_id(schema_metadata)` → returns PASS, FAIL, or UNSURE
4. If PASS → reads tuple inside `[@Pass]` → first value is the fix SQL → outputs it
5. If FAIL → looks for next `[@check_id]` inside the `[@Fail]` branch → repeats
6. If UNSURE → reads tuple inside `[@Unsure]` → outputs for human review
7. If no more checks inside `[@Fail]` → that tuple IS the final answer (human review)

## Full Example — `no_column_spread`

```
[@no_column_spread]{
    [@is_audit_column]{
        [@Pass]{("-- acceptable: audit columns are intentionally spread";100)}
        [@Fail]{
            [@same_name_diff_meaning]{
                [@Pass]{("ALTER TABLE {table} RENAME COLUMN {column} TO {table}_{column}";90)}
                [@Fail]{
                    [@same_name_same_meaning]{
                        [@Pass]{("CREATE TABLE {lookup} (id INTEGER PRIMARY KEY, {column} {type})";80)}
                        [@Fail]{("-- flag for human review";50)}
                    }
                }
            }
        }
    }
}
```

### C engine execution flow:

```
1. Rule "no_column_spread" triggers a finding
2. Engine enters [@no_column_spread] container
3. Engine finds [@is_audit_column] → calls is_audit_column(schema)
4. is_audit_column returns PASS
   → read tuple: ("-- acceptable: ...";100)
   → output: "-- acceptable: audit columns are intentionally spread"
   → done
5. is_audit_column returns FAIL
   → enter [@Fail] branch
   → find [@same_name_diff_meaning] → calls same_name_diff_meaning(schema)
   → if PASS: read tuple → output fix SQL → done
   → if FAIL: enter [@Fail] branch
   → find [@same_name_same_meaning] → calls same_name_same_meaning(schema)
   → if PASS: read tuple → output fix SQL → done
   → if FAIL: read tuple → output "-- flag for human review" → done
```

## Full Example — `must_have_pk`

```
[@must_have_pk]{
    [@has_single_unique_non_null_column]{
        [@Pass]{("ALTER TABLE {table} RENAME TO {table}_old; CREATE TABLE {table} ({column} {type} PRIMARY KEY, ...); -- migrate data";95)}
        [@Fail]{
            [@has_composite_unique]{
                [@Pass]{("ALTER TABLE {table} ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT; -- unique index already enforces business key";85)}
                [@Fail]{("ALTER TABLE {table} ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;";75)}
            }
        }
    }
}
```

## Full Example — `no_fk_cycles`

```
[@no_fk_cycles]{
    [@cycle_has_two_tables]{
        [@Pass]{("ALTER TABLE {table} DROP FOREIGN KEY({fk_name}); -- break A->B->A cycle";90)}
        [@Fail]{
            [@cycle_has_three_or_more]{
                [@Pass]{("CREATE TABLE {junction} (id INTEGER PRIMARY KEY, {col_a} INTEGER, {col_b} INTEGER, FOREIGN KEY({col_a}) REFERENCES {table_a}, FOREIGN KEY({col_b}) REFERENCES {table_b}); -- remove direct FKs";85)}
                [@Fail]{
                    [@cycle_is_intentional]{
                        [@Pass]{("-- keep cycle; make one FK DEFERRABLE to allow insert order";80)}
                        [@Fail]{("-- flag for human review";50)}
                    }
                }
            }
        }
    }
}
```

## Auto-Fixable Rules (14) — No Decision Tree Needed

These rules have exactly one fix. No Pass/Fail branching. Just a single fix template.

```
[@auto_fixable]{
    [@fk_must_have_id_suffix]{("ALTER TABLE {table} RENAME COLUMN {column} TO {column}_id;";100)}
    [@no_bad_column_names]{("ALTER TABLE {table} RENAME COLUMN {column} TO {table}_ID;";100)}
    [@no_spaces_in_names]{("ALTER TABLE {table} RENAME COLUMN {column} TO {column_underscore};";100)}
    [@no_string_null_default]{("ALTER TABLE {table} RENAME COLUMN {column} TO {column}_tmp; ALTER TABLE {table} ADD COLUMN {column} {type} NOT NULL DEFAULT {real_default};";95)}
    [@no_column_prefix_match_table]{("ALTER TABLE {table} RENAME COLUMN {column} TO {stripped};";100)}
    [@no_duplicate_indexes]{("DROP INDEX {index_name};";100)}
    [@no_redundant_indexes]{("DROP INDEX {index_name};";100)}
    [@fk_must_have_index]{("CREATE INDEX idx_{table}_{column} ON {table}({column});";100)}
    [@no_bool_wrong_type]{("ALTER TABLE {table} RENAME COLUMN {column} TO {column}_tmp; ALTER TABLE {table} ADD COLUMN {column} INTEGER;";95)}
    [@no_timestamp_naming]{("ALTER TABLE {table} RENAME COLUMN {column} TO created_at;";100)}
    [@no_autoincr_non_integer]{("-- Recreate table with INTEGER PRIMARY KEY AUTOINCREMENT";90)}
    [@must_enforce_fk]{("PRAGMA foreign_keys = ON;";100)}
    [@no_reserved_words]{("ALTER TABLE {table} RENAME COLUMN {column} TO {column}_col;";100)}
    [@sqlite_no_sqlite_prefix]{("ALTER TABLE {table} RENAME TO {table}_tbl;";100)}
}
```

## Placeholders

Fix SQL templates use `{placeholder}` syntax. The C engine fills these in from schema metadata:

| Placeholder | Source |
|-------------|--------|
| `{table}` | Table name from finding |
| `{column}` | Column name from finding |
| `{index_name}` | Index name from finding |
| `{fk_name}` | FK constraint name |
| `{ref_table}` | Referenced table name |
| `{ref_col}` | Referenced column name |
| `{type}` | Column type |
| `{real_default}` | Actual default value |
| `{stripped}` | Column name with table prefix removed |
| `{column_underscore}` | Column name with spaces replaced by underscores |
| `{junction}` | Generated junction table name |
| `{lookup}` | Generated lookup table name |
| `{col_a}` | First column in cycle |
| `{col_b}` | Second column in cycle |
| `{table_a}` | First table in cycle |
| `{table_b}` | Second table in cycle |

## Complete BCL Config File Structure

```
[@schemalint]{
    [@meta]{("version";"2.1")("structural_count";36)("design_count";80)("total_count";116)}

    [@severities]{("high";"high")("medium";"medium")("low";"low")("strict";"strict")("guideline";"guideline")}
    [@engines]{("sqlite";"sqlite")("mysql";"mysql")}
    [@thresholds]{("max_lob_columns";1)("max_table_columns";30)("max_index_columns";4)("min_tables_for_spread";3)}
    [@score_weights]{("high";10)("medium";3)("low";1)("strict";10)("guideline";3)("score_max";100)}

    [@patterns]{("bad_column_patterns";"^.*\.ID$")("csv_indicators";"_list";"_ids";"_csv";"_tags";"_names")...}
    [@types]{("lob_types";"TEXT";"BLOB")("boolean_types";"INTEGER";"INT";"BOOLEAN";"BOOL";"TINYINT")}
    [@reserved_words]{("abort";"action";"add";...)}

    [@domains]{("integrity";"must_have_pk";"pk_must_not_be_nullable";...)...}

    [@structural_rules]{
        [@must_have_pk]{("description";"Every table MUST have a primary key")("severity";"high")("check_type";"table_must_have_pk")("enabled";True)("engines";"sqlite";"mysql")}
        ...
    }

    [@design_rules]{
        [@SCHEMA-001]{("description";"...")("severity";"guideline")("check_type";"...")("enabled";True)("engines";"sqlite";"mysql")}
        ...
    }

    [@auto_fixable]{
        [@fk_must_have_id_suffix]{("ALTER TABLE {table} RENAME COLUMN {column} TO {column}_id;";100)}
        ...
    }

    [@decision_trees]{
        [@must_have_pk]{[@has_single_unique_non_null_column]{[@Pass]{("...";95)}[@Fail]{...}}}
        [@no_column_spread]{[@is_audit_column]{[@Pass]{("...";100)}[@Fail]{...}}}
        ...
    }
}
```

## Summary

- **BCL format**: `[@name]{("value";"value";weight)}` — from `vb_shared.tokens`
- **Decision tree**: nested `[@check_id]` containers with `[@Pass]`/`[@Fail]`/`[@Unsure]` branches
- **Fix SQL**: first value in the tuple inside Pass/Fail — C engine outputs it
- **Weight**: last value in tuple — confidence score (0-100)
- **Container name = C function name**: engine dispatches on it
- **Auto-fixable rules**: single tuple, no branching — straight fix
- **Placeholders**: `{table}`, `{column}`, etc. — C engine fills from schema metadata
