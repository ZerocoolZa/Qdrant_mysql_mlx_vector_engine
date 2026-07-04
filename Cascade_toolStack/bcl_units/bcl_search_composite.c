//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_msearch_magnetic.c" date="2026-07-03" author="cascade" session_id="bcl-msearch-units" context="BCL unit for msearch magnetic radius search and context reconstruction. Broken from msearch_v5.c sections: MAGNETIC RADIUS SEARCH, chat history radius, graph radius."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_msearch_magnetic.c" domain="cascade_tools" authority="MsearchMagnetic"}
//[@SUMMARY]{summary="Magnetic radius search and context reconstruction for msearch. Commands: magnetic, chat_radius, graph_radius, read_state, set_config. Expands search results with context neighborhood using radius expansion."}
//[@CLASS]{class="MsearchMagnetic" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="MagneticSearch" type="query"}
//[@METHOD]{method="ChatRadius" type="query"}
//[@METHOD]{method="GraphRadius" type="query"}

/*
 * bcl_msearch_magnetic.c — Magnetic radius search and context reconstruction
 *
 * BCL IN:  [@RUN]{[@CMD]{magnetic}[@QUERY]{keyword}[@RADIUS]{200}}
 *          [@RUN]{[@CMD]{chat_radius}[@QUERY]{keyword}[@RADIUS]{50}}
 *          [@RUN]{[@CMD]{graph_radius}[@QUERY]{keyword}[@RADIUS]{100}}
 *          [@RUN]{[@CMD]{read_state}}
 * BCL OUT: [@OK]{[@CENTER]{...}[@NEIGHBORS]{...}[@RADIUS]{N}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_toolstack.h"
#include <mysql.h>

/* ===== DIM BLOCK ===== */

#define MAG_MAX_QUERY      4096
#define MAG_MAX_RADIUS     10000
#define MAG_DEFAULT_RADIUS 200
#define MAG_HOST_LEN       256
#define MAG_USER_LEN       64
#define MAG_PASS_LEN       128
#define MAG_SOCKET_LEN     256
#define MAG_MAX_OUTPUT     65536

/* ===== STATE ===== */

static struct {
    MYSQL *conn;
    int initialized;
    int connected;
    char host[MAG_HOST_LEN];
    char user[MAG_USER_LEN];
    char pass[MAG_PASS_LEN];
    char socket[MAG_SOCKET_LEN];
    int port;
    int magnetic_searches;
    int chat_radius_searches;
    int graph_radius_searches;
    int default_radius;
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
        NULL, STATE.port, sock, 0);
    if (!result) {
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

/* ===== UTILITIES ===== */

static void mag_escape_like(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 2 < out_sz; i++) {
        if (in[i] == '%' || in[i] == '_' || in[i] == '\\')
            out[j++] = '\\';
        out[j++] = in[i];
    }
    out[j] = '\0';
}

static void mag_clean_snippet(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 1 < out_sz; i++) {
        if (in[i] == '\n' || in[i] == '\r') out[j++] = ' ';
        else if (in[i] == '{' || in[i] == '}') out[j++] = ' ';
        else if (in[i] == '[' && in[i+1] == '@') out[j++] = ' ';
        else out[j++] = in[i];
    }
    out[j] = '\0';
}

/* ===== CHAT RADIUS — devin_messages ±N messages around keyword match ===== */

static int chat_radius_search(const char *keyword, int radius,
                              char *out, size_t out_sz) {
    if (!ensure_connected()) return 0;

    char esc_key[MAG_MAX_QUERY];
    mag_escape_like(keyword, esc_key, sizeof(esc_key));

    MYSQL *chat_conn = mysql_init(NULL);
    if (!chat_conn) return 0;
    const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
    if (!mysql_real_connect(chat_conn, STATE.host, STATE.user,
            STATE.pass[0] ? STATE.pass : NULL,
            "devin", STATE.port, sock, 0)) {
        mysql_close(chat_conn);
        return 0;
    }

    char query[MAG_MAX_QUERY];
    snprintf(query, sizeof(query),
        "SELECT session_id, row_id, role, LEFT(content, 200) "
        "FROM devin_messages WHERE content LIKE '%%%s%%' "
        "ORDER BY created_at DESC LIMIT 5",
        esc_key);

    if (mysql_query(chat_conn, query) != 0) {
        mysql_close(chat_conn);
        return 0;
    }
    MYSQL_RES *res = mysql_store_result(chat_conn);
    if (!res) {
        mysql_close(chat_conn);
        return 0;
    }

    int offset = 0;
    int match_count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 1024) {
        const char *sid = row[0] ? row[0] : "";
        int hit_row = row[1] ? atoi(row[1]) : 0;
        const char *role = row[2] ? row[2] : "";
        const char *preview = row[3] ? row[3] : "";

        int win_start = hit_row - radius;
        int win_end = hit_row + radius;
        if (win_start < 0) win_start = 0;

        char wq[MAG_MAX_QUERY];
        snprintf(wq, sizeof(wq),
            "SELECT role, LEFT(content, 300) FROM devin_messages "
            "WHERE session_id = '%s' AND row_id >= %d AND row_id <= %d "
            "ORDER BY row_id LIMIT 20",
            sid, win_start, win_end);

        char window_text[8192];
        window_text[0] = '\0';
        if (mysql_query(chat_conn, wq) == 0) {
            MYSQL_RES *wres = mysql_store_result(chat_conn);
            if (wres) {
                MYSQL_ROW wrow;
                while ((wrow = mysql_fetch_row(wres))) {
                    char wrole[64], wcontent[512];
                    mag_clean_snippet(wrow[0] ? wrow[0] : "", wrole, sizeof(wrole));
                    mag_clean_snippet(wrow[1] ? wrow[1] : "", wcontent, sizeof(wcontent));
                    char part[700];
                    snprintf(part, sizeof(part), "[%s] %.300s  ", wrole, wcontent);
                    strncat(window_text, part, sizeof(window_text) - strlen(window_text) - 1);
                }
                mysql_free_result(wres);
            }
        }

        char clean_preview[512], clean_window[8192];
        mag_clean_snippet(preview, clean_preview, sizeof(clean_preview));
        mag_clean_snippet(window_text, clean_window, sizeof(clean_window));

        offset += snprintf(out + offset, out_sz - offset,
            "[@MATCH]{[@SESSION]{%s}[@HIT_ROW]{%d}[@WINDOW]{pm%d}[@ROLE]{%s}[@PREVIEW]{%.400s}[@CONTEXT]{%.4000s}}",
            sid, hit_row, radius, role, clean_preview, clean_window);
        match_count++;
    }
    mysql_free_result(res);
    mysql_close(chat_conn);
    return match_count;
}

/* ===== GRAPH RADIUS — callers + dependencies from bcl_ir.bcl_edges ===== */

static int graph_radius_search(const char *keyword, int radius,
                               char *out, size_t out_sz) {
    if (!ensure_connected()) return 0;

    char esc_key[MAG_MAX_QUERY];
    mag_escape_like(keyword, esc_key, sizeof(esc_key));

    MYSQL *bcl_conn = mysql_init(NULL);
    if (!bcl_conn) return 0;
    const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
    if (!mysql_real_connect(bcl_conn, STATE.host, STATE.user,
            STATE.pass[0] ? STATE.pass : NULL,
            "bcl_ir", STATE.port, sock, 0)) {
        mysql_close(bcl_conn);
        return 0;
    }

    int offset = 0;
    int total = 0;

    char q[MAG_MAX_QUERY];
    snprintf(q, sizeof(q),
        "SELECT DISTINCT source_method_id, target, edge_type, line_number "
        "FROM bcl_edges WHERE (source_method_id LIKE '%%%s%%' "
        "OR target LIKE '%%%s%%') AND edge_type = 'CALL' LIMIT 10",
        esc_key, esc_key);

    offset += snprintf(out + offset, out_sz - offset, "[@CALLERS]{");
    if (mysql_query(bcl_conn, q) == 0) {
        MYSQL_RES *res = mysql_store_result(bcl_conn);
        if (res) {
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                char src[512], tgt[512];
                mag_clean_snippet(row[0] ? row[0] : "", src, sizeof(src));
                mag_clean_snippet(row[1] ? row[1] : "", tgt, sizeof(tgt));
                offset += snprintf(out + offset, out_sz - offset,
                    "[@EDGE]{[@SOURCE]{%s}[@TARGET]{%s}[@LINE]{%s}}",
                    src, tgt, row[3] ? row[3] : "0");
                total++;
            }
            mysql_free_result(res);
        }
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    snprintf(q, sizeof(q),
        "SELECT DISTINCT source_method_id, target, edge_type "
        "FROM bcl_edges WHERE (source_method_id LIKE '%%%s%%' "
        "OR target LIKE '%%%s%%') AND edge_type IN ('IMPORT','STATE_READ','STATE_WRITE','RESOURCE') LIMIT 10",
        esc_key, esc_key);

    offset += snprintf(out + offset, out_sz - offset, "[@DEPENDENCIES]{");
    if (mysql_query(bcl_conn, q) == 0) {
        MYSQL_RES *res = mysql_store_result(bcl_conn);
        if (res) {
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                char src[512], tgt[512], et[64];
                mag_clean_snippet(row[0] ? row[0] : "", src, sizeof(src));
                mag_clean_snippet(row[1] ? row[1] : "", tgt, sizeof(tgt));
                mag_clean_snippet(row[2] ? row[2] : "", et, sizeof(et));
                offset += snprintf(out + offset, out_sz - offset,
                    "[@DEP]{[@SOURCE]{%s}[@TARGET]{%s}[@TYPE]{%s}}",
                    src, tgt, et);
                total++;
            }
            mysql_free_result(res);
        }
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    mysql_close(bcl_conn);
    return total;
}

/* ===== MAGNETIC SEARCH — 9-section context reconstruction with radius ===== */

static int magnetic_search(const char *keyword, int radius,
                           char *out, size_t out_sz) {
    if (!ensure_connected()) return 0;

    char esc_key[MAG_MAX_QUERY];
    mag_escape_like(keyword, esc_key, sizeof(esc_key));

    int offset = 0;
    int total = 0;
    int limit = radius > 100 ? 5 : 10;

    mysql_query(STATE.conn, "USE vb_shared");

    /* 1. AUTHORITY — class_understandings */
    offset += snprintf(out + offset, out_sz - offset, "[@AUTHORITY]{");
    {
        char q[MAG_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT class_name, cascade_understanding, layer "
            "FROM class_understandings WHERE class_name LIKE '%%%s%%' "
            "OR cascade_understanding LIKE '%%%s%%' LIMIT %d",
            esc_key, esc_key, limit > 3 ? 3 : limit);
        if (mysql_query(STATE.conn, q) == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                    char cn[512], cu[4096];
                    mag_clean_snippet(row[0] ? row[0] : "", cn, sizeof(cn));
                    mag_clean_snippet(row[1] ? row[1] : "", cu, sizeof(cu));
                    offset += snprintf(out + offset, out_sz - offset,
                        "[@ENTRY]{[@CLASS]{%s}[@UNDERSTANDING]{%.500s}[@LAYER]{%s}}",
                        cn, cu, row[2] ? row[2] : "");
                    total++;
                }
                mysql_free_result(res);
            }
        }
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* 2. CHAT CONTEXT — devin_messages ±N messages */
    offset += snprintf(out + offset, out_sz - offset, "[@CHAT_CONTEXT]{");
    offset += chat_radius_search(keyword, radius, out + offset, out_sz - offset - 64);
    offset = strlen(out);
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* 3. GRAPH — callers + dependencies from bcl_ir */
    offset += snprintf(out + offset, out_sz - offset, "[@GRAPH]{");
    offset += graph_radius_search(keyword, radius, out + offset, out_sz - offset - 64);
    offset = strlen(out);
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* 4. CODE — code_classes */
    offset += snprintf(out + offset, out_sz - offset, "[@CODE]{");
    {
        char q[MAG_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT class_name, description FROM code_classes "
            "WHERE class_name LIKE '%%%s%%' LIMIT %d",
            esc_key, limit > 3 ? 3 : limit);
        if (mysql_query(STATE.conn, q) == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                    char cn[512], desc[1024];
                    mag_clean_snippet(row[0] ? row[0] : "", cn, sizeof(cn));
                    mag_clean_snippet(row[1] ? row[1] : "", desc, sizeof(desc));
                    offset += snprintf(out + offset, out_sz - offset,
                        "[@ENTRY]{[@CLASS]{%s}[@DESCRIPTION]{%.300s}}",
                        cn, desc);
                    total++;
                }
                mysql_free_result(res);
            }
        }
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* 5. RULES — learned_rules */
    offset += snprintf(out + offset, out_sz - offset, "[@RULES]{");
    {
        char q[MAG_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT pattern, fix_action, confidence FROM learned_rules "
            "WHERE pattern LIKE '%%%s%%' OR fix_action LIKE '%%%s%%' "
            "ORDER BY confidence DESC LIMIT %d",
            esc_key, esc_key, limit > 5 ? 5 : limit);
        if (mysql_query(STATE.conn, q) == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                    char pat[2048], fix[2048];
                    mag_clean_snippet(row[0] ? row[0] : "", pat, sizeof(pat));
                    mag_clean_snippet(row[1] ? row[1] : "", fix, sizeof(fix));
                    offset += snprintf(out + offset, out_sz - offset,
                        "[@RULE]{[@PATTERN]{%.500s}[@FIX]{%.500s}[@CONFIDENCE]{%s}}",
                        pat, fix, row[2] ? row[2] : "0");
                    total++;
                }
                mysql_free_result(res);
            }
        }
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* 6. METHODS — code_index */
    offset += snprintf(out + offset, out_sz - offset, "[@METHODS]{");
    {
        char q[MAG_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT entity_name, entity_type, related_entity, relationship "
            "FROM code_index WHERE entity_name LIKE '%%%s%%' "
            "OR related_entity LIKE '%%%s%%' LIMIT %d",
            esc_key, esc_key, limit);
        if (mysql_query(STATE.conn, q) == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                    char en[512], re[512];
                    mag_clean_snippet(row[0] ? row[0] : "", en, sizeof(en));
                    mag_clean_snippet(row[2] ? row[2] : "", re, sizeof(re));
                    offset += snprintf(out + offset, out_sz - offset,
                        "[@ENTRY]{[@ENTITY]{%s}[@TYPE]{%s}[@RELATED]{%s}[@REL]{%s}}",
                        en, row[1] ? row[1] : "", re, row[3] ? row[3] : "");
                    total++;
                }
                mysql_free_result(res);
            }
        }
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* 7. TIMELINE — execution_log */
    offset += snprintf(out + offset, out_sz - offset, "[@TIMELINE]{");
    {
        char q[MAG_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT command, status, timestamp FROM execution_log "
            "WHERE command LIKE '%%%s%%' ORDER BY timestamp DESC LIMIT %d",
            esc_key, limit > 5 ? 5 : limit);
        if (mysql_query(STATE.conn, q) == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                    char cmd[2048];
                    mag_clean_snippet(row[0] ? row[0] : "", cmd, sizeof(cmd));
                    offset += snprintf(out + offset, out_sz - offset,
                        "[@ENTRY]{[@COMMAND]{%.500s}[@STATUS]{%s}[@TIME]{%s}}",
                        cmd, row[1] ? row[1] : "", row[2] ? row[2] : "");
                    total++;
                }
                mysql_free_result(res);
            }
        }
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* 8. RELATED — code_identifier_frequency */
    offset += snprintf(out + offset, out_sz - offset, "[@RELATED]{");
    {
        char q[MAG_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT identifier, identifier_type, authority_score "
            "FROM code_identifier_frequency WHERE identifier LIKE '%%%s%%' "
            "ORDER BY authority_score DESC LIMIT %d",
            esc_key, limit > 10 ? 10 : limit);
        if (mysql_query(STATE.conn, q) == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                    char id[512];
                    mag_clean_snippet(row[0] ? row[0] : "", id, sizeof(id));
                    offset += snprintf(out + offset, out_sz - offset,
                        "[@ENTRY]{[@IDENTIFIER]{%s}[@TYPE]{%s}[@AUTHORITY]{%s}}",
                        id, row[1] ? row[1] : "", row[2] ? row[2] : "0");
                    total++;
                }
                mysql_free_result(res);
            }
        }
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* 9. ERRORS — error_knowledge */
    offset += snprintf(out + offset, out_sz - offset, "[@ERRORS]{");
    {
        char q[MAG_MAX_QUERY];
        snprintf(q, sizeof(q),
            "SELECT error_type, cause, solution FROM error_knowledge "
            "WHERE error_type LIKE '%%%s%%' OR cause LIKE '%%%s%%' LIMIT %d",
            esc_key, esc_key, limit > 3 ? 3 : limit);
        if (mysql_query(STATE.conn, q) == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                    char et[512], cause[2048], sol[2048];
                    mag_clean_snippet(row[0] ? row[0] : "", et, sizeof(et));
                    mag_clean_snippet(row[1] ? row[1] : "", cause, sizeof(cause));
                    mag_clean_snippet(row[2] ? row[2] : "", sol, sizeof(sol));
                    offset += snprintf(out + offset, out_sz - offset,
                        "[@ENTRY]{[@TYPE]{%s}[@CAUSE]{%.500s}[@SOLUTION]{%.500s}}",
                        et, cause, sol);
                    total++;
                }
                mysql_free_result(res);
            }
        }
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    return total;
}

/* ===== UNIT INTERFACE ===== */

int MsearchMagnetic_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host, "localhost", sizeof(STATE.host) - 1);
    strncpy(STATE.user, "root", sizeof(STATE.user) - 1);
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    STATE.default_radius = MAG_DEFAULT_RADIUS;
    STATE.initialized = 1;
    return 1;
}

int MsearchMagnetic_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) MsearchMagnetic_Init();

    /* ===== MAGNETIC — context reconstruction with radius ===== */
    if (strcmp(cmd, "magnetic") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[MAG_MAX_QUERY] = {0};
        char radius_str[16] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "RADIUS", radius_str, sizeof(radius_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int radius = radius_str[0] ? atoi(radius_str) : STATE.default_radius;
        if (radius <= 0 || radius > MAG_MAX_RADIUS) radius = STATE.default_radius;

        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{");
        int total = magnetic_search(query, radius, bcl_out + offset, out_sz - offset - 64);
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "[@TOTAL]{%d}}", total);
        STATE.magnetic_searches++;
        return 1;
    }

    /* ===== CHAT_RADIUS — chat history radius only ===== */
    if (strcmp(cmd, "chat_radius") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[MAG_MAX_QUERY] = {0};
        char radius_str[16] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "RADIUS", radius_str, sizeof(radius_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int radius = radius_str[0] ? atoi(radius_str) : 50;

        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{");
        int total = chat_radius_search(query, radius, bcl_out + offset, out_sz - offset - 64);
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "[@TOTAL]{%d}}", total);
        STATE.chat_radius_searches++;
        return 1;
    }

    /* ===== GRAPH_RADIUS — callers + dependencies from bcl_ir ===== */
    if (strcmp(cmd, "graph_radius") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[MAG_MAX_QUERY] = {0};
        char radius_str[16] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "RADIUS", radius_str, sizeof(radius_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int radius = radius_str[0] ? atoi(radius_str) : 100;
        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{");
        int total = graph_radius_search(query, radius, bcl_out + offset, out_sz - offset - 64);
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "[@TOTAL]{%d}}", total);
        STATE.graph_radius_searches++;
        return 1;
    }

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@CONNECTED]{%d}[@MAGNETIC]{%d}[@CHAT]{%d}[@GRAPH]{%d}[@RADIUS]{%d}[@ERROR]{%s}",
            STATE.initialized, STATE.connected,
            STATE.magnetic_searches, STATE.chat_radius_searches,
            STATE.graph_radius_searches, STATE.default_radius,
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[MAG_HOST_LEN] = {0};
        char user[MAG_USER_LEN] = {0};
        char pass[MAG_PASS_LEN] = {0};
        char socket[MAG_SOCKET_LEN] = {0};
        char port_str[16] = {0};
        char radius_str[16] = {0};
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PASS", pass, sizeof(pass));
        BclParser_Extract(&parse, "SOCKET", socket, sizeof(socket));
        BclParser_Extract(&parse, "PORT", port_str, sizeof(port_str));
        BclParser_Extract(&parse, "RADIUS", radius_str, sizeof(radius_str));
        BclParser_Free(&parse);
        if (host[0]) strncpy(STATE.host, host, sizeof(STATE.host) - 1);
        if (user[0]) strncpy(STATE.user, user, sizeof(STATE.user) - 1);
        if (pass[0]) strncpy(STATE.pass, pass, sizeof(STATE.pass) - 1);
        if (socket[0]) strncpy(STATE.socket, socket, sizeof(STATE.socket) - 1);
        if (port_str[0]) STATE.port = atoi(port_str);
        if (radius_str[0]) STATE.default_radius = atoi(radius_str);
        if (STATE.connected) {
            mysql_close(STATE.conn);
            STATE.conn = NULL;
            STATE.connected = 0;
        }
        char body[512];
        snprintf(body, sizeof(body),
            "[@HOST]{%s}[@USER]{%s}[@PORT]{%d}[@SOCKET]{%s}[@RADIUS]{%d}",
            STATE.host, STATE.user, STATE.port, STATE.socket, STATE.default_radius);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int MsearchMagnetic_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    return 1;
}

const char * MsearchMagnetic_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "MsearchMagnetic: initialized=%d connected=%d magnetic=%d chat=%d graph=%d radius=%d",
        STATE.initialized, STATE.connected,
        STATE.magnetic_searches, STATE.chat_radius_searches,
        STATE.graph_radius_searches, STATE.default_radius);
    return buf;
}
