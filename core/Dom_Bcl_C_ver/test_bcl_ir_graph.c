//[@GHOST]{file_path="core/Dom_Bcl_C_ver/test_bcl_ir_graph.c" date="2026-06-29" author="Devin" session_id="bcl-ir-graph" context="Test harness for BCL IR Graph — parses a sample BCL packet, computes all transformer signals, prints the IR graph, and verifies node count, token IDs, PE non-zero, mask blocked entries, and domain IDs"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="test_bcl_ir_graph.c" domain="bcl_c_engine" authority="BclIrGraphTest"}
//[@SUMMARY]{summary="Test for BclIrGraph: parse sample packet, compute all signals, print, verify 4+ nodes, token_ids computed, PE non-zero, mask has blocked entries, domain_ids has -1 and 0+ values"}
//[@CLASS]{class="BclIrGraphTest" domain="bcl_c_engine" authority="single"}
//[@METHOD]{method="Run" type="command"}

#include "bcl_ir_graph.h"

static int CheckCondition(const char *name, int ok) {
    printf("  [%s] %s\n", ok ? "PASS" : "FAIL", name);
    return ok ? 1 : 0;
}

int main(void) {
    BclIrGraph ir;
    const char *bcl = "[@REPORT]{[@ERRORS]{(91;94)}[@FIXES]{(1;2)}[@SECURITY]{(99)}}";
    int i, j;
    int passes = 0;
    int total = 0;
    int has_blocked = 0;
    int has_minus_one = 0;
    int has_pos_domain = 0;
    int pe_nonzero = 0;

    printf(">>> BCL IR Graph Test <<<\n");
    printf("Input: %s\n\n", bcl);

    BclIrGraph_Init(&ir);

    if (!BclIrGraph_Parse(&ir, bcl)) {
        printf("PARSE FAILED: %s (pos %d)\n", ir.error_msg, ir.error_pos);
        return 1;
    }
    printf("Parse OK. node_count=%d\n\n", ir.node_count);

    BclIrGraph_ComputeAll(&ir);
    BclIrGraph_Print(&ir);

    printf("\n>>> VERIFICATION <<<\n");

    /* 1. 4+ nodes */
    total++; passes += CheckCondition("node_count >= 4", ir.node_count >= 4);

    /* 2. token_ids computed (non-zero) */
    {
        int tok_ok = 0;
        for (i = 0; i < ir.node_count; i++) {
            if (ir.token_ids[i] != 0) {
                tok_ok = 1;
                break;
            }
        }
        total++; passes += CheckCondition("token_ids computed (non-zero)", tok_ok);
    }

    /* 3. PE non-zero */
    for (i = 0; i < ir.node_count; i++) {
        for (j = 0; j < BCLIR_PE_DIM; j++) {
            if (ir.pe_matrix[i][j] != 0.0f) {
                pe_nonzero = 1;
                break;
            }
        }
        if (pe_nonzero) break;
    }
    total++; passes += CheckCondition("PE matrix non-zero", pe_nonzero);

    /* 4. mask has blocked entries (1s) */
    for (i = 0; i < ir.node_count && !has_blocked; i++) {
        for (j = 0; j < ir.node_count; j++) {
            if (ir.mask[i][j] == 1) {
                has_blocked = 1;
                break;
            }
        }
    }
    total++; passes += CheckCondition("mask has blocked entries", has_blocked);

    /* 5. domain_ids has -1 and 0+ values */
    for (i = 0; i < ir.node_count; i++) {
        if (ir.domain_ids[i] == -1) has_minus_one = 1;
        if (ir.domain_ids[i] >= 0) has_pos_domain = 1;
    }
    total++; passes += CheckCondition("domain_ids has -1 (unknown)", has_minus_one);
    total++; passes += CheckCondition("domain_ids has 0+ (matched)", has_pos_domain);

    printf("\n>>> RESULT: %d/%d checks passed <<<\n", passes, total);
    if (passes != total) {
        return 1;
    }
    printf(">>> ALL CHECKS PASSED <<<\n");
    return 0;
}
