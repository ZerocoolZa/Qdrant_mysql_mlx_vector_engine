"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/dom_semantic_router/SemanticRouter.py";"identity=SemanticRouter";"purpose=Load inputs, upsert MLX vectors to Qdrant, kNN-classify unresolved against truth centroids, write hypothesis results";"date=2026-06-26";"version=2.0";"author=Devin";"task=TASK-086")}
#[@VBSTYLE]{("auth=Devin";"role=domain_routing";"return=Tuple3";"orch=Config";"no=no_decorators|no_print|no_hardcoded|no_tabs|no_self_underscore";"model=one_class_one_domain_one_authority_complete")}
#[@CLASSES]{("SemanticRouter")}
#[@METHODS]{("Run";"read_state";"set_config";"_p";"_LoadInputs";"_EnsureCollection";"_UpsertQdrant";"_Classify";"_WriteResults";"_PointId")}
#[@DOMAIN]{("routing")}
"""

import hashlib
import logging
import sqlite3
from typing import Any, Dict, List, Tuple

import numpy

from Config import (
    V20_DB_PATH, DOMAIN_GRAPH_DB_PATH, QDRANT_HOST, QDRANT_PORT,
    QDRANT_COLLECTION, EMBED_DIM, SIMILARITY_THRESHOLD, TIER_HYPOTHESIS,
    METHOD_MLX_BGE, LAYER_TRUTH, LAYER_UNRESOLVED, QDRANT_UPSERT_BATCH,
    LOG_PATH
)

Logger = logging.getLogger("dom_semantic_router.SemanticRouter")
if not Logger.handlers:
    Handler = logging.FileHandler(LOG_PATH)
    Handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    Logger.addHandler(Handler)
Logger.setLevel(logging.INFO)


class SemanticRouter:
    """Authority for routing unresolved classes to hypothesis-tier owners via centroid kNN."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "client": None
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "load_inputs":
            return self._LoadInputs(params)
        elif command == "upsert_qdrant":
            return self._UpsertQdrant(params)
        elif command == "classify":
            return self._Classify(params)
        elif command == "write_results":
            return self._WriteResults(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _LoadInputs(self, params):
        try:
            Conn = sqlite3.connect(DOMAIN_GRAPH_DB_PATH)
            Conn.execute("ATTACH DATABASE ? AS v20", (V20_DB_PATH,))
            truth_rows = Conn.execute(
                "SELECT t.class_name, t.owner, c.class_code "
                "FROM domain_truth t JOIN v20.classes c ON c.class_name = t.class_name"
            ).fetchall()
            unresolved_rows = Conn.execute(
                "SELECT u.class_name, u.current_domain_guess, c.class_code "
                "FROM domain_unresolved u JOIN v20.classes c ON c.class_name = u.class_name"
            ).fetchall()
            truth_before = Conn.execute("SELECT COUNT(*) FROM domain_truth").fetchone()[0]
            unresolved_before = Conn.execute("SELECT COUNT(*) FROM domain_unresolved").fetchone()[0]
            Conn.close()
            truth = [{"class_name": r[0], "owner": r[1], "class_code": r[2],
                      "layer": LAYER_TRUTH} for r in truth_rows]
            unresolved = [{"class_name": r[0], "current_domain_guess": r[1],
                           "class_code": r[2], "layer": LAYER_UNRESOLVED} for r in unresolved_rows]
            return (1, {"truth": truth, "unresolved": unresolved,
                        "truth_count": len(truth), "unresolved_count": len(unresolved),
                        "truth_before": truth_before,
                        "unresolved_before": unresolved_before}, None)
        except Exception as e:
            return (0, None, ("LOAD_INPUTS_ERROR", str(e), 0))

    def _PointId(self, class_name):
        Digest = hashlib.md5(class_name.encode("utf-8")).digest()
        return int.from_bytes(Digest[:8], "big", signed=False)

    def _EnsureCollection(self, client):
        from qdrant_client.models import VectorParams, Distance
        cols = client.get_collections().collections
        names = [c.name for c in cols]
        if QDRANT_COLLECTION not in names:
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE)
            )
            Logger.info("Created Qdrant collection %s (dim=%d, cosine)", QDRANT_COLLECTION, EMBED_DIM)
        return (1, True, None)

    def _UpsertQdrant(self, params):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import PointStruct
            records = self._p(params, "records", [])
            if not records:
                return (0, None, ("NO_RECORDS", "No vector records supplied", 0))
            client = self.state.get("client")
            if client is None:
                client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
                self.state["client"] = client
            ok, _, err = self._EnsureCollection(client)
            if not ok:
                return (0, None, err)
            upserted = 0
            skipped = 0
            batch = []
            for rec in records:
                vec = rec.get("vector")
                if vec is None:
                    skipped = skipped + 1
                    continue
                point = PointStruct(
                    id=self._PointId(rec["class_name"]),
                    vector=vec,
                    payload={
                        "class_name": rec["class_name"],
                        "owner": rec.get("owner", ""),
                        "layer": rec.get("layer", LAYER_UNRESOLVED)
                    }
                )
                batch.append(point)
                if len(batch) >= QDRANT_UPSERT_BATCH:
                    client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
                    upserted = upserted + len(batch)
                    batch = []
            if batch:
                client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
                upserted = upserted + len(batch)
            Logger.info("Qdrant upsert: %d points (skipped %d empty)", upserted, skipped)
            return (1, {"upserted": upserted, "skipped": skipped}, None)
        except Exception as e:
            return (0, None, ("UPSERT_ERROR", str(e), 0))

    def _Classify(self, params):
        try:
            unresolved = self._p(params, "unresolved", [])
            centroids = self._p(params, "centroids", {})
            threshold = self._p(params, "threshold", SIMILARITY_THRESHOLD)
            if not unresolved:
                return (0, None, ("NO_UNRESOLVED", "No unresolved vectors supplied", 0))
            if not centroids:
                return (0, None, ("NO_CENTROIDS", "No centroids supplied", 0))
            owner_names = list(centroids.keys())
            cent_matrix = numpy.stack(
                [numpy.asarray(centroids[o]["centroid"], dtype="float32") for o in owner_names]
            )
            assignments = []
            assigned = 0
            kept = 0
            for rec in unresolved:
                vec = rec.get("vector")
                if vec is None:
                    kept = kept + 1
                    assignments.append({"class_name": rec["class_name"], "owner": None,
                                        "score": None, "assigned": False, "reason": "no_vector"})
                    continue
                v = numpy.asarray(vec, dtype="float32")
                v_norm = numpy.linalg.norm(v)
                if v_norm > 0:
                    v = v / v_norm
                sims = cent_matrix @ v
                best_idx = int(numpy.argmax(sims))
                score = float(sims[best_idx])
                owner = owner_names[best_idx]
                if score >= threshold:
                    assigned = assigned + 1
                    assignments.append({"class_name": rec["class_name"], "owner": owner,
                                        "score": score, "assigned": True})
                else:
                    kept = kept + 1
                    assignments.append({"class_name": rec["class_name"], "owner": owner,
                                        "score": score, "assigned": False, "reason": "below_threshold"})
            Logger.info("Classify: %d assigned (>= %.2f), %d kept unresolved",
                        assigned, threshold, kept)
            return (1, {"assignments": assignments, "assigned": assigned,
                        "kept": kept, "threshold": threshold}, None)
        except Exception as e:
            return (0, None, ("CLASSIFY_ERROR", str(e), 0))

    def _WriteResults(self, params):
        try:
            assignments = self._p(params, "assignments", [])
            if not assignments:
                return (0, None, ("NO_ASSIGNMENTS", "No assignments supplied", 0))
            to_write = [a for a in assignments if a.get("assigned")]
            if not to_write:
                return (1, {"inserted": 0, "deleted": 0, "note": "no assignments above threshold"}, None)
            Conn = sqlite3.connect(DOMAIN_GRAPH_DB_PATH)
            Conn.execute("BEGIN")
            truth_before = Conn.execute("SELECT COUNT(*) FROM domain_truth").fetchone()[0]
            inserted = 0
            deleted = 0
            for a in to_write:
                Conn.execute(
                    "DELETE FROM domain_hypothesis WHERE class_name = ? AND method = ?",
                    (a["class_name"], METHOD_MLX_BGE)
                )
                Conn.execute(
                    "INSERT INTO domain_hypothesis(class_name, owner, tier, method, score) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (a["class_name"], a["owner"], TIER_HYPOTHESIS, METHOD_MLX_BGE, a["score"])
                )
                inserted = inserted + 1
                cur = Conn.execute("DELETE FROM domain_unresolved WHERE class_name = ?",
                                   (a["class_name"],))
                deleted = deleted + cur.rowcount
            Conn.commit()
            truth_after = Conn.execute("SELECT COUNT(*) FROM domain_truth").fetchone()[0]
            unresolved_after = Conn.execute("SELECT COUNT(*) FROM domain_unresolved").fetchone()[0]
            hypothesis_after = Conn.execute("SELECT COUNT(*) FROM domain_hypothesis").fetchone()[0]
            Conn.close()
            Logger.info("Write: inserted %d hypothesis, deleted %d unresolved (truth %d->%d)",
                        inserted, deleted, truth_before, truth_after)
            return (1, {"inserted": inserted, "deleted": deleted,
                        "truth_before": truth_before, "truth_after": truth_after,
                        "unresolved_after": unresolved_after,
                        "hypothesis_after": hypothesis_after}, None)
        except Exception as e:
            try:
                Conn.rollback()
            except Exception:
                pass
            return (0, None, ("WRITE_ERROR", str(e), 0))

    def read_state(self, params):
        return (1, dict(self.state), None)

    def set_config(self, params):
        try:
            for key, value in params.items():
                self.state["config"][key] = value
            return (1, dict(self.state["config"]), None)
        except Exception as e:
            return (0, None, ("SET_CONFIG_ERROR", str(e), 0))
