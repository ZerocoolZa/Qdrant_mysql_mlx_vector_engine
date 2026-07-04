//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_rule_gap_graph.c" date="2026-07-04" author="devin" session_id="bcl-vsstyle-units" context="BCL unit for finding rule coverage gaps. Source: core/Dom_Vsstyle/vbs_rule_gap_graph.py. Commands: build, gaps, covered, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_rule_gap_graph.c" domain="bcl_units" authority="RuleGapGraph"}
//[@SUMMARY]{summary="Rule gap graph. Finds rules with no code coverage. Queries MySQL rules + code_co_occurrence. Commands: build, gaps, covered, read_state, set_config."}
//[@CLASS]{class="RuleGapGraph" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Build" type="command"}
//[@METHOD]{method="Gaps" type="query"}
//[@METHOD]{method="Covered" type="query"}

#include "bcl_toolstack.h"
#include <mysql.h>
#include <ctype.h>

/* ===== DIM BLOCK ===== */

#define RGG_MAX_GAPS    256
#define RGG_MAX_BODY    16384
#define RGG_MAX_NAME    128
#define RGG_MAX_AREA    256
#define RGG_MAX_DESC    512

typedef struct {
    char rule[RGG_MAX_NAME];
    char area[RGG_MAX_AREA];
    int  covered;
} GapEntry;

static struct {
    int       initialized;
    int       gap_count;
    int       covered_count;
    GapEntry  gaps[RGG_MAX_GAPS];
    GapEntry  covered[RGG_MAX_GAPS];
    int       connected;
    MYSQL    *conn;
    char      host[256];
    char      user[64];
    char      pass[128];
    char      socket[256];
    int       port;
    char      last_error[256];
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

/* Build the gap graph from MySQL vb_shared.rules + vb_shared.code_co_occurrence.
   A rule is "covered" if a matching code_co_occurrence row exists for its name;
   otherwise it is a gap. */
static int BuildGapGraph(void) {
    EnsureConnected();
    if (!STATE.connected) {
        return 0;
    }
    /* Load all rules */
    const char *q_rules = "SELECT rule, LEFT(description, 500) FROM rules ORDER BY rule LIMIT 512";
    if (mysql_query(STATE.conn, q_rules)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "%s", mysql_error(STATE.conn));
        return 0;
    }
    MYSQL_RES *res_rules = mysql_store_result(STATE.conn);
    if (!res_rules) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "no rules result set");
        return 0;
    }
    STATE.gap_count = 0;
    STATE.covered_count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res_rules))) {
        const char *rname = row[0] ? row[0] : "";
        const char *rdesc = row[1] ? row[1] : "";
        /* Check code_co_occurrence for a matching entity */
        char ename[RGG_MAX_NAME * 2];
        mysql_real_escape_string(STATE.conn, ename, rname, (unsigned long)strlen(rname));
        char q_coc[512];
        snprintf(q_coc, sizeof(q_coc),
            "SELECT entity FROM code_co_occurrence WHERE entity='%s' LIMIT 1", ename);
        if (mysql_query(STATE.conn, q_coc)) {
            /* table may be missing — treat as gap */
            if (STATE.gap_count < RGG_MAX_GAPS) {
                strncpy(STATE.gaps[STATE.gap_count].rule, rname, RGG_MAX_NAME - 1);
                strncpy(STATE.gaps[STATE.gap_count].area, rdesc, RGG_MAX_AREA - 1);
                STATE.gaps[STATE.gap_count].covered = 0;
                STATE.gap_count++;
            }
            continue;
        }
        MYSQL_RES *res_coc = mysql_store_result(STATE.conn);
        int has_match = 0;
        if (res_coc) {
            has_match = (mysql_num_rows(res_coc) > 0);
            mysql_free_result(res_coc);
        }
        if (has_match) {
            if (STATE.covered_count < RGG_MAX_GAPS) {
                strncpy(STATE.covered[STATE.covered_count].rule, rname, RGG_MAX_NAME - 1);
                strncpy(STATE.covered[STATE.covered_count].area, rdesc, RGG_MAX_AREA - 1);
                STATE.covered[STATE.covered_count].covered = 1;
                STATE.covered_count++;
            }
        } else {
            if (STATE.gap_count < RGG_MAX_GAPS) {
                strncpy(STATE.gaps[STATE.gap_count].rule, rname, RGG_MAX_NAME - 1);
                strncpy(STATE.gaps[STATE.gap_count].area, rdesc, RGG_MAX_AREA - 1);
                STATE.gaps[STATE.gap_count].covered = 0;
                STATE.gap_count++;
            }
        }
    }
    mysql_free_result(res_rules);
    return 1;
}

/* ===== UNIT INTERFACE ===== */

int RuleGapGraph_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    strcpy(STATE.host, "localhost");
    strcpy(STATE.user, "root");
    STATE.port = 0;
    strcpy(STATE.socket, "/tmp/mysql.sock");
    return 1;
}

int RuleGapGraph_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) {
        return BclResult_Err(bcl_out, out_sz, 1, "not initialized");
    }

    /* ---- build ---- */
    if (strcmp(cmd, "build") == 0) {
        if (!BuildGapGraph()) {
            return BclResult_Err(bcl_out, out_sz, 2, STATE.last_error[0] ? STATE.last_error : "build failed");
        }
        char body[RGG_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@GAPS]{%d}[@COVERED]{%d}", STATE.gap_count, STATE.covered_count);
        for (int i = 0; i < STATE.gap_count && offset < (int)sizeof(body) - 256; i++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@GAP]{[@RULE]{%s}[@AREA]{%s}}",
                STATE.gaps[i].rule, STATE.gaps[i].area);
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- gaps (list uncovered rule areas) ---- */
    if (strcmp(cmd, "gaps") == 0) {
        char body[RGG_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@GAPS]{%d}", STATE.gap_count);
        for (int i = 0; i < STATE.gap_count && offset < (int)sizeof(body) - 256; i++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@GAP]{[@RULE]{%s}[@AREA]{%s}}",
                STATE.gaps[i].rule, STATE.gaps[i].area);
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- covered (list covered areas) ---- */
    if (strcmp(cmd, "covered") == 0) {
        char body[RGG_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@COVERED]{%d}", STATE.covered_count);
        for (int i = 0; i < STATE.covered_count && offset < (int)sizeof(body) - 256; i++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@COVERED_ENTRY]{[@RULE]{%s}[@AREA]{%s}}",
                STATE.covered[i].rule, STATE.covered[i].area);
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- read_state ---- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@GAP_COUNT]{%d}[@COVERED_COUNT]{%d}[@CONNECTED]{%d}[@LAST_ERROR]{%s}",
            STATE.initialized, STATE.gap_count, STATE.covered_count,
            STATE.connected, STATE.last_error[0] ? STATE.last_error : "none");
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

int RuleGapGraph_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    STATE.gap_count = 0;
    STATE.covered_count = 0;
    return 1;
}

const char * RuleGapGraph_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "RuleGapGraph: initialized=%d gaps=%d covered=%d connected=%d",
        STATE.initialized, STATE.gap_count, STATE.covered_count, STATE.connected);
    return buf;
}
