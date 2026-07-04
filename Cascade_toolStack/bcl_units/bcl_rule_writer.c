//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_rule_writer.c" date="2026-07-04" author="devin" session_id="bcl-vsstyle-units" context="BCL unit for writing VBStyle rules to MySQL vb_shared.rules table or JSON file. Source: core/Dom_Vsstyle/vbs_rule_writer.py. Commands: write, write_file, insert, delete, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_rule_writer.c" domain="bcl_units" authority="RuleWriter"}
//[@SUMMARY]{summary="VBStyle rule writer. Writes rules to MySQL vb_shared.rules or JSON file. Commands: write (MySQL bulk), write_file (JSON), insert (single rule), delete (by name), read_state, set_config."}
//[@CLASS]{class="RuleWriter" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="WriteToDb" type="command"}
//[@METHOD]{method="WriteToFile" type="command"}
//[@METHOD]{method="InsertRule" type="command"}
//[@METHOD]{method="DeleteRule" type="command"}

#include "bcl_toolstack.h"
#include <mysql.h>

/* ===== DIM BLOCK ===== */

#define RW_MAX_RULES    256
#define RW_MAX_NAME     128
#define RW_MAX_DESC     512
#define RW_MAX_BODY     16384
#define RW_MAX_FILE     262144
#define RW_MAX_QUERY    4096

typedef struct {
    char name[RW_MAX_NAME];
    char description[RW_MAX_DESC];
    int  severity;
} RuleWrite;

static struct {
    int        initialized;
    int        rule_count;
    RuleWrite  rules[RW_MAX_RULES];
    int        written_count;
    int        error_count;
    int        connected;
    MYSQL     *conn;
    char       host[256];
    char       user[64];
    char       pass[128];
    char       socket[256];
    int        port;
    char       last_error[256];
    char       last_file[RW_MAX_NAME];
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

static int EscapeString(MYSQL *conn, char *out, size_t out_sz, const char *in) {
    if (!in || !in[0]) {
        out[0] = '\0';
        return 0;
    }
    return mysql_real_escape_string(conn, out, in, (unsigned long)strlen(in));
}

/* ===== UNIT INTERFACE ===== */

int RuleWriter_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    strcpy(STATE.host, "localhost");
    strcpy(STATE.user, "root");
    STATE.port = 0;
    strcpy(STATE.socket, "/tmp/mysql.sock");
    return 1;
}

int RuleWriter_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) {
        return BclResult_Err(bcl_out, out_sz, 1, "not initialized");
    }
    
    /* ---- write (bulk to MySQL) ---- */
    if (strcmp(cmd, "write") == 0) {
        EnsureConnected();
        if (!STATE.connected) {
            return BclResult_Err(bcl_out, out_sz, 2, STATE.last_error);
        }
        int written = 0;
        int errors = 0;
        for (int i = 0; i < STATE.rule_count; i++) {
            char ename[RW_MAX_NAME * 2];
            char edesc[RW_MAX_DESC * 2];
            EscapeString(STATE.conn, ename, sizeof(ename), STATE.rules[i].name);
            EscapeString(STATE.conn, edesc, sizeof(edesc), STATE.rules[i].description);
            char query[RW_MAX_QUERY];
            snprintf(query, sizeof(query),
                "INSERT INTO rules (rule, description) VALUES ('%s', '%s') ON DUPLICATE KEY UPDATE description='%s'",
                ename, edesc, edesc);
            if (mysql_query(STATE.conn, query)) {
                errors++;
            } else {
                written++;
            }
        }
        STATE.written_count = written;
        STATE.error_count = errors;
        char body[256];
        snprintf(body, sizeof(body), "[@WRITTEN]{%d}[@ERRORS]{%d}[@TOTAL]{%d}", written, errors, STATE.rule_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- write_file (to JSON) ---- */
    if (strcmp(cmd, "write_file") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[RW_MAX_NAME];
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 5, "no PATH in packet");
        }
        FILE *f = fopen(path, "w");
        if (!f) {
            return BclResult_Err(bcl_out, out_sz, 6, "cannot open file for writing");
        }
        fprintf(f, "{\n  \"rules\": [\n");
        for (int i = 0; i < STATE.rule_count; i++) {
            fprintf(f, "    {\"rule\": \"%s\", \"description\": \"%s\"}%s\n",
                STATE.rules[i].name, STATE.rules[i].description,
                (i < STATE.rule_count - 1) ? "," : "");
        }
        fprintf(f, "  ]\n}\n");
        fclose(f);
        strncpy(STATE.last_file, path, RW_MAX_NAME - 1);
        char body[256];
        snprintf(body, sizeof(body), "[@WRITTEN]{%d}[@FILE]{%s}", STATE.rule_count, path);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- insert (single rule into in-memory list) ---- */
    if (strcmp(cmd, "insert") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char name[RW_MAX_NAME];
        char desc[RW_MAX_DESC];
        BclParser_Extract(&parse, "NAME", name, sizeof(name));
        BclParser_Extract(&parse, "DESC", desc, sizeof(desc));
        BclParser_Free(&parse);
        if (!name[0]) {
            return BclResult_Err(bcl_out, out_sz, 7, "no NAME in packet");
        }
        if (STATE.rule_count >= RW_MAX_RULES) {
            return BclResult_Err(bcl_out, out_sz, 8, "rule buffer full");
        }
        strncpy(STATE.rules[STATE.rule_count].name, name, RW_MAX_NAME - 1);
        strncpy(STATE.rules[STATE.rule_count].description, desc, RW_MAX_DESC - 1);
        STATE.rules[STATE.rule_count].severity = 1;
        STATE.rule_count++;
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{inserted}[@NAME]{%s}[@TOTAL]{%d}", name, STATE.rule_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- delete (from MySQL by name) ---- */
    if (strcmp(cmd, "delete") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char name[RW_MAX_NAME];
        BclParser_Extract(&parse, "NAME", name, sizeof(name));
        BclParser_Free(&parse);
        if (!name[0]) {
            return BclResult_Err(bcl_out, out_sz, 9, "no NAME in packet");
        }
        EnsureConnected();
        if (!STATE.connected) {
            return BclResult_Err(bcl_out, out_sz, 2, STATE.last_error);
        }
        char ename[RW_MAX_NAME * 2];
        EscapeString(STATE.conn, ename, sizeof(ename), name);
        char query[RW_MAX_QUERY];
        snprintf(query, sizeof(query), "DELETE FROM rules WHERE rule='%s'", ename);
        if (mysql_query(STATE.conn, query)) {
            return BclResult_Err(bcl_out, out_sz, 10, mysql_error(STATE.conn));
        }
        int affected = (int)mysql_affected_rows(STATE.conn);
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{deleted}[@NAME]{%s}[@AFFECTED]{%d}", name, affected);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- read_state ---- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@RULE_COUNT]{%d}[@WRITTEN]{%d}[@ERRORS]{%d}[@CONNECTED]{%d}[@LAST_FILE]{%s}",
            STATE.initialized, STATE.rule_count, STATE.written_count, STATE.error_count,
            STATE.connected, STATE.last_file[0] ? STATE.last_file : "none");
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
        snprintf(body, sizeof(body), "[@STATUS]{config_set}[@HOST]{%s}", STATE.host);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int RuleWriter_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    STATE.rule_count = 0;
    STATE.written_count = 0;
    STATE.error_count = 0;
    return 1;
}

const char * RuleWriter_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "RuleWriter: initialized=%d rules=%d written=%d errors=%d",
        STATE.initialized, STATE.rule_count, STATE.written_count, STATE.error_count);
    return buf;
}
