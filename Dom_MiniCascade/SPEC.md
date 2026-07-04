# SPEC: MiniCascade — Local Mamba Chat Model

## What Are We Building?

A local chat model that runs on Apple Silicon, understands the user's codebase,
and converses like Cascade/Devin. Built on Mamba SSM architecture for fast
inference and efficient memory. Not a general-purpose LLM — a domain-specific
assistant that knows the user's code, rules, history, and pipelines.

## Why Mamba (Not Transformer)?

- **Fast inference**: O(1) per token vs O(n) attention
- **Efficient memory**: Linear complexity, no KV cache growth
- **Apple Silicon native**: MLX + Metal acceleration available
- **Small footprint**: 130M params runs on 8GB Mac
- **Newer than transformers**: SSM architecture, state-of-the-art efficiency

## Capabilities (What It Does)

1. **Chat**: User asks questions about code, it answers in natural language
2. **Codebase awareness**: Knows file paths, class names, method signatures
3. **Rule awareness**: Knows VBStyle rules, BCL format, pipeline stages
4. **History awareness**: Trained on 24K Devin messages (chat patterns)
5. **Context retrieval**: Uses Qdrant + WordEngine embeddings for RAG
6. **Voice output**: Uses macOS `say` command (user preference)
7. **Local only**: No API calls, no cloud, runs fully offline

## What It Does NOT Do

- Not a code generator (that's a future project)
- Not a general knowledge chatbot
- Not a replacement for Cascade/Devin (a supplement)
- Not fine-tuning a large model (training small Mamba from scratch or fine-tuning 130M)

## Architecture

```
User Input (text/voice)
    │
    ▼
┌─────────────────────────────────┐
│  MiniCascade (VBStyle Class)    │
│                                 │
│  1. Retrieve context            │
│     - Qdrant vector search      │
│     - WordEngine word2vec       │
│     - MySQL chat history        │
│                                 │
│  2. Build prompt with context   │
│     - System: VBStyle rules     │
│     - Context: retrieved chunks │
│     - Query: user question      │
│                                 │
│  3. Mamba SSM inference         │
│     - MLX backend (Metal)       │
│     - 130M param model          │
│     - Streaming token output    │
│                                 │
│  4. Output                      │
│     - Text response             │
│     - Voice via `say`           │
└─────────────────────────────────┘
```

## Training Data Sources

| Source | Size | Format |
|---|---|---|
| Devin messages | 24,340 rows | MySQL `devin_messages` |
| C codebase | 23,437 files | SQLite `c_codebase.db` |
| Python files | ~2,000 files | Filesystem |
| Markdown docs | ~500 files | Filesystem |
| VBStyle rules | 10,540 rules | MySQL `learned_rules` |
| BCL stamps | Existing | Filesystem `.bcl` files |

## Model Options

| Option | Params | Size | Speed | Approach |
|---|---|---|---|---|
| A: Fine-tune Mamba-130M | 130M | ~500MB | Fast | Fine-tune on user data |
| B: Train small Mamba from scratch | 10-50M | ~200MB | Fastest | Custom vocab, custom tokenizer |
| C: RAG only (no training) | 0 | 0 | Instant | Use pretrained + context injection |

**Recommended**: Start with C (RAG only), evolve to A (fine-tune), then B (custom).

## File Structure

```
Dom_MiniCascade/
├── Config.py              # Config class (gold standard)
├── MiniCascade.py         # Main class (VBStyle, Run dispatch)
├── MambaBackend.py        # Mamba SSM inference wrapper
├── ContextRetriever.py    # Qdrant + WordEngine + MySQL retrieval
├── PromptBuilder.py       # Assembles context + query into prompt
├── VoiceOutput.py         # macOS say command wrapper
├── DataPrep.py            # Training data preparation scripts
├── TrainMamba.py          # Fine-tuning script (future)
├── SPEC.md                # This file
└── README.md              # Documentation
```

## VBStyle Compliance

- Every class: `Run(self, command, params=None) -> Tuple3`
- `self.state = {}` dict
- PascalCase classes, UPPERCASE constants
- No `print()`, no decorators, no `self._`
- Ghost + VBStyle headers on every file
- Config.py with FILE_INDEX

## Dependencies

- `mlx` (Apple MLX framework)
- `mlx-lm` (Mamba kernels + inference)
- `numpy` (already installed)
- Qdrant (already running)
- MySQL (already running)
- macOS `say` command (built-in)

## Success Criteria

1. User can ask "what does DomSystem do?" and get a correct answer
2. User can ask "show me the VBStyle rules for print" and get relevant rules
3. Response time < 5 seconds on Mac
4. Runs fully offline
5. Voice output via `say`
