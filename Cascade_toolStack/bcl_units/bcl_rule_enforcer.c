//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_rule_enforcer.c" date="2026-07-04" author="devin" session_id="bcl-vsstyle-units" context="BCL unit for enforcing VBStyle rules — blocks files with too many violations. Source: core/Dom_Vsstyle/vbs_rule_enforcer.py. Commands: enforce, block, stats, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_rule_enforcer.c" domain="bcl_units" authority="RuleEnforcer"}
//[@SUMMARY]{summary="VBStyle rule enforcer. Checks files, blocks if violations exceed threshold. Commands: enforce, block, stats, read_state, set_config."}
//[@CLASS]{class="RuleEnforcer" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Enforce" type="command"}
//[@METHOD]{method="Block" type="command"}
//[@METHOD]{method="Stats" type="query"}
/*
 * bcl_rule_enforcer.c — VBStyle rule enforcer BCL unit
 * BCL IN:  enforce [@PATH], block [@PATH][@THRESHOLD], stats,
 *          read_state, set_config [@MAX_VIOLATIONS]
 * BCL OUT: [@OK]{[@FILE]{path}[@STATUS]{PASS|BLOCKED}[@VIOLATIONS]{N}[@THRESHOLD]{N}}
 */
#include "bcl_toolstack.h"
#include <dirent.h>
#include <sys/stat.h>

/* ===== DIM BLOCK ===== */
#define RE_MAX_PATH        4096
#define RE_MAX_FILE        262144
#define RE_MAX_VIOLATIONS  256
#define RE_MAX_BODY        8192
#define RE_MAX_LINE        1024
#define RE_MAX_RULENAME    32
#define RE_MAX_DETAILS     256
#define RE_RULE_COUNT      9
#define RE_DEFAULT_THRESH  10

typedef struct {
    char rule[RE_MAX_RULENAME];
    int  line;
    char details[RE_MAX_DETAILS];
} ReViolation;

static const char *RE_RULE_NAMES[RE_RULE_COUNT] = {
    "NoPrint", "NoDecorators", "NoSelfUnderscore",
    "GhostHeader", "VBStyleHeader", "RunDispatch",
    "PascalCase", "NoTabs", "NoTrailingWS"
};

static struct {
    int  initialized;
    int  total_enforced;
    int  total_blocked;
    int  total_passed;
    int  max_violations;   /* threshold */
    char last_path[RE_MAX_PATH];
    int  tally[RE_RULE_COUNT];
} STATE;

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

/* ===== LINE ITERATOR ===== */
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
static int re_line_has_print(const char *line) {
    const char *p = line;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '#') return 0;
    return strncmp(p, "print(", 6) == 0 ? 1 : 0;
}

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

static int re_line_has_self_underscore(const char *line) {
    return strstr(line, "self._") != NULL ? 1 : 0;
}

static int re_line_has_tab(const char *line) {
    return strchr(line, '\t') != NULL ? 1 : 0;
}

static int re_line_has_trailing_ws(const char *line) {
    size_t n = strlen(line);
    if (n == 0) return 0;
    char last = line[n - 1];
    return (last == ' ' || last == '\t' || last == '\r') ? 1 : 0;
}

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

static int re_line_has_run(const char *line) {
    const char *p = line;
    if (*p != ' ' && *p != '\t') return 0;
    while (*p == ' ' || *p == '\t') p++;
    if (strncmp(p, "def Run(", 8) == 0) return 1;
    return 0;
}

static int re_is_pascalcase(const char *name) {
    if (!name[0]) return 0;
    if (!isupper((unsigned char)name[0])) return 0;
    for (const char *p = name; *p; p++) {
        if (*p == '_') return 0;
    }
    return 1;
}

/* ===== CHECK CODE — scan lines, fill violations array =====
 * Returns violation count (capped at RE_MAX_VIOLATIONS). */
static int re_check_code(const char *code, ReViolation *vios, int max_v) {
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

        if (re_line_has_print(line)) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoPrint");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "print() found");
            count++; STATE.tally[0]++;
            if (count >= max_v) break;
        }

        char which[32];
        if (re_line_has_decorator(line, which, sizeof(which))) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoDecorators");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "%s found", which);
            count++; STATE.tally[1]++;
            if (count >= max_v) break;
        }

        if (re_line_has_self_underscore(line)) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoSelfUnderscore");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "self._ found");
            count++; STATE.tally[2]++;
            if (count >= max_v) break;
        }

        if (re_line_has_tab(line)) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoTabs");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "tab character found");
            count++; STATE.tally[7]++;
            if (count >= max_v) break;
        }

        if (re_line_has_trailing_ws(line)) {
            snprintf(vios[count].rule, sizeof(vios[count].rule), "NoTrailingWS");
            vios[count].line = lineno;
            snprintf(vios[count].details, sizeof(vios[count].details),
                "trailing whitespace");
            count++; STATE.tally[8]++;
            if (count >= max_v) break;
        }
    }

    if (!has_ghost && count < max_v) {
        snprintf(vios[count].rule, sizeof(vios[count].rule), "GhostHeader");
        vios[count].line = 0;
        snprintf(vios[count].details, sizeof(vios[count].details),
            "missing [@GHOST] header");
        count++; STATE.tally[3]++;
    }
    if (!has_vbstyle && count < max_v) {
        snprintf(vios[count].rule, sizeof(vios[count].rule), "VBStyleHeader");
        vios[count].line = 0;
        snprintf(vios[count].details, sizeof(vios[count].details),
            "missing [@VBSTYLE] header");
        count++; STATE.tally[4]++;
    }
    if (!has_run && count < max_v) {
        snprintf(vios[count].rule, sizeof(vios[count].rule), "RunDispatch");
        vios[count].line = 0;
        snprintf(vios[count].details, sizeof(vios[count].details),
            "missing Run() method");
        count++; STATE.tally[5]++;
    }
    if (has_class && class_name[0] && !re_is_pascalcase(class_name) && count < max_v) {
        snprintf(vios[count].rule, sizeof(vios[count].rule), "PascalCase");
        vios[count].line = 0;
        snprintf(vios[count].details, sizeof(vios[count].details),
            "class %s not PascalCase", class_name);
        count++; STATE.tally[6]++;
    }

    return count;
}

/* ===== ENFORCE FILE — read + check, return count via out param ===== */
static int re_enforce_file(const char *path, int *violation_count) {
    static char file_buf[RE_MAX_FILE];
    long len = re_read_file(path, file_buf, sizeof(file_buf));
    if (len < 0) {
        *violation_count = -1;
        return 0;
    }
    STATE.total_enforced++;
    strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
    STATE.last_path[sizeof(STATE.last_path) - 1] = '\0';

    ReViolation vios[RE_MAX_VIOLATIONS];
    memset(vios, 0, sizeof(vios));
    int count = re_check_code(file_buf, vios, RE_MAX_VIOLATIONS);
    *violation_count = count;
    return (count == 0) ? 1 : 0;
}

/* ===== UNIT INTERFACE ===== */
int RuleEnforcer_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.max_violations = RE_DEFAULT_THRESH;
    STATE.initialized = 1;
    return 1;
}

int RuleEnforcer_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) RuleEnforcer_Init();

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[RE_MAX_BODY];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{1}[@TOTAL_ENFORCED]{%d}[@TOTAL_BLOCKED]{%d}"
            "[@TOTAL_PASSED]{%d}[@MAX_VIOLATIONS]{%d}[@LAST_PATH]{%s}",
            STATE.total_enforced, STATE.total_blocked,
            STATE.total_passed, STATE.max_violations, STATE.last_path);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char maxv[16] = {0};
        BclParser_Extract(&parse, "MAX_VIOLATIONS", maxv, sizeof(maxv));
        BclParser_Extract(&parse, "THRESHOLD", maxv, sizeof(maxv));
        BclParser_Free(&parse);
        if (maxv[0]) STATE.max_violations = atoi(maxv);
        return BclResult_Ok(bcl_out, out_sz,
            "[@STATUS]{config_set}[@MAX_VIOLATIONS]{set}");
    }

    /* ===== STATS ===== */
    if (strcmp(cmd, "stats") == 0) {
        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@TOTAL_ENFORCED]{%d}[@TOTAL_BLOCKED]{%d}"
            "[@TOTAL_PASSED]{%d}[@MAX_VIOLATIONS]{%d}[@BY_RULE]{",
            STATE.total_enforced, STATE.total_blocked,
            STATE.total_passed, STATE.max_violations);
        for (int i = 0; i < RE_RULE_COUNT; i++) {
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@RULE]{[@NAME]{%s}[@COUNT]{%d}}",
                RE_RULE_NAMES[i], STATE.tally[i]);
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}}");
        return 1;
    }

    /* ===== ENFORCE ===== */
    if (strcmp(cmd, "enforce") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[RE_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        int count = 0;
        int passed = re_enforce_file(path, &count);
        if (count < 0) {
            return BclResult_Err(bcl_out, out_sz, 21, "cannot read file");
        }
        if (passed) STATE.total_passed++;
        const char *status = passed ? "PASS" : "FAIL";
        char body[RE_MAX_BODY];
        snprintf(body, sizeof(body),
            "[@FILE]{%s}[@STATUS]{%s}[@VIOLATIONS]{%d}[@THRESHOLD]{%d}",
            path, status, count, STATE.max_violations);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== BLOCK ===== */
    if (strcmp(cmd, "block") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[RE_MAX_PATH] = {0};
        char thr_str[16] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "THRESHOLD", thr_str, sizeof(thr_str));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        int threshold = thr_str[0] ? atoi(thr_str) : STATE.max_violations;
        int count = 0;
        int passed = re_enforce_file(path, &count);
        if (count < 0) {
            return BclResult_Err(bcl_out, out_sz, 21, "cannot read file");
        }
        int blocked = (count > threshold) ? 1 : 0;
        if (blocked) STATE.total_blocked++;
        else if (passed) STATE.total_passed++;
        const char *status = blocked ? "BLOCKED" : "PASS";
        char body[RE_MAX_BODY];
        snprintf(body, sizeof(body),
            "[@FILE]{%s}[@STATUS]{%s}[@VIOLATIONS]{%d}[@THRESHOLD]{%d}",
            path, status, count, threshold);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- report — walk directory, enforce each .py file, aggregate ---- */
    if (strcmp(cmd, "report") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[RE_MAX_PATH] = {0};
        char thr_str[16] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "THRESHOLD", thr_str, sizeof(thr_str));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 22, "no PATH in packet");
        }
        int threshold = thr_str[0] ? atoi(thr_str) : STATE.max_violations;

        /* Walk directory recursively */
        DIR *d = opendir(path);
        if (!d) {
            return BclResult_Err(bcl_out, out_sz, 23, "cannot open directory");
        }

        int total_files = 0;
        int total_pass = 0;
        int total_block = 0;
        int total_violations = 0;
        char body[RE_MAX_BODY];
        int offset = 0;
        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@DIR]{%s}[@THRESHOLD]{%d}", path, threshold);

        /* Simple stack-based walk (depth <= 8) */
        char dirs[16][RE_MAX_PATH];
        int dir_top = 0;
        strncpy(dirs[dir_top++], path, RE_MAX_PATH - 1);

        while (dir_top > 0 && total_files < 500) {
            char cur[RE_MAX_PATH];
            strncpy(cur, dirs[--dir_top], RE_MAX_PATH);
            cur[RE_MAX_PATH - 1] = '\0';
            DIR *cd = opendir(cur);
            if (!cd) continue;
            struct dirent *entry;
            while ((entry = readdir(cd)) != NULL && total_files < 500) {
                if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
                if (strstr(entry->d_name, ".git") || strstr(entry->d_name, "__pycache__") ||
                    strstr(entry->d_name, "node_modules") || strstr(entry->d_name, ".venv") ||
                    strstr(entry->d_name, ".codex")) continue;

                char full[RE_MAX_PATH];
                snprintf(full, sizeof(full), "%s/%s", cur, entry->d_name);
                struct stat st;
                if (stat(full, &st) != 0) continue;

                if (S_ISDIR(st.st_mode)) {
                    if (dir_top < 16) {
                        strncpy(dirs[dir_top++], full, RE_MAX_PATH - 1);
                    }
                    continue;
                }
                if (!S_ISREG(st.st_mode)) continue;
                const char *ext = strrchr(entry->d_name, '.');
                if (!ext || strcmp(ext, ".py") != 0) continue;

                total_files++;
                int vc = 0;
                re_enforce_file(full, &vc);
                if (vc < 0) continue;
                total_violations += vc;
                int blocked = (vc > threshold) ? 1 : 0;
                if (blocked) total_block++;
                else total_pass++;

                if (offset < (int)sizeof(body) - 256) {
                    const char *st_str = blocked ? "BLOCKED" : "PASS";
                    offset += snprintf(body + offset, sizeof(body) - offset,
                        "[@FILE]{[@PATH]{%s}[@STATUS]{%s}[@VIOLATIONS]{%d}}",
                        full, st_str, vc);
                }
            }
            closedir(cd);
        }

        offset += snprintf(body + offset, sizeof(body) - offset,
            "[@FILES]{%d}[@PASSED]{%d}[@BLOCKED]{%d}[@TOTAL_VIOLATIONS]{%d}[@STATUS]{enforcement_report}",
            total_files, total_pass, total_block, total_violations);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int RuleEnforcer_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * RuleEnforcer_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "RuleEnforcer: initialized=%d enforced=%d blocked=%d passed=%d threshold=%d",
        STATE.initialized, STATE.total_enforced,
        STATE.total_blocked, STATE.total_passed, STATE.max_violations);
    return buf;
}
