"""
cognition_fabric.py — Multi-provider execution fabric with parallel fanout,
normalized response nodes, SQLite caching, and cognitive merge engine.

Architecture:
  L1 Transport  — providers (gemini, msearch, local, web)
  L2 Extraction — raw output from each provider
  L3 Normalization — convert to unified node schema
  L4 Merge Engine — dedup, cluster, conflict detection, coverage scoring
  L5 Cache — SQLite, hash prompt → stored results

Usage:
  python3 cognition_fabric.py "your query"
  python3 cognition_fabric.py --providers gemini,msearch "query"
  python3 cognition_fabric.py --all "query"          # fanout to all providers
  python3 cognition_fabric.py --json "query"          # JSON output
  python3 cognition_fabric.py --cache-stats            # show cache stats
  python3 cognition_fabric.py --no-cache "query"      # bypass cache
"""

import subprocess
import sys
import os
import json
import time
import hashlib
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FABRIC_DIR = Path(__file__).parent
CACHE_DB = FABRIC_DIR / "cognition_cache.db"
MSEARCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/msearch"
GEMINI_SCRIPT = str(FABRIC_DIR / "gemini_cli.py")

# ---------------------------------------------------------------------------
# Unified Node Schema
# ---------------------------------------------------------------------------

def make_node(source, content, content_type="explanation", confidence=0.5,
              raw=None, metadata=None):
    """Create a normalized response node."""
    return {
        "node_id": str(uuid4()),
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": content,
        "content_type": content_type,  # code | explanation | fact | suggestion | search_results
        "confidence": confidence,      # 0.0-1.0, system-determined
        "trace_id": str(uuid4()),
        "raw": raw if raw is not None else content,
        "metadata": metadata or {},
    }


# ---------------------------------------------------------------------------
# L1: Transport Layer — Providers
# ---------------------------------------------------------------------------

def provider_gemini(query):
    """Call Gemini via browser automation."""
    try:
        result = subprocess.run(
            [sys.executable, GEMINI_SCRIPT, query],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return make_node("gemini", f"[ERROR] {result.stderr.strip()}", "error", 0.0)
        text = result.stdout.strip()
        if not text:
            return make_node("gemini", "[EMPTY]", "error", 0.0)
        return make_node("gemini", text, "explanation", 0.8, raw=text)
    except subprocess.TimeoutExpired:
        return make_node("gemini", "[TIMEOUT]", "error", 0.0)
    except Exception as e:
        return make_node("gemini", f"[ERROR] {e}", "error", 0.0)


def provider_msearch(query):
    """Call local magnetic search engine."""
    try:
        result = subprocess.check_output([MSEARCH_BIN, query], text=True, timeout=30)
        if not result.strip():
            return make_node("msearch", "[NO MATCHES]", "search_results", 0.3)
        return make_node("msearch", result.strip(), "search_results", 0.9, raw=result.strip(),
                         metadata={"engine": "msearch3"})
    except subprocess.TimeoutExpired:
        return make_node("msearch", "[TIMEOUT]", "error", 0.0)
    except Exception as e:
        return make_node("msearch", f"[ERROR] {e}", "error", 0.0)


def provider_local(query):
    """Local echo — test provider."""
    return make_node("local", f"[LOCAL_ECHO] {query}", "explanation", 0.1)


PROVIDERS = {
    "gemini": provider_gemini,
    "msearch": provider_msearch,
    "local": provider_local,
}


# ---------------------------------------------------------------------------
# L5: Cache Layer
# ---------------------------------------------------------------------------

def init_cache():
    """Initialize SQLite cache."""
    db = sqlite3.connect(str(CACHE_DB))
    db.execute("""
        CREATE TABLE IF NOT EXISTS query_cache (
            prompt_hash TEXT PRIMARY KEY,
            prompt TEXT,
            provider TEXT,
            node_json TEXT,
            created_at TEXT,
            hit_count INTEGER DEFAULT 0
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS cache_stats (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    db.commit()
    db.close()


def hash_prompt(prompt, provider):
    """Hash prompt + provider for cache key."""
    return hashlib.sha256(f"{provider}:{prompt}".encode()).hexdigest()[:16]


def cache_get(prompt, provider):
    """Get cached result for prompt+provider. Returns node dict or None."""
    db = sqlite3.connect(str(CACHE_DB))
    h = hash_prompt(prompt, provider)
    row = db.execute(
        "SELECT node_json FROM query_cache WHERE prompt_hash=?", (h,)
    ).fetchone()
    if row:
        db.execute("UPDATE query_cache SET hit_count = hit_count + 1 WHERE prompt_hash=?", (h,))
        db.commit()
        db.close()
        return json.loads(row[0])
    db.close()
    return None


def cache_put(prompt, provider, node):
    """Store result in cache."""
    db = sqlite3.connect(str(CACHE_DB))
    h = hash_prompt(prompt, provider)
    db.execute(
        "INSERT OR REPLACE INTO query_cache (prompt_hash, prompt, provider, node_json, created_at, hit_count) VALUES (?, ?, ?, ?, ?, 0)",
        (h, prompt, provider, json.dumps(node), datetime.now(timezone.utc).isoformat())
    )
    db.commit()
    db.close()


def cache_stats():
    """Print cache statistics."""
    db = sqlite3.connect(str(CACHE_DB))
    rows = db.execute("SELECT provider, COUNT(*), SUM(hit_count) FROM query_cache GROUP BY provider").fetchall()
    total = db.execute("SELECT COUNT(*), SUM(hit_count) FROM query_cache").fetchone()
    db.close()
    print(f"Cache: {CACHE_DB}")
    print(f"Total entries: {total[0]}, Total hits: {total[1] or 0}")
    for provider, count, hits in rows:
        print(f"  {provider}: {count} entries, {hits or 0} hits")


# ---------------------------------------------------------------------------
# L2+L3: Fanout Execution with Normalization
# ---------------------------------------------------------------------------

def fanout(query, provider_names, use_cache=True):
    """Execute providers in parallel, return list of normalized nodes."""
    nodes = []

    with ThreadPoolExecutor(max_workers=len(provider_names)) as executor:
        future_to_provider = {}
        for name in provider_names:
            if name not in PROVIDERS:
                print(f"[WARN] Unknown provider: {name}, skipping")
                continue

            # Check cache first
            if use_cache:
                cached = cache_get(query, name)
                if cached:
                    cached["metadata"]["cache_hit"] = True
                    nodes.append(cached)
                    continue

            future = executor.submit(PROVIDERS[name], query)
            future_to_provider[future] = name

        for future in as_completed(future_to_provider):
            name = future_to_provider[future]
            try:
                node = future.result()
                if use_cache and node.get("content_type") != "error":
                    cache_put(query, name, node)
                nodes.append(node)
            except Exception as e:
                nodes.append(make_node(name, f"[FANOUT ERROR] {e}", "error", 0.0))

    return nodes


# ---------------------------------------------------------------------------
# L4: Cognitive Merge Engine
# ---------------------------------------------------------------------------

def merge_nodes(nodes):
    """Merge normalized nodes into a unified cognitive map."""
    if not nodes:
        return {"nodes": [], "summary": "[NO RESULTS]", "conflicts": [], "coverage": {}}

    # Step 1: Deduplication — remove nodes with identical content
    seen_content = set()
    deduped = []
    for node in nodes:
        content_key = node["content"].strip().lower()[:200]
        if content_key not in seen_content:
            seen_content.add(content_key)
            deduped.append(node)
        else:
            node["metadata"]["deduped"] = True

    # Step 2: Clustering — group by source
    clusters = {}
    for node in deduped:
        src = node["source"]
        if src not in clusters:
            clusters[src] = []
        clusters[src].append(node)

    # Step 3: Conflict detection — flag errors and disagreements
    conflicts = []
    error_nodes = [n for n in deduped if n["content_type"] == "error"]
    for n in error_nodes:
        conflicts.append({
            "type": "provider_error",
            "source": n["source"],
            "content": n["content"],
        })

    # Step 4: Coverage scoring
    total_providers = len(PROVIDERS)
    active_providers = len(clusters)
    coverage = {
        "providers_active": list(clusters.keys()),
        "providers_total": total_providers,
        "coverage_ratio": active_providers / total_providers if total_providers > 0 else 0,
        "error_count": len(error_nodes),
        "success_count": len(deduped) - len(error_nodes),
        "cache_hits": sum(1 for n in deduped if n.get("metadata", {}).get("cache_hit")),
    }

    # Build summary
    successful = [n for n in deduped if n["content_type"] != "error"]
    if successful:
        sources = [n["source"] for n in successful]
        summary = f"Merged {len(successful)} responses from: {', '.join(sources)}"
    else:
        summary = "[ALL PROVIDERS FAILED]"

    return {
        "query": nodes[0].get("metadata", {}).get("query", "") if nodes else "",
        "nodes": deduped,
        "clusters": {k: len(v) for k, v in clusters.items()},
        "conflicts": conflicts,
        "coverage": coverage,
        "summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Output Formatters
# ---------------------------------------------------------------------------

def print_text(merged):
    """Human-readable output."""
    print(f"\n{'='*60}")
    print(f"COGNITION FABRIC — {merged['summary']}")
    print(f"{'='*60}\n")

    for node in merged["nodes"]:
        if node.get("metadata", {}).get("deduped"):
            continue
        source = node["source"].upper()
        ctype = node["content_type"]
        conf = node["confidence"]
        cache_hit = " [CACHED]" if node.get("metadata", {}).get("cache_hit") else ""
        print(f"--- [{source}] ({ctype}, conf={conf}){cache_hit} ---")
        content = node["content"]
        if len(content) > 500:
            print(content[:500] + "\n... [truncated]")
        else:
            print(content)
        print()

    cov = merged["coverage"]
    print(f"{'─'*60}")
    print(f"Coverage: {cov['providers_active']} | Errors: {cov['error_count']} | "
          f"Success: {cov['success_count']} | Cache hits: {cov['cache_hits']}")

    if merged["conflicts"]:
        print(f"Conflicts: {len(merged['conflicts'])}")
        for c in merged["conflicts"]:
            print(f"  ! [{c['source']}] {c['content'][:80]}")


def print_json(merged):
    """JSON output."""
    print(json.dumps(merged, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# CLI Entry
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Cognition Fabric — multi-provider parallel query system"
    )
    parser.add_argument("query", nargs="*", help="Your query")
    parser.add_argument("--providers", "-p", default="gemini",
                        help="Comma-separated providers (default: gemini)")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Fanout to all providers")
    parser.add_argument("--json", "-j", action="store_true",
                        help="JSON output")
    parser.add_argument("--no-cache", action="store_true",
                        help="Bypass cache")
    parser.add_argument("--cache-stats", action="store_true",
                        help="Show cache statistics")
    args = parser.parse_args()

    init_cache()

    if args.cache_stats:
        cache_stats()
        return

    if not args.query:
        parser.print_help()
        return

    query = " ".join(args.query)

    if args.all:
        provider_names = list(PROVIDERS.keys())
    else:
        provider_names = [p.strip() for p in args.providers.split(",")]

    start = time.time()
    nodes = fanout(query, provider_names, use_cache=not args.no_cache)
    merged = merge_nodes(nodes)
    elapsed = time.time() - start

    merged["query"] = query
    merged["elapsed_seconds"] = round(elapsed, 2)

    if args.json:
        print_json(merged)
    else:
        print_text(merged)
        print(f"Time: {elapsed:.2f}s\n")


if __name__ == "__main__":
    main()
