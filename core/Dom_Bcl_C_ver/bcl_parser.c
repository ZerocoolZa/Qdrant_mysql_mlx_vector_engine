//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_parser.c" date="2026-06-29" author="cascade+devin" session_id="bcl-c-central-db" context="BCL C Engine Layer 2 — syntax-only parser. Knows ONLY [@TAG]{content} brackets. No semantic knowledge."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_parser.c" domain="bcl_c_engine" authority="BclParser"}
//[@SUMMARY]{summary="BCL packet parser: tokenizes [@TAG]{content} packets, builds in-memory node tree. Syntax only — no semantic validation. All tag meaning comes from dictionary."}
//[@CLASS]{class="BclParser" domain="bcl_c_engine" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Parse" type="command"}
//[@METHOD]{method="Validate" type="command"}
//[@METHOD]{method="Extract" type="command"}
//[@METHOD]{method="Free" type="command"}
//[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Syntax-only parser. No tag knowledge.>][@todos<none>]}

#include "bcl_engine.h"

/* ===== DIM BLOCK (declarations) ===== */

/* static result buffer for Extract-style string returns (no dynamic memory) */
static char RESULT_BUF[BCL_MAX_RESULT];

/* ===== INIT BLOCK (constructors + helpers) ===== */

/* zero out the parse result struct — no dynamic memory to manage */
void BclParser_Init(BclParseResult *p) {
    if (!p) {
        return;
    }
    memset(p, 0, sizeof(BclParseResult));
    p->parse_ok = 1;
    p->error_pos = -1;
}

/* zero out the parse result struct — no dynamic memory to free */
void BclParser_Free(BclParseResult *p) {
    if (!p) {
        return;
    }
    memset(p, 0, sizeof(BclParseResult));
    p->parse_ok = 0;
    p->error_pos = -1;
}

/* add a node to the tree; returns node index or -1 on overflow */
static int AddNode(BclParseResult *p, const char *tag, int start_pos, int depth, int parent_idx) {
    int idx;
    if (p->node_count >= BCL_MAX_NODES) {
        return -1;
    }
    idx = p->node_count;
    memset(&p->nodes[idx], 0, sizeof(BclNode));
    strncpy(p->nodes[idx].tag, tag, BCL_MAX_TAG - 1);
    p->nodes[idx].tag[BCL_MAX_TAG - 1] = '\0';
    p->nodes[idx].start_pos = start_pos;
    p->nodes[idx].depth = depth;
    p->nodes[idx].parent_idx = parent_idx;
    p->nodes[idx].child_count = 0;
    p->node_count++;
    return idx;
}

/* set raw content (text between braces) on a node */
static void SetNodeContent(BclParseResult *p, int idx, const char *content, int len) {
    int copy_len;
    if (idx < 0 || idx >= p->node_count) {
        return;
    }
    copy_len = len;
    if (copy_len >= BCL_MAX_CONTENT) {
        copy_len = BCL_MAX_CONTENT - 1;
    }
    if (copy_len > 0) {
        memcpy(p->nodes[idx].content, content, copy_len);
    }
    p->nodes[idx].content[copy_len] = '\0';
    p->nodes[idx].end_pos = p->nodes[idx].start_pos + len;
}

/* attach a child index to a parent node */
static void AddChild(BclParseResult *p, int parent_idx, int child_idx) {
    BclNode *parent;
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

/* set error state on the parse result */
static void SetError(BclParseResult *p, const char *msg, int pos) {
    p->parse_ok = 0;
    strncpy(p->error_msg, msg, sizeof(p->error_msg) - 1);
    p->error_msg[sizeof(p->error_msg) - 1] = '\0';
    p->error_pos = pos;
}

/* ===== FORWARD BLOCK (prototypes) ===== */

static int ParseBclInner(BclParseResult *p, const char *text, int pos, int end_pos, int depth, int parent_idx);

/* ===== DISPATCH BLOCK (entry points) ===== */

/* main entry: reset state, run recursive parser, return 1=ok 0=error */
int BclParser_Parse(BclParseResult *p, const char *bcl_text) {
    if (!p || !bcl_text) {
        return 0;
    }

    /* reset parser state */
    p->node_count = 0;
    p->parse_ok = 1;
    p->error_msg[0] = '\0';
    p->error_pos = -1;

    ParseBclInner(p, bcl_text, 0, (int)strlen(bcl_text), 0, -1);

    return p->parse_ok ? 1 : 0;
}

/* syntax check only — just reads the parse_ok flag set by Parse.
 * This is NOT semantic validation. Tag meaning lives in the dictionary. */
int BclParser_Validate(BclParseResult *p) {
    if (!p) {
        return 0;
    }
    return p->parse_ok ? 1 : 0;
}

/* find first node with matching tag name, copy its content to out buffer.
 * returns 1=found 0=not_found */
int BclParser_Extract(BclParseResult *p, const char *tag, char *out, size_t out_sz) {
    int i;
    if (!p || !tag || !out || out_sz == 0) {
        return 0;
    }
    out[0] = '\0';
    if (!p->parse_ok) {
        return 0;
    }
    for (i = 0; i < p->node_count; i++) {
        if (strncmp(p->nodes[i].tag, tag, BCL_MAX_TAG) == 0) {
            strncpy(out, p->nodes[i].content, out_sz - 1);
            out[out_sz - 1] = '\0';
            return 1;
        }
    }
    return 0;
}

/* ===== GUTS BLOCK (implementation) ===== */

/* recursive BCL parser: scans for [@TAG]{content}, tracks brace depth,
 * builds node tree. Knows ONLY bracket syntax — no tag semantics.
 *
 * Algorithm:
 *   1. Scan for [@ to find tag start
 *   2. Read tag name until ]
 *   3. Expect { after ]
 *   4. Find matching } (track brace depth for nested content)
 *   5. Add node with tag, content, start_pos, depth, parent_idx
 *   6. Recurse into content to find nested tags
 *   7. On error: set parse_ok=0, error_msg, error_pos
 */
static int ParseBclInner(BclParseResult *p, const char *text, int pos, int end_pos, int depth, int parent_idx) {
    int len;
    int i;
    int tag_start;
    int tag_end;
    int brace_start;
    int content_start;
    int brace_end;
    int brace_depth;
    int node_idx;
    char tag[BCL_MAX_TAG];

    len = end_pos;

    while (pos < len) {
        /* step 1: look for [@ to find tag start */
        if (text[pos] == '[' && pos + 1 < len && text[pos + 1] == '@') {
            tag_start = pos + 2;

            /* step 2: read tag name until ] */
            tag_end = tag_start;
            while (tag_end < len && text[tag_end] != ']' && text[tag_end] != '\0') {
                tag_end++;
            }
            if (tag_end >= len || text[tag_end] != ']') {
                SetError(p, "unterminated_tag", pos);
                return -1;
            }

            /* extract tag name into local buffer */
            i = 0;
            while (i < BCL_MAX_TAG - 1 && tag_start + i < tag_end) {
                tag[i] = text[tag_start + i];
                i++;
            }
            tag[i] = '\0';

            if (i == 0) {
                SetError(p, "empty_tag", pos);
                return -1;
            }

            /* step 3: expect { after ] */
            if (tag_end + 1 >= len || text[tag_end + 1] != '{') {
                /* tag without braces — skip it, not a packet */
                pos = tag_end + 1;
                continue;
            }
            brace_start = tag_end + 1;
            content_start = brace_start + 1;

            /* step 4: find matching } (track brace depth for nested content) */
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
                SetError(p, "unterminated_brace", brace_start);
                return -1;
            }
            brace_end = i;

            /* step 5: add node with tag, content, start_pos, depth, parent_idx */
            node_idx = AddNode(p, tag, pos, depth, parent_idx);
            if (node_idx < 0) {
                SetError(p, "max_nodes_exceeded", pos);
                return -1;
            }
            if (parent_idx >= 0) {
                AddChild(p, parent_idx, node_idx);
            }

            /* set content (raw text between braces) */
            SetNodeContent(p, node_idx, text + content_start, brace_end - content_start);

            /* step 6: recurse into content to find nested tags.
             * bound the scan to brace_end so nested recursions do not
             * re-discover sibling/ancestor nodes outside this node. */
            ParseBclInner(p, text, content_start, brace_end, depth + 1, node_idx);

            /* bail out early if a nested parse failed */
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
