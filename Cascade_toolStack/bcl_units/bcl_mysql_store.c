//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_mysql_store.c" date="2026-07-04" author="Devin" session_id="bcl-vbast-units" context="BCL unit that writes AST/BCL/graph results to MySQL bcl_ir tables. Absorbs mysql_store.c into the bcl_units convention. Always compiles with MySQL (no CASCADE_USE_MYSQL guard). Commands: store, set_config, read_state."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_mysql_store.c" domain="bcl_units" authority="MysqlStore"}
//[@SUMMARY]{summary="MySQL store BCL unit. Parses a source file via ast_init/ast_parse_file, builds graph edges, then writes classes/methods/edges to bcl_ir tables. Owns MySQL connection config in STATE. Commands: store, set_config, read_state."}
//[@CLASS]{class="MysqlStore" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="EscapeStr" type="internal"}
//[@METHOD]{method="MakeHash" type="internal"}
//[@METHOD]{method="CodebaseNameFromPath" type="internal"}
//[@METHOD]{method="GetOrCreateCodebase" type="internal"}
//[@METHOD]{method="MakeMethodId" type="internal"}
//[@METHOD]{method="MethodType" type="internal"}
//[@METHOD]{method="StoreClasses" type="internal"}
//[@METHOD]{method="StoreMethods" type="internal"}
//[@METHOD]{method="StoreEdges" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<MySQL store BCL unit. Absorbs vbast/mysql_store.c. Always links mysqlclient. No printf/fprintf — errors go to STATE.last_error.>][@todos<>]}

/*
 * bcl_mysql_store.c — write AST/BCL/graph results to MySQL bcl_ir tables
 *
 * BCL IN:  [@RUN]{[@CMD]{store}[@PATH]{/path/to/file.py}[@DB]{bcl_ir}}
 *          [@RUN]{[@CMD]{set_config}[@HOST]{...}[@USER]{...}[@PORT]{...}[@DB]{...}}
 *          [@RUN]{[@CMD]{read_state}}
 * BCL OUT: [@OK]{[@FILE]{...}[@DB]{...}[@CLASSES]{N}[@METHODS]{N}[@EDGES]{N}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 *
 * Aligned to the EXISTING bcl_ir schema:
 *   bcl_codebases: lookup or create by name (derived from file path)
 *   bcl_classes:   codebase_id (NOT NULL), class_name, file_path, bases, method_count, line_start, line_end
 *   bcl_methods:   codebase_id (NOT NULL), bcl_class_id, method_id (filepath::Class.method),
 *                  method_id_hash (md5-ish 16-char hex), method_name, class_name, file_path,
 *                  method_type, is_async, line_start, line_end
 *   bcl_edges:     codebase_id (NOT NULL), bcl_method_id, source_method_id (filepath::Class.method),
 *                  source_method_row_id, target, edge_type, certainty, line_number
 */

#include "vbast.h"
#include "bcl_toolstack.h"
#include <mysql.h>

/* ===== DIM BLOCK ===== */

#define MYSQLSTORE_MAX_PATH   1024

/* ===== STATE ===== */

static struct {
    int          initialized;
    ParseResult  result;
    int          files_stored;
    int          classes_stored;
    int          methods_stored;
    int          edges_stored;
    char         host[256];
    char         user[64];
    char         pass[128];
    int          port;
    char         socket[256];
    char         db_name[64];
    char         last_error[256];
} STATE;

/* ===== SECTION: HELPERS ===== */

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
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "codebase create: %s", mysql_error(conn));
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

/* ===== SECTION: INTERNAL STORE FUNCTIONS (static — do not conflict with bcl_graph_store.c) ===== */

/* Forward declarations — static, internal to this unit */
static int ms_store_classes(ParseResult *r, void *conn_ptr, int codebase_id);
static int ms_store_methods(ParseResult *r, void *conn_ptr, int codebase_id);
static int ms_store_edges(ParseResult *r, void *conn_ptr, int codebase_id);

static int ms_store_results(ParseResult *r, const char *db_name) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed");
        return 0;
    }
    const char *use_db = (db_name && db_name[0]) ? db_name : STATE.db_name;
    if (!mysql_real_connect(conn, STATE.host, STATE.user, STATE.pass,
                            use_db, STATE.port, STATE.socket[0] ? STATE.socket : NULL, 0)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "mysql connect: %s", mysql_error(conn));
        mysql_close(conn);
        return 0;
    }

    int codebase_id = get_or_create_codebase(conn, r->file_path);
    if (codebase_id < 0) {
        mysql_close(conn);
        return 0;
    }

    int ok = 1;
    if (!ms_store_classes(r, conn, codebase_id)) ok = 0;
    if (!ms_store_methods(r, conn, codebase_id)) ok = 0;
    if (!ms_store_edges(r, conn, codebase_id)) ok = 0;

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

static int ms_store_classes(ParseResult *r, void *conn_ptr, int codebase_id) {
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
            snprintf(STATE.last_error, sizeof(STATE.last_error),
                "bcl_classes insert: %s", mysql_error(conn));
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
        STATE.classes_stored++;
    }
    return 1;
}

static int ms_store_methods(ParseResult *r, void *conn_ptr, int codebase_id) {
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
            snprintf(STATE.last_error, sizeof(STATE.last_error),
                "bcl_methods insert: %s", mysql_error(conn));
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
        STATE.methods_stored++;
    }
    return 1;
}

static int ms_store_edges(ParseResult *r, void *conn_ptr, int codebase_id) {
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
            snprintf(STATE.last_error, sizeof(STATE.last_error),
                "bcl_edges insert: %s", mysql_error(conn));
            return 0;
        }
        STATE.edges_stored++;
    }
    return 1;
}

/* ===== SECTION: UNIT INTERFACE ===== */

int MysqlStore_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host,   "localhost",       sizeof(STATE.host) - 1);
    strncpy(STATE.user,   "root",            sizeof(STATE.user) - 1);
    STATE.pass[0] = '\0';
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    strncpy(STATE.db_name,"bcl_ir",          sizeof(STATE.db_name) - 1);
    STATE.initialized = 1;
    return 1;
}

int MysqlStore_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) MysqlStore_Init();

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@STORED]{%d}[@CLASSES]{%d}[@METHODS]{%d}[@EDGES]{%d}",
            STATE.initialized ? 1 : 0,
            STATE.files_stored, STATE.classes_stored,
            STATE.methods_stored, STATE.edges_stored);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[256] = {0};
        char user[64]  = {0};
        char pass[128] = {0};
        char port_str[16] = {0};
        char socket_path[256] = {0};
        char db_name[64] = {0};
        BclParser_Extract(&parse, "HOST",   host,        sizeof(host));
        BclParser_Extract(&parse, "USER",   user,        sizeof(user));
        BclParser_Extract(&parse, "PASS",   pass,        sizeof(pass));
        BclParser_Extract(&parse, "PORT",   port_str,    sizeof(port_str));
        BclParser_Extract(&parse, "SOCKET", socket_path, sizeof(socket_path));
        BclParser_Extract(&parse, "DB",     db_name,     sizeof(db_name));
        BclParser_Free(&parse);
        if (host[0])        strncpy(STATE.host,   host,        sizeof(STATE.host) - 1);
        if (user[0])        strncpy(STATE.user,   user,        sizeof(STATE.user) - 1);
        if (pass[0])        strncpy(STATE.pass,   pass,        sizeof(STATE.pass) - 1);
        if (port_str[0])    STATE.port = atoi(port_str);
        if (socket_path[0]) strncpy(STATE.socket, socket_path, sizeof(STATE.socket) - 1);
        if (db_name[0])     strncpy(STATE.db_name,db_name,     sizeof(STATE.db_name) - 1);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* ===== STORE ===== */
    if (strcmp(cmd, "store") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[MYSQLSTORE_MAX_PATH] = {0};
        char db_name[64] = {0};
        BclParser_Extract(&parse, "PATH", path,    sizeof(path));
        BclParser_Extract(&parse, "DB",   db_name, sizeof(db_name));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }

        /* 1. parse the source file */
        ast_init(&STATE.result, path);
        if (ast_parse_file(&STATE.result) == 0) {
            snprintf(STATE.last_error, sizeof(STATE.last_error),
                "ast_parse_file failed for %s", path);
            return BclResult_Err(bcl_out, out_sz, 21, STATE.last_error);
        }

        /* 2. build graph edges before storing */
        graph_build_edges(&STATE.result);

        /* 3. store to MySQL */
        const char *use_db = db_name[0] ? db_name : STATE.db_name;
        int ok = ms_store_results(&STATE.result, use_db);
        if (!ok) {
            return BclResult_Err(bcl_out, out_sz, 22,
                STATE.last_error[0] ? STATE.last_error : "ms_store_results failed");
        }

        STATE.files_stored++;

        /* 4. output result */
        char ok_body[1024];
        snprintf(ok_body, sizeof(ok_body),
            "[@FILE]{%s}[@DB]{%s}[@CLASSES]{%d}[@METHODS]{%d}[@EDGES]{%d}",
            path, use_db,
            STATE.result.class_count, STATE.result.method_count, STATE.result.edge_count);
        return BclResult_Ok(bcl_out, out_sz, ok_body);
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int MysqlStore_Close(void) {
    ast_free(&STATE.result);
    STATE.initialized = 0;
    return 1;
}

const char * MysqlStore_State(void) {
    static char buf[512];
    snprintf(buf, sizeof(buf),
        "MysqlStore: initialized=%d files=%d classes=%d methods=%d edges=%d db=%s host=%s",
        STATE.initialized, STATE.files_stored, STATE.classes_stored,
        STATE.methods_stored, STATE.edges_stored, STATE.db_name, STATE.host);
    return buf;
}
