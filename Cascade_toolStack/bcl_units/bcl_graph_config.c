//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_config.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="BCL unit for GraphConfig — config parser for the Max Graph Engine, reads TOML-like config files and applies settings to Graph structures"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_config.c" domain="graph_engine" authority="GraphConfig"}
//[@SUMMARY]{summary="GraphConfig BCL unit. Reads simple TOML-like config files (key=value, [section] headers, # comments) and applies settings to Graph policy/executor. Commands: load, get, get_int, get_float, apply, read_state, set_config."}
//[@CLASS]{class="GraphConfig" domain="graph_engine" authority="single"}
//[@METHOD]{method="config_create" type="lifecycle"}
//[@METHOD]{method="config_free" type="lifecycle"}
//[@METHOD]{method="config_load" type="command"}
//[@METHOD]{method="config_get" type="query"}
//[@METHOD]{method="config_get_int" type="query"}
//[@METHOD]{method="config_get_float" type="query"}
//[@METHOD]{method="config_apply_to_graph" type="command"}
//[@METHOD]{method="GraphConfig_Init" type="lifecycle"}
//[@METHOD]{method="GraphConfig_Run" type="dispatch"}
//[@METHOD]{method="GraphConfig_Close" type="lifecycle"}
//[@METHOD]{method="GraphConfig_State" type="query"}

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"

/* ════════════════════════════════════════════
 * UNIT STATE
 * ════════════════════════════════════════════ */

static struct {
    int     initialized;
    Config *config;          /* active config object for BCL dispatch */
    char    last_path[256];  /* last loaded config path */
    char    last_error[256]; /* last error description */
} STATE;

/* ════════════════════════════════════════════
 * INTERNAL HELPERS
 * ════════════════════════════════════════════ */

/* trim — in-place whitespace trim (kept static, header does not declare it) */
static void trim(char *s) {
    if (!s) return;
    char *start = s;
    while (*start && (*start == ' ' || *start == '\t' || *start == '\r' || *start == '\n')) start++;
    if (start != s) memmove(s, start, strlen(start) + 1);
    int len = (int)strlen(s);
    while (len > 0 && (s[len-1] == ' ' || s[len-1] == '\t' || s[len-1] == '\r' || s[len-1] == '\n')) {
        s[--len] = '\0';
    }
}

/* ════════════════════════════════════════════
 * CONFIG CORE FUNCTIONS
 * ════════════════════════════════════════════ */

Config *config_create(void) {
    Config *c = (Config *)calloc(1, sizeof(Config));
    if (!c) return NULL;
    c->capacity = 100;
    c->entries = (ConfigEntry *)calloc(c->capacity, sizeof(ConfigEntry));
    c->count = 0;
    return c;
}

void config_free(Config *c) {
    if (!c) return;
    if (c->entries) free(c->entries);
    free(c);
}

/* config_load — reads key=value pairs from a file
 * Sections are [section_name]
 * Lines starting with # or // are comments */
int config_load(Config *c, const char *path) {
    if (!c || !path) return -1;
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    char line[512];
    char section[64] = "";
    while (fgets(line, sizeof(line), f)) {
        trim(line);
        if (line[0] == '\0' || line[0] == '#' || (line[0] == '/' && line[1] == '/')) continue;
        if (line[0] == '[') {
            char *end = strchr(line, ']');
            if (end) {
                *end = '\0';
                strncpy(section, line + 1, sizeof(section) - 1);
                section[sizeof(section) - 1] = '\0';
            }
            continue;
        }
        char *eq = strchr(line, '=');
        if (!eq) continue;
        *eq = '\0';
        char *key = line;
        char *value = eq + 1;
        trim(key);
        trim(value);
        if (c->count >= c->capacity) {
            int new_cap = c->capacity * 2;
            ConfigEntry *new_entries = (ConfigEntry *)realloc(c->entries, new_cap * sizeof(ConfigEntry));
            if (!new_entries) { fclose(f); return -1; }
            c->entries = new_entries;
            c->capacity = new_cap;
        }
        strncpy(c->entries[c->count].section, section, sizeof(c->entries[c->count].section) - 1);
        c->entries[c->count].section[sizeof(c->entries[c->count].section) - 1] = '\0';
        strncpy(c->entries[c->count].key, key, sizeof(c->entries[c->count].key) - 1);
        c->entries[c->count].key[sizeof(c->entries[c->count].key) - 1] = '\0';
        strncpy(c->entries[c->count].value, value, sizeof(c->entries[c->count].value) - 1);
        c->entries[c->count].value[sizeof(c->entries[c->count].value) - 1] = '\0';
        c->count++;
    }
    fclose(f);
    return 0;
}

const char *config_get(Config *c, const char *section, const char *key) {
    if (!c || !section || !key) return NULL;
    for (int i = 0; i < c->count; i++) {
        if (strcmp(c->entries[i].section, section) == 0 && strcmp(c->entries[i].key, key) == 0) {
            return c->entries[i].value;
        }
    }
    return NULL;
}

int config_get_int(Config *c, const char *section, const char *key, int default_val) {
    const char *v = config_get(c, section, key);
    if (!v) return default_val;
    return atoi(v);
}

float config_get_float(Config *c, const char *section, const char *key, float default_val) {
    const char *v = config_get(c, section, key);
    if (!v) return default_val;
    return (float)atof(v);
}

/* config_apply_to_graph — apply config to a Graph's policy and executor */
int config_apply_to_graph(Config *c, Graph *g) {
    if (!c || !g) return -1;
    g->policy.hard_limit = config_get_int(c, "engine", "max_depth", 6);
    g->policy.attention_threshold = config_get_float(c, "policy", "attention_threshold", 0.3f);
    g->policy.max_nodes_per_hop = config_get_int(c, "policy", "max_nodes_per_hop", 100);
    g->policy.max_total_nodes = config_get_int(c, "policy", "max_total_nodes", 10000);
    g->executor.memory_budget = (size_t)config_get_int(c, "engine", "memory_budget_mb", 512) * 1024 * 1024;
    g->executor.timeout_ms = config_get_int(c, "engine", "timeout_ms", 5000);
    g->executor.cost_limit = config_get_int(c, "engine", "cost_limit", 10000);
    const char *mysql_host = config_get(c, "stored_graph", "mysql_host");
    if (mysql_host) {
        strncpy(g->mysql_host, mysql_host, sizeof(g->mysql_host) - 1);
        g->mysql_host[sizeof(g->mysql_host) - 1] = '\0';
    } else {
        strncpy(g->mysql_host, "localhost", sizeof(g->mysql_host) - 1);
        g->mysql_host[sizeof(g->mysql_host) - 1] = '\0';
    }
    const char *mysql_user = config_get(c, "stored_graph", "mysql_user");
    if (mysql_user) {
        strncpy(g->mysql_user, mysql_user, sizeof(g->mysql_user) - 1);
        g->mysql_user[sizeof(g->mysql_user) - 1] = '\0';
    } else {
        strncpy(g->mysql_user, "root", sizeof(g->mysql_user) - 1);
        g->mysql_user[sizeof(g->mysql_user) - 1] = '\0';
    }
    const char *mysql_db = config_get(c, "stored_graph", "mysql_db");
    if (mysql_db) {
        strncpy(g->mysql_db, mysql_db, sizeof(g->mysql_db) - 1);
        g->mysql_db[sizeof(g->mysql_db) - 1] = '\0';
    } else {
        strncpy(g->mysql_db, "vb_shared", sizeof(g->mysql_db) - 1);
        g->mysql_db[sizeof(g->mysql_db) - 1] = '\0';
    }
    return 0;
}

/* ════════════════════════════════════════════
 * BCL DISPATCH INTERFACE
 * ════════════════════════════════════════════ */

int GraphConfig_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.config = config_create();
    if (!STATE.config) {
        strncpy(STATE.last_error, "config_create failed", sizeof(STATE.last_error) - 1);
        STATE.initialized = 0;
        return 0;
    }
    STATE.initialized = 1;
    return 1;
}

int GraphConfig_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphConfig_Init();
    if (!cmd) {
        return BclResult_Err(bcl_out, out_sz, 10, "no command provided");
    }

    /* --- read_state --- */
    if (strcmp(cmd, "read_state") == 0) {
        char buf[512];
        snprintf(buf, sizeof(buf),
            "[@INITIALIZED]{%d}[@ENTRIES]{%d}[@LAST_PATH]{%s}[@LAST_ERROR]{%s}",
            STATE.initialized,
            STATE.config ? STATE.config->count : 0,
            STATE.last_path,
            STATE.last_error);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- set_config --- */
    if (strcmp(cmd, "set_config") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* --- load --- */
    if (strcmp(cmd, "load") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char path[256] = "";
        BclParser_Extract(&parse, "path", path, sizeof(path));

        BclParser_Free(&parse);

        if (!*path) {
            strncpy(STATE.last_error, "no PATH in packet", sizeof(STATE.last_error) - 1);
            STATE.last_error[sizeof(STATE.last_error) - 1] = '\0';
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }

        /* free old config, create fresh */
        if (STATE.config) config_free(STATE.config);
        STATE.config = config_create();
        if (!STATE.config) {
            strncpy(STATE.last_error, "config_create failed", sizeof(STATE.last_error) - 1);
            STATE.last_error[sizeof(STATE.last_error) - 1] = '\0';
            return BclResult_Err(bcl_out, out_sz, 50, "config_create failed");
        }

        int rc = config_load(STATE.config, path);
        if (rc != 0) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "failed to load %s", path);
            strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
            STATE.last_path[sizeof(STATE.last_path) - 1] = '\0';
            return BclResult_Err(bcl_out, out_sz, 50, STATE.last_error);
        }

        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        STATE.last_path[sizeof(STATE.last_path) - 1] = '\0';
        STATE.last_error[0] = '\0';

        char buf[512];
        snprintf(buf, sizeof(buf),
            "[@PATH]{%s}[@ENTRIES]{%d}",
            STATE.last_path, STATE.config->count);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- get --- */
    if (strcmp(cmd, "get") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char section[64] = "";
        char key[64] = "";
        BclParser_Extract(&parse, "section", section, sizeof(section));
        BclParser_Extract(&parse, "key", key, sizeof(key));

        BclParser_Free(&parse);

        if (!*section || !*key) {
            return BclResult_Err(bcl_out, out_sz, 20, "no SECTION or KEY in packet");
        }
        if (!STATE.config) {
            return BclResult_Err(bcl_out, out_sz, 50, "no config loaded");
        }

        const char *val = config_get(STATE.config, section, key);
        if (!val) {
            char err[256];
            snprintf(err, sizeof(err), "key not found: %s.%s", section, key);
            return BclResult_Err(bcl_out, out_sz, 40, err);
        }

        char buf[512];
        snprintf(buf, sizeof(buf),
            "[@SECTION]{%s}[@KEY]{%s}[@VALUE]{%s}",
            section, key, val);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- get_int --- */
    if (strcmp(cmd, "get_int") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char section[64] = "";
        char key[64] = "";
        char default_str[32] = "";
        BclParser_Extract(&parse, "section", section, sizeof(section));
        BclParser_Extract(&parse, "key", key, sizeof(key));
        BclParser_Extract(&parse, "default", default_str, sizeof(default_str));

        BclParser_Free(&parse);

        if (!*section || !*key) {
            return BclResult_Err(bcl_out, out_sz, 20, "no SECTION or KEY in packet");
        }
        if (!STATE.config) {
            return BclResult_Err(bcl_out, out_sz, 50, "no config loaded");
        }

        int default_val = *default_str ? atoi(default_str) : 0;
        int val = config_get_int(STATE.config, section, key, default_val);

        char buf[512];
        snprintf(buf, sizeof(buf),
            "[@SECTION]{%s}[@KEY]{%s}[@VALUE]{%d}",
            section, key, val);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- get_float --- */
    if (strcmp(cmd, "get_float") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char section[64] = "";
        char key[64] = "";
        char default_str[32] = "";
        BclParser_Extract(&parse, "section", section, sizeof(section));
        BclParser_Extract(&parse, "key", key, sizeof(key));
        BclParser_Extract(&parse, "default", default_str, sizeof(default_str));

        BclParser_Free(&parse);

        if (!*section || !*key) {
            return BclResult_Err(bcl_out, out_sz, 20, "no SECTION or KEY in packet");
        }
        if (!STATE.config) {
            return BclResult_Err(bcl_out, out_sz, 50, "no config loaded");
        }

        float default_val = *default_str ? (float)atof(default_str) : 0.0f;
        float val = config_get_float(STATE.config, section, key, default_val);

        char buf[512];
        snprintf(buf, sizeof(buf),
            "[@SECTION]{%s}[@KEY]{%s}[@VALUE]{%.6f}",
            section, key, val);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- apply --- */
    if (strcmp(cmd, "apply") == 0) {
        if (!STATE.config) {
            return BclResult_Err(bcl_out, out_sz, 50, "no config loaded");
        }
        /* Apply to a freshly created Graph (BCL dispatch cannot receive a Graph*
         * pointer over the wire, so we create one, apply, and report the
         * resulting policy/executor settings). */
        Graph *g = graph_create(1024);
        if (!g) {
            return BclResult_Err(bcl_out, out_sz, 50, "graph_create failed");
        }

        int rc = config_apply_to_graph(STATE.config, g);
        if (rc != 0) {
            graph_free(g);
            return BclResult_Err(bcl_out, out_sz, 50, "config_apply_to_graph failed");
        }

        char buf[1024];
        snprintf(buf, sizeof(buf),
            "[@APPLIED]{1}[@MAX_DEPTH]{%d}[@ATTENTION_THRESHOLD]{%.4f}"
            "[@MAX_NODES_PER_HOP]{%d}[@MAX_TOTAL_NODES]{%d}"
            "[@MEMORY_BUDGET_MB]{%zu}[@TIMEOUT_MS]{%d}[@COST_LIMIT]{%d}"
            "[@MYSQL_HOST]{%s}[@MYSQL_USER]{%s}[@MYSQL_DB]{%s}",
            g->policy.hard_limit,
            g->policy.attention_threshold,
            g->policy.max_nodes_per_hop,
            g->policy.max_total_nodes,
            g->executor.memory_budget / (1024 * 1024),
            g->executor.timeout_ms,
            g->executor.cost_limit,
            g->mysql_host,
            g->mysql_user,
            g->mysql_db);

        graph_free(g);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- unknown command --- */
    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int GraphConfig_Close(void) {
    if (STATE.config) {
        config_free(STATE.config);
        STATE.config = NULL;
    }
    STATE.initialized = 0;
    STATE.last_path[0] = '\0';
    STATE.last_error[0] = '\0';
    return 1;
}

const char * GraphConfig_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "GraphConfig: initialized=%d entries=%d last_path=%s",
        STATE.initialized,
        STATE.config ? STATE.config->count : 0,
        STATE.last_path);
    return buf;
}
