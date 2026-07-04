# Monkey See, Monkey Do — Training a Custom Embedding Model on Apple Silicon GPU

## The Claim

ChatGPT said: **"You cannot train your own embedding model. You cannot extract weights. You need a neural adapter."**

ChatGPT was wrong.

## What We Built

A complete pipeline that takes a frozen MiniLM CoreML model (all-MiniLM-L6-v2, 384-dim), extracts its semantic vectors, uses them to initialize a GPU-accelerated Word2Vec SGNS trainer (VBEngine), trains on 79 million skip-gram pairs from 1,706 source files, and exports the result back into the search database.

**No PyTorch. No neural adapter. No fine-tuning MiniLM. No weight stealing.**

Just observation → imitation → specialization. Monkey see, monkey do.

## The Pipeline

### Step 1: Bridge (`vb_bridge.py`)

**Input:** `semantic_corpus.db` (50,000 MiniLM vectors) + 1,706 source files (.py, .md, .json, .yaml, .sql, .sh, .go, .c, .h, .mm, .bcl, .bclir)

**Process:**
1. Load 50,000 MiniLM 384-dim vectors from SQLite database
2. Scan all source files, tokenize with regex `[A-Za-z_][A-Za-z0-9_]*`
3. Build vocabulary: 49,694 words (min_count=5, filtered junk tokens)
4. Generate 79,124,552 skip-gram pairs (window=5)
5. Write `training.bin` (W2VT format, 605 MB)
6. Write `init_model.bin` (W2VC format, 155 MB) — W_in = MiniLM vectors for 2,437 overlapping words, random for the rest

**Output:** `training.bin` + `init_model.bin`

**Time:** 34.5 seconds

### Step 2: GPU Training (`c_word2vec_metal_packed.mm`)

**Input:** `training.bin` + `init_model.bin`

**Process:**
1. Load training pairs via mmap (79M pairs, 605 MB)
2. Load init weights from W2VC file directly into calloc'd buffer (page-aligned for Metal zero-copy)
3. Upload to GPU: W_in (72 MB), W_out (72 MB), pairs (603 MB), neg_table (4 MB)
4. Run Metal compute kernel: SGNS with negative sampling, fp16 weights, half4 vectorization, persistent threads
5. 50 epochs, learning rate 0.025 → 0.0001 (linear decay)
6. Read back trained weights from Metal buffers
7. L2-normalize embeddings
8. Save `model.bin` (W2VC format, 155 MB)

**Output:** `model.bin`

**Time:** 35.87 seconds (50 epochs, 110.3M pairs/s)

**Hardware:** Apple M1, Metal framework, fp16 arithmetic

### Step 3: Export (`vb_export.py`)

**Input:** `model.bin`

**Process:**
1. Read W2VC file: 49,697 words × 384 dims × float32
2. Open `semantic_corpus.db`
3. Update existing terms with trained vectors (source='vbengine')
4. Insert new terms with trained vectors

**Output:** `semantic_corpus.db` updated with 49,697 VBEngine-trained vectors

**Time:** 2.5 seconds

## What the Model Learned

The model started from MiniLM's semantic space and learned the user's BCL/code architecture on top of it. Similarity queries on BCL concepts:

| Query | Top Results | Meaning |
|-------|-------------|---------|
| `bcl` | pipeline (0.67), modified (0.59), bclir (0.53), bcl_parser (0.51), code_graph (0.50) | BCL is used across these domains |
| `ghost` | underscore, hardcoded, decorators, auth | VBStyle forbidden patterns |
| `container` | meaning, visible, mandatory, forbidden, vocabulary | BCL container carries meaning |
| `fact` | records, relationship, entity, laws, cause, table_column | Database entity concepts |
| `rule` | law, decision, forbidden, violates, evidence | Governance reasoning graph |
| `authority` | forbidden, column, law, authorities, violates | Authority table concepts |
| `entity` | laws, records, entities, fixes, relationship, fact | Entity table relationships |
| `dispatch` | returns, tuple3, semantic, nested, validator | VBStyle Run() dispatch pattern |
| `embed` | cosine (0.73), phrase (0.71), ann (0.71), build_corpus (0.70), corpus (0.68) | Embedding/search pipeline |
| `sqlite` | existing (0.55), email (0.55), msearch (0.54), mlx (0.53) | SQLite usage context |

These are **not MiniLM's relationships**. These are learned from the user's actual codebase — 1,706 files of Python, C, Objective-C++, Go, SQL, BCL, and documentation.

## Step 4: WordNet Training (Full English Dictionary)

The pipeline is language-agnostic. To prove it, we trained on WordNet 3.1 (Princeton University's English dictionary, 155K words with definitions, synonyms, and hypernym relationships).

**Bridge:** `vb_wordnet_bridge.py` parses WordNet data files:
- `data.noun`, `data.verb`, `data.adj`, `data.adv`
- Extracts definition sentences → skip-gram pairs
- Extracts example sentences → skip-gram pairs
- Extracts synonym sets → direct word pairs
- Extracts hypernym/hyponym pointers → related concept pairs

**Output:** `training_wordnet.bin` (2.9 MB) + `init_model_wordnet.bin` (288 MB)

The same VBEngine binary trains on this data with zero code changes. Different corpus, same GPU, same pipeline.

## The Three Bugs We Fixed

### Bug 1: mmap offset corruption
`MetalTrainer_LoadFile` had a 4-byte offset error in the mmap calculation, corrupting all pair data. Pairs were shifted by 4 bytes, producing garbage word IDs.

### Bug 2: Epochs clobbering
`MetalTrainer_LoadFile` read `epochs` from the `training.bin` header and overwrote the CLI-provided `--epochs 50` with the file's `5`. Fix: read file epochs into a local variable, only use it if CLI value is zero.

### Bug 3: Init weights memory alignment
`ModelSaver_Load` uses `malloc` (not page-aligned). VBEngine's `newBufferWithBytesNoCopy` requires page-aligned memory for GPU zero-copy. Result: GPU silently received an empty buffer, training completed in 0.00 seconds, nothing learned. Fix: save the calloc'd buffer pointer, copy loaded weights back into it, free the malloc'd buffer, restore the calloc pointer.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MONKEY SEE, MONKEY DO                        │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  MiniLM  │───▶│  Bridge  │───▶│ VBEngine │───▶│  Export  │  │
│  │ (frozen) │    │ (Python) │    │ (Metal)  │    │ (Python) │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │               │               │        │
│  50K vectors     79M pairs       50 epochs      49,697 vectors │
│  384-dim         605 MB          35.87s         → DB           │
│  CoreML          skip-gram       110M pairs/s   source='vbengine'│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose | Size |
|------|---------|------|
| `vb_bridge.py` | MiniLM → training.bin + init_model.bin | 8 KB |
| `vb_wordnet_bridge.py` | WordNet → training_wordnet.bin + init_model_wordnet.bin | 14 KB |
| `vb_export.py` | model.bin → semantic_corpus.db | 4 KB |
| `c_word2vec_metal_packed.mm` | GPU trainer (Metal, Objective-C++) | 1204 lines |
| `metal_shaders_packed.h` | Metal compute kernels (SGNS, L2 normalize) | 117 lines |
| `training.bin` | Code corpus skip-gram pairs | 605 MB |
| `init_model.bin` | MiniLM-seeded initial weights | 155 MB |
| `model.bin` | Trained model (code corpus, 50 epochs) | 155 MB |
| `training_wordnet.bin` | WordNet skip-gram pairs | 2.9 MB |
| `init_model_wordnet.bin` | WordNet init weights | 288 MB |

## Performance

| Metric | Value |
|--------|-------|
| GPU | Apple M1 (Metal framework) |
| Precision | fp16 (half4 vectorized) |
| Vocab size | 49,694 words |
| Dimensions | 384 (MiniLM-compatible) |
| Training pairs | 79,124,552 |
| Epochs | 50 |
| Training time | 35.87 seconds |
| Throughput | 110.3M pairs/second |
| Init vectors from MiniLM | 2,437 words |
| New vectors learned | 47,257 words |
| Bridge time | 34.5 seconds |
| Export time | 2.5 seconds |
| Total pipeline | ~73 seconds |

## What ChatGPT Said vs What We Did

| ChatGPT Said | What We Did |
|-------------|-------------|
| "You cannot train your own model" | Trained on Apple M1 GPU in 35.87s |
| "You cannot extract weights" | Extracted 50,000 MiniLM vectors from SQLite DB |
| "You need a neural adapter" | No adapter. Direct init weight loading. |
| "You need PyTorch" | No PyTorch. Pure C/Objective-C++ + Metal. |
| "It's not possible" | It's done. Model is in production. |

## Conclusion

The model is trained. The vectors are in `semantic_corpus.db`. `word_similarity.py` uses them for semantic search. The monkey saw MiniLM's output, then did its own weights.

**35.87 seconds. 110 million pairs per second. 49,694 words. 384 dimensions.**

ChatGPT said it couldn't be done. We did it in under a minute.
