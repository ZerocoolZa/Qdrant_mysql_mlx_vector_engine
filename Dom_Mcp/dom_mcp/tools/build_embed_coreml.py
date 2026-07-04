#!/usr/bin/env python3
#[@GHOST]{[@file<build_embed_coreml.py>][@state<active>][@ver<v1.0>][@auth<Devin>][@date<2026-07-04>]}
#[@VBSTYLE]{[@auth<Devin>][@role<coreml_builder>][@return<mlmodel>][@no<print|hardcoded>]}
#[@FILEID]{build_embed_coreml}
#[@SUMMARY]{Builds a tiny 64-dim semantic embedding CoreML model for chat message similarity search. Pulls messages from MySQL cascade_chats.messages, builds a 256-word vocab, trains a TF-IDF+SVD-initialized two-layer autoencoder (256->128->64 + L2 normalize), converts to .mlpackage.}
#[@CLASS]{EmbedCoremlBuilder}
#[@METHOD]{fetch_messages, build_vocab, text_to_bow, fit_svd, build_encoder, finetune_autoencoder, convert_coreml, save, test_similarity}

"""
Build a tiny 64-dim semantic embedding model -> CoreML .mlpackage.

Architecture:
  Input:  bag-of-words vector (256 vocab words -> 256-dim float)
  Layer1: Linear(256 -> 128) + ReLU
  Layer2: Linear(128 -> 64) + L2 normalize
  Output: 64-dim normalized embedding vector

Training approach:
  1. Pull messages from MySQL cascade_chats.messages (content column).
  2. Build a 256-word vocab (top frequency words, stop words removed).
  3. Fit TF-IDF + TruncatedSVD (LSA) to learn a latent-topic projection
     that captures semantic co-occurrence (e.g. kokoro/tts/speech cluster).
  4. Initialize the two-layer encoder from the SVD projection (split into
     256->128 and 128->64 stages).
  5. Fine-tune as an autoencoder (content -> 64-dim -> reconstruct content)
     to sharpen the embedding space.
  6. Convert the encoder to CoreML .mlpackage.

The SVD/LSA stage is what gives "kokoro voice pipeline" and "tts speech
synthesis" high cosine similarity: even though they share no surface words,
the training messages co-occur kokoro/tts/speech/voice, so LSA places them
in the same latent topic dimension.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import coremltools as ct
import numpy as np
import json
import os
import re
import time
from collections import Counter
from pathlib import Path
import mysql.connector
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

OUTPUT_DIR = Path(__file__).parent / "embed_model"
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL_PATH = OUTPUT_DIR / "SemanticEmbed.mlpackage"
VOCAB_PATH = OUTPUT_DIR / "embed_vocab.json"

VOCAB_SIZE = 256
EMBED_DIM = 64
HIDDEN_DIM = 128
MAX_MESSAGES = 5000
MIN_CONTENT_LEN = 50

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "for", "to",
    "of", "in", "on", "at", "by", "with", "from", "as", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "must", "can", "shall",
    "this", "that", "these", "those", "it", "its", "they", "them", "their",
    "there", "here", "where", "when", "why", "how", "what", "which", "who",
    "whom", "whose", "i", "you", "he", "she", "we", "us", "me", "my", "your",
    "his", "her", "our", "us", "him", "so", "not", "no", "yes", "than", "too",
    "very", "just", "also", "only", "up", "down", "out", "over", "under",
    "again", "more", "most", "some", "any", "all", "each", "every", "both",
    "few", "many", "much", "such", "same", "other", "into", "onto", "off",
    "about", "above", "below", "between", "through", "during", "after",
    "before", "since", "until", "while", "because", "though", "although",
    "code", "file", "files", "use", "using", "used", "like", "need", "want",
    "get", "got", "make", "made", "go", "going", "one", "two", "new", "now",
    "let", "via", "per", "etc", "ie", "eg", "ok", "okay", "yeah", "uh",
    "im", "ive", "id", "youre", "youve", "dont", "doesnt", "didnt", "wont",
    "cant", "isnt", "arent", "wasnt", "werent", "hasnt", "havent", "hadnt",
    "would", "could", "should", "might", "must", "shall", "ll", "ve", "re",
    "s", "t", "d", "m", "ll",
}


def fetch_messages():
    """Pull training messages from MySQL cascade_chats.messages."""
    conn = mysql.connector.connect(
        host="localhost", user="root", password="", database="cascade_chats"
    )
    cur = conn.cursor()
    query = (
        "SELECT content FROM messages "
        "WHERE content IS NOT NULL AND LENGTH(content) > %s "
        "ORDER BY id LIMIT %s"
    )
    cur.execute(query, (MIN_CONTENT_LEN, MAX_MESSAGES))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    messages = [r[0] for r in rows if r[0]]
    return messages


def tokenize(text):
    """Lowercase, strip punctuation, split on non-alphanumeric."""
    text = text.lower()
    tokens = re.findall(r"[a-z][a-z0-9_]*", text)
    return tokens


def build_vocab(messages, max_vocab=VOCAB_SIZE):
    """Build vocab from top-frequency words, excluding stop words."""
    counts = Counter()
    for msg in messages:
        for tok in tokenize(msg):
            if len(tok) < 2:
                continue
            if tok in STOP_WORDS:
                continue
            counts[tok] += 1
    # Sort by frequency desc, then alpha for determinism
    sorted_words = sorted(counts.keys(), key=lambda w: (-counts[w], w))
    vocab = sorted_words[:max_vocab]
    word_to_idx = {w: i for i, w in enumerate(vocab)}
    return vocab, word_to_idx


def text_to_bow(text, word_to_idx, vocab_size=VOCAB_SIZE):
    """Convert text to a bag-of-words vector (binary presence)."""
    vec = np.zeros(vocab_size, dtype=np.float32)
    for tok in tokenize(text):
        idx = word_to_idx.get(tok)
        if idx is not None:
            vec[idx] = 1.0
    return vec


def messages_to_bow_matrix(messages, word_to_idx, vocab_size=VOCAB_SIZE):
    """Build a (N, vocab_size) bag-of-words matrix."""
    mat = np.zeros((len(messages), vocab_size), dtype=np.float32)
    for i, msg in enumerate(messages):
        mat[i] = text_to_bow(msg, word_to_idx, vocab_size)
    return mat


def fit_svd_projection(bow_matrix, hidden_dim=HIDDEN_DIM, embed_dim=EMBED_DIM):
    """
    Fit TF-IDF + two-stage TruncatedSVD (LSA) to get a semantic projection.
    Returns (W1, W2) where:
      W1: (hidden_dim, vocab_size)  -> stage 1 (256 -> 128)
      W2: (embed_dim, hidden_dim)   -> stage 2 (128 -> 64)
    The composition W2 @ W1 maps 256-dim BoW -> 64-dim semantic embedding.
    """
    # TF-IDF weighting on the BoW matrix (fit_transform expects text-like,
    # but we already have a term-doc matrix; apply idf manually for stability).
    # Use TfidfVectorizer on raw text for proper idf, restricted to our vocab.
    # Simpler: apply sklearn TfidfVectorizer with fixed vocabulary.
    # We rebuild from messages is not available here, so apply idf to BoW.
    df = (bow_matrix > 0).sum(axis=0)
    n_docs = bow_matrix.shape[0]
    idf = np.log((1.0 + n_docs) / (1.0 + df)) + 1.0
    idf = np.where(df > 0, idf, 0.0)
    tfidf = bow_matrix * idf[np.newaxis, :]
    # L2 normalize rows
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    tfidf = tfidf / norms

    # Stage 1: SVD to hidden_dim (128)
    svd1 = TruncatedSVD(n_components=hidden_dim, random_state=42)
    hidden = svd1.fit_transform(tfidf)  # (N, 128)
    W1 = svd1.components_.astype(np.float32)  # (128, 256)

    # Stage 2: SVD to embed_dim (64) on the hidden representation
    svd2 = TruncatedSVD(n_components=embed_dim, random_state=42)
    svd2.fit(hidden)
    W2 = svd2.components_.astype(np.float32)  # (64, 128)

    return W1, W2


class EmbedEncoder(nn.Module):
    """Encoder: 256 -> 128 (ReLU) -> 64 (L2 normalize)."""
    def __init__(self, vocab_size=VOCAB_SIZE, hidden_dim=HIDDEN_DIM, embed_dim=EMBED_DIM):
        super().__init__()
        self.fc1 = nn.Linear(vocab_size, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, embed_dim)

    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.fc2(x)
        x = F.normalize(x, p=2, dim=-1)
        return x


class Autoencoder(nn.Module):
    """Encoder + decoder for fine-tuning (reconstruct BoW input)."""
    def __init__(self, vocab_size=VOCAB_SIZE, hidden_dim=HIDDEN_DIM, embed_dim=EMBED_DIM):
        super().__init__()
        self.encoder = EmbedEncoder(vocab_size, hidden_dim, embed_dim)
        self.decoder = nn.Linear(embed_dim, vocab_size)

    def forward(self, x):
        z = self.encoder(x)
        recon = self.decoder(z)
        return recon, z


def init_encoder_from_svd(encoder, W1, W2):
    """Initialize encoder layers from SVD projection matrices."""
    # fc1 weight shape: (hidden_dim, vocab_size) == W1 shape
    with torch.no_grad():
        encoder.fc1.weight.copy_(torch.from_numpy(W1))
        encoder.fc1.bias.zero_()
        # fc2 weight shape: (embed_dim, hidden_dim) == W2 shape
        encoder.fc2.weight.copy_(torch.from_numpy(W2))
        encoder.fc2.bias.zero_()


def finetune_autoencoder(bow_matrix, encoder, epochs=60, lr=0.01, batch_size=128):
    """Fine-tune the encoder via autoencoder reconstruction loss."""
    ae = Autoencoder(VOCAB_SIZE, HIDDEN_DIM, EMBED_DIM)
    # Copy SVD-initialized encoder weights into the autoencoder
    ae.encoder.load_state_dict(encoder.state_dict())
    # Initialize decoder as pseudo-inverse-ish of encoder (for stable recon)
    with torch.no_grad():
        W2 = ae.encoder.fc2.weight.detach().clone()
        W1 = ae.encoder.fc1.weight.detach().clone()
        # decoder: (vocab, embed). Approximate inverse via pinv of (W2 @ W1)
        proj = (W2 @ W1).numpy()  # (64, 256)
        pinv = np.linalg.pinv(proj).astype(np.float32)  # (256, 64)
        ae.decoder.weight.copy_(torch.from_numpy(pinv))
        ae.decoder.bias.zero_()

    X = torch.from_numpy(bow_matrix)
    optimizer = torch.optim.Adam(ae.parameters(), lr=lr, weight_decay=1e-4)
    criterion = nn.MSELoss()

    n = X.shape[0]
    for epoch in range(epochs):
        perm = torch.randperm(n)
        epoch_loss = 0.0
        for i in range(0, n, batch_size):
            idx = perm[i:i + batch_size]
            xb = X[idx]
            optimizer.zero_grad()
            recon, _ = ae(xb)
            loss = criterion(recon, xb)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * xb.shape[0]
        epoch_loss /= n
        if (epoch + 1) % 20 == 0:
            print(f"  AE epoch {epoch+1}: recon_loss={epoch_loss:.6f}")

    # Copy fine-tuned encoder back
    encoder.load_state_dict(ae.encoder.state_dict())
    return encoder


def convert_to_coreml(encoder):
    """Convert the encoder to a CoreML .mlpackage."""
    encoder.eval()
    example = torch.randn(1, VOCAB_SIZE)
    traced = torch.jit.trace(encoder, example)
    mlmodel = ct.convert(
        traced,
        inputs=[ct.TensorType(name="text_bow", shape=(1, VOCAB_SIZE))],
        outputs=[ct.TensorType(name="embedding")],
    )
    mlmodel.short_description = (
        "64-dim semantic embedding for chat message similarity search"
    )
    mlmodel.author = "Devin"
    mlmodel.version = "1.0"
    mlmodel.user_defined_metadata["embed_dim"] = str(EMBED_DIM)
    mlmodel.user_defined_metadata["vocab_size"] = str(VOCAB_SIZE)
    return mlmodel


def cosine_sim(a, b):
    """Cosine similarity between two vectors."""
    a = np.asarray(a, dtype=np.float32).flatten()
    b = np.asarray(b, dtype=np.float32).flatten()
    na = np.linalg.norm(a) + 1e-12
    nb = np.linalg.norm(b) + 1e-12
    return float(np.dot(a, b) / (na * nb))


def embed_text_torch(text, encoder, word_to_idx):
    """Embed a text using the PyTorch encoder."""
    vec = text_to_bow(text, word_to_idx)
    x = torch.from_numpy(vec).unsqueeze(0)
    with torch.no_grad():
        emb = encoder(x).squeeze(0).numpy()
    return emb


def embed_text_coreml(text, mlmodel, word_to_idx):
    """Embed a text using the CoreML model."""
    vec = text_to_bow(text, word_to_idx)
    out = mlmodel.predict({"text_bow": vec.reshape(1, -1)})
    key = list(out.keys())[0]
    return np.asarray(out[key], dtype=np.float32).flatten()


def main():
    print("=== Building Semantic Embedding CoreML Model ===\n")

    # 1. Fetch training data from MySQL
    print("Fetching messages from MySQL cascade_chats.messages...")
    messages = fetch_messages()
    print(f"  Pulled {len(messages)} messages (len > {MIN_CONTENT_LEN})\n")

    # 2. Build vocab
    print("Building vocabulary...")
    vocab, word_to_idx = build_vocab(messages, max_vocab=VOCAB_SIZE)
    print(f"  Vocab: {len(vocab)} words")
    print(f"  Sample: {vocab[:20]}\n")

    # 3. Build BoW matrix
    print("Building bag-of-words matrix...")
    bow = messages_to_bow_matrix(messages, word_to_idx, VOCAB_SIZE)
    print(f"  Matrix: {bow.shape}\n")

    # 4. Fit TF-IDF + SVD (LSA) projection
    print("Fitting TF-IDF + SVD (LSA) projection...")
    W1, W2 = fit_svd_projection(bow, HIDDEN_DIM, EMBED_DIM)
    print(f"  W1: {W1.shape}  W2: {W2.shape}\n")

    # 5. Build encoder and initialize from SVD
    print("Initializing encoder from SVD projection...")
    encoder = EmbedEncoder(VOCAB_SIZE, HIDDEN_DIM, EMBED_DIM)
    init_encoder_from_svd(encoder, W1, W2)

    # Quick semantic check with SVD-only encoder
    e1 = embed_text_torch("kokoro voice pipeline", encoder, word_to_idx)
    e2 = embed_text_torch("tts speech synthesis", encoder, word_to_idx)
    e3 = embed_text_torch("mysql database", encoder, word_to_idx)
    e4 = embed_text_torch("kokoro voice", encoder, word_to_idx)
    print(f"  [SVD-only] sim('kokoro voice pipeline','tts speech synthesis') = {cosine_sim(e1, e2):.4f}")
    print(f"  [SVD-only] sim('mysql database','kokoro voice') = {cosine_sim(e3, e4):.4f}\n")

    # 6. Fine-tune as autoencoder
    print("Fine-tuning as autoencoder...")
    encoder = finetune_autoencoder(bow, encoder, epochs=60, lr=0.01, batch_size=128)

    e1 = embed_text_torch("kokoro voice pipeline", encoder, word_to_idx)
    e2 = embed_text_torch("tts speech synthesis", encoder, word_to_idx)
    e3 = embed_text_torch("mysql database", encoder, word_to_idx)
    e4 = embed_text_torch("kokoro voice", encoder, word_to_idx)
    print(f"  [finetuned] sim('kokoro voice pipeline','tts speech synthesis') = {cosine_sim(e1, e2):.4f}")
    print(f"  [finetuned] sim('mysql database','kokoro voice') = {cosine_sim(e3, e4):.4f}\n")

    # 7. Convert to CoreML
    print("Converting encoder to CoreML...")
    mlmodel = convert_to_coreml(encoder)
    mlmodel.save(str(MODEL_PATH))
    # .mlpackage is a directory bundle; walk it for true size
    size = 0
    for root, _dirs, files in os.walk(MODEL_PATH):
        for fname in files:
            size += os.path.getsize(os.path.join(root, fname))
    print(f"  Saved: {MODEL_PATH} ({size/1024:.1f} KB)\n")

    # 8. Save vocab
    with open(VOCAB_PATH, "w") as f:
        json.dump({
            "vocab": vocab,
            "word_to_idx": word_to_idx,
            "vocab_size": VOCAB_SIZE,
            "embed_dim": EMBED_DIM,
            "hidden_dim": HIDDEN_DIM,
            "input_name": "text_bow",
            "output_name": "embedding",
        }, f, indent=2)
    print(f"  Saved: {VOCAB_PATH}\n")

    # 9. Test similarity with CoreML model
    print("=== CoreML Inference + Similarity Tests ===\n")
    tests = [
        ("kokoro voice pipeline", "tts speech synthesis", "high"),
        ("mysql database", "kokoro voice", "low"),
        ("kokoro voice pipeline", "kokoro voice", "high"),
        ("mysql database query", "sql database connection", "high"),
        ("tts speech synthesis", "mysql database", "low"),
    ]
    for a, b, expect in tests:
        ea = embed_text_coreml(a, mlmodel, word_to_idx)
        eb = embed_text_coreml(b, mlmodel, word_to_idx)
        sim = cosine_sim(ea, eb)
        status = "PASS" if (sim > 0.5 if expect == "high" else sim < 0.5) else "FAIL"
        print(f"  [{status}] sim('{a}','{b}') = {sim:.4f}  (expect {expect})")

    # 10. Inference timing
    print("\nInference timing (CoreML):")
    sample_vec = text_to_bow("kokoro voice pipeline", word_to_idx).reshape(1, -1)
    # Warmup
    for _ in range(5):
        mlmodel.predict({"text_bow": sample_vec})
    n_iter = 50
    t0 = time.time()
    for _ in range(n_iter):
        mlmodel.predict({"text_bow": sample_vec})
    elapsed = time.time() - t0
    per_call = (elapsed / n_iter) * 1000.0
    print(f"  {n_iter} calls: {elapsed*1000:.1f} ms total, {per_call:.3f} ms/call")

    # 11. Model size
    print(f"\nModel size: {size/1024:.1f} KB ({size} bytes)")
    print(f"  Architecture: Linear({VOCAB_SIZE}->{HIDDEN_DIM}) + ReLU + Linear({HIDDEN_DIM}->{EMBED_DIM}) + L2norm")
    print(f"  Params: {VOCAB_SIZE*HIDDEN_DIM + HIDDEN_DIM*EMBED_DIM} weights + {HIDDEN_DIM+EMBED_DIM} biases")

    print(f"\n=== Done ===")
    print(f"  Model:  {MODEL_PATH}")
    print(f"  Vocab:  {VOCAB_PATH}")
    print(f"  Size:   {size/1024:.1f} KB")
    print(f"  Latency: {per_call:.3f} ms/call (Neural Engine ready)")


if __name__ == "__main__":
    main()
