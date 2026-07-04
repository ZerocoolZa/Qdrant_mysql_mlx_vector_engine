//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_rule_cluster_graph.c" date="2026-07-04" author="devin" session_id="bcl-vsstyle-units" context="BCL unit for clustering rules by keyword similarity. Source: core/Dom_Vsstyle/vbs_rule_cluster_graph.py. Commands: build, clusters, cluster, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_rule_cluster_graph.c" domain="bcl_units" authority="RuleClusterGraph"}
//[@SUMMARY]{summary="Rule cluster graph. Clusters rules by keyword similarity in description. Commands: build, clusters, cluster, read_state, set_config."}
//[@CLASS]{class="RuleClusterGraph" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Build" type="command"}
//[@METHOD]{method="Clusters" type="query"}
//[@METHOD]{method="Cluster" type="query"}

#include "bcl_toolstack.h"
#include <mysql.h>
#include <ctype.h>

/* ===== DIM BLOCK ===== */

#define RCG_MAX_CLUSTERS  64
#define RCG_MAX_RULES     512
#define RCG_MAX_BODY      16384
#define RCG_MAX_NAME      128
#define RCG_MAX_KEYWORD   64
#define RCG_MAX_MEMBERS   64

typedef struct {
    char name[RCG_MAX_NAME];
    char description[RCG_MAX_NAME];
} RuleRec;

typedef struct {
    char keyword[RCG_MAX_KEYWORD];
    int  member_count;
    char members[RCG_MAX_MEMBERS][RCG_MAX_NAME];
} ClusterRec;

static struct {
    int         initialized;
    int         rule_count;
    int         cluster_count;
    RuleRec     rules[RCG_MAX_RULES];
    ClusterRec  clusters[RCG_MAX_CLUSTERS];
    int         connected;
    MYSQL      *conn;
    char        host[256];
    char        user[64];
    char        pass[128];
    char        socket[256];
    int         port;
    char        last_error[256];
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

/* Lowercase + alphabetic-only normalize of a word into out (size out_sz).
   Returns length written. */
static int NormalizeWord(const char *in, char *out, size_t out_sz) {
    size_t n = 0;
    while (*in && n + 1 < out_sz) {
        char c = *in++;
        if (isalpha((unsigned char)c)) {
            out[n++] = (char)tolower((unsigned char)c);
        } else if (c == '_' || c == '-') {
            out[n++] = '_';
        }
    }
    out[n] = '\0';
    return (int)n;
}

/* Extract the first distinctive keyword (len >= 5) from description. */
static int FirstKeyword(const char *desc, char *out, size_t out_sz) {
    const char *p = desc;
    while (*p) {
        while (*p && !isalpha((unsigned char)*p)) p++;
        const char *start = p;
        while (*p && (isalpha((unsigned char)*p) || *p == '_' || *p == '-')) p++;
        int len = (int)(p - start);
        if (len >= 5) {
            char word[RCG_MAX_KEYWORD];
            int wl = NormalizeWord(start, word, sizeof(word));
            if (wl >= 5) {
                strncpy(out, word, out_sz - 1);
                out[out_sz - 1] = '\0';
                return 1;
            }
        }
    }
    return 0;
}

/* Find or create a cluster by keyword. Returns cluster index, -1 if full. */
static int FindOrCreateCluster(const char *keyword) {
    for (int i = 0; i < STATE.cluster_count; i++) {
        if (strcmp(STATE.clusters[i].keyword, keyword) == 0) {
            return i;
        }
    }
    if (STATE.cluster_count >= RCG_MAX_CLUSTERS) {
        return -1;
    }
    strncpy(STATE.clusters[STATE.cluster_count].keyword, keyword, RCG_MAX_KEYWORD - 1);
    STATE.clusters[STATE.cluster_count].keyword[RCG_MAX_KEYWORD - 1] = '\0';
    STATE.clusters[STATE.cluster_count].member_count = 0;
    return STATE.cluster_count++;
}

/* Build clusters from MySQL vb_shared.rules: group rules by shared
   distinctive keyword in description. */
static int BuildClusters(void) {
    EnsureConnected();
    if (!STATE.connected) {
        return 0;
    }
    const char *q = "SELECT rule, LEFT(description, 500) FROM rules ORDER BY rule LIMIT 512";
    if (mysql_query(STATE.conn, q)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "%s", mysql_error(STATE.conn));
        return 0;
    }
    MYSQL_RES *res = mysql_store_result(STATE.conn);
    if (!res) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "no result set");
        return 0;
    }
    STATE.rule_count = 0;
    STATE.cluster_count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) && STATE.rule_count < RCG_MAX_RULES) {
        const char *rname = row[0] ? row[0] : "";
        const char *rdesc = row[1] ? row[1] : "";
        strncpy(STATE.rules[STATE.rule_count].name, rname, RCG_MAX_NAME - 1);
        STATE.rules[STATE.rule_count].name[RCG_MAX_NAME - 1] = '\0';
        strncpy(STATE.rules[STATE.rule_count].description, rdesc, RCG_MAX_NAME - 1);
        STATE.rules[STATE.rule_count].description[RCG_MAX_NAME - 1] = '\0';
        STATE.rule_count++;
        char kw[RCG_MAX_KEYWORD];
        if (!FirstKeyword(rdesc, kw, sizeof(kw))) {
            strncpy(kw, "general", sizeof(kw) - 1);
            kw[sizeof(kw) - 1] = '\0';
        }
        int idx = FindOrCreateCluster(kw);
        if (idx < 0) continue;
        if (STATE.clusters[idx].member_count < RCG_MAX_MEMBERS) {
            strncpy(STATE.clusters[idx].members[STATE.clusters[idx].member_count],
                rname, RCG_MAX_NAME - 1);
            STATE.clusters[idx].members[STATE.clusters[idx].member_count][RCG_MAX_NAME - 1] = '\0';
            STATE.clusters[idx].member_count++;
        }
    }
    mysql_free_result(res);
    return 1;
}

/* ===== UNIT INTERFACE ===== */

int RuleClusterGraph_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    strcpy(STATE.host, "localhost");
    strcpy(STATE.user, "root");
    STATE.port = 0;
    strcpy(STATE.socket, "/tmp/mysql.sock");
    return 1;
}

int RuleClusterGraph_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) {
        return BclResult_Err(bcl_out, out_sz, 1, "not initialized");
    }

    /* ---- build ---- */
    if (strcmp(cmd, "build") == 0) {
        if (!BuildClusters()) {
            return BclResult_Err(bcl_out, out_sz, 2, STATE.last_error[0] ? STATE.last_error : "build failed");
        }
        char body[RCG_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@CLUSTERS]{%d}", STATE.cluster_count);
        for (int i = 0; i < STATE.cluster_count && offset < (int)sizeof(body) - 512; i++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@CLUSTER]{[@ID]{%d}[@NAME]{%s}[@MEMBERS]{%d}",
                i, STATE.clusters[i].keyword, STATE.clusters[i].member_count);
            for (int m = 0; m < STATE.clusters[i].member_count && offset < (int)sizeof(body) - 256; m++) {
                offset += snprintf(body + offset, sizeof(body) - offset,
                    "[@RULE]{%s}", STATE.clusters[i].members[m]);
            }
            offset += snprintf(body + offset, sizeof(body) - offset, "}");
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- clusters (list all clusters) ---- */
    if (strcmp(cmd, "clusters") == 0) {
        char body[RCG_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@CLUSTERS]{%d}", STATE.cluster_count);
        for (int i = 0; i < STATE.cluster_count && offset < (int)sizeof(body) - 512; i++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@CLUSTER]{[@ID]{%d}[@NAME]{%s}[@MEMBERS]{%d}",
                i, STATE.clusters[i].keyword, STATE.clusters[i].member_count);
            for (int m = 0; m < STATE.clusters[i].member_count && offset < (int)sizeof(body) - 256; m++) {
                offset += snprintf(body + offset, sizeof(body) - offset,
                    "[@RULE]{%s}", STATE.clusters[i].members[m]);
            }
            offset += snprintf(body + offset, sizeof(body) - offset, "}");
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- cluster (get one cluster by id) ---- */
    if (strcmp(cmd, "cluster") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char id_str[32];
        BclParser_Extract(&parse, "ID", id_str, sizeof(id_str));
        BclParser_Free(&parse);
        int id = id_str[0] ? atoi(id_str) : -1;
        if (id < 0 || id >= STATE.cluster_count) {
            return BclResult_Err(bcl_out, out_sz, 3, "invalid cluster id");
        }
        char body[RCG_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@CLUSTER]{[@ID]{%d}[@NAME]{%s}[@MEMBERS]{%d}",
            id, STATE.clusters[id].keyword, STATE.clusters[id].member_count);
        for (int m = 0; m < STATE.clusters[id].member_count && offset < (int)sizeof(body) - 256; m++) {
            offset += snprintf(body + offset, sizeof(body) - offset,
                "[@RULE]{%s}", STATE.clusters[id].members[m]);
        }
        offset += snprintf(body + offset, sizeof(body) - offset, "}");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- read_state ---- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@RULE_COUNT]{%d}[@CLUSTER_COUNT]{%d}[@CONNECTED]{%d}[@LAST_ERROR]{%s}",
            STATE.initialized, STATE.rule_count, STATE.cluster_count,
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

int RuleClusterGraph_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    STATE.rule_count = 0;
    STATE.cluster_count = 0;
    return 1;
}

const char * RuleClusterGraph_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "RuleClusterGraph: initialized=%d rules=%d clusters=%d connected=%d",
        STATE.initialized, STATE.rule_count, STATE.cluster_count, STATE.connected);
    return buf;
}
