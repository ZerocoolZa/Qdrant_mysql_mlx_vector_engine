/*
 * cascade_utils.h — Shared utilities for all Cascade CLI tools
 *
 * This is the "common aspect" — MySQL connection, string escaping,
 * file reading, CLI helpers. Every tool includes this and drops its
 * duplicate code.
 *
 * Think of this as the shared config layer that smartcli and all
 * tools use. One copy of the common stuff, used everywhere.
 */

#ifndef CASCADE_UTILS_H
#define CASCADE_UTILS_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

/* MySQL header — only needed by tools that do DB operations */
/* Tools that use MySQL should add: -I<mysql include path> and include mysql.h themselves */
#ifdef CASCADE_USE_MYSQL
#include <mysql.h>
#endif

/* ── MySQL defaults (shared across all tools) ── */
#define CASCADE_HOST    "localhost"
#define CASCADE_USER    "root"
#define CASCADE_PASS    ""
#define CASCADE_PORT    3306
#define CASCADE_DB      "vb_shared"

/* ── Buffer sizes ── */
#define CASCADE_BUF     8192
#define CASCADE_BIGBUF  65536
#define CASCADE_MAXBUF  1048576  /* 1MB */

/* ════════════════════════════════════════════
 * MYSQL CONNECTION HELPER
 * One call, returns connected MYSQL* or NULL
 * Only compiled when tool defines CASCADE_USE_MYSQL
 * ════════════════════════════════════════════ */

#ifdef CASCADE_USE_MYSQL
static MYSQL *cascade_mysql_connect(const char *host,
                                     const char *user,
                                     const char *pass,
                                     const char *db,
                                     int port) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) return NULL;

    if (!mysql_real_connect(conn,
            host ? host : CASCADE_HOST,
            user ? user : CASCADE_USER,
            pass ? pass : CASCADE_PASS,
            db ? db : CASCADE_DB,
            port ? port : CASCADE_PORT, NULL, 0)) {
        mysql_close(conn);
        return NULL;
    }
    return conn;
}
#endif

/* ════════════════════════════════════════════
 * STRING ESCAPING
 * ════════════════════════════════════════════ */

/* Escape keyword for LIKE clauses (%, _, \) */
static void cascade_escape_like(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 2 < out_sz; i++) {
        if (in[i] == '%' || in[i] == '_' || in[i] == '\\')
            out[j++] = '\\';
        out[j++] = in[i];
    }
    out[j] = '\0';
}

/* Escape string for JSON output */
static void cascade_json_escape(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 6 < out_sz; i++) {
        unsigned char c = (unsigned char)in[i];
        if (c == '"')       { out[j++] = '\\'; out[j++] = '"'; }
        else if (c == '\\') { out[j++] = '\\'; out[j++] = '\\'; }
        else if (c == '\n') { out[j++] = '\\'; out[j++] = 'n'; }
        else if (c == '\r') { out[j++] = '\\'; out[j++] = 'r'; }
        else if (c == '\t') { out[j++] = '\\'; out[j++] = 't'; }
        else if (c < 32)    { j += snprintf(out + j, out_sz - j, "\\u%04x", c); }
        else                { out[j++] = c; }
    }
    out[j] = '\0';
}

/* ════════════════════════════════════════════
 * FILE READING
 * ════════════════════════════════════════════ */

static char *cascade_read_file(const char *path, char *buf, size_t bufsize) {
    FILE *f = fopen(path, "r");
    if (!f) return NULL;
    size_t n = fread(buf, 1, bufsize - 1, f);
    buf[n] = '\0';
    fclose(f);
    return buf;
}

/* ════════════════════════════════════════════
 * COLUMN TYPE CHECK
 * ════════════════════════════════════════════ */

static int cascade_is_text_type(const char *type) {
    return !strcasecmp(type, "char") ||
           !strcasecmp(type, "varchar") ||
           !strcasecmp(type, "text") ||
           !strcasecmp(type, "tinytext") ||
           !strcasecmp(type, "mediumtext") ||
           !strcasecmp(type, "longtext");
}

/* ════════════════════════════════════════════
 * LINE NUMBER HELPER
 * ════════════════════════════════════════════ */

static int cascade_line_for_pos(const char *content, int pos) {
    int line = 1;
    for (int i = 0; i < pos && content[i]; i++)
        if (content[i] == '\n') line++;
    return line;
}

/* ════════════════════════════════════════════
 * TOOL REGISTRY (for smartcli)
 * Each tool registers its name and entry point
 * ════════════════════════════════════════════ */

typedef int (*tool_fn)(int argc, char **argv);

typedef struct {
    const char *name;       /* command name */
    const char *binary;     /* path to standalone binary */
    const char *description;
    const char *help_text;
} ToolEntry;

#endif /* CASCADE_UTILS_H */
