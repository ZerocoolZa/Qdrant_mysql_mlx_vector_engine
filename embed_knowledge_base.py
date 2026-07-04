#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     embed_knowledge_base.py
# Domain:   knowledge_base_embedding
# Authority: embeds vb_shared knowledge tables into Qdrant for semantic search
# DB:       vb_shared (MySQL) -> Qdrant knowledge_base collection
# ============================================================================
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    - Ghost Header present
#   @vbsty    - VBStyle Header present
#   @hardcode - no hardcoded paths (env-overridable constants)
#   @cstyle   - coding style compliant (4-space indent, no tabs)
#   @notab    - spaces only
#   @logging  - logging module used, no print
#   @nodeco   - no decorators
#   @tuple3   - Tuple3 returns (ok, data, error)
#   @run      - Run() dispatch entry
#   @state    - self.state dict pattern
#   @pascal   - PascalCase classes/methods
#   @upper    - UPPERCASE constants
# ============================================================================

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request

import mysql.connector

# ============================================================================
# CONSTANTS
# ============================================================================
QDRANT_URL = os.environ.get("KB_QDRANT_URL", "http://localhost:6333")
COLLECTION = os.environ.get("KB_COLLECTION", "knowledge_base")
MODEL_NAME = os.environ.get("KB_MODEL", "BAAI/bge-small-en-v1.5")
MYSQL_HOST = os.environ.get("KB_MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("KB_MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("KB_MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("KB_MYSQL_PASSWORD", "")
MYSQL_DB = os.environ.get("KB_MYSQL_DB", "vb_shared")
VECTOR_DIM = 384
BATCH_SIZE = 256
EMBED_SUBBATCH = 64
MAX_TEXT_LEN = 8000
PROGRESS_EVERY = 100

# Table config: table_name -> (select_sql, text_fields, extra_payload_fields)
# text_fields are joined with single space to form the embedding text.
TABLE_CONFIG = {
    "learned_rules": {
        "sql": "SELECT id, pattern, trigger_condition, fix_action, confidence "
               "FROM learned_rules "
               "WHERE pattern IS NOT NULL OR fix_action IS NOT NULL",
        "text_fields": ["pattern", "trigger_condition", "fix_action"],
        "extra_payload": ["confidence"],
    },
    "know_problems": {
        "sql": "SELECT id, problem, description FROM know_problems "
               "WHERE problem IS NOT NULL",
        "text_fields": ["problem", "description"],
        "extra_payload": [],
    },
    "know_solutions": {
        "sql": "SELECT id, solution, fault_code FROM know_solutions "
               "WHERE solution IS NOT NULL",
        "text_fields": ["solution", "fault_code"],
        "extra_payload": [],
    },
    "know_questions": {
        "sql": "SELECT id, question, category FROM know_questions "
               "WHERE question IS NOT NULL",
        "text_fields": ["question", "category"],
        "extra_payload": [],
    },
    "know_answers": {
        "sql": "SELECT id, answer, provenance, confidence FROM know_answers "
               "WHERE answer IS NOT NULL",
        "text_fields": ["answer", "provenance"],
        "extra_payload": ["confidence"],
    },
    "chat_ingestions": {
        "sql": "SELECT id, content FROM chat_ingestions "
               "WHERE content IS NOT NULL AND LENGTH(content) > 10",
        "text_fields": ["content"],
        "extra_payload": [],
    },
    "json_ingestions": {
        "sql": "SELECT id, content FROM json_ingestions "
               "WHERE content IS NOT NULL AND LENGTH(content) > 10",
        "text_fields": ["content"],
        "extra_payload": [],
    },
}

# ============================================================================
# LOGGING SETUP
# ============================================================================
Logger = logging.getLogger("embed_knowledge_base")
Logger.setLevel(logging.INFO)
_Handler = logging.StreamHandler(sys.stdout)
_Handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
Logger.addHandler(_Handler)
Logger.propagate = False

_Model = None


def GetModel():
    """Load and cache the BGE sentence-transformer model."""
    global _Model
    if _Model is None:
        from sentence_transformers import SentenceTransformer
        Logger.info("Loading model: %s ...", MODEL_NAME)
        _Model = SentenceTransformer(MODEL_NAME)
        Logger.info("Model loaded.")
    return _Model


def QdrantGet(path):
    """HTTP GET to Qdrant, return parsed JSON."""
    url = QDRANT_URL + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def QdrantPost(path, payload, timeout=60):
    """HTTP POST to Qdrant, return parsed JSON."""
    url = QDRANT_URL + path
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def QdrantPut(path, payload, timeout=60):
    """HTTP PUT to Qdrant, return parsed JSON."""
    url = QDRANT_URL + path
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def StableId(table_name, row_id):
    """Generate a stable integer point ID from table name + row id."""
    h = hashlib.sha256()
    h.update(table_name.encode("utf-8"))
    h.update(str(row_id).encode("utf-8"))
    return int.from_bytes(h.digest()[:8], "big") % (2 ** 62)


def CombineText(row, fields):
    """Join the given row fields with single space, skipping None/empty."""
    parts = []
    for f in fields:
        val = row.get(f)
        if val is not None and str(val).strip() != "":
            parts.append(str(val).strip())
    return " ".join(parts)[:MAX_TEXT_LEN]


def EmbedTexts(texts):
    """Embed a batch of texts using the BGE model. Returns list of vectors."""
    model = GetModel()
    vectors = model.encode(texts, show_progress_bar=False, batch_size=EMBED_SUBBATCH)
    return [v.tolist() for v in vectors]


def UpsertPoints(points, timeout=120):
    """Upsert points to Qdrant. points = list of {id, vector, payload}."""
    payload = {"points": points}
    QdrantPut("/collections/" + COLLECTION + "/points?wait=true", payload, timeout=timeout)


# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  KnowledgeBaseEmbedder
# Domain: knowledge_base_embedding
# Authority: orchestrates MySQL read + BGE embed + Qdrant store for vb_shared
# Dependencies: mysql.connector, sentence_transformers, urllib
# ============================================================================
class KnowledgeBaseEmbedder:
    """Embeds vb_shared knowledge tables into Qdrant collection knowledge_base."""

    def __init__(self):
        self.state = {
            "conn": None,
            "embedded_ids": set(),
            "total_embedded": 0,
            "total_skipped": 0,
        }

    def Run(self, command, params):
        """Dispatch entry. Returns Tuple3 (ok, data, error)."""
        dispatch = {
            "embed_all": self.EmbedAll,
            "embed_table": self.EmbedTable,
            "ensure_collection": self.EnsureCollection,
            "count": self.Count,
            "search": self.Search,
        }
        fn = dispatch.get(command)
        if fn is None:
            return (False, None, "unknown command: " + str(command))
        return fn(params)

    def ConnectMysql(self):
        """Open MySQL connection to vb_shared. Returns Tuple3."""
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB,
            )
            self.state["conn"] = conn
            return (True, conn, "")
        except mysql.connector.Error as exc:
            Logger.error("MySQL connect failed: %s", exc)
            return (False, None, "mysql connect failed: " + str(exc))

    def EnsureCollection(self, params):
        """Create Qdrant collection if missing. Returns Tuple3 (ok, count, error)."""
        try:
            info = QdrantGet("/collections/" + COLLECTION)
            count = info.get("result", {}).get("points_count", 0)
            Logger.info("Collection '%s' exists: %s points", COLLECTION, count)
            return (True, count, "")
        except urllib.error.HTTPError:
            pass
        except Exception as exc:
            Logger.error("EnsureCollection check failed: %s", exc)
            return (False, None, "qdrant check failed: " + str(exc))

        Logger.info("Creating collection '%s' (%s-dim, cosine)...", COLLECTION, VECTOR_DIM)
        payload = {
            "vectors": {"size": VECTOR_DIM, "distance": "Cosine"},
            "optimizers_config": {"default_segment_number": 4},
        }
        try:
            QdrantPut("/collections/" + COLLECTION, payload)
            Logger.info("Collection created.")
            return (True, 0, "")
        except Exception as exc:
            Logger.error("Create collection failed: %s", exc)
            return (False, None, "create collection failed: " + str(exc))

    def LoadEmbeddedIds(self):
        """Scroll existing Qdrant point IDs for resume. Returns Tuple3."""
        embedded = set()
        offset = None
        while True:
            scroll_payload = {"limit": BATCH_SIZE, "with_payload": False, "with_vector": False}
            if offset:
                scroll_payload["offset"] = offset
            try:
                result = QdrantPost("/collections/" + COLLECTION + "/points/scroll", scroll_payload)
            except Exception as exc:
                Logger.warning("Scroll stopped: %s", exc)
                break
            points = result.get("result", {}).get("points", [])
            for p in points:
                embedded.add(p["id"])
            offset = result.get("result", {}).get("next_page_offset")
            if not offset:
                break
        self.state["embedded_ids"] = embedded
        Logger.info("Resume: %s existing points found", len(embedded))
        return (True, len(embedded), "")

    def EmbedTable(self, params):
        """Embed a single table. params = {table, resume}. Returns Tuple3."""
        table = params.get("table")
        resume = params.get("resume", False)
        if table not in TABLE_CONFIG:
            return (False, None, "unknown table: " + str(table))
        cfg = TABLE_CONFIG[table]

        ok, _, err = self.ConnectMysql()
        if not ok:
            return (False, None, err)
        conn = self.state["conn"]
        cur = conn.cursor(dictionary=True)

        try:
            cur.execute(cfg["sql"])
        except mysql.connector.Error as exc:
            Logger.error("Query failed for %s: %s", table, exc)
            cur.close()
            conn.close()
            return (False, None, "query failed: " + str(exc))

        total_rows = 0
        embedded = 0
        skipped = 0
        start_time = time.time()
        text_fields = cfg["text_fields"]
        extra_fields = cfg["extra_payload"]

        Logger.info("Embedding table '%s' ...", table)

        while True:
            rows = cur.fetchmany(BATCH_SIZE)
            if not rows:
                break

            texts = []
            metadata = []
            for row in rows:
                row_id = row.get("id")
                if row_id is None:
                    continue
                text = CombineText(row, text_fields)
                if text.strip() == "":
                    continue
                point_id = StableId(table, row_id)
                if resume and point_id in self.state["embedded_ids"]:
                    skipped += 1
                    continue
                payload = {"table": table, "row_id": row_id, "text": text[:200]}
                for ef in extra_fields:
                    if ef in row and row[ef] is not None:
                        payload[ef] = float(row[ef]) if isinstance(row[ef], (int, float)) else str(row[ef])
                texts.append(text)
                metadata.append({"id": point_id, "payload": payload})

            if not texts:
                continue

            # Embed in sub-batches
            all_vectors = []
            for j in range(0, len(texts), EMBED_SUBBATCH):
                batch_texts = texts[j:j + EMBED_SUBBATCH]
                vectors = EmbedTexts(batch_texts)
                all_vectors.extend(vectors)

            points = []
            for vec, meta in zip(all_vectors, metadata):
                points.append({"id": meta["id"], "vector": vec, "payload": meta["payload"]})
            UpsertPoints(points)
            embedded += len(points)
            total_rows += len(rows)

            if embedded % PROGRESS_EVERY < BATCH_SIZE or embedded == len(points):
                elapsed = time.time() - start_time
                rate = embedded / elapsed if elapsed > 0 else 0
                Logger.info("  [%s] embedded=%s skipped=%s rate=%.0f/s", table, embedded, skipped, rate)

        cur.close()
        conn.close()
        self.state["total_embedded"] += embedded
        self.state["total_skipped"] += skipped
        Logger.info("Table '%s' done: embedded=%s skipped=%s", table, embedded, skipped)
        return (True, {"table": table, "embedded": embedded, "skipped": skipped}, "")

    def EmbedAll(self, params):
        """Embed all configured tables. params = {resume}. Returns Tuple3."""
        resume = params.get("resume", False)

        ok, _, err = self.EnsureCollection({})
        if not ok:
            return (False, None, err)

        if resume:
            self.LoadEmbeddedIds()

        results = []
        for table in TABLE_CONFIG:
            ok, data, err = self.EmbedTable({"table": table, "resume": resume})
            if not ok:
                Logger.error("Failed table %s: %s", table, err)
                results.append({"table": table, "error": err})
            else:
                results.append(data)

        # Final collection count
        try:
            info = QdrantGet("/collections/" + COLLECTION)
            final_count = info.get("result", {}).get("points_count", 0)
        except Exception as exc:
            Logger.error("Final count failed: %s", exc)
            final_count = -1

        Logger.info("=" * 60)
        Logger.info("EXPORT COMPLETE")
        Logger.info("  Total embedded this run: %s", self.state["total_embedded"])
        Logger.info("  Total skipped: %s", self.state["total_skipped"])
        Logger.info("  Collection '%s' now has: %s points", COLLECTION, final_count)
        Logger.info("  Vector dim: %s (BGE-small)  Distance: Cosine", VECTOR_DIM)
        return (True, {"results": results, "final_count": final_count}, "")

    def Count(self, params):
        """Return current point count of the collection. Returns Tuple3."""
        try:
            info = QdrantGet("/collections/" + COLLECTION)
            count = info.get("result", {}).get("points_count", 0)
            return (True, count, "")
        except Exception as exc:
            return (False, None, "count failed: " + str(exc))

    def Search(self, params):
        """Semantic search. params = {query, limit}. Returns Tuple3."""
        query = params.get("query", "")
        limit = int(params.get("limit", 5))
        if not query:
            return (False, None, "empty query")
        try:
            vectors = EmbedTexts([query])
            payload = {"vector": vectors[0], "limit": limit, "with_payload": True}
            result = QdrantPost("/collections/" + COLLECTION + "/points/search", payload)
            return (True, result, "")
        except Exception as exc:
            return (False, None, "search failed: " + str(exc))


# ============================================================================
# MAIN ENTRY
# ============================================================================
def Main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Embed vb_shared knowledge tables -> Qdrant")
    parser.add_argument("--resume", action="store_true", help="Skip already-embedded rows")
    parser.add_argument("--table", type=str, default=None, help="Embed only one table")
    parser.add_argument("--search", type=str, default=None, help="Run a semantic search query")
    parser.add_argument("--limit", type=int, default=5, help="Search result limit")
    args = parser.parse_args()

    Logger.info("Knowledge Base -> Qdrant Embeddings")
    Logger.info("  Collection: %s", COLLECTION)
    Logger.info("  Model: %s", MODEL_NAME)
    Logger.info("  MySQL: %s@%s:%s/%s", MYSQL_USER, MYSQL_HOST, MYSQL_PORT, MYSQL_DB)
    Logger.info("  Resume: %s", args.resume)

    embedder = KnowledgeBaseEmbedder()

    if args.search:
        ok, data, err = embedder.Search({"query": args.search, "limit": args.limit})
        if not ok:
            Logger.error("Search failed: %s", err)
            sys.exit(1)
        print(json.dumps(data, indent=2, default=str))
        return

    if args.table:
        ok, _, err = embedder.EnsureCollection({})
        if not ok:
            Logger.error("EnsureCollection failed: %s", err)
            sys.exit(1)
        if args.resume:
            embedder.LoadEmbeddedIds()
        ok, data, err = embedder.EmbedTable({"table": args.table, "resume": args.resume})
        if not ok:
            Logger.error("EmbedTable failed: %s", err)
            sys.exit(1)
        Logger.info("Done: %s", data)
        return

    ok, data, err = embedder.EmbedAll({"resume": args.resume})
    if not ok:
        Logger.error("EmbedAll failed: %s", err)
        sys.exit(1)
    Logger.info("Done: %s", data)


if __name__ == "__main__":
    Main()
