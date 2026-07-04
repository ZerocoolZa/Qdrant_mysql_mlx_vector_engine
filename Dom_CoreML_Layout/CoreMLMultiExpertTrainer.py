#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLMultiExpertTrainer.py
#[@SUMMARY] Trains multiple expert modules for different layout domains
#[@CLASS] CoreMLMultiExpertTrainer
#[@METHOD] train_all, train_one, deploy
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import sys
import json
import subprocess
import numpy as np
from Config_CoreMLLayout import (
    INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM,
    CANVAS_WIDTH, CANVAS_HEIGHT,
    MODEL_PATH_PYTORCH,
    TRAINING_EPOCHS,
)
from CoreMLExpertRegistry import CoreMLExpertRegistry, EXPERT_DIR
from CoreMLLayoutDataGenerator import CoreMLLayoutDataGenerator
from CoreTotchBridge import CoreTotchBridge

EXPERT_DOMAINS = [
    {"name": "vscode", "description": "VSCode-style IDE layout", "node_range": [3, 5], "constraint_prob": 0.15},
    {"name": "browser", "description": "Browser-style layout", "node_range": [4, 6], "constraint_prob": 0.20},
    {"name": "dashboard", "description": "Analytics dashboard layout", "node_range": [5, 8], "constraint_prob": 0.30},
    {"name": "mobile", "description": "Mobile app layout", "node_range": [3, 5], "constraint_prob": 0.10},
    {"name": "tablet", "description": "Tablet layout", "node_range": [4, 7], "constraint_prob": 0.25},
]

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
PT_EXPORT_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/pt_weights.bin"


class CoreMLMultiExpertTrainer:
    """Trains multiple expert modules, each specialized for a layout domain.

    Pipeline per expert:
      1. Generate domain-specific training data
      2. C CoreTotch trains weights via SGD
      3. Register expert in manifest
      4. At runtime: C loads only the selected expert
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "results": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "train_all":
            return self.cmdTrainAll(params)
        if command == "train_one":
            return self.cmdTrainOne(params)
        if command == "deploy":
            return self.cmdDeploy(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def cmdTrainAll(self, params):
        """Train all expert modules."""
        try:
            episodes = int(self.p(params, "episodes", 100))
            epochs = int(self.p(params, "epochs", 30))
            lr = float(self.p(params, "lr", 0.001))
            bridge = CoreTotchBridge()
            ok, expData, expErr = bridge.Run("export_pt_to_bin", {})
            if not ok:
                return (0, None, expErr)
            results = []
            for domain in EXPERT_DOMAINS:
                name = domain["name"]
                sys.stdout.write("\n--- Training expert: " + name + " ---\n")
                sys.stdout.flush()
                ok, trainData, trainErr = self.trainExpert(domain, episodes, epochs, lr)
                if not ok:
                    sys.stdout.write("  FAILED: " + str(trainErr) + "\n")
                    sys.stdout.flush()
                    results.append({"expert": name, "status": "failed", "error": str(trainErr)})
                    continue
                results.append({"expert": name, "status": "trained", "data": trainData})
                sys.stdout.write("  OK: " + str(trainData) + "\n")
                sys.stdout.flush()
            self.state["results"] = results
            return (1, {
                "experts_trained": len([r for r in results if r["status"] == "trained"]),
                "experts_failed": len([r for r in results if r["status"] == "failed"]),
                "results": results,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_ALL_ERROR", str(e), 0))

    def trainExpert(self, domain, episodes, epochs, lr):
        """Train a single expert module."""
        try:
            name = domain["name"]
            nMin, nMax = domain["node_range"]
            if not os.path.exists(EXPERT_DIR):
                os.makedirs(EXPERT_DIR, exist_ok=True)
            dataPath = os.path.join(EXPERT_DIR, name + "_data.json")
            weightsPath = os.path.join(EXPERT_DIR, name + ".weights.bin")
            gen = CoreMLLayoutDataGenerator()
            ok, genData, genErr = gen.Run("generate", {"episodes": episodes})
            if not ok:
                return (0, None, genErr)
            ok, saveData, saveErr = gen.Run("save", {"path": dataPath})
            if not ok:
                return (0, None, saveErr)
            if not os.path.exists(CORETOTCH_BIN):
                return (0, None, ("CORETOTCH_NOT_FOUND", "Compile coretotch.c first", 0))
            cmd = [
                CORETOTCH_BIN, "train",
                dataPath, weightsPath, str(epochs), str(lr), PT_EXPORT_BIN,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return (0, None, ("CTRAIN_ERROR", result.stderr[:300], 0))
            registry = CoreMLExpertRegistry()
            ok, regData, regErr = registry.Run("register", {
                "name": name,
                "weights_path": weightsPath,
                "domain": name,
                "description": domain["description"],
            })
            if not ok:
                return (0, None, regErr)
            return (1, {
                "expert": name,
                "weights_path": weightsPath,
                "data_path": dataPath,
                "training_output": result.stderr[:200],
            }, None)
        except Exception as e:
            return (0, None, ("EXPERT_TRAIN_ERROR", str(e), 0))

    def cmdTrainOne(self, params):
        """Train a single expert by name."""
        try:
            name = self.p(params, "name")
            episodes = int(self.p(params, "episodes", 100))
            epochs = int(self.p(params, "epochs", 30))
            lr = float(self.p(params, "lr", 0.001))
            domain = None
            for d in EXPERT_DOMAINS:
                if d["name"] == name:
                    domain = d
                    break
            if not domain:
                return (0, None, ("DOMAIN_NOT_FOUND", "No domain: " + name, 0))
            bridge = CoreTotchBridge()
            ok, expData, expErr = bridge.Run("export_pt_to_bin", {})
            if not ok:
                return (0, None, expErr)
            ok, trainData, trainErr = self.trainExpert(domain, episodes, epochs, lr)
            if not ok:
                return (0, None, trainErr)
            return (1, trainData, None)
        except Exception as e:
            return (0, None, ("TRAIN_ONE_ERROR", str(e), 0))

    def cmdDeploy(self, params):
        """Select an expert and build CoreML model from its weights."""
        try:
            name = self.p(params, "name")
            if not name:
                return (0, None, ("PARAMS_ERROR", "name required", 0))
            registry = CoreMLExpertRegistry()
            ok, selData, selErr = registry.Run("select", {"name": name})
            if not ok:
                return (0, None, selErr)
            weightsPath = selData["weights_path"]
            from Config_CoreMLLayout import MODEL_PATH_TRAINED
            outputPath = os.path.join(EXPERT_DIR, name + ".mlpackage")
            bridge = CoreTotchBridge()
            ok, buildData, buildErr = bridge.Run("build_coreml", {
                "weights_path": weightsPath,
                "output_path": outputPath,
            })
            if not ok:
                return (0, None, buildErr)
            return (1, {
                "deployed_expert": name,
                "coreml_model": outputPath,
                "weights": weightsPath,
                "domain": selData["domain"],
            }, None)
        except Exception as e:
            return (0, None, ("DEPLOY_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "results_count": len(self.state["results"]),
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
