#!/usr/bin/env python3
# [@GHOST]{[@file<semantic_finder.py>][@state<active>][@date<2026-07-04>][@ver<1.0>][@auth<devin>][@context<Semantic similarity search using all-MiniLM-L6-v2 embeddings]]}
# [@VBSTYLE]{[@auth<devin>][@role<semantic_search>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@FILEID]{id="semantic_finder.py" domain="Dom_Smart_system_seach" authority="SemanticFinder"}
# [@SUMMARY]{summary="Send word/phrase -> get back similar terms. Uses all-MiniLM-L6-v2 + cosine similarity. Offline. Pre-embedded corpus."}
# [@CLASS]{class="SemanticFinder" domain="Dom_Smart_system_seach" authority="single"}
# [@METHOD]{methods="Run,search,build_corpus,load_corpus,add_terms,read_state,set_config"}

"""
SemanticFinder — Send word/phrase, get back similar terms.

Uses all-MiniLM-L6-v2 (384-dim embeddings) + cosine similarity.
Runs completely offline. Corpus is pre-embedded and cached to disk.

Usage (CLI):
    python3 semantic_finder.py build                    # build corpus from DB + curated terms
    python3 semantic_finder.py search "collapse by invariance"
    python3 semantic_finder.py search "collapse by invariance" --top 20
    python3 semantic_finder.py add "my custom term" "another term"
    python3 semantic_finder.py interactive              # REPL mode

Usage (programmatic):
    from semantic_finder import SemanticFinder
    sf = SemanticFinder()
    ok, data, err = sf.Run("search", {"query": "collapse by invariance", "top": 20})
"""

import os
import sys
import json
import pickle
import numpy as np
from pathlib import Path

# ════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
MAX_LENGTH = 128
CACHE_DIR = Path(__file__).parent / "semantic_cache"
CORPUS_CACHE = CACHE_DIR / "corpus_embeddings.pkl"
TERMS_CACHE = CACHE_DIR / "corpus_terms.json"

# CoreML embedding model (SemanticEmbed.mlpackage — 64-dim, Apple Neural Engine)
COREML_MODEL_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/embed_model/SemanticEmbed.mlpackage"
COREML_VOCAB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/embed_model/embed_vocab.json"
COREML_EMBED_DIM = 64
COREML_VOCAB_SIZE = 256

# Curated technical dictionary — software engineering, compiler, math, AI, BCL
CURATED_TERMS = [
    # ── Collapse / reduction ──
    "collapse by abstraction", "collapse by invariance", "collapse by complexity",
    "semantic compression", "canonicalization", "factorization", "normalization",
    "graph contraction", "code reduction", "complexity reduction",
    "collapse code block", "collapse function", "collapse class",
    "collapse conditional", "collapse branch", "collapse loop",
    "collapse duplicate", "collapse wrapper", "collapse ceremony",
    "collapse boilerplate", "collapse repetitive code",
    "collapse into single method", "collapse into one function",
    "collapse identical paths", "collapse execution paths",
    "structural collapse", "collapse nodes", "collapse edges",

    # ── Compiler optimizations ──
    "constant folding", "constant propagation", "dead code elimination",
    "strength reduction", "loop unrolling", "loop invariant hoisting",
    "loop invariant code motion", "common subexpression elimination",
    "copy propagation", "value numbering", "partial redundancy elimination",
    "tail call optimization", "inlining", "devirtualization",
    "escape analysis", "scalar replacement", "register allocation",
    "instruction scheduling", "peephole optimization", "branch prediction",

    # ── Refactoring ──
    "extract method", "extract function", "extract class",
    "inline method", "inline function", "rename method",
    "move method", "move field", "pull up method", "push down method",
    "extract superclass", "extract interface", "collapse hierarchy",
    "form template method", "replace inheritance with delegation",
    "replace delegation with inheritance", "replace conditional with polymorphism",
    "replace parameter with method", "replace method with method object",
    "introduce parameter object", "introduce named parameter",
    "remove setting method", "hide method", "encapsulate field",
    "self encapsulate field", "replace data value with object",
    "change value to reference", "change reference to value",
    "replace array with object", "replace magic number with symbolic constant",
    "rename variable", "split variable", "remove assignments to parameters",

    # ── Software engineering ──
    "code optimization", "reduce complexity", "simplify code",
    "merge duplicate functions", "unify execution paths",
    "extract common pattern", "refactor repetitive code",
    "consolidate classes", "deduplicate code", "dry principle",
    "single responsibility principle", "separation of concerns",
    "don't repeat yourself", "you ain't gonna need it",
    "keep it simple stupid", "law of demeter",
    "composition over inheritance", "favor composition over inheritance",
    "program to interface not implementation",
    "dependency inversion", "open closed principle",
    "liskov substitution principle", "interface segregation principle",

    # ── Architecture ──
    "monolithic architecture", "microservices", "service oriented architecture",
    "event driven architecture", "pipe and filter", "layered architecture",
    "hexagonal architecture", "clean architecture", "onion architecture",
    "domain driven design", "bounded context", "aggregate root",
    "repository pattern", "unit of work", "factory pattern",
    "strategy pattern", "observer pattern", "decorator pattern",
    "adapter pattern", "facade pattern", "command pattern",
    "chain of responsibility", "template method pattern",
    "state machine", "finite state machine", "state pattern",

    # ── Data structures / algorithms ──
    "graph traversal", "depth first search", "breadth first search",
    "topological sort", "shortest path", "minimum spanning tree",
    "dynamic programming", "greedy algorithm", "divide and conquer",
    "backtracking", "branch and bound", "memoization",
    "binary search", "hash table", "bloom filter",
    "red black tree", "avl tree", "b-tree", "trie", "suffix tree",
    "heap", "priority queue", "union find", "segment tree",
    "fenwick tree", "skip list", "consistent hashing",

    # ── Math / logic ──
    "invariant", "loop invariant", "class invariant",
    "precondition", "postcondition", "assertion",
    "theorem proving", "formal verification", "model checking",
    "abstract interpretation", "symbolic execution",
    "satisfiability modulo theories", "boolean satisfiability",
    "constraint satisfaction", "linear programming",
    "integer programming", "convex optimization",
    "gradient descent", "newton's method", "quadratic programming",

    # ── AI / ML ──
    "embedding", "vector embedding", "word embedding",
    "sentence embedding", "document embedding",
    "cosine similarity", "euclidean distance", "dot product",
    "nearest neighbor search", "approximate nearest neighbor",
    "vector database", "vector index", "quantization",
    "dimensionality reduction", "principal component analysis",
    "t-distributed stochastic neighbor embedding",
    "uniform manifold approximation and projection",
    "transformer architecture", "attention mechanism",
    "self attention", "multi head attention",
    "contrastive learning", "triplet loss", "margin loss",
    "fine tuning", "transfer learning", "domain adaptation",
    "zero shot learning", "few shot learning",
    "retrieval augmented generation", "semantic search",

    # ── BCL / VBStyle concepts ──
    "bracket command language", "BCL token", "BCL parser",
    "VBStyle", "ghost header", "tuple3 return",
    "execution unification", "collapse identical execution",
    "one class one domain", "domain complete class",
    "deterministic execution graph", "graph fidelity",
    "authority table", "entity table", "join table",
    "container hands array", "BCL container",
    "semantic compression token", "BCL stage 1",
    "BCL stage 2", "token extraction",

    # ── Database ──
    "normalization", "denormalization", "indexing",
    "query optimization", "join optimization",
    "materialized view", "covering index", "partial index",
    "sharding", "partitioning", "replication",
    "acid properties", "base properties", "cap theorem",
    "eventual consistency", "strong consistency",
    "optimistic concurrency", "pessimistic concurrency",
    "mvcc", "write ahead logging", "snapshot isolation",

    # ── Concurrency ──
    "race condition", "deadlock", "livelock",
    "mutex", "semaphore", "condition variable",
    "lock free", "wait free", "compare and swap",
    "actor model", "communicating sequential processes",
    "software transactional memory", "futures and promises",
    "async await", "coroutine", "green thread",

    # ── Testing ──
    "unit test", "integration test", "end to end test",
    "property based testing", "fuzz testing", "mutation testing",
    "test driven development", "behavior driven development",
    "mock object", "test double", "fixture",
    "code coverage", "branch coverage", "path coverage",
    "regression test", "smoke test", "sanity test",
]


class SemanticFinder:
    """Semantic similarity search using all-MiniLM-L6-v2."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "model_name": MODEL_NAME,
                "embed_dim": EMBED_DIM,
                "max_length": MAX_LENGTH,
                "default_top": 20,
                "cache_dir": str(CACHE_DIR),
                "backend": "minilm",  # "minilm" or "coreml"
            },
            "model": None,
            "tokenizer": None,
            "coreml_model": None,
            "coreml_vocab": None,
            "corpus_terms": [],
            "corpus_vectors": None,
            "last_query": None,
            "last_results": None,
        }

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        """Dispatch commands."""
        dispatch = {
            "search": self.cmd_search,
            "build": self.cmd_build_corpus,
            "add": self.cmd_add_terms,
            "load": self.cmd_load_corpus,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, (1, "unknown_command: %s" % command, 0))
        return handler(params)

    def cmd_read_state(self, params):
        return (1, {
            "config": dict(self.state["config"]),
            "corpus_size": len(self.state["corpus_terms"]),
            "model_loaded": self.state["model"] is not None,
        }, None)

    def cmd_set_config(self, params):
        if not params:
            return (0, None, (1, "no params", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def _load_model(self):
        """Lazy-load the transformer model."""
        if self.state["model"] is not None:
            return
        from transformers import AutoTokenizer, AutoModel
        import torch
        self.state["tokenizer"] = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.state["model"] = AutoModel.from_pretrained(MODEL_NAME)
        self.state["model"].eval()

    def _embed(self, texts):
        """Embed a list of texts. Returns numpy array (N, dim). Backend-aware."""
        backend = self.state["config"].get("backend", "minilm")
        if backend == "coreml":
            return self._embed_coreml_batch(texts)
        return self._embed_minilm_batch(texts)

    def _embed_minilm_batch(self, texts):
        """Embed a list of texts using all-MiniLM-L6-v2. Returns numpy array (N, 384)."""
        import torch
        import torch.nn.functional as F
        tok = self.state["tokenizer"]
        model = self.state["model"]
        with torch.no_grad():
            enc = tok(texts, padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt")
            out = model(**enc)
            mask = enc["attention_mask"].unsqueeze(-1).float()
            emb = (out.last_hidden_state * mask).sum(1) / mask.sum(1)
            emb = F.normalize(emb, p=2, dim=1)
        return emb.numpy()

    def _load_coreml_model(self):
        """Lazy-load the CoreML SemanticEmbed model + vocab."""
        if self.state["coreml_model"] is not None:
            return
        import coremltools as ct
        with open(COREML_VOCAB_PATH, "r") as f:
            vdata = json.load(f)
        self.state["coreml_vocab"] = vdata.get("vocab", [])
        self.state["coreml_model"] = ct.models.MLModel(COREML_MODEL_PATH)

    def _embed_coreml_batch(self, texts):
        """Embed a list of texts using CoreML SemanticEmbed. Returns numpy array (N, 64).
        Uses bag-of-words with the domain-specific 256-token vocab.
        Runs on Apple Neural Engine — fast, no Python overhead per inference."""
        self._load_coreml_model()
        vocab = self.state["coreml_vocab"]
        model = self.state["coreml_model"]
        results = []
        for text in texts:
            tokens = [t for t in text.lower().split() if len(t) >= 2]
            bow = np.zeros((1, len(vocab)), dtype=np.float32)
            for t in tokens:
                if t in vocab:
                    bow[0][vocab.index(t)] = 1.0
            out = model.predict({"text_bow": bow})
            emb = np.array(out["embedding"]).flatten()
            results.append(emb)
        return np.array(results, dtype=np.float32)

    def _embed_single(self, text):
        """Embed a single text. Returns numpy array (dim,)."""
        return self._embed([text])[0]

    def cmd_build_corpus(self, params):
        """Build corpus from curated terms + MySQL DB terms. Pre-compute embeddings."""
        backend = self.state["config"].get("backend", "minilm")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if backend == "coreml":
            self._load_coreml_model()
        else:
            self._load_model()

        terms = list(CURATED_TERMS)

        # Pull from MySQL if available
        db_terms = self._fetch_db_terms()
        terms.extend(db_terms)

        # Deduplicate, preserve order
        seen = set()
        unique_terms = []
        for t in terms:
            t_clean = t.strip()
            if t_clean and t_clean.lower() not in seen:
                seen.add(t_clean.lower())
                unique_terms.append(t_clean)

        # Embed in batches
        vectors = self._embed(unique_terms)

        # Save to cache (backend-specific filenames)
        suffix = "_coreml" if backend == "coreml" else ""
        corpus_path = CACHE_DIR / ("corpus_embeddings%s.pkl" % suffix)
        terms_path = CACHE_DIR / ("corpus_terms%s.json" % suffix)
        with open(corpus_path, "wb") as f:
            pickle.dump(vectors, f)
        with open(terms_path, "w") as f:
            json.dump(unique_terms, f, indent=2)

        self.state["corpus_terms"] = unique_terms
        self.state["corpus_vectors"] = vectors

        return (1, {
            "corpus_size": len(unique_terms),
            "curated_count": len(CURATED_TERMS),
            "db_count": len(db_terms),
            "backend": backend,
            "embed_dim": vectors.shape[1],
            "cache_path": str(corpus_path),
            "terms_path": str(terms_path),
        }, None)

    def _fetch_db_terms(self):
        """Fetch terms from MySQL databases."""
        terms = []
        try:
            import mysql.connector
            conn = mysql.connector.connect(host="localhost", user="root", database="vb_shared")
            c = conn.cursor()
            # Token names (BCL tokens)
            try:
                c.execute("SELECT DISTINCT name FROM tokens WHERE name IS NOT NULL AND name != '' LIMIT 300")
                terms.extend([r[0] for r in c.fetchall()])
            except Exception:
                pass
            # Class names
            try:
                c.execute("SELECT DISTINCT class_name FROM code_classes WHERE class_name IS NOT NULL AND class_name != '' LIMIT 300")
                terms.extend([r[0] for r in c.fetchall()])
            except Exception:
                pass
            # Instruction names
            try:
                c.execute("SELECT DISTINCT instruction_name FROM instructions WHERE instruction_name IS NOT NULL AND instruction_name != '' LIMIT 100")
                terms.extend([r[0] for r in c.fetchall()])
            except Exception:
                pass
            # Learned rules patterns (first 200 chars, unique)
            try:
                c.execute("SELECT DISTINCT SUBSTRING(pattern, 1, 200) FROM learned_rules WHERE pattern IS NOT NULL AND pattern != '' LIMIT 500")
                terms.extend([r[0] for r in c.fetchall()])
            except Exception:
                pass
            conn.close()
        except Exception:
            pass
        return terms

    def cmd_load_corpus(self, params):
        """Load pre-built corpus from cache (backend-specific)."""
        backend = self.state["config"].get("backend", "minilm")
        suffix = "_coreml" if backend == "coreml" else ""
        corpus_path = CACHE_DIR / ("corpus_embeddings%s.pkl" % suffix)
        terms_path = CACHE_DIR / ("corpus_terms%s.json" % suffix)
        if not corpus_path.exists() or not terms_path.exists():
            return (0, None, (1, "corpus not built for backend '%s'. Run build first." % backend, 0))
        with open(corpus_path, "rb") as f:
            self.state["corpus_vectors"] = pickle.load(f)
        with open(terms_path, "r") as f:
            self.state["corpus_terms"] = json.load(f)
        return (1, {"corpus_size": len(self.state["corpus_terms"]), "backend": backend}, None)

    def cmd_add_terms(self, params):
        """Add custom terms to corpus and re-embed only new ones."""
        terms = self._p(params, "terms", [])
        if isinstance(terms, str):
            terms = [terms]
        if not terms:
            return (0, None, (1, "no terms provided", 0))

        # Load existing corpus if not loaded
        if self.state["corpus_vectors"] is None:
            ok, data, err = self.cmd_load_corpus({})
            if not ok:
                # No corpus yet, build fresh with just these terms
                self._load_model()
                self.state["corpus_terms"] = []
                self.state["corpus_vectors"] = np.zeros((0, EMBED_DIM))

        existing = set(t.lower() for t in self.state["corpus_terms"])
        new_terms = [t.strip() for t in terms if t.strip() and t.strip().lower() not in existing]
        if not new_terms:
            return (1, {"added": 0, "corpus_size": len(self.state["corpus_terms"])}, None)

        self._load_model()
        new_vecs = self._embed(new_terms)

        if self.state["corpus_vectors"].shape[0] > 0:
            self.state["corpus_vectors"] = np.vstack([self.state["corpus_vectors"], new_vecs])
        else:
            self.state["corpus_vectors"] = new_vecs
        self.state["corpus_terms"].extend(new_terms)

        # Save
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CORPUS_CACHE, "wb") as f:
            pickle.dump(self.state["corpus_vectors"], f)
        with open(TERMS_CACHE, "w") as f:
            json.dump(self.state["corpus_terms"], f, indent=2)

        return (1, {
            "added": len(new_terms),
            "corpus_size": len(self.state["corpus_terms"]),
            "new_terms": new_terms,
        }, None)

    def cmd_search(self, params):
        """Search for similar terms. Params: query, top."""
        query = self._p(params, "query", "")
        top = self._p(params, "top", self.state["config"]["default_top"])
        if not query:
            return (0, None, (1, "no query provided", 0))

        # Load corpus if needed
        if self.state["corpus_vectors"] is None:
            ok, data, err = self.cmd_load_corpus({})
            if not ok:
                # Auto-build if no corpus
                ok2, data2, err2 = self.cmd_build_corpus({})
                if not ok2:
                    return (0, None, err2)

        backend = self.state["config"].get("backend", "minilm")
        if backend == "coreml":
            self._load_coreml_model()
        else:
            self._load_model()

        # Embed query
        q_vec = self._embed_single(query)

        # Cosine similarity (vectors are already normalized)
        sims = np.dot(self.state["corpus_vectors"], q_vec)

        # Rank
        n = min(top, len(sims))
        top_idx = np.argsort(sims)[::-1][:n]

        results = []
        for idx in top_idx:
            results.append({
                "term": self.state["corpus_terms"][idx],
                "score": float(sims[idx]),
                "rank": len(results) + 1,
            })

        self.state["last_query"] = query
        self.state["last_results"] = results

        return (1, {
            "query": query,
            "top": n,
            "corpus_size": len(self.state["corpus_terms"]),
            "results": results,
        }, None)


# ════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ════════════════════════════════════════════════════════════════

def cli_main():
    import argparse
    ap = argparse.ArgumentParser(description="SemanticFinder — word/phrase similarity search")
    sub = ap.add_subparsers(dest="cmd")

    p_build = sub.add_parser("build", help="Build corpus from curated terms + DB")
    p_build.add_argument("--backend", choices=["minilm", "coreml"], default="minilm",
                         help="Embedding backend: minilm (384-dim, general) or coreml (64-dim, domain-specific, ANE)")
    p_search = sub.add_parser("search", help="Search for similar terms")
    p_search.add_argument("query", help="Word or phrase to search")
    p_search.add_argument("--top", type=int, default=20, help="Top N results (default 20)")
    p_search.add_argument("--backend", choices=["minilm", "coreml"], default="minilm",
                          help="Embedding backend: minilm or coreml")
    p_add = sub.add_parser("add", help="Add custom terms to corpus")
    p_add.add_argument("terms", nargs="+", help="Terms to add")
    p_add.add_argument("--backend", choices=["minilm", "coreml"], default="minilm")
    p_interactive = sub.add_parser("interactive", help="REPL mode")
    p_interactive.add_argument("--backend", choices=["minilm", "coreml"], default="minilm")
    p_info = sub.add_parser("info", help="Show corpus info")

    args = ap.parse_args()
    sf = SemanticFinder()
    if hasattr(args, "backend") and args.backend:
        sf.Run("set_config", {"backend": args.backend})

    if args.cmd == "build":
        sys.stderr.write("Building corpus (curated + DB terms)...\n")
        ok, data, err = sf.Run("build", {})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("Corpus built: %d terms (curated=%d, db=%d)\n" % (
            data["corpus_size"], data["curated_count"], data["db_count"]))
        sys.stderr.write("Cache: %s\n" % data["cache_path"])
        return 0

    if args.cmd == "search":
        ok, data, err = sf.Run("search", {"query": args.query, "top": args.top})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("\n=== Input: '%s' ===\n" % data["query"])
        sys.stderr.write("Corpus: %d terms | Top %d:\n\n" % (data["corpus_size"], data["top"]))
        for r in data["results"]:
            sys.stderr.write("  %2d. %-45s %.3f\n" % (r["rank"], r["term"], r["score"]))
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "add":
        ok, data, err = sf.Run("add", {"terms": args.terms})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("Added %d terms. Corpus now: %d\n" % (data["added"], data["corpus_size"]))
        if data.get("new_terms"):
            for t in data["new_terms"]:
                sys.stderr.write("  + %s\n" % t)
        return 0

    if args.cmd == "info":
        ok, data, err = sf.Run("read_state", {})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("SemanticFinder State:\n")
        sys.stderr.write("  Backend: %s\n" % data["config"].get("backend", "minilm"))
        sys.stderr.write("  Model: %s\n" % data["config"]["model_name"])
        sys.stderr.write("  Model loaded: %s\n" % data["model_loaded"])
        sys.stderr.write("  Corpus size: %d terms\n" % data["corpus_size"])
        sys.stderr.write("  Embed dim: %d\n" % data["config"]["embed_dim"])
        sys.stderr.write("  Cache: %s\n" % data["config"]["cache_dir"])
        return 0

    if args.cmd == "interactive":
        # REPL mode
        sys.stderr.write("SemanticFinder Interactive (type 'quit' to exit)\n")
        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in ("quit", "exit", "q"):
                break
            if not q:
                continue
            ok, data, err = sf.Run("search", {"query": q, "top": 20})
            if not ok:
                sys.stderr.write("ERROR: %s\n" % err[1])
                continue
            for r in data["results"]:
                sys.stderr.write("  %2d. %-45s %.3f\n" % (r["rank"], r["term"], r["score"]))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(cli_main())
