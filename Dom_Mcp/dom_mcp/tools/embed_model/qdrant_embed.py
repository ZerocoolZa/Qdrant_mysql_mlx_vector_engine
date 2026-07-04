#!/usr/bin/env python3
#[@GHOST]{[@file<qdrant_embed.py>][@state<active>][@ver<v1.0>][@auth<Devin>][@date<2026-07-04>]}
#[@VBSTYLE]{[@auth<Devin>][@role<embed_engine>][@return<tuple3>][@no<print|hardcoded>]}
#[@FILEID]{qdrant_embed}
#[@SUMMARY]{Shared TF-IDF + random-projection embedding engine for chat messages. Produces 64-dim L2-normalized vectors. Vocab and IDF weights persisted to JSON so indexing and search stay identical.}
#[@CLASS]{QdrantEmbed}
#[@METHOD]{__init__, tokenize, fit, save, load, embed, Run, read_state, set_config}

"""
QdrantEmbed — Shared embedding engine for chat-message semantic search.

Produces a fixed 64-dimensional L2-normalized vector for any text using:
  1. Bag-of-words tokenization (lowercase, alphanumeric, min length 2)
  2. TF-IDF weighting (IDF computed from a fitted corpus)
  3. Random projection from vocab space down to 64 dimensions
     (Gaussian random matrix, fixed seed for reproducibility)
  4. L2 normalization

The vocabulary, IDF weights, and the random projection matrix seed are
persisted to ``qdrant_vocab_idf.json`` so that ``qdrant_index.py`` and
``qdrant_search.py`` produce IDENTICAL embeddings for the same text.

Public API (Tuple3 returns):
  - fit(corpus)         -> (1, vocab_size, None)
  - save(path)          -> (1, path, None)
  - load(path)          -> (1, True, None)  or (0, None, error)
  - embed(text)         -> (1, np.ndarray(64,), None)
"""

import os
import re
import json
import math
import hashlib
import numpy as np

VECTOR_DIM = 64
DEFAULT_SEED = 1337
MIN_TOKEN_LEN = 2
MAX_VOCAB_SIZE = 20000
MODEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_vocab_idf.json")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class QdrantEmbed:
    """TF-IDF + random-projection embedder producing 64-dim vectors."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if param is not None else {}
        self.state = {
            "config": {
                "vector_dim": VECTOR_DIM,
                "seed": DEFAULT_SEED,
                "min_token_len": MIN_TOKEN_LEN,
                "max_vocab": MAX_VOCAB_SIZE,
            },
            "vocab": {},          # token -> column index
            "idf": {},            # token -> idf weight
            "projection": None,   # numpy array (vocab_size, VECTOR_DIM)
            "fitted": False,
            "model_path": self.param.get("model_path", MODEL_FILE),
        }
        self.rng = None

    def p(self, msg):
        """Internal logger helper (no print to stdout for VBStyle)."""
        sys_msg = "[QdrantEmbed] " + str(msg)
        return sys_msg

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, values):
        if not isinstance(values, dict):
            return (0, None, (1, "set_config expects a dict", 0))
        self.state["config"].update(values)
        return (1, dict(self.state["config"]), None)

    def tokenize(self, text):
        """Lowercase alphanumeric tokenization, min length filter."""
        if not text:
            return []
        tokens = _TOKEN_RE.findall(text.lower())
        out = []
        for t in tokens:
            if len(t) >= self.state["config"]["min_token_len"]:
                if not t.isdigit():
                    out.append(t)
        return out

    def fit(self, corpus):
        """Build vocab + IDF from a list of text documents.

        corpus: list[str]
        Returns Tuple3 (1, vocab_size, None).
        """
        cfg = self.state["config"]
        doc_freq = {}
        total_docs = len(corpus)
        if total_docs == 0:
            return (0, None, (2, "empty corpus", 0))

        for doc in corpus:
            seen = set(self.tokenize(doc))
            for tok in seen:
                doc_freq[tok] = doc_freq.get(tok, 0) + 1

        # sort by frequency desc, keep top MAX_VOCAB_SIZE
        sorted_tokens = sorted(doc_freq.items(), key=lambda kv: (-kv[1], kv[0]))
        if len(sorted_tokens) > cfg["max_vocab"]:
            sorted_tokens = sorted_tokens[: cfg["max_vocab"]]

        vocab = {}
        idf = {}
        for idx, (tok, df) in enumerate(sorted_tokens):
            vocab[tok] = idx
            # smoothed IDF: log((1+N)/(1+df)) + 1
            idf[tok] = math.log((1.0 + total_docs) / (1.0 + df)) + 1.0

        vocab_size = len(vocab)
        seed = cfg["seed"]
        # Gaussian random projection matrix (vocab_size x VECTOR_DIM)
        rng = np.random.RandomState(seed)
        projection = rng.normal(0.0, 1.0 / math.sqrt(cfg["vector_dim"]),
                                size=(vocab_size, cfg["vector_dim"])).astype(np.float32)

        self.state["vocab"] = vocab
        self.state["idf"] = idf
        self.state["projection"] = projection
        self.state["fitted"] = True
        return (1, vocab_size, None)

    def save(self, path=None):
        """Persist vocab + IDF + projection to JSON file."""
        if not self.state["fitted"]:
            return (0, None, (3, "not fitted", 0))
        target = path or self.state["model_path"]
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        data = {
            "config": self.state["config"],
            "vocab": self.state["vocab"],
            "idf": self.state["idf"],
            "projection": self.state["projection"].tolist(),
        }
        with open(target, "w") as fh:
            json.dump(data, fh)
        return (1, target, None)

    def load(self, path=None):
        """Load vocab + IDF + projection from JSON file."""
        target = path or self.state["model_path"]
        if not os.path.exists(target):
            return (0, None, (4, "model file not found: " + target, 0))
        with open(target, "r") as fh:
            data = json.load(fh)
        self.state["config"] = data.get("config", self.state["config"])
        self.state["vocab"] = data.get("vocab", {})
        self.state["idf"] = data.get("idf", {})
        proj = data.get("projection")
        if proj is None:
            return (0, None, (5, "projection missing in model file", 0))
        self.state["projection"] = np.array(proj, dtype=np.float32)
        self.state["fitted"] = True
        return (1, True, None)

    def embed(self, text):
        """Embed a single text string into a 64-dim L2-normalized vector.

        Returns Tuple3 (1, np.ndarray(64,), None).
        """
        if not self.state["fitted"]:
            return (0, None, (6, "embedder not fitted/loaded", 0))
        vocab = self.state["vocab"]
        idf = self.state["idf"]
        proj = self.state["projection"]
        dim = self.state["config"]["vector_dim"]

        tokens = self.tokenize(text)
        if not tokens:
            return (1, np.zeros(dim, dtype=np.float32), None)

        # TF-IDF weighted bag-of-words sparse vector
        tf_counts = {}
        for t in tokens:
            if t in vocab:
                tf_counts[t] = tf_counts.get(t, 0) + 1

        if not tf_counts:
            # no known tokens -> zero vector (caller may handle)
            return (1, np.zeros(dim, dtype=np.float32), None)

        total_tokens = float(len(tokens))
        bow = np.zeros(len(vocab), dtype=np.float32)
        for tok, count in tf_counts.items():
            tf = count / total_tokens
            col = vocab[tok]
            bow[col] = tf * idf[tok]

        # random projection to 64 dims
        vec = bow @ proj  # (vector_dim,)

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec = vec / norm
        return (1, vec.astype(np.float32), None)

    def Run(self, command, params=None):
        """Dispatch interface for VBStyle compliance."""
        params = params or {}
        if command == "fit":
            return self.fit(params.get("corpus", []))
        elif command == "save":
            return self.save(params.get("path"))
        elif command == "load":
            return self.load(params.get("path"))
        elif command == "embed":
            return self.embed(params.get("text", ""))
        elif command == "tokenize":
            return (1, self.tokenize(params.get("text", "")), None)
        elif command == "read_state":
            return self.read_state()
        elif command == "set_config":
            return self.set_config(params.get("values", {}))
        return (0, None, (99, "unknown command: " + str(command), 0))
