#!/usr/bin/env python3
"""
BgeSearch.py — BGE semantic search over VBStyle document chunks.

Usage:
    python3 BgeSearch.py "domain collapse prevent code drift"
    python3 BgeSearch.py "magnetic registry trajectory" --top 10
    python3 BgeSearch.py "boot sequence order" --full

Loads pre-computed BGE embeddings and returns the most semantically
relevant document chunks for a given query.
"""

import os
import sys
import json
import numpy as np

EMB_PATH = "/tmp/vbstyle_bge_embeddings.npy"
CHUNKS_PATH = "/tmp/vbstyle_chunks.json"
MODEL_NAME = "BAAI/bge-small-en-v1.5"

_state = {
    "embeddings": None,
    "chunks": None,
    "model": None,
}


def Load():
    if _state["embeddings"] is None:
        _state["embeddings"] = np.load(EMB_PATH)
        with open(CHUNKS_PATH) as f:
            _state["chunks"] = json.load(f)
        from sentence_transformers import SentenceTransformer
        _state["model"] = SentenceTransformer(MODEL_NAME)


def Search(query, top_k=5, min_score=0.0):
    Load()
    query_emb = _state["model"].encode([query])[0]
    emb = _state["embeddings"]
    norms = np.linalg.norm(emb, axis=1)
    q_norm = np.linalg.norm(query_emb)
    scores = (emb @ query_emb) / (norms * q_norm + 1e-8)
    top_idx = np.argsort(scores)[::-1][:top_k]
    results = []
    for idx in top_idx:
        score = float(scores[idx])
        if score < min_score:
            break
        results.append({
            "file": _state["chunks"][idx]["file"],
            "start": _state["chunks"][idx]["start"],
            "score": score,
            "text": _state["chunks"][idx]["text"],
        })
    return results


def Run(command, params):
    ok = 1
    data = None
    error = None
    try:
        if command == "search":
            results = Search(params["query"], params.get("top_k", 5))
            data = results
        elif command == "stats":
            Load()
            data = {
                "chunks": len(_state["chunks"]),
                "dimensions": _state["embeddings"].shape[1],
                "model": MODEL_NAME,
            }
        else:
            ok = 0
            error = ("UNKNOWN_COMMAND", f"Unknown: {command}", 0)
    except Exception as e:
        ok = 0
        error = ("EXCEPTION", str(e), 0)
    return (ok, data, error)


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "VBStyle architecture"
    top_k = 5
    show_full = False
    for arg in sys.argv[2:]:
        if arg == "--full":
            show_full = True
        elif arg == "--top":
            top_k = int(sys.argv[sys.argv.index(arg) + 1])
        elif arg.startswith("--top="):
            top_k = int(arg.split("=")[1])

    results = Search(query, top_k=top_k)
    for r in results:
        print(f"[{r['score']:.3f}] {r['file']} (pos {r['start']})")
        if show_full:
            print(r["text"])
        else:
            print(f"  {r['text'][:200]}")
        print()
