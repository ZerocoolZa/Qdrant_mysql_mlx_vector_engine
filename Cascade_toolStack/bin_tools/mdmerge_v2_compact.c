/*
 * mdmerge.c v2.0
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <sqlite3.h>

#define MAX_STACK 64
#define MAX_HEADING 1024
#define VERSION "2.0"

typedef struct { int level; int id; } SectionEntry;
typedef struct { sqlite3 *db; SectionEntry stack[MAX_STACK]; int stack_count; } MergeContext;

static void die(const char *msg) { fprintf(stderr, "mdmerge: %s\n", msg); exit(1); }
static void die_sqlite(sqlite3 *db, const char *ctx) { fprintf(stderr, "mdmerge: SQLite error in %s: %s\n", ctx, sqlite3_errmsg(db)); exit(1); }

static int exec_sql(sqlite3 *db, const char *sql) {
    char *err = NULL;
    if (sqlite3_exec(db, sql, NULL, NULL, &err) != SQLITE_OK) {
        fprintf(stderr, "mdmerge: SQL error: %s\n", err ? err : "(null)");
        sqlite3_free(err);
        return 0;
    }
    return 1;
}

static int db_init(sqlite3 *db) {
    exec_sql(db, "PRAGMA journal_mode=WAL;");
    exec_sql(db, "PRAGMA synchronous=OFF;");
    exec_sql(db, "PRAGMA foreign_keys=ON;");
    exec_sql(db, "CREATE TABLE IF NOT EXISTS document(id INTEGER PRIMARY KEY,name TEXT NOT NULL,line_count INTEGER DEFAULT 0,section_count INTEGER DEFAULT 0,paragraph_count INTEGER DEFAULT 0,date_imported TEXT DEFAULT CURRENT_TIMESTAMP);");
    exec_sql(db, "CREATE TABLE IF NOT EXISTS section(id INTEGER PRIMARY KEY,document_id INTEGER NOT NULL,parent_id INTEGER DEFAULT 0,level INTEGER NOT NULL,title TEXT NOT NULL,ord INTEGER DEFAULT 0,FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE);");
    exec_sql(db, "CREATE TABLE IF NOT EXISTS paragraph(id INTEGER PRIMARY KEY,document_id INTEGER NOT NULL,section_id INTEGER DEFAULT 0,ord INTEGER DEFAULT 0,text TEXT NOT NULL,is_code INTEGER DEFAULT 0,is_blockquote INTEGER DEFAULT 0,is_table INTEGER DEFAULT 0,is_list INTEGER DEFAULT 0,FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE);");
    exec_sql(db, "CREATE TABLE IF NOT EXISTS semantic_log(id INTEGER PRIMARY KEY,action TEXT,source_id INTEGER,target_id INTEGER,note TEXT,date_applied TEXT DEFAULT CURRENT_TIMESTAMP);");
    exec_sql(db, "CREATE INDEX IF NOT EXISTS idx_section_doc ON section(document_id);");
    exec_sql(db, "CREATE INDEX IF NOT EXISTS idx_section_parent ON section(parent_id);");
    exec_sql(db, "CREATE INDEX IF NOT EXISTS idx_para_doc ON paragraph(document_id);");
    exec_sql(db, "CREATE INDEX IF NOT EXISTS idx_para_section ON paragraph(section_id);");
    return 1;
}

static int insert_document(sqlite3 *db, const char *name, int lc) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "INSERT INTO document(name,line_count) VALUES(?,?);", -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, name, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, lc);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    return (int)sqlite3_last_insert_rowid(db);
}

static void update_doc_counts(sqlite3 *db, int did, int sc, int pc) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "UPDATE document SET section_count=?,paragraph_count=? WHERE id=?;", -1, &stmt, NULL);
    sqlite3_bind_int(stmt, 1, sc); sqlite3_bind_int(stmt, 2, pc); sqlite3_bind_int(stmt, 3, did);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
}

static int insert_section(sqlite3 *db, int doc, int parent, int level, int ord, const char *title) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "INSERT INTO section(document_id,parent_id,level,ord,title) VALUES(?,?,?,?,?);", -1, &stmt, NULL);
    sqlite3_bind_int(stmt, 1, doc); sqlite3_bind_int(stmt, 2, parent);
    sqlite3_bind_int(stmt, 3, level); sqlite3_bind_int(stmt, 4, ord);
    sqlite3_bind_text(stmt, 5, title, -1, SQLITE_TRANSIENT);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
    return (int)sqlite3_last_insert_rowid(db);
}

static void insert_paragraph(sqlite3 *db, int doc, int sec, int ord, const char *text, int ic, int ib, int it, int il) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "INSERT INTO paragraph(document_id,section_id,ord,text,is_code,is_blockquote,is_table,is_list) VALUES(?,?,?,?,?,?,?,?);", -1, &stmt, NULL);
    sqlite3_bind_int(stmt, 1, doc); sqlite3_bind_int(stmt, 2, sec);
    sqlite3_bind_int(stmt, 3, ord); sqlite3_bind_text(stmt, 4, text, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 5, ic); sqlite3_bind_int(stmt, 6, ib);
    sqlite3_bind_int(stmt, 7, it); sqlite3_bind_int(stmt, 8, il);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
}

static void log_semantic(sqlite3 *db, const char *action, int src, int tgt, const char *note) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "INSERT INTO semantic_log(action,source_id,target_id,note) VALUES(?,?,?,?);", -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, action, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, src); sqlite3_bind_int(stmt, 3, tgt);
    sqlite3_bind_text(stmt, 4, note, -1, SQLITE_TRANSIENT);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
}

static int is_blank(const char *s) { while (*s) { if (!isspace((unsigned char)*s)) return 0; s++; } return 1; }

static int heading_level(const char *s) {
    int n = 0;
    while (*s == '#') { n++; s++; }
    if (n == 0 || n > 6) return 0;
    if (*s != ' ' && *s != '\t') return 0;
    return n;
}

static int is_code_fence(const char *s) {
    if (s[0]=='`'&&s[1]=='`'&&s[2]=='`') return 1;
    if (s[0]=='~'&&s[1]=='~'&&s[2]=='~') return 1;
    return 0;
}

static int is_blockquote(const char *s) { return (s[0] == '>'); }
static int is_table_row(const char *s) { return (strchr(s, '|') != NULL && !is_blank(s)); }

static int is_list_item(const char *s) {
    if (*s=='-'&&s[1]==' ') return 1;
    if (*s=='*'&&s[1]==' ') return 1;
    if (*s=='+'&&s[1]==' ') return 1;
    if (isdigit((unsigned char)*s)) {
        const char *p = s + 1;
        while (isdigit((unsigned char)*p)) p++;
        if (*p=='.'&&p[1]==' ') return 1;
    }
    return 0;
}

static int is_hr(const char *s) {
    if (s[0]=='-'&&s[1]=='-'&&s[2]=='-'&&is_blank(s+3)) return 1;
    if (s[0]=='*'&&s[1]=='*'&&s[2]=='*'&&is_blank(s+3)) return 1;
    if (s[0]=='_'&&s[1]=='_'&&s[2]=='_'&&is_blank(s+3)) return 1;
    return 0;
}

static void trim(char *s) {
    int len = (int)strlen(s);
    while (len > 0 && (s[len-1]=='\n'||s[len-1]=='\r'||s[len-1]==' '||s[len-1]=='\t')) { s[len-1]=0; len--; }
}

static char *skip_heading(const char *line) {
    int n = 0;
    while (line[n] == '#') n++;
    while (line[n] == ' ' || line[n] == '\t') n++;
    return (char *)(line + n);
}

typedef struct { char *buf; size_t cap; size_t len; } LineBuf;

static void lb_init(LineBuf *lb) { lb->cap = 4096; lb->buf = (char*)malloc(lb->cap); lb->buf[0]=0; lb->len=0; }
static void lb_free(LineBuf *lb) { free(lb->buf); lb->buf=NULL; lb->cap=0; lb->len=0; }

static int lb_read(LineBuf *lb, FILE *fp) {
    lb->len = 0; lb->buf[0] = 0;
    int c, got = 0;
    while ((c = fgetc(fp)) != EOF) {
        got = 1;
        if (lb->len + 2 >= lb->cap) { lb->cap *= 2; lb->buf = (char*)realloc(lb->buf, lb->cap); }
        lb->buf[lb->len++] = (char)c; lb->buf[lb->len] = 0;
        if (c == '\n') break;
    }
    if (!got) return 0;
    trim(lb->buf); lb->len = strlen(lb->buf);
    return 1;
}

static int cur_section(MergeContext *ctx) { return ctx->stack_count ? ctx->stack[ctx->stack_count-1].id : 0; }
static int par_section(MergeContext *ctx) { return ctx->stack_count ? ctx->stack[ctx->stack_count-1].id : 0; }

static void push_section(MergeContext *ctx, int level, int id) {
    while (ctx->stack_count > 0 && ctx->stack[ctx->stack_count-1].level >= level) ctx->stack_count--;
    ctx->stack[ctx->stack_count].level = level;
    ctx->stack[ctx->stack_count].id = id;
    ctx->stack_count++;
}

static void reset_stack(MergeContext *ctx) { ctx->stack_count = 0; }

typedef struct { char *buf; size_t cap; size_t len; } TextAcc;

static void ta_init(TextAcc *t) { t->cap=8192; t->buf=(char*)malloc(t->cap); t->buf[0]=0; t->len=0; }
static void ta_free(TextAcc *t) { free(t->buf); t->buf=NULL; t->cap=0; t->len=0; }
static void ta_clear(TextAcc *t) { t->buf[0]=0; t->len=0; }
static int ta_empty(TextAcc *t) { return t->len == 0; }

static void ta_append(TextAcc *t, const char *line) {
    size_t ll = strlen(line);
    if (t->len + ll + 2 >= t->cap) {
        while (t->len + ll + 2 >= t->cap) t->cap *= 2;
        t->buf = (char*)realloc(t->buf, t->cap);
    }
    if (t->len > 0) { t->buf[t->len++] = '\n'; t->buf[t->len] = 0; }
    strcat(t->buf, line); t->len += ll;
}

static void parse_file(sqlite3 *db, MergeContext *ctx, const char *filename) {
    FILE *fp = fopen(filename, "r");
    if (!fp) { fprintf(stderr, "mdmerge: cannot open %s\n", filename); return; }
    reset_stack(ctx);
    int doc_id = insert_document(db, filename, 0);
    LineBuf lb; lb_init(&lb);
    TextAcc para; ta_init(&para);
    int s_ord=0, p_ord=0, lc=0, sc=0, pc=0;
    int in_fence=0, p_code=0, p_bq=0, p_tbl=0, p_lst=0;

    while (lb_read(&lb, fp)) {
        lc++;
        char *line = lb.buf;

        if (is_code_fence(line)) {
            if (!ta_empty(&para)) {
                insert_paragraph(db, doc_id, cur_section(ctx), p_ord++, para.buf, p_code, p_bq, p_tbl, p_lst);
                pc++; ta_clear(&para); p_code=p_bq=p_tbl=p_lst=0;
            }
            in_fence = !in_fence; p_code = 1;
            ta_append(&para, line);
            continue;
        }
        if (in_fence) { ta_append(&para, line); continue; }

        int level = heading_level(line);
        if (level) {
            if (!ta_empty(&para)) {
                insert_paragraph(db, doc_id, cur_section(ctx), p_ord++, para.buf, p_code, p_bq, p_tbl, p_lst);
                pc++; ta_clear(&para); p_code=p_bq=p_tbl=p_lst=0;
            }
            char *title = skip_heading(line);
            int sid = insert_section(db, doc_id, par_section(ctx), level, s_ord++, title);
            sc++; push_section(ctx, level, sid); p_ord = 0;
            continue;
        }

        if (is_hr(line)) {
            if (!ta_empty(&para)) {
                insert_paragraph(db, doc_id, cur_section(ctx), p_ord++, para.buf, p_code, p_bq, p_tbl, p_lst);
                pc++; ta_clear(&para); p_code=p_bq=p_tbl=p_lst=0;
            }
            ta_append(&para, line);
            insert_paragraph(db, doc_id, cur_section(ctx), p_ord++, para.buf, 0, 0, 0, 0);
            pc++; ta_clear(&para);
            continue;
        }

        if (is_blank(line)) {
            if (!ta_empty(&para)) {
                insert_paragraph(db, doc_id, cur_section(ctx), p_ord++, para.buf, p_code, p_bq, p_tbl, p_lst);
                pc++; ta_clear(&para); p_code=p_bq=p_tbl=p_lst=0;
            }
            continue;
        }

        if (ta_empty(&para)) {
            if (is_blockquote(line)) p_bq = 1;
            else if (is_table_row(line)) p_tbl = 1;
            else if (is_list_item(line)) p_lst = 1;
        }
        ta_append(&para, line);
    }

    if (!ta_empty(&para)) {
        insert_paragraph(db, doc_id, cur_section(ctx), p_ord++, para.buf, p_code, p_bq, p_tbl, p_lst);
        pc++;
    }

    update_doc_counts(db, doc_id, sc, pc);
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "UPDATE document SET line_count=? WHERE id=?;", -1, &stmt, NULL);
    sqlite3_bind_int(stmt, 1, lc); sqlite3_bind_int(stmt, 2, doc_id);
    sqlite3_step(stmt); sqlite3_finalize(stmt);

    lb_free(&lb); ta_free(&para); fclose(fp);
    printf("  Imported: %s (%d lines, %d sections, %d paragraphs)\n", filename, lc, sc, pc);
}

static void cmd_import(sqlite3 *db, char **files, int n) {
    MergeContext ctx; ctx.db = db; ctx.stack_count = 0;
    exec_sql(db, "BEGIN;");
    for (int i = 0; i < n; i++) parse_file(db, &ctx, files[i]);
    exec_sql(db, "COMMIT;");
    printf("Import complete: %d file(s)\n", n);
}

static void export_tree(sqlite3 *db, FILE *out, int doc_id, int parent_id, int *cnt) {
    sqlite3_stmt *ss;
    sqlite3_prepare_v2(db, "SELECT id,level,title,ord FROM section WHERE document_id=? AND parent_id=? ORDER BY ord;", -1, &ss, NULL);
    sqlite3_bind_int(ss, 1, doc_id); sqlite3_bind_int(ss, 2, parent_id);
    while (sqlite3_step(ss) == SQLITE_ROW) {
        int sid = sqlite3_column_int(ss, 0);
        int level = sqlite3_column_int(ss, 1);
        const unsigned char *title = sqlite3_column_text(ss, 2);
        for (int i = 0; i < level; i++) fputc('#', out);
        fprintf(out, " %s\n\n", title ? (const char*)title : "");
        sqlite3_stmt *ps;
        sqlite3_prepare_v2(db, "SELECT text FROM paragraph WHERE section_id=? ORDER BY ord;", -1, &ps, NULL);
        sqlite3_bind_int(ps, 1, sid);
        while (sqlite3_step(ps) == SQLITE_ROW) {
            const unsigned char *txt = sqlite3_column_text(ps, 0);
            if (txt) { fprintf(out, "%s\n\n", (const char*)txt); }
        }
        sqlite3_finalize(ps);
        (*cnt)++;
        export_tree(db, out, doc_id, sid, cnt);
    }
    sqlite3_finalize(ss);
}

static void export_root_paras(sqlite3 *db, FILE *out, int doc_id) {
    sqlite3_stmt *ps;
    sqlite3_prepare_v2(db, "SELECT text FROM paragraph WHERE document_id=? AND section_id=0 ORDER BY ord;", -1, &ps, NULL);
    sqlite3_bind_int(ps, 1, doc_id);
    while (sqlite3_step(ps) == SQLITE_ROW) {
        const unsigned char *txt = sqlite3_column_text(ps, 0);
        if (txt) { fprintf(out, "%s\n\n", (const char*)txt); }
    }
    sqlite3_finalize(ps);
}

static void cmd_export(sqlite3 *db, const char *out_path) {
    FILE *out = fopen(out_path, "w");
    if (!out) die("cannot open output file");
    sqlite3_stmt *ds;
    sqlite3_prepare_v2(db, "SELECT id,name FROM document ORDER BY id;", -1, &ds, NULL);
    int cnt = 0, first = 1;
    while (sqlite3_step(ds) == SQLITE_ROW) {
        int did = sqlite3_column_int(ds, 0);
        const unsigned char *name = sqlite3_column_text(ds, 1);
        if (!first) fprintf(out, "\n---\n\n");
        first = 0;
        fprintf(out, "<!-- Document: %s -->\n\n", name ? (const char*)name : "");
        export_root_paras(db, out, did);
        export_tree(db, out, did, 0, &cnt);
    }
    sqlite3_finalize(ds); fclose(out);
    printf("Export complete: %s (%d sections)\n", out_path, cnt);
}

static void cmd_dump(sqlite3 *db) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "SELECT d.name,s.title,p.text,p.is_code,p.is_blockquote,p.is_table,p.is_list FROM paragraph p LEFT JOIN section s ON s.id=p.section_id LEFT JOIN document d ON d.id=p.document_id ORDER BY d.id,s.ord,p.ord;", -1, &stmt, NULL);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const unsigned char *doc=sqlite3_column_text(stmt,0), *sec=sqlite3_column_text(stmt,1), *txt=sqlite3_column_text(stmt,2);
        int ic=sqlite3_column_int(stmt,3), ib=sqlite3_column_int(stmt,4), it=sqlite3_column_int(stmt,5), il=sqlite3_column_int(stmt,6);
        printf("--------------------------------------------------\n");
        printf("DOC     : %s\n", doc ? (const char*)doc : "");
        printf("SECTION : %s\n", sec ? (const char*)sec : "<root>");
        printf("TYPE    : %s\n", ic?"CODE":ib?"BLOCKQUOTE":it?"TABLE":il?"LIST":"TEXT");
        printf("%s\n\n", txt ? (const char*)txt : "");
    }
    sqlite3_finalize(stmt);
}

static void cmd_stats(sqlite3 *db) {
    sqlite3_stmt *stmt;
    printf("=== MDMERGE DATABASE STATS ===\n\n");
    const char *q[] = {
        "SELECT COUNT(*) FROM document;",
        "SELECT COUNT(*) FROM section;",
        "SELECT COUNT(*) FROM paragraph;",
        "SELECT COUNT(*) FROM paragraph WHERE is_code=1;",
        "SELECT COUNT(*) FROM paragraph WHERE is_blockquote=1;",
        "SELECT COUNT(*) FROM paragraph WHERE is_table=1;",
        "SELECT COUNT(*) FROM paragraph WHERE is_list=1;",
        "SELECT COUNT(*) FROM semantic_log;",
    };
    const char *lbl[] = {"Documents  ","Sections   ","Paragraphs ","  Code     ","  Blockq   ","  Table    ","  List     ","Semantic ops"};
    for (int i = 0; i < 8; i++) {
        sqlite3_prepare_v2(db, q[i], -1, &stmt, NULL);
        sqlite3_step(stmt);
        if (i == 7) printf("\n");
        printf("%s: %d\n", lbl[i], sqlite3_column_int(stmt, 0));
        sqlite3_finalize(stmt);
    }
    printf("\n--- Per-document breakdown ---\n");
    sqlite3_prepare_v2(db, "SELECT id,name,line_count,section_count,paragraph_count FROM document ORDER BY id;", -1, &stmt, NULL);
    while (sqlite3_step(stmt) == SQLITE_ROW)
        printf("  [%d] %s (%d lines, %d sections, %d paragraphs)\n", sqlite3_column_int(stmt,0), sqlite3_column_text(stmt,1), sqlite3_column_int(stmt,2), sqlite3_column_int(stmt,3), sqlite3_column_int(stmt,4));
    sqlite3_finalize(stmt);
}

static void cmd_sections(sqlite3 *db) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "SELECT s.id,d.name,s.parent_id,s.level,s.ord,s.title FROM section s JOIN document d ON d.id=s.document_id ORDER BY d.id,s.ord;", -1, &stmt, NULL);
    printf("=== SECTION TREE ===\n\n");
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int id=sqlite3_column_int(stmt,0), parent=sqlite3_column_int(stmt,2), level=sqlite3_column_int(stmt,3), ord=sqlite3_column_int(stmt,4);
        const char *doc=(const char*)sqlite3_column_text(stmt,1), *title=(const char*)sqlite3_column_text(stmt,5);
        for (int i = 0; i < level; i++) printf("  ");
        printf("[%d] %s (parent=%d, ord=%d) - %s\n", id, doc, parent, ord, title);
    }
    sqlite3_finalize(stmt);
}

static void sem_move(sqlite3 *db, int pid, int nsid, int nord) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "UPDATE paragraph SET section_id=?,ord=? WHERE id=?;", -1, &stmt, NULL);
    sqlite3_bind_int(stmt,1,nsid); sqlite3_bind_int(stmt,2,nord); sqlite3_bind_int(stmt,3,pid);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
    log_semantic(db, "move_paragraph", pid, nsid, "Moved");
    printf("  Moved paragraph %d -> section %d (ord %d)\n", pid, nsid, nord);
}

static void sem_merge(sqlite3 *db, int src, int tgt) {
    if (src == tgt) { printf("  Cannot merge with itself\n"); return; }
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "UPDATE paragraph SET section_id=? WHERE section_id=?;", -1, &stmt, NULL);
    sqlite3_bind_int(stmt,1,tgt); sqlite3_bind_int(stmt,2,src);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
    int tparent = 0;
    sqlite3_prepare_v2(db, "SELECT parent_id FROM section WHERE id=?;", -1, &stmt, NULL);
    sqlite3_bind_int(stmt,1,tgt);
    if (sqlite3_step(stmt) == SQLITE_ROW) tparent = sqlite3_column_int(stmt,0);
    sqlite3_finalize(stmt);
    sqlite3_prepare_v2(db, "UPDATE section SET parent_id=? WHERE parent_id=?;", -1, &stmt, NULL);
    sqlite3_bind_int(stmt,1,tparent); sqlite3_bind_int(stmt,2,src);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
    sqlite3_prepare_v2(db, "DELETE FROM section WHERE id=?;", -1, &stmt, NULL);
    sqlite3_bind_int(stmt,1,src);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
    log_semantic(db, "merge_section", src, tgt, "Merged");
    printf("  Merged section %d -> %d\n", src, tgt);
}

static void sem_rename(sqlite3 *db, int sid, const char *title) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "UPDATE section SET title=? WHERE id=?;", -1, &stmt, NULL);
    sqlite3_bind_text(stmt,1,title,-1,SQLITE_TRANSIENT); sqlite3_bind_int(stmt,2,sid);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
    log_semantic(db, "rename_section", sid, 0, title);
    printf("  Renamed section %d -> '%s'\n", sid, title);
}

static void sem_reorder(sqlite3 *db, int sid, int nord) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "UPDATE section SET ord=? WHERE id=?;", -1, &stmt, NULL);
    sqlite3_bind_int(stmt,1,nord); sqlite3_bind_int(stmt,2,sid);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
    log_semantic(db, "reorder_section", sid, nord, "Reordered");
    printf("  Reordered section %d -> ord %d\n", sid, nord);
}

static void sem_delete(sqlite3 *db, int pid, const char *reason) {
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, "DELETE FROM paragraph WHERE id=?;", -1, &stmt, NULL);
    sqlite3_bind_int(stmt,1,pid);
    sqlite3_step(stmt); sqlite3_finalize(stmt);
    log_semantic(db, "delete_paragraph", pid, 0, reason);
    printf("  Deleted paragraph %d (%s)\n", pid, reason);
}

static void sem_add_section(sqlite3 *db, int did, int pid, int level, int ord, const char *title) {
    int nid = insert_section(db, did, pid, level, ord, title);
    log_semantic(db, "add_section", nid, pid, title);
    printf("  Added section %d '%s' under parent %d\n", nid, title, pid);
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
    sqlite3_prepare_v2(db, "SELECT id,action,source_id,target_id,note,date_applied FROM semantic_log ORDER BY id DESC LIMIT 20;", -1, &stmt, NULL);
    int count = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        printf("  [%d] %s: src=%d tgt=%d '%s' (%s)\n", sqlite3_column_int(stmt,0), sqlite3_column_text(stmt,1), sqlite3_column_int(stmt,2), sqlite3_column_int(stmt,3), sqlite3_column_text(stmt,4), sqlite3_column_text(stmt,5));
        count++;
    }
    if (count == 0) printf("  (no semantic operations yet)\n");
    sqlite3_finalize(stmt);

    printf("\n--- All paragraphs (for AI inspection) ---\n");
    sqlite3_prepare_v2(db, "SELECT p.id,p.document_id,p.section_id,p.ord,LENGTH(p.text),SUBSTR(p.text,1,80),s.title FROM paragraph p LEFT JOIN section s ON s.id=p.section_id ORDER BY p.document_id,p.section_id,p.ord;", -1, &stmt, NULL);
    count = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        printf("  P[%d] doc=%d sec=%d(%s) ord=%d len=%d: %s...\n",
            sqlite3_column_int(stmt,0), sqlite3_column_int(stmt,1), sqlite3_column_int(stmt,2),
            sqlite3_column_text(stmt,6) ? sqlite3_column_text(stmt,6) : "<root>",
            sqlite3_column_int(stmt,3), sqlite3_column_int(stmt,4), sqlite3_column_text(stmt,5));
        count++;
    }
    printf("  Total: %d paragraphs\n", count);
    sqlite3_finalize(stmt);
}

static void usage(void) {
    printf("mdmerge v%s - Markdown Structured SQLite Importer/Exporter\n\n", VERSION);
    printf("Usage:\n");
    printf("  mdmerge import  file1.md [file2.md ...] output.db\n");
    printf("  mdmerge export  input.db output.md\n");
    printf("  mdmerge dump    input.db\n");
    printf("  mdmerge stats   input.db\n");
    printf("  mdmerge sections input.db\n");
    printf("  mdmerge semantic input.db\n");
    printf("\nSchema:\n");
    printf("  document(id, name, line_count, section_count, paragraph_count, date_imported)\n");
    printf("  section(id, document_id, parent_id, level, title, ord)\n");
    printf("  paragraph(id, document_id, section_id, ord, text, is_code, is_blockquote, is_table, is_list)\n");
    printf("  semantic_log(id, action, source_id, target_id, note, date_applied)\n");
}

int main(int argc, char **argv) {
    if (argc < 3) { usage(); return 1; }
    const char *cmd = argv[1];

    if (strcmp(cmd, "import") == 0) {
        if (argc < 4) { usage(); return 1; }
        const char *dbp = argv[argc-1];
        int nf = argc - 3;
        sqlite3 *db;
        if (sqlite3_open(dbp, &db) != SQLITE_OK) die("cannot open database");
        db_init(db);
        printf("Importing %d file(s) into %s\n", nf, dbp);
        cmd_import(db, &argv[2], nf);
        sqlite3_close(db);
        return 0;
    }
    if (strcmp(cmd, "export") == 0) {
        if (argc < 4) { usage(); return 1; }
        sqlite3 *db;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK) die("cannot open database");
        cmd_export(db, argv[3]);
        sqlite3_close(db);
        return 0;
    }
    if (strcmp(cmd, "dump") == 0) {
        if (argc < 3) { usage(); return 1; }
        sqlite3 *db;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK) die("cannot open database");
        cmd_dump(db); sqlite3_close(db); return 0;
    }
    if (strcmp(cmd, "stats") == 0) {
        if (argc < 3) { usage(); return 1; }
        sqlite3 *db;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK) die("cannot open database");
        cmd_stats(db); sqlite3_close(db); return 0;
    }
    if (strcmp(cmd, "sections") == 0) {
        if (argc < 3) { usage(); return 1; }
        sqlite3 *db;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK) die("cannot open database");
        cmd_sections(db); sqlite3_close(db); return 0;
    }
    if (strcmp(cmd, "semantic") == 0) {
        if (argc < 3) { usage(); return 1; }
        sqlite3 *db;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK) die("cannot open database");
        cmd_semantic(db); sqlite3_close(db); return 0;
    }
    usage();
    return 1;
}
