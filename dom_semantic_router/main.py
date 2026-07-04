"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/dom_semantic_router/main.py";"identity=Main";"purpose=CLI entry point orchestrating the MLX bge-small semantic domain router pipeline";"date=2026-06-26";"version=2.0";"author=Devin";"task=TASK-086")}
#[@VBSTYLE]{("auth=Devin";"role=domain_orchestration";"return=Tuple3";"orch=Config|ClassEmbedder|CentroidBuilder|SemanticRouter";"no=no_decorators|no_print|no_hardcoded|no_tabs|no_self_underscore";"model=one_class_one_domain_one_authority_complete")}
#[@CLASSES]{("Main")}
#[@METHODS]{("Run";"read_state";"set_config";"_p";"_RunFull";"_WriteReport")}
#[@DOMAIN]{("orchestration")}
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from Config import (
    BASE_DIR, SIMILARITY_THRESHOLD, LAYER_TRUTH, LAYER_UNRESOLVED,
    LAYER_HYPOTHESIS, METHOD_MLX_BGE, LOG_PATH
)
from ClassEmbedder import ClassEmbedder
from CentroidBuilder import CentroidBuilder
from SemanticRouter import SemanticRouter

Logger = logging.getLogger("dom_semantic_router.Main")
if not Logger.handlers:
    Handler = logging.FileHandler(LOG_PATH)
    Handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    Handler.setLevel(logging.INFO)
    Logger.addHandler(Handler)
Logger.setLevel(logging.INFO)

REPORT_PATH = str(Path(BASE_DIR) / "dom_semantic_router_report.json")


class Main:
    """Authority for orchestrating the semantic domain router pipeline."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "run":
            return self._RunFull(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _RunFull(self, params):
        try:
            threshold = self._p(params, "threshold", SIMILARITY_THRESHOLD)
            Embedder = ClassEmbedder(param={"threshold": threshold})
            Builder = CentroidBuilder(param={"threshold": threshold})
            Router = SemanticRouter(param={"threshold": threshold})

            ok, inputs, err = Router.Run("load_inputs", {})
            if not ok:
                return (0, None, err)
            truth = inputs["truth"]
            unresolved = inputs["unresolved"]
            Logger.info("Inputs: truth=%d unresolved=%d (truth_before=%d)",
                        len(truth), len(unresolved), inputs["truth_before"])

            embed_records = []
            for rec in truth:
                embed_records.append({"class_name": rec["class_name"],
                                      "class_code": rec["class_code"], "owner": rec["owner"],
                                      "layer": LAYER_TRUTH})
            for rec in unresolved:
                embed_records.append({"class_name": rec["class_name"],
                                      "class_code": rec["class_code"],
                                      "owner": rec.get("current_domain_guess", ""),
                                      "layer": LAYER_UNRESOLVED})

            ok, embed_data, err = Embedder.Run("embed_classes", {"records": embed_records})
            if not ok:
                return (0, None, err)
            embedded = embed_data["records"]
            skipped = embed_data["skipped"]
            Logger.info("Embedded %d records (skipped %d empty)", len(embedded), skipped)

            vec_by_name = {r["class_name"]: r.get("vector") for r in embedded}
            upsert_records = []
            for rec in embed_records:
                upsert_records.append({"class_name": rec["class_name"],
                                       "vector": vec_by_name.get(rec["class_name"]),
                                       "owner": rec["owner"], "layer": rec["layer"]})
            ok, upsert_data, err = Router.Run("upsert_qdrant", {"records": upsert_records})
            if not ok:
                return (0, None, err)

            truth_vectors = []
            for rec in truth:
                vec = vec_by_name.get(rec["class_name"])
                if vec is not None:
                    truth_vectors.append({"class_name": rec["class_name"],
                                          "owner": rec["owner"], "vector": vec})
            ok, cent_data, err = Builder.Run("build_centroids", {"truth": truth_vectors})
            if not ok:
                return (0, None, err)
            centroids = cent_data["centroids"]
            Logger.info("Centroids: %d owners", len(centroids))

            unresolved_vectors = []
            for rec in unresolved:
                unresolved_vectors.append({"class_name": rec["class_name"],
                                           "vector": vec_by_name.get(rec["class_name"])})
            ok, class_data, err = Router.Run("classify",
                                             {"unresolved": unresolved_vectors,
                                              "centroids": centroids,
                                              "threshold": threshold})
            if not ok:
                return (0, None, err)
            assignments = class_data["assignments"]

            ok, write_data, err = Router.Run("write_results", {"assignments": assignments})
            if not ok:
                return (0, None, err)

            top = sorted([a for a in assignments if a.get("assigned")],
                         key=lambda a: a.get("score", 0), reverse=True)[:10]
            report = {
                "threshold": threshold,
                "inputs": {"truth": len(truth), "unresolved": len(unresolved),
                           "truth_before": inputs["truth_before"],
                           "unresolved_before": inputs["unresolved_before"]},
                "embedded": {"total": len(embedded), "skipped_empty": skipped},
                "qdrant": {"upserted": upsert_data["upserted"],
                           "skipped": upsert_data["skipped"]},
                "centroids": {"owners": len(centroids),
                              "skipped_owners": len(cent_data["skipped_owners"])},
                "classify": {"assigned": class_data["assigned"],
                             "kept_unresolved": class_data["kept"]},
                "write": write_data,
                "top_10_assignments": top
            }
            self.state["results"] = self.state.get("results", []) + [report]
            self._WriteReport(report)
            Logger.info("Pipeline complete: assigned=%d kept=%d truth_after=%d",
                        class_data["assigned"], class_data["kept"],
                        write_data["truth_after"])
            return (1, report, None)
        except Exception as e:
            return (0, None, ("RUN_ERROR", str(e), 0))

    def _WriteReport(self, report):
        try:
            with open(REPORT_PATH, "w") as fh:
                json.dump(report, fh, indent=2)
            return (1, REPORT_PATH, None)
        except Exception as e:
            return (0, None, ("REPORT_WRITE_ERROR", str(e), 0))

    def read_state(self, params):
        return (1, dict(self.state), None)

    def set_config(self, params):
        try:
            for key, value in params.items():
                self.state["config"][key] = value
            return (1, dict(self.state["config"]), None)
        except Exception as e:
            return (0, None, ("SET_CONFIG_ERROR", str(e), 0))


if __name__ == "__main__":
    ArgThreshold = SIMILARITY_THRESHOLD
    for Arg in sys.argv[1:]:
        if Arg.startswith("threshold="):
            try:
                ArgThreshold = float(Arg.split("=", 1)[1])
            except Exception:
                pass
    Orchestrator = Main()
    Ok, Data, Err = Orchestrator.Run("run", {"threshold": ArgThreshold})
    if Ok:
        Logger.info("Report written to %s", REPORT_PATH)
    else:
        Logger.error("Pipeline failed: %s", Err)
