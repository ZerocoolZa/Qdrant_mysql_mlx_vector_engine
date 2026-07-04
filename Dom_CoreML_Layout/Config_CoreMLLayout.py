#[@GHOST]
#[@VBSTYLE]
#[@FILEID] Config_CoreMLLayout.py
#[@SUMMARY] Constants for CoreML on-device layout policy training
#[@CLASS] Config_CoreMLLayout
#[@METHOD] none
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 700

INPUT_DIM = 40
HIDDEN_DIM = 128
OUTPUT_DIM = 10

MODEL_NAME = "LayoutPolicyMLP"
MODEL_PATH_MLPACKAGE = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/LayoutPolicyMLP.mlpackage"
MODEL_PATH_PYTORCH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/brain_model_v3.pt"
MODEL_PATH_TRAINED = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/LayoutPolicyTrained.mlpackage"

TRAINING_EPOCHS = 50
TRAINING_BATCH_SIZE = 16
LEARNING_RATE = 0.001
MAX_EPISODES = 200

NUM_ROLES = 5
ROLE_NAMES = ["top", "left", "center", "right", "bottom"]
ROLE_SIZES = {
    "top": (800, 60),
    "left": (200, 400),
    "center": (600, 400),
    "right": (200, 400),
    "bottom": (800, 60),
}

NODE_FEATURES_PER_NODE = 8
MAX_NODES = 5

SWIFT_SCRIPT_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coreml_layout_update.swift"
TRAINING_DATA_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/training_data.json"
