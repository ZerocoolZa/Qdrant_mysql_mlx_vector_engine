#!/usr/bin/env python3
#[@GHOST]{[@file<qdrant_search.py>][@state<active>][@ver<v1.0>][@auth<Devin>][@date<2026-07-04>]}
#[@VBSTYLE]{[@auth<Devin>][@role<qdrant_searcher>][@return<tuple3>][@no<print|hardcoded>]}
#[@FILEID]{qdrant_search}
#[@SUMMARY]{Semantic search over Qdrant chat_messages collection. Reads a JSON query from stdin, embeds it with the shared TF-IDF+random-projection model, and returns the top matching messages with scores and metadata.}
#[@CLASS]{QdrantSearcher}
#[@METHOD]{__init__, load_embedder, search, Run, read_state, set_config}

"""
QdrantSearcher — Semantic search over indexed chat messages.

Input (stdin JSON):
    {"query": "kokoro,voice,pipeline", "limit": 20}

Output (stdout JSON):
    {"results": [
        {"id": ..., "score": ..., "trajectory_id": ..., "role": ..., "content_preview": ...},
        ...
    ]}

The query is embedded using the SAME QdrantEmbed model that qdrant_index.py
fit and persisted to embed_model/qdrant_vocab_idf.json, guaranteeing identical
embedding space between indexing and search.
"""

import os
import sys
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from embed_model.qdrant_embed import QdrantEmbed, MODEL_FILE

from qdrant_client import QdrantClient

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "chat_messages"
DEFAULT_LIMIT = 20


class QdrantSearcher:
    """Searches the Qdrant chat_messages collection semantically."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if param is not None else {}
        self.state = {
            "config": {
                "qdrant_host": QDRANT_HOST,
                "qdrant_port": QDRANT_PORT,
                "collection": COLLECTION_NAME,
                "default_limit": DEFAULT_LIMIT,
            },
            "qdrant_client": None,
            "embedder": None,
            "errors": [],
        }

    def _p(self, msg):
        return "[QdrantSearcher] " + str(msg)

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, values):
        if not isinstance(values, dict):
            return (0, None, (1, "set_config expects dict", 0))
        self.state["config"].update(values)
        return (1, dict(self.state["config"]), None)

    def load_embedder(self):
        """Load the shared embedder from persisted vocab/IDF file."""
        embedder = QdrantEmbed(param={"model_path": MODEL_FILE})
        code, _, err = embedder.load(MODEL_FILE)
        if code != 1:
            return (0, None, err)
        self.state["embedder"] = embedder
        return (1, True, None)

    def connect_qdrant(self):
        """Open Qdrant client."""
        host = self.state["config"]["qdrant_host"]
        port = self.state["config"]["qdrant_port"]
        client = QdrantClient(host=host, port=port)
        self.state["qdrant_client"] = client
        return (1, True, None)

    def search(self, query, limit=None):
        """Run a semantic search.

        query: str
        limit: int or None (falls back to default_limit)
        Returns Tuple3 (1, list_of_result_dicts, None).
        """
        if self.state["embedder"] is None:
            return (0, None, (2, "embedder not loaded", 0))
        if self.state["qdrant_client"] is None:
            return (0, None, (3, "qdrant not connected", 0))

        if limit is None:
            limit = self.state["config"]["default_limit"]

        # embed query with shared model
        code, vec, err = self.state["embedder"].embed(query)
        if code != 1:
            return (0, None, err)

        client = self.state["qdrant_client"]
        collection = self.state["config"]["collection"]
        hits = client.query_points(
            collection_name=collection,
            query=vec.tolist(),
            limit=int(limit),
        )

        results = []
        for point in hits.points:
            payload = point.payload or {}
            results.append({
                "id": point.id,
                "score": float(point.score),
                "trajectory_id": payload.get("trajectory_id"),
                "role": payload.get("role"),
                "content_preview": payload.get("content_preview"),
            })
        return (1, results, None)

    def Run(self, command, params=None):
        params = params or {}
        if command == "load_embedder":
            return self.load_embedder()
        elif command == "connect_qdrant":
            return self.connect_qdrant()
        elif command == "search":
            return self.search(params.get("query", ""), params.get("limit"))
        elif command == "read_state":
            return self.read_state()
        elif command == "set_config":
            return self.set_config(params.get("values", {}))
        return (0, None, (99, "unknown command: " + str(command), 0))


def main():
    raw = sys.stdin.read()
    try:
        req = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        sys.stdout.write(json.dumps({"results": [], "error": "invalid JSON: " + str(e)}) + "\n")
        sys.exit(1)

    query = req.get("query", "")
    limit = req.get("limit", DEFAULT_LIMIT)

    searcher = QdrantSearcher()
    code, _, err = searcher.load_embedder()
    if code != 1:
        sys.stdout.write(json.dumps({"results": [], "error": "embedder load failed: " + str(err)}) + "\n")
        sys.exit(1)

    code, _, err = searcher.connect_qdrant()
    if code != 1:
        sys.stdout.write(json.dumps({"results": [], "error": "qdrant connect failed: " + str(err)}) + "\n")
        sys.exit(1)

    code, results, err = searcher.search(query, limit)
    if code != 1:
        sys.stdout.write(json.dumps({"results": [], "error": "search failed: " + str(err)}) + "\n")
        sys.exit(1)

    sys.stdout.write(json.dumps({"results": results}) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
