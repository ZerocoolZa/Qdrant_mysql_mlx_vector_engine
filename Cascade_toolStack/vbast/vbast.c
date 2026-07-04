//[@GHOST]{file_path="Cascade_toolStack/vbast/vbast.c" date="2026-06-29" author="Devin" session_id="vbast-bcl-stamp" context="CLI dispatch, flags, orchestration for VBAST tool"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="vbast.c" domain="vbast" authority="VbastDispatcher"}
//[@SUMMARY]{summary="CLI entry point — parses args, dispatches to ast/bcl/graph/vbstyle/store subsystems"}
//[@CLASS]{class="VbastDispatcher" domain="vbast" authority="single"}
//[@METHOD]{methods="main,dispatch,print_json,print_summary,process_file,process_dir"}
//
// vbast.c — CLI dispatch, flags, orchestration
//
// VBAST = VBStyle AST + BCL + Graph + Check
//
// Uses tree-sitter-python to parse Python files into a real AST,
// then extracts classes/methods/signatures, generates BCL stamps,
// builds call/state/import graph edges, checks VBStyle compliance,
// and optionally stores results to MySQL bcl_ir tables.
//
// Usage:
//   vbast <file.py>                  — full analysis (AST + BCL + graph + check)
//   vbast <file.py> --ast            — extract classes/methods/signatures
//   vbast <file.py> --bcl            — generate BCL header stamps
//   vbast <file.py> --graph          — build call/state/import edges
//   vbast <file.py> --check          — VBStyle compliance check
//   vbast <file.py> --store <db>     — write to MySQL bcl_ir tables
//   vbast <file.py> --all            — everything (default)
//   vbast <file.py> --json           — JSON output
//   vbast <dir>                      — process all .py files in directory
//
// Compile: see Makefile

#include "vbast.h"
#include <dirent.h>
#include <sys/stat.h>
#include <time.h>

/* ── file reading ── */

char *read_file(const char *path, char *buf, size_t bufsize) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    size_t n = fread(buf, 1, bufsize - 1, f);
    buf[n] = '\0';
    fclose(f);
    return buf;
}

int line_for_offset(const char *content, int offset) {
    int line = 1;
    for (int i = 0; i < offset && content[i]; i++) {
        if (content[i] == '\n') line++;
    }
    return line;
}

void trim(char *s) {
    size_t len = strlen(s);
    while (len > 0 && isspace((unsigned char)s[len-1])) s[--len] = '\0';
    size_t start = 0;
    while (s[start] && isspace((unsigned char)s[start])) start++;
    if (start > 0) memmove(s, s + start, len - start + 1);
}

/* ── process a single file ── */

static void process_file(const char *path, int do_ast, int do_bcl,
                         int do_graph, int do_check, int do_store,
                         const char *db_name, int json_mode) {
    ParseResult r;
    ast_init(&r, path);

    if (!ast_parse_file(&r)) {
        ast_free(&r);
        return;
    }

    if (do_graph) {
        graph_build_edges(&r);
    }

    if (do_check) {
        /* skip VBStyle checks for C files — Python-specific rules */
        if (r.language == LANG_C) {
            r.violation_count = 0;
        } else {
            check_vbstyle(&r);
        }
    }

    /* output */
    if (json_mode) {
        printf("{\"file\":\"%s\",\"classes\":%d,\"methods\":%d,\"edges\":%d,\"violations\":%d}\n",
               path, r.class_count, r.method_count, r.edge_count, r.violation_count);
    } else {
        if (do_ast) {
            ast_print(&r);
        }
        if (do_graph) {
            graph_print(&r);
        }
        if (do_bcl) {
            char stamps[8192];
            bcl_stamp_all(&r, stamps, sizeof(stamps));
            printf("=== BCL STAMPS ===\n%s\n", stamps);
        }
        if (do_check) {
            printf("=== VBSTYLE CHECK ===\n");
            if (r.violation_count == 0) {
                printf("  ALL CHECKS PASSED — VBStyle compliant\n\n");
            } else {
                check_print_violations(&r);
            }
        }
        if (do_store) {
            if (mysql_store_results(&r, db_name)) {
                printf("=== STORED TO MYSQL: %s ===\n", db_name ? db_name : "bcl_ir");
                printf("  classes: %d | methods: %d | edges: %d\n\n",
                       r.class_count, r.method_count, r.edge_count);
            }
        }
    }

    ast_free(&r);
}

/* ── process a directory ── */

static void process_dir(const char *dirpath, int do_ast, int do_bcl,
                        int do_graph, int do_check, int do_store,
                        const char *db_name, int json_mode) {
    DIR *d = opendir(dirpath);
    if (!d) {
        fprintf(stderr, "ERROR: cannot open dir %s\n", dirpath);
        return;
    }
    struct dirent *entry;
    while ((entry = readdir(d)) != NULL) {
        if (entry->d_name[0] == '.') continue;
        size_t len = strlen(entry->d_name);
        /* accept .py, .c, and .h files */
        int is_py = (len >= 3 && strcmp(entry->d_name + len - 3, ".py") == 0);
        int is_c  = (len >= 2 && strcmp(entry->d_name + len - 2, ".c") == 0);
        int is_h  = (len >= 2 && strcmp(entry->d_name + len - 2, ".h") == 0);
        if (!is_py && !is_c && !is_h) continue;
        char full[1024];
        snprintf(full, sizeof(full), "%s/%s", dirpath, entry->d_name);
        process_file(full, do_ast, do_bcl, do_graph, do_check, do_store, db_name, json_mode);
    }
    closedir(d);
}

/* ── usage ── */

static void usage(const char *prog) {
    fprintf(stderr,
        "vbast v1.0 — VBStyle AST + BCL + Graph + Check (tree-sitter-python + tree-sitter-c)\n\n"
        "Usage: %s <file.py|file.c|file.h|dir> [options]\n\n"
        "Modes:\n"
        "  (default)         Full analysis: AST + BCL + graph + check\n"
        "  --ast             Extract classes/methods/signatures only\n"
        "  --bcl             Generate BCL header stamps only\n"
        "  --graph           Build call/state/import edges only\n"
        "  --check           VBStyle compliance check only (Python)\n"
        "  --store <db>      Write results to MySQL database\n"
        "  --all             Everything (same as default)\n\n"
        "Output:\n"
        "  --json            JSON output for programmatic parsing\n\n"
        "Languages:\n"
        "  .py  → Python (tree-sitter-python)\n"
        "  .c   → C (tree-sitter-c)\n"
        "  .h   → C (tree-sitter-c)\n\n"
        "Examples:\n"
        "  %s dom_system.py              — full analysis\n"
        "  %s dom_system.py --check      — just VBStyle check\n"
        "  %s BclDispatcher.c --ast      — extract C functions\n"
        "  %s dom_system.py --ast --json — AST as JSON\n"
        "  %s ./Domains/ --store bcl_ir  — process dir, store to MySQL\n",
        prog, prog, prog, prog, prog, prog);
}

/* ── main ── */

int main(int argc, char **argv) {
    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    const char *target = NULL;
    int do_ast = 0, do_bcl = 0, do_graph = 0, do_check = 0, do_store = 0;
    int do_all = 0, json_mode = 0;
    const char *db_name = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--ast") == 0) do_ast = 1;
        else if (strcmp(argv[i], "--bcl") == 0) do_bcl = 1;
        else if (strcmp(argv[i], "--graph") == 0) do_graph = 1;
        else if (strcmp(argv[i], "--check") == 0) do_check = 1;
        else if (strcmp(argv[i], "--all") == 0) do_all = 1;
        else if (strcmp(argv[i], "--json") == 0) json_mode = 1;
        else if (strcmp(argv[i], "--store") == 0) {
            do_store = 1;
            if (i + 1 < argc && argv[i+1][0] != '-') {
                db_name = argv[++i];
            }
        }
        else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            usage(argv[0]);
            return 0;
        }
        else if (argv[i][0] != '-') {
            target = argv[i];
        }
    }

    if (!target) {
        usage(argv[0]);
        return 1;
    }

    /* if no modes selected, do all */
    if (!do_ast && !do_bcl && !do_graph && !do_check && !do_store && !do_all) {
        do_all = 1;
    }
    if (do_all) {
        do_ast = 1; do_bcl = 1; do_graph = 1; do_check = 1;
    }
    /* --store needs graph edges to be built */
    if (do_store) {
        do_graph = 1;
    }

    /* check if target is file or directory */
    struct stat st;
    if (stat(target, &st) != 0) {
        fprintf(stderr, "ERROR: cannot stat %s\n", target);
        return 1;
    }

    if (S_ISDIR(st.st_mode)) {
        process_dir(target, do_ast, do_bcl, do_graph, do_check, do_store, db_name, json_mode);
    } else {
        process_file(target, do_ast, do_bcl, do_graph, do_check, do_store, db_name, json_mode);
    }

    return 0;
}
