//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_cognitive_core.c" date="2026-07-04" author="Devin" session_id="bcl-cognitive-core" context="BCL unit - cognitive reasoning engine. Searches MySQL knowledge base (know_answers JOIN know_questions, learned_rules) and synthesizes answers. Learns new facts."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_cognitive_core.c" domain="cascade_tools" authority="CognitiveCore"}
//[@SUMMARY]{summary="Cognitive core engine. Commands: reason, learn, query_rules, query_answers, summary, read_state, set_config. Connects localhost/root/vb_shared."}
//[@CLASS]{class="CognitiveCore" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}[@METHOD]{method="Run" type="dispatch"}[@METHOD]{method="Close" type="command"}[@METHOD]{method="State" type="query"}
//[@METHOD]{method="EnsureConnected" type="internal"}[@METHOD]{method="EscapeLike" type="internal"}[@METHOD]{method="TruncateText" type="internal"}
//[@METHOD]{method="DoReason" type="internal"}[@METHOD]{method="DoLearn" type="internal"}[@METHOD]{method="DoQuery" type="internal"}[@METHOD]{method="DoSummary" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<reason: search know_answers+learned_rules, synthesize. learn: store rule. query_rules/query_answers: lookup. summary: counts.>][@todos<>]}

/* BCL IN:  reason[@QUESTION]{...} | learn[@PATTERN]{...}[@FIX]{...}[@CONFIDENCE]{0.8} | query_rules[@PATTERN]{...}[@LIMIT]{10}
 *          query_answers[@QUESTION]{...}[@LIMIT]{10} | summary | read_state | set_config[@DB_NAME]{...}[@MAX_RESULTS]{50}
 * BCL OUT: [@OK]{[@ANSWER]{...}[@RULE]{...}[@CONFIDENCE]{0.85}[@COUNT]{N}} | [@ERR]{[@CODE]{N}[@DESC]{...}} */

#include "bcl_toolstack.h"
#include <mysql.h>

#define COG_MAX_QUERY      4096
#define COG_MAX_SNIPPET    512
#define COG_MAX_FIELD      1024
#define COG_HOST_LEN       256
#define COG_USER_LEN       64
#define COG_PASS_LEN       128
#define COG_SOCKET_LEN     256
#define COG_MAX_DB         64
#define COG_DEFAULT_LIMIT  10
#define COG_MAX_LIMIT      200

/* State struct */
static struct {
    int initialized;
    int connected;
    MYSQL *conn;
    char host[COG_HOST_LEN];
    char user[COG_USER_LEN];
    char pass[COG_PASS_LEN];
    char socket[COG_SOCKET_LEN];
    int port;
    char db_name[COG_MAX_DB];
    int max_results;
    double min_confidence;
    int queries_run;
    int facts_learned;
    int rules_found;
    int answers_found;
    char last_question[COG_MAX_FIELD];
    double last_confidence;
    char last_error[256];
} STATE;

/* Helper: parse bcl_in, extract one tag, free */
static void cog_extract(const char *bcl_in, const char *tag, char *out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    BclParser_Extract(&parse, tag, out, out_sz);
    BclParser_Free(&parse);
}

static int cog_ensure_connected(void) {
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
        STATE.db_name, STATE.port, sock, 0);
    if (!result) {
        result = mysql_real_connect(STATE.conn,
            STATE.host, STATE.user,
            STATE.pass[0] ? STATE.pass : NULL,
            STATE.db_name, STATE.port, NULL, 0);
    }
    if (!result) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "connect: %s", mysql_error(STATE.conn));
        return 0;
    }
    STATE.connected = 1;
    return 1;
}
static void cog_escape_like(const char *in, char *out, size_t out_sz) {
    size_t pos = 0;
    for (size_t i = 0; in[i] && pos < out_sz - 8; i++) {
        if (in[i] == '%' || in[i] == '_' || in[i] == '\\' ||
            in[i] == '\'' || in[i] == '"') {
            out[pos++] = '\\';
        }
        out[pos++] = in[i];
    }
    out[pos] = '\0';
}
static void cog_escape_sql(const char *in, char *out, size_t out_sz) {
    if (STATE.conn && STATE.connected) {
        mysql_real_escape_string(STATE.conn, out, in, (unsigned long)strlen(in));
    } else {
        cog_escape_like(in, out, out_sz);
    }
}
static void cog_truncate_text(const char *in, char *out, int out_sz) {
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
        if (out[i] == '[' && i + 1 < out_sz && out[i + 1] == '@') out[i] = ' ';
    }
}
static void cog_patch_total(char *out, int total) {
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
/* DO REASON — synthesize answer from knowledge base */
static int cog_do_reason(const char *question, char *bcl_out, size_t out_sz) {
    if (!cog_ensure_connected()) {
        return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
    }
    char esc_q[COG_MAX_QUERY];
    cog_escape_like(question, esc_q, sizeof(esc_q));
    int offset = 0;
    offset += snprintf(bcl_out + offset, out_sz - offset,
        "[@OK]{[@QUESTION]{%.300s}[@ANSWERS]{", question);
    /* Query 1: know_answers JOIN know_questions for matching answers */
    char query1[COG_MAX_QUERY];
    snprintf(query1, sizeof(query1),
        "SELECT qa.id, qq.question, LEFT(qa.answer, 400), qa.confidence "
        "FROM vb_shared.know_answers qa "
        "JOIN vb_shared.know_questions qq ON qa.question_id = qq.id "
        "WHERE qq.question LIKE '%%%s%%' "
        "ORDER BY qa.confidence DESC LIMIT %d",
        esc_q, STATE.max_results);
    int answer_count = 0;
    double best_answer_conf = 0.0;
    if (mysql_query(STATE.conn, query1) == 0) {
        MYSQL_RES *res = mysql_store_result(STATE.conn);
        if (res) {
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                const char *aid = row[0] ? row[0] : "0";
                char q_snip[COG_MAX_SNIPPET], a_snip[COG_MAX_SNIPPET];
                cog_truncate_text(row[1], q_snip, sizeof(q_snip));
                cog_truncate_text(row[2], a_snip, sizeof(a_snip));
                double conf = row[3] ? atof(row[3]) : 0.0;
                offset += snprintf(bcl_out + offset, out_sz - offset,
                    "[@ANSWER]{[@ID]{%s}[@Q]{%.200s}[@A]{%.400s}[@CONF]{%.2f}}",
                    aid, q_snip, a_snip, conf);
                answer_count++;
                STATE.answers_found++;
                if (conf > best_answer_conf) best_answer_conf = conf;
            }
            mysql_free_result(res);
        }
    }
    offset += snprintf(bcl_out + offset, out_sz - offset, "}[@RULES]{");
    /* Query 2: learned_rules for matching patterns */
    char query2[COG_MAX_QUERY];
    snprintf(query2, sizeof(query2),
        "SELECT id, LEFT(pattern, 300), LEFT(fix_action, 400), confidence, "
        "success_count, failure_count "
        "FROM vb_shared.learned_rules "
        "WHERE pattern LIKE '%%%s%%' "
        "ORDER BY confidence DESC LIMIT %d",
        esc_q, STATE.max_results);
    int rule_count = 0;
    double best_rule_conf = 0.0;
    if (mysql_query(STATE.conn, query2) == 0) {
        MYSQL_RES *res = mysql_store_result(STATE.conn);
        if (res) {
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                const char *rid = row[0] ? row[0] : "0";
                char p_snip[COG_MAX_SNIPPET], f_snip[COG_MAX_SNIPPET];
                cog_truncate_text(row[1], p_snip, sizeof(p_snip));
                cog_truncate_text(row[2], f_snip, sizeof(f_snip));
                double conf = row[3] ? atof(row[3]) : 0.0;
                int sc = row[4] ? atoi(row[4]) : 0;
                int fc = row[5] ? atoi(row[5]) : 0;
                offset += snprintf(bcl_out + offset, out_sz - offset,
                    "[@RULE]{[@ID]{%s}[@PATTERN]{%.200s}[@FIX]{%.400s}"
                    "[@CONF]{%.2f}[@SUCC]{%d}[@FAIL]{%d}}",
                    rid, p_snip, f_snip, conf, sc, fc);
                rule_count++;
                STATE.rules_found++;
                if (conf > best_rule_conf) best_rule_conf = conf;
            }
            mysql_free_result(res);
        }
    }
    /* Synthesize confidence: weighted blend of best answer and best rule */
    double synth_conf = 0.0;
    if (answer_count > 0 && rule_count > 0) {
        synth_conf = (best_answer_conf * 0.6) + (best_rule_conf * 0.4);
    } else if (answer_count > 0) {
        synth_conf = best_answer_conf;
    } else if (rule_count > 0) {
        synth_conf = best_rule_conf * 0.8;
    }
    if (synth_conf < STATE.min_confidence) synth_conf = STATE.min_confidence;
    offset += snprintf(bcl_out + offset, out_sz - offset,
        "}[@CONFIDENCE]{%.2f}[@ANSWER_COUNT]{%d}[@RULE_COUNT]{%d}}",
        synth_conf, answer_count, rule_count);
    strncpy(STATE.last_question, question, sizeof(STATE.last_question) - 1);
    STATE.last_question[sizeof(STATE.last_question) - 1] = '\0';
    STATE.last_confidence = synth_conf;
    STATE.queries_run++;
    return 1;
}
/* DO LEARN — store a new learned rule */
static int cog_do_learn(const char *pattern, const char *fix,
                        const char *confidence_str, char *bcl_out, size_t out_sz) {
    if (!pattern[0] || !fix[0]) {
        return BclResult_Err(bcl_out, out_sz, 20, "PATTERN and FIX required");
    }
    if (!cog_ensure_connected()) {
        return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
    }
    double conf = confidence_str[0] ? atof(confidence_str) : 0.5;
    if (conf < 0.0) conf = 0.0;
    if (conf > 1.0) conf = 1.0;
    char esc_pattern[COG_MAX_FIELD * 2];
    char esc_fix[COG_MAX_FIELD * 2];
    cog_escape_sql(pattern, esc_pattern, sizeof(esc_pattern));
    cog_escape_sql(fix, esc_fix, sizeof(esc_fix));
    char query[COG_MAX_QUERY];
    snprintf(query, sizeof(query),
        "INSERT INTO vb_shared.learned_rules "
        "(pattern, fix_action, confidence, severity, success_count, failure_count, source) "
        "VALUES ('%s', '%s', %.4f, 2, 0, 0, 'cognitive_core')",
        esc_pattern, esc_fix, conf);

    if (mysql_query(STATE.conn, query) != 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "insert failed: %s", mysql_error(STATE.conn));
        return BclResult_Err(bcl_out, out_sz, 11, STATE.last_error);
    }
    my_ulonglong new_id = mysql_insert_id(STATE.conn);
    STATE.facts_learned++;
    STATE.queries_run++;
    char result[512];
    snprintf(result, sizeof(result),
        "[@STATUS]{learned}[@ID]{%llu}[@CONFIDENCE]{%.2f}[@PATTERN]{%.200s}",
        (unsigned long long)new_id, conf, pattern);
    return BclResult_Ok(bcl_out, out_sz, result);
}
/* DO QUERY — shared keyword lookup for rules and answers */
static int cog_do_query(int mode, const char *keyword, int limit,
                        char *bcl_out, size_t out_sz) {
    if (!cog_ensure_connected()) {
        return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
    }
    char esc_k[COG_MAX_QUERY];
    cog_escape_like(keyword, esc_k, sizeof(esc_k));
    char query[COG_MAX_QUERY];
    if (mode == 0) {
        snprintf(query, sizeof(query),
            "SELECT id, LEFT(pattern, 300), LEFT(fix_action, 400), confidence, "
            "success_count, failure_count "
            "FROM vb_shared.learned_rules "
            "WHERE pattern LIKE '%%%s%%' "
            "ORDER BY confidence DESC LIMIT %d",
            esc_k, limit);
    } else {
        snprintf(query, sizeof(query),
            "SELECT qa.id, qq.question, LEFT(qa.answer, 400), qa.confidence "
            "FROM vb_shared.know_answers qa "
            "JOIN vb_shared.know_questions qq ON qa.question_id = qq.id "
            "WHERE qq.question LIKE '%%%s%%' OR qa.answer LIKE '%%%s%%' "
            "ORDER BY qa.confidence DESC LIMIT %d",
            esc_k, esc_k, limit);
    }
    if (mysql_query(STATE.conn, query) != 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "query failed: %s", mysql_error(STATE.conn));
        return BclResult_Err(bcl_out, out_sz, 12, STATE.last_error);
    }
    MYSQL_RES *res = mysql_store_result(STATE.conn);
    if (!res) {
        return BclResult_Err(bcl_out, out_sz, 13, "no result set");
    }
    const char *section = (mode == 0) ? "RULES" : "ANSWERS";
    const char *item = (mode == 0) ? "RULE" : "ANSWER";
    int offset = 0;
    offset += snprintf(bcl_out + offset, out_sz - offset,
        "[@OK]{[@KEYWORD]{%.200s}[@TOTAL]{0}[@%s]{", keyword, section);
    int count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
        const char *rid = row[0] ? row[0] : "0";
        char s1[COG_MAX_SNIPPET], s2[COG_MAX_SNIPPET];
        cog_truncate_text(row[1], s1, sizeof(s1));
        cog_truncate_text(row[2], s2, sizeof(s2));
        double conf = row[3] ? atof(row[3]) : 0.0;
        if (mode == 0) {
            int sc = row[4] ? atoi(row[4]) : 0;
            int fc = row[5] ? atoi(row[5]) : 0;
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@%s]{[@ID]{%s}[@PATTERN]{%.200s}[@FIX]{%.400s}"
                "[@CONF]{%.2f}[@SUCC]{%d}[@FAIL]{%d}}",
                item, rid, s1, s2, conf, sc, fc);
            STATE.rules_found++;
        } else {
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@%s]{[@ID]{%s}[@Q]{%.200s}[@A]{%.400s}[@CONF]{%.2f}}",
                item, rid, s1, s2, conf);
            STATE.answers_found++;
        }
        count++;
    }
    mysql_free_result(res);
    cog_patch_total(bcl_out, count);
    offset = (int)strlen(bcl_out);
    snprintf(bcl_out + offset, out_sz - offset, "}}");
    STATE.queries_run++;
    return 1;
}
/* DO SUMMARY — cognitive summary (counts) */
static int cog_do_summary(char *bcl_out, size_t out_sz) {
    if (!cog_ensure_connected()) {
        return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
    }
    long total_rules = 0, total_answers = 0;
    long total_learned = STATE.facts_learned;
    const char *queries[] = {
        "SELECT COUNT(*) FROM vb_shared.learned_rules",
        "SELECT COUNT(*) FROM vb_shared.know_answers",
        NULL
    };
    long *targets[] = { &total_rules, &total_answers };
    for (int i = 0; queries[i] != NULL; i++) {
        if (mysql_query(STATE.conn, queries[i]) == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) {
                MYSQL_ROW row = mysql_fetch_row(res);
                if (row && row[0]) *targets[i] = atol(row[0]);
                mysql_free_result(res);
            }
        }
    }
    STATE.queries_run++;
    char body[512];
    snprintf(body, sizeof(body),
        "[@SUMMARY]{[@TOTAL_RULES]{%ld}[@TOTAL_ANSWERS]{%ld}"
        "[@TOTAL_LEARNED]{%ld}[@QUERIES_RUN]{%d}[@RULES_FOUND]{%d}"
        "[@ANSWERS_FOUND]{%d}}",
        total_rules, total_answers, total_learned,
        STATE.queries_run, STATE.rules_found, STATE.answers_found);
    return BclResult_Ok(bcl_out, out_sz, body);
}
/* ===== UNIT INTERFACE ===== */
int CognitiveCore_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host, "localhost", sizeof(STATE.host) - 1);
    strncpy(STATE.user, "root", sizeof(STATE.user) - 1);
    STATE.pass[0] = '\0';
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    strncpy(STATE.db_name, "vb_shared", sizeof(STATE.db_name) - 1);
    STATE.max_results = COG_DEFAULT_LIMIT;
    STATE.min_confidence = 0.3;
    STATE.initialized = 1;
    return 1;
}

int CognitiveCore_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) CognitiveCore_Init();
    /* READ_STATE */
    if (strcmp(cmd, "read_state") == 0) {
        char body[640];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{1}[@CONNECTED]{%d}[@DB_NAME]{%s}"
            "[@MAX_RESULTS]{%d}[@MIN_CONFIDENCE]{%.2f}"
            "[@QUERIES_RUN]{%d}[@FACTS_LEARNED]{%d}"
            "[@RULES_FOUND]{%d}[@ANSWERS_FOUND]{%d}"
            "[@LAST_QUESTION]{%.200s}[@LAST_CONFIDENCE]{%.2f}",
            STATE.connected, STATE.db_name,
            STATE.max_results, STATE.min_confidence,
            STATE.queries_run, STATE.facts_learned,
            STATE.rules_found, STATE.answers_found,
            STATE.last_question, STATE.last_confidence);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    /* SET_CONFIG */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char db_name[COG_MAX_DB] = {0};
        char max_results[32] = {0};
        char min_conf[32] = {0};
        BclParser_Extract(&parse, "DB_NAME", db_name, sizeof(db_name));
        BclParser_Extract(&parse, "MAX_RESULTS", max_results, sizeof(max_results));
        BclParser_Extract(&parse, "MIN_CONFIDENCE", min_conf, sizeof(min_conf));
        BclParser_Free(&parse);
        if (db_name[0]) {
            strncpy(STATE.db_name, db_name, sizeof(STATE.db_name) - 1);
            STATE.db_name[sizeof(STATE.db_name) - 1] = '\0';
        }
        if (max_results[0]) {
            int v = atoi(max_results);
            if (v > 0 && v <= COG_MAX_LIMIT) STATE.max_results = v;
        }
        if (min_conf[0]) {
            double v = atof(min_conf);
            if (v >= 0.0 && v <= 1.0) STATE.min_confidence = v;
        }
        if (STATE.conn) { mysql_close(STATE.conn); STATE.conn = NULL; }
        STATE.connected = 0;
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }
    /* REASON */
    if (strcmp(cmd, "reason") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char question[COG_MAX_FIELD] = {0};
        BclParser_Extract(&parse, "QUESTION", question, sizeof(question));
        BclParser_Free(&parse);
        if (!question[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUESTION in packet");
        }
        return cog_do_reason(question, bcl_out, out_sz);
    }
    /* LEARN */
    if (strcmp(cmd, "learn") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char pattern[COG_MAX_FIELD] = {0};
        char fix[COG_MAX_FIELD] = {0};
        char confidence[32] = {0};
        BclParser_Extract(&parse, "PATTERN", pattern, sizeof(pattern));
        BclParser_Extract(&parse, "FIX", fix, sizeof(fix));
        BclParser_Extract(&parse, "CONFIDENCE", confidence, sizeof(confidence));
        BclParser_Free(&parse);
        return cog_do_learn(pattern, fix, confidence, bcl_out, out_sz);
    }
    /* QUERY_RULES */
    if (strcmp(cmd, "query_rules") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char pattern[COG_MAX_FIELD] = {0};
        char limit_str[32] = {0};
        BclParser_Extract(&parse, "PATTERN", pattern, sizeof(pattern));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Free(&parse);
        if (!pattern[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATTERN in packet");
        }
        int limit = limit_str[0] ? atoi(limit_str) : STATE.max_results;
        if (limit <= 0 || limit > COG_MAX_LIMIT) limit = STATE.max_results;
        return cog_do_query(0, pattern, limit, bcl_out, out_sz);
    }
    /* QUERY_ANSWERS */
    if (strcmp(cmd, "query_answers") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char question[COG_MAX_FIELD] = {0};
        char limit_str[32] = {0};
        BclParser_Extract(&parse, "QUESTION", question, sizeof(question));
        BclParser_Extract(&parse, "LIMIT", limit_str, sizeof(limit_str));
        BclParser_Free(&parse);
        if (!question[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUESTION in packet");
        }
        int limit = limit_str[0] ? atoi(limit_str) : STATE.max_results;
        if (limit <= 0 || limit > COG_MAX_LIMIT) limit = STATE.max_results;
        return cog_do_query(1, question, limit, bcl_out, out_sz);
    }
    /* SUMMARY */
    if (strcmp(cmd, "summary") == 0) {
        return cog_do_summary(bcl_out, out_sz);
    }
    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int CognitiveCore_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    return 1;
}

const char * CognitiveCore_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "CognitiveCore: initialized=%d connected=%d db=%s queries=%d learned=%d",
        STATE.initialized, STATE.connected, STATE.db_name,
        STATE.queries_run, STATE.facts_learned);
    return buf;
}
