// GraphConfig — config parser for the Max Graph Engine
// Reads a simple TOML-like config file and populates Graph settings

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Simple config parser — reads key=value pairs from a file
// Sections are [section_name]
// Lines starting with # or // are comments

typedef struct ConfigEntry {
    char section[64];
    char key[64];
    char value[256];
} ConfigEntry;

typedef struct Config {
    ConfigEntry *entries;
    int count;
    int capacity;
} Config;

Config *config_create() {
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

static void trim(char *s) {
    if (!s) return;
    char *start = s;
    while (*start && (*start == ' ' || *start == '\t' || *start == '\r' || *start == '
')) start++;
    if (start != s) memmove(s, start, strlen(start) + 1);
    int len = strlen(s);
    while (len > 0 && (s[len-1] == ' ' || s[len-1] == '\t' || s[len-1] == '\r' || s[len-1] == '
')) {
        s[--len] = '\0';
    }
}

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
        strncpy(c->entries[c->count].key, key, sizeof(c->entries[c->count].key) - 1);
        strncpy(c->entries[c->count].value, value, sizeof(c->entries[c->count].value) - 1);
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

// Apply config to a Graph's policy and executor
int config_apply_to_graph(Config *c, Graph *g) {
    if (!c || !g) return -1;
    g->policy.hard_limit = config_get_int(c, "engine", "max_depth", 6);
    g->policy.attention_threshold = config_get_float(c, "policy", "attention_threshold", 0.3);
    g->policy.max_nodes_per_hop = config_get_int(c, "policy", "max_nodes_per_hop", 100);
    g->policy.max_total_nodes = config_get_int(c, "policy", "max_total_nodes", 10000);
    g->executor.memory_budget = (size_t)config_get_int(c, "engine", "memory_budget_mb", 512) * 1024 * 1024;
    g->executor.timeout_ms = config_get_int(c, "engine", "timeout_ms", 5000);
    g->executor.cost_limit = config_get_int(c, "engine", "cost_limit", 10000);
    const char *mysql_host = config_get(c, "stored_graph", "mysql_host");
    if (mysql_host) {
        strncpy(g->mysql_host, mysql_host, sizeof(g->mysql_host) - 1);
    } else {
        strncpy(g->mysql_host, "localhost", sizeof(g->mysql_host) - 1);
    }
    const char *mysql_user = config_get(c, "stored_graph", "mysql_user");
    if (mysql_user) {
        strncpy(g->mysql_user, mysql_user, sizeof(g->mysql_user) - 1);
    } else {
        strncpy(g->mysql_user, "root", sizeof(g->mysql_user) - 1);
    }
    const char *mysql_db = config_get(c, "stored_graph", "mysql_db");
    if (mysql_db) {
        strncpy(g->mysql_db, mysql_db, sizeof(g->mysql_db) - 1);
    } else {
        strncpy(g->mysql_db, "vb_shared", sizeof(g->mysql_db) - 1);
    }
    return 0;
}
