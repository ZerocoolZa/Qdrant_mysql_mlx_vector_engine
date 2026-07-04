//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_ingestion_engine.c" date="2026-06-29" author="Devin" session_id="bcl-c-central-db" context="Tree-sitter walk, extract classes/methods/signatures from Python source"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_ingestion_engine.c" domain="bcl_c_engine" authority="IngestionEngine"}
//[@SUMMARY]{summary="AST walker — tree-sitter parse, extract classes/methods/imports from Python source"}
//
// Uses tree-sitter-python to parse Python source into a real AST.
// Walks the tree and populates ParseResult with:
//   - classes (name, bases, line range, flags)
//   - methods (name, class, signature, line range, flags)
//   - imports (module, alias, line)
//
// No string guessing. No regex. Real syntax tree.

#include "bcl_engine.h"

/* ── helpers ── */

static char *node_text(TSNode node, const char *source) {
    uint32_t start = ts_node_start_byte(node);
    uint32_t end = ts_node_end_byte(node);
    uint32_t len = end - start;
    static char buf[VBAST_MAX_SIG];
    if (len >= VBAST_MAX_SIG) len = VBAST_MAX_SIG - 1;
    memcpy(buf, source + start, len);
    buf[len] = '\0';
    return buf;
}

static int node_line(TSNode node) {
    return (int)ts_node_start_point(node).row + 1;
}

static int node_end_line(TSNode node) {
    return (int)ts_node_end_point(node).row + 1;
}

/* ════════════════════════════════════════════
 * LANGUAGE DETECTION
 * ════════════════════════════════════════════ */

Language detect_language(const char *file_path) {
    const char *ext = strrchr(file_path, '.');
    if (!ext) return LANG_UNKNOWN;
    if (strcmp(ext, ".py") == 0) return LANG_PYTHON;
    if (strcmp(ext, ".c") == 0 || strcmp(ext, ".h") == 0) return LANG_C;
    return LANG_UNKNOWN;
}

/* ════════════════════════════════════════════
 * C AST WALKER HELPERS
 * ════════════════════════════════════════════ */

/* ── extract parameters from a C function_definition ──
 * C grammar nests: function_definition → function_declarator → parameter_list
 * Extracts text of parameter_list, stripping outer parens.
 * Example output: "BclDictionary *d, const char *tag" */

static void extract_c_params(TSNode func_node, const char *source, char *out, size_t out_sz) {
    out[0] = '\0';
    /* find function_declarator child */
    uint32_t count = ts_node_named_child_count(func_node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(func_node, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "function_declarator") == 0) {
            /* find parameter_list child of function_declarator */
            uint32_t dcount = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < dcount; j++) {
                TSNode dchild = ts_node_named_child(child, j);
                const char *dtype = ts_node_type(dchild);
                if (strcmp(dtype, "parameter_list") == 0) {
                    char *txt = node_text(dchild, source);
                    /* strip outer parens */
                    char *inner = txt;
                    if (inner[0] == '(') inner++;
                    size_t len = strlen(inner);
                    while (len > 0 && (inner[len-1] == ')' || inner[len-1] == ' ')) {
                        inner[--len] = '\0';
                    }
                    strncpy(out, inner, out_sz - 1);
                    out[out_sz - 1] = '\0';
                    return;
                }
            }
            return;
        }
    }
}

/* ── walk a C tree-sitter AST and populate ParseResult ──
 * Extracts:
 *   - preproc_include  → imports (strip quotes/angle brackets)
 *   - function_definition → methods (module-level, no class)
 *   - struct_specifier → classes (skip anonymous structs)
 *   - type_definition  → classes (if it names a struct) */

static void walk_c_ast(ParseResult *r, TSTree *tree) {
    TSNode root = ts_tree_root_node(tree);
    uint32_t count = ts_node_named_child_count(root);

    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(root, i);
        const char *type = ts_node_type(child);

        /* A. C includes (as imports) */
        if (strcmp(type, "preproc_include") == 0) {
            if (r->import_count >= VBAST_MAX_IMPORTS) continue;
            ImportInfo *imp = &r->imports[r->import_count];
            memset(imp, 0, sizeof(ImportInfo));
            imp->line_number = node_line(child);

            /* find string_literal or system_lib_string child */
            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(child, j);
                const char *mtype = ts_node_type(mc);
                if (strcmp(mtype, "string_literal") == 0 ||
                    strcmp(mtype, "system_lib_string") == 0) {
                    char *txt = node_text(mc, r->source);
                    /* strip surrounding quotes or angle brackets */
                    char *path = txt;
                    size_t plen = strlen(path);
                    if (plen >= 2) {
                        if (path[0] == '"' && path[plen-1] == '"') {
                            path++;
                            path[plen - 2] = '\0';
                        } else if (path[0] == '<' && path[plen-1] == '>') {
                            path++;
                            path[plen - 2] = '\0';
                        }
                    }
                    strncpy(imp->module, path, VBAST_MAX_NAME - 1);
                    imp->module[VBAST_MAX_NAME - 1] = '\0';
                    break;
                }
            }
            r->import_count++;
        }

        /* B. C functions (as methods) */
        else if (strcmp(type, "function_definition") == 0) {
            if (r->method_count >= VBAST_MAX_METHODS) continue;
            MethodInfo *m = &r->methods[r->method_count];
            memset(m, 0, sizeof(MethodInfo));

            /* find function_declarator → identifier (the name) */
            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(mc), "function_declarator") == 0) {
                    uint32_t dc = ts_node_named_child_count(mc);
                    for (uint32_t k = 0; k < dc; k++) {
                        TSNode dn = ts_node_named_child(mc, k);
                        if (strcmp(ts_node_type(dn), "identifier") == 0) {
                            strncpy(m->name, node_text(dn, r->source), VBAST_MAX_NAME - 1);
                            m->name[VBAST_MAX_NAME - 1] = '\0';
                            break;
                        }
                    }
                    break;
                }
            }

            /* C functions are module-level, no class */
            m->class_name[0] = '\0';
            m->line_start = node_line(child);
            m->line_end = node_end_line(child);
            extract_c_params(child, r->source, m->signature, VBAST_MAX_SIG);
            m->has_tuple3 = 0;
            m->has_print = 0;
            r->method_count++;
        }

        /* C. C structs (as classes) */
        else if (strcmp(type, "struct_specifier") == 0) {
            if (r->class_count >= VBAST_MAX_CLASSES) continue;

            /* find identifier child (struct name) — skip anonymous structs */
            char struct_name[VBAST_MAX_NAME];
            struct_name[0] = '\0';
            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(mc), "identifier") == 0) {
                    strncpy(struct_name, node_text(mc, r->source), VBAST_MAX_NAME - 1);
                    struct_name[VBAST_MAX_NAME - 1] = '\0';
                    break;
                }
            }
            if (struct_name[0] == '\0') continue; /* anonymous struct */

            ClassInfo *c = &r->classes[r->class_count];
            memset(c, 0, sizeof(ClassInfo));
            strncpy(c->name, struct_name, VBAST_MAX_NAME - 1);
            c->name[VBAST_MAX_NAME - 1] = '\0';
            c->bases[0] = '\0'; /* no inheritance in C */
            c->line_start = node_line(child);
            c->line_end = node_end_line(child);
            r->class_count++;
        }

        /* D. C typedefs (as classes if they name a struct) */
        else if (strcmp(type, "type_definition") == 0) {
            if (r->class_count >= VBAST_MAX_CLASSES) continue;

            /* typedef name = first identifier child */
            char typedef_name[VBAST_MAX_NAME];
            typedef_name[0] = '\0';

            /* check for struct_specifier child with an identifier */
            int has_named_struct = 0;
            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(child, j);
                const char *mtype = ts_node_type(mc);
                if (strcmp(mtype, "struct_specifier") == 0) {
                    uint32_t sc = ts_node_named_child_count(mc);
                    for (uint32_t k = 0; k < sc; k++) {
                        TSNode sn = ts_node_named_child(mc, k);
                        if (strcmp(ts_node_type(sn), "identifier") == 0) {
                            has_named_struct = 1;
                            break;
                        }
                    }
                }
                if (strcmp(mtype, "identifier") == 0 && typedef_name[0] == '\0') {
                    strncpy(typedef_name, node_text(mc, r->source), VBAST_MAX_NAME - 1);
                    typedef_name[VBAST_MAX_NAME - 1] = '\0';
                }
            }

            if (!has_named_struct || typedef_name[0] == '\0') continue;

            ClassInfo *c = &r->classes[r->class_count];
            memset(c, 0, sizeof(ClassInfo));
            strncpy(c->name, typedef_name, VBAST_MAX_NAME - 1);
            c->name[VBAST_MAX_NAME - 1] = '\0';
            c->bases[0] = '\0';
            c->line_start = node_line(child);
            c->line_end = node_end_line(child);
            r->class_count++;
        }
    }
}

/* ── extract parameters from a function_definition ── */

static void extract_params(TSNode func_node, const char *source, char *out, size_t out_sz) {
    out[0] = '\0';
    /* find parameters child */
    uint32_t count = ts_node_named_child_count(func_node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(func_node, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "parameters") == 0) {
            char *txt = node_text(child, source);
            /* strip outer parens */
            char *inner = txt;
            if (inner[0] == '(') inner++;
            size_t len = strlen(inner);
            while (len > 0 && (inner[len-1] == ')' || inner[len-1] == ' ')) {
                inner[--len] = '\0';
            }
            strncpy(out, inner, out_sz - 1);
            out[out_sz - 1] = '\0';
            return;
        }
    }
}

/* ── extract base classes from a class_definition ── */

static void extract_bases(TSNode class_node, const char *source, char *out, size_t out_sz) {
    out[0] = '\0';
    uint32_t count = ts_node_named_child_count(class_node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(class_node, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "argument_list") == 0) {
            char *txt = node_text(child, source);
            /* strip outer parens */
            char *inner = txt;
            if (inner[0] == '(') inner++;
            size_t len = strlen(inner);
            while (len > 0 && inner[len-1] == ')') inner[--len] = '\0';
            strncpy(out, inner, out_sz - 1);
            out[out_sz - 1] = '\0';
            return;
        }
    }
}

/* ── check if method body contains a Tuple3 return ── */

static int has_tuple3_return(TSNode body, const char *source) {
    /* walk the body looking for return_statement with tuple */
    uint32_t count = ts_node_named_child_count(body);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(body, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "return_statement") == 0) {
            /* check if it returns a tuple */
            uint32_t rc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < rc; j++) {
                TSNode ret_val = ts_node_named_child(child, j);
                const char *rt = ts_node_type(ret_val);
                if (strcmp(rt, "tuple") == 0) {
                    return 1;
                }
            }
        }
        /* recurse into nested blocks (if/for/while/try) */
        if (strcmp(type, "if_statement") == 0 || strcmp(type, "for_statement") == 0 ||
            strcmp(type, "while_statement") == 0 || strcmp(type, "try_statement") == 0 ||
            strcmp(type, "with_statement") == 0) {
            /* find the block/consequence */
            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t k = 0; k < cc; k++) {
                TSNode sub = ts_node_named_child(child, k);
                const char *st = ts_node_type(sub);
                if (strcmp(st, "block") == 0) {
                    if (has_tuple3_return(sub, source)) return 1;
                }
            }
        }
    }
    return 0;
}

/* ── check if method body contains print() ── */

static int has_print_call(TSNode body, const char *source) {
    uint32_t count = ts_node_named_child_count(body);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(body, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "expression_statement") == 0) {
            uint32_t ec = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < ec; j++) {
                TSNode expr = ts_node_named_child(child, j);
                const char *et = ts_node_type(expr);
                if (strcmp(et, "call") == 0) {
                    TSNode func = ts_node_named_child(expr, 0);
                    char *fname = node_text(func, source);
                    if (strcmp(fname, "print") == 0) return 1;
                }
            }
        }
        /* recurse */
        if (strcmp(type, "if_statement") == 0 || strcmp(type, "for_statement") == 0 ||
            strcmp(type, "while_statement") == 0 || strcmp(type, "try_statement") == 0 ||
            strcmp(type, "with_statement") == 0) {
            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t k = 0; k < cc; k++) {
                TSNode sub = ts_node_named_child(child, k);
                if (strcmp(ts_node_type(sub), "block") == 0) {
                    if (has_print_call(sub, source)) return 1;
                }
            }
        }
    }
    return 0;
}

/* ── check for decorators on a function or class ── */

static int has_decorator(TSNode node) {
    uint32_t count = ts_node_named_child_count(node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(node, i);
        if (strcmp(ts_node_type(child), "decorator") == 0) return 1;
    }
    return 0;
}

/* ── check for type hints in parameters ── */

static int has_type_hints(TSNode func_node, const char *source) {
    uint32_t count = ts_node_named_child_count(func_node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(func_node, i);
        if (strcmp(ts_node_type(child), "parameters") == 0) {
            uint32_t pc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < pc; j++) {
                TSNode param = ts_node_named_child(child, j);
                const char *pt = ts_node_type(param);
                if (strcmp(pt, "typed_parameter") == 0 ||
                    strcmp(pt, "typed_default_parameter") == 0) {
                    return 1;
                }
            }
        }
        /* check return type */
        if (strcmp(ts_node_type(child), "type") == 0) return 1;
    }
    return 0;
}

/* ── extract nested functions defined inside a method/function body ── */

static void extract_nested_functions(TSNode body, const char *source,
                                     const char *class_name, ParseResult *r) {
    uint32_t count = ts_node_named_child_count(body);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(body, i);
        const char *type = ts_node_type(child);

        if (strcmp(type, "function_definition") != 0 &&
            strcmp(type, "decorated_definition") != 0) {
            continue;
        }

        TSNode func_node = child;
        int nested_decorated = 0;
        if (strcmp(type, "decorated_definition") == 0) {
            nested_decorated = 1;
            int found_func = 0;
            uint32_t dc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < dc; j++) {
                TSNode dn = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(dn), "function_definition") == 0) {
                    func_node = dn;
                    found_func = 1;
                    break;
                }
            }
            if (!found_func) continue;
        }

        if (r->method_count >= VBAST_MAX_METHODS) continue;
        MethodInfo *m = &r->methods[r->method_count];
        memset(m, 0, sizeof(MethodInfo));
        m->has_decorator = nested_decorated;

        uint32_t cc = ts_node_named_child_count(func_node);
        for (uint32_t j = 0; j < cc; j++) {
            TSNode mc = ts_node_named_child(func_node, j);
            if (strcmp(ts_node_type(mc), "identifier") == 0 && m->name[0] == '\0') {
                strncpy(m->name, node_text(mc, source), VBAST_MAX_NAME - 1);
                break;
            }
        }

        strncpy(m->class_name, class_name, VBAST_MAX_NAME - 1);
        m->line_start = node_line(func_node);
        m->line_end = node_end_line(func_node);
        extract_params(func_node, source, m->signature, VBAST_MAX_SIG);
        m->has_type_hint = has_type_hints(func_node, source);
        m->is_async = 0;

        /* find body: check tuple3/print, then recurse for deeper nesting */
        for (uint32_t j = 0; j < cc; j++) {
            TSNode mc = ts_node_named_child(func_node, j);
            if (strcmp(ts_node_type(mc), "block") == 0) {
                m->has_tuple3 = has_tuple3_return(mc, source);
                m->has_print = has_print_call(mc, source);
                extract_nested_functions(mc, source, class_name, r);
                break;
            }
        }

        r->method_count++;
    }
}

/* ── walk a class body for methods ── */

static void walk_class_body(TSNode body, const char *source, const char *class_name,
                            ParseResult *r) {
    uint32_t count = ts_node_named_child_count(body);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(body, i);
        const char *type = ts_node_type(child);

        if (strcmp(type, "function_definition") == 0 ||
            strcmp(type, "decorated_definition") == 0) {
            TSNode func_node = child;
            int meth_decorated = 0;
            if (strcmp(type, "decorated_definition") == 0) {
                meth_decorated = 1;
                int found_func = 0;
                uint32_t dc = ts_node_named_child_count(child);
                for (uint32_t j = 0; j < dc; j++) {
                    TSNode dn = ts_node_named_child(child, j);
                    if (strcmp(ts_node_type(dn), "function_definition") == 0) {
                        func_node = dn;
                        found_func = 1;
                        break;
                    }
                }
                if (!found_func) continue;
            }

            if (r->method_count >= VBAST_MAX_METHODS) continue;
            MethodInfo *m = &r->methods[r->method_count];
            memset(m, 0, sizeof(MethodInfo));
            m->has_decorator = meth_decorated;

            /* method name */
            uint32_t cc = ts_node_named_child_count(func_node);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(func_node, j);
                if (strcmp(ts_node_type(mc), "identifier") == 0 && m->name[0] == '\0') {
                    strncpy(m->name, node_text(mc, source), VBAST_MAX_NAME - 1);
                    break;
                }
            }

            strncpy(m->class_name, class_name, VBAST_MAX_NAME - 1);
            m->line_start = node_line(func_node);
            m->line_end = node_end_line(func_node);
            extract_params(func_node, source, m->signature, VBAST_MAX_SIG);
            m->has_type_hint = has_type_hints(func_node, source);
            m->is_async = 0;

            /* find body and check for tuple3 + print, then walk nested funcs */
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(func_node, j);
                if (strcmp(ts_node_type(mc), "block") == 0) {
                    m->has_tuple3 = has_tuple3_return(mc, source);
                    m->has_print = has_print_call(mc, source);
                    extract_nested_functions(mc, source, class_name, r);
                    break;
                }
            }

            /* update class flags */
            if (strcmp(m->name, "Run") == 0) {
                r->classes[r->class_count - 1].has_run = 1;
            }

            r->method_count++;
        }
        /* nested class (may be decorated) */
        else if (strcmp(type, "class_definition") == 0 ||
                 strcmp(type, "decorated_definition") == 0) {
            TSNode class_node = child;
            int is_decorated = 0;
            if (strcmp(type, "decorated_definition") == 0) {
                is_decorated = 1;
                int found_class = 0;
                uint32_t dc = ts_node_named_child_count(child);
                for (uint32_t j = 0; j < dc; j++) {
                    TSNode dn = ts_node_named_child(child, j);
                    if (strcmp(ts_node_type(dn), "class_definition") == 0) {
                        class_node = dn;
                        found_class = 1;
                        break;
                    }
                }
                if (!found_class) continue;
            }

            if (r->class_count >= VBAST_MAX_CLASSES) continue;
            ClassInfo *c = &r->classes[r->class_count];
            memset(c, 0, sizeof(ClassInfo));
            c->has_decorator = is_decorated;

            uint32_t cc = ts_node_named_child_count(class_node);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(class_node, j);
                if (strcmp(ts_node_type(mc), "identifier") == 0 && c->name[0] == '\0') {
                    strncpy(c->name, node_text(mc, source), VBAST_MAX_NAME - 1);
                    break;
                }
            }
            extract_bases(class_node, source, c->bases, VBAST_MAX_SIG);
            c->line_start = node_line(class_node);
            c->line_end = node_end_line(class_node);
            r->class_count++;

            /* find body */
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(class_node, j);
                if (strcmp(ts_node_type(mc), "block") == 0) {
                    walk_class_body(mc, source, c->name, r);
                    break;
                }
            }
        }
    }
}

/* ── check for GHOST/VBSTYLE tags in comments ── */

static void check_tags(ParseResult *r) {
    const char *src = r->source;
    if (!src) return;
    /* check first 2000 chars for tags */
    size_t check_len = r->source_len < 2000 ? r->source_len : 2000;
    char head[2048];
    memcpy(head, src, check_len);
    head[check_len] = '\0';

    if (strstr(head, "@GHOST") || strstr(head, "[@GHOST]")) {
        if (r->class_count > 0) r->classes[0].has_ghost = 1;
    }
    if (strstr(head, "@VBSTYLE") || strstr(head, "[@VBSTYLE]")) {
        if (r->class_count > 0) r->classes[0].has_vbstyle = 1;
    }
}

/* ════════════════════════════════════════════
 * PUBLIC API
 * ════════════════════════════════════════════ */

void ast_init(ParseResult *r, const char *file_path) {
    memset(r, 0, sizeof(ParseResult));
    strncpy(r->file_path, file_path, VBAST_MAX_LINE - 1);
    r->source = NULL;
    r->source_len = 0;
}

int ast_parse_file(ParseResult *r) {
    static char buf[VBAST_MAXBUF];
    char *content = read_file(r->file_path, buf, sizeof(buf));
    if (!content) {
        fprintf(stderr, "ERROR: cannot read %s\n", r->file_path);
        return 0;
    }
    r->source = strdup(content);
    r->source_len = strlen(content);

    /* dispatch by detected language */
    r->language = detect_language(r->file_path);
    const TSLanguage *lang = NULL;
    if (r->language == LANG_PYTHON) {
        lang = tree_sitter_python();
    } else if (r->language == LANG_C) {
        lang = tree_sitter_c();
    } else {
        fprintf(stderr, "ERROR: unknown language for %s\n", r->file_path);
        return 0;
    }

    TSParser *parser = ts_parser_new();
    if (!ts_parser_set_language(parser, lang)) {
        fprintf(stderr, "ERROR: cannot set parser language\n");
        ts_parser_delete(parser);
        return 0;
    }

    TSTree *tree = ts_parser_parse_string(parser, NULL, r->source, (uint32_t)r->source_len);
    if (!tree) {
        fprintf(stderr, "ERROR: parse failed\n");
        ts_parser_delete(parser);
        return 0;
    }

    /* C: use dedicated C walker, then cleanup */
    if (r->language == LANG_C) {
        walk_c_ast(r, tree);
        check_tags(r);
        ts_tree_delete(tree);
        ts_parser_delete(parser);
        return 1;
    }

    /* Python: walk top-level: import statements and class definitions */
    TSNode root = ts_tree_root_node(tree);
    uint32_t count = ts_node_named_child_count(root);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(root, i);
        const char *type = ts_node_type(child);

        /* imports */
        if (strcmp(type, "import_statement") == 0) {
            if (r->import_count < VBAST_MAX_IMPORTS) {
                ImportInfo *imp = &r->imports[r->import_count];
                memset(imp, 0, sizeof(ImportInfo));
                char *txt = node_text(child, r->source);
                /* parse "import foo" or "from foo import bar" */
                if (strncmp(txt, "from ", 5) == 0) {
                    char *mod = txt + 5;
                    char *imp_kw = strstr(mod, " import ");
                    if (imp_kw) {
                        size_t mlen = imp_kw - mod;
                        if (mlen >= VBAST_MAX_NAME) mlen = VBAST_MAX_NAME - 1;
                        memcpy(imp->module, mod, mlen);
                        imp->module[mlen] = '\0';
                    }
                } else if (strncmp(txt, "import ", 7) == 0) {
                    char *mod = txt + 7;
                    strncpy(imp->module, mod, VBAST_MAX_NAME - 1);
                    /* strip "as alias" */
                    char *as_kw = strstr(imp->module, " as ");
                    if (as_kw) *as_kw = '\0';
                }
                imp->line_number = node_line(child);
                r->import_count++;
            }
        }

        /* module-level functions (not inside a class) */
        else if (strcmp(type, "function_definition") == 0 ||
                 strcmp(type, "decorated_definition") == 0) {
            TSNode func_node = child;
            int mod_decorated = 0;
            if (strcmp(type, "decorated_definition") == 0) {
                mod_decorated = 1;
                int found_func = 0;
                uint32_t dc = ts_node_named_child_count(child);
                for (uint32_t j = 0; j < dc; j++) {
                    TSNode dn = ts_node_named_child(child, j);
                    if (strcmp(ts_node_type(dn), "function_definition") == 0) {
                        func_node = dn;
                        found_func = 1;
                        break;
                    }
                }
                if (!found_func) continue;
            }

            if (r->method_count >= VBAST_MAX_METHODS) continue;
            MethodInfo *m = &r->methods[r->method_count];
            memset(m, 0, sizeof(MethodInfo));
            m->has_decorator = mod_decorated;

            uint32_t cc = ts_node_named_child_count(func_node);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(func_node, j);
                if (strcmp(ts_node_type(mc), "identifier") == 0 && m->name[0] == '\0') {
                    strncpy(m->name, node_text(mc, r->source), VBAST_MAX_NAME - 1);
                    break;
                }
            }
            /* module-level: class_name is empty */
            m->class_name[0] = '\0';
            m->line_start = node_line(func_node);
            m->line_end = node_end_line(func_node);
            extract_params(func_node, r->source, m->signature, VBAST_MAX_SIG);
            m->has_type_hint = has_type_hints(func_node, r->source);

            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(func_node, j);
                if (strcmp(ts_node_type(mc), "block") == 0) {
                    m->has_tuple3 = has_tuple3_return(mc, r->source);
                    m->has_print = has_print_call(mc, r->source);
                    extract_nested_functions(mc, r->source, m->class_name, r);
                    break;
                }
            }
            r->method_count++;
        }

        /* class definitions (may be wrapped in decorated_definition) */
        else if (strcmp(type, "class_definition") == 0 ||
                 strcmp(type, "decorated_definition") == 0) {
            TSNode class_node = child;
            int is_decorated = 0;
            if (strcmp(type, "decorated_definition") == 0) {
                is_decorated = 1;
                int found_class = 0;
                /* find the class_definition inside */
                uint32_t dc = ts_node_named_child_count(child);
                for (uint32_t j = 0; j < dc; j++) {
                    TSNode dn = ts_node_named_child(child, j);
                    if (strcmp(ts_node_type(dn), "class_definition") == 0) {
                        class_node = dn;
                        found_class = 1;
                        break;
                    }
                }
                if (!found_class) continue;
            }

            if (r->class_count >= VBAST_MAX_CLASSES) continue;
            ClassInfo *c = &r->classes[r->class_count];
            memset(c, 0, sizeof(ClassInfo));
            c->has_decorator = is_decorated;

            uint32_t cc = ts_node_named_child_count(class_node);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(class_node, j);
                if (strcmp(ts_node_type(mc), "identifier") == 0 && c->name[0] == '\0') {
                    strncpy(c->name, node_text(mc, r->source), VBAST_MAX_NAME - 1);
                    break;
                }
            }
            extract_bases(class_node, r->source, c->bases, VBAST_MAX_SIG);
            c->line_start = node_line(class_node);
            c->line_end = node_end_line(class_node);
            r->class_count++;

            /* find body and walk it */
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(class_node, j);
                if (strcmp(ts_node_type(mc), "block") == 0) {
                    walk_class_body(mc, r->source, c->name, r);
                    break;
                }
            }
        }
    }

    /* count methods per class */
    for (int ci = 0; ci < r->class_count; ci++) {
        r->classes[ci].method_count = 0;
        for (int mi = 0; mi < r->method_count; mi++) {
            if (strcmp(r->methods[mi].class_name, r->classes[ci].name) == 0) {
                r->classes[ci].method_count++;
            }
        }
    }

    check_tags(r);

    ts_tree_delete(tree);
    ts_parser_delete(parser);
    return 1;
}

void ast_free(ParseResult *r) {
    if (r->source) {
        free(r->source);
        r->source = NULL;
    }
}

void ast_print(ParseResult *r) {
    printf("=== AST: %s ===\n", r->file_path);
    printf("Classes: %d | Methods: %d | Imports: %d | Edges: %d\n\n",
           r->class_count, r->method_count, r->import_count, r->edge_count);

    for (int i = 0; i < r->import_count; i++) {
        printf("  IMPORT: %s (line %d)\n", r->imports[i].module, r->imports[i].line_number);
    }
    printf("\n");

    for (int i = 0; i < r->class_count; i++) {
        ClassInfo *c = &r->classes[i];
        printf("  CLASS: %s", c->name);
        if (c->bases[0]) printf(" (%s)", c->bases);
        printf("  [lines %d-%d]  methods=%d", c->line_start, c->line_end, c->method_count);
        if (c->has_run) printf(" RUN");
        if (c->has_ghost) printf(" GHOST");
        if (c->has_vbstyle) printf(" VBSTYLE");
        if (c->has_decorator) printf(" DECORATOR!");
        printf("\n");

        for (int j = 0; j < r->method_count; j++) {
            MethodInfo *m = &r->methods[j];
            if (strcmp(m->class_name, c->name) != 0) continue;
            printf("    METHOD: %s(%s)  [lines %d-%d]",
                   m->name, m->signature, m->line_start, m->line_end);
            if (m->has_tuple3) printf(" T3");
            if (m->has_print) printf(" PRINT!");
            if (m->has_decorator) printf(" DEC!");
            if (m->has_type_hint) printf(" HINT!");
            printf("\n");
        }
        printf("\n");
    }
}
