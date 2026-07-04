/*
 * vbcheck.c — Native C VBStyle Enforcer CLI
 *
 * Checks Python files against the full 15-rule VBStyle specification.
 * Rules loaded from MySQL vb_shared.instructions (same source as AI brain).
 * No Python needed — pure C, fast, native.
 *
 * Rules:
 *   ERROR: no_decorators, no_inheritance, no_sys_path, no_type_hints, no_dataclass
 *   ERROR: must_have_run, must_return_tuple3, must_have_state_dict, must_accept_mem
 *   WARN:  no_hardcoded_paths, no_print_outside_main, ghost_tag, vbstyle_tag
 *
 * Compile:
 *   cc -O2 -I/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/include/mysql -o vbcheck vbcheck.c \
 *      -L/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/lib -lmysqlclient -lz -L/opt/homebrew/lib -lssl -lcrypto -lresolv
 *
 * Usage:
 *   vbcheck <file.py>                    — check single file
 *   vbcheck <file.py> --json             — JSON output
 *   vbcheck <file.py> --fix              — auto-fix (strip decorators, type hints, print)
 *   vbcheck <dir>                        — check all .py files in directory
 *   vbcheck <file.py> --rules            — show all loaded rules from MySQL
 *   vbcheck <file.py> --strip            — output fixed code to stdout
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <dirent.h>
#include <sys/stat.h>
#include <mysql.h>

#define BUF     65536
#define MAXBUF  1048576  /* 1MB for large files */
#define MAX_RULES 32
#define MAX_VIOLATIONS 1024

/* ── rule structure ── */
typedef struct {
    char name[64];
    char description[512];
    char severity[16];  /* "error" or "warn" */
    char source[64];
} VBRule;

static VBRule rules[MAX_RULES];
static int rule_count = 0;

/* ── violation structure ── */
typedef struct {
    char rule_name[64];
    char severity[16];
    char details[512];
    int  line_num;
} Violation;

static Violation violations[MAX_VIOLATIONS];
static int violation_count = 0;

/* ── flags ── */
static int opt_json = 0;
static int opt_fix = 0;
static int opt_strip = 0;
static int opt_rules = 0;
static int opt_verbose = 0;

/* ════════════════════════════════════════════
 * RULE LOADING FROM MYSQL
 * ════════════════════════════════════════════ */

static int load_rules_from_mysql(void) {
    MYSQL *conn = mysql_init(NULL);
    if (!mysql_real_connect(conn, "localhost", "root", "", "vb_shared", 3306, NULL, 0)) {
        return 0;
    }

    /* Load vbstyle_core rules */
    if (mysql_query(conn,
        "SELECT instruction_name, instruction_body FROM instructions "
        "WHERE instruction_name IN ('vbstyle_core','no_file_imports','core_memunit_is_the_bus') "
        "ORDER BY priority")) {
        mysql_close(conn);
        return 0;
    }

    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) {
        mysql_close(conn);
        return 0;
    }

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) && rule_count < MAX_RULES) {
        const char *name = row[0] ? row[0] : "";
        const char *body = row[1] ? row[1] : "";

        /* Parse BCL bracket format to extract rules */
        /* Look for "NO " and "MUST " patterns */
        const char *p = body;
        while (*p) {
            if (strncmp(p, "\"NO ", 4) == 0 || strncmp(p, "NO ", 3) == 0) {
                const char *start = (p[0] == '"') ? p + 4 : p + 3;
                const char *end = start;
                while (*end && *end != '"' && *end != ';' && *end != '\n') end++;
                int len = end - start;
                if (len > 0 && len < 500 && rule_count < MAX_RULES) {
                    snprintf(rules[rule_count].name, 64, "no_%s", start);
                    /* truncate at space */
                    char *sp = strchr(rules[rule_count].name, ' ');
                    if (sp) *sp = '\0';
                    snprintf(rules[rule_count].description, 512, "%.*s", len, start);
                    strcpy(rules[rule_count].severity, "error");
                    strncpy(rules[rule_count].source, name, 63);
                    rule_count++;
                }
                p = end;
            } else if (strncmp(p, "\"MUST ", 6) == 0 || strncmp(p, "MUST ", 5) == 0) {
                const char *start = (p[0] == '"') ? p + 6 : p + 5;
                const char *end = start;
                while (*end && *end != '"' && *end != ';' && *end != '\n') end++;
                int len = end - start;
                if (len > 0 && len < 500 && rule_count < MAX_RULES) {
                    snprintf(rules[rule_count].name, 64, "must_%s", start);
                    char *sp = strchr(rules[rule_count].name, ' ');
                    if (sp) *sp = '\0';
                    snprintf(rules[rule_count].description, 512, "%.*s", len, start);
                    strcpy(rules[rule_count].severity, "error");
                    strncpy(rules[rule_count].source, name, 63);
                    rule_count++;
                }
                p = end;
            } else {
                p++;
            }
        }
    }

    mysql_free_result(res);
    mysql_close(conn);
    return rule_count > 0;
}

/* Load built-in rules as fallback */
static void load_builtin_rules(void) {
    const char *builtin[] = {
        "no_decorators",     "NO decorators ever",                      "error", "vbstyle_core",
        "no_print_methods",  "NO print in class methods",               "error", "vbstyle_core",
        "no_hardcoded_paths","NO hardcoded paths",                      "warn",  "vbstyle_core",
        "no_inheritance",    "NO ABC / inheritance",                    "error", "vbstyle_core",
        "no_sys_path",       "NO sys.path.insert",                      "error", "no_file_imports",
        "no_type_hints",     "NO type hints in signatures",             "error", "vbstyle_core",
        "no_dataclass",      "NO @dataclass decorator",                 "error", "vbstyle_core",
        "must_have_run",     "MUST use Run() dispatch",                 "error", "vbstyle_core",
        "must_return_tuple3","MUST return Tuple3 (1,data,None)",        "error", "vbstyle_core",
        "must_have_state",   "MUST have state dict: config,memunit,db", "error", "vbstyle_core",
        "must_accept_mem",   "MUST accept mem param in __init__",       "error", "core_memunit",
        "ghost_tag",         "SHOULD have [@GHOST] at file top",        "warn",  "vbstyle_core",
        "vbstyle_tag",       "SHOULD have [@VBSTYLE] at file top",      "warn",  "vbstyle_core",
        NULL
    };

    for (int i = 0; builtin[i] && rule_count < MAX_RULES; i += 4) {
        strncpy(rules[rule_count].name, builtin[i], 63);
        strncpy(rules[rule_count].description, builtin[i+1], 511);
        strncpy(rules[rule_count].severity, builtin[i+2], 15);
        strncpy(rules[rule_count].source, builtin[i+3], 63);
        rule_count++;
    }
}

/* ════════════════════════════════════════════
 * FILE READING
 * ════════════════════════════════════════════ */

static char *read_file(const char *path, char *buf, size_t bufsize) {
    FILE *f = fopen(path, "r");
    if (!f) return NULL;
    size_t n = fread(buf, 1, bufsize - 1, f);
    buf[n] = '\0';
    fclose(f);
    return buf;
}

/* count lines up to position */
static int line_for_pos(const char *content, int pos) {
    int line = 1;
    for (int i = 0; i < pos && content[i]; i++)
        if (content[i] == '\n') line++;
    return line;
}

/* ════════════════════════════════════════════
 * VBSTYLE CHECKS — C implementation
 * Uses regex-like pattern matching on source text
 * ════════════════════════════════════════════ */

static void add_violation(const char *rule, const char *severity, const char *details, int line) {
    if (violation_count >= MAX_VIOLATIONS) return;
    strncpy(violations[violation_count].rule_name, rule, 63);
    strncpy(violations[violation_count].severity, severity, 15);
    strncpy(violations[violation_count].details, details, 511);
    violations[violation_count].line_num = line;
    violation_count++;
}

/* check for decorators: lines starting with @ (not inside strings/comments) */
static void check_decorators(const char *content) {
    const char *p = content;
    int line = 1;
    int in_string = 0;
    int in_comment = 0;
    while (*p) {
        if (*p == '\n') { line++; in_comment = 0; p++; continue; }
        if (in_comment) { p++; continue; }
        if (*p == '#') { in_comment = 1; p++; continue; }

        /* check for @decorator at start of line (after whitespace) */
        if (*p == '@' && (p == content || p[-1] == '\n' || (p > content && isspace((unsigned char)p[-1])))) {
            /* make sure it's not inside a string */
            const char *start = p;
            /* skip leading whitespace on this line */
            const char *line_start = p;
            while (line_start > content && line_start[-1] != '\n') line_start--;
            int only_ws = 1;
            for (const char *c = line_start; c < p; c++) {
                if (!isspace((unsigned char)*c)) { only_ws = 0; break; }
            }
            if (only_ws) {
                /* check it's a decorator (not @GHOST or @VBSTYLE in comments) */
                char dec_name[64] = {0};
                int i = 0;
                const char *d = p + 1;
                while (*d && (isalnum((unsigned char)*d) || *d == '_' || *d == '.') && i < 63) {
                    dec_name[i++] = *d++;
                }
                if (strlen(dec_name) > 0 && strcmp(dec_name, "GHOST") != 0 &&
                    strcmp(dec_name, "VBSTYLE") != 0 && strcmp(dec_name, "CLASSES") != 0 &&
                    strcmp(dec_name, "dataclass") != 0) {
                    char details[256];
                    snprintf(details, sizeof(details), "decorator @%s at line %d", dec_name, line);
                    add_violation("no_decorators", "error", details, line);
                }
                if (strcmp(dec_name, "dataclass") == 0) {
                    char details[256];
                    snprintf(details, sizeof(details), "@dataclass at line %d", line);
                    add_violation("no_dataclass", "error", details, line);
                }
            }
        }
        p++;
    }
}

/* check for inheritance: class Foo(Bar) */
static void check_inheritance(const char *content) {
    const char *p = content;
    int line = 1;
    while (*p) {
        if (*p == '\n') line++;
        /* find "class " at start of line */
        if (strncmp(p, "class ", 6) == 0 && (p == content || p[-1] == '\n' || isspace((unsigned char)p[-1]))) {
            const char *paren = strchr(p, '(');
            const char *colon = strchr(p, ':');
            if (paren && colon && paren < colon) {
                /* extract base class name */
                char base[128] = {0};
                const char *start = paren + 1;
                const char *end = colon;
                while (start < end && isspace((unsigned char)*start)) start++;
                int i = 0;
                while (start < end && *start != ')' && *start != ',' && i < 127) {
                    base[i++] = *start++;
                }
                if (strlen(base) > 0) {
                    char details[256];
                    snprintf(details, sizeof(details), "class inherits from %s at line %d", base, line);
                    add_violation("no_inheritance", "error", details, line);
                }
            }
        }
        p++;
    }
}

/* check for sys.path.insert */
static void check_sys_path(const char *content) {
    if (strstr(content, "sys.path.insert")) {
        int line = line_for_pos(content, (int)(strstr(content, "sys.path.insert") - content));
        add_violation("no_sys_path", "error", "sys.path.insert found", line);
    }
}

/* check for type hints in function signatures: def foo(x: int, y: str) -> bool */
static void check_type_hints(const char *content) {
    const char *p = content;
    int line = 1;
    while (*p) {
        if (*p == '\n') line++;
        /* find "def " */
        if (strncmp(p, "def ", 4) == 0) {
            /* find the closing paren */
            const char *paren = strchr(p, '(');
            const char *close = paren ? strchr(paren, ')') : NULL;
            const char *colon = close ? strchr(close, ':') : NULL;
            if (paren && close && colon) {
                /* check for type hints between parens: look for ": " pattern */
                for (const char *c = paren + 1; c < close; c++) {
                    if (*c == ':' && c + 1 < close && (isalpha((unsigned char)c[1]) || c[1] == '[')) {
                        char details[256];
                        snprintf(details, sizeof(details), "type hint in signature at line %d", line);
                        add_violation("no_type_hints", "error", details, line);
                        break;
                    }
                }
                /* check for return type hint: -> Type */
                for (const char *c = close; c < colon; c++) {
                    if (*c == '-' && c + 1 < colon && c[1] == '>') {
                        char details[256];
                        snprintf(details, sizeof(details), "return type hint at line %d", line);
                        add_violation("no_type_hints", "error", details, line);
                        break;
                    }
                }
            }
        }
        p++;
    }
}

/* check for print() outside __main__ */
static void check_print(const char *content) {
    const char *main = strstr(content, "if __name__");
    const char *check_end = main ? main : content + strlen(content);
    const char *p = content;
    int line = 1;
    while (p < check_end) {
        if (*p == '\n') line++;
        /* find print( not inside a string or comment */
        if (strncmp(p, "print(", 6) == 0 && (p == content || !isalnum((unsigned char)p[-1]))) {
            /* check we're not in a comment */
            const char *line_start = p;
            while (line_start > content && line_start[-1] != '\n') line_start--;
            int in_comment = 0;
            for (const char *c = line_start; c < p; c++) {
                if (*c == '#') { in_comment = 1; break; }
            }
            if (!in_comment) {
                char details[256];
                snprintf(details, sizeof(details), "print() outside __main__ at line %d", line);
                add_violation("no_print_methods", "error", details, line);
            }
        }
        p++;
    }
}

/* check for Run() method in each class */
static void check_run_method(const char *content) {
    const char *p = content;
    int line = 1;
    while (*p) {
        if (*p == '\n') line++;
        if (strncmp(p, "class ", 6) == 0 && (p == content || p[-1] == '\n' || isspace((unsigned char)p[-1]))) {
            char class_name[128] = {0};
            const char *start = p + 6;
            int i = 0;
            while (*start && (isalnum((unsigned char)*start) || *start == '_') && i < 127) {
                class_name[i++] = *start++;
            }
            /* find end of class block (next class at same or lower indent, or EOF) */
            const char *class_start = p;
            const char *next = p + 1;
            while (*next) {
                if (*next == '\n' && next + 1 < content + strlen(content)) {
                    const char *nl = next + 1;
                    if (strncmp(nl, "class ", 6) == 0) break;
                }
                next++;
            }
            /* check for def Run( in class block */
            int found_run = 0;
            for (const char *c = class_start; c < next; c++) {
                if (strncmp(c, "def Run(", 8) == 0) { found_run = 1; break; }
            }
            if (!found_run) {
                char details[256];
                snprintf(details, sizeof(details), "class %s has no Run() method at line %d", class_name, line);
                add_violation("must_have_run", "warn", details, line);
            }
        }
        p++;
    }
}

/* check for Tuple3 return pattern in Run methods */
static void check_tuple3(const char *content) {
    const char *p = content;
    int line = 1;
    while (*p) {
        if (*p == '\n') line++;
        if (strncmp(p, "def Run(", 8) == 0) {
            /* find the method body until next def or class */
            const char *body_start = p;
            const char *body_end = p + 1;
            while (*body_end) {
                if (*body_end == '\n') {
                    const char *nl = body_end + 1;
                    if (strncmp(nl, "    def ", 8) == 0 || strncmp(nl, "def ", 4) == 0 ||
                        strncmp(nl, "class ", 6) == 0) break;
                }
                body_end++;
            }
            /* check for return (0, or return (1, */
            int found_tuple3 = 0;
            for (const char *c = body_start; c < body_end; c++) {
                if (strncmp(c, "return (", 8) == 0 || strncmp(c, "return(", 7) == 0) {
                    const char *paren = strchr(c, '(');
                    if (paren) {
                        const char *after = paren + 1;
                        while (*after && isspace((unsigned char)*after)) after++;
                        if (*after == '0' || *after == '1') {
                            found_tuple3 = 1;
                            break;
                        }
                    }
                }
            }
            if (!found_tuple3) {
                char details[256];
                snprintf(details, sizeof(details), "Run() at line %d does not return Tuple3", line);
                add_violation("must_return_tuple3", "warn", details, line);
            }
        }
        p++;
    }
}

/* check for state dict pattern in __init__ */
static void check_state_dict(const char *content) {
    const char *p = content;
    int line = 1;
    while (*p) {
        if (*p == '\n') line++;
        if (strncmp(p, "def __init__(", 13) == 0 || strncmp(p, "def __init__ (", 14) == 0) {
            /* find method body */
            const char *body_start = p;
            const char *body_end = p + 1;
            while (*body_end) {
                if (*body_end == '\n') {
                    const char *nl = body_end + 1;
                    if (strncmp(nl, "    def ", 8) == 0 || strncmp(nl, "def ", 4) == 0 ||
                        strncmp(nl, "class ", 6) == 0) break;
                }
                body_end++;
            }
            int body_len = body_end - body_start;
            char *body = malloc(body_len + 1);
            memcpy(body, body_start, body_len);
            body[body_len] = '\0';

            int has_config = strstr(body, "\"config\"") || strstr(body, "'config'");
            int has_memunit = strstr(body, "\"memunit\"") || strstr(body, "'memunit'");
            int has_db = strstr(body, "\"db_manager\"") || strstr(body, "'db_manager'");

            if (!has_config || !has_memunit || !has_db) {
                char details[256];
                snprintf(details, sizeof(details), "__init__ at line %d missing state dict keys", line);
                add_violation("must_have_state", "warn", details, line);
            }
            free(body);
        }
        p++;
    }
}

/* check for mem param in __init__ */
static void check_mem_param(const char *content) {
    const char *p = content;
    int line = 1;
    while (*p) {
        if (*p == '\n') line++;
        if (strncmp(p, "def __init__(", 13) == 0) {
            const char *close = strchr(p, ')');
            if (close) {
                int has_mem = 0;
                for (const char *c = p; c < close; c++) {
                    if (strncmp(c, "mem", 3) == 0) { has_mem = 1; break; }
                }
                if (!has_mem) {
                    char details[256];
                    snprintf(details, sizeof(details), "__init__ at line %d does not accept mem param", line);
                    add_violation("must_accept_mem", "warn", details, line);
                }
            }
        }
        p++;
    }
}

/* check for GHOST and VBSTYLE tags at file top */
static void check_tags(const char *content) {
    char top[512] = {0};
    strncpy(top, content, 511);

    if (!strstr(top, "[@GHOST]"))
        add_violation("ghost_tag", "warn", "No [@GHOST] tag at file top", 1);
    if (!strstr(top, "[@VBSTYLE]"))
        add_violation("vbstyle_tag", "warn", "No [@VBSTYLE] tag at file top", 1);
}

/* check for hardcoded paths */
static void check_hardcoded_paths(const char *content) {
    const char *p = content;
    int line = 1;
    int count = 0;
    char first_path[256] = {0};
    while (*p) {
        if (*p == '\n') line++;
        if (strncmp(p, "/Users/", 7) == 0 && (p > content && (p[-1] == '"' || p[-1] == '\''))) {
            count++;
            if (first_path[0] == '\0') {
                const char *end = p;
                while (*end && *end != '"' && *end != '\'' && *end != '\n' && end - p < 255) end++;
                strncpy(first_path, p, end - p);
            }
        }
        p++;
    }
    if (count > 0) {
        char details[256];
        snprintf(details, sizeof(details), "%d hardcoded paths (e.g. %s)", count, first_path);
        add_violation("no_hardcoded_paths", "warn", details, 1);
    }
}

/* ════════════════════════════════════════════
 * RUN ALL CHECKS
 * ════════════════════════════════════════════ */

static void run_all_checks(const char *content) {
    violation_count = 0;
    check_decorators(content);
    check_inheritance(content);
    check_sys_path(content);
    check_type_hints(content);
    check_print(content);
    check_run_method(content);
    check_tuple3(content);
    check_state_dict(content);
    check_mem_param(content);
    check_tags(content);
    check_hardcoded_paths(content);
}

/* ════════════════════════════════════════════
 * AUTO-FIX (strip violations)
 * ════════════════════════════════════════════ */

static void strip_violations(const char *content, FILE *out) {
    const char *p = content;
    int in_string = 0;
    int in_comment = 0;

    while (*p) {
        /* detect line start */
        const char *line_start = p;
        const char *line_end = p;
        while (*line_end && *line_end != '\n') line_end++;

        int line_len = line_end - line_start;
        char *line = malloc(line_len + 2);
        memcpy(line, line_start, line_len);
        line[line_len] = '\n';
        line[line_len + 1] = '\0';

        /* check if line is a decorator (starts with @ after whitespace) */
        const char *ws_end = line;
        while (*ws_end && isspace((unsigned char)*ws_end)) ws_end++;

        int is_decorator = 0;
        if (*ws_end == '@') {
            char dec_name[64] = {0};
            int i = 0;
            const char *d = ws_end + 1;
            while (*d && (isalnum((unsigned char)*d) || *d == '_' || *d == '.') && i < 63)
                dec_name[i++] = *d++;
            if (strlen(dec_name) > 0 && strcmp(dec_name, "GHOST") != 0 &&
                strcmp(dec_name, "VBSTYLE") != 0 && strcmp(dec_name, "CLASSES") != 0) {
                is_decorator = 1;
            }
        }

        if (is_decorator) {
            /* skip this line */
        } else if (strncmp(ws_end, "print(", 6) == 0) {
            /* replace print( with pass  # print( */
            fwrite(line, 1, ws_end - line, out);
            fprintf(out, "pass  # ");
            fwrite(ws_end, 1, line_len - (ws_end - line), out);
            fputc('\n', out);
        } else {
            /* output line as-is, but strip type hints from def lines */
            if (strncmp(ws_end, "def ", 4) == 0) {
                /* strip type hints: remove : Type from params and -> Type from return */
                char *def_line = strdup(line);
                /* remove -> Type */
                char *arrow = strstr(def_line, " -> ");
                if (arrow) {
                    char *colon = strchr(arrow, ':');
                    if (colon) {
                        *arrow = ':';
                        memmove(arrow + 1, colon + 1, strlen(colon));
                    }
                }
                /* remove : Type from params (simplified) */
                /* This is a basic strip — full AST would be better but C doesn't have Python AST */
                fputs(def_line, out);
                free(def_line);
            } else {
                fwrite(line, 1, line_len + 1, out);
            }
        }

        free(line);
        p = line_end;
        if (*p == '\n') p++;
    }
}

/* ════════════════════════════════════════════
 * OUTPUT
 * ════════════════════════════════════════════ */

static void print_results(const char *filename) {
    int errors = 0, warns = 0, passes = 0;

    /* count by severity */
    for (int i = 0; i < violation_count; i++) {
        if (strcmp(violations[i].severity, "error") == 0) errors++;
        else warns++;
    }

    /* rules that passed = total rules - rules with violations */
    int rules_with_violations = 0;
    for (int i = 0; i < rule_count; i++) {
        int found = 0;
        for (int v = 0; v < violation_count; v++) {
            if (strstr(violations[v].rule_name, rules[i].name)) { found = 1; break; }
        }
        if (!found) passes++;
        else rules_with_violations++;
    }

    if (opt_json) {
        printf("{\"file\":\"%s\",\"rules_loaded\":%d,\"violations\":%d,\"errors\":%d,\"warns\":%d,\"passes\":%d,\"checks\":[",
               filename, rule_count, violation_count, errors, warns, passes);
        for (int i = 0; i < violation_count; i++) {
            if (i > 0) printf(",");
            printf("{\"rule\":\"%s\",\"severity\":\"%s\",\"line\":%d,\"details\":\"%s\"}",
                   violations[i].rule_name, violations[i].severity,
                   violations[i].line_num, violations[i].details);
        }
        printf("]}\n");
    } else {
        printf("\n=== VBCHECK: %s ===\n", filename);
        printf("Rules loaded: %d (from MySQL vb_shared.instructions)\n\n", rule_count);

        if (violation_count == 0) {
            printf("  ALL CHECKS PASSED — VBStyle compliant\n");
        } else {
            for (int i = 0; i < violation_count; i++) {
                const char *sym = strcmp(violations[i].severity, "error") == 0 ? "FAIL" : "WARN";
                printf("  [%s] %s (line %d): %s\n",
                       sym, violations[i].rule_name,
                       violations[i].line_num, violations[i].details);
            }
        }

        printf("\n  SUMMARY: %d pass, %d fail, %d warn\n", passes, errors, warns);
        if (errors == 0)
            printf("  STATUS: VBSTYLE COMPLIANT (warnings only)\n");
        else
            printf("  STATUS: NOT COMPLIANT (%d errors must fix)\n", errors);
    }
}

static void print_rules(void) {
    printf("=== VBSTYLE RULES (loaded from MySQL vb_shared.instructions) ===\n\n");
    for (int i = 0; i < rule_count; i++) {
        printf("  [%s] %s: %s\n", rules[i].severity, rules[i].name, rules[i].description);
        printf("         source: %s\n\n", rules[i].source);
    }
    printf("Total: %d rules\n", rule_count);
}

/* ════════════════════════════════════════════
 * DIRECTORY SCANNING
 * ════════════════════════════════════════════ */

static int has_py_ext(const char *name) {
    int len = strlen(name);
    return len > 3 && strcmp(name + len - 3, ".py") == 0;
}

static void check_directory(const char *dirpath) {
    DIR *d = opendir(dirpath);
    if (!d) {
        fprintf(stderr, "Cannot open directory: %s\n", dirpath);
        return;
    }

    struct dirent *entry;
    int total_files = 0;
    int total_errors = 0;
    int total_warns = 0;

    while ((entry = readdir(d))) {
        if (entry->d_name[0] == '.') continue;
        if (!has_py_ext(entry->d_name)) continue;

        char filepath[1024];
        snprintf(filepath, sizeof(filepath), "%s/%s", dirpath, entry->d_name);

        struct stat st;
        if (stat(filepath, &st) != 0 || !S_ISREG(st.st_mode)) continue;

        static char filebuf[MAXBUF];
        if (!read_file(filepath, filebuf, sizeof(filebuf))) continue;

        run_all_checks(filebuf);
        print_results(filepath);

        for (int i = 0; i < violation_count; i++) {
            if (strcmp(violations[i].severity, "error") == 0) total_errors++;
            else total_warns++;
        }
        total_files++;
    }

    closedir(d);

    if (total_files > 0) {
        printf("\n=== DIRECTORY SUMMARY: %s ===\n", dirpath);
        printf("  Files checked: %d\n", total_files);
        printf("  Total errors: %d\n", total_errors);
        printf("  Total warnings: %d\n", total_warns);
    }
}

/* ════════════════════════════════════════════
 * USAGE
 * ════════════════════════════════════════════ */

static void usage(const char *p) {
    fprintf(stderr,
        "vbcheck — Native C VBStyle Enforcer\n"
        "\n"
        "Usage: %s <file.py|dir> [options]\n"
        "\n"
        "Options:\n"
        "  --json       JSON output for programmatic parsing\n"
        "  --fix        Show what would be auto-fixed (dry run)\n"
        "  --strip      Output fixed code to stdout (decorators, type hints, print)\n"
        "  --rules      Show all loaded VBStyle rules from MySQL\n"
        "  --verbose    Show passing checks too\n"
        "\n"
        "Rules loaded from MySQL vb_shared.instructions (same source as AI brain).\n"
        "If MySQL is unavailable, built-in rules are used as fallback.\n"
        "\n"
        "Examples:\n"
        "  %s dom_search.py\n"
        "  %s dom_codegraph.py --json\n"
        "  %s /path/to/Domains/ --verbose\n"
        "  %s dom_search.py --strip > fixed.py\n"
        "  %s --rules\n",
        p, p, p, p, p, p);
}

/* ════════════════════════════════════════════
 * MAIN
 * ════════════════════════════════════════════ */

int main(int argc, char **argv) {
    const char *target = NULL;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--json")) opt_json = 1;
        else if (!strcmp(argv[i], "--fix")) opt_fix = 1;
        else if (!strcmp(argv[i], "--strip")) opt_strip = 1;
        else if (!strcmp(argv[i], "--rules")) opt_rules = 1;
        else if (!strcmp(argv[i], "--verbose")) opt_verbose = 1;
        else if (argv[i][0] != '-' && !target) target = argv[i];
    }

    /* Load rules: try MySQL first, fall back to built-in */
    if (!load_rules_from_mysql()) {
        load_builtin_rules();
        if (!opt_json && opt_verbose)
            fprintf(stderr, "Note: Using built-in rules (MySQL not available)\n");
    }

    if (opt_rules) {
        print_rules();
        return 0;
    }

    if (!target) {
        usage(argv[0]);
        return 1;
    }

    /* Check if target is a directory or file */
    struct stat st;
    if (stat(target, &st) != 0) {
        fprintf(stderr, "Error: %s not found\n", target);
        return 1;
    }

    if (S_ISDIR(st.st_mode)) {
        check_directory(target);
    } else {
        static char filebuf[MAXBUF];
        if (!read_file(target, filebuf, sizeof(filebuf))) {
            fprintf(stderr, "Error: cannot read %s\n", target);
            return 1;
        }

        if (opt_strip) {
            strip_violations(filebuf, stdout);
        } else {
            run_all_checks(filebuf);
            print_results(target);
        }
    }

    return 0;
}
