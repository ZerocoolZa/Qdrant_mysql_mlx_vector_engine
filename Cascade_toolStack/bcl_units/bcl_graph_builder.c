//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_builder.c" date="2026-07-04" author="Devin" session_id="bcl-vbast-units" context="BCL unit for graph edge building. Source: parsed AST (tree-sitter). Pipeline: ast_init -> ast_parse_file -> graph_build_edges -> BCL output. Absorbs graph_builder.c from vbast. No MySQL dependency."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_graph_builder.c" domain="bcl_units" authority="GraphBuilder"}
//[@SUMMARY]{summary="Graph builder BCL unit. Source = parsed AST. Owns full pipeline: ast_init, ast_parse_file, graph_build_edges, BCL output. Commands: build_edges, read_state. No MySQL. Absorbs graph_builder.c."}
//[@CLASS]{class="GraphBuilder" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="node_text" type="internal"}
//[@METHOD]{method="node_line" type="internal"}
//[@METHOD]{method="add_edge" type="internal"}
//[@METHOD]{method="extract_call" type="internal"}
//[@METHOD]{method="extract_state_access" type="internal"}
//[@METHOD]{method="walk_body_for_edges" type="internal"}
//[@METHOD]{method="graph_build_edges" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<Graph builder BCL unit. Walks tree-sitter AST to extract CALL, STATE_READ, STATE_WRITE, IMPORT edges. Absorbs graph_builder.c from vbast.>][@todos<>]}

/*
 * bcl_graph_builder.c — Graph builder BCL unit
 *
 * BCL IN:  [@RUN]{[@CMD]{build_edges}[@PATH]{/path/to/file.py}}
 *          [@RUN]{[@CMD]{read_state}}
 * BCL OUT: [@OK]{[@FILE]{...}[@EDGES]{N}[@EDGE]{[@SOURCE]{Class.method}[@TARGET]{...}[@TYPE]{CALL|STATE_READ|STATE_WRITE|IMPORT}[@CERTAINTY]{CERTAIN|PROBABLE}[@LINE]{N}}...}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "vbast.h"
#include "bcl_toolstack.h"

/* ===== DIM BLOCK ===== */

#define GRAPH_BUILDER_MAX_PATH  4096

/* ===== STATE ===== */

static struct {
    int  initialized;
    ParseResult result;
    int  files_processed;
    int  total_edges;
    char last_error[256];
} STATE;

/* ===== SECTION: HELPERS — copied from vbast/graph_builder.c ===== */

/* ── node_text — extract source text for a tree-sitter node ── */

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

/* ── node_line — get 1-based line number for a tree-sitter node ── */

static int node_line(TSNode node) {
    return (int)ts_node_start_point(node).row + 1;
}

/* ===== SECTION: ADD_EDGE — append an edge to ParseResult ===== */

static void add_edge(ParseResult *r, const char *source_name,
                     const char *target, const char *edge_type,
                     const char *certainty, int line) {
    if (r->edge_count >= VBAST_MAX_EDGES) return;
    EdgeInfo *e = &r->edges[r->edge_count];
    memset(e, 0, sizeof(EdgeInfo));
    strncpy(e->source, source_name, VBAST_MAX_NAME - 1);
    strncpy(e->target, target, VBAST_MAX_NAME - 1);
    strncpy(e->edge_type, edge_type, 31);
    strncpy(e->certainty, certainty, 15);
    e->line_number = line;
    r->edge_count++;
}

/* ===== SECTION: EXTRACT_CALL — extract call target from a call node ===== */

static void extract_call(TSNode call_node, const char *source,
                         const char *method_owner, int line,
                         ParseResult *r) {
    if (ts_node_named_child_count(call_node) == 0) return;
    TSNode func = ts_node_named_child(call_node, 0);
    const char *type = ts_node_type(func);
    char *txt = node_text(func, source);

    /* self.foo() — self_method_call */
    if (strcmp(type, "attribute") == 0 && strncmp(txt, "self.", 5) == 0) {
        /* skip self.state (that's state access, not a call) */
        if (strncmp(txt, "self.state", 10) == 0) return;
        add_edge(r, method_owner, txt, "CALL", "CERTAIN", line);
    }
    /* Foo.bar() — external call */
    else if (strcmp(type, "attribute") == 0) {
        add_edge(r, method_owner, txt, "CALL", "PROBABLE", line);
    }
    /* bare function call: foo() */
    else if (strcmp(type, "identifier") == 0) {
        /* skip builtins */
        if (strcmp(txt, "print") == 0 || strcmp(txt, "len") == 0 ||
            strcmp(txt, "str") == 0 || strcmp(txt, "int") == 0 ||
            strcmp(txt, "dict") == 0 || strcmp(txt, "list") == 0 ||
            strcmp(txt, "range") == 0 || strcmp(txt, "isinstance") == 0 ||
            strcmp(txt, "open") == 0 || strcmp(txt, "enumerate") == 0 ||
            strcmp(txt, "type") == 0 || strcmp(txt, "bool") == 0 ||
            strcmp(txt, "float") == 0 || strcmp(txt, "tuple") == 0 ||
            strcmp(txt, "set") == 0 || strcmp(txt, "sorted") == 0 ||
            strcmp(txt, "sum") == 0 || strcmp(txt, "min") == 0 ||
            strcmp(txt, "max") == 0 || strcmp(txt, "abs") == 0 ||
            strcmp(txt, "round") == 0 || strcmp(txt, "any") == 0 ||
            strcmp(txt, "all") == 0 || strcmp(txt, "zip") == 0 ||
            strcmp(txt, "map") == 0 || strcmp(txt, "filter") == 0 ||
            strcmp(txt, "next") == 0 || strcmp(txt, "iter") == 0 ||
            strcmp(txt, "getattr") == 0 || strcmp(txt, "setattr") == 0 ||
            strcmp(txt, "hasattr") == 0 || strcmp(txt, "super") == 0) {
            return;
        }
        add_edge(r, method_owner, txt, "CALL", "PROBABLE", line);
    }
}

/* ===== SECTION: EXTRACT_STATE_ACCESS — extract state read/write from subscript or attribute ===== */

static void extract_state_access(TSNode node, const char *source,
                                 const char *method_owner, int line,
                                 ParseResult *r, int is_write) {
    char *txt = node_text(node, source);
    /* self.state["key"] or self.state.get("key") */
    if (strncmp(txt, "self.state", 10) != 0) return;

    /* extract the key if it's a subscript */
    const char *type = ts_node_type(node);
    if (strcmp(type, "subscript") == 0) {
        /* find the index node */
        uint32_t count = ts_node_named_child_count(node);
        for (uint32_t i = 0; i < count; i++) {
            TSNode child = ts_node_named_child(node, i);
            const char *ct = ts_node_type(child);
            if (strcmp(ct, "string") == 0 || strcmp(ct, "integer") == 0 ||
                strcmp(ct, "identifier") == 0) {
                char *key = node_text(child, source);
                /* strip quotes from string */
                char clean[128];
                strncpy(clean, key, 127);
                clean[127] = '\0';
                if (clean[0] == '"' || clean[0] == '\'') {
                    size_t klen = strlen(clean);
                    if (klen > 1 && (clean[klen-1] == '"' || clean[klen-1] == '\'')) {
                        memmove(clean, clean + 1, klen - 2);
                        clean[klen - 2] = '\0';
                    }
                }
                char target[256];
                snprintf(target, sizeof(target), "self.state[%s]", clean);
                add_edge(r, method_owner, target,
                         is_write ? "STATE_WRITE" : "STATE_READ",
                         "CERTAIN", line);
                return;
            }
        }
    }
    /* self.state.get("key") or self.state.update(...) */
    else if (strcmp(type, "call") == 0) {
        add_edge(r, method_owner, "self.state", "STATE_READ", "CERTAIN", line);
    }
}

/* ===== SECTION: WALK_BODY_FOR_EDGES — walk a method body for calls and state access ===== */

static void walk_body_for_edges(TSNode node, const char *source,
                                const char *method_owner, ParseResult *r) {
    if (ts_node_is_null(node)) return;
    const char *type = ts_node_type(node);
    int line = node_line(node);

    /* call node */
    if (strcmp(type, "call") == 0) {
        /* check if it's a self.state call first */
        TSNode func = ts_node_named_child_count(node) > 0
            ? ts_node_named_child(node, 0) : node;
        char *ftxt = node_text(func, source);
        if (strncmp(ftxt, "self.state", 10) == 0) {
            extract_state_access(node, source, method_owner, line, r, 0);
        } else {
            extract_call(node, source, method_owner, line, r);
        }
    }

    /* subscript: self.state["key"] */
    if (strcmp(type, "subscript") == 0) {
        extract_state_access(node, source, method_owner, line, r, 0);
    }

    /* assignment: check if LHS is self.state["key"] = ... */
    if (strcmp(type, "assignment") == 0) {
        TSNode lhs = ts_node_named_child_count(node) > 0
            ? ts_node_named_child(node, 0) : node;
        char *ltxt = node_text(lhs, source);
        if (strncmp(ltxt, "self.state", 10) == 0) {
            extract_state_access(lhs, source, method_owner, line, r, 1);
        }
    }

    /* recurse into all named children */
    uint32_t count = ts_node_named_child_count(node);
    for (uint32_t i = 0; i < count; i++) {
        TSNode child = ts_node_named_child(node, i);
        walk_body_for_edges(child, source, method_owner, r);
    }
}

/* ===== SECTION: GRAPH_BUILD_EDGES — public API, declared in vbast.h ===== */

void graph_build_edges(ParseResult *r) {
    if (!r->source) return;

    const TSLanguage *lang = tree_sitter_python();
    TSParser *parser = ts_parser_new();
    ts_parser_set_language(parser, lang);
    TSTree *tree = ts_parser_parse_string(parser, NULL, r->source, (uint32_t)r->source_len);
    TSNode root = ts_tree_root_node(tree);

    /* add import edges */
    for (int i = 0; i < r->import_count; i++) {
        add_edge(r, "module", r->imports[i].module, "IMPORT", "CERTAIN",
                 r->imports[i].line_number);
    }

    /* walk each class -> method -> body */
    uint32_t class_count = ts_node_named_child_count(root);
    for (uint32_t ci = 0; ci < class_count; ci++) {
        TSNode class_node = ts_node_named_child(root, ci);
        if (strcmp(ts_node_type(class_node), "class_definition") != 0) continue;

        /* get class name */
        char class_name[VBAST_MAX_NAME] = {0};
        uint32_t cc = ts_node_named_child_count(class_node);
        for (uint32_t j = 0; j < cc; j++) {
            TSNode mc = ts_node_named_child(class_node, j);
            if (strcmp(ts_node_type(mc), "identifier") == 0) {
                strncpy(class_name, node_text(mc, r->source), VBAST_MAX_NAME - 1);
                break;
            }
        }

        /* find class body */
        for (uint32_t j = 0; j < cc; j++) {
            TSNode body = ts_node_named_child(class_node, j);
            if (strcmp(ts_node_type(body), "block") != 0) continue;

            /* walk methods in class body */
            uint32_t mc_count = ts_node_named_child_count(body);
            for (uint32_t k = 0; k < mc_count; k++) {
                TSNode method = ts_node_named_child(body, k);
                if (strcmp(ts_node_type(method), "function_definition") != 0) continue;

                /* get method name */
                char method_name[VBAST_MAX_NAME] = {0};
                char method_owner[VBAST_MAX_NAME * 2];
                uint32_t mcc = ts_node_named_child_count(method);
                for (uint32_t m = 0; m < mcc; m++) {
                    TSNode mn = ts_node_named_child(method, m);
                    if (strcmp(ts_node_type(mn), "identifier") == 0) {
                        strncpy(method_name, node_text(mn, r->source), VBAST_MAX_NAME - 1);
                        break;
                    }
                }
                snprintf(method_owner, sizeof(method_owner), "%s.%s",
                         class_name, method_name);

                /* find method body and walk it */
                for (uint32_t m = 0; m < mcc; m++) {
                    TSNode mbody = ts_node_named_child(method, m);
                    if (strcmp(ts_node_type(mbody), "block") == 0) {
                        walk_body_for_edges(mbody, r->source, method_owner, r);
                        break;
                    }
                }
            }
        }
    }

    ts_tree_delete(tree);
    ts_parser_delete(parser);
}

/* ===== SECTION: UNIT INTERFACE ===== */

int GraphBuilder_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    return 1;
}

int GraphBuilder_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphBuilder_Init();

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{1}[@PROCESSED]{%d}[@EDGES]{%d}",
            STATE.files_processed, STATE.total_edges);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== BUILD_EDGES ===== */
    if (strcmp(cmd, "build_edges") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[GRAPH_BUILDER_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);

        if (!path[0]) {
            strncpy(STATE.last_error, "no PATH in packet", sizeof(STATE.last_error) - 1);
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }

        /* parse the file via ast_walker API */
        ParseResult *r = &STATE.result;
        memset(r, 0, sizeof(ParseResult));
        ast_init(r, path);
        if (ast_parse_file(r) == 0) {
            strncpy(STATE.last_error, "ast_parse_file failed", sizeof(STATE.last_error) - 1);
            ast_free(r);
            return BclResult_Err(bcl_out, out_sz, 21, "ast_parse_file failed");
        }

        /* build edges from AST */
        int edges_before = r->edge_count;
        graph_build_edges(r);
        int edges_built = r->edge_count - edges_before;

        STATE.files_processed++;
        STATE.total_edges += edges_built;

        /* build BCL output */
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@FILE]{%s}[@EDGES]{%d}", path, edges_built);

        for (int i = edges_before; i < r->edge_count && offset < (int)out_sz - 512; i++) {
            EdgeInfo *e = &r->edges[i];
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@EDGE]{[@SOURCE]{%s}[@TARGET]{%s}[@TYPE]{%s}[@CERTAINTY]{%s}[@LINE]{%d}}",
                e->source, e->target, e->edge_type, e->certainty, e->line_number);
        }

        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");

        ast_free(r);
        return 1;
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int GraphBuilder_Close(void) {
    memset(&STATE, 0, sizeof(STATE));
    return 1;
}

const char * GraphBuilder_State(void) {
    static char buf[512];
    snprintf(buf, sizeof(buf),
        "GraphBuilder: initialized=%d files_processed=%d total_edges=%d last_error=%s",
        STATE.initialized, STATE.files_processed, STATE.total_edges,
        STATE.last_error[0] ? STATE.last_error : "none");
    return buf;
}
