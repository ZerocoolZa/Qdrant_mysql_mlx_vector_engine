//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_ir_graph.h" date="2026-06-29" author="Devin" session_id="bcl-ir-graph" context="BCL IR Graph — central hub that parses BCL once and computes ALL structural signals for the transformer (token IDs, positional encoding, attention mask, domain IDs, graph bias)"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_ir_graph.h" domain="bcl_c_engine" authority="BclIrGraph"}
//[@SUMMARY]{summary="BCL IR Graph header — defines BclIrGraph struct (nodes + token_ids + pe_matrix + mask + domain_ids + graph_bias) and declares the API that parses BCL once and computes every transformer signal in a single pass"}
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

#ifndef BCL_IR_GRAPH_H
#define BCL_IR_GRAPH_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>

/* ════════════════════════════════════════════
 * CONSTANTS
 * ════════════════════════════════════════════ */

#define BCLIR_MAX_NODES    256
#define BCLIR_MAX_CONTENT  4096
#define BCLIR_MAX_TAG      64
#define BCLIR_PE_DIM       384     /* positional encoding dimensionality */
#define BCLIR_VOCAB_SIZE   162612  /* djb2 hash modulo vocab size */
#define BCLIR_DOMAIN_COUNT 10      /* C version: 10 common domains */

/* ════════════════════════════════════════════
 * BCL NODE — one parsed [@TAG]{content} packet
 * (mirrors BclNode from bcl_engine.h so this
 *  header is self-contained — no tree_sitter)
 * ════════════════════════════════════════════ */

typedef struct {
    char tag[BCLIR_MAX_TAG];        /* container name */
    char content[BCLIR_MAX_CONTENT];/* raw text between braces */
    int  start_pos;
    int  end_pos;
    int  depth;                     /* nesting depth -> positional encoding */
    int  parent_idx;                /* -1 = root -> attention mask */
    int  child_count;
    int  children[32];              /* child indices -> attention mask */
} BclIrNode;

typedef struct {
    BclIrNode nodes[BCLIR_MAX_NODES];
    int       node_count;
    int       parse_ok;
    char      error_msg[256];
    int       error_pos;
} BclIrParseResult;

/* ════════════════════════════════════════════
 * BCL IR GRAPH — the central hub.
 * Parses BCL once, then computes ALL transformer
 * structural signals in a single pass:
 *   token_ids   — tag -> vocab hash -> ID
 *   pe_matrix   — depth + path -> sinusoidal
 *   mask        — parent/children -> 0/1
 *   domain_ids  — class name -> domain (0-9, -1)
 *   graph_bias  — graph edges -> T5-style bias
 * ════════════════════════════════════════════ */

typedef struct {
    BclIrNode nodes[BCLIR_MAX_NODES];
    int   node_count;
    int   parse_ok;
    char  error_msg[256];
    int   error_pos;

    int   token_ids[BCLIR_MAX_NODES];        /* tag -> vocab hash -> ID */
    float pe_matrix[BCLIR_MAX_NODES][BCLIR_PE_DIM]; /* depth + path -> sinusoidal */
    char  mask[BCLIR_MAX_NODES][BCLIR_MAX_NODES];   /* parent/children -> 0/1 */
    int   domain_ids[BCLIR_MAX_NODES];       /* class name -> domain (0-9, -1=unknown) */
    float graph_bias[BCLIR_MAX_NODES][BCLIR_MAX_NODES]; /* graph edges -> T5-style bias */
    int   computed;
} BclIrGraph;

/* ════════════════════════════════════════════
 * API
 * ════════════════════════════════════════════ */

void BclIrGraph_Init(BclIrGraph *ir);
int  BclIrGraph_Parse(BclIrGraph *ir, const char *bcl_text);   /* returns 1=ok, 0=error */
void BclIrGraph_ComputeTokenIds(BclIrGraph *ir);
void BclIrGraph_ComputePE(BclIrGraph *ir);
void BclIrGraph_ComputeMask(BclIrGraph *ir);
void BclIrGraph_ComputeDomains(BclIrGraph *ir);
void BclIrGraph_ComputeGraphBias(BclIrGraph *ir);
void BclIrGraph_ComputeAll(BclIrGraph *ir);
void BclIrGraph_Print(BclIrGraph *ir);

#endif /* BCL_IR_GRAPH_H */
