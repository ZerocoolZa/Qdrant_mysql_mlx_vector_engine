//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_stamper.c" date="2026-06-29" author="Devin" session_id="bcl-c-central-db" context="Generate BCL header stamps from AST — GHOST, VBSTYLE, CLASSES, METHODS"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_stamper.c" domain="bcl_c_engine" authority="BclStamper"}
//[@SUMMARY]{summary="BCL stamper — generates @GHOST/@VBSTYLE/@CLASSES/@METHODS header stamps from parsed AST"}
//
// Generates VBStyle bracket stamps:
//   [@GHOST]    — file identity (path, date, author, version)
//   [@VBSTYLE]  — style rules (auth, role, return, orch, no, model)
//   [@CLASSES]  — comma-separated class names
//   [@METHODS]  — comma-separated method names
//
// Output is a ready-to-paste header block.

#include "bcl_engine.h"
#include <time.h>

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
    snprintf(out, out_sz, "%04d-%02d-%02d", tm->tm_year + 1900, tm->tm_mon + 1, tm->tm_mday);
}

/* ════════════════════════════════════════════
 * PUBLIC API
 * ════════════════════════════════════════════ */

void bcl_stamp_ghost(ParseResult *r, char *out, size_t out_sz) {
    char fname[256];
    char date[16];
    basename_only(r->file_path, fname, sizeof(fname));
    today_str(date, sizeof(date));

    snprintf(out, out_sz,
        "#[@GHOST]{(\"file_path=%s\";\"identity=%s\";\"purpose=VBStyle domain authority\";\"date=%s\";\"version=1.0\";\"author=VBAST\";\"task=auto-stamped\")}",
        r->file_path, fname, date);
}

void bcl_stamp_vbstyle(ParseResult *r, char *out, size_t out_sz) {
    snprintf(out, out_sz,
        "#[@VBSTYLE]{(\"auth=VBAST\";\"role=domain_authority\";\"return=Tuple3\";\"orch=none\";\"no=decorators|print|hardcoded|tabs|self_underscore\";\"model=one_class_one_domain_one_authority_complete\")}");
}

void bcl_stamp_classes(ParseResult *r, char *out, size_t out_sz) {
    out[0] = '\0';
    size_t pos = 0;
    pos += snprintf(out + pos, out_sz - pos, "#[@CLASSES]{(\"");
    for (int i = 0; i < r->class_count && pos < out_sz - 32; i++) {
        if (i > 0) pos += snprintf(out + pos, out_sz - pos, ";");
        pos += snprintf(out + pos, out_sz - pos, "%s", r->classes[i].name);
    }
    pos += snprintf(out + pos, out_sz - pos, "\")}");
}

void bcl_stamp_methods(ParseResult *r, char *out, size_t out_sz) {
    out[0] = '\0';
    size_t pos = 0;
    pos += snprintf(out + pos, out_sz - pos, "#[@METHODS]{(\"");
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

    snprintf(out, out_sz,
        "\"\"\"\n%s\n%s\n%s\n%s\n\"\"\"\n",
        ghost, vbstyle, classes, methods);
}
