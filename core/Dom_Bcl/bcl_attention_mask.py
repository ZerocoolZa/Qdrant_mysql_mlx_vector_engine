#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Bcl/bcl_attention_mask.py"
# date="2026-06-27" author="Cascade" session_id="bcl-attention-mask"
# context="BCL Structured Attention Mask — converts BCL AST into (seq_len, seq_len) additive mask for transformer attention"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_attention_mask.py" domain="BCL" authority="BclAttentionMask"}
# [@SUMMARY]{summary="BCL Attention Mask: flattens BCL AST into token sequence, builds structured attention mask. Sibling + ancestor attention, cousin masking, causal within arrays. O(N) per token."}
# [@CLASS]{class="BclAttentionMask" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="build_mask" type="command"}
# [@METHOD]{method="build_mask_ast" type="command"}
# [@METHOD]{method="explain" type="command"}
# [@METHOD]{method="info" type="command"}
# [@METHOD]{method="flatten_ast" type="command"}
# [@METHOD]{method="walk_node" type="command"}
# [@METHOD]{method="build_mask_matrix" type="command"}
# [@METHOD]{method="can_attend" type="helper"}
# [@METHOD]{method="token_label" type="helper"}
# [@METHOD]{method="build_explanation" type="command"}
# [@METHOD]{method="attend_reason" type="helper"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import numpy as np

from bcl_lexer import BCLTokenizer
from bcl_parser import BCLParser, BCLNode


ATTEND = 0.0
MASKED = -np.inf

RULE_SAME_CONTAINER = "a) same_container_sibling"
RULE_PARENT_NAME = "b) parent_name_attention"
RULE_ANCESTOR_PATH = "c) ancestor_path_attention"
RULE_COUSIN_MASK = "d) cousin_sibling_masking"
RULE_CAUSAL_ARRAY = "e) causal_within_arrays"


class BclAttentionMask:
    """Builds structured attention masks from BCL ASTs.

    Standard transformer attention is O(N^2) — every token attends to every other.
    BCL structure constrains this: a token inside [@ERRORS]{(91;94;97)} should
    attend to siblings (91, 94, 97) and ancestors ([@ERRORS], [@REPORT]) but NOT
    to tokens in cousin containers like [@FIXES]{(1;2;3)}.

    This makes attention O(N) in practice because each token only attends to
    its siblings within one container plus its ancestor path (depth of tree),
    not all N tokens in the sequence.

    Mask format: numpy array (seq_len, seq_len) of 0.0 (attend) and -inf (masked),
    ready to add to attention scores before softmax.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "causal": True,
                "mask_value": MASKED,
                "attend_value": ATTEND,
            },
            "tokens": [],
            "mask": None,
            "explain_lines": [],
            "seq_len": 0,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "build_mask":
            return self.BuildMask(params)
        elif command == "build_mask_ast":
            return self.BuildMaskAst(params)
        elif command == "explain":
            return self.Explain(params)
        elif command == "info":
            return self.Info(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Info(self, params):
        config = dict(self.state["config"])
        info = {
            "class": "BclAttentionMask",
            "version": 1,
            "domain": "BCL",
            "commands": ["build_mask", "build_mask_ast", "explain", "info",
                         "read_state", "set_config"],
            "rules": [
                RULE_SAME_CONTAINER,
                RULE_PARENT_NAME,
                RULE_ANCESTOR_PATH,
                RULE_COUSIN_MASK,
                RULE_CAUSAL_ARRAY,
            ],
            "mask_format": "numpy (seq_len, seq_len) float64, 0.0=attend, -inf=masked",
            "complexity": "O(N) per token via sibling window + ancestor path",
            "config": config,
        }
        return (1, info, None)

    def BuildMask(self, params):
        text = self._p(params, "text")
        if text is None:
            return (0, None, ("MISSING_PARAM", "text required", 0))
        tokenizer = BCLTokenizer()
        tok_result = tokenizer.Run("tokenize", {"text": text})
        if tok_result[0] == 0:
            return (0, None, ("LEXER_ERROR", str(tok_result[2]), 0))
        tokens = tok_result[1]["tokens"]
        parser = BCLParser()
        parse_result = parser.Run("parse", {"tokens": tokens})
        if parse_result[0] == 0:
            return (0, None, ("PARSER_ERROR", str(parse_result[2]), 0))
        root = parse_result[1]["root"]
        return self.BuildMaskAst({"root": root})

    def BuildMaskAst(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root (BCLNode AST) required", 0))
        flat_result = self.FlattenAst(root)
        if flat_result[0] == 0:
            return flat_result
        flat_tokens = flat_result[1]
        mask_result = self.BuildMaskMatrix(flat_tokens)
        if mask_result[0] == 0:
            return mask_result
        mask = mask_result[1]
        labels = []
        for t in flat_tokens:
            lbl_result = self.TokenLabel(t)
            labels.append(lbl_result[1])
        self.state["tokens"] = flat_tokens
        self.state["mask"] = mask
        self.state["seq_len"] = len(flat_tokens)
        result = {
            "mask": mask,
            "seq_len": len(flat_tokens),
            "tokens": flat_tokens,
            "token_labels": labels,
        }
        return (1, result, None)

    def Explain(self, params):
        text = self._p(params, "text")
        if text is None:
            return (0, None, ("MISSING_PARAM", "text required", 0))
        tokenizer = BCLTokenizer()
        tok_result = tokenizer.Run("tokenize", {"text": text})
        if tok_result[0] == 0:
            return (0, None, ("LEXER_ERROR", str(tok_result[2]), 0))
        parser = BCLParser()
        parse_result = parser.Run("parse", {"tokens": tok_result[1]["tokens"]})
        if parse_result[0] == 0:
            return (0, None, ("PARSER_ERROR", str(parse_result[2]), 0))
        root = parse_result[1]["root"]
        flat_result = self.FlattenAst(root)
        if flat_result[0] == 0:
            return flat_result
        flat_tokens = flat_result[1]
        mask_result = self.BuildMaskMatrix(flat_tokens)
        if mask_result[0] == 0:
            return mask_result
        mask = mask_result[1]
        explain_result = self.BuildExplanation(flat_tokens, mask)
        if explain_result[0] == 0:
            return explain_result
        lines = explain_result[1]
        self.state["tokens"] = flat_tokens
        self.state["mask"] = mask
        self.state["seq_len"] = len(flat_tokens)
        self.state["explain_lines"] = lines
        return (1, {
            "explanation": "\n".join(lines),
            "lines": lines,
            "seq_len": len(flat_tokens),
            "mask": mask,
        }, None)

    def FlattenAst(self, root):
        tokens = []
        for child in root.state["children"]:
            walk_result = self.WalkNode(child, tokens, [])
            if walk_result[0] == 0:
                return walk_result
        return (1, tokens, None)

    def WalkNode(self, node, tokens, ancestor_indices):
        name_idx = len(tokens)
        tokens.append({
            "type": "container_name",
            "value": node.state["name"],
            "container": node,
            "ancestor_indices": list(ancestor_indices),
            "tuple_index": None,
            "tuple_id": None,
            "name_token_idx": name_idx,
        })
        my_ancestors = list(ancestor_indices) + [name_idx]
        for tuple_idx, tup in enumerate(node.state["tuples"]):
            for val_idx, val in enumerate(tup):
                tokens.append({
                    "type": "value",
                    "value": val,
                    "container": node,
                    "ancestor_indices": list(my_ancestors),
                    "tuple_index": val_idx,
                    "tuple_id": (id(node), tuple_idx),
                    "name_token_idx": name_idx,
                })
        for child in node.state["children"]:
            child_result = self.WalkNode(child, tokens, my_ancestors)
            if child_result[0] == 0:
                return child_result
        return (1, True, None)

    def BuildMaskMatrix(self, tokens):
        n = len(tokens)
        if n == 0:
            empty = np.zeros((0, 0), dtype=np.float64)
            return (1, empty, None)
        mask_value = self.state["config"].get("mask_value", MASKED)
        attend_value = self.state["config"].get("attend_value", ATTEND)
        causal = self.state["config"].get("causal", True)
        mask = np.full((n, n), mask_value, dtype=np.float64)
        for i in range(n):
            mask[i][i] = attend_value
            ti = tokens[i]
            ti_ancestors = ti["ancestor_indices"]
            ti_container = ti["container"]
            ti_tuple_id = ti["tuple_id"]
            ti_tuple_index = ti["tuple_index"]
            for j in range(n):
                if i == j:
                    continue
                tj = tokens[j]
                attend = False
                if j in ti_ancestors:
                    attend = True
                if not attend and ti_container is tj["container"]:
                    if causal and ti_tuple_id is not None and ti_tuple_id == tj["tuple_id"]:
                        if tj["tuple_index"] <= ti_tuple_index:
                            attend = True
                    else:
                        attend = True
                if attend:
                    mask[i][j] = attend_value
        return (1, mask, None)

    def CanAttend(self, ti, tj, j, causal=True):
        if j in ti["ancestor_indices"]:
            return (1, True, None)
        if ti["container"] is tj["container"]:
            if causal and ti["tuple_id"] is not None and ti["tuple_id"] == tj["tuple_id"]:
                if tj["tuple_index"] <= ti["tuple_index"]:
                    return (1, True, None)
                return (1, False, None)
            return (1, True, None)
        return (1, False, None)

    def TokenLabel(self, t):
        if t["type"] == "container_name":
            return (1, "[@%s]" % t["value"], None)
        return (1, str(t["value"]), None)

    def AttendReason(self, ti, tj, j):
        if j in ti["ancestor_indices"]:
            return (1, "ancestor", None)
        if ti["container"] is tj["container"]:
            if ti["tuple_id"] is not None and ti["tuple_id"] == tj["tuple_id"]:
                return (1, "sibling+causal", None)
            if ti["type"] == "container_name" and tj["type"] == "value":
                return (1, "own_values", None)
            if ti["type"] == "value" and tj["type"] == "container_name":
                return (1, "parent_name", None)
            return (1, "sibling", None)
        return (1, "unknown", None)

    def BuildExplanation(self, tokens, mask):
        n = len(tokens)
        lines = []
        lines.append("BCL Attention Mask Explanation")
        lines.append("=" * 50)
        lines.append("Sequence length: %d tokens" % n)
        lines.append("")
        lines.append("Masking rules:")
        lines.append("  %s" % RULE_SAME_CONTAINER)
        lines.append("  %s" % RULE_PARENT_NAME)
        lines.append("  %s" % RULE_ANCESTOR_PATH)
        lines.append("  %s" % RULE_COUSIN_MASK)
        lines.append("  %s" % RULE_CAUSAL_ARRAY)
        lines.append("")
        lines.append("Token sequence:")
        for i in range(n):
            t = tokens[i]
            type_str = "CONTAINER" if t["type"] == "container_name" else "VALUE"
            lbl_result = self.TokenLabel(t)
            lbl = lbl_result[1]
            anc = t["ancestor_indices"]
            lines.append("  [%d] %s %s  ancestors=%s" % (i, type_str, lbl, anc))
        lines.append("")
        lines.append("Per-token attention:")
        lines.append("-" * 50)
        for i in range(n):
            ti = tokens[i]
            type_str = "CONTAINER" if ti["type"] == "container_name" else "VALUE"
            lbl_result = self.TokenLabel(ti)
            lbl = lbl_result[1]
            lines.append("")
            lines.append("Token %d [%s] %s:" % (i, type_str, lbl))
            attend_items = []
            mask_items = []
            for j in range(n):
                if i == j:
                    continue
                tj = tokens[j]
                tj_lbl_result = self.TokenLabel(tj)
                tj_lbl = tj_lbl_result[1]
                if mask[i][j] == 0.0:
                    reason_result = self.AttendReason(ti, tj, j)
                    reason = reason_result[1]
                    attend_items.append("  -> token %d %s  (%s)" % (j, tj_lbl, reason))
                else:
                    mask_items.append("  xx token %d %s" % (j, tj_lbl))
            lines.append("  ATTENDS TO:")
            lines.append("    -> self")
            for a in attend_items:
                lines.append("    %s" % a)
            if mask_items:
                lines.append("  MASKED FROM:")
                for m in mask_items:
                    lines.append("    %s" % m)
        lines.append("")
        lines.append("=" * 50)
        lines.append("Mask matrix (row=query, col=key, 1=attend, .=masked):")
        lines.append("")
        if n > 0:
            header = "       " + " ".join(["%3d" % j for j in range(n)])
            lines.append(header)
            for i in range(n):
                ti = tokens[i]
                lbl_result = self.TokenLabel(ti)
                lbl = lbl_result[1]
                cells = []
                for j in range(n):
                    if mask[i][j] == 0.0:
                        cells.append("  1")
                    else:
                        cells.append("  .")
                lines.append("%3d %s  %s" % (i, lbl.ljust(10), "".join(cells)))
        lines.append("")
        lines.append("Additive mask values: 0.0 = attend, -inf = masked")
        return (1, lines, None)
