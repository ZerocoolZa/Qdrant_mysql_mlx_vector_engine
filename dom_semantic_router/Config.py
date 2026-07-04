"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/dom_semantic_router/Config.py";"identity=Config";"purpose=Shared constants and paths for the MLX bge-small semantic domain router";"date=2026-06-26";"version=2.0";"author=Devin";"task=TASK-086")}
#[@VBSTYLE]{("auth=Devin";"role=domain_config";"return=Tuple3";"orch=none";"no=no_decorators|no_print|no_hardcoded|no_tabs|no_self_underscore";"model=one_class_one_domain_one_authority_complete")}
#[@CLASSES]{("Config")}
#[@METHODS]{("Run";"read_state";"set_config";"_p";"_Get")}
#[@DOMAIN]{("config")}
"""

import os
from pathlib import Path
from typing import Any, Dict, Tuple

BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent
CODE_STORE_DIR = PROJECT_DIR / "code_store_variations"

V20_DB_PATH = str(CODE_STORE_DIR / "v20_hybrid_best.db")
DOMAIN_GRAPH_DB_PATH = str(CODE_STORE_DIR / "domain_graph.db")

QDRANT_HOST = os.environ.get("DOM_QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("DOM_QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.environ.get("DOM_QDRANT_COLLECTION", "dom_class_code")

MODEL_ID = os.environ.get("DOM_MODEL_ID", "mlx-community/bge-small-en-v1.5-8bit")
EMBED_DIM = 384
MAX_TOKENS = 512
MAX_CHUNKS = int(os.environ.get("DOM_MAX_CHUNKS", "64"))
CHUNK_OVERLAP = int(os.environ.get("DOM_CHUNK_OVERLAP", "0"))

SIMILARITY_THRESHOLD = float(os.environ.get("DOM_THRESHOLD", "0.60"))
MIN_CENTROID_MEMBERS = int(os.environ.get("DOM_MIN_CENTROID_MEMBERS", "3"))

EMBED_BATCH_SIZE = int(os.environ.get("DOM_EMBED_BATCH", "16"))
QDRANT_UPSERT_BATCH = int(os.environ.get("DOM_QDRANT_BATCH", "64"))

TIER_TRUTH = 1
TIER_HYPOTHESIS = 3
METHOD_MLX_BGE = "mlx-bge-knn"

LAYER_TRUTH = "truth"
LAYER_HYPOTHESIS = "hypothesis"
LAYER_UNRESOLVED = "unresolved"

DEVICE_MLX_GPU = os.environ.get("DOM_DEVICE", "gpu")

LOG_PATH = str(BASE_DIR / "dom_semantic_router.log")


class Config:
    """Authority for shared configuration constants and path resolution."""

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
        if command == "get":
            return self._Get(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _Get(self, params):
        try:
            key = self._p(params, "key", "")
            attr_map = {
                "v20_db_path": V20_DB_PATH,
                "domain_graph_db_path": DOMAIN_GRAPH_DB_PATH,
                "qdrant_host": QDRANT_HOST,
                "qdrant_port": QDRANT_PORT,
                "qdrant_collection": QDRANT_COLLECTION,
                "model_id": MODEL_ID,
                "embed_dim": EMBED_DIM,
                "max_tokens": MAX_TOKENS,
                "max_chunks": MAX_CHUNKS,
                "chunk_overlap": CHUNK_OVERLAP,
                "similarity_threshold": SIMILARITY_THRESHOLD,
                "min_centroid_members": MIN_CENTROID_MEMBERS,
                "embed_batch_size": EMBED_BATCH_SIZE,
                "qdrant_upsert_batch": QDRANT_UPSERT_BATCH,
                "tier_truth": TIER_TRUTH,
                "tier_hypothesis": TIER_HYPOTHESIS,
                "method_mlx_bge": METHOD_MLX_BGE,
                "layer_truth": LAYER_TRUTH,
                "layer_hypothesis": LAYER_HYPOTHESIS,
                "layer_unresolved": LAYER_UNRESOLVED,
                "device_mlx_gpu": DEVICE_MLX_GPU,
                "log_path": LOG_PATH
            }
            if not key:
                return (1, dict(attr_map), None)
            value = attr_map.get(key)
            if value is None:
                return (0, None, ("KEY_NOT_FOUND", "Config key not found: " + str(key), 0))
            return (1, value, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))

    def read_state(self, params):
        return (1, dict(self.state), None)

    def set_config(self, params):
        try:
            for key, value in params.items():
                self.state["config"][key] = value
            return (1, dict(self.state["config"]), None)
        except Exception as e:
            return (0, None, ("SET_CONFIG_ERROR", str(e), 0))
