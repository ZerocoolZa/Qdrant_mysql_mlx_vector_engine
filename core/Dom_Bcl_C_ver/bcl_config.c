//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_config.c" date="2026-06-29" author="Devin" session_id="bcl-c-central-db" context="Runtime config reader for BCL C engine — reads bcl_config.json, provides db_path/backend_type/max_nodes to all units. Matches Python BclConfig.py."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_config.c" domain="bcl_c_engine" authority="BclConfig"}
//[@SUMMARY]{summary="Runtime config reader — reads bcl_config.json, provides config_get() for db_path, backend_type, max_nodes, compile flags. Backend selectable: sqlite | mysql."}
//[@CLASS]{class="BclConfig" domain="bcl_c_engine" authority="single"}
//[@METHOD]{method="config_load" type="command"}
//[@METHOD]{method="config_get" type="command"}
//[@METHOD]{method="config_get_int" type="command"}
//[@METHOD]{method="config_set" type="command"}
//[@METHOD]{method="config_save" type="command"}
//[@METHOD]{method="config_free" type="command"}
//[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Runtime config for C engine. Reads JSON, provides config_get. Backend selectable.>][@todos<none>]}

/*
 * bcl_config.c — Runtime config reader for BCL C engine.
 *
 * Reads bcl_config.json (same format as Python BclConfig.py writes).
 * Provides config_get() / config_get_int() for all other C units.
 *
 * Backend selectable:
 *   "sqlite" → GraphStore uses SQLite local file
 *   "mysql"  → GraphStore uses MySQL vb_shared
 *
 * Usage:
 *   BclConfig cfg;
 *   config_load(&cfg, "bcl_config.json");
 *   const char *backend = config_get(&cfg, "backend");
 *   const char *db_path = config_get(&cfg, "sqlite.path");
 *   config_free(&cfg);
 *
 * Or use the global singleton:
 *   config_init_global("bcl_config.json");
 *   const char *v = config_get_global("backend");
 */

#include "bcl_engine.h"
#include <json-c/json.h>
#include <unistd.h>
#include <sys/stat.h>

/* ════════════════════════════════════════════
 * CONFIG STRUCTURE
 * ════════════════════════════════════════════ */

typedef struct {
    char config_path[VBAST_MAX_LINE];
    json_object *root;           /* parsed JSON tree */
    int loaded;                  /* 1 if config loaded successfully */
    char backend[32];            /* "sqlite" or "mysql" */
    char db_path[VBAST_MAX_LINE];
    char db_host[128];
    char db_user[64];
    char db_name[128];
    char db_table[128];
    int  db_port;
    char domain[64];
    char binary_name[128];
    char output_dir[VBAST_MAX_LINE];
} BclConfig;

/* Global singleton — most C units use this */
static BclConfig g_config = {0};

/* ════════════════════════════════════════════
 * HELPERS
 * ════════════════════════════════════════════ */

/* Get nested JSON value by dotted path: "sqlite.path" → root["sqlite"]["path"] */
static json_object *json_get_nested(json_object *root, const char *path) {
    if (!root || !path) return NULL;
    char buf[VBAST_MAX_LINE];
    strncpy(buf, path, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    json_object *current = root;
    char *token = strtok(buf, ".");
    while (token && current) {
        if (!json_object_object_get_ex(current, token, &current))
            return NULL;
        token = strtok(NULL, ".");
    }
    return current;
}

/* Detect default config path — same dir as binary or CWD */
static void default_config_path(char *out, size_t out_sz) {
    if (getcwd(out, out_sz)) {
        size_t len = strlen(out);
        snprintf(out + len, out_sz - len, "/bcl_config.json");
        return;
    }
    strncpy(out, "bcl_config.json", out_sz - 1);
    out[out_sz - 1] = '\0';
}

/* ════════════════════════════════════════════
 * CONFIG LOAD
 * ════════════════════════════════════════════ */

int config_load(void *cfg_v, const char *path) {
    BclConfig *cfg = (BclConfig *)cfg_v;
    if (!cfg) return 0;
    memset(cfg, 0, sizeof(BclConfig));

    if (path && *path) {
        strncpy(cfg->config_path, path, sizeof(cfg->config_path) - 1);
    } else {
        default_config_path(cfg->config_path, sizeof(cfg->config_path));
    }

    FILE *f = fopen(cfg->config_path, "r");
    if (!f) {
        /* Config file doesn't exist — use compiled-in defaults */
        strncpy(cfg->backend, "sqlite", sizeof(cfg->backend) - 1);
        strncpy(cfg->db_path, "bcl_c_engine.db", sizeof(cfg->db_path) - 1);
        strncpy(cfg->domain, "bcl_c_engine", sizeof(cfg->domain) - 1);
        strncpy(cfg->binary_name, "dom_graph_engine", sizeof(cfg->binary_name) - 1);
        cfg->db_port = 3306;
        cfg->loaded = 0;
        return 1;
    }

    struct stat st;
    fstat(fileno(f), &st);
    char *content = (char *)malloc(st.st_size + 1);
    if (!content) { fclose(f); return 0; }
    size_t nread = fread(content, 1, st.st_size, f);
    content[nread] = '\0';
    fclose(f);

    cfg->root = json_tokener_parse(content);
    free(content);

    if (!cfg->root) {
        strncpy(cfg->backend, "sqlite", sizeof(cfg->backend) - 1);
        cfg->loaded = 0;
        return 1;
    }

    cfg->loaded = 1;

    const char *backend = config_get(cfg, "backend");
    if (backend) strncpy(cfg->backend, backend, sizeof(cfg->backend) - 1);
    else strncpy(cfg->backend, "sqlite", sizeof(cfg->backend) - 1);

    const char *domain = config_get(cfg, "domain");
    if (domain) strncpy(cfg->domain, domain, sizeof(cfg->domain) - 1);
    else strncpy(cfg->domain, "bcl_c_engine", sizeof(cfg->domain) - 1);

    const char *bin = config_get(cfg, "binary_name");
    if (bin) strncpy(cfg->binary_name, bin, sizeof(cfg->binary_name) - 1);
    else strncpy(cfg->binary_name, "dom_graph_engine", sizeof(cfg->binary_name) - 1);

    const char *outdir = config_get(cfg, "output_dir");
    if (outdir) strncpy(cfg->output_dir, outdir, sizeof(cfg->output_dir) - 1);

    if (strcmp(cfg->backend, "mysql") == 0) {
        const char *host = config_get(cfg, "mysql.host");
        const char *user = config_get(cfg, "mysql.user");
        const char *db   = config_get(cfg, "mysql.database");
        const char *tbl  = config_get(cfg, "mysql.table");
        if (host) strncpy(cfg->db_host, host, sizeof(cfg->db_host) - 1);
        if (user) strncpy(cfg->db_user, user, sizeof(cfg->db_user) - 1);
        if (db)   strncpy(cfg->db_name, db, sizeof(cfg->db_name) - 1);
        if (tbl)  strncpy(cfg->db_table, tbl, sizeof(cfg->db_table) - 1);
        cfg->db_port = config_get_int(cfg, "mysql.port", 3306);
    } else {
        const char *path = config_get(cfg, "sqlite.path");
        const char *tbl  = config_get(cfg, "sqlite.table");
        if (path) strncpy(cfg->db_path, path, sizeof(cfg->db_path) - 1);
        else strncpy(cfg->db_path, "bcl_c_engine.db", sizeof(cfg->db_path) - 1);
        if (tbl) strncpy(cfg->db_table, tbl, sizeof(cfg->db_table) - 1);
        else strncpy(cfg->db_table, "c_classes", sizeof(cfg->db_table) - 1);
    }

    return 1;
}

/* ════════════════════════════════════════════
 * CONFIG GET
 * ════════════════════════════════════════════ */

const char *config_get(void *cfg_v, const char *key) {
    BclConfig *cfg = (BclConfig *)cfg_v;
    if (!cfg || !key) return NULL;
    if (!cfg->root) return NULL;
    json_object *val = json_get_nested(cfg->root, key);
    if (val && json_object_is_type(val, json_type_string))
        return json_object_get_string(val);
    return NULL;
}

int config_get_int(void *cfg_v, const char *key, int default_val) {
    BclConfig *cfg = (BclConfig *)cfg_v;
    if (!cfg || !key) return default_val;
    if (!cfg->root) return default_val;
    json_object *val = json_get_nested(cfg->root, key);
    if (val && json_object_is_type(val, json_type_int))
        return json_object_get_int(val);
    if (val && json_object_is_type(val, json_type_string))
        return atoi(json_object_get_string(val));
    return default_val;
}

/* ════════════════════════════════════════════
 * CONFIG SET
 * ════════════════════════════════════════════ */

int config_set(void *cfg_v, const char *key, const char *value) {
    BclConfig *cfg = (BclConfig *)cfg_v;
    if (!cfg || !key || !value) return 0;
    if (!cfg->root) {
        cfg->root = json_object_new_object();
        if (!cfg->root) return 0;
    }

    char buf[VBAST_MAX_LINE];
    strncpy(buf, key, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    char *last_dot = strrchr(buf, '.');
    json_object *parent = cfg->root;

    if (last_dot) {
        *last_dot = '\0';
        char *token = strtok(buf, ".");
        while (token) {
            json_object *child;
            if (!json_object_object_get_ex(parent, token, &child)) {
                child = json_object_new_object();
                json_object_object_add(parent, token, child);
            }
            parent = child;
            token = strtok(NULL, ".");
        }
        key = last_dot + 1;
    }

    json_object_object_add(parent, (char *)key, json_object_new_string(value));
    return 1;
}

/* ════════════════════════════════════════════
 * CONFIG SAVE
 * ════════════════════════════════════════════ */

int config_save(void *cfg_v, const char *path) {
    BclConfig *cfg = (BclConfig *)cfg_v;
    if (!cfg || !cfg->root) return 0;
    const char *save_path = (path && *path) ? path : cfg->config_path;
    FILE *f = fopen(save_path, "w");
    if (!f) return 0;
    const char *json_str = json_object_to_json_string_ext(cfg->root, JSON_C_TO_STRING_PRETTY);
    fputs(json_str, f);
    fputc('\n', f);
    fclose(f);
    return 1;
}

/* ════════════════════════════════════════════
 * CONFIG FREE
 * ════════════════════════════════════════════ */

void config_free(void *cfg_v) {
    BclConfig *cfg = (BclConfig *)cfg_v;
    if (cfg && cfg->root) {
        json_object_put(cfg->root);
        cfg->root = NULL;
    }
    if (cfg) cfg->loaded = 0;
}

/* ════════════════════════════════════════════
 * GLOBAL SINGLETON
 * ════════════════════════════════════════════ */

int config_init_global(const char *path) {
    return config_load(&g_config, path);
}

const char *config_get_global(const char *key) {
    return config_get(&g_config, key);
}

int config_get_global_int(const char *key, int default_val) {
    return config_get_int(&g_config, key, default_val);
}

const char *config_global_backend(void) {
    return g_config.backend;
}

const char *config_global_db_path(void) {
    if (strcmp(g_config.backend, "mysql") == 0)
        return g_config.db_name;
    return g_config.db_path;
}

const char *config_global_db_host(void) { return g_config.db_host; }
const char *config_global_db_user(void) { return g_config.db_user; }
const char *config_global_db_table(void) { return g_config.db_table; }
int         config_global_db_port(void) { return g_config.db_port; }
const char *config_global_domain(void)  { return g_config.domain; }

void config_free_global(void) {
    config_free(&g_config);
}

/* ════════════════════════════════════════════
 * CLI ENTRY POINT (for testing)
 * ════════════════════════════════════════════ */

#ifdef BCL_CONFIG_STANDALONE
int main(int argc, char **argv) {
    const char *path = (argc > 1) ? argv[1] : NULL;
    const char *key  = (argc > 2) ? argv[2] : "backend";

    BclConfig cfg;
    if (!config_load(&cfg, path)) {
        fprintf(stderr, "Failed to load config\n");
        return 1;
    }

    printf("Config path: %s\n", cfg.config_path);
    printf("Loaded: %s\n", cfg.loaded ? "yes" : "no (defaults)");
    printf("Backend: %s\n", cfg.backend);
    printf("Domain: %s\n", cfg.domain);
    printf("Binary: %s\n", cfg.binary_name);

    if (strcmp(cfg.backend, "mysql") == 0) {
        printf("DB Host: %s\n", cfg.db_host);
        printf("DB User: %s\n", cfg.db_user);
        printf("DB Name: %s\n", cfg.db_name);
        printf("DB Table: %s\n", cfg.db_table);
        printf("DB Port: %d\n", cfg.db_port);
    } else {
        printf("DB Path: %s\n", cfg.db_path);
        printf("DB Table: %s\n", cfg.db_table);
    }

    if (key) {
        const char *val = config_get(&cfg, key);
        printf("\nconfig_get(\"%s\") = %s\n", key, val ? val : "(null)");
    }

    config_free(&cfg);
    return 0;
}
#endif
