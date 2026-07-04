#!/usr/bin/env python3
"""Test MiniLM-L6 CoreML with a real tokenizer."""
import coremltools as ct
import numpy as np
from transformers import AutoTokenizer

MODEL_PATH = "/Users/wws/Documents/Models/MiniLM-L12-v2/all-MiniLM-L12-v2-converted/all-MiniLM-L6-v2_6136536182.mlpackage"

# Try multiple tokenizer paths
TOKENIZER_PATHS = [
    "/Users/wws/Documents/Models/coreml_models/microsoft_codebert-base-tokenizer",
    "/Users/wws/Documents/Models/coreml_models/graphcodebert_coreml",
]

m = ct.models.MLModel(MODEL_PATH)
spec = m.get_spec()
print("Model loaded: MiniLM-L6 CoreML")
print(f"  Input: input_ids [1,128] int32, attention_mask [1,128] int32")
print(f"  Output: sentence_embedding [1,384] float32")

tok = None
for tp in TOKENIZER_PATHS:
    try:
        tok = AutoTokenizer.from_pretrained(tp)
        print(f"Tokenizer loaded from: {tp}")
        break
    except Exception as e:
        print(f"Tokenizer {tp} failed: {str(e)[:100]}")

if tok is None:
    print("No tokenizer found, using basic char-level")
    tok = None

def embed(text):
    if tok is not None:
        enc = tok(text, padding="max_length", truncation=True, max_length=128, return_tensors="np")
        input_ids = enc["input_ids"].astype(np.int32)
        attn_mask = enc["attention_mask"].astype(np.int32)
    else:
        # char-level fallback
        ids = [ord(c) % 30000 for c in text[:128]]
        ids = ids + [0] * (128 - len(ids))
        input_ids = np.array([ids], dtype=np.int32)
        attn_mask = np.array([[1]*len(ids) + [0]*(128-len(ids))], dtype=np.int32)
    
    out = m.predict({
        "input_ids": input_ids,
        "attention_mask": attn_mask,
    })
    vec = np.asarray(out["sentence_embedding"], dtype=np.float32).flatten()
    return vec

def cosine_sim(a, b):
    na = np.linalg.norm(a) + 1e-12
    nb = np.linalg.norm(b) + 1e-12
    return float(np.dot(a, b) / (na * nb))

# Test pairs
pairs = [
    ("collapse by invariance", "collapse by abstraction"),
    ("collapse by invariance", "semantic compression"),
    ("collapse by invariance", "canonicalization"),
    ("collapse by invariance", "factorization"),
    ("collapse by invariance", "normalization"),
    ("collapse by invariance", "graph contraction"),
    ("kokoro voice pipeline", "tts speech synthesis"),
    ("mysql database query", "sql database connection"),
    ("mysql database", "kokoro voice"),
    ("embedding vector", "vector embedding"),
    ("compile build", "deploy run"),
    ("compile build", "database query"),
]

print("\n=== Similarity Tests ===")
for a, b in pairs:
    va = embed(a)
    vb = embed(b)
    sim = cosine_sim(va, vb)
    print(f"  sim('{a}', '{b}') = {sim:.4f}")

# Quick corpus search
corpus = [
    "collapse by abstraction", "semantic compression", "canonicalization",
    "factorization", "normalization", "graph contraction", "quotient construction",
    "abstraction", "generalization", "specialization", "refactoring", "optimization",
    "simplification", "transformation", "compression", "encoding", "decoding",
    "parsing", "tokenization", "embedding", "vectorization", "clustering",
    "classification", "regression", "inference", "training", "database", "query",
    "index", "search", "retrieval", "ranking", "sorting", "filtering",
    "compile", "build", "deploy", "run", "execute", "debug", "test", "validate",
    "verify", "check", "inspect", "analyze", "profile", "optimize", "parallelize",
    "pipeline", "workflow", "process", "thread", "async", "concurrent",
    "pattern", "template", "schema", "model", "entity", "relation",
    "algorithm", "heuristic", "strategy", "plan", "goal", "objective",
    "metric", "score", "weight", "bias", "loss", "accuracy",
    "neural network", "deep learning", "machine learning", "artificial intelligence",
    "natural language processing", "computer vision", "data science",
    "software engineering", "compiler design", "operating system",
    "distributed system", "concurrent programming", "functional programming",
    "object oriented", "design pattern", "architecture", "system design",
]

print(f"\n=== Corpus Search ({len(corpus)} entries) ===")
corpus_vecs = np.stack([embed(c) for c in corpus])

query = "collapse by invariance"
q_vec = embed(query)
sims = corpus_vecs @ q_vec / (np.linalg.norm(corpus_vecs, axis=1) * np.linalg.norm(q_vec) + 1e-12)
top = np.argsort(sims)[::-1][:20]
print(f"\nQuery: '{query}'")
print(f"{'#':>3}  {'Phrase':<40} {'Score':>8}")
print(f"{'---':>3}  {'-'*40} {'-'*8}")
for i, idx in enumerate(top, 1):
    print(f"{i:>3}. {corpus[idx]:<40} {sims[idx]:.4f}")

# Timing
import time
t0 = time.time()
for _ in range(50):
    embed("test query")
elapsed = time.time() - t0
print(f"\nTiming: {(elapsed/50)*1000:.2f} ms/embed (CoreML Neural Engine)")
