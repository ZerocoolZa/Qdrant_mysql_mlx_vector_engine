#!/usr/bin/env python3
# [@GHOST]{[@file<embed_devin_summaries.py>][@domain<devin_embedding>][@role<embedding_exporter>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<embedding_exporter>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Embeds Devin session summaries from MySQL devin.devin_summaries into Qdrant collection devin_summaries for semantic search.}
# [@CLASS]{EmbedDevinSummaries}
# [@METHOD]{Run,embed_all,create_collection,embed_batch,read_state,set_config}

import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error

import mysql.connector
from sentence_transformers import SentenceTransformer

QDRANT_URL = os.environ.get("DS_QDRANT_URL", "http://localhost:6333")
COLLECTION = os.environ.get("DS_COLLECTION", "devin_summaries")
MODEL_NAME = os.environ.get("DS_MODEL", "BAAI/bge-small-en-v1.5")
MYSQL_HOST = os.environ.get("DS_MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("DS_MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("DS_MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("DS_MYSQL_PASSWORD", "")
MYSQL_DB = os.environ.get("DS_MYSQL_DB", "devin")
VECTOR_DIM = 384
BATCH_SIZE = 32
MAX_TEXT_LEN = 8000


class EmbedDevinSummaries:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "qdrant_url": QDRANT_URL,
                "collection": COLLECTION,
                "model_name": MODEL_NAME,
                "mysql_host": MYSQL_HOST,
                "mysql_port": MYSQL_PORT,
                "mysql_user": MYSQL_USER,
                "mysql_pass": MYSQL_PASSWORD,
                "mysql_db": MYSQL_DB,
                "vector_dim": VECTOR_DIM,
                "batch_size": BATCH_SIZE,
                "max_text_len": MAX_TEXT_LEN,
            },
            "results": {
                "total_embedded": 0,
                "total_failed": 0,
                "last_run": None,
            },
            "model": None,
        }
        if db:
            self.state["config"].update(db)
        if param:
            self.state["config"].update(param)

    def _p(self, params, key, default=None):
        if not params or not isinstance(params, dict):
            return default
        val = params.get(key, default)
        if val is None:
            return default
        return val

    def _conn(self):
        cfg = self.state["config"]
        return mysql.connector.connect(
            user=cfg["mysql_user"],
            password=cfg["mysql_pass"],
            host=cfg["mysql_host"],
            port=cfg["mysql_port"],
            database=cfg["mysql_db"],
            autocommit=True,
        )

    def _qdrant(self, method, path, body=None):
        url = self.state["config"]["qdrant_url"] + path
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode("utf-8"), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    def _load_model(self):
        if self.state["model"] is None:
            self.state["model"] = SentenceTransformer(self.state["config"]["model_name"])
        return self.state["model"]

    def Run(self, command, params=None):
        dispatch = {
            "embed_all": self._cmd_embed_all,
            "create_collection": self._cmd_create_collection,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"unknown command: {command}", 0))
        return handler(params)

    def _cmd_create_collection(self, params=None):
        cfg = self.state["config"]
        body = {
            "vectors": {"size": cfg["vector_dim"], "distance": "Cosine"},
            "optimizers_config": {"default_segment_number": 2},
        }
        result = self._qdrant("PUT", f"/collections/{cfg['collection']}", body)
        if "error" in result:
            return (0, None, ("ERR_CREATE", result["error"], 0))
        return (1, {"collection": cfg["collection"], "status": result}, None)

    def _cmd_embed_all(self, params=None):
        cfg = self.state["config"]
        ok, _, err = self._cmd_create_collection()
        if not ok:
            return (0, None, err)

        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT id, summary_file, content, file_size FROM devin_summaries")
        rows = c.fetchall()
        conn.close()

        model = self._load_model()
        total = len(rows)
        embedded = 0
        failed = 0
        batch = []

        for row in rows:
            rid, summary_file, content, file_size = row[0], row[1], row[2] or "", row[3] or 0
            text = content[:cfg["max_text_len"]]
            if len(text.strip()) < 10:
                failed += 1
                continue

            point_id = hashlib.md5(f"devin_summary_{rid}".encode()).hexdigest()[:16]
            batch.append({
                "id": point_id,
                "content": text,
                "payload": {
                    "source": "devin_summaries",
                    "summary_id": rid,
                    "summary_file": summary_file,
                    "file_size": file_size,
                    "text_preview": text[:200],
                },
            })

            if len(batch) >= cfg["batch_size"]:
                ok, n, fail = self._embed_batch(model, batch)
                embedded += n
                failed += fail
                batch = []

        if batch:
            ok, n, fail = self._embed_batch(model, batch)
            embedded += n
            failed += fail

        self.state["results"]["total_embedded"] = embedded
        self.state["results"]["total_failed"] = failed
        self.state["results"]["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")

        return (1, {
            "total": total,
            "embedded": embedded,
            "failed": failed,
            "collection": cfg["collection"],
        }, None)

    def _embed_batch(self, model, batch):
        texts = [item["content"] for item in batch]
        try:
            embeddings = model.encode(texts, show_progress_bar=False)
        except Exception:
            return (0, 0, len(batch))

        points = []
        for i, item in enumerate(batch):
            points.append({
                "id": item["id"],
                "vector": embeddings[i].tolist(),
                "payload": item["payload"],
            })

        cfg = self.state["config"]
        result = self._qdrant("PUT", f"/collections/{cfg['collection']}/points", {"points": points})
        if "error" in result:
            return (0, 0, len(batch))
        return (1, len(batch), 0)

    def read_state(self, params=None):
        return (1, {
            "config": dict(self.state["config"]),
            "results": dict(self.state["results"]),
        }, None)

    def set_config(self, params):
        if not params or not isinstance(params, dict):
            return (0, None, ("ERR_PARAMS", "config dict required", 0))
        self.state["config"].update(params)
        return (1, {"updated": list(params.keys())}, None)


if __name__ == "__main__":
    exporter = EmbedDevinSummaries()
    ok, data, err = exporter.Run("embed_all")
    if ok:
        print(f"Embedded {data['embedded']}/{data['total']} summaries into {data['collection']}")
        if data["failed"]:
            print(f"Failed: {data['failed']}")
    else:
        print(f"ERROR: {err}")
        sys.exit(1)
