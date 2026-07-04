//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_msearch.c" date="2026-06-29" author="devin" session_id="bcl-msearch-impl" context="BCL unit for MySQL keyword search across vb_shared, vb_code_test, devin databases. Converted from core/utility/msearch.py + msearch v6 binary spec. Searches learned_rules, know_problems, know_solutions, know_questions, know_answers, code_classes, instructions, rule_tokens, vb_classes, vb_methods, devin_messages, devin_summaries."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_msearch.c" domain="cascade_tools" authority="Msearch"}
//[@SUMMARY]{summary="MySQL keyword search across all knowledge databases. Commands: search, where, count, stats, read_state, set_config. Connects to localhost root no-password. Searches 12+ tables in 3 databases. Returns BCL packets with match results."}
//[@CLASS]{class="Msearch" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Connect" type="command"}
//[@METHOD]{method="SearchKeyword" type="query"}
//[@METHOD]{method="SearchTable" type="query"}
//[@METHOD]{method="DiscoverTables" type="query"}
//[@METHOD]{method="CountKeyword" type="query"}
//[@METHOD]{method="Stats" type="query"}
//[@METHOD]{method="EscapeString" type="command"}
//[@METHOD]{method="ReadState" type="command"}
//[@METHOD]{method="SetConfig" type="command"}
//[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<implementation>][@notes<MySQL C client via mysql_config. LIKE keyword search. BCL packet output. Multi-database multi-table.>][@todos<link mysqlclient, test compile, verify searches>]}

/*
 * bcl_msearch.c — MySQL keyword search across knowledge databases
 *
 * BCL IN:  [@RUN]{[@CMD]{search}[@QUERY]{keyword}[@LIMIT]{50}}
 *          [@RUN]{[@CMD]{count}[@QUERY]{keyword}}
 *          [@RUN]{[@CMD]{where}[@DB]{vb_shared}}
 *          [@RUN]{[@CMD]{stats}}
 *          [@RUN]{[@CMD]{read_state}}
 *          [@RUN]{[@CMD]{set_config}[@HOST]{localhost}[@USER]{root}[@PORT]{3306}}
 * BCL OUT: [@OK]{[@KEYWORD]{...}[@TOTAL]{N}[@MATCH]{...}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_toolstack.h"
#include <mysql.h>
#include <dirent.h>
#include <sys/stat.h>
#include <time.h>

/* ===== DIM BLOCK ===== */

#define MSEARCH_MAX_QUERY    4096
#define MSEARCH_MAX_SNIPPET  512
#define MSEARCH_MAX_TABLES   32
#define MSEARCH_MAX_DB       64
#define MSEARCH_DEFAULT_LIMIT 50
#define MSEARCH_HOST_LEN     256
#define MSEARCH_USER_LEN     64
#define MSEARCH_PASS_LEN     128
#define MSEARCH_SOCKET_LEN   256
#define MSEARCH_BUF          8192
#define MSEARCH_MAX_DB_S     32
#define MSEARCH_MAX_COLS     32

/* Search target descriptor — one per table.column to search */
typedef struct {
    char db[MSEARCH_MAX_DB];
    char table[64];
    char search_col[128];     /* column to LIKE search */
    char id_col[64];          /* PK column for row id */
    char snippet_col[128];    /* column for snippet text */
    char label[64];           /* human label for result */
} SearchTarget;

/* Known search targets — the knowledge base tables */
#define TARGET_COUNT 14
static const SearchTarget TARGETS[TARGET_COUNT] = {
    /* vb_shared — rules and knowledge */
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
    /* vb_code_test — code registry */
    {"vb_code_test", "vb_classes",  "class_name",   "id",      "description",  "vb_class"},
    {"vb_code_test", "vb_methods",  "method_name",  "id",      "method_name",  "vb_method"},
    /* devin — session history */
    {"devin", "devin_messages",    "content",      "row_id",   "content",      "devin_msg"},
};

/* State */
static struct {
    MYSQL *conn;
    int initialized;
    int connected;
    char host[MSEARCH_HOST_LEN];
    char user[MSEARCH_USER_LEN];
    char pass[MSEARCH_PASS_LEN];
    char socket[MSEARCH_SOCKET_LEN];
    int port;
    int queries_run;
    int total_matches;
    int tables_searched;
    char last_error[256];
} STATE;

/* ===== BUILD MATCH — mode-aware WHERE clause (not in any other unit) ===== */

static void build_match(const char *col, const char *keyword,
                         const char *mode, char *out, size_t out_sz) {
    char escaped[MSEARCH_MAX_QUERY];
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

/* ===== MYSQL CONNECT ===== */

static int ensure_connected(void) {
    if (STATE.connected && STATE.conn) return 1;
    if (!STATE.conn) {
        STATE.conn = mysql_init(NULL);
        if (!STATE.conn) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed");
            return 0;
        }
    }
    /* Try socket first (faster, no TCP), then TCP */
    const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
    MYSQL *result = mysql_real_connect(STATE.conn,
        STATE.host, STATE.user,
        STATE.pass[0] ? STATE.pass : NULL,
        NULL, STATE.port, sock, 0);
    if (!result) {
        /* Retry without socket (TCP fallback) */
        result = mysql_real_connect(STATE.conn,
            STATE.host, STATE.user,
            STATE.pass[0] ? STATE.pass : NULL,
            NULL, STATE.port, NULL, 0);
    }
    if (!result) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "connect: %s",
                 mysql_error(STATE.conn));
        return 0;
    }
    STATE.connected = 1;
    return 1;
}

/* ===== ESCAPE STRING ===== */

static void escape_like(MYSQL *conn, const char *in, char *out, size_t out_sz) {
    /* For LIKE patterns — escape % and _ literally, then wrap in %% */
    size_t pos = 0;
    for (size_t i = 0; in[i] && pos < out_sz - 8; i++) {
        if (in[i] == '%' || in[i] == '_' || in[i] == '\\') {
            out[pos++] = '\\';
        }
        out[pos++] = in[i];
    }
    out[pos] = '\0';
}

static void escape_sql(MYSQL *conn, const char *in, char *out, size_t out_sz) {
    mysql_real_escape_string(conn, out, in, (unsigned long)strlen(in));
}

/* ===== TRUNCATE FOR SNIPPET ===== */

static void truncate_text(const char *in, char *out, int out_sz) {
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
    /* Strip newlines from snippet (BCL packets are single-line) */
    for (int i = 0; out[i]; i++) {
        if (out[i] == '\n' || out[i] == '\r') out[i] = ' ';
        if (out[i] == '{' || out[i] == '}') out[i] = ' ';
        if (out[i] == '[' && out[i+1] == '@') out[i] = ' ';
    }
}

/* ===== SEARCH ONE TABLE ===== */

static int search_one_table(const SearchTarget *t, const char *keyword,
                             int limit, char *out, size_t out_sz, int *offset) {
    if (!ensure_connected()) return 0;

    char esc_key[MSEARCH_MAX_QUERY];
    escape_like(STATE.conn, keyword, esc_key, sizeof(esc_key));

    char like_pattern[MSEARCH_MAX_QUERY];
    snprintf(like_pattern, sizeof(like_pattern), "%%%s%%", esc_key);

    char query[MSEARCH_MAX_QUERY];
    snprintf(query, sizeof(query),
        "SELECT `%s`, LEFT(`%s`, 300) FROM `%s`.`%s` WHERE `%s` LIKE '%%%s%%' LIMIT %d",
        t->id_col, t->snippet_col, t->db, t->table, t->search_col, esc_key, limit);

    if (mysql_query(STATE.conn, query) != 0) {
        /* Table might not exist or column mismatch — skip silently */
        return 0;
    }

    MYSQL_RES *res = mysql_store_result(STATE.conn);
    if (!res) return 0;

    int match_count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL && *offset < (int)out_sz - 512) {
        const char *row_id = row[0] ? row[0] : "0";
        const char *snippet_raw = row[1] ? row[1] : "";
        char snippet[MSEARCH_MAX_SNIPPET];
        truncate_text(snippet_raw, snippet, sizeof(snippet));

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

/* ===== DISCOVER TABLES (where) ===== */

static int discover_tables(const char *db_filter, char *out, size_t out_sz, int *offset) {
    if (!ensure_connected()) return 0;

    char query[512];
    if (db_filter && db_filter[0]) {
        char esc_db[128];
        escape_sql(STATE.conn, db_filter, esc_db, sizeof(esc_db));
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

    if (mysql_query(STATE.conn, query) != 0) {
        return 0;
    }

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

static int count_keyword(const char *keyword, char *out, size_t out_sz) {
    if (!ensure_connected()) {
        return BclResult_Err(out, out_sz, 10, STATE.last_error);
    }

    char esc_key[MSEARCH_MAX_QUERY];
    escape_like(STATE.conn, keyword, esc_key, sizeof(esc_key));

    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset, "[@OK]{[@KEYWORD]{%s}", keyword);

    int total = 0;
    for (int i = 0; i < TARGET_COUNT; i++) {
        const SearchTarget *t = &TARGETS[i];
        char query[MSEARCH_MAX_QUERY];
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

    /* Patch total into front — prepend total count */
    char total_str[64];
    snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", total);
    /* Insert after [@KEYWORD]{...} */
    char insert_point[128];
    snprintf(insert_point, sizeof(insert_point), "[@KEYWORD]{%s}", keyword);
    char *pos = strstr(out, insert_point);
    if (pos) {
        pos += strlen(insert_point);
        int remaining = strlen(pos);
        memmove(pos + strlen(total_str), pos, remaining + 1);
        memcpy(pos, total_str, strlen(total_str));
    }
    offset = strlen(out);
    snprintf(out + offset, out_sz - offset, "}");
    STATE.queries_run++;
    return 1;
}

/* ===== STATS ===== */

static int stats_all(char *out, size_t out_sz) {
    if (!ensure_connected()) {
        return BclResult_Err(out, out_sz, 10, STATE.last_error);
    }

    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset, "[@OK]{");

    /* Count rows in key tables */
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

/* ===== SEARCH FILES — filesystem search with ext + content + time filters ===== */

static int search_files(const char *root_dir, const char *ext_filter,
                         const char *keyword, int within_hours,
                         char *out, size_t out_sz) {
    DIR *dir = opendir(root_dir);
    if (!dir) {
        return BclResult_Err(out, out_sz, 50, "cannot open directory");
    }

    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@ROOT]{%s}[@EXT]{%s}[@KEYWORD]{%s}[@HOURS]{%d}[@TOTAL]{0}",
        root_dir, ext_filter ? ext_filter : "*", keyword ? keyword : "*", within_hours);

    int total = 0;
    time_t now = time(NULL);
    time_t cutoff = now - (within_hours * 3600);
    struct dirent *ent;

    while ((ent = readdir(dir)) != NULL && offset < (int)out_sz - 1024) {
        if (ent->d_name[0] == '.') continue;

        char path[1024];
        snprintf(path, sizeof(path), "%s/%s", root_dir, ent->d_name);

        struct stat st;
        if (stat(path, &st) != 0) continue;

        /* Recurse into directories */
        if (S_ISDIR(st.st_mode)) {
            char sub_out[TOOL_MAX_RESULT];
            search_files(path, ext_filter, keyword, within_hours, sub_out, sizeof(sub_out));
            /* Extract matches from sub-result and append */
            const char *sub_start = strstr(sub_out, "[@OK]{");
            if (sub_start) {
                sub_start += 6;
                const char *sub_total = strstr(sub_start, "[@TOTAL]{");
                if (sub_total) {
                    /* Find the matches after the header */
                    const char *cursor = sub_total;
                    while (cursor && *cursor) {
                        cursor = strstr(cursor, "[@FILE]{");
                        if (!cursor) break;
                        const char *end = strstr(cursor, "}");
                        if (!end) break;
                        int frag_len = end - cursor + 1;
                        if (offset + frag_len < (int)out_sz - 512) {
                            memcpy(out + offset, cursor, frag_len);
                            offset += frag_len;
                        }
                        cursor = end + 1;
                        total++;
                    }
                }
            }
            continue;
        }

        /* Extension filter */
        if (ext_filter && ext_filter[0]) {
            const char *dot = strrchr(ent->d_name, '.');
            if (!dot || strcasecmp(dot + 1, ext_filter) != 0) continue;
        }

        /* Time filter */
        if (within_hours > 0 && st.st_mtime < cutoff) continue;

        /* Content keyword filter — grep the file */
        if (keyword && keyword[0]) {
            FILE *fp = fopen(path, "r");
            if (!fp) continue;
            char line[1024];
            int found = 0;
            int line_num = 0;
            while (fgets(line, sizeof(line), fp) && !found) {
                line_num++;
                if (strcasestr(line, keyword)) {
                    found = 1;
                }
            }
            fclose(fp);
            if (!found) continue;

            /* Re-open to collect matching lines */
            fp = fopen(path, "r");
            if (!fp) continue;
            offset += snprintf(out + offset, out_sz - offset,
                "[@FILE]{[@PATH]{%s}[@MATCHES]{", path);
            int match_count = 0;
            line_num = 0;
            while (fgets(line, sizeof(line), fp) && match_count < 20 && offset < (int)out_sz - 512) {
                line_num++;
                if (strcasestr(line, keyword)) {
                    /* Clean line for BCL */
                    char clean[1024];
                    int ci = 0;
                    for (int li = 0; line[li] && ci < 1000; li++) {
                        if (line[li] == '\n' || line[li] == '\r' || line[li] == '{' || line[li] == '}')
                            clean[ci++] = ' ';
                        else if (line[li] == '[' && line[li+1] == '@')
                            clean[ci++] = ' ';
                        else
                            clean[ci++] = line[li];
                    }
                    clean[ci] = '\0';
                    offset += snprintf(out + offset, out_sz - offset,
                        "[@LINE]{[@NUM]{%d}[@TEXT]{%.200s}}", line_num, clean);
                    match_count++;
                }
            }
            fclose(fp);
            offset += snprintf(out + offset, out_sz - offset, "}");
            total++;
        } else {
            /* No keyword filter — just list the file */
            offset += snprintf(out + offset, out_sz - offset,
                "[@FILE]{[@PATH]{%s}[@SIZE]{%lld}[@MTIME]{%ld}}",
                path, (long long)st.st_size, (long)st.st_mtime);
            total++;
        }
    }
    closedir(dir);

    /* Patch total */
    char total_str[64];
    snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", total);
    char *pos = strstr(out, "[@TOTAL]{0}");
    if (pos) {
        int old_len = strlen("[@TOTAL]{0}");
        int new_len = strlen(total_str);
        memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
        memcpy(pos, total_str, new_len);
    }
    offset = strlen(out);
    snprintf(out + offset, out_sz - offset, "}");
    return 1;
}

/* ===== UNIT INTERFACE ===== */

int Msearch_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host, "localhost", sizeof(STATE.host) - 1);
    strncpy(STATE.user, "root", sizeof(STATE.user) - 1);
    STATE.pass[0] = '\0';
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    STATE.initialized = 1;
    return 1;
}

int Msearch_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Msearch_Init();

    /* ===== SEARCH — keyword across all known tables ===== */
    if (strcmp(cmd, "search") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[MSEARCH_MAX_QUERY] = {0};
        char limit_str[32] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int limit = limit_str[0] ? atoi(limit_str) : MSEARCH_DEFAULT_LIMIT;
        if (limit <= 0 || limit > 500) limit = MSEARCH_DEFAULT_LIMIT;

        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@KEYWORD]{%s}[@TOTAL]{0}", query);

        int total = 0;
        for (int i = 0; i < TARGET_COUNT; i++) {
            int matched = search_one_table(&TARGETS[i], query, limit,
                                           bcl_out, out_sz, &offset);
            total += matched;
        }

        /* Patch total count */
        char total_str[64];
        snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", total);
        char *pos = strstr(bcl_out, "[@TOTAL]{0}");
        if (pos) {
            int old_len = strlen("[@TOTAL]{0}");
            int new_len = strlen(total_str);
            memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
            memcpy(pos, total_str, new_len);
        }
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        STATE.queries_run++;
        return 1;
    }

    /* ===== WHERE — table discovery ===== */
    if (strcmp(cmd, "where") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char db_filter[128] = {0};
        BclParser_Extract(&parse, "DB", db_filter, sizeof(db_filter));
        BclParser_Free(&parse);

        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{[@TOTAL]{0}");
        int count = discover_tables(db_filter[0] ? db_filter : NULL,
                                    bcl_out, out_sz, &offset);

        char total_str[64];
        snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", count);
        char *pos = strstr(bcl_out, "[@TOTAL]{0}");
        if (pos) {
            int old_len = strlen("[@TOTAL]{0}");
            int new_len = strlen(total_str);
            memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
            memcpy(pos, total_str, new_len);
        }
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    /* ===== COUNT — count keyword hits per table ===== */
    if (strcmp(cmd, "count") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[MSEARCH_MAX_QUERY] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        return count_keyword(query, bcl_out, out_sz);
    }

    /* ===== STATS — database overview ===== */
    if (strcmp(cmd, "stats") == 0) {
        return stats_all(bcl_out, out_sz);
    }

    /* ===== SEARCH_FILES — filesystem search with ext + content + time filters ===== */
    if (strcmp(cmd, "search_files") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char root[512] = {0};
        char ext[32] = {0};
        char query[MSEARCH_MAX_QUERY] = {0};
        char hours_str[16] = {0};
        BclParser_Extract(&parse, "ROOT", root, sizeof(root));
        BclParser_Extract(&parse, "EXT", ext, sizeof(ext));
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "HOURS", hours_str, sizeof(hours_str));
        BclParser_Free(&parse);
        if (!root[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no ROOT in packet");
        }
        int hours = hours_str[0] ? atoi(hours_str) : 0;
        return search_files(root, ext[0] ? ext : NULL,
                            query[0] ? query : NULL, hours,
                            bcl_out, out_sz);
    }

    /* ===== SEARCH_SCHEMA — schema-aware search using registry discovery ===== */
    if (strcmp(cmd, "search_schema") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[MSEARCH_MAX_QUERY] = {0};
        char mode_str[16] = {0};
        char db_str[64] = {0};
        char limit_str[32] = {0};
        char status_filter[64] = {0};
        char context_str[256] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "MODE", mode_str, sizeof(mode_str));
        BclParser_Extract(&parse, "DB", db_str, sizeof(db_str));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Extract(&parse, "STATUS", status_filter, sizeof(status_filter));
        BclParser_Extract(&parse, "CONTEXT", context_str, sizeof(context_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        const char *mode = mode_str[0] ? mode_str : "contains";
        const char *db = db_str[0] ? db_str : "vb_shared";
        int limit = limit_str[0] ? atoi(limit_str) : MSEARCH_DEFAULT_LIMIT;
        if (limit <= 0 || limit > 500) limit = MSEARCH_DEFAULT_LIMIT;

        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }

        /* Ask registry unit to discover schema for this database */
        char reg_in[512];
        snprintf(reg_in, sizeof(reg_in), "[@CMD]{discover_schema}[@DB]{%s}", db);
        char reg_out[TOOL_MAX_RESULT];
        MsearchRegistry_Run("discover_schema", reg_in, reg_out, sizeof(reg_out));

        /* Now search each table in the database using SHOW TABLES + column discovery */
        char esc_key[MSEARCH_MAX_QUERY];
        size_t ek = 0;
        for (size_t i = 0; query[i] && ek + 2 < sizeof(esc_key); i++) {
            if (query[i] == '%' || query[i] == '_' || query[i] == '\\')
                esc_key[ek++] = '\\';
            esc_key[ek++] = query[i];
        }
        esc_key[ek] = '\0';

        /* Use the current database */
        char use_q[128];
        snprintf(use_q, sizeof(use_q), "USE `%s`", db);
        mysql_query(STATE.conn, use_q);

        /* SHOW TABLES */
        if (mysql_query(STATE.conn, "SHOW TABLES") != 0) {
            return BclResult_Err(bcl_out, out_sz, 30, "SHOW TABLES failed");
        }
        MYSQL_RES *tres = mysql_store_result(STATE.conn);
        if (!tres) {
            return BclResult_Err(bcl_out, out_sz, 31, "no tables");
        }

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@KEYWORD]{%s}[@DB]{%s}[@TOTAL]{0}", query, db);

        int total = 0;
        MYSQL_ROW trow;
        while ((trow = mysql_fetch_row(tres)) != NULL && offset < (int)out_sz - 2048) {
            const char *tname = trow[0] ? trow[0] : "";
            /* Discover text columns for this table */
            char cq[512];
            snprintf(cq, sizeof(cq),
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s' AND "
                "(DATA_TYPE LIKE '%%char%%' OR DATA_TYPE LIKE '%%text%%') "
                "ORDER BY ORDINAL_POSITION LIMIT %d",
                db, tname, MSEARCH_MAX_COLS);
            if (mysql_query(STATE.conn, cq) != 0) continue;
            MYSQL_RES *cres = mysql_store_result(STATE.conn);
            if (!cres) continue;

            char cols[MSEARCH_MAX_COLS][128];
            int col_count = 0;
            MYSQL_ROW crow;
            while ((crow = mysql_fetch_row(cres)) != NULL && col_count < MSEARCH_MAX_COLS) {
                strncpy(cols[col_count], crow[0] ? crow[0] : "", 127);
                cols[col_count][127] = '\0';
                col_count++;
            }
            mysql_free_result(cres);
            if (col_count == 0) continue;

            /* Build WHERE clause from all text columns */
            char where[MSEARCH_BUF];
            size_t wpos = 0;
            for (int c = 0; c < col_count; c++) {
                char match_frag[512];
                build_match(cols[c], query, mode, match_frag, sizeof(match_frag));
                int written = snprintf(where + wpos, sizeof(where) - wpos,
                    "%s%s", (c ? " OR " : ""), match_frag);
                if (written < 0 || (size_t)written >= sizeof(where) - wpos) break;
                wpos += written;
            }

            /* Add status filter if provided */
            if (status_filter[0]) {
                int written = snprintf(where + wpos, sizeof(where) - wpos,
                    " AND `status` LIKE '%%%s%%'", status_filter);
                if (written > 0 && (size_t)written < sizeof(where) - wpos)
                    wpos += written;
            }

            /* Search */
            char sql[MSEARCH_BUF * 2];
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
                /* Build row with field names */
                offset += snprintf(bcl_out + offset, out_sz - offset,
                    "[@ROW]{[@IDX]{%d}", row_idx + 1);
                unsigned long *lens = mysql_fetch_lengths(res);
                MYSQL_FIELD *fields = mysql_fetch_fields(res);
                for (int f = 0; f < fcount && offset < (int)out_sz - 512; f++) {
                    const char *val = row[f] ? row[f] : "";
                    int vlen = lens[f];
                    if (vlen > 200) vlen = 200;
                    char clean[256];
                    int ci = 0;
                    for (int vi = 0; vi < vlen && ci < 250; vi++) {
                        if (val[vi] == '\n' || val[vi] == '\r' || val[vi] == '{' || val[vi] == '}')
                            clean[ci++] = ' ';
                        else if (val[vi] == '[' && val[vi+1] == '@')
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

        /* Patch total */
        char total_str[64];
        snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", total);
        char *pos = strstr(bcl_out, "[@TOTAL]{0}");
        if (pos) {
            int old_len = strlen("[@TOTAL]{0}");
            int new_len = strlen(total_str);
            memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
            memcpy(pos, total_str, new_len);
        }
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        STATE.queries_run++;
        return 1;
    }

    /* ===== SEARCH_ALL_DB — cross-database search (vb_shared + CODEBASE) ===== */
    if (strcmp(cmd, "search_all_db") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[MSEARCH_MAX_QUERY] = {0};
        char limit_str[32] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int limit = limit_str[0] ? atoi(limit_str) : MSEARCH_DEFAULT_LIMIT;
        if (limit <= 0 || limit > 500) limit = MSEARCH_DEFAULT_LIMIT;

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@KEYWORD]{%s}[@TOTAL]{0}", query);

        const char *dbs[] = {"vb_shared", "CODEBASE", NULL};
        int total = 0;
        for (int d = 0; dbs[d] && offset < (int)out_sz - 2048; d++) {
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@DB]{[@NAME]{%s}", dbs[d]);

            /* Connect to this database */
            MYSQL *dconn = mysql_init(NULL);
            if (!dconn) { offset += snprintf(bcl_out + offset, out_sz - offset, "}"); continue; }
            const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
            MYSQL *r = mysql_real_connect(dconn, STATE.host, STATE.user,
                STATE.pass[0] ? STATE.pass : NULL, dbs[d], STATE.port, sock, 0);
            if (!r) {
                r = mysql_real_connect(dconn, STATE.host, STATE.user,
                    STATE.pass[0] ? STATE.pass : NULL, dbs[d], STATE.port, NULL, 0);
            }
            if (!r) {
                mysql_close(dconn);
                offset += snprintf(bcl_out + offset, out_sz - offset, "}");
                continue;
            }

            /* Use existing search_one_table logic but with this connection */
            char esc_key[MSEARCH_MAX_QUERY];
            size_t ek = 0;
            for (size_t i = 0; query[i] && ek + 2 < sizeof(esc_key); i++) {
                if (query[i] == '%' || query[i] == '_' || query[i] == '\\')
                    esc_key[ek++] = '\\';
                esc_key[ek++] = query[i];
            }
            esc_key[ek] = '\0';

            /* SHOW TABLES */
            if (mysql_query(dconn, "SHOW TABLES") == 0) {
                MYSQL_RES *tres = mysql_store_result(dconn);
                if (tres) {
                    MYSQL_ROW trow;
                    while ((trow = mysql_fetch_row(tres)) != NULL && offset < (int)out_sz - 1024) {
                        const char *tname = trow[0] ? trow[0] : "";
                        /* Find text columns */
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

                        char sql[MSEARCH_BUF];
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

        /* Patch total */
        char total_str[64];
        snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", total);
        char *pos = strstr(bcl_out, "[@TOTAL]{0}");
        if (pos) {
            int old_len = strlen("[@TOTAL]{0}");
            int new_len = strlen(total_str);
            memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
            memcpy(pos, total_str, new_len);
        }
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        STATE.queries_run++;
        return 1;
    }

    /* ===== SEARCH_ALL_MYSQL — auto-discover ALL MySQL databases ===== */
    if (strcmp(cmd, "search_all_mysql") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[MSEARCH_MAX_QUERY] = {0};
        char limit_str[32] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int limit = limit_str[0] ? atoi(limit_str) : 20;
        if (limit <= 0 || limit > 200) limit = 20;

        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }

        /* SHOW DATABASES */
        if (mysql_query(STATE.conn, "SHOW DATABASES") != 0) {
            return BclResult_Err(bcl_out, out_sz, 30, "SHOW DATABASES failed");
        }
        MYSQL_RES *dres = mysql_store_result(STATE.conn);
        if (!dres) {
            return BclResult_Err(bcl_out, out_sz, 31, "no databases");
        }

        char db_list[MSEARCH_MAX_DB_S][64];
        int db_count = 0;
        MYSQL_ROW drow;
        while ((drow = mysql_fetch_row(dres)) != NULL && db_count < MSEARCH_MAX_DB_S) {
            const char *dbname = drow[0] ? drow[0] : "";
            /* Skip system databases */
            if (!strcasecmp(dbname, "information_schema") ||
                !strcasecmp(dbname, "mysql") ||
                !strcasecmp(dbname, "performance_schema") ||
                !strcasecmp(dbname, "sys")) continue;
            strncpy(db_list[db_count], dbname, 63);
            db_list[db_count][63] = '\0';
            db_count++;
        }
        mysql_free_result(dres);

        char esc_key[MSEARCH_MAX_QUERY];
        size_t ek = 0;
        for (size_t i = 0; query[i] && ek + 2 < sizeof(esc_key); i++) {
            if (query[i] == '%' || query[i] == '_' || query[i] == '\\')
                esc_key[ek++] = '\\';
            esc_key[ek++] = query[i];
        }
        esc_key[ek] = '\0';

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@KEYWORD]{%s}[@DB_COUNT]{%d}[@TOTAL]{0}", query, db_count);

        int total = 0;
        for (int d = 0; d < db_count && offset < (int)out_sz - 2048; d++) {
            MYSQL *dconn = mysql_init(NULL);
            if (!dconn) continue;
            const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
            MYSQL *r = mysql_real_connect(dconn, STATE.host, STATE.user,
                STATE.pass[0] ? STATE.pass : NULL, db_list[d], STATE.port, sock, 0);
            if (!r) {
                r = mysql_real_connect(dconn, STATE.host, STATE.user,
                    STATE.pass[0] ? STATE.pass : NULL, db_list[d], STATE.port, NULL, 0);
            }
            if (!r) { mysql_close(dconn); continue; }

            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@DB]{[@NAME]{%s}", db_list[d]);

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
                            db_list[d], tname);
                        if (mysql_query(dconn, cq) != 0) continue;
                        MYSQL_RES *cres = mysql_store_result(dconn);
                        if (!cres) continue;
                        MYSQL_ROW crow = mysql_fetch_row(cres);
                        if (!crow || !crow[0]) { mysql_free_result(cres); continue; }
                        char first_col[128];
                        strncpy(first_col, crow[0], 127);
                        first_col[127] = '\0';
                        mysql_free_result(cres);

                        char sql[MSEARCH_BUF];
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
                                db_list[d], tname, row[0] ? row[0] : "");
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

        /* Patch total */
        char total_str[64];
        snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", total);
        char *pos = strstr(bcl_out, "[@TOTAL]{0}");
        if (pos) {
            int old_len = strlen("[@TOTAL]{0}");
            int new_len = strlen(total_str);
            memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
            memcpy(pos, total_str, new_len);
        }
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        STATE.queries_run++;
        return 1;
    }

    /* ===== HYBRID — MySQL keyword + Qdrant vector combined ===== */
    if (strcmp(cmd, "hybrid") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[MSEARCH_MAX_QUERY] = {0};
        char limit_str[32] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int limit = limit_str[0] ? atoi(limit_str) : MSEARCH_DEFAULT_LIMIT;
        if (limit <= 0 || limit > 500) limit = MSEARCH_DEFAULT_LIMIT;

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@KEYWORD]{%s}[@PHASE1]{", query);

        /* Phase 1: MySQL keyword search using existing targets */
        if (ensure_connected()) {
            for (int i = 0; i < TARGET_COUNT; i++) {
                search_one_table(&TARGETS[i], query, limit, bcl_out, out_sz, &offset);
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}[@PHASE2]{");

        /* Phase 2: Qdrant vector search via msearch_qdrant unit */
        char qdr_in[512];
        snprintf(qdr_in, sizeof(qdr_in),
            "[@CMD]{semantic}[@QUERY]{%s}[@TOP]{10}", query);
        char qdr_out[TOOL_MAX_RESULT];
        MsearchQdrant_Run("semantic", qdr_in, qdr_out, sizeof(qdr_out));
        /* Append qdrant output (strip [@OK] wrapper) */
        const char *qstart = strstr(qdr_out, "[@OK]{");
        if (qstart) {
            qstart += 6; /* skip [@OK]{ */
            int qlen = strlen(qstart);
            if (qlen > 1 && qstart[qlen-1] == '}') qlen--; /* strip trailing } */
            if (offset + qlen < (int)out_sz - 256) {
                memcpy(bcl_out + offset, qstart, qlen);
                offset += qlen;
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        STATE.queries_run++;
        return 1;
    }

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@CONNECTED]{%d}[@HOST]{%s}[@USER]{%s}[@PORT]{%d}"
            "[@QUERIES]{%d}[@MATCHES]{%d}[@TABLES]{%d}[@ERROR]{%s}",
            STATE.initialized, STATE.connected,
            STATE.host, STATE.user, STATE.port,
            STATE.queries_run, STATE.total_matches, STATE.tables_searched,
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[MSEARCH_HOST_LEN] = {0};
        char user[MSEARCH_USER_LEN] = {0};
        char pass[MSEARCH_PASS_LEN] = {0};
        char socket[MSEARCH_SOCKET_LEN] = {0};
        char port_str[16] = {0};
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PASS", pass, sizeof(pass));
        BclParser_Extract(&parse, "SOCKET", socket, sizeof(socket));
        BclParser_Extract(&parse, "PORT", port_str, sizeof(port_str));
        BclParser_Free(&parse);

        if (host[0]) strncpy(STATE.host, host, sizeof(STATE.host) - 1);
        if (user[0]) strncpy(STATE.user, user, sizeof(STATE.user) - 1);
        if (pass[0]) strncpy(STATE.pass, pass, sizeof(STATE.pass) - 1);
        if (socket[0]) strncpy(STATE.socket, socket, sizeof(STATE.socket) - 1);
        if (port_str[0]) STATE.port = atoi(port_str);

        /* If config changes, force reconnect */
        if (STATE.connected) {
            mysql_close(STATE.conn);
            STATE.conn = NULL;
            STATE.connected = 0;
        }

        char body[512];
        snprintf(body, sizeof(body),
            "[@HOST]{%s}[@USER]{%s}[@PORT]{%d}[@SOCKET]{%s}",
            STATE.host, STATE.user, STATE.port, STATE.socket);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int Msearch_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    return 1;
}

const char * Msearch_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Msearch: initialized=%d connected=%d queries=%d matches=%d",
        STATE.initialized, STATE.connected,
        STATE.queries_run, STATE.total_matches);
    return buf;
}