//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_validator.c" date="2026-06-29" author="cascade+devin" session_id="bcl-c-central-db" context="BCL C Engine Layer 2 — semantic validator. Checks parsed tree against dictionary rules. Parser → Validator → Runtime."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_validator.c" domain="bcl_c_engine" authority="BclValidator"}
//[@SUMMARY]{summary="BCL semantic validator: checks parsed node tree against dictionary. Validates tag existence, parent/child rules, required children, repeatable/max_count constraints. Returns errors with problem/solution."}
//[@CLASS]{class="BclValidator" domain="bcl_c_engine" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Validate" type="command"}
//[@METHOD]{method="Print" type="command"}
//[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Semantic validator. Checks dictionary rules.>][@todos<none>]}

#include "bcl_engine.h"
#include <stdio.h>
#include <string.h>

/* ============================================================ */
/* DIM BLOCK — constants, locals, helpers                       */
/* ============================================================ */

#define ROOT_CONTEXT "body"

/* ---- local helpers ---- */

static int CountChildOccurrences(BclParseResult *tree, int parent_idx,
                                 const char *tag)
{
    BclNode *parent;
    int i;
    int count = 0;

    if (parent_idx < 0 || parent_idx >= tree->node_count) {
        return 0;
    }

    parent = &tree->nodes[parent_idx];

    for (i = 0; i < parent->child_count; i++) {
        int child_idx = parent->children[i];
        if (child_idx < 0 || child_idx >= tree->node_count) {
            continue;
        }
        if (strcmp(tree->nodes[child_idx].tag, tag) == 0) {
            count++;
        }
    }
    return count;
}

static int HasChildTag(BclParseResult *tree, int parent_idx, const char *tag)
{
    return CountChildOccurrences(tree, parent_idx, tag) > 0;
}

/* Check whether tag appears in a comma-separated list like "a,b,c" or "*" */
static int TagInList(const char *list, const char *tag)
{
    const char *p;
    const char *start;
    char buf[BCL_MAX_TAG];
    int len;

    if (list == NULL || list[0] == '\0') {
        return 0;
    }

    if (strcmp(list, "*") == 0) {
        return 1;
    }

    p = list;
    while (*p != '\0') {
        start = p;
        while (*p != '\0' && *p != ',') {
            p++;
        }
        len = (int)(p - start);
        if (len > 0 && len < BCL_MAX_TAG) {
            memcpy(buf, start, (size_t)len);
            buf[len] = '\0';
            if (strcmp(buf, tag) == 0) {
                return 1;
            }
        }
        if (*p == ',') {
            p++;
        }
    }
    return 0;
}

/* Add an error to the result if there is room */
static void AddError(ValidationResult *v, int node_idx, const char *tag,
                     const char *problem, const char *solution)
{
    ValidationError *e;

    if (v->error_count >= VAL_MAX_ERRORS) {
        return;
    }

    e = &v->errors[v->error_count];
    memset(e, 0, sizeof(ValidationError));

    if (tag != NULL) {
        strncpy(e->tag, tag, BCL_MAX_TAG - 1);
        e->tag[BCL_MAX_TAG - 1] = '\0';
    }
    if (problem != NULL) {
        strncpy(e->problem, problem, VAL_MAX_MSG - 1);
        e->problem[VAL_MAX_MSG - 1] = '\0';
    }
    if (solution != NULL) {
        strncpy(e->solution, solution, VAL_MAX_MSG - 1);
        e->solution[VAL_MAX_MSG - 1] = '\0';
    }
    e->node_idx = node_idx;

    v->error_count++;
    v->is_valid = 0;
}

/* ============================================================ */
/* INIT BLOCK — BclValidator_Init                               */
/* ============================================================ */

void BclValidator_Init(ValidationResult *v)
{
    if (v == NULL) {
        return;
    }
    memset(v, 0, sizeof(ValidationResult));
    v->error_count = 0;
    v->is_valid = 1;
}

/* ============================================================ */
/* GUTS BLOCK — BclValidator_Validate                           */
/* ============================================================ */

/* Step 1: per-node checks (tag existence + context validity) */
static void ValidateNodeTags(ValidationResult *v, BclParseResult *tree,
                             BclDictionary *dict)
{
    int i;
    char context[BCL_MAX_TAG];
    char problem[VAL_MAX_MSG];
    char solution[VAL_MAX_MSG];

    for (i = 0; i < tree->node_count; i++) {
        BclNode *node = &tree->nodes[i];

        /* 1a. tag existence */
        if (!BclDictionary_IsValidTag(dict, node->tag)) {
            snprintf(problem, VAL_MAX_MSG,
                     "Unknown tag: %s", node->tag);
            snprintf(solution, VAL_MAX_MSG,
                     "Check tag spelling or add to dictionary");
            AddError(v, i, node->tag, problem, solution);
            /* skip context check for unknown tags */
            continue;
        }

        /* 1b. context validity — use parent's valid_in as context */
        if (node->parent_idx < 0) {
            strncpy(context, ROOT_CONTEXT, BCL_MAX_TAG - 1);
            context[BCL_MAX_TAG - 1] = '\0';
        } else {
            BclNode *parent = &tree->nodes[node->parent_idx];
            char p_ns[BCL_MAX_TAG], p_vi[BCL_MAX_TAG], p_par[BCL_MAX_TAG], p_ch[BCL_MAX_CONTENT];
            int p_req, p_rep, p_mc;
            char p_dt[BCL_MAX_TAG];
            if (BclDictionary_Lookup(dict, parent->tag, p_ns, p_vi, p_par, p_ch,
                                     &p_req, &p_rep, &p_mc, p_dt)) {
                strncpy(context, p_vi, BCL_MAX_TAG - 1);
                context[BCL_MAX_TAG - 1] = '\0';
            } else {
                strncpy(context, ROOT_CONTEXT, BCL_MAX_TAG - 1);
                context[BCL_MAX_TAG - 1] = '\0';
            }
        }

        if (!BclDictionary_IsValidIn(dict, node->tag, context)) {
            snprintf(problem, VAL_MAX_MSG,
                     "Tag %s not valid in context %s",
                     node->tag, context);
            snprintf(solution, VAL_MAX_MSG,
                     "Move tag to correct context");
            AddError(v, i, node->tag, problem, solution);
        }
    }
}

/* Step 2: per-parent checks (allowed children, required, repeatable/max) */
static void ValidateParentRules(ValidationResult *v, BclParseResult *tree,
                                BclDictionary *dict)
{
    int i, j;
    char children_list[BCL_MAX_CONTENT];
    char namespace_out[BCL_MAX_TAG];
    char valid_in_out[BCL_MAX_TAG];
    char parent_out[BCL_MAX_TAG];
    char children_out[BCL_MAX_CONTENT];
    char datatype_out[BCL_MAX_TAG];
    int  required;
    int  repeatable;
    int  max_count;
    char problem[VAL_MAX_MSG];
    char solution[VAL_MAX_MSG];

    for (i = 0; i < tree->node_count; i++) {
        BclNode *parent = &tree->nodes[i];

        if (parent->child_count <= 0) {
            continue;
        }

        /* Look up parent tag in dictionary to get its children_allowed list */
        children_list[0] = '\0';
        namespace_out[0] = '\0';
        valid_in_out[0] = '\0';
        parent_out[0] = '\0';
        children_out[0] = '\0';
        datatype_out[0] = '\0';
        required = 0;
        repeatable = 0;
        max_count = 0;

        if (BclDictionary_Lookup(dict, parent->tag,
                                 namespace_out, valid_in_out,
                                 parent_out, children_out,
                                 &required, &repeatable, &max_count,
                                 datatype_out)) {
            strncpy(children_list, children_out, BCL_MAX_CONTENT - 1);
            children_list[BCL_MAX_CONTENT - 1] = '\0';
        }

        /* 2b. Check each child is allowed inside this parent */
        for (j = 0; j < parent->child_count; j++) {
            int child_idx = parent->children[j];
            BclNode *child;
            int req_flag;
            int min_count;
            int max_c;

            if (child_idx < 0 || child_idx >= tree->node_count) {
                continue;
            }
            child = &tree->nodes[child_idx];

            if (children_list[0] != '\0' &&
                !TagInList(children_list, child->tag)) {
                snprintf(problem, VAL_MAX_MSG,
                         "Tag %s not allowed inside %s",
                         child->tag, parent->tag);
                snprintf(solution, VAL_MAX_MSG,
                         "Remove %s from %s or update dictionary",
                         child->tag, parent->tag);
                AddError(v, child_idx, child->tag, problem, solution);
            }

            /* 2d. repeatable / max_count per child tag */
            req_flag = 0;
            min_count = 0;
            max_c = 0;
            if (BclDictionary_GetRule(dict, parent->tag, child->tag,
                                      &req_flag, &min_count, &max_c)) {
                int occ;

                if (!repeatable && max_c == 0) {
                    /* fall back to per-rule repeatable check via max_count */
                }

                occ = CountChildOccurrences(tree, i, child->tag);

                /* repeatable=0 means max 1 occurrence */
                if (max_c == 1 && occ > 1) {
                    snprintf(problem, VAL_MAX_MSG,
                             "Tag %s is not repeatable inside %s "
                             "(found %d, max 1)",
                             child->tag, parent->tag, occ);
                    snprintf(solution, VAL_MAX_MSG,
                             "Remove duplicate %s tags inside %s",
                             child->tag, parent->tag);
                    AddError(v, child_idx, child->tag, problem, solution);
                }

                if (max_c > 1 && occ > max_c) {
                    snprintf(problem, VAL_MAX_MSG,
                             "Tag %s exceeds max_count inside %s "
                             "(found %d, max %d)",
                             child->tag, parent->tag, occ, max_c);
                    snprintf(solution, VAL_MAX_MSG,
                             "Reduce %s occurrences inside %s to at most %d",
                             child->tag, parent->tag, max_c);
                    AddError(v, child_idx, child->tag, problem, solution);
                }
            }
        }

        /* 2c. Check required children.
         * Iterate the parent's children_allowed list and for each entry
         * query GetRule to see if required=1; if so verify presence. */
        if (children_list[0] != '\0') {
            const char *p = children_list;
            while (*p != '\0') {
                char buf[BCL_MAX_TAG];
                const char *start = p;
                int len;
                int req_flag = 0;
                int min_count = 0;
                int max_c = 0;

                while (*p != '\0' && *p != ',') {
                    p++;
                }
                len = (int)(p - start);
                if (len > 0 && len < BCL_MAX_TAG) {
                    memcpy(buf, start, (size_t)len);
                    buf[len] = '\0';

                    if (strcmp(buf, "*") != 0 &&
                        BclDictionary_GetRule(dict, parent->tag, buf,
                                              &req_flag, &min_count,
                                              &max_c)) {
                        if (req_flag && !HasChildTag(tree, i, buf)) {
                            snprintf(problem, VAL_MAX_MSG,
                                     "Required tag %s missing inside %s",
                                     buf, parent->tag);
                            snprintf(solution, VAL_MAX_MSG,
                                     "Add [@%s]{...} inside [@%s]{...}",
                                     buf, parent->tag);
                            AddError(v, i, buf, problem, solution);
                        }
                    }
                }
                if (*p == ',') {
                    p++;
                }
            }
        }
    }
}

int BclValidator_Validate(ValidationResult *v, BclParseResult *tree,
                          BclDictionary *dict)
{
    if (v == NULL || tree == NULL || dict == NULL) {
        return 0;
    }

    /* If the parser itself failed, the tree is not valid */
    if (!tree->parse_ok) {
        char problem[VAL_MAX_MSG];
        char solution[VAL_MAX_MSG];
        snprintf(problem, VAL_MAX_MSG,
                 "Parse failed: %s", tree->error_msg);
        snprintf(solution, VAL_MAX_MSG,
                 "Fix parse errors before validation");
        AddError(v, -1, "", problem, solution);
        return 0;
    }

    if (tree->node_count <= 0) {
        /* empty tree is valid */
        v->is_valid = 1;
        return 1;
    }

    ValidateNodeTags(v, tree, dict);
    ValidateParentRules(v, tree, dict);

    return v->is_valid ? 1 : 0;
}

/* ============================================================ */
/* PRINT BLOCK — BclValidator_Print                             */
/* ============================================================ */

void BclValidator_Print(ValidationResult *v)
{
    int i;

    if (v == NULL) {
        return;
    }

    if (v->error_count == 0) {
        fprintf(stderr, "[BclValidator] OK — no validation errors.\n");
        return;
    }

    fprintf(stderr, "[BclValidator] %d validation error(s):\n",
            v->error_count);

    for (i = 0; i < v->error_count; i++) {
        ValidationError *e = &v->errors[i];
        fprintf(stderr, "  [%d] tag=%s node=%d\n",
                i + 1,
                e->tag[0] ? e->tag : "(none)",
                e->node_idx);
        fprintf(stderr, "      problem:  %s\n", e->problem);
        fprintf(stderr, "      solution: %s\n", e->solution);
    }
}
