//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_ast_walker.c" date="2026-07-04" author="Devin" session_id="bcl-vbast-units" context="BCL unit for tree-sitter AST walker. Source: local source files (.py/.c/.h). Pipeline: detect language -> tree-sitter parse -> walk AST -> extract classes/methods/imports/signatures -> BCL output. Wraps ast_walker.c. Owns tree-sitter parsing for the 5 vbast units. No MySQL dependency."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_ast_walker.c" domain="bcl_units" authority="AstWalker"}
//[@SUMMARY]{summary="AST walker BCL unit. Source = local source files (.py/.c/.h). Owns tree-sitter parse pipeline: detect language, parse, walk AST, extract classes/methods/imports/signatures. Commands: parse_file, get_classes, get_methods, read_state. Public API: ast_init, ast_parse_file, ast_free, detect_language, read_file, trim."}
//[@CLASS]{class="AstWalker" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Walk" type="internal"}
//[@METHOD]{method="WalkClassBody" type="internal"}
//[@METHOD]{method="WalkCAst" type="internal"}
//[@METHOD]{method="CheckTags" type="internal"}
//[@METHOD]{method="ExtractParams" type="internal"}
//[@METHOD]{method="ExtractBases" type="internal"}
//[@METHOD]{method="ExtractNestedFunctions" type="internal"}
//[@METHOD]{method="ExtractCFuncName" type="internal"}
//[@METHOD]{method="ExtractCParams" type="internal"}
//[@METHOD]{method="WalkCCalls" type="internal"}
//[@METHOD]{method="HasTuple3Return" type="internal"}
//[@METHOD]{method="HasPrintCall" type="internal"}
//[@METHOD]{method="HasDecorator" type="internal"}
//[@METHOD]{method="HasTypeHints" type="internal"}
//[@METHOD]{method="NodeText" type="internal"}
//[@METHOD]{method="NodeLine" type="internal"}
//[@METHOD]{method="NodeEndLine" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<AST walker BCL unit. Wraps tree-sitter parse for Python and C. Public API used by the other 4 vbast units.>][@todos<>]}

/*
 * bcl_ast_walker.c — tree-sitter AST walker BCL unit
 *
 * BCL IN:  [@RUN]{[@CMD]{parse_file}[@PATH]{/path/to/file.py}}
 *          [@RUN]{[@CMD]{get_classes}}
 *          [@RUN]{[@CMD]{get_methods}}
 *          [@RUN]{[@CMD]{read_state}}
 * BCL OUT: [@OK]{[@FILE]{...}[@LANG]{PYTHON|C}[@CLASSES]{N}[@METHODS]{N}[@IMPORTS]{N}[@CLASS]{...}...}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "vbast.h"
#include "bcl_toolstack.h"

/* ===== DIM BLOCK ===== */

/* (constants come from vbast.h) */

/* State */
static struct {
    int          initialized;
    ParseResult  result;
    int          files_parsed;
    int          classes_found;
    int          methods_found;
    char         last_error[256];
} STATE;

/* ===== NODE HELPERS ===== */

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

/* ===== EXTRACT PARAMS ===== */

static void extract_params(TSNode func_node, const char *source, char *out, size_t out_sz) {
    out[0] = '\0';
    uint32_t count = ts_node_named_child_count(func_node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(func_node, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "parameters") == 0) {
            char *txt = node_text(child, source);
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

/* ===== EXTRACT BASES ===== */

static void extract_bases(TSNode class_node, const char *source, char *out, size_t out_sz) {
    out[0] = '\0';
    uint32_t count = ts_node_named_child_count(class_node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(class_node, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "argument_list") == 0) {
            char *txt = node_text(child, source);
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

/* ===== HAS TUPLE3 RETURN ===== */

static int has_tuple3_return(TSNode body, const char *source) {
    uint32_t count = ts_node_named_child_count(body);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(body, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "return_statement") == 0) {
            uint32_t rc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < rc; j++) {
                TSNode ret_val = ts_node_named_child(child, j);
                const char *rt = ts_node_type(ret_val);
                if (strcmp(rt, "tuple") == 0) {
                    return 1;
                }
            }
        }
        if (strcmp(type, "if_statement") == 0 || strcmp(type, "for_statement") == 0 ||
            strcmp(type, "while_statement") == 0 || strcmp(type, "try_statement") == 0 ||
            strcmp(type, "with_statement") == 0) {
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

/* ===== HAS PRINT CALL ===== */

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

/* ===== HAS DECORATOR ===== */

static int has_decorator(TSNode node) {
    uint32_t count = ts_node_named_child_count(node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(node, i);
        if (strcmp(ts_node_type(child), "decorator") == 0) return 1;
    }
    return 0;
}

/* ===== HAS TYPE HINTS ===== */

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
        if (strcmp(ts_node_type(child), "type") == 0) return 1;
    }
    return 0;
}

/* ===== EXTRACT NESTED FUNCTIONS ===== */

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

/* ===== WALK CLASS BODY ===== */

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

            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(func_node, j);
                if (strcmp(ts_node_type(mc), "block") == 0) {
                    m->has_tuple3 = has_tuple3_return(mc, source);
                    m->has_print = has_print_call(mc, source);
                    extract_nested_functions(mc, source, class_name, r);
                    break;
                }
            }

            if (strcmp(m->name, "Run") == 0) {
                r->classes[r->class_count - 1].has_run = 1;
            }

            r->method_count++;
        }
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

/* ===== CHECK TAGS — GHOST/VBSTYLE in comments ===== */

static void check_tags(ParseResult *r) {
    const char *src = r->source;
    if (!src) return;
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

/* ===== LANGUAGE DETECTION ===== */

Language detect_language(const char *file_path) {
    size_t len = strlen(file_path);
    if (len >= 3 && strcmp(file_path + len - 3, ".py") == 0) {
        return LANG_PYTHON;
    }
    if (len >= 2 && strcmp(file_path + len - 2, ".c") == 0) {
        return LANG_C;
    }
    if (len >= 2 && strcmp(file_path + len - 2, ".h") == 0) {
        return LANG_C;
    }
    return LANG_UNKNOWN;
}

/* ===== C AST WALKER — EXTRACT C FUNC NAME ===== */

static void extract_c_func_name(TSNode func_node, const char *source,
                                char *out, size_t out_sz) {
    out[0] = '\0';
    uint32_t count = ts_node_named_child_count(func_node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(func_node, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "function_declarator") == 0) {
            uint32_t dc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < dc; j++) {
                TSNode dn = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(dn), "identifier") == 0) {
                    strncpy(out, node_text(dn, source), out_sz - 1);
                    out[out_sz - 1] = '\0';
                    return;
                }
                if (strcmp(ts_node_type(dn), "pointer_declarator") == 0) {
                    uint32_t pc = ts_node_named_child_count(dn);
                    for (uint32_t k = 0; k < pc; k++) {
                        TSNode pn = ts_node_named_child(dn, k);
                        if (strcmp(ts_node_type(pn), "function_declarator") == 0) {
                            uint32_t fc = ts_node_named_child_count(pn);
                            for (uint32_t l = 0; l < fc; l++) {
                                TSNode fn = ts_node_named_child(pn, l);
                                if (strcmp(ts_node_type(fn), "identifier") == 0) {
                                    strncpy(out, node_text(fn, source), out_sz - 1);
                                    out[out_sz - 1] = '\0';
                                    return;
                                }
                            }
                        }
                    }
                }
            }
        }
        if (strcmp(type, "identifier") == 0 && out[0] == '\0') {
            strncpy(out, node_text(child, source), out_sz - 1);
            out[out_sz - 1] = '\0';
        }
    }
}

/* ===== C AST WALKER — EXTRACT C PARAMS ===== */

static void extract_c_params(TSNode func_node, const char *source,
                             char *out, size_t out_sz) {
    out[0] = '\0';
    uint32_t count = ts_node_named_child_count(func_node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(func_node, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "function_declarator") == 0) {
            uint32_t dc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < dc; j++) {
                TSNode dn = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(dn), "parameter_list") == 0) {
                    char *txt = node_text(dn, source);
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
    }
}

/* ===== C AST WALKER — WALK C CALLS ===== */

static void walk_c_calls(TSNode node, const char *source, const char *caller,
                         ParseResult *r) {
    uint32_t count = ts_node_named_child_count(node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(node, i);
        const char *type = ts_node_type(child);

        if (strcmp(type, "call_expression") == 0) {
            if (r->edge_count < VBAST_MAX_EDGES) {
                EdgeInfo *e = &r->edges[r->edge_count];
                memset(e, 0, sizeof(EdgeInfo));
                TSNode func = ts_node_named_child(child, 0);
                if (!ts_node_is_null(func)) {
                    char *fname = node_text(func, source);
                    strncpy(e->target, fname, VBAST_MAX_NAME - 1);
                }
                strncpy(e->source, caller, VBAST_MAX_NAME - 1);
                strncpy(e->edge_type, "CALL", sizeof(e->edge_type) - 1);
                strncpy(e->certainty, "PROBABLE", sizeof(e->certainty) - 1);
                e->line_number = node_line(child);
                r->edge_count++;
            }
            walk_c_calls(child, source, caller, r);
        } else {
            walk_c_calls(child, source, caller, r);
        }
    }
}

/* ===== C AST WALKER — WALK C AST TOP-LEVEL ===== */

static void walk_c_ast(TSNode root, ParseResult *r) {
    uint32_t count = ts_node_named_child_count(root);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(root, i);
        const char *type = ts_node_type(child);

        if (strcmp(type, "preproc_include") == 0) {
            if (r->import_count < VBAST_MAX_IMPORTS) {
                ImportInfo *imp = &r->imports[r->import_count];
                memset(imp, 0, sizeof(ImportInfo));
                uint32_t cc = ts_node_named_child_count(child);
                for (uint32_t j = 0; j < cc; j++) {
                    TSNode mc = ts_node_named_child(child, j);
                    const char *mt = ts_node_type(mc);
                    if (strcmp(mt, "string_literal") == 0 ||
                        strcmp(mt, "system_lib_string") == 0 ||
                        strcmp(mt, "path") == 0) {
                        char *txt = node_text(mc, r->source);
                        char *s = txt;
                        while (*s == '"' || *s == '<' || *s == ' ') s++;
                        size_t len = strlen(s);
                        while (len > 0 && (s[len-1] == '"' || s[len-1] == '>' ||
                               s[len-1] == ' ')) s[--len] = '\0';
                        strncpy(imp->module, s, VBAST_MAX_NAME - 1);
                        break;
                    }
                }
                imp->line_number = node_line(child);
                r->import_count++;
            }
        }

        else if (strcmp(type, "function_definition") == 0) {
            if (r->method_count >= VBAST_MAX_METHODS) continue;
            MethodInfo *m = &r->methods[r->method_count];
            memset(m, 0, sizeof(MethodInfo));
            extract_c_func_name(child, r->source, m->name, VBAST_MAX_NAME);
            m->class_name[0] = '\0';
            m->line_start = node_line(child);
            m->line_end = node_end_line(child);
            extract_c_params(child, r->source, m->signature, VBAST_MAX_SIG);
            r->method_count++;

            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(mc), "compound_statement") == 0) {
                    walk_c_calls(mc, r->source, m->name, r);
                    break;
                }
            }
        }

        else if (strcmp(type, "struct_specifier") == 0) {
            if (r->class_count >= VBAST_MAX_CLASSES) continue;
            ClassInfo *c = &r->classes[r->class_count];
            memset(c, 0, sizeof(ClassInfo));
            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(mc), "type_identifier") == 0 ||
                    strcmp(ts_node_type(mc), "identifier") == 0) {
                    strncpy(c->name, node_text(mc, r->source), VBAST_MAX_NAME - 1);
                    break;
                }
            }
            c->line_start = node_line(child);
            c->line_end = node_end_line(child);
            r->class_count++;

            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(mc), "field_declaration_list") == 0) {
                    uint32_t fc = ts_node_named_child_count(mc);
                    for (uint32_t k = 0; k < fc; k++) {
                        TSNode fn = ts_node_named_child(mc, k);
                        if (strcmp(ts_node_type(fn), "function_definition") == 0) {
                            if (r->method_count >= VBAST_MAX_METHODS) continue;
                            MethodInfo *m = &r->methods[r->method_count];
                            memset(m, 0, sizeof(MethodInfo));
                            extract_c_func_name(fn, r->source, m->name, VBAST_MAX_NAME);
                            strncpy(m->class_name, c->name, VBAST_MAX_NAME - 1);
                            m->line_start = node_line(fn);
                            m->line_end = node_end_line(fn);
                            extract_c_params(fn, r->source, m->signature, VBAST_MAX_SIG);
                            r->method_count++;
                            c->method_count++;
                        }
                    }
                    break;
                }
            }
        }

        else if (strcmp(type, "type_definition") == 0) {
            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(mc), "struct_specifier") == 0) {
                    if (r->class_count >= VBAST_MAX_CLASSES) break;
                    ClassInfo *c = &r->classes[r->class_count];
                    memset(c, 0, sizeof(ClassInfo));
                    uint32_t sc = ts_node_named_child_count(mc);
                    for (uint32_t k = 0; k < sc; k++) {
                        TSNode sn = ts_node_named_child(mc, k);
                        if (strcmp(ts_node_type(sn), "type_identifier") == 0 ||
                            strcmp(ts_node_type(sn), "identifier") == 0) {
                            strncpy(c->name, node_text(sn, r->source), VBAST_MAX_NAME - 1);
                            break;
                        }
                    }
                    if (c->name[0] == '\0') {
                        for (uint32_t k = 0; k < cc; k++) {
                            TSNode tn = ts_node_named_child(child, k);
                            if (strcmp(ts_node_type(tn), "type_identifier") == 0) {
                                strncpy(c->name, node_text(tn, r->source), VBAST_MAX_NAME - 1);
                                break;
                            }
                        }
                    }
                    c->line_start = node_line(child);
                    c->line_end = node_end_line(child);
                    r->class_count++;
                    break;
                }
            }
        }
    }

    for (int ci = 0; ci < r->class_count; ci++) {
        r->classes[ci].method_count = 0;
        for (int mi = 0; mi < r->method_count; mi++) {
            if (strcmp(r->methods[mi].class_name, r->classes[ci].name) == 0) {
                r->classes[ci].method_count++;
            }
        }
    }
}

/* ===== SHARED HELPERS (from vbast.c — declared in vbast.h) ===== */

char *read_file(const char *path, char *buf, size_t bufsize) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    size_t n = fread(buf, 1, bufsize - 1, f);
    buf[n] = '\0';
    fclose(f);
    return buf;
}

void trim(char *s) {
    size_t len = strlen(s);
    while (len > 0 && isspace((unsigned char)s[len-1])) s[--len] = '\0';
    size_t start = 0;
    while (s[start] && isspace((unsigned char)s[start])) start++;
    if (start > 0) memmove(s, s + start, len - start + 1);
}

/* ===== PUBLIC API — used by the other 4 vbast units ===== */

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
        snprintf(STATE.last_error, sizeof(STATE.last_error),
                 "cannot read %s", r->file_path);
        return 0;
    }
    r->source = strdup(content);
    r->source_len = strlen(content);

    r->language = detect_language(r->file_path);
    if (r->language == LANG_UNKNOWN) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
                 "unsupported file type (not .py/.c/.h): %s", r->file_path);
        return 0;
    }

    const TSLanguage *lang = NULL;
    if (r->language == LANG_PYTHON) {
        lang = tree_sitter_python();
    } else if (r->language == LANG_C) {
        lang = tree_sitter_c();
    }
    if (!lang) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
                 "cannot load grammar for language %d", r->language);
        return 0;
    }

    TSParser *parser = ts_parser_new();
    if (!ts_parser_set_language(parser, lang)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "cannot set language");
        ts_parser_delete(parser);
        return 0;
    }

    TSTree *tree = ts_parser_parse_string(parser, NULL, r->source, (uint32_t)r->source_len);
    if (!tree) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "parse failed");
        ts_parser_delete(parser);
        return 0;
    }

    TSNode root = ts_tree_root_node(tree);

    if (r->language == LANG_C) {
        walk_c_ast(root, r);
        check_tags(r);
        ts_tree_delete(tree);
        ts_parser_delete(parser);
        return 1;
    }

    /* ── Python walk ── */
    uint32_t count = ts_node_named_child_count(root);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(root, i);
        const char *type = ts_node_type(child);

        if (strcmp(type, "import_statement") == 0) {
            if (r->import_count < VBAST_MAX_IMPORTS) {
                ImportInfo *imp = &r->imports[r->import_count];
                memset(imp, 0, sizeof(ImportInfo));
                char *txt = node_text(child, r->source);
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
                    char *as_kw = strstr(imp->module, " as ");
                    if (as_kw) *as_kw = '\0';
                }
                imp->line_number = node_line(child);
                r->import_count++;
            }
        }

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
                    strncpy(c->name, node_text(mc, r->source), VBAST_MAX_NAME - 1);
                    break;
                }
            }
            extract_bases(class_node, r->source, c->bases, VBAST_MAX_SIG);
            c->line_start = node_line(class_node);
            c->line_end = node_end_line(class_node);
            r->class_count++;

            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(class_node, j);
                if (strcmp(ts_node_type(mc), "block") == 0) {
                    walk_class_body(mc, r->source, c->name, r);
                    break;
                }
            }
        }
    }

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

/* ===== UNIT INTERFACE ===== */

int AstWalker_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    return 1;
}

int AstWalker_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) AstWalker_Init();

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[256];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@FILES]{%d}[@CLASSES]{%d}[@METHODS]{%d}",
            STATE.initialized ? 1 : 0,
            STATE.files_parsed, STATE.classes_found, STATE.methods_found);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== PARSE_FILE ===== */
    if (strcmp(cmd, "parse_file") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[VBAST_MAX_LINE] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }

        /* free any previous parse result */
        ast_free(&STATE.result);
        ast_init(&STATE.result, path);

        if (!ast_parse_file(&STATE.result)) {
            return BclResult_Err(bcl_out, out_sz, 21,
                STATE.last_error[0] ? STATE.last_error : "parse failed");
        }

        STATE.files_parsed++;
        STATE.classes_found   = STATE.result.class_count;
        STATE.methods_found   = STATE.result.method_count;

        const char *lang_str = "UNKNOWN";
        if (STATE.result.language == LANG_PYTHON) lang_str = "PYTHON";
        else if (STATE.result.language == LANG_C) lang_str = "C";

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@FILE]{%s}[@LANG]{%s}[@CLASSES]{%d}[@METHODS]{%d}[@IMPORTS]{%d}",
            STATE.result.file_path, lang_str,
            STATE.result.class_count, STATE.result.method_count,
            STATE.result.import_count);

        /* emit class blocks */
        for (int i = 0; i < STATE.result.class_count && offset < (int)out_sz - 1024; i++) {
            ClassInfo *c = &STATE.result.classes[i];
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@CLASS]{[@NAME]{%s}[@LINES]{%d-%d}[@METHODS]{%d}[@RUN]{%d}[@GHOST]{%d}[@VBSTYLE]{%d}[@DECORATOR]{%d}}",
                c->name, c->line_start, c->line_end, c->method_count,
                c->has_run, c->has_ghost, c->has_vbstyle, c->has_decorator);
        }

        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    /* ===== GET_CLASSES ===== */
    if (strcmp(cmd, "get_classes") == 0) {
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@FILE]{%s}[@CLASSES]{%d}",
            STATE.result.file_path, STATE.result.class_count);

        for (int i = 0; i < STATE.result.class_count && offset < (int)out_sz - 1024; i++) {
            ClassInfo *c = &STATE.result.classes[i];
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@CLASS]{[@NAME]{%s}[@LINES]{%d-%d}[@METHODS]{%d}[@RUN]{%d}[@GHOST]{%d}[@VBSTYLE]{%d}[@DECORATOR]{%d}}",
                c->name, c->line_start, c->line_end, c->method_count,
                c->has_run, c->has_ghost, c->has_vbstyle, c->has_decorator);
        }

        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    /* ===== GET_METHODS ===== */
    if (strcmp(cmd, "get_methods") == 0) {
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@FILE]{%s}[@METHODS]{%d}",
            STATE.result.file_path, STATE.result.method_count);

        for (int i = 0; i < STATE.result.method_count && offset < (int)out_sz - 512; i++) {
            MethodInfo *m = &STATE.result.methods[i];
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@METHOD]{[@NAME]{%s}[@CLASS]{%s}[@SIG]{%s}[@LINES]{%d-%d}[@T3]{%d}[@PRINT]{%d}[@DEC]{%d}[@HINT]{%d}}",
                m->name, m->class_name, m->signature,
                m->line_start, m->line_end,
                m->has_tuple3, m->has_print, m->has_decorator, m->has_type_hint);
        }

        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int AstWalker_Close(void) {
    ast_free(&STATE.result);
    STATE.initialized = 0;
    return 1;
}

const char * AstWalker_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "AstWalker: initialized=%d files=%d classes=%d methods=%d",
        STATE.initialized, STATE.files_parsed,
        STATE.classes_found, STATE.methods_found);
    return buf;
}
