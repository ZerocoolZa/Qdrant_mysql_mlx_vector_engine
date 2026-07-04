//[@GHOST]{file_path="Cascade_toolStack/vbast/mysql_store.c" date="2026-06-29" author="Devin" session_id="vbast-bcl-stamp" context="Write AST/BCL/graph results to MySQL bcl_ir tables"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="mysql_store.c" domain="vbast" authority="MysqlStore"}
//[@SUMMARY]{summary="MySQL store — writes classes, methods, edges, units to bcl_ir tables"}
//[@CLASS]{class="MysqlStore" domain="vbast" authority="single"}
//[@METHOD]{methods="store_all,store_classes,store_methods,store_edges,store_unit,connect_db"}
//
// mysql_store.c — write AST/BCL/graph results to MySQL bcl_ir tables
//
// Aligned to the EXISTING bcl_ir schema:
//   bcl_codebases: lookup or create by name (derived from file path)
//   bcl_classes:   codebase_id (NOT NULL), class_name, file_path, bases, method_count, line_start, line_end
//   bcl_methods:   codebase_id (NOT NULL), bcl_class_id, method_id (filepath::Class.method),
//                  method_id_hash (md5-ish 16-char hex), method_name, class_name, file_path,
//                  method_type, is_async, line_start, line_end
//   bcl_edges:     codebase_id (NOT NULL), bcl_method_id, source_method_id (filepath::Class.method),
//                  source_method_row_id, target, edge_type, certainty, line_number

#include "vbast.h"

#ifdef CASCADE_USE_MYSQL
#include <mysql.h>
#endif

/* ════════════════════════════════════════════
 * HELPERS
 * ════════════════════════════════════════════ */

#ifdef CASCADE_USE_MYSQL

static void escape_str(MYSQL *conn, const char *in, char *out, size_t out_sz) {
    mysql_real_escape_string(conn, out, in, (unsigned long)strlen(in));
    (void)out_sz;
}

/* Simple hash — 16-char hex from a string (FNV-1a variant) */
static void make_hash(const char *input, char *out) {
    unsigned long h1 = 2166136261UL;
    unsigned long h2 = 14695981039346656037UL;
    for (const char *p = input; *p; p++) {
        h1 ^= (unsigned char)*p; h1 *= 16777619UL;
        h2 ^= (unsigned char)*p; h2 *= 1099511628211UL;
    }
    snprintf(out, 17, "%08lx%08lx", h1 & 0xFFFFFFFFUL, h2 & 0xFFFFFFFFUL);
    out[16] = '\0';
}

/* Derive codebase name from file path — use parent directory name */
static void codebase_name_from_path(const char *file_path, char *out, size_t out_sz) {
    /* find last / */
    const char *last_slash = strrchr(file_path, '/');
    if (!last_slash) { strncpy(out, "unknown", out_sz - 1); return; }
    /* find second-to-last / */
    const char *prev = NULL;
    for (const char *p = file_path; p < last_slash; p++) {
        if (*p == '/') prev = p;
    }
    if (prev) {
        size_t len = last_slash - prev - 1;
        if (len >= out_sz) len = out_sz - 1;
        memcpy(out, prev + 1, len);
        out[len] = '\0';
    } else {
        strncpy(out, "root", out_sz - 1);
        out[out_sz - 1] = '\0';
    }
}

/* Lookup or create a codebase, return its id */
static int get_or_create_codebase(MYSQL *conn, const char *file_path) {
    char cb_name[256];
    codebase_name_from_path(file_path, cb_name, sizeof(cb_name));

    char sql[512];
    snprintf(sql, sizeof(sql), "SELECT id FROM bcl_codebases WHERE name = '%s'", cb_name);
    if (mysql_query(conn, sql)) return -1;
    MYSQL_RES *res = mysql_store_result(conn);
    if (res && mysql_num_rows(res) > 0) {
        MYSQL_ROW row = mysql_fetch_row(res);
        int id = atoi(row[0]);
        mysql_free_result(res);
        return id;
    }
    if (res) mysql_free_result(res);

    /* create */
    char ename[512];
    escape_str(conn, cb_name, ename, sizeof(ename));
    char epath[1024];
    escape_str(conn, file_path, epath, sizeof(epath));
    snprintf(sql, sizeof(sql),
        "INSERT INTO bcl_codebases (name, root_path) VALUES ('%s', '%s')",
        ename, epath);
    if (mysql_query(conn, sql)) {
        fprintf(stderr, "ERROR: codebase create: %s\n", mysql_error(conn));
        return -1;
    }
    return (int)mysql_insert_id(conn);
}

/* Build method_id string: filepath::Class.method */
static void make_method_id(const char *file_path, const char *class_name,
                           const char *method_name, char *out, size_t out_sz) {
    snprintf(out, out_sz, "%s::%s.%s",
             file_path,
             class_name[0] ? class_name : "<module>",
             method_name);
}

/* Determine method type: CORE, INIT, CLEANUP, LINK, IO */
static const char *method_type(const char *name) {
    if (strcmp(name, "__init__") == 0) return "INIT";
    if (strcmp(name, "__del__") == 0 || strcmp(name, "cleanup") == 0 ||
        strcmp(name, "close") == 0 || strcmp(name, "destroy") == 0) return "CLEANUP";
    if (strcmp(name, "Run") == 0) return "CORE";
    return "LINK";
}

/* ════════════════════════════════════════════
 * PUBLIC API
 * ════════════════════════════════════════════ */

int mysql_store_results(ParseResult *r, const char *db_name) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) {
        fprintf(stderr, "ERROR: mysql_init failed\n");
        return 0;
    }
    if (!mysql_real_connect(conn, "localhost", "root", "",
                            db_name ? db_name : "bcl_ir", 3306, NULL, 0)) {
        fprintf(stderr, "ERROR: mysql connect: %s\n", mysql_error(conn));
        mysql_close(conn);
        return 0;
    }

    int codebase_id = get_or_create_codebase(conn, r->file_path);
    if (codebase_id < 0) {
        mysql_close(conn);
        return 0;
    }

    int ok = 1;
    if (!mysql_store_classes(r, conn, codebase_id)) ok = 0;
    if (!mysql_store_methods(r, conn, codebase_id)) ok = 0;
    if (!mysql_store_edges(r, conn, codebase_id)) ok = 0;

    /* update codebase stats */
    if (ok) {
        char sql[512];
        snprintf(sql, sizeof(sql),
            "UPDATE bcl_codebases SET class_count=%d, method_count=%d, edge_count=%d, "
            "scanned_at=NOW() WHERE id=%d",
            r->class_count, r->method_count, r->edge_count, codebase_id);
        mysql_query(conn, sql); /* best effort */
    }

    mysql_close(conn);
    return ok;
}

int mysql_store_classes(ParseResult *r, void *conn_ptr, int codebase_id) {
    MYSQL *conn = (MYSQL *)conn_ptr;
    for (int i = 0; i < r->class_count; i++) {
        ClassInfo *c = &r->classes[i];
        char ename[256], epath[1024], ebases[1024];
        escape_str(conn, c->name, ename, sizeof(ename));
        escape_str(conn, r->file_path, epath, sizeof(epath));
        escape_str(conn, c->bases, ebases, sizeof(ebases));

        char sql[2048];
        snprintf(sql, sizeof(sql),
            "INSERT IGNORE INTO bcl_classes (codebase_id, class_name, file_path, bases, "
            "method_count, line_start, line_end) VALUES (%d, '%s', '%s', '%s', %d, %d, %d)",
            codebase_id, ename, epath, ebases, c->method_count, c->line_start, c->line_end);
        if (mysql_query(conn, sql)) {
            fprintf(stderr, "ERROR: bcl_classes insert: %s\n", mysql_error(conn));
            return 0;
        }
        /* store the inserted id (0 if duplicate, but that's ok for linking) */
        c->db_id = (int)mysql_insert_id(conn);
        if (c->db_id == 0) {
            /* duplicate — look up existing id */
            snprintf(sql, sizeof(sql),
                "SELECT id FROM bcl_classes WHERE codebase_id=%d AND class_name='%s' AND file_path='%s'",
                codebase_id, ename, epath);
            if (mysql_query(conn, sql) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res && mysql_num_rows(res) > 0) {
                    MYSQL_ROW row = mysql_fetch_row(res);
                    c->db_id = atoi(row[0]);
                    mysql_free_result(res);
                } else if (res) {
                    mysql_free_result(res);
                }
            }
        }
    }
    return 1;
}

int mysql_store_methods(ParseResult *r, void *conn_ptr, int codebase_id) {
    MYSQL *conn = (MYSQL *)conn_ptr;
    for (int i = 0; i < r->method_count; i++) {
        MethodInfo *m = &r->methods[i];
        char method_id[1024];
        make_method_id(r->file_path, m->class_name, m->name, method_id, sizeof(method_id));

        char hash[17];
        make_hash(method_id, hash);

        char ename[256], ecname[256], epath[1024], emid[2048];
        escape_str(conn, m->name, ename, sizeof(ename));
        escape_str(conn, m->class_name, ecname, sizeof(ecname));
        escape_str(conn, r->file_path, epath, sizeof(epath));
        escape_str(conn, method_id, emid, sizeof(emid));

        /* find bcl_class_id by matching class_name + file_path */
        int bcl_class_id = 0;
        for (int ci = 0; ci < r->class_count; ci++) {
            if (strcmp(r->classes[ci].name, m->class_name) == 0) {
                bcl_class_id = r->classes[ci].db_id;
                break;
            }
        }

        const char *mtype = method_type(m->name);

        /* build bcl_class_id value: "NULL" or the integer */
        char class_id_str[32];
        if (bcl_class_id > 0) {
            snprintf(class_id_str, sizeof(class_id_str), "%d", bcl_class_id);
        } else {
            snprintf(class_id_str, sizeof(class_id_str), "NULL");
        }

        char sql[4096];
        snprintf(sql, sizeof(sql),
            "INSERT IGNORE INTO bcl_methods (codebase_id, bcl_class_id, method_id, method_id_hash, "
            "method_name, class_name, file_path, method_type, is_async, line_start, line_end) "
            "VALUES (%d, %s, '%s', '%s', '%s', '%s', '%s', '%s', %d, %d, %d)",
            codebase_id, class_id_str,
            emid, hash, ename, ecname, epath, mtype, m->is_async,
            m->line_start, m->line_end);
        if (mysql_query(conn, sql)) {
            fprintf(stderr, "ERROR: bcl_methods insert: %s\n", mysql_error(conn));
            return 0;
        }
        m->db_id = (int)mysql_insert_id(conn);
        if (m->db_id == 0) {
            /* duplicate — look up existing id */
            snprintf(sql, sizeof(sql),
                "SELECT id FROM bcl_methods WHERE codebase_id=%d AND method_id_hash='%s'",
                codebase_id, hash);
            if (mysql_query(conn, sql) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res && mysql_num_rows(res) > 0) {
                    MYSQL_ROW row = mysql_fetch_row(res);
                    m->db_id = atoi(row[0]);
                    mysql_free_result(res);
                } else if (res) {
                    mysql_free_result(res);
                }
            }
        }
    }
    return 1;
}

int mysql_store_edges(ParseResult *r, void *conn_ptr, int codebase_id) {
    MYSQL *conn = (MYSQL *)conn_ptr;
    for (int i = 0; i < r->edge_count; i++) {
        EdgeInfo *e = &r->edges[i];
        char esrc[2048], etgt[2048], etype[64], ecert[64];
        escape_str(conn, e->source, esrc, sizeof(esrc));
        escape_str(conn, e->target, etgt, sizeof(etgt));
        escape_str(conn, e->edge_type, etype, sizeof(etype));
        escape_str(conn, e->certainty, ecert, sizeof(ecert));

        /* find source_method_row_id by matching source name to a method */
        int src_row_id = 0;
        for (int mi = 0; mi < r->method_count; mi++) {
            /* source is like "ClassName.method_name" */
            char buf[512];
            snprintf(buf, sizeof(buf), "%s.%s", r->methods[mi].class_name, r->methods[mi].name);
            if (strcmp(buf, e->source) == 0) {
                src_row_id = r->methods[mi].db_id;
                break;
            }
        }

        /* build source_method_row_id value: "NULL" or the integer */
        char src_row_str[32];
        if (src_row_id > 0) {
            snprintf(src_row_str, sizeof(src_row_str), "%d", src_row_id);
        } else {
            snprintf(src_row_str, sizeof(src_row_str), "NULL");
        }

        char sql[2048];
        snprintf(sql, sizeof(sql),
            "INSERT INTO bcl_edges (codebase_id, source_method_id, source_method_row_id, "
            "target, edge_type, certainty, line_number) "
            "VALUES (%d, '%s', %s, '%s', '%s', '%s', %d)",
            codebase_id, esrc, src_row_str,
            etgt, etype, ecert, e->line_number);
        if (mysql_query(conn, sql)) {
            fprintf(stderr, "ERROR: bcl_edges insert: %s\n", mysql_error(conn));
            return 0;
        }
    }
    return 1;
}

#else

/* No MySQL — stub functions */
int mysql_store_results(ParseResult *r, const char *db_name) {
    (void)r; (void)db_name;
    fprintf(stderr, "MySQL support not compiled in (use: make mysql)\n");
    return 0;
}
int mysql_store_classes(ParseResult *r, void *conn, int codebase_id) {
    (void)r; (void)conn; (void)codebase_id; return 0;
}
int mysql_store_methods(ParseResult *r, void *conn, int codebase_id) {
    (void)r; (void)conn; (void)codebase_id; return 0;
}
int mysql_store_edges(ParseResult *r, void *conn, int codebase_id) {
    (void)r; (void)conn; (void)codebase_id; return 0;
}

#endif
