#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Bcl/bcl_positional_encoding.py"
# date="2026-06-27" author="Cascade" session_id="bcl-pos-enc"
# context="BCL Positional Encoding: structural PE from BCL AST depth, path position, container type"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_positional_encoding.py" domain="BCL" authority="BclPositionalEncoding"}
# [@SUMMARY]{summary="BCL Positional Encoding: converts BCL AST into a (seq_len, 384) PE matrix using depth + path + type signals."}
# [@CLASS]{class="BclPositionalEncoding" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="encode" type="command"}
# [@METHOD]{method="encode_ast" type="command"}
# [@METHOD]{method="encode_depth" type="command"}
# [@METHOD]{method="info" type="command"}
# [@METHOD]{method="flatten_ast" type="command"}
# [@METHOD]{method="sinusoidal" type="helper"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sys
import math

import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from bcl_lexer import BCLTokenizer
from bcl_parser import BCLParser

# ─── CONSTANTS ───────────────────────────────────────────────────────────────

D_MODEL = 384
HALF_DIM = 192
MAX_DEPTH = 256
NUM_TYPES = 4
TYPE_DIMS = D_MODEL

TYPE_CONTAINER = 0
TYPE_HANDS = 1
TYPE_ARRAY = 2
TYPE_VALUE = 3

TYPE_NAMES = {
    TYPE_CONTAINER: "container",
    TYPE_HANDS: "hands",
    TYPE_ARRAY: "array",
    TYPE_VALUE: "value",
}

BASE_10000 = 10000.0
SEED = 1337


class BclPositionalEncoding:
    """BCL structural positional encoding.

    Three signals per token:
      1. depth_signal  — sinusoidal from container nesting depth (0..256), HALF_DIM dims
      2. path_signal   — sinusoidal from ordinal position among siblings, HALF_DIM dims
      3. type_embedding — learned D_MODEL-dim vector per container type, added on top

    Final vector = concat(depth_signal[HALF_DIM], path_signal[HALF_DIM]) + type_embedding[D_MODEL]
    Output shape: (seq_len, D_MODEL).
    """

    def __init__(self, mem=None, db=None, param=None):
        rng = np.random.RandomState(SEED)
        type_embeddings = {}
        for type_id in range(NUM_TYPES):
            type_embeddings[type_id] = rng.normal(0.0, 0.02, size=(D_MODEL,)).astype(np.float32)
        self.state = {
            "config": {
                "d_model": D_MODEL,
                "half_dim": HALF_DIM,
                "max_depth": MAX_DEPTH,
                "num_types": NUM_TYPES,
                "base": BASE_10000,
                "seed": SEED,
            },
            "type_embeddings": type_embeddings,
            "last_tokens": [],
            "last_matrix": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "encode":
            return self.Encode(params)
        elif command == "encode_ast":
            return self.EncodeAst(params)
        elif command == "encode_depth":
            return self.EncodeDepth(params)
        elif command == "info":
            return self.Info(params)
        elif command == "flatten_ast":
            return self.FlattenAst(params)
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

    # ─── CORE ENCODING ───────────────────────────────────────────────────────

    def Sinusoidal(self, position, dims):
        """Standard sinusoidal encoding for a scalar position over `dims` dimensions."""
        if dims <= 0:
            return np.zeros(0, dtype=np.float32)
        half = dims // 2
        out = np.zeros(dims, dtype=np.float32)
        denom = np.power(BASE_10000, (2.0 * np.arange(half)) / float(dims)).astype(np.float32)
        out[0:2 * half:2] = np.sin(position / denom)
        out[1:2 * half:2] = np.cos(position / denom)
        if dims % 2 == 1:
            out[2 * half] = float(math.sin(position / (BASE_10000 ** (2.0 * half / float(dims)))))
        return out

    def DepthSignal(self, depth):
        """Sinusoidal encoding from container depth, normalized to [0,1] then scaled."""
        max_depth = self.state["config"].get("max_depth", MAX_DEPTH)
        depth_norm = float(min(max(depth, 0), max_depth)) / float(max_depth)
        scaled = depth_norm * float(max_depth)
        return self.Sinusoidal(scaled, HALF_DIM)

    def PathSignal(self, path_pos):
        """Sinusoidal encoding from ordinal sibling position."""
        return self.Sinusoidal(float(path_pos), HALF_DIM)

    def TypeEmbedding(self, type_id):
        """Learned D_MODEL-dim embedding for a container type."""
        embeddings = self.state["type_embeddings"]
        if type_id not in embeddings:
            return np.zeros(D_MODEL, dtype=np.float32)
        return embeddings[type_id].copy()

    def EncodeToken(self, depth, path_pos, type_id):
        """Combine the three signals into one D_MODEL vector."""
        depth_part = self.DepthSignal(depth)
        path_part = self.PathSignal(path_pos)
        combined = np.zeros(D_MODEL, dtype=np.float32)
        combined[0:HALF_DIM] = depth_part
        combined[HALF_DIM:D_MODEL] = path_part
        combined = combined + self.TypeEmbedding(type_id)
        return combined

    # ─── AST FLATTENING ──────────────────────────────────────────────────────

    def FlattenAst(self, params):
        """Flatten a BCL AST (parser root) into a list of structural tokens.

        Each token is a dict: {"depth": int, "path_pos": int, "type": int, "name": str}.
        Pre-order DFS. Synthetic 'root' node is skipped; top-level containers start at depth 0.
        """
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        tokens = []
        children = root.state.get("children", [])
        for idx, child in enumerate(children):
            self.WalkNode(child, 0, idx, tokens)
        self.state["last_tokens"] = tokens
        return (1, {"tokens": tokens, "count": len(tokens)}, None)

    def WalkNode(self, node, depth, path_pos, tokens):
        """Recursively walk one BCLNode, emitting container/hands/array/value tokens."""
        name = node.state.get("name", "")
        tuples = node.state.get("tuples", [])
        children = node.state.get("children", [])
        tokens.append({"depth": depth, "path_pos": path_pos,
                       "type": TYPE_CONTAINER, "name": name})
        has_body = len(tuples) > 0 or len(children) > 0
        body_depth = depth + 1
        if has_body:
            tokens.append({"depth": body_depth, "path_pos": 0,
                           "type": TYPE_HANDS, "name": name + ":hands"})
        for t_idx, tup in enumerate(tuples):
            tokens.append({"depth": body_depth, "path_pos": t_idx,
                           "type": TYPE_ARRAY, "name": name + ":array"})
            if isinstance(tup, list):
                for v_idx, val in enumerate(tup):
                    tokens.append({"depth": body_depth + 1, "path_pos": v_idx,
                                   "type": TYPE_VALUE, "name": str(val)})
            else:
                tokens.append({"depth": body_depth + 1, "path_pos": 0,
                               "type": TYPE_VALUE, "name": str(tup)})
        for c_idx, child in enumerate(children):
            self.WalkNode(child, body_depth, c_idx, tokens)
        return (1, True, None)

    # ─── COMMANDS ────────────────────────────────────────────────────────────

    def EncodeAst(self, params):
        """Encode a BCL AST root into a (seq_len, D_MODEL) matrix."""
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        flat_result = self.FlattenAst({"root": root})
        if flat_result[0] == 0:
            return flat_result
        tokens = flat_result[1]["tokens"]
        if not tokens:
            return (1, np.zeros((0, D_MODEL), dtype=np.float32), None)
        matrix = np.zeros((len(tokens), D_MODEL), dtype=np.float32)
        for i, tok in enumerate(tokens):
            matrix[i] = self.EncodeToken(tok["depth"], tok["path_pos"], tok["type"])
        self.state["last_matrix"] = matrix
        return (1, {"matrix": matrix, "shape": matrix.shape,
                    "tokens": tokens, "count": len(tokens)}, None)

    def Encode(self, params):
        """Encode raw BCL text into a (seq_len, D_MODEL) matrix.

        Runs lexer + parser, then EncodeAst on the result.
        """
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
        return self.EncodeAst({"root": root})

    def EncodeDepth(self, params):
        """Encode a single depth integer into a D_MODEL-dim vector.

        Returns depth_signal (HALF_DIM) padded with zeros (HALF_DIM).
        """
        depth = self._p(params, "depth")
        if depth is None:
            return (0, None, ("MISSING_PARAM", "depth required", 0))
        try:
            depth_int = int(depth)
        except (TypeError, ValueError):
            return (0, None, ("INVALID_PARAM", "depth must be an integer", 0))
        vec = np.zeros(D_MODEL, dtype=np.float32)
        vec[0:HALF_DIM] = self.DepthSignal(depth_int)
        return (1, {"vector": vec, "shape": vec.shape,
                    "depth": depth_int, "normalized": float(min(max(depth_int, 0), MAX_DEPTH)) / float(MAX_DEPTH)}, None)

    def Info(self, params=None):
        """Return configuration info."""
        config = dict(self.state["config"])
        type_names = {tid: TYPE_NAMES.get(tid, "unknown") for tid in range(NUM_TYPES)}
        return (1, {"config": config, "type_names": type_names,
                    "d_model": D_MODEL, "half_dim": HALF_DIM,
                    "num_types": NUM_TYPES, "max_depth": MAX_DEPTH}, None)
