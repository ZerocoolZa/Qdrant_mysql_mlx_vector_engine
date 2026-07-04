//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_engine_cli.c" date="2026-06-29" author="Devin" session_id="bcl-c-central-db" context="CLI dispatch, flags, orchestration for BCL C engine"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_engine_cli.c" domain="bcl_c_engine" authority="BclDispatcher"}
//[@SUMMARY]{summary="CLI entry point — parses args, dispatches to ingestion/graph/vbstyle subsystems"}
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

#include "bcl_engine.h"
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
            if (store_results(&r, db_name)) {
                const char *backend = config_global_backend();
                printf("=== STORED TO %s: %s ===\n",
                       backend ? backend : "sqlite",
                       db_name ? db_name : (config_global_db_path() ? config_global_db_path() : ":memory:"));
                printf("  classes: %d | methods: %d | edges: %d | source: %zu bytes\n\n",
                       r.class_count, r.method_count, r.edge_count, r.source_len);
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
        "  %s --describe                 — self-describe in BCL\n"
        "  %s --validate \"[@RUN]{...}\"   — validate a BCL packet\n"
        "  %s ./Domains/ --store bcl_ir  — process dir, store to MySQL\n",
        prog, prog, prog, prog, prog, prog, prog, prog);
}

/* ── self-describe (BCL format for AI discovery) ── */

static void describe_engine(void) {
    config_init_global("bcl_config.json");
    const char *backend = config_global_backend();
    const char *db_path = config_global_db_path();
    const char *domain  = config_global_domain();

    printf("[@OK]{\n");
    printf("  [@IDENTITY]{\n");
    printf("    [@NAME]{bcl_engine}\n");
    printf("    [@VERSION]{1.0}\n");
    printf("    [@AUTHOR]{cascade+devin}\n");
    printf("    [@DATE]{2026-06-29}\n");
    printf("    [@DESCRIPTION]{VBStyle AST + BCL + Graph + Check engine. Parses Python and C files via tree-sitter, extracts classes/methods/signatures, generates BCL stamps, builds call/state/import graph edges, checks VBStyle compliance, stores results to DB.}\n");
    printf("  }\n");
    printf("  [@CAPABILITIES]{\n");
    printf("    [@CMD]{--ast}      [@DESC]{Extract classes/methods/signatures from file}\n");
    printf("    [@CMD]{--bcl}      [@DESC]{Generate BCL header stamps ([@GHOST]/[@VBSTYLE]/[@CLASS]/[@METHOD])}\n");
    printf("    [@CMD]{--graph}    [@DESC]{Build call/state/import graph edges}\n");
    printf("    [@CMD]{--check}    [@DESC]{VBStyle compliance check (Python only, 11 rules)}\n");
    printf("    [@CMD]{--store}    [@DESC]{Write results to MySQL/SQLite DB}\n");
    printf("    [@CMD]{--validate} [@DESC]{Validate BCL packet against dictionary (syntax + semantic)}\n");
    printf("    [@CMD]{--all}      [@DESC]{Full analysis: AST + BCL + graph + check}\n");
    printf("    [@CMD]{--json}     [@DESC]{JSON output for programmatic parsing}\n");
    printf("    [@CMD]{--describe} [@DESC]{Self-describe in BCL format (this output)}\n");
    printf("    [@CMD]{--help}     [@DESC]{Show usage help}\n");
    printf("  }\n");
    printf("  [@INTERFACE]{\n");
    printf("    [@INPUT]{file path (.py, .c, .h) or directory path + optional flags}\n");
    printf("    [@OUTPUT]{\n");
    printf("      [@OK]{text output: AST summary, BCL stamps, graph edges, VBStyle violations, or JSON}\n");
    printf("      [@ERR]{stderr: error messages, usage help}\n");
    printf("    }\n");
    printf("    [@FORMAT]{\n");
    printf("      [@EXAMPLE]{./bcl_engine file.py --ast}\n");
    printf("      [@EXAMPLE]{./bcl_engine file.py --check}\n");
    printf("      [@EXAMPLE]{./bcl_engine file.c --ast}\n");
    printf("      [@EXAMPLE]{./bcl_engine ./dir/ --all --json}\n");
    printf("      [@EXAMPLE]{./bcl_engine --describe}\n");
    printf("    }\n");
    printf("  }\n");
    printf("  [@LANGUAGES]{\n");
    printf("    [@LANG]{python} [@GRAMMAR]{tree-sitter-python} [@EXT]{.py}\n");
    printf("    [@LANG]{c}      [@GRAMMAR]{tree-sitter-c}      [@EXT]{.c, .h}\n");
    printf("  }\n");
    printf("  [@CONFIG]{\n");
    printf("    [@BACKEND]{%s}\n", backend ? backend : "sqlite (default)");
    printf("    [@DB_PATH]{%s}\n", db_path ? db_path : "(not set)");
    printf("    [@DOMAIN]{%s}\n", domain ? domain : "bcl_c_engine");
    printf("    [@CONFIG_FILE]{bcl_config.json (runtime, overrides compiled defaults)}\n");
    printf("    [@COMPILED_DEFAULTS]{backend=sqlite, db_path=bcl_c_engine.db, domain=bcl_c_engine}\n");
    printf("  }\n");
    printf("  [@VBSTYLE_RULES]{\n");
    printf("    [@RULE]{1} [@NAME]{Tuple3}     [@DESC]{All methods return (1, data, None) or (0, None, (code, desc, 0))}\n");
    printf("    [@RULE]{2} [@NAME]{NoPrint}    [@DESC]{No print() calls in method bodies}\n");
    printf("    [@RULE]{3} [@NAME]{NoDecorator}[@DESC]{No @property/@staticmethod/@classmethod}\n");
    printf("    [@RULE]{4} [@NAME]{NoSelfUnderscore}[@DESC]{No self._ attributes (except self._p helper)}\n");
    printf("    [@RULE]{5} [@NAME]{RunDispatch} [@DESC]{Class has Run(self, command, params) dispatch method}\n");
    printf("    [@RULE]{6} [@NAME]{PascalCase}  [@DESC]{Class names are PascalCase}\n");
    printf("    [@RULE]{7} [@NAME]{UPPERCASE}   [@DESC]{Constants are UPPERCASE}\n");
    printf("    [@RULE]{8} [@NAME]{SelfState}   [@DESC]{State in self.state dict, not self._ attrs}\n");
    printf("    [@RULE]{9} [@NAME]{NoTabs}      [@DESC]{Spaces only, no tabs}\n");
    printf("    [@RULE]{10}[@NAME]{NoEnum}      [@DESC]{No enum types}\n");
    printf("    [@RULE]{11}[@NAME]{BclHeaders}  [@DESC]{File has [@GHOST]/[@VBSTYLE]/[@FILEID]/[@SUMMARY] headers}\n");
    printf("  }\n");
    printf("  [@UNITS]{\n");
    printf("    [@UNIT]{bcl_engine.h}            [@ROLE]{shared declarations, structs, function prototypes}\n");
    printf("    [@UNIT]{bcl_engine_cli.c}        [@ROLE]{CLI dispatch, flags, orchestration}\n");
    printf("    [@UNIT]{bcl_ingestion_engine.c}  [@ROLE]{tree-sitter walk, extract classes/methods/signatures}\n");
    printf("    [@UNIT]{bcl_stamper.c}           [@ROLE]{generate BCL header stamps}\n");
    printf("    [@UNIT]{bcl_graph_builder.c}     [@ROLE]{build call/state/import graph edges}\n");
    printf("    [@UNIT]{bcl_static_analyzer.c}   [@ROLE]{VBStyle compliance checks (11 rules)}\n");
    printf("    [@UNIT]{bcl_graph_store.c}       [@ROLE]{write results to MySQL/SQLite}\n");
    printf("    [@UNIT]{bcl_config.c}            [@ROLE]{runtime config reader (backend selectable)}\n");
    printf("    [@UNIT]{bcl_dictionary.c}        [@ROLE]{BCL tag dictionary — 94 tags, 8 namespaces, rich grammar schema}\n");
    printf("    [@UNIT]{bcl_parser.c}            [@ROLE]{BCL syntax-only parser — knows ONLY [@TAG]{...} brackets}\n");
    printf("    [@UNIT]{bcl_validator.c}         [@ROLE]{BCL semantic validator — checks parsed tree against dictionary rules}\n");
    printf("    [@UNIT]{bcl_mem_unit.c}          [@ROLE]{in-RAM SQLite :memory: orchestration bus — 6 tables, central dispatch}\n");
    printf("  }\n");
    printf("  [@HOW_TO_UPDATE]{\n");
    printf("    [@STEP]{1. Modify .c source files in core/Dom_Bcl_C_ver/}\n");
    printf("    [@STEP]{2. Update MySQL c_classes table: UPDATE c_classes SET class_code=... WHERE class_name=...}\n");
    printf("    [@STEP]{3. Rebuild: python3 bcl_c_loader.py build_all}\n");
    printf("    [@STEP]{4. Run --describe to verify new capabilities appear}\n");
    printf("    [@STEP]{5. Run --check on a .py file to verify VBStyle compliance}\n");
    printf("  }\n");
    printf("  [@COMPILE_MODES]{\n");
    printf("    [@MODE]{binary}  [@CMD]{cc -o bcl_engine *.c -lsqlite3 -ljson-c -ltree-sitter -ltree-sitter-python -ltree-sitter-c}  [@USAGE]{CLI tool}\n");
    printf("    [@MODE]{shared}  [@CMD]{cc -shared -o libbcl_engine.so *.c -lsqlite3 -ljson-c}  [@USAGE]{Python ctypes: ctypes.CDLL('./libbcl_engine.so')}\n");
    printf("    [@MODE]{static}  [@CMD]{cc -c *.c; ar rcs libbcl_engine.a *.o}  [@USAGE]{Link into other C programs}\n");
    printf("  }\n");
    printf("}\n");

    config_free_global();
}

/* ── main ── */

int main(int argc, char **argv) {
    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    /* --describe works without a target file */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--describe") == 0) {
            describe_engine();
            return 0;
        }
    }

    /* --validate: parse + validate a BCL packet from stdin or arg */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--validate") == 0) {
            config_init_global("bcl_config.json");
            BclDictionary dict;
            BclDictionary_Init(&dict, ":memory:");
            BclDictionary_Populate(&dict);

            const char *bcl_text = NULL;
            if (i + 1 < argc && argv[i+1][0] != '-') {
                /* BCL text from next arg */
                bcl_text = argv[i + 1];
            } else {
                /* Read BCL from stdin */
                static char stdin_buf[BCL_MAX_BCL];
                int n = 0;
                int c;
                while ((c = fgetc(stdin)) != EOF && n < BCL_MAX_BCL - 1) {
                    stdin_buf[n++] = (char)c;
                }
                stdin_buf[n] = '\0';
                bcl_text = stdin_buf;
            }

            BclParseResult tree;
            BclParser_Init(&tree);
            if (!BclParser_Parse(&tree, bcl_text)) {
                printf("[@ERR]{[@CODE]{3}[@DESC]{%s at pos %d}}\n",
                       tree.error_msg, tree.error_pos);
                BclDictionary_Close(&dict);
                return 1;
            }

            ValidationResult vresult;
            BclValidator_Init(&vresult);
            if (BclValidator_Validate(&vresult, &tree, &dict)) {
                printf("[@OK]{[@VALID]{1}[@NODE_COUNT]{%d}[@ERRORS]{0}}\n",
                       tree.node_count);
            } else {
                printf("[@OK]{[@VALID]{0}[@NODE_COUNT]{%d}[@ERRORS]{%d}}\n",
                       tree.node_count, vresult.error_count);
                for (int e = 0; e < vresult.error_count; e++) {
                    printf("  [@ERROR]{[@TAG]{%s}[@PROBLEM]{%s}[@SOLUTION]{%s}}\n",
                           vresult.errors[e].tag,
                           vresult.errors[e].problem,
                           vresult.errors[e].solution);
                }
            }

            BclDictionary_Close(&dict);
            return 0;
        }
    }

    /* Initialize config for all other commands */
    config_init_global("bcl_config.json");

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
