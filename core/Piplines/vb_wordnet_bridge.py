#!/usr/bin/env python3
#[@GHOST]{file_path="core/Piplines/vb_wordnet_bridge.py" date="2026-07-04" author="Devin" session_id="wordnet-train" context="WordNet bridge — extract definitions + synonyms as training corpus for VBEngine. Full English dictionary."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE spaces only"}
#[@FILEID]{id="vb_wordnet_bridge.py" domain="Piplines" authority="VBWordnetBridge"}
#[@SUMMARY]{summary="Parse WordNet 3.1 data files (noun/verb/adj/adv), extract definitions as sentences + synonym sets, generate skip-gram pairs, write training.bin for VBEngine."}

"""
VBEngine WordNet Bridge — Full English Dictionary Training

Parses WordNet 3.1 data files:
  - data.noun, data.verb, data.adj, data.adv
  - Each line: synset_id pos_type n_words word1 lex_id1 word2 lex_id2 ... ptrs... | definition | examples

Extracts:
  1. Definition text → sentences (skip-gram pairs from definition words)
  2. Example sentences (after definition, in quotes)
  3. Synonym pairs (words within same synset are synonyms → direct pairs)
  4. Hypernym/hyponym pairs (related concepts → direct pairs)

Output: training.bin (W2VT format) ready for VBEngine GPU training.

Usage:
  python3 vb_wordnet_bridge.py --wn-dir wordnet_data/dict --db /Users/wws/Qdrant_mysql_mlx_vector_engine/semantic_corpus.db --outdir .
"""

import os
import re
import sys
import struct
import time
import sqlite3
import numpy as np
from collections import Counter

PROJECT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine"
DB_PATH = os.path.join(PROJECT_DIR, "semantic_corpus.db")
WN_DIR = os.path.join(os.path.dirname(__file__), "wordnet_data", "dict")
EMBED_DIM = 384
WINDOW = 5
MIN_COUNT = 2
MAX_VOCAB = 200000
NEG = 5
EPOCHS = 50
LR_START = 0.025
LR_END = 0.0001

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
POS_FILES = ["data.noun", "data.verb", "data.adj", "data.adv"]


def load_minilm_vectors(db_path):
    """Load MiniLM/VBEngine vectors from semantic_corpus.db for init weights."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT term, vector FROM embeddings ORDER BY term")
    term_to_vec = {}
    for term, vec_blob in cur.fetchall():
        vec = np.frombuffer(vec_blob, dtype=np.float32)
        if vec.shape[0] == EMBED_DIM:
            t = term.lower()
            if t not in term_to_vec:
                term_to_vec[t] = vec
    conn.close()
    sys.stderr.write("[WN] Loaded %d init vectors from %s\n" % (len(term_to_vec), db_path))
    return term_to_vec


def parse_wordnet_line(line):
    """Parse one WordNet data line. Returns (words_list, definition, examples_list, pointers_list).

    Format: synset_id pos_type n_words w1 lex1 w2 lex2 ... n_ptrs ptr_type target offset pos ... | definition | example1 | example2
    """
    if line.startswith(" ") or not line[0].isdigit():
        return None

    pipe_idx = line.find(" | ")
    if pipe_idx < 0:
        return None

    before = line[:pipe_idx]
    after = line[pipe_idx + 3:].strip()

    parts = before.split(" ")
    if len(parts) < 5:
        return None

    # synset_id=parts[0], lex_filenum=parts[1], pos=parts[2], n_words=parts[3]
    try:
        n_words = int(parts[3])
    except ValueError:
        return None

    word_start = 4
    word_end = word_start + n_words * 2
    if word_end > len(parts):
        return None

    words = []
    for i in range(word_start, word_end, 2):
        w = parts[i].lower().replace("_", " ")
        words.append(w)

    # Parse pointers (after words, before |)
    ptr_parts = parts[word_end:]
    pointers = []
    try:
        n_ptrs = int(ptr_parts[0]) if ptr_parts else 0
    except (ValueError, IndexError):
        n_ptrs = 0

    if n_ptrs > 0 and len(ptr_parts) >= 1 + n_ptrs * 4:
        ptr_data = ptr_parts[1:]
        for i in range(0, n_ptrs * 4, 4):
            if i + 3 < len(ptr_data):
                ptr_type = ptr_data[i]
                target_offset = ptr_data[i + 1]
                target_pos = ptr_data[i + 2]
                pointers.append((ptr_type, target_offset, target_pos))

    # Parse definition and examples
    # Examples are in double quotes within the definition field
    examples = []
    definition = after

    # Extract examples (quoted strings)
    quote_re = re.compile(r'"([^"]+)"')
    for m in quote_re.finditer(after):
        examples.append(m.group(1))
    definition = quote_re.sub("", after).strip().rstrip(";").strip()

    return words, definition, examples, pointers


def extract_wordnet_corpus(wn_dir):
    """Parse all WordNet data files. Returns list of (tokens_list, synonym_pairs_list)."""
    all_sentences = []
    all_synonym_pairs = []
    synset_words = {}  # synset_id -> list of words
    synset_ptrs = {}   # synset_id -> list of (ptr_type, target_offset)

    for fname in POS_FILES:
        fpath = os.path.join(wn_dir, fname)
        if not os.path.exists(fpath):
            sys.stderr.write("[WN] Missing %s\n" % fpath)
            continue

        n_lines = 0
        n_synsets = 0
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                n_lines += 1
                result = parse_wordnet_line(line)
                if result is None:
                    continue

                words, definition, examples, pointers = result
                if not words:
                    continue

                n_synsets += 1

                # Store synset for pointer resolution
                synset_id = line.split(" ")[0]
                synset_words[synset_id] = words
                synset_ptrs[synset_id] = pointers

                # Synonym pairs: all words in same synset are synonyms
                for i in range(len(words)):
                    for j in range(len(words)):
                        if i != j:
                            all_synonym_pairs.append((words[i], words[j]))

                # Definition as a sentence
                if definition:
                    tokens = [t.lower() for t in TOKEN_RE.findall(definition) if len(t) >= 2]
                    if len(tokens) >= 3:
                        all_sentences.append(tokens)

                # Examples as sentences
                for ex in examples:
                    tokens = [t.lower() for t in TOKEN_RE.findall(ex) if len(t) >= 2]
                    if len(tokens) >= 3:
                        all_sentences.append(tokens)

        sys.stderr.write("[WN] %s: %d lines, %d synsets\n" % (fname, n_lines, n_synsets))

    # Resolve hypernym/hyponym pointers → related word pairs
    n_ptr_pairs = 0
    for synset_id, ptrs in synset_ptrs.items():
        if synset_id not in synset_words:
            continue
        source_words = synset_words[synset_id]
        for ptr_type, target_offset, target_pos in ptrs:
            if ptr_type in ("@", "~", "%p", "%s", "+", "#m", "#p"):
                if target_offset in synset_words:
                    target_words = synset_words[target_offset]
                    for sw in source_words:
                        for tw in target_words:
                            if sw != tw:
                                all_synonym_pairs.append((sw, tw))
                                n_ptr_pairs += 1

    sys.stderr.write("[WN] Total: %d sentences, %d synonym pairs, %d pointer pairs\n" %
                     (len(all_sentences), len(all_synonym_pairs), n_ptr_pairs))
    return all_sentences, all_synonym_pairs


def build_vocab(sentences, synonym_pairs, init_vectors, min_count=MIN_COUNT):
    """Build vocab from sentences + synonym pairs, intersected with init vectors where possible."""
    freq = Counter()
    for tokens in sentences:
        freq.update(tokens)
    for w1, w2 in synonym_pairs:
        freq[w1] += 1
        freq[w2] += 1

    # Build vocab: include all words that meet min_count
    vocab = []
    for word, count in freq.most_common():
        if count < min_count:
            continue
        vocab.append((word, count))

    # Also add all init vector terms even if freq < min_count (they have pre-trained vectors)
    init_terms = set(init_vectors.keys())
    existing = set(w for w, _ in vocab)
    for term in init_terms:
        if term not in existing:
            vocab.append((term, 1))

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

    init_hits = sum(1 for w in word_list if w in init_terms)
    sys.stderr.write("[WN] Vocab: %d words (init vectors: %d, new: %d)\n" %
                     (len(word_list), init_hits, len(word_list) - init_hits))
    return word_list, freq_list, word_to_idx


def write_training_bin_streaming(path, dims, vocab_words, vocab_freqs,
                                  sentences, synonym_pairs, word_to_idx,
                                  window, neg, epochs, lr_start, lr_end):
    """Write training.bin in W2VT format. Streams pairs to disk."""
    CHUNK = 1000000
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
        pair_count_offset = f.tell()
        f.write(struct.pack("<q", 0))

        total_pairs = 0
        buf = np.zeros((CHUNK, 2), dtype=np.int32)
        buf_idx = 0
        t0 = time.time()

        def flush_buf():
            nonlocal buf_idx, total_pairs
            if buf_idx > 0:
                f.write(buf[:buf_idx].tobytes())
                total_pairs += buf_idx
                buf_idx = 0

        def add_pair(c, ctx):
            nonlocal buf_idx
            if c < 0 or ctx < 0 or c == ctx:
                return
            buf[buf_idx, 0] = c
            buf[buf_idx, 1] = ctx
            buf_idx += 1
            if buf_idx >= CHUNK:
                flush_buf()

        # 1. Skip-gram pairs from definition/example sentences
        for tokens in sentences:
            indices = [word_to_idx[t] for t in tokens if t in word_to_idx]
            n = len(indices)
            for i in range(n):
                center = indices[i]
                lo = max(0, i - window)
                hi = min(n - 1, i + window)
                for j in range(lo, hi + 1):
                    if j != i:
                        add_pair(center, indices[j])

        # 2. Synonym + pointer pairs (direct, no window)
        for w1, w2 in synonym_pairs:
            if w1 in word_to_idx and w2 in word_to_idx:
                add_pair(word_to_idx[w1], word_to_idx[w2])

        flush_buf()
        f.seek(pair_count_offset)
        f.write(struct.pack("<q", total_pairs))

    size_mb = os.path.getsize(path) / (1024 * 1024)
    elapsed = time.time() - t0
    sys.stderr.write("[WN] Wrote %s (%.1f MB, %d pairs, %.1fs)\n" % (path, size_mb, total_pairs, elapsed))
    return total_pairs


def write_init_model(path, dims, vocab_words, vocab_freqs, init_vectors):
    """Write init_model.bin in W2VC format. W_in = existing vectors, W_out = small random."""
    vocab_size = len(vocab_words)
    w_in = np.zeros((vocab_size, dims), dtype=np.float32)
    w_out = np.zeros((vocab_size, dims), dtype=np.float32)
    rng = np.random.RandomState(42)
    for i, word in enumerate(vocab_words):
        if word in init_vectors:
            w_in[i] = init_vectors[word]
        w_out[i] = (rng.randn(dims).astype(np.float32)) * 0.01

    with open(path, "wb") as f:
        f.write(b"W2VC")
        f.write(struct.pack("<i", dims))
        f.write(struct.pack("<i", vocab_size))
        f.write(struct.pack("<i", 0))
        f.write(struct.pack("<i", WINDOW))
        f.write(struct.pack("<i", 5))
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
    sys.stderr.write("[WN] Wrote %s (%.1f MB, W_in=existing)\n" % (path, size_mb))


def main():
    wn_dir = WN_DIR
    db_path = DB_PATH
    out_dir = os.path.dirname(__file__)
    epochs = EPOCHS

    for i in range(1, len(sys.argv)):
        if sys.argv[i] == "--wn-dir" and i + 1 < len(sys.argv):
            wn_dir = sys.argv[i + 1]
        elif sys.argv[i] == "--db" and i + 1 < len(sys.argv):
            db_path = sys.argv[i + 1]
        elif sys.argv[i] == "--outdir" and i + 1 < len(sys.argv):
            out_dir = sys.argv[i + 1]
        elif sys.argv[i] == "--epochs" and i + 1 < len(sys.argv):
            epochs = int(sys.argv[i + 1])

    t0 = time.time()

    sys.stderr.write("[WN] === WordNet Bridge ===\n")
    sys.stderr.write("[WN] WordNet dir: %s\n" % wn_dir)

    init_vectors = load_minilm_vectors(db_path)
    sentences, synonym_pairs = extract_wordnet_corpus(wn_dir)
    vocab_words, vocab_freqs, word_to_idx = build_vocab(sentences, synonym_pairs, init_vectors)

    train_path = os.path.join(out_dir, "training_wordnet.bin")
    init_path = os.path.join(out_dir, "init_model_wordnet.bin")

    total_pairs = write_training_bin_streaming(
        train_path, EMBED_DIM, vocab_words, vocab_freqs,
        sentences, synonym_pairs, word_to_idx,
        WINDOW, NEG, epochs, LR_START, LR_END
    )
    write_init_model(init_path, EMBED_DIM, vocab_words, vocab_freqs, init_vectors)

    elapsed = time.time() - t0
    sys.stderr.write("\n[WN] Done in %.1fs\n" % elapsed)
    sys.stderr.write("\nNow run:\n")
    sys.stderr.write("  cd %s\n" % out_dir)
    sys.stderr.write("  ./vbengine --train --pairs training_wordnet.bin --model model_wordnet.bin --init-model init_model_wordnet.bin --dims 384 --epochs %d\n" % epochs)
    sys.stderr.write("  python3 vb_export.py --model model_wordnet.bin --db %s\n" % db_path)


if __name__ == "__main__":
    main()
