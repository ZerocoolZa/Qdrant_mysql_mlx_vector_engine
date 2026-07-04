//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_schemalint.c" date="2026-07-04" author="Devin" session_id="bcl-schemalint" context="BCL unit - MySQL schema linter. Connects to MySQL, runs SHOW TABLES + DESCRIBE per table, checks for PK, wide VARCHAR, TEXT without index, missing timestamps, naming inconsistency, too-wide tables. Commands: lint, lint_all, report, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_schemalint.c" domain="cascade_tools" authority="Schemalint"}
//[@SUMMARY]{summary="MySQL schema linter BCL unit. Lint a single DB or all DBs. Checks: no PK, wide VARCHAR without index, TEXT without index, missing created_at/updated_at, snake_case vs camelCase, >50 columns. Returns BCL violation list."}
//[@CLASS]{class="Schemalint" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}

#include "bcl_toolstack.h"
#include <mysql.h>

/* ===== DIM BLOCK ===== */

#define SCHEMALINT_MAX_TABLES    512
#define SCHEMALINT_MAX_COLS      128
#define SCHEMALINT_MAX_NAME      128
#define SCHEMALINT_MAX_BCL_OUT   65536
#define SCHEMALINT_DEFAULT_MAXC  50
#define SCHEMALINT_VARCHAR_LIMIT 255
#define SCHEMALINT_HOST_LEN      256
#define SCHEMALINT_USER_LEN      64
#define SCHEMALINT_PASS_LEN      128
#define SCHEMALINT_SOCKET_LEN    256
#define SCHEMALINT_VIOL_TYPES    10

/* Violation issue codes — indices into violations_by_type[] */
enum {
    V_NO_PK = 0,        /* table without primary key            */
    V_WIDE_VARCHAR,     /* VARCHAR > 255 without index          */
    V_TEXT_NO_INDEX,    /* TEXT column without corresponding idx */
    V_MISSING_CREATED,  /* missing created_at timestamp column  */
    V_MISSING_UPDATED,  /* missing updated_at timestamp column  */
    V_NAMING_MIX,       /* snake_case vs camelCase inconsistency */
    V_TOO_WIDE,         /* table has > max_columns columns       */
    V_TYPE_COUNT        /* sentinel — must be last              */
};

/* ===== STATE ===== */

static struct {
    int  initialized;
    int  lints_run;
    int  total_violations;
    char last_db[SCHEMALINT_MAX_NAME];
    int  violations_by_type[SCHEMALINT_VIOL_TYPES];
    /* config */
    char db_name[SCHEMALINT_MAX_NAME];
    int  max_columns;
    int  check_timestamps;
    /* mysql connection config */
    char host[SCHEMALINT_HOST_LEN];
    char user[SCHEMALINT_USER_LEN];
    char pass[SCHEMALINT_PASS_LEN];
    char socket[SCHEMALINT_SOCKET_LEN];
    int  port;
    /* last lint report buffer */
    char last_report[SCHEMALINT_MAX_BCL_OUT];
    char last_error[256];
} STATE;

/* ===== ENSURE CONNECTED ===== */

static int schemalint_ensure_connected(MYSQL *conn) {
    const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
    MYSQL *result = mysql_real_connect(conn,
        STATE.host, STATE.user,
        STATE.pass[0] ? STATE.pass : NULL,
        NULL, STATE.port, sock, 0);
    if (!result) {
        result = mysql_real_connect(conn,
            STATE.host, STATE.user,
            STATE.pass[0] ? STATE.pass : NULL,
            NULL, STATE.port, NULL, 0);
    }
    if (!result) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "connect: %s", mysql_error(conn));
        return 0;
    }
    return 1;
}

/* ===== NAMING DETECTORS ===== */

static int is_camel_case(const char *name) {
    int has_upper = 0, has_lower = 0, has_underscore = 0;
    for (const char *p = name; *p; p++) {
        if (*p >= 'A' && *p <= 'Z') has_upper = 1;
        if (*p >= 'a' && *p <= 'z') has_lower = 1;
        if (*p == '_') has_underscore = 1;
    }
    /* camelCase: mixed case, no underscores, starts lower */
    return (has_upper && has_lower && !has_underscore);
}

static int is_snake_case(const char *name) {
    int has_underscore = 0, has_upper = 0;
    for (const char *p = name; *p; p++) {
        if (*p == '_') has_underscore = 1;
        if (*p >= 'A' && *p <= 'Z') has_upper = 1;
    }
    /* snake_case: has underscore, all lowercase letters */
    return (has_underscore && !has_upper);
}

/* ===== VIOLATION HELPERS ===== */

static void count_violation(int type) {
    if (type >= 0 && type < V_TYPE_COUNT) {
        STATE.violations_by_type[type]++;
        STATE.total_violations++;
    }
}

static void append_violation(char *out, size_t out_sz, int *offset,
                             const char *table, const char *col,
                             int issue, const char *severity) {
    static const char *ISSUE_NAMES[] = {
        "no_pk", "wide_varchar_no_index", "text_no_index",
        "missing_created_at", "missing_updated_at",
        "naming_inconsistent", "too_wide"
    };
    const char *iname = (issue >= 0 && issue < V_TYPE_COUNT)
        ? ISSUE_NAMES[issue] : "unknown";
    if (col && col[0]) {
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@VIOLATION]{[@TABLE]{%s}[@COLUMN]{%s}[@ISSUE]{%s}[@SEVERITY]{%s}}",
            table, col, iname, severity);
    } else {
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@VIOLATION]{[@TABLE]{%s}[@ISSUE]{%s}[@SEVERITY]{%s}}",
            table, iname, severity);
    }
    count_violation(issue);
}

/* ===== LINT ONE TABLE ===== */

static void lint_one_table(MYSQL *conn, const char *db, const char *table,
                           char *out, size_t out_sz, int *offset) {
    char sql[256];
    snprintf(sql, sizeof(sql), "DESCRIBE `%s`.`%s`", db, table);
    if (mysql_query(conn, sql) != 0) return;
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) return;

    int has_pk = 0, col_count = 0, has_created = 0, has_updated = 0;
    int snake_count = 0, camel_count = 0;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL &&
           col_count < SCHEMALINT_MAX_COLS) {
        const char *fname = row[0] ? row[0] : "";
        const char *ftype = row[1] ? row[1] : "";
        const char *fkey  = row[3] ? row[3] : "";
        int indexed = (strcmp(fkey, "PRI") == 0 || strcmp(fkey, "UNI") == 0 ||
                       strcmp(fkey, "MUL") == 0);
        if (strcmp(fkey, "PRI") == 0) has_pk = 1;
        if (strstr(fname, "created_at") || strstr(fname, "created_time") ||
            strstr(fname, "createdAt")) has_created = 1;
        if (strstr(fname, "updated_at") || strstr(fname, "updated_time") ||
            strstr(fname, "updatedAt")) has_updated = 1;
        if (is_snake_case(fname)) snake_count++;
        if (is_camel_case(fname)) camel_count++;
        /* VARCHAR > 255 without index */
        if (strncasecmp(ftype, "varchar", 7) == 0 && !indexed) {
            const char *paren = strchr(ftype, '(');
            if (paren && atoi(paren + 1) > SCHEMALINT_VARCHAR_LIMIT) {
                append_violation(out, out_sz, offset, table,
                    fname, V_WIDE_VARCHAR, "warning");
            }
        }
        /* TEXT without index */
        if (strncasecmp(ftype, "text", 4) == 0 && !indexed) {
            append_violation(out, out_sz, offset, table,
                fname, V_TEXT_NO_INDEX, "warning");
        }
        col_count++;
    }
    mysql_free_result(res);

    if (!has_pk) append_violation(out, out_sz, offset, table, NULL, V_NO_PK, "error");
    if (STATE.check_timestamps) {
        if (!has_created) append_violation(out, out_sz, offset, table, NULL, V_MISSING_CREATED, "info");
        if (!has_updated) append_violation(out, out_sz, offset, table, NULL, V_MISSING_UPDATED, "info");
    }
    if (snake_count > 0 && camel_count > 0)
        append_violation(out, out_sz, offset, table, NULL, V_NAMING_MIX, "warning");
    if (col_count > STATE.max_columns)
        append_violation(out, out_sz, offset, table, NULL, V_TOO_WIDE, "warning");
}

/* ===== LINT ONE DATABASE ===== */

static int lint_one_db(const char *db, char *out, size_t out_sz) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) { snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed"); return 0; }
    if (!schemalint_ensure_connected(conn)) { mysql_close(conn); return 0; }

    char use_sql[256];
    snprintf(use_sql, sizeof(use_sql), "USE `%s`", db);
    if (mysql_query(conn, use_sql) != 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "USE %s failed: %s", db, mysql_error(conn));
        mysql_close(conn); return 0;
    }
    if (mysql_query(conn, "SHOW TABLES") != 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "SHOW TABLES failed: %s", mysql_error(conn));
        mysql_close(conn); return 0;
    }
    MYSQL_RES *tres = mysql_store_result(conn);
    if (!tres) { snprintf(STATE.last_error, sizeof(STATE.last_error), "no tables result"); mysql_close(conn); return 0; }

    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset, "[@OK]{[@DB]{%s}[@VIOLATIONS]{", db);
    int table_count = 0;
    MYSQL_ROW trow;
    while ((trow = mysql_fetch_row(tres)) != NULL && table_count < SCHEMALINT_MAX_TABLES) {
        const char *tname = trow[0] ? trow[0] : "";
        if (tname[0]) { lint_one_table(conn, db, tname, out, out_sz, &offset); table_count++; }
    }
    mysql_free_result(tres);
    mysql_close(conn);
    offset += snprintf(out + offset, out_sz - offset, "}[@TABLES]{%d}}", table_count);
    STATE.lints_run++;
    strncpy(STATE.last_db, db, sizeof(STATE.last_db) - 1);
    STATE.last_db[sizeof(STATE.last_db) - 1] = '\0';
    return 1;
}

/* ===== UNIT INTERFACE ===== */

int Schemalint_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host, "localhost", sizeof(STATE.host) - 1);
    strncpy(STATE.user, "root", sizeof(STATE.user) - 1);
    STATE.pass[0] = '\0';
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    STATE.max_columns = SCHEMALINT_DEFAULT_MAXC;
    STATE.check_timestamps = 1;
    STATE.initialized = 1;
    return 1;
}

int Schemalint_Run(const char *cmd, const char *bcl_in,
                   char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Schemalint_Init();

    /* READ_STATE */
    if (strcmp(cmd, "read_state") == 0) {
        char body[1024];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@LINTS_RUN]{%d}[@TOTAL_VIOLATIONS]{%d}[@LAST_DB]{%s}"
            "[@MAX_COLUMNS]{%d}[@CHECK_TIMESTAMPS]{%d}[@NO_PK]{%d}[@WIDE_VARCHAR]{%d}"
            "[@TEXT_NO_INDEX]{%d}[@MISSING_CREATED]{%d}[@MISSING_UPDATED]{%d}"
            "[@NAMING_MIX]{%d}[@TOO_WIDE]{%d}",
            STATE.initialized, STATE.lints_run, STATE.total_violations, STATE.last_db,
            STATE.max_columns, STATE.check_timestamps,
            STATE.violations_by_type[V_NO_PK], STATE.violations_by_type[V_WIDE_VARCHAR],
            STATE.violations_by_type[V_TEXT_NO_INDEX], STATE.violations_by_type[V_MISSING_CREATED],
            STATE.violations_by_type[V_MISSING_UPDATED], STATE.violations_by_type[V_NAMING_MIX],
            STATE.violations_by_type[V_TOO_WIDE]);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* SET_CONFIG */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char db_name[SCHEMALINT_MAX_NAME] = {0};
        char maxc[16] = {0};
        char chkts[16] = {0};
        char host[128] = {0}, user[64] = {0}, port[16] = {0}, pass[128] = {0};
        char sock[256] = {0};
        BclParser_Extract(&parse, "DB_NAME", db_name, sizeof(db_name));
        BclParser_Extract(&parse, "MAX_COLUMNS", maxc, sizeof(maxc));
        BclParser_Extract(&parse, "CHECK_TIMESTAMPS", chkts, sizeof(chkts));
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PORT", port, sizeof(port));
        BclParser_Extract(&parse, "PASS", pass, sizeof(pass));
        BclParser_Extract(&parse, "SOCKET", sock, sizeof(sock));
        BclParser_Free(&parse);
        if (db_name[0]) strncpy(STATE.db_name, db_name, sizeof(STATE.db_name) - 1);
        if (maxc[0]) STATE.max_columns = atoi(maxc);
        if (chkts[0]) STATE.check_timestamps = atoi(chkts);
        if (host[0]) strncpy(STATE.host, host, sizeof(STATE.host) - 1);
        if (user[0]) strncpy(STATE.user, user, sizeof(STATE.user) - 1);
        if (port[0]) STATE.port = atoi(port);
        if (pass[0]) strncpy(STATE.pass, pass, sizeof(STATE.pass) - 1);
        if (sock[0]) strncpy(STATE.socket, sock, sizeof(STATE.socket) - 1);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* LINT */
    if (strcmp(cmd, "lint") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char db[SCHEMALINT_MAX_NAME] = {0};
        BclParser_Extract(&parse, "DB", db, sizeof(db));
        BclParser_Free(&parse);
        if (!db[0] && STATE.db_name[0]) strncpy(db, STATE.db_name, sizeof(db) - 1);
        if (!db[0]) return BclResult_Err(bcl_out, out_sz, 20, "no DB in packet");
        if (!lint_one_db(db, bcl_out, out_sz)) return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        strncpy(STATE.last_report, bcl_out, sizeof(STATE.last_report) - 1);
        STATE.last_report[sizeof(STATE.last_report) - 1] = '\0';
        return 1;
    }

    /* LINT_ALL */
    if (strcmp(cmd, "lint_all") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char exclude[512] = {0};
        BclParser_Extract(&parse, "EXCLUDE", exclude, sizeof(exclude));
        BclParser_Free(&parse);
        MYSQL *conn = mysql_init(NULL);
        if (!conn) return BclResult_Err(bcl_out, out_sz, 10, "mysql_init failed");
        if (!schemalint_ensure_connected(conn)) { mysql_close(conn); return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error); }
        if (mysql_query(conn, "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA") != 0) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "schema list failed: %s", mysql_error(conn));
            mysql_close(conn); return BclResult_Err(bcl_out, out_sz, 30, STATE.last_error);
        }
        MYSQL_RES *sres = mysql_store_result(conn);
        if (!sres) { mysql_close(conn); return BclResult_Err(bcl_out, out_sz, 31, "no schemas"); }
        mysql_close(conn);
        const char *default_excl = "mysql,performance_schema,information_schema,sys";
        const char *excl = exclude[0] ? exclude : default_excl;
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{[@DATABASES]{");
        int db_count = 0;
        MYSQL_ROW srow;
        while ((srow = mysql_fetch_row(sres)) != NULL && offset < (int)out_sz - 4096) {
            const char *sname = srow[0] ? srow[0] : "";
            if (!sname[0] || strstr(excl, sname) != NULL) continue;
            char db_result[8192];
            if (lint_one_db(sname, db_result, sizeof(db_result))) {
                offset += snprintf(bcl_out + offset, out_sz - offset, "[@DB_RESULT]{%s}", db_result);
                db_count++;
            }
        }
        mysql_free_result(sres);
        offset += snprintf(bcl_out + offset, out_sz - offset, "}[@DB_COUNT]{%d}}", db_count);
        return 1;
    }

    /* REPORT */
    if (strcmp(cmd, "report") == 0) {
        if (!STATE.last_report[0]) return BclResult_Err(bcl_out, out_sz, 40, "no lint run yet - run lint first");
        char body[2048];
        snprintf(body, sizeof(body),
            "[@LINTS_RUN]{%d}[@TOTAL_VIOLATIONS]{%d}[@LAST_DB]{%s}[@BREAKDOWN]{"
            "[@NO_PK]{%d}[@WIDE_VARCHAR]{%d}[@TEXT_NO_INDEX]{%d}[@MISSING_CREATED]{%d}"
            "[@MISSING_UPDATED]{%d}[@NAMING_MIX]{%d}[@TOO_WIDE]{%d}}",
            STATE.lints_run, STATE.total_violations, STATE.last_db,
            STATE.violations_by_type[V_NO_PK], STATE.violations_by_type[V_WIDE_VARCHAR],
            STATE.violations_by_type[V_TEXT_NO_INDEX], STATE.violations_by_type[V_MISSING_CREATED],
            STATE.violations_by_type[V_MISSING_UPDATED], STATE.violations_by_type[V_NAMING_MIX],
            STATE.violations_by_type[V_TOO_WIDE]);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int Schemalint_Close(void) {
    STATE.initialized = 0;
    STATE.lints_run = 0;
    STATE.total_violations = 0;
    STATE.last_db[0] = '\0';
    STATE.last_report[0] = '\0';
    memset(STATE.violations_by_type, 0, sizeof(STATE.violations_by_type));
    return 1;
}

const char * Schemalint_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Schemalint: initialized=%d lints=%d violations=%d last_db=%s",
        STATE.initialized, STATE.lints_run, STATE.total_violations,
        STATE.last_db);
    return buf;
}
