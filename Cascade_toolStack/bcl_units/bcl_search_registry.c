//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_msearch_registry.c" date="2026-07-03" author="cascade" session_id="bcl-msearch-units" context="BCL unit for msearch registry routing and schema loading. Handles table_registry loading, BCL bracket keyword detection, and schema discovery. Broken from msearch_v5.c sections: REGISTRY-FIRST ROUTING, BCL BRACKET AWARENESS, SCHEMA LOADING."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_msearch_registry.c" domain="cascade_tools" authority="MsearchRegistry"}
//[@SUMMARY]{summary="Registry-first routing and schema loading for msearch. Commands: load_registry, detect_route, schema, read_state, set_config. Loads table_registry metadata, detects keyword routing patterns, discovers MySQL schema."}
//[@CLASS]{class="MsearchRegistry" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="LoadRegistry" type="command"}
//[@METHOD]{method="DetectRoute" type="query"}
//[@METHOD]{method="DiscoverSchema" type="query"}

/*
 * bcl_msearch_registry.c — Registry routing and schema loading
 *
 * BCL IN:  [@RUN]{[@CMD]{load_registry}[@HOST]{localhost}[@USER]{root}[@PORT]{3306}}
 *          [@RUN]{[@CMD]{detect_route}[@QUERY]{[@TokenName]}}
 *          [@RUN]{[@CMD]{schema}[@DB]{vb_shared}}
 *          [@RUN]{[@CMD]{read_state}}
 * BCL OUT: [@OK]{[@REGISTRY]{...}[@ROUTE]{token_table}[@TABLES]{...}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_toolstack.h"
#include <mysql.h>

/* ===== DIM BLOCK ===== */

#define REG_MAX_TABLES    1024
#define REG_MAX_COLS      512
#define REG_MAX_DB        64
#define REG_HOST_LEN      256
#define REG_USER_LEN      64
#define REG_PASS_LEN      128
#define REG_SOCKET_LEN    256

typedef struct {
    char table[256];
    char cols[REG_MAX_COLS][256];
    int  col_count;
    char table_type[64];
    char purpose[512];
    char contains[512];
    char notes[512];
    char related_tables[256];
    int  has_registry;
    int  relevance;
} RegistrySchema;

/* ===== STATE ===== */

static struct {
    MYSQL *conn;
    int initialized;
    int connected;
    char host[REG_HOST_LEN];
    char user[REG_USER_LEN];
    char pass[REG_PASS_LEN];
    char socket[REG_SOCKET_LEN];
    int port;
    RegistrySchema schema[REG_MAX_TABLES];
    int table_count;
    int registries_loaded;
    int routes_detected;
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

/* ===== LOAD REGISTRY ===== */

static int load_registry(char *out, size_t out_sz, int *offset) {
    if (!ensure_connected()) return 0;

    if (mysql_query(STATE.conn, "SELECT COUNT(*) FROM table_registry")) {
        return 0;
    }
    MYSQL_RES *res = mysql_store_result(STATE.conn);
    if (res) mysql_free_result(res);

    if (mysql_query(STATE.conn,
        "SELECT table_name, table_type, purpose, `contains`, notes, related_tables "
        "FROM table_registry")) {
        return 0;
    }

    res = mysql_store_result(STATE.conn);
    if (!res) return 0;

    int loaded = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        const char *tname = row[0] ? row[0] : "";
        for (int i = 0; i < STATE.table_count; i++) {
            if (strcmp(STATE.schema[i].table, tname) == 0) {
                strncpy(STATE.schema[i].table_type, row[1] ? row[1] : "", 63);
                strncpy(STATE.schema[i].purpose, row[2] ? row[2] : "", 511);
                strncpy(STATE.schema[i].contains, row[3] ? row[3] : "", 511);
                strncpy(STATE.schema[i].notes, row[4] ? row[4] : "", 511);
                strncpy(STATE.schema[i].related_tables, row[5] ? row[5] : "", 255);
                STATE.schema[i].has_registry = 1;
                loaded++;
                break;
            }
        }
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@REG]{[@TABLE]{%s}[@TYPE]{%s}[@PURPOSE]{%.200s}}",
            tname, row[1] ? row[1] : "", row[2] ? row[2] : "");
    }
    mysql_free_result(res);
    STATE.registries_loaded += loaded;
    return loaded;
}

/* ===== DETECT ROUTE ===== */

static const char *detect_route(const char *keyword) {
    if (keyword[0] == '[' && keyword[1] == '@')
        return "token_table";
    if (strncmp(keyword, "dom_", 4) == 0)
        return "code_table";
    if (keyword[0] == '[' && (strstr(keyword, "INTENT") || strstr(keyword, "PURPOSE")))
        return "code_table";
    if (strstr(keyword, "err") || strstr(keyword, "error") || strstr(keyword, "fix"))
        return "token_table";
    if (strstr(keyword, "workflow") || strstr(keyword, "flow"))
        return "token_table";
    return NULL;
}

/* ===== IS_TEXT_TYPE — check if MySQL data type is text-based ===== */

static int is_text_type(const char *type) {
    return !strcasecmp(type, "char") ||
           !strcasecmp(type, "varchar") ||
           !strcasecmp(type, "text") ||
           !strcasecmp(type, "tinytext") ||
           !strcasecmp(type, "mediumtext") ||
           !strcasecmp(type, "longtext");
}

/* ===== DISCOVER SCHEMA — table discovery + column discovery via INFORMATION_SCHEMA ===== */

static int discover_schema(const char *db_filter, char *out, size_t out_sz, int *offset) {
    if (!ensure_connected()) return 0;

    char query[512];
    if (db_filter && db_filter[0]) {
        snprintf(query, sizeof(query),
            "SHOW TABLES FROM `%s`", db_filter);
    } else {
        snprintf(query, sizeof(query),
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA IN ('vb_shared','vb_code_test','devin') "
            "AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_SCHEMA, TABLE_NAME");
    }

    if (mysql_query(STATE.conn, query) != 0) return 0;
    MYSQL_RES *res = mysql_store_result(STATE.conn);
    if (!res) return 0;

    int count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL && *offset < (int)out_sz - 256) {
        const char *tname = row[0] ? row[0] : "";
        if (count < REG_MAX_TABLES) {
            strncpy(STATE.schema[count].table, tname, 255);
            STATE.schema[count].col_count = 0;
            STATE.schema[count].has_registry = 0;
            STATE.schema[count].relevance = 0;

            /* Discover text columns via INFORMATION_SCHEMA.COLUMNS */
            char cq[512];
            snprintf(cq, sizeof(cq),
                "SELECT COLUMN_NAME, DATA_TYPE "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s'",
                db_filter && db_filter[0] ? db_filter : "vb_shared", tname);

            if (mysql_query(STATE.conn, cq) == 0) {
                MYSQL_RES *cres = mysql_store_result(STATE.conn);
                if (cres) {
                    MYSQL_ROW crow;
                    while ((crow = mysql_fetch_row(cres)) != NULL &&
                           STATE.schema[count].col_count < REG_MAX_COLS) {
                        if (crow[1] && is_text_type(crow[1])) {
                            strncpy(STATE.schema[count].cols[STATE.schema[count].col_count++],
                                crow[0], 255);
                        }
                    }
                    mysql_free_result(cres);
                }
            }

            count++;
        }
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@TABLE]{%s}", tname);
    }
    STATE.table_count = count;
    mysql_free_result(res);

    /* Load registry metadata after schema discovery */
    load_registry(out, out_sz, offset);

    return count;
}

/* ===== UNIT INTERFACE ===== */

int MsearchRegistry_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host, "localhost", sizeof(STATE.host) - 1);
    strncpy(STATE.user, "root", sizeof(STATE.user) - 1);
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    STATE.initialized = 1;
    return 1;
}

int MsearchRegistry_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) MsearchRegistry_Init();

    /* ===== LOAD_REGISTRY ===== */
    if (strcmp(cmd, "load_registry") == 0) {
        if (!ensure_connected()) {
            return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        }
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{");
        int loaded = load_registry(bcl_out, out_sz, &offset);
        char count_str[64];
        snprintf(count_str, sizeof(count_str), "[@LOADED]{%d}", loaded);
        offset += snprintf(bcl_out + offset, out_sz - offset, "%s}", count_str);
        return 1;
    }

    /* ===== DETECT_ROUTE ===== */
    if (strcmp(cmd, "detect_route") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[4096] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        const char *route = detect_route(query);
        STATE.routes_detected++;
        char body[512];
        snprintf(body, sizeof(body), "[@QUERY]{%s}[@ROUTE]{%s}",
            query, route ? route : "all");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SCHEMA ===== */
    if (strcmp(cmd, "schema") == 0) {
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
        int count = discover_schema(db_filter[0] ? db_filter : NULL,
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

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@CONNECTED]{%d}[@TABLES]{%d}[@REGISTRIES]{%d}[@ROUTES]{%d}[@ERROR]{%s}",
            STATE.initialized, STATE.connected, STATE.table_count,
            STATE.registries_loaded, STATE.routes_detected,
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[REG_HOST_LEN] = {0};
        char user[REG_USER_LEN] = {0};
        char pass[REG_PASS_LEN] = {0};
        char socket[REG_SOCKET_LEN] = {0};
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

int MsearchRegistry_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    return 1;
}

const char * MsearchRegistry_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "MsearchRegistry: initialized=%d connected=%d tables=%d registries=%d routes=%d",
        STATE.initialized, STATE.connected, STATE.table_count,
        STATE.registries_loaded, STATE.routes_detected);
    return buf;
}
