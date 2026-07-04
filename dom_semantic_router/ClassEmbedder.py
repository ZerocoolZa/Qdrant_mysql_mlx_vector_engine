"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/dom_semantic_router/ClassEmbedder.py";"identity=ClassEmbedder";"purpose=Encode class_code into 384-dim MLX bge-small-8bit vectors with chunked mean-pooling";"date=2026-06-26";"version=2.0";"author=Devin";"task=TASK-086")}
#[@VBSTYLE]{("auth=Devin";"role=domain_embedding";"return=Tuple3";"orch=Config";"no=no_decorators|no_print|no_hardcoded|no_tabs|no_self_underscore|no_torch";"model=one_class_one_domain_one_authority_complete")}
#[@CLASSES]{("ClassEmbedder")}
#[@METHODS]{("Run";"read_state";"set_config";"_p";"_LoadModel";"_SampleText";"_EmbedBatches";"_MeanPool";"_EmbedClassCode";"_EmbedClasses")}
#[@DOMAIN]{("embedding")}
"""

import logging
from typing import Any, Dict, List, Tuple

import numpy

from Config import (
    MODEL_ID, EMBED_DIM, MAX_TOKENS, MAX_CHUNKS, EMBED_BATCH_SIZE,
    DEVICE_MLX_GPU, LOG_PATH
)

Logger = logging.getLogger("dom_semantic_router.ClassEmbedder")
if not Logger.handlers:
    Handler = logging.FileHandler(LOG_PATH)
    Handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    Logger.addHandler(Handler)
Logger.setLevel(logging.INFO)


class ClassEmbedder:
    """Authority for encoding class source code into fixed-size MLX bge-small vectors."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "tokenizer": None,
            "model": None,
            "loaded": False
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "load_model":
            return self._LoadModel(params)
        elif command == "embed_class":
            return self._EmbedClassCode(params)
        elif command == "embed_classes":
            return self._EmbedClasses(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _LoadModel(self, params):
        try:
            import mlx.core as mx
            import mlx_embeddings
            if DEVICE_MLX_GPU == "gpu":
                mx.set_default_device(mx.gpu)
            Logger.info("Loading MLX model %s on %s", MODEL_ID, mx.default_device())
            Model, Tokenizer = mlx_embeddings.load(MODEL_ID)
            self.state["tokenizer"] = Tokenizer
            self.state["model"] = Model
            self.state["loaded"] = True
            self.state["results"] = self.state.get("results", []) + [
                {"event": "model_loaded", "model": MODEL_ID,
                 "device": str(mx.default_device())}
            ]
            return (1, {"model": MODEL_ID, "device": str(mx.default_device())}, None)
        except Exception as e:
            return (0, None, ("LOAD_MODEL_ERROR", str(e), 0))

    def _SampleText(self, text, max_chars):
        if text is None:
            return ""
        if len(text) <= max_chars:
            return text
        chunks = MAX_CHUNKS
        if chunks < 1:
            chunks = 1
        window = max_chars // chunks
        if window < 1:
            window = 1
        total = len(text)
        parts = []
        for i in range(chunks):
            start = (total * i) // chunks
            end = start + window
            if end > total:
                end = total
            parts.append(text[start:end])
        return "".join(parts)

    def _MeanPool(self, last_hidden, attention_mask):
        import mlx.core as mx
        mask = mx.expand_dims(attention_mask, -1).astype(last_hidden.dtype)
        summed = (last_hidden * mask).sum(0)
        counts = mask.sum(0)
        counts = mx.maximum(counts, mx.array(1e-9))
        return summed / counts

    def _EmbedBatches(self, text_chunks):
        try:
            import mlx.core as mx
            Model = self.state["model"]
            Tokenizer = self.state["tokenizer"]
            if Model is None or Tokenizer is None:
                return (0, None, ("MODEL_NOT_LOADED", "Call load_model before embedding", 0))
            vectors = []
            total = len(text_chunks)
            for start in range(0, total, EMBED_BATCH_SIZE):
                batch = text_chunks[start:start + EMBED_BATCH_SIZE]
                Tok = Tokenizer(batch, padding=True, truncation=True, max_length=MAX_TOKENS)
                input_ids = mx.array(Tok["input_ids"])
                attn = mx.array(Tok["attention_mask"])
                Out = Model(input_ids, attn)
                Pooled = self._MeanPool(Out.last_hidden_state, attn)
                mx.eval(Pooled)
                arr = numpy.array(Pooled).astype("float32")
                if arr.ndim == 1:
                    arr = arr.reshape(1, -1)
                for row in arr:
                    vectors.append(row)
            return (1, vectors, None)
        except Exception as e:
            return (0, None, ("EMBED_BATCH_ERROR", str(e), 0))

    def _EmbedClassCode(self, params):
        try:
            class_name = self._p(params, "class_name", "")
            code = self._p(params, "class_code", "")
            if code is None or str(code).strip() == "":
                self.state["results"] = self.state.get("results", []) + [
                    {"event": "skipped_empty", "class_name": class_name}
                ]
                return (1, {"class_name": class_name, "vector": None, "skipped": True}, None)
            max_chars = MAX_CHUNKS * MAX_TOKENS * 4
            sampled = self._SampleText(str(code), max_chars)
            Tokenizer = self.state["tokenizer"]
            if Tokenizer is None:
                return (0, None, ("MODEL_NOT_LOADED", "Call load_model before embedding", 0))
            token_ids = Tokenizer(sampled, add_special_tokens=True, truncation=False)["input_ids"]
            if isinstance(token_ids, list) and token_ids and isinstance(token_ids[0], list):
                token_ids = token_ids[0]
            chunks = []
            step = MAX_TOKENS
            for i in range(0, len(token_ids), step):
                piece = token_ids[i:i + step]
                if hasattr(Tokenizer, "decode"):
                    chunks.append(Tokenizer.decode(piece, skip_special_tokens=False))
                else:
                    chunks.append(sampled[i * 4:(i + step) * 4])
            if not chunks:
                return (1, {"class_name": class_name, "vector": None, "skipped": True}, None)
            ok, vectors, err = self._EmbedBatches(chunks)
            if not ok:
                return (0, None, err)
            stacked = numpy.stack(vectors).astype("float32")
            mean_vec = stacked.mean(axis=0)
            norm = numpy.linalg.norm(mean_vec)
            if norm > 0:
                mean_vec = mean_vec / norm
            return (1, {"class_name": class_name, "vector": mean_vec.tolist(),
                        "chunks": len(chunks), "skipped": False}, None)
        except Exception as e:
            return (0, None, ("EMBED_CLASS_ERROR", str(e), 0))

    def _EmbedClasses(self, params):
        try:
            records = self._p(params, "records", [])
            if not records:
                return (0, None, ("NO_RECORDS", "No class records supplied", 0))
            if not self.state["loaded"]:
                ok, _, err = self._LoadModel(params)
                if not ok:
                    return (0, None, err)
            results = []
            skipped = 0
            total = len(records)
            for idx, rec in enumerate(records):
                ok, data, err = self._EmbedClassCode(rec)
                if not ok:
                    return (0, None, err)
                if data.get("skipped"):
                    skipped = skipped + 1
                results.append(data)
                if (idx + 1) % 25 == 0 or (idx + 1) == total:
                    Logger.info("Embedded %d/%d (skipped %d)", idx + 1, total, skipped)
            self.state["results"] = self.state.get("results", []) + [
                {"event": "batch_done", "total": total, "skipped": skipped}
            ]
            return (1, {"records": results, "total": total, "skipped": skipped}, None)
        except Exception as e:
            return (0, None, ("EMBED_CLASSES_ERROR", str(e), 0))

    def read_state(self, params):
        return (1, dict(self.state), None)

    def set_config(self, params):
        try:
            for key, value in params.items():
                self.state["config"][key] = value
            return (1, dict(self.state["config"]), None)
        except Exception as e:
            return (0, None, ("SET_CONFIG_ERROR", str(e), 0))
