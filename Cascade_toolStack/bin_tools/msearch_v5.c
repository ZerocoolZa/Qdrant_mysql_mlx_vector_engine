/*
 * msearch.c v5 — Magnetic Context Reconstruction Engine
 *
 * v5 enhancements:
 * 18. Magnetic radius search (--magnetic) — context reconstruction
 * 19. Chat history radius (--magnetic --chat) — devin_messages ±N messages
 * 20. Multi-dimensional radius (text, AST, execution, dependency, temporal, conversation, semantic, BCL, IR)
 * 21. Context packet assembly — one query returns reconstructed neighborhood
 * 22. Custom radius (--radius N) — control expansion size
 *
 * v4 features preserved:
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

/* Qdrant flags (v4) */
static int  opt_semantic = 0;     /* --semantic: Qdrant vector search */
static int  opt_multi = 0;        /* --multi: search multiple Qdrant dimensions */
static int  opt_hybrid = 0;       /* --hybrid: MySQL + Qdrant combined */
static int  opt_qstats = 0;       /* --qstats: Qdrant collection stats */
static int  opt_full = 0;        /* --full: semantic object search (all sections) */
static int  opt_magnetic = 0;    /* --magnetic: context reconstruction with radius */
static int  opt_chat = 0;        /* --magnetic --chat: chat history radius only */
static int  opt_graph_radius = 0; /* --magnetic --graph: execution + dependency radius only */
static int  opt_radius = 200;    /* --radius N: expansion size (±N lines/messages) */
static char opt_mode[16] = "contains"; /* --mode: exact|prefix|contains|regex|magnetic */
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

/* ════════════════════════════════════════════
 * MATCH MODE BUILDER — builds SQL WHERE fragment based on --mode
 * exact:    `col` = 'keyword'
 * prefix:   `col` LIKE 'keyword%'
 * contains: `col` LIKE '%keyword%'   (default)
 * regex:    `col` REGEXP 'keyword'
 * ════════════════════════════════════════════ */
static void build_match(const char *col, const char *keyword, char *out, size_t out_sz) {
    char escaped[1024];
    escape_like(keyword, escaped, sizeof(escaped));
    if (strcmp(opt_mode, "exact") == 0) {
        snprintf(out, out_sz, "`%s` = '%s'", col, escaped);
    } else if (strcmp(opt_mode, "prefix") == 0) {
        snprintf(out, out_sz, "`%s` LIKE '%s%%'", col, escaped);
    } else if (strcmp(opt_mode, "regex") == 0) {
        snprintf(out, out_sz, "`%s` REGEXP '%s'", col, keyword);
    } else {
        snprintf(out, out_sz, "`%s` LIKE '%%%s%%'", col, escaped);
    }
}

/* Build a 2-column OR WHERE clause (e.g. "col1 LIKE '%kw%' OR col2 LIKE '%kw%'") */
static void build_match2(const char *col1, const char *col2, const char *keyword, char *out, size_t out_sz) {
    char frag1[512], frag2[512];
    build_match(col1, keyword, frag1, sizeof(frag1));
    build_match(col2, keyword, frag2, sizeof(frag2));
    snprintf(out, out_sz, "%s OR %s", frag1, frag2);
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

        /* build WHERE clause — cursor-based, mode-aware */
        char where[BUF];
        size_t wpos = 0;

        for (int c = 0; c < schema[i].col_count; c++) {
            char match_frag[512];
            build_match(schema[i].cols[c], keyword, match_frag, sizeof(match_frag));
            int written = snprintf(where + wpos, sizeof(where) - wpos,
                     "%s%s",
                     (c ? " OR " : ""),
                     match_frag);
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
 * USAGE
 * ════════════════════════════════════════════ */

static void usage(const char *p) {
    fprintf(stderr,
        "msearch v5 — Magnetic Context Reconstruction Engine\n"
        "\n"
        "Usage: %s <keyword> [options]\n"
        "\n"
        "Match modes (--mode):\n"
        "  --mode exact        Exact match only: col = 'keyword'\n"
        "  --mode prefix       Prefix match: col LIKE 'keyword%%'\n"
        "  --mode contains     Contains match: col LIKE '%%keyword%%' (default)\n"
        "  --mode regex        Regex match: col REGEXP 'keyword'\n"
        "  --mode magnetic     Magnetic radius: locate + expand + reconstruct context\n"
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

/* ════════════════════════════════════════════
 * ENHANCEMENT #18: FULL SEMANTIC OBJECT SEARCH (--full)
 * One search returns everything: Authority, Files, Classes, Methods,
 * Relationships, Rules, Examples, History, Confidence, Related, Actions
 * Assembles a structured JSON object from all table queries.
 * ════════════════════════════════════════════ */

static void full_search(MYSQL *conn, const char *keyword, int limit) {
    char escaped[1024];
    char esc_json[2048];
    escape_like(keyword, escaped, sizeof(escaped));
    json_escape(keyword, esc_json, sizeof(esc_json));

    load_schema(conn, "vb_shared");
    load_registry(conn);

    printf("{\"query\":\"%s\",\"sections\":{", esc_json);

    /* ── 1. AUTHORITY — canonical definition from class_understandings ── */
    printf("\"authority\":");
    {
        char q[BUF];
        char where_clause[1024];
        build_match2("class_name", "cascade_understanding", keyword, where_clause, sizeof(where_clause));
        snprintf(q, sizeof(q),
            "SELECT class_name, cascade_understanding, layer, code_classes_id "
            "FROM class_understandings WHERE %s LIMIT %d",
            where_clause, limit > 3 ? 3 : limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char cn[512], cu[4096];
                json_escape(row[0] ? row[0] : "", cn, sizeof(cn));
                json_escape(row[1] ? row[1] : "", cu, sizeof(cu));
                printf("%s{\"class\":\"%s\",\"understanding\":\"%s\",\"layer\":\"%s\"}",
                    first ? "" : ",", cn, cu, row[2] ? row[2] : "");
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 2. FILES — file paths from code_classes ── */
    printf(",\"files\":");
    {
        char q[BUF];
        char where_clause[512];
        build_match("class_name", keyword, where_clause, sizeof(where_clause));
        snprintf(q, sizeof(q),
            "SELECT class_name, class_code, description FROM code_classes "
            "WHERE %s LIMIT %d",
            where_clause, limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char cn[512], desc[1024];
                json_escape(row[0] ? row[0] : "", cn, sizeof(cn));
                json_escape(row[2] ? row[2] : "", desc, sizeof(desc));
                printf("%s{\"class\":\"%s\",\"description\":\"%s\"}",
                    first ? "" : ",", cn, desc);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 3. METHODS — from code_index ── */
    printf(",\"methods\":");
    {
        char q[BUF];
        char where_clause[1024];
        build_match2("entity_name", "related_entity", keyword, where_clause, sizeof(where_clause));
        snprintf(q, sizeof(q),
            "SELECT entity_name, entity_type, related_entity, relationship, evidence "
            "FROM code_index WHERE %s LIMIT %d",
            where_clause, limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char en[512], et[128], re[512], rel[128], ev[4096];
                json_escape(row[0] ? row[0] : "", en, sizeof(en));
                json_escape(row[1] ? row[1] : "", et, sizeof(et));
                json_escape(row[2] ? row[2] : "", re, sizeof(re));
                json_escape(row[3] ? row[3] : "", rel, sizeof(rel));
                json_escape(row[4] ? row[4] : "", ev, sizeof(ev));
                printf("%s{\"entity\":\"%s\",\"type\":\"%s\",\"related\":\"%s\",\"relationship\":\"%s\"}",
                    first ? "" : ",", en, et, re, rel);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 4. RELATIONSHIPS — from code_co_occurrence ── */
    printf(",\"relationships\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT entity_a, entity_b, relationship_type, weight "
            "FROM code_co_occurrence WHERE entity_a LIKE '%%%s%%' "
            "OR entity_b LIKE '%%%s%%' LIMIT %d",
            escaped, escaped, limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char ea[512], eb[512], rt[128];
                json_escape(row[0] ? row[0] : "", ea, sizeof(ea));
                json_escape(row[1] ? row[1] : "", eb, sizeof(eb));
                json_escape(row[2] ? row[2] : "", rt, sizeof(rt));
                printf("%s{\"a\":\"%s\",\"b\":\"%s\",\"type\":\"%s\",\"weight\":\"%s\"}",
                    first ? "" : ",", ea, eb, rt, row[3] ? row[3] : "1");
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 5. RULES — from learned_rules ── */
    printf(",\"rules\":");
    {
        char q[BUF];
        char where_clause[1024];
        build_match2("pattern", "fix_action", keyword, where_clause, sizeof(where_clause));
        snprintf(q, sizeof(q),
            "SELECT pattern, fix_action, confidence FROM learned_rules "
            "WHERE %s ORDER BY confidence DESC LIMIT %d",
            where_clause, limit > 5 ? 5 : limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char pat[2048], fix[2048], conf[64];
                json_escape(row[0] ? row[0] : "", pat, sizeof(pat));
                json_escape(row[1] ? row[1] : "", fix, sizeof(fix));
                json_escape(row[2] ? row[2] : "", conf, sizeof(conf));
                printf("%s{\"pattern\":\"%s\",\"fix\":\"%s\",\"confidence\":\"%s\"}",
                    first ? "" : ",", pat, fix, conf);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 6. EXAMPLES — from code_registry ── */
    printf(",\"examples\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT token_name, LEFT(code, 500) FROM code_registry "
            "WHERE token_name LIKE '%%%s%%' LIMIT %d",
            escaped, limit > 3 ? 3 : limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char tn[512], code[2048];
                json_escape(row[0] ? row[0] : "", tn, sizeof(tn));
                json_escape(row[1] ? row[1] : "", code, sizeof(code));
                printf("%s{\"name\":\"%s\",\"preview\":\"%s\"}",
                    first ? "" : ",", tn, code);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 7. HISTORY — from execution_log ── */
    printf(",\"history\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT command, status, timestamp FROM execution_log "
            "WHERE command LIKE '%%%s%%' ORDER BY timestamp DESC LIMIT %d",
            escaped, limit > 5 ? 5 : limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char cmd[2048], st[64], ts[64];
                json_escape(row[0] ? row[0] : "", cmd, sizeof(cmd));
                json_escape(row[1] ? row[1] : "", st, sizeof(st));
                json_escape(row[2] ? row[2] : "", ts, sizeof(ts));
                printf("%s{\"command\":\"%s\",\"status\":\"%s\",\"timestamp\":\"%s\"}",
                    first ? "" : ",", cmd, st, ts);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 8. ERRORS — from error_knowledge ── */
    printf(",\"errors\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT error_type, cause, solution, confidence FROM error_knowledge "
            "WHERE error_type LIKE '%%%s%%' OR cause LIKE '%%%s%%' LIMIT %d",
            escaped, escaped, limit > 3 ? 3 : limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char et[512], cause[2048], sol[2048], conf[64];
                json_escape(row[0] ? row[0] : "", et, sizeof(et));
                json_escape(row[1] ? row[1] : "", cause, sizeof(cause));
                json_escape(row[2] ? row[2] : "", sol, sizeof(sol));
                json_escape(row[3] ? row[3] : "", conf, sizeof(conf));
                printf("%s{\"type\":\"%s\",\"cause\":\"%s\",\"solution\":\"%s\",\"confidence\":\"%s\"}",
                    first ? "" : ",", et, cause, sol, conf);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 9. RELATED — from code_identifier_frequency ── */
    printf(",\"related\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT identifier, identifier_type, frequency, authority_score "
            "FROM code_identifier_frequency WHERE identifier LIKE '%%%s%%' "
            "ORDER BY authority_score DESC LIMIT %d",
            escaped, limit > 10 ? 10 : limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char id[512], it[128], freq[64], auth[64];
                json_escape(row[0] ? row[0] : "", id, sizeof(id));
                json_escape(row[1] ? row[1] : "", it, sizeof(it));
                json_escape(row[2] ? row[2] : "", freq, sizeof(freq));
                json_escape(row[3] ? row[3] : "", auth, sizeof(auth));
                printf("%s{\"identifier\":\"%s\",\"type\":\"%s\",\"frequency\":\"%s\",\"authority\":\"%s\"}",
                    first ? "" : ",", id, it, freq, auth);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 10. DESIGN RATIONALE — from designrationale ── */
    printf(",\"rationale\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT subject, rationale, category FROM designrationale "
            "WHERE subject LIKE '%%%s%%' OR rationale LIKE '%%%s%%' LIMIT %d",
            escaped, escaped, limit > 3 ? 3 : limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char subj[512], rat[4096], cat[128];
                json_escape(row[0] ? row[0] : "", subj, sizeof(subj));
                json_escape(row[1] ? row[1] : "", rat, sizeof(rat));
                json_escape(row[2] ? row[2] : "", cat, sizeof(cat));
                printf("%s{\"subject\":\"%s\",\"rationale\":\"%s\",\"category\":\"%s\"}",
                    first ? "" : ",", subj, rat, cat);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 11. PROBLEMS — from know_problems ── */
    printf(",\"problems\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT problem, description FROM know_problems "
            "WHERE problem LIKE '%%%s%%' OR description LIKE '%%%s%%' LIMIT %d",
            escaped, escaped, limit > 3 ? 3 : limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char prob[512], desc[2048];
                json_escape(row[0] ? row[0] : "", prob, sizeof(prob));
                json_escape(row[1] ? row[1] : "", desc, sizeof(desc));
                printf("%s{\"problem\":\"%s\",\"description\":\"%s\"}",
                    first ? "" : ",", prob, desc);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 12. DECISIONS — from decision_trees ── */
    printf(",\"decisions\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT tree FROM decision_trees WHERE tree LIKE '%%%s%%' LIMIT %d",
            escaped, limit > 3 ? 3 : limit);
        if (mysql_query(conn, q)) {
            printf("null");
        } else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row;
            int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char tree[4096];
                json_escape(row[0] ? row[0] : "", tree, sizeof(tree));
                printf("%s\"%s\"", first ? "" : ",", tree);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── Close sections + actions ── */
    printf("},\"actions\":[\"open\",\"edit\",\"ingest\",\"verify\",\"reindex\"]}");
}

/* ════════════════════════════════════════════
 * ENHANCEMENT #19: MAGNETIC RADIUS SEARCH (--magnetic)
 * Context reconstruction engine — finds keyword, expands radius,
 * returns a context packet with chat history, graph, code, rules.
 * ════════════════════════════════════════════ */

static void magnetic_search(MYSQL *conn, const char *keyword, int radius, int limit) {
    char escaped[1024];
    char esc_json[2048];
    escape_like(keyword, escaped, sizeof(escaped));
    json_escape(keyword, esc_json, sizeof(esc_json));

    load_schema(conn, "vb_shared");
    load_registry(conn);

    printf("{\"query\":\"%s\",\"radius\":%d,\"packet\":{", esc_json, radius);

    /* ── 1. AUTHORITY — canonical definition ── */
    printf("\"authority\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT class_name, cascade_understanding, layer "
            "FROM class_understandings WHERE class_name LIKE '%%%s%%' "
            "OR cascade_understanding LIKE '%%%s%%' LIMIT %d",
            escaped, escaped, limit > 3 ? 3 : limit);
        if (mysql_query(conn, q)) { printf("null"); }
        else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row; int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char cn[512], cu[4096];
                json_escape(row[0]?row[0]:"", cn, sizeof(cu));
                json_escape(row[1]?row[1]:"", cu, sizeof(cu));
                printf("%s{\"class\":\"%s\",\"understanding\":\"%s\",\"layer\":\"%s\"}",
                    first?"":",", cn, cu, row[2]?row[2]:"");
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 2. CHAT HISTORY RADIUS — devin_messages ±N messages around each hit ── */
    printf(",\"chat_context\":");
    if (opt_chat || opt_magnetic) {
        /* Connect to devin database for chat history */
        MYSQL *chat_conn = mysql_init(NULL);
        if (mysql_real_connect(chat_conn,
                opt_host?opt_host:DEF_HOST,
                opt_user?opt_user:DEF_USER,
                opt_pass?opt_pass:DEF_PASS,
                "devin",
                opt_port?opt_port:DEF_PORT, NULL, 0)) {
            char q[BUF];
            /* Find messages containing the keyword, get session_id and row_id */
            snprintf(q, sizeof(q),
                "SELECT session_id, row_id, role, LEFT(content, 200) "
                "FROM devin_messages WHERE content LIKE '%%%s%%' "
                "ORDER BY created_at DESC LIMIT %d",
                escaped, limit > 5 ? 5 : limit);
            if (mysql_query(chat_conn, q)) {
                printf("null");
            } else {
                MYSQL_RES *res = mysql_store_result(chat_conn);
                MYSQL_ROW row; int first = 1;
                printf("[");
                while ((row = mysql_fetch_row(res))) {
                    char sid[256], role[64], content[512];
                    json_escape(row[0]?row[0]:"", sid, sizeof(sid));
                    json_escape(row[2]?row[2]:"", role, sizeof(role));
                    json_escape(row[3]?row[3]:"", content, sizeof(content));
                    int hit_row = row[1] ? atoi(row[1]) : 0;
                    int win_start = hit_row - radius;
                    int win_end = hit_row + radius;
                    if (win_start < 0) win_start = 0;

                    /* Fetch the context window — messages around the hit */
                    char wq[BUF];
                    snprintf(wq, sizeof(wq),
                        "SELECT role, LEFT(content, 300) FROM devin_messages "
                        "WHERE session_id = '%s' AND row_id >= %d AND row_id <= %d "
                        "ORDER BY row_id LIMIT 20",
                        sid, win_start, win_end);
                    char window_text[8192];
                    window_text[0] = '\0';
                    if (mysql_query(chat_conn, wq) == 0) {
                        MYSQL_RES *wres = mysql_store_result(chat_conn);
                        MYSQL_ROW wrow;
                        while ((wrow = mysql_fetch_row(wres))) {
                            char wrole[64], wcontent[512];
                            json_escape(wrow[0]?wrow[0]:"", wrole, sizeof(wrole));
                            json_escape(wrow[1]?wrow[1]:"", wcontent, sizeof(wcontent));
                            char part[700];
                            snprintf(part, sizeof(part), "%s[%s] %s\\n",
                                window_text[0]?"":"", wrole, wcontent);
                            strncat(window_text, part, sizeof(window_text) - strlen(window_text) - 1);
                        }
                        mysql_free_result(wres);
                    }

                    char wt[8192];
                    json_escape(window_text, wt, sizeof(wt));
                    printf("%s{\"session\":\"%s\",\"hit_row\":%d,\"window\":\"±%d messages\",\"role\":\"%s\",\"preview\":\"%s\",\"context\":\"%s\"}",
                        first?"":",", sid, hit_row, radius, role, content, wt);
                    first = 0;
                }
                printf("]");
                mysql_free_result(res);
            }
            mysql_close(chat_conn);
        } else {
            printf("null");
        }
    } else {
        printf("null");
    }

    /* ── 3. GRAPH RADIUS — callers, callees, dependencies from bcl_ir ── */
    printf(",\"graph\":");
    if (opt_graph_radius || opt_magnetic) {
        MYSQL *bcl_conn = mysql_init(NULL);
        if (mysql_real_connect(bcl_conn,
                opt_host?opt_host:DEF_HOST,
                opt_user?opt_user:DEF_USER,
                opt_pass?opt_pass:DEF_PASS,
                "bcl_ir",
                opt_port?opt_port:DEF_PORT, NULL, 0)) {
            char q[BUF];
            /* Callers — who calls methods matching keyword */
            snprintf(q, sizeof(q),
                "SELECT DISTINCT source_method_id, target, edge_type, line_number "
                "FROM bcl_edges WHERE (source_method_id LIKE '%%%s%%' "
                "OR target LIKE '%%%s%%') AND edge_type = 'CALL' LIMIT %d",
                escaped, escaped, limit > 10 ? 10 : limit);
            printf("{\"callers\":");
            if (mysql_query(bcl_conn, q)) { printf("null"); }
            else {
                MYSQL_RES *res = mysql_store_result(bcl_conn);
                MYSQL_ROW row; int first = 1;
                printf("[");
                while ((row = mysql_fetch_row(res))) {
                    char src[512], tgt[512], et[64];
                    json_escape(row[0]?row[0]:"", src, sizeof(src));
                    json_escape(row[1]?row[1]:"", tgt, sizeof(tgt));
                    json_escape(row[2]?row[2]:"", et, sizeof(et));
                    printf("%s{\"source\":\"%s\",\"target\":\"%s\",\"line\":\"%s\"}",
                        first?"":",", src, tgt, row[3]?row[3]:"0");
                    first = 0;
                }
                printf("]");
                mysql_free_result(res);
            }

            /* Dependencies — imports, state reads, state writes */
            snprintf(q, sizeof(q),
                "SELECT DISTINCT source_method_id, target, edge_type "
                "FROM bcl_edges WHERE (source_method_id LIKE '%%%s%%' "
                "OR target LIKE '%%%s%%') AND edge_type IN ('IMPORT','STATE_READ','STATE_WRITE','RESOURCE') LIMIT %d",
                escaped, escaped, limit > 10 ? 10 : limit);
            printf(",\"dependencies\":");
            if (mysql_query(bcl_conn, q)) { printf("null"); }
            else {
                MYSQL_RES *res = mysql_store_result(bcl_conn);
                MYSQL_ROW row; int first = 1;
                printf("[");
                while ((row = mysql_fetch_row(res))) {
                    char src[512], tgt[512], et[64];
                    json_escape(row[0]?row[0]:"", src, sizeof(src));
                    json_escape(row[1]?row[1]:"", tgt, sizeof(tgt));
                    json_escape(row[2]?row[2]:"", et, sizeof(et));
                    printf("%s{\"source\":\"%s\",\"target\":\"%s\",\"type\":\"%s\"}",
                        first?"":",", src, tgt, et);
                    first = 0;
                }
                printf("]");
                mysql_free_result(res);
            }
            printf("}");
            mysql_close(bcl_conn);
        } else {
            printf("null");
        }
    } else {
        printf("null");
    }

    /* ── 4. CODE — files, classes, methods from vb_shared ── */
    printf(",\"code\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT class_name, description FROM code_classes "
            "WHERE class_name LIKE '%%%s%%' LIMIT %d",
            escaped, limit > 3 ? 3 : limit);
        if (mysql_query(conn, q)) { printf("null"); }
        else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row; int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char cn[512], desc[1024];
                json_escape(row[0]?row[0]:"", cn, sizeof(cn));
                json_escape(row[1]?row[1]:"", desc, sizeof(desc));
                printf("%s{\"class\":\"%s\",\"description\":\"%s\"}",
                    first?"":",", cn, desc);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 5. RULES — learned rules ── */
    printf(",\"rules\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT pattern, fix_action, confidence FROM learned_rules "
            "WHERE pattern LIKE '%%%s%%' OR fix_action LIKE '%%%s%%' "
            "ORDER BY confidence DESC LIMIT %d",
            escaped, escaped, limit > 5 ? 5 : limit);
        if (mysql_query(conn, q)) { printf("null"); }
        else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row; int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char pat[2048], fix[2048], conf[64];
                json_escape(row[0]?row[0]:"", pat, sizeof(pat));
                json_escape(row[1]?row[1]:"", fix, sizeof(fix));
                json_escape(row[2]?row[2]:"", conf, sizeof(conf));
                printf("%s{\"pattern\":\"%s\",\"fix\":\"%s\",\"confidence\":\"%s\"}",
                    first?"":",", pat, fix, conf);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 6. METHODS — from code_index ── */
    printf(",\"methods\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT entity_name, entity_type, related_entity, relationship "
            "FROM code_index WHERE entity_name LIKE '%%%s%%' "
            "OR related_entity LIKE '%%%s%%' LIMIT %d",
            escaped, escaped, limit);
        if (mysql_query(conn, q)) { printf("null"); }
        else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row; int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char en[512], et[128], re[512], rel[128];
                json_escape(row[0]?row[0]:"", en, sizeof(en));
                json_escape(row[1]?row[1]:"", et, sizeof(et));
                json_escape(row[2]?row[2]:"", re, sizeof(re));
                json_escape(row[3]?row[3]:"", rel, sizeof(rel));
                printf("%s{\"entity\":\"%s\",\"type\":\"%s\",\"related\":\"%s\",\"relationship\":\"%s\"}",
                    first?"":",", en, et, re, rel);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 7. HISTORY — execution log ── */
    printf(",\"timeline\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT command, status, timestamp FROM execution_log "
            "WHERE command LIKE '%%%s%%' ORDER BY timestamp DESC LIMIT %d",
            escaped, limit > 5 ? 5 : limit);
        if (mysql_query(conn, q)) { printf("null"); }
        else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row; int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char cmd[2048], st[64], ts[64];
                json_escape(row[0]?row[0]:"", cmd, sizeof(cmd));
                json_escape(row[1]?row[1]:"", st, sizeof(st));
                json_escape(row[2]?row[2]:"", ts, sizeof(ts));
                printf("%s{\"command\":\"%s\",\"status\":\"%s\",\"timestamp\":\"%s\"}",
                    first?"":",", cmd, st, ts);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 8. RELATED — identifier frequency ── */
    printf(",\"related\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT identifier, identifier_type, authority_score "
            "FROM code_identifier_frequency WHERE identifier LIKE '%%%s%%' "
            "ORDER BY authority_score DESC LIMIT %d",
            escaped, limit > 10 ? 10 : limit);
        if (mysql_query(conn, q)) { printf("null"); }
        else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row; int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char id[512], it[128], auth[64];
                json_escape(row[0]?row[0]:"", id, sizeof(id));
                json_escape(row[1]?row[1]:"", it, sizeof(it));
                json_escape(row[2]?row[2]:"", auth, sizeof(auth));
                printf("%s{\"identifier\":\"%s\",\"type\":\"%s\",\"authority\":\"%s\"}",
                    first?"":",", id, it, auth);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── 9. ERRORS — error knowledge ── */
    printf(",\"errors\":");
    {
        char q[BUF];
        snprintf(q, sizeof(q),
            "SELECT error_type, cause, solution FROM error_knowledge "
            "WHERE error_type LIKE '%%%s%%' OR cause LIKE '%%%s%%' LIMIT %d",
            escaped, escaped, limit > 3 ? 3 : limit);
        if (mysql_query(conn, q)) { printf("null"); }
        else {
            MYSQL_RES *res = mysql_store_result(conn);
            MYSQL_ROW row; int first = 1;
            printf("[");
            while ((row = mysql_fetch_row(res))) {
                char et[512], cause[2048], sol[2048];
                json_escape(row[0]?row[0]:"", et, sizeof(et));
                json_escape(row[1]?row[1]:"", cause, sizeof(cause));
                json_escape(row[2]?row[2]:"", sol, sizeof(sol));
                printf("%s{\"type\":\"%s\",\"cause\":\"%s\",\"solution\":\"%s\"}",
                    first?"":",", et, cause, sol);
                first = 0;
            }
            printf("]");
            mysql_free_result(res);
        }
    }

    /* ── Close packet ── */
    printf("},\"actions\":[\"open\",\"edit\",\"ingest\",\"verify\",\"reindex\",\"expand_radius\",\"show_chat\"]}");
}

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
        /* Qdrant flags (v4) */
        else if (!strcmp(argv[i], "--semantic"))
            opt_semantic = 1;
        else if (!strcmp(argv[i], "--multi"))
            opt_multi = 1;
        else if (!strcmp(argv[i], "--hybrid"))
            opt_hybrid = 1;
        else if (!strcmp(argv[i], "--qstats"))
            opt_qstats = 1;
        else if (!strcmp(argv[i], "--full"))
            opt_full = 1;
        else if (!strcmp(argv[i], "--magnetic"))
            opt_magnetic = 1;
        else if (!strcmp(argv[i], "--chat"))
            opt_chat = 1;
        else if (!strcmp(argv[i], "--graph-radius"))
            opt_graph_radius = 1;
        else if (!strcmp(argv[i], "--radius") && i + 1 < argc)
            opt_radius = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--mode") && i + 1 < argc) {
            strncpy(opt_mode, argv[++i], sizeof(opt_mode) - 1);
            opt_mode[sizeof(opt_mode) - 1] = '\0';
            if (strcmp(opt_mode, "magnetic") == 0) opt_magnetic = 1;
        }
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

    /* --full mode: semantic object search (all 12 sections in one query) */
    if (opt_full && keyword) {
        MYSQL *conn = mysql_init(NULL);
        if (!mysql_real_connect(conn,
                opt_host ? opt_host : DEF_HOST,
                opt_user ? opt_user : DEF_USER,
                opt_pass ? opt_pass : DEF_PASS,
                DEF_DB,
                opt_port ? opt_port : DEF_PORT, NULL, 0)) {
            fprintf(stderr, "Connection failed: %s\n", mysql_error(conn));
            return 1;
        }
        full_search(conn, keyword, limit);
        mysql_close(conn);
        return 0;
    }

    /* --magnetic mode: context reconstruction with radius expansion */
    if (opt_magnetic && keyword) {
        MYSQL *conn = mysql_init(NULL);
        if (!mysql_real_connect(conn,
                opt_host ? opt_host : DEF_HOST,
                opt_user ? opt_user : DEF_USER,
                opt_pass ? opt_pass : DEF_PASS,
                DEF_DB,
                opt_port ? opt_port : DEF_PORT, NULL, 0)) {
            fprintf(stderr, "Connection failed: %s\n", mysql_error(conn));
            return 1;
        }
        magnetic_search(conn, keyword, opt_radius, limit);
        mysql_close(conn);
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
