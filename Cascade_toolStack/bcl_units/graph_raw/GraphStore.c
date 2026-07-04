//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_graph_store.c" date="2026-06-29" author="Devin" session_id="bcl-c-central-db" context="Write AST/BCL/graph results to MySQL or SQLite — backend selectable via bcl_config.json. Supports :memory: ephemeral mode."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_graph_store.c" domain="bcl_c_engine" authority="GraphStore"}
//[@SUMMARY]{summary="Unified graph store — writes classes, methods, edges, source_files to MySQL or SQLite. Backend selected at runtime via config_global_backend(). Supports :memory: for ephemeral mode."}
//[@CLASS]{class="GraphStore" domain="bcl_c_engine" authority="single"}
//[@METHOD]{method="store_results" type="command"}
//[@METHOD]{method="store_source" type="command"}
//[@METHOD]{method="store_classes" type="helper"}
//[@METHOD]{method="store_methods" type="helper"}
//[@METHOD]{method="store_edges" type="helper"}
//[@METHOD]{method="sqlite_init_schema" type="helper"}
//[@METHOD]{method="sqlite_get_or_create_codebase" type="helper"}
//[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Backend-agnostic store. SQLite + MySQL + :memory:.>][@todos<none>]}

/*
 * bcl_graph_store.c — Unified graph store (MySQL + SQLite + :memory:)
 *
 * Backend selected at runtime via config_global_backend():
 *   "mysql"  → connects to MySQL vb_shared (or configured db)
 *   "sqlite" → opens local SQLite file (or :memory: if no path)
 *
 * Schema (both backends):
 *   bcl_codebases:  id, name, root_path, class_count, method_count, edge_count, scanned_at
 *   bcl_classes:    id, codebase_id, class_name, file_path, bases, method_count, line_start, line_end
 *   bcl_methods:    id, codebase_id, bcl_class_id, method_id, method_id_hash, method_name,
 *                   class_name, file_path, method_type, is_async, line_start, line_end
 *   bcl_edges:      id, codebase_id, source_method_id, source_method_row_id, target,
 *                   edge_type, certainty, line_number
 *   source_files:   id, codebase_id, file_path, source_text, source_len, language, stored_at
 */

#include "bcl_engine.h"
#include <sqlite3.h>

#ifdef CASCADE_USE_MYSQL
#include <mysql.h>
#endif

/* ════════════════════════════════════════════
 * SHARED HELPERS (backend-independent)
 * ════════════════════════════════════════════ */

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

static void codebase_name_from_path(const char *file_path, char *out, size_t out_sz) {
    const char *last_slash = strrchr(file_path, '/');
    if (!last_slash) { strncpy(out, "unknown", out_sz - 1); out[out_sz - 1] = '\0'; return; }
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

static void make_method_id(const char *file_path, const char *class_name,
                           const char *method_name, char *out, size_t out_sz) {
    snprintf(out, out_sz, "%s::%s.%s", file_path,
             class_name[0] ? class_name : "<module>", method_name);
}

static const char *method_type(const char *name) {
    if (strcmp(name, "__init__") == 0) return "INIT";
    if (strcmp(name, "__del__") == 0 || strcmp(name, "cleanup") == 0 ||
        strcmp(name, "close") == 0 || strcmp(name, "destroy") == 0) return "CLEANUP";
    if (strcmp(name, "Run") == 0) return "CORE";
    return "LINK";
}

/* ════════════════════════════════════════════
 * SQLITE BACKEND
 * ════════════════════════════════════════════ */

static int sqlite_init_schema(sqlite3 *db) {
    const char *sqls[] = {
        "CREATE TABLE IF NOT EXISTS bcl_codebases (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, root_path TEXT, class_count INTEGER DEFAULT 0, method_count INTEGER DEFAULT 0, edge_count INTEGER DEFAULT 0, scanned_at TEXT DEFAULT (datetime('now')))",
        "CREATE TABLE IF NOT EXISTS bcl_classes (id INTEGER PRIMARY KEY AUTOINCREMENT, codebase_id INTEGER NOT NULL, class_name TEXT NOT NULL, file_path TEXT, bases TEXT, method_count INTEGER DEFAULT 0, line_start INTEGER, line_end INTEGER, UNIQUE(codebase_id, class_name, file_path))",
        "CREATE TABLE IF NOT EXISTS bcl_methods (id INTEGER PRIMARY KEY AUTOINCREMENT, codebase_id INTEGER NOT NULL, bcl_class_id INTEGER, method_id TEXT, method_id_hash TEXT, method_name TEXT, class_name TEXT, file_path TEXT, method_type TEXT, is_async INTEGER DEFAULT 0, line_start INTEGER, line_end INTEGER, UNIQUE(codebase_id, method_id_hash))",
        "CREATE TABLE IF NOT EXISTS bcl_edges (id INTEGER PRIMARY KEY AUTOINCREMENT, codebase_id INTEGER NOT NULL, source_method_id TEXT, source_method_row_id INTEGER, target TEXT, edge_type TEXT, certainty TEXT, line_number INTEGER)",
        "CREATE TABLE IF NOT EXISTS source_files (id INTEGER PRIMARY KEY AUTOINCREMENT, codebase_id INTEGER NOT NULL, file_path TEXT NOT NULL, source_text TEXT, source_len INTEGER, language TEXT, stored_at TEXT DEFAULT (datetime('now')), UNIQUE(codebase_id, file_path))",
        NULL
    };
    for (int i = 0; sqls[i]; i++) {
        char *err = NULL;
        if (sqlite3_exec(db, sqls[i], NULL, NULL, &err) != SQLITE_OK) {
            fprintf(stderr, "ERROR: sqlite schema: %s
", err ? err : "(unknown)");
            sqlite3_free(err);
            return 0;
        }
    }
    return 1;
}

static int sqlite_get_or_create_codebase(sqlite3 *db, const char *file_path) {
    char cb_name[256];
    codebase_name_from_path(file_path, cb_name, sizeof(cb_name));
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, "SELECT id FROM bcl_codebases WHERE name = ?", -1, &stmt, NULL) != SQLITE_OK) return -1;
    sqlite3_bind_text(stmt, 1, cb_name, -1, SQLITE_TRANSIENT);
    int id = -1;
    if (sqlite3_step(stmt) == SQLITE_ROW) id = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    if (id > 0) return id;
    if (sqlite3_prepare_v2(db, "INSERT INTO bcl_codebases (name, root_path) VALUES (?, ?)", -1, &stmt, NULL) != SQLITE_OK) return -1;
    sqlite3_bind_text(stmt, 1, cb_name, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, file_path, -1, SQLITE_TRANSIENT);
    if (sqlite3_step(stmt) != SQLITE_DONE) { sqlite3_finalize(stmt); return -1; }
    sqlite3_finalize(stmt);
    return (int)sqlite3_last_insert_rowid(db);
}

static int sqlite_store_source(sqlite3 *db, int codebase_id, ParseResult *r) {
    const char *lang = (r->language == LANG_PYTHON) ? "python" : (r->language == LANG_C) ? "c" : "unknown";
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, "INSERT OR REPLACE INTO source_files (codebase_id, file_path, source_text, source_len, language) VALUES (?, ?, ?, ?, ?)", -1, &stmt, NULL) != SQLITE_OK) return 0;
    sqlite3_bind_int(stmt, 1, codebase_id);
    sqlite3_bind_text(stmt, 2, r->file_path, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, r->source ? r->source : "", (int)r->source_len, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 4, (int)r->source_len);
    sqlite3_bind_text(stmt, 5, lang, -1, SQLITE_TRANSIENT);
    int ok = (sqlite3_step(stmt) == SQLITE_DONE);
    sqlite3_finalize(stmt);
    return ok;
}

static int sqlite_store_classes(ParseResult *r, sqlite3 *db, int codebase_id) {
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, "INSERT OR IGNORE INTO bcl_classes (codebase_id, class_name, file_path, bases, method_count, line_start, line_end) VALUES (?, ?, ?, ?, ?, ?, ?)", -1, &stmt, NULL) != SQLITE_OK) return 0;
    for (int i = 0; i < r->class_count; i++) {
        ClassInfo *c = &r->classes[i];
        sqlite3_bind_int(stmt, 1, codebase_id);
        sqlite3_bind_text(stmt, 2, c->name, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 3, r->file_path, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 4, c->bases, -1, SQLITE_TRANSIENT);
        sqlite3_bind_int(stmt, 5, c->method_count);
        sqlite3_bind_int(stmt, 6, c->line_start);
        sqlite3_bind_int(stmt, 7, c->line_end);
        if (sqlite3_step(stmt) != SQLITE_DONE) { sqlite3_reset(stmt); continue; }
        c->db_id = (int)sqlite3_last_insert_rowid(db);
        if (c->db_id == 0) {
            sqlite3_stmt *lk; sqlite3_prepare_v2(db, "SELECT id FROM bcl_classes WHERE codebase_id=? AND class_name=? AND file_path=?", -1, &lk, NULL);
            sqlite3_bind_int(lk, 1, codebase_id); sqlite3_bind_text(lk, 2, c->name, -1, SQLITE_TRANSIENT); sqlite3_bind_text(lk, 3, r->file_path, -1, SQLITE_TRANSIENT);
            if (sqlite3_step(lk) == SQLITE_ROW) c->db_id = sqlite3_column_int(lk, 0);
            sqlite3_finalize(lk);
        }
        sqlite3_reset(stmt);
    }
    sqlite3_finalize(stmt);
    return 1;
}

static int sqlite_store_methods(ParseResult *r, sqlite3 *db, int codebase_id) {
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, "INSERT OR IGNORE INTO bcl_methods (codebase_id, bcl_class_id, method_id, method_id_hash, method_name, class_name, file_path, method_type, is_async, line_start, line_end) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", -1, &stmt, NULL) != SQLITE_OK) return 0;
    for (int i = 0; i < r->method_count; i++) {
        MethodInfo *m = &r->methods[i];
        char method_id[1024]; make_method_id(r->file_path, m->class_name, m->name, method_id, sizeof(method_id));
        char hash[17]; make_hash(method_id, hash);
        int bcl_class_id = 0;
        for (int ci = 0; ci < r->class_count; ci++) if (strcmp(r->classes[ci].name, m->class_name) == 0) { bcl_class_id = r->classes[ci].db_id; break; }
        const char *mtype = method_type(m->name);
        sqlite3_bind_int(stmt, 1, codebase_id);
        sqlite3_bind_int(stmt, 2, bcl_class_id);
        sqlite3_bind_text(stmt, 3, method_id, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 4, hash, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 5, m->name, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 6, m->class_name, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 7, r->file_path, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 8, mtype, -1, SQLITE_TRANSIENT);
        sqlite3_bind_int(stmt, 9, m->is_async);
        sqlite3_bind_int(stmt, 10, m->line_start);
        sqlite3_bind_int(stmt, 11, m->line_end);
        if (sqlite3_step(stmt) != SQLITE_DONE) { sqlite3_reset(stmt); continue; }
        m->db_id = (int)sqlite3_last_insert_rowid(db);
        if (m->db_id == 0) {
            sqlite3_stmt *lk; sqlite3_prepare_v2(db, "SELECT id FROM bcl_methods WHERE codebase_id=? AND method_id_hash=?", -1, &lk, NULL);
            sqlite3_bind_int(lk, 1, codebase_id); sqlite3_bind_text(lk, 2, hash, -1, SQLITE_TRANSIENT);
            if (sqlite3_step(lk) == SQLITE_ROW) m->db_id = sqlite3_column_int(lk, 0);
            sqlite3_finalize(lk);
        }
        sqlite3_reset(stmt);
    }
    sqlite3_finalize(stmt);
    return 1;
}

static int sqlite_store_edges(ParseResult *r, sqlite3 *db, int codebase_id) {
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, "INSERT INTO bcl_edges (codebase_id, source_method_id, source_method_row_id, target, edge_type, certainty, line_number) VALUES (?, ?, ?, ?, ?, ?, ?)", -1, &stmt, NULL) != SQLITE_OK) return 0;
    for (int i = 0; i < r->edge_count; i++) {
        EdgeInfo *e = &r->edges[i];
        int src_row_id = 0;
        for (int mi = 0; mi < r->method_count; mi++) {
            char buf[512]; snprintf(buf, sizeof(buf), "%s.%s", r->methods[mi].class_name, r->methods[mi].name);
            if (strcmp(buf, e->source) == 0) { src_row_id = r->methods[mi].db_id; break; }
        }
        sqlite3_bind_int(stmt, 1, codebase_id);
        sqlite3_bind_text(stmt, 2, e->source, -1, SQLITE_TRANSIENT);
        sqlite3_bind_int(stmt, 3, src_row_id);
        sqlite3_bind_text(stmt, 4, e->target, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 5, e->edge_type, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 6, e->certainty, -1, SQLITE_TRANSIENT);
        sqlite3_bind_int(stmt, 7, e->line_number);
        if (sqlite3_step(stmt) != SQLITE_DONE) { sqlite3_reset(stmt); continue; }
        sqlite3_reset(stmt);
    }
    sqlite3_finalize(stmt);
    return 1;
}

static int sqlite_store_results(ParseResult *r, const char *db_path) {
    sqlite3 *db;
    if (sqlite3_open(db_path ? db_path : ":memory:", &db) != SQLITE_OK) { sqlite3_close(db); return 0; }
    if (!sqlite_init_schema(db)) { sqlite3_close(db); return 0; }
    int codebase_id = sqlite_get_or_create_codebase(db, r->file_path);
    if (codebase_id < 0) { sqlite3_close(db); return 0; }
    int ok = 1;
    if (!sqlite_store_source(db, codebase_id, r)) ok = 0;
    if (!sqlite_store_classes(r, db, codebase_id)) ok = 0;
    if (!sqlite_store_methods(r, db, codebase_id)) ok = 0;
    if (!sqlite_store_edges(r, db, codebase_id)) ok = 0;
    if (ok) {
        char sql[512];
        snprintf(sql, sizeof(sql), "UPDATE bcl_codebases SET class_count=%d, method_count=%d, edge_count=%d, scanned_at=datetime('now') WHERE id=%d", r->class_count, r->method_count, r->edge_count, codebase_id);
        sqlite3_exec(db, sql, NULL, NULL, NULL);
    }
    sqlite3_close(db);
    return ok;
}

/* ════════════════════════════════════════════
 * MYSQL BACKEND
 * ════════════════════════════════════════════ */

#ifdef CASCADE_USE_MYSQL

static void escape_str(MYSQL *conn, const char *in, char *out, size_t out_sz) {
    mysql_real_escape_string(conn, out, in, (unsigned long)strlen(in));
    (void)out_sz;
}

static int mysql_get_or_create_codebase(MYSQL *conn, const char *file_path) {
    char cb_name[256]; codebase_name_from_path(file_path, cb_name, sizeof(cb_name));
    char sql[512];
    snprintf(sql, sizeof(sql), "SELECT id FROM bcl_codebases WHERE name = '%s'", cb_name);
    if (mysql_query(conn, sql)) return -1;
    MYSQL_RES *res = mysql_store_result(conn);
    if (res && mysql_num_rows(res) > 0) { MYSQL_ROW row = mysql_fetch_row(res); int id = atoi(row[0]); mysql_free_result(res); return id; }
    if (res) mysql_free_result(res);
    char ename[512]; escape_str(conn, cb_name, ename, sizeof(ename));
    char epath[1024]; escape_str(conn, file_path, epath, sizeof(epath));
    snprintf(sql, sizeof(sql), "INSERT INTO bcl_codebases (name, root_path) VALUES ('%s', '%s')", ename, epath);
    if (mysql_query(conn, sql)) return -1;
    return (int)mysql_insert_id(conn);
}

static int mysql_store_source(MYSQL *conn, int codebase_id, ParseResult *r) {
    const char *lang = (r->language == LANG_PYTHON) ? "python" : (r->language == LANG_C) ? "c" : "unknown";
    mysql_query(conn, "CREATE TABLE IF NOT EXISTS source_files (id INT AUTO_INCREMENT PRIMARY KEY, codebase_id INT NOT NULL, file_path TEXT NOT NULL, source_text LONGTEXT, source_len INT, language VARCHAR(32), stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY uq_source (codebase_id, file_path(512)))");
    char *escaped_src = (char *)malloc(2 * r->source_len + 1);
    if (!escaped_src) return 0;
    mysql_real_escape_string(conn, escaped_src, r->source ? r->source : "", (unsigned long)(r->source ? r->source_len : 0));
    char epath[2048]; escape_str(conn, r->file_path, epath, sizeof(epath));
    char sql[4096];
    snprintf(sql, sizeof(sql), "INSERT INTO source_files (codebase_id, file_path, source_text, source_len, language) VALUES (%d, '%s', '%s', %d, '%s') ON DUPLICATE KEY UPDATE source_text=VALUES(source_text), source_len=VALUES(source_len), language=VALUES(language)", codebase_id, epath, escaped_src, (int)r->source_len, lang);
    free(escaped_src);
    if (mysql_query(conn, sql)) return 0;
    return 1;
}

int mysql_store_results(ParseResult *r, const char *db_name) {
    const char *host = config_global_db_host(); const char *user = config_global_db_user();
    const char *dbname = db_name ? db_name : config_global_db_path();
    if (!host) host = "localhost"; if (!user) user = "root"; if (!dbname) dbname = "bcl_ir";
    MYSQL *conn = mysql_init(NULL);
    if (!conn) return 0;
    if (!mysql_real_connect(conn, host, user, "", dbname, 3306, NULL, 0)) { mysql_close(conn); return 0; }
    int codebase_id = mysql_get_or_create_codebase(conn, r->file_path);
    if (codebase_id < 0) { mysql_close(conn); return 0; }
    int ok = 1;
    if (!mysql_store_source(conn, codebase_id, r)) ok = 0;
    if (!mysql_store_classes(r, conn, codebase_id)) ok = 0;
    if (!mysql_store_methods(r, conn, codebase_id)) ok = 0;
    if (!mysql_store_edges(r, conn, codebase_id)) ok = 0;
    if (ok) {
        char sql[512];
        snprintf(sql, sizeof(sql), "UPDATE bcl_codebases SET class_count=%d, method_count=%d, edge_count=%d, scanned_at=NOW() WHERE id=%d", r->class_count, r->method_count, r->edge_count, codebase_id);
        mysql_query(conn, sql);
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
        snprintf(sql, sizeof(sql), "INSERT IGNORE INTO bcl_classes (codebase_id, class_name, file_path, bases, method_count, line_start, line_end) VALUES (%d, '%s', '%s', '%s', %d, %d, %d)", codebase_id, ename, epath, ebases, c->method_count, c->line_start, c->line_end);
        if (mysql_query(conn, sql)) return 0;
        c->db_id = (int)mysql_insert_id(conn);
        if (c->db_id == 0) {
            snprintf(sql, sizeof(sql), "SELECT id FROM bcl_classes WHERE codebase_id=%d AND class_name='%s' AND file_path='%s'", codebase_id, ename, epath);
            if (mysql_query(conn, sql) == 0) { MYSQL_RES *res = mysql_store_result(conn); if (res && mysql_num_rows(res) > 0) { MYSQL_ROW row = mysql_fetch_row(res); c->db_id = atoi(row[0]); mysql_free_result(res); } else if (res) mysql_free_result(res); }
        }
    }
    return 1;
}

int mysql_store_methods(ParseResult *r, void *conn_ptr, int codebase_id) {
    MYSQL *conn = (MYSQL *)conn_ptr;
    for (int i = 0; i < r->method_count; i++) {
        MethodInfo *m = &r->methods[i];
        char method_id[1024]; make_method_id(r->file_path, m->class_name, m->name, method_id, sizeof(method_id));
        char hash[17]; make_hash(method_id, hash);
        char ename[256], ecname[256], epath[1024], emid[2048];
        escape_str(conn, m->name, ename, sizeof(ename));
        escape_str(conn, m->class_name, ecname, sizeof(ecname));
        escape_str(conn, r->file_path, epath, sizeof(epath));
        escape_str(conn, method_id, emid, sizeof(emid));
        int bcl_class_id = 0;
        for (int ci = 0; ci < r->class_count; ci++) if (strcmp(r->classes[ci].name, m->class_name) == 0) { bcl_class_id = r->classes[ci].db_id; break; }
        const char *mtype = method_type(m->name);
        char class_id_str[32];
        if (bcl_class_id > 0) snprintf(class_id_str, sizeof(class_id_str), "%d", bcl_class_id); else snprintf(class_id_str, sizeof(class_id_str), "NULL");
        char sql[4096];
        snprintf(sql, sizeof(sql), "INSERT IGNORE INTO bcl_methods (codebase_id, bcl_class_id, method_id, method_id_hash, method_name, class_name, file_path, method_type, is_async, line_start, line_end) VALUES (%d, %s, '%s', '%s', '%s', '%s', '%s', '%s', %d, %d, %d)", codebase_id, class_id_str, emid, hash, ename, ecname, epath, mtype, m->is_async, m->line_start, m->line_end);
        if (mysql_query(conn, sql)) return 0;
        m->db_id = (int)mysql_insert_id(conn);
        if (m->db_id == 0) {
            snprintf(sql, sizeof(sql), "SELECT id FROM bcl_methods WHERE codebase_id=%d AND method_id_hash='%s'", codebase_id, hash);
            if (mysql_query(conn, sql) == 0) { MYSQL_RES *res = mysql_store_result(conn); if (res && mysql_num_rows(res) > 0) { MYSQL_ROW row = mysql_fetch_row(res); m->db_id = atoi(row[0]); mysql_free_result(res); } else if (res) mysql_free_result(res); }
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
        int src_row_id = 0;
        for (int mi = 0; mi < r->method_count; mi++) {
            char buf[512]; snprintf(buf, sizeof(buf), "%s.%s", r->methods[mi].class_name, r->methods[mi].name);
            if (strcmp(buf, e->source) == 0) { src_row_id = r->methods[mi].db_id; break; }
        }
        char src_row_str[32];
        if (src_row_id > 0) snprintf(src_row_str, sizeof(src_row_str), "%d", src_row_id); else snprintf(src_row_str, sizeof(src_row_str), "NULL");
        char sql[2048];
        snprintf(sql, sizeof(sql), "INSERT INTO bcl_edges (codebase_id, source_method_id, source_method_row_id, target, edge_type, certainty, line_number) VALUES (%d, '%s', %s, '%s', '%s', '%s', %d)", codebase_id, esrc, src_row_str, etgt, etype, ecert, e->line_number);
        if (mysql_query(conn, sql)) return 0;
    }
    return 1;
}

#else

int mysql_store_results(ParseResult *r, const char *db_name) { (void)r; (void)db_name; fprintf(stderr, "MySQL not compiled in
"); return 0; }
int mysql_store_classes(ParseResult *r, void *conn, int codebase_id) { (void)r; (void)conn; (void)codebase_id; return 0; }
int mysql_store_methods(ParseResult *r, void *conn, int codebase_id) { (void)r; (void)conn; (void)codebase_id; return 0; }
int mysql_store_edges(ParseResult *r, void *conn, int codebase_id) { (void)r; (void)conn; (void)codebase_id; return 0; }

#endif /* CASCADE_USE_MYSQL */

/* ════════════════════════════════════════════
 * UNIFIED PUBLIC API — dispatches based on config
 * ════════════════════════════════════════════ */

int store_results(ParseResult *r, const char *db_name) {
    if (!config_global_backend()) config_init_global("bcl_config.json");
    const char *backend = config_global_backend();
    if (backend && strcmp(backend, "mysql") == 0) {
#ifdef CASCADE_USE_MYSQL
        return mysql_store_results(r, db_name);
#else
        fprintf(stderr, "ERROR: backend=mysql but CASCADE_USE_MYSQL not compiled in
");
        return 0;
#endif
    }
    const char *db_path = config_global_db_path();
    return sqlite_store_results(r, db_path);
}

int store_source(ParseResult *r) {
    if (!config_global_backend()) config_init_global("bcl_config.json");
    const char *backend = config_global_backend();
    if (backend && strcmp(backend, "mysql") == 0) {
#ifdef CASCADE_USE_MYSQL
        const char *host = config_global_db_host(); const char *user = config_global_db_user();
        const char *dbname = config_global_db_path();
        if (!host) host = "localhost"; if (!user) user = "root"; if (!dbname) dbname = "bcl_ir";
        MYSQL *conn = mysql_init(NULL);
        if (!conn) return 0;
        if (!mysql_real_connect(conn, host, user, "", dbname, 3306, NULL, 0)) { mysql_close(conn); return 0; }
        int codebase_id = mysql_get_or_create_codebase(conn, r->file_path);
        int ok = 0;
        if (codebase_id >= 0) ok = mysql_store_source(conn, codebase_id, r);
        mysql_close(conn);
        return ok;
#else
        return 0;
#endif
    }
    const char *db_path = config_global_db_path();
    sqlite3 *db;
    if (sqlite3_open(db_path ? db_path : ":memory:", &db) != SQLITE_OK) { sqlite3_close(db); return 0; }
    sqlite_init_schema(db);
    int codebase_id = sqlite_get_or_create_codebase(db, r->file_path);
    int ok = 0;
    if (codebase_id >= 0) ok = sqlite_store_source(db, codebase_id, r);
    sqlite3_close(db);
    return ok;
}
