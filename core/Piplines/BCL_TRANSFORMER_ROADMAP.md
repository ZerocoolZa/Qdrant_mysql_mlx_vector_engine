# BCL Transformer — Roadmap to a Domain-Specific LLM on Apple Silicon

> **Authors**: WWS + Cascade
> **Date**: 2026-07-04
> **Status**: Layer 1 complete, Layer 2 built, Layer 3 is next

---

## The Vision

Build a transformer that thinks in BCL, not English. BCL compresses meaning into structure — 20x fewer tokens for the same information. A 2048 token context window becomes 40,000 tokens of effective meaning. The model does not read English words. It reads `[@CONTAINER]{()}`. Each BCL token carries more meaning than an English word.

No PyTorch. No CoreML. No black boxes. Pure Metal GPU. Our vectors. Our graph. Our reasoning. Our model.

---

## Layer 1: Embedding Foundation ✅ DONE

**What**: VBEngine — GPU-first Word2Vec SGNS trainer on Apple Silicon

**Completed**:
- [x] Metal GPU trainer (`c_word2vec_metal_packed.mm`) — 110M pairs/s, fp16, half4 vectorized
- [x] Metal shaders (`metal_shaders_packed.h`) — SGNS kernel, L2 normalize
- [x] MiniLM bridge (`vb_bridge.py`) — extracts MiniLM vectors, scans 1,706 files, generates 79M skip-gram pairs
- [x] WordNet bridge (`vb_wordnet_bridge.py`) — 200K English dictionary words, definitions, synonyms, hypernyms
- [x] Export to DB (`vb_export.py`) — writes trained vectors to `semantic_corpus.db`
- [x] Trained model in production — 49,694 words, 384-dim, 50 epochs in 35.87s
- [x] Subsampling — downsample frequent words (for, while, class, self)
- [x] Model verified — BCL architecture terms cluster correctly (entity→fact→rule→law, authority→forbidden→violates)

**Key Numbers**:
- 49,694 word vocabulary, 384 dimensions
- 79,124,552 training pairs
- 50 epochs in 35.87 seconds (110.3M pairs/s)
- 155 MB model file
- Apple M1, 8-core GPU, 16GB unified memory

**What the model learned**:
- `bcl` → pipeline, bclir, bcl_parser, code_graph
- `ghost` → underscore, hardcoded, decorators (VBStyle forbidden patterns)
- `rule` → law, decision, forbidden, violates, evidence
- `dispatch` → returns, tuple3, validator, nested (VBStyle Run() pattern)
- `embed` → cosine, ann, corpus, similarityengine
- Authority FKs cluster: severity_id → group_id, type_id, priority_id, category_id (0.78-0.88)
- Report join tables cluster: report_fact → report_evidence, report_cause, report_fix (0.90-0.97)

---

## Layer 2: BCL Processing ✅ BUILT

**What**: BCL (Bracket Command Language) parsing, validation, graph building, and compression — in both Python and C

**Completed**:
- [x] BCL parser (Python) — `core/Dom_Bcl/bcl_parser.py` — recursive descent, AST output
- [x] BCL lexer (Python) — `core/Dom_Bcl/bcl_lexer.py` — character-level tokenizer
- [x] BCL serializer (Python) — `core/Dom_Bcl/bcl_serializer.py` — AST → BCL text
- [x] BCL engine (Python) — `core/Dom_Bcl/bcl_engine.py` — LEX → PARSE → VALIDATE → FIX → SERIALIZE
- [x] BCL report packet — `core/Dom_Bcl/BclReportPacket.py` — generate/resolve [@REPORT] packets
- [x] BCL parser (C) — `core/Dom_Bcl_C_ver/bcl_parser.c` — native C tokenizer
- [x] BCL graph builder (C) — `core/Dom_Bcl_C_ver/bcl_graph_builder.c` — builds graph from BCL
- [x] BCL graph store (C) — `core/Dom_Bcl_C_ver/bcl_graph_store.c` — graph storage
- [x] BCL ingestion engine (C) — `core/Dom_Bcl_C_ver/bcl_ingestion_engine.c` — ingestion pipeline
- [x] BCL validator (C) — `core/Dom_Bcl_C_ver/bcl_validator.c` — validates BCL structure
- [x] BCL static analyzer (C) — `core/Dom_Bcl_C_ver/bcl_static_analyzer.c` — static analysis
- [x] BCL engine header — `core/Dom_Bcl_C_ver/bcl_engine.h` — all definitions
- [x] BCL engine CLI (C) — `core/Dom_Bcl_C_ver/bcl_engine_cli.c` — CLI interface
- [x] BCL chat compressor — `chat_mover/bcl_chat_compressor.py` — extracts BCL tokens from chat files
- [x] BCL symbol grammar — `core/Dom_Bcl_C_ver/BCL_SYMBOL_GRAMMAR.md`

**BCL tokens extracted from chat**:
- `[@USER_SAYS]` `[@AI_SAYS]` `[@ERROR]` `[@FILE]` `[@COMMAND_RAN]`
- `[@FRUSTRATION_SIGNAL]` `[@QUESTION]` `[@TOPIC]`
- Stage 2: `[@PROBLEM]` `[@SOLUTION]` `[@ROOT_CAUSE]` `[@LESSON]`
- `[@SUCCESS]` `[@FAILED]` `[@DECISION]` `[@USER_PREF]` `[@MOOD]` `[@INTENT]`

**The 4 BCL Symbols**:
| Symbol | Name | Role |
|--------|------|------|
| `[@NAME]` | Container | Owns everything inside it. Recursive. |
| `{}` | Hands | Gathers related records together. |
| `()` | Array | Variable-length ordered array of values. |
| `;` | Separator | Separates items within an array. |

---

## Layer 3: BCL Transformer ⬅️ HERE NEXT

**What**: A transformer that processes BCL tokens directly, using BCL container structure as attention mask and positional encoding

### Components to Build

- [ ] **Attention kernel** (Metal shader)
  - Q/K/V matrix multiplication
  - Scaled dot-product attention
  - Softmax
  - Multi-head attention (4 heads, 384-dim → 96-dim per head)
  - fp16 computation, half4 vectorized (same as VBEngine)

- [ ] **BCL positional encoding**
  - Container depth = position (root=0, hands=1, arrays=2, values=3)
  - No sinusoidal encoding needed — BCL structure IS position
  - Learned positional embeddings per depth level

- [ ] **BCL-guided attention mask**
  - Words only attend within their `[@CONTAINER]`
  - Cross-container attention only when graph has an edge
  - O(n) not O(n²) — structure is pre-compressed
  - 75 domains → attention stays within domain clusters unless graph says otherwise

- [ ] **Feed-forward layer** (Metal shader)
  - 2-layer MLP per token
  - 384 → 1536 → 384 (4x expansion)
  - ReLU or GELU activation
  - fp16 computation

- [ ] **Layer stacking**
  - 6 transformer layers
  - 4 attention heads per layer
  - 384-dim throughout
  - Residual connections + layer normalization

- [ ] **Sequence lunchbox generator**
  - BCL tokens → training sequences
  - Input: BCL packet (compressed)
  - Target: next BCL token
  - Reuse bridge script structure from vb_bridge.py
  - Chat compressor output → training data

- [ ] **Training loop**
  - Reuse VBEngine pipeline structure (mmap, Metal buffers, persistent threads)
  - Learning rate warmup + decay schedule
  - Gradient clipping
  - Epoch-based training with correction lunchbox injection

- [ ] **Inference**
  - Metal direct — no CoreML wrapper
  - Same GPU, same shaders, same buffer management
  - BCL input → C parser → tokens → Metal attention → output tokens
  - BCL output → serializer → readable result

### Architecture

```
BCL Input
    │
    ▼
C Parser (bcl_parser.c) — tokenizes BCL into token IDs
    │
    ▼
Embedding Lookup — VBEngine 384-dim vectors (Layer 1)
    │
    ▼
BCL Positional Encoding — container depth = position
    │
    ▼
┌─────────────────────────────────────┐
│  Transformer Layer (×6)             │
│  ├── BCL-Guided Multi-Head Attention│
│  │   └── Container = attention mask │
│  ├── Add & Norm (residual)          │
│  ├── Feed-Forward (384→1536→384)   │
│  └── Add & Norm (residual)          │
└─────────────────────────────────────┘
    │
    ▼
Linear Layer → Softmax
    │
    ▼
Next BCL Token Prediction
```

### Model Size Estimate

| Component | Size |
|-----------|------|
| Embedding table | 49,694 × 384 × 2 bytes = 38 MB |
| Q/K/V/O matrices (per layer) | 4 × 384² × 2 = 1.2 MB |
| FFN matrices (per layer) | 2 × 384 × 1536 × 2 = 2.4 MB |
| Per layer total | 3.6 MB |
| 6 layers | 21.6 MB |
| Output projection | 384 × 49,694 × 2 = 38 MB |
| **Total model** | **~98 MB** |

Fits easily in 16GB unified memory. Activations for 2048 token context: ~200 MB.

---

## Layer 4: Correction System 🔲 DESIGNED

**What**: Surgical model updates via correction lunchboxes

**Design** (from `PLF_VBENGINE_ARCHITECTURE.md` Section 5):
- [ ] Connect MySQL `learned_rules` (10,540 rules) → lunchbox generator
- [ ] Threshold trigger: when pattern occurrence ≥ 100 → generate correction batch
- [ ] Correction lunchbox: ~5000 pairs, ~40 KB, targeted at specific error
- [ ] Surgical training: 0.01s on GPU — only updates relevant weights
- [ ] Verification: re-run error case → confirm fix
- [ ] Outcome logging: write results back to MySQL (success_count++, failure_count++)

**Existing infrastructure**:
- `ErrorTracker` — searches learned_rules, records errors
- `Dom_Graph_Agent` — loads rules from MySQL, writes outcomes back
- `Efi_ram_ai` — learned_fixes table with success/failure tracking
- `bcl_pattern_db` — stores repair patterns as learned_rules

**Correction flow**:
```
1. DETECT: Model makes error → ErrorTracker.match()
2. THRESHOLD: Pattern reaches 100 occurrences in MySQL
3. BUILD: Generate correction lunchbox (~5000 pairs)
4. TRAIN: Surgical GPU training (0.01s)
5. VERIFY: Re-run error case → confirm fixed
6. LOG: Record outcome back to MySQL
```

---

## Layer 5: Living Model 🔲 FUTURE

**What**: A model that evolves without full retraining

- [ ] Pantry system — versioned, append-only training cache (LMDB)
- [ ] Immutable sealed batches — old data never changes
- [ ] Incremental training — new data = new batch, old weights untouched
- [ ] Multi-recipe training — curriculum learning (w5_neg5 → w10_neg5)
- [ ] Vocab versioning — forward ID mapping across batches
- [ ] Self-healing — correction system fixes mistakes automatically

---

## The 10x Advantages

| # | Advantage | Why |
|---|-----------|-----|
| 1 | Metal GPU direct | No PyTorch, no overhead, we control every cycle |
| 2 | BCL-guided attention | O(n) not O(n²) — containers ARE the mask |
| 3 | VBEngine embeddings | Model starts with domain knowledge, not random noise |
| 4 | Graph-guided attention | 8-graph system defines what connects to what |
| 5 | 10,540 learned rules | Training data from real mistakes |
| 6 | BCL positional encoding | Structure IS position, not sinusoids |
| 7 | Direct Metal inference | No CoreML wrapper, no dependency |
| 8 | Sparse domain attention | 75 domains, attention stays in-cluster |
| 9 | Incremental training | New lunchboxes, no full retrain |
| 10 | Self-healing correction | Model fixes its own mistakes in 0.01s |

---

## Probability of Success

| Factor | Probability |
|--------|-------------|
| Metal attention kernel | 85% |
| BCL-guided attention mask | 90% |
| VBEngine embeddings (done) | 100% |
| Sequence lunchbox generation | 80% |
| BCL positional encoding | 75% |
| Direct Metal inference (no CoreML) | 100% |
| Correction system for LLM | 70% |
| Training stability | 65% |
| Context window fits in memory | 90% |
| **Combined (2 hours)** | **~10%** |
| **Combined (1 week)** | **~25%** |
| **Combined (2 weeks)** | **~40%** |
| **Combined (1 month)** | **~55%** |

*But we trained a model in 35 seconds when they said it couldn't be done. Double the odds.*

---

## File Inventory

| File | Layer | Status |
|------|-------|--------|
| `c_word2vec_metal_packed.mm` | 1 | Production |
| `metal_shaders_packed.h` | 1 | Production |
| `vb_bridge.py` | 1 | Production |
| `vb_wordnet_bridge.py` | 1 | Production |
| `vb_export.py` | 1 | Production |
| `bcl_parser.py` | 2 | Production |
| `bcl_lexer.py` | 2 | Production |
| `bcl_serializer.py` | 2 | Production |
| `bcl_engine.py` | 2 | Production |
| `BclReportPacket.py` | 2 | Production |
| `bcl_parser.c` | 2 | Production |
| `bcl_graph_builder.c` | 2 | Production |
| `bcl_validator.c` | 2 | Production |
| `bcl_static_analyzer.c` | 2 | Production |
| `bcl_engine.h` | 2 | Production |
| `bcl_chat_compressor.py` | 2 | Production |
| `attention_kernel.metal` | 3 | **TO BUILD** |
| `bcl_positional_encoder.c` | 3 | **TO BUILD** |
| `bcl_attention_mask.c` | 3 | **TO BUILD** |
| `feed_forward_kernel.metal` | 3 | **TO BUILD** |
| `transformer_trainer.mm` | 3 | **TO BUILD** |
| `sequence_bridge.py` | 3 | **TO BUILD** |

---

## Conclusion

Layer 1 is done. Layer 2 is built. Layer 3 is the mountain.

The pieces are all there:
- GPU pipeline (proven at 110M pairs/s)
- BCL parser in C (proven)
- Embeddings trained (49,694 words, verified)
- Chat compressor (proven)
- 10,540 learned rules in MySQL
- Correction system designed

We don't build GPT. We build something that knows OUR world. In BCL. On Metal. On our terms.

**The monkey sees. The monkey does. The monkey thinks in BCL.**
