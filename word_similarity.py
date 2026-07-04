#!/usr/bin/env python3
"""
CoreML Semantic Search Engine
Input a word/phrase -> get top N semantically similar terms from ALL your data.

Corpus sources (scanned automatically):
  - All .py, .md, .json, .yaml files in the project (class names, function names, concepts)
  - MySQL vb_shared: learned_rules.pattern, know_problems.problem, know_solutions.solution
  - MySQL vb_code_test: vb_classes.class_name, vb_methods.method_name
  - English dictionary: /usr/share/dict/words
  - Chat history databases

Model: all-MiniLM-L6-v2 (CoreML .mlpackage, 384-dim embeddings, Neural Engine)
Tokenizer: sentence-transformers/all-MiniLM-L6-v2 (BERT tokenizer, vocab 30522)
Latency: ~1.2 ms/embed on Neural Engine
Cache: Embeddings stored in SQLite (persistent, incremental). Only new terms get embedded.
         Once embedded, you never need the original files again — the SQLite DB IS the compressed knowledge.
"""

import coremltools as ct
import numpy as np
import time
import sys
import os
import re
import json
import sqlite3
from pathlib import Path
from collections import Counter
from transformers import AutoTokenizer

MODEL_PATH = "/Users/wws/Documents/Models/MiniLM-L12-v2/all-MiniLM-L12-v2-converted/all-MiniLM-L6-v2_6136536182.mlpackage"
TOKENIZER_PATH = "sentence-transformers/all-MiniLM-L6-v2"
MAX_LEN = 128
EMBED_DIM = 384
TOP_N = 20
DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/semantic_corpus.db"

PROJECT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine"
SCAN_EXTENSIONS = {".py", ".md", ".json", ".yaml", ".yml", ".sql", ".sh", ".go", ".c", ".h"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".DS_Store", "Archive", "archive",
             "chat_resources", "Cascade_toolStack", "Dom_CoreML_Layout"}
MIN_TERM_LEN = 3
MAX_TERM_LEN = 80
MAX_CORPUS_SIZE = 50000
MAX_FILE_TERMS = 200
MAX_MYSQL_TERMS = 5000


def extract_terms_from_text(text, max_terms=MAX_FILE_TERMS):
    """Extract meaningful terms/phrases from text."""
    terms = set()
    # CamelCase / snake_case identifiers
    for m in re.finditer(r'[A-Za-z_][A-Za-z0-9_]{2,}', text):
        word = m.group()
        if len(word) < MIN_TERM_LEN or len(word) > MAX_TERM_LEN:
            continue
        if word.isdigit():
            continue
        # Split CamelCase into words
        parts = re.sub(r'([a-z])([A-Z])', r'\1 \2', word).split()
        if len(parts) > 1:
            terms.add(" ".join(parts).lower())
        terms.add(word.lower())
        if len(terms) >= max_terms:
            break
    # Multi-word phrases from markdown headings / definitions
    for m in re.finditer(r'^[#>*-]+\s+(.{5,80})$', text, re.MULTILINE):
        phrase = m.group(1).strip().lower()
        if len(phrase) >= MIN_TERM_LEN and len(phrase) <= MAX_TERM_LEN:
            terms.add(phrase)
    # BCL tokens like [@Something]
    for m in re.finditer(r'\[@([A-Za-z]+)\]', text):
        terms.add(m.group(1).lower())
    return list(terms)


def scan_files(project_dir, max_terms_per_file=MAX_FILE_TERMS):
    """Scan all source files and extract unique terms."""
    all_terms = set()
    file_count = 0
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SCAN_EXTENSIONS:
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                terms = extract_terms_from_text(content, max_terms_per_file)
                all_terms.update(terms)
                file_count += 1
            except Exception:
                pass
    print(f"  Scanned {file_count} files -> {len(all_terms)} unique terms")
    return list(all_terms)


def scan_mysql():
    """Pull terms from MySQL knowledge base."""
    terms = set()
    try:
        import mysql.connector
        conn = mysql.connector.connect(host="localhost", user="root", password="", database="vb_shared")
        cur = conn.cursor()
        for table_col in [("learned_rules", "pattern"), ("know_problems", "problem"),
                          ("know_solutions", "solution"), ("rule_tokens", "name"),
                          ("rule_tokens", "bracket_body"), ("rules", "rule")]:
            table, col = table_col
            try:
                cur.execute(f"SELECT DISTINCT {col} FROM {table} LIMIT {MAX_MYSQL_TERMS}")
                for row in cur.fetchall():
                    val = str(row[0]) if row[0] else ""
                    if val:
                        extracted = extract_terms_from_text(val, max_terms=20)
                        terms.update(extracted)
            except Exception:
                pass
        cur.close()
        conn.close()
        print(f"  MySQL vb_shared -> {len(terms)} unique terms")
    except Exception as e:
        print(f"  MySQL vb_shared: {e}")
    # vb_code_test
    try:
        import mysql.connector
        conn = mysql.connector.connect(host="localhost", user="root", password="", database="vb_code_test")
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT DISTINCT class_name FROM vb_classes LIMIT {MAX_MYSQL_TERMS}")
            for row in cur.fetchall():
                if row[0]:
                    terms.add(str(row[0]).lower())
        except Exception:
            pass
        try:
            cur.execute(f"SELECT DISTINCT method_name FROM vb_methods LIMIT {MAX_MYSQL_TERMS}")
            for row in cur.fetchall():
                if row[0]:
                    terms.add(str(row[0]).lower())
        except Exception:
            pass
        cur.close()
        conn.close()
        print(f"  MySQL vb_code_test -> total {len(terms)} unique terms")
    except Exception as e:
        print(f"  MySQL vb_code_test: {e}")
    return list(terms)


def scan_dictionary():
    """Load English dictionary."""
    terms = set()
    dict_path = "/usr/share/dict/words"
    if os.path.exists(dict_path):
        with open(dict_path) as f:
            for line in f:
                word = line.strip().lower()
                if MIN_TERM_LEN <= len(word) <= MAX_TERM_LEN and word.isalpha():
                    terms.add(word)
        print(f"  Dictionary -> {len(terms)} words")
    return list(terms)


def scan_chat_history():
    """Pull terms from chat history SQLite databases."""
    terms = set()
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
            # Try common table/column patterns
            for table in ["messages", "chat_messages", "content"]:
                try:
                    cur.execute(f"SELECT content FROM {table} LIMIT 2000")
                    for row in cur.fetchall():
                        val = str(row[0]) if row[0] else ""
                        if val:
                            extracted = extract_terms_from_text(val, max_terms=15)
                            terms.update(extracted)
                except Exception:
                    pass
            cur.close()
            conn.close()
        except Exception:
            pass
    if terms:
        print(f"  Chat history -> {len(terms)} unique terms")
    return list(terms)


def build_corpus():
    """Build corpus from all sources."""
    print("Building corpus from all sources...")
    all_terms = set()

    # 1. Scan project files
    print("  [1/4] Scanning project files...")
    file_terms = scan_files(PROJECT_DIR)
    all_terms.update(file_terms)

    # 2. MySQL knowledge base
    print("  [2/4] Scanning MySQL...")
    mysql_terms = scan_mysql()
    all_terms.update(mysql_terms)

    # 3. Chat history
    print("  [3/4] Scanning chat history...")
    chat_terms = scan_chat_history()
    all_terms.update(chat_terms)

    # 4. Dictionary (optional, adds bulk)
    print("  [4/4] Loading dictionary...")
    dict_terms = scan_dictionary()
    all_terms.update(dict_terms)

    # Sort and limit
    sorted_terms = sorted(all_terms)
    if len(sorted_terms) > MAX_CORPUS_SIZE:
        # Prefer longer phrases (more informative)
        sorted_terms = sorted(sorted_terms, key=lambda t: (-len(t), t))[:MAX_CORPUS_SIZE]
        sorted_terms = sorted(sorted_terms)

    print(f"\n  Total corpus: {len(sorted_terms)} unique terms")
    return sorted_terms


class CoreMLSemanticSearch:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.corpus = []
        self.corpus_vectors = None
        self.embed_time = 0.0
        self.cache_loaded = False
        self.db = None
        self.term_to_idx = {}

    def load(self):
        self.model = ct.models.MLModel(MODEL_PATH)
        self.tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
        self.db = sqlite3.connect(DB_PATH)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                term TEXT PRIMARY KEY,
                vector BLOB NOT NULL,
                source TEXT DEFAULT 'unknown',
                created_at REAL DEFAULT 0
            )
        """)
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_term ON embeddings(term)")
        self.db.commit()
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

    def _get_existing_terms(self):
        """Return set of terms already in SQLite DB."""
        cur = self.db.execute("SELECT term FROM embeddings")
        return set(row[0] for row in cur.fetchall())

    def _load_vectors_from_db(self):
        """Load all vectors from SQLite into numpy matrix for fast search."""
        cur = self.db.execute("SELECT term, vector FROM embeddings ORDER BY term")
        terms = []
        vectors = []
        for term, vec_blob in cur.fetchall():
            terms.append(term)
            vec = np.frombuffer(vec_blob, dtype=np.float32)
            vectors.append(vec)
        if not terms:
            return [], None
        return terms, np.stack(vectors)

    def _store_vectors(self, terms, vectors, source="scan"):
        """Store new terms + vectors into SQLite. Skip existing."""
        existing = self._get_existing_terms()
        new_count = 0
        now = time.time()
        for term, vec in zip(terms, vectors):
            if term in existing:
                continue
            self.db.execute(
                "INSERT OR IGNORE INTO embeddings (term, vector, source, created_at) VALUES (?, ?, ?, ?)",
                (term, vec.tobytes(), source, now)
            )
            new_count += 1
        self.db.commit()
        return new_count

    def build_index(self, corpus, use_cache=True):
        """Build index using SQLite as persistent store. Only embed NEW terms."""
        # Check what's already in DB
        existing = self._get_existing_terms()
        new_terms = [t for t in corpus if t not in existing]
        cached_count = len(corpus) - len(new_terms)

        if new_terms:
            print(f"  SQLite cache: {cached_count} existing, {len(new_terms)} new terms to embed")
            self.embed_start = time.time()
            t0 = time.time()
            new_vectors = self.embed_batch(new_terms)
            self.embed_time = time.time() - t0
            self._store_vectors(new_terms, new_vectors, source="scan")
            print(f"  Embedded {len(new_terms)} new terms in {self.embed_time:.1f}s -> SQLite")
        else:
            print(f"  SQLite cache: all {len(corpus)} terms already embedded")
            self.embed_time = 0.0
            self.cache_loaded = True

        # Load all vectors from SQLite into RAM for fast cosine search
        t0 = time.time()
        self.corpus, self.corpus_vectors = self._load_vectors_from_db()
        load_time = time.time() - t0
        self.term_to_idx = {t: i for i, t in enumerate(self.corpus)}
        print(f"  Loaded {len(self.corpus)} vectors from SQLite in {load_time:.2f}s")
        return self

    def add_term(self, term, source="manual"):
        """Add a single term. Embed + store in SQLite. No full rebuild needed."""
        term = term.lower().strip()
        if term in self._get_existing_terms():
            return False
        vec = self.embed(term)
        self._store_vectors([term], [vec], source=source)
        # Reload vectors
        self.corpus, self.corpus_vectors = self._load_vectors_from_db()
        self.term_to_idx = {t: i for i, t in enumerate(self.corpus)}
        return True

    def search(self, query, top_n=TOP_N):
        q_vec = self.embed(query)
        q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-12)
        c_norms = np.linalg.norm(self.corpus_vectors, axis=1, keepdims=True) + 1e-12
        c_normed = self.corpus_vectors / c_norms
        sims = c_normed @ q_norm
        top_idx = np.argsort(sims)[::-1][:top_n]
        return [(self.corpus[idx], float(sims[idx])) for idx in top_idx]

    def interactive(self):
        print("=" * 70)
        print("  CoreML Semantic Search Engine")
        print("  Model: all-MiniLM-L6-v2 (384-dim, Neural Engine)")
        print(f"  Corpus: {len(self.corpus)} terms from files + MySQL + chat + dict")
        if self.cache_loaded:
            print(f"  Index: loaded from cache")
        else:
            print(f"  Index build: {self.embed_time:.1f}s ({len(self.corpus)/self.embed_time:.0f} embeds/s)")
        print(f"  Query latency: ~1.2 ms + search")
        print("=" * 70)
        print()
        print("Commands: 'quit' | 'rebuild' | 'add <term>' | 'stats' | type any phrase to search")
        print("-" * 70)

        while True:
            try:
                query = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not query or query.lower() in ("quit", "exit", "q"):
                break
            if query.lower() == "rebuild":
                print("Rebuilding corpus...")
                corpus = build_corpus()
                self.build_index(corpus, use_cache=True)
                print(f"  Total: {len(self.corpus)} terms in SQLite")
                continue
            if query.lower() == "stats":
                cur = self.db.execute("SELECT COUNT(*), source, COUNT(*) FROM embeddings GROUP BY source")
                total = self.db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
                print(f"\n  SQLite DB: {DB_PATH}")
                print(f"  Total terms: {total}")
                print(f"  Matrix: {self.corpus_vectors.shape} ({self.corpus_vectors.nbytes / 1024 / 1024:.1f} MB in RAM)")
                continue
            if query.lower().startswith("add "):
                term = query[4:].strip()
                if term:
                    added = self.add_term(term)
                    if added:
                        print(f"  Added '{term}' -> now {len(self.corpus)} terms")
                    else:
                        print(f"  '{term}' already exists")
                continue

            t0 = time.time()
            results = self.search(query)
            elapsed = (time.time() - t0) * 1000

            print(f"\n  Top {TOP_N} Similar (query: '{query}') [{elapsed:.1f}ms]")
            print(f"  {'#':>3}  {'Term':<50} {'Score':>8}")
            print(f"  {'---':>3}  {'-'*50} {'-'*8}")
            for i, (phrase, score) in enumerate(results, 1):
                bar = "#" * int(score * 30)
                print(f"  {i:>3}. {phrase:<50} {score:.4f} {bar}")

        print("\nDone.")


def main():
    sim = CoreMLSemanticSearch().load()

    # Build corpus from all sources
    corpus = build_corpus()
    sim.build_index(corpus, use_cache=True)

    if len(sys.argv) > 1 and sys.argv[1] != "--interactive":
        query = " ".join(sys.argv[1:])
        results = sim.search(query)
        print(f"\nTop {TOP_N} similar to '{query}':")
        print(f"  {'#':>3}  {'Term':<50} {'Score':>8}")
        print(f"  {'---':>3}  {'-'*50} {'-'*8}")
        for i, (phrase, score) in enumerate(results, 1):
            print(f"  {i:>3}. {phrase:<50} {score:.4f}")
    else:
        sim.interactive()


if __name__ == "__main__":
    main()
