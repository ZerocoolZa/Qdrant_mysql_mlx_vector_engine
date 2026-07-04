//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_vbcheck.c" date="2026-07-04" author="Devin" session_id="bcl-vbcheck-impl" context="BCL unit - VBStyle compliance checker. Reads Python files via fopen/fread and queries MySQL vb_code_test.vb_classes for violations. Commands: check, check_dir, check_mysql, summary, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_vbcheck.c" domain="cascade_tools" authority="Vbcheck"}
//[@SUMMARY]{summary="VBStyle compliance checker. Scans Python files for GHOST/VBSTYLE headers, print(), decorators, self._, Run(), Tuple3 returns, PascalCase. Queries MySQL vb_classes for violations. Commands: check, check_dir, check_mysql, summary, read_state, set_config."}
//[@CLASS]{class="Vbcheck" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="CheckFile" type="internal"}
//[@METHOD]{method="CheckCode" type="internal"}
//[@METHOD]{method="EnsureConnected" type="internal"}
//[@METHOD]{method="ReadFile" type="internal"}
/*
 * bcl_vbcheck.c — VBStyle compliance checker BCL unit
 * BCL IN:  check [@PATH], check_dir [@PATH][@MAX], check_mysql [@DB],
 *          summary, read_state, set_config [@STRICT][@MAX]
 * BCL OUT: [@OK]{[@CHECK]{[@NAME]{..}[@STATUS]{pass|fail}}...}
 */
#include "bcl_toolstack.h"
#include <mysql.h>
#include <dirent.h>
/* ===== DIM BLOCK ===== */
#define VBCHECK_MAX_FILE    262144
#define VBCHECK_MAX_PATH    4096
#define VBCHECK_MAX_DB      64
#define VBCHECK_HOST_LEN    256
#define VBCHECK_USER_LEN    64
#define VBCHECK_PASS_LEN    128
#define VBCHECK_SOCKET_LEN  256
#define VBCHECK_CHECK_COUNT 9
#define VBCHECK_MAX_CLASSES 512

typedef struct { int pass; int fail; } CheckTally;

static struct {
    int  initialized;
    int  total_checked;
    int  total_pass;
    int  total_fail;
    char last_path[VBCHECK_MAX_PATH];
    int  checks_run;
    int  strict_mode;
    int  max_files;
    CheckTally tally[VBCHECK_CHECK_COUNT];
    int  connected;  /* MySQL */
    MYSQL *conn;
    char host[VBCHECK_HOST_LEN];
    char user[VBCHECK_USER_LEN];
    char pass[VBCHECK_PASS_LEN];
    char socket[VBCHECK_SOCKET_LEN];
    int  port;
    char last_error[256];
} STATE;

/* Check names in fixed order — index matches tally[] */
static const char *CHECK_NAMES[VBCHECK_CHECK_COUNT] = {
    "ghost_header", "vbstyle_header", "no_print", "no_decorators",
    "no_self_underscore", "has_run", "has_init_mem_db_param",
    "returns_tuple3", "pascalcase_class"
};
/* ===== READ FILE — fopen/fread into buffer ===== */

static long vb_read_file(const char *path, char *buf, size_t buf_sz) {
    FILE *fp = fopen(path, "rb");
    if (!fp) return -1;
    size_t total = 0;
    size_t n;
    while (total + 4096 < buf_sz &&
           (n = fread(buf + total, 1, 4096, fp)) > 0) {
        total += n;
    }
    fclose(fp);
    buf[total] = '\0';
    return (long)total;
}
/* ===== STRING SEARCH HELPERS ===== */
static int vb_contains(const char *hay, const char *needle) {
    return strstr(hay, needle) != NULL ? 1 : 0;
}
/* Detect "print(" outside strings and comments. */
static int vb_has_print_violation(const char *code) {
    int in_squote = 0, in_dquote = 0;
    int line_start = 1;
    const char *p = code;
    while (*p) {
        char c = *p;
        if (c == '\n') {
            in_squote = 0; in_dquote = 0; line_start = 1; p++; continue;
        }
        if (line_start) {
            /* skip leading whitespace */
            if (c == ' ' || c == '\t') { p++; continue; }
            line_start = 0;
        }
        if (in_dquote) {
            if (c == '\\' && p[1]) { p += 2; continue; }
            if (c == '"') in_dquote = 0;
            p++; continue;
        }
        if (in_squote) {
            if (c == '\\' && p[1]) { p += 2; continue; }
            if (c == '\'') in_squote = 0;
            p++; continue;
        }
        if (c == '#') {
            while (*p && *p != '\n') p++;
            continue;
        }
        if (c == '"') { in_dquote = 1; p++; continue; }
        if (c == '\'') { in_squote = 1; p++; continue; }
        if (strncmp(p, "print(", 6) == 0) return 1;
        p++;
    }
    return 0;
}
/* Detect @property, @staticmethod, @classmethod decorators. */
static int vb_has_decorator_violation(const char *code) {
    const char *p = code;
    while ((p = strstr(p, "@")) != NULL) {
        if (strncmp(p, "@property", 9) == 0) return 1;
        if (strncmp(p, "@staticmethod", 13) == 0) return 1;
        if (strncmp(p, "@classmethod", 12) == 0) return 1;
        p++;
    }
    return 0;
}
/* Detect self._ private attribute access. */
static int vb_has_self_underscore(const char *code) {
    return vb_contains(code, "self._") ? 1 : 0;
}
/* Check first class definition is PascalCase. */
static int vb_pascalcase_ok(const char *code) {
    const char *p = strstr(code, "class ");
    if (!p) return 0;
    if (p != code && p[-1] != '\n') return 0;  /* must be at line start */
    p += 6;
    char name[128];
    size_t i = 0;
    while (*p && *p != '(' && *p != ':' && *p != ' ' && i < 127) {
        name[i++] = *p++;
    }
    name[i] = '\0';
    if (i == 0) return 0;
    if (!isupper((unsigned char)name[0])) return 0;
    for (size_t k = 0; k < i; k++) {
        if (name[k] == '_') return 0;
    }
    return 1;
}
/* ===== CHECK CODE — run all 9 checks, append BCL. Returns pass count. */
static int vb_check_code(const char *code, char *out, size_t out_sz, int *offset) {
    int results[VBCHECK_CHECK_COUNT];
    results[0] = vb_contains(code, "[@GHOST]") ? 1 : 0;
    results[1] = vb_contains(code, "[@VBSTYLE]") ? 1 : 0;
    results[2] = vb_has_print_violation(code) ? 0 : 1;
    results[3] = vb_has_decorator_violation(code) ? 0 : 1;
    results[4] = vb_has_self_underscore(code) ? 0 : 1;
    results[5] = vb_contains(code, "def Run(") ? 1 : 0;
    results[6] = vb_contains(code, "def __init__(self, mem=None, db=None, param=None") ? 1 : 0;
    results[7] = (vb_contains(code, "return (1,") ||
                  vb_contains(code, "return (0, None,")) ? 1 : 0;
    results[8] = vb_pascalcase_ok(code);

    int pass_count = 0;
    for (int i = 0; i < VBCHECK_CHECK_COUNT; i++) {
        const char *status = results[i] ? "pass" : "fail";
        if (results[i]) { pass_count++; STATE.tally[i].pass++; }
        else { STATE.tally[i].fail++; }
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@CHECK]{[@NAME]{%s}[@STATUS]{%s}}", CHECK_NAMES[i], status);
    }
    return pass_count;
}
/* ===== CHECK FILE — read + check one .py file ===== */
static int vb_check_file(const char *path, char *out, size_t out_sz, int *offset) {
    static char file_buf[VBCHECK_MAX_FILE];
    long len = vb_read_file(path, file_buf, sizeof(file_buf));
    if (len < 0) {
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@FILE]{[@PATH]{%s}[@ERROR]{cannot_read}}", path);
        return 0;
    }
    STATE.total_checked++;
    STATE.checks_run += VBCHECK_CHECK_COUNT;
    strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
    STATE.last_path[sizeof(STATE.last_path) - 1] = '\0';

    *offset += snprintf(out + *offset, out_sz - *offset,
        "[@FILE]{[@PATH]{%s}", path);
    int pass_count = vb_check_code(file_buf, out, out_sz, offset);
    int fail_count = VBCHECK_CHECK_COUNT - pass_count;
    STATE.total_pass += pass_count;
    STATE.total_fail += fail_count;
    *offset += snprintf(out + *offset, out_sz - *offset,
        "[@PASS]{%d}[@FAIL]{%d}}", pass_count, fail_count);
    return pass_count;
}
/* ===== MYSQL — ensure connection ===== */
static int vb_ensure_connected(void) {
    if (STATE.connected && STATE.conn) return 1;
    if (!STATE.conn) {
        STATE.conn = mysql_init(NULL);
        if (!STATE.conn) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed");
            return 0;
        }
    }
    const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
    MYSQL *result = mysql_real_connect(STATE.conn,
        STATE.host, STATE.user,
        STATE.pass[0] ? STATE.pass : NULL,
        NULL, STATE.port, sock, 0);
    if (!result) {
        result = mysql_real_connect(STATE.conn,
            STATE.host, STATE.user,
            STATE.pass[0] ? STATE.pass : NULL,
            NULL, STATE.port, NULL, 0);
    }
    if (!result) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "connect: %s", mysql_error(STATE.conn));
        return 0;
    }
    STATE.connected = 1;
    return 1;
}
/* ===== CHECK MYSQL — query vb_classes for violations ===== */
static int vb_check_mysql(const char *db, char *bcl_out, size_t out_sz) {
    if (!vb_ensure_connected()) {
        return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
    }
    char query[512];
    snprintf(query, sizeof(query),
        "SELECT id, class_name, class_code FROM `%s`.`vb_classes` ORDER BY id LIMIT %d",
        db, VBCHECK_MAX_CLASSES);
    if (mysql_query(STATE.conn, query) != 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "query: %s", mysql_error(STATE.conn));
        return BclResult_Err(bcl_out, out_sz, 11, STATE.last_error);
    }
    MYSQL_RES *res = mysql_store_result(STATE.conn);
    if (!res) {
        return BclResult_Err(bcl_out, out_sz, 12, "no result set");
    }

    int offset = snprintf(bcl_out, out_sz,
        "[@OK]{[@DB]{%s}[@TOTAL]{0}", db);
    int total = 0;
    int total_pass = 0;
    int total_fail = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 1024) {
        const char *id = row[0] ? row[0] : "0";
        const char *cname = row[1] ? row[1] : "";
        const char *code = row[2] ? row[2] : "";

        int has_ghost = vb_contains(code, "[@GHOST]") ? 1 : 0;
        int has_vbstyle = vb_contains(code, "[@VBSTYLE]") ? 1 : 0;
        int has_decorator = vb_has_decorator_violation(code) ? 1 : 0;
        int has_print = vb_has_print_violation(code) ? 1 : 0;
        int has_run = vb_contains(code, "def Run(") ? 1 : 0;
        int has_tuple3 = (vb_contains(code, "return (1,") ||
                          vb_contains(code, "return (0, None,")) ? 1 : 0;

        STATE.total_checked++;
        STATE.checks_run += 6;
        int pass_count = has_ghost + has_vbstyle + has_run + has_tuple3
                       + (has_decorator ? 0 : 1) + (has_print ? 0 : 1);
        STATE.total_pass += pass_count;
        STATE.total_fail += 6 - pass_count;
        if (pass_count == 6) total_pass++; else total_fail++;

        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@CLASS]{[@ID]{%s}[@NAME]{%s}[@HAS_GHOST]{%d}[@HAS_VBSTYLE]{%d}"
            "[@HAS_DECORATOR]{%d}[@HAS_PRINT]{%d}[@HAS_RUN]{%d}[@HAS_TUPLE3]{%d}"
            "[@PASS]{%d}[@FAIL]{%d}}",
            id, cname, has_ghost, has_vbstyle, has_decorator,
            has_print, has_run, has_tuple3, pass_count, 6 - pass_count);
        total++;
    }
    mysql_free_result(res);
    offset += snprintf(bcl_out + offset, out_sz - offset,
        "[@TOTAL]{%d}[@TOTAL_PASS]{%d}[@TOTAL_FAIL]{%d}}",
        total, total_pass, total_fail);
    /* patch the leading TOTAL placeholder */
    char total_patch[32];
    snprintf(total_patch, sizeof(total_patch), "[@TOTAL]{%d}", total);
    char *ph = strstr(bcl_out, "[@TOTAL]{0}");
    if (ph) memcpy(ph, total_patch, strlen(total_patch));
    return 1;
}

/* ===== UNIT INTERFACE ===== */
int Vbcheck_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.host, "localhost", sizeof(STATE.host) - 1);
    strncpy(STATE.user, "root", sizeof(STATE.user) - 1);
    STATE.pass[0] = '\0';
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    STATE.strict_mode = 0;
    STATE.max_files = 50;
    STATE.initialized = 1;
    return 1;
}

int Vbcheck_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Vbcheck_Init();

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{1}[@TOTAL_CHECKED]{%d}[@TOTAL_PASS]{%d}"
            "[@TOTAL_FAIL]{%d}[@CHECKS_RUN]{%d}[@STRICT]{%d}[@MAX_FILES]{%d}"
            "[@LAST_PATH]{%s}[@CONNECTED]{%d}",
            STATE.total_checked, STATE.total_pass, STATE.total_fail,
            STATE.checks_run, STATE.strict_mode, STATE.max_files,
            STATE.last_path, STATE.connected);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char strict[16] = {0}, maxf[16] = {0};
        char host[128] = {0}, user[64] = {0}, port[16] = {0};
        BclParser_Extract(&parse, "STRICT", strict, sizeof(strict));
        BclParser_Extract(&parse, "MAX", maxf, sizeof(maxf));
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PORT", port, sizeof(port));
        BclParser_Free(&parse);
        if (strict[0]) STATE.strict_mode = atoi(strict);
        if (maxf[0]) STATE.max_files = atoi(maxf);
        if (host[0]) { strncpy(STATE.host, host, sizeof(STATE.host) - 1); STATE.connected = 0; }
        if (user[0]) { strncpy(STATE.user, user, sizeof(STATE.user) - 1); STATE.connected = 0; }
        if (port[0]) { STATE.port = atoi(port); STATE.connected = 0; }
        return BclResult_Ok(bcl_out, out_sz,
            "[@STATUS]{config_set}[@STRICT]{set}[@MAX]{set}");
    }

    /* ===== CHECK ===== */
    if (strcmp(cmd, "check") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[VBCHECK_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        int offset = snprintf(bcl_out, out_sz, "[@OK]{");
        int pass_count = vb_check_file(path, bcl_out, out_sz, &offset);
        int fail_count = VBCHECK_CHECK_COUNT - pass_count;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@TOTAL]{%d}[@PASS]{%d}[@FAIL]{%d}}",
            VBCHECK_CHECK_COUNT, pass_count, fail_count);
        return 1;
    }

    /* ===== CHECK_DIR ===== */
    if (strcmp(cmd, "check_dir") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[VBCHECK_MAX_PATH] = {0};
        char max_str[16] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "MAX", max_str, sizeof(max_str));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        int max_files = max_str[0] ? atoi(max_str) : STATE.max_files;
        DIR *dir = opendir(path);
        if (!dir) {
            return BclResult_Err(bcl_out, out_sz, 21, "cannot open directory");
        }
        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@DIR]{%s}[@MAX]{%d}", path, max_files);
        int checked = 0;
        struct dirent *ent;
        while ((ent = readdir(dir)) != NULL && checked < max_files &&
               offset < (int)out_sz - 2048) {
            const char *nm = ent->d_name;
            size_t nl = strlen(nm);
            if (nl < 3 || strcmp(nm + nl - 3, ".py") != 0) continue;
            char full[VBCHECK_MAX_PATH];
            snprintf(full, sizeof(full), "%s/%s", path, nm);
            vb_check_file(full, bcl_out, out_sz, &offset);
            checked++;
        }
        closedir(dir);
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@FILES_CHECKED]{%d}[@TOTAL_PASS]{%d}[@TOTAL_FAIL]{%d}}",
            checked, STATE.total_pass, STATE.total_fail);
        return 1;
    }

    /* ===== CHECK_MYSQL ===== */
    if (strcmp(cmd, "check_mysql") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char db[VBCHECK_MAX_DB] = {0};
        BclParser_Extract(&parse, "DB", db, sizeof(db));
        BclParser_Free(&parse);
        if (!db[0]) strncpy(db, "vb_code_test", sizeof(db) - 1);
        return vb_check_mysql(db, bcl_out, out_sz);
    }

    /* ===== SUMMARY ===== */
    if (strcmp(cmd, "summary") == 0) {
        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@TOTAL_FILES]{%d}[@PASSES]{%d}[@FAILS]{%d}[@CHECKS_RUN]{%d}"
            "[@BY_CHECK]{",
            STATE.total_checked, STATE.total_pass, STATE.total_fail,
            STATE.checks_run);
        for (int i = 0; i < VBCHECK_CHECK_COUNT; i++) {
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@CHECK]{[@NAME]{%s}[@PASS]{%d}[@FAIL]{%d}}",
                CHECK_NAMES[i], STATE.tally[i].pass, STATE.tally[i].fail);
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}}");
        return 1;
    }

    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int Vbcheck_Close(void) {
    if (STATE.conn) { mysql_close(STATE.conn); STATE.conn = NULL; }
    STATE.connected = 0;
    STATE.initialized = 0;
    return 1;
}

const char * Vbcheck_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Vbcheck: initialized=%d checked=%d pass=%d fail=%d checks=%d connected=%d",
        STATE.initialized, STATE.total_checked, STATE.total_pass,
        STATE.total_fail, STATE.checks_run, STATE.connected);
    return buf;
}
