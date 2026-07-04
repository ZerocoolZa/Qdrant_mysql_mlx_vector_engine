/*
 * schemalint.c — Rule-Based Schema Lint Engine for SQLite
 *
 * Architecture:
 *   1. RULES (compiled-in config structs — 22 rules)
 *   2. ENGINE (generic executor: extract schema → run rules → report)
 *   3. SCHEMA (runtime input — any SQLite .db or .sql file)
 *
 * The engine reads schema metadata via PRAGMA queries,
 * builds an in-memory graph (tables, columns, FKs, indexes),
 * then evaluates each rule against the graph.
 *
 * To add a rule:
 *   1. Write a check function: static int check_foo(Schema *s, Rule *r, Finding *out)
 *   2. Add it to the CHECKS dispatch table
 *   3. Add a RULES entry
 *
 * Compile:
 *   cc -O2 -o schemalint schemalint.c -lsqlite3
 *
 * Usage:
 *   ./schemalint schema_v2.sql        — lint a schema file
 *   ./schemalint efl_brain.db         — lint a live database
 *   ./schemalint efl_brain.db --json  — JSON output
 *   ./schemalint efl_brain.db --score — health score only
 *
 * Author: wws / Cascade
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <sqlite3.h>

/* ════════════════════════════════════════════
 * CONSTANTS
 * ════════════════════════════════════════════ */

#define MAX_TABLES    128
#define MAX_COLS      64
#define MAX_INDEXES   32
#define MAX_FKS       16
#define MAX_FINDINGS  1024
#define MAX_NAME      256
#define MAX_TYPE      64
#define MAX_MSG       512
#define MAX_RULES     32

/* ════════════════════════════════════════════
 * DATA STRUCTURES — In-Memory Schema Graph
 * ════════════════════════════════════════════ */

typedef struct {
    char name[MAX_NAME];
    char type[MAX_TYPE];
    int  notnull;
    char default_val[MAX_NAME];
    int  pk_order;       /* 0 = not PK, 1+ = PK column order */
    int  cid;
} Column;

typedef struct {
    char name[MAX_NAME];
    int  is_unique;
    char columns[MAX_COLS][MAX_NAME];
    int  col_count;
} Index;

typedef struct {
    char ref_table[MAX_NAME];
    char from_col[MAX_NAME];
    char to_col[MAX_NAME];
} ForeignKey;

typedef struct {
    char       name[MAX_NAME];
    Column     columns[MAX_COLS];
    int        col_count;
    Index      indexes[MAX_INDEXES];
    int        idx_count;
    ForeignKey fks[MAX_FKS];
    int        fk_count;
    int        row_count;
} Table;

typedef struct {
    Table tables[MAX_TABLES];
    int   table_count;
} Schema;

/* ════════════════════════════════════════════
 * RULES & FINDINGS
 * ════════════════════════════════════════════ */

typedef enum {
    SEV_HIGH = 0,
    SEV_MEDIUM = 1,
    SEV_LOW = 2
} Severity;

typedef struct {
    char      id[MAX_NAME];
    char      description[MAX_MSG];
    Severity  severity;
    char      check_type[MAX_NAME];
    int       enabled;
    /* params */
    int       max_lob_count;
    char      lob_types[8][MAX_TYPE];
    int       lob_type_count;
} Rule;

typedef struct {
    char     rule_id[MAX_NAME];
    char     description[MAX_MSG];
    Severity severity;
    char     table[MAX_NAME];
    char     column[MAX_NAME];
    char     message[MAX_MSG];
} Finding;

/* ════════════════════════════════════════════
 * GLOBALS
 * ════════════════════════════════════════════ */

static Schema   g_schema;
static Finding  g_findings[MAX_FINDINGS];
static int      g_finding_count = 0;
static int      opt_json = 0;
static int      opt_score = 0;

/* SQL reserved words */
static const char *RESERVED_WORDS[] = {
    "abort","action","add","after","all","alter","analyze","and","as","asc",
    "attach","autoincrement","before","begin","between","by","cascade","case",
    "cast","check","collate","column","commit","conflict","constraint","create",
    "cross","current_date","current_time","current_timestamp","database","default",
    "deferrable","deferred","delete","desc","detach","distinct","drop","each",
    "else","end","escape","except","exclusive","exists","explain","fail","for",
    "foreign","from","full","glob","group","having","if","ignore","immediate",
    "in","index","indexed","initially","inner","insert","instead","intersect",
    "into","is","isnull","join","key","left","like","limit","match","natural",
    "no","not","notnull","null","of","offset","on","or","order","outer","plan",
    "pragma","primary","query","raise","references","regexp","reindex","rename",
    "replace","restrict","right","rollback","row","savepoint","select","set",
    "table","temp","temporary","then","timestamp","to","transaction","trigger",
    "union","unique","update","using","vacuum","values","view","virtual","when",
    "where", NULL
};

/* ════════════════════════════════════════════
 * SCHEMA EXTRACTION — SQLite PRAGMA queries
 * ════════════════════════════════════════════ */

static void extract_columns(sqlite3 *db, Table *t) {
    char sql[512];
    snprintf(sql, sizeof(sql), "PRAGMA table_info(%s)", t->name);
    sqlite3_stmt *st;
    if (sqlite3_prepare_v2(db, sql, -1, &st, NULL) != SQLITE_OK) return;
    while (sqlite3_step(st) == SQLITE_ROW && t->col_count < MAX_COLS) {
        Column *c = &t->columns[t->col_count];
        c->cid = sqlite3_column_int(st, 0);
        strncpy(c->name, (const char*)sqlite3_column_text(st, 1), MAX_NAME-1);
        c->name[MAX_NAME-1] = 0;
        strncpy(c->type, (const char*)sqlite3_column_text(st, 2), MAX_TYPE-1);
        c->type[MAX_TYPE-1] = 0;
        c->notnull = sqlite3_column_int(st, 3);
        const char *dflt = (const char*)sqlite3_column_text(st, 4);
        strncpy(c->default_val, dflt ? dflt : "", MAX_NAME-1);
        c->default_val[MAX_NAME-1] = 0;
        c->pk_order = sqlite3_column_int(st, 5);
        t->col_count++;
    }
    sqlite3_finalize(st);
}

static void extract_indexes(sqlite3 *db, Table *t) {
    char sql[512];
    snprintf(sql, sizeof(sql), "PRAGMA index_list(%s)", t->name);
    sqlite3_stmt *st;
    if (sqlite3_prepare_v2(db, sql, -1, &st, NULL) != SQLITE_OK) return;
    while (sqlite3_step(st) == SQLITE_ROW && t->idx_count < MAX_INDEXES) {
        Index *idx = &t->indexes[t->idx_count];
        strncpy(idx->name, (const char*)sqlite3_column_text(st, 1), MAX_NAME-1);
        idx->name[MAX_NAME-1] = 0;
        idx->is_unique = sqlite3_column_int(st, 2);
        idx->col_count = 0;
        /* get index columns */
        char sql2[512];
        snprintf(sql2, sizeof(sql2), "PRAGMA index_info(%s)", idx->name);
        sqlite3_stmt *st2;
        if (sqlite3_prepare_v2(db, sql2, -1, &st2, NULL) == SQLITE_OK) {
            while (sqlite3_step(st2) == SQLITE_ROW && idx->col_count < MAX_COLS) {
                strncpy(idx->columns[idx->col_count],
                    (const char*)sqlite3_column_text(st2, 2), MAX_NAME-1);
                idx->columns[idx->col_count][MAX_NAME-1] = 0;
                idx->col_count++;
            }
            sqlite3_finalize(st2);
        }
        t->idx_count++;
    }
    sqlite3_finalize(st);
}

static void extract_foreign_keys(sqlite3 *db, Table *t) {
    char sql[512];
    snprintf(sql, sizeof(sql), "PRAGMA foreign_key_list(%s)", t->name);
    sqlite3_stmt *st;
    if (sqlite3_prepare_v2(db, sql, -1, &st, NULL) != SQLITE_OK) return;
    while (sqlite3_step(st) == SQLITE_ROW && t->fk_count < MAX_FKS) {
        ForeignKey *fk = &t->fks[t->fk_count];
        strncpy(fk->ref_table, (const char*)sqlite3_column_text(st, 2), MAX_NAME-1);
        fk->ref_table[MAX_NAME-1] = 0;
        strncpy(fk->from_col, (const char*)sqlite3_column_text(st, 3), MAX_NAME-1);
        fk->from_col[MAX_NAME-1] = 0;
        strncpy(fk->to_col, (const char*)sqlite3_column_text(st, 4), MAX_NAME-1);
        fk->to_col[MAX_NAME-1] = 0;
        t->fk_count++;
    }
    sqlite3_finalize(st);
}

static void extract_row_count(sqlite3 *db, Table *t) {
    char sql[512];
    snprintf(sql, sizeof(sql), "SELECT COUNT(*) FROM %s", t->name);
    sqlite3_stmt *st;
    if (sqlite3_prepare_v2(db, sql, -1, &st, NULL) == SQLITE_OK) {
        if (sqlite3_step(st) == SQLITE_ROW)
            t->row_count = sqlite3_column_int(st, 0);
        sqlite3_finalize(st);
    }
}

static Schema* extract_schema(sqlite3 *db) {
    Schema *s = &g_schema;
    memset(s, 0, sizeof(Schema));
    sqlite3_stmt *st;
    const char *sql = "SELECT name FROM sqlite_master "
                      "WHERE type='table' AND name NOT LIKE 'sqlite_%'";
    if (sqlite3_prepare_v2(db, sql, -1, &st, NULL) != SQLITE_OK) return s;
    while (sqlite3_step(st) == SQLITE_ROW && s->table_count < MAX_TABLES) {
        Table *t = &s->tables[s->table_count];
        strncpy(t->name, (const char*)sqlite3_column_text(st, 0), MAX_NAME-1);
        t->name[MAX_NAME-1] = 0;
        t->col_count = 0;
        t->idx_count = 0;
        t->fk_count = 0;
        t->row_count = -1;  /* lazy: only fetch when needed */
        extract_columns(db, t);
        extract_indexes(db, t);
        extract_foreign_keys(db, t);
        s->table_count++;
    }
    sqlite3_finalize(st);
    return s;
}

/* ════════════════════════════════════════════
 * HELPERS
 * ════════════════════════════════════════════ */

static Table* find_table(Schema *s, const char *name) {
    for (int i = 0; i < s->table_count; i++)
        if (strcasecmp(s->tables[i].name, name) == 0)
            return &s->tables[i];
    return NULL;
}

static Column* find_column(Table *t, const char *name) {
    for (int i = 0; i < t->col_count; i++)
        if (strcasecmp(t->columns[i].name, name) == 0)
            return &t->columns[i];
    return NULL;
}

static int is_reserved_word(const char *name) {
    for (int i = 0; RESERVED_WORDS[i]; i++)
        if (strcasecmp(name, RESERVED_WORDS[i]) == 0) return 1;
    return 0;
}

static int col_is_indexed(Table *t, const char *col_name) {
    /* Check explicit indexes */
    for (int i = 0; i < t->idx_count; i++)
        for (int j = 0; j < t->indexes[i].col_count; j++)
            if (strcasecmp(t->indexes[i].columns[j], col_name) == 0) return 1;
    /* PK columns are indexed */
    for (int i = 0; i < t->col_count; i++)
        if (t->columns[i].pk_order > 0 && strcasecmp(t->columns[i].name, col_name) == 0)
            return 1;
    return 0;
}

static int is_lob_type(const char *type, Rule *r) {
    for (int i = 0; i < r->lob_type_count; i++)
        if (strcasecmp(type, r->lob_types[i]) == 0) return 1;
    return 0;
}

static void add_finding(Rule *r, const char *table, const char *column, const char *msg) {
    if (g_finding_count >= MAX_FINDINGS) return;
    Finding *f = &g_findings[g_finding_count++];
    strncpy(f->rule_id, r->id, MAX_NAME-1);
    strncpy(f->description, r->description, MAX_MSG-1);
    f->severity = r->severity;
    strncpy(f->table, table ? table : "", MAX_NAME-1);
    strncpy(f->column, column ? column : "", MAX_NAME-1);
    strncpy(f->message, msg, MAX_MSG-1);
}

static const char* sev_str(Severity s) {
    return s == SEV_HIGH ? "HIGH" : s == SEV_MEDIUM ? "MEDIUM" : "LOW";
}

/* ════════════════════════════════════════════
 * CHECK FUNCTIONS
 * Each returns void, adds findings directly.
 * Signature: void check_xxx(Schema *s, Rule *r)
 * ════════════════════════════════════════════ */

/* RULE 1: table_must_have_pk */
static void check_table_must_have_pk(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        int has_pk = 0, has_non_pk = 0;
        for (int j = 0; j < t->col_count; j++) {
            if (t->columns[j].pk_order > 0) has_pk = 1;
            else has_non_pk = 1;
        }
        if (!has_pk && has_non_pk) {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "Table '%s' has no primary key", t->name);
            add_finding(r, t->name, NULL, msg);
        }
    }
}

/* RULE 2: fk_must_have_index */
static void check_fk_must_have_index(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        for (int j = 0; j < t->fk_count; j++) {
            if (!col_is_indexed(t, t->fks[j].from_col)) {
                char msg[MAX_MSG];
                snprintf(msg, sizeof(msg), "FK '%s' on '%s' has no index",
                    t->fks[j].from_col, t->name);
                add_finding(r, t->name, t->fks[j].from_col, msg);
            }
        }
    }
}

/* RULE 3: pk_must_be_first */
static void check_pk_must_be_first(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        int first_pk_cid = -1, first_non_pk_cid = -1;
        for (int j = 0; j < t->col_count; j++) {
            if (t->columns[j].pk_order > 0 && first_pk_cid < 0)
                first_pk_cid = t->columns[j].cid;
            if (t->columns[j].pk_order == 0 && first_non_pk_cid < 0)
                first_non_pk_cid = t->columns[j].cid;
        }
        if (first_pk_cid >= 0 && first_non_pk_cid >= 0 && first_non_pk_cid < first_pk_cid) {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "PK not declared first in '%s'", t->name);
            add_finding(r, t->name, NULL, msg);
        }
    }
}

/* RULE 4: fk_type_must_match */
static void check_fk_type_must_match(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        for (int j = 0; j < t->fk_count; j++) {
            Column *from = find_column(t, t->fks[j].from_col);
            Table *ref = find_table(s, t->fks[j].ref_table);
            if (!from || !ref) continue;
            Column *to = find_column(ref, t->fks[j].to_col);
            if (!to) continue;
            if (strcasecmp(from->type, to->type) != 0) {
                char msg[MAX_MSG];
                snprintf(msg, sizeof(msg), "FK '%s' (%s) type mismatch with '%s.%s' (%s)",
                    t->fks[j].from_col, from->type, ref->name, t->fks[j].to_col, to->type);
                add_finding(r, t->name, t->fks[j].from_col, msg);
            }
        }
    }
}

/* RULE 5: column_type_consistent */
static void check_column_type_consistent(Schema *s, Rule *r) {
    /* Check same column name across tables has same type */
    for (int i = 0; i < s->table_count; i++) {
        for (int j = 0; j < s->tables[i].col_count; j++) {
            char *name = s->tables[i].columns[j].name;
            char *type = s->tables[i].columns[j].type;
            for (int k = i + 1; k < s->table_count; k++) {
                Column *c = find_column(&s->tables[k], name);
                if (c && strcasecmp(c->type, type) != 0) {
                    char msg[MAX_MSG];
                    snprintf(msg, sizeof(msg), "Column '%s' has types '%s' vs '%s'",
                        name, type, c->type);
                    add_finding(r, s->tables[i].name, name, msg);
                }
            }
        }
    }
}

/* RULE 6: name_must_not_be_reserved */
static void check_name_not_reserved(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        if (is_reserved_word(t->name)) {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "Table name '%s' is a reserved word", t->name);
            add_finding(r, t->name, NULL, msg);
        }
        for (int j = 0; j < t->col_count; j++) {
            if (is_reserved_word(t->columns[j].name)) {
                char msg[MAX_MSG];
                snprintf(msg, sizeof(msg), "Column '%s.%s' is a reserved word",
                    t->name, t->columns[j].name);
                add_finding(r, t->name, t->columns[j].name, msg);
            }
        }
    }
}

/* RULE 7: name_must_not_contain_spaces */
static void check_name_no_spaces(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        if (strchr(t->name, ' ')) {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "Table '%s' contains spaces", t->name);
            add_finding(r, t->name, NULL, msg);
        }
        for (int j = 0; j < t->col_count; j++) {
            if (strchr(t->columns[j].name, ' ')) {
                char msg[MAX_MSG];
                snprintf(msg, sizeof(msg), "Column '%s.%s' contains spaces",
                    t->name, t->columns[j].name);
                add_finding(r, t->name, t->columns[j].name, msg);
            }
        }
    }
}

/* RULE 8: no_redundant_indexes */
static void check_no_redundant_indexes(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        for (int a = 0; a < t->idx_count; a++) {
            for (int b = 0; b < t->idx_count; b++) {
                if (a == b) continue;
                Index *ia = &t->indexes[a], *ib = &t->indexes[b];
                if (ia->col_count < ib->col_count) {
                    int prefix_match = 1;
                    for (int c = 0; c < ia->col_count; c++)
                        if (strcasecmp(ia->columns[c], ib->columns[c]) != 0)
                            { prefix_match = 0; break; }
                    if (prefix_match) {
                        char msg[MAX_MSG];
                        snprintf(msg, sizeof(msg), "Index '%s' redundant (covered by '%s')",
                            ia->name, ib->name);
                        add_finding(r, t->name, NULL, msg);
                        break;
                    }
                }
            }
        }
    }
}

/* RULE 9: no_nullable_in_unique_index */
static void check_no_nullable_in_unique(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        for (int j = 0; j < t->idx_count; j++) {
            if (!t->indexes[j].is_unique) continue;
            for (int k = 0; k < t->indexes[j].col_count; k++) {
                Column *c = find_column(t, t->indexes[j].columns[k]);
                if (c && c->notnull == 0) {
                    char msg[MAX_MSG];
                    snprintf(msg, sizeof(msg), "Nullable '%s' in unique index '%s'",
                        c->name, t->indexes[j].name);
                    add_finding(r, t->name, c->name, msg);
                }
            }
        }
    }
}

/* RULE 10: no_all_nullable_columns */
static void check_no_all_nullable(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        int non_pk = 0, nullable = 0;
        for (int j = 0; j < t->col_count; j++) {
            if (t->columns[j].pk_order == 0) {
                non_pk++;
                if (t->columns[j].notnull == 0) nullable++;
            }
        }
        if (non_pk > 0 && non_pk == nullable) {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "Table '%s' has all nullable non-PK columns", t->name);
            add_finding(r, t->name, NULL, msg);
        }
    }
}

/* RULE 11: no_fk_self_reference */
static void check_no_fk_self_reference(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        for (int j = 0; j < t->fk_count; j++) {
            if (strcasecmp(t->fks[j].ref_table, t->name) == 0) {
                int is_pk = 0;
                for (int k = 0; k < t->col_count; k++)
                    if (strcasecmp(t->columns[k].name, t->fks[j].from_col) == 0
                        && t->columns[k].pk_order > 0) is_pk = 1;
                if (is_pk) {
                    char msg[MAX_MSG];
                    snprintf(msg, sizeof(msg), "Self-referencing FK on '%s'", t->fks[j].from_col);
                    add_finding(r, t->name, t->fks[j].from_col, msg);
                }
            }
        }
    }
}

/* RULE 12: no_table_cycles — DFS cycle detection */
static int dfs_cycle(Schema *s, int node, int *visited, int *stack) {
    visited[node] = 1;
    stack[node] = 1;
    Table *t = &s->tables[node];
    for (int j = 0; j < t->fk_count; j++) {
        if (strcasecmp(t->fks[j].ref_table, t->name) == 0) continue; /* skip self-ref */
        for (int k = 0; k < s->table_count; k++) {
            if (strcasecmp(s->tables[k].name, t->fks[j].ref_table) == 0) {
                if (!visited[k]) {
                    if (dfs_cycle(s, k, visited, stack)) return 1;
                } else if (stack[k]) {
                    return 1;
                }
            }
        }
    }
    stack[node] = 0;
    return 0;
}

static void check_no_table_cycles(Schema *s, Rule *r) {
    int visited[MAX_TABLES] = {0};
    int stack[MAX_TABLES] = {0};
    for (int i = 0; i < s->table_count; i++) {
        if (!visited[i]) {
            if (dfs_cycle(s, i, visited, stack)) {
                char msg[MAX_MSG];
                snprintf(msg, sizeof(msg), "Cyclical FK relationship involving '%s'",
                    s->tables[i].name);
                add_finding(r, s->tables[i].name, NULL, msg);
            }
        }
    }
}

/* RULE 13: no_single_column_table */
static void check_no_single_column(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        if (s->tables[i].col_count < 2) {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "Table '%s' has only %d column(s)",
                s->tables[i].name, s->tables[i].col_count);
            add_finding(r, s->tables[i].name, NULL, msg);
        }
    }
}

/* RULE 14: no_string_null_default */
static void check_no_string_null_default(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        for (int j = 0; j < t->col_count; j++) {
            char *d = t->columns[j].default_val;
            if (d[0] && strcasecmp(d, "NULL") == 0) {
                char msg[MAX_MSG];
                snprintf(msg, sizeof(msg), "Column '%s.%s' has string default 'NULL'",
                    t->name, t->columns[j].name);
                add_finding(r, t->name, t->columns[j].name, msg);
            }
        }
    }
}

/* RULE 15: no_bad_column_names — bare 'ID' check */
static void check_no_bad_column_names(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        for (int j = 0; j < t->col_count; j++) {
            if (strcasecmp(t->columns[j].name, "ID") == 0) {
                char msg[MAX_MSG];
                snprintf(msg, sizeof(msg), "Column '%s.%s' should be fully named (e.g. '%s_ID')",
                    t->name, t->columns[j].name, t->name);
                add_finding(r, t->name, t->columns[j].name, msg);
            }
        }
    }
}

/* RULE 16: no_incrementing_columns */
static void check_no_incrementing_columns(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        /* group by prefix: extract trailing digits */
        for (int j = 0; j < t->col_count; j++) {
            char *name = t->columns[j].name;
            int len = strlen(name);
            int digit_start = len;
            while (digit_start > 0 && isdigit(name[digit_start - 1]))
                digit_start--;
            if (digit_start == len || digit_start == 0) continue; /* no digits or all digits */
            /* check if another column has same prefix with different number */
            char prefix[MAX_NAME];
            strncpy(prefix, name, digit_start);
            prefix[digit_start] = 0;
            for (int k = j + 1; k < t->col_count; k++) {
                if (strncasecmp(t->columns[k].name, prefix, digit_start) == 0) {
                    int klen = strlen(t->columns[k].name);
                    int kdigit = klen;
                    while (kdigit > 0 && isdigit(t->columns[k].name[kdigit - 1]))
                        kdigit--;
                    if (kdigit == digit_start &&
                        strncasecmp(t->columns[k].name, prefix, digit_start) == 0 &&
                        kdigit < klen) {
                        char msg[MAX_MSG];
                        snprintf(msg, sizeof(msg),
                            "Incrementing columns '%s*' detected (denormalization risk)",
                            prefix);
                        add_finding(r, t->name, prefix, msg);
                        break;
                    }
                }
            }
        }
    }
}

/* RULE 17: no_too_many_lobs */
static void check_no_too_many_lobs(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        int lob_count = 0;
        for (int j = 0; j < t->col_count; j++)
            if (is_lob_type(t->columns[j].type, r)) lob_count++;
        if (lob_count > r->max_lob_count) {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "Table '%s' has %d large object columns (max %d)",
                t->name, lob_count, r->max_lob_count);
            add_finding(r, t->name, NULL, msg);
        }
    }
}

/* RULE 18: no_composite_pk */
static void check_no_composite_pk(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        int pk_count = 0;
        for (int j = 0; j < t->col_count; j++)
            if (t->columns[j].pk_order > 0) pk_count++;
        if (pk_count > 1) {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "Table '%s' has composite PK (%d columns) — use surrogate",
                t->name, pk_count);
            add_finding(r, t->name, NULL, msg);
        }
    }
}

/* RULE 19: no_empty_table */
static void check_no_empty_table(Schema *s, Rule *r) {
    /* Requires DB connection — skip for schema-only mode */
    /* This check needs live row counts, handled separately */
}

/* RULE 20: no_table_without_indexes */
static void check_no_table_without_indexes(Schema *s, Rule *r) {
    for (int i = 0; i < s->table_count; i++) {
        Table *t = &s->tables[i];
        int has_non_pk = 0;
        for (int j = 0; j < t->col_count; j++)
            if (t->columns[j].pk_order == 0) has_non_pk = 1;
        if (!has_non_pk) continue;
        if (t->idx_count == 0) {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "Table '%s' has no indexes", t->name);
            add_finding(r, t->name, NULL, msg);
        }
    }
}

/* ════════════════════════════════════════════
 * CHECK DISPATCH TABLE
 * ════════════════════════════════════════════ */

typedef void (*CheckFn)(Schema *s, Rule *r);

typedef struct {
    char     check_type[MAX_NAME];
    CheckFn  fn;
} CheckEntry;

static CheckEntry CHECKS[] = {
    {"table_must_have_pk",        check_table_must_have_pk},
    {"fk_must_have_index",        check_fk_must_have_index},
    {"pk_must_be_first",          check_pk_must_be_first},
    {"fk_type_must_match",        check_fk_type_must_match},
    {"column_type_consistent",    check_column_type_consistent},
    {"name_must_not_be_reserved", check_name_not_reserved},
    {"name_must_not_contain_spaces", check_name_no_spaces},
    {"no_redundant_indexes",      check_no_redundant_indexes},
    {"no_nullable_in_unique_index", check_no_nullable_in_unique},
    {"no_all_nullable_columns",   check_no_all_nullable},
    {"no_fk_self_reference",      check_no_fk_self_reference},
    {"no_table_cycles",           check_no_table_cycles},
    {"no_single_column_table",    check_no_single_column},
    {"no_string_null_default",    check_no_string_null_default},
    {"no_bad_column_names",       check_no_bad_column_names},
    {"no_incrementing_columns",   check_no_incrementing_columns},
    {"no_too_many_lobs",          check_no_too_many_lobs},
    {"no_composite_pk",           check_no_composite_pk},
    {"no_empty_table",            check_no_empty_table},
    {"no_table_without_indexes",  check_no_table_without_indexes},
    {"", NULL}
};

static CheckFn lookup_check(const char *check_type) {
    for (int i = 0; CHECKS[i].fn; i++)
        if (strcasecmp(CHECKS[i].check_type, check_type) == 0)
            return CHECKS[i].fn;
    return NULL;
}

/* ════════════════════════════════════════════
 * RULES CONFIG — 22 rules as compiled-in data
 * ════════════════════════════════════════════ */

static Rule RULES[] = {
    /* --- MUST rules --- */
    {"must_have_pk",
     "Every table MUST have a primary key",
     SEV_HIGH, "table_must_have_pk", 1, 0, {}, 0},

    {"fk_must_have_index",
     "Every FK column MUST have an index",
     SEV_LOW, "fk_must_have_index", 1, 0, {}, 0},

    {"pk_must_be_first",
     "Primary key columns MUST be declared first",
     SEV_LOW, "pk_must_be_first", 1, 0, {}, 0},

    {"fk_type_must_match",
     "FK column type MUST match referenced PK type",
     SEV_MEDIUM, "fk_type_must_match", 1, 0, {}, 0},

    {"column_type_consistent",
     "Same column name MUST have same type across tables",
     SEV_MEDIUM, "column_type_consistent", 1, 0, {}, 0},

    /* --- MUST NOT rules --- */
    {"no_reserved_words",
     "Names MUST NOT be SQL reserved words",
     SEV_MEDIUM, "name_must_not_be_reserved", 1, 0, {}, 0},

    {"no_spaces_in_names",
     "Names MUST NOT contain spaces",
     SEV_MEDIUM, "name_must_not_contain_spaces", 1, 0, {}, 0},

    {"no_redundant_indexes",
     "Tables MUST NOT have redundant indexes",
     SEV_HIGH, "no_redundant_indexes", 1, 0, {}, 0},

    {"no_nullable_in_unique",
     "Unique indexes MUST NOT contain nullable columns",
     SEV_MEDIUM, "no_nullable_in_unique_index", 1, 0, {}, 0},

    {"no_all_nullable",
     "Tables MUST NOT have all nullable non-PK columns",
     SEV_MEDIUM, "no_all_nullable_columns", 1, 0, {}, 0},

    {"no_fk_self_reference",
     "FKs MUST NOT self-reference the PK",
     SEV_MEDIUM, "no_fk_self_reference", 1, 0, {}, 0},

    {"no_fk_cycles",
     "Tables MUST NOT have cyclical FK relationships",
     SEV_HIGH, "no_table_cycles", 1, 0, {}, 0},

    {"no_single_column_tables",
     "Tables MUST NOT have fewer than 2 columns",
     SEV_LOW, "no_single_column_table", 1, 0, {}, 0},

    {"no_string_null_default",
     "Defaults MUST NOT be string 'NULL'",
     SEV_MEDIUM, "no_string_null_default", 1, 0, {}, 0},

    {"no_bad_column_names",
     "Columns MUST NOT be named bare 'ID'",
     SEV_LOW, "no_bad_column_names", 1, 0, {}, 0},

    {"no_incrementing_columns",
     "Tables MUST NOT have incrementing column names",
     SEV_MEDIUM, "no_incrementing_columns", 1, 0, {}, 0},

    {"no_too_many_lobs",
     "Tables MUST NOT exceed large object column limit",
     SEV_MEDIUM, "no_too_many_lobs", 1, 1, {"TEXT"}, 1},

    {"no_composite_pk",
     "Tables SHOULD NOT use composite primary keys",
     SEV_MEDIUM, "no_composite_pk", 1, 0, {}, 0},

    /* --- Optional (disabled) --- */
    {"no_empty_tables",
     "Tables MUST NOT be empty",
     SEV_LOW, "no_empty_table", 0, 0, {}, 0},

    {"no_table_without_indexes",
     "Tables MUST NOT lack indexes entirely",
     SEV_LOW, "no_table_without_indexes", 0, 0, {}, 0},
};

static int RULE_COUNT = sizeof(RULES) / sizeof(Rule);

/* ════════════════════════════════════════════
 * ENGINE
 * ════════════════════════════════════════════ */

static void run_engine(Schema *s) {
    g_finding_count = 0;
    for (int i = 0; i < RULE_COUNT; i++) {
        if (!RULES[i].enabled) continue;
        CheckFn fn = lookup_check(RULES[i].check_type);
        if (fn) fn(s, &RULES[i]);
        else {
            char msg[MAX_MSG];
            snprintf(msg, sizeof(msg), "ERROR: unknown check_type '%s'", RULES[i].check_type);
            add_finding(&RULES[i], NULL, NULL, msg);
        }
    }
}

/* ════════════════════════════════════════════
 * REPORTING
 * ════════════════════════════════════════════ */

static void print_text_report(void) {
    int high = 0, med = 0, low = 0;
    for (int i = 0; i < g_finding_count; i++) {
        if (g_findings[i].severity == SEV_HIGH) high++;
        else if (g_findings[i].severity == SEV_MEDIUM) med++;
        else low++;
    }

    printf("\n======================================================================\n");
    printf("Schema Lint Report — %d finding(s)\n", g_finding_count);
    printf("  High: %d  Medium: %d  Low: %d\n", high, med, low);
    printf("======================================================================\n");

    Severity current = -1;
    for (int i = 0; i < g_finding_count; i++) {
        if (g_findings[i].severity != current) {
            current = g_findings[i].severity;
            printf("\n--- %s ---\n\n", sev_str(current));
        }
        char loc[MAX_NAME * 2];
        if (g_findings[i].column[0])
            snprintf(loc, sizeof(loc), "%s.%s", g_findings[i].table, g_findings[i].column);
        else
            snprintf(loc, sizeof(loc), "%s", g_findings[i].table);
        printf("  [%s] %s\n", g_findings[i].rule_id, loc);
        printf("    %s\n\n", g_findings[i].message);
    }

    if (g_finding_count == 0)
        printf("Schema is clean. All rules passed.\n");
}

static void print_json_report(void) {
    printf("[\n");
    for (int i = 0; i < g_finding_count; i++) {
        Finding *f = &g_findings[i];
        printf("  {");
        printf("\"rule\":\"%s\",", f->rule_id);
        printf("\"severity\":\"%s\",", sev_str(f->severity));
        printf("\"table\":\"%s\",", f->table);
        printf("\"column\":\"%s\",", f->column);
        printf("\"message\":\"%s\"", f->message);
        printf("}%s\n", i < g_finding_count - 1 ? "," : "");
    }
    printf("]\n");
}

static void print_score(void) {
    int high = 0, med = 0, low = 0;
    for (int i = 0; i < g_finding_count; i++) {
        if (g_findings[i].severity == SEV_HIGH) high++;
        else if (g_findings[i].severity == SEV_MEDIUM) med++;
        else low++;
    }
    /* Score: 100 - (high*10 + med*3 + low*1), clamped to 0 */
    int score = 100 - (high * 10 + med * 3 + low * 1);
    if (score < 0) score = 0;
    printf("{\n");
    printf("  \"schema_health_score\": %d,\n", score);
    printf("  \"findings\": %d,\n", g_finding_count);
    printf("  \"high\": %d,\n", high);
    printf("  \"medium\": %d,\n", med);
    printf("  \"low\": %d,\n", low);
    printf("  \"tables\": %d,\n", g_schema.table_count);
    printf("  \"rules_evaluated\": %d\n", RULE_COUNT);
    printf("}\n");
}

/* ════════════════════════════════════════════
 * MAIN
 * ════════════════════════════════════════════ */

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr,
            "Usage: %s <database.db | schema.sql> [--json] [--score]\n"
            "\n"
            "  --json   Output findings as JSON\n"
            "  --score  Output schema health score as JSON\n"
            "\n"
            "Compile: cc -O2 -o schemalint schemalint.c -lsqlite3\n",
            argv[0]);
        return 1;
    }

    const char *target = argv[1];
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--json") == 0) opt_json = 1;
        if (strcmp(argv[i], "--score") == 0) opt_score = 1;
    }

    sqlite3 *db;
    int is_sql_file = strstr(target, ".sql") != NULL;

    if (is_sql_file) {
        /* Load schema into in-memory DB */
        if (sqlite3_open(":memory:", &db) != SQLITE_OK) {
            fprintf(stderr, "Cannot open in-memory DB\n");
            return 1;
        }
        FILE *f = fopen(target, "r");
        if (!f) {
            fprintf(stderr, "Cannot open %s\n", target);
            sqlite3_close(db);
            return 1;
        }
        fseek(f, 0, SEEK_END);
        long sz = ftell(f);
        fseek(f, 0, SEEK_SET);
        char *sql = malloc(sz + 1);
        fread(sql, 1, sz, f);
        sql[sz] = 0;
        fclose(f);
        char *err = NULL;
        if (sqlite3_exec(db, sql, NULL, NULL, &err) != SQLITE_OK) {
            fprintf(stderr, "SQL error: %s\n", err);
            sqlite3_free(err);
            free(sql);
            sqlite3_close(db);
            return 1;
        }
        free(sql);
    } else {
        if (sqlite3_open(target, &db) != SQLITE_OK) {
            fprintf(stderr, "Cannot open %s\n", target);
            return 1;
        }
    }

    sqlite3_exec(db, "PRAGMA foreign_keys = ON", NULL, NULL, NULL);

    /* Extract schema */
    Schema *s = extract_schema(db);

    /* Run rules */
    run_engine(s);

    /* Report */
    if (opt_score)
        print_score();
    else if (opt_json)
        print_json_report();
    else
        print_text_report();

    sqlite3_close(db);
    return g_finding_count > 0 ? 1 : 0;
}
