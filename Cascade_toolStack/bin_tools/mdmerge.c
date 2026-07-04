/*
 * mdmerge.c — Markdown Structured SQLite Importer/Exporter v2.0
 *
 * A complete C program that:
 *   - Parses Markdown correctly (headings, code fences, paragraphs)
 *   - Detects headings (#–######)
 *   - Groups paragraphs (blank-line separated)
 *   - Builds a section hierarchy (stack-based parent tracking)
 *   - Stores everything in SQLite (document → section → paragraph)
 *   - Preserves ordering (ord columns)
 *   - Exports back to Markdown (tree traversal, regeneration)
 *   - Provides a semantic interface for AI reorganization
 *
 * Build:
 *     cc mdmerge.c -lsqlite3 -o mdmerge
 *
 * Usage:
 *     ./mdmerge import  file1.md [file2.md ...] output.db
 *     ./mdmerge export  input.db output.md
 *     ./mdmerge dump    input.db
 *     ./mdmerge stats   input.db
 *     ./mdmerge sections input.db
 *     ./mdmerge semantic input.db
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <time.h>
#include <sqlite3.h>

#define MAX_LINE        65536
#define MAX_TEXT        131072
#define MAX_PATH        4096
#define MAX_STACK       64
#define MAX_HEADING     1024
#define LINE_BUF_INIT   4096
#define TEXT_BUF_INIT   8192
#define VERSION         "2.0"

/* ═══ Data Structures ═══ */

typedef struct {
    int level;
    int id;
} SectionEntry;

typedef struct {
    sqlite3 *db;
    SectionEntry stack[MAX_STACK];
    int stack_count;
} MergeContext;

/* Global prepared statements for reuse */
static sqlite3_stmt *stmt_insert_document = NULL;
static sqlite3_stmt *stmt_update_counts = NULL;
static sqlite3_stmt *stmt_insert_section = NULL;
static sqlite3_stmt *stmt_insert_paragraph = NULL;
static sqlite3_stmt *stmt_log_semantic = NULL;
static sqlite3_stmt *stmt_update_linecount = NULL;
static sqlite3_stmt *stmt_export_section = NULL;
static sqlite3_stmt *stmt_export_paragraph = NULL;
static sqlite3_stmt *stmt_export_root_para = NULL;
static sqlite3_stmt *stmt_move_para = NULL;
static sqlite3_stmt *stmt_update_para_sec = NULL;
static sqlite3_stmt *stmt_select_parent = NULL;
static sqlite3_stmt *stmt_update_sec_parent = NULL;
static sqlite3_stmt *stmt_delete_sec = NULL;
static sqlite3_stmt *stmt_rename_sec = NULL;
static sqlite3_stmt *stmt_reorder_sec = NULL;
static sqlite3_stmt *stmt_delete_para = NULL;

static void stmt_init(sqlite3 *db) {
    sqlite3_prepare_v2(db, "INSERT INTO document(name, line_count) VALUES(?,?);", -1, &stmt_insert_document, NULL);
    sqlite3_prepare_v2(db, "UPDATE document SET section_count=?, paragraph_count=? WHERE id=?;", -1, &stmt_update_counts, NULL);
    sqlite3_prepare_v2(db, "INSERT INTO section(document_id, parent_id, level, ord, ord_global, title) VALUES(?,?,?,?,?,?);", -1, &stmt_insert_section, NULL);
    sqlite3_prepare_v2(db, "INSERT INTO paragraph(document_id, section_id, ord, ord_global, text, is_code, is_blockquote, is_table, is_list, language, uuid, hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?);", -1, &stmt_insert_paragraph, NULL);
    sqlite3_prepare_v2(db, "INSERT INTO semantic_log(action, source_id, target_id, note) VALUES(?,?,?,?);", -1, &stmt_log_semantic, NULL);
    sqlite3_prepare_v2(db, "UPDATE document SET line_count=? WHERE id=?;", -1, &stmt_update_linecount, NULL);
    sqlite3_prepare_v2(db, "SELECT id, level, title, ord FROM section WHERE document_id=? AND parent_id=? ORDER BY ord;", -1, &stmt_export_section, NULL);
    sqlite3_prepare_v2(db, "SELECT text, is_code, is_blockquote, is_table, is_list, language FROM paragraph WHERE section_id=? ORDER BY ord;", -1, &stmt_export_paragraph, NULL);
    sqlite3_prepare_v2(db, "SELECT text, is_code, is_blockquote, is_table, is_list, language FROM paragraph WHERE document_id=? AND section_id=0 ORDER BY ord;", -1, &stmt_export_root_para, NULL);
    /* Semantic operation statements */
    sqlite3_prepare_v2(db, "UPDATE paragraph SET section_id=?, ord=? WHERE id=?;", -1, &stmt_move_para, NULL);
    sqlite3_prepare_v2(db, "UPDATE paragraph SET section_id=? WHERE section_id=?;", -1, &stmt_update_para_sec, NULL);
    sqlite3_prepare_v2(db, "SELECT parent_id FROM section WHERE id=?;", -1, &stmt_select_parent, NULL);
    sqlite3_prepare_v2(db, "UPDATE section SET parent_id=? WHERE parent_id=?;", -1, &stmt_update_sec_parent, NULL);
    sqlite3_prepare_v2(db, "DELETE FROM section WHERE id=?;", -1, &stmt_delete_sec, NULL);
    sqlite3_prepare_v2(db, "UPDATE section SET title=? WHERE id=?;", -1, &stmt_rename_sec, NULL);
    sqlite3_prepare_v2(db, "UPDATE section SET ord=? WHERE id=?;", -1, &stmt_reorder_sec, NULL);
    sqlite3_prepare_v2(db, "DELETE FROM paragraph WHERE id=?;", -1, &stmt_delete_para, NULL);
}

static void stmt_cleanup(void) {
    if (stmt_insert_document) sqlite3_finalize(stmt_insert_document);
    if (stmt_update_counts) sqlite3_finalize(stmt_update_counts);
    if (stmt_insert_section) sqlite3_finalize(stmt_insert_section);
    if (stmt_insert_paragraph) sqlite3_finalize(stmt_insert_paragraph);
    if (stmt_log_semantic) sqlite3_finalize(stmt_log_semantic);
    if (stmt_update_linecount) sqlite3_finalize(stmt_update_linecount);
    if (stmt_export_section) sqlite3_finalize(stmt_export_section);
    if (stmt_export_paragraph) sqlite3_finalize(stmt_export_paragraph);
    if (stmt_export_root_para) sqlite3_finalize(stmt_export_root_para);
    if (stmt_move_para) sqlite3_finalize(stmt_move_para);
    if (stmt_update_para_sec) sqlite3_finalize(stmt_update_para_sec);
    if (stmt_select_parent) sqlite3_finalize(stmt_select_parent);
    if (stmt_update_sec_parent) sqlite3_finalize(stmt_update_sec_parent);
    if (stmt_delete_sec) sqlite3_finalize(stmt_delete_sec);
    if (stmt_rename_sec) sqlite3_finalize(stmt_rename_sec);
    if (stmt_reorder_sec) sqlite3_finalize(stmt_reorder_sec);
    if (stmt_delete_para) sqlite3_finalize(stmt_delete_para);
    stmt_insert_document = NULL;
    stmt_update_counts = NULL;
    stmt_insert_section = NULL;
    stmt_insert_paragraph = NULL;
    stmt_log_semantic = NULL;
    stmt_update_linecount = NULL;
    stmt_export_section = NULL;
    stmt_export_paragraph = NULL;
    stmt_export_root_para = NULL;
    stmt_move_para = NULL;
    stmt_update_para_sec = NULL;
    stmt_select_parent = NULL;
    stmt_update_sec_parent = NULL;
    stmt_delete_sec = NULL;
    stmt_rename_sec = NULL;
    stmt_reorder_sec = NULL;
    stmt_delete_para = NULL;
}

/* ═══ Part 1: Utilities, SQLite Init, Schema ═══ */

typedef enum {
    P_TEXT,
    P_CODE,
    P_QUOTE,
    P_LIST,
    P_TABLE
} ParaType;

static const char* type_to_str(int t) {
    switch(t) {
        case P_CODE: return "code";
        case P_QUOTE: return "quote";
        case P_LIST: return "list";
        case P_TABLE: return "table";
        default: return "text";
    }
}

static void die(const char *msg) {
    fprintf(stderr, "mdmerge: %s\n", msg);
    exit(1);
}

static void die_sqlite(sqlite3 *db, const char *context) {
    fprintf(stderr, "mdmerge: SQLite error in %s: %s\n", context, sqlite3_errmsg(db));
    exit(1);
}

static int exec_sql(sqlite3 *db, const char *sql) {
    char *err = NULL;
    if (sqlite3_exec(db, sql, NULL, NULL, &err) != SQLITE_OK) {
        fprintf(stderr, "mdmerge: SQL error: %s\n", err ? err : "(null)");
        sqlite3_free(err);
        return 0;
    }
    return 1;
}

typedef struct {
    sqlite3 *db;
    int active;
} Tx;

static void tx_begin(Tx *t) {
    if (!t->active) {
        exec_sql(t->db, "BEGIN;");
        t->active = 1;
    }
}

static void tx_commit(Tx *t) {
    if (t->active) {
        exec_sql(t->db, "COMMIT;");
        t->active = 0;
    }
}

static void tx_rollback(Tx *t) {
    if (t->active) {
        exec_sql(t->db, "ROLLBACK;");
        t->active = 0;
    }
}

static int db_init(sqlite3 *db) {
    exec_sql(db, "PRAGMA journal_mode=WAL;");
    exec_sql(db, "PRAGMA synchronous=OFF;");
    exec_sql(db, "PRAGMA foreign_keys=ON;");

    exec_sql(db,
        "CREATE TABLE IF NOT EXISTS document("
        "  id INTEGER PRIMARY KEY,"
        "  name TEXT NOT NULL,"
        "  line_count INTEGER DEFAULT 0,"
        "  section_count INTEGER DEFAULT 0,"
        "  paragraph_count INTEGER DEFAULT 0,"
        "  date_imported TEXT DEFAULT CURRENT_TIMESTAMP);");

    exec_sql(db,
        "CREATE TABLE IF NOT EXISTS section("
        "  id INTEGER PRIMARY KEY,"
        "  document_id INTEGER NOT NULL,"
        "  parent_id INTEGER DEFAULT 0,"
        "  level INTEGER NOT NULL,"
        "  title TEXT NOT NULL,"
        "  ord INTEGER DEFAULT 0,"
        "  ord_global INTEGER DEFAULT 0,"
        "  FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE);");

    exec_sql(db,
        "CREATE TABLE IF NOT EXISTS paragraph("
        "  id INTEGER PRIMARY KEY,"
        "  document_id INTEGER NOT NULL,"
        "  section_id INTEGER DEFAULT 0,"
        "  ord INTEGER DEFAULT 0,"
        "  ord_global INTEGER DEFAULT 0,"
        "  text TEXT NOT NULL,"
        "  is_code INTEGER DEFAULT 0,"
        "  is_blockquote INTEGER DEFAULT 0,"
        "  is_table INTEGER DEFAULT 0,"
        "  is_list INTEGER DEFAULT 0,"
        "  language TEXT,"
        "  uuid TEXT UNIQUE,"
        "  hash TEXT,"
        "  FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE);");

    exec_sql(db,
        "CREATE TABLE IF NOT EXISTS semantic_log("
        "  id INTEGER PRIMARY KEY,"
        "  action TEXT,"
        "  source_id INTEGER,"
        "  target_id INTEGER,"
        "  note TEXT,"
        "  date_applied TEXT DEFAULT CURRENT_TIMESTAMP);");

    exec_sql(db,
        "CREATE TABLE IF NOT EXISTS op_log("
        "  id INTEGER PRIMARY KEY,"
        "  op_type TEXT,"
        "  payload TEXT,"
        "  timestamp TEXT DEFAULT CURRENT_TIMESTAMP);");

    exec_sql(db,
        "CREATE TABLE IF NOT EXISTS edge("
        "  id INTEGER PRIMARY KEY,"
        "  from_id INTEGER,"
        "  to_id INTEGER,"
        "  weight REAL,"
        "  type TEXT);");

    exec_sql(db,
        "CREATE TABLE IF NOT EXISTS score("
        "  id INTEGER PRIMARY KEY,"
        "  a INTEGER,"
        "  b INTEGER,"
        "  similarity REAL);");

    exec_sql(db,
        "CREATE TABLE IF NOT EXISTS adjacency("
        "  from_id INTEGER,"
        "  to_id INTEGER,"
        "  weight REAL,"
        "  type TEXT);");

    exec_sql(db, "CREATE INDEX IF NOT EXISTS idx_section_doc ON section(document_id);");
    exec_sql(db, "CREATE INDEX IF NOT EXISTS idx_section_parent ON section(parent_id);");
    exec_sql(db, "CREATE INDEX IF NOT EXISTS idx_para_doc ON paragraph(document_id);");
    exec_sql(db, "CREATE INDEX IF NOT EXISTS idx_para_section ON paragraph(section_id);");

    return 1;
}

static int insert_document(sqlite3 *db, const char *name, int line_count) {
    sqlite3_reset(stmt_insert_document);
    sqlite3_bind_text(stmt_insert_document, 1, name, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt_insert_document, 2, line_count);
    int rc = sqlite3_step(stmt_insert_document);
    if (rc != SQLITE_DONE) die_sqlite(db, "insert_document step");
    return (int)sqlite3_last_insert_rowid(db);
}

static void update_document_counts(sqlite3 *db, int doc_id, int sec_count, int para_count) {
    sqlite3_reset(stmt_update_counts);
    sqlite3_bind_int(stmt_update_counts, 1, sec_count);
    sqlite3_bind_int(stmt_update_counts, 2, para_count);
    sqlite3_bind_int(stmt_update_counts, 3, doc_id);
    sqlite3_step(stmt_update_counts);
}

static int insert_section(sqlite3 *db, int doc, int parent, int level, int ord, int ord_global, const char *title) {
    sqlite3_reset(stmt_insert_section);
    sqlite3_bind_int(stmt_insert_section, 1, doc);
    sqlite3_bind_int(stmt_insert_section, 2, parent);
    sqlite3_bind_int(stmt_insert_section, 3, level);
    sqlite3_bind_int(stmt_insert_section, 4, ord);
    sqlite3_bind_int(stmt_insert_section, 5, ord_global);
    sqlite3_bind_text(stmt_insert_section, 6, title, -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(stmt_insert_section);
    if (rc != SQLITE_DONE) die_sqlite(db, "insert_section step");
    return (int)sqlite3_last_insert_rowid(db);
}

static void insert_paragraph(sqlite3 *db, int doc, int section, int ord, int ord_global,
                             const char *text, int is_code, int is_bq, int is_table, int is_list, const char *language,
                             const char *uuid, const char *hash) {
    sqlite3_reset(stmt_insert_paragraph);
    sqlite3_bind_int(stmt_insert_paragraph, 1, doc);
    sqlite3_bind_int(stmt_insert_paragraph, 2, section);
    sqlite3_bind_int(stmt_insert_paragraph, 3, ord);
    sqlite3_bind_int(stmt_insert_paragraph, 4, ord_global);
    sqlite3_bind_text(stmt_insert_paragraph, 5, text, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt_insert_paragraph, 6, is_code);
    sqlite3_bind_int(stmt_insert_paragraph, 7, is_bq);
    sqlite3_bind_int(stmt_insert_paragraph, 8, is_table);
    sqlite3_bind_int(stmt_insert_paragraph, 9, is_list);
    sqlite3_bind_text(stmt_insert_paragraph, 10, language, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt_insert_paragraph, 11, uuid, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt_insert_paragraph, 12, hash, -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(stmt_insert_paragraph);
    if (rc != SQLITE_DONE) die_sqlite(db, "insert_paragraph step");
}

static void log_semantic(sqlite3 *db, const char *action, int src, int tgt, const char *note) {
    sqlite3_reset(stmt_log_semantic);
    sqlite3_bind_text(stmt_log_semantic, 1, action, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt_log_semantic, 2, src);
    sqlite3_bind_int(stmt_log_semantic, 3, tgt);
    sqlite3_bind_text(stmt_log_semantic, 4, note, -1, SQLITE_TRANSIENT);
    sqlite3_step(stmt_log_semantic);
}

static void log_op(sqlite3 *db, const char *op, const char *payload) {
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "INSERT INTO op_log(op_type,payload) VALUES(?,?);",
        -1, &st, 0);
    sqlite3_bind_text(st, 1, op, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(st, 2, payload, -1, SQLITE_TRANSIENT);
    sqlite3_step(st);
    sqlite3_finalize(st);
}

static void add_edge(sqlite3 *db, int a, int b, float w, const char *type) {
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "INSERT INTO edge(from_id,to_id,weight,type) VALUES(?,?,?,?);",
        -1, &st, 0);
    sqlite3_bind_int(st, 1, a);
    sqlite3_bind_int(st, 2, b);
    sqlite3_bind_double(st, 3, w);
    sqlite3_bind_text(st, 4, type, -1, SQLITE_TRANSIENT);
    sqlite3_step(st);
    sqlite3_finalize(st);
}

static void add_score(sqlite3 *db, int a, int b, double s) {
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "INSERT INTO score(a,b,similarity) VALUES(?,?,?);",
        -1, &st, 0);
    sqlite3_bind_int(st, 1, a);
    sqlite3_bind_int(st, 2, b);
    sqlite3_bind_double(st, 3, s);
    sqlite3_step(st);
    sqlite3_finalize(st);
}

static int get_parent(sqlite3 *db, int section_id) {
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "SELECT parent_id FROM section WHERE id=?;",
        -1, &st, 0);
    sqlite3_bind_int(st, 1, section_id);
    int parent = 0;
    if (sqlite3_step(st) == SQLITE_ROW)
        parent = sqlite3_column_int(st, 0);
    sqlite3_finalize(st);
    return parent;
}

typedef struct {
    int para_id;
    int new_section;
    int new_ord;
} Mutation;

#define MAX_MUT 4096
static Mutation queue[MAX_MUT];
static int qn = 0;

static void push_mut(int p, int s, int o) {
    if (qn < MAX_MUT) {
        queue[qn++] = (Mutation){p, s, o};
    }
}

static void apply_queue(sqlite3 *db) {
    for (int i = 0; i < qn; i++) {
        sqlite3_stmt *st;
        sqlite3_prepare_v2(db,
            "UPDATE paragraph SET section_id=?, ord=? WHERE id=?;",
            -1, &st, 0);
        sqlite3_bind_int(st, 1, queue[i].new_section);
        sqlite3_bind_int(st, 2, queue[i].new_ord);
        sqlite3_bind_int(st, 3, queue[i].para_id);
        sqlite3_step(st);
        sqlite3_finalize(st);
        log_op(db, "MOVE", "batch_mutation");
    }
    qn = 0;
}

static unsigned long fingerprint(const char *s) {
    unsigned long h = 1469598103934665603ULL;
    while (*s) {
        h ^= (unsigned char)(*s++);
        h *= 1099511628211ULL;
    }
    return h;
}

static unsigned long hash_str(const char *s) {
    unsigned long h = 5381;
    while (*s) h = ((h << 5) + h) + (unsigned char)(*s++);
    return h;
}

typedef struct {
    int paragraph_id;
    int target_section;
    int new_order;
} MoveOp;

static void apply_move(sqlite3 *db, MoveOp op) {
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "UPDATE paragraph SET section_id=?, ord=? WHERE id=?;",
        -1, &st, 0);
    sqlite3_bind_int(st, 1, op.target_section);
    sqlite3_bind_int(st, 2, op.new_order);
    sqlite3_bind_int(st, 3, op.paragraph_id);
    sqlite3_step(st);
    sqlite3_finalize(st);
}

typedef struct {
    int id;
    int doc;
    int section;
    int ord;
    char *text;
    int type;
    unsigned long hash;
} Node;

typedef struct {
    int max_section_depth;
    int max_paragraph_len;
    int allow_orphans;
} Constraints;

static int validate_move(sqlite3 *db, int para_id, int target_section) {
    if (target_section < 0) return 0;
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "SELECT LENGTH(text) FROM paragraph WHERE id=?;",
        -1, &st, 0);
    sqlite3_bind_int(st, 1, para_id);
    int ok = 1;
    if (sqlite3_step(st) == SQLITE_ROW) {
        int len = sqlite3_column_int(st, 0);
        if (len > 50000) ok = 0;
    }
    sqlite3_finalize(st);
    return ok;
}

typedef struct {
    int op_type;
    int a;
    int b;
    int c;
    double weight;
} PlanOp;

#define MAX_PLAN 8192
static PlanOp plan[MAX_PLAN];
static int plan_n = 0;

static void plan_push(int t, int a, int b, int c, double w) {
    if (plan_n < MAX_PLAN) {
        plan[plan_n++] = (PlanOp){t, a, b, c, w};
    }
}

static int detect_conflict(int a, int b) {
    return (a == b);
}

static void safe_plan_push(int t, int a, int b, int c, double w) {
    if (detect_conflict(a, b)) return;
    plan_push(t, a, b, c, w);
}

typedef struct {
    int op_type;
    int para_id;
    int old_section;
    int old_ord;
} UndoOp;

#define MAX_UNDO 16384
static UndoOp undo_stack[MAX_UNDO];
static int undo_n = 0;

static void push_undo(int op, int pid, int old_s, int old_o) {
    if (undo_n < MAX_UNDO) {
        undo_stack[undo_n++] = (UndoOp){op, pid, old_s, old_o};
    }
}

static void undo_last(sqlite3 *db) {
    if (undo_n == 0) return;
    UndoOp *u = &undo_stack[--undo_n];
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "UPDATE paragraph SET section_id=?, ord=? WHERE id=?;",
        -1, &st, 0);
    sqlite3_bind_int(st, 1, u->old_section);
    sqlite3_bind_int(st, 2, u->old_ord);
    sqlite3_bind_int(st, 3, u->para_id);
    sqlite3_step(st);
    sqlite3_finalize(st);
}

static void execute_plan(sqlite3 *db) {
    for (int i = 0; i < plan_n; i++) {
        PlanOp *p = &plan[i];
        if (p->op_type == 0) {
            if (!validate_move(db, p->a, p->b))
                continue;
            int old_sec = 0;
            int old_ord = 0;
            sqlite3_stmt *q;
            sqlite3_prepare_v2(db,
                "SELECT section_id, ord FROM paragraph WHERE id=?;",
                -1, &q, 0);
            sqlite3_bind_int(q, 1, p->a);
            if (sqlite3_step(q) == SQLITE_ROW) {
                old_sec = sqlite3_column_int(q, 0);
                old_ord = sqlite3_column_int(q, 1);
            }
            sqlite3_finalize(q);
            push_undo(0, p->a, old_sec, old_ord);
            sqlite3_stmt *st;
            sqlite3_prepare_v2(db,
                "UPDATE paragraph SET section_id=?, ord=? WHERE id=?;",
                -1, &st, 0);
            sqlite3_bind_int(st, 1, p->b);
            sqlite3_bind_int(st, 2, p->c);
            sqlite3_bind_int(st, 3, p->a);
            sqlite3_step(st);
            sqlite3_finalize(st);
        }
        if (p->op_type == 1) {
            sqlite3_stmt *st;
            sqlite3_prepare_v2(db,
                "UPDATE paragraph SET section_id=? WHERE section_id=?;",
                -1, &st, 0);
            sqlite3_bind_int(st, 1, p->b);
            sqlite3_bind_int(st, 2, p->a);
            sqlite3_step(st);
            sqlite3_finalize(st);
        }
    }
    plan_n = 0;
}

static double similarity(const char *a, const char *b) {
    int match = 0;
    int len = strlen(a) < strlen(b) ? strlen(a) : strlen(b);
    for (int i = 0; i < len; i++)
        if (a[i] == b[i]) match++;
    return (double)match / (double)len;
}

static void build_graph(sqlite3 *db) {
    sqlite3_stmt *a, *b;
    sqlite3_prepare_v2(db,
        "SELECT id,text FROM paragraph;",
        -1, &a, 0);
    while (sqlite3_step(a) == SQLITE_ROW) {
        int id_a = sqlite3_column_int(a, 0);
        const char *ta = (const char*)sqlite3_column_text(a, 1);
        sqlite3_prepare_v2(db,
            "SELECT id,text FROM paragraph;",
            -1, &b, 0);
        while (sqlite3_step(b) == SQLITE_ROW) {
            int id_b = sqlite3_column_int(b, 0);
            const char *tb = (const char*)sqlite3_column_text(b, 1);
            if (id_a == id_b) continue;
            double s = similarity(ta, tb);
            if (s > 0.6) {
                sqlite3_stmt *ins;
                sqlite3_prepare_v2(db,
                    "INSERT INTO adjacency VALUES(?,?,?,?);",
                    -1, &ins, 0);
                sqlite3_bind_int(ins, 1, id_a);
                sqlite3_bind_int(ins, 2, id_b);
                sqlite3_bind_double(ins, 3, s);
                sqlite3_bind_text(ins, 4, "sim", -1, SQLITE_STATIC);
                sqlite3_step(ins);
                sqlite3_finalize(ins);
            }
        }
        sqlite3_finalize(b);
    }
    sqlite3_finalize(a);
}

typedef struct {
    char command[32];
    int a;
    int b;
    int c;
    double w;
} CascadeOp;

static void interpret(sqlite3 *db, CascadeOp *ops, int n) {
    for (int i = 0; i < n; i++) {
        if (strcmp(ops[i].command, "move") == 0)
            safe_plan_push(0, ops[i].a, ops[i].b, ops[i].c, ops[i].w);
        if (strcmp(ops[i].command, "merge") == 0)
            safe_plan_push(1, ops[i].a, ops[i].b, 0, ops[i].w);
    }
    execute_plan(db);
}

typedef struct {
    int id;
    double confidence;
    int votes;
} Agent;

#define MAX_AGENTS 8
static Agent agents[MAX_AGENTS];
static int agent_n = 0;

static int vote(int op_id, double score) {
    if (score > 0.7) return 1;
    return 0;
}

static int consensus(double *scores, int n) {
    int v = 0;
    for (int i = 0; i < n; i++)
        if (scores[i] > 0.6)
            v++;
    return v > (n / 2);
}

static void propagate_weights(sqlite3 *db) {
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "SELECT from_id,to_id,weight FROM adjacency;",
        -1, &st, 0);
    while (sqlite3_step(st) == SQLITE_ROW) {
        int a = sqlite3_column_int(st, 0);
        int b = sqlite3_column_int(st, 1);
        double w = sqlite3_column_double(st, 2);
        if (w > 0.8) {
            safe_plan_push(0, a, b, 0, w);
        }
    }
    sqlite3_finalize(st);
}

static double stability(sqlite3 *db, int pid) {
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "SELECT COUNT(*) FROM adjacency WHERE from_id=?;",
        -1, &st, 0);
    sqlite3_bind_int(st, 1, pid);
    double s = 0;
    if (sqlite3_step(st) == SQLITE_ROW)
        s = sqlite3_column_int(st, 0);
    sqlite3_finalize(st);
    return s;
}

static void generate_rewrites(sqlite3 *db) {
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "SELECT id FROM paragraph;",
        -1, &st, 0);
    while (sqlite3_step(st) == SQLITE_ROW) {
        int id = sqlite3_column_int(st, 0);
        double s = stability(db, id);
        if (s < 2.0) {
            safe_plan_push(2, id, 0, 0, s);
        }
    }
    sqlite3_finalize(st);
}

static void split_paragraph(sqlite3 *db, int pid) {
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,
        "SELECT text FROM paragraph WHERE id=?;",
        -1, &st, 0);
    sqlite3_bind_int(st, 1, pid);
    if (sqlite3_step(st) == SQLITE_ROW) {
        const char *txt = (const char*)sqlite3_column_text(st, 0);
        char buf1[2048], buf2[2048];
        int len = strlen(txt);
        int mid = len / 2;
        strncpy(buf1, txt, mid);
        buf1[mid] = 0;
        strcpy(buf2, txt + mid);
        char uuid[64], hash_buf[32];
        unsigned long h = hash_str(buf1);
        sprintf(hash_buf, "%lu", h);
        sprintf(uuid, "%ld-%lu", (long)time(NULL), h);
        insert_paragraph(db, 0, 0, 0, 0, buf1, 0, 0, 0, 0, "", uuid, hash_buf);
        h = hash_str(buf2);
        sprintf(hash_buf, "%lu", h);
        sprintf(uuid, "%ld-%lu", (long)time(NULL), h);
        insert_paragraph(db, 0, 0, 0, 0, buf2, 0, 0, 0, 0, "", uuid, hash_buf);
    }
    sqlite3_finalize(st);
}

static void dispatch(sqlite3 *db, int op, int a, int b) {
    switch(op) {
        case 0: break;
        case 1: break;
        case 2: split_paragraph(db, a); break;
    }
}

static void trace(sqlite3 *db, const char *msg) {
    log_op(db, "TRACE", msg);
}

static int checkpoint_id = 0;

static void checkpoint(sqlite3 *db) {
    char buf[64];
    sprintf(buf, "checkpoint_%d", checkpoint_id++);
    log_op(db, "CHECKPOINT", buf);
}

static void rollback_to(sqlite3 *db, int target) {
    while (undo_n > target)
        undo_last(db);
}

/* ═══ Part 2: Markdown Reader, Heading Detection, Code Fences ═══ */

static int is_blank(const char *s) {
    while (*s) {
        if (!isspace((unsigned char)*s))
            return 0;
        s++;
    }
    return 1;
}

static int heading_level(const char *s) {
    int n = 0;
    while (*s == '#') {
        n++;
        s++;
    }
    if (n == 0 || n > 6)
        return 0;
    if (*s != ' ' && *s != '\t')
        return 0;
    return n;
}

static int is_code_fence(const char *s, char *out_lang) {
    if (s[0] == '`' && s[1] == '`' && s[2] == '`') {
        if (out_lang) sscanf(s, "```%63s", out_lang);
        return 1;
    }
    if (s[0] == '~' && s[1] == '~' && s[2] == '~') {
        if (out_lang) sscanf(s, "~~~%63s", out_lang);
        return 1;
    }
    return 0;
}

static int is_blockquote(const char *s) {
    return (s[0] == '>');
}

static int is_table_row(const char *s) {
    return (strchr(s, '|') != NULL && !is_blank(s));
}

static int is_list_item(const char *s) {
    if (*s == '-' && s[1] == ' ')
        return 1;
    if (*s == '*' && s[1] == ' ')
        return 1;
    if (*s == '+' && s[1] == ' ')
        return 1;
    if (isdigit((unsigned char)*s)) {
        const char *p = s + 1;
        while (isdigit((unsigned char)*p))
            p++;
        if (*p == '.' && p[1] == ' ')
            return 1;
    }
    return 0;
}

static int is_hr(const char *s) {
    if (s[0] == '-' && s[1] == '-' && s[2] == '-' && is_blank(s + 3))
        return 1;
    if (s[0] == '*' && s[1] == '*' && s[2] == '*' && is_blank(s + 3))
        return 1;
    if (s[0] == '_' && s[1] == '_' && s[2] == '_' && is_blank(s + 3))
        return 1;
    return 0;
}

static void trim(char *s) {
    int len = (int)strlen(s);
    while (len > 0 && (s[len-1] == '\n' || s[len-1] == '\r' ||
                       s[len-1] == ' '  || s[len-1] == '\t')) {
        s[len-1] = 0;
        len--;
    }
}

static char *skip_heading_markup(const char *line) {
    int n = 0;
    while (line[n] == '#')
        n++;
    while (line[n] == ' ' || line[n] == '\t')
        n++;
    return (char *)(line + n);
}

/* Dynamic line reader — handles arbitrarily long lines */
typedef struct {
    char *buf;
    size_t cap;
    size_t len;
} LineBuffer;

static void linebuf_init(LineBuffer *lb) {
    lb->cap = LINE_BUF_INIT;
    lb->buf = (char *)malloc(lb->cap);
    lb->buf[0] = 0;
    lb->len = 0;
}

static void linebuf_free(LineBuffer *lb) {
    free(lb->buf);
    lb->buf = NULL;
    lb->cap = 0;
    lb->len = 0;
}

static int linebuf_read(LineBuffer *lb, FILE *fp) {
    lb->len = 0;
    lb->buf[0] = 0;
    
    if (fgets(lb->buf, (int)lb->cap, fp) == NULL)
        return 0;
    
    /* Handle lines longer than buffer */
    while (strlen(lb->buf) == lb->cap - 1 && lb->buf[lb->cap - 2] != '\n') {
        lb->cap *= 2;
        char *new_buf = (char *)realloc(lb->buf, lb->cap);
        if (!new_buf) {
            fprintf(stderr, "mdmerge: realloc failed in linebuf_read\n");
            return 0;
        }
        lb->buf = new_buf;
        if (fgets(lb->buf + lb->len, (int)(lb->cap - lb->len), fp) == NULL)
            break;
    }
    
    trim(lb->buf);
    lb->len = strlen(lb->buf);
    return 1;
}

/* ═══ Part 3: Section Tree Builder, Paragraph Collector ═══ */

static int current_section(MergeContext *ctx) {
    if (ctx->stack_count == 0)
        return 0;
    return ctx->stack[ctx->stack_count - 1].id;
}

static int parent_section(MergeContext *ctx) {
    if (ctx->stack_count == 0)
        return 0;
    return ctx->stack[ctx->stack_count - 1].id;
}

static void push_section(MergeContext *ctx, int level, int id) {
    while (ctx->stack_count > 0 && ctx->stack[ctx->stack_count - 1].level >= level)
        ctx->stack_count--;
    ctx->stack[ctx->stack_count].level = level;
    ctx->stack[ctx->stack_count].id = id;
    ctx->stack_count++;
}

static void reset_stack(MergeContext *ctx) {
    ctx->stack_count = 0;
}

/* Dynamic text accumulator for paragraphs */
typedef struct {
    char *buf;
    size_t cap;
    size_t len;
} TextAccum;

static void text_init(TextAccum *ta) {
    ta->cap = TEXT_BUF_INIT;
    ta->buf = (char *)malloc(ta->cap);
    ta->buf[0] = 0;
    ta->len = 0;
}

static void text_free(TextAccum *ta) {
    free(ta->buf);
    ta->buf = NULL;
    ta->cap = 0;
    ta->len = 0;
}

static void text_clear(TextAccum *ta) {
    ta->buf[0] = 0;
    ta->len = 0;
}

static int text_is_empty(TextAccum *ta) {
    return ta->len == 0;
}

static void text_append(TextAccum *ta, const char *line) {
    size_t line_len = strlen(line);
    if (ta->len + line_len + 2 >= ta->cap) {
        while (ta->len + line_len + 2 >= ta->cap)
            ta->cap *= 2;
        char *new_buf = (char *)realloc(ta->buf, ta->cap);
        if (!new_buf) {
            fprintf(stderr, "mdmerge: realloc failed in text_append\n");
            return;
        }
        ta->buf = new_buf;
    }
    if (ta->len > 0) {
        ta->buf[ta->len++] = '\n';
    }
    memcpy(ta->buf + ta->len, line, line_len);
    ta->len += line_len;
    ta->buf[ta->len] = 0;
}

/*
 * parse_file — main parsing loop
 * Detects headings, code fences, blockquotes, tables, lists, HRs.
 * Classifies each paragraph and stores in SQLite.
 */
static void parse_file(sqlite3 *db, MergeContext *ctx, const char *filename) {
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        fprintf(stderr, "mdmerge: cannot open %s\n", filename);
        return;
    }

    reset_stack(ctx);
    int doc_id = insert_document(db, filename, 0);

    LineBuffer lb;
    linebuf_init(&lb);

    TextAccum para;
    text_init(&para);

    int section_ord = 0;
    int paragraph_ord = 0;
    int line_count = 0;
    int section_count = 0;
    int paragraph_count = 0;
    int global_counter = 0;

    int in_code_fence = 0;
    int para_is_code = 0;
    int para_is_bq = 0;
    int para_is_table = 0;
    int para_is_list = 0;
    char fence_lang[64] = {0};
    char uuid[64];
    char hash_str_buf[32];

    while (linebuf_read(&lb, fp)) {
        line_count++;
        char *line = lb.buf;

        /* Code fence toggle */
        if (is_code_fence(line, fence_lang)) {
            if (!text_is_empty(&para)) {
                unsigned long h = hash_str(para.buf);
                sprintf(hash_str_buf, "%lu", h);
                sprintf(uuid, "%ld-%lu", (long)time(NULL), h);
                insert_paragraph(db, doc_id, current_section(ctx), paragraph_ord++, global_counter++,
                                 para.buf, para_is_code, para_is_bq, para_is_table, para_is_list, fence_lang, uuid, hash_str_buf);
                paragraph_count++;
                text_clear(&para);
                para_is_code = para_is_bq = para_is_table = para_is_list = 0;
                fence_lang[0] = 0;
            }
            if (!in_code_fence) {
                /* Opening fence */
                in_code_fence = 1;
                para_is_code = 1;
                fence_lang[0] = 0;
                is_code_fence(line, fence_lang);
            } else {
                /* Closing fence — flush code paragraph */
                if (!text_is_empty(&para)) {
                    unsigned long h = hash_str(para.buf);
                    sprintf(hash_str_buf, "%lu", h);
                    sprintf(uuid, "%ld-%lu", (long)time(NULL), h);
                    insert_paragraph(db, doc_id, current_section(ctx), paragraph_ord++, global_counter++,
                                     para.buf, para_is_code, para_is_bq, para_is_table, para_is_list, fence_lang, uuid, hash_str_buf);
                    paragraph_count++;
                    text_clear(&para);
                }
                in_code_fence = 0;
                para_is_code = para_is_bq = para_is_table = para_is_list = 0;
                fence_lang[0] = 0;
            }
            continue;
        }

        /* Inside code fence — accumulate everything as code */
        if (in_code_fence) {
            text_append(&para, line);
            continue;
        }

        /* Heading detection */
        int level = heading_level(line);
        if (level) {
            if (!text_is_empty(&para)) {
                unsigned long h = hash_str(para.buf);
                sprintf(hash_str_buf, "%lu", h);
                sprintf(uuid, "%ld-%lu", (long)time(NULL), h);
                insert_paragraph(db, doc_id, current_section(ctx), paragraph_ord++, global_counter++,
                                 para.buf, para_is_code, para_is_bq, para_is_table, para_is_list, fence_lang, uuid, hash_str_buf);
                paragraph_count++;
                text_clear(&para);
                para_is_code = para_is_bq = para_is_table = para_is_list = 0;
                fence_lang[0] = 0;
            }
            char *title = skip_heading_markup(line);
            int sec_id = insert_section(db, doc_id, parent_section(ctx), level, section_ord++, global_counter++, title);
            section_count++;
            push_section(ctx, level, sec_id);
            paragraph_ord = 0;
            continue;
        }

        /* Horizontal rule — flush + emit as standalone paragraph */
        if (is_hr(line)) {
            if (!text_is_empty(&para)) {
                unsigned long h = hash_str(para.buf);
                sprintf(hash_str_buf, "%lu", h);
                sprintf(uuid, "%ld-%lu", (long)time(NULL), h);
                insert_paragraph(db, doc_id, current_section(ctx), paragraph_ord++, global_counter++,
                                 para.buf, para_is_code, para_is_bq, para_is_table, para_is_list, fence_lang, uuid, hash_str_buf);
                paragraph_count++;
                text_clear(&para);
                para_is_code = para_is_bq = para_is_table = para_is_list = 0;
                fence_lang[0] = 0;
            }
            text_append(&para, line);
            unsigned long h = hash_str(para.buf);
            sprintf(hash_str_buf, "%lu", h);
            sprintf(uuid, "%ld-%lu", (long)time(NULL), h);
            insert_paragraph(db, doc_id, current_section(ctx), paragraph_ord++, global_counter++,
                             para.buf, 0, 0, 0, 0, "", uuid, hash_str_buf);
            paragraph_count++;
            text_clear(&para);
            continue;
        }

        /* Blank line — flush paragraph */
        if (is_blank(line)) {
            if (!text_is_empty(&para)) {
                unsigned long h = hash_str(para.buf);
                sprintf(hash_str_buf, "%lu", h);
                sprintf(uuid, "%ld-%lu", (long)time(NULL), h);
                insert_paragraph(db, doc_id, current_section(ctx), paragraph_ord++, global_counter++,
                                 para.buf, para_is_code, para_is_bq, para_is_table, para_is_list, fence_lang, uuid, hash_str_buf);
                paragraph_count++;
                text_clear(&para);
                para_is_code = para_is_bq = para_is_table = para_is_list = 0;
                fence_lang[0] = 0;
            }
            continue;
        }

        /* Classify paragraph type from first line */
        if (text_is_empty(&para)) {
            if (is_blockquote(line))
                para_is_bq = 1;
            else if (is_table_row(line))
                para_is_table = 1;
            else if (is_list_item(line))
                para_is_list = 1;
        }

        text_append(&para, line);
    }

    /* Flush remaining paragraph */
    if (!text_is_empty(&para)) {
        unsigned long h = hash_str(para.buf);
        sprintf(hash_str_buf, "%lu", h);
        sprintf(uuid, "%ld-%lu", (long)time(NULL), h);
        insert_paragraph(db, doc_id, current_section(ctx), paragraph_ord++, global_counter++,
                         para.buf, para_is_code, para_is_bq, para_is_table, para_is_list, fence_lang, uuid, hash_str_buf);
        paragraph_count++;
    }

    /* Update document counts */
    update_document_counts(db, doc_id, section_count, paragraph_count);

    /* Update line count */
    sqlite3_reset(stmt_update_linecount);
    sqlite3_bind_int(stmt_update_linecount, 1, line_count);
    sqlite3_bind_int(stmt_update_linecount, 2, doc_id);
    sqlite3_step(stmt_update_linecount);

    linebuf_free(&lb);
    text_free(&para);
    fclose(fp);

    printf("  Imported: %s (%d lines, %d sections, %d paragraphs)\n",
           filename, line_count, section_count, paragraph_count);
}

/* ═══ Part 4: SQLite Insertion + Transactions ═══ */

static void cmd_import(sqlite3 *db, char **files, int n_files) {
    MergeContext ctx;
    ctx.db = db;
    ctx.stack_count = 0;

    exec_sql(db, "BEGIN;");
    for (int i = 0; i < n_files; i++) {
        parse_file(db, &ctx, files[i]);
    }
    exec_sql(db, "COMMIT;");
    printf("Import complete: %d file(s)\n", n_files);
}

/* ═══ Part 5: Exporter — Tree Traversal, Markdown Regeneration ═══ */

static void export_section_tree(sqlite3 *db, FILE *out, int doc_id, int parent_id, int *ord_counter) {
    sqlite3_reset(stmt_export_section);
    sqlite3_bind_int(stmt_export_section, 1, doc_id);
    sqlite3_bind_int(stmt_export_section, 2, parent_id);

    while (sqlite3_step(stmt_export_section) == SQLITE_ROW) {
        int sec_id = sqlite3_column_int(stmt_export_section, 0);
        int level = sqlite3_column_int(stmt_export_section, 1);
        const unsigned char *title = sqlite3_column_text(stmt_export_section, 2);

        for (int i = 0; i < level; i++)
            fputc('#', out);
        fprintf(out, " %s\n", title ? (const char *)title : "");
        fprintf(out, "\n");

        /* Print paragraphs in this section */
        sqlite3_reset(stmt_export_paragraph);
        sqlite3_bind_int(stmt_export_paragraph, 1, sec_id);

        while (sqlite3_step(stmt_export_paragraph) == SQLITE_ROW) {
            const unsigned char *text = sqlite3_column_text(stmt_export_paragraph, 0);
            int is_code = sqlite3_column_int(stmt_export_paragraph, 1);
            int is_bq = sqlite3_column_int(stmt_export_paragraph, 2);
            int is_table = sqlite3_column_int(stmt_export_paragraph, 3);
            int is_list = sqlite3_column_int(stmt_export_paragraph, 4);
            const unsigned char *lang = sqlite3_column_text(stmt_export_paragraph, 5);
            if (text) {
                if (is_code) {
                    fprintf(out, "```%s\n", lang ? (const char *)lang : "");
                    fprintf(out, "%s\n", (const char *)text);
                    fprintf(out, "```\n\n");
                } else if (is_bq) {
                    fprintf(out, "%s\n", (const char *)text);
                    fprintf(out, "\n");
                } else {
                    fprintf(out, "%s\n", (const char *)text);
                    fprintf(out, "\n");
                }
            }
        }

        (*ord_counter)++;

        /* Recurse into children */
        export_section_tree(db, out, doc_id, sec_id, ord_counter);
    }
}

static void export_root_paragraphs(sqlite3 *db, FILE *out, int doc_id) {
    sqlite3_reset(stmt_export_root_para);
    sqlite3_bind_int(stmt_export_root_para, 1, doc_id);

    while (sqlite3_step(stmt_export_root_para) == SQLITE_ROW) {
        const unsigned char *text = sqlite3_column_text(stmt_export_root_para, 0);
        int is_code = sqlite3_column_int(stmt_export_root_para, 1);
        int is_bq = sqlite3_column_int(stmt_export_root_para, 2);
        const unsigned char *lang = sqlite3_column_text(stmt_export_root_para, 5);
        if (text) {
            if (is_code) {
                fprintf(out, "```%s\n", lang ? (const char *)lang : "");
                fprintf(out, "%s\n", (const char *)text);
                fprintf(out, "```\n\n");
            } else {
                fprintf(out, "%s\n", (const char *)text);
                fprintf(out, "\n");
            }
        }
    }
}

static void cmd_export(sqlite3 *db, const char *output_path) {
    FILE *out = fopen(output_path, "w");
    if (!out) {
        die("cannot open output file for writing");
    }

    sqlite3_stmt *doc_stmt;
    sqlite3_prepare_v2(db,
        "SELECT id, name FROM document ORDER BY id;",
        -1, &doc_stmt, NULL);

    int ord_counter = 0;
    int first_doc = 1;

    while (sqlite3_step(doc_stmt) == SQLITE_ROW) {
        int doc_id = sqlite3_column_int(doc_stmt, 0);
        const unsigned char *name = sqlite3_column_text(doc_stmt, 1);

        if (!first_doc) {
            fprintf(out, "\n---\n\n");
        }
        first_doc = 0;

        fprintf(out, "<!-- Document: %s -->\n\n", name ? (const char *)name : "");

        export_root_paragraphs(db, out, doc_id);
        export_section_tree(db, out, doc_id, 0, &ord_counter);
    }

    sqlite3_finalize(doc_stmt);
    fclose(out);
    printf("Export complete: %s (%d sections)\n", output_path, ord_counter);
}

/* ═══ Part 5b: Dump, Stats, Sections ═══ */

static void cmd_dump(sqlite3 *db) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db,
        "SELECT d.name, s.title, p.text, p.is_code, p.is_blockquote, p.is_table, p.is_list "
        "FROM paragraph p "
        "LEFT JOIN section s ON s.id = p.section_id "
        "LEFT JOIN document d ON d.id = p.document_id "
        "ORDER BY d.id, s.ord, p.ord;",
        -1, &stmt, NULL);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const unsigned char *doc = sqlite3_column_text(stmt, 0);
        const unsigned char *sec = sqlite3_column_text(stmt, 1);
        const unsigned char *txt = sqlite3_column_text(stmt, 2);
        int is_code = sqlite3_column_int(stmt, 3);
        int is_bq = sqlite3_column_int(stmt, 4);
        int is_table = sqlite3_column_int(stmt, 5);
        int is_list = sqlite3_column_int(stmt, 6);

        printf("--------------------------------------------------\n");
        printf("DOC     : %s\n", doc ? (const char *)doc : "");
        printf("SECTION : %s\n", sec ? (const char *)sec : "<root>");
        if (is_code) printf("TYPE    : CODE\n");
        else if (is_bq) printf("TYPE    : BLOCKQUOTE\n");
        else if (is_table) printf("TYPE    : TABLE\n");
        else if (is_list) printf("TYPE    : LIST\n");
        else printf("TYPE    : TEXT\n");
        printf("%s\n\n", txt ? (const char *)txt : "");
    }
    sqlite3_finalize(stmt);
}

static void cmd_stats(sqlite3 *db) {
    sqlite3_stmt *stmt;

    printf("=== MDMERGE DATABASE STATS ===\n\n");

    /* Single query for all paragraph type counts */
    sqlite3_prepare_v2(db,
        "SELECT COUNT(*) FROM document;",
        -1, &stmt, NULL);
    sqlite3_step(stmt);
    printf("Documents  : %d\n", sqlite3_column_int(stmt, 0));
    sqlite3_finalize(stmt);

    sqlite3_prepare_v2(db,
        "SELECT COUNT(*) FROM section;",
        -1, &stmt, NULL);
    sqlite3_step(stmt);
    printf("Sections   : %d\n", sqlite3_column_int(stmt, 0));
    sqlite3_finalize(stmt);

    sqlite3_prepare_v2(db,
        "SELECT COUNT(*), SUM(is_code), SUM(is_blockquote), SUM(is_table), SUM(is_list) FROM paragraph;",
        -1, &stmt, NULL);
    sqlite3_step(stmt);
    printf("Paragraphs : %d\n", sqlite3_column_int(stmt, 0));
    printf("  Code     : %d\n", sqlite3_column_int(stmt, 1));
    printf("  Blockq   : %d\n", sqlite3_column_int(stmt, 2));
    printf("  Table    : %d\n", sqlite3_column_int(stmt, 3));
    printf("  List     : %d\n", sqlite3_column_int(stmt, 4));
    sqlite3_finalize(stmt);

    sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM semantic_log;", -1, &stmt, NULL);
    sqlite3_step(stmt);
    printf("\nSemantic ops: %d\n", sqlite3_column_int(stmt, 0));
    sqlite3_finalize(stmt);

    printf("\n--- Per-document breakdown ---\n");
    sqlite3_prepare_v2(db,
        "SELECT id, name, line_count, section_count, paragraph_count FROM document ORDER BY id;",
        -1, &stmt, NULL);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        printf("  [%d] %s (%d lines, %d sections, %d paragraphs)\n",
               sqlite3_column_int(stmt, 0),
               sqlite3_column_text(stmt, 1),
               sqlite3_column_int(stmt, 2),
               sqlite3_column_int(stmt, 3),
               sqlite3_column_int(stmt, 4));
    }
    sqlite3_finalize(stmt);
}

static void cmd_sections(sqlite3 *db) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db,
        "SELECT s.id, d.name, s.parent_id, s.level, s.ord, s.title "
        "FROM section s JOIN document d ON d.id = s.document_id "
        "ORDER BY d.id, s.ord;",
        -1, &stmt, NULL);

    printf("=== SECTION TREE ===\n\n");
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int id = sqlite3_column_int(stmt, 0);
        const char *doc = (const char *)sqlite3_column_text(stmt, 1);
        int parent = sqlite3_column_int(stmt, 2);
        int level = sqlite3_column_int(stmt, 3);
        int ord = sqlite3_column_int(stmt, 4);
        const char *title = (const char *)sqlite3_column_text(stmt, 5);

        for (int i = 0; i < level; i++)
            printf("  ");
        printf("[%d] %s (parent=%d, ord=%d) — %s\n", id, doc, parent, ord, title);
    }
    sqlite3_finalize(stmt);
}

/* ═══ Part 6: Semantic Interface ═══ */

static void semantic_move_paragraph(sqlite3 *db, int para_id, int new_section_id, int new_ord) {
    sqlite3_reset(stmt_move_para);
    sqlite3_bind_int(stmt_move_para, 1, new_section_id);
    sqlite3_bind_int(stmt_move_para, 2, new_ord);
    sqlite3_bind_int(stmt_move_para, 3, para_id);
    sqlite3_step(stmt_move_para);
    log_semantic(db, "move_paragraph", para_id, new_section_id, "Moved paragraph to new section");
    printf("  Moved paragraph %d -> section %d (ord %d)\n", para_id, new_section_id, new_ord);
}

static void semantic_merge_sections(sqlite3 *db, int src_section_id, int tgt_section_id) {
    if (src_section_id == tgt_section_id) {
        printf("  Cannot merge section with itself\n");
        return;
    }

    sqlite3_reset(stmt_update_para_sec);
    sqlite3_bind_int(stmt_update_para_sec, 1, tgt_section_id);
    sqlite3_bind_int(stmt_update_para_sec, 2, src_section_id);
    sqlite3_step(stmt_update_para_sec);

    int tgt_parent = 0;
    sqlite3_reset(stmt_select_parent);
    sqlite3_bind_int(stmt_select_parent, 1, tgt_section_id);
    if (sqlite3_step(stmt_select_parent) == SQLITE_ROW)
        tgt_parent = sqlite3_column_int(stmt_select_parent, 0);

    sqlite3_reset(stmt_update_sec_parent);
    sqlite3_bind_int(stmt_update_sec_parent, 1, tgt_parent);
    sqlite3_bind_int(stmt_update_sec_parent, 2, src_section_id);
    sqlite3_step(stmt_update_sec_parent);

    sqlite3_reset(stmt_delete_sec);
    sqlite3_bind_int(stmt_delete_sec, 1, src_section_id);
    sqlite3_step(stmt_delete_sec);

    log_semantic(db, "merge_section", src_section_id, tgt_section_id, "Merged sections");
    printf("  Merged section %d -> %d\n", src_section_id, tgt_section_id);
}

static void semantic_rename_section(sqlite3 *db, int section_id, const char *new_title) {
    sqlite3_reset(stmt_rename_sec);
    sqlite3_bind_text(stmt_rename_sec, 1, new_title, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt_rename_sec, 2, section_id);
    sqlite3_step(stmt_rename_sec);
    log_semantic(db, "rename_section", section_id, 0, new_title);
    printf("  Renamed section %d -> '%s'\n", section_id, new_title);
}

static void semantic_reorder_section(sqlite3 *db, int section_id, int new_ord) {
    sqlite3_reset(stmt_reorder_sec);
    sqlite3_bind_int(stmt_reorder_sec, 1, new_ord);
    sqlite3_bind_int(stmt_reorder_sec, 2, section_id);
    sqlite3_step(stmt_reorder_sec);
    log_semantic(db, "reorder_section", section_id, new_ord, "Reordered section");
    printf("  Reordered section %d -> ord %d\n", section_id, new_ord);
}

static void semantic_delete_paragraph(sqlite3 *db, int para_id, const char *reason) {
    sqlite3_reset(stmt_delete_para);
    sqlite3_bind_int(stmt_delete_para, 1, para_id);
    sqlite3_step(stmt_delete_para);
    log_semantic(db, "delete_paragraph", para_id, 0, reason);
    printf("  Deleted paragraph %d (%s)\n", para_id, reason);
}

static void semantic_add_section(sqlite3 *db, int doc_id, int parent_id, int level,
                                 int ord, const char *title) {
    int new_id = insert_section(db, doc_id, parent_id, level, ord, 0, title);
    log_semantic(db, "add_section", new_id, parent_id, title);
    printf("  Added section %d '%s' under parent %d\n", new_id, title, parent_id);
}

static void cmd_semantic(sqlite3 *db) {
    printf("=== SEMANTIC INTERFACE ===\n\n");
    printf("Available operations (call from external AI):\n\n");
    printf("  move_paragraph(para_id, new_section_id, new_ord)\n");
    printf("  merge_sections(src_section_id, tgt_section_id)\n");
    printf("  rename_section(section_id, new_title)\n");
    printf("  reorder_section(section_id, new_ord)\n");
    printf("  delete_paragraph(para_id, reason)\n");
    printf("  add_section(doc_id, parent_id, level, ord, title)\n\n");
    printf("All operations are logged in semantic_log table.\n\n");

    printf("--- Current semantic log ---\n");
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db,
        "SELECT id, action, source_id, target_id, note, date_applied "
        "FROM semantic_log ORDER BY id DESC LIMIT 20;",
        -1, &stmt, NULL);
    int count = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        printf("  [%d] %s: src=%d tgt=%d '%s' (%s)\n",
               sqlite3_column_int(stmt, 0),
               sqlite3_column_text(stmt, 1),
               sqlite3_column_int(stmt, 2),
               sqlite3_column_int(stmt, 3),
               sqlite3_column_text(stmt, 4),
               sqlite3_column_text(stmt, 5));
        count++;
    }
    if (count == 0)
        printf("  (no semantic operations yet)\n");
    sqlite3_finalize(stmt);

    printf("\n--- All paragraphs (for AI inspection) ---\n");
    sqlite3_prepare_v2(db,
        "SELECT p.id, p.document_id, p.section_id, p.ord, "
        "       LENGTH(p.text) as text_len, "
        "       SUBSTR(p.text, 1, 80) as preview, "
        "       s.title as sec_title "
        "FROM paragraph p "
        "LEFT JOIN section s ON s.id = p.section_id "
        "ORDER BY p.document_id, p.section_id, p.ord;",
        -1, &stmt, NULL);
    count = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        printf("  P[%d] doc=%d sec=%d(%s) ord=%d len=%d: %s...\n",
               sqlite3_column_int(stmt, 0),
               sqlite3_column_int(stmt, 1),
               sqlite3_column_int(stmt, 2),
               sqlite3_column_text(stmt, 6) ? (const char *)sqlite3_column_text(stmt, 6) : "<root>",
               sqlite3_column_int(stmt, 3),
               sqlite3_column_int(stmt, 4),
               (const char *)sqlite3_column_text(stmt, 5));
        count++;
    }
    printf("  Total: %d paragraphs\n", count);
    sqlite3_finalize(stmt);
}

/* ═══ Main — CLI dispatch ═══ */

static void usage(void) {
    printf("mdmerge v%s — Markdown Structured SQLite Importer/Exporter\n\n", VERSION);
    printf("Usage:\n");
    printf("  mdmerge import  file1.md [file2.md ...] output.db\n");
    printf("  mdmerge export  input.db output.md\n");
    printf("  mdmerge dump    input.db\n");
    printf("  mdmerge stats   input.db\n");
    printf("  mdmerge sections input.db\n");
    printf("  mdmerge semantic input.db\n");
    printf("\nCommands:\n");
    printf("  import   — Parse .md files into SQLite (document->section->paragraph)\n");
    printf("  export   — Reconstruct .md from SQLite (tree traversal)\n");
    printf("  dump     — Human-readable dump of all paragraphs\n");
    printf("  stats    — Database statistics\n");
    printf("  sections — Section tree with IDs and parents\n");
    printf("  semantic — Semantic interface: list paragraphs, show log, AI hooks\n");
    printf("\nSchema:\n");
    printf("  document(id, name, line_count, section_count, paragraph_count, date_imported)\n");
    printf("  section(id, document_id, parent_id, level, title, ord)\n");
    printf("  paragraph(id, document_id, section_id, ord, text, is_code, is_blockquote, is_table, is_list)\n");
    printf("  semantic_log(id, action, source_id, target_id, note, date_applied)\n");
}

int main(int argc, char **argv) {
    if (argc < 3) {
        usage();
        return 1;
    }

    const char *cmd = argv[1];

    if (strcmp(cmd, "import") == 0) {
        if (argc < 4) {
            usage();
            return 1;
        }
        const char *db_path = argv[argc - 1];
        int n_files = argc - 3;
        char **files = &argv[2];

        sqlite3 *db;
        if (sqlite3_open(db_path, &db) != SQLITE_OK)
            die("cannot open database");
        db_init(db);
        stmt_init(db);
        printf("Importing %d file(s) into %s\n", n_files, db_path);
        cmd_import(db, files, n_files);
        stmt_cleanup();
        sqlite3_close(db);
        return 0;
    }

    if (strcmp(cmd, "export") == 0) {
        if (argc < 4) {
            usage();
            return 1;
        }
        const char *db_path = argv[2];
        const char *out_path = argv[3];

        sqlite3 *db;
        if (sqlite3_open(db_path, &db) != SQLITE_OK)
            die("cannot open database");
        stmt_init(db);
        cmd_export(db, out_path);
        stmt_cleanup();
        sqlite3_close(db);
        return 0;
    }

    if (strcmp(cmd, "dump") == 0) {
        if (argc < 3) {
            usage();
            return 1;
        }
        sqlite3 *db;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK)
            die("cannot open database");
        cmd_dump(db);
        sqlite3_close(db);
        return 0;
    }

    if (strcmp(cmd, "stats") == 0) {
        if (argc < 3) {
            usage();
            return 1;
        }
        sqlite3 *db;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK)
            die("cannot open database");
        cmd_stats(db);
        sqlite3_close(db);
        return 0;
    }

    if (strcmp(cmd, "sections") == 0) {
        if (argc < 3) {
            usage();
            return 1;
        }
        sqlite3 *db;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK)
            die("cannot open database");
        cmd_sections(db);
        sqlite3_close(db);
        return 0;
    }

    if (strcmp(cmd, "semantic") == 0) {
        if (argc < 3) {
            usage();
            return 1;
        }
        sqlite3 *db;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK)
            die("cannot open database");
        cmd_semantic(db);
        sqlite3_close(db);
        return 0;
    }

    usage();
    return 1;
}
