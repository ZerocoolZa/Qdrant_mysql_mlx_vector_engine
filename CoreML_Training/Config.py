#[@GHOST]{[@file<Config.py>][@domain<coreml_training_config>][@role<configuration>][@return<Tuple3>][@auth<devin>][@date<2026-06-28>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<config>][@return<Tuple3>][@state<paths,hyperparams,io>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/CoreML_Training/Config.py>][@date<2026-06-28>][@session<coreml_training>]}
#[@SUMMARY]{Configuration constants for CoreML MLUpdateTask training proof-of-concept}
#[@CLASS]{Config — holds paths, hyperparameters, IO settings}
#[@METHOD]{none — constants only}

import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
BASE_MODEL_PATH = os.path.join(OUTPUT_DIR, "BaseClassifier.mlmodel")
UPDATABLE_MODEL_PATH = os.path.join(OUTPUT_DIR, "UpdatableClassifier.mlmodel")
TRAINED_MODEL_PATH = os.path.join(OUTPUT_DIR, "TrainedClassifier.mlmodel")
BASELINE_WEIGHTS_PATH = os.path.join(OUTPUT_DIR, "baseline_weights.npz")
TRAINED_WEIGHTS_PATH = os.path.join(OUTPUT_DIR, "trained_weights.npz")

INPUT_DIM = 4
HIDDEN_DIM = 8
NUM_CLASSES = 3
NUM_SAMPLES = 200
BATCH_SIZE = 32
EPOCHS = 20
LEARNING_RATE = 0.01
ADAM_BETA1 = 0.9
ADAM_BETA2 = 0.999
ADAM_EPS = 1e-08
SEED = 42

INPUT_NAME = "features"
OUTPUT_NAME = "class_probs"
LOSS_NAME = "lossLayer"
LAYER_FC1 = "fc1"
LAYER_FC2 = "fc2"
CLASS_LABELS = ["class_0", "class_1", "class_2"]

PYTHON_BIN = "/usr/local/bin/python3"
SWIFT_BIN = "/usr/bin/swift"

def ensure_output_dir():
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    return (1, OUTPUT_DIR, None)
