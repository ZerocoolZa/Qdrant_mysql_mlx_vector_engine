#[@GHOST]{[@file<UpdatableBuilder.py>][@domain<coreml_training>][@role<model_builder>][@return<Tuple3>][@auth<devin>][@date<2026-06-28>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<builder>][@return<Tuple3>][@state<config,spec,paths>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/CoreML_Training/UpdatableBuilder.py>][@date<2026-06-28>][@session<coreml_training>]}
#[@SUMMARY]{Builds a tiny FC classifier (4->8->3) and marks it updatable via coremltools make_updatable + Adam + cross-entropy}
#[@CLASS]{UpdatableBuilder — owns construction of the updatable .mlmodel spec}
#[@METHOD]{Run dispatch: build_base, build_updatable, inspect}

import os
import numpy as np
import coremltools as ct
from coremltools.models import MLModel
from coremltools.models.neural_network import NeuralNetworkBuilder, AdamParams
from coremltools.models import datatypes as ct_datatypes
from coremltools.proto import FeatureTypes_pb2 as ft

import Config


class UpdatableBuilder:
    """Builds a tiny updatable FC classifier for MLUpdateTask proof-of-concept."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "input_dim": Config.INPUT_DIM,
                "hidden_dim": Config.HIDDEN_DIM,
                "num_classes": Config.NUM_CLASSES,
                "epochs": Config.EPOCHS,
                "lr": Config.LEARNING_RATE,
                "batch": Config.BATCH_SIZE,
            },
            "spec": None,
            "paths": {
                "base": Config.BASE_MODEL_PATH,
                "updatable": Config.UPDATABLE_MODEL_PATH,
            },
            "results": {},
            "errors": [],
            "meta": {"class": "UpdatableBuilder", "ver": "1.0"},
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "build_base": self.build_base,
            "build_updatable": self.build_updatable,
            "inspect": self.inspect,
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

    def build_base(self, params):
        ok, out_dir, err = Config.ensure_output_dir()
        if not ok:
            return (0, None, err)
        rng = np.random.default_rng(Config.SEED)
        input_features = [(Config.INPUT_NAME, ct_datatypes.Array(Config.INPUT_DIM))]
        output_features = [(Config.OUTPUT_NAME, ct_datatypes.Array(Config.NUM_CLASSES))]
        builder = NeuralNetworkBuilder(input_features, output_features)
        fc1_w = rng.standard_normal((Config.HIDDEN_DIM, Config.INPUT_DIM)).astype(np.float32) * 0.1
        fc1_b = np.zeros((Config.HIDDEN_DIM,), dtype=np.float32)
        builder.add_inner_product(
            name=Config.LAYER_FC1,
            W=fc1_w,
            b=fc1_b,
            input_channels=Config.INPUT_DIM,
            output_channels=Config.HIDDEN_DIM,
            has_bias=True,
            input_name=Config.INPUT_NAME,
            output_name="fc1_out",
        )
        builder.add_activation(
            name="fc1_relu",
            non_linearity="RELU",
            input_name="fc1_out",
            output_name="fc1_act",
        )
        fc2_w = rng.standard_normal((Config.NUM_CLASSES, Config.HIDDEN_DIM)).astype(np.float32) * 0.1
        fc2_b = np.zeros((Config.NUM_CLASSES,), dtype=np.float32)
        builder.add_inner_product(
            name=Config.LAYER_FC2,
            W=fc2_w,
            b=fc2_b,
            input_channels=Config.HIDDEN_DIM,
            output_channels=Config.NUM_CLASSES,
            has_bias=True,
            input_name="fc1_act",
            output_name="fc2_out",
        )
        builder.add_softmax(
            name="softmax_out",
            input_name="fc2_out",
            output_name=Config.OUTPUT_NAME,
        )
        spec = builder.spec
        spec.description.input[0].shortDescription = "Input feature vector"
        spec.description.output[0].shortDescription = "Class probabilities"
        spec.description.metadata.author = "Devin CoreML Training"
        spec.description.metadata.shortDescription = "Base FC classifier (4->8->3) for MLUpdateTask proof"
        spec.description.metadata.versionString = "1.0"
        base_path = self.state["paths"]["base"]
        MLModel(spec).save(base_path)
        self.state["spec"] = spec
        self.state["results"]["base_path"] = base_path
        return (1, {"base_path": base_path, "layers": [Config.LAYER_FC1, Config.LAYER_FC2]}, None)

    def build_updatable(self, params):
        if self.state["spec"] is None:
            ok, data, err = self.build_base(params)
            if not ok:
                return (0, None, err)
        spec = self.state["spec"]
        builder = NeuralNetworkBuilder(spec=spec)
        builder.make_updatable([Config.LAYER_FC1, Config.LAYER_FC2])
        builder.set_categorical_cross_entropy_loss(name=Config.LOSS_NAME, input=Config.OUTPUT_NAME)
        adam = AdamParams(
            lr=Config.LEARNING_RATE,
            beta1=Config.ADAM_BETA1,
            beta2=Config.ADAM_BETA2,
            eps=Config.ADAM_EPS,
            batch=Config.BATCH_SIZE,
        )
        builder.set_adam_optimizer(adam)
        builder.set_epochs(Config.EPOCHS)
        spec.description.trainingInput[0].shortDescription = "Training input feature vector"
        spec.description.trainingInput[1].shortDescription = "Training target label (class index)"
        updatable_path = self.state["paths"]["updatable"]
        MLModel(spec).save(updatable_path)
        self.state["spec"] = spec
        self.state["results"]["updatable_path"] = updatable_path
        return (1, {"updatable_path": updatable_path, "is_updatable": True, "epochs": Config.EPOCHS}, None)

    def inspect(self, params):
        path = self._p(params, "path", self.state["paths"].get("updatable"))
        if path is None or not os.path.exists(path):
            return (0, None, ("no_model", "Model not found: " + str(path), 0))
        m = MLModel(path)
        spec = m.get_spec()
        info = {
            "is_updatable": spec.isUpdatable,
            "training_inputs": [t.name for t in spec.description.trainingInput],
            "type": spec.WhichOneof("Type"),
            "outputs": [o.name for o in spec.description.output],
            "inputs": [i.name for i in spec.description.input],
        }
        try:
            nn = spec.neuralNetwork
            info["updatable_layers"] = list(nn.updateParams.updatableLayers)
            info["optimizer"] = nn.updateParams.optimizer.WhichOneof("optimizer")
            info["losses"] = [l.name for l in nn.updateParams.losses]
            info["epochs"] = nn.updateParams.epochs
        except Exception as exc:
            info["nn_error"] = str(exc)
        return (1, info, None)
