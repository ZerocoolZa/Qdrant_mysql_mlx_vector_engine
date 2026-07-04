//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_rule_reader.c" date="2026-07-04" author="devin" session_id="bcl-vsstyle-units" context="BCL unit for reading VBStyle rules from MySQL vb_shared.rules table or JSON file. Source: core/Dom_Vsstyle/vbs_rule_reader.py. Commands: read, read_file, list, count, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_rule_reader.c" domain="bcl_units" authority="RuleReader"}
//[@SUMMARY]{summary="VBStyle rule reader. Reads rules from MySQL vb_shared.rules table or local JSON file. Commands: read (MySQL), read_file (JSON), list (names only), count, read_state, set_config."}
//[@CLASS]{class="RuleReader" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="ReadFromDb" type="command"}
//[@METHOD]{method="ReadFromFile" type="command"}
//[@METHOD]{method="ListRules" type="query"}
//[@METHOD]{method="CountRules" type="query"}

#include "bcl_toolstack.h"
#include <mysql.h>
#include <ctype.h>

/* ===== DIM BLOCK ===== */

#define RR_MAX_RULES    512
#define RR_MAX_NAME     128
#define RR_MAX_DESC     512
#define RR_MAX_BODY     32768
#define RR_MAX_FILE     262144

typedef struct {
    char name[RR_MAX_NAME];
    char description[RR_MAX_DESC];
    int  severity;
} RuleEntry;

static struct {
    int       initialized;
    int       rule_count;
    RuleEntry rules[RR_MAX_RULES];
    int       connected;
    MYSQL    *conn;
    char      host[256];
    char      user[64];
    char      pass[128];
    char      socket[256];
    int       port;
    char      last_error[256];
    char      last_file[RR_MAX_NAME];
} STATE;

/* ===== HELPERS ===== */

static void EnsureConnected(void) {
    if (STATE.connected && STATE.conn) return;
    STATE.conn = mysql_init(NULL);
    if (!STATE.conn) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed");
        return;
    }
    STATE.conn = mysql_real_connect(STATE.conn,
        STATE.host[0] ? STATE.host : "localhost",
        STATE.user[0] ? STATE.user : "root",
        STATE.pass[0] ? STATE.pass : "",
        "vb_shared", STATE.port, STATE.socket[0] ? STATE.socket : NULL, 0);
    if (!STATE.conn) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "%s", mysql_error(STATE.conn));
        mysql_close(STATE.conn);
        STATE.conn = NULL;
        return;
    }
    STATE.connected = 1;
}

static int ParseJsonRules(const char *json, int json_len) {
    /* Minimal JSON parser: looks for "rule" and "description" fields */
    STATE.rule_count = 0;
    const char *p = json;
    const char *end = json + json_len;
    
    while (p < end && STATE.rule_count < RR_MAX_RULES) {
        /* Find "rule" or "name" key */
        const char *rule_key = strstr(p, "\"rule\"");
        const char *name_key = strstr(p, "\"name\"");
        const char *key = rule_key ? rule_key : name_key;
        if (!key || key >= end) break;
        
        /* Skip to value */
        p = key;
        while (*p && *p != ':') p++;
        if (*p != ':') break;
        p++;
        while (*p && isspace((unsigned char)*p)) p++;
        if (*p != '"') break;
        p++;
        
        /* Extract name */
        int nlen = 0;
        while (*p && *p != '"' && nlen < RR_MAX_NAME - 1) {
            STATE.rules[STATE.rule_count].name[nlen++] = *p++;
        }
        STATE.rules[STATE.rule_count].name[nlen] = '\0';
        if (*p == '"') p++;
        
        /* Find description */
        const char *desc_key = strstr(p, "\"description\"");
        if (desc_key && desc_key < end) {
            p = desc_key;
            while (*p && *p != ':') p++;
            if (*p == ':') {
                p++;
                while (*p && isspace((unsigned char)*p)) p++;
                if (*p == '"') {
                    p++;
                    int dlen = 0;
                    while (*p && *p != '"' && dlen < RR_MAX_DESC - 1) {
                        STATE.rules[STATE.rule_count].description[dlen++] = *p++;
                    }
                    STATE.rules[STATE.rule_count].description[dlen] = '\0';
                    if (*p == '"') p++;
                }
            }
        } else {
            STATE.rules[STATE.rule_count].description[0] = '\0';
        }
        
        STATE.rules[STATE.rule_count].severity = 1;
        STATE.rule_count++;
    }
    return STATE.rule_count;
}

/* ===== UNIT INTERFACE ===== */

int RuleReader_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    strcpy(STATE.host, "localhost");
    strcpy(STATE.user, "root");
    STATE.port = 0;
    strcpy(STATE.socket, "/tmp/mysql.sock");
    return 1;
}

int RuleReader_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) {
        return BclResult_Err(bcl_out, out_sz, 1, "not initialized");
    }
    
    /* ---- read (from MySQL) ---- */
    if (strcmp(cmd, "read") == 0) {
        EnsureConnected();
        if (!STATE.connected) {
            return BclResult_Err(bcl_out, out_sz, 2, STATE.last_error);
        }
        const char *q = "SELECT rule, LEFT(description, 500) FROM rules ORDER BY rule LIMIT 512";
        if (mysql_query(STATE.conn, q)) {
            return BclResult_Err(bcl_out, out_sz, 3, mysql_error(STATE.conn));
        }
        MYSQL_RES *res = mysql_store_result(STATE.conn);
        if (!res) {
            return BclResult_Err(bcl_out, out_sz, 4, "no result set");
        }
        STATE.rule_count = 0;
        MYSQL_ROW row;
        char body[RR_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset, "[@COUNT]{%d}", (int)mysql_num_rows(res));
        while ((row = mysql_fetch_row(res)) && STATE.rule_count < RR_MAX_RULES) {
            strncpy(STATE.rules[STATE.rule_count].name, row[0] ? row[0] : "", RR_MAX_NAME - 1);
            strncpy(STATE.rules[STATE.rule_count].description, row[1] ? row[1] : "", RR_MAX_DESC - 1);
            STATE.rules[STATE.rule_count].severity = 1;
            STATE.rule_count++;
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@RULE]{[@NAME]{%s}[@DESC]{%s}}",
                row[0] ? row[0] : "", row[1] ? row[1] : "");
            if (offset > (int)sizeof(body) - 512) break;
        }
        mysql_free_result(res);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- read_file (from JSON) ---- */
    if (strcmp(cmd, "read_file") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[RR_MAX_NAME];
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 5, "no PATH in packet");
        }
        FILE *f = fopen(path, "r");
        if (!f) {
            return BclResult_Err(bcl_out, out_sz, 6, "cannot open file");
        }
        char buf[RR_MAX_FILE];
        int n = (int)fread(buf, 1, sizeof(buf) - 1, f);
        buf[n] = '\0';
        fclose(f);
        strncpy(STATE.last_file, path, RR_MAX_NAME - 1);
        int count = ParseJsonRules(buf, n);
        char body[256];
        snprintf(body, sizeof(body), "[@COUNT]{%d}[@FILE]{%s}", count, path);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- list (names only) ---- */
    if (strcmp(cmd, "list") == 0) {
        char body[RR_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset, "[@COUNT]{%d}", STATE.rule_count);
        for (int i = 0; i < STATE.rule_count && offset < (int)sizeof(body) - 256; i++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@RULE]{[@NAME]{%s}}", STATE.rules[i].name);
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- count ---- */
    if (strcmp(cmd, "count") == 0) {
        char body[128];
        snprintf(body, sizeof(body), "[@COUNT]{%d}", STATE.rule_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- read_state ---- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@RULE_COUNT]{%d}[@CONNECTED]{%d}[@LAST_FILE]{%s}[@LAST_ERROR]{%s}",
            STATE.initialized, STATE.rule_count, STATE.connected,
            STATE.last_file[0] ? STATE.last_file : "none",
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- set_config ---- */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[256], user[64], pass[128], socket[256];
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PASS", pass, sizeof(pass));
        BclParser_Extract(&parse, "SOCKET", socket, sizeof(socket));
        BclParser_Free(&parse);
        if (host[0]) strncpy(STATE.host, host, sizeof(STATE.host) - 1);
        if (user[0]) strncpy(STATE.user, user, sizeof(STATE.user) - 1);
        if (pass[0]) strncpy(STATE.pass, pass, sizeof(STATE.pass) - 1);
        if (socket[0]) strncpy(STATE.socket, socket, sizeof(STATE.socket) - 1);
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{config_set}[@HOST]{%s}[@USER]{%s}", STATE.host, STATE.user);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int RuleReader_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    STATE.rule_count = 0;
    return 1;
}

const char * RuleReader_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "RuleReader: initialized=%d rules=%d connected=%d",
        STATE.initialized, STATE.rule_count, STATE.connected);
    return buf;
}
