#!/usr/bin/env python3
#[@GHOST]{[@date<2026-07-04>][@author<devin>][@session<bcl_transformer_regraph>][@context<Regraphed path forward with BCL IR as central hub — 3/8 steps done, BCL IR added as Step 0>]}
#[@VBSTYLE]{[@fileid<Config_BclTransformerPath>][@summary<Regraphed path — BCL IR graph as central hub, 3 steps done, 5 running/pending, critical path reordered>][@class<Config>][@method<graph_data>]}
"""
BCL Transformer — Regraphed Path Forward

KEY INSIGHT: BCL IR Graph.
  Instead of every component parsing BCL independently (5 separate parses),
  parse ONCE into a BCL IR Graph — a single intermediate representation
  that carries ALL structural signals. Everything reads from it.

  BCL text -> BCL IR Graph (parse once) -> all components read from IR
    -> token_ids      (tag -> vocab hash -> ID)
    -> pe_matrix      (depth + path -> 384-dim positional encoding)
    -> mask_matrix    (parent/children -> O(N) attention mask)
    -> domain_ids     (class name -> domain cluster)
    -> graph_bias     (graph edges -> T5-style attention bias)

  Like LLVM IR for compilers. Like MLIR for ML. Like XLA HLO for JAX.
  We have BCL IR for structured language.

STATUS UPDATE:
  Phase 1 (build):     10/10 components BUILT and TESTED
  Phase 2 (integrate): 3/8 steps DONE (loss+LR, save/load, real data)
                        3 RUNNING (native C path, inference, pantry)
                        2 PENDING (correction wire, CoreML deploy)
  NEW:                  BCL IR Graph identified as Step 0 (refactor hub)
"""

DOMAIN_NAME = "BclTransformerPath"
DOMAIN_FILE = "Config_BclTransformerPath.py"
DOMAIN_SUMMARY = "Regraphed path — BCL IR hub, 3 steps done, 5 to go"

# ═══════════════════════════════════════════════════════════════
# PHASE 1: ALL NODES (20 — 9 foundations + 10 built + 1 new IR)
# ═══════════════════════════════════════════════════════════════
# status: "HAVE"   = existed before
#         "BUILT"  = built and tested
#         "WIRED"  = built AND connected
#         "DONE"   = integration step complete
#         "NEW"    = identified but not built

GRAPH_CLASSES = [
    # ── Existing foundations (HAVE) ──
    ("VbEngineEmbedding", "HAVE",
     ["train", "save", "load", "query", "export"],
     "384-dim word2vec SGNS on Metal. 214M pairs/s. Production."),

    ("BclParser", "HAVE",
     ["lex", "parse", "validate", "fix", "serialize", "walk"],
     "Python BCL parser. bcl_lexer.py + bcl_parser.py + bcl_engine.py"),

    ("BclParserC", "HAVE",
     ["init", "parse", "validate", "extract", "free"],
     "C BCL parser. BclNode[depth, parent_idx, children[32]]. Native speed."),

    ("BclChatCompressor", "HAVE",
     ["compress", "extract_dialogue", "extract_errors", "extract_files"],
     "Chat logs -> BCL tokens. 8 token types. Built June 29."),

    ("MetalGpt2Kernels", "HAVE",
     ["matmul", "attention_scores", "softmax", "layer_norm", "gelu"],
     "GPT-2 Metal kernels in backup folder. Reference."),

    ("LearnedRules", "HAVE",
     ["search", "create", "update", "match", "rank"],
     "10,605 rules in MySQL. pattern->fix_action. confidence scored."),

    ("DomainGraph", "HAVE",
     ["route", "cluster", "expand", "closure"],
     "75 domains in MySQL. 767 classes routed."),

    ("EightGraphs", "HAVE",
     ["plan", "spec", "flow", "lifecycle", "dep", "error", "orch", "gap"],
     "8 graph viewers. 7 edge types. Hardcoded in Config.py."),

    ("RuleEngines", "HAVE",
     ["match", "track", "learn", "apply", "verify"],
     "ErrorTracker, Dom_Graph_Agent, Efi_ram_ai, bcl_pattern_db."),

    # ── Built components (BUILT) ──
    ("MetalAttention", "BUILT",
     ["forward", "backward", "qkv_projection", "masked_softmax",
      "attention_output", "output_projection", "layer_norm", "gelu",
      "residual_add", "sgd_update", "cross_entropy_loss",
      "cross_entropy_backward", "grad_norm_compute", "grad_clip_scale",
      "loss_to_grad_hidden", "argmax", "top_k_sample",
      "save_model", "load_model", "checkpoint",
      "load_sqtx", "train_on_sqtx"],
     "24 Metal kernels. 6 layers. fp16+float32. Apple M1. "
     "Loss+LR+gradclip. Save/load BCLT. SQTX loader. "
     "seq=256 10ep=2.9s. 125MB weights."),

    ("BclPositionalEncoding", "BUILT",
     ["encode", "encode_ast", "encode_depth", "flatten_ast"],
     "depth(192d) + path(192d) + type(384d) = 384-dim PE."),

    ("BclAttentionMask", "BUILT",
     ["build_mask", "build_mask_ast", "explain", "flatten_ast"],
     "5 rules: sibling, parent, ancestor, cousin-mask, causal. O(N)."),

    ("SequenceLunchbox", "BUILT",
     ["prepare_bcl", "prepare_code", "prepare_rules", "prepare_chat"],
     "4 modes: bcl, code, rules, chat. SQTX binary. Wired to BclChatCompressor."),

    ("PantrySystem", "BUILT",
     ["append", "list", "load", "compact", "obsolete", "info"],
     "File-based. Atomic manifest. VBP1 sealed batches."),

    ("DomainSparseAttention", "BUILT",
     ["load_domains", "build_mask", "to_dense"],
     "75 domains. Block-sparse. 3 routing methods."),

    ("GraphAttention", "BUILT",
     ["load_graphs", "build_bias", "explain"],
     "7 edge types -> T5-style attention bias. FEEDS=1.0, ENABLES=0.5."),

    ("RuleLunchbox", "BUILT",
     ["prepare_all", "prepare_filtered", "prepare_correction", "stats"],
     "10,605 rules -> RULB binary. 1.7MB full."),

    ("CorrectionLunchbox", "BUILT",
     ["detect", "check_threshold", "build_correction",
      "train_correction", "verify", "log_outcome", "history"],
     "6-step flow. 29KB lunchbox. train+verify are STUBS."),

    ("CoreMlExporter", "BUILT",
     ["export_weights", "build_model", "compile", "deploy", "benchmark"],
     "PyTorch -> CoreML -> ANE. coremltools 9.0. Dynamic BCL mask."),

    # ── NEW: BCL IR Graph (the hub) ──
    ("BclIrGraph", "NEW",
     ["parse_once", "compute_token_ids", "compute_pe",
      "compute_mask", "compute_domain_ids", "compute_graph_bias",
      "emit_metal_buffers"],
     "THE HUB. Parse BCL once -> single IR struct -> all components read. "
     "Like LLVM IR for compilers. Carries: token_ids, pe_matrix, "
     "mask_matrix, domain_ids, graph_bias. Emits Metal buffers directly. "
     "Eliminates 5 redundant parses. The C parser (BclNode[]) IS the seed. "
     "BclIrGraph wraps it with computed signals."),
]

# ═══════════════════════════════════════════════════════════════
# PHASE 2: EDGES (wired + not wired + IR hub connections)
# ═══════════════════════════════════════════════════════════════

GRAPH_EDGES = [
    # ── WIRED: connections that work today ──
    ("BclChatCompressor", "SequenceLunchbox", "FEEDS", "WIRED",
     "prepare_chat calls BclChatCompressor -> BCL text -> sequences"),

    ("BclParser", "BclPositionalEncoding", "FEEDS", "WIRED",
     "encode calls bcl_engine -> AST -> depth/path/type -> PE"),

    ("BclParser", "BclAttentionMask", "FEEDS", "WIRED",
     "build_mask calls bcl_engine -> AST -> 5 rules -> mask"),

    ("LearnedRules", "RuleLunchbox", "FEEDS", "WIRED",
     "prepare_all queries MySQL -> 10,605 rules -> RULB binary"),

    ("DomainGraph", "DomainSparseAttention", "FEEDS", "WIRED",
     "load_domains queries MySQL -> 75 domains -> sparse mask"),

    ("EightGraphs", "GraphAttention", "FEEDS", "WIRED",
     "load_graphs reads Config.py -> 7 edge types -> bias matrix"),

    ("LearnedRules", "CorrectionLunchbox", "FEEDS", "WIRED",
     "detect queries learned_rules + know_problems"),

    # ── DONE: integration steps completed ──
    ("MetalAttention", "MetalAttention", "HAS_LOSS", "DONE",
     "Step 1 DONE: cross_entropy_loss + LR warmup/cosine + grad clip. 5 new kernels."),

    ("MetalAttention", "MetalAttention", "HAS_SAVELOAD", "DONE",
     "Step 2 DONE: BCLT format, 125.86MB, save/load bit-identical verified."),

    ("SequenceLunchbox", "MetalAttention", "FEEDS", "DONE",
     "Step 3 DONE: SQTX loader, 273 real BCL sequences, trains on real data."),

    # ── RUNNING: integration steps in progress ──
    ("BclParserC", "MetalAttention", "FEEDS", "RUNNING",
     "Step 4: C parser -> BclNode[] -> Metal buffers. No Python in loop."),

    ("MetalAttention", "MetalAttention", "HAS_INFER", "RUNNING",
     "Step 5: Forward-only + argmax/top-k + BCL output. The moment of truth."),

    ("PantrySystem", "MetalAttention", "FEEDS", "RUNNING",
     "Step 6: VBP1 loader, pantry dir -> Metal streaming."),

    # ── PENDING: not started ──
    ("CorrectionLunchbox", "MetalAttention", "FEEDS", "PENDING",
     "Step 7: Replace train_correction stub with real Metal training."),

    ("MetalAttention", "CoreMlExporter", "FEEDS", "PENDING",
     "Step 8: Export trained weights -> CoreML -> ANE."),

    # ── NEW: BCL IR Graph hub connections (the regraph) ──
    ("BclParserC", "BclIrGraph", "FEEDS", "IR_HUB",
     "C parser produces BclNode[] -> BclIrGraph wraps with computed signals"),

    ("BclIrGraph", "MetalAttention", "FEEDS", "IR_HUB",
     "IR emits Metal buffers: token_ids, pe, mask, domain_ids, graph_bias — all from one parse"),

    ("BclIrGraph", "BclPositionalEncoding", "REPLACES", "IR_HUB",
     "IR computes PE internally. PE component becomes a method on IR, not standalone."),

    ("BclIrGraph", "BclAttentionMask", "REPLACES", "IR_HUB",
     "IR computes mask internally. Mask component becomes a method on IR."),

    ("BclIrGraph", "DomainSparseAttention", "FEEDS", "IR_HUB",
     "IR calls domain routing -> domain_ids. Sparse attention reads from IR."),

    ("BclIrGraph", "GraphAttention", "FEEDS", "IR_HUB",
     "IR calls graph lookup -> graph_bias. Graph attention reads from IR."),

    ("BclIrGraph", "SequenceLunchbox", "FEEDS", "IR_HUB",
     "IR can emit token sequences directly for lunchbox packing. No separate tokenize step."),
]

# ═══════════════════════════════════════════════════════════════
# PHASE 3: BCL IR GRAPH SPEC (the new hub)
# ═══════════════════════════════════════════════════════════════

BCL_IR_SPEC = """
BCL IR GRAPH — INTERMEDIATE REPRESENTATION

THE PROBLEM:
  Today, every component parses BCL independently:
    BclPositionalEncoding  -> calls bcl_engine -> parse -> read depth
    BclAttentionMask       -> calls bcl_engine -> parse -> read parent/children
    DomainSparseAttention  -> calls bcl_engine -> parse -> read class names
    GraphAttention         -> calls bcl_engine -> parse -> read graph edges
    SequenceLunchbox       -> calls bcl_engine -> parse -> read tokens
  = 5 separate parses of the same BCL text.

THE SOLUTION:
  Parse ONCE into BclIrGraph. All components read from IR.

  BCL text
    -> BclParser_Parse() (C, microseconds)
    -> BclNode[256] (depth, parent_idx, children, tag, content)
    -> BclIrGraph_Compute() (one pass over nodes)
    -> BclIrGraph {
         nodes[256]         // original BclNode array
         node_count         // number of nodes
         token_ids[256]     // tag -> vocab hash -> int ID
         pe_matrix[256][384]// depth + path -> sinusoidal -> 384-dim
         mask[256][256]     // parent/children -> 0=attend, 1=block
         domain_ids[256]    // class name -> domain cluster (0-74)
         graph_bias[256][256] // graph edges -> T5-style float bias
       }
    -> BclIrGraph_EmitMetalBuffers() -> 5 MTLBuffers ready for GPU

THE STRUCT (C):
  typedef struct {
      // From parser (existing BclNode)
      BclNode nodes[256];
      int node_count;

      // Computed once (NEW)
      int   token_ids[256];       // vocab hash
      float pe_matrix[256][384];  // positional encoding
      char  mask[256][256];       // attention mask (0/1)
      int   domain_ids[256];      // domain cluster ID
      float graph_bias[256][256]; // graph attention bias
      int   computed;             // 1 = signals computed
  } BclIrGraph;

THE API:
  void BclIrGraph_Init(BclIrGraph* ir);
  int  BclIrGraph_Parse(BclIrGraph* ir, const char* bcl_text);  // parse + compute all
  int  BclIrGraph_ParseNodes(BclIrGraph* ir, BclParseResult* parsed);  // from existing parse
  void BclIrGraph_ComputeTokenIds(BclIrGraph* ir);   // tag -> hash -> ID
  void BclIrGraph_ComputePE(BclIrGraph* ir);         // depth + path -> sinusoidal
  void BclIrGraph_ComputeMask(BclIrGraph* ir);       // parent/children -> mask
  void BclIrGraph_ComputeDomains(BclIrGraph* ir);    // class name -> domain
  void BclIrGraph_ComputeGraphBias(BclIrGraph* ir);  // graph edges -> bias
  void BclIrGraph_EmitMetalBuffers(BclIrGraph* ir, MetalBackend* backend);
  // Emits 5 MTLBuffers: token_ids, pe, mask, domain_ids, graph_bias

WHY THIS MATTERS:
  1. Performance: 1 parse instead of 5. C speed. No Python.
  2. Correctness: All signals from same parse. No inconsistency.
  3. Simplicity: Metal kernel gets all buffers from one source.
  4. Extensibility: Add new signal types to IR without touching consumers.
  5. Native path: BclIrGraph -> Metal buffers -> GPU. No Python in loop.

ANALOGY:
  LLVM IR   -> backends (x86, ARM, GPU) read from one IR
  MLIR      -> dialects compose into one IR
  XLA HLO   -> JAX/TF compile to one IR -> TPU/GPU
  BCL IR    -> components read from one IR -> Metal GPU

IMPLEMENTATION:
  File: core/Dom_Bcl_C_ver/bcl_ir_graph.c (new)
  Header: core/Dom_Bcl_C_ver/bcl_engine.h (add BclIrGraph struct)
  The C parser (bcl_parser.c) is the seed. BclIrGraph wraps it.
  Compute functions are pure C (no Python, no Metal).
  EmitMetalBuffers is in c_transformer_attention.mm (Metal-aware).
"""

# ═══════════════════════════════════════════════════════════════
# PHASE 4: REGRAPHED CRITICAL PATH (BCL IR as Step 0)
# ═══════════════════════════════════════════════════════════════

CRITICAL_PATH = [
    {
        "step": 0,
        "name": "BclIrGraph",
        "title": "Build BCL IR Graph — the central hub",
        "why": "Parse BCL once -> all signals computed -> emit Metal buffers. "
               "Eliminates 5 redundant parses. Makes native path clean. "
               "This is the architecture refactor that makes everything else simpler.",
        "deliverable": "bcl_ir_graph.c + BclIrGraph struct. "
                       "Parse + compute token_ids, pe, mask, domain_ids, graph_bias. "
                       "EmitMetalBuffers -> 5 MTLBuffers.",
        "depends_on": "BclParserC (HAVE), all 5 signal components (BUILT)",
        "status": "NEW — not started",
        "difficulty": "MEDIUM",
    },
    {
        "step": 1,
        "name": "LossAndSchedule",
        "title": "Loss kernel + LR schedule + grad clip",
        "deliverable": "5 new Metal kernels. Loss logged per epoch. LR warmup+cosine. Grad clip.",
        "depends_on": "MetalAttention",
        "status": "DONE",
        "difficulty": "MEDIUM",
    },
    {
        "step": 2,
        "name": "SaveLoadWeights",
        "title": "Save/load fp16 weights (BCLT format)",
        "deliverable": "125.86MB BCLT file. Save/load bit-identical.",
        "depends_on": "Step 1",
        "status": "DONE",
        "difficulty": "EASY",
    },
    {
        "step": 3,
        "name": "RealTrainingData",
        "title": "Load real BCL sequences (SQTX) into Metal",
        "deliverable": "SQTX loader. 273 real BCL sequences. Trains on real data.",
        "depends_on": "Step 2",
        "status": "DONE",
        "difficulty": "EASY",
    },
    {
        "step": 4,
        "name": "NativeCPath",
        "title": "C parser -> Metal buffers (no Python)",
        "deliverable": "bcl_parser.c -> BclNode[] -> Metal. Native training loop.",
        "depends_on": "Step 3, Step 0 (BCL IR makes this cleaner)",
        "status": "RUNNING",
        "difficulty": "MEDIUM",
    },
    {
        "step": 5,
        "name": "InferenceMode",
        "title": "BCL input -> model -> BCL output",
        "deliverable": "Forward-only + argmax/top-k + token output. The moment of truth.",
        "depends_on": "Step 4, Step 2",
        "status": "RUNNING",
        "difficulty": "MEDIUM",
    },
    {
        "step": 6,
        "name": "PantryToGpu",
        "title": "Stream sealed batches from Pantry to Metal",
        "deliverable": "VBP1 loader. Pantry dir -> Metal streaming.",
        "depends_on": "Step 3, Step 4",
        "status": "RUNNING (retry)",
        "difficulty": "EASY",
    },
    {
        "step": 7,
        "name": "CorrectionTrainWire",
        "title": "Wire correction system to Metal (surgical retraining)",
        "deliverable": "Replace stubs. Error -> 5000 pair lunchbox -> 0.01s GPU -> verify.",
        "depends_on": "Step 5 (inference for verify), Step 2 (save/load)",
        "status": "PENDING",
        "difficulty": "MEDIUM",
    },
    {
        "step": 8,
        "name": "CoreMlDeploy",
        "title": "Export to Apple Neural Engine",
        "deliverable": "BclTransformer.mlpackage. ANE-optimized. On-device inference.",
        "depends_on": "Step 5, Step 2",
        "status": "PENDING",
        "difficulty": "MEDIUM",
    },
]

# ═══════════════════════════════════════════════════════════════
# PHASE 5: THE REGRAPHED END STATE
# ═══════════════════════════════════════════════════════════════

END_STATE = """
BCL TRANSFORMER — REGRAPHED END STATE

THE NATIVE STACK (with BCL IR):

  BCL text
    -> BclParser_Parse() (C, microseconds)
    -> BclNode[256] (depth, parent_idx, children, tag)
    -> BclIrGraph_Compute() (ONE PASS — all signals)
         -> token_ids[256]     (tag -> vocab hash -> ID)
         -> pe_matrix[256][384] (depth + path -> sinusoidal)
         -> mask[256][256]     (parent/children -> 0/1)
         -> domain_ids[256]    (class name -> domain 0-74)
         -> graph_bias[256][256] (graph edges -> T5 bias)
    -> BclIrGraph_EmitMetalBuffers() -> 5 MTLBuffers
    -> Metal: 24 kernels, 6 layers, fp16
         -> forward (Q/K/V -> attention -> softmax -> V -> FFN -> LN)
         -> loss (cross-entropy)
         -> backward (all gradients)
         -> grad clip (max_norm=1.0)
         -> SGD update (LR warmup + cosine decay)
    -> save weights (BCLT, 125MB)
    -> OR: inference (forward-only -> argmax -> BCL output)

  ONE PARSE. ONE IR. FIVE BUFFERS. ZERO PYTHON.

TRAINING:
  1. Chat logs -> BclChatCompressor -> BCL text
  2. BCL text -> SequenceLunchbox -> SQTX .bin (or BclIrGraph direct)
  3. SQTX -> PantrySystem -> sealed batches
  4. Sealed batches -> BclIrGraph -> Metal buffers -> 24 kernels -> train
  5. Loss logged. LR scheduled. Grads clipped. Weights checkpointed.

INFERENCE:
  1. BCL input -> BclIrGraph -> Metal buffers
  2. Forward-only (no backward, no SGD)
  3. Argmax / top-k / temperature sampling
  4. Token IDs -> BCL text output
  5. BCL output -> resolve references -> story

CORRECTION:
  1. ErrorTracker detects pattern (100 occurrences)
  2. CorrectionLunchbox fires -> 5000 pair lunchbox (29KB)
  3. Load model -> surgical train -> save
  4. Verify: inference on error case -> confirm fixed
  5. Log to MySQL correction_history

DEPLOYMENT:
  1. Trained weights -> CoreMlExporter
  2. PyTorch -> CoreML -> ANE-optimized .mlpackage
  3. On-device inference on Apple Neural Engine

BCL IS THE TOKEN SPACE.
BCL IR IS THE HUB.
20x COMPRESSION. O(N) ATTENTION. ONE PARSE. WE ARE US.
"""

# ═══════════════════════════════════════════════════════════════
# PHASE 6: METRICS
# ═══════════════════════════════════════════════════════════════

METRICS = {
    # Components
    "components_built": 10,
    "components_tested": 10,
    "components_passing": 10,
    "foundations_have": 9,
    "new_nodes": 1,  # BclIrGraph
    "total_nodes": 20,
    # Edges
    "edges_wired": 7,
    "edges_done": 3,  # Steps 1-3
    "edges_running": 3,  # Steps 4-6
    "edges_pending": 2,  # Steps 7-8
    "edges_ir_hub": 7,  # BCL IR connections
    # Steps
    "steps_done": 3,
    "steps_running": 3,
    "steps_pending": 2,
    "steps_new": 1,  # BCL IR (Step 0)
    "total_steps": 9,  # 0-8
    # Metal
    "metal_kernels": 24,
    "metal_layers": 6,
    "metal_seq_256_10ep_s": 2.9,
    "metal_seq_512_5ep_s": 6.28,
    "weight_file_mb": 125.86,
    # Data
    "rules_available": 10605,
    "domains_available": 75,
    "vocab_size": 162612,
    "real_sequences_loaded": 273,
    # Model
    "d_model": 384,
    "n_heads": 6,
    "n_layers": 6,
    "max_seq_len": 2048,
    "precision": "fp16 storage + float32 accumulation",
    "hardware": "Apple M1",
    # BCL IR
    "bcl_ir_signals": 5,  # token_ids, pe, mask, domain_ids, graph_bias
    "bcl_ir_parses_eliminated": 5,  # was 5 separate parses, now 1
    "bcl_ir_buffers_emitted": 5,  # MTLBuffers
}
