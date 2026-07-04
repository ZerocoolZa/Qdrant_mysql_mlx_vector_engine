"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/dom_semantic_router/CentroidBuilder.py";"identity=CentroidBuilder";"purpose=Build per-domain centroids from truth class MLX vectors anchored by owners with >=3 members";"date=2026-06-26";"version=2.0";"author=Devin";"task=TASK-086")}
#[@VBSTYLE]{("auth=Devin";"role=domain_centroid";"return=Tuple3";"orch=Config";"no=no_decorators|no_print|no_hardcoded|no_tabs|no_self_underscore";"model=one_class_one_domain_one_authority_complete")}
#[@CLASSES]{("CentroidBuilder")}
#[@METHODS]{("Run";"read_state";"set_config";"_p";"_BuildCentroids")}
#[@DOMAIN]{("centroid")}
"""

import logging
from typing import Any, Dict, List, Tuple

import numpy

from Config import MIN_CENTROID_MEMBERS, LOG_PATH

Logger = logging.getLogger("dom_semantic_router.CentroidBuilder")
if not Logger.handlers:
    Handler = logging.FileHandler(LOG_PATH)
    Handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    Logger.addHandler(Handler)
Logger.setLevel(logging.INFO)


class CentroidBuilder:
    """Authority for computing stable per-owner centroids from truth vectors."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "centroids": {}
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "build_centroids":
            return self._BuildCentroids(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _BuildCentroids(self, params):
        try:
            truth = self._p(params, "truth", [])
            if not truth:
                return (0, None, ("NO_TRUTH", "No truth vectors supplied", 0))
            by_owner = {}
            skipped_owners = []
            for rec in truth:
                vec = rec.get("vector")
                owner = rec.get("owner", "")
                if vec is None:
                    continue
                by_owner.setdefault(owner, []).append(vec)
            centroids = {}
            for owner, vecs in by_owner.items():
                if len(vecs) < MIN_CENTROID_MEMBERS:
                    skipped_owners.append({"owner": owner, "members": len(vecs)})
                    continue
                stacked = numpy.stack(vecs).astype("float32")
                centroid = stacked.mean(axis=0)
                norm = numpy.linalg.norm(centroid)
                if norm > 0:
                    centroid = centroid / norm
                centroids[owner] = {
                    "centroid": centroid.tolist(),
                    "members": len(vecs)
                }
            self.state["centroids"] = centroids
            self.state["results"] = self.state.get("results", []) + [
                {"event": "centroids_built", "owners": len(centroids),
                 "skipped_owners": len(skipped_owners)}
            ]
            Logger.info("Centroids built: %d owners (skipped %d with <%d members)",
                        len(centroids), len(skipped_owners), MIN_CENTROID_MEMBERS)
            return (1, {"centroids": centroids, "owners": len(centroids),
                        "skipped_owners": skipped_owners}, None)
        except Exception as e:
            return (0, None, ("CENTROID_ERROR", str(e), 0))

    def read_state(self, params):
        return (1, dict(self.state), None)

    def set_config(self, params):
        try:
            for key, value in params.items():
                self.state["config"][key] = value
            return (1, dict(self.state["config"]), None)
        except Exception as e:
            return (0, None, ("SET_CONFIG_ERROR", str(e), 0))
