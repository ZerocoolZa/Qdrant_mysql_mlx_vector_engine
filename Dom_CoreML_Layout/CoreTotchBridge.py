#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreTotchBridge.py
#[@SUMMARY] Bridge: C CoreTotch weights -> CoreML .mlpackage injection
#[@CLASS] CoreTotchBridge
#[@METHOD] inject, export_pt_to_bin, build_coreml
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import sys
import json
import subprocess
import numpy as np
from Config_CoreMLLayout import (
    INPUT_DIM,
    HIDDEN_DIM,
    OUTPUT_DIM,
    MODEL_PATH_PYTORCH,
    MODEL_PATH_MLPACKAGE,
    MODEL_PATH_TRAINED,
    TRAINING_DATA_PATH,
)

WEIGHTS_BIN_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/weights.bin"
CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
PT_EXPORT_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/pt_weights.bin"


class CoreTotchBridge:
    """Bridge between C CoreTotch training engine and CoreML inference.

    Pipeline:
      1. export_pt_to_bin  — PyTorch .pt -> raw float32 binary
      2. C coretotch train  — SGD updates weights in C
      3. inject             — C-trained weights -> CoreML .mlpackage
      4. CoreML inference   — Apple ANE/GPU runs the model
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "export_pt_to_bin":
            return self.cmdExportPtToBin(params)
        if command == "train_c":
            return self.cmdTrainC(params)
        if command == "inject":
            return self.cmdInject(params)
        if command == "build_coreml":
            return self.cmdBuildCoreML(params)
        if command == "full_pipeline":
            return self.cmdFullPipeline(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def cmdExportPtToBin(self, params):
        """Export PyTorch .pt weights to raw float32 binary for C engine."""
        try:
            import torch
            torchPath = self.p(params, "torch_path", MODEL_PATH_PYTORCH)
            outPath = self.p(params, "output_path", PT_EXPORT_BIN)
            state = torch.load(torchPath, map_location="cpu")
            w0 = state["0.weight"].numpy().astype(np.float32).flatten()
            b0 = state["0.bias"].numpy().astype(np.float32).flatten()
            w2 = state["2.weight"].numpy().astype(np.float32).flatten()
            b2 = state["2.bias"].numpy().astype(np.float32).flatten()
            w4 = state["4.weight"].numpy().astype(np.float32).flatten()
            b4 = state["4.bias"].numpy().astype(np.float32).flatten()
            allWeights = np.concatenate([w0, b0, w2, b2, w4, b4])
            allWeights.tofile(outPath)
            return (1, {
                "output_path": outPath,
                "total_params": int(allWeights.shape[0]),
                "expected": 23050,
            }, None)
        except Exception as e:
            return (0, None, ("EXPORT_ERROR", str(e), 0))

    def cmdTrainC(self, params):
        """Run the C CoreTotch training engine."""
        try:
            dataPath = self.p(params, "data_path", TRAINING_DATA_PATH)
            weightsOut = self.p(params, "weights_out", WEIGHTS_BIN_PATH)
            epochs = str(self.p(params, "epochs", 50))
            lr = str(self.p(params, "lr", 0.001))
            initWeights = self.p(params, "init_weights", PT_EXPORT_BIN)
            if not os.path.exists(CORETOTCH_BIN):
                compileOk = self.compileCoreTotch()
                if not compileOk:
                    return (0, None, ("COMPILE_ERROR", "Failed to compile coretotch.c", 0))
            cmd = [
                CORETOTCH_BIN, "train",
                dataPath, weightsOut, epochs, lr, initWeights,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return (0, None, ("CTRAIN_ERROR", result.stderr[:500], 0))
            return (1, {
                "stdout": result.stderr[:500],
                "returncode": result.returncode,
                "weights_path": weightsOut,
            }, None)
        except Exception as e:
            return (0, None, ("CTRAIN_RUN_ERROR", str(e), 0))

    def compileCoreTotch(self):
        try:
            srcPath = os.path.join(os.path.dirname(CORETOTCH_BIN), "coretotch.c")
            result = subprocess.run(
                ["cc", "-O2", "-o", CORETOTCH_BIN, srcPath, "-lm"],
                capture_output=True, text=True, timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def cmdBuildCoreML(self, params):
        """Build a CoreML .mlpackage from scratch with current weights."""
        try:
            import coremltools as ct
            import torch
            import torch.nn as nn

            weightsPath = self.p(params, "weights_path", WEIGHTS_BIN_PATH)
            outputPath = self.p(params, "output_path", MODEL_PATH_MLPACKAGE)

            if not os.path.exists(weightsPath):
                return (0, None, ("WEIGHTS_NOT_FOUND", "No weights.bin", 0))

            weights = np.fromfile(weightsPath, dtype=np.float32)
            if weights.shape[0] != 23050:
                return (0, None, ("WEIGHTS_SHAPE", "Expected 23050, got " + str(weights.shape[0]), 0))

            w0 = weights[0:5120].reshape(128, 40)
            b0 = weights[5120:5248]
            w2 = weights[5248:21632].reshape(128, 128)
            b2 = weights[21632:21760]
            w4 = weights[21760:23040].reshape(10, 128)
            b4 = weights[23040:23050]

            class LayoutPolicy(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.net = nn.Sequential(
                        nn.Linear(40, 128),
                        nn.ReLU(),
                        nn.Linear(128, 128),
                        nn.ReLU(),
                        nn.Linear(128, 10),
                    )
                def forward(self, x):
                    return self.net(x)

            model = LayoutPolicy()
            model.net[0].weight.data = torch.from_numpy(w0)
            model.net[0].bias.data = torch.from_numpy(b0)
            model.net[2].weight.data = torch.from_numpy(w2)
            model.net[2].bias.data = torch.from_numpy(b2)
            model.net[4].weight.data = torch.from_numpy(w4)
            model.net[4].bias.data = torch.from_numpy(b4)
            model.eval()

            example = torch.rand(1, 40)
            traced = torch.jit.trace(model, example)
            mlmodel = ct.convert(
                traced,
                inputs=[ct.TensorType(name="state", shape=(1, 40))],
            )
            mlmodel.save(outputPath)
            return (1, {
                "output_path": outputPath,
                "weights_source": weightsPath,
                "params": 23050,
            }, None)
        except Exception as e:
            return (0, None, ("BUILD_ERROR", str(e), 0))

    def cmdInject(self, params):
        """Inject C-trained weights into existing CoreML model (rebuild)."""
        return self.cmdBuildCoreML(params)

    def cmdFullPipeline(self, params):
        """Run the full CoreTotch -> CoreML pipeline."""
        try:
            episodes = int(self.p(params, "episodes", 200))
            epochs = int(self.p(params, "epochs", 50))
            lr = float(self.p(params, "lr", 0.001))

            sys.stdout.write("Step 1: Export PyTorch weights to binary...\n")
            sys.stdout.flush()
            ok, data, err = self.cmdExportPtToBin({})
            if not ok:
                return (0, None, err)
            sys.stdout.write("  " + str(data) + "\n")
            sys.stdout.flush()

            sys.stdout.write("Step 2: Generate training data...\n")
            sys.stdout.flush()
            from CoreMLLayoutDataGenerator import CoreMLLayoutDataGenerator
            gen = CoreMLLayoutDataGenerator()
            ok, genData, genErr = gen.Run("generate", {"episodes": episodes})
            if not ok:
                return (0, None, genErr)
            ok, saveData, saveErr = gen.Run("save", {})
            if not ok:
                return (0, None, saveErr)
            sys.stdout.write("  " + str(genData) + "\n")
            sys.stdout.flush()

            sys.stdout.write("Step 3: C CoreTotch training (" + str(epochs) + " epochs)...\n")
            sys.stdout.flush()
            ok, trainData, trainErr = self.cmdTrainC({
                "epochs": epochs,
                "lr": lr,
            })
            if not ok:
                return (0, None, trainErr)
            sys.stdout.write("  " + str(trainData) + "\n")
            sys.stdout.flush()

            sys.stdout.write("Step 4: Build CoreML model with C-trained weights...\n")
            sys.stdout.flush()
            ok, buildData, buildErr = self.cmdBuildCoreML({
                "weights_path": WEIGHTS_BIN_PATH,
                "output_path": MODEL_PATH_TRAINED,
            })
            if not ok:
                return (0, None, buildErr)
            sys.stdout.write("  " + str(buildData) + "\n")
            sys.stdout.flush()

            sys.stdout.write("Step 5: Verify CoreML model...\n")
            sys.stdout.flush()
            import coremltools as ct
            model = ct.models.MLModel(MODEL_PATH_TRAINED)
            spec = model.get_spec()
            inputName = spec.description.input[0].name
            testState = np.random.rand(1, 40).astype(np.float32)
            pred = model.predict({inputName: testState})
            outputName = spec.description.output[0].name
            outVal = pred.get(outputName, [])
            sys.stdout.write("  Inference test OK: input=" + inputName + " output=" + outputName + " val=" + str(outVal[:3]) + "...\n")
            sys.stdout.flush()

            return (1, {
                "status": "complete",
                "pipeline": "CoreTotch(C-train) -> weights.bin -> CoreML(inference)",
                "episodes": episodes,
                "epochs": epochs,
                "lr": lr,
                "model_path": MODEL_PATH_TRAINED,
                "inference_test": True,
            }, None)
        except Exception as e:
            return (0, None, ("PIPELINE_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {"config": self.state["config"]}, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
