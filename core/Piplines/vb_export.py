#!/usr/bin/env python3
#[@GHOST]{file_path="core/Piplines/vb_export.py" date="2026-07-04" author="Cascade" session_id="monkey-see-monkey-do" context="Export trained VBEngine model.bin back to semantic_corpus.db. Replace MiniLM vectors with trained vectors."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE spaces only"}
#[@FILEID]{id="vb_export.py" domain="Piplines" authority="VBExport"}
#[@SUMMARY]{summary="Read trained VBEngine model.bin (W2VC format), update semantic_corpus.db with new trained vectors. The monkey's own weights replace the teacher's."}

"""
VBEngine Export — Monkey Did

Reads trained model.bin (W2VC format) and updates semantic_corpus.db
with the new trained vectors. This replaces MiniLM's vectors with
VBEngine's own learned weights.

Usage:
  python3 vb_export.py --model model.bin --db semantic_corpus.db
"""

import sqlite3
import numpy as np
import struct
import os
import sys
import time

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/semantic_corpus.db"


def read_model(path):
    """Read W2VC model.bin file. Returns (vocab_words, W_in, W_out, dims)."""
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"W2VC":
            raise ValueError("Bad magic: %s (expected W2VC)" % magic)
        dims = struct.unpack("<i", f.read(4))[0]
        vocab_size = struct.unpack("<i", f.read(4))[0]
        epochs = struct.unpack("<i", f.read(4))[0]
        window = struct.unpack("<i", f.read(4))[0]
        neg = struct.unpack("<i", f.read(4))[0]
        lr_start = struct.unpack("<d", f.read(8))[0]
        lr_end = struct.unpack("<d", f.read(8))[0]

        vocab_words = []
        for _ in range(vocab_size):
            wlen = struct.unpack("<i", f.read(4))[0]
            word = f.read(wlen).decode("utf-8")
            vocab_words.append(word)

        vocab_freqs = np.frombuffer(f.read(vocab_size * 4), dtype=np.int32)

        w_size = vocab_size * dims
        W_in = np.frombuffer(f.read(w_size * 4), dtype=np.float32).reshape(vocab_size, dims).copy()
        W_out = np.frombuffer(f.read(w_size * 4), dtype=np.float32).reshape(vocab_size, dims).copy()

    sys.stderr.write("[EXPORT] Loaded model: %s\n" % path)
    sys.stderr.write("[EXPORT] dims=%d vocab=%d epochs=%d\n" % (dims, vocab_size, epochs))
    return vocab_words, W_in, W_out, dims


def update_db(db_path, vocab_words, W_in, dims):
    """Update semantic_corpus.db with trained vectors."""
    conn = sqlite3.connect(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS embeddings_trained (
            term TEXT PRIMARY KEY,
            vector BLOB NOT NULL,
            source TEXT DEFAULT 'vbengine',
            created_at REAL DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_term_trained ON embeddings_trained(term)")

    existing = set(row[0] for row in conn.execute("SELECT term FROM embeddings").fetchall())

    now = time.time()
    updated = 0
    inserted = 0

    for i, word in enumerate(vocab_words):
        vec = W_in[i]
        vec_blob = vec.tobytes()

        if word in existing:
            conn.execute(
                "UPDATE embeddings SET vector=?, source='vbengine', created_at=? WHERE term=?",
                (vec_blob, now, word)
            )
            updated += 1
        else:
            conn.execute(
                "INSERT OR IGNORE INTO embeddings (term, vector, source, created_at) VALUES (?, ?, 'vbengine', ?)",
                (word, vec_blob, now)
            )
            inserted += 1

    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    conn.close()

    sys.stderr.write("[EXPORT] Updated %d existing, inserted %d new vectors\n" % (updated, inserted))
    sys.stderr.write("[EXPORT] Total in DB: %d terms\n" % total)
    sys.stderr.write("[EXPORT] Source label: 'vbengine' (trained, not MiniLM)\n")


def main():
    model_path = "model.bin"
    db_path = DB_PATH

    for i in range(1, len(sys.argv)):
        if sys.argv[i] == "--model" and i + 1 < len(sys.argv):
            model_path = sys.argv[i + 1]
        elif sys.argv[i] == "--db" and i + 1 < len(sys.argv):
            db_path = sys.argv[i + 1]

    if not os.path.exists(model_path):
        sys.stderr.write("ERROR: model file not found: %s\n" % model_path)
        sys.exit(1)

    t0 = time.time()
    vocab_words, W_in, W_out, dims = read_model(model_path)
    update_db(db_path, vocab_words, W_in, dims)
    elapsed = time.time() - t0
    sys.stderr.write("\n[EXPORT] Done in %.1fs\n" % elapsed)
    sys.stderr.write("\nNow test with word_similarity.py — vectors are updated.\n")


if __name__ == "__main__":
    main()
