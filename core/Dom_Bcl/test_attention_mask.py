#!/usr/bin/env python3
# Test script for BclAttentionMask

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from bcl_attention_mask import BclAttentionMask


def main():
    bcl_text = "[@REPORT]{[@ERRORS]{(91;94)}[@FIXES]{(1;2)}}"

    mask_builder = BclAttentionMask()

    # Test 1: info
    info_result = mask_builder.Run("info", {})
    print("=== INFO ===")
    print("ok:", info_result[0])
    for k, v in info_result[1].items():
        if k == "rules":
            print("  rules:")
            for r in v:
                print("    ", r)
        elif k == "commands":
            print("  commands:", v)
        else:
            print("  %s: %s" % (k, v))

    print()

    # Test 2: build_mask
    mask_result = mask_builder.Run("build_mask", {"text": bcl_text})
    print("=== BUILD_MASK ===")
    print("ok:", mask_result[0])
    if mask_result[0] == 1:
        data = mask_result[1]
        mask = data["mask"]
        seq_len = data["seq_len"]
        labels = data["token_labels"]
        print("seq_len:", seq_len)
        print("token_labels:", labels)
        print()
        print("Mask matrix (0.0=attend, -inf=masked):")
        print("Row=query, Col=key")
        header = "          " + "  ".join(["%6s" % l for l in labels])
        print(header)
        for i in range(seq_len):
            row_vals = []
            for j in range(seq_len):
                if mask[i][j] == 0.0:
                    row_vals.append("  ATT ")
                else:
                    row_vals.append("  MSK ")
            print("%6s  %s" % (labels[i], "".join(row_vals)))
        print()
        # Verify mask shape and dtype
        print("shape:", mask.shape)
        print("dtype:", mask.dtype)
        print()

        # Verify specific rules
        print("=== RULE VERIFICATION ===")
        # Token layout: 0=REPORT, 1=ERRORS, 2=91, 3=94, 4=FIXES, 5=1, 6=2

        # Rule a: same container sibling attention
        # 91 (idx 2) and 94 (idx 3) are in same container ERRORS
        # 94 should attend to 91 (earlier in array)
        assert mask[3][2] == 0.0, "Rule a: 94 should attend to 91 (sibling)"
        print("Rule a (same container): 94 attends to 91 = PASS")

        # Rule b: parent container name attention
        # 91 (idx 2) should attend to ERRORS (idx 1, parent name)
        assert mask[2][1] == 0.0, "Rule b: 91 should attend to ERRORS (parent name)"
        print("Rule b (parent name): 91 attends to ERRORS = PASS")

        # Rule c: ancestor path attention
        # 91 (idx 2) should attend to REPORT (idx 0, ancestor)
        assert mask[2][0] == 0.0, "Rule c: 91 should attend to REPORT (ancestor)"
        print("Rule c (ancestor path): 91 attends to REPORT = PASS")

        # Rule d: cousin sibling masking
        # 91 (idx 2) should NOT attend to 1 (idx 5, cousin container FIXES)
        assert mask[2][5] == -np.inf, "Rule d: 91 should NOT attend to 1 (cousin)"
        # ERRORS (idx 1) should NOT attend to FIXES (idx 4, sibling container)
        assert mask[1][4] == -np.inf, "Rule d: ERRORS should NOT attend to FIXES (cousin)"
        print("Rule d (cousin masking): 91 NOT attend to 1, ERRORS NOT attend to FIXES = PASS")

        # Rule e: causal within arrays
        # 91 (idx 2) should NOT attend to 94 (idx 3, later in same array)
        assert mask[2][3] == -np.inf, "Rule e: 91 should NOT attend to 94 (causal, later)"
        # 1 (idx 5) should NOT attend to 2 (idx 6, later in same array)
        assert mask[5][6] == -np.inf, "Rule e: 1 should NOT attend to 2 (causal, later)"
        print("Rule e (causal arrays): 91 NOT attend to 94, 1 NOT attend to 2 = PASS")

        # Self attention
        for i in range(seq_len):
            assert mask[i][i] == 0.0, "Self-attention should always be allowed"
        print("Self-attention: all diagonal = 0.0 = PASS")

        print()
        print("ALL ASSERTIONS PASSED")

    print()

    # Test 3: explain
    explain_result = mask_builder.Run("explain", {"text": bcl_text})
    print("=== EXPLAIN ===")
    print("ok:", explain_result[0])
    if explain_result[0] == 1:
        print(explain_result[1]["explanation"])

    print()
    print("=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    main()
