//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_store.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="BCL unit for graph store — writes classes, methods, edges, source_files to MySQL or SQLite. Backend selectable via config. Supports :memory: ephemeral mode. Stubs for load/search (require MySQL)."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_graph_store.c" domain="graph_engine" authority="GraphStore"}
//[@SUMMARY]{summary="Unified graph store BCL unit — writes classes, methods, edges, source_files to MySQL or SQLite. Backend selected at runtime via config. Supports :memory: for ephemeral mode. Dispatches: load_all, search_nodes, load_class_graph, load_bcl_edges, load_token_edges, load_know_edges, store_results, read_state, set_config."}
//[@CLASS]{class="GraphStore" domain="graph_engine" authority="single"}
//[@METHOD]{method="GraphStore_Init" type="lifecycle"}
//[@METHOD]{method="GraphStore_Run" type="dispatch"}
//[@METHOD]{method="GraphStore_Close" type="lifecycle"}
//[@METHOD]{method="GraphStore_State" type="query"}
//[@METHOD]{method="store_results" type="command"}
//[@METHOD]{method="store_source" type="command"}
//[@METHOD]{method="store_classes" type="helper"}
//[@METHOD]{method="store_methods" type="helper"}
//[@METHOD]{method="store_edges" type="helper"}
//[@METHOD]{method="sqlite_init_schema" type="helper"}
//[@METHOD]{method="sqlite_get_or_create_codebase" type="helper"}
//[@METHOD]{method="store_load_all" type="command"}
//[@METHOD]{method="store_search_nodes" type="command"}
//[@METHOD]{method="store_load_class_graph" type="command"}
//[@METHOD]{method="store_load_bcl_edges" type="command"}
//[@METHOD]{method="store_load_token_edges" type="command"}
//[@METHOD]{method="store_load_know_edges" type="command"}

/*
 * bcl_graph_store.c — Unified graph store (MySQL + SQLite + :memory:)
 *
 * Backend selected at runtime via config_global_backend():
 *   "mysql"  -> connects to MySQL vb_shared (or configured db)
 *   "sqlite" -> opens local SQLite file (or :memory: if no path)
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

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"
#include <sqlite3.h>
#include <mysql.h>

/* ════════════════════════════════════════════
 * UNIT STATE
 * ════════════════════════════════════════════ */

static struct {
    int    initialized;
    int    store_count;
    int    load_count;
    int    last_code;
    char   last_cmd[64];
    char   backend[32];
    char   db_path[256];
} STATE;

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
            fprintf(stderr, "ERROR: sqlite schema: %s\n", err ? err : "(unknown)");
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

static void escape_str(MYSQL *conn, const char *in, char *out, size_t out_sz) {
    mysql_real_escape_string(conn, out, in, (unsigned long)strlen(in));
    (void)out_sz;
}

/* Forward declarations — defined below, used by mysql_store_results */
int mysql_store_classes(ParseResult *r, void *conn_ptr, int codebase_id);
int mysql_store_methods(ParseResult *r, void *conn_ptr, int codebase_id);
int mysql_store_edges(ParseResult *r, void *conn_ptr, int codebase_id);

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

/* ════════════════════════════════════════════
 * UNIFIED PUBLIC API — dispatches based on config
 * ════════════════════════════════════════════ */

int store_results(ParseResult *r, const char *db_name) {
    if (!config_global_backend()) config_init_global("bcl_config.json");
    const char *backend = config_global_backend();
    if (backend && strcmp(backend, "mysql") == 0) {
        return mysql_store_results(r, db_name);
    }
    const char *db_path = config_global_db_path();
    return sqlite_store_results(r, db_path);
}

int store_source(ParseResult *r) {
    if (!config_global_backend()) config_init_global("bcl_config.json");
    const char *backend = config_global_backend();
    if (backend && strcmp(backend, "mysql") == 0) {
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

int store_classes(ParseResult *r, void *conn, int codebase_id) {
    return mysql_store_classes(r, conn, codebase_id);
}

int store_methods(ParseResult *r, void *conn, int codebase_id) {
    return mysql_store_methods(r, conn, codebase_id);
}

int store_edges(ParseResult *r, void *conn, int codebase_id) {
    return mysql_store_edges(r, conn, codebase_id);
}

/* ════════════════════════════════════════════
 * GRAPH LOAD/SEARCH — read from MySQL into a Graph
 * These query bcl_ir and vb_shared and populate a Graph.
 * ════════════════════════════════════════════ */

/* Helper: open a MySQL connection to a named database (localhost/root) */
static MYSQL *graph_db_connect(const char *db_name) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) return NULL;
    if (!mysql_real_connect(conn, "localhost", "root", "", db_name, 3306, NULL, 0)) {
        mysql_close(conn);
        return NULL;
    }
    return conn;
}

/* Helper: extract the method name (last dot-segment after ::) from a
 * source_method_id like "/path/to/file.py::ClassName.method_name".
 * For targets like "os.path.join" or "self.GetAllSymbols" the leading
 * path/class components are stripped, leaving just the final segment. */
static void parse_method_name(const char *id_str, char *out, size_t out_sz) {
    out[0] = '\0';
    if (!id_str || !id_str[0]) return;
    const char *p = strstr(id_str, "::");
    if (p) p += 2; else p = id_str;
    const char *last_dot = strrchr(p, '.');
    if (last_dot) p = last_dot + 1;
    strncpy(out, p, out_sz - 1);
    out[out_sz - 1] = '\0';
}

/* Helper: load bcl_classes as "class" nodes into g.
 * Returns number of class nodes added. */
static int load_class_nodes(Graph *g, MYSQL *conn) {
    int added = 0;
    if (mysql_query(conn, "SELECT class_name FROM bcl_classes") != 0) return 0;
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) return 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL) {
        if (!row[0] || !row[0][0]) continue;
        if (graph_find_node(g, row[0])) continue;
        Node *n = node_create(g->node_count, row[0], "class", 0.5);
        if (n) { graph_add_node(g, n); added++; }
    }
    mysql_free_result(res);
    return added;
}

/* Helper: load bcl_methods as "method" nodes and create HAS_METHOD edges
 * from their class node. Returns number of method nodes added. */
static int load_method_nodes(Graph *g, MYSQL *conn) {
    int added = 0;
    if (mysql_query(conn, "SELECT method_name, class_name FROM bcl_methods") != 0) return 0;
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) return 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL) {
        const char *mname = row[0] ? row[0] : "";
        const char *cname = row[1] ? row[1] : "";
        if (!mname[0]) continue;
        Node *mnode = graph_find_node(g, mname);
        if (!mnode) {
            mnode = node_create(g->node_count, mname, "method", 0.4);
            if (!mnode) continue;
            graph_add_node(g, mnode);
            added++;
        }
        if (cname[0]) {
            Node *cnode = graph_find_node(g, cname);
            if (cnode) {
                Edge *e = edge_create(g->edge_count, cnode, mnode, "HAS_METHOD", 1.0);
                if (e) graph_add_edge(g, e);
            }
        }
    }
    mysql_free_result(res);
    return added;
}

/* Helper: load CALL edges from bcl_edges into g, matching method nodes by
 * parsing class_name.method_name out of source_method_id and target.
 * Returns number of edges added. */
static int load_call_edges(Graph *g, MYSQL *conn) {
    int added = 0;
    if (mysql_query(conn, "SELECT source_method_id, target FROM bcl_edges WHERE edge_type='CALL'") != 0) return 0;
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) return 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL) {
        char src_mname[GRAPH_MAX_NAME];
        char tgt_mname[GRAPH_MAX_NAME];
        parse_method_name(row[0], src_mname, sizeof(src_mname));
        parse_method_name(row[1], tgt_mname, sizeof(tgt_mname));
        if (!src_mname[0] || !tgt_mname[0]) continue;
        Node *src = graph_find_node(g, src_mname);
        Node *tgt = graph_find_node(g, tgt_mname);
        if (!src || !tgt) continue;
        Edge *e = edge_create(g->edge_count, src, tgt, "CALL", 1.0);
        if (e) { graph_add_edge(g, e); added++; }
    }
    mysql_free_result(res);
    return added;
}

int store_load_all(Graph *g) {
    if (!g) return -1;
    int total = 0;

    /* --- bcl_ir: classes, methods, HAS_METHOD edges, CALL edges --- */
    MYSQL *conn = graph_db_connect("bcl_ir");
    if (!conn) return -1;
    total += load_class_nodes(g, conn);
    total += load_method_nodes(g, conn);
    load_call_edges(g, conn);
    mysql_close(conn);

    /* --- vb_shared: graph_nodes + graph_edges --- */
    conn = graph_db_connect("vb_shared");
    if (conn) {
        /* Load graph_nodes, keeping a DB-id -> Node* map for edge joining.
         * graph_nodes is small (<= a few hundred), so a static array is fine. */
        if (mysql_query(conn, "SELECT id, node_type, name FROM graph_nodes") == 0) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) {
                int map_cap = 256;
                int *gn_ids = (int *)malloc(map_cap * sizeof(int));
                Node **gn_nodes = (Node **)malloc(map_cap * sizeof(Node *));
                int gn_count = 0;
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) != NULL) {
                    int db_id = row[0] ? atoi(row[0]) : 0;
                    const char *ntype = row[1] ? row[1] : "node";
                    const char *name = row[2] ? row[2] : "";
                    char gname[GRAPH_MAX_NAME];
                    snprintf(gname, sizeof(gname), "%s:%s", ntype, name);
                    if (graph_find_node(g, gname)) continue;
                    Node *n = node_create(g->node_count, gname, ntype, 0.3);
                    if (!n) continue;
                    graph_add_node(g, n);
                    total++;
                    if (gn_count >= map_cap) {
                        map_cap *= 2;
                        gn_ids = (int *)realloc(gn_ids, map_cap * sizeof(int));
                        gn_nodes = (Node **)realloc(gn_nodes, map_cap * sizeof(Node *));
                    }
                    gn_ids[gn_count] = db_id;
                    gn_nodes[gn_count] = n;
                    gn_count++;
                }
                mysql_free_result(res);

                /* Load graph_edges (co_occurs) and join via the id map */
                if (mysql_query(conn, "SELECT from_node, to_node, edge_type, weight FROM graph_edges") == 0) {
                    MYSQL_RES *eres = mysql_store_result(conn);
                    if (eres) {
                        MYSQL_ROW erow;
                        while ((erow = mysql_fetch_row(eres)) != NULL) {
                            int from_id = erow[0] ? atoi(erow[0]) : 0;
                            int to_id = erow[1] ? atoi(erow[1]) : 0;
                            const char *etype = erow[2] ? erow[2] : "co_occurs";
                            float w = erow[3] ? (float)atof(erow[3]) : 1.0f;
                            Node *src = NULL, *tgt = NULL;
                            for (int i = 0; i < gn_count; i++) {
                                if (gn_ids[i] == from_id) src = gn_nodes[i];
                                if (gn_ids[i] == to_id) tgt = gn_nodes[i];
                            }
                            if (src && tgt) {
                                Edge *e = edge_create(g->edge_count, src, tgt, etype, w);
                                if (e) graph_add_edge(g, e);
                            }
                        }
                        mysql_free_result(eres);
                    }
                }
                free(gn_ids);
                free(gn_nodes);
            }
        }
        mysql_close(conn);
    }

    return total;
}

int store_search_nodes(Graph *g, const char *query, int max_results) {
    if (!g || !query || !query[0]) return -1;
    /* If the graph is empty, load everything first */
    if (g->node_count == 0) {
        if (store_load_all(g) < 0) return -1;
    }
    int matches = 0;
    for (int i = 0; i < g->node_count; i++) {
        Node *n = g->nodes[i];
        if (!n || !n->name[0]) continue;
        if (strstr(n->name, query) != NULL) {
            matches++;
            if (max_results > 0 && matches >= max_results) break;
        }
    }
    return matches;
}

int store_load_class_graph(Graph *g) {
    if (!g) return -1;
    MYSQL *conn = graph_db_connect("bcl_ir");
    if (!conn) return -1;
    int total = load_class_nodes(g, conn);
    total += load_method_nodes(g, conn);
    mysql_close(conn);
    return total;
}

int store_load_bcl_edges(Graph *g) {
    if (!g) return -1;
    /* If the graph has no method nodes yet, load the class graph first
     * so CALL edges have endpoints to attach to. */
    if (g->node_count == 0) {
        if (store_load_class_graph(g) < 0) return -1;
    }
    MYSQL *conn = graph_db_connect("bcl_ir");
    if (!conn) return -1;
    int added = load_call_edges(g, conn);
    mysql_close(conn);
    return added;
}

int store_load_token_edges(Graph *g) {
    if (!g) return -1;
    MYSQL *conn = graph_db_connect("vb_shared");
    if (!conn) return -1;
    int total = 0;

    /* Load token nodes (graph_nodes WHERE node_type='tokens') with id map */
    if (mysql_query(conn, "SELECT id, name FROM graph_nodes WHERE node_type='tokens'") == 0) {
        MYSQL_RES *res = mysql_store_result(conn);
        if (res) {
            int map_cap = 256;
            int *tn_ids = (int *)malloc(map_cap * sizeof(int));
            Node **tn_nodes = (Node **)malloc(map_cap * sizeof(Node *));
            int tn_count = 0;
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) != NULL) {
                int db_id = row[0] ? atoi(row[0]) : 0;
                const char *name = row[1] ? row[1] : "";
                char gname[GRAPH_MAX_NAME];
                snprintf(gname, sizeof(gname), "token:%s", name);
                if (graph_find_node(g, gname)) continue;
                Node *n = node_create(g->node_count, gname, "tokens", 0.3);
                if (!n) continue;
                graph_add_node(g, n);
                total++;
                if (tn_count >= map_cap) {
                    map_cap *= 2;
                    tn_ids = (int *)realloc(tn_ids, map_cap * sizeof(int));
                    tn_nodes = (Node **)realloc(tn_nodes, map_cap * sizeof(Node *));
                }
                tn_ids[tn_count] = db_id;
                tn_nodes[tn_count] = n;
                tn_count++;
            }
            mysql_free_result(res);

            /* Load co_occurs edges between token nodes */
            if (mysql_query(conn, "SELECT from_node, to_node, weight FROM graph_edges WHERE edge_type='co_occurs'") == 0) {
                MYSQL_RES *eres = mysql_store_result(conn);
                if (eres) {
                    MYSQL_ROW erow;
                    while ((erow = mysql_fetch_row(eres)) != NULL) {
                        int from_id = erow[0] ? atoi(erow[0]) : 0;
                        int to_id = erow[1] ? atoi(erow[1]) : 0;
                        float w = erow[2] ? (float)atof(erow[2]) : 1.0f;
                        Node *src = NULL, *tgt = NULL;
                        for (int i = 0; i < tn_count; i++) {
                            if (tn_ids[i] == from_id) src = tn_nodes[i];
                            if (tn_ids[i] == to_id) tgt = tn_nodes[i];
                        }
                        if (src && tgt) {
                            Edge *e = edge_create(g->edge_count, src, tgt, "co_occurs", w);
                            if (e) graph_add_edge(g, e);
                        }
                    }
                    mysql_free_result(eres);
                }
            }
            free(tn_ids);
            free(tn_nodes);
        }
    }
    mysql_close(conn);
    return total;
}

int store_load_know_edges(Graph *g) {
    if (!g) return -1;
    MYSQL *conn = graph_db_connect("vb_shared");
    if (!conn) return -1;
    int total = 0;

    /* Check know_nodes table exists; bail out silently if not */
    if (mysql_query(conn, "SELECT 1 FROM know_nodes LIMIT 1") != 0) {
        mysql_close(conn);
        return 0;
    }
    mysql_free_result(mysql_store_result(conn));

    /* Load know_nodes (id -> question) with id map */
    if (mysql_query(conn, "SELECT id, question FROM know_nodes") == 0) {
        MYSQL_RES *res = mysql_store_result(conn);
        if (res) {
            int map_cap = 256;
            long *kn_ids = (long *)malloc(map_cap * sizeof(long));
            Node **kn_nodes = (Node **)malloc(map_cap * sizeof(Node *));
            int kn_count = 0;
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) != NULL) {
                long db_id = row[0] ? atol(row[0]) : 0;
                const char *question = row[1] ? row[1] : "";
                char gname[GRAPH_MAX_NAME];
                snprintf(gname, sizeof(gname), "know:%ld", db_id);
                if (graph_find_node(g, gname)) continue;
                Node *n = node_create(g->node_count, gname, "know", 0.3);
                if (!n) continue;
                /* Stash a short label in name for searchability */
                if (question[0]) {
                    strncpy(n->name, gname, sizeof(n->name) - 1);
                    n->name[sizeof(n->name) - 1] = '\0';
                }
                graph_add_node(g, n);
                total++;
                if (kn_count >= map_cap) {
                    map_cap *= 2;
                    kn_ids = (long *)realloc(kn_ids, map_cap * sizeof(long));
                    kn_nodes = (Node **)realloc(kn_nodes, map_cap * sizeof(Node *));
                }
                kn_ids[kn_count] = db_id;
                kn_nodes[kn_count] = n;
                kn_count++;
            }
            mysql_free_result(res);

            /* Load know_edges (from_node_id, to_node_id, relation_type) */
            if (mysql_query(conn, "SELECT from_node_id, to_node_id, relation_type FROM know_edges") == 0) {
                MYSQL_RES *eres = mysql_store_result(conn);
                if (eres) {
                    MYSQL_ROW erow;
                    while ((erow = mysql_fetch_row(eres)) != NULL) {
                        long from_id = erow[0] ? atol(erow[0]) : 0;
                        long to_id = erow[1] ? atol(erow[1]) : 0;
                        const char *rtype = erow[2] ? erow[2] : "relates";
                        Node *src = NULL, *tgt = NULL;
                        for (int i = 0; i < kn_count; i++) {
                            if (kn_ids[i] == from_id) src = kn_nodes[i];
                            if (kn_ids[i] == to_id) tgt = kn_nodes[i];
                        }
                        if (src && tgt) {
                            Edge *e = edge_create(g->edge_count, src, tgt, rtype, 1.0);
                            if (e) graph_add_edge(g, e);
                        }
                    }
                    mysql_free_result(eres);
                }
            }
            free(kn_ids);
            free(kn_nodes);
        }
    }
    mysql_close(conn);
    return total;
}

/* ════════════════════════════════════════════
 * BCL DISPATCH FUNCTIONS
 * ════════════════════════════════════════════ */

int GraphStore_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    if (!config_global_backend()) config_init_global("bcl_config.json");
    const char *backend = config_global_backend();
    if (backend) {
        strncpy(STATE.backend, backend, sizeof(STATE.backend) - 1);
        STATE.backend[sizeof(STATE.backend) - 1] = '\0';
    } else {
        strncpy(STATE.backend, "sqlite", sizeof(STATE.backend) - 1);
        STATE.backend[sizeof(STATE.backend) - 1] = '\0';
    }
    const char *dbp = config_global_db_path();
    if (dbp) {
        strncpy(STATE.db_path, dbp, sizeof(STATE.db_path) - 1);
        STATE.db_path[sizeof(STATE.db_path) - 1] = '\0';
    } else {
        strncpy(STATE.db_path, ":memory:", sizeof(STATE.db_path) - 1);
        STATE.db_path[sizeof(STATE.db_path) - 1] = '\0';
    }
    return 1;
}

int GraphStore_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphStore_Init();
    if (!cmd) return BclResult_Err(bcl_out, out_sz, 50, "null command");
    strncpy(STATE.last_cmd, cmd, sizeof(STATE.last_cmd) - 1);
    STATE.last_cmd[sizeof(STATE.last_cmd) - 1] = '\0';

    /* --- load_all --- */
    if (strcmp(cmd, "load_all") == 0) {
        Graph *g = graph_create(GRAPH_MAX_NODES);
        if (!g) return BclResult_Err(bcl_out, out_sz, 51, "graph_create failed");
        int rc = store_load_all(g);
        if (rc < 0) {
            graph_free(g);
            STATE.last_code = 52;
            return BclResult_Err(bcl_out, out_sz, 52, "load_all failed (MySQL connection error)");
        }
        char body[256];
        snprintf(body, sizeof(body), "[@LOAD_ALL]{[@NODES]{(%d)}[@EDGES]{(%d)}}", g->node_count, g->edge_count);
        graph_free(g);
        STATE.load_count++;
        STATE.last_code = 0;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- search_nodes --- */
    if (strcmp(cmd, "search_nodes") == 0) {
        char query[256] = {0};
        BclParseResult parser;
        BclParser_Init(&parser);
        if (bcl_in && BclParser_Parse(&parser, bcl_in)) {
            BclParser_Extract(&parser, "QUERY", query, sizeof(query));
        }
        BclParser_Free(&parser);
        if (query[0] == '\0') {
            STATE.last_code = 53;
            return BclResult_Err(bcl_out, out_sz, 53, "search_nodes requires [@QUERY]");
        }
        Graph *g = graph_create(GRAPH_MAX_NODES);
        if (!g) return BclResult_Err(bcl_out, out_sz, 54, "graph_create failed");
        int rc = store_search_nodes(g, query, 100);
        if (rc < 0) {
            graph_free(g);
            STATE.last_code = 55;
            return BclResult_Err(bcl_out, out_sz, 55, "search_nodes failed (MySQL connection error)");
        }
        char body[512];
        snprintf(body, sizeof(body), "[@SEARCH]{[@QUERY]{\"%s\"}[@NODES]{(%d)}}", query, g->node_count);
        graph_free(g);
        STATE.load_count++;
        STATE.last_code = 0;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- load_class_graph --- */
    if (strcmp(cmd, "load_class_graph") == 0) {
        Graph *g = graph_create(GRAPH_MAX_NODES);
        if (!g) return BclResult_Err(bcl_out, out_sz, 56, "graph_create failed");
        int rc = store_load_class_graph(g);
        if (rc < 0) {
            graph_free(g);
            STATE.last_code = 57;
            return BclResult_Err(bcl_out, out_sz, 57, "load_class_graph failed (MySQL connection error)");
        }
        char body[256];
        snprintf(body, sizeof(body), "[@LOAD_CLASS_GRAPH]{[@NODES]{(%d)}[@EDGES]{(%d)}}", g->node_count, g->edge_count);
        graph_free(g);
        STATE.load_count++;
        STATE.last_code = 0;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- load_bcl_edges --- */
    if (strcmp(cmd, "load_bcl_edges") == 0) {
        Graph *g = graph_create(GRAPH_MAX_NODES);
        if (!g) return BclResult_Err(bcl_out, out_sz, 58, "graph_create failed");
        int rc = store_load_bcl_edges(g);
        if (rc < 0) {
            graph_free(g);
            STATE.last_code = 59;
            return BclResult_Err(bcl_out, out_sz, 59, "load_bcl_edges failed (MySQL connection error)");
        }
        char body[256];
        snprintf(body, sizeof(body), "[@LOAD_BCL_EDGES]{[@EDGES]{(%d)}}", g->edge_count);
        graph_free(g);
        STATE.load_count++;
        STATE.last_code = 0;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- load_token_edges --- */
    if (strcmp(cmd, "load_token_edges") == 0) {
        Graph *g = graph_create(GRAPH_MAX_NODES);
        if (!g) return BclResult_Err(bcl_out, out_sz, 60, "graph_create failed");
        int rc = store_load_token_edges(g);
        if (rc < 0) {
            graph_free(g);
            STATE.last_code = 61;
            return BclResult_Err(bcl_out, out_sz, 61, "load_token_edges failed (MySQL connection error)");
        }
        char body[256];
        snprintf(body, sizeof(body), "[@LOAD_TOKEN_EDGES]{[@EDGES]{(%d)}}", g->edge_count);
        graph_free(g);
        STATE.load_count++;
        STATE.last_code = 0;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- load_know_edges --- */
    if (strcmp(cmd, "load_know_edges") == 0) {
        Graph *g = graph_create(GRAPH_MAX_NODES);
        if (!g) return BclResult_Err(bcl_out, out_sz, 62, "graph_create failed");
        int rc = store_load_know_edges(g);
        if (rc < 0) {
            graph_free(g);
            STATE.last_code = 63;
            return BclResult_Err(bcl_out, out_sz, 63, "load_know_edges failed (MySQL connection error)");
        }
        char body[256];
        snprintf(body, sizeof(body), "[@LOAD_KNOW_EDGES]{[@EDGES]{(%d)}}", g->edge_count);
        graph_free(g);
        STATE.load_count++;
        STATE.last_code = 0;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- store_results --- */
    if (strcmp(cmd, "store_results") == 0) {
        /* bcl_in would carry a ParseResult reference or file path.
         * In the BCL unit context, we acknowledge the store request.
         * Actual store_results() is called directly by the ingestion pipeline
         * with a ParseResult pointer. Here we report readiness. */
        char body[256];
        snprintf(body, sizeof(body), "[@STORE_RESULTS]{[@STATUS]{ready}[@BACKEND]{\"%s\"}[@DB_PATH]{\"%s\"}}",
                 STATE.backend, STATE.db_path);
        STATE.store_count++;
        STATE.last_code = 0;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- read_state --- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
                 "[@STATE]{[@INITIALIZED]{%d}[@BACKEND]{\"%s\"}[@DB_PATH]{\"%s\"}[@STORE_COUNT]{%d}[@LOAD_COUNT]{%d}[@LAST_CMD]{\"%s\"}[@LAST_CODE]{%d}}",
                 STATE.initialized, STATE.backend, STATE.db_path,
                 STATE.store_count, STATE.load_count, STATE.last_cmd, STATE.last_code);
        STATE.last_code = 0;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- set_config --- */
    if (strcmp(cmd, "set_config") == 0) {
        char backend[32] = {0};
        char db_path[256] = {0};
        BclParseResult parser;
        BclParser_Init(&parser);
        if (bcl_in && BclParser_Parse(&parser, bcl_in)) {
            BclParser_Extract(&parser, "BACKEND", backend, sizeof(backend));
            BclParser_Extract(&parser, "DB_PATH", db_path, sizeof(db_path));
        }
        BclParser_Free(&parser);
        if (backend[0]) {
            strncpy(STATE.backend, backend, sizeof(STATE.backend) - 1);
            STATE.backend[sizeof(STATE.backend) - 1] = '\0';
        }
        if (db_path[0]) {
            strncpy(STATE.db_path, db_path, sizeof(STATE.db_path) - 1);
            STATE.db_path[sizeof(STATE.db_path) - 1] = '\0';
        }
        char body[256];
        snprintf(body, sizeof(body), "[@SET_CONFIG]{[@BACKEND]{\"%s\"}[@DB_PATH]{\"%s\"}}",
                 STATE.backend, STATE.db_path);
        STATE.last_code = 0;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    STATE.last_code = 99;
    return BclResult_Err(bcl_out, out_sz, 99, "unknown command");
}

int GraphStore_Close(void) {
    STATE.initialized = 0;
    STATE.store_count = 0;
    STATE.load_count = 0;
    STATE.last_code = 0;
    STATE.last_cmd[0] = '\0';
    STATE.backend[0] = '\0';
    STATE.db_path[0] = '\0';
    return 1;
}

const char * GraphStore_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
             "GraphStore: initialized=%d backend=%s db_path=%s store_count=%d load_count=%d last_cmd=%s last_code=%d",
             STATE.initialized, STATE.backend, STATE.db_path,
             STATE.store_count, STATE.load_count, STATE.last_cmd, STATE.last_code);
    return buf;
}
