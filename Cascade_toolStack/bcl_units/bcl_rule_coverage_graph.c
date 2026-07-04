//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_rule_coverage_graph.c" date="2026-07-04" author="devin" session_id="bcl-vsstyle-units" context="BCL unit for rule coverage graph — maps rules to code entities. Source: core/Dom_Vsstyle/vbs_rule_coverage_graph.py. Commands: build, coverage, uncovered, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_rule_coverage_graph.c" domain="bcl_units" authority="RuleCoverageGraph"}
//[@SUMMARY]{summary="Rule coverage graph. Maps rules to code entities, finds uncovered entities. Commands: build, coverage, uncovered, read_state, set_config."}
//[@CLASS]{class="RuleCoverageGraph" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Build" type="command"}
//[@METHOD]{method="Coverage" type="query"}
//[@METHOD]{method="Uncovered" type="query"}

#include "bcl_toolstack.h"
#include <mysql.h>
#include <ctype.h>

/* ===== DIM BLOCK ===== */

#define RCVG_MAX_MAPPINGS  512
#define RCVG_MAX_BODY      16384
#define RCVG_MAX_NAME      128

typedef struct {
    char rule[RCVG_MAX_NAME];
    char entity[RCVG_MAX_NAME];
} CoverageMap;

static struct {
    int           initialized;
    int           mapping_count;
    int           uncovered_count;
    CoverageMap   mappings[RCVG_MAX_MAPPINGS];
    char          uncovered[RCVG_MAX_MAPPINGS][RCVG_MAX_NAME];
    int           connected;
    MYSQL        *conn;
    char          host[256];
    char          user[64];
    char          pass[128];
    char          socket[256];
    int           port;
    char          last_error[256];
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

/* Check whether a rule name appears as a substring of a class name.
   Returns 1 if matched, 0 otherwise. */
static int RuleMatchesEntity(const char *rule, const char *entity) {
    if (!rule[0] || !entity[0]) return 0;
    /* case-insensitive substring match */
    const char *r = rule;
    while (*r) {
        const char *e = entity;
        const char *rr = r;
        while (*rr && *e && tolower((unsigned char)*rr) == tolower((unsigned char)*e)) {
            rr++;
            e++;
        }
        if (!*rr) return 1;
        r++;
    }
    return 0;
}

/* Build coverage from MySQL vb_shared.rules + vb_code_test.vb_classes.
   Maps each rule to matching code entities (class_name). Entities with
   no matching rule are collected as uncovered. */
static int BuildCoverage(void) {
    EnsureConnected();
    if (!STATE.connected) {
        return 0;
    }
    /* Load rules */
    const char *q_rules = "SELECT rule FROM rules ORDER BY rule LIMIT 512";
    if (mysql_query(STATE.conn, q_rules)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "%s", mysql_error(STATE.conn));
        return 0;
    }
    MYSQL_RES *res_rules = mysql_store_result(STATE.conn);
    if (!res_rules) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "no rules result set");
        return 0;
    }
    char rules[RCVG_MAX_MAPPINGS][RCVG_MAX_NAME];
    int rule_count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res_rules)) && rule_count < RCVG_MAX_MAPPINGS) {
        strncpy(rules[rule_count], row[0] ? row[0] : "", RCVG_MAX_NAME - 1);
        rules[rule_count][RCVG_MAX_NAME - 1] = '\0';
        rule_count++;
    }
    mysql_free_result(res_rules);

    /* Load vb_classes from vb_code_test */
    if (mysql_select_db(STATE.conn, "vb_code_test")) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "%s", mysql_error(STATE.conn));
        return 0;
    }
    const char *q_classes = "SELECT class_name FROM vb_classes ORDER BY class_name LIMIT 2048";
    if (mysql_query(STATE.conn, q_classes)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "%s", mysql_error(STATE.conn));
        mysql_select_db(STATE.conn, "vb_shared");
        return 0;
    }
    MYSQL_RES *res_classes = mysql_store_result(STATE.conn);
    if (!res_classes) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "no classes result set");
        mysql_select_db(STATE.conn, "vb_shared");
        return 0;
    }

    STATE.mapping_count = 0;
    STATE.uncovered_count = 0;
    char covered_flags[RCVG_MAX_MAPPINGS];
    for (int i = 0; i < RCVG_MAX_MAPPINGS; i++) covered_flags[i] = 0;

    while ((row = mysql_fetch_row(res_classes))) {
        const char *cname = row[0] ? row[0] : "";
        int matched = 0;
        for (int i = 0; i < rule_count; i++) {
            if (RuleMatchesEntity(rules[i], cname)) {
                if (STATE.mapping_count < RCVG_MAX_MAPPINGS) {
                    strncpy(STATE.mappings[STATE.mapping_count].rule, rules[i], RCVG_MAX_NAME - 1);
                    STATE.mappings[STATE.mapping_count].rule[RCVG_MAX_NAME - 1] = '\0';
                    strncpy(STATE.mappings[STATE.mapping_count].entity, cname, RCVG_MAX_NAME - 1);
                    STATE.mappings[STATE.mapping_count].entity[RCVG_MAX_NAME - 1] = '\0';
                    STATE.mapping_count++;
                }
                covered_flags[i] = 1;
                matched = 1;
            }
        }
        if (!matched) {
            if (STATE.uncovered_count < RCVG_MAX_MAPPINGS) {
                strncpy(STATE.uncovered[STATE.uncovered_count], cname, RCVG_MAX_NAME - 1);
                STATE.uncovered[STATE.uncovered_count][RCVG_MAX_NAME - 1] = '\0';
                STATE.uncovered_count++;
            }
        }
    }
    mysql_free_result(res_classes);
    mysql_select_db(STATE.conn, "vb_shared");
    return 1;
}

/* ===== UNIT INTERFACE ===== */

int RuleCoverageGraph_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    strcpy(STATE.host, "localhost");
    strcpy(STATE.user, "root");
    STATE.port = 0;
    strcpy(STATE.socket, "/tmp/mysql.sock");
    return 1;
}

int RuleCoverageGraph_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) {
        return BclResult_Err(bcl_out, out_sz, 1, "not initialized");
    }

    /* ---- build ---- */
    if (strcmp(cmd, "build") == 0) {
        if (!BuildCoverage()) {
            return BclResult_Err(bcl_out, out_sz, 2, STATE.last_error[0] ? STATE.last_error : "build failed");
        }
        char body[RCVG_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@COVERED]{%d}[@UNCOVERED]{%d}", STATE.mapping_count, STATE.uncovered_count);
        for (int i = 0; i < STATE.mapping_count && offset < (int)sizeof(body) - 256; i++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@MAPPING]{[@RULE]{%s}[@ENTITY]{%s}}",
                STATE.mappings[i].rule, STATE.mappings[i].entity);
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- coverage (list rule->entity mappings) ---- */
    if (strcmp(cmd, "coverage") == 0) {
        char body[RCVG_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@COVERED]{%d}", STATE.mapping_count);
        for (int i = 0; i < STATE.mapping_count && offset < (int)sizeof(body) - 256; i++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@MAPPING]{[@RULE]{%s}[@ENTITY]{%s}}",
                STATE.mappings[i].rule, STATE.mappings[i].entity);
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- uncovered (entities with no rules) ---- */
    if (strcmp(cmd, "uncovered") == 0) {
        char body[RCVG_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@UNCOVERED]{%d}", STATE.uncovered_count);
        for (int i = 0; i < STATE.uncovered_count && offset < (int)sizeof(body) - 256; i++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@ENTITY]{%s}", STATE.uncovered[i]);
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- read_state ---- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@MAPPING_COUNT]{%d}[@UNCOVERED_COUNT]{%d}[@CONNECTED]{%d}[@LAST_ERROR]{%s}",
            STATE.initialized, STATE.mapping_count, STATE.uncovered_count,
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

int RuleCoverageGraph_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    STATE.mapping_count = 0;
    STATE.uncovered_count = 0;
    return 1;
}

const char * RuleCoverageGraph_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "RuleCoverageGraph: initialized=%d mappings=%d uncovered=%d connected=%d",
        STATE.initialized, STATE.mapping_count, STATE.uncovered_count, STATE.connected);
    return buf;
}
