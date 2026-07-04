/*
 * codeingest.c — Native C Python Source Ingestor into SQLite
 *
 * Reads .py files, extracts classes/methods/functions/constants/imports
 * using regex-based parsing (no Python AST needed — pure C), and stores
 * everything into a normalized SQLite database for code analysis, merging,
 * and query operations.
 *
 * Schema (auto-created):
 *   source_files  — filename, filepath, content, line_count
 *   classes       — source_file, class_name, methods (JSON array)
 *   functions     — source_file, func_name, args, line_start, line_end, body
 *   constants     — source_file, name, value, line
 *   imports       — source_file, module, alias
 *   regex_patterns— source_file, var_name, pattern
 *
 * Compile:
 *   cc -O2 -o codeingest codeingest.c -lsqlite3
 *
 * Usage:
 *   ./codeingest <file.py>                     — ingest single file into code_ingest.db
 *   ./codeingest <file.py> -o <output.db>      — specify output database
 *   ./codeingest <dir>                         — ingest all .py files in directory
 *   ./codeingest <dir> -o <output.db>          — directory ingest with output
 *   ./codeingest <file.py> --status            — show database stats after ingest
 *   ./codeingest <file.py> --json              — JSON summary output
 *   ./codeingest --schema                      — print schema SQL and exit
 *   ./codeingest --query <db> <sql>            — run SQL query on existing db
 *
 * Author: wws / Cascade
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sqlite3.h>

/* ════════════════════════════════════════════
 * CONSTANTS
 * ════════════════════════════════════════════ */

#define BUF        65536
#define MAXBUF     1048576   /* 1MB for large files */
#define MAX_LINE   2048
#define MAX_NAME   256
#define MAX_ARGS   1024
#define MAX_BODY   65536
#define MAX_FILES  4096
#define MAX_METHODS 512

static const char *SCHEMA_SQL =
"CREATE TABLE IF NOT EXISTS source_files (\n"
"    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
"    filename TEXT,\n"
"    filepath TEXT UNIQUE,\n"
"    content TEXT,\n"
"    line_count INTEGER,\n"
"    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP\n"
");\n"
"CREATE TABLE IF NOT EXISTS classes (\n"
"    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
"    source_file TEXT,\n"
"    class_name TEXT,\n"
"    methods TEXT,\n"
"    line_start INTEGER,\n"
"    line_end INTEGER\n"
");\n"
"CREATE TABLE IF NOT EXISTS functions (\n"
"    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
"    source_file TEXT,\n"
"    func_name TEXT,\n"
"    args TEXT,\n"
"    line_start INTEGER,\n"
"    line_end INTEGER,\n"
"    body TEXT,\n"
"    is_method INTEGER DEFAULT 0,\n"
"    parent_class TEXT\n"
");\n"
"CREATE TABLE IF NOT EXISTS constants (\n"
"    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
"    source_file TEXT,\n"
"    name TEXT,\n"
"    value TEXT,\n"
"    line INTEGER\n"
");\n"
"CREATE TABLE IF NOT EXISTS imports (\n"
"    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
"    source_file TEXT,\n"
"    module TEXT,\n"
"    alias TEXT,\n"
"    line INTEGER\n"
");\n"
"CREATE TABLE IF NOT EXISTS regex_patterns (\n"
"    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
"    source_file TEXT,\n"
"    var_name TEXT,\n"
"    pattern TEXT,\n"
"    line INTEGER\n"
");\n"
"CREATE INDEX IF NOT EXISTS idx_sf_file ON source_files(filepath);\n"
"CREATE INDEX IF NOT EXISTS idx_cls_file ON classes(source_file);\n"
"CREATE INDEX IF NOT EXISTS idx_cls_name ON classes(class_name);\n"
"CREATE INDEX IF NOT EXISTS idx_fn_file ON functions(source_file);\n"
"CREATE INDEX IF NOT EXISTS idx_fn_name ON functions(func_name);\n"
"CREATE INDEX IF NOT EXISTS idx_const_file ON constants(source_file);\n"
"CREATE INDEX IF NOT EXISTS idx_const_name ON constants(name);\n"
"CREATE INDEX IF NOT EXISTS idx_imp_file ON imports(source_file);\n"
"CREATE INDEX IF NOT EXISTS idx_rx_file ON regex_patterns(source_file);\n"
;

/* ════════════════════════════════════════════
 * FLAGS
 * ════════════════════════════════════════════ */

static int opt_status = 0;
static int opt_json   = 0;
static char output_db[MAX_NAME] = "code_ingest.db";

/* ════════════════════════════════════════════
 * UTILITIES
 * ════════════════════════════════════════════ */

static char *read_file(const char *path, long *out_len) {
    FILE *f = fopen(path, "r");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (len > MAXBUF) len = MAXBUF;
    char *buf = (char *)malloc(len + 1);
    if (!buf) { fclose(f); return NULL; }
    fread(buf, 1, len, f);
    buf[len] = '\0';
    fclose(f);
    if (out_len) *out_len = len;
    return buf;
}

static int count_lines(const char *src) {
    int count = 1;
    for (const char *p = src; *p; p++)
        if (*p == '\n') count++;
    return count;
}

static char *get_line(const char *src, int lineno, char *out, int max) {
    int cur = 1;
    const char *start = src;
    for (const char *p = src; *p; p++) {
        if (cur == lineno) {
            const char *eol = strchr(p, '\n');
            int len = eol ? (int)(eol - p) : (int)strlen(p);
            if (len >= max) len = max - 1;
            memcpy(out, p, len);
            out[len] = '\0';
            return out;
        }
        if (*p == '\n') cur++;
    }
    out[0] = '\0';
    return out;
}

static int starts_with(const char *s, const char *prefix) {
    return strncmp(s, prefix, strlen(prefix)) == 0;
}

static char *trim(char *s) {
    while (*s && isspace((unsigned char)*s)) s++;
    char *end = s + strlen(s) - 1;
    while (end > s && isspace((unsigned char)*end)) *end-- = '\0';
    return s;
}

static char *lstrip(char *s) {
    while (*s && isspace((unsigned char)*s)) s++;
    return s;
}

/* Escape single quotes for SQL */
static void sql_escape(const char *in, char *out, int max) {
    int j = 0;
    for (int i = 0; in[i] && j < max - 2; i++) {
        if (in[i] == '\'') {
            if (j < max - 3) { out[j++] = '\''; out[j++] = '\''; }
        } else {
            out[j++] = in[i];
        }
    }
    out[j] = '\0';
}

/* ════════════════════════════════════════════
 * PARSER — Regex-based Python extraction
 * ════════════════════════════════════════════ */

typedef struct {
    char name[MAX_NAME];
    char args[MAX_ARGS];
    int  line_start;
    int  line_end;
    int  is_method;
    char parent_class[MAX_NAME];
} FuncInfo;

typedef struct {
    char name[MAX_NAME];
    int  line_start;
    int  line_end;
    char methods[MAX_BODY]; /* comma-separated */
} ClassInfo;

typedef struct {
    char name[MAX_NAME];
    char value[MAX_BODY];
    int  line;
} ConstInfo;

typedef struct {
    char module[MAX_NAME];
    char alias[MAX_NAME];
    int  line;
} ImportInfo;

typedef struct {
    char var_name[MAX_NAME];
    char pattern[MAX_BODY];
    int  line;
} RegexInfo;

/* Parse a function signature from a line:
   "    def foo(self, x, y):"
   extracts name="foo", args="self, x, y" */
static int parse_def(const char *line, char *name, int name_max, char *args, int args_max) {
    const char *p = strstr(line, "def ");
    if (!p) return 0;
    p += 4;
    /* skip whitespace */
    while (*p && isspace((unsigned char)*p)) p++;
    /* read name */
    int ni = 0;
    while (*p && (isalnum((unsigned char)*p) || *p == '_') && ni < name_max - 1) {
        name[ni++] = *p++;
    }
    name[ni] = '\0';
    if (!*p) return 0;
    /* skip to '(' */
    while (*p && *p != '(') p++;
    if (*p != '(') return 0;
    p++;
    /* read args until matching ')' */
    int depth = 1;
    int ai = 0;
    while (*p && depth > 0 && ai < args_max - 1) {
        if (*p == '(') depth++;
        else if (*p == ')') { depth--; if (depth == 0) break; }
        args[ai++] = *p++;
    }
    args[ai] = '\0';
    return 1;
}

/* Find the end of a function/class body based on indentation.
   The body ends when we see a line with less indentation than the def/class. */
static int find_body_end(const char *src, int total_lines, int start_line, int indent) {
    int end = start_line;
    char line[MAX_LINE];
    for (int i = start_line + 1; i <= total_lines; i++) {
        get_line(src, i, line, sizeof(line));
        /* skip blank lines and comments */
        char *stripped = lstrip(line);
        if (*stripped == '\0' || *stripped == '#') continue;
        /* count leading whitespace */
        int cur_indent = 0;
        for (const char *p = line; *p && (*p == ' ' || *p == '\t'); p++) cur_indent++;
        if (cur_indent < indent && *stripped != '\0') {
            return i - 1;
        }
        end = i;
    }
    return end;
}

static int count_indent(const char *line) {
    int n = 0;
    for (const char *p = line; *p && (*p == ' ' || *p == '\t'); p++) n++;
    return n;
}

/* Main parser — extracts all constructs from source */
typedef struct {
    ClassInfo  classes[128];
    int        class_count;
    FuncInfo   funcs[512];
    int        func_count;
    ConstInfo  consts[256];
    int        const_count;
    ImportInfo imports[128];
    int        import_count;
    RegexInfo  regexes[64];
    int        regex_count;
} ParseResult;

static void parse_source(const char *src, const char *filename, ParseResult *pr) {
    memset(pr, 0, sizeof(*pr));
    int total_lines = count_lines(src);
    char line[MAX_LINE];
    char prev_line[MAX_LINE] = "";

    int current_class = -1; /* index into pr->classes, -1 if not in class */
    int class_indent = 0;

    for (int i = 1; i <= total_lines; i++) {
        get_line(src, i, line, sizeof(line));
        char *stripped = lstrip(line);
        int indent = count_indent(line);

        /* Skip blank lines and comments */
        if (*stripped == '\0' || *stripped == '#') {
            strncpy(prev_line, line, sizeof(prev_line) - 1);
            continue;
        }

        /* Track class context */
        if (current_class >= 0 && indent <= class_indent && *stripped != '\0') {
            /* Check if this is a new class or top-level */
            if (!starts_with(stripped, "def ") && !starts_with(stripped, "class ")) {
                current_class = -1;
            }
        }

        /* Class definition */
        if (starts_with(stripped, "class ")) {
            char *p = stripped + 6;
            char name[MAX_NAME] = "";
            int ni = 0;
            while (*p && (isalnum((unsigned char)*p) || *p == '_') && ni < sizeof(name) - 1) {
                name[ni++] = *p++;
            }
            name[ni] = '\0';

            if (pr->class_count < 128) {
                strncpy(pr->classes[pr->class_count].name, name, MAX_NAME - 1);
                pr->classes[pr->class_count].line_start = i;
                pr->classes[pr->class_count].line_end = find_body_end(src, total_lines, i, indent);
                pr->classes[pr->class_count].methods[0] = '\0';
                current_class = pr->class_count;
                class_indent = indent;
                pr->class_count++;
            }
            continue;
        }

        /* Function/method definition */
        if (starts_with(stripped, "def ") || starts_with(stripped, "async def ")) {
            char name[MAX_NAME] = "";
            char args[MAX_ARGS] = "";
            const char *def_pos = strstr(stripped, "def ");
            if (!def_pos) continue;
            if (!parse_def(stripped, name, sizeof(name), args, sizeof(args))) continue;

            if (pr->func_count < 512) {
                strncpy(pr->funcs[pr->func_count].name, name, MAX_NAME - 1);
                strncpy(pr->funcs[pr->func_count].args, args, MAX_ARGS - 1);
                pr->funcs[pr->func_count].line_start = i;
                pr->funcs[pr->func_count].line_end = find_body_end(src, total_lines, i, indent);
                pr->funcs[pr->func_count].is_method = (current_class >= 0) ? 1 : 0;
                if (current_class >= 0) {
                    strncpy(pr->funcs[pr->func_count].parent_class,
                            pr->classes[current_class].name, MAX_NAME - 1);

                    /* Append method name to class methods list */
                    char *m = pr->classes[current_class].methods;
                    int ml = strlen(m);
                    if (ml > 0 && ml < MAX_BODY - strlen(name) - 2) {
                        m[ml++] = ',';
                        m[ml] = '\0';
                    }
                    if (ml < MAX_BODY - strlen(name) - 1) {
                        strcat(m, name);
                    }
                }
                pr->func_count++;
            }
            continue;
        }

        /* Import statements */
        if (starts_with(stripped, "import ") || starts_with(stripped, "from ")) {
            if (pr->import_count < 128) {
                char module[MAX_NAME] = "";
                char alias[MAX_NAME] = "";
                if (starts_with(stripped, "from ")) {
                    /* from X import Y */
                    char *p = stripped + 5;
                    while (*p && isspace((unsigned char)*p)) p++;
                    int mi = 0;
                    while (*p && !isspace((unsigned char)*p) && mi < sizeof(module) - 1) {
                        module[mi++] = *p++;
                    }
                    module[mi] = '\0';
                } else {
                    /* import X [as Y] */
                    char *p = stripped + 7;
                    while (*p && isspace((unsigned char)*p)) p++;
                    int mi = 0;
                    while (*p && !isspace((unsigned char)*p) && *p != ',' && mi < sizeof(module) - 1) {
                        module[mi++] = *p++;
                    }
                    module[mi] = '\0';
                    /* check for "as" alias */
                    char *as_pos = strstr(stripped, " as ");
                    if (as_pos) {
                        as_pos += 4;
                        int ai = 0;
                        while (*as_pos && !isspace((unsigned char)*as_pos) && ai < sizeof(alias) - 1) {
                            alias[ai++] = *as_pos++;
                        }
                        alias[ai] = '\0';
                    }
                }
                strncpy(pr->imports[pr->import_count].module, module, MAX_NAME - 1);
                strncpy(pr->imports[pr->import_count].alias, alias, MAX_NAME - 1);
                pr->imports[pr->import_count].line = i;
                pr->import_count++;
            }
            continue;
        }

        /* Module-level constants: UPPERCASE_NAME = ... */
        if (indent == 0 && *stripped != '\0') {
            /* Check if it's an assignment */
            char *eq = strchr(stripped, '=');
            if (eq && eq != stripped && eq[-1] != '=' && eq[1] != '=') {
                /* Extract name */
                char name[MAX_NAME] = "";
                int ni = 0;
                const char *p = stripped;
                while (*p && (isalnum((unsigned char)*p) || *p == '_') && ni < sizeof(name) - 1) {
                    name[ni++] = *p++;
                }
                name[ni] = '\0';
                /* Check if all uppercase */
                int is_upper = 1;
                for (int j = 0; j < ni; j++) {
                    if (name[j] != '_' && !isupper((unsigned char)name[j])) {
                        is_upper = 0;
                        break;
                    }
                }
                if (is_upper && ni > 0) {
                    /* Extract value (everything after =) */
                    char *val = eq + 1;
                    while (*val && (isspace((unsigned char)*val) || *val == ' ')) val++;
                    /* Trim trailing whitespace */
                    char *vend = val + strlen(val) - 1;
                    while (vend > val && isspace((unsigned char)*vend)) *vend-- = '\0';

                    /* Check if it's a regex pattern (re.compile) */
                    if (strstr(val, "re.compile(")) {
                        if (pr->regex_count < 64) {
                            strncpy(pr->regexes[pr->regex_count].var_name, name, MAX_NAME - 1);
                            strncpy(pr->regexes[pr->regex_count].pattern, val, MAX_BODY - 1);
                            pr->regexes[pr->regex_count].line = i;
                            pr->regex_count++;
                        }
                    }

                    if (pr->const_count < 256) {
                        strncpy(pr->consts[pr->const_count].name, name, MAX_NAME - 1);
                        strncpy(pr->consts[pr->const_count].value, val, MAX_BODY - 1);
                        pr->consts[pr->const_count].line = i;
                        pr->const_count++;
                    }
                }
            }
        }

        strncpy(prev_line, line, sizeof(prev_line) - 1);
    }
}

/* ════════════════════════════════════════════
 * DATABASE OPERATIONS
 * ════════════════════════════════════════════ */

static sqlite3 *open_db(const char *path) {
    sqlite3 *db = NULL;
    if (sqlite3_open(path, &db) != SQLITE_OK) {
        fprintf(stderr, "Cannot open database: %s\n", sqlite3_errmsg(db));
        return NULL;
    }
    char *err = NULL;
    if (sqlite3_exec(db, SCHEMA_SQL, NULL, NULL, &err) != SQLITE_OK) {
        fprintf(stderr, "Schema error: %s\n", err);
        sqlite3_free(err);
        sqlite3_close(db);
        return NULL;
    }
    return db;
}

static int ingest_file(sqlite3 *db, const char *filepath, const char *label) {
    long len = 0;
    char *content = read_file(filepath, &len);
    if (!content) {
        fprintf(stderr, "  FAIL: cannot read %s\n", filepath);
        return 0;
    }

    int total_lines = count_lines(content);
    ParseResult *pr = (ParseResult *)calloc(1, sizeof(ParseResult));
    if (!pr) { free(content); return 0; }
    parse_source(content, label, pr);

    sqlite3_stmt *stmt;
    char *err = NULL;

    /* Insert source file using prepared statement */
    const char *sql_sf = "INSERT OR REPLACE INTO source_files (filename, filepath, content, line_count) VALUES (?,?,?,?)";
    if (sqlite3_prepare_v2(db, sql_sf, -1, &stmt, NULL) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, label, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 2, filepath, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 3, content, (int)len, SQLITE_TRANSIENT);
        sqlite3_bind_int(stmt, 4, total_lines);
        if (sqlite3_step(stmt) != SQLITE_DONE) {
            fprintf(stderr, "  SQL error (source_files): %s\n", sqlite3_errmsg(db));
        }
        sqlite3_finalize(stmt);
    }

    /* Insert classes */
    const char *sql_cls = "INSERT INTO classes (source_file, class_name, methods, line_start, line_end) VALUES (?,?,?,?,?)";
    for (int i = 0; i < pr->class_count; i++) {
        if (sqlite3_prepare_v2(db, sql_cls, -1, &stmt, NULL) == SQLITE_OK) {
            sqlite3_bind_text(stmt, 1, label, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, pr->classes[i].name, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 3, pr->classes[i].methods, -1, SQLITE_TRANSIENT);
            sqlite3_bind_int(stmt, 4, pr->classes[i].line_start);
            sqlite3_bind_int(stmt, 5, pr->classes[i].line_end);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    }

    /* Insert functions */
    const char *sql_fn = "INSERT INTO functions (source_file, func_name, args, line_start, line_end, body, is_method, parent_class) VALUES (?,?,?,?,?,?,?,?)";
    for (int i = 0; i < pr->func_count; i++) {
        /* Extract body */
        char *body = (char *)malloc(MAX_BODY);
        if (!body) continue;
        int blen = 0;
        char line[MAX_LINE];
        for (int j = pr->funcs[i].line_start; j <= pr->funcs[i].line_end && blen < MAX_BODY - MAX_LINE; j++) {
            get_line(content, j, line, sizeof(line));
            int ll = (int)strlen(line);
            if (blen + ll + 2 < MAX_BODY) {
                memcpy(body + blen, line, ll);
                blen += ll;
                body[blen++] = '\n';
            }
        }
        body[blen] = '\0';

        if (sqlite3_prepare_v2(db, sql_fn, -1, &stmt, NULL) == SQLITE_OK) {
            sqlite3_bind_text(stmt, 1, label, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, pr->funcs[i].name, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 3, pr->funcs[i].args, -1, SQLITE_TRANSIENT);
            sqlite3_bind_int(stmt, 4, pr->funcs[i].line_start);
            sqlite3_bind_int(stmt, 5, pr->funcs[i].line_end);
            sqlite3_bind_text(stmt, 6, body, blen, SQLITE_TRANSIENT);
            sqlite3_bind_int(stmt, 7, pr->funcs[i].is_method);
            sqlite3_bind_text(stmt, 8, pr->funcs[i].parent_class, -1, SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
        free(body);
    }

    /* Insert constants */
    const char *sql_const = "INSERT INTO constants (source_file, name, value, line) VALUES (?,?,?,?)";
    for (int i = 0; i < pr->const_count; i++) {
        if (sqlite3_prepare_v2(db, sql_const, -1, &stmt, NULL) == SQLITE_OK) {
            sqlite3_bind_text(stmt, 1, label, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, pr->consts[i].name, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 3, pr->consts[i].value, -1, SQLITE_TRANSIENT);
            sqlite3_bind_int(stmt, 4, pr->consts[i].line);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    }

    /* Insert imports */
    const char *sql_imp = "INSERT INTO imports (source_file, module, alias, line) VALUES (?,?,?,?)";
    for (int i = 0; i < pr->import_count; i++) {
        if (sqlite3_prepare_v2(db, sql_imp, -1, &stmt, NULL) == SQLITE_OK) {
            sqlite3_bind_text(stmt, 1, label, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, pr->imports[i].module, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 3, pr->imports[i].alias, -1, SQLITE_TRANSIENT);
            sqlite3_bind_int(stmt, 4, pr->imports[i].line);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    }

    /* Insert regex patterns */
    const char *sql_rx = "INSERT INTO regex_patterns (source_file, var_name, pattern, line) VALUES (?,?,?,?)";
    for (int i = 0; i < pr->regex_count; i++) {
        if (sqlite3_prepare_v2(db, sql_rx, -1, &stmt, NULL) == SQLITE_OK) {
            sqlite3_bind_text(stmt, 1, label, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, pr->regexes[i].var_name, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 3, pr->regexes[i].pattern, -1, SQLITE_TRANSIENT);
            sqlite3_bind_int(stmt, 4, pr->regexes[i].line);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    }

    int rc = pr->class_count + pr->func_count + pr->const_count;
    printf("  OK %s: %d classes, %d funcs, %d consts, %d imports, %d regexes, %d lines\n",
           label, pr->class_count, pr->func_count, pr->const_count, pr->import_count, pr->regex_count, total_lines);
    free(pr);
    free(content);
    return rc > 0 ? 1 : 0;
}

static int ingest_directory_recursive(sqlite3 *db, const char *dir, int *total) {
    DIR *d = opendir(dir);
    if (!d) return 0;
    int count = 0;
    struct dirent *entry;
    while ((entry = readdir(d)) != NULL) {
        if (entry->d_name[0] == '.') continue;

        char path[MAX_NAME * 4];
        snprintf(path, sizeof(path), "%s/%s", dir, entry->d_name);
        struct stat st;
        if (stat(path, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            /* Skip __pycache__ and hidden dirs */
            if (strcmp(entry->d_name, "__pycache__") == 0) continue;
            /* Skip common non-code dirs */
            if (strcmp(entry->d_name, "node_modules") == 0) continue;
            if (strcmp(entry->d_name, ".git") == 0) continue;
            count += ingest_directory_recursive(db, path, total);
            continue;
        }

        if (!S_ISREG(st.st_mode)) continue;
        size_t len = strlen(entry->d_name);
        if (len < 3 || strcmp(entry->d_name + len - 3, ".py") != 0) continue;

        /* Use relative path from initial dir as label */
        char label[MAX_NAME];
        strncpy(label, entry->d_name, sizeof(label) - 1);
        label[sizeof(label) - 1] = '\0';
        char *dot = strrchr(label, '.');
        if (dot) *dot = '\0';

        if (ingest_file(db, path, label)) {
            count++;
            (*total)++;
        }
    }
    closedir(d);
    return count;
}

static int ingest_directory(sqlite3 *db, const char *dir) {
    int total = 0;
    ingest_directory_recursive(db, dir, &total);
    return total;
}

static void show_status(sqlite3 *db) {
    char sql[] = "SELECT 'source_files', COUNT(*) FROM source_files "
                 "UNION ALL SELECT 'classes', COUNT(*) FROM classes "
                 "UNION ALL SELECT 'functions', COUNT(*) FROM functions "
                 "UNION ALL SELECT 'constants', COUNT(*) FROM constants "
                 "UNION ALL SELECT 'imports', COUNT(*) FROM imports "
                 "UNION ALL SELECT 'regex_patterns', COUNT(*) FROM regex_patterns";
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) == SQLITE_OK) {
        printf("\n=== DATABASE STATUS ===\n");
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            printf("  %s: %d rows\n", sqlite3_column_text(stmt, 0), sqlite3_column_int(stmt, 1));
        }
        sqlite3_finalize(stmt);
    }

    /* Show classes summary */
    char sql2[] = "SELECT source_file, class_name, methods FROM classes ORDER BY source_file, class_name";
    if (sqlite3_prepare_v2(db, sql2, -1, &stmt, NULL) == SQLITE_OK) {
        printf("\n=== CLASSES ===\n");
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const char *sf = (const char *)sqlite3_column_text(stmt, 0);
            const char *cn = (const char *)sqlite3_column_text(stmt, 1);
            const char *ms = (const char *)sqlite3_column_text(stmt, 2);
            int mc = 0;
            if (ms && *ms) {
                mc = 1;
                for (const char *p = ms; *p; p++) if (*p == ',') mc++;
            }
            printf("  %s.%s: %d methods\n", sf, cn, mc);
        }
        sqlite3_finalize(stmt);
    }

    /* Show function count per file */
    char sql3[] = "SELECT source_file, COUNT(*), SUM(is_method) FROM functions GROUP BY source_file ORDER BY source_file";
    if (sqlite3_prepare_v2(db, sql3, -1, &stmt, NULL) == SQLITE_OK) {
        printf("\n=== FUNCTIONS PER FILE ===\n");
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            printf("  %s: %d total (%d methods, %d top-level)\n",
                   sqlite3_column_text(stmt, 0),
                   sqlite3_column_int(stmt, 1),
                   sqlite3_column_int(stmt, 2),
                   sqlite3_column_int(stmt, 1) - sqlite3_column_int(stmt, 2));
        }
        sqlite3_finalize(stmt);
    }
}

static void run_query(sqlite3 *db, const char *sql) {
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "Query error: %s\n", sqlite3_errmsg(db));
        return;
    }
    int cols = sqlite3_column_count(stmt);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        for (int i = 0; i < cols; i++) {
            if (i > 0) printf(" | ");
            const char *val = (const char *)sqlite3_column_text(stmt, i);
            printf("%s", val ? val : "NULL");
        }
        printf("\n");
    }
    sqlite3_finalize(stmt);
}

/* ════════════════════════════════════════════
 * MAIN
 * ════════════════════════════════════════════ */

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr,
            "Usage: codeingest <file.py|dir> [-o output.db] [--status] [--json] [--schema] [--query db sql]\n");
        return 1;
    }

    /* Handle --schema */
    if (strcmp(argv[1], "--schema") == 0) {
        printf("%s", SCHEMA_SQL);
        return 0;
    }

    /* Handle --query */
    if (strcmp(argv[1], "--query") == 0) {
        if (argc < 4) {
            fprintf(stderr, "Usage: codeingest --query <db> <sql>\n");
            return 1;
        }
        sqlite3 *db = NULL;
        if (sqlite3_open(argv[2], &db) != SQLITE_OK) {
            fprintf(stderr, "Cannot open: %s\n", argv[2]);
            return 1;
        }
        run_query(db, argv[3]);
        sqlite3_close(db);
        return 0;
    }

    /* Parse args */
    const char *input = argv[1];
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) {
            strncpy(output_db, argv[++i], sizeof(output_db) - 1);
        } else if (strcmp(argv[i], "--status") == 0) {
            opt_status = 1;
        } else if (strcmp(argv[i], "--json") == 0) {
            opt_json = 1;
        }
    }

    sqlite3 *db = open_db(output_db);
    if (!db) return 1;

    struct stat st;
    if (stat(input, &st) != 0) {
        fprintf(stderr, "Path not found: %s\n", input);
        sqlite3_close(db);
        return 1;
    }

    int count = 0;
    if (S_ISDIR(st.st_mode)) {
        printf("Ingesting directory: %s → %s\n", input, output_db);
        count = ingest_directory(db, input);
        printf("\nIngested %d files\n", count);
    } else {
        char label[MAX_NAME];
        const char *base = strrchr(input, '/');
        strncpy(label, base ? base + 1 : input, sizeof(label) - 1);
        label[sizeof(label) - 1] = '\0';
        char *dot = strrchr(label, '.');
        if (dot) *dot = '\0';
        printf("Ingesting: %s → %s\n", input, output_db);
        count = ingest_file(db, input, label) ? 1 : 0;
    }

    if (opt_status) {
        show_status(db);
    }

    sqlite3_close(db);
    return count > 0 ? 0 : 1;
}
