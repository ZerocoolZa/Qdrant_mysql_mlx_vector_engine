/*
 * msearch.c v6 — Context Reconstruction Engine
 *
 * v6 NEW: --context-reconstruct Multi-Radius Context Packet
 *  19. Chat radius — find keyword in chat history, extract ±N messages
 *  20. Multi-dimensional radius — text, dependency, conversation, semantic
 *  21. Context packet — merged neighborhood from all dimensions
 *  22. Timeline view — chronological context from chat + code + history
 *
 * v5: --smart Consolidated Semantic Object (10 sections, 1 query)
 *  18. Smart mode — Authority, Summary, Files, Methods, Dependencies,
 *      Rules, Related, History, Confidence, Actions in one pass
 *
 * 12 MySQL Enhancements:
 *  1. Registry-first routing (table_registry)
 *  2. What/Where/Why output (purpose, type, notes)
 *  3. Semantic type filter (--type)
 *  4. BCL bracket awareness (auto-detect [@Token], dom_*, [INTENT)
 *  5. Code class dump mode (--dump)
 *  6. Context-aware ranking (--context)
 *  7. Update routing (--where)
 *  8. JSON output mode (--json)
 *  9. Cross-database search (--all-db)
 * 10. Class understandings integration
 * 11. Status pipeline awareness (--status)
 * 12. Four truth streams (--truth)
 *
 * 5 Qdrant Vector Search Enhancements (v4):
 * 13. Semantic vector search (--semantic)
 * 14. Dimension selection (--dimension)
 * 15. Multi-dimension search (--multi)
 * 16. Qdrant collection stats (--qstats)
 * 17. Hybrid MySQL + Qdrant search (--hybrid)
 *
 * Compile:
 *   cc -O2 -I/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/include/mysql -o msearch msearch.c \
 *      -L/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/lib -lmysqlclient -lz -L/opt/homebrew/lib -lssl -lcrypto -lresolv
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <mysql.h>
#include "discovery.h"

/* ── constants ── */
#define MAX_TABLES 1024
#define MAX_COLS   512
#define BUF        8192
#define BIGBUF     65536
#define MAX_DB     32
#define MAX_KEYWORDS 16

/* Qdrant helper script path */
#define QDRANT_HELPER "/Users/wws/bin/msearch_qdrant.py"
#define QDRANT_DEFAULT_COLLECTION "dim_semantic"
#define QDRANT_DEFAULT_TOP 10

static const char *DEF_HOST = "localhost";
static const char *DEF_USER = "root";
static const char *DEF_PASS = "";
static const char *DEF_DB   = "vb_shared";
static int  DEF_PORT = 3306;
static int  DEF_LIMIT = 50;

/* ── table schema with registry metadata ── */
typedef struct {
    char table[256];
    char cols[MAX_COLS][256];
    int  col_count;
    /* registry metadata (#1, #2) */
    char table_type[64];
    char purpose[512];
    char contains[512];
    char notes[512];
    char related_tables[256];
    int  has_registry;
    /* relevance score for ranking (#6) */
    int  relevance;
} TableSchema;

static TableSchema schema[MAX_TABLES];
static int table_count = 0;

/* ── flags ── */
static int  opt_json = 0;
static int  opt_dump = 0;
static int  opt_all_db = 0;
static int  opt_where = 0;
static int  opt_truth = 0;
static const char *opt_type = NULL;
static const char *opt_context = NULL;
static const char *opt_status = NULL;
static const char *opt_host = NULL;
static const char *opt_user = NULL;
static const char *opt_pass = NULL;
static int  opt_port = 0;
static int  opt_vbstyle = 0;  /* --vbstyle: run vbcheck on a file */
static int  opt_verbose = 0;
static int  opt_count = 0;       /* --count: show match counts per table, no rows */
static int  opt_deep = 0;        /* --deep: include data_table types (huge LONGTEXT dumps) */
static int  opt_fulltext = 1;    /* --no-fulltext: disable FULLTEXT, force LIKE */
static int  opt_all_mysql = 0;   /* --all-mysql: auto-discover ALL databases */
static int  opt_multi_kw = 0;    /* multi-keyword mode */
static char opt_kw_mode[8] = "or"; /* --and: require all keywords */
static int  opt_smart = 0;       /* --smart: consolidated semantic object */
static int  opt_context_recon = 0;  /* --context-reconstruct: multi-radius context packet */
static int  opt_radius = 200;       /* --radius N: context radius (lines or messages) */
static int  opt_mode = 0;           /* --mode: 0=magnetic(substring), 1=exact, 2=prefix, 3=regex */
static int  opt_web = 0;           /* --web: external discovery layer */

/* Qdrant flags (v4) */
static int  opt_semantic = 0;     /* --semantic: Qdrant vector search */
static int  opt_multi = 0;        /* --multi: search multiple Qdrant dimensions */
static int  opt_hybrid = 0;       /* --hybrid: MySQL + Qdrant combined */
static int  opt_qstats = 0;       /* --qstats: Qdrant collection stats */
static const char *opt_dimension = NULL;  /* --dimension: Qdrant collection name */
static int  opt_top = 0;          /* --top: number of vector results */

/* ════════════════════════════════════════════
 * UTILITIES
 * ════════════════════════════════════════════ */

static int is_text_type(const char *type) {
    return !strcasecmp(type, "char") ||
           !strcasecmp(type, "varchar") ||
           !strcasecmp(type, "text") ||
           !strcasecmp(type, "tinytext") ||
           !strcasecmp(type, "mediumtext") ||
           !strcasecmp(type, "longtext");
}

static void escape_like(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 2 < out_sz; i++) {
        if (in[i] == '%' || in[i] == '_' || in[i] == '\\')
            out[j++] = '\\';
        out[j++] = in[i];
    }
    out[j] = '\0';
}

/* v6: Build SQL match expression for a column based on --mode */
/* mode 0=magnetic: LIKE '%kw%' (substring, default) */
/* mode 1=exact:   = 'kw' (exact match only) */
/* mode 2=prefix:  LIKE 'kw%' (starts with) */
/* mode 3=regex:   REGEXP 'kw' (MySQL regex) */
static void match_expr(char *out, size_t sz, const char *col, const char *keyword) {
    char esc[1024];
    /* Handle table.column — wrap each part in backticks separately */
    char colbuf[256];
    const char *dot = strchr(col, '.');
    if (dot) {
        char tbl[128], clm[128];
        size_t tlen = dot - col;
        memcpy(tbl, col, tlen); tbl[tlen] = '\0';
        strncpy(clm, dot + 1, sizeof(clm) - 1); clm[sizeof(clm)-1] = '\0';
        snprintf(colbuf, sizeof(colbuf), "`%s`.`%s`", tbl, clm);
    } else {
        snprintf(colbuf, sizeof(colbuf), "`%s`", col);
    }
    switch (opt_mode) {
        case 1: /* exact */
            escape_like(keyword, esc, sizeof(esc));
            snprintf(out, sz, "%s = '%s'", colbuf, esc);
            break;
        case 2: /* prefix */
            escape_like(keyword, esc, sizeof(esc));
            snprintf(out, sz, "%s LIKE '%s%%'", colbuf, esc);
            break;
        case 3: /* regex */
            escape_like(keyword, esc, sizeof(esc));
            snprintf(out, sz, "%s REGEXP '%s'", colbuf, keyword);
            break;
        default: /* magnetic (substring) */
            escape_like(keyword, esc, sizeof(esc));
            snprintf(out, sz, "%s LIKE '%%%s%%'", colbuf, esc);
            break;
    }
}

/* escape single quotes for shell commands (prevents injection) */
static void shell_escape(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 2 < out_sz; i++) {
        if (in[i] == '\'') { out[j++] = '\''; out[j++] = '\''; }
        else if (in[i] == ';') { out[j++] = '\\'; out[j++] = ';'; }
        else if (in[i] == '|') { out[j++] = '\\'; out[j++] = '|'; }
        else if (in[i] == '&') { out[j++] = '\\'; out[j++] = '&'; }
        else if (in[i] == '`') { out[j++] = '\\'; out[j++] = '`'; }
        else if (in[i] == '$') { out[j++] = '\\'; out[j++] = '$'; }
        else if (in[i] == '(' || in[i] == ')') { out[j++] = '\\'; out[j++] = in[i]; }
        else out[j++] = in[i];
    }
    out[j] = '\0';
}

/* escape string for JSON output (#8) */
static void json_escape(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 6 < out_sz; i++) {
        unsigned char c = (unsigned char)in[i];
        if (c == '"') { out[j++] = '\\'; out[j++] = '"'; }
        else if (c == '\\') { out[j++] = '\\'; out[j++] = '\\'; }
        else if (c == '\n') { out[j++] = '\\'; out[j++] = 'n'; }
        else if (c == '\r') { out[j++] = '\\'; out[j++] = 'r'; }
        else if (c == '\t') { out[j++] = '\\'; out[j++] = 't'; }
        else if (c < 32) { j += snprintf(out + j, out_sz - j, "\\u%04x", c); }
        else out[j++] = c;
    }
    out[j] = '\0';
}

/* ════════════════════════════════════════════
 * ENHANCEMENT #1: REGISTRY-FIRST ROUTING
 * Load table_registry to know what each table is
 * ════════════════════════════════════════════ */

static void load_registry(MYSQL *conn) {
    /* Check if table_registry exists */
    if (mysql_query(conn, "SELECT COUNT(*) FROM table_registry"))
        return;

    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) return;
    mysql_free_result(res);

    /* Load registry entries */
    if (mysql_query(conn,
        "SELECT table_name, table_type, purpose, `contains`, notes, related_tables "
        "FROM table_registry"))
        return;

    res = mysql_store_result(conn);
    if (!res) return;

    int unmatched = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        const char *tname = row[0] ? row[0] : "";
        int found = 0;
        /* find matching schema entry */
        for (int i = 0; i < table_count; i++) {
            if (strcmp(schema[i].table, tname) == 0) {
                strncpy(schema[i].table_type, row[1] ? row[1] : "", 63);
                strncpy(schema[i].purpose, row[2] ? row[2] : "", 511);
                strncpy(schema[i].contains, row[3] ? row[3] : "", 511);
                strncpy(schema[i].notes, row[4] ? row[4] : "", 511);
                strncpy(schema[i].related_tables, row[5] ? row[5] : "", 255);
                schema[i].has_registry = 1;
                found = 1;
                break;
            }
        }
        /* fix #6: warn about registry entries not in SHOW TABLES */
        if (!found) {
            unmatched++;
            if (opt_verbose)
                fprintf(stderr, "Registry entry '%s' not found in schema (table may not exist yet)\n", tname);
        }
    }
    if (unmatched > 0 && opt_verbose)
        fprintf(stderr, "load_registry: %d registry entries had no matching table\n", unmatched);
    mysql_free_result(res);
}

/* ════════════════════════════════════════════
 * ENHANCEMENT #4: BCL BRACKET AWARENESS
 * Detect keyword pattern and route to correct tables
 * ════════════════════════════════════════════ */

static const char *detect_route(const char *keyword) {
    /* [@TokenName] pattern -> token tables */
    if (keyword[0] == '[' && keyword[1] == '@')
        return "token_table";
    /* dom_* pattern -> code tables */
    if (strncmp(keyword, "dom_", 4) == 0)
        return "code_table";
    /* [INTENT or [PURPOSE pattern -> code_registry */
    if (keyword[0] == '[' && (strstr(keyword, "INTENT") || strstr(keyword, "PURPOSE")))
        return "code_table";
    /* err_ or error -> err_tokens + know_problems */
    if (strstr(keyword, "err") || strstr(keyword, "error") || strstr(keyword, "fix"))
        return "token_table";
    /* workflow or flow -> flow_tokens */
    if (strstr(keyword, "workflow") || strstr(keyword, "flow"))
        return "token_table";
    /* default -> meta_table (instructions) */
    return NULL; /* NULL = search all */
}

/* ════════════════════════════════════════════
 * ENHANCEMENT #6: CONTEXT-AWARE RANKING
 * Score tables by relevance to search context
 * ════════════════════════════════════════════ */

static void score_relevance(const char *keyword, const char *context) {
    for (int i = 0; i < table_count; i++) {
        int score = 0;
        /* keyword match in purpose boosts score */
        if (schema[i].has_registry) {
            if (schema[i].purpose[0] && strcasestr(schema[i].purpose, keyword))
                score += 10;
            if (schema[i].contains[0] && strcasestr(schema[i].contains, keyword))
                score += 5;
            if (schema[i].notes[0] && strcasestr(schema[i].notes, keyword))
                score += 3;
        }
        /* context boost */
        if (context && schema[i].has_registry) {
            if (schema[i].purpose[0] && strcasestr(schema[i].purpose, context))
                score += 8;
            if (schema[i].notes[0] && strcasestr(schema[i].notes, context))
                score += 4;
        }
        /* meta_table gets boost for plain English keywords */
        if (schema[i].has_registry && strcmp(schema[i].table_type, "meta_table") == 0)
            score += 2;
        /* code_table gets boost for dom_ keywords */
        if (strncmp(keyword, "dom_", 4) == 0 &&
            schema[i].has_registry && strcmp(schema[i].table_type, "code_table") == 0)
            score += 15;
        /* token_table gets boost for [@ keywords */
        if (keyword[0] == '[' && keyword[1] == '@' &&
            schema[i].has_registry && strcmp(schema[i].table_type, "token_table") == 0)
            score += 15;

        schema[i].relevance = score;
    }
}

/* strcasestr is available on macOS string.h */

/* sort tables by relevance (highest first) */
static void sort_by_relevance(void) {
    for (int i = 0; i < table_count - 1; i++) {
        for (int j = i + 1; j < table_count; j++) {
            if (schema[j].relevance > schema[i].relevance) {
                TableSchema tmp = schema[i];
                schema[i] = schema[j];
                schema[j] = tmp;
            }
        }
    }
}

/* ════════════════════════════════════════════
 * SCHEMA LOADING
 * ════════════════════════════════════════════ */

static void load_schema(MYSQL *conn, const char *db) {
    if (mysql_query(conn, "SHOW TABLES")) {
        if (opt_verbose)
            fprintf(stderr, "load_schema: SHOW TABLES failed: %s\n", mysql_error(conn));
        return;
    }

    MYSQL_RES *res = mysql_store_result(conn);
    MYSQL_ROW row;

    table_count = 0;

    while ((row = mysql_fetch_row(res)) && table_count < MAX_TABLES) {
        strncpy(schema[table_count].table, row[0], 255);
        schema[table_count].col_count = 0;
        schema[table_count].has_registry = 0;
        schema[table_count].table_type[0] = '\0';
        schema[table_count].purpose[0] = '\0';
        schema[table_count].contains[0] = '\0';
        schema[table_count].notes[0] = '\0';
        schema[table_count].related_tables[0] = '\0';
        schema[table_count].relevance = 0;

        char q[512];
        snprintf(q, sizeof(q),
            "SELECT COLUMN_NAME, DATA_TYPE "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s'",
            db, row[0]);

        if (mysql_query(conn, q)) {
            if (opt_verbose)
                fprintf(stderr, "load_schema: column query failed for %s: %s\n", row[0], mysql_error(conn));
            continue;
        }

        MYSQL_RES *cres = mysql_store_result(conn);
        MYSQL_ROW crow;

        while ((crow = mysql_fetch_row(cres)) &&
               schema[table_count].col_count < MAX_COLS) {
            if (is_text_type(crow[1])) {
                strncpy(schema[table_count]
                        .cols[schema[table_count].col_count++],
                        crow[0], 255);
            }
        }

        mysql_free_result(cres);

        if (schema[table_count].col_count > 0)
            table_count++;
    }

    mysql_free_result(res);

    /* #1: Load registry metadata after schema */
    load_registry(conn);
}

/* ════════════════════════════════════════════
 * ENHANCEMENT #7: UPDATE ROUTING
 * Tell brain where to store new things
 * ════════════════════════════════════════════ */

static void show_where_to_store(MYSQL *conn, const char *keyword) {
    printf("=== UPDATE ROUTING FOR: %s ===\n\n", keyword);

    /* Search table_registry for relevant tables */
    char escaped[1024];
    escape_like(keyword, escaped, sizeof(escaped));

    char q[BUF];
    snprintf(q, sizeof(q),
        "SELECT table_name, table_type, purpose, `contains`, notes "
        "FROM table_registry WHERE purpose LIKE '%%%s%%' "
        "OR `contains` LIKE '%%%s%%' OR notes LIKE '%%%s%%'",
        escaped, escaped, escaped);

    if (mysql_query(conn, q)) {
        printf("Could not query table_registry.\n");
        return;
    }

    MYSQL_RES *res = mysql_store_result(conn);
    if (!res || mysql_num_rows(res) == 0) {
        printf("No matching table found for '%s'.\n", keyword);
        printf("Suggested: store in instructions (category=general, priority=0)\n");
        if (res) mysql_free_result(res);
        return;
    }

    MYSQL_ROW row;
    int idx = 0;
    while ((row = mysql_fetch_row(res))) {
        const char *tname = row[0] ? row[0] : "";
        const char *ttype = row[1] ? row[1] : "";
        const char *purpose = row[2] ? row[2] : "";
        const char *contains = row[3] ? row[3] : "";
        const char *notes = row[4] ? row[4] : "";

        printf("[%d] TABLE: %s\n", ++idx, tname);
        printf("    TYPE: %s\n", ttype);
        printf("    PURPOSE: %s\n", purpose);
        printf("    COLUMNS: %s\n", contains);
        printf("    NOTES: %s\n\n", notes);

        /* Get actual columns from INFORMATION_SCHEMA */
        char cq[512];
        snprintf(cq, sizeof(cq),
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s' ORDER BY ORDINAL_POSITION",
            DEF_DB, tname);

        if (mysql_query(conn, cq)) continue;
        MYSQL_RES *cres = mysql_store_result(conn);
        if (!cres) continue;

        printf("    ACTUAL COLUMNS: ");
        MYSQL_ROW crow;
        int first = 1;
        while ((crow = mysql_fetch_row(cres))) {
            printf("%s%s", first ? "" : ", ", crow[0] ? crow[0] : "");
            first = 0;
        }
        printf("\n\n");
        mysql_free_result(cres);
    }

    mysql_free_result(res);
}

/* ════════════════════════════════════════════
 * ENHANCEMENT #10: CLASS UNDERSTANDINGS
 * Fetch understanding for code_classes matches
 * ════════════════════════════════════════════ */

static void fetch_understanding(MYSQL *conn, const char *class_name) {
    char q[512];
    char escaped[256];
    escape_like(class_name, escaped, sizeof(escaped));
    snprintf(q, sizeof(q),
        "SELECT cascade_understanding, wayne_understanding, layer "
        "FROM class_understandings WHERE class_name='%s'", escaped);

    if (mysql_query(conn, q)) return;
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) return;

    MYSQL_ROW row = mysql_fetch_row(res);
    if (row) {
        if (opt_json) {
            char esc_cascade[BUF], esc_wayne[BUF];
            json_escape(row[0] ? row[0] : "", esc_cascade, sizeof(esc_cascade));
            json_escape(row[1] ? row[1] : "", esc_wayne, sizeof(esc_wayne));
            printf(",\"cascade_understanding\":\"%s\"", esc_cascade);
            printf(",\"wayne_understanding\":\"%s\"", esc_wayne);
            printf(",\"layer\":\"%s\"", row[2] ? row[2] : "");
        } else {
            printf("    UNDERSTANDING (cascade): %s\n", row[0] ? row[0] : "(none)");
            printf("    UNDERSTANDING (wayne): %s\n", row[1] ? row[1] : "(none)");
            printf("    LAYER: %s\n", row[2] ? row[2] : "(none)");
        }
    }
    mysql_free_result(res);
}

/* ════════════════════════════════════════════
 * SEARCH ENGINE — ENHANCED
 * ════════════════════════════════════════════ */

static void search(MYSQL *conn, const char *keyword,
                   const char *table_filter,
                   const char *db,
                   int limit) {

    char escaped[1024];
    escape_like(keyword, escaped, sizeof(escaped));

    /* #4: Auto-detect route from keyword pattern */
    const char *auto_route = detect_route(keyword);
    const char *active_type = opt_type ? opt_type : auto_route;

    /* #6: Score and sort by relevance */
    score_relevance(keyword, opt_context);
    if (opt_context || auto_route)
        sort_by_relevance();

    int total = 0;
    int first_table = 1;

    if (opt_json) printf("[");

    for (int i = 0; i < table_count; i++) {

        /* table name filter */
        if (table_filter && !strstr(schema[i].table, table_filter))
            continue;

        /* #3: semantic type filter */
        if (active_type && schema[i].has_registry) {
            if (strcmp(schema[i].table_type, active_type) != 0)
                continue;
        }

        /* v5: skip data_table by default (huge LONGTEXT dumps) unless --deep */
        if (!opt_deep && schema[i].has_registry &&
            strcmp(schema[i].table_type, "data_table") == 0)
            continue;

        if (schema[i].col_count == 0)
            continue;

        /* build WHERE clause — cursor-based (fix #2: no strncat in loops) */
        char where[BUF];
        size_t wpos = 0;

        for (int c = 0; c < schema[i].col_count; c++) {
            int written = snprintf(where + wpos, sizeof(where) - wpos,
                     "%s`%s` LIKE '%%%s%%'",
                     (c ? " OR " : ""),
                     schema[i].cols[c],
                     escaped);
            if (written < 0 || (size_t)written >= sizeof(where) - wpos) break;
            wpos += written;
        }

        /* #11: status filter */
        if (opt_status) {
            int written = snprintf(where + wpos, sizeof(where) - wpos,
                " AND `status` LIKE '%%%s%%'", opt_status);
            if (written > 0 && (size_t)written < sizeof(where) - wpos)
                wpos += written;
        }

        char sql[BUF * 2];

        /* v5: --count mode — just count matches, don't fetch rows */
        if (opt_count) {
            snprintf(sql, sizeof(sql),
                "SELECT COUNT(*) FROM `%s` WHERE %s",
                schema[i].table, where);
            if (mysql_query(conn, sql)) {
                if (opt_verbose)
                    fprintf(stderr, "SQL error on %s: %s\n", schema[i].table, mysql_error(conn));
                continue;
            }
            MYSQL_RES *cres = mysql_store_result(conn);
            if (!cres) continue;
            MYSQL_ROW crow = mysql_fetch_row(cres);
            int cnt = crow[0] ? atoi(crow[0]) : 0;
            if (cnt > 0) {
                printf("  %-40s %d matches\n", schema[i].table, cnt);
                total += cnt;
            }
            mysql_free_result(cres);
            continue;
        }

        snprintf(sql, sizeof(sql),
            "SELECT * FROM `%s` WHERE %s LIMIT %d",
            schema[i].table, where, limit);

        if (mysql_query(conn, sql)) {
            if (opt_verbose)
                fprintf(stderr, "SQL error on %s: %s\n", schema[i].table, mysql_error(conn));
            continue;
        }

        MYSQL_RES *res = mysql_store_result(conn);
        MYSQL_ROW row;

        int row_idx = 0;
        int is_code_classes = (strcmp(schema[i].table, "code_classes") == 0);

        while ((row = mysql_fetch_row(res))) {
            unsigned long *lens = mysql_fetch_lengths(res);
            MYSQL_FIELD *fields = mysql_fetch_fields(res);
            int fcount = mysql_num_fields(res);

            if (row_idx == 0) {
                if (opt_json) {
                    if (!first_table) printf(",");
                    first_table = 0;
                    printf("{\"table\":\"%s\"", schema[i].table);
                    /* #2: what/where/why */
                    if (schema[i].has_registry) {
                        char esc_p[BUF], esc_n[BUF];
                        json_escape(schema[i].purpose, esc_p, sizeof(esc_p));
                        json_escape(schema[i].notes, esc_n, sizeof(esc_n));
                        printf(",\"what\":\"%s\"", esc_p);
                        printf(",\"where\":\"%s\"", schema[i].table_type);
                        printf(",\"why\":\"%s\"", esc_n);
                    }
                    printf(",\"rows\":[");
                } else {
                    printf("\n=== TABLE: %s", schema[i].table);
                    /* #2: what/where/why */
                    if (schema[i].has_registry) {
                        printf(" [%s]", schema[i].table_type);
                        if (schema[i].purpose[0])
                            printf("\n  WHAT: %s", schema[i].purpose);
                        if (schema[i].notes[0])
                            printf("\n  WHY: %s", schema[i].notes);
                    }
                    /* #6: show relevance score if context mode */
                    if (opt_context && schema[i].relevance > 0)
                        printf(" (relevance: %d)", schema[i].relevance);
                    printf("\n");
                }
            }

            if (opt_json) {
                if (row_idx > 0) printf(",");
                printf("{");
                for (int f = 0; f < fcount; f++) {
                    if (f > 0) printf(",");
                    char esc_val[BIGBUF];
                    /* #5: dump mode — full class_code for code_classes */
                    if (opt_dump && is_code_classes &&
                        strcmp(fields[f].name, "class_code") == 0 && row[f]) {
                        json_escape(row[f], esc_val, sizeof(esc_val));
                        printf("\"%s\":\"%s\"", fields[f].name, esc_val);
                    } else if (lens[f] > 180 && !opt_dump) {
                        char trunc[256];
                        strncpy(trunc, row[f] ? row[f] : "", 180);
                        trunc[180] = '\0';
                        json_escape(trunc, esc_val, sizeof(esc_val));
                        printf("\"%s\":\"%s...\"", fields[f].name, esc_val);
                    } else {
                        json_escape(row[f] ? row[f] : "", esc_val, sizeof(esc_val));
                        printf("\"%s\":\"%s\"", fields[f].name, esc_val);
                    }
                }
                /* #10: class understandings for code_classes */
                if (is_code_classes) {
                    /* find class_name field */
                    for (int f = 0; f < fcount; f++) {
                        if (strcmp(fields[f].name, "class_name") == 0 && row[f]) {
                            fetch_understanding(conn, row[f]);
                            break;
                        }
                    }
                }
                printf("}");
            } else {
                printf("[%d] ", ++row_idx);

                for (int f = 0; f < fcount; f++) {
                    const char *val = row[f] ? row[f] : "NULL";
                    printf("%s=", fields[f].name);

                    /* #5: dump mode — full class_code */
                    if (opt_dump && is_code_classes &&
                        strcmp(fields[f].name, "class_code") == 0 && row[f]) {
                        printf("%s ", val);
                    } else if (lens[f] > 180) {
                        printf("%.180s... ", val);
                    } else {
                        printf("%s ", val);
                    }
                }

                /* #10: class understandings for code_classes */
                if (is_code_classes) {
                    for (int f = 0; f < fcount; f++) {
                        if (strcmp(fields[f].name, "class_name") == 0 && row[f]) {
                            fetch_understanding(conn, row[f]);
                            break;
                        }
                    }
                }

                printf("\n");
            }

            total++;
            row_idx++;
        }

        if (row_idx > 0 && opt_json)
            printf("]}");
        else if (row_idx == 0 && opt_json && !first_table)
            first_table = 1; /* fix #7: no table output, revert comma state */

        mysql_free_result(res);
    }

    if (opt_json) {
        printf("]\n");
    } else {
        if (!total) {
            if (opt_count)
                printf("No matches found.\n");
            else
                printf("No matches found.\n");
        } else {
            if (opt_count)
                printf("\nTOTAL MATCHES: %d across %d tables\n", total, table_count);
            else
                printf("\nTOTAL MATCHES: %d\n", total);
        }
    }
}

/* ════════════════════════════════════════════
 * ENHANCEMENT #9: CROSS-DATABASE SEARCH
 * ════════════════════════════════════════════ */

static void search_all_databases(const char *keyword,
                                  const char *table_filter,
                                  int limit) {
    const char *dbs[] = {"vb_shared", "CODEBASE", NULL};

    for (int d = 0; dbs[d]; d++) {
        MYSQL *conn = mysql_init(NULL);
        if (!mysql_real_connect(conn,
                opt_host ? opt_host : DEF_HOST,
                opt_user ? opt_user : DEF_USER,
                opt_pass ? opt_pass : DEF_PASS,
                dbs[d],
                opt_port ? opt_port : DEF_PORT, NULL, 0)) {
            if (!opt_json)
                printf("\n--- DB: %s (connection failed) ---\n", dbs[d]);
            mysql_close(conn);
            continue;
        }

        if (!opt_json)
            printf("\n--- DATABASE: %s ---\n", dbs[d]);

        load_schema(conn, dbs[d]);
        search(conn, keyword, table_filter, dbs[d], limit);

        mysql_close(conn);
    }
}

/* ════════════════════════════════════════════
 * v5: AUTO-DISCOVER ALL MYSQL DATABASES
 * Connects to server, runs SHOW DATABASES, searches every one
 * Skips system DBs: information_schema, mysql, performance_schema, sys
 * ════════════════════════════════════════════ */

static int is_system_db(const char *db) {
    return !strcasecmp(db, "information_schema") ||
           !strcasecmp(db, "mysql") ||
           !strcasecmp(db, "performance_schema") ||
           !strcasecmp(db, "sys");
}

static void search_all_mysql(const char *keyword,
                               const char *table_filter,
                               int limit) {
    MYSQL *conn = mysql_init(NULL);
    if (!mysql_real_connect(conn,
            opt_host ? opt_host : DEF_HOST,
            opt_user ? opt_user : DEF_USER,
            opt_pass ? opt_pass : DEF_PASS,
            NULL, /* no default DB */
            opt_port ? opt_port : DEF_PORT, NULL, 0)) {
        fprintf(stderr, "Connection failed: %s\n", mysql_error(conn));
        mysql_close(conn);
        return;
    }

    if (mysql_query(conn, "SHOW DATABASES")) {
        fprintf(stderr, "SHOW DATABASES failed: %s\n", mysql_error(conn));
        mysql_close(conn);
        return;
    }

    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) {
        mysql_close(conn);
        return;
    }

    char *db_list[MAX_DB];
    int db_count = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) && db_count < MAX_DB) {
        const char *dbname = row[0] ? row[0] : "";
        if (is_system_db(dbname)) continue;
        db_list[db_count] = strdup(dbname);
        db_count++;
    }
    mysql_free_result(res);
    mysql_close(conn);

    if (opt_verbose)
        fprintf(stderr, "Found %d databases to search\n", db_count);

    for (int d = 0; d < db_count; d++) {
        conn = mysql_init(NULL);
        if (!mysql_real_connect(conn,
                opt_host ? opt_host : DEF_HOST,
                opt_user ? opt_user : DEF_USER,
                opt_pass ? opt_pass : DEF_PASS,
                db_list[d],
                opt_port ? opt_port : DEF_PORT, NULL, 0)) {
            if (!opt_json)
                printf("\n--- DB: %s (connection failed) ---\n", db_list[d]);
            mysql_close(conn);
            free(db_list[d]);
            continue;
        }

        if (!opt_json)
            printf("\n--- DATABASE: %s ---\n", db_list[d]);

        load_schema(conn, db_list[d]);
        search(conn, keyword, table_filter, db_list[d], limit);

        mysql_close(conn);
        free(db_list[d]);
    }
}

/* ════════════════════════════════════════════
 * QDRANT VECTOR SEARCH (v4)
 * Calls msearch_qdrant.py via popen for embedding + search
 * ════════════════════════════════════════════ */

/* Run the Python Qdrant helper and stream its output */
static void qdrant_run(const char *subcmd, const char *query,
                       const char *collection, int top) {
    char cmd[BUF * 2];
    const char *fmt = opt_json ? "json" : "text";

    if (strcmp(subcmd, "stats") == 0) {
        snprintf(cmd, sizeof(cmd), "python3 %s stats 2>/dev/null", QDRANT_HELPER);
    } else if (strcmp(subcmd, "collections") == 0) {
        snprintf(cmd, sizeof(cmd), "python3 %s collections 2>/dev/null", QDRANT_HELPER);
    } else if (strcmp(subcmd, "multi") == 0) {
        char esc_query[BUF], esc_col[BUF];
        shell_escape(query ? query : "", esc_query, sizeof(esc_query));
        if (collection) {
            shell_escape(collection, esc_col, sizeof(esc_col));
            snprintf(cmd, sizeof(cmd),
                "python3 %s multi '%s' --collections '%s' --top %d --format %s 2>/dev/null",
                QDRANT_HELPER, esc_query, esc_col, top, fmt);
        } else
            snprintf(cmd, sizeof(cmd),
                "python3 %s multi '%s' --top %d --format %s 2>/dev/null",
                QDRANT_HELPER, esc_query, top, fmt);
    } else {
        /* default: search */
        const char *col = collection ? collection : QDRANT_DEFAULT_COLLECTION;
        int t = top > 0 ? top : QDRANT_DEFAULT_TOP;
        char esc_query[BUF], esc_col[BUF];
        shell_escape(query ? query : "", esc_query, sizeof(esc_query));
        shell_escape(col, esc_col, sizeof(esc_col));
        snprintf(cmd, sizeof(cmd),
            "python3 %s search '%s' --collection '%s' --top %d --format %s 2>/dev/null",
            QDRANT_HELPER, esc_query, esc_col, t, fmt);
    }

    FILE *fp = popen(cmd, "r");
    if (!fp) {
        fprintf(stderr, "Error: cannot run Qdrant helper. Is python3 available?\n");
        return;
    }

    /* Stream output directly — Python helper handles formatting */
    char line[4096];
    while (fgets(line, sizeof(line), fp))
        printf("%s", line);

    pclose(fp);
}

/* Show Qdrant collection stats */
static void qdrant_stats(void) {
    if (opt_json) {
        qdrant_run("stats", NULL, NULL, 0);
    } else {
        /* Human-readable: run stats and parse the JSON properly */
        char cmd[BUF];
        snprintf(cmd, sizeof(cmd), "python3 %s stats 2>/dev/null", QDRANT_HELPER);
        FILE *fp = popen(cmd, "r");
        if (!fp) {
            fprintf(stderr, "Error: cannot run Qdrant helper.\n");
            return;
        }

        /* Read entire output */
        char *buf = malloc(BIGBUF * 4);
        if (!buf) { pclose(fp); return; }
        size_t total = 0;
        char chunk[4096];
        while (fgets(chunk, sizeof(chunk), fp)) {
            size_t len = strlen(chunk);
            if (total + len < BIGBUF * 4 - 1) {
                memcpy(buf + total, chunk, len);
                total += len;
            }
        }
        buf[total] = '\0';
        pclose(fp);

        printf("=== QDRANT COLLECTION STATS ===\n\n");
        printf("%-25s  %8s  %6s  %s\n", "COLLECTION", "POINTS", "DIMS", "STATUS");
        printf("%-25s  %8s  %6s  %s\n", "-------------------------", "--------", "------", "------");

        /* Simple JSON parsing for the stats format */
        char *p = buf;
        while ((p = strstr(p, "\"name\":"))) {
            char *start = strchr(p + 7, '"');
            if (!start) break;
            char *end = strchr(start + 1, '"');
            if (!end) break;
            char name[128];
            size_t nlen = end - start - 1;
            if (nlen >= sizeof(name)) nlen = sizeof(name) - 1;
            strncpy(name, start + 1, nlen);
            name[nlen] = '\0';

            /* Find points */
            char *pts_match = strstr(end, "\"points\":");
            int points = 0;
            if (pts_match) points = atoi(pts_match + 9);

            /* Find vectors */
            char *vec_match = strstr(end, "\"vectors\":");
            int vectors = 0;
            if (vec_match) vectors = atoi(vec_match + 10);

            /* Find status */
            char *stat_match = strstr(end, "\"status\":");
            char status[32] = "?";
            if (stat_match) {
                char *s = strchr(stat_match + 9, '"');
                if (s) {
                    char *e = strchr(s + 1, '"');
                    if (e) {
                        size_t slen = e - s - 1;
                        if (slen < sizeof(status)) {
                            strncpy(status, s + 1, slen);
                            status[slen] = '\0';
                        }
                    }
                }
            }

            printf("%-25s  %8d  %6d  %s\n", name, points, vectors, status);
            p = end + 1;
        }
        free(buf);
    }
}

/* Qdrant semantic search */
static void qdrant_search(const char *query) {
    const char *col = opt_dimension ? opt_dimension : QDRANT_DEFAULT_COLLECTION;
    int top = opt_top > 0 ? opt_top : QDRANT_DEFAULT_TOP;

    if (!opt_json)
        printf("=== QDRANT VECTOR SEARCH ===\n\n");

    if (opt_multi) {
        qdrant_run("multi", query, opt_dimension, top);
    } else {
        qdrant_run("search", query, col, top);
    }
}

/* Hybrid search: MySQL keyword + Qdrant vector */
static void hybrid_search(const char *keyword, const char *table_filter,
                          const char *db, int limit) {
    /* Phase 1: MySQL keyword search */
    if (!opt_json)
        printf("╔══════════════════════════════════════════════╗\n"
               "║  HYBRID SEARCH: MySQL + Qdrant              ║\n"
               "╚══════════════════════════════════════════════╝\n\n");

    if (!opt_json)
        printf("─── PHASE 1: MySQL Keyword Search ───\n\n");

    MYSQL *conn = mysql_init(NULL);
    if (!mysql_real_connect(conn,
            opt_host ? opt_host : DEF_HOST,
            opt_user ? opt_user : DEF_USER,
            opt_pass ? opt_pass : DEF_PASS,
            db,
            opt_port ? opt_port : DEF_PORT, NULL, 0)) {
        fprintf(stderr, "MySQL connection failed: %s\n", mysql_error(conn));
        mysql_close(conn);
        return;
    }

    load_schema(conn, db);
    search(conn, keyword, table_filter, db, limit);
    mysql_close(conn);

    /* Phase 2: Qdrant vector search */
    if (!opt_json)
        printf("\n─── PHASE 2: Qdrant Vector Search ───\n\n");

    qdrant_search(keyword);

    if (!opt_json)
        printf("\n─── HYBRID SEARCH COMPLETE ───\n");
}

/* ════════════════════════════════════════════
 * v6: CONTEXT RECONSTRUCTION ENGINE
 * Multi-radius search → context packet → timeline
 * ════════════════════════════════════════════ */

/* ── Chat radius search: find keyword in chat messages, grab ±N messages ── */
static int chat_radius_search(const char *keyword, int radius, int max_hits) {
    /* Search Chat_History.messages (142K messages) */
    MYSQL *conn = mysql_init(NULL);
    if (!mysql_real_connect(conn,
            opt_host ? opt_host : DEF_HOST,
            opt_user ? opt_user : DEF_USER,
            opt_pass ? opt_pass : DEF_PASS,
            "Chat_History",
            opt_port ? opt_port : DEF_PORT, NULL, 0)) {
        printf("  (Chat_History unavailable)\n");
        mysql_close(conn);
        return 0;
    }

    char esc[1024];
    escape_like(keyword, esc, sizeof(esc));

    /* Find matching message row_ids */
    char q[BUF * 2];
    char match[BUF];
    match_expr(match, sizeof(match), "content", keyword);
    snprintf(q, sizeof(q),
        "SELECT row_id, session_id, node_id, role, content, sequence "
        "FROM messages WHERE %s "
        "ORDER BY row_id LIMIT %d", match, max_hits);

    if (mysql_query(conn, q)) {
        printf("  (Chat_History query failed)\n");
        mysql_close(conn);
        return 0;
    }

    MYSQL_RES *res = mysql_store_result(conn);
    if (!res || mysql_num_rows(res) == 0) {
        printf("  No chat messages found.\n");
        if (res) mysql_free_result(res);
        mysql_close(conn);
        return 0;
    }

    MYSQL_ROW row;
    int hit_count = 0;
    while ((row = mysql_fetch_row(res)) && hit_count < max_hits) {
        long row_id = row[0] ? atol(row[0]) : 0;
        long session_id = row[1] ? atol(row[1]) : 0;
        const char *role = row[3] ? row[3] : "?";
        const char *content = row[4] ? row[4] : "";
        int seq = row[5] ? atoi(row[5]) : 0;

        /* Truncate the hit content for display */
        char snippet[300];
        strncpy(snippet, content, 299);
        snippet[299] = '\0';

        printf("  ┌─ CHAT HIT #%d (session=%ld, seq=%d, role=%s)\n",
            ++hit_count, session_id, seq, role);
        printf("  │  %.250s\n", snippet);

        /* Now grab ±radius messages around this hit in the same session */
        char rq[BUF * 2];
        snprintf(rq, sizeof(rq),
            "SELECT role, content, sequence FROM messages "
            "WHERE session_id = %ld AND sequence >= %d AND sequence <= %d "
            "ORDER BY sequence LIMIT %d",
            session_id, seq - radius, seq + radius, radius * 2);

        if (mysql_query(conn, rq)) {
            printf("  │  (radius query failed)\n");
            printf("  └─\n\n");
            continue;
        }

        MYSQL_RES *rres = mysql_store_result(conn);
        if (!rres) {
            printf("  └─\n\n");
            continue;
        }

        MYSQL_ROW rrow;
        int ctx_count = 0;
        int showed = 0;
        while ((rrow = mysql_fetch_row(rres))) {
            const char *crole = rrow[0] ? rrow[0] : "?";
            const char *ccontent = rrow[1] ? rrow[1] : "";
            int cseq = rrow[2] ? atoi(rrow[2]) : 0;

            /* Only show first 5 and last 5 of the radius to keep output manageable */
            int total_rows = mysql_num_rows(rres);
            if (showed < 3 || showed >= total_rows - 3) {
                char ctx_snippet[200];
                strncpy(ctx_snippet, ccontent, 199);
                ctx_snippet[199] = '\0';
                printf("  │  [%d] %s: %.180s\n", cseq, crole, ctx_snippet);
            } else if (showed == 3) {
                printf("  │  ... (%d messages omitted) ...\n", total_rows - 6);
            }
            showed++;
            ctx_count++;
        }

        printf("  │  (%d messages in ±%d radius)\n", ctx_count, radius);
        printf("  └─\n\n");
        mysql_free_result(rres);
    }

    int total_hits = hit_count;
    mysql_free_result(res);
    mysql_close(conn);
    return total_hits;
}

/* ── ChatGPT export radius search ── */
static int chatgpt_radius_search(const char *keyword, int max_hits) {
    MYSQL *conn = mysql_init(NULL);
    if (!mysql_real_connect(conn,
            opt_host ? opt_host : DEF_HOST,
            opt_user ? opt_user : DEF_USER,
            opt_pass ? opt_pass : DEF_PASS,
            "chatgpt_export",
            opt_port ? opt_port : DEF_PORT, NULL, 0)) {
        printf("  (chatgpt_export unavailable)\n");
        mysql_close(conn);
        return 0;
    }

    char esc[1024];
    escape_like(keyword, esc, sizeof(esc));

    char q[BUF * 2];
    char match[BUF];
    match_expr(match, sizeof(match), "m.text", keyword);
    snprintf(q, sizeof(q),
        "SELECT m.id, m.conversation_id, m.role, m.text, c.title "
        "FROM messages m JOIN conversations c ON m.conversation_id = c.id "
        "WHERE %s "
        "ORDER BY m.id LIMIT %d", match, max_hits);

    if (mysql_query(conn, q)) {
        printf("  (chatgpt_export query failed: %s)\n", mysql_error(conn));
        mysql_close(conn);
        return 0;
    }

    MYSQL_RES *res = mysql_store_result(conn);
    if (!res || mysql_num_rows(res) == 0) {
        printf("  No ChatGPT export messages found.\n");
        if (res) mysql_free_result(res);
        mysql_close(conn);
        return 0;
    }

    MYSQL_ROW row;
    int hit_count = 0;
    while ((row = mysql_fetch_row(res)) && hit_count < max_hits) {
        const char *conv_id = row[1] ? row[1] : "?";
        const char *role = row[2] ? row[2] : "?";
        const char *text = row[3] ? row[3] : "";
        const char *title = row[4] ? row[4] : "(untitled)";

        char snippet[300];
        strncpy(snippet, text, 299);
        snippet[299] = '\0';

        printf("  ┌─ CHATGPT HIT #%d (conv=%s)\n", ++hit_count, conv_id);
        printf("  │  TITLE: %.100s\n", title);
        printf("  │  ROLE: %s\n", role);
        printf("  │  %.250s\n", snippet);

        /* Grab surrounding messages in same conversation */
        long msg_id = row[0] ? atol(row[0]) : 0;
        char rq[BUF * 2];
        snprintf(rq, sizeof(rq),
            "SELECT role, text FROM messages "
            "WHERE conversation_id = '%s' AND id BETWEEN %ld AND %ld "
            "ORDER BY id LIMIT 10",
            conv_id, msg_id - 5, msg_id + 5);

        if (mysql_query(conn, rq)) {
            printf("  └─\n\n");
            continue;
        }

        MYSQL_RES *rres = mysql_store_result(conn);
        if (!rres) {
            printf("  └─\n\n");
            continue;
        }

        MYSQL_ROW rrow;
        while ((rrow = mysql_fetch_row(rres))) {
            const char *crole = rrow[0] ? rrow[0] : "?";
            const char *ctext = rrow[1] ? rrow[1] : "";
            char ctx_snippet[200];
            strncpy(ctx_snippet, ctext, 199);
            ctx_snippet[199] = '\0';
            printf("  │  %s: %.180s\n", crole, ctx_snippet);
        }

        printf("  └─\n\n");
        mysql_free_result(rres);
    }

    int total_hits = hit_count;
    mysql_free_result(res);
    mysql_close(conn);
    return total_hits;
}

/* ── Q&A radius: find keyword in know_answers/know_questions ── */
static void qa_radius_search(MYSQL *conn, const char *keyword) {
    char esc[1024];
    escape_like(keyword, esc, sizeof(esc));

    char q[BUF * 2];
    char mq[BUF], ma[BUF];
    match_expr(mq, sizeof(mq), "q.question", keyword);
    match_expr(ma, sizeof(ma), "a.answer", keyword);
    snprintf(q, sizeof(q),
        "SELECT q.question, a.answer, a.confidence, a.provenance "
        "FROM know_questions q JOIN know_answers a ON q.id = a.question_id "
        "WHERE %s OR %s "
        "ORDER BY a.confidence DESC LIMIT 5", mq, ma);

    if (mysql_query(conn, q)) {
        printf("  (Q&A query failed: %s)\n\n", mysql_error(conn));
        return;
    }

    MYSQL_RES *res = mysql_store_result(conn);
    if (!res || mysql_num_rows(res) == 0) {
        printf("  No Q&A matches found.\n\n");
        if (res) mysql_free_result(res);
        return;
    }

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        const char *question = row[0] ? row[0] : "?";
        const char *answer = row[1] ? row[1] : "?";
        const char *conf = row[2] ? row[2] : "?";
        const char *prov = row[3] ? row[3] : "?";

        printf("  Q: %.150s\n", question);
        printf("  A: %.250s\n", answer);
        printf("  (confidence=%s, source=%s)\n\n", conf, prov);
    }

    mysql_free_result(res);
}

/* ── Main context reconstruction function ── */
static void context_reconstruct(MYSQL *conn, const char *keyword) {
    int radius = opt_radius;
    int max_hits = 5;

    /* Hit counters for coverage map */
    int hits_authority = 0, hits_classes = 0, hits_methods = 0;
    int hits_deps = 0, hits_rules = 0, hits_qa = 0;
    int hits_chat = 0, hits_chatgpt = 0, hits_conf = 0;

    /* Authority text for conflict detection */
    char auth_text[512]; auth_text[0] = '\0';
    char auth_class[128]; auth_class[0] = '\0';

    printf("══════════════════════════════════════════════════════════════\n");
    printf("  CONTEXT RECONSTRUCTION: \"%s\"  (radius=%d", keyword, radius);
    if (opt_mode == 1) printf(", mode=exact");
    else if (opt_mode == 2) printf(", mode=prefix");
    else if (opt_mode == 3) printf(", mode=regex");
    else printf(", mode=magnetic");
    printf(")\n");
    printf("══════════════════════════════════════════════════════════════\n\n");

    int sections = 0;

    /* ═══ 1. AUTHORITY (from vb_shared) ═══ */
    printf("══════ AUTHORITY ══════\n");
    {
        char q[BUF];
        char match[BUF];
        match_expr(match, sizeof(match), "class_name", keyword);
        snprintf(q, sizeof(q),
            "SELECT class_name, cascade_understanding, layer "
            "FROM class_understandings WHERE %s LIMIT 3", match);
        if (mysql_query(conn, q)) {
            printf("  (unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No authority found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  %s [%s]\n", row[0] ? row[0] : "?", row[2] ? row[2] : "?");
                    if (row[1]) {
                        printf("  %.300s\n\n", row[1]);
                        if (auth_text[0] == '\0' && row[0]) {
                            strncpy(auth_class, row[0], sizeof(auth_class)-1);
                            auth_class[sizeof(auth_class)-1] = '\0';
                            strncpy(auth_text, row[1], sizeof(auth_text)-1);
                            auth_text[sizeof(auth_text)-1] = '\0';
                        }
                    }
                    hits_authority++;
                }
                mysql_free_result(res);
                sections++;
            }
        }
    }

    /* ═══ 2. CODE CLASSES (from vb_shared) ═══ */
    printf("══════ CODE CLASSES ══════\n");
    {
        char q[BUF * 2];
        char match[BUF];
        match_expr(match, sizeof(match), "class_name", keyword);
        snprintf(q, sizeof(q),
            "SELECT class_name, description FROM code_classes "
            "WHERE %s LIMIT 10", match);
        if (mysql_query(conn, q)) {
            printf("  (unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No classes found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  %s", row[0] ? row[0] : "?");
                    if (row[1] && row[1][0])
                        printf(" — %.100s", row[1]);
                    printf("\n");
                    hits_classes++;
                }
                mysql_free_result(res);
                printf("\n");
                sections++;
            }
        }
    }

    /* ═══ 3. METHODS (from vb_shared) ═══ */
    printf("══════ METHODS ══════\n");
    {
        char q[BUF * 2];
        char match[BUF];
        match_expr(match, sizeof(match), "identifier", keyword);
        snprintf(q, sizeof(q),
            "SELECT identifier, identifier_type, frequency, authority_score "
            "FROM code_identifier_frequency "
            "WHERE %s LIMIT 15", match);
        if (mysql_query(conn, q)) {
            printf("  (unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No methods found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  %-40s  %s  freq=%s  auth=%s\n",
                        row[0] ? row[0] : "?",
                        row[1] ? row[1] : "?",
                        row[2] ? row[2] : "0",
                        row[3] ? row[3] : "0");
                    hits_methods++;
                }
                mysql_free_result(res);
                printf("\n");
                sections++;
            }
        }
    }

    /* ═══ 4. DEPENDENCY RADIUS (from vb_shared.class_graph) ═══ */
    printf("══════ DEPENDENCY RADIUS ══════\n");
    {
        char q[BUF * 2];
        char ms[BUF], mt[BUF];
        match_expr(ms, sizeof(ms), "source_class", keyword);
        match_expr(mt, sizeof(mt), "target_class", keyword);
        snprintf(q, sizeof(q),
            "SELECT source_class, target_class, relationship FROM class_graph "
            "WHERE %s OR %s LIMIT 15", ms, mt);
        if (mysql_query(conn, q)) {
            printf("  (unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No dependency edges found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  %s  --%s-->  %s\n",
                        row[0] ? row[0] : "?",
                        row[2] ? row[2] : "?",
                        row[1] ? row[1] : "?");
                    hits_deps++;
                }
                mysql_free_result(res);
                printf("\n");
                sections++;
            }
        }
    }

    /* ═══ 5. RULES RADIUS (from vb_shared.learned_rules) ═══ */
    printf("══════ RULES RADIUS ══════\n");
    {
        char q[BUF * 2];
        char match[BUF];
        match_expr(match, sizeof(match), "pattern", keyword);
        snprintf(q, sizeof(q),
            "SELECT pattern, fix_action, confidence, severity FROM learned_rules "
            "WHERE %s ORDER BY confidence DESC LIMIT 5", match);
        if (mysql_query(conn, q)) {
            printf("  (unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No applicable rules found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    char sev = ' ';
                    if (row[3]) {
                        int sv = atoi(row[3]);
                        sev = sv >= 4 ? 'X' : (sv >= 3 ? '!' : '.');
                    }
                    printf("  [%c] %.100s\n", sev, row[0] ? row[0] : "?");
                    if (row[1] && row[1][0])
                        printf("      fix: %.100s\n", row[1]);
                    hits_rules++;
                }
                mysql_free_result(res);
                printf("\n");
                sections++;
            }
        }
    }

    /* ═══ 6. Q&A RADIUS (from vb_shared.know_questions/know_answers) ═══ */
    printf("══════ Q&A RADIUS ══════\n");
    {
        char q[BUF * 2];
        char mq[BUF], ma[BUF];
        match_expr(mq, sizeof(mq), "q.question", keyword);
        match_expr(ma, sizeof(ma), "a.answer", keyword);
        snprintf(q, sizeof(q),
            "SELECT q.question, a.answer, a.confidence, a.provenance "
            "FROM know_questions q JOIN know_answers a ON q.id = a.question_id "
            "WHERE %s OR %s "
            "ORDER BY a.confidence DESC LIMIT 5", mq, ma);
        if (mysql_query(conn, q)) {
            printf("  (Q&A query failed: %s)\n\n", mysql_error(conn));
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No Q&A matches found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  Q: %.150s\n", row[0] ? row[0] : "?");
                    printf("  A: %.250s\n", row[1] ? row[1] : "?");
                    printf("  (confidence=%s, source=%s)\n\n",
                        row[2] ? row[2] : "?", row[3] ? row[3] : "?");
                    hits_qa++;
                }
                mysql_free_result(res);
                sections++;
            }
        }
    }

    /* ═══ 7. CHAT HISTORY RADIUS (from Chat_History.messages — 142K msgs) ═══ */
    printf("══════ CHAT HISTORY RADIUS (±%d messages) ══════\n", radius);
    {
        /* Count hits by running the search and capturing count */
        int chat_count = chat_radius_search(keyword, radius, max_hits);
        hits_chat = chat_count;
        sections++;
    }

    /* ═══ 8. CHATGPT EXPORT RADIUS (from chatgpt_export.messages — 73K msgs) ═══ */
    printf("══════ CHATGPT EXPORT RADIUS ══════\n");
    {
        int cgpt_count = chatgpt_radius_search(keyword, max_hits);
        hits_chatgpt = cgpt_count;
        sections++;
    }

    /* ═══ 9. CONFIDENCE ═══ */
    printf("══════ CONFIDENCE ══════\n");
    {
        char q[BUF];
        char match[BUF];
        match_expr(match, sizeof(match), "pattern", keyword);
        snprintf(q, sizeof(q),
            "SELECT AVG(confidence), COUNT(*) FROM learned_rules WHERE %s", match);
        if (mysql_query(conn, q)) {
            printf("  (unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row = mysql_fetch_row(res);
            double avg = row[0] ? atof(row[0]) : 0;
            int cnt = row[1] ? atoi(row[1]) : 0;
            if (cnt > 0) {
                printf("  Rules: %d, Avg confidence: %.2f\n", cnt, avg);
                if (avg >= 0.9)
                    printf("  Verdict: HIGH CONFIDENCE\n");
                else if (avg >= 0.7)
                    printf("  Verdict: MEDIUM CONFIDENCE\n");
                else
                    printf("  Verdict: LOW CONFIDENCE\n");
                hits_conf = cnt;
            } else {
                printf("  No confidence data.\n");
            }
            mysql_free_result(res);
            printf("\n");
            sections++;
        }
    }

    /* ═══ 10. COVERAGE MAP (v6 NEW) ═══ */
    printf("══════ COVERAGE MAP ══════\n");
    {
        int max_hits_dim = hits_authority;
        if (hits_classes > max_hits_dim) max_hits_dim = hits_classes;
        if (hits_methods > max_hits_dim) max_hits_dim = hits_methods;
        if (hits_deps > max_hits_dim) max_hits_dim = hits_deps;
        if (hits_rules > max_hits_dim) max_hits_dim = hits_rules;
        if (hits_qa > max_hits_dim) max_hits_dim = hits_qa;
        if (hits_chat > max_hits_dim) max_hits_dim = hits_chat;
        if (hits_chatgpt > max_hits_dim) max_hits_dim = hits_chatgpt;
        if (max_hits_dim < 1) max_hits_dim = 1;

        /* Print bars (12 chars max) */
        #define BAR(n) do { \
            int blen = (int)((float)(n) / max_hits_dim * 12); \
            if (blen < 1 && (n) > 0) blen = 1; \
            for (int bi = 0; bi < blen; bi++) putchar('#'); \
            for (int bi = blen; bi < 12; bi++) putchar(' '); \
        } while(0)

        printf("  Spec (authority):     "); BAR(hits_authority);
        printf("  %d hits\n", hits_authority);
        printf("  Impl (code_classes):  "); BAR(hits_classes);
        printf("  %d hits\n", hits_classes);
        printf("  Impl (methods):       "); BAR(hits_methods);
        printf("  %d hits\n", hits_methods);
        printf("  Struct (deps):        "); BAR(hits_deps);
        printf("  %d hits\n", hits_deps);
        printf("  Failure (rules):      "); BAR(hits_rules);
        printf("  %d hits\n", hits_rules);
        printf("  Failure (Q&A):        "); BAR(hits_qa);
        printf("  %d hits\n", hits_qa);
        printf("  Interp (chat):        "); BAR(hits_chat);
        printf("  %d hits\n", hits_chat);
        printf("  Interp (chatgpt):     "); BAR(hits_chatgpt);
        printf("  %d hits\n", hits_chatgpt);
        printf("  Confidence (rules):   "); BAR(hits_conf);
        printf("  %d hits\n", hits_conf);

        /* Gaps */
        printf("\n  Gaps:\n");
        if (hits_authority == 0) printf("    [ ] No authority definition found\n");
        if (hits_classes == 0) printf("    [ ] No code implementation found\n");
        if (hits_methods == 0) printf("    [ ] No method identifiers found\n");
        if (hits_deps == 0) printf("    [ ] No dependency edges found\n");
        if (hits_rules == 0) printf("    [ ] No learned rules found\n");
        if (hits_qa == 0) printf("    [ ] No Q&A pairs found\n");
        if (hits_chat == 0) printf("    [ ] No chat history matches\n");
        if (hits_chatgpt == 0) printf("    [ ] No ChatGPT export matches\n");

        /* Drift detection: interpretation >> specification */
        int interp = hits_chat + hits_chatgpt;
        int spec = hits_authority + hits_classes;
        if (interp > 0 && spec == 0)
            printf("    [!] Interpretation exists but NO specification — possible folklore\n");
        else if (interp > spec * 3 && spec > 0)
            printf("    [!] Interpretation >> specification — possible drift\n");

        /* Coverage verdict */
        int covered = 0;
        if (hits_authority > 0) covered++;
        if (hits_classes > 0) covered++;
        if (hits_methods > 0) covered++;
        if (hits_deps > 0) covered++;
        if (hits_rules > 0) covered++;
        if (hits_qa > 0) covered++;
        if (hits_chat > 0) covered++;
        if (hits_chatgpt > 0) covered++;
        printf("\n  Coverage: %d/8 axes populated", covered);
        if (covered >= 7) printf(" — COMPREHENSIVE\n");
        else if (covered >= 5) printf(" — GOOD\n");
        else if (covered >= 3) printf(" — PARTIAL\n");
        else printf(" — SPARSE\n");
        printf("\n");
        sections++;
    }

    /* ═══ 11. CONFLICT DETECTION (v6 NEW) ═══ */
    printf("══════ CONFLICTS ══════\n");
    {
        int conflicts = 0;

        /* Check: authority says X, but does code_classes agree? */
        if (auth_text[0] && hits_classes > 0) {
            /* Query code_classes description for the same class */
            char q[BUF * 2];
            char esc[256];
            escape_like(auth_class, esc, sizeof(esc));
            snprintf(q, sizeof(q),
                "SELECT class_name, description FROM code_classes "
                "WHERE class_name = '%s' LIMIT 1", esc);
            if (!mysql_query(conn, q)) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res && mysql_num_rows(res) > 0) {
                    MYSQL_ROW row = mysql_fetch_row(res);
                    const char *desc = row[1] ? row[1] : "";
                    /* Heuristic: if authority mentions "execution" but description doesn't */
                    if (strstr(auth_text, "execution") && !strstr(desc, "execution") &&
                        strstr(auth_text, "authority") && !strstr(desc, "authority")) {
                        printf("  [!] %s — definition mismatch\n", auth_class);
                        printf("      Authority: \"%.100s...\"\n", auth_text);
                        printf("      Code desc: \"%.100s\"\n", desc);
                        printf("      Verdict: Authority source is canonical\n");
                        conflicts++;
                    }
                }
                if (res) mysql_free_result(res);
            }
        }

        /* Check: rules with severity X (critical) vs authority — do rules contradict? */
        if (hits_rules > 0 && hits_authority > 0) {
            char q[BUF * 2];
            char match[BUF];
            match_expr(match, sizeof(match), "pattern", keyword);
            snprintf(q, sizeof(q),
                "SELECT pattern, severity FROM learned_rules "
                "WHERE %s AND severity >= 4 LIMIT 5", match);
            if (!mysql_query(conn, q)) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    while (mysql_fetch_row(res)) {
                        /* Critical rules about this keyword exist — flag if authority
                           describes it as stable/canonical */
                        if (strstr(auth_text, "authority") || strstr(auth_text, "canonical")) {
                            printf("  [!] Critical rules exist for \"%s\" despite authority definition\n",
                                   keyword);
                            printf("      Authority says: \"%.80s...\"\n", auth_text);
                            printf("      But critical rules suggest known issues\n");
                            conflicts++;
                            break;
                        }
                    }
                    mysql_free_result(res);
                }
            }
        }

        /* Check: Q&A confidence vs rules confidence — do they agree? */
        if (hits_qa > 0 && hits_conf > 0) {
            char q[BUF * 2];
            char mq[BUF], ma[BUF];
            match_expr(mq, sizeof(mq), "q.question", keyword);
            match_expr(ma, sizeof(ma), "a.answer", keyword);
            snprintf(q, sizeof(q),
                "SELECT AVG(a.confidence) FROM know_questions q "
                "JOIN know_answers a ON q.id = a.question_id "
                "WHERE %s OR %s", mq, ma);
            if (!mysql_query(conn, q)) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row = mysql_fetch_row(res);
                    if (row[0]) {
                        double qa_conf = atof(row[0]);
                        char q2[BUF];
                        char match2[BUF];
                        match_expr(match2, sizeof(match2), "pattern", keyword);
                        snprintf(q2, sizeof(q2),
                            "SELECT AVG(confidence) FROM learned_rules WHERE %s", match2);
                        if (!mysql_query(conn, q2)) {
                            MYSQL_RES *res2 = mysql_store_result(conn);
                            if (res2) {
                                MYSQL_ROW row2 = mysql_fetch_row(res2);
                                if (row2[0]) {
                                    double rule_conf = atof(row2[0]);
                                    double diff = qa_conf - rule_conf;
                                    if (diff > 0.2 || diff < -0.2) {
                                        printf("  [!] Confidence divergence for \"%s\"\n", keyword);
                                        printf("      Q&A confidence:    %.2f\n", qa_conf);
                                        printf("      Rules confidence:  %.2f\n", rule_conf);
                                        printf("      Gap: %.2f — sources disagree on reliability\n",
                                               diff > 0 ? diff : -diff);
                                        conflicts++;
                                    }
                                }
                                mysql_free_result(res2);
                            }
                        }
                    }
                    mysql_free_result(res);
                }
            }
        }

        /* Check: interpretation volume vs specification — folklore risk */
        if (hits_chat > 0 && hits_authority == 0 && hits_classes == 0) {
            printf("  [!] \"%s\" discussed in chat but NOT in authority or code\n", keyword);
            printf("      Chat hits: %d, Authority: 0, Code: 0\n", hits_chat);
            printf("      Verdict: Possible folklore — concept exists only in conversation\n");
            conflicts++;
        }

        if (conflicts == 0) {
            printf("  No conflicts detected — sources are consistent.\n");
        } else {
            printf("\n  Total conflicts: %d\n", conflicts);
        }
        printf("\n");
        sections++;
    }

    /* ── Summary ── */
    printf("══════════════════════════════════════════════════════════════\n");
    printf("  CONTEXT PACKET: %d dimensions | radius=%d | keyword=\"%s\"",
        sections, radius, keyword);
    {
        int total_hits = hits_authority + hits_classes + hits_methods + hits_deps +
                         hits_rules + hits_qa + hits_chat + hits_chatgpt;
        printf(" | %d total evidence points", total_hits);
    }
    printf("\n");
    printf("══════════════════════════════════════════════════════════════\n");
}

/* ════════════════════════════════════════════
 * v5: SMART CONSOLIDATED SEARCH
 * One keyword → 10 sections → complete semantic object
 * ════════════════════════════════════════════ */

static void smart_search(MYSQL *conn, const char *keyword) {
    char esc[1024];
    escape_like(keyword, esc, sizeof(esc));
    char q[BUF * 2];
    int total_sections = 0;
    int total_matches = 0;

    /* ── Header ── */
    printf("══════════════════════════════════════════════════\n");
    printf("  SMART SEARCH: %s\n", keyword);
    printf("══════════════════════════════════════════════════\n\n");

    /* ════════════════════════════════════════════
     * 1. AUTHORITY — canonical definition from class_understandings
     * ════════════════════════════════════════════ */
    printf("────────── AUTHORITY ──────────\n");
    {
        snprintf(q, sizeof(q),
            "SELECT class_name, cascade_understanding, wayne_understanding, layer "
            "FROM class_understandings WHERE class_name LIKE '%%%s%%' LIMIT 3", esc);
        if (mysql_query(conn, q)) {
            printf("  (table unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No canonical definition found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  CLASS: %s\n", row[0] ? row[0] : "?");
                    if (row[1] && row[1][0])
                        printf("  CASCADE: %.300s\n", row[1]);
                    if (row[2] && row[2][0])
                        printf("  WAYNE: %.200s\n", row[2]);
                    if (row[3] && row[3][0])
                        printf("  LAYER: %s\n", row[3]);
                    printf("\n");
                    total_matches++;
                }
                mysql_free_result(res);
                total_sections++;
            }
        }
    }

    /* ════════════════════════════════════════════
     * 2. FILES — code_classes matching keyword
     * ════════════════════════════════════════════ */
    printf("────────── FILES & CLASSES ──────────\n");
    {
        snprintf(q, sizeof(q),
            "SELECT class_name, description FROM code_classes "
            "WHERE class_name LIKE '%%%s%%' LIMIT 10", esc);
        if (mysql_query(conn, q)) {
            printf("  (table unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No matching classes found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  %s", row[0] ? row[0] : "?");
                    if (row[1] && row[1][0])
                        printf(" — %.120s", row[1]);
                    printf("\n");
                    total_matches++;
                }
                mysql_free_result(res);
                printf("\n");
                total_sections++;
            }
        }
    }

    /* ════════════════════════════════════════════
     * 3. METHODS — code_identifier_frequency
     * ════════════════════════════════════════════ */
    printf("────────── METHODS ──────────\n");
    {
        snprintf(q, sizeof(q),
            "SELECT identifier, identifier_type, frequency, authority_score "
            "FROM code_identifier_frequency "
            "WHERE identifier LIKE '%%%s%%' LIMIT 15", esc);
        if (mysql_query(conn, q)) {
            printf("  (table unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No methods found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  %-40s  %s  freq=%s  auth=%s\n",
                        row[0] ? row[0] : "?",
                        row[1] ? row[1] : "?",
                        row[2] ? row[2] : "0",
                        row[3] ? row[3] : "0");
                    total_matches++;
                }
                mysql_free_result(res);
                printf("\n");
                total_sections++;
            }
        }
    }

    /* ════════════════════════════════════════════
     * 4. DEPENDENCIES — class_graph relationships
     * ════════════════════════════════════════════ */
    printf("────────── DEPENDENCIES ──────────\n");
    {
        snprintf(q, sizeof(q),
            "SELECT source_class, target_class, relationship FROM class_graph "
            "WHERE source_class LIKE '%%%s%%' OR target_class LIKE '%%%s%%' LIMIT 15",
            esc, esc);
        if (mysql_query(conn, q)) {
            printf("  (table unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No dependency edges found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                int printed = 0;
                while ((row = mysql_fetch_row(res))) {
                    printf("  %s  --%s-->  %s\n",
                        row[0] ? row[0] : "?",
                        row[2] ? row[2] : "?",
                        row[1] ? row[1] : "?");
                    total_matches++;
                    printed++;
                }
                mysql_free_result(res);
                if (printed == 0)
                    printf("  No dependency edges found.\n");
                printf("\n");
                total_sections++;
            }
        }
    }

    /* ════════════════════════════════════════════
     * 5. RULES — learned_rules top 5 by confidence
     * ════════════════════════════════════════════ */
    printf("────────── RULES ──────────\n");
    {
        snprintf(q, sizeof(q),
            "SELECT pattern, fix_action, confidence, severity FROM learned_rules "
            "WHERE pattern LIKE '%%%s%%' ORDER BY confidence DESC, severity DESC LIMIT 5",
            esc);
        if (mysql_query(conn, q)) {
            printf("  (table unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No applicable rules found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    char sev = ' ';
                    if (row[3]) {
                        int sv = atoi(row[3]);
                        sev = sv >= 4 ? 'X' : (sv >= 3 ? '!' : '.');
                    }
                    printf("  [%c] %.100s\n", sev, row[0] ? row[0] : "?");
                    if (row[1] && row[1][0])
                        printf("      fix: %.100s\n", row[1]);
                    if (row[2])
                        printf("      confidence: %s\n", row[2]);
                    total_matches++;
                }
                mysql_free_result(res);
                printf("\n");
                total_sections++;
            }
        }
    }

    /* ════════════════════════════════════════════
     * 6. RELATED — code_co_occurrence
     * ════════════════════════════════════════════ */
    printf("────────── RELATED CONCEPTS ──────────\n");
    {
        snprintf(q, sizeof(q),
            "SELECT entity_b, relationship_type, co_occurrence_count "
            "FROM code_co_occurrence "
            "WHERE entity_a LIKE '%%%s%%' "
            "GROUP BY entity_b ORDER BY co_occurrence_count DESC LIMIT 10",
            esc);
        if (mysql_query(conn, q)) {
            printf("  (table unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No related concepts found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  %-30s  (%s, count=%s)\n",
                        row[0] ? row[0] : "?",
                        row[1] ? row[1] : "?",
                        row[2] ? row[2] : "0");
                    total_matches++;
                }
                mysql_free_result(res);
                printf("\n");
                total_sections++;
            }
        }
    }

    /* ════════════════════════════════════════════
     * 7. HISTORY — code_index evolution
     * ════════════════════════════════════════════ */
    printf("────────── HISTORY ──────────\n");
    {
        snprintf(q, sizeof(q),
            "SELECT entity_name, entity_type, relationship, status, first_seen, last_seen "
            "FROM code_index WHERE entity_name LIKE '%%%s%%' LIMIT 10", esc);
        if (mysql_query(conn, q)) {
            printf("  (table unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  No history records found.\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  %s [%s] %s — status: %s",
                        row[0] ? row[0] : "?",
                        row[1] ? row[1] : "?",
                        row[2] ? row[2] : "?",
                        row[3] ? row[3] : "?");
                    if (row[4])
                        printf(" (first: %s)", row[4]);
                    printf("\n");
                    total_matches++;
                }
                mysql_free_result(res);
                printf("\n");
                total_sections++;
            }
        }
    }

    /* ════════════════════════════════════════════
     * 8. WHERE TO STORE — table_registry routing
     * ════════════════════════════════════════════ */
    printf("────────── STORAGE ROUTING ──────────\n");
    {
        snprintf(q, sizeof(q),
            "SELECT table_name, table_type, purpose FROM table_registry "
            "WHERE purpose LIKE '%%%s%%' OR `contains` LIKE '%%%s%%' LIMIT 3",
            esc, esc);
        if (mysql_query(conn, q)) {
            printf("  (table_registry unavailable)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res || mysql_num_rows(res) == 0) {
                printf("  Suggested: instructions (category=general)\n\n");
                if (res) mysql_free_result(res);
            } else {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    printf("  -> %s [%s] %s\n",
                        row[0] ? row[0] : "?",
                        row[1] ? row[1] : "?",
                        row[2] ? row[2] : "");
                }
                mysql_free_result(res);
                printf("\n");
                total_sections++;
            }
        }
    }

    /* ════════════════════════════════════════════
     * 9. CONFIDENCE — aggregate from learned_rules
     * ════════════════════════════════════════════ */
    printf("────────── CONFIDENCE ──────────\n");
    {
        snprintf(q, sizeof(q),
            "SELECT AVG(confidence), COUNT(*) FROM learned_rules WHERE pattern LIKE '%%%s%%'",
            esc);
        if (mysql_query(conn, q)) {
            printf("  (unable to compute)\n\n");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row = mysql_fetch_row(res);
            double avg = row[0] ? atof(row[0]) : 0;
            int cnt = row[1] ? atoi(row[1]) : 0;
            if (cnt > 0) {
                printf("  Rules: %d, Avg confidence: %.2f\n", cnt, avg);
                if (avg >= 0.9)
                    printf("  Verdict: HIGH CONFIDENCE — well-established pattern\n");
                else if (avg >= 0.7)
                    printf("  Verdict: MEDIUM CONFIDENCE — some evidence\n");
                else
                    printf("  Verdict: LOW CONFIDENCE — emerging pattern\n");
            } else {
                printf("  No confidence data — keyword not in learned_rules.\n");
            }
            mysql_free_result(res);
            printf("\n");
            total_sections++;
        }
    }

    /* ════════════════════════════════════════════
     * 10. NEXT ACTIONS
     * ════════════════════════════════════════════ */
    printf("────────── NEXT ACTIONS ──────────\n");
    printf("  [1] Open authority file (grep for class on disk)\n");
    printf("  [2] Show callers (msearch \"%s\" --table class_graph)\n", keyword);
    printf("  [3] Full search (msearch \"%s\" --limit 20)\n", keyword);
    printf("  [4] Verify rules (msearch \"%s\" --table learned_rules)\n", keyword);
    printf("  [5] Semantic search (msearch \"%s\" --semantic --top 5)\n", keyword);
    printf("  [6] Where to store (msearch --where \"%s\")\n", keyword);
    printf("  [7] VBStyle check (msearch --vbstyle <file.py>)\n");
    printf("\n");

    /* ── Summary ── */
    printf("══════════════════════════════════════════════════\n");
    printf("  SECTIONS: %d populated | TOTAL MATCHES: %d\n",
        total_sections, total_matches);
    printf("══════════════════════════════════════════════════\n");
}

/* ════════════════════════════════════════════
 * USAGE
 * ════════════════════════════════════════════ */

static void usage(const char *p) {
    fprintf(stderr,
        "msearch3 v6 — Context Reconstruction Engine\n"
        "\n"
        "Usage: %s <keyword> [options]\n"
        "\n"
        "Context reconstruction (v6 NEW):\n"
        "  --context-reconstruct  Multi-radius context packet (chat + code + Q&A + rules)\n"
        "  --radius <N>           Context radius in messages/lines (default: 200)\n"
        "  --mode <mode>          Match mode: magnetic (default), exact, prefix, regex\n"
        "  --web                  External discovery layer (GitHub, Stack Overflow, Google, Gemini, Reddit)\n"
        "\n"
        "Match modes:\n"
        "  magnetic  Substring match: LIKE '%%kw%%' + blast radius (default)\n"
        "  exact     Exact match only: = 'kw' (no substring)\n"
        "  prefix    Prefix match: LIKE 'kw%%' (starts with keyword)\n"
        "  regex     MySQL regex: REGEXP 'kw' (pattern matching)\n"
        "\n"
        "Smart mode (v5):\n"
        "  --smart              Consolidated 10-section semantic object (1 query, all info)\n"
        "\n"
        "Search options:\n"
        "  --table <substr>    Filter tables by name substring\n"
        "  --db <database>     Database name (default: vb_shared)\n"
        "  --limit <N>         Max rows per table (default: 50)\n"
        "  --type <type>       Semantic type filter: token_table, code_table, data_table, meta_table\n"
        "  --context <text>    Context for relevance ranking\n"
        "  --status <status>   Filter by status\n"
        "\n"
        "Output modes:\n"
        "  --json              JSON output for programmatic parsing\n"
        "  --dump              Full output (no truncation) for code_classes\n"
        "  --truth             Show four truth streams status\n"
        "\n"
        "Special modes:\n"
        "  --where <keyword>   Show where to store new data (update routing)\n"
        "  --all-db            Search across vb_shared + CODEBASE\n"
        "  --all-mysql         Auto-discover and search ALL MySQL databases\n"
        "  --deep              Include data_table types (huge LONGTEXT dumps like chat_ingestions)\n"
        "  --count             Show match counts per table only (no row data)\n"
        "  --and               Multi-keyword AND mode (default: OR)\n"
        "  --no-fulltext       Force LIKE search even if FULLTEXT index exists\n"
        "  --vbstyle <file>    Run VBStyle enforcer on a Python file (calls vbcheck)\n"
        "\n"
        "Qdrant vector search (v4):\n"
        "  --semantic          Search Qdrant vector DB (auto-embeds query via BGE)\n"
        "  --dimension <name>  Qdrant collection: dim_semantic, dim_structural, dim_dependency,\n"
        "                      dim_control_flow, dim_execution, dim_data_flow, dim_capability, etc.\n"
        "  --multi             Search multiple Qdrant dimensions simultaneously\n"
        "  --hybrid            Combine MySQL keyword search + Qdrant vector search\n"
        "  --qstats            Show Qdrant collection stats (point counts, vector sizes)\n"
        "  --top <N>           Number of vector results (default: 10)\n"
        "\n"
        "Connection:\n"
        "  --host <host>       MySQL host (default: localhost)\n"
        "  --user <user>       MySQL user (default: root)\n"
        "  --pass <pass>       MySQL password (default: empty)\n"
        "  --port <port>       MySQL port (default: 3306)\n"
        "\n"
        "Examples:\n"
        "  %s \"VBStyle\" --table instructions\n"
        "  %s \"Tuple3\" --json\n"
        "  %s \"MemUnit lifecycle\" --semantic --top 5\n"
        "  %s \"bracket authority\" --dimension dim_structural --top 10\n"
        "  %s \"domain collapse\" --multi --top 5\n"
        "  %s \"Zero-Drift\" --hybrid --top 5\n"
        "  %s --qstats\n"
        "  %s --where \"new VBStyle rule\"\n",
        p, p, p, p, p, p, p, p, p);
}

/* ════════════════════════════════════════════
 * MAIN
 * ════════════════════════════════════════════ */

int main(int argc, char **argv) {

    const char *keyword = NULL;
    const char *table_filter = NULL;
    const char *db = DEF_DB;
    int limit = DEF_LIMIT;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--table") && i + 1 < argc)
            table_filter = argv[++i];
        else if (!strcmp(argv[i], "--db") && i + 1 < argc)
            db = argv[++i];
        else if (!strcmp(argv[i], "--limit") && i + 1 < argc)
            limit = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--type") && i + 1 < argc)
            opt_type = argv[++i];
        else if (!strcmp(argv[i], "--context") && i + 1 < argc)
            opt_context = argv[++i];
        else if (!strcmp(argv[i], "--status") && i + 1 < argc)
            opt_status = argv[++i];
        else if (!strcmp(argv[i], "--json"))
            opt_json = 1;
        else if (!strcmp(argv[i], "--dump"))
            opt_dump = 1;
        else if (!strcmp(argv[i], "--truth"))
            opt_truth = 1;
        else if (!strcmp(argv[i], "--all-db"))
            opt_all_db = 1;
        else if (!strcmp(argv[i], "--all-mysql"))
            opt_all_mysql = 1;
        else if (!strcmp(argv[i], "--deep"))
            opt_deep = 1;
        else if (!strcmp(argv[i], "--count"))
            opt_count = 1;
        else if (!strcmp(argv[i], "--and"))
            strcpy(opt_kw_mode, "and");
        else if (!strcmp(argv[i], "--no-fulltext"))
            opt_fulltext = 0;
        else if (!strcmp(argv[i], "--where")) {
            opt_where = 1;
            if (i + 1 < argc) keyword = argv[++i];
        }
        else if (!strcmp(argv[i], "--host") && i + 1 < argc)
            opt_host = argv[++i];
        else if (!strcmp(argv[i], "--user") && i + 1 < argc)
            opt_user = argv[++i];
        else if (!strcmp(argv[i], "--pass") && i + 1 < argc)
            opt_pass = argv[++i];
        else if (!strcmp(argv[i], "--port") && i + 1 < argc)
            opt_port = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--vbstyle")) {
            opt_vbstyle = 1;
            if (i + 1 < argc) keyword = argv[++i];
        }
        else if (!strcmp(argv[i], "--verbose"))
            opt_verbose = 1;
        else if (!strcmp(argv[i], "--smart"))
            opt_smart = 1;
        else if (!strcmp(argv[i], "--context-reconstruct") || !strcmp(argv[i], "--cr"))
            opt_context_recon = 1;
        else if (!strcmp(argv[i], "--radius") && i + 1 < argc)
            opt_radius = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--mode") && i + 1 < argc) {
            const char *m = argv[++i];
            if (!strcmp(m, "exact")) opt_mode = 1;
            else if (!strcmp(m, "prefix")) opt_mode = 2;
            else if (!strcmp(m, "regex")) opt_mode = 3;
            else opt_mode = 0; /* magnetic */
        }
        else if (!strcmp(argv[i], "--web"))
            opt_web = 1;
        /* Qdrant flags (v4) */
        else if (!strcmp(argv[i], "--semantic"))
            opt_semantic = 1;
        else if (!strcmp(argv[i], "--multi"))
            opt_multi = 1;
        else if (!strcmp(argv[i], "--hybrid"))
            opt_hybrid = 1;
        else if (!strcmp(argv[i], "--qstats"))
            opt_qstats = 1;
        else if (!strcmp(argv[i], "--dimension") && i + 1 < argc)
            opt_dimension = argv[++i];
        else if (!strcmp(argv[i], "--top") && i + 1 < argc)
            opt_top = atoi(argv[++i]);
        else if (argv[i][0] != '-' && !keyword)
            keyword = argv[i];
    }

    if (!keyword && !opt_vbstyle && !opt_qstats) {
        usage(argv[0]);
        return 1;
    }

    /* --vbstyle mode: exec vbcheck on the file */
    if (opt_vbstyle) {
        if (!keyword) {
            fprintf(stderr, "Error: --vbstyle requires a file path\n");
            return 1;
        }
        /* Build vbcheck command with same json flag */
        char cmd[2048];
        snprintf(cmd, sizeof(cmd), "/Users/wws/bin/vbcheck '%s'%s%s%s",
            keyword,
            opt_json ? " --json" : "",
            opt_dump ? " --strip" : "",
            opt_verbose ? " --verbose" : "");
        return system(cmd) == 0 ? 0 : 1;
    }

    /* --qstats mode: show Qdrant collection stats */
    if (opt_qstats) {
        qdrant_stats();
        return 0;
    }

    /* empty keyword rejection */
    if (keyword && keyword[0] == '\0') {
        fprintf(stderr, "Error: empty keyword not allowed.\n");
        return 1;
    }

    /* --semantic or --dimension mode: Qdrant vector search only */
    if (opt_semantic || opt_dimension) {
        opt_semantic = 1;  /* ensure semantic flag is set if dimension was used */
        qdrant_search(keyword);
        return 0;
    }

    /* --hybrid mode: MySQL + Qdrant combined */
    if (opt_hybrid) {
        hybrid_search(keyword, table_filter, db, limit);
        return 0;
    }

    /* v5: all-mysql mode — auto-discover every database */
    if (opt_all_mysql) {
        search_all_mysql(keyword, table_filter, limit);
        return 0;
    }

    /* #9: cross-database mode */
    if (opt_all_db) {
        search_all_databases(keyword, table_filter, limit);
        return 0;
    }

    /* v6: context reconstruction mode — multi-radius context packet */
    if (opt_context_recon) {
        MYSQL *conn = mysql_init(NULL);
        if (!mysql_real_connect(conn,
                opt_host ? opt_host : DEF_HOST,
                opt_user ? opt_user : DEF_USER,
                opt_pass ? opt_pass : DEF_PASS,
                db,
                opt_port ? opt_port : DEF_PORT, NULL, 0)) {
            fprintf(stderr, "Connection failed: %s\n", mysql_error(conn));
            return 1;
        }
        context_reconstruct(conn, keyword);
        mysql_close(conn);

        /* v6 NEW: external discovery + candidate compression layer
         * External layer proposes. Magnetic layer verifies.
         * External evidence → compressed entry points → ready for magnetic expansion */
        if (opt_web) {
            discovery_config_t wcfg;
            discovery_config_init(&wcfg);
            discovery_config_from_env(&wcfg);
            discovery_and_compress(keyword, &wcfg);
        }

        return 0;
    }

    /* v5: smart consolidated mode — 10 sections, 1 query */
    if (opt_smart) {
        MYSQL *conn = mysql_init(NULL);
        if (!mysql_real_connect(conn,
                opt_host ? opt_host : DEF_HOST,
                opt_user ? opt_user : DEF_USER,
                opt_pass ? opt_pass : DEF_PASS,
                db,
                opt_port ? opt_port : DEF_PORT, NULL, 0)) {
            fprintf(stderr, "Connection failed: %s\n", mysql_error(conn));
            return 1;
        }
        smart_search(conn, keyword);
        mysql_close(conn);
        return 0;
    }

    /* connect */
    MYSQL *conn = mysql_init(NULL);

    if (!mysql_real_connect(conn,
            opt_host ? opt_host : DEF_HOST,
            opt_user ? opt_user : DEF_USER,
            opt_pass ? opt_pass : DEF_PASS,
            db,
            opt_port ? opt_port : DEF_PORT, NULL, 0)) {
        fprintf(stderr, "Connection failed: %s\n", mysql_error(conn));
        return 1;
    }

    /* #7: update routing mode */
    if (opt_where) {
        show_where_to_store(conn, keyword);
        mysql_close(conn);
        return 0;
    }

    load_schema(conn, db);
    search(conn, keyword, table_filter, db, limit);

    mysql_close(conn);
    return 0;
}
