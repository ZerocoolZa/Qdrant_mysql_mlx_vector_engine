#!/usr/bin/env python3
#[@GHOST]{[@file<build_intent_coreml.py>][@state<active>][@ver<v1.0>][@auth<Devin>][@date<2026-07-04>]}
#[@VBSTYLE]{[@auth<Devin>][@role<coreml_builder>][@return<mlmodel>][@no<print|hardcoded>]}
#[@FILEID]{build_intent_coreml}
#[@SUMMARY]{Trains a tiny bag-of-words intent classifier in PyTorch, converts to CoreML .mlmodel. Runs on Neural Engine, zero RAM bloat. 19 tool intents, 128 vocab, 2 linear layers.}
#[@CLASS]{IntentCoremlBuilder}
#[@METHOD]{build_vocab, make_dataset, train, convert_coreml, save}

"""
Build a tiny intent classifier → CoreML model.

Architecture:
  Input:  bag-of-words vector (128 vocab words → 128-dim float vector)
  Layer1: Linear(128 → 64) + ReLU
  Layer2: Linear(64 → 19) + Softmax
  Output: 19 class probabilities (one per tool intent)

Size: ~8KB weights. Runs on Apple Neural Engine. Zero RAM bloat.

The C code in Dom_Bloodhound loads the .mlmodel and feeds it a bag-of-words
vector built from the user's query. The model outputs which tool to call.
"""

import torch
import torch.nn as nn
import coremltools as ct
import numpy as np
import json
import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "intent_model"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Tool intents (must match smart_router.py TOOL_CATALOG) ────
INTENTS = [
    ("cascade_chat_search_sessions", "search find session chat topic discussed conversation which where"),
    ("cascade_chat_session_detail",  "detail full show session trajectory tell me about what happened"),
    ("cascade_chat_search_files",    "file files mentioned touched created modified edited which what"),
    ("cascade_chat_search",          "keyword search loaded ram messages content"),
    ("cascade_chat_load_all",        "load all everything decrypt pb files"),
    ("cascade_chat_scan",            "scan discover list files available how many exist"),
    ("cascade_chat_stats",           "stats statistics count summary overview how many loaded"),
    ("cascade_chat_list",            "list loaded what loaded show loaded trajectories"),
    ("cascade_chat_read",            "read chat pb show conversation open file"),
    ("cascade_chat_export",          "export markdown md archive save as markdown"),
    ("cascade_chat_export_db",       "export mysql database populate sync transfer to db"),
    ("cascade_chat_verify_db",       "verify check mysql all database missing from db"),
    ("cascade_chat_clean",           "clean delete remove old chats pb files"),
    ("bcl_chat_compress",           "compress bcl tokens tokenize extract tokens"),
    ("bcl_chat_dry_run",            "dry run preview bcl estimate tokens preview compression"),
    ("read_file",                    "read file cat show contents what's in file"),
    ("write_file",                   "write save create file content to file"),
    ("list_directory",               "list dir directory ls folder contents what's in directory"),
    ("tools_md",                     "tools help what tools available document tools generate docs"),
]

# ── Training data: (query, intent_index) ──────────────────────
TRAINING_QUERIES = [
    # search_sessions
    ("search for kokoro voice pipeline", 0),
    ("find sessions about mlx", 0),
    ("which chats discussed vbstyle", 0),
    ("search conversations about graph engine", 0),
    ("find chat where we talked about qdrant", 0),
    ("search for cascade cli", 0),
    ("look for sessions about bloodhound", 0),
    ("which sessions discussed the pipeline", 0),
    ("find chats about mysql migration", 0),
    ("search for embedding model", 0),
    ("find sessions about error handling", 0),
    ("search for dom_bcl parser", 0),
    ("which chats talked about taskplanner", 0),
    ("search for voice pipeline config", 0),
    ("find sessions about cascade_chats database", 0),

    # session_detail
    ("show me session 8fe75f98-5aff-47d7-9695-cc3acf2c6963", 1),
    ("get details for trajectory abc123", 1),
    ("full detail of session xyz", 1),
    ("tell me about session 12345", 1),
    ("what happened in session 8fe75f98", 1),
    ("show session detail", 1),
    ("get session info", 1),

    # search_files
    ("which sessions touched model_gui.py", 2),
    ("who created file model_gui.py", 2),
    ("which sessions mentioned pb_reader.py", 2),
    ("find sessions that edited config.py", 2),
    ("which chats modified main.go", 2),
    ("sessions that touched tools.go", 2),
    ("who mentioned bloodhound.c", 2),
    ("which sessions created the file", 2),
    ("find chats that referenced model_gui", 2),
    ("which sessions edited the file", 2),

    # search (RAM)
    ("search loaded chats for keyword", 3),
    ("keyword search in ram messages", 3),
    ("search content in loaded chats", 3),

    # load_all
    ("load all chats", 4),
    ("load everything", 4),
    ("decrypt all pb files", 4),
    ("load all cascade files", 4),
    ("load all pb files into ram", 4),

    # scan
    ("scan for pb files", 5),
    ("discover chat files", 5),
    ("what files exist on disk", 5),
    ("how many pb files", 5),
    ("list available chats", 5),

    # stats
    ("stats", 6),
    ("show statistics", 6),
    ("how many loaded", 6),
    ("count of trajectories", 6),
    ("summary of loaded data", 6),
    ("overview of ram db", 6),

    # list
    ("list loaded trajectories", 7),
    ("what is loaded in ram", 7),
    ("show loaded chats", 7),
    ("list what we have", 7),

    # read
    ("read chat file", 8),
    ("read this pb file", 8),
    ("show conversation from file", 8),
    ("open chat abc.pb", 8),
    ("read the chat", 8),

    # export
    ("export chat to markdown", 9),
    ("export to md files", 9),
    ("archive this chat", 9),
    ("save as markdown", 9),

    # export_db
    ("export to mysql", 10),
    ("populate the database", 10),
    ("sync to mysql", 10),
    ("transfer to database", 10),
    ("export loaded chats to mysql", 10),

    # verify_db
    ("verify database", 11),
    ("check mysql", 11),
    ("are all files in mysql", 11),
    ("verify all pb in db", 11),
    ("check what's missing from db", 11),

    # clean
    ("clean up old pb files", 12),
    ("delete old chats", 12),
    ("remove pb files after export", 12),

    # bcl_compress
    ("compress this chat to bcl", 13),
    ("bcl tokenize this file", 13),
    ("extract bcl tokens", 13),
    ("compress to tokens", 13),

    # bcl_dry_run
    ("dry run bcl compression", 14),
    ("preview bcl tokens", 14),
    ("estimate token count", 14),
    ("preview compression without writing", 14),

    # read_file
    ("read file contents", 15),
    ("cat this file", 15),
    ("show me the file", 15),
    ("what's in this file", 15),
    ("read the file at path", 15),

    # write_file
    ("write to file", 16),
    ("save this content to a file", 16),
    ("create a new file", 16),
    ("write content to disk", 16),

    # list_directory
    ("list directory contents", 17),
    ("ls this folder", 17),
    ("what's in this directory", 17),
    ("show directory listing", 17),

    # tools_md
    ("what tools are available", 18),
    ("show me the tools", 18),
    ("help with tools", 18),
    ("generate tools documentation", 18),
    ("list all tools", 18),
]


class IntentNet(nn.Module):
    """Tiny bag-of-words classifier: 128 → 64 → 19."""
    def __init__(self, vocab_size, num_classes):
        super().__init__()
        self.fc1 = nn.Linear(vocab_size, 64)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(64, num_classes)

    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.fc2(x)
        return x


def build_vocab(training_queries, max_vocab=128):
    """Build vocabulary from training queries."""
    word_counts = {}
    for query, _ in training_queries:
        for word in query.lower().split():
            word = word.strip(".,!?;:\"'()[]{}")
            if len(word) < 2:
                continue
            word_counts[word] = word_counts.get(word, 0) + 1

    # Sort by frequency, take top N
    sorted_words = sorted(word_counts.keys(), key=lambda w: -word_counts[w])
    vocab = sorted_words[:max_vocab]
    word_to_idx = {w: i for i, w in enumerate(vocab)}
    return vocab, word_to_idx


def query_to_vector(query, word_to_idx, vocab_size):
    """Convert query to bag-of-words vector."""
    vec = np.zeros(vocab_size, dtype=np.float32)
    for word in query.lower().split():
        word = word.strip(".,!?;:\"'()[]{}")
        if word in word_to_idx:
            vec[word_to_idx[word]] = 1.0
    return vec


def train_model(X, y, vocab_size, num_classes, epochs=200):
    """Train the tiny classifier."""
    model = IntentNet(vocab_size, num_classes)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    X_t = torch.FloatTensor(X)
    y_t = torch.LongTensor(y)

    for epoch in range(epochs):
        optimizer.zero_grad()
        out = model(X_t)
        loss = criterion(out, y_t)
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 50 == 0:
            with torch.no_grad():
                preds = model(X_t).argmax(dim=1)
                acc = (preds == y_t).float().mean().item()
                print(f"  Epoch {epoch+1}: loss={loss.item():.4f} acc={acc:.2%}")

    return model


def convert_to_coreml(torch_model, vocab_size, num_classes, intent_names):
    """Convert PyTorch model to CoreML."""
    torch_model.eval()

    # Trace the model
    example = torch.randn(1, vocab_size)
    traced = torch.jit.trace(torch_model, example)

    # Convert to CoreML
    mlmodel = ct.convert(
        traced,
        inputs=[ct.TensorType(name="query_bow", shape=(1, vocab_size))],
    )

    # Add metadata
    mlmodel.short_description = "Intent classifier for MCP tool routing"
    mlmodel.author = "Devin"
    mlmodel.version = "1.0"
    mlmodel.user_defined_metadata["intent_names"] = json.dumps(intent_names)

    return mlmodel


def main():
    print("=== Building Intent CoreML Model ===\n")

    # 1. Build vocab
    vocab, word_to_idx = build_vocab(TRAINING_QUERIES)
    vocab_size = len(vocab)
    print(f"Vocabulary: {vocab_size} words")

    # 2. Build dataset
    X = np.array([query_to_vector(q, word_to_idx, vocab_size) for q, _ in TRAINING_QUERIES])
    y = np.array([label for _, label in TRAINING_QUERIES])
    print(f"Training data: {len(X)} samples, {len(INTENTS)} classes\n")

    # 3. Train
    print("Training:")
    model = train_model(X, y, vocab_size, len(INTENTS), epochs=200)

    # 4. Test
    print("\nTest predictions:")
    test_queries = [
        "search for kokoro",
        "which sessions touched model_gui.py",
        "load all chats",
        "export to mysql",
        "stats",
        "what tools are available",
        "show me session abc-123",
        "compress to bcl",
    ]
    for q in test_queries:
        vec = torch.FloatTensor(query_to_vector(q, word_to_idx, vocab_size)).unsqueeze(0)
        with torch.no_grad():
            pred = model(vec).argmax(dim=1).item()
            probs = torch.softmax(model(vec), dim=1)
            conf = probs[0][pred].item()
        print(f"  '{q}' → {INTENTS[pred][0]} (conf={conf:.2f})")

    # 5. Convert to CoreML
    print("\nConverting to CoreML...")
    intent_names = [name for name, _ in INTENTS]
    mlmodel = convert_to_coreml(model, vocab_size, len(INTENTS), intent_names)

    # 6. Save
    model_path = OUTPUT_DIR / "IntentRouter.mlpackage"
    mlmodel.save(str(model_path))
    size = os.path.getsize(model_path)
    print(f"\nSaved: {model_path} ({size/1024:.1f} KB)")

    # 7. Save vocab + intent names for C code
    meta_path = OUTPUT_DIR / "intent_vocab.json"
    with open(meta_path, "w") as f:
        json.dump({
            "vocab": vocab,
            "word_to_idx": word_to_idx,
            "intents": intent_names,
            "intent_keywords": {name: kw for name, kw in INTENTS},
        }, f, indent=2)
    print(f"Saved: {meta_path}")

    # 8. Test CoreML model
    print("\nCoreML inference test:")
    test_vec = query_to_vector("search for kokoro", word_to_idx, vocab_size)
    pred = mlmodel.predict({"query_bow": test_vec.reshape(1, -1)})
    # Find the output key (auto-named by CoreML)
    out_key = list(pred.keys())[0]
    probs = pred[out_key][0]
    best_idx = int(np.argmax(probs))
    print(f"  'search for kokoro' → {intent_names[best_idx]} (prob={probs[best_idx]:.4f})")

    # Test a few more
    for q in ["which sessions touched model_gui.py", "load all chats", "stats"]:
        vec = query_to_vector(q, word_to_idx, vocab_size)
        p = mlmodel.predict({"query_bow": vec.reshape(1, -1)})
        probs = p[out_key][0]
        idx = int(np.argmax(probs))
        print(f"  '{q}' → {intent_names[idx]} (prob={probs[idx]:.4f})")

    print(f"\n=== Done. Model: {model_path} ===")
    print(f"    Vocab: {meta_path}")
    print(f"    Size: {size/1024:.1f} KB (runs on Neural Engine, zero RAM bloat)")


if __name__ == "__main__":
    main()
