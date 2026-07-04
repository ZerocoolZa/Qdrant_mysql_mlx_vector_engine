//[@GHOST]{file_path="Cascade_toolStack/vbast/ast_walker.c" date="2026-06-29" author="Devin" session_id="vbast-bcl-stamp" context="Tree-sitter walk, extract classes/methods/signatures from Python source"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="ast_walker.c" domain="vbast" authority="AstWalker"}
//[@SUMMARY]{summary="AST walker — tree-sitter parse, extract classes/methods/imports from Python source"}
//[@CLASS]{class="AstWalker" domain="vbast" authority="single"}
//[@METHOD]{methods="walk,extract_classes,extract_methods,extract_imports,extract_signatures"}
//
// ast_walker.c — tree-sitter walk, extract classes/methods/signatures
//
// Uses tree-sitter-python to parse Python source into a real AST.
// Walks the tree and populates ParseResult with:
//   - classes (name, bases, line range, flags)
//   - methods (name, class, signature, line range, flags)
//   - imports (module, alias, line)
//
// No string guessing. No regex. Real syntax tree.

#include "vbast.h"

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
 * LANGUAGE DETECTION
 * ════════════════════════════════════════════ */

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

/* ════════════════════════════════════════════
 * C AST WALKER
 * ════════════════════════════════════════════ */

/* ── extract function name from a C function_definition ── */

static void extract_c_func_name(TSNode func_node, const char *source,
                                char *out, size_t out_sz) {
    out[0] = '\0';
    /* C function_definition has children: type, declarator, body
     * The declarator is a function_declarator which contains an identifier */
    uint32_t count = ts_node_named_child_count(func_node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(func_node, i);
        const char *type = ts_node_type(child);
        if (strcmp(type, "function_declarator") == 0) {
            /* function_declarator contains the identifier */
            uint32_t dc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < dc; j++) {
                TSNode dn = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(dn), "identifier") == 0) {
                    strncpy(out, node_text(dn, source), out_sz - 1);
                    out[out_sz - 1] = '\0';
                    return;
                }
                /* pointer_declarator wraps function_declarator */
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
        /* direct identifier (simple function) */
        if (strcmp(type, "identifier") == 0 && out[0] == '\0') {
            strncpy(out, node_text(child, source), out_sz - 1);
            out[out_sz - 1] = '\0';
        }
    }
}

/* ── extract C function parameters from function_definition ── */

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
    }
}

/* ── walk a C function body for call_expression edges ── */

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
                /* function name is first child */
                TSNode func = ts_node_named_child(child, 0);
                if (!ts_node_is_null(func)) {
                    char *fname = node_text(func, source);
                    /* strip to just the name (could be identifier or field) */
                    strncpy(e->target, fname, VBAST_MAX_NAME - 1);
                }
                strncpy(e->source, caller, VBAST_MAX_NAME - 1);
                strncpy(e->edge_type, "CALL", sizeof(e->edge_type) - 1);
                strncpy(e->certainty, "PROBABLE", sizeof(e->certainty) - 1);
                e->line_number = node_line(child);
                r->edge_count++;
            }
            /* recurse into arguments */
            walk_c_calls(child, source, caller, r);
        } else {
            /* recurse into other nodes */
            walk_c_calls(child, source, caller, r);
        }
    }
}

/* ── walk C AST top-level ── */

static void walk_c_ast(TSNode root, ParseResult *r) {
    uint32_t count = ts_node_named_child_count(root);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(root, i);
        const char *type = ts_node_type(child);

        /* #include directives → ImportInfo */
        if (strcmp(type, "preproc_include") == 0) {
            if (r->import_count < VBAST_MAX_IMPORTS) {
                ImportInfo *imp = &r->imports[r->import_count];
                memset(imp, 0, sizeof(ImportInfo));
                /* find the path/STRING_LITERAL child */
                uint32_t cc = ts_node_named_child_count(child);
                for (uint32_t j = 0; j < cc; j++) {
                    TSNode mc = ts_node_named_child(child, j);
                    const char *mt = ts_node_type(mc);
                    if (strcmp(mt, "string_literal") == 0 ||
                        strcmp(mt, "system_lib_string") == 0 ||
                        strcmp(mt, "path") == 0) {
                        char *txt = node_text(mc, r->source);
                        /* strip quotes/angle brackets */
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

        /* function_definition → MethodInfo (file scope, class_name="") */
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

            /* walk body for call edges */
            uint32_t cc = ts_node_named_child_count(child);
            for (uint32_t j = 0; j < cc; j++) {
                TSNode mc = ts_node_named_child(child, j);
                if (strcmp(ts_node_type(mc), "compound_statement") == 0) {
                    walk_c_calls(mc, r->source, m->name, r);
                    break;
                }
            }
        }

        /* struct_specifier → ClassInfo */
        else if (strcmp(type, "struct_specifier") == 0) {
            if (r->class_count >= VBAST_MAX_CLASSES) continue;
            ClassInfo *c = &r->classes[r->class_count];
            memset(c, 0, sizeof(ClassInfo));
            /* name is the "name" child (identifier) */
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

            /* walk body for function_definitions (methods) */
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

        /* type_definition (typedef struct {...} Name) → ClassInfo */
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
                    /* if no name inside struct, use the typedef name */
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

    /* count methods per class (C structs) */
    for (int ci = 0; ci < r->class_count; ci++) {
        r->classes[ci].method_count = 0;
        for (int mi = 0; mi < r->method_count; mi++) {
            if (strcmp(r->methods[mi].class_name, r->classes[ci].name) == 0) {
                r->classes[ci].method_count++;
            }
        }
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

    /* detect language by file extension */
    r->language = detect_language(r->file_path);
    if (r->language == LANG_UNKNOWN) {
        fprintf(stderr, "ERROR: unsupported file type (not .py/.c/.h): %s\n", r->file_path);
        return 0;
    }

    /* select the matching tree-sitter grammar */
    const TSLanguage *lang = NULL;
    if (r->language == LANG_PYTHON) {
        lang = tree_sitter_python();
    } else if (r->language == LANG_C) {
        lang = tree_sitter_c();
    }
    if (!lang) {
        fprintf(stderr, "ERROR: cannot load grammar for language %d\n", r->language);
        return 0;
    }

    TSParser *parser = ts_parser_new();
    if (!ts_parser_set_language(parser, lang)) {
        fprintf(stderr, "ERROR: cannot set language\n");
        ts_parser_delete(parser);
        return 0;
    }

    TSTree *tree = ts_parser_parse_string(parser, NULL, r->source, (uint32_t)r->source_len);
    if (!tree) {
        fprintf(stderr, "ERROR: parse failed\n");
        ts_parser_delete(parser);
        return 0;
    }

    TSNode root = ts_tree_root_node(tree);

    /* dispatch to language-specific walker */
    if (r->language == LANG_C) {
        walk_c_ast(root, r);
        check_tags(r);
        ts_tree_delete(tree);
        ts_parser_delete(parser);
        return 1;
    }

    /* ── Python walk (existing behavior) ── */
    /* walk top-level: import statements and class definitions */
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
    const char *lang_str = "UNKNOWN";
    if (r->language == LANG_PYTHON) lang_str = "PYTHON";
    else if (r->language == LANG_C) lang_str = "C";

    printf("=== AST: %s [%s] ===\n", r->file_path, lang_str);
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

    /* file-scope functions (class_name empty) — common in C */
    int printed_free = 0;
    for (int j = 0; j < r->method_count; j++) {
        MethodInfo *m = &r->methods[j];
        if (m->class_name[0] != '\0') continue;
        if (!printed_free) {
            printf("  FILE-SCOPE FUNCTIONS:\n");
            printed_free = 1;
        }
        printf("    FUNC: %s(%s)  [lines %d-%d]\n",
               m->name, m->signature, m->line_start, m->line_end);
    }
    if (printed_free) printf("\n");
}
