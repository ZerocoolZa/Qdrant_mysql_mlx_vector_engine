//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_rule_engine.c" date="2026-07-04" author="devin" session_id="bcl-vsstyle-units" context="BCL unit for running VBStyle rules against code files. Source: core/Dom_Vsstyle/vbs_rule_engine.py. Commands: check, check_dir, evaluate, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_rule_engine.c" domain="bcl_units" authority="RuleEngine"}
//[@SUMMARY]{summary="VBStyle rule engine. Runs rules against .py files and produces violation reports. Commands: check, check_dir, evaluate, read_state, set_config."}
//[@CLASS]{class="RuleEngine" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="CheckFile" type="command"}
//[@METHOD]{method="CheckDir" type="command"}
//[@METHOD]{method="Evaluate" type="query"}
/*
 * bcl_rule_engine.c — VBStyle rule engine BCL unit
 * BCL IN:  check [@PATH], check_dir [@PATH][@MAX], evaluate [@CODE],
 *          read_state, set_config [@STRICT][@MAX],
 *          report [@PATH], check_rules [@PATH]
 * BCL OUT: [@OK]{[@FILE]{path}[@VIOLATIONS]{N}[@VIOLATION]{...}...[@STATUS]{COMPLIANT|VIOLATIONS}}
 */
#include "bcl_toolstack.h"
#include <dirent.h>
#include <sys/stat.h>
#include <mysql.h>

/* ===== DIM BLOCK ===== */
#define RE_MAX_PATH        4096
#define RE_MAX_FILE        262144
#define RE_MAX_VIOLATIONS  256
#define RE_MAX_BODY        32768
#define RE_MAX_LINE        1024
#define RE_MAX_FILES       500
#define RE_MAX_RULENAME    32
#define RE_MAX_DETAILS     256
#define RE_RULE_COUNT      9

typedef struct {
    char rule[RE_MAX_RULENAME];
    int  line;
    char details[RE_MAX_DETAILS];
} RuleViolation;

static const char *RE_RULE_NAMES[RE_RULE_COUNT] = {
    "NoPrint", "NoDecorators", "NoSelfUnderscore",
    "GhostHeader", "VBStyleHeader", "RunDispatch",
    "PascalCase", "NoTabs", "NoTrailingWS"
};

static struct {
    int           initialized;
    int           total_checked;
    int           total_compliant;
    int           total_violations;
    int           strict_mode;
    int           max_files;
    char          last_path[RE_MAX_PATH];
    int           tally[RE_RULE_COUNT];
    int           rules_loaded;
    int           report_files;
    int           report_compliant;
    int           report_violating;
} STATE;

static MYSQL *s_mysql = NULL;

/* ===== MYSQL CONNECTION HELPER ===== */
static void EnsureConnected(void) {
    if (s_mysql) return;
    s_mysql = mysql_init(NULL);
    if (!s_mysql) return;
    if (!mysql_real_connect(s_mysql, "localhost", "root", NULL,
                            "vb_shared", 0, "/tmp/mysql.sock", 0)) {
        mysql_close(s_mysql);
        s_mysql = NULL;
        return;
    }
}

/* ===== READ FILE — fopen/fread into buffer ===== */
static long re_read_file(const char *path, char *buf, size_t buf_sz) {
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

/* ===== LINE ITERATOR — yield one line at a time with line number ===== */
typedef struct {
    const char *cursor;
    int         line_no;
    char        line[RE_MAX_LINE];
} ReLineIter;

static void re_iter_init(ReLineIter *it, const char *src) {
    it->cursor = src;
    it->line_no = 0;
    it->line[0] = '\0';
}

/* Returns 1 if a line was produced, 0 at end. Strips trailing \n. */
static int re_iter_next(ReLineIter *it) {
    if (!it->cursor || *it->cursor == '\0') return 0;
    it->line_no++;
    size_t i = 0;
    const char *p = it->cursor;
    while (*p && *p != '\n' && i < RE_MAX_LINE - 1) {
        it->line[i++] = *p++;
    }
    it->line[i] = '\0';
    if (*p == '\n') p++;
    it->cursor = p;
    return 1;
}

/* ===== CHECK HELPERS — per-line detectors ===== */

/* Detect print( at start of stripped line (ignoring comments). */
static int re_line_has_print(const char *line) {
    const char *p = line;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '#') return 0;
    return strncmp(p, "print(", 6) == 0 ? 1 : 0;
}

/* Detect @property / @staticmethod / @classmethod decorators. */
static int re_line_has_decorator(const char *line, char *which, size_t which_sz) {
    const char *p = line;
    while (*p == ' ' || *p == '\t') p++;
    if (strncmp(p, "@property", 9) == 0) {
        snprintf(which, which_sz, "@property");
        return 1;
    }
    if (strncmp(p, "@staticmethod", 13) == 0) {
        snprintf(which, which_sz, "@staticmethod");
        return 1;
    }
    if (strncmp(p, "@classmethod", 12) == 0) {
        snprintf(which, which_sz, "@classmethod");
        return 1;
    }
    return 0;
}

/* Detect self._ attribute access. */
static int re_line_has_self_underscore(const char *line) {
    return strstr(line, "self._") != NULL ? 1 : 0;
}

/* Detect tab character. */
static int re_line_has_tab(const char *line) {
    return strchr(line, '\t') != NULL ? 1 : 0;
}

/* Detect trailing whitespace (spaces/tabs before \n). */
static int re_line_has_trailing_ws(const char *line) {
    size_t n = strlen(line);
    if (n == 0) return 0;
    char last = line[n - 1];
    return (last == ' ' || last == '\t' || last == '\r') ? 1 : 0;
}

/* Detect class definition; return 1 and fill name if found. */
static int re_line_class_name(const char *line, char *name, size_t name_sz) {
    const char *p = line;
    while (*p == ' ' || *p == '\t') p++;
    if (strncmp(p, "class ", 6) != 0) return 0;
    p += 6;
    size_t i = 0;
    while (*p && *p != '(' && *p != ':' && *p != ' ' && i < name_sz - 1) {
        name[i++] = *p++;
    }
    name[i] = '\0';
    return (i > 0) ? 1 : 0;
}

/* Detect indented def Run( method. */
static int re_line_has_run(const char *line) {
    const char *p = line;
    if (*p != ' ' && *p != '\t') return 0;
    while (*p == ' ' || *p == '\t') p++;
    if (strncmp(p, "def Run(", 8) == 0) return 1;
    return 0;
}

/* Check PascalCase: first char upper, no underscores. */
static int re_is_pascalcase(const char *name) {
    if (!name[0]) return 0;
    if (!isupper((unsigned char)name[0])) return 0;
    for (const char *p = name; *p; p++) {
        if (*p == '_') return 0;
    }
    return 1;
}

/* ===== CHECK CODE — scan lines, fill violations array =====
 * Returns violation count (capped at RE_MAX_VIOLATIONS).
 * run_mask[idx]==1 means run that check; tally is incremented per match. */
static int re_check_code_masked(const char *code, RuleViolation *vios, int max_v,
                                int *tally, const int *run_mask) {
    int count = 0;
    int has_ghost = 0;
    int has_vbstyle = 0;
    int has_run = 0;
    int has_class = 0;
    char class_name[128] = {0};

    ReLineIter it;
    re_iter_init(&it, code);
    while (re_iter_next(&it) && count < max_v) {
        const char *line = it.line;
        int lineno = it.line_no;

        if (strstr(line, "[@GHOST]")) has_ghost = 1;
        if (strstr(line, "[@VBSTYLE]")) has_vbstyle = 1;
        if (re_line_has_run(line)) has_run = 1;

        char cname[128];
        if (re_line_class_name(line, cname, sizeof(cname))) {
            has_class = 1;
            strncpy(class_name, cname, sizeof(class_name) - 1);
            class_name[sizeof(class_name) - 1] = '\0';
        }

        if (run_mask[0] && re_line_has_print(line)) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoPrint");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "print() found");
            count++; tally[0]++;
            if (count >= max_v) break;
        }

        char which[32];
        if (run_mask[1] && re_line_has_decorator(line, which, sizeof(which))) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoDecorators");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "%s found", which);
            count++; tally[1]++;
            if (count >= max_v) break;
        }

        if (run_mask[2] && re_line_has_self_underscore(line)) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoSelfUnderscore");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "self._ found");
            count++; tally[2]++;
            if (count >= max_v) break;
        }

        if (run_mask[7] && re_line_has_tab(line)) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoTabs");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "tab character found");
            count++; tally[7]++;
            if (count >= max_v) break;
        }

        if (run_mask[8] && re_line_has_trailing_ws(line)) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoTrailingWS");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "trailing whitespace");
            count++; tally[8]++;
            if (count >= max_v) break;
        }
    }

    /* File-level checks (line 0). */
    if (run_mask[3] && !has_ghost && count < max_v) {
        snprintf(vios[count].rule, sizeof(vios[count].rule), "GhostHeader");
        vios[count].line = 0;
        snprintf(vios[count].details, sizeof(vios[count].details),
            "missing [@GHOST] header");
        count++; tally[3]++;
    }
    if (run_mask[4] && !has_vbstyle && count < max_v) {
        snprintf(vios[count].rule, sizeof(vios[count].rule), "VBStyleHeader");
        vios[count].line = 0;
        snprintf(vios[count].details, sizeof(vios[count].details),
            "missing [@VBSTYLE] header");
        count++; tally[4]++;
    }
    if (run_mask[5] && !has_run && count < max_v) {
        snprintf(vios[count].rule, sizeof(vios[count].rule), "RunDispatch");
        vios[count].line = 0;
        snprintf(vios[count].details, sizeof(vios[count].details),
            "missing Run() method");
        count++; tally[5]++;
    }
    if (run_mask[6] && has_class && class_name[0] && !re_is_pascalcase(class_name) && count < max_v) {
        snprintf(vios[count].rule, sizeof(vios[count].rule), "PascalCase");
        vios[count].line = 0;
        snprintf(vios[count].details, sizeof(vios[count].details),
            "class %s not PascalCase", class_name);
        count++; tally[6]++;
    }

    return count;
}

/* All checks enabled, tally into STATE.tally (legacy behaviour). */
static int re_check_code(const char *code, RuleViolation *vios, int max_v) {
    int mask[RE_RULE_COUNT];
    for (int i = 0; i < RE_RULE_COUNT; i++) mask[i] = 1;
    return re_check_code_masked(code, vios, max_v, STATE.tally, mask);
}

/* All checks enabled, tally into caller-provided array. */
static int re_check_code_into(const char *code, RuleViolation *vios, int max_v,
                              int *tally) {
    int mask[RE_RULE_COUNT];
    for (int i = 0; i < RE_RULE_COUNT; i++) mask[i] = 1;
    return re_check_code_masked(code, vios, max_v, tally, mask);
}

/* ===== EMIT VIOLATIONS — append BCL violation packets ===== */
static void re_emit_violations(char *out, size_t out_sz, int *offset,
                               const RuleViolation *vios, int count) {
    for (int i = 0; i < count; i++) {
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@VIOLATION]{[@RULE]{%s}[@LINE]{%d}[@DETAILS]{%s}}",
            vios[i].rule, vios[i].line, vios[i].details);
    }
}

/* ===== CHECK FILE — read + check one .py file, emit BCL ===== */
static int re_check_file(const char *path, char *out, size_t out_sz, int *offset) {
    static char file_buf[RE_MAX_FILE];
    long len = re_read_file(path, file_buf, sizeof(file_buf));
    if (len < 0) {
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@FILE]{[@PATH]{%s}[@ERROR]{cannot_read}[@VIOLATIONS]{0}[@STATUS]{ERROR}}",
            path);
        return 0;
    }

    STATE.total_checked++;
    strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
    STATE.last_path[sizeof(STATE.last_path) - 1] = '\0';

    RuleViolation vios[RE_MAX_VIOLATIONS];
    memset(vios, 0, sizeof(vios));
    int count = re_check_code(file_buf, vios, RE_MAX_VIOLATIONS);
    STATE.total_violations += count;

    const char *status = (count == 0) ? "COMPLIANT" : "VIOLATIONS";
    if (count == 0) STATE.total_compliant++;

    *offset += snprintf(out + *offset, out_sz - *offset,
        "[@FILE]{[@PATH]{%s}[@VIOLATIONS]{%d}", path, count);
    re_emit_violations(out, out_sz, offset, vios, count);
    *offset += snprintf(out + *offset, out_sz - *offset,
        "[@STATUS]{%s}}", status);
    return count;
}

/* ===== EVALUATE — check code string directly, emit BCL ===== */
static int re_evaluate(const char *code, char *out, size_t out_sz) {
    RuleViolation vios[RE_MAX_VIOLATIONS];
    memset(vios, 0, sizeof(vios));
    int count = re_check_code(code, vios, RE_MAX_VIOLATIONS);
    STATE.total_violations += count;
    STATE.total_checked++;
    if (count == 0) STATE.total_compliant++;

    const char *status = (count == 0) ? "COMPLIANT" : "VIOLATIONS";
    int offset = snprintf(out, out_sz,
        "[@OK]{[@EVAL]{[@VIOLATIONS]{%d}", count);
    re_emit_violations(out, out_sz, &offset, vios, count);
    offset += snprintf(out + offset, out_sz - offset,
        "[@STATUS]{%s}}}", status);
    return 1;
}

/* ===== CHECK_DIR — walk directory, skip junk dirs ===== */
static int re_skip_dir(const char *nm) {
    if (strcmp(nm, ".git") == 0) return 1;
    if (strcmp(nm, "__pycache__") == 0) return 1;
    if (strcmp(nm, "node_modules") == 0) return 1;
    if (strcmp(nm, ".venv") == 0) return 1;
    if (strcmp(nm, "venv") == 0) return 1;
    if (strcmp(nm, ".codex") == 0) return 1;
    return 0;
}

static int re_is_py(const char *nm) {
    size_t nl = strlen(nm);
    if (nl < 3) return 0;
    return strcmp(nm + nl - 3, ".py") == 0 ? 1 : 0;
}

/* Recursive walk with depth guard. Returns files checked. */
static int re_walk_dir(const char *path, char *out, size_t out_sz,
                       int *offset, int max_files, int *checked, int depth) {
    if (depth > 8 || *checked >= max_files) return 0;
    DIR *dir = opendir(path);
    if (!dir) return 0;
    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL && *checked < max_files &&
           *offset < (int)out_sz - 2048) {
        const char *nm = ent->d_name;
        if (strcmp(nm, ".") == 0 || strcmp(nm, "..") == 0) continue;
        char full[RE_MAX_PATH];
        snprintf(full, sizeof(full), "%s/%s", path, nm);
        struct stat st;
        if (stat(full, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) {
            if (re_skip_dir(nm)) continue;
            re_walk_dir(full, out, out_sz, offset, max_files, checked, depth + 1);
            continue;
        }
        if (!S_ISREG(st.st_mode)) continue;
        if (!re_is_py(nm)) continue;
        re_check_file(full, out, out_sz, offset);
        (*checked)++;
    }
    closedir(dir);
    return *checked;
}

/* ===== REPORT WALK — recursive walk aggregating compliance stats ===== */
static int re_report_walk(const char *path, int max_files, int *checked,
                          int *compliant, int *violating, int *total_vios,
                          int *by_rule, int depth) {
    if (depth > 8 || *checked >= max_files) return 0;
    DIR *dir = opendir(path);
    if (!dir) return 0;
    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL && *checked < max_files) {
        const char *nm = ent->d_name;
        if (strcmp(nm, ".") == 0 || strcmp(nm, "..") == 0) continue;
        char full[RE_MAX_PATH];
        snprintf(full, sizeof(full), "%s/%s", path, nm);
        struct stat st;
        if (stat(full, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) {
            if (re_skip_dir(nm)) continue;
            re_report_walk(full, max_files, checked, compliant, violating,
                           total_vios, by_rule, depth + 1);
            continue;
        }
        if (!S_ISREG(st.st_mode)) continue;
        if (!re_is_py(nm)) continue;
        static char file_buf[RE_MAX_FILE];
        long len = re_read_file(full, file_buf, sizeof(file_buf));
        (*checked)++;
        if (len < 0) {
            (*violating)++;
            continue;
        }
        RuleViolation vios[RE_MAX_VIOLATIONS];
        memset(vios, 0, sizeof(vios));
        int count = re_check_code_into(file_buf, vios, RE_MAX_VIOLATIONS, by_rule);
        *total_vios += count;
        if (count == 0) (*compliant)++;
        else (*violating)++;
    }
    closedir(dir);
    return *checked;
}

/* ===== RULE KEYWORD MATCHER — map a rule name to a built-in check index =====
 * Returns check index 0..8, or -1 if no keyword matches (case-insensitive). */
static int re_match_rule_keyword(const char *rule) {
    char low[RE_MAX_DETAILS];
    size_t n = 0;
    for (; rule[n] && n < sizeof(low) - 1; n++)
        low[n] = (char)tolower((unsigned char)rule[n]);
    low[n] = '\0';
    if (strstr(low, "print"))      return 0; /* NoPrint */
    if (strstr(low, "decorator"))  return 1; /* NoDecorators */
    if (strstr(low, "self._"))     return 2; /* NoSelfUnderscore */
    if (strstr(low, "ghost"))      return 3; /* GhostHeader */
    if (strstr(low, "vbstyle"))    return 4; /* VBStyleHeader */
    if (strstr(low, "run"))        return 5; /* RunDispatch */
    if (strstr(low, "pascalcase")) return 6; /* PascalCase */
    if (strstr(low, "tab"))        return 7; /* NoTabs */
    if (strstr(low, "whitespace")) return 8; /* NoTrailingWS */
    return -1;
}

/* ===== UNIT INTERFACE ===== */
int RuleEngine_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.strict_mode = 0;
    STATE.max_files = RE_MAX_FILES;
    STATE.initialized = 1;
    return 1;
}

int RuleEngine_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) RuleEngine_Init();

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@INITIALIZED]{1}[@TOTAL_CHECKED]{%d}[@TOTAL_COMPLIANT]{%d}"
            "[@TOTAL_VIOLATIONS]{%d}[@STRICT]{%d}[@MAX_FILES]{%d}"
            "[@LAST_PATH]{%s}[@BY_RULE]{",
            STATE.total_checked, STATE.total_compliant,
            STATE.total_violations, STATE.strict_mode, STATE.max_files,
            STATE.last_path);
        for (int i = 0; i < RE_RULE_COUNT; i++) {
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@RULE]{[@NAME]{%s}[@COUNT]{%d}}",
                RE_RULE_NAMES[i], STATE.tally[i]);
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}}");
        return 1;
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char strict[16] = {0}, maxf[16] = {0};
        BclParser_Extract(&parse, "STRICT", strict, sizeof(strict));
        BclParser_Extract(&parse, "MAX", maxf, sizeof(maxf));
        BclParser_Free(&parse);
        if (strict[0]) STATE.strict_mode = atoi(strict);
        if (maxf[0]) STATE.max_files = atoi(maxf);
        return BclResult_Ok(bcl_out, out_sz,
            "[@STATUS]{config_set}[@STRICT]{set}[@MAX]{set}");
    }

    /* ===== CHECK ===== */
    if (strcmp(cmd, "check") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[RE_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        int offset = snprintf(bcl_out, out_sz, "[@OK]{");
        int count = re_check_file(path, bcl_out, out_sz, &offset);
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@TOTAL_VIOLATIONS]{%d}[@STATUS]{%s}}",
            count, (count == 0) ? "COMPLIANT" : "VIOLATIONS");
        return 1;
    }

    /* ===== CHECK_DIR ===== */
    if (strcmp(cmd, "check_dir") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[RE_MAX_PATH] = {0};
        char max_str[16] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "MAX", max_str, sizeof(max_str));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        int max_files = max_str[0] ? atoi(max_str) : STATE.max_files;
        if (max_files <= 0 || max_files > RE_MAX_FILES) max_files = RE_MAX_FILES;
        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@DIR]{%s}[@MAX]{%d}", path, max_files);
        int checked = 0;
        re_walk_dir(path, bcl_out, out_sz, &offset, max_files, &checked, 0);
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@FILES_CHECKED]{%d}[@TOTAL_VIOLATIONS]{%d}[@TOTAL_COMPLIANT]{%d}}",
            checked, STATE.total_violations, STATE.total_compliant);
        return 1;
    }

    /* ===== EVALUATE ===== */
    if (strcmp(cmd, "evaluate") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char code[RE_MAX_BODY] = {0};
        BclParser_Extract(&parse, "CODE", code, sizeof(code));
        BclParser_Free(&parse);
        if (!code[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no CODE in packet");
        }
        return re_evaluate(code, bcl_out, out_sz);
    }

    /* ===== REPORT — walk directory, generate full compliance report ===== */
    if (strcmp(cmd, "report") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[RE_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        int by_rule[RE_RULE_COUNT];
        for (int i = 0; i < RE_RULE_COUNT; i++) by_rule[i] = 0;
        int checked = 0, compliant = 0, violating = 0, total_vios = 0;
        re_report_walk(path, RE_MAX_FILES, &checked, &compliant, &violating,
                       &total_vios, by_rule, 0);
        STATE.report_files = checked;
        STATE.report_compliant = compliant;
        STATE.report_violating = violating;
        STATE.total_checked += checked;
        STATE.total_compliant += compliant;
        STATE.total_violations += total_vios;
        for (int i = 0; i < RE_RULE_COUNT; i++) STATE.tally[i] += by_rule[i];

        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@DIR]{%s}[@FILES]{%d}[@COMPLIANT]{%d}[@VIOLATING]{%d}"
            "[@TOTAL_VIOLATIONS]{%d}[@BY_RULE]{",
            path, checked, compliant, violating, total_vios);
        for (int i = 0; i < RE_RULE_COUNT; i++) {
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@RULE]{%s}[@COUNT]{%d}",
                RE_RULE_NAMES[i], by_rule[i]);
        }
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "}[@STATUS]{report_complete}}");
        return 1;
    }

    /* ===== CHECK_RULES — load rules from MySQL, check file vs matching rules ===== */
    if (strcmp(cmd, "check_rules") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[RE_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }

        int run_mask[RE_RULE_COUNT];
        for (int i = 0; i < RE_RULE_COUNT; i++) run_mask[i] = 0;
        int rules_loaded = 0;

        EnsureConnected();
        if (s_mysql) {
            if (mysql_query(s_mysql,
                    "SELECT rule, description FROM rules ORDER BY rule") == 0) {
                MYSQL_RES *res = mysql_store_result(s_mysql);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL) {
                        const char *rule = row[0] ? row[0] : "";
                        int idx = re_match_rule_keyword(rule);
                        if (idx >= 0) {
                            run_mask[idx] = 1;
                            rules_loaded++;
                        }
                    }
                    mysql_free_result(res);
                }
            }
        }
        STATE.rules_loaded = rules_loaded;

        static char file_buf[RE_MAX_FILE];
        long len = re_read_file(path, file_buf, sizeof(file_buf));
        if (len < 0) {
            int offset = snprintf(bcl_out, out_sz,
                "[@OK]{[@RULES_LOADED]{%d}[@FILE]{[@PATH]{%s}"
                "[@ERROR]{cannot_read}[@VIOLATIONS]{0}[@STATUS]{ERROR}}",
                rules_loaded, path);
            (void)offset;
            return 1;
        }

        STATE.total_checked++;
        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        STATE.last_path[sizeof(STATE.last_path) - 1] = '\0';

        RuleViolation vios[RE_MAX_VIOLATIONS];
        memset(vios, 0, sizeof(vios));
        int count = re_check_code_masked(file_buf, vios, RE_MAX_VIOLATIONS,
                                         STATE.tally, run_mask);
        STATE.total_violations += count;
        if (count == 0) STATE.total_compliant++;

        const char *status = (count == 0) ? "COMPLIANT" : "VIOLATIONS";
        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@RULES_LOADED]{%d}[@FILE]{[@PATH]{%s}[@VIOLATIONS]{%d}",
            rules_loaded, path, count);
        re_emit_violations(bcl_out, out_sz, &offset, vios, count);
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@TOTAL_VIOLATIONS]{%d}[@STATUS]{%s}}",
            count, status);
        (void)offset;
        return 1;
    }

    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int RuleEngine_Close(void) {
    if (s_mysql) {
        mysql_close(s_mysql);
        s_mysql = NULL;
    }
    STATE.initialized = 0;
    return 1;
}

const char * RuleEngine_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "RuleEngine: initialized=%d checked=%d compliant=%d violations=%d",
        STATE.initialized, STATE.total_checked,
        STATE.total_compliant, STATE.total_violations);
    return buf;
}
