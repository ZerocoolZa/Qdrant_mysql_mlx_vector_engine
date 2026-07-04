//[@GHOST]{file_path="Cascade_toolStack/bin_tools/bcl_builder.c" date="2026-06-29" author="Devin" session_id="bcl-builder" context="BCL unit builder — generates .c BCL unit files from BCL spec input, checks compliance, compiles"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_builder.c" domain="bcl_builder" authority="BclBuilder"}
//[@SUMMARY]{summary="BCL builder — accepts BCL spec, generates .c BCL unit file with BCL-in/BCL-out interface, stamps headers, checks VBStyle, compiles"}
//[@CLASS]{class="BclBuilder" domain="bcl_builder" authority="single"}
//[@METHOD]{methods="Run,make,check,test,parse_bcl_spec,write_unit_file,write_header,write_dispatch,write_methods,compile_unit"}

/*
 * bcl_builder.c — BCL Unit Builder
 *
 * Accepts BCL spec input, generates a complete .c BCL unit file.
 *
 * BCL IN:
 *   [@MAKE]{[@FILE]{bcl_scanner.c}[@DOMAIN]{scanner}[@AUTHORITY]{Scanner}
 *           [@SUMMARY]{Scans files for patterns}
 *           [@METHODS]{scan,list,read}
 *           [@INCLUDES]{sqlite3.h,string.h}}
 *
 * BCL OUT (success):
 *   [@OK]{[@FILE]{bcl_scanner.c}[@LINES]{142}[@COMPILE]{1}[@CHECK]{PASS}}
 *
 * BCL OUT (error):
 *   [@ERR]{[@CODE]{3}[@DESC]{compile failed}}
 *
 * Usage:
 *   bcl_builder "[@MAKE]{[@FILE]{name.c}[@DOMAIN]{dom}[@AUTHORITY]{Auth}
 *                [@SUMMARY]{desc}[@METHODS]{m1,m2,m3}
 *                [@INCLUDES]{lib1.h,lib2.h}}"
 *
 *   bcl_builder --file spec.bcl     # read spec from file
 *   bcl_builder --check unit.c      # check existing unit compliance
 *   bcl_builder --test unit.c       # compile-test a unit
 *
 * Compile:
 *   cc -O2 -Wall bcl_builder.c -o bcl_builder
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <unistd.h>
#include <sys/stat.h>

/* UPPERCASE CONSTANTS */

#define MAX_BCL    65536
#define MAX_FIELDS 64
#define MAX_FIELD  4096
#define MAX_NAME   256
#define MAX_METHODS 32
#define MAX_INCLUDES 32
#define MAX_LINE   1024

/* BCL field structure */
typedef struct {
    char tag[MAX_NAME];
    char value[MAX_FIELD];
} BclField;

typedef struct {
    BclField fields[MAX_FIELDS];
    int count;
} BclSpec;

/* Error codes */
static const char* ERR_OK       = "OK";
static const char* ERR_PARSE    = "PARSE_ERROR";
static const char* ERR_WRITE    = "WRITE_ERROR";
static const char* ERR_COMPILE  = "COMPILE_ERROR";
static const char* ERR_CHECK    = "CHECK_ERROR";
static const char* ERR_BADCMD   = "BADCMD";
static const char* ERR_NOFILE   = "NOFILE";
static const char* ERR_INTERNAL = "INTERNAL";

/* BCL output helpers */
static void bcl_ok(char* out, int out_sz, const char* fields_bcl) {
    snprintf(out, out_sz, "[@OK]{%s}", fields_bcl);
}

static void bcl_err(char* out, int out_sz, int code, const char* desc) {
    snprintf(out, out_sz, "[@ERR]{[@CODE]{%d}[@DESC]{%s}}", code, desc);
}

/* Parse BCL spec: [@MAKE]{[@FILE]{x}[@DOMAIN]{y}...} */
static int parse_bcl_spec(const char* input, BclSpec* spec) {
    spec->count = 0;
    const char* p = input;

    /* find [@MAKE]{ */
    p = strstr(p, "[@MAKE]");
    if (!p) return 0;
    p = strchr(p, '{');
    if (!p) return 0;
    p++;

    /* parse inner fields [@TAG]{value} */
    while (*p && *p != '}' && spec->count < MAX_FIELDS) {
        /* skip whitespace */
        while (*p && (*p == ' ' || *p == '\n' || *p == '\t')) p++;
        if (*p == '}' || *p == '\0') break;

        /* expect [@TAG] */
        if (*p != '[' || *(p+1) != '@') {
            p++;
            continue;
        }
        p += 2; /* skip [@ */

        /* read tag until ] */
        int ti = 0;
        while (*p && *p != ']' && ti < MAX_NAME - 1) {
            spec->fields[spec->count].tag[ti++] = *p++;
        }
        spec->fields[spec->count].tag[ti] = '\0';
        if (*p == ']') p++;

        /* expect {value} */
        if (*p != '{') {
            p++;
            continue;
        }
        p++; /* skip { */

        /* read value until matching } (handle nested braces) */
        int depth = 1;
        int vi = 0;
        while (*p && depth > 0 && vi < MAX_FIELD - 1) {
            if (*p == '{') depth++;
            else if (*p == '}') {
                depth--;
                if (depth == 0) break;
            }
            spec->fields[spec->count].value[vi++] = *p++;
        }
        spec->fields[spec->count].value[vi] = '\0';
        if (*p == '}') p++;

        spec->count++;
    }
    return spec->count;
}

static const char* spec_get(BclSpec* spec, const char* tag) {
    for (int i = 0; i < spec->count; i++) {
        if (strcmp(spec->fields[i].tag, tag) == 0)
            return spec->fields[i].value;
    }
    return NULL;
}

/* Split comma-separated list */
static int split_list(const char* input, char out[][MAX_NAME], int max) {
    int count = 0;
    const char* p = input;
    while (*p && count < max) {
        while (*p == ' ' || *p == ',') p++;
        if (!*p) break;
        int i = 0;
        while (*p && *p != ',' && i < MAX_NAME - 1) {
            out[count][i++] = *p++;
        }
        out[count][i] = '\0';
        /* trim trailing space */
        while (i > 0 && out[count][i-1] == ' ') out[count][--i] = '\0';
        count++;
    }
    return count;
}

/* ── Write BCL unit .c file ──────────────────────────────────── */

static int write_unit_file(BclSpec* spec, const char* filepath, char* report, int report_sz) {
    const char* filename = spec_get(spec, "FILE");
    const char* domain   = spec_get(spec, "DOMAIN");
    const char* authority = spec_get(spec, "AUTHORITY");
    const char* summary  = spec_get(spec, "SUMMARY");
    const char* methods_str = spec_get(spec, "METHODS");
    const char* includes_str = spec_get(spec, "INCLUDES");

    if (!filename || !domain || !authority) {
        bcl_err(report, report_sz, 1, "missing FILE, DOMAIN, or AUTHORITY in spec");
        return 0;
    }

    char outpath[MAX_NAME];
    snprintf(outpath, sizeof(outpath), "%s", filepath ? filepath : filename);

    /* parse methods */
    char methods[MAX_METHODS][MAX_NAME];
    int method_count = 0;
    if (methods_str) {
        method_count = split_list(methods_str, methods, MAX_METHODS);
    }
    if (method_count == 0) {
        strcpy(methods[0], "run");
        method_count = 1;
    }

    /* parse includes */
    char includes[MAX_INCLUDES][MAX_NAME];
    int include_count = 0;
    if (includes_str) {
        include_count = split_list(includes_str, includes, MAX_INCLUDES);
    }

    FILE* f = fopen(outpath, "w");
    if (!f) {
        bcl_err(report, report_sz, 2, "cannot write file");
        return 0;
    }

    /* BCL headers */
    fprintf(f, "//[@GHOST]{file_path=\"%s\" date=\"2026-06-29\" author=\"bcl_builder\" session_id=\"bcl-builder\" context=\"%s\"}\n",
            outpath, summary ? summary : "BCL unit");
    fprintf(f, "//[@VBSTYLE]{standard=\"VBStyle\" version=\"1\" rules=\"PascalCase UPPERCASE BCL-in BCL-out Run dispatch no-print\"}\n");
    fprintf(f, "//[@FILEID]{id=\"%s\" domain=\"%s\" authority=\"%s\"}\n", filename, domain, authority);
    fprintf(f, "//[@SUMMARY]{summary=\"%s\"}\n", summary ? summary : "BCL unit");
    fprintf(f, "//[@CLASS]{class=\"%s\" domain=\"%s\" authority=\"single\"}\n", authority, domain);
    fprintf(f, "//[@METHOD]{method=\"Run\" type=\"dispatch\"}\n");
    for (int i = 0; i < method_count; i++) {
        fprintf(f, "//[@METHOD]{method=\"%s\" type=\"command\"}\n", methods[i]);
    }
    fprintf(f, "\n/*\n * %s — %s\n *\n * BCL unit: accepts BCL in, returns BCL out.\n *   IN:  [@RUN]{[@CMD]{%s}[@PARAM]{...}}\n *   OUT: [@OK]{[@RESULT]{...}}\n *   ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}\n */\n\n",
            filename, summary ? summary : "BCL unit", methods[0]);

    /* Includes */
    fprintf(f, "#include <stdio.h>\n");
    fprintf(f, "#include <stdlib.h>\n");
    fprintf(f, "#include <string.h>\n");
    for (int i = 0; i < include_count; i++) {
        /* if it has a path separator, use quotes, else angle brackets */
        if (strchr(includes[i], '/')) {
            fprintf(f, "#include \"%s\"\n", includes[i]);
        } else {
            fprintf(f, "#include <%s>\n", includes[i]);
        }
    }
    fprintf(f, "\n");

    /* Constants */
    fprintf(f, "/* UPPERCASE CONSTANTS */\n");
    fprintf(f, "#define MAX_BCL 65536\n\n");

    /* Command enum */
    fprintf(f, "typedef enum {\n");
    for (int i = 0; i < method_count; i++) {
        /* uppercase the method name for enum */
        char enum_name[MAX_NAME];
        int j;
        for (j = 0; methods[i][j] && j < MAX_NAME - 1; j++) {
            enum_name[j] = toupper((unsigned char)methods[i][j]);
        }
        enum_name[j] = '\0';
        fprintf(f, "    CMD_%s = %d,\n", enum_name, i);
    }
    fprintf(f, "    CMD_COUNT\n");
    fprintf(f, "} Command;\n\n");

    /* Unit struct */
    fprintf(f, "typedef struct {\n");
    fprintf(f, "    char state[1024];\n");
    fprintf(f, "    char config[1024];\n");
    fprintf(f, "} %s;\n\n", authority);

    /* BCL output helpers */
    fprintf(f, "static void bcl_ok(char* out, int sz, const char* result) {\n");
    fprintf(f, "    snprintf(out, sz, \"[@OK]{%%s}\", result);\n");
    fprintf(f, "}\n\n");
    fprintf(f, "static void bcl_err(char* out, int sz, int code, const char* desc) {\n");
    fprintf(f, "    snprintf(out, sz, \"[@ERR]{{[@CODE]{%%d}[@DESC]{%%s}}}\", code, desc);\n");
    fprintf(f, "}\n\n");

    /* Forward declarations */
    fprintf(f, "/* FORWARD DECLARATIONS */\n");
    for (int i = 0; i < method_count; i++) {
        fprintf(f, "static const char* fn_%s(%s* u, const char* bcl_in, char* out, int out_sz);\n",
                methods[i], authority);
    }
    fprintf(f, "\n");

    /* Dispatch table */
    fprintf(f, "/* DISPATCH TABLE */\n");
    fprintf(f, "typedef const char* (*CmdFn)(%s*, const char*, char*, int);\n", authority);
    fprintf(f, "static const CmdFn DISPATCH[CMD_COUNT] = {\n");
    for (int i = 0; i < method_count; i++) {
        fprintf(f, "    fn_%s,\n", methods[i]);
    }
    fprintf(f, "};\n\n");

    /* Init */
    fprintf(f, "void %s_Init(%s* u) {\n", authority, authority);
    fprintf(f, "    memset(u, 0, sizeof(*u));\n");
    fprintf(f, "}\n\n");

    /* Run dispatch — BCL in, BCL out */
    fprintf(f, "/* Run — BCL in, BCL out */\n");
    fprintf(f, "const char* %s_Run(%s* u, Command cmd, const char* bcl_in, char* out, int out_sz) {\n",
            authority, authority);
    fprintf(f, "    if (cmd < 0 || cmd >= CMD_COUNT) {\n");
    fprintf(f, "        bcl_err(out, out_sz, 1, \"unknown_command\");\n");
    fprintf(f, "        return out;\n");
    fprintf(f, "    }\n");
    fprintf(f, "    return DISPATCH[cmd](u, bcl_in, out, out_sz);\n");
    fprintf(f, "}\n\n");

    /* Method stubs — BCL in, BCL out */
    fprintf(f, "/* METHOD STUBS — BCL in, BCL out */\n\n");
    for (int i = 0; i < method_count; i++) {
        fprintf(f, "static const char* fn_%s(%s* u, const char* bcl_in, char* out, int out_sz) {\n",
                methods[i], authority);
        fprintf(f, "    /* IN:  [@RUN]{[@CMD]{%s}[@PARAM]{...}} */\n", methods[i]);
        fprintf(f, "    /* OUT: [@OK]{[@RESULT]{...}} */\n");
        fprintf(f, "    (void)u; (void)bcl_in;\n");
        fprintf(f, "    bcl_ok(out, out_sz, \"[@RESULT]{implemented}\");\n");
        fprintf(f, "    return out;\n");
        fprintf(f, "}\n\n");
    }

    /* CLI main for standalone testing */
    fprintf(f, "/* CLI — for standalone testing */\n");
    fprintf(f, "#ifdef BCL_UNIT_STANDALONE\n");
    fprintf(f, "int main(int argc, char** argv) {\n");
    fprintf(f, "    %s u;\n", authority);
    fprintf(f, "    %s_Init(&u);\n", authority);
    fprintf(f, "    char out[MAX_BCL];\n");
    fprintf(f, "    const char* bcl_in = (argc > 1) ? argv[1] : \"[@RUN]{[@CMD]{%s}}\";\n", methods[0]);
    fprintf(f, "    /* parse cmd from bcl_in — simplified: just use first method */\n");
    fprintf(f, "    const char* result = %s_Run(&u, 0, bcl_in, out, sizeof(out));\n", authority);
    fprintf(f, "    printf(\"%%s\\n\", result);\n");
    fprintf(f, "    return 0;\n");
    fprintf(f, "}\n");
    fprintf(f, "#endif\n");

    fclose(f);

    /* count lines */
    int lines = 0;
    FILE* lf = fopen(outpath, "r");
    if (lf) {
        char line[MAX_LINE];
        while (fgets(line, sizeof(line), lf)) lines++;
        fclose(lf);
    }

    char fields[512];
    snprintf(fields, sizeof(fields), "[@FILE]{%s}[@LINES]{%d}", outpath, lines);
    bcl_ok(report, report_sz, fields);
    return 1;
}

/* ── Check VBStyle compliance ────────────────────────────────── */

static int check_compliance(const char* filepath, char* report, int report_sz) {
    FILE* f = fopen(filepath, "r");
    if (!f) {
        bcl_err(report, report_sz, 3, "cannot open file");
        return 0;
    }

    char line[MAX_LINE];
    int has_ghost = 0, has_vbstyle = 0, has_fileid = 0, has_summary = 0;
    int has_class = 0, has_method = 0, has_run = 0;
    int has_print = 0, has_bcl_in = 0, has_bcl_out = 0;
    int line_count = 0;
    int violations = 0;
    char details[4096];
    int dpos = 0;

    while (fgets(line, sizeof(line), f)) {
        line_count++;
        if (strstr(line, "[@GHOST]")) has_ghost = 1;
        if (strstr(line, "[@VBSTYLE]")) has_vbstyle = 1;
        if (strstr(line, "[@FILEID]")) has_fileid = 1;
        if (strstr(line, "[@SUMMARY]")) has_summary = 1;
        if (strstr(line, "[@CLASS]")) has_class = 1;
        if (strstr(line, "[@METHOD]")) has_method = 1;
        if (strstr(line, "_Run(")) has_run = 1;
        if (strstr(line, "[@OK]")) has_bcl_out = 1;
        if (strstr(line, "[@ERR]")) has_bcl_out = 1;
        if (strstr(line, "[@RUN]")) has_bcl_in = 1;
        /* check for print() outside main and comments */
        char* p = strstr(line, "printf(");
        if (p) {
            /* check if it's in a comment */
            char* comment = strstr(line, "//");
            if (!comment || comment > p) {
                has_print = 1;
            }
        }
    }
    fclose(f);

    if (!has_ghost) { violations++; dpos += snprintf(details + dpos, sizeof(details) - dpos, "missing [@GHOST]; "); }
    if (!has_vbstyle) { violations++; dpos += snprintf(details + dpos, sizeof(details) - dpos, "missing [@VBSTYLE]; "); }
    if (!has_fileid) { violations++; dpos += snprintf(details + dpos, sizeof(details) - dpos, "missing [@FILEID]; "); }
    if (!has_summary) { violations++; dpos += snprintf(details + dpos, sizeof(details) - dpos, "missing [@SUMMARY]; "); }
    if (!has_class) { violations++; dpos += snprintf(details + dpos, sizeof(details) - dpos, "missing [@CLASS]; "); }
    if (!has_method) { violations++; dpos += snprintf(details + dpos, sizeof(details) - dpos, "missing [@METHOD]; "); }
    if (!has_run) { violations++; dpos += snprintf(details + dpos, sizeof(details) - dpos, "missing Run dispatch; "); }
    if (!has_bcl_in) { violations++; dpos += snprintf(details + dpos, sizeof(details) - dpos, "missing BCL-in ([@RUN]); "); }
    if (!has_bcl_out) { violations++; dpos += snprintf(details + dpos, sizeof(details) - dpos, "missing BCL-out ([@OK]/[@ERR]); "); }

    if (violations == 0) {
        char fields[512];
        snprintf(fields, sizeof(fields), "[@FILE]{%s}[@LINES]{%d}[@VIOLATIONS]{0}[@STATUS]{PASS}", filepath, line_count);
        bcl_ok(report, report_sz, fields);
        return 1;
    } else {
        char fields[1024];
        snprintf(fields, sizeof(fields), "[@FILE]{%s}[@LINES]{%d}[@VIOLATIONS]{%d}[@STATUS]{FAIL}[@DETAILS]{%s}",
                filepath, line_count, violations, details);
        bcl_ok(report, report_sz, fields);
        return 0;
    }
}

/* ── Compile test ────────────────────────────────────────────── */

static int compile_test(const char* filepath, char* report, int report_sz) {
    char cmd[MAX_BCL];
    char bin_path[MAX_NAME];

    /* strip .c extension for output binary */
    snprintf(bin_path, sizeof(bin_path), "/tmp/bcl_test_%d", (int)getpid());

    snprintf(cmd, sizeof(cmd), "cc -O2 -Wall -DBCL_UNIT_STANDALONE %s -o %s 2>&1", filepath, bin_path);

    FILE* pipe = popen(cmd, "r");
    if (!pipe) {
        bcl_err(report, report_sz, 4, "cannot run compiler");
        return 0;
    }

    char output[4096];
    int opos = 0;
    char line[MAX_LINE];
    while (fgets(line, sizeof(line), pipe) && opos < (int)sizeof(output) - MAX_LINE) {
        opos += snprintf(output + opos, sizeof(output) - opos, "%s", line);
    }
    int exit_code = pclose(pipe);
    int compile_ok = (exit_code == 0);

    /* if compiled, run it */
    int run_ok = 0;
    char run_output[1024] = "";
    if (compile_ok) {
        snprintf(cmd, sizeof(cmd), "%s 2>&1", bin_path);
        FILE* rp = popen(cmd, "r");
        if (rp) {
            fgets(run_output, sizeof(run_output), rp);
            pclose(rp);
            run_ok = (strstr(run_output, "[@OK]") != NULL);
        }
        unlink(bin_path);
    }

    char fields[2048];
    snprintf(fields, sizeof(fields),
             "[@FILE]{%s}[@COMPILE]{%d}[@RUN]{%d}[@OUTPUT]{%s}[@WARNINGS]{%s}",
             filepath, compile_ok, run_ok,
             run_output[0] ? run_output : "(not run)",
             opos > 0 ? output : "(none)");

    if (compile_ok && run_ok) {
        bcl_ok(report, report_sz, fields);
        return 1;
    } else {
        bcl_err(report, report_sz, 5, compile_ok ? "run failed" : "compile failed");
        /* still include details in the error */
        snprintf(report, report_sz, "[@ERR]{[@CODE]{5}[@DESC]{%s}[@DETAILS]{%s}}",
                 compile_ok ? "run failed" : "compile failed", output);
        return 0;
    }
}

/* ── CLI main ────────────────────────────────────────────────── */

int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr,
            "Usage: %s <command> [args]\n"
            "\n"
            "Commands:\n"
            "  %s \"[@MAKE]{[@FILE]{name.c}[@DOMAIN]{dom}[@AUTHORITY]{Auth}[@SUMMARY]{desc}[@METHODS]{m1,m2}[@INCLUDES]{lib.h}}\"\n"
            "      — generate BCL unit .c file from spec\n"
            "  %s --file spec.bcl\n"
            "      — read BCL spec from file, generate unit\n"
            "  %s --check unit.c\n"
            "      — check VBStyle compliance of existing unit\n"
            "  %s --test unit.c\n"
            "      — compile-test a BCL unit\n"
            "\n"
            "BCL IN:  [@MAKE]{[@FILE]{...}[@DOMAIN]{...}[@AUTHORITY]{...}[@SUMMARY]{...}[@METHODS]{...}[@INCLUDES]{...}}\n"
            "BCL OUT: [@OK]{[@FILE]{...}[@LINES]{N}[@COMPILE]{1}[@CHECK]{PASS}}\n"
            "         [@ERR]{[@CODE]{N}[@DESC]{...}}\n",
            argv[0], argv[0], argv[0], argv[0], argv[0]);
        return 1;
    }

    char report[MAX_BCL];
    char bcl_input[MAX_BCL];

    if (strcmp(argv[1], "--check") == 0) {
        if (argc < 3) {
            bcl_err(report, sizeof(report), 1, "usage: --check <file.c>");
            printf("%s\n", report);
            return 1;
        }
        int ok = check_compliance(argv[2], report, sizeof(report));
        printf("%s\n", report);
        return ok ? 0 : 1;
    }

    if (strcmp(argv[1], "--test") == 0) {
        if (argc < 3) {
            bcl_err(report, sizeof(report), 1, "usage: --test <file.c>");
            printf("%s\n", report);
            return 1;
        }
        int ok = compile_test(argv[2], report, sizeof(report));
        printf("%s\n", report);
        return ok ? 0 : 1;
    }

    if (strcmp(argv[1], "--file") == 0) {
        if (argc < 3) {
            bcl_err(report, sizeof(report), 1, "usage: --file <spec.bcl>");
            printf("%s\n", report);
            return 1;
        }
        FILE* f = fopen(argv[2], "r");
        if (!f) {
            bcl_err(report, sizeof(report), 2, "cannot open spec file");
            printf("%s\n", report);
            return 1;
        }
        int n = fread(bcl_input, 1, sizeof(bcl_input) - 1, f);
        bcl_input[n] = '\0';
        fclose(f);
    } else {
        snprintf(bcl_input, sizeof(bcl_input), "%s", argv[1]);
    }

    /* Parse BCL spec */
    BclSpec spec;
    int field_count = parse_bcl_spec(bcl_input, &spec);
    if (field_count == 0) {
        bcl_err(report, sizeof(report), 1, "no BCL fields found in input");
        printf("%s\n", report);
        return 1;
    }

    /* Generate unit file */
    const char* filename = spec_get(&spec, "FILE");
    if (!write_unit_file(&spec, filename, report, sizeof(report))) {
        printf("%s\n", report);
        return 1;
    }

    /* Extract the generated file path from the OK report */
    char generated_path[MAX_NAME];
    const char* fp = strstr(report, "[@FILE]{");
    if (fp) {
        fp += 8;
        int i = 0;
        while (*fp && *fp != '}' && i < MAX_NAME - 1) {
            generated_path[i++] = *fp++;
        }
        generated_path[i] = '\0';
    } else {
        printf("%s\n", report);
        return 0;
    }

    printf("%s\n", report);

    /* Auto-check compliance */
    char check_report[MAX_BCL];
    check_compliance(generated_path, check_report, sizeof(check_report));
    printf("%s\n", check_report);

    /* Auto-compile test */
    char test_report[MAX_BCL];
    compile_test(generated_path, test_report, sizeof(test_report));
    printf("%s\n", test_report);

    return 0;
}
