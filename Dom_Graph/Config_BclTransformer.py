#!/usr/bin/env python3
#[@GHOST]{[@date<2026-07-02>][@author<cascade>][@session<bcl_transformer_design>]}
#[@VBSTYLE]{[@fileid<Config_BclTransformer>][@summary<Graph of BCL Transformer vision — 10 components mapped to concrete nodes and edges>][@class<Config>][@method<graph_data>]}
"""
BCL Transformer Vision Graph
Maps the 10-point vision to concrete graph nodes + edges.
Consumed by gap analysis: what we HAVE vs what we NEED.
"""

DOMAIN_NAME = "BclTransformer"
DOMAIN_FILE = "Config_BclTransformer.py"
DOMAIN_SUMMARY = "Domain-specific transformer that knows OUR world — BCL, code, rules, architecture"

# ─── Nodes: the 10 vision components ──────────────────────────────────────────
# (name, status, methods, description)
# status: "HAVE" = exists and works, "PARTIAL" = exists but incomplete, "NEED" = must build

GRAPH_CLASSES = [
    # ── Foundation (what we stand on) ──
    ("VbEngineEmbedding", "HAVE",
     ["train", "save", "load", "query", "export"],
     "384-dim word2vec SGNS on Metal. 214M pairs/s. Production. File: c_word2vec_metal_packed.mm"),

    ("BclParser", "HAVE",
     ["lex", "parse", "validate", "fix", "serialize", "walk"],
     "BCL lexer + parser + engine. 4 symbols, AST tree, depth tracking. Files: bcl_lexer.py, bcl_parser.py, bcl_engine.py"),

    ("MetalGpt2Kernels", "HAVE",
     ["matmul", "attention_scores", "softmax", "layer_norm", "gelu", "embedding_lookup"],
     "GPT-2 Metal kernels in backup folder. matmul, attention, softmax, layernorm, GELU. Files: 00007_GPT2_Metal_Kernels.metal, 04227_Kernels_GPT2.metal"),

    ("LearnedRules", "HAVE",
     ["search", "create", "update", "delete", "match", "rank"],
     "10,540 pattern->fix rules in MySQL vb_shared.learned_rules. confidence scored. 4 rule engines exist"),

    ("DomainGraph", "HAVE",
     ["route", "cluster", "expand", "closure"],
     "75 domains in MySQL vb_shared.domains. 767/1445 classes routed. domain_closure recursive CTE"),

    ("EightGraphs", "PARTIAL",
     ["plan", "spec", "flow", "lifecycle", "dep", "error", "orch", "gap"],
     "8 graph viewers. 9 edge types. Hardcoded in Config.py. SQL schema designed but not wired to DB"),

    ("RuleEngines", "HAVE",
     ["match", "track", "learn", "apply", "verify"],
     "ErrorTracker, Dom_Graph_Agent, Efi_ram_ai, bcl_pattern_db. All connected to MySQL. All query learned_rules"),

    # ── Transformer components (what we need to build) ──
    ("BclPositionalEncoding", "NEED",
     ["encode_depth", "encode_path", "encode_container_type"],
     "Container depth (0-256) + path position + container type as positional encoding. Replaces sinusoidal PE"),

    ("BclAttentionMask", "NEED",
     ["container_mask", "hands_mask", "array_mask"],
     "BCL containers as attention masks. Token attends only to siblings in same container. O(N) not O(N^2)"),

    ("GraphAttention", "NEED",
     ["edge_mask", "follow_edge", "lifecycle_phase_mask"],
     "8 graphs guide attention. FEEDS edges = forward attention. PAIRS edges = bidirectional. TRIGGERS = causal"),

    ("DomainSparseAttention", "NEED",
     ["cluster_attention", "cross_domain_mask", "domain_routing"],
     "75 domains as sparse attention clusters. Token attends to same-domain tokens fully, cross-domain sparsely"),

    ("SequenceLunchbox", "NEED",
     ["bcl_to_sequence", "code_to_sequence", "rule_to_sequence", "pack"],
     "Convert BCL packets, code, rules into input->target token sequences. The LLM lunchbox (not word pairs)"),

    ("RuleLunchbox", "NEED",
     ["pattern_to_sequence", "fix_to_sequence", "threshold_check", "pack"],
     "Convert 10,540 learned rules into training sequences. pattern = input, fix_action = target. Fires at threshold"),

    ("PantrySystem", "NEED",
     ["append", "seal", "list", "compact", "load_manifest"],
     "Versioned append-only training cache. LMDB. Immutable sealed batches. Multiple recipes coexist"),

    ("MetalAttention", "NEED",
     ["forward", "backward", "multi_head", "causal_mask", "gradient_update"],
     "Adapt GPT-2 Metal kernels for BCL transformer. Q/K/V projection, multi-head, backprop, SGD"),

    ("CorrectionLunchbox", "NEED",
     ["detect", "threshold", "build_correction", "surgical_train", "verify", "log_outcome"],
     "Surgical retraining. Error pattern hits 100 occurrences -> 5000 pair lunchbox -> 0.01s GPU train -> fix"),

    ("CoreMlExporter", "NEED",
     ["export_weights", "convert_attention", "compile_model", "deploy_ane"],
     "Export trained transformer to CoreML for Apple Neural Engine deployment"),
]

# ─── Edges: how components connect ────────────────────────────────────────────
# (src, dst, edge_type)
# Edge types: FEEDS (data flows), USES (calls), ENABLES (unlocks), WRAPS (orchestrates),
#             TRIGGERS (causes), PAIRS (bidirectional), BUILDS (constructs from)

GRAPH_EDGES = [
    # ── Foundation -> Transformer (data flows up) ──
    ("VbEngineEmbedding", "MetalAttention", "FEEDS"),
    ("BclParser", "BclPositionalEncoding", "FEEDS"),
    ("BclParser", "BclAttentionMask", "FEEDS"),
    ("MetalGpt2Kernels", "MetalAttention", "FEEDS"),
    ("LearnedRules", "RuleLunchbox", "FEEDS"),
    ("DomainGraph", "DomainSparseAttention", "FEEDS"),
    ("EightGraphs", "GraphAttention", "FEEDS"),

    # ── Transformer internal wiring ──
    ("BclPositionalEncoding", "MetalAttention", "FEEDS"),
    ("BclAttentionMask", "MetalAttention", "ENABLES"),
    ("GraphAttention", "MetalAttention", "ENABLES"),
    ("DomainSparseAttention", "MetalAttention", "ENABLES"),

    # ── Training pipeline ──
    ("SequenceLunchbox", "PantrySystem", "FEEDS"),
    ("RuleLunchbox", "PantrySystem", "FEEDS"),
    ("PantrySystem", "MetalAttention", "FEEDS"),

    # ── Correction loop ──
    ("RuleEngines", "CorrectionLunchbox", "TRIGGERS"),
    ("CorrectionLunchbox", "PantrySystem", "FEEDS"),
    ("CorrectionLunchbox", "RuleEngines", "FEEDS"),

    # ── Deployment ──
    ("MetalAttention", "CoreMlExporter", "FEEDS"),

    # ── Wrapping (orchestration) ──
    ("MetalAttention", "GraphAttention", "USES"),
    ("MetalAttention", "DomainSparseAttention", "USES"),
    ("PantrySystem", "CorrectionLunchbox", "WRAPS"),
]

# ─── Gap Analysis: HAVE vs NEED ───────────────────────────────────────────────

GAP_ANALYSIS = {
    "HAVE": [
        ("VbEngineEmbedding", "c_word2vec_metal_packed.mm", "Production. 384-dim. 214M pairs/s. fp16+half4"),
        ("BclParser", "bcl_lexer.py + bcl_parser.py + bcl_engine.py", "Full LEX->PARSE->VALIDATE->FIX->SERIALIZE pipeline"),
        ("MetalGpt2Kernels", "00007_GPT2_Metal_Kernels.metal", "matmul, attention, softmax, layernorm, GELU. Ready to adapt"),
        ("LearnedRules", "vb_shared.learned_rules", "10,540 rules. pattern->fix_action. confidence scored. 4 engines"),
        ("DomainGraph", "vb_shared.domains", "75 domains. 767 classes routed. domain_closure CTE"),
        ("RuleEngines", "ErrorTracker + Dom_Graph_Agent + Efi_ram_ai + bcl_pattern_db", "All query learned_rules. All track success/failure"),
    ],
    "PARTIAL": [
        ("EightGraphs", "Dom_Graph_*.py", "8 viewers exist. Hardcoded data. SQL schema designed but not wired"),
    ],
    "NEED": [
        ("BclPositionalEncoding", "NEW", "Container depth + path + type as positional encoding. No sinusoidal PE"),
        ("BclAttentionMask", "NEW", "Containers as attention masks. O(N) complexity. Sibling-only attention"),
        ("GraphAttention", "NEW", "8 graph edge types as attention guides. FEEDS=forward, PAIRS=bidirectional"),
        ("DomainSparseAttention", "NEW", "75 domains as sparse clusters. Same-domain full, cross-domain sparse"),
        ("SequenceLunchbox", "NEW", "BCL packets + code + rules -> input/target token sequences"),
        ("RuleLunchbox", "NEW", "10,540 rules -> training sequences. pattern=input, fix=target"),
        ("PantrySystem", "NEW", "LMDB versioned cache. Immutable batches. Append-only. Multiple recipes"),
        ("MetalAttention", "NEW", "Adapt GPT-2 kernels. Q/K/V, multi-head, backprop, SGD. The attention kernel"),
        ("CorrectionLunchbox", "NEW", "Surgical retraining. 100 occurrences -> 5000 pair lunchbox -> 0.01s GPU"),
        ("CoreMlExporter", "NEW", "Trained model -> CoreML -> Apple Neural Engine"),
    ],
}

# ─── Build order: what to build first ─────────────────────────────────────────
# Each step depends on the previous

BUILD_ORDER = [
    (1, "MetalAttention",
     "Adapt GPT-2 kernels. Add Q/K/V projection, multi-head split, backprop, SGD gradient update.",
     "depends_on: MetalGpt2Kernels, VbEngineEmbedding"),
    (2, "BclPositionalEncoding",
     "Map container depth (0-256) to positional encoding vector. Add to token embeddings before attention.",
     "depends_on: BclParser, MetalAttention"),
    (3, "BclAttentionMask",
     "Generate attention mask from BCL AST. Token attends only to siblings in same container.",
     "depends_on: BclParser, MetalAttention"),
    (4, "SequenceLunchbox",
     "Convert BCL packets to input->target token sequences. The LLM lunchbox format.",
     "depends_on: BclParser, VbEngineEmbedding"),
    (5, "PantrySystem",
     "LMDB versioned cache. Seal sequence lunchboxes as immutable batches.",
     "depends_on: SequenceLunchbox"),
    (6, "DomainSparseAttention",
     "Wire 75 domains as sparse attention clusters. Same-domain full attention, cross-domain sparse.",
     "depends_on: DomainGraph, MetalAttention"),
    (7, "GraphAttention",
     "Wire 8 graphs as attention guides. FEEDS=forward, PAIRS=bidirectional, TRIGGERS=causal.",
     "depends_on: EightGraphs, MetalAttention"),
    (8, "RuleLunchbox",
     "Convert 10,540 learned rules to training sequences. pattern=input, fix=target.",
     "depends_on: LearnedRules, SequenceLunchbox"),
    (9, "CorrectionLunchbox",
     "Surgical retraining. Error hits threshold -> tiny lunchbox -> 0.01s GPU train -> verify -> log.",
     "depends_on: RuleEngines, PantrySystem, MetalAttention"),
    (10, "CoreMlExporter",
     "Export trained transformer to CoreML. Deploy on Apple Neural Engine.",
     "depends_on: MetalAttention"),
]
