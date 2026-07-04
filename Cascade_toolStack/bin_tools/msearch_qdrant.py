#!/usr/bin/env python3
"""
msearch_qdrant.py — Qdrant vector search helper for msearch.c

Called by msearch.c via popen(). Outputs JSON to stdout.

Usage:
    python3 msearch_qdrant.py search  <query> [--collection dim_semantic] [--top 10]
    python3 msearch_qdrant.py stats
    python3 msearch_qdrant.py embed  <query>     # just output embedding JSON
    python3 msearch_qdrant.py collections

The C side reads stdout as JSON.
"""

import sys
import json
import urllib.request
import urllib.error

QDRANT_URL = "http://localhost:6333"
MODEL_NAME = "BAAI/bge-small-en-v1.5"

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(query):
    """Generate 384-dim BGE embedding for a query string."""
    model = get_model()
    vec = model.encode([query])[0]
    return vec.tolist()


def qdrant_get(path):
    """GET request to Qdrant REST API."""
    url = f"{QDRANT_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def qdrant_post(path, payload):
    """POST request to Qdrant REST API."""
    url = f"{QDRANT_URL}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def cmd_stats():
    """Show all Qdrant collections with point counts and vector sizes."""
    result = qdrant_get("/collections")
    collections = result.get("result", {}).get("collections", [])
    output = {"collections": []}
    for col in collections:
        name = col["name"]
        try:
            info = qdrant_get(f"/collections/{name}")
            r = info.get("result", {})
            output["collections"].append({
                "name": name,
                "points": r.get("points_count", 0),
                "vectors": r.get("config", {}).get("params", {}).get("vectors", {}).get("size", 0),
                "status": r.get("status", "unknown"),
            })
        except Exception as e:
            output["collections"].append({"name": name, "error": str(e)})
    print(json.dumps(output, indent=2))


def cmd_collections():
    """List collection names only."""
    result = qdrant_get("/collections")
    collections = [c["name"] for c in result.get("result", {}).get("collections", [])]
    print(json.dumps({"collections": collections}))


def cmd_embed(query):
    """Just output the embedding vector as JSON."""
    vec = embed(query)
    print(json.dumps({"vector": vec, "dims": len(vec)}))


def cmd_search(query, collection="dim_semantic", top=10, fmt="json"):
    """Search a Qdrant collection with a text query (auto-embeds)."""
    vec = embed(query)
    payload = {
        "vector": vec,
        "limit": top,
        "with_payload": True,
        "with_vector": False,
    }
    try:
        result = qdrant_post(f"/collections/{collection}/points/search", payload)
        hits = result.get("result", [])

        if fmt == "text":
            print(f"Query: {query}")
            print(f"Collection: {collection}")
            print(f"Results: {len(hits)}")
            print()
            for i, hit in enumerate(hits, 1):
                score = hit.get("score", 0)
                payload_data = hit.get("payload", {})
                file_id = payload_data.get("file_id", "?")
                filename = payload_data.get("filename", "?")
                source = payload_data.get("source_table", "?")
                dim_count = payload_data.get("dim_count", "?")
                sample = payload_data.get("sample_row", "")
                print(f"[{i}] score={score:.4f}  id={hit.get('id', '?')}  file_id={file_id}")
                print(f"    file: {filename}")
                print(f"    source: {source}  dim_count: {dim_count}")
                if sample:
                    print(f"    sample: {sample}")
                print()
        else:
            output = {
                "query": query,
                "collection": collection,
                "count": len(hits),
                "results": [],
            }
            for hit in hits:
                score = hit.get("score", 0)
                payload_data = hit.get("payload", {})
                output["results"].append({
                    "id": hit.get("id"),
                    "score": round(score, 4),
                    "payload": payload_data,
                })
            print(json.dumps(output, indent=2))
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(json.dumps({"error": f"Qdrant HTTP {e.code}", "detail": body}, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))


def cmd_search_multi(query, collections=None, top=5, fmt="json"):
    """Search multiple Qdrant collections and merge results by score."""
    if collections is None:
        collections = [
            "dim_semantic", "dim_structural", "dim_dependency",
            "dim_control_flow", "dim_execution", "dim_data_flow",
        ]
    vec = embed(query)
    all_hits = []
    for col in collections:
        payload = {
            "vector": vec,
            "limit": top,
            "with_payload": True,
            "with_vector": False,
        }
        try:
            result = qdrant_post(f"/collections/{col}/points/search", payload)
            hits = result.get("result", [])
            for hit in hits:
                all_hits.append({
                    "collection": col,
                    "id": hit.get("id"),
                    "score": round(hit.get("score", 0), 4),
                    "payload": hit.get("payload", {}),
                })
        except Exception:
            pass
    # Sort by score descending
    all_hits.sort(key=lambda x: x["score"], reverse=True)
    # Limit to top N overall
    all_hits = all_hits[:top * 2]

    if fmt == "text":
        print(f"Query: {query}")
        print(f"Dimensions searched: {', '.join(collections)}")
        print(f"Results: {len(all_hits)} (merged by score)")
        print()
        for i, hit in enumerate(all_hits, 1):
            score = hit.get("score", 0)
            col = hit.get("collection", "?")
            payload_data = hit.get("payload", {})
            filename = payload_data.get("filename", "?")
            file_id = payload_data.get("file_id", "?")
            print(f"[{i}] score={score:.4f}  dim={col}  id={hit.get('id', '?')}  file_id={file_id}")
            if filename and filename != "?":
                print(f"    file: {filename}")
            print()
    else:
        output = {
            "query": query,
            "collections_searched": collections,
            "count": len(all_hits),
            "results": all_hits,
        }
        print(json.dumps(output, indent=2))


def main():
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"error": "no command. Use: search|stats|embed|collections|multi"}))
        sys.exit(1)

    cmd = args[0]

    if cmd == "stats":
        cmd_stats()
    elif cmd == "collections":
        cmd_collections()
    elif cmd == "embed":
        if len(args) < 2:
            print(json.dumps({"error": "embed requires a query"}))
            sys.exit(1)
        cmd_embed(args[1])
    elif cmd == "search":
        query = None
        collection = "dim_semantic"
        top = 10
        fmt = "json"
        i = 1
        while i < len(args):
            if args[i] == "--collection" and i + 1 < len(args):
                collection = args[i + 1]; i += 2
            elif args[i] == "--top" and i + 1 < len(args):
                top = int(args[i + 1]); i += 2
            elif args[i] == "--format" and i + 1 < len(args):
                fmt = args[i + 1]; i += 2
            elif not args[i].startswith("--"):
                query = args[i]; i += 1
            else:
                i += 1
        if not query:
            print(json.dumps({"error": "search requires a query"}))
            sys.exit(1)
        cmd_search(query, collection, top, fmt)
    elif cmd == "multi":
        query = None
        top = 5
        collections = None
        fmt = "json"
        i = 1
        while i < len(args):
            if args[i] == "--top" and i + 1 < len(args):
                top = int(args[i + 1]); i += 2
            elif args[i] == "--collections" and i + 1 < len(args):
                collections = args[i + 1].split(","); i += 2
            elif args[i] == "--format" and i + 1 < len(args):
                fmt = args[i + 1]; i += 2
            elif not args[i].startswith("--"):
                query = args[i]; i += 1
            else:
                i += 1
        if not query:
            print(json.dumps({"error": "multi requires a query"}))
            sys.exit(1)
        cmd_search_multi(query, collections, top, fmt)
    else:
        print(json.dumps({"error": f"unknown command: {cmd}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
