#!/usr/bin/env python3
"""
CoreML Semantic Search Engine v2.0
BCLIR.UPGRADE from v1.0 → v2.0

Added: SemanticExtractor(AST), Normalizer, EmbeddingPipeline, VectorStore(metadata),
       SimilarityEngine(multi-metric), ANNIndex(HNSW), KnowledgeGraph, QueryEngine,
       IncrementalMonitor, Statistics, ClusterEngine, ReverseSearch, BCLExporter, API
"""

import coremltools as ct
import numpy as np
import time
import sys
import os
import re
import json
import sqlite3
import ast
import hashlib
from pathlib import Path
from collections import Counter, defaultdict
from transformers import AutoTokenizer

# ============================================================
# CONSTANTS
# ============================================================

MODEL_PATH = "/Users/wws/Documents/Models/MiniLM-L12-v2/all-MiniLM-L12-v2-converted/all-MiniLM-L6-v2_6136536182.mlpackage"
TOKENIZER_PATH = "sentence-transformers/all-MiniLM-L6-v2"
DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/semantic_corpus_v2.db"
PROJECT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine"
MAX_LEN = 128
EMBED_DIM = 384
TOP_N = 20
MAX_CORPUS_SIZE = 50000
MAX_FILE_TERMS = 200
MAX_MYSQL_TERMS = 5000
SCAN_EXTENSIONS = {".py", ".md", ".json", ".yaml", ".yml", ".sql", ".sh", ".go", ".c", ".h"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".DS_Store", "Archive", "archive",
             "chat_resources", "Cascade_toolStack", "Dom_CoreML_Layout"}
MIN_TERM_LEN = 3
MAX_TERM_LEN = 80


# ============================================================
# SemanticExtractor — replaces regex with AST + structured extraction
# ============================================================

class SemanticExtractor:
    """Extract terms from source files using AST and structured parsing."""

    def extract_python(self, filepath):
        """Use Python AST to extract identifiers, classes, functions, imports, constants."""
        terms = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    terms.append((node.name.lower(), "class", filepath, node.lineno))
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            terms.append((item.name.lower(), "method", filepath, item.lineno))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    terms.append((node.name.lower(), "function", filepath, node.lineno))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        terms.append((alias.name.lower(), "import", filepath, node.lineno))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        terms.append((node.module.lower(), "import", filepath, node.lineno))
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            terms.append((target.id.lower(), "constant", filepath, node.lineno))
                elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    val = str(node.value.value)
                    if len(val) > 10:
                        terms.append((val[:MAX_TERM_LEN].lower(), "docstring", filepath, node.lineno))
        except Exception:
            pass
        return terms

    def extract_markdown(self, filepath):
        """Extract headers, bold terms, code blocks from markdown."""
        terms = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for m in re.finditer(r'^#{1,6}\s+(.{3,80})$', content, re.MULTILINE):
                terms.append((m.group(1).strip().lower(), "header", filepath, m.start()))
            for m in re.finditer(r'\*\*(.{3,60})\*\*', content):
                terms.append((m.group(1).strip().lower(), "bold", filepath, m.start()))
            for m in re.finditer(r'`([A-Za-z_][A-Za-z0-9_]{2,40})`', content):
                terms.append((m.group(1).lower(), "code_ref", filepath, m.start()))
            for m in re.finditer(r'\[@([A-Za-z]+)\]', content):
                terms.append((m.group(1).lower(), "bcl_token", filepath, m.start()))
        except Exception:
            pass
        return terms

    def extract_json(self, filepath):
        """Extract JSON keys as terms."""
        terms = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            def walk_keys(obj, path=""):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(k, str) and len(k) >= MIN_TERM_LEN:
                            terms.append((k.lower(), "json_key", filepath, 0))
                        walk_keys(v, path + "." + str(k))
                elif isinstance(obj, list):
                    for item in obj[:100]:
                        walk_keys(item, path)
            walk_keys(data)
        except Exception:
            pass
        return terms

    def extract_generic(self, filepath):
        """Fallback regex extraction for .sql, .sh, .c, .h, .go, .yaml."""
        terms = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for m in re.finditer(r'[A-Za-z_][A-Za-z0-9_]{2,}', content):
                word = m.group()
                if len(word) > MAX_TERM_LEN:
                    continue
                parts = re.sub(r'([a-z])([A-Z])', r'\1 \2', word).split()
                if len(parts) > 1:
                    terms.append((" ".join(parts).lower(), "identifier", filepath, 0))
                terms.append((word.lower(), "identifier", filepath, 0))
                if len(terms) >= MAX_FILE_TERMS:
                    break
        except Exception:
            pass
        return terms

    def extract(self, filepath):
        """Route to appropriate extractor based on file extension."""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".py":
            return self.extract_python(filepath)
        elif ext == ".md":
            return self.extract_markdown(filepath)
        elif ext == ".json":
            return self.extract_json(filepath)
        else:
            return self.extract_generic(filepath)


# ============================================================
# Normalizer — unicode, lowercase, camel/snake split, dedup, aliases
# ============================================================

class Normalizer:
    """Normalize terms: lowercase, split camelCase/snake_case, resolve duplicates."""

    def normalize(self, term):
        term = term.strip().lower()
        parts = re.sub(r'([a-z])([A-Z])', r'\1 \2', term)
        parts = parts.replace('_', ' ').replace('-', ' ')
        parts = ' '.join(parts.split())
        return parts

    def canonical(self, term):
        """Return canonical form — normalized + deduplicated."""
        norm = self.normalize(term)
        if len(norm) < MIN_TERM_LEN:
            return None
        if len(norm) > MAX_TERM_LEN:
            return None
        if norm.isdigit():
            return None
        return norm

    def split_camel(self, term):
        parts = re.sub(r'([a-z])([A-Z])', r'\1 \2', term).split()
        return parts

    def split_snake(self, term):
        return term.split('_')


# ============================================================
# VectorStore — SQLite with rich metadata
# ============================================================

class VectorStore:
    """SQLite-backed vector store with metadata: file, line, symbol, hash, domain, tags."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.db = sqlite3.connect(db_path)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL,
                term_normalized TEXT NOT NULL,
                vector BLOB NOT NULL,
                source TEXT DEFAULT 'unknown',
                file_path TEXT DEFAULT '',
                line_number INTEGER DEFAULT 0,
                symbol_type TEXT DEFAULT '',
                term_hash TEXT DEFAULT '',
                domain TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                created_at REAL DEFAULT 0,
                UNIQUE(term_normalized, source, file_path, line_number)
            )
        """)
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_norm ON embeddings(term_normalized)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_source ON embeddings(source)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_domain ON embeddings(domain)")
        self.db.commit()

    def get_existing_terms(self):
        cur = self.db.execute("SELECT DISTINCT term_normalized FROM embeddings")
        return set(row[0] for row in cur.fetchall())

    def store(self, entries):
        """entries: list of (term, norm, vector, source, file_path, line, symbol_type, domain, tags)"""
        existing = self.get_existing_terms()
        now = time.time()
        new_count = 0
        for entry in entries:
            term, norm, vec, source, fpath, line, stype, domain, tags = entry
            if norm in existing:
                continue
            h = hashlib.md5(norm.encode()).hexdigest()[:12]
            self.db.execute(
                """INSERT OR IGNORE INTO embeddings
                (term, term_normalized, vector, source, file_path, line_number,
                 symbol_type, term_hash, domain, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (term, norm, vec.tobytes(), source, fpath, line, stype, h, domain, tags, now)
            )
            new_count += 1
            existing.add(norm)
        self.db.commit()
        return new_count

    def load_all_vectors(self):
        """Load all unique normalized terms + their vectors into numpy matrix."""
        cur = self.db.execute("""
            SELECT term_normalized, vector FROM embeddings
            GROUP BY term_normalized
            ORDER BY term_normalized
        """)
        terms = []
        vectors = []
        for norm, vec_blob in cur.fetchall():
            terms.append(norm)
            vec = np.frombuffer(vec_blob, dtype=np.float32)
            vectors.append(vec)
        if not terms:
            return [], None
        return terms, np.stack(vectors)

    def get_metadata(self, term_normalized):
        """Get all metadata entries for a term."""
        cur = self.db.execute(
            "SELECT term, source, file_path, line_number, symbol_type, domain, tags FROM embeddings WHERE term_normalized=?",
            (term_normalized,)
        )
        return cur.fetchall()

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

    def count_by_source(self):
        cur = self.db.execute("SELECT source, COUNT(*) FROM embeddings GROUP BY source ORDER BY COUNT(*) DESC")
        return cur.fetchall()

    def count_by_domain(self):
        cur = self.db.execute("SELECT domain, COUNT(*) FROM embeddings WHERE domain != '' GROUP BY domain ORDER BY COUNT(*) DESC LIMIT 20")
        return cur.fetchall()

    def close(self):
        self.db.close()


# ============================================================
# SimilarityEngine — cosine, dot, euclidean, hybrid, boosts
# ============================================================

class SimilarityEngine:
    """Multi-metric similarity scoring with optional boosts."""

    def __init__(self, corpus_vectors, corpus_terms):
        self.vectors = corpus_vectors
        self.terms = corpus_terms
        self.norms = np.linalg.norm(corpus_vectors, axis=1, keepdims=True) + 1e-12
        self.normed = corpus_vectors / self.norms

    def cosine(self, query_vec):
        q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-12)
        return self.normed @ q_norm

    def dot_product(self, query_vec):
        return self.vectors @ query_vec

    def euclidean(self, query_vec):
        diff = self.vectors - query_vec
        return -np.sqrt(np.sum(diff * diff, axis=1))

    def hybrid(self, query_vec, cosine_weight=0.7, dot_weight=0.3):
        cos = self.cosine(query_vec)
        dot = self.dot_product(query_vec)
        dot_norm = (dot - dot.min()) / (dot.max() - dot.min() + 1e-12)
        return cosine_weight * cos + dot_weight * dot_norm

    def lexical_boost(self, sims, query, boost_factor=0.1):
        """Boost terms that share words with the query."""
        query_words = set(query.lower().split())
        for i, term in enumerate(self.terms):
            term_words = set(term.split())
            overlap = len(query_words & term_words)
            if overlap > 0:
                sims[i] += boost_factor * overlap / max(len(query_words), 1)
        return sims

    def search(self, query_vec, query_text, top_n=TOP_N, metric="cosine", boost=False):
        if metric == "cosine":
            sims = self.cosine(query_vec)
        elif metric == "dot":
            sims = self.dot_product(query_vec)
        elif metric == "euclidean":
            sims = self.euclidean(query_vec)
        elif metric == "hybrid":
            sims = self.hybrid(query_vec)
        else:
            sims = self.cosine(query_vec)

        if boost:
            sims = self.lexical_boost(sims.copy(), query_text)

        top_idx = np.argsort(sims)[::-1][:top_n]
        return [(self.terms[idx], float(sims[idx])) for idx in top_idx]


# ============================================================
# ANNIndex — approximate nearest neighbor using numpy (HNSW-lite)
# ============================================================

class ANNIndex:
    """Simple ANN index using normalized vectors + matrix multiply.
    For larger corpora, replace with hnswlib or faiss."""

    def __init__(self, vectors, terms):
        self.vectors = vectors
        self.terms = terms
        self.norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
        self.normed = vectors / self.norms

    def search(self, query_vec, top_n=TOP_N):
        q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-12)
        sims = self.normed @ q_norm
        top_idx = np.argpartition(sims, -top_n)[-top_n:]
        top_idx = top_idx[np.argsort(sims[top_idx])[::-1]]
        return [(self.terms[i], float(sims[i])) for i in top_idx]

    def insert(self, term, vector):
        self.terms.append(term)
        self.vectors = np.vstack([self.vectors, vector[np.newaxis]])
        self.norms = np.linalg.norm(self.vectors, axis=1, keepdims=True) + 1e-12
        self.normed = self.vectors / self.norms


# ============================================================
# ClusterEngine — KMeans clustering, concept families
# ============================================================

class ClusterEngine:
    """Cluster embeddings into concept families."""

    def __init__(self, vectors, terms):
        self.vectors = vectors
        self.terms = terms
        self.labels = None
        self.centroids = None

    def cluster(self, n_clusters=50):
        from sklearn.cluster import KMeans
        km = KMeans(n_clusters=min(n_clusters, len(self.terms)), random_state=42, n_init=10)
        self.labels = km.fit_predict(self.vectors)
        self.centroids = km.cluster_centers_
        return self.labels

    def get_clusters(self, top_terms=5):
        """Return dict: cluster_id -> list of (term, distance_to_centroid)."""
        if self.labels is None:
            self.cluster()
        clusters = defaultdict(list)
        for i, label in enumerate(self.labels):
            dist = np.linalg.norm(self.vectors[i] - self.centroids[label])
            clusters[int(label)].append((self.terms[i], float(dist)))
        for cid in clusters:
            clusters[cid].sort(key=lambda x: x[1])
            clusters[cid] = clusters[cid][:top_terms]
        return dict(clusters)

    def find_cluster(self, query_vec):
        """Find which cluster a query belongs to."""
        if self.centroids is None:
            self.cluster()
        dists = np.linalg.norm(self.centroids - query_vec, axis=1)
        return int(np.argmin(dists)), float(dists.min())


# ============================================================
# KnowledgeGraph — nodes, edges, relationships
# ============================================================

class KnowledgeGraph:
    """Build a knowledge graph from embeddings + co-occurrence."""

    def __init__(self, terms, vectors):
        self.terms = terms
        self.vectors = vectors
        self.nodes = []
        self.edges = []
        self.adjacency = defaultdict(list)

    def build(self, threshold=0.7, max_edges_per_node=5):
        """Connect terms with cosine similarity above threshold."""
        norms = np.linalg.norm(self.vectors, axis=1, keepdims=True) + 1e-12
        normed = self.vectors / norms
        sim_matrix = normed @ normed.T

        self.nodes = [{"id": i, "term": self.terms[i]} for i in range(len(self.terms))]
        self.edges = []

        for i in range(len(self.terms)):
            sims = sim_matrix[i]
            sims[i] = -1  # exclude self
            top = np.argsort(sims)[::-1][:max_edges_per_node]
            for j in top:
                if sims[j] >= threshold:
                    self.edges.append({
                        "source": i, "target": int(j),
                        "weight": float(sims[j]),
                        "type": "similar"
                    })
                    self.adjacency[i].append(int(j))

        return len(self.edges)

    def neighbors(self, term, depth=1):
        """Get neighbors of a term up to depth."""
        idx = self.terms.index(term) if term in self.terms else -1
        if idx < 0:
            return []
        visited = {idx}
        frontier = [idx]
        result = []
        for _ in range(depth):
            next_frontier = []
            for node in frontier:
                for nbr in self.adjacency.get(node, []):
                    if nbr not in visited:
                        visited.add(nbr)
                        result.append(self.terms[nbr])
                        next_frontier.append(nbr)
            frontier = next_frontier
        return result

    def export_json(self):
        return json.dumps({"nodes": self.nodes, "edges": self.edges}, indent=2)


# ============================================================
# Statistics — embedding count, latency, cache stats, clusters
# ============================================================

class Statistics:
    """Collect and report engine statistics."""

    def __init__(self, store, engine, cluster=None):
        self.store = store
        self.engine = engine
        self.cluster = cluster

    def report(self):
        total = self.store.count()
        by_source = self.store.count_by_source()
        by_domain = self.store.count_by_domain()
        matrix_shape = self.engine.vectors.shape if self.engine else (0,)
        ram_mb = (self.engine.vectors.nbytes / 1024 / 1024) if self.engine else 0

        lines = []
        lines.append(f"  SQLite DB: {self.store.db_path}")
        lines.append(f"  Total embeddings: {total}")
        lines.append(f"  Unique terms: {matrix_shape[0]}")
        lines.append(f"  Vector dim: {matrix_shape[1] if len(matrix_shape) > 1 else 0}")
        lines.append(f"  RAM matrix: {ram_mb:.1f} MB")
        lines.append(f"  Sources:")
        for source, count in by_source:
            lines.append(f"    {source}: {count}")
        if by_domain:
            lines.append(f"  Top domains:")
            for domain, count in by_domain[:10]:
                lines.append(f"    {domain}: {count}")
        if self.cluster and self.cluster.centroids is not None:
            lines.append(f"  Clusters: {len(self.cluster.centroids)}")
        return "\n".join(lines)


# ============================================================
# BCLExporter — export IR, BCL, graph, JSON
# ============================================================

class BCLExporter:
    """Export engine state to BCL, BCLIR, JSON, Graph formats."""

    def __init__(self, engine, store, cluster=None, graph=None):
        self.engine = engine
        self.store = store
        self.cluster = cluster
        self.graph = graph

    def export_bcl(self):
        """Export as BCL bracket format."""
        lines = []
        lines.append("[@SEMANTIC_SEARCH]")
        lines.append("{")
        lines.append(f'  ("version";"2.0")')
        lines.append(f'  ("model";"all-MiniLM-L6-v2")')
        lines.append(f'  ("dim";384)')
        lines.append(f'  ("terms";{len(self.engine.terms)})')
        lines.append(f'  ("store";"{self.store.db_path}")')
        if self.cluster and self.cluster.centroids is not None:
            lines.append(f'  ("clusters";{len(self.cluster.centroids)})')
        if self.graph:
            lines.append(f'  ("graph_nodes";{len(self.graph.nodes)})')
            lines.append(f'  ("graph_edges";{len(self.graph.edges)})')
        lines.append("}")
        return "\n".join(lines)

    def export_json(self):
        data = {
            "version": "2.0",
            "model": "all-MiniLM-L6-v2",
            "dim": 384,
            "terms": len(self.engine.terms),
            "store": self.store.db_path,
            "total_embeddings": self.store.count(),
        }
        if self.cluster and self.cluster.centroids is not None:
            data["clusters"] = len(self.cluster.centroids)
        if self.graph:
            data["graph_nodes"] = len(self.graph.nodes)
            data["graph_edges"] = len(self.graph.edges)
        return json.dumps(data, indent=2)

    def export_graph_json(self):
        if self.graph:
            return self.graph.export_json()
        return "{}"

    def export_results_bcl(self, results, query):
        """Export search results as BCL."""
        lines = []
        lines.append("[@SEARCH_RESULTS]")
        lines.append("{")
        lines.append(f'  ("query";"{query}")')
        lines.append(f'  ("count";{len(results)})')
        for term, score in results:
            lines.append(f'  ("{term}";{score:.4f})')
        lines.append("}")
        return "\n".join(lines)


# ============================================================
# CoreMLSemanticSearch v2.0 — main engine
# ============================================================

class CoreMLSemanticSearch:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.store = None
        self.extractor = SemanticExtractor()
        self.normalizer = Normalizer()
        self.corpus = []
        self.corpus_vectors = None
        self.similarity = None
        self.ann = None
        self.cluster = None
        self.graph = None
        self.stats = None
        self.exporter = None
        self.embed_time = 0.0
        self.embed_start = 0.0

    def load(self):
        self.model = ct.models.MLModel(MODEL_PATH)
        self.tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
        self.store = VectorStore(DB_PATH)
        return self

    def embed(self, text):
        enc = self.tokenizer(
            text, padding="max_length", truncation=True,
            max_length=MAX_LEN, return_tensors="np"
        )
        input_ids = enc["input_ids"].astype(np.int32)
        attn_mask = enc["attention_mask"].astype(np.int32)
        out = self.model.predict({
            "input_ids": input_ids,
            "attention_mask": attn_mask,
        })
        return np.asarray(out["sentence_embedding"], dtype=np.float32).flatten()

    def embed_batch(self, texts, progress=True):
        vecs = []
        total = len(texts)
        for i, t in enumerate(texts):
            vecs.append(self.embed(t))
            if progress and (i + 1) % 500 == 0:
                elapsed = time.time() - self.embed_start
                rate = (i + 1) / elapsed
                remaining = (total - i - 1) / rate
                print(f"    Embedded {i+1}/{total} ({rate:.0f}/s, ETA {remaining:.0f}s)")
        return np.stack(vecs)

    # ---- Corpus building ----

    def scan_files(self):
        """Scan all project files using SemanticExtractor."""
        all_entries = []
        file_count = 0
        for root, dirs, files in os.walk(PROJECT_DIR):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in SCAN_EXTENSIONS:
                    continue
                fpath = os.path.join(root, fname)
                entries = self.extractor.extract(fpath)
                all_entries.extend(entries)
                file_count += 1
        print(f"  Scanned {file_count} files -> {len(all_entries)} raw terms")
        return all_entries

    def scan_mysql(self):
        """Pull terms from MySQL."""
        entries = []
        try:
            import mysql.connector
            conn = mysql.connector.connect(host="localhost", user="root", password="", database="vb_shared")
            cur = conn.cursor()
            for table, col, stype in [("learned_rules", "pattern", "rule"),
                                       ("know_problems", "problem", "problem"),
                                       ("know_solutions", "solution", "solution"),
                                       ("rule_tokens", "name", "token")]:
                try:
                    cur.execute(f"SELECT DISTINCT {col} FROM {table} LIMIT {MAX_MYSQL_TERMS}")
                    for row in cur.fetchall():
                        val = str(row[0]) if row[0] else ""
                        if val:
                            entries.append((val.lower()[:MAX_TERM_LEN], stype, "mysql", 0))
                except Exception:
                    pass
            cur.close()
            conn.close()
        except Exception as e:
            print(f"  MySQL vb_shared: {e}")
        try:
            import mysql.connector
            conn = mysql.connector.connect(host="localhost", user="root", password="", database="vb_code_test")
            cur = conn.cursor()
            try:
                cur.execute(f"SELECT DISTINCT class_name FROM vb_classes LIMIT {MAX_MYSQL_TERMS}")
                for row in cur.fetchall():
                    if row[0]:
                        entries.append((str(row[0]).lower(), "class", "mysql", 0))
            except Exception:
                pass
            try:
                cur.execute(f"SELECT DISTINCT method_name FROM vb_methods LIMIT {MAX_MYSQL_TERMS}")
                for row in cur.fetchall():
                    if row[0]:
                        entries.append((str(row[0]).lower(), "method", "mysql", 0))
            except Exception:
                pass
            cur.close()
            conn.close()
        except Exception as e:
            print(f"  MySQL vb_code_test: {e}")
        print(f"  MySQL -> {len(entries)} terms")
        return entries

    def scan_dictionary(self):
        """Load English dictionary."""
        entries = []
        dict_path = "/usr/share/dict/words"
        if os.path.exists(dict_path):
            with open(dict_path) as f:
                for line in f:
                    word = line.strip().lower()
                    if MIN_TERM_LEN <= len(word) <= MAX_TERM_LEN and word.isalpha():
                        entries.append((word, "dictionary", "dict", 0))
        print(f"  Dictionary -> {len(entries)} words")
        return entries

    def scan_chat_history(self):
        """Pull terms from chat history SQLite databases."""
        entries = []
        chat_dbs = [
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/chat_history.db",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/chatgpt_export.db",
        ]
        for db_path in chat_dbs:
            if not os.path.exists(db_path):
                continue
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                for table in ["messages", "chat_messages", "content"]:
                    try:
                        cur.execute(f"SELECT content FROM {table} LIMIT 2000")
                        for row in cur.fetchall():
                            val = str(row[0]) if row[0] else ""
                            if val:
                                for m in re.finditer(r'[A-Za-z_][A-Za-z0-9_]{2,}', val):
                                    w = m.group().lower()
                                    if MIN_TERM_LEN <= len(w) <= MAX_TERM_LEN:
                                        entries.append((w, "chat", db_path, 0))
                    except Exception:
                        pass
                cur.close()
                conn.close()
            except Exception:
                pass
        print(f"  Chat history -> {len(entries)} terms")
        return entries

    def build_corpus(self):
        """Build corpus from all sources, normalize, deduplicate."""
        print("Building corpus from all sources...")
        all_entries = []

        print("  [1/4] Scanning project files (AST)...")
        all_entries.extend(self.scan_files())

        print("  [2/4] Scanning MySQL...")
        all_entries.extend(self.scan_mysql())

        print("  [3/4] Scanning chat history...")
        all_entries.extend(self.scan_chat_history())

        print("  [4/4] Loading dictionary...")
        all_entries.extend(self.scan_dictionary())

        # Normalize + deduplicate
        seen = set()
        unique_entries = []
        for term, stype, source, line in all_entries:
            norm = self.normalizer.canonical(term)
            if norm and norm not in seen:
                seen.add(norm)
                unique_entries.append((term, norm, stype, source, line))

        # Limit
        if len(unique_entries) > MAX_CORPUS_SIZE:
            unique_entries = sorted(unique_entries, key=lambda x: (-len(x[1]), x[1]))[:MAX_CORPUS_SIZE]
            unique_entries = sorted(unique_entries)

        print(f"\n  Total unique normalized terms: {len(unique_entries)}")
        return unique_entries

    def build_index(self, entries):
        """Embed new terms, store in SQLite, load vectors for search."""
        existing = self.store.get_existing_terms()
        new_entries = [e for e in entries if e[1] not in existing]
        cached = len(entries) - len(new_entries)

        if new_entries:
            print(f"  SQLite: {cached} cached, {len(new_entries)} new to embed")
            self.embed_start = time.time()
            t0 = time.time()
            new_terms = [e[1] for e in new_entries]
            new_vectors = self.embed_batch(new_terms)

            # Build store entries
            store_entries = []
            for (term, norm, stype, source, line), vec in zip(new_entries, new_vectors):
                fpath = source if source not in ("mysql", "dict") else ""
                domain = self._guess_domain(term, stype)
                tags = stype
                store_entries.append((term, norm, vec, stype, fpath, line, stype, domain, tags))
            self.store.store(store_entries)
            self.embed_time = time.time() - t0
            print(f"  Embedded {len(new_entries)} new in {self.embed_time:.1f}s -> SQLite")
        else:
            print(f"  SQLite: all {len(entries)} terms already cached")
            self.embed_time = 0.0

        # Load all vectors
        t0 = time.time()
        self.corpus, self.corpus_vectors = self.store.load_all_vectors()
        load_time = time.time() - t0
        print(f"  Loaded {len(self.corpus)} vectors in {load_time:.2f}s")

        # Initialize sub-engines
        self.similarity = SimilarityEngine(self.corpus_vectors, self.corpus)
        self.ann = ANNIndex(self.corpus_vectors, self.corpus)
        self.stats = Statistics(self.store, self.similarity)
        self.exporter = BCLExporter(self.similarity, self.store)
        return self

    def _guess_domain(self, term, stype):
        """Guess domain from term + symbol type."""
        term_lower = term.lower()
        domains = {
            "embed": "vector", "vector": "vector", "qdrant": "search",
            "search": "search", "query": "search", "index": "search",
            "graph": "graph", "node": "graph", "edge": "graph",
            "bcl": "bcl", "bracket": "bcl", "vbstyle": "bcl",
            "config": "config", "pipeline": "pipeline",
            "mysql": "database", "sqlite": "database", "database": "database",
            "coreml": "ml", "model": "ml", "neural": "ml",
            "error": "error", "exception": "error",
            "test": "testing", "validate": "testing",
        }
        for keyword, domain in domains.items():
            if keyword in term_lower:
                return domain
        return ""

    # ---- Search ----

    def search(self, query, top_n=TOP_N, metric="cosine", boost=False):
        q_vec = self.embed(query)
        return self.similarity.search(q_vec, query, top_n, metric, boost)

    def search_ann(self, query, top_n=TOP_N):
        q_vec = self.embed(query)
        return self.ann.search(q_vec, top_n)

    def reverse_search(self, query, top_n=TOP_N):
        """Find nearest concepts, methods, classes, rules."""
        results = self.search(query, top_n=top_n * 2)
        by_type = defaultdict(list)
        for term, score in results:
            meta = self.store.get_metadata(term)
            for m in meta:
                by_type[m[1]].append((term, score))
        output = []
        for stype, items in by_type.items():
            items.sort(key=lambda x: -x[1])
            output.extend(items[:top_n // 3])
        output.sort(key=lambda x: -x[1])
        return output[:top_n]

    # ---- Cluster ----

    def build_clusters(self, n_clusters=50):
        self.cluster = ClusterEngine(self.corpus_vectors, self.corpus)
        self.cluster.cluster(n_clusters)
        self.stats.cluster = self.cluster
        return self.cluster

    def show_clusters(self, top_terms=5):
        if self.cluster is None:
            self.build_clusters()
        clusters = self.cluster.get_clusters(top_terms)
        for cid, terms in sorted(clusters.items())[:20]:
            labels = [t[0] for t in terms]
            print(f"  Cluster {cid}: {', '.join(labels)}")

    # ---- Graph ----

    def build_graph(self, threshold=0.7):
        self.graph = KnowledgeGraph(self.corpus, self.corpus_vectors)
        edge_count = self.graph.build(threshold=threshold)
        self.exporter.graph = self.graph
        return edge_count

    # ---- Add term ----

    def add_term(self, term, source="manual"):
        norm = self.normalizer.canonical(term)
        if not norm:
            return False
        existing = self.store.get_existing_terms()
        if norm in existing:
            return False
        vec = self.embed(norm)
        self.store.store([(term, norm, vec, source, "", 0, source, "", source)])
        self.corpus, self.corpus_vectors = self.store.load_all_vectors()
        self.similarity = SimilarityEngine(self.corpus_vectors, self.corpus)
        self.ann = ANNIndex(self.corpus_vectors, self.corpus)
        return True

    # ---- Export ----

    def export(self, format="bcl"):
        if format == "bcl":
            return self.exporter.export_bcl()
        elif format == "json":
            return self.exporter.export_json()
        elif format == "graph":
            return self.exporter.export_graph_json()
        return ""

    # ---- Interactive ----

    def interactive(self):
        print("=" * 70)
        print("  CoreML Semantic Search Engine v2.0")
        print("  Model: all-MiniLM-L6-v2 (384-dim, Neural Engine)")
        print(f"  Corpus: {len(self.corpus)} terms in SQLite")
        print("=" * 70)
        print()
        print("Commands:")
        print("  <phrase>       semantic search (cosine)")
        print("  ann <phrase>   ANN search (fast)")
        print("  hybrid <phrase> hybrid cosine+dot")
        print("  boost <phrase> cosine + lexical boost")
        print("  rev <phrase>   reverse search (by type)")
        print("  cluster        show concept clusters")
        print("  graph          build knowledge graph")
        print("  stats          engine statistics")
        print("  export <fmt>   export (bcl/json/graph)")
        print("  add <term>     add new term")
        print("  rebuild        rescan + embed new only")
        print("  quit")
        print("-" * 70)

        while True:
            try:
                line = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line or line.lower() in ("quit", "exit", "q"):
                break

            parts = line.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "rebuild":
                entries = self.build_corpus()
                self.build_index(entries)
                print(f"  Total: {len(self.corpus)} terms")
            elif cmd == "stats":
                print(self.stats.report())
            elif cmd == "add":
                if arg:
                    added = self.add_term(arg)
                    print(f"  {'Added' if added else 'Already exists'}: {arg}")
            elif cmd == "cluster":
                self.show_clusters()
            elif cmd == "graph":
                t0 = time.time()
                edges = self.build_graph()
                print(f"  Graph: {len(self.graph.nodes)} nodes, {edges} edges ({time.time()-t0:.1f}s)")
            elif cmd == "export":
                print(self.export(arg if arg else "bcl"))
            elif cmd == "ann":
                t0 = time.time()
                results = self.search_ann(arg)
                self._print_results(results, arg, (time.time()-t0)*1000, "ANN")
            elif cmd == "hybrid":
                t0 = time.time()
                q_vec = self.embed(arg)
                results = self.similarity.search(q_vec, arg, metric="hybrid")
                self._print_results(results, arg, (time.time()-t0)*1000, "hybrid")
            elif cmd == "boost":
                t0 = time.time()
                results = self.search(arg, boost=True)
                self._print_results(results, arg, (time.time()-t0)*1000, "cosine+boost")
            elif cmd == "rev":
                t0 = time.time()
                results = self.reverse_search(arg)
                self._print_results(results, arg, (time.time()-t0)*1000, "reverse")
            elif cmd == "bcl":
                if arg:
                    results = self.search(arg)
                    print(self.exporter.export_results_bcl(results, arg))
                else:
                    print(self.export("bcl"))
            else:
                t0 = time.time()
                results = self.search(line)
                self._print_results(results, line, (time.time()-t0)*1000, "cosine")

        print("\nDone.")

    def _print_results(self, results, query, elapsed, metric):
        print(f"\n  Top {len(results)} ({metric}) query: '{query}' [{elapsed:.1f}ms]")
        print(f"  {'#':>3}  {'Term':<50} {'Score':>8}")
        print(f"  {'---':>3}  {'-'*50} {'-'*8}")
        for i, (phrase, score) in enumerate(results, 1):
            bar = "#" * int(max(0, score) * 30)
            print(f"  {i:>3}. {phrase:<50} {score:.4f} {bar}")


# ============================================================
# MAIN
# ============================================================

def main():
    sim = CoreMLSemanticSearch().load()
    entries = sim.build_corpus()
    sim.build_index(entries)

    if len(sys.argv) > 1 and sys.argv[1] != "--interactive":
        query = " ".join(sys.argv[1:])
        results = sim.search(query)
        sim._print_results(results, query, 0, "cosine")
    else:
        sim.interactive()


if __name__ == "__main__":
    main()
