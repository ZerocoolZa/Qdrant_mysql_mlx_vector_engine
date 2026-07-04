#[@GHOST]{[@file<GhostQAEngine.py>][@domain<ghost_qa_engine>][@role<configurable_qa_pipeline>][@return<Tuple3>][@auth<cascade>][@date<2026-06-21>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<class>][@return<Tuple3>][@state<config,catalog,results,errors,meta,hardware,models>]}
#[@SPEC]{[@ref<QA_ENGINE_SPEC.md>][@sections<15>][@compliance<full>]}

import json
import os
import re
import sys
import time
import urllib.request
import platform
import subprocess
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Config_qa_engine import CONFIG_DICT as _DEFAULT_CONFIG, CONFIG_JSON_PATH

FAILURE_STAGES = [
    "DOCUMENT_LOAD", "CHUNKING", "EMBEDDING", "VECTOR_STORE",
    "RETRIEVAL", "RERANKING", "QA_EXTRACTION", "CLASSIFICATION",
    "RESOURCE_LIMIT", "NONE",
]

PIPELINE_MODES = {
    "A": ["embed", "search"],
    "B": ["embed", "search", "qa_extract", "classify"],
    "C": ["embed", "search", "qa_extract", "classify", "llm_format"],
    "D": ["embed", "search", "llm_extract", "classify"],
    "E": ["qa_extract", "classify"],
    "R": ["embed", "search", "route", "classify"],
}

MODE_NAMES = {
    "A": "retrieval_only",
    "B": "retrieval_qa",
    "C": "retrieval_qa_llm",
    "D": "retrieval_llm",
    "E": "qa_only",
    "R": "routed_auto",
}

STORAGE_MODES = ["ram_only", "persistent", "hybrid"]

EXECUTION_MODES = ["cpu", "gpu", "auto", "hybrid"]


class HardwareDetector:
    """Detects available hardware resources. No hardcoded assumptions."""

    def Run(self, command, params=None):
        if command == "detect":
            return self.Detect()
        if command == "read_state":
            return (1, self.state, None)
        return (0, None, ("UNKNOWN_COMMAND", f"HardwareDetector unknown: {command}", 0))

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "errors": [],
            "meta": {"detected": False},
        }

    def Detect(self):
        try:
            import multiprocessing
            cpu_cores = multiprocessing.cpu_count()
        except Exception:
            cpu_cores = 1

        ram_total_mb = 0
        ram_free_mb = 0
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
                )
                ram_total_mb = int(result.stdout.strip()) // (1024 * 1024)
                vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
                for line in vm.stdout.split("\n"):
                    if "free" in line.lower():
                        parts = line.split()
                        if len(parts) >= 3:
                            free_pages = int(parts[2].rstrip("."))
                            ram_free_mb = (free_pages * 4096) // (1024 * 1024)
                            break
            elif sys.platform.startswith("linux"):
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            ram_total_mb = int(line.split()[1]) // 1024
                        elif line.startswith("MemAvailable:"):
                            ram_free_mb = int(line.split()[1]) // 1024
                            break
        except Exception:
            pass

        gpu_available = False
        gpu_name = ""
        gpu_memory_mb = 0
        metal_available = False
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=10
                )
                output = result.stdout
                if "Apple" in output and ("Metal" in output or "GPU" in output):
                    gpu_available = True
                    metal_available = True
                    for line in output.split("\n"):
                        if "Chipset" in line or "VRAM" in line or "Total Number of Cores" in line:
                            gpu_name = line.strip()
                            break
                    if not gpu_name:
                        gpu_name = "Apple Silicon GPU"
        except Exception:
            pass

        disk_total_mb = 0
        disk_free_mb = 0
        try:
            usage = os.statvfs(os.path.expanduser("~"))
            disk_free_mb = (usage.f_bavail * usage.f_frsize) // (1024 * 1024)
            disk_total_mb = (usage.f_blocks * usage.f_frsize) // (1024 * 1024)
        except Exception:
            pass

        self.state["config"] = {
            "cpu_cores": cpu_cores,
            "ram_total_mb": ram_total_mb,
            "ram_free_mb": ram_free_mb,
            "gpu_available": gpu_available,
            "gpu_name": gpu_name,
            "gpu_memory_mb": gpu_memory_mb,
            "metal_available": metal_available,
            "disk_total_mb": disk_total_mb,
            "disk_free_mb": disk_free_mb,
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
        }
        self.state["meta"]["detected"] = True
        return (1, self.state["config"], None)


class ModelRegistry:
    """Loads and caches models by name from config registry. No hardcoded model names in execution paths."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "errors": [],
            "meta": {"loaded_models": {}},
        }
        self._cache = {}

    def Run(self, command, params=None):
        params = params or {}
        if command == "load":
            return self.LoadModel(params)
        if command == "get":
            return self.GetModel(params)
        if command == "list":
            return self.ListModels(params)
        if command == "unload":
            return self.UnloadModel(params)
        if command == "read_state":
            return (1, self.state, None)
        return (0, None, ("UNKNOWN_COMMAND", f"ModelRegistry unknown: {command}", 0))

    def LoadModel(self, params):
        model_type = params.get("model_type", "")
        model_key = params.get("model_key", "")
        registry = params.get("registry", {})

        if not model_type or not model_key or not registry:
            return (0, None, ("MISSING_PARAMS", "Need model_type, model_key, registry", 0))

        cache_key = f"{model_type}:{model_key}"
        if cache_key in self._cache:
            return (1, {"cached": True, "model": self._cache[cache_key]}, None)

        model_type_val = registry.get("type", "")
        try:
            if model_type_val == "sentence_transformer":
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer(registry["name"])
                self._cache[cache_key] = {"type": "embedding", "model": model, "dim": registry.get("dim", 384)}
            elif model_type_val == "coreml":
                import coremltools as ct
                model = ct.models.MLModel(registry["path"])
                self._cache[cache_key] = {"type": model_type, "model": model, "config": registry}
            elif model_type_val == "mlx":
                if model_type == "embedding":
                    from mlx_embedding_models import load as mlx_load
                    model = mlx_load(registry["name"])
                    self._cache[cache_key] = {"type": "embedding", "model": model, "dim": registry.get("dim", 384)}
                else:
                    from mlx_lm import load as mlx_load
                    model, tokenizer = mlx_load(registry["name"])
                    self._cache[cache_key] = {"type": "llm", "model": model, "tokenizer": tokenizer}
            elif model_type_val == "none":
                self._cache[cache_key] = {"type": "none", "model": None}
            else:
                return (0, None, ("UNKNOWN_MODEL_TYPE", f"Unknown model type: {model_type_val}", 0))
        except Exception as e:
            self.state["errors"].append(str(e))
            return (0, None, ("MODEL_LOAD_FAILED", str(e), 0))

        self.state["meta"]["loaded_models"][cache_key] = {
            "type": model_type,
            "key": model_key,
            "loaded_at": datetime.now().isoformat(),
        }
        return (1, {"cached": False, "model": self._cache[cache_key]}, None)

    def GetModel(self, params):
        model_type = params.get("model_type", "")
        model_key = params.get("model_key", "")
        cache_key = f"{model_type}:{model_key}"
        if cache_key not in self._cache:
            return (0, None, ("MODEL_NOT_LOADED", f"Model not loaded: {cache_key}", 0))
        return (1, self._cache[cache_key], None)

    def ListModels(self, params):
        return (1, list(self._cache.keys()), None)

    def UnloadModel(self, params):
        model_type = params.get("model_type", "")
        model_key = params.get("model_key", "")
        cache_key = f"{model_type}:{model_key}"
        if cache_key in self._cache:
            del self._cache[cache_key]
            self.state["meta"]["loaded_models"].pop(cache_key, None)
            return (1, "Model unloaded", None)
        return (0, None, ("MODEL_NOT_FOUND", f"Model not in cache: {cache_key}", 0))


class VectorBackend:
    """Abstract vector backend. Supports Qdrant, FAISS, SQLite Vector, RAM Index. No hardcoded backend."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"backend": "", "connection": {}},
            "catalog": [],
            "results": [],
            "errors": [],
            "meta": {"connected": False, "points_stored": 0},
        }
        self._ram_index = None
        self._ram_texts = None
        self._ram_ids = None

    def Run(self, command, params=None):
        params = params or {}
        if command == "connect":
            return self.Connect(params)
        if command == "upsert":
            return self.Upsert(params)
        if command == "search":
            return self.Search(params)
        if command == "delete_collection":
            return self.DeleteCollection(params)
        if command == "create_collection":
            return self.CreateCollection(params)
        if command == "count":
            return self.Count(params)
        if command == "read_state":
            return (1, self.state, None)
        return (0, None, ("UNKNOWN_COMMAND", f"VectorBackend unknown: {command}", 0))

    def Connect(self, params):
        backend = params.get("backend", "qdrant")
        config = params.get("config", {})

        self.state["config"]["backend"] = backend
        self.state["config"]["connection"] = config

        if backend == "qdrant":
            url = config.get("url", "") or os.environ.get("QDRANT_URL", "http://localhost:6333")
            try:
                req = urllib.request.Request(f"{url}/collections")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                self.state["meta"]["connected"] = True
                return (1, {"backend": "qdrant", "url": url, "collections": len(data["result"]["collections"])}, None)
            except Exception as e:
                self.state["errors"].append(str(e))
                return (0, None, ("VECTOR_STORE", f"Qdrant connect failed: {e}", 0))

        if backend == "ram":
            self._ram_index = None
            self._ram_texts = []
            self._ram_ids = []
            self.state["meta"]["connected"] = True
            return (1, {"backend": "ram", "points": 0}, None)

        if backend == "faiss":
            try:
                import faiss
                self.state["meta"]["connected"] = True
                return (1, {"backend": "faiss"}, None)
            except ImportError:
                return (0, None, ("VECTOR_STORE", "faiss not installed", 0))

        if backend == "sqlite_vector":
            path = config.get("path", "")
            if not path:
                return (0, None, ("VECTOR_STORE", "sqlite_vector requires path", 0))
            self.state["meta"]["connected"] = True
            return (1, {"backend": "sqlite_vector", "path": path}, None)

        return (0, None, ("UNKNOWN_BACKEND", f"Unknown backend: {backend}", 0))

    def CreateCollection(self, params):
        backend = self.state["config"]["backend"]
        name = params.get("name", "")
        dim = params.get("dim", 384)

        if not name:
            return (0, None, ("MISSING_PARAMS", "Need collection name", 0))

        if backend == "qdrant":
            url = self.state["config"]["connection"].get("url", "")
            try:
                try:
                    req = urllib.request.Request(f"{url}/collections/{name}", method="DELETE")
                    urllib.request.urlopen(req, timeout=10)
                except Exception:
                    pass
                payload = {"vectors": {"size": dim, "distance": "Cosine"}}
                req = urllib.request.Request(
                    f"{url}/collections/{name}",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="PUT",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    json.loads(resp.read().decode())
                return (1, f"Collection {name} created (dim={dim})", None)
            except Exception as e:
                return (0, None, ("VECTOR_STORE", str(e), 0))

        if backend == "ram":
            self._ram_index = None
            self._ram_texts = []
            self._ram_ids = []
            return (1, f"RAM collection {name} created", None)

        return (0, None, ("UNSUPPORTED", f"CreateCollection not supported for {backend}", 0))

    def Upsert(self, params):
        backend = self.state["config"]["backend"]
        collection = params.get("collection", "")
        points = params.get("points", [])

        if not points:
            return (0, None, ("MISSING_PARAMS", "No points to upsert", 0))

        if backend == "qdrant":
            url = self.state["config"]["connection"].get("url", "")
            try:
                batch_size = 50
                for i in range(0, len(points), batch_size):
                    batch = points[i:i + batch_size]
                    req = urllib.request.Request(
                        f"{url}/collections/{collection}/points?wait=true",
                        data=json.dumps({"points": batch}).encode(),
                        headers={"Content-Type": "application/json"},
                        method="PUT",
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        json.loads(resp.read().decode())
                self.state["meta"]["points_stored"] += len(points)
                return (1, {"upserted": len(points)}, None)
            except Exception as e:
                return (0, None, ("VECTOR_STORE", str(e), 0))

        if backend == "ram":
            if self._ram_index is None:
                vectors = np.array([p["vector"] for p in points])
                self._ram_index = vectors
                self._ram_texts = [p.get("payload", {}).get("text", "") for p in points]
                self._ram_ids = [p.get("id", i) for i, p in enumerate(points)]
            else:
                new_vectors = np.array([p["vector"] for p in points])
                self._ram_index = np.vstack([self._ram_index, new_vectors])
                self._ram_texts.extend([p.get("payload", {}).get("text", "") for p in points])
                self._ram_ids.extend([p.get("id", i) for i, p in enumerate(points)])
            self.state["meta"]["points_stored"] = len(self._ram_ids)
            return (1, {"upserted": len(points), "total": len(self._ram_ids)}, None)

        return (0, None, ("UNSUPPORTED", f"Upsert not supported for {backend}", 0))

    def Search(self, params):
        backend = self.state["config"]["backend"]
        collection = params.get("collection", "")
        vector = params.get("vector", [])
        top_k = params.get("top_k", 5)
        threshold = params.get("threshold", 0.0)

        if not vector:
            return (0, None, ("MISSING_PARAMS", "No search vector", 0))

        if backend == "qdrant":
            url = self.state["config"]["connection"].get("url", "")
            try:
                payload = {"vector": vector, "limit": top_k, "with_payload": True, "with_vector": False}
                req = urllib.request.Request(
                    f"{url}/collections/{collection}/points/search",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode())
                hits = result.get("result", [])
                filtered = [h for h in hits if h.get("score", 0) >= threshold]
                return (1, filtered, None)
            except Exception as e:
                return (0, None, ("RETRIEVAL", str(e), 0))

        if backend == "ram":
            if self._ram_index is None or len(self._ram_index) == 0:
                return (1, [], None)
            query_vec = np.array(vector)
            norms = np.linalg.norm(self._ram_index, axis=1) * np.linalg.norm(query_vec)
            norms[norms == 0] = 1
            scores = (self._ram_index @ query_vec) / norms
            top_indices = np.argsort(scores)[::-1][:top_k]
            hits = []
            for idx in top_indices:
                score = float(scores[idx])
                if score >= threshold:
                    hits.append({
                        "id": self._ram_ids[idx],
                        "score": score,
                        "payload": {"text": self._ram_texts[idx]},
                    })
            return (1, hits, None)

        return (0, None, ("UNSUPPORTED", f"Search not supported for {backend}", 0))

    def DeleteCollection(self, params):
        backend = self.state["config"]["backend"]
        name = params.get("name", "")
        if backend == "qdrant":
            url = self.state["config"]["connection"].get("url", "")
            try:
                req = urllib.request.Request(f"{url}/collections/{name}", method="DELETE")
                urllib.request.urlopen(req, timeout=10)
                return (1, f"Deleted {name}", None)
            except Exception:
                return (1, f"Collection {name} did not exist", None)
        if backend == "ram":
            self._ram_index = None
            self._ram_texts = []
            self._ram_ids = []
            return (1, "RAM index cleared", None)
        return (0, None, ("UNSUPPORTED", f"DeleteCollection not supported for {backend}", 0))

    def Count(self, params):
        backend = self.state["config"]["backend"]
        collection = params.get("collection", "")
        if backend == "qdrant":
            url = self.state["config"]["connection"].get("url", "")
            try:
                req = urllib.request.Request(f"{url}/collections/{collection}")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                return (1, data["result"]["points_count"], None)
            except Exception as e:
                return (0, None, ("VECTOR_STORE", str(e), 0))
        if backend == "ram":
            return (1, len(self._ram_ids) if self._ram_ids else 0, None)
        return (0, None, ("UNSUPPORTED", f"Count not supported for {backend}", 0))


class QueryInterpreter:
    """Classifies question type and rewrites presupposition errors.

    Based on empirical data from 5-mode experiment:
    - Negation questions ("Are X allowed?") need yes/no prompt formatting
    - "What is X used for?" presupposes X exists — rewrite to "What is the status of X?"
    - Code questions need exact token preservation
    - Temporal questions need explicit time framing

    This is the layer that fixes query semantics BEFORE inference begins.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "errors": [],
            "meta": {"queries_classified": 0, "rewrites_applied": 0},
        }

    def Run(self, command, params=None):
        params = params or {}
        if command == "classify":
            return self.Classify(params)
        if command == "rewrite":
            return self.Rewrite(params)
        if command == "interpret":
            return self.Interpret(params)
        if command == "read_state":
            return (1, self.state, None)
        return (0, None, ("UNKNOWN_COMMAND", f"QueryInterpreter unknown: {command}", 0))

    def Classify(self, params):
        question = params.get("question", "")
        if not question:
            return (0, None, ("EMPTY_QUESTION", "No question to classify", 0))

        self.state["meta"]["queries_classified"] += 1
        q_lower = question.lower().strip()

        qtype = "factual"
        features = []

        if any(q_lower.startswith(w) for w in ["are ", "is ", "was ", "were ", "do ", "does ", "did ", "can ", "could ", "should ", "may ", "might "]):
            qtype = "yes_no"
            features.append("yes_no_form")

        if any(w in q_lower for w in ["not ", "no ", "never", "forbidden", "prohibited", "allowed", "permitted", "okay", "ok to"]):
            if qtype != "yes_no":
                qtype = "negation"
            features.append("negation_present")

        if any(w in q_lower for w in ["what is", "what are", "what was", "what does", "what controls", "what governs", "what owns", "what belongs"]):
            qtype = "definition"
            features.append("definition_form")

        if any(w in q_lower for w in ["used for", "purpose of", "role of"]):
            qtype = "purpose"
            features.append("presupposition_exists")

        if any(w in q_lower for w in ["order", "sequence", "spine", "boot order", "steps"]):
            qtype = "sequence"
            features.append("sequential_structure")

        if any(w in q_lower for w in ["list", "what are the", "what are all", "enumerate"]):
            qtype = "list"
            features.append("list_structure")

        if any(w in q_lower for w in ["code", "signature", "constructor", "def ", "function", "method", "class ", "import"]):
            qtype = "code"
            features.append("code_tokens")

        if any(w in q_lower for w in ["port", "config", "flag", "parameter", "value", "number"]):
            if qtype == "factual":
                qtype = "config_lookup"
            features.append("config_token")

        if any(w in q_lower for w in ["old ", "new ", "current ", "previous ", "before", "after", "was renamed", "version"]):
            qtype = "temporal"
            features.append("temporal_comparison")

        if any(w in q_lower for w in ["how ", "why ", "explain", "describe"]):
            qtype = "explanatory"
            features.append("explanatory_form")

        if any(w in q_lower for w in ["who ", "where "]):
            qtype = "entity_lookup"
            features.append("entity_form")

        result = {
            "question": question,
            "qtype": qtype,
            "features": features,
        }
        self.state["results"].append(result)
        return (1, result, None)

    def Rewrite(self, params):
        question = params.get("question", "")
        qtype = params.get("qtype", "")
        if not question:
            return (0, None, ("EMPTY_QUESTION", "No question to rewrite", 0))

        rewritten = question

        if qtype == "purpose":
            # Case-insensitive replacement of presupposition phrases.
            # "used for" / "purpose of" / "role of" all presuppose existence —
            # rewrite to "status of" so the QA model can report non-existence.
            for phrase in ("used for", "purpose of", "role of"):
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                if pattern.search(question):
                    rewritten = pattern.sub("status of", question)
                    break

        if qtype == "yes_no" and not rewritten.endswith("?"):
            rewritten = rewritten + "?"

        # Only flag as applied if the text actually changed
        rewrite_applied = rewritten != question

        if rewrite_applied:
            self.state["meta"]["rewrites_applied"] += 1

        return (1, {
            "original": question,
            "rewritten": rewritten,
            "rewrite_applied": rewrite_applied,
        }, None)

    def Interpret(self, params):
        """Combined classify + rewrite in one call."""
        ok, classification, err = self.Classify(params)
        if not ok:
            return (0, None, err)

        ok, rewrite, err = self.Rewrite({
            "question": params.get("question", ""),
            "qtype": classification["qtype"],
        })
        if not ok:
            return (0, None, err)

        return (1, {
            "qtype": classification["qtype"],
            "features": classification["features"],
            "original_question": rewrite["original"],
            "effective_question": rewrite["rewritten"],
            "rewrite_applied": rewrite["rewrite_applied"],
        }, None)


class ModeRouter:
    """Routes questions to the best cognitive mode based on question type.

    Routing rules derived from empirical 5-mode experiment data:

    Route to BERT (Mode B) when:
    - negation questions (BERT captures "NO X" spans directly)
    - config_lookup (ports, flags, exact values)
    - near-miss disambiguation needed
    - yes_no questions where literal span contains the answer

    Route to Qwen (Mode D) when:
    - sequence/list questions (Qwen reconstructs structure)
    - code questions (Qwen preserves token boundaries)
    - temporal questions (Qwen distinguishes old vs current)
    - definition questions (Qwen synthesizes multi-fact answers)
    - explanatory questions (Qwen understands context)
    - conversation/decision questions (Qwen interprets intent)
    - unknown detection matters (Qwen says NOT FOUND, BERT hallucinates)

    Route to Retrieval Only (Mode A) when:
    - entity_lookup with high confidence (just need the chunk)

    Fallback: if primary mode returns NOT FOUND/low confidence, try the other.
    """

    BERT_TYPES = {"negation", "config_lookup"}
    QWEN_TYPES = {"sequence", "list", "code", "temporal", "definition", "explanatory", "purpose", "yes_no"}
    RETRIEVAL_TYPES = {"entity_lookup"}  # entity lookup — chunk retrieval is sufficient

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "errors": [],
            "meta": {"routes_decided": 0, "bert_routes": 0, "qwen_routes": 0, "retrieval_routes": 0, "fallbacks": 0},
        }

    def Run(self, command, params=None):
        params = params or {}
        if command == "route":
            return self.Route(params)
        if command == "read_state":
            return (1, self.state, None)
        return (0, None, ("UNKNOWN_COMMAND", f"ModeRouter unknown: {command}", 0))

    def Route(self, params):
        qtype = params.get("qtype", "")
        features = params.get("features", [])
        if not qtype:
            return (0, None, ("MISSING_QTYPE", "No question type provided", 0))

        self.state["meta"]["routes_decided"] += 1

        primary_mode = "D"
        fallback_mode = "B"
        reason = ""

        if qtype in self.BERT_TYPES:
            primary_mode = "B"
            fallback_mode = "D"
            reason = f"qtype={qtype} → BERT excels at literal span extraction for this type"
            self.state["meta"]["bert_routes"] += 1
        elif qtype in self.QWEN_TYPES:
            primary_mode = "D"
            fallback_mode = "B"
            reason = f"qtype={qtype} → Qwen excels at structural reasoning for this type"
            self.state["meta"]["qwen_routes"] += 1
        elif qtype in self.RETRIEVAL_TYPES:
            primary_mode = "A"
            fallback_mode = "D"
            reason = f"qtype={qtype} → retrieval sufficient for entity lookup"
            self.state["meta"]["retrieval_routes"] += 1
        else:
            primary_mode = "D"
            fallback_mode = "B"
            reason = f"qtype={qtype} → default to Qwen (structural reasoning)"
            self.state["meta"]["qwen_routes"] += 1

        if "presupposition_exists" in features and primary_mode == "D":
            reason += " | presupposition detected → Qwen handles non-existence better"

        result = {
            "qtype": qtype,
            "primary_mode": primary_mode,
            "fallback_mode": fallback_mode,
            "reason": reason,
            "features": features,
        }
        self.state["results"].append(result)
        return (1, result, None)


class GhostQAEngine:
    """Configurable QA Engine. All models, backends, thresholds from config. No hardcoded names in execution paths.

    Architecture (per QA_ENGINE_SPEC.md):
        Question -> [EMBED] -> [SEARCH] -> [QA_EXTRACT] -> [CLASSIFY] -> [LLM_FORMAT?]
        Every stage configurable. Every model replaceable. Every failure attributed.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "errors": [],
            "meta": {
                "questions_asked": 0,
                "answers_found": 0,
                "mode_correct": 0,
                "failure_stages": {},
                "latencies": {"embed": [], "search": [], "qa": [], "total": []},
            },
            "hardware": {},
            "models": {},
        }
        self._config_path = param.get("config_path", CONFIG_JSON_PATH) if param else CONFIG_JSON_PATH
        self._hw = HardwareDetector()
        self._registry = ModelRegistry()
        self._backend = VectorBackend()
        self._interpreter = QueryInterpreter()
        self._router = ModeRouter()
        self._tokenizer = None

    def Run(self, command, params=None):
        params = params or {}
        if command == "init":
            return self.InitEngine(params)
        if command == "ask":
            return self.AskQuestion(params)
        if command == "embed":
            return self.EmbedText(params)
        if command == "search":
            return self.SearchChunks(params)
        if command == "extract":
            return self.ExtractAnswer(params)
        if command == "ingest":
            return self.IngestDocument(params)
        if command == "explain":
            return self.ExplainAnswer(params)
        if command == "interpret":
            return self._interpreter.Run("interpret", params)
        if command == "route":
            return self._router.Run("route", params)
        if command == "read_state":
            return (1, self.state, None)
        if command == "read_config":
            return (1, self.state["config"], None)
        if command == "set_config":
            return self.SetConfig(params.get("config"))
        if command == "reload_config":
            return self.ReloadConfig()
        if command == "detect_hardware":
            return self.DetectHardware()
        if command == "read_hardware":
            return (1, self.state["hardware"], None)
        return (0, None, ("UNKNOWN_COMMAND", f"GhostQAEngine unknown: {command}", 0))

    def _LoadConfig(self):
        try:
            with open(self._config_path) as f:
                return json.load(f)
        except Exception:
            import copy
            return copy.deepcopy(_DEFAULT_CONFIG)

    def InitEngine(self, params):
        config = self._LoadConfig()
        if "error" in config:
            return (0, None, ("DOCUMENT_LOAD", f"Config load failed: {config['error']}", 0))

        self.state["config"] = config

        if config.get("hardware", {}).get("detect_on_init", False):
            ok, hw, err = self._hw.Run("detect")
            if ok:
                self.state["hardware"] = hw

        storage_config = config.get("storage", {})
        backend_name = storage_config.get("vector_backend", "qdrant")
        backend_config = storage_config.get("backends", {}).get(backend_name, {})
        ok, _, err = self._backend.Run("connect", {"backend": backend_name, "config": backend_config})
        if not ok:
            self.state["errors"].append(f"Backend connect: {err}")
            return (0, None, err)

        emb_active = config.get("models", {}).get("embedding", {}).get("active", "")
        emb_registry = config.get("models", {}).get("embedding", {}).get("registry", {})
        if emb_active and emb_active in emb_registry:
            ok, _, err = self._registry.Run("load", {
                "model_type": "embedding",
                "model_key": emb_active,
                "registry": emb_registry[emb_active],
            })
            if not ok:
                self.state["errors"].append(f"Embedding model load: {err}")

        qa_active = config.get("models", {}).get("qa", {}).get("active", "")
        qa_registry = config.get("models", {}).get("qa", {}).get("registry", {})
        if qa_active and qa_active in qa_registry:
            ok, _, err = self._registry.Run("load", {
                "model_type": "qa",
                "model_key": qa_active,
                "registry": qa_registry[qa_active],
            })
            if not ok:
                self.state["errors"].append(f"QA model load: {err}")

            qa_cfg = qa_registry[qa_active]
            tokenizer_name = qa_cfg.get("tokenizer", "")
            if tokenizer_name:
                try:
                    from transformers import BertTokenizer
                    self._tokenizer = BertTokenizer.from_pretrained(tokenizer_name)
                except Exception as e:
                    self.state["errors"].append(f"Tokenizer load: {e}")

        llm_active = config.get("models", {}).get("llm", {}).get("active", "")
        llm_enabled = config.get("models", {}).get("llm", {}).get("enabled", False)
        llm_registry = config.get("models", {}).get("llm", {}).get("registry", {})
        if llm_enabled and llm_active and llm_active in llm_registry:
            ok, _, err = self._registry.Run("load", {
                "model_type": "llm",
                "model_key": llm_active,
                "registry": llm_registry[llm_active],
            })
            if not ok:
                self.state["errors"].append(f"LLM model load: {err}")

        return (1, {
            "config_loaded": True,
            "hardware_detected": bool(self.state["hardware"]),
            "backend": backend_name,
            "embedding_model": emb_active,
            "qa_model": qa_active,
            "llm_model": llm_active if llm_enabled else "disabled",
            "pipeline_mode": config.get("pipeline", {}).get("mode", "retrieval_qa"),
        }, None)

    def ReloadConfig(self):
        config = self._LoadConfig()
        if "error" in config:
            return (0, None, ("DOCUMENT_LOAD", f"Config reload failed: {config['error']}", 0))
        self.state["config"] = config
        return (1, "Config reloaded", None)

    def SetConfig(self, config):
        if not config:
            return (0, None, ("EMPTY_CONFIG", "No config provided", 0))
        self.state["config"].update(config)
        return (1, "Config updated", None)

    def DetectHardware(self):
        ok, hw, err = self._hw.Run("detect")
        if ok:
            self.state["hardware"] = hw
        return (ok, hw, err)

    def _GetEmbedder(self):
        emb_active = self.state["config"].get("models", {}).get("embedding", {}).get("active", "")
        ok, model_data, err = self._registry.Run("get", {"model_type": "embedding", "model_key": emb_active})
        if not ok:
            return None, err
        return model_data, None

    def _GetQAModel(self):
        qa_active = self.state["config"].get("models", {}).get("qa", {}).get("active", "")
        ok, model_data, err = self._registry.Run("get", {"model_type": "qa", "model_key": qa_active})
        if not ok:
            return None, err
        return model_data, None

    def _GetLLM(self):
        llm_active = self.state["config"].get("models", {}).get("llm", {}).get("active", "")
        llm_enabled = self.state["config"].get("models", {}).get("llm", {}).get("enabled", False)
        if not llm_enabled:
            return None, None
        ok, model_data, err = self._registry.Run("get", {"model_type": "llm", "model_key": llm_active})
        if not ok:
            return None, err
        return model_data, None

    def EmbedText(self, params):
        text = params.get("text", "")
        if not text:
            return (0, None, ("EMPTY_TEXT", "No text to embed", 0))

        embedder_data, err = self._GetEmbedder()
        if err:
            return (0, None, err)

        t0 = time.time()
        model = embedder_data["model"]
        model_type = embedder_data.get("type", "")

        if model_type == "embedding" and hasattr(model, "encode"):
            vec = model.encode([text])[0].tolist()
        elif model_type == "coreml":
            vec = self._EmbedCoreML(model, text)
        else:
            return (0, None, ("EMBEDDING", f"Unsupported embedder type: {model_type}", 0))

        latency = (time.time() - t0) * 1000
        self.state["meta"]["latencies"]["embed"].append(latency)
        return (1, vec, None)

    def _EmbedCoreML(self, model, text):
        try:
            output = model.predict({"input": text})
            for key in ["embeddings", "output", "result"]:
                if key in output:
                    return output[key].flatten().tolist()
        except Exception:
            pass
        return []

    def SearchChunks(self, params):
        question = params.get("question", "")
        vector = params.get("vector", [])
        collection = params.get("collection", "")
        top_k = params.get("top_k", self.state["config"].get("retrieval", {}).get("top_k", 5))
        threshold = params.get("threshold", self.state["config"].get("retrieval", {}).get("similarity_threshold", 0.30))

        if not vector and question:
            ok, vec, err = self.EmbedText({"text": question})
            if not ok:
                return (0, None, err)
            vector = vec

        if not vector:
            return (0, None, ("EMPTY_VECTOR", "No vector to search", 0))

        if not collection:
            storage = self.state["config"].get("storage", {})
            collection = storage.get("backends", {}).get(
                storage.get("vector_backend", "qdrant"), {}
            ).get("default_collection", "")

        t0 = time.time()
        ok, hits, err = self._backend.Run("search", {
            "collection": collection,
            "vector": vector,
            "top_k": top_k,
            "threshold": threshold,
        })
        latency = (time.time() - t0) * 1000
        self.state["meta"]["latencies"]["search"].append(latency)

        if not ok:
            return (0, None, err)

        chunks = []
        for hit in hits:
            pd = hit.get("payload", {})
            text = ""
            for key in ["text", "content", "sample_row", "filename", "source_table"]:
                if key in pd:
                    text = str(pd[key])
                    break
            if text:
                chunks.append({
                    "source": f"{self.state['config'].get('storage',{}).get('vector_backend','')}:{collection}",
                    "score": hit.get("score", 0),
                    "text": text,
                    "id": hit.get("id"),
                })
        return (1, chunks, None)

    def ExtractAnswer(self, params):
        question = params.get("question", "")
        context = params.get("context", "")
        if not question or not context:
            return (0, None, ("MISSING_PARAMS", "Need question and context", 0))
        if len(context.strip()) < 10:
            return (0, None, ("CONTEXT_TOO_SHORT", "Context is too short", 0))

        qa_data, err = self._GetQAModel()
        if err:
            return (0, None, err)

        qa_cfg = self.state["config"].get("qa", {})
        max_length = qa_cfg.get("max_length", 384)

        if self._tokenizer is None:
            return (0, None, ("QA_EXTRACTION", "Tokenizer not loaded", 0))

        t0 = time.time()
        try:
            encoded = self._tokenizer(
                question, context,
                add_special_tokens=True,
                return_tensors="np",
                max_length=max_length,
                truncation=True,
                padding="max_length",
            )
            word_ids = encoded["input_ids"].astype(np.float32)
            word_types = encoded["token_type_ids"].astype(np.float32)

            model = qa_data["model"]
            output = model.predict({"wordIDs": word_ids, "wordTypes": word_types})

            start_logits = output["startLogits"][0]
            end_logits = output["endLogits"][0]
            start_idx = int(np.argmax(start_logits))
            end_idx = int(np.argmax(end_logits)) + 1
            if end_idx <= start_idx:
                end_idx = start_idx + 1

            answer_tokens = encoded["input_ids"][0][start_idx:end_idx]
            answer = self._tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

            start_score = float(np.max(start_logits))
            end_score = float(np.max(end_logits))
            confidence = (start_score + end_score) / 2
        except Exception as e:
            latency = (time.time() - t0) * 1000
            self.state["meta"]["latencies"]["qa"].append(latency)
            return (0, None, ("QA_EXTRACTION", str(e), 0))

        latency = (time.time() - t0) * 1000
        self.state["meta"]["latencies"]["qa"].append(latency)
        return (1, {"answer": answer, "confidence": confidence}, None)

    def LLMExtract(self, params):
        """Mode D: LLM as QA extractor (evidence-locked synthesis, not free generation).
        
        Unlike ExplainAnswer which formats an already-extracted answer,
        LLMExtract reads the evidence chunks and produces the answer directly.
        No BERT QA span extraction involved.
        """
        question = params.get("question", "")
        chunks = params.get("chunks", [])
        if not question:
            return (0, None, ("EMPTY_QUESTION", "No question provided", 0))
        if not chunks:
            return (0, None, ("EMPTY_CHUNKS", "No evidence chunks provided", 0))

        llm_data, err = self._GetLLM()
        if err or llm_data is None:
            return (0, None, ("LLM_NOT_AVAILABLE", "LLM not loaded or not enabled", 0))

        evidence = " ".join(chunk["text"] for chunk in chunks[:3])
        if len(evidence) > 3000:
            evidence = evidence[:3000]

        llm_cfg = self.state["config"].get("models", {}).get("llm", {}).get("registry", {}).get(
            self.state["config"].get("models", {}).get("llm", {}).get("active", ""), {}
        )
        max_tokens = llm_cfg.get("max_tokens", 200)

        t0 = time.time()
        try:
            from mlx_lm import generate as mlx_generate

            messages = [
                {
                    "role": "system",
                    "content": "You are a precise question answering system. Answer using ONLY information from the provided evidence. Be concise. If the answer is not in the evidence, respond with exactly: NOT FOUND"
                },
                {
                    "role": "user",
                    "content": f"Evidence: {evidence}\n\nQuestion: {question}\n\nAnswer (from evidence only):"
                }
            ]
            prompt = llm_data["tokenizer"].apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            response = mlx_generate(
                llm_data["model"], llm_data["tokenizer"],
                prompt=prompt, max_tokens=max_tokens, verbose=False,
            )
            answer = response.strip().replace("<|im_end|>", "").strip()

            if "NOT FOUND" in answer.upper():
                confidence = -1.0
                answer = "NOT FOUND"
            elif len(answer) < 20:
                confidence = 7.0
            elif len(answer) < 100:
                confidence = 6.0
            else:
                confidence = 5.0
        except Exception as e:
            latency = (time.time() - t0) * 1000
            self.state["meta"]["latencies"]["qa"].append(latency)
            return (0, None, ("QA_EXTRACTION", f"LLM extract failed: {e}", 0))

        latency = (time.time() - t0) * 1000
        self.state["meta"]["latencies"]["qa"].append(latency)
        return (1, {"answer": answer, "confidence": confidence}, None)

    def AskQuestion(self, params):
        """Full 5-mode inference graph. Mode is selected from config.pipeline.mode.
        
        Mode A: embed -> search (retrieval only)
        Mode B: embed -> search -> qa_extract -> classify (BERT QA)
        Mode C: embed -> search -> qa_extract -> classify -> llm_format (BERT + LLM)
        Mode D: embed -> search -> llm_extract -> classify (LLM only, no BERT)
        Mode E: qa_extract -> classify (direct QA, no embeddings)
        
        Graceful degradation: if a model is not loaded, the stage is skipped
        and the system degrades to the best available mode.
        """
        question = params.get("question", "")
        if not question:
            return (0, None, ("EMPTY_QUESTION", "No question provided", 0))

        self.state["meta"]["questions_asked"] += 1
        pipeline_mode = params.get("pipeline_mode", "") or self.state["config"].get("pipeline", {}).get("mode", "B")
        stages = PIPELINE_MODES.get(pipeline_mode, PIPELINE_MODES["B"])

        failure_stage = "NONE"
        total_t0 = time.time()
        latencies = {"embed": 0, "search": 0, "qa": 0, "llm": 0}

        chunks = []
        vec = []

        # ─── MODE E: QA ONLY (no embeddings, no retrieval) ───
        if pipeline_mode == "E":
            context = params.get("context", "")
            if not context:
                return (0, None, ("MISSING_PARAMS", "Mode E requires context param", 0))

            ok, result, err = self.ExtractAnswer({"question": question, "context": context})
            if not ok:
                self._RecordFailure("QA_EXTRACTION")
                return (0, None, err)

            answer = result["answer"]
            confidence = result["confidence"]
            final_mode = self._Classify(answer, confidence, None)
            total_ms = round((time.time() - total_t0) * 1000, 2)

            answer_data = {
                "question": question, "found": final_mode == "TRUE",
                "answer": answer, "confidence": round(confidence, 4),
                "mode": final_mode, "failure_stage": "NONE" if final_mode == "TRUE" else "QA_EXTRACTION",
                "chunks_searched": 0, "evidence": context[:300],
                "latency_ms": total_ms, "pipeline_mode": "E",
            }
            self.state["results"].append(answer_data)
            if final_mode != "TRUE":
                self._RecordFailure("QA_EXTRACTION")
            return (1, answer_data, None)

        # ─── STAGE: EMBED ───
        if "embed" in stages:
            embedder_data, emb_err = self._GetEmbedder()
            if emb_err or embedder_data is None:
                failure_stage = "EMBEDDING"
                self._RecordFailure(failure_stage)
                return (0, None, ("EMBEDDING", "Embedding model not available", 0))

            t0 = time.time()
            ok, vec, err = self.EmbedText({"text": question})
            latencies["embed"] = (time.time() - t0) * 1000
            if not ok:
                failure_stage = "EMBEDDING"
                self._RecordFailure(failure_stage)
                return (0, None, err)

        # ─── STAGE: SEARCH ───
        if "search" in stages:
            t0 = time.time()
            ok, chunks, err = self.SearchChunks({"vector": vec, "collection": params.get("collection", "")})
            latencies["search"] = (time.time() - t0) * 1000
            if not ok:
                failure_stage = "RETRIEVAL"
                self._RecordFailure(failure_stage)
                return (0, None, err)

            if not chunks:
                result = {
                    "question": question, "found": False, "answer": "Not Found",
                    "confidence": -999.0, "chunks_searched": 0,
                    "mode": "UNKNOWN", "failure_stage": "RETRIEVAL",
                    "latency_ms": round((time.time() - total_t0) * 1000, 2),
                    "pipeline_mode": pipeline_mode,
                }
                self.state["results"].append(result)
                self._RecordFailure("RETRIEVAL")
                return (1, result, None)

        # ─── MODE A: RETRIEVAL ONLY ───
        if pipeline_mode == "A" or ("qa_extract" not in stages and "llm_extract" not in stages and "route" not in stages):
            total_ms = round((time.time() - total_t0) * 1000, 2)
            answer_data = {
                "question": question, "found": True, "answer": None,
                "chunks": chunks, "mode": "RETRIEVAL_ONLY",
                "chunks_searched": len(chunks),
                "top_score": round(chunks[0]["score"], 4) if chunks else 0,
                "latency_ms": total_ms, "pipeline_mode": "A",
            }
            self.state["results"].append(answer_data)
            return (1, answer_data, None)

        # ─── MODE R: ROUTED AUTO (interpret → route → execute → fallback) ───
        if pipeline_mode == "R":
            return self._ExecuteRoutedMode(question, chunks, params, total_t0, latencies)

        # ─── STAGE: QA_EXTRACT (BERT SQuAD — Mode B, C) ───
        best_answer = ""
        best_confidence = -999.0
        best_chunk = None

        if "qa_extract" in stages:
            qa_data, qa_err = self._GetQAModel()
            if qa_err or qa_data is None:
                # Graceful degradation: fall through to LLM extract if available
                if "llm_extract" not in stages:
                    failure_stage = "QA_EXTRACTION"
                    self._RecordFailure(failure_stage)
                    return (0, None, ("QA_EXTRACTION", "QA model not available and no LLM fallback", 0))
                # Add llm_extract to stages as fallback
                stages = stages + ["llm_extract"]
            else:
                t0 = time.time()
                for chunk in chunks:
                    ok, result, err = self.ExtractAnswer({
                        "question": question, "context": chunk["text"],
                    })
                    if ok and result["answer"]:
                        if result["confidence"] > best_confidence:
                            best_answer = result["answer"]
                            best_confidence = result["confidence"]
                            best_chunk = chunk
                latencies["qa"] = (time.time() - t0) * 1000

        # ─── STAGE: LLM_EXTRACT (Mode D — LLM as primary QA) ───
        if "llm_extract" in stages:
            llm_data, llm_err = self._GetLLM()
            if llm_err or llm_data is None:
                if not best_answer:
                    failure_stage = "QA_EXTRACTION"
                    self._RecordFailure(failure_stage)
                    return (0, None, ("QA_EXTRACTION", "LLM not available and no BERT fallback", 0))
                # Fall back to BERT answer if we have one
            else:
                t0 = time.time()
                ok, result, err = self.LLMExtract({
                    "question": question, "chunks": chunks,
                })
                latencies["llm"] = (time.time() - t0) * 1000
                if ok:
                    best_answer = result["answer"]
                    best_confidence = result["confidence"]
                    best_chunk = chunks[0] if chunks else None

        # ─── STAGE: CLASSIFY ───
        final_mode = self._Classify(best_answer, best_confidence, None)
        found = final_mode == "TRUE"

        if not found:
            if not best_answer or best_confidence < 0:
                failure_stage = "QA_EXTRACTION"
            elif best_confidence < self.state["config"].get("classification", {}).get("unknown_threshold", 0.0):
                failure_stage = "THRESHOLD"
            else:
                failure_stage = "QA_EXTRACTION"

        answer_data = {
            "question": question,
            "found": found,
            "answer": best_answer if found else "Not Found",
            "confidence": round(best_confidence, 4),
            "mode": final_mode,
            "failure_stage": failure_stage if not found else "NONE",
            "source": best_chunk["source"] if best_chunk else None,
            "source_score": round(best_chunk["score"], 4) if best_chunk else 0,
            "chunks_searched": len(chunks),
            "evidence": best_chunk["text"][:300] if best_chunk else None,
            "explained": None,
            "latency_embed": round(latencies["embed"], 2),
            "latency_search": round(latencies["search"], 2),
            "latency_qa": round(latencies["qa"] + latencies["llm"], 2),
            "latency_ms": round((time.time() - total_t0) * 1000, 2),
            "pipeline_mode": pipeline_mode,
        }

        # ─── STAGE: LLM_FORMAT (Mode C — format BERT answer with LLM) ───
        if "llm_format" in stages and found:
            llm_data, llm_err = self._GetLLM()
            if llm_data and llm_err is None:
                ok, explained, err = self.ExplainAnswer({
                    "question": question,
                    "evidence": best_chunk["text"] if best_chunk else "",
                    "extracted": best_answer,
                })
                if ok:
                    answer_data["explained"] = explained

        self.state["results"].append(answer_data)
        if found:
            self.state["meta"]["answers_found"] += 1
        else:
            self._RecordFailure(failure_stage)

        total_latency = (time.time() - total_t0) * 1000
        self.state["meta"]["latencies"]["total"].append(total_latency)

        return (1, answer_data, None)

    def _Classify(self, answer, confidence, expected_answer):
        """Classify result as TRUE/FALSE/UNKNOWN based on confidence thresholds."""
        classification_cfg = self.state["config"].get("classification", {})
        true_threshold = classification_cfg.get("true_threshold", 5.0)
        unknown_threshold = classification_cfg.get("unknown_threshold", 0.0)

        if not answer or "NOT FOUND" in answer.upper():
            return "UNKNOWN"
        if confidence < unknown_threshold:
            return "UNKNOWN"
        if confidence >= true_threshold:
            return "TRUE"
        return "FALSE"

    def _ExecuteRoutedMode(self, question, chunks, params, total_t0, latencies):
        """Mode R: Query interpretation + mode routing + BERT fallback.

        Flow:
        1. Interpret question (classify type + rewrite presuppositions)
        2. Route to primary mode (BERT or Qwen based on question type)
        3. Execute primary mode
        4. If primary returns NOT FOUND / low confidence, try fallback mode
        5. Classify and return
        """
        # Step 1: Interpret
        ok, interpretation, err = self._interpreter.Run("interpret", {"question": question})
        if not ok:
            self._RecordFailure("CLASSIFICATION")
            return (0, None, err)

        qtype = interpretation["qtype"]
        features = interpretation["features"]
        effective_question = interpretation["effective_question"]

        # Step 2: Route
        ok, routing, err = self._router.Run("route", {"qtype": qtype, "features": features})
        if not ok:
            self._RecordFailure("CLASSIFICATION")
            return (0, None, err)

        primary_mode = routing["primary_mode"]
        fallback_mode = routing["fallback_mode"]

        # Step 3: Execute primary mode
        best_answer = ""
        best_confidence = -999.0
        best_chunk = None
        used_mode = primary_mode
        used_fallback = False

        if primary_mode == "B":
            best_answer, best_confidence, best_chunk, qa_ms = self._ExecuteBERT(effective_question, chunks)
            latencies["qa"] = qa_ms
        elif primary_mode == "D":
            best_answer, best_confidence, best_chunk, qa_ms = self._ExecuteQwen(effective_question, chunks, qtype)
            latencies["llm"] = qa_ms
        elif primary_mode == "A":
            total_ms = round((time.time() - total_t0) * 1000, 2)
            answer_data = {
                "question": question, "found": True, "answer": None,
                "chunks": chunks, "mode": "RETRIEVAL_ONLY",
                "chunks_searched": len(chunks),
                "top_score": round(chunks[0]["score"], 4) if chunks else 0,
                "latency_ms": total_ms, "pipeline_mode": "R",
                "routed_to": "A", "qtype": qtype,
            }
            self.state["results"].append(answer_data)
            return (1, answer_data, None)

        # Step 4: Fallback if primary failed or gave suspiciously short answer
        needs_fallback = False
        if not best_answer or "NOT FOUND" in best_answer.upper() or best_confidence < 0:
            needs_fallback = True
        # If Qwen answered with just "Yes" or "No" on a non-yes/no question, that's a prompt leak — try BERT
        if qtype != "yes_no" and best_answer and best_answer.strip().rstrip(".").lower() in ("yes", "no"):
            needs_fallback = True

        if needs_fallback and chunks:
            self._router.state["meta"]["fallbacks"] += 1
            used_fallback = True

            if fallback_mode == "B" and primary_mode != "B":
                fb_answer, fb_conf, fb_chunk, fb_ms = self._ExecuteBERT(effective_question, chunks)
                latencies["qa"] += fb_ms
            elif fallback_mode == "D" and primary_mode != "D":
                fb_answer, fb_conf, fb_chunk, fb_ms = self._ExecuteQwen(effective_question, chunks, qtype)
                latencies["llm"] += fb_ms
            else:
                fb_answer, fb_conf, fb_chunk = "", -999.0, None

            if fb_conf > best_confidence and fb_answer and "NOT FOUND" not in fb_answer.upper():
                best_answer = fb_answer
                best_confidence = fb_conf
                best_chunk = fb_chunk
                used_mode = fallback_mode

        # Step 5: Classify
        final_mode = self._Classify(best_answer, best_confidence, None)
        found = final_mode == "TRUE"

        failure_stage = "NONE"
        if not found:
            if not best_answer or best_confidence < 0:
                failure_stage = "QA_EXTRACTION"
            elif best_confidence < self.state["config"].get("classification", {}).get("unknown_threshold", 0.0):
                failure_stage = "THRESHOLD"
            else:
                failure_stage = "QA_EXTRACTION"

        total_ms = round((time.time() - total_t0) * 1000, 2)
        answer_data = {
            "question": question,
            "found": found,
            "answer": best_answer if found else "Not Found",
            "confidence": round(best_confidence, 4),
            "mode": final_mode,
            "failure_stage": failure_stage,
            "source": best_chunk["source"] if best_chunk else None,
            "source_score": round(best_chunk["score"], 4) if best_chunk else 0,
            "chunks_searched": len(chunks),
            "evidence": best_chunk["text"][:300] if best_chunk else None,
            "latency_embed": round(latencies["embed"], 2),
            "latency_search": round(latencies["search"], 2),
            "latency_qa": round(latencies["qa"] + latencies["llm"], 2),
            "latency_ms": total_ms,
            "pipeline_mode": "R",
            "qtype": qtype,
            "routed_to": used_mode,
            "fallback_used": used_fallback,
            "rewrite_applied": interpretation["rewrite_applied"],
            "effective_question": effective_question if interpretation["rewrite_applied"] else None,
        }

        self.state["results"].append(answer_data)
        if found:
            self.state["meta"]["answers_found"] += 1
        else:
            self._RecordFailure(failure_stage)

        self.state["meta"]["latencies"]["total"].append(total_ms)
        return (1, answer_data, None)

    def _ExecuteBERT(self, question, chunks):
        """Run BERT QA extraction on all chunks, return best."""
        best_answer = ""
        best_confidence = -999.0
        best_chunk = None
        t0 = time.time()

        for chunk in chunks:
            ok, result, err = self.ExtractAnswer({"question": question, "context": chunk["text"]})
            if ok and result["answer"]:
                if result["confidence"] > best_confidence:
                    best_answer = result["answer"]
                    best_confidence = result["confidence"]
                    best_chunk = chunk

        qa_ms = (time.time() - t0) * 1000
        return best_answer, best_confidence, best_chunk, qa_ms

    def _ExecuteQwen(self, question, chunks, qtype=None):
        """Run Qwen evidence-locked extraction with improved prompt contract."""
        best_chunk = chunks[0] if chunks else None
        t0 = time.time()

        llm_data, err = self._GetLLM()
        if err or llm_data is None:
            return "", -999.0, None, (time.time() - t0) * 1000

        evidence = " ".join(chunk["text"] for chunk in chunks[:3])
        if len(evidence) > 3000:
            evidence = evidence[:3000]

        llm_cfg = self.state["config"].get("models", {}).get("llm", {}).get("registry", {}).get(
            self.state["config"].get("models", {}).get("llm", {}).get("active", ""), {}
        )
        max_tokens = llm_cfg.get("max_tokens", 200)

        # Improved prompt contract — adapts based on question type
        base_rules = (
            "You are a precise question answering system. "
            "Answer using ONLY information from the provided evidence. "
            "Be concise.\n\n"
            "Rules:\n"
            "- If the evidence says something does not exist, is a typo, or is an error, report that as the answer.\n"
            "- If the evidence describes what something is NOT, report what it IS (including 'a typo', 'an error', 'does not exist').\n"
            "- For questions about order or sequence, list all items in order.\n"
            "- For questions about what belongs under something, list all components.\n"
            "- For code questions, preserve exact syntax including underscores and parentheses.\n"
            "- If the answer is truly not in the evidence, respond with exactly: NOT FOUND"
        )

        if qtype == "yes_no":
            system_prompt = base_rules + "\n- For yes/no questions, answer Yes or No first, then explain from evidence."
        else:
            system_prompt = base_rules + "\n- Do NOT answer with just Yes or No. Extract the specific answer from the evidence."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Evidence: {evidence}\n\nQuestion: {question}\n\nAnswer (from evidence only):"}
        ]

        try:
            from mlx_lm import generate as mlx_generate
            prompt = llm_data["tokenizer"].apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            response = mlx_generate(llm_data["model"], llm_data["tokenizer"], prompt=prompt, max_tokens=max_tokens, verbose=False)
            answer = response.strip().replace("<|im_end|>", "").strip()

            if "NOT FOUND" in answer.upper():
                confidence = -1.0
                answer = "NOT FOUND"
            elif len(answer) < 20:
                confidence = 7.0
            elif len(answer) < 100:
                confidence = 6.0
            else:
                confidence = 5.0
        except Exception as e:
            self.state["errors"].append(str(e))
            return "", -999.0, None, (time.time() - t0) * 1000

        qa_ms = (time.time() - t0) * 1000
        self.state["meta"]["latencies"]["qa"].append(qa_ms)
        return answer, confidence, best_chunk, qa_ms

    def ExplainAnswer(self, params):
        question = params.get("question", "")
        evidence = params.get("evidence", "")
        extracted = params.get("extracted", "")
        if not question or not evidence:
            return (0, None, ("MISSING_PARAMS", "Need question and evidence", 0))

        llm_data, err = self._GetLLM()
        if err or llm_data is None:
            return (1, extracted, None)

        try:
            from mlx_lm import generate
            prompt = (
                f"Based only on the following evidence, write a clear and concise answer "
                f"to the question. Do not add information that is not in the evidence.\n\n"
                f"Question: {question}\n\nEvidence: {evidence}\n\nAnswer:"
            )
            max_tokens = self.state["config"].get("models", {}).get("llm", {}).get("registry", {}).get(
                self.state["config"].get("models", {}).get("llm", {}).get("active", ""), {}
            ).get("max_tokens", 200)

            response = generate(
                llm_data["model"],
                llm_data["tokenizer"],
                prompt=prompt,
                max_tokens=max_tokens,
                verbose=False,
            )
            return (1, response.strip(), None)
        except Exception as e:
            self.state["errors"].append(str(e))
            return (0, None, ("LLM_FAILED", str(e), 0))

    def IngestDocument(self, params):
        text = params.get("text", "")
        collection = params.get("collection", "")
        doc_id = params.get("doc_id", 1)

        if not text:
            return (0, None, ("EMPTY_TEXT", "No text to ingest", 0))

        retrieval_cfg = self.state["config"].get("retrieval", {})
        chunk_size = retrieval_cfg.get("chunk_size", 400)
        chunk_overlap = retrieval_cfg.get("chunk_overlap", 80)

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = end - chunk_overlap

        if not chunks:
            return (0, None, ("CHUNKING", "No chunks produced", 0))

        embedder_data, err = self._GetEmbedder()
        if err:
            return (0, None, err)

        model = embedder_data["model"]
        if hasattr(model, "encode"):
            vectors = model.encode(chunks)
        else:
            return (0, None, ("EMBEDDING", "Embedder does not support batch encode", 0))

        points = []
        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            points.append({
                "id": i + 1,
                "vector": vec.tolist(),
                "payload": {"text": chunk, "chunk_index": i, "doc_id": doc_id, "source": "ingest"},
            })

        if not collection:
            storage = self.state["config"].get("storage", {})
            collection = storage.get("backends", {}).get(
                storage.get("vector_backend", "qdrant"), {}
            ).get("default_collection", "")

        ok, _, err = self._backend.Run("upsert", {"collection": collection, "points": points})
        if not ok:
            return (0, None, err)

        return (1, {"chunks": len(chunks), "collection": collection, "doc_id": doc_id}, None)

    def _RecordFailure(self, stage):
        self.state["meta"]["failure_stages"][stage] = self.state["meta"]["failure_stages"].get(stage, 0) + 1

    def ReadState(self):
        return (1, self.state, None)
