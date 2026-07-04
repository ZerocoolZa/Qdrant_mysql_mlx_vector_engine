//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_search_db.c" date="2026-07-04" author="Devin" session_id="bcl-search-units" context="BCL unit for MySQL database search. Source: MySQL databases. Pipeline: schema discovery -> column detection -> query build -> execute -> row normalize -> BCL output. Absorbs bcl_msearch.c core (search, count, where, stats, search_schema, search_all_db, search_all_mysql) plus build_match, escape_like, escape_sql, truncate_text, search_one_table, count_keyword, stats_all, discover_tables."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_search_db.c" domain="cascade_tools" authority="SearchDb"}
//[@SUMMARY]{summary="MySQL database search unit. Source = MySQL databases. Owns full pipeline: schema discovery, column detection, query build, execute, row normalize, BCL output. Commands: search, count, where, stats, search_schema, search_all_db, search_all_mysql, read_state, set_config. Absorbs bcl_msearch.c."}
//[@CLASS]{class="SearchDb" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="BuildMatch" type="internal"}
//[@METHOD]{method="EnsureConnected" type="internal"}
//[@METHOD]{method="EscapeLike" type="internal"}
//[@METHOD]{method="EscapeSql" type="internal"}
//[@METHOD]{method="TruncateText" type="internal"}
//[@METHOD]{method="SearchOneTable" type="internal"}
//[@METHOD]{method="DiscoverTables" type="internal"}
//[@METHOD]{method="CountKeyword" type="internal"}
//[@METHOD]{method="StatsAll" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<MySQL database search BCL unit. Absorbs bcl_msearch.c core. 14 known targets across vb_shared/vb_code_test/devin. Schema-aware search via SHOW TABLES + INFORMATION_SCHEMA. Cross-database search.>][@todos<>]}

/*
 * bcl_search_db.c — MySQL database search BCL unit
 *
 * BCL IN:  [@RUN]{[@CMD]{search}[@QUERY]{keyword}[@LIMIT]{50}}
 *          [@RUN]{[@CMD]{count}[@QUERY]{keyword}}
 *          [@RUN]{[@CMD]{where}[@DB]{vb_shared}}
 *          [@RUN]{[@CMD]{stats}}
 *          [@RUN]{[@CMD]{search_schema}[@QUERY]{foo}[@DB]{vb_shared}[@MODE]{contains}}
 *          [@RUN]{[@CMD]{search_all_db}[@QUERY]{foo}[@LIMIT]{50}}
 *          [@RUN]{[@CMD]{search_all_mysql}[@QUERY]{foo}[@LIMIT]{20}}
 *          [@RUN]{[@CMD]{read_state}}
 *          [@RUN]{[@CMD]{set_config}[@HOST]{localhost}[@USER]{root}[@PORT]{3306}}
 * BCL OUT: [@OK]{[@KEYWORD]{...}[@TOTAL]{N}[@MATCH]{...}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_toolstack.h"
#include <mysql.h>

/* ===== DIM BLOCK ===== */

#define SEARCHDB_MAX_QUERY     4096
#define SEARCHDB_MAX_SNIPPET   512
#define SEARCHDB_MAX_DB        64
#define SEARCHDB_DEFAULT_LIMIT 50
#define SEARCHDB_HOST_LEN      256
#define SEARCHDB_USER_LEN      64
#define SEARCHDB_PASS_LEN      128
#define SEARCHDB_SOCKET_LEN    256
#define SEARCHDB_BUF           8192
#define SEARCHDB_MAX_COLS      32

/* Search target descriptor — one per table.column to search */
typedef struct {
    char db[SEARCHDB_MAX_DB];
    char table[64];
    char search_col[128];
    char id_col[64];
    char snippet_col[128];
    char label[64];
} SearchDbTarget;

/* Known search targets — the knowledge base tables */
#define TARGET_COUNT 14
static const SearchDbTarget TARGETS[TARGET_COUNT] = {
    {"vb_shared", "learned_rules",  "pattern",      "id",      "pattern",      "learned_rule"},
    {"vb_shared", "learned_rules",  "fix_action",   "id",      "fix_action",   "rule_fix"},
    {"vb_shared", "know_problems",  "problem",      "id",      "description",  "problem"},
    {"vb_shared", "know_solutions", "solution",     "id",      "solution",     "solution"},
    {"vb_shared", "know_questions", "question",     "id",      "question",     "question"},
    {"vb_shared", "know_answers",   "answer",       "id",      "answer",       "answer"},
    {"vb_shared", "code_classes",   "class_name",   "id",      "description",  "class"},
    {"vb_shared", "code_classes",   "description",  "id",      "class_name",   "class_desc"},
    {"vb_shared", "instructions",   "instruction_name", "id",  "instruction_body", "instruction"},
    {"vb_shared", "instructions",   "instruction_body","id",   "instruction_name", "instruction_body"},
    {"vb_shared", "rule_tokens",    "name",         "id",      "bracket_body", "rule_token"},
    {"vb_code_test", "vb_classes",  "class_name",   "id",      "description",  "vb_class"},
    {"vb_code_test", "vb_methods",  "method_name",  "id",      "method_name",  "vb_method"},
    {"devin", "devin_messages",     "content",      "row_id",   "content",      "devin_msg"},
};

/* State */
static struct {
    int initialized;
    int connected;
    MYSQL *conn;
    char host[SEARCHDB_HOST_LEN];
    char user[SEARCHDB_USER_LEN];
    char pass[SEARCHDB_PASS_LEN];
    char socket[SEARCHDB_SOCKET_LEN];
    int port;
    int queries_run;
    int total_matches;
    int tables_searched;
    char last_error[256];
} STATE;

/* ===== BUILD MATCH — mode-aware WHERE clause ===== */

static void db_build_match(const char *col, const char *keyword,
                           const char *mode, char *out, size_t out_sz) {
    char escaped[SEARCHDB_MAX_QUERY];
    size_t ej = 0;
    for (size_t i = 0; keyword[i] && ej + 2 < sizeof(escaped); i++) {
        if (keyword[i] == '%' || keyword[i] == '_' || keyword[i] == '\\')
            escaped[ej++] = '\\';
        escaped[ej++] = keyword[i];
    }
    escaped[ej] = '\0';

    if (strcmp(mode, "exact") == 0) {
        snprintf(out, out_sz, "`%s` = '%s'", col, escaped);
    } else if (strcmp(mode, "prefix") == 0) {
        snprintf(out, out_sz, "`%s` LIKE '%s%%'", col, escaped);
    } else if (strcmp(mode, "regex") == 0) {
        snprintf(out, out_sz, "`%s` REGEXP '%s'", col, keyword);
    } else {
        snprintf(out, out_sz, "`%s` LIKE '%%%s%%'", col, escaped);
    }
}

/* ===== ENSURE CONNECTED ===== */

static int db_ensure_connected(void) {
    if (STATE.connected && STATE.conn) return 1;
    if (!STATE.conn) {
        STATE.conn = mysql_init(NULL);
        if (!STATE.conn) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed");
            return 0;
        }
    }
    const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
    MYSQL *result = mysql_real_connect(STATE.conn,
        STATE.host, STATE.user,
        STATE.pass[0] ? STATE.pass : NULL,
        NULL, STATE.port, sock, 0);
    if (!result) {
        result = mysql_real_connect(STATE.conn,
            STATE.host, STATE.user,
            STATE.pass[0] ? STATE.pass : NULL,
            NULL, STATE.port, NULL, 0);
    }
    if (!result) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "connect: %s", mysql_error(STATE.conn));
        return 0;
    }
    STATE.connected = 1;
    return 1;
}

/* ===== ESCAPE LIKE ===== */

static void db_escape_like(const char *in, char *out, size_t out_sz) {
    size_t pos = 0;
    for (size_t i = 0; in[i] && pos < out_sz - 8; i++) {
        if (in[i] == '%' || in[i] == '_' || in[i] == '\\') out[pos++] = '\\';
        out[pos++] = in[i];
    }
    out[pos] = '\0';
}

/* ===== ESCAPE SQL ===== */

static void db_escape_sql(const char *in, char *out, size_t out_sz) {
    if (STATE.conn) {
        mysql_real_escape_string(STATE.conn, out, in, (unsigned long)strlen(in));
    } else {
        strncpy(out, in, out_sz - 1);
        out[out_sz - 1] = '\0';
    }
}

/* ===== TRUNCATE TEXT ===== */

static void db_truncate_text(const char *in, char *out, int out_sz) {
    if (!in) { out[0] = '\0'; return; }
    int len = (int)strlen(in);
    if (len <= out_sz - 4) {
        strncpy(out, in, out_sz - 1);
        out[out_sz - 1] = '\0';
    } else {
        strncpy(out, in, out_sz - 4);
        out[out_sz - 4] = '\0';
        strcat(out, "...");
    }
    for (int i = 0; out[i]; i++) {
        if (out[i] == '\n' || out[i] == '\r') out[i] = ' ';
        if (out[i] == '{' || out[i] == '}') out[i] = ' ';
        if (out[i] == '[' && out[i + 1] == '@') out[i] = ' ';
    }
}

/* ===== PATCH TOTAL ===== */

static void db_patch_total(char *out, int total) {
    char total_str[64];
    snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", total);
    char *pos = strstr(out, "[@TOTAL]{0}");
    if (pos) {
        int old_len = (int)strlen("[@TOTAL]{0}");
        int new_len = (int)strlen(total_str);
        memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
        memcpy(pos, total_str, new_len);
    }
}

/* ===== SEARCH ONE TABLE ===== */

static int db_search_one_table(const SearchDbTarget *t, const char *keyword,
                               int limit, char *out, size_t out_sz, int *offset) {
    if (!db_ensure_connected()) return 0;
    char esc_key[SEARCHDB_MAX_QUERY];
    db_escape_like(keyword, esc_key, sizeof(esc_key));

    char query[SEARCHDB_MAX_QUERY];
    snprintf(query, sizeof(query),
        "SELECT `%s`, LEFT(`%s`, 300) FROM `%s`.`%s` WHERE `%s` LIKE '%%%s%%' LIMIT %d",
        t->id_col, t->snippet_col, t->db, t->table, t->search_col, esc_key, limit);

    if (mysql_query(STATE.conn, query) != 0) return 0;
    MYSQL_RES *res = mysql_store_result(STATE.conn);
    if (!res) return 0;

    int match_count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL && *offset < (int)out_sz - 512) {
        const char *row_id = row[0] ? row[0] : "0";
        const char *snippet_raw = row[1] ? row[1] : "";
        char snippet[SEARCHDB_MAX_SNIPPET];
        db_truncate_text(snippet_raw, snippet, sizeof(snippet));
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@MATCH]{[@TABLE]{%s.%s}[@LABEL]{%s}[@ID]{%s}[@TEXT]{%.400s}}",
            t->db, t->table, t->label, row_id, snippet);
        match_count++;
        STATE.total_matches++;
    }
    mysql_free_result(res);
    STATE.tables_searched++;
    return match_count;
}

/* ===== DISCOVER TABLES ===== */

static int db_discover_tables(const char *db_filter, char *out, size_t out_sz, int *offset) {
    if (!db_ensure_connected()) return 0;
    char query[512];
    if (db_filter && db_filter[0]) {
        char esc_db[128];
        db_escape_sql(db_filter, esc_db, sizeof(esc_db));
        snprintf(query, sizeof(query),
            "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = '%s' AND TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME", esc_db);
    } else {
        snprintf(query, sizeof(query),
            "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA IN ('vb_shared','vb_code_test','devin') "
            "AND TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME");
    }
    if (mysql_query(STATE.conn, query) != 0) return 0;
    MYSQL_RES *res = mysql_store_result(STATE.conn);
    if (!res) return 0;
    int count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL && *offset < (int)out_sz - 256) {
        const char *schema = row[0] ? row[0] : "";
        const char *table = row[1] ? row[1] : "";
        const char *rows = row[2] ? row[2] : "0";
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@TABLE]{[@DB]{%s}[@NAME]{%s}[@ROWS]{%s}}", schema, table, rows);
        count++;
    }
    mysql_free_result(res);
    return count;
}

/* ===== COUNT KEYWORD ===== */

static int db_count_keyword(const char *keyword, char *out, size_t out_sz) {
    if (!db_ensure_connected()) {
        return BclResult_Err(out, out_sz, 10, STATE.last_error);
    }
    char esc_key[SEARCHDB_MAX_QUERY];
    db_escape_like(keyword, esc_key, sizeof(esc_key));
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@KEYWORD]{%s}[@TOTAL]{0}", keyword);
    int total = 0;
    for (int i = 0; i < TARGET_COUNT; i++) {
        const SearchDbTarget *t = &TARGETS[i];
        char query[SEARCHDB_MAX_QUERY];
        snprintf(query, sizeof(query),
            "SELECT COUNT(*) FROM `%s`.`%s` WHERE `%s` LIKE '%%%s%%'",
            t->db, t->table, t->search_col, esc_key);
        if (mysql_query(STATE.conn, query) != 0) continue;
        MYSQL_RES *res = mysql_store_result(STATE.conn);
        if (!res) continue;
        MYSQL_ROW row = mysql_fetch_row(res);
        if (row && row[0]) {
            int cnt = atoi(row[0]);
            if (cnt > 0) {
                offset += snprintf(out + offset, out_sz - offset,
                    "[@COUNT]{[@TABLE]{%s.%s}[@HITS]{%d}}", t->db, t->table, cnt);
                total += cnt;
            }
        }
        mysql_free_result(res);
    }
    db_patch_total(out, total);
    offset = (int)strlen(out);
    snprintf(out + offset, out_sz - offset, "}");
    STATE.queries_run++;
    return 1;
}

/* ===== STATS ALL ===== */

static int db_stats_all(char *out, size_t out_sz) {
    if (!db_ensure_connected()) {
        return BclResult_Err(out, out_sz, 10, STATE.last_error);
    }
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset, "[@OK]{");
    const char *count_queries[] = {
        "SELECT 'learned_rules', COUNT(*) FROM vb_shared.learned_rules",
        "SELECT 'know_problems', COUNT(*) FROM vb_shared.know_problems",
        "SELECT 'know_solutions', COUNT(*) FROM vb_shared.know_solutions",
        "SELECT 'know_questions', COUNT(*) FROM vb_shared.know_questions",
        "SELECT 'know_answers', COUNT(*) FROM vb_shared.know_answers",
        "SELECT 'code_classes', COUNT(*) FROM vb_shared.code_classes",
        "SELECT 'instructions', COUNT(*) FROM vb_shared.instructions",
        "SELECT 'rule_tokens', COUNT(*) FROM vb_shared.rule_tokens",
        "SELECT 'vb_classes', COUNT(*) FROM vb_code_test.vb_classes",
        "SELECT 'vb_methods', COUNT(*) FROM vb_code_test.vb_methods",
        "SELECT 'devin_messages', COUNT(*) FROM devin.devin_messages",
        "SELECT 'devin_summaries', COUNT(*) FROM devin.devin_summaries",
        NULL
    };
    for (int i = 0; count_queries[i] != NULL; i++) {
        if (mysql_query(STATE.conn, count_queries[i]) != 0) continue;
        MYSQL_RES *res = mysql_store_result(STATE.conn);
        if (!res) continue;
        MYSQL_ROW row = mysql_fetch_row(res);
        if (row && row[0] && row[1]) {
            offset += snprintf(out + offset, out_sz - offset,
                "[@TABLE]{[@NAME]{%s}[@ROWS]{%s}}", row[0], row[1]);
        }
        mysql_free_result(res);
    }
    offset += snprintf(out + offset, out_sz - offset,
        "[@META]{[@QUERIES]{%d}[@MATCHES]{%d}[@TABLES_SEARCHED]{%d}}",
        STATE.queries_run, STATE.total_matches, STATE.tables_searched);
    snprintf(out + offset, out_sz - offset, "}");
    return 1;
}

/* ===== UNIT INTERFACE ===== */

int SearchDb_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host, "localhost", sizeof(STATE.host) - 1);
    strncpy(STATE.user, "root", sizeof(STATE.user) - 1);
    STATE.pass[0] = '\0';
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    STATE.initialized = 1;
    return 1;
}

int SearchDb_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) SearchDb_Init();
    STATE.queries_run++;

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        return BclResult_Ok(bcl_out, out_sz,
            "[@INITIALIZED]{1}[@CONNECTED]{1}[@QUERIES]{...}[@MATCHES]{...}");
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[128] = {0}, user[64] = {0}, port[16] = {0}, pass[128] = {0};
        char sock[256] = {0};
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PORT", port, sizeof(port));
        BclParser_Extract(&parse, "PASS", pass, sizeof(pass));
        BclParser_Extract(&parse, "SOCKET", sock, sizeof(sock));
        BclParser_Free(&parse);
        if (host[0]) strncpy(STATE.host, host, sizeof(STATE.host) - 1);
        if (user[0]) strncpy(STATE.user, user, sizeof(STATE.user) - 1);
        if (port[0]) STATE.port = atoi(port);
        if (pass[0]) strncpy(STATE.pass, pass, sizeof(STATE.pass) - 1);
        if (sock[0]) strncpy(STATE.socket, sock, sizeof(STATE.socket) - 1);
        if (STATE.conn) { mysql_close(STATE.conn); STATE.conn = NULL; }
        STATE.connected = 0;
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* ===== SEARCH ===== */
    if (strcmp(cmd, "search") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[SEARCHDB_MAX_QUERY] = {0};
        char limit_str[32] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int limit = limit_str[0] ? atoi(limit_str) : SEARCHDB_DEFAULT_LIMIT;
        if (limit <= 0 || limit > 500) limit = SEARCHDB_DEFAULT_LIMIT;
        if (!db_ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@KEYWORD]{%s}[@TOTAL]{0}", query);
        int total = 0;
        for (int i = 0; i < TARGET_COUNT; i++) {
            total += db_search_one_table(&TARGETS[i], query, limit, bcl_out, out_sz, &offset);
        }
        db_patch_total(bcl_out, total);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    /* ===== WHERE ===== */
    if (strcmp(cmd, "where") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char db_filter[128] = {0};
        BclParser_Extract(&parse, "DB", db_filter, sizeof(db_filter));
        BclParser_Free(&parse);
        if (!db_ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{[@TOTAL]{0}");
        int count = db_discover_tables(db_filter[0] ? db_filter : NULL, bcl_out, out_sz, &offset);
        db_patch_total(bcl_out, count);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    /* ===== COUNT ===== */
    if (strcmp(cmd, "count") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[SEARCHDB_MAX_QUERY] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        return db_count_keyword(query, bcl_out, out_sz);
    }

    /* ===== STATS ===== */
    if (strcmp(cmd, "stats") == 0) {
        return db_stats_all(bcl_out, out_sz);
    }

    /* ===== SEARCH_SCHEMA ===== */
    if (strcmp(cmd, "search_schema") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[SEARCHDB_MAX_QUERY] = {0};
        char mode_str[16] = {0}, db_str[64] = {0}, limit_str[32] = {0};
        char status_filter[64] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "MODE", mode_str, sizeof(mode_str));
        BclParser_Extract(&parse, "DB", db_str, sizeof(db_str));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Extract(&parse, "STATUS", status_filter, sizeof(status_filter));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        const char *mode = mode_str[0] ? mode_str : "contains";
        const char *db = db_str[0] ? db_str : "vb_shared";
        int limit = limit_str[0] ? atoi(limit_str) : SEARCHDB_DEFAULT_LIMIT;
        if (limit <= 0 || limit > 500) limit = SEARCHDB_DEFAULT_LIMIT;
        if (!db_ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }
        char use_q[128];
        snprintf(use_q, sizeof(use_q), "USE `%s`", db);
        mysql_query(STATE.conn, use_q);
        if (mysql_query(STATE.conn, "SHOW TABLES") != 0) {
            return BclResult_Err(bcl_out, out_sz, 30, "SHOW TABLES failed");
        }
        MYSQL_RES *tres = mysql_store_result(STATE.conn);
        if (!tres) return BclResult_Err(bcl_out, out_sz, 31, "no tables");

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@KEYWORD]{%s}[@DB]{%s}[@TOTAL]{0}", query, db);
        int total = 0;
        MYSQL_ROW trow;
        while ((trow = mysql_fetch_row(tres)) != NULL && offset < (int)out_sz - 2048) {
            const char *tname = trow[0] ? trow[0] : "";
            char cq[512];
            snprintf(cq, sizeof(cq),
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s' AND "
                "(DATA_TYPE LIKE '%%char%%' OR DATA_TYPE LIKE '%%text%%') "
                "ORDER BY ORDINAL_POSITION LIMIT %d",
                db, tname, SEARCHDB_MAX_COLS);
            if (mysql_query(STATE.conn, cq) != 0) continue;
            MYSQL_RES *cres = mysql_store_result(STATE.conn);
            if (!cres) continue;
            char cols[SEARCHDB_MAX_COLS][128];
            int col_count = 0;
            MYSQL_ROW crow;
            while ((crow = mysql_fetch_row(cres)) != NULL && col_count < SEARCHDB_MAX_COLS) {
                strncpy(cols[col_count], crow[0] ? crow[0] : "", 127);
                cols[col_count][127] = '\0';
                col_count++;
            }
            mysql_free_result(cres);
            if (col_count == 0) continue;

            char where[SEARCHDB_BUF];
            size_t wpos = 0;
            for (int c = 0; c < col_count; c++) {
                char match_frag[512];
                db_build_match(cols[c], query, mode, match_frag, sizeof(match_frag));
                int written = snprintf(where + wpos, sizeof(where) - wpos,
                    "%s%s", (c ? " OR " : ""), match_frag);
                if (written < 0 || (size_t)written >= sizeof(where) - wpos) break;
                wpos += written;
            }
            if (status_filter[0]) {
                int written = snprintf(where + wpos, sizeof(where) - wpos,
                    " AND `status` LIKE '%%%s%%'", status_filter);
                if (written > 0 && (size_t)written < sizeof(where) - wpos) wpos += written;
            }
            char sql[SEARCHDB_BUF * 2];
            snprintf(sql, sizeof(sql), "SELECT * FROM `%s` WHERE %s LIMIT %d",
                tname, where, limit);
            if (mysql_query(STATE.conn, sql) != 0) continue;
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (!res) continue;
            int fcount = mysql_num_fields(res);
            MYSQL_ROW row;
            int row_idx = 0;
            while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 1024) {
                if (row_idx == 0) {
                    offset += snprintf(bcl_out + offset, out_sz - offset,
                        "[@TABLE]{[@NAME]{%s}", tname);
                }
                offset += snprintf(bcl_out + offset, out_sz - offset,
                    "[@ROW]{[@IDX]{%d}", row_idx + 1);
                unsigned long *lens = mysql_fetch_lengths(res);
                MYSQL_FIELD *fields = mysql_fetch_fields(res);
                for (int f = 0; f < fcount && offset < (int)out_sz - 512; f++) {
                    const char *val = row[f] ? row[f] : "";
                    int vlen = (int)lens[f];
                    if (vlen > 200) vlen = 200;
                    char clean[256];
                    int ci = 0;
                    for (int vi = 0; vi < vlen && ci < 250; vi++) {
                        if (val[vi] == '\n' || val[vi] == '\r' || val[vi] == '{' || val[vi] == '}')
                            clean[ci++] = ' ';
                        else if (val[vi] == '[' && val[vi + 1] == '@')
                            clean[ci++] = ' ';
                        else
                            clean[ci++] = val[vi];
                    }
                    clean[ci] = '\0';
                    offset += snprintf(bcl_out + offset, out_sz - offset,
                        "[@FLD]{[@NAME]{%s}[@VAL]{%.200s}}", fields[f].name, clean);
                }
                offset += snprintf(bcl_out + offset, out_sz - offset, "}");
                row_idx++;
                total++;
            }
            if (row_idx > 0) {
                offset += snprintf(bcl_out + offset, out_sz - offset, "}");
            }
            mysql_free_result(res);
            STATE.tables_searched++;
        }
        mysql_free_result(tres);
        db_patch_total(bcl_out, total);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    /* ===== SEARCH_ALL_DB ===== */
    if (strcmp(cmd, "search_all_db") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[SEARCHDB_MAX_QUERY] = {0};
        char limit_str[32] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int limit = limit_str[0] ? atoi(limit_str) : SEARCHDB_DEFAULT_LIMIT;
        if (limit <= 0 || limit > 500) limit = SEARCHDB_DEFAULT_LIMIT;
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@KEYWORD]{%s}[@TOTAL]{0}", query);
        const char *dbs[] = {"vb_shared", "CODEBASE", NULL};
        int total = 0;
        char esc_key[SEARCHDB_MAX_QUERY];
        db_escape_like(query, esc_key, sizeof(esc_key));
        for (int d = 0; dbs[d] && offset < (int)out_sz - 2048; d++) {
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@DB]{[@NAME]{%s}", dbs[d]);
            MYSQL *dconn = mysql_init(NULL);
            if (!dconn) { offset += snprintf(bcl_out + offset, out_sz - offset, "}"); continue; }
            const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
            MYSQL *r = mysql_real_connect(dconn, STATE.host, STATE.user,
                STATE.pass[0] ? STATE.pass : NULL, dbs[d], STATE.port, sock, 0);
            if (!r) {
                r = mysql_real_connect(dconn, STATE.host, STATE.user,
                    STATE.pass[0] ? STATE.pass : NULL, dbs[d], STATE.port, NULL, 0);
            }
            if (!r) { mysql_close(dconn); offset += snprintf(bcl_out + offset, out_sz - offset, "}"); continue; }
            if (mysql_query(dconn, "SHOW TABLES") == 0) {
                MYSQL_RES *tres = mysql_store_result(dconn);
                if (tres) {
                    MYSQL_ROW trow;
                    while ((trow = mysql_fetch_row(tres)) != NULL && offset < (int)out_sz - 1024) {
                        const char *tname = trow[0] ? trow[0] : "";
                        char cq[512];
                        snprintf(cq, sizeof(cq),
                            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                            "WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s' AND "
                            "(DATA_TYPE LIKE '%%char%%' OR DATA_TYPE LIKE '%%text%%') LIMIT 1",
                            dbs[d], tname);
                        if (mysql_query(dconn, cq) != 0) continue;
                        MYSQL_RES *cres = mysql_store_result(dconn);
                        if (!cres) continue;
                        MYSQL_ROW crow = mysql_fetch_row(cres);
                        if (!crow || !crow[0]) { mysql_free_result(cres); continue; }
                        char first_col[128];
                        strncpy(first_col, crow[0], 127);
                        first_col[127] = '\0';
                        mysql_free_result(cres);
                        char sql[SEARCHDB_BUF];
                        snprintf(sql, sizeof(sql),
                            "SELECT * FROM `%s` WHERE `%s` LIKE '%%%s%%' LIMIT %d",
                            tname, first_col, esc_key, limit);
                        if (mysql_query(dconn, sql) != 0) continue;
                        MYSQL_RES *res = mysql_store_result(dconn);
                        if (!res) continue;
                        MYSQL_ROW row;
                        while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                            offset += snprintf(bcl_out + offset, out_sz - offset,
                                "[@MATCH]{[@TABLE]{%s.%s}[@TEXT]{%.200s}}",
                                dbs[d], tname, row[0] ? row[0] : "");
                            total++;
                        }
                        mysql_free_result(res);
                    }
                    mysql_free_result(tres);
                }
            }
            mysql_close(dconn);
            offset += snprintf(bcl_out + offset, out_sz - offset, "}");
        }
        db_patch_total(bcl_out, total);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    /* ===== SEARCH_ALL_MYSQL ===== */
    if (strcmp(cmd, "search_all_mysql") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[SEARCHDB_MAX_QUERY] = {0};
        char limit_str[32] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int limit = limit_str[0] ? atoi(limit_str) : 20;
        if (limit <= 0 || limit > 200) limit = 20;
        if (!db_ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@KEYWORD]{%s}[@TOTAL]{0}", query);
        char esc_key[SEARCHDB_MAX_QUERY];
        db_escape_like(query, esc_key, sizeof(esc_key));

        if (mysql_query(STATE.conn,
            "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
            "WHERE SCHEMA_NAME NOT IN ('information_schema','mysql','performance_schema','sys')")
            != 0) {
            return BclResult_Err(bcl_out, out_sz, 30, "schema discovery failed");
        }
        MYSQL_RES *sres = mysql_store_result(STATE.conn);
        if (!sres) return BclResult_Err(bcl_out, out_sz, 31, "no schemas");
        int total = 0;
        MYSQL_ROW srow;
        while ((srow = mysql_fetch_row(sres)) != NULL && offset < (int)out_sz - 2048) {
            const char *sname = srow[0] ? srow[0] : "";
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@DB]{[@NAME]{%s}", sname);
            MYSQL *dconn = mysql_init(NULL);
            if (!dconn) { offset += snprintf(bcl_out + offset, out_sz - offset, "}"); continue; }
            const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
            MYSQL *r = mysql_real_connect(dconn, STATE.host, STATE.user,
                STATE.pass[0] ? STATE.pass : NULL, sname, STATE.port, sock, 0);
            if (!r) {
                r = mysql_real_connect(dconn, STATE.host, STATE.user,
                    STATE.pass[0] ? STATE.pass : NULL, sname, STATE.port, NULL, 0);
            }
            if (!r) { mysql_close(dconn); offset += snprintf(bcl_out + offset, out_sz - offset, "}"); continue; }
            if (mysql_query(dconn, "SHOW TABLES") == 0) {
                MYSQL_RES *tres = mysql_store_result(dconn);
                if (tres) {
                    MYSQL_ROW trow;
                    while ((trow = mysql_fetch_row(tres)) != NULL && offset < (int)out_sz - 1024) {
                        const char *tname = trow[0] ? trow[0] : "";
                        char cq[512];
                        snprintf(cq, sizeof(cq),
                            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                            "WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s' AND "
                            "(DATA_TYPE LIKE '%%char%%' OR DATA_TYPE LIKE '%%text%%') LIMIT 1",
                            sname, tname);
                        if (mysql_query(dconn, cq) != 0) continue;
                        MYSQL_RES *cres = mysql_store_result(dconn);
                        if (!cres) continue;
                        MYSQL_ROW crow = mysql_fetch_row(cres);
                        if (!crow || !crow[0]) { mysql_free_result(cres); continue; }
                        char first_col[128];
                        strncpy(first_col, crow[0], 127);
                        first_col[127] = '\0';
                        mysql_free_result(cres);
                        char sql[SEARCHDB_BUF];
                        snprintf(sql, sizeof(sql),
                            "SELECT * FROM `%s` WHERE `%s` LIKE '%%%s%%' LIMIT %d",
                            tname, first_col, esc_key, limit);
                        if (mysql_query(dconn, sql) != 0) continue;
                        MYSQL_RES *res = mysql_store_result(dconn);
                        if (!res) continue;
                        MYSQL_ROW row;
                        while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                            offset += snprintf(bcl_out + offset, out_sz - offset,
                                "[@MATCH]{[@TABLE]{%s.%s}[@TEXT]{%.200s}}",
                                sname, tname, row[0] ? row[0] : "");
                            total++;
                        }
                        mysql_free_result(res);
                    }
                    mysql_free_result(tres);
                }
            }
            mysql_close(dconn);
            offset += snprintf(bcl_out + offset, out_sz - offset, "}");
        }
        mysql_free_result(sres);
        db_patch_total(bcl_out, total);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int SearchDb_Close(void) {
    if (STATE.conn) { mysql_close(STATE.conn); STATE.conn = NULL; }
    STATE.connected = 0;
    STATE.initialized = 0;
    return 1;
}

const char * SearchDb_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "SearchDb: initialized=%d connected=%d queries=%d matches=%d tables=%d",
        STATE.initialized, STATE.connected, STATE.queries_run,
        STATE.total_matches, STATE.tables_searched);
    return buf;
}
