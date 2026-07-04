#!/usr/bin/env python3
#[@GHOST]{[@file<qdrant_index.py>][@state<active>][@ver<v1.0>][@auth<Devin>][@date<2026-07-04>]}
#[@VBSTYLE]{[@auth<Devin>][@role<qdrant_indexer>][@return<tuple3>][@no<print|hardcoded>]}
#[@FILEID]{qdrant_index}
#[@SUMMARY]{Indexes chat messages from MySQL cascade_chats.messages into a Qdrant collection for semantic search. Builds TF-IDF + random-projection embeddings (64-dim), persists vocab/IDF for search consistency, batch-uploads to Qdrant.}
#[@CLASS]{QdrantIndexer}
#[@METHOD]{__init__, connect_mysql, fetch_messages, build_embeddings, create_collection, upload_batch, run_index, Run, read_state, set_config}

"""
QdrantIndexer — Build a Qdrant vector store of chat messages.

Pipeline:
  1. Connect to MySQL cascade_chats.messages
  2. Fetch messages with non-trivial content (LENGTH > 50)
  3. Fit TF-IDF + random-projection embedder on the full corpus
  4. Persist vocab/IDF/projection to embed_model/qdrant_vocab_idf.json
  5. Create (or recreate) Qdrant collection ``chat_messages`` (64-dim, Cosine)
  6. Batch upload points (100/batch) with payload metadata
  7. Report progress + final count

Run directly:
    python3 qdrant_index.py
"""

import os
import sys
import json
import time
import numpy as np

# make sibling embed_model importable
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from embed_model.qdrant_embed import QdrantEmbed, MODEL_FILE

import pymysql
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "chat_messages"
VECTOR_SIZE = 64
BATCH_SIZE = 100
CONTENT_MIN_LEN = 50
CONTENT_PREVIEW_LEN = 200

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "cascade_chats",
    "charset": "utf8mb4",
}


class QdrantIndexer:
    """Indexes MySQL chat messages into Qdrant for semantic search."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if param is not None else {}
        self.state = {
            "config": {
                "qdrant_host": QDRANT_HOST,
                "qdrant_port": QDRANT_PORT,
                "collection": COLLECTION_NAME,
                "vector_size": VECTOR_SIZE,
                "batch_size": BATCH_SIZE,
                "content_min_len": CONTENT_MIN_LEN,
                "preview_len": CONTENT_PREVIEW_LEN,
            },
            "mysql_conn": None,
            "qdrant_client": None,
            "embedder": None,
            "indexed_count": 0,
            "total_messages": 0,
            "errors": [],
        }

    def p(self, msg):
        return "[QdrantIndexer] " + str(msg)

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, values):
        if not isinstance(values, dict):
            return (0, None, (1, "set_config expects dict", 0))
        self.state["config"].update(values)
        return (1, dict(self.state["config"]), None)

    def connect_mysql(self):
        """Open MySQL connection to cascade_chats."""
        cfg = dict(MYSQL_CONFIG)
        cfg.update(self.param.get("mysql", {}))
        conn = pymysql.connect(**cfg)
        self.state["mysql_conn"] = conn
        return (1, True, None)

    def connect_qdrant(self):
        """Open Qdrant client."""
        host = self.state["config"]["qdrant_host"]
        port = self.state["config"]["qdrant_port"]
        client = QdrantClient(host=host, port=port)
        self.state["qdrant_client"] = client
        return (1, True, None)

    def fetch_messages(self):
        """Fetch all qualifying messages from MySQL.

        Returns Tuple3 (1, list_of_dicts, None).
        Each dict: {id, trajectory_id, role, content}
        """
        conn = self.state["mysql_conn"]
        if conn is None:
            return (0, None, (2, "mysql not connected", 0))
        cur = conn.cursor(pymysql.cursors.DictCursor)
        sql = (
            "SELECT id, trajectory_id, role, content FROM messages "
            "WHERE content IS NOT NULL AND LENGTH(content) > %s"
        )
        min_len = self.state["config"]["content_min_len"]
        cur.execute(sql, (min_len,))
        rows = cur.fetchall()
        cur.close()
        self.state["total_messages"] = len(rows)
        return (1, rows, None)

    def build_embeddings(self, messages):
        """Fit embedder on corpus and embed every message.

        Returns Tuple3 (1, list_of_vectors, None).
        """
        embedder = QdrantEmbed(param={"model_path": MODEL_FILE})
        corpus = [m["content"] for m in messages]
        code, data, err = embedder.fit(corpus)
        if code != 1:
            return (0, None, err)
        # persist vocab/idf/projection
        code, data, err = embedder.save(MODEL_FILE)
        if code != 1:
            return (0, None, err)
        self.state["embedder"] = embedder

        vectors = []
        for m in messages:
            code, vec, err = embedder.embed(m["content"])
            if code != 1:
                vectors.append(np.zeros(VECTOR_SIZE, dtype=np.float32))
            else:
                vectors.append(vec)
        return (1, vectors, None)

    def create_collection(self):
        """Create (or recreate) the Qdrant collection."""
        client = self.state["qdrant_client"]
        if client is None:
            return (0, None, (3, "qdrant not connected", 0))
        # drop if exists
        existing = client.get_collections().collections
        names = [c.name for c in existing]
        if COLLECTION_NAME in names:
            client.delete_collection(COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        return (1, True, None)

    def upload_batch(self, messages, vectors, start_idx):
        """Upload a single batch of points to Qdrant.

        start_idx is the offset for point ids.
        Returns Tuple3 (1, uploaded_count, None).
        """
        client = self.state["qdrant_client"]
        if client is None:
            return (0, None, (4, "qdrant not connected", 0))
        preview_len = self.state["config"]["preview_len"]
        points = []
        for i, msg in enumerate(messages):
            pid = int(msg["id"])
            vec = vectors[i]
            content = msg["content"] or ""
            payload = {
                "message_id": pid,
                "trajectory_id": msg["trajectory_id"],
                "role": msg["role"],
                "content_preview": content[:preview_len],
            }
            points.append(PointStruct(id=pid, vector=vec.tolist(), payload=payload))
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        return (1, len(points), None)

    def run_index(self):
        """Full indexing pipeline. Returns Tuple3 (1, count, None)."""
        errors = self.state["errors"]
        # 1. connect
        code, _, err = self.connect_mysql()
        if code != 1:
            errors.append(str(err))
            return (0, None, err)
        code, _, err = self.connect_qdrant()
        if code != 1:
            errors.append(str(err))
            return (0, None, err)

        # 2. fetch
        code, messages, err = self.fetch_messages()
        if code != 1:
            errors.append(str(err))
            return (0, None, err)
        total = len(messages)
        sys.stderr.write(self.p("fetched %d messages\n" % total))

        # 3. embeddings
        code, vectors, err = self.build_embeddings(messages)
        if code != 1:
            errors.append(str(err))
            return (0, None, err)
        sys.stderr.write(self.p("built %d embeddings, vocab saved to %s\n" % (len(vectors), MODEL_FILE)))

        # 4. collection
        code, _, err = self.create_collection()
        if code != 1:
            errors.append(str(err))
            return (0, None, err)
        sys.stderr.write(self.p("collection '%s' ready\n" % COLLECTION_NAME))

        # 5. batch upload
        batch_size = self.state["config"]["batch_size"]
        count = 0
        t0 = time.time()
        for start in range(0, total, batch_size):
            batch_msgs = messages[start:start + batch_size]
            batch_vecs = vectors[start:start + batch_size]
            code, n, err = self.upload_batch(batch_msgs, batch_vecs, start)
            if code != 1:
                errors.append(str(err))
                sys.stderr.write(self.p("batch %d error: %s\n" % (start, err)))
                continue
            count += n
            if (start // batch_size) % 5 == 0 or start + batch_size >= total:
                pct = 100.0 * count / max(total, 1)
                sys.stderr.write(self.p("uploaded %d/%d (%.1f%%)\n" % (count, total, pct)))

        elapsed = time.time() - t0
        self.state["indexed_count"] = count
        sys.stderr.write(self.p("DONE: %d messages indexed in %.1fs\n" % (count, elapsed)))

        # close mysql
        try:
            self.state["mysql_conn"].close()
        except Exception:
            pass
        return (1, count, None)

    def Run(self, command, params=None):
        params = params or {}
        if command == "run_index":
            return self.run_index()
        elif command == "connect_mysql":
            return self.connect_mysql()
        elif command == "connect_qdrant":
            return self.connect_qdrant()
        elif command == "fetch_messages":
            return self.fetch_messages()
        elif command == "build_embeddings":
            return self.build_embeddings(params.get("messages", []))
        elif command == "create_collection":
            return self.create_collection()
        elif command == "upload_batch":
            return self.upload_batch(params.get("messages", []),
                                     params.get("vectors", []),
                                     params.get("start_idx", 0))
        elif command == "read_state":
            return self.read_state()
        elif command == "set_config":
            return self.set_config(params.get("values", {}))
        return (0, None, (99, "unknown command: " + str(command), 0))


def main():
    indexer = QdrantIndexer()
    code, data, err = indexer.run_index()
    result = {
        "status": "ok" if code == 1 else "error",
        "indexed_count": indexer.state["indexed_count"],
        "total_messages": indexer.state["total_messages"],
        "errors": indexer.state["errors"],
    }
    if code != 1 and err is not None:
        result["error_detail"] = str(err)
    sys.stdout.write(json.dumps(result) + "\n")
    sys.exit(0 if code == 1 else 1)


if __name__ == "__main__":
    main()
