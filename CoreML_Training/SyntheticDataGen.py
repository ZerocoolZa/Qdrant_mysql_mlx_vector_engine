#[@GHOST]{[@file<SyntheticDataGen.py>][@domain<coreml_training>][@role<data_generator>][@return<Tuple3>][@auth<devin>][@date<2026-06-28>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<generator>][@return<Tuple3>][@state<config,samples,batch>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/CoreML_Training/SyntheticDataGen.py>][@date<2026-06-28>][@session<coreml_training>]}
#[@SUMMARY]{Generates synthetic labeled tensors (4-dim input, 3-class labels) and wraps them as MLFeatureProvider batch for MLUpdateTask}
#[@CLASS]{SyntheticDataGen — owns synthetic training data for the proof-of-concept}
#[@METHOD]{Run dispatch: generate, summary}

import json
import os
import numpy as np

import Config


class SyntheticDataGen:
    """Generates synthetic labeled data and wraps it as an MLArrayBatchProvider."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "num_samples": Config.NUM_SAMPLES,
                "input_dim": Config.INPUT_DIM,
                "num_classes": Config.NUM_CLASSES,
                "seed": Config.SEED,
            },
            "samples": {"features": None, "labels": None},
            "batch": None,
            "results": {},
            "errors": [],
            "meta": {"class": "SyntheticDataGen", "ver": "1.0"},
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "generate": self.generate,
            "summary": self.summary,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    def read_state(self):
        return (1, dict(self.state["config"]), None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_params", "set_config requires dict", 0))
        self.state["config"].update(params)
        return (1, dict(self.state["config"]), None)

    def generate(self, params):
        cfg = self.state["config"]
        rng = np.random.default_rng(cfg["seed"])
        num = cfg["num_samples"]
        dim = cfg["input_dim"]
        classes = cfg["num_classes"]
        centers = rng.standard_normal((classes, dim)).astype(np.float32) * 2.0
        labels = rng.integers(0, classes, size=num).astype(np.int32)
        features = np.zeros((num, dim), dtype=np.float32)
        for i in range(num):
            features[i] = centers[labels[i]] + rng.standard_normal(dim).astype(np.float32) * 0.3
        self.state["samples"]["features"] = features
        self.state["samples"]["labels"] = labels
        out_path = os.path.join(Config.OUTPUT_DIR, "training_data.json")
        samples_json = [
            {"features": [float(x) for x in features[i]], "label": int(labels[i])}
            for i in range(num)
        ]
        with open(out_path, "w") as f:
            json.dump(samples_json, f)
        self.state["results"]["count"] = num
        self.state["results"]["class_counts"] = {
            int(c): int(np.sum(labels == c)) for c in range(classes)
        }
        self.state["results"]["data_path"] = out_path
        return (1, {"count": num, "class_counts": self.state["results"]["class_counts"], "data_path": out_path}, None)

    def summary(self, params):
        if self.state["samples"]["features"] is None:
            return (0, None, ("no_data", "Generate data first", 0))
        feats = self.state["samples"]["features"]
        labels = self.state["samples"]["labels"]
        info = {
            "count": int(feats.shape[0]),
            "dim": int(feats.shape[1]),
            "feature_mean": float(feats.mean()),
            "feature_std": float(feats.std()),
            "class_counts": {int(c): int(np.sum(labels == c)) for c in range(self.state["config"]["num_classes"])},
            "batch_ready": self.state["results"].get("data_path") is not None,
        }
        return (1, info, None)
