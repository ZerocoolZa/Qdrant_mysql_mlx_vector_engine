//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_bcl_stamper.c" date="2026-07-04" author="Devin" session_id="bcl-vbast-units" context="BCL unit for BCL header stamp generation. Source: parsed AST (tree-sitter). Pipeline: ast_init -> ast_parse_file -> bcl_stamp_* -> BCL output. Absorbs bcl_stamper.c from vbast. No MySQL dependency."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_bcl_stamper.c" domain="bcl_units" authority="BclStamper"}
//[@SUMMARY]{summary="BCL stamper unit. Source = parsed AST. Owns full pipeline: ast_init, ast_parse_file, bcl_stamp_ghost/vbstyle/classes/methods/all, BCL output. Commands: stamp_all, stamp_ghost, stamp_vbstyle, stamp_classes, stamp_methods, read_state. No MySQL."}
//[@CLASS]{class="BclStamper" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="basename_only" type="internal"}
//[@METHOD]{method="today_str" type="internal"}
//[@METHOD]{method="bcl_stamp_ghost" type="internal"}
//[@METHOD]{method="bcl_stamp_vbstyle" type="internal"}
//[@METHOD]{method="bcl_stamp_classes" type="internal"}
//[@METHOD]{method="bcl_stamp_methods" type="internal"}
//[@METHOD]{method="bcl_stamp_all" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<BCL stamper unit. Generates @GHOST/@VBSTYLE/@CLASSES/@METHODS header stamps from parsed AST. Absorbs bcl_stamper.c from vbast.>][@todos<>]}

/*
 * bcl_bcl_stamper.c — BCL header stamp generator BCL unit
 *
 * BCL IN:  [@RUN]{[@CMD]{stamp_all}[@PATH]{/path/to/file.py}}
 *          [@RUN]{[@CMD]{stamp_ghost}[@PATH]{/path/to/file.py}}
 *          [@RUN]{[@CMD]{stamp_vbstyle}[@PATH]{/path/to/file.py}}
 *          [@RUN]{[@CMD]{stamp_classes}[@PATH]{/path/to/file.py}}
 *          [@RUN]{[@CMD]{stamp_methods}[@PATH]{/path/to/file.py}}
 *          [@RUN]{[@CMD]{read_state}}
 * BCL OUT: [@OK]{[@FILE]{...}[@STAMP]{...the full stamp block...}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "vbast.h"
#include "bcl_toolstack.h"
#include <time.h>

/* ===== DIM BLOCK ===== */

#define STAMPER_MAX_PATH   1024
#define STAMPER_MAX_STAMP  8192

/* State */
static struct {
    int  initialized;
    ParseResult result;
    int  files_stamped;
    char last_error[256];
    char stamp_output[STAMPER_MAX_STAMP];
} STATE;

/* ===== SECTION: STATIC HELPERS ===== */

/* ── extract filename from path ── */

static void basename_only(const char *path, char *out, size_t out_sz) {
    const char *slash = strrchr(path, '/');
    const char *base = slash ? slash + 1 : path;
    strncpy(out, base, out_sz - 1);
    out[out_sz - 1] = '\0';
}

/* ── get current date (YYYY-MM-DD) ── */

static void today_str(char *out, size_t out_sz) {
    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    snprintf(out, out_sz, "%04d-%02d-%02d",
             tm->tm_year + 1900, tm->tm_mon + 1, tm->tm_mday);
}

/* ===== SECTION: PUBLIC API (stamp generators) ===== */

void bcl_stamp_ghost(ParseResult *r, char *out, size_t out_sz) {
    char fname[256];
    char date[16];
    basename_only(r->file_path, fname, sizeof(fname));
    today_str(date, sizeof(date));

    /* C files use // comment style, Python uses # */
    const char *prefix = (r->language == LANG_C) ? "//" : "#";

    snprintf(out, out_sz,
        "%s[@GHOST]{(\"file_path=%s\";\"identity=%s\";\"purpose=VBStyle domain authority\";\"date=%s\";\"version=1.0\";\"author=VBAST\";\"task=auto-stamped\")}",
        prefix, r->file_path, fname, date);
}

void bcl_stamp_vbstyle(ParseResult *r, char *out, size_t out_sz) {
    /* C files use // comment style, Python uses # */
    const char *prefix = (r->language == LANG_C) ? "//" : "#";

    snprintf(out, out_sz,
        "%s[@VBSTYLE]{(\"auth=VBAST\";\"role=domain_authority\";\"return=Tuple3\";\"orch=none\";\"no=decorators|print|hardcoded|tabs|self_underscore\";\"model=one_class_one_domain_one_authority_complete\")}",
        prefix);
}

void bcl_stamp_classes(ParseResult *r, char *out, size_t out_sz) {
    out[0] = '\0';
    size_t pos = 0;
    const char *prefix = (r->language == LANG_C) ? "//" : "#";
    pos += snprintf(out + pos, out_sz - pos, "%s[@CLASSES]{(\"", prefix);
    for (int i = 0; i < r->class_count && pos < out_sz - 32; i++) {
        if (i > 0) pos += snprintf(out + pos, out_sz - pos, ";");
        pos += snprintf(out + pos, out_sz - pos, "%s", r->classes[i].name);
    }
    pos += snprintf(out + pos, out_sz - pos, "\")}");
}

void bcl_stamp_methods(ParseResult *r, char *out, size_t out_sz) {
    out[0] = '\0';
    size_t pos = 0;
    const char *prefix = (r->language == LANG_C) ? "//" : "#";
    pos += snprintf(out + pos, out_sz - pos, "%s[@METHODS]{(\"", prefix);
    int first = 1;
    for (int i = 0; i < r->method_count && pos < out_sz - 64; i++) {
        if (!first) pos += snprintf(out + pos, out_sz - pos, ";");
        pos += snprintf(out + pos, out_sz - pos, "%s", r->methods[i].name);
        first = 0;
    }
    pos += snprintf(out + pos, out_sz - pos, "\")}");
}

void bcl_stamp_all(ParseResult *r, char *out, size_t out_sz) {
    char ghost[512];
    char vbstyle[512];
    char classes[1024];
    char methods[4096];

    bcl_stamp_ghost(r, ghost, sizeof(ghost));
    bcl_stamp_vbstyle(r, vbstyle, sizeof(vbstyle));
    bcl_stamp_classes(r, classes, sizeof(classes));
    bcl_stamp_methods(r, methods, sizeof(methods));

    /* C files use block comment, Python uses docstring */
    if (r->language == LANG_C) {
        snprintf(out, out_sz,
            "/*\n%s\n%s\n%s\n%s\n*/\n",
            ghost, vbstyle, classes, methods);
    } else {
        snprintf(out, out_sz,
            "\"\"\"\n%s\n%s\n%s\n%s\n\"\"\"\n",
            ghost, vbstyle, classes, methods);
    }
}

/* ===== SECTION: INTERNAL — parse file then run a stamp function ===== */

typedef void (*StampFn)(ParseResult *r, char *out, size_t out_sz);

static int stamper_run_stamp(const char *bcl_in, char *bcl_out, size_t out_sz,
                             StampFn fn) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char path[STAMPER_MAX_PATH] = {0};
    BclParser_Extract(&parse, "PATH", path, sizeof(path));
    BclParser_Free(&parse);

    if (!path[0]) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "no PATH in packet");
        return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
    }

    ast_init(&STATE.result, path);
    if (ast_parse_file(&STATE.result) == 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
                 "ast_parse_file failed for %s", path);
        ast_free(&STATE.result);
        return BclResult_Err(bcl_out, out_sz, 21, "parse failed");
    }

    STATE.stamp_output[0] = '\0';
    fn(&STATE.result, STATE.stamp_output, sizeof(STATE.stamp_output));

    STATE.files_stamped++;
    ast_free(&STATE.result);

    return BclResult_Ok(bcl_out, out_sz,
        STATE.stamp_output);
}

/* ===== SECTION: UNIT INTERFACE ===== */

int BclStamper_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    return 1;
}

int BclStamper_Run(const char *cmd, const char *bcl_in,
                   char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) BclStamper_Init();

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[256];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@STAMPED]{%d}",
            STATE.initialized, STATE.files_stamped);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== STAMP_ALL ===== */
    if (strcmp(cmd, "stamp_all") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[STAMPER_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }

        ast_init(&STATE.result, path);
        if (ast_parse_file(&STATE.result) == 0) {
            snprintf(STATE.last_error, sizeof(STATE.last_error),
                     "ast_parse_file failed for %s", path);
            ast_free(&STATE.result);
            return BclResult_Err(bcl_out, out_sz, 21, "parse failed");
        }

        STATE.stamp_output[0] = '\0';
        bcl_stamp_all(&STATE.result, STATE.stamp_output,
                      sizeof(STATE.stamp_output));
        STATE.files_stamped++;
        ast_free(&STATE.result);

        char body[STAMPER_MAX_STAMP + 256];
        snprintf(body, sizeof(body),
            "[@FILE]{%s}[@STAMP]{%s}", path, STATE.stamp_output);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== STAMP_GHOST ===== */
    if (strcmp(cmd, "stamp_ghost") == 0) {
        return stamper_run_stamp(bcl_in, bcl_out, out_sz, bcl_stamp_ghost);
    }

    /* ===== STAMP_VBSTYLE ===== */
    if (strcmp(cmd, "stamp_vbstyle") == 0) {
        return stamper_run_stamp(bcl_in, bcl_out, out_sz, bcl_stamp_vbstyle);
    }

    /* ===== STAMP_CLASSES ===== */
    if (strcmp(cmd, "stamp_classes") == 0) {
        return stamper_run_stamp(bcl_in, bcl_out, out_sz, bcl_stamp_classes);
    }

    /* ===== STAMP_METHODS ===== */
    if (strcmp(cmd, "stamp_methods") == 0) {
        return stamper_run_stamp(bcl_in, bcl_out, out_sz, bcl_stamp_methods);
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int BclStamper_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * BclStamper_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "BclStamper: initialized=%d files_stamped=%d last_error=%s",
        STATE.initialized, STATE.files_stamped,
        STATE.last_error[0] ? STATE.last_error : "(none)");
    return buf;
}
