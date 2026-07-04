//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_error_fix.c" date="2026-07-04" author="Devin" session_id="bcl-toolstack-units" context="BCL unit - Error fix trainer. Learns error/fix pairs from MySQL vb_shared.learned_rules and know_problems/know_fixes. Commands: lookup, train, batch_train, stats, validate, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch static STATE no-self._ no-print"}
//[@FILEID]{id="bcl_error_fix.c" domain="cascade_tools" authority="ErrorFix"}
//[@SUMMARY]{summary="Error fix trainer BCL unit. Queries vb_shared.learned_rules for fixes matching an error text, trains new error/fix pairs, batch-trains from JSON, reports stats, and validates fixes. Owns MySQL connection config in STATE. Always links mysqlclient."}
//[@CLASS]{class="ErrorFix" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Lookup" type="internal"}
//[@METHOD]{method="Train" type="internal"}
//[@METHOD]{method="BatchTrain" type="internal"}
//[@METHOD]{method="Stats" type="internal"}
//[@METHOD]{method="Validate" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<MySQL-backed error fix trainer. No printf/fprintf — errors go to STATE.last_error.>][@todos<>]}

/* bcl_error_fix.c — error fix trainer BCL unit
 * Schema (vb_shared): learned_rules(id, pattern, trigger_condition, fix_action, language,
 *   category, severity, success_count, failure_count, confidence, source, created_at, last_used)
 *   know_problems(id, problem, description, ...) -> know_solutions(id, problem_id, solution, ...)
 *   -> know_fixes(id, solution_id, fix_text, file_path, line_range, applied_at) */

#include "bcl_toolstack.h"
#include <mysql.h>

#define ERRORFIX_MAX_PATH    4096
#define ERRORFIX_MAX_SQL     4096
#define ERRORFIX_MAX_FIX     2048
#define ERRORFIX_MAX_LANG      32
#define ERRORFIX_MAX_RESULTS  100

static struct {
    int initialized, lookups_run, fixes_trained, fixes_found;
    char last_error[512], last_fix[ERRORFIX_MAX_FIX];
    double success_rate;
    char host[128], user[64], pass[128], socket[256], db_name[64];
    int port, max_results;
    double min_confidence;
} STATE;

static void escape_str(MYSQL *conn, const char *in, char *out, size_t out_sz) {
    if (!in || !in[0]) { out[0] = '\0'; return; }
    mysql_real_escape_string(conn, out, in, (unsigned long)strlen(in));
    (void)out_sz;
}

static MYSQL * errorfix_connect(void) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) { snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed"); return NULL; }
    if (!mysql_real_connect(conn, STATE.host, STATE.user, STATE.pass, STATE.db_name,
                            STATE.port, STATE.socket[0] ? STATE.socket : NULL, 0)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql connect: %s", mysql_error(conn));
        mysql_close(conn);
        return NULL;
    }
    return conn;
}

static int errorfix_count_query(MYSQL *conn, const char *sql) {
    if (mysql_query(conn, sql) != 0) return 0;
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) return 0;
    MYSQL_ROW row = mysql_fetch_row(res);
    int count = row ? atoi(row[0]) : 0;
    mysql_free_result(res);
    return count;
}

static int errorfix_lookup(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char error_text[BCL_MAX_CONTENT] = {0};
    char language[ERRORFIX_MAX_LANG] = {0};
    BclParser_Extract(&parse, "ERROR",    error_text, sizeof(error_text));
    BclParser_Extract(&parse, "LANGUAGE", language,   sizeof(language));
    BclParser_Free(&parse);
    if (!error_text[0]) return BclResult_Err(bcl_out, out_sz, 20, "no ERROR in packet");

    MYSQL *conn = errorfix_connect();
    if (!conn) return BclResult_Err(bcl_out, out_sz, 21,
        STATE.last_error[0] ? STATE.last_error : "mysql connect failed");

    char eerr[BCL_MAX_CONTENT * 2 + 1];
    escape_str(conn, error_text, eerr, sizeof(eerr));
    char sql[ERRORFIX_MAX_SQL];
    snprintf(sql, sizeof(sql),
        "SELECT pattern, fix_action, confidence, language, success_count, failure_count "
        "FROM learned_rules WHERE (pattern LIKE '%%%s%%' OR trigger_condition LIKE '%%%s%%')",
        eerr, eerr);
    if (language[0]) {
        char elang[ERRORFIX_MAX_LANG * 2 + 1];
        escape_str(conn, language, elang, sizeof(elang));
        char lang_clause[ERRORFIX_MAX_LANG * 2 + 32];
        snprintf(lang_clause, sizeof(lang_clause), " AND language = '%s'", elang);
        strncat(sql, lang_clause, sizeof(sql) - strlen(sql) - 1);
    }
    char order_clause[128];
    snprintf(order_clause, sizeof(order_clause), " ORDER BY confidence DESC LIMIT %d", STATE.max_results);
    strncat(sql, order_clause, sizeof(sql) - strlen(sql) - 1);

    if (mysql_query(conn, sql)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "learned_rules query: %s", mysql_error(conn));
        mysql_close(conn);
        return BclResult_Err(bcl_out, out_sz, 22, STATE.last_error);
    }
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "no result set: %s", mysql_error(conn));
        mysql_close(conn);
        return BclResult_Err(bcl_out, out_sz, 23, STATE.last_error);
    }

    char body[TOOL_MAX_BCL];
    body[0] = '\0';
    int found = 0;
    double best_conf = 0.0;
    char best_fix[ERRORFIX_MAX_FIX] = {0};
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        const char *pattern = row[0] ? row[0] : "", *fix = row[1] ? row[1] : "";
        const char *conf_str = row[2] ? row[2] : "0", *lang = row[3] ? row[3] : "";
        const char *succ_str = row[4] ? row[4] : "0", *fail_str = row[5] ? row[5] : "0";
        double conf = atof(conf_str);
        char entry[1024];
        snprintf(entry, sizeof(entry),
            "[@RULE]{[@PATTERN]{%.200s}[@FIX]{%.400s}[@CONFIDENCE]{%s}[@LANGUAGE]{%s}[@SUCCESS]{%s}[@FAILURE]{%s}}",
            pattern, fix, conf_str, lang, succ_str, fail_str);
        strncat(body, entry, sizeof(body) - strlen(body) - 1);
        found++;
        if (conf > best_conf) {
            best_conf = conf;
            strncpy(best_fix, fix, sizeof(best_fix) - 1);
            best_fix[sizeof(best_fix) - 1] = '\0';
        }
    }
    mysql_free_result(res);

    /* Also query know_problems JOIN know_solutions JOIN know_fixes */
    snprintf(sql, sizeof(sql),
        "SELECT kp.problem, kp.description, ks.solution, kf.fix_text "
        "FROM know_problems kp "
        "LEFT JOIN know_solutions ks ON ks.problem_id = kp.id "
        "LEFT JOIN know_fixes kf ON kf.solution_id = ks.id "
        "WHERE kp.problem LIKE '%%%s%%' OR kp.description LIKE '%%%s%%' LIMIT %d",
        eerr, eerr, STATE.max_results);
    if (mysql_query(conn, sql) == 0) {
        MYSQL_RES *res2 = mysql_store_result(conn);
        if (res2) {
            MYSQL_ROW row2;
            while ((row2 = mysql_fetch_row(res2))) {
                const char *prob = row2[0] ? row2[0] : "", *desc = row2[1] ? row2[1] : "";
                const char *sol = row2[2] ? row2[2] : "", *fixt = row2[3] ? row2[3] : "";
                char entry[1024];
                snprintf(entry, sizeof(entry),
                    "[@KNOW]{[@PROBLEM]{%.200s}[@DESCRIPTION]{%.200s}[@SOLUTION]{%.200s}[@FIX]{%.300s}}",
                    prob, desc, sol, fixt);
                strncat(body, entry, sizeof(body) - strlen(body) - 1);
                found++;
                if (!best_fix[0] && fixt[0]) {
                    strncpy(best_fix, fixt, sizeof(best_fix) - 1);
                    best_fix[sizeof(best_fix) - 1] = '\0';
                }
            }
            mysql_free_result(res2);
        }
    }
    mysql_close(conn);

    STATE.lookups_run++;
    STATE.fixes_found += found;
    if (best_fix[0]) {
        strncpy(STATE.last_fix, best_fix, sizeof(STATE.last_fix) - 1);
        STATE.last_fix[sizeof(STATE.last_fix) - 1] = '\0';
    }
    char full[TOOL_MAX_BCL];
    snprintf(full, sizeof(full), "[@FOUND]{%d}[@BEST_CONFIDENCE]{%.3f}[@LAST_FIX]{%.200s}%s",
        found, best_conf, best_fix, body);
    return BclResult_Ok(bcl_out, out_sz, full);
}

/* ===== TRAIN ===== */

static int errorfix_train(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char pattern[BCL_MAX_CONTENT] = {0}, fix[BCL_MAX_CONTENT] = {0};
    char language[ERRORFIX_MAX_LANG] = {0}, conf_str[32] = {0};
    char source[64] = {0}, trigger[BCL_MAX_CONTENT] = {0};
    BclParser_Extract(&parse, "PATTERN",    pattern,  sizeof(pattern));
    BclParser_Extract(&parse, "FIX",        fix,      sizeof(fix));
    BclParser_Extract(&parse, "LANGUAGE",   language, sizeof(language));
    BclParser_Extract(&parse, "CONFIDENCE", conf_str, sizeof(conf_str));
    BclParser_Extract(&parse, "SOURCE",     source,   sizeof(source));
    BclParser_Extract(&parse, "TRIGGER",    trigger,  sizeof(trigger));
    BclParser_Free(&parse);
    if (!pattern[0] || !fix[0]) return BclResult_Err(bcl_out, out_sz, 30, "no PATTERN or FIX in packet");

    double confidence = conf_str[0] ? atof(conf_str) : 0.5;
    if (!language[0]) strncpy(language, "unknown", sizeof(language) - 1);
    if (!source[0])   strncpy(source,   "manual",  sizeof(source) - 1);

    MYSQL *conn = errorfix_connect();
    if (!conn) return BclResult_Err(bcl_out, out_sz, 31,
        STATE.last_error[0] ? STATE.last_error : "mysql connect failed");

    char epat[BCL_MAX_CONTENT * 2 + 1], efix[BCL_MAX_CONTENT * 2 + 1];
    char etrig[BCL_MAX_CONTENT * 2 + 1], elang[ERRORFIX_MAX_LANG * 2 + 1], esrc[256];
    escape_str(conn, pattern,  epat,  sizeof(epat));
    escape_str(conn, fix,      efix,  sizeof(efix));
    escape_str(conn, trigger,  etrig, sizeof(etrig));
    escape_str(conn, language, elang, sizeof(elang));
    escape_str(conn, source,   esrc,  sizeof(esrc));

    char sql[ERRORFIX_MAX_SQL];
    snprintf(sql, sizeof(sql),
        "INSERT INTO learned_rules (pattern, trigger_condition, fix_action, language, "
        "confidence, source) VALUES ('%s', '%s', '%s', '%s', %.4f, '%s')",
        epat, etrig, efix, elang, confidence, esrc);
    if (mysql_query(conn, sql)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "learned_rules insert: %s", mysql_error(conn));
        mysql_close(conn);
        return BclResult_Err(bcl_out, out_sz, 32, STATE.last_error);
    }
    my_ulonglong new_id = mysql_insert_id(conn);
    mysql_close(conn);

    STATE.fixes_trained++;
    strncpy(STATE.last_fix, fix, sizeof(STATE.last_fix) - 1);
    STATE.last_fix[sizeof(STATE.last_fix) - 1] = '\0';
    char body[512];
    snprintf(body, sizeof(body), "[@ID]{%llu}[@PATTERN]{%.100s}[@LANGUAGE]{%s}[@CONFIDENCE]{%.3f}",
        (unsigned long long)new_id, pattern, language, confidence);
    return BclResult_Ok(bcl_out, out_sz, body);
}

/* ===== BATCH TRAIN ===== */
/* Expected JSON: [{"error":"...","fix":"...","language":"python","confidence":0.8}, ...] */

static void json_extract(char *obj_start, char *obj_end, const char *key,
                         char *out, size_t out_sz, int is_num) {
    out[0] = '\0';
    char *k = strstr(obj_start, key);
    if (!k || k >= obj_end) return;
    char *val = strchr(k + strlen(key), ':');
    if (!val) return;
    val++;
    while (*val == ' ') val++;
    if (!is_num) {
        val = strchr(val, '"');
        if (!val) return;
        val++;
        char *end = strchr(val, '"');
        if (!end) return;
        size_t len = end - val;
        if (len >= out_sz) len = out_sz - 1;
        memcpy(out, val, len);
        out[len] = '\0';
    } else {
        char *end = val;
        while (*end && (*end == '.' || (*end >= '0' && *end <= '9'))) end++;
        size_t len = end - val;
        if (len >= out_sz) len = out_sz - 1;
        memcpy(out, val, len);
        out[len] = '\0';
    }
}

static int errorfix_batch_train(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char path[ERRORFIX_MAX_PATH] = {0};
    BclParser_Extract(&parse, "PATH", path, sizeof(path));
    BclParser_Free(&parse);
    if (!path[0]) return BclResult_Err(bcl_out, out_sz, 40, "no PATH in packet");

    FILE *fp = fopen(path, "r");
    if (!fp) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "cannot open file: %s", path);
        return BclResult_Err(bcl_out, out_sz, 41, STATE.last_error);
    }
    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (fsize <= 0 || fsize > 1024 * 1024) {
        fclose(fp);
        snprintf(STATE.last_error, sizeof(STATE.last_error), "file too large or empty: %ld bytes", fsize);
        return BclResult_Err(bcl_out, out_sz, 42, STATE.last_error);
    }
    char *json = (char *)malloc((size_t)fsize + 1);
    if (!json) { fclose(fp); return BclResult_Err(bcl_out, out_sz, 43, "oom"); }
    size_t nread = fread(json, 1, (size_t)fsize, fp);
    json[nread] = '\0';
    fclose(fp);

    MYSQL *conn = errorfix_connect();
    if (!conn) { free(json); return BclResult_Err(bcl_out, out_sz, 44,
        STATE.last_error[0] ? STATE.last_error : "mysql connect failed"); }

    int inserted = 0, errors = 0;
    char *cursor = json;
    while (cursor) {
        char *obj_start = strchr(cursor, '{');
        if (!obj_start) break;
        char *obj_end = strchr(obj_start, '}');
        if (!obj_end) break;
        char error_text[1024] = {0}, fix_text[1024] = {0};
        char language[32] = {0}, conf_str[32] = {0};
        json_extract(obj_start, obj_end, "\"error\"",      error_text, sizeof(error_text), 0);
        json_extract(obj_start, obj_end, "\"fix\"",        fix_text,   sizeof(fix_text),   0);
        json_extract(obj_start, obj_end, "\"language\"",   language,   sizeof(language),   0);
        json_extract(obj_start, obj_end, "\"confidence\"", conf_str,   sizeof(conf_str),   1);
        if (error_text[0] && fix_text[0]) {
            double confidence = conf_str[0] ? atof(conf_str) : 0.5;
            if (!language[0]) strncpy(language, "unknown", sizeof(language) - 1);
            char epat[2048], efix[2048], elang[64];
            escape_str(conn, error_text, epat,  sizeof(epat));
            escape_str(conn, fix_text,   efix,  sizeof(efix));
            escape_str(conn, language,   elang, sizeof(elang));
            char sql[ERRORFIX_MAX_SQL];
            snprintf(sql, sizeof(sql),
                "INSERT INTO learned_rules (pattern, fix_action, language, confidence, source) "
                "VALUES ('%s', '%s', '%s', %.4f, 'batch_train')",
                epat, efix, elang, confidence);
            if (mysql_query(conn, sql) == 0) { inserted++; STATE.fixes_trained++; }
            else errors++;
        }
        cursor = obj_end + 1;
    }
    mysql_close(conn);
    free(json);
    char body[256];
    snprintf(body, sizeof(body), "[@PATH]{%s}[@INSERTED]{%d}[@ERRORS]{%d}", path, inserted, errors);
    return BclResult_Ok(bcl_out, out_sz, body);
}

/* ===== STATS ===== */

static int errorfix_stats(char *bcl_out, size_t out_sz) {
    MYSQL *conn = errorfix_connect();
    if (!conn) return BclResult_Err(bcl_out, out_sz, 50,
        STATE.last_error[0] ? STATE.last_error : "mysql connect failed");

    int total = errorfix_count_query(conn, "SELECT COUNT(*) FROM learned_rules");
    char sql[256];
    snprintf(sql, sizeof(sql), "SELECT COUNT(*) FROM learned_rules WHERE confidence >= 0.8");
    int high = errorfix_count_query(conn, sql);
    snprintf(sql, sizeof(sql), "SELECT COUNT(*) FROM learned_rules WHERE confidence >= 0.5 AND confidence < 0.8");
    int mid = errorfix_count_query(conn, sql);
    snprintf(sql, sizeof(sql), "SELECT COUNT(*) FROM learned_rules WHERE confidence < 0.5");
    int low = errorfix_count_query(conn, sql);

    long total_success = 0, total_fail = 0;
    if (mysql_query(conn,
        "SELECT COALESCE(SUM(success_count),0), COALESCE(SUM(failure_count),0) FROM learned_rules") == 0) {
        MYSQL_RES *res = mysql_store_result(conn);
        if (res) {
            MYSQL_ROW row = mysql_fetch_row(res);
            if (row) { total_success = atol(row[0]); total_fail = atol(row[1]); }
            mysql_free_result(res);
        }
    }
    double success_rate = 0.0;
    if (total_success + total_fail > 0)
        success_rate = (double)total_success / (double)(total_success + total_fail);

    char lang_body[2048];
    lang_body[0] = '\0';
    if (mysql_query(conn,
        "SELECT language, COUNT(*) FROM learned_rules GROUP BY language ORDER BY COUNT(*) DESC") == 0) {
        MYSQL_RES *res = mysql_store_result(conn);
        if (res) {
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res))) {
                const char *lang = row[0] ? row[0] : "unknown";
                const char *cnt  = row[1] ? row[1] : "0";
                char entry[128];
                snprintf(entry, sizeof(entry), "[@LANG]{[@NAME]{%s}[@COUNT]{%s}}", lang, cnt);
                strncat(lang_body, entry, sizeof(lang_body) - strlen(lang_body) - 1);
            }
            mysql_free_result(res);
        }
    }
    mysql_close(conn);
    STATE.success_rate = success_rate;
    char body[TOOL_MAX_BCL];
    snprintf(body, sizeof(body),
        "[@TOTAL]{%d}[@HIGH_CONF]{%d}[@MID_CONF]{%d}[@LOW_CONF]{%d}"
        "[@SUCCESS_COUNT]{%ld}[@FAILURE_COUNT]{%ld}[@SUCCESS_RATE]{%.4f}%s",
        total, high, mid, low, total_success, total_fail, success_rate, lang_body);
    return BclResult_Ok(bcl_out, out_sz, body);
}

/* ===== VALIDATE ===== */

static int errorfix_validate(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char pattern[BCL_MAX_CONTENT] = {0}, fix[BCL_MAX_CONTENT] = {0};
    BclParser_Extract(&parse, "PATTERN", pattern, sizeof(pattern));
    BclParser_Extract(&parse, "FIX",     fix,     sizeof(fix));
    BclParser_Free(&parse);
    if (!pattern[0] || !fix[0]) return BclResult_Err(bcl_out, out_sz, 60, "no PATTERN or FIX in packet");

    MYSQL *conn = errorfix_connect();
    if (!conn) return BclResult_Err(bcl_out, out_sz, 61,
        STATE.last_error[0] ? STATE.last_error : "mysql connect failed");

    char epat[BCL_MAX_CONTENT * 2 + 1], efix[BCL_MAX_CONTENT * 2 + 1];
    escape_str(conn, pattern, epat, sizeof(epat));
    escape_str(conn, fix,     efix, sizeof(efix));
    char sql[ERRORFIX_MAX_SQL];
    snprintf(sql, sizeof(sql),
        "SELECT id, confidence, success_count, failure_count FROM learned_rules "
        "WHERE pattern = '%s' AND fix_action = '%s' LIMIT 1", epat, efix);
    if (mysql_query(conn, sql)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "validate query: %s", mysql_error(conn));
        mysql_close(conn);
        return BclResult_Err(bcl_out, out_sz, 62, STATE.last_error);
    }
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) { mysql_close(conn); return BclResult_Err(bcl_out, out_sz, 63, "no result set"); }

    int exists = 0, rule_id = 0, success_count = 0, failure_count = 0;
    double confidence = 0.0;
    MYSQL_ROW row = mysql_fetch_row(res);
    if (row) {
        exists = 1;
        rule_id = row[0] ? atoi(row[0]) : 0;
        confidence = row[1] ? atof(row[1]) : 0.0;
        success_count = row[2] ? atoi(row[2]) : 0;
        failure_count = row[3] ? atoi(row[3]) : 0;
    }
    mysql_free_result(res);
    mysql_close(conn);

    int meets_threshold = (confidence >= STATE.min_confidence) ? 1 : 0;
    const char *verdict = "not_found";
    if (exists && meets_threshold) verdict = "valid";
    else if (exists && !meets_threshold) verdict = "low_confidence";

    char body[512];
    snprintf(body, sizeof(body),
        "[@EXISTS]{%d}[@RULE_ID]{%d}[@CONFIDENCE]{%.4f}[@SUCCESS]{%d}[@FAILURE]{%d}"
        "[@MEETS_THRESHOLD]{%d}[@VERDICT]{%s}",
        exists, rule_id, confidence, success_count, failure_count, meets_threshold, verdict);
    return BclResult_Ok(bcl_out, out_sz, body);
}

/* ===== UNIT INTERFACE ===== */

int ErrorFix_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host,    "localhost",      sizeof(STATE.host) - 1);
    strncpy(STATE.user,    "root",           sizeof(STATE.user) - 1);
    STATE.pass[0] = '\0';
    STATE.port = 3306;
    strncpy(STATE.socket,  "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    strncpy(STATE.db_name, "vb_shared",      sizeof(STATE.db_name) - 1);
    STATE.min_confidence = 0.5;
    STATE.max_results = ERRORFIX_MAX_RESULTS;
    STATE.success_rate = 0.0;
    STATE.initialized = 1;
    return 1;
}

int ErrorFix_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) ErrorFix_Init();

    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@LOOKUPS]{%d}[@TRAINED]{%d}[@FOUND]{%d}"
            "[@SUCCESS_RATE]{%.4f}[@LAST_ERROR]{%.200s}[@LAST_FIX]{%.200s}",
            STATE.initialized ? 1 : 0, STATE.lookups_run, STATE.fixes_trained,
            STATE.fixes_found, STATE.success_rate,
            STATE.last_error[0] ? STATE.last_error : "",
            STATE.last_fix[0] ? STATE.last_fix : "");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char db_name[64] = {0}, min_conf[32] = {0}, max_results[16] = {0};
        char host[128] = {0}, user[64] = {0}, port_str[16] = {0};
        BclParser_Extract(&parse, "DB",             db_name,     sizeof(db_name));
        BclParser_Extract(&parse, "MIN_CONFIDENCE", min_conf,    sizeof(min_conf));
        BclParser_Extract(&parse, "MAX_RESULTS",    max_results, sizeof(max_results));
        BclParser_Extract(&parse, "HOST",           host,        sizeof(host));
        BclParser_Extract(&parse, "USER",           user,        sizeof(user));
        BclParser_Extract(&parse, "PORT",           port_str,    sizeof(port_str));
        BclParser_Free(&parse);
        if (db_name[0])     strncpy(STATE.db_name, db_name, sizeof(STATE.db_name) - 1);
        if (min_conf[0])    STATE.min_confidence = atof(min_conf);
        if (max_results[0]) STATE.max_results = atoi(max_results);
        if (host[0])        strncpy(STATE.host, host, sizeof(STATE.host) - 1);
        if (user[0])        strncpy(STATE.user, user, sizeof(STATE.user) - 1);
        if (port_str[0])    STATE.port = atoi(port_str);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    if (strcmp(cmd, "lookup") == 0)      return errorfix_lookup(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "train") == 0)       return errorfix_train(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "batch_train") == 0) return errorfix_batch_train(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "stats") == 0)       return errorfix_stats(bcl_out, out_sz);
    if (strcmp(cmd, "validate") == 0)    return errorfix_validate(bcl_in, bcl_out, out_sz);

    return BclResult_Err(bcl_out, out_sz, 90, "unknown command");
}

int ErrorFix_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * ErrorFix_State(void) {
    static char buf[512];
    snprintf(buf, sizeof(buf),
        "ErrorFix: initialized=%d lookups=%d trained=%d found=%d success_rate=%.4f db=%s host=%s",
        STATE.initialized, STATE.lookups_run, STATE.fixes_trained,
        STATE.fixes_found, STATE.success_rate, STATE.db_name, STATE.host);
    return buf;
}
