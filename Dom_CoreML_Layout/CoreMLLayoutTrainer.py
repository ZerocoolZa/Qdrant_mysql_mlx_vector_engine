#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLLayoutTrainer.py
#[@SUMMARY] Orchestrates CoreML on-device training: convert, generate data, run update
#[@CLASS] CoreMLLayoutTrainer
#[@METHOD] train, evaluate, export
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import sys
import os
import json
import subprocess
from Config_CoreMLLayout import (
    MODEL_PATH_MLPACKAGE,
    MODEL_PATH_TRAINED,
    TRAINING_DATA_PATH,
    SWIFT_SCRIPT_PATH,
    TRAINING_EPOCHS,
    MAX_EPISODES,
)
from CoreMLLayoutConverter import CoreMLLayoutConverter
from CoreMLLayoutDataGenerator import CoreMLLayoutDataGenerator


class CoreMLLayoutTrainer:
    """Orchestrates the full CoreML on-device training pipeline."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "converter": None,
            "generator": None,
            "results": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "train":
            return self.cmdTrain(params)
        if command == "evaluate":
            return self.cmdEvaluate(params)
        if command == "export":
            return self.cmdExport(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def cmdTrain(self, params):
        try:
            episodes = int(self.p(params, "episodes", MAX_EPISODES))
            epochs = int(self.p(params, "epochs", TRAINING_EPOCHS))
            sys.stdout.write("Step 1: Converting PyTorch model to updatable CoreML...\n")
            sys.stdout.flush()
            converter = CoreMLLayoutConverter()
            ok, convData, convErr = converter.Run("convert", {})
            if not ok:
                return (0, None, convErr)
            sys.stdout.write("  Converted: " + str(convData) + "\n")
            sys.stdout.flush()
            sys.stdout.write("Step 2: Verifying updatable model...\n")
            sys.stdout.flush()
            ok, verifyData, verifyErr = converter.Run("verify", {})
            if not ok:
                return (0, None, verifyErr)
            sys.stdout.write("  Verified: " + str(verifyData) + "\n")
            sys.stdout.flush()
            sys.stdout.write("Step 3: Generating " + str(episodes) + " synthetic episodes...\n")
            sys.stdout.flush()
            generator = CoreMLLayoutDataGenerator()
            ok, genData, genErr = generator.Run("generate", {"episodes": episodes})
            if not ok:
                return (0, None, genErr)
            sys.stdout.write("  Generated: " + str(genData) + "\n")
            sys.stdout.flush()
            sys.stdout.write("Step 4: Saving training data...\n")
            sys.stdout.flush()
            ok, saveData, saveErr = generator.Run("save", {})
            if not ok:
                return (0, None, saveErr)
            sys.stdout.write("  Saved: " + str(saveData) + "\n")
            sys.stdout.flush()
            sys.stdout.write("Step 5: Running Swift MLUpdateTask (" + str(epochs) + " epochs)...\n")
            sys.stdout.flush()
            ok, swiftData, swiftErr = self.runSwiftUpdate(epochs)
            if not ok:
                return (0, None, swiftErr)
            sys.stdout.write("  Swift result: " + str(swiftData) + "\n")
            sys.stdout.flush()
            self.state["results"].append({
                "episodes": episodes,
                "epochs": epochs,
                "conversion": convData,
                "verification": verifyData,
                "generation": genData,
                "swift": swiftData,
            })
            return (1, {
                "status": "complete",
                "episodes": episodes,
                "epochs": epochs,
                "model_path": MODEL_PATH_TRAINED,
                "swift_output": swiftData,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_ERROR", str(e), 0))

    def runSwiftUpdate(self, epochs):
        try:
            cmd = [
                "swift", SWIFT_SCRIPT_PATH,
                "--model", MODEL_PATH_MLPACKAGE,
                "--data", TRAINING_DATA_PATH,
                "--output", MODEL_PATH_TRAINED,
                "--epochs", str(epochs),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                return (0, None, ("SWIFT_ERROR", result.stderr[:500], 0))
            return (1, {
                "stdout": result.stdout[:500],
                "returncode": result.returncode,
            }, None)
        except FileNotFoundError:
            return (0, None, ("SWIFT_NOT_FOUND", "swift command not found", 0))
        except subprocess.TimeoutExpired:
            return (0, None, ("SWIFT_TIMEOUT", "Swift script timed out", 0))
        except Exception as e:
            return (0, None, ("SWIFT_RUN_ERROR", str(e), 0))

    def cmdEvaluate(self, params):
        try:
            import coremltools as ct
            import numpy as np
            path = self.p(params, "model_path", MODEL_PATH_TRAINED)
            if not os.path.exists(path):
                path = MODEL_PATH_MLPACKAGE
            model = ct.models.MLModel(path)
            generator = CoreMLLayoutDataGenerator()
            ok, genData, genErr = generator.Run("generate", {"episodes": 10, "steps": 5})
            if not ok:
                return (0, None, genErr)
            totalEnergy = 0.0
            sampleCount = 0
            for ep in generator.state["episodes"]:
                for step in ep["steps"]:
                    state = np.array(step["state"], dtype=np.float32).reshape(1, -1)
                    pred = model.predict({"state": state})
                    actionOut = pred.get("action", [0.0] * 10)
                    sampleCount += 1
            return (1, {
                "model_path": path,
                "samples_evaluated": sampleCount,
            }, None)
        except Exception as e:
            return (0, None, ("EVAL_ERROR", str(e), 0))

    def cmdExport(self, params):
        try:
            src = self.p(params, "source", MODEL_PATH_TRAINED)
            dst = self.p(params, "destination", "")
            if not dst:
                return (0, None, ("PARAMS_ERROR", "destination required", 0))
            import shutil
            shutil.copytree(src, dst)
            return (1, {"source": src, "destination": dst}, None)
        except Exception as e:
            return (0, None, ("EXPORT_ERROR", str(e), 0))

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
