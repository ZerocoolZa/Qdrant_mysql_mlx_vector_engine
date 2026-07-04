#!/usr/bin/env python3
#[@GHOST]{file_path="core/Piplines/vb_bridge.py" date="2026-07-04" author="Cascade" session_id="monkey-see-monkey-do" context="Bridge: MiniLM vectors → VBEngine training.bin + init_model.bin. Monkey see, monkey do."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE spaces only"}
#[@FILEID]{id="vb_bridge.py" domain="Piplines" authority="VBBridge"}
#[@SUMMARY]{summary="Extract MiniLM 384-dim vectors from semantic_corpus.db, scan code corpus for skip-gram pairs, write VBEngine training.bin + init_model.bin with MiniLM vectors as initial weights."}

"""
VBEngine Bridge — Monkey See, Monkey Do

Pipeline:
  1. Read MiniLM vectors from semantic_corpus.db (term → 384-dim float32)
  2. Scan code/BCL files → tokenize → build vocab (intersection with MiniLM terms)
  3. Generate skip-gram pairs with dynamic window
  4. Write training.bin (W2VT format, dims=384) — VBEngine's lunchbox
  5. Write init_model.bin (W2VC format, W_in=MiniLM vectors) — VBEngine's starting brain

Usage:
  python3 vb_bridge.py --db semantic_corpus.db --outdir .

Then:
  ./c_word2vec_metal_packed --train --pairs training.bin --model model.bin --init-model init_model.bin --dims 384 --epochs 5

Then:
  python3 vb_export.py --model model.bin --db semantic_corpus.db
"""

import sqlite3
import numpy as np
import os
import re
import struct
import time
import sys
from collections import Counter

PROJECT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine"
DB_PATH = os.path.join(PROJECT_DIR, "semantic_corpus.db")
SCAN_EXTENSIONS = {".py", ".md", ".json", ".yaml", ".yml", ".sql", ".sh", ".go", ".c", ".h", ".mm", ".bcl", ".bclir"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".DS_Store", "Archive", "archive",
             "chat_resources", "Cascade_toolStack", "Dom_CoreML_Layout", "treasure_trove_backup",
             ".backup", ".bookmarkai"}
EMBED_DIM = 384
WINDOW = 8
MIN_COUNT = 5
MAX_VOCAB = 200000
MAX_PAIRS = 0  # 0 = unlimited
SUBSAMPLE_T = 1e-4  # subsampling threshold — frequent words like 'for','self','class' get downsampled

TOKEN_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def load_minilm_vectors(db_path):
    """Load original scan-source vectors from semantic_corpus.db.
    Only loads source='scan' to avoid contamination from previous vbengine/wordnet training runs."""
    conn = sqlite3.connect(db_path)
    # Prefer 'scan' source (original pre-trained vectors, not retrained)
    cur = conn.execute("SELECT term, vector FROM embeddings WHERE source='scan' ORDER BY term")
    rows = cur.fetchall()
    if len(rows) == 0:
        # Fallback: load all if no 'scan' source exists
        cur = conn.execute("SELECT term, vector FROM embeddings ORDER BY term")
        rows = cur.fetchall()
    terms = []
    vectors = []
    for term, vec_blob in rows:
        vec = np.frombuffer(vec_blob, dtype=np.float32)
        if vec.shape[0] == EMBED_DIM:
            terms.append(term.lower())
            vectors.append(vec)
    conn.close()
    term_to_vec = {}
    for t, v in zip(terms, vectors):
        if t not in term_to_vec:
            term_to_vec[t] = v
    sys.stderr.write("[BRIDGE] Loaded %d MiniLM vectors (%d-dim) from %s\n" % (len(term_to_vec), EMBED_DIM, db_path))
    return term_to_vec


def scan_corpus(project_dir):
    """Scan all source files, return list of (filepath, token_list)."""
    files = []
    for root, dirs, filenames in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SCAN_EXTENSIONS:
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                tokens = [t.lower() for t in TOKEN_RE.findall(content) if len(t) >= 2]
                if len(tokens) > 5:
                    files.append(tokens)
            except Exception:
                pass
    sys.stderr.write("[BRIDGE] Scanned %d files\n" % len(files))
    return files


def build_vocab(files, minilm_terms, min_count=MIN_COUNT):
    """Build vocabulary from ALL code tokens. MiniLM membership not required —
    words without MiniLM vectors get random init instead."""
    freq = Counter()
    for tokens in files:
        freq.update(tokens)

    vocab = []
    for word, count in freq.most_common():
        if count < min_count:
            continue
        if len(word) < 3 or len(word) > 80:
            continue
        if word.startswith("_"):
            continue
        if word.isdigit() or word.replace("_", "").isdigit():
            continue
        vocab.append((word, count))

    vocab.sort(key=lambda x: x[0])
    if len(vocab) > MAX_VOCAB:
        vocab = vocab[:MAX_VOCAB]

    word_to_idx = {}
    word_list = []
    freq_list = []
    for word, count in vocab:
        word_to_idx[word] = len(word_list)
        word_list.append(word)
        freq_list.append(count)

    minilm_hits = sum(1 for w in word_list if w in minilm_terms)
    sys.stderr.write("[BRIDGE] Vocab: %d words (min_count=%d, MiniLM init: %d, random init: %d)\n" % (len(word_list), min_count, minilm_hits, len(word_list) - minilm_hits))
    return word_list, freq_list, word_to_idx


def write_training_bin_streaming(path, dims, vocab_words, vocab_freqs, files, word_to_idx, window, neg, epochs, lr_start, lr_end):
    """Write training.bin in W2VT format. Streams pairs to disk in chunks — no giant in-memory list.
    Applies subsampling: frequent words (for, self, class) are randomly discarded with
    probability 1 - sqrt(t/freq) to reduce noise from overly common tokens."""
    import random
    rng = random.Random(42)

    # Compute subsampling discard probabilities
    total_tokens = sum(vocab_freqs)
    discard_prob = {}
    for i, freq in enumerate(vocab_freqs):
        f = freq / total_tokens
        if f <= 0:
            discard_prob[i] = 0.0
        else:
            # Standard word2vec subsampling: P(discard) = 1 - sqrt(t/f)
            discard_prob[i] = max(0.0, 1.0 - (SUBSAMPLE_T / f) ** 0.5)

    # Log most-subsampled words
    top_sub = sorted(discard_prob.items(), key=lambda x: -x[1])[:10]
    for idx, prob in top_sub:
        sys.stderr.write("[BRIDGE] subsample: %-20s freq=%d P(discard)=%.2f\n" % (vocab_words[idx], vocab_freqs[idx], prob))

    CHUNK = 1000000  # 1M pairs per chunk = 8MB buffer
    with open(path, "wb") as f:
        f.write(b"W2VT")
        f.write(struct.pack("<i", dims))
        f.write(struct.pack("<i", len(vocab_words)))
        f.write(struct.pack("<i", neg))
        f.write(struct.pack("<i", window))
        f.write(struct.pack("<i", epochs))
        f.write(struct.pack("<d", lr_start))
        f.write(struct.pack("<d", lr_end))
        for word in vocab_words:
            encoded = word.encode("utf-8")
            f.write(struct.pack("<i", len(encoded)))
            f.write(encoded)
        for freq in vocab_freqs:
            f.write(struct.pack("<i", freq))
        # Reserve 8 bytes for pair count — fill in after
        pair_count_offset = f.tell()
        f.write(struct.pack("<q", 0))

        total_pairs = 0
        buf = np.zeros((CHUNK, 2), dtype=np.int32)
        buf_idx = 0
        t0 = time.time()

        for fi, tokens in enumerate(files):
            # Apply subsampling: filter out frequent words probabilistically
            indices = []
            for t in tokens:
                if t in word_to_idx:
                    idx = word_to_idx[t]
                    if rng.random() >= discard_prob[idx]:
                        indices.append(idx)
            n = len(indices)
            for i in range(n):
                center = indices[i]
                lo = max(0, i - window)
                hi = min(n - 1, i + window)
                for j in range(lo, hi + 1):
                    if j == i:
                        continue
                    buf[buf_idx, 0] = center
                    buf[buf_idx, 1] = indices[j]
                    buf_idx += 1
                    if buf_idx >= CHUNK:
                        f.write(buf[:buf_idx].tobytes())
                        total_pairs += buf_idx
                        buf_idx = 0
                        if total_pairs % 10000000 < CHUNK:
                            el = time.time() - t0
                            sys.stderr.write("[BRIDGE] %dM pairs, %.1fs\n" % (total_pairs // 1000000, el))
            if fi % 500 == 0 and fi > 0:
                el = time.time() - t0
                sys.stderr.write("[BRIDGE] file %d/%d, %dM pairs, %.1fs\n" % (fi, len(files), total_pairs // 1000000, el))

        # Flush remaining
        if buf_idx > 0:
            f.write(buf[:buf_idx].tobytes())
            total_pairs += buf_idx

        # Go back and write actual pair count
        f.seek(pair_count_offset)
        f.write(struct.pack("<q", total_pairs))

    size_mb = os.path.getsize(path) / (1024 * 1024)
    sys.stderr.write("[BRIDGE] Wrote %s (%.1f MB, %d pairs)\n" % (path, size_mb, total_pairs))
    return total_pairs


def write_init_model(path, dims, vocab_words, vocab_freqs, minilm_vectors):
    """Write init_model.bin in W2VC format. W_in = MiniLM vectors, W_out = small random."""
    vocab_size = len(vocab_words)
    w_in = np.zeros((vocab_size, dims), dtype=np.float32)
    w_out = np.zeros((vocab_size, dims), dtype=np.float32)
    rng = np.random.RandomState(42)
    for i, word in enumerate(vocab_words):
        if word in minilm_vectors:
            w_in[i] = minilm_vectors[word]
        w_out[i] = (rng.randn(dims).astype(np.float32)) * 0.01

    with open(path, "wb") as f:
        f.write(b"W2VC")
        f.write(struct.pack("<i", dims))
        f.write(struct.pack("<i", vocab_size))
        f.write(struct.pack("<i", 0))   # epochs (placeholder)
        f.write(struct.pack("<i", WINDOW))
        f.write(struct.pack("<i", 5))   # neg_samples
        f.write(struct.pack("<d", 0.025))
        f.write(struct.pack("<d", 0.0001))
        for word in vocab_words:
            encoded = word.encode("utf-8")
            f.write(struct.pack("<i", len(encoded)))
            f.write(encoded)
        for freq in vocab_freqs:
            f.write(struct.pack("<i", freq))
        f.write(w_in.tobytes())
        f.write(w_out.tobytes())
    size_mb = os.path.getsize(path) / (1024 * 1024)
    sys.stderr.write("[BRIDGE] Wrote %s (%.1f MB, W_in=MiniLM)\n" % (path, size_mb))


def main():
    db_path = DB_PATH
    out_dir = PROJECT_DIR
    epochs = 5
    lr_start = 0.025
    lr_end = 0.0001
    neg = 5

    for i in range(1, len(sys.argv)):
        if sys.argv[i] == "--db" and i + 1 < len(sys.argv):
            db_path = sys.argv[i + 1]
        elif sys.argv[i] == "--outdir" and i + 1 < len(sys.argv):
            out_dir = sys.argv[i + 1]
        elif sys.argv[i] == "--epochs" and i + 1 < len(sys.argv):
            epochs = int(sys.argv[i + 1])
        elif sys.argv[i] == "--lr" and i + 1 < len(sys.argv):
            lr_start = float(sys.argv[i + 1])

    t0 = time.time()

    minilm_vectors = load_minilm_vectors(db_path)
    files = scan_corpus(PROJECT_DIR)
    vocab_words, vocab_freqs, word_to_idx = build_vocab(files, set(minilm_vectors.keys()))

    train_path = os.path.join(out_dir, "training.bin")
    init_path = os.path.join(out_dir, "init_model.bin")

    total_pairs = write_training_bin_streaming(train_path, EMBED_DIM, vocab_words, vocab_freqs,
                                                files, word_to_idx, WINDOW, neg, epochs, lr_start, lr_end)
    write_init_model(init_path, EMBED_DIM, vocab_words, vocab_freqs, minilm_vectors)

    elapsed = time.time() - t0
    sys.stderr.write("\n[BRIDGE] Done in %.1fs\n" % elapsed)
    sys.stderr.write("\nNow run:\n")
    sys.stderr.write("  cd %s\n" % out_dir)
    sys.stderr.write("  clang -fobjc-arc -framework Metal -framework Foundation c_word2vec_metal_packed.mm -o vbengine -lsqlite3 -lmysqlclient\n")
    sys.stderr.write("  ./vbengine --train --pairs training.bin --model model.bin --init-model init_model.bin --dims 384 --epochs %d\n" % epochs)
    sys.stderr.write("  python3 vb_export.py --model model.bin --db %s\n" % db_path)


if __name__ == "__main__":
    main()
