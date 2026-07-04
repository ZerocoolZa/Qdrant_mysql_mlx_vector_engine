#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLLayoutConverter.py
#[@SUMMARY] Converts PyTorch 40-dim MLP to updatable CoreML mlpackage
#[@CLASS] CoreMLLayoutConverter
#[@METHOD] convert, verify, inspect
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import sys
import torch
import torch.nn as nn
import coremltools as ct
from coremltools.models.neural_network import NeuralNetworkBuilder
from Config_CoreMLLayout import (
    INPUT_DIM,
    HIDDEN_DIM,
    OUTPUT_DIM,
    MODEL_NAME,
    MODEL_PATH_MLPACKAGE,
    MODEL_PATH_PYTORCH,
)


class CoreMLLayoutConverter:
    """Converts PyTorch layout policy MLP to updatable CoreML model."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "model": None,
            "torch_model": None,
            "coreml_model": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "convert":
            return self.cmdConvert(params)
        if command == "verify":
            return self.cmdVerify(params)
        if command == "inspect":
            return self.cmdInspect(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def cmdConvert(self, params):
        try:
            torchPath = self.p(params, "torch_path", MODEL_PATH_PYTORCH)
            outputPath = self.p(params, "output_path", MODEL_PATH_MLPACKAGE)
            state = torch.load(torchPath, map_location="cpu")
            w0 = state["0.weight"].numpy()
            b0 = state["0.bias"].numpy()
            w2 = state["2.weight"].numpy()
            b2 = state["2.bias"].numpy()
            w4 = state["4.weight"].numpy()
            b4 = state["4.bias"].numpy()
            inputFeatures = [
                ct.FeatureType(name="state", type=ct.FeatureType.Array(INPUT_DIM, float)),
            ]
            outputFeatures = [
                ct.FeatureType(name="action", type=ct.FeatureType.Array(OUTPUT_DIM, float)),
            ]
            builder = NeuralNetworkBuilder(
                inputFeatures,
                outputFeatures,
                mode=None,
            )
            builder.add_inner_product(
                name="fc0",
                W=w0,
                b=b0,
                input_channels=INPUT_DIM,
                output_channels=HIDDEN_DIM,
                has_bias=True,
                input_name="state",
                output_name="fc0_out",
            )
            builder.add_activation(
                name="relu0",
                non_linearity="RELU",
                input_name="fc0_out",
                output_name="relu0_out",
            )
            builder.add_inner_product(
                name="fc2",
                W=w2,
                b=b2,
                input_channels=HIDDEN_DIM,
                output_channels=HIDDEN_DIM,
                has_bias=True,
                input_name="relu0_out",
                output_name="fc2_out",
            )
            builder.add_activation(
                name="relu2",
                non_linearity="RELU",
                input_name="fc2_out",
                output_name="relu2_out",
            )
            builder.add_inner_product(
                name="fc4",
                W=w4,
                b=b4,
                input_channels=HIDDEN_DIM,
                output_channels=OUTPUT_DIM,
                has_bias=True,
                input_name="relu2_out",
                output_name="action",
            )
            coremlModel = ct.models.MLModel(builder.spec)
            spec = coremlModel.get_spec()
            spec.neuralNetwork.layers[0].isUpdatable = True
            spec.neuralNetwork.layers[2].isUpdatable = True
            spec.neuralNetwork.layers[4].isUpdatable = True
            trainingFeatures = [
                ct.FeatureType(name="action_target", type=ct.FeatureType.Array(OUTPUT_DIM, float)),
            ]
            ct.utils.make_updatable(
                spec,
                training_features=trainingFeatures,
                optimizer=ct.utils.SGDOptimizer(lr=0.001),
                loss_layers=ct.utils.LossType.MeanSquaredError,
            )
            finalModel = ct.models.MLModel(spec)
            finalModel.save(outputPath)
            self.state["coreml_model"] = outputPath
            return (1, {
                "output_path": outputPath,
                "input_dim": INPUT_DIM,
                "hidden_dim": HIDDEN_DIM,
                "output_dim": OUTPUT_DIM,
                "updatable_layers": 3,
            }, None)
        except Exception as e:
            return (0, None, ("CONVERT_ERROR", str(e), 0))

    def cmdVerify(self, params):
        try:
            path = self.p(params, "model_path", MODEL_PATH_MLPACKAGE)
            model = ct.models.MLModel(path)
            spec = model.get_spec()
            updatableCount = 0
            layerCount = 0
            for layer in spec.neuralNetwork.layers:
                layerCount += 1
                if layer.isUpdatable:
                    updatableCount += 1
            return (1, {
                "path": path,
                "total_layers": layerCount,
                "updatable_layers": updatableCount,
                "is_updatable": updatableCount > 0,
                "input_desc": str(spec.description.input[0].name),
                "output_desc": str(spec.description.output[0].name),
            }, None)
        except Exception as e:
            return (0, None, ("VERIFY_ERROR", str(e), 0))

    def cmdInspect(self, params):
        try:
            path = self.p(params, "model_path", MODEL_PATH_MLPACKAGE)
            model = ct.models.MLModel(path)
            spec = model.get_spec()
            layers = []
            for layer in spec.neuralNetwork.layers:
                layers.append({
                    "name": layer.name,
                    "type": str(layer.WhichOneof("layer")),
                    "updatable": layer.isUpdatable,
                })
            return (1, {"path": path, "layers": layers}, None)
        except Exception as e:
            return (0, None, ("INSPECT_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "coreml_model": self.state["coreml_model"],
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
