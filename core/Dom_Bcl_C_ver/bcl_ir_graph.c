//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_ir_graph.c" date="2026-06-29" author="Devin" session_id="bcl-ir-graph" context="BCL IR Graph implementation — parses BCL once via an embedded copy of the syntax-only parser, then computes token IDs (djb2), positional encoding (depth + sibling index sinusoidal), attention mask (ancestor/sibling graph), domain IDs (10-domain substring match), and graph bias (FEEDS/PAIRS/ENABLES/MEASURES T5-style edges) in a single pass"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_ir_graph.c" domain="bcl_c_engine" authority="BclIrGraph"}
//[@SUMMARY]{summary="BCL IR Graph implementation — embedded syntax-only parser + 5 signal computers (TokenIds, PE, Mask, Domains, GraphBias) + ComputeAll + Print. Self-contained: only string.h, ctype.h, math.h — no tree_sitter dependency"}
//[@CLASS]{class="BclIrGraph" domain="bcl_c_engine" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Parse" type="command"}
//[@METHOD]{method="ComputeTokenIds" type="command"}
//[@METHOD]{method="ComputePE" type="command"}
//[@METHOD]{method="ComputeMask" type="command"}
//[@METHOD]{method="ComputeDomains" type="command"}
//[@METHOD]{method="ComputeGraphBias" type="command"}
//[@METHOD]{method="ComputeAll" type="command"}
//[@METHOD]{method="Print" type="command"}
//[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Self-contained IR graph. Parser copied from bcl_parser.c to avoid tree_sitter header dependency.>][@todos<none>]}

#include "bcl_ir_graph.h"

/* ════════════════════════════════════════════
 * EMBEDDED PARSER — copied from bcl_parser.c
 * (syntax-only, knows ONLY [@TAG]{content})
 * Kept here so bcl_ir_graph.c compiles without
 * the tree_sitter headers that bcl_engine.h pulls.
 * ════════════════════════════════════════════ */

static void IrParser_Init(BclIrParseResult *p) {
    if (!p) {
        return;
    }
    memset(p, 0, sizeof(BclIrParseResult));
    p->parse_ok = 1;
    p->error_pos = -1;
}

static int IrAddNode(BclIrParseResult *p, const char *tag, int start_pos, int depth, int parent_idx) {
    int idx;
    if (p->node_count >= BCLIR_MAX_NODES) {
        return -1;
    }
    idx = p->node_count;
    memset(&p->nodes[idx], 0, sizeof(BclIrNode));
    strncpy(p->nodes[idx].tag, tag, BCLIR_MAX_TAG - 1);
    p->nodes[idx].tag[BCLIR_MAX_TAG - 1] = '\0';
    p->nodes[idx].start_pos = start_pos;
    p->nodes[idx].depth = depth;
    p->nodes[idx].parent_idx = parent_idx;
    p->nodes[idx].child_count = 0;
    p->node_count++;
    return idx;
}

static void IrSetNodeContent(BclIrParseResult *p, int idx, const char *content, int len) {
    int copy_len;
    if (idx < 0 || idx >= p->node_count) {
        return;
    }
    copy_len = len;
    if (copy_len >= BCLIR_MAX_CONTENT) {
        copy_len = BCLIR_MAX_CONTENT - 1;
    }
    if (copy_len > 0) {
        memcpy(p->nodes[idx].content, content, copy_len);
    }
    p->nodes[idx].content[copy_len] = '\0';
    p->nodes[idx].end_pos = p->nodes[idx].start_pos + len;
}

static void IrAddChild(BclIrParseResult *p, int parent_idx, int child_idx) {
    BclIrNode *parent;
    if (parent_idx < 0 || parent_idx >= p->node_count) {
        return;
    }
    parent = &p->nodes[parent_idx];
    if (parent->child_count >= 32) {
        return;
    }
    parent->children[parent->child_count] = child_idx;
    parent->child_count++;
}

static void IrSetError(BclIrParseResult *p, const char *msg, int pos) {
    p->parse_ok = 0;
    strncpy(p->error_msg, msg, sizeof(p->error_msg) - 1);
    p->error_msg[sizeof(p->error_msg) - 1] = '\0';
    p->error_pos = pos;
}

static int IrParseBclInner(BclIrParseResult *p, const char *text, int pos, int end_pos, int depth, int parent_idx) {
    int len;
    int i;
    int tag_start;
    int tag_end;
    int brace_start;
    int content_start;
    int brace_end;
    int brace_depth;
    int node_idx;
    char tag[BCLIR_MAX_TAG];

    len = end_pos;

    while (pos < len) {
        if (text[pos] == '[' && pos + 1 < len && text[pos + 1] == '@') {
            tag_start = pos + 2;

            tag_end = tag_start;
            while (tag_end < len && text[tag_end] != ']' && text[tag_end] != '\0') {
                tag_end++;
            }
            if (tag_end >= len || text[tag_end] != ']') {
                IrSetError(p, "unterminated_tag", pos);
                return -1;
            }

            i = 0;
            while (i < BCLIR_MAX_TAG - 1 && tag_start + i < tag_end) {
                tag[i] = text[tag_start + i];
                i++;
            }
            tag[i] = '\0';

            if (i == 0) {
                IrSetError(p, "empty_tag", pos);
                return -1;
            }

            if (tag_end + 1 >= len || text[tag_end + 1] != '{') {
                pos = tag_end + 1;
                continue;
            }
            brace_start = tag_end + 1;
            content_start = brace_start + 1;

            brace_depth = 1;
            i = content_start;
            while (i < len && brace_depth > 0) {
                if (text[i] == '{') {
                    brace_depth++;
                } else if (text[i] == '}') {
                    brace_depth--;
                }
                if (brace_depth > 0) {
                    i++;
                }
            }
            if (brace_depth != 0) {
                IrSetError(p, "unterminated_brace", brace_start);
                return -1;
            }
            brace_end = i;

            node_idx = IrAddNode(p, tag, pos, depth, parent_idx);
            if (node_idx < 0) {
                IrSetError(p, "max_nodes_exceeded", pos);
                return -1;
            }
            if (parent_idx >= 0) {
                IrAddChild(p, parent_idx, node_idx);
            }

            IrSetNodeContent(p, node_idx, text + content_start, brace_end - content_start);

            IrParseBclInner(p, text, content_start, brace_end, depth + 1, node_idx);

            if (!p->parse_ok) {
                return -1;
            }

            pos = brace_end + 1;
            continue;
        }
        pos++;
    }
    return 0;
}

static int IrParser_Parse(BclIrParseResult *p, const char *bcl_text) {
    if (!p || !bcl_text) {
        return 0;
    }
    p->node_count = 0;
    p->parse_ok = 1;
    p->error_msg[0] = '\0';
    p->error_pos = -1;
    IrParseBclInner(p, bcl_text, 0, (int)strlen(bcl_text), 0, -1);
    return p->parse_ok ? 1 : 0;
}

/* ════════════════════════════════════════════
 * DOMAIN TABLE — 10 common domains (C version)
 * Full 75-domain routing lives in MySQL.
 * ════════════════════════════════════════════ */

static const char *DOMAIN_NAMES[BCLIR_DOMAIN_COUNT] = {
    "security", "network", "storage", "parser", "graph",
    "error",    "report",  "config",  "database", "ui"
};

/* ════════════════════════════════════════════
 * API — Init
 * ════════════════════════════════════════════ */

void BclIrGraph_Init(BclIrGraph *ir) {
    if (!ir) {
        return;
    }
    memset(ir, 0, sizeof(BclIrGraph));
    ir->parse_ok = 1;
    ir->error_pos = -1;
    ir->computed = 0;
}

/* ════════════════════════════════════════════
 * API — Parse
 * Runs the embedded syntax-only parser and copies
 * the resulting node tree into the IR graph.
 * ════════════════════════════════════════════ */

int BclIrGraph_Parse(BclIrGraph *ir, const char *bcl_text) {
    BclIrParseResult pr;
    int i;

    if (!ir || !bcl_text) {
        return 0;
    }

    IrParser_Init(&pr);
    if (!IrParser_Parse(&pr, bcl_text)) {
        ir->parse_ok = 0;
        strncpy(ir->error_msg, pr.error_msg, sizeof(ir->error_msg) - 1);
        ir->error_msg[sizeof(ir->error_msg) - 1] = '\0';
        ir->error_pos = pr.error_pos;
        return 0;
    }

    /* copy parsed nodes into the IR graph */
    ir->node_count = pr.node_count;
    ir->parse_ok = 1;
    ir->error_msg[0] = '\0';
    ir->error_pos = -1;
    for (i = 0; i < pr.node_count; i++) {
        ir->nodes[i] = pr.nodes[i];
    }
    return 1;
}

/* ════════════════════════════════════════════
 * API — ComputeTokenIds
 * djb2 hash of tag string, modulo vocab size.
 * ════════════════════════════════════════════ */

void BclIrGraph_ComputeTokenIds(BclIrGraph *ir) {
    int i;
    unsigned long hash;
    const char *s;

    if (!ir) {
        return;
    }
    for (i = 0; i < ir->node_count; i++) {
        hash = 5381;
        s = ir->nodes[i].tag;
        while (*s) {
            hash = ((hash << 5) + hash) + (unsigned char)(*s);
            s++;
        }
        ir->token_ids[i] = (int)(hash % BCLIR_VOCAB_SIZE);
    }
}

/* ════════════════════════════════════════════
 * API — ComputePE
 * 384-dim sinusoidal positional encoding.
 *   first  192 dims: sinusoidal from depth
 *   last   192 dims: sinusoidal from sibling index
 * ════════════════════════════════════════════ */

void BclIrGraph_ComputePE(BclIrGraph *ir) {
    int i, j;
    int pos_depth, pos_sib;
    int half;
    float div_term;

    if (!ir) {
        return;
    }
    half = BCLIR_PE_DIM / 2;  /* 192 */

    for (i = 0; i < ir->node_count; i++) {
        pos_depth = ir->nodes[i].depth;

        /* sibling index: position among parent's children */
        pos_sib = 0;
        if (ir->nodes[i].parent_idx >= 0) {
            BclIrNode *parent = &ir->nodes[ir->nodes[i].parent_idx];
            int c;
            for (c = 0; c < parent->child_count; c++) {
                if (parent->children[c] == i) {
                    pos_sib = c;
                    break;
                }
            }
        }

        for (j = 0; j < half; j++) {
            div_term = (float)pow(10000.0, (double)(2 * (j / 2)) / (double)BCLIR_PE_DIM);
            /* first half from depth */
            ir->pe_matrix[i][2 * j]     = (float)sin((double)pos_depth / div_term);
            ir->pe_matrix[i][2 * j + 1] = (float)cos((double)pos_depth / div_term);
            /* second half from sibling index */
            ir->pe_matrix[i][half + 2 * j]     = (float)sin((double)pos_sib / div_term);
            ir->pe_matrix[i][half + 2 * j + 1] = (float)cos((double)pos_sib / div_term);
        }
    }
}

/* ════════════════════════════════════════════
 * API — ComputeMask
 * mask[i][j] = 0 (allow) if:
 *   i == j (self)
 *   j is in i's ancestor chain
 *   i and j share the same parent (siblings)
 * mask[i][j] = 1 (block) otherwise
 * ════════════════════════════════════════════ */

static int IsAncestor(BclIrGraph *ir, int i, int j) {
    /* walk i's parent chain; return 1 if j is an ancestor of i */
    int cur = ir->nodes[i].parent_idx;
    while (cur >= 0) {
        if (cur == j) {
            return 1;
        }
        cur = ir->nodes[cur].parent_idx;
    }
    return 0;
}

void BclIrGraph_ComputeMask(BclIrGraph *ir) {
    int i, j;

    if (!ir) {
        return;
    }
    for (i = 0; i < ir->node_count; i++) {
        for (j = 0; j < ir->node_count; j++) {
            if (i == j) {
                ir->mask[i][j] = 0;            /* self */
            } else if (IsAncestor(ir, i, j)) {
                ir->mask[i][j] = 0;            /* ancestor */
            } else if (ir->nodes[i].parent_idx == ir->nodes[j].parent_idx) {
                ir->mask[i][j] = 0;            /* siblings (incl. both root) */
            } else {
                ir->mask[i][j] = 1;            /* block */
            }
        }
    }
}

/* ════════════════════════════════════════════
 * API — ComputeDomains
 * Substring match tag against 10 domain names.
 * domain_ids[i] = index or -1.
 * ════════════════════════════════════════════ */

static int LowerContains(const char *haystack, const char *needle) {
    char buf[BCLIR_MAX_TAG];
    int i;
    size_t hlen, nlen, k;

    for (i = 0; i < BCLIR_MAX_TAG - 1 && haystack[i]; i++) {
        buf[i] = (char)tolower((unsigned char)haystack[i]);
    }
    buf[i] = '\0';
    hlen = strlen(buf);
    nlen = strlen(needle);
    if (nlen == 0 || nlen > hlen) {
        return 0;
    }
    for (k = 0; k + nlen <= hlen; k++) {
        if (strncmp(buf + k, needle, nlen) == 0) {
            return 1;
        }
    }
    return 0;
}

void BclIrGraph_ComputeDomains(BclIrGraph *ir) {
    int i, d;

    if (!ir) {
        return;
    }
    for (i = 0; i < ir->node_count; i++) {
        ir->domain_ids[i] = -1;
        for (d = 0; d < BCLIR_DOMAIN_COUNT; d++) {
            if (LowerContains(ir->nodes[i].tag, DOMAIN_NAMES[d])) {
                ir->domain_ids[i] = d;
                break;
            }
        }
    }
}

/* ════════════════════════════════════════════
 * API — ComputeGraphBias
 * T5-style graph bias for each pair (i, j):
 *   1.0  j is i's parent        (FEEDS)
 *   1.0  i and j are siblings   (PAIRS)
 *   0.5  j is i's ancestor      (ENABLES, weak)
 *   0.3  different subtree      (MEASURES, low)
 *   0.0  otherwise
 *   diagonal = 1.0 (self-attn baseline)
 * ════════════════════════════════════════════ */

void BclIrGraph_ComputeGraphBias(BclIrGraph *ir) {
    int i, j;
    int same_subtree;

    if (!ir) {
        return;
    }
    for (i = 0; i < ir->node_count; i++) {
        for (j = 0; j < ir->node_count; j++) {
            if (i == j) {
                ir->graph_bias[i][j] = 1.0f;   /* self */
                continue;
            }
            if (ir->nodes[i].parent_idx == j) {
                ir->graph_bias[i][j] = 1.0f;   /* FEEDS: j is parent */
                continue;
            }
            if (ir->nodes[i].parent_idx == ir->nodes[j].parent_idx) {
                ir->graph_bias[i][j] = 1.0f;   /* PAIRS: siblings */
                continue;
            }
            if (IsAncestor(ir, i, j)) {
                ir->graph_bias[i][j] = 0.5f;   /* ENABLES: ancestor (weak) */
                continue;
            }
            /* MEASURES: different subtree?
             * same subtree = one is ancestor of the other.
             * already handled ancestor above, so if not ancestor
             * and not sibling -> different subtree */
            same_subtree = IsAncestor(ir, j, i);  /* i is ancestor of j? */
            if (same_subtree) {
                /* i is ancestor of j — covered conceptually as ENABLES reverse;
                 * treat as weak too */
                ir->graph_bias[i][j] = 0.5f;
            } else {
                ir->graph_bias[i][j] = 0.3f;   /* MEASURES: different subtree */
            }
        }
    }
}

/* ════════════════════════════════════════════
 * API — ComputeAll
 * ════════════════════════════════════════════ */

void BclIrGraph_ComputeAll(BclIrGraph *ir) {
    if (!ir) {
        return;
    }
    BclIrGraph_ComputeTokenIds(ir);
    BclIrGraph_ComputePE(ir);
    BclIrGraph_ComputeMask(ir);
    BclIrGraph_ComputeDomains(ir);
    BclIrGraph_ComputeGraphBias(ir);
    ir->computed = 1;
}

/* ════════════════════════════════════════════
 * API — Print (debugging)
 * ════════════════════════════════════════════ */

void BclIrGraph_Print(BclIrGraph *ir) {
    int i, j;
    int show;

    if (!ir) {
        printf("[BclIrGraph] NULL\n");
        return;
    }

    printf("=== BCL IR GRAPH ===\n");
    printf("node_count : %d\n", ir->node_count);
    printf("parse_ok   : %d\n", ir->parse_ok);
    printf("computed   : %d\n", ir->computed);
    if (ir->parse_ok == 0) {
        printf("error      : %s (pos %d)\n", ir->error_msg, ir->error_pos);
    }

    printf("\n--- NODES ---\n");
    for (i = 0; i < ir->node_count; i++) {
        printf("[%2d] tag=%-12s depth=%d parent=%d token_id=%d domain_id=%d\n",
               i, ir->nodes[i].tag, ir->nodes[i].depth,
               ir->nodes[i].parent_idx, ir->token_ids[i], ir->domain_ids[i]);
    }

    printf("\n--- PE MATRIX ---\n");
    printf("shape: [%d][%d]\n", ir->node_count, BCLIR_PE_DIM);
    for (i = 0; i < ir->node_count; i++) {
        float sum = 0.0f;
        for (j = 0; j < BCLIR_PE_DIM; j++) {
            sum += ir->pe_matrix[i][j] * ir->pe_matrix[i][j];
        }
        printf("[%2d] L2norm=%.4f  first4=[%.3f, %.3f, %.3f, %.3f]\n",
               i, (float)sqrt((double)sum),
               ir->pe_matrix[i][0], ir->pe_matrix[i][1],
               ir->pe_matrix[i][2], ir->pe_matrix[i][3]);
    }

    show = ir->node_count < 10 ? ir->node_count : 10;
    printf("\n--- MASK MATRIX (first %dx%d, 0=allow 1=block) ---\n", show, show);
    printf("     ");
    for (j = 0; j < show; j++) {
        printf("%3d ", j);
    }
    printf("\n");
    for (i = 0; i < show; i++) {
        printf("[%2d] ", i);
        for (j = 0; j < show; j++) {
            printf("  %d ", ir->mask[i][j]);
        }
        printf("\n");
    }

    printf("\n--- GRAPH BIAS MATRIX (first %dx%d) ---\n", show, show);
    printf("     ");
    for (j = 0; j < show; j++) {
        printf("%5d ", j);
    }
    printf("\n");
    for (i = 0; i < show; i++) {
        printf("[%2d] ", i);
        for (j = 0; j < show; j++) {
            printf("%5.2f ", ir->graph_bias[i][j]);
        }
        printf("\n");
    }
    printf("\n=== END BCL IR GRAPH ===\n");
}
