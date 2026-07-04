import sqlite3, json, time

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/online_projects.db"

db = sqlite3.connect(DB_PATH)
db.execute("""CREATE TABLE IF NOT EXISTS code_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT,
    file_path TEXT,
    line_count INTEGER,
    language TEXT,
    purpose TEXT,
    key_techniques TEXT,
    useful_for TEXT,
    analysis TEXT,
    analyzed_at TEXT
)""")

analyses = [
    {
        "project": "Rapid-MLX",
        "file": "vllm_mlx/server.py",
        "lines": 2196,
        "lang": "Python",
        "purpose": "OpenAI-compatible FastAPI server for MLX LLM inference on Apple Silicon",
        "techniques": "FastAPI, streaming responses, MCP tool integration, continuous batching, multimodal (text+image+video)",
        "useful": "Drop-in local OpenAI API replacement. Could replace Gemini browser hack with localhost:8000/v1/chat/completions",
        "analysis": "2196 lines. Full OpenAI API server. Supports /v1/completions, /v1/chat/completions, /v1/models, /v1/embeddings, MCP tools. Two modes: simple (max throughput single user) and batched (continuous batching multi-user). Uses mlx-lm for text, mlx-vlm for multimodal. This is the piece the user does not have yet."
    },
    {
        "project": "Rapid-MLX",
        "file": "vllm_mlx/prefix_cache.py",
        "lines": 1184,
        "lang": "Python",
        "purpose": "Prefix cache manager — reuses computed KV cache for common prompt prefixes",
        "techniques": "LRU cache, trie-based prefix matching, block-aware paged cache, KV cache sharing, reference counting",
        "useful": "0.08s cached TTFT. If user sends similar prompts repeatedly (like cognition fabric queries), this skips recompute. Could make local LLM faster than msearch for repeated queries.",
        "analysis": "1184 lines. Two implementations: PrefixCacheManager (trie-based LRU) and BlockAwarePrefixCache (block-based with PagedCacheManager). Tracks hits, misses, tokens_saved, evictions. The prefix cache is why Rapid-MLX gets 0.08s TTFT — it skips recomputing tokens it already computed for a previous similar prompt."
    },
    {
        "project": "Rapid-MLX",
        "file": "vllm_mlx/embedding.py",
        "lines": 210,
        "lang": "Python",
        "purpose": "Embedding engine using mlx-embeddings for /v1/embeddings endpoint",
        "techniques": "Lazy model loading, mlx-embeddings, batch embedding, OpenAI-compatible embedding API",
        "useful": "User already has MLX embedding models (BGE-small, BGE-M3, All-MiniLM-L6-v2). This file shows how to serve them as an API. Could replace manual embedding code.",
        "analysis": "210 lines. Simple wrapper around mlx_embeddings. Lazy loads model on first request. Provides /v1/embeddings endpoint. User already has the models downloaded, just needs this serving layer."
    },
    {
        "project": "Rapid-MLX",
        "file": "vllm_mlx/tool_parsers/",
        "lines": 14076,
        "lang": "Python",
        "purpose": "17 tool parsers for different LLM formats (Qwen, Llama, DeepSeek, Mistral, etc)",
        "techniques": "Per-model tool call parsing, function calling, structured output extraction",
        "useful": "If user wants local LLM to call tools (like msearch, cognition fabric), these parsers handle the parsing. User has Qwen model already.",
        "analysis": "17 parsers total. Each handles a different LLM's tool calling format. Qwen parser is relevant since user has Qwen 2.5 Coder downloaded. DeepSeek parser for reasoning models. This is the tool calling layer that turns an LLM from a chatbot into an agent."
    },
    {
        "project": "LEANN",
        "file": "leann-core/src/leann/api.py",
        "lines": 1795,
        "lang": "Python",
        "purpose": "Core RAG API — add text, compute embeddings, search, chat",
        "techniques": "Multiple embedding backends (sentence-transformers, MLX, OpenAI, Gemini), HNSW backend, metadata filtering, passage ID schemes",
        "useful": "User's msearch already does this faster in C. But LEANN's multi-backend embedding approach (switch between MLX, OpenAI, Gemini) is a clean pattern worth studying.",
        "analysis": "1795 lines. The core RAG pipeline. compute_embeddings() supports 4 backends: sentence-transformers, MLX, OpenAI, Gemini. Uses HNSW for graph-based search. Has metadata filtering. The passage ID scheme (sequential vs content-hash) is clever — content-hash IDs survive file reordering. But fundamentally this is what msearch already does, just slower because Python."
    },
    {
        "project": "LEANN",
        "file": "leann-core/src/leann/embedding_compute.py",
        "lines": 1452,
        "lang": "Python",
        "purpose": "Unified embedding computation with multiple model support",
        "techniques": "Token limit registry, dynamic token discovery, lazy torch import, batch encoding, MLX backend",
        "useful": "The token limit registry (EMBEDDING_MODEL_LIMITS dict) is useful. User could use this to know max token lengths for their models without trial and error.",
        "analysis": "1452 lines. Heavy. Imports torch lazily to avoid 1GB memory overhead. Has a hardcoded token limit registry for common models: bge-m3=8192, all-minilm=512, nomic-embed-text=2048. Dynamic discovery via Ollama /api/show. This is overengineered for what user needs — user already knows their model limits."
    },
    {
        "project": "LEANN",
        "file": "leann-core/src/leann/searcher_base.py",
        "lines": 232,
        "lang": "Python",
        "purpose": "Abstract base class for search backends",
        "techniques": "Embedding server manager, metadata loading, daemon TTL, warmup",
        "useful": "The daemon pattern (embedding server stays alive for 900s between queries) is smart. User could use this for msearch — keep the DB connection alive instead of reopening.",
        "analysis": "232 lines. Clean abstract class. Key insight: EmbeddingServerManager keeps an embedding server running as a daemon with 900s TTL. This avoids cold-start latency on repeated queries. User's msearch already does this implicitly (DB stays open), but the explicit daemon pattern is worth noting."
    },
    {
        "project": "ANEMLL",
        "file": "anemll/ane_converter/llama_converter.py",
        "lines": 1593,
        "lang": "Python",
        "purpose": "Converts Llama PyTorch models to CoreML format for Apple Neural Engine",
        "techniques": "coremltools, LUT quantization (4-bit), per-channel quantization, chunked ANE segments, unified KV cache",
        "useful": "If user wants to run Llama on Neural Engine instead of GPU, this is the conversion pipeline. User already has ANEMLL models downloaded but this shows HOW they were made.",
        "analysis": "1593 lines. Uses coremltools to convert PyTorch Llama to CoreML. Key: LUT quantization with 4-bit lookup tables, per-channel quantization with 8 channels. Chunks model into ANE-friendly segments. Unified KV cache for state management. This is the compiler pipeline that makes LLMs run on the Neural Engine."
    },
    {
        "project": "ANEMLL",
        "file": "anemll/models/llama_model.py",
        "lines": 1450,
        "lang": "Python",
        "purpose": "Llama model architecture reimplemented for CoreML/ANE",
        "techniques": "PyTorch reimplementation with ANE-specific ops, Conv2d for LM head, vocab splitting (2-way and 8-way), unified KV cache, float16 only",
        "useful": "Shows the specific architectural changes needed for ANE: Conv2d instead of Linear for LM head, vocabulary splitting to avoid ANE tensor limits, forced float16. These are hardware constraints user would hit if trying ANE.",
        "analysis": "1450 lines. Pure PyTorch but modified for ANE. Key ANE constraints: float16 only (MODEL_DTYPE), Conv2d for LM head (ENABLE_CONV2D), vocabulary split into 2 or 8 parts (ANE tensor size limit), unified KV cache (FORCE_UNIFIED_CACHE). These are the hardware-specific hacks needed to make LLMs work on Neural Engine. User would need these if they ever target ANE."
    },
    {
        "project": "ANEMLL",
        "file": "anemll/ane_converter/qwen_converter.py",
        "lines": 1593,
        "lang": "Python",
        "purpose": "Converts Qwen models to CoreML for ANE — directly relevant to user's Qwen 2.5 model",
        "techniques": "Same as Llama converter but adapted for Qwen architecture",
        "useful": "User has Qwen 2.5 Coder 1.5B downloaded. This converter could turn it into a CoreML model that runs on Neural Engine instead of GPU. Lower power, background execution.",
        "analysis": "1593 lines. Qwen-specific converter. User has mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit in HuggingFace cache. This converter could transform it to CoreML/ANE format. Would enable low-power background LLM execution on Neural Engine instead of GPU."
    },
]

for a in analyses:
    db.execute(
        "INSERT INTO code_analysis (project_name, file_path, line_count, language, purpose, key_techniques, useful_for, analysis, analyzed_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (a["project"], a["file"], a["lines"], a["lang"], a["purpose"], a["techniques"], a["useful"], a["analysis"], time.strftime("%Y-%m-%d %H:%M:%S")),
    )

db.commit()

count = db.execute("SELECT COUNT(*) FROM code_analysis").fetchone()[0]
print(f"Saved {count} code analyses to online_projects.db")

for row in db.execute("SELECT project_name, file_path, line_count FROM code_analysis ORDER BY project_name, file_path").fetchall():
    print(f"  {row[0]:12s} | {row[1]:50s} | {row[2]} lines")

db.close()
