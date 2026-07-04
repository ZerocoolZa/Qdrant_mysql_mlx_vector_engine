//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_msearch_ranking.c" date="2026-07-03" author="cascade" session_id="bcl-msearch-units" context="BCL unit for msearch context-aware ranking and class understandings. Broken from msearch_v5.c sections: CONTEXT-AWARE RANKING, UPDATE ROUTING, CLASS UNDERSTANDINGS."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_msearch_ranking.c" domain="cascade_tools" authority="MsearchRanking"}
//[@SUMMARY]{summary="Context-aware ranking and class understandings for msearch. Commands: rank, update_route, understandings, read_state, set_config. Scores search results by relevance using context keywords and class understanding integration."}
//[@CLASS]{class="MsearchRanking" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="ScoreRelevance" type="query"}
//[@METHOD]{method="UpdateRoute" type="command"}
//[@METHOD]{method="LoadUnderstandings" type="command"}

/*
 * bcl_msearch_ranking.c — Context-aware ranking and class understandings
 *
 * BCL IN:  [@RUN]{[@CMD]{rank}[@QUERY]{keyword}[@CONTEXT]{database}}
 *          [@RUN]{[@CMD]{update_route}[@TABLE]{learned_rules}}
 *          [@RUN]{[@CMD]{understandings}[@CLASS]{Msearch}}
 *          [@RUN]{[@CMD]{read_state}}
 * BCL OUT: [@OK]{[@SCORE]{N}[@ROUTE]{...}[@UNDERSTANDING]{...}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_toolstack.h"
#include <mysql.h>

/* ===== DIM BLOCK ===== */

#define RANK_MAX_CONTEXT    256
#define RANK_MAX_TABLE      128
#define RANK_MAX_CLASS      128
#define RANK_MAX_UNDERSTAND 512
#define RANK_HOST_LEN       256
#define RANK_USER_LEN       64
#define RANK_PASS_LEN       128
#define RANK_SOCKET_LEN     256
#define RANK_MAX_QUERY      4096

/* ===== STATE ===== */

static struct {
    int initialized;
    int connected;
    MYSQL *conn;
    int rankings_computed;
    int routes_resolved;
    int understandings_loaded;
    char host[RANK_HOST_LEN];
    char user[RANK_USER_LEN];
    char pass[RANK_PASS_LEN];
    char socket[RANK_SOCKET_LEN];
    int port;
    char last_context[RANK_MAX_CONTEXT];
    char last_error[256];
} STATE;

/* ===== CONNECT ===== */

static int ensure_connected(void) {
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
        "vb_shared", STATE.port, sock, 0);
    if (!result) {
        result = mysql_real_connect(STATE.conn,
            STATE.host, STATE.user,
            STATE.pass[0] ? STATE.pass : NULL,
            "vb_shared", STATE.port, NULL, 0);
    }
    if (!result) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "connect: %s",
                 mysql_error(STATE.conn));
        return 0;
    }
    STATE.connected = 1;
    return 1;
}

/* ===== CLEAN SNIPPET ===== */

static void rank_clean(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 1 < out_sz; i++) {
        if (in[i] == '\n' || in[i] == '\r') out[j++] = ' ';
        else if (in[i] == '{' || in[i] == '}') out[j++] = ' ';
        else if (in[i] == '[' && in[i+1] == '@') out[j++] = ' ';
        else out[j++] = in[i];
    }
    out[j] = '\0';
}

/* ===== SCORE RELEVANCE — uses registry metadata (purpose, contains, notes) ===== */

static int score_relevance(const char *table_name, const char *keyword, const char *context) {
    int score = 0;
    if (!table_name || !keyword) return 0;

    /* Query table_registry for metadata */
    if (ensure_connected()) {
        char q[RANK_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT purpose, `contains`, notes, table_type FROM table_registry "
            "WHERE table_name = '%s'", table_name);
        if (mysql_query(STATE.conn, q) == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) {
                MYSQL_ROW row = mysql_fetch_row(res);
                if (row) {
                    const char *purpose = row[0] ? row[0] : "";
                    const char *contains = row[1] ? row[1] : "";
                    const char *notes = row[2] ? row[2] : "";
                    const char *ttype = row[3] ? row[3] : "";

                    /* Keyword match in purpose */
                    if (strstr(purpose, keyword)) score += 100;
                    /* Keyword match in contains */
                    if (strstr(contains, keyword)) score += 80;
                    /* Keyword match in notes */
                    if (strstr(notes, keyword)) score += 40;

                    /* Table type specific boosts */
                    if (strcmp(ttype, "meta") == 0) score += 15;
                    if (strcmp(ttype, "code") == 0 && context && strcmp(context, "code") == 0) score += 30;
                    if (strcmp(ttype, "token") == 0 && context && strcmp(context, "database") == 0) score += 25;
                }
                mysql_free_result(res);
            }
        }
    }

    /* Fallback: exact table name match with keyword */
    if (strstr(table_name, keyword)) score += 50;

    /* Context-aware boosting */
    if (context && context[0]) {
        if (strstr(table_name, context)) score += 30;
        if (strcmp(context, "database") == 0 && strstr(table_name, "rule")) score += 20;
        if (strcmp(context, "code") == 0 && strstr(table_name, "class")) score += 20;
        if (strcmp(context, "error") == 0 && strstr(table_name, "problem")) score += 20;
        if (strcmp(context, "chat") == 0 && strstr(table_name, "message")) score += 20;
    }

    /* Priority tables get base score */
    if (strstr(table_name, "learned_rules")) score += 20;
    if (strstr(table_name, "know_problems")) score += 15;
    if (strstr(table_name, "know_solutions")) score += 15;
    if (strstr(table_name, "know_answers")) score += 10;
    if (strstr(table_name, "devin_messages")) score += 5;

    return score;
}

/* ===== UPDATE ROUTE ===== */

static const char *resolve_update_route(const char *table_name) {
    if (!table_name) return NULL;
    if (strstr(table_name, "learned_rules")) return "vb_shared.learned_rules";
    if (strstr(table_name, "know_problems")) return "vb_shared.know_problems";
    if (strstr(table_name, "know_solutions")) return "vb_shared.know_solutions";
    if (strstr(table_name, "know_questions")) return "vb_shared.know_questions";
    if (strstr(table_name, "know_answers")) return "vb_shared.know_answers";
    if (strstr(table_name, "code_classes")) return "vb_shared.code_classes";
    if (strstr(table_name, "instructions")) return "vb_shared.instructions";
    if (strstr(table_name, "rule_tokens")) return "vb_shared.rule_tokens";
    if (strstr(table_name, "vb_classes")) return "vb_code_test.vb_classes";
    if (strstr(table_name, "vb_methods")) return "vb_code_test.vb_methods";
    if (strstr(table_name, "devin_messages")) return "devin.devin_messages";
    if (strstr(table_name, "devin_summaries")) return "devin.devin_summaries";
    return NULL;
}

/* ===== UNIT INTERFACE ===== */

int MsearchRanking_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host, "localhost", sizeof(STATE.host) - 1);
    strncpy(STATE.user, "root", sizeof(STATE.user) - 1);
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    STATE.initialized = 1;
    return 1;
}

int MsearchRanking_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) MsearchRanking_Init();

    /* ===== RANK — score relevance of a table for a keyword ===== */
    if (strcmp(cmd, "rank") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[4096] = {0};
        char context[RANK_MAX_CONTEXT] = {0};
        char table[RANK_MAX_TABLE] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "CONTEXT", context, sizeof(context));
        BclParser_Extract(&parse, "TABLE", table, sizeof(table));
        BclParser_Free(&parse);
        if (!table[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no TABLE in packet");
        }
        int score = score_relevance(table, query, context);
        STATE.rankings_computed++;
        if (context[0]) strncpy(STATE.last_context, context, sizeof(STATE.last_context) - 1);
        char body[512];
        snprintf(body, sizeof(body),
            "[@TABLE]{%s}[@KEYWORD]{%s}[@CONTEXT]{%s}[@SCORE]{%d}",
            table, query, context, score);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== UPDATE_ROUTE — resolve where updates go for a table ===== */
    if (strcmp(cmd, "update_route") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char table[RANK_MAX_TABLE] = {0};
        BclParser_Extract(&parse, "TABLE", table, sizeof(table));
        BclParser_Free(&parse);
        if (!table[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no TABLE in packet");
        }
        const char *route = resolve_update_route(table);
        STATE.routes_resolved++;
        char body[512];
        snprintf(body, sizeof(body),
            "[@TABLE]{%s}[@ROUTE]{%s}",
            table, route ? route : "unknown");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== UNDERSTANDINGS — fetch class understanding from MySQL ===== */
    if (strcmp(cmd, "understandings") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char class_name[RANK_MAX_CLASS] = {0};
        BclParser_Extract(&parse, "CLASS", class_name, sizeof(class_name));
        BclParser_Free(&parse);
        if (!class_name[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no CLASS in packet");
        }
        STATE.understandings_loaded++;

        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }

        char q[RANK_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT class_name, cascade_understanding, layer, code_classes_id "
            "FROM class_understandings WHERE class_name = '%s'", class_name);

        if (mysql_query(STATE.conn, q) != 0) {
            return BclResult_Err(bcl_out, out_sz, 30, "query class_understandings failed");
        }

        MYSQL_RES *res = mysql_store_result(STATE.conn);
        if (!res) {
            return BclResult_Err(bcl_out, out_sz, 31, "no results from class_understandings");
        }

        MYSQL_ROW row = mysql_fetch_row(res);
        if (!row) {
            mysql_free_result(res);
            char body[512];
            snprintf(body, sizeof(body),
                "[@CLASS]{%s}[@STATUS]{not_found}", class_name);
            return BclResult_Ok(bcl_out, out_sz, body);
        }

        char cn[512], cu[RANK_MAX_UNDERSTAND * 8];
        rank_clean(row[0] ? row[0] : "", cn, sizeof(cn));
        rank_clean(row[1] ? row[1] : "", cu, sizeof(cu));

        char body[RANK_MAX_UNDERSTAND * 8 + 512];
        snprintf(body, sizeof(body),
            "[@CLASS]{%s}[@UNDERSTANDING]{%.500s}[@LAYER]{%s}[@CODE_ID]{%s}",
            cn, cu, row[2] ? row[2] : "", row[3] ? row[3] : "0");
        mysql_free_result(res);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== WHERE_TO_STORE — query table_registry + INFORMATION_SCHEMA for storage suggestions ===== */
    if (strcmp(cmd, "where_to_store") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char keyword[RANK_MAX_QUERY] = {0};
        BclParser_Extract(&parse, "QUERY", keyword, sizeof(keyword));
        BclParser_Free(&parse);
        if (!keyword[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }

        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }

        char esc_key[RANK_MAX_QUERY];
        size_t ej = 0;
        for (size_t i = 0; keyword[i] && ej + 2 < sizeof(esc_key); i++) {
            if (keyword[i] == '%' || keyword[i] == '_' || keyword[i] == '\\')
                esc_key[ej++] = '\\';
            esc_key[ej++] = keyword[i];
        }
        esc_key[ej] = '\0';

        char q[RANK_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT table_name, table_type, purpose, `contains`, notes "
            "FROM table_registry WHERE purpose LIKE '%%%s%%' "
            "OR `contains` LIKE '%%%s%%' OR notes LIKE '%%%s%%' LIMIT 20",
            esc_key, esc_key, esc_key);

        if (mysql_query(STATE.conn, q) != 0) {
            return BclResult_Err(bcl_out, out_sz, 30, "query table_registry failed");
        }

        MYSQL_RES *res = mysql_store_result(STATE.conn);
        if (!res) {
            return BclResult_Err(bcl_out, out_sz, 31, "no results from table_registry");
        }

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@QUERY]{%s}[@SUGGESTIONS]{", keyword);

        MYSQL_ROW row;
        int count = 0;
        while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 1024) {
            const char *tname = row[0] ? row[0] : "";
            char tp[128], purpose[1024], contains[1024], notes[1024];
            rank_clean(row[1] ? row[1] : "", tp, sizeof(tp));
            rank_clean(row[2] ? row[2] : "", purpose, sizeof(purpose));
            rank_clean(row[3] ? row[3] : "", contains, sizeof(contains));
            rank_clean(row[4] ? row[4] : "", notes, sizeof(notes));

            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@TABLE]{[@NAME]{%s}[@TYPE]{%s}[@PURPOSE]{%.300s}[@CONTAINS]{%.300s}[@NOTES]{%.300s}",
                tname, tp, purpose, contains, notes);

            /* Get actual columns from INFORMATION_SCHEMA */
            char cq[512];
            snprintf(cq, sizeof(cq),
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA='vb_shared' AND TABLE_NAME='%s' "
                "ORDER BY ORDINAL_POSITION", tname);

            if (mysql_query(STATE.conn, cq) == 0) {
                MYSQL_RES *cres = mysql_store_result(STATE.conn);
                if (cres) {
                    offset += snprintf(bcl_out + offset, out_sz - offset, "[@COLUMNS]{");
                    MYSQL_ROW crow;
                    int first = 1;
                    while ((crow = mysql_fetch_row(cres)) != NULL && offset < (int)out_sz - 256) {
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "%s%s", first ? "" : ",", crow[0] ? crow[0] : "");
                        first = 0;
                    }
                    offset += snprintf(bcl_out + offset, out_sz - offset, "}");
                    mysql_free_result(cres);
                }
            }
            offset += snprintf(bcl_out + offset, out_sz - offset, "}");
            count++;
        }
        mysql_free_result(res);

        if (count == 0) {
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@SUGGESTION]{store in instructions (category=general, priority=0)}");
        }

        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "[@COUNT]{%d}}", count);
        return 1;
    }

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@RANKINGS]{%d}[@ROUTES]{%d}[@UNDERSTANDINGS]{%d}[@CONTEXT]{%s}[@ERROR]{%s}",
            STATE.initialized, STATE.rankings_computed, STATE.routes_resolved,
            STATE.understandings_loaded,
            STATE.last_context[0] ? STATE.last_context : "none",
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[RANK_HOST_LEN] = {0};
        char user[RANK_USER_LEN] = {0};
        char pass[RANK_PASS_LEN] = {0};
        char socket[RANK_SOCKET_LEN] = {0};
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

int MsearchRanking_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    return 1;
}

const char * MsearchRanking_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "MsearchRanking: initialized=%d rankings=%d routes=%d understandings=%d",
        STATE.initialized, STATE.rankings_computed, STATE.routes_resolved,
        STATE.understandings_loaded);
    return buf;
}
